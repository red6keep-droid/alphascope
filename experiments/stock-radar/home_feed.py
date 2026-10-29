"""홈 `관심 종목` · `섹터 상위 종목` 카드 데이터 → output/home/stocks.json (2026-10-21 사용자: "홈에 카드를 만들어서 관심 종목으로
카드 만들어라. 그리고 섹터 상위 종목 카드도. 그래서 그걸 타고 가서 개별 종목을 볼 수 있게").

    python experiments/stock-radar/home_feed.py          # data/snapshot.json(수집 결과) + data/pages_live.json(발행된 페이지) → output/home/stocks.json

워크플로(nvda-report.yml)가 publish_pages 뒤에 돌리고 gh-pages 에 올린다. 홈 JS(alphaflow-home.html `관심 종목` · `섹터 상위 종목`)가
jsDelivr 로 읽는다. 종가 기준(하루 1회) — 15분 시세(data.json)와 다른 파일인 이유: 후보 49개의 시세 · 섹터 · 페이지 유무는 레이더가 안다.

page: 그 종목의 고정 페이지가 실제로 있는지 (publish_pages 가 남긴 pages_live.json). 아직 없는 종목(하루 10개씩 만드는 중)은
홈 카드가 목록 페이지로 보낸다 — 404 링크를 홈에 두지 않는다.
"""

import datetime
import json
import os
import sys

import analyze
import collect
import universe as U

BASE = os.path.dirname(os.path.abspath(__file__))
PAGES_LIVE = os.path.join(BASE, "data", "pages_live.json")
OUT = os.path.join(BASE, "output", "home", "stocks.json")
EVENT_DAYS = 30   # 홈 맨 위 일정 배너 — 이 기간 안 실적 발표 (홈 JS 가 오늘 이후 가까운 3개를 고른다)


def _live():
    try:
        with open(PAGES_LIVE, encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def events(a, snap, live):
    """홈 맨 위 일정 배너 (2026-10-28 사용자: 실적 발표 등 롤링 배너 3개, 누르면 그 종목 상세 화면 캘린더 탭).
    고정 페이지가 있는 종목만 — 링크가 404 가 되지 않게. 가까운 날 · 큰 시총 순."""
    end = (datetime.date.fromisoformat(a["day"]) + datetime.timedelta(days=EVENT_DAYS)).isoformat()
    out = []
    for s in a["stocks"]:
        nxt = (s.get("earnings") or {}).get("next")
        if not nxt or nxt > end or s["sym"] in U.REPORT_TYPE or s["sym"] not in live:
            continue
        when = next((x.get("when") for x in (snap.get("earnings") or {}).get(s["sym"]) or [] if x["day"] == nxt), None)
        out.append({"kind": "earnings", "day": nxt, "when": when, "s": s["sym"], "name": U.BY_SYM[s["sym"]][1], "slug": U.BY_SYM[s["sym"]][2], "mc": int(s["cap"]) if s.get("cap") else None})
    return sorted(out, key=lambda e: (e["day"], -(e["mc"] or 0)))


def build(a, live, snap=None):
    by = {s["sym"]: s for s in a["stocks"]}
    rows = []
    for sym, name, slug, sector in U.CANDIDATES:
        s = by.get(sym)
        if not s or s.get("close") is None:
            continue
        rows.append({
            "s": sym, "name": name, "sector": sector, "slug": slug,
            "page": sym in live or sym in U.REPORT_TYPE,   # NVDA 는 리포트형(엔비디아 글 목록으로)
            "p": round(float(s["close"]), 2), "cp": round(float(s["ret_1d"]), 2) if s.get("ret_1d") is not None else None,
            "mc": int(s["cap"]) if s.get("cap") else None, "rank": s.get("rank"), "top": bool(s.get("in_top")),
        })
    have = {r["s"] for r in rows}
    watch = [{"group": g, "syms": [x for x in syms if x in have]} for g, syms in U.WATCH]
    sectors = {}
    for r in rows:
        sectors.setdefault(r["sector"], []).append(r)
    sector_rows = []
    for sec, items in sectors.items():
        items = sorted(items, key=lambda r: -(r["mc"] or 0))
        sector_rows.append({"sector": sec, "syms": [r["s"] for r in items[:3]], "cap": items[0]["mc"] or 0})
    sector_rows.sort(key=lambda x: -x["cap"])   # 섹터 순서 = 1위 종목 시총 순
    return {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "day": a["day"], "stocks": rows, "watch": watch, "sectors": [{"sector": x["sector"], "syms": x["syms"]} for x in sector_rows],
        "events": events(a, snap or {}, live),
    }


def write(a=None):
    snap = collect.load()
    a = a or analyze.run(snap)
    data = build(a, _live(), snap)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"[home] 종목 {len(data['stocks'])} · 페이지 있음 {sum(1 for r in data['stocks'] if r['page'])} · 관심 묶음 {len(data['watch'])} · 섹터 {len(data['sectors'])} · 일정 {len(data['events'])} → {OUT}")
    return OUT


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    write()
