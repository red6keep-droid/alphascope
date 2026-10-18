"""시총 TOP 10 후보 20개 (doc/종목-레이더-기획.md 10-10, 2026-10-18 첫 선정).

후보 = S&P 500 편입 종목 중 시가총액 상위 20개 (외국 ADR 제외, 한 회사의 두 주식은 하나). 분기마다 다시 뽑는다.
slug 는 고정 페이지 영문 주소(`/p/<slug>.html`)가 된다. 한 번 만든 뒤에는 바꾸지 않는다 — 검색 이력이 쌓이는 주소다.
"""

# (티커, 한글 이름, 영문 주소, 섹터)
CANDIDATES = [
    ("NVDA", "엔비디아", "nvidia-nvda-stock", "반도체"),
    ("AAPL", "애플", "apple-aapl-stock", "빅테크"),
    ("GOOGL", "알파벳(구글)", "alphabet-googl-stock", "빅테크"),
    ("MSFT", "마이크로소프트", "microsoft-msft-stock", "빅테크"),
    ("AMZN", "아마존", "amazon-amzn-stock", "소비 · 플랫폼"),
    ("META", "메타", "meta-stock", "빅테크"),
    ("AVGO", "브로드컴", "broadcom-avgo-stock", "반도체"),
    ("TSLA", "테슬라", "tesla-tsla-stock", "소비 · 플랫폼"),
    ("BRK-B", "버크셔 해서웨이", "berkshire-hathaway-brk-b-stock", "금융"),
    ("LLY", "일라이 릴리", "eli-lilly-lly-stock", "헬스케어"),
    ("MU", "마이크론", "micron-mu-stock", "반도체"),
    ("WMT", "월마트", "walmart-wmt-stock", "필수 소비재"),
    ("JPM", "JP모건", "jpmorgan-jpm-stock", "금융"),
    ("AMD", "AMD", "amd-stock", "반도체"),
    ("V", "비자", "visa-v-stock", "결제"),
    ("XOM", "엑슨모빌", "exxonmobil-xom-stock", "에너지"),
    ("JNJ", "존슨앤드존슨", "johnson-johnson-jnj-stock", "헬스케어"),
    ("MA", "마스터카드", "mastercard-ma-stock", "결제"),
    ("ABBV", "애브비", "abbvie-abbv-stock", "헬스케어"),
    ("INTC", "인텔", "intel-intc-stock", "반도체"),
]

TOP_N = 10
SWAP_DAYS = 5      # 11위 밖으로 5거래일 연속 밀리면 빠진다 (10-10)
BENCH = "SPY"      # 기간별 수익률 비교 = S&P 500
REPORT_TYPE = {"NVDA"}   # 매일 리포트가 나가는 종목 = 상세가 리포트형 (최신 리포트 글로 링크)

BLOG = "https://alpha-scope.blogspot.com"
LIST_SLUG = "us-market-cap-top10"
LIST_TITLE = "미국 시가총액 상위 10개 종목 주가"
LIST_SLUG_TITLE = "us market cap top10"   # 처음 만들 때 이 제목으로 → 주소 고정, 바로 한글 제목으로 바꾼다
NVDA_REPORTS_URL = BLOG + "/search/label/%EC%97%94%EB%B9%84%EB%94%94%EC%95%84"   # 리포트형 상세의 임시 링크(라벨 목록). 발행 때 최신 글 주소로 바꾼다

BY_SYM = {c[0]: c for c in CANDIDATES}


def name(sym):
    return BY_SYM[sym][1]


def page_url(sym):
    return f"{BLOG}/p/{BY_SYM[sym][2]}.html"


def page_title(sym):
    return f"{name(sym)}({sym}) 주가 정보"


def slug_title(sym):
    return BY_SYM[sym][2].replace("-", " ")


LIST_URL = f"{BLOG}/p/{LIST_SLUG}.html"
