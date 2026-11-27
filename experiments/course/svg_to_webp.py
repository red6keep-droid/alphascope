"""사용자 SVG 그림 → 강좌 캐릭터 · 아이콘 WebP.

    python experiments/course/svg_to_webp.py chars <원본.svg> <이름>     # 320×320, 아래 맞춤 → chars/<이름>.webp, 원본은 chars/src/<이름>.svg
    python experiments/course/svg_to_webp.py icons <원본.svg> <이름>     # 128×128, 가운데 → icons/<이름>.webp
    python experiments/course/svg_to_webp.py wide <원본.svg> <이름>      # 가로 컷(여럿이 나오는 그림), 가로 560 비율 그대로 → chars/<이름>.webp

- 그리기 = Windows Edge headless 화면 찍기(투명 바탕), 맥은 Chrome headless. 따로 설치할 것 없음.
- 투명하지 않은 영역만 잘라 긴 변을 칸에 맞춘다. 원본에 떨어진 점이 있으면 잘림 영역이 넓어지니 SVG 에서 먼저 지운다.
- 렌더러 이름 표(render_course.py CHARS · ICONS)에는 손으로 한 줄 추가.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE):   # 맥(집) = Chrome headless — 같은 옵션 (2026-11-21)
    EDGE = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SIZE = {"chars": (320, "bottom"), "icons": (128, "center"), "wide": (560, None)}   # wide = 여럿이 나오는 가로 컷: 네모 칸에 넣지 않고 가로 560 그대로 → chars/ (2026-11-21)


def shot(svg, png, px=800):
    d = os.path.dirname(svg)
    page = os.path.join(d, "_shot.html")
    open(page, "w", encoding="utf-8").write(
        '<!doctype html><html><body style="margin:0;background:transparent">'
        f'<img src="{os.path.basename(svg)}" style="display:block;width:{px}px;height:{px}px;object-fit:contain"></body></html>')
    prof = os.path.join(tempfile.gettempdir(), "edge_svg_shot")
    try:
        for _ in range(3):   # Edge 가 바로 끝나지 않고 파일을 늦게 쓰는 때가 있어 기다리고, 안 나오면 다시
            subprocess.run([EDGE, "--headless", "--disable-gpu", "--hide-scrollbars", "--default-background-color=00000000",
                            f"--user-data-dir={prof}", f"--window-size={px},{px}", f"--screenshot={png}", "file:///" + page.replace("\\", "/")],
                           capture_output=True)
            for _ in range(30):
                if os.path.exists(png) and os.path.getsize(png) > 0:
                    time.sleep(0.3)
                    return
                time.sleep(0.3)
        raise SystemExit(f"그리기 실패: {svg}")
    finally:
        os.remove(page)


def main():
    kind, src, name = sys.argv[1], sys.argv[2], sys.argv[3]
    side, align = SIZE[kind]
    wide, kind = kind == "wide", "chars" if kind == "wide" else kind
    os.makedirs(os.path.join(HERE, kind, "src"), exist_ok=True)
    svg = os.path.join(HERE, kind, "src", name + ".svg")
    if os.path.abspath(src) != os.path.abspath(svg):
        shutil.copyfile(src, svg)
    png = os.path.join(HERE, kind, "src", "_" + name + ".png")
    shot(svg, png)
    im = Image.open(png).convert("RGBA")
    os.remove(png)
    im = im.crop(im.getchannel("A").getbbox())
    k = (side - (5 if kind == "icons" else 0)) / max(im.size)
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    if wide:
        out = im
    else:
        out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        y = side - im.height if align == "bottom" else (side - im.height) // 2
        out.paste(im, ((side - im.width) // 2, y), im)
    dst = os.path.join(HERE, kind, name + ".webp")
    out.save(dst, "WEBP", quality=90, method=6)
    print(f"{dst}  {im.size}")


if __name__ == "__main__":
    main()
