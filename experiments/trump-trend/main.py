"""트럼프 SNS 트렌드 파이프라인 실행 (그림자 모드 — 어디에도 게시하지 않는다).

사용법 (리포 루트에서):
    python experiments/trump-trend/main.py                 # 전체: 수집 → 가격 → 캘린더 → 분류 → 이벤트 → 스터디 → 집계 → MD
    python experiments/trump-trend/main.py --skip-classify # Gemini 호출 없이 (수집·가격·집계만)
    python experiments/trump-trend/main.py --max-batches 5 # 분류를 5배치(75건)까지만
    python experiments/trump-trend/main.py --narrate       # 마지막에 Gemini 서술까지

흐름:
    collect_posts   → trump_posts (새 id만, noise_reason)
    collect_prices  → daily_bars (일봉, 첫 실행 2y 백필)
    calendar_macro  → macro_calendar (FOMC 정적 + FRED + 실적)
    classify_posts  → ai_* 컬럼 (배치 Gemini, 항목별 검증)
    cluster_events  → trump_events (전부 재생성)
    event_study     → event_reactions (종가 기준, SPY 대비 초과)
    aggregate       → output/trump_analysis.json
    narrate (선택)  → output/narrative.json
    render_report   → output/trump_report.md
"""

import argparse
import os
import sys
import time

from dotenv import load_dotenv

import aggregate
import calendar_macro
import classify_posts
import cluster_events
import collect_posts
import collect_prices
import config
import db
import event_study
import render_report
import state_io

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _step(n, total, title):
    print("=" * 60)
    print(f"[{n}/{total}] {title}")
    print("=" * 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-collect", action="store_true")
    ap.add_argument("--skip-prices", action="store_true")
    ap.add_argument("--skip-calendar", action="store_true")
    ap.add_argument("--skip-classify", action="store_true")
    ap.add_argument("--backfill-prices", action="store_true", help="일봉 2년치 강제 재수집")
    ap.add_argument("--max-batches", type=int, default=config.CLASSIFY_MAX_BATCHES_PER_RUN)
    ap.add_argument("--since-days", type=int, default=config.CLASSIFY_SINCE_DAYS)
    ap.add_argument("--narrate", action="store_true", help="Gemini 서술 생성")
    ap.add_argument("--refilter", action="store_true", help="사전 필터 규칙 변경 후 전체 행 noise_reason 재계산")
    ap.add_argument("--import-state", metavar="PATH", help="수집 직후 분류 결과 JSONL을 DB에 붙인다 (GitHub Actions용)")
    ap.add_argument("--export-state", metavar="PATH", help="분류 직후 분류 결과를 JSONL로 내보낸다 (GitHub Actions용)")
    args = ap.parse_args()

    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    load_dotenv(os.path.join(config.BASE_DIR, ".env"))

    t0 = time.time()
    conn = db.connect()
    total = 8

    _step(1, total, "게시물 수집 (CNN archive)")
    if args.refilter:
        collect_posts.refilter(conn)
    if args.skip_collect:
        print("건너뜀")
    else:
        try:
            collect_posts.collect(conn)
        except Exception as e:  # noqa: BLE001
            print(f"[posts] 실패 — 기존 DB로 계속: {e}")
    if args.import_state:
        state_io.import_state(conn, args.import_state)

    _step(2, total, "일봉 수집 (yfinance)")
    if args.skip_prices:
        print("건너뜀")
    else:
        try:
            collect_prices.collect(conn, force_backfill=args.backfill_prices)
        except Exception as e:  # noqa: BLE001
            print(f"[prices] 실패 — 기존 일봉으로 계속: {e}")

    _step(3, total, "거시 캘린더")
    if args.skip_calendar:
        print("건너뜀")
    else:
        try:
            calendar_macro.refresh(conn)
        except Exception as e:  # noqa: BLE001
            print(f"[calendar] 실패 — 기존 캘린더로 계속: {e}")

    _step(4, total, "Gemini 분류")
    if args.skip_classify:
        print("건너뜀")
    else:
        classify_posts.classify(conn, since_days=args.since_days, max_batches=args.max_batches)
    if args.export_state:
        # 분류 직후 바로 내보낸다 — 뒤 단계가 실패해도 Gemini 호출 결과는 남는다.
        state_io.export_state(conn, args.export_state)

    _step(5, total, "이벤트 클러스터링")
    cluster_events.build(conn)

    _step(6, total, "이벤트 스터디 (일 단위)")
    event_study.build(conn)

    _step(7, total, "집계")
    aggregate.build(conn)

    _step(8, total, "서술 + 렌더")
    narrative_path = os.path.join(config.OUTPUT_DIR, "narrative.json")
    if args.narrate:
        import narrate
        try:
            narrate.narrate()
        except Exception as e:  # noqa: BLE001
            print(f"[narrate] 실패 — 서술 없이 렌더: {e}")
            if os.path.exists(narrative_path):
                os.remove(narrative_path)
    elif os.path.exists(narrative_path):
        os.remove(narrative_path)   # 지난 실행의 문장이 오늘 표에 붙지 않게
    path = render_report.render()

    conn.close()
    print(f"\n완료 — {time.time() - t0:.0f}s · {path}")


if __name__ == "__main__":
    main()
