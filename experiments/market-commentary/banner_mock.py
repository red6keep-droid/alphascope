"""시황 해설 배너 목업 (2026-11-17 사용자 "목업부터 만들어줘") — 화풍 4 × 분위기 2(내린 날 · 오른 날), 글자 얹기 있음 · 없음.

    python experiments/market-commentary/banner_mock.py            # 그림 받기(없는 것만) + 목업 HTML
    python experiments/market-commentary/banner_mock.py --html     # 그림은 그대로, HTML 만 다시

- 그림: Pollinations flux (키 없음, 옛 데일리 커버와 같은 길). 무료는 IP 당 45초에 1장(11-17 402 FREE_LIMIT) — 50초 간격. 실제 운영은 Workers AI flux-1-schnell 맨 앞 — 같은 FLUX 계열.
- 장면: 파이썬 틀(주제 낱말 + 방향) — AI 0. 오늘 주제 = 기술주 내림 · 엔비디아 실적 (briefing/2026-11-17-am.json).
- 글자 얹기: Pillow + 맑은 고딕(이 PC). CI 에선 한글 폰트를 따로 넣어야 한다.
- 출력: output/banner/*.webp · output/banner-mock.html (커밋 안 함)
"""
import argparse
import io
import os
import sys
import time
import urllib.parse

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "output")
IMG = os.path.join(OUT, "banner")
W, H = 1024, 400

SCENE = {   # 주제 낱말 → 장면 (반도체 · 기술주)
    "down": "glowing semiconductor chips on a circuit board under a calm night sky, cool blue tones, quiet mood, gentle downward light trails",
    "up": "glowing semiconductor chips on a circuit board under a bright sunrise sky, warm red and orange tones, energetic mood, rising light trails",
}
STYLES = {
    "A": ("평면 일러스트", "flat vector illustration, clean modern editorial art, simple shapes"),
    "B": ("3D 입체", "soft 3D isometric render, clay material, studio lighting, minimal"),
    "C": ("사진풍", "cinematic photograph, shallow depth of field, high detail, wide shot"),
    "D": ("추상 그라데이션", "abstract minimal composition, smooth gradients, geometric light shapes, no objects in focus"),
}
NO_TEXT = ", wide banner composition, no text, no letters, no numbers, no logos, no watermark"
TITLE = {"down": "11월 17일 아침 · 기술주 내림 뒤, 오늘 밤 엔비디아 실적",
         "up": "(비교용) 오른 날 · 반도체가 지수를 끌어올림"}


def prompt(style, mood):
    return f"{SCENE[mood]}, {STYLES[style][1]}{NO_TEXT}"


def fetch(p, seed):
    url = (f"https://image.pollinations.ai/prompt/{urllib.parse.quote(p)}"
           f"?model=flux&nologo=true&width={W}&height={H}&seed={seed}&referrer=www.newfact.app")
    for i in range(3):
        try:
            r = requests.get(url, timeout=120, headers={"User-Agent": "alpha-scope-mock/1.0"})
            if r.status_code == 200 and len(r.content) > 10_000:
                return r.content
            print(f"  HTTP {r.status_code} · {len(r.content)}B")
        except Exception as e:  # noqa: BLE001
            print(f"  실패: {e}")
        time.sleep(50)
    return None


def font(px):
    for f in (r"C:\Windows\Fonts\malgunbd.ttf", r"C:\Windows\Fonts\malgun.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, px)
    return ImageFont.load_default()


def overlay(src, dst, mood):
    im = Image.open(src).convert("RGB").resize((W, H))
    shade = Image.new("L", (W, H), 0)   # 왼쪽 아래 어둡게 — 글자 읽히게
    d = ImageDraw.Draw(shade)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=int(150 * max(0, (y - H * 0.35) / (H * 0.65))))
    im = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), im, shade.filter(ImageFilter.GaussianBlur(4)))
    d = ImageDraw.Draw(im)
    d.text((40, H - 118), "뉴팩트 시황 해설", font=font(44), fill="white")
    d.text((42, H - 60), "2026.11.17 아침" if mood == "down" else "예시 · 오른 날", font=font(26), fill=(230, 230, 230))
    im.save(dst, "WEBP", quality=80)


def build_images():
    os.makedirs(IMG, exist_ok=True)
    for s in STYLES:
        for m in SCENE:
            raw = os.path.join(IMG, f"{s}-{m}.webp")
            if not os.path.exists(raw):
                print(f"[그림] {s}-{m} ({STYLES[s][0]})")
                data = fetch(prompt(s, m), seed=1117)
                if not data:
                    print("  → 못 받음, 건너뜀")
                    continue
                Image.open(io.BytesIO(data)).convert("RGB").save(raw, "WEBP", quality=80)
                time.sleep(50)
            txt = os.path.join(IMG, f"{s}-{m}-text.webp")
            overlay(raw, txt, m)


def kb(p):
    return f"{os.path.getsize(p) / 1024:.0f}KB" if os.path.exists(p) else "—"


def card(s, m, text):
    name = f"{s}-{m}{'-text' if text else ''}.webp"
    path = os.path.join(IMG, name)
    img = (f'<img src="banner/{name}" alt="" style="width:100%;display:block;aspect-ratio:1024/400;object-fit:cover;border-radius:8px;">'
           if os.path.exists(path) else '<div class="miss">그림 못 받음</div>')
    return (f'<article class="post">{img}'
            f'<h3>{TITLE[m]}</h3>'
            f'<p class="lede">지난밤 미국은 기술 업종이 −2.39% 로 가장 많이 내렸고, S&amp;P 500 은 −1.91% 였다. 오늘 장 마감 뒤 엔비디아 실적이 나온다. <span class="mute">(본문 예시)</span></p>'
            f'<p class="meta">{"글자 얹음" if text else "그림만"} · {kb(path)}</p></article>')


def build_html():
    rows = []
    for s, (label, _) in STYLES.items():
        rows.append(f'<section><h2>{s}. {label}</h2>'
                    f'<p class="p">장면 설명: <code>{prompt(s, "down")}</code></p>'
                    f'<div class="grid">{card(s, "down", False)}{card(s, "down", True)}{card(s, "up", False)}{card(s, "up", True)}</div></section>')
    html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>시황 배너 목업</title><style>
body{{margin:0;background:#f5f6f8;color:#111;font-family:"Malgun Gothic",system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px 60px}}
h1{{font-size:22px;margin:0 0 6px}} .intro{{color:#333;font-size:15px;line-height:1.6;margin:0 0 24px}}
section{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px 16px;margin:0 0 20px}}
h2{{font-size:18px;margin:0 0 6px}} .p{{font-size:12px;color:#6b7280;margin:0 0 14px;word-break:break-all}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}}
.post{{border:1px solid #eee;border-radius:10px;padding:10px;background:#fff}}
.post h3{{font-size:17px;line-height:1.4;margin:12px 2px 6px}} .lede{{font-size:14px;line-height:1.6;color:#333;margin:0 2px 8px}}
.mute,.meta{{color:#9ca3af;font-size:12px}} .meta{{margin:0 2px}}
.miss{{aspect-ratio:1024/400;display:flex;align-items:center;justify-content:center;background:#f3f4f6;color:#9ca3af;border-radius:8px}}
code{{font-size:12px}}
</style></head><body><main>
<h1>뉴팩트 시황 해설 — 배너 목업</h1>
<p class="intro">화풍 4가지(A~D) × 분위기 2가지. 왼쪽 두 칸 = 오늘 아침(지난밤 기술주 내림 · 파랑 톤), 오른쪽 두 칸 = 비교용 오른 날(빨강 톤). 각 분위기마다 그림만 · 글자 얹음.<br>
그림 = Pollinations FLUX(목업용, 운영은 Workers AI FLUX schnell). 장면은 파이썬 틀이 주제 낱말(반도체) + 방향으로 만든 것 — AI 글 모델 0. 글 제목 · 본문은 예시.</p>
{''.join(rows)}
</main></body></html>"""
    p = os.path.join(OUT, "banner-mock.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[목업] {p}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", action="store_true")
    a = ap.parse_args()
    if not a.html:
        build_images()
    build_html()
    sys.exit(0)
