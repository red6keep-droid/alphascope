"""신호 서명 검증 — 지표가 사건보다 먼저 말하나 (기획 증시-전망-기획 8-19 2단계, 2026-11-08).

    .venv/bin/python experiments/issue_store/signal_signatures.py   → results/signal_signatures.md · .csv

질문 넷 (기준은 결과 보기 전에 고정 — 아래 상수):
A. 사건 전 신호: 사건 전 5거래일 누적 변화가 평소(사건 11거래일 전까지 60거래일)의 2σ 를 넘는 지표가 2개 이상인 사건 비율
   vs 사건 없는 날(사건 ±10거래일 밖 무작위 날) 같은 비율 → 배수(lift). 1 이면 신호 없음.
B. 서명: 사건 종류(subkind, 3건 이상)마다 사건 당일 · 다음 날 반응 z 의 평균과 부호 일치율 → 평균 |z| ≥ 1 · 일치율 ≥ 70% 인 지표 = 그 종류의 서명.
C. 분류: 반응 벡터로 사건 종류를 맞히나 — 하나 빼고 나머지로 묶음(family) 평균을 만들어 코사인 유사도 순위 → 1위 · 3위 안 정확도 vs 우연.
   같은 것을 사건 전 벡터로도 — 사건 전 움직임만으로 종류를 가를 수 있나.
D. 매일 스캔 헛울림: 2008~ 매일, 지표 2개 이상이 같은 날 하루 3σ → 연 몇 번 울리나 · 그중 다음 날부터 5거래일 안에 사건표 사건 또는 S&P 500 충격(shocks.csv)이 온 비율.
AI 0. 자료 = data/store/bars · fred (깃 밖).
"""
import os

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STORE = os.path.join(ROOT, "data", "store")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_MD = os.path.join(HERE, "results", "signal_signatures.md")
OUT_CSV = os.path.join(HERE, "results", "signal_signatures.csv")

# 지표판: 이름 → (파일, 변화 방식) — pct = 로그 수익률, diff = 차이(금리 · 스프레드)
BOARD = {
    "유가": ("bars/CL_F", "pct"), "금": ("bars/GC_F", "pct"), "달러": ("bars/DX-Y.NYB", "pct"), "엔(USDJPY)": ("bars/JPY_X", "pct"),
    "원화(USDKRW)": ("bars/KRW_X", "pct"), "10년 금리": ("bars/_TNX", "diff"), "3개월 금리": ("bars/_IRX", "diff"),
    "VIX": ("bars/_VIX", "pct"), "유가 변동성": ("bars/_OVX", "pct"), "채권 변동성": ("bars/_MOVE", "pct"),
    "구리": ("bars/HG_F", "pct"), "천연가스": ("bars/NG_F", "pct"), "밀": ("bars/ZW_F", "pct"),
    "장기 국채": ("bars/TLT", "pct"), "하이일드": ("bars/HYG", "pct"), "투자등급": ("bars/LQD", "pct"),
    "방산": ("bars/ITA", "pct"), "항공": ("bars/JETS", "pct"), "에너지": ("bars/XLE", "pct"), "금융": ("bars/XLF", "pct"),
    "기술": ("bars/XLK", "pct"), "유틸리티": ("bars/XLU", "pct"), "신흥국": ("bars/EEM", "pct"), "중국": ("bars/FXI", "pct"),
    "한국": ("bars/EWY", "pct"), "비트코인": ("bars/BTC-USD", "pct"),
    "회사채 웃돈": ("fred/BAA10Y", "diff"), "기대 물가": ("fred/T10YIE", "diff"), "2년 금리": ("fred/DGS2", "diff"),
}
PRE, REACT, BASE, GAP = 5, 2, 60, 11     # 사건 전 창 · 반응 창(당일 + 다음 날) · 평소 창 · 평소 창 끝 = 사건 11거래일 전
Z_PRE, N_MIN = 2.0, 2                    # A: 2σ 넘는 지표 2개 이상
Z_DAY = 3.0                              # D: 하루 3σ
SIG_Z, SIG_AGREE = 1.0, 0.7              # B: 서명 기준
SEED, N_RANDOM = 7, 3000

FAMILY = {
    "전쟁 · 테러": "지정학 충격", "재난 · 팬데믹": "지정학 충격", "선거 · 정치": "지정학 충격", "휴전 · 종전": "휴전 · 종전",
    "유가 충격": "유가 충격",
    "해외 금융위기": "금융 위기", "금융기관 부실 · 신용경색": "금융 위기",
    "연준 긴축 신호": "금리 긴축", "연준 완화": "금리 완화", "해외 중앙은행": "금리 긴축",
    "관세 · 무역": "정책 · 규제", "규제 (수출 · 반독점)": "정책 · 규제", "미국 재정 · 부채한도": "정책 · 규제",
    "환율 · 개입": "환율",
    "시장 구조 사고": "시장 충격", "기술주 · 반도체 급락": "시장 충격", "투매 뒤 반등 · 바닥": "반등 · 바닥",
    "경제지표 충격": "지표 · 실적", "실적 · 전망": "지표 · 실적", "기업 사업 소식": "지표 · 실적", "애널리스트 의견": "지표 · 실적",
}


def load(path):
    f = os.path.join(STORE, path + (".parquet" if path.startswith("bars") else ".csv"))
    if path.startswith("bars"):
        s = pd.read_parquet(f)["close"]
    else:
        d = pd.read_csv(f)
        d.columns = [c.lower() for c in d.columns]
        s = pd.to_numeric(d.set_index(pd.to_datetime(d[d.columns[0]]))[d.columns[1]], errors="coerce")
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s[~s.index.duplicated()].dropna().sort_index()


def changes(cal):
    """{지표: 거래일 달력에 맞춘 하루 변화} — 비는 날은 NaN (앞 값으로 채우지 않는다: 가짜 0 변화 방지)."""
    out = {}
    for name, (path, how) in BOARD.items():
        try:
            s = load(path)
        except Exception:
            continue
        s = s[s > 0] if how == "pct" else s
        ch = np.log(s).diff() if how == "pct" else s.diff()
        out[name] = ch.reindex(cal)
    return pd.DataFrame(out)


def zscores(ch, i):
    """사건 위치 i(달력 번호) → (사건 전 z, 반응 z) 지표별. 평소 σ = i-GAP 까지 BASE 거래일."""
    base = ch.iloc[max(0, i - GAP - BASE): i - GAP]
    sd = base.std()
    ok = (base.notna().sum() >= BASE * 0.8) & (sd > 0)
    pre = ch.iloc[i - PRE: i]
    rea = ch.iloc[i: i + REACT]
    zp = (pre.sum(min_count=PRE - 1) / (sd * np.sqrt(PRE))).where(ok)
    zr = (rea.sum(min_count=REACT) / (sd * np.sqrt(REACT))).where(ok)
    return zp, zr


def cos(a, b):
    m = a.notna() & b.notna()
    if m.sum() < 5:
        return np.nan
    x, y = a[m].values, b[m].values
    n = np.linalg.norm(x) * np.linalg.norm(y)
    return float(x @ y / n) if n else np.nan


def main():
    cal = load("bars/_GSPC").index
    cal = cal[cal >= "1995-01-01"]
    ch = changes(cal)
    ev = pd.read_csv(os.path.join(HERE, "events_curated.csv"))
    ev["day"] = pd.to_datetime(ev["start"])
    rows = []
    for _, e in ev.iterrows():
        i = cal.searchsorted(e["day"])
        if i < GAP + BASE or i + REACT > len(cal):
            continue
        zp, zr = zscores(ch, i)
        rows.append({"day": cal[i], "subkind": e["subkind"], "family": FAMILY.get(e["subkind"], "그 밖"), "title": e["title"],
                     **{f"pre:{k}": v for k, v in zp.items()}, **{f"react:{k}": v for k, v in zr.items()}})
    df = pd.DataFrame(rows)
    # 유가 충격은 방향이 반대인 사건(급등 · 급락)이 섞여 평균이 0 으로 지워진다 → 반응 날 유가 부호로 나눈다 (첫 실행에서 찾음)
    oil = df["react:유가"]
    df.loc[(df["family"] == "유가 충격") & (oil > 0), "family"] = "유가 급등"
    df.loc[(df["family"] == "유가 충격") & (oil <= 0), "family"] = "유가 급락"
    names = [c[4:] for c in df.columns if c.startswith("pre:")]
    P = df[[f"pre:{n}" for n in names]].set_axis(names, axis=1)
    R = df[[f"react:{n}" for n in names]].set_axis(names, axis=1)
    df["n_pre"] = (P.abs() >= Z_PRE).sum(axis=1)
    df["n_avail"] = P.notna().sum(axis=1)

    # A — 무작위 날 기준선 (사건 ±10거래일 밖, 2004~ : 지표판 대부분이 있는 때)
    ev_idx = set()
    for d in df["day"]:
        j = cal.get_loc(d)
        ev_idx.update(range(j - 10, j + 11))
    rng = np.random.default_rng(SEED)
    cand = [j for j in range(cal.searchsorted(pd.Timestamp("2004-01-01")), len(cal) - REACT) if j not in ev_idx]
    base_n = []
    for j in rng.choice(cand, size=min(N_RANDOM, len(cand)), replace=False):
        zp, _ = zscores(ch, j)
        base_n.append(int((zp.abs() >= Z_PRE).sum()))
    base_n = np.array(base_n)
    base_rate = float((base_n >= N_MIN).mean())
    recent = df[df["day"] >= "2004-01-01"]
    hit = float((recent["n_pre"] >= N_MIN).mean())

    fam_rows = []
    for fam, g in recent.groupby("family"):
        h = float((g["n_pre"] >= N_MIN).mean())
        fam_rows.append((fam, len(g), h, h / base_rate if base_rate else np.nan, g["n_pre"].mean()))
    fam_rows.sort(key=lambda r: -r[3])

    # B — 서명 (반응), 종류 = family
    sig = {}
    for fam, g in df.groupby("family"):
        if len(g) < 3:
            continue
        Rg = R.loc[g.index]
        mean = Rg.mean()
        agree = (np.sign(Rg).eq(np.sign(mean), axis=1) & Rg.notna()).sum() / Rg.notna().sum()
        n = Rg.notna().sum()
        keep = mean[(mean.abs() >= SIG_Z) & (agree >= SIG_AGREE) & (n >= 3)].sort_values(key=abs, ascending=False)
        sig[fam] = [(k, float(mean[k]), float(agree[k]), int(n[k])) for k in keep.index]
        # 사건 전 서명도 같은 기준으로
        Pg = P.loc[g.index]
        pm = Pg.mean()
        pa = (np.sign(Pg).eq(np.sign(pm), axis=1) & Pg.notna()).sum() / Pg.notna().sum()
        pk = pm[(pm.abs() >= SIG_Z) & (pa >= SIG_AGREE) & (Pg.notna().sum() >= 3)].sort_values(key=abs, ascending=False)
        sig[fam + " (사건 전)"] = [(k, float(pm[k]), float(pa[k]), int(Pg[k].notna().sum())) for k in pk.index]

    # C — 하나 빼고 분류
    def loo(M):
        fams = df["family"]
        valid = fams.map(fams.value_counts()) >= 3
        top1 = top3 = tot = 0
        for i in df.index[valid]:
            others = df.index[valid & (df.index != i)]
            cents = M.loc[others].groupby(fams[others]).mean()
            sims = cents.apply(lambda c: cos(M.loc[i], c), axis=1).dropna().sort_values(ascending=False)
            if sims.empty:
                continue
            tot += 1
            top1 += sims.index[0] == fams[i]
            top3 += fams[i] in sims.index[:3]
        k = fams[valid].nunique()
        return tot, top1 / tot, top3 / tot, 1 / k, min(3, k) / k

    c_react, c_pre = loo(R), loo(P)

    # D — 매일 스캔 헛울림 (2008~)
    s08 = cal.searchsorted(pd.Timestamp("2008-01-01"))
    sd = ch.rolling(BASE, min_periods=int(BASE * 0.8)).std().shift(1)
    zd = (ch / sd).iloc[s08:]
    alarm = (zd.abs() >= Z_DAY).sum(axis=1) >= N_MIN
    sh = pd.read_csv(os.path.join(STORE, "calendar", "shocks.csv"))
    sh = pd.to_datetime(sh.loc[sh["market"] == "S&P 500", "day"])
    targets = set(cal.searchsorted(pd.DatetimeIndex(list(df["day"]) + list(sh))))
    a_idx = [cal.get_loc(d) for d in zd.index[alarm]]
    lead = [any((j + k) in targets for k in range(1, 6)) for j in a_idx]   # 다음 날부터 5거래일 — 경보 당일 충격은 '미리' 가 아니다 (첫 실행 0 포함 → 고침)
    years = (cal[-1] - cal[s08]).days / 365.25
    per_year = len(a_idx) / years
    precision = float(np.mean(lead)) if lead else np.nan
    base_prec = float(np.mean([any((j + k) in targets for k in range(1, 6)) for j in range(s08, len(cal) - 6)]))

    # 쓰기
    df.round(2).to_csv(OUT_CSV, index=False)
    L = ["# 신호 서명 검증 (기획 증시-전망-기획 8-19 2단계)", "",
         f"사건표 {len(df)}건 ({df['day'].min():%Y}~{df['day'].max():%Y}) · 지표판 {len(names)}개 · 기준은 스크립트 머리말에 결과 전 고정. AI 0.", "",
         "## A. 사건 전 신호 — 사건 전 5거래일, 2σ 넘는 지표 2개 이상", "",
         f"- 사건(2004~ {len(recent)}건): **{hit * 100:.0f}%** · 사건 없는 날(무작위 {len(base_n)}일): **{base_rate * 100:.0f}%** → 배수 **{hit / base_rate:.2f}**",
         "", "| 묶음 | 건수 | 사건 전 신호 비율 | 배수 | 평균 지표 수 |", "|---|---|---|---|---|"]
    L += [f"| {f} | {n} | {h * 100:.0f}% | {lift:.2f} | {m:.1f} |" for f, n, h, lift, m in fam_rows]
    L += ["", "배수 1 = 사건 없는 날과 같음(신호 없음). 건수가 적은 묶음은 우연 폭이 크다.", "",
          "## B. 서명 — 평균 |z| ≥ 1 · 부호 일치 ≥ 70% 인 지표 (z = 평소 σ 배수, + 오름)", ""]
    for fam, items in sig.items():
        if items:
            L.append(f"- **{fam}**: " + " · ".join(f"{k} {m:+.1f} ({a * 100:.0f}%, {n}건)" for k, m, a, n in items[:8]))
        else:
            L.append(f"- **{fam}**: 기준을 넘는 지표 없음")
    L += ["", "## C. 분류 — 하나 빼고 나머지로 묶음 평균을 만들어 맞히기", "",
          "| 쓴 벡터 | 건수 | 1위 정확도 | 3위 안 | 우연 1위 | 우연 3위 안 |", "|---|---|---|---|---|---|",
          f"| 반응 (당일 + 다음 날) | {c_react[0]} | {c_react[1] * 100:.0f}% | {c_react[2] * 100:.0f}% | {c_react[3] * 100:.0f}% | {c_react[4] * 100:.0f}% |",
          f"| 사건 전 5일 | {c_pre[0]} | {c_pre[1] * 100:.0f}% | {c_pre[2] * 100:.0f}% | {c_pre[3] * 100:.0f}% | {c_pre[4] * 100:.0f}% |",
          "", "## D. 매일 스캔 헛울림 — 2008~, 지표 2개 이상 같은 날 하루 3σ", "",
          f"- 연 **{per_year:.0f}번** 울림 · 그중 다음 날부터 5거래일 안에 사건표 사건 또는 S&P 500 충격이 온 비율 **{precision * 100:.0f}%** "
          f"(아무 날이나 고를 때 {base_prec * 100:.0f}%)", ""]
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
