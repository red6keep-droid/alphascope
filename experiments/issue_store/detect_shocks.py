"""시장이 크게 움직인 날 찾기 — 이슈를 기억으로 떠올리지 않고 데이터에서 먼저 찾는다 (2026-10-17 사용자: "더 많은 이슈가 있을 텐데, 시장 변화가 없다면 패스").

    python experiments/issue_store/detect_shocks.py

기준 (결과 보기 전에 고정 — 볼린저 계획 3절):
- 평소 대비 크기: 그날 변화 ÷ 직전 60거래일 하루 변화의 표준편차 ≥ 3 (평소의 3배)
- 그리고 절대 크기도: S&P 500 ±2% · 엔비디아 ±7% · VIX +25% · 10년 금리 ±15bp · 원유 ±6% · 엔화 ±1.5% · 반도체 지수 ±4% · 달러 ±1.2%
  (둘 다 넘어야 — 조용한 시기의 작은 움직임 · 늘 요동치는 시기의 평범한 움직임을 둘 다 거른다)
연속된 날은 한 묶음(episode)으로. 결과: data/store/calendar/shocks.csv — 날짜 · 시장 · 크기 · 배수 · 묶음 번호 · 설명(사건표 · 캘린더에서 붙인 것)
"""

import os

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STORE = os.path.join(ROOT, "data", "store")
CAL = os.path.join(STORE, "calendar")

# 심볼: (이름, 변화 방식, 절대 기준)
SERIES = {"_GSPC": ("S&P 500", "pct", 2.0), "NVDA": ("엔비디아", "pct", 7.0), "_SOX": ("반도체 지수", "pct", 4.0),
          "_VIX": ("VIX", "pct_up", 25.0), "_TNX": ("10년 금리", "bp", 15.0), "CL_F": ("원유", "pct", 6.0),
          "JPY_X": ("엔화(USD/JPY)", "pct", 1.5), "DX-Y.NYB": ("달러 지수", "pct", 1.2)}
Z_MIN, LOOKBACK = 3.0, 60


def load(sym):
    return pd.read_parquet(os.path.join(STORE, "bars", sym + ".parquet"))["close"].dropna()


def detect():
    rows = []
    for sym, (name, how, absmin) in SERIES.items():
        c = load(sym)
        if how == "bp":
            ch = c.diff() * 100   # ^TNX 는 % 단위 → bp
        else:
            ch = c.pct_change() * 100
        if sym == "CL_F":
            ch = ch[c.shift(1) > 5]   # 2020-04 음수 유가 구간의 비정상 % 제외
        sd = ch.rolling(LOOKBACK).std().shift(1)
        z = ch / sd
        hit = (z.abs() >= Z_MIN) & (ch.abs() >= absmin)
        if how == "pct_up":
            hit = (z >= Z_MIN) & (ch >= absmin)
        for d in ch[hit].index:
            rows.append({"day": d.normalize(), "market": name, "change": round(float(ch[d]), 2), "unit": "bp" if how == "bp" else "%", "z": round(float(z[d]), 1)})
    df = pd.DataFrame(rows).sort_values("day")
    days = df["day"].drop_duplicates().sort_values().reset_index(drop=True)
    ep = (days.diff().dt.days.fillna(99) > 4).cumsum()   # 4일 넘게 떨어지면 새 묶음
    df["episode"] = df["day"].map(dict(zip(days, ep)))
    return df


def explain(df):
    """사건표 · 캘린더에서 그날(±2일, 이전 쪽) 이슈를 붙인다."""
    ev = pd.read_csv(os.path.join(ROOT, "experiments", "issue_store", "events_curated.csv"), parse_dates=["start"])
    cal = []
    for f, label in (("econ_releases.csv", "subkind"), ("fomc.csv", "subkind"), ("earnings.csv", "subkind")):
        p = os.path.join(CAL, f)
        if os.path.exists(p):
            t = pd.read_csv(p, parse_dates=["day"])
            if f == "fomc.csv":
                t["subkind"] = "FOMC " + t["decision"].fillna("")
            if f == "earnings.csv":
                t["subkind"] = "엔비디아 실적 " + t["surprise_band"].fillna("")
            cal.append(t[["day", "subkind"]])
    cal = pd.concat(cal)
    out = []
    for d in df["day"]:
        # 사건 시작 3일 전 ~ 기간 끝 (거래일 ≈ 달력 1.45배) 안이면 그 사건으로 설명된다
        e = ev[(ev["start"] <= d + pd.Timedelta(days=0)) & (ev["start"] + pd.to_timedelta(ev["window_days"] * 1.45, unit="D") >= d)]
        c = cal[(cal["day"] <= d) & (cal["day"] >= d - pd.Timedelta(days=1))]
        major = [x for x in c["subkind"] if x.startswith(("CPI", "고용", "FOMC", "엔비디아 실적", "PCE", "GDP", "PPI"))]
        out.append(" · ".join(list(e["title"]) + sorted(set(major))))
    df["explained_by"] = out
    return df


if __name__ == "__main__":
    df = explain(detect())
    df.to_csv(os.path.join(CAL, "shocks.csv"), index=False)
    ep = df.groupby("episode").agg(start=("day", "min"), end=("day", "max"), markets=("market", lambda x: " · ".join(sorted(set(x)))),
                                   explained=("explained_by", lambda x: next((v for v in x if v), "")))
    print(f"큰 움직임 {len(df)}건 · 날짜 {df['day'].nunique()}일 · 묶음 {len(ep)}개")
    print(df.groupby("market").size().to_string())
    for lo, hi in (("1990", "2005"), ("2006", "2015"), ("2016", "2026")):
        sub = ep[(ep["start"].dt.year >= int(lo)) & (ep["start"].dt.year <= int(hi))]
        print(f"{lo}~{hi}: 묶음 {len(sub)} · 설명 붙음 {int((sub['explained'] != '').sum())} · 원인 확인 필요 {int((sub['explained'] == '').sum())}")
