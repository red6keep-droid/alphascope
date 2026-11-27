"""한국 종목 — 수집 → 분석 → 목록 · 상세 HTML (기획 11절).
    python experiments/kr-stocks/main_kr.py            # 받고 그리기 (yfinance · ECOS)
    python experiments/kr-stocks/main_kr.py --cached   # 받은 것(data/*.json)으로 그리기만
결과 output/<종목코드>.html (본문) · output/mock_<종목코드>.html (블로그 테마를 입힌 미리보기) · output/images/ (가격 그래프).
"""
import os
import sys

import analyze_kr
import collect_kr
import collect_kr_extra
import render_kr

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def record(a):
    import datetime
    import stock_records   # experiments/ — render_kr 가 경로를 넣는다
    today = datetime.datetime.now(stock_records.KST).strftime("%Y-%m-%d")
    rows = []
    for s in a["stocks"]:
        try:
            picks = [p for p in render_kr.PICKS if p["market"] == "KR" and p["ticker"].split(".")[0] == s["code"]]
            rows += stock_records.verdict_rows(today, "kr", s, render_kr.verdict_items(s), picks)
        except Exception as e:  # noqa: BLE001 — 기록은 게시를 막지 않는다
            print(f"::warning::[kr] {s['sym']} 기록 실패: {e!r}")
    stock_records.save(collect_kr.DATA, rows)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cached = "--cached" in sys.argv
    snap, flows, hist = collect_kr.load() if cached else collect_kr.run()
    if snap is None:
        print("[kr] 시세 없음 — 이 실행은 자료 지연 (페이지를 만들지 않는다)")
        sys.exit(0)
    try:   # 실적과 기대 · 캘린더 재료 — 실패해도 페이지는 만든다 (그 탭은 `판단 유보`)
        extra = collect_kr_extra.load() if cached else collect_kr_extra.run()
    except Exception as e:  # noqa: BLE001
        print(f"[kr] 탭 재료 실패: {str(e)[:120]}")
        extra = {}
    if not cached:   # 빈 값 막기 — 미국과 같은 틀. 시총 · 일봉은 analyze 전에 메워야 하지만 일봉은 메우지 않고 건너뛰기만이라 여기서 함께
        try:
            import data_guard
            data_guard.guard_run(collect_kr.DATA, "한국 종목", [c[0] for c in collect_kr.U.CANDIDATES], snap, extra, nested=("analysts", "eps"),
                                 snap_path=collect_kr.SNAP, extra_path=collect_kr_extra.EXTRA)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[kr] 빈 값 검사 실패 (예전처럼 계속): {e!r}")
    a = analyze_kr.run(snap, flows, hist)   # 빈 값을 메운 뒤에 (시총)
    if not cached:   # 실적 발표일 = DART 잠정실적 공시 (2026-10-31) — 실패하면 지난 캐시
        try:
            import collect_kr_earn_dart
            collect_kr_earn_dart.run()
        except (Exception, SystemExit) as e:  # noqa: BLE001
            print(f"[kr] DART 실적일 실패: {str(e)[:120]}")
        try:   # 최근 공시는?. 오늘 · 어제 목록만 다시, 실패하면 지난 캐시
            import collect_kr_dart
            collect_kr_dart._save(collect_kr_dart.FILINGS, collect_kr_dart.filings(collect_kr_dart.FILINGS, {c[0].split(".")[0] for c in collect_kr.U.CANDIDATES}))
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[kr] DART 공시 목록 실패 (지난 캐시로): {e!r}")
        try:   # 잠정실적 숫자(공시 원문, AI 0) · 보고서 `매출 및 수주상황`(Gemini lite, 정식만 하루 30건) — 실적 탭 카드. 실패하면 지난 캐시
            import collect_kr_dart
            import collect_kr_fin
            import dart_biz
            import dart_prelim
            codes = [c[0].split(".")[0] for c in collect_kr.U.CANDIDATES]
            cmap = collect_kr_dart.corp_codes(collect_kr_dart._key())
            dart_prelim.run(codes, cmap, collect_kr_dart.filings_by_code(collect_kr_dart._load(collect_kr_dart.FILINGS)))
            if os.environ.get("KR_BIZ_AFTER") != "1":   # 워크플로는 새벽 quick-dart.yml biz 잡(biz_after.py)으로. 손으로 돌릴 땐 여기서
                dart_biz.run(codes, cmap, collect_kr_dart._load(collect_kr_fin.CACHE))
            else:
                print("[kr] 보고서 `매출 및 수주상황` 읽기는 새벽 실행으로 — 이번 화면은 지난 캐시")
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[kr] 잠정실적 · 사업 부문 실패 (지난 캐시로): {e!r}")
    if not cached:   # 기록 먼저, 렌더링 나중 (2026-11-07, 데이터-기록-계획 3부 10-1 의 5) — 카드 판정 · 애널리스트 · 방송 의견 → data/records (kr-state, A5-4)
        try:
            record(a)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[kr] 기록 저장 실패 (페이지는 계속): {e!r}")
    pages = render_kr.write_all(a, OUT, snap, extra=extra)
    if not cached:   # 의견 탭 요약 문단이 오늘 보여 준 값(신호 · 평균 목표가 · 방송 의견 id) → data/records/opinion — 내일 화면의 비교 대상
        try:
            render_kr.OC.save(render_kr.OP_STATE)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[kr] 의견 요약 기록 실패 (페이지는 계속): {e!r}")
    # 오늘(KST) 봉이 있나 — 휴장일 · 데이터 지연이면 0. 워크플로는 1일 때만 게시한다 (수동 실행은 강제 가능)
    import datetime
    from zoneinfo import ZoneInfo
    fresh = a["day"] == datetime.datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
    with open(os.path.join(OUT, "fresh.txt"), "w", encoding="utf-8") as f:
        f.write("1" if fresh else "0")
    print(f"[kr] {a['day']} · 페이지 {len(pages)}개 → {OUT}" + ("" if fresh else " · 오늘 봉 없음(휴장일 또는 지연) — 게시 건너뜀 표시"))
