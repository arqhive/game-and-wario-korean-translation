"""게임 폰트 4종의 머리 정보와 시트 0 앞부분을 그림으로 뽑는다(2단계 준비).

BC4: tools/font_atlas.py(환영이문록에서 복사: 시트마다 swizzle (i%4)<<9, 상하 반전).
BC5: 블록 16바이트 = 빨강 BC4 8바이트 + 초록 BC4 8바이트로 보고 두 채널을 따로 그린다.
사용: python -I tools/gw_font_peek.py
결과: work/font_peek/<폰트>_s0.png (BC5 는 _R·_G), 화면에 머리 정보
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
import bffnt_tool as bt  # noqa: E402
import font_atlas as fa  # noqa: E402
import fzip  # noqa: E402
import gtx_lib  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]', 'content', 'Common', 'Font')
OUT = os.path.join(ROOT, 'work', 'font_peek')


def bc5_map(w, h, swz):
    """BC5(블록 16바이트) 저장 순서 ↔ 선형 순서. BC4 매핑과 달라서(bpp 128) 따로 뽑는다."""
    import addrlib
    n = (w // 4) * (h // 4)
    probe = np.repeat(np.arange(n, dtype='>u8'), 2).tobytes()   # 블록마다 16바이트 = 번호 2번
    lin = addrlib.deswizzle(w, h, h, 0x35, 4, swz, w // 4, 128, probe)
    return np.frombuffer(lin, '>u8')[::2].astype(np.int64)


def bc5_sheet(data, w, h, i):
    """BC5 시트 → (R, G) 그림. 저장 순서 매핑은 BC4 와 같은 블록 단위로 본다(블록 16바이트)."""
    m = bc5_map(w, h, fa.sheet_swizzle(i))
    st = np.frombuffer(data, np.uint8).reshape(-1, 16)
    lin = st[m].reshape(h // 4, w // 4, 16)
    r = gtx_lib.bc4_decode_blocks(np.ascontiguousarray(lin[..., :8]))[::-1]
    g = gtx_lib.bc4_decode_blocks(np.ascontiguousarray(lin[..., 8:]))[::-1]
    return r, g


def main():
    os.makedirs(OUT, exist_ok=True)
    for n in ('Caption50L_JP', 'Caption64L_JP', 'Exp50_JP', 'Serif38_JP'):
        f = bt.BFFNT(fzip.unpack(open(os.path.join(FONT, n + '.bffnt.fzip'), 'rb').read()))
        kanji_w = [f.widths[g] for c, g in f.charmap.items() if 0x4E00 <= c <= 0x9FFF and g in f.widths][:3]
        print(n, 'fmt', hex(f.format), 'cell', f.cell_w, f.cell_h, 'sheets', f.num_sheets, 'sheet', f.sheet_w, f.sheet_h,
              'cols/rows', f.columns, f.rows, 'baseline', f.baseline, 'height', f.height, 'ascent', f.ascent,
              'line_feed', f.line_feed, 'glyphs', len(f.charmap), 'cmaps', [(c.code_begin, c.code_end, c.method) for c in f.cmaps][:6],
              '한자 폭 예', kanji_w)
        if f.format & 0xff in (0x0c, 0x34) or f.format == 0x0c:
            pass
        try:
            if 'Serif' in n:
                r, g = bc5_sheet(f.sheets[0], f.sheet_w, f.sheet_h, 0)
                Image.fromarray(r[:300, :600]).save(os.path.join(OUT, n + '_s0_R.png'))
                Image.fromarray(g[:300, :600]).save(os.path.join(OUT, n + '_s0_G.png'))
            else:
                im = fa.decode_sheet(f.sheets[0], f.sheet_w, f.sheet_h, 0)
                Image.fromarray(im[:300, :600]).save(os.path.join(OUT, n + '_s0.png'))
        except Exception as ex:  # noqa: BLE001
            print('  그림 실패', ex)


if __name__ == '__main__':
    main()
