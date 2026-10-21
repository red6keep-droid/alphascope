"""볼린저 하단 · 상단 진입 — 15종목 · 업종 묶음별 이슈 · 상황 검증 (doc/검증/볼린저-이슈별-검증-계획.md 3절 · 4-1 규칙 그대로).

    python experiments/issue_store/bollinger_by_stock.py           # 계산 ("검증해" 때만)
    python experiments/issue_store/bollinger_by_stock.py --check   # 종목별 진입 수 · 묶음 수만 (수익률 안 봄)
    python experiments/issue_store/bollinger_by_stock.py --hyp2    # 가설 2차 H4 · H6 · H7 · H8 만 (계획 4-8) → bollinger_15_h2.md

엔비디아 단독 판(bollinger_by_issue.py)과 같은 신호 · 묶음 · 비교 · 판정. 바뀐 것 (2026-10-17 사용자 확정, 계획 4-1):
- 층 셋: **종목별** 15 (리포트 문장은 여기서) · **업종 묶음** 4 (CSCO 는 묶지 않음) · **15 전체** (참고만, 근거 없는 혼합)
- 엔비디아 전용 구간은 **그 종목의 값** (1년 수익률 · 200일선 기울기 · 횡보 · 하루 변동성 · H2 · H3 · H5), 경계값 그대로.
  "회사 시기" 는 NVDA 만. H1 비교 지수는 반도체 = ^SOX, 플랫폼 · CSCO = ^IXIC. 실적은 그 종목의 실적 (장 마감 뒤 발표로 봄)
- 부트스트랩 블록 = 달 (묶음 층은 모든 종목의 같은 달을 한 블록 — 같은 날 함께 진입한 것은 독립이 아니다)
- BH 보정은 가족(구간 · 이슈) × 층 × 비교 안에서만
- 종목별: 한 기간(1999~2012 · 2013~2026) 진입이 10번 미만이면 '효과 있음' 대신 '참고'
- 업종 묶음: 판정을 넘고 ① 한 종목씩 빼도 차이 방향 유지 ② 진입 10번 이상 종목 중 과반이 같은 방향 → '효과 있음 · 업종 성질',
  아니면 '묶음만 · X 가 끌어올림'
결과: results/bollinger_15.md · bollinger_15.csv.gz
"""

import os
import sys
from math import erfc, sqrt

import numpy as np
import pandas as pd

from event_vocab import check as check_vocab

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STORE = os.path.join(ROOT, "data", "store")
CAL = os.path.join(STORE, "calendar")
OUT = os.path.join(os.path.dirname(__file__), "results")
HZ = [1, 5, 10, 20]
MAIN_HZ = [1, 5, 10]   # 판정은 단기, 20일은 참고
SPLIT = pd.Timestamp("2013-01-01")
START = pd.Timestamp("1999-01-01")   # 엔비디아 판과 같은 두 기간 — 그 전 일봉은 지표 계산(200 · 252일)에만 쓴다
N_MIN, Q_MAX, BOOT, N_PERIOD, N_MEMBER = 30, 0.10, 2000, 10, 10
SECTORS = {   # 2026-10-17 사용자 확정 (계획 4-1)
    "반도체 설계": ["NVDA", "AMD", "QCOM", "AVGO"],
    "반도체 장비": ["AMAT", "LRCX", "KLAC"],
    "메모리 · 제조 · 아날로그": ["MU", "INTC", "TXN"],
    "대형 기술 플랫폼": ["MSFT", "AAPL", "AMZN", "GOOGL"],
}
SOLO = ["CSCO"]   # 묶지 않음 — 종목별로만
STOCKS = [s for v in SECTORS.values() for s in v] + SOLO
SEMI = set(SECTORS["반도체 설계"] + SECTORS["반도체 장비"] + SECTORS["메모리 · 제조 · 아날로그"])
SECTOR_SYMS = {True: "SMH|SOXX|\\^SOX", False: "QQQ|\\^IXIC|XLK"}   # 사건표에서 '업종 관련' 으로 볼 대상
REGIME = ("전체", "회사 시기", "종목 1년 수익률", "200일선 기울기", "횡보", "종목 하루 변동성", "시장 ·", "시장 낙폭", "VIX",
          "H1 ", "H2 ", "H3 ", "H5 ")   # 구간 가족 (나머지는 이슈)
HYP2 = ("H4 ", "H6 ", "H7 ", "H8 ")   # 가설 2차 가족 (계획 4-8) — --hyp2 로 따로 돌린다
MODE = {"hyp2": "--hyp2" in sys.argv}
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


def spans(rows, idx):
    """사건 시작일 ~ +window_days 거래일."""
    m = np.zeros(len(idx), bool)
    for _, r in rows.iterrows():
        p = idx.searchsorted(r.start)
        m[p:min(len(idx), p + int(r.window_days))] = True
    return pd.Series(m, index=idx)


def load_shared():
    ec = pd.read_csv(os.path.join(CAL, "econ_releases.csv"), parse_dates=["day"])
    fo = pd.read_csv(os.path.join(CAL, "fomc.csv"), parse_dates=["day"])
    er = pd.read_csv(os.path.join(CAL, "earnings.csv"), parse_dates=["day"])
    ms = pd.read_csv(os.path.join(CAL, "market_structure.csv"), parse_dates=["day"])
    ev = pd.read_csv(os.path.join(ROOT, "experiments", "issue_store", "events_curated.csv"), parse_dates=["start"])
    check_vocab(ev)   # 세부 종류는 고정 어휘 21개
    ev = ev[ev.confidence.astype(str).str.contains("기억|기사 확인")]
    sh = pd.read_csv(os.path.join(CAL, "shocks.csv"), parse_dates=["day"])
    mk = {k: bars(k)["close"] for k in ("_GSPC", "_VIX", "_SOX", "_IXIC", "_TNX")}
    return ec, fo, er, ms, ev, sh, mk


def build(sym, shared):
    """한 종목의 진입 신호 · 묶음 (그날 아침에 아는 것 — 추세 · 시장 값은 전날 종가 기준)."""
    ec, fo, er, ms, ev, sh, mk = shared
    px = bars(sym)
    c = px["close"]
    idx = c.index
    fwd = {h: c.shift(-h) / c - 1 for h in HZ}
    ma, sd = c.rolling(20).mean(), c.rolling(20).std()
    sig = {}
    for k in (2.0, 1.5):
        lo, hi = c <= ma - k * sd, c >= ma + k * sd
        sig[f"하단 {k}σ"] = lo & ~lo.shift(1, fill_value=False)
        sig[f"상단 {k}σ"] = hi & ~hi.shift(1, fill_value=False)

    g = {"전체": pd.Series(True, index=idx)}
    if sym == "NVDA":   # 회사 시기 — 엔비디아만 (다른 종목 경계를 손으로 정하면 결과 보고 긋게 된다)
        for a, b, name in (("1999", "2008", "1999~2008 초창기"), ("2009", "2015", "2009~2015 중기"), ("2016", "2022", "2016~2022 성장기"), ("2023", "2026", "2023~2026 폭발기")):
            g["회사 시기 · " + name] = pd.Series((idx >= a) & (idx <= b + "-12-31"), index=idx)
    r1y = (c / c.shift(252) - 1).shift(1) * 100
    for lo_, hi_, name in ((-1e9, -20, "−20% 아래"), (-20, 0, "−20~0%"), (0, 30, "0~30%"), (30, 100, "30~100%"), (100, 1e9, "100% 위")):
        g["종목 1년 수익률 · " + name] = (r1y > lo_) & (r1y <= hi_)
    ma200 = c.rolling(200).mean()
    slope = (ma200 / ma200.shift(250) - 1).shift(1) * 100
    for lo_, hi_, name in ((-1e9, -5, "내림"), (-5, 5, "평평"), (5, 40, "완만한 오름"), (40, 1e9, "가파른 오름")):
        g["200일선 기울기 · " + name] = (slope > lo_) & (slope <= hi_)
    rng60 = ((c.rolling(60).max() / c.rolling(60).min() - 1) * 100).shift(1)
    g["횡보 (60일 고저 폭 25% 안)"] = rng60 <= 25   # 엔비디아 판과 같은 경계
    vol = (c.pct_change().rolling(20).std() * 100).shift(1)
    for lo_, hi_, name in ((0, 2, "2% 아래"), (2, 3, "2~3%"), (3, 5, "3~5%"), (5, 1e9, "5% 위")):
        g["종목 하루 변동성 · " + name] = (vol > lo_) & (vol <= hi_)
    # H1 시장 동반 vs 종목만 — 반도체는 ^SOX, 플랫폼 · CSCO 는 ^IXIC
    bench = mk["_SOX" if sym in SEMI else "_IXIC"].reindex(idx).ffill()
    rel5 = ((c / c.shift(5)) - (bench / bench.shift(5))) * 100
    g["H1 하락 성격 · 종목만 (업종 지수 대비 −5%p 아래)"] = rel5 <= -5
    g["H1 하락 성격 · 섞임 (−5~−2%p)"] = (rel5 > -5) & (rel5 <= -2)
    g["H1 하락 성격 · 시장 동반 (−2%p 위)"] = rel5 > -2
    width = (4 * sd / ma).shift(1)
    wrank = width.rolling(252).rank(pct=True)
    g["H2 밴드 폭 · 좁음 (1년 중 하위 20%, 스퀴즈)"] = wrank <= 0.2
    g["H2 밴드 폭 · 중간"] = (wrank > 0.2) & (wrank < 0.8)
    g["H2 밴드 폭 · 넓음 (상위 20%)"] = wrank >= 0.8
    gap = (px["open"] / c.shift(1) - 1) * 100
    g["H3 시가 갭 · −3% 아래 (갭 하락)"] = gap <= -3
    g["H3 시가 갭 · −3% 위"] = gap > -3
    pos200 = (c > ma200).shift(1)
    g["H5 200일선 위치 · 위"] = pos200 == True   # noqa: E712 — NaN 은 어느 쪽도 아님
    g["H5 200일선 위치 · 아래"] = pos200 == False   # noqa: E712
    # 가설 2차 H4 · H6 · H7 · H8 (2026-10-17 밤 사용자 확정, 계획 4-8, 결과 보기 전 고정)
    vr = px["volume"] / px["volume"].rolling(20).mean().shift(1)
    g["H4 거래량 · 20일 평균 2배 이상 (투매)"] = vr >= 2
    g["H4 거래량 · 20일 평균 1.2배 아래"] = vr < 1.2
    d52 = (c.shift(1) / c.rolling(252).max().shift(1) - 1) * 100
    g["H6 52주 고점 대비 · −10% 안"] = d52 > -10
    g["H6 52주 고점 대비 · −10 ~ −30%"] = (d52 <= -10) & (d52 > -30)
    g["H6 52주 고점 대비 · −30% 아래"] = d52 <= -30
    tnx = mk["_TNX"].reindex(idx).ffill()
    t5 = tnx - tnx.shift(5)
    g["H7 10년물 금리 5일 · +0.25%p 이상"] = t5 >= 0.25
    g["H7 10년물 금리 5일 · 그 밖"] = t5 < 0.25
    vx = mk["_VIX"].reindex(idx).ffill()
    vx1 = vx / vx.shift(1) - 1
    g["H8 VIX 하루 · +20% 이상"] = vx1 >= 0.2
    g["H8 VIX 하루 · 그 밖"] = vx1 < 0.2
    sp = mk["_GSPC"].reindex(idx).ffill()
    above = (sp > sp.rolling(200).mean()).shift(1)
    g["시장 · S&P 500 200일선 위"] = above == True   # noqa: E712
    g["시장 · S&P 500 200일선 아래"] = above == False   # noqa: E712
    dd = ((sp / sp.cummax() - 1) * 100).shift(1)
    for lo_, hi_, name in ((-5, 0.1, "고점 −5% 안"), (-10, -5, "−5~−10%"), (-20, -10, "−10~−20%"), (-100, -20, "−20% 아래")):
        g["시장 낙폭 · " + name] = (dd > lo_) & (dd <= hi_)
    vix = mk["_VIX"].reindex(idx).ffill().shift(1)
    for lo_, hi_, name in ((0, 15, "15 아래"), (15, 20, "15~20"), (20, 30, "20~30"), (30, 1e9, "30 위")):
        g["VIX · " + name] = (vix > lo_) & (vix <= hi_)
    # 이슈 가족 — 캘린더(발표일 ±1거래일) · 실적 · 시장 구조 · 사건 · 큰 움직임
    for sub in sorted(ec.subkind.unique()):
        g["경제지표 · " + sub + " ±1일"] = near(ec[ec.subkind == sub].day, idx)
    for grp in sorted(ec.group.unique()):
        g["경제지표 분류 · " + grp + " ±1일"] = near(ec[ec.group == grp].day, idx)
    for dec in ("인상", "동결", "인하"):
        g["FOMC · " + dec + " ±1일"] = near(fo[fo.decision == dec].day, idx)
    g["FOMC · 긴급 결정 ±1일"] = near(fo[(~fo.scheduled.astype(bool)) & fo.decision.isin(["인상", "인하"])].day, idx)
    mine = er[(er.symbol == sym) & (er.day <= idx.max())]
    g["종목 실적 · 발표 다음 날 ±1일"] = near(mine.day, idx, 0, 2)   # 장 마감 뒤 발표 → 다음 날부터
    for band in ("크게 상회", "상회", "부합", "하회"):
        g["종목 실적 · " + band] = near(mine[mine.surprise_band == band].day, idx, 0, 2)
    g["시장 구조 · 옵션 만기 ±1일"] = near(ms[ms.subkind.isin(["월간 옵션 만기", "네 마녀의 날"])].day, idx)
    g["시장 구조 · 분기 말 ±1일"] = near(ms[ms.subkind.isin(["분기 말", "연말"])].day, idx)
    for subk, sub in ev.dropna(subset=["subkind"]).groupby("subkind"):
        g["사건 세부 · " + subk] = spans(sub, idx)
    for kind, sub in ev.groupby("kind"):
        g["사건 · " + kind] = spans(sub, idx)
    pat = f"(?:^|\\s){sym}(?:$|\\s)|" + SECTOR_SYMS[sym in SEMI]
    g["사건 · 종목 · 업종 관련"] = spans(ev[ev.symbols.fillna("").str.contains(pat)], idx)
    g["큰 움직임 직후 · 아무 시장 (5일 안)"] = near(sh.day, idx, 0, 5)
    for m_ in sorted(sh.market.unique()):
        g["큰 움직임 직후 · " + m_ + " (5일 안)"] = near(sh[sh.market == m_].day, idx, 0, 5)
    g["큰 움직임 직후 · 원인 미확인 (5일 안)"] = near(sh[sh.explained_by.isna()].day, idx, 0, 5)

    keep = idx >= START
    g = {k: v.reindex(idx).fillna(False).astype(bool)[keep] for k, v in g.items()}
    sig = {k: v[keep] for k, v in sig.items()}
    fwd = {h: v[keep] for h, v in fwd.items()}
    return fwd, sig, g


def _blocks(up, months):
    codes, uniq = pd.factorize(months)
    return np.bincount(codes, weights=up, minlength=len(uniq)), np.bincount(codes, minlength=len(uniq))


def boot_p(e, base):
    """오른 비율 차이(진입일 − 비교 날)의 양측 p — 진입일 · 비교 날을 각각 달 블록으로 다시 뽑는다
    (가까운 날끼리의 겹침, 묶음 층은 여러 종목의 같은 달을 한 블록). 표준오차 → 정규 근사.
    2026-10-17 무작위 수익률 시험에서 고침: ① 2,000번 중 몇 번을 세면 드문 차이가 p = 0 이 되어 BH 를 그냥 통과(116칸)
    ② 비교 날 오른 비율을 고정값으로 두면 날 수 적은 이슈 묶음에서 p 가 작게 나옴
    ③ 표준오차를 관측 비율로 재면(왈드) 84% 같은 치우친 칸에서 작게 나와 p 가 과하게 작다 → 분산은 '차이 없음' 가정의
    비율 p0(비교 날 비율)로 다시 재고, 블록 겹침 몫(설계 효과 = 부트스트랩 분산 ÷ 독립 가정 분산)만 부트스트랩에서 가져온다"""
    p0 = (base > 0).mean()
    se2 = 0.0
    for x in (e, base):
        s, k = _blocks((x > 0).astype(float).values, x.index.to_period("M"))
        if len(s) < 5:
            return np.nan
        pick = rng.integers(0, len(s), (BOOT, len(s)))
        ph = (x > 0).mean()
        iid = ph * (1 - ph) / len(x)
        deff = (s[pick].sum(1) / k[pick].sum(1)).var() / iid if iid > 0 else 1.0
        se2 += max(deff, 1.0) * p0 * (1 - p0) / len(x)
    obs = (e > 0).mean() - p0
    return float(erfc(abs(obs) / sqrt(se2) / sqrt(2))) if se2 > 0 else np.nan


def rate(x):
    return 100 * (x > 0).mean() if len(x) else np.nan


def cell(e, b, a, judged):
    """e = 진입일 수익률, b = 같은 묶음의 모든 날, a = 1999~ 모든 날 (Series, 날짜 index — 여러 종목이면 날짜 중복)."""
    r = {"n": len(e), "묶음 날 수": len(b), "오른 비율": rate(e), "일반 오른 비율": rate(b), "전체 비교 오른 비율": rate(a),
         "중앙값": 100 * e.median() if len(e) else np.nan, "일반 중앙값": 100 * b.median(), "전체 중앙값": 100 * a.median(),
         "나쁜 쪽 10%": 100 * e.quantile(.1) if len(e) else np.nan, "일반 나쁜 쪽 10%": 100 * b.quantile(.1),
         "n 1999~2012": int((e.index < SPLIT).sum()), "n 2013~2026": int((e.index >= SPLIT).sum()),
         # 한 종목씩 빼기 계산용 — 진입 · 비교 날의 오른 수
         "_eu": int((e > 0).sum()), "_bn": len(b), "_bu": int((b > 0).sum()), "_an": len(a), "_au": int((a > 0).sum())}
    if not len(e):
        return r
    e1, e2 = e[e.index < SPLIT], e[e.index >= SPLIT]
    for base, tag in ((b, ""), (a, "전체 ")):
        b1, b2 = base[base.index < SPLIT], base[base.index >= SPLIT]
        r[tag + "차이"] = rate(e) - rate(base)
        r[tag + "차이 1999~2012"] = rate(e1) - rate(b1) if len(e1) >= 1 and len(b1) >= 10 else np.nan
        r[tag + "차이 2013~2026"] = rate(e2) - rate(b2) if len(e2) >= 1 and len(b2) >= 10 else np.nan
        r[tag + "p"] = boot_p(e, base) if judged else np.nan
    return r


def run(check=False):
    shared = load_shared()
    data = {s: build(s, shared) for s in STOCKS}
    if check:   # 진입 수 · 묶음 수만 — 수익률은 보지 않는다
        print("| 종목 | 첫날 | 묶음 | 하단 2σ (1999~2012 · 2013~2026) | 하단 1.5σ |")
        for s, (fwd, sig, g) in data.items():
            d = sig["하단 2.0σ"].index
            cnt = lambda k: f"{int(sig[k][d < SPLIT].sum())} · {int(sig[k][d >= SPLIT].sum())}"   # noqa: E731
            print(f"| {s} | {d.min().date()} | {len(g)} | {cnt('하단 2.0σ')} | {cnt('하단 1.5σ')} |")
        return None
    units = [("종목", s, [s]) for s in STOCKS] + [("묶음", k, v) for k, v in SECTORS.items()] + [("15 전체", "15 전체", STOCKS)]
    names = list(dict.fromkeys(n for s in STOCKS for n in data[s][2]))
    names = [n for n in names if n.startswith(HYP2) == MODE["hyp2"]]   # 4-7 판(구간 · 이슈)과 가설 2차를 섞지 않는다
    rows, dropped = [], []
    for layer, unit, members in units:
        for gname in names:
            have = [m for m in members if gname in data[m][2]]
            if not have:
                continue
            for h in HZ:
                b = pd.concat([data[m][0][h][data[m][2][gname]] for m in have]).dropna()
                if len(b) < 10:
                    if h == HZ[0]:
                        dropped.append((layer, unit, gname, len(b)))
                    continue
                a = pd.concat([data[m][0][h] for m in have]).dropna()
                for sname in data[have[0]][1]:
                    e = pd.concat([data[m][0][h][data[m][1][sname] & data[m][2][gname]] for m in have]).dropna()
                    r = {"층": layer, "단위": unit, "신호": sname, "묶음": gname, "기간": h}
                    r.update(cell(e, b, a, len(e) >= N_MIN and h in MAIN_HZ))
                    rows.append(r)
    df = pd.DataFrame(rows)
    df.insert(0, "가족", np.where(df["묶음"].str.startswith(HYP2), "가설 2차", np.where(df["묶음"].str.startswith(REGIME), "구간", "이슈")))
    for tag, col in (("", "구간 대비 판정"), ("전체 ", "전체 대비 판정")):
        df[col] = verdict(df, tag)
    return df, dropped


def verdict(df, tag):
    """BH(가족 × 층 안에서) → 판정. 종목 층은 한 기간 진입 10번 미만이면 '참고', 묶음 층은 고름 검사."""
    m = df[tag + "p"].notna()
    df[tag + "q"] = np.nan
    for (fam, layer), _ in df.groupby(["가족", "층"]):
        mf = m & (df["가족"] == fam) & (df["층"] == layer)
        p = df.loc[mf, tag + "p"].values
        if not len(p):
            continue
        order = np.argsort(p)
        q = np.empty_like(p)
        q[order] = np.minimum.accumulate((p[order] * len(p) / np.arange(1, len(p) + 1))[::-1])[::-1]
        df.loc[mf, tag + "q"] = np.minimum(q, 1)
    core = (m & (df[tag + "q"] < Q_MAX) & (df["n"] >= N_MIN)).to_numpy()
    same = (np.sign(df[tag + "차이 1999~2012"]) == np.sign(df[tag + "차이 2013~2026"])).to_numpy()
    few = (df[["n 1999~2012", "n 2013~2026"]].min(axis=1) < N_PERIOD).to_numpy()
    out = np.where(df["n"] == 0, "진입 없음", np.where(df["n"] < N_MIN, "표본 부족", "뚜렷한 차이 없음")).astype(object)
    stock = (df["층"] == "종목").to_numpy()
    out[stock & core & few] = "참고 (한 기간 진입 10번 미만)"
    out[stock & core & ~few & same] = "효과 있음"
    other = ~stock & core & same
    out[other & (df["층"] == "15 전체").to_numpy()] = "효과 있음 (참고 — 혼합)"
    # 업종 묶음 — 한 종목씩 빼기 · 과반 같은 방향
    base_n, base_u = ("_bn", "_bu") if not tag else ("_an", "_au")
    st = df[stock].set_index(["단위", "신호", "묶음", "기간"])
    for i in np.where(other & (df["층"] == "묶음").to_numpy())[0]:
        r = df.iloc[i]
        sign = np.sign(r[tag + "차이"])
        loo_ok, agree, eligible, top = True, 0, 0, (None, -1e9)
        for mem in SECTORS[r["단위"]]:
            key = (mem, r["신호"], r["묶음"], r["기간"])
            if key not in st.index:
                continue
            s = st.loc[key]
            ne, nb = r["n"] - s["n"], r[base_n] - s[base_n]
            if ne > 0 and nb > 0:
                d = 100 * ((r["_eu"] - s["_eu"]) / ne - (r[base_u] - s[base_u]) / nb)
                loo_ok &= np.sign(d) == sign
            if s["n"] >= N_MEMBER:
                eligible += 1
                agree += int(np.sign(s[tag + "차이"]) == sign)
            contrib = s["n"] * sign * (s[tag + "차이"] if pd.notna(s[tag + "차이"]) else 0)
            if contrib > top[1]:
                top = (mem, contrib)
        out[i] = "효과 있음 · 업종 성질" if loo_ok and agree * 2 > eligible else f"묶음만 · {top[0]} 가 끌어올림"
    return out


HYP = [   # 사용자 가설 · 등록 가설 (계획 0 · 2-F · 4-5) — 요약 표의 행
    ("폭발 성장기", "종목 1년 수익률 · 100% 위"), ("완만한 우상향", "200일선 기울기 · 완만한 오름"), ("가파른 오름", "200일선 기울기 · 가파른 오름"),
    ("하락 추세", "200일선 기울기 · 내림"), ("횡보", "횡보 (60일 고저 폭 25% 안)"), ("변동성 큼", "종목 하루 변동성 · 3~5%"),
    ("변동성 작음", "종목 하루 변동성 · 2% 아래"), ("시장 하락장", "시장 · S&P 500 200일선 아래"), ("시장 고점 근처", "시장 낙폭 · 고점 −5% 안"),
    ("H1 종목만 하락", "H1 하락 성격 · 종목만 (업종 지수 대비 −5%p 아래)"), ("H1 시장 동반", "H1 하락 성격 · 시장 동반 (−2%p 위)"),
    ("H2 스퀴즈", "H2 밴드 폭 · 좁음 (1년 중 하위 20%, 스퀴즈)"), ("H3 갭 하락", "H3 시가 갭 · −3% 아래 (갭 하락)"),
    ("H5 200일선 위", "H5 200일선 위치 · 위"), ("H5 200일선 아래", "H5 200일선 위치 · 아래"),
]


HYP_2 = [("H4 투매 (거래량 2배↑)", "H4 거래량 · 20일 평균 2배 이상 (투매)"), ("H4 조용한 하락 (1.2배↓)", "H4 거래량 · 20일 평균 1.2배 아래"),
         ("H6 고점 −10% 안", "H6 52주 고점 대비 · −10% 안"), ("H6 −10 ~ −30%", "H6 52주 고점 대비 · −10 ~ −30%"), ("H6 −30% 아래", "H6 52주 고점 대비 · −30% 아래"),
         ("H7 금리 급등", "H7 10년물 금리 5일 · +0.25%p 이상"), ("H7 그 밖", "H7 10년물 금리 5일 · 그 밖"),
         ("H8 VIX 급등일", "H8 VIX 하루 · +20% 이상"), ("H8 그 밖", "H8 VIX 하루 · 그 밖")]


def report(df, dropped):
    global HYP
    os.makedirs(OUT, exist_ok=True)
    stem = "bollinger_15_h2" if MODE["hyp2"] else "bollinger_15"
    if MODE["hyp2"]:
        HYP = HYP_2
    pq = [c for c in df.columns if c in ("p", "q", "전체 p", "전체 q")]   # p · q 는 반올림하지 않는다
    df.drop(columns=[c for c in df.columns if c.startswith("_")]).round({c: 2 for c in df.columns if c not in pq}).to_csv(os.path.join(OUT, stem + ".csv.gz"), index=False)
    L = ["# 볼린저 — 15종목 · 업종 묶음별 이슈 · 상황 결과", "",
         f"생성 {pd.Timestamp.today().date()} · 규칙 doc/검증/볼린저-이슈별-검증-계획.md 3절 · 4-1 · 판정 = n ≥ {N_MIN} · BH q < {Q_MAX} (가족 × 층) · "
         "두 기간(1999~2012 · 2013~2026) 방향 일치 · 단기 1 · 5 · 10일. 전체 칸은 `bollinger_15.csv.gz`", "",
         "비교 둘: **구간 대비** = 같은 묶음의 모든 날 (리포트 문장 기준) · **전체 대비** = 1999~ 모든 날 (구간 자체의 힘이 섞임)", "",
         "## 칸 수", "", "| 층 | 가족 | 칸 | 판정 대상 | 구간 대비 판정 | 전체 대비 판정 |", "|---|---|---|---|---|---|"]
    for (layer, fam), d in df.groupby(["층", "가족"], sort=False):
        cnt = lambda col: " · ".join(f"{k} {v}" for k, v in d[col].value_counts().items() if k not in ("표본 부족", "진입 없음", "뚜렷한 차이 없음"))   # noqa: E731
        L.append(f"| {layer} | {fam} | {len(d)} | {int(d['p'].notna().sum())} | {cnt('구간 대비 판정') or '-'} | {cnt('전체 대비 판정') or '-'} |")
    cols = ["층", "단위", "신호", "묶음", "기간", "n", "n 1999~2012", "n 2013~2026", "오른 비율"]
    for tag, col, title in (("", "구간 대비 판정", "구간 대비"), ("전체 ", "전체 대비 판정", "전체 대비")):
        base = "일반 오른 비율" if not tag else "전체 비교 오른 비율"
        hit = df[~df[col].isin(["표본 부족", "진입 없음", "뚜렷한 차이 없음"])].sort_values(["층", "가족", "단위", "신호", "묶음", "기간"])
        cc = cols + [base, tag + "차이", tag + "차이 1999~2012", tag + "차이 2013~2026", tag + "q", col]
        L += ["", f"## 통과 · 참고 ({title}) — {len(hit)}칸", ""]
        if len(hit):
            L += ["| 가족 | " + " | ".join(cc) + " |", "|" + "---|" * (len(cc) + 1)]
            L += ["| " + r["가족"] + " | " + " | ".join(f"{r[c]:.0f}" if isinstance(r[c], float) else str(r[c]) for c in cc) + " |" for _, r in hit.iterrows()]
    # 가설 대조 — 하단, 구간 대비 차이(%p) 1 · 5 · 10일, 괄호는 5일 n
    units = list(SECTORS) + SOLO + ["15 전체"]
    for s in ("하단 2.0σ", "하단 1.5σ"):
        L += ["", f"## 가설 대조 · {s} — 업종 묶음 (구간 대비 %p, 1 · 5 · 10일 · 5일 n)", "", "| 가설 | " + " | ".join(units) + " |", "|" + "---|" * (len(units) + 1)]
        for lab, g in HYP:
            cells = []
            for u in units:
                d = df[(df["단위"] == u) & (df["신호"] == s) & (df["묶음"] == g)].set_index("기간")
                if not len(d) or 5 not in d.index:
                    cells.append("-"); continue
                v = " · ".join(f"{d.loc[h, '차이']:+.0f}" if h in d.index and pd.notna(d.loc[h].get("차이")) else "-" for h in MAIN_HZ)
                cells.append(f"{v} ({int(d.loc[5, 'n'])})")
            L.append(f"| {lab} | " + " | ".join(cells) + " |")
    L += ["", "## 가설 대조 · 하단 1.5σ 5일 — 종목별 (구간 대비 %p · n)", "", "| 가설 | " + " | ".join(STOCKS) + " |", "|" + "---|" * (len(STOCKS) + 1)]
    for lab, g in HYP:
        cells = []
        for u in STOCKS:
            d = df[(df["단위"] == u) & (df["신호"] == "하단 1.5σ") & (df["묶음"] == g) & (df["기간"] == 5)]
            cells.append(f"{d['차이'].iloc[0]:+.0f} ({int(d['n'].iloc[0])})" if len(d) and pd.notna(d["차이"].iloc[0]) else "-")
        L.append(f"| {lab} | " + " | ".join(cells) + " |")
    L += ["", "## 비교할 날이 10일 미만이라 뺀 묶음", ""] + [f"- {a} {b} · {c} ({k}일)" for a, b, c, k in dropped]
    open(os.path.join(OUT, stem + ".md"), "w", encoding="utf-8").write("\n".join(L).replace("nan", "-"))
    for (layer, fam), d in df.groupby(["층", "가족"], sort=False):
        print(f"{layer} · {fam}: 칸 {len(d)} · 판정 대상 {int(d['p'].notna().sum())} · " +
              " / ".join(f"{k}" for k in d["구간 대비 판정"].value_counts().items() if k[0] not in ("표본 부족", "진입 없음", "뚜렷한 차이 없음")))
    print(f"→ results/{stem}.md")


if __name__ == "__main__":
    if "--check" in sys.argv:
        run(check=True)
    else:
        report(*run())
