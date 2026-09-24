"""섹터 하향식 검증 — 강한 섹터의 주도 종목을 사면 같은 날 아무 종목을 사는 것보다 나은가.

    .venv/bin/python experiments/signal-study/sector_topdown.py     # data/bars.pkl 캐시 필요 (main.py 가 만든다)

규칙 (2026-09-24 사전 확정 — 결과를 보고 바꾸지 않는다):
  섹터 점수 = 섹터 ETF 의 SPY 대비 5D 초과수익 순위 + 20D 초과수익 순위 (평균). 상위 3 섹터.
  종목 점수 = 소속 섹터 ETF 대비 5D 초과수익 순위 + 20D 초과수익 순위 (섹터 안 평균). 섹터당 상위 3 → 하루 9종목.
  진입 = 다음 거래일 시가, 청산 = 신호일 + h 거래일 종가. h = 3 · 5 · 20. 왕복 비용 0.2%.
  리밸런스 = h 거래일마다 (보유 구간이 겹치지 않게 — 겹치면 같은 상승을 여러 번 세서 p 가 과하게 작아진다).

비교 (플라시보는 전부 '같은 날' 무작위 — 시장 타이밍 효과가 빠지고 선택 효과만 남는다):
  A  상위 섹터 × 주도 종목            vs 전체 유니버스 무작위 9종목      → 전체 효과
  B  상위 섹터 × 무작위 종목          vs 전체 유니버스 무작위           → 섹터 효과
  C  상위 섹터 × 주도 종목            vs 상위 섹터 안 무작위            → 섹터 안 종목 선별 효과
  D  섹터 무시 · 전체 주도 종목 9개    vs 전체 유니버스 무작위           → 종목 모멘텀만
  E  하위 3 섹터 × 무작위 종목         vs 전체 유니버스 무작위           → 대조 (약한 섹터)
  또 종목 점수를 5D 만 / 20D 만으로 나눠 본다 (단기 반전 vs 모멘텀 분리).
"""

import os
import sys

import numpy as np
import pandas as pd

import config
import outcomes
import universe

HORIZONS = [3, 5, 20]
TOP_SECTORS = 3
PER_SECTOR = 3
LOOKBACKS = (5, 20)
B = 1000
OUT = os.path.join(config.OUTPUT_DIR, "sector_topdown.md")


def wide(bars, syms, col):
    return pd.DataFrame({s: bars[s][col] for s in syms if s in bars})


def load():
    bars = pd.read_pickle(os.path.join(config.DATA_DIR, "bars.pkl"))
    uni = universe.load()
    uni = uni[uni["symbol"].isin(bars)]
    spy = bars[config.BENCHMARK]
    days = spy.index
    C = wide(bars, uni["symbol"], "Close").reindex(days)
    O = wide(bars, uni["symbol"], "Open").reindex(days)
    etfs = sorted(set(config.SECTOR_ETF.values()))
    EC = wide(bars, etfs, "Close").reindex(days)
    sec_of = dict(zip(uni["symbol"], uni["sector"]))
    etf_of = {s: config.SECTOR_ETF[sec_of[s]] for s in C.columns}
    risk_on = outcomes.regime(spy, bars[config.VIX]).reindex(days).fillna(False)
    return C, O, EC, spy, etf_of, risk_on


def scores(C, EC, spy, etf_of, lbs):
    """sector_rank: 날짜 × ETF 점수(높을수록 강함). stock_in_sector: 날짜 × 종목, 섹터 안 순위 점수. stock_all: 전체 순위."""
    sc = spy["Close"].reindex(C.index)
    sec_parts, stk_parts, all_parts = [], [], []
    etf_cols = [etf_of[s] for s in C.columns]
    for lb in lbs:
        er = EC / EC.shift(lb) - 1
        ex_sec = er.sub(sc / sc.shift(lb) - 1, axis=0)
        sec_parts.append(ex_sec.rank(axis=1, pct=True))
        cr = C / C.shift(lb) - 1
        ex_stk = cr - er[etf_cols].set_axis(C.columns, axis=1)
        # 섹터 안 순위: 섹터별로 나눠 rank
        r = pd.DataFrame(index=C.index, columns=C.columns, dtype=float)
        for etf in set(etf_cols):
            cols = [s for s in C.columns if etf_of[s] == etf]
            r[cols] = ex_stk[cols].rank(axis=1, pct=True)
        stk_parts.append(r)
        all_parts.append(ex_stk.rank(axis=1, pct=True))
    sec = sum(sec_parts) / len(lbs)
    # ETF 가 아직 없는 날(XLC 2018-06 전)은 그 섹터 종목 점수를 비운다
    stk = sum(stk_parts) / len(lbs)
    stk_all = sum(all_parts) / len(lbs)
    etf_ok = EC[etf_cols].set_axis(C.columns, axis=1).shift(max(lbs)).notna()
    return sec, stk.where(etf_ok), stk_all.where(etf_ok)


def picks_for_day(t, sec, stk, stk_all, etf_of):
    s = sec.loc[t].dropna().sort_values(ascending=False)
    if len(s) < 2 * TOP_SECTORS:
        return None
    top, bot = list(s.index[:TOP_SECTORS]), list(s.index[-TOP_SECTORS:])
    row = stk.loc[t]
    valid = row.dropna().index
    etf = pd.Series(etf_of)[valid]
    A = []
    for e in top:
        A += list(row[etf[etf == e].index].sort_values(ascending=False).index[:PER_SECTOR])
    in_top = list(etf[etf.isin(top)].index)
    in_bot = list(etf[etf.isin(bot)].index)
    D = list(stk_all.loc[t].dropna().sort_values(ascending=False).index[:TOP_SECTORS * PER_SECTOR])
    return {"A": A, "D": D, "top": in_top, "bot": in_bot, "all": list(valid), "top_sectors": top}


def evaluate(C, O, spy, risk_on, sel, h, key, pool_key, n_pick, seed):
    """리밸런스 날짜마다 선택 종목 vs 같은 날 pool 무작위 n_pick 종목. 결과 dict (전체/탐색/검증/RISK ON/OFF)."""
    fwd = C.shift(-h) / O.shift(-1) - 1 - config.COST_ROUND_TRIP
    spy_fwd = spy["Close"].shift(-h) / spy["Open"].shift(-1) - 1
    rng = np.random.default_rng(seed)
    rows = []
    for t, d in sel.items():
        if d is None:
            continue
        r = fwd.loc[t]
        # B·E: 그 섹터 전 종목 = 그 섹터에서 무작위로 뽑은 기대값
        chosen = r[d[{"random_top": "top", "random_bot": "bot"}.get(key, key)]].dropna()
        pool = r[d[pool_key]].dropna().values
        if chosen.empty or len(pool) < n_pick * 2:
            continue
        # 무작위 뽑기 B 회 (비복원): 승률·평균 분포
        samp = pool[np.argsort(rng.random((B, len(pool))), axis=1)[:, :n_pick]]
        rows.append({
            "day": t, "n": len(chosen),
            "wins": int((chosen > 0).sum()), "sum": float(chosen.sum()),
            "big": int((chosen >= (0.10 if h >= 20 else 0.05)).sum()),
            "spy": float(spy_fwd.loc[t]) if pd.notna(spy_fwd.loc[t]) else np.nan,
            "port": float(chosen.mean()),
            "pool_port": float(pool.mean()),
            "rw": (samp > 0).mean(axis=1), "rm": samp.mean(axis=1),
            "risk_on": bool(risk_on.loc[t]),
        })
    return rows


def summarize(rows):
    if not rows:
        return None
    n = sum(r["n"] for r in rows)
    win = sum(r["wins"] for r in rows) / n
    mean = sum(r["sum"] for r in rows) / n
    big = sum(r["big"] for r in rows) / n
    # 플라시보: 날짜마다 무작위 뽑기의 승률·평균을 날짜 가중(선택 종목 수) 평균
    w = np.array([r["n"] for r in rows], dtype=float)
    rw = np.array([r["rw"] for r in rows])       # dates × B
    rm = np.array([r["rm"] for r in rows])
    bw = (rw * w[:, None]).sum(0) / w.sum()
    bm = (rm * w[:, None]).sum(0) / w.sum()
    port = np.array([r["port"] for r in rows])
    pool = np.array([r["pool_port"] for r in rows])
    diff = port - pool
    t_stat = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if len(diff) > 2 else np.nan
    spy = np.array([r["spy"] for r in rows])
    return {
        "dates": len(rows), "n": n, "win": win, "mean": mean, "big": big,
        "base_win": float(bw.mean()), "base_mean": float(bm.mean()),
        "p_win": float(((bw >= win).sum() + 1) / (B + 1)),
        "p_mean": float(((bm >= mean).sum() + 1) / (B + 1)),
        "hit_dates": float((diff > 0).mean()), "t": float(t_stat),
        "excess_spy": float(np.nanmean(port - spy)),
    }


def splits(rows):
    return {
        "전체": rows,
        "탐색 ~2022": [r for r in rows if r["day"] < pd.Timestamp(config.SPLIT_DAY)],
        "검증 2023~": [r for r in rows if r["day"] >= pd.Timestamp(config.SPLIT_DAY)],
        "RISK ON": [r for r in rows if r["risk_on"]],
        "RISK OFF": [r for r in rows if not r["risk_on"]],
    }


VARIANTS = [
    ("A", "상위 3섹터 × 주도 종목 9", "A", "all"),
    ("B", "상위 3섹터 × 전 종목 (섹터 효과)", "random_top", "all"),
    ("C", "상위 3섹터 안: 주도 종목 vs 같은 섹터 무작위", "A", "top"),
    ("D", "섹터 무시 · 전체 주도 종목 9", "D", "all"),
    ("E", "하위 3섹터 × 전 종목 (대조)", "random_bot", "all"),
]


def sgn(x, d=2):
    return "—" if x is None or np.isnan(x) else f"{x * 100:+.{d}f}%"


def run_set(C, O, EC, spy, etf_of, risk_on, lbs, only=None):
    sec, stk, stk_all = scores(C, EC, spy, etf_of, lbs)
    start = C.index.searchsorted(pd.Timestamp(config.STUDY_START))
    out = {}
    for h in HORIZONS:
        dates = C.index[start:len(C.index) - h - 1:h]
        sel = {t: picks_for_day(t, sec, stk, stk_all, etf_of) for t in dates}
        for code, name, key, pool_key in VARIANTS:
            if only and code not in only:
                continue
            n_pick = TOP_SECTORS * PER_SECTOR
            rows = evaluate(C, O, spy, risk_on, sel, h, key, pool_key, n_pick, seed=config.SEED + h * 100 + ord(code))
            out[(code, h)] = {k: summarize(v) for k, v in splits(rows).items()}
        if h == 5:
            out["sector_freq"] = pd.Series([s for d in sel.values() if d for s in d["top_sectors"]]).value_counts()
            out["last_pick"] = next((t, d) for t, d in reversed(list(sel.items())) if d)
    return out


def table(out, code, h):
    lines = ["| 구간 | 리밸런스 | 종목 수 | 승률 | 무작위 승률 | p(승률) | 평균 | 무작위 평균 | p(평균) | 무작위보다 나은 날 | t | SPY 대비 | 큰 상승 비율 |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for k, s in out[(code, h)].items():
        if s is None:
            continue
        lines.append(f"| {k} | {s['dates']} | {s['n']:,} | {s['win']:.1%} | {s['base_win']:.1%} | {s['p_win']:.3f} | "
                     f"{sgn(s['mean'])} | {sgn(s['base_mean'])} | {s['p_mean']:.3f} | {s['hit_dates']:.0%} | {s['t']:.2f} | "
                     f"{sgn(s['excess_spy'])} | {s['big']:.1%} |")
    return "\n".join(lines)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    C, O, EC, spy, etf_of, risk_on = load()
    print(f"[load] 종목 {C.shape[1]} · 거래일 {C.shape[0]}")
    main_out = run_set(C, O, EC, spy, etf_of, risk_on, LOOKBACKS)
    print("[run] 기본 규칙 완료")
    only5 = run_set(C, O, EC, spy, etf_of, risk_on, (5,), only={"A", "B", "C", "D"})
    only20 = run_set(C, O, EC, spy, etf_of, risk_on, (20,), only={"A", "B", "C", "D"})
    print("[run] 5D 단독 · 20D 단독 완료")

    md = ["# 섹터 하향식 검증 — 결과", "",
          f"S&P 500 현재 구성 {C.shape[1]}종목 · {config.STUDY_START} ~ {C.index.max().date()} · 캐시 일봉. "
          "규칙과 비교 방식은 `sector_topdown.py` 머리말. 비용 0.2% 차감 후 수치.", "",
          "- **무작위** = 같은 리밸런스 날, 비교 풀에서 같은 수를 무작위로 1,000번 뽑은 평균. p = 무작위가 관측 이상일 비율.",
          "- **무작위보다 나은 날** = 리밸런스 날 중 선택 종목 평균이 풀 평균을 넘은 비율. t = 그 날별 차이의 t 통계량.",
          "- **큰 상승 비율** = 3·5일 보유는 +5% 이상, 20일 보유는 +10% 이상으로 끝난 종목 비율.", ""]
    for code, name, _, pool_key in VARIANTS:
        md.append(f"## {code}. {name}")
        md.append(f"비교 풀: {'전체 유니버스' if pool_key == 'all' else '상위 3섹터 종목'}")
        md.append("")
        for h in HORIZONS:
            md += [f"**{h}일 보유**", "", table(main_out, code, h), ""]
    md.append("## 종목 점수 분해 — 5D 단독 vs 20D 단독 (전체 기간)")
    md.append("")
    md.append("| 변형 | 점수 | 보유 | 승률 | 무작위 | p(승률) | 평균 | 무작위 평균 | p(평균) | t |")
    md.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for code in "ABCD":
        for lbl, o in (("5D+20D", main_out), ("5D", only5), ("20D", only20)):
            for h in HORIZONS:
                s = o[(code, h)]["전체"]
                md.append(f"| {code} | {lbl} | {h}일 | {s['win']:.1%} | {s['base_win']:.1%} | {s['p_win']:.3f} | "
                          f"{sgn(s['mean'])} | {sgn(s['base_mean'])} | {s['p_mean']:.3f} | {s['t']:.2f} |")
    md.append("")
    md.append("## 상위 3섹터에 든 횟수 (5일 리밸런스)")
    md.append("")
    inv = {v: k for k, v in config.SECTOR_ETF.items()}
    md.append("| ETF | 섹터 | 횟수 |")
    md.append("| --- | --- | ---: |")
    for etf, n in main_out["sector_freq"].items():
        md.append(f"| {etf} | {inv[etf]} | {n} |")
    t, d = main_out["last_pick"]
    md += ["", f"마지막 리밸런스({t.date()}) 상위 섹터: {', '.join(d['top_sectors'])} · 종목: {', '.join(d['A'])}", ""]
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
