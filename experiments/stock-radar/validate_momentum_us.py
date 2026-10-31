"""미국 종목 12-1 모멘텀 검증 — 한국 K18(experiments/kr-stocks/validate_daily.run_price_signals)과 같은 방법 (2026-10-31 사용자 "진행해").

    python experiments/stock-radar/validate_momentum_us.py    # → doc/검증/미국-모멘텀-검증.md · data/validate_momentum_us.json

판정 기준은 한국과 같다(결과 보기 전에 고정):
- 월말에 12-1 모멘텀(1달 전 가격 ÷ 12달 전 가격)으로 줄 세워 5분위 상위 − 하위의 다음 달 수익 차이(%p/월)
- 플라시보 = 종목 라벨 섞기 500회 → p(양쪽) < 0.05
- 앞뒤 절반이 같은 방향(+)
- 그 달 종목 10개 이상, 달 60개 이상
묶음 둘: ① 우리 64종목(지금 페이지가 있는 종목 — 오늘 살아남은 큰 종목만이라 생존 편향이 크다)
         ② 30년 저장소 전체(data/store/bars, 상장폐지 · 편입 제외 종목 포함 약 740개 — 바깥 확인)
같은 표에 한국과 같은 가격 신호 셋(1개월 반전 · 52주 최고가 위치 · 200일선 거리)도 함께 본다.
"""
import json
import os
import random
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", ".."))
sys.path.insert(0, BASE)
import universe as U  # noqa: E402

STORE = os.path.join(ROOT, "data", "store", "bars")
OUT_MD = os.path.join(ROOT, "doc", "검증", "미국-모멘텀-검증.md")
OUT_JSON = os.path.join(BASE, "data", "validate_momentum_us.json")
SEED = 20261031
N_PL = 500
MIN_STOCKS, MIN_MONTHS = 10, 60
START = "1999-01-01"   # 한국 검증(2000~)과 견줄 수 있게


def load(sym):
    for f in (sym, sym.replace(".", "-"), sym.replace("^", "_")):
        p = os.path.join(STORE, f"{f}.parquet")
        if os.path.exists(p):
            c = pd.read_parquet(p)["close"].dropna()
            c.index = pd.to_datetime(c.index).tz_localize(None).normalize()
            return c[c.index >= START]
    return None


def download(syms):
    import yfinance as yf
    df = yf.download(syms, start=START, interval="1d", auto_adjust=True, group_by="ticker", progress=False, threads=3)
    out = {}
    for s in syms:
        try:
            c = df[s]["Close"].dropna()
        except KeyError:
            continue
        if len(c):
            c.index = pd.to_datetime(c.index).tz_localize(None).normalize()
            out[s] = c
    return out


def daily(syms, fetch_missing=True):
    px, miss = {}, []
    for s in syms:
        c = load(s)
        if c is None or not len(c):
            miss.append(s)
        else:
            px[s] = c
    if miss and fetch_missing:
        px.update(download(miss))
    return pd.DataFrame(px).sort_index()


def ls_series(sig, m_ret):
    """월별 5분위 상위 − 하위 다음 달 수익 (numpy). sig · m_ret 은 같은 모양(달 × 종목)."""
    S, R = sig.to_numpy(), m_ret.to_numpy()
    rows = []
    for i in range(len(S) - 1):
        s, r = S[i], R[i + 1]
        ok = ~np.isnan(s) & ~np.isnan(r)
        if ok.sum() < MIN_STOCKS:
            continue
        sv, rv = s[ok], r[ok]
        k = max(2, len(sv) // 5)
        o = np.argsort(sv)
        rows.append((sig.index[i + 1], rv[o[-k:]].mean() - rv[o[:k]].mean(), sv, rv))
    return rows


def test(sig, m_ret, name, expect, rng):
    rows = ls_series(sig, m_ret)
    if len(rows) < MIN_MONTHS:
        return {"name": name, "n": len(rows), "note": "표본 부족"}
    ls = pd.Series({d: v for d, v, _, _ in rows})
    mean = float(ls.mean())
    pl = []
    for _ in range(N_PL):
        vals = []
        for _, _, sv, rv in rows:
            perm = rng.permutation(len(sv))
            k = max(2, len(sv) // 5)
            o = np.argsort(sv[perm])
            rr = rv   # 라벨 섞기 = 신호를 섞고 수익은 그대로
            vals.append(rr[o[-k:]].mean() - rr[o[:k]].mean())
        pl.append(np.mean(vals))
    p = (sum(1 for v in pl if abs(v) >= abs(mean)) + 1) / (N_PL + 1)
    half = len(ls) // 2
    a, b = float(ls.iloc[:half].mean()), float(ls.iloc[half:].mean())
    stable = bool(np.sign(a) == np.sign(b) == expect)
    ok = bool(np.sign(mean) == expect and p < 0.05 and stable)
    return {"name": name, "expect": expect, "from": str(ls.index.min().date()), "to": str(ls.index.max().date()), "n": len(ls),
            "stocks_avg": float(np.mean([len(sv) for _, _, sv, _ in rows])), "spread": mean, "p": p, "first_half": a, "second_half": b,
            "stable": stable, "hit_rate": float((ls > 0).mean()), "pass": ok}


def signals(px):
    P = px.resample("ME").last()
    m_ret = P.pct_change(fill_method=None) * 100
    mom = (P.shift(1) / P.shift(12) - 1) * 100
    rev = m_ret.copy()
    high52 = P / px.rolling(252, min_periods=200).max().resample("ME").last() * 100
    ma200 = (P / px.rolling(200, min_periods=200).mean().resample("ME").last() - 1) * 100
    return m_ret, [(mom, "12-1 모멘텀 상위 − 하위 → 다음 달", +1),
                   (rev, "지난 1개월 수익 상위 − 하위 → 다음 달 (반전이면 −)", -1),
                   (high52, "52주 최고가 대비 위치 상위 − 하위 → 다음 달", +1),
                   (ma200, "200일선 대비 거리 상위 − 하위 → 다음 달", +1)]


def run(group, px, rng):
    m_ret, sigs = signals(px)
    out = []
    for sig, name, expect in sigs:
        r = test(sig, m_ret, name, expect, rng)
        r["group"] = group
        out.append(r)
        print(f"[{group}] {name}: " + (f"{r['spread']:+.2f}%p/월 p={r['p']:.3f} 앞 {r['first_half']:+.2f} 뒤 {r['second_half']:+.2f} → {'통과' if r['pass'] else '안 됨'} (n {r['n']}개월, 평균 {r['stocks_avg']:.0f}종목)" if "spread" in r else r.get("note", "")))
    return out


def write_md(results):
    lines = ["# 미국 종목 12-1 모멘텀 검증 (2026-10-31)", "",
             "한국 K18([한국-일별-사건-검증](한국-일별-사건-검증.md))과 같은 방법 · 같은 판정 기준. 코드 `experiments/stock-radar/validate_momentum_us.py`.", "",
             "- 월말 5분위 상위 − 하위의 다음 달 수익 차이(%p/월). 플라시보 = 종목 라벨 섞기 500회, p < 0.05 · 앞뒤 절반 같은 방향 = 통과",
             "- 묶음 ① 우리 64종목(페이지 있는 종목, 오늘 살아남은 큰 종목 — **생존 편향**) ② 30년 저장소 전체(상장폐지 · 편입 제외 포함, 바깥 확인)", "",
             "| 묶음 | 신호 | 기간 | 달 | 평균 종목 | 상위−하위 %p/월 | p | 앞 절반 | 뒤 절반 | 맞힌 달 | 판정 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        if "spread" not in r:
            lines.append(f"| {r['group']} | {r['name']} | — | {r['n']} | — | — | — | — | — | — | {r.get('note', '')} |")
            continue
        lines.append(f"| {r['group']} | {r['name']} | {r['from'][:7]}~{r['to'][:7]} | {r['n']} | {r['stocks_avg']:.0f} | {r['spread']:+.2f} | {r['p']:.3f} | "
                     f"{r['first_half']:+.2f} | {r['second_half']:+.2f} | {r['hit_rate'] * 100:.0f}% | {'**통과**' if r['pass'] else '안 됨'} |")
    lines += ["", "한국 K18 비교: 우리 35종목 12-1 모멘텀 +1.30%p/월 (2001~2026, 309개월, p .006, 앞뒤 절반 +) 통과.", ""]
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    rng = np.random.default_rng(SEED)
    random.seed(SEED)
    ours = [c[0] for c in U.CANDIDATES]
    res = run("우리 64종목", daily(ours), rng)
    every = sorted(f[:-8] for f in os.listdir(STORE) if f.endswith(".parquet") and not f.startswith("_"))
    etf = {"SPY", "QQQ", "DIA", "IWM", "SMH", "SOXX", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"}   # 지수 · 업종 ETF 는 종목이 아니다
    every = [s for s in every if s not in etf]
    res += run(f"저장소 전체 {len(every)}종목", daily(every, fetch_missing=False), rng)
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    write_md(res)
    print("→", OUT_MD)


if __name__ == "__main__":
    main()
