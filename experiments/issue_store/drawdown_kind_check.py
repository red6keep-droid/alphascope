"""하락의 종류 검증 V1 ~ V6 — 고점 대비 −10% 넘게 빠진 하락이 시작된 날(가르는 날)의 조건으로 갈라,
그 뒤 더 깊고 길었나를 본다. 기준은 비공개 doc/기획/거시-흐름-지도.md 5-1 절에 결과 보기 전 고정.

    .venv/bin/python experiments/issue_store/drawdowns.py          # 하락 목록 먼저
    .venv/bin/python experiments/issue_store/drawdown_kind_check.py

자료: data/store/drawdowns/_GSPC.csv · _KS11.csv, data/store/bars(일봉), data/store/fred
(IC4WSA · UNRATE · USREC = fetch_macro_history.py, DGS10_long · BAA10Y_long = fetch_fred_daily.fetch 로 전 기간).
결과: experiments/issue_store/results/drawdown_kind.md · drawdown_kind_cases.csv (깃 밖).
"""
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from normal_range import load_close  # noqa: E402

ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
FRED = os.path.join(ROOT, "data", "store", "fred")
DD = os.path.join(ROOT, "data", "store", "drawdowns")
OUT = os.path.join(_HERE, "results")
HS = (20, 60, 120)
NPERM = 2000
SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
rng = np.random.default_rng(20261128)


def fred_raw(sid):
    d = pd.read_csv(os.path.join(FRED, f"{sid}.csv"))
    s = pd.Series(d["value"].astype(float).values, pd.to_datetime(d["day"]))
    return s[~s.index.duplicated()].sort_index()


def on_index(s, idx):
    first = s.index[0]
    out = s.reindex(s.index.union(idx)).ffill(limit=5).reindex(idx)
    out[out.index < first] = np.nan
    return out


def known(s, day, lag):
    """day 에 발표돼 있던 값들 — 관측 날짜 + lag 일 ≤ day."""
    return s[s.index + pd.Timedelta(days=lag) <= day]


# ---------- 조건 (5-1 절 그대로) ----------
def v1_claims(day, ic):
    k = known(ic, day, 5)
    if len(k) == 0 or k.index[-1] - k.index[0] < pd.Timedelta(days=364):
        return None
    last = k.iloc[-1]
    low = k[k.index > k.index[-1] - pd.Timedelta(days=364)].min()
    return bool(last > low * 1.15)


def v1_unrate(day, ur):
    k = known(ur, day, 35)
    if len(k) < 12:
        return None
    return bool(k.iloc[-3:].mean() - k.iloc[-12:].min() > 0.3)


def v2_baa(x, baa):
    if x < 61 or np.isnan(baa.iloc[x - 1]) or np.isnan(baa.iloc[x - 61]):
        return None
    return bool(baa.iloc[x - 1] - baa.iloc[x - 61] >= 0.20)


def v2_hy(x, chg, cut):
    v = chg.iloc[x]
    return None if np.isnan(v) else bool(v < cut)


def v3_rate(x, d10):
    if x < 121 or np.isnan(d10.iloc[x - 1]) or np.isnan(d10.iloc[x - 121]):
        return None
    return bool(d10.iloc[x - 1] - d10.iloc[x - 121] > 0)


def v4_broad(day, sec):
    n = 0
    for c in sec.values():
        k = c[c.index <= day]
        if len(k) < 252 or day - k.index[-1] > pd.Timedelta(days=7):   # 업종 일봉이 그날까지 없으면 모름
            return None
        if k.iloc[-1] / k.iloc[-252:].max() - 1 < -0.10:
            n += 1
    return bool(n >= 6)


def v5_us(day, spx):
    k = spx[spx.index < day]   # 한국 장이 닫힐 때 아는 미국 = 전날 밤 종가
    if len(k) < 252:
        return None
    return bool(k.iloc[-1] / k.iloc[-252:].max() - 1 < -0.10)


# ---------- 결과 ----------
def outcomes(dd, c):
    rows = []
    for _, r in dd.iterrows():
        cross = pd.Timestamp(r["cross"])
        x = c.index.get_indexer([cross])[0]
        row = {"peak": r["peak"], "cross": r["cross"], "trough": r["trough"], "x": x,
               "depth": r["depth"], "more": r["cross_to_trough"], "days": r["d_cross_trough"],
               "open": r["end"] == "진행 중"}
        row["deep"] = r["cross_to_trough"] < -0.10
        row["long"] = r["d_cross_trough"] > 60
        for h in HS:
            row[f"r{h}"] = c.iloc[x + h] / c.iloc[x] - 1 if x + h < len(c) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def md_table(df):
    def f(v):
        if isinstance(v, float):
            return "" if np.isnan(v) else f"{v:.3f}"
        return "" if v is None else str(v)
    head = "| " + " | ".join(df.columns) + " |\n|" + "---|" * len(df.columns)
    return head + "\n" + "\n".join("| " + " | ".join(f(v) for v in r) + " |" for r in df.itertuples(index=False))


def perm_p(on, vals, stat):
    """켜짐 · 꺼짐 표지를 하락끼리 섞어 stat(켜짐) − stat(꺼짐) 차이의 양쪽 p."""
    ok = ~pd.isna(vals)
    on, vals = on[ok], vals[ok].astype(float)
    if on.sum() == 0 or (~on).sum() == 0:
        return np.nan, np.nan
    obs = stat(vals[on]) - stat(vals[~on])
    cnt = 0
    for _ in range(NPERM):
        p = rng.permutation(on)
        if abs(stat(vals[p]) - stat(vals[~p])) >= abs(obs) - 1e-12:
            cnt += 1
    return obs, (cnt + 1) / (NPERM + 1)


def summarize(name, label, df, col):
    d = df[df[col].notna() & ~df["open"]].copy()
    on = d[col].astype(bool).values
    out = {"조건": name, "자": label, "하락 수": len(d), "켜짐": int(on.sum()), "꺼짐": int((~on).sum()),
           "기간": f"{d['cross'].iloc[0][:4]} ~ {d['cross'].iloc[-1][:4]}" if len(d) else ""}
    for k in ("deep", "long"):
        v = d[k].astype(float).values
        out[f"{k} 켜짐"] = f"{int(v[on].sum())}/{on.sum()}"
        out[f"{k} 꺼짐"] = f"{int(v[~on].sum())}/{(~on).sum()}"
        out[f"{k} p"] = perm_p(on, v, np.mean)[1]
    for h in HS:
        v = d[f"r{h}"].values
        okv = ~np.isnan(v)
        out[f"r{h} 켜짐"] = np.nanmedian(v[on & okv]) if (on & okv).any() else np.nan
        out[f"r{h} 꺼짐"] = np.nanmedian(v[~on & okv]) if (~on & okv).any() else np.nan
        out[f"r{h} p"] = perm_p(on, v, np.median)[1]
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    spx = load_close("^GSPC")
    ks = load_close("^KS11")
    ic, ur, rec = fred_raw("IC4WSA"), fred_raw("UNRATE"), fred_raw("USREC")
    baa = on_index(fred_raw("BAA10Y_long"), spx.index)
    d10 = on_index(fred_raw("DGS10_long"), spx.index)
    ratio = (load_close("HYG") / load_close("IEI")).dropna()
    ratio = ratio.reindex(spx.index)
    chg = ratio / ratio.shift(60) - 1
    hy_cut = chg.dropna().quantile(0.20)
    sec = {s: load_close(s) for s in SECTORS}

    us = outcomes(pd.read_csv(os.path.join(DD, "_GSPC.csv")), spx)
    for i, r in us.iterrows():
        day, x = pd.Timestamp(r["cross"]), int(r["x"])
        us.loc[i, "V1"] = v1_claims(day, ic)
        us.loc[i, "V1'"] = v1_unrate(day, ur)
        us.loc[i, "V2"] = v2_baa(x, baa)
        us.loc[i, "V2'"] = v2_hy(x, chg, hy_cut)
        us.loc[i, "V3"] = v3_rate(x, d10)
        us.loc[i, "V4"] = v4_broad(day, sec)
        pk, tr = pd.Timestamp(r["peak"]), pd.Timestamp(r["trough"])
        months = rec[(rec.index >= pk.to_period("M").to_timestamp()) & (rec.index <= tr)]
        us.loc[i, "침체(사후)"] = bool((months == 1).any())
    kr = outcomes(pd.read_csv(os.path.join(DD, "_KS11.csv")), ks)
    for i, r in kr.iterrows():
        kr.loc[i, "V5"] = v5_us(pd.Timestamp(r["cross"]), spx)

    conds = [("V1 실업수당 4주 평균 > 52주 최저 × 1.15", "S&P 500", us, "V1"),
             ("V1' 실업률 3개월 평균 − 12개월 최저 > 0.3%p", "S&P 500", us, "V1'"),
             ("V2 Baa 가산금리 60일 +0.20%p 이상", "S&P 500", us, "V2"),
             ("V2' 하이일드 대리 60일 변화 아래 20%", "S&P 500", us, "V2'"),
             ("V3 10년물 120일 변화 > 0", "S&P 500", us, "V3"),
             ("V4 업종 ETF 9개 중 6개 이상 −10% 아래", "S&P 500", us, "V4"),
             ("V5 미국도 52주 고점 −10% 아래 (코스피 하락)", "코스피", kr, "V5"),
             ("(사후 대조) 침체 달이 낀 하락", "S&P 500", us, "침체(사후)")]
    summ = pd.DataFrame([summarize(n, l, d, c) for n, l, d, c in conds])

    base = {}
    for lab, d in (("S&P 500", us), ("코스피", kr)):
        dd = d[~d["open"]]
        base[lab] = (f"하락 {len(dd)}개 · 깊음 {int(dd['deep'].sum())} · 김 {int(dd['long'].sum())} · "
                     + " · ".join(f"{h}일 중앙 {np.nanmedian(dd[f'r{h}']) * 100:+.1f}%" for h in HS))

    agree = us[us["V1"].notna() & ~us["open"]]
    v1_vs_rec = pd.crosstab(agree["V1"].astype(bool), agree["침체(사후)"].astype(bool))

    pct = lambda v: "" if pd.isna(v) else f"{v * 100:+.1f}%"
    pf = lambda v: "" if pd.isna(v) else f"{v:.3f}"
    lines = ["# 하락의 종류 V1 ~ V6", "", f"자료 끝: S&P 500 {spx.index[-1].date()} · 코스피 {ks.index[-1].date()}",
             f"하이일드 대리 아래 20% 선 = 60일 변화 {hy_cut * 100:.2f}%", ""]
    for k, v in base.items():
        lines.append(f"- 바탕 {k}: {v}")
    lines += ["", "| 조건 | 자 | 기간 | 하락 | 켜짐 | 깊음 켜짐 | 깊음 꺼짐 | p | 김 켜짐 | 김 꺼짐 | p | 20일 켜짐 | 꺼짐 | p | 60일 켜짐 | 꺼짐 | p | 120일 켜짐 | 꺼짐 | p |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, s in summ.iterrows():
        lines.append(f"| {s['조건']} | {s['자']} | {s['기간']} | {s['하락 수']} | {s['켜짐']} | {s['deep 켜짐']} | {s['deep 꺼짐']} | {pf(s['deep p'])} | "
                     f"{s['long 켜짐']} | {s['long 꺼짐']} | {pf(s['long p'])} | "
                     + " | ".join(f"{pct(s[f'r{h} 켜짐'])} | {pct(s[f'r{h} 꺼짐'])} | {pf(s[f'r{h} p'])}" for h in HS) + " |")
    lines += ["", "## V1 (그날 알 수 있던 실업수당) × 침체 달(사후)", "", "```", v1_vs_rec.to_string(), "```", "", "## 지금 진행 중인 하락", ""]
    for lab, d in (("S&P 500", us), ("코스피", kr)):
        o = d[d["open"]]
        for _, r in o.iterrows():
            flags = {c: r.get(c) for c in ("V1", "V1'", "V2", "V2'", "V3", "V4", "V5") if c in d.columns}
            lines.append(f"- {lab} 고점 {r['peak']} · 가르는 날 {r['cross']} · 지금까지 {r['depth'] * 100:.1f}% · 조건 {flags}")
    cols = ["peak", "cross", "trough", "depth", "more", "days", "deep", "long", "r20", "r60", "r120",
            "V1", "V1'", "V2", "V2'", "V3", "V4", "침체(사후)", "open"]
    lines += ["", "## 하락마다 (S&P 500)", "", md_table(us[cols]),
              "", "## 하락마다 (코스피)", "", md_table(kr[["peak", "cross", "trough", "depth", "more", "days", "deep", "long", "r20", "r60", "r120", "V5", "open"]])]
    with open(os.path.join(OUT, "drawdown_kind.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    pd.concat([us.assign(자="S&P 500"), kr.assign(자="코스피")]).to_csv(os.path.join(OUT, "drawdown_kind_cases.csv"), index=False)
    print("\n".join(lines[:20 + len(conds)]))


if __name__ == "__main__":
    main()
