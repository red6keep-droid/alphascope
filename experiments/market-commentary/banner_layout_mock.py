"""시황 배너 배치 목업 — 그림은 새로 만들지 않고 기존 그림만, 글 길이별로.

    python experiments/market-commentary/banner_layout_mock.py   # → output/banner-layout.html
"""
import io
import os
import sys
from contextlib import redirect_stdout

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import banner as B  # noqa: E402

OUT = os.path.join(B.BASE, "output")
IMG = os.path.join(OUT, "banner-layout")

BGS = [   # (이름, 파일, 분위기)
    ("오늘 아침 · Lucid (내린 날)", os.path.join(OUT, "banner-cf", "lucid-origin", "today-am.webp"), "plunge"),
    ("기본 배너 · 크게 오른 날 (밝은 사진)", os.path.join(B.DEFAULT_DIR, "strong_up.webp"), "strong_up"),
]
CASES = [   #: 짧음은 한 줄 · 30% 크게, 아주 김은 없음(글자 수 제한 — 띄어쓰기 빼고 줄마다 한글 10자 · 요약 20자)
    ("보통 · 두 줄", "줄마다 한글 10자 안 — 사양 크기(79 · 80px) 그대로",
     {"titles": [["기술주 내림 뒤", "엔비디아 실적 기다림"]], "keys": ["미국 기술 업종 약세", "반도체 관망", "한국장 첫 반응"]}),
    ("짧음 → 한 줄", "두 줄을 이어 104px(30% 크게) 한 줄에 들어가면 한 줄 — 앞 흰색 · 뒤 방향 색",
     {"titles": [["기술주", "반등"]], "keys": ["반도체 강세", "한국장 첫 반응"]}),
    ("짧은 한 줄 후보", "후보가 한 줄이고 104px 에 들어가면 그대로 크게",
     {"titles": [["연준 금리 동결"]], "keys": ["금리 보합", "달러 약세"]}),
    ("글자 제한 끝", "띄어쓰기 빼고 줄마다 한글 10자 · 요약 20자 — 줄이지 않고 들어감",
     {"titles": [["미국 기술주 이틀째 급락", "실적 앞둔 반도체 관망"]], "keys": ["미국 기술 업종 약세", "반도체 관망", "한국장 첫 반응"]}),
    ("제목 후보 3개", "좋은 것부터 — 1번이 제한을 넘어 길면 2번",
     {"titles": [["미국 기술주가 이틀째 크게 내리면서", "엔비디아 실적 앞두고 시장 전체가 관망"], ["기술주 이틀째 급락", "엔비디아 실적 기다림"], ["기술주 급락", "실적 대기"]],
      "keys": ["미국 기술 업종 약세", "반도체 관망", "한국장 첫 반응"]}),
    ("후보 없음 → 글 제목에서", "수집기 banner 칸이 없는 날 — 글 제목(그날 주제)의 숫자 없는 앞 구절 (글 제목은 길이 제한 밖이라 줄어듦)",
     B.banner_text({"title": "앤트로픽 IPO와 엔비디아 악재에 기술주 급락, 나스닥 2.47% 하락"})),
]


def main():
    os.makedirs(IMG, exist_ok=True)
    cards = []
    for bi, (bname, bpath, mood) in enumerate(BGS):
        bg = Image.open(bpath).convert("RGB")
        sc = {"mood": mood, "date": "2026-11-17", "slot": "am"}
        for ci, (cname, why, banner) in enumerate(CASES):
            buf = io.StringIO()
            with redirect_stdout(buf):
                im = B.compose(bg, sc, banner)
            name = f"b{bi}-c{ci}.webp"
            im.save(os.path.join(IMG, name), "WEBP", quality=82)
            logs = "<br>".join(x.replace("[banner] ", "") for x in buf.getvalue().splitlines()) or "줄임 · 덜어냄 없음"
            cards.append(f'<figure><img src="banner-layout/{name}" alt=""><figcaption><b>{cname}</b> · {bname}<small>{why}</small>'
                         f'<small class="log">{logs}</small></figcaption></figure>')
    html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>시황 배너 배치</title><style>
body{{margin:0;background:#f5f6f8;color:#111;font-family:"Malgun Gothic",system-ui,sans-serif}}
main{{max-width:1900px;margin:0 auto;padding:24px 16px 60px}}
h1{{font-size:22px;margin:0 0 6px}}.intro{{font-size:15px;line-height:1.7;color:#333;margin:0 0 18px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:18px}}
figure{{margin:0;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:10px}}
img{{width:100%;display:block;border-radius:6px}}figcaption{{font-size:15px;margin:10px 2px 2px}}
small{{display:block;color:#6b7280;font-size:13px;margin-top:3px}}.log{{color:#9ca3af;font-size:12px}}
</style></head><body><main>
<h1>시황 배너 — 배치 (900×350, 2026-11-17 사양)</h1>
<p class="intro">그림은 새로 만들지 않고 기존 그림을 사진 상자 917×463 에 맞춰 줄여 왼쪽 위에 둠(오른쪽 · 아래는 잘림).
주요 제목 79px #F5F6F8 (76) · 강조 제목 80px 방향 색 (150) · 시장 요약 32px #DAE1EA (260), 왼쪽 68. 폰트 = 강원교육튼튼.<br>
길이 기준(11-17): 짧으면 한 줄 · 30% 크게(104px) · 보통은 두 줄 사양 크기 · 글자 수 제한 = 띄어쓰기 빼고 줄마다 한글 10자 · 요약 20자(수집기). 제한을 넘는 글(수집기 실수 · 글 제목 대체)은 빼지 않고 칸에 들어갈 때까지 줄임.</p>
<div class="grid">{''.join(cards)}</div></main></body></html>"""
    with open(os.path.join(OUT, "banner-layout.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[배치] {os.path.join(OUT, 'banner-layout.html')} · {len(cards)}장")


if __name__ == "__main__":
    main()
