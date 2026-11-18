"""영상의 장면이 바뀌는 순간마다 프레임을 뽑아 시트로 만든다(2초 간격 표본 사이에 잠깐 뜨는 글자 확인용).

대상: content/Movie/*.mp4 13개 + meta/bootMovie.h264
방법: ffmpeg select='eq(n,0)+gt(scene,기준)' — 첫 프레임과 화면이 기준 이상 바뀐 프레임 전부. 기준 기본 0.03.
사용: python -I tools/movie_scenes.py [기준=0.03]
결과: work/survey/movie_scene/<영상>/s_*.png, 시트 work/survey/movie_scene/sheets/<영상>_NN.png
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
import imageio_ffmpeg  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]')
OUT = os.path.join(ROOT, 'work', 'survey', 'movie_scene')
FF = imageio_ffmpeg.get_ffmpeg_exe()


def main():
    th = float(sys.argv[1]) if len(sys.argv) > 1 else 0.03
    os.makedirs(os.path.join(OUT, 'sheets'), exist_ok=True)
    mdir = os.path.join(GAME, 'content', 'Movie')
    srcs = [os.path.join(mdir, f) for f in sorted(os.listdir(mdir)) if f.endswith('.mp4')]
    srcs.append(os.path.join(GAME, 'meta', 'bootMovie.h264'))
    total = 0
    for p in srcs:
        name = os.path.splitext(os.path.basename(p))[0]
        d = os.path.join(OUT, name)
        os.makedirs(d, exist_ok=True)
        for x in os.listdir(d):
            os.remove(os.path.join(d, x))
        subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-y', '-i', p,
                        '-vf', f"select='eq(n,0)+gt(scene,{th})',scale=480:-1", '-vsync', 'vfr', '-frame_pts', '1',
                        os.path.join(d, 's_%08d.png')], check=True)
        frames = sorted(os.listdir(d), key=lambda x: int(x[2:10]))
        total += len(frames)
        COLS, ROWS = 4, 6
        for s in range(0, len(frames), COLS * ROWS):
            chunk = frames[s:s + COLS * ROWS]
            w, h = Image.open(os.path.join(d, chunk[0])).size
            sh = Image.new('RGB', (COLS * w, ROWS * (h + 16)), (30, 30, 30))
            dr = ImageDraw.Draw(sh)
            for k, fr in enumerate(chunk):
                im = Image.open(os.path.join(d, fr)).convert('RGB')
                x, y = (k % COLS) * w, (k // COLS) * (h + 16)
                sh.paste(im, (x, y))
                dr.text((x + 4, y + h + 2), f'{name} pts {int(fr[2:10])}', fill=(255, 255, 0))
            sh.save(os.path.join(OUT, 'sheets', f'{name}_{s // (COLS * ROWS):02d}.png'))
        print(name, len(frames), '장')
    print('합계', total)


if __name__ == '__main__':
    main()
