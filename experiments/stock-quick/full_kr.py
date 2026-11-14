"""간단 정보(한국) = 한국 정식 종목 렌더러 그대로 (2026-11-14 사용자 "TIGER 2차전지 테마처럼 · 정식 종목과 거의 차이 없게").

full_us.py 와 같은 원칙 — 정식 계산(analyze_kr) · 정식 카드(render_kr)를 그대로 부르고, 막히는 줄(방송 뉴스 · 방송 의견 · 미국과 연결 짝)만 뺀다.
11-12 목업(mock_quick.page_kr_full)과 같은 화면을 853종목 매일 실행으로.
  - 탭 = 오늘 · 매수의견(애널리스트 — 값이 있을 때만) · 실적(분기 매출 · 이익 예상 · 돈을 어디에 쓰나 + 시장 일정) · 업계상황 · 기업.
  - 실적 발표일 카드는 없다 — 한국은 예정일이 미리 나오는 회사가 드물다(실측 3/25, 기획 6-3-2 ⑥).
  - 함께 움직이는 종목 = 같은 업종에서 1년 등락이 가장 비슷하게 움직인 3곳(상관 계산, full_us.corr_peers). 정식의 `미국과 연결`(검증한 짝)은 빌려 오지 않는다.
  - 업계 카드 = 업종 원자료(로고 메타데이터 industry_en)가 분명한 업종만 정식 대표 종목의 업계 자료로 잇는다(IND_REP). 원자료가 틀린 종목은 KR_FIX.
재료 (AI 0 · Blogger 0 · 그림 0):
  - 일봉 2년(collect_kr._bars) — 간단 종목 + 코스피 · 코스닥 · 업종 ETF.
  - 자금 흐름 · 업계 통계(flows.json) · 정식 종목 시총 · 이익 예상 · DART 매출(비교 묶음 `시총 상위 20개`) = 한국 정식 실행 상태(kr-state)를 읽기만.
  - 분기 매출 · 손익 · 현금흐름(DART) · 기업개황(DART) · 애널리스트 · 이익 예상(야후) = 간단 종목 몫은 cache_dir 에 따로, 하루 BUDGET 종목까지.
  - 고점 회복 통계(1999~, 코스피 대비) = 7일 · 하루 BUDGET.
"""

import datetime
import json
import os
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
KRD = os.path.join(EXP, "kr-stocks")
sys.path[:0] = [EXP, KRD, os.path.join(EXP, "nvda-report"), os.path.join(EXP, "daily-report"), HERE]

import design_kit as dk  # noqa: E402
import candle_chart as CC  # noqa: E402
import detail_cache as DC  # noqa: E402
import universe_kr as K  # noqa: E402
import analyze_kr  # noqa: E402
import render_kr  # noqa: E402
import collect_kr_dart as D  # noqa: E402
import collect_kr_fin as FIN  # noqa: E402
import full_us  # noqa: E402

R = render_kr.R
WHEN = full_us.WHEN
BUDGET = {"detail": 60, "dart": 40, "company": 60, "hist": 100}
DETAIL_FIELDS = ("analysts", "eps")
MARKET = sorted({K.BENCH, K.KOSDAQ, *K.SECTOR_ETF_LIST})

# 업종 원자료(industry_en) → 업계 자료를 빌려 올 한국 정식 종목. 그 업종 종목 대부분에 맞는 것만 (2026-11-14 Claude) — 나머지는 업계 카드 없이
IND_REP = {
    "Semiconductors": "000660.KS",
    "Pharmaceuticals: Major": "068270.KS", "Biotechnology": "196170.KQ",
    "Major Banks": "105560.KS", "Regional Banks": "105560.KS",
    "Multi-Line Insurance": "000810.KS", "Property/Casualty Insurance": "000810.KS", "Life/Health Insurance": "032830.KS",
    "Auto Parts: OEM": "005380.KS", "Automotive Aftermarket": "005380.KS",
    "Homebuilding": "028260.KS", "Engineering & Construction": "028260.KS",
    "Steel": "005490.KS",
    "Major Telecommunications": "017670.KS",
    "Aerospace & Defense": "064350.KS",
    "Packaged Software": "035420.KS", "Internet Software/Services": "035420.KS",
}
# 종목 하나씩 — 원자료 업종이 틀렸거나 한 업종에 다른 사업이 섞인 것 (코드: 대표 종목, None = 업계 카드 없음)
KR_FIX = {
    "009830": None,          # 한화솔루션 — 원자료 `반도체`, 실제는 화학 · 태양광
    "009150": None,          # 삼성전기 — 원자료 `반도체`, 실제는 전자 부품(적층세라믹콘덴서 · 기판)
    "010140": "009540.KS",   # 삼성중공업 — 원자료 `건설 기계`, 실제는 조선
    "082740": "009540.KS",   # 한화엔진 — 선박 엔진
    "071970": "009540.KS",   # HD현대마린엔진 — 선박 엔진
    "443060": "009540.KS",   # HD현대마린솔루션 — 원자료 `도매 유통`, 실제는 선박 서비스
}


def code_of(sym):
    return sym.split(".")[0]


def rep_of(sym, e):
    c = code_of(sym)
    if c in KR_FIX:
        return KR_FIX[c]
    return IND_REP.get(e.get("industry_en"))


def alias(rep, sym):
    """대표 종목의 업계 칸을 이 종목에 잇는다 — 업종 ETF · 업계 통계 · 사업 묶음만. 미국과 연결 짝(PAIRS)은 빌리지 않는다(그 종목에서 검증한 것)."""
    if rep in K.SECTOR_ETF:
        K.SECTOR_ETF[sym] = K.SECTOR_ETF[rep]
    for n in ("BSI_INDUSTRY", "FIN_INDUSTRY", "LOAN_INDUSTRY"):
        for _code, (_name, syms) in getattr(K, n).items():
            if rep in syms and sym not in syms:
                syms.append(sym)
    if code_of(rep) in K.BIZ_OF:
        K.BIZ_OF[code_of(sym)] = K.BIZ_OF[code_of(rep)]


# ---------------------------------------------------------------- 재료

_load, _save = full_us._load, full_us._save


def bars(syms):
    import collect_kr
    out = {}
    allsyms = list(dict.fromkeys(list(syms) + MARKET))
    for i in range(0, len(allsyms), 100):
        try:
            out.update(collect_kr._bars(allsyms[i:i + 100]))
        except Exception as e:  # noqa: BLE001
            print(f"[quick-kr] 일봉 묶음 {i} 실패: {str(e)[:120]}")
        time.sleep(2)
    return out


def details(cache_dir, syms):
    """애널리스트 · 이익 예상 — 한국 정식(collect_kr_extra)과 같은 함수 · 같은 주기, 하루 BUDGET. 비어 온 칸은 7일 뒤 다시."""
    import collect_kr_extra as KX
    import yfinance as yf
    cache = DC.DetailCache(os.path.join(cache_dir, "kr"))
    tried = cache.blobs.get("tried", {}).get("v") or {}
    today = cache.today.isoformat()
    plan = []
    for s in syms:
        due = []
        for f in DETAIL_FIELDS:
            t = (tried.get(s) or {}).get(f)
            if cache.get(s, f) is None and t and (cache.today - datetime.date.fromisoformat(t)).days < full_us.RETRY_EMPTY:
                continue
            if cache.due(s, f):
                due.append(f)
        if due:
            plan.append((sum(1 for f in DETAIL_FIELDS if cache.get(s, f) is not None), zlib.crc32(s.encode()), s, tuple(due)))
    plan.sort()
    jobs = plan[:BUDGET["detail"]]
    for _, _, s, due in jobs:
        t = yf.Ticker(s)
        fn = {"analysts": lambda: KX._analysts(t), "eps": lambda: KX.EX._eps(t)}
        for f in due:
            try:
                v = fn[f]()
            except Exception as e:  # noqa: BLE001
                print(f"[quick-kr] {s} {f} 실패: {str(e)[:80]}")
                v = None
            if not cache.put(s, f, v):
                tried.setdefault(s, {})[f] = today
        time.sleep(0.5)   # 정식 한국 수집과 같은 간격
    cache.blobs["tried"] = {"v": tried, "day": today}
    cache.save("간단 정보 한국")
    print(f"[quick-kr] 상세 값 새로 받은 종목 {len(jobs)} · 남은 대기 {len(plan) - len(jobs)}")
    return {s: {f: cache.get(s, f) for f in DETAIL_FIELDS} for s in syms}


def rev_rows(cache, codes, syms):
    """DART 주요계정 캐시 → {sym: [{end, rev, cq, yoy, src}]} — collect_kr_dart.run 의 뒷부분과 같은 셈(받기 없이)."""
    today = datetime.date.today()
    out = {}
    for sym in syms:
        mine = cache.get(codes.get(code_of(sym)) or "", {})
        rows = []
        for year in range(today.year - D.YEARS + 1, today.year + 1):
            q = {rc: mine.get(f"{year}-{rc}") or {} for rc, _ in D.REPORTS}
            for i, (rc, mmdd) in enumerate(D.REPORTS):
                rev = q[rc].get("rev")
                if rc == "11011":
                    q3 = q["11014"].get("add")
                    rev = rev - q3 if rev is not None and q3 is not None else None
                if rev is not None:
                    rows.append({"end": f"{year}-{mmdd}", "rev": rev, "cq": f"{year}Q{i + 1}", "src": "dart"})
        by = {r["cq"]: r["rev"] for r in rows}
        for r in rows:
            prev = by.get(f"{int(r['cq'][:4]) - 1}{r['cq'][4:]}")
            r["yoy"] = (r["rev"] / prev - 1) * 100 if prev else None
        if rows:
            out[sym] = rows
    return out


def dart(cache_dir, syms):
    """간단 종목 DART — 회사 번호(한 달 한 번) · 분기 매출 · 손익 · 현금흐름(이미 받은 보고서는 다시 안 받음) · 기업개황(90일). 하루 BUDGET 회사."""
    key = D._key()
    keep = (D.CORP, D.CACHE, D.COMPANY, FIN.CACHE, list(K.CANDIDATES))
    D.CORP, D.CACHE = os.path.join(cache_dir, "kr", "dart_corp.json"), os.path.join(cache_dir, "kr", "dart_fin.json")
    D.COMPANY, FIN.CACHE = os.path.join(cache_dir, "kr", "dart_company.json"), os.path.join(cache_dir, "kr", "dart_fin_all.json")
    try:
        K.CANDIDATES[:] = [(s, "", "", "", []) for s in syms]
        codes = D.corp_codes(key) if key else (_load(D.CORP, {}) or {}).get("map") or {}
        prog = _load(os.path.join(cache_dir, "kr", "dart_done.json"), {})   # 회사마다 마지막으로 살핀 날 — 하루 BUDGET 을 오래된 것부터
        today = datetime.date.today()
        todo = sorted((s for s in syms if code_of(s) in codes and (not prog.get(s) or (today - datetime.date.fromisoformat(prog[s])).days >= 7)),
                      key=lambda s: prog.get(s) or "")[:BUDGET["dart"]]
        if key and todo:
            K.CANDIDATES[:] = [(s, "", "", "", []) for s in todo]
            try:
                D.run()     # 매출 — 새 보고서만
                FIN.run()   # 손익 · 현금흐름 — 새 보고서만
            except Exception as e:  # noqa: BLE001
                print(f"[quick-kr] DART 실패 — 지난 값: {str(e)[:120]}")
            for s in todo:
                prog[s] = str(today)
            _save(os.path.join(cache_dir, "kr", "dart_done.json"), prog)
        K.CANDIDATES[:] = [(s, "", "", "", []) for s in syms]
        rev = rev_rows(_load(D.CACHE, {}), codes, syms)
        _k = D._key
        D._key = lambda: ""   # 손익 표는 받기 없이 캐시로만 (FIN.run 이 키가 없으면 캐시를 읽는다)
        try:
            cash = FIN.run()
        finally:
            D._key = _k
        comp = _load(D.COMPANY, {"map": {}, "day": {}})
        comp.setdefault("day", {})
        old = sorted((s for s in syms if code_of(s) in codes and (not comp["day"].get(code_of(s)) or (today - datetime.date.fromisoformat(comp["day"][code_of(s)])).days >= 90)),
                     key=lambda s: comp["day"].get(code_of(s)) or "")[:BUDGET["company"]]
        if key and old:
            import requests
            for s in old:
                c = code_of(s)
                try:
                    r = requests.get(f"{D.API}/company.json", params={"crtfc_key": key, "corp_code": codes[c]}, timeout=30).json()
                    if r.get("status") == "000":
                        comp["map"][c] = {k: (r.get(k) or "").strip() for k in D.COMPANY_KEYS}
                    comp["day"][c] = str(today)
                except Exception as e:  # noqa: BLE001
                    print(f"[quick-kr] {c} 기업개황 실패: {str(e)[:80]}")
                time.sleep(0.2)
            _save(D.COMPANY, comp)
    finally:
        D.CORP, D.CACHE, D.COMPANY, FIN.CACHE, cands = keep
        K.CANDIDATES[:] = cands
    print(f"[quick-kr] DART 새로 살핀 회사 {len(todo)} · 매출 {len(rev)} · 손익 표 {len(cash)} · 기업개황 {len(comp['map'])}")
    return {"revenue": rev, "capex": cash, "company": comp["map"]}


def history(cache_dir, syms):
    """고점 하락 후 회복 통계 — 한국 정식 collect_kr.history 와 같은 계산(코스피 같은 기간 bench_dd), 7일 · 하루 BUDGET."""
    import yfinance as yf
    import history_stats as HS
    path = os.path.join(cache_dir, "kr", "hist.json")
    c = _load(path, {"stats": {}, "day": {}})
    today = datetime.date.today()
    todo = sorted((s for s in syms if not c["day"].get(s) or (today - datetime.date.fromisoformat(c["day"][s])).days >= 7),
                  key=lambda s: (s in c["stats"], c["day"].get(s) or ""))[:BUDGET["hist"]]
    if todo:
        try:
            df = yf.download(todo + [K.BENCH], start="1999-01-01", interval="1d", auto_adjust=False, group_by="ticker", progress=False, threads=3)
            bench = df[K.BENCH]["Close"].dropna()
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
                                 "bench_dd": HS.dd_summary(HS.drawdown_cycles(bench[bench.index >= cl.index[0]]))}
            _save(path, c)
        except Exception as e:  # noqa: BLE001
            print(f"[quick-kr] 고점 회복 통계 실패 — 지난 값: {str(e)[:100]}")
    print(f"[quick-kr] 고점 회복 통계 새로 {len(todo)} · 전체 {len(c['stats'])}")
    return {"stats": c["stats"], "bench": K.BENCH}


def full_group():
    """비교 묶음 `시총 상위 20개` 재료 — 한국 정식 실행 상태(kr-stocks/data: detail_cache 시총 · 이익 예상, dart_fin 매출)를 읽기만."""
    data = os.path.join(KRD, "data")
    cache = DC.DetailCache(data)
    full = [c[0] for c in K.CANDIDATES]
    caps = {s: cache.get(s, "caps") for s in full if cache.get(s, "caps")}
    group = set(sorted(caps, key=lambda s: -caps[s])[:K.PEER_GROUP_N])
    codes = (_load(os.path.join(data, "dart_corp.json"), {}) or {}).get("map") or {}
    rev = rev_rows(_load(os.path.join(data, "dart_fin.json"), {}), codes, list(group))
    eps = {s: {"eps": cache.get(s, "eps")} for s in group if cache.get(s, "eps")}
    return group, rev, eps


# ---------------------------------------------------------------- 화면

def pairs_card(s, peers, by):
    """`함께 움직이는 종목은?` — 같은 업종에서 1년 등락이 가장 비슷한 종목들의 오늘 등락 (미국 간단 정보와 같은 판정 · 같은 막대)."""
    moves = [(p, by[p]) for p in peers if by.get(p) is not None]
    if not moves:
        return ""
    rets = [r for _, r in moves]
    ups, downs = sum(1 for x in rets if x >= 0.5), sum(1 for x in rets if x <= -0.5)
    state = "엇갈림" if ups and downs else "같이 올랐음" if ups else "같이 내렸음" if downs else "비슷함"
    theme, col = {"엇갈림": ("uncertain", R.SOON), "같이 올랐음": ("positive", R.UP), "같이 내렸음": ("negative", R.DOWN)}.get(state, ("neutral", R.MUTED))
    day = render_kr._md(s["day"])
    lines = [(f"오늘({day}) 함께 움직여 온 종목은 " + ", ".join(f"{K.name(p)} {render_kr._sgn(r)}%" for p, r in moves)
              + f"였고, {dk.josa(s['name'], '은')} {render_kr._sgn(s['ret_1d'])}%였다.", "plain")]
    rows = [(K.name(p), "", r, "us") for p, r in moves] + [(s["name"], "", s["ret_1d"], "me")]
    vb = s["tech"].get("vs_bench")
    if vb is not None:
        rows.append(("KOSPI", "", s["ret_1d"] - vb, "bench"))
    lines.append((R.pair_bars([(f"함께 움직여 온 종목 ({day})", rows)]), "html"))
    R.add_small_note(lines, "같은 업종에서 최근 1년 하루 등락이 가장 비슷하게 움직인 종목입니다. ±0.5% 넘게 움직인 종목만 오른 곳 · 내린 곳으로 셉니다.")
    card = R._state_card("함께 움직이는 종목은?", state, theme, col, lines, "", fold=True)
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{card}</div>'


def sec_expect(s):
    """render_kr.sec_expect 와 같은 카드 — 받지 못한 것은 빼고(빈 답 금지)."""
    ex = s.get("expect") or {}
    out = ""
    spec = (("회사는 돈을 더 벌고 있나?", "revenue", render_kr.RP.card_revenue), (R.EPS_TITLE, "eps", R.card_eps),
            ("돈을 어디에 쓰나?", "capex", lambda c: render_kr.RP.card_capex(c, render_kr.KR_MONEY)))
    for title, key, fn in spec:
        c = ex.get(key)
        if not c:
            continue
        lines, tip = render_kr._rename(fn(c), s["name"])
        tip = tip.replace("SEC EDGAR", "금융감독원 전자공시(OpenDART)").replace("(억 달러)", "(억 원)")
        theme, col = R.EXPECT_THEME.get(c["state"], ("neutral", R.MUTED))
        out += R._state_card(title, c["state"], theme, col, list(lines), "", tip=tip, fold=True, opened=not out)
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>' if out else ""


def opinions_tab(s):
    if not s.get("analysts") and not s.get("broker"):
        return ""
    R.picks_card, keep = full_us._no_picks, R.picks_card
    try:
        closes = [b["close"] for b in (render_kr.BARS.get(s["sym"]) or [])[-R.PICK_SHOW_DAYS:]]
        return R.opinions_cards(s["name"], s.get("analysts") or [], s.get("close"), None, render_kr.won, lambda: render_kr.together_items(s),
                                m0=render_kr.man_won, m2=render_kr.won, closes=closes, broker=s.get("broker"))   # 증권사 목표가(텔레그램, 2026-11-14)
    finally:
        R.picks_card = keep


def body(s, a, peers, by, related_links, extra_today=""):
    today = (R.day_path_chart(s["tech"].get("path"), s["tech"].get("bench_path"), s["name"], "KOSPI") + render_kr.price_card(s) + render_kr.sec_regime(s)
             + render_kr.sec_tech(s) + pairs_card(s, peers, by) + render_kr.sec_states(s) + extra_today)
    op = opinions_tab(s)
    cal = render_kr.sec_calendar(s, ("macro",), open_first=False)
    ex = sec_expect(s)
    ea = ex + (R.group_title("주요 일정") + cal if cal else "")
    title = f"{s['name']} 주가"
    return render_kr.wrap(f'<div data-quick-title="{dk.esc(title)}"><span data-kr-code="{s["code"]}" hidden></span>'
            + dk.report_stamp(dk.kst_close_day(s["day"], "KR"), WHEN)
            + render_kr.lead(s) + CC.card(s["name"], render_kr.BARS.get(s["sym"]) or [], 0, title="") + '<div style="height:20px;"></div>'   # 봉차트 하나만 — 정식 page_block 은 목업 · 발행 두 벌 + 스크립트(조각엔 페이지 본문 스크립트 하나로)
            + R._section("오늘", today, line=False, tab="오늘")
            + (R._section("매수의견", op, tab="매수의견") if op else "")
            + (R._section("실적", ea, tab="실적") if ea else "")
            + R._section("업계상황", render_kr.sec_industry_tab(s), tab="업계상황")
            + R._section("기업", render_kr.sec_company(s), tab="기업")
            + R.related_buttons(related_links) + "</div>")


def build(ref_kr, bars_all, flows, hist_full, det, dart_data, hist_quick, only=None, related=None, extra_today=None):
    """간단 종목(정식 아님) 화면 조각 {코드: html}."""
    quick = [s for s, e in ref_kr.items() if not e.get("full") and len(bars_all.get(s) or []) >= 30 and (only is None or s in only)]
    groups = {}
    for s, e in ref_kr.items():
        if s in K.BY_SYM:
            groups.setdefault(K.sector(s), []).append(s)
            continue
        if len(bars_all.get(s) or []) < 30:
            continue
        rep = rep_of(s, e)
        K.CANDIDATES.append((s, e["ko"], f"quick-{code_of(s)}", e.get("sector") or "기타", list(K.groups(rep)) if rep else []))
        K.BY_SYM[s] = K.CANDIDATES[-1]
        if rep:
            alias(rep, s)
        groups.setdefault(e.get("sector") or "기타", []).append(s)
    peers = full_us.corr_peers(bars_all, {k: [s for s in v if bars_all.get(s)] for k, v in groups.items()})
    group, grev, geps = full_group()
    hist = {"stats": {**(hist_full or {}).get("stats", {}), **hist_quick.get("stats", {})}, "bench": K.BENCH}
    snap = {"bars": bars_all, "caps": {}, "fetched_at": datetime.datetime.now().isoformat(timespec="minutes")}
    extra = {"stocks": {**geps, **{s: {f: (det.get(s) or {}).get(f) for f in DETAIL_FIELDS} for s in quick}},
             "revenue": {"series": {**grev, **dart_data["revenue"]}}, "capex": dart_data["capex"], "company": dart_data["company"],
             "earnings": {}, "pair_earnings": {}}
    stocks = [x for x in (analyze_kr.stock(s, snap, hist, flows) for s in quick) if x]
    if not stocks:
        return {}
    day = max(x["day"] for x in stocks)
    market = analyze_kr.flows(flows, bars_all.get(K.BENCH)) or {}
    mr = analyze_kr.A.market_regime({"bars": {analyze_kr.NC.REGIME_BENCHMARK: bars_all.get(K.BENCH) or []}})
    for x in stocks:
        x.update(market_regime=mr, sector_flow=analyze_kr.sector_flow(snap, x["sym"]), fx=market.get("fx"), crash=None, rank=None, in_top=False, pairs={})
    a = {"day": day, "stocks": stocks, "market": market, "crash": {}}
    # render_kr.write_all 의 준비 부분 그대로 (파일 쓰기 · 목록 페이지 · 방송 읽기 빼고)
    render_kr.KR_PRICES.clear()
    render_kr.KR_PRICES.update({x["code"]: (x["name"], x.get("ret_1d")) for x in stocks if x.get("ret_1d") is not None})
    render_kr.attach_broker(stocks)   # 증권사 목표가 — 한국 정식 실행이 kr-state 에 남긴 broker_tg.json 을 읽기만
    macro_rows = render_kr.us_calendar()
    for x in stocks:
        x["company"] = extra["company"].get(x["code"]) or {}
        render_kr.build_expect(x, extra, group)
        x["_revenue_rows"] = extra["revenue"]["series"].get(x["sym"]) or []
        try:
            render_kr.build_calendar(x, snap, extra, macro_rows)
        except Exception as e:  # noqa: BLE001
            print(f"[quick-kr] {x['sym']} 캘린더 실패: {e}")
    render_kr.NOW = datetime.datetime.now(datetime.timezone.utc)
    render_kr.BARS = bars_all
    render_kr.PICK_SINCE = R.pick_window(bars_all.get(K.BENCH) or [], render_kr.media_feed.KST, now=render_kr.NOW)[1]
    render_kr.MEDIA, render_kr.MEDIA_WEEK, render_kr.PICKS = [], [], []
    by = {x["sym"]: x.get("ret_1d") for x in stocks}
    for s in peers:
        for p in peers[s]:
            if p not in by and len(bars_all.get(p) or []) >= 2 and bars_all[p][-1]["day"] == day and bars_all[p][-2].get("adj"):
                by[p] = (bars_all[p][-1]["adj"] / bars_all[p][-2]["adj"] - 1) * 100
    out, fails = {}, 0
    for x in stocks:
        try:
            out[x["code"]] = body(x, a, list(peers.get(x["sym"]) or {}), by, related(x["sym"], ref_kr[x["sym"]]) if related else [],
                                  extra_today(x["sym"]) if extra_today else "")
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"[quick-kr] {x['sym']} 화면 실패: {e!r}")
    print(f"[quick-kr] 화면 {len(out)}/{len(quick)} · 실패 {fails}")
    return out
