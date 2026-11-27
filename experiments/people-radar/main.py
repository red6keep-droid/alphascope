"""인물 발언 레이더 전체 실행 (기획 6절): 상태 불러오기 → 수집 → 인용 추출 → 분류 → 집계 → 서술 → 렌더 → 상태 내보내기 → 게시.

    python main.py                       # 로컬 전체 (dry-run 게시)
    python main.py --state output/state  # CI: 상태 폴더에서 불러와 다시 내보낸다
    python main.py --publish             # 실제 게시 — 사용자 확인 뒤에만
    python main.py --state output/state --madmoney-only --publish   # 매드머니 갱신 — 그날 회차를 아침 글에 붙인다 (2026-11-20)
"""

import argparse
import datetime
import json
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

sys.path.append(os.path.join(config.BASE_DIR, ".."))   # 뒤에 붙인다 — 이쪽 모듈 이름을 가리지 않게
import ops_log  # noqa: E402,F401  — 운영 기록 (experiments/ops_log.py, 2026-10-23)
import record_store  # noqa: E402  — 신호 누적 (experiments/record_store.py, 2026-10-22). statements.jsonl 은 30일만 남아 신호는 따로 쌓는다


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", help="상태 폴더 (statements.jsonl)")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--no-llm", action="store_true", help="추출 · 분류 · 서술을 건너뛴다")
    ap.add_argument("--madmoney-only", action="store_true", help="매드머니 갱신: 그날 회차만 받아 아침 글에 붙인다 (AI = 새 카드 서술만)")
    a = ap.parse_args()
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    conn = db.connect()
    state_file = os.path.join(a.state, "statements.jsonl") if a.state else None
    if state_file:
        state_io.import_state(conn, state_file)
    if a.madmoney_only:
        return madmoney_update(conn, a, state_file)
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
    if a.state:
        _v, _i = record_store.radar_rows(radar, render_html.today_kst())
        record_store.append(a.state, "verdicts", _v)
        record_store.append(a.state, "issues", _i)
    narrative_path = os.path.join(config.OUTPUT_DIR, "narrative.json")
    if os.path.exists(narrative_path):
        os.remove(narrative_path)   # 지난 실행의 문장이 오늘 카드에 붙지 않게
    print("[5/7] 서술")
    if radar["event_count"] and not a.no_llm:
        import narrate
        narrate.narrate()
    print("[6/7] 렌더"); render_html.render()
    print("[7/7] 게시" + ("" if a.publish else " — dry-run")); publish.publish(do_publish=a.publish)
    import stock_mentions   # 종목 페이지 · 미국 증시 리포트용 발언 — 게시 뒤(그 글 주소를 `○○ 발언 더 보기` 에 쓴다, P371). 상태 폴더 → radar-state
    stock_mentions.update(os.path.join(config.OUTPUT_DIR, "radar.json"), narrative_path, os.path.join(a.state, "people_mentions.json") if a.state else stock_mentions.OUT,
                          post_url_path=os.path.join(config.OUTPUT_DIR, "post_url.txt") if a.publish else None)


def _madmoney_ids(radar):
    """radar.json 신호 가운데 매드머니가 대표인 것의 대표 id 집합 (주소 = 유튜브 #i)."""
    return {s["lead"]["id"] for p in radar.get("people", []) for s in p.get("signals", []) if "youtube.com" in (s["lead"].get("url") or "")}


def madmoney_update(conn, a, state_file):
    """매드머니 갱신. 매드머니는 KST 09:30 ~ 10:30 에 유튜브에 올라와 08:00 아침 글엔 없다.
    방송 분배(media-daily)가 기록하면 여기서 그 줄만 받아 **아침 글과 같은 기준 시각**으로 다시 집계 → 새 카드만 서술 → 같은 글 고쳐 쓰기.
    구글 뉴스 · 인용 추출 · 분류 AI 는 부르지 않는다. 아침 상태(radar.json · narrative.json)가 없거나, 그날 회차가 없거나, 이미 실렸으면 그대로 끝낸다."""
    sd = a.state or config.OUTPUT_DIR
    try:
        with open(os.path.join(sd, "radar.json"), encoding="utf-8") as f:
            morning = json.load(f)
    except (OSError, ValueError):
        print("[madmoney-only] 아침 radar.json 없음 — 건너뜀")
        return
    anchor = morning.get("generated_at") or ""
    try:
        a_day = (datetime.datetime.strptime(anchor, "%Y-%m-%dT%H:%M:%SZ") + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")
    except ValueError:
        a_day = ""
    if a_day != render_html.today_kst():
        print(f"[madmoney-only] 아침 상태가 오늘 것이 아님({anchor}) — 건너뜀")
        return
    os.environ["PEOPLE_NOW"] = anchor   # 다른 인물 카드가 그대로 남게 아침 기준 시각으로 집계
    print(f"[1/5] 매드머니 수집 (기준 시각 {anchor})")
    collect.collect(conn, only={"cramer"}, sources={"madmoney"})
    classify.apply_madmoney_labels(conn, aggregate._kst_midnight())
    if state_file:
        state_io.export_state(conn, state_file)
    print("[2/5] 집계"); radar = aggregate.build(conn)
    new_ids = _madmoney_ids(radar) - _madmoney_ids(morning)
    if not new_ids:
        print("[madmoney-only] 새 매드머니 신호 없음(그날 회차가 아직 없거나 이미 실림) — 게시하지 않는다")
        with open(os.path.join(config.OUTPUT_DIR, "radar.json"), "w", encoding="utf-8") as f:
            json.dump(morning, f, ensure_ascii=False, indent=1)   # 상태 저장 단계가 아침 것을 그대로 다시 쓰게
        return
    print(f"[madmoney-only] 새 매드머니 신호 {len(new_ids)}개")
    if a.state:
        _v, _i = record_store.radar_rows(radar, render_html.today_kst())
        record_store.append(a.state, "verdicts", _v)
        record_store.append(a.state, "issues", _i)
    narrative_path = os.path.join(config.OUTPUT_DIR, "narrative.json")
    try:
        with open(os.path.join(sd, "narrative.json"), encoding="utf-8") as f:
            reuse = json.load(f)
    except (OSError, ValueError):
        reuse = None
    print("[3/5] 서술 (새 카드만)")
    if not a.no_llm:
        import narrate
        narrate.narrate(reuse=reuse)
    elif reuse:
        with open(narrative_path, "w", encoding="utf-8") as f:
            json.dump(reuse, f, ensure_ascii=False, indent=1)
    print("[4/5] 렌더"); render_html.render()
    print("[5/5] 게시" + ("" if a.publish else " — dry-run")); publish.publish(do_publish=a.publish)
    import stock_mentions
    stock_mentions.update(os.path.join(config.OUTPUT_DIR, "radar.json"), narrative_path, os.path.join(a.state, "people_mentions.json") if a.state else stock_mentions.OUT,
                          post_url_path=os.path.join(config.OUTPUT_DIR, "post_url.txt") if a.publish else None)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
