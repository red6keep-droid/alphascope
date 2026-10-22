"""실적 발표 날짜 · 시각 두 번째 출처 — SEC EDGAR 8-K 2.02항(실적 공시) 접수 시각.

평소 범위 검증 계획 C6 ① (doc/리포트-재설계/평소-범위-검증-계획.md). earnings.csv 의 발표 시각이
전부 16:20 기본값이라, EDGAR 접수 시각으로 반응일(16:00 뒤 → 다음 거래일)을 정한다.
8-K 항목 코드는 2004-08 이후만 있음.

출력: data/store/calendar/earnings_edgar.csv  (symbol, cik, filed, accepted_et, items, accession)

주의: 8-K 는 보도자료보다 늦게(몇 시간 ~ 다음 날 아침) 접수되기도 한다. 그래서 접수 시각은 "발표가 늦어도
이때까지" 라는 상한. 반응일 = 접수가 16:00 ET 전이면 그날(전날 저녁 · 그날 아침 발표 모두 그날 반응),
16:00 뒤면 다음 거래일. 틀리는 경우는 장 전 발표를 장 마감 뒤에 접수한 드문 경우뿐.
실행: .venv/bin/python experiments/issue_store/fetch_earnings_edgar.py
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "nvda-report"))
import config  # noqa: E402  EDGAR_USER_AGENT

OUT = ROOT / "data" / "store" / "calendar" / "earnings_edgar.csv"
HEADERS = {"User-Agent": config.EDGAR_USER_AGENT, "Accept-Encoding": "identity"}

# 회사가 바뀌며 CIK 가 바뀐 종목은 예전 CIK 도 함께
CIKS = {
    "NVDA": [1045810], "AMD": [2488], "QCOM": [804328],
    "AVGO": [1730168, 1649338, 1441634],          # Broadcom Inc · Broadcom Ltd · Avago
    "AMAT": [6951], "LRCX": [707549], "KLAC": [319201],
    "MU": [723125], "INTC": [50863], "TXN": [97476],
    "MSFT": [789019], "AAPL": [320193], "AMZN": [1018724],
    "GOOGL": [1652044, 1288776],                    # Alphabet · Google Inc
    "CSCO": [858877],
}


def get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    time.sleep(0.15)  # SEC 초당 10회 제한
    return data


def filings(cik):
    base = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
    sub = get(base)
    blocks = [sub["filings"]["recent"]]
    for f in sub["filings"].get("files", []):
        blocks.append(get(f"https://data.sec.gov/submissions/{f['name']}"))
    rows = []
    for b in blocks:
        for form, filed, acc, items, accno in zip(b["form"], b["filingDate"], b["acceptanceDateTime"],
                                                  b["items"], b["accessionNumber"]):
            if form == "8-K" and "2.02" in (items or ""):
                rows.append({"cik": cik, "filed": filed, "accepted_et": acc, "items": items, "accession": accno})
    return rows


def main():
    out = []
    for sym, ciks in CIKS.items():
        n0 = len(out)
        for cik in ciks:
            try:
                for r in filings(cik):
                    out.append({"symbol": sym, **r})
            except Exception as e:  # 예전 CIK 가 없을 수 있음
                print(f"[{sym}] CIK {cik} 실패: {e}")
        print(f"{sym}: {len(out) - n0}건")
    df = pd.DataFrame(out)
    # acceptanceDateTime 은 UTC (확인: 장 마감 뒤 발표가 20 ~ 21시 · 다음 날 0 ~ 2시로 찍힘) → 미 동부 시각으로
    ts = pd.to_datetime(df["accepted_et"], utc=True).dt.tz_convert("America/New_York")
    df["accepted_et"] = ts.dt.strftime("%Y-%m-%dT%H:%M:%S")
    df = df.sort_values(["symbol", "accepted_et"]).drop_duplicates(["symbol", "accession"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"저장: {OUT} ({len(df)}건)")


if __name__ == "__main__":
    main()
