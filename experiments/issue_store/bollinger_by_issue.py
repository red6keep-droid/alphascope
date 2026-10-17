"""엔비디아 볼린저 하단 · 상단 진입 — 이슈 · 상황별 검증 (doc/볼린저-이슈별-검증-계획.md 3절 규칙 그대로).

    python experiments/issue_store/bollinger_by_issue.py

- 진입일: 종가가 볼린저(20일) 2σ · 1.5σ 하단 이하(상단 이상)로 처음 들어간 날 (연속 구간 첫날)
- 결과: 진입일 종가 → 1 · 5 · 10 · 20거래일 뒤 종가 수익률. 오른 비율 · 중앙값 · 나쁜 쪽 10%
- 비교 둘 (2026-10-17 사용자: "둘 다 보여줘"):
    구간 대비 = **같은 묶음에 속한 모든 날** — 그 구간에서 볼린저가 더 알려 주는 게 있나 (리포트의 '볼린저 효과' 문장은 이것만)
    전체 대비 = **1999~ 모든 날** — 그 구간의 하단 진입이 평소보다 나은가 (구간 자체의 힘이 섞인다)
- 묶음: 그날 아침에 알 수 있던 것만 — 캘린더(발표일 ±1) · 사건 기간 · 시장 상태(전날 종가) · 엔비디아 추세 · 회사 시기
- 판정: n ≥ 30 (엔비디아 단독은 '참고' 수준), 차이의 블록 부트스트랩(월 단위) 양측 p → 전체 칸 BH 보정 q < 0.1,
        두 기간(1999~2012 · 2013~2026) 방향 일치 — 셋 다 넘어야 '효과 있음'. 두 비교에 같은 규칙, 보정은 비교별로 따로
- 가설 H1 · H2 · H3 · H5 (2026-10-17 사용자 확정) 는 구간 가족 — 하락이 시장 동반인가 · 스퀴즈 직후인가 · 갭인가 · 200일선 위인가
- 묶음 두 가족 (2026-10-17 사용자: "떼어내") — **구간**(회사 시기 · 추세 · 성장 · 변동성 · 시장 상태, 사용자 가설) 과
        **이슈**(경제지표 · FOMC · 실적 · 시장 구조 · 사건 · 큰 움직임). BH 보정은 가족 안에서만 — 이슈 칸 수가 구간 판정을 엄격하게 만들지 않게
결과: results/bollinger_nvda.md · bollinger_nvda.csv
"""

import os

import numpy as np
import pandas as pd

from event_vocab import check as check_vocab

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STORE = os.path.join(ROOT, "data", "store")
CAL = os.path.join(STORE, "calendar")
OUT = os.path.join(os.path.dirname(__file__), "results")
HZ = [1, 5, 10, 20]
MAIN_HZ = [1, 5, 10]   # 판정은 단기 (사용자 2026-10-17), 20일은 참고
SPLIT = pd.Timestamp("2013-01-01")
N_MIN, Q_MAX, BOOT = 30, 0.10, 2000
REGIME = ("전체", "회사 시기", "엔비디아 1년 수익률", "200일선 기울기", "횡보", "엔비디아 하루 변동성", "시장 ·", "시장 낙폭", "VIX",
          "H1 ", "H2 ", "H3 ", "H5 ")   # 구간 가족 (나머지는 이슈)
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
    # 하락의 성격 — 가설 H1 · H2 · H3 · H5 (2026-10-17 사용자 확정, 볼린저 계획 4-5, 결과 보기 전 고정)
    # H1 시장 동반 vs 엔비디아만: 진입일까지 5일 엔비디아 − 반도체 지수(^SOX, 1994~) 수익률 (%p)
    sox = bars("_SOX")["close"].reindex(idx).ffill()
    rel5 = ((c / c.shift(5)) - (sox / sox.shift(5))) * 100
    g["H1 하락 성격 · 엔비디아만 (반도체 대비 −5%p 아래)"] = rel5 <= -5
    g["H1 하락 성격 · 섞임 (−5~−2%p)"] = (rel5 > -5) & (rel5 <= -2)
    g["H1 하락 성격 · 시장 동반 (−2%p 위)"] = rel5 > -2
    # H2 스퀴즈: 전날 밴드 폭(4σ ÷ 평균)이 지난 252일 중 몇 번째로 좁은가
    width = (4 * sd / ma).shift(1)
    wrank = width.rolling(252).rank(pct=True)
    g["H2 밴드 폭 · 좁음 (1년 중 하위 20%, 스퀴즈)"] = wrank <= 0.2
    g["H2 밴드 폭 · 중간"] = (wrank > 0.2) & (wrank < 0.8)
    g["H2 밴드 폭 · 넓음 (상위 20%)"] = wrank >= 0.8
    # H3 갭 하락: 그날 시가 ÷ 전날 종가
    gap = (nv["open"] / c.shift(1) - 1) * 100
    g["H3 시가 갭 · −3% 아래 (갭 하락)"] = gap <= -3
    g["H3 시가 갭 · −3% 위"] = gap > -3
    # H5 장기 추세 위치: 전날 종가가 200일선 위 · 아래
    pos200 = (c > ma200).shift(1)
    g["H5 200일선 위치 · 위"] = pos200 == True
    g["H5 200일선 위치 · 아래"] = pos200 == False
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
    for sub in sorted(ec.subkind.unique()):   # 저장소의 경제지표 전부 (2026-10-17 사용자: 확보한 이슈 포함)
        g["경제지표 · " + sub + " ±1일"] = near(ec[ec.subkind == sub].day, idx)
    for grp in sorted(ec.group.unique()):
        g["경제지표 분류 · " + grp + " ±1일"] = near(ec[ec.group == grp].day, idx)
    fo = pd.read_csv(os.path.join(CAL, "fomc.csv"), parse_dates=["day"])
    for dec in ("인상", "동결", "인하"):
        g["FOMC · " + dec + " ±1일"] = near(fo[fo.decision == dec].day, idx)
    g["FOMC · 긴급 결정 ±1일"] = near(fo[(~fo.scheduled.astype(bool)) & fo.decision.isin(["인상", "인하"])].day, idx)
    er = pd.read_csv(os.path.join(CAL, "earnings.csv"), parse_dates=["day"])
    er = er[er.symbol == "NVDA"]   # 실적표는 15종목 (2026-10-17)
    g["엔비디아 실적 · 발표 다음 날 ±1일"] = near(er.day, idx, 0, 2)   # 장 마감 뒤 발표 → 다음 날부터
    for band in ("크게 상회", "상회", "부합", "하회"):
        g["엔비디아 실적 · " + band] = near(er[er.surprise_band == band].day, idx, 0, 2)
    ms = pd.read_csv(os.path.join(CAL, "market_structure.csv"), parse_dates=["day"])
    g["시장 구조 · 옵션 만기 ±1일"] = near(ms[ms.subkind.isin(["월간 옵션 만기", "네 마녀의 날"])].day, idx)
    g["시장 구조 · 분기 말 ±1일"] = near(ms[ms.subkind.isin(["분기 말", "연말"])].day, idx)
    # 사건 기간 (사건표, 시작일 ~ +window_days 거래일)
    ev = pd.read_csv(os.path.join(ROOT, "experiments", "issue_store", "events_curated.csv"), parse_dates=["start"])
    check_vocab(ev)   # 세부 종류는 고정 어휘 21개 (event_vocab.py)
    ev = ev[ev.confidence.astype(str).str.contains("기억|기사 확인")]
    for subk, sub in ev.dropna(subset=["subkind"]).groupby("subkind"):   # 세부 종류 (전쟁 · 테러 · 관세 · 무역 · 연준 긴축 신호 …)
        m = np.zeros(len(idx), bool)
        for _, r in sub.iterrows():
            p = idx.searchsorted(r.start)
            m[p:min(len(idx), p + int(r.window_days))] = True
        g["사건 세부 · " + subk] = pd.Series(m, index=idx)
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
    # 큰 움직임 직후 (detect_shocks.py, 데이터 오류 제외) — 그날 ~ 5거래일
    sh = pd.read_csv(os.path.join(CAL, "shocks.csv"), parse_dates=["day"])
    g["큰 움직임 직후 · 아무 시장 (5일 안)"] = near(sh.day, idx, 0, 5)
    for mk in sorted(sh.market.unique()):
        g["큰 움직임 직후 · " + mk + " (5일 안)"] = near(sh[sh.market == mk].day, idx, 0, 5)
    g["큰 움직임 직후 · 원인 미확인 (5일 안)"] = near(sh[sh.explained_by.isna()].day, idx, 0, 5)
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


DROPPED = []


def compare(e, b, tag):
    """진입일 수익률 e 를 비교 날 b 와 — 오른 비율 차이 · p · 두 기간 차이. tag = '' (구간 대비) 또는 '전체 ' (전체 대비)."""
    r = {tag + "비교 오른 비율" if tag else "일반 오른 비율": 100 * (b > 0).mean()}
    base = r[tag + "비교 오른 비율" if tag else "일반 오른 비율"]
    r[tag + "차이"] = 100 * (e > 0).mean() - base
    e1, e2 = e[e.index < SPLIT], e[e.index >= SPLIT]
    b1, b2 = b[b.index < SPLIT], b[b.index >= SPLIT]
    r[tag + "차이 1999~2012"] = (100 * (e1 > 0).mean() - 100 * (b1 > 0).mean()) if len(e1) >= 1 and len(b1) >= 10 else np.nan
    r[tag + "차이 2013~2026"] = (100 * (e2 > 0).mean() - 100 * (b2 > 0).mean()) if len(e2) >= 1 and len(b2) >= 10 else np.nan
    return r


def verdict(df, tag):
    """BH 보정(판정 대상 칸만, 가족 안에서) + 판정 — 비교별로 따로."""
    m = df[tag + "p"].notna()
    for fam in df["가족"].unique():
        mf = m & (df["가족"] == fam)
        p = df.loc[mf, tag + "p"].values
        order = np.argsort(p)
        q = np.empty_like(p)
        q[order] = np.minimum.accumulate((p[order] * len(p) / np.arange(1, len(p) + 1))[::-1])[::-1]
        df.loc[mf, tag + "q"] = np.minimum(q, 1)
    same = np.sign(df[tag + "차이 1999~2012"]) == np.sign(df[tag + "차이 2013~2026"])
    return np.where(m & (df[tag + "q"] < Q_MAX) & same & (df["n"] >= N_MIN), "효과 있음",
                    np.where(df["n"] == 0, "진입 없음", np.where(df["n"] < N_MIN, "표본 부족", "뚜렷한 차이 없음")))


def run():
    idx, fwd, sig, groups = build()
    for gname, gm in groups.items():
        if int(gm.sum()) < 10:
            DROPPED.append((gname, int(gm.sum())))
    rows = []
    for sname, s in sig.items():
        for gname, gm in groups.items():
            ent = s & gm
            for h in HZ:
                f = fwd[h]
                e = f[ent].dropna()
                b = f[gm].dropna()
                if len(b) < 10:   # 묶음 날 자체가 10일 미만이면 비교 불가 — 아래 '빠진 묶음' 에 이유와 함께 남는다
                    continue
                a = f.dropna()   # 전체 대비 — 1999~ 모든 날
                if len(e) == 0:   # 이 묶음 기간에 진입이 없었다 — 표에 n 0 으로 남긴다
                    rows.append({"신호": sname, "묶음": gname, "기간": h, "n": 0, "일반 오른 비율": 100 * (b > 0).mean(),
                                 "전체 비교 오른 비율": 100 * (a > 0).mean(), "묶음 날 수": len(b)})
                    continue
                r = {"신호": sname, "묶음": gname, "기간": h, "n": len(e), "묶음 날 수": len(b), "오른 비율": 100 * (e > 0).mean(),
                     "중앙값": 100 * e.median(), "일반 중앙값": 100 * b.median(), "전체 중앙값": 100 * a.median(),
                     "나쁜 쪽 10%": 100 * e.quantile(.1), "일반 나쁜 쪽 10%": 100 * b.quantile(.1)}
                judged = len(e) >= N_MIN and h in MAIN_HZ
                for base, tag in ((b, ""), (a, "전체 ")):
                    r.update(compare(e, base, tag))
                    r[tag + "p"] = boot_p(e, (base > 0).mean(), e.index.to_period("M")) if judged else np.nan
                r["n 1999~2012"], r["n 2013~2026"] = int((e.index < SPLIT).sum()), int((e.index >= SPLIT).sum())
                rows.append(r)
    df = pd.DataFrame(rows)
    df.insert(0, "가족", np.where(df["묶음"].str.startswith(REGIME), "구간", "이슈"))
    df["판정"] = verdict(df, "")             # 구간 대비 — 리포트의 '볼린저 효과' 문장은 이것만
    df["전체 대비 판정"] = verdict(df, "전체 ")
    return df.round(2)


def report(df):
    os.makedirs(OUT, exist_ok=True)
    df.to_csv(os.path.join(OUT, "bollinger_nvda.csv"), index=False)
    lines = ["# 엔비디아 볼린저 — 이슈 · 상황별 결과", "",
             f"생성 {pd.Timestamp.today().date()} · 규칙 doc/볼린저-이슈별-검증-계획.md 3절 · 판정 = n ≥ {N_MIN} · BH q < {Q_MAX} · 두 기간 방향 일치 (단기 1 · 5 · 10일)", ""]
    lines += ["비교 둘: **구간 대비** = 같은 묶음의 모든 날 (볼린저가 그 구간에서 더 알려 주나 — 리포트 문장 기준) · "
              "**전체 대비** = 1999~ 모든 날 (그 구간의 하단 진입이 평소보다 나은가 — 구간 자체의 힘이 섞임)", ""]
    for fam, col, tag, title in ((f, c, t, f"{f} 가족 · {ti}") for f in ("구간", "이슈")
                                 for c, t, ti in (("판정", "", "구간 대비"), ("전체 대비 판정", "전체 ", "전체 대비"))):
        eff = df[(df["가족"] == fam) & (df[col] == "효과 있음")].sort_values(["신호", "묶음", "기간"])
        base = "일반 오른 비율" if not tag else "전체 비교 오른 비율"
        lines += [f"## 효과 있음 ({title}) — {len(eff)}칸", ""]
        cols = ["신호", "묶음", "기간", "n", "오른 비율", base, tag + "차이", "중앙값", "나쁜 쪽 10%", tag + "차이 1999~2012", tag + "차이 2013~2026", tag + "q",
                "판정" if tag else "전체 대비 판정"]
        if len(eff):
            lines += ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(str(r[c]) for c in cols) + " |" for _, r in eff.iterrows()]
        lines += [""]
    for fam, s in ((f, s) for f in ("구간", "이슈") for s in ("하단 2.0σ", "하단 1.5σ", "상단 2.0σ")):
        sub = df[(df["가족"] == fam) & (df["신호"] == s) & (df["기간"].isin([5, 10]))].sort_values("차이", ascending=False)
        lines += ["", f"## {fam} 가족 · {s} — 5 · 10일 (구간 대비 차이 순)", "",
                  "| 묶음 | 기간 | n | 오른 비율 | 구간 아무 날 | 구간 대비 차이 | 전체 아무 날 | 전체 대비 차이 | 중앙값 | 나쁜 쪽 10% | 1999~2012 | 2013~2026 | q | 판정 (구간) | 판정 (전체) |", "|" + "---|" * 15]
        lines += [f"| {r['묶음']} | {r['기간']} | {r['n']} | {r['오른 비율']:.0f}% | {r['일반 오른 비율']:.0f}% | {r['차이']:+.0f} | {r['전체 비교 오른 비율']:.0f}% | {r['전체 차이']:+.0f} | "
                  f"{r['중앙값']:+.1f}% | {r['나쁜 쪽 10%']:+.1f}% | {r['차이 1999~2012']:+.0f} | {r['차이 2013~2026']:+.0f} | {r['q'] if pd.notna(r['q']) else '-'} | {r['판정']} | {r['전체 대비 판정']} |"
                  for _, r in sub.iterrows()]
    lines += ["", "## 비교할 날이 10일 미만이라 뺀 묶음", ""] + [f"- {n} ({k}일)" for n, k in DROPPED]
    open(os.path.join(OUT, "bollinger_nvda.md"), "w", encoding="utf-8").write("\n".join(lines).replace("nan", "-"))
    for fam, d in df.groupby("가족"):
        print(f"{fam} 가족: 칸 {len(d)} · 판정 대상 {int(d['p'].notna().sum())} · 효과 있음 구간 대비 {int((d['판정'] == '효과 있음').sum())} · "
              f"전체 대비 {int((d['전체 대비 판정'] == '효과 있음').sum())}")
    print("→ results/bollinger_nvda.md")


if __name__ == "__main__":
    report(run())
