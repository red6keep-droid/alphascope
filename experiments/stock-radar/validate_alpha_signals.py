"""Alpha Scope 신호 검증 1차 — 가격으로 다시 만들 수 있는 신호 (doc/기획/알파스코프-신호-재설계.md 3-4 · 4절, 2026-11-02 사용자 "검증해").

    python experiments/stock-radar/validate_alpha_signals.py    # → doc/검증/알파스코프-신호-검증.md · data/validate_alpha_signals.json

신호 정의는 페이지와 같다(analyze · tech_signals · signal_groups):
- 기술지표 방향(단기)  tech_signals 전체 요약 → 상승 · 강한 상승 = +1, 하락 · 강한 하락 = −1
- 과열 신호(단기)      RSI14 ≥ 80 · 200일 평균 +40% · 20일 +25% 중 하나 → −1
- 업계 자금(단기)      업종 ETF 20일 − S&P 500 20일 ≥ +2%p → +1, ≤ −2%p → −1
- 평균선 대비(중기)    20 · 60 · 120 · 200일 평균 모두 위 → +1, 모두 아래 → −1
- 12개월 모멘텀(중기)  (21일 전 ÷ 252일 전) 우리 종목 안 상위 25% → +1, 하위 25% → −1
- 증시 분위기(단기)    S&P 500 상승 추세 → +1, 조정장 → −1 (VIX 30 이상 = 불안 국면 = 0)
- 시장 충격(단기)      VIX 35 이상 시작 · 25 아래 끝, 그 안 → −1

판정 기준 (결과 보기 전에 고정, 문서 3-4):
- 맞힘 = 시장 대비 초과 수익: 종목 h거래일 뒤 수익 − S&P 500(SPY) 같은 기간. 단기 h=5, 중기 h=21 · 63.
  증시 분위기 · 시장 충격은 시장 전체 신호라 종목 초과 수익이 아니라 S&P 500 자체 수익으로 잰다
- 값 = 신호 방향 × 초과 수익의 평균(%p, edge) · 맞힘률(초과 수익 부호가 신호와 같은 비율)
- 플라시보 = 종목마다 신호 줄을 1~n년 무작위로 밀기(순환) 500회 — 신호가 얼마나 자주 · 오래 켜지는지는 그대로, 날짜만 어긋나게
- 통과 = 플라시보보다 edge 가 큰 쪽(신호 방향)으로 p < 0.05(여러 번 시험 Holm 보정) · 앞 절반(1999~2012) · 뒤 절반(2013~) 둘 다 플라시보 평균보다 신호 방향
묶음: ① 우리 64종목(오늘 살아남은 큰 종목 — 생존 편향) ② 30년 저장소 전체(상장폐지 포함 약 740개 — 바깥 확인, 업계 자금 · 기술지표는 ①만)
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", ".."))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, ".."))
sys.path.insert(0, os.path.join(BASE, "..", "nvda-report"))
import config as NC  # noqa: E402
import tech_signals as TS  # noqa: E402
import universe as U  # noqa: E402

STORE = os.path.join(ROOT, "data", "store", "bars")
OUT_MD = os.path.join(ROOT, "doc", "검증", "알파스코프-신호-검증.md")
OUT_JSON = os.path.join(BASE, "data", "validate_alpha_signals.json")
SEED = 20261102
N_PL = int(os.environ.get("N_PL", "500"))
START, SPLIT = "1999-01-01", "2013-01-01"
LOAD_FROM = "1997-06-01"   # 200 · 252일 창을 채울 앞 기간
TECH_WIN = 260
ALPHA = 0.05


def _load(sym):
    for f in (sym, sym.replace("-", "."), sym.replace("^", "_")):
        p = os.path.join(STORE, f"{f}.parquet")
        if os.path.exists(p):
            d = pd.read_parquet(p)
            d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
            return d[d.index >= LOAD_FROM]
    return None


def _download(syms):
    import yfinance as yf
    out = {}
    df = yf.download(syms, start=LOAD_FROM, interval="1d", auto_adjust=True, group_by="ticker", progress=False, threads=3)
    for s in syms:
        try:
            d = df[s][["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        except KeyError:
            continue
        d.columns = ["open", "high", "low", "close", "volume"]
        d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
        if len(d):
            out[s] = d
    return out


def frames(syms, fetch=True):
    got, miss = {}, []
    for s in syms:
        d = _load(s)
        (miss.append(s) if d is None or not len(d) else got.__setitem__(s, d))
    if miss and fetch:
        got.update(_download(miss))
    return got


# ---------------------------------------------------------------- 신호 (날짜 × 종목, +1 · −1 · 0, 계산 못 하면 NaN)

def sig_tech(d):
    """tech_signals 전체 요약을 날마다 (창 260봉) — 페이지 카드와 같은 계산."""
    d = d.dropna(subset=["close"])
    d = d[d["close"] > 0]
    bars = [{"day": str(i.date()), "close": r.close, "high": r.high if r.high == r.high else r.close, "low": r.low if r.low == r.low else r.close,
             "open": r.open, "volume": r.volume} for i, r in d.iterrows()]
    out = np.full(len(bars), np.nan)
    m = {"강한 상승": 1, "상승": 1, "하락": -1, "강한 하락": -1}
    for i in range(TECH_WIN - 1, len(bars)):
        try:
            al = TS._frame(bars[i - TECH_WIN + 1:i + 1], "us")[4]
        except (TypeError, ZeroDivisionError, ValueError):   # 값이 빈 봉(옛 자료) — 그날은 계산하지 않는다
            continue
        out[i] = m.get(TS.word(al["net"]).lstrip("▲▼ "), 0)   # 답 앞 ▲ · ▼ 를 뗀다
    return pd.Series(out, index=d.index)


def _rsi(c, n=14):
    d = c.diff()
    up, dn = d.clip(lower=0), -d.clip(upper=0)
    au = up.ewm(alpha=1 / n, adjust=False).mean()
    ad = dn.ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + au / ad)


def sig_overheat(C):
    ma200 = C.rolling(200, min_periods=200).mean()
    hot = (C.apply(_rsi) >= NC.OVERHEAT_RSI) | ((C / ma200 - 1) * 100 >= NC.OVERHEAT_MA200_PCT) | ((C / C.shift(20) - 1) * 100 >= NC.OVERHEAT_RET20_PCT)
    return (-hot.astype(float)).where(ma200.notna())


def sig_ma(C):
    rel = [C / C.rolling(n, min_periods=n).mean() - 1 for n in (20, 60, 120, 200)]
    above = sum((r > 0).astype(int) for r in rel)
    below = sum((r < 0).astype(int) for r in rel)
    s = pd.DataFrame(0.0, index=C.index, columns=C.columns)
    s[above == 4] = 1.0
    s[below == 4] = -1.0
    return s.where(rel[-1].notna())


def sig_momentum(C, min_n=8):
    mom = C.shift(21) / C.shift(252) - 1
    r = mom.rank(axis=1, pct=False)
    n = mom.notna().sum(axis=1)
    s = pd.DataFrame(0.0, index=C.index, columns=C.columns)
    s[r.le(n.div(4), axis=0)] = -1.0   # 하위 25% (순위 1 = 가장 낮음)
    s[r.gt(n.mul(3 / 4), axis=0)] = 1.0
    return s.where(mom.notna() & n.ge(min_n).to_numpy()[:, None])


def sig_sector(C, etfs, spy):
    out = {}
    for s in C.columns:
        e = U.sector_etf(s)[0]
        if e not in etfs:
            continue
        rel = ((etfs[e] / etfs[e].shift(20)) - (spy / spy.shift(20))) * 100
        x = pd.Series(0.0, index=rel.index)
        x[rel >= NC.SECTOR_FLOW_PP] = 1.0
        x[rel <= -NC.SECTOR_FLOW_PP] = -1.0
        out[s] = x.where(rel.notna()).reindex(C.index)
    return pd.DataFrame(out)


def sig_regime(spy, vix):
    hi = spy.rolling(NC.REGIME_HIGH_DAYS, min_periods=NC.REGIME_HIGH_DAYS).max()
    ph = ((spy / hi - 1) * 100).round(1)
    ma = spy.rolling(NC.REGIME_MA_DAYS, min_periods=NC.REGIME_MA_DAYS).mean()
    v = vix.reindex(spy.index).ffill()
    s = pd.Series(0.0, index=spy.index)
    corr = (ph <= NC.REGIME_CORRECTION_PCT) | (spy < ma)
    s[corr] = -1.0
    s[~corr & (ph > NC.REGIME_PULLBACK_PCT)] = 1.0
    s[v >= NC.REGIME_VIX_HIGH] = 0.0
    return s.where(ma.notna() & hi.notna())


def sig_shock(spy, vix):
    v = vix.reindex(spy.index).ffill()
    inside, out = False, []
    for x in v:
        if not inside and x >= 35:
            inside = True
        elif inside and x < 25:
            inside = False
        out.append(-1.0 if inside else 0.0)
    return pd.Series(out, index=spy.index)


# ---------------------------------------------------------------- 검정

def fwd(C, h):
    return (C.shift(-h) / C - 1) * 100


def test(S, X, name, horizon, group, rng, expect=+1):
    """S · X = 같은 모양(날짜 × 열). 기간 START~ 만. 플라시보 = 열마다 신호를 무작위로 순환 이동."""
    S, X = S.loc[START:], X.reindex(S.index).loc[START:]
    if isinstance(S, pd.Series):
        S, X = S.to_frame("mkt"), X.to_frame("mkt")
    cols = [c for c in S.columns if c in X.columns]
    Sv, Xv = S[cols].to_numpy(dtype=float), X[cols].to_numpy(dtype=float)
    valid = ~np.isnan(Sv) & np.isfinite(Xv) & (np.abs(Xv) < 300)   # 0 원 · 액면 분할 오류 같은 깨진 봉(±300% 넘는 초과 수익)은 뺀다
    Sv0, Xv0 = np.where(valid, Sv, 0.0), np.where(valid, Xv, 0.0)
    on = (Sv0 != 0)
    n_on = int(on.sum())
    if n_on < 200:
        return {"name": name, "group": group, "h": horizon, "n_on": n_on, "note": "표본 부족"}
    edge = float((Sv0 * Xv0).sum() / n_on)
    hit = float(((np.sign(Xv0) == Sv0) & on).sum() / n_on)
    split = S.index < pd.Timestamp(SPLIT)
    halves = []
    for m in (split, ~split):
        k = on[m].sum()
        halves.append(float((Sv0[m] * Xv0[m]).sum() / k) if k else float("nan"))
    T = len(S)
    pl, pl_h = [], []
    for _ in range(N_PL):
        tot, cnt, h1, h2, c1, c2 = 0.0, 0, 0.0, 0.0, 0, 0
        for j in range(len(cols)):
            col_ok = valid[:, j]
            idx = np.flatnonzero(col_ok)
            if len(idx) < 300:
                continue
            k = int(rng.integers(252, max(253, len(idx) - 252)))
            sv = np.zeros(T)
            sv[idx] = np.roll(Sv0[idx, j], k)   # 그 열의 유효한 날 안에서만 밀어 빈 날을 섞지 않는다
            prod = sv * Xv0[:, j]
            o = sv != 0
            tot += prod.sum(); cnt += o.sum()
            h1 += prod[split].sum(); c1 += o[split].sum()
            h2 += prod[~split].sum(); c2 += o[~split].sum()
        if cnt:
            pl.append(tot / cnt)
            pl_h.append((h1 / c1 if c1 else np.nan, h2 / c2 if c2 else np.nan))
    pl = np.array(pl)
    mu = float(pl.mean())
    p = float(((np.abs(pl - mu) >= abs(edge - mu)).sum() + 1) / (len(pl) + 1))
    mh = np.nanmean(np.array(pl_h), axis=0)
    stable = bool(all((not np.isnan(a)) and np.sign(a - b) == expect for a, b in zip(halves, mh)))
    return {"name": name, "group": group, "h": horizon, "cols": len(cols), "n_on": n_on, "share_on": float(n_on / valid.sum()),
            "edge": edge, "placebo": mu, "excess_edge": edge - mu, "hit": hit, "p": p,
            "first_half": halves[0] - float(mh[0]), "second_half": halves[1] - float(mh[1]), "stable": stable,
            "right_way": bool(np.sign(edge - mu) == expect)}


def holm(rows):
    rs = sorted([r for r in rows if "p" in r], key=lambda r: r["p"])
    m = len(rs)
    alive = True
    for i, r in enumerate(rs):
        thr = ALPHA / (m - i)
        alive = alive and r["p"] < thr
        r["holm_thr"] = thr
        r["pass"] = bool(alive and r["right_way"] and r["stable"])
    return rows


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rng = np.random.default_rng(SEED)
    t0 = time.time()
    ours = [c[0] for c in U.CANDIDATES]
    mk = frames(["SPY", "_VIX"] + sorted({U.sector_etf(s)[0] for s in ours}), fetch=False)
    spy, vix = mk["SPY"]["close"], mk["_VIX"]["close"]
    etfs = {k: v["close"] for k, v in mk.items() if k not in ("SPY", "_VIX")}
    our = frames(ours)
    C = pd.DataFrame({s: d["close"] for s, d in our.items()}).sort_index()
    C = C.loc[C.index.isin(spy.index)]
    spy = spy.reindex(C.index.union(spy.index)).loc[spy.index]
    print(f"[valid] 우리 종목 {C.shape[1]}/{len(ours)} · {C.index.min().date()}~{C.index.max().date()}")

    def excess(Cx, h):
        return fwd(Cx, h).sub(fwd(spy, h).reindex(Cx.index), axis=0)

    rows = []
    # 시장 신호 — S&P 500 자체 수익
    rows.append(test(sig_regime(spy, vix), fwd(spy, 5), "증시 분위기", 5, "시장", rng))
    rows.append(test(sig_shock(spy, vix), fwd(spy, 5), "시장 충격", 5, "시장", rng))
    # 우리 64종목
    X5, X21, X63 = excess(C, 5), excess(C, 21), excess(C, 63)
    print(f"[valid] 기술지표 계산 중 ({time.time() - t0:.0f}s)")
    T = pd.DataFrame({s: sig_tech(our[s].loc[our[s].index.isin(C.index)]) for s in C.columns}).reindex(C.index)
    print(f"[valid] 기술지표 끝 ({time.time() - t0:.0f}s)")
    rows.append(test(T, X5, "기술지표 방향", 5, "우리 종목", rng))
    rows.append(test(sig_overheat(C), X5, "과열 신호", 5, "우리 종목", rng))
    rows.append(test(sig_sector(C, etfs, spy), X5, "업계 자금 흐름", 5, "우리 종목", rng))
    for h, X in ((21, X21), (63, X63)):
        rows.append(test(sig_ma(C), X, "평균선 대비", h, "우리 종목", rng))
        rows.append(test(sig_momentum(C), X, "12개월 모멘텀", h, "우리 종목", rng))
    holm([r for r in rows])
    # 바깥 확인 — 30년 저장소 전체 (보정 묶음은 따로)
    allsyms = sorted(f[:-8] for f in os.listdir(STORE) if f.endswith(".parquet") and not f.startswith("_") and f[:-8] not in etfs and f[:-8] != "SPY")
    A = pd.DataFrame({s: d["close"] for s in allsyms if (d := _load(s)) is not None and len(d)}).sort_index()
    A = A.loc[A.index.isin(spy.index)]
    print(f"[valid] 저장소 전체 {A.shape[1]}종목 ({time.time() - t0:.0f}s)")
    ext = []
    ext.append(test(sig_overheat(A), excess(A, 5), "과열 신호", 5, "저장소 전체", rng))
    for h in (21, 63):
        XA = excess(A, h)
        ext.append(test(sig_ma(A), XA, "평균선 대비", h, "저장소 전체", rng))
        ext.append(test(sig_momentum(A, min_n=50), XA, "12개월 모멘텀", h, "저장소 전체", rng))
    holm(ext)
    for r in rows + ext:
        if "p" in r:
            print(f"[{r['group']}] {r['name']} {r['h']}일: edge {r['excess_edge']:+.3f}%p (플라시보 대비) 맞힘 {r['hit'] * 100:.1f}% p={r['p']:.3f} "
                  f"앞 {r['first_half']:+.3f} 뒤 {r['second_half']:+.3f} → {'통과' if r['pass'] else '탈락'}")
        else:
            print(f"[{r['group']}] {r['name']} {r['h']}일: {r.get('note')}")
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"built": time.strftime("%Y-%m-%d"), "seed": SEED, "n_placebo": N_PL, "ours": rows, "external": ext}, f, ensure_ascii=False, indent=1)
    print(f"[valid] 끝 {time.time() - t0:.0f}s → {OUT_JSON}")


if __name__ == "__main__":
    main()
