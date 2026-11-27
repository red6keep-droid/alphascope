"""주식 공부 캐릭터 — 강조 줄용 '가운데 맞춤' 그림 만들기.

    .venv/bin/python experiments/course/center_chars.py      # chars/*.webp(320×320) → chars/c_*.webp

까닭: svg_to_webp.py chars 는 320×320 칸에 **아래 맞춤**이라 그림 위쪽이 비어 있다(최대 94px). 상자 가운데에 놓아도 몸이 아래로 쏠린다.
→ 투명 여백을 잘라 낸 그림을 같은 320×320 칸의 위아래 · 좌우 가운데에 다시 놓는다. 그림 크기(배율)는 그대로라 보이는 크기는 변하지 않는다.
강조 줄 = c_ 그림. 대결 = t_ 그림(위쪽 여백만 잘라 바닥 맞춤, 높이가 그림마다 다름). 말풍선 아래 그림은 원본(render_course.py char()).
새 캐릭터를 svg_to_webp.py 로 만든 뒤에는 이 스크립트를 다시 돌린다.
"""
import glob
import os

from PIL import Image

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chars")


def main():
    n = 0
    for f in sorted(glob.glob(os.path.join(HERE, "*.webp"))):
        name = os.path.basename(f)
        if name.startswith(("c_", "t_")):
            continue
        im = Image.open(f).convert("RGBA")
        if im.size != (320, 320):   # 가로 컷(pair_box · mid_scale · mid_ruler)은 대상 아님
            continue
        bb = im.getchannel("A").getbbox()
        part = im.crop(bb)
        out = Image.new("RGBA", im.size, (0, 0, 0, 0))
        out.paste(part, ((320 - part.width) // 2, (320 - part.height) // 2))
        out.save(os.path.join(HERE, "c_" + name), "WEBP", quality=90, method=6)
        # 대결용 = 위쪽 투명 여백만 잘라 낸 그림(바닥 맞춤 · 가로 320 그대로) — 말풍선 꼬리 바로 아래에 몸이 오게
        im.crop((0, bb[1], 320, 320)).save(os.path.join(HERE, "t_" + name), "WEBP", quality=90, method=6)
        n += 1
    print(f"[가운데] {n}장 → chars/c_*.webp · 대결용 t_*.webp")


if __name__ == "__main__":
    main()
