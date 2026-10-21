"""테마 모니터 설정 — 질문 하나 · 묶음 · 임계값 · 상태 말 (doc/테마-모니터-기획.md 2절, 2026-10-21 사용자: A · B · D 로 진행, 상태 말은 테마마다 질문에 맞게).

테마는 여기에만 적는다. 코드(analyze · render)는 테마 수와 무관하게 같은 계산을 돈다.
slug 는 고정 페이지 영문 주소(`/p/<slug>.html`) — 한 번 만든 뒤 바꾸지 않는다.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stock-radar"))
import universe as U  # noqa: E402

BENCH = U.BENCH                 # S&P 500 (SPY)
FLOW_DAYS = 20                  # 자금 흐름 = 20거래일 상대 수익률 (레이더 sector_flow 와 같은 창)
FLOW_PP = 2.0                   # ±2%p 넘으면 유입 · 유출 (레이더와 같은 임계)
NORMAL_WINDOW = 252             # 평소 범위 = 지난 252일 하루 수익률 분포
HISTORY_MIN_N = 30              # 통계 말은 30건부터 (운영지침 5절)

THEMES = [
    {
        "key": "ai",
        "slug": "theme-ai-capex",
        "title": "AI 투자 자금 방향",          # 2026-10-21 사용자: "모니터" 단어 삭제
        "slug_title": "theme ai capex monitor",
        "question": "AI 투자, 아직 돈이 들어오나?",
        "why": "반도체 · 데이터 센터 · 전력 설비 세 갈래가 같이 가면 AI 테마 자체로 돈이 오는 것이고, 한 갈래만 가면 다른 이유(반도체 랠리 · 금리)일 수 있습니다.",
        # 갈래 (2026-10-21 사용자: 칩 → 반도체, 클라우드 → 데이터 센터). 데이터 센터 = 짓고 쓰는 회사(클라우드 사업자 · 데이터센터 리츠), 전력 설비 = 전기 · 냉각 · 네트워크
        "baskets": [
            ("반도체", ["NVDA", "AVGO", "TSM", "MU", "AMD"]),
            ("데이터 센터", ["MSFT", "ORCL", "CRWV", "GOOGL", "AMZN", "EQIX"]),
            ("전력 설비", ["CEG", "NEE", "VRT", "ANET"]),
        ],
        # 상태 말 — 질문에 답하는 말 (2026-10-21 사용자 결정 2)
        "states": {"all": "세 갈래 모두 유입", "two": "두 갈래 유입", "one": "{name}에만 유입", "none": "뚜렷하지 않음", "out": "유출"},
    },
    {
        "key": "fed",
        "slug": "theme-fed-rate-cut-expectations",
        "title": "연준 금리 인하 기대",
        "slug_title": "theme fed rate cut expectations",
        "question": "연준은 언제 내리나 — 시장은 지금 어떻게 보나?",
        "why": "2년물 금리는 시장이 보는 앞으로 2년의 기준금리 평균입니다. 기준금리보다 얼마나 낮은지가 '인하 기대'의 크기이고, 그 차이가 커지면 시장은 더 빨리 · 더 많이 내릴 것으로 보는 것입니다.",
        "fred": {"policy": "DFF", "y2": "DGS2", "y10": "DGS10", "curve": "T10Y2Y"},
        "cpi_release_id": 10,     # FRED release 10 = CPI
        "change_bp": 10,          # 20거래일 동안 인하 기대가 10bp 넘게 변하면 상태가 바뀐다
        "states": {"up": "인하 기대 커짐", "flat": "그대로", "down": "인하 기대 줄어듦"},
        "sensitive": [("장기채", "TLT"), ("리츠", "EQIX"), ("유틸리티", "NEE"), ("소형주", "IWM"), ("은행", "JPM"), ("빅테크", "QQQ")],   # 금리 민감 자산 (시세만, 페이지 없음)
    },
    {
        "key": "insider",
        "slug": "theme-insider-trading",
        "title": "임원 기관 매매 동향",
        "slug_title": "theme insider trading monitor",
        "question": "임원과 기관은 지금 사나, 파나?",
        "why": "임원의 장내 매수(Form 4 P 코드)는 자기 돈으로 사는 것이라 가장 믿을 만한 신호로 봅니다. 매도는 사전 매도 계획(10b5-1)이 많아 계획 외 매도만 따로 셉니다.",
        "days": 30,
        "states": {"buy": "임원 순매수", "flat": "중립", "sell": "임원 순매도"},
    },
]

BY_KEY = {t["key"]: t for t in THEMES}
BLOG = U.BLOG


def page_url(t):
    return f"{BLOG}/p/{t['slug']}.html"
