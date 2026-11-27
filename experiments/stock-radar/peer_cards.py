"""종목 페이지 새 카드 넷 — 같은 업종 S&P 500 종목과 견준다.

카드 (자리)
  `같은 업종 안 주가 순위는?`  오늘 탭 가격 카드 아래 — 기간별(1주 ~ 5년) 상승률 순위. 답 = 1년(없으면 3개월) 순위 구간
  `발표 때 예상을 넘었나?`     실적 탭 둘째 — 발표마다 1주당 이익 실제 vs 애널리스트 예상, 매출 예상은 기록이 있는 분기만
  `재무 건전성은?`             실적 탭 — 부채비율 · 유동비율 · 이자보상배율 · 잉여현금 비율 · 현금 대비 빚 순위. 답 = 부채비율 구간
  `이익에 비해 주가 수준은?`   실적 탭 — 주가수익비율 · 주가순자산비율 · 주가매출비율 · 주가 대비 잉여현금 순위 + 이 종목 5년 범위. 답 = 지난 1년 주가수익비율 구간
  + `돈을 어디에 쓰나?` 끝에 현금흐름 세 줄(투자 · 재무 · 순변동)
  점수 없음 · 순위만(항목을 섞으면 가중치 = 점수). 비교 대상 = 같은 업종 중앙값(헌법 제1조). 그래프 = rank_cols 세로 막대(0선 = 중앙값).

비교 묶음 (규칙, 사람 몫 없음)
  반도체(우리 분류표 세부 업종 SMH — GICS Semiconductors · Semiconductor Materials & Equipment) → S&P 500 반도체
  그 밖 → S&P 500 같은 업종(GICS 11, 이름 = taxonomy.SECTORS). 이 종목은 S&P 500 밖이어도 묶음에 넣는다(U.sector_etf 로 업종).

받기 (collect, 정식 실행마다 — 실패해도 페이지는 지난 값으로)
  일봉 6년  S&P 500 + 후보 약 520종목 묶음 한 번 — 새 거래일에만(하루 여러 실행은 다시 안 받음). 수익률 = 배당 포함 수정 종가
  SEC 재무 · 야후 배수  종목마다 7일 주기(후보는 실적 발표 뒤 처음 실행에도), 한 실행 FUND_MAX 개 · FUND_SECONDS 초까지 — 나머지는 다음 실행
           (버리지 않음: 일주일 안에 전부 한 바퀴). 배수는 받은 날 주가로 적혀 있어 오늘 종가 비율로 고친다(주식 수는 일주일에 거의 안 바뀜)
  실적 (후보만)  야후 발표일 · 실제/예상 + Finnhub — 7일 주기, 다음 실적 14일 안이면 매일, 발표 뒤 처음
  매출 · 이익 예상 기록 (후보만)  새 거래일마다 그날 애널리스트 평균을 rev_log 에 쌓는다 — 무료 자료는 지난 분기 예상을 주지 않아서(목업 때 확인)
  주식 수 (후보만)  7일 — 5년 범위(주가수익비율 · 주가매출비율)용, 분할을 곱해 맞춘다
파일 data/peer_fin.json — 워크플로가 상태 브랜치 radar/ 에 보존. AI 0 · Blogger 쓰기 0(같은 페이지 내용만).
"""

import datetime
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "data", "peer_fin.json")
UNIVERSE = os.path.join(HERE, "..", "ref", "universe_all.json")
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "nvda-report"))   # expect._sec (SEC 공용 호출)

PERIODS = (("1주", 5), ("1개월", 21), ("3개월", 63), ("6개월", 126), ("1년", 252), ("3년", 756), ("5년", 1260))
BEAT_TOL = 0.005   # 0.5% 안 = 예상과 같음
MIN_EPS = 0.10   # `예상을 넘은 횟수` 는 예상이 0.10달러 이상인 발표만 센다
FUND_DAYS = 7
FUND_MAX, FUND_SECONDS = 150, 300   # 한 실행 상한 — 첫 실행은 520종목을 4번에 나눠 채운다
GROUP_COVER = 0.8   # 묶음의 80% 넘게 재무를 받았을 때만 재무 · 주가 수준 카드 (첫 며칠 반쪽 묶음으로 순위를 내지 않게)
MIN_GROUP = 5

GICS_ETF = {"Information Technology": "XLK", "Financials": "XLF", "Energy": "XLE", "Health Care": "XLV", "Consumer Staples": "XLP",
            "Consumer Discretionary": "XLY", "Utilities": "XLU", "Industrials": "XLI", "Materials": "XLB", "Real Estate": "XLRE",
            "Communication Services": "XLC"}
SEMI_SUBS = ("Semiconductors", "Semiconductor Materials & Equipment")

TAGS_ADD = {"rev": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
            "int": ("InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt", "InterestAndDebtExpense"),
            "inv_cf": ("NetCashProvidedByUsedInInvestingActivities", "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations"),
            "fin_cf": ("NetCashProvidedByUsedInFinancingActivities", "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations"),
            "net_cf": ("CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
                       "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseExcludingExchangeRateEffect",
                       "CashAndCashEquivalentsPeriodIncreaseDecrease")}
INST_ADD = {"assets": ("Assets",), "liab": ("Liabilities",), "le": ("LiabilitiesAndStockholdersEquity",),
            "equity": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
            "cur_a": ("AssetsCurrent",), "cur_l": ("LiabilitiesCurrent",)}
KEEP = ("end", "cq", "rev", "int", "opinc", "ni", "fcf", "cash", "debt", "assets", "liab", "equity", "cur_a", "cur_l", "inv_cf", "fin_cf", "net_cf")
INFO = ("marketCap", "trailingPE", "forwardPE", "priceToBook", "priceToSalesTrailing12Months")

DATA = None   # 페이지 그리기가 읽는 값 — main 이 load() 로 채운다. 없으면(간단 종목 · 목업) 카드 없이
REV = {}      # 분기 매출 표(collect_extra revenue series) — 실적 카드의 실제 매출


# ---------------------------------------------------------------- 묶음

def groups():
    """{후보: (묶음 이름, [묶음 종목])} — 이 종목 포함."""
    import taxonomy
    import universe as U
    u = json.load(open(UNIVERSE, encoding="utf-8"))["us"]
    by = {r["sym"]: r for r in u}
    semis = sorted(r["sym"] for r in u if r["sub"] in SEMI_SUBS)
    sector = {}
    for r in u:
        sector.setdefault(GICS_ETF.get(r["sector"]), []).append(r["sym"])
    out = {}
    for sym, *_ in U.CANDIDATES:
        r = by.get(sym)
        if r:
            etf = "SMH" if r["sub"] in SEMI_SUBS else GICS_ETF.get(r["sector"])
        else:
            etf = U.sector_etf(sym)[0]
        if etf == "SMH":
            out[sym] = ("반도체", sorted(set(semis) | {sym}))
        elif etf in sector:
            out[sym] = (taxonomy.SECTORS[etf], sorted(set(sector[etf]) | {sym}))
    return out


# ---------------------------------------------------------------- 받기

def load():
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(d):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))


def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


def _age(day, today):
    return (today - datetime.date.fromisoformat(day)).days if day else 10 ** 6


def _prices(d, syms, bar_day):
    """일봉 6년 묶음 한 번 → 기간별 수익률(배당 포함) · 오늘 종가 · 후보 월말 종가. 새 거래일에만."""
    if d.get("px_bar") == bar_day:
        return
    import yfinance as yf
    df = yf.download(sorted(syms), period="6y", interval="1d", auto_adjust=False, progress=False, threads=True)
    adj, close = df["Adj Close"], df["Close"]
    rets = {lb: {} for lb, _ in PERIODS}
    px, got = {}, 0
    for c in adj.columns:
        a = adj[c].dropna()
        if a.empty:
            continue
        got += 1
        sym = str(c).replace(".", "-")
        v = a.tolist()
        for lb, n in PERIODS:
            if len(v) > n and v[-1 - n] > 0:
                rets[lb][sym] = round((v[-1] / v[-1 - n] - 1) * 100, 3)
        cl = close[c].dropna()
        if not cl.empty:
            px[sym] = round(float(cl.iloc[-1]), 4)
    if got < len(syms) * 0.9:   # 빈 값 막기 — 야후가 반쯤 비운 날은 어제 값 그대로
        print(f"[peer] 일봉 {got}/{len(syms)} — 모자라 지난 값 유지")
        return
    d["rets"], d["px"], d["px_bar"] = rets, px, bar_day
    print(f"[peer] 일봉 {got}/{len(syms)}종목 · {bar_day}")


def _month_closes(syms):
    """후보 월말 종가(분할 반영, 배당 미반영) — 5년 범위의 분기 말 시가총액용."""
    import yfinance as yf
    df = yf.download(sorted(syms), period="6y", interval="1mo", auto_adjust=False, progress=False, threads=True)["Close"]
    out = {}
    for c in df.columns:
        s = df[c].dropna()
        out[str(c).replace(".", "-")] = [[d.date().isoformat(), round(float(v), 4)] for d, v in s.items()]
    return out


def _cik():
    import expect as EX   # nvda-report — SEC 공용 호출(초당 10번 아래)
    t = EX._sec("https://www.sec.gov/files/company_tickers.json")
    return {v["ticker"]: str(v["cik_str"]).zfill(10) for v in t.values()}


def _sec_rows(cik, sym):
    import collect_capex as CX
    import expect as EX
    c = cik.get(sym) or cik.get(sym.replace("-", "."))
    if not c:
        return []
    facts = EX._sec(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c}.json")
    saved = (dict(CX.TAGS), dict(CX.INSTANT_TAGS), CX.YEARS)
    try:   # 돈 카드(collect_capex)의 항목 표에 재무 항목만 더해 한 번 읽는다 — 끝나면 원래 표로 (같은 실행의 capex.json 이 바뀌지 않게)
        CX.TAGS.update(TAGS_ADD)
        CX.INSTANT_TAGS.update(INST_ADD)
        CX.YEARS = 6
        rows = CX.rows_from_facts(facts, c)
    finally:
        CX.TAGS.clear(); CX.TAGS.update(saved[0])  # noqa: E702
        CX.INSTANT_TAGS.clear(); CX.INSTANT_TAGS.update(saved[1])  # noqa: E702
        CX.YEARS = saved[2]
    for r in rows:   # 총부채를 따로 안 적는 회사 = 부채와 자본 합계 − 자본
        if r.get("liab") is None and r.get("le") and r.get("equity") is not None:
            r["liab"] = r["le"] - r["equity"]
    return [{k: (round(r[k]) if isinstance(r.get(k), float) else r.get(k)) for k in KEEP} for r in rows[-24:]]


def _info(t):
    i = t.info or {}
    out = {k: _num(i.get(k)) for k in INFO}
    out["px"] = _num(i.get("currentPrice") or i.get("regularMarketPrice"))
    return out if any(out.values()) else None


def _shares(t):
    """주식 수 기록 — 야후 get_shares_full × 그 뒤 분할(splits). 야후 기록도 분할 전 숫자 그대로(엔비디아 2024-06 10:1 전 24.7억 주)."""
    ser = t.get_shares_full(start=(datetime.date.today() - datetime.timedelta(days=6 * 365)).isoformat())
    sp = [(str(d.date()), float(v)) for d, v in (t.splits.items() if t.splits is not None else [])]

    def adj(day, v):
        for sd, ratio in sp:
            if sd > day:
                v *= ratio
        return v
    return sorted({str(d.date()): adj(str(d.date()), float(v)) for d, v in ser.items()}.items()) if ser is not None else []


def _earn(t, sym):
    import requests
    rows = {}
    ed = t.get_earnings_dates(limit=40)
    for d, r in (ed.iterrows() if ed is not None else []):
        rows[d.date().isoformat()] = {"day": d.date().isoformat(), "est": _num(r.get("EPS Estimate")), "act": _num(r.get("Reported EPS"))}
    hist = []
    eh = t.earnings_history
    for q, r in (eh.iterrows() if eh is not None else []):
        hist.append({"end": q.date().isoformat(), "est": _num(r.get("epsEstimate")), "act": _num(r.get("epsActual"))})
    fh = []
    key = (os.environ.get("FINNHUB_API_KEY") or os.environ.get("FINNHUB_API") or "").split(",")[0].strip()   # 첫 키만 (price_source._key 규칙)
    if key:
        t0 = datetime.date.today()
        try:
            j = requests.get("https://finnhub.io/api/v1/calendar/earnings", timeout=30,
                             params={"symbol": sym, "from": str(t0 - datetime.timedelta(days=800)), "to": str(t0 + datetime.timedelta(days=120)), "token": key}).json()
            fh = [{"day": e["date"], "eps_est": e.get("epsEstimate"), "eps_act": e.get("epsActual"), "rev_est": e.get("revenueEstimate"), "rev_act": e.get("revenueActual")}
                  for e in j.get("earningsCalendar") or []]
        except Exception as e:  # noqa: BLE001
            print(f"[peer] {sym} Finnhub 실패: {str(e)[:80]}")
    if not rows and not hist:
        return None
    return {"dates": sorted(rows.values(), key=lambda x: x["day"]), "hist": hist, "finnhub": fh}


def _estimates(t):
    """오늘 애널리스트 평균 — 이번 분기(0q) · 다음 분기(+1q) 매출 · 1주당 이익."""
    out = {}
    re_, ee = t.revenue_estimate, t.earnings_estimate
    for p in ("0q", "+1q"):
        if re_ is not None and p in re_.index and _num(re_.loc[p, "avg"]):
            out["rev" + p] = [_num(re_.loc[p, "avg"]), _num(re_.loc[p, "numberOfAnalysts"])]
        if ee is not None and p in ee.index and _num(ee.loc[p, "avg"]) is not None:
            out["eps" + p] = [_num(ee.loc[p, "avg"]), _num(ee.loc[p, "numberOfAnalysts"])]
    return out or None


def collect(snap):
    """정식 실행마다 — 지난 값에 이어 붙이고 저장. 어느 단계가 실패해도 나머지는 계속."""
    import yfinance as yf
    import universe as U
    today = datetime.date.today()
    d = load()
    g = groups()
    cands = [c[0] for c in U.CANDIDATES if c[0] in g]
    allsyms = sorted({x for _, m in g.values() for x in m})
    bar_day = max((b[-1]["day"] for b in (snap.get("bars") or {}).values() if b), default=today.isoformat())
    earn_days = {s: [e["day"] for e in (snap.get("earnings") or {}).get(s) or []] for s in cands}
    try:
        _prices(d, allsyms, bar_day)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[peer] 일봉 실패 — 지난 값: {str(e)[:120]}")
    if d.get("mclose_bar", "")[:7] != bar_day[:7] or not d.get("mclose"):   # 월말 종가는 달이 바뀔 때 · 처음
        try:
            d["mclose"], d["mclose_bar"] = _month_closes(cands), bar_day
        except Exception as e:  # noqa: BLE001
            print(f"[peer] 월말 종가 실패: {str(e)[:120]}")
    for k in ("rows", "info", "fund_day", "shares", "earn", "earn_day", "rev_log"):
        d.setdefault(k, {})
    # 재무 · 배수 — 7일 주기, 오래된 것부터
    def passed(sym, since):
        return any(since < x <= today.isoformat() for x in earn_days.get(sym, []))
    due = [s for s in allsyms if _age(d["fund_day"].get(s), today) >= FUND_DAYS or (s in earn_days and passed(s, d["fund_day"].get(s, "")))]
    due.sort(key=lambda s: d["fund_day"].get(s, ""))
    t0, done, cik = time.time(), 0, None
    for s in due[:FUND_MAX]:
        if time.time() - t0 > FUND_SECONDS:
            break
        try:
            cik = cik or _cik()
            rows = _sec_rows(cik, s)
            t = yf.Ticker(s)
            info = _info(t)
            if rows:
                d["rows"][s] = rows
            if info:
                d["info"][s] = info
            if s in cands:
                sh = _shares(t)
                if sh:
                    d["shares"][s] = sh
            d["fund_day"][s] = today.isoformat()   # 비어도 받은 날은 적는다(외국 회사 · SEC 없음) — 다음 주에 다시
            done += 1
        except Exception as e:  # noqa: BLE001
            print(f"[peer] {s} 재무 실패: {str(e)[:100]}")
    print(f"[peer] 재무 {done}/{len(due)} (남은 것은 다음 실행) · 저장 {len(d['rows'])}종목")
    # 실적 · 예상 기록 — 후보만
    for s in cands:
        t = yf.Ticker(s)
        nxt = next((x for x in sorted(earn_days.get(s, [])) if x >= today.isoformat()), None)
        soon = nxt is not None and (datetime.date.fromisoformat(nxt) - today).days <= 14
        last = d["earn_day"].get(s, "")
        if _age(last or None, today) >= FUND_DAYS or passed(s, last) or (soon and last != today.isoformat()):
            try:
                e = _earn(t, s)
                if e:
                    d["earn"][s], d["earn_day"][s] = e, today.isoformat()
            except Exception as ex:  # noqa: BLE001
                print(f"[peer] {s} 실적 실패: {str(ex)[:100]}")
        log = d["rev_log"].setdefault(s, {})
        if bar_day not in log:
            try:
                est = _estimates(t)
                if est:
                    log[bar_day] = est
            except Exception as ex:  # noqa: BLE001
                print(f"[peer] {s} 예상 기록 실패: {str(ex)[:100]}")
    d["groups"] = {s: [n, len(m)] for s, (n, m) in g.items()}
    _save(d)
    return d


# ---------------------------------------------------------------- 값

def _ttm(rows, k):
    last4 = rows[-4:]
    if len(last4) < 4 or any(r.get(k) is None for r in last4):
        return None
    if (datetime.date.fromisoformat(last4[-1]["end"]) - datetime.date.fromisoformat(last4[0]["end"])).days > 300:   # 빠진 분기가 있으면 1년 합이 아니다
        return None
    return sum(r[k] for r in last4)


def health(rows):
    rows = [r for r in rows if r.get("assets")]
    if not rows:
        return {}
    r = rows[-1]
    eq = r.get("equity")
    out = {"_r": r}
    out["dr"] = (r["liab"] / eq * 100 if eq and eq > 0 else float("inf")) if r.get("liab") is not None and eq is not None else None
    out["cr"] = r["cur_a"] / r["cur_l"] if r.get("cur_a") and r.get("cur_l") else None
    op, it = _ttm(rows, "opinc"), _ttm(rows, "int")
    out["ic"] = (op / it if it and it > 0 else None) if op is not None else None
    fcf, rev = _ttm(rows, "fcf"), _ttm(rows, "rev")
    out["fm"] = fcf / rev * 100 if fcf is not None and rev else None
    out["dc"] = r["debt"] / r["cash"] if r.get("debt") is not None and r.get("cash") else None
    return out


def valuation(info, rows, px_now=None):
    """배수 — 야후가 받은 날 주가로 적은 값을 오늘 종가 비율로 고친다(모두 주가에 비례). 적자 · 음수 배수는 순위에서 뺀다."""
    i = info or {}
    k = (px_now / i["px"]) if px_now and i.get("px") else 1.0
    fcf = _ttm(rows or [], "fcf")
    pos = lambda v: v * k if isinstance(v, (int, float)) and v > 0 else None   # noqa: E731
    return {"pe": pos(i.get("trailingPE")), "fpe": pos(i.get("forwardPE")), "pb": pos(i.get("priceToBook")),
            "ps": pos(i.get("priceToSalesTrailing12Months")), "pf": pos(i["marketCap"] / fcf) if i.get("marketCap") and fcf else None}


def history(sym, d):
    """5년 분기 말 주가수익비율 · 주가매출비율 — 분기 말 무렵 종가 × 그 무렵 주식 수 ÷ 지난 4분기 순이익 · 매출."""
    rows, sh, px = d["rows"].get(sym) or [], d["shares"].get(sym) or [], (d.get("mclose") or d.get("qclose") or {}).get(sym) or []
    if not (rows and sh and px):
        return {}
    out = {"pe": [], "ps": []}
    for i in range(3, len(rows)):
        end = rows[i]["end"]
        if end < (datetime.date.today() - datetime.timedelta(days=5 * 365 + 30)).isoformat():
            continue
        p = [v for dd, v in px if dd <= end]
        s = [v for dd, v in sh if dd >= end] or [sh[-1][1]]
        if not p:
            continue
        cap = p[-1] * s[0]
        ni, rev = _ttm(rows[:i + 1], "ni"), _ttm(rows[:i + 1], "rev")
        if ni and ni > 0:
            out["pe"].append(cap / ni)
        if rev:
            out["ps"].append(cap / rev)
    return out


def _rank(me, others, high_right):
    vals = [v for v in others if v is not None] + [me]
    n = len(vals)
    if me is None or n < MIN_GROUP:
        return None
    rank = sorted(vals, reverse=high_right).index(me) + 1   # 1위 = 위 끝
    return {"rank": rank, "n": n, "pct": (n - rank) / max(n - 1, 1) * 100, "med": statistics.median(vals)}


def _zone(pct):
    return 2 if pct >= 75 else 0 if pct < 25 else 1


# ---------------------------------------------------------------- 그리기

def _mods():
    import render_pages as RP   # 그릴 때만 — render_pages 가 이 파일을 부른다(순환 막기)
    return RP, RP.R, RP._dk


def rank_cols(R, dk, rows, top_word="1위", bottom_word="꼴찌", flip=False):
    """같은 업종 안 순위 세로 막대 — 넷 카드 가운데 셋이 같이 쓴다.
    rows = [{lb(가로축 이름, 줄바꿈 가능), rank, pct(0 = 꼴찌 · 100 = 1위)}]. 0선 = 업종 중앙값, 위 끝 = 1위(top_word) · 아래 끝 = 꼴찌(bottom_word).
    눈금은 25% 단위로 고정(상위 25% · 하위 25% 경계가 그대로 눈금선). 색 = 위 4분의 1 빨강 · 아래 4분의 1 파랑 · 사이 회색, flip 이면 반대(주가 수준 = 높으면 파랑).
    틀 = 공용 col_frame 오른쪽 모양(축 오른쪽 · 넘칠 때만 `‹ 넘겨 보기`)."""
    vals = [x["pct"] - 50 for x in rows]
    txt = [f"{x['rank']}위" for x in rows]
    fs = R._chart_label_px(len(rows))
    lbl = max(R.CHART_LBL, fs + 4) + max(dk.LBL_LIFT, dk.LBL_LIFT_DN)
    height = 180
    scale = (height - lbl - lbl - dk.AXIS_PAD) / 100
    top = lbl + 50 * scale
    ticks = [-50, -25, 0, 25, 50]
    names = {50: top_word, 25: "상위 25%", 0: "중앙값", -25: "하위 25%", -50: bottom_word}
    fmt = lambda v: names[int(round(v))]   # noqa: E731
    gut = int(max(dk.text_px(t, dk.GRID_FS) for t in names.values()) + 6)
    label_px = max(dk.text_px(t, fs) for t in txt) + 4
    axis_px = min(max(dk.text_px(ln, 13) for x in rows for ln in x["lb"].split("\n")) + 14, dk.AXIS_MAX)   # +14 — 숫자 글꼴(Inter)이 text_px 어림보다 넓어 `+158%` 의 % 가 꺾였다 (2026-11-22)
    bw, lw, min_w = dk.col_layout(len(rows), 1, label_px, axis_px)
    up, dn = (R.DOWN, R.UP) if flip else (R.UP, R.DOWN)
    bg = {2: R._PASTEL_DN if flip else R._PASTEL_UP, 1: R._GRAY_BAR, 0: R._PASTEL_UP if flip else R._PASTEL_DN}
    fg = {2: up, 1: "#111", 0: dn}
    parts = []
    for i, (x, v, t) in enumerate(zip(rows, vals, txt)):
        z = _zone(x["pct"])
        h = max(1.0, abs(v) * scale)
        y, ly = (top - h, top - h - (lbl - dk.LBL_LIFT) + 1 - dk.LBL_LIFT) if v >= 0 else (top, top + h + 1 + dk.LBL_LIFT_DN)
        rad = "3px 3px 0 0" if v >= 0 else "0 0 3px 3px"
        parts.append(f'<span style="position:absolute;{dk.bar_x(i, 0, len(rows), 1, bw, lw)}top:{y:.1f}px;height:{h:.1f}px;background:{bg[z]};border-radius:{rad};"></span>')
        parts.append(f'<span style="position:absolute;{dk.bar_x(i, 0, len(rows), 1, bw, lw, label=True)}top:{ly:.1f}px;height:{lbl - dk.LBL_LIFT - 2}px;line-height:{lbl - dk.LBL_LIFT - 2}px;'
                     f'text-align:center;font-size:{fs}px;font-weight:700;white-space:nowrap;color:{fg[z]};">{t}</span>')
    return dk._col_frame_right("".join(parts), [x["lb"] for x in rows], height, top, scale, ticks, min_w, fmt, gut)


def rank_chart(R, dk, rows, base_lb, keep_order=False, **kw):
    """rank_cols 를 흰 그래프 카드에 담고, 답을 정하는 항목(base_lb) 축 이름 위에 점 (P175).
    항목 그래프는 답 항목을 오른쪽 끝 = 처음 보이는 자리(넘칠 때 왼쪽으로 넘겨 봄)에, 나머지는 항목 순서를 거꾸로 왼쪽에. 기간 그래프(keep_order)는 기간 순서 그대로."""
    if not keep_order:
        rows = [x for x in rows if x["lb"] != base_lb][::-1] + [x for x in rows if x["lb"] == base_lb]
    chart = R.axis_dot(rank_cols(R, dk, rows, **kw), base_lb, "#111")
    return f'<span style="{R.MULTI}margin:0 {dk.CHART_CARD_X}px;"><span style="display:block;padding:{dk.CHART_CARD_PAD}px 12px 0;">{chart}</span></span>'


def values_rows(rows):
    """그래프 아래 항목마다 한 줄 — 이 종목 값 · 업종 중앙값 · 뜻 (비교 대상 = 중앙값)."""
    return [("row", x["name"], x["val"], f"중앙값 {x['med_s']} · {x['mean']}") for x in rows]


def mom_card(name, sym, gname, group, rets):
    """`같은 업종 안 주가 순위는?` — (state, (theme, color), lines, tip) 또는 None."""
    RP, R, dk = _mods()
    rows = []
    for lb, _ in PERIODS:
        r = {x: v for x, v in ((rets or {}).get(lb) or {}).items() if x in group}
        if sym not in r or len(r) < MIN_GROUP:
            continue
        vals = sorted(r.values(), reverse=True)
        rank = vals.index(r[sym]) + 1
        n = len(vals)
        rows.append({"lb": lb, "ret": r[sym], "rank": rank, "n": n, "pct": (n - rank) / max(n - 1, 1) * 100, "med": statistics.median(vals)})
    if not rows:
        return None
    base = next((x for x in rows if x["lb"] == "1년"), None) or next((x for x in rows if x["lb"] == "3개월"), rows[-1])
    state = ("하위 25%", "중간", "상위 25%")[_zone(base["pct"])]
    theme = {"상위 25%": ("positive", R.UP), "하위 25%": ("negative", R.DOWN)}.get(state, ("neutral", "#111"))
    first = (f"{name} 주가는 최근 {base['lb']} 동안 {RP._sgn(base['ret'])}% 움직여, S&P 500 안 {gname} {base['n']}종목 가운데 {base['rank']}위입니다. "
             f"같은 기간 {gname} 종목의 중앙값은 {RP._sgn(base['med'])}%입니다.")
    missing = [lb for lb, _ in PERIODS if lb not in {x["lb"] for x in rows}]
    ax = lambda x: f"{x['lb']}\n{x['ret']:+.0f}%".replace("-", "−")   # noqa: E731 — 가로축 둘째 줄 = 이 종목 상승률(정수 %, 회색). 중앙값은 0선이 보여 준다
    chart = rank_chart(R, dk, [dict(x, lb=ax(x)) for x in rows[::-1]], ax(base), keep_order=True)   # 5년 → 1주, 가까운 기간 오른쪽 (P165 · 기간별 수익률 막대와 같은 방향)
    for x in rows:   # 둘째 줄(상승률) = 한 포인트 작게 12 · 오름 빨강 · 내림 파랑, 부호 +/−
        t = ax(x).split("\n")[1]
        col = R.UP if round(x["ret"]) > 0 else R.DOWN if round(x["ret"]) < 0 else "#111"
        chart = chart.replace(f"<br>{t}</span>", f'<br><span style="font-size:12px;color:{col};">{t}</span></span>')
    lines = [(first, "plain"), (f'{dk.CHART_TITLE_M}기간별 수익률 순위 (위로 갈수록 1위)</span>{chart}', "html"),
             ("row", "비교 묶음", f"{gname} {base['n']}종목", f"S&P 500 안 같은 업종 · {name} 포함"),
             ("row", "기준 기간", base["lb"], "답(상위 · 중간 · 하위)을 정하는 기간")]
    if missing:
        lines.append((f"{' · '.join(missing)}은 상장한 지 그만큼 되지 않아 뺐습니다.", "note"))
    if len({x["n"] for x in rows}) > 1:   # 긴 기간은 그만큼 상장하지 않은 종목이 빠져 묶음이 작아진다
        lines.append((" · ".join(f"{x['lb']} {x['n']}종목" for x in rows if x["n"] != base["n"]) + "은 그 기간만큼 상장하지 않은 종목을 빼고 견줬습니다.", "note"))
    tip = ("같은 업종 종목들과 견준 기간별 주가 수익률 순위. 가운데 가로선이 업종 중앙값, 위로 뻗으면 중앙값보다 많이 오른 것이고 맨 위가 1위\n"
           f"· 나누는 법 : {base['lb']} 순위가 위 4분의 1이면 상위 25%, 아래 4분의 1이면 하위 25%, 그 사이는 중간\n"
           "· 수익률 : 기간 이름 아래 숫자. 배당을 다시 넣은 수정 종가 기준\n"
           "· 비교 묶음 : S&P 500 구성 종목의 업종 분류(GICS). 반도체는 반도체끼리")
    return state, theme, lines, tip


# 실적 카드 ------------------------------------------------------------

def _cq_of_end(end):
    d = datetime.date.fromisoformat(end) - datetime.timedelta(days=45)   # 분기 가운데 날짜의 달력 분기 (expect._cq 와 같은 뜻)
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def _logged_rev_est(log, day):
    """발표일 전 마지막 기록의 이번 분기 매출 예상 — 우리가 매일 쌓은 값(rev_log)."""
    prev = [k for k in (log or {}) if k < day]
    if not prev:
        return None
    v = (log[max(prev)] or {}).get("rev0q")
    return v[0] if v else None


def beat_rows(e, rev_series, log=None):
    """발표 줄 [{day, cq, est, act, rev, rev_est}] — 발표일마다 그 앞 100일 안에 끝난 분기. 분기 끝 = 야후 earnings_history · SEC 분기 끝."""
    ends = sorted({h["end"] for h in e["hist"]} | {r["end"] for r in rev_series})
    rev = {r["end"]: r["rev"] for r in rev_series}
    fh = {x["day"]: x for x in e.get("finnhub") or []}
    out = {}
    for x in e["dates"]:
        if x["act"] is None:
            continue
        d = datetime.date.fromisoformat(x["day"])
        cand = [en for en in ends if 0 < (d - datetime.date.fromisoformat(en)).days <= 100]
        end = cand[-1] if cand else (d - datetime.timedelta(days=60)).isoformat()
        f = fh.get(x["day"]) or {}
        out[end] = {"day": x["day"], "end": end, "cq": _cq_of_end(end), "est": x["est"], "act": x["act"], "rev": rev.get(end) or f.get("rev_act"),
                    "rev_est": f.get("rev_est") or _logged_rev_est(log, x["day"])}
    for h in e["hist"]:   # 발표일 표에 없는 분기(상장 첫 분기)도 싣는다 — 예상 없음
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


def beat_card(name, e, rev_series, today, log=None):
    """`발표 때 예상을 넘었나?` — (state, lines, tip) 또는 None."""
    RP, R, dk = _mods()
    rows = [r for r in beat_rows(e, rev_series, log) if r["act"] is not None]
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
    first = f"{dk.josa(name, '는')} {when + ' ' if when else ''}{q} 실적을 발표했습니다. 1주당 이익은 {_money(last['act'])}"
    first += f"로, 애널리스트 예상 {_money(last['est'])}를 {verb[ce]}." if ce is not None else "입니다. 발표 전 애널리스트 예상은 없었습니다."
    if cr is not None:
        first += f" 매출은 {RP._bil(last['rev'])}로 예상 {RP._bil(last['rev_est'])}를 {verb[cr]}."
    scored = [r for r in rows if _cmp(r["act"], r["est"]) is not None and abs(r["est"]) >= MIN_EPS]   # 분할로 1센트 단위가 된 옛 값은 반올림 차이가 판정을 가른다(엔비디아 2014 ~ 17년 0.01달러)
    nbeat = sum(1 for r in scored if _cmp(r["act"], r["est"]) > 0)
    since = scored[0]["cq"][:4] if scored else ""
    groups_ = [(dk.q_axis(r["cq"]), [r["act"], r["est"]]) for r in rows]

    def color_at(i, k, v):
        r = rows[i]
        if k == 1:
            return (R._GRAY_BAR, R.NOTE)
        c = _cmp(r["act"], r["est"])
        if c is None or c == 0:
            return ("#9CA3AF", "#111")
        return (R._PASTEL_UP, R.UP) if c > 0 else (R._PASTEL_DN, R.DOWN)
    inner = R._col_chart(groups_, [lambda v: R._GRAY_BAR] * 2, [lambda v: "#111"] * 2, fmt=lambda v: f"{v:.2f}".replace("-", "−"), color_at=color_at, right=True)
    legend = R._legend_chips([("예상보다 높음", R._PASTEL_UP), ("예상보다 낮음", R._PASTEL_DN), ("애널리스트 예상", R._GRAY_BAR)])
    chart = (f'<span style="{R.MULTI}margin:0 {dk.CHART_CARD_X}px;"><span style="display:block;padding:{dk.CHART_CARD_PAD}px 12px 0;">'
             f'{dk.legend_top(inner, dk.legend_unit(legend, "달러"))}</span></span>')
    lines = [(first, "plain"), (f'{dk.CHART_TITLE_M}발표마다 1주당 이익, 실제와 예상</span>{chart}', "html")]
    if scored:
        lines.append(("row", "예상을 넘은 횟수", f"{len(scored)}번 중 {nbeat}번", f"{since}년 이후 발표 · 1주당 이익"))
    for r in rows[::-1]:   # 매출 예상이 있는 분기만 줄로 (최신 위)
        c = _cmp(r["rev"], r["rev_est"])
        if c is not None:
            lines.append(("row", f"{r['cq'][2:4]}년 {r['cq'][-1]}분기 매출", RP._bil(r["rev"]), f"예상 {RP._bil(r['rev_est'])} · {({1: '넘음', -1: '밑돎', 0: '같음'})[c]}"))
    nxt = [x for x in e["dates"] if x["act"] is None and x["day"] >= today]
    fh_next = [x for x in e.get("finnhub") or [] if x.get("eps_act") is None and x["day"] >= today]
    est = (log or {}).get(max(log)) if log else {}
    if nxt or fh_next:
        day = (fh_next or nxt)[0]["day"]
        left = (datetime.date.fromisoformat(day) - datetime.date.fromisoformat(today)).days
        if (est or {}).get("eps0q"):
            v, n = est["eps0q"]
            lines.append(("row", "다음 발표 1주당 이익 예상", _money(v), f"애널리스트 {int(n or 0)}명 평균 · {int(day[5:7])}월 {int(day[8:])}일 발표 예정({left}일 뒤)"))
        if (est or {}).get("rev0q"):
            v, n = est["rev0q"]
            lines.append(("row", "다음 발표 매출 예상", RP._bil(v), f"애널리스트 {int(n or 0)}명 평균"))
    if not any(_cmp(r["rev"], r["rev_est"]) is not None for r in rows):
        lines.append(("지난 분기 매출 예상은 받을 수 있는 무료 자료가 없어, 다음 발표부터 발표 전 예상을 기록해 견줍니다.", "note"))
    tip = ("실적 발표 때 실제 1주당 이익(EPS)이 애널리스트 예상 평균보다 높았는지 낮았는지. 1주당 이익은 회사 순이익을 주식 수로 나눈 값\n"
           "· 나누는 법 : 마지막 발표의 이익 · 매출이 둘 다 예상보다 높으면 예상 넘음, 둘 다 낮으면 예상 밑돎, 하나씩이면 엇갈림. 예상과 0.5% 안이면 같음\n"
           "· 예상 : 발표 직전 애널리스트 평균(Yahoo Finance · Finnhub 집계, 매출은 우리가 매일 기록한 값도)\n"
           "· 넘은 횟수 : 주식 분할로 1센트 단위가 된 옛 발표(예상 0.10달러 미만)는 반올림 차이가 커서 세지 않는다\n"
           "· 참고 : 회사가 미리 예상을 낮춰 두는 일이 많아 넘는 횟수가 많은 편이다")
    return state, lines, tip


# 재무 건전성 · 주가 수준 ----------------------------------------------

def _b(v):
    return f'<b style="color:#111;">{v}</b>'


AXIS = {"dr": "부채비율", "cr": "유동비율", "ic": "이자보상\n배율", "fm": "잉여현금\n비율", "dc": "현금 대비\n빚",
        "pe": "주가\n수익비율\n(지난 1년)", "fpe": "주가\n수익비율\n(1년 예상)", "pb": "주가\n순자산비율", "ps": "주가\n매출비율", "pf": "주가 대비\n잉여현금"}   # 가로축 이름 — 좁은 칸이라 짧은 줄로 나눈다(한 줄 5글자 안쪽, 휴대폰 폭에 다섯 칸)

HEALTH = (("dr", "부채비율", False, lambda v: "자본잠식" if v == float("inf") else f"{v:.0f}%", "총부채 ÷ 자본"),
          ("cr", "유동비율", True, lambda v: f"{v:.2f}배", "1년 안 돈이 되는 자산 ÷ 1년 안 갚을 빚"),
          ("ic", "이자보상배율", True, lambda v: f"{v:.1f}배", "지난 1년 영업이익 ÷ 이자 비용"),
          ("fm", "잉여현금 비율", True, lambda v: f"{v:.0f}%".replace("-", "−"), "지난 1년 잉여현금 ÷ 매출"),
          ("dc", "현금 대비 빚", False, lambda v: f"{v:.2f}배", "장기 부채 ÷ 현금"))

VALUE = (("pe", "주가수익비율 (지난 1년)", lambda v: f"{v:.1f}배", "시가총액 ÷ 지난 1년 순이익"),
         ("fpe", "주가수익비율 (다음 1년 예상)", lambda v: f"{v:.1f}배", "애널리스트 이익 예상 기준"),
         ("pb", "주가순자산비율", lambda v: f"{v:.1f}배", "시가총액 ÷ 자본"),
         ("ps", "주가매출비율", lambda v: f"{v:.1f}배", "시가총액 ÷ 지난 1년 매출"),
         ("pf", "주가 대비 잉여현금", lambda v: f"{v:.1f}배", "시가총액 ÷ 지난 1년 잉여현금"))


def health_card(name, sym, gname, peers, d):
    """`재무 건전성은?` — (state, (theme, color), lines, tip) 또는 None."""
    RP, R, dk = _mods()
    me = health(d["rows"].get(sym) or [])
    if not me:
        return None
    oth = [health(d["rows"].get(p) or []) for p in peers]
    rows, missing = [], []
    for k, lb, hi, fmt, mean in HEALTH:
        rk = _rank(me.get(k), [o.get(k) for o in oth], hi)
        if not rk:
            missing.append(lb)
            continue
        rows.append(dict(rk, lb=AXIS[k], name=lb, k=k, val=fmt(me[k]), med_s=fmt(rk["med"]), mean=mean))
    dr = next((x for x in rows if x["k"] == "dr"), None)
    if not dr:
        return None
    state = ("빚 많은 쪽", "업종 수준", "빚 적은 쪽")[_zone(dr["pct"])]
    theme = {"빚 적은 쪽": ("positive", R.UP), "빚 많은 쪽": ("negative", R.DOWN)}.get(state, ("neutral", "#111"))
    r = me["_r"]
    end = f"{int(r['end'][5:7])}월 말"
    first = (f"{name}의 {end} 부채비율(총부채 ÷ 자본)은 {HEALTH[0][3](me['dr'])}로, S&P 500 안 {gname} {dr['n']}종목 가운데 빚이 적은 쪽부터 {dr['rank']}번째입니다. "
             f"아래 줄마다 같은 업종 안 위치를 따로 보여 드리며, 항목을 합쳐 점수를 내지는 않습니다.")
    lines = [(first, "plain"), (f'{dk.CHART_TITLE_M}같은 업종 안 위치 (위로 갈수록 여유)</span>{rank_chart(R, dk, rows, dr["lb"], top_word="가장 여유", bottom_word="가장 빠듯")}', "html")]
    lines += values_rows(rows)
    if me.get("dr") == float("inf"):
        lines.append(("row", "자본잠식", "해당", "부채가 자산보다 많습니다"))
    if me.get("cr") is not None and me["cr"] < 1:
        lines.append(("row", "유동비율 1배 미만", "해당", "1년 안에 갚을 빚이 1년 안에 돈이 되는 자산보다 많습니다"))
    if me.get("ic") is not None and me["ic"] < 1:
        lines.append(("row", "이자보상배율 1배 미만", "해당", "지난 1년 영업이익으로 이자를 다 내지 못했습니다"))
    lines += [("row", "총자산", RP._bil(r["assets"]), f"{end} · 회사가 가진 모든 것"),
              ("row", "총부채", RP._bil(r["liab"]), "갚아야 할 돈 전부"),
              ("row", "자본", RP._bil(r["equity"]), "자산에서 부채를 뺀 주주 몫")]
    if missing:
        lines.append((f"{' · '.join(missing)}은 회사가 해당 항목을 따로 적지 않았거나 지난 1년 분기가 모자라 뺐습니다.", "note"))
    tip = ("빚 · 현금 사정을 같은 업종 회사들과 견준 위치. 항목마다 따로 순위를 매기고 합쳐서 점수를 내지 않는다\n"
           "· 나누는 법 : 부채비율이 업종에서 빚 적은 쪽 4분의 1이면 빚 적은 쪽, 많은 쪽 4분의 1이면 빚 많은 쪽, 그 사이는 업종 수준\n"
           "· 따로 알리는 경우 : 자본잠식 · 유동비율 1배 미만 · 이자보상배율 1배 미만은 순위와 상관없이 한 줄로\n"
           "· 참고 : 업종마다 빚을 쓰는 방식이 달라 다른 업종과는 견주지 않는다")
    return state, theme, lines, tip


def value_card(name, sym, gname, peers, d):
    """`이익에 비해 주가 수준은?` — (state, (theme, color), lines, tip) 또는 None."""
    RP, R, dk = _mods()
    px = d.get("px") or {}
    me = valuation(d["info"].get(sym), d["rows"].get(sym), px.get(sym))
    oth = [valuation(d["info"].get(p), d["rows"].get(p), px.get(p)) for p in peers]
    rows = []
    for k, lb, fmt, mean in VALUE:
        rk = _rank(me.get(k), [o.get(k) for o in oth], True)
        if rk:
            rows.append(dict(rk, lb=AXIS[k], name=lb, k=k, val=fmt(me[k]), med_s=fmt(rk["med"]), mean=mean))
    base = next((x for x in rows if x["k"] == "pe"), None) or next((x for x in rows if x["k"] == "ps"), None)
    if not base:
        return None
    state = ("업종보다 낮음", "업종 수준", "업종보다 높음")[_zone(base["pct"])]
    # 숫자와 반대 색 — 업종보다 낮으면 빨강 · 높으면 파랑
    theme = {"업종보다 낮음": ("positive", R.UP), "업종보다 높음": ("negative", R.DOWN)}.get(state, ("neutral", "#111"))
    first = (f"{name}의 {base['name']}은 {base['val']}로, S&P 500 안 {gname} {base['n']}종목 가운데 높은 쪽부터 {base['rank']}번째입니다. "
             f"높을수록 이익 · 매출에 비해 주가가 높게 매겨져 있다는 뜻입니다.")
    if base["k"] == "ps":
        first = f"{dk.josa(name, '는')} 지난 1년 순이익이 적자라 주가수익비율 대신 주가매출비율로 견줍니다. " + first
    lines = [(first, "plain"), (f'{dk.CHART_TITLE_M}같은 업종 안 위치 (위로 갈수록 높음)</span>{rank_chart(R, dk, rows, base["lb"], top_word="가장 높음", bottom_word="가장 낮음", flip=True)}', "html")]
    lines += values_rows(rows)
    h = history(sym, d)
    for k, lb in (("pe", "주가수익비율"), ("ps", "주가매출비율")):
        hs, now = h.get(k) or [], me.get(k)
        if len(hs) >= 8 and now:
            lo, hi_ = min(hs), max(hs)
            below = sum(1 for v in hs if v < now)
            where = ("5년 중 가장 낮음" if below == 0 else "5년 중 가장 높음" if below == len(hs)
                     else f"5년 분기 말 {len(hs)}번 중 지금보다 낮았던 때 {below}번")
            lines.append(("row", f"{lb} 5년 범위", f"{lo:.0f} ~ {hi_:.0f}배", f"지금 {now:.1f}배 · {where}"))
    if (me.get("pe") or me.get("ps")) and not any(len(h.get(k) or []) >= 8 for k in ("pe", "ps")):
        lines.append(("5년 범위는 분기 기록이 2년이 안 돼 내지 않았습니다.", "note"))
    if me.get("pe") is None:
        lines.append(("row", "주가수익비율 (지난 1년)", "계산 안 함", "지난 1년 순이익이 적자"))
    tip = ("이익 · 매출 · 자본에 비해 주가가 얼마나 높게 매겨져 있는지를 같은 업종 회사들과 견준 위치. 싸다 · 비싸다를 판정하지 않는다\n"
           "· 나누는 법 : 지난 1년 주가수익비율이 업종 높은 쪽 4분의 1이면 업종보다 높음, 낮은 쪽 4분의 1이면 업종보다 낮음, 그 사이는 업종 수준. 적자면 주가매출비율로\n"
           "· 5년 범위 : 지난 5년 분기 말 주가 × 주식 수 ÷ 그때까지 1년 이익 · 매출\n"
           "· 참고 : 성장이 빠른 회사는 배수가 높게 매겨지는 일이 많아, 높고 낮음만으로 좋고 나쁨을 말할 수 없다")
    return state, theme, lines, tip


def cash_rows(rows, cq):
    """`돈을 어디에 쓰나?` 끝에 더할 현금흐름 세 줄 — 그 카드의 최근 분기(cq)와 같은 분기."""
    RP, _, _ = _mods()
    r = next((x for x in rows or [] if x.get("cq") == cq), None)
    if not r:
        return []
    out = []
    for k, nm, note in (("inv_cf", "투자 활동 현금", "설비 · 회사 인수 · 증권 사고팔기 합 · +는 들어옴, −는 나감"),
                        ("fin_cf", "재무 활동 현금", "빚 · 증자 · 자사주 · 배당 합 · +는 들어옴, −는 나감"),
                        ("net_cf", "현금 순변동", "영업 · 투자 · 재무를 다 더한 석 달 현금 증감")):
        if r.get(k) is not None:
            out.append(("row", nm, RP._bil(r[k]), note))
    return out


# ---------------------------------------------------------------- 페이지가 부르는 곳

_G = None


def _group(sym):
    global _G
    if _G is None:
        try:
            _G = groups()
        except Exception as e:  # noqa: BLE001
            print(f"[peer] 묶음 실패: {e!r}")
            _G = {}
    return _G.get(sym)


def _covered(group):
    fd = (DATA or {}).get("fund_day") or {}
    return sum(1 for x in group if x in fd) >= len(group) * GROUP_COVER


def rank_section(s):
    """오늘 탭 가격 카드 아래 — 카드 HTML 또는 ''."""
    if not DATA:
        return ""
    g = _group(s["sym"])
    if not g:
        return ""
    try:
        got = mom_card(s["name"], s["sym"], g[0], set(g[1]), DATA.get("rets"))
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[peer] {s['sym']} 순위 카드 실패: {e!r}")
        return ""
    if not got:
        return ""
    _, R, _ = _mods()
    state, (th, col), lines, tip = got
    card = R._state_card("같은 업종 안 주가 순위는?", state, th, col, lines, "", tip=tip, fold=True, opened=False)
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{card}</div>'


def has_rank(s):
    g = DATA and _group(s["sym"])
    return bool(g and s["sym"] in ((DATA.get("rets") or {}).get("1년", {}) | (DATA.get("rets") or {}).get("3개월", {})))


def expect_cards(s):
    """실적 탭에 더할 카드 {key: {"state", "_lt": (lines, tip)}} — 테마 색은 R.EXPECT_THEME 에 넣는다."""
    out = {}
    if not DATA:
        return out
    _, R, _ = _mods()
    init_theme()
    sym = s["sym"]
    e = (DATA.get("earn") or {}).get(sym)
    try:
        got = beat_card(s["name"], e, REV.get(sym) or [], s["day"], (DATA.get("rev_log") or {}).get(sym)) if e else None
        if got:
            out["beat"] = {"state": got[0], "_lt": (got[1], got[2])}
    except Exception as ex:  # noqa: BLE001
        print(f"::warning::[peer] {sym} 실적 카드 실패: {ex!r}")
    g = _group(sym)
    if g and _covered(g[1]):
        peers = [x for x in g[1] if x != sym]
        for key, fn in (("health", health_card), ("value", value_card)):
            try:
                got = fn(s["name"], sym, g[0], peers, DATA)
            except Exception as ex:  # noqa: BLE001
                print(f"::warning::[peer] {sym} {key} 카드 실패: {ex!r}")
                got = None
            if got:
                out[key] = {"state": got[0], "_lt": (got[2], got[3])}
                R.EXPECT_THEME[got[0]] = got[1]
    return out


def init_theme():
    _, R, _ = _mods()
    R.EXPECT_THEME.update({"예상 넘음": ("positive", R.UP), "예상 밑돎": ("negative", R.DOWN), "엇갈림": ("neutral", "#111"), "예상과 같음": ("neutral", "#111")})


def sym_rows(sym):
    return ((DATA or {}).get("rows") or {}).get(sym) or []
