"""북미판 그림의 픽셀 MD5 전체 집합을 만들고, 일본판 고유 그림 중 북미판에 같은 픽셀이 없는 것을 뽑는다.
북미판이 바꾼 그림 = 글자가 든 그림일 가능성이 큰 대조용 목록(눈 검토 누락 찾기용, 이것으로 거르지 않음).

사용: python -I tools/tex_region_diff.py
결과: work/survey/tex/jp_only.json [고유 번호...], 화면에 개수
"""
import hashlib
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fzip  # noqa: E402
import gtx_lib  # noqa: E402
import nlib  # noqa: E402
import texdec  # noqa: E402
import warc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
US = os.path.join(ROOT, 'Game Wario [Game] [000500001011f200]')
T = os.path.join(ROOT, 'work', 'survey', 'tex')
md5s = set()


def walk(path, data):
    if data[:4] == b'FZIP':
        data = fzip.unpack(data)
    if data[:4] == b'SARC':
        for n, b, hh in nlib.sarc_read(data)[1]:
            walk(path + '//' + (n or ''), b)
        return
    if data[:4] == b'WARC':
        for e in warc.read(data):
            walk(path + '//' + e['name'], data[e['start']:e['start'] + e['size']])
        return
    if path.lower().endswith('.bflim') and data[-0x28:-0x24] == b'FLIM':
        i = texdec.flim_info(data)
        md5s.add(hashlib.md5(i['data']).hexdigest())
    elif data[:4] == b'FRES':
        for off, s, raw, name in texdec.ftex_list(data):
            md5s.add(hashlib.md5(raw).hexdigest())
    elif data[:4] == b'Gfx2':
        try:
            g = gtx_lib.gtx_parse(data)
            ib = g['img_blk']
            md5s.add(hashlib.md5(data[ib['data']:ib['data'] + ib['size']]).hexdigest())
        except Exception:  # noqa: BLE001
            pass


def main():
    for dp, dn, fn in os.walk(US):
        for f in fn:
            if f.lower().endswith(('.fzip', '.bflim', '.bfres', '.gtx')):
                p = os.path.join(dp, f)
                walk(os.path.relpath(p, US), open(p, 'rb').read())
    rs = [json.loads(l) for l in open(os.path.join(T, 'index.jsonl'), encoding='utf-8')]
    uniq = [r for r in rs if 'id' in r]
    jp_only = [r['id'] for r in uniq if r['md5'] not in md5s]
    json.dump(jp_only, open(os.path.join(T, 'jp_only.json'), 'w', encoding='utf-8'))
    print(f'북미판 고유 픽셀 {len(md5s)}, 일본판 고유 그림 {len(uniq)}, 북미판에 같은 픽셀 없는 일본판 그림 {len(jp_only)}')


if __name__ == '__main__':
    main()
