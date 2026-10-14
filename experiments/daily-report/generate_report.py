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

PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "daily_report.txt")
# report.out.json 의 핵심 칸 — 빠지면 그 모델 답은 버리고 다음 단계로
REQUIRED_KEYS = ("one_line", "summary", "opinion", "risk", "news")


def _load_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def _load_payload(input_path, analysis_path):
    if analysis_path and os.path.exists(analysis_path):
        with open(analysis_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data.get("raw"), dict):
            print("[Gemini] 입력: analysis.json (원본 + 분석값)")
            return data
        print("[Gemini] analysis.json에 raw가 없어 원본만 보냅니다.")
    else:
        print("[Gemini] 입력: report_input.json (원본만 — 분석 없음)")
    with open(input_path, "r", encoding="utf-8") as f:
        return {"raw": json.load(f)}


def generate_report(input_path, output_path, analysis_path=None):
    """예전에는 Gemini 키만 차례로 돌았다. 이제 공용 사슬 "json" — Gemini 키들 → Groq → NVIDIA DeepSeek (2026-10-14).
    프롬프트가 3만 자를 넘어 Groq 무료 등급(분당 8,000토큰)은 413 으로 바로 넘어가고, 실제 예비는 DeepSeek 다."""
    payload = _load_payload(input_path, analysis_path)
    prompt = _load_prompt() + "\n\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    print(f"[Gemini] 프롬프트 {len(prompt):,}자")

    def check(report):   # 예비 모델이 형식을 빠뜨리면 다음 단계로 — 렌더러가 읽는 핵심 칸 (2026-10-14)
        if not isinstance(report, dict):
            raise ValueError("리포트 JSON 객체가 아님")
        missing = [k for k in REQUIRED_KEYS if not report.get(k)]
        if missing or not isinstance(report.get("news"), list):
            raise ValueError(f"필수 칸 누락: {missing or 'news(list)'}")

    pool = LLMPool("json", label="daily-report")
    report = pool.generate_json(prompt, temperature=None, validate=check)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[Gemini] 리포트 생성 완료 -> {output_path} (모델: {pool.last_model})")
    return report


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    generate_report("report_input.json", "report.out.json", analysis_path="analysis.json")