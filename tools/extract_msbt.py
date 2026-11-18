"""MSBT 전부를 JSON 으로 뽑고 분량·태그를 센다.

사용: python -I tools/extract_msbt.py
결과: work/extract/msbt_JP_Japanese.json, msbt_US_English.json (파일·인덱스·라벨·문자열)
화면: 칸 수, 빈 칸 수, 순수 글자 수(태그 제외), 고유 글자, 태그 종류별 개수
"""
import collections
import json
import os
import sys as _sys
_sys.stdout.reconfigure(encoding="utf-8")
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fzip  # noqa: E402
import nlib  # noqa: E402
import warc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = {
    'JP_Japanese': ('Game Wario [Game] [0005000010112d00]', 'JP_Japanese'),
    'US_English': ('Game Wario [Game] [000500001011f200]', 'US_English'),
}
TAG = re.compile(r'\{[^}]*\}')


def extract(folder, lang):
    p = os.path.join(ROOT, folder, 'content', 'Common', 'Msg', lang, 'msbt.warc.fzip')
    d = fzip.unpack(open(p, 'rb').read())
    rows = []
    for e in warc.read(d):
        b = d[e['start']:e['start'] + e['size']]
        m = nlib.msbt_read(b)
        for i, t in enumerate(m['texts']):
            rows.append({'file': e['name'], 'idx': i, 'label': m['labels'].get(i),
                         'text': nlib.msbt_text_to_str(t, m['endian'])})
    return rows


def stats(name, rows):
    tags = collections.Counter()
    chars = collections.Counter()
    empty = 0
    for r in rows:
        s = r['text']
        for t in TAG.findall(s):
            k = t.split(':')[0] + ':' + t.split(':')[1].rstrip('}') if ':' in t else t
            tags[k] += 1
        plain = TAG.sub('', s)
        if not plain.strip():
            empty += 1
        for c in plain:
            if c not in '\n ':
                chars[c] += 1
    kanji = [c for c in chars if '一' <= c <= '鿿']
    kana = [c for c in chars if '぀' <= c <= 'ヿ']
    print(f'== {name}: 칸 {len(rows)}, 글 없는 칸 {empty}, 순수 글자 {sum(chars.values())}, '
          f'고유 글자 {len(chars)} (한자 {len(kanji)}, 가나 {len(kana)})')
    print('   태그(그룹:종류) 개수:', dict(tags.most_common()))
    return chars


def main():
    out_dir = os.path.join(ROOT, 'work', 'extract')
    os.makedirs(out_dir, exist_ok=True)
    for key, (folder, lang) in SRC.items():
        rows = extract(folder, lang)
        s = json.dumps(rows, ensure_ascii=False, indent=1)
        open(os.path.join(out_dir, f'msbt_{key}.json'), 'w', encoding='utf-8').write(s)
        stats(key, rows)
        per = collections.Counter(r['file'] for r in rows)
        print('   파일별 칸:', dict(per))


if __name__ == '__main__':
    main()
