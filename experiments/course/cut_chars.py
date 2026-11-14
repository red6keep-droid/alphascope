"""강좌 캐릭터 시트 → 칸마다 투명 배경 그림 (2026-11-14 사용자: 캐릭터 시트를 주면 잘라서 쓰기).

    .venv/bin/python experiments/course/cut_chars.py

- 원본: chars/src/sheet1.png (사용자 제공, 위 4칸 · 아래 3칸, 칸 사이 회색 선)
- 칸 안쪽(회색 선 안)을 잘라 → 가장자리와 이어진 흰 바탕 · 바닥 그림자를 투명으로 → 그림만 남게 잘라 정사각 캔버스 가운데 · 아래 맞춤
- 출력: chars/<이름>.webp (무손실, 한 변 SIZE px)
"""
import os
from collections import deque

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "chars", "src", "sheet1.png")
OUT = os.path.join(HERE, "chars")
SIZE = 320   # 화면 최대 125px의 2배 넘게 — 고해상도 화면 여유
PAD = 8      # 회색 선 안쪽으로 더 들어가 자를 폭

# 칸 경계(회색 선 탐지 결과, 1536×1024) — 순서 = 사용자 설명 순서
CELLS = [
    ("up_buy",       (5, 5, 383, 510)),      # 상승이 – 신나게 매수하기
    ("down_grumpy",  (388, 5, 766, 510)),    # 하락이 – 못마땅하게 반응하기
    ("up_surprised", (771, 5, 1149, 510)),   # 상승이 – 예상 밖 상황에 놀라기
    ("mid_think",    (1153, 5, 1532, 510)),  # 중심이 – 고민하며 생각하기
    ("up_sweat",     (5, 514, 502, 1019)),   # 상승이 – 물려서 식은땀 흘리기
    ("mid_explain",  (508, 514, 1023, 1019)),  # 중심이 – 손가락으로 설명하기
    ("down_happy",   (1029, 514, 1532, 1019)),  # 하락이 – 밝게 반응하기
]


def is_bg(p):
    """바탕(흰색) · 바닥 그림자(연한 회청색) — 채도 낮고 밝은 색."""
    r, g, b = p[:3]
    return min(r, g, b) > 200 and max(r, g, b) - min(r, g, b) < 28


def cut(im, box):
    x0, y0, x1, y1 = box
    c = im.crop((x0 + PAD, y0 + PAD, x1 - PAD, y1 - PAD)).convert("RGBA")
    w, h = c.size
    px = c.load()
    seen = bytearray(w * h)
    q = deque((x, y) for x in range(w) for y in (0, h - 1))
    q.extend((x, y) for y in range(h) for x in (0, w - 1))
    while q:   # 가장자리에서 이어진 바탕만 지운다 — 눈 흰자처럼 안에 갇힌 흰색은 남는다
        x, y = q.popleft()
        if seen[y * w + x] or not is_bg(px[x, y]):
            continue
        seen[y * w + x] = 1
        px[x, y] = (255, 255, 255, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx]:
                q.append((nx, ny))
    # 가장자리 흰 테두리(안티에일리어싱) 한 겹 — 바탕에 붙은 밝은 점은 반투명으로
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a and min(r, g, b) > 225:
                if any(0 <= nx < w and 0 <= ny < h and px[nx, ny][3] == 0 for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))):
                    px[x, y] = (r, g, b, 90)
    c = c.crop(c.getbbox())
    side = max(c.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(c, ((side - c.width) // 2, side - c.height), c)   # 가로 가운데 · 발 = 아래
    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


def main():
    im = Image.open(SRC).convert("RGB")
    for name, box in CELLS:
        out = os.path.join(OUT, f"{name}.webp")
        cut(im, box).save(out, "WEBP", lossless=True)
        print(f"{name} → {out} ({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
