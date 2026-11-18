"""북미판 그림으로 갈아 끼울 칸을 북미판에서 꺼내 둔다(사용자 11/18).
  - 분홍 붓글씨 13장(Telephone GirlTypo00~12): 북미판은 글씨 대신 닌자 그림. 일본판과 크기·형식·길이 같음.
  - 스태프 사진 Staff116(ナシ): 북미판은 웃는 얼굴. 크기가 다름(일본판 160x160, 북미판 216x216) →
    북미판 그림을 160 으로 줄여 일본판 그림 파일에 다시 압축하고, 같은 「ナシ」 사본 Staff117~150 까지 35칸에 넣는다(사용자 11/18).
꺼낸 파일은 work/na_gfx/ 에, 목록은 work/na_gfx/manifest.json. 그림 빌드에서 같은 경로 칸에 그대로 넣는다.

사용: python -I tools/gw_na_gfx.py
"""
import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fzip  # noqa: E402
import gtx_lib  # noqa: E402
import nlib  # noqa: E402
import texdec  # noqa: E402
import warc  # noqa: E402
from PIL import Image  # noqa: E402
import numpy as np  # noqa: E402
import gw_gfx  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JP = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]')
NA = os.path.join(ROOT, 'Game Wario [Game] [000500001011f200]')
OUT = os.path.join(ROOT, 'work', 'na_gfx')
# 북미판 그림으로 바꿀 목록 id (work/gpt_graphics/list.json)
NA_IDS = [5538, 5554, 5555, 5623, 5647, 5648, 5711, 5731, 5804, 5821, 5837, 5839, 5885, 5412, 6137, 6138]
SIZE_MAY_DIFFER = {5412}
# 북미판에서 이름이 다른 칸(영어판 _ENG): YES·NO 는 가나 루비만 빠진 같은 글씨(사용자 11/18 교체)
NA_PATH = {6137: 'content/Pon/YesNoMan1/YesNoMan1.lytarc.fzip//timg/Yes_ENG^q.bflim',
           6138: 'content/Pon/YesNoMan1/YesNoMan1.lytarc.fzip//timg/No_ENG^q.bflim'}


def fetch(root, gp):
    parts = gp.split('//')
    data = open(os.path.join(root, *parts[0].split('/')), 'rb').read()
    for sub in parts[1:]:
        if data[:4] == b'FZIP':
            data = fzip.unpack(data)
        if data[:4] == b'WARC':
            m = {e['name']: data[e['start']:e['start'] + e['size']] for e in warc.read(data)}
        else:
            m = {n: b for n, b, h in nlib.sarc_read(data)[1]}
        data = m[sub]
    return data


def info(data):
    """(원시 데이터, 크기·형식 dict)"""
    if data[:4] == b'Gfx2':
        g = gtx_lib.gtx_parse(data); s = g['surf']; ib = g['img_blk']
        return data[ib['data']:ib['data'] + ib['size']], dict(width=s['width'], height=s['height'], format=s['format'],
                                                              tileMode=s['tileMode'], swizzle=s['swizzle'])
    f = texdec.flim_info(data)
    return f['data'], dict(width=f['width'], height=f['height'], format=f['format'], tileMode=f['tileMode'],
                           swizzle=f['swizzle'])


def main():
    rows = {r['id']: r for r in json.load(open(os.path.join(ROOT, 'work', 'gpt_graphics', 'list.json'), encoding='utf-8'))}
    os.makedirs(OUT, exist_ok=True)
    dups = {}
    for l in open(os.path.join(ROOT, 'work', 'survey', 'tex', 'index.jsonl'), encoding='utf-8'):
        e = json.loads(l)
        if 'dup_of' in e:
            dups.setdefault(e['dup_of'], []).append(e)
    manifest = []
    for i in NA_IDS:
        gp = rows[i]['game_path']
        a, b = fetch(JP, gp), fetch(NA, NA_PATH.get(i, gp))
        ra, fa = info(a)
        rb, fb = info(b)
        assert ra != rb, (i, '북미판이 일본판과 같음')
        # swizzle 은 bflim 머리에 함께 들어 있어 파일째 넣으면 같이 따라간다(YES·NO: 256 → 512)
        same = len(a) == len(b) and {k: v for k, v in fa.items() if k != 'swizzle'} == \
            {k: v for k, v in fb.items() if k != 'swizzle'}
        assert same or i in SIZE_MAY_DIFFER, (i, gp, fa, fb)
        rel = gp.replace('//', '__').replace('/', '__').replace('^', '_')
        img = texdec.decode(rb, fb['width'], fb['height'], fb['format'], fb['tileMode'], fb['swizzle'])
        if not same:
            # 크기가 다르면 북미판 그림을 일본판 크기로 줄여 일본판 그림 파일에 다시 압축(묶음 크기 그대로, 사용자 11/18)
            old = texdec.decode(ra, fa['width'], fa['height'], fa['format'], fa['tileMode'], fa['swizzle'])
            img = np.array(Image.fromarray(img, 'RGBA').resize((fa['width'], fa['height']), Image.LANCZOS))
            b, n, _ = gw_gfx.patch_blob(a, old, img)
            assert len(b) == len(a)
        open(os.path.join(OUT, rel), 'wb').write(b)
        Image.fromarray(img, 'RGBA').save(os.path.join(OUT, rel + '.png'))
        manifest.append(dict(id=i, game_path=gp, file=rel, same_size=same))
        # 같은 바이트 사본 자리(조사 색인 dup_of)도 같은 파일로 (11/18 실수: 사본 자리 누락)
        for e in dups.get(i, []):
            manifest.append(dict(id=i, game_path=e['path'], file=rel, same_size=same, dup_of=i))
        print(i, gp.split('/')[-1], '크기·형식 같음' if same else
              '크기 다름 %dx%d → 일본판 크기로 줄여 다시 압축' % (fb['width'], fb['height']), '사본 자리', len(dups.get(i, [])))
    json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('저장', len(manifest), '/', len(NA_IDS))


if __name__ == '__main__':
    main()
