"""블로그 검색 즉답 색인 — 종목 이름 · 별명 → 최신 값 (2026-11-10 사용자: 검색 + 블로그 챗봇 목업).

    python experiments/site-search/build_search_index.py     # output/search_index.json

AI 호출 0. 이미 모아 둔 자료만 읽는다:
  미국  stock-radar/data/snapshot.json(일봉 · 시총 · 실적 발표일) · extra.json(EPS · 목표가 · 회사 · 매출) · news.json(한국어 요약)
  한국  kr-stocks/data/snapshot.json · extra.json(EPS · 목표가 · 매출 · DART 회사 정보)
적용 때: 종목 페이지 실행(nvda-report · 한국 종목) 끝에서 이 파일을 gh-pages search/index.json 으로 올리고 테마 JS 가 jsDelivr 로 읽는다.
값마다 기준일을 넣는다 — 화면은 "현재"가 아니라 "MM-DD 종가"로 쓴다(미국은 정규장 종가만).
"""
import json
import os
import sys
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [EXP, os.path.join(EXP, "stock-radar"), os.path.join(EXP, "kr-stocks")]
import tech_signals as T  # noqa: E402
import universe as U  # noqa: E402
import universe_kr as UK  # noqa: E402

BLOG = "https://alpha-scope.blogspot.com"
OUT = os.path.join(HERE, "output", "search_index.json")

# 사람들이 실제로 치는 줄임말 · 영문 — 이름 · 티커 · 종목 코드 · 회사 영문 첫 단어는 자동으로 들어간다
EXTRA_ALIAS = {
    "NVDA": ["엔비", "엔디비아"], "GOOGL": ["구글", "알파벳", "goog"], "MSFT": ["마소", "마이크로소프트"],
    "AMZN": ["아마존"], "META": ["메타", "페이스북", "facebook"], "TSLA": ["테슬라", "테슬"], "BRK-B": ["버크셔", "brk.b", "brkb"],
    "AVGO": ["브로드컴", "브컴"], "AMD": ["에이엠디"], "MU": ["마이크론"], "JPM": ["제이피모건", "jp모건"],
    "005930.KS": ["삼전", "삼성"], "000660.KS": ["하이닉스", "하닉", "sk하닉"], "373220.KS": ["엘지엔솔", "lg엔솔", "엔솔"],
    "005380.KS": ["현차", "현대자동차"], "207940.KS": ["삼바"], "066570.KS": ["엘지전자"], "051910.KS": ["엘지화학"],
    "247540.KQ": ["에코비엠"], "015760.KS": ["한전"],
}
SHORT_TICKER = 3   # 이 길이 이하 영문 티커(V · MA · GE · HD · MU)는 낱말 그대로일 때만 — "mama" 속 MA 를 잡지 않게


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pct(a, b):
    return None if not a or b is None else round((b / a - 1) * 100, 2)


def close_on_or_before(bars, day):
    hit = None
    for b in bars:
        if b["day"] <= day:
            hit = b
        else:
            break
    return hit


def price_block(bars):
    last, prev = bars[-1], bars[-2]
    d = date.fromisoformat(last["day"])
    def back(days):
        b = close_on_or_before(bars, (d - timedelta(days=days)).isoformat())
        return pct(b["close"], last["close"]) if b else None
    ye = close_on_or_before(bars, f"{d.year - 1}-12-31")
    yr = [b for b in bars if b["day"] > (d - timedelta(days=365)).isoformat()]
    hi = max(yr, key=lambda b: b["high"] or b["close"])
    lo = min(yr, key=lambda b: b["low"] or b["close"])
    vol20 = [b["volume"] for b in bars[-21:-1] if b.get("volume")]
    return {
        "d": last["day"], "c": round(last["close"], 2), "chg": pct(prev["close"], last["close"]),
        "r": {"1w": back(7), "1m": back(30), "3m": back(91), "ytd": pct(ye["close"], last["close"]) if ye else None, "1y": back(365)},
        "h52": [round(hi["high"] or hi["close"], 2), hi["day"]], "l52": [round(lo["low"] or lo["close"], 2), lo["day"]],
        "v": last.get("volume"), "va": round(sum(vol20) / len(vol20)) if vol20 else None,
    }


def tech_block(bars, mkt):
    rows = {r["key"]: r for r in T.indicators(bars)}
    out = {}
    for k in ("rsi", "macd", "adx"):
        r = rows.get(k)
        if r:
            out[k] = [r["name"], r["text"], r["label"]]
    out["ma"] = [[m["n"], round(m["sma"], 2), m["sma_above"]] for m in T.moving_averages(bars, T.MA_PERIODS[mkt]) if m.get("sma")]
    return out


def eps_block(x):
    e, a = x.get("eps") or {}, x.get("analysts") or {}
    rc = a.get("rating_counts") or {}
    out = {}
    if e.get("current"):
        out["eps"] = [round(e["current"], 2), round(e.get("30daysAgo") or 0, 2) or None]
    if a.get("pt_mean"):
        out["pt"] = [round(a["pt_mean"], 2), round(a.get("pt_low") or 0, 2), round(a.get("pt_high") or 0, 2), sum(rc.values()) or None]
    return out


def rev_block(series):
    return [[q["cq"], q["rev"], None if q.get("yoy") is None else round(q["yoy"], 1)] for q in (series or [])[-4:]]


def next_earn(rows, today):
    fut = [r["day"] for r in rows or [] if r["day"] >= today]
    return min(fut) if fut else None


def aliases(sym, name, extra=()):
    out = {sym.lower(), name.lower().replace(" ", "")}
    base = sym.split(".")[0]
    out.add(base.lower())
    if "(" in name:   # 알파벳(구글) → 알파벳 · 구글
        a, b = name.rstrip(")").split("(", 1)
        out |= {a.strip().lower(), b.strip().lower()}
    first = (extra[0] if extra else "").strip()
    if first:
        out.add(first.lower())
    out |= {a.lower().replace(" ", "") for a in EXTRA_ALIAS.get(sym, [])}
    return sorted(a for a in out if a)


def us_news(news, sym, n=3):
    rows = [v for v in news.values() if sym in (v.get("queries") or [v.get("query")]) and (v.get("title_ko") or v.get("fact"))]
    rows.sort(key=lambda v: v.get("published_at") or "", reverse=True)
    # 원문 주소(구글 뉴스 긴 주소)는 넣지 않는다 — 색인 크기의 절반이 그것. 자세히는 종목 페이지 뉴스 칸으로
    return [[(v.get("published_at") or "")[:10], v.get("title_ko") or v.get("fact"), v.get("source") or ""] for v in rows[:n]]


def main():
    today = date.today().isoformat()
    us_snap = load(os.path.join(EXP, "stock-radar", "data", "snapshot.json"))
    us_x = load(os.path.join(EXP, "stock-radar", "data", "extra.json"))
    news = load(os.path.join(EXP, "stock-radar", "data", "news.json"))
    kr_snap = load(os.path.join(EXP, "kr-stocks", "data", "snapshot.json"))
    kr_x = load(os.path.join(EXP, "kr-stocks", "data", "extra.json"))
    stocks = []

    for sym, name, slug, sector in U.CANDIDATES:
        bars = us_snap["bars"].get(sym)
        if not bars or len(bars) < 30:
            continue
        x = us_x["stocks"].get(sym, {})
        co = x.get("company") or {}
        s = {"s": sym, "n": name, "m": "us", "sec": sector, "u": f"{BLOG}/p/{slug}.html",
             "a": aliases(sym, name, [(co.get("name") or "").split(" ")[0]]),
             "p": price_block(bars), "t": tech_block(bars, "us"), "cap": us_snap["caps"].get(sym),
             "rev": rev_block(us_x["revenue"]["series"].get(sym)), "ne": next_earn(us_snap["earnings"].get(sym), today),
             "news": us_news(news, sym)}
        s.update(eps_block(x))
        if co:
            s["co"] = {"nm": co.get("name"), "ceo": (co.get("ceo") or "").replace("  ", " "), "hq": ", ".join(v for v in (co.get("city"), co.get("state"), co.get("country")) if v),
                       "web": co.get("website"), "emp": co.get("employees"), "ex": co.get("exchange"), "listed": co.get("listed")}
        stocks.append(s)

    for sym, name, slug, sector, _groups in UK.CANDIDATES:
        bars = kr_snap["bars"].get(sym)
        if not bars or len(bars) < 30:
            continue
        code = sym.split(".")[0]
        co = kr_x["company"].get(code) or {}
        eng = (co.get("corp_name_eng") or "").split(" ")[0]
        s = {"s": sym, "n": name, "m": "kr", "sec": sector, "u": f"{BLOG}/p/{slug}.html",
             "a": aliases(sym, name, [eng] if eng else ()),
             "p": price_block(bars), "t": tech_block(bars, "kr"), "cap": kr_snap["caps"].get(sym),
             "rev": rev_block(kr_x["revenue"]["series"].get(sym)), "ne": next_earn(kr_x["earnings"].get(sym), today), "news": []}
        s.update(eps_block(kr_x["stocks"].get(sym, {})))
        if co:
            est = co.get("est_dt") or ""
            s["co"] = {"nm": co.get("corp_name"), "ceo": co.get("ceo_nm"), "hq": " ".join((co.get("adres") or "").split()),
                       "web": co.get("hm_url"), "est": f"{est[:4]}-{est[4:6]}-{est[6:]}" if len(est) == 8 else None,
                       "ex": {"Y": "유가증권", "K": "코스닥"}.get(co.get("corp_cls"))}
        stocks.append(s)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc = {"built": datetime.now().strftime("%Y-%m-%d %H:%M"), "stocks": stocks}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"만듦: {OUT} — 미국 {sum(s['m'] == 'us' for s in stocks)} · 한국 {sum(s['m'] == 'kr' for s in stocks)}종목, {os.path.getsize(OUT) / 1024:.0f}KB")


if __name__ == "__main__":
    main()
