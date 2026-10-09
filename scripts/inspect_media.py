import argparse
import hashlib
import json
from pathlib import Path
from common import probe, json_write, output_path


def main():
    p = argparse.ArgumentParser(description='Inspect local media; optional full file hash.')
    p.add_argument('inputs', nargs='+'); p.add_argument('--output'); p.add_argument('--sha256', action='store_true')
    a = p.parse_args(); result = []
    for name in a.inputs:
        path = Path(name).resolve(); st = path.stat(); info = probe(path)
        item = {'path': str(path), 'bytes': st.st_size, 'mtime_ns': st.st_mtime_ns, 'probe': info}
        if a.sha256:
            with path.open('rb') as f:
                item['sha256'] = hashlib.file_digest(f, 'sha256').hexdigest()
        result.append(item)
    if a.output: json_write(output_path(a.output, a.inputs), result)
    else: print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
