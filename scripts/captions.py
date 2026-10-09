"""SRT validation, trimming and EDL mapping. All timestamps are integer milliseconds."""
import argparse
import json
import re
from pathlib import Path
from common import finite, json_write, local_path, output_path


def ms(value):
    return round(finite(value) * 1000)


def parse_stamp(s):
    m = re.fullmatch(r'(\d+):(\d{2}):(\d{2})[,.](\d{3})', s.strip())
    if not m: raise ValueError('Invalid SRT timestamp: ' + s)
    h, minute, sec, milli = map(int, m.groups())
    if minute >= 60 or sec >= 60: raise ValueError('Invalid minute/second: ' + s)
    return ((h * 60 + minute) * 60 + sec) * 1000 + milli


def stamp(n):
    if n < 0: raise ValueError('Negative timestamp')
    return f'{n//3600000:02}:{n//60000%60:02}:{n//1000%60:02},{n%1000:03}'


def validate(cues, length=None):
    previous = 0
    for i, c in enumerate(cues):
        if not isinstance(c['start'], int) or not isinstance(c['end'], int): raise ValueError('Expected integer milliseconds')
        if not 0 <= c['start'] < c['end'] or c['start'] < previous: raise ValueError(f'Invalid/overlapping cue {i+1}')
        if length is not None and c['end'] > length: raise ValueError(f'Cue {i+1} exceeds duration')
        if not c['text'].strip(): raise ValueError(f'Empty cue {i+1}')
        previous = c['end']
    return cues


def read(path):
    text = Path(path).read_text(encoding='utf-8-sig').replace('\r\n', '\n').replace('\r', '\n').strip()
    cues = []
    if not text: return cues
    for block in re.split(r'\n\s*\n', text):
        lines = block.splitlines(); k = next((i for i, s in enumerate(lines) if '-->' in s), None)
        if k is None: raise ValueError('Missing SRT timing line')
        parts = lines[k].split('-->')
        if len(parts) != 2: raise ValueError('Invalid SRT timing line')
        cues.append({'start': parse_stamp(parts[0]), 'end': parse_stamp(parts[1]), 'text': '\n'.join(lines[k+1:]).strip()})
    return validate(cues)


def dumps(cues):
    validate(cues)
    return '\n\n'.join(f"{i+1}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}" for i,c in enumerate(cues)) + ('\n' if cues else '')


def trim(cues, start, end=None):
    if start < 0 or (end is not None and end <= start): raise ValueError('Invalid trim range')
    result = []
    for c in cues:
        a, b = max(start, c['start']), min(end if end is not None else c['end'], c['end'])
        if b > a: result.append({'start': a-start, 'end': b-start, 'text': c['text']})
    return validate(result)


def load_edl(path):
    path = Path(path).resolve(); data = json.loads(path.read_text(encoding='utf-8'))
    if not data.get('segments'): raise ValueError('EDL needs at least one segment')
    segments = []
    for s in data['segments']:
        start, end = finite(s['start']), finite(s['end'])
        if start < 0 or end <= start: raise ValueError('Invalid EDL range')
        segments.append({'source': str(local_path(path.parent, s['source'])), 'start': start, 'end': end})
    return segments


def map_edl(segments, by_source):
    result, warnings, cursor = [], [], 0
    for i, s in enumerate(segments):
        a, b = ms(s['start']), ms(s['end'])
        if b <= a: raise ValueError('Range shorter than millisecond precision')
        source = str(Path(s['source']).resolve())
        if source not in by_source: raise ValueError('Missing subtitles for source: '+source)
        cues = by_source[source]
        for c in cues:
            if c['end'] > a and c['start'] < b and (c['start'] < a or c['end'] > b):
                warnings.append({'segment': i+1, 'source': source, 'cue': c, 'reason': 'Boundary cuts this cue; review words against audio.'})
        result.extend({**c, 'start': c['start']+cursor, 'end': c['end']+cursor} for c in trim(cues, a, b))
        cursor += b-a
    return validate(result), warnings


def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd', required=True)
    v=sub.add_parser('validate'); v.add_argument('input'); v.add_argument('--duration',type=float)
    t=sub.add_parser('trim'); t.add_argument('input'); t.add_argument('output'); t.add_argument('--start',type=float,required=True);t.add_argument('--end',type=float)
    m=sub.add_parser('map'); m.add_argument('edl');m.add_argument('manifest');m.add_argument('output')
    a=p.parse_args()
    if a.cmd=='validate':
        cues=validate(read(a.input),ms(a.duration) if a.duration is not None else None);print(f'{len(cues)} valid cues');return
    if a.cmd=='trim':
        cues=trim(read(a.input),ms(a.start),ms(a.end) if a.end is not None else None);inputs=[a.input]
    else:
        manifest=Path(a.manifest).resolve();data=json.loads(manifest.read_text(encoding='utf-8'))
        sources={str(local_path(manifest.parent,k)):read(local_path(manifest.parent,v)) for k,v in data.items()}
        cues,warnings=map_edl(load_edl(a.edl),sources);inputs=[a.edl,a.manifest,*[local_path(manifest.parent,v) for v in data.values()]]
        report=output_path(str(a.output)+'.review.json');json_write(report,warnings)
    out=output_path(a.output,inputs)
    with out.open('x',encoding='utf-8') as f:f.write(dumps(cues))
    print(out)


if __name__=='__main__':main()
