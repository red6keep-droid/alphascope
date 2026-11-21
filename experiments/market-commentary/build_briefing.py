"""알파스코프 시황 해설 — 수집기에 보내는 묶음 파일 briefing/{날짜}-{am|pm}.json 만들기.

수집기(News-sub)가 시황 해설을 쓰고, 블로그는 이 묶음(이미 계산해 공개한 사실)만 보낸다.
형식 기준 문서: News-doc `요청-알파스코프-시황-해설.md` 4절 (형식은 블로그가 정하고, 바꾸면 v 를 올린다).

- AI 호출 0. 파이썬으로 공개 파일만 묶는다.
- 재료는 **사이트에 이미 공개한 것만**: gh-pages data.json(미국 지수 · 대형주 · 업종) · kr.json(한국) · hypo.json(증시 전망)
  · news.json(뉴스 요약 줄) + 데일리 리포트 입력의 일정(calendar) · VIX.
  issues.json(이슈 모니터링)은 관리자 미리보기 단계라 넣지 않는다.
- 상한 · 자르기 없음: 읽는 쪽이 수집기 하루 2번뿐이라 크기가 문제 되지 않고, 무엇을 쓸지는 수집기가 고른다(조용히 버리지 않기).
- am = 미국 마감(한국 아침 07:30 KST 무렵, 미국 데일리 리포트 실행 끝), pm = 한국 마감(16:30 KST 무렵, 한국 증시 리포트 실행 끝).
- pm 의 미국 일정은 그날 am 묶음의 calendar 를 다시 쓴다(한국 실행에는 일정 수집이 없다 — 일정 API 를 두 번 부르지 않음).
- 월요일 am(Q18, 2026-11-16): 미국 리포트가 월요일 아침엔 안 돌므로 토요일 실행이 월요일 묶음도 같이 만든다
  (`ahead: true`, generated = 토요일). 금요일 미국 마감 숫자 + 월요일 밤 미국 일정 + 월요일 한국장 시작 줄.
  토요일 am 묶음은 한국장이 쉬므로 장 시작 줄이 없다.
- next_session 줄마다 kind: open(한국장 시작 줄, Q17) · event(일정). event 는 us_day(미국 날짜)도 준다.

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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kr-stocks"))
from universe_kr import EXAM_DAYS  # noqa: E402  수능일 목록(해마다 한 줄) — 장 시각 원본 하나


def kr_open_time(d):
    """한국장 여는 시각 — 수능일 · 새해 첫 거래일은 10:00, 그 밖 09:00 (2026-11-19 사용자 "09:00 은 항상 고정 글이야?").
    새해 첫 거래일 = 1월 2일부터 첫 평일(1월 1일 휴장). 1월 초 다른 휴장일은 없다고 본다."""
    if d.isoformat() in EXAM_DAYS:
        return "10:00"
    if d.month == 1 and d.day >= 2 and d.weekday() < 5:
        first = datetime.date(d.year, 1, 2)
        while first.weekday() >= 5:
            first += datetime.timedelta(days=1)
        if d == first:
            return "10:00"
    return "09:00"

V = 1
KST = ZoneInfo("Asia/Seoul")
NY = ZoneInfo("America/New_York")
RAW = "https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages"
SITE = "https://www.newfact.app"
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


def _prev_weekday(d):
    """d 직전 평일(미국 장 날짜 후보). 휴장은 data.json trade_date 와 대조해 session 으로 걸러진다."""
    d -= datetime.timedelta(days=1)
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d


def _event_rows(calendar, day):
    """calendar(14일) 중 그 미국 날짜의 일정 → [{time, what, market, kind: event, us_day}] (time 은 KST)."""
    out = []
    for r in (calendar or {}).get("items") or []:
        if r.get("day") != day:
            continue
        kind = r.get("kind")
        if kind == "EARNINGS":
            sym = r.get("symbol", "")
            out.append({"time": "장 마감 뒤" if r.get("after_close") else "장 시작 전",
                        "what": f"{US_NAME.get(sym, sym)} 실적 발표", "market": "US", "kind": "event", "us_day": day})
        elif kind in EVENT_NAME:
            out.append({"time": _kst_time(day, kind), "what": EVENT_NAME[kind], "market": "US", "kind": "event", "us_day": day})
    return out


def _news(news):
    rows = []
    for x in (news or {}).get("items") or []:
        t = x.get("title_ko") or x.get("title")
        if not t:
            continue
        rows.append({"title": t, "lines": x.get("lines") or [], "source": x.get("source") or "",
                     "published": x.get("published") or ""})
    return rows


def _hypotheses(hypo, market):
    rows = []
    for x in (hypo or {}).get("open") or []:
        if x.get("market") != market:
            continue
        rows.append({"label": x.get("title"), "event": x.get("event"), "url": x.get("url"), "dir": None})
    return rows


def build_am(day_kst, report_input, data=None, hypo=None, news=None):
    data = data if data is not None else (_load(None, "data.json") or {})
    hypo = hypo if hypo is not None else _load(None, "hypo.json")
    news = news if news is not None else _load(None, "news.json")
    d = datetime.date.fromisoformat(day_kst)
    us_day = _prev_weekday(d).isoformat()   # 직전 미국 장 날짜 (월요일 → 금요일)
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
    if vix.get("value") is not None:   # 수준만 있고 전날 대비가 없어 방향을 못 정함 → flat (근거 건수에 안 셈)
        signals.append({"name": "VIX", "text": f"VIX {vix['value']}", "dir": "flat", "date": vix.get("date")})

    calendar = (report_input or {}).get("calendar")
    # 관전 포인트 후보 맨 앞 = 한국장 시작 줄(Q16): 지난밤 가장 크게 움직인 업종 · 대형주. 숫자는 close 와 같다
    nxt = _event_rows(calendar, day_kst)
    if session == "open" and d.weekday() < 5:   # 토요일 am 은 한국장이 쉰다 → 장 시작 줄 없음
        pct = lambda x: f"{x:+.2f}%".replace("-", "−")
        top_s = max((x for x in sectors if x["chg_pct"] is not None), key=lambda x: abs(x["chg_pct"]), default=None)
        top_m = next((m for m in movers if m["chg_pct"] is not None), None)
        parts = ([f"{top_s['name']} 업종 {pct(top_s['chg_pct'])}"] if top_s else []) + ([f"{top_m['name']} {pct(top_m['chg_pct'])}"] if top_m else [])
        if parts:
            when = "지난밤 미국 " if us_day == (d - datetime.timedelta(days=1)).isoformat() else "지난 금요일 미국 "
            nxt.insert(0, {"time": kr_open_time(d), "what": when + " · ".join(parts) + " 뒤 한국장 첫 반응",
                           "market": "KR", "kind": "open"})
    return {
        "v": V, "date": day_kst, "slot": "am", "market": "US", "session": session, "trade_date": data.get("trade_date"),
        "close": {"indices": indices, "sectors": sectors, "movers": movers},
        "signals": signals,
        "hypotheses": _hypotheses(hypo, "us"),
        "news": _news(news),
        # 아침 편 관전 포인트 = 오늘 한국장. 한국 일정 재료는 아직 없어 오늘 밤(KST) 미국 일정을 같이 준다.
        "next_session": {"market": "KR", "items": nxt},
        "calendar": calendar,   # pm 묶음이 다시 쓴다
        "links": {"report": f"{SITE}/search/label/%EB%AF%B8%EA%B5%AD%20%EC%A6%9D%EC%8B%9C%20%EB%A6%AC%ED%8F%AC%ED%8A%B8",
                  "forecast": (hypo or {}).get("list_url")},
    }


LISTS_URLS = ("https://alpha-scope.pages.dev/{m}/_lists.json",
              "https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@quick-{m}/{m}/_lists.json")
SECTOR11 = {"기술", "커뮤니케이션", "경기 소비재", "필수 소비재", "헬스케어", "금융", "산업재", "소재", "에너지", "유틸리티", "부동산"}


def read_lists_doc(m):
    """종목 모아보기 목록 파일(간단 종목 실행이 매일 올림, build_lists.py) — 읽는 순서 = stock_lists.js 와 같다. 못 받으면 None."""
    for url in LISTS_URLS:
        doc = _get_json(url.format(m=m))
        if doc and doc.get("rows"):
            return doc
    return None


def sectors_from_lists(doc, day):
    """업종 등락 = 종목 모아보기 `업종` 탭 지도와 같은 셈 (2026-11-20 사용자 "업종 숫자가 서로 다르다").
    목록 파일의 그날 종목 전체(한국 약 350) · 같은 업종 분류(GICS 11) · 단순 평균(stock_lists.js heatmap avg).
    옛 셈 = kr.json 업종 묶음의 대형주 1~3개 평균 → 커뮤니케이션이 SK텔레콤 하나에 끌려 −6.63%(업종 탭 −3.08%), 경기 소비재 = 현대차 · 기아 둘(−4.14%, 업종 탭 −1.44%).
    목록 파일 날짜가 장 날짜와 다르면 None (부르는 쪽이 옛 셈으로). `기타`(분류 못 한 종목)는 업종이 아니라 뺀다."""
    if not doc or not day or doc.get("d") != day:
        return None
    by = {}
    for r in doc.get("rows") or []:
        if r.get("r") is not None and r.get("s") in SECTOR11:
            by.setdefault(r["s"], []).append(r["r"])
    return [{"name": k, "chg_pct": _r(sum(v) / len(v)), "n": len(v)} for k, v in by.items()] or None


def build_pm(day_kst, kr_path):
    kr = _load(kr_path, "kr.json") or {}
    hypo = _load(None, "hypo.json")
    session = "open" if kr.get("day") == day_kst else "closed"

    stocks = kr.get("stocks") or []
    movers = sorted(({"name": s.get("name"), "ticker": s.get("s"), "chg_pct": _r(s.get("cp"))} for s in stocks),
                    key=lambda m: -abs(m["chg_pct"] or 0))
    by_sym = {s.get("s"): s for s in stocks}
    sectors = sectors_from_lists(read_lists_doc("kr"), kr.get("day"))
    sectors_basis = "lists"
    if not sectors:   # 목록 파일이 아직 그날 것이 아니면(간단 종목 실행 17:01 전) 옛 셈 — 발행기가 글을 낼 때 목록 파일로 다시 셈한다
        sectors, sectors_basis = [], "kr-top"
        for g in kr.get("sectors") or []:
            cps = [by_sym[x]["cp"] for x in g.get("syms") or [] if x in by_sym and by_sym[x].get("cp") is not None]
            if cps:
                sectors.append({"name": g.get("sector"), "chg_pct": _r(sum(cps) / len(cps)), "n": len(cps)})
    print(f"[묶음] 업종 {len(sectors)}개 — {'종목 모아보기 목록 전체 평균' if sectors_basis == 'lists' else '대형주 묶음 평균(목록 파일 아직 없음)'}")
    # dir = 주가 쪽 방향(Q10): 밤사이 미국 EWY 상승 · 외국인 순매수 · 원화 강세 = up. 시장 열기(거래대금)는 방향이 아니라 늘 flat
    signals = [{"name": f.get("title"), "text": f"{f.get('state')} — {f.get('sub')}",
                "dir": "flat" if f.get("title") == "시장 열기" else KIND_DIR.get(f.get("kind"), "flat")}
               for f in kr.get("flows") or []]

    am = _get_json(f"{RAW}/briefing/{day_kst}-am.json") or {}
    return {
        "v": V, "date": day_kst, "slot": "pm", "market": "KR", "session": session, "trade_date": kr.get("day"),
        # 코스피 · 코스닥 종가 = kr.json indices(2026-11-17, 수집기 14절 장 날짜 첫 줄) — 봉 날짜가 장 날짜와 같은 것만. 옛 kr.json 이면 빈 칸
        "close": {"indices": [{"name": i.get("name"), "close": _r(i.get("close")), "chg_pct": _r(i.get("chg_pct"))}
                              for i in kr.get("indices") or [] if i.get("day") == kr.get("day")],
                  "sectors": sectors, "sectors_basis": sectors_basis, "movers": movers,
                  # 외국인 순매수(코스피 · 코스닥 · 20일 누적 · 연속) · 원/달러 · 국고채 3년 — kr.json figures 그대로, 칸마다 day(ECOS 는 하루 늦는 날이 있어 거르지 않고 날짜로 알림, 수집기 Q20)
                  "figures": kr.get("figures") or []},
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
    outs = []
    if a.slot == "am":
        ri = None
        if a.report_input and os.path.exists(a.report_input):
            with open(a.report_input, encoding="utf-8") as f:
                ri = json.load(f)
        data, hypo, news = _load(None, "data.json") or {}, _load(None, "hypo.json"), _load(None, "news.json")
        outs.append(build_am(day, ri, data, hypo, news))
        if datetime.date.fromisoformat(day).weekday() == 5:   # 토요일 실행 → 월요일 am 묶음도 (Q18)
            monday = (datetime.date.fromisoformat(day) + datetime.timedelta(days=2)).isoformat()
            outs.append(dict(build_am(monday, ri, data, hypo, news), ahead=True))
    else:
        outs.append(build_pm(day, a.kr))
    now = datetime.datetime.now(KST).isoformat(timespec="seconds")
    for out in outs:
        out["generated"] = now
        body = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
        path = os.path.join(a.out_dir, "briefing", f"{out['date']}-{a.slot}.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        print(f"[묶음] {path} {len(body.encode('utf-8')):,}B session={out['session']} "
              f"뉴스 {len(out['news'])} · 일정 {len(out['next_session']['items'])} · 신호 {len(out['signals'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
