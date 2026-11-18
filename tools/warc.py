"""게임앤와리오 자체 묶음 WARC 읽기·쓰기.

구조(2026-11-12 역산, 빅엔디언):
  0x00 'WARC', 0x04 0x20, 0x0C 전체 크기, 0x2C 파일 수
  항목: 0x40 부터 0x20바이트씩
    +0x00 이름 길이, +0x04 이름 상대 위치(+0x04 기준), +0x08 부모(상대), +0x0C 0x20,
    +0x10 0, +0x14 크기, +0x18 0, +0x1C 데이터 상대 위치(+0x18 기준)
쓰기: 머리·항목표·이름표는 원본 바이트 그대로 두고, 데이터를 원본 순서·원본 정렬로 다시 놓는다.
"""
import struct


def read(d: bytes):
    assert d[:4] == b'WARC', d[:4]
    cnt = struct.unpack('>I', d[0x2C:0x30])[0]
    ents = []
    for i in range(cnt):
        o = 0x40 + i * 0x20
        nlen, nrel = struct.unpack('>II', d[o:o + 8])
        size = struct.unpack('>I', d[o + 0x14:o + 0x18])[0]
        drel = struct.unpack('>I', d[o + 0x1C:o + 0x20])[0]
        name = d[o + 4 + nrel:o + 4 + nrel + nlen].decode('ascii')
        start = o + 0x18 + drel
        ents.append({'i': i, 'o': o, 'name': name, 'start': start, 'size': size})
    return ents


def detect_align(d: bytes, ents):
    """데이터 시작 위치가 모두 나누어떨어지는 가장 큰 2의 거듭제곱(최대 0x10000).
    msbt·script 는 0x20, 그림(gtx) 묶음은 0x2000."""
    a = 0x10000
    while a > 1 and any(e['start'] % a for e in ents):
        a //= 2
    return a


def write(d: bytes, rep: dict = None, align: int = None) -> bytes:
    """rep = {이름: 새 바이트}. 나머지는 원본 그대로."""
    rep = rep or {}
    ents = read(d)
    if align is None:
        align = detect_align(d, ents)
    order = sorted(ents, key=lambda e: e['start'])
    first = order[0]['start']
    out = bytearray(d[:first])
    for e in order:
        while len(out) % align:
            out += b'\0'
        data = rep.get(e['name'], d[e['start']:e['start'] + e['size']])
        o = e['o']
        struct.pack_into('>I', out, o + 0x14, len(data))
        struct.pack_into('>I', out, o + 0x1C, len(out) - (o + 0x18))
        out += data
    # 원본 꼬리(마지막 데이터 뒤 채움)
    last = order[-1]
    tail = len(d) - (last['start'] + last['size'])
    if not rep:
        out += d[len(d) - tail:] if tail else b''
    else:
        while len(out) % align:
            out += b'\0'
    # 0x0C 는 파일 길이와 정확히 같지 않다(msbt.warc: 0x91240 vs 0x91230) → 원본 차이만큼 유지
    orig = struct.unpack('>I', d[0x0C:0x10])[0]
    struct.pack_into('>I', out, 0x0C, orig + len(out) - len(d))
    return bytes(out)
