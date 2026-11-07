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


def record(a, news):
    import datetime
    import stock_records   # experiments/ — render_pages 가 경로를 넣는다
    today = datetime.datetime.now(stock_records.KST).strftime("%Y-%m-%d")
    rows = []
    for s in a["stocks"]:
        try:
            picks = [p for p in render_pages.PICKS if p["market"] == "US" and p["ticker"] == s["sym"]]
            rows += stock_records.verdict_rows(today, "radar", s, render_pages.verdict_items(s), picks)
        except Exception as e:  # noqa: BLE001 — 기록은 게시를 막지 않는다
            print(f"::warning::[radar] {s['sym']} 기록 실패: {e!r}")
    stock_records.save(os.path.join(os.environ["STATE_DIR"], "radar"), rows, stock_records.news_rows(news))

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cached = "--cached" in sys.argv
    snap = collect.load() if cached else collect.run()
    extra = (collect_extra.load() if cached else collect_extra.run(snap)) or {}
    news = collect_news.load() if cached else collect_news.run()
    a = analyze.run(snap)
    import industry_us   # 업계 카드 — FRED (2026-11-01 사용자 P268, 실패해도 페이지는 만든다)
    try:
        fred = industry_us.load() if cached else industry_us.fetch()
    except Exception as e:  # noqa: BLE001
        print(f"[radar] 업계 자료 실패: {str(e)[:120]}")
        fred = {}
    for s in a["stocks"]:
        analyze_tabs.build(s, snap, extra)
        s["industry_us"] = industry_us.build(s["sym"], fred)
    if not cached:   # 소송 일정 — 추적 사건 법원 문서 (P270, 실패해도 페이지는 만든다)
        import court
        try:
            court.fetch(a["day"])
        except Exception as e:  # noqa: BLE001
            print(f"[radar] 소송 일정 실패: {str(e)[:120]}")
    if not cached and os.environ.get("STATE_DIR"):   # 기록 먼저, 렌더링 나중 (2026-11-07, 데이터-기록-계획 3부 10-1 의 5 — 렌더가 죽어도 그날 기록은 남게)
        try:
            record(a, news)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[radar] 기록 저장 실패 (페이지는 계속): {e!r}")
    pages = render_pages.write_all(a, OUT, snap, news, summarize=not cached)   # 목록 기사 요약(팝업) — 받기 실행만, --cached 는 캐시만 (P341)
    print(f"[radar] {a['day']} · 페이지 {len(pages)}개 → {OUT}")
