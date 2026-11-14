"""간단 정보 고정 페이지 목업 — 실제 블로그처럼 quick_page.js 가 카드 조각을 받아 끼워 넣는다 (2026-11-14).

    .venv/bin/python experiments/stock-quick/mock_quick_page.py --data DIR     # DIR = collect_quick.py --out 결과

output/quick-data/ 에 예시 종목 조각만 복사하고, 종목마다 목업 페이지 mock_qpage_<코드>.html 을 만든다(같은 JS, 기본 종목만 다름).
목업 서버(experiments/mock_server.py, 8800)로 열어야 fetch 가 된다 — 파일을 바로 열면 브라우저가 막는다.
"""

import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, EXP)
import design_kit as dk  # noqa: E402
import candle_chart as CC  # noqa: E402

OUT = os.path.join(HERE, "output")
# 예시 — 미국 간단 · 미국 이름 고친 것 · 한국(게임 · 해운 · 조선 = 업계 고침표 · 화학 = 업계 카드 없음) · 1년 안 된 종목 · 없는 코드
SAMPLES = [("us", "UBER"), ("us", "SBUX"), ("us", "GPC"), ("kr", "259960"), ("kr", "011200"), ("kr", "010140"), ("kr", "009830"),
           ("us", "FDXF"), ("us", "ZZZZ")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    a = ap.parse_args()
    dst = os.path.join(OUT, "quick-data")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    for d in ("us", "kr"):
        os.makedirs(os.path.join(dst, d), exist_ok=True)
    for fn in ("version.json", "bench.json"):
        if os.path.exists(os.path.join(a.data, fn)):
            shutil.copy(os.path.join(a.data, fn), os.path.join(dst, fn))
    js = open(os.path.join(HERE, "quick_page.js"), encoding="utf-8").read()
    for d, code in SAMPLES:
        src = os.path.join(a.data, d, code + ".html")
        if os.path.exists(src):
            shutil.copy(src, os.path.join(dst, d, code + ".html"))
        body = (f'<div id="as-quick" data-local="quick-data/" data-default="{code}" data-list="mock_all_stocks.html"></div>'
                f'<script>{js}</script>' + CC.SCRIPT)   # 발행 본문(publish_quick_page.body)과 같은 순서
        p = dk.write_mock(body, os.path.join(OUT, f"mock_qpage_{code}.html"), f"간단 정보 ({code})")
        print("만듦:", p)


if __name__ == "__main__":
    main()
