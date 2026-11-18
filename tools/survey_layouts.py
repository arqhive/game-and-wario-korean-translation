"""레이아웃(lytarc=SARC)의 bflyt 가 쓰는 폰트와 글 칸(txt1) 기본 글을 센다.

사용: python -I tools/survey_layouts.py
결과: work/survey/layout_fonts.json
"""
import collections
import json
import os
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fzip  # noqa: E402
import nlib  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]', 'content')


def sections(b):
    e = '>' if b[4:6] == b'\xfe\xff' else '<'
    hs = struct.unpack(e + 'H', b[6:8])[0]
    n = struct.unpack(e + 'H', b[0x10:0x12])[0]
    p = hs
    for _ in range(n):
        mg = b[p:p + 4]
        sz = struct.unpack(e + 'I', b[p + 4:p + 8])[0]
        yield mg, p, sz, e
        p += sz


def main():
    font_use = collections.Counter()
    txt_total = 0
    txt_jp = 0
    samples = []
    per = {}
    for dp, dn, fn in os.walk(BASE):
        for f in fn:
            if not f.endswith('.lytarc.fzip'):
                continue
            rel = os.path.relpath(os.path.join(dp, f), BASE).replace('\\', '/')
            d = fzip.unpack(open(os.path.join(dp, f), 'rb').read())
            info, files = nlib.sarc_read(d)
            fonts_here = set()
            for name, b, h in files:
                if not name.endswith('.bflyt'):
                    continue
                fnl = []
                for mg, p, sz, e in sections(b):
                    if mg == b'fnl1':
                        cnt = struct.unpack(e + 'H', b[p + 8:p + 10])[0]
                        offs = [struct.unpack(e + 'I', b[p + 12 + i * 4:p + 16 + i * 4])[0] for i in range(cnt)]
                        for o in offs:
                            s = p + 12 + o
                            fnl.append(b[s:b.index(b'\0', s)].decode('ascii'))
                    elif mg == b'txt1':
                        txt_total += 1
                        # 기본 글: 텍스트 오프셋(pane 0x4C 뒤 구조, 버전마다 다름) — 대신 UTF-16 가나·한자 존재로 판정
                        body = b[p:p + sz]
                        found = False
                        for i in range(0x54, len(body) - 1, 2):
                            c = struct.unpack(e + 'H', body[i:i + 2])[0]
                            if 0x3040 <= c <= 0x30FF or 0x4E00 <= c <= 0x9FFF:
                                found = True
                                break
                        if found:
                            txt_jp += 1
                            if len(samples) < 5:
                                samples.append((rel, name))
                for x in fnl:
                    font_use[x] += 1
                    fonts_here.add(x)
            per[rel] = sorted(fonts_here)
    os.makedirs(os.path.join(ROOT, 'work', 'survey'), exist_ok=True)
    s = json.dumps(per, ensure_ascii=False, indent=1)
    open(os.path.join(ROOT, 'work', 'survey', 'layout_fonts.json'), 'w', encoding='utf-8').write(s)
    print('bflyt 폰트 참조(파일 수):', dict(font_use.most_common()))
    print(f'txt1 칸 {txt_total}, 가나·한자가 든 칸 {txt_jp}', samples)


if __name__ == '__main__':
    main()
