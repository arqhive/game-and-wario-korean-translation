"""번역 넘침 검사(3단계 창 측정 결과 work/survey/window_limits.json 사용).

  상자 칸(kind=box): 그 대사가 들어가는 모든 글 상자마다 줄 폭(px) ≤ 상자 폭, 줄 수 ≤ 상자 줄 수. {1:0:} 폭 맞춤 구간은 폭 검사 생략.
  상대 칸(kind=rel, 코드가 넣는 칸으로 추정): 기준 폰트로 잰 줄 폭 ≤ max(원문, 북미판) 폭, 줄 수 ≤ max(원문, 북미판) 줄 수.
입력: translation/messages.json 의 ko (또는 인자로 준 JSON {"파일|라벨": 번역문} / [{file,label,ko}])
옵션: --self-test  원문을 번역문 자리에 넣어 통과 수를 보고, 일부러 긴 문장 하나가 잡히는지 확인
출력: 넘친 줄 목록 work/survey/overflow_report.txt, 종료 코드 = 넘친 수(최대 255)
사용: python -I tools/check_overflow.py [번역.json] [--self-test]
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import window_limits as wl  # noqa: E402

ROOT = os.path.dirname(HERE)


def load_tr(path):
    j = json.load(open(path, encoding='utf-8'))
    if isinstance(j, dict):
        return {k: v for k, v in j.items() if not k.startswith('_') and v}
    return {'%s|%s' % (r['file'], r['label']): r['ko'] for r in j if r.get('ko')}


def check(key, ko, L):
    bad = []
    if L['kind'] == 'box':
        for b in L['boxes']:
            ls = wl.lines_px(ko, wl.font(b['font']), b['fsize'], b['cspace'])
            if len(ls) > b['max_lines']:
                bad.append('%s %s: 줄 %d > %d' % (b['layout'], b['pane'], len(ls), b['max_lines']))
            if not b.get('fit') and '{1:0:}' not in ko:
                for i, (w, _) in enumerate(ls):
                    if w > b['w'] + 0.5:
                        bad.append('%s %s: %d줄 폭 %.0f > %.0f' % (b['layout'], b['pane'], i + 1, w, b['w']))
    else:
        ref = wl.font(L['ref_font'])
        ls = wl.lines_px(ko, ref, wl.ref_fsize(L['ref_font']), 0)
        if len(ls) > L['limit_lines']:
            bad.append('줄 %d > %d(원문·북미판)' % (len(ls), L['limit_lines']))
        for i, (w, _) in enumerate(ls):
            if w > L['limit_w'] + 0.5 and '{1:0:}' not in ko:     # 폭 맞춤 구간은 상자 칸처럼 폭 검사 생략
                bad.append('%d줄 폭 %.0f > %.0f(원문·북미판, 기준 %s)' % (i + 1, w, L['limit_w'], L['ref_font']))
    return bad


def main():
    lim = json.load(open(os.path.join(ROOT, 'work', 'survey', 'window_limits.json'), encoding='utf-8'))
    if '--self-test' in sys.argv:
        tr = {k: v['text'] for k, v in lim.items()}
        n_bad = sum(1 for k, t in tr.items() if check(k, t, lim[k]))
        print('원문을 넣어 검사: %d칸 중 넘침 %d칸 (상자 칸 %d, 상대 칸 %d)' % (
            len(tr), n_bad, sum(v['kind'] == 'box' for v in lim.values()), sum(v['kind'] == 'rel' for v in lim.values())))
        for k in ('Co.msbt|Btn0', 'Co_exp.msbt|Ar_00_1'):
            if k in lim:
                long = '아주 길고 긴 한국어 문장을 일부러 넣어서 넘치는지 보는 시험 문장입니다 ' * 3
                print('일부러 긴 문장', k, lim[k]['kind'], '→ 잡힘' if check(k, long, lim[k]) else '→ 못 잡음(!)', check(k, long, lim[k])[:2])
        return 0
    src = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else os.path.join(ROOT, 'translation', 'messages.json')
    tr = load_tr(src)
    bad, unknown = [], []
    for k, ko in tr.items():
        if k not in lim:
            unknown.append(k)
            continue
        for b in check(k, ko, lim[k]):
            bad.append((k, b, ko))
    out = os.path.join(ROOT, 'work', 'survey', 'overflow_report.txt')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('검사 %d칸, 넘침 %d건, 한도 모름 %d칸\n' % (len(tr), len(bad), len(unknown)))
        for k, b, ko in bad:
            f.write('%s | %s | %s\n' % (k, b, ko.replace('\n', '/')))
        for u in unknown:
            f.write('한도 모름 | %s\n' % u)
    print('검사 %d칸, 넘침 %d건, 한도 모름 %d칸 → %s' % (len(tr), len(bad), len(unknown), out))
    return min(len(bad), 255)


if __name__ == '__main__':
    sys.exit(main())
