"""엔비디아 볼린저 하단 · 상단 진입 — 이슈 · 상황별 검증 (doc/볼린저-이슈별-검증-계획.md 3절 규칙 그대로).

    python experiments/issue_store/bollinger_by_issue.py

- 진입일: 종가가 볼린저(20일) 2σ · 1.5σ 하단 이하(상단 이상)로 처음 들어간 날 (연속 구간 첫날)
- 결과: 진입일 종가 → 1 · 5 · 10 · 20거래일 뒤 종가 수익률. 오른 비율 · 중앙값 · 나쁜 쪽 10%
- 비교(일반적인 날): **같은 묶음에 속한 모든 날** 의 같은 기간 수익률
- 묶음: 그날 아침에 알 수 있던 것만 — 캘린더(발표일 ±1) · 사건 기간 · 시장 상태(전날 종가) · 엔비디아 추세 · 회사 시기
- 판정: n ≥ 30 (엔비디아 단독은 '참고' 수준), 차이의 블록 부트스트랩(월 단위) 양측 p → 전체 칸 BH 보정 q < 0.1,
        두 기간(1999~2012 · 2013~2026) 방향 일치 — 셋 다 넘어야 '효과 있음'
결과: results/bollinger_nvda.md · bollinger_nvda.csv
"""

import os

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STORE = os.path.join(ROOT, "data", "store")
CAL = os.path.join(STORE, "calendar")
OUT = os.path.join(os.path.dirname(__file__), "results")
HZ = [1, 5, 10, 20]
MAIN_HZ = [1, 5, 10]   # 판정은 단기 (사용자 2026-10-17), 20일은 참고
SPLIT = pd.Timestamp("2013-01-01")
N_MIN, Q_MAX, BOOT = 30, 0.10, 2000
rng = np.random.default_rng(20261017)


def bars(sym):
    return pd.read_parquet(os.path.join(STORE, "bars", sym + ".parquet"))


def near(days, idx, before=1, after=1):
    """발표일 집합 → 거래일 기준 ±창 안에 드는 날 표시."""
    pos = idx.searchsorted(pd.DatetimeIndex(sorted(set(days))))
    m = np.zeros(len(idx), bool)
    for p in pos:
        m[max(0, p - before):min(len(idx), p + after + 1)] = True
    return pd.Series(m, index=idx)


def build():
    nv = bars("NVDA")
    c = nv["close"]
    idx = c.index
    fwd = {h: c.shift(-h) / c - 1 for h in HZ}
    ma, sd = c.rolling(20).mean(), c.rolling(20).std()
    sig = {}
    for k in (2.0, 1.5):
        lo, hi = c <= ma - k * sd, c >= ma + k * sd
        sig[f"하단 {k}σ"] = lo & ~lo.shift(1, fill_value=False)
        sig[f"상단 {k}σ"] = hi & ~hi.shift(1, fill_value=False)

    # 묶음 (그날 아침에 아는 것 — 시장 · 추세 값은 전날 종가 기준)
    g = {}
    g["전체"] = pd.Series(True, index=idx)
    # 회사 시기
    for a, b, name in (("1999", "2008", "1999~2008 초창기"), ("2009", "2015", "2009~2015 중기"), ("2016", "2022", "2016~2022 성장기"), ("2023", "2026", "2023~2026 폭발기")):
        g["회사 시기 · " + name] = pd.Series((idx >= a) & (idx <= b + "-12-31"), index=idx)
    # 엔비디아 추세 · 변동성 (전날까지)
    r1y = (c / c.shift(252) - 1).shift(1) * 100
    for lo_, hi_, name in ((-1e9, -20, "−20% 아래"), (-20, 0, "−20~0%"), (0, 30, "0~30%"), (30, 100, "30~100%"), (100, 1e9, "100% 위")):
        g["엔비디아 1년 수익률 · " + name] = (r1y > lo_) & (r1y <= hi_)
    ma200 = c.rolling(200).mean()
    slope = (ma200 / ma200.shift(250) - 1).shift(1) * 100
    for lo_, hi_, name in ((-1e9, -5, "내림"), (-5, 5, "평평"), (5, 40, "완만한 오름"), (40, 1e9, "가파른 오름")):
        g["200일선 기울기 · " + name] = (slope > lo_) & (slope <= hi_)
    rng60 = ((c.rolling(60).max() / c.rolling(60).min() - 1) * 100).shift(1)
    g["횡보 (60일 고저 폭 25% 안)"] = rng60 <= 25   # 엔비디아는 15% 안 횡보가 드물어 25% (계획 2-F 경계값 조정 — 결과 보기 전)
    vol = (c.pct_change().rolling(20).std() * 100).shift(1)
    for lo_, hi_, name in ((0, 2, "2% 아래"), (2, 3, "2~3%"), (3, 5, "3~5%"), (5, 1e9, "5% 위")):
        g["엔비디아 하루 변동성 · " + name] = (vol > lo_) & (vol <= hi_)
    # 시장 상태 (S&P 500 · VIX, 전날 종가)
    sp = bars("_GSPC")["close"].reindex(idx).ffill()
    above = (sp > sp.rolling(200).mean()).shift(1)
    g["시장 · S&P 500 200일선 위"] = above == True
    g["시장 · S&P 500 200일선 아래"] = above == False
    dd = ((sp / sp.cummax() - 1) * 100).shift(1)
    for lo_, hi_, name in ((-5, 0.1, "고점 −5% 안"), (-10, -5, "−5~−10%"), (-20, -10, "−10~−20%"), (-100, -20, "−20% 아래")):
        g["시장 낙폭 · " + name] = (dd > lo_) & (dd <= hi_)
    vix = bars("_VIX")["close"].reindex(idx).ffill().shift(1)
    for lo_, hi_, name in ((0, 15, "15 아래"), (15, 20, "15~20"), (20, 30, "20~30"), (30, 1e9, "30 위")):
        g["VIX · " + name] = (vix > lo_) & (vix <= hi_)
    # 캘린더 (발표일 ±1거래일)
    ec = pd.read_csv(os.path.join(CAL, "econ_releases.csv"), parse_dates=["day"])
    for sub in ("CPI", "고용 보고서", "PCE", "PPI", "GDP", "소매판매"):
        g["경제지표 · " + sub + " ±1일"] = near(ec[ec.subkind == sub].day, idx)
    fo = pd.read_csv(os.path.join(CAL, "fomc.csv"), parse_dates=["day"])
    for dec in ("인상", "동결", "인하"):
        g["FOMC · " + dec + " ±1일"] = near(fo[fo.decision == dec].day, idx)
    g["FOMC · 긴급 결정 ±1일"] = near(fo[(~fo.scheduled.astype(bool)) & fo.decision.isin(["인상", "인하"])].day, idx)
    er = pd.read_csv(os.path.join(CAL, "earnings.csv"), parse_dates=["day"])
    g["엔비디아 실적 · 발표 다음 날 ±1일"] = near(er.day, idx, 0, 2)   # 장 마감 뒤 발표 → 다음 날부터
    for band in ("크게 상회", "상회", "부합", "하회"):
        g["엔비디아 실적 · " + band] = near(er[er.surprise_band == band].day, idx, 0, 2)
    ms = pd.read_csv(os.path.join(CAL, "market_structure.csv"), parse_dates=["day"])
    g["시장 구조 · 옵션 만기 ±1일"] = near(ms[ms.subkind.isin(["월간 옵션 만기", "네 마녀의 날"])].day, idx)
    g["시장 구조 · 분기 말 ±1일"] = near(ms[ms.subkind.isin(["분기 말", "연말"])].day, idx)
    # 사건 기간 (사건표, 시작일 ~ +window_days 거래일)
    ev = pd.read_csv(os.path.join(ROOT, "experiments", "issue_store", "events_curated.csv"), parse_dates=["start"])
    ev = ev[ev.confidence.astype(str).str.contains("기억|기사 확인")]
    for kind, sub in ev.groupby("kind"):
        m = np.zeros(len(idx), bool)
        for _, r in sub.iterrows():
            p = idx.searchsorted(r.start)
            m[p:min(len(idx), p + int(r.window_days))] = True
        g["사건 · " + kind] = pd.Series(m, index=idx)
    nvd = ev[ev.symbols.fillna("").str.contains("NVDA|SMH|\\^SOX")]
    m = np.zeros(len(idx), bool)
    for _, r in nvd.iterrows():
        p = idx.searchsorted(r.start); m[p:min(len(idx), p + int(r.window_days))] = True
    g["사건 · 엔비디아 · 반도체 관련"] = pd.Series(m, index=idx)
    g = {k: v.reindex(idx).fillna(False).astype(bool) for k, v in g.items()}
    return idx, fwd, sig, g


def boot_p(entry_fwd, base_rate, months):
    """오른 비율 차이의 양측 p — 진입일을 달 단위 블록으로 다시 뽑는다 (가까운 진입일끼리의 겹침 반영)."""
    up = (entry_fwd > 0).astype(float)
    groups = pd.Series(up.values).groupby(months.values)
    blocks = [v.values for _, v in groups]
    if len(blocks) < 5:
        return np.nan
    obs = up.mean() - base_rate
    diffs = np.empty(BOOT)
    for i in range(BOOT):
        pick = rng.integers(0, len(blocks), len(blocks))
        diffs[i] = np.concatenate([blocks[j] for j in pick]).mean() - base_rate
    centered = diffs - diffs.mean()
    return float(np.mean(np.abs(centered) >= abs(obs)))


def run():
    idx, fwd, sig, groups = build()
    rows = []
    for sname, s in sig.items():
        for gname, gm in groups.items():
            ent = s & gm
            for h in HZ:
                f = fwd[h]
                e = f[ent].dropna()
                b = f[gm].dropna()
                if len(e) < 5 or len(b) < 50:
                    continue
                r = {"신호": sname, "묶음": gname, "기간": h, "n": len(e), "오른 비율": 100 * (e > 0).mean(), "일반 오른 비율": 100 * (b > 0).mean(),
                     "중앙값": 100 * e.median(), "일반 중앙값": 100 * b.median(), "나쁜 쪽 10%": 100 * e.quantile(.1), "일반 나쁜 쪽 10%": 100 * b.quantile(.1)}
                r["차이"] = r["오른 비율"] - r["일반 오른 비율"]
                r["p"] = boot_p(e, (b > 0).mean(), e.index.to_period("M")) if len(e) >= N_MIN and h in MAIN_HZ else np.nan
                # 두 기간 방향 (1999~2012 · 2013~2026)
                e1, e2 = e[e.index < SPLIT], e[e.index >= SPLIT]
                b1, b2 = b[b.index < SPLIT], b[b.index >= SPLIT]
                d1 = (100 * (e1 > 0).mean() - 100 * (b1 > 0).mean()) if len(e1) >= 5 and len(b1) >= 50 else np.nan
                d2 = (100 * (e2 > 0).mean() - 100 * (b2 > 0).mean()) if len(e2) >= 5 and len(b2) >= 50 else np.nan
                r["차이 1999~2012"], r["차이 2013~2026"] = d1, d2
                r["n 1999~2012"], r["n 2013~2026"] = len(e1), len(e2)
                rows.append(r)
    df = pd.DataFrame(rows)
    # BH 보정 — 판정 대상 칸(n ≥ 30, 단기)만
    m = df["p"].notna()
    p = df.loc[m, "p"].values
    order = np.argsort(p)
    q = np.empty_like(p)
    q[order] = np.minimum.accumulate((p[order] * len(p) / np.arange(1, len(p) + 1))[::-1])[::-1]
    df.loc[m, "q"] = np.minimum(q, 1)
    same = np.sign(df["차이 1999~2012"]) == np.sign(df["차이 2013~2026"])
    df["판정"] = np.where(m & (df["q"] < Q_MAX) & same & (df["n"] >= N_MIN), "효과 있음",
                        np.where(df["n"] < N_MIN, "표본 부족", "뚜렷한 차이 없음"))
    return df.round(2)


def report(df):
    os.makedirs(OUT, exist_ok=True)
    df.to_csv(os.path.join(OUT, "bollinger_nvda.csv"), index=False)
    lines = ["# 엔비디아 볼린저 — 이슈 · 상황별 결과", "",
             f"생성 {pd.Timestamp.today().date()} · 규칙 doc/볼린저-이슈별-검증-계획.md 3절 · 판정 = n ≥ {N_MIN} · BH q < {Q_MAX} · 두 기간 방향 일치 (단기 1 · 5 · 10일)", ""]
    eff = df[df["판정"] == "효과 있음"].sort_values(["신호", "묶음", "기간"])
    lines += [f"## 효과 있음 — {len(eff)}칸", ""]
    cols = ["신호", "묶음", "기간", "n", "오른 비율", "일반 오른 비율", "차이", "중앙값", "일반 중앙값", "나쁜 쪽 10%", "차이 1999~2012", "차이 2013~2026", "q"]
    if len(eff):
        lines += ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(str(r[c]) for c in cols) + " |" for _, r in eff.iterrows()]
    for s in ("하단 2.0σ", "하단 1.5σ", "상단 2.0σ"):
        sub = df[(df["신호"] == s) & (df["기간"].isin([5, 10]))].sort_values("차이", ascending=False)
        lines += ["", f"## {s} — 5 · 10일, 전체 묶음 (차이 순)", "", "| 묶음 | 기간 | n | 오른 비율 | 일반 | 차이 | 중앙값 | 일반 중앙값 | 나쁜 쪽 10% | 1999~2012 | 2013~2026 | q | 판정 |", "|" + "---|" * 13]
        lines += [f"| {r['묶음']} | {r['기간']} | {r['n']} | {r['오른 비율']:.0f}% | {r['일반 오른 비율']:.0f}% | {r['차이']:+.0f} | {r['중앙값']:+.1f}% | {r['일반 중앙값']:+.1f}% | {r['나쁜 쪽 10%']:+.1f}% | "
                  f"{r['차이 1999~2012']:+.0f} | {r['차이 2013~2026']:+.0f} | {r['q'] if pd.notna(r['q']) else '-'} | {r['판정']} |" for _, r in sub.iterrows()]
    open(os.path.join(OUT, "bollinger_nvda.md"), "w", encoding="utf-8").write("\n".join(lines).replace("nan", "-"))
    print(f"칸 {len(df)} · 판정 대상 {int(df['p'].notna().sum())} · 효과 있음 {len(eff)} → results/bollinger_nvda.md")


if __name__ == "__main__":
    report(run())
