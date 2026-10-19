"""LLM(주력 Gemini, 예비 Groq · DeepSeek — experiments/llm_chain.py)을 호출하여 리포트 내러티브를 생성한다.

입력: report_input.json (수집 데이터) + analysis.json (파이썬 분석, 있을 때)
출력: report.out.json (Gemini가 생성한 한국어 분석 + 뉴스 선택)

Gemini에 보내는 JSON은 항상 {"raw": 수집 원본, ...분석값} 구조다. analysis.json이
있으면 그것을 그대로(raw 포함) 보내고, 없으면 {"raw": report_input}만 보낸다.
프롬프트가 구조 하나만 설명하면 되게 하려는 것이다.

숫자 자체는 이 단계에서 생성하지 않는다. Gemini는 오직 분석 문구와
뉴스 index 선택만 담당한다.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from llm_chain import LLMPool  # noqa: E402  — 모든 리포트 공용 LLM 사슬 (2026-10-14)
import fact_check  # noqa: E402  — 서술 숫자 · 방향 검사 (2026-10-14)
from validate_report import REQUIRED_LLM_KEYS  # noqa: E402

PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "daily_report.txt")
# 숫자 검사를 하지 않는 칸 — 그림 프롬프트(영어 묘사), 뉴스(제목 번역 · 선정 이유는 기사 원문 숫자를 옮긴다)
NO_FACT_CHECK = ("image_prompt", "news")


def _load_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def _load_payload(input_path, analysis_path):
    if analysis_path and os.path.exists(analysis_path):
        with open(analysis_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data.get("raw"), dict):
            print("[Gemini] 입력: analysis.json (원본 + 분석값)")
            # 앞날을 가르지 못한 점수 · 신호등 · 내일 체크와 한국 · 일정 기록은 보내지 않는다 — 문장이 등급을 말하거나 한국장을 내다보지 않게 (2026-10-18)
            for k in ("regime", "status", "watch", "korea", "fx", "calendar", "regime_check", "krw_check"):
                data.pop(k, None)
            data["raw"].pop("calendar", None)
            return data
        print("[Gemini] analysis.json에 raw가 없어 원본만 보냅니다.")
    else:
        print("[Gemini] 입력: report_input.json (원본만 — 분석 없음)")
    with open(input_path, "r", encoding="utf-8") as f:
        return {"raw": json.load(f)}


def generate_report(input_path, output_path, analysis_path=None):
    """예전에는 Gemini 키만 차례로 돌았다. 이제 공용 사슬 "json" — Gemini(키 하나, 2026-10-19) → NVIDIA DeepSeek → Groq (2026-10-14).
    프롬프트가 3만 자를 넘어 Groq 무료 등급(분당 8,000토큰)은 413 이라, 실제 예비는 DeepSeek 다 (2026-10-14 비교: 75초, 13칸 · 숫자 검사 통과)."""
    payload = _load_payload(input_path, analysis_path)
    prompt = _load_prompt() + "\n\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    print(f"[Gemini] 프롬프트 {len(prompt):,}자")

    def structure(report):   # validate_report 가 볼 칸이 모두 있어야 한다
        if not isinstance(report, dict):
            raise ValueError("리포트 JSON 객체가 아님")
        missing = [k for k in REQUIRED_LLM_KEYS if k not in report]
        if missing or not isinstance(report.get("news"), list):
            raise ValueError(f"필수 칸 누락: {missing or 'news(list)'}")

    def check(report):   # 구조 + 숫자 검사 — 걸리면 그 모델 답은 버리고 다음 단계로
        structure(report)
        problems = fact_check.check([v for k, v in report.items() if k not in NO_FACT_CHECK and isinstance(v, str)], payload)
        if problems:
            raise ValueError("숫자 검사 — " + " / ".join(problems))

    pool = LLMPool("json-daily", label="daily-report")   # flash → DeepSeek → lite (2026-10-16, 데일리만 — llm_chain.CHAINS 참조)
    try:
        report = pool.generate_json(prompt, temperature=None, validate=check)
    except RuntimeError:
        # 모든 모델이 검사에 걸린 날: 구조가 맞는 첫 답에서 틀린 문장만 빼고 쓴다 — 리포트 전체가 빠지는 것보다 낫다 (2026-10-14)
        report, used = None, None
        for name, value, _why in pool.rejected:
            try:
                structure(value)
            except ValueError:
                continue
            report, used = value, name
            break
        if report is None:
            raise
        for k, v in list(report.items()):
            if k in NO_FACT_CHECK or not isinstance(v, str):
                continue
            fixed, problems = fact_check.drop_bad(v, payload)
            if problems:
                print(f"[검사] {k}: 틀린 문장 {len(problems)}개 뺌 — " + " / ".join(problems)[:300])
                report[k] = fixed
        pool.last_model = f"{used} (틀린 문장 뺌)"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[Gemini] 리포트 생성 완료 -> {output_path} (모델: {pool.last_model})")
    return report


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    generate_report("report_input.json", "report.out.json", analysis_path="analysis.json")