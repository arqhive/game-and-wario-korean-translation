"""survey_all.py 결과를 형식별로 집계한다.

사용: python -I tools/survey_summary.py
결과: 화면에 형식별 표(파일 수, 검사 방식, 목록 줄 수, 깨짐 아님 줄 수), work/survey/summary.json
"""
import collections
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, 'work', 'survey')


def main():
    files = {}
    kind = collections.Counter()
    for line in open(os.path.join(S, 'all_files.jsonl'), encoding='utf-8', newline='\n'):
        r = json.loads(line)
        if r.get('note', '').startswith('container'):
            continue
        ext = r['ext']
        if r.get('model_excluded'):
            k = '모델(검사 안 함)'
        elif r.get('sound_excluded'):
            k = '소리(검사 안 함)'
        elif r.get('media_count_only'):
            k = '영상(개수만)'
        elif r.get('broken_count_only'):
            k = '바이너리(깨짐은 개수만)'
        else:
            k = '전부 목록'
        files[r['path']] = (ext, k)
        kind[(ext, k)] += 1
    lines = collections.Counter()
    ok = collections.Counter()
    for line in open(os.path.join(S, 'strings.jsonl'), encoding='utf-8', newline='\n'):
        r = json.loads(line)
        key = files.get(r['path'], ('?', '?'))
        lines[key] += 1
        if not r['broken']:
            ok[key] += 1
    rows = sorted(kind.items(), key=lambda x: (-lines[x[0]], x[0]))
    print('형식\t검사\t잎 파일\t목록 줄\t깨짐 아님')
    out = []
    for (ext, k), n in rows:
        print(f'{ext}\t{k}\t{n}\t{lines[(ext, k)]}\t{ok[(ext, k)]}')
        out.append({'ext': ext, 'kind': k, 'files': n, 'lines': lines[(ext, k)], 'not_broken': ok[(ext, k)]})
    print('합계 잎 파일', sum(kind.values()), '목록 줄', sum(lines.values()))
    json.dump(out, open(os.path.join(S, 'summary.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
