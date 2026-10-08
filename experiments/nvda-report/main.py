"""엔비디아 데일리 리포트 실행 — ①단계 뼈대 (Gemini 없음, 그림자 모드, 어디에도 게시하지 않는다).

사용법 (리포 루트에서):
    python experiments/nvda-report/main.py                  # 전체: 일봉 → 캘린더 → 상태판(옵션·추정치·애널리스트·보유) → EDGAR → 판정 → MD
    python experiments/nvda-report/main.py --skip-options   # 옵션 체인 없이 (빠른 점검)
    python experiments/nvda-report/main.py --skip-edgar     # EDGAR 없이
    python experiments/nvda-report/main.py --day 2026-10-06 # 특정 거래일 기준으로 판정·렌더 (수집은 그대로)
    python experiments/nvda-report/main.py --skip-classify  # Gemini 없이 (수집·중복 제거·판정·렌더)
    python experiments/nvda-report/main.py --skip-courts    # CourtListener 없이 (느리다)

흐름:
    collect_market.collect_bars   → daily_bars (일봉 5심볼, 첫 실행 2y)
    collect_calendar.refresh      → calendar (FOMC·FRED·실적 12종목·OPEX/INDEX·정적 행사)
    collect_market.collect_state  → option_snapshots · daily_state[day] · items(analyst)
    collect_edgar.collect         → items(form4·8k·10q·10k)
    collect_feeds · collect_regulatory → items(newsroom·blog·news·fedreg·court)
    dedupe.run · classify_items   → prefilter_reason · ai_* (Gemini)
    judge.build                   → daily_state 기술 칸 백필 · output/nvda_analysis.json
    render_report.render          → output/nvda_report.md · title.txt
"""

import argparse
import datetime
import os
import sys
import time

from dotenv import load_dotenv

import collect_calendar
import collect_edgar
import collect_feeds
import collect_market
import collect_regulatory
import config
import db
import dedupe
import judge
import labels
import render_report

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

KST = datetime.timezone(datetime.timedelta(hours=9))


def _step(n, total, title):
    print("=" * 60)
    print(f"[{n}/{total}] {title}")
    print("=" * 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-prices", action="store_true")
    ap.add_argument("--skip-calendar", action="store_true")
    ap.add_argument("--skip-market", action="store_true", help="상태판 수집(옵션·추정치·애널리스트·보유) 건너뜀")
    ap.add_argument("--skip-options", action="store_true", help="옵션 체인만 건너뜀")
    ap.add_argument("--skip-edgar", action="store_true")
    ap.add_argument("--skip-feeds", action="store_true", help="뉴스룸·블로그·CNBC·Google News·연방관보·법원 수집 건너뜀")
    ap.add_argument("--skip-courts", action="store_true", help="CourtListener만 건너뜀 (100초 넘게 걸린다)")
    ap.add_argument("--skip-classify", action="store_true", help="Gemini 분류 건너뜀")
    ap.add_argument("--max-batches", type=int, default=config.CLASSIFY_MAX_BATCHES_PER_RUN)
    ap.add_argument("--backfill-prices", action="store_true", help="일봉 2년치 강제 재수집")
    ap.add_argument("--edgar-days", type=int, default=None, help="첫 실행 EDGAR 백필 일수 (기본 config)")
    ap.add_argument("--day", metavar="YYYY-MM-DD", help="기준 거래일 (기본: 마지막 일봉)")
    args = ap.parse_args()

    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    load_dotenv(os.path.join(config.BASE_DIR, ".env"))

    t0 = time.time()
    conn = db.connect()
    total = 8
    run_date = datetime.datetime.now(KST).date().isoformat()

    _step(1, total, "일봉 수집 (yfinance)")
    if args.skip_prices:
        print("건너뜀")
    else:
        try:
            collect_market.collect_bars(conn, force_backfill=args.backfill_prices)
        except Exception as e:  # noqa: BLE001
            print(f"[prices] 실패 — 기존 일봉으로 계속: {e}")
    day = args.day or collect_market.last_bar_day(conn)
    if not day:
        print("일봉이 없다 — 중단")
        sys.exit(1)
    print(f"기준 거래일 {day} · 실행일(KST) {run_date}")

    _step(2, total, "캘린더 (FOMC · FRED · 실적 12종목 · OPEX/INDEX · 행사)")
    if args.skip_calendar:
        print("건너뜀")
    else:
        try:
            collect_calendar.refresh(conn, datetime.date.fromisoformat(day))
        except Exception as e:  # noqa: BLE001
            print(f"[calendar] 실패 — 기존 캘린더로 계속: {e}")

    _step(3, total, "상태판 수집 (옵션 · 추정치 · 애널리스트 · 보유/공매도)")
    if args.skip_market:
        print("건너뜀")
    else:
        try:
            collect_market.collect_state(conn, day, next_earnings_day=collect_calendar.next_of(conn, "EARNINGS", day, config.SYMBOL),
                                         skip_options=args.skip_options)
        except Exception as e:  # noqa: BLE001
            print(f"[state] 실패 — 기존 상태판으로 계속: {e}")

    _step(4, total, "EDGAR (Form 4 · 8-K · 10-Q · 10-K)")
    if args.skip_edgar:
        print("건너뜀")
    else:
        try:
            collect_edgar.collect(conn, since_days=args.edgar_days)
        except Exception as e:  # noqa: BLE001
            print(f"[edgar] 실패 — 기존 공시로 계속: {e}")

    _step(5, total, "문서 수집 (뉴스룸 · 블로그 · CNBC · Google News · 연방관보 · 법원)")
    if args.skip_feeds:
        print("건너뜀")
    else:
        try:
            collect_feeds.collect(conn)
        except Exception as e:  # noqa: BLE001
            print(f"[feeds] 실패 — 계속: {e}")
        try:
            collect_regulatory.collect(conn, skip_courts=args.skip_courts)
        except Exception as e:  # noqa: BLE001
            print(f"[regulatory] 실패 — 계속: {e}")

    _step(6, total, "중복 제거 + Gemini 분류")
    dedupe.run(conn)
    if args.skip_classify:
        print("분류 건너뜀")
    else:
        import classify_items
        try:
            classify_items.classify(conn, max_batches=args.max_batches)
        except Exception as e:  # noqa: BLE001
            print(f"[classify] 실패 — 분류 없이 계속: {e}")
    labels.reapply(conn)   # 보정 규칙을 과거 행에도 (멱등)

    _step(7, total, "판정 (이벤트 · 상태판 · 다가오는 것 · 점검표)")
    judge.build(conn, day, run_date)

    _step(8, total, "렌더 (MD)")
    path = render_report.render()

    conn.close()
    print(f"\n완료 — {time.time() - t0:.0f}s · {path}")


if __name__ == "__main__":
    main()
