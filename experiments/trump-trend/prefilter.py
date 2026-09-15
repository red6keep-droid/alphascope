"""1단계 사전 필터 — 확실한 노이즈만 표시한다 (기획서 5절).

원칙: 애매하면 None을 돌려 Gemini로 보낸다. 관련 글을 버리는 쪽이 더 비싸다.
순수 함수라서 테스트하기 쉽다.
"""

import re

import config

_RT_RE = re.compile(r"^\s*RT:\s*https?://\S+\s*$", re.IGNORECASE)
# 자기 글 재게시 — 본문이 원문 복사라서 원문과 이중 계산된다. 원문은 별도 행으로 있다.
_SELF_RT_RE = re.compile(r"^\s*RT\s*@realDonaldTrump", re.IGNORECASE)
_URL_ONLY_RE = re.compile(r"^\s*(https?://\S+\s*)+$", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def clean_text(content):
    """HTML 태그 제거 + 공백 정리. 저장은 원문, 판정은 이 값으로."""
    text = _TAG_RE.sub(" ", content or "")
    return re.sub(r"\s+", " ", text).strip()


def noise_reason(content, media_count=0):
    text = clean_text(content)
    if not text:
        return "no_text"
    if _RT_RE.match(text):
        return "bare_reshare"
    if _SELF_RT_RE.match(text):
        return "self_repost"
    if _URL_ONLY_RE.match(text):
        return "no_text"

    words = text.split()
    lowered = text.lower()
    if len(words) <= config.TOO_SHORT_MAX_WORDS:
        return "too_short"
    if len(words) <= config.GREETING_MAX_WORDS and lowered.startswith(config.GREETING_PREFIXES):
        return "greeting"
    return None
