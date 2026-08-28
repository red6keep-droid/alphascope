"""리포트 날짜/제목 규칙 (main.py와 check_published.py가 공유)

cron 이중화로 하루에 두 번 실행될 수 있으므로, "오늘의 제목"을 만드는 규칙이
파이프라인과 중복 확인 스크립트에서 정확히 같아야 한다. 그래서 한 곳에 둔다.
"""

import datetime

KST = datetime.timezone(datetime.timedelta(hours=9))

TITLE_PREFIX = "미국 증시 데일리 브리핑 — "


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
    """게시글 제목. 같은 날짜면 항상 같은 문자열이어야 한다."""
    return TITLE_PREFIX + korean_date(date_str)
