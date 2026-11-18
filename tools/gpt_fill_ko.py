"""work/gpt_graphics/ko.tsv(id<TAB>한국어<TAB>메모)를 list.json 의 ko·ko_note 에 넣고 list.md 를 다시 만든다.
한국어의 ' / ' 는 원문 text_jp 와 같은 칸 나눔 표기. gpt_pack.py 는 폴더를 지우므로 다시 돌리지 말 것.
사용: python -I tools/gpt_fill_ko.py
"""
import collections, json, os, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'gpt_graphics')

rows = json.load(open(os.path.join(OUT, 'list.json'), encoding='utf-8'))
ko = {}
for l in open(os.path.join(OUT, 'ko.tsv'), encoding='utf-8'):
    l = l.rstrip('\n')
    if not l:
        continue
    p = (l.split('\t') + [''])[:3]
    assert len(l.split('\t')) in (2, 3) and p[1].strip(), l
    assert int(p[0]) not in ko, ('중복 id', p[0])
    ko[int(p[0])] = (p[1], p[2])
ids = {r['id'] for r in rows}
assert set(ko) == ids, ('목록에 없는 id', sorted(set(ko) - ids), '빠진 id', sorted(ids - set(ko)))
for r in rows:
    r['ko'], r['ko_note'] = ko[r['id']]
json.dump(rows, open(os.path.join(OUT, 'list.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
grp = collections.defaultdict(list)
for r in rows:
    grp[r['game_path'].split('/')[1]].append(r)
esc = lambda s: s.replace('\n', ' / ').replace('|', '\\|')
md = ['# 그림 목록 (%d장)' % len(rows), '', '| id | 파일 | 크기 | 투명 | 일본어 원문 | 설명 | 한국어 | 번역 메모 |',
      '|---|---|---|---|---|---|---|---|']
for g in sorted(grp):
    for r in grp[g]:
        md.append('| %d | %s | %s | %s | %s | %s | %s | %s |' % (r['id'], r['file'], r['size'], 'O' if r['alpha'] else '',
                                                             esc(r['text_jp']), esc(r['note']), esc(r['ko']), esc(r['ko_note'])))
open(os.path.join(OUT, 'list.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
print('채움', len(rows), '/ 메모 있음', sum(bool(r['ko_note']) for r in rows),
      '/ 칸 수(" / ") 다름', [(r['id'], r['text_jp'].count(' / '), r['ko'].count(' / ')) for r in rows
                             if r['ko'].count(' / ') != r['text_jp'].count(' / ')])
