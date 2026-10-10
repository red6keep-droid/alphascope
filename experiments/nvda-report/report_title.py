"""게시글 제목·날짜 규칙 (기획서 10절). 게시와 중복 확인이 같은 문자열을 써야 하므로 한 곳에 둔다."""

import datetime

import config

KST = datetime.timezone(datetime.timedelta(hours=9))

TITLE_PREFIX = "엔비디아 데일리 — "
LABELS = ["엔비디아", "미국 증시", "자동 리포트"] + (["테스트 중"] if config.TEST_MODE else [])


def today_kst():
    return datetime.datetime.now(KST).strftime("%Y-%m-%d")


def korean_date(date_str):
    try:
        y, m, d = str(date_str).split("-")[:3]
        return f"{int(y)}년 {int(m)}월 {int(d)}일"
    except Exception:  # noqa: BLE001
        return date_str


def post_title(date_str):
    """같은 날짜면 항상 같은 문자열 — 중복 게시 판정의 기준."""
    return TITLE_PREFIX + korean_date(date_str)
