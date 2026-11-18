"""4단계 전수 조사: 일본판의 모든 파일(code·content·meta)을 묶음(FZIP·SARC·WARC) 안쪽까지 펼쳐
잎 파일 목록과 일본어 문자열 후보를 뽑는다.

사용: python -I tools/survey_all.py
결과:
  work/survey/all_files.jsonl  잎 파일마다 {path, ext, magic, size, md5, hits{인코딩: 개수}}
  work/survey/strings.jsonl    문자열마다 {path, enc, off, text, chars_ok, broken}

문자열 규칙(거르지 않음):
  - 인코딩 4가지: UTF-16BE, UTF-16LE, UTF-8, Shift-JIS. 모든 바이트 위치(짝·홀)에서 찾는다.
  - 0(UTF-16 은 00 00)으로 끝나고, 일본어 글자(가나·한자·전각·반각 가나·일본어 부호)가 하나라도 든 문자열은
    길이·개수 조건 없이 전부 넣는다. 일본어 글자가 하나도 없는 영문 문자열은 넣지 않는다(원래 영어).
  - broken: 문자열 속 일본어 글자 중 게임 폰트(번들 BFFNT 12개 + CafeStd_JP.txt)에 없는 글자가 있으면 True.
    게임이 그릴 수 없는 글자라 깨진 가짜일 가능성이 크다는 표시일 뿐, 빼지 않는다.
"""
import hashlib
import json
import os
import re
import struct
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bffnt_tool  # noqa: E402
import fzip  # noqa: E402
import nlib  # noqa: E402
import warc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]')
OUT = os.path.join(ROOT, 'work', 'survey')

# ---- 바이트 정규식 -------------------------------------------------------
# UTF-16BE: 일본어 글자 J, 허용 글자 A(ASCII·라틴1·일반 부호 2000-27FF·개인 영역 E000-E0FF)
J16BE = rb'(?:\x30[\x00-\xff]|[\x4e-\x9f][\x00-\xff]|\xff[\x01-\x9f])'
A16BE = rb'(?:\x00[\x09\x0a\x0d\x20-\x7e\xa0-\xff]|[\x20-\x27][\x00-\xff]|\xe0[\x00-\xff])'
J16LE = rb'(?:[\x00-\xff]\x30|[\x00-\xff][\x4e-\x9f]|[\x01-\x9f]\xff)'
A16LE = rb'(?:[\x09\x0a\x0d\x20-\x7e\xa0-\xff]\x00|[\x00-\xff][\x20-\x27]|[\x00-\xff]\xe0)'
J8 = rb'(?:\xe3[\x80-\x83][\x80-\xbf]|[\xe4-\xe9][\x80-\xbf][\x80-\xbf]|\xef\xbc[\x81-\xbf]|\xef\xbd[\x80-\xbf]|\xef\xbe[\x80-\x9f])'
A8 = rb'(?:[\x09\x0a\x0d\x20-\x7e]|\xc2[\xa0-\xbf]|\xc3[\x80-\xbf]|\xe2[\x80-\x9f][\x80-\xbf]|\xee[\x80-\x83][\x80-\xbf])'
JSJ = rb'(?:[\x81-\x84\x88-\x9f\xe0-\xea][\x40-\x7e\x80-\xfc]|[\xa1-\xdf])'
ASJ = rb'(?:[\x09\x0a\x0d\x20-\x7e])'

ENCS = {
    # 이름: (일본어 글자로 시작해 허용 글자가 이어지다 0 으로 끝나는 꼬리, 왼쪽 확장용 단위, 끝 0, 코덱, 단위 길이)
    'utf16be': (J16BE, A16BE, b'\x00\x00', 'utf-16-be', 2),
    'utf16le': (J16LE, A16LE, b'\x00\x00', 'utf-16-le', 2),
    'utf8': (J8, A8, b'\x00', 'utf-8', 0),
    'sjis': (JSJ, ASJ, b'\x00', 'cp932', 0),
}
PAT = {}
LEFT = {}
for k, (j, a, z, c, u) in ENCS.items():
    PAT[k] = re.compile(j + rb'(?:' + j + rb'|' + a + rb')*+' + re.escape(z))
    LEFT[k] = re.compile(rb'(?:' + j + rb'|' + a + rb')')

JPCH = re.compile('[　-ヿ一-鿿！-ﾟ]')


def load_font_chars():
    chars = set()
    fdir = os.path.join(GAME, 'content', 'Common', 'Font')
    for f in os.listdir(fdir):
        p = os.path.join(fdir, f)
        if f.endswith('.bffnt.fzip'):
            ft = bffnt_tool.BFFNT(fzip.unpack(open(p, 'rb').read()))
            chars |= {chr(c) for c in ft.charmap}
        elif f.endswith('.txt'):
            chars |= set(open(p, encoding='utf-16').read())   # CafeStd_JP.txt 는 UTF-16(BOM FE FF)
    return chars


FONT = set()


def extend_left(data, start, enc):
    """매치 시작(일본어 글자)에서 왼쪽으로 허용 글자를 붙인다(같은 단위 길이 정렬 유지)."""
    j, a, z, c, u = ENCS[enc]
    pat = LEFT[enc]
    s = start
    if u == 2:
        while s >= 2 and pat.fullmatch(data, s - 2, s):
            s -= 2
    else:
        # 가변 길이: 1~3바이트 뒤로 보며 허용 글자 하나가 정확히 끝나는지
        while True:
            for back in (1, 2, 3):
                if s - back >= 0 and pat.fullmatch(data, s - back, s):
                    s -= back
                    break
            else:
                break
    return s


LIST_EXT = ('.msbt', '.bflyt', '.sttxt', '.txt', '.ini', '.tsv', '.csv', '.xml', '.pos', '.dat', '.bin', '.fsid', '.fsdb')
RPX_LIST_SECS = ('.rodata', '.data', '.fexports', '.strtab', '.shstrtab', '.module_id')


def is_list_target(path):
    """글이 들어가는 형식: 조건 없이 전부 목록. 그 밖(그림·모델·소리·영상·기계어): 깨짐 아닌 것만 목록, 깨짐은 개수만."""
    leaf = path.split('//')[-1]
    if path.startswith('code/') and '//' in path:
        return any(leaf.endswith(s) for s in RPX_LIST_SECS)
    if path.startswith('meta/') or path.startswith('code/'):
        return True
    return os.path.splitext(leaf)[1].lower() in LIST_EXT


import numpy as np  # noqa: E402

# 한 번만 훑는(선형) 방식. 예전 방식(일본어 글자에서 시작해 0 까지 *+ 로 읽기)은 0 이 없는 긴 구간에서
# 시작 위치마다 끝까지 다시 읽어 시간이 제곱으로 늘었다(스키 맵 bfres 한 개에 몇 시간).
# 지금: 허용 글자(일본어+허용)로 된 「가장 긴 구간」을 한 번에 찾고, 그 바로 뒤가 0 이며 일본어 글자가 든 구간만 문자열.
# 예전 extend_left(왼쪽으로 허용 글자 붙이기)와 같은 결과다. UTF-16 은 짝·홀 정렬을 따로 다 본다.
RUN8 = {k: re.compile(rb'(?:' + ENCS[k][0] + rb'|' + ENCS[k][1] + rb')++') for k in ('utf8', 'sjis')}


def u16_runs(data, enc):
    """UTF-16 문자열 후보 [(바이트 시작, 바이트 끝)] — 짝·홀 정렬 모두."""
    dt = '>u2' if enc == 'utf16be' else '<u2'
    out = []
    for a in (0, 1):
        n = (len(data) - a) // 2
        if n <= 0:
            continue
        u = np.frombuffer(data, dtype=dt, count=n, offset=a).astype(np.int32)
        J = ((u >= 0x3000) & (u <= 0x30ff)) | ((u >= 0x4e00) & (u <= 0x9fff)) | ((u >= 0xff01) & (u <= 0xff9f))
        A = ((u == 9) | (u == 10) | (u == 13) | ((u >= 0x20) & (u <= 0x7e)) | ((u >= 0xa0) & (u <= 0xff))
             | ((u >= 0x2000) & (u <= 0x27ff)) | ((u >= 0xe000) & (u <= 0xe0ff)))
        ok = (J | A).astype(np.int8)
        d = np.diff(np.concatenate(([0], ok, [0])))
        st = np.flatnonzero(d == 1)
        en = np.flatnonzero(d == -1)
        if not len(st):
            continue
        keep = en < n
        st, en = st[keep], en[keep]
        keep = u[en] == 0
        st, en = st[keep], en[keep]
        cj = np.concatenate(([0], np.cumsum(J)))
        keep = cj[en] - cj[st] > 0
        for s, e in zip(st[keep].tolist(), en[keep].tolist()):
            out.append((a + 2 * s, a + 2 * e))
    out.sort()
    return out


# 글자를 이루는 바이트 전부(첫 바이트·뒷 바이트·ASCII). 00 은 없다.
B8CLASS = {
    'sjis': [0x09, 0x0a, 0x0d] + list(range(0x20, 0x7f)) + list(range(0x80, 0xfd)),
    'utf8': [0x09, 0x0a, 0x0d] + list(range(0x20, 0x7f)) + list(range(0x80, 0xc0)) + [0xc2, 0xc3] + list(range(0xe2, 0xea)) + [0xee, 0xef],
}
B8LUT = {}
for _k, _v in B8CLASS.items():
    _t = np.zeros(256, dtype=bool)
    _t[_v] = True
    B8LUT[_k] = _t


def b8_runs(data, enc):
    """UTF-8·SJIS: 예전 방식(일본어 글자에서 앞으로 읽어 0 에서 끝 + 왼쪽 확장)을 그대로 쓰되,
    「글자 바이트가 이어지다 바로 뒤가 00 인 구간」 안에서만 돌린다.
    문자열은 00 으로 끝나고 안에 00·글자 밖 바이트가 없으므로 그런 구간 밖에서는 예전 방식도 아무것도 못 찾는다(결과 같음).
    00 으로 안 끝나는 긴 구간을 시작 위치마다 다시 읽던 제곱 시간(Search Map04 3,082초)이 없어진다.
    (구간 전체를 한 덩어리로 읽는 방식은 SJIS 2바이트 경계를 잘못 잡아 놓쳐서 쓰지 않는다 — 대조 시험 ItemMine 30개.)"""
    z = len(ENCS[enc][2])
    b = np.frombuffer(data, dtype=np.uint8)
    if not len(b):
        return []
    ok = B8LUT[enc][b].astype(np.int8)
    d = np.diff(np.concatenate(([0], ok, [0])))
    st = np.flatnonzero(d == 1)
    en = np.flatnonzero(d == -1)
    keep = en < len(b)
    st, en = st[keep], en[keep]
    keep = b[en] == 0
    out = []
    for s, e in zip(st[keep].tolist(), en[keep].tolist()):
        for m in PAT[enc].finditer(data, s, e + 1):
            out.append((extend_left(data, m.start(), enc), m.end() - z))
    return out


def scan(data, path, sfh, list_all=True):
    hits = {}
    for enc, (j, a, z, codec, u) in ENCS.items():
        n = 0
        nb = 0
        runs = u16_runs(data, enc) if u == 2 else b8_runs(data, enc)
        for s, e in runs:
            raw = data[s:e]
            try:
                text = raw.decode(codec)
            except UnicodeDecodeError:
                text = raw.decode(codec, 'replace')
            jp = JPCH.findall(text)
            if not jp:
                continue
            missing = sorted({ch for ch in jp if ch not in FONT})
            n += 1
            if missing:
                nb += 1
                if not list_all:
                    continue
            rec = {'path': path, 'enc': enc, 'off': s, 'text': text,
                   'broken': bool(missing)}
            if missing:
                rec['not_in_font'] = ''.join(missing[:20])
            sfh.write(json.dumps(rec, ensure_ascii=False) + '\n')
        if n:
            hits[enc] = n
            hits[enc + '_broken'] = nb
    return hits


TEXT_EXT = ('.txt', '.ini', '.tsv', '.csv', '.xml', '.pos', '.dat', '.fsid', '.fsdb')
# 영상: 바이트 검사는 잡음뿐(Ski.mp4 한 개에 12만 줄, 99.6% 폰트에 없는 글자) → 개수만 세고 목록은 안 쓴다.
# 영상 화면은 movie_sheets.py 로 따로 봤다.
MEDIA_EXT = ('.mp4', '.h264')
# 소리: 사용자 지시(2026-11-12)로 전수조사에서 보지 않는다. 훑지 않고 파일 개수만 센다.
SOUND_EXT = ('.bfstm', '.bfgrp', '.bfsar', '.btsnd', '.wav')


def is_model(path):
    """3D 모델(bfres): 사용자 지시(2026-11-13)로 문자열 바이트 검사에서 뺀다. 개수만 센다.
    모델에 든 그림(FTEX)은 tex_survey.py 로 따로 다 꺼내 봤다."""
    top = path.split('//')[0].replace('.fzip', '')
    return os.path.splitext(top)[1].lower() == '.bfres' or path.lower().endswith('.bfres')


def is_sound(path):
    top = path.split('//')[0].replace('.fzip', '')
    ext = os.path.splitext(top)[1].lower()
    if ext in SOUND_EXT:
        return True
    return top.startswith('content/Sound/wav/') and ext in ('.raw', '.rdb')


def text_lines(data, path, sfh):
    """평문 파일: BOM·UTF-8·CP932 순서로 통째로 풀어 일본어가 든 줄을 전부 넣는다."""
    # 마지막 'utf-8-replace': UTF-8 BOM 파일인데 중간에 UTF-8 아닌 바이트가 섞인 경우(셰이더 .fsdb 116개, 0xa0 하나 때문에
    # 통째로 실패해 일본어 라벨 3,104줄을 놓쳤음) — 이상한 바이트만 대체 문자로 바꿔 끝까지 읽는다.
    for codec in ('utf-16', 'utf-8', 'cp932', 'utf-8-replace'):
        if codec == 'utf-16' and data[:2] not in (b'\xff\xfe', b'\xfe\xff'):
            continue
        if codec == 'utf-8-replace':
            if data[:3] != b'\xef\xbb\xbf':
                continue
            s = data.decode('utf-8', 'replace')
        else:
            try:
                s = data.decode(codec)
            except UnicodeDecodeError:
                continue
        n = 0
        for i, line in enumerate(s.splitlines()):
            jp = JPCH.findall(line)
            if not jp:
                continue
            missing = sorted({ch for ch in jp if ch not in FONT})
            rec = {'path': path, 'enc': 'text-' + codec, 'line': i + 1, 'text': line, 'broken': bool(missing)}
            if missing:
                rec['not_in_font'] = ''.join(missing[:20])
            sfh.write(json.dumps(rec, ensure_ascii=False) + '\n')
            n += 1
        return codec, n
    return None, 0


def rpx_sections(data):
    """RPX(ELF) 구역을 풀어 [(이름, 바이트)]. 압축 구역(flags 0x08000000)은 zlib."""
    import zlib
    shoff = struct.unpack('>I', data[0x20:0x24])[0]
    shnum, shstr = struct.unpack('>HH', data[0x30:0x34])
    secs = []
    for i in range(shnum):
        o = shoff + i * 40
        name, typ, flags, addr, off, size = struct.unpack('>IIIIII', data[o:o + 24])
        raw = data[off:off + size] if typ != 8 else b''
        if flags & 0x08000000 and size >= 4:
            raw = zlib.decompress(raw[4:])
        secs.append((name, raw))
    strtab = secs[shstr][1]
    return [(strtab[n:strtab.index(b'\0', n)].decode('ascii', 'replace') or '#%d' % i, r)
            for i, (n, r) in enumerate(secs)]


def leaf(path, data, ffh, sfh, stat):
    if path.endswith('.rpx') and data[:4] == b'\x7fELF':
        secs = rpx_sections(data)
        record(path, b'', ffh, sfh, stat, note='container RPX %d' % len(secs))
        for i, (n, b) in enumerate(secs):
            leaf(path + '//%02d_%s' % (i, n), b, ffh, sfh, stat)
        return
    if data[:4] == b'FZIP':
        try:
            return leaf(path, fzip.unpack(data), ffh, sfh, stat)
        except Exception as ex:  # noqa: BLE001
            return record(path, data, ffh, sfh, stat, note='FZIP-ERR ' + str(ex))
    if data[:1] == b'\x78' and data[1:2] in (b'\x01', b'\x5e', b'\x9c', b'\xda'):
        # 맨 zlib(전자 설명서 Manual.bfma 의 .arc 7개 = zlib → SARC). 처음엔 안 풀어 설명서 안을 못 봤다.
        import zlib
        try:
            u = zlib.decompress(data)
        except zlib.error:
            u = None
        if u is not None:
            record(path, b'', ffh, sfh, stat, note='container ZLIB %d' % len(u))
            return leaf(path + '//(zlib)', u, ffh, sfh, stat)
    if data[:4] == b'SARC':
        files = nlib.sarc_read(data)[1]
        record(path, b'', ffh, sfh, stat, note='container SARC %d' % len(files))
        for n, b, h in files:
            leaf(path + '//' + (n or '#%08x' % h), b, ffh, sfh, stat)
        return
    if data[:4] == b'WARC':
        ents = warc.read(data)
        record(path, b'', ffh, sfh, stat, note='container WARC %d' % len(ents))
        for e in ents:
            leaf(path + '//' + e['name'], data[e['start']:e['start'] + e['size']], ffh, sfh, stat)
        return
    record(path, data, ffh, sfh, stat)


def record(path, data, ffh, sfh, stat, note=None):
    name = path.split('//')[-1]
    ext = os.path.splitext(name)[1].lower() or '(없음)'
    r = {'path': path, 'ext': ext, 'size': len(data), 'magic': data[:4].hex(),
         'md5': hashlib.md5(data).hexdigest() if data else ''}
    if note:
        r['note'] = note
    else:
        stat['leaf'] += 1
        top_ext = os.path.splitext(path.split('//')[0].replace('.fzip', ''))[1].lower()
        if is_model(path):
            r['model_excluded'] = True
            ffh.write(json.dumps(r, ensure_ascii=False) + '\n')
            return
        if is_sound(path):
            r['sound_excluded'] = True
            ffh.write(json.dumps(r, ensure_ascii=False) + '\n')
            return
        if ext in MEDIA_EXT or top_ext in MEDIA_EXT:
            import io
            h = scan(data, path, io.StringIO())       # 개수만
            r['media_count_only'] = True
        else:
            la = is_list_target(path)
            h = scan(data, path, sfh, list_all=la)
            if not la:
                r['broken_count_only'] = True
        if ext in TEXT_EXT or data[:2] in (b'\xff\xfe', b'\xfe\xff') and ext not in ('.msbt',):
            codec, n = text_lines(data, path, sfh)
            if codec:
                r['text_codec'] = codec
                if n:
                    h['text'] = n
        if h:
            r['hits'] = h
    ffh.write(json.dumps(r, ensure_ascii=False) + '\n')


def _init():
    global FONT
    FONT = load_font_chars()


def work(rel):
    """원본 파일 하나(안쪽 묶음까지)를 처리해 (rel, 파일 줄, 문자열 줄, 잎 수, 걸린 초)."""
    import io
    t1 = time.time()
    ffh, sfh = io.StringIO(), io.StringIO()
    stat = {'leaf': 0}
    leaf(rel, open(os.path.join(GAME, rel), 'rb').read(), ffh, sfh, stat)
    return rel, ffh.getvalue(), sfh.getvalue(), stat['leaf'], time.time() - t1


def main():
    import multiprocessing as mp
    global FONT
    FONT = load_font_chars()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    stat = {'leaf': 0, 'top': 0}
    rels = []
    for dp, dn, fn in os.walk(GAME):
        dn.sort()
        for f in sorted(fn):
            rels.append(os.path.relpath(os.path.join(dp, f), GAME).replace(os.sep, '/'))
    # 큰 파일부터 나눠 주고(오래 걸리는 것 먼저 시작), 결과는 원래 순서로 쓴다.
    order = sorted(rels, key=lambda r: -os.path.getsize(os.path.join(GAME, r)))
    res = {}
    with mp.Pool(max(1, (os.cpu_count() or 4) - 2), initializer=_init) as pool:
        for rel, fl, sl, nleaf, sec in pool.imap_unordered(work, order):
            res[rel] = (fl, sl)
            stat['leaf'] += nleaf
            stat['top'] += 1
            if sec > 10:
                print('  느림 %.0f초 %s' % (sec, rel), flush=True)
            if stat['top'] % 100 == 0:
                print('%d/%d 파일, 잎 %d, %.0f초' % (stat['top'], len(rels), stat['leaf'], time.time() - t0), flush=True)
    with open(os.path.join(OUT, 'all_files.jsonl'), 'w', encoding='utf-8') as ffh, \
            open(os.path.join(OUT, 'strings.jsonl'), 'w', encoding='utf-8') as sfh:
        for rel in rels:
            ffh.write(res[rel][0])
            sfh.write(res[rel][1])
    print('끝: 원본 파일 %d, 잎 파일 %d, 폰트 글자 %d, %.0f초' % (stat['top'], stat['leaf'], len(FONT), time.time() - t0))


if __name__ == '__main__':
    main()
