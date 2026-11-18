"""일본판·북미판 원본 해시 기록을 비교한다(같은 경로 파일이 같은지).

사용: python -I tools/cmp_regions.py
"""
import collections
import os
import sys as _sys
_sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(tid):
    m = {}
    for line in open(os.path.join(ROOT, 'docs', f'original_hashes_{tid}.txt'), encoding='utf-8'):
        if line.startswith('#'):
            continue
        p, s, h = line.rstrip('\n').split('\t')
        m[p] = (int(s), h)
    return m


def main():
    jp, us = load('0005000010112d00'), load('000500001011f200')
    same = [p for p in jp if p in us and jp[p][1] == us[p][1]]
    diff = [p for p in jp if p in us and jp[p][1] != us[p][1]]
    jo = [p for p in jp if p not in us]
    uo = [p for p in us if p not in jp]
    print(f'같음 {len(same)}, 다름 {len(diff)}, 일본판만 {len(jo)}, 북미판만 {len(uo)}')
    top = collections.Counter('/'.join(p.split('/')[:2]) for p in diff)
    print('다른 파일(폴더별):', dict(top.most_common()))
    print('다른 파일 중 영상·사운드:', [p for p in diff if 'Movie' in p or 'Sound/' in p and 'bfstm' not in p])
    ext = collections.Counter(os.path.splitext(p.replace('.fzip', ''))[1] for p in diff)
    print('다른 파일 확장자:', dict(ext))
    print('일본판만(앞 20):', jo[:20])
    print('북미판만 폴더:', dict(collections.Counter('/'.join(p.split('/')[:3]) for p in uo).most_common(15)))


if __name__ == '__main__':
    main()
