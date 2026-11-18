"""사운드 목록(SLATE_Sound.xml)에서 음성으로 보이는 이름을 센다(4단계 음성 조사).

사용: python -I tools/sound_names.py
결과: work/survey/sound_voice.json — 이름에 SERIF·VOICE·_JP·_JPN 이 든 소리 전부
"""
import collections
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XML = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]', 'content', 'Sound', 'SLATE_Sound.xml')


def main():
    s = open(XML, encoding='utf-8', errors='replace').read()
    items = re.findall(r'<(\w+) ID="([0-9A-F]+)" Name="([^"]+)"', s)
    allc = collections.Counter(t for t, i, n in items)
    voice = [(t, i, n) for t, i, n in items if re.search(r'SERIF|VOICE|_JPN?(_|$)', n)]
    groups = collections.Counter(re.sub(r'\d+', '#', n) for t, i, n in voice)
    out = [dict(type=t, id=i, name=n) for t, i, n in voice]
    json.dump(out, open(os.path.join(ROOT, 'work', 'survey', 'sound_voice.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('사운드 항목 종류별:', dict(allc))
    print('음성 후보', len(voice))
    for k, v in groups.most_common(40):
        print(f'  {v:4d}  {k}')


if __name__ == '__main__':
    main()
