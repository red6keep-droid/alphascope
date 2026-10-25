"""경로표 — 발언(인물군 × 주제)이 어떤 경로로 어느 자산에 닿는가 (기획 9-2, 2026-10-25).

LLM 은 이 표 밖의 자산을 고르지 못한다: 경로 이름 · 자산은 여기서 정해지고, narrate 는 "왜 그 자리인지" 한 문장만 쓴다.
예측이 아니다 — "닿는 곳" 은 발언이 가는 길이고, 그날 반응(reaction)은 기록이다.
"""

CHANNEL_KO = {
    "rates": "금리 경로", "cost": "비용 경로", "supply": "공급 경로", "risk": "위험 회피 경로",
    "regulation": "규제 경로", "fiscal": "재정 경로", "earnings": "실적 경로", "attention": "관심 경로",
}
CHANNEL_WHY = {   # 경로 이름 옆 짧은 뜻 (독자용, 가이드라인 3-4: 어려운 말은 풀어서)
    "rates": "금리 기대가 바뀌면 국채 · 금융 · 성장주가 먼저 움직입니다",
    "cost": "관세는 수입 원가와 상대국 통화에 먼저 닿습니다",
    "supply": "공급 · 생산 발언은 유가와 에너지 업종에 먼저 닿습니다",
    "risk": "전쟁 · 긴장 발언은 변동성과 유가, 시장 전체에 닿습니다",
    "regulation": "규제는 그 업종과 이름이 오른 회사에 닿습니다",
    "fiscal": "세금 · 재정 발언은 시장 전체와 국채 금리에 닿습니다",
    "earnings": "제품 · 투자 · 실적 발언은 그 회사와 거래 상대의 실적 기대에 닿습니다",
    "attention": "유명 투자자의 매매 · 의견은 그 종목에 당일 관심으로 닿고, 되돌아오는 일이 잦습니다",
}
SECTOR_ETF = {"Semiconductor": "SMH", "Technology": "XLK", "Financials": "XLF", "Energy": "XLE", "Healthcare": "XLV", "Industrials": "XLI",
              "Consumer": "XLY", "Materials": "XLB", "Real Estate": "XLRE", "Utilities": "XLU", "Defense": "ITA", "Bonds/Rates": "^TNX",
              "Broad Market": "SPY", "Crypto": "BTC-USD", "Autos": "XLY"}
COUNTRY_FX = {"China": "CNY=X", "Japan": "JPY=X", "EU": "EURUSD=X", "Europe": "EURUSD=X", "Germany": "EURUSD=X", "France": "EURUSD=X",
              "Mexico": "MXN=X", "South Korea": "KRW=X", "Korea": "KRW=X", "India": "INR=X", "UK": "GBPUSD=X", "Canada": "CAD=X",
              "Taiwan": "TWD=X", "Brazil": "BRL=X", "Switzerland": "CHF=X", "Vietnam": "VND=X"}
MIDEAST = {"Iran", "Israel", "Saudi Arabia", "Qatar", "UAE", "Gaza", "Palestine", "Iraq", "Syria", "Lebanon", "Yemen"}
SEMI_COUNTRIES = {"China", "Taiwan"}
ASSET_KO = {"^TNX": "미국 10년물 금리", "XLF": "금융 업종", "QQQ": "나스닥 100", "SMH": "반도체", "SPY": "S&P 500", "CL=F": "유가(WTI)",
            "XLE": "에너지 업종", "^VIX": "변동성 VIX", "XLK": "기술 업종", "XLV": "헬스케어 업종", "XLI": "산업 업종", "XLY": "소비 업종",
            "XLB": "소재 업종", "XLRE": "부동산 업종", "XLU": "유틸리티 업종", "ITA": "방산 업종", "DX-Y.NYB": "달러 지수", "BTC-USD": "비트코인",
            "JPY=X": "엔 · 달러", "CNY=X": "위안 · 달러", "EURUSD=X": "유로 · 달러", "MXN=X": "페소 · 달러", "KRW=X": "원 · 달러", "INR=X": "루피 · 달러",
            "GBPUSD=X": "파운드 · 달러", "CAD=X": "캐나다 달러", "TWD=X": "대만 달러", "BRL=X": "헤알 · 달러", "CHF=X": "프랑 · 달러", "VND=X": "동 · 달러"}
MAX_ASSETS = 3


def asset_label(sym):
    """화면 이름 — 한국어 + 티커 괄호 (가이드라인 3-4). 종목은 티커만."""
    ko = ASSET_KO.get(sym)
    return f"{ko}({sym})" if ko else sym


def _dedupe(seq):
    out = []
    for x in seq:
        if x and x not in out:
            out.append(x)
    return out


def resolve(signal, own_ticker=None):
    """신호 → {"channel": 키, "assets": [심볼]} — 표 밖(Other · Personal …)은 None."""
    t, g = signal["topic"], signal.get("group")
    companies, sectors, countries = signal.get("companies") or [], signal.get("sectors") or [], signal.get("countries") or []
    sector_etfs = _dedupe(SECTOR_ETF.get(s) for s in sectors)
    if t == "Fed":
        return {"channel": "rates", "assets": ["^TNX", "XLF", "QQQ"]}
    if t == "Trade":
        fx = _dedupe(COUNTRY_FX.get(c) for c in countries)
        semi = ["SMH"] if any(c in SEMI_COUNTRIES for c in countries) else []
        return {"channel": "cost", "assets": _dedupe(fx[:1] + semi + ["SPY", "DX-Y.NYB"])[:MAX_ASSETS]}
    if t == "Energy":
        return {"channel": "supply", "assets": ["CL=F", "XLE"]}
    if t == "Geopolitics":
        oil = ["CL=F"] if any(c in MIDEAST for c in countries) else []
        return {"channel": "risk", "assets": _dedupe(["^VIX"] + oil + ["SPY"])[:MAX_ASSETS]}
    if t == "Regulation":
        a = _dedupe(sector_etfs[:1] + companies[:2])
        return {"channel": "regulation", "assets": (a or ["SPY"])[:MAX_ASSETS]}
    if t in ("Tax", "Immigration", "Policy"):
        return {"channel": "fiscal", "assets": ["SPY", "^TNX"]}
    if t == "Company":
        a = _dedupe(companies[:2] + sector_etfs[:1])
        return {"channel": "earnings", "assets": (a or ["SPY"])[:MAX_ASSETS]}
    if t in ("Product", "Investment", "Earnings", "Deal"):
        a = _dedupe([own_ticker] + [c for c in companies if c != own_ticker][:2])
        return {"channel": "earnings", "assets": (a or sector_etfs[:1] or ["SPY"])[:MAX_ASSETS]}
    if t == "Industry View":
        a = _dedupe(sector_etfs[:1] + [own_ticker])
        return {"channel": "earnings", "assets": (a or ["SPY"])[:MAX_ASSETS]}
    if t in ("Stock Call", "Position"):
        a = _dedupe(companies)[:MAX_ASSETS]
        return {"channel": "attention", "assets": a} if a else None
    if t == "Sector Call":
        return {"channel": "attention", "assets": (sector_etfs or ["SPY"])[:MAX_ASSETS]}
    if t in ("Macro Warning", "Market Outlook"):
        return {"channel": "risk", "assets": ["SPY", "^VIX"]}
    return None
