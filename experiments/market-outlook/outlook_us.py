"""시장 전망 지도(가칭) — 미국: 투자회사의 S&P 500 연말 목표를 기사 제목에서 찾기 · 거르기 (그림자 실행, 기록 · 발행 없음).

기획: 비공개 doc/기획/시장-전망-리포트-기획.md 10절 1번 · 11절(작년 시험) · 12절(미국 = 제목 파이썬, AI 0)..

    python experiments/market-outlook/outlook_us.py            # 구글 뉴스 RSS → output/outlook_us.json
    python experiments/market-outlook/outlook_us.py --cached   # 받은 RSS(output/rss_us.json)로 거르기만

- 리포트 원문 · 기사 본문은 받지 않는다. 제목(과 RSS 의 매체 이름 · 날짜 · 링크)만.
- AI 0. 회사 이름은 아래 목록과 맞을 때만, 숫자는 제목 글자에 있는 것만.
- 구글 뉴스는 짧은 간격이면 429(11-25 시험: 1.5초 간격 네 번째). 검색 사이 GAP 초, 429 면 그 검색은 건너뛴다(우회 · 재시도 X).
- 대상 넷 중 제목으로 잡히는 것은 S&P 500 목표. 미국 10년물 · 업종 비중은 제목에서 드물어 `확인 필요` 로만 모은다(화면 X).
"""
import datetime as dt
import email.utils
import json
import os
import re
import sys
import time
import urllib.parse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
RSS = os.path.join(OUT, "rss_us.json")
RESULT = os.path.join(OUT, "outlook_us.json")
UA = "Mozilla/5.0 (compatible; alphascope-research/1.0)"
GAP = 8   # 초 — 시험에서 1.5초는 429

# 회사 이름: 제목에 나오는 꼴 → 한 이름 (영어 원문 이름 그대로 — 화면은 이 이름)
FIRMS = [
    (r"Goldman", "Goldman Sachs"), (r"Morgan Stanley", "Morgan Stanley"), (r"J\.?P\.? ?Morgan|JPMorgan", "JPMorgan"),
    (r"\bUBS\b", "UBS"), (r"Bank of America|BofA", "Bank of America"), (r"\bCiti(group)?\b", "Citi"), (r"Wells Fargo", "Wells Fargo"),
    (r"Barclays", "Barclays"), (r"Deutsche", "Deutsche Bank"), (r"\bHSBC\b", "HSBC"), (r"\bBMO\b", "BMO"), (r"\bRBC\b", "RBC"),
    (r"Evercore", "Evercore ISI"), (r"Oppenheimer", "Oppenheimer"), (r"Yardeni", "Yardeni Research"), (r"Jefferies", "Jefferies"),
    (r"Stifel", "Stifel"), (r"Soci[eé]t[eé] G[eé]n[eé]rale|SocGen", "Societe Generale"), (r"\bBNP\b", "BNP Paribas"), (r"Nomura", "Nomura"),
    (r"Capital Economics", "Capital Economics"), (r"Piper Sandler", "Piper Sandler"), (r"Truist", "Truist"), (r"Ned Davis", "Ned Davis Research"),
    (r"Fundstrat", "Fundstrat"), (r"Bernstein", "Bernstein"), (r"Wolfe", "Wolfe Research"), (r"Mizuho", "Mizuho"), (r"Macquarie", "Macquarie"),
    (r"BlackRock", "BlackRock"), (r"Vanguard", "Vanguard"), (r"Schwab", "Charles Schwab"), (r"Morningstar", "Morningstar"), (r"\bCFRA\b", "CFRA"),
    (r"\bLPL\b", "LPL Financial"), (r"Ameriprise", "Ameriprise"), (r"Edward Jones", "Edward Jones"), (r"Bank of Montreal", "BMO"),
    (r"Canaccord", "Canaccord Genuity"), (r"Raymond James", "Raymond James"), (r"Cantor", "Cantor Fitzgerald"), (r"Baird", "Baird"),
]
FIRM_RX = [(re.compile(p, re.I), n) for p, n in FIRMS]
SPX = re.compile(r"S&P(\s?500)?")
LEVEL = re.compile(r"(?<![\d.$])((?:[5-9]|1[0-2]),?\d{3})(?![\d%])")   # 5,000 ~ 12,999 — 지수 자리. 퍼센트 · 달러 금액 제외
LEVEL_K = re.compile(r"(?<![\d.$])((?:[5-9]|1[0-2])(?:\.\d)?)K(?![a-z])")   # '9K' · '8.5K'
NOT_BASE = re.compile(r"(?i)\?|scenario|bull case|bear case|could (hit|reach|plunge|fall)|plunge to|extreme")   # 질문 · 시나리오 — 기본 목표가 아님
YEAR = re.compile(r"\b(20[2-3]\d)\b")
YIELD10 = re.compile(r"(?i)10-year|treasury yield")
SECTOR = re.compile(r"(?i)\boverweight\b|\bunderweight\b|top sector|favored sectors")
OUTSIDE_US = re.compile(r"(?i)\b(India|Nifty|Sensex|China|Hang Seng|Nikkei|Japan|Europe|Stoxx|FTSE|DAX|Kospi|Korea|Taiwan|ASX|TSX|Brazil)\b")


def queries(today):
    """올해 · 내년 연말 목표. 10월부터는 내년 전망 시즌. 검색어는 적게(구글 뉴스 429)."""
    years = [today.year + 1, today.year] if today.month >= 10 else [today.year]
    qs = []
    for y in years:
        qs += [f'"S&P 500" target {y} strategist when:30d', f'"S&P 500" year-end {y} target when:30d']
    qs += ['"S&P 500" target raises OR cuts strategist when:14d']   # 수시 수정
    return qs


def fetch(qs):
    rows, status = [], []
    for i, q in enumerate(qs):
        if i:
            time.sleep(GAP)
        url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=en-US&gl=US&ceid=US:en"
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        except requests.RequestException as e:
            status.append({"q": q, "status": f"error {str(e)[:60]}"})
            continue
        status.append({"q": q, "status": r.status_code})
        if r.status_code != 200:   # 429 등 — 건너뛴다(우회 X)
            continue
        import xml.etree.ElementTree as ET
        for it in ET.fromstring(r.content).iter("item"):
            rows.append({"q": q, "title": it.findtext("title") or "", "link": it.findtext("link") or "",
                         "pub": it.findtext("pubDate") or "", "source": it.findtext("source") or ""})
    return rows, status


def _date(pub):
    try:
        return email.utils.parsedate_to_datetime(pub).date().isoformat()
    except (TypeError, ValueError):
        return None


def _horizon(title, published):
    """제목의 연도(가장 큰 것) → 그해 말. 'next year' 면 기사 해 + 1. 없으면 None(확인 필요)."""
    ys = [int(y) for y in YEAR.findall(title)]
    if ys:
        return f"{max(ys)}-12"
    if published and re.search(r"(?i)next year|in two years|end of next", title):
        return f"{int(published[:4]) + 1}-12"
    if published and re.search(r"(?i)year-end|year end|end of (the )?year", title):   # 연도 없는 '연말' = 기사 해의 말
        return f"{published[:4]}-12"
    return None


def sift(rows):
    """제목 → 잡힘(회사 · 숫자 · 기한) / 확인 필요(회사나 대상은 있는데 칸이 모자람) / 걸러짐. 같은 회사 · 기한 · 값은 한 줄(출처 여럿)."""
    seen_title, got, check, dropped = set(), {}, [], 0
    for r in rows:
        t = re.sub(r"\s+-\s+[^-]+$", "", r["title"]).strip()   # 끝의 ' - 매체' 떼기
        key = re.sub(r"\W+", "", t.lower())
        if key in seen_title:
            continue
        seen_title.add(key)
        published = _date(r["pub"])
        firms = sorted({n for rx, n in FIRM_RX if rx.search(t)})
        base = {"title": t, "source": r["source"], "link": r["link"], "published": published}
        if OUTSIDE_US.search(t) and not SPX.search(t):
            dropped += 1
            continue
        if SPX.search(t):
            lv = [int(v.replace(",", "")) for v in LEVEL.findall(t)] + [round(float(v) * 1000) for v in LEVEL_K.findall(t)]
            hz = _horizon(t, published)
            if lv and NOT_BASE.search(t):
                check.append(dict(base, why="질문 · 시나리오 — 기본 목표가 아님", firms=firms))
                continue
            if len(set(lv)) > 1:   # 미국 전략가는 연말 목표를 숫자 하나로 낸다 — 범위는 '그 전에 시험할 자리' · 시나리오인 때가 많다(11-25: 모건스탠리 7,100-7,300)
                check.append(dict(base, why="숫자가 둘 이상 — 목표인지 확인", firms=firms))
                continue
            if len(firms) == 1 and lv and hz:
                vals = sorted(set(lv))
                rec = {"firm": firms[0], "target": "S&P 500", "horizon": hz,
                       "value": vals[0] if len(vals) == 1 else None, "low": vals[0] if len(vals) > 1 else None,
                       "high": vals[-1] if len(vals) > 1 else None}
                k = (rec["firm"], rec["horizon"], rec["value"], rec["low"], rec["high"])
                g = got.setdefault(k, dict(rec, sources=[]))
                g["sources"].append(base)
                continue
            if firms or lv:
                check.append(dict(base, why=("회사가 둘 이상" if len(firms) > 1 else "회사 없음" if not firms else
                                             "숫자 없음" if not lv else "기한 없음"), firms=firms))
                continue
        elif firms and (YIELD10.search(t) or SECTOR.search(t)):
            check.append(dict(base, why="10년물 · 업종 — 제목만으로는 칸을 못 채움", firms=firms))
            continue
        dropped += 1
    items = sorted(got.values(), key=lambda x: (x["horizon"], -(x["value"] or x["high"] or 0)))
    for it in items:
        it["published"] = min(s["published"] or "9999" for s in it["sources"])
    return items, check, dropped


def spx_close():
    try:
        import yfinance as yf
        h = yf.Ticker("^GSPC").history(period="5d")
        return {"day": h.index[-1].date().isoformat(), "close": round(float(h["Close"].iloc[-1]), 2)}
    except Exception as e:  # noqa: BLE001
        print(f"[outlook] S&P 500 종가 실패: {e!r}")
        return None


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(OUT, exist_ok=True)
    today = dt.date.today()
    if "--cached" in sys.argv:
        raw = json.load(open(RSS, encoding="utf-8"))
    else:
        rows, status = fetch(queries(today))
        raw = {"made": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "status": status, "rows": rows}
        json.dump(raw, open(RSS, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    items, check, dropped = sift(raw["rows"])
    out = {"made": raw["made"], "status": raw.get("status"), "spx": spx_close(), "items": items, "check": check,
           "counts": {"titles": len(raw["rows"]), "got": len(items), "check": len(check), "dropped": dropped}}
    json.dump(out, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for s in raw.get("status") or []:
        print(f"[outlook] {s['status']} · {s['q']}")
    print(f"[outlook] 제목 {len(raw['rows'])} → 잡힘 {len(items)} · 확인 필요 {len(check)} · 걸러짐 {dropped}")
    for it in items:
        v = it["value"] or f"{it['low']}~{it['high']}"
        print(f"  {it['horizon']} · {it['firm']} · {v} · {it['published']} · 출처 {len(it['sources'])}")


if __name__ == "__main__":
    main()
