"""미국 업계 카드 — FRED 공식 통계로 `업계상황` 탭의 `○○ 업계 ○○은?` 카드.

사용자 결정(11-01): 독자는 업계 상황을 빨리 파악하려는 것이라 방향(▲▼)은 한국 카드처럼 붙인다. 검증 결과(doc/검증/미국-업종지표-검증.md ·
미국-빅테크-지표-검증.md)는 독자에게 쓰지 않는다 — 카드는 정보 전달까지.
빅테크는 회사마다 사업에 맞는 업계 — 옛 `빅테크 업계 고객 설비투자는?`(핵심 자본재 주문) 대신.

카드 = (꼬리 질문, FRED 번호, 지표 이름, 모드, 출처 기관, 키). 모드: qty(늘고 있음 · 줄고 있음) · price(오르는 중 · 내리는 중) — 1년 전 같은 달(분기 자료는 같은 분기)보다 ±5%.
수익성 = 업종 기업이익(분기, 미국 경제분석국) 1년 전 같은 분기보다 ±10% → 나아짐 · 나빠짐.
"""
import datetime
import json
import os
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "data", "fred_us.json")
LIM_WORK, LIM_MONEY = 5.0, 10.0

FED, CENSUS, BLS, BEA = "미국 연방준비제도", "미국 인구조사국", "미국 노동통계국", "미국 경제분석국"
EIA, BTS, DOT = "미국 에너지정보청", "미국 교통통계국", "미국 연방도로청"

# 업계 묶음 → (카드 제목에 쓰는 업계 이름, 일감 · 값 카드들, 수익성 카드)
BIZ = {
    "semi":    ("반도체", [("생산은?", "IPG3344S", "반도체 생산지수", "qty", FED, "semi_ip"), ("제품 값은?", "PCU33443344", "반도체 생산자물가", "price", BLS, "semi_ppi")],
                ("N501RC1Q027SBEA", "컴퓨터 · 전자제품 업종 기업이익", "tech_profit")),
    "ad":      ("인터넷 광고", [("매출은?", "QREV519TUSY", "인터넷 서비스(검색 · 소셜) 매출", "qty", CENSUS, "net_rev"),
                            ("단가는?", "WPU366101", "인터넷 광고 생산자물가", "price", BLS, "ad_ppi")], None),
    "cloud":   ("클라우드", [("매출은?", "REV518TMSA", "데이터 처리 · 호스팅 매출", "qty", CENSUS, "hosting_rev")], None),
    "software": ("소프트웨어", [("매출은?", "REV5112TAXABL144QSA", "소프트웨어 회사 매출", "qty", CENSUS, "sw_rev")], None),
    "sw_invest": ("소프트웨어", [("기업 투자는?", "B985RC1Q027SBEA", "기업 소프트웨어 투자", "qty", BEA, "sw_invest")], None),
    "electronics": ("전자제품", [("판매는?", "RSEAS", "전자제품 · 가전 매장 판매", "qty", CENSUS, "elec_sales")], None),
    "mart":    ("대형 유통", [("판매는?", "RSGMS", "종합소매(대형마트) 판매", "qty", CENSUS, "retail_gm")], ("N415RC1Q027SBEA", "소매업 기업이익", "retail_profit")),
    "staples": ("소비재", [("소매 판매는?", "RSXFS", "소매판매 (외식 제외)", "qty", CENSUS, "retail_all")], None),
    "home":    ("건자재 유통", [("판매는?", "RSBMGESD", "건자재 · 원예 판매", "qty", CENSUS, "building_mat")], None),
    "food":    ("외식", [("판매는?", "RSFSDP", "외식 판매", "qty", CENSUS, "food_service")], None),
    "online":  ("온라인 유통", [("판매는?", "RSNSR", "무점포(온라인) 판매", "qty", CENSUS, "nonstore")], None),
    "auto":    ("자동차", [("판매는?", "TOTALSA", "신차 판매", "qty", BEA, "auto_sales"), ("생산은?", "IPG3361T3S", "자동차 · 부품 생산지수", "qty", FED, "auto_ip")], None),
    "bank":    ("은행", [("대출은?", "TOTLL", "은행 대출", "qty", FED, "bank_loans")], None),
    "oil":     ("석유", [("유가는?", "MCOILWTICO", "유가 (WTI)", "price", "미국 에너지정보청", "wti")], ("N404RC1Q027SBEA", "석유 · 석탄 제품 업종 기업이익", "oil_profit")),
    "power":   ("전력", [("생산은?", "IPG2211S", "전력 생산지수", "qty", FED, "power_ip"), ("전기요금은?", "CUSR0000SEHF01", "전기요금 (소비자물가)", "price", BLS, "power_cpi")],
                ("N419RC1Q027SBEA", "전기 · 가스 업종 기업이익", "util_profit")),
    "pharma":  ("제약", [("생산은?", "IPG3254S", "의약품 생산지수", "qty", FED, "pharma_ip"), ("제품 값은?", "PCU32543254", "의약품 생산자물가", "price", BLS, "pharma_ppi")], None),
    "machine": ("산업재", [("건설 투자는?", "PNRESCONS", "비주거 건설 지출", "qty", CENSUS, "nonres_build")], None),
    "chem":    ("화학", [("생산은?", "IPG325S", "화학 생산지수", "qty", FED, "chem_ip")], None),
    # ── — 503종목 점검 뒤 새 묶음. 모두 미국 정부 기관 통계(FRED 경유). 저작권 표시가 있는 민간 자료(프레디맥 주택담보대출 금리 · IMF 원자재 값)는 쓰지 않는다
    "travel":  ("여행 · 숙박", [("숙박 요금은?", "CUSR0000SEHB", "숙박 요금 (소비자물가)", "price", BLS, "lodging_cpi")], None),
    "airline": ("항공", [("여객은?", "AIRRPMTSID11", "항공 여객 수송 (유상 여객 마일)", "qty", BTS, "air_rpm"), ("항공 요금은?", "CUSR0000SETG01", "항공 요금 (소비자물가)", "price", BLS, "airfare_cpi")], None),
    "homebuild": ("주택 건설", [("주택 착공은?", "HOUST", "주택 착공 (연율)", "qty", CENSUS, "housing_starts"), ("새집 판매는?", "HSN1F", "새 단독주택 판매 (연율)", "qty", CENSUS, "new_home_sales")], None),
    "bldg":    ("건축 자재", [("주택 건설 지출은?", "PRRESCONS", "민간 주택 건설 지출", "qty", CENSUS, "res_build")], None),
    "aggregates": ("건설 자재", [("건설 지출은?", "TTLCONS", "전체 건설 지출", "qty", CENSUS, "total_build"), ("자재 값은?", "WPUSI012011", "건설 자재 생산자물가", "price", BLS, "constr_mat_ppi")], None),
    "aero":    ("항공우주", [("생산은?", "IPG3364T9S", "항공우주 · 기타 운송장비 생산지수", "qty", FED, "aero_ip")], None),
    "defense": ("방산", [("국방 장비 출하는?", "ADEFVS", "국방 자본재 출하", "qty", CENSUS, "defense_ship")], None),
    "capgoods": ("산업 기계", [("설비 주문은?", "NEWORDER", "핵심 자본재 주문 (국방 · 항공기 제외)", "qty", CENSUS, "core_orders"), ("생산은?", "IPG333S", "기계 생산지수", "qty", FED, "machinery_ip")], None),
    "elec_equip": ("전기 장비", [("주문은?", "A35SNO", "전기 장비 · 부품 주문", "qty", CENSUS, "elec_orders")], None),
    "truck":   ("트럭", [("대형 트럭 판매는?", "HTRUCKSSAAR", "대형 트럭 판매 (연율)", "qty", BEA, "heavy_trucks")], None),
    "rail":    ("철도", [("화물은?", "RAILFRTCARLOADSD11", "철도 화물 (화차 수)", "qty", BTS, "rail_carloads"), ("컨테이너 화물은?", "RAILFRTINTERMODALD11", "철도 복합 운송 (컨테이너 · 트레일러)", "qty", BTS, "rail_intermodal")], None),
    "freight": ("화물 운송", [("화물 운송량은?", "TSIFRGHT", "화물 운송 서비스 지수", "qty", BTS, "freight_tsi")], None),
    "payments": ("결제", [("소비 지출은?", "RSAFS", "소매 · 외식 판매", "qty", CENSUS, "retail_food"), ("카드 빚은?", "REVOLSL", "카드 등 회전 신용 잔액", "qty", FED, "revolving_credit")], None),
    "broker":  ("증권 · 자산운용", [("매출은?", "REV523TAXABL144QNSA", "증권 · 투자 업종 매출", "qty", CENSUS, "securities_rev")], None),
    "pc_ins":  ("손해보험", [("보험료는?", "PCU924126924126", "손해보험료 (생산자물가)", "price", BLS, "pc_premium_ppi")], None),
    "medtech": ("의료기기", [("생산은?", "IPN3391S", "의료기기 · 용품 생산지수", "qty", FED, "medtech_ip"), ("제품 값은?", "PCU33913391", "의료기기 생산자물가", "price", BLS, "medtech_ppi")], None),
    "hospital": ("병원", [("매출은?", "REV622ALLEST144QSA", "병원 매출", "qty", CENSUS, "hospital_rev"), ("병원비는?", "CUSR0000SEMD", "병원 서비스 요금 (소비자물가)", "price", BLS, "hospital_cpi")], None),
    "managed": ("건강보험", [("보험료는?", "PCU524114524114", "건강보험료 (생산자물가)", "price", BLS, "health_premium_ppi")], None),
    "drugstore": ("의약품 유통", [("약국 판매는?", "RSHPCS", "약국 · 건강용품 매장 판매", "qty", CENSUS, "pharmacy_sales")], None),
    "hardware": ("컴퓨터 장비", [("주문은?", "A34SNO", "컴퓨터 · 전자제품 주문", "qty", CENSUS, "computer_orders"), ("생산은?", "IPG3341S", "컴퓨터 · 주변기기 생산지수", "qty", FED, "computer_ip")], None),
    "netgear": ("통신 장비", [("생산은?", "IPG3342S", "통신 장비 생산지수", "qty", FED, "comm_equip_ip")], None),
    "components": ("전자 부품", [("주문은?", "A34SNO", "컴퓨터 · 전자제품 주문", "qty", CENSUS, "computer_orders")], None),
    "itsvc":   ("IT 서비스", [("매출은?", "QREV5415TUSY", "컴퓨터 시스템 설계 · 관련 서비스 매출", "qty", CENSUS, "it_services_rev")], None),
    "media":   ("미디어", [("유료 방송 요금은?", "CUSR0000SERA02", "케이블 · 위성 · 실시간 스트리밍 요금 (소비자물가)", "price", BLS, "paytv_cpi")], None),
    "live":    ("공연 · 스포츠", [("입장료는?", "CUSR0000SS62031", "영화 · 공연 입장료 (소비자물가)", "price", BLS, "admission_cpi")], None),
    "telecom": ("통신", [("무선 통신 매출은?", "QREV517312TUSY", "무선 통신사 매출", "qty", CENSUS, "wireless_rev")], None),
    "apartment": ("임대 주택", [("집세는?", "CUSR0000SEHA", "집세 (소비자물가)", "price", BLS, "rent_cpi")], None),
    "steel":   ("철강", [("생산은?", "IPG3311A2S", "철강 생산지수", "qty", FED, "steel_ip"), ("철강 값은?", "WPU101", "철강 생산자물가", "price", BLS, "steel_ppi")], None),
    "paper":   ("포장재", [("생산은?", "IPG322S", "종이 · 포장재 생산지수", "qty", FED, "paper_ip"), ("종이 값은?", "WPU0913", "종이 생산자물가", "price", BLS, "paper_ppi")], None),
    "copper":  ("구리", [("구리 값은?", "WPUSI019011", "구리 · 구리 제품 생산자물가", "price", BLS, "copper_ppi")], None),
    "gold":    ("금", [("금 값은?", "IR14270", "금 수입 가격지수", "price", BLS, "gold_import_px")], None),
    "apparel": ("의류", [("판매는?", "RSCCAS", "의류 · 잡화 매장 판매", "qty", CENSUS, "clothing_sales")], None),
    "autoparts": ("자동차 정비 · 부품 유통", [("주행 거리는?", "TRFVOLUSM227NFWA", "자동차 주행 거리", "qty", DOT, "vehicle_miles")], None),
    "usedcar": ("중고차", [("중고차 값은?", "CUSR0000SETA02", "중고차 값 (소비자물가)", "price", BLS, "used_car_cpi")], None),
    "furniture": ("가구", [("판매는?", "RSFHFS", "가구 · 생활용품 매장 판매", "qty", CENSUS, "furniture_sales")], None),
    "hobby":   ("취미 · 완구", [("판매는?", "RSSGHBMS", "스포츠 · 취미 · 서점 판매", "qty", CENSUS, "hobby_sales")], None),
    "grocery": ("식료품", [("식료품점 판매는?", "RSGCS", "식료품점 판매", "qty", CENSUS, "grocery_sales"), ("식품 값은?", "CUSR0000SAF11", "집에서 먹는 식품 값 (소비자물가)", "price", BLS, "food_home_cpi")], None),
    "tobacco": ("담배", [("담배 값은?", "CUSR0000SEGA", "담배 값 (소비자물가)", "price", BLS, "tobacco_cpi")], None),
    "alcohol": ("주류", [("술값은?", "CUSR0000SAF116", "주류 값 (소비자물가)", "price", BLS, "alcohol_cpi")], None),
    "grain":   ("곡물 가공", [("콩 값은?", "WPU01830131", "콩 생산자물가", "price", BLS, "soybean_ppi"), ("옥수수 값은?", "WPS012202", "옥수수 생산자물가", "price", BLS, "corn_ppi")], None),
    "payroll": ("급여 · 인사 서비스", [("일자리는?", "PAYEMS", "비농업 일자리 수", "qty", BLS, "payrolls")], None),
    "natgas":  ("천연가스", [("가스 값은?", "MHHNGSP", "천연가스 값 (헨리 허브)", "price", EIA, "henry_hub")], None),
    "midstream": ("석유 · 가스 수송", [("생산량은?", "IPG211S", "석유 · 가스 생산지수", "qty", FED, "oilgas_ip")], None),
    "refine":  ("정유", [("휘발유 값은?", "GASREGW", "휘발유 소매 값", "price", EIA, "gasoline_px")], None),
    "oilsvc":  ("유전 서비스", [("시추는?", "IPN213111S", "석유 · 가스 시추 생산지수", "qty", FED, "drilling_ip")], None),
    "gasutil": ("가스 공급", [("가스 요금은?", "CUSR0000SEHF02", "도시가스 요금 (소비자물가)", "price", BLS, "gas_cpi")], None),
}

# 값 읽는 법 — 번호 → (나누는 수, 단위, 소수 자리). 여기에 없으면 render_pages._fred_value 의 옛 규칙(번호 앞글자) → 지수
UNITS = {
    **{k: (100, "억 달러", 0) for k in ("PRRESCONS", "TTLCONS", "ANAPNO", "ADEFNO", "ADEFVS", "A35SNO", "PNRESCONS")},
    "REVOLSL": (1e6, "조 달러", 2), "HOUST": (10, "만 채", 1), "HSN1F": (10, "만 채", 1), "HTRUCKSSAAR": (0.01, "만 대", 1),
    "AIRRPMTSID11": (1e5, "억 마일", 0), "RAILFRTCARLOADSD11": (1e4, "만 대", 1), "RAILFRTINTERMODALD11": (1e4, "만 개", 1), "TRFVOLUSM227NFWA": (100, "억 마일", 0),
    "PAYEMS": (10, "만 명", 0), "MHHNGSP": (1, "달러", 2), "GASREGW": (1, "달러", 2), "DCOILWTICO": (1, "달러", 1), "WJFUELUSGULF": (1, "달러", 2),
    "DGS10": (1, "%", 2), "DRCCLACBS": (1, "%", 2),
}
PCT = {"DGS10", "DRCCLACBS"}   # 변화 = %p
PARTIAL = {"TOTLL", "GASREGW", "DGS10", "DCOILWTICO", "WJFUELUSGULF"}   # 주간 · 일별 자료 — 덜 찬 이번 달은 뺀다(달 평균끼리 견준다)

# 함께 볼 지표 (2026-11-25, 한국 universe_kr.RELATED 와 같은 기준) — 업계 통계는 아니지만 그 회사의 원가이거나 손님 수. 판정 없음, 1년 전 같은 달(분기)과 견줌
#   묶음 → [(번호, 이름, 왜 함께 보나)]. 종목 지정(RELATED_SYM)이 먼저
_R10 = ("DGS10", "10년 국채 금리 (달 평균)")
_WTI = ("DCOILWTICO", "유가 (WTI, 달 평균)")
_DC = ("REV518TMSA", "데이터 처리 · 호스팅 매출")
RELATED = {
    "travel": [("AIRRPMTSID11", "항공 여객 수송", "비행기로 움직인 여행객 — 호텔 · 크루즈 손님"), ("GASREGW", "휘발유 소매 값 (달 평균)", "자동차 여행 비용")],
    "airline": [("WJFUELUSGULF", "항공유 값 (달 평균)", "연료비 — 가장 큰 원가")],
    "homebuild": [(*_R10, "주택담보대출 금리의 바탕 — 집 사는 사람의 부담"), ("WPU081", "목재 생산자물가", "집 짓는 원가")],
    "bldg": [("HOUST", "주택 착공 (연율)", "새로 짓는 집 — 자재 · 냉난방 손님"), (*_R10, "주택담보대출 금리의 바탕")],
    "aggregates": [("HOUST", "주택 착공 (연율)", "새로 짓는 집 — 골재 · 시멘트 손님")],
    "aero": [("ANAPNO", "민간 항공기 · 부품 주문", "앞으로 만들 일감 — 달마다 크게 출렁임"), ("AIRRPMTSID11", "항공 여객 수송", "항공사가 비행기를 더 사는 바탕")],
    "defense": [("ADEFNO", "국방 자본재 주문", "앞으로 만들 일감 — 달마다 크게 출렁임")],
    "capgoods": [("IPMAN", "제조업 생산지수", "공장이 돌아가는 정도 — 기계 손님")],
    "elec_equip": [("IPG2211S", "전력 생산지수", "전기를 더 만들수록 설비가 필요"), ("PNRESCONS", "비주거 건설 지출", "공장 · 데이터센터 건설 — 전기 장비 손님")],
    "truck": [("TSIFRGHT", "화물 운송 서비스 지수", "실어 나를 짐 — 운송 회사가 트럭을 사는 바탕")],
    "rail": [(*_WTI, "기관차 연료비의 바탕"), ("IPMAN", "제조업 생산지수", "실어 나를 짐을 만드는 공장")],
    "freight": [(*_WTI, "연료비의 바탕"), ("RSNSR", "무점포(온라인) 판매", "택배 물량")],
    "payments": [("PAYEMS", "비농업 일자리 수", "일하는 사람 — 소비 여력")],
    "broker": [(*_R10, "채권 값 · 자금 조달 비용")],
    "pc_ins": [(*_R10, "보험사가 굴리는 채권 금리"), ("CUSR0000SETA02", "중고차 값 (소비자물가)", "자동차 보험 보상 원가")],
    "medtech": [("REV622ALLEST144QSA", "병원 매출", "의료기기를 사는 손님")],
    "managed": [("CPIMEDSL", "의료비 (소비자물가)", "보험사가 내주는 진료비 — 원가")],
    "hardware": [(*_DC, "데이터센터 — 서버 · 저장장치 손님")],
    "netgear": [(*_DC, "데이터센터 — 통신 장비 손님")],
    "components": [(*_DC, "데이터센터 — 부품 손님"), ("IPG3361T3S", "자동차 · 부품 생산지수", "자동차 — 전자 부품 손님")],
    "itsvc": [("B985RC1Q027SBEA", "기업 소프트웨어 투자", "기업이 전산에 쓰는 돈")],
    "apartment": [(*_R10, "부동산 값과 빚 부담")],
    "steel": [("IPG3361T3S", "자동차 · 부품 생산지수", "강판 손님"), ("TTLCONS", "전체 건설 지출", "철근 · 형강 손님")],
    "paper": [("RSNSR", "무점포(온라인) 판매", "택배 상자 손님")],
    "autoparts": [("GASREGW", "휘발유 소매 값 (달 평균)", "차를 모는 비용 — 덜 몰면 정비도 줄어듦")],
    "midstream": [("MHHNGSP", "천연가스 값 (헨리 허브)", "실어 나르는 가스 값")],
    "refine": [(*_WTI, "원유 값 — 원가")],
    "oilsvc": [(*_WTI, "유가 — 시추를 늘릴지 정하는 바탕")],
    "semi": [(*_DC, "데이터센터 — AI 반도체 손님")],
    "auto": [("GASREGW", "휘발유 소매 값 (달 평균)", "차를 모는 비용"), (*_R10, "자동차 할부 금리의 바탕")],
    "bank": [(*_R10, "대출 금리의 바탕"), ("DRCCLACBS", "신용카드 연체율", "못 받는 돈 — 오르면 손실")],
    "power": [("MHHNGSP", "천연가스 값 (헨리 허브)", "발전 연료 — 원가")],
    "home": [("HOUST", "주택 착공 (연율)", "새집 — 자재 · 공구 손님"), (*_R10, "주택담보대출 금리의 바탕")],
    "food": [("CUSR0000SAF11", "집에서 먹는 식품 값 (소비자물가)", "식재료 값 — 원가")],
    "chem": [("MHHNGSP", "천연가스 값 (헨리 허브)", "원료이자 연료 — 원가")],
    "ad": [("RSAFS", "소매 · 외식 판매", "광고주가 버는 돈 — 광고비의 바탕")],
    "online": [("PAYEMS", "비농업 일자리 수", "일하는 사람 — 소비 여력")],
    "mart": [("CUSR0000SAF11", "집에서 먹는 식품 값 (소비자물가)", "장보기 물가")],
}
_REIT = [(*_R10, "부동산 값과 빚 부담")]
RELATED_SYM = {
    **{k: [("DRCCLACBS", "신용카드 연체율", "못 받는 돈 — 오르면 손실"), ("PAYEMS", "비농업 일자리 수", "일하는 사람 — 소비 여력")] for k in ("AXP", "COF", "SYF")},
    **{k: [(*_R10, "보험사가 굴리는 채권 금리")] for k in ("MET", "PRU", "AFL", "GL", "PFG", "BRK-B")},
    **{k: [("QREV517312TUSY", "무선 통신사 매출", "타워를 빌려 쓰는 손님"), (*_R10, "부동산 값과 빚 부담")] for k in ("AMT", "CCI", "SBAC")},
    **{k: [("RSAFS", "소매 · 외식 판매", "입점 매장의 매출"), (*_R10, "부동산 값과 빚 부담")] for k in ("SPG", "O", "KIM", "REG", "FRT")},
    "PLD": [("RSNSR", "무점포(온라인) 판매", "물류 창고를 빌리는 손님"), (*_R10, "부동산 값과 빚 부담")],
    **{k: _REIT for k in ("DOC", "VTR", "WELL", "ARE", "BXP", "EXR", "PSA", "VICI", "IRM", "CBRE", "CSGP")},
    **{k: [("IPG3254S", "의약품 생산지수", "제약사 — 연구 장비 · 시약 손님")] for k in ("TMO", "DHR", "A", "WAT", "MTD", "ILMN", "IQV", "CRL", "TECH", "RVTY")},
    "WY": [("HOUST", "주택 착공 (연율)", "새집 — 목재 손님"), ("WPU081", "목재 생산자물가", "목재 값")],
    "FSLR": [("IPG2211S", "전력 생산지수", "전기 수요 — 태양광 발전소 손님"), (*_R10, "발전소 건설 자금 부담")],
    **{k: [("AIRRPMTSID11", "항공 여객 수송", "비행기로 움직인 여행객")] for k in ("LVS", "WYNN", "UBER")},
    **{k: [(*_R10, "회사채 발행 비용 — 발행이 늘면 평가 · 지수 수수료도 늘어남")] for k in ("SPGI", "MCO", "MSCI", "FDS")},
    **{k: [("TTLCONS", "전체 건설 지출", "쓰레기 · 시설 관리 손님")] for k in ("WM", "RSG")},
}

SYM_BIZ = {**{s: "semi" for s in ("NVDA", "AVGO", "MU", "AMD", "INTC", "TSM", "ASML", "LRCX", "AMAT")},
           "AAPL": "electronics", "META": "ad", "GOOGL": ("ad", "cloud"), "MSFT": ("software", "cloud"), "ORCL": ("sw_invest", "cloud"),   # 빅테크 = 회사별 (11-01)
           "WMT": "mart", "COST": "mart", "KO": "staples", "PG": "staples", "PM": "tobacco", "HD": "home", "MCD": "food", "AMZN": "online", "TSLA": "auto",
           "JPM": "bank", **{s: "oil" for s in ("XOM", "CVX", "COP", "EOG")}, "SLB": "oilsvc", **{s: "power" for s in ("CEG", "NEE", "SO", "VST")},
           **{s: "pharma" for s in ("LLY", "JNJ", "ABBV")}, "CAT": "machine", "GE": "aero", "VRT": "elec_equip", "LIN": "chem"}   # 2026-11-25: 버크셔 = 은행 아님(뺌) · GE = 항공우주 · 버티브 = 전기 장비 · 필립모리스 = 담배
SYM_BIZ_FIXED = dict(SYM_BIZ)   # 손으로 정한 정식 종목 — 배정표보다 먼저
try:   # 그 밖의 종목(정식 · 간단 모두) = 배정표 ref/us_industry_fix.json (build_us_industry_fix.py, 2026-11-25). 정식 명단에 있지만 손 지정이 없던 종목(비자 · 델 …)도 카드가 붙는다
    _fix = json.load(open(os.path.join(BASE, "..", "ref", "us_industry_fix.json"), encoding="utf-8"))
    for _s, _x in _fix.get("card", {}).items():
        SYM_BIZ.setdefault(_s, tuple(_x["group"]) if isinstance(_x["group"], list) else _x["group"])
except (OSError, ValueError, KeyError):
    pass
QUARTERLY = {"QREV519TUSY", "REV518TMSA", "REV5112TAXABL144QSA", "B985RC1Q027SBEA", "REV523TAXABL144QNSA", "REV622ALLEST144QSA", "QREV5415TUSY", "QREV517312TUSY",
             "DRCCLACBS"}   # 분기 자료 — 1년 전 = 4칸 전


def _key():
    k = os.environ.get("FRED_API_KEY")
    root = os.path.join(BASE, "..", "..", ".env")
    if not k and os.path.exists(root):
        for line in open(root, encoding="utf-8"):
            if line.startswith("FRED_API_KEY="):
                k = line.split("=", 1)[1].strip().strip("\"'")
    return k


def _ids():
    out = set()
    for _n, works, money in BIZ.values():
        out |= {w[1] for w in works}
        if money:
            out.add(money[0])
    for rows in list(RELATED.values()) + list(RELATED_SYM.values()):
        out |= {r[0] for r in rows}
    return sorted(out)


def fmt(sid, v):
    """UNITS 에 있는 번호의 값 글 — 없으면 None(옛 규칙으로)."""
    u = UNITS.get(sid)
    return f"{v / u[0]:,.{u[2]}f}{u[1]}" if u else None


def related(sym, data):
    """함께 볼 지표 줄 — [{fred, name, why, month, v, chg, pct, quarterly}]. 업계 카드에 이미 있는 번호는 뺀다."""
    keys = SYM_BIZ.get(sym)
    keys = () if not keys else (keys,) if isinstance(keys, str) else keys
    rows = RELATED_SYM.get(sym) or [r for k in keys for r in RELATED.get(k) or []]
    own = {w[1] for k in keys for w in BIZ[k][1]}
    out, seen = [], set()
    for sid, name, why in rows:
        if sid in own or sid in seen:
            continue
        seen.add(sid)
        ser = _series(sid, data)
        q = sid in QUARTERLY
        last, chg = _yoy(ser, 4 if q else 12)
        if not last:
            continue
        if sid in PCT:
            chg = last["v"] - ser[-1 - (4 if q else 12)]["v"]
        out.append({"fred": sid, "name": name, "why": why, "month": last["month"], "v": last["v"], "chg": chg, "pct": sid in PCT, "quarterly": q, "next": next_release(sid, data)})
    return out[:3]


def fetch():
    """FRED 최근 4년 — 하루 한 번(캐시가 오늘이면 그대로). 실패한 지표는 지난 캐시 값을 둔다. 키가 없으면 캐시만."""
    old = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    today = datetime.date.today().isoformat()
    if old.get("fetched") == today and "_dates" in old:
        return old
    key = _key()
    if not key:
        print("[industry_us] FRED_API_KEY 없음 — 캐시만")
        return old
    start = f"{datetime.date.today().year - 4}-01-01"
    out = {"fetched": today}
    for sid in _ids():
        try:
            q = urllib.parse.urlencode({"series_id": sid, "api_key": key, "file_type": "json", "observation_start": start})
            obs = json.load(urllib.request.urlopen(f"https://api.stlouisfed.org/fred/series/observations?{q}", timeout=60))["observations"]
            out[sid] = [(o["date"][:7], float(o["value"])) for o in obs if o["value"] not in (".", "")]
        except Exception as e:  # noqa: BLE001 — 지표 하나 실패로 페이지를 막지 않는다
            print(f"[industry_us] {sid} 실패: {str(e)[:80]}")
            if old.get(sid):
                out[sid] = old[sid]
        time.sleep(0.25)   # 94번 연달아 — FRED 1분 120번 한도에 다른 실행과 겹쳐 걸리지 않게 (2026-11-25)
    _releases(out, old, key, today)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(out, open(CACHE, "w", encoding="utf-8"))
    return out


def _releases(out, old, key, today):
    """다음 발표일 재료 — FRED 발표 일정. `_release` = 번호 → 발표 묶음(한 번 알아 두면 다시 안 부른다),
    `_dates` = 발표 묶음 → 오늘부터의 발표일 셋(날마다). 매일 · 매주 나오는 자료(PARTIAL)는 뺀다. 실패하면 지난 값."""
    def get(path, **q):
        u = f"https://api.stlouisfed.org/fred/{path}?" + urllib.parse.urlencode({**q, "api_key": key, "file_type": "json"})
        return json.load(urllib.request.urlopen(u, timeout=60))

    rel = dict(old.get("_release") or {})
    for sid in _ids():
        if sid in PARTIAL or sid in rel:
            continue
        try:
            rel[sid] = get("series/release", series_id=sid)["releases"][0]["id"]
        except Exception as e:  # noqa: BLE001
            print(f"[industry_us] 발표 묶음 {sid} 실패: {str(e)[:80]}")
        time.sleep(0.25)
    dates = {}
    for rid in sorted({str(r) for s_, r in rel.items() if s_ not in PARTIAL}):
        try:
            got = get("release/dates", release_id=rid, realtime_start=today, realtime_end="9999-12-31", include_release_dates_with_no_data="true", sort_order="asc", limit=3)
            dates[rid] = [x["date"] for x in got.get("release_dates") or []]
        except Exception as e:  # noqa: BLE001
            print(f"[industry_us] 발표일 {rid} 실패: {str(e)[:80]}")
            if (old.get("_dates") or {}).get(rid):
                dates[rid] = old["_dates"][rid]
        time.sleep(0.25)
    out["_release"], out["_dates"] = rel, dates


def next_release(sid, data):
    """번호의 다음 발표일(YYYY-MM-DD) — 오늘(한국 날짜) 이후 첫 날. 없으면 None. 미국 아침 발표는 한국 날짜로 같은 날 밤이다."""
    rid = (data.get("_release") or {}).get(sid)
    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")
    return next((d for d in (data.get("_dates") or {}).get(str(rid)) or [] if d >= today), None) if rid and sid not in PARTIAL else None


def load():
    return json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}


def _monthly(rows):
    """[(YYYY-MM, 값)] — 주간(은행 대출)은 달 평균. 분기 자료는 그대로(분기 첫 달 표기)."""
    by = {}
    for m, v in rows:
        by.setdefault(m, []).append(v)
    return [{"month": m, "v": sum(v) / len(v)} for m, v in sorted(by.items())]


def _series(sid, data):
    """달별 줄 — 주간 · 일별 자료는 달 평균, 덜 찬 이번 달은 뺀다."""
    ser = _monthly(data.get(sid) or [])
    if sid in PARTIAL and ser and ser[-1]["month"] == datetime.date.today().strftime("%Y-%m"):
        ser = ser[:-1]
    return ser


def _yoy(series, step):
    """마지막 값과 1년 전(월 자료 12칸 · 분기 4칸) 대비 % — (마지막 행, 변화 %)."""
    if len(series) <= step:
        return None, None
    last, prev = series[-1], series[-1 - step]
    return last, ((last["v"] / prev["v"] - 1) * 100 if prev["v"] else None)


def build(sym, data):
    """종목 → 업계 카드 재료 {biz, works: [...], money}. 업계가 둘인 회사(구글 · 마이크로소프트 · 오라클)는 works 마다 biz. 자료 없으면 None."""
    keys = SYM_BIZ.get(sym)
    if not data:
        return None
    rel = related(sym, data)
    if not keys:
        return {"biz": "", "works": [], "money": None, "related": rel} if rel else None   # 업계 카드는 없고 함께 볼 지표만 있는 종목
    keys = (keys,) if isinstance(keys, str) else keys
    out = {"biz": BIZ[keys[0]][0], "works": [], "money": None, "related": rel}
    works = [(BIZ[k][0], *w) for k in keys for w in BIZ[k][1]]
    money = BIZ[keys[0]][2]
    for biz, q, sid, label, mode, src, vkey in works:
        ser = _series(sid, data)   # 주간 · 일별 자료는 덜 찬 이번 달을 뺀다
        quarterly = sid in QUARTERLY
        last, chg = _yoy(ser, 4 if quarterly else 12)
        if not last:
            continue
        up, dn = ("늘고 있음", "줄고 있음") if mode == "qty" else ("오르는 중", "내리는 중")
        state = "판단 유보" if chg is None else up if chg >= LIM_WORK else dn if chg <= -LIM_WORK else "비슷함"
        out["works"].append({"biz": biz, "q": q, "fred": sid, "name": label, "mode": mode, "src": src, "vkey": vkey, "month": last["month"], "v": last["v"], "chg": chg,
                             "state": state, "series": ser[-9:] if quarterly else ser[-25:], "quarterly": quarterly, "next": next_release(sid, data)})
    if money:
        sid, label, vkey = money
        ser = _monthly(data.get(sid) or [])
        last, chg = _yoy(ser, 4)
        if last:
            state = "판단 유보" if chg is None else "나아짐" if chg >= LIM_MONEY else "나빠짐" if chg <= -LIM_MONEY else "비슷함"
            out["money"] = {"fred": sid, "name": label, "src": BEA, "vkey": vkey, "month": last["month"], "v": last["v"], "chg": chg, "state": state, "series": ser[-9:], "next": next_release(sid, data)}
    return out if out["works"] or out["money"] or rel else None
