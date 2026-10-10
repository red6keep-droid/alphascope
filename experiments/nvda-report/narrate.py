"""⑦ 오늘의 해석 — Gemini 서술, 3문장 이내 (기획서 10절 · 2026-10-10 사용자: 서술은 세 문장 이내, robust 통계 없으면 숫자 해석 금지).

입력은 nvda_analysis.json 중 서술에 필요한 부분만. 출력은 금지어 검증 뒤 output/narrative.json.
이벤트가 0건이면 Gemini를 부르지 않고 건너뛴다 (⑦ 생략).
"""

import json
import os
import re
import sys

import config
import render_report as rr
from gemini_client import GeminiPool

PROMPT_FILE = os.path.join(config.PROMPTS_DIR, "narrate.txt")
FORBIDDEN = re.compile(r"때문에|영향을 미|하락시|상승시|원인|오를 것|내릴 것|전망|기대|우려|매수|매도|목표가|비중|사라|팔아|진입|청산|급격|폭발|역대급|긍정적|부정적|부담|안도")
MAX_SENTENCES = 3
MAX_CHARS = 80


def _slim(a):
    return {
        "day": a["day"],
        "headline": a["headline"],
        "events": [{"area": rr.AREA_KO.get(e["area"], e["area"]), "direction": rr.DIR_KO.get(e["direction"], e["direction"]),
                    "fact": e["fact"], "source": e.get("source")} for e in a["events"][:5]],
        "status_flags": [{"key": x["key"], "value": x["value"]} for grp in a["status"].values() if isinstance(grp, list) for x in grp if x.get("flag")],
        "upcoming": a["upcoming"][:3],
        "checklist_down": [{"metric": r["metric"], "label": r["label"], "value": r["value"], "unit": r["unit"], "asof": r["asof"]}
                           for r in a["checklist"] if r.get("arrow") == "↓"],
    }


def validate(narrative):
    items = (narrative or {}).get("today")
    if not isinstance(items, list) or not items:
        raise ValueError("today 누락")
    out = []
    for s in items:
        if not isinstance(s, str) or not s.strip():
            continue
        s = s.strip()
        if FORBIDDEN.search(s):
            raise ValueError(f"금지 표현: {s[:80]}")
        if len(s) > MAX_CHARS:
            raise ValueError(f"너무 긺 ({len(s)}자): {s[:60]}")
        out.append(s)
    if not out:
        raise ValueError("today 비어 있음")
    return {"today": out[:MAX_SENTENCES]}


def narrate(analysis_path=None, output_path=None):
    analysis_path = analysis_path or os.path.join(config.OUTPUT_DIR, "nvda_analysis.json")
    output_path = output_path or os.path.join(config.OUTPUT_DIR, "narrative.json")
    with open(analysis_path, "r", encoding="utf-8") as f:
        a = json.load(f)
    if os.path.exists(output_path):
        os.remove(output_path)
    if not a.get("events"):
        print("[narrate] 이벤트 0건 — ⑦ 생략")
        return None
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        prompt = f.read() + json.dumps(_slim(a), ensure_ascii=False, indent=1)
    pool = GeminiPool()
    last = None
    for attempt in range(1, 3):
        try:
            result = validate(pool.generate_json(prompt, temperature=0.2))
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"[narrate] {len(result['today'])}문장 → {output_path}")
            return result
        except ValueError as e:
            last = e
            print(f"[narrate] 검증 실패 ({attempt}/2): {e}")
    raise RuntimeError(f"서술 생성 실패: {last}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    narrate()
