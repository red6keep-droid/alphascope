"""엔비디아 실적 뒤 반도체 vs 시장 — `엔비디아 실적 뒤 반도체는?` 전망의 `과거 기록에서 비슷한 때는?` 칸 (2026-11-12 사용자).

전엔 EH-2026-001(11.05 반도체 급락)의 `불안 지수 28 넘은 날` 기록이 그대로 복사돼 있었다 → 이 전망의 사건(엔비디아 실적)으로 다시 잰다.
자료 = data/store/calendar/earnings.csv (NVDA, 장 마감 뒤 16:20 → 발표 날 종가가 기준) · data/store/bars/_SOX · _GSPC (β 1, 전망과 같은 자).
값 = 발표 날 종가부터 N거래일 뒤 반도체 − S&P 500 (%p). 평소 = 같은 기간 아무 날이나 고른 때의 같은 셈. AI 0 · 새 수집 0.

    python experiments/issue_store/validate_nvda_earnings_history.py      # → 표 출력 + EH-2026-002.json 에 넣을 history JSON
"""
import json
import os

import pandas as pd

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORE = os.path.join(_ROOT, "data", "store")
LINE = 3.0   # 전망의 기준(금) %p


def main():
    s = pd.read_parquet(os.path.join(STORE, "bars", "_SOX.parquet"))["close"]
    m = pd.read_parquet(os.path.join(STORE, "bars", "_GSPC.parquet"))["close"]
    df = pd.concat([s, m], axis=1, keys=["s", "m"], sort=True).dropna()
    e = pd.read_csv(os.path.join(STORE, "calendar", "earnings.csv"))
    e = e[(e.symbol == "NVDA") & e.surprise_band.notna()]
    idx = df.index

    def rel(i, k):
        if i < 0 or i + k >= len(df):
            return None
        a, b = df.iloc[i], df.iloc[i + k]
        return ((b.s / a.s - 1) - (b.m / a.m - 1)) * 100

    rows = []
    for _, r in e.iterrows():
        d = pd.Timestamp(r.day)
        i = idx.searchsorted(d)
        if i >= len(idx) or idx[i] != d:
            continue
        rows.append({"day": r.day, "big": r.surprise_band == "크게 상회", "r20": rel(i, 20), "pre10": rel(i - 10, 10)})
    R = pd.DataFrame(rows)
    sub = df[df.index >= pd.Timestamp(R.day.min())]
    base = lambda k: pd.Series([((sub.s.iloc[i + k] / sub.s.iloc[i] - 1) - (sub.m.iloc[i + k] / sub.m.iloc[i] - 1)) * 100 for i in range(len(sub) - k)])  # noqa: E731
    b20, b10 = base(20), base(10)
    big, oth = R[R.big].dropna(subset=["r20"]), R[~R.big].dropna(subset=["r20"])
    pre = R.dropna(subset=["pre10"])
    pct = lambda x: round(float(x.mean()) * 100, 1)  # noqa: E731
    hist = {
        "what": "엔비디아가 실적을 발표한 날이", "n": int(len(R)), "since": int(str(R.day.min())[:4]), "vs_base": True,
        "rows": [
            ["발표 전 열흘 반도체가 시장보다 올랐다", int((pre.pre10 > 0).sum()), int(len(pre)), pct(b10 > 0)],
            ["크게 넘은 뒤 한 달 반도체가 시장보다 올랐다", int((big.r20 > 0).sum()), int(len(big)), pct(b20 > 0)],
            ["크게 넘은 뒤 한 달 기준 넘게 더 올랐다", int((big.r20 >= LINE).sum()), int(len(big)), pct(b20 >= LINE)],
            ["그 밖일 때 한 달 기준 넘게 빠졌다", int((oth.r20 <= -LINE).sum()), int(len(oth)), pct(b20 <= -LINE)],
        ],
        "alike": [[str(x.day)[:7].replace("-", "."), "예상을 크게 넘음" if x.big else "그 밖", f'{"+" if x.r20 >= 0 else "−"}{abs(x.r20):.1f}%p']
                  for x in R.dropna(subset=["r20"]).tail(4).iloc[::-1].itertuples()],
        "alike_note": "최근 발표 · 그 뒤 한 달 반도체 vs 시장",
    }
    print(json.dumps(hist, ensure_ascii=False, indent=1))
    return hist


if __name__ == "__main__":
    main()
