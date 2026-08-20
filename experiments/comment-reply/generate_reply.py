"""Gemini로 댓글에 대한 답글 생성

댓글 내용 + 게시글 제목을 입력으로 한국어 답글을 생성한다.
숫자/주장을 지어내지 않도록 지시문(prompts/comment_reply.txt)으로 제약한다.
결과는 {"reply": "..."} JSON 으로 받아 문자열만 추출한다.

환경변수: GEMINI_API_KEY (다중 키는 ; 또는 , 로 구분, 실패 시 다음 키 fallback)
         GEMINI_MODEL (기본 gemini-3.5-flash)
"""

import json
import os
import re
import time

from google import genai
from google.genai import types

PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "comment_reply.txt")
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
        raise RuntimeError("GEMINI_API_KEY 환경 변수가 필요합니다.")
    return keys


def _mask(key):
    if len(key) <= 8:
        return key[:3] + "***"
    return key[:8] + "***"


def generate_reply(post_title, comment_content, comment_author=""):
    keys = _api_keys()
    model_name = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    prompt = _load_prompt() + "\n\n" + json.dumps(
        {"post_title": post_title, "comment_author": comment_author, "comment": comment_content},
        ensure_ascii=False,
    )

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
                reply = (report.get("reply") or "").strip()
                if not reply:
                    raise ValueError("reply 필드가 비어 있습니다")
                print(f"[Gemini] 답글 생성 완료 (사용 키: {masked})")
                return reply
            except Exception as e:
                last_error = e
                print(f"[Gemini] 키 {idx} 실패({attempt}/{PER_KEY_ATTEMPTS}): {e}")
                if attempt < PER_KEY_ATTEMPTS:
                    time.sleep(RETRY_SLEEP_SECONDS)
        errors.append(f"키{idx}({masked}): {last_error}")

    raise RuntimeError("답글 생성 실패 (모든 키 소진)\n" + "\n".join(errors))