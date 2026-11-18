"""inspect/*.txt 에서 「사람이 쓴 글처럼 보이는 줄」을 형식별로 세고 모은다(눈 확인 순서용, 원래 목록은 그대로).

기준(보기용): 모든 글자가 CP932 로 표현되고, 반각 가나·제어 문자(줄바꿈·탭 제외)가 없고, 가나가 1자 이상.
사용: python -I tools/survey_plausible.py
결과: work/survey/inspect/plausible_<형식>.txt, 화면에 형식별 개수·파일별 개수
"""
import collections
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, 'work', 'survey', 'inspect')
KANA = re.compile('[ぁ-んァ-ヶ]')
HALF = re.compile('[｡-ﾟ]')
CTRL = re.compile('[\x00-\x08\x0b-\x1f\x7f]')


def ok(t):
    if not KANA.search(t) or HALF.search(t) or CTRL.search(t):
        return False
    try:
        t.encode('cp932')
    except UnicodeEncodeError:
        return False
    return True


def main():
    for f in sorted(os.listdir(D)):
        if not f.endswith('.txt') or f.startswith('plausible_'):
            continue
        hit = []
        n = 0
        for line in open(os.path.join(D, f), encoding='utf-8', newline='\n'):
            n += 1
            sc, b, enc, off, path, t = line.rstrip('\n').split('\t', 5)
            t = json.loads(t)
            if ok(t):
                hit.append((path, enc, off, b, t))
        hit.sort(key=lambda x: (x[0], x[1], int(x[2]) if x[2].isdigit() else 0))
        with open(os.path.join(D, 'plausible_' + f), 'w', encoding='utf-8') as o:
            for h in hit:
                o.write('\t'.join(h[:4]) + '\t' + json.dumps(h[4], ensure_ascii=False) + '\n')
        byfile = collections.Counter(h[0].split('//')[0] + (('//' + h[0].split('//')[1][:20]) if '//' in h[0] else '') for h in hit)
        print('%s\t전체 %d\t글처럼 보임 %d\t파일 %d' % (f[:-4], n, len(hit), len(byfile)), byfile.most_common(4))


if __name__ == '__main__':
    main()
