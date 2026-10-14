"""Gemini로 댓글에 대한 답글 생성

댓글 내용 + 게시글 제목을 입력으로 한국어 답글을 생성한다.
숫자/주장을 지어내지 않도록 지시문(prompts/comment_reply.txt)으로 제약한다.
결과는 {"reply": "..."} JSON 으로 받아 문자열만 추출한다.

환경변수: GEMINI_API_KEY (다중 키는 ; 또는 , 로 구분, 실패 시 다음 키 fallback)
         GEMINI_MODEL (기본 gemini-3.5-flash)
         GROQ_API_KEY · NVIDIA_API_KEY (선택) — Gemini 키가 모두 실패하면 이 순서로 예비 (2026-10-14,
         Gemini 무료 한도가 프로젝트당 하루 약 20회라 다른 리포트와 나눠 쓰면 넘칠 수 있다). 모델은 NVDA 리포트 예비 사슬과 같다.
"""

import json
import os
import re
import time

import requests

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


# 예비 사슬 — experiments/nvda-report/config.FALLBACK_CHAIN 과 같은 모델 (OpenAI 호환 REST)
FALLBACK_CHAIN = [
    {"name": "groq", "env": "GROQ_API_KEY", "url": "https://api.groq.com/openai/v1/chat/completions",
     "model": "openai/gpt-oss-120b", "params": {"reasoning_effort": "low", "max_completion_tokens": 2000}},
    {"name": "nvidia", "env": "NVIDIA_API_KEY", "url": "https://integrate.api.nvidia.com/v1/chat/completions",
     "model": "deepseek-ai/deepseek-v4.1-flash", "params": {"max_tokens": 2000, "chat_template_kwargs": {"thinking": False}}},
]


def _reply_of(text):
    reply = (_parse_json(text).get("reply") or "").strip()
    if not reply:
        raise ValueError("reply 필드가 비어 있습니다")
    return reply


def _fallback(prompt, errors):
    for step in FALLBACK_CHAIN:
        key = os.environ.get(step["env"], "").strip()
        if not key:
            continue
        try:
            print(f"[예비] {step['name']}:{step['model']} 시도")
            body = {"model": step["model"], "temperature": 0.3, "messages": [{"role": "user", "content": prompt}]}
            body.update(step["params"])
            r = requests.post(step["url"], json=body, timeout=180,
                              headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            if r.status_code != 200:
                raise RuntimeError(f"{r.status_code}: {r.text[:160]}")
            reply = _reply_of(r.json()["choices"][0]["message"].get("content") or "")
            print(f"[예비] 답글 생성 완료 ({step['name']})")
            return reply
        except Exception as e:
            print(f"[예비] {step['name']} 실패: {e}")
            errors.append(f"{step['name']}: {e}")
    raise RuntimeError("답글 생성 실패 (Gemini 키 · 예비 모두 소진)\n" + "\n".join(errors))


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
                reply = _reply_of(response.text)
                print(f"[Gemini] 답글 생성 완료 (사용 키: {masked})")
                return reply
            except Exception as e:
                last_error = e
                print(f"[Gemini] 키 {idx} 실패({attempt}/{PER_KEY_ATTEMPTS}): {e}")
                if attempt < PER_KEY_ATTEMPTS:
                    time.sleep(RETRY_SLEEP_SECONDS)
        errors.append(f"키{idx}({masked}): {last_error}")

    return _fallback(prompt, errors)