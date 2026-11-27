"""차트 읽기 캐릭터 컷(한 장에 한 컷, 흰 바탕) → 투명 바탕 320×320 WebP.

    .venv/bin/python experiments/chart-talk/to_webp.py <그림.png> <이름>   예) … 1.png down_hello → chars/down_hello.webp
바탕 지우기는 course/sheet_to_webp.cut 과 같다(가장자리에서 이어진 흰색만 투명). 그림을 꽉 채워 320 칸 아래 맞춤.
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "course"))
from sheet_to_webp import BOX, PAD, cut  # noqa: E402


def main():
    src, name = sys.argv[1], sys.argv[2]
    im = Image.open(src)
    if im.mode in ("RGBA", "LA", "P") and im.convert("RGBA").getchannel("A").getextrema()[0] < 255:
        rgba = im.convert("RGBA")   # 이미 바탕이 투명한 그림 = 그대로 (흰 면 · 햇살이 옅어지지 않게)
    else:
        im = im.convert("RGB")
        a = np.asarray(im).astype(int)
        bg = np.median(a[:8, :8].reshape(-1, 3), axis=0)
        rgba = cut(im, bg)
    rgba = rgba.crop(rgba.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())
    k = (BOX - 2 * PAD) / max(rgba.size)
    rgba = rgba.resize((max(1, round(rgba.width * k)), max(1, round(rgba.height * k))), Image.LANCZOS)
    out = Image.new("RGBA", (BOX, BOX), (0, 0, 0, 0))
    out.paste(rgba, ((BOX - rgba.width) // 2, BOX - PAD - rgba.height), rgba)
    path = os.path.join(HERE, "chars", name + ".webp")
    out.save(path, "WEBP", quality=90, method=6)
    print(path, os.path.getsize(path) // 1024, "KB")


if __name__ == "__main__":
    main()
