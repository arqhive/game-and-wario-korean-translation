"""레이아웃 글 상자의 textID 가 MSBT 라벨과 맞는지 센다.

사용: python -I tools/textid_map.py   (먼저 extract_msbt.py, survey_textboxes.py)
결과: work/survey/textid_map.json {textid: [msbt 파일, ...]}, 못 찾은 textID 목록
"""
import collections
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    msg = json.load(open(os.path.join(ROOT, 'work', 'extract', 'msbt_JP_Japanese.json'), encoding='utf-8'))
    tb = json.load(open(os.path.join(ROOT, 'work', 'survey', 'textboxes.json'), encoding='utf-8'))
    lab = collections.defaultdict(list)
    for r in msg:
        if r['label']:
            lab[r['label']].append(r['file'])
    ids = collections.Counter(r['textid'] for r in tb)

    def key(t):
        # textID 형식(추정): [숫자[x숫자]@][$]라벨 — 앞 숫자는 글 칸 크기·줄 수 표시로 보임.
        # '@' 뒤만 남기고 '$' 를 떼어 라벨과 맞춘다
        return t.split('@')[-1].lstrip('$')
    hit = {t: lab[key(t)] for t in ids if key(t) in lab}
    miss = sorted(t for t in ids if key(t) not in lab)
    print('접두 $ 개수', sum(1 for t in ids if t.startswith('$')), '$@', sum(1 for t in ids if t.startswith('$@')))
    out = {'hit': hit, 'miss': miss}
    s = json.dumps(out, ensure_ascii=False, indent=1)
    open(os.path.join(ROOT, 'work', 'survey', 'textid_map.json'), 'w', encoding='utf-8').write(s)
    print(f'글 상자 {len(tb)}, 서로 다른 textID {len(ids)}, MSBT 라벨과 같은 것 {len(hit)}, 못 찾음 {len(miss)}')
    print('라벨이 여러 MSBT 에 있는 textID:', sum(1 for v in hit.values() if len(v) > 1))
    print('못 찾은 textID 예:', miss[:30])


if __name__ == '__main__':
    main()
