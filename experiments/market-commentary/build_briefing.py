"""알파스코프 시황 해설 — 수집기에 보내는 묶음 파일 briefing/{날짜}-{am|pm}.json 만들기.

수집기(News-sub)가 시황 해설을 쓰고, 블로그는 이 묶음(이미 계산해 공개한 사실)만 보낸다.
형식 기준 문서: News-doc `요청-알파스코프-시황-해설.md` 4절 (형식은 블로그가 정하고, 바꾸면 v 를 올린다).

- AI 호출 0. 파이썬으로 공개 파일만 묶는다.
- 재료는 **사이트에 이미 공개한 것만**: gh-pages data.json(미국 지수 · 대형주 · 업종) · kr.json(한국) · hypo.json(증시 전망)
  · news.json(뉴스 요약 줄) + 데일리 리포트 입력의 일정(calendar) · VIX.
  issues.json(이슈 모니터링)은 관리자 미리보기 단계라 넣지 않는다.
- am = 미국 마감(한국 아침 07:30 KST 무렵, 미국 데일리 리포트 실행 끝), pm = 한국 마감(16:30 KST 무렵, 한국 증시 리포트 실행 끝).
- pm 의 미국 일정은 그날 am 묶음의 calendar 를 다시 쓴다(한국 실행에는 일정 수집이 없다 — 일정 API 를 두 번 부르지 않음).

사용:
  python build_briefing.py --slot am --report-input experiments/daily-report/output/report_input.json --out-dir deploy-briefing
  python build_briefing.py --slot pm --kr deploy/kr.json --out-dir deploy-briefing
"""

import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

V = 1
KST = ZoneInfo("Asia/Seoul")
NY = ZoneInfo("America/New_York")
RAW = "https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages"
SITE = "https://alpha-scope.blogspot.com"
MAX_BYTES = 50_000
UA = {"User-Agent": "alpha-scope/market-briefing"}

# 일정 이름 (collect_calendar.py kind) · 발표 시각(뉴욕 기준)
EVENT_NAME = {
    "CPI": "미국 소비자물가(CPI)",
    "NFP": "미국 고용보고서",
    "GDP": "미국 GDP",
    "PCE": "미국 PCE 물가",
    "CLAIMS": "미국 주간 실업수당 청구",
    "FOMC": "FOMC 금리 결정",
    "OPEX": "미국 월간 옵션 만기",
}
EVENT_NY_TIME = {"CPI": (8, 30), "NFP": (8, 30), "GDP": (8, 30), "PCE": (8, 30), "CLAIMS": (8, 30), "FOMC": (14, 0)}
US_NAME = {"NVDA": "엔비디아", "AAPL": "애플", "MSFT": "마이크로소프트", "GOOGL": "알파벳", "AMZN": "아마존",
           "META": "메타", "AVGO": "브로드컴", "TSLA": "테슬라", "BRK-B": "버크셔 해서웨이", "LLY": "일라이 릴리"}
KIND_DIR = {"positive": "up", "negative": "down", "neutral": "flat"}


def _get_json(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        print(f"[묶음] 읽기 실패 {url}: {e}")
        return None


def _load(path_or_none, name):
    """로컬 파일이 있으면 그것(방금 만든 값), 없으면 gh-pages 공개 주소."""
    if path_or_none and os.path.exists(path_or_none):
        with open(path_or_none, encoding="utf-8") as f:
            return json.load(f)
    return _get_json(f"{RAW}/{name}")


def _r(x, n=2):
    return None if x is None else round(float(x), n)


def _kst_time(day, kind):
    """뉴욕 발표 시각 → KST 'HH:MM' (다음 날이면 '(다음 날)')."""
    hm = EVENT_NY_TIME.get(kind)
    if not hm:
        return "장중" if kind == "OPEX" else ""
    d = datetime.date.fromisoformat(day)
    ny = datetime.datetime(d.year, d.month, d.day, hm[0], hm[1], tzinfo=NY)
    k = ny.astimezone(KST)
    return k.strftime("%H:%M") + (" (다음 날)" if k.date() > d else "")


def _event_rows(calendar, day):
    """calendar(14일) 중 그 미국 날짜의 일정 → [{time, what}] (KST)."""
    out = []
    for r in (calendar or {}).get("items") or []:
        if r.get("day") != day:
            continue
        kind = r.get("kind")
        if kind == "EARNINGS":
            sym = r.get("symbol", "")
            out.append({"time": "장 마감 뒤" if r.get("after_close") else "장 시작 전",
                        "what": f"{US_NAME.get(sym, sym)} 실적 발표", "market": "US"})
        elif kind in EVENT_NAME:
            out.append({"time": _kst_time(day, kind), "what": EVENT_NAME[kind], "market": "US"})
    return out


def _news(news, limit=12):
    rows = []
    for x in (news or {}).get("items") or []:
        t = x.get("title_ko") or x.get("title")
        if not t:
            continue
        rows.append({"title": t, "lines": (x.get("lines") or [])[:3], "source": x.get("source") or "",
                     "published": x.get("published") or ""})
    return rows[:limit]


def _hypotheses(hypo, market):
    rows = []
    for x in (hypo or {}).get("open") or []:
        if x.get("market") != market:
            continue
        rows.append({"label": x.get("title"), "event": x.get("event"), "url": x.get("url"), "dir": None})
    return rows


def build_am(day_kst, report_input):
    data = _load(None, "data.json") or {}
    hypo = _load(None, "hypo.json")
    news = _load(None, "news.json")
    us_day = (datetime.date.fromisoformat(day_kst) - datetime.timedelta(days=1)).isoformat()   # 지난밤 미국 장 날짜
    session = "open" if data.get("trade_date") == us_day else "closed"

    indices = [{"name": i.get("name"), "close": _r(i.get("p")), "chg_pct": _r(i.get("cp"))} for i in data.get("indices") or []]
    sectors = sorted(({"name": s.get("name"), "chg_pct": _r(s.get("cp"))} for s in data.get("sectors") or []),
                     key=lambda s: s["chg_pct"] if s["chg_pct"] is not None else 0)
    movers = sorted(({"name": US_NAME.get(s.get("s"), s.get("s")), "ticker": s.get("s"), "chg_pct": _r(s.get("cp"))}
                     for s in data.get("stocks") or []), key=lambda m: -abs(m["chg_pct"] or 0))

    signals = []
    ups = sum(1 for s in sectors if (s["chg_pct"] or 0) > 0)
    downs = sum(1 for s in sectors if (s["chg_pct"] or 0) < 0)
    if sectors:
        signals.append({"name": "업종 폭", "text": f"11개 업종 중 오름 {ups} · 내림 {downs}",
                        "dir": "up" if ups > downs else "down" if downs > ups else "flat"})
    vix = ((report_input or {}).get("macro") or {}).get("vix") or {}
    if vix.get("value") is not None:
        signals.append({"name": "VIX", "text": f"VIX {vix['value']}", "dir": "flat", "date": vix.get("date")})

    calendar = (report_input or {}).get("calendar")
    return {
        "v": V, "date": day_kst, "slot": "am", "market": "US", "session": session, "trade_date": data.get("trade_date"),
        "close": {"indices": indices, "sectors": sectors, "movers": movers[:6]},
        "signals": signals,
        "hypotheses": _hypotheses(hypo, "us"),
        "news": _news(news),
        # 아침 편 관전 포인트 = 오늘 한국장. 한국 일정 재료는 아직 없어 오늘 밤(KST) 미국 일정을 같이 준다.
        "next_session": {"market": "KR", "items": _event_rows(calendar, day_kst)},
        "calendar": calendar,   # pm 묶음이 다시 쓴다
        "links": {"report": f"{SITE}/search/label/%EB%AF%B8%EA%B5%AD%20%EC%A6%9D%EC%8B%9C%20%EB%A6%AC%ED%8F%AC%ED%8A%B8",
                  "forecast": (hypo or {}).get("list_url")},
    }


def build_pm(day_kst, kr_path):
    kr = _load(kr_path, "kr.json") or {}
    hypo = _load(None, "hypo.json")
    session = "open" if kr.get("day") == day_kst else "closed"

    stocks = kr.get("stocks") or []
    movers = sorted(({"name": s.get("name"), "ticker": s.get("s"), "chg_pct": _r(s.get("cp"))} for s in stocks),
                    key=lambda m: -abs(m["chg_pct"] or 0))
    by_sym = {s.get("s"): s for s in stocks}
    sectors = []
    for g in kr.get("sectors") or []:
        cps = [by_sym[x]["cp"] for x in g.get("syms") or [] if x in by_sym and by_sym[x].get("cp") is not None]
        if cps:
            sectors.append({"name": g.get("sector"), "chg_pct": _r(sum(cps) / len(cps)), "n": len(cps)})
    signals = [{"name": f.get("title"), "text": f"{f.get('state')} — {f.get('sub')}", "dir": KIND_DIR.get(f.get("kind"), "flat")}
               for f in kr.get("flows") or []]

    am = _get_json(f"{RAW}/briefing/{day_kst}-am.json") or {}
    return {
        "v": V, "date": day_kst, "slot": "pm", "market": "KR", "session": session, "trade_date": kr.get("day"),
        # 한국 지수 종가는 kr.json 에 없다 — 시가총액 상위 35종목 등락 · 업종 평균으로 준다
        "close": {"indices": [], "sectors": sectors, "movers": movers[:6]},
        "signals": signals,
        "hypotheses": _hypotheses(hypo, "kr"),
        "news": [],
        "next_session": {"market": "US", "items": _event_rows(am.get("calendar"), day_kst)},
        "links": {"report": f"{SITE}/search/label/%ED%95%9C%EA%B5%AD%20%EC%A6%9D%EC%8B%9C%20%EB%A6%AC%ED%8F%AC%ED%8A%B8",
                  "forecast": (hypo or {}).get("list_url")},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", choices=["am", "pm"], required=True)
    ap.add_argument("--date", help="KST 날짜 YYYY-MM-DD (기본 오늘)")
    ap.add_argument("--report-input", help="am: 데일리 리포트 report_input.json (일정 · VIX)")
    ap.add_argument("--kr", help="pm: 방금 만든 kr.json (없으면 공개 주소)")
    ap.add_argument("--out-dir", default="deploy-briefing")
    a = ap.parse_args()

    day = a.date or datetime.datetime.now(KST).date().isoformat()
    if a.slot == "am":
        ri = None
        if a.report_input and os.path.exists(a.report_input):
            with open(a.report_input, encoding="utf-8") as f:
                ri = json.load(f)
        out = build_am(day, ri)
    else:
        out = build_pm(day, a.kr)
    out["generated"] = datetime.datetime.now(KST).isoformat(timespec="seconds")

    body = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    if len(body.encode("utf-8")) > MAX_BYTES:   # 넘치면 뉴스부터, 그래도 넘치면 14일 일정을 뺀다(다음 장 일정은 남김)
        out["news"] = out["news"][:5]
        body = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
        if len(body.encode("utf-8")) > MAX_BYTES:
            out.pop("calendar", None)
            body = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    path = os.path.join(a.out_dir, "briefing", f"{day}-{a.slot}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"[묶음] {path} {len(body.encode('utf-8')):,}B session={out['session']} "
          f"뉴스 {len(out['news'])} · 일정 {len(out['next_session']['items'])} · 신호 {len(out['signals'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
