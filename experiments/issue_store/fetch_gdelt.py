"""과거 뉴스 · 분위기 일별 백필 — GDELT DOC 2.0 (2017~, 무료 · 공개) (2026-11-07 사용자 "과거 뉴스 채우기 진행", 기획 9-3 의 1).

    python experiments/issue_store/fetch_gdelt.py            # 받을 것만 받고 이어 받기(끊겨도 다시 돌리면 이어짐)
    python experiments/issue_store/fetch_gdelt.py --build    # 받은 원자료 → data/store/gdelt/{topic}.csv (day, count, total, share, tone)

왜: 우리 이슈 코드(뉴스 분류)는 2026-11-01 부터라 "뉴스 동반 급변은 이어지고 뉴스 없는 급변은 되돌린다"(Chan 2003 가중) ·
경고 카드의 "뉴스가 부정적일 때" · 동행 · 사건 이름 붙이기를 과거로 검증할 수 없다. GDELT 주제별 기사 비중 · 어조를 이슈 코드의 **대리**로 쓴다.
- 주제 = 이슈 코드와 같은 이름(TOPICS), 영어 기사(sourcelang:english). 비중 = 그 주제 기사 수 ÷ 그날 전체 감시 기사 수.
- 어조 = GDELT Average Tone(음수 = 부정). 독자에게는 숫자 X — "부정 기사가 많았던 날" 같은 조건으로만 쓴다.
- 한도: 5초에 한 번(GDELT 안내) → 8초 간격, 막히면 30초씩 늘려 쉼. 연 단위로 나눠 받아 raw/ 에 캐시.
- AI 호출 0.
"""
import argparse
import csv
import io
import os
import sys
import time
import urllib.parse
from datetime import date

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "data", "store", "gdelt")
RAW = os.path.join(OUT, "raw")
API = "https://api.gdeltproject.org/api/v2/doc/doc"
GAP = 8.0   # 안내는 5초지만 넉넉히 (2026-11-07 시험 중 몇 번 막힘)
START_YEAR = 2017

# 이슈 코드 → GDELT 검색어 (영어 기사). 뉴스 분류 issue_codes.ISSUES 와 같은 이름
TOPICS = {
    "MARKET": '("stock market" OR "wall street" OR "s&p 500" OR nasdaq OR "dow jones")',
    "RATES_FED": '("federal reserve" OR "interest rate" OR "rate cut" OR "rate hike" OR fomc OR powell)',
    "INFLATION": '(inflation OR "consumer price index" OR "cpi report" OR "price pressures")',
    "GROWTH_JOBS": '(recession OR "jobs report" OR unemployment OR payrolls OR "gdp growth")',
    "TARIFF_TRADE": '(tariff OR tariffs OR "trade war" OR "trade deal")',
    "GEOPOLITICS": '(war OR invasion OR missile OR airstrike OR "military strike" OR terrorist)',
    "OIL_ENERGY": '("oil prices" OR crude OR opec OR "natural gas prices")',
    "AI_CAPEX": '(semiconductor OR "chip stocks" OR nvidia OR "data center" OR "artificial intelligence spending")',
    "REGULATION": '(antitrust OR "export controls" OR "export ban" OR regulators OR "chip ban")',
    "FISCAL_POLITICS": '(election OR "government shutdown" OR "debt ceiling" OR "tax bill")',
    "CREDIT_BANKS": '("bank failure" OR "credit crunch" OR "bank run" OR "banking crisis" OR "credit spreads")',
    "MARKET_STRUCTURE": '("flash crash" OR "margin call" OR "short squeeze" OR "carry trade" OR "sell-off")',
}
MODES = {"vol": "timelinevolraw", "tone": "timelinetone"}


def _raw_path(topic, year, mode):
    return os.path.join(RAW, f"{topic}_{year}_{mode}.csv")


def fetch_one(topic, year, mode):
    end = min(date(year, 12, 31), date.today())
    q = f'{TOPICS[topic]} sourcelang:english'
    url = (f"{API}?query={urllib.parse.quote(q)}&mode={MODES[mode]}&format=csv"
           f"&startdatetime={year}0101000000&enddatetime={end.strftime('%Y%m%d')}235959")
    for attempt in range(4):
        r = requests.get(url, headers={"User-Agent": "alphascope-research/1.0"}, timeout=90)
        txt = r.text
        if r.status_code == 200 and txt.lstrip("﻿").startswith("Date"):
            return txt
        time.sleep(30 * (attempt + 1))   # 한도 안내 문구 · 오류면 30 · 60 · 90초 쉬고 다시
    raise RuntimeError(f"{topic} {year} {mode}: 응답 형식 아님")


def download():
    os.makedirs(RAW, exist_ok=True)
    years = range(START_YEAR, date.today().year + 1)
    todo = [(t, y, m) for t in TOPICS for y in years for m in MODES
            if not os.path.exists(_raw_path(t, y, m)) or y == date.today().year]
    print(f"[gdelt] 받을 것 {len(todo)}개 · 약 {len(todo) * GAP / 60:.0f}분")
    bad = 0
    for i, (t, y, m) in enumerate(todo, 1):
        try:
            txt = fetch_one(t, y, m)
            with open(_raw_path(t, y, m), "w", encoding="utf-8") as f:
                f.write(txt)
            if i % 20 == 0:
                print(f"[gdelt] {i}/{len(todo)}")
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"[gdelt] 실패 {t} {y} {m}: {type(e).__name__}", file=sys.stderr)
        time.sleep(GAP)
    print(f"[gdelt] 끝 — 실패 {bad}")
    return bad


def build():
    """raw → topic.csv: day, count(그 주제 기사 수), total(그날 전체 감시 기사 수), share(‰), tone."""
    for t in TOPICS:
        rows = {}
        for y in range(START_YEAR, date.today().year + 1):
            for m in MODES:
                p = _raw_path(t, y, m)
                if not os.path.exists(p):
                    continue
                for r in csv.DictReader(io.StringIO(open(p, encoding="utf-8").read().lstrip("﻿"))):
                    d = r["Date"][:10]
                    v = float(r["Value"]) if r["Value"] not in ("", None) else None
                    s = r["Series"]
                    row = rows.setdefault(d, {})
                    if m == "tone":
                        row["tone"] = v
                    elif "Total" in s:
                        row["total"] = v
                    else:
                        row["count"] = v
        out = os.path.join(OUT, f"{t}.csv")
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["day", "count", "total", "share_permille", "tone"])
            for d in sorted(rows):
                r = rows[d]
                c, tot = r.get("count"), r.get("total")
                share = round(c / tot * 1000, 4) if c is not None and tot else None
                w.writerow([d, c, tot, share, r.get("tone")])
        print(f"[gdelt] {t}: {len(rows)}일 → {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    a = ap.parse_args()
    if a.build:
        build()
    else:
        download()
        build()
