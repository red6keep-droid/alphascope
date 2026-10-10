"""엔비디아 데일리 리포트 설정값.

기획서(doc/엔비디아-리포트-기획.md)의 "개발 전 확정값"과 6절 임계값 표를 코드로 옮긴 곳이다.
숫자를 바꿀 때는 여기만 바꾼다. 다른 모듈은 이 값을 읽기만 한다.
"""

import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "nvda.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STATIC_DIR = os.path.join(BASE_DIR, "static")
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")

HTTP_TIMEOUT = 60
USER_AGENT = "Mozilla/5.0 (alphascope nvda-report; personal research)"

# ── 관찰 심볼 (확정값: 5개, 늘리지 않는다) ─────────────────────────────────
SYMBOL = "NVDA"
BENCHMARK = "SPY"
SYMBOLS = ["NVDA", "SPY", "SMH", "AMD", "QQQ"]
PRICE_BACKFILL_PERIOD = "2y"     # 첫 실행. 이후는 PRICE_UPDATE_PERIOD
PRICE_UPDATE_PERIOD = "1mo"

# ── 기술 지표 (7절) ──────────────────────────────────────────────────────
VOL_LOOKBACK_DAYS = 20
MA_SHORT = 50
MA_LONG = 200
RSI_PERIOD = 14
HIGH_52W_DAYS = 252

# ── 옵션 (7절 · 확정값) ───────────────────────────────────────────────────
OPTION_NEAR_EXPIRIES = 4          # 가까운 만기 4개
OPTION_IV_TARGET_DAYS = 30        # ATM IV를 보간할 기준 일수. 이 일수를 감싸는 만기 둘을 추가로 받는다
OPTION_EARNINGS_LOOKAHEAD_DAYS = 45   # 실적이 이 안에 있으면 실적 직후 만기도 받는다 (implied move)
OPTION_STRIKE_BAND = 0.30         # 스냅샷은 현재가 ±30% 행사가만 저장 (P/C 비율은 전체 체인으로 계산)
OPTION_SNAPSHOT_KEEP_DAYS = 90
RISK_FREE_RATE = 0.04
IV_RANK_WINDOW = 60               # 스냅샷 60일 쌓인 뒤 활성
# 체인 품질 게이트 — 미국 자정 뒤 Yahoo가 주는 리셋 체인(호가 0·OI 0·IV≈0)을 걸러낸다
OPTION_MIN_QUOTED_FRACTION = 0.5  # ±30% 행사가 중 호가(bid/ask 또는 lastPrice)가 있는 비율
OPTION_IV_SANE = (0.08, 2.5)      # ATM IV30이 이 밖이면 불량
IMPLIED_MOVE_SHOW_DAYS = 30       # 실적 D-30부터 표시

# ── 실적 캘린더 종목 (확정값 12개: 고객 5 · 공급 3 · 동종 1 · OEM 2 + NVDA) ──
EARNINGS_SYMBOLS = ["NVDA", "MSFT", "GOOGL", "AMZN", "META", "ORCL",
                    "TSM", "AMD", "AVGO", "MU", "SMCI", "DELL"]
EARNINGS_FUTURE_LIMIT_DAYS = 120  # 이보다 먼 추정 실적일은 넣지 않는다

# ── EDGAR ────────────────────────────────────────────────────────────────
EDGAR_CIK = "0001045810"
EDGAR_USER_AGENT = os.environ.get("EDGAR_USER_AGENT", "alphascope nvda-report redkeep@futechsoft.com")
EDGAR_FORMS = ("4", "8-K", "10-Q", "10-K")
EDGAR_BACKFILL_DAYS = 90          # 첫 실행에 받는 공시 범위
EDGAR_REQUEST_GAP_SECONDS = 0.15  # 10 req/s 제한 아래

# ── 거시 캘린더 (trump-trend calendar_macro와 같은 정의) ──────────────────
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
# 지수 리밸런싱: S&P는 3·6·9·12월 셋째 금요일 발효, 나스닥100 연례 재구성은 12월 셋째 금요일.
INDEX_REBALANCE_MONTHS = (3, 6, 9, 12)
CALENDAR_LOOKAHEAD_DAYS = 7       # "다가오는 것"에 보이는 범위
# 트럼프 브리지 (기획서 9절, 2026-10-10 "한 줄만") — trump-trend 상태 브랜치의 분석 JSON
TRUMP_STATE_PATH = "experiments/trump-trend/output/state/trump_analysis.json"
TRUMP_STATE_URL = "https://raw.githubusercontent.com/red6keep-droid/alphascope/trump-state/" + TRUMP_STATE_PATH
TRUMP_POST_URL = ""                 # 비우면 링크 없음. 블로그 글 주소는 매일 바뀌어 고정하지 않는다
TRUMP_SEMI_RULES = ("trade_china_semis", "trade_semis_sector")
TRUMP_MIN_INTENSITY = 5
COURT_LOOKAHEAD_DAYS = 30         # 법원 일정(심리·재판)만 더 멀리 — 판결은 포지션을 미리 생각할 시간이 필요 (2026-10-10)
COURT_RULING_BACKFILL_DAYS = 3    # 첫 실행에서 판결 이벤트를 소급할 일수
CALENDAR_GENERATE_YEARS = 2       # 셋째 금요일(OPEX·INDEX)을 미리 만들어 둘 연수

# ── 이벤트 판정 임계값 (6절 초안 — 30일 그림자 뒤 조정) ───────────────────
VOL_RATIO_EVENT = 2.0             # 거래량 ≥ 20일 평균의 2배
RANGE_PCT_EVENT = 4.0             # 일중 (고−저)/종가 ≥ 4%
REL_SPY_EVENT = 3.0               # |NVDA − SPY 일간 수익률| ≥ 3%p
NEAR_52W_HIGH_PCT = -2.0          # 52주 고점 대비 −2% 이내 "진입일"만
IV_RANK_HIGH = 80
IV_RANK_LOW = 20
PC_RATIO_CHG_EVENT = 0.20         # P/C(OI) 전일 대비 ±20%
OI_JUMP_MULT = 2.0                # 특정 행사가 OI 전일 대비 2배
OI_JUMP_MIN = 10_000              # 그 행사가의 OI가 이 이상일 때만
EST_CHG_EVENT_PCT = 1.0           # EPS·매출 컨센서스 7일 변화 절대값 ≥ 1%
REVISION_RATIO_EVENT = 3.0        # 30일 상향:하향 ≥ 3:1 (또는 반대)
ETF_SHARES_5D_EVENT_PCT = 2.0
SHORT_INTEREST_CHG_EVENT_PCT = 15.0
MAX_EVENTS_IN_BODY = 8            # 넘으면 나머지는 접힘 목록
EVENT_ITEM_MAX_AGE_DAYS = 3       # 지난 리포트 기록이 없을 때(첫 실행) 이보다 오래된 공시·문서는 '오늘 바뀐 것'이 아니라 백필
INSIDER_WINDOW_DAYS = 90          # 점검표 insider_net_sold_90d

# ── ②단계: 문서 수집 (2절 뉴스·규제 묶음) ─────────────────────────────────
BROWSER_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")   # Federal Register·TSMC는 기본 UA를 Cloudflare가 막는다
FEEDS = {
    # kind, source, url — 뉴스룸·블로그는 공식 1차 자료라 키워드 필터를 거치지 않는다
    "newsroom": ("newsroom", "nvidianews", "https://nvidianews.nvidia.com/releases.xml"),
    "blog": ("blog", "nvidiablog", "https://blogs.nvidia.com/feed/"),
    "cnbc_top": ("news", "cnbc", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    "cnbc_tech": ("news", "cnbc", "https://www.cnbc.com/id/19854910/device/rss/rss.html"),
    "gnews": ("news", "googlenews", "https://news.google.com/rss/search?q=Nvidia+when:7d&hl=en-US&gl=US&ceid=US:en"),
    # 법적·규제 전용 (2026-10-10 사용자: 법적 문제 기사는 꼼꼼히). q=Nvidia 100건 상한을 주가 해설이 채우는 것을 피한다
    "gnews_legal": ("news", "googlenews", "https://news.google.com/rss/search?q=Nvidia+(lawsuit+OR+antitrust+OR+DOJ+OR+FTC+OR+%22export+control%22+OR+BIS+OR+tariff+OR+%22export+license%22+OR+%22chips+to+China%22+OR+H20+OR+H200+OR+court+OR+ruling+OR+probe+OR+subpoena)+when:7d&hl=en-US&gl=US&ceid=US:en"),
}
# 외부 기사 1차 키워드 필터 — 제목+요약에 하나라도 있어야 분류 대상
NVDA_KEYWORDS = ("nvidia", "nvda", "jensen huang", "geforce", "blackwell", "rubin", "cuda", "hopper",
                 "h20", "h100", "h200", "gb200", "gb300", "dgx", "rtx")
# 제목에 Nvidia가 없어도 분류로 보내는 규제 어구 (2026-10-10). 무관하면 Gemini가 relevance 0으로 거른다
REGULATORY_KEYWORDS = ("export control", "export controls", "chip export", "chip exports", "ai chip", "ai chips", "semiconductor tariff",
                       "chip tariff", "bureau of industry and security", "entity list", "chip ban", "semiconductor export", "chips to china")
# 2차 출처 (2026-10-10) — 법적 쿼리가 끌어온 SEO 사이트·소셜·전재 피드. 중복 제거의 대표가 되지 못하고(1차 보도 우선),
# 단독이면 논평 취급(relevance ≤ 1 · repeat). 출처가 도메인 문자열이면 2차로 본다
SECONDARY_SOURCES = (
    "youtube", "stocktwits", "tradingview", "inshorts", "pluang", "biggo", "traders union", "crypto briefing", "beinsure",
    "within nigeria", "xenospectrum", "dealroom", "howl.link", "marketscreener", "financial-news", "tech-insider", "shattered.io",
    "startup fortune", "newsbytes", "sri lanka guardian", "wtvb", "devdiscourse",
)
SECONDARY_SOURCE_RE = re.compile(r"^(https?://|www\.)|\.(com|org|io|net|co\.uk|info|biz)/?$", re.I)


def is_secondary_source(source):
    s = (source or "").lower().strip()
    return any(p in s for p in SECONDARY_SOURCES) or bool(SECONDARY_SOURCE_RE.search(s))


NEWSROOM_BODY_MAX_CHARS = 6000    # 보도자료 본문 저장 상한 (raw_json)
FEDREG_TERMS = ("Nvidia", "advanced computing", "semiconductor export")
FEDREG_BACKFILL_DAYS = 30
FEDREG_SKIP_AGENCIES = ("Securities and Exchange Commission",)   # 거래소 자율규제 공지에 NVDA가 ETF 구성종목으로 언급될 뿐
# 전문 검색 "Nvidia"는 HFC 배분·약가 모델 같은 무관 문서(본문 어딘가 언급)까지 끌어온다 →
# 아래 기관이거나 제목에 아래 단어가 있을 때만 분류 대상. 나머지는 prefilter_reason='fedreg_offtopic'
FEDREG_ALLOW_AGENCIES = ("Industry and Security Bureau", "Commerce Department", "International Trade Commission",
                         "Trade Representative, Office of United States", "Office of the United States Trade Representative",
                         "Federal Trade Commission", "Justice Department", "Antitrust Division", "Science and Technology Policy Office",
                         "Treasury Department", "Foreign Assets Control Office", "Executive Office of the President")
FEDREG_TITLE_KEYWORDS = ("semiconductor", "chip", "export", "advanced computing", "artificial intelligence", " ai ", "china",
                         "entity list", "tariff", "section 232", "section 301", "nvidia", "data center", "supercomput")
COURTLISTENER_BACKFILL_DAYS = 30
COURTLISTENER_TIMEOUT = 180       # party 검색이 100초 넘게 걸린다 (2026-10-08 확인)
COURTLISTENER_QUERY = 'party:"NVIDIA"'
# 뉴스 중복 제거 (5절 ①) — 같은 날 ±1일 안에서 제목 토큰 자카드 유사도
DEDUPE_JACCARD = 0.6
DEDUPE_WINDOW_DAYS = 1
NEWS_COUNT_EVENT_MULT = 2.0       # 기사 수가 7일 평균의 2배 (#48 헤드라인 톤)
# ── ②단계: Gemini 분류 (4-A · 12절) ─────────────────────────────────────
AREAS = ["Earnings", "Flows", "Regulation", "Legal", "Product", "Demand", "Supply", "Corporate", "Macro", "Other"]
DIRECTIONS = ["positive", "negative", "uncertain", "neutral"]
NOVELTIES = ["new", "update", "repeat"]
RELEVANCE_RANGE = (0, 3)
RELEVANCE_EVENT_MIN = 2
PRIORITY_AREAS = ("Legal", "Regulation")   # 법적·규제 영역은 relevance 1부터 이벤트, 접히지 않고 맨 위 (2026-10-10 사용자)
PRIORITY_RELEVANCE_EVENT_MIN = 1


def event_min(area):
    """영역별 이벤트 relevance 하한."""
    return PRIORITY_RELEVANCE_EVENT_MIN if area in PRIORITY_AREAS else RELEVANCE_EVENT_MIN
NOVELTY_WINDOW_DAYS = 7           # 신규성 판단용 최근 사실 목록 창
NOVELTY_CONTEXT_MAX = 30
CLASSIFY_KINDS = ("news", "newsroom", "blog", "fedreg", "court")
CLASSIFY_BATCH_SIZE = 20
CLASSIFY_MAX_BATCHES_PER_RUN = 12
CLASSIFY_SINCE_DAYS = 30
CLASSIFY_MAX_ATTEMPTS = 2         # 검증 탈락이 이 횟수를 넘으면 prefilter_reason='classify_failed'
MAX_TEXT_CHARS = 1200
DEFAULT_MODEL = "gemini-3.5-flash"
KEY_COOLDOWN_SECONDS = 60
PER_BATCH_ATTEMPTS = 5
RETRY_SLEEP_SECONDS = 3

# ── 리포트 ───────────────────────────────────────────────────────────────
REPORT_TITLE_PREFIX = "엔비디아 데일리"
# 테스트 운영 (2026-10-10 사용자: "테스트 중" 라벨을 붙이고 우선 발행, 부족한 데이터는 안내 문구로). 끝내면 False — 제목은 바뀌지 않는다
TEST_MODE = True
TEST_NOTICE = ("이 리포트는 테스트 운영 중입니다. 수집·판정 규칙과 문구가 바뀔 수 있고, 일부 칸은 데이터가 쌓이는 중이라 비어 있습니다. "
               "빈 칸에는 이유와 채워질 시점을 적어 두었습니다.")
# 빈 칸 안내 문구 — 상태판 key별. 없는 key는 기본 문구
MISSING_HINTS = {
    "iv_atm_30d": "옵션 체인은 미국 장 마감 후에만 받습니다 — 다음 실행에서 채움",
    "implied_move_next_earnings": "옵션 체인 수집 후 계산",
    "pc_ratio_oi": "옵션 체인 수집 후 계산", "pc_ratio_vol": "옵션 체인 수집 후 계산",
    "gex_approx": "옵션 체인 수집 후 계산", "gex_flip_strike": "옵션 체인 수집 후 계산",
    "max_oi_strike_call": "옵션 체인 수집 후 계산", "max_oi_strike_put": "옵션 체인 수집 후 계산",
    "iv_rank_60d": "60거래일 스냅샷이 쌓인 뒤 표시",
    "rev_est_cq_7d_chg_pct": "7일치 스냅샷이 쌓인 뒤 표시",
    "ma_cross": "오늘 교차 없음",
    "smh_shares_out": "ETF 발행주식수는 아직 수집하지 않습니다 (운용사 페이지 파싱 보류)",
    "soxx_shares_out": "ETF 발행주식수는 아직 수집하지 않습니다 (운용사 페이지 파싱 보류)",
}
MISSING_DEFAULT_HINT = "이번 실행에서 받지 못함 — 다음 실행에서 재시도"
REPORT_LABELS = ["엔비디아", "미국 증시", "자동 리포트"]
