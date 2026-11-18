"""탭 구분 번역표(idx<TAB>칸0[<TAB>칸1...]) → putseg 묶음 JSON.
사용: python -I tools/tsv2seg.py <파일.msbt> <표.txt> <출력.json>
"""
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
fn, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]
out = {}
for line in open(src, encoding='utf-8'):
    line = line.rstrip('\n')
    if not line.strip():
        continue
    cols = line.split('\t')
    out['%s:%s' % (fn, cols[0])] = cols[1:]
json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(len(out))
