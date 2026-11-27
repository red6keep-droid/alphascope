"""간단 정보(미국) = 정식 종목 렌더러 그대로.

기획 6-6: 정식 카드 가운데 막히는 줄(옵션 · 뉴스 · 방송 · 소송)만 빼고 다 — 상세 값은 바뀌는 주기에 맞춰 드물게 받아 저장해 둔다.
ETF 페이지(stock-etf/etf_pages.us_pages)와 같은 방식: 종목을 이 실행 안에서만 정식 명단(universe)에 얹고, 정식 계산(analyze · analyze_tabs)과
정식 카드(render_pages)를 그대로 부른다. 정식과 다른 것:
  - 탭 = 오늘 · 매수의견(애널리스트 · 증권사) · 실적 · 업계상황 · 기업. 시장 예상 흔들림(옵션) · 소송은 없다.
    한국 연관 종목 = 정식과 같은 sec_pairs — 검증 통과 짝(ref/kr_us_links.json)이 있는 22종목(GM · BA 등)만 막대 · 기록 표 (11-15부터, 11-16 GM · BA 렌더로 확인).
    방송 의견 · 방송 줄 · 인물 발언 = 그 종목 자료가 있을 때만(방송 줄은 이 종목이 중심인 방송만, 업종 이슈 X).
    뉴스 · 중요 이슈 · 뉴스 의견 = quick-news(Finnhub, 15:10) 분류 결과가 있을 때 정식 함수 그대로 (2026-11-15 3단계).
  - 함께 보는 회사 = 사람이 고른 목록 대신 같은 업종에서 1년 등락이 가장 비슷하게 움직인 3곳(상관 계산). 그 회사들 실적 일정 카드도 정식처럼.
  - SEC 공시(Form 4 · 8-K) = 정식 collect_extra.edgar 그대로, 8일만 받아 저장(edgar_us.json).
  - 업계 카드(FRED) = 세부 업종(GICS)이 분명히 맞는 업계만 (SUB_BIZ).
  - 기업 소개 문단(연차보고서로 쓴 고정 문구) 없음 — 기본 정보 줄만.
재료 (AI 0 · Blogger 0 · 그림 0):
  - 일봉 2년 = 정식 수집과 같은 함수(collect._bars, 예비 사슬 포함) — 간단 종목 + 시장 · 업종 ETF.
  - 실적일 = Finnhub 실적 달력(지난 2년은 처음 한 번, 그 뒤 주 1회 앞 100일 + 지난 2주).
  - 애널리스트 · 이익 예상 · 공매도 · 기업 정보 = 야후, detail_cache 주기(의견 · 이익 예상 7일 · 공매도 14일 · 기업 90일) + 하루 상한(BUDGET).
  - 분기 매출 · 돈을 어디에 쓰나 = SEC companyfacts, 7일 · 하루 상한.
  - 고점 회복 통계(1999~) = 7일 · 하루 상한.  업계 = FRED(하루 한 번).  시장 일정 = 엔비디아 리포트 calendar.jsonl(읽기만).
저장값은 cache_dir(워크플로 = 비공개 상태 저장소 quick-state 브랜치)에 — 공개 브랜치 quick-data 에는 화면 조각만.
"""

import datetime
import json
import math
import os
import re
import statistics
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
RADAR = os.path.join(EXP, "stock-radar")
sys.path[:0] = [EXP, RADAR, os.path.join(EXP, "nvda-report"), os.path.join(EXP, "daily-report")]

import design_kit as dk  # noqa: E402
import detail_cache as DC  # noqa: E402
import candle_chart as CC  # noqa: E402
import universe as U  # noqa: E402
import analyze  # noqa: E402
import analyze_tabs  # noqa: E402
import industry_us  # noqa: E402
import render_pages as RP  # noqa: E402

R = RP.R
LATE_DAY = None   # 그날 다른 종목의 마지막 일봉 날짜 — collect_quick 이 넣는다. 이보다 이른 종목 = 늦음 상자
WHEN = "아침 9시 무렵"            # 간단 정보 미국 = quick-data 08:20 KST(이어 붙이기) · 끝 08:48 쯤. 정식 미국 페이지는 아침 7시 30분
WHEN_KR = "오후 5시 무렵"         # 간단 정보 한국 = 한국 종목(15:50) 뒤 이어 붙이기 · 끝 16:36 쯤. 정식 한국 페이지는 오후 4시 30분
MARKET = sorted({U.BENCH, "^VIX", "SMH", "^GSPC", *__import__("collect").SECTOR_ETFS})
BUDGET = {"detail": 90, "sec": 100, "hist": 100}   # 한 번 실행에 새로 받는 종목 수 상한 — 첫 주에 나눠 채우고, 그 뒤는 주기만큼만 (기획 6-6 `요일 나눔`)
DETAIL_FIELDS = ("analysts", "eps", "short", "company")   # 옵션(시장 예상 흔들림)은 매일이어야 뜻이 있어 뺀다 (6-6)
RETRY_EMPTY = 7   # 받았는데 비어 온 칸은 7일 뒤 다시 (빈 값은 detail_cache 에 남지 않아 매번 다시 부르게 된다)
PEERS_N, PEERS_MIN_CORR = 3, 0.4

# 세부 업종(GICS) → 업계 카드 묶음(industry_us.BIZ). 분명히 그 업계 통계로 읽히는 것만 — 나머지는 업종 자금 흐름 카드만 (2026-11-14 Claude)
SUB_BIZ = {
    "Semiconductors": "semi", "Semiconductor Materials & Equipment": "semi",
    "Application Software": "software", "Systems Software": "software",
    "Internet Services & Infrastructure": "cloud",
    "Interactive Media & Services": "ad", "Advertising": "ad",
    "Consumer Electronics": "electronics", "Computer & Electronics Retail": "electronics",
    "Consumer Staples Merchandise Retail": "mart", "Broadline Retail": "online",
    "Household Products": "staples", "Personal Care Products": "staples", "Soft Drinks & Non-alcoholic Beverages": "staples",
    "Packaged Foods & Meats": "staples", "Food Retail": "staples",
    "Home Improvement Retail": "home", "Restaurants": "food",
    "Automobile Manufacturers": "auto", "Automotive Parts & Equipment": "auto",
    "Diversified Banks": "bank", "Regional Banks": "bank",
    "Oil & Gas Exploration & Production": "oil", "Oil & Gas Equipment & Services": "oil", "Oil & Gas Refining & Marketing": "oil",
    "Integrated Oil & Gas": "oil",
    "Electric Utilities": "power", "Multi-Utilities": "power", "Independent Power Producers & Energy Traders": "power",
    "Pharmaceuticals": "pharma",
    "Construction & Engineering": "machine", "Construction Machinery & Heavy Transportation Equipment": "machine",
    "Heavy Electrical Equipment": "machine", "Electrical Components & Equipment": "machine",
    "Commodity Chemicals": "chem", "Specialty Chemicals": "chem", "Industrial Gases": "chem", "Fertilizers & Agricultural Chemicals": "chem",
}


# 종목별 업계 카드 배정표 — build_us_industry_fix.py 가 503종목을 점검해 만든 ref/us_industry_fix.json. 한국 kr_industry_fix.json 과 같은 꼴
try:
    US_FIX = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ref", "us_industry_fix.json"), encoding="utf-8"))
except (OSError, ValueError):
    US_FIX = {"card": {}, "card_off": {}}


def sector_key(e):
    """간단 종목 업종(분류 세 층의 업종) → 정식 명단의 업종 칸(universe.SECTOR_ETF 키). 반도체만 따로(SMH)."""
    if e.get("sub_en") in ("Semiconductors", "Semiconductor Materials & Equipment"):
        return "반도체"
    return e.get("sector") if e.get("sector") in U.SECTOR_ETF else "기술"


# ---------------------------------------------------------------- 재료

def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path, v):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(v, f, ensure_ascii=False, separators=(",", ":"))


def bars(syms):
    """정식 미국 수집과 같은 함수 — 2년 일봉 {day, open, high, low, close, adj, volume} + 예비 사슬. 100개씩 나눠 부른다."""
    import collect
    out = {}
    allsyms = list(dict.fromkeys(list(syms) + MARKET))
    for i in range(0, len(allsyms), 100):
        try:
            out.update(collect._bars(allsyms[i:i + 100]))
        except Exception as e:  # noqa: BLE001
            print(f"[quick-us] 일봉 묶음 {i} 실패: {str(e)[:120]}")
        time.sleep(2)
    return out


HOUR = {"bmo": "bmo", "amc": "amc"}


def earnings(cache_dir, syms, key):
    """Finnhub 실적 달력 → {sym: [{day, when}]}. 지난 2년은 처음 한 번(주 단위 약 105번), 그 뒤 주 1회 = 지난 2주 + 앞 100일(약 17번)."""
    import requests
    path = os.path.join(cache_dir, "earn_us.json")
    c = _load(path, {"rows": {}, "past_from": None, "fetched": None})
    today = datetime.date.today()
    if c.get("fetched") and (today - datetime.date.fromisoformat(c["fetched"])).days < 7:
        return c["rows"]
    if not key:
        print("[quick-us] FINNHUB_API_KEY 없음 — 실적일은 지난 값")
        return c["rows"]
    start = today - datetime.timedelta(days=14) if c.get("past_from") else today - datetime.timedelta(days=730)
    rows = {k: [x for x in v if x["day"] < str(start)] for k, v in (c.get("rows") or {}).items()}
    d0, calls, ok = start, 0, 0
    while d0 < today + datetime.timedelta(days=100):
        d1 = d0 + datetime.timedelta(days=6)
        try:
            j = requests.get("https://finnhub.io/api/v1/calendar/earnings", timeout=60,
                             params={"from": str(d0), "to": str(d1), "token": key}).json()
            ok += 1
            for e in j.get("earningsCalendar", []) or []:
                sym = (e.get("symbol") or "").replace(".", "-")
                if sym in syms and e.get("date"):
                    rows.setdefault(sym, []).append({"day": e["date"], "when": HOUR.get(e.get("hour") or "")})
        except Exception as e:  # noqa: BLE001
            print(f"[quick-us] Finnhub {d0} 실패: {str(e)[:80]}")
        calls += 1
        d0 = d1 + datetime.timedelta(days=1)
        time.sleep(1.1)   # 무료 분당 60번
    if ok < calls * 0.8:
        print(f"[quick-us] Finnhub {ok}/{calls} 성공 — 지난 값 유지")
        return c["rows"]
    rows = {k: sorted({x["day"]: x for x in v}.values(), key=lambda x: x["day"]) for k, v in rows.items()}
    _save(path, {"rows": rows, "past_from": c.get("past_from") or str(start), "fetched": str(today), "calls": calls})
    print(f"[quick-us] 실적일 {len(rows)}종목 · Finnhub {calls}번")
    return rows


def details(cache_dir, syms, bar_day, earn):
    """애널리스트 · 이익 예상 · 공매도 · 기업 정보 — 정식과 같은 함수(collect_extra._one) · 같은 주기(detail_cache), 하루 BUDGET 종목까지."""
    import collect_extra
    cache = DC.DetailCache(cache_dir)
    tried = cache.blobs.get("tried", {}).get("v") or {}
    today = cache.today.isoformat()
    plan = []
    for s in syms:
        past = [e["day"] for e in earn.get(s) or [] if e["day"] <= bar_day]
        nxt = next((e["day"] for e in earn.get(s) or [] if e["day"] >= bar_day), None)
        due = []
        for f in DETAIL_FIELDS:
            t = (tried.get(s) or {}).get(f)
            if cache.get(s, f) is None and t and (cache.today - datetime.date.fromisoformat(t)).days < RETRY_EMPTY:
                continue   # 지난번에 비어 왔다 — 며칠 뒤 다시
            if cache.due(s, f, bar=bar_day, earn_days=past, next_earn=nxt):
                due.append(f)
        if due:
            have = sum(1 for f in DETAIL_FIELDS if cache.get(s, f) is not None)
            plan.append((have, zlib.crc32(s.encode()), s, tuple(due)))
    plan.sort()   # 아직 아무것도 없는 종목부터
    jobs = plan[:BUDGET["detail"]]
    import expect as EX
    import yfinance as yf

    def one(j):
        """정식 collect_extra._one 과 같은 함수들 — 기업 정보에는 주식 수(시총 = 주식 수 × 종가, 시총 호출 0)를 덧붙인다."""
        s, due = j[2], j[3]
        t = yf.Ticker(s)
        fn = {"analysts": lambda: collect_extra._analysts(t), "eps": lambda: EX._eps(t), "short": lambda: EX._short(t),
              "company": lambda: dict(collect_extra._company(t), shares=(t.info or {}).get("sharesOutstanding"))}
        g = {}
        for f in due:
            try:
                g[f] = fn[f]()
            except Exception as e:  # noqa: BLE001
                print(f"[quick-us] {s} {f} 실패: {str(e)[:80]}")
                g[f] = None
        return s, g
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(3) as ex:   # 정식과 같은 3스레드 (운영지침 D6-1)
        got = dict(ex.map(one, jobs))
    for _, _, s, due in jobs:
        g = got.get(s) or {}
        for f in due:
            if not cache.put(s, f, g.get(f)):
                tried.setdefault(s, {})[f] = today
    cache.blobs["tried"] = {"v": tried, "day": today}
    cache.save("간단 정보 미국")
    print(f"[quick-us] 상세 값 새로 받은 종목 {len(jobs)} · 남은 대기 {len(plan) - len(jobs)}")
    return {s: {f: cache.get(s, f) for f in DETAIL_FIELDS} for s in syms}


def sec_tables(cache_dir, syms):
    """분기 매출(EX.revenue_rows) · 돈 표(collect_capex.rows_from_facts) — 정식과 같은 SEC companyfacts 한 번으로 둘 다. 7일 · 하루 BUDGET."""
    import expect as EX
    import collect_capex as CX
    path = os.path.join(cache_dir, "sec_us.json")
    c = _load(path, {"rev": {}, "cash": {}, "day": {}})
    today = datetime.date.today()
    old = [s for s in syms if not c["day"].get(s) or (today - datetime.date.fromisoformat(c["day"][s])).days >= 7]
    old.sort(key=lambda s: (s in c["rev"], c["day"].get(s) or ""))
    todo = old[:BUDGET["sec"]]
    if todo:
        try:
            tickers = EX._sec("https://www.sec.gov/files/company_tickers.json")
            cik = {v["ticker"]: str(v["cik_str"]).zfill(10) for v in tickers.values()}
        except Exception as e:  # noqa: BLE001
            print(f"[quick-us] SEC 회사 번호 실패 — 지난 값: {str(e)[:80]}")
            todo, cik = [], {}
        for s in todo:
            k = cik.get(s) or cik.get(s.replace("-", ".")) or cik.get(s.replace("-", ""))
            c["day"][s] = str(today)
            if not k:
                continue
            try:
                facts = EX.company_facts(k)
            except Exception as e:  # noqa: BLE001
                print(f"[quick-us] {s} companyfacts 실패: {str(e)[:80]}")
                continue
            try:
                rows = EX.revenue_rows(facts)
                if rows:
                    c["rev"][s] = rows
            except Exception as e:  # noqa: BLE001
                print(f"[quick-us] {s} 매출 실패: {str(e)[:80]}")
            try:
                rows = CX.rows_from_facts(facts, k)
                if rows:
                    c["cash"][s] = rows
            except Exception as e:  # noqa: BLE001
                print(f"[quick-us] {s} 돈 표 실패: {str(e)[:80]}")
            time.sleep(0.15)   # SEC 초당 10번 안
        _save(path, c)
    print(f"[quick-us] SEC 새로 {len(todo)} · 매출 {len(c['rev'])} · 돈 표 {len(c['cash'])}")
    return c


def history(cache_dir, syms):
    """고점 하락 후 회복 통계(1999~) — 정식 collect.history 와 같은 계산(history_stats), 종목마다 7일 · 하루 BUDGET."""
    import yfinance as yf
    import history_stats as HS
    path = os.path.join(cache_dir, "hist_us.json")
    c = _load(path, {"stats": {}, "day": {}})
    today = datetime.date.today()
    if c.get("method") != HS.DD_METHOD:   # 사이클 정의가 바뀌면 모든 종목을 다시 받을 차례로 (하루 BUDGET 안에서)
        c["day"], c["method"] = {}, HS.DD_METHOD
    old = [s for s in syms if not c["day"].get(s) or (today - datetime.date.fromisoformat(c["day"][s])).days >= 7]
    old.sort(key=lambda s: (s in c["stats"], c["day"].get(s) or ""))
    todo = old[:BUDGET["hist"]]
    if todo:
        try:
            df = yf.download(todo + [U.BENCH], start="1999-01-01", interval="1d", auto_adjust=False, group_by="ticker", progress=False, threads=True)
            spy = df[U.BENCH]["Close"].dropna()
            for s in todo:
                c["day"][s] = str(today)
                try:
                    cl = df[s]["Close"].dropna()
                except KeyError:
                    continue
                cl = cl[cl > 0]
                if len(cl) < 500:
                    continue
                c["stats"][s] = {"from": cl.index[0].strftime("%Y-%m-%d"), "to": cl.index[-1].strftime("%Y-%m-%d"), "dd": HS.dd_summary(HS.drawdown_cycles(cl)),
                                 "spy_dd": HS.dd_summary(HS.drawdown_cycles(spy[spy.index >= cl.index[0]]))}
            if not c["stats"].get(U.BENCH) or (today - datetime.date.fromisoformat(c["day"].get(U.BENCH, "2000-01-01"))).days >= 7:
                c["stats"][U.BENCH] = {"from": spy.index[0].strftime("%Y-%m-%d"), "to": spy.index[-1].strftime("%Y-%m-%d"),
                                       "dd": HS.dd_summary(HS.drawdown_cycles(spy)), "spy_dd": HS.dd_summary(HS.drawdown_cycles(spy))}
                c["day"][U.BENCH] = str(today)
            _save(path, c)
        except Exception as e:  # noqa: BLE001
            print(f"[quick-us] 고점 회복 통계 실패 — 지난 값: {str(e)[:100]}")
    print(f"[quick-us] 고점 회복 통계 새로 {len(todo)} · 전체 {len(c['stats'])}")
    return {"stats": c["stats"]}


EDGAR_DAYS = 8   # 화면은 7일(_news_for) — 정식처럼 30일을 받으면 첫 실행 Form 4 가 네 배


def edgar(cache_dir, syms):
    """SEC 공시(임원 거래 Form 4 · 수시 공시 8-K) — 정식 collect_extra.edgar 그대로, 받은 공시는 저장해 다시 안 받는다. 실패하면 지난 값."""
    import collect_extra
    import expect as EX
    path = os.path.join(cache_dir, "edgar_us.json")
    have = _load(path, {})
    t0 = time.time()
    try:
        tickers = EX._sec("https://www.sec.gov/files/company_tickers.json")
        cik = {v["ticker"].replace(".", "-"): str(v["cik_str"]).zfill(10) for v in tickers.values()}
        got = collect_extra.edgar(have, cik, syms=sorted(syms), days=EDGAR_DAYS)
        _save(path, got)
    except Exception as e:  # noqa: BLE001
        print(f"[quick-us] SEC 공시 실패 — 지난 값: {str(e)[:100]}")
        got = have
    print(f"[quick-us] SEC 공시 {len(got)}건 · {sum(1 for v in got.values() if v['form'] == '4')}건 Form 4 · {time.time() - t0:.0f}초")
    return got


def fred(cache_dir):
    industry_us.CACHE = os.path.join(cache_dir, "fred_us.json")
    try:
        return industry_us.fetch()
    except Exception as e:  # noqa: BLE001
        print(f"[quick-us] FRED 실패: {str(e)[:100]}")
        return _load(industry_us.CACHE, {})


def macro_rows_from(jsonl):
    """엔비디아 리포트 상태(calendar.jsonl)의 시장 일정 — analyze_tabs._macro_rows 를 이것으로 바꿔 쓴다(DB 없이)."""
    rows = []
    try:
        for line in open(jsonl, encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("kind") in analyze_tabs.CC.MACRO_KINDS and r.get("day"):
                rows.append({"day": r["day"], "kind": r["kind"], "label": r.get("label") or ""})
    except OSError:
        return None
    rows = sorted({(r["day"], r["kind"]): r for r in rows}.values(), key=lambda r: r["day"])
    return lambda d0, d1: [r for r in rows if d0 <= r["day"] <= d1]


# ---------------------------------------------------------------- 함께 보는 회사 = 상관 계산

def corr_peers(bars_all, groups, n=PEERS_N):
    """같은 업종 안에서 최근 1년 하루 등락이 가장 비슷하게 움직인 n곳 (상관 ≥ PEERS_MIN_CORR). {sym: {peer: "동종"}}."""
    def rets(sym):
        b = bars_all.get(sym) or []
        return {b[i]["day"]: b[i]["adj"] / b[i - 1]["adj"] - 1 for i in range(max(1, len(b) - 250), len(b)) if b[i - 1].get("adj")}
    R_ = {s: rets(s) for g in groups.values() for s in g}
    out = {}
    for g in groups.values():
        for s in g:
            a = R_.get(s) or {}
            cands = []
            for p in g:
                if p == s:
                    continue
                b = R_.get(p) or {}
                days = [d for d in a if d in b]
                if len(days) < 120:
                    continue
                x, y = [a[d] for d in days], [b[d] for d in days]
                mx, my = sum(x) / len(x), sum(y) / len(y)
                sx = math.sqrt(sum((v - mx) ** 2 for v in x))
                sy = math.sqrt(sum((v - my) ** 2 for v in y))
                if sx and sy:
                    r = sum((u - mx) * (v - my) for u, v in zip(x, y)) / (sx * sy)
                    if r >= PEERS_MIN_CORR:
                        cands.append((r, p))
            out[s] = {p: "동종" for _, p in sorted(cands, reverse=True)[:n]}
    return out


# ---------------------------------------------------------------- 화면

def _no_picks(*a, **k):
    return ""


def sec_expect(s):
    """`실적` 탭 카드 — RP.sec_expect 와 같은 카드에서 받지 못한 것은 빼고(빈 답 금지), 시장 예상 흔들림(옵션)은 늘 뺀다."""
    ex = s.get("expect") or {}
    spec = [("회사는 돈을 더 벌고 있나?", "revenue", RP.card_revenue), (R.EPS_TITLE, "eps", R.card_eps),
            ("하락에 거는 돈은?", "short", R.card_short), ("돈을 어디에 쓰나?", "capex", RP.card_capex)]
    out = ""
    for i, (title, key, fn) in enumerate(spec):
        c = ex.get(key)
        if not c:
            continue
        lines, tip = RP._rename(fn(c), s["name"])
        theme, col = R.EXPECT_THEME.get(c["state"], ("neutral", R.MUTED))
        out += R._state_card(title, c["state"], theme, col, list(lines), "", tip=tip, fold=True, opened=not out)
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>' if out else ""


def earnings_tab(s):
    cal = RP.sec_calendar(s, ("earnings", "peers", "macro"), open_first=False)   # 함께 보는 회사 일정 = 상관 3곳의 실적일(Finnhub 달력, 이미 받음)
    ex = sec_expect(s)
    if not ex and not cal:
        return ""
    return ex + (R.group_title("주요 일정") + cal if cal else "")


def opinions_tab(s):
    cells = s.get("analysts") or []
    ps = RP._picks(s) if RP.PICKS else []   # 방송에서 이 종목을 짚은 의견
    if not cells and not s.get("broker") and not ps and not (RP.NEWS and RP._news_opinions(s)):
        return ""
    keep = R.picks_card
    if not ps and not MEDIA_OK:
        R.picks_card = _no_picks   # 방송 자료를 못 읽었으면 카드 없이 — 읽었는데 없으면 정식처럼 `없음` 카드
    try:
        return R.opinions_cards(s["name"], cells, s.get("close"), ps if (ps or MEDIA_OK) else None, lambda v: f"${v:,.2f}", lambda: RP.together_items(s),
                                broker=s.get("broker") or [], news_ops=RP._news_opinions(s) if RP.NEWS else None, closes=[b["close"] for b in (RP.BARS.get(s["sym"]) or [])[-R.PICK_SHOW_DAYS:]])
    finally:
        R.picks_card = keep


def body(s, bars_s, related_links, extra_today=""):
    """정식 detail_body 와 같은 순서 — 머리(안내 · 요약) → 봉차트 → 오늘 탭 → 매수의견 · 실적 · 업계상황 · 기업 → 함께 보는 페이지.
    뉴스(RP.NEWS = quick-news 분류 결과)가 있으면 오늘 탭 끝 = 정식과 같은 `중요 이슈` · `뉴스`(sec_today_tab, 급락 카드 포함) — `이름이 나온 기사` 카드는 뺀다 (2026-11-15 3단계)."""
    news_mode = bool(RP.NEWS)
    today = (R.day_path_chart(s["tech"].get("path"), s["tech"].get("bench_path"), s["name"], "S&P 500")
             + RP.price_card(s, s["day"]) + RP.sec_regime(s) + RP.sec_tech(s) + RP.sec_pairs(s) + RP.sec_states(s) + ("" if news_mode else extra_today))
    op, ea = opinions_tab(s), earnings_tab(s)
    ind = RP.sec_industry_tab(s)
    return RP._link_peers(s, RP.wrap(f'<div data-quick-title="{dk.esc(U.page_title(s["sym"]).replace(" · 실적 일정", ""))}">'   # wrap = 정식과 같은 틀 · 제목 정렬 · 합니다체
            + dk.report_stamp(dk.kst_close_day(s["day"], "US"), WHEN, close="새벽 마감", late=bool(LATE_DAY) and str(s["day"])[:10] < LATE_DAY)
            + RP.lead(s) + CC.card(s["name"], bars_s, 2, title="") + CC.chart_talk.block(bars_s, s["name"], "us") + '<div style="height:20px;"></div>'
            + R._section("오늘", today, line=False, tab="오늘")
            + (RP.sec_today_tab(s, RP.NEWS) if news_mode else RP.sec_crash(s))   # 급락일에 버텼을 때만 (정식과 같은 자리 · 같은 카드) — 뉴스 있으면 sec_today_tab 이 급락 카드까지
            + (R._section("매수의견", op, tab="매수의견") if op else "")
            + (R._section("실적", ea, tab="실적") if ea else "")
            + R._section("업계상황", ind, tab="업계상황")
            + R._section("기업", RP.sec_company(s), tab="기업")
            + R.related_buttons(related_links) + "</div>"))   # 비교 종목 이름 → 그 종목 페이지 (정식 detail_body 와 같게)


def full_group(radar_dir):
    """비교 묶음 `시총 상위 20개` 재료 — 미국 정식 실행 상태(nvda-state radar/detail_cache.json: 시총 · 이익 예상 · 매출 묶음)를 읽기만. 없으면 빈 묶음."""
    if not radar_dir or not os.path.exists(os.path.join(radar_dir, "detail_cache.json")):
        return set(), {}, {}
    cache = DC.DetailCache(radar_dir)
    caps = {c[0]: cache.get(c[0], "caps") for c in U.CANDIDATES if c[0] not in U.TOP_EXCLUDE and cache.get(c[0], "caps")}
    group = set(sorted(caps, key=lambda s: -caps[s])[:U.PEER_GROUP_N])
    rev = ((cache.blob("revenue", 10 ** 6) or {}).get("series")) or {}
    return group, {s: rev[s] for s in group if s in rev}, {s: {"eps": cache.get(s, "eps")} for s in group if cache.get(s, "eps")}


MEDIA_OK = False   # 방송 자료를 실제로 읽었나 — 읽었을 때만 `방송 의견 없음` 카드를 둔다


def media_inputs():
    """방송 이슈(24시간) · 방송 의견(최근 5거래일) — 정식 write_all 과 같은 읽기(Firestore, 읽기 전용 키 YTB_FIRESTORE_KEY). 키가 없거나 실패하면 ([], []) = 그 칸 없이."""
    import os as _os
    if not (_os.environ.get("YTB_FIRESTORE_KEY") or _os.environ.get("MEDIA_FEED_JSON") or _os.environ.get("QUICK_MEDIA_LOCAL")):   # QUICK_MEDIA_LOCAL = 목업(PC 의 gcloud 기본 인증으로 읽기)
        print("[quick-us] 방송 자료 키 없음 — 방송 줄 · 방송 의견 없이")
        return [], []
    MF = RP.media_feed
    try:
        vids = MF.load(RP.NOW.astimezone(MF.KST).strftime("%Y-%m-%d"), days=R.PICK_DAYS - 1)
        iss, ps = MF.issues(MF.rows(vids), RP._since()), MF.picks(vids, RP.PICK_SINCE)
        print(f"[quick-us] 방송 영상 {len(vids)} · 이슈 {len(iss)} · 종목 의견 {len(ps)}")
        global MEDIA_OK
        MEDIA_OK = True
        return iss, ps
    except Exception as e:  # noqa: BLE001
        print(f"[quick-us] 방송 자료 실패 — 없이: {str(e)[:100]}")
        return [], []


def load_news(qnews_dir):
    """quick-news.yml 이 비공개 quick-news-state 에 남긴 분류 결과(news.json) · 팝업 요약(summaries.json → {item_id: [줄]}). 없으면 ({}, {})."""
    if not qnews_dir:
        return {}, {}
    news = _load(os.path.join(qnews_dir, "news.json"), {})
    summ = {k: v.get("lines") or [] for k, v in _load(os.path.join(qnews_dir, "summaries.json"), {}).items()}
    return news, summ


def build(ref_us, bars_all, earn, det, sec, hist, fred_data, macro=None, only=None, related=None, radar_dir=None, extra_today=None, news=None, summaries=None, filings=None):
    """간단 종목(정식 아님) 화면 조각 {sym: html}. ref_us = quick_ref.json 의 us. related(sym, e) → [(글, 주소)]. extra_today(sym) → 오늘 탭 끝 카드(이름이 나온 기사, 뉴스 없을 때만).
    news · summaries = load_news — 있으면 정식과 같은 중요 이슈 · 뉴스 · 뉴스 의견 (방송 · 인물 발언 재료는 없다)."""
    quick = [s for s, e in ref_us.items() if not e.get("full") and len(bars_all.get(s) or []) >= 30 and (only is None or s in only)]
    # 이 실행 안에서만 정식 명단에 얹는다 (ETF 페이지와 같은 방식)
    groups = {}
    for s, e in ref_us.items():
        if s in U.BY_SYM or len(bars_all.get(s) or []) < 30:
            if s in U.BY_SYM:
                groups.setdefault(U.BY_SYM[s][3] if U.BY_SYM[s][3] in U.SECTOR_ETF else "기술", []).append(s)
            continue
        k = sector_key(e)
        U.CANDIDATES.append((s, e["ko"], s.lower(), k))
        U.BY_SYM[s] = U.CANDIDATES[-1]
        groups.setdefault(k, []).append(s)
        g = (US_FIX["card"].get(s) or {}).get("group") if s in US_FIX["card"] or s in US_FIX["card_off"] else SUB_BIZ.get(e.get("sub_en"))   # 배정표가 먼저, 표에 없는 새 종목만 세부 업종 기본값
        if g:
            industry_us.SYM_BIZ[s] = tuple(g) if isinstance(g, list) else g
    peers = corr_peers(bars_all, {k: [s for s in v if s in quick or s in U.BY_SYM] for k, v in groups.items()})
    for s in quick:
        U.PEERS[s] = peers.get(s) or {}
    if macro:
        analyze_tabs._macro_rows = macro
    group, grev, geps = full_group(radar_dir)
    analyze_tabs.peer_group = lambda snap: group   # 비교 묶음 = 정식과 같은 `시총 상위 20개`(정식 종목) — 간단 종목 시총은 쓰지 않는다
    snap = {"bars": bars_all, "caps": {}, "earnings": {**{s: v for s, v in earn.items() if v}, **{s: earn.get(s) or [] for s in quick}}, "history": hist}   # 정식 종목 실적일도 — 함께 보는 회사가 정식 종목일 때
    extra = {"stocks": {**geps, **{s: {f: (det.get(s) or {}).get(f) for f in DETAIL_FIELDS} for s in quick}},
             "revenue": {"series": {**grev, **(sec.get("rev") or {})}}, "capex": sec.get("cash") or {}, "peer_earnings": {}, "edgar": filings or {}}
    RP.BARS = bars_all
    RP.NOW = datetime.datetime.now(datetime.timezone.utc)
    RP.NEWS, RP.SUMMARY = news or {}, summaries or {}
    RP.PICK_SINCE = R.pick_window(bars_all.get(U.BENCH) or [], RP.NY, now=RP.NOW)[1]
    t_m = time.time()
    RP.MEDIA, RP.PICKS = media_inputs()
    print(f"[quick-us] 방송 자료 읽기 {time.time() - t_m:.0f}초", flush=True)
    MF = RP.media_feed
    keep_for_page = MF.for_page
    MF.for_page = lambda rs, sym: MF.for_ticker(rs, sym, U.name(sym))   # 방송 줄 = 이 종목이 중심인 방송만 — 정식의 `업종 이슈면 업종 종목 전부` 는 간단 종목 수십 곳에 같은 줄이 깔려 뺀다
    mr, ms = analyze.market_regime(snap), analyze.market_shock(snap)
    crash = RP.CW.compute(bars_all, "us", quick)   # 급락장에서 어땠나? — 정식과 같은 계산(지수 −2% 넘은 날 버텼나), 일봉만
    out, fails = {}, 0
    t0 = time.time()
    for i, sym in enumerate(quick):
        if i and i % 50 == 0:   # 진행 표시 — 11-16 실행이 출력 없이 80분 상한에 걸렸다
            print(f"[quick-us] 화면 {i}/{len(quick)} · {time.time() - t0:.0f}초", flush=True)
        try:
            s = analyze.stock(sym, snap)
            b = s.pop("_bars")
            s["tech"] = analyze.technical(b, snap, sym)
            s["market_regime"], s["market_shock"] = mr, ms
            s["sector_flow"], s["bollinger"] = analyze.sector_flow(snap, sym), analyze.bollinger(b)
            s["overheat"], s["drawdown"] = analyze.overheat(b, s["tech"]), analyze.drawdown(b, s["year_range"], snap, sym)
            s["peer_moves"] = analyze.peer_moves(snap, sym, s["day"])
            s.update(in_top=False, rank=None, mom_12_1=None, crash=RP.CW.for_stock(crash, sym))
            analyze_tabs.build(s, snap, extra)
            s["industry_us"] = industry_us.build(sym, fred_data)
            out[sym] = body(s, b, related(sym, ref_us[sym]) if related else [], extra_today(sym) if extra_today else "")
        except Exception as e:  # noqa: BLE001 — 한 종목 실패가 나머지를 막지 않게
            fails += 1
            print(f"[quick-us] {sym} 화면 실패: {e!r}")
    n_media = sum(1 for s in out if MF.for_page(RP.MEDIA, s))
    MF.for_page = keep_for_page
    print(f"[quick-us] 화면 {len(out)}/{len(quick)} · 실패 {fails} · 방송 줄 {n_media}종목 · 방송 의견 {len({p['ticker'] for p in RP.PICKS if p['market'] == 'US'} & set(out))}종목"
          f" · 인물 발언 {sum(1 for s in out if RP.people_section.for_stock(s))}종목")
    return out
