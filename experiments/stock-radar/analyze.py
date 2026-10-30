"""종목별 숫자 — 순위 · 오늘 · 평소 범위 · 기간별 수익률 · 1년 범위 · 실적. 모두 파이썬 값 (AI 없음).

평소 범위는 NVDA 리포트와 같은 자(normal_range_line): EWMA λ 0.94 로그 수익률, 실적 반응일 제외, 전날까지의 값으로 오늘을 잰다, 2배 이상 = 밖.
수익률 · 평소 범위는 배당 반영 종가(adj), 화면 가격 · 1년 고저는 실제 거래 가격(close · high · low).
"""

import datetime
import json
import math
import os

import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nvda-report"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))   # tech_signals (experiments/)
import config as NC  # noqa: E402  — NVDA 리포트 기준값(국면 · 섹터 흐름 · 볼린저 · 과열)을 그대로 쓴다
import indicators  # noqa: E402

import universe as U  # noqa: E402

LAM, Z_OUT = 0.94, 2.0
PERIODS = (("1주", 5), ("1개월", 21), ("3개월", 63), ("6개월", 126), ("1년", 252))
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "rank_state.json")


def reaction_days(days, earnings):
    """실적 발표 → 가격이 처음 반응한 거래일. 장 시작 전 = 그날(휴일 · 주말이면 다음 거래일), 장 마감 뒤 = 다음 거래일."""
    out = []
    for e in earnings:
        nxt = [d for d in days if (d >= e["day"] if e["when"] == "bmo" else d > e["day"])]
        if nxt and nxt[0] != days[0]:
            out.append((e["day"], nxt[0]))
    return out


def normal_range(bars, earn_days):
    rows, var = [], None
    for i in range(1, len(bars)):
        r = math.log(bars[i]["adj"] / bars[i - 1]["adj"])
        d = bars[i]["day"]
        sd = math.sqrt(var) if var else None
        if d not in earn_days:
            var = r * r if var is None else LAM * var + (1 - LAM) * r * r
        rows.append({"day": d, "z": r / sd if sd else None, "sd": sd, "earn": d in earn_days})
    if len(rows) < 260 or rows[-1]["sd"] is None:
        return None
    t = rows[-1]
    past = [abs(x["z"]) for x in rows[-253:-1] if x["z"] is not None and not x["earn"]]
    return {"z": t["z"], "sigma_pct": t["sd"] * 100, "outside": abs(t["z"]) >= Z_OUT, "earnings_day": t["earn"],
            "n_year": sum(1 for x in past if x >= abs(t["z"]))}


def period_returns(bars, bench):
    a, b = [x["adj"] for x in bars], {x["day"]: x["adj"] for x in bench}
    bd = [x["day"] for x in bars]
    out = []
    for label, n in PERIODS:
        if len(a) <= n:
            continue
        s = (a[-1] / a[-1 - n] - 1) * 100
        m = (b[bd[-1]] / b[bd[-1 - n]] - 1) * 100 if bd[-1] in b and bd[-1 - n] in b else None
        out.append({"label": label, "stock": s, "spy": m})
    return out


def year_range(bars):
    y = bars[-252:]
    if len(y) < 200:
        return None
    hi, lo = max(y, key=lambda x: x["high"]), min(y, key=lambda x: x["low"])
    c, span = y[-1]["close"], hi["high"] - lo["low"]
    return {"high": hi["high"], "high_day": hi["day"], "low": lo["low"], "low_day": lo["day"], "close": c,
            "pos_pct": (c - lo["low"]) / span * 100 if span else 50.0, "pct_from_high": (c / hi["high"] - 1) * 100}


def earnings(bars, evs, today, n=8):
    days = [x["day"] for x in bars]
    idx = {d: i for i, d in enumerate(days)}
    moves = []
    for ann, rd in reaction_days(days, [e for e in evs if e["day"] <= today]):
        i = idx[rd]
        moves.append({"day": rd, "ann": ann, "ret": (bars[i]["adj"] / bars[i - 1]["adj"] - 1) * 100})
    moves = moves[-n:]
    rets = sorted(abs((bars[i]["adj"] / bars[i - 1]["adj"] - 1) * 100) for i in range(max(1, len(bars) - 252), len(bars)))
    fut = [e["day"] for e in evs if e["day"] > today]
    out = {"next": fut[0] if fut else None, "moves": moves}
    if moves and rets:
        absm = sorted(abs(m["ret"]) for m in moves)
        out.update(median_abs=absm[len(absm) // 2], normal_abs=rets[len(rets) // 2])
    return out


def _closes(snap, sym):
    return [x["close"] for x in snap["bars"].get(sym) or []]


def technical(bars, snap, sym):
    """차트 지표 (2층) — NVDA 리포트 indicators 와 같은 정의. 하루 대비는 S&P 500 · 업종 ETF."""
    c = [x["close"] for x in bars]
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
    bc = [x["close"] for x in snap["bars"].get(U.BENCH) or [] if x["day"] <= t["day"]]   # S&P 500 도 같은 날까지 — 평균선 대비 비교 막대 (2026-10-27 P37)
    out["bench_ma_rel"] = {n: (bc[-1] / (sum(bc[-n:]) / n) - 1) * 100 for n in (20, 60, 120, 200) if len(bc) >= n}
    out["path"], out["bench_path"] = day_path(bars), day_path(snap["bars"].get(U.BENCH), t["day"])   # 오늘 하루 흐름 (P41)
    r1 = (t["close"] / p["close"] - 1) * 100
    for key, ref in (("vs_spy", U.BENCH), ("vs_sector", U.sector_etf(sym)[0])):
        rb = {x["day"]: x["close"] for x in snap["bars"].get(ref) or []}
        out[key] = r1 - (rb[t["day"]] / rb[p["day"]] - 1) * 100 if t["day"] in rb and p["day"] in rb else None
    try:
        import tech_signals   # experiments/ — 기술 지표 12 · 이동평균 · 피벗 (2026-10-30 사용자)
        out["signals"] = tech_signals.compute(bars)
    except Exception as e:   # noqa: BLE001
        print(f"[radar] {sym} 기술 지표 계산 실패 : {e}")
        out["signals"] = None
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


def market_regime(snap):
    """시장 분위기 — NVDA 리포트 judge.market_regime 과 같은 규칙 (전환 기록 없이 오늘 상태만)."""
    c = _closes(snap, NC.REGIME_BENCHMARK)
    if len(c) < NC.REGIME_MA_DAYS:
        return None
    vix = _closes(snap, "^VIX")
    vix = vix[-1] if vix else None
    ph = (c[-1] / max(c[-NC.REGIME_HIGH_DAYS:]) - 1) * 100
    ma = sum(c[-NC.REGIME_MA_DAYS:]) / NC.REGIME_MA_DAYS
    streak = 0
    for i in range(len(c) - 1, 0, -1):
        d = c[i] - c[i - 1]
        if d == 0 or (streak and (d > 0) != (streak > 0)):
            break
        streak += 1 if d > 0 else -1
    regime = ("불안 국면" if vix is not None and vix >= NC.REGIME_VIX_HIGH else
              "조정장" if ph <= NC.REGIME_CORRECTION_PCT or c[-1] < ma else "단기 조정" if ph <= NC.REGIME_PULLBACK_PCT else "상승 추세")
    return {"regime": regime, "prev_regime": None, "changed": False, "pct_from_high": ph, "above_ma200": c[-1] >= ma, "ma200": ma,
            "pct_vs_ma200": (c[-1] / ma - 1) * 100, "vix": vix, "streak": streak}


def market_shock(snap):
    """시장 충격 — VIX 종가 35 이상 시작 · 25 아래 끝 (normal_range_line.market_shock 과 같다). 흔들림 회복 묶음은 NVDA 리포트에만."""
    inside, start, days_in = False, None, 0
    for x in snap["bars"].get("^VIX") or []:
        if not inside and x["close"] >= 35:
            inside, start, days_in = True, x["day"], 0
        elif inside and x["close"] < 25:
            inside, start = False, None
        if inside:
            days_in += 1
    v = _closes(snap, "^VIX")
    return {"active": inside, "start": start, "vix": v[-1] if v else None, "days_in": days_in, "early_complete": False}


def _rel(snap, etf, n):
    a, b = _closes(snap, etf), _closes(snap, U.BENCH)
    if len(a) <= n or len(b) <= n:
        return None
    return ((a[-1] / a[-1 - n]) - (b[-1] / b[-1 - n])) * 100


def sector_flow(snap, sym):
    """'○○ 업종으로 돈이 올까?' — NVDA 리포트 sector_flow 와 같은 규칙(20거래일 · ±2%p), 기준 ETF 만 종목의 업종으로. ETF 주식 수 확인은 없다."""
    etf, name = U.sector_etf(sym)
    n, pp = NC.SECTOR_FLOW_DAYS, NC.SECTOR_FLOW_PP
    rel = _rel(snap, etf, n)
    if rel is None:
        return None
    sectors = sorted(({"etf": e, "name": nm, "rel": r} for e, nm in NC.SECTOR_ETFS.items() if (r := _rel(snap, e, n)) is not None), key=lambda x: -x["rel"])
    pool = sectors + ([{"etf": "SMH", "name": "반도체", "rel": rel}] if etf == "SMH" else [])
    rank = 1 + sum(1 for x in pool if x["rel"] > rel)
    return {"etf": etf, "name": name, "state": "모이는 중" if rel >= pp else "빠져나가는 중" if rel <= -pp else "뚜렷하지 않음",
            "rel_pp": rel, "days": n, "sectors": sectors, "rank": rank, "n_pool": len(pool)}


def bollinger(bars):
    """한 달간 변화 범위 — NVDA 리포트 judge.bollinger 와 같은 정의(20일 · 2σ). 과거 통계는 없다(이 종목은 검증하지 않았다)."""
    c, w = [x["close"] for x in bars], NC.BOLL_WINDOW

    def at(i):
        win = c[i - w + 1:i + 1]
        m = sum(win) / w
        sd = (sum((x - m) ** 2 for x in win) / (w - 1)) ** 0.5
        lo, hi = m - NC.BOLL_SIGMA * sd, m + NC.BOLL_SIGMA * sd
        return ((c[i] - lo) / (hi - lo) if hi > lo else 0.5), lo, hi, m
    if len(c) < w + 1:
        return None
    pb, lo, hi, m = at(len(c) - 1)
    state = "하단 도달" if pb <= 0 else "상단 도달" if pb >= 1 else "밴드 안"
    days = 0
    if state != "밴드 안":
        for i in range(len(c) - 1, w - 1, -1):
            q = at(i)[0]
            if (q <= 0) if state == "하단 도달" else (q >= 1):
                days += 1
            else:
                break
    return {"pctb": pb, "lower": lo, "upper": hi, "ma20": m, "close": c[-1], "state": state, "days": days, "stats": None}


def overheat(bars, tech):
    c = [x["close"] for x in bars]
    if len(c) < 21:
        return None
    ret20 = (c[-1] / c[-21] - 1) * 100
    d200 = (c[-1] / tech["ma200"] - 1) * 100 if tech.get("ma200") else None
    rsi = tech.get("rsi14")
    active = [k for k, ok in (("rsi80", rsi is not None and rsi >= NC.OVERHEAT_RSI), ("ma200_40", d200 is not None and d200 >= NC.OVERHEAT_MA200_PCT),
                              ("ret20_25", ret20 >= NC.OVERHEAT_RET20_PCT)) if ok]
    return {"active": active, "values": {"rsi80": rsi, "ma200_40": d200, "ret20_25": ret20}, "stats": None}


def drawdown(bars, yr, snap, sym):
    """고점 하락 후 가격 회복 — 이 종목 1999년부터(상장이 늦으면 상장부터) · S&P 500 같은 기간 통계 + 지금 위치."""
    h = (snap.get("history") or {}).get("stats") or {}
    if sym not in h or U.BENCH not in h or not yr:
        return None
    return {"stock": h[sym], "spy": h[U.BENCH], "pct_from_high": yr["pct_from_high"], "days_since_high": sum(1 for x in bars if x["day"] > yr["high_day"])}


def stock(sym, snap):
    bars = snap["bars"].get(sym) or []
    if len(bars) < 2:
        return None
    evs = snap["earnings"].get(sym) or []
    days = [x["day"] for x in bars]
    earn_days = {rd for _, rd in reaction_days(days, evs)}
    t, p = bars[-1], bars[-2]
    vol20 = [x["volume"] for x in bars[-21:-1] if x["volume"]]
    return {"sym": sym, "name": U.name(sym), "day": t["day"], "close": t["close"], "ret_1d": (t["adj"] / p["adj"] - 1) * 100,
            "vol_ratio": t["volume"] / (sum(vol20) / len(vol20)) if vol20 and t["volume"] else None,
            "cap": snap["caps"].get(sym), "normal_range": normal_range(bars, earn_days),
            "periods": period_returns(bars, snap["bars"].get(U.BENCH) or []), "year_range": year_range(bars),
            "earnings": earnings(bars, evs, t["day"]), "_bars": bars}


def update_ranks(stocks, day, path=STATE):
    """순위 + 교체 (10-10): 시총 순위를 날마다 적고, 지금 TOP 10 종목이 11위 밖으로 SWAP_DAYS 거래일 연속 밀리면
    그 기간 가장 높았던 후보(평균 순위)와 바꾼다. 처음에는 그날 시총 상위 10개.
    순위 · TOP 10 은 U.TOP_EXCLUDE(외국 ADR · S&P 500 밖)를 빼고 매긴다 — 그 종목은 순위가 없다 (2026-10-20, 48개 확대)."""
    ranked = sorted((s for s in stocks if s.get("cap") and s["sym"] not in U.TOP_EXCLUDE), key=lambda s: -s["cap"])
    today = {s["sym"]: i + 1 for i, s in enumerate(ranked)}
    try:
        with open(path, encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    hist = [h for h in st.get("history", []) if h["day"] != day] + [{"day": day, "rank": today}]
    hist = hist[-60:]
    top = st.get("top") or [s["sym"] for s in ranked[:U.TOP_N]]
    recent = hist[-U.SWAP_DAYS:]
    if len(recent) == U.SWAP_DAYS:
        out = [s for s in top if all(h["rank"].get(s, 99) > U.TOP_N for h in recent)]
        for s in out:
            pool = [c for c in today if c not in top]
            if not pool:
                break
            best = min(pool, key=lambda c: sum(h["rank"].get(c, 99) for h in recent))
            top[top.index(s)] = best
            print(f"[rank] 교체 : {s} → {best}")
    st = {"day": day, "top": top, "history": hist}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)
    for s in stocks:
        s["rank"] = today.get(s["sym"])
        s["in_top"] = s["sym"] in top
    return sorted(stocks, key=lambda s: (not s["in_top"], s["rank"] or 99))


def run(snap):
    stocks = [x for x in (stock(c[0], snap) for c in U.CANDIDATES) if x]
    mr, ms = market_regime(snap), market_shock(snap)
    for s in stocks:
        bars = s.pop("_bars")
        s["tech"] = technical(bars, snap, s["sym"])
        s["market_regime"], s["market_shock"] = mr, ms
        s["sector_flow"] = sector_flow(snap, s["sym"])
        s["bollinger"] = bollinger(bars)
        s["overheat"] = overheat(bars, s["tech"])
        s["drawdown"] = drawdown(bars, s["year_range"], snap, s["sym"])
    day = max(s["day"] for s in stocks)
    return {"day": day, "fetched_at": snap["fetched_at"], "stocks": update_ranks(stocks, day)}


if __name__ == "__main__":
    import collect
    a = run(collect.load())
    for s in a["stocks"]:
        nr = s["normal_range"] or {}
        e = s["earnings"]
        print(f"{s['rank'] or '-':>2} {'*' if s['in_top'] else ' '} {s['sym']:6} ${s['close']:>9,.2f} {s['ret_1d']:+6.2f}% z={nr.get('z', 0):+.1f} σ={nr.get('sigma_pct', 0):.1f}% "
              f"next={e['next']} med={e.get('median_abs', 0):.1f} n={len(e['moves'])}")
