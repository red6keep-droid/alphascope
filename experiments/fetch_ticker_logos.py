"""종목 로고 받기 — 우리가 다루는 종목만 받아 output/logos 에 두고, gh-pages images/logos 로 올린다.

한국 종목(kr-stocks/universe_kr.py)은 같은 저장소 같은 커밋의 logos/korea/<종목코드> — 키는 005930.KS, 파일은 KR_005930.svg.

출처: MrChartist/global-stock-logos (코드 MIT, 로고 대부분은 TradingView 공개 로고 서비스에서 모은 것).
고정한 커밋에서만 받는다 — 저장소가 바뀌어도 우리 파일은 그대로. 받은 기록은 ref/ticker_logos.json.

운영지침 4-6 (2026-10-22 사용자 결정으로 바꿈): 로고는 종목 식별 용도로만, 원래 모양 그대로, 우리 gh-pages 사본만 쓴다.
없는 종목 · 삭제 요청이 온 종목은 design_kit.ticker_logo 가 티커 두 글자 배지로 그린다 (REMOVED 에 넣고 다시 돌린다).

    python experiments/fetch_ticker_logos.py   # 그 뒤 gh-pages 에 images/logos/* 복사 · 푸시
"""

import datetime
import importlib.util
import json
import os
import re
import sys
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "output", "logos")
META = os.path.join(BASE, "ref", "ticker_logos.json")

REPO = "MrChartist/global-stock-logos"
COMMIT = "0f4bf995d9c90d752461ebb7f7604da3290f97a1"   # 2026-10-22 고정
RAW = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/logos/us/{{sym}}.{{ext}}"   # 대부분 svg, 일부(META · JPM …)는 png 만 있다
RAW_KR = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/logos/korea/{{sym}}.{{ext}}"   # 한국: 6자리 종목 코드 (2026-10-25)

REMOVED = set()   # 삭제 요청 · 잘못된 로고 — 배지로 돌린다

EXTRA = ["SPY", "QQQ", "SMH", "SOXX", "XLK", "XLY", "XLF", "XLC", "XLE", "XLV", "XLI", "XLP", "XLU", "XLB", "XLRE",
         "TSLA", "NFLX", "PLTR", "COIN", "MSTR", "UBER", "SHOP", "CRM", "ADBE", "QCOM", "TXN", "ARM", "SMCI", "DELL"]

# <img> 로만 쓰므로 스크립트는 돌지 않지만, 받은 파일 자체도 깨끗해야 한다
BAD = re.compile(r"<script|<foreignObject|\son\w+\s*=|javascript:|(?:xlink:)?href\s*=\s*[\"'](?!#)|<!ENTITY|<iframe", re.I)


def _load(name, path):
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tickers():
    syms = set(EXTRA)
    u = _load("sr_universe", os.path.join(BASE, "stock-radar", "universe.py"))
    syms |= {c[0] for c in u.CANDIDATES}
    syms |= {s for _, group in u.WATCH for s in group}
    syms |= {v[0] for v in u.SECTOR_ETF.values()} | {u.BENCH}
    t = _load("tm_themes", os.path.join(BASE, "theme-monitor", "themes.py"))
    syms |= {s for th in t.THEMES for _, group in th.get("baskets", []) for s in group}
    y = _load("dr_yahoo", os.path.join(BASE, "daily-report", "collect_yahoo.py"))
    syms |= set(y.HISTORY_UNIVERSE["mega"])
    return sorted(s for s in syms if re.fullmatch(r"[A-Z][A-Z.\-]{0,6}", s))


def kr_tickers():
    """한국 종목 — yfinance 표기(005930.KS) 그대로 키로 쓴다. 파일 이름은 KR_005930 (미국 숫자 티커와 겹치지 않게)."""
    u = _load("kr_universe", os.path.join(BASE, "kr-stocks", "universe_kr.py"))
    return sorted(c[0] for c in u.CANDIDATES)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AlphaScope-logos/0.1"})
    return urllib.request.urlopen(req, timeout=30).read()


def main():
    os.makedirs(OUT, exist_ok=True)
    meta, missing = {}, []
    today = datetime.date.today().isoformat()
    jobs = [(s, RAW, [s, s.replace("-", "."), s.replace("-", "")], s) for s in tickers()]
    jobs += [(s, RAW_KR, [s.split(".")[0]], "KR_" + s.split(".")[0]) for s in kr_tickers()]
    for sym, raw, cands, fname in jobs:
        if sym in REMOVED:
            continue
        data = ext = None
        for cand in dict.fromkeys(cands):
            for e in ("svg", "png"):
                try:
                    data, ext = get(raw.format(sym=cand, ext=e)), e
                    break
                except Exception:
                    continue
            if data:
                break
        if ext == "svg":
            svg = data.decode("utf-8", "replace")
            if "<svg" not in svg or BAD.search(svg):
                print(f"{sym}: SVG 가 아니거나 위험한 요소가 있어 버림")
                missing.append(sym)
                continue
            data = re.sub(r"^\s*<!--.*?-->\s*", "", svg, flags=re.S).encode("utf-8")   # 원본 주석 — 출처는 ref 에 남긴다
        elif ext == "png" and not data.startswith(bytes([0x89]) + b"PNG"):
            data = None
        if not data:
            missing.append(sym)
            continue
        with open(os.path.join(OUT, f"{fname}.{ext}"), "wb") as f:
            f.write(data)
        meta[sym] = {"file": f"{fname}.{ext}", "source": f"{REPO}@{COMMIT[:7]}", "fetched": today}
    os.makedirs(os.path.dirname(META), exist_ok=True)
    with open(META, "w", encoding="utf-8") as f:
        json.dump({"_note": "종목 로고 — 식별 용도. 각 로고는 해당 회사의 상표. 출처 MrChartist/global-stock-logos (TradingView 로고 서비스)",
                   "logos": dict(sorted(meta.items()))}, f, ensure_ascii=False, indent=1)
    print(f"로고 {len(meta)}개 받음 · 없음 {len(missing)}: {missing}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
