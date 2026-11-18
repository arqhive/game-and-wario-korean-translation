"""번역용 JSON: work/../translation/messages.json (git 제외 — 원문 포함)

칸마다: id(파일:인덱스), file, idx, label, ja, en(북미판 같은 파일·같은 라벨), boxes(이 라벨을 쓰는 레이아웃 글 상자: 폰트·크기),
ko(빈 칸). 글 없는 칸도 거르지 않고 넣는다(empty=True).
사용: python -I tools/make_tl_json.py   (먼저 extract_msbt.py, survey_textboxes.py)
"""
import collections
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = re.compile(r'\{[^}]*\}')


def main():
    ja = json.load(open(os.path.join(ROOT, 'work', 'extract', 'msbt_JP_Japanese.json'), encoding='utf-8'))
    en = json.load(open(os.path.join(ROOT, 'work', 'extract', 'msbt_US_English.json'), encoding='utf-8'))
    tb = json.load(open(os.path.join(ROOT, 'work', 'survey', 'textboxes.json'), encoding='utf-8'))
    en_map = {(r['file'], r['label']): r['text'] for r in en if r['label']}
    boxes = collections.defaultdict(list)
    for r in tb:
        key = r['textid'].split('@')[-1].lstrip('$')
        if key:
            boxes[key].append(dict(arc=r['arc'], layout=r['layout'], pane=r['pane'], font=r['font'],
                                   size=r['size'], fsize=r['fsize'], prefix=r['textid'][:-len(key)] if key else ''))
    out = []
    for r in ja:
        plain = TAG.sub('', r['text'])
        rec = dict(id=f"{r['file']}:{r['idx']}", file=r['file'], idx=r['idx'], label=r['label'], ja=r['text'],
                   en=en_map.get((r['file'], r['label'])), empty=not plain.strip(), ko='')
        if r['label'] in boxes:
            rec['boxes'] = boxes[r['label']]
        out.append(rec)
    os.makedirs(os.path.join(ROOT, 'translation'), exist_ok=True)
    s = json.dumps(out, ensure_ascii=False, indent=1)
    open(os.path.join(ROOT, 'translation', 'messages.json'), 'w', encoding='utf-8').write(s)
    n_en = sum(1 for r in out if r['en'] is not None)
    print(f'칸 {len(out)}, 글 있음 {sum(not r["empty"] for r in out)}, 북미판 대응 {n_en}, '
          f'레이아웃 상자 연결 {sum(1 for r in out if "boxes" in r)}')


if __name__ == '__main__':
    main()
