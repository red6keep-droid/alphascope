"""신호 스터디 확정값 — 규칙 · 보유 방식 · 비용 · 검정 파라미터.

규칙 다섯 개는 reference2/doc/MRH_v1/MRH_Signal_Engine_Core_Specification_V1.md 6~10장의 값을 그대로 옮겼다
(2026-09-24 확정). 바꾸려면 이 파일만 고치고 다시 돌린다.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
OUTPUT_DIR = os.path.join(HERE, "output")

# ---------------------------------------------------------------- 데이터 범위
PRICE_START = "2015-06-01"      # 지표 계산 여유(20일선 · RVOL) 포함
STUDY_START = "2016-01-01"      # 이 날부터의 신호만 센다
SPLIT_DAY = "2023-01-01"        # 이전 = 탐색(train) · 이후 = 검증(test). 같은 데이터로 규칙을 다듬고 재지 않기 위해

BENCHMARK = "SPY"
VIX = "^VIX"

# GICS 섹터 → SPDR 섹터 ETF. XLC는 2018-06, XLRE는 2015-10 상장 — 그 전 날짜는 섹터 조건을 평가할 수 없어 신호에서 빠진다.
SECTOR_ETF = {
    "Information Technology": "XLK",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}

# ---------------------------------------------------------------- 규칙 (MRH Signal Engine 6~10장)
RULE = {
    "ret1_min": 0.05,        # 6.3  당일 상승률 +5% ~ +12%
    "ret1_max": 0.12,
    "rvol_min": 2.0,         # 7.2  RVOL > 2.0 (직전 20거래일 평균 거래량 대비)
    "rvol_lookback": 20,
    "close_pos_min": 0.75,   # 9    종가가 당일 고저 범위의 상위 25%
    "sector_ma": 20,         # 8    소속 섹터 ETF 종가 > 20일선
    "ret5_max": 0.20,        # 10.2 최근 5거래일 누적 +20% 미만 (과열 제외)
}

# 조건 하나씩 빼 보는 절제(ablation) 변형. 키 = 결과표 이름, 값 = 끄는 조건
ABLATIONS = {
    "규칙 전체": None,
    "− 상승률 구간": "ret1",
    "− RVOL": "rvol",
    "− 종가 강도": "close_pos",
    "− 섹터 20일선": "sector",
    "− 과열 제외": "overheat",
}

CLUSTER_GAP = 5              # 같은 종목이 5거래일 안에 다시 조건을 채우면 한 건으로 본다 (첫 날만)

# ---------------------------------------------------------------- 보유 방식
# 진입은 신호일 다음 거래일 시가 (Signal Engine 11장: 마감 후 신호 → 다음 날 매수)
HORIZONS = [3, 5, 7]         # 고정 보유: 신호일 + h 거래일 종가에 청산 (12.2 평균 보유 3~7일)
STOP = -0.07                 # 손절 · 목표 방식 — 사용자 확정 2026-09-24
TARGET = 0.10
MAX_HOLD = 7                 # 둘 다 안 닿으면 신호일 + 7 거래일 종가 청산 (12.3 최대 1.5주)

COST_ROUND_TRIP = 0.002      # 편도 슬리피지 0.1% × 2. 수수료 0 가정 (MRH 백테스트 명세 4장: 비용 없는 백테스트는 의미 없음)

# ---------------------------------------------------------------- 시장 국면 (Tech Master Spec 3.1)
REGIME_VIX_MAX = 20.0        # VIX < 20 이고
REGIME_SPY_MA = 20           # SPY 종가 > 20일선 이면 RISK ON

EARNINGS_WINDOW = 1          # 실적 발표일 ±1 거래일 안의 신호는 '실적 인접'으로 표시

# ---------------------------------------------------------------- 검정
PLACEBO_RESAMPLES = 1000     # 같은 종목의 비신호 날을 이벤트 수만큼 뽑아 평균 분포를 만든다
SEED = 20260924
MIN_N = 30                   # 이보다 표본이 적은 칸은 숫자를 신뢰하지 말라고 표시
