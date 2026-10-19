"""인물 발언 레이더 설정값 (doc/인물-발언-레이더-기획.md).

인물 · 소스를 바꿀 때는 여기만 바꾼다. 수집기(collect.py)는 PEOPLE 를 읽기만 한다.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "people.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

HTTP_TIMEOUT = 40
# 백악관 · 재무부는 봇 UA 를 막을 수 있어 브라우저 UA (2026-10-19 확인: 둘 다 200)
BROWSER_USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# 수집 창 — 이보다 오래된 항목은 넣지 않는다. 피드에 고정 글이 섞인다(USTR 2009년 글, 2026-10-19 확인).
# 트럼프 과거 게시물 · 반응 통계 이력은 trump-trend(trump-state 브랜치)에 있다 — 레이더는 최근 발언만 모은다.
COLLECT_SINCE_HOURS = 72
GOOGLE_NEWS_WHEN = "2d"
PRIMARY_BODY_MAX_CHARS = 4000   # 1차 소스 본문 — 분류 · 인용 추출 입력 상한

CNN_ARCHIVE_URL = "https://ix.cnn.io/data/truth-social/truth_archive.json"
ARK_TRADES_URL = "https://arkfunds.io/api/v2/etf/trades?symbol={fund}"   # 제3자 API (ARK 공식 페이지는 JS, 2026-10-19 확인)
ARK_FUNDS = ["ARKK", "ARKW", "ARKG", "ARKQ", "ARKF", "ARKX"]
TREASURY_PRESS_URL = "https://home.treasury.gov/news/press-releases"
FED_MONETARY_CATEGORIES = {"Monetary Policy"}   # 연준 보도자료 중 금리 관련만 (제재 · 감독 조치는 버린다)


def gnews(query):
    from urllib.parse import quote_plus
    return (f"https://news.google.com/rss/search?q={quote_plus(query)}+when:{GOOGLE_NEWS_WHEN}"
            f"&hl=en-US&gl=US&ceid=US:en")


# ── 인물 ─────────────────────────────────────────────────────────────────
# group = 분류 프롬프트 · 주제 체계 (기획 2절): policy · investor · commentator · ceo
# primary = [(수집기, 인자, attribution)] — attribution: self(본인 글 · 연설) · office(기관 발표) · trade(매매 공시)
# news = Google News 검색어 (2차 소스, 인용 추출 대상)
# start = 기획 6절 4단계 첫 6명이면 True. 나머지는 2차 전용(6단계) — 수집은 지금부터 한다
PEOPLE = {
    "trump": {
        "name_ko": "트럼프", "title_ko": "미국 대통령", "group": "policy", "start": True,
        "primary": [("cnn_archive", None, "self"),
                    ("rss", "https://www.whitehouse.gov/presidential-actions/feed/", "office"),
                    ("rss", "https://www.whitehouse.gov/briefings-statements/feed/", "office")],
        "news": '"Trump said" OR "Trump says"',
    },
    "bessent": {
        "name_ko": "스콧 베센트", "title_ko": "재무장관", "group": "policy", "start": True,
        "primary": [("treasury_html", None, "office")],
        "news": '"Scott Bessent"',
    },
    "lutnick": {
        "name_ko": "하워드 러트닉", "title_ko": "상무장관", "group": "policy", "start": False,
        "primary": [],   # 상무부는 Cloudflare 403 (2026-10-16) — 2차로만
        "news": '"Howard Lutnick"',
    },
    "greer": {
        "name_ko": "제이미슨 그리어", "title_ko": "무역대표(USTR)", "group": "policy", "start": True,
        "primary": [("rss", "https://ustr.gov/rss.xml", "office")],
        "news": '"Jamieson Greer"',
    },
    "fed": {
        "name_ko": "연준", "title_ko": "워시 의장 · 이사들", "group": "policy", "start": True,
        "primary": [("fed_speeches", "https://www.federalreserve.gov/feeds/speeches.xml", "self"),
                    ("fed_press", "https://www.federalreserve.gov/feeds/press_all.xml", "office")],
        "news": '"Kevin Warsh"',
    },
    "burry": {
        "name_ko": "마이클 버리", "title_ko": "투자자", "group": "investor", "start": True,
        "primary": [("rss", "https://michaeljburry.substack.com/feed", "self")],   # michaelburry.substack.com 은 다른 사람
        "news": '"Michael Burry"',
    },
    "wood": {
        "name_ko": "캐시 우드", "title_ko": "ARK 대표", "group": "investor", "start": True,
        "primary": [("ark_trades", None, "trade")],
        "news": '"Cathie Wood"',
    },
    "ackman": {"name_ko": "빌 애크먼", "title_ko": "투자자", "group": "investor", "start": False,
               "primary": [], "news": '"Bill Ackman"'},
    "cramer": {"name_ko": "짐 크레이머", "title_ko": "CNBC 진행자", "group": "commentator", "start": False,
               "primary": [], "news": '"Jim Cramer"'},
    "timiraos": {"name_ko": "닉 티미라오스", "title_ko": "WSJ 연준 담당 기자", "group": "commentator", "start": False,
                 "primary": [], "news": '"Nick Timiraos"'},
    "musk": {"name_ko": "일론 머스크", "title_ko": "테슬라 CEO", "group": "ceo", "start": False,
             "primary": [], "news": '"Elon Musk"'},
    "altman": {"name_ko": "샘 올트먼", "title_ko": "OpenAI CEO", "group": "ceo", "start": False,
               "primary": [], "news": '"Sam Altman"'},
    "huang": {"name_ko": "젠슨 황", "title_ko": "엔비디아 CEO", "group": "ceo", "start": False,
              "primary": [], "news": '"Jensen Huang"'},
}
