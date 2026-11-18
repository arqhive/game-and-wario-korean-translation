"""GPT 에 넘길 그림 묶음 만들기: 일본어 그림(review_verified 「일본어 맞음」)을 원본 PNG 와 목록으로.
출력 work/gpt_graphics/ (원본 그림이라 커밋 안 함)
  jp/<id>_<이름>.png   원본(디코드한 그대로, 크기·알파 유지)
  list.json / list.md   id·파일·원문·설명·크기·형식·번역안(빈 칸)
  요청서.md
사용: python -I tools/gpt_pack.py
"""
import collections, json, os, shutil, sys
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = os.path.join(ROOT, 'work', 'survey', 'tex')
OUT = os.path.join(ROOT, 'work', 'gpt_graphics')

rev = json.load(open(os.path.join(TEX, 'review_verified.json'), encoding='utf-8'))
idx = {}
for l in open(os.path.join(TEX, 'index.jsonl'), encoding='utf-8'):
    e = json.loads(l)
    if 'id' in e:
        idx[e['id']] = e
jp = [e for e in rev if e['verified'] == '일본어 맞음']
if os.path.isdir(OUT):
    shutil.rmtree(OUT)
os.makedirs(os.path.join(OUT, 'jp'))
rows = []
for e in sorted(jp, key=lambda e: e['id']):
    src = os.path.join(TEX, 'img', '%05d.png' % e['id'])
    base = os.path.splitext(e['name'].replace('^', '_'))[0]
    fn = '%05d_%s.png' % (e['id'], base)
    shutil.copyfile(src, os.path.join(OUT, 'jp', fn))
    im = Image.open(src)
    ix = idx.get(e['id'], {})
    rows.append(dict(id=e['id'], file='jp/' + fn, game_path=e['path'], text_jp=e['text'], note=e['note'],
                     size='%dx%d' % im.size, mode=im.mode, alpha=im.mode in ('RGBA', 'LA'),
                     fmt=ix.get('fmt'), ko=''))
json.dump(rows, open(os.path.join(OUT, 'list.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
grp = collections.defaultdict(list)
for r in rows:
    grp[r['game_path'].split('/')[1]].append(r)
md = ['# 그림 목록 (%d장)' % len(rows), '', '| id | 파일 | 크기 | 투명 | 일본어 원문 | 설명 | 한국어 |', '|---|---|---|---|---|---|---|']
for g in sorted(grp):
    for r in grp[g]:
        md.append('| %d | %s | %s | %s | %s | %s | %s |' % (r['id'], r['file'], r['size'], 'O' if r['alpha'] else '', r['text_jp'].replace('\n', ' / ').replace('|', '\\|'),
                                                       r['note'].replace('|', '\\|'), r['ko']))
open(os.path.join(OUT, 'list.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
print('그림', len(rows), '묶음별', {g: len(v) for g, v in sorted(grp.items())})
print('투명', sum(r['alpha'] for r in rows), '모드', collections.Counter(r['mode'] for r in rows))
