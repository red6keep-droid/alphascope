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
# 리포트 표기용 한국어 (디자인-가이드라인 3-4, 2026-10-11 사용자: 용어는 한국어 위주). 분류 enum 은 영어 그대로 — 화면에서만 바꾼다
TOPIC_KO = {"Trade": "무역", "Fed": "연준", "Tax": "세금", "Energy": "에너지", "Immigration": "이민", "Regulation": "규제",
            "Geopolitics": "지정학", "Company": "기업", "Personal": "개인", "Sports": "스포츠", "Media/Press": "언론",
            "Campaign/Politics": "정치", "Legal": "법무", "Congratulations": "축하", "Other": "기타"}
SECTOR_KO = {"Semiconductor": "반도체", "Technology": "기술", "Financials": "금융", "Energy": "에너지", "Healthcare": "헬스케어",
             "Industrials": "산업", "Consumer": "소비", "Autos": "자동차", "Defense": "방산", "Materials": "소재",
             "Real Estate": "부동산", "Utilities": "유틸리티", "Crypto": "가상자산", "Bonds/Rates": "채권·금리", "Broad Market": "시장 전체"}
SUBTOPIC_KO = {
    "Tariff": "관세", "Trade Deal": "무역 합의", "Trade Relations": "무역 관계", "Trade Deficit": "무역 적자", "Reciprocity": "상호주의",
    "Infrastructure Deal": "인프라 합의", "Sanctions": "제재", "Rate Cut": "금리 인하", "Interest Rates": "금리", "Inflation": "물가",
    "Fed Chair": "연준 의장", "Fed Board Nomination": "연준 이사 지명", "Fed Building Costs": "연준 건물 비용", "Jobs Report": "고용 보고서",
    "Oil Prices": "유가", "Oil Drilling": "석유 시추", "Drilling": "시추", "Oil Investment": "석유 투자", "Oil Production": "석유 생산",
    "Diesel Fuel": "경유", "Gas Prices": "휘발유 가격", "Gasoline Prices": "휘발유 가격", "Fuel Economy": "연비",
    "Drug Pricing": "약가", "Healthcare": "의료", "AI Regulation": "AI 규제", "Data Centers": "데이터센터", "Antitrust": "반독점",
    "Crypto": "가상자산", "Trump Accounts": "트럼프 계좌", "Deforestation": "산림 파괴",
    "Border": "국경", "Deportation": "추방", "Home Prices": "주택 가격", "Housing Prices": "주택 가격",
    "Tax Cut": "감세", "Military Strike": "군사 공격", "Military Threat": "군사 위협", "War": "전쟁", "Iran War": "이란 전쟁",
    "Ceasefire": "휴전", "Cease Fire": "휴전", "Retaliation": "보복", "Strait of Hormuz": "호르무즈 해협", "Hormuz Strait Tolls": "호르무즈 통행료",
    "Iran": "이란", "Iran Deal": "이란 협상", "Investment": "투자", "Corporate Investment": "기업 투자", "Earnings": "실적",
    "Price Cuts": "가격 인하", "Semiconductor Manufacturing": "반도체 제조", "Media Bias": "언론 편향", "Election Fraud": "선거 부정",
}
TERM_KO = dict(SUBTOPIC_KO)
TERM_KO.update(SECTOR_KO)
TERM_KO.update(TOPIC_KO)
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
    # 2026-10-07: 같은 뉴스가 다른 하위주제로 쪼개지던 것들
    "artificial intelligence": "AI", "super intelligence": "AI", "superintelligence": "AI",
    "fuel economy": "Fuel Economy", "cafe": "Fuel Economy",
    "iran": "Iran", "media bias": "Media Bias", "healthcare": "Healthcare",
}
# subtopic 꼬리말 — 떼고 나서 앨리어스를 찾는다. "Fuel Economy Rules"/"Fuel Economy Standards" → "Fuel Economy",
# "AI Regulation" → "AI", "Iran Policy" → "Iran". 긴 것부터 맞춘다.
SUBTOPIC_STRIP_SUFFIXES = (
    " regulations", " regulation", " standards", " standard", " policies", " policy", " rules", " rule",
)

# ── 라벨 보정 규칙 (labels.adjust, 2026-10-07) ─────────────────────────────
# 기사 제목 + 링크만 올린 글: 남의 헤드라인은 본인의 정책 발표가 아니다 → 강도 상한.
# (로이터 링크 하나가 강도 10으로 급상승 상위에 오르던 문제)
LINK_POST_MAX_WORDS = 40          # URL을 뺀 단어 수가 이 이하이면 링크 글
LINK_POST_MAX_INTENSITY = 6       # 강한 주장(5–6)까지만. 조치 명시(7+)·발표(9+)는 본인 글에만
# 감사 인사로 시작하는 글: 정책 조치가 없다 → 관련성 상한 (이벤트 임계값 2 미만)
GRATITUDE_PREFIXES = ("i am grateful", "i'm grateful", "thank you to", "i want to thank", "many thanks to")
GRATITUDE_MAX_RELEVANCE = 1

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
# Gemini 가 한도(429) · 수요 폭주(503)로 끝까지 실패하면 이 순서로 (backup_llm). nvda-report config 와 같다 (2026-10-14)
FALLBACK_CHAIN = [
    {"provider": "groq", "model": "openai/gpt-oss-120b", "min_interval": 60, "timeout": 120,
     "params": {"reasoning_effort": "low", "max_completion_tokens": 8000}},          # 분당 8,000토큰 → 호출 간격 60초
    {"provider": "nvidia", "model": "deepseek-ai/deepseek-v4.1-flash", "timeout": 300,
     "params": {"max_tokens": 8000, "chat_template_kwargs": {"thinking": False}}},   # 사고 끄기 — 켜면 답이 비거나 5분 초과
]
KEY_COOLDOWN_SECONDS = 60           # 429를 받은 키의 휴식
PER_BATCH_ATTEMPTS = 5              # 503(수요 폭주)은 3·6·12·24·48s 지수 백오프
RETRY_SLEEP_SECONDS = 3
