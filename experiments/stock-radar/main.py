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
    record_broker(a, today)


def record_broker(a, today):
    """증권사별 등급 · 목표가 변경 → radar/records/broker.
    날마다 = 이미 받은 30일 창(s["broker"])에서 처음 보는 줄만. 종목마다 한 번 = 야후 이력 전부를 담는다(첫 담기 — 종목이 새로 들어와도 그 종목만).
    담은 종목은 records/broker/_backfill.json 에 적는다. 첫 담기가 실패한 종목은 적지 않아 다음 실행에 다시."""
    import json
    import time
    import stock_records
    state = os.path.join(os.environ["STATE_DIR"], "radar")
    mark = os.path.join(state, "records", "broker", "_backfill.json")
    try:
        with open(mark, encoding="utf-8") as f:
            done = set(json.load(f).get("syms") or [])
    except (OSError, ValueError):
        done = set()
    rows, filled = [], []
    for s in a["stocks"]:
        sym, name = s["sym"], s.get("name")
        rows += stock_records.broker_rows(sym, name, s.get("broker"), today)
        if sym in done:
            continue
        try:
            rows += stock_records.broker_rows(sym, name, collect_extra.broker_history(sym), today, backfill=True)
            filled.append(sym)
        except Exception as e:  # noqa: BLE001 — 다음 실행에 다시
            print(f"::warning::[radar] {sym} 증권사 이력 첫 담기 실패: {str(e)[:120]}")
        time.sleep(0.5)
    n = stock_records.save_broker(state, rows)
    if n is None:
        print("::warning::[radar] 증권사 변경 기록 쓰기 실패 — 첫 담기 표시를 남기지 않음(다음 실행에 다시)")
        return
    if filled:
        os.makedirs(os.path.dirname(mark), exist_ok=True)
        with open(mark, "w", encoding="utf-8") as f:
            json.dump({"syms": sorted(done | set(filled)), "updated": today}, f, ensure_ascii=False)
    print(f"[radar] 증권사 변경 기록 {n}줄 새로 · 첫 담기 {len(filled)}종목")

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cached = "--cached" in sys.argv
    snap = collect.load() if cached else collect.run()
    extra = (collect_extra.load() if cached else collect_extra.run(snap)) or {}
    if not cached:   # 빈 값 막기 — 야후가 오류 없이 빈 값을 줄 때. 실패해도 페이지는 만든다
        try:
            import data_guard
            import universe as U
            data_guard.guard_run(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"), "미국 종목", [c[0] for c in U.CANDIDATES],
                                 snap, extra, snap_path=collect.SNAP, extra_path=collect_extra.EXTRA)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[radar] 빈 값 검사 실패 (예전처럼 계속): {e!r}")
    news = collect_news.load() if cached else collect_news.run()
    import peer_cards   # 같은 업종 S&P 500 과 견주는 카드 넷 — 실패해도 지난 값 · 없으면 카드 없이
    try:
        peer_cards.DATA = peer_cards.load() if cached else peer_cards.collect(snap)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[radar] 업종 비교 수집 실패 — 지난 값: {e!r}")
        peer_cards.DATA = peer_cards.load()
    peer_cards.REV = (extra.get("revenue") or {}).get("series") or {}
    a = analyze.run(snap)
    import industry_us   # 업계 카드 — FRED
    try:
        fred = industry_us.load() if cached else industry_us.fetch()
    except Exception as e:  # noqa: BLE001
        print(f"[radar] 업계 자료 실패: {str(e)[:120]}")
        fred = {}
    for s in a["stocks"]:
        analyze_tabs.build(s, snap, extra)
        s["industry_us"] = industry_us.build(s["sym"], fred)
    if not cached and os.environ.get("RADAR_COURT") != "0":   # 소송 일정 — 추적 사건 법원 문서 (P270, 실패해도 페이지는 만든다). 워크플로는 게시 뒤 단계에서(RADAR_COURT=0, 2026-11-20)
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
    if not cached and os.environ.get("STATE_DIR"):   # 의견 탭 요약 문단이 오늘 보여 준 값(신호 · 평균 목표가 · 방송 의견 id) → radar/records/opinion — 내일 화면의 비교 대상
        try:
            render_pages.OC.save(os.path.join(os.environ["STATE_DIR"], "radar"))
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[radar] 의견 요약 기록 실패 (페이지는 계속): {e!r}")
    print(f"[radar] {a['day']} · 페이지 {len(pages)}개 → {OUT}")
