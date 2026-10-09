"""Local, dependency-light media helpers. Never invokes a shell."""
import hashlib
import json
import math
import os
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path


def run(args):
    p = subprocess.run([str(a) for a in args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise RuntimeError(p.stderr.decode('utf-8', errors='replace')[-6000:])
    return p.stdout


def require_tools():
    for name in ('ffmpeg', 'ffprobe'):
        if not shutil.which(name):
            raise RuntimeError(f'Missing executable: {name}')


def probe(path):
    require_tools()
    return json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                           '-show_chapters', '-of', 'json', Path(path).resolve()]))


def video(info):
    return next(s for s in info['streams'] if s['codec_type'] == 'video')


def audio(info):
    return next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)


def duration(info):
    return float(info['format']['duration'])


def fps(v):
    return Fraction(v.get('avg_frame_rate', '0/1'))


def rotation(v):
    return sum(float(s.get('rotation', 0)) for s in v.get('side_data_list', [])) or float(v.get('tags', {}).get('rotate', 0))


def standard_sdr(info):
    if sum(s['codec_type']=='video' for s in info['streams'])!=1 or sum(s['codec_type']=='audio' for s in info['streams'])>1:
        raise ValueError('Renderer needs one video and at most one audio track; choose/preserve additional tracks explicitly.')
    extras=[s for s in info['streams'] if s['codec_type'] not in ('video','audio') and not (s['codec_type']=='data' and info.get('chapters') and s.get('codec_tag_string')=='text')]
    if extras:raise ValueError('Embedded subtitles/additional tracks need an explicit preservation workflow before rendering.')
    v = video(info)
    if rotation(v) % 360:
        raise ValueError('Rotated input: normalize orientation deliberately before using this renderer.')
    if v.get('pix_fmt') not in ('yuv420p', 'yuvj420p') or v.get('color_transfer') in ('smpte2084', 'arib-std-b67'):
        raise ValueError('Renderer supports 8-bit SDR yuv420p only; preserve other formats in a dedicated workflow.')
    a, r = fps(v), Fraction(v.get('r_frame_rate', '0/1'))
    if a <= 0 or r <= 0 or abs(float(a / r) - 1) > .0001:
        raise ValueError('VFR/irregular timing: choose an explicit frame-rate conversion first.')
    if abs(float(v.get('start_time', 0))) > .001:
        raise ValueError('Normalize nonzero source start timestamps explicitly before rendering.')
    if v.get('sample_aspect_ratio', '1:1') not in ('1:1', '0:1', 'N/A'):
        raise ValueError('Non-square pixels require an explicit display-aspect conversion.')
    return v


def decoded_count(path):
    x = json.loads(run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames',
                       '-show_entries', 'stream=nb_read_frames', '-of', 'json', path]))
    return int(x['streams'][0]['nb_read_frames'])


def output_path(path, inputs=()):
    p = Path(path).expanduser().resolve()
    if p.exists() or p.is_symlink() or p in [Path(x).resolve() for x in inputs]:
        raise FileExistsError(f'Refusing to overwrite: {p}')
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def publish(temp, target):
    # Atomic create-if-absent, same filesystem because temporary files live beside target.
    os.link(temp, target)
    Path(temp).unlink()


def json_write(path, data):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def finite(value):
    v = float(value)
    if not math.isfinite(v):
        raise ValueError('Time must be finite')
    return v


def local_path(base, value):
    p = Path(value).expanduser()
    return (p if p.is_absolute() else Path(base) / p).resolve()


def frame_hash(path, time=0):
    return run(['ffmpeg', '-v', 'error', '-ss', f'{time:.9f}', '-i', path,
                '-map', '0:v:0', '-frames:v', '1', '-f', 'hash', '-hash', 'sha256', '-']).decode().strip()


def packet_hashes(path, stream):
    d = json.loads(run(['ffprobe', '-v', 'error', '-select_streams', stream, '-show_packets',
                       '-show_data_hash', 'sha256', '-show_entries', 'packet=data_hash', '-of', 'json', path]))
    return [p['data_hash'] for p in d['packets']]


def suffix_match(original, kept):
    if not kept:
        return False
    return len(kept) <= len(original) and original[-len(kept):] == kept


def decode_check(path):
    run(['ffmpeg', '-v', 'error', '-xerror', '-threads', '4', '-i', path,
         '-map', '0:v:0', '-map', '0:a:0?', '-f', 'null', '-'])


def ffmeta(chapters, length):
    def escape(s):
        return str(s).replace('\\', '\\\\').replace('\n', ' ').replace('\r', ' ').replace('=', '\\=').replace(';', '\\;').replace('#', '\\#')
    text = ';FFMETADATA1\n'
    for i, c in enumerate(chapters):
        end = chapters[i + 1]['start'] if i + 1 < len(chapters) else length
        text += f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={round(c['start']*1000)}\nEND={round(end*1000)}\ntitle={escape(c['title'])}\n"
    return text
