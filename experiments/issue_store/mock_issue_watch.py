"""이슈 모니터링 목업 (2026-11-13 사용자: "이슈 모니터링으로 별도 페이지 — 평소 계속 지켜보다가 주식이 선반영되는 낌새가 보이면 포착, 동향 파악").

    python experiments/issue_store/mock_issue_watch.py   → output/mock_issue_watch.html

예측판이 아니라 동향판 — 사실 세 가지만 매일 적는다:
  ① 얼마나 화제인가 = 이 이슈 기사 수 (공용 뉴스 처리 news_store_home.json + 종목 레이더 뉴스, signal_standby.load_news)
  ② 시장이 먼저 움직이나 = 사슬 사전(chains.CEASEFIRE) 고리 지표의 10거래일 움직임 · 평소의 몇 배(signal_scan 과 같은 셈)
  ③ 이렇게 되면 = 사슬 갈림점 + 사건표(events_curated.csv) 같은 종류 사례의 당일 · 20거래일 뒤 실제 움직임
검증 3-a(기획 8-19): 전쟁 · 지정학은 가격이 미리 움직이지 않았다(7~8건, 가설) → 화면은 "포착했다" 를 말하지 않는다.
이슈 = 키워드 묶음(ISSUES). signal_standby 의 주제 정규식은 이란 기사 대부분을 놓쳐서(11-10 `긴장 완화 기대` 등) 이슈는 이름으로 모으고, 기사마다 쪽(종전 · 확전 · 미정)을 붙인다.
쪽 · 단계는 목업에선 글 패턴 — 운영 땐 공용 뉴스 처리(Groq, 이미 도는 호출)의 칸으로 옮길지 정한다. AI 0 · 새 수집 0 · 블로그에 안 나감.
"""
import datetime as dt
import json
import os
import re
import sys

from collections import Counter

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))
import chains as CH  # noqa: E402
import design_kit as dk  # noqa: E402
import hypo_pages as H  # noqa: E402
import signal_standby as SB  # noqa: E402
import tech_signals as TS  # noqa: E402
import cards as qc  # noqa: E402  — 질문 카드(강조 카드 + 접기, 가이드라인 2-7) · hypo_pages 가 daily-report 를 경로에 넣는다

OUT = os.path.join(_HERE, "output")
KST = dt.timezone(dt.timedelta(hours=9))
RULES = "IW-2026-11-13a"
HEAD_TITLE = "Hot Issue"   # 머리 줄 제목 — 옛 `이슈 모니터링` (2026-11-13 사용자: 영어로 핫 이슈)
PUBLIC = False   # True = 블로그 게시용(issue_watch_daily.py): 목록 줄 = 블로그 주소 · 운영자 상자 없음 · 글 끝 `함께 보는 페이지`

# 지켜보는 이슈 — 키워드로 모은다. by = 자동(뉴스가 평소 2배) · 운영자(직접 추가)
ISSUES = [
    {"id": "IRAN", "name": "이란 전쟁", "q": "이란 전쟁, 끝나면 시장은?", "by": "운영자",
     "pat": r"이란|Iran|호르무즈|Hormuz|게심|Qeshm", "chain": "CEASEFIRE", "cases": ("휴전 · 종전",),
     "gq": "이란 전쟁 OR 이란 휴전 OR 이란 종전 OR 호르무즈", "since": "2026-11-13"},   # since = 게시 날짜 (제목 아래 오른쪽 `게시 : 11.13`)
    {"id": "TARIFF", "name": "관세", "q": "관세, 다시 오르나?", "by": "자동", "pat": r"관세(?!청)|tariff|무역 ?전쟁|trade war", "chain": "TARIFF", "gq": "트럼프 관세 OR 상호 관세 OR 관세 협상",
     "cases": ("관세 · 무역",), "since": "2026-11-13"},
    {"id": "EXPORT", "name": "반도체 수출 통제", "q": "반도체 수출 통제, 넓어지나?", "by": "자동",
     "pat": r"수출 ?통제|export control|chip (ban|export)|거래 제한 명단|entity list", "chain": "REGULATION", "gq": "반도체 수출 통제 OR 수출 통제 엔비디아",
     "cases": ("규제 (수출 · 반독점)",), "since": "2026-11-13"},
]
# 기사 쪽 — 위에서부터 먼저 맞는 것 (종전 쪽 · 확전 쪽 · 방향 미정)
SIDE_PAT = [
    ("멀어짐", r"필요 ?없|불필요|교착|희망 적|결렬|거부|황당"),   # 협상이 멀어지는 말은 확전 쪽보다 먼저
    ("종전", r"휴전|종전|평화|끝날|끝나|마무리|종식|긴장 완화|완화 기대|협상 진전|진전 시|합의|ceasefire|truce|peace|de-?escalat"),
    ("확전", r"공격|타격|공습|미사일|위협|확전|제재|일촉즉발|봉쇄|폭발|기뢰|피격|파괴|나포|격추|attack|strike|missile|escalat"),
]
SIDE_NAME = {"멀어짐": "확전", "종전": "종전", "확전": "확전"}
SIDE_KIND = {"종전": "positive", "확전": "negative", "방향 미정": "neutral"}   # 종전 = 시장에 좋은 쪽 빨강 · 확전 = 나쁜 쪽 파랑 — 증시 전망 `전망A · B` · 뉴스 긍정 · 부정과 같은 색 (2026-11-13 사용자)
def josa(w, pair):
    """받침에 맞춘 조사 — pair = ("은", "는") · ("이", "가")."""
    c = w.rstrip()[-1]
    has = "가" <= c <= "힣" and (ord(c) - 0xAC00) % 28 != 0
    return w + (pair[0] if has else pair[1])


def side_pill(side, pop=False):
    """쪽 라벨 — 종전쪽 빨강 · 확전쪽 파랑(뉴스 긍정 · 부정), 방향미정 = 증시 전망 `향방미정` 라벨과 같은 회색(바탕 #F8FAFC · 테두리 #E2E8F0, H.open_pill) (2026-11-13 사용자).
    pop = 팝업 줄 앞(flex 줄 안, H.news_pill)."""
    k = SIDE_KIND[side]
    if k == "neutral":
        bg, bd = dk.CARD_DIR["neutral"]
        if pop:
            return H.news_pill(SIDE_LABEL[side], (bg, bd, dk.PILL["neutral"][1]), inline=False)
        return H.open_pill().replace(f">{H.OPEN_TITLE}<", f">{SIDE_LABEL[side]}<", 1)
    if pop:
        return H.news_pill(SIDE_LABEL[side], (dk.PILL_BG.get(k, "#fff"), *dk.PILL[k]), inline=False)
    return dk.pill(SIDE_LABEL[side], k, bare=True)


SIDE_LABEL = {"종전": "종전", "확전": "확전", "방향 미정": "방향미정"}   # 안쪽 열쇠 `종전` = 시장에 좋은 쪽 · `확전` = 나쁜 쪽 — 화면 이름은 이슈마다 use() 가 바꾼다   # `쪽` 없이 — 증시 전망 `반등` · `지속` 과 같게 (2026-11-11 · 11-13 사용자)   # 라벨 글자는 띄어쓰기 없이 (가이드라인 8절, `논의중` · `시장예상` 과 같게)
TALK = re.compile(r"[“”\"'‘’]|선언|밝혀|말했|발언|검토|기대|희망|우려|위험|경고|가능|전망|분석|어떻게|맞설|논의|추진|모멘텀|긍정|이냐|할까|\?|관측|시사|의향|촉구|요구|주장|which|could|would", re.I)   # 논의 · 추진 · 모멘텀 · `…이냐` 추가 (2026-11-13: 단계 사다리가 말을 일어난 일로 올렸다)

# 가격 — 사슬 고리 지표(yfinance) + 비교
LINK_SYM = {"CL_F": "CL=F", "_VIX": "^VIX", "XLK": "XLK", "EWY": "^KS11", "ITA": "ITA", "GC_F": "GC=F", "XLE": "XLE", "JETS": "JETS",
            "XLY": "XLY", "_SOX": "^SOX", "_TNX": "^TNX", "DX-Y.NYB": "DX-Y.NYB", "SMH": "SMH", "NVDA": "NVDA", "091160.KS": "091160.KS"}
LINK_NAME = {"CL_F": "유가 (WTI)", "_VIX": "변동성 지수 (VIX)", "XLK": "미국 기술 업종", "EWY": "코스피", "ITA": "미국 방산 업종",
             "GC_F": "금", "XLE": "미국 에너지 업종", "JETS": "미국 항공 업종",
             "XLY": "미국 경기소비재 업종", "_SOX": "미국 반도체 지수 (SOX)", "_TNX": "미국 10년 국채 금리", "DX-Y.NYB": "달러 지수",
             "SMH": "미국 반도체 ETF (SMH)", "NVDA": "엔비디아", "091160.KS": "KODEX 반도체"}
KR_KEYS = {"EWY", "091160.KS"}   # 한국 장 = 미국보다 하루 먼저 닫는다 — 마지막 날 맞출 때 뺀다
EXTRA_LINKS = [("에너지 업종 약세", "XLE", -1), ("항공 강세 (연료비 ↓)", "JETS", +1)]   # 공급 복귀 사슬(OIL_SUPPLY_RETURN)에서   # 공급 복귀 사슬에서 — 그림자 스캔 11-09 · 11-10 에 움직인 둘
CASE_COLS = [("유가", "CL=F"), ("S&P 500", "^GSPC"), ("한국 (EWY)", "EWY"), ("에너지", "XLE"), ("방산", "ITA")]
Z_CLEAR, Z_SOME, BASE = 2.0, 1.0, 60
WIN = 5   # 독자 카드의 시장 기간 = 5거래일 = 뉴스 바늘 `최근 일주일` (2026-11-14 사용자: 기간을 하나로)
# 지표 묶음 — 한 줄로 세면 서로 다른 이유(11-05 반도체 급락)로 움직인 주식이 유가 쪽 신호를 가린다 (2026-11-13 실측: 유가 쪽 3개 모두 종전 방향, 주식 쪽 3개 반대)
GROUPS = [("유가", ("CL_F", "XLE", "JETS")), ("주식", ("XLK", "EWY", "ITA")), ("안전 자산", ("_VIX", "GC_F"))]   # `쪽` 없이 (2026-11-13 사용자)


# 이슈마다 다른 것 (2026-11-13 사용자: 관세 · 반도체 수출 통제도 이란 전쟁처럼 모니터링)
#   good / bad = 기사 방향 이름(좋은 쪽 빨강 · 나쁜 쪽 파랑), watch = 시장 지표가 재는 쪽(사슬 사전 고리의 부호가 그 사건 기준), q 의 질문과 같은 쪽
CFG = {
    "IRAN": dict(slug="issue-iran", good="종전", bad="확전", watch="종전", file="mock_issue_watch.html",
                 side_pat=[("멀어짐", r"필요 ?없|불필요|교착|희망 적|결렬|거부|황당"),
                           ("종전", r"휴전|종전|평화|끝날|끝나|마무리|종식|긴장 완화|완화 기대|협상 진전|진전 시|합의|ceasefire|truce|peace|de-?escalat"),
                           ("확전", r"공격|타격|공습|미사일|위협|확전|제재|일촉즉발|봉쇄|폭발|기뢰|피격|파괴|나포|격추|attack|strike|missile|escalat")],
                 tip="종전 = 휴전 · 협상 진전 · 긴장 완화 소식\n확전 = 공격 · 위협 · 제재 · 협상이 멀어지는 말",
                 groups=[("유가", ("CL_F", "XLE", "JETS")), ("주식", ("XLK", "EWY", "ITA")), ("안전 자산", ("_VIX", "GC_F"))],
                 extra=[("에너지 업종 약세", "XLE", -1), ("항공 강세 (연료비 ↓)", "JETS", +1)], skip=(),
                 case_cols=[("유가", "CL=F"), ("S&P 500", "^GSPC"), ("한국 (EWY)", "EWY"), ("에너지", "XLE"), ("방산", "ITA")],
                 case_exp={"유가": -1, "S&P 500": +1, "한국 (EWY)": +1, "에너지": -1, "방산": -1}, case_re=None,
                 case_name="휴전 · 종전",
                 case_note="3번뿐이라 ‘보통 이렇다’고 말할 수는 없습니다. 03.31 과 04.08 은 20거래일이 겹칩니다. 04.08 휴전 뒤 전쟁은 다시 이어졌습니다(10월 해협 공격 · 11.07 타격).",
                 bridge="가격이 크게 움직이거나(에너지 업종이 S&P 500 보다 하루에 평소의 3배 · 2.5%p 넘게) 휴전 서명 · 협상 시한처럼 날짜가 잡히면 증시 전망으로 넘어갑니다.",
                 bridge_sym="XLE", chart=None,
                 stages={"종전": [("발언", r"끝날|끝나|종전|평화|휴전"), ("협상 제안", r"협상 제안|대화 제안|중재|협상.{0,6}(요구|의향|제의)"),
                                  ("날짜 잡힘", r"일정|회담.{0,8}(열린|예정|개최)|협상.{0,4}재개"), ("회담", r"회담|대면 협상|직접 협상|담판|협상단.{0,8}만나"),
                                  ("합의 · 서명", r"합의(했|문)|서명했|서명식|타결|휴전 발효|휴전 성립"), ("이행", r"철수(했|완료|시작)|재개방(했|됐|돼)|포로 교환|봉쇄 해제(했|됐)")],
                         "확전": [("위협", r"위협|경고|불필요|최후통첩|일촉즉발"), ("제재 · 봉쇄", r"제재|봉쇄|나포"),
                                  ("공격", r"공격|타격|공습|미사일|폭발|격추|피격|기뢰|드론"), ("보복 · 확대", r"보복 (공격|공습|타격)|지상군 투입|전면전|확전(했|됐|돼)")]}),
    "TARIFF": dict(slug="issue-tariff", good="완화", bad="강화", watch="강화", file="mock_issue_watch-tariff.html",
                   side_pat=[("멀어짐", r"결렬|교착|무산|거부"),
                             ("종전", r"유예|연기|인하|철회|면제|예외|합의|타결|협상 진전|완화|낮춰|철폐|pause|delay|exempt|deal|truce"),
                             ("확전", r"부과|인상|발효|보복|위협|확대|강화|폭탄|올려|추가 관세|impose|hike|retaliat|threat|escalat")],
                   tip="완화 = 유예 · 인하 · 면제 · 합의 소식\n강화 = 부과 · 인상 · 보복 · 위협 · 협상 결렬",
                   groups=[("주식", ("XLY", "EWY", "_SOX")), ("금리 · 달러", ("_TNX", "DX-Y.NYB"))],
                   extra=[], skip=("_GSPC",),
                   case_cols=[("S&P 500", "^GSPC"), ("한국 (EWY)", "EWY"), ("반도체", "^SOX"), ("경기소비재", "XLY"), ("달러", "DX-Y.NYB")],
                   case_exp=None, case_re=None, case_name="관세 · 무역",
                   case_note="강화 소식과 유예 · 완화 소식(2025.04.09)이 섞여 있습니다. 기록은 눈금일 뿐 이번이 그대로 되풀이된다는 뜻은 아닙니다.",
                   bridge="가격이 크게 움직이거나(S&P 500 이 하루에 평소의 3배 넘게) 관세 발효 · 협상 시한처럼 날짜가 잡히면 증시 전망으로 넘어갑니다.",
                   bridge_sym="XLY", chart=("^GSPC", "S&P 500"),
                   stages={"종전": [("발언", r"유예|인하|완화|면제|협상"), ("협상", r"협상|회담|담판"), ("유예 · 인하", r"유예|연기|인하|면제|철회"), ("합의 · 서명", r"합의|타결|서명")],
                           "확전": [("위협 · 예고", r"위협|경고|예고|시사|검토"), ("발표", r"발표|행정명령|부과 방침|서명"), ("발효", r"발효|시행|부과"), ("보복 · 확대", r"보복|맞불|확대|추가 관세")]}),
    "EXPORT": dict(slug="issue-export", good="완화", bad="강화", watch="강화", file="mock_issue_watch-export.html",
                   side_pat=[("종전", r"허가|승인|완화|면제|해제|재개|허용|풀어|풀린|license|approv|lift"),
                             ("확전", r"통제 강화|제한|금지|규제|명단|추가|확대|차단|단속|막아|ban|restrict|curb|blacklist|entity list|tighten")],
                   tip="완화 = 수출 허가 · 승인 · 면제 소식\n강화 = 제한 · 금지 · 거래 제한 명단 추가 · 단속",
                   groups=[("미국 반도체", ("_SOX", "SMH", "NVDA")), ("한국 반도체", ("091160.KS",))],
                   extra=[("엔비디아 약세 (중국 매출)", "NVDA", -1)], skip=(),
                   case_cols=[("반도체 (SOX)", "^SOX"), ("엔비디아", "NVDA"), ("한국 (EWY)", "EWY"), ("S&P 500", "^GSPC")],
                   case_exp={"반도체 (SOX)": -1, "엔비디아": -1}, case_re=r"수출|BIS|H20|규제 강화", case_name="반도체 수출 규제",
                   case_note="기록은 눈금일 뿐 이번이 그대로 되풀이된다는 뜻은 아닙니다.",
                   bridge="가격이 크게 움직이거나(반도체 지수가 S&P 500 보다 하루에 평소의 3배 · 2.5%p 넘게) 규제 발효일처럼 날짜가 잡히면 증시 전망으로 넘어갑니다.",
                   bridge_sym="_SOX", chart=("^SOX", "미국 반도체 지수 (SOX)"),
                   stages={"종전": [("발언", r"완화|허가|승인"), ("허가 · 승인", r"허가|승인|허용|면제"), ("규제 해제", r"해제|철회|폐지")],
                           "확전": [("검토 · 보도", r"검토|추진|보도|위협"), ("발표", r"발표|명단|거래 제한|규정"), ("시행", r"시행|발효|금지|차단"), ("확대", r"확대|추가 제한|동맹국|강화")]}),
}
# 뉴스 타임라인 기준 가격 (2026-11-14 사용자: 증시 전망처럼 날마다 기준이 되는 가격) — 이슈가 가장 먼저 움직이는 값 하나.
#   이란 = 브렌트유(호르무즈 · 공급, 이 페이지 그래프도 브렌트), 관세 = S&P 500(관세 그래프와 같음), 수출 통제 = 미국 반도체 지수
TL_REF = {"IRAN": ("브렌트유", "BZ=F", "{:,.1f}달러"), "TARIFF": ("S&P 500", "^GSPC", "{:,.0f}"), "EXPORT": ("반도체 지수", "^SOX", "{:,.0f}")}
C = {}   # 지금 그리는 이슈 설정 (use() 가 채운다)

# `종전되면 · 확전되면 주가는?` — 쪽마다 흔한 설명(사슬 갈림) + 사건표 사례 (2026-11-14 사용자: 독자가 궁금한 건 확전 때 · 종전 때 주가)
#   chain = 흔한 설명을 가져올 사슬(None = 없음) · kinds = 사건표 분류 · inc / exc = 제목 낱말 · note = 표 아래 안내
IF_SIDES = {
    "IRAN": {"종전": dict(chain="CEASEFIRE", kinds=("휴전 · 종전",), inc=None, exc=None,
                         note="3번뿐이라 ‘보통 이렇다’고 말할 수는 없습니다. 03.31 과 04.08 은 20거래일이 겹칩니다. 04.08 휴전 뒤 전쟁은 다시 이어졌습니다(10월 해협 공격 · 11.07 타격)."),
             "확전": dict(chain="WAR", kinds=("전쟁 · 테러",), inc=r"이란|이라크|이스라엘|사우디|리비아|하마스", exc=None,
                         note="중동에서 전쟁이 시작되거나 커진 날입니다. 사건마다 규모가 달라 ‘보통 이렇다’고 말할 수는 없습니다.")},
    "TARIFF": {"종전": dict(chain=None, kinds=("관세 · 무역",), inc=r"유예|합의|휴전|타결", exc=None,
                           note="완화 사례는 1번뿐입니다. 기록은 눈금일 뿐 이번이 그대로 되풀이된다는 뜻은 아닙니다."),
               "확전": dict(chain="TARIFF", kinds=("관세 · 무역",), inc=None, exc=r"유예|합의|휴전|타결",
                           note="기록은 눈금일 뿐 이번이 그대로 되풀이된다는 뜻은 아닙니다.")},
    "EXPORT": {"종전": dict(chain=None, kinds=(), inc=None, exc=None, note=""),
               "확전": dict(chain="REGULATION", kinds=("규제 (수출 · 반독점)",), inc=r"수출|BIS|H20|규제 강화", exc=None,
                           note="기록은 눈금일 뿐 이번이 그대로 되풀이된다는 뜻은 아닙니다.")},
}
# `종전되면 · 확전되면 수혜주는?` — 시장에서 흔히 꼽는 종목 (2026-11-14 사용자: "확전되면 수혜주, 종전되면 수혜주를 예를 들어").
#   종목 고르기 = Claude 설계(흔한 설명 · 교과서 · 언론), 알파스코프의 추천이 아니다(법 기준: 매수 추천 금지). (이름, 야후 기호, 흔히 드는 이유)
#   2026-11-14 둘째 (사용자: "테마를 먼저, 그 테마의 주도주를 하나씩 · 유가가 움직이면 따라 나오는 수혜주는 왜 빠졌나 · 한국 · 미국이 섞였나"):
#   테마 = (이름, 경로, 흔한 이유, 미국 후보, 한국 후보). 경로 = 이 테마가 좋아지는 길 — "유가 하락" · "유가 상승" 은 이번 주 유가 움직임과 맞대어 본다.
#   주도주 = 후보 중 시가총액 1위(나라마다 하나, 자동 — 사람이 고르지 않는다). 테마 값 = 후보 전체 시장 대비 평균(미국 = S&P 500 · 한국 = 코스피 대비).
#   후보 = Claude 설계(흔한 설명 · 언론), 알파스코프의 추천이 아니다(법 기준: 매수 추천 금지).
OIL_PATH = {"유가 하락": -1, "유가 상승": +1}
THEME_ICON = {"항공": "t_air", "여행 · 크루즈": "t_travel", "화학": "t_chem", "중동 재건 · 건설": "t_build", "방산": "t_defense", "석유 생산": "t_oil",
              "정유": "t_refine", "해운": "t_ship", "자동차": "t_car", "전자 · 스마트폰": "t_phone", "소매 · 의류": "t_shop", "철강": "t_steel",
              "태양광 · 미국 공장": "t_solar", "AI 반도체": "t_chip", "반도체 장비": "t_tool"}   # 테마 이름 앞 기본형 회색 원 (design_kit.ICON_GLYPHS t_*, 2026-11-14 사용자 — 수혜주는 계속 쓰니 아이콘을 만들어 둔다)
THEME_SEP_EXTRA = 15   # 테마 사이 구분선 아래(다음 테마 이름 위) +15 (2026-11-14 사용자: "화학 위 구분선 여백 15픽셀 더")
STAGE_Q = {"IRAN": "전쟁 진행 상황", "TARIFF": "관세 진행 상황", "EXPORT": "수출 통제 진행 상황"}   # 옛 `실제로 어디까지 갔나?` (2026-11-14 사용자: "전쟁 진행 상황 이렇게 줄여줘")
BENEFIT = {
    "IRAN": {"종전": [("항공", "유가 하락", "연료비 부담 줄어듦 · 중동 노선 회복", [("델타항공", "DAL"), ("유나이티드항공", "UAL"), ("아메리칸항공", "AAL")],
                       [("대한항공", "003490.KS"), ("진에어", "272450.KS")]),
                      ("여행 · 크루즈", "유가 하락", "연료비 · 여행 수요 회복", [("로열캐리비안", "RCL"), ("카니발", "CCL")], [("하나투어", "039130.KS")]),
                      ("화학", "유가 하락", "원료(나프타) 값 내림", [("다우", "DOW"), ("라이온델바젤", "LYB")], [("LG화학", "051910.KS"), ("롯데케미칼", "011170.KS")]),
                      ("중동 재건 · 건설", "재건 공사", "전쟁 뒤 재건 · 플랜트 발주", [("플루어", "FLR")], [("현대건설", "000720.KS"), ("삼성E&A", "028050.KS")])],
             "확전": [("방산", "무기 수요", "무기 · 탄약 수요 늘어남", [("록히드마틴", "LMT"), ("RTX", "RTX"), ("노스롭그루먼", "NOC")],
                       [("한화에어로스페이스", "012450.KS"), ("LIG넥스원", "079550.KS"), ("현대로템", "064350.KS")]),
                      ("석유 생산", "유가 상승", "파는 원유 값 오름", [("엑슨모빌", "XOM"), ("셰브런", "CVX"), ("코노코필립스", "COP")], []),
                      ("정유", "유가 상승", "재고 값 · 정제 마진 오름", [("발레로", "VLO"), ("매러선 페트롤리엄", "MPC")], [("SK이노베이션", "096770.KS"), ("에쓰오일", "010950.KS")]),
                      ("해운", "운임 상승", "해협을 돌아가는 항로로 운임 오름", [("프론트라인", "FRO")], [("HMM", "011200.KS"), ("팬오션", "028670.KS")])]},
    "TARIFF": {"종전": [("자동차", "관세 부담 줄어듦", "미국으로 들여오는 차 · 부품 관세 내림", [("GM", "GM"), ("포드", "F")], [("현대차", "005380.KS"), ("기아", "000270.KS")]),
                        ("전자 · 스마트폰", "관세 부담 줄어듦", "중국 · 아시아 생산품 관세 내림", [("애플", "AAPL")], [("LG전자", "066570.KS")]),
                        ("소매 · 의류", "관세 부담 줄어듦", "수입해 파는 물건 값 내림", [("월마트", "WMT"), ("나이키", "NKE"), ("타깃", "TGT")], [])],
               "확전": [("철강", "수입 경쟁 줄어듦", "수입 철강이 비싸짐", [("뉴코", "NUE"), ("스틸 다이내믹스", "STLD"), ("클리블랜드클리프스", "CLF")], []),
                        ("태양광 · 미국 공장", "수입 경쟁 줄어듦", "미국 안에서 만드는 회사가 유리", [("퍼스트솔라", "FSLR")], [("한화솔루션", "009830.KS")])]},
    "EXPORT": {"종전": [("AI 반도체", "중국 판매 재개", "중국에 팔 수 있는 칩이 늘어남", [("엔비디아", "NVDA"), ("AMD", "AMD")], [("SK하이닉스", "000660.KS")]),
                        ("반도체 장비", "중국 판매 재개", "중국 공장에 장비 공급", [("어플라이드머티리얼즈", "AMAT"), ("램리서치", "LRCX"), ("KLA", "KLAC")],
                         [("한미반도체", "042700.KS")])],
               "확전": []},   # 강화 때 흔히 꼽는 수혜 테마가 뚜렷하지 않다 — 피해 쪽만 주로 거론 → 빈 탭은 그렇게 말한다
}
# 테마 아래 회색 한 줄 = 왜 좋아지나 명사형 몇 마디 (2026-11-14 사용자: 경로 · 숫자 없이, 문장 말고 `연료비 감소` 처럼)
THEME_WHY = {"항공": "연료비 감소", "여행 · 크루즈": "연료비 감소 · 여행 수요 회복", "화학": "원료(나프타) 값 하락", "중동 재건 · 건설": "재건 공사 발주",
             "방산": "무기 · 탄약 주문 증가", "석유 생산": "원유 값 상승", "정유": "재고 값 · 정제 마진 상승", "해운": "우회 항로 · 운임 상승",
             "자동차": "차 · 부품 관세 인하", "전자 · 스마트폰": "아시아 생산품 관세 인하", "소매 · 의류": "수입품 값 하락",
             "철강": "수입 철강 경쟁 감소", "태양광 · 미국 공장": "미국 생산 회사 유리",
             "AI 반도체": "중국 칩 판매 재개", "반도체 장비": "중국 장비 판매 재개"}   # 명사형 짧게 (2026-11-14 사용자: 합니다체 문장 X)
BENEFIT_NONE = "강화 때 흔히 꼽는 수혜 테마는 뚜렷하지 않습니다. 주로 피해 쪽(AI 반도체 · 장비)이 거론됩니다."
FORK_WORDS = [("되돌림 — 전쟁 사슬로 돌아감", "되돌림 — 유가 오름 · 위험 회피로 돌아감"), ("유가 · 물가 경로로 금리 사슬로 넘어감", "유가 · 물가를 거쳐 금리 걱정으로 이어짐"),
              ("경기 사슬로", "경기 걱정으로 이어짐"), ("사슬로 넘어감", "다른 걱정으로 이어짐")]   # `사슬` = 내부 말


def use(iss):
    """이슈 설정을 모듈 값에 깐다 — 목업 한 번에 이슈 셋을 차례로 그린다."""
    global SIDE_PAT, GROUPS, EXTRA_LINKS, CASE_COLS, CASE_EXP, GAUGE_ZONES, WEEK_DESC, WEEK_PREV, POP_HEAD, HIST_COL
    C.clear()
    C.update(CFG[iss["id"]], iss=iss, name=iss["name"])
    g, b = C["good"], C["bad"]
    SIDE_LABEL.update({"종전": g, "확전": b})
    SIDE_PAT, GROUPS, EXTRA_LINKS, CASE_COLS, CASE_EXP = C["side_pat"], C["groups"], C["extra"], C["case_cols"], C["case_exp"] or {}
    GAUGE_ZONES = [(-1.0, -0.5, f"{b} 뚜렷", TS.ZONES[0][3]), (-0.5, -0.15, b, TS.ZONES[1][3]), (-0.15, 0.15, "방향미정", TS.ZONES[2][3]),
                   (0.15, 0.5, g, TS.ZONES[3][3]), (0.5, 1.0, f"{g} 뚜렷", TS.ZONES[4][3])]
    WEEK_DESC = {f"{g} 뚜렷": f"{g} 소식이 훨씬 많았습니다", g: f"{g} 소식이 조금 더 많았습니다", "방향미정": f"{g} · {b} 소식이 엇갈렸습니다",
                 b: f"{b} 소식이 조금 더 많았습니다", f"{b} 뚜렷": f"{b} 소식이 훨씬 많았습니다"}   # `기사` → `소식` = 사건 단위 (2026-11-13)
    WEEK_PREV = {f"{g} 뚜렷": f"{g} 소식이 훨씬 많았습니다", g: f"{g} 소식이 더 많았습니다", "방향미정": "엇갈렸습니다",
                 b: f"{b} 소식이 더 많았습니다", f"{b} 뚜렷": f"{b} 소식이 훨씬 많았습니다"}
    POP_HEAD = {"종전": (f"{g} 전망 정보", dk.UP), "확전": (f"{b} 전망 정보", dk.DOWN), "방향 미정": ("방향미정 정보", "#111")}
    good_c, good_l, bad_c, bad_l = TS.ZONES[4][3], TS.ZONES[3][3], TS.ZONES[0][3], TS.ZONES[1][3]
    w_good = C["watch"] == g
    HIST_COL = {"strong": good_c if w_good else bad_c, "some": good_l if w_good else bad_l, "rev": bad_c if w_good else good_c,
                "good": good_c, "bad": bad_c, "mixed": "#CBD5E1", "calm": "#F1F5F9"}


def W():
    return C["watch"]   # 시장 지표가 재는 쪽 이름 (이란 = 종전 · 관세 · 수출 통제 = 강화)


def R():
    return C["bad"] if C["watch"] == C["good"] else C["good"]   # 그 반대 쪽 이름


def news_rows(items, pat):
    rx = re.compile(pat, re.I)
    out = []
    for it in items:
        txt = " ".join(str(it.get(k) or "") for k in ("title", "title_ko", "fact", "fact_en"))
        t = SB._ts(it)
        if not t or not rx.search(txt):
            continue
        side = "방향 미정"
        for nm, p in SIDE_PAT:
            if re.search(p, txt, re.I):
                side = SIDE_NAME[nm]
                break
        out.append({"t": t, "title": it.get("title_ko") or it.get("title") or "", "fact": it.get("fact") or "", "url": it.get("url"),
                    "src": it.get("source") or "", "gn": bool(it.get("_gn")), "side": side, "stage": "논의 · 발언" if TALK.search(txt) else "일어난 일", "issue": it.get("issue")})
    return sorted(out, key=lambda r: r["t"], reverse=True)


GN_CACHE = os.path.join(OUT, "_gnews_cache.json")   # 운영 = issue_watch_daily 가 상태 저장소 records/issues/ 로 바꾼다   # 목업용 — 지난 날은 다시 안 받는다(운영은 이 페이지가 하루 두 번 받아 상태 브랜치에 쌓는다)
GN_CAP = 100   # 구글 뉴스 RSS 한 번 = 100건까지 — 닿은 날은 `100건 넘음` 으로 표시


def gnews(iss, days):
    """이슈 검색어로 구글 뉴스(한국어) — 하루씩 나눠 받는다(14일 한 번에 받으면 100건 상한에 앞날이 잘린다). 같은 주소 · 같은 제목은 하나만."""
    import requests, time, urllib.parse as U, xml.etree.ElementTree as ET, email.utils as eu
    cache = json.load(open(GN_CACHE, encoding="utf-8")) if os.path.exists(GN_CACHE) else {}
    old = (dt.date.fromisoformat(days[-1]) - dt.timedelta(days=60)).isoformat()
    cache = {k: v for k, v in cache.items() if k.split("|")[1] >= old}   # 60일 지난 날은 지운다 — 캐시가 끝없이 커지지 않게
    today = days[-1]
    out, capped = [], set()
    for d in days:
        key = f'{iss["id"]}|{d}'
        if key not in cache or d >= (dt.date.fromisoformat(today) - dt.timedelta(days=1)).isoformat():
            d1 = (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()
            url = f'https://news.google.com/rss/search?q={U.quote(iss["gq"] + f" after:{d} before:{d1}")}&hl=ko&gl=KR&ceid=KR:ko'
            try:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
                its = ET.fromstring(r.content).findall(".//item")
                cache[key] = [{"title": i.findtext("title") or "", "url": i.findtext("link"), "src": i.findtext("source") or "",
                               "t": eu.parsedate_to_datetime(i.findtext("pubDate")).isoformat()} for i in its]
            except Exception as e:  # noqa: BLE001
                print(f"[gnews] {key} 못 받음: {type(e).__name__}")
                continue
            time.sleep(0.7)
        if len(cache.get(key, [])) >= GN_CAP:
            capped.add(d)
        out.extend(cache.get(key, []))
    os.makedirs(os.path.dirname(GN_CACHE), exist_ok=True)
    json.dump(cache, open(GN_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    items = []
    for x in out:
        title = re.sub(r"\s+-\s+[^-]+$", "", x["title"])   # 끝 `- 언론사` 떼기
        items.append({"title_ko": title, "title": title, "url": x["url"], "source": x["src"], "published_at": x["t"], "_gn": True})
    return items, capped


def merge_rows(*lists):
    """같은 주소 · 같은 제목(공백 · 기호 빼고 앞 24자)은 하나만 — 공용 뉴스(번역 · 요약 있음)를 먼저."""
    seen, out = set(), []
    for rs in lists:
        for r in rs:
            k1, k2 = r.get("url"), re.sub(r"[\W_]+", "", r["title"])[:24]
            if k1 in seen or k2 in seen:
                continue
            seen.update({k1, k2})
            out.append(r)
    return sorted(out, key=lambda r: r["t"], reverse=True)


def news_level(rows, at, base_days=28):
    """`at` 시각 기준 48시간 기사 수 · 평소(직전 28일의 48시간 평균) · 뉴스 늘어남."""
    n48 = sum(at - dt.timedelta(hours=48) < r["t"] <= at for r in rows)
    old = [r for r in rows if at - dt.timedelta(days=base_days) < r["t"] <= at - dt.timedelta(hours=48)]
    first = min((r["t"] for r in rows), default=at)
    span = max(1.0, (at - dt.timedelta(hours=48) - max(first, at - dt.timedelta(days=base_days))).total_seconds() / 172800)
    base = len(old) / span if old else None
    return n48, base, n48 >= 3 and n48 >= 2 * max(base or 0, 0.5)


def history(px, chain_id, rows, n=10):
    """지난 n 거래일 상태 — 그날 종가까지의 가격 · 그날 밤(KST 23시)까지의 뉴스로 다시 셈 (목업 = 거슬러 셈, 운영 = 날마다 기록)."""
    end = last_day(px, chain_id)
    cal = px["^GSPC"].dropna()
    cal = cal[cal.index <= end].index[-n:]
    out = []
    for d in cal:
        links = link_rows(px, chain_id, end=d, n=WIN)   # 칸 하나 = 그날까지 5거래일 — 위 카드 답과 같은 기간 (2026-11-14)
        g = group_state(links)
        at = dt.datetime.combine((d + pd.Timedelta(days=1)).date(), dt.time(8, 0), tzinfo=KST)   # 뉴욕 종가 = 한국 다음 날 아침
        n48, base, hot = news_level(rows, at)
        st, _ = state_of(n48, base, g)
        r7 = [r for r in rows if at - dt.timedelta(days=GAUGE_DAYS) < r["t"] <= at]
        evs = events(r7)
        _ai_apply(evs)   # 판정 캐시만 — 여기서 AI 를 부르지 않는다
        side = _zone_word(ev_net(evs)) if r7 else "방향미정"   # 그날까지 7일 사건 방향 = 바늘과 같은 셈
        out.append({"day": d.strftime("%Y-%m-%d"), "state": st, "n48": n48, "hot": hot, "side": side,
                    "groups": {gname: w for gname, w, *_ in g}, "gside": {x["g"]: (x["side"], x["strong"]) for x in group_side(links)}})
    return out


def history_line(hist):
    """같은 상태가 이어진 날을 묶어 한 줄로 — `10.30 ~ 11.03 조용함 → 11.04 ~ 11.11 …`."""
    runs = []
    for h in hist:
        if runs and runs[-1][2] == h["state"]:
            runs[-1][1] = h["day"]
        else:
            runs.append([h["day"], h["day"], h["state"]])
    rows = []
    for a, b, st in runs:
        when = H.md(a) if a == b else f"{H.md(a)} ~ {H.md(b)}"
        kind = "uncertain" if "움직이는" in st or "늘고" in st else "area" if "조금" in st or "늘어남" in st else "neutral"
        rows.append((dk.esc(when), dk.esc(short(st)), "", None, True))
    return rows


SUM_URL = "https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages/news_summaries_home.json"   # 홈 주요 뉴스 팝업 요약 다섯 줄 (fetch_news.SUM_FILE)


def _iid(link):
    import hashlib
    return hashlib.sha1(link.encode()).hexdigest()[:12]   # fetch_news._iid 와 같은 셈


def pop_lines():
    """기사 id → 요약 줄 (홈 주요 뉴스 팝업과 같은 캐시 — 새 AI 호출 없음)."""
    import requests
    try:
        d = requests.get(SUM_URL, timeout=20).json()
    except Exception as e:  # noqa: BLE001
        print(f"[요약] 못 받음: {type(e).__name__}")
        return {}
    return {k: v.get("lines") or [] for k, v in d.items() if isinstance(v, dict)}


def daily_counts(rows, days):
    c = {d: {"종전": 0, "확전": 0, "방향 미정": 0} for d in days}
    for r in rows:
        d = r["t"].astimezone(KST).date().isoformat()
        if d in c:
            c[d][r["side"]] += 1
    return c


def counts_24h(rows, now, n=14):
    """지금 시각에서 24시간씩 끊어 센 기사 수 — 열쇠 = 그 24시간이 끝나는 날짜(KST), 옛 것 → 최근.
    옛 셈(달력 하루)은 마지막 점이 `오늘 0시 ~ 지금` 몇 분치라 늘 뚝 떨어졌다 (2026-11-14 사용자: 오늘 0시가 왜 거의 0인가)."""
    c = {}
    for i in range(n - 1, -1, -1):
        hi = now - dt.timedelta(hours=24 * i)
        lo = hi - dt.timedelta(hours=24)
        k = {"종전": 0, "확전": 0, "방향 미정": 0}
        for r in rows:
            if lo < r["t"] <= hi:
                k[r["side"]] += 1
        c[hi.astimezone(KST).date().isoformat()] = k
    return c


def prices():
    import yfinance as yf
    syms = sorted(set(LINK_SYM.values()) | {s for c in CFG.values() for _, s in c["case_cols"]} | {"BZ=F", "EWY", "^GSPC", "^KS11"}
                  | {s for b in BENEFIT.values() for ths in b.values() for th in ths for _, s in th[3] + th[4]})
    df = yf.download(syms, start="2002-10-01", progress=False, auto_adjust=True, threads=False)["Close"]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df


def z10(s, end=None, n=10):
    """signal_scan.scan 과 같은 셈 — n거래일 로그 누적 ÷ (직전 60거래일 하루 σ × √n). VIX 도 비율(pct). end = 모든 지표가 있는 마지막 날.
    n = 10(운영자 상자 · 옛 셈) · WIN 5(독자 카드 — 위 뉴스 바늘 `최근 일주일` 과 같은 기간, 2026-11-14 사용자: 카드끼리 기간이 달라 위아래가 안 맞아 보였다)."""
    s = s.dropna()
    s = s[s > 0]
    if end is not None:
        s = s[s.index <= end]
    ch = np.log(s).diff()
    sd = ch.rolling(BASE, min_periods=int(BASE * 0.8)).std().shift(1)
    z = ch.iloc[-n:].sum() / (sd.iloc[-n - 1] * np.sqrt(n))
    pct = (s.iloc[-1] / s.iloc[-n - 1] - 1) * 100
    return float(z), float(pct), s.index[-n - 1], s.index[-1]


def chain_links(chain_id):
    """사슬 고리 + 이슈 덧붙임, 같은 지표는 처음 것만 (반도체 규제 사슬엔 SOX 가 하락 · 반등 두 번 나온다), skip = 뺄 고리(관세 `유예 뉴스에 급반등`)."""
    out, seen = [], set()
    for nm, f, sg, *_ in CH.CHAINS[chain_id]["links"]:
        if f in seen or f in C.get("skip", ()):
            continue
        seen.add(f)
        out.append((nm, f, sg))
    return out + [x for x in EXTRA_LINKS if x[1] not in seen]


def last_day(px, chain_id):
    return min(px[LINK_SYM[f]].dropna().index[-1] for _, f, _ in chain_links(chain_id) if LINK_SYM.get(f) in px and f not in KR_KEYS)


def link_rows(px, chain_id, end=None, n=10):
    links = chain_links(chain_id)
    out = []
    if end is None:
        end = last_day(px, chain_id)   # 코스피는 미국보다 하루 먼저 닫는다 — 미국 마지막 날에 맞춘다   # ETF 가 선물보다 하루 늦게 들어오는 날(yfinance) — 같은 날에 맞춘다
    for nm, f, sg in links:
        sym = LINK_SYM.get(f)
        if not sym or sym not in px:
            continue
        z, pct, d0, d1 = z10(px[sym], end, n)
        sz = sg * z
        state = "뚜렷하게" if sz >= Z_CLEAR else "조금" if sz >= Z_SOME else "반대로" if sz <= -Z_SOME else "평소 범위"
        out.append({"key": f, "name": LINK_NAME[f], "why": nm, "sg": sg, "z": z, "pct": pct, "state": state, "d0": d0, "d1": d1, "extra": (nm, f, sg) in EXTRA_LINKS})
    return out


def cases(px, kinds, inc=None, exc=None):
    """inc · exc = 사건 제목에 들어가야 할 · 빠져야 할 낱말 (이 이슈와 같은 종류만 — 이란 확전 = 중동 사건)."""
    ev = pd.read_csv(os.path.join(_HERE, "events_curated.csv"))
    ev = ev[ev["subkind"].isin(kinds)]
    if inc:
        ev = ev[ev["title"].str.contains(inc, na=False)]
    if exc:
        ev = ev[~ev["title"].str.contains(exc, na=False)]
    out = []
    for _, e in ev.iterrows():
        cal = px["^GSPC"].dropna().index
        i = cal.searchsorted(pd.Timestamp(e["start"]))
        if i >= len(cal) or i < 1:
            continue
        row = {"day": cal[i].strftime("%Y-%m-%d"), "title": e["title"].split(" — ")[0], "src": e["note"].split(" http")[0] if isinstance(e["note"], str) else ""}
        for nm, s in CASE_COLS:
            x = px[s].reindex(cal)
            a, b = x.iloc[i - 1], x.iloc[i]
            c = x.iloc[i + 20] if i + 20 < len(cal) else np.nan
            row[nm] = (None if np.isnan(a) or np.isnan(b) else (b / a - 1) * 100, None if np.isnan(a) or np.isnan(c) else (c / a - 1) * 100)
        out.append(row)
    return out


CASE_EXP = {"유가": -1, "S&P 500": +1, "한국 (EWY)": +1, "에너지": -1, "방산": -1}   # 흔한 설명의 방향 (chains.CEASEFIRE + 공급 복귀)


def case_gap(rows, exp=None):
    """흔한 설명과 사례가 어긋난 지표 — 그날 움직임이 있는 사례 모두에서 반대였으면 한 줄 (위 표 `흔한 설명은 내림` 과 아래 표가 다르게 보이는 자리)."""
    out = []
    for nm, sg in (CASE_EXP if exp is None else exp).items():
        v = [r[nm][0] for r in rows if r.get(nm) and r[nm][0] is not None]
        if len(v) >= 2 and all(x * sg < 0 for x in v):
            out.append(f'{nm}은 흔한 설명({"내림" if sg < 0 else "오름"})과 달리 {len(v)}번 모두 그날 {"올랐습니다" if sg < 0 else "내렸습니다"}')
    return (" " + " · ".join(out) + ".") if out else ""


# ───────────── 화면
def arrow(v, d=1):
    """증감 = 부호 숫자 + 증감 색 + 굵게 — 공용 마무리 fix_colons 가 ▲ · ▼(그 자리 글자의 80%, dk.tri_span)로 바꾼다 (가이드라인 5절).
    dk.arrow 는 ▲ 를 글자 크기 그대로 써서 쓰지 않는다 (2026-11-13 사용자: 삼각형 디자인 규칙)."""
    if v is None:
        return f'<span style="color:{dk.SUB};">—</span>'
    if round(v, d) == 0:
        return f'<span style="font-weight:700;white-space:nowrap;">{0:.{d}f}%</span>'
    return f'<span style="color:{dk.UP if v > 0 else dk.DOWN};font-weight:700;white-space:nowrap;">{"+" if v > 0 else "−"}{abs(v):.{d}f}%</span>'


def arrow_tri(v, d=1, px=15):
    """▲ · ▼ 를 직접 — 넘겨 보기 칸(data-lscroll) 안은 공용 마무리 fix_colons 가 그래프 자리로 보고 건너뛴다."""
    if v is None:
        return f'<span style="color:{dk.SUB};">—</span>'
    if round(v, d) == 0:
        return f'<span style="font-weight:700;white-space:nowrap;">{0:.{d}f}%</span>'
    return f'<span style="color:{dk.UP if v > 0 else dk.DOWN};font-weight:700;white-space:nowrap;">{dk.tri_span(v > 0, px)}{abs(v):.{d}f}%</span>'


def group_state(links):
    """묶음마다: 종전 방향 1배 넘는 지표 수 · 2배 넘는 것 · 반대 1배 넘는 것 → 한 마디."""
    by = {r["key"]: r for r in links}
    out = []
    for g, keys in GROUPS:
        rs = [by[k] for k in keys if k in by]
        need = min(2, len(rs))   # 지표 하나뿐인 묶음(한국 반도체)은 하나로
        ok = sum(r["sg"] * r["z"] >= Z_SOME for r in rs)
        clear = sum(r["sg"] * r["z"] >= Z_CLEAR for r in rs)
        rev = sum(r["sg"] * r["z"] <= -Z_SOME for r in rs)
        word = (f"{W()} 방향으로 움직이는 중" if ok >= need and clear >= 1 else f"{W()} 방향으로 조금" if ok >= need else
                "반대로 움직이는 중" if rev >= need else "평소 범위")
        out.append((g, word, ok, len(rs), rs))
    return out


def group_side(links):
    """묶음마다 어느 쪽으로 움직였나 — 종전 쪽 · 확전 쪽 둘 다 센다 (2026-11-14 사용자: 시장 카드가 종전 쪽만 재서 위 뉴스 바늘 `확전` 과 말이 안 맞았다).
    묶음 안 2개 이상(지표 하나뿐이면 1개)이 한쪽으로 평소의 1배 넘게 → 그 쪽. strong = 그 쪽에 2배 넘는 지표가 있음."""
    by = {r["key"]: r for r in links}
    out = []
    for g, keys in GROUPS:
        rs = [by[k] for k in keys if k in by]
        need = min(2, len(rs))
        w = [r for r in rs if r["sg"] * r["z"] >= Z_SOME]
        b = [r for r in rs if r["sg"] * r["z"] <= -Z_SOME]
        side = W() if len(w) >= need and len(w) > len(b) else R() if len(b) >= need and len(b) > len(w) else "평소 범위"
        pick = w if side == W() else b if side == R() else []
        out.append({"g": g, "side": side, "k": len(pick), "n": len(rs), "rs": rs, "strong": any(abs(r["z"]) >= Z_CLEAR for r in pick)})
    return out


def market_side(gs):
    """묶음 판정을 하나로 — 움직인 묶음이 모두 같은 쪽이면 그 쪽, 서로 다르면 `엇갈림`, 없으면 `평소 범위`."""
    sides = {x["side"] for x in gs if x["side"] != "평소 범위"}
    return sides.pop() if len(sides) == 1 else "엇갈림" if sides else "평소 범위"


def news_side(word):
    """바늘 말(`확전 뚜렷` · `종전` · `방향미정`) → 쪽 이름 또는 None."""
    return C["good"] if word.startswith(C["good"]) else C["bad"] if word.startswith(C["bad"]) else None


def state_of(news48, base48, groups):
    hot = news48 >= 3 and (base48 is None or news48 >= 2 * max(base48, 0.5))
    moving = [g for g, w, *_ in groups if w == f"{W()} 방향으로 움직이는 중"]
    if moving and hot:   # `시장 함께` 는 주식 쪽이 반대로 갈 때도 같이 움직인다고 읽힌다 → 움직인 묶음 이름을 쓴다
        return (f"뉴스 늘고 {josa(moving[0], ('이', '가'))} {W()} 방향으로" if len(moving) == 1 else f"뉴스 늘고 시장이 {W()} 방향으로"), "uncertain"
    if moving:
        return (f"{josa(moving[0], ('이', '가'))} {W()} 방향으로" if len(moving) == 1 else f"시장이 {W()} 방향으로"), "uncertain"   # `먼저` 는 선반영 단언(검증 3-a) → 사실만
    some = [g for g, w, *_ in groups if w == f"{W()} 방향으로 조금"]   # 묶음 줄은 `조금` 인데 머리는 `조용함` 이면 어긋난다 (11-13: 하루 더 들어오자 유가 2.1배 → 1.8배로 머리만 `조용함` 이 됐다)
    if some:
        who = josa(some[0], ("이", "가")) if len(some) == 1 else "시장이"   # 위 `뉴스 늘고 유가가 종전 방향으로` 와 같은 꼴
        return ("뉴스 늘고 " if hot else "") + f"{who} {W()} 방향으로 조금", "area"
    if hot:
        return "뉴스 늘어남", "neutral"
    return "조용함", "neutral"


def short(st):
    """목록 · 지난 2주 칸의 짧은 말 (500px 에서 오른쪽 칸에 들어가게 — 긴 말은 `지금은` 카드 오른쪽에만). 방향은 이 페이지가 종전 쪽만 보므로 뺀다."""
    if st == "조용함" or st == "뉴스 늘어남":
        return st
    who = next((g for g, _ in GROUPS if st.startswith(g) or f"늘고 {g}" in st), "시장")
    return ("뉴스 · " if "뉴스" in st else "") + who + (" 조금 움직임" if "조금" in st and "뉴스" not in st else " 조금" if "조금" in st else " 움직임")


def head_card(st, kind, news48, base48, groups, sides48=None, asof=""):
    news = f'48시간 이란 기사 {news48}건' + (f' (종전 {sides48[0]} · 확전 {sides48[1]})' if sides48 and news48 else '') + (f' · 평소 {base48:.1f}건' if base48 is not None else '')

    def gline(w, ok, n, rs):   # 괄호 안 숫자는 그 말과 같은 쪽만 — `평소 범위 (0개 종전 방향)` 처럼 줄 표시와 어긋나지 않게
        rev = sum(r["sg"] * r["z"] <= -Z_SOME for r in rs)
        return w + (f' ({n}개 중 {rev}개 반대 방향)' if "반대" in w else f' ({n}개 중 {ok}개 종전 방향)' if "종전" in w else "")
    items = [("뉴스", news)] + [(g, gline(w, ok, n, rs)) for g, w, ok, n, rs in groups] + ([("기준", asof)] if asof else [])
    tipt = ("뉴스 = 이 이슈 기사 수가 평소의 2배 · 3건 넘으면 `뉴스 늘어남`.\n"
            "시장 = 종전이면 움직인다고 흔히 설명하는 지표를 묶음별로 — 묶음 안 2개 이상이 그 방향으로 평소보다 크게(하나는 2배 넘게) 움직이면 `움직이는 중`.\n"
            "예측이 아니라 지금까지 일어난 일입니다.")
    return dk.state_card(f'지금은{dk.tip(tipt)}', kind=kind, right_html=dk.esc(st), items=items)


def list_card(rows, cur_id):
    """지켜보는 이슈 = 이슈마다 페이지 하나, 줄 전체를 누르면 그 페이지(테마 줄 링크 data-row-link, 가이드라인 10-9) (2026-11-13 사용자: 관세 · 반도체 수출 통제도 모니터링).
    지금 보는 이슈 = 이름 굵게 · 링크 없음."""
    parts = []
    for i, r in enumerate(rows):
        on = r["state"] != "조용함"
        lab = f'<span style="font-weight:{dk.STATE_VAL_W};color:{qc.SOON if on else "#111"};word-break:keep-all;text-align:right;">{dk.esc(r["short"])}</span>'   # 라벨 대신 값 글자 — 띄어쓰기 든 긴 말은 라벨로 쓰지 않는다 (8절)
        here = r["id"] == cur_id
        row = dk.crow(f"<b>{dk.esc(r['name'])}</b>" if here else dk.esc(r["name"]), lab, dk.esc(f'48시간 기사 {r["n48"]}건'), first=i == 0, sub_below=True)
        if not here:
            href = H.page_url(CFG[r["id"]]["slug"]) if PUBLIC else CFG[r["id"]]["file"]
            row = row.replace("<span ", f'<span data-row-link="1" data-href="{href}" style="cursor:pointer;" ', 1).replace('style="cursor:pointer;" style="', 'style="cursor:pointer;', 1)
        parts.append(row)
    return f'<span style="{dk.MULTI}">{"".join(parts)}</span>'


NOW_LABEL = [""]


def news_chart(counts, now_label="", base_day=None):
    """now_label = 마지막 날이 오늘(진행 중)이면 그 눈금 글자 `오늘 23시` — 문장의 48시간 건수와 그래프가 같은 날까지 (2026-11-13 사용자: 오늘 확전 61건이 그래프에 없어 숫자가 안 맞아 보였다)."""
    days = list(counts)
    labels = [H.md(d) if i in (0, len(days) // 2, len(days) - 1) else "" for i, d in enumerate(days)]
    if now_label:
        labels[-1] = now_label
    series = [("기사", [sum(counts[d].values()) for d in days], dk.CHART_MAIN, "solid")]   # 하루 기사 수 한 줄 = 관심의 크기 — 종전 · 확전 두 선은 옮긴 기사 수라 방향으로 읽히면 안 된다 (2026-11-13 사용자)
    if base_day:
        series.append(("평소", [round(base_day, 1)] * len(days), dk.CHART_CMP, "dash"))   # 비교 대상 = 평소 하루 (직전 4주 48시간 평균 ÷ 2)   # 라벨과 같은 빨강 · 파랑 (2026-11-13 사용자)   # 방향 미정은 선에서 뺀다 — 회색 점선은 범례가 `비교 대상` 이 된다. 건수는 아래 한 줄에
    return dk.trend_card(f"날마다 {C['name']} 기사 (건)", labels, series, lambda v: f"{v:.0f}" if float(v).is_integer() else "", ends_only=True)   # 건수 축에 0.5 없음


def link_card(links, groups):
    rows = []
    for g, w, ok, n, rs in groups:
        rows.append((f'<b>{dk.esc(g)}</b>', dk.pill(w, "uncertain" if "움직이는 중" in w and "반대" not in w else "area", bare=True), "", None, True))
        rows.extend(_link_row(r) for r in rs)
    d0, d1 = links[0]["d0"], links[0]["d1"]
    return d0, d1, rows


def _link_row(r):
    exp = "내림" if r["sg"] < 0 else "오름"
    kind = {"뚜렷하게": "uncertain", "조금": "area", "반대로": "negative", "평소 범위": "neutral"}[r["state"]]
    name = dk.esc(r["name"])
    sub = f'흔한 설명은 {exp} · 평소의 {abs(r["z"]):.1f}배 {"같은" if r["sg"] * r["z"] > 0 else "반대"} 방향'
    return (name, arrow(r["pct"]) + " " + dk.pill(r["state"], kind), dk.esc(sub), None, True, True)


def link_sec(links, groups):
    d0, d1, rows = link_card(links, groups)
    tipt = (f"최근 10거래일({H.md(d0.strftime('%Y-%m-%d'))} 종가 → {H.md(d1.strftime('%Y-%m-%d'))} 종가) 움직임.\n"
            "평소의 몇 배 = 이 지표가 보통 10거래일에 움직이는 폭(직전 60거래일 기준)의 몇 배인지.\n"
            "· 뚜렷하게 = 예상 방향으로 2배 넘게\n· 조금 = 1~2배\n· 반대로 = 반대 방향 1배 넘게\n"
            "예상 방향은 시장에서 흔히 쓰는 설명(교과서 · 언론)이고, 우리 주장은 아닙니다.")
    return dk.section("시장이 먼저 움직이나?", dk.ccard(rows) + dk.muted(f"최근 10거래일 {H.md(d0.strftime('%Y-%m-%d'))} → {H.md(d1.strftime('%Y-%m-%d'))} 종가"),
                      aside=dk.tips_right([("읽는 법", tipt)]))


def year_chart(px, sym, name):
    """올해 선 그래프 + 한 줄 (관세 = S&P 500 · 수출 통제 = 반도체 지수) — 브렌트유 그래프 자리."""
    s = px[sym].dropna()
    s = s[s.index >= f"{dt.date.today().year}-01-02"]
    days = [d.strftime("%Y-%m-%d") for d in s.index]
    labels = [""] * len(days)
    labels[-1] = H.md(days[-1])
    gr = dk.trend_card(f"{name} (올해)", labels, [(name, [round(v, 1) for v in s], dk.CHART_MAIN, "solid")], lambda v: f"{v:,.0f}")
    a, b = float(s.iloc[0]), float(s.iloc[-1])
    hi, hd = float(s.max()), s.idxmax().strftime("%Y-%m-%d")
    pct = (b / a - 1) * 100
    line = f"올해 첫 거래일 {a:,.0f} → 지금({H.md(days[-1])}) {b:,.0f}, {'+' if pct >= 0 else '−'}{abs(pct):.0f}%. 올해 가장 높았던 날({H.md(hd)}) {hi:,.0f}."
    return gr, line


def oil_chart(px):
    s = px["BZ=F"].dropna()
    s = s[s.index >= "2026-01-02"]
    days = [d.strftime("%Y-%m-%d") for d in s.index]
    marks = {"2026-03-02": "개전", "2026-04-08": "휴전", days[-1]: H.md(days[-1])}
    labels = [marks.get(d, "") for d in days]
    for k, v in marks.items():   # 휴일이면 다음 거래일에
        if k not in days:
            j = next((i for i, d in enumerate(days) if d > k), None)
            if j is not None:
                labels[j] = v
    gr = dk.trend_card("브렌트유 (달러, 올해)", labels, [("브렌트유", [round(v, 1) for v in s], dk.CHART_MAIN, "solid")], lambda v: f"{v:.0f}", small_end=True)   # 점이 많아 날마다 동그라미 없이 끝 값만
    pk = s[s.index >= "2026-03-02"]
    peak, peak_d = float(pk.max()), pk.idxmax().strftime("%Y-%m-%d")
    now = float(s.iloc[-1])
    pre = float(s[s.index < "2026-02-28"].iloc[-1])
    rc = s.iloc[-30:]   # 최근 30거래일 고점 → 지금 을 먼저 (10월에 다시 3월 고점까지 올랐다 — `오른 폭의 절반을 내려놓았다` 는 한 방향으로 내린 것처럼 읽힌다)
    rh, rd = float(rc.max()), rc.idxmax().strftime("%Y-%m-%d")
    pre_d = H.md(s[s.index < '2026-02-28'].index[-1].strftime('%Y-%m-%d'))
    line = (f"최근 고점({H.md(rd)}) {rh:.0f}달러 → 지금({H.md(days[-1])}) {now:.0f}달러, {(now / rh - 1) * 100:.0f}%. ".replace("-", "−") if rh > now * 1.05 else f"지금({H.md(days[-1])}) {now:.0f}달러. ")
    line += f"전쟁 전({pre_d}) {pre:.0f}달러 · 올해 가장 높았던 날({H.md(peak_d)}) {peak:.0f}달러."
    return gr, line


CASE_NAME_W, CASE_WHEN_W, CASE_COL_W, CASE_ROW_H = 92, 62, 84, 32   # 왼쪽 고정 칸(지표 · 그날/20일 뒤) · 사례 칸 폭 · 줄 높이


def cases_card(rows):
    """과거 사례 표 — 사례(시간)를 가로로: 왼쪽 = 옛날 · 오른쪽 = 최근, 처음엔 오른쪽 끝(최근 사례), `‹ 넘겨 보기` 왼쪽 · 넘길 것이 남으면 왼쪽 그림자.
    그래프 넘겨 보기와 같은 꼴(dk._col_frame_right: direction rtl · data-lscroll · data-sh="l") (2026-11-13 사용자: 넘겨 보는 방향을 우리 그래프처럼 · 좌측 그림자).
    지표 이름 칸은 넘겨도 그대로(그래프의 세로축 숫자처럼 고정). 사례 이름은 표 아래 작은 줄."""
    if not rows:
        return ""
    rows = sorted(rows, key=lambda r: r["day"])
    cy = str(dt.date.today().year)
    when = lambda d: H.md(d) if d[:4] == cy else d.replace("-", ".")   # noqa: E731
    H_ = CASE_ROW_H
    cell = f"display:flex;align-items:center;height:{H_}px;box-sizing:border-box;white-space:nowrap;"
    # 왼쪽 고정 칸
    left = f'<span style="{cell}border-bottom:1px solid #E2E8F0;font-size:13px;color:{dk.SUB};">사례</span>'
    for i, (nm, _) in enumerate(CASE_COLS):
        for k, lab in enumerate(("그날", "20일 뒤")):
            bt = "border-top:1px solid #E2E8F0;" if i and k == 0 else ""
            left += (f'<span style="{cell}{bt}gap:6px;font-size:14px;">'
                     f'<span style="flex:none;width:{CASE_NAME_W - 6}px;overflow:hidden;text-overflow:ellipsis;color:#111;font-weight:{600 if k == 0 else 400};">{dk.esc(nm) if k == 0 else ""}</span>'
                     f'<span style="flex:none;color:{dk.SUB};font-size:13px;">{lab}</span></span>')
    # 넘기는 칸 — 사례마다 한 열
    cols = ""
    for r in rows:
        c = f'<span style="{cell}justify-content:flex-end;border-bottom:1px solid #E2E8F0;font-size:13px;font-weight:600;color:#111;">{when(r["day"])}</span>'
        for i, (nm, _) in enumerate(CASE_COLS):
            for k in (0, 1):
                bt = "border-top:1px solid #E2E8F0;" if i and k == 0 else ""
                c += f'<span style="{cell}{bt}justify-content:flex-end;font-size:15px;">{arrow_tri(r[nm][k]) if r.get(nm) else "—"}</span>'
        cols += f'<span style="display:block;flex:1 0 {CASE_COL_W}px;padding:0 8px 0 0;">{c}</span>'
    min_w = len(rows) * CASE_COL_W
    over = CASE_NAME_W + CASE_WHEN_W + min_w > dk.CHART_PHONE_W
    hint = (f'<span data-scroll-hint="1" data-lhint="1" style="display:block;text-align:left;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.FAINT};margin:0 0 4px;">‹ {dk.SCROLL_HINT}</span>' if over else "")
    shade = ('<span data-sh="l" aria-hidden="true" style="position:absolute;top:0;bottom:0;left:0;width:14px;pointer-events:none;transition:opacity .15s;'
             'background:radial-gradient(farthest-side at 0 50%,rgba(15,23,42,.18),rgba(15,23,42,0));opacity:1;"></span>') if over else ""
    scroll = (f'<span style="display:block;position:relative;flex:1 1 auto;min-width:0;">'
              f'<span data-lscroll="1" style="display:block;overflow-x:auto;direction:rtl;scrollbar-width:none;-webkit-overflow-scrolling:touch;">'
              f'<span style="display:flex;direction:ltr;min-width:{min_w}px;">{cols}</span></span>{shade}</span>')
    names = "".join(f'<span style="display:block;"><b style="font-weight:600;color:#333;">{when(r["day"])}</b> {dk.esc(r["title"])}</span>' for r in reversed(rows))   # 이름 줄 = 최근 먼저
    return (f'<div style="margin:0 0 8px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;padding:10px 12px 10px;">{hint}'
            f'<span style="display:flex;"><span style="display:block;flex:none;width:{CASE_NAME_W + CASE_WHEN_W}px;">{left}</span>{scroll}</span>'
            f'<span style="display:block;margin:10px 0 0;padding:8px 0 0;border-top:1px solid #E2E8F0;font-size:13px;line-height:19px;color:{dk.SUB};word-break:keep-all;">{names}</span></div>')


def forks_card(chain_id):
    ch = CH.CHAINS[chain_id]
    rows = [(dk.esc(a), dk.esc(b.replace("전쟁 사슬로 돌아감", "유가 오름 · 위험 회피로 돌아감")), "", 45) for a, b in ch["forks"]]   # `사슬` = 내부 말
    return dk.ccard(rows, left=45)


def bridge_card(px):
    """증시 전망으로 넘어가는 자리 — 에너지 업종 vs S&P 500 하루 움직임이 평소 3배 · 2.5%p (forecast_register 기준)."""
    e, s = px["XLE"].dropna(), px["^GSPC"].dropna()
    idx = e.index.intersection(s.index)
    rel = (e.reindex(idx).pct_change() - s.reindex(idx).pct_change()) * 100   # forecast_register 와 같은 단순 수익률 차
    sd = rel.rolling(60, min_periods=48).std().shift(1)
    z = (rel / sd).iloc[-10:]
    j = z.abs().idxmax()
    hit = abs(z[j]) >= 3 and abs(rel[j]) >= 2.5
    word = "더 빠져" if rel[j] < 0 else "더 올라"
    now = (f'{H.md(j.strftime("%Y-%m-%d"))}에 에너지 업종이 S&P 500 보다 {abs(rel[j]):.1f}%p {word}(평소의 {abs(z[j]):.1f}배) 이 기준을 넘었습니다. 전망을 자동으로 만들기 시작한 11.11 전이라 그날 전망은 없습니다.' if hit else
           f'최근 10거래일 가장 컸던 날은 {H.md(j.strftime("%Y-%m-%d"))} {abs(rel[j]):.1f}%p (평소의 {abs(z[j]):.1f}배).')
    rows = [("가격이 크게 움직이면", '에너지 업종이 S&P 500 보다 하루에 평소의 3배 · 2.5%p 넘게 움직이면 다음 날 ‘급락 뒤’ 증시 전망으로. ' + now),
            ("날짜가 잡히면", "휴전 서명 · 협상 시한처럼 날짜가 정해지면 → 사건 전 전망 (합의 · 결렬 두 갈래)")]
    return dk.state_card("증시 전망으로 넘어가는 때", items=rows)


# ───────────── 같은 사건 묶기 (AI 0) — 기사 수백 건을 그대로 늘어놓지 않고 사건 한 줄 + 보도 n곳 + 원문 링크 몇 개 (2026-11-13 사용자)
EV_SIM, EV_HOURS, EV_MIN_SRC, EV_LINKS = 0.3, 36, 3, 3   # 제목 글자 둘씩 겹침(자카드) · 같은 사건으로 보는 시간 폭 · 위 목록에 올리는 보도 곳 수 · 원문 링크 수


def _grams(t):
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", t)
    t = re.sub(r"[\W_]+", "", t)
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _clean_title(t):
    """사건 줄 = 대표 제목에서 `[속보]` · `(종합)` · 그림 문자 · 끝 `- 매체` 를 뗀 것."""
    t = re.sub(r"\[[^\]]*\]|\((?:종합|종합\d보|상보|영상)[^)]*\)", "", t)
    t = re.sub(r"\s+-\s+[^-]{1,20}$", "", t)
    t = re.sub(r"[\U0001F000-\U0001FAFF☀-➿️]", "", t)
    t = re.sub(r"\s*[:|]\s*(?:국제|정치|경제|세계|뉴스|사회|IT|증권|글로벌|월드)[^:|]{0,6}$", "", t)   # 끝 섹션 이름 `: 국제`
    return re.sub(r"\s+", " ", t).strip()


def cluster(rows):
    """최신 → 과거 순으로, 시간 폭 안 묶음의 앞 6건과 가장 많이 겹치는 묶음에 넣는다."""
    out = []
    for r in rows:
        g = r.setdefault("_g", _grams(r["title"]))
        best, bs = None, 0.0
        for cl in out:
            if abs((cl[0]["t"] - r["t"]).total_seconds()) > EV_HOURS * 3600:
                continue
            sim = max(len(g & m["_g"]) / max(1, len(g | m["_g"])) for m in cl[:6])
            if sim > bs:
                best, bs = cl, sim
        if best is not None and bs >= EV_SIM:
            best.append(r)
        else:
            out.append([r])
    return out


def _major(cl, key, skip):
    c = {}
    for m in cl:
        c[m[key]] = c.get(m[key], 0) + 1
    named = {k: v for k, v in c.items() if k != skip}
    return max(named, key=named.get) if named and max(named.values()) * 2 >= max(1, len(cl) - c.get(skip, 0)) else skip


def event_of(cl):
    """묶음 → 사건 한 줄. 대표 = 다른 기사들과 가장 많이 겹치는 제목(가운데 기사). 공용 뉴스(우리 말 사실 줄)가 들어 있으면 그것을 쓴다."""
    own = next((m for m in cl if not m["gn"] and m.get("fact")), None)
    rep = max(cl, key=lambda m: sum(len(m["_g"] & o["_g"]) / max(1, len(m["_g"] | o["_g"])) for o in cl))
    srcs, links = [], []
    for m in sorted(cl, key=lambda m: m["t"]):   # 먼저 보도한 곳부터
        if m["src"] and m["src"] not in srcs:
            srcs.append(m["src"])
            if len(links) < EV_LINKS and m.get("url"):
                links.append((m["src"], m["url"]))
    import hashlib
    first = min(cl, key=lambda m: m["t"])
    return {"key": hashlib.sha1(re.sub(r"[\W_]+", "", first["title"]).encode()).hexdigest()[:12],   # AI 판정 캐시 열쇠 — 첫 보도 제목 (묶음이 커져도 안 바뀜)
            "title": own["fact"] if own else _clean_title(rep["title"]), "n_src": len(srcs), "n": len(cl), "links": links,
            "first": min(m["t"] for m in cl), "last": max(m["t"] for m in cl),
            "side": _major(cl, "side", "방향 미정"), "talk": sum(m["stage"] != "일어난 일" for m in cl) * 2 >= len(cl), "own": own, "rep": rep}


def _src_links(links):
    a = " · ".join(f'<a href="{dk.esc(u)}" target="_blank" rel="nofollow noopener" style="color:inherit;text-decoration:none;">{dk.esc(n)}</a>' for n, u in links)
    return f'<span style="display:block;margin:4px 0 0;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};">원문 : {a}</span>'


def event_item(ev, sums):
    labs = side_pill(ev["side"]) + (dk.pill("논의중", "neutral", bare=True) if ev["talk"] else "")
    meta = (dk.news_when(ev["first"].isoformat()), f'보도 {ev["n_src"]}곳' if ev["n_src"] > 1 else (ev["links"][0][0] if ev["links"] else ""))
    own = ev["own"]
    lines = (sums.get(_iid(own["url"] or "")) or []) if own else []
    if len(lines) >= 2:   # 공용 뉴스 요약 줄이 있는 사건 — 줄 전체를 눌러 팝업 (가이드라인 10절)
        pid = dk.news_pop_id("iw", own["url"])
        return (dk.news_pop_wrap(dk.news_item(dk.esc(ev["title"]), None, labels=labs, meta=meta), pid)
                + dk.news_pop_body(pid, ev["title"], lines, source=own["src"], kind="기사", url=own["url"])), True
    return dk.news_item(dk.esc(ev["title"]), None, subs=[_src_links(ev["links"])], labels=labs, meta=meta), False


def small_row(ev):
    """한두 곳만 보도한 기사 = 작은 한 줄 (제목 링크 · 날짜 · 매체) — 버리지 않고 접어 둔다."""
    u = ev["links"][0][1] if ev["links"] else None
    t = dk.esc(ev["title"])
    head = f'<a href="{dk.esc(u)}" target="_blank" rel="nofollow noopener" style="color:#111;text-decoration:none;">{t}</a>' if u else t
    meta = " · ".join(x for x in (H.md(ev["first"].astimezone(KST).date().isoformat()), " · ".join(n for n, _ in ev["links"][:2])) if x)
    return (f'<div style="padding:9px {dk.ALIGN_PX}px;border-top:1px solid #E2E8F0;font-size:16px;line-height:26px;word-break:keep-all;">{head}'
            f'<span style="display:block;font-size:13px;line-height:19px;color:{dk.SUB};">{dk.esc(meta)}</span></div>')


# ───────────── 관련 뉴스 = 막대 두 개 + 타임라인 (2026-11-13 사용자: "우리 뉴스 긍정 · 부정 그래프처럼 · 뉴스 타임라인 · 누르면 그날 사실 블릿 · 끝에 - 기사 22건")
SIDE_BAR = {"종전": dk.BAR_PASTEL["positive"], "확전": dk.BAR_PASTEL["negative"], "방향 미정": dk.BAR_PASTEL["neutral"]}   # 뉴스 방향 막대의 긍정 · 부정 · 중립 색 그대로 (2026-11-13 사용자: 종전 = 빨강 · 확전 = 파랑)
TL_SHOWN = 5   # 타임라인 처음에 보이는 날 — 나머지는 `지난 n일 더 보기` (증시 전망 타임라인과 같은 5)


def side_bars(today_rows, rows):
    """dk.direction_bars 와 같은 꼴 — 처음엔 `오늘` 막대만, 제목 줄 오른쪽 `최근 2주` + 접기 버튼을 누르면 최근 2주 막대가 펼쳐진다 (2026-11-13 사용자: 미국 증시 뉴스 막대).
    색 · 이름만 종전 · 확전 · 방향미정. direction_bars 는 긍정 · 부정 이름이 고정이라 같은 틀을 여기서 짠다."""
    def cnt(rs):
        return {k: sum(r["side"] == k for r in rs) for k in SIDE_BAR}

    def bar(label, c):
        return dk.legend_bar(f"{label} 소식 {sum(c.values())}개", [(SIDE_LABEL[k], c[k], *SIDE_BAR[k]) for k in SIDE_BAR])   # 사건 개수 — 같은 소식을 옮긴 기사는 하나로 (2026-11-13 사용자)
    t, w = cnt(today_rows), cnt(rows)
    if not sum(w.values()):
        return ""
    n_today = sum(t.values())
    title = f"오늘 소식 {n_today}개"
    plain = f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};margin:0 0 3px;color:#111;font-weight:700;">{dk.esc(title)}</span>'
    head = (f'<span style="display:flex;justify-content:space-between;align-items:center;height:{dk.FOLD_BOX}px;margin:0;">'
            f'<span style="font-size:{dk.TINY};line-height:{dk.LH_TINY};color:#111;font-weight:700;">{dk.esc(title)}</span>'
            f'<span style="display:inline-flex;align-items:center;"><span style="font-size:{dk.TINY};line-height:{dk.LH_TINY};color:#333;font-weight:400;">최근 2주</span>{dk.fold_btn()}</span></span>')
    top = (bar("오늘", t) if n_today else plain + f'<span style="display:block;height:{dk.BARS_EMPTY_PAD}px;"></span>').replace(plain, head, 1)
    gap = f'<span style="display:block;height:{dk.BAR_GROUP_GAP - 5}px;"></span>' if n_today else ""
    return (f'<div style="margin:0 0 8px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;padding:12px 12px {dk.SEP_GAP - 3 - 10}px;">'
            f'<details data-acc="1" data-bars="1"><summary style="list-style:none;cursor:pointer;display:block;" aria-label="최근 2주 막대 보기">{top}</summary>'
            f'{gap}{bar("최근 2주", w)}</details></div>')


ONE_HARD = re.compile(r"폭발|공격|타격|공습|격추|피격|나포|봉쇄|개방|휴전|정전|합의|서명|타결|결렬|철수|파병|발사|사망|제재|발효|승인|통과")   # 실제로 일어난 일 낱말
ONE_WIRE = {"연합뉴스", "뉴스1", "뉴시스", "연합인포맥스", "연합뉴스TV"}   # 속보를 먼저 내는 통신사


def one_pick(e):
    """한 곳만 보도한 사건 중 팝업에 올릴 것 — 따옴표 발언이 아닌 `일어난 일` + 사건 낱말, 또는 통신사 기사 (AI 0, 2026-11-13 사용자: 23건 다 펼치지 말고 다른 방법).
    막 터진 사실(유조선 폭발 · 기지 공격)은 처음엔 한 곳만 보도할 수 있다. 반응 · 해설 · 칼럼은 빠진다."""
    return (not e["talk"] and bool(ONE_HARD.search(e["title"]))) or bool(e["links"] and e["links"][0][0] in ONE_WIRE)


POP_ART_GAP = 10
POP_HEAD = {"종전": ("종전 전망 정보", dk.UP), "확전": ("확전 전망 정보", dk.DOWN), "방향 미정": ("방향미정 정보", "#111")}   # 팝업 소제목 = 라벨 대신 글자 (2026-11-13 사용자: `확전 전망 정보` 파랑 굵게 본문 글씨)


SIDE_KIND3 = {"종전": "up", "확전": "down", "방향 미정": "flat"}   # 팝업 소제목 아이콘 · 색 = H.pop_group_head (증시 전망 팝업과 같은 부품)


def ev_rank(e):
    """사건 순서 = 실제로 일어난 일 먼저 → 단계 높은 것 → 최근. 옮긴 기사 수는 쓰지 않는다 (2026-11-13 사용자: 복사 수가 중요도로 읽히는 선입견)."""
    st = stage_of(e)
    return (e["talk"], -(st if st is not None else -1), -e["first"].timestamp())


def _day_pop(pid, day, evs):
    """그날 팝업 = 사건마다 한 줄(사실) + 끝 꼬리 `- 기사 n건` — 증시 전망 근거 팝업 줄(H._pop_li)과 같은 모양. 쪽마다 라벨 하나 + 블릿.
    두 곳 이상 보도한 사건 + 한 곳만이라도 one_pick 에 맞는 사건. 나머지 한 곳만 보도는 팝업에 싣지 않는다 (옛 `그 밖에 n건` 줄 삭제, 2026-11-13 사용자)."""
    lis = ""
    many = [e for e in evs if e["n"] >= 2 or one_pick(e)] or evs[:1]
    many.sort(key=ev_rank)
    groups = sorted({e["side"] for e in many}, key=lambda k: -sum(W_TALK if e["talk"] else W_ACT for e in many if e["side"] == k))   # 무게(실제 일 1 · 발언 0.5) 큰 묶음 먼저 — 옮긴 기사 수 X
    for gi, side in enumerate(groups):   # 묶음 = 방향 소제목(아이콘 + `확전 전망 정보`) + 기사 줄, 묶음 사이 가로 점선 + 15 (2026-11-13 사용자 — 옛 소제목 오른쪽 점선)
        lis += H.pop_group_head(POP_HEAD[side][0], SIDE_KIND3[side], first=gi == 0)
        for k, e in enumerate([e for e in many if e["side"] == side]):
            li = H._pop_li(e["title"], "", talk=e["talk"])   # `- 기사 n건` 꼬리 삭제 — 옮긴 곳이 많다고 중요한 일이 아니다 (2026-11-13 사용자)
            lis += H.art_gap(li, k)   # 기사와 기사 사이 +10 (2026-11-13 사용자) — 증시 전망 팝업과 같은 부품
    title = f'{H.md(day)} {C["name"]} 뉴스'
    return f'<div data-news-pop-body="{dk.esc(pid)}" data-news-pop-title="{dk.esc(title)}" hidden>{lis}</div>'


TL_MORE_STEP = H.MORE_STEP   # 더 보기 한 번에 10일 — 증시 전망 `지난 경과 더 보기` 와 같은 버튼 · 같은 개수 (2026-11-13 사용자)
TL_BOTTOM = 5   # 타임라인 아래 더 띄움 (2026-11-13 사용자 "5픽셀 정도 더")
TL_TITLE_BELOW = 10   # `News Timeline` 제목 아래 +10 (2026-11-13 사용자) — 증시 전망 Timeline 제목 아래 11 에 더함


def tail_chev(text):
    """문장 끝 › — 마지막 낱말과 › 를 한 덩어리(줄바꿈 없음)로 묶어, 두 줄로 꺾여도 › 가 문장 끝 글자 옆에 붙는다 (P541, 2026-11-13 사용자).
    옛 flex 꼴은 글이 꺾이면 › 가 오른쪽 끝에 따로 떨어졌다. 증시 전망 근거 줄은 한 줄 말줄임(_one_line)이라 해당 없음."""
    head, _, last = text.rstrip().rpartition(" ")
    chev = H._CHEV_R.replace("flex:none;display:inline-flex;", "display:inline-flex;vertical-align:-2px;margin-left:4px;", 1)
    return (dk.esc(head) + " " if head else "") + f'<span style="white-space:nowrap;">{dk.esc(last)}{chev}</span>'


def tl_lead():
    """증시 전망 timeline_lead 와 같은 머리 — 시계 아이콘을 레일 마디로, 오른쪽 `News Timeline`. 아래 날짜 점까지 점선이 이어진다 (2026-11-13 사용자: 아이콘과 점이 끊겨 있었다)."""
    big = H.CLOCK.replace('width="16" height="16"', f'width="{H.TL_TITLE_ICON}" height="{H.TL_TITLE_ICON}"', 1)
    icon = f'<span style="display:inline-flex;color:{dk.SUB};">{big}</span>'
    title = (f'<div data-tl-title="1" style="padding:0 0 {11 + TL_TITLE_BELOW}px;font-size:{H.TL_TITLE_FS}px;line-height:{H.TL_TITLE_ICON + 4}px;font-weight:700;color:#111;">News Timeline</div>')
    return f'<div style="height:{28 + H.TL_TITLE_GAP}px;"></div>' + H._tl_row(icon, H.TL_TITLE_ICON + 4, 0, title, True, False)


def _more_btn_css():
    return (f"display:inline-flex;align-items:center;gap:4px;padding:6px 12px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;"
            f"font:inherit;font-size:{dk.TINY};line-height:{dk.LH_TINY};font-weight:600;color:#333;cursor:pointer;")   # H._waiting 더 보기 버튼과 같은 값


def news_timeline(evs, days_desc, px=None):
    """날짜별 한 줄 = 그날 가장 많이 보도된 사건. 줄을 누르면 그날 사건 전부(많이 보도된 순) 팝업.
    처음 TL_SHOWN 일 + `지난 n일 더 보기 (남은 m일)` 10일씩 · 맨 끝에만 `접기` (증시 전망 타임라인과 같은 규칙, 끝 묶음 1~2일은 앞 묶음에 합침)."""
    by = {}
    for e in evs:
        by.setdefault(e["first"].astimezone(KST).date().isoformat(), []).append(e)
    days = [d for d in days_desc if by.get(d)]
    pops = ""
    node = (f'<span style="display:inline-block;width:{H.TL_DOT}px;height:{H.TL_DOT}px;box-sizing:border-box;border:2px solid {H.TL_LINE};border-radius:50%;background:#fff;"></span>')
    ref_nm, ref_sym, ref_fmt = TL_REF[C["iss"]["id"]]
    ref = px[ref_sym].dropna() if px is not None and ref_sym in px else None

    def price(d):
        """날짜 옆 기준 가격 = 그날 소식 뒤 첫 종가(한국 시간 다음 날 아침 도착하는 미국 종가) · 전날 대비 ▲▼ — 주말 · 휴장 · 아직 안 닫힌 날은 비움."""
        if ref is None:
            return ""
        t = pd.Timestamp(d)
        if t not in ref.index:
            return ""
        i = ref.index.get_loc(t)
        if i == 0:
            return ""
        c, p = float(ref.iloc[i]), float(ref.iloc[i - 1])
        if c == p:   # 전날 값을 그대로 채운 줄(선물 자료가 아직 안 들어온 날) — 0.0% 로 보이지 않게 비움
            return ""
        chg = (c / p - 1) * 100
        val = dk.emph_tri(dk.arrow(chg, 1, "%").replace("font-weight:700;", "font-weight:400;"), H.TL_TRI) if round(chg, 1) != 0 else '<span style="color:#111;">0.0%</span>'
        return (f'<span style="font-weight:400;color:{dk.SUB};white-space:nowrap;">{dk.esc(ref_nm)}</span>'
                f'<span style="font-weight:400;color:#111;white-space:nowrap;">{dk.esc(ref_fmt.format(c))}</span>'
                f'<span style="white-space:nowrap;">{val}</span>')

    def row(d, last, first=False):
        """증시 전망 타임라인(H._waiting · day_why_html)과 같은 꼴 (2026-11-14 사용자): 날짜 굵게 한 줄 → 아래 근거 한 줄 = 쪽 라벨 + 한 줄 글(말줄임) + ›.
        라벨은 줄바꿈 없이 글 앞, 논의중은 글 뒤 작은 표시(H._talk_mark). 줄 전체 = 그날 팝업."""
        es = sorted(by[d], key=ev_rank)   # 그날 대표 = 실제 일 · 높은 단계 먼저 (옛: 가장 많이 옮겨진 기사)
        top = es[0]
        pid = dk.news_pop_id("iwday", d)
        pad = 12 - dk.VP
        lab = side_pill(top["side"]).replace("vertical-align:middle;", f"vertical-align:middle;flex:none;margin-right:{dk.PILL_GAP}px;", 1)
        talk = H._talk_mark().replace(f"margin:0 {dk.PILL_GAP}px;", f"margin:0 0 0 {dk.PILL_GAP}px;flex:none;", 1) if top["talk"] else ""
        chev = f'<span aria-hidden="true" style="flex:none;display:inline-flex;transform:rotate(-90deg);color:#333;">{H.CHEV14}</span>'
        content = (f'<div data-news-pop="{dk.esc(pid)}" role="button" tabindex="0" style="cursor:pointer;">'
                   f'<div style="display:flex;align-items:center;gap:8px;padding:{0 if first else pad}px 0 {pad}px;font-size:{dk.NAME};line-height:{dk.LH_CARD};font-weight:700;color:#111;"><span style="white-space:nowrap;">{H.md(d)}</span>{price(d)}</div>'
                   f'<div style="display:flex;align-items:center;gap:4px;margin:-4px 0 {pad}px;">'
                   f'<span style="display:flex;align-items:center;min-width:0;flex:0 1 auto;">{lab}{H._one_line(dk.esc(top["title"]), grow=False, color=H.TL_WHY_INK)}{talk}</span>{chev}</div>'
                   + ("" if last else f'<div style="height:{H.TL_DAY_GAP}px;"></div>') + '</div>')
        return H._tl_row(node, int(dk.LH_CARD.rstrip("px")), 0 if first else pad, content, False, last), _day_pop(pid, d, es)

    shown = days if len(days) <= TL_SHOWN + 2 else days[:TL_SHOWN]   # 1~2일 숨기려고 버튼을 두지 않는다
    rest = days[len(shown):]
    out = ""
    for i, d in enumerate(shown):
        h, p = row(d, i == len(shown) - 1 and not rest, first=i == 0)
        out += h
        pops += p
    if rest:
        btn = _more_btn_css()
        up = f'<span style="display:inline-flex;transform:rotate(180deg);">{dk.ACC_CHEV.replace("acc-chev", "fc-up")}</span>'
        close = (f'<div style="padding:6px 0 0 {H.TL_RAIL + 8}px;"><button type="button" style="{btn}" '
                 'onclick="var d=this.closest(\'.fc-more-root\');d.open=false;d.scrollIntoView({block:\'nearest\'});">'
                 f'접기 {up}</button></div>')
        chunks = [rest[k:k + TL_MORE_STEP] for k in range(0, len(rest), TL_MORE_STEP)]
        if len(chunks) > 1 and len(chunks[-1]) <= 2:
            chunks[-2:] = [chunks[-2] + chunks[-1]]

        def chunk(ci):
            nonlocal pops
            part, left = chunks[ci], sum(len(c) for c in chunks[ci:])
            label = f"지난 {len(part)}일 더 보기" + (f" (남은 {left}일)" if left > len(part) else "")
            last = ci == len(chunks) - 1
            inner = ""
            for i, d in enumerate(part):
                h, p = row(d, i == len(part) - 1 and last)
                inner += h
                pops += p
            inner += close if last else chunk(ci + 1)
            return (f'<details class="fc-more{" fc-more-root" if ci == 0 else ""}" style="margin:0;">'
                    f'<summary style="list-style:none;cursor:pointer;padding:6px 0 0 {H.TL_RAIL + 8}px;">'
                    f'<span style="{btn}">{label} {dk.ACC_CHEV}</span></summary>' + inner + '</details>')
        out += chunk(0)
    return H.PLUS_CSS + tl_lead() + out + pops


# ───────────── 뉴스 바늘 (2026-11-13 사용자: 기술 지표 게이지처럼 바늘이 종전 · 확전 쪽으로) — 기사 방향을 센 것, 예측 아님
GAUGE_ZONES = [(-1.0, -0.5, "확전 뚜렷", TS.ZONES[0][3]), (-0.5, -0.15, "확전", TS.ZONES[1][3]), (-0.15, 0.15, "방향미정", TS.ZONES[2][3]),
               (0.15, 0.5, "종전", TS.ZONES[3][3]), (0.5, 1.0, "종전 뚜렷", TS.ZONES[4][3])]   # 왼쪽 확전 파랑 · 오른쪽 종전 빨강 = 라벨 색 그대로
GAUGE_TITLE_TOP = 6 + 15   # 카드 안 위 테두리 ~ `최근 일주일 뉴스는 어느 쪽?` 글자 +15 (2026-11-13 사용자 — 카드 바깥 여백이 아니라 안쪽)
GAUGE_DAYS = 7   # 바늘 = 최근 7일 기사 — 48시간은 하루 건수에 바늘이 크게 흔들린다


W_ACT, W_TALK = 1.0, 0.5   # 사건 무게 — 실제로 일어난 일 1 · 발언 · 논의 0.5. 같은 일을 몇 곳이 옮겼는지는 세지 않는다 (2026-11-13 사용자: 복사 기사 수는 방향이 아니다)


def events(rows):
    return [event_of(c) for c in cluster(rows)]


def ev_net(evs):
    """사건 방향 — (종전 무게 − 확전 무게) ÷ 전체 무게(방향미정 포함). 기사 수 대신 (옛 _net = 기사 수)."""
    w = lambda e: W_TALK if e["talk"] else W_ACT   # noqa: E731
    tot = sum(w(e) for e in evs)
    a = sum(w(e) for e in evs if e["side"] == "종전")
    b = sum(w(e) for e in evs if e["side"] == "확전")
    return (a - b) / tot if tot else 0.0


# ───────────── 하루 한 번 AI 판정 (2026-11-13 사용자: "매시간 말고 하루 한 번 묶어서 결론") — 사건마다 방향 · 실제로 일어났나 · 단계
AI_ON = False        # issue_watch_daily --ai (07:30 본 실행만). 13:00 갱신 · 목업은 캐시만 읽는다
AI_CACHE = os.path.join(OUT, "_stage_ai.json")   # 운영 = 상태 저장소 records/issues/stage_ai.json
AI_BATCH, AI_MAX_CALLS, AI_TIME = 20, 5, 120   # 20사건 묶음 · 이슈마다 실행당 최대 5회 · 이슈마다 2분(세 이슈 최대 6분, Groq 는 호출 사이 60초 — 07:30 실행 60분 제한).
# 하루 새 사건 약 45개 = 이란 2회 · 관세 · 수출 통제 각 1회. 첫날 밀린 것(약 585개)은 최신부터 며칠에 나눠 (2026-11-13 시험: 공통 10회를 이란이 다 써 관세 · 수출 통제 0회)
AI_CHAIN = "json-backup-first"   # Groq(Qwen → gpt-oss) → DeepSeek → Gemini lite — 운영지침 3-2 순서, flash 로는 안 넘어감
_AI = {"cache": None, "calls": 0, "model": Counter(), "t0": None}


def _ai_cache():
    if _AI["cache"] is None:
        try:
            _AI["cache"] = json.load(open(AI_CACHE, encoding="utf-8"))
        except (OSError, ValueError):
            _AI["cache"] = {}
    return _AI["cache"]


def _ai_prompt(evs):
    g, b = C["good"], C["bad"]
    lad = lambda side: " → ".join(f"{i}:{nm}" for i, (nm, _) in enumerate(C["stages"][side]))   # noqa: E731
    lines = "\n".join(f"{i}. {e['title']}" + (f" / {e['rep']['title']}" if e["rep"]["title"] != e["title"] else "") for i, e in enumerate(evs))
    return (f"이슈: {C['name']}. 아래 뉴스 사건(기사 제목)마다 판정하라.\n"
            f"side: '{g}'(시장에 좋은 쪽) · '{b}'(나쁜 쪽) · '없음'(어느 쪽도 아니거나 해설 · 반응).\n"
            "done: 제목이 말하는 일이 실제로 일어났으면 true. 발언 · 주장 · 논의 · 검토 · 전망 · 임박 · 부인 · 의문문 · 칼럼이면 false.\n"
            f"stage: {g} 사다리 [{lad('종전')}], {b} 사다리 [{lad('확전')}] 에서 그 side 의 번호. done 이 false 면 0(말 단계) 또는 null, "
            "실제로 일어난 일만 그 단계 번호. side 가 '없음'이면 null.\n"
            '답은 JSON 하나: {"items": [{"i": 번호, "side": "...", "done": true, "stage": 2}, ...]} — 모든 번호를 빠짐없이.\n\n' + lines)


def _ai_validate(n):
    def v(val):
        items = val.get("items") if isinstance(val, dict) else None
        if not isinstance(items, list) or sorted(int(x.get("i", -1)) for x in items) != list(range(n)):
            raise ValueError("items 번호가 빠지거나 남음")
        for x in items:
            if x.get("side") not in (C["good"], C["bad"], "없음"):
                raise ValueError(f"side 값 {x.get('side')}")
            st = x.get("stage")
            if st is not None:
                side = "종전" if x["side"] == C["good"] else "확전" if x["side"] == C["bad"] else None
                if side is None or not (0 <= int(st) < len(C["stages"][side])):
                    raise ValueError(f"stage 범위 {st}")
        return val
    return v


def ai_judge(evs, today):
    """최근 2주 사건 중 캐시에 없는 것만, 최신 먼저 AI 로 판정 → 캐시. AI_ON 이 아니면 캐시만 붙인다. 실패하면 그 묶음은 글자 패턴 그대로."""
    cache = _ai_cache()
    todo = [e for e in sorted(evs, key=lambda e: e["first"], reverse=True) if f'{C["iss"]["id"]}|{e["key"]}' not in cache]
    if AI_ON and todo:
        import llm_chain as LC
        import time
        pool = LC.LLMPool(AI_CHAIN, label=f"issue-{C['iss']['id']}")
        t0 = time.time()   # 이슈마다 따로 — 한 이슈의 밀린 사건이 다른 이슈 몫을 다 쓰지 않게
        mine = 0
        for k in range(0, len(todo), AI_BATCH):
            if mine >= AI_MAX_CALLS or time.time() - t0 > AI_TIME:
                print(f"[issue-ai] {C['iss']['id']} 상한(이슈마다 {AI_MAX_CALLS}회 · {AI_TIME}초) — 남은 {len(todo) - k}건은 다음 날")
                break
            part = todo[k:k + AI_BATCH]
            _AI["calls"] += 1
            mine += 1
            try:
                val = pool.generate_json(_ai_prompt(part), validate=_ai_validate(len(part)), max_tokens=1200)
            except Exception as e:  # noqa: BLE001 — 실패 묶음은 글자 패턴으로
                print(f"[issue-ai] 실패: {str(e)[:160]}")
                continue
            _AI["model"][pool.last_model] += 1
            for x in val["items"]:
                e = part[int(x["i"])]
                cache[f'{C["iss"]["id"]}|{e["key"]}'] = {"side": x["side"], "done": bool(x.get("done")), "stage": x.get("stage"),
                                                       "day": e["first"].astimezone(KST).date().isoformat(), "model": pool.last_model}
        old = (today - dt.timedelta(days=30)).isoformat()
        for k2 in [k2 for k2, v in cache.items() if v.get("day", "") < old]:   # 30일 지난 판정은 지운다
            del cache[k2]
        os.makedirs(os.path.dirname(AI_CACHE), exist_ok=True)
        json.dump(cache, open(AI_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return _ai_apply(evs)


def _ai_apply(evs):
    """캐시에 있는 AI 판정만 사건에 붙인다 (AI 호출 없음) — 지난 2주 칸 셈이 같은 판정을 쓰게."""
    cache = _ai_cache()
    inv = {C["good"]: "종전", C["bad"]: "확전", "없음": "방향 미정"}
    n = 0
    for e in evs:
        a = cache.get(f'{C["iss"]["id"]}|{e["key"]}')
        if a:
            e["side"], e["talk"] = inv[a["side"]], not a["done"]
            e["ai_stage"] = None if a["stage"] is None or e["side"] == "방향 미정" else int(a["stage"])
            n += 1
    return n


def stage_of(ev):
    """사건의 단계 번호(사다리 아래 0부터) — 방향미정 · 맞는 낱말 없음 = None. 발언 · 논의는 첫 단계로만 (말만으로 회담 · 합의 단계에 올리지 않는다)."""
    if "ai_stage" in ev:   # 하루 한 번 AI 판정(ai_judge)이 있으면 그것 — 글자 패턴은 부인 · 임박 · `목소리` 를 못 가린다
        return ev["ai_stage"]
    if _AI["cache"]:   # AI 판정을 쓰는 중이면 판정 전 사건은 단계에 올리지 않는다 — 글자 패턴과 섞이면 `부인` 이 `회담` 으로 오른다 (최신부터 판정되므로 며칠이면 다 찬다)
        return None
    if ev["side"] not in ("종전", "확전"):
        return None
    txt = f'{ev["title"]} {ev["rep"]["title"]}'
    best = None
    for i, (_, pat) in enumerate(C["stages"][ev["side"]]):
        if i and ev["talk"]:
            break
        if re.search(pat, txt):
            best = i
    return best


def _net(rs):
    a, b = sum(r["side"] == "종전" for r in rs), sum(r["side"] == "확전" for r in rs)
    return ((a - b) / len(rs) if rs else 0.0), a, b, len(rs) - a - b   # 기술 지표 게이지와 같은 셈 — (종전 − 확전) ÷ 전체(방향미정 포함)


def _zone_word(net):
    return next(nm for lo, hi, nm, _ in GAUGE_ZONES if lo <= net <= hi)


WEEK_DESC = {"종전 뚜렷": "종전 기사가 훨씬 많았습니다", "종전": "종전 기사가 조금 더 많았습니다", "방향미정": "종전 · 확전 기사가 엇갈렸습니다",
             "확전": "확전 기사가 조금 더 많았습니다", "확전 뚜렷": "확전 기사가 훨씬 많았습니다"}
WEEK_PREV = {"종전 뚜렷": "종전 기사가 훨씬 많았습니다", "종전": "종전 기사가 더 많았습니다", "방향미정": "엇갈렸습니다",
             "확전": "확전 기사가 더 많았습니다", "확전 뚜렷": "확전 기사가 훨씬 많았습니다"}


def week_line(w, pw):
    """게이지 아래 한 줄 — 숫자 없이 이번 주 · 지난주 (P542, 2026-11-13 사용자: 구체적인 숫자 X, 짤막하게)."""
    if pw is None:
        return f"이번 주는 {WEEK_DESC[w]}."
    if pw == w:
        return f"이번 주도 지난주처럼 {WEEK_DESC[w]}."
    return f"이번 주는 {WEEK_DESC[w]}. 지난주는 {WEEK_PREV[pw]}."


def gauge_card(evs, today):
    """제목 아래 요약 — 최근 7일 사건 방향 바늘(실제 일 1 · 발언 0.5, 옮긴 기사 수 무시) + 답 + 지난주 한 줄. 흰 카드 = 기술 지표 `전체요약` 게이지와 같은 틀."""
    d7 = (today - dt.timedelta(days=GAUGE_DAYS - 1)).isoformat()
    d14 = (today - dt.timedelta(days=GAUGE_DAYS * 2 - 1)).isoformat()
    day = lambda e: e["first"].astimezone(KST).date().isoformat()   # noqa: E731
    now = [e for e in evs if day(e) >= d7]
    prev = [e for e in evs if d14 <= day(e) < d7]
    net = ev_net(now)
    pnet = ev_net(prev) if prev else None
    w = _zone_word(net)
    col = dk.UP if net >= 0.15 else dk.DOWN if net <= -0.15 else "#111"
    line = week_line(w, _zone_word(pnet) if pnet is not None else None)
    return (f'<span style="{dk.MULTI}margin:0 0 8px;text-align:center;"><span style="display:block;padding:{dk.CHART_CARD_PAD}px 8px;">'
            f'<span style="display:block;font-weight:700;color:#111;margin:{GAUGE_TITLE_TOP}px 0 4px;font-size:16px;line-height:24px;">최근 일주일 뉴스는 어느 쪽?</span>'
            f'{TS.gauge_svg(net, "big", zones=GAUGE_ZONES)}'
            f'<span style="display:block;font-weight:700;color:{col};font-size:19px;line-height:25px;margin-bottom:4px;">{dk.esc(w)}</span>'
            f'<span style="display:block;margin-bottom:4px;padding:0 4px;font-size:14px;line-height:20px;color:{dk.SUB};word-break:keep-all;">{dk.esc(line)}</span>'
            '</span></span>')


# ───────────── 질문 카드 (강조 카드 · 펼침 — 데일리 · 증시 전망 갈래 카드와 같은 qc.question_card, 2026-11-13 사용자 "강조 카드의 펼침 열림 디자인")
VIOLET = qc.SOON


def _theme(on):
    """움직임 · 뉴스 늘어남 = 보라 카드(방향이 주가 오름 · 내림이 아니라 `종전 쪽` 이라 빨강 · 파랑을 쓰지 않는다), 아니면 회색."""
    return ("uncertain", VIOLET) if on else ("neutral", "#111")


def _sp(html):
    return f"<span>{html}</span>"   # 근거 줄 값 · 이름이 HTML 이면 <span 으로 시작해야 그대로 쓴다


def _ttl(t):
    """카드 안 그래프 · 표 제목 — 그래프 제목과 같은 `※` + 16/24 굵게."""
    return f'{dk.CHART_TITLE_M}{dk.esc(t)}</span>'   # 공용 그래프 제목 (가이드라인 9절 간격 · 7-3, 2026-11-14 사용자 "그래프 스타일은 디자인 규칙에 맞게")


def q_news(iran, counts, days, r48):
    n48, base = iran["n48"], iran["base48"]
    ratio = n48 / base if base else None
    th, ink = _theme(iran["hot"])
    ans = f"평소의 {ratio:.1f}배" if ratio else f"{n48}건"
    nm = C["name"]
    first = (f"최근 48시간 {nm} 기사는 {n48}건으로 평소({base:.0f}건)의 {ratio:.1f}배입니다." if ratio else f"최근 48시간 {nm} 기사는 {n48}건입니다.")   # 방향 건수 삭제 — 화제성만 (2026-11-13 사용자)
    r2w = [x for x in iran["rows"] if x["t"].astimezone(KST).date().isoformat() >= days[0]]
    t, w = sum(x["side"] == "종전" for x in r2w), sum(x["side"] == "확전" for x in r2w)
    cap = sorted(c for c in iran["capped"] if c in days)
    note = "같은 소식을 여러 곳이 옮긴 기사도 모두 센 숫자라, 관심의 크기만 보여 줍니다."   # 방향은 바늘 · `어디까지 왔나?` 가 사건 단위로 (2026-11-13 사용자: 복사 기사 수 ≠ 중요도)
    tip = ("출처 : 알파스코프 뉴스 모음(CNBC) + 구글 뉴스 한국어 검색, 방송은 아직 안 셈\n평소 = 직전 4주 동안 48시간마다 나온 기사 수의 평균\n"
           "그래프 점 하나 = 지금 시각에서 24시간씩 끊어 센 기사 수, 마지막 점 = 최근 24시간")
    lines = [(first, "plain"), (news_chart(counts, NOW_LABEL[0], base / 2 if base else None), "html"), (note, "note")]
    return qc.question_card("얼마나 화제인가?", ans, th, ink, lines, tip=tip), r2w   # 펼침은 `어디까지 왔나?` 로 옮김


def q_market(links, groups, oil_gr, oil_line):
    d0, d1 = links[0]["d0"], links[0]["d1"]
    moving = [g for g, wd, *_ in groups if f"{W()} 방향" in wd]
    on = bool(moving)
    th, ink = _theme(on)
    by_w = {g: wd for g, wd, *_ in groups}
    ans = (f'{moving[0]}{"만" if len(moving) == 1 else " 외"} {"조금" if "조금" in by_w[moving[0]] else "움직임"}') if on else "평소 범위"
    parts = []
    for g, wd, ok, n, rs in groups:
        if f"{W()} 방향" in wd:
            parts.append(f"{g} 지표 {n}개 중 {ok}개가 {W()} 때 흔히 설명하는 방향으로 움직였습니다")
        elif "반대" in wd:
            parts.append(f"{josa(g, ('은', '는'))} 반대로 움직였습니다")
    calm = [g for g, wd, *_ in groups if wd == "평소 범위"]
    first = (". ".join(parts) + ". " if parts else "") + (f"{josa(' · '.join(calm), ('은', '는'))} 평소 범위입니다." if calm else "")
    lines = [(f"최근 10거래일({H.md(d0.strftime('%Y-%m-%d'))} → {H.md(d1.strftime('%Y-%m-%d'))} 종가) 기준입니다. " + first, "plain")]
    for gi, (g, wd, ok, n, rs) in enumerate(groups):
        kind = "uncertain" if f"{W()} 방향" in wd else "area"
        lines.append(("row", _sp(f"<b>{dk.esc(g)}</b>"), f"{n}개 중 {ok}개", wd, *(("gap",) if gi else ())))
        for r in rs:
            exp = "내림" if r["sg"] < 0 else "오름"
            sub = f'흔한 설명은 {exp} · 평소의 {abs(r["z"]):.1f}배 {"같은" if r["sg"] * r["z"] > 0 else "반대"} 방향'
            lines.append(("row", r["name"], arrow(r["pct"]), sub, "tight"))
    lines += ([(oil_gr, "html")] if oil_gr else []) + ([(oil_line, "note")] if oil_line else [])
    tip = ("평소의 몇 배 = 이 지표가 보통 10거래일에 움직이는 폭(직전 60거래일 기준)의 몇 배인지.\n"
           "· 뚜렷하게 = 흔한 설명 방향으로 2배 넘게\n· 조금 = 1~2배\n· 반대로 = 반대 방향 1배 넘게\n"
           "흔한 설명 = 시장에서 흔히 쓰는 설명(교과서 · 언론), 우리 주장이 아님.\n"
           "묶음 오른쪽 = 흔한 설명 방향으로 평소보다 크게(1배 넘게) 움직인 지표 수")
    return qc.question_card("시장이 먼저 움직이나?", ans, th, ink, lines, tip=tip)


HIST_COL_OLD = {"strong": GAUGE_ZONES[4][3], "some": GAUGE_ZONES[3][3], "rev": GAUGE_ZONES[0][3], "mixed": "#CBD5E1", "calm": "#F1F5F9"}   # 종전 빨강 · 종전 조금 연빨강 · 확전 파랑 · 방향미정 회색 · 평소 연회색 (2026-11-13 사용자: 종전 · 확전 색으로)
def news_col(word):
    return "good" if word.startswith(C["good"]) else "bad" if word.startswith(C["bad"]) else "mixed"   # 뉴스가 늘어난 날 = 그날 기사 방향 색   # 움직임 보라 · 조금 연보라(카드 보라 계열) · 반대 연파랑 · 평소 회색


def _hist_grid(hist):
    """줄 = 뉴스 · 유가 · 주식 · 안전 자산, 칸 = 거래일(왼쪽 옛날 → 오른쪽 최근, 가이드라인 시간 축). 칸 색 = 그날 상태.
    그래프 규칙에 맞춤 (2026-11-14 사용자 "강조 카드 안 그래프 스타일은 디자인 규칙에 맞게"): 흰 카드 안쪽 = dk.trend_card 와 같은 값(위 10 + 범례 5 · 좌우 12 · 아래 0),
    범례 = 그래프 위 오른쪽(칩 9 · 모서리 2 · 칩 사이 12 · 13px), 칸 = 줄 막대 꼴(높이 10 · 모서리 3 · 빈 칸 #F1F5F9), 가로축 이름 13 · 줄 칸 26."""
    def cell(c):
        return f'<span style="flex:1 1 0;min-width:0;height:10px;border-radius:3px;background:{c};"></span>'
    gs, gl, bs, bl = TS.ZONES[4][3], TS.ZONES[3][3], TS.ZONES[0][3], TS.ZONES[1][3]

    def ncol(word):   # 뉴스 = 그날까지 7일 바늘 말 (`뚜렷` = 진함)
        s = news_side(word)
        return HIST_COL["mixed"] if s is None else (gs if "뚜렷" in word else gl) if s == C["good"] else (bs if "뚜렷" in word else bl)

    def mcol(side, strong):   # 시장 묶음 = 그날까지 5거래일 쪽 (2배 넘는 지표 있음 = 진함)
        return HIST_COL["calm"] if side == "평소 범위" else (gs if strong else gl) if side == C["good"] else (bs if strong else bl)
    rows = [("뉴스", [ncol(h.get("side", "방향미정")) for h in hist])]   # 양쪽 다 색 (2026-11-14 — 옛 칸은 시장을 종전 쪽만 칠했다)
    for g, _ in GROUPS:
        rows.append((g, [mcol(*h["gside"].get(g, ("평소 범위", False))) for h in hist]))
    lab_w = 64
    out = ""
    for i, (nm, cs) in enumerate(rows):
        out += (f'<span style="display:flex;align-items:center;gap:6px;margin:{0 if i == 0 else 4}px 0 0;">'
                f'<span style="flex:none;width:{lab_w}px;font-size:{dk.TINY};line-height:20px;color:#111;white-space:nowrap;">{dk.esc(nm)}</span>'
                f'<span style="flex:1;display:flex;gap:2px;">{"".join(cell(c) for c in cs)}</span></span>')
    n = len(hist)
    ax = (f'<span style="display:flex;justify-content:space-between;align-items:flex-start;height:26px;margin:{dk.AXIS_PAD - 10}px 0 0 {lab_w + 6}px;font-size:{dk.AXIS_FS};line-height:20px;color:{dk.NOTE};">'
          f'<span>{H.md(hist[0]["day"])}</span><span>{H.md(hist[n // 2]["day"])}</span><span>{H.md(hist[-1]["day"])}</span></span>')
    chip = lambda c, t: (f'<span style="display:inline-flex;align-items:center;gap:5px;white-space:nowrap;">'   # noqa: E731
                         f'<span style="width:{dk.LEGEND_CHIP}px;height:{dk.LEGEND_CHIP}px;border-radius:2px;background:{c};"></span>{dk.esc(t)}</span>')
    used = {c for _, cs in rows for c in cs}
    leg = (f'<span data-chart-top="1" style="display:flex;flex-wrap:wrap;justify-content:flex-end;column-gap:12px;font-size:{dk.LEGEND_FS};line-height:{dk.LH_CARD};color:{dk.NOTE};'
           f'margin:{dk.LEGEND_TOP}px 0 6px;padding-left:{dk.LEGEND_LEFT}px;">'
           + "".join(chip(c, t) for c, t in legend_items() if c in used or t == "평소") + '</span>')   # 범례 = 그래프 위 오른쪽 (가이드라인 9절)
    return (f'<span style="{dk.MULTI}margin:0 {dk.CHART_CARD_X}px;"><span style="display:block;padding:{dk.CHART_CARD_PAD}px 12px 0;">'
            f'{leg}{out}{ax}</span></span>')


def legend_items():
    """색 → 이름 (좋은 쪽 진함 · 연함 · 나쁜 쪽 진함 · 연함 · 방향미정 · 평소), 같은 색은 한 번."""
    g, b = C["good"], C["bad"]
    pairs = [(TS.ZONES[4][3], g), (TS.ZONES[3][3], f"{g} 조금"), (TS.ZONES[0][3], b), (TS.ZONES[1][3], f"{b} 조금"), (HIST_COL["mixed"], "방향미정"), (HIST_COL["calm"], "평소")]
    return pairs


def q_history(hist):
    """답 = 묶음이 종전 방향으로 움직인 날 수가 가장 많은 것 (옛 `4번 바뀜` · `1일째` — `움직임` ↔ `조금` 이 바뀔 때마다 다시 세서 칸 그림과 어긋났다).
    펼치면 한 문장 + 날짜 × 묶음 칸."""
    n = len(hist)
    hot = sum(bool(h.get("hot")) for h in hist)
    mv = {g: sum(f"{W()} 방향" in h["groups"].get(g, "") for h in hist) for g, _ in GROUPS}
    g1 = max(mv, key=mv.get)
    ans = (f"{g1} {n}일 중 {mv[g1]}일" if mv[g1] else f"뉴스 {n}일 중 {hot}일" if hot else "조용함")
    parts = [f"뉴스가 늘어난 날은 {hot}일" if hot else "뉴스가 늘어난 날은 없었고"]
    parts += [f"{josa(g, ('이', '가'))} {W()} 방향으로 움직인 날은 {k}일" for g, k in mv.items() if k]
    rv = {g: sum("반대" in h["groups"].get(g, "") for h in hist) for g, _ in GROUPS}
    parts += [f"{josa(g, ('은', '는'))} {R()} 방향으로 {k}일" for g, k in rv.items() if k]
    calm = [g for g in mv if not mv[g] and not rv[g]]
    first = (f"최근 {n}거래일 가운데 " + ", ".join(parts) + "입니다."
             + (f" {josa(' · '.join(calm), ('은', '는'))} 평소 범위였습니다." if calm else ""))
    lines = [(first, "plain"), (_hist_grid(hist), "html"),
             ("미국 종가 기준이라 날짜는 뉴욕 날짜입니다.", "note")]
    tip = "날마다 같은 기준으로 센 상태입니다.\n기준선 근처에서는 하루 사이에 `움직임` ↔ `조금` 으로 바뀔 수 있습니다."
    return qc.question_card("지난 2주는?", ans, "neutral", "#111", lines, tip=tip)


def gauge_word(evs, today):
    d7 = (today - dt.timedelta(days=GAUGE_DAYS - 1)).isoformat()
    return _zone_word(ev_net([e for e in evs if e["first"].astimezone(KST).date().isoformat() >= d7]))


def _excl(t):
    return (f'<div style="display:flex;align-items:flex-start;gap:4px;margin:4px 0 0;font-size:13px;line-height:19px;color:{dk.SUB};word-break:keep-all;">'
            f'<span style="flex:none;display:flex;align-items:center;height:19px;">{H.EXCL_ICON}</span><span>{dk.esc(t)}</span></div>')


def _side_box(side):
    """기술 지표 채운 상자(tech_signals.box) — 좋은 쪽 = 빨강 상자 · 나쁜 쪽 = 파랑 · 평소 = 회색, 기호 없이 글자만."""
    kind = "up" if side == C["good"] else "down" if side == C["bad"] else "flat"
    return TS.box(kind, side if kind != "flat" else "평소", dk.esc, sym=False)


def _align_table(gs):
    """시장 지표 = 기술 지표 표 꼴 (2026-11-14 사용자: "일반 독자가 꼼꼼히 볼 수치가 아니라 가볍게 보는 수치 — 기술 지표 느낌으로").
    묶음 = 기술 지표 묶음 제목(18 굵게) + 오른쪽 묶음 상자, 줄 = 이름 15 + 회색 13 `종전되면 흔히 내림` · 오른쪽 등락(보통 굵기) + 상자. 평소의 몇 배는 툴팁 기준으로만."""
    th = "uncertain" if market_side(gs) != "평소 범위" else "neutral"
    line = dk.darken(dk.lighten(dk.lighten(dk.CARD_DIR[th][1]), 0.3), 0.02)   # 질문 카드 줄 구분선과 같은 색
    out = ""
    for x in gs:
        head = (f'<span style="display:flex;justify-content:space-between;align-items:center;margin:18px 0 2px;font-weight:700;color:#111;font-size:18px;line-height:26px;">'
                f'<span>{dk.esc(x["g"])}</span></span>')   # 묶음 · 줄 상자(종전 · 확전 · 평소) 삭제 — 회색 `종전되면 흔히 내림` 과 반복돼 헷갈린다 (2026-11-14 사용자)
        trs = []
        for r in x["rs"]:
            exp = "내림" if r["sg"] < 0 else "오름"
            sz = r["sg"] * r["z"]
            way = W() if sz >= Z_SOME else R() if sz <= -Z_SOME else "평소 범위"
            pct = f'{"+" if r["pct"] >= 0 else "−"}{abs(r["pct"]):.1f}%'
            trs.append(f'<span style="min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{dk.esc(r["name"])}'
                       f'<span style="margin-left:4px;font-size:{TS.WHY_FS};line-height:19px;color:{dk.SUB};">{W()}되면 흔히 {exp}</span></span>'
                       f'<span style="flex:none;display:inline-flex;align-items:center;gap:8px;">{pct}{_side_box(way)}</span>')   # 줄마다 종전 · 확전 · 평소 상자 (2026-11-14 사용자: 묶음 제목 상자만 빼고 줄에는 붙임)
        out += head + TS._table(trs, line)
    return f'<span style="display:block;margin-top:-12px;">{out}</span>'


def q_align(word, links, gs, oil_gr, oil_line, hist, asof):
    """시장도 같은 쪽인가? — 옛 `지금은` · `시장이 먼저 움직이나?` · `지난 2주는?` 셋을 하나로 (2026-11-14 사용자: 위 바늘은 확전인데 아래 카드는 종전 방향이라 헷갈림).
    기간 = 최근 일주일(뉴스 7일 · 시장 5거래일), 시장 지표도 양쪽을 다 센다. 뉴스와 시장이 다르면 `엇갈림` 이라고 말한다."""
    g, b = C["good"], C["bad"]
    ns, mk = news_side(word), market_side(gs)
    if mk == "평소 범위":
        ans = "시장은 평소 범위"
    elif mk == "엇갈림":
        ans = "시장 안에서 엇갈림"
    elif ns is None:
        ans = f"시장만 {mk} 쪽"
    else:
        ans = f"같은 쪽 ({mk})" if ns == mk else "엇갈림"
    d0, d1 = links[0]["d0"], links[0]["d1"]
    nd = f"{ns} 소식이 더 많았습니다" if ns else f"{g} · {b} 소식이 엇갈렸습니다"
    mv = [f"{josa(x['g'], ('이', '가'))} {x['side']} 쪽으로" for x in gs if x["side"] != "평소 범위"]
    calm = [x["g"] for x in gs if x["side"] == "평소 범위"]
    md = (" · ".join(mv) + " 움직였습니다." if mv else "") + ((" " if mv else "") + f"{josa(' · '.join(calm), ('은', '는'))} 평소 범위입니다." if calm else "")
    verdict = ("" if mk == "평소 범위" or ns is None else " 뉴스와 시장이 같은 쪽을 가리킵니다." if ns == mk else " 뉴스와 시장이 서로 다른 쪽을 가리킵니다.")
    first = f"최근 일주일 뉴스는 {nd}. 같은 기간({H.md(d0.strftime('%Y-%m-%d'))} → {H.md(d1.strftime('%Y-%m-%d'))} 종가) 시장은 " + md + verdict
    lines = [(first, "plain"), (_align_table(gs), "html")]
    lines += [(_ttl("날마다 어느 쪽이었나") + _hist_grid(hist), "html"),
              ("칸 하나 = 그날까지 일주일입니다. 미국 종가 기준이라 날짜는 뉴욕 날짜입니다.", "note")]
    lines += ([(oil_gr, "html")] if oil_gr else []) + ([(oil_line, "note")] if oil_line else [])
    lines.append((_excl(f"{asof} 기준입니다."), "html"))
    tip = ("뉴스 = 위 바늘과 같은 셈(최근 7일 소식, 실제로 일어난 일 1 · 발언 0.5).\n"
           f"시장 = {W()}되면 움직인다고 흔히 설명하는 지표를 묶음별로 — 묶음 안 2개 이상이 한쪽으로 평소보다 크게 움직이면 그 쪽.\n"
           "평소의 몇 배 = 이 지표가 보통 5거래일에 움직이는 폭(직전 60거래일 기준)의 몇 배인지, 1배 넘으면 그 쪽.\n"
           "흔한 설명 = 시장에서 흔히 쓰는 설명(교과서 · 언론), 알파스코프의 주장이 아님.\n"
           "예측이 아니라 지금까지 일어난 일입니다.")
    th, ink = _theme(mk not in ("평소 범위",))
    return qc.question_card("시장도 같은 쪽인가?", ans, th, ink, lines, tip=tip), ans


def q_now(st, kind, iran, groups, sides48, asof):
    """`지금은` = 다른 질문 카드와 같은 접는 강조 카드, 줄 = 왼쪽 구분 · 오른쪽 값 (2026-11-13 사용자: 강조 카드처럼 좌 구분명 · 우 값, 접는 방향)."""
    th, ink = ("uncertain", VIOLET) if kind in ("uncertain", "area") else ("neutral", "#111")
    n48, base = iran["n48"], iran["base48"]
    lines = [("row", "뉴스", f"48시간 {n48}건", f"평소 {base:.0f}건" if base is not None else "")]
    for g, w, ok, n, rs in groups:
        rev = sum(r["sg"] * r["z"] <= -Z_SOME for r in rs)
        lines.append(("row", g, w, f"{n}개 중 {rev}개 반대 방향" if "반대" in w else f"{n}개 중 {ok}개 {W()} 방향"))
    lines.append((f'<div style="display:flex;align-items:flex-start;gap:4px;margin:4px 0 0;font-size:13px;line-height:19px;color:{dk.SUB};word-break:keep-all;">'
                  f'<span style="flex:none;display:flex;align-items:center;height:19px;">{H.EXCL_ICON}</span><span>{dk.esc(asof)} 기준입니다.</span></div>', "html"))   # P543 — 안내는 행이 아니라 느낌표 + 작은 회색
    tip = ("뉴스 = 이 이슈 기사 수가 평소의 2배 · 3건 넘으면 `뉴스 늘어남`.\n"
           f"시장 = {W()}되면 움직인다고 흔히 설명하는 지표를 묶음별로 — 묶음 안 2개 이상이 그 방향으로 평소보다 크게(하나는 2배 넘게) 움직이면 `움직이는 중`.\n"
           "예측이 아니라 지금까지 일어난 일입니다.")
    return qc.question_card("지금은", short(st), th, ink, lines, tip=tip)


STAGE_RAW = {}   # 차례 규칙 전 가장 높은 단계 — 운영자 상자용


def _stage_hits(evs, side):
    hit = {}
    for e in evs:
        st = stage_of(e) if e["side"] == side else None
        if st is not None and (st not in hit or e["first"] > hit[st]["first"]):
            hit[st] = e
    return hit


def _reach(hit):
    """단계는 차례대로만 오른다 — 아래 단계가 없으면 위 단계는 세지 않는다 (2026-11-14: 합의 없이 `LNG 운반선 통항` 하나로 `이행` 에 올랐다)."""
    r = -1
    while r + 1 in hit:
        r += 1
    return r if r >= 0 else None


def _ladder(side, reach, hit):
    """쪽마다 한 줄 진행 막대 — 칸 = 단계, 오른 칸까지 색, 아래 단계 이름. 그 아래 도달한 단계의 가장 최근 일.
    막대 = 줄 막대 꼴(가이드라인 9절: 높이 10 · 모서리 3 · 빈 칸 #F1F5F9 · 부호 있는 값 = 연빨강 · 연파랑 dk.BAR_PASTEL), 단계 이름 = 가로축 이름 13 (2026-11-14 사용자)."""
    lad = C["stages"][side]
    col = dk.BAR_PASTEL["positive" if side == "종전" else "negative"][0]
    ink = dk.UP if side == "종전" else dk.DOWN
    segs = ""
    for i, (nm, _) in enumerate(lad):
        on = reach is not None and i <= reach
        segs += (f'<span style="flex:1 1 0;min-width:0;display:flex;flex-direction:column;gap:6px;">'
                 f'<span style="height:10px;border-radius:3px;background:{col if on else "#F1F5F9"};"></span>'
                 f'<span style="font-size:{dk.AXIS_FS};line-height:20px;text-align:center;word-break:keep-all;color:{"#111" if on else dk.NOTE};font-weight:{700 if on and i == reach else 400};">{dk.esc(nm)}</span></span>')
    where = f"‘{lad[reach][0]}’ 단계까지" if reach is not None else "아직 단계에 오른 일이 없습니다"
    head = (f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin:0 0 8px;font-size:{dk.NAME};line-height:{dk.LH_CARD};color:#111;">'
            f'<b style="flex:none;color:{ink};">{dk.esc(SIDE_LABEL[side])}</b><span style="text-align:right;word-break:keep-all;">{dk.esc(where)}</span></span>')   # `‘협상 제안’ 단계까지` = 오른쪽 정렬 (2026-11-14 사용자)
    e = hit.get(reach) if reach is not None else None
    last = (f'<span style="display:block;margin:6px 0 0;font-size:{dk.TINY};line-height:20px;color:{dk.SUB};word-break:keep-all;">'
            f'<b style="font-weight:600;color:#333;">{H.md(e["first"].astimezone(KST).date().isoformat())}</b> {dk.esc(e["title"])}</span>') if e else ""
    return head + f'<span style="display:flex;gap:2px;">{segs}</span>' + last


def q_stage(evs):
    """종전 · 확전, 실제로 어디까지 갔나? — 최근 2주 사건을 쪽마다 단계 사다리에 놓고 한 줄 진행 막대로 (2026-11-14 사용자: 1~6 줄 · `없음` 줄은 이해하기 어렵다).
    답 = 양쪽 다. 같은 일을 몇 곳이 옮겼는지 무관 · 발언 · 논의는 첫 단계로만 · 단계는 차례대로만."""
    g, b = C["good"], C["bad"]
    hits = {s: _stage_hits(evs, s) for s in ("종전", "확전")}
    reach = {s: _reach(hits[s]) for s in hits}
    STAGE_RAW.update({s: (max(hits[s]) if hits[s] else None) for s in hits})
    sh = lambda s: C["stages"][s][reach[s]][0].split(" · ")[0] if reach[s] is not None else "없음"   # noqa: E731
    ans = (f'<span style="display:inline-block;text-align:right;white-space:nowrap;">{dk.esc(g + " " + sh("종전"))}<br>{dk.esc(b + " " + sh("확전"))}</span>')   # 두 줄 (2026-11-14 사용자 "줄바꿈")
    word = lambda s: f"‘{C['stages'][s][reach[s]][0]}’ 단계까지" if reach[s] is not None else "아직 단계에 오른 일 없이"   # noqa: E731
    first = f"최근 2주 동안 {josa(g, ('은', '는'))} {word('종전')}, {josa(b, ('은', '는'))} {word('확전')} 갔습니다."
    cand = [(hits[s][i]["first"], s, i) for s in hits if reach[s] is not None for i in range(reach[s] + 1)]
    if cand:
        t, s, i = max(cand)
        first += f" 가장 최근은 {H.md(t.astimezone(KST).date().isoformat())} {SIDE_LABEL[s]} ‘{C['stages'][s][i][0]}’ 입니다."
    box = (_ttl("단계별 진행")   # 그래프 제목은 흰 카드 밖 (가이드라인 7-3) · 흰 카드 = 공용 꼴(MULTI · 양쪽 5 내밈 · 위 10 + 5 · 좌우 12 · 아래 10)
           + f'<span style="{dk.MULTI}margin:0 {dk.CHART_CARD_X}px;"><span style="display:block;padding:{dk.CHART_CARD_PAD + dk.LEGEND_TOP}px 12px {dk.CHART_CARD_PAD}px;">'
           + _ladder("종전", reach["종전"], hits["종전"])
           + '<span style="display:block;height:1px;background:#E2E8F0;margin:14px 0;"></span>'
           + _ladder("확전", reach["확전"], hits["확전"]) + '</span></span>')
    lines = [(first, "plain"), (box, "html"),
             ("같은 일을 여러 곳이 보도해도 한 번만 셉니다. 발언 · 논의는 첫 단계로만 셉니다. 단계는 차례대로만 오릅니다.", "note")]
    tip = ("단계 = 그 일이 실제로 어디까지 갔는지.\n아래 단계가 없으면 위 단계 소식이 있어도 세지 않습니다.\n"
           "막대 아래 = 도달한 단계의 가장 최근 일.\n기사 제목으로 나눈 것이라 틀릴 수 있습니다.")
    return qc.question_card(STAGE_Q[C["iss"]["id"]], ans, "neutral", "#111", lines, tip=tip, opened=True)


def q_stage_old(evs):
    """옛 사다리 줄 꼴 (2026-11-13) — 2026-11-14 q_stage 로 바뀜, 비교용으로 남김."""
    g, b = C["good"], C["bad"]
    reach, lines, latest = {}, [], None
    for side, lab in (("종전", g), ("확전", b)):
        ladder = C["stages"][side]
        hit = {}
        for e in evs:
            st = stage_of(e) if e["side"] == side else None
            if st is None:
                continue
            if st not in hit or e["first"] > hit[st]["first"]:
                hit[st] = e
            if latest is None or (e["first"], st) > (latest[0]["first"], latest[1]):
                latest = (e, st, side)
        reach[side] = max(hit) if hit else None
        ink = dk.UP if side == "종전" else dk.DOWN
        lines.append(("row", _sp(f'<b style="color:{ink};">{dk.esc(lab)}</b>'), "", "", *(("gap",) if side == "확전" else ())))
        for i, (nm, _) in enumerate(ladder):
            e = hit.get(i)
            val = _sp(f'<span style="color:{ink if e else dk.SUB};font-weight:{700 if e else 400};">{H.md(e["first"].astimezone(KST).date().isoformat()) if e else "없음"}</span>')
            lines.append(("row", _sp(f'<span style="color:{"#111" if e else dk.SUB};">{i + 1}. {dk.esc(nm)}</span>'), val, e["title"] if e else "", "tight"))
    word = lambda side: f"‘{C['stages'][side][reach[side]][0]}’ 단계까지" if reach[side] is not None else "아직 단계에 오른 일이 없이"   # noqa: E731
    first = f"최근 2주 동안 {josa(g, ('은', '는'))} {word('종전')}, {josa(b, ('은', '는'))} {word('확전')} 일이 있었습니다."
    if latest:
        e, st, side = latest
        first += f" 가장 최근은 {H.md(e['first'].astimezone(KST).date().isoformat())} {SIDE_LABEL[side]} ‘{C['stages'][side][st][0]}’ 입니다."
    w = W()
    wk = "종전" if C["watch"] == g else "확전"
    ans = f"{w} · {C['stages'][wk][reach[wk]][0]}" if reach[wk] is not None else "아직 없음"
    lines = [(first, "plain")] + lines + [("같은 일을 여러 곳이 보도해도 한 번만 셉니다. 발언 · 논의는 첫 단계로만 셉니다.", "note")]
    tip = "단계 = 그 일이 실제로 어디까지 갔는지.\n날짜 = 그 단계의 가장 최근 일.\n기사 제목의 낱말로 나눈 것이라 틀릴 수 있습니다."
    return qc.question_card("사건은 어디까지 왔나?", ans, "neutral", "#111", lines, tip=tip, opened=True)


def _fork(t):
    for a, b in FORK_WORDS:
        t = t.replace(a, b)
    return re.sub(r"(\S+) 사슬로", r"\1 걱정으로 이어짐", t)   # 남은 `실적 사슬로` 등


def side_cases(px):
    """쪽마다 사건표 사례 (IF_SIDES) — 아래 접는 줄 · 수혜주 카드가 같이 쓴다."""
    cfg = IF_SIDES[C["iss"]["id"]]
    return {side: (cases(px, s["kinds"], s["inc"], s["exc"]) if s["kinds"] else []) for side, s in cfg.items()}


SEG_JS = ("<script>document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('[data-segbox] .rt-seg');if(!b)return;"
          "var w=b.closest('[data-segbox]');w.querySelectorAll(':scope>.rt-segs .rt-seg').forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});"
          "w.querySelectorAll(':scope>[data-segp]').forEach(function(p){p.hidden=p.dataset.segp!==b.dataset.seg;});});</script>")


def seg_tabs(panes):
    """카드 · 접는 줄 안 전환 버튼 — 테마 `.rt-segs` · `.rt-seg`(가이드라인 서브탭 · 전환 버튼 19/25) 모양, 누르면 그 쪽 내용만 (2026-11-14 사용자: 종전되면 · 확전되면을 탭으로)."""
    if len(panes) == 1:   # 한 쪽뿐(수출 통제 = 완화 사례 없음)이면 버튼 하나는 그리지 않는다
        return panes[0][1]
    tone = lambda lab: "up" if lab.startswith(C["good"]) else "down"   # noqa: E731 — 탭 색은 순서가 아니라 쪽으로(확전이 앞서면 확전 탭이 첫째)
    btns = "".join(f'<button type="button" class="rt-seg" data-seg="{i}" data-tone="{tone(lab)}" aria-pressed="{"true" if i == 0 else "false"}">{dk.esc(lab)}</button>'
                   for i, (lab, _) in enumerate(panes))
    body = "".join(f'<div data-segp="{i}"{" hidden" if i else ""}>{html}</div>' for i, (_, html) in enumerate(panes))
    css = (_UL + _ULC).format(v=".post-body .iw-seg")   # E1 밑줄 탭 — 글자 폭 탭 + 오른쪽 끝까지 바닥선, 고른 쪽 색 글자 + 2px 색 밑줄 (2026-11-14 사용자 결정)
    return f'<style>{css}</style><div class="iw-seg" data-segbox="1"><div class="rt-segs" style="margin:0 0 10px {dk.ALIGN_PX}px;">{btns}</div>{body}</div>'


def _cnt(xs, verb):
    """`n번 중 k번 올랐고` — 표에 0.0% 로 보이는 날은 오른 날로 세지 않는다. 사례 하나면 그냥 `올랐고`."""
    k = sum(round(x, 1) > 0 for x in xs)
    neg = verb.replace("올랐", "오르지 않았").replace("올라 있었", "올라 있지 않았")
    if len(xs) == 1:
        return verb if k else neg
    return f"{len(xs)}번 모두 {verb}" if k == len(xs) else f"{len(xs)}번 중 한 번도 {neg}" if k == 0 else f"{len(xs)}번 중 {k}번 {verb}"


def if_fold(chain_id, scs):
    """종전되면 · 확전되면 주가는? — 원래 자리(아래쪽 접는 줄 묶음 = `과거 기록에서 비슷한 때는?` 자리)로 되돌리고 안은 전환 버튼 두 쪽 (2026-11-14 사용자).
    쪽마다: 첫 문장(S&P 500 그날 · 20거래일 뒤) → 흔한 설명 갈림 → 지난 사례 표 → 안내."""
    cfg = IF_SIDES[C["iss"]["id"]]
    base_side = "종전" if C["watch"] == C["good"] else "확전"   # CFG case_exp 가 재는 쪽
    panes = []
    for side in ("종전", "확전"):
        s, cs = cfg[side], scs[side]
        forks = CH.CHAINS[s["chain"]]["forks"] if s["chain"] else []
        lab = SIDE_LABEL[side]
        if not cs and not forks:
            continue
        v = [r["S&P 500"] for r in cs if r.get("S&P 500") and r["S&P 500"][0] is not None]
        v20 = [x[1] for x in v if x[1] is not None]
        lead = (f"지난 {lab} 사례에서 S&P 500 은 그날 " + _cnt([x[0] for x in v], "올랐고")
                + (", 20거래일 뒤에는 " + _cnt(v20, "올라 있었습니다") if v20 else "") + ".") if v else f"알파스코프 사건표에 {lab} 사례가 아직 없습니다."
        html = H._plain_rows(lead, [], lines=False)
        if forks:
            html += _ttl_plain("시장에서 흔히 하는 설명") + H._plain_rows("", [(_fork(a), "", _fork(c)) for a, c in forks])
        if cs:
            exp = CASE_EXP if side == base_side else {k: -x for k, x in CASE_EXP.items()}
            html += (_ttl_plain(f"지난 {lab} 때 실제로는") + f'<div style="padding:0 {dk.ALIGN_PX}px;">{cases_card(cs)}</div>'
                     + H._plain_rows("", [], note=s["note"] + case_gap(cs, exp)))
        panes.append((f"{lab}되면", html))
    if not panes:
        return ""
    note = H._plain_rows("", [], note="흔한 설명은 교과서 · 언론의 설명이고, 사례는 지난 기록입니다. 이번에 그대로 된다는 뜻은 아닙니다.")
    return H._fold_group(H._fold_row(f"과거 기록에서 {C['good']} · {C['bad']} 때 주가는?", seg_tabs(panes) + note)) + SEG_JS   # 과거 기록임을 제목에 (증시 전망 `과거 기록에서 비슷한 때는?` 과 같은 말, 2026-11-14 사용자)


def _ttl_plain(t):
    return f'<div style="margin:14px 0 4px;padding:0 {dk.ALIGN_PX}px;font-size:16px;line-height:24px;font-weight:700;color:#111;">※ {dk.esc(t)}</div>'


def _day_move(ser, day):
    """사건 날(미국 날짜) 이후 첫 거래일의 하루 등락 — 한국 종목은 미국 저녁 사건이 다음 날 반영되므로 그 시장의 첫 거래일로 (목업 근사)."""
    ser = ser.dropna()
    t = pd.Timestamp(day)
    i = ser.index.searchsorted(t)
    if i < 1 or i >= len(ser) or (ser.index[i] - t).days > 4:
        return None
    return (ser.iloc[i] / ser.iloc[i - 1] - 1) * 100


def _pp(v):
    return f'{"+" if v >= 0 else "−"}{abs(v):.1f}%p'


def _pp_html(v):
    """줄 값 = 시장 대비 %p — 증감 색 + 굵게 (arrow 와 같은 꼴, fix_colons 가 ▲ · ▼ 로)."""
    if round(v, 1) == 0:
        return '<span style="font-weight:700;white-space:nowrap;">0.0%p</span>'
    return f'<span style="color:{dk.UP if v > 0 else dk.DOWN};font-weight:700;white-space:nowrap;">{_pp(v)}</span>'


MCAP_CACHE = os.path.join(OUT, "_mcap_cache.json")   # 주도주 = 시가총액 1위 — 목업은 7일 캐시 (운영 = 상태 저장소, 주 1회)


def mcaps(syms):
    """야후 시가총액 (나라 안에서만 비교 — 원 · 달러 섞지 않는다)."""
    try:
        cache = json.load(open(MCAP_CACHE, encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    old = (dt.date.today() - dt.timedelta(days=7)).isoformat()
    todo = [s for s in syms if s not in cache or cache[s]["day"] < old]
    if todo:
        import yfinance as yf
        for s in todo:
            try:
                cache[s] = {"day": dt.date.today().isoformat(), "cap": float(yf.Ticker(s).fast_info["marketCap"] or 0)}
            except Exception as e:  # noqa: BLE001
                print(f"[mcap] {s} 못 받음: {type(e).__name__}")
        os.makedirs(OUT, exist_ok=True)
        json.dump(cache, open(MCAP_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return {s: cache.get(s, {}).get("cap", 0) for s in syms}


def _ex5(px, sym):
    """최근 5거래일 시장 대비 %p — 미국 = S&P 500 · 한국 = 코스피."""
    if sym not in px:
        return None
    s, m = px[sym].dropna(), px["^KS11" if sym.endswith(".KS") else "^GSPC"].dropna()
    if len(s) <= WIN or len(m) <= WIN:
        return None
    return (s.iloc[-1] / s.iloc[-WIN - 1] - 1) * 100 - (m.iloc[-1] / m.iloc[-WIN - 1] - 1) * 100


def _beat(px, sym, cs):
    """지난 같은 사례 그날 그 나라 시장보다 셌던 횟수 (n, k)."""
    s, m = px[sym].dropna(), px["^KS11" if sym.endswith(".KS") else "^GSPC"].dropna()
    n = k = 0
    for c in cs:
        r, rm = _day_move(s, c["day"]), _day_move(m, c["day"])
        if r is None or rm is None:
            continue
        n += 1
        k += round(r - rm, 1) > 0
    return n, k


LEADER_LOGO = 24   # 주도주 로고 20 → 24 (2026-11-14 사용자: 수혜주는 중요 — 왼쪽 이름 18(본문 19 보다 1 작게) · 로고 키움 · 종목 사이 구분선)
LEADER_PAD = 13    # 주도주 줄 · 테마 머리 아래 ~ 구분선 — 선 사이 종목 위아래 같게, 줄 전체가 종목 상세 링크라 누르기 쉽게 (26 + 26 = 52)
THEME_GAP = 20     # 테마 구획 사이 — 앞 구획 마지막 종목 아래 구분선 ~ 다음 테마 머리 20 (2026-11-14 사용자 `구분선 기준 20`)


# 가상 로고 (목업만) — 우리 로고 사본(ref/ticker_logos.json)이 아직 없는 종목. 발행 전 fetch_ticker_logos.py 로 실제 로고를 받는다 (2026-11-14 사용자: 회색 글자 배지 대신 로고처럼)
VIRTUAL_LOGO = {"AAL": ("#0078D2", "AA"), "272450.KS": ("#7AB800", "J"), "039130.KS": ("#5B2C83", "H"), "FLR": ("#0033A0", "F"),
                "079550.KS": ("#00468C", "LIG"), "FRO": ("#003A70", "F"), "CLF": ("#0A2240", "C")}
LOGO_ZOOM = {"003490.KS": 1.6}   # 그림이 원 안에 작게 든 로고 — 대한항공 태극이 지름의 57% 라 키워 꽉 채움 (2026-11-14 사용자)


def _logo(sym, nm):
    """주도주 이름 앞 로고 20 (2026-11-14 사용자: 나라 라벨 대신 티커 로고). 우리 gh-pages 로고가 없으면 dk 는 티커 두 글자 배지 —
    한국 종목은 숫자(`03`)가 되므로 이름 첫 글자 배지로."""
    sz = LEADER_LOGO
    if sym in VIRTUAL_LOGO and sym.upper() not in dk._logo_files():
        bg, t = VIRTUAL_LOGO[sym]
        fs = 12 if len(t) <= 1 else 10 if len(t) == 2 else 8
        return (f'<span aria-hidden="true" style="display:inline-block;flex:none;width:{sz}px;height:{sz}px;line-height:{sz}px;border-radius:50%;margin-right:8px;'
                f'background:{bg};color:#fff;font-size:{fs}px;font-weight:800;letter-spacing:-0.3px;text-align:center;">{dk.esc(t)}</span>')
    if sym in LOGO_ZOOM and sym.upper() in dk._logo_files():
        img = dk.ticker_logo(sym, sz).replace("vertical-align:-4px;", "").replace("margin-right:6px;", "").replace("border-radius:50%;", "", 1)
        img = img.replace("object-fit:cover;", f"object-fit:cover;transform:scale({LOGO_ZOOM[sym]});", 1)
        return f'<span style="display:inline-flex;flex:none;width:{sz}px;height:{sz}px;border-radius:50%;overflow:hidden;margin-right:8px;">{img}</span>'
    if sym.upper() in dk._logo_files() or not sym.endswith(".KS"):
        return dk.ticker_logo(sym, LEADER_LOGO).replace("vertical-align:-4px;", "").replace("margin-right:6px;", "margin-right:8px;")
    return (f'<span aria-hidden="true" style="display:inline-block;flex:none;width:{LEADER_LOGO}px;height:{LEADER_LOGO}px;line-height:{LEADER_LOGO}px;border-radius:50%;margin-right:8px;'
            f'background:#E2E8F0;color:#334155;font-size:12px;font-weight:700;text-align:center;">{dk.esc(nm[:1])}</span>')


def _good_red(html):
    """수혜주 카드 글자 속 좋은 쪽 말(종전 · 완화) = 빨강 (2026-11-14 사용자 "종전이라는 말은 다 빨간색") — 글자 마디만, 속성 · 툴팁은 그대로."""
    w = C["good"]
    red = lambda t: re.sub(r">([^<]*)<", lambda m: ">" + m.group(1).replace(w, f'<span style="color:{dk.UP};">{w}</span>') + "<", t)   # noqa: E731
    parts = re.split(r"(<button\b.*?</button>)", html, flags=re.S)   # 탭 버튼 글자는 탭 색을 따른다 (D 시안 — 고른 쪽 색 · 흰 글자)
    return "".join(p if p.startswith("<button") else red(p) for p in parts)


def _theme_block(th, first, oil5, last=False):
    """테마 한 묶음 — 머리 줄(테마 이름 굵게 · 오른쪽 테마 평균 시장 대비) + 회색 줄(경로 · 이유) + 주도주 줄(나라 라벨 · 이름 · 시장 대비 · 지난 사례)."""
    A = dk.ALIGN_PX
    path = th["path"]
    if path in OIL_PATH and oil5 is not None:
        same = (oil5 > 0) == (OIL_PATH[path] > 0)
        path += f" 경로 · 이번 주 유가 {_pct_html(oil5)}, " + ("같은 방향" if same else "반대 방향")
    else:
        path = dk.esc(path + " 경로")
    ic = dk.soft_icon(THEME_ICON[th["name"]]) if th["name"] in THEME_ICON else ""
    # 구획 = 테마 머리 → 구분선 → 종목 → 구분선 → 종목 (2026-11-14 사용자: 머리 아래에도 구분선, 선 사이 종목은 위아래 여백 같게 · 테마 구획 사이 20)
    line = f'<div style="height:0;margin:0 {A}px;border-top:1px solid #E2E8F0;"></div>'
    head = (f'<div style="padding:{14 - dk.VP if first else THEME_GAP}px {A}px {LEADER_PAD}px;">'
            f'<span style="display:flex;align-items:center;gap:6px;min-width:0;font-size:{dk.NAME};line-height:{dk.LH_CARD};"><b style="flex:none;color:#111;">{dk.esc(th["name"])}</b>'
            f'<span aria-hidden="true" style="flex:none;width:0;height:12px;margin:0 2px;border-left:1px solid #E2E8F0;"></span>'
            f'<span style="min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:{dk.TINY};color:{dk.SUB};">{dk.esc(THEME_WHY.get(th["name"], th["why"]))}</span>'
            '</span></div>')   # 이유 = 테마 이름 같은 줄, 앞에 세로 구분선 · 테마 증감은 삭제(손으로 고른 종목 평균이라 ETF 처럼 읽혔다)
    rows = ""
    for ld in th["leaders"]:
        rows += line + dk.stock_row_link(f'<span style="display:block;padding:{LEADER_PAD}px {A}px;">'
                 f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;font-size:16px;line-height:26px;">'
                 f'<span style="display:inline-flex;align-items:center;color:#111;min-width:0;font-size:18px;">{_logo(ld["sym"], ld["nm"])}<span>{dk.esc(ld["nm"])}</span></span>'
                 f'{_pp_html(ld["ex"])}</span></span>', ld["sym"])   # 줄 전체 = 종목 상세 페이지(가이드라인 10절 줄 전체 링크) · `지난 사례` 줄 삭제
    return head + rows + line + (f'<div style="height:{14 - dk.VP}px;"></div>' if last else "")   # 마지막 종목 아래도 구분선, 다음 구획 머리까지 = 선 기준 20 (2026-11-14 사용자)


def _pct_html(v):
    return (f'<span style="color:{dk.UP if v > 0 else dk.DOWN};font-weight:700;white-space:nowrap;">{"+" if v > 0 else "−"}{abs(v):.1f}%</span>'
            if round(v, 1) else '<span style="font-weight:700;">0.0%</span>')


def bene_card(px, scs):
    """종전되면 · 확전되면 수혜주는? — 테마 먼저(시장 대비 평균) → 테마마다 주도주(시가총액 1위, 미국 · 한국 하나씩) (2026-11-14 사용자 둘째).
    유가 경로 테마는 이번 주 유가 움직임과 맞대어 `이 쪽` · `반대 쪽`. 추천이 아니다."""
    lst = BENEFIT[C["iss"]["id"]]
    g, b = C["good"], C["bad"]
    cl = px["CL=F"].dropna() if "CL=F" in px else None
    oil5 = (cl.iloc[-1] / cl.iloc[-WIN - 1] - 1) * 100 if cl is not None and len(cl) > WIN else None
    caps = mcaps(sorted({s for side in lst.values() for th in side for lst2 in (th[3], th[4]) for _, s in lst2}))
    avg, panes = {}, []
    for side in ("종전", "확전"):
        lab = SIDE_LABEL[side]
        ths = []
        for name, path, why, us, kr in lst.get(side, []):
            exs = [e for e in (_ex5(px, s) for _, s in us + kr) if e is not None]
            leaders = []
            for mk, cands in (("미국", us), ("한국", kr)):
                cands = [(nm, s) for nm, s in cands if s in px and _ex5(px, s) is not None]
                if not cands:
                    continue
                nm, s = max(cands, key=lambda c: caps.get(c[1], 0))
                n, k = _beat(px, s, scs.get(side, []))
                leaders.append({"mk": mk, "nm": nm, "sym": s, "ex": _ex5(px, s), "n": n, "k": k})
            ths.append({"name": name, "path": path, "why": why, "avg": sum(exs) / len(exs) if exs else None, "n": len(exs), "leaders": leaders})
        vals = [t["avg"] for t in ths if t["avg"] is not None]
        if vals:
            avg[side] = sum(vals) / len(vals)
        if ths:
            ths.sort(key=lambda t: -t["avg"] if t["avg"] is not None else 1e9)   # 최근 일주일 시장 대비 가장 센 테마가 맨 위 (2026-11-14 사용자) — `n개 가운데 가장 셌던 것은 …` 문장은 삭제
            html = "".join(_theme_block(t, i == 0, oil5, i == len(ths) - 1) for i, t in enumerate(ths))
        else:
            html = H._plain_rows(BENEFIT_NONE if C["iss"]["id"] == "EXPORT" else f"{lab} 때 흔히 꼽는 수혜 테마가 뚜렷하지 않습니다.", [])
        panes.append((f"{lab}되면", html))
    if len(avg) == 2:
        d = avg["종전"] - avg["확전"]
        ans = "비슷함" if abs(d) < 1 else f"이번 주 {josa(g if d > 0 else b, ('이', '가'))} 앞섬"   # 2026-11-14 사용자 `이번 주 종전이 앞섬`
        th_, ink_ = ("neutral", "#111") if abs(d) < 1 else ("positive", dk.UP) if d > 0 else ("negative", dk.DOWN)   # 카드 색 = 앞선 쪽 색(종전 = 빨강 카드 · 확전 = 파랑) (2026-11-14 사용자)
        first = (f"최근 일주일 시장 대비로 {g} 수혜 테마는 평균 {_pp(avg['종전'])}, {b} 수혜 테마는 {_pp(avg['확전'])} 움직였습니다. "
                 + ("두 쪽이 비슷했습니다." if abs(d) < 1 else f"{g if d > 0 else b} 쪽 테마가 더 셌습니다."))
    elif avg:
        side = next(iter(avg))
        ans = f"{SIDE_LABEL[side]} 쪽 시장 대비 {_pp(avg[side])}"
        th_, ink_ = "neutral", "#111"
        first = f"최근 일주일 {SIDE_LABEL[side]} 수혜 테마는 시장보다 평균 {_pp(avg[side])} 움직였습니다."
    else:
        return ""
    if oil5 is not None and C["iss"]["id"] == "IRAN":
        first += f" 같은 기간 유가(WTI)는 {_pp(oil5).replace('%p', '%')}입니다."
    if len(avg) == 2 and avg["확전"] - avg["종전"] >= 1:   # 이번 주 앞선 쪽 탭이 첫째 — 확전이 앞서면 `확전되면` 이 앞 · 처음 열림 (2026-11-14 사용자)
        panes = panes[::-1]
    lines = [(first, "plain"), (seg_tabs(panes) + SEG_JS, "html")]   # 카드 끝 `알파스코프의 추천이 아닙니다` 줄 삭제 — 면책은 블로그 공통 푸터 하나(꼬리말 금지), 툴팁엔 남김 (2026-11-14)
    tip = ("수혜 테마 = 그 일이 생기면 좋아진다고 시장에서 흔히 꼽는 테마(교과서 · 언론), 알파스코프의 주장 · 추천이 아님.\n"
           "주도주 = 테마 안 시가총액 1위, 미국 · 한국 하나씩. 오른쪽 = 최근 5거래일 그 나라 시장 대비(미국 = S&P 500 · 한국 = 코스피).")   # 테마 평균 · 셌던 때 줄 삭제 (2026-11-14 사용자)
    if th_ != "neutral":
        lab = g if th_ == "positive" else b
        ans = f'<span style="color:{ink_};">{dk.esc(ans).replace(lab, f"<span>{lab}</span>")}</span>'
    row_line = dk.darken(dk.lighten(dk.lighten(qc.CARD_DIR[th_][1]), 0.3), 0.02)   # 테마 사이 구분선 = 그 카드 색의 줄 구분선(question_card bd_row 와 같은 셈) — 회색 #E2E8F0 아님 (2026-11-14 사용자)
    lines[1] = (lines[1][0].replace("border-top:1px solid #E2E8F0;", f"border-top:1px solid {row_line};").replace("border-left:1px solid #E2E8F0;", f"border-left:1px solid {row_line};"), "html")
    return _good_red(qc.question_card("수혜주는?", ans, th_, ink_, lines, tip=tip))   # 옛 `종전되면 · 확전되면 수혜주는?` (2026-11-14 사용자: "그냥 수혜주는")


def q_related(today_rows, r2w):
    """관련 뉴스 = 접는 강조 카드 안 방향 막대 (오늘 · 최근 2주). 타임라인은 카드 아래 그대로."""
    return qc.question_card("관련 뉴스", f"오늘 {len(today_rows)}건", "neutral", "#111", [(side_bars(today_rows, r2w), "html")])


def q_if(chain_id, cs):
    ch = CH.CHAINS[chain_id]
    lines = [("row", a, "", b.replace("전쟁 사슬로 돌아감", "유가 오름 · 위험 회피로 돌아감")) for a, b in ch["forks"]]
    lines += [(_ttl("지난 휴전 · 종전 때 실제로는") + cases_card(cs), "html"),
              ("3번뿐이라 ‘보통 이렇다’고 말할 수는 없습니다. 03.31 과 04.08 은 20거래일이 겹칩니다. 04.08 휴전 뒤 전쟁은 다시 이어졌습니다(10월 해협 공격 · 11.07 타격)." + case_gap(cs), "note")]
    tip = ("갈림 = 시장에서 흔히 쓰는 설명(교과서 · 언론), 우리 주장이 아님.\n"
           "사례 = 알파스코프 사건표의 `휴전 · 종전` 날, 그날 종가와 20거래일 뒤 종가를 전날 종가와 비교\n"
           "한국 (EWY) = 미국에 상장된 한국 증시 ETF, 미국 장 시간에 같이 잴 수 있어서")
    return qc.question_card("이렇게 되면?", f"지난 사례 {len(cs)}번", "neutral", "#111", lines, tip=tip)


def bottom(chain_id, cs):
    """증시 전망 페이지 아래쪽과 같은 접는 줄 묶음 + 안내 글 (2026-11-13 사용자: `이렇게 되면?` = 과거 기록, `증시 전망으로 넘어가나?` = 안내 글)."""
    ch = CH.CHAINS[chain_id]
    forks = H._plain_rows("시장에서 흔히 쓰는 설명입니다. 알파스코프의 주장은 아닙니다.",
                          [(a, "", b.replace("전쟁 사슬로 돌아감", "유가 오름 · 위험 회피로 돌아감")) for a, b in ch["forks"]])
    past = (H._plain_rows(f"알파스코프 사건표의 {C['case_name']} 날 {len(cs)}번입니다. 그날 종가와 20거래일 뒤 종가를 전날 종가와 비교했습니다.", [])
            + f'<div style="padding:0 {dk.ALIGN_PX}px;">{cases_card(cs)}</div>'
            + H._plain_rows("", [], note=C["case_note"] + case_gap(cs))) if cs else ""
    grp = ""   # 접는 줄 둘은 `종전되면 · 확전되면 주가는?` 카드로 올림 (2026-11-14) — forks · past 는 비교용으로 계산만
    note = C["bridge"]
    return grp + (f'<div data-why-note="1" style="display:flex;align-items:flex-start;gap:4px;margin:12px 0 0;padding:0 {dk.ALIGN_PX}px;font-size:13px;line-height:19px;color:{dk.SUB};word-break:keep-all;">'
                  f'<span style="flex:none;display:flex;align-items:center;height:19px;">{H.EXCL_ICON}</span><span>{dk.esc(note)}</span></div>')


def bridge_now(px):
    """운영자 상자용 — 최근 10거래일 에너지 vs S&P 500 가장 큰 날 (독자 화면에서는 뺐다)."""
    e, s = px[LINK_SYM.get(C["bridge_sym"], C["bridge_sym"])].dropna(), px["^GSPC"].dropna()
    idx = e.index.intersection(s.index)
    rel = (e.reindex(idx).pct_change() - s.reindex(idx).pct_change()) * 100
    sd = rel.rolling(60, min_periods=48).std().shift(1)
    z = (rel / sd).iloc[-10:]
    j = z.abs().idxmax()
    return f'{j:%Y-%m-%d} {rel[j]:+.1f}%p ({abs(z[j]):.1f}σ){" — 기준 넘음" if abs(z[j]) >= 3 and abs(rel[j]) >= 2.5 else ""}'


def title_h2(iss):
    """증시 전망 질문 줄과 같은 꼴 — 저울 아이콘 + 질문, 아래 줄 오른쪽 `게시 : 11.13` (forecast_body 의 q)."""
    icon = f'<span style="display:flex;flex:none;align-items:center;height:1lh;">{H.scale_icon(24)}</span>'
    date = (f'<span style="display:flex;flex-wrap:wrap;justify-content:flex-end;align-items:center;gap:4px 10px;margin-top:29px;line-height:{dk.LH_TINY};">'
            f'<span style="display:flex;flex:none;flex-wrap:wrap;align-items:center;gap:4px 10px;font-size:{dk.TINY};font-weight:400;color:{dk.SUB};">'
            f'<span style="white-space:nowrap;">게시 : <span style="color:#111;">{H.md(iss["since"])}</span></span></span></span>')
    return (f'<h2 style="{dk.H2}display:flex;flex-wrap:nowrap;align-items:flex-start;gap:8px;margin:26px 0 11px;">' + icon
            + f'<span style="flex:1 1 auto;min-width:0;display:flex;flex-direction:column;"><span style="word-break:keep-all;">{dk.esc(iss["q"])}</span>{date}</span></h2>')


def build():
    """이슈 셋을 차례로 그린다 — {파일 이름: 본문}."""
    items = SB.load_news()
    now = dt.datetime.now(dt.timezone.utc)
    today = now.astimezone(KST).date()
    days = [(today - dt.timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    gdays = [(today - dt.timedelta(days=i)).isoformat() for i in range(41, -1, -1)]   # 평소 = 직전 28일 → 지난 2주 상태까지 거슬러 세려면 42일
    px = prices()

    watch = []
    for iss in ISSUES:   # 먼저 셋 다 상태를 센다 — 맨 위 목록에 같이 쓴다
        use(iss)
        gn, capped = gnews(iss, gdays)
        rows = merge_rows(news_rows(items, iss["pat"]), news_rows(gn, iss["pat"]))
        n48, base, hot = news_level(rows, now)
        links = link_rows(px, iss["chain"])
        groups = group_state(links)
        st, kind = state_of(n48, base, groups)
        watch.append({**iss, "rows": rows, "n48": n48, "base48": base, "hot": hot, "capped": capped, "links": links, "groups": groups,
                      "state": st, "kind": kind, "short": short(st),
                      "n_store": sum(not r["gn"] for r in rows), "n_gn": sum(r["gn"] for r in rows)})
    sums = pop_lines()
    pages, logs = {}, {}
    for cur in watch:
        use(cur)
        pages[C["slug"] if PUBLIC else C["file"]] = page(cur, watch, items, px, now, today, days, sums, logs)
        logs[cur["id"]] = {"day": today.isoformat(), "made": now.isoformat(), "rules": RULES, "state": cur["state"], "align": cur.get("align"), "n48": cur["n48"],
                           "base48": cur["base48"], "hot": cur["hot"], "groups": {g: w for g, w, *_ in cur["groups"]},
                           "gauge": _zone_word(ev_net(events([r for r in cur["rows"] if r["t"].astimezone(KST).date() >= today - dt.timedelta(days=GAUGE_DAYS - 1)]))),
                           "history": logs.get(cur["id"])}
    if not PUBLIC:
        json.dump({"rules": RULES, "made": now.isoformat(), "issues": logs}, open(os.path.join(OUT, "issue_state_log.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    build.logs = logs   # 운영 = issue_watch_daily 가 상태 저장소 records/issues/{ID}.jsonl 에 하루 한 줄(같은 날 다시 돌면 바꿔 씀)
    return pages


def page(cur, watch, items, px, now, today, days, sums, logs):
    links, groups, st, kind = cur["links"], cur["groups"], cur["state"], cur["kind"]
    hist = history(px, cur["chain"], cur["rows"])
    logs[cur["id"]] = hist
    counts = counts_24h(cur["rows"], now)   # 지금에서 24시간씩 — 마지막 점도 꽉 찬 24시간 (2026-11-14 사용자: 오늘 0시가 뚝 떨어짐)
    NOW_LABEL[0] = f"지금 {now.astimezone(KST):%H}시"
    chart_gr, chart_line = oil_chart(px) if C["chart"] is None else year_chart(px, *C["chart"])
    cs = cases(px, cur["cases"])

    top = ""   # 맨 위 안내 문장 · 이슈 목록 삭제 — 이슈마다 따로 페이지, 제목이 바로 머리 줄 아래 (2026-11-13 사용자, 증시 전망 질문 줄과 같은 자리)

    q = title_h2(cur)
    r48 = [r for r in cur["rows"] if now - r["t"] <= dt.timedelta(hours=48)]
    asof = f'시장 {H.md(links[0]["d1"].strftime("%Y-%m-%d"))} 종가 · 뉴스 {H.md(today.isoformat())} {now.astimezone(KST):%H}시까지'
    r14 = [r for r in cur["rows"] if r["t"].astimezone(KST).date().isoformat() >= days[0]]
    evs = sorted(events(r14), key=lambda e: e["first"], reverse=True)   # 최근 2주 사건 — 바늘 · 어디까지 왔나 · 막대 · 타임라인이 같이 쓴다
    n_ai = ai_judge(evs, today)   # AI 판정(하루 한 번)이 붙은 사건 수 — 없는 사건은 글자 패턴
    gauge = gauge_card(evs, today)
    links5 = link_rows(px, cur["chain"], n=WIN)
    gs5 = group_side(links5)
    c_align, align = q_align(gauge_word(evs, today), links5, gs5, chart_gr, chart_line, hist, asof)
    cur["align"] = align

    c_news, r2w = q_news(cur, counts, days, r48)
    today_evs = [e for e in evs if e["first"].astimezone(KST).date() == today]
    # 순서 = 독자 질문 순 (2026-11-14 사용자) — 바늘 → 시장도 같은 쪽? → 어디까지 갔나? → 되면 수혜주는? · `되면 주가는?` 은 아래 접는 줄
    scs = side_cases(px)
    bene = bene_card(px, scs)
    BENE_HTML[cur["id"]] = bene   # 탭 모양 시안 페이지(seg_variants)가 같은 카드를 쓴다
    qcards = f'<div style="margin:0 0 8px;">{c_align + q_stage(evs) + bene}</div>'   # 수혜주 카드 = 단계 카드 아래 (2026-11-14 사용자)

    sec_list = (dk.section("관련 뉴스", c_news + side_bars(today_evs, evs), line=False)   # `얼마나 화제인가?` = 방향이 아닌 관심의 크기 → 위 방향 카드들 사이에서 뉴스 구획으로
                + f'<div style="margin:0 0 24px;padding:0 0 {TL_BOTTOM}px;">{news_timeline(evs, days[::-1], px)}</div>')   # 아래 +5 = padding — margin 은 아래 접는 줄 묶음 위 28 과 겹쳐(collapse) 늘지 않았다 (2026-11-13 사용자)

    op_rows = [
        ("규칙", RULES), ("모으기", f"키워드 /{cur['pat']}/ — 공용 뉴스(CNBC 8일 보관) {cur['n_store']}건 + 구글 뉴스 한국어(하루씩, 42일) {cur['n_gn']}건, 겹침 제거. 100건 상한 닿은 날 {', '.join(sorted(cur['capped'])) or '없음'}"),
        ("지난 2주", "목업 = 오늘 가진 가격 · 뉴스로 거슬러 셈. 운영 = 날마다 그날 값을 기록(issue_state_log.json → 상태 브랜치)"),
        ("방향 · 단계", f"목업 = 글 패턴(CFG[{cur['id']}].side_pat · TALK). 운영 땐 공용 뉴스 처리 Groq 칸으로 옮길지 결정"),
        ("시장 지표", f"사슬 {cur['chain']} 고리 = {W()} 쪽 부호 · " + " / ".join(f"{g}: {', '.join(k)}" for g, k in GROUPS) + (f" · 뺀 고리 {', '.join(C['skip'])}" if C["skip"] else "")),
        ("AI 판정", f"사건 {len(evs)}개 중 {n_ai}개 (사슬 {AI_CHAIN}, 묶음 {AI_BATCH} · 실행당 {AI_MAX_CALLS}회, 이번 실행 호출 {_AI['calls']}회 {dict(_AI['model'])}). 나머지 = 글자 패턴"),
        ("묶기", f"기사 {len(r2w)}건 → 사건 {len(evs)}개 (제목 글자 둘씩 겹침 {EV_SIM} · {EV_HOURS}시간 안, 사건 날짜 = 첫 보도 날). AI 0"),
        ("팝업 한 곳만", "한 곳만 보도한 사건은 one_pick(따옴표 발언 아닌 사건 낱말 ONE_HARD, 또는 통신사 ONE_WIRE)만 올림. 나머지는 팝업에 없음"),
        ("상태 규칙", f"뉴스 늘어남 = 48시간 ≥ 3 · 평소 2배 / 시장 = 묶음 안 2개 이상(지표 하나뿐인 묶음은 1개) {W()} 방향 1σ, 하나는 2σ"),
        ("전망 기준(최근 10거래일 최대)", f"{C['bridge_sym']} vs S&P 500 " + bridge_now(px)),
        ("사례", f"사건표 {', '.join(cur['cases'])}" + (f" · 제목 /{C['case_re']}/" if C.get("case_re") else "") + f" → {len(cs)}건"),
        ("단계 차례 규칙", f"차례 규칙 전 가장 높은 단계 = 종전 {STAGE_RAW.get('종전')} · 확전 {STAGE_RAW.get('확전')} (0부터) — 화면은 빈 단계에서 멈춤"),
        ("시장 기간", f"독자 카드 = {WIN}거래일 ({links5[0]['d0']:%m-%d} → {links5[0]['d1']:%m-%d}) · 10거래일 판정(옛) = {short(st)}"),
    ]
    if cur["id"] == "IRAN":
        op_rows += [
            ("11-02 ~ 11-04 빈칸", "수집 버그 아님 — 공용 뉴스는 CNBC 만 · 8일 보관(STORE_DAYS 8). 이 페이지는 자기 기록을 따로 쌓는다"),
            ("코스피", "최근 10거래일 줄만 ^KS11 (미국 마지막 날까지). 사건표는 미국 장 같은 시간이라 EWY 유지"),
            ("standby 정규식", f"CEASEFIRE 48시간 {sum(SB.topic_of(x) == 'CEASEFIRE' for x in items)}건 — 이 페이지 키워드 묶음보다 적게 잡힘"),
            ("검증 3-a", "전쟁 · 테러 사건 전 신호 1.12배(7건) · GPR 0.84~1.17 — 화면에 ‘포착’ 단언 금지"),
            ("놓친 등록", "11-04 유가 −8.3% · XLE vs S&P −6.3%p 3.9σ = 틀 R 기준 넘음. 자동 등록(11-11~) 전이라 미등록. 거슬러 등록하지 않음"),
        ]
    op = "" if PUBLIC else H.operator_box(op_rows)
    body = (top + q + gauge + qcards + sec_list + op + if_fold(cur["chain"], scs) + bottom(cur["chain"], cs) + (H.RELATED if PUBLIC else ""))   # `주가는?` = 원래 아래 접는 줄 자리 (2026-11-14 사용자)
    body = body.replace('data-cards="1" ', "")   # data-cards 는 테마(엔비디아 탭) JS 가 글 머리로 옮긴다 — 이 페이지 카드는 제자리에
    return dk.fix_colons(f'<div data-head-title="{HEAD_TITLE}" data-seo-lead="{dk.esc(HEAD_TITLE + " — " + cur["q"] + " 뉴스와 시장 " + align)}">{body}</div>')


BENE_HTML = {}
# 2026-11-14 사용자 둘째: "탭은 D 로, D 에서 더 세부 시안 — 종전되면 내용을 흰 카드(강조 카드 안 그래프 흰 카드)에 넣고 그 위에서 탭 모양 여러 가지".
# 공통 = 고른 쪽 색이 바뀌는 탭(종전 연빨강 · 확전 연파랑) + 내용 = 흰 카드(흰 바탕 · 모서리 8 · 양쪽 5 내밈 · 테두리 EMPH_WHITE_BD, 안 줄 선 #E2E8F0).
_RED, _BLUE = ("#FEF2F2", "#FCA5A5", "#B91C1C"), ("#EFF6FF", "#93C5FD", "#1D4ED8")   # 바탕 · 테두리 · 글자 = 외곽선 라벨 긍정 · 부정 색 (8절)
_WC = ("{v} [data-segp]{{background:#fff;border:1px solid " + dk.EMPH_WHITE_BD + ";border-radius:8px;margin:0 " + str(dk.CHART_CARD_X) + "px;padding:4px 6px 0}}"
       "{v} [data-segp] [style*='border-top:1px solid']{{border-top-color:#E2E8F0!important}}"
       "{v} .rt-segs{{margin-left:0!important;margin-right:0!important}}")
_SEL = ("{v} .rt-seg[data-tone='up'][aria-pressed=true]{{background:" + _RED[0] + "!important;border-color:" + _RED[1] + "!important;color:" + _RED[2] + "!important}}"
        "{v} .rt-seg[data-tone='down'][aria-pressed=true]{{background:" + _BLUE[0] + "!important;border-color:" + _BLUE[1] + "!important;color:" + _BLUE[2] + "!important}}")
_BTN2 = ("{v} .rt-segs{{display:flex!important;gap:6px!important;padding:0!important;background:none!important;margin-bottom:8px!important}}"
         "{v} .rt-seg{{flex:1 1 0;border:1px solid #E2E8F0!important;background:#fff!important;border-radius:8px!important;box-shadow:none!important}}")
# 2026-11-14 사용자 셋째: 지금 페이지(수혜주 구분선 구획) 기준으로 다시 — 본 페이지엔 D1(양쪽 색 두 칸 버튼) 우선 적용,
# 시안 = `탭 오른쪽 아래로 구분선이 이어지는` 밑줄 탭 여러 가지(E). 흰 카드 없음.
_LINE = "rgba(15,23,42,.10)"   # 탭 바닥선 — 색 카드 위에서도 보이는 옅은 선
_UL = ("{v} .rt-segs{{display:flex!important;gap:20px!important;padding:0 " + str(dk.ALIGN_PX) + "px!important;margin:0 0 12px!important;background:none!important;border-radius:0!important;border-bottom:1px solid " + _LINE + "}}"
       "{v} .rt-seg{{padding:8px 2px 9px!important;border-radius:0!important;background:none!important;box-shadow:none!important;margin-bottom:-1px;border-bottom:2px solid transparent!important}}")
_ULC = ("{v} .rt-seg[data-tone='up'][aria-pressed=true]{{color:" + _RED[2] + "!important;border-bottom-color:" + _RED[2] + "!important}}"
        "{v} .rt-seg[data-tone='down'][aria-pressed=true]{{color:" + _BLUE[2] + "!important;border-bottom-color:" + _BLUE[2] + "!important}}")
SEG_VARIANTS = [   # (열쇠, 이름, 설명, CSS 틀 — {v} = 시안 칸)
    ("D1", "D1. 양쪽 색 두 칸 버튼 (지금 페이지에 적용)", "고른 쪽 = 연빨강(종전) · 연파랑(확전) 바탕 + 테두리 + 색 글자. 비교 기준.", _BTN2 + _SEL),
    ("E1", "E1. 밑줄 탭 — 기본", "글자 폭 탭 두 개를 왼쪽에 두고, 바닥 1px 선이 오른쪽 끝까지 이어진다. 고른 쪽 = 색 글자 + 2px 색 밑줄.", _UL + _ULC),
    ("E2", "E2. 밑줄 탭 — 굵은 밑줄", "E1 과 같고 밑줄만 3px · 탭 사이 28. 고른 쪽이 더 또렷하다.",
     _UL + _ULC + "{v} .rt-segs{{gap:28px!important}}{v} .rt-seg{{border-bottom-width:3px!important;padding-bottom:8px!important}}"),
    ("E3", "E3. 밑줄 탭 — 고른 탭 연한 바탕", "고른 탭에 위 모서리 둥근 연빨강 · 연파랑 바탕을 깔고 밑줄. 버튼 느낌이 조금 남는다.",
     _UL + _ULC + "{v} .rt-segs{{gap:4px!important}}{v} .rt-seg{{padding:8px 14px 9px!important;border-radius:8px 8px 0 0!important}}"
     "{v} .rt-seg[data-tone='up'][aria-pressed=true]{{background:" + _RED[0] + "!important}}{v} .rt-seg[data-tone='down'][aria-pressed=true]{{background:" + _BLUE[0] + "!important}}"),
    ("E4", "E4. 폴더 탭 — 고른 탭만 테두리, 바닥선이 그 아래서 끊김",
     "고른 탭 = 위 · 양옆 색 테두리 + 흰 바탕, 그 아래만 바닥선이 비어 내용과 이어진다. 오른쪽으로는 바닥선이 끝까지.",
     _UL + "{v} .rt-segs{{gap:4px!important}}{v} .rt-seg{{padding:8px 16px 9px!important;border:1px solid transparent!important;border-bottom:0!important;border-radius:8px 8px 0 0!important;margin-bottom:-1px}}"
     "{v} .rt-seg[aria-pressed=true]{{background:#fff!important;padding-bottom:10px!important}}"
     "{v} .rt-seg[data-tone='up'][aria-pressed=true]{{border-color:" + _RED[1] + "!important;color:" + _RED[2] + "!important}}"
     "{v} .rt-seg[data-tone='down'][aria-pressed=true]{{border-color:" + _BLUE[1] + "!important;color:" + _BLUE[2] + "!important}}"),
    ("E5", "E5. 바닥선도 고른 쪽 색", "E1 에 더해 오른쪽으로 이어지는 바닥선이 고른 쪽 연한 색(연빨강 · 연파랑)으로 바뀐다.",
     _UL + _ULC + "{v} [data-segbox]:has(.rt-seg[data-tone='up'][aria-pressed=true])>.rt-segs{{border-bottom-color:" + _RED[1] + "!important}}"
     "{v} [data-segbox]:has(.rt-seg[data-tone='down'][aria-pressed=true])>.rt-segs{{border-bottom-color:" + _BLUE[1] + "!important}}"),
    ("E6", "E6. 밑줄 탭 — 색 점", "E1 글자 앞에 쪽 색 점(8). 안 고른 쪽도 점 색은 연하게 남아 두 쪽 색이 늘 보인다.",
     _UL + _ULC + "{v} .rt-seg::before{{content:'';display:inline-block;width:8px;height:8px;border-radius:50%;margin:0 6px 2px 0;vertical-align:middle}}"
     "{v} .rt-seg[data-tone='up']::before{{background:" + _RED[1] + "}}{v} .rt-seg[data-tone='down']::before{{background:" + _BLUE[1] + "}}"
     "{v} .rt-seg[data-tone='up'][aria-pressed=true]::before{{background:" + _RED[2] + "}}{v} .rt-seg[data-tone='down'][aria-pressed=true]::before{{background:" + _BLUE[2] + "}}"),
]


def seg_variants():
    """탭 모양 시안 — 실제 `수혜주는?` 카드(이란)를 시안마다 하나씩, 열린 채로. 버튼을 눌러 바뀌는 것까지 볼 수 있다."""
    card = BENE_HTML.get("IRAN", "")
    if not card:
        return ""
    card = card.replace('<details data-acc="1">', '<details data-acc="1" open>', 1)
    card = card.replace('class="iw-seg" ', '')   # 본 페이지 D1 스타일이 시안 CSS 를 덮지 않게
    out = ('<p style="margin:16px 6px 24px;font-size:14px;line-height:21px;color:#6B7280;">Hot Issue `수혜주는?` 카드 안 종전되면 · 확전되면 탭 모양 시안입니다. '
           '지금 페이지(D1 양쪽 색 두 칸 버튼)와 비교해, 탭 오른쪽으로 바닥선이 이어지는 밑줄 탭 E1~E6 을 그렸습니다. 버튼을 눌러 확전 쪽도 볼 수 있습니다.</p>')
    for k, nm, desc, css in SEG_VARIANTS:
        css = css.format(v=f".post-body .v{k}")
        out += (f'<style>{css}</style><h2 style="{dk.H2}margin:32px 0 4px;">{dk.esc(nm)}</h2>'
                f'<p style="margin:0 6px 12px;font-size:14px;line-height:21px;color:#6B7280;">{dk.esc(desc)}</p><div class="v{k}">{card}</div>')
    return out


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    AI_ON = os.environ.get("IW_AI") == "1"   # 목업에서 AI 판정까지 돌려 보기: IW_AI=1 (키 = .env)
    if AI_ON:
        try:
            from dotenv import load_dotenv
            load_dotenv(os.path.join(_HERE, "..", "..", ".env"))
        except ImportError:
            pass
    for fn, body in build().items():
        print(dk.write_mock(body, os.path.join(OUT, fn), HEAD_TITLE))
    if not PUBLIC:
        print(dk.write_mock(dk.fix_colons(f'<div data-head-title="탭 모양 시안">{seg_variants()}</div>'), os.path.join(OUT, "mock_seg_tabs.html"), "탭 모양 시안"))
