"""토론 아바타 24종 자르기 — 사용자 그림 두 장(4 × 3 원) → 원 하나씩 96px 정사각 webp(원 밖 투명).

  avatars_src/sheet_animal.webp  → output/avatars/a01~a12.webp  (동물)
  avatars_src/sheet_people.webp  → output/avatars/p01~p12.webp  (일반)

순서 = 왼쪽 위부터 줄마다 왼쪽 → 오른쪽. 원 지름은 가로 폭으로 잡는다(귀 · 뿔 · 왕관이 원 위로 나온 그림이 있어 세로 폭은 믿지 않음).
(수정 모음 P631).
"""
import os
from collections import deque

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "avatars_src")
OUT = os.path.join(HERE, "output", "avatars")
SIZE = 96
SCALE = 4   # 연결 덩어리 찾기는 1/4 크기로


def blobs(im):
    small = im.resize((im.width // SCALE, im.height // SCALE))
    w, h = small.size
    px = small.load()
    ink = [[min(px[x, y]) < 235 for x in range(w)] for y in range(h)]
    seen = [[False] * w for _ in range(h)]
    found = []
    for y in range(h):
        for x in range(w):
            if not ink[y][x] or seen[y][x]:
                continue
            q, box, n = deque([(x, y)]), [x, y, x, y], 0
            seen[y][x] = True
            while q:
                cx, cy = q.popleft()
                n += 1
                box = [min(box[0], cx), min(box[1], cy), max(box[2], cx), max(box[3], cy)]
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and ink[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        q.append((nx, ny))
            if n > 2000:
                found.append([v * SCALE for v in box])
    return found


def cut(sheet, prefix):
    im = Image.open(os.path.join(SRC, sheet)).convert("RGB")
    cells = {}   # 4 × 3 칸마다 덩어리 합치기(원 위로 떨어져 나온 왕관 · 귀 · 흰 옷 조각)
    for b in blobs(im):
        k = (int((b[1] + b[3]) / 2 * 3 // im.height), int((b[0] + b[2]) / 2 * 4 // im.width))
        o = cells.get(k)
        cells[k] = b if o is None else [min(o[0], b[0]), min(o[1], b[1]), max(o[2], b[2]), max(o[3], b[3])]
    assert len(cells) == 12, f"{sheet}: 칸 {len(cells)}개"
    bs = [cells[k] for k in sorted(cells)]
    cys = [b[3] + SCALE - (b[2] - b[0] + SCALE) / 2 for b in bs]
    for i, (x0, y0, x1, y1) in enumerate(bs, 1):
        d = x1 - x0 + SCALE
        row = sorted(cys[(i - 1) // 4 * 4:(i - 1) // 4 * 4 + 4])
        cy = cys[i - 1] if abs(cys[i - 1] - (row[1] + row[2]) / 2) < 12 else (row[1] + row[2]) / 2   # 흰 옷이 원 아래를 끊은 그림(우주인) = 같은 줄 가운데 높이
        cx = (x0 + x1 + SCALE) / 2
        r = d / 2 - 3   # 가장자리 흰 번짐 빼기
        sq = im.crop((round(cx - r), round(cy - r), round(cx + r), round(cy + r))).resize((SIZE * 4, SIZE * 4), Image.LANCZOS)
        mask = Image.new("L", sq.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, sq.width - 1, sq.height - 1), fill=255)
        sq.putalpha(mask)
        sq.resize((SIZE, SIZE), Image.LANCZOS).save(os.path.join(OUT, f"{prefix}{i:02d}.webp"), quality=90)


def main():
    os.makedirs(OUT, exist_ok=True)
    cut("sheet_animal.webp", "a")
    cut("sheet_people.webp", "p")
    print("24개 →", OUT)


if __name__ == "__main__":
    main()
