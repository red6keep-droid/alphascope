"""한국 종목 분석 — 미국 종목(stock-radar/analyze.py)의 순수 계산 함수를 그대로 쓰고, 비교 대상만 KOSPI 로 (기획 11절).

종목마다: 종가 · 전일 대비 · 거래량 배수 · 평소 범위 · 기간별 수익률(KOSPI 대비) · 1년 범위 · 차트 지표 · 볼린저 · 과열 · 고점 회복 · 미국 연결 짝의 밤사이 움직임.
시장(자금 흐름, ECOS): 외국인 일별 순매수(20일 누적 · 평소 범위) · 투자자별 월별 · 예탁금 · 신용융자.
실적 발표 · 옵션 · 공시 · 애널리스트는 없다(1단계, 기획 11-1).
"""
import json
import math
import os
import sys

import universe_kr as U

BASE = os.path.dirname(os.path.abspath(__file__))
for p in ("stock-radar", "nvda-report", "."):
    sys.path.insert(0, os.path.join(BASE, "..", p))
import analyze as A  # noqa: E402 — stock-radar (normal_range · period_returns · year_range · bollinger · overheat)
import indicators  # noqa: E402 — nvda-report
import config as NC  # noqa: E402 — nvda-report (RSI_PERIOD 등)

STATE = os.path.join(BASE, "data", "rank_state.json")
FLOW_WINDOW = 20      # 외국인 순매수 누적 창 (거래일)
FLOW_LAM = 0.94


def _closes(bars):
    return [x["close"] for x in bars]


def technical(bars, bench_bars):
    """차트 지표 — stock-radar technical 과 같은 정의, 하루 대비는 KOSPI."""
    c = _closes(bars)
    t, p = bars[-1], bars[-2]
    ma = lambda n: sum(c[-n:]) / n if len(c) >= n else None   # noqa: E731
    out = {"ma_rel": {n: (c[-1] / ma(n) - 1) * 100 for n in (20, 60, 120, 200) if ma(n)},
           "ma50": ma(50), "ma200": ma(200), "rsi14": indicators.rsi(c[-(NC.RSI_PERIOD * 10):]),
           "gap": (t["open"] / p["close"] - 1) * 100 if t.get("open") else None,
           "range_pct": (t["high"] - t["low"]) / t["close"] * 100 if t["close"] else None}
    pm50 = sum(c[-51:-1]) / 50 if len(c) >= 51 else None
    pm200 = sum(c[-201:-1]) / 200 if len(c) >= 201 else None
    cross = None
    if out["ma50"] and out["ma200"] and pm50 and pm200:
        cross = "golden" if pm50 <= pm200 and out["ma50"] > out["ma200"] else "death" if pm50 >= pm200 and out["ma50"] < out["ma200"] else None
    out["ma_cross"] = cross
    r1 = (t["close"] / p["close"] - 1) * 100
    rb = {x["day"]: x["close"] for x in bench_bars or []}
    bc = [x["close"] for x in bench_bars or [] if x["day"] <= t["day"]]   # 지수도 같은 날까지 — 평균선 대비 비교 막대 (2026-10-27 P37)
    out["bench_ma_rel"] = {n: (bc[-1] / (sum(bc[-n:]) / n) - 1) * 100 for n in (20, 60, 120, 200) if len(bc) >= n}
    out["path"], out["bench_path"] = day_path(bars), day_path(bench_bars, t["day"])   # 오늘 하루 흐름 (P41)
    out["vs_bench"] = r1 - (rb[t["day"]] / rb[p["day"]] - 1) * 100 if t["day"] in rb and p["day"] in rb else None
    return out


def day_path(bars, day=None):
    """오늘 하루 흐름 — 전일 종가 대비 시가 · 장중 고점 · 장중 저점 · 종가 % (2026-10-27 사용자 P41). day 를 주면 그날(지수를 종목 날짜에 맞춘다)."""
    if day is not None:
        bars = [x for x in bars or [] if x["day"] <= day]
    if not bars or len(bars) < 2 or bars[-1]["day"] != (day or bars[-1]["day"]):
        return None
    t, pc = bars[-1], bars[-2]["close"]
    if not pc or not t.get("open") or not t.get("high") or not t.get("low"):
        return None
    return {k: (t[k] / pc - 1) * 100 for k in ("open", "high", "low", "close")}


def drawdown(bars, yr, hist, sym):
    h = (hist or {}).get("stats") or {}
    if sym not in h or not yr:
        return None
    return {"stock": h[sym], "pct_from_high": yr["pct_from_high"], "days_since_high": sum(1 for x in bars if x["day"] > yr["high_day"])}


def us_move(t, snap, kr_day, points=False):
    """미국 티커 하나의 움직임 둘 — `before` = 한국 장이 열리기 전 마지막 미국 거래일(한국 날짜보다 앞선 날, "밤사이") · `latest` = 그 뒤 더 새 미국 종가가 있으면
    (한국 장 마감 뒤 끝난 미국장 — 다음 한국장 전 참고). 미국 10-23 종가는 한국 10-24 새벽에 나오므로 한국 10-23 반응의 짝은 미국 10-22 다.
    points = 수익률 대신 포인트 차이(VIX)."""
    b = (snap.get("us_bars") or {}).get(t) or []
    chg = (lambda i: b[i]["close"] - b[i - 1]["close"]) if points else (lambda i: (b[i]["adj"] / b[i - 1]["adj"] - 1) * 100)
    before = latest = None
    prev = [i for i in range(1, len(b)) if b[i]["day"] < kr_day]
    if prev:
        i = prev[-1]
        before = {"sym": t, "day": b[i]["day"], "ret": chg(i), "close": b[i]["close"], "points": points}
    if len(b) >= 2 and b[-1]["day"] >= kr_day:
        latest = {"sym": t, "day": b[-1]["day"], "ret": chg(len(b) - 1), "close": b[-1]["close"], "points": points}
    return before, latest


def pair_moves(sym, snap, kr_day):
    """미국 연결 짝 + 같은 회사 ADR(K24) + 반도체면 SOX(K25) 의 밤사이 움직임."""
    tickers, why = U.PAIRS.get(sym, ([], ""))
    before, latest = [], []
    for t in tickers:
        b, l = us_move(t, snap, kr_day)
        if b:
            before.append(b)
        if l:
            latest.append(l)
    adr = sox = None
    if sym in U.ADR:
        adr = us_move(U.ADR[sym], snap, kr_day)[0]
    if "반도체" in U.groups(sym):
        sox = us_move("^SOX", snap, kr_day)[0]
    return {"why": why, "moves": before, "latest": latest, "adr": adr, "sox": sox}


def _pct_rank(vals, v):
    return sum(1 for x in vals if x <= v) / len(vals) * 100 if vals else None


def bsi_rows(sym, flow_data):
    """K1 · K2 업종별 BSI — 항목(업황 · 매출 · 신규수주 · 채산성)마다 실적 · 전망 마지막 값, 전달 대비, 12개월 범위 위치, 역대 백분위(K5 바닥권 판정)."""
    ind, ind_name = U.bsi_industry(sym)
    data = ((flow_data or {}).get("bsi") or {}).get(ind) if ind else None
    if not data:
        return None
    rows = []
    for a_item, f_item, name in U.BSI_ITEMS:
        xa, xf = data.get(a_item) or [], data.get(f_item) or []
        if len(xa) < 2:
            continue
        vals12 = [x["v"] for x in xa[-12:]]
        allv = [x["v"] for x in xa]
        r = {"item": a_item, "f_item": f_item, "name": name, "month": xa[-1]["month"], "v": xa[-1]["v"], "chg": xa[-1]["v"] - xa[-2]["v"],
             "pos12": (xa[-1]["v"] - min(vals12)) / (max(vals12) - min(vals12)) * 100 if max(vals12) > min(vals12) else 50,
             "pct_all": _pct_rank(allv, xa[-1]["v"]), "n_all": len(allv), "series": xa[-24:]}   # 24개월 — 그래프 `작년 같은 달` 비교 (2026-10-25)
        if xf:
            r["forecast"] = xf[-1]["v"]
            r["forecast_month"] = xf[-1]["month"]
            r["forecast_pct_all"] = _pct_rank([x["v"] for x in xf], xf[-1]["v"])
        rows.append(r)
    return {"industry": ind, "industry_name": ind_name, "rows": rows, "record": U.BSI_RECORD.get(ind) or {}}


def fin_rows(sym, flow_data):
    """K10 업종 분기 기업경영분석 + K15 산업별 대출 — 마지막 분기 값, 전년 같은 분기 대비, 최근 4분기 범위."""
    out = []
    def pack(name, unit, xs, yoy_pct=False, note=""):
        if len(xs) < 2:
            return
        last = xs[-1]
        same = next((x["v"] for x in xs if x["q"] == f"{int(last['q'][:4]) - 1}{last['q'][4:]}"), None)
        vals = [x["v"] for x in xs[-4:]]
        d = None if same is None else ((last["v"] / same - 1) * 100 if yoy_pct and same else last["v"] - same)
        out.append({"name": name, "unit": unit, "q": last["q"], "v": last["v"], "chg": d, "chg_unit": "%" if yoy_pct else "%p", "hi4": max(vals), "lo4": min(vals), "note": note, "series": xs[-8:]})
    ind, ind_name = U.fin_industry(sym)
    fq = ((flow_data or {}).get("fin_q") or {}).get(ind) if ind else None
    if fq:
        for stat, _item, name, unit in U.FIN_ITEMS:
            pack(f"{ind_name} {name}", unit, fq.get(stat) or [], note="한국은행 기업경영분석 · 종합")
    lind, lname = U.loan_industry(sym)
    lq = ((flow_data or {}).get("loan_q") or {}).get(lind) if lind else None
    if lq:
        pack(f"{lname} 은행 대출 잔액", "조 원", lq, yoy_pct=True, note="예금은행 산업별 대출금 · 후행 지표로 알려져 있다")
    return out


def momentum(bars):
    """K18 12-1 모멘텀 — 12개월 전 대비 1개월 전 가격 (%). 최근 1개월은 단기 반전 때문에 뺀다 (학계 표준)."""
    c = _closes(bars)
    return (c[-21] / c[-252] - 1) * 100 if len(c) >= 252 and c[-252] else None


def industry_rows(sym, flow_data):
    """종목의 업종 재료 지표 — 마지막 값 · 비교(전년 동월 또는 전월) · 12개월 범위 위치."""
    ind = dict((flow_data or {}).get("industry") or {})
    for dk_, (a_key, b_key, *_r) in U.DERIVED.items():   # 파생 지표 = a − b (같은 달끼리)
        a_, b_ = {x["month"]: x["v"] for x in ind.get(a_key) or []}, {x["month"]: x["v"] for x in ind.get(b_key) or []}
        ind[dk_] = [{"month": mo, "v": a_[mo] - b_[mo]} for mo in sorted(a_) if mo in b_]
    out = []
    for key in U.indicators_for(sym):
        xs = ind.get(key) or []
        if len(xs) < 2:
            continue
        stat, item, name, kind, cmp_, note = (("derived", "", *U.DERIVED[key][2:]) if key in U.DERIVED else U.INDICATORS[key])
        last = xs[-1]
        if cmp_ == "yoy":
            y, mo = int(last["month"][:4]), last["month"][5:]
            prev = next((x["v"] for x in xs if x["month"] == f"{y - 1}-{mo}"), None)
        else:
            prev = xs[-2]["v"]
        chg = (last["v"] - prev) if (kind == "pct" and prev is not None) else ((last["v"] / prev - 1) * 100 if prev else None)   # 금리 · 연체율은 %p 차이
        vals = [x["v"] for x in xs[-12:]]
        pos = (last["v"] - min(vals)) / (max(vals) - min(vals)) * 100 if max(vals) > min(vals) else 50
        out.append({"key": key, "name": name, "kind": kind, "cmp": cmp_, "note": note, "month": last["month"], "v": last["v"], "chg": chg, "pos12": pos,
                    "series": xs[-24:], "src_stat": stat})   # 24개월 — 그래프 `작년 같은 달` 비교 (2026-10-25)
    return out


def stock(sym, snap, hist, flow_data=None):
    bars = snap["bars"].get(sym) or []
    if len(bars) < 2:
        return None
    bench = snap["bars"].get(U.BENCH) or []
    t, p = bars[-1], bars[-2]
    vol20 = [x["volume"] for x in bars[-21:-1] if x["volume"]]
    yr = A.year_range(bars)
    tech = technical(bars, bench)
    s = {"sym": sym, "code": U.code(sym), "name": U.name(sym), "market": U.market(sym), "sector": U.sector(sym), "day": t["day"], "close": t["close"],
         "ret_1d": (t["adj"] / p["adj"] - 1) * 100,
         "vol_ratio": t["volume"] / (sum(vol20) / len(vol20)) if vol20 and t["volume"] else None,
         "cap": snap["caps"].get(sym), "normal_range": A.normal_range(bars, set()),
         "periods": A.period_returns(bars, bench), "year_range": yr, "tech": tech,
         "bollinger": A.bollinger(bars), "overheat": A.overheat(bars, tech), "drawdown": drawdown(bars, yr, hist, sym),
         "pairs": pair_moves(sym, snap, t["day"]), "industry": industry_rows(sym, flow_data), "bsi": bsi_rows(sym, flow_data), "fin": fin_rows(sym, flow_data),
         "mom_12_1": momentum(bars), "trade_tag": U.TRADE_TAG.get(sym), "_bars": bars}
    return s


# ── 순위 (미국 update_ranks 와 같은 규칙 — 유가증권 보통주만, SWAP_DAYS 연속 밀리면 교체) ──

def update_ranks(stocks, day, path=STATE):
    ranked = sorted((s for s in stocks if s["cap"] and U.rankable(s["sym"])), key=lambda s: -s["cap"])
    for i, s in enumerate(ranked, 1):
        s["rank"] = i
    try:
        with open(path, encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {"day": None, "top": [], "history": []}
    by = {s["sym"]: s for s in ranked}
    cur = [s["sym"] for s in ranked[:U.TOP_N]]
    if not st["top"]:
        top = cur
    else:
        top = [x for x in st["top"] if x in by]
        hist = (st.get("history") or []) + [cur]
        hist = hist[-60:]
        for x in list(top):   # 11위 밖으로 SWAP_DAYS 연속이면 뺀다
            if all(x not in h for h in hist[-U.SWAP_DAYS:]) and len(hist) >= U.SWAP_DAYS:
                top.remove(x)
        for x in cur:         # 빈자리는 지금 순위 순으로
            if len(top) >= U.TOP_N:
                break
            if x not in top:
                top.append(x)
        st["history"] = hist
    if st.get("day") != day:
        st["history"] = ((st.get("history") or []) + [cur])[-60:] if st["top"] else [cur]
    st.update(day=day, top=top)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(st, f)
    for s in stocks:
        s["in_top"] = s["sym"] in top
    return sorted(stocks, key=lambda s: (not s["in_top"], s.get("rank") or 999, -(s["cap"] or 0)))


# ── 시장 · 자금 흐름 (ECOS) ─────────────────────────────────────────────

def _ewma_sd(vals, lam=FLOW_LAM):
    var = None
    for v in vals[:-1]:
        var = v * v if var is None else lam * var + (1 - lam) * v * v
    return math.sqrt(var) if var else None


def flows(flow_data, bench_bars):
    """외국인 일별 순매수(억원) → 오늘 · 20일 누적 · 평소 범위(EWMA) · 올해 누적. 투자자별 월별 · 증시자금 월별은 최근 값과 1년 범위."""
    if not flow_data:
        return None
    d = flow_data.get("daily") or {}
    fk, fq = d.get("foreign_kospi") or [], d.get("foreign_kosdaq") or []
    out = {"source": flow_data.get("source"), "fetched_at": flow_data.get("fetched_at")}
    if fk:
        vals = [x["v"] for x in fk]
        sd = _ewma_sd(vals)
        today = vals[-1]
        cum20 = sum(vals[-FLOW_WINDOW:])
        year = fk[-1]["day"][:4]
        ytd = sum(x["v"] for x in fk if x["day"].startswith(year))
        streak, sign = 0, 1 if today > 0 else -1
        for v in reversed(vals):
            if (v > 0) == (sign > 0) and v != 0:
                streak += 1
            else:
                break
        past20 = [sum(vals[i - FLOW_WINDOW:i]) for i in range(FLOW_WINDOW, len(vals))]
        rank20 = sum(1 for v in past20 if v <= cum20) / len(past20) * 100 if past20 else None
        out["foreign"] = {"day": fk[-1]["day"], "today": today, "z": today / sd if sd else None, "sigma": sd, "cum20": cum20, "ytd": ytd, "streak": streak,
                          "streak_sign": sign, "cum20_pct_rank": rank20, "series": fk[-FLOW_WINDOW * 3:],
                          "kosdaq_today": fq[-1]["v"] if fq and fq[-1]["day"] == fk[-1]["day"] else None}
    inv = flow_data.get("investor_m") or {}
    if inv.get("foreign"):
        out["investor_m"] = {k: v[-12:] for k, v in inv.items()}
        # 거래 비중 = (매수 + 매도) / 전체 (매수 + 매도), 월별 — 개인 비중이 높아지면 과열로 읽히곤 한다
        def _by_month(key):
            return {x["month"]: x["v"] for x in inv.get(key) or []}
        tot_b, tot_s = _by_month("all_buy"), _by_month("all_sell")
        shares = []
        for mo in sorted(tot_b):
            den = tot_b.get(mo, 0) + tot_s.get(mo, 0)
            if not den:
                continue
            row = {"month": mo}
            for who in ("indiv", "foreign", "inst", "foreign_other", "corp_other"):
                row[who] = (_by_month(who + "_buy").get(mo, 0) + _by_month(who + "_sell").get(mo, 0)) / den * 100
            row["total"] = den / 1e6   # 조원
            shares.append(row)
        if shares:
            vals = [r["indiv"] for r in shares[-12:]]
            out["investor_share"] = {"series": shares[-12:], "last": shares[-1], "indiv_hi12": max(vals), "indiv_lo12": min(vals)}
    fm = flow_data.get("funds_m") or {}
    if fm.get("credit_loan"):
        def _rng(series):
            vals = [x["v"] for x in series[-12:]]
            return {"last": series[-1], "prev": series[-2] if len(series) > 1 else None, "hi12": max(vals), "lo12": min(vals), "series": series[-24:]}
        out["funds_m"] = {k: _rng(v) for k, v in fm.items() if v}
    k = d.get("kospi") or []
    if k:
        out["kospi"] = {"day": k[-1]["day"], "close": k[-1]["v"], "ret_1d": (k[-1]["v"] / k[-2]["v"] - 1) * 100 if len(k) > 1 else None}
    # 시장 열기 — 거래대금(억원) 오늘 vs 20일 평균, 거래량(만주)
    tv, vo = d.get("turnover_kospi") or [], d.get("volume_kospi") or []
    if len(tv) > 21:
        avg20 = sum(x["v"] for x in tv[-21:-1]) / 20
        out["heat"] = {"day": tv[-1]["day"], "turnover": tv[-1]["v"], "turnover_ratio": tv[-1]["v"] / avg20 if avg20 else None,
                       "volume": vo[-1]["v"] if vo and vo[-1]["day"] == tv[-1]["day"] else None, "series": tv[-FLOW_WINDOW:],
                       "pct_rank_1y": sum(1 for x in tv[-252:] if x["v"] <= tv[-1]["v"]) / min(252, len(tv)) * 100,
                       "kosdaq_turnover": (d.get("turnover_kosdaq") or [{}])[-1].get("v"), "kosdaq_volume": (d.get("volume_kosdaq") or [{}])[-1].get("v")}
    mc = d.get("mcap_kospi") or []
    if mc:
        vals = [x["v"] for x in mc[-252:]]
        out["mcap"] = {"day": mc[-1]["day"], "v": mc[-1]["v"], "chg_1d": (mc[-1]["v"] / mc[-2]["v"] - 1) * 100 if len(mc) > 1 else None, "hi_1y": max(vals), "lo_1y": min(vals),
                       "pct_rank_1y": sum(1 for v in vals if v <= mc[-1]["v"]) / len(vals) * 100}
    md = flow_data.get("more_d") or {}
    ns = md.get("news_sentiment") or []
    if len(ns) > 21:
        vals = [x["v"] for x in ns]
        out["news"] = {"day": ns[-1]["day"], "v": ns[-1]["v"], "avg20": sum(vals[-20:]) / 20, "avg_1y": sum(vals[-365:]) / len(vals[-365:]),
                       "pct_rank_1y": sum(1 for v in vals[-365:] if v <= vals[-1]) / len(vals[-365:]) * 100, "series": ns[-60:]}
    def _last(key, n_chg=20):
        xs = md.get(key) or []
        if not xs:
            return None
        return {"day": xs[-1]["day"], "v": xs[-1]["v"], "chg_1d": xs[-1]["v"] - xs[-2]["v"] if len(xs) > 1 else None,
                "chg_n": xs[-1]["v"] - xs[-1 - n_chg]["v"] if len(xs) > n_chg else None, "hi_1y": max(x["v"] for x in xs[-252:]), "lo_1y": min(x["v"] for x in xs[-252:])}
    rates = {k2: _last(k2) for k2 in ("ktb3", "ktb10", "corp_aa", "corp_bbb", "base_rate")}
    if any(rates.values()):
        out["rates"] = rates
    fx = {k2: _last(k2) for k2 in ("usdkrw", "jpykrw100", "cnykrw")}
    if fx.get("usdkrw"):
        out["fx"] = fx
    wti = md.get("wti") or []
    if len(wti) > 21:   # K21 — 달러/배럴, 하루 변화는 %
        out["wti"] = {"day": wti[-1]["day"], "v": wti[-1]["v"], "chg_1d": (wti[-1]["v"] / wti[-2]["v"] - 1) * 100 if wti[-2]["v"] else None,
                      "chg_n": (wti[-1]["v"] / wti[-21]["v"] - 1) * 100 if wti[-21]["v"] else None, "hi_1y": max(x["v"] for x in wti[-252:]), "lo_1y": min(x["v"] for x in wti[-252:])}
    mm = flow_data.get("more_m") or {}
    def _m(key):
        xs = mm.get(key) or []
        if not xs:
            return None
        vals = [x["v"] for x in xs[-12:]]
        return {"month": xs[-1]["month"], "v": xs[-1]["v"], "prev": xs[-2]["v"] if len(xs) > 1 else None, "hi12": max(vals), "lo12": min(vals),
                "avg_all": sum(x["v"] for x in xs) / len(xs), "series": xs[-24:]}
    val = {k2: _m(k2) for k2 in ("per", "div_yield", "turnover_ratio")}
    if val.get("per"):
        if val.get("div_yield") and rates.get("ktb3"):   # K29 일드갭 = KOSPI 배당수익률 − 국고채 3년 (%p) — 검증: 이후 KOSPI 와 관계 없음, 값만
            val["yield_gap"] = {"v": val["div_yield"]["v"] - rates["ktb3"]["v"], "month": val["div_yield"]["month"], "ktb3": rates["ktb3"]["v"]}
        out["valuation"] = val
    # 경제 바탕 — 지수형(물가 · 생산 · 수출 · 고용)은 전년 동월 대비 %, 심리형(ESI · CSI · BSI · 선행 순환)은 값 그대로, 모두 12개월 범위 위치
    def _yoy(key):
        xs = mm.get(key) or []
        if len(xs) < 13:
            return None
        bym = {x["month"]: x["v"] for x in xs}
        ser = []
        for x in xs:
            y, mo = int(x["month"][:4]), x["month"][5:]
            prev = bym.get(f"{y - 1}-{mo}")
            if prev:
                ser.append({"month": x["month"], "v": (x["v"] / prev - 1) * 100})
        if not ser:
            return None
        vals = [s_["v"] for s_ in ser[-12:]]
        return {"month": ser[-1]["month"], "v": ser[-1]["v"], "prev": ser[-2]["v"] if len(ser) > 1 else None, "hi12": max(vals), "lo12": min(vals), "avg12": sum(vals) / len(vals), "series": ser[-12:], "level": xs[-1]["v"]}
    def _lvl(key):
        xs = mm.get(key) or []
        if not xs:
            return None
        vals = [x["v"] for x in xs[-12:]]
        return {"month": xs[-1]["month"], "v": xs[-1]["v"], "prev": xs[-2]["v"] if len(xs) > 1 else None, "hi12": max(vals), "lo12": min(vals), "avg12": sum(vals) / len(vals), "series": xs[-12:]}
    macro = {"cpi": _yoy("cpi"), "ppi": _yoy("ppi"), "exports": _yoy("exports"), "ip": _yoy("ip"), "emp_insured": _yoy("emp_insured"),
             "esi": _lvl("esi"), "csi": _lvl("csi"), "bsi": _lvl("bsi"), "lead_cycle": _lvl("lead_cycle"), "tot": _lvl("tot")}
    qs = (flow_data.get("more_q") or {}).get("op_margin") or []
    if qs:   # 분기 — 최근 4분기 범위 · 전년 같은 분기와 비교 (계절성 때문에 전 분기가 아니라)
        vals = [x["v"] for x in qs[-4:]]
        same = next((x["v"] for x in qs if x["q"] == f"{int(qs[-1]['q'][:4]) - 1}{qs[-1]['q'][4:]}"), None)
        macro["op_margin"] = {"month": qs[-1]["q"], "v": qs[-1]["v"], "prev": same, "hi12": max(vals), "lo12": min(vals), "avg12": sum(vals) / len(vals), "series": qs[-8:], "quarterly": True}
    if any(macro.values()):
        out["macro"] = macro
    # 가계 — 개인의 매수 여력 (분기). 비교는 전년 같은 분기(계절성)
    mq = flow_data.get("more_q") or {}
    def _q(key, pct_of=None):
        xs = mq.get(key) or []
        if not xs:
            return None
        byq = {x["q"]: x["v"] for x in xs}
        last = xs[-1]
        same = byq.get(f"{int(last['q'][:4]) - 1}{last['q'][4:]}")
        vals = [x["v"] for x in xs[-4:]]
        return {"q": last["q"], "v": last["v"], "same": same, "yoy": (last["v"] / same - 1) * 100 if same else None, "hi4": max(vals), "lo4": min(vals), "series": xs[-8:]}
    hh = {k2: _q(k2) for k2 in ("hh_surplus", "hh_surplus_rate", "hh_disp_income", "hh_credit", "hh_stock", "hh_stock_buy", "hh_fin_total")}
    if hh.get("hh_stock") and hh.get("hh_fin_total"):
        st, ft = hh["hh_stock"], hh["hh_fin_total"]
        byq = {x["q"]: x["v"] for x in ft["series"]}
        share = [{"q": x["q"], "v": x["v"] / byq[x["q"]] * 100} for x in st["series"] if byq.get(x["q"])]
        hh["hh_stock_share"] = {"q": share[-1]["q"], "v": share[-1]["v"], "series": share, "hi4": max(s_["v"] for s_ in share[-4:]), "lo4": min(s_["v"] for s_ in share[-4:])} if share else None
    if any(hh.values()):
        out["household"] = hh
    cv, pv = mm.get("call_vol") or [], mm.get("put_vol") or []
    if cv and pv:
        pc = [{"month": c["month"], "v": p_["v"] / c["v"]} for c, p_ in zip(cv, pv) if c["v"]]
        vals12 = [x["v"] for x in pc[-12:]]
        out["derivatives"] = {"month": pc[-1]["month"], "put_call": pc[-1]["v"], "pc_hi12": max(vals12), "pc_lo12": min(vals12), "pc_series": pc[-12:],
                              "fut_amt_avg": _m("fut_amt_avg"), "opt_amt_avg": _m("opt_amt_avg")}
    return out


def overnight(snap, kr_day):
    """K24 · K25 목록 페이지 '밤사이 미국은?' — EWY · SOX · VIX · 달러지수의 밤사이 움직임과 그 뒤 더 새 종가."""
    out = []
    for t, label in U.US_MARKET.items():
        b, l = us_move(t, snap, kr_day, points=t in U.US_MARKET_POINTS)
        if b:
            out.append({"sym": t, "label": label, "before": b, "latest": l, "record": U.OVERNIGHT_RECORD.get(t)})
    return out


def run(snap, flow_data=None, hist=None):
    stocks = [x for x in (stock(c[0], snap, hist, flow_data) for c in U.CANDIDATES) if x]
    day = max(s["day"] for s in stocks)
    stocks = update_ranks(stocks, day)
    market = flows(flow_data, snap["bars"].get(U.BENCH)) or {}
    market["overnight"] = overnight(snap, day)
    # K18 모멘텀 순위(우리 종목 안) · K14 환율 · K21 WTI 를 종목에 붙인다 (카드에서 값만 보여 준다)
    ranked = sorted((s for s in stocks if s.get("mom_12_1") is not None), key=lambda s: -s["mom_12_1"])
    for i, s in enumerate(ranked, 1):
        s["mom_rank"] = (i, len(ranked))
    for s in stocks:
        s["fx"] = market.get("fx")
        if s["sym"] == "015760.KS":
            s["wti"] = market.get("wti")
    return {"day": day, "fetched_at": snap["fetched_at"], "stocks": stocks, "market": market}


if __name__ == "__main__":
    import collect_kr
    snap, fl, hist = collect_kr.load()
    a = run(snap, fl, hist)
    for s in a["stocks"][:12]:
        print(f"{s.get('rank') or '-':>3} {'★' if s['in_top'] else ' '} {s['name']:10s} {s['close']:>12,.0f}원 {s['ret_1d']:+.2f}% 시총 {(s['cap'] or 0) / 1e12:6.1f}조 "
              f"KOSPI대비 {s['tech']['vs_bench'] and round(s['tech']['vs_bench'], 2)} 짝 {[(m['sym'], round(m['ret'], 1)) for m in s['pairs']['moves']]}")
    m = a["market"] or {}
    if m.get("foreign"):
        f = m["foreign"]
        print(f"외국인 {f['day']} 오늘 {f['today']:+,.0f}억 (z {f['z']:.1f}) · 20일 누적 {f['cum20']:+,.0f}억 (과거 20일 누적 중 {f['cum20_pct_rank']:.0f}% 지점) · 연속 {f['streak']}일 · 올해 {f['ytd']:+,.0f}억")
    if m.get("funds_m"):
        c = m["funds_m"]["credit_loan"]
        print(f"신용융자 {c['last']['month']} {c['last']['v'] / 1e12:.1f}조 (12개월 {c['lo12'] / 1e12:.1f}~{c['hi12'] / 1e12:.1f}조)")
