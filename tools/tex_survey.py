"""4단계 그림 전수: 일본판 안의 모든 BFLIM(lytarc 속)·BFRES(FTEX)·GTX(따로·WARC 속)를 풀어
같은 그림(픽셀 데이터 MD5)은 한 번만 work/survey/tex/img/<번호>.png 로 저장하고,
모든 칸(중복 포함)을 work/survey/tex/index.jsonl 에 남긴다.
ptcl(SPBD) 속 텍스처는 형식 미해독이라 칸 수만 따로 센다(별도 작업).

사용: python -I tools/tex_survey.py
"""
import hashlib
import json
import os
import struct
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fzip  # noqa: E402
import gtx_lib  # noqa: E402
import nlib  # noqa: E402
import texdec  # noqa: E402
import warc  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]')
OUT = os.path.join(ROOT, 'work', 'survey', 'tex')
IMG = os.path.join(OUT, 'img')
seen = {}
stat = {'slots': 0, 'err': 0, 'ptcl': 0}


def save(idx, path, name, raw, W, H, fmt, tm, swz, kind, extra=None):
    h = hashlib.md5(raw).hexdigest()
    r = dict(path=path, name=name, kind=kind, w=W, h=H, fmt=fmt, tm=tm, md5=h)
    if extra:
        r.update(extra)
    stat['slots'] += 1
    if h in seen:
        r['dup_of'] = seen[h]
    else:
        n = len(seen)
        seen[h] = n
        r['id'] = n
        try:
            img = texdec.decode(raw, W, H, fmt, tm, swz)
            Image.fromarray(img, 'RGBA').save(os.path.join(IMG, '%05d.png' % n))
        except Exception as ex:  # noqa: BLE001
            r['err'] = str(ex)[:120]
            stat['err'] += 1
    idx.write(json.dumps(r, ensure_ascii=False) + '\n')


def walk(idx, path, data):
    if data[:4] == b'FZIP':
        data = fzip.unpack(data)
    if data[:4] == b'SARC':
        for n, b, hh in nlib.sarc_read(data)[1]:
            walk(idx, path + '//' + (n or '#%08x' % hh), b)
        return
    if data[:4] == b'WARC':
        for e in warc.read(data):
            walk(idx, path + '//' + e['name'], data[e['start']:e['start'] + e['size']])
        return
    low = path.lower()
    if low.endswith('.bflim') and data[-0x28:-0x24] == b'FLIM':
        i = texdec.flim_info(data)
        if i['format'] is None:
            stat['slots'] += 1
            stat['err'] += 1
            idx.write(json.dumps(dict(path=path, kind='bflim', err='flim fmt %d' % i['flim_format'])) + '\n')
            return
        save(idx, path, os.path.basename(path), i['data'], i['width'], i['height'], i['format'],
             i['tileMode'], i['swizzle'], 'bflim')
    elif data[:4] == b'FRES':
        for off, s, raw, name in texdec.ftex_list(data):
            save(idx, path, name, raw, s['width'], s['height'], s['format'], s['tileMode'], s['swizzle'], 'ftex')
    elif data[:4] == b'Gfx2':
        try:
            g = gtx_lib.gtx_parse(data)
            s = g['surf']
            ib = g['img_blk']
            raw = data[ib['data']:ib['data'] + ib['size']]
            save(idx, path, os.path.basename(path), raw, s['width'], s['height'], s['format'],
                 s['tileMode'], s['swizzle'], 'gtx', {'depth': s['depth']})
        except Exception as ex:  # noqa: BLE001
            stat['slots'] += 1
            stat['err'] += 1
            idx.write(json.dumps(dict(path=path, kind='gtx', err=str(ex)[:120])) + '\n')
    elif data[:4] == b'SPBD':
        stat['ptcl'] += 1
        idx.write(json.dumps(dict(path=path, kind='ptcl', note='텍스처 형식 미해독(따로 확인)')) + '\n')


def main():
    os.makedirs(IMG, exist_ok=True)
    t0 = time.time()
    n = 0
    with open(os.path.join(OUT, 'index.jsonl'), 'w', encoding='utf-8') as idx:
        for dp, dn, fn in os.walk(GAME):
            dn.sort()
            for f in sorted(fn):
                if not f.lower().endswith(('.fzip', '.bflim', '.bfres', '.gtx')):
                    continue
                p = os.path.join(dp, f)
                walk(idx, os.path.relpath(p, GAME).replace(os.sep, '/'), open(p, 'rb').read())
                n += 1
                if n % 100 == 0:
                    print('%d 묶음, 칸 %d, 고유 %d, %.0f초' % (n, stat['slots'], len(seen), time.time() - t0), flush=True)
    print('끝: 묶음 %d, 그림 칸 %d, 고유 %d, 디코드 실패 %d, ptcl %d, %.0f초' % (
        n, stat['slots'], len(seen), stat['err'], stat['ptcl'], time.time() - t0))


if __name__ == '__main__':
    main()
