"""전자 설명서(meta/Manual.bfma) 글 뽑기.

구조: Manual.bfma = SARC → JPN_ja_*.arc = zlib → SARC.
  textset.arc / text_title.arc 의 .bin = 글 상자 하나. 글은 UTF-16BE, 끝에 00 00 이 없다(글자 수가 앞에 붙음).
  그래서 00 끝 문자열만 찾는 survey_all.py 에 안 걸렸다.
뽑기(거르지 않음): 각 .bin 을 짝·홀 정렬로 UTF-16BE 로 읽어, 일본어 글자가 1자 이상 든 「허용 글자 구간」을 전부 넣는다.
  허용 글자 = survey_all 의 UTF-16 J·A 와 같음.

사용: python -I tools/extract_manual.py
결과: work/extract/manual_JP.json [{arc, file, align, off, text}], 화면에 개수와 예
"""
import json
import os
import re
import sys
import zlib

import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nlib  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]')
JP = re.compile('[　-ヿ一-鿿！-ﾟ]')


def runs(b):
    out = []
    for a in (0, 1):
        n = (len(b) - a) // 2
        if n <= 0:
            continue
        u = np.frombuffer(b, dtype='>u2', count=n, offset=a).astype(np.int32)
        J = ((u >= 0x3000) & (u <= 0x30ff)) | ((u >= 0x4e00) & (u <= 0x9fff)) | ((u >= 0xff01) & (u <= 0xff9f))
        A = ((u == 9) | (u == 10) | (u == 13) | ((u >= 0x20) & (u <= 0x7e)) | ((u >= 0xa0) & (u <= 0xff))
             | ((u >= 0x2000) & (u <= 0x27ff)) | ((u >= 0xe000) & (u <= 0xe0ff)))
        ok = (J | A).astype(np.int8)
        d = np.diff(np.concatenate(([0], ok, [0])))
        for s, e in zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist()):
            t = b[a + 2 * s:a + 2 * e].decode('utf-16-be')
            if JP.search(t):
                out.append((a, a + 2 * s, t))
    return out


def main():
    data = open(os.path.join(GAME, 'meta', 'Manual.bfma'), 'rb').read()
    rows = []
    nfiles = 0
    for an, ab, _ in nlib.sarc_read(data)[1]:
        if not an.endswith('.arc'):
            continue
        u = zlib.decompress(ab)
        for fn, fb, _ in nlib.sarc_read(u)[1]:
            if not fn.endswith('.bin'):
                continue
            nfiles += 1
            for a, off, t in runs(fb):
                rows.append({'arc': an, 'file': fn, 'align': a, 'off': off, 'text': t})
    rows.sort(key=lambda r: (r['file'], r['align'], r['off']))
    out = os.path.join(ROOT, 'work', 'extract', 'manual_JP.json')
    json.dump(rows, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    a0 = [r for r in rows if r['align'] == 0]
    print('글 상자 파일', nfiles, '뽑은 구간', len(rows), '(짝 정렬', len(a0), '/ 홀 정렬', len(rows) - len(a0), ')')
    print('짝 정렬 글자 수 합', sum(len(r['text']) for r in a0))
    for r in a0[:25]:
        print(' ', r['file'][:42], json.dumps(r['text'], ensure_ascii=False)[:70])


if __name__ == '__main__':
    main()
