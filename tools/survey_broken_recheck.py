"""바이너리 형식(survey_all 에서 「깨짐은 개수만」이던 것)의 깨짐 줄까지 다시 훑어, 사람 글처럼 보이는 줄이 있는지 확인한다.

「깨짐」은 게임 폰트 2,019자 기준이라 진짜 일본어(예: 薄暗い)도 깨짐이 될 수 있어서, 개수만 남긴 줄을 이 기준으로 다시 본다.
기준(엄격): 가나 3자 이상, 길이 4자 이상, 가나 비율 60% 이상, 한자는 JIS 1수준(CP932 0x989F 미만)만, 반각 가나·제어 문자 없음.
모델(bfres)·소리·영상은 사용자 결정대로 보지 않는다.

사용: python -I tools/survey_broken_recheck.py
결과: work/survey/broken_recheck.jsonl (기준에 맞은 줄 전부), 화면에 형식별 개수
"""
import collections
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import survey_all as S  # noqa: E402

KANA = re.compile('[ぁ-んァ-ヶー]')
KANJI = re.compile('[一-鿿]')
HALF = re.compile('[｡-ﾟ]')
CTRL = re.compile('[\x00-\x08\x0b-\x1f\x7f]')


def strict(t):
    if HALF.search(t) or CTRL.search(t):
        return False
    k = len(KANA.findall(t))
    if k < 3 or len(t) < 4 or k / len(t) < 0.6:
        return False
    for ch in KANJI.findall(t):
        try:
            b = ch.encode('cp932')
        except UnicodeEncodeError:
            return False
        if b >= b'\x98\x9f':
            return False
    return True


def visit(path, data, out, stat):
    if path.endswith('.rpx') and data[:4] == b'\x7fELF':
        for i, (n, b) in enumerate(S.rpx_sections(data)):
            visit(path + '//%02d_%s' % (i, n), b, out, stat)
        return
    if data[:4] == b'FZIP':
        try:
            return visit(path, S.fzip.unpack(data), out, stat)
        except Exception:  # noqa: BLE001
            return
    if data[:4] == b'SARC':
        for n, b, h in S.nlib.sarc_read(data)[1]:
            visit(path + '//' + (n or '#%08x' % h), b, out, stat)
        return
    if data[:4] == b'WARC':
        for e in S.warc.read(data):
            visit(path + '//' + e['name'], data[e['start']:e['start'] + e['size']], out, stat)
        return
    if S.is_model(path) or S.is_sound(path):
        return
    name = path.split('//')[-1]
    ext = os.path.splitext(name)[1].lower() or '(없음)'
    top_ext = os.path.splitext(path.split('//')[0].replace('.fzip', ''))[1].lower()
    if ext in S.MEDIA_EXT or top_ext in S.MEDIA_EXT or S.is_list_target(path):
        return      # 영상은 제외, 글 형식은 이미 전부 목록에 있음
    stat[ext] += 0
    for enc, (j, a, z, codec, u) in S.ENCS.items():
        runs = S.u16_runs(data, enc) if u == 2 else S.b8_runs(data, enc)
        for s, e in runs:
            t = data[s:e].decode(codec, 'replace')
            jp = S.JPCH.findall(t)
            if not jp:
                continue
            if not any(ch not in S.FONT for ch in jp):
                continue        # 깨짐 아님 = 이미 목록에 있음
            stat[ext + ' 깨짐'] += 1
            if strict(t):
                out.append({'path': path, 'enc': enc, 'off': s, 'text': t})


def work(rel):
    out = []
    stat = collections.Counter()
    visit(rel, open(os.path.join(S.GAME, rel), 'rb').read(), out, stat)
    return out, stat


def main():
    import multiprocessing as mp
    t0 = time.time()
    rels = []
    for dp, dn, fn in os.walk(S.GAME):
        for f in fn:
            rels.append(os.path.relpath(os.path.join(dp, f), S.GAME).replace(os.sep, '/'))
    rels.sort(key=lambda r: -os.path.getsize(os.path.join(S.GAME, r)))
    allout = []
    tot = collections.Counter()
    with mp.Pool(max(1, (os.cpu_count() or 4) - 2), initializer=S._init) as pool:
        for out, stat in pool.imap_unordered(work, rels):
            allout += out
            tot.update(stat)
    with open(os.path.join(S.OUT, 'broken_recheck.jsonl'), 'w', encoding='utf-8') as f:
        for r in sorted(allout, key=lambda r: (r['path'], r['off'])):
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    byext = collections.Counter(os.path.splitext(r['path'].split('//')[-1])[1].lower() for r in allout)
    print('다시 본 깨짐 줄(형식별):', {k: v for k, v in tot.items() if v})
    print('엄격 기준에 맞은 줄', len(allout), dict(byext))
    for t, n in collections.Counter(r['text'] for r in allout).most_common(30):
        print(' ', n, json.dumps(t, ensure_ascii=False)[:80])
    print('%.0f초' % (time.time() - t0))


if __name__ == '__main__':
    main()
