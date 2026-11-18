"""용어집 후보 뽑기: 일본어 대사에서 가타카나 낱말·한자 낱말 빈도 + 같은 칸 북미판 문장.
출력 work/glossary/term_candidates.json, 화면 요약
거르지 않는다(빈도 1도 넣음). 태그·후리가나는 떼고 센다(후리가나 읽기는 따로 적음).
사용: python -I tools/term_candidates.py
"""
import collections, json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = re.compile(r'\{[^}]*\}')
RUBY = re.compile(r'\{0:0:([0-9a-f]{4})([0-9a-f]{4})([0-9a-f]*)\}')
KATA = re.compile(r'[ァ-ヺー・]{2,}')
KANJI = re.compile(r'[一-龥々]{2,}')

ja = json.load(open(os.path.join(ROOT, 'work', 'extract', 'msbt_JP_Japanese.json'), encoding='utf-8'))
en = {(e['file'], e['label']): e['text'] for e in json.load(open(os.path.join(ROOT, 'work', 'extract', 'msbt_US_English.json'), encoding='utf-8'))}
kata, kanji, ruby = collections.Counter(), collections.Counter(), {}
where = collections.defaultdict(list)
for e in ja:
    t = e['text']
    for m in RUBY.finditer(t):
        r = bytes.fromhex(m.group(3)).decode('utf-16-be', 'replace')
        base_len = int(m.group(1), 16) // 2
        rest = TAG.sub('', t[m.end():])[:base_len]
        ruby[rest] = r
    s = TAG.sub('', t)
    for rx, c in ((KATA, kata), (KANJI, kanji)):
        for w in rx.findall(s):
            c[w] += 1
            if len(where[w]) < 3:
                where[w].append(dict(id='%s|%s' % (e['file'], e['label']), ja=s[:80], en=TAG.sub('', en.get((e['file'], e['label']), ''))[:100]))
out = dict(katakana=[dict(w=w, n=n, ex=where[w]) for w, n in kata.most_common()],
           kanji=[dict(w=w, n=n, ruby=ruby.get(w), ex=where[w]) for w, n in kanji.most_common()],
           files=collections.Counter(e['file'] for e in ja if e['text'].strip()))
os.makedirs(os.path.join(ROOT, 'work', 'glossary'), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, 'work', 'glossary', 'term_candidates.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('가타카나 낱말', len(kata), '한자 낱말', len(kanji))
print('파일별 칸', dict(out['files']))
print('가타카나 상위', ' '.join('%s(%d)' % x for x in kata.most_common(150)))
