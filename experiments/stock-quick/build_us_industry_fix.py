"""미국 간단 종목 업계 카드 배정표 만들기 — ref/us_industry_fix.json (2026-11-25 사용자 "미국도 한국처럼 끝까지").

    python experiments/stock-quick/build_us_industry_fix.py

한국 ref/kr_industry_fix.json 과 같은 꼴: card = {종목: {name, group}} (group = industry_us.BIZ 묶음 하나 또는 둘), card_off = {종목: {name, why}}.
세부 업종(GICS) 기본 배정(SUB) 위에 종목별 예외(SYM · OFF)를 얹는다 — 503종목을 세부 업종별로 펼쳐 놓고 회사 사업과 견줘 정함.
새 종목이 명단에 들어오면 이 스크립트를 다시 돌리고, 배정이 틀리면 SYM · OFF 에 한 줄. full_us.py 가 이 파일을 읽는다(없는 종목은 SUB 기본값).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "stock-radar"))
import industry_us as I  # noqa: E402

NO_STAT = "맞는 월 통계 없음"
# 세부 업종 → 묶음. None = 카드 없음(이유는 SUB_WHY)
SUB = {
    "Hotels, Resorts & Cruise Lines": "travel", "Restaurants": "food", "Homebuilding": "homebuild", "Apparel, Accessories & Luxury Goods": "apparel",
    "Automotive Retail": "autoparts", "Automobile Manufacturers": "auto", "Casinos & Gaming": None, "Broadline Retail": "online", "Home Improvement Retail": "home",
    "Apparel Retail": "apparel", "Other Specialty Retail": None, "Automotive Parts & Equipment": "auto", "Computer & Electronics Retail": "electronics",
    "Specialized Consumer Services": None, "Footwear": "apparel", "Distributors": "autoparts", "Consumer Electronics": "electronics", "Leisure Products": "hobby",
    "Homefurnishing Retail": "furniture",
    "Asset Management & Custody Banks": "broker", "Financial Exchanges & Data": "broker", "Transaction & Payment Processing Services": "payments",
    "Property & Casualty Insurance": "pc_ins", "Diversified Banks": "bank", "Insurance Brokers": "pc_ins", "Regional Banks": "bank", "Investment Banking & Brokerage": "broker",
    "Life & Health Insurance": None, "Multi-line Insurance": "pc_ins", "Consumer Finance": "payments", "Multi-Sector Holdings": None, "Reinsurance": "pc_ins",
    "Application Software": "software", "Semiconductors": "semi", "Technology Hardware, Storage & Peripherals": "hardware", "Systems Software": "software",
    "Communications Equipment": "netgear", "Semiconductor Materials & Equipment": "semi", "IT Consulting & Other Services": "itsvc",
    "Electronic Equipment & Instruments": "components", "Internet Services & Infrastructure": "cloud", "Electronic Components": "components",
    "Electronic Manufacturing Services": "components", "Technology Distributors": "hardware",
    "Multi-Family Residential REITs": "apartment", "Single-Family Residential REITs": "apartment", "Data Center REITs": "cloud", "Retail REITs": None, "Telecom Tower REITs": None,
    "Health Care REITs": None, "Office REITs": None, "Real Estate Services": None, "Self-Storage REITs": None, "Hotel & Resort REITs": None, "Other Specialized REITs": None,
    "Industrial REITs": None, "Timber REITs": None,
    "Industrial Machinery & Supplies & Components": "capgoods", "Aerospace & Defense": "aero", "Building Products": "bldg", "Electrical Components & Equipment": "elec_equip",
    "Construction Machinery & Heavy Transportation Equipment": "machine", "Air Freight & Logistics": "freight", "Construction & Engineering": "machine",
    "Environmental & Facilities Services": None, "Diversified Support Services": None, "Rail Transportation": "rail", "Passenger Airlines": "airline",
    "Industrial Conglomerates": "capgoods", "Trading Companies & Distributors": "capgoods", "Cargo Ground Transportation": "freight",
    "Human Resource & Employment Services": "payroll", "Research & Consulting Services": None, "Heavy Electrical Equipment": "elec_equip",
    "Data Processing & Outsourced Services": None, "Agricultural & Farm Machinery": "capgoods", "Passenger Ground Transportation": None,
    "Specialty Chemicals": "chem", "Paper & Plastic Packaging Products & Materials": "paper", "Construction Materials": "aggregates", "Industrial Gases": "chem",
    "Fertilizers & Agricultural Chemicals": "chem", "Steel": "steel", "Metal, Glass & Plastic Containers": None, "Commodity Chemicals": "chem", "Copper": "copper", "Gold": "gold",
    "Oil & Gas Exploration & Production": "oil", "Oil & Gas Storage & Transportation": "midstream", "Oil & Gas Equipment & Services": "oilsvc",
    "Oil & Gas Refining & Marketing": "refine", "Integrated Oil & Gas": "oil",
    "Electric Utilities": "power", "Multi-Utilities": "power", "Independent Power Producers & Energy Traders": "power", "Gas Utilities": "gasutil", "Water Utilities": None,
    "Movies & Entertainment": "media", "Interactive Media & Services": "ad", "Advertising": "ad", "Cable & Satellite": "media", "Wireless Telecommunication Services": "telecom",
    "Broadcasting": "media", "Publishing": None, "Integrated Telecommunication Services": "telecom", "Interactive Home Entertainment": None,
    "Packaged Foods & Meats": "grocery", "Consumer Staples Merchandise Retail": "mart", "Household Products": "staples", "Soft Drinks & Non-alcoholic Beverages": "staples",
    "Agricultural Products & Services": "grain", "Distillers & Vintners": "alcohol", "Food Retail": "grocery", "Personal Care Products": "staples", "Tobacco": "tobacco",
    "Food Distributors": "food",
    "Health Care Equipment": "medtech", "Life Sciences Tools & Services": None, "Biotechnology": "pharma", "Pharmaceuticals": "pharma", "Health Care Services": None,
    "Health Care Distributors": "drugstore", "Managed Health Care": "managed", "Health Care Supplies": "medtech", "Health Care Facilities": "hospital", "Health Care Technology": None,
}
SUB_WHY = {
    "Casinos & Gaming": "카지노 — 마카오 · 라스베이거스 방문객 통계가 정부 월 통계에 없음", "Life & Health Insurance": "생명보험 — 보험료 월 통계 없음(금리는 함께 볼 지표로)",
    "Multi-Sector Holdings": "여러 사업 지주 — 한 업계 통계로 설명되지 않음", "Life Sciences Tools & Services": "연구 장비 · 시약 — 따로 보는 월 통계 없음(제약 생산은 함께 볼 지표로)",
    "Retail REITs": "상가 리츠 — 임대료 월 통계 없음(입점 매장 매출 · 금리는 함께 볼 지표로)", "Telecom Tower REITs": "통신 타워 리츠 — 타워 임대 월 통계 없음(통신사 매출 · 금리는 함께 볼 지표로)",
    "Water Utilities": "수도 — 수도 요금 월 통계를 FRED 에서 찾지 못함", "Interactive Home Entertainment": "게임 — 게임만 따로 보는 미국 월 통계 없음",
    "Publishing": "신문 · 출판 — 따로 보는 월 통계 없음",
}
# 종목별 예외 — 묶음
SYM = {
    **{k: "defense" for k in ("LMT", "NOC", "GD", "LHX", "HII", "LDOS")}, "RTX": ["aero", "defense"],   # 방산은 국방 장비 출하, RTX 는 민항 엔진 · 방산 반반
    "EQT": "natgas", "EXE": "natgas",                                   # 천연가스 생산 회사 — 유가 아닌 가스 값
    "PCAR": "truck", "CMI": "truck", "WAB": "rail",                      # 트럭 · 트럭 엔진 · 철도 차량
    "ROK": "capgoods", "AME": "capgoods", "EMR": "capgoods", "HUBB": "elec_equip",   # 공장 자동화 · 계측 = 설비 주문, 허벨 = 전력 설비
    "DD": "chem", "FERG": "bldg", "URI": "aggregates",                   # 듀폰 = 화학 소재, 퍼거슨 = 배관 자재 유통, 유나이티드 렌탈스 = 건설 장비 임대
    "MGM": "travel", "HST": "travel",                                    # 라스베이거스 호텔 · 호텔 리츠
    "TSCO": "home", "DASH": "food", "CVNA": "usedcar",                   # 농가 · 원예 용품점, 음식 배달, 중고차
    "CI": "managed", "CVS": "drugstore", "SOLV": "medtech", "VEEV": "software",
    "LYV": "live", "TKO": "live", "CASY": "staples",                     # 공연 · 스포츠 흥행, 케이시스 = 편의점 · 주유
}
# 종목별 예외 — 카드 없음
OFF = {
    "FSLR": "태양광 패널 — 반도체 통계가 설명하지 못함(전력 수요 · 금리는 함께 볼 지표로)", "AXON": "경찰 장비 · 소프트웨어 — 항공 · 방산 통계가 설명하지 못함",
    "ROP": "소프트웨어 여러 사업 — 전자 장비 통계가 설명하지 못함", "JKHY": "은행용 소프트웨어 — 결제 통계가 설명하지 못함", "COIN": "가상자산 거래소 — 증권 업종 통계가 설명하지 못함",
    **{k: "신용평가 · 지수 · 금융 데이터 — 증권 거래 통계가 설명하지 못함(금리는 함께 볼 지표로)" for k in ("SPGI", "MCO", "MSCI", "FDS")},
    "ULTA": "화장품 전문점 — 화장품만 따로 보는 매장 판매 통계 없음", "UBER": "차량 호출 — " + NO_STAT, "HSIC": "치과 · 동물병원 용품 유통 — 약국 판매 통계가 설명하지 못함",
    **{k: "검사 · 투석 서비스 — " + NO_STAT for k in ("DGX", "LH", "DVA")}, "IT": "리서치 구독 — IT 서비스 매출 통계가 설명하지 못함",
    "CTAS": "작업복 대여 — " + NO_STAT, "CPRT": "사고 차량 경매 — " + NO_STAT, "BR": "금융 문서 처리 — " + NO_STAT, "EFX": "신용 정보 — " + NO_STAT, "VRSK": "보험 데이터 분석 — " + NO_STAT,
    **{k: "쓰레기 · 시설 관리 — 요금 월 통계를 FRED 에서 찾지 못함" for k in ("WM", "RSG", "ROL", "VLTO")}, "BALL": "음료 캔 — " + NO_STAT, "TTWO": SUB_WHY["Interactive Home Entertainment"],
    "LVS": SUB_WHY["Casinos & Gaming"], "WYNN": SUB_WHY["Casinos & Gaming"], "VICI": "카지노 부동산 리츠 — 임대료 월 통계 없음", "BRK-B": SUB_WHY["Multi-Sector Holdings"],
}


def main():
    ref = json.load(open(os.path.join(EXP, "ref", "quick_ref.json"), encoding="utf-8"))["us"]
    card, off = {}, {}
    for s, e in sorted(ref.items()):
        sub = e.get("sub_en") or ""
        if s in I.SYM_BIZ_FIXED:   # 손으로 정한 정식 종목 — industry_us.SYM_BIZ_FIXED 가 먼저(여기는 기록)
            g = I.SYM_BIZ_FIXED[s]
        elif s in OFF:
            g = None
        else:
            g = SYM.get(s, SUB.get(sub))
        if g:
            g = list(g) if isinstance(g, (list, tuple)) else g
            assert all(k in I.BIZ for k in ([g] if isinstance(g, str) else g)), (s, g)
            card[s] = {"name": e["ko"], "group": g}
        else:
            why = OFF.get(s) or SUB_WHY.get(sub) or f"{e.get('sub') or sub} — {NO_STAT}"
            off[s] = {"name": e["ko"], "why": why}
    out = {"_note": "미국 간단 종목 업계 카드 배정 — build_us_industry_fix.py 가 만든다. 손으로 고치지 말고 그 스크립트의 SYM · OFF 를 고친 뒤 다시 만들 것", "card": card, "card_off": off}
    p = os.path.join(EXP, "ref", "us_industry_fix.json")
    open(p, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    missing = sorted({e.get("sub_en") for e in ref.values()} - set(SUB))
    print(f"카드 있음 {len(card)} · 카드 없음 {len(off)} → {p}" + (f" · 기본 배정에 없는 세부 업종 {missing}" if missing else ""))


if __name__ == "__main__":
    main()
