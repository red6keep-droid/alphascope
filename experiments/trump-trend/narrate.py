"""Gemini 서술 — 집계 JSON을 문장으로 (기획서 10절). 선택 단계.

입력은 trump_analysis.json 전체가 아니라 서술에 필요한 부분만 잘라 보낸다.
출력은 문구 규칙(인과 단정·예측 금지)을 검증한 뒤 output/narrative.json 에 쓴다.
"""

import json
import os
import re
import sys

import config
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from llm_chain import LLMPool, usage_line  # noqa: E402  — 모든 리포트 공용 LLM 사슬 (experiments/llm_chain.py, 2026-10-14)
import fact_check  # noqa: E402  — 서술 숫자 · 방향 검사 (2026-10-14, Groq 가 +18.4% 를 "18.4% 감소" 로 쓴 뒤)

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


def validate(narrative, source=None):
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
    if source is not None:
        problems = fact_check.check(out["what_changed"] + out["watch_tomorrow"], source)
        if problems:
            raise ValueError("숫자 검사 — " + " / ".join(problems))
    return out


def narrate(analysis_path=None, output_path=None):
    analysis_path = analysis_path or os.path.join(config.OUTPUT_DIR, "trump_analysis.json")
    output_path = output_path or os.path.join(config.OUTPUT_DIR, "narrative.json")
    with open(analysis_path, "r", encoding="utf-8") as f:
        a = json.load(f)
    slim = _slim(a)
    prompt = _load_prompt() + json.dumps(slim, ensure_ascii=False, indent=1)

    def check(v):
        return validate(v, slim)   # 문장의 숫자는 모델에 보낸 데이터(slim)에 있어야 한다

    pool = LLMPool("json", label="trump-narrate")
    last = None
    for attempt in range(1, 3):
        try:
            # 둘째 시도는 검증까지 사슬 안에서 — Gemini 답이 또 탈락하면 예비 모델로 넘어간다 (2026-10-14)
            result = check(pool.generate_json(prompt, temperature=0.3, validate=check if attempt == 2 else None))
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"[narrate] → {output_path}")
            return result
        except (ValueError, RuntimeError) as e:   # RuntimeError = 사슬 전부 실패
            last = e
            print(f"[narrate] 검증 실패 ({attempt}/2): {str(e)[:300]}")
    raise RuntimeError(f"서술 생성 실패: {last}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    narrate()
