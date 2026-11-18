"""폰트(BFFNT) 12개를 풀어 구조·칸 수·왕복을 본다.

사용: python -I tools/survey_fonts.py
결과: work/extract/Font/*.bffnt, 화면 표
"""
import os
import sys as _sys
_sys.stdout.reconfigure(encoding="utf-8")
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bffnt_tool  # noqa: E402
import fzip  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]', 'content', 'Common', 'Font')
OUT = os.path.join(ROOT, 'work', 'extract', 'Font')
FMT = {0: 'RGBA8', 1: 'RGB8', 2: 'RGB5A1', 3: 'RGB565', 4: 'RGBA4', 5: 'LA8', 6: 'LA4', 7: 'A4', 8: 'A8',
       9: 'BC1', 10: 'BC2', 11: 'BC3', 12: 'BC4', 13: 'BC5'}


def main():
    os.makedirs(OUT, exist_ok=True)
    print('폰트 | 셀 | 시트 수·크기 | 형식 | 칸/시트 | 전체 칸 | 글리프 | 빈 칸 | 한자 | 가나 | 한글 | 왕복')
    for f in sorted(os.listdir(SRC)):
        if not f.endswith('.bffnt.fzip'):
            continue
        d = fzip.unpack(open(os.path.join(SRC, f), 'rb').read())
        name = f[:-5]
        open(os.path.join(OUT, name), 'wb').write(d)
        ft = bffnt_tool.BFFNT(d)
        g = ft.glyph_count()
        kanji = sum(1 for c in ft.charmap if 0x4E00 <= c <= 0x9FFF)
        kana = sum(1 for c in ft.charmap if 0x3040 <= c <= 0x30FF)
        hangul = sum(1 for c in ft.charmap if 0xAC00 <= c <= 0xD7A3)
        try:
            ok = 'OK' if ft.build() == d else 'X'
        except Exception as e:  # noqa: BLE001
            ok = 'ERR ' + str(e)[:40]
        print(f'{name} | {ft.cell_w}x{ft.cell_h} | {ft.num_sheets}×{ft.sheet_w}x{ft.sheet_h} '
              f'({ft.sheet_size}B) | {FMT.get(ft.format, ft.format)} | {ft.per_sheet} | {ft.capacity} | {g} | '
              f'{ft.capacity - g} | {kanji} | {kana} | {hangul} | {ok}')


if __name__ == '__main__':
    main()
