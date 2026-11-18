"""번역 작업 도구(translation/messages.json 의 ko 칸).

  show <파일.msbt> [시작idx] [끝idx]   원문(후리가나는 漢字《よみ》로 풀어 보임)·북미판·창 한도를 찍는다
  put <묶음.json>                      {"파일.msbt:idx": "번역", ...} 를 넣는다. 넣기 전에 검사:
                                         - 후리가나 {0:0:..} 를 뺀 태그가 원문과 같은 순서·같은 값인지
                                         - 창 넘침(check_overflow 와 같은 함수)
                                       하나라도 걸리면 그 칸은 넣지 않고 이유를 찍는다(--force 로 넘침만 무시).
                                       단 상대 한도(원문·북미판 길이로 잰 칸, 실제 창 폭 아님)의 넘침은 참고로만
                                       찍고 넣는다(11/19 사용자 결정). 상자 한도·태그·폰트 검사는 그대로 막는다.
  stat                                 파일별 번역 진행
  get <파일.msbt> [시작] [끝]          넣은 번역을 원문과 나란히 다시 찍는다(넣은 뒤 대조용)
후리가나: 한국어에는 읽기 표시가 없으므로 번역문에서는 뺀다(태그 검사에서도 제외).
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
MSG = os.path.join(ROOT, 'translation', 'messages.json')
TAG = re.compile(r'\{[^}]*\}')
RUBY = re.compile(r'\{0:0:([0-9a-f]{4})([0-9a-f]{4})([0-9a-f]*)\}')


def load():
    return json.load(open(MSG, encoding='utf-8'))


def save(j):
    s = json.dumps(j, ensure_ascii=False, indent=1)
    tmp = MSG + '.tmp'
    open(tmp, 'w', encoding='utf-8').write(s)
    os.replace(tmp, MSG)


def readable(t):
    out, pos = [], 0
    for m in RUBY.finditer(t):
        out.append(t[pos:m.start()])
        n = int(m.group(1), 16) // 2
        r = bytes.fromhex(m.group(3)).decode('utf-16-be', 'replace')
        rest = t[m.end():]
        # 바탕 글자 n 개(태그 건너뜀)
        base, k, i = '', 0, 0
        while i < len(rest) and k < n:
            if rest[i] == '{':
                j = rest.index('}', i)
                base += rest[i:j + 1]
                i = j + 1
                continue
            base += rest[i]
            k += 1
            i += 1
        out.append('%s《%s》' % (base, r))
        pos = m.end() + i
    out.append(t[pos:])
    return ''.join(out)


PUA = re.compile(r'[-]')
PUA_MARK = re.compile(r'⟦([0-9A-Fa-f]{4})⟧')


def show_pua(t):
    """버튼 그림 글자(사용 영역 문자)는 화면에서 안 보이므로 ⟦E002⟧ 꼴로 찍는다."""
    return PUA.sub(lambda m: '⟦%04X⟧' % ord(m.group()), t)


def from_mark(t):
    return PUA_MARK.sub(lambda m: chr(int(m.group(1), 16)), t)


def tags(t):
    """태그(후리가나 빼고) + 버튼 그림 글자, 나온 순서대로."""
    return [x for x in re.findall(r'\{[^}]*\}|[-]', t) if not x.startswith('{0:0:')]


def limits():
    p = os.path.join(ROOT, 'work', 'survey', 'window_limits.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def lim_str(L):
    if not L:
        return '한도 없음'
    if L['kind'] == 'box':
        return '상자 ' + ', '.join('%s %dpx×%d줄' % (b['font'], b['w'], b['max_lines']) for b in L['boxes'][:3])
    return '상대(원문·북미판) %dpx×%d줄' % (L['limit_w'], L['limit_lines'])


def rng(j, fn, a, b):
    return [e for e in j if e['file'] == fn and a <= e['idx'] <= b]


SPLIT = re.compile(r'(\{[^}]*\}|[-])')


def slots(ja):
    """후리가나를 뺀 원문을 태그·버튼 그림과 글자 칸으로 나눈다 -> (조각 목록, 글자 칸 번호들)."""
    t = RUBY.sub('', ja)
    parts = [p for p in SPLIT.split(t) if p != '']
    idx = [i for i, p in enumerate(parts) if not SPLIT.fullmatch(p) and p.strip()]
    return parts, idx


def main():
    cmd = sys.argv[1]
    if cmd == 'seg':
        # seg <파일> <시작> <끝>: 글자 칸만 번호 매겨 찍는다(공백뿐인 칸은 그대로 둠)
        fn, a, b = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
        for e in rng(load(), fn, a, b):
            if e['empty']:
                continue
            parts, idx = slots(e['ja'])
            print('■ %s:%d %s' % (e['file'], e['idx'], ' | '.join('[%d]%s' % (n, parts[i].replace('\n', '⏎')) for n, i in enumerate(idx))))
        return
    if cmd == 'putseg':
        # putseg <묶음.json>: {"파일:idx": ["칸0 번역", "칸1 번역", ...]} → 태그는 원문 그대로, 글자 칸만 바꿔 put 과 같은 검사
        batch = json.load(open(sys.argv[2], encoding='utf-8'))
        by = {e['id']: e for e in load()}
        out = {}
        for k, segs in batch.items():
            parts, idx = slots(by[k]['ja'])
            if len(segs) != len(idx):
                print('칸 수 다름', k, len(idx), '→', len(segs))
                continue
            for n, i in enumerate(idx):
                s = segs[n]
                if s.startswith('⌫'):
                    # 바로 앞 글자 칸까지 사이에 있는 공백뿐인 조각을 지운다(「이름 의」 → 「이름의」)
                    s = s[1:]
                    j2 = i - 1
                    while j2 >= 0 and (SPLIT.fullmatch(parts[j2]) or not parts[j2].strip()):
                        if not SPLIT.fullmatch(parts[j2]):
                            parts[j2] = ''
                        j2 -= 1
                parts[i] = s
            out[k] = show_pua(''.join(parts))
        tmp = sys.argv[2] + '.full.json'
        json.dump(out, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        sys.argv = [sys.argv[0], 'put', tmp] + sys.argv[3:]
        cmd = 'put'
    if cmd in ('show', 'get'):
        fn = sys.argv[2]
        a = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        b = int(sys.argv[4]) if len(sys.argv) > 4 else 10 ** 9
        L = limits()
        for e in rng(load(), fn, a, b):
            if e['empty']:
                continue
            k = '%s|%s' % (e['file'], e['label'])
            print('■ %s:%d [%s] %s' % (e['file'], e['idx'], e['label'], lim_str(L.get(k))))
            print('  JA:', show_pua(readable(e['ja'])).replace('\n', '⏎'))
            print('  EN:', show_pua(e['en'] or '').replace('\n', '⏎'))
            if cmd == 'get' or e['ko']:
                print('  KO:', show_pua(e['ko']).replace('\n', '⏎'))
        return
    if cmd == 'put':
        import check_overflow as co
        batch = json.load(open(sys.argv[2], encoding='utf-8'))
        force = '--force' in sys.argv
        j = load()
        by = {e['id']: e for e in j}
        L = limits()
        ok, bad = 0, 0
        for k, ko in batch.items():
            ko = from_mark(ko).replace('⏎', '\n')
            e = by.get(k)
            if e is None:
                print('없는 칸', k)
                bad += 1
                continue
            if tags(e['ja']) != tags(ko):
                print('태그 다름', k, show_pua(' '.join(tags(e['ja']))), '→', show_pua(' '.join(tags(ko))))
                bad += 1
                continue
            lk = '%s|%s' % (e['file'], e['label'])
            prob = co.check(lk, ko, L[lk]) if lk in L else []
            # 상자 폰트(글자 그림 폰트)에 없는 한글 밖 글자(예: Serif38 의 반각 !)
            if lk in L and L[lk]['kind'] == 'box':
                import window_limits as wl
                plain = TAG.sub('', ko)
                for b in L[lk]['boxes']:
                    if b['font'] == 'CafeStd':
                        continue
                    cm = wl.font(b['font']).f.charmap
                    # ‘’“” 는 게임 폰트에 없지만 빌드 때 한글과 같이 새 글꼴에서 넣는다(11/18 결정)
                    # 원문에도 있는 글자는 원문 그대로 나오므로 제외({0:1:..} 글꼴 바꿈 태그로 다른 폰트일 수 있음)
                    # 반각(ASCII)도 폰트에 없으면 빌드 때 그려 넣는다(11/19, gw_build.build_fonts) → 검사에서 뺀다
                    miss = sorted({c for c in plain if c not in '\n‘’“”' and not 0xAC00 <= ord(c) <= 0xD7A3
                                   and ord(c) > 0x7F
                                   and ord(c) not in cm and c not in e['ja']})
                    if miss:
                        prob = prob + ['%s 폰트에 없는 글자 %s' % (b['font'], ''.join(miss))]
            # 상대 한도는 원문·북미판 길이일 뿐 실제 창 폭이 아니다 → 참고로만(11/19 사용자 결정)
            if prob and lk in L and L[lk]['kind'] == 'rel':
                print('참고(원문보다 김)', k, prob[:2], show_pua(ko).replace('\n', '⏎'))
                prob = []
            if prob and not force:
                print('넘침', k, prob[:2], show_pua(ko).replace('\n', '⏎'))
                bad += 1
                continue
            e['ko'] = ko
            ok += 1
        save(j)
        print('넣음 %d, 못 넣음 %d' % (ok, bad))
        return
    if cmd == 'stat':
        import collections
        j = load()
        t, d = collections.Counter(), collections.Counter()
        for e in j:
            if e['empty']:
                continue
            t[e['file']] += 1
            d[e['file']] += bool(e['ko'])
        for f in sorted(t):
            print('%-24s %4d / %4d' % (f, d[f], t[f]))
        print('합계 %d / %d' % (sum(d.values()), sum(t.values())))


if __name__ == '__main__':
    main()
