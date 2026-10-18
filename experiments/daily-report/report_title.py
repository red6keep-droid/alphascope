"""리포트 날짜/제목 규칙 (main.py와 check_published.py가 공유)

cron 이중화로 하루에 두 번 실행될 수 있으므로, "오늘의 제목"을 만드는 규칙이
파이프라인과 중복 확인 스크립트에서 정확히 같아야 한다. 그래서 한 곳에 둔다.
"""

import datetime

KST = datetime.timezone(datetime.timedelta(hours=9))

TITLE_NAME = "미국 증시 리포트"   # (2026-10-12 사용자: 리포트 이름을 미국 증시 리포트 · 트럼프 SNS 트렌드 · 엔비디아 리포트로)
LEGACY_PREFIX = "미국 증시 리포트 — "   # 2026-10-18 이전 제목. 줄표는 쓰지 않는다 (가이드라인 2-6)
SLUG_NAME = "us stock market report"   # 영문 주소 (검색 노출, 2026-10-18 사용자)


def today_kst():
    """KST 기준 오늘 날짜 (YYYY-MM-DD)."""
    return datetime.datetime.now(KST).strftime("%Y-%m-%d")


def korean_date(date_str):
    try:
        y, m, d = str(date_str).split("-")[:3]
        return f"{int(y)}년 {int(m)}월 {int(d)}일"
    except Exception:
        return date_str


def daily_title(date_str):
    """게시글 제목 `이름 날짜` — 날짜는 테마가 오른쪽에 둔다. 같은 날짜면 항상 같은 문자열이어야 한다."""
    return f"{TITLE_NAME} {korean_date(date_str)}"


post_title = daily_title   # 세 리포트 같은 이름

def legacy_title(date_str):
    """옛 제목 `이름 — 날짜` (2026-10-18 이전). 이미 올린 글을 찾을 때만 쓴다 — 그날 글이 두 개 생기지 않게."""
    return LEGACY_PREFIX + korean_date(date_str)


def slug_title(date_str):
    """처음 올릴 때만 쓰는 영문 제목 — Blogger 주소가 이 제목으로 정해지고, 바로 한글 제목으로 바꾼다 (2026-10-18 시험: 바꿔도 주소는 그대로)."""
    return f"{SLUG_NAME} {str(date_str)[:10]}"


def match_titles(date_str):
    """이미 올린 그날 글로 볼 제목들 — 새 제목 · 옛 제목 · 영문 제목(한글로 바꾸기 전에 멈춘 글)."""
    return [post_title(date_str), legacy_title(date_str), slug_title(date_str)]


def date_of(title):
    """제목의 `2026년 10월 19일` → `2026-10-19` (title.txt 로 받은 제목에서 그날 제목들을 다시 만들 때). 없으면 None."""
    import re
    m = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", str(title or ""))
    return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}" if m else None
