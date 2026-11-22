"""종목 페이지 새 카드 둘 목업 — `발표 때 예상을 넘었나?`(실적 탭) · `같은 업종 안 주가 순위는?`(오늘 탭 가격 카드 아래) (2026-11-20 사용자: 인베스팅 스페이스X 실적 · 가격 모멘텀 화면 보고 "목업 만들어 봐").

    .venv/bin/python experiments/stock-radar/mock_earn_mom.py           # 받아 둔 것으로 그리기만 (없으면 한 번 받음)
    .venv/bin/python experiments/stock-radar/mock_earn_mom.py --fetch   # 다시 받기 (야후 · Finnhub 읽기만)
    → output/mock_earnmom_SPCX.html · output/mock_earnmom_NVDA.html

설계(2026-11-20 Claude, 사용자 확인 전 목업):
- 실적 카드 = 발표마다 1주당 이익 실제 vs 애널리스트 예상(야후 earnings_dates, 엔비디아는 2021년부터 24번). 막대 둘(실제 = 넘으면 빨강 · 밑돌면 파랑, 예상 = 회색 비교).
  매출 예상은 무료 자료가 지난 분기를 주지 않는다 — 야후 = 다음 분기만, Finnhub = 최근 한 달만 · 스페이스X 없음. 그래서 매출은 가진 분기만 줄로,
  앞으로는 발표 전 예상을 매일 기록해 쌓는다(est_history 와 같은 방식). 다음 발표 예상 = 이익 · 매출 둘 다 줄로.
  답 = 마지막 발표: 이익 · 매출 둘 다(또는 매출 없음) 넘음 → `예상 넘음`(빨강 카드) · 둘 다 밑돎 → `예상 밑돎`(파랑) · 엇갈리면 `엇갈림`(중립).
- 순위 카드 = 같은 업종(S&P 500 GICS) 종목 사이 기간별(1주 ~ 5년) 상승률 순위, 오른쪽 = 1위. 비교 = 업종 중앙값. 평가 말(약함 · 훌륭함) 없이 순위만.
  답 = 1년 순위 구간(상위 25% · 중간 · 하위 25%), 1년치가 없으면 3개월. 상장이 짧으면 그 기간 줄은 뺀다(스페이스X = 2026-06 상장).
  가격 카드 펼침의 `12개월 모멘텀`(우리 64종목 중 순위)은 이 카드로 합쳐 뺀다 (2026-11-20 사용자). 한국은 함께 보기 판정에 쓰여(K18 통과) 그대로.
- (11-20 뒤 `재무 건전성은?` 으로 넓힘 — mock_fin_cards.py, 아래 balance_card 는 쓰지 않음) 빚 카드 `빚은 얼마나 지고 있나?`(실적 탭 `돈을 어디에 쓰나?` 다음, 2026-11-20 사용자 인베스팅 대차대조표 보고 "목업 만들어 봐") = 분기 말 총부채 ÷ 자본(부채비율)
  vs 같은 업종 중앙값 막대 + 총자산 · 총부채 · 자본 · 유동비율 줄. 재료 = 돈 카드가 이미 받는 SEC companyfacts 같은 파일(collect_capex.rows_from_facts 에 항목만 더함).
  답 = 업종 중앙값의 0.75배 아래 `업종보다 적음` · 1.25배 위 `업종보다 많음` · 그 사이 `업종 수준`. `안전 · 위험` 같은 판단 말 없음.
- 돈 카드 `돈을 어디에 쓰나?` 에 현금흐름 세 줄(투자로 나간 돈 · 재무로 들어온 돈 · 현금 순변동, 최근 분기)을 더한다.
- AI 0 · 블로그 게시 0 · 상태 브랜치 쓰기 0. 인터넷 = --fetch(또는 캐시 없을 때) 야후 · Finnhub · SEC 읽기만.
"""
import datetime
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import render_pages as RP  # noqa: E402
import mock_fin_cards as FC  # noqa: E402  — 세로 순위 막대(rank_cols)를 같이 쓴다

R, dk = RP.R, RP._dk
CACHE = os.path.join(HERE, "data", "mock_earn_mom.json")
OUT = os.path.join(HERE, "output")
SYMS = ("SPCX", "NVDA")
PEER_GROUP = {"SPCX": ("산업재", lambda r: r["sector"] == "Industrials"),
              "NVDA": ("반도체", lambda r: r["sub"] in ("Semiconductors", "Semiconductor Materials & Equipment"))}
PERIODS = (("1주", 5), ("1개월", 21), ("3개월", 63), ("6개월", 126), ("1년", 252), ("3년", 756), ("5년", 1260))
BEAT_TOL = 0.005   # 0.5% 안 = 예상과 같음


# ---------------------------------------------------------------- 받기

def _finnhub_key():
    for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
        if line.startswith("FINNHUB_API_KEY"):
            m = re.match(r"\s*['\"]?([A-Za-z0-9]+)", line.split("=", 1)[1])   # 줄 끝 주석 · 따옴표 떼기
            return m.group(1) if m else None
    return None


def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


def fetch_earn(sym):
    import requests
    import yfinance as yf
    t = yf.Ticker(sym)
    rows = {}
    ed = t.get_earnings_dates(limit=40)
    for d, r in (ed.iterrows() if ed is not None else []):
        rows[d.date().isoformat()] = {"day": d.date().isoformat(), "est": _num(r.get("EPS Estimate")), "act": _num(r.get("Reported EPS"))}
    hist = []
    eh = t.earnings_history
    for q, r in (eh.iterrows() if eh is not None else []):
        hist.append({"end": q.date().isoformat(), "est": _num(r.get("epsEstimate")), "act": _num(r.get("epsActual"))})
    rev_est = {}
    re_ = t.revenue_estimate
    for p in ("0q", "+1q"):
        if re_ is not None and p in re_.index:
            rev_est[p] = {"avg": _num(re_.loc[p, "avg"]), "n": _num(re_.loc[p, "numberOfAnalysts"])}
    eps_est = {}
    ee = t.earnings_estimate
    if ee is not None and "0q" in ee.index:
        eps_est = {"avg": _num(ee.loc["0q", "avg"]), "n": _num(ee.loc["0q", "numberOfAnalysts"])}
    fh = []
    key = _finnhub_key()
    if key:
        t0 = datetime.date.today()
        j = requests.get("https://finnhub.io/api/v1/calendar/earnings", timeout=30,
                         params={"symbol": sym, "from": str(t0 - datetime.timedelta(days=800)), "to": str(t0 + datetime.timedelta(days=120)), "token": key}).json()
        fh = [{"day": e["date"], "eps_est": e.get("epsEstimate"), "eps_act": e.get("epsActual"), "rev_est": e.get("revenueEstimate"), "rev_act": e.get("revenueActual")}
              for e in j.get("earningsCalendar") or []]
    return {"dates": sorted(rows.values(), key=lambda x: x["day"]), "hist": hist, "rev_est": rev_est, "eps_est": eps_est, "finnhub": fh}


def fetch_mom():
    import yfinance as yf
    u = json.load(open(os.path.join(HERE, "..", "ref", "universe_all.json"), encoding="utf-8"))["us"]
    groups = {s: sorted({r["sym"] for r in u if fn(r)} | {s}) for s, (_, fn) in PEER_GROUP.items()}
    syms = sorted({x for g in groups.values() for x in g})
    df = yf.download(syms, period="6y", progress=False, auto_adjust=True, threads=True)["Close"]
    closes = {c.replace(".", "-"): [round(float(v), 4) for v in df[c].dropna().tolist()] for c in df.columns}
    out = {}
    for s, g in groups.items():
        rets = {}
        for lb, n in PERIODS:
            rets[lb] = {x: (closes[x][-1] / closes[x][-1 - n] - 1) * 100 for x in g if len(closes.get(x) or []) > n}
        out[s] = {"group": g, "rets": rets, "asof": str(df.index[-1].date())}
    return out


def load(force=False):
    if not force and os.path.exists(CACHE):
        return json.load(open(CACHE, encoding="utf-8"))
    d = {"fetched": datetime.date.today().isoformat(), "earn": {s: fetch_earn(s) for s in SYMS}, "mom": fetch_mom()}
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(d, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return d


# ---------------------------------------------------------------- 실적 카드

def _cq_of_end(end):
    d = datetime.date.fromisoformat(end) - datetime.timedelta(days=45)   # 분기 가운데 날짜의 달력 분기 (expect._cq 와 같은 뜻)
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def beat_rows(e, rev_series):
    """발표 줄 [{day, cq, est, act, rev, rev_est}] — 발표일마다 그 앞 100일 안에 끝난 분기. 분기 끝 = 야후 earnings_history · SEC 분기 끝."""
    ends = sorted({h["end"] for h in e["hist"]} | {r["end"] for r in rev_series})
    rev = {r["end"]: r["rev"] for r in rev_series}
    fh = {x["day"]: x for x in e["finnhub"]}
    out = {}
    for x in e["dates"]:
        if x["act"] is None:
            continue
        d = datetime.date.fromisoformat(x["day"])
        cand = [en for en in ends if 0 < (d - datetime.date.fromisoformat(en)).days <= 100]
        end = cand[-1] if cand else (d - datetime.timedelta(days=60)).isoformat()
        f = fh.get(x["day"]) or {}
        out[end] = {"day": x["day"], "end": end, "cq": _cq_of_end(end), "est": x["est"], "act": x["act"], "rev": rev.get(end) or f.get("rev_act"), "rev_est": f.get("rev_est")}
    for h in e["hist"]:   # 발표일 표에 없는 분기(스페이스X 상장 첫 분기)도 싣는다 — 예상 없음
        out.setdefault(h["end"], {"day": None, "end": h["end"], "cq": _cq_of_end(h["end"]), "est": h["est"], "act": h["act"], "rev": rev.get(h["end"]), "rev_est": None})
    return sorted(out.values(), key=lambda r: r["end"])


def _cmp(act, est):
    if act is None or est is None:
        return None
    if abs(act - est) <= abs(est) * BEAT_TOL + 0.005:
        return 0
    return 1 if act > est else -1


def _money(v):
    return f"${v:.2f}".replace("$-", "−$")


def beat_card(name, e, rev_series, today):
    rows = beat_rows(e, rev_series)
    if not rows:
        return None
    last = rows[-1]
    ce, cr = _cmp(last["act"], last["est"]), _cmp(last["rev"], last["rev_est"])
    sides = [c for c in (ce, cr) if c is not None]
    state = ("예상 넘음" if sides and all(c > 0 for c in sides) else "예상 밑돎" if sides and all(c < 0 for c in sides)
             else "예상과 같음" if sides and all(c == 0 for c in sides) else "엇갈림" if sides else "판단 유보")
    when = f"{int(last['day'][5:7])}월 {int(last['day'][8:])}일" if last["day"] else ""
    q = f"{last['cq'][2:4]}년 {last['cq'][-1]}분기"
    verb = {1: "넘었습니다", -1: "밑돌았습니다", 0: "같았습니다"}
    first = f"{name}는 {when + ' ' if when else ''}{q} 실적을 발표했습니다. 1주당 이익은 {_money(last['act'])}로, 애널리스트 예상 {_money(last['est'])}를 {verb[ce]}."
    if cr is not None:
        first += f" 매출은 {RP._bil(last['rev'])}로 예상 {RP._bil(last['rev_est'])}를 {verb[cr]}."
    scored = [r for r in rows if _cmp(r["act"], r["est"]) is not None]
    nbeat = sum(1 for r in scored if _cmp(r["act"], r["est"]) > 0)
    since = scored[0]["cq"][:4] if scored else ""
    groups = [(dk.q_axis(r["cq"]), [r["act"], r["est"]]) for r in rows]

    def color_at(i, k, v):
        r = rows[i]
        if k == 1:
            return (R._GRAY_BAR, R.NOTE)
        c = _cmp(r["act"], r["est"])
        if c is None or c == 0:
            return ("#9CA3AF", "#111")
        return (R._PASTEL_UP, R.UP) if c > 0 else (R._PASTEL_DN, R.DOWN)
    # color_at 을 넘기려면 _col_chart 를 직접 부른다 — _chart_card 는 시리즈 색 함수만 받는다
    inner = R._col_chart(groups, [lambda v: R._GRAY_BAR] * 2, [lambda v: "#111"] * 2, fmt=lambda v: f"{v:.2f}".replace("-", "−"), color_at=color_at, right=True)
    legend = R._legend_chips([("예상보다 높음", R._PASTEL_UP), ("예상보다 낮음", R._PASTEL_DN), ("애널리스트 예상", R._GRAY_BAR)])
    chart = (f'<span style="{R.MULTI}margin:0 {dk.CHART_CARD_X}px;"><span style="display:block;padding:{dk.CHART_CARD_PAD}px 12px 0;">'
             f'{dk.legend_top(inner, dk.legend_unit(legend, "달러"))}</span></span>')
    lines = [(first, "plain"), (f'{dk.CHART_TITLE_M}발표마다 1주당 이익, 실제와 예상</span>{chart}', "html")]
    if scored:
        lines.append(("row", "예상을 넘은 횟수", f"{len(scored)}번 중 {nbeat}번", f"{since}년 이후 발표 · 1주당 이익"))
    for r in rows[::-1]:   # 매출 예상이 있는 분기만 줄로 (최신 위)
        c = _cmp(r["rev"], r["rev_est"])
        if c is not None:
            lines.append(("row", f"{r['cq'][2:4]}년 {r['cq'][-1]}분기 매출", RP._bil(r["rev"]), f"예상 {RP._bil(r['rev_est'])} · {verb[c].replace('습니다', '음').replace('넘었음', '넘음').replace('밑돌았음', '밑돎')}"))
    nxt = [x for x in e["dates"] if x["act"] is None and x["day"] >= today]
    fh_next = [x for x in e["finnhub"] if x.get("eps_act") is None and x["day"] >= today]
    if nxt or fh_next:
        day = (fh_next or nxt)[0]["day"]
        left = (datetime.date.fromisoformat(day) - datetime.date.fromisoformat(today)).days
        ee = e.get("eps_est") or {}
        if ee.get("avg") is not None:
            lines.append(("row", "다음 발표 1주당 이익 예상", _money(ee["avg"]), f"애널리스트 {int(ee['n'])}명 평균 · {int(day[5:7])}월 {int(day[8:])}일 발표 예정({left}일 뒤)"))
        rv = (e.get("rev_est") or {}).get("0q") or {}
        if rv.get("avg"):
            lines.append(("row", "다음 발표 매출 예상", RP._bil(rv["avg"]), f"애널리스트 {int(rv['n'])}명 평균"))
    no_rev = not any(_cmp(r["rev"], r["rev_est"]) is not None for r in rows)
    if no_rev:
        lines.append(("지난 분기 매출 예상은 받을 수 있는 무료 자료가 없어, 다음 발표부터 발표 전 예상을 기록해 견줍니다.", "note"))
    tip = ("실적 발표 때 실제 1주당 이익(EPS)이 애널리스트 예상 평균보다 높았는지 낮았는지. 1주당 이익은 회사 순이익을 주식 수로 나눈 값\n"
           "· 나누는 법 : 마지막 발표의 이익 · 매출이 둘 다 예상보다 높으면 예상 넘음, 둘 다 낮으면 예상 밑돎, 하나씩이면 엇갈림. 예상과 0.5% 안이면 같음\n"
           "· 예상 : 발표 직전 애널리스트 평균(Yahoo Finance · Finnhub 집계)\n"
           "· 참고 : 회사가 미리 예상을 낮춰 두는 일이 많아 넘는 횟수가 많은 편이다")
    return state, lines, tip


# ---------------------------------------------------------------- 순위 카드

def _zone(pct):
    return 2 if pct >= 75 else 0 if pct < 25 else 1


def mom_card(name, sym, m):
    gname = PEER_GROUP[sym][0]
    rows = []
    for lb, _ in PERIODS:
        r = m["rets"].get(lb) or {}
        if sym not in r or len(r) < 5:
            continue
        vals = sorted(r.values(), reverse=True)
        rank = vals.index(r[sym]) + 1
        n = len(vals)
        pct = (n - rank) / max(n - 1, 1) * 100   # 오른쪽 = 1위
        rows.append({"lb": lb, "ret": r[sym], "rank": rank, "n": n, "pct": pct, "med": statistics.median(vals)})
    if not rows:
        return None
    base = next((x for x in rows if x["lb"] == "1년"), None) or next((x for x in rows if x["lb"] == "3개월"), rows[-1])
    state = ("상위 25%", "중간", "하위 25%")[2 - _zone(base["pct"])]
    theme = {"상위 25%": ("positive", R.UP), "하위 25%": ("negative", R.DOWN)}.get(state, ("neutral", "#111"))
    first = (f"{name} 주가는 최근 {base['lb']} 동안 {RP._sgn(base['ret'])}% 움직여, S&P 500 안 {gname} {base['n']}종목 가운데 {base['rank']}위입니다. "
             f"같은 기간 {gname} 종목의 중앙값은 {RP._sgn(base['med'])}%입니다.")
    missing = [lb for lb, _ in PERIODS if lb not in {x["lb"] for x in rows}]
    chart = FC.rank_cols(R, dk, rows[::-1])   # 5년 → 1주, 가까운 기간 오른쪽 (P165 · 기간별 수익률 막대와 같은 방향)
    chart = R.axis_dot(chart, base["lb"], "#111")   # 답을 정하는 기준 기간 = 축 이름 위 점 (P175 막대 하나 강조 규칙)
    chart = (f'<span style="{R.MULTI}margin:0 {dk.CHART_CARD_X}px;"><span style="display:block;padding:{dk.CHART_CARD_PAD}px 12px 0;">{chart}</span></span>')
    lines = [(first, "plain"), (f'{dk.CHART_TITLE_M}기간별 상승률 순위 (위로 갈수록 1위)</span>{chart}', "html"),
             ("row", "비교 묶음", f"{gname} {base['n']}종목", "S&P 500 안 같은 업종 · " + (f"{sym} 포함" if sym == "SPCX" else "엔비디아 포함")),
             ("row", "기준 기간", base["lb"], "답(상위 · 중간 · 하위)을 정하는 기간")]
    if missing:
        lines.append((f"{' · '.join(missing)}은 상장한 지 그만큼 되지 않아 뺐습니다.", "note"))
    ns = sorted({x["n"] for x in rows})
    if len(ns) > 1:   # 긴 기간은 그만큼 상장하지 않은 종목이 빠져 묶음이 작아진다
        lines.append((" · ".join(f"{x['lb']} {x['n']}종목" for x in rows if x["n"] != base["n"]) + "은 그 기간만큼 상장하지 않은 종목을 빼고 견줬습니다.", "note"))
    tip = (f"같은 업종 종목들과 견준 기간별 주가 상승률 순위. 가운데 가로선이 업종 중앙값, 위로 뻗으면 중앙값보다 많이 오른 것이고 맨 위가 1위\n"
           f"· 나누는 법 : {base['lb']} 순위가 위 4분의 1이면 상위 25%, 아래 4분의 1이면 하위 25%, 그 사이는 중간\n"
           "· 비교 묶음 : S&P 500 구성 종목의 업종 분류(GICS)")
    return state, theme, lines, tip


# ---------------------------------------------------------------- 빚 카드 · 현금흐름 세 줄 (SEC)

BAL_CACHE = os.path.join(HERE, "data", "mock_balance.json")
BAL_TAGS = {"inv_cf": ("NetCashProvidedByUsedInInvestingActivities", "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations"),
            "fin_cf": ("NetCashProvidedByUsedInFinancingActivities", "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations"),
            "net_cf": ("CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
                       "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseExcludingExchangeRateEffect",
                       "CashAndCashEquivalentsPeriodIncreaseDecrease")}
BAL_INST = {"assets": ("Assets",), "liab": ("Liabilities",), "le": ("LiabilitiesAndStockholdersEquity",),
            "equity": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
            "cur_a": ("AssetsCurrent",), "cur_l": ("LiabilitiesCurrent",)}
KEEP = ("start", "end", "cq", "inv_cf", "fin_cf", "net_cf", "assets", "liab", "equity", "cur_a", "cur_l")


def fetch_balance():
    import time
    import config
    import collect_capex as CX
    import requests
    CX.TAGS.update(BAL_TAGS)
    CX.INSTANT_TAGS.update(BAL_INST)
    ua = {"User-Agent": config.EDGAR_USER_AGENT}
    cik = {v["ticker"]: str(v["cik_str"]).zfill(10) for v in requests.get("https://www.sec.gov/files/company_tickers.json", headers=ua, timeout=60).json().values()}
    u = json.load(open(os.path.join(HERE, "..", "ref", "universe_all.json"), encoding="utf-8"))["us"]
    groups = {s: sorted({r["sym"] for r in u if fn(r)} | {s}) for s, (_, fn) in PEER_GROUP.items()}
    out = {"groups": groups, "rows": {}}
    for sym in sorted({x for g in groups.values() for x in g}):
        c = cik.get(sym) or cik.get(sym.replace("-", "."))
        if not c:
            continue
        try:
            facts = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c}.json", headers=ua, timeout=60).json()
            rows = CX.rows_from_facts(facts, c)
        except Exception as e:  # noqa: BLE001
            print(f"[balance] {sym} 실패: {str(e)[:80]}")
            continue
        for r in rows:   # 총부채를 따로 안 적는 회사 = 부채와 자본 합계 − 자본
            if r.get("liab") is None and r.get("le") and r.get("equity") is not None:
                r["liab"] = r["le"] - r["equity"]
        out["rows"][sym] = [{k: r.get(k) for k in KEEP} for r in rows[-12:]]
        time.sleep(0.15)   # SEC 초당 10번 아래
    json.dump(out, open(BAL_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return out


def load_balance(force=False):
    if not force and os.path.exists(BAL_CACHE):
        return json.load(open(BAL_CACHE, encoding="utf-8"))
    return fetch_balance()


def _dr(r):
    """부채비율 % = 총부채 ÷ 자본. 자본이 0 이하(자본잠식)면 None — 비율이 뜻이 없다."""
    return r["liab"] / r["equity"] * 100 if r.get("liab") is not None and r.get("equity") and r["equity"] > 0 else None


def balance_card(name, sym, bal):
    rows = [r for r in bal["rows"].get(sym) or [] if r.get("assets")]
    if not rows:
        return None
    gname = PEER_GROUP[sym][0]
    peers = [p for p in bal["groups"][sym] if p != sym]

    def med(cq, fn):
        vals = [fn(r) for p in peers for r in bal["rows"].get(p) or [] if r["cq"] == cq]
        vals = [v for v in vals if v is not None]
        return (statistics.median(vals), len(vals)) if len(vals) >= 5 else (None, len(vals))
    last = rows[-1]
    dr = _dr(last)
    m, n = med(last["cq"], _dr)
    if dr is None or m is None:
        state = "판단 유보"
    else:
        state = "업종보다 적음" if dr < m * 0.75 else "업종보다 많음" if dr > m * 1.25 else "업종 수준"
    end = f"{int(last['end'][5:7])}월 말"
    first = (f"{name}의 {end} 총자산은 {RP._bil(last['assets'])}, 총부채는 {RP._bil(last['liab'])}, 자본은 {RP._bil(last['equity'])}입니다.")
    if dr is not None and m is not None:
        tail = {"업종보다 적음": "보다 낮습니다", "업종보다 많음": "보다 높습니다"}.get(state, "와 비슷합니다")
        first += f" 총부채는 자본의 {dr:.0f}%로, S&P 500 안 {gname} {n}종목 중앙값 {m:.0f}%{tail}."
    elif dr is not None:
        first += f" 총부채는 자본의 {dr:.0f}%입니다."
    shown = rows[-8:]
    groups = [(dk.q_axis(r["cq"]), [_dr(r), med(r["cq"], _dr)[0]]) for r in shown]
    inner = R._col_chart(groups, [lambda v: dk.CHART_SERIES[0], lambda v: R._GRAY_BAR], [lambda v: "#111", lambda v: R.NOTE],
                         fmt=lambda v: f"{v:.0f}", right=True)
    legend = dk.legend_unit(R._legend_chips([(name, dk.CHART_SERIES[0]), (f"{gname} 중앙값", R._GRAY_BAR)]), "%")
    chart = (f'<span style="{R.MULTI}margin:0 {dk.CHART_CARD_X}px;"><span style="display:block;padding:{dk.CHART_CARD_PAD}px 12px 0;">'
             f'{dk.legend_top(inner, legend)}</span></span>')
    lines = [(first, "plain"), (f'{dk.CHART_TITLE_M}분기 말 부채비율 (총부채 ÷ 자본)</span>{chart}', "html")]
    yago = next((r for r in rows if abs((datetime.date.fromisoformat(last["end"]) - datetime.date.fromisoformat(r["end"])).days - 365) <= 20), None)

    def chg(k):
        return f" · 1년 전 {RP._bil(yago[k])}" if yago and yago.get(k) is not None else ""   # 1년 전 값이 없으면(상장 1년 안) 꼬리 없이
    lines += [("row", "총자산", RP._bil(last["assets"]), "회사가 가진 모든 것" + chg("assets")),
              ("row", "총부채", RP._bil(last["liab"]), "갚아야 할 돈 전부" + chg("liab")),
              ("row", "자본", RP._bil(last["equity"]), "자산에서 부채를 뺀 주주 몫" + chg("equity"))]
    if last.get("cur_a") and last.get("cur_l"):
        cr = last["cur_a"] / last["cur_l"]
        cm, _ = med(last["cq"], lambda r: r["cur_a"] / r["cur_l"] if r.get("cur_a") and r.get("cur_l") else None)
        lines.append(("row", "유동비율", f"{cr:.2f}배", "1년 안 갚을 빚 대비 1년 안 돈이 되는 자산" + (f" · {gname} 중앙값 {cm:.2f}배" if cm else "")))
    tip = ("분기 말 회사가 진 빚(총부채)이 주주 몫(자본)의 몇 %인지, 같은 업종 회사들과 견준 값. 회사가 SEC 에 낸 분기 · 연간 보고서의 재무상태표\n"
           "· 나누는 법 : 업종 중앙값의 0.75배보다 낮으면 업종보다 적음, 1.25배보다 높으면 업종보다 많음, 그 사이는 업종 수준\n"
           "· 참고 : 업종마다 빚을 쓰는 방식이 달라(공장 · 비행기 리스가 많은 업종은 높다) 다른 업종과는 견주지 않는다")
    return state, lines, tip


def cash_rows(sym, bal, cq):
    """`돈을 어디에 쓰나?` 끝에 더할 현금흐름 세 줄 — 그 카드의 최근 분기(cq)와 같은 분기."""
    r = next((x for x in bal["rows"].get(sym) or [] if x["cq"] == cq), None)
    if not r:
        return []
    out = []
    for k, nm, note in (("inv_cf", "투자 활동 현금", "설비 · 회사 인수 · 증권 사고팔기 합 · +는 들어옴, −는 나감"),
                        ("fin_cf", "재무 활동 현금", "빚 · 증자 · 자사주 · 배당 합 · +는 들어옴, −는 나감"),
                        ("net_cf", "현금 순변동", "영업 · 투자 · 재무를 다 더한 석 달 현금 증감")):
        if r.get(k) is not None:
            out.append(("row", nm, RP._bil(r[k]), note))
    return out


# ---------------------------------------------------------------- 페이지에 끼우기

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    data = load("--fetch" in sys.argv)
    bal = load_balance("--fetch" in sys.argv)
    u_ = json.load(open(os.path.join(HERE, "..", "ref", "universe_all.json"), encoding="utf-8"))["us"]
    fin_groups = {s_: sorted({r["sym"] for r in u_ if fn(r)} | {s_}) for s_, (_, fn) in PEER_GROUP.items()}
    fin = FC.load(fin_groups, SYMS, "--fetch" in sys.argv)
    import analyze
    import analyze_tabs
    import collect
    import collect_extra
    import collect_news
    import industry_us
    snap, extra, news = collect.load(), collect_extra.load() or {}, collect_news.load()
    a = analyze.run(snap)
    fred = industry_us.load()
    a["stocks"] = [s for s in a["stocks"] if s["sym"] in SYMS]
    for s in a["stocks"]:
        analyze_tabs.build(s, snap, extra)
        s["industry_us"] = industry_us.build(s["sym"], fred)
    rev = (extra.get("revenue") or {}).get("series") or {}
    R.EXPECT_THEME.update({"예상 넘음": ("positive", R.UP), "예상 밑돎": ("negative", R.DOWN), "엇갈림": ("neutral", "#111"), "예상과 같음": ("neutral", "#111"),
                           "업종보다 적음": ("positive", R.UP), "업종보다 많음": ("negative", R.DOWN), "업종 수준": ("neutral", "#111")})

    orig_price = RP.price_card

    def sec_expect(s, open_first=True):
        """RP.sec_expect 와 같은 순서 · 같은 카드 + 둘째 자리에 새 카드(돈을 더 버나 → 예상을 넘었나 → 이익 예상 변화)."""
        ex = dict(s.get("expect") or {})
        got = beat_card(s["name"], data["earn"][s["sym"]], rev.get(s["sym"]) or [], s["day"])
        if got:
            ex["beat"] = {"state": got[0], "_lt": (got[1], got[2])}
        g = PEER_GROUP[s["sym"]][0]
        peers = [x for x in fin_groups[s["sym"]] if x != s["sym"]]
        for key, fn_ in (("health", FC.health_card), ("value", FC.value_card)):
            got_ = fn_(R, dk, RP, s["name"], s["sym"], g, peers, fin)
            if got_:
                ex[key] = {"state": got_[0], "_lt": (got_[2], got_[3])}
                R.EXPECT_THEME[got_[0]] = got_[1]

        def capex_plus(c):   # 돈 카드 + 현금흐름 세 줄 (같은 최근 분기)
            lines, tip = RP.card_capex(c)
            cq = (c.get("bars") or [{}])[-1].get("cq")
            lines = list(lines)
            at = next((i for i, x in enumerate(lines) if "출처" in str(x[0])), len(lines))   # 출처 줄은 카드 맨 끝에 그대로
            return lines[:at] + cash_rows(s["sym"], bal, cq) + lines[at:], tip
        spec = [("회사는 돈을 더 벌고 있나?", "revenue", RP.card_revenue), ("발표 때 예상을 넘었나?", "beat", lambda c: c["_lt"]),
                (R.EPS_TITLE, "eps", R.card_eps), ("시장 예상 흔들림은?", "move", R.card_move), ("하락에 거는 돈은?", "short", R.card_short),
                ("돈을 어디에 쓰나?", "capex", capex_plus), ("재무 건전성은?", "health", lambda c: c["_lt"]),
                ("이익에 비해 주가 수준은?", "value", lambda c: c["_lt"])]
        out = ""
        for i, (title, key, fn) in enumerate(spec):
            c = ex.get(key)
            if key in ("capex", "beat", "health", "value") and not c:
                continue
            if c:
                lines, tip = RP._rename(fn(c), s["name"])
                state = c["state"]
            else:
                lines, tip, state = [("이번 실행에서 재료를 받지 못했다. 다음 실행에서 다시 받는다.", "plain")], "", "판단 유보"
            lines = list(lines)
            if key == "move" and s.get("options_status"):
                blk = R.status_block({"status": s["options_status"]}, "options", "옵션 지표")
                if blk:
                    lines.append((blk, "html"))
            theme, col = R.EXPECT_THEME.get(state, ("neutral", R.MUTED))
            out += R._state_card(title, state, theme, col, lines, "", tip=tip, fold=True, opened=(open_first and i == 0) or key in ("beat", "health", "value"))
        return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>'

    def price_card(s, today):
        got = mom_card(s["name"], s["sym"], data["mom"][s["sym"]])
        out = orig_price(s, today)
        if not got:
            return out
        state, (th, col), lines, tip = got[0], got[1], got[2], got[3]
        card = R._state_card("같은 업종 안 주가 순위는?", state, th, col, lines, "", tip=tip, fold=True, opened=True)
        return out + f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{card}</div>'

    RP.sec_expect, RP.price_card = sec_expect, price_card
    RP.sec_momentum = lambda s: ""   # 가격 카드 펼침의 `12개월 모멘텀`(우리 64종목 순위)은 새 순위 카드로 합침 (2026-11-20 사용자 "합치는 쪽으로") — 미국은 화면에만 쓰던 값이라 판정 영향 없음
    tmp = os.path.join(OUT, "_earnmom_tmp")
    pages = RP.write_all(a, tmp, None, news)
    for s in a["stocks"]:
        src = os.path.join(tmp, f"mock_{s['sym']}.html")
        dst = os.path.join(OUT, f"mock_earnmom_{s['sym']}.html")
        html = open(src, encoding="utf-8").read().replace("— 목업</title>", "— 새 카드 목업</title>")
        open(dst, "w", encoding="utf-8").write(html)
        print("→", dst)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    return pages


if __name__ == "__main__":
    main()
