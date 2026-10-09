"""Execute an approved EDL. Does not decide which spoken content to remove."""
import argparse
import json
import tempfile
from pathlib import Path
from fractions import Fraction
from captions import load_edl
from common import probe,video,audio,duration,standard_sdr,output_path,run,publish,json_write,decode_check


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('edl');p.add_argument('output');p.add_argument('--width',type=int);p.add_argument('--height',type=int);p.add_argument('--fps');p.add_argument('--crf',type=int,default=14);p.add_argument('--verify-decode',action='store_true');a=p.parse_args()
    segments=load_edl(a.edl);out=output_path(a.output,[a.edl,*[s['source'] for s in segments]]);report=output_path(str(out)+'.report.json')
    if out.suffix.lower()!='.mp4':raise ValueError('Output must be .mp4')
    infos={s['source']:probe(s['source']) for s in segments};formats=set()
    for s in segments:
        info=infos[s['source']];v=standard_sdr(info)
        if not audio(info):raise ValueError('EDL helper requires an audio track on every source; handle silent sources explicitly.')
        if s['end']>duration(info)+.001:raise ValueError('EDL exceeds source duration')
        formats.add((v['width'],v['height'],v['avg_frame_rate']))
    colors={tuple(video(info).get(k,'unknown') for k in ('color_space','color_transfer','color_primaries','color_range')) for info in infos.values()}
    if len(colors)>1:raise ValueError('Mixed color metadata: normalize color deliberately before assembly.')
    explicit=any(x is not None for x in (a.width,a.height,a.fps))
    if explicit and not all(x is not None for x in (a.width,a.height,a.fps)):raise ValueError('Specify width, height and fps together')
    if len(formats)>1 and not explicit:raise ValueError('Mixed formats: explicitly choose --width --height --fps')
    w,h,rate=(a.width,a.height,a.fps) if explicit else next(iter(formats))
    if w<=0 or h<=0 or w%2 or h%2 or Fraction(rate)<=0:raise ValueError('Invalid canvas/fps')
    if not 0<=a.crf<=51:raise ValueError('Invalid CRF')
    length=sum(s['end']-s['start'] for s in segments)
    with tempfile.TemporaryDirectory(prefix='.assemble-',dir=out.parent) as td:
        tmp=Path(td)/'joined.mp4';cmd=['ffmpeg','-v','error'];filters=[]
        for i,s in enumerate(segments):
            d=s['end']-s['start'];cmd+=['-threads','2','-ss',str(s['start']),'-t',str(d),'-i',s['source']]
            vf=f'[{i}:v]trim=duration={d},setpts=PTS-STARTPTS'
            if explicit:vf+=f',scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={rate}'
            filters += [vf+f'[v{i}]',f'[{i}:a]atrim=duration={d},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]']
        n=len(segments);filters.append(''.join(f'[v{i}][a{i}]' for i in range(n))+f'concat=n={n}:v=1:a=1[v][a]')
        cmd+=['-filter_complex_threads','2','-filter_complex',';'.join(filters),'-map','[v]','-map','[a]','-map_chapters','-1','-c:v','libx264','-preset','fast','-crf',str(a.crf),'-threads','4','-pix_fmt','yuv420p','-fps_mode','vfr','-c:a','aac','-b:a','320k','-movflags','+faststart',tmp]
        # Tag a homogeneous known source color space without inventing one.
        for key,flag in [('color_space','-colorspace'),('color_transfer','-color_trc'),('color_primaries','-color_primaries'),('color_range','-color_range')]:
            value=video(next(iter(infos.values()))).get(key)
            if value and value!='unknown':cmd[-1:-1]=[flag,value]
        run(cmd);result=probe(tmp)
        if abs(duration(result)-length)>max(.12,len(segments)/float(Fraction(rate))):raise RuntimeError('Unexpected assembly duration')
        if a.verify_decode:decode_check(tmp)
        publish(tmp,out);json_write(report,{'segments':segments,'duration':duration(result),'expected_duration':length,'canvas':[w,h],'target_fps':str(rate),'explicit_conversion':explicit,'reencoded':True,'full_decode':a.verify_decode,'command':[str(x) for x in cmd]})
    print(out)


if __name__=='__main__':main()
