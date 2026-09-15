"""Gemini를 호출하여 리포트 내러티브를 생성한다.

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
import re
import time

from google import genai
from google.genai import types

PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "daily_report.txt")
DEFAULT_MODEL = "gemini-3.5-flash"
PER_KEY_ATTEMPTS = 2
RETRY_SLEEP_SECONDS = 2


def _load_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def _parse_json(text):
    text = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S | re.M)
    if fenced:
        text = fenced.group(1).strip()
    m = re.search(r"[{\[]", text)
    if not m:
        raise ValueError("JSON 시작 문자({/[)를 찾지 못했습니다.")
    end = max(text.rfind("}"), text.rfind("]"))
    if end < m.start():
        raise ValueError("JSON 닫는 문자(}/])를 찾지 못했습니다.")
    return json.loads(text[m.start(): end + 1])


def _api_keys():
    raw = os.environ.get("GEMINI_API_KEY", "")
    keys = [k.strip() for k in re.split(r"[;,]", raw)]
    keys = [k for k in keys if k]
    if not keys:
        raise RuntimeError("GEMINI_API_KEY 환경 변수(또는 .env)가 필요합니다.")
    return keys


def _mask(key):
    if len(key) <= 8:
        return key[:3] + "***"
    return key[:8] + "***"


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
    keys = _api_keys()
    model_name = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)

    payload = _load_payload(input_path, analysis_path)
    prompt = _load_prompt() + "\n\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    print(f"[Gemini] 프롬프트 {len(prompt):,}자")

    errors = []
    for idx, key in enumerate(keys, 1):
        masked = _mask(key)
        client = genai.Client(api_key=key)
        for attempt in range(1, PER_KEY_ATTEMPTS + 1):
            last_error = None
            try:
                print(f"[Gemini] 키 {idx}/{len(keys)} ({masked}) 시도 {attempt}/{PER_KEY_ATTEMPTS} (model={model_name})")
                chat = client.chats.create(model=model_name)
                response = chat.send_message(
                    prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                )
                report = _parse_json(response.text)

                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)

                print(f"[Gemini] 리포트 생성 완료 -> {output_path} (사용 키: {masked})")
                return report
            except Exception as e:
                last_error = e
                print(f"[Gemini] 키 {idx} 실패({attempt}/{PER_KEY_ATTEMPTS}): {e}")
                if attempt < PER_KEY_ATTEMPTS:
                    time.sleep(RETRY_SLEEP_SECONDS)
        errors.append(f"키{idx}({masked}): {last_error}")

    raise RuntimeError(
        "Gemini 리포트 생성 실패 (모든 키 소진)\n" + "\n".join(errors)
    )


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    generate_report("report_input.json", "report.out.json", analysis_path="analysis.json")