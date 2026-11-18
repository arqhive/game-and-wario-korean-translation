"""게임앤와리오 BFFNT 에 한글 글리프를 넣는다(2단계 출력 시험용: 원본 글리프는 그대로 두고 빈 칸에 추가).

폰트 4종(content/Common/Font):
  Caption50L_JP·Caption64L_JP : BC4 한 채널, 흰 속(255) + 회색 테두리(약 130) 를 한 채널에 함께 담음
  Exp50_JP                     : BC4 한 채널, 테두리 없는 글자
  Serif38_JP                   : BC5, 빨강 = 글자 속, 초록 = 테두리(번짐)
시트: 시트마다 swizzle (i%4)<<9, 상하 반전(font_atlas.py). BC5 는 블록 16바이트라 위치 매핑을 따로 뽑는다.

맞추는 값(원본 한자 글리프에서 잰다, measure()):
  속 높이(속 픽셀 >= 200 의 잉크 높이 중앙값), 속 아랫선, 테두리 두께, 테두리 밝기, CWDH 최빈값.
넣는 방법: 원본 시트·CMAP 은 그대로, 빈 칸(글리프 번호 끝 뒤)에 새 글리프를 넣고 그 시트만 다시 인코딩,
  새 글자는 범위를 덮는 기존 SCAN(0000-FFFF) 목록에 합친다(없을 때만 새 SCAN 블록). 빈 칸이 모자라면 오류(시험에서는 시트를 늘리지 않는다).
"""
import collections
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import addrlib  # noqa: E402
import bffnt_tool as bt  # noqa: E402
import font_atlas as fa  # noqa: E402
import gtx_lib  # noqa: E402

UFONT = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Windows', 'Fonts')
# 시험용 한글 글꼴(최종 글꼴은 5~6단계에서 따로 정한다)
TTF = {
    # 11/17 사용자 결정: Caption 둘 = 넥슨 메이플스토리 Bold, Exp50 = 충주김생체, Serif38 = 둘기마요.
    'Caption50L_JP': (os.path.join(UFONT, 'Maplestory Bold.ttf'), None),
    'Caption64L_JP': (os.path.join(UFONT, 'Maplestory Bold.ttf'), None),
    'Exp50_JP': (os.path.join(UFONT, 'ChungjuKimSaeng.ttf'), None),
    'Serif38_JP': (os.path.join(UFONT, 'dovemayo.otf'), None),   # 11/17 사용자: 둘기마요
}
FILL_T = 200


# ---------------------------------------------------------------- BC5 시트
_M5 = {}


def bc5_map(w, h, swz):
    key = (w, h, swz)
    if key not in _M5:
        n = (w // 4) * (h // 4)
        probe = np.repeat(np.arange(n, dtype='>u8'), 2).tobytes()
        lin = addrlib.deswizzle(w, h, h, 0x35, 4, swz, w // 4, 128, probe)
        _M5[key] = np.frombuffer(lin, '>u8')[::2].astype(np.int64)
    return _M5[key]


def bc5_decode(data, w, h, i):
    m = bc5_map(w, h, fa.sheet_swizzle(i))
    lin = np.frombuffer(data, np.uint8).reshape(-1, 16)[m].reshape(h // 4, w // 4, 16)
    r = gtx_lib.bc4_decode_blocks(np.ascontiguousarray(lin[..., :8]))[::-1].copy()
    g = gtx_lib.bc4_decode_blocks(np.ascontiguousarray(lin[..., 8:]))[::-1].copy()
    return r, g


def bc5_encode(r, g, i):
    h, w = r.shape
    br = gtx_lib.bc4_encode_blocks(np.ascontiguousarray(r[::-1])).reshape(-1, 8)
    bg = gtx_lib.bc4_encode_blocks(np.ascontiguousarray(g[::-1])).reshape(-1, 8)
    lin = np.concatenate([br, bg], axis=1)
    st = np.zeros_like(lin)
    st[bc5_map(w, h, fa.sheet_swizzle(i))] = lin
    return st.tobytes()


def is_bc5(f):
    return f.format == 0x0D


def decode(f):
    """-> 채널별 시트 목록: BC4 = [[시트...]], BC5 = [[R시트...], [G시트...]]"""
    if is_bc5(f):
        rs, gs = zip(*[bc5_decode(s, f.sheet_w, f.sheet_h, i) for i, s in enumerate(f.sheets)])
        return [list(rs), list(gs)]
    return [fa.decode_sheets(f)]


# ---------------------------------------------------------------- 재기
def ink(a, t):
    ys, xs = np.nonzero(a >= t)
    if not len(ys):
        return None
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def measure(f, chans):
    """원본 한자에서 속 높이·아랫선·테두리 두께·테두리 밝기, CWDH 최빈값."""
    hs, bots, rads, ovs, cxs = [], [], [], [], []
    wid = collections.Counter()
    for code, g in sorted(f.charmap.items()):
        if not 0x4E00 <= code <= 0x9FFF:
            continue
        if g in f.widths:
            wid[f.widths[g]] += 1
        main = fa.get_glyph(chans[0], f, g)
        inner = ink(main, FILL_T)
        if not inner:
            continue
        hs.append(inner[3] - inner[1])
        bots.append(inner[3])
        cxs.append((inner[0] + inner[2]) / 2)
        if len(chans) == 2:
            outer = ink(fa.get_glyph(chans[1], f, g), 40)
        else:
            outer = ink(main, 40)
            mid = main[(main >= 60) & (main < FILL_T)]
            if len(mid):
                ovs.append(int(np.median(mid)))
        if outer:
            rads.append(((inner[0] - outer[0]) + (outer[2] - inner[2]) + (inner[1] - outer[1]) + (outer[3] - inner[3])) / 4)
    m = dict(fill_h=float(np.median(hs)), bottom=int(np.median(bots)), radius=float(np.median(rads)) if rads else 0.0,
             outline_v=int(np.median(ovs)) if ovs else 0, width=wid.most_common(1)[0][0], n=len(hs),
             cx=float(np.mean(cxs)))
    m['profile'] = edge_profile(f, chans)
    return m


def edge_profile(f, chans, nmax=12):
    """테두리 채널 값을 '글자 속(>=FILL_T)에서의 거리'별 중앙값으로 잰다. [d=0..nmax] (0 = 속 안)."""
    from scipy.ndimage import distance_transform_edt
    bins = [[] for _ in range(nmax + 1)]
    k = 0
    for code, g in sorted(f.charmap.items()):
        if not 0x4E00 <= code <= 0x9FFF:
            continue
        fill = fa.get_glyph(chans[0], f, g)
        edge = fa.get_glyph(chans[-1], f, g)
        mask = fill >= FILL_T
        if not mask.any():
            continue
        d = distance_transform_edt(~mask)
        di = np.rint(d).astype(int)
        for b in range(1, nmax + 1):
            v = edge[di == b]
            if len(v):
                bins[b].append(np.median(v))
        k += 1
        if k >= 150:
            break
    return [255.0] + [float(np.median(b)) if b else 0.0 for b in bins[1:]]


# ---------------------------------------------------------------- 그리기
def _font(path, var, px):
    ft = ImageFont.truetype(path, px)
    if var:
        try:
            ft.set_variation_by_name(var)
        except Exception:  # noqa: BLE001
            pass
    return ft


def render_fill(ch, path, var, fill_h, cell_w, cell_h, bottom, cx, margin=0):
    """속(0~255)을 셀 크기로. 한글 속 높이가 원본 한자 속 높이와 같도록 글꼴 크기를 맞춘다.
    cx = 원본 한자 속 가로 가운데(칸 좌표), margin = 테두리·빛이 칸 밖으로 안 나가게 둘 여백(되는 만큼)."""
    ref = '한'
    px = int(fill_h * 1.2)
    for _ in range(12):
        ft = _font(path, var, px)
        bb = ft.getbbox(ref)
        h = bb[3] - bb[1]
        if abs(h - fill_h) < 0.6:
            break
        px = max(4, int(round(px * fill_h / max(1, h))))
    ft = _font(path, var, px)
    def draw(c):
        big = Image.new('L', (cell_w * 3, cell_h * 3), 0)
        ImageDraw.Draw(big).text((cell_w, cell_h), c, font=ft, fill=255)
        return np.array(big)
    a = draw(ch)
    bx = ink(a, 1)
    out = np.zeros((cell_h, cell_w), np.uint8)
    if not bx:
        return out
    x0, y0, x1, y1 = bx
    gw, gh = x1 - x0, y1 - y0
    # 테두리·빛 여백을 두고도 칸보다 큰 글자(넓은 갉·높은 ㅊ+ㅇ받침)만 그 글자를 칸에 맞게 줄인다
    s = min(1.0, (cell_w - 2 * margin) / gw, (cell_h - 2 * margin) / gh)
    if s < 1.0:
        a = a.copy()
        sub0 = Image.fromarray(a[y0:y1, x0:x1]).resize((max(1, int(gw * s)), max(1, int(gh * s))), Image.LANCZOS)
        a[y0:y1, x0:x1] = 0
        cyb = y1                                   # 아랫단 기준은 유지하고 줄인 만큼 아래로 붙인다
        nw, nh = sub0.size
        x0n = x0 + (gw - nw) // 2
        y0n = cyb - nh
        a[y0n:y0n + nh, x0n:x0n + nw] = np.array(sub0)
        x0, y0, x1, y1 = x0n, y0n, x0n + nw, y0n + nh
        gw, gh = nw, nh
    # 가로: 원본 한자 속 가운데(cx)에 맞춘다(11/17: 글리프 영역 left~ 기준이면 테두리가 칸 왼쪽 밖으로 잘림).
    # 세로: 글자마다 잉크 아랫단을 맞추면 받침 없는 글자가 아랫선에 붙는다(11/17 실기 Exp50 지적)
    # → 글꼴의 원래 세로 위치는 그대로 두고, 기준 글자 '한'의 아랫단만 원본 한자 아랫선에 맞춘다.
    # 다만 테두리·빛이 칸 밖으로 나가면(ㅊ 위·ㅇ받침 아래) 그 글자만 칸 안으로 민다.
    ox = int(round(cx - gw / 2))
    ref_y1 = ink(draw(ref), 1)[3]
    oy = bottom - (ref_y1 - y0)

    def clamp(o, size, cell):
        lo, hi = margin, cell - margin - size
        if lo > hi:
            return int(round((cell - size) / 2))
        return min(max(o, lo), hi)
    ox, oy = clamp(ox, gw, cell_w), clamp(oy, gh, cell_h)
    sub = a[y0:y1, x0:x1]
    X0, Y0 = max(0, ox), max(0, oy)
    X1, Y1 = min(cell_w, ox + gw), min(cell_h, oy + gh)
    out[Y0:Y1, X0:X1] = sub[Y0 - oy:Y1 - oy, X0 - ox:X1 - ox]
    return out


def grow(fill, r):
    """속을 r 픽셀만큼 둥글게 키운 테두리 모양(0~255)."""
    if r <= 0:
        return fill.copy()
    im = Image.fromarray(fill)
    k = int(np.ceil(r)) * 2 + 1
    big = im.filter(ImageFilter.MaxFilter(k))
    return np.array(big.filter(ImageFilter.GaussianBlur(0.6)))


def edge_from_profile(fill, prof, ss=1):
    """원본에서 잰 거리별 밝기(prof)로 테두리를 만든다: 값 = prof(속에서의 거리), 속과 큰 값을 고른다.
    ss = 크게 그린 배율(거리를 셀 픽셀로 바꿔 prof 를 읽는다)."""
    from scipy.ndimage import distance_transform_edt
    d = distance_transform_edt(fill < 128) / ss
    xs = np.arange(len(prof), dtype=np.float32)
    val = np.interp(d, xs, np.array(prof, np.float32), right=0.0)
    return np.maximum(val, fill.astype(np.float32)).clip(0, 255).astype(np.uint8)


SS = 4            # 4배로 그리고 테두리까지 만든 뒤 줄인다(셀 크기에서 바로 그리면 테두리 가장자리가 계단, 11/17 사용자 지적)
# 폰트별 한글 크기 배율(원본 한자 속 높이 기준 1.0). 11/17 잰 값: 「한」 높이를 한자에 맞추면 한글 속이
# 가나보다 작다(Caption50L 가나 43 / 한글 36, Caption64L 56/47, Serif38 31/30) → 키우고 위아래 가운데로.
SIZE_K = {'Caption50L_JP': 1.12, 'Caption64L_JP': 1.12, 'Serif38_JP': 1.06}


def _down(a, w, h):
    return np.array(Image.fromarray(a).resize((w, h), Image.BOX))


_CMAPS = {}
FALLBACK = (r'C:\Windows\Fonts\malgun.ttf', None)     # 고른 글꼴에 없는 기호(예: 메이플스토리의 ©)만


def _has(path, ch):
    if path not in _CMAPS:
        from fontTools.ttLib import TTFont
        _CMAPS[path] = set(TTFont(path, fontNumber=0).getBestCmap())
    return ord(ch) in _CMAPS[path]


def make_cell(ch, name, f, m, out=None):
    """out=(폭, 높이): 칸을 줄인 폰트용. 원래 칸 기준으로 그린 뒤(SS 배) 바로 줄인 칸 크기로 내린다."""
    ow, oh = out or (f.cell_w, f.cell_h)
    path, var = TTF[name]
    if not _has(path, ch):
        path, var = FALLBACK
    left, gw, _ = m['width']
    k = SIZE_K.get(name, 1.0)
    bottom = m['bottom'] + m['fill_h'] * (k - 1) / 2       # 키운 만큼 위아래로 반씩(한자 속 가운데 유지)
    prof = m['profile']
    reach = next((d for d in range(1, len(prof)) if prof[d] < 8), len(prof))   # 테두리·빛이 닿는 거리
    fill = render_fill(ch, path, var, m['fill_h'] * k * SS, f.cell_w * SS, f.cell_h * SS, int(round(bottom * SS)),
                       m['cx'] * SS, margin=(reach + 1) * SS)
    small = _down(fill, ow, oh)
    if is_bc5(f):
        return [small, _down(edge_from_profile(fill, m['profile'], SS), ow, oh)]
    if m['outline_v'] and m['radius'] > 1.5:   # Exp50 은 안티에일리어싱만으로 0.8 이 나온다(테두리 없음)
        return [_down(edge_from_profile(fill, m['profile'], SS), ow, oh)]
    return [small]


# ---------------------------------------------------------------- 넣기
def add_glyphs(data, name, chars):
    """-> (새 bffnt bytes, 보고 dict)"""
    f = bt.BFFNT(data)
    chans = decode(f)
    m = measure(f, chans)
    new = [c for c in sorted(set(chars)) if ord(c) not in f.charmap]
    start = max(f.charmap.values()) + 1
    if start + len(new) > f.capacity:
        raise ValueError('%s: 빈 칸 %d < 새 글자 %d' % (name, f.capacity - start, len(new)))
    touched = set()
    widths = dict(f.widths)
    cmap = {}
    for k, c in enumerate(new):
        gi = start + k
        cells = make_cell(c, name, f, m)
        for ch_sheets, cell in zip(chans, cells):
            fa.put_glyph(ch_sheets, f, gi, cell)
        touched.add(gi // f.per_sheet)
        widths[gi] = m['width']
        cmap[ord(c)] = gi
    sheets = list(f.sheets)
    for s in touched:
        if is_bc5(f):
            sheets[s] = bc5_encode(chans[0][s], chans[1][s], s)
        else:
            sheets[s] = fa.encode_sheet(chans[0][s], s)
    # 원본은 맨 끝에 0000-FFFF SCAN 목록이 있다. 새 목록을 그 뒤에 붙이면 실기에서 한글이 빈칸(11/17 실기,
    # 범위가 맞는 첫 목록에서 찾기를 끝내는 것으로 추정) → 새 글자는 범위가 덮는 기존 SCAN 목록에 합친다.
    cm = [bt.CMAP(c.code_begin, c.code_end, c.method, c.pad, dict(c.entries)) for c in f.cmaps]
    if cmap:
        host = [c for c in cm if c.method == 2 and c.code_begin <= min(cmap) and max(cmap) <= c.code_end]
        if host:
            host[-1].entries.update(cmap)
        else:
            cm.append(bt.CMAP.scan(cmap))
    out = f.build(sheets=sheets, widths=widths, cmaps=cm)
    return out, dict(name=name, added=len(new), free_before=f.capacity - start, sheets_reencoded=sorted(touched), **m)


def build_korean(data, name, chars, keep_chars):
    """본 빌드(11/18 사용자 결정: 일본어 칸 재사용 + 모자라면 시트 추가).
    keep_chars(번역문에 쓰는 한글 밖 글자)·ASCII·대체 글자 칸은 그대로 두고, 나머지 칸(안 쓰는 가나·한자·빈 칸)을
    chars(한글·‘’“” 등 새 글자)로 덮어쓴다. 모자라면 시트를 덧붙인다. 원래 CMAP 은 그대로 두고 새 글자는 0000-FFFF SCAN 에 합친다.
    -> (bytes, 보고 dict)"""
    import math
    f = bt.BFFNT(data)
    chans = decode(f)
    m = measure(f, chans)
    new = [c for c in sorted(set(chars))]
    keep = {f.alter_index}
    for c in set(keep_chars) | {chr(x) for x in range(0x20, 0x7F)}:
        if ord(c) in f.charmap:
            keep.add(f.charmap[ord(c)])
    free = [g for g in range(f.capacity) if g not in keep]
    add_sheets = 0
    if len(free) < len(new):
        add_sheets = math.ceil((len(new) - len(free)) / f.per_sheet)
        for ch in chans:
            for _ in range(add_sheets):
                ch.append(np.zeros((f.sheet_h, f.sheet_w), np.uint8))
        free += list(range(f.capacity, f.capacity + add_sheets * f.per_sheet))
    widths = dict(f.widths)
    cmap = {}
    touched = set()
    for c, gi in zip(new, free):
        cells = make_cell(c, name, f, m)
        for ch_sheets, cell in zip(chans, cells):
            fa.put_glyph(ch_sheets, f, gi, cell)
        touched.add(gi // f.per_sheet)
        widths[gi] = m['width']
        cmap[ord(c)] = gi
    # 안 쓰는 칸으로 남은 옛 글리프는 지워 둔다(엉뚱한 일본어가 그려지지 않게)
    for gi in [g for g in free[len(new):] if g < f.capacity]:
        for ch_sheets in chans:
            fa.put_glyph(ch_sheets, f, gi, np.zeros((f.cell_h, f.cell_w), np.uint8))
        touched.add(gi // f.per_sheet)
    sheets = list(f.sheets) + [None] * add_sheets
    for s in sorted(touched):
        if is_bc5(f):
            sheets[s] = bc5_encode(chans[0][s], chans[1][s], s)
        else:
            sheets[s] = fa.encode_sheet(chans[0][s], s)
    cm = [bt.CMAP(x.code_begin, x.code_end, x.method, x.pad, dict(x.entries)) for x in f.cmaps]
    host = [x for x in cm if x.method == 2 and x.code_begin <= min(cmap) and max(cmap) <= x.code_end]
    if host:
        host[-1].entries.update(cmap)
    else:
        cm.append(bt.CMAP.scan(cmap))
    out = f.build(sheets=sheets, widths=widths, cmaps=cm)
    return out, dict(name=name, added=len(new), kept=len(keep), reused=min(len(new), f.capacity - len(keep)),
                     add_sheets=add_sheets, sheets=len(sheets))


def fit_cell(f, n_glyphs, sheets):
    """시트 sheets 장에 n_glyphs 칸이 들어가는 가장 큰 칸 크기(가로세로 같은 비율로 줄임). -> (폭, 높이, 열, 행)"""
    for cw in range(f.cell_w, 7, -1):
        s = cw / f.cell_w
        ch = int(f.cell_h * s)
        cols, rows = f.sheet_w // (cw + 1), f.sheet_h // (ch + 1)
        if cols * rows * sheets >= n_glyphs:
            return cw, ch, cols, rows
    raise ValueError('칸이 너무 작아짐')


def build_korean_fit(data, name, chars, keep_chars, sheets):
    """메모리 한계(11/18 실기: 폰트 넷이 늘어난 양 합계 약 1.6~2.1MB 사이에서 멈춤) 때문에 시트 수를 정해 두고,
    모자라면 칸을 같은 비율로 줄인다. 글자 칸 크기·CWDH·FINF(높이·폭·ascent·줄 간격)·기준선을 같은 비율로 줄여
    화면에서는 같은 크기로 늘려 그려지게 한다(레이아웃 글자 크기 / 폰트 높이 비율로 늘린다는 가정 — 실기 확인 필요).
    남길 글자(keep_chars·ASCII·대체 글자)는 원래 글리프 번호 그대로(그림만 줄여 옮김), 나머지 번호에 chars 를 넣는다.
    -> (bytes, 보고 dict)"""
    import copy
    f = bt.BFFNT(data)
    chans = decode(f)
    m = measure(f, chans)
    new = sorted(set(chars))
    keep = {f.alter_index}
    for c in set(keep_chars) | {chr(x) for x in range(0x20, 0x7F)}:
        if ord(c) in f.charmap:
            keep.add(f.charmap[ord(c)])
    cw, ch, cols, rows = fit_cell(f, max(len(keep) + len(new), max(keep) + 1), sheets)
    g = copy.copy(f)
    sx, sy = cw / f.cell_w, ch / f.cell_h
    g.cell_w, g.cell_h, g.columns, g.rows = cw, ch, cols, rows
    if (cw, ch) != (f.cell_w, f.cell_h):
        rx = lambda v: max(0, int(round(v * sx)))
        ry = lambda v: max(0, int(round(v * sy)))
        g.max_char_w = rx(f.max_char_w)
        g.baseline = ry(f.baseline)
        g.height, g.width, g.ascent, g.line_feed = ry(f.height), rx(f.width), ry(f.ascent), ry(f.line_feed)
        g.def_left, g.def_glyph_w, g.def_char_w = int(round(f.def_left * sx)), rx(f.def_glyph_w), rx(f.def_char_w)
    assert max(keep) < g.per_sheet * sheets
    out = [[np.zeros((f.sheet_h, f.sheet_w), np.uint8) for _ in range(sheets)] for _ in chans]
    widths = {}
    for gi in keep:
        for o_sheets, n_sheets in zip(chans, out):
            cell = fa.get_glyph(o_sheets, f, gi)
            if (cw, ch) != (f.cell_w, f.cell_h):
                cell = np.array(Image.fromarray(cell).resize((cw, ch), Image.LANCZOS))
            fa.put_glyph(n_sheets, g, gi, cell)
        l, gw_, cw_ = f.widths.get(gi, (f.def_left, f.def_glyph_w, f.def_char_w))
        widths[gi] = (int(round(l * sx)), min(cw, int(round(gw_ * sx))), int(round(cw_ * sx)))
    free = [x for x in range(g.per_sheet * sheets) if x not in keep]
    assert len(free) >= len(new), (len(free), len(new))
    wl, wg, wc = m['width']
    kw = (int(round(wl * sx)), min(cw, int(round(wg * sx))), int(round(wc * sx)))
    cmap = {}
    widened = 0
    # 반각 글자 기준: 새로 그린 한글 「한」의 왼쪽 잉크 위치와 간격(글자 폭 - 잉크 폭)을 따라 좁은 폭으로 넣는다(11/19).
    # (원본 '.' 을 기준으로 했더니 Serif38 의 '.' 이 전각처럼 넓어 부호 앞뒤가 벌어졌다.)
    rb = [b for b in (ink(x, 8) for x in make_cell('한', name, f, m, out=(cw, ch))) if b]
    dot_ref = (kw, (min(b[0] for b in rb), 0, max(b[2] for b in rb), 0)) if rb else None
    for c, gi in zip(new, free):
        cells = make_cell(c, name, f, m, out=(cw, ch))
        if ord(c) <= 0x7F and dot_ref:
            (dl, dg, dc), db = dot_ref
            bs = [b for b in (ink(x, 8) for x in cells) if b]
            x0, x1 = min(b[0] for b in bs), max(b[2] for b in bs)
            dx = db[0] - x0
            moved = []
            for x in cells:
                y = np.zeros_like(x)
                if dx >= 0:
                    y[:, dx:] = x[:, :x.shape[1] - dx]
                else:
                    y[:, :dx] = x[:, -dx:]
                moved.append(y)
            for n_sheets, cell in zip(out, moved):
                fa.put_glyph(n_sheets, g, gi, cell)
            gap = dc - (db[2] - db[0])
            widths[gi] = (dl, min(cw, x1 + dx), max(1, (x1 - x0) + gap))
            cmap[ord(c)] = gi
            continue
        for n_sheets, cell in zip(out, cells):
            fa.put_glyph(n_sheets, g, gi, cell)
        # 게임은 칸에서 glyph_w 까지만 그린다. 한자보다 넓은 한글(ㅏ 획 등)은 테두리가 그 밖으로 나가 잘렸다
        # (11/19 사용자 지적 「아·까」). 잉크가 넘는 글자만 glyph_w 를 잉크 오른쪽 끝까지(칸 폭 안) 늘린다.
        # 글자 그림·왼쪽(left)·글자 간격(char_w)은 그대로.
        right = max((b[2] for b in (ink(x, 8) for x in cells) if b), default=0)
        widths[gi] = (kw[0], min(cw, max(kw[1], right)), kw[2])
        widened += widths[gi][1] != kw[1]
        cmap[ord(c)] = gi
    # SCAN 에서는 안 남긴 일본어 글자를 빼고(번호가 한글 칸을 가리키지 않게), 새 글자는 0000-FFFF SCAN 에 합친다.
    # DIRECT/TABLE 은 모양을 못 바꾸니 그대로 둔다(안 남긴 번호는 한글이나 빈 칸을 가리키지만 번역문에 안 쓰는 글자).
    cm = []
    for x in f.cmaps:
        ent = {k: v for k, v in x.entries.items() if v in keep}
        if x.method == 2:
            cm.append(bt.CMAP(x.code_begin, x.code_end, 2, x.pad, ent))
        else:
            cm.append(bt.CMAP(x.code_begin, x.code_end, x.method, x.pad, dict(x.entries)))
    host = [x for x in cm if x.method == 2 and x.code_begin <= min(cmap) and max(cmap) <= x.code_end]
    if host:
        host[-1].entries.update(cmap)
    else:
        cm.append(bt.CMAP.scan(cmap))
    if is_bc5(f):
        enc = [bc5_encode(out[0][s], out[1][s], s) for s in range(sheets)]
    else:
        enc = [fa.encode_sheet(out[0][s], s) for s in range(sheets)]
    data2 = g.build(sheets=enc, widths=widths, cmaps=cm)
    return data2, dict(name=name, added=len(new), kept=len(keep), sheets=sheets, cell=(f.cell_w, f.cell_h, cw, ch),
                       scale=round(sx, 3), per_sheet=g.per_sheet, spare=len(free) - len(new), widened=widened)


def verify_fit(old_data, new_data, chars, keep_chars):
    """칸을 줄인 폰트 검사: 남긴 글자는 원래 번호 그대로이고 줄인 그림과 비슷한지, 새 글자는 비지 않았는지,
    모든 CMAP 번호가 칸 안에 있는지."""
    o, n = bt.BFFNT(old_data), bt.BFFNT(new_data)
    oc, nc = decode(o), decode(n)
    bad = []
    for c in set(keep_chars) | {chr(x) for x in range(0x21, 0x7F)}:
        if ord(c) in o.charmap:
            g = o.charmap[ord(c)]
            if n.charmap.get(ord(c)) != g:
                bad.append(c)
                continue
            for a, b in zip(oc, nc):
                ref = np.array(Image.fromarray(fa.get_glyph(a, o, g)).resize((n.cell_w, n.cell_h), Image.LANCZOS)).astype(int)
                if np.abs(ref - fa.get_glyph(b, n, g).astype(int)).max() > 24:
                    bad.append(c)
                    break
    blank = [c for c in set(chars) if ord(c) not in n.charmap or fa.get_glyph(nc[0], n, n.charmap[ord(c)]).max() == 0]
    out_of_range = [k for k, v in n.charmap.items() if v >= n.capacity]
    return bad, blank, out_of_range


def verify_korean(old_data, new_data, chars, keep_chars):
    """남긴 글자는 모양 그대로, 새 글자는 비지 않고 지정 칸에 있는지."""
    o, n = bt.BFFNT(old_data), bt.BFFNT(new_data)
    oc, nc = decode(o), decode(n)
    bad = []
    for c in set(keep_chars) | {chr(x) for x in range(0x21, 0x7F)}:
        if ord(c) in o.charmap:
            g = o.charmap[ord(c)]
            if n.charmap.get(ord(c)) != g or any(
                    np.abs(fa.get_glyph(a, o, g).astype(int) - fa.get_glyph(b, n, g).astype(int)).max() > 24 for a, b in zip(oc, nc)):
                bad.append(c)
    blank = [c for c in set(chars) if ord(c) not in n.charmap or fa.get_glyph(nc[0], n, n.charmap[ord(c)]).max() == 0]
    return bad, blank


def verify(old_data, new_data, chars):
    """원본 글자는 다시 인코딩된 시트에서도 모양이 그대로인지(BC 손실 허용 24), 새 글자는 비지 않았는지."""
    o, n = bt.BFFNT(old_data), bt.BFFNT(new_data)
    oc, nc = decode(o), decode(n)
    bad = 0
    for code, g in o.charmap.items():
        if n.charmap.get(code) != g:
            bad += 1
            continue
        for a, b in zip(oc, nc):
            if np.abs(fa.get_glyph(a, o, g).astype(int) - fa.get_glyph(b, n, g).astype(int)).max() > 24:
                bad += 1
                break
    blank = [c for c in set(chars) if ord(c) not in n.charmap or fa.get_glyph(nc[0], n, n.charmap[ord(c)]).max() == 0]
    return bad, blank, len(o.charmap), len(n.charmap)
