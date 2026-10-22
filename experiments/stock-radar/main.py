"""시총 TOP 10 — 수집 → 분석 → 목록 · 간단형 상세 HTML (게시는 아직 없음, doc/기획/종목-레이더-기획.md 10-8).

    python experiments/stock-radar/main.py            # 받고 그리기 (일봉 · 추가 재료 · 뉴스 수집 · 분류)
    python experiments/stock-radar/main.py --cached   # 받은 것(data/*.json)으로 그리기만
결과 output/<티커>.html (본문) · output/mock_<티커>.html (블로그 테마를 입힌 미리보기) · output/images/ (가격 그래프).
"""

import os
import sys

import analyze
import analyze_tabs
import collect
import collect_extra
import collect_news
import render_pages

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cached = "--cached" in sys.argv
    snap = collect.load() if cached else collect.run()
    extra = (collect_extra.load() if cached else collect_extra.run(snap)) or {}
    news = collect_news.load() if cached else collect_news.run()
    a = analyze.run(snap)
    for s in a["stocks"]:
        analyze_tabs.build(s, snap, extra)
    pages = render_pages.write_all(a, OUT, snap, news)
    print(f"[radar] {a['day']} · 페이지 {len(pages)}개 → {OUT}")
