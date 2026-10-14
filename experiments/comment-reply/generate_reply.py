"""댓글에 대한 답글 생성

댓글 내용 + 게시글 제목을 입력으로 한국어 답글을 만든다.
숫자/주장을 지어내지 않도록 지시문(prompts/comment_reply.txt)으로 제약한다.
결과는 {"reply": "..."} JSON 으로 받아 문자열만 꺼낸다.

모델 호출은 모든 리포트 공용 사슬 experiments/llm_chain.py ("json": Gemini 키들 → NVIDIA DeepSeek → Groq Qwen → Groq gpt-oss, 2026-10-14).
환경변수: GEMINI_API_KEY (; 또는 , 로 여럿) · GROQ_API_KEY · NVIDIA_API_KEY — 키 없는 단계는 건너뛴다.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from llm_chain import LLMPool  # noqa: E402

PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "comment_reply.txt")


def _load_prompt():
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def _reply_of(value):
    reply = ((value or {}).get("reply") or "").strip() if isinstance(value, dict) else ""
    if not reply:
        raise ValueError("reply 필드가 비어 있습니다")
    return reply


def generate_reply(post_title, comment_content, comment_author=""):
    prompt = _load_prompt() + "\n\n" + json.dumps(
        {"post_title": post_title, "comment_author": comment_author, "comment": comment_content},
        ensure_ascii=False,
    )
    pool = LLMPool("json", label="comment-reply")
    value = pool.generate_json(prompt, temperature=0.3, validate=lambda v: _reply_of(v) and None)
    print(f"[답글] 생성 완료 ({pool.last_model})")
    return _reply_of(value)
