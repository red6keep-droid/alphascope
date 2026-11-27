"""업종 안 순위 검증 — 가장 강한 종목 · 조건이 깨진 뒤 · 덜 오른 종목.

    .venv/bin/python experiments/issue_store/sector_rank_check.py                     # 지금 종목만(1차) → results/sector_rank_check.md
    .venv/bin/python experiments/issue_store/sector_rank_check.py --removed           # + 2016 뒤 제외 94종목(removed_sectors.csv)
    .venv/bin/python experiments/issue_store/sector_rank_check.py --start 2016 [--removed]   # 쏠림 재기: 제외 목록이 다 있는 기간

설계는 결과 보기 전에 비공개 doc/검증/업종-안-순위-검증.md 에 고정했다.
"""
import os

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BARS = os.path.join(ROOT, "data", "store", "bars")
OUT = os.path.join(os.path.dirname(__file__), "results")
import sys  # noqa: E402
WITH_REMOVED = "--removed" in sys.argv
_y = sys.argv[sys.argv.index("--start") + 1] if "--start" in sys.argv else "1999"
START = pd.Timestamp(f"{_y}-01-01")
SPLIT = pd.Timestamp("2013-01-01") if _y == "1999" else START + (pd.Timestamp("2026-10-16") - START) / 2
TAG = ("" if _y == "1999" else f"_{_y}") + ("_removed" if WITH_REMOVED else "")
N_PL, N_BOOT, MIN_N, SEED = 1000, 2000, 8, 20261122
KO = {"Industrials": "산업재", "Financials": "금융", "Information Technology": "기술", "Health Care": "헬스케어",
      "Consumer Discretionary": "경기 소비재", "Consumer Staples": "필수 소비재", "Utilities": "유틸리티",
      "Real Estate": "부동산", "Materials": "소재", "Communication Services": "커뮤니케이션", "Energy": "에너지"}
SIGS = {"r63": "63일 수익", "r126": "126일 수익", "mom": "12-1 모멘텀", "hi52": "52주 최고가 위치"}


def load():
    u = pd.read_csv(os.path.join(ROOT, "backtest", "data", "universe.csv"))
    sector = {s.replace(".", "-"): KO[sec] for s, sec in zip(u.symbol, u.sector)}
    if WITH_REMOVED:
        r = pd.read_csv(os.path.join(os.path.dirname(__file__), "removed_sectors.csv"))
        sector.update({s.replace(".", "-"): sec for s, sec in zip(r.symbol, r.sector)})
    px = {}
    for s in sector:
        p = os.path.join(BARS, f"{s}.parquet")
        if os.path.exists(p):
            c = pd.read_parquet(p)["close"]
            c.index = pd.to_datetime(c.index).tz_localize(None).normalize()
            c = c[c > 0]
            px[s] = c[~c.index.duplicated()]
    px = pd.DataFrame(px).sort_index()
    px = px[px.index >= "1997-06-01"]
    px = px[px.notna().sum(axis=1) > 100]
    comp = pd.read_csv(os.path.join(ROOT, "data", "store", "calendar", "sp500_components.csv"), parse_dates=["date"])
    comp = comp.set_index("date").tickers.sort_index()
    total = pd.Series(0, index=px.index)
    mem = pd.DataFrame(False, index=px.index, columns=px.columns)
    pos = comp.index.searchsorted(px.index, side="right") - 1
    cache = {}
    for i, d in enumerate(px.index):
        k = pos[i]
        if k < 0:
            continue
        if k not in cache:
            t = comp.iloc[k].split(",")
            cache[k] = (px.columns.isin([x.replace(".", "-") for x in t]), len(t))
        mem.iloc[i] = cache[k][0]
        total.iloc[i] = cache[k][1]
    return px, mem, pd.Series(sector).reindex(px.columns), total


def pl_p(obs, pl):
    pl = np.asarray(pl)
    return (np.sum(np.abs(pl - pl.mean()) >= abs(obs - pl.mean())) + 1) / (len(pl) + 1)


def cell(rows, rng, picker, k):
    """rows = [(date, sig배열, 초과수익 배열)], picker(sig, k) → 고른 자리. 관측 평균 · 플라시보 p · 앞뒤."""
    if len(rows) < 30:
        return None
    dates = pd.DatetimeIndex([r[0] for r in rows])
    obs = np.array([ex[picker(sg, k)].mean() for _, sg, ex in rows])
    pl = np.zeros((N_PL, len(rows)))
    for j, (_, sg, ex) in enumerate(rows):
        idx = np.argsort(rng.random((N_PL, len(ex))), axis=1)[:, :k]
        pl[:, j] = ex[idx].mean(axis=1)
    a, b = dates < SPLIT, dates >= SPLIT
    return {"n": len(rows), "mean": obs.mean() * 100, "hit": (obs > 0).mean() * 100, "p": pl_p(obs.mean(), pl.mean(axis=1)),
            "a": obs[a].mean() * 100 if a.sum() else np.nan, "b": obs[b].mean() * 100 if b.sum() else np.nan,
            "na": int(a.sum()), "nb": int(b.sum()),
            "pa": pl_p(obs[a].mean(), pl[:, a].mean(axis=1)) if a.sum() >= 15 else np.nan,
            "pb": pl_p(obs[b].mean(), pl[:, b].mean(axis=1)) if b.sum() >= 15 else np.nan}


def top(sg, k):
    return np.argsort(sg)[-k:]


def bot(sg, k):
    return np.argsort(sg)[:k]


def bh(ps, q=0.05):
    ps = np.asarray(ps, float)
    o = np.argsort(ps)
    ok = np.zeros(len(ps), bool)
    thr = q * (np.arange(1, len(ps) + 1)) / len(ps)
    passed = np.where(ps[o] <= thr)[0]
    if len(passed):
        ok[o[:passed.max() + 1]] = True
    return ok


def main():
    rng = np.random.default_rng(SEED)
    px, mem, sector, total = load()
    lag = []   # (날짜, 그날 자료 비율, 업종 63일 꼴찌의 뒤 20일 초과) — 쏠림 크기 재기
    sig = {"r63": px / px.shift(63) - 1, "r126": px / px.shift(126) - 1, "mom": px.shift(21) / px.shift(252) - 1,
           "hi52": px / px.rolling(252, min_periods=200).max()}
    days = px.index[px.index >= START]
    i0 = px.index.get_loc(days[0])
    secs = sorted(set(sector.dropna()))
    cols = {s: np.where(sector.values == s)[0] for s in secs}
    P, M = px.to_numpy(), mem.to_numpy()
    S = {k: v.to_numpy() for k, v in sig.items()}
    out = []
    print(f"종목 {px.shape[1]} · 거래일 {len(days)} ({days[0].date()}~{days[-1].date()})")

    hot_rank = {}   # 날짜 자리 → 업종 순위(63일 수익 평균)
    for h in (20, 60):
        form = list(range(i0, len(px) - h, h))
        fwd = {i: P[i + h] / P[i] - 1 for i in form}
        # ── Q1 · Q3: 업종 안 순위
        rows = {(sg, s): [] for sg in SIGS for s in secs}
        rows_hot = {(sg, tag): [] for sg in ("r63", "r126") for tag in ("hot", "rest")}
        sec_rows = []
        for i in form:
            f = fwd[i]
            okall = M[i] & ~np.isnan(f) & ~np.isnan(S["r63"][i])
            sc = {s: np.nanmean(S["r63"][i][cols[s]][okall[cols[s]]]) for s in secs if okall[cols[s]].sum() >= MIN_N}
            order = sorted(sc, key=sc.get, reverse=True)
            hot_rank[i] = order
            if len(order) >= 8:
                mkt = f[okall].mean()
                sec_rows.append((px.index[i], np.array([sc[s] for s in order]),
                                 np.array([f[cols[s]][okall[cols[s]]].mean() - mkt for s in order])))
            for s in secs:
                c = cols[s]
                for sg in SIGS:
                    ok = M[i][c] & ~np.isnan(f[c]) & ~np.isnan(S[sg][i][c])
                    if ok.sum() < MIN_N:
                        continue
                    ex = f[c][ok] - f[c][ok].mean()
                    r = (px.index[i], S[sg][i][c][ok], ex)
                    rows[(sg, s)].append(r)
                    if sg == "r63" and h == 20:
                        lag.append((px.index[i], M[i].sum() / max(total.iloc[i], 1), ex[np.argmin(S[sg][i][c][ok])], ex[np.argmax(S[sg][i][c][ok])]))
                    if sg in ("r63", "r126") and s in order:
                        rows_hot[(sg, "hot" if order.index(s) < 3 else "rest")].append(r)
        for (sg, s), rr in rows.items():
            for name, pk, k in (("1위", top, 1), ("상위 3", top, 3), ("꼴찌", bot, 1), ("하위 3", bot, 3)):
                if name in ("꼴찌", "하위 3") and sg not in ("r63", "r126"):
                    continue
                r = cell(rr, rng, pk, k)
                if r:
                    out.append({"q": "Q1" if pk is top else "Q3", "h": h, "sig": sg, "pick": name, "sector": s, **r})
        for sg in SIGS:   # 전 업종 합침(참고): 날짜마다 업종 평균이 아니라 칸을 그대로 이어 붙임
            allr = [r for s in secs for r in rows[(sg, s)]]
            for name, pk, k in (("1위", top, 1), ("상위 3", top, 3), ("꼴찌", bot, 1), ("하위 3", bot, 3)):
                if name in ("꼴찌", "하위 3") and sg not in ("r63", "r126"):
                    continue
                r = cell(allr, rng, pk, k)
                out.append({"q": "Q1" if pk is top else "Q3", "h": h, "sig": sg, "pick": name, "sector": "전 업종(참고)", **r})
        for (sg, tag), rr in rows_hot.items():
            for name, pk, k in (("꼴찌", bot, 1), ("하위 3", bot, 3), ("1위", top, 1)):
                r = cell(rr, rng, pk, k)
                out.append({"q": "Q3h", "h": h, "sig": sg, "pick": name, "sector": "뜨거운 업종(1~3위) 안" if tag == "hot" else "그 밖 업종 안", **r})
        # ── Q1-b: 뜨거운 업종
        for name, pk in (("1위 업종", lambda sg, k: np.array([0])), ("꼴찌 업종", lambda sg, k: np.array([len(sg) - 1]))):
            r = cell(sec_rows, rng, pk, 1)
            out.append({"q": "Q1b", "h": h, "sig": "r63", "pick": name, "sector": "업종 11개", **r})

    # ── Q2: 조건이 깨진 뒤
    H2, TRACK = 20, 60
    ma50 = px.rolling(50, min_periods=50).mean().to_numpy()
    f20 = np.full_like(P, np.nan)
    f20[:-H2] = P[H2:] / P[:-H2] - 1
    secmean = np.full_like(P, np.nan)      # 그날 그 종목 업종의 뒤 20일 평균(편입 종목)
    for s in secs:
        c = cols[s]
        x = np.where(M[:, c], f20[:, c], np.nan)
        with np.errstate(all="ignore"):
            secmean[:, c] = np.nanmean(x, axis=1)[:, None]
    ex20 = f20 - secmean
    q2 = []
    form = list(range(i0, len(px) - TRACK - H2, 20))
    for brk in ("B1", "B2"):
        ev = []   # (날짜 자리, 깨짐 여부, 초과수익)
        for i in form:
            for s in secs:
                c = cols[s]
                ok = M[i][c] & ~np.isnan(S["r63"][i][c])
                if ok.sum() < MIN_N:
                    continue
                cc = c[ok][np.argsort(S["r63"][i][c][ok])[-3:]]
                for j in cc:
                    if not (P[i, j] > ma50[i, j]):
                        continue
                    peak, broke = P[i, j], False
                    for d in range(i + 1, i + TRACK + 1):
                        if np.isnan(P[d, j]):
                            break
                        peak = max(peak, P[d, j])
                        hit = P[d, j] < ma50[d, j] if brk == "B1" else P[d, j] <= peak * 0.9
                        if hit:
                            if not np.isnan(ex20[d, j]):
                                ev.append((d, 1, ex20[d, j]))
                            broke = True
                            break
                        if (d - i) % 5 == 0 and not np.isnan(ex20[d, j]):   # 유지 중인 날은 5거래일마다 하나
                            ev.append((d, 0, ex20[d, j]))
        e = pd.DataFrame(ev, columns=["i", "brk", "ex"])
        e["date"] = px.index[e.i.values]
        e["ym"] = e.date.dt.to_period("M")

        def diff(d):
            return d.ex[d.brk == 1].mean() - d.ex[d.brk == 0].mean()
        res = {"brk": brk, "n_brk": int(e.brk.sum()), "n_hold": int((e.brk == 0).sum()),
               "brk_mean": e.ex[e.brk == 1].mean() * 100, "hold_mean": e.ex[e.brk == 0].mean() * 100,
               "brk_hit": (e.ex[e.brk == 1] > 0).mean() * 100, "hold_hit": (e.ex[e.brk == 0] > 0).mean() * 100,
               "diff": diff(e) * 100, "a": diff(e[e.date < SPLIT]) * 100, "b": diff(e[e.date >= SPLIT]) * 100}
        groups = [g for _, g in e.groupby("ym")]
        bs = []
        for _ in range(N_BOOT):
            pick = rng.integers(0, len(groups), len(groups))
            bs.append(diff(pd.concat([groups[k] for k in pick])))
        bs = np.array(bs) * 100
        res["lo"], res["hi"] = np.percentile(bs, [2.5, 97.5])
        res["p"] = min(1.0, 2 * min((bs <= 0).mean(), (bs >= 0).mean()) + 1 / N_BOOT)
        q2.append(res)
        print(brk, {k: (round(v, 2) if isinstance(v, float) else v) for k, v in res.items()})

    df = pd.DataFrame(out)
    os.makedirs(OUT, exist_ok=True)
    df.to_csv(os.path.join(OUT, f"sector_rank_check{TAG}.csv"), index=False)
    pd.DataFrame(q2).to_csv(os.path.join(OUT, f"sector_rank_check{TAG}_break.csv"), index=False)
    lg = pd.DataFrame(lag, columns=["date", "cov", "lag", "lead"])
    lg["era"] = (lg.date.dt.year - 1999) // 3 * 3 + 1999
    era = lg.groupby("era").agg(cov=("cov", "mean"), lag=("lag", "mean"), lead=("lead", "mean"), n=("lag", "size"))
    era.to_csv(os.path.join(OUT, f"sector_rank_check{TAG}_era.csv"))
    write_md(df, q2, px, days, era)


def verdict(r, bh_ok=None):
    same = np.sign(r["a"]) == np.sign(r["b"]) == np.sign(r["mean"])
    sig_ok = (r["p"] < 0.05) if bh_ok is None else bh_ok
    if sig_ok and same:
        return "**이어짐**" if r["mean"] > 0 else "**거꾸로**"
    if r["p"] < 0.05 and not same:
        return "시기마다 다름"
    return "차이 없음"


def fmt(r, v):
    return (f"| {r['sector']} | {r['n']} | {r['mean']:+.2f} | {r['hit']:.0f}% | {r['p']:.3f} | "
            f"{r['a']:+.2f} ({r['na']}) | {r['b']:+.2f} ({r['nb']}) | {v} |")


HEAD = ["| 업종 | 고른 횟수 | 업종 평균 대비 %p | 업종 평균 이긴 비율 | p | 앞 시기 (횟수) | 뒤 시기 (횟수) | 판정 |", "|---|---|---|---|---|---|---|---|"]


def write_md(df, q2, px, days, era):
    L = [f"# 업종 안 순위 검증 결과 (2026-11-22){' · 2016 뒤 제외 종목 포함' if WITH_REMOVED else ''}", "",
         f"앞 · 뒤 시기 경계 {SPLIT.date()}.",
         f"자료: {'지금 S&P 500 + 2016 뒤 제외 종목' if WITH_REMOVED else '지금 S&P 500'} {px.shape[1]}종목 · {days[0].date()} ~ {days[-1].date()} · 그날 편입 종목만. 생존 편향 있음(편입 제외 종목은 업종 표가 없어 빠짐).",
         "값 = 고른 종목의 뒤 수익 − 같은 업종 평균(%p). p = 같은 날 같은 업종 아무 종목 1,000회.", ""]
    main_ = df[(df.q == "Q1") & (df.sig == "r63") & (df.pick == "1위") & (df.sector != "전 업종(참고)")].copy()
    main_["bh"] = bh(main_.p.values)
    L += ["## Q1 주 규칙 — 63일 수익 업종 1위 (22칸 BH 보정)", ""]
    for h in (20, 60):
        L += [f"### 뒤 {h}거래일", ""] + HEAD
        for _, r in main_[main_.h == h].iterrows():
            L.append(fmt(r, verdict(r, r.bh)))
        r = df[(df.q == "Q1") & (df.sig == "r63") & (df.pick == "1위") & (df.sector == "전 업종(참고)") & (df.h == h)].iloc[0]
        L += [fmt(r, verdict(r)), ""]
    L += ["## Q1 참고 — 다른 자 · 상위 3 (전 업종 합침과 업종별 판정 수)", "",
          "| 자 | 고르는 수 | 창 | 전 업종 %p | p | 앞 | 뒤 | 업종 11개 중 이어짐 / 거꾸로 (p<.05 · 앞뒤 같은 방향, 보정 전) |", "|---|---|---|---|---|---|---|---|"]
    for (sg, pick, h), g in df[df.q == "Q1"].groupby(["sig", "pick", "h"], sort=False):
        a = g[g.sector == "전 업종(참고)"].iloc[0]
        ind = g[g.sector != "전 업종(참고)"]
        vs = [verdict(r) for _, r in ind.iterrows()]
        L.append(f"| {SIGS[sg]} | {pick} | {h} | {a['mean']:+.2f} | {a['p']:.3f} | {a['a']:+.2f} | {a['b']:+.2f} | {vs.count('**이어짐**')} / {vs.count('**거꾸로**')} |")
    L += ["", "## Q1-b 뜨거운 업종 (63일 수익 평균 1위 업종 · 값 = 업종 뒤 수익 − 전 종목 평균)", ""] + HEAD
    for _, r in df[df.q == "Q1b"].iterrows():
        r = r.copy()
        r["sector"] = f"{r['pick']} · 뒤 {r['h']}일"
        L.append(fmt(r, verdict(r)))
    L += ["", "## Q2 조건이 깨진 뒤 (업종 안 63일 수익 상위 3 · 뒤 60거래일 추적 · 값 = 뒤 20거래일 수익 − 업종 평균)", "",
          "| 깨짐 | 깨진 횟수 | 깨진 뒤 %p | 이긴 비율 | 유지 중 표본 | 유지 중 %p | 이긴 비율 | 차이 %p (95% 구간) | p | 앞 | 뒤 | 판정 |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    nm = {"B1": "50일선 아래로", "B2": "고른 뒤 최고가에서 −10%"}
    for r in q2:
        same = np.sign(r["a"]) == np.sign(r["b"]) == np.sign(r["diff"])
        v = ("**깨진 뒤 더 약함**" if r["diff"] < 0 else "**깨진 뒤 더 강함**") if (r["p"] < 0.05 and same) else ("시기마다 다름" if r["p"] < 0.05 else "차이 없음")
        L.append(f"| {nm[r['brk']]} | {r['n_brk']} | {r['brk_mean']:+.2f} | {r['brk_hit']:.0f}% | {r['n_hold']} | {r['hold_mean']:+.2f} | {r['hold_hit']:.0f}% | "
                 f"{r['diff']:+.2f} ({r['lo']:+.2f} ~ {r['hi']:+.2f}) | {r['p']:.3f} | {r['a']:+.2f} | {r['b']:+.2f} | {v} |")
    L += ["", "## Q3 덜 오른 종목 (업종 꼴찌 · 하위 3)", ""]
    for sg in ("r63", "r126"):
        for pick in ("꼴찌", "하위 3"):
            for h in (20, 60):
                g = df[(df.q == "Q3") & (df.sig == sg) & (df.pick == pick) & (df.h == h)]
                L += [f"### {SIGS[sg]} {pick} · 뒤 {h}거래일", ""] + HEAD
                for _, r in g.iterrows():
                    L.append(fmt(r, verdict(r)))
                L.append("")
    L += ["### 뜨거운 업종 안으로 좁힘", "", "| 묶음 | 자 | 고르는 수 | 창 | 횟수 | 업종 평균 대비 %p | 이긴 비율 | p | 앞 | 뒤 | 판정 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in df[df.q == "Q3h"].iterrows():
        L.append(f"| {r['sector']} | {SIGS[r['sig']]} | {r['pick']} | {r['h']} | {r['n']} | {r['mean']:+.2f} | {r['hit']:.0f}% | {r['p']:.3f} | {r['a']:+.2f} | {r['b']:+.2f} | {verdict(r)} |")
    L += ["", "## 쏠림 재기 — 3년마다 자료 비율과 업종 꼴찌 · 1위의 뒤 20일 (업종 평균 대비 %p)", "",
          "| 시기 | 편입 종목 중 표에 있는 비율 | 꼴찌 | 1위 | 칸 수 |", "|---|---|---|---|---|"]
    for y, r in era.iterrows():
        L.append(f"| {y}~{y + 2} | {r['cov'] * 100:.0f}% | {r['lag'] * 100:+.2f} | {r['lead'] * 100:+.2f} | {int(r['n'])} |")
    open(os.path.join(OUT, f"sector_rank_check{TAG}.md"), "w").write("\n".join(L) + "\n")
    print(f"→ results/sector_rank_check{TAG}.md")


if __name__ == "__main__":
    main()
