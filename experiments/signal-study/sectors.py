"""⓪ 섹터 순환 (계획 3절) — output/r01_sector_cycle.md · output/r01_regime.pkl

섹터 지수 두 개: ETF(시총 가중 = 대장주) · 동일가중(500종목 섹터별 일간 수익률 평균 = 평균 종목).
국면(RRG 방식, 동일가중 기준):  level = (섹터/SPY) ÷ 그 60일 평균 − 1,  mom = level − 10일 전 level
    주도 level>0·mom>0 | 약화 level>0·mom<0 | 소외 level<0·mom<0 | 개선 level<0·mom>0
전환 이벤트 (확정 2026-09-24):
    (a) 상대강도 20일 변화 음 → 양
    (c) 섹터 폭(20일선 위 종목 비율) 50% 상향 돌파
    (d) 섹터 지수가 자기 200일선 회복
    이벤트 날에도 전제 조건 1 (SPY > 200일선) 적용.
"""

import os
import sys

import numpy as np
import pandas as pd

import common
import config

SEC_H = [5, 10, 20, 60]
TEXTBOOK = ["Financials", "Consumer Discretionary", "Industrials", "Information Technology", "Materials", "Energy",
            "Consumer Staples", "Health Care", "Utilities", "Real Estate", "Communication Services"]
SHORT = {"Information Technology": "기술", "Financials": "금융", "Health Care": "헬스", "Consumer Discretionary": "경기소비",
         "Consumer Staples": "필수소비", "Energy": "에너지", "Industrials": "산업", "Materials": "소재", "Utilities": "유틸",
         "Real Estate": "부동산", "Communication Services": "통신"}


def build_indices(D):
    sectors = sorted(set(D.sector[s] for s in D.syms if D.sector[s] != "Removed"))
    R = D.C.pct_change()
    ew, breadth = {}, {}
    above20 = D.C > D.C.rolling(20).mean()
    for sec in sectors:
        cols = [s for s in D.syms if D.sector[s] == sec]
        v = D.valid[cols]
        r = R[cols].where(v)
        ew[sec] = (1 + r.mean(axis=1).fillna(0)).cumprod()
        breadth[sec] = above20[cols].where(v).mean(axis=1)
    EW = pd.DataFrame(ew)
    BR = pd.DataFrame(breadth)
    ETF = pd.DataFrame({sec: D.etf[sec]["Close"].reindex(D.days) for sec in sectors if sec in D.etf})
    spy = D.spy["Close"]
    return sectors, EW, ETF, BR, spy


def regime_labels(idx, spy):
    rs = idx.div(spy, axis=0)
    level = rs / rs.rolling(60).mean() - 1
    mom = level - level.shift(10)
    lab = np.where(level > 0, np.where(mom > 0, "주도", "약화"), np.where(mom > 0, "개선", "소외"))
    lab = pd.DataFrame(lab, index=idx.index, columns=idx.columns).where(level.notna() & mom.notna())
    return lab, level, mom


def transitions(idx, BR, spy):
    rs20 = idx.div(spy, axis=0).pct_change(20)
    a = (rs20 > 0) & (rs20.shift(1) <= 0)
    c = (BR > 0.5) & (BR.shift(1) <= 0.5)
    d = (idx > idx.rolling(200).mean()) & (idx.shift(1) <= idx.rolling(200).mean().shift(1))
    return {"(a) 상대강도 20일 음→양": a, "(c) 섹터 폭 50% 돌파": c, "(d) 200일선 회복": d}


def persistence(idx, spy, ev, ok_days):
    """전환 뒤 h일 섹터 초과수익(SPY 대비) · 승률 vs 그 섹터의 모든 유효일 (무조건)."""
    rows = []
    for h in SEC_H:
        ex = idx.shift(-h) / idx - 1
        ex = ex.sub(spy.shift(-h) / spy - 1, axis=0)
        okm = np.tile(ok_days.values[:, None], (1, ex.shape[1]))
        obs = ex.where(ev.values & okm).stack().dropna()
        base = ex.where(okm).stack().dropna()
        rows.append((h, len(obs), obs.mean(), (obs > 0).mean(), base.mean(), (base > 0).mean()))
    return rows


def stock_mask_from_events(D, ev, sectors, top=None, EW=None, delay=0):
    """섹터 이벤트 (날, 섹터) → 종목 신호 (날+delay, 그 섹터 종목). top 이면 섹터 내 20일 상대강도 상위 top 만."""
    m = pd.DataFrame(False, index=D.days, columns=D.syms)
    evs = ev.shift(delay).fillna(False).astype(bool)
    if top:
        r20 = D.C / D.C.shift(20) - 1
    for sec in sectors:
        cols = [s for s in D.syms if D.sector[s] == sec]
        days = evs.index[evs[sec].values]
        if not top:
            m.loc[days, cols] = True
        else:
            rel = r20[cols].sub((EW[sec] / EW[sec].shift(20) - 1), axis=0)
            for d in days:
                row = rel.loc[d].where(D.signal_ok.loc[d, cols]).dropna().sort_values(ascending=False)
                m.loc[d, list(row.index[:top])] = True
    return m & D.signal_ok


def weekly(x):
    return x.resample("W-FRI").last()


def lead_lag(EW, spy, sectors, max_lag=8):
    """주간 상대강도 변화의 선행·지연 상관. (i, j, lag): i 의 변화가 j 의 lag 주 뒤 변화와 갖는 상관."""
    w = weekly(EW.div(spy, axis=0)).pct_change().dropna()
    out = {}
    for i in sectors:
        for j in sectors:
            if i == j:
                continue
            best = (0, w[i].corr(w[j]))
            for lag in range(1, max_lag + 1):
                c = w[i].corr(w[j].shift(-lag))
                if abs(c) > abs(best[1]):
                    best = (lag, c)
            out[(i, j)] = best
    return out, len(w)


def cause_corr(D, EW, spy, sectors):
    m = D.macro
    ratio = m["HYG"]["Close"] / m["LQD"]["Close"]
    vars_ = {"10년 금리": m["^TNX"]["Close"], "유가 WTI": m["CL=F"]["Close"], "금": m["GC=F"]["Close"],
             "구리": m["HG=F"]["Close"], "HYG/LQD": ratio, "VIX": D.vix}
    wsec = weekly(EW.div(spy, axis=0)).pct_change()
    rows = []
    for name, v in vars_.items():
        wv = weekly(v.reindex(D.days).ffill())
        wv = wv.diff() if name in ("10년 금리", "VIX") else wv.pct_change()
        for sec in sectors:
            c0 = wsec[sec].corr(wv)
            best = (0, c0)
            for lag in range(1, 5):
                c = wsec[sec].corr(wv.shift(lag))       # 변수가 lag 주 앞섬
                if abs(c) > abs(best[1]):
                    best = (lag, c)
            rows.append((name, sec, c0, best[0], best[1]))
    return rows


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    D = common.load()
    sectors, EW, ETF, BR, spy = build_indices(D)
    ok_days = D.spy_ok & D.study
    lab_ew, level, mom = regime_labels(EW, spy)
    lab_etf, _, _ = regime_labels(ETF, spy)
    # 종목 단위 국면 표 저장 (① ~ ③ 의 분할 축)
    reg = pd.DataFrame({s: lab_ew[D.sector[s]] if D.sector[s] in lab_ew else np.nan for s in D.syms}, index=D.days)
    os.makedirs(common.OUT, exist_ok=True)
    reg.to_pickle(os.path.join(common.OUT, "r01_regime.pkl"))

    md = ["# r01 ⓪ 섹터 순환", "",
          f"S&P 500 {len(D.syms)}종목 · {config.STUDY_START} ~ {D.days.max().date()} · 전제 조건: SPY > 200일선인 날만 이벤트로 인정, 종목은 편입일 이후.",
          "섹터 지수 = ETF(대장주) · 동일가중(평균 종목). 국면·전환은 **동일가중** 기준, ETF 는 비교용. 방법은 `sectors.py` 머리말.", ""]

    # ⓪-1 ETF vs 동일가중
    md += ["## ⓪-1 섹터 지수 — ETF vs 동일가중 (연환산 수익률 · 괴리)", "",
           "| 섹터 | ETF 연수익 | 동일가중 연수익 | 괴리 (ETF−EW) | 국면 일치율 |", "| --- | ---: | ---: | ---: | ---: |"]
    yrs = (D.days.max() - pd.Timestamp(config.STUDY_START)).days / 365.25
    for sec in sectors:
        e = ETF[sec].dropna(); e = e[e.index >= config.STUDY_START]
        w = EW[sec][EW.index >= e.index.min()]
        ann_e = (e.iloc[-1] / e.iloc[0]) ** (1 / ((e.index[-1] - e.index[0]).days / 365.25)) - 1
        ann_w = (w.iloc[-1] / w.iloc[0]) ** (1 / ((w.index[-1] - w.index[0]).days / 365.25)) - 1
        agree = (lab_ew[sec] == lab_etf[sec]).loc[ok_days].mean()
        md.append(f"| {SHORT[sec]} | {ann_e:+.1%} | {ann_w:+.1%} | {ann_e - ann_w:+.1%} | {agree:.0%} |")
    md += ["", "괴리가 큰 섹터(기술·경기소비·통신)는 대장주 몇 개가 ETF 를 끌었다는 뜻이다. 국면 일치율이 낮으면 \"섹터가 강하다\"의 뜻이 두 지수에서 다르다.", ""]

    # ⓪-2 전환 건수
    ev = transitions(EW, BR, spy)
    ev_etf = transitions(ETF, BR, spy)
    md += ["## ⓪-2 전환 이벤트 건수 (동일가중 · SPY > 200일선인 날)", "",
           "| 정의 | 전체 | 연평균 | 섹터당 연평균 | 탐색 ~2022 | 검증 2023~ |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name, e in ev.items():
        e2 = e & np.tile(ok_days.values[:, None], (1, e.shape[1]))
        n = int(e2.values.sum())
        md.append(f"| {name} | {n} | {n / yrs:.0f} | {n / yrs / len(sectors):.1f} | {int(e2[D.period == '탐색 ~2022'].values.sum())} | {int(e2[D.period == '검증 2023~'].values.sum())} |")
    md += ["", "국면 분포 (동일가중, 전체 섹터·유효일): " + " · ".join(f"{k} {v:.0%}" for k, v in lab_ew.loc[ok_days].stack().dropna().value_counts(normalize=True).items()), ""]

    # ⓪-3 지속성
    md += ["## ⓪-3 지속성 — 전환 뒤 섹터의 SPY 대비 초과수익", "",
           "\"강세가 시작되면 얼마나 이어지나\". 기준선 = 그 섹터의 모든 유효일에서 같은 h일 초과수익.", ""]
    for name, e in ev.items():
        md += [f"**{name}**", "", "| h | n | 초과수익 평균 | 승률 | 무조건 평균 | 무조건 승률 | 차이 %p |", "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for h, n, mu, win, bmu, bwin in persistence(EW, spy, e, ok_days):
            md.append(f"| {h} | {n} | {mu * 100:+.2f}% | {win:.1%} | {bmu * 100:+.2f}% | {bwin:.1%} | **{(win - bwin) * 100:+.1f}** |")
        md.append("")
    md += ["ETF 기준으로 같은 것 — (a) 만", ""]
    md += ["| h | n | 초과수익 평균 | 승률 | 무조건 평균 | 무조건 승률 | 차이 %p |", "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for h, n, mu, win, bmu, bwin in persistence(ETF, spy, ev_etf["(a) 상대강도 20일 음→양"], ok_days):
        md.append(f"| {h} | {n} | {mu * 100:+.2f}% | {win:.1%} | {bmu * 100:+.2f}% | {bwin:.1%} | **{(win - bwin) * 100:+.1f}** |")
    md.append("")
    # 섹터별 (a) h=20
    md += ["**(a) 전환 뒤 20일, 섹터별**", "", "| 섹터 | n | 초과수익 | 승률 | 무조건 승률 | 차이 %p |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    a = ev["(a) 상대강도 20일 음→양"]
    ex20 = (EW.shift(-20) / EW - 1).sub(spy.shift(-20) / spy - 1, axis=0)
    for sec in sectors:
        e = a[sec] & ok_days
        o = ex20[sec][e].dropna(); b = ex20[sec][ok_days].dropna()
        md.append(f"| {SHORT[sec]} | {len(o)} | {o.mean() * 100:+.2f}% | {(o > 0).mean():.1%} | {(b > 0).mean():.1%} | {((o > 0).mean() - (b > 0).mean()) * 100:+.1f} |")
    md.append("")

    # ⓪-4 종목 진입
    md += ["## ⓪-4 종목 진입 — 전환일 다음 날 시가에 그 섹터 종목 매수", "", common.LEGEND, ""]
    for name, e in ev.items():
        for label, top in (("섹터 전 종목", None), ("섹터 내 상대강도 상위 3", 3)):
            md += [f"**{name} · {label}**", "", common.HEADER]
            m0 = stock_mask_from_events(D, e, sectors, top=top, EW=EW)
            for h in (3, 5, 10, 20):
                m = common.cluster(m0, h)
                s = common.evaluate(D, m, h, placebo=True, seed=h)
                md.append(common.fmt_row(f"{h}일", s))
            md.append("")
    # 기간 분할 — (a) 전 종목 5일·20일
    e = ev["(a) 상대강도 20일 음→양"]
    m0 = stock_mask_from_events(D, e, sectors)
    for h in (5, 20):
        md.append(common.split_table(D, common.cluster(m0, h), h, D.period, f"(a) 전 종목 {h}일 — 구간별"))
        md.append(common.year_table(D, common.cluster(m0, h), h) + "\n")

    # ⓪-5 진입 지연
    md += ["## ⓪-5 진입 지연 — (a) 전 종목, 전환 당일 / 3일 뒤 / 5일 뒤 진입", "", common.HEADER]
    for delay in (0, 3, 5):
        m0 = stock_mask_from_events(D, e, sectors, delay=delay)
        for h in (5, 20):
            s = common.evaluate(D, common.cluster(m0, h), h)
            md.append(common.fmt_row(f"+{delay}일 진입 · {h}일 보유", s))
    md.append("")

    # ⓪-6 순환 순서
    ll, nweeks = lead_lag(EW, spy, sectors)
    md += ["## ⓪-6 순환 순서 — 주간 상대강도 변화의 선행·지연 상관", "",
           f"주간(금요일) 동일가중 상대강도 변화 {nweeks}주. 칸 = i(행)의 변화가 j(열)의 **몇 주 뒤** 변화와 가장 상관이 큰가 (지연 주 / 상관). 0 이면 동시. 상관 |r| < 0.15 는 `·`.", ""]
    md.append("| i → j | " + " | ".join(SHORT[s] for s in TEXTBOOK) + " |")
    md.append("| --- | " + " | ".join("---" for _ in TEXTBOOK) + " |")
    for i in TEXTBOOK:
        cells = []
        for j in TEXTBOOK:
            if i == j:
                cells.append("—"); continue
            lag, c = ll[(i, j)]
            cells.append("·" if abs(c) < 0.15 else f"{lag}주 {c:+.2f}")
        md.append(f"| {SHORT[i]} | " + " | ".join(cells) + " |")
    lead_pairs = [(i, j, lag, c) for (i, j), (lag, c) in ll.items() if lag >= 1 and c > 0.2]
    md += ["", f"지연 ≥ 1주 이고 r > 0.2 인 선행 쌍: **{len(lead_pairs)}** / {len(ll)}. "
           + ("없음 — 한 섹터가 다른 섹터를 몇 주 앞서 움직이는 규칙적 순서는 이 데이터에 없다." if not lead_pairs else
              " · ".join(f"{SHORT[i]}→{SHORT[j]} {lag}주 {c:+.2f}" for i, j, lag, c in sorted(lead_pairs, key=lambda x: -x[3])[:15])), ""]

    # ⓪-7 원인 변수
    rows = cause_corr(D, EW, spy, sectors)
    md += ["## ⓪-7 원인 변수 — 주간 변화와 섹터 상대강도의 상관", "",
           "동시(lag 0) 상관과, 변수가 1~4주 **앞설** 때 가장 큰 상관. 사전 가설(계획 2절): 금리↑→금융+·유틸·부동산−, 유가↑→에너지+, 구리↑→산업·소재+, 금↑·VIX↑→위험 회피, HYG/LQD↑→위험 선호.", "",
           "| 변수 | " + " | ".join(SHORT[s] for s in TEXTBOOK) + " |", "| --- | " + " | ".join("---" for _ in TEXTBOOK) + " |"]
    by = {}
    for name, sec, c0, lag, cb in rows:
        by.setdefault(name, {})[sec] = (c0, lag, cb)
    for name, d in by.items():
        cells = []
        for sec in TEXTBOOK:
            c0, lag, cb = d[sec]
            cells.append(f"{c0:+.2f}" + (f" ({lag}주 {cb:+.2f})" if lag > 0 and abs(cb) > abs(c0) + 0.05 else ""))
        md.append(f"| {name} | " + " | ".join(cells) + " |")
    md += ["", "괄호 = 변수가 앞설 때 동시 상관보다 0.05 이상 커지는 경우만. 괄호가 거의 없으면 이 변수들은 섹터와 **같은 주에** 움직이고 예고하지 않는다.", ""]

    # 최근 국면
    last = ok_days[ok_days].index[-1]
    md += ["## 참고 — 마지막 유효일의 섹터 국면 (동일가중)", "", f"{last.date()}: " + " · ".join(f"{SHORT[s]} {lab_ew.loc[last, s]}" for s in sectors), ""]

    path = os.path.join(common.OUT, "r01_sector_cycle.md")
    open(path, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(f"→ {path}\n→ {os.path.join(common.OUT, 'r01_regime.pkl')}")


if __name__ == "__main__":
    main()
