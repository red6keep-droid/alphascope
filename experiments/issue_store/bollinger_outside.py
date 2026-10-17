"""바깥 확인 — 15종목 밖 S&P 500, 30년 저장소 (doc/볼린저-이슈별-검증-계획.md 4-10, 결과 보기 전 고정).

    python experiments/issue_store/fetch_bars.py <바깥 종목들>      # 먼저 30년 일봉 (data/store/bars)
    python experiments/issue_store/bollinger_outside.py

가설 둘 (각각 판정, p < 0.05 / 2):
  A 조용한 하락 — 하단 1.5σ × 진입일 거래량 ÷ 전날까지 20일 평균 1.2배 아래 × 1일, 비교 = 같은 구간(거래량 1.2배 아래) 아무 날
  B 급등 중 하단 — 1년 수익률(전날까지 252일) +100% 위 × 하단 2σ × 1일, 비교 = 같은 구간 아무 날
- 대상: backtest/data/universe.csv + removed.csv − 15종목, data/store 에 있는 것만 (못 받은 수는 결과에 적음)
- 기간 1999 ~, 두 기간 1999 ~ 2012 · 2013 ~ 2026. 판정: n ≥ 30 · p < 0.025 · 두 기간 모두 + → '바깥에서도 확인'
- p 는 bollinger_by_stock.boot_p 그대로 (달 블록 · '차이 없음' 분산). 섹터별 · 5년 단위 방향은 참고 (대원칙 2 · 4)
결과: results/bollinger_outside.md (4-9 의 10년 판은 이 파일로 덮어씀 — 숫자는 계획 4-9 에 남아 있음)
"""

import os

import numpy as np
import pandas as pd

from bollinger_by_stock import STOCKS, boot_p, rate

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "backtest", "data")
BARS = os.path.join(ROOT, "data", "store", "bars")
OUT = os.path.join(os.path.dirname(__file__), "results")
START, SPLIT = pd.Timestamp("1999-01-01"), pd.Timestamp("2013-01-01")
HZ = [1, 5, 10]
P_MAX = 0.05 / 2


def symbols():
    u = pd.read_csv(os.path.join(DATA, "universe.csv"))
    r = pd.read_csv(os.path.join(DATA, "removed.csv"))
    sector = {s.replace(".", "-"): sec for s, sec in zip(u.symbol, u.sector)}
    syms = [s.replace(".", "-") for s in dict.fromkeys(list(u.symbol) + list(r.symbol)) if s not in STOCKS]
    return syms, sector


def per_stock(px):
    px = px[px["close"] > 0]
    c = px["close"]
    fwd = {h: c.shift(-h) / c - 1 for h in HZ}
    ma, sd = c.rolling(20).mean(), c.rolling(20).std()
    sig = {}
    for k in (2.0, 1.5):
        lo = c <= ma - k * sd
        sig[k] = lo & ~lo.shift(1, fill_value=False)
    zone = {"A": px["volume"] / px["volume"].rolling(20).mean().shift(1) < 1.2,
            "B": (c / c.shift(252) - 1).shift(1) * 100 > 100}
    keep = c.index >= START
    return {h: v[keep] for h, v in fwd.items()}, {k: v[keep] for k, v in sig.items()}, {k: v[keep] for k, v in zone.items()}


HYP = {"A": ("조용한 하락 (거래량 1.2배 아래)", 1.5), "B": ("급등 중 하단 (1년 +100% 위)", 2.0)}


def main():
    syms, sector = symbols()
    got, missing = {}, []
    for s in syms:
        p = os.path.join(BARS, s.replace("^", "_").replace("=", "_") + ".parquet")
        if os.path.exists(p):
            df = pd.read_parquet(p)
            if len(df) >= 300 and df.index.max() >= START:
                got[s] = per_stock(df)
                continue
        missing.append(s)
    L = ["# 볼린저 — 15종목 밖 바깥 확인 (30년 저장소)", "",
         f"생성 {pd.Timestamp.today().date()} · 등록 doc/볼린저-이슈별-검증-계획.md 4-10 · 종목 {len(got)} (못 받음 · 300일 미만 {len(missing)}) · 1999 ~", "",
         f"판정 = n ≥ 30 · p < {P_MAX} (가설 둘) · 두 기간(1999~2012 · 2013~2026) 모두 +", ""]
    for key, (title, k) in HYP.items():
        L += [f"## 가설 {key} — {title} × 하단 {k}σ", "",
              "| 신호 | 기간 | n | 종목 수 | 오른 비율 | 구간 아무 날 | 차이 | 1999~2012 (n) | 2013~2026 (n) | p | 판정 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for kk in (k, 3.5 - k):   # 등록한 밴드 먼저, 다른 밴드는 참고
            for h in HZ:
                es, bs, secs = [], [], []
                for s, (fwd, sig, zone) in got.items():
                    e = fwd[h][sig[kk] & zone[key]].dropna()
                    es.append(e); bs.append(fwd[h][zone[key]].dropna()); secs.append(s)
                e, b = pd.concat(es), pd.concat(bs)
                e1, e2, b1, b2 = e[e.index < SPLIT], e[e.index >= SPLIT], b[b.index < SPLIT], b[b.index >= SPLIT]
                d1, d2 = rate(e1) - rate(b1), rate(e2) - rate(b2)
                main_cell = kk == k and h == 1
                p = boot_p(e, b) if len(e) >= 30 else np.nan
                v = ("**바깥에서도 확인**" if len(e) >= 30 and p < P_MAX and d1 > 0 and d2 > 0 else "확인 안 됨") if main_cell else "참고"
                L.append(f"| 하단 {kk}σ{' **(가설)**' if main_cell else ''} | {h} | {len(e)} | {sum(len(x) > 0 for x in es)} | {rate(e):.0f}% | {rate(b):.0f}% | "
                         f"{rate(e) - rate(b):+.1f} | {d1:+.1f} ({len(e1)}) | {d2:+.1f} ({len(e2)}) | {p:.4f} | {v} |")
                if main_cell:
                    main_es, main_bs, main_secs = es, bs, secs
        # 대원칙 4 — 5년 단위로 지속하나 / 대원칙 2 — 섹터별로 고른가 (가설 칸, 참고)
        e, b = pd.concat(main_es), pd.concat(main_bs)
        L += ["", f"5년 단위 (가설 칸) — 차이 %p (n)", "", "| " + " | ".join(f"{y}~{y + 4}" for y in range(1999, 2027, 5)) + " |", "|" + "---|" * 6]
        cells = []
        for y in range(1999, 2027, 5):
            ee, bb = e[(e.index.year >= y) & (e.index.year <= y + 4)], b[(b.index.year >= y) & (b.index.year <= y + 4)]
            cells.append(f"{rate(ee) - rate(bb):+.1f} ({len(ee)})" if len(ee) else "-")
        L += ["| " + " | ".join(cells) + " |", "", "섹터별 (가설 칸)", "", "| 섹터 | n | 오른 비율 | 구간 아무 날 | 차이 |", "|---|---|---|---|---|"]
        by = {}
        for s, ee, bb in zip(main_secs, main_es, main_bs):
            sec = sector.get(s, "제외 종목")
            by.setdefault(sec, ([], []))
            by[sec][0].append(ee); by[sec][1].append(bb)
        for sec, (es_, bs_) in sorted(by.items(), key=lambda kv: -sum(len(x) for x in kv[1][0])):
            ee, bb = pd.concat(es_), pd.concat(bs_)
            if len(ee):
                L.append(f"| {sec} | {len(ee)} | {rate(ee):.0f}% | {rate(bb):.0f}% | {rate(ee) - rate(bb):+.1f} |")
        L.append("")
    L += ["", "못 받은 종목: " + " ".join(missing)]
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "bollinger_outside.md"), "w", encoding="utf-8").write("\n".join(L))
    print(f"종목 {len(got)} · 못 받음 {len(missing)} → results/bollinger_outside.md")


if __name__ == "__main__":
    main()
