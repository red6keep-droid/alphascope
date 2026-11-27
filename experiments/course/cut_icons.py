"""주식 공부 소품 아이콘 시트 → 아이콘마다 투명 배경 그림.

    .venv/bin/python experiments/course/cut_icons.py

- 원본: icons/src/sheet1.png (사용자 제공, 2160×1620, 가로 4칸 × 세로 3줄 = 540px 칸 — 11-15 두 번째 시트(메모장 추가), 선 없이 투명 바탕)
- 원본이 투명 바탕(RGBA) — 칸을 잘라 그림만 남게 → 정사각 캔버스 가운데
- 출력: icons/<이름>.webp (무손실, 한 변 SIZE px)
"""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "icons", "src", "sheet1.png")
OUT = os.path.join(HERE, "icons")
SIZE = 128   # 화면 = 40px 동그라미 안 26px — 고해상도 화면 여유
CELL = 540

# 순서 = 시트 왼쪽 위부터 (커리큘럼 문서 5절 공통 세트 9개 + 0편 주제 2개 + 메모장(연재 · 확인 방법 구획))
NAMES = ["theater", "question", "ruler", "chart",
         "scale", "magnifier", "bulb", "map",
         "check", "hook", "calendars", "memo"]


def cut(im, k):
    x0, y0 = (k % 4) * CELL, (k // 4) * CELL
    c = im.crop((x0, y0, x0 + CELL, y0 + CELL))
    c = c.crop(c.getchannel("A").getbbox())   # 원본이 이미 투명 바탕 — 그림만 남게
    side = round(max(c.size) * 1.08)   # 둘레 4% 투명 여백 — 외곽선이 그림 가장자리에 붙어 잘려 보이지 않게
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(c, ((side - c.width) // 2, (side - c.height) // 2), c)
    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


def main():
    im = Image.open(SRC).convert("RGBA")
    for k, name in enumerate(NAMES):
        out = os.path.join(OUT, f"{name}.webp")
        cut(im, k).save(out, "WEBP", lossless=True)
        print(f"{name} → {out} ({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
