"""RPX 에서 가져온 함수(import)를 부르는 곳을 찾아 그 앞 기계어를 풀어 보인다.

사용: python -I tools/rpx_calls.py <함수 이름> [앞 명령 수=24]
예:   python -I tools/rpx_calls.py OSGetSharedData
"""
import os
import struct
import sys
import zlib

sys.stdout.reconfigure(encoding='utf-8')
import capstone  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RPX = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]', 'code', 'Slate.rpx')


def sections(d):
    shoff = struct.unpack('>I', d[0x20:0x24])[0]
    shnum, shstr = struct.unpack('>HH', d[0x30:0x34])
    out = []
    for i in range(shnum):
        o = shoff + i * 40
        name, typ, flags, addr, off, size, link, info, align, entsize = struct.unpack('>10I', d[o:o + 40])
        raw = d[off:off + size] if typ != 8 else b''
        if flags & 0x08000000 and size >= 4:
            raw = zlib.decompress(raw[4:])
        out.append(dict(i=i, name=name, typ=typ, flags=flags, addr=addr, raw=raw, link=link, entsize=entsize))
    st = out[shstr]['raw']
    for s in out:
        s['name'] = st[s['name']:st.index(b'\0', s['name'])].decode()
    return out


def symbols(secs):
    res = {}
    for s in secs:
        if s['typ'] != 2:   # SHT_SYMTAB
            continue
        strtab = secs[s['link']]['raw']
        raw = s['raw']
        for k in range(0, len(raw), 16):
            nm, val, size, info, other, shndx = struct.unpack('>IIIBBH', raw[k:k + 16])
            if nm:
                n = strtab[nm:strtab.index(b'\0', nm)].decode('ascii', 'replace')
                res.setdefault(n, []).append((val, shndx))
    return res


def main():
    fn = sys.argv[1]
    back = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    d = open(RPX, 'rb').read()
    secs = sections(d)
    sym = symbols(secs)
    targets = [v for v, _ in sym.get(fn, [])]
    print(fn, '기호 주소', [hex(t) for t in targets])
    text = next(s for s in secs if s['name'] == '.text')
    base, raw = text['addr'], text['raw']
    md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
    calls = []
    for o in range(0, len(raw) - 3, 4):
        w = struct.unpack('>I', raw[o:o + 4])[0]
        if w >> 26 == 18 and w & 1:              # bl
            li = w & 0x03FFFFFC
            if li & 0x02000000:
                li -= 0x04000000
            tgt = li if w & 2 else base + o + li
            if tgt in targets:
                calls.append(base + o)
    # 가져온 함수는 기계어 안 점프 주소가 비어 있고 재배치(.rela.text)로 채워진다 → 재배치에서 찾는다
    for s in secs:
        if s['typ'] != 4 or s['name'] != '.rela.text':   # SHT_RELA
            continue
        symsec = secs[s['link']]
        strtab = secs[symsec['link']]['raw']
        for k in range(0, len(s['raw']), 12):
            off, info, add = struct.unpack('>IIi', s['raw'][k:k + 12])
            si = info >> 8
            nm = struct.unpack('>I', symsec['raw'][si * 16:si * 16 + 4])[0]
            n = strtab[nm:strtab.index(b'\0', nm)].decode('ascii', 'replace')
            if n == fn and off not in calls:
                calls.append(off)
    calls.sort()
    print('부르는 곳', len(calls))
    for c in calls:
        o = c - base
        s = max(0, o - back * 4)
        print('---- %08x' % c)
        for ins in md.disasm(raw[s:o + 8], base + s):
            print('  %08x  %-8s %s' % (ins.address, ins.mnemonic, ins.op_str))


if __name__ == '__main__':
    main()
