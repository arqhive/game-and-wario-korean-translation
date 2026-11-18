"""1단계 무변경 왕복 검사: WARC·MSBT·SARC(lytarc).

사용: python -I tools/roundtrip.py
- WARC 5개: warc.write(원본) == 원본
- MSBT 54개: 문자열로 풀고(msbt_text_to_str) 다시 묶은(str_to_msbt → msbt_write) 결과 == 원본
- SARC 128개: sarc_write(원본 순서·원본 정렬 추정) == 원본
일부러 바꾼 예(MSBT 한 줄에 글자 추가)가 「다름」으로 잡히는지도 확인한다.
"""
import os
import sys as _sys
_sys.stdout.reconfigure(encoding="utf-8")
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fzip  # noqa: E402
import nlib  # noqa: E402
import warc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]', 'content')


def sarc_align_guess(data):
    """원본 파일별 시작 위치에서 각 파일 정렬값 추정."""
    info, files = nlib.sarc_read(data)
    lay = dict(nlib.sarc_layout(data))
    al = {}
    for n, b, h in files:
        s = lay[n] + info['data_off']
        a = 0x2000
        while a > 1 and s % a:
            a //= 2
        al[n] = a
    return info, files, al


def sarc_roundtrip(data):
    info, files, al = sarc_align_guess(data)
    # 원본 정렬값을 그대로 쓰되, 크게 잡힌 정렬이 실제 원본 위치와 맞는지는 결과 비교로 판단
    order = sorted(nlib.sarc_layout(data), key=lambda x: x[1])
    name_b = {n: b for n, b, h in files}
    # 실제 배치 재현: 앞 파일 끝에서 다음 시작까지 최소 정렬
    lay = dict(order)
    need = {}
    prev_end = None
    for n, s in order:
        if prev_end is None:
            need[n] = 4
        else:
            a = 1
            while True:
                nxt = (prev_end + info['data_off'] + a - 1) // a * a - info['data_off']
                if nxt == s:
                    break
                a *= 2
                if a > 0x10000:
                    a = None
                    break
            need[n] = a or 4
        prev_end = s + len(name_b[n])
    out = nlib.sarc_write([(n, b) for n, b, h in files], mult=info['mult'], endian=info['endian'],
                          data_off=info['data_off'], align=lambda n, b: need[n], ver=info['ver'])
    return out, need


def main():
    res = {'warc': [0, 0], 'msbt': [0, 0], 'sarc': [0, 0]}
    fails = []
    msbt_samples = []
    for dp, dn, fn in os.walk(BASE):
        for f in sorted(fn):
            if not f.endswith('.fzip'):
                continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, BASE)
            d = fzip.unpack(open(p, 'rb').read())
            if d[:4] == b'WARC':
                res['warc'][1] += 1
                if warc.write(d) == d:
                    res['warc'][0] += 1
                else:
                    fails.append(('warc', rel))
                for e in warc.read(d):
                    if not e['name'].endswith('.msbt'):
                        continue
                    b = d[e['start']:e['start'] + e['size']]
                    m = nlib.msbt_read(b)
                    en = m['endian']
                    strs = [nlib.msbt_text_to_str(t, en) for t in m['texts']]
                    raw = [nlib.str_to_msbt(s, en) for s in strs]
                    out = nlib.msbt_write(m, raw)
                    res['msbt'][1] += 1
                    if out == b:
                        res['msbt'][0] += 1
                    else:
                        fails.append(('msbt', rel + ':' + e['name']))
                    if not msbt_samples:
                        msbt_samples.append((m, strs, b))
            elif d[:4] == b'SARC':
                res['sarc'][1] += 1
                out, need = sarc_roundtrip(d)
                if out == d:
                    res['sarc'][0] += 1
                else:
                    fails.append(('sarc', rel))
    for k, (ok, n) in res.items():
        print(f'{k}: 같음 {ok} / {n}')
    print('다름 목록(앞 10개):', fails[:10], '총', len(fails))
    # 일부러 틀린 예
    m, strs, b = msbt_samples[0]
    en = m['endian']
    strs2 = list(strs)
    idx = next(i for i, s in enumerate(strs2) if s)
    strs2[idx] = strs2[idx] + '가'
    out = nlib.msbt_write(m, [nlib.str_to_msbt(s, en) for s in strs2])
    print('틀린 예(한 줄에 「가」 추가) 다름으로 잡힘:', out != b)


if __name__ == '__main__':
    main()
