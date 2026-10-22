"""이슈 분류 코드 — 매일 기사 · 인물 발언 · 30년 사건표가 같이 쓰는 어휘 (doc/기획/이슈-분류-코드표.md, 2026-10-21).

세 파이프라인(종목 레이더 공용 뉴스 분류 · 데일리 CNBC 뉴스 · 인물 발언 레이더)이 이 모듈을 import 해 같은 enum 을 쓴다.
저장은 영어 코드, 화면은 ISSUE_KO (디자인 가이드라인 3-4). 코드를 바꿀 때는 여기 한 곳과 문서만 — 프롬프트의 목록은 PROMPT_BLOCK 으로 만든다.
사용자(2026-10-21): 미디어 쪽 분류 체계를 나중에 보여 줄 테니 그때 한 번 더 고친다 — 그래서 어휘를 한 곳에 모아 둔다.
"""

# 코드 → (화면 이름, 프롬프트용 영어 설명)
ISSUES = {
    "RATES_FED":        ("금리 · 연준",        "Fed decisions and officials, policy rates, Treasury yields, QT; also foreign central banks (ECB, BOJ)"),
    "INFLATION":        ("물가",               "CPI, PCE, PPI, wages, inflation expectations; oil only when framed as an inflation driver"),
    "GROWTH_JOBS":      ("경기 · 고용 · 소비", "GDP, payrolls, unemployment, retail sales, PMI, consumer sentiment, recession debate, labor supply"),
    "TARIFF_TRADE":     ("관세 · 무역",        "tariffs imposed/paused/negotiated, trade deals, trade deficits, supply-chain reshoring (export controls -> REGULATION)"),
    "GEOPOLITICS":      ("지정학",             "wars, ceasefires, Middle East, Taiwan, sanctions, terrorism, disasters, pandemics, US-China security/diplomacy"),
    "OIL_ENERGY":       ("유가 · 에너지",      "crude, natural gas, OPEC, power, nuclear, energy prices (AI data-center power demand -> AI_CAPEX)"),
    "AI_CAPEX":         ("AI 투자 · 반도체 수요", "data-center capex, GPU/accelerator demand, AI bubble debate, hyperscaler spending, AI power demand"),
    "EARNINGS":         ("실적 · 가이던스",    "earnings results, guidance, consensus, analyst targets/ratings — big tech included (ticker attribute tells)"),
    "CORP_EVENT":       ("기업 사건",          "M&A, IPO, buybacks, splits, dividends, executive changes, large contracts, product launches"),
    "REGULATION":       ("규제 · 산업정책",    "antitrust, export controls, subsidies, safety regulators (FDA, NHTSA), lawsuits, rulings"),
    "FISCAL_POLITICS":  ("재정 · 정치",        "shutdowns, debt ceiling, tax bills, elections, credit rating, appointments"),
    "CREDIT_BANKS":     ("금융 시스템 · 신용", "bank stress, credit crunch, private credit, CRE loans, bailouts, deposit flight"),
    "MARKET_STRUCTURE": ("수급 · 시장 구조",   "flash crashes, volatility products, options expiry, index inclusion, meme stocks, carry-trade unwinds, capitulation and rebounds"),
    "INVESTOR_CALLS":   ("투자자 매매 · 의견", "a known investor or commentator buys/sells, recommends, or warns about a stock/sector (Cramer, Burry, ARK trades)"),
    "FX_GLOBAL":        ("환율 · 해외 시장",   "dollar, yen, yuan, FX intervention, sharp moves in foreign markets (country attribute carries which)"),
    "CRYPTO":           ("암호화폐",           "bitcoin, crypto ETFs, stablecoin rules, exchanges"),
    "REAL_ESTATE":      ("부동산 · 주택",      "home prices, mortgage rates, housing starts, REITs"),
    "OTHER":            ("그 밖",              "market-related but none of the above"),
}
ISSUE_KO = {k: v[0] for k, v in ISSUES.items()}
SCOPES = ("market", "sector", "stock")
SCOPE_KO = {"market": "시장 전체", "sector": "업종", "stock": "개별 종목"}


def prompt_block():
    """프롬프트에 붙이는 ISSUE 목록 (영어). 세 프롬프트가 같은 글을 쓴다."""
    lines = [f"  {k:<17} {v[1]}" for k, v in ISSUES.items()]
    return "ISSUE (what is happening in the world — ONE code; pick the cause, not the effect):\n" + "\n".join(lines)


ATTR_BLOCK = """\
  "issue": string,              // ONE code from ISSUE below
  "subtopic": string,           // SHORTEST canonical noun phrase, 2-4 words, reused across items ("Tariff", "Oil Prices", "Memory Chips"). "" if none
  "scope": "market" | "sector" | "stock",   // what the item is about: the whole market, one sector, or one company
  "countries": string[],        // countries/regions involved, English short names ("China", "EU", "Japan"). [] if none
  "scheduled": boolean,         // true if a pre-announced release/decision/report (CPI, FOMC, earnings date), false if unexpected
  "surprise": integer -2..2     // for scheduled items: vs expectations (-2 much worse ... +2 much better); 0 if unknown or unscheduled"""


def coerce(item):
    """모델 답에서 이슈 속성만 안전하게 꺼낸다 — 어휘 밖이면 OTHER · 빈 값. 모델이 칸을 빼먹어도 분류 자체는 살린다."""
    issue = item.get("issue") if item.get("issue") in ISSUES else "OTHER"
    scope = item.get("scope") if item.get("scope") in SCOPES else None
    try:
        surprise = max(-2, min(2, int(item.get("surprise") or 0)))
    except (TypeError, ValueError):
        surprise = 0
    countries = [str(c)[:30] for c in item.get("countries") or [] if isinstance(c, str)][:5]
    return {"issue": issue, "subtopic": str(item.get("subtopic") or "")[:60], "scope": scope, "countries": countries,
            "scheduled": bool(item.get("scheduled")), "surprise": surprise}


# 30년 사건표 세부 종류(experiments/issue_store/event_vocab.py) → 이슈 코드 (문서 3-1)
FROM_EVENT_SUBKIND = {
    "전쟁 · 테러": "GEOPOLITICS", "휴전 · 종전": "GEOPOLITICS", "재난 · 팬데믹": "GEOPOLITICS", "해외 금융위기": "GEOPOLITICS",
    "선거 · 정치": "FISCAL_POLITICS", "미국 재정 · 부채한도": "FISCAL_POLITICS", "관세 · 무역": "TARIFF_TRADE",
    "규제 (수출 · 반독점)": "REGULATION", "환율 · 개입": "FX_GLOBAL", "유가 충격": "OIL_ENERGY",
    "연준 긴축 신호": "RATES_FED", "연준 완화": "RATES_FED", "해외 중앙은행": "RATES_FED",
    "경제지표 충격": "GROWTH_JOBS",   # 물가 충격은 detail 로 INFLATION 으로 보정 (events_add_issue.py)
    "금융기관 부실 · 신용경색": "CREDIT_BANKS", "시장 구조 사고": "MARKET_STRUCTURE", "기술주 · 반도체 급락": "MARKET_STRUCTURE",
    "투매 뒤 반등 · 바닥": "MARKET_STRUCTURE", "실적 · 전망": "EARNINGS", "애널리스트 의견": "EARNINGS", "기업 사업 소식": "CORP_EVENT",
}

# 인물 발언 레이더 주제 → 이슈 코드 (문서 3-2). 내용에 따라 갈리는 주제는 모델이 issue 를 직접 붙인다 — 이 표는 옛 행 보정용
FROM_PEOPLE_TOPIC = {
    "Trade": "TARIFF_TRADE", "Fed": "RATES_FED", "Tax": "FISCAL_POLITICS", "Energy": "OIL_ENERGY", "Immigration": "GROWTH_JOBS",
    "Regulation": "REGULATION", "Geopolitics": "GEOPOLITICS", "Company": "CORP_EVENT", "Product": "CORP_EVENT", "Deal": "CORP_EVENT",
    "Investment": "CORP_EVENT", "Stock Call": "INVESTOR_CALLS", "Sector Call": "INVESTOR_CALLS", "Position": "INVESTOR_CALLS",
    "Macro Warning": "MARKET_STRUCTURE", "Market Outlook": "MARKET_STRUCTURE", "Earnings": "EARNINGS", "Industry View": "AI_CAPEX",
    "Policy": "FISCAL_POLITICS",
}
