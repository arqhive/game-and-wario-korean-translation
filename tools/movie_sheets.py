"""영상 13개에서 일정 간격으로 장면을 뽑아 눈 확인용 시트를 만든다(4단계, 영상 속 글자 조사).

사용: python -I tools/movie_sheets.py [간격초=2]
결과: work/survey/movie/<영상>/f_%05d.png, work/survey/movie/sheets/<영상>_NN.png, 정보 work/survey/movie/info.json
ffmpeg 는 imageio_ffmpeg 에 든 것을 쓴다.
"""
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
import imageio_ffmpeg  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOV = os.path.join(ROOT, 'Game Wario [Game] [0005000010112d00]', 'content', 'Movie')
OUT = os.path.join(ROOT, 'work', 'survey', 'movie')
FF = imageio_ffmpeg.get_ffmpeg_exe()


def probe(p):
    r = subprocess.run([FF, '-hide_banner', '-i', p], capture_output=True, text=True, encoding='utf-8', errors='replace')
    dur = re.search(r'Duration: (\d+):(\d+):([\d.]+)', r.stderr)
    sec = int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3)) if dur else None
    streams = [l.strip() for l in r.stderr.splitlines() if 'Stream #' in l]
    return sec, streams


def main():
    step = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    os.makedirs(os.path.join(OUT, 'sheets'), exist_ok=True)
    info = {}
    for f in sorted(os.listdir(MOV)):
        if not f.endswith('.mp4'):
            continue
        p = os.path.join(MOV, f)
        name = f[:-4]
        d = os.path.join(OUT, name)
        os.makedirs(d, exist_ok=True)
        sec, streams = probe(p)
        subprocess.run([FF, '-hide_banner', '-loglevel', 'error', '-y', '-i', p, '-vf', f'fps=1/{step},scale=480:-1',
                        os.path.join(d, 'f_%05d.png')], check=True)
        frames = sorted(x for x in os.listdir(d) if x.startswith('f_'))
        info[name] = dict(seconds=sec, streams=streams, frames=len(frames))
        COLS, ROWS = 4, 6
        for s in range(0, len(frames), COLS * ROWS):
            chunk = frames[s:s + COLS * ROWS]
            im0 = Image.open(os.path.join(d, chunk[0]))
            w, h = im0.size
            sh = Image.new('RGB', (COLS * w, ROWS * (h + 16)), (30, 30, 30))
            dr = ImageDraw.Draw(sh)
            for k, fr in enumerate(chunk):
                im = Image.open(os.path.join(d, fr)).convert('RGB')
                x, y = (k % COLS) * w, (k // COLS) * (h + 16)
                sh.paste(im, (x, y))
                t = (int(fr[2:7]) - 1) * step
                dr.text((x + 4, y + h + 2), f'{name} {t:.0f}s', fill=(255, 255, 0))
            sh.save(os.path.join(OUT, 'sheets', f'{name}_{s // (COLS * ROWS):02d}.png'))
        print(name, f'{sec:.1f}s' if sec else '?', len(frames), '장', streams)
    json.dump(info, open(os.path.join(OUT, 'info.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
