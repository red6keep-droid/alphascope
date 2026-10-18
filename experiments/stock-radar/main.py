"""시총 TOP 10 1단계 — 수집 → 분석 → 목록 · 간단형 상세 HTML (게시는 아직 없음, doc/종목-레이더-기획.md 10-8).

    python experiments/stock-radar/main.py            # 받고 그리기
    python experiments/stock-radar/main.py --cached   # 받은 것(data/snapshot.json)으로 그리기만
결과 output/<티커>.html (본문) · output/mock_<티커>.html (블로그 테마를 입힌 미리보기).
"""

import os
import sys

import analyze
import collect
import render_pages

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    snap = collect.load() if "--cached" in sys.argv else collect.run()
    a = analyze.run(snap)
    pages = render_pages.write_all(a, OUT)
    print(f"[radar] {a['day']} · 페이지 {len(pages)}개 → {OUT}")
