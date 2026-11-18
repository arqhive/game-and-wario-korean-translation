"""그림 글씨 넣기(사용자 11/18 「그림 작업 다 했어」).

입력
  work/gpt_graphics/list.json      그림 목록(id, game_path, file)
  work/gpt_graphics/ko/<같은 이름>.png  한글 그림(원본 jp/ 와 같은 크기, texdec 로 푼 같은 색 공간)
  work/na_gfx/manifest.json        북미판 그림으로 통째 교체할 칸(tools/gw_na_gfx.py)
방식
  - 바뀐 4x4 블록만 다시 압축한다(나머지 블록 바이트는 원본 그대로). 비교는 원본 jp png 와 ko png 로 한다.
  - 형식: RGBA8(0x1a), BC1(0x31·0x431), BC3(0x33·0x433), BC5(0x35), BC5 부호 있음(0x235, 노멀맵).
  - 3D 모델(bfres) 그림은 밉맵도 다시 만든다: 원본·한글 0레벨을 같은 방법(BOX)으로 줄여 다른 블록만 바꾼다.
    밉 배치: 레벨1 은 밉 데이터 처음, 레벨 L(2~) 은 mipOffsets[L-1], 레벨별 tileMode·pitch 는 addrlib.getSurfaceInfo
    (원본 밉을 풀어 0레벨 축소본과 맞는지 확인함, 11/18).
  - 담는 곳: bflim·gtx 가 든 SARC 는 같은 크기 교체, WARC 는 warc.write, 단독 gtx·bfres 는 바이트 자리 교체. 모두 fzip 다시 압축.
사용: import gw_gfx; files, report = gw_gfx.build()   (gw_build 가 부른다)
      python -I tools/gw_gfx.py  → 검사만(결과 그림 풀어 ko 와 비교)
"""
import json
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import addrlib  # noqa: E402
import bc1  # noqa: E402
import fzip  # noqa: E402
import gtx2  # noqa: E402
import gtx_lib  # noqa: E402
import nlib  # noqa: E402
import texdec  # noqa: E402
import warc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]')
GG = os.path.join(ROOT, 'work', 'gpt_graphics')
NA_DIR = os.path.join(ROOT, 'work', 'na_gfx')
BCN = {0x31, 0x32, 0x33, 0x34, 0x35}


# ------------------------------------------------------------------ 블록 압축
def _bc4_pal(r0, r1, signed):
    r0 = r0.astype(np.float64); r1 = r1.astype(np.float64)
    hi = r0 > r1
    pal = np.zeros(r0.shape + (8,))
    pal[..., 0] = r0; pal[..., 1] = r1
    for i in range(1, 7):
        pal[..., 1 + i] = np.where(hi, ((7 - i) * r0 + i * r1) / 7, pal[..., 1 + i])
    for i in range(1, 5):
        pal[..., 1 + i] = np.where(hi, pal[..., 1 + i], ((5 - i) * r0 + i * r1) / 5)
    lo_v, hi_v = (-127, 127) if signed else (0, 255)
    pal[..., 6] = np.where(hi, pal[..., 6], lo_v)
    pal[..., 7] = np.where(hi, pal[..., 7], hi_v)
    return pal


def bc4_enc(px, signed=False):
    """px: (n,16) 값(부호 없음 0~255 / 부호 있음 -127~127) → (n,8) 블록"""
    px = px.astype(np.int32)
    hi = px.max(1); lo = px.min(1)
    eq = hi == lo
    lim_lo = -127 if signed else 0
    r0 = np.where(eq & (hi > lim_lo), hi, hi)
    r1 = np.where(eq & (hi > lim_lo), hi - 1, lo)
    r0 = np.where(eq & (hi <= lim_lo), hi + 1, r0)
    pal = _bc4_pal(r0, r1, signed)
    idx = np.abs(px[:, :, None] - pal[:, None, :]).argmin(-1).astype(np.int64)
    bits = np.zeros(len(px), np.int64)
    for k in range(16):
        bits |= idx[:, k] << (3 * k)
    out = np.zeros((len(px), 8), np.uint8)
    out[:, 0] = r0.astype(np.int64) & 255; out[:, 1] = r1.astype(np.int64) & 255
    for i in range(6):
        out[:, 2 + i] = (bits >> (8 * i)) & 255
    return out


def bc4_dec(blk, signed=False):
    """(n,8) → (n,16) 값"""
    b = blk.astype(np.int64)
    r0, r1 = b[:, 0], b[:, 1]
    if signed:
        r0 = np.where(r0 > 127, r0 - 256, r0); r1 = np.where(r1 > 127, r1 - 256, r1)
        r0 = np.maximum(r0, -127); r1 = np.maximum(r1, -127)
    pal = _bc4_pal(r0, r1, signed)
    bits = np.zeros(len(b), np.int64)
    for i in range(6):
        bits |= b[:, 2 + i] << (8 * i)
    idx = np.stack([(bits >> (3 * k)) & 7 for k in range(16)], 1)
    return np.round(np.take_along_axis(pal, idx, 1)).astype(np.int64)


def to_signed(u8):
    v = u8.astype(np.int64)
    return np.where(v > 127, v - 256, v)


def encode_blocks(px, fmt):
    """px: (n,16,4) uint8 RGBA(그림 공간) → (n, bpe) 블록. fmt 는 전체 형식 값."""
    f6 = fmt & 0x3F
    if f6 == 0x31:
        return bc1.encode_blocks(px[:, :, :3].astype(np.float64))
    if f6 == 0x33:
        a = bc4_enc(px[:, :, 3])
        c = bc1.encode_blocks(px[:, :, :3].astype(np.float64))
        return np.concatenate([a, c], 1)
    if f6 == 0x35:
        signed = bool(fmt & 0x200)
        ch = (lambda k: to_signed(px[:, :, k])) if signed else (lambda k: px[:, :, k])
        return np.concatenate([bc4_enc(ch(0), signed), bc4_enc(ch(1), signed)], 1)
    raise NotImplementedError(hex(fmt))


def decode_blocks(blk, fmt):
    """(n,bpe) → (n,16,4) 그림 공간(부호 있는 BC5 는 바이트로 되돌림, 실제 하드웨어 값과 같은 비트)"""
    f6 = fmt & 0x3F
    n = len(blk)
    one = lambda b: np.ascontiguousarray(b).reshape(n, 1, -1)
    if f6 == 0x31:
        rgb = gtx_lib.bc1_decode_blocks(one(blk)).reshape(n, 16, 3)
        return np.dstack([rgb, np.full((n, 16), 255)]).astype(np.int64)
    if f6 == 0x33:
        a = bc4_dec(blk[:, 0:8])
        rgb = gtx_lib.bc1_decode_blocks(one(blk[:, 8:16])).reshape(n, 16, 3)
        return np.dstack([rgb, a]).astype(np.int64)
    if f6 == 0x35:
        signed = bool(fmt & 0x200)
        r = bc4_dec(blk[:, 0:8], signed) & 255; g = bc4_dec(blk[:, 8:16], signed) & 255
        return np.dstack([r, g, np.zeros_like(r), np.full_like(r, 255)])
    raise NotImplementedError(hex(fmt))


# ------------------------------------------------------------------ 주소
def offsets(w, h, fmt, tm, pitch, height, swz):
    """요소(블록 또는 픽셀) 좌표 (bh,bw) → 바이트 위치"""
    bpp = addrlib.surfaceGetBitsPerPixel(fmt)
    bw, bh = ((w + 3) // 4, (h + 3) // 4) if (fmt & 0x3F) in BCN else (w, h)
    if tm == 4:
        return gtx2.addr_map(bw, bh, bpp, pitch, height, swz), bpp // 8
    m = np.zeros((bh, bw), np.int64)
    for y in range(bh):
        for x in range(bw):
            if tm in (0, 1):
                m[y, x] = (y * pitch + x) * bpp // 8
            elif tm in (2, 3):
                m[y, x] = addrlib.computeSurfaceAddrFromCoordMicroTiled(x, y, bpp, pitch, tm)
            else:
                raise NotImplementedError('tileMode %d' % tm)
    return m, bpp // 8


def to_blocks(img):
    """(H,W,4) → (bh,bw,16,4), 가장자리 복제로 4의 배수 맞춤"""
    H, W = img.shape[:2]
    bh, bw = (H + 3) // 4, (W + 3) // 4
    p = np.pad(img, ((0, bh * 4 - H), (0, bw * 4 - W), (0, 0)), mode='edge')
    return p.reshape(bh, 4, bw, 4, 4).transpose(0, 2, 1, 3, 4).reshape(bh, bw, 16, 4)


def patch_level(buf, old_img, new_img, fmt, tm, pitch, height, swz):
    """buf(bytearray, 레벨 자리) 안에서 old/new 가 다른 블록만 다시 압축해 넣는다. 바꾼 블록 수를 돌려준다."""
    h, w = new_img.shape[:2]
    m, bpe = offsets(w, h, fmt, tm, pitch, height, swz)
    f6 = fmt & 0x3F
    if f6 == 0x1A:
        ch = np.any(old_img != new_img, -1)
        ys, xs = np.nonzero(ch)
        for k in range(4):
            idx = m[ys, xs] + k
            ok = idx < len(buf)
            np.asarray(buf)[idx[ok]] = new_img[ys, xs, k][ok]
        return int(ch.sum())
    a, b = to_blocks(old_img), to_blocks(new_img)
    ch = np.any(a != b, axis=(2, 3))
    ys, xs = np.nonzero(ch)
    if len(ys):
        enc = encode_blocks(b[ys, xs], fmt)
        arr = np.frombuffer(buf, np.uint8) if isinstance(buf, bytes) else np.asarray(buf)
        for k in range(bpe):
            arr[m[ys, xs] + k] = enc[:, k]
    return int(ch.sum())


def shrink(img, w, h, fmt):
    """밉 축소(BOX). 부호 있는 BC5 는 부호 값으로 평균."""
    signed = (fmt & 0x3F) == 0x35 and bool(fmt & 0x200)
    chans = []
    for k in range(4):
        c = img[..., k]
        c = to_signed(c).astype(np.float32) if signed and k < 2 else c.astype(np.float32)
        r = np.array(Image.fromarray(c, 'F').resize((w, h), Image.BOX))
        r = np.round(r).astype(np.int64)
        chans.append(r & 255 if signed and k < 2 else np.clip(r, 0, 255))
    return np.stack(chans, -1).astype(np.uint8)


def level_surface(s, L):
    si = addrlib.getSurfaceInfo(s['format'], s['width'], s['height'], s.get('depth', 1), s.get('dim', 1), s['tileMode'],
                                s.get('aa', 0), L)
    return si.tileMode, si.pitch, si.height, si.surfSize


# ------------------------------------------------------------------ 한 그림
def patch_surface(raw, s, old_img, new_img):
    """0레벨 raw(bytes) 를 고친 bytes 와 바꾼 블록 수"""
    buf = bytearray(raw)
    tm, pitch, height, _ = level_surface(s, 0)
    n = patch_level(np.frombuffer(buf, np.uint8), old_img, new_img, s['format'], tm, pitch, height, s['swizzle'])
    return bytes(buf), n


def patch_mips(mip, s, mipoffs, old0, new0):
    buf = bytearray(mip)
    arr = np.frombuffer(buf, np.uint8)
    total = 0
    for L in range(1, s['numMips']):
        w, h = max(1, s['width'] >> L), max(1, s['height'] >> L)
        tm, pitch, height, size = level_surface(s, L)
        off = 0 if L == 1 else mipoffs[L - 1]
        o, n_ = shrink(old0, w, h, s['format']), shrink(new0, w, h, s['format'])
        total += patch_level(arr[off:off + size], o, n_, s['format'], tm, pitch, height, s['swizzle'])
    return bytes(buf), total


def load_png(p):
    return np.array(Image.open(p).convert('RGBA'))


# ------------------------------------------------------------------ 담는 곳
def read_top(gp_file):
    return open(os.path.join(GAME, *gp_file.split('/')), 'rb').read()


def ko_targets():
    """한글 그림을 넣을 자리 전부: 목록 칸 + 조사 때 같은 바이트라 목록에서 뺀 사본 자리(dup_of).
    (11/18 실기: 「혼자서」 LogoSingl_NRM·_SPC 가 LogoGames_NRM·_SPC 의 사본이라 일본어가 비쳐 보였다)
    돌려주는 칸: list.json 행에 'ftex'(bfres 그림 이름), 'dup_of'(사본이면 원래 id) 를 더한 것."""
    rows = json.load(open(os.path.join(GG, 'list.json'), encoding='utf-8'))
    ko = {int(f[:5]): f for f in os.listdir(os.path.join(GG, 'ko')) if f.endswith('.png')}
    idx = [json.loads(l) for l in open(os.path.join(ROOT, 'work', 'survey', 'tex', 'index.jsonl'), encoding='utf-8')]
    dups = {}
    for e in idx:
        if 'dup_of' in e:
            dups.setdefault(e['dup_of'], []).append(e)
    out = []
    for r in rows:
        if r['id'] not in ko:
            continue
        r = dict(r, ko_file=ko[r['id']])
        if not '//' in r['game_path'] and r['game_path'].endswith('.bfres.fzip'):
            r['ftex'] = os.path.basename(r['file'])[6:-4]
        out.append(r)
        for e in dups.get(r['id'], []):
            d = dict(r, game_path=e['path'], dup_of=r['id'])
            if e['kind'] == 'ftex':
                d['ftex'] = e['name']
            out.append(d)
    return out


def build(verbose=True):
    ko_dir = os.path.join(GG, 'ko')
    na = json.load(open(os.path.join(NA_DIR, 'manifest.json'), encoding='utf-8'))
    # 파일별로 모으기: top -> [(kind, member, payload)]
    jobs = {}
    for r in ko_targets():
        top, _, member = r['game_path'].partition('//')
        jobs.setdefault(top, []).append(('ko', member, r, os.path.join(ko_dir, r['ko_file'])))
    for e in na:
        top, _, member = e['game_path'].partition('//')
        jobs.setdefault(top, []).append(('na', member, e, os.path.join(NA_DIR, e['file'])))
    files, report = {}, []
    for top, js in sorted(jobs.items()):
        orig = read_top(top)
        data = fzip.unpack(orig) if orig[:4] == b'FZIP' else orig
        members = {}
        for kind, member, r, src in js:
            if kind == 'na':
                assert member, top
                members[member] = open(src, 'rb').read()
                report.append(dict(id=r['id'], kind='na', path=top + '//' + member, blocks=None))
                continue
            old = load_png(os.path.join(GG, r['file'].replace('/', os.sep)))
            new = load_png(src)
            assert old.shape == new.shape, (r['id'], old.shape, new.shape)
            if member:                                    # SARC 안 bflim·gtx
                sarc = {n: b for n, b, h in nlib.sarc_read(data)[1]}
                blob = members.get(member, sarc[member])
                blob, n, mips = patch_blob(blob, old, new)
                members[member] = blob
            elif data[:4] == b'Gfx2':                     # 단독 gtx
                data, n, mips = patch_blob(data, old, new)
            elif data[:4] == b'FRES':                     # bfres 안 FTEX
                data, n, mips = patch_ftex(data, r['ftex'], old, new)
            else:
                raise NotImplementedError(top)
            report.append(dict(id=r['id'], kind='ko', path=r['game_path'], ftex=r.get('ftex'), dup_of=r.get('dup_of'),
                               blocks=n, mip_blocks=mips))
        if members:
            if data[:4] == b'SARC':
                data = nlib.sarc_patch_same_size(data, members)
            elif data[:4] == b'WARC':
                ents = {e['name']: e for e in warc.read(data)}
                if all(len(b) == ents[n]['size'] for n, b in members.items()):
                    buf = bytearray(data)               # 크기가 같으면 제자리 덮어쓰기(묶음 크기·배치 그대로)
                    for n, b in members.items():
                        buf[ents[n]['start']:ents[n]['start'] + len(b)] = b
                    data = bytes(buf)
                else:
                    data = warc.write(data, members)
            else:
                raise NotImplementedError(top)
        out = fzip.pack(data) if orig[:4] == b'FZIP' else data
        files[top[len('content/'):]] = out
        if verbose:
            print('파일', top, '바꾼 칸', len(js))
    return files, report


def patch_blob(blob, old, new):
    """bflim 또는 gtx 바이트를 고친다 → (새 바이트, 바꾼 블록 수, 밉 블록 수)"""
    if blob[:4] == b'Gfx2':
        g = gtx_lib.gtx_parse(blob); s = g['surf']; ib = g['img_blk']
        assert s['numMips'] <= 1, ('gtx 밉맵', s['numMips'])
        raw = blob[ib['data']:ib['data'] + ib['size']]
        nraw, n = patch_surface(raw, s, old, new)
        return blob[:ib['data']] + nraw + blob[ib['data'] + ib['size']:], n, 0
    f = texdec.flim_info(blob)
    s = dict(width=f['width'], height=f['height'], format=f['format'], tileMode=f['tileMode'], swizzle=f['swizzle'],
             numMips=1, depth=1, dim=1, aa=0)
    nraw, n = patch_surface(f['data'], s, old, new)
    return nraw + blob[len(f['data']):], n, 0


def ftex_find(d, name):
    hit = [t for t in texdec.ftex_list(d) if t[3] == name]
    assert len(hit) == 1, (name, len(hit))
    p, s, raw, _ = hit[0]
    dp = p + 0xB0 + struct.unpack('>i', d[p + 0xB0:p + 0xB4])[0]
    mp = p + 0xB4 + struct.unpack('>i', d[p + 0xB4:p + 0xB8])[0]
    mipoffs = struct.unpack('>13I', d[p + 0x44:p + 0x44 + 52])
    return p, s, dp, mp, mipoffs


def patch_ftex(d, name, old, new):
    p, s, dp, mp, mipoffs = ftex_find(d, name)
    raw = d[dp:dp + s['imageSize']]
    nraw, n = patch_surface(raw, s, old, new)
    d = d[:dp] + nraw + d[dp + s['imageSize']:]
    m = 0
    if s['numMips'] > 1:
        mip = d[mp:mp + s['mipSize']]
        nmip, m = patch_mips(mip, s, mipoffs, old, new)
        d = d[:mp] + nmip + d[mp + s['mipSize']:]
    return d, n, m


# ------------------------------------------------------------------ 검사
def decode_true(raw, s, L=0, mipoffs=None):
    """하드웨어와 같은 풀기(부호 있는 BC5 포함) → (h,w,4)"""
    w, h = max(1, s['width'] >> L), max(1, s['height'] >> L)
    tm, pitch, height, size = level_surface(s, L)
    m, bpe = offsets(w, h, s['format'], tm, pitch, height, s['swizzle'])
    buf = np.frombuffer(raw, np.uint8)
    lin = buf[m[..., None] + np.arange(bpe)]
    if (s['format'] & 0x3F) == 0x1A:
        return lin[:h, :w, :4]
    bh, bw = lin.shape[:2]
    px = decode_blocks(lin.reshape(-1, bpe), s['format']).reshape(bh, bw, 4, 4, 4)
    return px.transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)[:h, :w].astype(np.uint8)


def check(files):
    """만든 파일에서 그림을 다시 풀어 ko png 와 비교. 바뀌지 않은 블록이 원본과 같은지도 본다."""
    rows = json.load(open(os.path.join(GG, 'list.json'), encoding='utf-8'))
    res = []
    for r in ko_targets():
        top, _, member = r['game_path'].partition('//')
        newd = files[top[len('content/'):]]
        newd = fzip.unpack(newd) if newd[:4] == b'FZIP' else newd
        oldd = read_top(top); oldd = fzip.unpack(oldd) if oldd[:4] == b'FZIP' else oldd

        def surf(d):
            if member:
                d = {n: b for n, b, h in nlib.sarc_read(d)[1]}[member]
            if d[:4] == b'Gfx2':
                g = gtx_lib.gtx_parse(d); s = g['surf']; ib = g['img_blk']
                return d[ib['data']:ib['data'] + ib['size']], s, None, None
            if d[:4] == b'FRES':
                p, s, dp, mp, mo = ftex_find(d, r['ftex'])
                return d[dp:dp + s['imageSize']], s, d[mp:mp + s['mipSize']], mo
            f = texdec.flim_info(d)
            return f['data'], dict(width=f['width'], height=f['height'], format=f['format'], tileMode=f['tileMode'],
                                   swizzle=f['swizzle'], numMips=1), None, None
        nraw, s, nmip, mo = surf(newd)
        oraw, _, omip, _ = surf(oldd)
        new_img = load_png(os.path.join(GG, 'ko', r['ko_file'])).astype(int)
        old_png = load_png(os.path.join(GG, r['file'].replace('/', os.sep))).astype(int)
        got = decode_true(nraw, s).astype(int)
        orig_true = decode_true(oraw, s).astype(int)
        chg = np.any(np.abs(new_img - old_png) > 0, -1)
        # 블록 단위로 바뀐 곳
        H, W = chg.shape
        cb = np.pad(chg, ((0, (-H) % 4), (0, (-W) % 4))).reshape((H + 3) // 4, 4, (W + 3) // 4, 4).any((1, 3))
        cbp = np.repeat(np.repeat(cb, 4, 0), 4, 1)[:H, :W]
        signed = (s['format'] & 0x3F) == 0x35 and bool(s['format'] & 0x200)
        diff = np.abs(got - new_img)
        if signed:                                  # 바이트 공간 차이는 0/255 경계에서 감싸므로 부호 값으로
            diff = np.abs(to_signed(got.astype(np.uint8)) - to_signed(new_img.astype(np.uint8)))
            diff[..., 2:] = 0
        err = diff[cbp].mean() if cbp.any() else 0.0
        same_out = bool(np.array_equal(got[~cbp], orig_true[~cbp]))
        mip_err = None
        if nmip is not None and s['numMips'] > 1:
            errs = []
            for L in range(1, min(s['numMips'], 4)):
                w, h = max(1, s['width'] >> L), max(1, s['height'] >> L)
                tm, pitch, height, size = level_surface(s, L)
                off = 0 if L == 1 else mo[L - 1]
                g2 = decode_true(nmip[off:off + size], s, L).astype(int)
                want = shrink(new_img.astype(np.uint8), w, h, s['format']).astype(int)
                d2 = np.abs(g2 - want)
                if signed:
                    d2 = np.abs(to_signed(g2.astype(np.uint8)) - to_signed(want.astype(np.uint8))); d2[..., 2:] = 0
                errs.append(round(float(d2.mean()), 2))
            mip_err = errs
        res.append(dict(id=r['id'], ftex=r.get('ftex'), dup_of=r.get('dup_of'), fmt=hex(s['format']),
                        changed_blocks=int(cb.sum()), err=round(float(err), 2),
                        unchanged_same=same_out, mip_err=mip_err))
    return res


def leftover(files):
    """바꾸기로 한 그림(한글·북미판)의 원본 바이트가 결과 파일 어디에 아직 남았는지 찾는다(사본 자리 포함).
    조사 색인의 모든 자리(id·dup_of)를 원본 md5 와 대조. 돌려주는 값: 남은 자리 목록(0이어야 함)."""
    import hashlib
    rows = json.load(open(os.path.join(GG, 'list.json'), encoding='utf-8'))
    ko = {int(f[:5]) for f in os.listdir(os.path.join(GG, 'ko')) if f.endswith('.png')}
    na = {e['id'] for e in json.load(open(os.path.join(NA_DIR, 'manifest.json'), encoding='utf-8'))}
    want = ko | na
    idx = [json.loads(l) for l in open(os.path.join(ROOT, 'work', 'survey', 'tex', 'index.jsonl'), encoding='utf-8')]
    slots = [e for e in idx if e.get('id', e.get('dup_of')) in want and 'md5' in e]
    cache, left = {}, []
    for e in slots:
        top, _, member = e['path'].partition('//')
        key = top[len('content/'):]
        if key not in files:
            left.append((e['path'], e['name'], '결과 파일 없음')); continue
        if key not in cache:
            d = files[key]
            cache[key] = fzip.unpack(d) if d[:4] == b'FZIP' else d
        d = cache[key]
        if member:
            m = ({x['name']: d[x['start']:x['start'] + x['size']] for x in warc.read(d)} if d[:4] == b'WARC'
                 else {a: b for a, b, h in nlib.sarc_read(d)[1]})
            blob = m[member]
            if blob[:4] == b'Gfx2':
                g = gtx_lib.gtx_parse(blob); ib = g['img_blk']; raw = blob[ib['data']:ib['data'] + ib['size']]
            else:
                raw = texdec.flim_info(blob)['data']
        elif d[:4] == b'Gfx2':
            g = gtx_lib.gtx_parse(d); ib = g['img_blk']; raw = d[ib['data']:ib['data'] + ib['size']]
        else:
            p, s, dp, mp, mo = ftex_find(d, e['name'])
            raw = d[dp:dp + s['imageSize']]
        if hashlib.md5(raw).hexdigest() == e['md5']:
            left.append((e['path'], e['name'], '원본 그대로'))
    return slots, left


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    files, rep = build()
    res = check(files)
    for x in res:
        print(x)
    print('바뀐 곳 밖이 원본과 다른 그림', [x['id'] for x in res if not x['unchanged_same']])
    print('평균 오차 가장 큰 5', sorted(res, key=lambda x: -x['err'])[:5])
