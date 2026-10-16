"""경제 캘린더 날짜표 — FRED 발표일 (이슈 저장소 3절 1 · 2, 볼린저 계획 2-A).

    python experiments/issue_store/fetch_calendar.py

저장: data/store/calendar/econ_releases.csv — day, release, release_id, kind, subkind
발표 시각은 미국 동부 08:30 (장 시작 전)이 대부분 — 예외는 RELEASES 의 time 칸. 반응은 그날 시가 갭부터 본다.
FOMC 는 fetch_fomc.py 가 따로 (연준 목표금리 시계열 + 회의 일정).
"""

import os

import pandas as pd
import requests
from dotenv import dotenv_values

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "data", "store", "calendar")

# release_id: (subkind, 시각 ET) — kind 는 모두 "경제지표"
RELEASES = {
    10: ("CPI", "08:30"), 46: ("PPI", "08:30"), 54: ("PCE", "08:30"),
    50: ("고용 보고서", "08:30"), 180: ("주간 실업수당", "08:30"), 192: ("JOLTS", "10:00"), 194: ("ADP 고용", "08:15"),
    53: ("GDP", "08:30"), 9: ("소매판매", "08:30"), 13: ("산업생산", "09:15"),
    91: ("미시간 소비자심리", "10:00"), 27: ("주택 착공", "08:30"), 291: ("기존 주택 판매", "10:00"),
}
GROUP = {"CPI": "물가", "PPI": "물가", "PCE": "물가", "고용 보고서": "고용", "주간 실업수당": "고용", "JOLTS": "고용", "ADP 고용": "고용",
         "GDP": "성장", "소매판매": "성장", "산업생산": "성장", "미시간 소비자심리": "심리", "주택 착공": "주택", "기존 주택 판매": "주택"}


def main():
    key = dotenv_values(os.path.join(ROOT, ".env")).get("FRED_API_KEY") or os.environ.get("FRED_API_KEY")
    rows = []
    for rid, (sub, t) in RELEASES.items():
        r = requests.get("https://api.stlouisfed.org/fred/release/dates", params={
            "release_id": rid, "api_key": key, "file_type": "json", "realtime_start": "1776-07-04",
            "include_release_dates_with_no_data": "false", "limit": 10000, "sort_order": "asc"}, timeout=60)
        r.raise_for_status()
        ds = [d["date"] for d in r.json().get("release_dates", [])]
        rows += [{"day": d, "kind": "경제지표", "group": GROUP[sub], "subkind": sub, "time_et": t, "release_id": rid} for d in ds]
        print(f"{sub:>10}  {len(ds):>5}건  {ds[0] if ds else '-'} ~ {ds[-1] if ds else '-'}")
    os.makedirs(OUT, exist_ok=True)
    df = pd.DataFrame(rows).drop_duplicates(["day", "subkind"]).sort_values(["day", "subkind"])
    df.to_csv(os.path.join(OUT, "econ_releases.csv"), index=False)
    print(f"저장 {len(df)}건 → {os.path.join(OUT, 'econ_releases.csv')}")


if __name__ == "__main__":
    main()
