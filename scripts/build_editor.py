import argparse
import hashlib
import html
import json
import os
from pathlib import Path
from urllib.parse import quote
from captions import read
from common import output_path


def main():
    p=argparse.ArgumentParser();p.add_argument('--srt',required=True);p.add_argument('--video');p.add_argument('--output',required=True);a=p.parse_args()
    srt=Path(a.srt).resolve();out=output_path(a.output,[srt]+([a.video] if a.video else []));cues=read(srt)
    template=(Path(__file__).resolve().parents[1]/'assets/editor.html').read_text(encoding='utf-8')
    data=json.dumps(cues,ensure_ascii=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    draft='captions-'+hashlib.sha256((str(srt)+data).encode()).hexdigest()[:24]
    src=''
    if a.video:
        path=Path(a.video).resolve()
        if not path.is_file():raise FileNotFoundError(path)
        src='src="'+html.escape(quote(os.path.relpath(path,out.parent).replace(os.sep,'/')),quote=True)+'"'
    template=template.replace('__CUES__',data).replace('__DRAFT__',json.dumps(draft)).replace('__VIDEO__',src)
    with out.open('x',encoding='utf-8') as f:f.write(template)
    print(out)


if __name__=='__main__':main()
