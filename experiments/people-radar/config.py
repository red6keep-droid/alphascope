"""인물 발언 레이더 설정값 (doc/기획/인물-발언-레이더-기획.md).

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

# 첫 발행은 '테스트 중' 라벨로 (NVDA 첫 발행 때 사용자 결정 10-10 과 같게). 테스트를 끝낼 때 False
TEST_MODE = True

# ── 3단계 인용 추출 (extract.py) ─────────────────────────────────────────
# 새 기능은 예비 공급자 먼저, Gemini 는 맨 뒤 (llm_chain 머리말 2026-10-19: 키 하나를 모든 리포트가 나눠 쓴다)
EXTRACT_CHAIN = "json-backup-first"
EXTRACT_BATCH = 16            # 묶음 대표 제목 16개 = 호출 1회 — 묶음당 출력 약 50토큰, Groq Qwen 출력 상한 1,000토큰 안에 여유 있게 (2026-10-26, 30이면 1,500)
EXTRACT_SINCE_HOURS = 48      # 아직 추출하지 않은 2차 항목을 볼 범위
GROUP_JACCARD = 0.45          # 같은 인물 · 48시간 안 제목 토큰 자카드 ≥ 이 값이면 같은 발언 묶음
# 말한 형태 — 제목에 이것도 인물 이름도 없으면 LLM 전에 버린다 (해설 · 기사 모음 · 이름만 스친 글)
SPEECH_RE = (r"\b(say|says|said|saying|warns?|warned|urges?|urged|calls?|called|slams?|blasts?|predicts?|believes?|thinks?|"
             r"sees?|expects?|signals?|signaled|vows?|vowed|pledges?|pledged|plans?|reveals?|defends?|denies|denied|claims?|"
             r"touts?|tells?|told|insists?|argues?|admits?|hints?|suggests?|praises?|criticizes?|rejects?|announces?|"
             r"announced|buys?|bought|sells?|sold|dumps?|bets?|shorts?|doubles? down)\b|[:“”\"‘’]")

CNN_ARCHIVE_URL = "https://ix.cnn.io/data/truth-social/truth_archive.json"
ARK_TRADES_URL = "https://arkfunds.io/api/v2/etf/trades?symbol={fund}"   # 제3자 API (ARK 공식 페이지는 JS, 2026-10-19 확인)
ARK_FUNDS = ["ARKK", "ARKW", "ARKG", "ARKQ", "ARKF", "ARKX"]
TREASURY_PRESS_URL = "https://home.treasury.gov/news/press-releases"
FED_MONETARY_CATEGORIES = {"Monetary Policy"}   # 연준 보도자료 중 금리 관련만 (제재 · 감독 조치는 버린다)


def gnews(query):
    from urllib.parse import quote_plus
    return (f"https://news.google.com/rss/search?q={quote_plus(query)}+when:{GOOGLE_NEWS_WHEN}"
            f"&hl=en-US&gl=US&ceid=US:en")


# ── 4단계 분류 (classify.py) ─────────────────────────────────────────────
# 출력 칸은 세 인물군 공통(trump-trend 와 같은 8칸) — 묶기 · 반응 통계를 그대로 쓰려고. 주제 목록만 인물군별 (기획 2절)
CLASSIFY_CHAIN = "json-oss-first"    # 출력이 길어(20건 약 2천 토큰) Qwen 출력 한도에 걸린다 — gpt-oss 먼저 (llm_chain 10-26)
NARRATE_CHAIN = "json-oss-first"     # 카드 한국어 요약 (narrate.py) — 같은 이유
# gpt-oss 하루 토큰(20만)이 바닥나면 NVIDIA 를 건너뛰고 바로 gemini-lite 로 (2026-10-28: NVIDIA 5/5 연결 끊김으로 45분 초과.
# lite 하루 500회 중 최대 50회 사용 → 이 몫 최대 약 20회를 더해도 약 430회 여유)
SKIP_WHEN_DAY_OUT = {"groq": ["nvidia-deepseek"]}
CLASSIFY_BATCH = 20
CLASSIFY_TEXT_MAX = 1500
TOPICS_BY_GROUP = {
    "policy": (["Trade", "Fed", "Tax", "Energy", "Immigration", "Regulation", "Geopolitics", "Company"],
               ["Personal", "Sports", "Media/Press", "Campaign/Politics", "Legal", "Congratulations", "Other"]),
    "investor": (["Stock Call", "Position", "Sector Call", "Macro Warning", "Market Outlook", "Fed", "Policy"],
                 ["Personal", "Media/Press", "Charity", "Other"]),
    "ceo": (["Product", "Investment", "Earnings", "Deal", "Regulation", "Industry View"],
            ["Politics", "Personal", "Media/Press", "Other"]),
}
TOPICS_BY_GROUP["commentator"] = TOPICS_BY_GROUP["investor"]
PROMPT_BY_GROUP = {"policy": "classify_policy.txt", "investor": "classify_investor.txt",
                   "commentator": "classify_investor.txt", "ceo": "classify_ceo.txt"}
SECTORS = ["Semiconductor", "Technology", "Financials", "Energy", "Healthcare", "Industrials", "Consumer", "Autos",
           "Defense", "Materials", "Real Estate", "Utilities", "Crypto", "Bonds/Rates", "Broad Market"]
DIRECTIONS = ["positive", "negative", "neutral"]
# 화면 표기 (디자인-가이드라인 3-4: enum 은 영어 그대로, 화면에서만 한국어). 정책군은 trump-trend config.TOPIC_KO 와 같다
TOPIC_KO = {"Trade": "무역", "Fed": "연준 · 금리", "Tax": "세금", "Energy": "에너지", "Immigration": "이민", "Regulation": "규제",
            "Geopolitics": "지정학", "Company": "기업",
            "Stock Call": "종목 의견", "Position": "매매", "Sector Call": "업종 의견", "Macro Warning": "거시 경고",
            "Market Outlook": "시장 전망", "Policy": "정책 의견",
            "Product": "제품", "Investment": "투자", "Earnings": "실적", "Deal": "거래 · 제휴", "Industry View": "업계 평가"}
SECTOR_KO = {"Semiconductor": "반도체", "Technology": "기술", "Financials": "금융", "Energy": "에너지", "Healthcare": "헬스케어",
             "Industrials": "산업", "Consumer": "소비", "Autos": "자동차", "Defense": "방산", "Materials": "소재",
             "Real Estate": "부동산", "Utilities": "유틸리티", "Crypto": "가상자산", "Bonds/Rates": "채권 · 금리", "Broad Market": "시장 전체"}
DIR_KO = {"positive": "긍정", "negative": "부정", "neutral": "중립"}
# 트럼프 Truth Social 은 trump-trend 가 매일 분류한 라벨을 그대로 쓴다 (trump-state 브랜치). 없으면 정책군 프롬프트로
TRUMP_LABELS_PATH = os.path.join(BASE_DIR, "..", "trump-trend", "output", "state", "classifications.jsonl")
TRUMP_LABELS_GIT = "origin/trump-state:experiments/trump-trend/output/state/classifications.jsonl"


# ── 인물 ─────────────────────────────────────────────────────────────────
# group = 분류 프롬프트 · 주제 체계 (기획 2절): policy · investor · commentator · ceo
# primary = [(수집기, 인자, attribution)] — attribution: self(본인 글 · 연설) · office(기관 발표) · trade(매매 공시)
# news = Google News 검색어 (2차 소스, 인용 추출 대상) · aliases = 제목에 이 중 하나가 있어야 그 인물 기사 (소문자)
# start = 기획 6절 4단계 첫 6명이면 True. 나머지는 2차 전용(6단계) — 수집은 지금부터 한다
PEOPLE = {
    "trump": {
        "name_ko": "트럼프", "title_ko": "미국 대통령", "group": "policy", "start": True,
        "primary": [("cnn_archive", None, "self"),
                    ("rss", "https://www.whitehouse.gov/presidential-actions/feed/", "office"),
                    ("rss", "https://www.whitehouse.gov/briefings-statements/feed/", "office")],
        "aliases": ["trump"],
        "news": '"Trump said" OR "Trump says"',
    },
    "bessent": {
        "name_ko": "스콧 베센트", "title_ko": "재무장관", "group": "policy", "start": True,
        "primary": [("treasury_html", None, "office")],
        "aliases": ["bessent", "treasury secretary", "treasury chief"],
        "news": '"Scott Bessent"',
    },
    "lutnick": {
        "name_ko": "하워드 러트닉", "title_ko": "상무장관", "group": "policy", "start": False,
        "primary": [],   # 상무부는 Cloudflare 403 (2026-10-16) — 2차로만
        "aliases": ["lutnick", "commerce secretary"],
        "news": '"Howard Lutnick"',
    },
    "greer": {
        "name_ko": "제이미슨 그리어", "title_ko": "무역대표(USTR)", "group": "policy", "start": True,
        "primary": [("rss", "https://ustr.gov/rss.xml", "office")],
        "aliases": ["greer", "trade representative", "ustr"],
        "news": '"Jamieson Greer"',
    },
    "fed": {
        "name_ko": "연준", "title_ko": "워시 의장 · 이사들", "group": "policy", "start": True,
        "primary": [("fed_speeches", "https://www.federalreserve.gov/feeds/speeches.xml", "self"),
                    ("fed_press", "https://www.federalreserve.gov/feeds/press_all.xml", "office")],
        "aliases": ["warsh", "fed chair", "fed’s", "fed's"],
        "news": '"Kevin Warsh"',
    },
    "burry": {
        "name_ko": "마이클 버리", "title_ko": "투자자", "group": "investor", "start": True,
        "primary": [("rss", "https://michaeljburry.substack.com/feed", "self")],   # michaelburry.substack.com 은 다른 사람
        "aliases": ["burry"],
        "news": '"Michael Burry"',
    },
    "wood": {
        "name_ko": "캐시 우드", "title_ko": "ARK 대표", "group": "investor", "start": True,
        "primary": [("ark_trades", None, "trade")],
        "aliases": ["cathie wood", "wood", "ark invest", "ark’s", "ark's"],
        "news": '"Cathie Wood"',
    },
    "ackman": {"name_ko": "빌 애크먼", "title_ko": "투자자", "group": "investor", "start": False,
               "primary": [], "aliases": ["ackman"],
        "news": '"Bill Ackman"'},
    "cramer": {"name_ko": "짐 크레이머", "title_ko": "CNBC 진행자", "group": "commentator", "start": False,
               "primary": [], "aliases": ["cramer"],
        "news": '"Jim Cramer"'},
    "timiraos": {"name_ko": "닉 티미라오스", "title_ko": "WSJ 연준 담당 기자", "group": "commentator", "start": False,
                 "primary": [], "aliases": ["timiraos"],
        "news": '"Nick Timiraos"'},
    "musk": {"name_ko": "일론 머스크", "title_ko": "테슬라 CEO", "group": "ceo", "start": False,
             "primary": [], "aliases": ["musk"],
        "news": '"Elon Musk"'},
    "altman": {"name_ko": "샘 올트먼", "title_ko": "OpenAI CEO", "group": "ceo", "start": False,
               "primary": [], "aliases": ["altman"],
        "news": '"Sam Altman"'},
    "huang": {"name_ko": "젠슨 황", "title_ko": "엔비디아 CEO", "group": "ceo", "start": False,
              "primary": [], "aliases": ["huang", "nvidia ceo", "nvidia chief"],
        "news": '"Jensen Huang"'},
}
