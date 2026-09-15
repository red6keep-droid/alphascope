"""Gemini 서술 — 집계 JSON을 문장으로 (기획서 10절). 선택 단계.

입력은 trump_analysis.json 전체가 아니라 서술에 필요한 부분만 잘라 보낸다.
출력은 문구 규칙(인과 단정·예측 금지)을 검증한 뒤 output/narrative.json 에 쓴다.
"""

import json
import os
import re
import sys

import config
from gemini_client import GeminiPool

PROMPT_FILE = os.path.join(config.PROMPTS_DIR, "narrate.txt")
FORBIDDEN = re.compile(r"때문에|영향을 미|하락시|상승시|원인|오를 것|내릴 것|전망")


def _load_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()


def _slim(a):
    """서술에 필요한 부분만. reactions는 publishable 통계만 남긴다."""
    reactions = {}
    for k, blk in a["reactions"].items():
        syms = {}
        for sym, hz in blk["symbols"].items():
            pub = {h: st for h, st in hz.items() if st and st["publishable"]}
            if pub:
                syms[sym] = pub
        if syms:
            reactions[k] = {"counts": blk["counts"], "symbols": syms}
    return {
        "generated_at": a["generated_at"],
        "data_status": a["data_status"],
        "post_volume": a["post_volume"]["last_24h"],
        "recent_events": a["recent_events"][:10],
        "trend_scores": a["trend_scores"],
        "new_entrants": a["new_entrants"],
        "windows_7D_topics": a["windows"].get("7D", {}).get("dims", {}).get("topic_subtopic", [])[:8],
        "reactions_publishable": reactions,
    }


def validate(narrative):
    if not isinstance(narrative, dict):
        raise ValueError("객체가 아님")
    out = {}
    for key in ("what_changed", "watch_tomorrow"):
        items = narrative.get(key)
        if not isinstance(items, list) or not items:
            raise ValueError(f"{key} 누락")
        clean = []
        for s in items:
            if not isinstance(s, str) or not s.strip():
                continue
            if FORBIDDEN.search(s):
                raise ValueError(f"금지 표현: {s[:80]}")
            clean.append(s.strip())
        if not clean:
            raise ValueError(f"{key} 비어 있음")
        out[key] = clean[:4]
    return out


def narrate(analysis_path=None, output_path=None):
    analysis_path = analysis_path or os.path.join(config.OUTPUT_DIR, "trump_analysis.json")
    output_path = output_path or os.path.join(config.OUTPUT_DIR, "narrative.json")
    with open(analysis_path, "r", encoding="utf-8") as f:
        a = json.load(f)
    prompt = _load_prompt() + json.dumps(_slim(a), ensure_ascii=False, indent=1)
    pool = GeminiPool()
    last = None
    for attempt in range(1, 3):
        try:
            result = validate(pool.generate_json(prompt, temperature=0.3))
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"[narrate] → {output_path}")
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
