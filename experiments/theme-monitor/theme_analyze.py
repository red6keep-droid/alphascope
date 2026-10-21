"""테마 신호 — 전부 파이썬 (doc/기획/테마-모니터-기획.md 3절). 입력은 레이더 snapshot(일봉) · extra(공시 · 공매도) · FRED.

    python experiments/theme-monitor/theme_analyze.py     # 로컬 data 로 계산해 output/themes_analysis.json
"""

import datetime
import json
import math
import os
import re
import statistics
import sys

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "stock-radar"))

import price_source  # noqa: E402
import themes as T  # noqa: E402
import universe as U  # noqa: E402

OUT = os.path.join(_HERE, "output", "themes_analysis.json")


# ── 바스켓 (동일가중) ─────────────────────────────────────────────────────

def _closes(snap, sym):
    return [(b["day"], b.get("adj") or b["close"]) for b in snap["bars"].get(sym) or [] if b.get("close")]


def basket_index(snap, syms, days=300):
    """동일가중 지수 — 공통 거래일에서 종목 일수익률 평균을 누적. [(day, value)], 시작 100. 종목이 하나도 없으면 []."""
    series = {s: dict(_closes(snap, s)) for s in syms}
    series = {s: v for s, v in series.items() if len(v) > 30}
    if not series:
        return [], []
    days_common = sorted(set.intersection(*(set(v) for v in series.values())))[-days:]
    idx, val = [], 100.0
    for i, d in enumerate(days_common):
        if i:
            p = days_common[i - 1]
            rets = [series[s][d] / series[s][p] - 1 for s in series if series[s].get(p)]
            val *= 1 + sum(rets) / len(rets)
        idx.append((d, val))
    return idx, sorted(series)


def rel_return(idx, bench, n):
    """n거래일 수익률 차 (%p) — 바스켓 − 기준."""
    if len(idx) <= n or len(bench) <= n:
        return None
    bd = dict(bench)
    d1, d0 = idx[-1][0], idx[-1 - n][0]
    if d1 not in bd or d0 not in bd:
        return None
    return ((idx[-1][1] / idx[-1 - n][1]) - (bd[d1] / bd[d0])) * 100


def period_return(idx, n):
    return (idx[-1][1] / idx[-1 - n][1] - 1) * 100 if len(idx) > n else None


def breadth(snap, syms):
    """20일선 위 비율 · 오늘 오른 비율."""
    above = up = n = 0
    for s in syms:
        c = [v for _, v in _closes(snap, s)]
        if len(c) < 21:
            continue
        n += 1
        above += c[-1] > sum(c[-20:]) / 20
        up += c[-1] > c[-2]
    return {"n": n, "above_ma20": above, "up_today": up} if n else None


def vol_ratio(snap, syms):
    xs = []
    for s in syms:
        v = [b["volume"] for b in snap["bars"].get(s) or [] if b.get("volume")]
        if len(v) >= 21 and sum(v[-21:-1]):
            xs.append(v[-1] / (sum(v[-21:-1]) / 20))
    return statistics.median(xs) if xs else None


def normal_z(idx):
    """오늘 바스켓 수익률 / 지난 252일 하루 수익률 표준편차."""
    r = [idx[i][1] / idx[i - 1][1] - 1 for i in range(1, len(idx))]
    if len(r) < 60:
        return None
    hist = r[-(T.NORMAL_WINDOW + 1):-1]
    sd = statistics.pstdev(hist)
    return {"z": r[-1] / sd if sd else None, "today_pct": r[-1] * 100, "sigma_pct": sd * 100, "n": len(hist)}


def rsi(idx, n=14):
    r = [idx[i][1] - idx[i - 1][1] for i in range(1, len(idx))][-n:]
    if len(r) < n:
        return None
    g = sum(x for x in r if x > 0) / n
    l = -sum(x for x in r if x < 0) / n
    return 100.0 if not l else 100 - 100 / (1 + g / l)


def flow_state(rel):
    return "유입" if rel is not None and rel >= T.FLOW_PP else "유출" if rel is not None and rel <= -T.FLOW_PP else "중립"


# ── A. AI 투자 ───────────────────────────────────────────────────────────

def analyze_ai(t, snap):
    bench, _ = basket_index(snap, [T.BENCH])
    out = {"baskets": []}
    for name, syms in t["baskets"]:
        idx, used = basket_index(snap, syms)
        if not idx:
            continue
        rel = rel_return(idx, bench, T.FLOW_DAYS)
        out["baskets"].append({
            "name": name, "syms": used, "rel_20d": rel, "state": flow_state(rel), "ret_20d": period_return(idx, T.FLOW_DAYS),
            "ret_5d": period_return(idx, 5), "ret_1d": period_return(idx, 1), "breadth": breadth(snap, used), "vol_ratio": vol_ratio(snap, used),
            "normal": normal_z(idx), "rsi": rsi(idx),
            "members": sorted(({"sym": s, "name": U.name(s) if s in U.BY_SYM else s, "ret_20d": _sym_ret(snap, s, T.FLOW_DAYS), "ret_1d": _sym_ret(snap, s, 1)} for s in used),
                              key=lambda x: -(x["ret_20d"] or -99)),
        })
    allsyms = [s for _, ss in t["baskets"] for s in ss]
    whole, used = basket_index(snap, allsyms)
    out["whole"] = {"rel_20d": rel_return(whole, bench, T.FLOW_DAYS), "ret_20d": period_return(whole, T.FLOW_DAYS), "normal": normal_z(whole), "rsi": rsi(whole),
                    "breadth": breadth(snap, used), "n": len(used)}
    out["bench_ret_20d"] = period_return(bench, T.FLOW_DAYS)
    ins = [b for b in out["baskets"] if b["state"] == "유입"]
    outs = [b for b in out["baskets"] if b["state"] == "유출"]
    st = t["states"]
    if len(ins) == len(out["baskets"]) and ins:
        out["state"] = st["all"]
    elif len(ins) == 2:
        out["state"] = st["two"]
    elif len(ins) == 1:
        out["state"] = st["one"].format(name=ins[0]["name"])
    elif outs and not ins:
        out["state"] = st["out"]
    else:
        out["state"] = st["none"]
    out["theme_kind"] = "positive" if ins and not outs else "negative" if outs and not ins else "neutral"
    return out


def _sym_ret(snap, sym, n):
    c = [v for _, v in _closes(snap, sym)]
    return (c[-1] / c[-1 - n] - 1) * 100 if len(c) > n else None


# ── B. 연준 인하 기대 ────────────────────────────────────────────────────

def _fred(sid, days=400):
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    try:
        return sorted(price_source._fred_observations(sid, start=start))   # [(day, value)] 오래된 날 앞
    except Exception as e:  # noqa: BLE001
        print(f"[theme] FRED {sid} 실패: {e}")
        return []


def _cpi_dates(release_id, days=120):
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        return []
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    try:
        r = requests.get("https://api.stlouisfed.org/fred/release/dates", params={"release_id": release_id, "api_key": key, "file_type": "json",
                         "realtime_start": start, "include_release_dates_with_no_data": "true"}, timeout=30)
        if r.status_code != 200:
            return []
        return sorted({x["date"] for x in r.json().get("release_dates", []) if x.get("date", "") <= datetime.date.today().isoformat()})
    except Exception as e:  # noqa: BLE001
        print(f"[theme] FRED 발표일 실패: {type(e).__name__}")
        return []


def _at(series, day):
    """day 또는 그 직전 관측."""
    prev = None
    for d, v in series:
        if d > day:
            break
        prev = (d, v)
    return prev


def analyze_fed(t, snap):
    f = t["fred"]
    policy, y2, y10, curve = (_fred(f[k]) for k in ("policy", "y2", "y10", "curve"))
    out = {"series": {}}
    if not policy or not y2:
        out["state"] = "자료 없음"
        out["theme_kind"] = "neutral"
        return out
    # 인하 기대 = 기준금리 − 2년물 (bp). 양수 = 시장이 인하를 본다
    pol = dict(policy)
    gap = [(d, (_at(policy, d)[1] - v) * 100) for d, v in y2 if _at(policy, d)]
    now = gap[-1]
    ago = gap[-1 - T.FLOW_DAYS] if len(gap) > T.FLOW_DAYS else None
    chg = now[1] - ago[1] if ago else None
    st = t["states"]
    state = st["up"] if chg is not None and chg >= t["change_bp"] else st["down"] if chg is not None and chg <= -t["change_bp"] else st["flat"]
    # 차이가 음수면 2년물이 기준금리보다 높다 = 시장은 인하가 아니라 인상(또는 동결 장기화)을 본다 (2026-10 실제: 기준 3.88 · 2년물 4.77)
    direction = "인하" if now[1] > 10 else "인상" if now[1] < -10 else "동결"
    out.update({
        "direction": direction,
        "day": now[0], "gap_bp": now[1], "gap_bp_20d_ago": ago[1] if ago else None, "gap_change_bp": chg,
        "policy": _at(policy, now[0])[1], "y2": y2[-1][1], "y10": y10[-1][1] if y10 else None, "curve": curve[-1][1] if curve else None,
        "y10_change_20d": (y10[-1][1] - y10[-1 - T.FLOW_DAYS][1]) * 100 if len(y10) > T.FLOW_DAYS else None,
        "curve_change_20d": (curve[-1][1] - curve[-1 - T.FLOW_DAYS][1]) * 100 if len(curve) > T.FLOW_DAYS else None,
        "state": state, "theme_kind": "positive" if state == st["up"] else "negative" if state == st["down"] else "neutral",
        "gap_series": gap[-60:],
    })
    # CPI 발표일의 2년물 반응 (발표일 종가 − 전일 종가, bp)
    rows = []
    y2d = dict(y2)
    days = [d for d, _ in y2]
    for cd in _cpi_dates(t["cpi_release_id"]):
        if cd not in y2d:
            continue
        i = days.index(cd)
        if i:
            rows.append({"day": cd, "y2_change_bp": (y2d[cd] - y2d[days[i - 1]]) * 100})
    out["cpi_days"] = rows[-6:]
    # 금리 민감 자산 20일 — 시세는 snapshot 에 있는 것만 (TLT · IWM · QQQ 는 2단계에서 수집)
    sens = []
    for name, sym in t["sensitive"]:
        r = _sym_ret(snap, sym, T.FLOW_DAYS)
        if r is not None:
            sens.append({"name": name, "sym": sym, "ret_20d": r})
    out["sensitive"] = sens
    return out


# ── D. 임원 · 기관 매매 ─────────────────────────────────────────────────

_USD = re.compile(r"약 \$([\d.,]+)M")
_BUY = re.compile(r"매수 ([\d,]+)주")
_SELL = re.compile(r"매도 ([\d,]+)주")


def analyze_insider(t, extra):
    cut = (datetime.date.today() - datetime.timedelta(days=t["days"])).isoformat()
    per = {}
    for row in (extra.get("edgar") or {}).values():
        if row.get("form") != "4" or row.get("filed", "") < cut:
            continue
        title = row.get("title") or ""
        usd = float(_USD.search(title).group(1).replace(",", "")) if _USD.search(title) else 0.0
        plan = "사전 매도 계획" in title
        # 빼는 것 (2026-10-21 로컬 자료로 확인): ① "10% 보유자" 공시 — 보유자(예: 버크셔)의 CIK 아래로도 오므로 발행사가 다른 회사일 수 있다 (2단계: XML 에서 발행사 확인)
        # ② $0.1M 미만 매수 — 주식 지급 · 소액 (TSM 임원 40~60주 30건)
        if "10% 보유자" in title:
            continue
        if _BUY.search(title) and not _SELL.search(title) and usd < 0.1:
            continue
        p = per.setdefault(row["sym"], {"sym": row["sym"], "name": U.name(row["sym"]) if row["sym"] in U.BY_SYM else row["sym"],
                                        "buy_n": 0, "buy_usd": 0.0, "sell_n": 0, "sell_usd": 0.0, "plan_n": 0, "plan_usd": 0.0, "last": ""})
        if _BUY.search(title) and not _SELL.search(title):
            p["buy_n"] += 1
            p["buy_usd"] += usd
        elif _SELL.search(title):
            if plan:
                p["plan_n"] += 1
                p["plan_usd"] += usd
            else:
                p["sell_n"] += 1
                p["sell_usd"] += usd
        p["last"] = max(p["last"], row["filed"])
    buy_n = sum(p["buy_n"] for p in per.values())
    sell_n = sum(p["sell_n"] for p in per.values())
    plan_n = sum(p["plan_n"] for p in per.values())
    st = t["states"]
    if buy_n >= 2 and buy_n >= 2 * sell_n:
        state, kind = st["buy"], "positive"
    elif sell_n >= 3 and sell_n >= 2 * max(buy_n, 1):
        state, kind = st["sell"], "negative"
    else:
        state, kind = st["flat"], "neutral"
    buyers = sorted((p for p in per.values() if p["buy_n"]), key=lambda p: -p["buy_usd"])
    sellers = sorted((p for p in per.values() if p["sell_n"]), key=lambda p: -p["sell_usd"])
    # 공매도 비율 변화 — 레이더 extra.stocks[sym].short (pct · prior_pct)
    rising = falling = n = 0
    for sym, v in (extra.get("stocks") or {}).items():
        s = (v or {}).get("short") or {}
        if s.get("pct") is not None and s.get("prior_pct") is not None:
            n += 1
            rising += s["pct"] > s["prior_pct"]
            falling += s["pct"] < s["prior_pct"]
    return {"days": t["days"], "buy_n": buy_n, "sell_n": sell_n, "plan_n": plan_n, "buy_usd": sum(p["buy_usd"] for p in buyers),
            "sell_usd": sum(p["sell_usd"] for p in sellers), "plan_usd": sum(p["plan_usd"] for p in per.values()),
            "buyers": buyers[:8], "sellers": sellers[:8], "n_companies": len(per), "universe": len(U.CANDIDATES) - len(U.REPORT_TYPE),
            "short": {"n": n, "rising": rising, "falling": falling} if n else None,
            "state": state, "theme_kind": kind, "extra_day": extra.get("day")}


# ── 전체 ────────────────────────────────────────────────────────────────

def run(snap, extra):
    out = {"day": max(b[-1]["day"] for b in snap["bars"].values() if b), "themes": {}}
    for t in T.THEMES:
        if t["key"] == "ai":
            out["themes"]["ai"] = analyze_ai(t, snap)
        elif t["key"] == "fed":
            out["themes"]["fed"] = analyze_fed(t, snap)
        elif t["key"] == "insider":
            out["themes"]["insider"] = analyze_insider(t, extra or {})
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_HERE, "..", "..", ".env"))
    import collect
    import collect_extra
    a = run(collect.load(), collect_extra.load() or {})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(a, f, ensure_ascii=False, indent=1, default=str)
    for k, v in a["themes"].items():
        print(k, "→", v.get("state"))
    print(f"[theme] → {OUT}")
