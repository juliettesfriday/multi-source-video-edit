import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import captions
from common import output_path,probe,video,frame_hash,duration,packet_hashes,suffix_match


def cli(script,*args,ok=True):
    p=subprocess.run([sys.executable,str(ROOT/'scripts'/script),*[str(x) for x in args]],capture_output=True,text=True)
    if ok and p.returncode:raise AssertionError(p.stderr)
    return p


def font_path():
    choices=[os.environ.get('TEST_FONT',''),'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/System/Library/Fonts/Supplemental/Arial.ttf','C:/Windows/Fonts/arial.ttf']
    return next((x for x in choices if x and Path(x).is_file()),None)


class SubtitleTests(unittest.TestCase):
    def test_unicode_bom_crlf_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'caption.srt';p.write_bytes('\ufeff1\r\n00:00:01,000 --> 00:00:02,000\r\n中文 AI\r\n第二行\r\n'.encode())
            c=captions.read(p);self.assertEqual(c[0]['text'],'中文 AI\n第二行');p.write_text(captions.dumps(c));self.assertEqual(captions.read(p),c)

    def test_overlap_and_nonfinite_rejected(self):
        with self.assertRaises(ValueError):captions.validate([dict(start=0,end=100,text='a'),dict(start=99,end=200,text='b')])
        with self.assertRaises(ValueError):captions.ms(float('nan'))
        with self.assertRaises(ValueError):captions.parse_stamp('00:99:00,000')

    def test_cut_half_open(self):
        c=[dict(start=0,end=1000,text='gone'),dict(start=1000,end=2500,text='kept'),dict(start=2500,end=3000,text='gone')]
        self.assertEqual(captions.trim(c,1000,2500),[dict(start=0,end=1500,text='kept')])

    def test_repeated_source_and_boundary_warning(self):
        source=str(Path('example.mp4').resolve());c=[dict(start=0,end=2000,text='phrase')]
        segments=[dict(source=source,start=.5,end=1.5),dict(source=source,start=0,end=2)]
        out,w=captions.map_edl(segments,{source:c});self.assertEqual([(x['start'],x['end']) for x in out],[(0,1000),(1000,3000)]);self.assertEqual(len(w),1)

    def test_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'keep';p.write_text('unchanged')
            with self.assertRaises(FileExistsError):output_path(p)
            self.assertEqual(p.read_text(),'unchanged')

    def test_editor_html_injection(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);srt=p/'x.srt';srt.write_text(captions.dumps([dict(start=0,end=1000,text='</script><script>alert(1)</script>中文')]))
            cli('build_editor.py','--srt',srt,'--output',p/'editor.html');html=(p/'editor.html').read_text()
            self.assertNotIn('</script><script>alert(1)',html);self.assertIn('\\u003c/script>',html)
            self.assertNotIn('__CUES__',html)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg/ffprobe required')
class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='skill-media-test-');cls.p=Path(cls.tmp.name);cls.src=cls.p/'source.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=640x360:rate=30:duration=6','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=6','-c:v','libx264','-threads','2','-g','60','-keyint_min','60','-sc_threshold','0','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',str(cls.src)],check=True)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_nonkeyframe_trim_exact_and_packet_identical(self):
        out=self.p/'trim.mp4';cli('trim.py',self.src,out,'--start','1.2','--verify-decode')
        self.assertEqual(frame_hash(out),frame_hash(self.src,1.2));self.assertTrue(suffix_match(packet_hashes(self.src,'v:0'),packet_hashes(out,'v:0')))
        self.assertAlmostEqual(duration(probe(out)),4.8,delta=.05)
        self.assertNotEqual(cli('trim.py',self.src,out,'--start','2',ok=False).returncode,0)

    def test_trim_preserves_subtitle_and_two_audio_tracks(self):
        subs=self.p/'embedded.srt';subs.write_text(captions.dumps([dict(start=0,end=3000,text='First'),dict(start=3000,end=6000,text='Second')]))
        source=self.p/'multitrack.mp4'
        subprocess.run(['ffmpeg','-v','error','-i',str(self.src),'-i',str(subs),'-map','0:v','-map','0:a','-map','0:a','-map','1:0','-c','copy','-c:s','mov_text',str(source)],check=True)
        out=self.p/'multitrack-trim.mp4';cli('trim.py',source,out,'--start','1.2','--verify-decode');streams=probe(out)['streams']
        self.assertEqual(sum(x['codec_type']=='audio' for x in streams),2)
        self.assertEqual(sum(x['codec_type']=='subtitle' for x in streams),1)

    def test_two_segment_assembly_and_mapping(self):
        edl=self.p/'edit.json';edl.write_text(json.dumps({'segments':[dict(source='source.mp4',start=.5,end=1.5),dict(source='source.mp4',start=3,end=4.5)]}))
        out=self.p/'joined.mp4';cli('assemble.py',edl,out,'--verify-decode');info=probe(out)
        self.assertAlmostEqual(duration(info),2.5,delta=.08);self.assertEqual((video(info)['width'],video(info)['height']),(640,360))
        srt=self.p/'source.srt';srt.write_text(captions.dumps([dict(start=500,end=1500,text='first'),dict(start=3000,end=4500,text='second')]))
        manifest=self.p/'subs.json';manifest.write_text(json.dumps({'source.mp4':'source.srt'}));mapped=self.p/'mapped.srt'
        cli('captions.py','map',edl,manifest,mapped);c=captions.read(mapped);self.assertEqual([x['start'] for x in c],[0,1000]);self.assertEqual(c[-1]['end'],2500)
        self.assertEqual(json.loads(Path(str(mapped)+'.review.json').read_text()),[])

    @unittest.skipUnless(importlib.util.find_spec('PIL') and font_path(),'Pillow and TEST_FONT/system font required')
    def test_footer_preview_render_chapters_audio_tail(self):
        from PIL import Image
        srt=self.p/'footer.srt';srt.write_text(captions.dumps([dict(start=0,end=3000,text='First example caption'),dict(start=3000,end=6000,text='Second example\nTwo lines')]))
        config=self.p/'style.json';config.write_text(json.dumps(dict(source='source.mp4',srt='footer.srt',font=font_path(),reference_width=3240,subtitle_size=100,footer_height=420,chapters=[dict(start=0,title='Intro'),dict(start=3,title='Demo')]),ensure_ascii=False))
        png=self.p/'preview.png';cli('render_footer.py','--config',config,'--preview-at','1','--output',png)
        with Image.open(png) as im:self.assertEqual(im.size,(640,444))
        out=self.p/'footer.mp4';cli('render_footer.py','--config',config,'--output',out,'--verify-decode');info=probe(out)
        self.assertEqual((video(info)['width'],video(info)['height']),(640,444));self.assertEqual(int(video(info)['nb_frames']),180)
        self.assertEqual([x['tags']['title'] for x in info['chapters']],['Intro','Demo'])
        report=json.loads(Path(str(out)+'.report.json').read_text());self.assertTrue(report['full_audio_preserved']);self.assertTrue(report['full_decode'])

    @unittest.skipUnless(importlib.util.find_spec('PIL') and font_path(),'Pillow and TEST_FONT/system font required')
    def test_dense_chapters_fail_before_render(self):
        from render_footer import Footer
        cfg=dict(font=font_path(),chapters=[dict(start=0,title='A very long introductory chapter'),dict(start=.01,title='Another very long chapter')])
        with self.assertRaises(ValueError):Footer(cfg,[],640,6,self.p)


if __name__=='__main__':unittest.main()
