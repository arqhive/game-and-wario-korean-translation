"""그림 눈 검토 결과(review_00~07.json, 서브에이전트 후보)를 합치고, 북미판에 같은 픽셀이 없는 일본판 그림(jp_only.json)과 대조한다.

사용: python -I tools/tex_review_merge.py
결과: work/survey/tex/review_merged.json, 화면에 종류별 개수와 「북미판이 바꿨는데 검토 목록에 없는 그림」
"""
import collections
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, 'work', 'survey', 'tex')


def main():
    rows = []
    for i in range(9):
        p = os.path.join(T, 'review', 'review_%02d.json' % i)
        for r in json.load(open(p, encoding='utf-8')):
            r['src'] = i
            rows.append(r)
    idx = {}
    for l in open(os.path.join(T, 'index.jsonl'), encoding='utf-8'):
        r = json.loads(l)
        if 'id' in r:
            idx[r['id']] = r
    by_id = {}
    for r in rows:
        by_id.setdefault(r['id'], r)
    jp_only = json.load(open(os.path.join(T, 'jp_only.json'), encoding='utf-8'))
    sheets = json.load(open(os.path.join(T, 'sheets.json'), encoding='utf-8'))
    auto = {int(k): v for k, v in sheets['auto'].items()}
    missing = [i for i in jp_only if i not in by_id]
    print('검토 목록', len(rows), '서로 다른 번호', len(by_id), '종류', dict(collections.Counter(r['kind'] for r in by_id.values())))
    print('북미판에 없는 그림', len(jp_only), '그중 검토 목록에 있음', len(jp_only) - len(missing), '없음', len(missing))
    print('없는 것 중 기계 판정(단색·8px):', sum(1 for i in missing if i in auto))
    for i in missing:
        r = idx[i]
        print(f"  {i}\t{r['w']}x{r['h']}\t{r['path']}\t{r['name']}")
    for r in by_id.values():
        r['path'] = idx[r['id']]['path']
        r['name'] = idx[r['id']]['name']
        r['jp_only'] = r['id'] in jp_only
    s = json.dumps(sorted(by_id.values(), key=lambda r: r['id']), ensure_ascii=False, indent=1)
    open(os.path.join(T, 'review_merged.json'), 'w', encoding='utf-8').write(s)


if __name__ == '__main__':
    main()
