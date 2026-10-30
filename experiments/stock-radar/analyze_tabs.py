"""상세 페이지 탭 재료 — 실적과 기대 카드 넷 · 캘린더 카드 셋 · 애널리스트. 모두 파이썬 값 (AI 없음).

판정 규칙과 기준값은 NVDA 리포트 expect.py · cal_cards.py 와 같다. 바뀐 것은 비교 묶음뿐이다:
  - NVDA 리포트 `기술주 15개` → 여기서는 `시총 상위 20개`(순위 대상 가운데 시총 상위 20개의 중앙값 — peer_group. 후보가 20개였을 때는 후보 전체)
  - `함께 보는 회사 실적` = 후보 20개 가운데 같은 업종 회사 (NVDA 는 고객 · 공급 · 경쟁사 목록)
  - 소송 카드는 없다 — 사건을 추적하는 종목이 NVDA 뿐이다
시장 일정(금리 결정 · 물가 · 고용 · 옵션 만기 …)은 시장 전체 일정이라 NVDA 리포트 DB 의 calendar 를 같이 읽는다.
"""

import datetime
import math
import os
import sqlite3
import statistics
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "nvda-report"))
import cal_cards as CC  # noqa: E402
import expect as EX  # noqa: E402

import universe as U  # noqa: E402

NVDA_DB = os.path.join(BASE, "..", "nvda-report", "data", "nvda.db")
PEER_LABEL = "시총 상위 20개"


def _d(s):
    return datetime.date.fromisoformat(s)


def _med(xs, need=EX.MIN_PEERS):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if len(xs) >= need else None


def peer_group(snap):
    """비교 묶음 `시총 상위 20개` 의 종목 — 순위 대상(TOP_EXCLUDE 밖) 가운데 시총 상위 PEER_GROUP_N 개.
    후보가 20개였을 때는 후보 전체였다. 48개로 늘린 뒤에도 묶음 이름과 뜻이 같게 (2026-10-20)."""
    caps = snap.get("caps") or {}
    pool = [c[0] for c in U.CANDIDATES if c[0] not in U.TOP_EXCLUDE and caps.get(c[0])]
    return set(sorted(pool, key=lambda s: -caps[s])[:U.PEER_GROUP_N])


# ---------------------------------------------------------------- 실적과 기대 (EX.card_* 와 같은 판정)

def card_revenue(sym, extra, group):
    series = ((extra.get("revenue") or {}).get("series")) or {}
    me = [r for r in series.get(sym) or [] if r.get("yoy") is not None][-8:]
    if not me:
        return None
    by_cq = {}
    for rows in (v for k, v in series.items() if k in group):   # 비교 = 시총 상위 20개만
        for r in rows:
            if r.get("yoy") is not None:
                by_cq.setdefault(r["cq"], []).append(r["yoy"])
    bars = [{"cq": r["cq"], "end": r["end"], "stock": r["yoy"], "peers": _med(by_cq.get(r["cq"], []))} for r in me]
    last = me[-1]
    prev = [r for r in series[sym] if r["end"] < last["end"]]
    yoy = last["yoy"]
    return {"state": "늘고 있음" if yoy >= EX.REV_PCT else "줄고 있음" if yoy <= -EX.REV_PCT else "비슷함", "yoy": yoy, "rev": last["rev"], "end": last["end"],
            "qoq": (last["rev"] / prev[-1]["rev"] - 1) * 100 if prev else None, "bars": bars, "peers_last": bars[-1]["peers"]}


CAPEX_PCT = 10   # 최근 4분기 설비 투자 합이 그 전 4분기보다 이만큼 넘게 다르면 늘리는 중 · 줄이는 중 (분기 값은 들쭉날쭉해 4분기 합으로)


def card_capex(sym, extra):
    """돈을 어디에 쓰나 (2026-10-30 사용자) — collect_capex 분기 표 → 카드 재료. 판단 없이 사실만: 최근 분기 · 최근 4분기 합 · 1년 전 대비 · 영업으로 번 돈 대비."""
    import collect_capex as CX
    rows = (extra.get("capex") or {}).get(sym) or []
    rows = [r for r in rows if r.get("capex") is not None or r.get("ocf") is not None]
    if not rows:
        return None
    last = rows[-1]
    sm = CX.summary(rows)
    bars = [{"cq": r["cq"], "end": r["end"], "capex": r.get("capex"), "ocf": r.get("ocf")} for r in rows[-8:]]
    c4, p4 = sm.get("capex"), sm.get("capex_prev")
    chg4 = (c4 / p4 - 1) * 100 if c4 is not None and p4 else None
    if last.get("capex") is None and not any(r.get("capex") is not None for r in rows[-4:]):
        state = "설비 투자 줄 없음"   # 은행 · 보험 — 현금흐름표에 설비 투자 항목이 따로 없다
    else:
        state = "늘리는 중" if chg4 is not None and chg4 >= CAPEX_PCT else "줄이는 중" if chg4 is not None and chg4 <= -CAPEX_PCT else "비슷함" if chg4 is not None else "4분기 안 됨"
    return {"state": state, "end": last["end"], "form": last.get("form"), "src": last.get("src"), "capex": last.get("capex"), "capex_yoy": last.get("capex_yoy"),
            "ocf": last.get("ocf"), "rnd": last.get("rnd"), "cash": last.get("cash"), "debt": last.get("debt"), "bars": bars, "chg4": chg4,
            "sum4": {k: sm.get(k) for k in CX.TAGS}, "n4": min(4, len(rows))}


def card_eps(sym, extra, group):
    allx = {s: (v or {}).get("eps") or {} for s, v in (extra.get("stocks") or {}).items()}
    me = allx.get(sym) or {}
    allx = {s: v for s, v in allx.items() if s in group}   # 비교 = 시총 상위 20개만
    if "current" not in me:
        return None

    def chg(e, k):
        return (e["current"] / e[k] - 1) * 100 if e.get(k) and e.get("current") else None
    wins = (("7일", "7daysAgo"), ("30일", "30daysAgo"), ("60일", "60daysAgo"), ("90일", "90daysAgo"))
    bars = [{"label": lb, "stock": chg(me, k), "peers": _med([chg(e, k) for e in allx.values()])} for lb, k in wins]
    c30 = bars[1]["stock"]
    if c30 is None:
        return None
    state = "더 좋게 봄" if c30 >= EX.EPS_PCT else "더 나쁘게 봄" if c30 <= -EX.EPS_PCT else "그대로"   # 전망 말로 (2026-10-27 사용자 B안)
    return {"state": state, "c30": c30, "bars": bars, "current": me["current"], "up30": me.get("up30"), "down30": me.get("down30")}


def card_move(s, snap, extra):
    x = (extra.get("stocks") or {}).get(s["sym"]) or {}
    nr = s.get("normal_range") or {}
    if not x.get("iv") or not nr.get("sigma_pct"):
        return None
    exp = x["iv"] / math.sqrt(252) * 100
    ratio = exp / nr["sigma_pct"]
    spy_closes = [b["close"] for b in snap["bars"].get(U.BENCH) or []][-260:]
    spy = {"exp": extra["spy_iv"] / math.sqrt(252) * 100 if extra.get("spy_iv") else None, "sigma": EX._ewma_sigma(spy_closes)}
    e = s.get("earnings") or {}
    nxt = e.get("next")
    days_to = (_d(nxt) - _d(s["day"])).days if nxt else None
    earn_day = EX._earnings_day_move(x["straddle"], nr["sigma_pct"], s["day"], nxt) if x.get("straddle") and nxt else None
    earn = ({"exp": earn_day, "past": e["median_abs"], "n": len(e.get("moves") or [])}
            if days_to is not None and days_to <= 30 and earn_day and e.get("median_abs") else None)
    return {"state": "평소보다 큼" if ratio >= EX.MOVE_HI else "평소보다 작음" if ratio <= EX.MOVE_LO else "평소 수준",
            "exp": exp, "sigma": nr["sigma_pct"], "ratio": ratio, "spy": spy, "earn": earn, "next_earnings": nxt, "days_to": days_to,
            "iv": x["iv"], "earn_day": earn_day, "past": e.get("median_abs")}


def card_short(sym, extra, group):
    allx = {s: (v or {}).get("short") or {} for s, v in (extra.get("stocks") or {}).items()}
    me = allx.get(sym) or {}
    allx = {s: v for s, v in allx.items() if s in group}   # 비교 = 시총 상위 20개만
    if not me.get("shares") or not me.get("prior") or me.get("pct") is None:
        return None
    chg = (me["shares"] / me["prior"] - 1) * 100
    return {"state": "늘어나는 중" if chg >= EX.SHORT_PCT else "줄어드는 중" if chg <= -EX.SHORT_PCT else "큰 변화 없음",
            "chg": chg, "pct": me["pct"], "prior_pct": me.get("prior_pct"), "asof": me.get("asof"), "prior_asof": me.get("prior_asof"),
            "peers_pct": _med([e.get("pct") for e in allx.values()]), "peers_prior_pct": _med([e.get("prior_pct") for e in allx.values()])}


def options_status(sym, extra):
    """옵션 상태판 칸 — NVDA judge 의 options 묶음과 같은 키 · 형식 (감마 근사 두 칸은 뺀다). 변동성 순위는 60거래일 쌓인 뒤."""
    x = (extra.get("stocks") or {}).get(sym) or {}
    o = x.get("options") or {}
    cfg = EX.config
    rank = x.get("iv_rank")

    def cell(key, value, flag=False, fmt="num2"):
        return {"key": key, "value": value, "flag": flag, "fmt": fmt}
    return {"iv_rank_n": x.get("iv_rank_n") or 0, "options": [
        cell("iv_atm_30d", o.get("iv_atm_30d") or x.get("iv"), fmt="iv"),
        cell("iv_rank_60d", rank, rank is not None and (rank >= cfg.IV_RANK_HIGH or rank <= cfg.IV_RANK_LOW), "num0"),
        cell("implied_move_next_earnings", o.get("implied_move_next_earnings") or x.get("straddle"), fmt="pct"),
        cell("pc_ratio_oi", o.get("pc_ratio_oi")), cell("pc_ratio_vol", o.get("pc_ratio_vol")),
        cell("max_oi_strike_call", o.get("max_oi_strike_call"), fmt="usd0"), cell("max_oi_strike_put", o.get("max_oi_strike_put"), fmt="usd0")]}


def analysts(sym, extra):
    a = ((extra.get("stocks") or {}).get(sym) or {}).get("analysts") or {}
    cells = [{"key": k, "value": a[k]} for k in ("pt_mean", "pt_median", "pt_high", "pt_low") if a.get(k)]
    if a.get("rating_counts"):
        cells.append({"key": "rating_counts", "value": a["rating_counts"]})
    return cells


# ---------------------------------------------------------------- 캘린더 (CC.card_* 와 같은 비교)

def _abs_rets(bars):
    return {bars[i]["day"]: abs(bars[i]["adj"] / bars[i - 1]["adj"] - 1) * 100 for i in range(1, len(bars))}


def _reaction(days, ev):
    return CC._next_trading(days, ev["day"], same_day=ev.get("when") == "bmo")


def cal_earnings(s, snap):
    e = s.get("earnings") or {}
    if not e.get("next"):
        return None
    when = next((x.get("when") for x in snap["earnings"].get(s["sym"]) or [] if x["day"] == e["next"]), None)
    return {"day": e["next"], "left": (_d(e["next"]) - _d(s["day"])).days, "when": when,
            "bars": [{"day": m["day"], "ret": m["ret"]} for m in e.get("moves") or []],
            "median": e.get("median_abs"), "normal": (s.get("normal_range") or {}).get("sigma_pct"),
            "market_exp": ((s.get("expect") or {}).get("move") or {}).get("earn_day")}


def _earn_dates(sym, snap, extra):
    return snap["earnings"].get(sym) or (((extra.get("peer_earnings") or {}).get("dates") or {}).get(sym)) or []


def cal_peers(s, snap, extra):
    """함께 보는 회사(universe.PEERS — 고객 · 공급 · 경쟁)의 실적 — 앞으로 30일 안 발표 · 지난 발표 다음 날 이 종목 |움직임| 보통값 vs 이 종목 보통 날 (최근 2년 일봉).
    NVDA cal_cards.card_peers 와 같은 비교, 회사 목록만 종목마다."""
    roles = U.PEERS.get(s["sym"]) or {}
    if not roles:
        return None
    bars = snap["bars"][s["sym"]]
    days = [b["day"] for b in bars]
    rets = _abs_rets(bars)
    normal = statistics.median(list(rets.values())[-252:])
    end = (_d(s["day"]) + datetime.timedelta(days=CC.WINDOW)).isoformat()
    end_all = (_d(s["day"]) + datetime.timedelta(days=CC.LIST_DAYS)).isoformat()
    up, up_all, effect = [], [], {}
    for p in roles:
        evs = _earn_dates(p, snap, extra)
        up += [{"symbol": p, "day": x["day"]} for x in evs if s["day"] < x["day"] <= end]
        up_all += [{"symbol": p, "day": x["day"]} for x in evs if s["day"] < x["day"] <= end_all]
        hits = [rets.get(_reaction(days, x)) for x in evs if days[0] < x["day"] < s["day"]]
        hits = [h for h in hits if h is not None]
        effect[p] = {"median": statistics.median(hits) if hits else None, "n": len(hits)}
    return {"upcoming": sorted(up, key=lambda x: x["day"]), "upcoming_all": sorted(up_all, key=lambda x: x["day"]),
            "effect": effect, "normal": normal, "roles": roles}


def _macro_rows(day, end):
    if not os.path.exists(NVDA_DB):
        return []
    conn = sqlite3.connect(NVDA_DB)
    try:
        q = f"SELECT day, kind, label FROM calendar WHERE kind IN ({','.join('?' * len(CC.MACRO_KINDS))}) AND day >= ? AND day <= ? ORDER BY day"
        return [{"day": r[0], "kind": r[1], "label": r[2]} for r in conn.execute(q, (*CC.MACRO_KINDS, day, end))]
    finally:
        conn.close()


def cal_macro(day, snap):
    """시장 전체 일정 — CC.card_macro 와 같다(그날 S&P 500 |움직임| vs 보통 날). 지난 일정은 일봉이 있는 2년 안."""
    bars = snap["bars"].get(U.BENCH) or []
    days = [b["day"] for b in bars]
    rets = _abs_rets(bars)
    end = (_d(day) + datetime.timedelta(days=CC.WINDOW)).isoformat()
    rows = _macro_rows(days[0], (_d(day) + datetime.timedelta(days=CC.LIST_DAYS)).isoformat())
    effect = {}
    for kind in CC.MACRO_KINDS:
        hits = [rets.get(CC._next_trading(days, r["day"], same_day=True)) for r in rows if r["kind"] == kind and r["day"] < day]
        hits = [h for h in hits if h is not None]
        if hits:
            effect[kind] = {"median": statistics.median(hits), "n": len(hits)}
    return {"upcoming": [r for r in rows if day < r["day"] <= end], "effect": effect,
            "normal": statistics.median(list(rets.values())[-252:]), "rows": [r for r in rows if r["day"] > day]}


def all_upcoming(s, peers, macro):
    end = (_d(s["day"]) + datetime.timedelta(days=CC.LIST_DAYS)).isoformat()
    out = []
    e = (s.get("earnings") or {}).get("next")
    if e and e <= end:
        out.append({"day": e, "kind": "EARNINGS", "label": f"{s['name']} 실적 발표"})
    out += [{"day": x["day"], "kind": "EARNINGS_PEER", "label": f"{U.peer_name(x['symbol'])} 실적 발표"} for x in (peers or {}).get("upcoming_all") or []]
    out += [dict(r, label=CC.MACRO_KO.get(r["kind"], r["label"])) for r in (macro or {}).get("rows") or [] if r["day"] <= end]
    return sorted(out, key=lambda x: (x["day"], x["kind"]))


def build(s, snap, extra):
    """s 에 expect · calendar_cards · analysts 를 단다."""
    s["expect"] = {}
    group = peer_group(snap)
    for k, f in (("revenue", lambda: card_revenue(s["sym"], extra, group)), ("eps", lambda: card_eps(s["sym"], extra, group)),
                 ("move", lambda: card_move(s, snap, extra)), ("short", lambda: card_short(s["sym"], extra, group)),
                 ("capex", lambda: card_capex(s["sym"], extra))):
        try:
            s["expect"][k] = f()
        except Exception as e:   # noqa: BLE001
            print(f"[tabs] {s['sym']} {k} 실패 : {e}")
            s["expect"][k] = None
    s["analysts"] = analysts(s["sym"], extra)
    peers = cal_peers(s, snap, extra)
    s["options_status"] = options_status(s["sym"], extra)
    s["filings"] = sorted((v for v in (extra.get("edgar") or {}).values() if v["sym"] == s["sym"]), key=lambda v: v["at"], reverse=True)
    macro = cal_macro(s["day"], snap)
    s["calendar_cards"] = {"earnings": cal_earnings(s, snap), "peers": peers, "macro": macro, "all": all_upcoming(s, peers, macro)}
    return s
