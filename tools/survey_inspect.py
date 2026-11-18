"""survey_all 결과(strings.jsonl)를 형식별로 눈 확인용으로 늘어놓는다. 거르지 않고 정렬만 한다.

- 각 줄에 「사람 글 점수」를 매겨(가나·자주 쓰는 한자 비율, 길이) 높은 순으로 보여 준다. 점수는 보는 순서일 뿐 빼는 기준이 아니다.
- MSBT 는 구조 추출(work/extract/msbt_JP_Japanese.json)의 글과 대조해, 구조 추출에 없는 바이트 검사 결과만 따로 센다.

사용: python -I tools/survey_inspect.py
결과: work/survey/inspect/<형식>.txt (형식마다 전부, 점수 순), 화면에 요약
"""
import collections
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, 'work', 'survey')
OUTD = os.path.join(S, 'inspect')
KANA = re.compile('[ぁ-んァ-ヶー]')
JP = re.compile('[　-ヿ一-鿿！-ﾟ]')
TAG = re.compile(r'\{[^}]*\}')


def score(t):
    n = len(t)
    if not n:
        return 0
    k = len(KANA.findall(t))
    j = len(JP.findall(t))
    return (k * 2 + j) / n * min(n, 20)


def msbt_texts():
    p = os.path.join(ROOT, 'work', 'extract', 'msbt_JP_Japanese.json')
    d = json.load(open(p, encoding='utf-8'))
    pieces = set()
    full = []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str):
            full.append(x)
            for s in TAG.split(x):
                if s:
                    pieces.add(s)
    walk(d)
    return pieces, '\n'.join(full)


def main():
    os.makedirs(OUTD, exist_ok=True)
    files = {}
    for line in open(os.path.join(S, 'all_files.jsonl'), encoding='utf-8', newline='\n'):
        r = json.loads(line)
        files[r['path']] = r['ext']
    by = collections.defaultdict(list)
    for line in open(os.path.join(S, 'strings.jsonl'), encoding='utf-8', newline='\n'):
        r = json.loads(line)
        by[files.get(r['path'], '?')].append(r)
    pieces, fulltext = msbt_texts()
    for ext, rows in sorted(by.items(), key=lambda x: -len(x[1])):
        rows.sort(key=lambda r: -score(r['text']))
        with open(os.path.join(OUTD, ext.strip('.') + '.txt'), 'w', encoding='utf-8') as f:
            for r in rows:
                f.write('%.1f\t%s\t%s\t%s\t%s\t%s\n' % (score(r['text']), 'X' if r['broken'] else '-', r['enc'],
                                                       r.get('off', r.get('line')), r['path'], json.dumps(r['text'], ensure_ascii=False)))
        hi = sum(1 for r in rows if score(r['text']) >= 10)
        extra = ''
        if ext == '.msbt':
            notin = [r for r in rows if r['text'] not in fulltext]
            extra = ' / 구조 추출 글에 없는 줄 %d (깨짐 아님 %d)' % (len(notin), sum(1 for r in notin if not r['broken']))
        print('%s\t전체 %d\t깨짐 아님 %d\t점수10이상 %d%s' % (ext, len(rows), sum(1 for r in rows if not r['broken']), hi, extra))


if __name__ == '__main__':
    main()
