"""게시글 제목·날짜 규칙. 게시(publish.py)와 중복 확인이 같은 문자열을 써야 하므로 한 곳에 둔다."""

import datetime

KST = datetime.timezone(datetime.timedelta(hours=9))
UTC = datetime.timezone.utc

TITLE_PREFIX = "트럼프 발언 트렌드 — "
LABELS = ["트럼프 트렌드", "미국 증시", "자동 리포트"]


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


def kst_hm(utc_iso):
    """'2026-09-14T17:33:00Z' → '09-15 02:33' (KST)."""
    dt = datetime.datetime.strptime(utc_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return dt.astimezone(KST).strftime("%m-%d %H:%M")
