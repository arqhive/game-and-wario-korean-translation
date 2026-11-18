"""전체 빌드(work/build/full)에서 바뀐 파일을 하나씩만 넣은 SDCafiine 시험 팩을 만든다(실기 에러 원인 좁히기).

출력: work/build/split/sd/wiiu/sdcafiine/0005000010112D00/<팩 이름>/content/...
사용: python -I tools/gw_split_packs.py   (먼저 gw_build.py 로 full 빌드가 있어야 함)
"""
import hashlib
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TITLE = '0005000010112D00'
FULL = os.path.join(ROOT, 'work', 'build', 'full', 'sd', 'wiiu', 'sdcafiine', TITLE, 'GameWarioKR', 'content')
OUT = os.path.join(ROOT, 'work', 'build', 'split')
F = 'Common/Font/'
PACKS = {
    'KR1_Msg': ['Common/Msg/JP_Japanese/msbt.warc.fzip'],
    'KR2_CafeTxt': [F + 'CafeStd_JP.txt'],
    'KR3_Cap50L': [F + 'Caption50L_JP.bffnt.fzip'],
    'KR4_Cap64L': [F + 'Caption64L_JP.bffnt.fzip'],
    'KR5_Exp50': [F + 'Exp50_JP.bffnt.fzip'],
    'KR6_Serif38': [F + 'Serif38_JP.bffnt.fzip'],
}


def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()


def main():
    allf = sorted(os.path.relpath(os.path.join(r, f), FULL).replace('\\', '/') for r, _, fs in os.walk(FULL) for f in fs)
    used = sorted(x for v in PACKS.values() for x in v)
    assert allf == used, ('full 빌드 파일과 팩 목록이 다름', allf, used)
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    for name, files in PACKS.items():
        for rel in files:
            s = os.path.join(FULL, rel)
            d = os.path.join(OUT, 'sd', 'wiiu', 'sdcafiine', TITLE, name, 'content', rel)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copyfile(s, d)
            assert md5(s) == md5(d)
            print(name, rel, os.path.getsize(d), md5(d))


if __name__ == '__main__':
    main()
