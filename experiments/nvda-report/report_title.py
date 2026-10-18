"""게시글 제목·날짜 규칙 (기획서 10절). 게시와 중복 확인이 같은 문자열을 써야 하므로 한 곳에 둔다."""

import datetime

import config

KST = datetime.timezone(datetime.timedelta(hours=9))

TITLE_NAME = "엔비디아(NVDA) 주가 리포트"   # (2026-10-12 사용자: 엔비디아 리포트) — 검색어 `NVDA` · `주가` 를 넣었다 (2026-10-18 검색 노출)
LEGACY_PREFIX = "엔비디아 리포트 — "   # 2026-10-18 이전 제목
SLUG_NAME = "nvidia nvda stock report"
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
    """`이름 날짜` — 같은 날짜면 항상 같은 문자열, 중복 게시 판정의 기준. 날짜는 테마가 오른쪽에 둔다."""
    return f"{TITLE_NAME} {korean_date(date_str)}"

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
