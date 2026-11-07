"""지정학 위험 지수(GPR, Caldara–Iacoviello) · 경제정책 불확실성 지수(EPU, Baker–Bloom–Davis) 일별 — 증시 전망 배경 칸(기획 8-10 · 10-1 ⑥).

    python experiments/issue_store/fetch_gpr_epu.py

저장: data/store/calendar/gpr_daily.csv (day, gpr, gprt, gpra) · epu_daily.csv (day, epu)
출처 표기(둘 다 무료 · 출처 표기 조건): GPR = Caldara & Iacoviello (2022, AER) https://www.matteoiacoviello.com/gpr.htm (매주 월요일 갱신, 받은 날짜 적기)
EPU = Baker, Bloom & Davis, https://www.policyuncertainty.com (일별 미국 뉴스 지수)
평소 = 100 (두 지수 모두 기준 100 으로 정규화돼 있다). 배경 줄은 "지정학 위험 지수 (GPR) 186 · 평소 100 · 1985년 이후 상위 5%" 처럼 값 + 분위.
"""
import io
import os
import sys
from datetime import date

import pandas as pd
import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "data", "store", "calendar")
GPR_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls"
EPU_URL = "https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv"
UA = {"User-Agent": "alphascope-research/1.0"}


def fetch_gpr():
    r = requests.get(GPR_URL, headers=UA, timeout=60)
    r.raise_for_status()
    df = pd.read_excel(io.BytesIO(r.content))
    df.columns = [c.lower() for c in df.columns]   # 열: DAY(yyyymmdd) · N10D · GPRD · GPRD_ACT · GPRD_THREAT · date · GPRD_MA30 · GPRD_MA7 (2026-11-07 확인)
    out = pd.DataFrame({"day": pd.to_datetime(df["day"].astype(int).astype(str), format="%Y%m%d").dt.date,
                        "gpr": df["gprd"], "gprt": df["gprd_threat"], "gpra": df["gprd_act"], "n_articles": df.get("n10d")})
    return out.dropna(subset=["gpr"])


def fetch_epu():
    r = requests.get(EPU_URL, headers=UA, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = [c.lower() for c in df.columns]
    df = df.dropna(subset=["year", "month", "day"])
    out = pd.DataFrame({"day": pd.to_datetime(df[["year", "month", "day"]].astype(int)).dt.date, "epu": df["daily_policy_index"]})
    return out.dropna()


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("gpr_daily", fetch_gpr), ("epu_daily", fetch_epu)):
        try:
            df = fn()
            df.to_csv(os.path.join(OUT, f"{name}.csv"), index=False)
            print(f"{name}: {len(df)}행 {df.day.min()}~{df.day.max()} (받은 날 {date.today()})")
        except Exception as e:   # noqa: BLE001  출처 사이트 형식이 바뀌면 여기서 멈춘다 — 열 이름을 다시 본다
            print(f"{name}: 실패 — {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)


if __name__ == "__main__":
    main()
