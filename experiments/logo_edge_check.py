"""흰 바탕 로고 찾기 — 동그라미로 잘린 로고 가장자리가 거의 흰색이면 ref/ticker_logos.json 에 "light": true 를 적는다.
design_kit.ticker_logo 가 그 로고에만 회색 외곽선(#E2E8F0)을 두른다 (2026-11-11 사용자: "흰 바탕 로고는 외곽선 · 블로그 전체 공통").

로고 대부분이 SVG 라 파이썬만으로는 그림을 못 읽는다 → 맥의 Chrome 으로 40px 동그라미로 그려 캡처한 뒤, 가장자리 고리(반지름 80~95%)의 밝기를 잰다.
로고를 새로 받은 뒤(fetch_ticker_logos.py) 한 번 돌린다. AI · 인터넷 0, 로컬 파일만.

    python experiments/logo_edge_check.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
META = os.path.join(HERE, "ref", "ticker_logos.json")
LOGOS = os.path.join(HERE, "output", "logos")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SZ, COLS, GAP = 40, 10, 10
OUTLINE = "#E2E8F0"   # 회색 강조 카드 테두리와 같은 색
LIGHT = 240   # 가장자리 평균 밝기(0~255)가 이 위면 흰 바탕 — 투명 로고는 자홍 바탕(밝기 약 105)이 비쳐 걸리지 않는다


def main():
    from PIL import Image
    meta = json.load(open(META, encoding="utf-8"))
    syms = [s for s, r in meta["logos"].items() if os.path.exists(os.path.join(LOGOS, r["file"]))]
    cells = "".join(f'<img src="file://{os.path.join(LOGOS, meta["logos"][s]["file"])}" style="position:absolute;left:{GAP + (i % COLS) * (SZ + GAP)}px;'
                    f'top:{GAP + (i // COLS) * (SZ + GAP)}px;width:{SZ}px;height:{SZ}px;border-radius:50%;object-fit:cover;background:#FF00FF;">'
                    for i, s in enumerate(syms))
    rows = (len(syms) + COLS - 1) // COLS
    w, h = GAP + COLS * (SZ + GAP), GAP + rows * (SZ + GAP)
    tmp = tempfile.mkdtemp()
    page, shot = os.path.join(tmp, "logos.html"), os.path.join(tmp, "logos.png")
    open(page, "w", encoding="utf-8").write(f'<html><body style="margin:0;background:#fff;">{cells}</body></html>')
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                    f"--window-size={w},{h}", "--virtual-time-budget=5000", f"--screenshot={shot}", f"file://{page}"],
                   check=True, capture_output=True)
    im = Image.open(shot).convert("L")
    k = im.size[0] / w
    light = []
    for i, s in enumerate(syms):
        cx, cy, r = (GAP + (i % COLS) * (SZ + GAP) + SZ / 2) * k, (GAP + (i // COLS) * (SZ + GAP) + SZ / 2) * k, SZ / 2 * k
        vals = []
        for a in range(0, 360, 6):
            for f in (0.80, 0.88, 0.95):
                import math
                vals.append(im.getpixel((int(cx + r * f * math.cos(math.radians(a))), int(cy + r * f * math.sin(math.radians(a))))))
        avg = sum(vals) / len(vals)
        meta["logos"][s]["light"] = avg > LIGHT
        if avg > LIGHT:
            light.append(f"{s}({avg:.0f})")
    json.dump(meta, open(META, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 테마(index.html)의 로고(홈 · 제목 · 목록 카드)도 같은 외곽선 — 파일 이름으로 고르는 CSS 한 줄을 표시 사이에 다시 쓴다 (테마 붙여넣기 필요)
    files = sorted(meta["logos"][s]["file"] for s in syms if meta["logos"][s].get("light"))
    sel = ", ".join(f'img[src$="/{f}"]' for f in files)
    css = f"{sel} {{ outline: 1px solid {OUTLINE}; outline-offset: -1px; }}   /* 흰 바탕 로고 외곽선 — logo_edge_check.py 가 쓴다 (2026-11-11 사용자) */"
    idx = os.path.join(os.path.dirname(HERE), "index.html")
    t = open(idx, encoding="utf-8").read()
    a, b = "/* LIGHT_LOGOS_START */", "/* LIGHT_LOGOS_END */"
    if a in t and b in t:
        t = t[:t.index(a) + len(a)] + "\n" + css + "\n" + t[t.index(b):]
        open(idx, "w", encoding="utf-8").write(t)
    print(f"흰 바탕 {len(light)}/{len(syms)}: {' '.join(light)}")


if __name__ == "__main__":
    sys.exit(main())
