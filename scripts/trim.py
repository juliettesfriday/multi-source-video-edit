"""Exact playback trim with untouched compressed packets and MP4 edit lists."""
import argparse
import json
import tempfile
from pathlib import Path
from common import (probe,video,audio,duration,finite,output_path,publish,run,frame_hash,
                    packet_hashes,suffix_match,decode_check,json_write)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input');p.add_argument('output');p.add_argument('--start',type=float,required=True);p.add_argument('--verify-decode',action='store_true');a=p.parse_args()
    src=Path(a.input).resolve();out=output_path(a.output,[src]);report=output_path(str(out)+'.report.json')
    if out.suffix.lower()!='.mp4':raise ValueError('This helper uses MP4 edit lists; output must be .mp4')
    info=probe(src);start=finite(a.start)
    if not 0<=start<duration(info):raise ValueError('Start is outside source duration')
    if abs(float(video(info).get('start_time',0)))>.001:raise ValueError('Nonzero source timestamps require explicit normalization')
    unsupported=[s for s in info['streams'] if s['codec_type'] not in ('video','audio','subtitle') and not (s['codec_type']=='data' and info.get('chapters') and s.get('codec_tag_string')=='text')]
    if unsupported:raise ValueError('Unsupported extra streams: choose a preservation workflow instead of silently dropping them')
    with tempfile.TemporaryDirectory(prefix='.trim-',dir=out.parent) as td:
        temp=Path(td)/'trim.mp4'
        cmd=['ffmpeg','-v','error','-ss',f'{start:.9f}','-i',src,'-map','0:v','-map','0:a?','-map','0:s?','-map_chapters','0','-map_metadata','0','-c','copy','-avoid_negative_ts','disabled','-use_editlist','1','-movflags','+faststart',temp]
        run(cmd);new=probe(temp)
        if frame_hash(src,start)!=frame_hash(temp):raise RuntimeError('Visible first frame mismatch; do not deliver as exact trim. Use explicit high-quality re-encoding.')
        hashes={}
        for kind,selector in [('video','v'),('audio','a'),('subtitle','s')]:
            old_streams=[s for s in info['streams'] if s['codec_type']==kind]
            new_streams=[s for s in new['streams'] if s['codec_type']==kind]
            if len(old_streams)!=len(new_streams):raise RuntimeError('Track was lost: '+kind)
            for old,new_s in zip(old_streams,new_streams):
                if old['codec_name']!=new_s['codec_name']:raise RuntimeError('Track codec changed: '+kind)
        selectors=[f'{kind}:{i}' for kind,name in [('v','video'),('a','audio')] for i in range(sum(s['codec_type']==name for s in info['streams']))]
        for stream in selectors:
            original=packet_hashes(src,stream);kept=packet_hashes(temp,stream)
            if not suffix_match(original,kept):raise RuntimeError('Compressed packet verification failed: '+stream)
            hashes[stream]={'bit_identical_suffix':True,'packets':len(kept)}
        if abs(duration(new)-(duration(info)-start))>.1:raise RuntimeError('Unexpected output duration')
        if a.verify_decode:decode_check(temp)
        record={'source':str(src),'requested_start':start,'duration':duration(new),'width':video(new)['width'],'height':video(new)['height'],'strategy':'stream-copy + MP4 edit list','first_frame_matches':True,'packets':hashes,'full_decode':a.verify_decode,'command':[str(x) for x in cmd],'note':'Invisible preroll reference frames may remain. Test destination player/platform.'}
        publish(temp,out);json_write(report,record)
    print(json.dumps({'output':str(out),'report':str(report)},ensure_ascii=False))


if __name__=='__main__':main()
