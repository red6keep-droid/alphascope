"""중요 이슈 (옛 ⑦ 오늘의 해석) — Gemini 요약 헤드라인 3줄 이내 (2026-10-11 사용자: 서술형 어미 금지, 요약체 · 2026-10-10: robust 통계 없으면 숫자 해석 금지).

입력은 nvda_analysis.json 중 서술에 필요한 부분만. 출력은 금지어 검증 뒤 output/narrative.json.
이벤트가 0건이면 Gemini를 부르지 않고 건너뛴다 (⑦ 생략).
"""

import datetime
import json
import os
import re
import sys

import config
import render_report as rr
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from llm_chain import LLMPool, usage_line  # noqa: E402  — 모든 리포트 공용 LLM 사슬 (experiments/llm_chain.py, 2026-10-14)
import fact_check  # noqa: E402  — 서술 숫자 · 방향 검사 (2026-10-14, Groq 가 +18.4% 를 "18.4% 감소" 로 쓴 뒤)

PROMPT_FILE = os.path.join(config.PROMPTS_DIR, "narrate.txt")
FORBIDDEN = re.compile(r"때문에|영향을 미|하락시|상승시|원인|오를 것|내릴 것|전망|기대|우려|매수|매도|목표가|비중|사라|팔아|진입|청산|급격|폭발|역대급|긍정적|부정적|부담|안도")
# 요약 헤드라인체 (2026-10-11 사용자: "~있다, ~했다, ~됐다 문체로 쓰지 마라") — 서술형 어미로 끝나면 거부
VERB_ENDING = re.compile(r"(다|요)\.?$")
MAX_SENTENCES = 3
MAX_CHARS = 48


def _slim(a):
    """서술 입력 — **새로 바뀐 것만** (2026-10-17 사용자: 같은 내용이 며칠째 반복된다). 일정은 새로 잡혔거나 내일 · 오늘인 것만,
    점검표는 값이 바뀐 것(새 분기)만 넣는다. 안 바뀐 사실은 재무 · 캘린더 탭에 있다."""
    new = set(a.get("new_flags") or ())
    today = datetime.date.fromisoformat(a["day"])
    upcoming = [c for c in a["upcoming"]
                if f"calendar:{c['kind']}:{c['day']}:{c['label']}" in new or (datetime.date.fromisoformat(c["day"]) - today).days <= 1][:3]
    return {
        "day": a["day"],
        "headline": a["headline"],
        "events": [{"area": rr.AREA_KO.get(e["area"], e["area"]), "direction": rr.DIR_KO.get(e["direction"], e["direction"]),
                    "fact": e["fact"], "source": e.get("source")} for e in [x for x in a["events"] if not x.get("media")][:5]],   # 방송 줄(의견 섞임)은 서술 입력에서 뺀다
        "status_flags": [{"key": x["key"], "value": x["value"]} for grp in a["status"].values() if isinstance(grp, list) for x in grp if x.get("flag")],
        "upcoming": upcoming,
        "checklist_down": [{"metric": r["metric"], "label": r["label"], "value": r["value"], "unit": r["unit"], "asof": r["asof"]}
                           for r in a["checklist"] if r.get("arrow") == "↓" and f"checklist:{r['metric']}" in new],
    }


def validate(narrative, source=None):
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
        if VERB_ENDING.search(s):
            raise ValueError(f"서술형 어미 (요약 헤드라인체로): {s[:80]}")
        if len(s) > MAX_CHARS:
            raise ValueError(f"너무 긺 ({len(s)}자): {s[:60]}")
        out.append(s)
    if not out:
        raise ValueError("today 비어 있음")
    out = out[:MAX_SENTENCES]
    if source is not None:
        problems = fact_check.check(out, source)
        if problems:
            raise ValueError("숫자 검사 — " + " / ".join(problems))
    return {"today": out}


def narrate(analysis_path=None, output_path=None):
    analysis_path = analysis_path or os.path.join(config.OUTPUT_DIR, "nvda_analysis.json")
    output_path = output_path or os.path.join(config.OUTPUT_DIR, "narrative.json")
    with open(analysis_path, "r", encoding="utf-8") as f:
        a = json.load(f)
    if os.path.exists(output_path):
        os.remove(output_path)
    slim = _slim(a)
    if not (slim["events"] or slim["upcoming"] or slim["checklist_down"] or slim["status_flags"]):
        print("[narrate] 새로 바뀐 것 0건 — ⑦ 생략")
        return None
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        prompt = f.read() + json.dumps(slim, ensure_ascii=False, indent=1)

    def check(v):
        return validate(v, slim)   # 문장의 숫자는 모델에 보낸 데이터(slim)에 있어야 한다

    pool = LLMPool("json", label="nvda-narrate")
    last = None
    for attempt in range(1, 3):
        try:
            # 둘째 시도는 검증까지 사슬 안에서 — Gemini 답이 또 탈락하면 예비 모델로 넘어간다 (2026-10-14)
            result = check(pool.generate_json(prompt, temperature=0.2, validate=check if attempt == 2 else None))
            result["model"] = pool.last_model   # 글 끝 "AI 서술 · 모델명" (운영지침 D3-1d, 2026-10-21)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"[narrate] {len(result['today'])}문장 → {output_path}")
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
