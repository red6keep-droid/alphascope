"""인물 발언 레이더 전체 실행 (기획 6절): 상태 불러오기 → 수집 → 인용 추출 → 분류 → 집계 → 서술 → 렌더 → 상태 내보내기 → 게시.

    python main.py                       # 로컬 전체 (dry-run 게시)
    python main.py --state output/state  # CI: 상태 폴더에서 불러와 다시 내보낸다
    python main.py --publish             # 실제 게시 — 사용자 확인 뒤에만
"""

import argparse
import os
import sys

from dotenv import load_dotenv

import aggregate
import classify
import collect
import config
import db
import extract
import publish
import render_html
import state_io


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", help="상태 폴더 (statements.jsonl)")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--no-llm", action="store_true", help="추출 · 분류 · 서술을 건너뛴다")
    a = ap.parse_args()
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    conn = db.connect()
    state_file = os.path.join(a.state, "statements.jsonl") if a.state else None
    if state_file:
        state_io.import_state(conn, state_file)
    print("[1/7] 수집"); collect.collect(conn)
    print("[2/7] 인용 추출"); extract.run(conn, use_llm=not a.no_llm)
    if state_file:
        state_io.export_state(conn, state_file)   # LLM 결과를 바로 남긴다 — 뒤 단계가 실패해도
    print("[3/7] 분류")
    if not a.no_llm:
        classify.classify(conn, classify._since(config.COLLECT_SINCE_HOURS))
    if state_file:
        state_io.export_state(conn, state_file)
    print("[4/7] 집계"); radar = aggregate.build(conn)
    narrative_path = os.path.join(config.OUTPUT_DIR, "narrative.json")
    if os.path.exists(narrative_path):
        os.remove(narrative_path)   # 지난 실행의 문장이 오늘 카드에 붙지 않게
    print("[5/7] 서술")
    if radar["event_count"] and not a.no_llm:
        import narrate
        narrate.narrate()
    print("[6/7] 렌더"); render_html.render()
    print("[7/7] 게시" + ("" if a.publish else " — dry-run")); publish.publish(do_publish=a.publish)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
