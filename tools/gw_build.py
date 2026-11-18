"""한글 패치 빌드(번역 전체).

입력: translation/messages.json 의 ko(빈 ko 는 원문 유지), 원본 일본판 content.
바꾸는 파일:
  content/Common/Msg/JP_Japanese/msbt.warc.fzip      대사 54개 MSBT
  content/Common/Font/{Caption50L,Caption64L,Exp50,Serif38}_JP.bffnt.fzip
      gw_font.build_korean: 번역문에 쓰는 한글 밖 글자·ASCII 칸은 그대로, 나머지 칸(안 쓰는 가나·한자)을 한글로 덮어쓰고
      모자라면 시트 추가(11/18 사용자 결정). ‘’“” 등 폰트에 없는 글자도 같이 넣는다.
  content/Common/Font/CafeStd_JP.txt                  본체 폰트로 미리 그릴 글자 목록에 한글 추가
  그림 글씨 49개 파일(gw_gfx: 한글 그림 113장 + 북미판 교체 16장)
출력: work/build/full/sd/wiiu/sdcafiine/0005000010112D00/GameWarioKR/content/...  (SD 루트 구조)
사용: python -I tools/gw_build.py
"""
import collections
import hashlib
import json
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fzip  # noqa: E402
import gw_font  # noqa: E402
import gw_gfx  # noqa: E402
import nlib  # noqa: E402
import warc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]', 'content')
OUT = os.path.join(ROOT, 'work', 'build', 'full')
TITLE = '0005000010112D00'
PACK = 'GameWarioKR'
MSG = os.path.join('Common', 'Msg', 'JP_Japanese', 'msbt.warc.fzip')
CAFE_TXT = os.path.join('Common', 'Font', 'CafeStd_JP.txt')
FONTS = ['Caption50L_JP', 'Caption64L_JP', 'Exp50_JP', 'Serif38_JP']
TAG = re.compile(r'\{[^}]*\}')


def load_tr():
    j = json.load(open(os.path.join(ROOT, 'translation', 'messages.json'), encoding='utf-8'))
    tr = collections.defaultdict(dict)
    for e in j:
        if e['ko']:
            tr[e['file']][e['idx']] = e['ko']
    return tr, j


def build_msg(tr):
    raw = fzip.unpack(open(os.path.join(GAME, MSG), 'rb').read())
    ents = warc.read(raw)
    rep, n = {}, 0
    for e in ents:
        if e['name'] not in tr:
            continue
        b = raw[e['start']:e['start'] + e['size']]
        m = nlib.msbt_read(b)
        assert nlib.msbt_write(m) == b, '무변경 다시 쓰기가 원본과 다름: ' + e['name']
        texts = list(m['texts'])
        for i, ko in tr[e['name']].items():
            texts[i] = nlib.str_to_msbt(ko, m['endian'])
            assert nlib.msbt_text_to_str(texts[i], m['endian']) == ko, (e['name'], i)
            n += 1
        rep[e['name']] = nlib.msbt_write(m, texts)
    new = warc.write(raw, rep)
    # 검사: 다시 읽은 대사가 번역과 같은지(전부)
    back = {x['name']: nlib.msbt_read(new[x['start']:x['start'] + x['size']]) for x in warc.read(new)}
    for fn, d in tr.items():
        for i, ko in d.items():
            assert nlib.msbt_text_to_str(back[fn]['texts'][i], back[fn]['endian']) == ko, (fn, i)
    return fzip.pack(new), n, len(rep)


def text_chars(j):
    allc = set()
    for e in j:
        if e['ko']:
            allc |= set(TAG.sub('', e['ko']))
    allc.discard('\n')
    return allc


# 11/18 실기: 폰트 넷이 원본보다 늘어난 양 합계가 1.57MB 는 통과, 2.10MB 는 게임 진입 때 에러(KR10·KR12 대조).
# 그래서 시트 수를 정해 두고(BC4 한 장 0.5MB, BC5 한 장 1MB) 모자라면 칸을 줄인다(사용자 「가 안」).
FIT_SHEETS = {'Caption50L_JP': 4, 'Caption64L_JP': 4, 'Exp50_JP': 3, 'Serif38_JP': 1}
GROW_LIMIT = 1_572_864      # 통과한 KR10 이 늘어난 양


def font_lines(j, charmap):
    """원본 일본어가 이 폰트에 있는 글자만으로 된 줄(= 이 폰트로 나올 수 있는 줄). 원본에 없는 글자가 섞인 줄은
    원래부터 이 폰트로는 못 그리므로 뺀다. 태그·버튼 그림·빈칸만 있는 줄은 뺀다."""
    cs = {chr(c) for c in charmap} | {' ', '　', '\n'}
    out = []
    for e in j:
        if not e['ko']:
            continue
        s = set(TAG.sub('', e['ja']))
        body = {c for c in s if not 0xE000 <= ord(c) <= 0xF8FF and c not in ' 　\n'}
        if body and s <= cs | {c for c in s if 0xE000 <= ord(c) <= 0xF8FF}:
            out.append(e)
    return out


def build_fonts(allc, j):
    import bffnt_tool as bt
    out, rep = {}, []
    for n in FONTS:
        src = fzip.unpack(open(os.path.join(GAME, 'Common', 'Font', n + '.bffnt.fzip'), 'rb').read())
        f = bt.BFFNT(src)
        need = text_chars([e for e in font_lines(j, f.charmap)])
        hangul = {c for c in need if 0xAC00 <= ord(c) <= 0xD7A3}
        other = {c for c in need if c not in hangul and ord(c) > 0x7F}
        keep = {c for c in other if ord(c) in f.charmap}
        new = hangul | {c for c in other if ord(c) not in f.charmap and not 0xE000 <= ord(c) <= 0xF8FF}
        # 반각(ASCII)도 폰트에 없으면 그려 넣는다(11/19: Serif38 원본에 ! ? ~ , : 등이 없어 화면에서 빠짐, 사용자 지적).
        new |= {c for c in need if ord(c) <= 0x7F and c not in ' \n' and ord(c) not in f.charmap}
        data, st = gw_font.build_korean_fit(src, n, new, keep, FIT_SHEETS[n])
        bad, blank, oor = gw_font.verify_fit(src, data, new, keep)
        st.update(keep_bad=''.join(sorted(bad)), blank=''.join(sorted(blank)), out_of_range=len(oor),
                  size=(len(src), len(data)), extra=''.join(sorted(c for c in new if c not in hangul)),
                  lines=len(font_lines(j, f.charmap)), hangul=len(hangul),
                  dropped=len({c for c in allc if 0xAC00 <= ord(c) <= 0xD7A3} - hangul))
        assert not bad and not blank and not oor, st
        # 11/19 실수 재발 막기: ① 이 폰트로 나올 줄의 번역 글자가 전부 있나(ASCII 포함) ② 새 글자 테두리가 그리는 폭 안인가
        g2 = bt.BFFNT(data)
        lack = sorted(c for c in need if c not in ' \n' and not 0xE000 <= ord(c) <= 0xF8FF and ord(c) not in g2.charmap)
        assert not lack, (n, '폰트에 없는 글자', ''.join(lack))
        ch2 = gw_font.decode(g2)
        spill = []
        for c in new:
            gi = g2.charmap[ord(c)]
            wl, wg, wc = g2.widths.get(gi, (g2.def_left, g2.def_glyph_w, g2.def_char_w))
            bx = [b for b in (gw_font.ink(gw_font.fa.get_glyph(s, g2, gi), 40) for s in ch2) if b]
            if bx and max(b[2] for b in bx) - wg > 1:
                spill.append(c)
        assert not spill, (n, '그리는 폭 밖으로 나가는 글자', ''.join(spill[:20]))
        st['lack'], st['spill'] = len(lack), len(spill)
        rep.append(st)
        out[n] = fzip.pack(data)
    grow = sum(r['size'][1] - r['size'][0] for r in rep)
    print('폰트 늘어난 양 합계', grow, '(통과한 KR10:', GROW_LIMIT, ')')
    if grow > GROW_LIMIT:
        print('주의: 통과 확인한 양보다', grow - GROW_LIMIT, '바이트 많음(에러 난 양 2,097,152 보다는', 2_097_152 - grow, '적음)')
    return out, rep


def build_cafe_txt(j):
    """본체 폰트로 미리 그릴 글자 목록. 11/18 실기: 원본(1,884자)에 한글을 더해 3,032자로 늘리자 목록 뒤쪽 글자
    (「시작」 등)가 ?? 로 나옴 → 일본어 한자를 빼고 번역에 쓰는 글자를 넣어 원본보다 짧게(KR15, 실기 전부 한글 확인).
    한자를 뺐으므로 대사 밖에서 오는 한자(Mii 이름 등)는 ?? 가 될 수 있다(확인 안 함)."""
    raw = open(os.path.join(GAME, CAFE_TXT), 'rb').read()
    s = raw.decode('utf-16')
    assert raw[:2] == b'\xfe\xff' and list(s) == sorted(s)
    use = set()
    for e in j:
        use |= set(TAG.sub('', e['ko'] or e['ja']))
    new = ''.join(sorted({c for c in s if not 0x4E00 <= ord(c) <= 0x9FFF} |
                         {c for c in use if ord(c) >= 0x20 and c != '\n' and not 0xE000 <= ord(c) <= 0xF8FF}))
    assert len(new) <= len(s), ('목록이 원본보다 김', len(new), len(s))
    return b'\xfe\xff' + new.encode('utf-16-be'), len(new) - len(s)


def main():
    tr, j = load_tr()
    allc = text_chars(j)
    msg, n_txt, n_msbt = build_msg(tr)
    print('대사', n_txt, '칸 / MSBT', n_msbt, '개')
    fonts, frep = build_fonts(allc, j)
    for r in frep:
        print('폰트', r['name'], '줄', r['lines'], '한글', r['hangul'], '(안 넣은 한글', r['dropped'], ') 새 글자', r['added'],
              '남긴 칸', r['kept'], '시트', r['sheets'], '칸', r['cell'], '배율', r['scale'], '남는 칸', r['spare'],
              '크기', r['size'], '한글 밖 추가', r['extra'])
    cafe, n_cafe = build_cafe_txt(j)
    print('CafeStd_JP.txt 글자 수 원본 대비', n_cafe)
    files = {MSG: msg, CAFE_TXT: cafe}
    for n, z in fonts.items():
        files[os.path.join('Common', 'Font', n + '.bffnt.fzip')] = z
    gfiles, grep = gw_gfx.build(verbose=False)
    gchk = gw_gfx.check(gfiles)
    bad = [x['id'] for x in gchk if not x['unchanged_same']]
    assert not bad, ('그림: 바뀐 블록 밖이 원본과 다름', bad)
    slots, left = gw_gfx.leftover(gfiles)
    print('그림 자리', len(slots), '중 원본 그대로 남은 자리', len(left))
    assert not left, ('그림: 바꾸기로 한 원본이 남음', left[:5])
    print('그림', len(grep), '칸(한글', sum(1 for x in grep if x['kind'] == 'ko'), '· 북미판', sum(1 for x in grep if x['kind'] == 'na'),
          ') 파일', len(gfiles), '· 최대 평균 오차', max(x['err'] for x in gchk))
    for rel, b in gfiles.items():
        rel = os.path.join(*rel.split('/'))
        assert rel not in files, rel
        files[rel] = b
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    base = os.path.join(OUT, 'sd', 'wiiu', 'sdcafiine', TITLE, PACK, 'content')
    man = {}
    for rel, b in files.items():
        p = os.path.join(base, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(b)
        man[rel.replace('\\', '/')] = hashlib.md5(b).hexdigest()
    json.dump(dict(files=man, fonts=frep), open(os.path.join(OUT, 'report.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1, default=str)
    for k, v in man.items():
        print(v, k)


if __name__ == '__main__':
    main()
