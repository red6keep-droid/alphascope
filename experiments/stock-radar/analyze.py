"""종목별 숫자 — 순위 · 오늘 · 평소 범위 · 기간별 수익률 · 1년 범위 · 실적. 모두 파이썬 값 (AI 없음).

평소 범위는 NVDA 리포트와 같은 자(normal_range_line): EWMA λ 0.94 로그 수익률, 실적 반응일 제외, 전날까지의 값으로 오늘을 잰다, 2배 이상 = 밖.
수익률 · 평소 범위는 배당 반영 종가(adj), 화면 가격 · 1년 고저는 실제 거래 가격(close · high · low).
"""

import datetime
import json
import math
import os

import universe as U

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
            "earnings": earnings(bars, evs, t["day"])}


def update_ranks(stocks, day, path=STATE):
    """순위 + 교체 (10-10): 시총 순위를 날마다 적고, 지금 TOP 10 종목이 11위 밖으로 SWAP_DAYS 거래일 연속 밀리면
    그 기간 가장 높았던 후보(평균 순위)와 바꾼다. 처음에는 그날 시총 상위 10개."""
    ranked = sorted((s for s in stocks if s.get("cap")), key=lambda s: -s["cap"])
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
    day = max(s["day"] for s in stocks)
    return {"day": day, "fetched_at": snap["fetched_at"], "stocks": update_ranks(stocks, day)}


if __name__ == "__main__":
    import collect
    a = run(collect.load())
    for s in a["stocks"]:
        nr = s["normal_range"] or {}
        e = s["earnings"]
        print(f"{s['rank']:>2} {'*' if s['in_top'] else ' '} {s['sym']:6} ${s['close']:>9,.2f} {s['ret_1d']:+6.2f}% z={nr.get('z', 0):+.1f} σ={nr.get('sigma_pct', 0):.1f}% "
              f"next={e['next']} med={e.get('median_abs', 0):.1f} n={len(e['moves'])}")
