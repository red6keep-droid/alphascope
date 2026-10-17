"""평소 범위 검증 — doc/평소-범위-검증-계획.md C1 ~ C8 (결과 보기 전 고정).

    .venv/bin/python experiments/issue_store/normal_range.py --check   # 진입 수만 (검증 아님)
    .venv/bin/python experiments/issue_store/normal_range.py           # 검증 ("검증해" 때만)

먼저: fetch_bars.py (일봉) · fetch_earnings_edgar.py (실적 접수 시각) · fetch_fx_krw.py (원/달러)

C1 주 방법 EWMA λ 0.94 (그날 장 마감까지), 비교 = 20일 · 60일 · "EWMA 와 252일 중 넓은 쪽"
C2 판정 1 · 5 · 10일(10일은 경계선), 참고 20일. 여러 날 = σ × √h (주), 비교 = h·(λ^h σ²_e + (1 − λ^h) σ²_252)
   겹치지 않는 구간
C3 P3 평소 구간의 그 종목 비율 = 약속 → P4 채점. ±1σ 안 · ±2σ 밖 위 · 아래. 경계 양쪽 p ≥ 0.05 녹 · ≥ 1e-4 황 · 그 아래 적
   (P3 · P4 비교는 Fisher 정확 검정 — 약속 비율 자체의 표본 오차를 넣기 위해, 교과서 비율은 이항 검정)
   판정 ① 교과서대로 ② 종목 비율로 ③ 흔들림 ④ 모름, P4 구간 < 30 이면 표본 부족. 틀린 날 몰림은 보고만
C4 P1 1999 ~ 2002 · P2 2003 ~ 2009 · P3 2010 ~ 2019 · P4 2020 ~
C5 시장 충격 VIX ≥ 35 ~ < 25 · 종목 충격 |r| ≥ 252일 표준편차 × 4 (실적일 제외) → 20거래일. 충격 시작 평가 · 보고
C6 실적 반응일 = EDGAR 8-K 2.02 접수 16:00 ET 전 그날 · 뒤 다음 거래일 (2004-09 이전은 earnings.csv 다음 거래일)
   EWMA 입력 · 평소 채점에서 제외. 분포 = |반응일| ÷ 직전 σ, 중앙값 · 10 ~ 90%, 최근 12회 · 전체, P3 80% 선 → P4
C7 원화 = 달러 로그 수익률 + 원/달러 로그 변화 (DEXKOUS, 빈 날 직전 값). 같은 규칙, 판정 따로, 원화 ÷ 달러 흔들림
C8 제외 종목 94 (이름 일치 · 아직 거래 · 이후 상폐) · 나머지 바깥 — 실적일 자료 없음 → 15종목 "실적일 안 뺀" 판과 비교
결과: results/normal_range.md · normal_range_*.csv
"""

import argparse
import math
import os

import numpy as np
import pandas as pd

from bollinger_by_stock import STOCKS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BARS = os.path.join(ROOT, "data", "store", "bars")
CAL = os.path.join(ROOT, "data", "store", "calendar")
DATA = os.path.join(ROOT, "backtest", "data")
OUT = os.path.join(os.path.dirname(__file__), "results")

LAM = 0.94
HZ = [1, 5, 10, 20]
JUDGE_HZ = [1, 5, 10]
START = pd.Timestamp("1999-01-01")
PERIODS = [("P1", "1999-01-01", "2002-12-31"), ("P2", "2003-01-01", "2009-12-31"),
           ("P3", "2010-01-01", "2019-12-31"), ("P4", "2020-01-01", "2099-12-31")]
VIX_IN, VIX_OUT = 35, 25
SHOCK_K, SHOCK_LEN = 4, 20
TEXTBOOK = {"in1": 0.6827, "up2": 0.02275, "dn2": 0.02275}
G_P, Y_P = 0.05, 1e-4
MIN_N = 30
METHODS = ["ewma", "d20", "d60", "wide"]


# ---------- 검정 (scipy 없이) ----------

def _lbin(k, n, p):
    if p <= 0:
        return 0.0 if k == 0 else -math.inf
    if p >= 1:
        return 0.0 if k == n else -math.inf
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * math.log(p) + (n - k) * math.log(1 - p)


def binom_p(k, n, p):
    """양쪽 정확 이항 p (pmf ≤ pmf(k) 의 합)."""
    if n == 0:
        return 1.0
    lk = _lbin(k, n, p)
    tot = sum(math.exp(l) for l in (_lbin(i, n, p) for i in range(n + 1)) if l <= lk + 1e-9)
    return min(1.0, tot)


def fisher_p(a, b, c, d):
    """2×2 [[a, b], [c, d]] 양쪽 Fisher 정확 p."""
    r1, c1, n = a + b, a + c, a + b + c + d
    if n == 0 or r1 == 0 or r1 == n or c1 == 0 or c1 == n:
        return 1.0

    def lh(x):
        return (math.lgamma(r1 + 1) - math.lgamma(x + 1) - math.lgamma(r1 - x + 1)
                + math.lgamma(n - r1 + 1) - math.lgamma(c1 - x + 1) - math.lgamma(n - r1 - c1 + x + 1)
                - math.lgamma(n + 1) + math.lgamma(c1 + 1) + math.lgamma(n - c1 + 1))
    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    la = lh(a)
    return min(1.0, sum(math.exp(l) for l in (lh(x) for x in range(lo, hi + 1)) if l <= la + 1e-9))


def color(p):
    return "녹" if p >= G_P else ("황" if p >= Y_P else "적")


WORST = {"녹": 0, "황": 1, "적": 2}


# ---------- 데이터 ----------

def load_close(sym):
    f = os.path.join(BARS, sym.replace("^", "_").replace("=", "_") + ".parquet")
    if not os.path.exists(f):
        return None
    c = pd.read_parquet(f)["close"]
    c = c[c > 0].dropna()
    c.index = pd.to_datetime(c.index).tz_localize(None).normalize()
    return c[~c.index.duplicated()]


def period_of(d):
    for name, a, b in PERIODS:
        if pd.Timestamp(a) <= d <= pd.Timestamp(b):
            return name
    return None


def market_shock(idx):
    v = load_close("^VIX").reindex(idx, method="ffill")
    m, inside = np.zeros(len(idx), bool), False
    for i, x in enumerate(v.values):
        if not inside and x >= VIX_IN:
            inside = True
        elif inside and x < VIX_OUT:
            inside = False
        m[i] = inside
    return pd.Series(m, index=idx)


def earnings_days(sym, idx):
    """반응일 (EDGAR 우선, 2004-09 이전은 earnings.csv 다음 거래일). csv 만 있는 2004-09 이후 날은 따로."""
    e = pd.read_csv(os.path.join(CAL, "earnings_edgar.csv"))
    e = e[e.symbol == sym]
    days = set()
    for t in pd.to_datetime(e.accepted_et):
        i = idx.searchsorted(t.normalize())
        if i < len(idx) and idx[i] == t.normalize() and t.hour >= 16:
            i += 1
        if i < len(idx):
            days.add(idx[i])
    csv = pd.read_csv(os.path.join(CAL, "earnings.csv"))
    csv = csv[csv.symbol == sym]
    csv_days = set()
    for d in pd.to_datetime(csv.day):
        i = idx.searchsorted(d)
        if i < len(idx) and idx[i] == d:
            i += 1
        if i < len(idx):
            csv_days.add(idx[i])
    cut = pd.Timestamp("2004-09-01")
    days |= {d for d in csv_days if d < cut}
    csv_only = sorted(d for d in csv_days if d >= cut and d not in days)
    return days, csv_only


def fx_logret(idx):
    fx = load_close("DEXKOUS")
    fx = fx.reindex(fx.index.union(idx)).ffill().reindex(idx)
    return np.log(fx).diff()


# ---------- 한 종목 ----------

def prepare(r, earn, mshock):
    """σ 예측(그날 장 마감까지 → 다음 날) · 충격 · 실적 표시."""
    r_in = r.where(~earn)
    var_e = (r_in ** 2).ewm(alpha=1 - LAM, adjust=False, ignore_na=True).mean().shift(1)
    sd = {"ewma": np.sqrt(var_e),
          "d20": r_in.rolling(20, min_periods=15).std().shift(1),
          "d60": r_in.rolling(60, min_periods=45).std().shift(1)}
    s252 = r_in.rolling(252, min_periods=200).std().shift(1)
    sd["wide"] = np.maximum(sd["ewma"], s252)
    trig = (r.abs() >= SHOCK_K * s252) & ~earn
    sshock = pd.Series(False, index=r.index)
    for i in np.flatnonzero(trig.values):
        sshock.iloc[i:i + SHOCK_LEN] = True
    return {"r": r, "sd": sd, "s252": s252, "earn": earn, "mshock": mshock, "sshock": sshock,
            "shock": mshock | sshock, "trig": trig}


def windows(P, h, method, blend=False):
    """겹치지 않는 h일 구간: 기준일 t 장 마감 → t+1 ~ t+h. 반환 DataFrame."""
    r, idx = P["r"], P["r"].index
    sd = P["sd"][method]
    ok = (idx >= START) & sd.notna().values & P["s252"].notna().values
    first = np.flatnonzero(ok)
    if len(first) == 0:
        return pd.DataFrame()
    rv, ev, shv = r.values, P["earn"].values, P["shock"].values
    rows = []
    for t in range(first[0] - 1, len(idx) - h, h):
        a, b = t + 1, t + 1 + h
        s1 = sd.values[a]
        if not np.isfinite(s1) or s1 <= 0:
            continue
        if blend:
            lr = P["s252"].values[a]
            sh = math.sqrt(h * (LAM ** h * s1 ** 2 + (1 - LAM ** h) * lr ** 2))
        else:
            sh = s1 * math.sqrt(h)
        R = np.nansum(rv[a:b])
        bucket = "earn" if ev[a:b].any() else ("shock" if shv[a:b].any() else "normal")
        rows.append((idx[a], period_of(idx[a]), bucket, R / sh))
    return pd.DataFrame(rows, columns=["day", "period", "bucket", "z"])


def tally(w):
    if w.empty:
        return pd.DataFrame()
    w = w.dropna(subset=["period"])
    g = w.groupby(["period", "bucket"])["z"]
    return pd.DataFrame({"n": g.size(), "in1": g.apply(lambda z: int((z.abs() < 1).sum())),
                         "up2": g.apply(lambda z: int((z > 2).sum())),
                         "dn2": g.apply(lambda z: int((z < -2).sum()))}).reset_index()


def clustering(P):
    """h = 1 평소 날: 어제 2σ 밖 → 오늘 2σ 밖 (주 방법)."""
    z = (P["r"] / P["sd"]["ewma"]).where(~P["earn"] & ~P["shock"])
    z = z[z.index >= START]
    out = z.abs() > 2
    prev = out.shift(1)
    both_ok = z.notna() & z.shift(1).notna()
    return int((prev & both_ok).sum()), int((prev & out & both_ok).sum()), int(both_ok.sum()), int((out & both_ok).sum())


def shock_onsets(P, sym, cur, p3_out2):
    """충격 시작 평가: 구간 첫 20거래일 2σ 밖 날 수(방법별) · 회복 일수 · 최대 벗어남."""
    r, idx = P["r"], P["r"].index
    thr = max(1, math.ceil(2 * (p3_out2 if p3_out2 else 0.0455) * 20))
    starts = []
    m = P["mshock"].values
    for i in range(1, len(idx)):
        if m[i] and not m[i - 1] and idx[i] >= START:
            starts.append((i, "시장"))
    for i in np.flatnonzero(P["trig"].values):
        if idx[i] >= START and not (i > 0 and P["sshock"].values[i - 1]):
            starts.append((i, "종목"))
    rows = []
    for i, kind in starts:
        seg = slice(i, min(i + 20, len(idx)))
        rec = {}
        for meth in METHODS:
            z = (r / P["sd"][meth]).where(~P["earn"]).values
            rec[meth] = int(np.nansum(np.abs(z[seg]) > 2))
        z = (r / P["sd"]["ewma"]).where(~P["earn"]).values
        recov = None
        for k in range(0, 251):
            win = np.abs(z[i + k:i + k + 20])
            if len(win) < 20:
                break
            if np.nansum(win > 2) <= thr:
                recov = k
                break
        rows.append({"symbol": sym, "cur": cur, "start": idx[i].date(), "kind": kind,
                     **{f"out2_20d_{m_}": rec[m_] for m_ in METHODS},
                     "recovery_days": recov if recov is not None else ">250",
                     "max_dev_sigma": round(float(np.nanmax(np.abs(z[seg]))), 1)})
    return rows


def earnings_dist(P, sym, cur, days):
    r, sd = P["r"], P["sd"]["ewma"]
    rows = []
    for d in sorted(days):
        if d < START or d not in r.index or not np.isfinite(sd.get(d, np.nan)):
            continue
        rows.append({"symbol": sym, "cur": cur, "day": d.date(), "period": period_of(d),
                     "ret": float(r[d]), "ratio": float(abs(r[d]) / sd[d])})
    return rows


# ---------- 판정 ----------

def judge(t):
    """t: 한 종목 · 통화 · 방법 · h 의 평소 구간 tally (period 별)."""
    by = {row.period: row for row in t.itertuples()}
    p3, p4 = by.get("P3"), by.get("P4")
    res = {"n_P3": p3.n if p3 is not None else 0, "n_P4": p4.n if p4 is not None else 0}
    for m in TEXTBOOK:
        for name, row in (("P3", p3), ("P4", p4)):
            res[f"{m}_{name}"] = round(getattr(row, m) / row.n, 4) if row is not None and row.n else None
    if p3 is None or p4 is None or p4.n < MIN_N or p3.n < MIN_N:
        res["verdict"] = "표본 부족"
        return res
    tb = max((WORST[color(binom_p(getattr(row, m), row.n, p0))] for m, p0 in TEXTBOOK.items() for row in (p3, p4)))
    own_ps = {m: fisher_p(getattr(p3, m), p3.n - getattr(p3, m), getattr(p4, m), p4.n - getattr(p4, m)) for m in TEXTBOOK}
    own = max(WORST[color(p)] for p in own_ps.values())
    res.update({f"p_own_{m}": round(p, 4) for m, p in own_ps.items()})
    res["textbook"] = ["녹", "황", "적"][tb]
    res["own"] = ["녹", "황", "적"][own]
    res["verdict"] = "① 교과서대로" if tb == 0 else ("② 종목 비율로" if own == 0 else ("③ 흔들림" if own == 1 else "④ 모름"))
    return res


# ---------- 실행 ----------

def removed_set():
    r = pd.read_csv(os.path.join(DATA, "removed.csv"))
    r = r[r.status.isin(["still_trading", "delisted_soon"]) & (r.name_match == True)]  # noqa: E712
    return {s.replace(".", "-"): pd.Timestamp(d) for s, d in zip(r.symbol, r.removed)}


def outside_set(removed):
    u = pd.read_csv(os.path.join(DATA, "universe.csv"))
    return [s.replace(".", "-") for s in u.symbol if s.replace(".", "-") not in STOCKS and s.replace(".", "-") not in removed]


def run_stock(sym, earn_excl, with_krw, detail):
    c = load_close(sym)
    if c is None or len(c) < 500:
        return None
    idx = c.index
    r_usd = np.log(c).diff()
    if earn_excl:
        edays, csv_only = earnings_days(sym, idx)
    else:
        edays, csv_only = set(), []
    earn = pd.Series(idx.isin(list(edays)), index=idx)
    ms = market_shock(idx)
    curs = {"USD": r_usd}
    if with_krw:
        curs["KRW"] = r_usd + fx_logret(idx)
    out = {"tally": [], "cluster": [], "onset": [], "earn": [], "csv_only": csv_only, "edays": edays,
           "krw": [], "P": {}}
    for cur, r in curs.items():
        P = prepare(r, earn, ms)
        out["P"][cur] = P
        for meth in METHODS:
            for h in HZ:
                for blend in ((False, True) if (meth == "ewma" and h > 1) else (False,)):
                    t = tally(windows(P, h, meth, blend))
                    if not t.empty:
                        t.insert(0, "method", meth + ("+blend" if blend else ""))
                        t.insert(0, "h", h)
                        t.insert(0, "cur", cur)
                        t.insert(0, "symbol", sym)
                        out["tally"].append(t)
        if detail:
            a, b, n, o = clustering(P)
            out["cluster"].append({"symbol": sym, "cur": cur, "out2_days": o, "prev_out": a, "both_out": b, "n": n})
            out["earn"] += earnings_dist(P, sym, cur, edays)
    return out


def check():
    removed = removed_set()
    outside = outside_set(removed)
    print("15종목 (USD · 실적일 제외)")
    print(f"{'종목':6} {'1999~일':>7} {'실적일':>6} {'csv만':>5} {'시장충격일':>9} {'종목충격':>8} " +
          " ".join(f"{p}h{h}" for p in ("P3", "P4") for h in JUDGE_HZ) + "  실적(P3/P4)")
    for sym in STOCKS:
        o = run_stock(sym, True, False, False)
        P = o["P"]["USD"]
        idx = P["r"].index
        keep = idx >= START
        t = pd.concat(o["tally"])
        t = t[(t.method == "ewma") & (t.bucket == "normal")]
        cells = []
        for p in ("P3", "P4"):
            for h in JUDGE_HZ:
                v = t[(t.period == p) & (t.h == h)].n
                cells.append(f"{int(v.iloc[0]) if len(v) else 0:>5}")
        ed = [d for d in o["edays"] if d >= START]
        e3 = sum(1 for d in ed if period_of(d) == "P3")
        e4 = sum(1 for d in ed if period_of(d) == "P4")
        print(f"{sym:6} {keep.sum():>7} {len(ed):>6} {len(o['csv_only']):>5} {int(P['mshock'][keep].sum()):>9} "
              f"{int(P['trig'][keep].sum()):>8} " + " ".join(cells) + f"  {e3}/{e4}")
    fx = load_close("DEXKOUS")
    print(f"\n원/달러: {fx.index[0].date()} ~ {fx.index[-1].date()} ({len(fx)}일)")
    have_r = [s for s in removed if load_close(s) is not None]
    have_o = [s for s in outside if load_close(s) is not None]
    p4r = sum(1 for s in have_r if load_close(s).index.max() >= pd.Timestamp("2020-06-01"))
    print(f"제외 종목 {len(removed)} 중 일봉 {len(have_r)} (P4 반년 이상 {p4r}) · 나머지 바깥 {len(outside)} 중 일봉 {len(have_o)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        check()
        return
    run_all()


def summarize_earn(E):
    rows = []
    for (sym, cur), g in E.groupby(["symbol", "cur"]):
        g = g.sort_values("day")
        res = {"symbol": sym, "cur": cur}
        for name, s in (("전체", g), ("최근12", g.tail(12)), ("P3", g[g.period == "P3"]), ("P4", g[g.period == "P4"])):
            res[f"n_{name}"] = len(s)
            res[f"med_{name}"] = round(s.ratio.median(), 2) if len(s) else None
            res[f"q10_{name}"] = round(s.ratio.quantile(0.1), 2) if len(s) else None
            res[f"q90_{name}"] = round(s.ratio.quantile(0.9), 2) if len(s) else None
        res["up"], res["down"] = int((g.ret > 0).sum()), int((g.ret < 0).sum())
        p3, p4 = g[g.period == "P3"].ratio, g[g.period == "P4"].ratio
        if len(p3) >= 20 and len(p4) >= 20:
            t80 = p3.quantile(0.8)
            k3, k4 = int((p3 <= t80).sum()), int((p4 <= t80).sum())
            pv = fisher_p(k3, len(p3) - k3, k4, len(p4) - k4)
            res.update({"t80_P3": round(t80, 2), "P4_within": round(k4 / len(p4), 2), "p": round(pv, 4), "color": color(pv)})
        else:
            res["color"] = "표본 부족"
        rows.append(res)
    return pd.DataFrame(rows)


def final_year(sym, rdate):
    o = run_stock(sym, False, False, False)
    if o is None:
        return None
    P = o["P"]["USD"]
    z = (P["r"] / P["sd"]["ewma"]).where(~P["shock"])
    z = z[z.index >= START].dropna()
    pos = z.index.searchsorted(rdate)
    if pos < 300:
        return None
    before, last = z.iloc[:pos - 252], z.iloc[pos - 252:pos]
    res = {"symbol": sym, "removed": rdate.date(), "n_before": len(before), "n_last": len(last)}
    for m, f in (("in1", lambda x: x.abs() < 1), ("out2", lambda x: x.abs() > 2)):
        k1, k2 = int(f(before).sum()), int(f(last).sum())
        res[f"{m}_before"], res[f"{m}_last"] = round(k1 / len(before), 4), round(k2 / max(len(last), 1), 4)
        res[f"p_{m}"] = round(fisher_p(k1, len(before) - k1, k2, len(last) - k2), 4)
    res["color"] = ["녹", "황", "적"][max(WORST[color(res["p_in1"])], WORST[color(res["p_out2"])])]
    return res


def judge_table(T, group):
    rows = []
    N = T[T.bucket == "normal"]
    for (sym, cur, meth, h), t in N.groupby(["symbol", "cur", "method", "h"]):
        rows.append({"group": group, "symbol": sym, "cur": cur, "method": meth, "h": h, **judge(t)})
    return pd.DataFrame(rows)


def run_all():
    os.makedirs(OUT, exist_ok=True)
    tallies, clus, onsets, earns, mism, krw = [], [], [], [], [], []
    for sym in STOCKS:
        o = run_stock(sym, True, True, True)
        tallies += o["tally"]
        clus += o["cluster"]
        earns += o["earn"]
        mism.append({"symbol": sym, "csv_only_days": len(o["csv_only"])})
        T = pd.concat(o["tally"])
        for cur in ("USD", "KRW"):
            P = o["P"][cur]
            t = T[(T.cur == cur) & (T.method == "ewma") & (T.h == 1) & (T.bucket == "normal") & (T.period == "P3")]
            p3 = float((t.up2 + t.dn2).sum() / t.n.sum()) if len(t) else None
            onsets += shock_onsets(P, sym, cur, p3)
        ru, rk = o["P"]["USD"]["r"], o["P"]["KRW"]["r"]
        sh, ea = o["P"]["USD"]["shock"], o["P"]["USD"]["earn"]
        for name, a, b in PERIODS:
            for bucket, m in (("평소", ~sh & ~ea), ("충격", sh & ~ea)):
                sel = m & (ru.index >= pd.Timestamp(a)) & (ru.index <= pd.Timestamp(b)) & (ru.index >= START)
                if sel.sum() >= 20:
                    krw.append({"symbol": sym, "period": name, "bucket": bucket, "days": int(sel.sum()),
                                "krw_over_usd": round(float(rk[sel].std() / ru[sel].std()), 3)})
        print(f"[15] {sym}")
    T15 = pd.concat(tallies)
    J = [judge_table(T15, "15")]
    noex = []
    for sym in STOCKS:
        noex += run_stock(sym, False, False, False)["tally"]
    J.append(judge_table(pd.concat(noex), "15_실적안뺌"))
    removed = removed_set()
    rem_t, fy = [], []
    for sym, d in removed.items():
        o = run_stock(sym, False, False, False)
        if o:
            rem_t += o["tally"]
            f = final_year(sym, d)
            if f:
                fy.append(f)
    if rem_t:
        J.append(judge_table(pd.concat(rem_t), "제외94"))
    out_t = []
    for i, sym in enumerate(outside_set(removed)):
        o = run_stock(sym, False, False, False)
        if o:
            out_t += [t[t.method == "ewma"] for t in o["tally"]]
        if i % 100 == 0:
            print(f"[바깥] {i}")
    if out_t:
        J.append(judge_table(pd.concat(out_t), "바깥"))
    J = pd.concat(J)
    E = pd.DataFrame(earns)
    ES = summarize_earn(E)
    pd.concat([T15]).to_csv(os.path.join(OUT, "normal_range_tally.csv"), index=False)
    J.to_csv(os.path.join(OUT, "normal_range_judge.csv"), index=False)
    pd.DataFrame(onsets).to_csv(os.path.join(OUT, "normal_range_onsets.csv"), index=False)
    E.to_csv(os.path.join(OUT, "normal_range_earn_events.csv"), index=False)
    ES.to_csv(os.path.join(OUT, "normal_range_earn.csv"), index=False)
    pd.DataFrame(krw).to_csv(os.path.join(OUT, "normal_range_krw.csv"), index=False)
    pd.DataFrame(clus).to_csv(os.path.join(OUT, "normal_range_cluster.csv"), index=False)
    pd.DataFrame(fy).to_csv(os.path.join(OUT, "normal_range_final_year.csv"), index=False)
    write_md(J, pd.DataFrame(onsets), ES, pd.DataFrame(krw), pd.DataFrame(clus), pd.DataFrame(fy), pd.DataFrame(mism))


def write_md(J, O, ES, K, C, FY, M):
    L = ["# 평소 범위 검증 결과", "", "계획: doc/평소-범위-검증-계획.md (C1 ~ C8). 판정 = 주 방법 EWMA, 평소 구간, P3 약속 → P4 채점.", ""]
    main = J[(J.group == "15") & (J.method == "ewma")]
    for cur in ("USD", "KRW"):
        L += [f"## 1. 15종목 판정 ({cur})", "", "| 종목 | " + " | ".join(f"{h}일" for h in HZ) + " |", "|---|" + "---|" * len(HZ)]
        for sym in STOCKS:
            cells = []
            for h in HZ:
                v = main[(main.symbol == sym) & (main.cur == cur) & (main.h == h)]
                cells.append(v.verdict.iloc[0] if len(v) else "-")
            L.append(f"| {sym} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["## 2. 방법별 판정 수 (15종목 USD)", "", "| 방법 | h | ① | ② | ③ | ④ | 표본 부족 |", "|---|---|---|---|---|---|---|"]
    m = J[(J.group == "15") & (J.cur == "USD")]
    for (meth, h), g in m.groupby(["method", "h"]):
        vc = g.verdict.value_counts()
        L.append(f"| {meth} | {h} | " + " | ".join(str(int(vc.get(k, 0))) for k in
                 ("① 교과서대로", "② 종목 비율로", "③ 흔들림", "④ 모름", "표본 부족")) + " |")
    L += ["", "## 3. 그룹별 판정 비율 (USD · EWMA · 실적일 안 뺌 비교)", "", "| 그룹 | h | 종목 수 | ① | ② | ③ | ④ | 표본 부족 |", "|---|---|---|---|---|---|---|---|"]
    for grp in ("15_실적안뺌", "제외94", "바깥"):
        g0 = J[(J.group == grp) & (J.method == "ewma") & (J.cur == "USD")]
        for h in JUDGE_HZ:
            g = g0[g0.h == h]
            vc = g.verdict.value_counts(normalize=True)
            L.append(f"| {grp} | {h} | {len(g)} | " + " | ".join(f"{vc.get(k, 0):.0%}" for k in
                     ("① 교과서대로", "② 종목 비율로", "③ 흔들림", "④ 모름", "표본 부족")) + " |")
    if not FY.empty:
        L += ["", f"제외 종목 '빠지기 직전 1년' 색: " + ", ".join(f"{k} {v}" for k, v in FY.color.value_counts().items()), ""]
    L += ["## 4. 틀린 날 몰림 (h = 1, 평소 날)", "", "| 종목 | 통화 | 2σ 밖 비율 | 어제 밖 → 오늘 밖 |", "|---|---|---|---|"]
    for r in C.itertuples():
        L.append(f"| {r.symbol} | {r.cur} | {r.out2_days / max(r.n, 1):.1%} | {r.both_out / max(r.prev_out, 1):.1%} ({r.both_out}/{r.prev_out}) |")
    L += ["", "## 5. 충격 시작 (첫 20거래일 2σ 밖 날 수 중앙값 · 회복 일수 중앙값)", "",
          "| 종목 | 종류 | 횟수 | EWMA | 20일 | 60일 | 넓은 쪽 | 회복(일) | 최대 벗어남(σ) |", "|---|---|---|---|---|---|---|---|---|"]
    Ou = O[O.cur == "USD"].copy()
    Ou["rec"] = pd.to_numeric(Ou.recovery_days, errors="coerce")
    for (sym, kind), g in Ou.groupby(["symbol", "kind"]):
        L.append(f"| {sym} | {kind} | {len(g)} | " + " | ".join(f"{g[f'out2_20d_{m_}'].median():.0f}" for m_ in METHODS)
                 + f" | {g.rec.median():.0f} (250 넘음 {g.rec.isna().sum()}) | {g.max_dev_sigma.median():.1f} |")
    L += ["", "## 6. 실적일 분포 (|반응일| ÷ 직전 σ, USD)", "",
          "| 종목 | 전체 n · 중앙값 · 10 ~ 90% | 최근 12 중앙값 | P3 80% 선 → P4 안 | 색 | 오름/내림 |", "|---|---|---|---|---|---|"]
    for r in ES[ES.cur == "USD"].itertuples():
        t = f"{r.t80_P3} → {r.P4_within:.0%}" if hasattr(r, "t80_P3") and pd.notna(getattr(r, "t80_P3", np.nan)) else "-"
        L.append(f"| {r.symbol} | {r.n_전체} · {r.med_전체} · {r.q10_전체} ~ {r.q90_전체} | {r.med_최근12} | {t} | {r.color} | {r.up}/{r.down} |")
    L += ["", "방향(오름/내림)은 세기만 함 — 예측 근거 아님.", "", "## 7. 원화 ÷ 달러 흔들림", "",
          "| 종목 | " + " | ".join(f"{p} 평소 | {p} 충격" for p, _, _ in PERIODS) + " |", "|---|" + "---|" * (2 * len(PERIODS))]
    for sym in STOCKS:
        cells = []
        for p, _, _ in PERIODS:
            for b in ("평소", "충격"):
                v = K[(K.symbol == sym) & (K.period == p) & (K.bucket == b)]
                cells.append(f"{v.krw_over_usd.iloc[0]:.2f}" if len(v) else "-")
        L.append(f"| {sym} | " + " | ".join(cells) + " |")
    L += ["", "## 8. 날짜 대조", "", "2004-09 이후 earnings.csv 에만 있는 반응일 수: " + ", ".join(f"{r.symbol} {r.csv_only_days}" for r in M.itertuples()), ""]
    with open(os.path.join(OUT, "normal_range.md"), "w") as f:
        f.write("\n".join(L))
    print("저장:", os.path.join(OUT, "normal_range.md"))


if __name__ == "__main__":
    main()
