"""데일리 리포트의 '기록상' 숫자 — 로컬에서 가끔 다시 만들어 static/daily_stats.json 으로 커밋한다 (doc/데일리-리포트-기획.md 5절).

CI 에는 data/store(약 30년 일봉 · 일정)가 없다. 그래서 오래 걸리는 기록 계산은 여기서 한 번 하고,
매일 리포트는 이 파일의 숫자와 그날 값만 맞춘다. 숫자는 전부 파이썬, 문장은 render_html 의 고정 틀.

    python experiments/daily-report/build_daily_stats.py      # 리포 루트에서, 수 분

담는 것
- korea   : 미국 밤사이 움직임 → 다음 날 한국 시작 가격(시가 갭) · 장중(시가 → 종가) (K1 · K2)
- krw     : S&P 500 과 원/달러의 관계, 원화로 본 S&P 500 (K3 · D4)
- macro   : FOMC · CPI · 고용 · GDP · PCE · 월간 옵션 만기 날의 S&P 500 움직임 vs 보통 날 (D5)
- fomc_upcoming : 앞으로의 FOMC 결정일 (data/store/calendar/fomc.csv)
- earnings: 대형주 10개 실적 반응일 움직임 vs 그 종목 보통 날 (D5)
- regime  : 옛 시장 상태 점수 · 신호등의 우리 검증 결과 (D6, 2008~)
"""

import datetime
import json
import math
import os
import sys

import numpy as np
import pandas as pd
import yfinance as yf

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", ".."))
STORE = os.path.join(ROOT, "data", "store")
OUT = os.path.join(BASE, "static", "daily_stats.json")

START = "2000-01-01"   # 한국 시가 자료가 쓸 만한 때부터 (코스피 시가 결측 0.1%)
Z_BIG = 2.0            # 평소 범위 밖 = |z| ≥ 2 (엔비디아 W1 과 같은 경계)
DECADES = [("2000", "2009"), ("2010", "2019"), ("2020", "2029")]

# (한국 쪽, 미국 쪽, 화면 이름) — 한국 투자자가 흔히 같이 보는 짝. 미국 쪽은 데일리가 매일 받는 심볼이어야 한다
PAIRS = [
    ("^KS11", "^GSPC", "코스피", "S&P 500"),
    ("^KQ11", "^IXIC", "코스닥", "나스닥"),
    ("005930.KS", "^SOX", "삼성전자", "미국 반도체 지수"),
    ("000660.KS", "^SOX", "SK하이닉스", "미국 반도체 지수"),
    ("006400.KS", "TSLA", "삼성SDI", "테슬라"),
    ("373220.KS", "TSLA", "LG에너지솔루션", "테슬라"),
]
MEGA = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "AVGO", "TSLA", "BRK-B", "LLY"]


def _dl(sym, start=START):
    df = yf.download(sym, start=start, auto_adjust=False, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _us_window(us_close, kr_dates):
    """한국 거래일 d 의 시가 갭에 들어가는 미국 움직임 = 한국 전 거래일 날짜 ~ d 전날까지의 미국 로그 수익 합 (휴장 묶음 포함)."""
    r = np.log(us_close).diff().dropna()
    out, prev = [], None
    for d in kr_dates:
        if prev is None:
            out.append(np.nan)
        else:
            m = (r.index >= prev) & (r.index < d)
            out.append(r[m].sum() if m.any() else np.nan)
        prev = d
    return pd.Series(out, index=kr_dates)


def _pct(x):
    return round(float(x) * 100, 2)


def korea_pair(kr, us, kr_name, us_name, cache):
    k = cache.setdefault(kr, _dl(kr))[["Open", "Close"]].dropna()
    k = k[k["Open"] > 0]
    gap = np.log(k["Open"] / k["Close"].shift(1))
    intra = np.log(k["Close"] / k["Open"])
    usc = cache.setdefault(us, _dl(us, "1999-01-01"))["Close"].dropna()
    df = pd.DataFrame({"us": _us_window(usc, list(k.index)), "gap": gap, "intra": intra}).dropna()
    df = df[np.abs(df.gap) > 1e-9]   # 시가 결측(시가 = 전일 종가로 찍힌 날) 제외
    sd = df.us.rolling(250, min_periods=120).std().shift(1)   # 그때까지의 미국 쪽 평소 크기
    df["z"] = df.us / sd
    df = df.dropna()
    c = df.us.corr(df.gap)
    out = {"kr": kr, "us": us, "kr_name": kr_name, "us_name": us_name,
           "first": str(df.index[0].date()), "last": str(df.index[-1].date()), "n": int(len(df)),
           "corr_gap": round(float(c), 2), "r2_gap": round(float(c * c), 2),
           "beta_gap": round(float(np.polyfit(df.us, df.gap, 1)[0]), 2),
           "intra_any": _pct(df.intra.mean()), "buckets": {}}
    for key, mask in [("up", df.z >= Z_BIG), ("down", df.z <= -Z_BIG), ("normal", df.z.abs() < 1)]:
        s = df[mask]
        b = {"n": int(len(s)), "gap": _pct(s.gap.mean()), "intra": _pct(s.intra.mean()),
             "against": round(float((np.sign(s.intra) != np.sign(s.us)).mean()) * 100),
             "t": round(float(s.intra.mean() / (s.intra.std() / math.sqrt(len(s)))), 1) if len(s) > 2 else None,
             "decades": []}
        for a, z in DECADES:
            q, base = s.loc[a:z], df.loc[a:z]
            if len(q) >= 10:
                b["decades"].append({"from": a, "to": min(z, str(df.index[-1].year)), "n": int(len(q)),
                                     "intra": _pct(q.intra.mean()), "intra_any": _pct(base.intra.mean())})
        out["buckets"][key] = b
    return out


def krw_stats(cache):
    spx = cache.setdefault("^GSPC", _dl("^GSPC", "1999-01-01"))["Close"].dropna()
    fx = _dl("KRW=X", "2003-12-01")["Close"].dropna()
    df = pd.DataFrame({"spx": np.log(spx).diff(), "fx": np.log(fx).diff()}).dropna()
    df = df[np.abs(df.fx) < 0.1]   # 야후 환율의 튀는 값(자릿수 오류) 제외
    df["won"] = df.spx + df.fx
    sd = df.spx.rolling(250, min_periods=120).std().shift(1)
    big = df[df.spx / sd <= -Z_BIG]
    return {"first": str(df.index[0].date()), "n": int(len(df)), "corr": round(float(df.spx.corr(df.fx)), 2),
            "big_down": {"n": int(len(big)), "spx": _pct(big.spx.mean()), "fx": _pct(big.fx.mean()), "won": _pct(big.won.mean()),
                         "cushion_share": round(float((big.fx > 0).mean()) * 100)}}


def macro_effect():
    """같은 날 움직임 — 08:30 지표와 14:00 FOMC 는 미국 장중(또는 장 전)에 나와 그날 종가에 들어간다."""
    b = pd.read_parquet(os.path.join(STORE, "bars", "_GSPC.parquet"))
    r = np.log(b["close"]).diff().dropna()
    r.index = pd.to_datetime(r.index)
    r = r.loc["1996":]
    cal = os.path.join(STORE, "calendar")
    ev = pd.read_csv(os.path.join(cal, "econ_releases.csv"))
    fomc = pd.read_csv(os.path.join(cal, "fomc.csv"))
    ms = pd.read_csv(os.path.join(cal, "market_structure.csv"))
    kinds = {
        "FOMC": set(fomc[fomc.scheduled == True].day),   # noqa: E712
        "CPI": set(ev[ev.subkind == "CPI"].day),
        "NFP": set(ev[ev.subkind == "고용 보고서"].day),
        "GDP": set(ev[ev.subkind == "GDP"].day),
        "PCE": set(ev[ev.subkind == "PCE"].day),
        "OPEX": set(ms[ms.subkind == "월간 옵션 만기"].day),
    }
    days = r.index.strftime("%Y-%m-%d")
    any_ev = set().union(*kinds.values())
    normal = r[[d not in any_ev for d in days]].abs()
    out = {"from": str(r.index[0].date()), "to": str(r.index[-1].date()), "normal": _pct(normal.median()), "normal_n": int(len(normal)), "kinds": {}}
    for k, ds in kinds.items():
        x = r[[d in ds for d in days]].abs()
        if len(x) >= 20:
            per = {}
            for a, z in [("1996", "2009"), ("2010", "2019"), ("2020", "2029")]:   # 시기마다 다른지 (대원칙: 묶지 않고 조건과 함께)
                xa, na = x.loc[a:z], normal.loc[a:z]
                if len(xa) >= 10:
                    per[a] = {"median": _pct(xa.median()), "normal": _pct(na.median()), "n": int(len(xa))}
            out["kinds"][k] = {"median": _pct(x.median()), "n": int(len(x)), "periods": per}
    today = datetime.date.today().isoformat()
    upcoming = sorted(d for d in kinds["FOMC"] if d >= today)
    return out, upcoming


def earnings_effect(cache):
    out = {}
    for sym in MEGA:
        try:
            ed = yf.Ticker(sym).get_earnings_dates(limit=60)
        except Exception as e:  # noqa: BLE001
            print(f"[실적] {sym} 실패: {e}")
            continue
        if ed is None or ed.empty:
            continue
        px = cache.setdefault(sym, _dl(sym, "2010-01-01"))["Close"].dropna()
        r = np.log(px).diff().dropna()
        days = list(r.index)
        react = []
        for ts, rep in zip(ed.index, ed["Reported EPS"]):   # 같은 시각이 두 번 나오는 종목이 있다
            if pd.isna(rep):
                continue
            d = pd.Timestamp(ts.date())
            after_close = ts.hour >= 16 or ts.hour == 0   # 시각이 없으면(00:00) 장 마감 뒤로 본다
            nxt = [x for x in days if (x > d if after_close else x >= d)]
            if nxt and d >= days[0]:   # 가격 자료 시작 전 발표는 뺀다
                react.append(nxt[0])
        react = sorted(set(react))
        if len(react) < 8:
            continue
        rx = r.loc[react].abs()
        normal = r.drop(react, errors="ignore").loc[react[0]:].abs()
        out[sym] = {"median": _pct(rx.median()), "n": int(len(rx)), "normal": _pct(normal.median()),
                    "first": str(react[0].date())}
    return out


def regime_verdict():
    """옛 시장 상태 점수 · 신호등 우리 검증 (2026-10-18, analyze.regime_score · status_board 를 2008 ~ 매일 다시 계산).
    결과만 적는다 — 다시 돌리려면 doc/데일리-리포트-기획.md 4-3 의 절차."""
    return {"from": "2008-01", "to": "2026-10", "n_days": 4746,
            "up20": {"Risk-On": 68, "Neutral": 67, "Risk-Off": 65, "any": 67},
            "mean20": {"Risk-On": 0.68, "Neutral": 1.04, "Risk-Off": 1.26, "any": 0.96},
            "red_share_calm": 53}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cache = {}
    korea = []
    for kr, us, kn, un in PAIRS:
        print(f"[한국] {kn} ← {un}")
        korea.append(korea_pair(kr, us, kn, un, cache))
    macro, fomc_up = macro_effect()
    stats = {"built": datetime.date.today().isoformat(), "korea": korea, "krw": krw_stats(cache),
             "macro": macro, "fomc_upcoming": fomc_up, "earnings": earnings_effect(cache), "regime": regime_verdict()}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
