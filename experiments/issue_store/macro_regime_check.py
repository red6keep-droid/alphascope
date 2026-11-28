"""금리 · 신용 국면 검증 — 상태 뒤 S&P 500 3 · 6개월, 끝난 때의 꺾임 신호, 금.

    .venv/bin/python experiments/issue_store/macro_regime_check.py

설계(결과 보기 전 고정): 비공개 doc/검증/금리-신용-국면-검증.md 1절.
- 상태(그날 값, 60거래일 변화): A1 실질금리 +0.45%p · A2 +0.25%p · B1 가산금리(BAA10Y) +0.35%p ·
  C1 A2 & 가산금리 +0.20%p · C2 A2 & 가산금리 +0.10%p 미만 · D1 10년 +0.55%p · D2 2년 +0.50%p.
- 결과 = 뒤 63 · 126거래일 수익률 · 창 안 최대 낙폭. 사건 = 63거래일 넘게 꺼졌다 켜진 첫날.
- 플라시보 = 서로 63거래일 넘게 떨어진 아무 날 2,000번 → 수익률 중앙값 양쪽 p. 앞뒤 절반 = 쓸 수 있는 기간 가운데 날.
- 끝난 때: 사건마다 252거래일 안 바닥 · 꺾임 신호 T1 ~ T5 가 바닥보다 며칠 먼저였나.
- 금: A1 · A2 뒤 금 63 · 126거래일 vs 금 아무 날, 연도별 금 · 실질금리 하루 상관.
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
OUT = os.path.join(_HERE, "results")
GAP = 63
HS = (63, 126)
NBOOT = 2000
rng = np.random.default_rng(20261128)


def fred(sid, idx):
    d = pd.read_csv(os.path.join(FRED, f"{sid}.csv"))
    s = pd.Series(d["value"].astype(float).values, pd.to_datetime(d["day"]))
    s = s[~s.index.duplicated()].sort_index()
    first = s.index[0]
    s = s.reindex(s.index.union(idx)).ffill(limit=5).reindex(idx)
    s[s.index < first] = np.nan
    return s


def episodes(sig):
    idx = np.where(sig.values)[0]
    out, last = [], -10 ** 9
    for i in idx:
        if i - last > GAP:
            out.append(i)
        last = i
    return np.array(out, dtype=int)


def spaced_random(k, valid):
    """서로 GAP 넘게 떨어진 아무 날 k개 — 섞은 순서대로 받아 기간 전체에 고르게(날짜순 앞에서 자르면 앞쪽 해에 쏠린다)."""
    picks = []
    for i in rng.permutation(valid):
        if all(abs(i - j) > GAP for j in picks):
            picks.append(i)
            if len(picks) >= k:
                break
    return np.array(picks)


def forward(c, h):
    v = c.values
    ret = np.full(len(v), np.nan)
    mdd = np.full(len(v), np.nan)
    for i in range(len(v) - h):
        w = v[i + 1:i + h + 1]
        ret[i] = w[-1] / v[i] - 1
        mdd[i] = w.min() / v[i] - 1
    return ret, mdd


def compare(name, sig, c, avail_from, h, label="S&P 500"):
    ret, mdd = forward(c, h)
    ok = (c.index >= avail_from) & ~np.isnan(ret)
    valid = np.where(ok)[0]
    ep = episodes(sig.fillna(False) & pd.Series(ok, c.index))
    ep = ep[ok[ep]]
    base_med = float(np.median(ret[valid]))
    base_up = float((ret[valid] > 0).mean())
    base_dd = float((mdd[valid] <= -0.10).mean())
    row = {"자": label, "상태": name, "창": h, "사건": len(ep), "아무 날 중앙값": base_med, "아무 날 상승 비율": base_up,
           "아무 날 낙폭≤−10%": base_dd}
    if len(ep) == 0:
        return row, ep, ret
    x = ret[ep]
    row.update({"중앙값": float(np.median(x)), "상승": int((x > 0).sum()), "상승 비율": float((x > 0).mean()),
                "낙폭≤−10%": int((mdd[ep] <= -0.10).sum()), "최악": float(x.min()), "최고": float(x.max())})
    boot = np.array([np.median(ret[spaced_random(len(ep), valid)]) for _ in range(NBOOT)])
    p = float(min(1.0, 2 * min((boot >= row["중앙값"]).mean(), (boot <= row["중앙값"]).mean())))
    mid = c.index[valid[len(valid) // 2]]
    halves = []
    for a, b in ((c.index[valid[0]], mid), (mid, c.index[-1] + pd.Timedelta(days=1))):
        e = ep[(c.index[ep] >= a) & (c.index[ep] < b)]
        v = valid[(c.index[valid] >= a) & (c.index[valid] < b)]
        halves.append(float(np.median(ret[e]) - np.median(ret[v])) if len(e) else np.nan)
    same = not any(np.isnan(halves)) and np.sign(halves[0]) == np.sign(halves[1]) and halves[0] != 0
    if len(ep) < 30:
        verdict = "표본 부족 — n번 중 m번"
    elif p < 0.05 and same:
        verdict = "더 약함 (통과)" if row["중앙값"] < base_med else "더 강함 (통과)"
    else:
        verdict = "차이 없음"
    row.update({"p": p, "앞 절반 차": halves[0], "뒤 절반 차": halves[1], "가운데 날": str(mid.date()), "판정": verdict})
    return row, ep, ret


def first_after(mask, start, end):
    w = np.where(mask[start:end + 1])[0]
    return start + int(w[0]) if len(w) else None


def turn_from_peak(s, start, end, drop, pct=False):
    """시작 뒤 그때까지의 최고점에서 drop 만큼 내려온 첫날."""
    v = s.values
    peak = -np.inf
    for i in range(start, min(end, len(v) - 1) + 1):
        if np.isnan(v[i]):
            continue
        peak = max(peak, v[i])
        fall = (v[i] / peak - 1) if pct else (v[i] - peak)
        if fall <= -drop:
            return i
    return None


def vix_calm(vix, start, end):
    v = vix.values
    hit = False
    for i in range(start, min(end, len(v) - 1) + 1):
        if v[i] > 25:
            hit = True
        elif hit and v[i] < 20:
            return i
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    c = load_close("^GSPC")
    c = c[c.index >= "1995-01-01"]
    idx = c.index
    vix = load_close("^VIX").reindex(idx).ffill(limit=5)
    gold = load_close("GC=F")
    d10, t2, ie, baa, usd = (fred(s, idx) for s in ("DGS10", "DGS2", "T10YIE", "BAA10Y", "DTWEXBGS"))
    real = d10 - ie
    dr, db = real.diff(60), baa.diff(60)
    states = {
        "A1 실질금리 60일 +0.45%p↑": (dr >= 0.45, "2003-01-02"),
        "A2 실질금리 60일 +0.25%p↑": (dr >= 0.25, "2003-01-02"),
        "B1 가산금리 60일 +0.35%p↑": (db >= 0.35, "1995-04-01"),
        "C1 실질금리↑ + 가산금리 +0.20%p↑": ((dr >= 0.25) & (db >= 0.20), "2003-01-02"),
        "C2 실질금리↑ + 가산금리 평온(+0.10%p 미만)": ((dr >= 0.25) & (db < 0.10), "2003-01-02"),
        "D1 10년 금리 60일 +0.55%p↑": (d10.diff(60) >= 0.55, "1995-04-01"),
        "D2 2년 금리 60일 +0.50%p↑": (t2.diff(60) >= 0.50, "1995-04-01"),
    }
    rows, eps = [], {}
    for name, (sig, frm) in states.items():
        for h in HS:
            r, ep, _ = compare(name, sig, c, pd.Timestamp(frm), h)
            rows.append(r)
            eps[name] = ep
    # 끝난 때 — C1 · A1 · B1 사건마다
    cases = []
    for name in ("C1 실질금리↑ + 가산금리 +0.20%p↑", "A1 실질금리 60일 +0.45%p↑", "B1 가산금리 60일 +0.35%p↑"):
        for s in eps[name]:
            end = min(s + 252, len(c) - 1)
            tr = s + int(np.argmin(c.values[s:end + 1]))
            dd = c.values[tr] / c.values[s] - 1
            look = min(tr + 252, len(c) - 1)
            sig_days = {
                "T1 2년 −0.30%p": turn_from_peak(t2, s, look, 0.30),
                "T2 실질 −0.30%p": turn_from_peak(real, s, look, 0.30),
                "T3 가산 −0.20%p": turn_from_peak(baa, s, look, 0.20),
                "T4 VIX 25→20": vix_calm(vix, s, look),
                "T5 달러 −3%": turn_from_peak(usd, s, look, 0.03, pct=True),
            }
            row = {"상태": name[:2], "시작": str(idx[s].date()), "바닥": str(idx[tr].date()), "시작→바닥 거래일": tr - s,
                   "낙폭": dd, "바닥 뒤 126일": (c.values[min(tr + 126, len(c) - 1)] / c.values[tr] - 1) if tr + 126 < len(c) else np.nan}
            for k, i in sig_days.items():
                row[k] = (i - tr) if i is not None else None
                row[k + " 뒤 더 빠짐"] = (c.values[tr] / c.values[i] - 1 if i < tr else 0.0) if i is not None else None
                row[k + " 뒤 126일"] = (c.values[i + 126] / c.values[i] - 1) if i is not None and i + 126 < len(c) else None
            cases.append(row)
    cs = pd.DataFrame(cases)
    # 금
    gold_rows = []
    g = gold.reindex(idx).ffill(limit=5)
    for name in ("A1 실질금리 60일 +0.45%p↑", "A2 실질금리 60일 +0.25%p↑"):
        for h in HS:
            r, _, _ = compare(name, states[name][0], g, pd.Timestamp("2003-01-02"), h, label="금")
            gold_rows.append(r)
    gr, rr = g.pct_change(), real.diff()
    yr = pd.DataFrame({"g": gr, "r": rr}).dropna()
    yr = yr[yr.index >= "2003-01-01"]
    corr_y = yr.groupby(yr.index.year).apply(lambda d: d["g"].corr(d["r"]))
    corr_p = {"2003 ~ 2021": yr[yr.index < "2022-01-01"].corr().iloc[0, 1], "2022 ~ 2026": yr[yr.index >= "2022-01-01"].corr().iloc[0, 1]}
    # 금 vs 실질금리 수준 — 252일 변화끼리
    lv = pd.DataFrame({"g": np.log(g).diff(252), "r": real.diff(252)}).dropna()
    corr_l = {"2003 ~ 2021": lv[lv.index < "2022-01-01"].corr().iloc[0, 1], "2022 ~ 2026": lv[lv.index >= "2022-01-01"].corr().iloc[0, 1]}
    # 지금 자리
    now = {"날짜": str(idx[-1].date()), "실질금리": real.iloc[-1], "실질 60일": dr.iloc[-1], "가산금리": baa.iloc[-1], "가산 60일": db.iloc[-1],
           "10년": d10.iloc[-1], "10년 60일": d10.diff(60).iloc[-1], "2년": t2.iloc[-1], "2년 60일": t2.diff(60).iloc[-1], "VIX": vix.iloc[-1],
           "켜진 상태": [n for n, (s, _) in states.items() if bool(s.iloc[-1])],
           "최근 1년 켜진 상태(마지막 날)": {n: str(idx[np.where(s.fillna(False).values)[0][-1]].date()) for n, (s, _) in states.items()
                                       if s.fillna(False).values[-252:].any()}}
    df, gd = pd.DataFrame(rows), pd.DataFrame(gold_rows)
    df.to_csv(os.path.join(OUT, "macro_regime_states.csv"), index=False)
    cs.to_csv(os.path.join(OUT, "macro_regime_cases.csv"), index=False)
    pct = lambda v: "—" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:+.1%}"  # noqa: E731
    pr = lambda v: "—" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.0%}"  # noqa: E731
    L = ["# 금리 · 신용 국면 검증 — 결과 (자동 생성, macro_regime_check.py)", "",
         f"지금 ({now['날짜']}): 실질금리 {now['실질금리']:.2f}% (60일 {now['실질 60일']:+.2f}) · 가산금리(BAA) {now['가산금리']:.2f}%p (60일 {now['가산 60일']:+.2f}) · "
         f"10년 {now['10년']:.2f}% ({now['10년 60일']:+.2f}) · 2년 {now['2년']:.2f}% ({now['2년 60일']:+.2f}) · VIX {now['VIX']:.1f}",
         f"켜진 상태: {', '.join(now['켜진 상태']) or '없음'}", f"최근 1년 안에 켜졌던 상태 → 마지막 날: {now['최근 1년 켜진 상태(마지막 날)']}", ""]
    for label, d in (("S&P 500", df), ("금", gd)):
        L += [f"## {label} — 상태 뒤 수익률", "",
              "| 상태 | 창 | 사건 | 중앙값 | 아무 날 | 상승 | 상승 비율 | 아무 날 | 낙폭≤−10% | 아무 날 | 최악 | 최고 | p | 앞 절반 차 | 뒤 절반 차 | 판정 |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for _, r in d.iterrows():
            if not r["사건"]:
                L.append(f"| {r['상태']} | {r['창']} | 0 | | | | | | | | | | | | | |")
                continue
            L.append(f"| {r['상태']} | {r['창']} | {r['사건']} | {pct(r['중앙값'])} | {pct(r['아무 날 중앙값'])} | {r['상승']}/{r['사건']} | {pr(r['상승 비율'])} | "
                     f"{pr(r['아무 날 상승 비율'])} | {r['낙폭≤−10%']}/{r['사건']} | {pr(r['아무 날 낙폭≤−10%'])} | {pct(r['최악'])} | {pct(r['최고'])} | {r['p']:.3f} | "
                     f"{pct(r['앞 절반 차'])} | {pct(r['뒤 절반 차'])} | {r['판정']} |")
        L.append("")
    L += ["## 금 하루 수익 vs 실질금리 하루 변화 — 상관", "", " · ".join(f"{k} {v:+.2f}" for k, v in corr_p.items()),
          "", "252일 변화끼리: " + " · ".join(f"{k} {v:+.2f}" for k, v in corr_l.items()), "",
          "연도별: " + " · ".join(f"{y} {v:+.2f}" for y, v in corr_y.items()), ""]
    L += ["## 끝난 때 — 사건마다 바닥과 꺾임 신호 (바닥 날 대비 거래일, − = 바닥보다 먼저)", "",
          "| 상태 | 시작 | 바닥 | 시작→바닥 | 낙폭 | 바닥 뒤 126일 | T1 2년 −0.30 | T2 실질 −0.30 | T3 가산 −0.20 | T4 VIX 25→20 | T5 달러 −3% |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    f = lambda v: "—" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{int(v):+d}"  # noqa: E731
    for _, r in cs.iterrows():
        L.append(f"| {r['상태']} | {r['시작']} | {r['바닥']} | {r['시작→바닥 거래일']} | {pct(r['낙폭'])} | {pct(r['바닥 뒤 126일'])} | "
                 f"{f(r['T1 2년 −0.30%p'])} | {f(r['T2 실질 −0.30%p'])} | {f(r['T3 가산 −0.20%p'])} | {f(r['T4 VIX 25→20'])} | {f(r['T5 달러 −3%'])} |")
    big = cs[cs["낙폭"] <= -0.05]
    L += ["", f"### 낙폭 5% 넘은 사건 {len(big)}개 — 신호가 바닥 전(−) · 바닥 뒤 63일 안(0 ~ +63) · 그 뒤 · 안 옴", ""]
    for k in ("T1 2년 −0.30%p", "T2 실질 −0.30%p", "T3 가산 −0.20%p", "T4 VIX 25→20", "T5 달러 −3%"):
        v = big[k]
        L.append(f"- {k}: 바닥 전 {int((v < 0).sum())} · 바닥 뒤 63일 안 {int(((v >= 0) & (v <= 63)).sum())} · 그 뒤 {int((v > 63).sum())} · 안 옴 {int(v.isna().sum())}"
                 f" · 중앙값 {('—' if v.dropna().empty else f'{int(v.median()):+d}')}")
        more = big[k + " 뒤 더 빠짐"].dropna().astype(float)
        fw = big[k + " 뒤 126일"].dropna().astype(float)
        L.append(f"  - 신호 날부터 바닥까지 더 빠진 폭 중앙값 {more.median():+.1%} · 10% 넘게 더 빠짐 {int((more <= -0.10).sum())}/{len(more)}"
                 f" · 신호 뒤 126일 중앙값 {fw.median():+.1%} · 상승 {int((fw > 0).sum())}/{len(fw)}")
    open(os.path.join(OUT, "macro_regime.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
