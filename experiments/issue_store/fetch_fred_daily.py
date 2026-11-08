"""FRED 일별 — 증시 전망 `오늘 나온 것` · 사슬 고리 · 배경 (2026-11-07 사용자 "모자란 일별 자료 추가해줘", 기획 9-2).

    python experiments/issue_store/fetch_fred_daily.py      # data/store/fred/{id}.csv  (day, value)

키 없이 공개 CSV(fredgraph.csv)로 받는다 — FRED 공식, 무료. 발표일 기준으로 쓴다(값의 날짜 = 그 값이 나온 거래일).
"""
import io
import os
import sys

import pandas as pd
import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "data", "store", "fred")
UA = {"User-Agent": "alphascope-research/1.0"}

SERIES = {   # id: (독자 이름, 단위, 사슬에서의 뜻)
    "BAMLH0A0HYM2": ("신용 위험 웃돈", "%p", "회사채가 국채보다 얼마나 더 이자를 받나 — 벌어지면 겁을 먹는 것 (신용 경색 · 침체 사슬 첫 고리)"),
    "T10Y2Y": ("장단기 금리 차", "%p", "10년 − 2년 — 거꾸로(음수)면 경기 걱정 (경기 사슬)"),
    "DGS10": ("10년 금리", "%", "금리 사슬 · 성장주"),
    "DGS2": ("2년 금리", "%", "금리 기대"),
    "T10YIE": ("기대 물가", "%", "시장이 보는 10년 물가 — 물가 사슬"),
    "DTWEXBGS": ("달러 가치", "지수", "달러 사슬"),
    "BAA10Y": ("회사채 웃돈 (긴 기록)", "%p", "무디스 BAA − 10년 국채, 1986~ — 하이일드(최근 3년만 공개)의 30년 검증 대리"),
}


def fetch(sid, start="1995-01-01"):
    """같은 주소를 curl 처럼 — 쿼리 하나(id)만. FRED 는 가끔 연결을 끊어 세 번까지 다시 시도한다."""
    last = None
    for _ in range(3):
        try:
            r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", headers={"User-Agent": "curl/8.4.0"}, timeout=45)
            r.raise_for_status()
            break
        except requests.RequestException as e:
            last = e
    else:
        raise last
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = ["day", "value"]
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna()
    return df[df["day"] >= start]


def load(sid):
    p = os.path.join(OUT, f"{sid}.csv")
    if not os.path.exists(p):
        return {}
    df = pd.read_csv(p)
    return dict(zip(df["day"].astype(str), df["value"].astype(float)))


def main():
    os.makedirs(OUT, exist_ok=True)
    bad = 0
    for sid, (name, _, _) in SERIES.items():
        try:
            df = fetch(sid)
            df.to_csv(os.path.join(OUT, f"{sid}.csv"), index=False)
            print(f"{name} ({sid}): {len(df)}행 · 마지막 {df.day.iloc[-1]} = {df.value.iloc[-1]}")
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"{name} ({sid}): 실패 — {type(e).__name__}", file=sys.stderr)
    return 1 if bad == len(SERIES) else 0


if __name__ == "__main__":
    sys.exit(main())
