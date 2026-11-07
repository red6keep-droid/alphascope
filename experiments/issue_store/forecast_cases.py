"""증시 전망 — 경우의 수 목업 (2026-11-07 사용자: "A 거시 · B 섹터 · C 개별 종목, 단일 · 겹침 · 맞음 · 틀림 · 이어가기까지 모든 시나리오를 탭으로").

    python experiments/issue_store/forecast_cases.py   → output/mock_forecast-cases.html (목업 서버 '증시 전망' 줄)

숫자는 전부 **가상**(시뮬레이션)이다. 페이지는 실제 렌더러(hypo_pages.forecast_body · list_body)와 판정 엔진(hypo_pages.judge)을 그대로 쓴다 —
목업에서 보이는 국면 · 판정 · 문장은 자동화 뒤 코드가 내놓을 그대로다. 탭 · 설명 상자는 목업 전용(블로그에 안 나간다).
"""
import json
import math
import re as _re
import os
import sys
from datetime import date, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import hypo_pages as H  # noqa: E402

dk = H.dk
HOL = {"2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18"}


def tdays(start, n):
    """start(포함)부터 거래일 n개."""
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5 and d.isoformat() not in HOL:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def path(keys, n, wig=0.0):
    """keys = [(거래일 번호, 값)] 사이를 곧게 잇고 작은 흔들림을 얹는다. 마지막 key 뒤는 None(아직 없는 날)."""
    out = []
    last = keys[-1][0]
    for i in range(n):
        if i > last:
            out.append(None)
            continue
        for (i0, v0), (i1, v1) in zip(keys, keys[1:]):
            if i0 <= i <= i1:
                v = v0 + (v1 - v0) * (i - i0) / max(1, i1 - i0)
                break
        else:
            v = keys[0][1]
        if 0 < i < last and all(i != k for k, _ in keys):
            v += wig * math.sin(i * 1.7)
        out.append(round(v, 2))
    return out


# ---------------------------------------------------------------- 대상 셋 (A 거시 · B 업종 · C 종목)
TIERS = {
    "A": {"name": "거시", "subject": "S&P 500", "subj_ga": "S&P 500 이", "subj_eun": "S&P 500 은", "cmp": None, "unit": "%", "line": 4.0,
          "ruler_short": "S&P 500 수익률", "event": "12.09 FOMC", "event_short": "FOMC", "event_day": "2026-12-09", "registered": "2026-12-04",
          "outcomes": ["금리 인하", "동결 · 인상"], "conds": ["금리 인하 시", "동결 · 인상 시"], "dirs": [1, -1], "market_prob": {"probs": [87, 13], "src": "CME FedWatch · Kalshi, 등록일"},
          "middle": ["돈 빌리는 비용이 낮아질 거란 기대", "돈 빌리는 비용 부담이 이어짐"], "tags": ["금리", "S&P 500"], "vix": True,
          "overlap": {"day": "12.18", "event": "반도체 급락", "no": 5, "title": "반도체 급락, 반등할까 더 빠질까?"}, "shock": -5.0,
          "what": "지수 전체(S&P 500)의 방향. 자 = 지수 자체의 수익률(절대), 금 = 20거래일 움직임 1σ ≈ 4%",
          "src": "사건 전 7일 방송 5곳 · 뉴스 31건에서 가장 많이 나온 설명",
          "hist_pre": {"what": "FOMC 가 금리를 내린 날이", "n": 47, "since": 1994, "rows": [["5거래일 뒤", 27, "−1.8 ~ +2.4%"], ["20거래일 뒤", 30, "−3.1 ~ +4.6%"], ["60거래일 뒤", 31, "−5.0 ~ +8.2%"]], "alike": [["2019.07", "10년 만의 보험성 인하", "+1.9%"], ["2024.09", "0.5%p 큰 폭 인하", "+2.4%"], ["2007.09", "금융위기 앞 첫 인하", "−1.2%"]]},
          "hist_after": {"what": "S&P 500 이 하루 3% 넘게 움직인 날이", "n": 212, "since": 1996, "rows": [["5거래일 뒤", 118, "−3.5 ~ +4.1%"], ["20거래일 뒤", 127, "−6.2 ~ +7.9%"], ["60거래일 뒤", 136, "−9.0 ~ +12.4%"]], "alike": [["2011.08", "미국 신용등급 강등", "+3.1%"], ["2024.08", "엔 캐리 청산", "+5.2%"], ["2018.02", "변동성 상품 붕괴", "+1.4%"]]}},
    "B": {"name": "업종", "subject": "반도체", "subj_ga": "반도체가", "subj_eun": "반도체는", "cmp": "시장보다", "unit": "%p", "line": 3.0,
          "ruler_short": "반도체 vs 시장", "beta": 1.5, "event": "11.17 엔비디아 실적", "event_short": "엔비디아 실적", "event_day": "2026-11-17", "registered": "2026-11-12",
          "outcomes": ["예상을 크게 넘음", "그 밖"], "conds": ["실적이 예상을 크게 넘으면", "그 밖이면"], "dirs": [1, -1], "market_prob": {"probs": [62, 38], "src": "지난 12번 실적 중 크게 넘은 횟수 · 예상치 상향 비율, 등록일"},
          "middle": ["AI 투자가 이어진다는 기대", "AI 투자 둔화 걱정"], "tags": ["실적", "반도체"], "vix": True,
          "overlap": {"day": "12.09", "event": "FOMC 금리 결정", "no": 4, "title": "FOMC 뒤 S&P 500 은?"}, "shock": -6.0,
          "what": "업종(반도체 지수)이 시장(S&P 500)보다 더 가나. 자 = 상대수익(%p), 금 = 3%p",
          "src": "사건 전 7일 방송 4곳 · 뉴스 23건에서 가장 많이 나온 설명",
          "hist_pre": {"what": "엔비디아 실적이 예상을 크게 넘은 날이", "n": 11, "since": 2016, "rows": [["5거래일 뒤", 7, "−1.5 ~ +3.0%p"], ["20거래일 뒤", 8, "−2.0 ~ +5.1%p"], ["60거래일 뒤", 8, "−3.4 ~ +8.8%p"]], "alike": [["2023.05", "AI 수요 첫 확인 실적", "+6.8%p"], ["2024.02", "데이터센터 매출 3배", "+4.1%p"], ["2024.08", "블랙웰 지연 우려 속 실적", "−2.3%p"]]},
          "hist_after": {"what": "반도체가 시장보다 하루 3%p 넘게 움직인 날이", "n": 96, "since": 1996, "rows": [["5거래일 뒤", 55, "−2.8 ~ +3.6%p"], ["20거래일 뒤", 56, "−5.1 ~ +6.0%p"], ["60거래일 뒤", 50, "−8.7 ~ +9.1%p"]], "alike": [["2024.07", "대중 수출 규제 강화 보도", "+2.2%p"], ["2022.10", "미국 첨단 반도체 수출 통제", "−3.9%p"], ["2018.10", "반도체 업황 고점 경고", "−1.7%p"]]}},
    "C": {"name": "개별 종목", "subject": "엔비디아", "subj_ga": "엔비디아가", "subj_eun": "엔비디아는", "cmp": "반도체 지수보다", "unit": "%p", "line": 6.0,
          "ruler_short": "엔비디아 vs 반도체", "beta": 1.4, "event": "11.17 엔비디아 실적", "event_short": "엔비디아 실적", "event_day": "2026-11-17", "registered": "2026-11-12", "line_src": "옵션 내재 예상 폭 ±6.8%(ATM IV, 11.12 nvda-state) → 정수 6%p. 옵션이 없으면 20거래일 1σ",
          "outcomes": ["예상을 크게 넘음", "그 밖"], "conds": ["실적이 예상을 크게 넘으면", "그 밖이면"], "dirs": [1, -1], "market_prob": {"probs": [62, 38], "src": "지난 12번 실적 중 크게 넘은 횟수 · 예상치 상향 비율, 등록일"},
          "middle": ["데이터센터 매출이 기대 이상", "데이터센터 매출이 기대 미달"], "tags": ["실적", "엔비디아"], "vix": False,
          "overlap": {"day": "12.09", "event": "FOMC 금리 결정", "no": 4, "title": "FOMC 뒤 S&P 500 은?"}, "shock": -12.0,
          "what": "종목(엔비디아)이 업종(반도체 지수)보다 더 가나. 자 = 상대수익(%p), 금 = 종목 20거래일 1σ ≈ 6%p",
          "src": "사건 전 7일 방송 4곳 · 뉴스 23건에서 가장 많이 나온 설명",
          "hist_pre": {"what": "엔비디아 실적이 예상을 크게 넘은 날이", "n": 11, "since": 2016, "rows": [["5거래일 뒤", 8, "−2.2 ~ +6.1%p"], ["20거래일 뒤", 8, "−3.5 ~ +9.0%p"], ["60거래일 뒤", 9, "−4.1 ~ +14.2%p"]], "alike": [["2023.05", "AI 수요 첫 확인 실적", "+11.2%p"], ["2024.02", "데이터센터 매출 3배", "+5.6%p"], ["2024.08", "블랙웰 지연 우려 속 실적", "−3.0%p"]]},
          "hist_after": {"what": "엔비디아가 반도체보다 하루 6%p 넘게 움직인 날이", "n": 38, "since": 2010, "rows": [["5거래일 뒤", 22, "−4.0 ~ +6.5%p"], ["20거래일 뒤", 23, "−7.2 ~ +9.8%p"], ["60거래일 뒤", 21, "−11 ~ +13%p"]]}},
}


def base_fc(t, no, kind, registered, start_text, title, dates, scenarios, T=None, **kw):
    T = T or TIERS[t]   # 돌발 · 묶음처럼 대상이 다른 경우는 T 를 넘긴다 (2026-11-07 고침: 전엔 TIERS[t] 만 써서 기준 · 이름이 어긋났다)
    fc = {"no": no, "slug": f"case-{t}-{no}", "kind": kind, "title": title, "subject": T["subject"], "subj_ga": T["subj_ga"], "cmp": T["cmp"],
          "unit": T["unit"], "line": T["line"], "ruler_short": T["ruler_short"], "registered": registered, "start_text": start_text,
          "posted": H.md(registered), "tags": T["tags"], "event": T["event"], "dates": dates, "scenarios": scenarios}
    fc.update(kw)
    return fc


def pre_fc(t, cond=None, follow=None, T=None):
    """틀 S — 사건 전 등록, 결과 두 갈래."""
    T = T or TIERS[t]
    L, u, ev = T["line"], T["unit"], T["event_day"]
    sc = []
    for k in (0, 1):
        d = T["dirs"][k]
        name = f'{T["subject"]} {H.DIR_WORD[d]}'
        if T["cmp"]:
            win = f'{T["subj_ga"]} {T["cmp"]} {L:g}{u} 넘게 더 {"오른다" if d > 0 else "빠진다"} ({H.md(ev)} 종가 기준)'
        else:
            win = f'{T["subj_ga"]} {H.md(ev)} 종가보다 {L:g}{u} 넘게 {"오른다" if d > 0 else "내린다"}'
        sc.append({"no": k + 1, "cond": T["conds"][k], "name": name, "dir": d,
                   "chain": [{"step": T["outcomes"][k], "state": "wait", "ev": "", "date": ""},
                             {"step": T["middle"][k], "state": "wait", "ev": T.get("src", "사건 전 7일 방송 4곳 · 뉴스 23건에서 가장 많이 나온 설명"), "date": ""},
                             {"step": name, "state": "wait", "ev": "", "date": ""}], "win": win})
    mp = T.get("market_prob")
    out = H.md(ev) + " " + T["outcomes"][cond - 1] if cond else "결과 전"
    if cond and mp:
        out += " · 예상대로" if mp["probs"][cond - 1] >= 50 else " · 예상 밖"
    fc = base_fc(t, 1, "pre", T["registered"], f'{T["event_short"]} 전에 두 갈래를 적었습니다. 결과가 나오면 그날 종가부터 잽니다.',
                 f'{T["event_short"]} 뒤 {T["subj_eun"]}?', [["게시", H.md(T["registered"])], ["사건", H.md(ev)]] + ([["시장 예상", f'{T["outcomes"][0]} {mp["probs"][0]}%']] if mp else []) + [["결과", out]], sc,
                 event_day=ev, outcomes=T["outcomes"], ruler_from=f"{H.md(ev)} 종가 대비", ref=f"{H.md(ev)} 종가보다", sides_title="결과별 전망",
                 line_src=T.get("line_src", f"20거래일 움직임 1σ → 정수 {L:g}{u}"), beta=T.get("beta"), market_prob=mp,
                 next={"title": "앞으로 볼 것은?", "answer": "지켜보는 중", "lead": "아직 정해지지 않은 것이 둘 있습니다.",
                       "lines": [f"얼마나 오래 가나 : 금을 넘은 뒤 며칠 만에 방향을 바꿀지, 더 이어질지는 열려 있습니다. 맞음이 나오면 세부 전망에서 이어 갑니다",
                                 f"무엇이 흐름을 바꾸나 : {T['subject']}가 크게 움직인 날에 어떤 뉴스가 많았는지로 가립니다"]},
                 follow=follow, T=T)
    if cond:   # 고리 상태 — 일어난 조건의 첫 고리는 확인, 일어나지 않은 갈래는 해당 없음
        for s in fc["scenarios"]:
            for c in s["chain"]:
                c["state"] = "no" if s["no"] != cond else c["state"]
        fc["scenarios"][cond - 1]["chain"][0].update(state="done", ev=f"{H.md(ev)} 결과 확정")
    return fc


def after_fc(t, no, gap, registered, shock_day, base_day, pick=1, title_event=None, T=None):
    """틀 R — 충격 뒤 등록, 반등(급락 뒤) · 조정(급등 뒤) vs 지속. gap = 등록 때 적은 충격 폭(고정)."""
    T = T or TIERS[t]
    L, u = T["line"], T["unit"]
    s = 1 if gap > 0 else -1
    w = H.DIR_WORD[s]
    more = "오름" if s > 0 else "빠짐"
    rw, rv = H.REV[s]
    sc = [{"no": 1, "cond": f"{rw} 쪽이면", "name": f'{T["subject"]} {rw}', "dir": -s,
           "chain": [{"step": f"{H.SHOCK[s]} 폭의 4분의 1 {rv}", "state": "wait", "ev": "", "date": ""},
                     {"step": f"{H.SHOCK[s]} 폭의 절반 {rv}", "state": "wait", "ev": "", "date": ""}],
           "win": f'{T["subj_ga"]} {H.SHOCK[s]} 폭({abs(gap):.1f}{u})의 절반을 {rv}한다'},
          {"no": 2, "cond": "지속 쪽이면", "name": f'{T["subject"]} {w} 지속', "dir": s,
           "chain": [{"step": f"{H.SHOCK[s]} 뒤 {L / 3:.0f}{u} 더 {more}", "state": "wait", "ev": "", "date": ""},
                     {"step": f"{H.SHOCK[s]} 뒤 {L:g}{u} 더 {more}", "state": "wait", "ev": "", "date": ""}],
           "win": f'{T["subj_ga"]} {H.SHOCK[s]} 뒤 {L:g}{u} 더 {"오른다" if s > 0 else "빠진다"}'}]
    # 우리 전망 = ① 뉴스 유무 ② 같은 종류 기록 비율 (개선 ④ · ②). hist_after 20거래일 줄의 "오른 횟수" 가 반등(급락 뒤) 또는 지속(급등 뒤)의 횟수
    h = T.get("hist_after")
    if h and len(h["rows"][1]) == 3:
        up = h["rows"][1][1]; n = h["n"]
        rate_rev = (up / n) if s < 0 else (1 - up / n)
        side, prob, why = H.pick_side(rate_rev, T.get("news", True))
        pick = side
        m = (up if s < 0 else n - up) if side == 1 else (n - up if s < 0 else up)   # 독자 줄 = 실제 횟수(가중 전), 확률 · 계산식은 운영자 상자
        pick_odds = (m, n, "같은 종류 사건 뒤 20거래일 · " + ("뉴스가 있는 급변은 이어지는 쪽이 더 흔해 조금 더 무게" if T.get("news", True) else "뉴스 없는 급변은 되돌리는 쪽이 더 흔해 조금 더 무게"))
    else:
        prob, why, pick_odds = None, "", None
    ev_word = title_event or ("급등" if s > 0 else "급락")
    d5 = tdays(registered, 6)[-1]
    return base_fc(t, no, "after", registered, f"{H.md(shock_day)} {ev_word} 뒤 두 갈래를 적었습니다. 다음 거래일부터 봅니다.",
                   f'{T["subject"]} {ev_word}, ' + ("조정 올까 더 오를까?" if s > 0 else "반등할까 더 빠질까?"), [["게시", H.md(registered)], [ev_word, H.md(shock_day)], ["첫 확인", H.md(d5)]], sc,
                   gap=gap, pick=pick, ruler_from=f"{H.md(base_day)} 종가 대비", ref=f"{H.md(base_day)} 종가보다", sides_title="갈래별 전망",
                   tags=[T["tags"][1], rw],
                   next={"title": "무엇으로 가르나?", "answer": "갈림 조건 둘", "lead": f"{rw}과 지속을 가르는 것으로 둘을 봅니다. 더 보태지 않습니다.",
                         "lines": [f"시장도 같이 움직였나 : 혼자 크게 움직인 {H.SHOCK[s]}과 시장이 같이 움직인 {H.SHOCK[s]}은 그 뒤 모양이 다릅니다",
                                   f"크게 움직인 날의 뉴스 : {H.SHOCK[s]}과 같은 종류의 뉴스가 이어지면 지속 쪽, 다른 종류의 뉴스가 늘면 {rw} 쪽입니다"],
                         "tail": f'{H.SHOCK[s]} 폭의 절반을 {rv}하면 ‘{sc[0]["name"]}’, {H.SHOCK[s]} 뒤 {L:g}{u} 더 가면 ‘{sc[1]["name"]}’으로 적습니다.'},
                   history=T.get("hist_after"), pick_prob=prob, pick_why=why, pick_odds=pick_odds, news=T.get("news", True), beta=T.get("beta"), T=T)


def mark_chain(fc, st):
    """판정 결과로 고리 상태를 채운다(자동화 뒤엔 코드가 같은 일을 한다)."""
    res = st.get("result")
    if fc["kind"] == "pre" and st.get("cond") and res and res.get("crossed"):
        for c in fc["scenarios"][st["cond"] - 1]["chain"][1:]:
            c["state"] = "done"
    if fc["kind"] == "after":
        rec = st.get("recovery") or 0
        g, s, L = fc["gap"], (1 if fc["gap"] > 0 else -1), fc["line"]
        ext = s * ((st.get("rel") or g) - g)
        sc1, sc2 = fc["scenarios"]
        sc1["chain"][0]["state"] = "done" if rec >= 25 else "wait"
        sc1["chain"][1]["state"] = "done" if rec >= 50 else "wait"
        sc2["chain"][0]["state"] = "done" if ext >= L / 3 else "wait"
        sc2["chain"][1]["state"] = "done" if ext >= L else "wait"


def run(fc, days, rel, cond=None, vix=None, end=None, volume_x=None):
    if end:
        fc["end_day"] = end
    if fc.get("pick_odds") and fc["kind"] == "after":
        fc["scenarios"][fc["pick"] - 1]["odds"] = fc["pick_odds"]
    last = max([i for i, v in enumerate(rel) if v is not None], default=-1)
    days, rel = days[:last + 4], rel[:last + 4]   # 그래프 오른쪽 빈 자리는 사흘만
    vix = vix[:last + 4] if vix else vix
    st = H.judge(fc, days, rel, cond=cond, vix=vix)
    st["volume_x"] = volume_x if volume_x is not None else (3.4 if fc["kind"] == "after" else 1.6)   # 거래량 배수 (개선 ⑤, 가상)
    if fc.get("end_day") and fc["dates"][-1][0] != "최종":
        fc["dates"] = fc["dates"][:-1] + [["최종", H.md(fc["end_day"])], fc["dates"][-1]]   # 결과 줄은 오른쪽 끝 그대로
    st["label_at"] = [0, len(days) // 2, len(days) - 1]
    mark_chain(fc, st)
    return st


def vix_for(rel, base=18.0):
    return [None if v is None else round(base - v * 0.8, 1) for v in rel] if rel else None


# ---------------------------------------------------------------- 돌발 사건 대상 (상황 10 · 11, 가상) — 대상은 코드가 고른다: 그날 시장 대비 가장 크게 움직인 계열 (범위 비율)
SUDDEN = {
    "A": {"name": "거시", "subject": "S&P 500", "subj_ga": "S&P 500 이", "subj_eun": "S&P 500 은", "cmp": None, "unit": "%", "line": 4.0,
          "ruler_short": "S&P 500 수익률", "event": "01.12 중동 전쟁 확산", "event_short": "전쟁 · 유가 급등", "tags": ["전쟁 · 유가", "S&P 500"], "vix": True,
          "shock": -5.2, "shock_day": "2027-01-12", "news": True, "beta": None,
          "story": "중동 전쟁 확산 → 호르무즈 해협 봉쇄 우려 → 유가 하루 +14% → S&P 500 -5.2%",
          "detect": "B1 일봉 _GSPC 하루 -5.2% = 최근 60일 평소(σ 0.9%)의 5.8배 · 절대 3% 넘음 · 거래량 3.4배 → 충격 (detect_shocks 기준)",
          "scope": "범위 비율 = 업종/시장 아님(지수 자체). 동반 하락: 나스닥 -6.1% · 코스피 -4.4% · 에너지 업종 +3.8%(반대) → 시장 전체 사건",
          "issues": "A5 뉴스 1.12 상위 = GEOPOLITICS 41건 · OIL_ENERGY 17건 · FX_GLOBAL 6건 / A6 방송 5채널 중 5 지정학 / A7 인물 발언 2 (재무장관 · 연준 의장 \"지켜본다\")",
          "kind_map": "사건 종류 = 사건표 어휘 ‘전쟁 · 테러’ (GEOPOLITICS 1위 + 유가 동행 → event_vocab 매핑)",
          "companions": "동행 자료(B2 · B4) = 유가 CL_F +14.2% · VIX 31.5 · 달러 +1.1% · 금 +2.8% · 10년 금리 -18bp",
          "history": "A8 사건표 같은 종류 9건(9/11 · 이라크 2003 · 리비아 2011 · 아람코 2019 · 우크라이나 2022 …) 뒤 S&P 500 중앙값: 5일 +0.4% · 20일 +2.1% · 60일 +4.0%",
          "pick": "우리 전망 = 반등 (규칙: 같은 종류 사건 뒤 20일 중앙값 부호가 충격과 반대면 반등 · 같으면 지속, 표본 5건 미만이면 ‘모든 3% 충격’ 분포로 대체)",
          "hist_after": {"what": "전쟁 · 테러로 S&P 500 이 하루 3% 넘게 빠진 날이", "n": 9, "since": 1996, "rows": [["5거래일 뒤", 5, "−2.9 ~ +3.3%"], ["20거래일 뒤", 6, "−4.4 ~ +6.0%"], ["60거래일 뒤", 7, "−6.1 ~ +9.5%"]]}},
    "B": {"name": "업종", "subject": "에너지 업종", "subj_ga": "에너지 업종이", "subj_eun": "에너지 업종은", "cmp": "시장보다", "unit": "%p", "line": 2.5,
          "ruler_short": "에너지 vs 시장", "event": "09.01 허리케인 걸프만 상륙", "event_short": "허리케인 · 정유 차질", "tags": ["허리케인", "에너지"], "vix": True,
          "shock": 6.3, "shock_day": "2027-09-01", "news": True, "beta": 0.8,
          "story": "허리케인 걸프만 상륙 → 정유 설비 40% 가동 중단 → 휘발유 선물 +18% → 에너지 업종(XLE) 시장보다 +6.3%p",
          "detect": "B1 일봉 XLE 하루 +5.9% − _GSPC -0.4% = +6.3%p = 평소(σ 1.1%p)의 5.7배 · 절대 2.5%p 넘음 → 충격 (detect_sector_shocks 기준)",
          "scope": "범위 비율 = 업종 +5.9 / 시장 -0.4 → 업종 단독 (시장은 평소 범위 안)",
          "issues": "A5 뉴스 9.01 상위 = OIL_ENERGY 29건 · GEOPOLITICS 3건 / A6 방송 4채널 중 3 유가 · 에너지 / A12 업종 재료(한국 정유) 2건",
          "kind_map": "사건 종류 = 사건표 어휘 ‘유가 충격’(허리케인 공급 차질) — OIL_ENERGY 1위 + 업종 단독",
          "companions": "동행 자료 = 휘발유 선물 +18% · 유가 CL_F +6.4% · VIX 19.8(평소) · 정유 3사 +8~11%",
          "history": "A8 사건표 같은 종류 4건(카트리나 · 리타 2005 · 구스타프 · 아이크 2008 · 하비 2017) 뒤 에너지 vs 시장 중앙값: 5일 -0.6%p · 20일 -1.8%p · 60일 -2.2%p",
          "pick": "우리 전망 = 조정 (20일 중앙값 부호가 충격(상승)과 반대. 표본 4건 → ‘모든 업종 단독 2.5%p 급등’ 68건으로 대체: 20일 -1.1%p, 같은 결론)",
          "hist_after": {"what": "에너지 업종이 시장보다 하루 2.5%p 넘게 오른 날이", "n": 68, "since": 1999, "rows": [["5거래일 뒤", 30, "−3.0 ~ +2.6%p"], ["20거래일 뒤", 27, "−5.4 ~ +4.0%p"], ["60거래일 뒤", 29, "−8.1 ~ +6.9%p"]]}},
    "C": {"name": "개별 종목", "subject": "엔비디아", "subj_ga": "엔비디아가", "subj_eun": "엔비디아는", "cmp": "반도체 지수보다", "unit": "%p", "line": 6.0,
          "ruler_short": "엔비디아 vs 반도체", "event": "03.04 대만 지진 · 공장 가동 중단", "event_short": "대만 지진 · 공급 차질", "tags": ["지진 · 공급", "엔비디아"], "vix": False,
          "shock": -7.5, "shock_day": "2027-03-04", "news": False, "beta": 1.6,
          "story": "대만 지진 → 첨단 공정 공장 가동 중단 → 엔비디아 신제품 출하 지연 보도 → 엔비디아 반도체 지수보다 -7.5%p",
          "detect": "B1 일봉 NVDA 하루 -9.0% − _SOX -1.5% = -7.5%p = 평소(σ 1.6%p)의 4.7배 · 절대 6%p 넘음 → 충격",
          "scope": "범위 비율 = 종목 -9.0 / 업종 -1.5 → 종목 단독 (업종 · 시장은 평소 범위 안)",
          "issues": "A5 뉴스 3.04 상위(ticker NVDA) = CORP_EVENT 14건 · GEOPOLITICS 9건 · AI_CAPEX 4건 / A4 공시 8-K 없음 / A11 애널리스트 목표가 변경 0",
          "kind_map": "사건 종류 = 사건표 어휘 ‘재난 · 팬데믹’ + 종목 범위 — 종목 사건표는 내부 장부만(공개 안 함)",
          "companions": "동행 자료 = TSM -6.2% · _SOX -1.5% · 옵션 ATM IV 58→71 · P/C 0.9→1.4 (nvda-state daily_state)",
          "history": "내부 장부: 종목 단독 2σ 급락 38건(2010~) 뒤 엔비디아 vs 반도체 중앙값: 5일 +1.5%p · 20일 +2.2%p · 60일 +1.9%p (공급 사고로 좁히면 3건 — 표본 부족)",
          "pick": "우리 전망 = 반등 (같은 종류 3건 < 5 → ‘모든 종목 단독 급락’ 38건 분포로 대체, 20일 중앙값 + 부호)",
          "hist_after": {"what": "엔비디아가 반도체보다 하루 6%p 넘게 빠진 날이", "n": 38, "since": 2010, "rows": [["5거래일 뒤", 22, "−4.0 ~ +6.5%p"], ["20거래일 뒤", 23, "−7.2 ~ +9.8%p"], ["60거래일 뒤", 21, "−11 ~ +13%p"]]}},
}

# 동시다발 (상황 11) — 일정 사건(틀 S) 창 안에 돌발 충격이 들어옴
CONCUR = {
    "A": {"name": "관세 급습", "day_off": 4, "size": -1.9, "issue": "TARIFF_TRADE 52건 · FX_GLOBAL 11건", "story": "대통령 SNS 로 전 품목 25% 관세 발표(장중) → S&P 500 하루 -4.5%",
          "detect": "B1 _GSPC -4.5% = 평소 5배 · A7 인물 발언(대통령) 1 · A5 TARIFF_TRADE 1위 → 충격 · 사건표 어휘 ‘관세 · 무역’"},
    "B": {"name": "수출 규제", "day_off": 4, "size": -1.9, "issue": "REGULATION 37건 · GEOPOLITICS 12건", "story": "중국행 첨단 반도체 수출 전면 규제 발표(장 마감 뒤) → 다음 날 반도체 시장보다 -5.7%p",
          "detect": "B1 _SOX -6.4% − _GSPC -0.7% = -5.7%p = 평소 5.2배 · A5 REGULATION 1위 · A11 목표가 하향 6건 → 충격 · 사건표 어휘 ‘규제 (수출 · 반독점)’"},
    "C": {"name": "수출 규제", "day_off": 4, "size": -1.6, "issue": "REGULATION 37건 · AI_CAPEX 8건", "story": "중국행 첨단 반도체 수출 전면 규제 → 엔비디아(중국 매출 비중 큼) 반도체보다 -9.6%p",
          "detect": "B1 NVDA -14.1% − _SOX -4.5% = -9.6%p = 평소 6배 · A5 REGULATION 1위(ticker NVDA 21건) · A4 8-K 매출 영향 공시 → 충격"},
}


def op_for(t, fc, st, extra=None):
    """운영자 확인용 상자 내용 — 80개 요인(데이터-기록-계획 A3-2) 중 이 전망에 쓰인 것 · 판정 근거. extra = 상황별 덧붙임 [(이름, 값)]."""
    T = TIERS[t]
    res = st.get("result")
    log = st.get("log") or []
    if fc["kind"] == "pre":
        rows = [("규칙", f'{H.RULES} (틀 S) · 자 = 시장 모형 β 조정 초과수익(추정 120일, β {fc.get("beta") or 1.0}) · 기준 = {fc.get("line_src", "")} · 창 D+5/20/60'),
                ("자료", f'B1 일봉 {"_GSPC" if t == "A" else ("_SOX · _GSPC" if t == "B" else "NVDA · _SOX")} · {"A2 FOMC 일정 · 결정(fomc.csv)" if t == "A" else "A3 실적 일정 · surprise_band(earnings.csv)"}'
                         + (" · B2 _VIX" if T["vix"] else "")),
                ("등록 근거", f'일정표 {T["event"]} 3거래일 전 자동. 조건 둘 = {" / ".join(T["outcomes"])} (코드 판정)'),
                ("방향 출처", f'사건 전 7일 A5 뉴스 · A6 방송 · A7 인물에서 사건 키워드 묶음 상위 → Groq 조건문 → 코드 검사 통과 (direction_source = 통용 설명). '
                             f'묶음 = {"RATES_FED 23 · GROWTH_JOBS 9 · INFLATION 7" if t == "A" else "EARNINGS 19 · AI_CAPEX 14 · REGULATION 3"}')]
    else:
        rows = [("규칙", f'{H.RULES} (틀 R) · 자 = β 조정 초과수익(β {fc.get("beta") or 1.0}) · 반등 · 조정 = 폭 절반 · 지속 = 금만큼 더 · 창 D+60'),
                ("자료", "B1 일봉 대상 · 비교 계열 · 거래량 · B2 _VIX · A5 이슈 코드(크게 움직인 날 상위 3일) · GPR · EPU 일별"),
                ("우리 전망", f'{fc["scenarios"][fc["pick"] - 1]["name"]} {(str(round(fc["pick_prob"] * 100)) + "%") if fc.get("pick_prob") else ""} — {fc.get("pick_why") or "기록상 같은 종류 뒤 20일 중앙값 부호"} (뉴스 유무 = {"1위 이슈 뚜렷" if fc.get("news", True) else "원인 미상"})')]
    if extra:
        rows += extra
    fx = st.get("fixed") or {}
    if fx:
        rows.append(("고정 시점 판정", " / ".join(f'D+{k} {H.md(d)} {v:+.1f} → {side}' for k, (d, v, side) in fx.items()) + " (첫 넘김 판정과 따로 센다)"))
    if res and fc.get("pick_prob"):
        hit = res["word"] == "맞음"
        rows.append(("브라이어", f'{H.brier(fc["pick_prob"], hit)} (확률 {fc["pick_prob"] * 100:.0f}% · 결과 {res["word"]}; 0 완벽 · 0.25 동전)'))
    if fc.get("market_prob"):
        mp = fc["market_prob"]; c = st.get("cond")
        rows.append(("시장 예상 · 놀람", f'등록 때 {fc["outcomes"][0]} {mp["probs"][0]}% ({mp["src"]})' + (f' → 결과 {fc["outcomes"][c - 1]} = {"예상대로(놀람 아님 · 기준 넘길 확률 낮음)" if mp["probs"][c - 1] >= 50 else "예상 밖(놀람)"}' if c else "") + " — 놀람 여부는 세 줄 기록에 같이 적어 나중에 ‘예상대로 vs 놀람’ 으로 가른다(11절 1)"))
    rows.append(("시점 고정", "등록 때 값(이슈 코드 · 분위기 · 시장 예상 · β · 기록 분포 · 닮은 사례)은 그날 스냅샷으로 저장, 다시 계산 안 함(11절 6)"))
    rows.append(("플라시보", "무작위 창에서 같은 규칙으로 ‘먼저 넘은 쪽 = 우리 전망’ 비율 — 검증해 때 계산해 맞은 비율 옆에 둔다"))
    if log and len(log) > 1:
        top = sorted([e for e in log if e.get("rel") is not None], key=lambda e: -abs(e["rel"]))[:3]
        rows.append(("이슈 코드 상위 3일", " / ".join(f'{H.md(e["day"])} {"RATES_FED 18 · GROWTH_JOBS 6" if t == "A" else "EARNINGS 12 · AI_CAPEX 9"}' for e in top) + " (A5 · 가상)"))
    if fc.get("pressure"):
        rows.append(("배경 (층 압력)", "등록 때 " + " · ".join(f"{k} {v}" for k, v, _ in fc["pressure"]["rows"]) + " → 갈림 조건 후보(3부 5절: 전망마다 2개 이하, 쌓이면 ‘시장이 위험 회피일 때 업종 급락 뒤 반등은 드물었다’ 식으로 센다)"))
    if fc.get("parent"):
        rows.append(("파급", f'위 층 전망 {fc["parent"][0]} 의 창 안에서 이 층이 스스로 기준을 넘어 등록(가격 기준은 층마다 따로). 위 층 국면을 배경 칸에 같이 기록'))
    rows.append(("겹침", ", ".join(f'{o["day"]} {o["event"]} → 전망 {o["no"]}' + (" (반대 방향)" if o.get("sign") == "opposite" else " (같은 방향)" if o.get("sign") == "same" else "") for o in fc.get("overlap", [])) or "없음"))
    rows.append(("세 줄 기록", f'결과 = {res["word"] if res else "미정"} · 겹침 = {"있음" if fc.get("overlap") else "없음"} · 동행 = {"RATES_FED" if t == "A" else "EARNINGS"} 묶음 {2 if log else 0}/3일'))
    return rows


def case_sudden(t, days_all):
    """상황 10 — 일정에 없던 돌발 사건. 감지는 가격, 이름은 그날 1위 이슈 코드 → 사건표 어휘, 우리 전망은 같은 종류 기록."""
    S = SUDDEN[t]
    g, u, L = S["shock"], S["unit"], S["line"]
    sgn = 1 if g > 0 else -1
    sd = tdays((date.fromisoformat(S["shock_day"]) - timedelta(days=1)).isoformat(), 30)
    rel = path([(0, 0), (1, g), (2, g * 1.08), (4, g * 0.95), (7, g * 0.7), (9, g * 0.62)], 12, wig=abs(g) * 0.02)
    dd = sd[:12]
    fc = after_fc(t, 1, round(rel[2], 1), dd[2], dd[1], dd[0], pick=1, T=S)
    fc["end_day"] = tdays(dd[2], 61)[-1]
    fc["event"] = S["event"]
    fc["dates"][1][0] = "사건"
    fc["dates"][1][1] = f'{H.md(dd[1])} {S["event_short"]}'
    fc["start_text"] = f'{H.md(dd[1])} {S["event_short"]}으로 {S["subject"]}이 {H.SHOCK[sgn]}한 뒤 두 갈래를 적었습니다. 다음 거래일부터 봅니다.'
    st = run(fc, dd, rel, vix=vix_for(rel, 24) if S["vix"] else None)
    st["log"][0]["text"] = fc["start_text"]
    op = op_for(t, fc, st, extra=[("감지", S["detect"]), ("범위", S["scope"]), ("이슈 코드", S["issues"]), ("사건 종류", S["kind_map"]),
                                  ("동행 자료", S["companions"]), ("기록", S["history"]), ("고른 근거", S["pick"])])
    expl = [("상황", S["story"] + " (가상)"),
            ("코드가 한 일", "일정에 없어도 틀 R 그대로: ① 가격으로 충격 감지 ② 그날 1위 이슈 코드로 사건 이름 · 사건표 어휘 ③ 같은 종류 기록으로 우리 전망 ④ 다음 거래일 장 마감 뒤 등록. 사건 전 전망은 없다(터진 뒤의 일만 적는다). AI 호출 0."),
            ("독자가 보는 것", f'제목 ‘{fc["title"]}’, 사건 줄에 {S["event_short"]}. 우리 전망 라벨 · 지금 {st["log"][-1]["label"]}. ‘기록상 비슷한 때는?’ 에 같은 종류 사건 뒤 분포.'),
            ("내부 기록", "회색 상자: 감지 배수 · 범위 비율 · 이슈 코드 · 사건 종류 · 동행 자료(유가 · VIX · 환율) · 기록 n · 고른 근거. 종목(C)은 공개 미정 — 내부 장부만.")]
    return expl, [("전망 페이지", H.forecast_body({"id": f"EH-{t}-s"}, st, fc, others=[], op=op))]


def case_concur(t, days, end):
    """상황 11 — 일정 사건 전망(틀 S)이 진행 중일 때 돌발 충격이 창 안에 들어옴. 겹침 양쪽 표시 · 동행 부호(같은 방향 / 반대 방향)만 적고 원인 몫은 재지 않는다."""
    T, C = TIERS[t], CONCUR[t]
    L, u = T["line"], T["unit"]
    k0 = C["day_off"]
    rel = path([(0, 0), (1, L * 0.2), (3, L * 0.45), (k0, L * 0.45 + C["size"] * L * 0.6), (k0 + 2, -L * 0.75), (k0 + 4, -L * 1.15), (k0 + 7, -L * 0.8)], k0 + 10, wig=L * 0.03)
    dd = days[:k0 + 10]
    f1 = pre_fc(t, cond=1)
    f1["history"] = T["hist_pre"]
    sh_day, reg2 = dd[k0], dd[k0 + 1]
    f1["overlap"] = [{"day": H.md(sh_day), "event": C["name"] + " 충격", "no": 2, "sign": "opposite", "title": "T2"}]
    st1 = run(f1, dd, rel, cond=1, vix=vix_for(rel) if T["vix"] else None, end=end)
    gap = round(rel[k0] - rel[k0 - 1], 1)
    rel2 = [None if v is None else round(v - rel[k0 - 1], 2) for v in rel]
    f2 = after_fc(t, 2, gap, reg2, sh_day, dd[k0 - 1], pick=1)
    f2["event"] = f'{H.md(sh_day)} {C["name"]}'
    f2["dates"][1] = ["사건", f'{H.md(sh_day)} {C["name"]}']
    f1["overlap"][0]["title"] = f2["title"]
    f2["overlap"] = [{"day": H.md(T["event_day"]), "event": C["name"] + " 충격", "no": 1, "sign": "opposite", "title": f1["title"], "role": "parent"}]
    f2["end_day"] = tdays(reg2, 61)[-1]
    st2 = run(f2, dd, rel2, vix=vix_for(rel2, 22) if T["vix"] else None)
    sign1 = "+" if rel[1] > 0 else "−"
    extra = [("촉발 · 동행", f'에피소드 시작일 {H.md(sh_day)} 1위 이슈 = {C["issue"]} → 충격 이름 ‘{C["name"]}’. 일정 사건 날({H.md(T["event_day"])}) 반응 {sign1}, 돌발 날 − → **반대 방향** (상쇄한 모양). 몫은 재지 않는다 — 두 사건을 가를 수 없으니 둘 다 ‘맞은 비율’ 에서 뺀다(3부 10-3)'),
             ("감지", C["detect"])]
    op1 = op_for(t, f1, st1, extra=extra)
    op2 = op_for(t, f2, st2, extra=extra)
    oth1, oth2 = [(2, f2["title"], f2["slug"])], [(1, f1["title"], f1["slug"])]
    expl = [("상황", f'{T["event"]} 뒤 ‘{f1["scenarios"][0]["name"]}’ 조짐으로 가던 중 {H.md(sh_day)} {C["story"]} (가상). 이어서 반대로 기준을 넘어 전망 1 은 ‘틀림’.'),
            ("코드가 한 일", "① 돌발 충격을 전망 2(틀 R)로 따로 등록 ② 전망 1 · 2 서로 겹침 표시 ③ 동행 부호: 일정 사건 날 반응과 돌발 날 반응이 반대 → ‘상쇄한 모양’ 으로만 기록(어느 쪽이 몇 % 원인인지는 적지 않는다) ④ 전망 1 틀림은 독자에게 그대로, 내부 ‘맞은 비율’ 집계에서는 겹침이라 둘 다 뺀다."),
            ("독자가 보는 것", "전망 1 맨 위 ‘틀림’ + 카드 아래 회색 한 줄(다른 사건이 들어와 따로 적었고 결과에 두 사건이 겹쳐 있음). 전망 2 는 새 전망으로 반등 vs 하락 지속."),
            ("내부 기록", "회색 상자 ‘촉발 · 동행’ 줄 — 1위 이슈 코드 · 반응 부호 · 상쇄 여부 · 집계 제외. 둘 다 세 줄 기록에 겹침 = 있음.")]
    reg = {"id": f"EH-{t}-c"}
    return expl, [("전망 1 페이지 (틀림 · 겹침)", H.forecast_body(reg, st1, f1, others=oth1, op=op1)),
                  ("전망 2 페이지 (돌발 충격)", H.forecast_body(reg, st2, f2, others=oth2, op=op2))]


# ---------------------------------------------------------------- 층 압력 · 분위기 (상황 12 · 모든 탭의 `지금 시장 분위기는?`) — 값은 이미 매일 나오는 우리 판정 (signal_groups regime · shock · sector_flow · news) + 공포 · 탐욕 지수. 가상
def pressure(t, mood):
    sec = {"A": "기술주", "B": "반도체", "C": "반도체"}[t]
    if mood == "shock":
        rows = [("미국 증시 분위기", "위험 회피", "데일리 regime 점수 −3 · 하락 종목 82% · 안전자산 ▲"), ("시장 충격 국면", "충격", "VIX 31.5 · 20일 −8% 안"),
                (f"{sec} 업계 자금", "유출", "5일 상대수익 −4.2%p"), ("뉴스 · 방송", "부정 많음", "뉴스 31건 중 부정 72% · 방송 5곳 중 4곳 부정 · 놀람 3"), ("공포 · 탐욕 지수", "극단적 공포", ""),
                ("거래량", "평소보다 아주 많음", ""), ("지정학 위험 지수", "아주 높음", ""), ("정책 불확실성", "높음", "")]
        return {"answer": "위험 회피", "rows": rows}
    if mood == "riskon":
        rows = [("미국 증시 분위기", "위험 선호", "regime 점수 +2 · 상승 종목 68%"), ("시장 충격 국면", "평소", "VIX 16.7"),
                (f"{sec} 업계 자금", "유입", "5일 상대수익 +2.1%p"), ("뉴스 · 방송", "긍정 많음", "뉴스 23건 중 긍정 61% · 방송 4곳 중 3곳 긍정"), ("공포 · 탐욕 지수", "탐욕", ""),
                ("거래량", "평소보다 많음", ""), ("지정학 위험 지수", "평소 수준", ""), ("정책 불확실성", "평소 수준", "")]
        return {"answer": "위험 선호", "rows": rows}
    rows = [("미국 증시 분위기", "중립", "regime 점수 0 · 상승 종목 52%"), ("시장 충격 국면", "평소", "VIX 18.0"),
            (f"{sec} 업계 자금", "보통", "5일 상대수익 +0.3%p"), ("뉴스 · 방송", "엇갈림", "뉴스 19건 긍정 47% · 부정 42%"), ("공포 · 탐욕 지수", "중립", ""),
            ("거래량", "평소 수준", ""), ("지정학 위험 지수", "평소 수준", ""), ("정책 불확실성", "조금 높음", "")]
    return {"answer": "중립", "rows": rows}


def case_cascade(t):
    """상황 12 — 한 돌발 사건이 시장 → 업종 → 종목으로 내려오는 사슬. 층마다 스스로 가격 기준을 넘어야 등록되고(위 층이 빠졌다고 자동 등록하지 않는다), 등록되면 위 층을 parent 로 잇는다.
    모든 탭(A · B · C)에서 같은 세 페이지를 보여 준다 — 자기 층 페이지가 맨 위."""
    S = SUDDEN["A"]
    sd = tdays("2027-01-11", 30); dd = sd[:12]
    mk = {}
    # 시장(S&P 500) -5.2% → 업종(반도체 vs 시장) -4.3%p → 종목(엔비디아 vs 반도체) -7.2%p — 아래 층일수록 더 빠진 가상 숫자
    specs = {"A": (dict(S), -5.2, None), "B": (dict(TIERS["B"], event=S["event"], event_short=S["event_short"], tags=["전쟁 · 유가", "반도체"], hist_after=TIERS["B"]["hist_after"]), -4.3, "A"),
             "C": (dict(TIERS["C"], event=S["event"], event_short=S["event_short"], tags=["전쟁 · 유가", "엔비디아"], hist_after=TIERS["C"]["hist_after"]), -7.2, "B")}
    for lay in "ABC":
        T, g, par = specs[lay]
        rel = path([(0, 0), (1, g), (2, g * 1.05), (4, g * 0.9), (7, g * 0.75), (9, g * 0.68)], 12, wig=abs(g) * 0.02)
        fc = after_fc(lay, {"A": 1, "B": 2, "C": 3}[lay], round(rel[2], 1), dd[2], dd[1], dd[0], pick=1, T=T)
        fc["slug"] = f"case-cascade-{lay}"; fc["end_day"] = tdays(dd[2], 61)[-1]; fc["event"] = S["event"]
        fc["dates"][1] = ["사건", f'{H.md(dd[1])} {S["event_short"]}']
        fc["start_text"] = f'{H.md(dd[1])} {S["event_short"]}으로 {T["subject"]}이 급락한 뒤 두 갈래를 적었습니다. 다음 거래일부터 봅니다.'
        st = run(fc, dd, rel, vix=vix_for(rel, 24) if T["vix"] else None)
        st["log"][0]["text"] = fc["start_text"]
        fc["pressure"] = pressure(lay, "shock")
        mk[lay] = (fc, st)
    for lay, par in (("B", "A"), ("C", "B")):
        p = mk[par][0]; c = mk[lay][0]
        c["parent"] = (p["no"], p["title"], p["slug"])
        p.setdefault("children", []).append((c["no"], c["title"], c["slug"]))
    order = [t] + [x for x in "ABC" if x != t]
    pages = []
    for lay in order:
        fc, st = mk[lay]
        extra = [("감지", {"A": S["detect"], "B": "B1 _SOX -9.1% − _GSPC -5.2% = -4.3%p (평소 3.6배) — 시장이 같이 빠졌지만 업종이 기준을 따로 넘어 등록", "C": "B1 NVDA -15.8% − _SOX -9.1% = -7.2%p (평소 4.5배) — 종목도 따로 기준 넘음"}[lay]),
                 ("범위", {"A": "시장 전체 (나스닥 -6.1% · 코스피 -4.4%)", "B": "업종 기울어진 시장 — 업종/시장 = 1.8 (범위 비율 1~2)", "C": "종목 기울어짐 — 종목/업종 = 1.7"}[lay]),
                 ("이슈 코드", {"A": S["issues"], "B": "A5 뉴스(sector 반도체) GEOPOLITICS 12 · AI_CAPEX 7 (‘대만 리스크 · 금리 상승 우려’) / A6 방송 3곳", "C": "A5 뉴스(NVDA) GEOPOLITICS 6 · EARNINGS 5 (실적 앞 포지션 정리) / A11 목표가 변경 0"}[lay]),
                 ("기록", {"A": S["history"], "B": "A8 사건표 ‘전쟁 · 테러’ 9건 뒤 반도체 vs 시장 20일 중앙값 +0.6%p (시장 반등 때 업종이 더 올랐다)", "C": "내부 장부 종목 단독 급락 38건 20일 중앙값 +2.2%p"}[lay])]
        pages.append((f'{ {"A": "시장", "B": "업종", "C": "종목"}[lay]} 층 · {fc["title"]}', H.forecast_body({"id": "EH-cascade"}, st, fc, others=[], op=op_for(lay, fc, st, extra=extra))))
    expl = [("상황", S["story"] + " → 반도체는 시장보다 4.3%p 더 빠지고 → 엔비디아는 반도체보다 7.2%p 더 빠짐 (가상). 한 사건이 세 층으로 내려온 모양."),
            ("코드가 한 일", "층마다 따로 가격 기준을 재서 넘은 층만 등록(시장이 빠졌다고 업종 · 종목을 자동 등록하지 않는다). 등록된 아래 층은 위 층 전망에 parent 로 잇고, 위 층의 국면 · 시장 분위기(regime · 충격 · 업계 자금 · 뉴스 방송 · 공포 탐욕)를 ‘배경’ 으로 함께 기록. 위 층이 반등하면 아래 층 페이지에 그대로 보인다."),
            ("독자가 보는 것", "‘지금 시장 분위기는?’ 카드 — 시장 → 업종 → 종목 순 분위기 다섯 줄 + ‘이 전망은 전망 n 에서 내려온 파급입니다’ · ‘아래로 이어진 전망’ 링크. 세 전망이 사슬로 읽힌다."),
            ("내부 기록", "배경 칸이 갈림 조건의 후보가 된다 — 쌓이면 ‘시장이 위험 회피일 때 업종 급락 뒤 반등은 n건 중 m건’ 처럼 층 조건별로 센다(3부 5절 2개 이하). 분위기 숫자(뉴스 방향 비율 · 방송 수 · 공포 탐욕)는 A5 · A6 · B 스냅샷에서 매일.")]
    return expl, pages


# ---------------------------------------------------------------- 상황 13 선반영 · 14 느린 누적 (2026-11-07 사용자: 뻔한 결과는 먼저 반영되고, 하루 1%씩 쌓이는 하락은 하루 기준에 안 걸린다)
def case_priced(t):
    """뻔한 결과 — 시장 확률 ≥ 70% 사흘 + 뉴스 묶음 집중 → 감지일에 등록(결과 10거래일 전). 감지일 종가부터 선반영을 재고, 결과일 종가에서 자를 다시 놓는다.
    예상대로 쪽 갈래 = `이미 반영`(priced): 결과 뒤 기준 넘게 더 가면 틀림, 되돌리거나 20거래일 기준 안이면 맞음."""
    T = dict(TIERS[t], market_prob={"probs": [82, 18], "src": "CME FedWatch · Kalshi, 감지일" if t == "A" else "예상치 상향 비율 · 옵션 예상 폭, 감지일"},
             hist_pre={"what": f'시장이 80% 넘게 예상한 대로 {TIERS[t]["outcomes"][0]} 이 나온 날이', "n": 29, "since": 2008,
                       "rows": [["5거래일 뒤", 13, "−1.9 ~ +1.6%" + ("" if t == "A" else "p")], ["20거래일 뒤", 14, "−3.8 ~ +3.1%" + ("" if t == "A" else "p")], ["60거래일 뒤", 16, "−6.0 ~ +6.4%" + ("" if t == "A" else "p")]],
                       "alike": [["2024.09", "모두가 예상한 첫 인하", "−0.4%"], ["2019.10", "세 번째 보험성 인하", "+1.1%"], ["2007.10", "두 번째 인하 · 되돌림", "−3.6%"]] if t == "A" else
                                [["2024.05", "예상대로 큰 폭 상회 · 되돌림", "−2.1%p"], ["2023.11", "예상대로 상회", "+0.9%p"], ["2024.11", "예상대로 상회 · 되돌림", "−1.6%p"]]})
    L, u, ev = T["line"], T["unit"], T["event_day"]
    pre = tdays((date.fromisoformat(ev) - timedelta(days=16)).isoformat(), 40)
    ei = next(i for i, d in enumerate(pre) if d >= ev)
    det = pre[ei - 10]
    days = pre[:ei + 24]
    top = L * 0.85
    rel = path([(0, 0), (ei, top), (ei + 1, top - L * 0.1), (ei + 6, top - L * 0.4), (ei + 12, top - L * 0.35), (ei + 20, top - L * 0.3)], len(days), wig=L * 0.03)
    days, rel = days[ei - 10:], [None if v is None else round(v - 0, 2) for v in rel[ei - 10:]]   # 감지일이 0
    fc = pre_fc(t, cond=1, T=T)
    fc.update(registered=det, detect_day=det, priced_end=tdays(ev, 21)[-1], end_day=tdays(ev, 61)[-1], history=T["hist_pre"],
              start_text=f'{T["event_short"]} 10거래일 전, 시장이 {T["outcomes"][0]}을 82%로 보고 뉴스도 그쪽으로 몰려 미리 적었습니다. 여기서부터 먼저 움직이는지 봅니다.',
              posted=H.md(det))
    fc["dates"] = [["게시", H.md(det)], ["감지", f"{H.md(det)} 시장 예상 82% · 뉴스 집중"], ["사건", H.md(ev)], ["최종", H.md(fc["end_day"])], ["결과", f'{H.md(ev)} {T["outcomes"][0]} · 예상대로']]
    a = fc["scenarios"][0]
    a.update(priced=True, cond=f'{T["conds"][0]} (예상대로)', name=f'{T["subject"]} 이미 반영',
             chain=[{"step": f'{T["outcomes"][0]} (시장 82% 예상)', "state": "done", "ev": f"{H.md(ev)} 결과 확정", "date": ""},
                    {"step": "결과 전에 먼저 오름", "state": "done", "ev": f"감지일부터 결과일까지 {top:+.1f}{u}", "date": ""},
                    {"step": "결과 뒤엔 더 오르지 않거나 되돌림", "state": "wait", "ev": "뉴스에 판다", "date": ""}],
             win=f'결과 뒤 20거래일 동안 {T["subj_ga"]} 기준({L:g}{u}) 넘게 더 오르지 않거나 되돌린다')
    b = fc["scenarios"][1]
    b.update(cond=f'{T["conds"][1]} (예상 밖)', chain=[dict(c, state="no") for c in b["chain"]])
    b["chain"][0]["step"] = f'{T["outcomes"][1]} (시장 18%)'
    st = run(fc, days, rel, cond=1, vix=vix_for(rel, 17) if T["vix"] else None, volume_x=1.3)
    st["label_at"] = [0, 10, len(days) - 1]
    fc["pressure"] = pressure(t, "riskon")
    for c in a["chain"]:
        if c["step"].startswith("결과 뒤엔"):
            c["state"] = "done" if st.get("result") and st["result"]["word"] == "맞음" else "wait"
    extra = [("감지 규칙", "일정 사건 10거래일 전부터 매일: 시장 확률(FedWatch · 옵션 · 예상치) ≥ 70% 가 사흘 이어지고 + 사건 키워드 이슈 묶음이 A5 뉴스 · A6 방송에서 상위 3 안 → 그날 장 마감 뒤 등록(감지일). 안 걸리면 평소대로 3거래일 전 틀 S"),
             ("선반영 구간", f'감지일 {H.md(det)} 종가 0 → 결과일 전날 {top:+.1f}{u} (10거래일, 하루 최대 {L * 0.12:.1f}{u} — 하루 기준엔 한 번도 안 걸림). 결과일 종가에서 자를 0 으로 다시 놓고 뒤를 잼'),
             ("판정 규칙", "예상대로 쪽 = ‘이미 반영’ 갈래: 결과 뒤 기준 넘게 더 가면 틀림(선반영이 다가 아니었다), 반대로 기준 넘게 되돌리면 맞음(뉴스에 팔기), 20거래일 기준 안이면 맞음(이미 반영된 대로). 예상 밖 쪽은 보통 틀 S")]
    expl = [("상황", f'{T["event"]} 10거래일 전부터 시장은 {T["outcomes"][0]}을 82%로 봤고 뉴스도 그쪽으로 몰림. 감지일부터 결과 전날까지 하루 0.3~0.5씩 {top:+.1f}{u} 먼저 오름(하루 기준엔 한 번도 안 걸림). 결과는 예상대로, 그 뒤엔 조금 되돌리며 기준 안 → 20거래일에 ‘이미 반영’ 맞음 (가상).'),
            ("코드가 한 일", "시장 확률 + 뉴스 집중으로 감지 → 감지일 등록(3거래일 전이 아니라 10거래일 전) → 선반영 구간을 따로 적고(`선반영 중`) → 결과일 종가에서 자를 다시 놓음 → 예상대로 쪽은 ‘이미 반영’ 갈래로 판정."),
            ("독자가 보는 것", "날짜 줄에 `감지 : 시장 예상 82% · 뉴스 집중`, 경과에 `선반영 중 : 감지일 종가보다 +2.3% 올랐습니다. 시장 예상이 먼저 반영되는 중입니다`, 결과 뒤 `지켜보는 중 — 먼저 반영된 대로 가는 중`, 20거래일에 `맞음 — 결과 전에 이미 반영된 대로`. 갈래 이름 ‘S&P 500 이미 반영’."),
            ("내부 기록", "감지 규칙 · 선반영 폭 · 결과일 재기준 · 놀람 아님. 세 줄 기록에 `선반영 폭` 칸 추가 — 쌓이면 ‘80% 넘게 예상된 사건은 결과 전에 평균 얼마나 먼저 가나’ 를 센다.")]
    return expl, [("전망 페이지 (선반영 → 이미 반영 맞음)", H.forecast_body({"id": f"EH-{t}-p"}, st, fc, others=[], op=op_for(t, fc, st, extra=extra)))]


def case_slow(t):
    """느린 누적 — 하루 기준(평소 3배)엔 못 미치지만 10거래일 누적 β 조정 초과수익이 10일 분포 2σ 를 넘으면 그날 장 마감 뒤 틀 R 로 등록. 급락과 같은 두 갈래(반등 vs 하락 지속)."""
    T = TIERS[t]
    L, u = T["line"], T["unit"]
    g = -L * 1.05
    sd = tdays("2027-01-18", 40)
    rel = path([(0, 0), (10, g), (12, g * 1.15), (16, g * 1.45), (19, g * 1.4)], 20, wig=abs(g) * 0.03)
    dd = sd[:20]
    fc = after_fc(t, 1, round(rel[10], 1), dd[10], dd[10], dd[0], pick=1, title_event="조용한 하락", T=dict(T, news=True))
    fc["end_day"] = tdays(dd[10], 61)[-1]
    fc["event"] = f'{H.md(dd[10])} 조용한 하락 감지'
    fc["dates"][1] = ["감지", f'{H.md(dd[10])} 10거래일 누적 {g:+.1f}{u}']
    fc["start_text"] = f'{H.md(dd[0])}부터 10거래일 동안 {T["subj_ga"]} 하루 기준엔 안 걸리게 조금씩 {abs(g):.1f}{u} 내렸습니다. 여기서 두 갈래를 적고 다음 거래일부터 봅니다.'
    st = run(fc, dd, rel, vix=vix_for(rel, 20) if T["vix"] else None, volume_x=1.1)
    st["log"][0]["text"] = fc["start_text"]
    fc["pressure"] = pressure(t, "shock")
    fc["pressure"]["rows"][1] = ("시장 충격 국면", "평소", "VIX 21 — 급락 없이 내려옴")
    extra = [("감지 규칙", f'둘째 감지기: 10거래일 누적 β 조정 초과수익 {g:+.1f}{u} = 10일 분포 2.3σ(기준 2σ). 하루 최대 −{abs(g) * 0.16:.1f}{u} = 평소 1.5배(하루 기준 3배 미달). 하루 감지기와 따로 돌고, 둘 다 걸리면 하루 쪽이 먼저'),
             ("뉴스", "A5 10거래일 누적 1위 이슈 묶음 = " + ("RATES_FED 41건 · INFLATION 19건 (‘인상 우려’ 꾸준히)" if t == "A" else "AI_CAPEX 33건 · EARNINGS 15건 (‘투자 둔화 우려’ 꾸준히)") + " → 뉴스 동반(지속 가중). 하루에 몰린 뉴스가 아니라 열흘 내내 같은 이야기"),
             ("왜 따로 두나", "하루 3배 기준은 1년에 2~4번 — 조용한 하락은 그 사이를 빠져나간다(지표 검증의 ‘H4 조용한 하락’ 가설과 같은 자리). 반등 vs 지속 기록은 급락과 따로 센다(종류 = 느린 누적)")]
    expl = [("상황", f'{T["subject"]}이 열흘 동안 하루 {abs(g) * 0.1:.1f}{u} 안팎으로 조금씩 내려 누적 {g:+.1f}{u} (가상). 하루로는 어느 날도 기준에 안 걸림. 뉴스는 열흘 내내 같은 걱정.'),
            ("코드가 한 일", "둘째 감지기(10거래일 누적 2σ)가 걸린 날 장 마감 뒤 틀 R 로 등록 — 자는 10거래일 전 종가 기준, 갈래는 급락과 같은 반등 vs 하락 지속, 우리 전망은 뉴스 동반이라 지속 가중."),
            ("독자가 보는 것", f'제목 ‘{fc["title"]}’, 날짜 줄 `감지 : 10거래일 누적 {g:+.1f}{u}`, 첫 문장 "하루 기준엔 안 걸리게 조금씩 내렸습니다". 나머지는 급락 페이지와 같다.'),
            ("내부 기록", "종류 = 느린 누적(급락과 따로), 감지 σ, 뉴스 누적 묶음. 선반영(상황 13)과 짝 — 뻔한 결과가 가까이 있으면 선반영 쪽으로 등록된다(일정 있음 우선).")]
    return expl, [("전망 페이지 (느린 누적 → 지속 조짐)", H.forecast_body({"id": f"EH-{t}-slow"}, st, fc, others=[], op=op_for(t, fc, st, extra=extra)))]


# ---------------------------------------------------------------- 앞으로 올 수 있는 일 — 경고 · 대비 카드 (2026-11-07 사용자: 묘사가 아니라 "이렇게 되면 이런 일이 올 수 있으니 미리 생각해 두자"). 숫자는 가상
def prepare_for(t, fc, st, mood):
    """사건 × 지금 분위기 × 기록 → 조건부 경고 둘셋 + 볼 것 + 사슬 한 줄. 결과가 이미 난 전망은 ‘다음에 올 수 있는 일’(세부 전망 · 사슬 다음 고리)."""
    T, L, u = TIERS[t], TIERS[t]["line"], TIERS[t]["unit"]
    sub = T["subject"]
    res = st.get("result")
    bad = mood == "위험 회피"
    if fc["kind"] == "pre" and not res:
        if t == "A":
            items = [(f'금리를 내려도', ("지금처럼 시장이 위험 회피일 때 인하 뒤 20거래일에 S&P 500 이 오른 건 기록상 12번 중 5번. 침체 걱정 속 인하는 묻히곤 했습니다 (2001 · 2007)" if bad else
                                  "시장이 차분할 때 인하 뒤 20거래일에 S&P 500 이 오른 건 기록상 35번 중 25번. 보험성 인하는 이어지곤 했습니다 (1995 · 1998 · 2019)"), "발표 뒤 이틀 10년 금리 · 달러가 같이 내리는지"),
                     ("동결 · 인상이면", f"시장이 {fc.get('market_prob', {}).get('probs', [0])[0]}%로 인하를 봤던 터라 예상 밖. 당일 하루 큰 움직임(기록상 18번 중 13번 기준 넘음)이 흔했습니다", "당일 종가 · 다음 날 되돌림 여부"),
                     ("그 전에 먼저 움직이면", "발표 전 열흘 동안 먼저 오르면 발표 날 ‘뉴스에 팔기’ 되돌림이 기록상 29번 중 16번", "발표 전 열흘 누적")]
            chain = "번지는 순서(사슬) : 금리 → 달러(0~5일) → 성장주 · 기술주(0~10일) → 신흥국 · 한국(1~10일). 다음 고리가 기준을 넘으면 세부 전망으로 잇습니다."
        else:
            who = "반도체가 시장보다" if t == "B" else "엔비디아가 반도체보다"
            items = [("실적이 예상을 넘어도", (f"지금처럼 시장이 위험 회피이고 뉴스가 부정 70% 넘을 때는 좋은 실적 뒤 20거래일에 {who} 오른 게 기록상 9번 중 3번. 좋은 실적이 묻힐 수 있습니다" if bad else
                                       f"시장이 차분할 때 좋은 실적 뒤 20거래일에 {who} 오른 게 기록상 11번 중 8번"), "발표 다음 날 " + ("반도체 vs 시장" if t == "B" else "엔비디아 vs 반도체") + " · 뉴스 분위기가 바뀌는지"),
                     ("예상에 못 미치면", ("하방 압력이 있을 때 실망 실적의 급락 폭은 평소의 1.6배. 기록상 7번 중 6번 기준을 넘었습니다" if bad else "실망 실적 뒤 급락은 기록상 9번 중 6번 기준을 넘었고, 그 뒤 20거래일 반등은 절반쯤"), "급락 뒤엔 ‘급락, 반등할까 더 빠질까?’ 세부 전망으로 이어 갑니다"),
                     ("그 전에 먼저 움직이면", "발표 전 열흘 동안 먼저 빠지면 발표 날 되돌림이 기록상 12번 중 7번. 선반영", "발표 전 열흘 누적 · 옵션 예상 폭")]
            chain = "번지는 순서(사슬) : 엔비디아 → 반도체 지수(당일~이틀) → 삼성 · 하이닉스(한국 다음 날) → 전력 · 데이터센터(1~20일)."
        lead = f'{T["event"]}을 앞두고 미리 생각해 둘 것입니다. 지금 시장 분위기는 {mood}입니다.'
        return {"lead": lead, "items": items, "chain": chain, "answer": "미리 생각해 둘 것"}
    if fc["kind"] == "after" and not res:
        rw = fc["scenarios"][0]["name"]; cont = fc["scenarios"][1]["name"]
        items = [(f"‘{rw}’ 쪽으로 가면", f"{H.SHOCK[1 if fc['gap'] > 0 else -1]} 폭의 절반을 되찾는 데 기록상 보통 8~15거래일, 되찾은 뒤 다시 빠진 적은 20번 중 6번", "되찾은 비율이 4분의 1을 넘는 날 · 그날 뉴스"),
                 (f"‘{cont}’ 쪽으로 가면", ("지금처럼 시장이 위험 회피일 때 지속은 기록상 20번 중 12번. 시장 전체가 같이 빠질 때가 많았습니다" if bad else "시장이 차분할 때 지속은 기록상 20번 중 7번"), "시장도 같이 빠지는지(범위 비율) · 불안 지수"),
                 ("둘 다 아닌 채 머물면", "60거래일 동안 기준 안에 머문 건 기록상 20번 중 3번", "최종 확인일까지")]
        chain = "번지는 순서(사슬) : " + ("시장 → 업종 → 종목 순으로 내려오고, 아래 층이 스스로 기준을 넘으면 세부 전망으로 잇습니다." if t == "A" else "업종이 빠지면 종목(엔비디아 · 삼성 · 하이닉스)이 뒤따르고, 전력 · 데이터센터로 번지는지 봅니다.")
        return {"lead": f'{fc["event"]} 뒤 올 수 있는 일입니다. 지금 시장 분위기는 {mood}입니다.', "items": items, "chain": chain, "answer": "미리 생각해 둘 것"}
    # 결과가 난 뒤. 다음에 올 수 있는 일
    nxt = fc.get("follow") or {}
    items = [("이대로 이어지면", "기준을 넘은 뒤 20거래일 더 같은 방향으로 간 건 기록상 30번 중 14번", "세부 전망의 지속 기준"),
             ("되돌리면", "기준을 넘은 뒤 절반 넘게 되돌린 건 기록상 30번 중 11번", "되찾은 비율")]
    return {"lead": f'결과({st["result"]["word"]})가 난 뒤 다음에 올 수 있는 일입니다.' + (f' 세부 전망 ‘{nxt["title"]}’ 에서 이어 갑니다.' if nxt.get("title") else ""), "items": items,
            "chain": "", "answer": "다음에 올 수 있는 일"}


def case_dday(t):
    """상황 15 — 실적 D-day 를 앞두고 시장 분위기가 위험 회피(규제 · 데이터센터 뉴스 · 부정 보도)일 때: 좋은 실적이 묻힐 수 있다는 경고가 맨 위에."""
    tt = "B" if t == "A" else t   # 거시 탭에서도 실적 사례로 보여 준다(FOMC 는 상황 1 · 13)
    T = TIERS[tt]
    L, u, ev = T["line"], T["unit"], T["event_day"]
    days = tdays((date.fromisoformat(ev) - timedelta(days=16)).isoformat(), 14)
    ei = next(i for i, d in enumerate(days) if d >= ev)
    rel = path([(0, 0), (ei - 1, -L * 0.6)], ei, wig=L * 0.05)   # 발표 전 열흘 먼저 빠지는 중 (하방 압력)
    rel = rel + [None] * (len(days) - len(rel))
    fc = pre_fc(tt, cond=None, T=dict(T, market_prob={"probs": [62, 38], "src": "예상치 상향 비율 · 옵션 예상 폭, 등록일"}))
    fc.update(detect_day=days[0], registered=days[0], posted=H.md(days[0]), history=T["hist_pre"],
              start_text=f'{T["event_short"]} 열흘 전. 시장 분위기가 위험 회피라 미리 적어 둡니다 — 좋은 실적이 묻힐 수 있는 때입니다.')
    fc["dates"] = [["게시", H.md(days[0])], ["감지", f"{H.md(days[0])} 하방 압력 · 뉴스 부정 72%"], ["사건", H.md(ev)], ["시장 예상", "예상을 크게 넘음 62%"], ["결과", "결과 전"]]
    st = run(fc, days, rel, cond=None, vix=vix_for(rel, 24) if T["vix"] else None, volume_x=1.4)
    st["label_at"] = [0, ei // 2, len(days) - 1]
    fc["pressure"] = pressure(tt, "shock")
    fc["prepare"] = prepare_for(tt, fc, st, "위험 회피")
    fc["prepare"]["lead"] = f'{T["event"]}이 열흘 뒤입니다. 그런데 지금 시장은 위험 회피이고(규제 · 데이터센터 뉴스, 부정 보도 72%), 발표 전부터 {T["subject"]}가 먼저 빠지는 중입니다. 이럴 때 미리 생각해 둘 것입니다.'
    extra = [("경고 카드 규칙", "사건 × 배경(시장 분위기 · 뉴스 방향 · 충격 국면) × 기록(그 배경에서 같은 사건 뒤 n번 중 m번) → 조건부 문장 둘셋 + 볼 것 + 사슬. 배경 조건별 기록은 사건표 + 매일 기록에서 코드가 셈(처음엔 30년 사건표 대리: 실적 + VIX>25 국면). 매수 · 매도 · 비중 말 금지, 날짜 붙은 ‘위험 구간’ 아님 — 사건 하나에 묶인 조건부 경고"),
             ("왜 지금 경고인가", "배경이 ‘위험 회피 + 뉴스 부정 70% 넘음 + 발표 전 선반영 하락’ 셋 다 켜짐 → 기록상 좋은 실적이 묻힌 비율이 평소(11번 중 3번)보다 높은 구간(9번 중 6번) — 가상 숫자")]
    expl = [("상황", f'{T["event"]} 열흘 전. 규제 · 데이터센터 건립 뉴스로 시장이 위험 회피, 보도도 부정 72%. {T["subject"]}는 발표 전부터 하루 조금씩 먼저 빠지는 중(선반영). 실적이 좋아도 묻힐 수 있는 때 (가상).'),
            ("코드가 한 일", "배경 세 가지(분위기 · 뉴스 방향 · 선반영)가 켜지자 D-day 열흘 전에 등록하고 맨 위에 ‘앞으로 올 수 있는 일’ 카드: 실적이 넘어도 / 못 미치면 / 먼저 움직이면 — 각각 그 배경에서의 기록 비율과 볼 것. 사슬 한 줄(엔비디아 → 반도체 → 삼성 · 하이닉스 → 전력)."),
            ("독자가 보는 것", "맨 위 주황 카드 `앞으로 올 수 있는 일 : 미리 생각해 둘 것` 세 줄 + 볼 것. 그 아래는 평소 전망 페이지. 날마다 국면 문장 끝에 ‘기준까지 1.2%p 남았습니다 — 넘으면 …’ 꼬리."),
            ("내부 기록", "경고 카드가 켜진 조건(배경 셋) · 기록 비율 · 날짜를 registered 줄에. 결과가 나면 ‘경고가 맞았나’ 도 센다(묻힘 = 좋은 실적인데 20거래일 기준 못 넘음).")]
    return expl, [("전망 페이지 (D-day 열흘 전 · 경고)", H.forecast_body({"id": f"EH-{t}-dday"}, st, fc, others=[], op=op_for(tt, fc, st, extra=extra)))]


# ---------------------------------------------------------------- 지도 13-5 순서대로: ① 한국은 어떻게? ② 보류 · 무효 ③ 번복 · 연속 (2026-11-07 사용자 "순서대로 넣어줘")
def korea_for(t, fc=None):
    """미국 사건 → 한국 다음 날. 비율 · 배수는 2016~ 실측(hypo_pages 머리말), 그 밖은 가상."""
    if t == "A":
        rows = [("코스피", "10번 중 8번 같은 방향", "S&P 500 이 하루 3% 넘게 움직인 날 뒤 · 크기는 보통 4분의 1 (0.28배)"), ("원/달러", "위험 회피면 원화 약세", "달러 강세 · 외국인 매도와 같이"), ("한국 반응 확인", "다음 날 아침 9시 · 종가", "")]
        lead = "미국 지수의 큰 움직임은 다음 날 아침 한국장으로 연결됩니다. 기록상(2016년부터) 코스피는 이랬습니다."
    else:
        rows = [("코스피", "10번 중 8번 같은 방향", "반도체 지수가 하루 3% 넘게 움직인 날 뒤 · 크기는 보통 4분의 1 (0.26배)"), ("KODEX 반도체 (삼성 · 하이닉스)", "10번 중 8번 같은 방향", "크기는 보통 5분의 2 (0.38배)"), ("코스닥", "10번 중 7번 같은 방향", "0.23배")]
        lead = ("엔비디아 실적은 미국 장 마감 뒤라 다음 날 아침 한국장으로 연결됩니다. " if t == "C" else "미국 반도체의 큰 움직임은 다음 날 아침 한국장으로 연결됩니다. ") + "기록상(2016년부터) 한국은 이랬습니다."
    return {"lead": lead, "rows": rows, "note": "같은 방향으로 가는 비율이지 크기까지 같다는 뜻은 아닙니다. 한국만의 사건(환율 · 수급)이 겹치면 달라집니다."}


def case_hold_void(t, days, end):
    """상황 16 — ① 판정 보류: 결과가 두 조건 어느 쪽도 아님(동결인데 인상 예고 / 실적은 넘었는데 가이던스 하향) ② 무효: 발표 연기."""
    T = TIERS[t]; L, u = T["line"], T["unit"]
    # ① 보류
    rel = path([(0, 0), (2, -L * 0.3), (5, L * 0.2), (8, -L * 0.4)], 12, wig=L * 0.05)
    f1 = pre_fc(t, cond=None)
    f1["history"] = T["hist_pre"]
    am = {"A": {"outcome": "동결 + 다음 회의 인상 예고", "why": "인하도 동결 · 인상도 아닌 ‘동결이지만 인상 쪽’ 이라 코드가 둘 중 하나로 매길 수 없습니다."},
          "B": {"outcome": "주당순이익은 크게 넘었지만 다음 분기 안내는 낮춤", "why": "‘크게 넘음’ 이면서 ‘그 밖’ 이기도 해서 코드가 둘 중 하나로 매길 수 없습니다."},
          "C": {"outcome": "주당순이익은 크게 넘었지만 데이터센터 매출 안내는 낮춤", "why": "‘크게 넘음’ 이면서 ‘그 밖’ 이기도 해서 코드가 둘 중 하나로 매길 수 없습니다."}}[t]
    f1["ambiguous"] = am
    f1["dates"] = [d for d in f1["dates"] if d[0] != "결과"] + [["결과", f'{H.md(T["event_day"])} {am["outcome"][:14]}… · 보류']]
    st1 = run(f1, days[:12], rel, cond=1, vix=vix_for(rel) if T["vix"] else None, end=end)
    for sc in f1["scenarios"]:
        for c in sc["chain"]:
            c["state"] = "no"
    f1["prepare"] = {"answer": "채점하지 않음", "lead": "결과가 미리 적은 두 조건 어느 쪽도 아니었습니다. 이 전망은 맞음 · 틀림을 세지 않고 움직임만 적습니다.",
                     "items": [("다음부터는", "같은 사건에 조건을 셋으로 둘지(동결 · 인상 예고를 따로) 분기 점검 때 정합니다. 지금 전망은 고치지 않습니다", "")], "chain": ""}
    f1["korea"] = korea_for(t)
    # ② 무효
    f2 = pre_fc(t, cond=None)
    nd = tdays(T["event_day"], 12)[-1]
    f2["void"] = {"day": T["registered"], "text": f'{T["event"]} 발표가 {H.md(nd)}로 미뤄져 이 전망은 무효입니다. 새 날짜로 세부 전망 ‘{f2["title"]}’ 을 다시 적습니다.'}
    f2["dates"] = [["게시", H.md(T["registered"])], ["사건", f'{H.md(T["event_day"])} → {H.md(nd)} 연기'], ["결과", "무효"]]
    f2["slug"] = f2["slug"] + "-void"
    st2 = run(f2, [], [], cond=None)
    f2["prepare"] = {"answer": "다시 적음", "lead": f'사건이 {H.md(nd)}로 미뤄졌습니다. 미룬 사건은 미리 적은 조건이 그대로라 새 날짜로 다시 적고, 이 전망은 성적표에서 세지 않습니다.', "items": [], "chain": ""}
    score = {"n": 9, "hit": 4, "miss": 1, "neither": 1, "watch": 1, "hold": 1, "void": 1, "picked_hit": (3, 4), "note": "보류 · 무효 · 겹친 전망은 따로 셉니다."}
    expl = [("상황", f'① {T["event"]} 결과 = {am["outcome"]} — 두 조건 어느 쪽도 아님. ② 같은 사건이 {H.md(nd)}로 연기 (둘 다 가상).'),
            ("코드가 한 일", "① 결과 코드가 두 값 중 하나로 안 떨어지면 ‘판정 보류’: 채점 안 하고 날마다 움직임만 적음, 고리 전부 해당 없음, 성적표 ‘판정 보류 1개 (세지 않음)’. ② 일정표에서 날짜가 바뀌면 ‘무효’: 전망을 멈추고 새 날짜로 세부 전망 등록. 사람 손 없이 둘 다 자동 — 자동화가 멈추지 않기 위한 상태."),
            ("독자가 보는 것", "① 맨 위 ‘판정 보류’(회색) + 왜 보류인지 한 문장, 경고 카드는 ‘채점하지 않음’. ② 맨 위 ‘무효’ + 새 날짜 · 세부 전망 링크."),
            ("내부 기록", "결과 = 보류 / 무효 · 사유. 분기 점검 때 보류가 잦은 사건은 조건을 셋으로 늘릴지 결정(사전 등록 원칙: 지금 전망은 안 고침).")]
    return expl, [("① 판정 보류", H.forecast_body({"id": f"EH-{t}-h"}, st1, f1, others=[], op=op_for(t, f1, st1, extra=[("보류 사유", am["why"])]))),
                  ("② 무효 (연기)", H.forecast_body({"id": f"EH-{t}-v"}, st2, f2, others=[], op=op_for(t, f2, st2, extra=[("무효 사유", "earnings.csv / fomc.csv 날짜 변경 감지")]))),
                  ("목록 페이지 (성적표에 보류 · 무효)", H.list_body([], {}, done=[(f1["title"], "—", "판정 보류"), (f2["title"], "—", "무효")], score=score))]


def case_reversal(t):
    """상황 17 — 번복: 관세 충격(틀 R) → 사흘 뒤 유예 발표로 급반등(반등 맞음) → 일주일 뒤 철회로 다시 급락 → 같은 사건 2회차. 성적표에서 번복 묶음은 한 건."""
    T = TIERS[t]; L, u = T["line"], T["unit"]
    sd = tdays("2027-02-01", 40)
    rel = path([(0, 0), (1, -L * 1.2), (2, -L * 1.3), (4, -L * 0.5), (5, -L * 0.3), (9, -L * 0.2), (10, -L * 1.4), (12, -L * 1.6), (15, -L * 1.3)], 17, wig=L * 0.04)
    dd = sd[:17]
    f1 = after_fc(t, 1, round(rel[2], 1), dd[2], dd[1], dd[0], pick=1, title_event="급락", T=dict(T, news=True))
    f1["end_day"] = tdays(dd[2], 61)[-1]
    f1["event"] = f"{H.md(dd[1])} 관세 발표"
    f1["dates"][1] = ["사건", f"{H.md(dd[1])} 전 품목 관세 발표"]
    st1 = run(f1, dd[:9], rel[:9], vix=vix_for(rel[:9], 24) if T["vix"] else None, volume_x=2.8)
    # 2회차 — 철회(dd[10]) 뒤 다시 급락
    rel2 = [None if v is None else round(v - rel[9], 2) for v in rel]
    f2 = after_fc(t, 2, round(rel2[11], 1), dd[11], dd[10], dd[9], pick=1, title_event="급락", T=dict(T, news=True))
    f2["end_day"] = tdays(dd[11], 61)[-1]
    f2["title"] = f'{T["subject"]} 급락 2회차, 반등할까 더 빠질까?'
    f2["event"] = f"{H.md(dd[10])} 유예 철회"
    f2["dates"] = [["게시", H.md(dd[11])], ["번복", f"{H.md(dd[10])} 유예 철회 (같은 사건 2회차)"], ["최종", H.md(f2["end_day"])], ["첫 확인", H.md(tdays(dd[11], 6)[-1])]]
    f2["reversal_of"] = (f1["title"], f1["slug"], 2)
    f2["start_text"] = f'{H.md(dd[4])} 유예로 되찾았던 것을 {H.md(dd[10])} 철회로 다시 내줬습니다. 같은 사건의 2회차로 적고 다음 거래일부터 봅니다.'
    st2 = run(f2, dd, rel2, vix=vix_for(rel2, 26) if T["vix"] else None, volume_x=2.1)
    st2["log"][0]["text"] = f2["start_text"]
    for f in (f1, f2):
        f["korea"] = korea_for(t); f["pressure"] = pressure(t, "shock")
    f1["prepare"] = {"answer": "다음에 올 수 있는 일", "lead": f'‘{f1["scenarios"][0]["name"]}’ 이 맞은 뒤 — 유예 뉴스로 되찾은 반등이라 번복될 수 있습니다.',
                     "items": [("유예가 철회되면", "유예 → 철회가 되풀이된 2025년에 철회 뒤 급락은 5번 중 4번 첫 급락보다 작았습니다", "같은 사건 2회차로 적습니다 · 철회 뉴스"), ("유예가 굳어지면", "협상 타결 뉴스 뒤 20거래일 상승 지속은 5번 중 3번", "협상 일정")], "chain": ""}
    f2["prepare"] = prepare_for(t, f2, st2, "위험 회피"); f2["prepare"]["lead"] = "같은 사건이 뒤집힌 2회차입니다. 2025년 관세 유예 · 철회 반복 때 2회차 급락은 첫 급락보다 작았고, 되찾는 데 걸린 날도 짧았습니다(5번 중 4번)."
    score = {"n": 9, "hit": 5, "miss": 1, "neither": 1, "watch": 2, "picked_hit": (4, 5), "note": "번복된 사건(2회차)은 묶어 한 건으로 셉니다."}
    expl = [("상황", f'{H.md(dd[1])} 관세 발표로 급락 → {H.md(dd[4])} 유예 발표로 급반등(1회차 ‘반등’ 맞음) → {H.md(dd[10])} 유예 철회로 다시 급락 → 2회차 (가상, 2025년 모양).'),
            ("코드가 한 일", "같은 사건 키워드(관세) · 같은 사슬(TARIFF)의 충격이 1회차 창 안에서 반대로 뒤집히면 ‘번복’: 1회차는 판정대로 두고(맞음), 2회차를 새 전망으로 등록하되 ‘같은 사건 n회차’ 로 묶는다. 성적표는 묶음을 한 건으로(첫 회차 결과), 번복 횟수는 따로 센다."),
            ("독자가 보는 것", "2회차 날짜 줄 ‘번복 : 유예 철회 (같은 사건 2회차)’, 첫 문장 ‘되찾았던 것을 다시 내줬습니다’, 경고 카드에 2025년 반복 기록. 1회차 페이지의 ‘다음에 올 수 있는 일’에 ‘유예가 철회되면’."),
            ("내부 기록", "번복 = 1회차 slug · 회차 번호 · 뒤집은 날 1위 이슈. 묶음 성적 · 번복 횟수 · 회차별 폭(2회차가 작았나)을 쌓는다.")]
    return expl, [("2회차 페이지", H.forecast_body({"id": f"EH-{t}-r"}, st2, f2, others=[(1, f1["title"], f1["slug"])], op=op_for(t, f2, st2, extra=[("번복", f'1회차 {f1["slug"]} · 뒤집은 날 {H.md(dd[10])} 1위 이슈 TARIFF_TRADE 48건 (유예 철회) · 2회차 폭 {abs(f2["gap"]):.1f}{u} < 1회차 {abs(f1["gap"]):.1f}{u}')]))),
                  ("1회차 페이지 (반등 맞음)", H.forecast_body({"id": f"EH-{t}-r"}, st1, f1, others=[(2, f2["title"], f2["slug"])], op=op_for(t, f1, st1))),
                  ("목록 페이지 (번복 묶음)", H.list_body([], {}, done=[(f1["title"], f1["scenarios"][0]["name"], "맞음 · 번복 2회차 진행 중")], score=score))]


def case_season(t):
    """상황 18 — 연속 사건: 빅테크 실적 주간(화 · 수 · 목 4건)을 묶음 전망 하나로. 조건 = ‘넷 중 셋 이상 예상 넘음 / 그 밖’, 자 = 마지막 결과일 종가부터, 구성 사건은 따로 등록하지 않는다(겹침 없음)."""
    week = tdays("2027-01-26", 3)
    last = week[-1]
    T = {"name": "업종", "subject": "기술주", "subj_ga": "기술주가", "subj_eun": "기술주는", "cmp": "시장보다", "unit": "%p", "line": 2.5,
         "ruler_short": "기술주 vs 시장", "event": f"{H.md(week[0])}~{H.md(last)} 빅테크 실적 주간", "event_short": "빅테크 실적 주간", "event_day": last, "registered": tdays("2027-01-19", 3)[-1],
         "outcomes": ["넷 중 셋 이상 예상 넘음", "그 밖"], "conds": ["넷 중 셋 이상이 예상을 넘으면", "그 밖이면"], "dirs": [1, -1],
         "middle": ["AI 투자가 이어진다는 확인", "AI 투자 둔화 걱정"], "tags": ["실적 시즌", "기술주"], "vix": True, "beta": 1.2,
         "src": "주간 전 7일 방송 5곳 · 뉴스 44건에서 가장 많이 나온 설명", "market_prob": {"probs": [55, 45], "src": "넷의 예상치 상향 비율 평균, 등록일"},
         "hist_pre": {"what": "빅테크 넷 중 셋 이상이 예상을 넘은 실적 주간이", "n": 14, "since": 2019, "rows": [["5거래일 뒤", 9, "−1.4 ~ +2.6%p"], ["20거래일 뒤", 9, "−2.9 ~ +4.3%p"], ["60거래일 뒤", 8, "−4.8 ~ +7.0%p"]],
                      "alike": [["2023.07", "AI 수요 확인 주간", "+3.1%p"], ["2024.10", "투자 늘리겠다 · 주가는 엇갈림", "−0.8%p"], ["2025.01", "딥시크 쇼크 직후 주간", "+1.4%p"]]},
         "what": "묶음 전망 — 사건 4건을 하나로"}
    L, u = T["line"], T["unit"]
    days = tdays(last, 30)
    rel = path([(0, 0), (2, L * 0.4), (5, L * 0.9), (8, L * 1.1)], 12, wig=L * 0.05)
    fc = pre_fc("B", cond=1, T=T)
    fc["slug"] = f"case-season-{t}"; fc["history"] = T["hist_pre"]; fc["end_day"] = tdays(last, 61)[-1]
    fc["dates"] = [["게시", H.md(T["registered"])], ["사건", f'{T["event"]} (4건)'], ["시장 예상", "셋 이상 넘음 55%"], ["최종", H.md(fc["end_day"])], ["결과", f"{H.md(last)} 넷 중 셋 넘음 · 예상대로"]]
    fc["start_text"] = "빅테크 넷의 실적이 한 주에 몰려 있어 하나로 묶어 적었습니다. 마지막 발표 다음 날 종가부터 잽니다."
    a = fc["scenarios"][0]
    a["chain"] = [{"step": "마이크로소프트 · 알파벳 (화)", "state": "done", "ev": "둘 다 예상 넘음", "date": ""}, {"step": "메타 (수)", "state": "done", "ev": "예상 넘음 · 투자 늘림", "date": ""},
                  {"step": "아마존 · 애플 (목)", "state": "done", "ev": "아마존 넘음 · 애플 못 미침 → 넷 중 셋", "date": ""}, {"step": "AI 투자가 이어진다는 확인", "state": "done", "ev": "넷의 투자 계획 합계 ↑", "date": ""}, {"step": "기술주 상승", "state": "done", "ev": "", "date": ""}]
    fc["scenarios"][1]["chain"] = [dict(c, state="no") for c in fc["scenarios"][1]["chain"]]
    st = run(fc, days[:12], rel, cond=1, vix=vix_for(rel, 17) if T["vix"] else None, end=fc["end_day"], volume_x=1.7)
    fc["pressure"] = pressure("A", "riskon"); fc["korea"] = korea_for("B"); fc["prepare"] = prepare_for("B", fc, st, "위험 선호")
    extra = [("묶음 규칙", "일정표에서 같은 업종 실적이 5거래일 안에 3건 이상이면 묶음 전망 하나(구성 사건은 따로 등록 안 함 → 겹침 없음). 조건 = ‘n 중 m 이상 넘음’(m = 과반 올림), 자 = 마지막 결과일 종가부터 업종 vs 시장, 고리 = 구성 사건 하나씩 확인. 한 종목만 보려면 종목 페이지의 실적 카드"),
             ("지표 주간도 같은 틀", "CPI · 고용 · GDP 가 한 주에 몰리면 ‘지표 주간’ 묶음 — 조건 ‘셋 중 둘 이상 예상보다 뜨거움/차가움’, 자 = 10년 금리 · S&P 500")]
    expl = [("상황", f'{T["event"]}: 화 마이크로소프트 · 알파벳, 수 메타, 목 아마존 · 애플. 넷 중 셋이 예상 넘음 → ‘기술주 상승’ 조짐 → 맞음 (가상).'),
            ("코드가 한 일", "실적 4건을 사건 하나(묶음)로 등록 — 따로 등록하면 겹침 규칙으로 전부 ‘복합’ 이 되어 성적에서 빠진다. 조건을 ‘넷 중 셋 이상’ 으로, 고리에 구성 사건을 한 줄씩, 자는 마지막 발표 다음 날부터."),
            ("독자가 보는 것", "제목 ‘빅테크 실적 주간 뒤 기술주는?’, 사건 줄 ‘(4건)’, 고리에 회사별 확인 · 대기, 기록 카드 ‘셋 이상 넘은 주간 14번 중 9번’."),
            ("내부 기록", "묶음 = 구성 사건 id 넷 · 각 결과. 분기 점검 때 ‘묶음 vs 종목별’ 어느 쪽이 더 맞았나 비교.")]
    return expl, [("묶음 전망 페이지", H.forecast_body({"id": f"EH-{t}-season"}, st, fc, others=[], op=op_for("B", fc, st, extra=extra)))]


# ---------------------------------------------------------------- 상황 열하나
SITU = [
    ("1", "사건 전 · 등록"), ("2", "진행 중 · 조짐"), ("3", "맞음"), ("4", "틀림"), ("5", "어느 쪽도 아님"),
    ("6", "겹침"), ("7", "이어가기 · 진행"), ("8", "이어가기 끝 · 사건 닫기"), ("9", "충격에서 시작 · 틀림"),
    ("10", "돌발 사건 (전쟁 · 재해 · 유가)"), ("11", "동시다발 (돌발 + 실적 · 금리)"), ("12", "파급 (시장 → 업종 → 종목)"),
    ("13", "선반영 (뻔한 결과)"), ("14", "느린 누적 (조용한 하락)"), ("15", "D-day 앞 하방 압력 (실적이 묻힐 때)"), ("16", "판정 보류 · 무효"), ("17", "번복 (유예 → 철회)"), ("18", "연속 사건 (실적 시즌 묶음)"),
]


def case(t, k):
    """→ (설명 줄들, [(소제목, 본문 html)])"""
    T = TIERS[t]
    L, u = T["line"], T["unit"]
    ev = T["event_day"]
    days = tdays(ev, 64)            # 사건일(기준일) 부터 창 60거래일 + 여유
    end = days[60]
    vx = T["vix"]
    others = []

    def page(fc, st, oth=None, op=None):
        fc.setdefault("pressure", pressure(t, "shock" if k in ("4", "9", "11") else ("calm" if k in ("1", "2", "5") else "riskon")))
        fc.setdefault("prepare", prepare_for(t, fc, st, fc["pressure"]["answer"]))
        fc.setdefault("korea", korea_for(t))
        return H.forecast_body({"id": f"EH-{t}", "forecasts": [fc]}, st, fc, others=oth if oth is not None else others, op=op or op_for(t, fc, st))

    if k == "12":
        return case_cascade(t)
    if k == "16":
        return case_hold_void(t, days, end)
    if k == "17":
        return case_reversal(t)
    if k == "18":
        return case_season(t)
    if k == "15":
        return case_dday(t)
    if k == "13":
        return case_priced(t)
    if k == "14":
        return case_slow(t)
    if k == "10":
        return case_sudden(t, days)
    if k == "11":
        return case_concur(t, days, end)
    if k == "1":
        fc = pre_fc(t)
        fc["history"] = T["hist_pre"]
        st = run(fc, [], [], cond=None)
        expl = [("상황", f'{T["event"]} 3거래일 전({H.md(T["registered"])}) 장 마감 뒤. 아직 결과 전.'),
                ("코드가 한 일", f'일정표에서 사건을 골라 틀 S 로 등록 — 조건 둘({T["conds"][0]} · {T["conds"][1]}) · 갈래 이름 · 금({L:g}{u}) · 고리를 규칙으로 채움. 방향은 사건 전 7일 방송 · 뉴스 설명(Groq), 모자라면 기록상 분포.'),
                ("독자가 보는 것", "전망 결과 = 지켜보는 중 한 줄. 두 갈래 다 지켜보는 중, 그래프 없음(잴 것이 아직 없다)."),
                ("내부 기록", "registered 한 줄(등록 시각 = 상태 저장소 커밋 + 블로그 첫 발행).")]
        return expl, [("전망 페이지", page(fc, st))]

    if k in ("2", "3", "4", "5", "6"):
        keys = {"2": [(0, 0), (2, L * 0.2), (4, L * 0.45)],
                "3": [(0, 0), (1, L * 0.5), (3, L * 1.15)],
                "4": [(0, 0), (2, L * 0.25), (4, -L * 0.4), (7, -L * 1.1)],
                "5": [(0, 0), (8, L * 0.5), (20, -L * 0.4), (35, L * 0.3), (50, -L * 0.2), (60, L * 0.1)],
                "6": [(0, 0), (6, L * 0.3), (12, L * 0.55), (18, L * 0.6)]}[k]
        rel = path(keys, len(days) if k == "5" else 24, wig=L * 0.06)
        dd = days if k == "5" else days[:24]
        fc = pre_fc(t, cond=1)
        fc["history"] = T["hist_pre"]
        if k == "6":
            o = T["overlap"]
            fc["overlap"] = [dict(o, sign="same")]
            others.append((o["no"], o["title"], "case-x"))
        st = run(fc, dd, rel, cond=1, vix=vix_for(rel) if vx else None, end=end)
        sim = [{"releases": ["소비자물가"], "rate10": 0.11, "news": ("금리 인하 기대", "")}, {"rate10": -0.06, "hy": -0.09},
               {"releases": ["고용 보고서"], "rate10": 0.16, "hy": 0.12, "news": ("경기 걱정", "나쁜 이야기가 많았습니다")}, {"news": ("AI 투자", "좋은 이야기가 많았습니다")}]
        for i, e in enumerate(st["log"][1:]):   # 가상 — 날마다 오늘 나온 것 (기획 9-2)
            e["today"] = H.today_line(sim[i % len(sim)])
        if k == "4":   # 틀림의 가치 — 어디서 끊겼나 (2026-11-07 사용자)
            a = fc["scenarios"][0]
            a["chain"][1].update(state="broken", ev={"A": "10년 금리가 내리지 않고 0.18%p 올랐음 (침체 걱정 · 회견이 매파적)", "B": "AI 투자 기대 대신 ‘다음 분기 안내’ 걱정이 뉴스 1위", "C": "데이터센터 매출은 넘었지만 마진 하락이 뉴스 1위"}[t])
            a["chain"][2].update(state="broken", ev="반대로 움직임")
            fork = {"A": ("보험성 인하면 상승 / 침체 대응 인하면 첫 인하 뒤 하락", "침체 대응 쪽 — 기록상 2001 · 2007 첫 인하 뒤에도 S&P 500 이 빠졌습니다"),
                    "B": ("업계 전체 수요 이야기면 업종 동반 / 한 회사 이야기면 경쟁사는 반대", "한 회사 이야기 쪽 — 실적은 좋았지만 업종 전체 수요 신호로 읽히지 않았습니다"),
                    "C": ("업계 전체 수요 이야기면 업종 동반 / 한 회사 이야기면 경쟁사는 반대", "기대가 이미 가격에 있던 쪽 — 넘었지만 ‘충분히 넘지 못했다’ 로 읽혔습니다")}[t]
            fc["broke"] = {"answer": "고리 대조", "lead": f'‘{a["name"]}’ 은 틀렸습니다. 고치지 않고 그대로 두며, 미리 적어 둔 사슬과 대조해 어디서 끊겼는지만 적습니다.',
                           "items": [("끊긴 고리", a["chain"][1]["step"] + " → " + a["chain"][1]["ev"], "고리마다 대리 지표로 코드가 매김"),
                                     ("미리 적어 둔 갈림점", fork[1], f"사슬 사전의 갈림 : {fork[0]} (등록 전에 적힌 것)"),
                                     ("등록 때 경고", "‘금리를 내려도 위험 회피일 때는 인하 뒤 오른 건 기록상 12번 중 5번’ 이라고 적어 두었습니다" if t == "A" else "‘실적이 넘어도 묻힐 수 있다’ 고 적어 두었습니다", ""),
                                     ("다음", f'이 틀림은 ‘{a["chain"][1]["step"]}’ 고리의 기록 비율에 들어가 다음 경고에 쓰입니다. 이어지는 움직임은 세부 전망 ‘{T["subject"]} 급락, 반등할까 더 빠질까?’ 로 적습니다', "")]}
        word = {"2": "조짐", "3": "맞음", "4": "틀림", "5": "어느 쪽도 아님", "6": "겹침"}[k]
        expl = [("상황", {"2": f'결과 = {T["outcomes"][0]}. 나흘 뒤 금의 절반 가까이 움직였지만 아직 금 안.',
                          "3": f'결과 = {T["outcomes"][0]}. 사흘 만에 금({L:g}{u})을 넘음.',
                          "4": f'결과 = {T["outcomes"][0]}. 처음엔 맞는 쪽으로 가다가 반대로 금을 넘음.',
                          "5": f'결과 = {T["outcomes"][0]}. 60거래일 내내 ±{L:g}{u} 안에서 오르내림.',
                          "6": f'결과 = {T["outcomes"][0]}. 조짐이 이어지는 중에 {T["overlap"]["day"]} {T["overlap"]["event"]} 이 창 안에 들어옴.'}[k]),
                ("코드가 한 일", {"2": f"날마다 자를 재서 국면을 매김 — 금의 3분의 1({L / 3:.0f}{u}) 넘으면 `조짐`.",
                                 "3": "금을 넘은 날 바로 `맞음` 판정, 그날로 기록을 멈춤(창 안 어느 날이든 넘으면 맞음). 고리 셋 확인.",
                                 "4": "반대 방향으로 기준을 넘은 날 `틀림` 판정, 고치지 않음. 고리마다 대리 지표로 끊긴 곳을 `끊김` 으로 매기고, 사슬 사전의 갈림점 중 일어난 쪽 · 등록 때 경고와 대조. 틀림은 그 고리의 기록 비율로 들어감.",
                                 "5": "창 끝(D+60)까지 금을 넘지 않아 `어느 쪽도 아님`.",
                                 "6": f'새 사건을 따로 전망 {T["overlap"]["no"]} 로 등록하고, 이 전망에 겹침 표시. 이 전망은 그대로 계속 잼.'}[k]),
                ("독자가 보는 것", {"2": "`○○ 조짐` (색 = 방향, 카드는 회색). 일어난 조건 = 실제 결과 라벨, 다른 조건 = 일어나지 않음(회색 · 접힘).",
                                   "3": "맨 위 큰 글씨 `맞음`(방향 색 카드). 그 갈래 답 = 일어남.",
                                   "4": "맨 위 `틀림` + 바로 아래 `어디서 끊겼나` 카드(끊긴 고리 · 미리 적어 둔 갈림점 · 등록 때 경고 · 다음). 고리 줄에 노란 `끊김` 라벨. 여지 말 없이 틀렸다고 쓰되 왜 끊겼는지를 보인다.",
                                   "5": "맨 위 `어느 쪽도 아님`(회색). 그래프에 창 60일 전체.",
                                   "6": "카드 아래 회색 한 줄: 다른 사건이 들어와 따로 적었고 결과에 두 사건이 겹쳐 있음. 다른 전망 링크."}[k]),
                ("내부 기록", {"2": "날마다 국면 한 줄(records/forecasts).", "3": "결과 = 맞음 · 겹침 = 없음 · 동행 = 상위 3일 이슈 코드.",
                              "4": "결과 = 틀림 · 겹침 없음 → `우리 전망이 맞은 비율` 의 분모에 들어감.",
                              "5": "결과 = 어느 쪽도 아님(맞음 · 틀림 어느 쪽에도 세지 않음, 따로 셈).",
                              "6": "겹침 = 전망 n. 끝나도 `맞은 비율` 에서 뺀다(셋 이상 겹치면 복합)."}[k])]
        return expl, [(f"전망 페이지 ({word})", page(fc, st))]

    if k in ("7", "8"):
        n = 24 if k == "7" else 32
        tail = [(8, L * 0.85), (11, L * 0.8)] if k == "7" else [(8, L * 0.85), (12, L * 0.6), (16, L * 0.55)]
        rel = path([(0, 0), (1, L * 0.5), (3, L * 1.15), (4, L * 1.3)] + tail, n, wig=L * 0.04)
        dd = days[:n]
        reg2 = dd[4]
        f2 = after_fc(t, 2, round(rel[4], 1), reg2, dd[3], ev, pick=1, title_event="급등" if T["dirs"][0] > 0 else "급락")
        f1 = pre_fc(t, cond=1, follow={"no": 2, "title": f2["title"]})
        f1["history"] = T["hist_pre"]
        st1 = run(f1, dd, rel, cond=1, vix=vix_for(rel) if vx else None, end=end)
        f2["end_day"] = tdays(reg2, 61)[-1]
        st2 = run(f2, dd, rel, vix=vix_for(rel) if vx else None)
        oth1 = [(2, f2["title"], f2["slug"])]
        oth2 = [(1, f1["title"], f1["slug"])]
        if k == "7":
            expl = [("상황", f'전망 1 이 {H.md(st1["result"]["day"])} `맞음`. 다음 거래일 장 마감 뒤 같은 사건으로 전망 2(조정 vs {T["subject"]} 상승 지속)를 등록. 지금 조정 조짐.'),
                    ("코드가 한 일", f'맞음 판정 → 틀 R 자동 등록. 충격 폭 = 등록일 자의 값({f2["gap"]:+.1f}{u}, 고정). 우리 전망 = 기록상 더 흔한 쪽(목업은 조정으로 가정). 갈래 이름 · 금 · 고리 · 문장 전부 틀.'),
                    ("독자가 보는 것", "전망 2: 우리 전망 라벨(노랑) · 조정 조짐. 그래프에 조정 금 · 지속 금 두 선. 전망 1 은 맞음에서 멈추고 `전망 2 에서 이어 갑니다`."),
                    ("내부 기록", "전망 1 결과 = 맞음, 전망 2 registered. 두 전망은 같은 사건(EH) 아래 번호만 다름.")]
        else:
            expl = [("상황", "전망 2 에서 오른 폭의 절반을 반납해 `조정`이 일어남 → 우리 전망(조정) 맞음. 사건 닫기."),
                    ("코드가 한 일", "조정 금을 넘은 날 판정 · 기록 멈춤. 같은 사건의 전망이 모두 판정되면 사건을 닫고 목록의 `끝난 전망` 으로 옮김. 창 끝(D+60) 뒤 목록에서 열린 줄이 빠짐."),
                    ("독자가 보는 것", "전망 2 맨 위 `맞음`, 조정 갈래 = 일어남, 지속 갈래 = 일어나지 않음(회색). 목록 페이지 `끝난 전망` 표에 두 줄."),
                    ("내부 기록", "전망 1 · 2 결과 = 맞음 · 맞음, 겹침 없음. 사건 닫힘(closed) 한 줄.")]
        out = [("전망 2 페이지", page(f2, st2, oth2)), ("전망 1 페이지 (맞음에서 멈춤)", page(f1, st1, oth1))]
        if k == "8":
            done = [(f1["title"], f1["scenarios"][0]["name"], "맞음"), (f2["title"], f2["scenarios"][0]["name"], "맞음")]
            score = {"n": 7, "hit": 4, "miss": 1, "neither": 1, "watch": 1, "picked_hit": (3, 4), "note": "두 사건이 겹친 전망 1개는 따로 셉니다."}
            out.insert(1, ("목록 페이지 (사건 닫은 뒤 · 성적표)", H.list_body([], {}, done=done, score=score)))
        return expl, out

    if k == "9":
        s = -1
        g = T["shock"]
        sd = tdays("2026-12-14", 40)   # 일정 없는 충격 — 12.15 하루 큰 하락
        rel = path([(0, 0), (1, g), (2, g * 1.05), (4, g * 0.9), (7, g + s * L * 0.4), (10, g + s * L * 1.4)], 24, wig=abs(g) * 0.02)
        dd = sd[:24]
        fc = after_fc(t, 1, round(rel[2], 1), dd[2], dd[1], dd[0], pick=1, T=dict(TIERS[t], news=False))   # 뉴스 없는 급락(원인 미상) → 규칙이 반등 쪽을 고른다
        fc["end_day"] = tdays(dd[2], 61)[-1]
        st = run(fc, dd, rel, vix=vix_for(rel) if vx else None, volume_x=1.2)
        mine = fc["scenarios"][fc["pick"] - 1]["name"]
        expl = [("상황", f'일정에 없던 큰 하락({H.md(dd[1])}, 평소의 3배 넘게), 그날 1위 뉴스 없음(원인 미상 충격 · 거래량 1.2배). 다음 날 장 마감 뒤 자동 등록. 규칙이 고른 우리 전망 = ‘{mine}’ {fc["pick_prob"] * 100:.0f}%. 잠깐 회복하다가 다시 빠져 ‘{fc["scenarios"][1]["name"]}’ 이 일어남 → {st["result"]["word"]}.'),
                ("코드가 한 일", f'큰 움직임 감지 → 틀 R 등록(AI 호출 0) → 우리 전망 = 뉴스 유무(없음 → 되돌림 가중) + 같은 종류 기록 비율 → {fc["pick_why"]} → 지속 기준을 넘은 날 판정 · 브라이어 {H.brier(fc["pick_prob"], st["result"]["word"] == "맞음")}.'),
                ("독자가 보는 것", f'맨 위 ‘{st["result"]["word"]}’. ‘{mine}’ 갈래 = 우리 전망 라벨 + 기록상 n번 중 m번 줄, 지속 갈래 = 일어남.'),
                ("내부 기록", "결과 · 겹침 없음 · 고정 시점 판정(D+5 · 20) · 브라이어. 충격에서 시작한 사건이라 첫 전망이 틀 R.")]
        return expl, [(f'전망 페이지 ({st["result"]["word"]})', page(fc, st))]


# ---------------------------------------------------------------- 탭 · 설명 상자 (목업 전용)
TAB_CSS = """
<style>
.fc-det summary::-webkit-details-marker{display:none;} .fc-det summary{list-style:none;}
.fc-det:not([open]) .fc-chev{transform:rotate(-90deg);display:inline-block;} .fc-chev{display:inline-block;transition:transform .15s;}
.fc-fold{display:block;width:100%;margin:10px 0 0;padding:8px 0;font:inherit;font-size:14px;line-height:20px;font-weight:700;color:#475569;background:#fff;border:1px solid #CBD5E1;border-radius:8px;cursor:pointer;}
#fc-tabs{position:sticky;top:0;z-index:50;background:#fff;padding:8px 0 8px;border-bottom:1px solid #E2E8F0;margin:0 0 16px;}
#fc-tabs summary{cursor:pointer;font-size:15px;line-height:23px;font-weight:700;color:#111;padding:4px 0;}
#fc-tabs .r{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 0;}
#fc-tabs button.tab{font:inherit;font-size:14px;line-height:20px;padding:6px 10px;border:1px solid #CBD5E1;border-radius:8px;background:#fff;color:#334155;cursor:pointer;}
#fc-tabs button.tab.on{background:#111;color:#fff;border-color:#111;font-weight:700;}
.fc-ex{border:1px solid #FDE68A;background:#FFFBEB;border-radius:8px;padding:0 14px;margin:0 0 16px;font-size:15px;line-height:25px;color:#333;}
.fc-ex summary{padding:10px 0;font-size:17px;line-height:27px;font-weight:700;color:#111;cursor:pointer;}
.fc-ex .body{padding:0 0 12px;} .fc-ex div{margin:0 0 4px;} .fc-ex span.k{display:inline-block;min-width:96px;font-weight:700;color:#92400E;}
.fc-sub{font-size:15px;line-height:23px;font-weight:700;color:#64748B;margin:28px 0 10px;padding:6px 0 0;border-top:2px dashed #CBD5E1;}
.fc-terms{border:1px solid #E2E8F0;border-radius:8px;padding:0 14px;margin:0 0 16px;font-size:15px;line-height:25px;}
.fc-terms summary{padding:10px 0;font-weight:700;cursor:pointer;} .fc-terms .body{padding:0 0 12px;}
</style>"""

TERMS = [("방향", "상승 · 하락 둘뿐"),
         ("사건 전 갈래", "‘{대상} 상승’ · ‘{대상} 하락’ — 조건(사건의 두 결과)마다 하나"),
         ("급락 뒤 갈래", "‘{대상} 반등’ · ‘{대상} 하락 지속’"),
         ("급등 뒤 갈래", "‘{대상} 조정’ · ‘{대상} 상승 지속’"),
         ("반등 · 조정", "빠진 폭의 절반 회복 = 반등, 오른 폭의 절반 반납 = 조정"),
         ("지속", "충격 방향으로 금만큼 더 감"),
         ("국면 (날마다)", "지켜보는 중 · ‘{갈래} 조짐’"),
         ("판정 (맨 위)", "맞음 · 틀림 · 어느 쪽도 아님"),
         ("갈래 답", "지켜보는 중 · 조짐 · 일어남 · 일어나지 않음"),
         ("라벨", "실제 결과(사건 전 전망의 일어난 조건) · 우리 전망(충격 뒤 전망에서 고른 쪽)"),
         ("기록상 n번 중 m번", "같은 종류 사건 뒤 오른 횟수 — 우리 전망의 확률이 되고 내부에서 브라이어 점수로 채점"),
         ("한국은 어떻게?", "미국 사건 → 한국 다음 날 아침. 기록상 같은 방향 비율(10번 중 n번)과 크기 배수 — 2016~ 실측"),
         ("판정 보류 · 무효", "보류 = 결과가 두 조건 어느 쪽도 아님(동결 + 인상 예고) → 채점 안 함. 무효 = 사건 취소 · 연기 · 자료 결함 → 새 날짜로 다시 적음"),
         ("번복 · 연속", "번복 = 같은 사건이 뒤집힘(유예 → 철회) → n회차로 묶어 성적표에 한 건. 연속 = 실적 시즌처럼 여러 건 묶음 전망(조건 ‘넷 중 셋 이상’)"),
         ("앞으로 올 수 있는 일", "맨 위 경고 · 대비 카드 — 다가오는 사건 × 지금 분위기 × 기록 → ‘~하면 … 기록상 n번 중 m번 · 볼 것’. 매수 · 매도 말 없음"),
         ("선반영 중", "뻔한 결과(시장 예상 70% 넘고 뉴스 집중)는 감지일부터 결과 전날까지의 움직임을 따로 보인다. 예상대로 쪽 갈래 = ‘이미 반영’(결과 뒤 더 안 가거나 되돌리면 맞음)"),
         ("조용한 하락", "하루 기준엔 못 미치지만 10거래일 누적이 평소 2배를 넘는 느린 움직임 — 급락처럼 반등 vs 지속으로 적는다"),
         ("시장 예상", "등록 때 시장이 본 확률(FedWatch · 옵션 · 예상치). 결과 줄에 예상대로 · 예상 밖"),
         ("우리 전망 성적표", "목록 맨 위 — 맞음 · 틀림 · 어느 쪽도 아님 · 고른 쪽이 맞은 비율. 겹친 전망은 따로"),
         ("끊김", "고리 상태 — 조건은 일어났는데 그 고리의 대리 지표가 반대로 감. 틀린 전망 맨 위 ‘어디서 끊겼나’ 카드"),
         ("세부 전망", "한 전망의 기간 안에 생긴 다른 사건 · 맞은 뒤 이어가기 · 아래 층 파급을 따로 적은 전망. 번호(전망 2) 대신 제목으로 부른다"),
         ("회색 점선 상자", "운영자 확인용 — 80개 요인 중 쓰인 것 · 이슈 코드 · 범위 비율 · 동행 · 겹침 · 규칙. 블로그에는 안 나감")]


def build():
    tiers = list(TIERS)
    terms = ('<details class="fc-det fc-terms"><summary>용어 (모든 탭 공통) <span class="fc-chev">▾</span></summary><div class="body">'
             + "".join(f'<div><span style="display:inline-block;min-width:120px;font-weight:700;">{dk.esc(a)}</span>{dk.esc(b)}</div>' for a, b in TERMS)
             + '<button type="button" class="fc-fold" onclick="this.closest(\'details\').removeAttribute(\'open\')">접기</button></div></details>')
    tabs = ('<details id="fc-tabs" class="fc-det" open><summary>경우 고르기 · <span id="fc-cur"></span> <span class="fc-chev">▾</span></summary>'
            '<div class="r">' + "".join(f'<button type="button" class="tab" data-t="{t}">{t} · {TIERS[t]["name"]}</button>' for t in tiers)
            + '</div><div class="r">' + "".join(f'<button type="button" class="tab" data-k="{k}">{k}. {dk.esc(n)}</button>' for k, n in SITU) + "</div>"
            '<button type="button" class="fc-fold" onclick="document.getElementById(\'fc-tabs\').removeAttribute(\'open\')">접기</button></details>')
    panes = []
    for t in tiers:
        T = TIERS[t]
        for k, n in SITU:
            expl, pages = case(t, k)
            head = f'<div><span class="k">대상</span>{dk.esc(T["what"])}</div>'
            if t == "C":
                head += '<div><span class="k">주의</span>개별 종목 방향 전망은 공개 여부 미정 — 기획(데이터-기록-계획 3부 10-2)은 종목 방향을 공개하지 않는 것으로 정해 두었다(법 기준). 목업으로만 본다.</div>'
            ex = (f'<details class="fc-det fc-ex" open><summary>{t}-{k} · {T["name"]} · {dk.esc(n)} <span class="fc-chev">▾</span></summary><div class="body">' + head
                  + "".join('<div><span class="k">' + dk.esc(a) + '</span>' + _re.sub(r"`([^`]+)`", r"‘\1’", dk.esc(b)) + '</div>' for a, b in expl)
                  + '<button type="button" class="fc-fold" onclick="this.closest(\'details\').removeAttribute(\'open\')">접기</button></div></details>')
            body = "".join((f'<div class="fc-sub">{dk.esc(s)}</div>' if i else "") + h for i, (s, h) in enumerate(pages))
            panes.append(f'<div data-pane="{t}{k}" hidden>{ex}{body}</div>')
    names = {k: n for k, n in SITU}
    js = ("<script>(function(){var t='B',k='3';var NAMES=" + json.dumps(names, ensure_ascii=False) + ";var TIER=" + json.dumps({t: TIERS[t]["name"] for t in tiers}, ensure_ascii=False) + ";"
          "function show(){document.querySelectorAll('[data-pane]').forEach(function(p){p.hidden=p.getAttribute('data-pane')!==t+k;});"
          "document.querySelectorAll('#fc-tabs [data-t]').forEach(function(b){b.classList.toggle('on',b.dataset.t===t);});"
          "document.querySelectorAll('#fc-tabs [data-k]').forEach(function(b){b.classList.toggle('on',b.dataset.k===k);});"
          "document.getElementById('fc-cur').textContent=t+' · '+TIER[t]+' / '+k+'. '+NAMES[k];try{location.hash=t+k;}catch(e){}}"
          "var h=(location.hash||'').slice(1);if(/^[ABC](?:[1-9]|1[0-8])$/.test(h)){t=h[0];k=h.slice(1);}"
          "document.querySelectorAll('#fc-tabs button.tab').forEach(function(b){b.addEventListener('click',function(){if(b.dataset.t)t=b.dataset.t;if(b.dataset.k)k=b.dataset.k;show();window.scrollTo(0,0);});});show();})();</script>")
    return TAB_CSS + tabs + terms + "".join(panes) + js


if __name__ == "__main__":
    out = os.path.join(_HERE, "output", "mock_forecast-cases.html")
    html = build().replace(f"{H.BLOG}p/", "mock_")
    print(dk.write_mock(html, out, "증시 전망 · 경우의 수"))
