"""증시 전망 거시 `기록상 비슷한 때는?` 실측 — FOMC 결정 뒤 S&P 500 (2026-11-07 사용자 "검증해").

    python experiments/issue_store/validate_fomc_history.py      # 표 출력 + output/fomc_history.json

질문: 목업의 "인하 뒤 한 달 10번 중 6번 올랐다" 는 평소와 다른가? 기준(4%)을 넘는 일은 평소보다 흔한가?
- 자료: data/store/calendar/fomc.csv(1994~, 결정 313건) · data/store/bars/_GSPC.parquet(일별 종가). 로컬만, AI 0.
- 기준점 = 결정이 나온 뒤 첫 종가(발표 14:00 ET 라 결정 날 종가, 일요일 긴급 결정은 다음 거래일 종가) — 틀 S 의 '결과 날 종가부터' 와 같다.
- 기간 = 5 · 20 · 60거래일. 셈 = 오름 비율 · +기준 넘음 · −기준 넘음 · 중앙값.
- 평소(플라시보) = 같은 기간(1994-01 ~ 마지막 결정 + 60거래일)의 모든 거래일을 기준점으로 한 같은 셈.
- 차이 검정 = 정확 이항(평소 비율을 귀무로, 양쪽). 겹치는 창(2001 처럼 연달은 인하)은 독립이 아니라 p 가 실제보다 작게 나온다 — 그래서 '인하 묶음(주기)' 수도 같이 적는다.
"""
import json
import math
import os

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
L = 4.0
HZ = (5, 20, 60)


def binom_p(k, n, p):
    """양쪽 정확 이항 p — 관측 확률 이하인 모든 경우의 합."""
    pk = math.comb(n, k) * p ** k * (1 - p) ** (n - k)
    return min(1.0, sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(n + 1)
                        if math.comb(n, i) * p ** i * (1 - p) ** (n - i) <= pk * (1 + 1e-9)))


def fwd(close, idx, h):
    j = idx + h
    return (close.iloc[j] / close.iloc[idx] - 1) * 100 if j < len(close) else None


def stats(rets):
    r = [x for x in rets if x is not None]
    n = len(r)
    if not n:
        return None
    s = sorted(r)
    return {"n": n, "up": sum(x > 0 for x in r), "over": sum(x >= L for x in r), "under": sum(x <= -L for x in r),
            "median": round(s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2, 2)}


def cycles(days, gap=120):
    """연달은 같은 결정은 한 묶음 — 앞 결정에서 gap 달력일 안이면 같은 주기."""
    out, last = 0, None
    for d in days:
        if last is None or (d - last).days > gap:
            out += 1
        last = d
    return out


def main():
    bars = pd.read_parquet(os.path.join(ROOT, "data", "store", "bars", "_GSPC.parquet"))
    close = bars["close"].dropna()
    close.index = pd.to_datetime(close.index)
    fomc = pd.read_csv(os.path.join(ROOT, "data", "store", "calendar", "fomc.csv"), parse_dates=["day"])
    start, last = fomc["day"].min(), fomc["day"].max()
    pos = {}
    for _, r in fomc.iterrows():
        i = close.index.searchsorted(r["day"])   # 결정 날(거래일이면 그날, 주말이면 다음 거래일)
        if i < len(close):
            pos[r["day"]] = i
    i0, i1 = close.index.searchsorted(start), min(close.index.searchsorted(last) + 60, len(close) - 1)
    base = {h: stats([fwd(close, i, h) for i in range(i0, i1)]) for h in HZ}
    groups = {"인하 전부": fomc[fomc.decision == "인하"], "인하 · 정례 회의만": fomc[(fomc.decision == "인하") & (fomc.scheduled)],
              "인하 · 긴급(정례 밖)": fomc[(fomc.decision == "인하") & (~fomc.scheduled)],
              "동결": fomc[fomc.decision == "동결"], "인상": fomc[fomc.decision == "인상"]}
    res = {"line": L, "period": [str(start.date()), str(close.index[i1].date())], "base": base, "groups": {}}
    print(f"기준 ±{L}% · 기간 {res['period'][0]} ~ {res['period'][1]}\n")
    print(f"{'묶음':<16}{'기간':>6}{'n':>5}{'오름':>14}{'+4% 넘음':>16}{'−4% 넘음':>16}{'중앙값':>8}")
    for h in HZ:
        b = base[h]
        print(f"{'평소(모든 날)':<16}{h:>5}일{b['n']:>5}{b['up'] / b['n'] * 100:>13.0f}%{b['over'] / b['n'] * 100:>15.0f}%{b['under'] / b['n'] * 100:>15.0f}%{b['median']:>8}")
    for name, g in groups.items():
        days = sorted(g["day"])
        res["groups"][name] = {"decisions": len(days), "cycles": cycles(days)}
        for h in HZ:
            st = stats([fwd(close, pos[d], h) for d in days if d in pos])
            b = base[h]
            p_up = binom_p(st["up"], st["n"], b["up"] / b["n"])
            p_over = binom_p(st["over"], st["n"], b["over"] / b["n"])
            p_under = binom_p(st["under"], st["n"], b["under"] / b["n"])
            st.update({"p_up": round(p_up, 3), "p_over": round(p_over, 3), "p_under": round(p_under, 3)})
            res["groups"][name][h] = st
            print(f"{name:<16}{h:>5}일{st['n']:>5}{st['up']:>6}({st['up'] / st['n'] * 100:3.0f}%) p{p_up:.2f}"
                  f"{st['over']:>5}({st['over'] / st['n'] * 100:3.0f}%) p{p_over:.2f}{st['under']:>5}({st['under'] / st['n'] * 100:3.0f}%) p{p_under:.2f}{st['median']:>8}")
        print(f"{'':<16}  결정 {len(days)}번 · 묶음(주기) {cycles(days)}개")
    alike = {}
    for d in ("2019-07-31", "2024-09-18", "2007-09-18"):
        i = close.index.searchsorted(pd.Timestamp(d))
        alike[d] = {h: round(fwd(close, i, h), 2) for h in HZ}
    res["alike"] = alike
    print("\n가장 비슷했던 때 (목업 값 → 실측)")
    for d, v in alike.items():
        print(f"  {d}: 5일 {v[5]:+.2f}% · 20일 {v[20]:+.2f}% · 60일 {v[60]:+.2f}%")
    out = os.path.join(os.path.dirname(__file__), "output", "fomc_history.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n→ {out}")


if __name__ == "__main__":
    main()
