"""3단계 창 측정: 대사(MSBT 칸)마다 들어가는 글 상자(bflyt txt1)의 폭·줄 수 한도와 원문 폭을 잰다.

폭 계산(nw4f 글 상자, 추정 모델 — 원문 넘침 수로 검증):
  글자 전진 = CWDH char_w × (글자크기 가로 / FINF width) [× {0:2:XXXX} 크기 % / 100] + 글자 간격(cspace)
  줄 높이 = FINF line_feed × (글자크기 세로 / FINF height) + 줄 간격(lspace), 줄 수 한도 = (상자 높이 + lspace) // 줄 높이
  후리가나 {0:0:LLLLRRRR..} 는 폭에 안 넣음(위에 붙음), 색 {0:3:} 등 다른 태그도 폭 0, 변수 {2:..} 는 「변수」 표시만.
  한글은 gw_font 로 넣는 글리프 폭(원본 한자 최빈 폭) = 그 폰트 한자 폭.
  CafeStd(본체 폰트, TTF)는 사용자 본체 CafeStd.ttf(바탕화면 사본)를 글자크기 세로 px 로 그려 잰다(추정, 실기 확인 안 함).
출력: work/survey/window_limits.json (칸마다), docs/window_sizes.md (요약)
사용: python -I tools/window_limits.py
"""
import collections
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bffnt_tool as bt  # noqa: E402
import fzip  # noqa: E402

ROOT = os.path.dirname(HERE)
FONT_DIR = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]', 'content', 'Common', 'Font')
CAFE_TTF = os.path.join(os.path.expanduser('~'), 'Desktop', 'CafeStd.ttf')
TAG = re.compile(r'\{(/?)(\d+):(\d+):([0-9a-fA-F]*)\}')


class BMFont:
    def __init__(self, name):
        p = os.path.join(FONT_DIR, name + '_JP.bffnt.fzip')
        if not os.path.exists(p):
            p = os.path.join(FONT_DIR, name + '.bffnt.fzip')      # 숫자 폰트
        f = bt.BFFNT(fzip.unpack(open(p, 'rb').read()))
        self.f = f
        kan = collections.Counter(f.widths[g][2] for c, g in f.charmap.items() if 0x4E00 <= c <= 0x9FFF and g in f.widths)
        self.han_w = kan.most_common(1)[0][0] if kan else f.def_char_w   # 한글 글리프 폭(gw_font 가 넣는 값과 같음)

    def adv(self, c):
        o = ord(c)
        if 0xAC00 <= o <= 0xD7A3:
            return self.han_w
        g = self.f.charmap.get(o, self.f.alter_index)
        return self.f.widths.get(g, (0, 0, self.f.def_char_w))[2]

    def sx(self, fsize):
        return fsize[0] / self.f.width

    def line_h(self, fsize, lspace):
        return self.f.line_feed * fsize[1] / self.f.height + lspace


class TTFont:
    def __init__(self, path):
        from PIL import ImageFont
        self.path, self.cache, self.ImageFont = path, {}, ImageFont
        self.ft = ImageFont.truetype(path, 100)
        a, d = self.ft.getmetrics()
        self.hpx = a + d            # 글꼴 높이(ascent+descent) — 글자크기 세로를 이 높이로 본다(추정)

    def adv(self, c):
        if c not in self.cache:
            self.cache[c] = self.ft.getlength(c)
        return self.cache[c]

    def sx(self, fsize):
        return fsize[1] / self.hpx

    def line_h(self, fsize, lspace):
        return fsize[1] * 1.0 + lspace


FONTS = {}
REF = 'Caption50L'
LIST_FILES = ['Dr_theme.msbt', 'Dr2_theme.msbt', 'Pon_name.msbt', 'Pon_voice.msbt']


def ref_fsize(name):
    """상대 칸을 잴 때 쓰는 글자 크기(원문·번역을 같은 크기로 재기만 하면 된다)."""
    f = font(name)
    return [f.f.width, f.f.height] if isinstance(f, BMFont) else [50.0, 50.0]


def font(name):
    if name not in FONTS:
        FONTS[name] = TTFont(CAFE_TTF) if name == 'CafeStd' else BMFont(name)
    return FONTS[name]


def lines_px(text, fnt, fsize, cspace):
    """-> [(줄 폭 px, 변수 있음)]"""
    out = []
    for raw in text.split('\n'):
        w, n, var, scale = 0.0, 0, False, 1.0
        pos = 0
        for m in TAG.finditer(raw + '{0:9:}'):
            for c in raw[pos:m.start()]:
                w += fnt.adv(c) * fnt.sx(fsize) * scale
                n += 1
            pos = m.end()
            if m.group(2) == '0' and m.group(3) == '2' and m.group(4):
                scale = int(m.group(4), 16) / 100.0
            if m.group(2) == '2':
                var = True
        if n > 1:
            w += cspace * (n - 1)
        out.append((round(w, 1), var))
    return out


def main():
    tb = json.load(open(os.path.join(ROOT, 'work', 'survey', 'textboxes.json'), encoding='utf-8'))
    tmap = json.load(open(os.path.join(ROOT, 'work', 'survey', 'textid_map.json'), encoding='utf-8'))['hit']
    jp = json.load(open(os.path.join(ROOT, 'work', 'extract', 'msbt_JP_Japanese.json'), encoding='utf-8'))
    text = {(e['file'], e['label']): e['text'] for e in jp}
    # 같은 라벨(PlyTv_02 등)이 여러 msbt 에 있다 → 레이아웃 이름 앞머리(Ar_·Re_·Co_)와 같은 msbt 만 연결
    boxes = collections.defaultdict(list)
    amb = collections.Counter()
    for e in tb:
        cands = tmap.get(e['textid'], [])
        pre = os.path.basename(e['layout']).split('_')[0]
        pick = [fn for fn in cands if fn[:-5] == pre]
        if not pick and len(cands) == 1:
            pick = cands
        if not pick and 'Co.msbt' in cands:
            pick = ['Co.msbt']
        if not pick:
            amb[(pre, tuple(cands))] += 1
            continue
        boxes[(pick[0], e['textid'])].append(e)
    print('msbt 못 정한 상자', sum(amb.values()), amb.most_common(8))
    res, over, kinds = {}, [], collections.Counter()
    for key, bl in sorted(boxes.items()):
        t = text.get(key)
        if t is None:
            continue
        ent = []
        for b in bl:
            fname = b['font'].replace('.bffnt', '')
            fnt = font(fname)
            lh = fnt.line_h(b['fsize'], b['lspace'])
            maxl = max(1, int((b['size'][1] + b['lspace']) // lh)) if lh > 0 else 1
            ls = lines_px(t, fnt, b['fsize'], b['cspace'])
            ent.append(dict(layout=b['arc'].split('/')[0] + '/' + os.path.basename(b['layout']), pane=b['pane'], font=fname,
                            w=b['size'][0], h=b['size'][1], max_lines=maxl, fsize=b['fsize'], jp_lines=[x[0] for x in ls],
                            var=any(x[1] for x in ls), align=b['align'], cspace=b['cspace'], lspace=b['lspace']))
            kinds[fname] += 1
            wmax = max(x[0] for x in ls)
            ent[-1]['fit'] = '{1:0:}' in t     # {1:0:}…{/1:0} = 폭 맞춤 구간으로 추정(원문 넘침 줄에만 붙음)
            if (wmax > b['size'][0] + 0.5 and not ent[-1]['fit']) or len(ls) > maxl:
                over.append((key, ent[-1], wmax, len(ls)))
        # 한도는 그 칸이 들어가는 상자 중 가장 좁은 것
        res['%s|%s' % key] = dict(kind='box', text=t, boxes=ent, limit_w=min(x['w'] for x in ent), limit_lines=min(x['max_lines'] for x in ent))
    # 상자를 못 찾은 칸(코드가 넣는 칸으로 추정): 원문·북미판 중 긴 쪽 폭·줄 수를 한도로(기준 폰트 Caption50L, 글자크기 = 칸 크기)
    en = {(e['file'], e['label']): e['text'] for e in json.load(open(os.path.join(ROOT, 'work', 'extract', 'msbt_US_English.json'), encoding='utf-8'))}
    for key, t in text.items():
        k = '%s|%s' % key
        if k in res or not t.strip():
            continue
        # 원문 글자가 기준 폰트(Caption50L)에 없으면(주제 단어 목록 등) 폭이 작게 재져 한도가 틀린다
        # → 그런 칸은 본체 폰트 CafeStd(TTF)로 잰다(11/18).
        plain = re.sub(r'\{[^}]*\}', '', t)
        rname = REF if all(ord(c) in font(REF).f.charmap for c in plain if c not in '\n') else 'CafeStd'
        ref = font(rname)
        rfs = ref_fsize(rname)
        lj = lines_px(t, ref, rfs, 0)
        le = lines_px(en.get(key, ''), ref, rfs, 0) if en.get(key, '').strip() else []
        res[k] = dict(kind='rel', text=t, en=en.get(key, ''), ref_font=rname,
                      limit_w=max([x[0] for x in lj + le]), limit_lines=max(len(lj), len(le)),
                      jp_w=max(x[0] for x in lj), en_w=max([x[0] for x in le]) if le else None)
    # 같은 화면 칸 하나에 번갈아 나오는 낱말 목록 파일(스케치 주제)은 칸마다 원문 길이로 재면 한 글자 낱말 한도가
    # 너무 좁다 → 그 파일 상대 칸 전체의 최대 폭·줄 수를 한도로(11/18, 같은 칸에 나오는 것으로 추정).
    for lf in LIST_FILES:
        ks = [k for k, v in res.items() if v['kind'] == 'rel' and k.startswith(lf + '|')]
        if ks:
            mw = max(res[k]['limit_w'] for k in ks)
            ml = max(res[k]['limit_lines'] for k in ks)
            for k in ks:
                res[k]['limit_w'], res[k]['limit_lines'], res[k]['list_max'] = mw, ml, True
    json.dump(res, open(os.path.join(ROOT, 'work', 'survey', 'window_limits.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    nobox = [k for k in text if text[k].strip() and k not in boxes]
    print('대사 칸(빈 칸 빼고)', sum(1 for v in text.values() if v.strip()), '상자 연결됨', len(res), '상자 없음(코드에서 넣거나 안 씀)', len(nobox))
    print('상자 연결 수(폰트별)', dict(kinds))
    print('원문이 넘치는 상자', len(over))
    oc = collections.Counter(o[1]['font'] for o in over)
    print('  폰트별', dict(oc))
    for key, b, w, n in over[:25]:
        print('  %s|%s %s %s 폭 %.0f/%d 줄 %d/%d %s' % (key[0], key[1], b['layout'], b['font'], w, b['w'], n, b['max_lines'], text[key][:40].replace('\n', '/')))
    return res, over, nobox


if __name__ == '__main__':
    main()
