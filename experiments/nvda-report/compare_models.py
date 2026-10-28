"""Gemini 모델 비교 — 저장된 주 모델 라벨과 후보 모델의 분류 일치율 (2026-10-28).

주 모델(3.6 Flash 한도로 집계, 하루 20회)이 최대 28회까지 쓰여 모자라다. 같은 키의 다른 모델(Gemini 3 Flash, 하루 20회 · 거의 안 씀)을
주 모델 다음 순서에 넣을지 정하려고, 엔비디아 분류 프롬프트로 일치율을 잰다. lite 는 대조군(10-16: 80칸 중 75).

1. 모델 목록 조회(할당량 안 씀) — 이름이 실제로 있는지
2. 주 모델(ai_model = gemini-3.5-flash)이 붙인 최근 기사 BATCHES × 20건을 후보 모델로 다시 분류 — 모델마다 호출 BATCHES 회
3. 4칸(area · direction · novelty · relevance) 일치 + relevance ±1 + is_event 일치

    python compare_models.py --state output/state --models gemini-3-flash,gemini-3.5-flash-lite
"""

import argparse
import os
import re
import sys

import requests

import classify_items
import db
import state_io
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import llm_chain  # noqa: E402

REFERENCE_MODEL = "gemini-3.5-flash"
FIELDS = ["ai_area", "ai_direction", "ai_novelty", "ai_relevance"]
BATCHES = 2


def list_models():
    key = llm_chain.gemini_keys()[0]
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": key, "pageSize": 1000}, timeout=30)
    r.raise_for_status()
    return sorted(m["name"].split("/", 1)[1] for m in r.json().get("models", [])
                  if "generateContent" in m.get("supportedGenerationMethods", []))


def resolve(name, available):
    """'gemini-3-flash' → 목록에 그 이름이 없으면 그 이름으로 시작하는 첫 모델(…-preview 등)."""
    if name in available:
        return name
    return next((m for m in available if re.match(re.escape(name) + r"(-preview|-\d|$)", m)), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="output/state")
    ap.add_argument("--models", default="gemini-3-flash,gemini-3.5-flash-lite")
    ap.add_argument("--db", default=os.path.join("output", "compare.db"))
    args = ap.parse_args()

    available = list_models()
    print("[models] generateContent 가능 · flash 계열: " + ", ".join(m for m in available if "flash" in m))
    for want in ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3-flash", "gemini-3.5-flash-lite"]:
        print(f"[models] {want}: {'있음' if want in available else '없음'}" + ("" if want in available else f" (비슷한 이름: {resolve(want, available)})"))

    if os.path.exists(args.db):
        os.remove(args.db)
    conn = db.connect(args.db)
    state_io.import_state(conn, args.state)
    rows = [dict(r) for r in conn.execute(
        """SELECT * FROM items WHERE ai_model = ? AND prefilter_reason IS NULL AND analyzed_at IS NOT NULL
           ORDER BY published_at DESC LIMIT ?""", (REFERENCE_MODEL, BATCHES * 20)).fetchall()][::-1]
    batches = [rows[i:i + 20] for i in range(0, len(rows), 20)]
    print(f"[compare] 기준 {REFERENCE_MODEL} 라벨 {len(rows)}건 · {len(batches)}배치 ({rows[0]['published_at'][:10]} ~ {rows[-1]['published_at'][:10]})")
    head = classify_items._load_prompt()

    report = []
    for want in [m.strip() for m in args.models.split(",") if m.strip()]:
        model = resolve(want, available)
        if not model:
            report.append(f"| {want} | 목록에 없음 | | | | |")
            continue
        llm_chain.STEPS["cmp"] = {"kind": "gemini", "env": "GEMINI_API_KEY", "model": model, "timeout": 300, "attempts": 3}
        llm_chain.CHAINS["cmp"] = ["cmp"]
        pool = llm_chain.LLMPool("cmp", label=f"cmp-{model}")
        cells = same = near = ev_same = answered = 0
        for batch in batches:
            facts = classify_items.recent_facts(conn, exclude=[it["item_id"] for it in batch])
            try:
                got = {v["item_id"]: v for v in classify_items.classify_batch(pool, head, batch, facts)}
            except Exception as e:  # noqa: BLE001
                print(f"[compare] {model} 배치 실패: {str(e)[:200]}")
                got = {}
            for it in batch:
                v = got.get(it["item_id"])
                cells += len(FIELDS)
                if not v:
                    continue
                answered += 1
                same += sum(str(v[f]) == str(it[f]) for f in FIELDS)
                near += abs(int(v["ai_relevance"]) - int(it["ai_relevance"])) <= 1
                ev_same += int(v["is_event"]) == int(it["is_event"] or 0)
        n = len(rows)
        report.append(f"| {model} | {answered}/{n} | {same}/{cells} ({100 * same / cells:.0f}%) | {near}/{n} | {ev_same}/{n} | {pool.calls} |")

    print("\n| 모델 | 답한 기사 | 4칸 일치 | 관련도 ±1 | 이벤트 판정 일치 | 성공 호출 |\n| --- | --- | --- | --- | --- | --- |")
    print("\n".join(report))


if __name__ == "__main__":
    main()
