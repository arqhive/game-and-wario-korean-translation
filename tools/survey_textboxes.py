"""모든 bflyt 의 글 상자(txt1)를 work/survey/textboxes.json 으로(4단계, 3단계 창 측정에도 씀).

FLYT v2.2(0x02020000, 1,288개 전부) txt1: +0x44 scale(2f) +0x4C size(2f) +0x54 bufBytes +0x56 strBytes +0x58 mat
 +0x5A font +0x5C textPos(u8) +0x5D align(u8) +0x5E flags(u16) +0x60 italic +0x64 textOff +0x70 fontSize(2f)
 +0x78 charSpace +0x7C lineSpace +0x80 textIDOff  (닌텐도 랜드 survey_textboxes.py 와 같은 구조)
같은 이름 레이아웃이 여러 묶음에 있어도 거르지 않고 전부 기록한다(dup 칸에 첫 위치).
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
rows = []
first = {}


def cstr(d, o):
    return d[o:d.index(b'\0', o)].decode('ascii', 'replace')


def bflyt(arc, name, d):
    p = struct.unpack('>H', d[6:8])[0]
    nb = struct.unpack('>H', d[0x10:0x12])[0]
    fl, stack, last = [], [], None
    key = (name, d)
    dup = first.get(hash(d))
    if dup is None:
        first[hash(d)] = arc + '//' + name
    for _ in range(nb):
        mg = d[p:p + 4]
        sz = struct.unpack('>I', d[p + 4:p + 8])[0]
        if mg == b'fnl1':
            n = struct.unpack('>H', d[p + 8:p + 10])[0]
            fl = [cstr(d, p + 12 + struct.unpack('>I', d[p + 12 + i * 4:p + 16 + i * 4])[0]) for i in range(n)]
        elif mg in (b'pan1', b'pic1', b'txt1', b'wnd1', b'bnd1', b'prt1'):
            last = d[p + 0x0C:p + 0x24].split(b'\0')[0].decode('ascii', 'replace')
            if mg == b'txt1':
                def f(o, t='>f'):
                    return struct.unpack(t, d[p + o:p + o + struct.calcsize(t)])[0]
                toff, strb, idoff = f(0x64, '>I'), f(0x56, '>H'), f(0x80, '>I')
                txt = d[p + toff:p + toff + strb].decode('utf-16-be', 'replace').rstrip('\0') if toff and strb else ''
                rows.append(dict(arc=arc, layout=name, pane=last, parents=list(stack),
                                 scale=[round(f(0x44), 3), round(f(0x48), 3)], size=[round(f(0x4C), 2), round(f(0x50), 2)],
                                 font=fl[f(0x5A, '>H')] if f(0x5A, '>H') < len(fl) else '?',
                                 fsize=[round(f(0x70), 2), round(f(0x74), 2)],
                                 cspace=round(f(0x78), 2), lspace=round(f(0x7C), 2), pos=d[p + 0x5C], align=d[p + 0x5D],
                                 flags=f(0x5E, '>H'), bufbytes=f(0x54, '>H'),
                                 textid=cstr(d, p + idoff) if idoff else '', text=txt,
                                 dup_of=dup))
        elif mg == b'pas1':
            stack.append(last)
        elif mg == b'pae1':
            stack.pop()
        p += sz


def main():
    for dp, dn, fn in os.walk(BASE):
        dn.sort()
        for f in sorted(fn):
            if not f.endswith('.lytarc.fzip'):
                continue
            arc = os.path.relpath(os.path.join(dp, f), BASE).replace(os.sep, '/')
            d = fzip.unpack(open(os.path.join(dp, f), 'rb').read())
            for n, b, h in nlib.sarc_read(d)[1]:
                if n.endswith('.bflyt'):
                    bflyt(arc, n, b)
    os.makedirs(os.path.join(ROOT, 'work', 'survey'), exist_ok=True)
    s = json.dumps(rows, ensure_ascii=False, indent=1)
    open(os.path.join(ROOT, 'work', 'survey', 'textboxes.json'), 'w', encoding='utf-8').write(s)
    jp = [r for r in rows if any('぀' <= c <= '鿿' for c in r['text'])]
    print('글 상자', len(rows), '기본 글 있음', sum(1 for r in rows if r['text']),
          '그중 일본어 든 것', len(jp), 'textID 있음', sum(1 for r in rows if r['textid']),
          '같은 bflyt 중복 안 상자', sum(1 for r in rows if r['dup_of']))
    print('폰트별 상자:', collections.Counter(r['font'] for r in rows).most_common())
    for r in jp[:8]:
        print('  ', r['arc'], r['layout'], r['pane'], r['font'], repr(r['text'][:40]), r['textid'])


if __name__ == '__main__':
    main()
