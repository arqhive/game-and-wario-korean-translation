"""FZIP 묶음 풀기·묶기.

형식: b'FZIP' + 원래 크기(4바이트 빅엔디언) + zlib 스트림.
원본 991개(일본판)는 파이썬 zlib 레벨 6으로 다시 묶으면 바이트까지 같다(2026-11-12 확인).
"""
import struct
import zlib

MAGIC = b'FZIP'
LEVEL = 6


def unpack(data: bytes) -> bytes:
    if data[:4] != MAGIC:
        raise ValueError('FZIP 아님')
    size = struct.unpack('>I', data[4:8])[0]
    out = zlib.decompress(data[8:])
    if len(out) != size:
        raise ValueError(f'크기 불일치 {len(out)} != {size}')
    return out


def pack(data: bytes, level: int = LEVEL) -> bytes:
    return MAGIC + struct.pack('>I', len(data)) + zlib.compress(data, level)
