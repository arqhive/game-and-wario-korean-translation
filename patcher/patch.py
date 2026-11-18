# -*- coding: utf-8 -*-
"""게임앤와리오(Wii U, 일본판) 한글 패치 적용기 — 가지고 있는 일본판 게임 파일로 한글판 파일을 만든다.

  패치하기.bat 에 게임 폴더를 끌어다 놓거나, 실행한 뒤 경로를 입력한다.
  python patch.py <게임 폴더(content 가 들어 있는 폴더) 또는 content 폴더>

결과(원본 파일은 바뀌지 않는다):
  출력/sdcafiine/0005000010112D00/GameWarioKR/content/...   Wii U 실기(SDCafiine)용
  출력/cemu/GameWarioKR/                                     Cemu 그래픽팩용(같은 파일을 하드 링크로)

패치 데이터에는 원본 게임 데이터를 넣지 않는다. 파일마다 바뀐 부분(xdelta)만 담는다.
  fzip  FZIP 묶음: 풀어서 xdelta → zlib 6 으로 다시 묶음
  raw   그대로 xdelta
모든 결과는 기준 해시(SHA-1)와 대조한다.
"""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import traceback
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
PAYLOAD = os.path.join(HERE, 'payload')
XDELTA = os.path.join(HERE, 'bin', 'xdelta3.exe')
OUT = os.path.join(TOP, '출력')
TID = '0005000010112D00'
MOD = 'GameWarioKR'
PROBE = ('Common', 'Msg', 'JP_Japanese', 'msbt.warc.fzip')


def sha1(b):
    return hashlib.sha1(b).hexdigest()


def fzip_unpack(data):
    if data[:4] != b'FZIP':
        raise ValueError('FZIP 아님')
    out = zlib.decompress(data[8:])
    if len(out) != struct.unpack('>I', data[4:8])[0]:
        raise ValueError('FZIP 크기 불일치')
    return out


def fzip_pack(data):
    return b'FZIP' + struct.pack('>I', len(data)) + zlib.compress(data, 6)


def find_content(arg):
    """게임 폴더·content·그 안의 폴더 어느 것을 줘도 content 폴더를 찾는다."""
    arg = os.path.abspath(arg.strip().strip('"'))
    for cand in (arg, os.path.join(arg, 'content'), os.path.dirname(arg), os.path.dirname(os.path.dirname(arg)),
                 os.path.dirname(os.path.dirname(os.path.dirname(arg)))):
        if os.path.isfile(os.path.join(cand, *PROBE)):
            return cand
    return None


def xdelta_apply(src, delta, tmp):
    a, d, o = (os.path.join(tmp, n) for n in ('src', 'delta', 'out'))
    open(a, 'wb').write(src)
    open(d, 'wb').write(delta)
    if os.path.exists(o):
        os.remove(o)
    r = subprocess.run([XDELTA, '-d', '-f', '-s', a, d, o], capture_output=True)
    if r.returncode != 0:
        raise RuntimeError('xdelta3 실패: %s' % r.stderr.decode('utf-8', 'replace'))
    return open(o, 'rb').read()


def make(entry, orig, tmp):
    delta = open(os.path.join(PAYLOAD, entry['data']), 'rb').read()
    if entry['kind'] == 'raw':
        return xdelta_apply(orig, delta, tmp)
    if entry['kind'] == 'fzip':
        return fzip_pack(xdelta_apply(fzip_unpack(orig), delta, tmp))
    raise ValueError(entry['kind'])


def link_or_copy(src, dst):
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def main():
    man = json.load(open(os.path.join(PAYLOAD, 'manifest.json'), encoding='utf-8'))
    print('게임앤와리오 한글 패치 %s\n' % man['version'])
    arg = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].strip() else None
    if not arg:
        print('일본판 「ゲーム&ワリオ」 게임 폴더(content 폴더가 들어 있는 폴더) 경로를 입력하세요.\n'
              '폴더를 이 창에 끌어다 놓아도 됩니다.')
        arg = input('> ')
    src = find_content(arg)
    if not src:
        print('[오류] %s 가 있는 content 폴더를 찾지 못했습니다: %s' % ('\\'.join(PROBE), arg))
        return 1
    print('원본 content 폴더: %s\n' % src)
    files = man['files']
    print('[1/3] 원본 확인')
    origs = {}
    for e in files:
        p = os.path.join(src, *e['path'].split('/'))
        if not os.path.isfile(p):
            print('[오류] 원본에 %s 가 없습니다.' % e['path'])
            return 1
        b = open(p, 'rb').read()
        if len(b) != e['src_size'] or sha1(b) != e['src_sha1']:
            print('[오류] %s 가 일본판 원본과 다릅니다(이미 패치했거나 다른 판).' % e['path'])
            return 1
        origs[e['path']] = b
    print('  %d개 파일 일치' % len(files))
    print('\n[2/3] 한글판 만들기')
    base = os.path.join(OUT, 'sdcafiine', TID, MOD, 'content')
    tmp = tempfile.mkdtemp(prefix='gw_ko_')
    t0 = time.time()
    try:
        for i, e in enumerate(files, 1):
            data = make(e, origs[e['path']], tmp)
            if sha1(data) != e['out_sha1']:
                print('[오류] %s 결과가 기준과 다릅니다. 패치 파일이 손상됐을 수 있습니다.' % e['path'])
                return 1
            dst = os.path.join(base, *e['path'].split('/'))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, 'wb').write(data)
            print('  [%2d/%d] %s' % (i, len(files), e['path']))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('  %d개 파일 결과 확인 일치 (%.0f초)' % (len(files), time.time() - t0))
    print('\n[3/3] Cemu 그래픽팩')
    gp = os.path.join(OUT, 'cemu', MOD)
    os.makedirs(gp, exist_ok=True)
    for f in ('rules.txt', 'patches.txt'):
        shutil.copyfile(os.path.join(HERE, f), os.path.join(gp, f))
    for e in files:
        dst = os.path.join(gp, 'content', *e['path'].split('/'))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        link_or_copy(os.path.join(base, *e['path'].split('/')), dst)
    print('  %s' % gp)
    print('\n완료.\n  Wii U(SDCafiine): 출력\\sdcafiine 폴더 안의 내용을 SD 카드 wiiu\\sdcafiine\\ 에 복사합니다.'
          '\n  Cemu: 출력\\cemu\\%s 폴더를 Cemu 의 graphicPacks 폴더에 넣고 그래픽팩에서 켭니다.' % MOD)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\n중단했습니다.')
        sys.exit(1)
    except Exception:
        traceback.print_exc()
        print('[오류] 예상하지 못한 문제가 생겼습니다.')
        sys.exit(1)
