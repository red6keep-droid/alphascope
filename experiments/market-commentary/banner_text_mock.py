"""시황 배너 글자 얹기 목업.

    python experiments/market-commentary/banner_text_mock.py

- 배경 = banner_mock2 그림(목업은 Pollinations), 글자 = Pillow. 숫자 없음.
- 칸: 위 알약(브랜드 · 날짜 · 편) / 제목 2줄 / 키워드 줄 / 오늘 볼 것 3칸 / 아래 `AI 생성 이미지`.
- 글은 운영에선 수집기 글(title · points)에서 온다 — 여기선 오늘 묶음 파일로 손으로 쓴 예시.
- 색: 한국 관행 오름 빨강 · 내림 파랑. 권유 말투(확인하세요 등) · 매수 · 매도 권유 없음.
- 폰트: 이 PC 맑은 고딕. 운영 CI 는 Noto Sans KR · Pretendard 같은 OFL 폰트 파일을 저장소에 넣어야 한다.
"""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "output", "banner2")
OUT = os.path.join(BASE, "output", "banner3")
W, H = 1200, 630
BOLD, REG = r"C:\Windows\Fonts\malgunbd.ttf", r"C:\Windows\Fonts\malgun.ttf"
UP, DOWN = (244, 67, 54), (84, 156, 255)

SAMPLES = [
    {"bg": "today-am", "dir": "down", "edition": "2026.11.17 (화) 아침",
     "title": ["기술주 내림 뒤", "엔비디아 실적 기다림"],
     "keys": [("미국 기술 업종 ", None), ("약세", "dir"), (" · 반도체 ", None), ("관망", "dir"), (" · 한국장 첫 반응", None)],
     "points": [("오늘 밤", "엔비디아 실적 발표"), ("한국장", "반도체 첫 반응"), ("이번 주", "실업수당 · 옵션 만기")]},
    {"bg": "strong-up", "dir": "up", "edition": "예시 · 오른 날",
     "title": ["반도체가 끌어올린", "미국 증시"],
     "keys": [("기술 업종 ", None), ("강세", "dir"), (" · 금리 ", None), ("안정", "dir"), (" · 거래 증가", None)],
     "points": [("오늘 밤", "주요 기업 실적"), ("한국장", "반도체 따라갈까"), ("이번 주", "물가 지표")]},
]


def f(path, px):
    return ImageFont.truetype(path, px)


def rounded(d, box, r, fill, outline=None, width=1):
    d.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)


def compose(s, src=SRC, tag=""):
    bg = Image.open(os.path.join(src, f"{s['bg']}.webp")).convert("RGB").resize((W, H))
    # 왼쪽을 어둡게 (글자 쪽) — 오른쪽은 그림이 보이게
    shade = Image.new("L", (W, H))
    sd = ImageDraw.Draw(shade)
    for x in range(W):
        sd.line([(x, 0), (x, H)], fill=int(205 * max(0.0, 1 - x / (W * 0.78))))
    for y in range(H - 200, H):
        sd.line([(0, y), (W, y)], fill=None)
    im = Image.composite(Image.new("RGB", (W, H), (8, 14, 30)), bg, shade.filter(ImageFilter.GaussianBlur(6)))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    acc = UP if s["dir"] == "up" else DOWN

    # ① 위 알약
    pill = f"Newfact 시황 해설   |   {s['edition']}"
    pf = f(BOLD, 24)
    pw = d.textlength(pill, font=pf)
    rounded(d, (48, 40, 48 + pw + 48, 92), 26, (10, 20, 45, 200), outline=(255, 255, 255, 90), width=2)
    d.text((72, 50), pill, font=pf, fill=(235, 240, 250))

    # ② 제목 2줄 (둘째 줄 = 방향 색)
    tf = f(BOLD, 74)
    d.text((48, 120), s["title"][0], font=tf, fill="white", stroke_width=2, stroke_fill=(0, 0, 0, 120))
    d.text((48, 210), s["title"][1], font=tf, fill=acc, stroke_width=2, stroke_fill=(0, 0, 0, 120))

    # ③ 키워드 줄
    kf = f(BOLD, 32)
    x = 52
    for txt, kind in s["keys"]:
        col = (255, 214, 64) if kind == "dir" else (235, 238, 245)
        d.text((x, 318), txt, font=kf, fill=col)
        x += d.textlength(txt, font=kf)

    # ④ 오늘 볼 것 3칸
    top, h = 400, 130
    rounded(d, (40, top, W - 40, top + h), 22, (10, 22, 50, 190), outline=(120, 160, 255, 110), width=2)
    rounded(d, (60, top + 22, 230, top + h - 22), 18, acc + (235,))
    lf = f(BOLD, 30)
    d.text((145, top + h / 2 - 20), "오늘", font=lf, fill="white", anchor="mm")
    d.text((145, top + h / 2 + 18), "볼 것", font=lf, fill="white", anchor="mm")
    cw = (W - 40 - 250) / 3
    px = 27   # 세 칸 같은 크기 — 가장 긴 칸에 맞춘다 (27 → 최소 18)
    while px > 18 and max(d.textlength(w2, font=f(BOLD, px)) for _, w2 in s["points"]) > cw - 76 - 20:
        px -= 1
    for i, (when, what) in enumerate(s["points"]):
        cx = 250 + i * cw
        if i:
            d.line([(cx, top + 26), (cx, top + h - 26)], fill=(255, 255, 255, 70), width=2)
        d.ellipse((cx + 24, top + 30, cx + 60, top + 66), fill=acc + (255,))
        d.text((cx + 42, top + 48), str(i + 1), font=f(BOLD, 22), fill="white", anchor="mm")
        d.text((cx + 76, top + 30), when, font=f(BOLD, 24), fill=(255, 214, 64))
        d.text((cx + 76, top + 66 + (27 - px) / 2), what, font=f(BOLD, px), fill="white")

    # ⑤ 아래 표시
    d.text((48, H - 34), "AI 생성 이미지 · Newfact", font=f(REG, 18), fill=(200, 205, 215), anchor="lm")
    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, f"{s['bg']}{tag}-text.webp")
    im.save(p, "WEBP", quality=85)
    print(f"[배너] {p} · {os.path.getsize(p) / 1024:.0f}KB")


CF = os.path.join(BASE, "output", "banner-cf")   # banner-cf-test.yml artifact 를 받은 곳 (2026-11-17 비교)


if __name__ == "__main__":
    for s in SAMPLES:
        compose(s)
        for m in ("flux-1-schnell", "lucid-origin"):
            if os.path.exists(os.path.join(CF, m, f"{s['bg']}.webp")):
                compose(s, os.path.join(CF, m), f"-{m}")
