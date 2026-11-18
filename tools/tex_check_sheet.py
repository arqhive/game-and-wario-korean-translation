"""번호 목록을 큰 칸(기본 300px) 확인 시트로. 알파는 진회색·밝은 회색 두 바탕에 나란히 합성해 흰 글자·검은 글자를 모두 보이게 한다.

사용: python -I tools/tex_check_sheet.py <번호 목록 json 또는 쉼표 목록> <출력 이름> [칸px]
결과: work/survey/tex/check/<출력 이름>_NN.png
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image, ImageDraw  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = os.path.join(ROOT, 'work', 'survey', 'tex')


def main():
    arg, name = sys.argv[1], sys.argv[2]
    cell = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    ids = json.load(open(arg, encoding='utf-8')) if arg.endswith('.json') else [int(x) for x in arg.split(',')]
    os.makedirs(os.path.join(T, 'check'), exist_ok=True)
    COLS = max(1, 1824 // (cell * 2 + 8))
    ROWS = max(1, 1300 // (cell + 16))
    W = cell * 2 + 8
    n = 0
    for s in range(0, len(ids), COLS * ROWS):
        chunk = ids[s:s + COLS * ROWS]
        sh = Image.new('RGB', (COLS * W, ROWS * (cell + 16)), (20, 20, 20))
        d = ImageDraw.Draw(sh)
        for k, i in enumerate(chunk):
            im = Image.open(os.path.join(T, 'img', '%05d.png' % i)).convert('RGBA')
            x, y = (k % COLS) * W, (k // COLS) * (cell + 16)
            for j, bgc in enumerate(((70, 70, 70, 255), (200, 200, 200, 255))):
                bg = Image.new('RGBA', im.size, bgc)
                bg.alpha_composite(im)
                bg.thumbnail((cell - 2, cell - 2))
                sh.paste(bg.convert('RGB'), (x + j * (cell + 2), y))
            d.text((x + 2, y + cell + 2), '%d %dx%d' % (i, im.size[0], im.size[1]), fill=(255, 255, 0))
        out = os.path.join(T, 'check', '%s_%02d.png' % (name, n))
        sh.save(out)
        n += 1
    print('시트', n, '장, 그림', len(ids))


if __name__ == '__main__':
    main()
