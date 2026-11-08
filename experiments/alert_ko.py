"""Slack 알림을 한국어로 — 알림 문구에서만 (2026-11-07 사용자: "알림에서만 바꿔줘"). 워크플로 이름 · Actions 화면 · 로그는 그대로.

    alert_ko.run_name()      # GITHUB_WORKFLOW → 한국어 이름 (없으면 원래 이름, 로컬이면 "로컬 실행")
    alert_ko.line(text)      # 영어 오류 원문이 붙은 줄 → 한국어 원인만 (원문은 실행 로그에)

notify.py(운영 알림) · llm_chain.py(AI 호출 알림)가 쓴다. 워크플로의 curl 알림은 .yml 에 한국어 이름을 직접 적었다(이 표와 같게).
"""
import os
import re

NAMES = {
    "Test Daily Report": "미국 데일리 리포트",
    "NVDA Report": "엔비디아 · 시총 TOP 10 페이지",
    "KR Stocks": "한국 종목 · 한국 증시 리포트",
    "KR Live Prices (10m)": "한국 장중 시세 (10분)",
    "People Radar": "주요 인물 발언",
    "Media Daily": "방송 이슈 (미디어 데일리)",
    "Update News (2x daily)": "뉴스 갱신 (하루 2회)",
    "Update 10 Stock Data (15m)": "홈 시세 갱신 (15분)",
    "Comment Reply": "댓글 답장",
    "Court Survey": "소송 조사",
    "Gemini Model Check": "Gemini 모델 점검",
    "Trump Trend": "트럼프 트렌드 (종료)",
    "Market Forecast": "증시 전망",   # 발행 단계 워크플로 이름(예정) — forecast_alerts.py
}

# (찾을 말, 한국어 원인) — 위에서부터 먼저 맞는 것 하나
RULES = [
    (r"per ?day|PerDay|\bTPD\b|\bRPD\b|daily limit", "하루 한도 소진"),
    (r"\b429\b|Too Many Requests|rate.?limit|RESOURCE_EXHAUSTED|quota", "요청 한도 초과"),
    (r"\b503\b|Service Unavailable|overloaded|UNAVAILABLE", "서버 일시 장애"),
    (r"\b50[024]\b|Bad Gateway|Gateway Time-?out|Internal Server Error", "서버 오류"),
    (r"timed? ?out|Timeout|DEADLINE_EXCEEDED", "응답 시간 초과"),
    (r"ConnectionError|Connection (refused|reset|aborted)|Max retries exceeded|NameResolution|getaddrinfo|SSLError", "연결 실패"),
    (r"\b40[13]\b|Unauthorized|Forbidden|PERMISSION_DENIED|invalid.{0,10}(api.?key|token)|API key not valid|invalid_grant", "인증 · 권한 오류 (키 · 토큰 확인)"),
    (r"\b404\b|Not Found", "주소 없음"),
    (r"No data found|possibly delisted|no price data|No timezone found|empty (response|data)|Empty DataFrame", "자료 없음"),
    (r"JSONDecodeError|Expecting value|Unterminated string|parse", "응답 형식 오류"),
    (r"KeyError|IndexError|AttributeError|TypeError|ValueError|NameError", "코드 오류"),
]


def run_name():
    w = os.environ.get("GITHUB_WORKFLOW")
    return NAMES.get(w, w) if w else "로컬 실행"


def reason(text):
    for pat, ko in RULES:
        if re.search(pat, text or "", re.I):
            return ko
    return ""


def _mostly_ascii(s):
    letters = [c for c in s if not c.isspace()]
    return bool(letters) and sum(c.isascii() for c in letters) / len(letters) > 0.7


def line(text):
    """'수집 실패 — NVDA 일봉 (yfinance) — HTTPError 503 …' → '수집 실패 — NVDA 일봉 (yfinance) — 서버 일시 장애'. 영어 원문은 뺀다
    (2026-11-07 사용자: "원문은 봐도 모르니 생략") — 원문은 링크의 실행 로그에 있다."""
    ko = reason(text) or "오류"
    head, sep, tail = text.rpartition(" — ")
    if sep and _mostly_ascii(tail):   # 끝 덩어리가 영어 원문
        return f"{head} — {ko}"
    i = text.find(": ")
    if i > 0 and _mostly_ascii(text[i + 2:]) and len(text) - i > 14:   # '전부 실패 news: groq: 429 …' 모양 — 첫 ': ' 뒤가 원문
        return f"{text[:i]}: {ko}"
    m = re.search(r"\s[A-Za-z][A-Za-z0-9_-]{15,}", text)   # 'Gemini 키 … GenerateRequestsPerDay… (news)' 같은 긴 영어 이름
    if m:
        lab = re.search(r"\(([^)]*)\)\s*$", text)   # 끝 괄호(사슬 이름)는 남긴다
        return f"{text[:m.start()]} — {ko}" + (f" ({lab.group(1)})" if lab else "")
    return text
