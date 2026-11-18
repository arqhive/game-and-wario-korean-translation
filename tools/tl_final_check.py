"""번역 마무리 검사: ko 에 남은 가나·한자, 홑/겹낫표, 조사 괄호, 이중 빈칸, 빈 번역을 뽑는다(거르지 않고 전부 출력).
사용: python -I tools/tl_final_check.py
"""
import json, os, re, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = re.compile(r'\{[^}]*\}')
j = json.load(open(os.path.join(ROOT, 'translation', 'messages.json'), encoding='utf-8'))
checks = {
    '가나': re.compile(r'[぀-ヿ]'),
    '한자': re.compile(r'[一-鿿]'),
    '낫표': re.compile(r'[「」『』]'),
    '조사 괄호': re.compile(r'\((을|를|이|가|은|는|와|과|으)\)'),
}
total = 0
for name, rx in checks.items():
    hits = [(e['id'], TAG.sub('', e['ko'])) for e in j if e['ko'] and rx.search(TAG.sub('', e['ko']))]
    total += len(hits)
    print('■ %s %d' % (name, len(hits)))
    for k, t in hits:
        print('  ', k, t.replace('\n', '⏎')[:80])
empty = [e['id'] for e in j if not e['empty'] and not e['ko']]
print('■ 빈 번역', len(empty), empty[:10])
