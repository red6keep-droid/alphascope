"""종목 특성 1단계 검증 — 평소 모습 + 함께 움직임.

정의 · 결과 = 비공개 alphascope-docs/doc/검증/종목-특성-1단계-검증.md (이 스크립트가 쓴다).

    python experiments/stock-character/check_stage1.py            # 받은 일봉 있으면 그대로, 없으면 받기
    python experiments/stock-character/check_stage1.py --refresh  # 일봉 다시 받기

대상 = experiments/ref/universe_all.json (미국 S&P 500 · 한국 코스피200 + 코스닥150), 2005-01 ~ 최근, yfinance 수정 주가.
일봉 캐시 = data/store/character/bars_{us,kr}.pkl (깃 밖). 종목 · 구간별 값 = data/store/character/stage1_metrics.csv.gz.
AI 0 · 운영 수집 0 (로컬 한 번).

축 (1단계):
  ① 바탕 물결  hl = 장중 폭 중앙값 log(고/저) · gap = 밤사이 틈 중앙값 |log(시가/전날 종가)| · vol = 하루 등락 흩어짐(연율)
  ② 걸음걸이    er = 20일 곧은 정도(간 거리 ÷ 오르내린 거리 합) 중앙값
  ③ 계절 변화   season = 63일 조각마다 흩어짐 → 조각끼리 log 값의 표준편차
  ⑦ 함께 움직임 r2_mkt = 지수가 설명하는 몫 · r2_sec = 업종이 더 설명하는 몫 · idio = 혼자 움직이는 몫(1 − 지수 + 업종 설명)
               beta = 지수 민감도 · asym = 지수 내린 날 민감도 − 오른 날 민감도
업종 수익률 = 같은 업종 다른 종목들의 그날 수익률 중앙값(자기 빼고, 3종목 이상일 때) — 20년 내내 같은 방법으로 잴 수 있게.
크기 = 구간 안 하루 거래대금 중앙값(log). 지금 시가총액은 과거 구간에 맞지 않아서 쓰지 않는다.

특성 판정 기준 셋:
  1. 유지되나 — 붙은 두 구간 순위 상관(스피어만). 최근 구간 vs 바로 앞 구간 + 모든 붙은 쌍 평균
  2. 겹치나   — 최근 3년 구간에서 축끼리 순위 상관 |ρ| ≥ 0.8 이면 같은 것을 잰 것
  3. 업종 · 크기를 빼고도 남나 — 순위를 업종 + 크기로 설명한 몫(R²), 남은 값(잔차)의 붙은 구간 순위 상관
"""

import datetime
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
STORE = os.path.join(ROOT, "data", "store", "character")
DOC = os.path.abspath(os.path.join(ROOT, "..", "alphascope-docs", "doc", "검증", "종목-특성-1단계-검증.md"))
START = "2005-01-01"
LENGTHS = [2, 3, 5]            # 구간 길이(년) — 1단계에서 셋을 견줘 고른다
MIN_COVER = 0.9                # 구간 거래일의 90% 이상 있어야 그 구간에 넣는다
SKIP_NEW = 120                 # 상장(첫 일봉) 뒤 120거래일은 뺀다
WINSOR = 0.005                 # 흩어짐 · 회귀는 양 끝 0.5% 를 잘라 붙인다(자료 오류 · 한 날이 좌우하지 않게)
EXAMPLES = {"us": ["MSFT", "AAPL", "NVDA", "TSLA", "AMD", "KO", "JNJ", "JPM", "XOM"],
            "kr": ["005930.KS", "000660.KS", "005380.KS", "035420.KS", "086520.KQ", "247540.KQ", "105560.KS", "017670.KS"]}
METRICS = [("hl", "① 장중 폭"), ("gap", "① 밤사이 틈"), ("vol", "① 하루 등락 흩어짐"), ("er", "② 걸음걸이(곧은 정도)"),
           ("season", "③ 계절 변화"), ("r2_mkt", "⑦ 지수가 설명하는 몫"), ("r2_sec", "⑦ 업종이 더 설명하는 몫"),
           ("idio", "⑦ 혼자 움직이는 몫"), ("beta", "⑦ 지수 민감도"), ("asym", "⑦ 내릴 때 − 오를 때 민감도")]


# ─── 자료 ───────────────────────────────────────────────────────────────
def universe():
    u = json.load(open(os.path.join(ROOT, "experiments", "ref", "universe_all.json"), encoding="utf-8"))
    ref = json.load(open(os.path.join(ROOT, "experiments", "ref", "quick_ref.json"), encoding="utf-8"))
    us = {r["sym"].replace(".", "-"): {"sector": r["sector"], "name": r["name"], "bench": "^GSPC"} for r in u["us"]}
    kr = {}
    for r in u["kr"]:
        q = ref["kr"].get(r["sym"], {})
        kr[r["sym"]] = {"sector": q.get("sector") or ref["kr_sector"].get(r.get("industry"), "기타"),
                        "name": q.get("ko") or r["name"], "bench": "^KS11" if r["market"] == "KOSPI" else "^KQ11"}
    return {"us": us, "kr": kr}


def download(syms):
    out = {}
    for i in range(0, len(syms), 40):
        chunk = syms[i:i + 40]
        for attempt in range(3):
            try:
                df = yf.download(chunk, start=START, interval="1d", auto_adjust=True, progress=False,
                                 group_by="ticker", threads=True)
                break
            except Exception as e:  # noqa: BLE001
                print(f"  다시 시도 {attempt + 1}: {str(e)[:80]}")
                time.sleep(10)
        for s in chunk:
            try:
                d = df[s] if isinstance(df.columns, pd.MultiIndex) else df
                d = d.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
                d.index = pd.to_datetime(d.index).tz_localize(None)
                if len(d):
                    out[s] = d
            except Exception:  # noqa: BLE001
                pass
        print(f"  {min(i + 40, len(syms))}/{len(syms)} 받음")
        time.sleep(2)
    return out


def load_bars(mkt, syms, refresh):
    os.makedirs(STORE, exist_ok=True)
    path = os.path.join(STORE, f"bars_{mkt}.pkl")
    if os.path.exists(path) and not refresh:
        return pd.read_pickle(path)
    print(f"[{mkt}] 일봉 받기 {len(syms)}개 (2005~)")
    bars = download(syms)
    pd.to_pickle(bars, path)
    return bars


# ─── 축 계산 ─────────────────────────────────────────────────────────────
def clean(d):
    """잘못된 날 빼기 — 시가 · 고가 · 저가가 앞뒤가 안 맞거나, 거래가 없는 날(거래정지)."""
    ok = (d["open"] > 0) & (d["low"] > 0) & (d["high"] >= d[["open", "close"]].max(axis=1) * 0.999) & \
         (d["low"] <= d[["open", "close"]].min(axis=1) * 1.001) & (d["volume"] > 0)
    return d[ok]


def wins(x):
    lo, hi = np.nanquantile(x, [WINSOR, 1 - WINSOR])
    return np.clip(x, lo, hi)


def ols_r2(y, X):
    X = np.column_stack([np.ones(len(y)), X])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ coef
    return coef, 1 - res.var() / y.var()


def block_metrics(d, ret, m, sec):
    """한 종목 · 한 구간 → 축 값 dict. d = 그 구간 일봉, ret = 로그 수익률(전체 시계열), m · sec = 지수 · 업종 수익률."""
    out = {}
    hl = np.log(d["high"] / d["low"])
    out["hl"] = float(hl.median()) if (hl <= 1e-6).mean() < 0.1 else np.nan   # 고가 = 저가가 많으면 장중 자료 없음
    pc = d["close"].shift(1)
    gap = np.log(d["open"] / pc).abs().dropna()
    out["gap"] = float(gap.median()) if (gap <= 1e-6).mean() < 0.5 else np.nan  # 시가 = 전날 종가가 절반 넘으면 시가 자료 없음
    r = ret.reindex(d.index).dropna()
    out["vol"] = float(np.std(wins(r.values)) * np.sqrt(252))
    lc = np.log(d["close"])
    step = lc.diff().abs().rolling(20).sum()
    er = (lc - lc.shift(20)).abs() / step
    out["er"] = float(er.median())
    chunks = [r.values[i:i + 63] for i in range(0, len(r) - 62, 63)]
    sd = [np.std(c) for c in chunks if len(c) >= 50]
    out["season"] = float(np.std(np.log(sd))) if len(sd) >= 4 and min(sd) > 0 else np.nan
    j = pd.concat([r.rename("s"), m.rename("m"), sec.rename("k")], axis=1).dropna()
    if len(j) >= 200:
        s, mm = wins(j["s"].values), j["m"].values
        (_, b), r2m = ols_r2(s, mm)
        _, r2ms = ols_r2(s, np.column_stack([mm, j["k"].values]))
        up, dn = mm > 0, mm < 0
        bu = ols_r2(s[up], mm[up])[0][1]
        bd = ols_r2(s[dn], mm[dn])[0][1]
        out.update(r2_mkt=float(r2m), r2_sec=float(r2ms - r2m), idio=float(1 - r2ms), beta=float(b), asym=float(bd - bu))
    out["size"] = float(np.log((d["close"] * d["volume"]).median() + 1))
    return out


def blocks(end, years):
    """최근부터 거꾸로 붙은 구간 [(이름, 시작, 끝)] — 2005 이전으로는 안 간다."""
    out, e = [], pd.Timestamp(end)
    while True:
        s = e - pd.DateOffset(years=years) + pd.Timedelta(days=1)
        if s < pd.Timestamp(START) + pd.DateOffset(months=6):
            break
        out.append((f"{s.year}-{s.month:02d}~{e.year}-{e.month:02d}", s, e))
        e = s - pd.Timedelta(days=1)
    return out


def measure(mkt, uni, bars):
    idx = {b: clean(bars[b]) if b in bars else None for b in {v["bench"] for v in uni.values()}}
    rets, valid = {}, {}
    for s in uni:
        if s not in bars:
            continue
        d = clean(bars[s])
        if len(d) < 300:
            continue
        d = d.iloc[SKIP_NEW:]
        valid[s] = d
        rets[s] = np.log(d["close"]).diff()
    R = pd.DataFrame(rets)
    # 업종 수익률 = 같은 업종 다른 종목 중앙값(자기 빼고)
    sec_ret = {}
    by_sec = {}
    for s in R.columns:
        by_sec.setdefault(uni[s]["sector"], []).append(s)
    for sec_name, mem in by_sec.items():
        sub = R[mem]
        for s in mem:
            others = sub.drop(columns=[s])
            if others.shape[1] >= 3:
                cnt = others.notna().sum(axis=1)
                sec_ret[s] = others.median(axis=1).where(cnt >= 3)
    mret = {b: np.log(d["close"]).diff() for b, d in idx.items() if d is not None}
    end = max(d.index.max() for d in valid.values())
    rows = []
    for L in LENGTHS:
        for name, s0, e0 in blocks(end, L):
            mdays = idx[next(iter(idx))]
            nday = ((mdays.index >= s0) & (mdays.index <= e0)).sum()
            for s, d in valid.items():
                if s not in sec_ret:
                    continue
                db = d[(d.index >= s0) & (d.index <= e0)]
                if len(db) < MIN_COVER * nday:
                    continue
                b = uni[s]["bench"]
                mt = block_metrics(db, rets[s], mret[b], sec_ret[s])
                rows.append({"mkt": mkt, "L": L, "block": name, "start": s0.date(), "sym": s,
                             "sector": uni[s]["sector"], **mt})
        print(f"[{mkt}] {L}년 구간 계산 끝")
    return pd.DataFrame(rows), end


# ─── 판정 ───────────────────────────────────────────────────────────────
def spearman(a, b):
    j = pd.concat([a, b], axis=1).dropna()
    if len(j) < 30:
        return np.nan, len(j)
    return float(j.rank().corr().iloc[0, 1]), len(j)


def residual(df, col):
    """순위(0~1)를 업종 더미 + 크기로 설명 → (R², 잔차 Series)."""
    x = df[[col, "sector", "size"]].dropna()
    if len(x) < 30:
        return np.nan, pd.Series(dtype=float)
    y = x[col].rank(pct=True).values
    D = pd.get_dummies(x["sector"], drop_first=True).astype(float).values
    sz = (x["size"] - x["size"].mean()) / x["size"].std()
    X = np.column_stack([np.ones(len(y)), D, sz.values])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ coef
    return float(1 - res.var() / y.var()), pd.Series(res, index=x.index)


def judge(df):
    """시장 · 길이 · 축마다 유지(최근 쌍 · 평균) · 업종크기 설명 몫 · 잔차 유지."""
    out = []
    for L in LENGTHS:
        sub = df[df.L == L]
        names = sorted(sub.block.unique(), key=lambda n: sub[sub.block == n].start.iloc[0], reverse=True)
        piv = {n: sub[sub.block == n].set_index("sym") for n in names}
        for col, _ in METRICS:
            pairs = [spearman(piv[names[i]][col], piv[names[i + 1]][col]) for i in range(len(names) - 1)]
            r2s, rres = [], []
            resid = {n: residual(piv[n], col) for n in names}
            for i in range(len(names) - 1):
                rres.append(spearman(resid[names[i]][1], resid[names[i + 1]][1])[0])
            r2s = [resid[n][0] for n in names]
            out.append({"L": L, "axis": col, "recent": pairs[0][0] if pairs else np.nan, "n": pairs[0][1] if pairs else 0,
                        "mean": np.nanmean([p[0] for p in pairs]) if pairs else np.nan,
                        "min": np.nanmin([p[0] for p in pairs]) if pairs else np.nan, "npairs": len(pairs),
                        "r2_secsize": r2s[0], "resid_recent": rres[0] if rres else np.nan,
                        "resid_mean": np.nanmean(rres) if rres else np.nan})
    return pd.DataFrame(out)


def overlap(df, L=3):
    sub = df[df.L == L]
    recent = sub[sub.start == sub.start.max()].set_index("sym")[[c for c, _ in METRICS]]
    return recent.rank().corr()


def examples(df, mkt, uni, L=3):
    """예시 종목의 구간별 백분위(그 시장 안, 0 = 가장 작음 · 100 = 가장 큼)."""
    sub = df[df.L == L].copy()
    for col, _ in METRICS:
        sub[col + "_p"] = sub.groupby("block")[col].rank(pct=True) * 100
    lines = []
    for s in EXAMPLES[mkt]:
        x = sub[sub.sym == s].sort_values("start")
        if x.empty:
            lines.append(f"- {uni.get(s, {}).get('name', s)} ({s}): 자료 없음")
            continue
        lines.append(f"\n**{uni[s]['name']} ({s}, {uni[s]['sector']})** — 3년 구간별 백분위 (0 = 그 시장에서 가장 작음, 100 = 가장 큼)\n")
        lines.append("| 구간 | " + " | ".join(lbl for _, lbl in METRICS) + " |")
        lines.append("|---|" + "---:|" * len(METRICS))
        for _, r in x.iterrows():
            lines.append(f"| {r['block']} | " + " | ".join("—" if pd.isna(r[c + '_p']) else f"{r[c + '_p']:.0f}" for c, _ in METRICS) + " |")
    return "\n".join(lines)


# ─── 문서 ───────────────────────────────────────────────────────────────
def f2(x):
    return "—" if pd.isna(x) else f"{x:.2f}"


def write_doc(res, ends, counts):
    L = []
    L.append("# 종목 특성 1단계 검증 — 평소 모습 + 함께 움직임\n")
    L.append(f"만든 날 {datetime.date.today()} · 스크립트 `experiments/stock-character/check_stage1.py` (공개 저장소) · AI 0\n")
    L.append("## 0. 왜 하나 · 정의 (2026-11-23 사용자와 정함)\n")
    L.append("- 목적: 종목의 특성 파악. \"거칠다 / 느슨하다\" 2원론 대신 축을 나눠 잰다 — 호수(바탕 물결) · 돌(평소보다 훨씬 큰 날) · 여운 · 파도(시장 전체 하락) 반응.")
    L.append("- 큰 파도(전쟁 · 코로나 · 금융위기)는 종목 특성을 덮으므로 모양을 재지 않고 **지수 파도 때 잠긴 깊이 · 떠오르는 시간**으로 잰다(3단계).")
    L.append("- 기간: 20년 받고 3년씩 자른다. **최근 3년 = 특성 본값**, 과거 구간 = 비교 대상(원래 그런가 · 달라졌나). 구간 길이는 2 · 3 · 5년을 이 문서에서 견준다.")
    L.append("- 특성으로 인정하는 기준: ① 붙은 구간끼리 순위가 유지되나 ② 다른 축과 겹치지 않나 ③ 업종 · 크기를 빼고도 남나.")
    L.append("- 단계: **1 = 평소 모습(①②③) + 함께 움직임(⑦)** · 2 = 돌(④⑤⑥, 실적일 자료 필요) · 3 = 파도 반응(⑧, 최대 기간)\n")
    L.append("## 1. 자료\n")
    for mkt, (n_all, n_ok) in counts.items():
        L.append(f"- {'미국 S&P 500' if mkt == 'us' else '한국 코스피200 + 코스닥150'}: 목록 {n_all}종목 · 계산된 종목 {n_ok} · 마지막 날 {ends[mkt].date()}")
    L.append("- yfinance 수정 주가, 2005-01 ~. 상장 뒤 120거래일 뺌, 구간 거래일 90% 미만이면 그 구간 뺌, 거래 없는 날 · 고저가 안 맞는 날 뺌.")
    L.append("- 지수: 미국 S&P 500 · 한국 유가증권 = 코스피, 코스닥 종목 = 코스닥. 업종 수익률 = 같은 업종 다른 종목 중앙값(자기 빼고).")
    L.append("- 크기 = 구간 안 하루 거래대금 중앙값. 지금 시가총액은 과거 구간에 맞지 않아 안 씀.")
    L.append("- **생존 편향**: 지금 목록으로 과거를 봄 — 상장폐지 · 지수에서 빠진 종목이 없다. 오래된 구간일수록 \"살아남은 종목\"만 남는다.")
    L.append("- **한국 가격 제한폭**: 2015-06 전 ±15% → 뒤 ±30%. 1단계 값은 중앙값 위주라 영향이 작지만, 흩어짐(vol)은 그 전 구간이 덜 크게 나올 수 있다.\n")
    L.append("## 2. 축 정의 (1단계)\n")
    L.append("| 축 | 칸 | 재는 법 |\n|---|---|---|")
    L.append("| ① 바탕 물결 | hl 장중 폭 | 하루 log(고가/저가)의 구간 중앙값 |")
    L.append("| | gap 밤사이 틈 | 하루 |log(시가/전날 종가)| 중앙값 |")
    L.append("| | vol 하루 등락 흩어짐 | 로그 수익률 표준편차 × √252 (양 끝 0.5% 잘라 붙임) |")
    L.append("| ② 걸음걸이 | er | 20일 동안 간 거리 ÷ 오르내린 거리 합, 구간 중앙값. 1 = 곧게, 0 = 제자리 |")
    L.append("| ③ 계절 변화 | season | 63일 조각마다 흩어짐 → 조각끼리 log 값의 표준편차. 클수록 시기마다 달라짐 |")
    L.append("| ⑦ 함께 움직임 | r2_mkt | 지수 수익률로 설명되는 몫(R²) |")
    L.append("| | r2_sec | 지수에 업종을 더했을 때 늘어나는 R² |")
    L.append("| | idio | 1 − (지수 + 업종) R² = 혼자 움직이는 몫 |")
    L.append("| | beta | 지수 민감도 |")
    L.append("| | asym | 지수 내린 날 민감도 − 오른 날 민감도. + 면 내릴 때 더 따라감 |\n")
    for mkt in ("us", "kr"):
        r = res[mkt]
        J = r["judge"]
        L.append(f"## {'3' if mkt == 'us' else '4'}. {'미국' if mkt == 'us' else '한국'}\n")
        L.append("### 유지되나 — 붙은 두 구간 순위 상관 (1 = 순위 그대로, 0 = 관계 없음)\n")
        L.append("최근 = 최근 구간 vs 바로 앞 구간. 평균 · 최저 = 모든 붙은 쌍. 잔차 = 업종 · 크기를 뺀 뒤 남은 값의 순위 상관. 업종·크기 R² = 최근 구간 순위를 업종 + 크기가 설명하는 몫.\n")
        L.append("| 축 | 길이 | 최근 | 평균 | 최저 | 쌍 수 | 종목 수 | 업종·크기 R² | 잔차 최근 | 잔차 평균 |")
        L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for col, lbl in METRICS:
            for _, x in J[J.axis == col].iterrows():
                L.append(f"| {lbl if x['L'] == LENGTHS[0] else ''} | {x['L']}년 | {f2(x['recent'])} | {f2(x['mean'])} | {f2(x['min'])} | "
                         f"{x['npairs']} | {x['n']} | {f2(x['r2_secsize'])} | {f2(x['resid_recent'])} | {f2(x['resid_mean'])} |")
        L.append("\n### 겹치나 — 최근 3년 구간, 축끼리 순위 상관 (|ρ| ≥ 0.8 = 같은 것을 잰 것)\n")
        C = r["overlap"]
        cols = [c for c, _ in METRICS]
        L.append("| | " + " | ".join(cols) + " |")
        L.append("|---|" + "---:|" * len(cols))
        for a in cols:
            L.append(f"| {a} | " + " | ".join(("**" + f2(C.loc[a, b]) + "**") if a != b and abs(C.loc[a, b]) >= 0.8 else f2(C.loc[a, b]) for b in cols) + " |")
        L.append("\n### 예시 종목\n")
        L.append(r["examples"])
        L.append("")
    head = "\n## 5. 판정 · 다음\n"
    old = open(DOC, encoding="utf-8").read() if os.path.exists(DOC) else ""
    L.append(head + old.split(head, 1)[1] if head in old else head + "\n(아래는 결과를 보고 사람이 쓴다 — 다시 돌려도 이 절은 그대로 둔다)\n")
    os.makedirs(os.path.dirname(DOC), exist_ok=True)
    open(DOC, "w", encoding="utf-8").write("\n".join(L))
    print(f"문서 → {DOC}")


def main():
    refresh = "--refresh" in sys.argv
    U = universe()
    res, ends, counts, alldf = {}, {}, {}, []
    for mkt in ("us", "kr"):
        uni = U[mkt]
        benches = sorted({v["bench"] for v in uni.values()})
        bars = load_bars(mkt, list(uni) + benches, refresh)
        df, end = measure(mkt, uni, bars)
        alldf.append(df)
        ends[mkt] = end
        counts[mkt] = (len(uni), df.sym.nunique())
        res[mkt] = {"judge": judge(df), "overlap": overlap(df), "examples": examples(df, mkt, uni)}
        print(res[mkt]["judge"].round(2).to_string())
    pd.concat(alldf).to_csv(os.path.join(STORE, "stage1_metrics.csv.gz"), index=False)
    write_doc(res, ends, counts)


if __name__ == "__main__":
    main()
