# -*- coding: utf-8 -*-
"""배포용 패처 꾸리기 — 빌드본과 원본을 파일마다 비교해 바뀐 부분(xdelta)만 담는다(데빌즈 서드 패처와 같은 방식).

  python -I tools/gw_build.py
  python -I tools/make_patcher.py v0.9 [--python <내장 파이썬 폴더>] [--xdelta <xdelta3.exe>]

출력: work/release/ASAJ_KPatch_<버전>/      패처 폴더(패치하기.bat · python · patcher · licenses · README_KO.txt)
      work/release/ASAJ_KPatch_<버전>.zip  (릴리즈 이름 규칙 [게임 코드]_KPatch_[버전])
패치 데이터에 원본 게임 데이터는 넣지 않는다: FZIP 은 풀어서 xdelta 를 만들고, 적용할 때 zlib 6 으로 다시 묶는다.
만든 뒤 패처와 같은 계산(patcher/patch.py 의 make)을 내장 파이썬으로 돌려 빌드본과 해시가 같은지 확인한다
(zlib 버전이 다르면 다시 묶은 결과가 달라질 수 있어서).
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fzip  # noqa: E402

GAME = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]', 'content')
BUILT = os.path.join(ROOT, 'work', 'build', 'full', 'sd', 'wiiu', 'sdcafiine', '0005000010112D00', 'GameWarioKR', 'content')
REL = os.path.join(ROOT, 'work', 'release')
PY_DEFAULT = 'G:/KoreanTranslation/[Wii U] 환영이문록/work/python_embed'
XD_DEFAULT = 'G:/KoreanTranslation/[N3DS] 파이어 엠블렘 무쌍/tools/bin/xdelta3.exe'

VERIFY = r'''
import hashlib, json, os, sys
sys.path.insert(0, sys.argv[1])
import patch
man = json.load(open(os.path.join(patch.PAYLOAD, 'manifest.json'), encoding='utf-8'))
game, built = sys.argv[2], sys.argv[3]
import tempfile
tmp = tempfile.mkdtemp()
bad = 0
for e in man['files']:
    orig = open(os.path.join(game, *e['path'].split('/')), 'rb').read()
    out = patch.make(e, orig, tmp)
    ok = hashlib.sha1(out).hexdigest() == e['out_sha1'] == hashlib.sha1(open(os.path.join(built, *e['path'].split('/')), 'rb').read()).hexdigest()
    bad += not ok
print('VERIFY', len(man['files']), 'bad', bad)
'''


def sha1(b):
    return hashlib.sha1(b).hexdigest()


def xdelta_make(xd, old, new, tmp):
    a, b, d = (os.path.join(tmp, n) for n in ('old', 'new', 'delta'))
    open(a, 'wb').write(old)
    open(b, 'wb').write(new)
    if os.path.exists(d):
        os.remove(d)
    subprocess.run([xd, '-e', '-9', '-f', '-s', a, b, d], check=True, capture_output=True)
    return open(d, 'rb').read()


def main():
    ver = sys.argv[1]
    py = sys.argv[sys.argv.index('--python') + 1] if '--python' in sys.argv else PY_DEFAULT
    xd = sys.argv[sys.argv.index('--xdelta') + 1] if '--xdelta' in sys.argv else XD_DEFAULT
    assert os.path.isfile(os.path.join(py, 'python.exe')), '내장 파이썬이 없음: %s' % py
    assert os.path.isfile(xd), 'xdelta3 가 없음: %s' % xd
    name = 'ASAJ_KPatch_%s' % ver
    top = os.path.join(REL, name)
    if os.path.exists(top):
        shutil.rmtree(top)
    pdir = os.path.join(top, 'patcher')
    pay = os.path.join(pdir, 'payload')
    os.makedirs(pay)
    os.makedirs(os.path.join(pdir, 'bin'))
    shutil.copyfile(xd, os.path.join(pdir, 'bin', 'xdelta3.exe'))
    for f in ('patch.py', 'rules.txt', 'patches.txt'):
        shutil.copyfile(os.path.join(ROOT, 'patcher', f), os.path.join(pdir, f))

    rels = sorted(os.path.relpath(os.path.join(dp, f), BUILT).replace(os.sep, '/')
                  for dp, _, fs in os.walk(BUILT) for f in fs)
    man = dict(version=ver, files=[])
    tmp = tempfile.mkdtemp(prefix='gw_mk_')
    total = 0
    try:
        for i, rel in enumerate(rels):
            new = open(os.path.join(BUILT, *rel.split('/')), 'rb').read()
            orig = open(os.path.join(GAME, *rel.split('/')), 'rb').read()
            kind = 'fzip' if orig[:4] == b'FZIP' else 'raw'
            e = dict(path=rel, kind=kind, src_size=len(orig), src_sha1=sha1(orig), out_sha1=sha1(new), data='%02d.bin' % i)
            if kind == 'fzip':
                assert fzip.pack(fzip.unpack(new)) == new, ('다시 묶으면 빌드본과 다름', rel)
                d = xdelta_make(xd, fzip.unpack(orig), fzip.unpack(new), tmp)
            else:
                d = xdelta_make(xd, orig, new, tmp)
            open(os.path.join(pay, e['data']), 'wb').write(d)
            man['files'].append(e)
            total += len(d)
            print('%-58s %-4s 원본 %9d · 패치 데이터 %9d' % (rel, kind, len(orig), len(d)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    json.dump(man, open(os.path.join(pay, 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('파일', len(rels), '· 패치 데이터 합계', total)

    bat = open(os.path.join(ROOT, 'patcher', '패치하기.bat'), 'rb').read().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    open(os.path.join(top, '패치하기.bat'), 'wb').write(bat)
    shutil.copytree(py, os.path.join(top, 'python'), ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(os.path.join(ROOT, 'patcher', 'licenses'), os.path.join(top, 'licenses'))
    readme = open(os.path.join(ROOT, 'patcher', 'README_KO.txt'), encoding='utf-8').read().replace('{VER}', ver)
    open(os.path.join(top, 'README_KO.txt'), 'w', encoding='utf-8', newline='\r\n').write(readme)

    # 내장 파이썬(배포본과 같은 zlib)으로 패처 계산을 돌려 빌드본과 같은지 확인
    vp = os.path.join(tempfile.gettempdir(), 'gw_verify_patch.py')
    open(vp, 'w', encoding='utf-8').write(VERIFY)
    r = subprocess.run([os.path.join(top, 'python', 'python.exe'), '-I', vp, pdir, GAME, BUILT],
                       capture_output=True, text=True, encoding='utf-8')
    print(r.stdout.strip(), r.stderr.strip()[-500:])
    assert 'bad 0' in r.stdout, '패처 계산 결과가 빌드본과 다름'

    zp = os.path.join(REL, name + '.zip')
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for dp, _, fs in os.walk(top):
            for f in sorted(fs):
                fp = os.path.join(dp, f)
                z.write(fp, os.path.relpath(fp, REL).replace(os.sep, '/'))
    print('%s %.1fMB' % (os.path.basename(zp), os.path.getsize(zp) / 1e6))


if __name__ == '__main__':
    main()
