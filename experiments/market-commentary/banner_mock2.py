"""시황 배너 목업 2 — "미국(한국) 경제의 하루" 시네마틱 실사 (2026-11-17 사용자 참고 글 · 참고 사진 2장).

    python experiments/market-commentary/banner_mock2.py           # 없는 그림만 받기 + HTML
    python experiments/market-commentary/banner_mock2.py --html    # HTML 만

- 장면 = 파이썬 틀(AI 글 모델 0): 마스터 화풍(고정) + 소재(업종 → 7종) + 시간대(am = 미국 장면 저녁 · pm = 한국 장면 저녁) + 분위기(지수 등락 → 5종).
- 규칙(운영지침 4-6): 로고 · 간판 · 랜드마크(거래소 정면 · 황소상) 없음, 사람은 멀리 · 뒷모습 · 얼굴 흐림, 글자 없음. 배너 아래 `AI 생성 이미지` 표시.
- 그림: Pollinations flux (목업용 — 무료는 IP 당 45초 1장 · 워터마크). 운영은 Workers AI flux-1-schnell.
"""
import argparse
import io
import os
import time
import urllib.parse

import requests
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "output")
IMG = os.path.join(OUT, "banner2")
W, H = 1200, 630

MASTER = ("cinematic editorial photograph for a premium business magazine, 35mm lens, natural light, realistic, "
          "wide establishing shot, people seen from a distance or from behind with faces not in focus, "
          "no recognizable landmarks, no brand logos, no readable signs, no text, no letters, no numbers, no watermark")

SUBJECT = {   # 업종 · 주제 → 소재 (참고 글 6절의 7갈래)
    "finance": "a financial district street between glass skyscrapers with office workers walking",
    "corporate": "a modern glass office lobby and meeting room seen through windows, business people working",
    "industry": "a large factory production line with engineers inspecting machines",
    "tech": "a semiconductor cleanroom and data center corridor with engineers in protective suits",
    "consumer": "a busy commercial shopping street with people carrying bags",
    "logistics": "a container port with cranes, trucks and workers",
    "city": "a wide city skyline with streets and traffic",
}
MOOD = {      # 지수 등락 → 분위기 (참고 글 4절)
    "strong_up": "clear bright morning, strong sunlight reflecting on glass buildings, fast moving energetic crowd",
    "mild": "soft overcast light, calm and steady atmosphere",
    "uncertain": "light fog between buildings, people busy but the far end of the scene hazy",
    "plunge": "dark evening, building lights still on, streets quieter than usual, cool blue tones, heavy mood",
    "rebound": "first light of dawn rising over a dark city, people starting to move again, warm light returning",
}
PLACE = {"US": "in an American city", "KR": "in Seoul, Korea"}

SAMPLES = [   # (파일, 시장, 소재, 분위기, 화면 제목, 설명)
    ("today-am", "US", "tech", "plunge", "11월 17일 아침 · 기술주 내림 뒤, 오늘 밤 엔비디아 실적",
     "오늘 실제 묶음 파일: S&P 500 −1.91% · 기술 −2.39%(가장 많이 내림) · 엔비디아 실적 → 소재 기술 · 분위기 급락"),
    ("strong-up", "US", "finance", "strong_up", "(예시) 크게 오른 날", "지수 +1% 이상 → 맑은 아침 · 빠른 출근 인파"),
    ("uncertain", "US", "corporate", "uncertain", "(예시) 방향 못 정한 날", "등락 작고 VIX 높음 → 안개"),
    ("plunge-city", "US", "city", "plunge", "(예시) 급락한 날 · 도시", "지수 −1.5% 이하 → 어두운 저녁 · 한산한 거리"),
    ("rebound", "US", "logistics", "rebound", "(예시) 반등한 날 · 물류", "전날 내림 뒤 오름 → 새벽빛"),
    ("kr-pm", "KR", "finance", "mild", "(예시) 저녁판 · 한국 마감", "저녁 21:00 편은 한국 장면"),
]


def prompt(market, subject, mood):
    return f"{SUBJECT[subject]} {PLACE[market]}, {MOOD[mood]}, {MASTER}"


def fetch(p, seed=1117):
    url = (f"https://image.pollinations.ai/prompt/{urllib.parse.quote(p)}"
           f"?model=flux&nologo=true&width={W}&height={H}&seed={seed}&referrer=www.newfact.app")
    for _ in range(3):
        try:
            r = requests.get(url, timeout=150, headers={"User-Agent": "alpha-scope-mock/1.0"})
            if r.status_code == 200 and len(r.content) > 10_000:
                return r.content
            print(f"  HTTP {r.status_code} · {len(r.content)}B")
        except Exception as e:  # noqa: BLE001
            print(f"  실패: {e}")
        time.sleep(50)
    return None


def build_images():
    os.makedirs(IMG, exist_ok=True)
    first = True
    for name, mk, sub, mood, *_ in SAMPLES:
        path = os.path.join(IMG, f"{name}.webp")
        if os.path.exists(path):
            continue
        if not first:
            time.sleep(50)
        first = False
        print(f"[그림] {name}")
        data = fetch(prompt(mk, sub, mood))
        if data:
            Image.open(io.BytesIO(data)).convert("RGB").save(path, "WEBP", quality=80)
        else:
            print("  → 못 받음")


def build_html():
    cards = []
    for name, mk, sub, mood, title, why in SAMPLES:
        path = os.path.join(IMG, f"{name}.webp")
        size = f"{os.path.getsize(path) / 1024:.0f}KB" if os.path.exists(path) else "—"
        img = (f'<img src="banner2/{name}.webp" alt="" style="width:100%;display:block;aspect-ratio:{W}/{H};object-fit:cover;border-radius:8px;">'
               if os.path.exists(path) else f'<div class="miss" style="aspect-ratio:{W}/{H}">그림 못 받음</div>')
        cards.append(
            f'<article class="post">{img}<p class="ai">AI 생성 이미지</p>'
            f'<h3>{title}</h3><p class="why">{why}</p>'
            f'<p class="tag">소재 <b>{sub}</b> · 분위기 <b>{mood}</b> · {"미국" if mk == "US" else "한국"} 장면 · {size}</p>'
            f'<details><summary>장면 설명</summary><code>{prompt(mk, sub, mood)}</code></details></article>')
    html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>시황 배너 목업 2</title><style>
body{{margin:0;background:#f5f6f8;color:#111;font-family:"Malgun Gothic",system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px 60px}}
h1{{font-size:22px;margin:0 0 6px}} .intro{{color:#333;font-size:15px;line-height:1.7;margin:0 0 20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px}}
.post{{border:1px solid #e2e8f0;border-radius:12px;padding:12px;background:#fff}}
.ai{{font-size:11px;color:#9ca3af;margin:4px 2px 0;text-align:right}}
.post h3{{font-size:17px;line-height:1.4;margin:8px 2px 6px}} .why{{font-size:14px;line-height:1.6;color:#333;margin:0 2px 6px}}
.tag{{font-size:12px;color:#6b7280;margin:0 2px 6px}} details{{font-size:12px;color:#6b7280;margin:0 2px}} code{{font-size:11px;word-break:break-all}}
.miss{{display:flex;align-items:center;justify-content:center;background:#f3f4f6;color:#9ca3af;border-radius:8px}}
</style></head><body><main>
<h1>알파스코프 시황 해설 — 배너 목업 2 · 경제의 하루</h1>
<p class="intro">마스터 화풍(경제 매거진 시네마틱 실사) 고정 + 소재 7갈래 × 분위기 5가지 × 시장(아침편 = 미국 장면, 저녁편 = 한국 장면)을 파이썬이 조합 — AI 글 모델 0.<br>
로고 · 간판 · 거래소 정면 · 황소상 없음, 사람은 멀리 · 뒷모습. 배너 아래 `AI 생성 이미지`(운영지침 4-6). 1200×630(공유 썸네일 비율).<br>
그림은 목업용 Pollinations(오른쪽 아래 워터마크) — 운영은 Workers AI FLUX schnell.</p>
<div class="grid">{''.join(cards)}</div>
</main></body></html>"""
    p = os.path.join(OUT, "banner-mock2.html")
    with open(p, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[목업] {p}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", action="store_true")
    if not ap.parse_args().html:
        build_images()
    build_html()
