"""여러 컷이 한 장에 든 그림(흰 바탕 + 컷 아래 설명 글자) → 컷마다 투명 바탕 320×320 WebP.

    python experiments/course/sheet_to_webp.py <한 장.png> <접두> <이름,이름,…> [--out 폴더]
    예) … sheet.png c_mid whistle,balance,chalk,…   → chars/c_mid_whistle.webp …

- 줄 = 가로로 빈 띠로 나눈다. 그림 줄 · 설명 글자 줄이 번갈아 오므로 글자 줄(높이가 그림 줄의 1/3 아래)은 버린다.
- 칸 = 그림 줄 안에서 세로로 빈 띠로 나눈다. 이름은 왼쪽 위부터 오른쪽으로, 줄 순서대로.
- 바탕 = 가장자리에서 이어진 흰색만 투명(눈 흰자 · 달걀 껍데기처럼 안에 갇힌 흰색은 남는다). 경계는 흰 테가 안 남게 옅어지도록.
- 320×320 칸에 아래 맞춤(svg_to_webp.py chars 와 같음).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
BOX, PAD = 320, 8
T_BG = 14      # 바탕과 이 값 안쪽 차이 = 바탕 후보
T_FULL = 56    # 경계에서 이 값 넘게 다르면 온전히 불투명


def bands(v, gap):
    out, s, last = [], None, None
    for i, x in enumerate(v):
        if x:
            if s is None:
                s = i
            elif i - last > gap:
                out.append((s, last + 1))
                s = i
            last = i
    if s is not None:
        out.append((s, last + 1))
    return out


def cut(rgb, bg):
    """한 칸 → 투명 바탕 RGBA."""
    a = np.asarray(rgb).astype(int)
    diff = np.abs(a - bg).max(axis=2)
    h, w = diff.shape
    m = Image.new("L", (w + 2, h + 2), 0)                       # 0 = 바탕 후보, 255 = 그림
    m.paste(Image.fromarray(((diff > T_BG) * 255).astype("uint8")), (1, 1))
    ImageDraw.floodfill(m, (0, 0), 128)                         # 가장자리에서 이어진 바탕만 128
    out_bg = np.asarray(m)[1:-1, 1:-1] == 128
    near = np.asarray(Image.fromarray((out_bg * 255).astype("uint8")).filter(ImageFilter.MaxFilter(7))) > 0   # 바탕에서 3px 안
    alpha = np.full((h, w), 255.0)
    edge = near & ~out_bg
    alpha[edge] = np.clip(diff[edge] / T_FULL, 0, 1) * 255
    alpha[out_bg] = 0
    al = (alpha / 255)[..., None]
    col = np.where(al > 0, (a - bg * (1 - al)) / np.maximum(al, 1e-3), a)   # 흰 바탕이 섞인 만큼 걷어 낸다
    return Image.fromarray(np.dstack([np.clip(col, 0, 255), alpha]).astype("uint8"), "RGBA")


def main():
    args = [x for i, x in enumerate(sys.argv[1:], 1) if not x.startswith("--") and sys.argv[i - 1] not in ("--out", "--gap")]
    src, prefix, names = args[0], args[1], args[2].split(",")
    out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(HERE, "chars")
    gap = int(sys.argv[sys.argv.index("--gap") + 1]) if "--gap" in sys.argv else 24   # 컷 사이 빈 띠가 좁은 장은 줄인다
    os.makedirs(out_dir, exist_ok=True)
    im = Image.open(src)
    if im.mode in ("RGBA", "LA", "P"):   # 이미 바탕을 지운(투명) 그림 = 흰 바탕에 얹어 같은 길로 (2026-11-21 하락이 장)
        im = im.convert("RGBA")
        w = Image.new("RGBA", im.size, (255, 255, 255, 255))
        w.alpha_composite(im)
        im = w
    im = im.convert("RGB")
    a = np.asarray(im).astype(int)
    bg = np.median(a[:8, :8].reshape(-1, 3), axis=0)
    mask = np.abs(a - bg).max(axis=2) > T_BG
    all_rows = bands(mask.sum(axis=1) > 2, 6)
    tall = max(b - t for t, b in all_rows)
    rows = [(t, b) for t, b in all_rows if b - t > tall / 3]    # 설명 글자 줄 버림
    cells, keeps = [], {}
    for t, b in rows:
        found = [(l, r) for l, r in bands(mask[t:b].sum(axis=0) > 2, gap) if r - l > tall / 4]
        if "--by-label" in sys.argv:   # 컷끼리 그림자가 붙은 장 = 아래 설명 글자 덩이 가운데로 칸을 나눈다
            lab = next((lt, lb) for lt, lb in all_rows if lt >= b)
            mids = [(l + r) / 2 for l, r in bands(mask[lab[0]:lab[1]].sum(axis=0) > 0, 60)]
            cuts = [0] + [round((x + y) / 2) for x, y in zip(mids, mids[1:])] + [im.width]
            found = []
            # 덩이(이어진 그림)마다 가운데가 어느 칸에 있나로 주인을 정한다 — 옆 컷의 구름 · 꼬리 조각을 빼려고
            D = 4
            strong = Image.fromarray(((np.abs(a[t:b] - bg).max(axis=2) > 40) * 255).astype("uint8")).reduce(D).point(lambda v: 255 if v > 0 else 0)
            lab_img, k, owner = strong.copy(), 0, {}
            arr = np.asarray(lab_img)
            while True:
                ys, xs = np.nonzero(arr == 255)
                if not len(xs) or k >= 250:
                    break
                k += 1
                ImageDraw.floodfill(lab_img, (int(xs[0]), int(ys[0])), k)
                arr = np.asarray(lab_img)
                cx = np.nonzero(arr == k)[1].mean() * D
                owner[k] = sum(cx >= c for c in cuts[1:-1])
            # 작은 덩이(구름 · 반짝이)는 가로로 가장 많이 겹치는 칸의 큰 덩이(캐릭터) 쪽으로 — 가운데만 보면 옆 칸으로 잘못 가는 때가 있다
            area = {j: int((arr == j).sum()) for j in owner}
            big_cut = max(area.values()) * 0.05 if area else 0
            span = {}
            for j, o in owner.items():
                if area[j] >= big_cut:
                    xs_ = np.nonzero((arr == j).any(axis=0))[0]
                    lo, hi = span.get(o, (10 ** 9, -1))
                    span[o] = (min(lo, xs_[0]), max(hi, xs_[-1]))
            for j in owner:
                if area[j] < big_cut:
                    xs_ = np.nonzero((arr == j).any(axis=0))[0]
                    ov = {o: min(xs_[-1], hi) - max(xs_[0], lo) for o, (lo, hi) in span.items()}
                    if ov and max(ov.values()) > 0:
                        owner[j] = max(ov, key=ov.get)
            for i, (l0, r0) in enumerate(zip(cuts, cuts[1:])):
                other = np.isin(arr, [j for j, o in owner.items() if o != i])
                big = np.asarray(Image.fromarray((other * 255).astype("uint8")).filter(ImageFilter.MaxFilter(5)).resize((arr.shape[1] * D, arr.shape[0] * D))) > 0
                other = np.zeros((b - t, im.width), bool)
                other[:big.shape[0], :big.shape[1]] = big[: b - t, : im.width]
                mine = np.nonzero(np.isin(arr, [j for j, o in owner.items() if o == i]).any(axis=0))[0]
                l1, r1 = (max(mine[0] * D - 12, 0), min((mine[-1] + 1) * D + 12, im.width)) if len(mine) else (l0, r0)   # 내 덩이가 칸 경계를 넘으면 넘은 데까지
                keep = np.zeros(mask.shape, bool)
                keep[t:b, l1:r1] = mask[t:b, l1:r1] & ~other[:, l1:r1]
                keeps[len(cells) + len(found)] = keep
                xs = np.nonzero(keep[t:b].sum(axis=0) > 2)[0]
                found.append((xs[0], xs[-1] + 1))
        cells += [(l, t, r, b) for l, r in found]
    if len(cells) != len(names):
        sys.exit(f"칸 {len(cells)}개 · 이름 {len(names)}개 — 맞지 않음: {cells}")
    for n_cell, ((l, t, r, b), name) in enumerate(zip(cells, names)):
        # 그림 줄과 설명 글자가 붙어 한 줄로 잡힌 칸 = 맨 아래 덩이가 짙은 글자면 버린다
        prof = bands(mask[t:b, l:r].sum(axis=1) > 2, 10)
        if len(prof) > 1:
            lt, lb = prof[-1]
            if lb - lt < (b - t) * 0.15 and (a[t + lt:t + lb, l:r].max(axis=2) < 110).sum() > 50:
                b = t + prof[-2][1]
        g = 12
        box_ = (max(l - g, 0), max(t - g, 0), min(r + g, im.width), min(b + g, im.height))
        c = cut(im.crop(box_), bg)
        if n_cell in keeps:   # 옆 컷 덩이 = 투명
            kp = keeps[n_cell][box_[1]:box_[3], box_[0]:box_[2]]
            c.putalpha(Image.fromarray((np.asarray(c.getchannel("A")) * kp).astype("uint8")))
        c = c.crop(c.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox())
        k = (BOX - 2 * PAD) / max(c.size)
        c = c.resize((max(1, round(c.width * k)), max(1, round(c.height * k))), Image.LANCZOS)
        box = Image.new("RGBA", (BOX, BOX), (0, 0, 0, 0))
        box.paste(c, ((BOX - c.width) // 2, BOX - PAD - c.height))
        p = os.path.join(out_dir, f"{prefix}_{name}.webp")
        box.save(p, "WEBP", quality=90, method=6)
        print(f"{name}: {r - l}×{b - t} → {os.path.getsize(p) // 1024}KB")


if __name__ == "__main__":
    main()
