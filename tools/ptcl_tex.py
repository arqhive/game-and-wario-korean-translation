"""이펙트(ptcl, SPBD v0x32) 안 그림을 전부 풀어 PNG·확인 시트로 만든다.

구조(직접 찾음, 2026-11-13):
  머리 0x14 그림 묶음 위치, 0x18 크기.
  그림 정보(이미터 안): +0 u16 너비, +2 u16 높이, +4 타일 방식, +8 swizzle, +0x10 피치, +0x1c 00 01 02 03(성분 선택),
    +0x78 형식(eft 번호), +0x7c 데이터 크기, +0x80 그림 묶음 안 위치.
  eft 형식 → GX2: 4 = BC1(0x31), 8 = BC3(0x33) (후보 형식으로 풀어 그림으로 확인). 그 밖의 번호는 화면에 따로 찍는다.
찾기: 너비·높이가 2의 거듭제곱(1~2048), 타일 1~16, +0x1c 가 00 01 02 03 인 자리(정렬 4).

사용: python -I tools/ptcl_tex.py
결과: work/survey/tex/ptcl/img/NNNN.png, work/survey/tex/ptcl/index.json, work/survey/tex/ptcl/sheets/sheet_NN.png
"""
import collections
import hashlib
import json
import os
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fzip  # noqa: E402
import texdec  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]')
OUT = os.path.join(ROOT, 'work', 'survey', 'tex', 'ptcl')
EFT2GX2 = {4: 0x31, 8: 0x33, 3: 0x32, 7: 0x33}   # 3·7 은 크기로 추정 → 결과 그림으로 확인
OK = {1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048}


def main():
    os.makedirs(os.path.join(OUT, 'img'), exist_ok=True)
    os.makedirs(os.path.join(OUT, 'sheets'), exist_ok=True)
    index = []
    md5seen = {}
    fmtc = collections.Counter()
    fails = []
    nfile = 0
    for dp, dn, fn in os.walk(GAME):
        dn.sort()
        for f in sorted(fn):
            if '.ptcl' not in f:
                continue
            nfile += 1
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, GAME).replace(os.sep, '/')
            d = open(p, 'rb').read()
            if d[:4] == b'FZIP':
                d = fzip.unpack(d)
            texpos, texsize = struct.unpack('>II', d[0x14:0x1c])
            done = set()
            for o in range(0, texpos - 0x90, 4):
                w, h, tile = struct.unpack('>HHI', d[o:o + 8])
                if not (w in OK and h in OK and 1 <= tile <= 16 and d[o + 0x1c:o + 0x20] == b'\x00\x01\x02\x03'):
                    continue
                swz = struct.unpack('>I', d[o + 8:o + 12])[0]
                ef, size, pos = struct.unpack('>III', d[o + 0x78:o + 0x84])
                fmtc[ef] += 1
                if (pos, size) in done:
                    continue
                done.add((pos, size))
                raw = d[texpos + pos:texpos + pos + size]
                rec = {'path': rel, 'struct': o, 'w': w, 'h': h, 'tile': tile, 'eft_fmt': ef, 'pos': pos, 'size': size}
                md5 = hashlib.md5(raw).hexdigest()
                if md5 in md5seen:
                    rec['dup_of'] = md5seen[md5]
                    index.append(rec)
                    continue
                if ef not in EFT2GX2 or pos + size > texsize:
                    rec['error'] = '형식 모름' if ef not in EFT2GX2 else '범위 밖'
                    fails.append(rec)
                    index.append(rec)
                    continue
                try:
                    rgba = texdec.decode(raw, w, h, EFT2GX2[ef], tile, swz)
                except Exception as ex:  # noqa: BLE001
                    rec['error'] = str(ex)
                    fails.append(rec)
                    index.append(rec)
                    continue
                i = len(md5seen)
                md5seen[md5] = i
                rec['id'] = i
                Image.fromarray(rgba, 'RGBA').save(os.path.join(OUT, 'img', '%04d.png' % i))
                index.append(rec)
    json.dump(index, open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    ids = sorted(md5seen.values())
    CELL, COLS, ROWS = 128, 6, 8
    for s in range(0, len(ids), COLS * ROWS):
        sh = Image.new('RGB', (COLS * (CELL * 2 + 6), ROWS * (CELL + 14)), (20, 20, 20))
        dr = ImageDraw.Draw(sh)
        for k, i in enumerate(ids[s:s + COLS * ROWS]):
            im = Image.open(os.path.join(OUT, 'img', '%04d.png' % i))
            x, y = (k % COLS) * (CELL * 2 + 6), (k // COLS) * (CELL + 14)
            for j, c in enumerate(((70, 70, 70, 255), (200, 200, 200, 255))):
                bg = Image.new('RGBA', im.size, c)
                bg.alpha_composite(im)
                bg.thumbnail((CELL, CELL))
                sh.paste(bg.convert('RGB'), (x + j * (CELL + 2), y))
            dr.text((x + 2, y + CELL + 1), '%d %dx%d' % (i, im.size[0], im.size[1]), fill=(255, 255, 0))
        sh.save(os.path.join(OUT, 'sheets', 'sheet_%02d.png' % (s // (COLS * ROWS))))
    print('ptcl 파일', nfile, '그림 정보', len(index), '고유 그림', len(ids), '형식별(그림 정보 수)', dict(fmtc), '실패', len(fails))
    for r in fails[:10]:
        print('  실패', r)


if __name__ == '__main__':
    main()
