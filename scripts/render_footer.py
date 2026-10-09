"""Portable A100/C-inspired subtitle and chapter footer; source pixels retain their width."""
import argparse
import bisect
import io
import json
import math
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageColor, ImageDraw, ImageFont
from common import (probe,video,audio,duration,fps,standard_sdr,decoded_count,output_path,
                    local_path,run,publish,json_write,ffmeta,decode_check,packet_hashes)
from captions import read,validate,ms


def wrap(text,font,width):
    lines=text.split('\n')
    if len(lines)>2:raise ValueError('Caption has more than two lines: '+text)
    if all(font.getlength(s)<=width for s in lines):return lines
    if len(lines)>1:raise ValueError('Explicit caption line too wide: '+text)
    options=[]
    for i in range(1,len(text)):
        if text[i-1].isascii() and text[i].isascii() and text[i-1].isalnum() and text[i].isalnum():continue
        a,b=text[:i].rstrip(),text[i:].lstrip();wa,wb=font.getlength(a),font.getlength(b)
        if max(wa,wb)<=width:options.append((abs(wa-wb),[a,b]))
    if not options:raise ValueError('Caption too long; split it in the SRT: '+text)
    return min(options,key=lambda v:v[0])[1]


class Footer:
    def __init__(self,cfg,cues,width,length,base):
        self.cfg=cfg;self.cues=validate(cues,ms(length)+1);self.starts=[c['start'] for c in cues];self.w=width;self.length=length
        self.scale=width/float(cfg.get('reference_width',3240))
        if self.scale<=0:raise ValueError('Invalid reference_width')
        def px(n):return max(1,round(n*self.scale))
        self.px=px;self.h=2*math.ceil(float(cfg.get('footer_height',420))*self.scale/2)
        if self.h<px(360):raise ValueError('Footer too short for subtitle and chapter areas')
        self.size=px(cfg.get('subtitle_size',100));font=local_path(base,cfg['font']);self.font=ImageFont.truetype(str(font),self.size)
        self.label=ImageFont.truetype(str(local_path(base,cfg.get('label_font',cfg['font']))),px(cfg.get('label_size',34)))
        self.clock=ImageFont.truetype(str(font),px(32));self.margin=px(120);self.x0=self.margin;self.x1=width-self.margin;self.y=self.h-px(94)
        self.ch=cfg['chapters']
        if not self.ch or self.ch[0]['start']!=0:raise ValueError('First chapter must start at zero')
        previous=-1
        self.positions=[];rects=[]
        for c in self.ch:
            t=float(c['start'])
            if not math.isfinite(t) or not previous<t<length:raise ValueError('Invalid chapter timing')
            previous=t;lines=c.get('lines',[c['title']]);c['lines']=lines
            if not 1<=len(lines)<=2 or not all(isinstance(s,str) and s for s in lines):raise ValueError('Chapter needs one or two display lines')
            x=self.x0+(self.x1-self.x0)*t/length;self.positions.append(x)
            w=max(self.label.getlength(s) for s in lines);left=x if t==0 else x-w/2;right=left+w
            if left<0 or right>width:raise ValueError('Chapter label outside canvas')
            if rects and left<rects[-1][1]+px(20):raise ValueError('Chapter labels overlap; shorten display lines or reduce label_size')
            rects.append((left,right))
        for c in cues:
            lines=wrap(c['text'],self.font,width-2*self.margin)
            center=(self.h-px(210))/2+px(5)
            for n,line in enumerate(lines):
                box=self.font.getbbox(line,anchor='mm');cy=center+(n-(len(lines)-1)/2)*self.size*1.14
                if cy+box[1]<px(6) or cy+box[3]>self.h-px(205):
                    raise ValueError('Subtitle exceeds reserved vertical area; increase footer_height or adjust line breaks')
        self.grad=Image.new('RGB',(self.x1-self.x0+1,px(7)));d=ImageDraw.Draw(self.grad)
        col0=ImageColor.getrgb(cfg.get('progress_start','#38acf0'));col1=ImageColor.getrgb(cfg.get('progress_end','#bb8fed'))
        for x in range(self.grad.width):
            q=x/max(1,self.grad.width-1);d.line((x,0,x,self.grad.height),fill=tuple(round(a+(b-a)*q) for a,b in zip(col0,col1)))
        self.cache=None;self.key=None

    def render(self,t):
        p=self.px;active=max(0,bisect.bisect_right([c['start'] for c in self.ch],t)-1);idx=bisect.bisect_right(self.starts,round(t*1000))-1
        text=self.cues[idx]['text'] if idx>=0 and round(t*1000)<self.cues[idx]['end'] else '';key=(active,text,int(t))
        if key!=self.key:
            im=Image.new('RGB',(self.w,self.h),self.cfg.get('background','#171522'));d=ImageDraw.Draw(im)
            lines=wrap(text,self.font,self.w-2*self.margin);center=(self.h-p(210))/2+p(5)
            for n,line in enumerate(lines):d.text((self.w/2,center+(n-(len(lines)-1)/2)*self.size*1.14),line,font=self.font,fill=self.cfg.get('text_color','white'),anchor='mm')
            d.line((self.x0,self.y,self.x1,self.y),fill='#696578',width=p(5))
            for i,(c,x) in enumerate(zip(self.ch,self.positions)):
                color='#d0b6ff' if i==active else '#a9b6ef' if i<active else '#a49fb7';top=self.h-p(187 if len(c['lines'])==2 else 166)
                for n,line in enumerate(c['lines']):d.text((x,top+n*p(40)),line,font=self.label,fill=color,anchor='lt' if i==0 else 'mt')
            total=round(self.length);d.text((self.x1,self.h-p(34)),f'{int(t)//60:02}:{int(t)%60:02} / {total//60:02}:{total%60:02}',font=self.clock,fill='#e5e1ef',anchor='rm')
            self.cache=im;self.key=key
        im=self.cache.copy();d=ImageDraw.Draw(im);x=self.x0+(self.x1-self.x0)*min(1,max(0,t/self.length));n=max(1,round(x-self.x0));im.paste(self.grad.resize((n,p(7))),(self.x0,self.y-p(3)))
        for i,cx in enumerate(self.positions):d.ellipse((cx-p(12),self.y-p(12),cx+p(12),self.y+p(12)),fill='#92a5fa' if i<=active else '#171522',outline='#b9adff' if i<=active else '#76728c',width=p(4))
        r=p(17);d.polygon([(x,self.y-r),(x+r,self.y),(x,self.y+r),(x-r,self.y)],fill='#d2b0ff');return im


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--output',required=True);ap.add_argument('--preview-at',type=float);ap.add_argument('--verify-decode',action='store_true');a=ap.parse_args()
    config=Path(a.config).resolve();cfg=json.loads(config.read_text(encoding='utf-8'));src=local_path(config.parent,cfg['source']);srt=local_path(config.parent,cfg['srt']);out=output_path(a.output,[src,srt,config]);info=probe(src);v=standard_sdr(info);rate=fps(v);length=duration(info);w=v['width'];h=int(cfg.get('crop_height',v['height']))
    if h<=0 or h>v['height'] or h%2 or w%2:raise ValueError('Invalid/even-pixel crop dimensions')
    footer=Footer(cfg,read(srt),w,length,config.parent)
    if a.preview_at is not None:
        if not 0<=a.preview_at<length:raise ValueError('Preview time outside source')
        data=run(['ffmpeg','-v','error','-ss',str(a.preview_at),'-i',src,'-frames:v','1','-f','image2pipe','-vcodec','png','-']);im=Image.open(io.BytesIO(data)).convert('RGB').crop((0,0,w,h));canvas=Image.new('RGB',(w,h+footer.h));canvas.paste(im);canvas.paste(footer.render(a.preview_at),(0,h))
        with out.open('xb') as f:canvas.save(f,format='PNG')
        print(out);return
    if out.suffix.lower()!='.mp4':raise ValueError('Output must be .mp4')
    report=output_path(str(out)+'.report.json');count=decoded_count(src);crf=int(cfg.get('crf',14))
    if not 0<=crf<=51:raise ValueError('Invalid CRF')
    with tempfile.TemporaryDirectory(prefix='.footer-',dir=out.parent) as td:
        td=Path(td);meta=td/'chapters.txt';meta.write_text(ffmeta(cfg['chapters'],length),encoding='utf-8');encoded=td/'video.mp4';complete=td/'complete.mp4';log=td/'ffmpeg.log';sound=td/'audio.m4a'
        has_audio=audio(info) is not None
        if has_audio:run(['ffmpeg','-v','error','-i',src,'-vn','-c:a','aac','-b:a','320k','-ar','48000',sound])
        cmd=['ffmpeg','-hide_banner','-threads','4','-i',str(src),'-thread_queue_size','16','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{w}x{footer.h}','-framerate',str(rate),'-i','pipe:0','-f','ffmetadata','-i',str(meta)]
        fc=f'[0:v]crop={w}:{h}:0:0,pad={w}:{h+footer.h}:0:0[main];[main][1:v]overlay=0:{h}:eof_action=repeat:format=yuv420[out]'
        cmd+=['-filter_complex_threads','2','-filter_complex',fc,'-map','[out]','-map_metadata','0','-map_chapters','2','-an','-c:v','libx264','-preset','fast','-crf',str(crf),'-threads','4','-pix_fmt','yuv420p','-fps_mode','passthrough','-enc_time_base',f'1:{rate.numerator}','-video_track_timescale',str(rate.numerator),'-frames:v',str(count)]
        for key,flag in [('color_space','-colorspace'),('color_transfer','-color_trc'),('color_primaries','-color_primaries')]:
            if v.get(key) and v[key]!='unknown':cmd += [flag,v[key]]
        cmd += [str(encoded)]
        with log.open('w') as f:
            proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=f,stderr=f)
            try:
                for n in range(count+1):proc.stdin.write(footer.render(float(n/rate)).tobytes())
            except BrokenPipeError:pass
            finally:
                try:proc.stdin.close()
                except BrokenPipeError:pass
            rc=proc.wait()
        if rc:raise RuntimeError(log.read_text()[-6000:])
        mux=['ffmpeg','-v','error','-i',encoded]
        if has_audio:mux+=['-i',sound]
        mux+=['-map','0:v:0']+(['-map','1:a:0'] if has_audio else [])+['-map_metadata','0','-map_chapters','0','-c','copy','-movflags','+faststart',complete]
        run(mux);new=probe(complete)
        if decoded_count(complete)!=count:raise RuntimeError('Frame count changed')
        if has_audio and packet_hashes(sound,'a:0')!=packet_hashes(complete,'a:0'):raise RuntimeError('Audio tail packet loss')
        if abs(duration(new)-length)>max(.1,2/float(rate)):raise RuntimeError('Unexpected render duration')
        if a.verify_decode:decode_check(complete)
        publish(complete,out);json_write(report,{'source':str(src),'config':str(config),'frames':count,'fps':str(rate),'size':[w,h+footer.h],'subtitle_size_pixels':footer.size,'duration':duration(new),'reencoded':True,'full_audio_preserved':has_audio,'full_decode':a.verify_decode,'command':cmd})
    print(out)


if __name__=='__main__':main()
