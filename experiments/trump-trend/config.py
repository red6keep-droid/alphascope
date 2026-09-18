"""트럼프 SNS 트렌드 파이프라인 설정값.

기획서(doc/트럼프-SNS-트렌드-리포트-기획.md)의 "개발 전 확정값"을 코드로 옮긴 곳이다.
숫자를 바꿀 때는 여기만 바꾼다. 다른 모듈은 이 값을 읽기만 한다.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_POSTS_DIR = os.path.join(DATA_DIR, "raw", "posts")
DB_PATH = os.path.join(DATA_DIR, "trump.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
MAPPING_RULES_PATH = os.path.join(BASE_DIR, "mapping_rules.json")

# ── 데이터 소스 ──────────────────────────────────────────────────────────────
CNN_ARCHIVE_URL = "https://ix.cnn.io/data/truth-social/truth_archive.json"
SOURCE_NAME = "cnn-archive"
HTTP_TIMEOUT = 60
USER_AGENT = "Mozilla/5.0 (alphascope trump-trend; personal research)"

# ── 분류 enum (4-A) ────────────────────────────────────────────────────────
TOPICS_MARKET = [
    "Trade", "Fed", "Tax", "Energy", "Immigration",
    "Regulation", "Geopolitics", "Company",
]
TOPICS_NONMARKET = [
    "Personal", "Sports", "Media/Press", "Campaign/Politics",
    "Legal", "Congratulations", "Other",
]
TOPICS = TOPICS_MARKET + TOPICS_NONMARKET

SECTORS = [
    "Semiconductor", "Technology", "Financials", "Energy", "Healthcare",
    "Industrials", "Consumer", "Autos", "Defense", "Materials",
    "Real Estate", "Utilities", "Crypto", "Bonds/Rates", "Broad Market",
]
DIRECTIONS = ["positive", "negative", "neutral"]
INTENSITY_RANGE = (1, 10)
RELEVANCE_RANGE = (0, 3)

# subtopic 표기 통일 (소문자 키 → 정식 표기). 복수형은 labels.py가 단수 키로 다시 찾는다.
SUBTOPIC_ALIASES = {
    "tariff": "Tariff", "tariffs": "Tariff", "import tariff": "Tariff", "reciprocal tariff": "Tariff",
    "trade deal": "Trade Deal", "trade agreement": "Trade Deal", "trade relation": "Trade Relations",
    "trade relations": "Trade Relations", "trade deficit": "Trade Deficit",
    "sanction": "Sanctions", "sanctions": "Sanctions",
    "rate cut": "Rate Cut", "rate cuts": "Rate Cut", "interest rate": "Interest Rates",
    "interest rates": "Interest Rates", "inflation": "Inflation", "powell": "Fed Chair",
    "fed chair": "Fed Chair", "jobs report": "Jobs Report",
    "oil price": "Oil Prices", "oil prices": "Oil Prices", "drilling": "Drilling",
    "drug price": "Drug Pricing", "drug prices": "Drug Pricing", "drug pricing": "Drug Pricing",
    "ai regulation": "AI Regulation", "ai": "AI", "data center": "Data Centers", "data centers": "Data Centers",
    "antitrust": "Antitrust", "crypto": "Crypto", "border": "Border", "deportation": "Deportation",
    "tax cut": "Tax Cut", "tax cuts": "Tax Cut", "military strike": "Military Strike", "war": "War",
    "ceasefire": "Ceasefire", "investment": "Investment", "earnings": "Earnings",
}

# ── 노이즈 필터 (5절) ──────────────────────────────────────────────────────
GREETING_PREFIXES = (
    "congratulations", "happy birthday", "happy ", "rip ", "rest in peace",
    "merry christmas", "thank you to", "god bless", "condolences",
)
GREETING_MAX_WORDS = 25
TOO_SHORT_MAX_WORDS = 3

# 용도별 market_relevance 임계값 (5절 3단계)
RELEVANCE_TREND_MIN = 1
RELEVANCE_EVENT_MIN = 2

# ── 이벤트 클러스터링 (6절) ───────────────────────────────────────────────
CLUSTER_GAP_MINUTES = 60

# ── 트렌드 (7절) ─────────────────────────────────────────────────────────
WINDOWS_DAYS = [3, 7, 30, 90]
TREND_WEIGHTS = {"frequency": 0.35, "intensity": 0.30, "recency": 0.25, "novelty": 0.10}
TREND_SCORE_WINDOW = 7          # Trend Score 계산 창
NOVELTY_LOOKBACK_DAYS = 90
TOP_TRENDS = 10

# ── 이벤트 스터디 (8절) ───────────────────────────────────────────────────
BENCHMARK = "SPY"
MIN_CLEAN_N = 20                # 미만이면 리포트에 내지 않는다
# 분봉은 쓰지 않는다 (2026-09-18 결정). 일봉 OHLCV만으로 아래 구간을 잰다.
#   immediate : 장외 게시물 → 갭(기준 종가 → 측정일 시가) · 정규장 게시물 → 장중(측정일 시가 → 종가)
#   close / next_close / d3 / d5 : 기준 종가 대비 당일·익일·+3·+5 거래일 종가
#   rel_range / rel_volume : 측정일 (고−저)/종가 · 거래량을 직전 REL_LOOKBACK_DAYS 거래일 기준과 나눈 배수
CAR_DAYS = [3, 5]               # 누적 반응 창 (거래일)
REL_LOOKBACK_DAYS = 20          # 변동폭·거래량 배수의 기준 기간
REL_MIN_LOOKBACK = 10           # 이보다 짧으면 배수를 계산하지 않는다
# 플라시보 — 같은 자산의 비이벤트 거래일에서 N개를 뽑은 평균 분포와 비교한다 (결정적 시드).
PLACEBO_RESAMPLES = 1000
PLACEBO_MIN_POOL = 120          # 비이벤트 거래일이 이보다 적으면 검정하지 않는다
PLACEBO_NOISE_P = 0.10          # 양측 p가 이 값 이상이면 "무작위 날과 구분되지 않음"
# 기존 collect_yahoo.py 유니버스와 겹치는 심볼은 그쪽 일봉을 그대로 쓸 수 있지만,
# 이 파이프라인은 독립 실행을 위해 자체 daily_bars 테이블을 채운다.
UNIVERSE = {
    "market": ["SPY", "QQQ"],
    "sector": ["SMH", "XLK", "XLF", "XLE", "XLV", "XLI"],
    "named": ["NVDA", "TSLA", "AAPL"],   # Trump가 이름을 부르는 회사. ≤ 5
}
ALL_SYMBOLS = [s for group in UNIVERSE.values() for s in group]
PRICE_BACKFILL_PERIOD = "2y"     # 첫 실행. 이후는 PRICE_UPDATE_PERIOD
PRICE_UPDATE_PERIOD = "1mo"

# ── 거시 캘린더 (confounded_daily) ───────────────────────────────────────
# FRED release_id — https://api.stlouisfed.org/fred/releases
FRED_RELEASES = {
    10: "CPI",
    50: "Employment Situation (NFP)",
    53: "GDP",
    54: "Personal Income and Outlays (PCE)",
}
# FOMC 결정일(2일차). 연준 공개 일정 기준 — 연도가 바뀌면 갱신한다.
FOMC_DECISION_DATES = [
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]

# ── Gemini (12절) ────────────────────────────────────────────────────────
DEFAULT_MODEL = "gemini-3.5-flash"
CLASSIFY_BATCH_SIZE = 15
CLASSIFY_MAX_BATCHES_PER_RUN = 40   # 무료 한도 안에서 하루치. 남은 건 다음 실행이 이어받는다
CLASSIFY_SINCE_DAYS = 90            # 백필 범위
KEY_COOLDOWN_SECONDS = 60           # 429를 받은 키의 휴식
PER_BATCH_ATTEMPTS = 5              # 503(수요 폭주)은 3·6·12·24·48s 지수 백오프
RETRY_SLEEP_SECONDS = 3
