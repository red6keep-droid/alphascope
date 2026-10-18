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
SECTOR_ETF = {"반도체": ("SMH", "반도체"), "빅테크": ("XLK", "기술"), "소비 · 플랫폼": ("XLY", "경기 소비재"), "금융": ("XLF", "금융"),
              "헬스케어": ("XLV", "헬스케어"), "필수 소비재": ("XLP", "필수 소비재"), "에너지": ("XLE", "에너지"), "결제": ("XLF", "금융")}
# 구글 · 메타는 S&P 업종 분류상 커뮤니케이션 (XLC)
SECTOR_OVERRIDE = {"GOOGL": ("XLC", "커뮤니케이션"), "META": ("XLC", "커뮤니케이션")}


def sector_etf(sym):
    """종목이 속한 업종 ETF · 이름 — '○○ 업종으로 돈이 올까?' 카드와 업종 대비 하루 등락에 쓴다."""
    return SECTOR_OVERRIDE.get(sym) or SECTOR_ETF[BY_SYM[sym][3]]


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


TITLE_NAME = {"GOOGL": "구글 알파벳"}   # 이름의 괄호(알파벳(구글))를 빼고 · 검색어(구글 주가)를 앞에


def page_title(sym):
    """제목 = 검색어(이름 · 티커 · 주가) + 페이지에 실제로 있는 것(실적 일정). 괄호 없이 `테슬라 TSLA 주가` — 엔비디아 글 제목과 같게 (2026-10-18 사용자).
    테마가 `티커 주가` 에서 티커를 읽어 로고를 단다."""
    nm = TITLE_NAME.get(sym, name(sym))
    return f"{sym} 주가 · 실적 일정" if nm == sym else f"{nm} {sym} 주가 · 실적 일정"   # AMD 처럼 이름 = 티커면 한 번만 (2026-10-18)


def slug_title(sym):
    return BY_SYM[sym][2].replace("-", " ")


LIST_URL = f"{BLOG}/p/{LIST_SLUG}.html"


# 함께 보는 회사 (캘린더 `함께 보는 회사 실적은?`) — 종목마다 한 번 정한다 (2026-10-18 Claude 설계, 사용자 "AI 없이 올릴 수 있는 것까지").
# NVDA 리포트 cal_cards.PEER_ROLE 과 같은 뜻 : 고객 · 공급 · 경쟁 (+ 버크셔는 큰 보유 종목). 실적 일정을 받을 수 있는 미국 상장 종목만 (TSMC 는 ADR).
PEERS = {
    "AAPL": {"TSM": "공급", "QCOM": "공급", "AVGO": "공급", "GOOGL": "협력"},
    "GOOGL": {"MSFT": "경쟁", "META": "경쟁", "AMZN": "경쟁", "NVDA": "공급"},
    "MSFT": {"GOOGL": "경쟁", "AMZN": "경쟁", "ORCL": "경쟁", "NVDA": "공급"},
    "AMZN": {"WMT": "경쟁", "MSFT": "경쟁", "GOOGL": "경쟁", "UPS": "협력"},
    "META": {"GOOGL": "경쟁", "SNAP": "경쟁", "PINS": "경쟁", "NVDA": "공급"},
    "AVGO": {"NVDA": "경쟁", "MRVL": "경쟁", "AAPL": "고객", "GOOGL": "고객"},
    "TSLA": {"GM": "경쟁", "F": "경쟁", "RIVN": "경쟁", "NVDA": "공급"},
    "BRK-B": {"AAPL": "보유", "AXP": "보유", "BAC": "보유", "KO": "보유"},
    "LLY": {"NVO": "경쟁", "MRK": "경쟁", "PFE": "경쟁", "ABBV": "경쟁"},
    "MU": {"NVDA": "고객", "AMD": "고객", "WDC": "경쟁", "AAPL": "고객"},
    "WMT": {"COST": "경쟁", "TGT": "경쟁", "AMZN": "경쟁", "KR": "경쟁"},
    "JPM": {"BAC": "경쟁", "WFC": "경쟁", "C": "경쟁", "GS": "경쟁"},
    "AMD": {"NVDA": "경쟁", "INTC": "경쟁", "TSM": "공급", "MSFT": "고객"},
    "V": {"MA": "경쟁", "AXP": "경쟁", "PYPL": "경쟁"},
    "XOM": {"CVX": "경쟁", "COP": "경쟁", "SLB": "공급"},
    "JNJ": {"PFE": "경쟁", "MRK": "경쟁", "ABT": "경쟁"},
    "MA": {"V": "경쟁", "AXP": "경쟁", "PYPL": "경쟁"},
    "ABBV": {"LLY": "경쟁", "MRK": "경쟁", "AMGN": "경쟁"},
    "INTC": {"AMD": "경쟁", "NVDA": "경쟁", "TSM": "경쟁", "QCOM": "경쟁"},
}
PEER_KO = {"TSM": "TSMC", "QCOM": "퀄컴", "ORCL": "오라클", "UPS": "UPS", "SNAP": "스냅", "PINS": "핀터레스트", "MRVL": "마벨", "GM": "GM", "F": "포드",
           "RIVN": "리비안", "AXP": "아메리칸 익스프레스", "BAC": "뱅크오브아메리카", "KO": "코카콜라", "NVO": "노보 노디스크", "MRK": "머크", "PFE": "화이자",
           "WDC": "웨스턴디지털", "COST": "코스트코", "TGT": "타깃", "KR": "크로거", "WFC": "웰스파고", "C": "씨티그룹", "GS": "골드만삭스", "PYPL": "페이팔",
           "CVX": "셰브런", "COP": "코노코필립스", "SLB": "SLB", "ABT": "애보트", "AMGN": "암젠"}


def peer_name(sym):
    return BY_SYM[sym][1] if sym in BY_SYM else PEER_KO.get(sym, sym)
