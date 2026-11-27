"""한국 종목 분석 — 미국 종목(stock-radar/analyze.py)의 순수 계산 함수를 그대로 쓰고, 비교 대상만 KOSPI 로 (기획 11절).

종목마다: 종가 · 전일 대비 · 거래량 배수 · 평소 범위 · 기간별 수익률(KOSPI 대비) · 1년 범위 · 차트 지표 · 볼린저 · 과열 · 고점 회복 · 미국 연결 짝의 밤사이 움직임.
시장(자금 흐름, ECOS): 외국인 일별 순매수(20일 누적 · 평소 범위) · 투자자별 월별 · 예탁금 · 신용융자.
실적 발표 · 옵션 · 공시 · 애널리스트는 없다(1단계, 기획 11-1).
"""
import datetime
import json
import math
import os
import sys

import universe_kr as U

BASE = os.path.dirname(os.path.abspath(__file__))
for p in ("stock-radar", "nvda-report", "."):
    sys.path.insert(0, os.path.join(BASE, "..", p))
sys.path.insert(0, os.path.join(BASE, ".."))   # tech_signals (experiments/)
import analyze as A  # noqa: E402 — stock-radar (normal_range · period_returns · year_range · bollinger · overheat)
import crash_watch as CW  # noqa: E402 — 급락장에서 버틴 종목 (experiments/, 코스피가 2% 넘게 내린 날, 2026-11-04)
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
    try:
        import tech_signals   # experiments/ — 기술 지표 12 · 이동평균 · 피벗
        out["signals"] = tech_signals.compute(bars, market="kr")   # 이동평균 60 · 120일 · 배열 · 크로스 한국 관행 (P119)
    except Exception as e:   # noqa: BLE001
        print(f"[kr] 기술 지표 계산 실패 : {e}")
        out["signals"] = None
    out["vs_bench"] = r1 - (rb[t["day"]] / rb[p["day"]] - 1) * 100 if t["day"] in rb and p["day"] in rb else None
    return out


def day_path(bars, day=None):
    """오늘 하루 흐름 — 전일 종가 대비 시가 · 장중 고점 · 장중 저점 · 종가 %. day 를 주면 그날(지수를 종목 날짜에 맞춘다)."""
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


def _closed_us(bars):
    """미국 장중에 받은 오늘 봉(아직 종가 아님)은 뺀다 — GitHub cron 이 몇 시간 늦어 미국 장중(KST 밤)에 돌면 장중 값이 `그 뒤 미국 종가` 로 게시된다
    (2026-10-28, NVDA 10-24 장중 게시 사고와 같은 종류). 뉴욕 16:30 전이면 뉴욕 오늘 날짜 봉을 뺀다."""
    import datetime
    from zoneinfo import ZoneInfo
    ny = datetime.datetime.now(ZoneInfo("America/New_York"))
    if bars and ny.time() < datetime.time(16, 30) and bars[-1]["day"] >= ny.strftime("%Y-%m-%d"):
        return bars[:-1]
    return bars


def us_move(t, snap, kr_day, points=False):
    """미국 티커 하나의 움직임 둘 — `before` = 한국 장이 열리기 전 마지막 미국 거래일(한국 날짜보다 앞선 날, "밤사이") · `latest` = 그 뒤 더 새 미국 종가가 있으면
    (한국 장 마감 뒤 끝난 미국장 — 다음 한국장 전 참고). 미국 10-23 종가는 한국 10-24 새벽에 나오므로 한국 10-23 반응의 짝은 미국 10-22 다.
    points = 수익률 대신 포인트 차이(VIX)."""
    b = _closed_us((snap.get("us_bars") or {}).get(t) or [])
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


def _rel(snap, sym, n):
    a, b = _closes(snap["bars"].get(sym) or []), _closes(snap["bars"].get(U.BENCH) or [])
    if len(a) <= n or len(b) <= n:
        return None
    return ((a[-1] / a[-1 - n]) - (b[-1] / b[-1 - n])) * 100


def sector_flow(snap, sym):
    """'○○ 업계 자금 흐름은?' — 미국 sector_flow 와 같은 규칙(20거래일 업종 ETF − KOSPI, ±2%p), 순위는 한국 업종 ETF 끼리 (2026-10-31)."""
    etf = U.SECTOR_ETF.get(sym)
    n, pp = NC.SECTOR_FLOW_DAYS, NC.SECTOR_FLOW_PP
    rel = _rel(snap, etf, n) if etf else None
    if rel is None:
        return None
    sectors = sorted(({"etf": e, "name": nm, "rel": r} for e, nm in U.SECTOR_ETF_LIST.items() if (r := _rel(snap, e, n)) is not None), key=lambda x: -x["rel"])
    return {"etf": etf, "etf_label": U.SECTOR_ETF_LABEL.get(etf, etf), "name": U.SECTOR_ETF_LIST[etf], "state": "모이는 중" if rel >= pp else "빠져나가는 중" if rel <= -pp else "뚜렷하지 않음",
            "rel_pp": rel, "days": n, "sectors": sectors, "rank": 1 + sum(1 for x in sectors if x["rel"] > rel), "n_pool": len(sectors)}


def next_release(key, flow_data, today=None):
    """지표의 다음 발표일 — 국가데이터처 보도계획에서 그 보도자료 이름(U.RELEASE_OF)의 오늘 이후 첫 줄. 없으면 None."""
    name = U.RELEASE_OF.get(key)
    if not name:
        return None
    today = today or datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d")
    xs = [x for x in (flow_data or {}).get("release_plan") or [] if x["day"] >= today and x["title"].rstrip().endswith(name)]
    return min(xs, key=lambda x: (x["day"], x["time"])) if xs else None


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
                    "series": xs[-24:], "src_stat": stat, "next_release": next_release(key, flow_data)})   # 24개월 — 그래프 `작년 같은 달` 비교 (2026-10-25)
    return out


def related_rows(sym, flow_data):
    """함께 볼 지표 (U.related_for) — 업계 지표와 같은 줄 모양. 일별 값(환율 · 금리)은 다 끝난 달의 평균으로 바꾼다."""
    ind = (flow_data or {}).get("industry") or {}
    daily = (flow_data or {}).get("more_d") or {}
    out = []
    for key, why in U.related_for(sym):
        if key in U.RELATED_DAILY:
            src, name, kind = U.RELATED_DAILY[key]
            mon = {}
            for x in daily.get(src) or []:
                mon.setdefault(x["day"][:7], []).append(x["v"])
            cur = datetime.date.today().strftime("%Y-%m")   # 다 끝난 달만 — 이번 달 일부 평균을 1년 전 한 달 전체와 견주면 비교가 어긋난다
            xs = [{"month": m, "v": sum(v) / len(v)} for m, v in sorted(mon.items()) if m < cur]
            stat = "daily"
        else:
            xs = ind.get(key) or []
            stat, _item, name, kind, *_r = U.INDICATORS[key]
        if len(xs) < 13:
            continue
        last = xs[-1]
        y, mo = int(last["month"][:4]), last["month"][5:]
        prev = next((x["v"] for x in xs if x["month"] == f"{y - 1}-{mo}"), None)
        chg = (last["v"] - prev) if (kind == "pct" and prev is not None) else ((last["v"] / prev - 1) * 100 if prev else None)
        out.append({"key": key, "name": name, "kind": kind, "cmp": "yoy", "note": why, "month": last["month"], "v": last["v"], "chg": chg,
                    "series": xs[-24:], "src_stat": stat, "next_release": next_release(key, flow_data)})
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
         "pairs": pair_moves(sym, snap, t["day"]), "industry": industry_rows(sym, flow_data), "bsi": bsi_rows(sym, flow_data), "fin": fin_rows(sym, flow_data), "related": related_rows(sym, flow_data),
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


MONEY_DROP_PCT, MONEY_NEAR_PCT, MONEY_STREAK = 10.0, 5.0, 3   # `증시에서 돈이 빠져나가나?` 판정 — 대기 자금 · 신용 고점 대비 %, 외국인 연속 달 수


def _peak12(ser):
    """월별 [{month, v}] 최근 12개월 → (마지막 달, 마지막 값, 고점 달, 고점 값, 고점 대비 %)."""
    w = ser[-12:]
    last, top = w[-1], max(w, key=lambda x: x["v"])
    return last["month"], last["v"], top["month"], top["v"], (last["v"] / top["v"] - 1) * 100 if top["v"] else 0.0


def money_state(flow_data):
    """`증시에서 돈이 빠져나가나?` — 대기 자금(예탁금) · 외국인 순매수 · 빚투(신용융자)를 몇 달 흐름(12개월 고점 대비 · 몇 달째)으로 묶은 상태.
    셋 중 둘 이상: 예탁금 고점 대비 −10% 넘게 · 외국인 3개월 이상 연속 순매도 · 신용 고점 대비 −10% 넘게 = 빠져나가는 중.
    반대(고점 5% 안 · 3개월 이상 연속 순매수)가 둘 이상 = 들어오는 중, 그 밖 = 뚜렷하지 않음. 거래대금은 활기라 판정 밖(같이 보여 주기만).
    상태까지만 말한다 — 앞으로의 주가는 말하지 않는다. 수집 · AI 0(flows.json 그대로)."""
    fm, im = flow_data.get("funds_m") or {}, flow_data.get("investor_m") or {}
    ind, d = flow_data.get("industry") or {}, flow_data.get("daily") or {}
    dep, crd, frg = fm.get("deposits") or [], fm.get("credit_loan") or [], im.get("foreign") or []
    if len(dep) < 12 or len(crd) < 12 or len(frg) < 2:
        return None
    mo, dv, dmo, dtop, dpct = _peak12(dep)
    _, cv, cmo, ctop, cpct = _peak12(crd)
    sign = 1 if frg[-1]["v"] > 0 else -1
    n, tot = 0, 0.0
    for x in reversed(frg):
        if (x["v"] > 0) != (sign > 0):
            break
        n, tot = n + 1, tot + x["v"]
    out_ = sum([dpct <= -MONEY_DROP_PCT, sign < 0 and n >= MONEY_STREAK, cpct <= -MONEY_DROP_PCT])
    in_ = sum([dpct >= -MONEY_NEAR_PCT, sign > 0 and n >= MONEY_STREAK, cpct >= -MONEY_NEAR_PCT])
    state = "빠져나가는 중" if out_ >= 2 else "들어오는 중" if in_ >= 2 else "뚜렷하지 않음"
    res = {"month": mo, "state": state, "rule": {"drop_pct": MONEY_DROP_PCT, "near_pct": MONEY_NEAR_PCT, "streak": MONEY_STREAK},
           "deposits": {"v": dv, "top_month": dmo, "top": dtop, "pct": dpct},
           "credit": {"v": cv, "top_month": cmo, "top": ctop, "pct": cpct},
           "foreign": {"months": n, "sign": sign, "sum": tot, "since": frg[-n]["month"]}}   # 단위: 원 · 백만 원(순매수) 그대로
    tov = ind.get("kospi_turnover") or []
    if len(tov) >= 12:
        _, tv, tmo, ttop, tpct = _peak12(tov)
        res["turnover"] = {"month": tov[-1]["month"], "v": tv, "top_month": tmo, "top": ttop, "pct": tpct}   # 하루 평균 거래대금(천 원)
    fk = d.get("foreign_kospi") or []
    if fk and fk[-1]["day"][:7] > mo:   # 이번 달 — 일별(억 원)
        cur = fk[-1]["day"][:7]
        res["foreign"]["cur"] = {"month": cur, "to_day": fk[-1]["day"], "sum": sum(x["v"] for x in fk if x["day"].startswith(cur))}
    ks = {}
    for x in d.get("kospi") or []:
        ks[x["day"][:7]] = x["v"]
    months = [x["month"] for x in dep[-12:]]
    tvm = {x["month"]: x["v"] for x in tov}
    res["series"] = {"months": months, "deposits": [x["v"] for x in dep[-12:]], "turnover": [tvm.get(m) for m in months], "kospi": [ks.get(m) for m in months]}
    return res


def flows(flow_data, bench_bars):
    """외국인 일별 순매수(억원) → 오늘 · 20일 누적 · 평소 범위(EWMA) · 올해 누적. 투자자별 월별 · 증시자금 월별은 최근 값과 1년 범위."""
    if not flow_data:
        return None
    d = flow_data.get("daily") or {}
    fk, fq = d.get("foreign_kospi") or [], d.get("foreign_kosdaq") or []
    out = {"source": flow_data.get("source"), "fetched_at": flow_data.get("fetched_at"), "stale": bool(flow_data.get("stale"))}   # stale = ECOS 실패로 지난 자료 (2026-11-09)
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
    try:
        mn = money_state(flow_data)
        if mn:
            out["money"] = mn
    except Exception as ex:  # noqa: BLE001 — 카드 하나 때문에 시장 자료 전체가 빠지지 않게
        print(f"[kr] 돈의 흐름 판정 못 함: {str(ex)[:120]}")
    k = d.get("kospi") or []
    if k:
        out["kospi"] = {"day": k[-1]["day"], "close": k[-1]["v"], "ret_1d": (k[-1]["v"] / k[-2]["v"] - 1) * 100 if len(k) > 1 else None,
                        "series": k[-40:]}   # 외국인 순매수 그래프 아래 같은 날 코스피 등락
    # 시장 열기 — 거래대금(억원) 오늘 vs 20일 평균, 거래량(만주)
    tv, vo = d.get("turnover_kospi") or [], d.get("volume_kospi") or []
    if len(tv) > 21:
        avg20 = sum(x["v"] for x in tv[-21:-1]) / 20
        out["heat"] = {"day": tv[-1]["day"], "turnover": tv[-1]["v"], "turnover_ratio": tv[-1]["v"] / avg20 if avg20 else None,
                       "volume": vo[-1]["v"] if vo and vo[-1]["day"] == tv[-1]["day"] else None, "series": tv[-FLOW_WINDOW:],
                       "pct_rank_1y": sum(1 for x in tv[-252:] if x["v"] <= tv[-1]["v"]) / min(252, len(tv)) * 100,
                       "kosdaq_turnover": (d.get("turnover_kosdaq") or [{}])[-1].get("v"), "kosdaq_volume": (d.get("volume_kosdaq") or [{}])[-1].get("v"),
                       "avg20": avg20, "avg_1y": sum(x["v"] for x in tv[-252:]) / min(252, len(tv)), "series60": tv[-60:],   # 60거래일 선 + 1년 평균 (2026-11-05 M72)
                       "kosdaq_avg20": (lambda kq: sum(x["v"] for x in kq[-21:-1]) / 20 if len(kq) > 21 else None)(d.get("turnover_kosdaq") or [])}   # 오늘 vs 20일 평균 가로 막대 (M73)
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
                "chg_n": xs[-1]["v"] - xs[-1 - n_chg]["v"] if len(xs) > n_chg else None, "hi_1y": max(x["v"] for x in xs[-252:]), "lo_1y": min(x["v"] for x in xs[-252:]),
                "series": xs[-400:]}   # 1년 선 그래프 (2026-11-05 M70) — 기준금리는 주말도 있어 넉넉히
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
        return {"month": ser[-1]["month"], "v": ser[-1]["v"], "prev": ser[-2]["v"] if len(ser) > 1 else None, "hi12": max(vals), "lo12": min(vals), "avg12": sum(vals) / len(vals), "series": ser[-12:], "level": xs[-1]["v"], "index_series": xs[-37:]}   # 지수 수준 3년 선 (2026-11-05 M71)
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
        return {"q": last["q"], "v": last["v"], "same": same, "yoy": (last["v"] / same - 1) * 100 if same else None, "hi4": max(vals), "lo4": min(vals), "series": xs[-8:],
                "series_all": xs}   # 8분기 그래프의 1년 전 같은 분기 비교까지 (2026-11-05 M77)
    hh = {k2: _q(k2) for k2 in ("hh_surplus", "hh_surplus_rate", "hh_disp_income", "hh_credit", "hh_stock", "hh_stock_buy", "hh_fin_total")}
    if hh.get("hh_stock") and hh.get("hh_fin_total"):
        byq = {x["q"]: x["v"] for x in mq.get("hh_fin_total") or []}
        share = [{"q": x["q"], "v": x["v"] / byq[x["q"]] * 100} for x in mq.get("hh_stock") or [] if byq.get(x["q"])]   # 받은 분기 전부 — 8분기 그래프의 1년 전 비교까지 (2026-11-05 M69)
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
    crash = CW.compute(snap["bars"], "kr", [c[0] for c in U.CANDIDATES])   # 급락장에서 버틴 종목 — 홈 `주목할 종목` · 오늘 탭 카드
    mr = A.market_regime({"bars": {NC.REGIME_BENCHMARK: snap["bars"].get(U.BENCH) or []}})   # 시장 분위기 — 미국과 같은 규칙, KOSPI (VIX 없음 → 불안 국면 판정 없음, 2026-10-31)
    for s in stocks:
        s["market_regime"] = mr
        s["sector_flow"] = sector_flow(snap, s["sym"])
    # K18 모멘텀 순위(우리 종목 안) · K14 환율 · K21 WTI 를 종목에 붙인다 (카드에서 값만 보여 준다)
    ranked = sorted((s for s in stocks if s.get("mom_12_1") is not None), key=lambda s: -s["mom_12_1"])
    for i, s in enumerate(ranked, 1):
        s["mom_rank"] = (i, len(ranked))
    for s in stocks:
        s["fx"] = market.get("fx")
        if s["sym"] == "015760.KS":
            s["wti"] = market.get("wti")
    for s in stocks:
        s["crash"] = CW.for_stock(crash, s["sym"])
    return {"day": day, "fetched_at": snap["fetched_at"], "stocks": stocks, "market": market, "crash": crash, "indices": indices(snap)}


def indices(snap):
    """코스피 · 코스닥 종가 · 전일 대비 — 이미 받는 봉(^KS11 · ^KQ11)으로 계산만, 수집 추가 없음.
    kr.json → 시황 해설 pm 묶음 close.indices (수집기 14절 '장 날짜 첫 줄', 2026-11-17). 봉 날짜를 같이 줘 받는 쪽이 그날 값인지 본다."""
    out = []
    for sym, name in ((U.BENCH, "코스피"), (U.KOSDAQ, "코스닥")):
        b = [x for x in snap["bars"].get(sym) or [] if x.get("close")]
        if len(b) < 2:
            continue
        out.append({"name": name, "day": b[-1]["day"], "close": round(b[-1]["close"], 2), "chg_pct": round((b[-1]["close"] / b[-2]["close"] - 1) * 100, 2)})
    return out


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
