"""실적과 기대 탭 — 질문 카드 넷의 재료 · 판정 (디자인-가이드라인 2-7, 2026-10-18 확정). AI 없음.

비교 대상 (가이드라인 1-4-1 : 그래프에는 반드시 비교 대상)
  1. 회사는 돈을 더 벌고 있나?      분기 매출 1년 전 대비 · 기술주 15개 중앙값 (SEC XBRL companyfacts, 주 1회)
  2. 애널리스트 전망은?    내년 1주당 이익 예상치 7 · 30 · 60 · 90일 변화 · 기술주 15개 중앙값 (yfinance eps_trend, 매일)
  3. 시장 예상 흔들림은?   옵션 30일 내재변동성 ÷ √252 vs 평소 하루(EWMA) · S&P 500 한 쌍 (매일)
  4. 하락에 거는 돈은?              공매도 비율(유통 주식 대비) 지난달 · 이번 달 · 기술주 15개 중앙값 (yfinance info, 매일 — 값은 격주로 바뀐다)
수집 결과는 meta 에 JSON 으로 둔다 (state_io 가 meta 를 통째로 내보내므로 Actions 에서도 이어진다).
"""

import datetime
import json
import math
import statistics
import time

import requests

import collect_market
import config
import db
import history_stats

PEERS = history_stats.PEERS   # 기술주 15개 — 고점 회복 카드와 같은 묶음
REV_CONCEPTS = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet")
REV_MAX_AGE_DAYS = 7
MIN_PEERS = 8          # 이 수 이상 공시한 분기만 중앙값을 그린다
REV_PCT, EPS_PCT, MOVE_HI, MOVE_LO, SHORT_PCT = 5.0, 1.0, 1.3, 0.8, 10.0   # 확정 기준 (2-7 표) · 4번은 Claude 설계


def _get(conn, key):
    raw = db.get_meta(conn, key)
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def _put(conn, key, value):
    db.set_meta(conn, key, json.dumps(value, ensure_ascii=False))
    conn.commit()


# ---------------------------------------------------------------- 1. 매출 (SEC XBRL)

def _sec(url):
    r = requests.get(url, headers={"User-Agent": config.EDGAR_USER_AGENT}, timeout=60)
    r.raise_for_status()
    time.sleep(0.15)   # SEC 초당 10회 한도 안
    return r.json()


def _d(s):
    return datetime.date.fromisoformat(s)


def _quarters(facts):
    """분기 매출 {(start, end): val} — 3개월 값이 없는 4분기는 연간 − 세 분기로 만든다. 같은 기간은 가장 늦게 공시한 값."""
    q, a = {}, {}
    for f in facts:
        if "start" not in f or f.get("form") not in ("10-Q", "10-K", "10-Q/A", "10-K/A"):
            continue
        dur = (_d(f["end"]) - _d(f["start"])).days
        key = (f["start"], f["end"])
        box = q if 70 <= dur <= 110 else a if 350 <= dur <= 380 else None
        if box is not None and (key not in box or f["filed"] > box[key][1]):
            box[key] = (f["val"], f["filed"])
    q = {k: v[0] for k, v in q.items()}
    for (s, e), (val, _) in a.items():
        inside = [k for k in q if k[0] >= s and k[1] <= e]
        if len(inside) == 3 and not any(k[1] == e for k in inside):
            last = max(k[1] for k in inside)
            q[((_d(last) + datetime.timedelta(days=1)).isoformat(), e)] = val - sum(q[k] for k in inside)
    return q


def _cq(start, end):
    """분기 가운데 날짜가 속한 달력 분기 — 회계 분기가 다른 회사들을 나란히 놓는다 (2-7)."""
    m = _d(start) + (_d(end) - _d(start)) / 2
    return f"{m.year}Q{(m.month - 1) // 3 + 1}"


def revenue_series(cik):
    facts = _sec(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json").get("facts", {}).get("us-gaap", {})
    cutoff = (datetime.date.today() - datetime.timedelta(days=4 * 365)).isoformat()
    best = {}
    for c in REV_CONCEPTS:   # 최근 4년 분기가 가장 많은 항목 하나를 쓴다 (회사마다 매출 항목 이름이 다르다)
        q = _quarters((facts.get(c) or {}).get("units", {}).get("USD", []))
        q = {k: v for k, v in q.items() if k[1] >= cutoff}
        if len(q) > len(best):
            best = q
    rows = sorted(({"start": s, "end": e, "rev": v} for (s, e), v in best.items()), key=lambda r: r["end"])
    for r in rows:
        prev = [x for x in rows if abs((_d(r["end"]) - _d(x["end"])).days - 364) <= 20]
        r["yoy"] = (r["rev"] / prev[0]["rev"] - 1) * 100 if prev and prev[0]["rev"] else None
        r["cq"] = _cq(r["start"], r["end"])
    return rows


def collect_revenue(conn):
    have = _get(conn, "expect_revenue")
    if have and (datetime.date.today() - _d(have["built"])).days < REV_MAX_AGE_DAYS:
        return have
    tickers = _sec("https://www.sec.gov/files/company_tickers.json")
    cik = {v["ticker"]: str(v["cik_str"]).zfill(10) for v in tickers.values()}
    series = {}
    for s in PEERS:
        try:
            series[s] = revenue_series(cik[s])
        except Exception as e:   # noqa: BLE001
            print(f"[expect] {s} 매출 실패 : {e}")
    out = {"built": datetime.date.today().isoformat(), "series": series}
    _put(conn, "expect_revenue", out)
    print(f"[expect] 매출 {len(series)}/{len(PEERS)}종목 (SEC XBRL)")
    return out


# ---------------------------------------------------------------- 2 · 4. 예상치 · 공매도 (yfinance) · 3. SPY 옵션

def _eps(t):
    tr, rv = t.eps_trend, t.eps_revisions
    row = tr.loc["+1y"]
    out = {k: float(row[k]) for k in ("current", "7daysAgo", "30daysAgo", "60daysAgo", "90daysAgo") if row.get(k) == row.get(k)}
    if rv is not None and "+1y" in rv.index:
        out["up30"], out["down30"] = int(rv.loc["+1y"].get("upLast30days") or 0), int(rv.loc["+1y"].get("downLast30days") or 0)
    return out


def _short(t):
    i = t.info
    fl = i.get("floatShares")
    out = {"shares": i.get("sharesShort"), "prior": i.get("sharesShortPriorMonth"), "float": fl,
           "asof": i.get("dateShortInterest"), "prior_asof": i.get("sharesShortPreviousMonthDate")}
    if fl:
        out["pct"] = out["shares"] / fl * 100 if out["shares"] else None
        out["prior_pct"] = out["prior"] / fl * 100 if out["prior"] else None
    for k in ("asof", "prior_asof"):
        if isinstance(out[k], (int, float)):
            out[k] = datetime.datetime.utcfromtimestamp(out[k]).date().isoformat()
    return out


def _atm_iv(t, spot, day):
    exps = t.options
    e = min(exps, key=lambda x: abs((_d(x) - _d(day)).days - 30))
    ch = t.option_chain(e)
    ivs = []
    for df in (ch.calls, ch.puts):
        near = df.iloc[(df["strike"] - spot).abs().argsort()[:2]]
        ivs += [v for v in near["impliedVolatility"] if v and v == v and 0.03 < v < 3]
    return sum(ivs) / len(ivs) if ivs else None


def collect_daily(conn, day):
    import yfinance as yf
    have = _get(conn, "expect_daily")
    if have and have.get("day") == day:
        return have
    eps, short = {}, {}
    for s in PEERS:
        t = yf.Ticker(s)
        try:
            eps[s] = _eps(t)
        except Exception as e:   # noqa: BLE001
            print(f"[expect] {s} 예상치 실패 : {e}")
        try:
            short[s] = _short(t)
        except Exception as e:   # noqa: BLE001
            print(f"[expect] {s} 공매도 실패 : {e}")
    spy_iv = None
    try:
        spot = collect_market.close_on(conn, "SPY", day)
        spy_iv = _atm_iv(yf.Ticker("SPY"), spot, day) if spot else None
    except Exception as e:   # noqa: BLE001
        print(f"[expect] SPY 옵션 실패 : {e}")
    out = {"day": day, "eps": eps, "short": short, "spy_iv": spy_iv}
    _put(conn, "expect_daily", out)
    print(f"[expect] 예상치 {len(eps)} · 공매도 {len(short)} · SPY 옵션 {'있음' if spy_iv else '없음'}")
    return out


def collect(conn, day):
    for f in (collect_revenue, lambda c: collect_daily(c, day)):
        try:
            f(conn)
        except Exception as e:   # noqa: BLE001
            print(f"[expect] 수집 실패 — 지난 값으로 계속 : {e}")


# ---------------------------------------------------------------- 판정

def _med(xs, need=MIN_PEERS):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if len(xs) >= need else None


def card_revenue(conn):
    rv = _get(conn, "expect_revenue")
    if not rv or not rv["series"].get(config.SYMBOL):
        return None
    me = [r for r in rv["series"][config.SYMBOL] if r.get("yoy") is not None][-8:]
    if not me:
        return None
    by_cq = {}
    for s, rows in rv["series"].items():
        for r in rows:
            if r.get("yoy") is not None:
                by_cq.setdefault(r["cq"], []).append(r["yoy"])
    bars = [{"cq": r["cq"], "end": r["end"], "stock": r["yoy"], "peers": _med(by_cq.get(r["cq"], [])), "n_peers": len(by_cq.get(r["cq"], []))} for r in me]
    last = me[-1]
    prev = [r for r in rv["series"][config.SYMBOL] if r["end"] < last["end"]]
    yoy = last["yoy"]
    state = "늘고 있음" if yoy >= REV_PCT else "줄고 있음" if yoy <= -REV_PCT else "비슷함"
    q = {r["metric"]: r["value"] for r in conn.execute(
        "SELECT metric, value FROM quarterly WHERE fiscal_quarter = (SELECT MAX(fiscal_quarter) FROM quarterly WHERE metric = 'revenue')")}
    guide = conn.execute("SELECT fiscal_quarter, value FROM quarterly WHERE metric = 'guidance_revenue_next' ORDER BY fiscal_quarter DESC LIMIT 1").fetchone()
    return {"state": state, "yoy": yoy, "rev": last["rev"], "end": last["end"], "qoq": (last["rev"] / prev[-1]["rev"] - 1) * 100 if prev else None,
            "bars": bars, "peers_last": bars[-1]["peers"], "dc_yoy": q.get("dc_revenue_yoy"), "beat": q.get("guidance_beat_pct"),
            "margin": q.get("gross_margin_nongaap"), "guide_next": guide["value"] if guide else None}


def card_eps(conn):
    dd = _get(conn, "expect_daily")
    me = (dd or {}).get("eps", {}).get(config.SYMBOL)
    if not me or "current" not in me:
        return None

    def chg(e, k):
        return (e["current"] / e[k] - 1) * 100 if e.get(k) else None
    wins = (("7일", "7daysAgo"), ("30일", "30daysAgo"), ("60일", "60daysAgo"), ("90일", "90daysAgo"))
    bars = [{"label": lb, "stock": chg(me, k), "peers": _med([chg(e, k) for s, e in dd["eps"].items() if "current" in e])} for lb, k in wins]
    c30 = bars[1]["stock"]
    state = "더 좋게 봄" if c30 is not None and c30 >= EPS_PCT else "더 나쁘게 봄" if c30 is not None and c30 <= -EPS_PCT else "그대로"   # 전망 말로 (2026-10-27 사용자 B안, 옛 올라가는 중 · 내려가는 중 · 큰 변화 없음)
    return {"state": state, "c30": c30, "bars": bars, "current": me["current"], "up30": me.get("up30"), "down30": me.get("down30")}


def _ewma_sigma(closes):
    var = None
    for a, b in zip(closes[:-1], closes[1:]):
        r = math.log(b / a)
        var = r * r if var is None else 0.94 * var + 0.06 * r * r
    return math.sqrt(var) * 100 if var else None


def card_move(conn, day, a):
    iv = next((c["value"] for c in (a["status"].get("options") or []) if c["key"] == "iv_atm_30d"), None)
    nr = a.get("normal_range") or {}
    if not iv or not nr.get("sigma_pct"):
        return None
    exp = iv / math.sqrt(252) * 100
    ratio = exp / nr["sigma_pct"]
    state = "평소보다 큼" if ratio >= MOVE_HI else "평소보다 작음" if ratio <= MOVE_LO else "평소 수준"
    dd = _get(conn, "expect_daily") or {}
    spy_closes = [b["close"] for b in collect_market.bars(conn, "SPY") if b["day"] <= day][-260:]
    spy = {"exp": dd["spy_iv"] / math.sqrt(252) * 100 if dd.get("spy_iv") else None, "sigma": _ewma_sigma(spy_closes)}
    nxt, earn = a.get("next_earnings"), None
    days_to = (_d(nxt) - _d(day)).days if nxt else None
    em = a.get("earnings_moves") or {}
    imp = next((c["value"] for c in (a["status"].get("options") or []) if c["key"] == "implied_move_next_earnings"), None)
    earn_day = _earnings_day_move(imp, nr["sigma_pct"], day, nxt) if imp and nxt else None
    if days_to is not None and days_to <= 30 and earn_day and em.get("median_abs"):
        earn = {"exp": earn_day, "past": em["median_abs"], "n": len(em.get("moves") or [])}
    rank = next((c["value"] for c in (a["status"].get("options") or []) if c["key"] == "iv_rank_60d"), None)
    return {"state": state, "exp": exp, "sigma": nr["sigma_pct"], "ratio": ratio, "spy": spy, "earn": earn, "next_earnings": nxt,
            "earn_in_window": days_to is not None and days_to <= 30, "days_to": days_to, "iv": iv, "rank": rank, "imp": imp, "earn_day": earn_day,
            "past": em.get("median_abs")}


def _earnings_day_move(straddle_pct, sigma_d, day, earnings_day):
    """실적 발표 하루 몫의 시장 예상 (추정) — 상태판의 `실적 발표 예상 변동폭`은 실적 직후 만기까지(수 주) 전체 움직임의 스트래들 값이라
    하루 실제 반응과 견줄 수 없다 (2026-10-18 발견: ±9.9% vs 지난 8번 ±3.2%). 만기까지 평소 움직임의 몫을 빼고 남은 것을 실적 하루 몫으로 본다.
    |움직임| 기대값 = √(2/π)·σ 로 스트래들과 σ 를 오간다. 만기 = 실적 발표 다음 금요일(주간 옵션)."""
    import numpy as np
    ed = _d(earnings_day)
    expiry = ed + datetime.timedelta(days=(4 - ed.weekday()) % 7 or 7)
    n = int(np.busday_count(_d(day) + datetime.timedelta(days=1), expiry + datetime.timedelta(days=1)))
    k = math.sqrt(2 / math.pi)
    total = straddle_pct / k
    rest = max(0, n - 1) * sigma_d ** 2
    return k * math.sqrt(total ** 2 - rest) if total ** 2 > rest else None


def card_short(conn):
    dd = _get(conn, "expect_daily")
    me = (dd or {}).get("short", {}).get(config.SYMBOL)
    if not me or not me.get("shares") or not me.get("prior"):
        return None
    chg = (me["shares"] / me["prior"] - 1) * 100
    state = "늘어나는 중" if chg >= SHORT_PCT else "줄어드는 중" if chg <= -SHORT_PCT else "큰 변화 없음"
    peers = list(dd["short"].values())   # 기술주 15개 (엔비디아 포함 — 1 · 2번 카드와 같은 묶음)
    return {"state": state, "chg": chg, "pct": me.get("pct"), "prior_pct": me.get("prior_pct"), "asof": me.get("asof"), "prior_asof": me.get("prior_asof"),
            "shares": me["shares"], "peers_pct": _med([e.get("pct") for e in peers]),
            "peers_prior_pct": _med([e.get("prior_pct") for e in peers])}


def build(conn, day, a):
    out = {}
    for k, f in (("revenue", lambda: card_revenue(conn)), ("eps", lambda: card_eps(conn)), ("move", lambda: card_move(conn, day, a)), ("short", lambda: card_short(conn))):
        try:
            out[k] = f()
        except Exception as e:   # noqa: BLE001
            print(f"[expect] {k} 판정 실패 : {e}")
            out[k] = None
    return out
