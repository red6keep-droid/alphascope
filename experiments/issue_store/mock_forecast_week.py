"""디자인 확인용 가상 목업 — 메타 급락 뒤 일주일 타임라인 · 날마다 근거 (2026-11-11 사용자). 기사 · 수치 · 신호 전부 지어낸 예시, 블로그에 나가지 않는다.
    python experiments/issue_store/mock_forecast_week.py   → output/mock_forecast-why-week.html (목업 서버 `증시 전망` 묶음)"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [HERE, EXP]
os.chdir(HERE)
import forecast_register as R
import hypo_pages as H
import design_kit as dk

w = [x for x in R.stocks() if x["sym"] == "META"][0]
why = {"issues": [("실적", 5)], "n": 14, "heads": [], "analyst": None, "signals": [], "window": ["2026-10-29", "2026-10-31"],
       "good": [{"t": "AMD, 메타에 10억 달러 투자", "day": "2026-10-31", "src": "Reuters", "stage": "done", "lv": 3},
                {"t": "메타, AI 광고 매출 32% 증가", "day": "2026-10-30", "src": "CNBC", "stage": "done", "lv": 3}],
       "bad": [{"t": "메타 950억 달러 신주 발행 검토", "day": "2026-10-31", "src": "Bloomberg", "stage": "talk", "lv": 3},
               {"t": "메타, 4분기 비용 전망 상향", "day": "2026-10-30", "src": "WSJ", "stage": "done", "lv": 3}],
       "open": [{"t": "메타, 유럽 디지털시장법 조사 결과 발표 예정", "day": "2026-10-31", "src": "FT", "stage": "talk", "lv": 3}],
       "count": {"good": 2, "bad": 2, "open": 1},
       "our_signals": {"as_of": "2026-10-30", "rows": [
           {"key": "tech", "name": "기술지표 방향", "state": "하락", "dir": -1, "hz": "단기"},
           {"key": "regime", "name": "미국 증시 분위기", "state": "상승 추세", "dir": 1, "hz": "단기"},
           {"key": "momentum", "name": "12개월 모멘텀", "state": "상위권", "dir": 1, "hz": "중기"},
           {"key": "ma", "name": "평균선 대비", "state": "평균 아래", "dir": -1, "hz": "중기"}]}}
reg, fc = R.build("EH-2026-903", w, "2026-10-31", "2026-10-30", "2026-10-29", -11.4, -5.2, 9, (6, 11), late=False, why=why)
b1, b2 = fc["scenarios"][0]["name"], fc["scenarios"][1]["name"]   # 메타 반등(+1) · 메타 하락 지속(−1)


def N(t, day, src, stage="done"):
    return {"t": t, "day": day, "src": src, "stage": stage, "lv": 3}


def W(day, good=(), bad=(), open_=(), changes=()):
    return {"day": day, "good": list(good), "bad": list(bad), "open": list(open_), "changes": list(changes),
            "count": {"good": len(good), "bad": len(bad), "open": len(open_)}}


E = H._entry
log = [
    E("2026-10-31", "start", "개시", 0, "10.30 급락 뒤 두 갈래를 적었습니다. 다음 거래일부터 봅니다.", 0.0),
    E("2026-11-03", "watch", "지켜보는 중", 0, "급락 날 종가보다 0.6%p 올랐습니다. 아직 어느 쪽으로도 기울지 않았습니다.", 0.6),
    E("2026-11-04", "lean", f"{b1} {H.LEAN}", 1, f"급락 폭의 30%(일부)를 회복했습니다. ‘{b1}’ 쪽으로 기울고 있습니다.", 3.4),
    E("2026-11-05", "watch", "지켜보는 중", 0, "급락 날 종가보다 1.4%p 올랐습니다. 아직 어느 쪽으로도 기울지 않았습니다.", 1.4),
    E("2026-11-06", "lean_x", f"{b2} {H.LEAN}", -1, f"급락 뒤 3.2%p 더 빠졌습니다. ‘{b2}’ 쪽으로 기울고 있습니다.", -3.2),
    E("2026-11-07", "lean_x", f"{b2} {H.LEAN}", -1, f"급락 뒤 4.0%p 더 빠졌습니다. ‘{b2}’ 쪽으로 기울고 있습니다.", -4.0),
    E("2026-11-10", "watch", "지켜보는 중", 0, "급락 날 종가보다 1.1%p 내렸습니다. 아직 어느 쪽으로도 기울지 않았습니다.", -1.1),
]
whys = {
    "2026-11-03": W("2026-11-03", good=[N("메타, 스레드 월간 이용자 4억 명 돌파", "2026-11-03", "The Verge")],
                    bad=[N("애널리스트, 메타 설비투자 부담 지적", "2026-11-03", "Barron's")]),
    "2026-11-04": W("2026-11-04", good=[N("메타, 엔비디아와 AI 칩 공급 계약 확대", "2026-11-04", "Reuters"),
                                        N("메타 목표가 올림 2곳", "2026-11-04", "")],
                    open_=[N("미국 법무부, 빅테크 광고 사업 조사 검토", "2026-11-04", "Bloomberg", "talk")],
                    changes=[{"name": "기술지표 방향", "from": "하락", "to": "중립", "dir": 0, "hz": "단기"}]),
    "2026-11-05": W("2026-11-05", good=[N("메타, 자사주 매입 300억 달러 추가 검토", "2026-11-05", "WSJ", "talk")],
                    bad=[N("유럽연합, 메타에 디지털시장법 위반 과징금 부과 논의", "2026-11-05", "FT", "talk"),
                         N("메타 광고 단가 3분기 연속 하락", "2026-11-05", "CNBC")]),
    "2026-11-06": W("2026-11-06", bad=[N("메타, 데이터센터 투자 계획 1,200억 달러로 확대", "2026-11-06", "Bloomberg"),
                                       N("메타 목표가 내림 3곳", "2026-11-06", ""),
                                       N("기관 투자자, 메타 지분 축소", "2026-11-06", "MarketWatch")],
                    changes=[{"name": "기술지표 방향", "from": "중립", "to": "하락", "dir": -1, "hz": "단기"},
                             {"name": "통신 서비스 업계 자금", "from": "모이는 중", "to": "빠져나가는 중", "dir": -1, "hz": "단기"}]),
    "2026-11-07": W("2026-11-07", bad=[N("메타, 950억 달러 신주 발행 일정 협의 중", "2026-11-07", "Reuters", "talk")],
                    good=[N("메타, 광고 신제품 사전 예약 2배", "2026-11-07", "Axios")]),
    "2026-11-10": W("2026-11-10", good=[N("메타, AI 비서 유료 구독 출시", "2026-11-10", "The Verge")],
                    bad=[N("메타 목표가 내림 1곳", "2026-11-10", "")],
                    open_=[N("미 의회, 소셜미디어 청소년 보호법 표결 일정 논의", "2026-11-10", "Politico", "talk")]),
}
for e in log:
    if e["day"] in whys:
        e["why"] = whys[e["day"]]
st = {"log": log, "quote": {"day": "2026-11-10", "close": 612.40, "chg": -1.32}}
out = os.path.join(HERE, "output", "mock_forecast-why-week.html")
print(dk.write_mock(H.forecast_body(reg, st, fc), out, H.CARD_NAME))
