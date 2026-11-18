"""원본 폴더의 모든 파일 MD5·크기를 기록한다.

사용: python -I tools/hash_original.py
결과: docs/original_hashes_<title id>.txt (경로\t크기\tMD5), 맨 아래 합계
"""
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = {
    '0005000010112d00': 'Game Wario [Game] [0005000010112d00]',  # 일본판 ASAJ (기준)
    '000500001011f200': 'Game Wario [Game] [000500001011f200]',  # 북미판 ASAE (참고)
}


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    for tid, folder in TARGETS.items():
        base = os.path.join(ROOT, folder)
        rows = []
        for dp, dn, fn in os.walk(base):
            dn.sort()
            for f in sorted(fn):
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, base).replace('\\', '/')
                rows.append((rel, os.path.getsize(p), md5(p)))
        rows.sort()
        out = os.path.join(ROOT, 'docs', f'original_hashes_{tid}.txt')
        total = sum(r[1] for r in rows)
        with open(out + '.tmp', 'w', encoding='utf-8', newline='\n') as w:
            w.write(f'# {folder}\n# path\tsize\tmd5\n')
            for r in rows:
                w.write(f'{r[0]}\t{r[1]}\t{r[2]}\n')
            w.write(f'# files={len(rows)} bytes={total}\n')
        os.replace(out + '.tmp', out)
        print(tid, 'files', len(rows), 'bytes', total)


if __name__ == '__main__':
    sys.exit(main())
