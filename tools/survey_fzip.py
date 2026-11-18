"""모든 .fzip 을 풀고, 다시 묶은 결과가 원본과 같은지 확인한다(0·1단계).

사용: python -I tools/survey_fzip.py [판본 폴더 이름]
결과: work/survey/fzip.json, 화면에 형식별 개수·재압축 일치 수
"""
import collections
import json
import os
import sys as _sys
_sys.stdout.reconfigure(encoding="utf-8")
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fzip  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else 'Game Wario [Game] [0005000010112d00]'
    base = os.path.join(ROOT, folder, 'content')
    rows, magic, same, bad = [], collections.Counter(), 0, []
    for dp, dn, fn in os.walk(base):
        for f in fn:
            if not f.lower().endswith('.fzip'):
                continue
            p = os.path.join(dp, f)
            raw = open(p, 'rb').read()
            try:
                d = fzip.unpack(raw)
            except Exception as e:  # noqa: BLE001
                bad.append((p, str(e)))
                continue
            m = d[:4]
            mk = m.decode('latin1') if all(32 <= c < 127 for c in m) else m.hex()
            magic[mk] += 1
            ok = fzip.pack(d) == raw
            same += ok
            rows.append({'path': os.path.relpath(p, base).replace('\\', '/'),
                         'zsize': len(raw), 'size': len(d), 'magic': mk, 'repack_same': ok})
    os.makedirs(os.path.join(ROOT, 'work', 'survey'), exist_ok=True)
    out = os.path.join(ROOT, 'work', 'survey', 'fzip.json')
    s = json.dumps(rows, ensure_ascii=False, indent=1)
    open(out, 'w', encoding='utf-8').write(s)
    print('fzip', len(rows), '재압축 같음', same, '실패', len(bad), bad[:5])
    print('안쪽 형식', dict(magic))


if __name__ == '__main__':
    main()
