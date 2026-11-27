"""r09 A안 — 종목별 언론 언급(GDELT DOC 2.0) 일별 이력 받기. 시험 10종목.

    python experiments/signal-study/news_gdelt_stock.py           # 받기(이어 받기) → data/store/gdelt_stock/{sym}.csv
    python experiments/signal-study/news_gdelt_stock.py --build   # 원자료 → csv 만

무엇: 종목마다 회사 이름 검색어로 영어 기사 수(그날 전체 감시 기사 대비) · 평균 어조. 2017-01 ~ 어제.
왜: 알파 검증(r00~r08)은 가격만 썼다. "언급이 갑자기 늘거나 어조가 좋아진 뒤 주가가 어떻게 됐나"를 9년으로 잰다.
시험 목적: 이름 검색이 그 회사 기사를 제대로 잡는지(Apple · Amazon · Intel · Meta 같은 흔한 낱말) 먼저 본다.
한도: GDELT 안내 5초에 1번이지만 11-07 짧은 재시도가 차단을 늘렸다 → 60초 간격, 429 면 30분 쉼. AI 0.
한 번에 여러 해를 부르면 하루 단위가 아닐 수 있어, 첫 종목에서 확인하고 아니면 해마다 나눠 받는다.
"""
import argparse
import csv
import io
import os
import sys
import time
import urllib.parse
from datetime import date, timedelta

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "data", "store", "gdelt_stock")
RAW = os.path.join(OUT, "raw")
API = "https://api.gdeltproject.org/api/v2/doc/doc"
GAP = 60.0
REST = 1800
START = date(2017, 1, 1)
MODES = {"vol": "timelinevolraw", "tone": "timelinetone"}

# 시험 10종목 — 이름이 뚜렷한 6 + 흔한 낱말 4(Apple · Amazon · Intel · Meta, 검색어가 쓸 만한지 보려고)
QUERIES = {
    "NVDA": '"nvidia"',
    "TSLA": '"tesla"',
    "NFLX": '"netflix"',
    "XOM": '"exxon"',
    "JPM": '("jpmorgan" OR "jp morgan")',
    "MU": '"micron"',
    "AAPL": '("apple inc" OR iphone OR "tim cook")',
    "AMZN": '(amazon -rainforest -"amazon river")',
    "INTC": '("intel corp" OR "intel chips" OR "intel shares" OR "pat gelsinger" OR "lip-bu tan")',
    "META": '(facebook OR "meta platforms" OR "mark zuckerberg")',
}


def _end():
    return date.today() - timedelta(days=1)


def _get(q, mode, a, b):
    url = (f"{API}?query={urllib.parse.quote(q + ' sourcelang:english')}&mode={MODES[mode]}&format=csv"
           f"&startdatetime={a.strftime('%Y%m%d')}000000&enddatetime={b.strftime('%Y%m%d')}235959")
    for _ in range(6):
        try:
            r = requests.get(url, headers={"User-Agent": "alphascope-research/1.0"}, timeout=120)
            t = r.text.lstrip("﻿")
            if r.status_code == 200 and t.startswith("Date"):
                return t
            print(f"[gdelt] {r.status_code} — {REST // 60}분 쉼", flush=True)
        except requests.RequestException as e:
            print(f"[gdelt] 연결 실패 {type(e).__name__} — {REST // 60}분 쉼", flush=True)
        time.sleep(REST)
    raise RuntimeError("계속 막힘")


def _daily(txt):
    days = sorted({r["Date"][:10] for r in csv.DictReader(io.StringIO(txt))})
    return len(days) > 300 * 9   # 9년 넘게 하루 단위면 하루 단위


def _spans(split):
    if not split:
        return [(START, _end(), "all")]
    return [(date(y, 1, 1), min(date(y, 12, 31), _end()), str(y)) for y in range(START.year, _end().year + 1)]


def download(syms):
    os.makedirs(RAW, exist_ok=True)
    split = os.path.exists(os.path.join(RAW, "_split"))
    first = True
    for s in syms:
        for mode in MODES:
            for a, b, tag in _spans(split):
                p = os.path.join(RAW, f"{s}_{mode}_{tag}.csv")
                if os.path.exists(p):
                    continue
                if not first:
                    time.sleep(GAP)
                first = False
                txt = _get(QUERIES[s], mode, a, b)
                if tag == "all" and not _daily(txt):
                    print("[gdelt] 여러 해 한 번 = 하루 단위 아님 → 해마다 나눠 받음", flush=True)
                    open(os.path.join(RAW, "_split"), "w").close()
                    return download(syms)
                open(p, "w", encoding="utf-8").write(txt)
                print(f"[gdelt] {s} {mode} {tag} 받음", flush=True)


def build(syms):
    for s in syms:
        rows = {}
        for f in sorted(os.listdir(RAW)):
            if not f.startswith(s + "_") or not f.endswith(".csv"):
                continue
            mode = f.split("_")[1]
            for r in csv.DictReader(io.StringIO(open(os.path.join(RAW, f), encoding="utf-8").read())):
                v = float(r["Value"]) if r["Value"] else None
                row = rows.setdefault(r["Date"][:10], {})
                if mode == "tone":
                    row["tone"] = v
                elif "Total" in r["Series"]:
                    row["total"] = v
                else:
                    row["count"] = v
        if not rows:
            continue
        with open(os.path.join(OUT, f"{s}.csv"), "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["day", "count", "total", "share_permille", "tone"])
            for d in sorted(rows):
                r = rows[d]
                c, tot = r.get("count"), r.get("total")
                w.writerow([d, c, tot, round(c / tot * 1000, 4) if c is not None and tot else None, r.get("tone")])
        print(f"[gdelt] {s}: {len(rows)}일", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    syms = [x for x in a.only.split(",") if x] or list(QUERIES)
    if not a.build:
        download(syms)
    build(syms)
