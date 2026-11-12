"""한국 계열 자동 등록 검증 — forecast_register.py(틀 R) 규칙을 한국 계열에 그대로 돌려 본다 (2026-11-12 사용자 "한국 자동 등록 검증해").

묻는 것
1. 감지 — 평소(60거래일)의 3배 + 절대 기준이 한국 계열에서 해마다 몇 번 걸리나. 같은 계열에 판정 안 난 전망이 있으면 건너뛰는 규칙까지 넣은 실제 등록 수.
2. 판정 — 등록 다음 날부터 40거래일 안에 어느 쪽이 먼저 일어나나(반등 · 조정 = 충격 폭 절반 회복 / 지속 = 기준만큼 더), 제자리 비율.
3. 우리 전망(pick_side) — 같은 계열 · 같은 방향 지난 충격의 20거래일 절반 회복 비율, 윌슨 아래 끝 > 50% 면 유력.
4. 플라시보 — 충격 없는 아무 날에서 같은 폭 · 같은 기준으로 경주를 시켰을 때의 반등 먼저 비율. 충격 뒤가 이것과 다르지 않으면 '충격 뒤라서'가 아니다.
5. 시기 — 2015 전 · 뒤로 나눠 같은 쪽인가.
미국(S&P 500 · 반도체) 같은 계산을 나란히 둔다. 자료 = data/store/bars(로컬), 한국 종목만 yfinance. AI 0.
"""
import json
import os
import random
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
import hypo_pages as H  # noqa: E402
import forecast_register as R  # noqa: E402

BARS = os.path.join(_ROOT, "data", "store", "bars")
OUT = os.path.join(_HERE, "output", "validate_kr_register.json")
SPLIT = pd.Timestamp("2015-01-01")

# (기호, 비교(None = 그대로), 이름, 절대 기준 %p) — 미국 INDEX 와 같은 자리: 지수 2.0 · 업종 2.5~3.0
KR_INDEX = [
    ("^KS11", None, "코스피", 2.0),
    ("^KQ11", None, "코스닥", 2.0),
    ("^KQ11", "^KS11", "코스닥(코스피 대비)", 2.0),
    ("091160.KS", "^KS11", "KODEX 반도체", 3.0),
    ("091170.KS", "^KS11", "KODEX 은행", 2.5),
    ("091180.KS", "^KS11", "KODEX 자동차", 2.5),
    ("117460.KS", "^KS11", "KODEX 에너지화학", 2.5),
]
US_REF = [("^GSPC", None, "S&P 500(참고)", 2.0), ("^SOX", "^GSPC", "반도체(참고)", 3.0)]
KR_SECTOR_OF = {"반도체": "091160.KS", "금융": "091170.KS", "경기 소비재": "091180.KS"}


def bar(sym):
    p = os.path.join(BARS, sym.replace("^", "_") + ".parquet")
    return pd.read_parquet(p)["close"] if os.path.exists(p) else None


def kr_stocks():
    sys.path.insert(0, os.path.join(_ROOT, "experiments", "kr-stocks"))
    import universe_kr as U
    import yfinance as yf
    rows = U.CANDIDATES[:25]
    syms = [r[0] for r in rows]
    df = yf.download(syms, start=R.HIST_START, progress=False, auto_adjust=True, threads=False)["Close"]
    out = []
    for sym, name, _slug, cat, tags in rows:
        if sym.endswith(".KQ"):
            mk = "^KQ11"
        elif "반도체" in tags:
            mk = "091160.KS"
        elif cat == "금융" and name in ("KB금융", "신한지주", "하나금융지주"):
            mk = "091170.KS"
        elif name in ("현대차", "기아"):
            mk = "091180.KS"
        else:
            mk = "^KS11"
        out.append((sym, mk, name, R.STOCK_AMIN, df[sym].dropna()))
    return out


def wilson_lo(q, n, z=1.96):
    return (q + z * z / (2 * n) - z * ((q * (1 - q) + z * z / (4 * n)) / n) ** 0.5) / (1 + z * z / n)


def race(c, m, i, gap, line, start_off=3, win=R.WIN_END):
    """기준일 = i-1 종가, 판정 = 등록 날(i+1) 다음 날부터(judge 의 day <= reg 건너뜀) ~ i+1+win. → 1 반등 먼저 · 2 지속 먼저 · 0 제자리 · None 자료 부족."""
    if i + 1 + win >= len(c):
        return None
    s = 1 if gap > 0 else -1
    path = R._rel_path(c, m, i - 1, i + 1 + win)
    for v in path[start_off:]:
        if 1 - v / gap >= H.R_HIT:
            return 1
        if s * (v - gap) >= line:
            return 2
    return 0


def analyse(sym, mk, name, amin, c=None):
    c = bar(sym) if c is None else c
    df = pd.DataFrame({sym: c})
    if mk:
        df[mk] = bar(mk)
    df = df.dropna(subset=[sym])
    w = {"sym": sym, "mkt": mk, "amin": amin}
    c, m, z, hits, line = R._series_stats(df, w)
    idx = {d: k for k, d in enumerate(c.index)}
    eps, last = [], None
    for d in hits:   # 같은 묶음(5일 안) = 첫날만
        if last is not None and (d - last).days <= R.SAME_EPISODE_DAYS:
            last = d
            continue
        last = d
        eps.append(d)
    years = (c.index[-1] - c.index[R.LOOKBACK]).days / 365.25
    rows, busy_until = [], -1
    for d in eps:
        i = idx[d]
        gap = R._rel_path(c, m, i - 1, i)[1]
        res = race(c, m, i, gap, line)
        reg = i > busy_until
        if reg and res is not None:   # 판정 날까지 같은 계열 새 등록 없음
            s = 1 if gap > 0 else -1
            path = R._rel_path(c, m, i - 1, i + 1 + R.WIN_END)
            k_end = next((k for k, v in enumerate(path[3:], 3) if (1 - v / gap >= H.R_HIT) or s * (v - gap) >= line), len(path) - 1)
            busy_until = i - 1 + k_end
        rows.append({"day": d, "i": i, "gap": gap, "s": 1 if gap > 0 else -1, "res": res, "reg": reg})
    # 우리 전망 = 등록 때 쓰는 기록(그날 이전 같은 방향) — 마지막 날 기준 전체 기록
    out = {"name": name, "sym": sym, "mkt": mk, "amin": amin, "line": line, "years": round(years, 1), "start": str(c.index[0].date()),
           "episodes": len(eps), "per_year": round(len(eps) / years, 1), "reg_per_year": round(sum(r["reg"] for r in rows) / years, 1)}
    rnd = random.Random(7)
    for s, lab in ((-1, "급락"), (1, "급등")):
        rs = [r for r in rows if r["s"] == s and r["res"] is not None]
        if not rs:
            out[lab] = {"n": 0}
            continue
        n = len(rs)
        reb = sum(r["res"] == 1 for r in rs)
        cont = sum(r["res"] == 2 for r in rs)
        mo, no = R._record(c, m, hits, c.index[-1] + pd.Timedelta(days=1), s)
        side, q, _why, strong = H.pick_side(mo, no) if no else (None, None, "", False)
        # 플라시보: 충격 아닌 날(앞뒤 5일 밖)에서 같은 폭 · 기준으로 경주
        shock_i = {idx[d] for d in hits}
        pool = list(range(R.LOOKBACK + 1, len(c) - R.WIN_END - 2))
        pool = [k for k in pool if k not in shock_i and (k - 1) not in shock_i]
        pb = []
        for r in rs:
            for k in rnd.sample(pool, min(40, len(pool))):
                g = r["gap"]
                p0 = R._rel_path(c, m, k, k + 1 + R.WIN_END)   # 기준 = k 종가, 그 날 이미 g 만큼 움직였다고 놓고 경주
                st = 1 if g > 0 else -1
                res = 0
                for v in p0[2:]:   # p0[0] = 충격 자리 날, p0[1] = 등록 날
                    vv = g + v
                    if 1 - vv / g >= H.R_HIT:
                        res = 1
                        break
                    if st * (vv - g) >= line:
                        res = 2
                        break
                pb.append(res)
        pre = [r for r in rs if r["day"] < SPLIT]
        post = [r for r in rs if r["day"] >= SPLIT]
        f = lambda xs, v: round(100 * sum(r["res"] == v for r in xs) / len(xs)) if xs else None  # noqa: E731
        out[lab] = {"n": n, "rebound_first": round(100 * reb / n), "continue_first": round(100 * cont / n), "neither": round(100 * (n - reb - cont) / n),
                    "rebound_lo": round(100 * wilson_lo(reb / n, n)), "placebo_rebound": round(100 * sum(x == 1 for x in pb) / len(pb)),
                    "record_20d": f"{mo}/{no}", "pick": {1: "반등·조정", 2: "지속"}.get(side), "pick_pct": round(100 * q) if q else None, "strong": strong,
                    "pre2015": {"n": len(pre), "rebound_first": f(pre, 1)}, "post2015": {"n": len(post), "rebound_first": f(post, 1)}}
    return out


def main():
    res = {"index": [], "us_ref": [], "stocks": []}
    for t in KR_INDEX:
        res["index"].append(analyse(*t))
    for t in US_REF:
        res["us_ref"].append(analyse(*t))
    try:
        for sym, mk, name, amin, c in kr_stocks():
            if len(c) > 300:
                res["stocks"].append(analyse(sym, mk, name, amin, c))
    except Exception as e:  # noqa: BLE001
        print("종목 실패", type(e).__name__, e)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(res, fp, ensure_ascii=False, indent=1, default=str)
    for grp in ("index", "us_ref", "stocks"):
        print(f"\n== {grp}")
        for o in res[grp]:
            line = f'{o["name"]:<16} {o["start"][:4]}~ 감지 {o["per_year"]}/년 등록 {o["reg_per_year"]}/년 기준 {o["line"]}'
            for lab in ("급락", "급등"):
                x = o[lab]
                if not x.get("n"):
                    continue
                line += (f' | {lab} n{x["n"]} 반등먼저 {x["rebound_first"]}%(아래끝 {x["rebound_lo"]}) 지속 {x["continue_first"]}% 제자리 {x["neither"]}%'
                         f' 플라시보 {x["placebo_rebound"]}% 기록 {x["record_20d"]}→{x["pick"]}{"(유력)" if x["strong"] else ""}'
                         f' 전/후 {x["pre2015"]["rebound_first"]}/{x["post2015"]["rebound_first"]}')
            print(line)


if __name__ == "__main__":
    main()
