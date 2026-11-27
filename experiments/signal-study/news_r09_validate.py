"""r09 A안 검증 — 언론 언급 급증(GDELT) 다음 날 시가 매수 → 1 · 5 · 20일, SPY 대비.

    python experiments/signal-study/news_r09_validate.py            # → output/r09_news_gdelt.md
    python experiments/signal-study/news_r09_validate.py --titles   # 흔한 이름 4종목 급증일 기사 제목 받기(GDELT 요청 8번) → 같은 표에 붙음

재료: data/store/gdelt_stock/{sym}.csv(news_gdelt_stock.py) · open.csv · close.csv · earnings.csv(yfinance 실적일).
신호:
- 언급 급증 = 그날 기사 비중(그 회사 기사 ÷ 그날 전체 감시 기사)이 직전 60일 중앙값의 3배 이상, 그 회사 기사 5건 이상.
- 호재 급증 / 악재 급증 = 급증한 날 어조가 직전 60일 평균 ± 1 표준편차 밖. 사이는 `어조 보통`.
- 매수 = GDELT 날짜(세계 표준시) 다음 거래일 시가. 보유 h 일 = 그날 시가 → h 번째 거래일 종가. 성과 = 종목 − SPY(같은 창).
- 실적 발표일 ±2일 안 급증은 `실적 무렵`으로 따로(실적 효과와 섞임).
판정 = 계획 4절: 탐색 2017~2022 / 검증 2023~, 승률 차이 +4%p 이상(회차 5회 넘음 → +3 → +4) · p<0.05 양쪽 · 기준선 이긴 해 7/10 · 기대값 > 기준선.
기준선 = 같은 종목 모든 거래일에 같은 방식으로 샀을 때. 보유 기간 안 재신호는 첫 건만. 10종목 시험이라 칸 대부분 1,000건 아래 = 방향만(‡).
AI 0.
"""
import argparse
import math
import os
import sys
import time
import urllib.parse

import pandas as pd
import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
D = os.path.join(ROOT, "data", "store", "gdelt_stock")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "r09_news_gdelt.md")
SYMS = ["NVDA", "TSLA", "NFLX", "XOM", "JPM", "MU", "AAPL", "AMZN", "INTC", "META"]
COMMON = ["AAPL", "AMZN", "INTC", "META"]
HOLD = [1, 5, 20]
WIN, MULT, MIN_CNT, TONE_SD, EARN_DAYS = 60, 3.0, 5, 1.0, 2
SPLIT = "2023-01-01"
ADOPT = 4.0


def _p_two(k, n, p0):
    """승률 k/n 이 기준선 p0 와 다른가 — 정규 근사 양쪽 p."""
    if n == 0 or p0 in (0, 1):
        return 1.0
    z = (k / n - p0) / math.sqrt(p0 * (1 - p0) / n)
    return math.erfc(abs(z) / math.sqrt(2))


def signals(sym, earn):
    g = pd.read_csv(os.path.join(D, f"{sym}.csv"), parse_dates=["day"]).set_index("day").sort_index()
    sh, tn = g["share_permille"], g["tone"]
    base = sh.shift(1).rolling(WIN, min_periods=40).median()
    m, s = tn.shift(1).rolling(WIN, min_periods=40).mean(), tn.shift(1).rolling(WIN, min_periods=40).std()
    spike = (sh >= MULT * base) & (g["count"] >= MIN_CNT) & base.notna()
    ev = g[spike].copy()
    ev["kind"] = ["호재 급증" if t > a + TONE_SD * b else "악재 급증" if t < a - TONE_SD * b else "어조 보통"
                  for t, a, b in zip(tn[spike], m[spike], s[spike])]
    ed = earn.get(sym, [])
    ev["earn"] = [any(abs((d - e).days) <= EARN_DAYS for e in ed) for d in ev.index]
    ev["ratio"] = (sh[spike] / base[spike]).round(1)
    return ev


def excess(op, cl, sym, i, h):
    j = i + h - 1
    if j >= len(op):
        return None
    return (cl[sym].iat[j] / op[sym].iat[i] - 1) - (cl["SPY"].iat[j] / op["SPY"].iat[i] - 1)


def run():
    op = pd.read_csv(os.path.join(D, "open.csv"), index_col=0, parse_dates=True)
    cl = pd.read_csv(os.path.join(D, "close.csv"), index_col=0, parse_dates=True)
    e = pd.read_csv(os.path.join(D, "earnings.csv"), parse_dates=["day"])
    earn = {s: list(x["day"]) for s, x in e.groupby("sym")}
    days = op.index
    trades, base, evs = [], [], {}
    for s in SYMS:
        if not os.path.exists(os.path.join(D, f"{s}.csv")):
            print(f"[r09] {s} GDELT 없음 — 건너뜀")
            continue
        ev = signals(s, earn)
        evs[s] = ev
        first = days.searchsorted(pd.Timestamp("2017-03-15"))   # 60일 창이 찬 뒤
        for h in HOLD:
            for i in range(first, len(days)):
                x = excess(op, cl, s, i, h)
                if x is not None:
                    base.append((s, h, days[i], x))
            last = {}
            for d, r in ev.iterrows():
                i = days.searchsorted(d, side="right")   # 다음 거래일
                if i >= len(days):
                    continue
                grp = (r["kind"], r["earn"])
                if grp in last and i < last[grp] + h:   # 보유 기간 안 재신호는 첫 건만
                    continue
                x = excess(op, cl, s, i, h)
                if x is None:
                    continue
                last[grp] = i
                trades.append((s, h, days[i], x, r["kind"], r["earn"]))
    T = pd.DataFrame(trades, columns=["sym", "h", "day", "x", "kind", "earn"])
    B = pd.DataFrame(base, columns=["sym", "h", "day", "x"])
    return T, B, evs


def cell(t, b):
    """t = 신호 거래, b = 같은 종목 · 같은 구간 기준선. 승률 · 기준선 승률 · 차이 · p · 평균 · 기준 평균."""
    if t.empty:
        return None
    # 기준선 = 신호가 난 종목들의 기준선을 신호 수만큼 가중(종목 구성 차이를 없앰)
    w = t["sym"].value_counts()
    bw = sum(n * (b[b["sym"] == s]["x"] > 0).mean() for s, n in w.items()) / w.sum()
    bm = sum(n * b[b["sym"] == s]["x"].mean() for s, n in w.items()) / w.sum()
    k, n = int((t["x"] > 0).sum()), len(t)
    return dict(n=n, win=k / n * 100, bwin=bw * 100, diff=(k / n - bw) * 100, p=_p_two(k, n, bw), mean=t["x"].mean() * 100, bmean=bm * 100)


def years_beat(t, b):
    out = []
    for y, ty in t.groupby(t["day"].dt.year):
        c = cell(ty, b[b["day"].dt.year == y])
        if c:
            out.append(c["diff"] > 0)
    return sum(out), len(out)


def report(T, B, evs, titles=None):
    L = ["# r09 A안 — 언론 언급 급증(GDELT) 뒤 주가 · 시험 10종목", "",
         f"만든 날 {pd.Timestamp.today().date()} · 코드 `experiments/signal-study/news_r09_validate.py` · 재료 `news_gdelt_stock.py`", "",
         "신호(미리 고정): 그날 기사 비중 ≥ 직전 60일 중앙값 × 3 · 기사 5건 이상. 어조가 직전 60일 평균 ± 1 표준편차 밖이면 호재 · 악재 급증.",
         "매수 = 다음 거래일 시가, 성과 = 종목 − SPY. 기준선 = 같은 종목 모든 거래일(신호 종목 구성대로 가중).",
         f"판정(계획 4절, 9회차): 승률 차이 +{ADOPT:.0f}%p 이상 · p<0.05 를 탐색(~2022) · 검증(2023~) 양쪽 + 이긴 해 7/10 + 기대값 > 기준선. n<300 †(해석 X) · n<1000 ‡(방향만).", "",
         "## 급증일 수", "", "| 종목 | 급증 | 호재 | 악재 | 보통 | 실적 무렵 |", "|---|---|---|---|---|---|"]
    for s, ev in evs.items():
        vc = ev["kind"].value_counts()
        L.append(f"| {s} | {len(ev)} | {vc.get('호재 급증', 0)} | {vc.get('악재 급증', 0)} | {vc.get('어조 보통', 0)} | {int(ev['earn'].sum())} |")
    L += ["", "## 결과", "", "| 신호 | 실적 | 보유 | 구간 | n | 승률 | 기준선 | 차이 | p | 평균 % | 기준 평균 % | 이긴 해 | 판정 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    passed = []
    for kind in ["전체 급증", "호재 급증", "악재 급증", "어조 보통"]:
        for earn in [False, True]:
            for h in HOLD:
                t = T[(T["h"] == h) & (T["earn"] == earn)]
                t = t if kind == "전체 급증" else t[t["kind"] == kind]
                if kind == "전체 급증":   # 전체는 같은 날 겹침 없이 다시 첫 건만 — 종목 · 날 하나
                    t = t.drop_duplicates(["sym", "day"])
                b = B[B["h"] == h]
                ok = []
                for name, tt, bb in [("탐색", t[t["day"] < SPLIT], b[b["day"] < SPLIT]), ("검증", t[t["day"] >= SPLIT], b[b["day"] >= SPLIT])]:
                    c = cell(tt, bb)
                    if not c:
                        continue
                    mark = "†" if c["n"] < 300 else "‡" if c["n"] < 1000 else ""
                    yb, yn = years_beat(t, b) if name == "탐색" else ("", "")
                    good = c["n"] >= 300 and c["diff"] >= ADOPT and c["p"] < 0.05 and c["mean"] > c["bmean"]   # † 칸은 해석 X (계획 4절)
                    ok.append(good)
                    L.append(f"| {kind} | {'실적 무렵' if earn else '실적 아님'} | {h}일 | {name} | {c['n']}{mark} | {c['win']:.1f}% | {c['bwin']:.1f}% | **{c['diff']:+.1f}%p** | {c['p']:.3f} | "
                             f"{c['mean']:+.2f} | {c['bmean']:+.2f} | {f'{yb}/{yn}' if yn != '' else ''} | {'통과' if good else ''} |")
                yb, yn = years_beat(t, b)
                if len(ok) == 2 and all(ok) and yb >= 0.7 * yn:
                    passed.append(f"{kind} · {'실적 무렵' if earn else '실적 아님'} · {h}일")
    L += ["", "## 판정", "", ("통과: " + ", ".join(passed)) if passed else "통과 없음 — 이 기준 · 이 표본으로는 확인 못 함(효과 없음이 아님, 계획 4절).", ""]
    if titles:
        L += ["## 검색어 점검 — 흔한 이름 급증일 기사 제목", ""]
        for (s, d), ts in titles.items():
            L.append(f"**{s} {d}**")
            L += [f"- {x}" for x in ts[:8]] or ["- (제목 없음)"]
            L.append("")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"[r09] → {OUT} · 통과 {len(passed)}")


def fetch_titles(evs):
    """흔한 이름 4종목 — 비율이 가장 큰 급증일 2개씩, 그날 기사 제목(artlist). 1분 간격."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from news_gdelt_stock import QUERIES
    out, first = {}, True
    for s in COMMON:
        ev = evs.get(s)
        if ev is None or ev.empty:
            continue
        for d in ev.sort_values("ratio", ascending=False).index[:2]:
            if not first:
                time.sleep(60)
            first = False
            q = urllib.parse.quote(QUERIES[s] + " sourcelang:english")
            ds = d.strftime("%Y%m%d")
            url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={q}&mode=artlist&maxrecords=15&format=json&startdatetime={ds}000000&enddatetime={ds}235959"
            try:
                r = requests.get(url, headers={"User-Agent": "alphascope-research/1.0"}, timeout=90)
                out[(s, d.date())] = [a.get("title", "") for a in (r.json().get("articles") or [])]
            except Exception as e:  # noqa: BLE001
                out[(s, d.date())] = [f"(못 받음: {type(e).__name__})"]
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--titles", action="store_true")
    a = ap.parse_args()
    T, B, evs = run()
    report(T, B, evs, fetch_titles(evs) if a.titles else None)
