"""홈 한국 탭 데이터 kr.json — 미국 stock-radar/home_feed.py(stocks.json)와 같은 모양 + 시장 흐름 세 질문 (기획 11-4).

    python home_feed_kr.py        # data/*.json(분석 결과) → output/home/kr.json
gh-pages 에 올리고 홈이 읽는다. 종목 줄 = {s(종목 코드), name, sector, slug, page, p(종가 원), cp(전일 대비 %), mc(시총 원), v(거래량 주), tv(거래대금 원), rank, top}.
"""
import datetime
import json
import os
import sys

import analyze_kr
import collect_kr
import universe_kr as U

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "output", "home", "kr.json")
PAGES_LIVE = os.path.join(BASE, "data", "pages_live.json")   # publish_pages_kr 가 쓴다 — 블로거에 있는 페이지 키 목록


def _live():
    try:
        with open(PAGES_LIVE, encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


def _flow_rows(m):
    """홈 '시장 흐름' 탭 세 줄 — 테마 목록과 같은 모양 {title, question, state, kind, sub, url}. 값은 전부 파이썬 계산."""
    rows = []
    ov = {x["sym"]: x["before"] for x in (m or {}).get("overnight") or []}   # K24 · K25 밤사이 미국 — 다음날 시가를 가장 잘 설명한 변수 (10-25 검증)
    if ov.get("EWY"):
        r = ov["EWY"]["ret"]
        sub = f"한국 ETF(EWY) {r:+.1f}%" + (f" · 반도체(SOX) {ov['^SOX']['ret']:+.1f}%" if ov.get("^SOX") else "") + (f" · VIX {ov['^VIX']['ret']:+.1f}p" if ov.get("^VIX") else "")
        rows.append({"title": "밤사이 미국", "question": "밤사이 미국은?", "state": "한국 ETF 상승" if r > 0.3 else "한국 ETF 하락" if r < -0.3 else "큰 변화 없음",
                     "kind": "positive" if r > 0.3 else "negative" if r < -0.3 else "neutral", "sub": sub.replace("-", "−"), "url": U.LIST_URL})
    f = (m or {}).get("foreign")
    if f:
        buy = f["today"] > 0
        cum = f["cum20"] / 1e4
        rows.append({"title": "외국인 수급", "question": "외국인은 사고 있나?", "state": f"오늘 {'순매수' if buy else '순매도'}", "kind": "positive" if buy else "negative",
                     "sub": f"오늘 {f['today']:+,.0f}억 · 20일 누적 {cum:+.1f}조".replace("-", "−"), "url": U.LIST_URL})
    rt, fx = (m or {}).get("rates") or {}, (m or {}).get("fx") or {}
    k3, usd = rt.get("ktb3"), fx.get("usdkrw")
    if k3 or usd:
        parts = []
        if k3:
            parts.append(f"국고채 3년 {k3['v']:.2f}%" + (f"({k3['chg_1d'] * 100:+.0f}bp)" if k3.get("chg_1d") is not None else ""))
        if usd:
            parts.append(f"원/달러 {usd['v']:,.0f}원" + (f"({usd['chg_1d']:+.1f})" if usd.get("chg_1d") is not None else ""))
        up = (usd or {}).get("chg_1d") or 0
        rows.append({"title": "금리 · 환율", "question": "금리 · 환율은?", "state": "원화 약세" if up > 2 else "원화 강세" if up < -2 else "큰 변화 없음",
                     "kind": "negative" if up > 2 else "positive" if up < -2 else "neutral", "sub": " · ".join(parts).replace("-", "−"), "url": U.LIST_URL})
    h, n = (m or {}).get("heat"), (m or {}).get("news")
    if h:
        tr = h.get("turnover_ratio") or 1
        st = "활발" if tr >= 1.5 else "한산" if tr < 0.7 else "평소 수준"
        sub = f"거래대금 {h['turnover'] / 1e4:.1f}조(20일 평균의 {tr:.1f}배)"
        if n:
            sub += f" · 뉴스심리 {n['v']:.0f}"
        rows.append({"title": "시장 열기", "question": "시장은 얼마나 뜨겁나?", "state": st, "kind": "positive" if tr >= 1.5 else "neutral", "sub": sub, "url": U.LIST_URL})
    return rows


def build(a):
    live = _live()
    stocks = []
    for s in a["stocks"]:
        b = s.get("_bars") or []
        t = b[-1] if b else {}
        stocks.append({"s": s["code"], "sym": s["sym"], "name": s["name"], "sector": s["sector"], "slug": U.BY_SYM[s["sym"]][2], "page": s["code"] in live,
                       "p": round(s["close"]), "cp": round(s["ret_1d"], 2) if s.get("ret_1d") is not None else None, "mc": int(s["cap"]) if s.get("cap") else None,
                       "v": int(t.get("volume") or 0) or None, "tv": int((t.get("volume") or 0) * t.get("close", 0)) or None,
                       "rank": s.get("rank"), "top": bool(s.get("in_top")), "market": s["market"]})
    by = {s["sym"]: s for s in a["stocks"]}
    watch = [{"group": g, "syms": [U.code(x) for x in syms if x in by]} for g, syms in U.WATCH]
    sectors = {}
    for s in sorted(a["stocks"], key=lambda x: -(x["cap"] or 0)):
        sectors.setdefault(s["sector"], []).append(s["code"])
    sector_rows = [{"sector": k, "syms": v[:3]} for k, v in sectors.items()]
    return {"updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"), "day": a["day"], "currency": "KRW",
            "list_url": U.LIST_URL, "stocks": stocks, "watch": watch, "sectors": sector_rows, "flows": _flow_rows(a.get("market")),
            "source": "시세 Yahoo Finance · 자금 흐름 한국은행 ECOS"}


def write(a=None):
    if a is None:
        snap, flows, hist = collect_kr.load()
        a = analyze_kr.run(snap, flows, hist)
    data = build(a)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"[kr-home] 종목 {len(data['stocks'])} · 묶음 {len(data['watch'])} · 섹터 {len(data['sectors'])} · 시장 흐름 {len(data['flows'])}줄 → {OUT}")
    return data


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    write()
