"""간단 종목 정보 목업 — 정식 종목(종목 분석 페이지)이 아닌 종목을 가격 자료만으로 보여 주는 화면 (2026-11-12 사용자 "목업 적용해", 기획 = 비공개 기획/회원-내-종목-기획.md 6-6).

    python experiments/stock-quick/mock_quick.py      # output/mock_quick_<종목>.html · output/mock_all_stocks.html

실제 적용 때는 고정 페이지 하나(stock-quick?s=코드)를 테마 JS 가 search/<시장>-lite.json 으로 그린다.
목업은 같은 화면을 파이썬으로 미리 그린다 — 카드 · 막대 · 범위 막대 · 선 그래프는 종목 페이지 · 데일리와 같은 공용 부품(design_kit · daily-report/cards).
자료 = yfinance 1년 일봉 묶음 + 실적일(회사 캘린더). AI 0.
"""

import datetime
import json
import re
import os
import sys

import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, EXP)
sys.path.insert(0, os.path.join(EXP, "daily-report"))
import design_kit as dk  # noqa: E402
import cards as C  # noqa: E402

OUT = os.path.join(HERE, "output")
LIST_DAY = ""

# 예시 — 정식 종목 목록(미국 64 · 한국 35)에 없는 종목. 업종 · 세부 업종은 분류 세 층(taxonomy) 말로
SAMPLES = [
    {"sym": "UBER", "name": "우버", "market": "US", "sector": "산업재", "sub": "운송 · 플랫폼", "peers": [("엔비디아 NVDA 주가", "#"), ("테슬라 TSLA 주가", "#")]},
    {"sym": "SBUX", "name": "스타벅스", "market": "US", "sector": "경기 소비재", "sub": "외식", "peers": [("맥도날드 MCD 주가", "#"), ("코스트코 COST 주가", "#")]},
    {"sym": "259960.KS", "name": "크래프톤", "market": "KR", "sector": "커뮤니케이션", "sub": "게임", "peers": [("NAVER 035420 주가", "#"), ("카카오 035720 주가", "#")],
     "slug": "krafton", "kr_sector": "커뮤니케이션"},
]
BENCH = {"US": ("^GSPC", "S&P 500"), "KR": ("^KS11", "코스피")}
# 전체 종목 목록 목업에 같이 싣는 종목 (정식 몇 개 + 간단 정보 몇 개)
LIST_KR = [("005930.KS", "삼성전자", "반도체", True), ("000660.KS", "SK하이닉스", "반도체", True), ("035420.KS", "NAVER", "커뮤니케이션", True),
           ("259960.KS", "크래프톤", "커뮤니케이션", False), ("352820.KS", "하이브", "커뮤니케이션", False), ("009150.KS", "삼성전기", "정보기술", False),
           ("011200.KS", "HMM", "산업재", False), ("128940.KS", "한미약품", "헬스케어", False), ("000100.KS", "유한양행", "헬스케어", False)]
LIST_US = [("NVDA", "엔비디아", "반도체", True), ("AAPL", "애플", "정보기술", True), ("UBER", "우버", "산업재", False), ("SBUX", "스타벅스", "경기 소비재", False),
           ("PLTR", "팔란티어", "정보기술", False), ("NKE", "나이키", "경기 소비재", False), ("SHOP", "쇼피파이", "정보기술", False), ("DE", "디어", "산업재", False)]


def money(v, market):
    return f"${v:,.2f}" if market == "US" else f"{v:,.0f}원"


def pct(v):
    return f"{v:+.1f}%".replace("-", "−")


def color(v):
    return C.UP if v > 0 else C.DOWN if v < 0 else "#111"


def ret(c, n):
    return (c[-1] / c[-1 - n] - 1) * 100 if len(c) > n else None


def ytd(days, c):
    y = days[-1][:4]
    i = next((k for k, d in enumerate(days) if d[:4] == y), 0)
    base = c[i - 1] if i else c[0]
    return (c[-1] / base - 1) * 100


def earnings(sym):
    try:
        ds = (yf.Ticker(sym).calendar or {}).get("Earnings Date") or []
        today = datetime.date.today()
        fut = sorted(d for d in ds if d >= today)
        return fut[0] if fut else None
    except Exception:  # noqa: BLE001
        return None


def kday(d):
    return f"{d.month}월 {d.day}일"


def page(s, df, bdf):
    sub = df.dropna(subset=["Close"])
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    if s["market"] == "KR" and sub.index[-1].strftime("%Y-%m-%d") == now.strftime("%Y-%m-%d") and now.hour < 16:
        sub = sub.iloc[:-1]   # 장중 봉 — 종가가 아니다
    days = [i.strftime("%Y-%m-%d") for i in sub.index]
    c = [float(x) for x in sub["Close"]]
    vol = [float(x or 0) for x in sub["Volume"]]
    b = bdf.dropna(subset=["Close"])
    bmap = {i.strftime("%Y-%m-%d"): float(x) for i, x in zip(b.index, b["Close"])}
    bc = [bmap.get(d) for d in days]
    for k in range(1, len(bc)):   # 휴장일이 다르면 앞 값
        bc[k] = bc[k] if bc[k] is not None else bc[k - 1]
    bc = [x if x is not None else bc[next(j for j in range(len(bc)) if bc[j] is not None)] for x in bc]
    m, bname = s["market"], BENCH[s["market"]][1]
    last = datetime.date.fromisoformat(days[-1])
    d1 = ret(c, 1)

    parts = [dk.price_stamp(last, m)]
    lead = (f'{kday(last)} {s["name"]}({s["sym"].split(".")[0]}) 종가는 {money(c[-1], m)}로 전날보다 '
            f'<span style="color:{color(d1)};white-space:nowrap;">{pct(d1)}</span> {"올랐" if d1 > 0 else "내렸" if d1 < 0 else "같았"}습니다. '
            f'업종은 {s["sector"]} · 세부 업종은 {s["sub"]}입니다.')
    parts.append(f'<p data-seo-lead="1" style="font-size:19px;line-height:35px;color:#333;margin:0 0 12px;word-break:keep-all;padding-left:6px;">{lead}</p>')

    q = []
    # 1. 오늘 주가는?
    q.append(C.question_card("오늘 주가는?", pct(d1), dk.dir_theme(d1, 1), color(d1), [
        ("row", "종가", money(c[-1], m), ""),
        ("row", "전날 종가", money(c[-2], m), ""),
        ("row", f"{bname} 하루", f'<span style="color:{color(ret(bc, 1))};">{pct(ret(bc, 1))}</span>', "같은 날 시장"),
    ], opened=True))
    # 2. 기간별로는?
    per = [("1주", 5), ("1달", 21), ("연초", None), ("1년", len(c) - 1)]
    groups, ahead = [], 0
    for nm, n in per:
        a = ytd(days, c) if n is None else ret(c, n)
        bb = ytd(days, bc) if n is None else ret(bc, n)
        groups.append((nm, [a, bb]))
        ahead += a > bb
    yr, byr = groups[-1][1]
    ans = "시장보다 앞섬" if yr > byr else "시장보다 뒤처짐"
    chart = C.chart_card("기간별 등락", groups, [C.sign_bg, C.gray], [C.sign_fg, C.note_fg], [(s["name"], C.PASTEL_UP), (bname, C.GRAY_BAR)], fmt=pct)
    q.append(C.question_card("기간별로는?", ans, "positive" if yr > byr else "negative", C.UP if yr > byr else C.DOWN, [
        (f"1년 동안 {pct(yr)} 움직였고, 같은 기간 {bname}는 {pct(byr)}였습니다.", "plain"),
        (chart, "html"),
    ], opened=True))
    # 3. 1년 중 어디쯤?
    hi, lo = max(c[-252:]), min(c[-252:])
    pos = (c[-1] - lo) / (hi - lo) * 100 if hi > lo else 50
    fh = (c[-1] / hi - 1) * 100
    gauge = C.range_gauge(lo, hi, pos, fh, lambda v: money(v, m), "", "1년 범위", "최고 대비", "최고가 근처")
    where = "최고가 근처" if fh > -3 else "중간쯤" if pos > 35 else "최저가 쪽"
    q.append(C.question_card("1년 중 어디쯤?", where, "neutral", "#111", [
        (f"1년 최고가보다 {abs(fh):.1f}% 아래에 있습니다." if fh <= -0.5 else "1년 최고가 근처에 있습니다.", "plain"),
        (gauge, "html"),
    ], opened=True))
    # 4. 추세는?
    ma50 = sum(c[-50:]) / 50
    ma200 = sum(c[-200:]) / 200 if len(c) >= 200 else None
    up = c[-1] > ma50 and (ma200 is None or c[-1] > ma200)
    dn = c[-1] < ma50 and (ma200 is None or c[-1] < ma200)
    st, th, col = ("▲상승", "positive", C.UP) if up else ("▼하락", "negative", C.DOWN) if dn else ("중립", "neutral", "#111")
    q.append(C.question_card("추세는?", st, th, col, [
        ("row", "50일 평균선", "위" if c[-1] > ma50 else "아래", f"{money(ma50, m)}"),
        ("row", "200일 평균선", "위" if ma200 and c[-1] > ma200 else "아래", f"{money(ma200, m)}" if ma200 else ""),
        ("평균선은 최근 며칠 동안의 종가 평균입니다. 종가가 두 선 위에 있으면 상승, 아래에 있으면 하락으로 봅니다.", "note"),
    ]))
    # 5. 거래는 평소와 같나?
    avg = sum(vol[-21:-1]) / 20 if len(vol) > 21 else None
    r = vol[-1] / avg if avg else None
    vt = "평소보다 많음" if r and r >= 1.5 else "평소보다 적음" if r and r <= 0.67 else "평소 수준"
    q.append(C.question_card("거래는 평소와 같나?", vt, "neutral", "#111", [
        ("최근 한 달 하루 평균 거래량과 비교했습니다. 거래가 크게 늘면 그날 소식이 있었는지 함께 보는 것이 좋습니다.", "plain"),
    ]))
    # 6. 다음 실적 발표는? — 없으면 카드 생략
    e = earnings(s["sym"])
    if e:
        q.append(C.question_card("다음 실적 발표는?", kday(e), "neutral", "#111", [
            ("회사가 알린 날짜입니다. 바뀌면 다음 갱신 때 고쳐집니다.", "note"),
        ]))
    parts.append(C.cards_grid("".join(q)))

    # 1년 가격 선 그래프 — 비교 = 시장 지수, 1년 전 = 0
    base, bb0 = c[0], bc[0]
    series = [(s["name"], [(x / base - 1) * 100 for x in c], dk.CHART_MAIN, "solid"),   # 그래프 색 = 주인공 주황 (2026-11-14 그래프 통일, 옛 오름 · 내림 색)
              (bname, [(x / bb0 - 1) * 100 for x in bc], dk.CHART_CMP, "dash")]
    parts.append(dk.section("1년 흐름", dk.trend_card("1년 전 대비 등락", dk.month_ticks(days), series, pct)))   # 1년 일별 = 끝 값만 · 점 없음 (ends_only 는 40일 전망 그래프용 날마다 점)
    parts.append(dk.muted("간단 정보는 가격 자료만 다룹니다. 뉴스 · 의견 · 소송은 종목 분석 페이지에서 다룹니다."))
    parts.append(dk.related_buttons(s["peers"] + [("전체 종목 목록", "mock_all_stocks.html")]))
    body = f'<div data-design="2" style="font-family:-apple-system,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;font-size:19px;line-height:35px;color:#333;">{"".join(parts)}</div>'
    title = f'{s["name"]} {s["sym"].split(".")[0]} 간단 정보'
    return dk.formal(body), title


def page_us_full(smp):
    """정식 종목과 같은 계산(stock-radar/analyze) · 같은 카드(stock-radar/render_pages)를 간단 정보 종목에 그대로 — 가격 · 공용 시장 자료로 되는 것만 (2026-11-12 사용자).
    빠지는 것 = 종목별 상세 호출 · 다른 수집 · AI 가 필요한 카드(의견 · 실적 · 기업 · 뉴스 · 방송 · 소송), 가격 그래프 PNG(브라우저가 그리는 1년 선 그래프로)."""
    rd = os.path.join(EXP, "stock-radar")
    sys.path.insert(0, rd)
    import universe as U
    sym = smp["sym"]
    if sym not in U.BY_SYM:   # 목업 안에서만 후보에 잠깐 넣는다 — 이름 · 업종 칸을 정식 계산이 읽는다
        U.CANDIDATES.append((sym, smp["name"], f"{sym.lower()}-stock", smp["sector"]))
        U.BY_SYM[sym] = U.CANDIDATES[-1]
    import collect
    import analyze
    import render_pages as RP
    syms = sorted({sym, U.BENCH, "^VIX", "SMH", *collect.SECTOR_ETFS})
    bars = collect._bars(syms)
    snap = {"fetched_at": "", "bars": bars, "caps": {sym: collect._cap(sym)[1]}, "earnings": {sym: collect._earnings(sym)[1]}, "history": history_stats([sym, U.BENCH])}
    s = analyze.stock(sym, snap)
    b = s.pop("_bars")
    s["tech"] = analyze.technical(b, snap, sym)
    s["market_regime"], s["market_shock"] = analyze.market_regime(snap), analyze.market_shock(snap)
    s["sector_flow"], s["bollinger"] = analyze.sector_flow(snap, sym), analyze.bollinger(b)
    s["overheat"], s["drawdown"] = analyze.overheat(b, s["tech"]), analyze.drawdown(b, s["year_range"], snap, sym)
    s.update(peer_moves=[], in_top=False, rank=None, industry_us=None, mom_12_1=None)
    R = RP.R
    sf = s.get("sector_flow")
    flow = ""
    if sf:
        th, col = R.FLOW_THEME.get(sf["state"], ("neutral", R.MUTED))
        flow = f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{R._state_card(sf["name"] + " 업계 자금 흐름은?", sf["state"], th, col, RP.sector_lines(sf), "", fold=True)}</div>'
    days = [x["day"] for x in b]
    c = [x["close"] for x in b][-252:]
    bmap = {x["day"]: x["close"] for x in bars[U.BENCH]}
    bc = [bmap.get(d) for d in days[-252:]]
    bc = [x if x is not None else next(y for y in bc if y is not None) for x in bc]
    series = [(smp["name"], [(x / c[0] - 1) * 100 for x in c], dk.CHART_MAIN, "solid"),   # 그래프 색 = 주인공 주황 (2026-11-14 그래프 통일, 옛 오름 · 내림 색)
              ("S&P 500", [(x / bc[0] - 1) * 100 for x in bc], dk.CHART_CMP, "dash")]
    line = dk.trend_card("1년 전 대비 등락", dk.month_ticks(days[-252:]), series, pct)
    # 상세 칸 — 정식 종목과 같은 카드, 받는 주기만 드물게(detail_cache 주기: 의견 · 이익 예상 주 1회 · 실적 뒤, 기업 90일). 공매도 · 옵션은 간단 종목에서 뺀다 (2026-11-12 사용자)
    import collect_extra as CE
    import analyze_tabs
    nxt = next((x["day"] for x in snap["earnings"][sym] if x["day"] >= s["day"]), None)
    _, st = CE._one((sym, s["close"], s["day"], nxt), only=("analysts", "eps", "company", "short"))   # 공매도 = 2주 1회 (2026-11-12 사용자 "공매도를 넣어서")
    rev, cash = sec_tables(sym)
    extra = {"stocks": {sym: st}, "revenue": {"series": {sym: rev} if rev else {}}, "capex": {sym: cash} if cash else {}, "peer_earnings": {}, "edgar": {}}
    analyze_tabs.build(s, snap, extra)
    s["expect"]["move"] = None   # 옵션(시장 예상 흔들림) = 정식 종목만 — 매일 받아야 뜻이 있다
    tab_today = (line + R.day_path_chart(s["tech"].get("path"), s["tech"].get("bench_path"), s["name"], "S&P 500")
                 + RP.price_card(s, s["day"]) + RP.sec_regime(s) + RP.sec_tech(s) + RP.sec_states(s))
    stamp_html = dk.price_stamp(s["day"], "US")
    body = (stamp_html + RP.lead(s) + R._section("오늘", tab_today, line=False, tab="오늘")
            + R._section("매수의견", RP.card_opinions(s) or dk.muted("애널리스트 의견이 아직 없습니다."), tab="매수의견")
            + R._section("실적", RP.sec_expect(s) + RP.sec_calendar(s, ("earnings",), open_first=False), tab="실적")
            + R._section("업계상황", flow or dk.muted("업계 자료가 없습니다."), tab="업계상황")
            + R._section("기업", RP.sec_company(s), tab="기업")
            + dk.muted("간단 정보는 뉴스 · 방송 의견 · 소송 · 옵션을 다루지 않습니다. 이 내용은 종목 분석 페이지에서 다룹니다.")
            + dk.related_buttons(smp["peers"] + [("전체 종목 목록", "mock_all_stocks.html")]))
    return RP.wrap(body), f'{smp["name"]} {sym} 간단 정보'


def page_kr_full(smp):
    """한국 간단 종목 — 한국 정식 종목과 같은 계산(kr-stocks/analyze_kr) · 같은 카드(render_kr). 미국과 같은 원칙(2026-11-12 사용자 "한국 거도 동일"):
    가격 · 공용 시장 자료 카드 + 드물게 받는 상세(이익 예상 · 애널리스트 · 실적일 · 분기 매출). 뉴스 · 방송 의견 · 공매도는 뺀다. 기업 정보는 DART 기업개황(실제는 등록 때 한 번)."""
    kd = os.path.join(EXP, "kr-stocks")
    sys.path.insert(0, kd)
    import universe_kr as K
    sym = smp["sym"]
    if sym not in K.BY_SYM:
        K.CANDIDATES.append((sym, smp["name"], f"{smp['slug']}-{sym.split('.')[0]}-stock", smp["kr_sector"], []))
        K.BY_SYM[sym] = K.CANDIDATES[-1]
        K.SECTOR_ETF[sym] = smp.get("kr_etf") or K.SECTOR_ETF.get("035420.KS")
    import collect_kr
    import collect_kr_extra as KX
    import analyze_kr
    import render_kr
    snap, flows, hist = collect_kr.load()
    nb = collect_kr._bars([sym])
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    for k in list(snap["bars"]):   # 장중에 목업을 돌리면 오늘 봉은 종가가 아니다 — 모든 종목에서 뺀다
        if snap["bars"][k] and snap["bars"][k][-1]["day"] == now.strftime("%Y-%m-%d") and now.hour < 16:
            snap["bars"][k] = snap["bars"][k][:-1]
    nb[sym] = [b for b in nb.get(sym, []) if not (b["day"] == now.strftime("%Y-%m-%d") and now.hour < 16)]
    snap["bars"].update(nb)
    snap["caps"][sym] = collect_kr._caps([sym]).get(sym)
    a = analyze_kr.run(snap, flows, hist)
    import yfinance as _yf
    t = _yf.Ticker(sym)
    with open(KX.EXTRA, encoding="utf-8") as f:
        extra = json.load(f)
    for key, fn in (("eps", lambda: KX.EX._eps(t)), ("analysts", lambda: KX._analysts(t))):
        try:
            extra.setdefault("stocks", {}).setdefault(sym, {})[key] = fn()
        except Exception as e:  # noqa: BLE001
            print(f"[quick] {sym} {key} 실패: {str(e)[:60]}")
    try:
        extra.setdefault("earnings", {})[sym] = KX._earn_dates(t)
        extra.setdefault("revenue", {}).setdefault("series", {})[sym] = KX._revenue(t)
    except Exception as e:  # noqa: BLE001
        print(f"[quick] {sym} 실적 실패: {str(e)[:60]}")
    try:   # 기업 정보 — DART 기업개황 (한국 정식 종목과 같은 칸)
        import collect_kr_dart as KD
        import requests as _rq
        key = KD._key()
        corp = KD.corp_codes(key).get(sym.split(".")[0]) if key else None
        r = _rq.get(f"{KD.API}/company.json", params={"crtfc_key": key, "corp_code": corp}, timeout=30).json() if corp else {}
        if r.get("status") == "000":
            extra.setdefault("company", {})[sym.split(".")[0]] = {k: (r.get(k) or "").strip() for k in KD.COMPANY_KEYS}
    except Exception as e:  # noqa: BLE001
        print(f"[quick] {sym} 기업개황 실패: {str(e)[:60]}")
    for x in a["stocks"]:   # 순위 목록에는 넣지 않는다 — 간단 종목은 시총 순위 밖
        if x["sym"] == sym:
            x["in_top"], x["rank"] = False, None
    tmp = os.path.join(OUT, "_kr_tmp")
    render_kr.write_all(a, tmp, snap, media=[], extra=extra)
    code = sym.split(".")[0]
    with open(os.path.join(tmp, f"{code}.html"), encoding="utf-8") as f:
        body = f.read()
    import re as _re
    # 종목 봉차트 그림(정식 종목만 만든다) 자리 → 오늘 탭 머리 + 브라우저가 그리는 1년 선 그래프 (미국 간단 정보와 같게)
    b = snap["bars"][sym][-252:]
    bmap = {x["day"]: x["close"] for x in snap["bars"].get(K.BENCH) or []}
    bc = [bmap.get(x["day"]) for x in b]
    bc = [v if v is not None else next(y for y in bc if y is not None) for v in bc]
    c = [x["close"] for x in b]
    series = [(smp["name"], [(v / c[0] - 1) * 100 for v in c], C.UP if c[-1] >= c[0] else C.DOWN, "solid"),
              (K.BENCH_NAME, [(v / bc[0] - 1) * 100 for v in bc], "#94A3B8", "dash")]
    line = dk.trend_card("1년 전 대비 등락", dk.month_ticks([x["day"] for x in b]), series, pct)
    body = _re.sub(r'<a href="[^"]*radar-[^"]*-' + code + r'-stock-price[^"]*".*?</a>', lambda m: render_kr.R._section("오늘", line, line=False, tab="오늘"), body, count=1, flags=_re.S)
    return body, f'{smp["name"]} {code} 간단 정보'


def sec_tables(sym):
    """분기 매출 · 돈 표 — 정식 종목 collect_extra.revenue 와 같은 SEC 공용 자료(companyfacts)를 이 종목만. 실패하면 빈 표."""
    sys.path.insert(0, os.path.join(EXP, "nvda-report"))
    import expect as EX
    import collect_capex as CX
    try:
        tickers = EX._sec("https://www.sec.gov/files/company_tickers.json")
        cik = {v["ticker"]: str(v["cik_str"]).zfill(10) for v in tickers.values()}[sym.replace("-", ".") if sym not in [v["ticker"] for v in tickers.values()] else sym]
        facts = EX.company_facts(cik)
        return EX.revenue_rows(facts), CX.rows_from_facts(facts, cik)
    except Exception as e:  # noqa: BLE001
        print(f"[quick] {sym} SEC 표 실패: {str(e)[:80]}")
        return [], []


def history_stats(syms):
    """고점 하락 후 회복 통계 — stock-radar collect.history 와 같은 계산을 이 종목 · S&P 500 만 (실제는 주 1회 긴 일봉 묶음)."""
    sys.path.insert(0, os.path.join(EXP, "nvda-report"))
    import history_stats as HS
    df = yf.download(syms, start="1999-01-01", interval="1d", auto_adjust=False, group_by="ticker", progress=False, threads=True)
    spy = df[syms[-1]]["Close"].dropna()
    out = {"stats": {}}
    for s in syms:
        cc = df[s]["Close"].dropna()
        cc = cc[cc > 0]
        if len(cc) < 500:
            continue
        out["stats"][s] = {"from": cc.index[0].strftime("%Y-%m-%d"), "to": cc.index[-1].strftime("%Y-%m-%d"), "dd": HS.dd_summary(HS.drawdown_cycles(cc)),
                           "spy_dd": HS.dd_summary(HS.drawdown_cycles(spy[spy.index >= cc.index[0]]))}
    return out


def _market_rows(data, items, market):
    """업종별 표 줄 — 이름 · 코드 · 1년 범위 위치 막대 · 하루 등락. 정식 종목은 이름 옆 `분석`."""
    rows, last = {}, None
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    for sym, name, sector, full in items:
        df = data.get(sym)
        if df is None:
            continue
        sub = df.dropna(subset=["Close"])
        if market == "KR" and sub.index[-1].strftime("%Y-%m-%d") == now.strftime("%Y-%m-%d") and now.hour < 16:
            sub = sub.iloc[:-1]   # 한국 장중 봉 — 종가가 아니다
        if len(sub) < 2:
            continue
        last = max(last or "", sub.index[-1].strftime("%Y-%m-%d"))
        c = [float(x) for x in sub["Close"]]
        d1 = ret(c, 1)
        hi, lo = max(c[-252:]), min(c[-252:])
        pos = (c[-1] - lo) / (hi - lo) * 100 if hi > lo else 50
        tag = ('<span style="margin-left:6px;padding:1px 6px;border:1px solid #E2E8F0;border-radius:4px;font-size:12px;line-height:16px;color:#6B7280;font-weight:600;">분석</span>' if full else "")
        bar = (f'<span style="display:inline-block;position:relative;width:64px;height:6px;border-radius:3px;background:#E2E8F0;vertical-align:middle;margin-right:8px;">'
               f'<span style="position:absolute;left:{pos:.0f}%;top:-3px;width:8px;height:12px;margin-left:-4px;border-radius:2px;background:#1a73e8;"></span></span>')
        code = sym.split(".")[0]
        href = "#" if full else (f"mock_quick_{code}.html" if os.path.exists(os.path.join(OUT, f"mock_quick_{code}.html")) else "#")
        nm = f'<a href="{href}" style="color:#111;text-decoration:none;">{dk.esc(name)}</a> <span style="font-size:14px;color:#6B7280;">{code}</span>{tag}'
        rows.setdefault(sector, []).append((nm, f'{bar}<span style="color:{color(d1)};">{pct(d1)}</span>', ""))
    return rows, last


def all_stocks(data):
    """전체 종목 목록 — 미국 · 한국 전환, 업종별 표: 이름 · 하루 등락 · 1년 범위 위치. 정식 종목은 이름 옆 `분석`."""
    search = ('<div style="margin:0 0 16px;"><input type="search" placeholder="종목 이름이나 코드로 찾기" '
              'style="width:100%;box-sizing:border-box;border:1px solid #E2E8F0;border-radius:999px;padding:10px 16px;font:inherit;font-size:16px;"></div>')
    btn = ('<button type="button" data-mk="{k}" onclick="document.querySelectorAll(\'[data-mk-pane]\').forEach(function(p){{p.hidden=p.dataset.mkPane!==\'{k}\'}});'
           'document.querySelectorAll(\'[data-mk]\').forEach(function(b){{b.style.fontWeight=b.dataset.mk===\'{k}\'?700:400;b.style.color=b.dataset.mk===\'{k}\'?\'#111\':\'#6B7280\'}})" '
           'style="border:0;background:none;padding:0 4px;font:inherit;font-size:15px;cursor:pointer;font-weight:{w};color:{c};">{t}</button>')
    tabs = ('<p style="margin:0 0 12px;">' + btn.format(k="US", t="미국", w=700, c="#111") + '<span style="color:#CBD5E1;"> · </span>'
            + btn.format(k="KR", t="한국", w=400, c="#6B7280") + "</p>")
    panes = []
    for market, items, tail in (("US", LIST_US, "(미국 시간)"), ("KR", LIST_KR, "")):
        rows, last = _market_rows(data, items, market)
        part = [dk.price_stamp(last, market)] if last else []
        for sector, rs in rows.items():
            part.append(dk.section(sector, dk.ccard(rs).replace('data-cards="1" ', '')))   # data-cards 는 테마가 탭 카드로 옮긴다 — 목록 표엔 쓰지 않음
        panes.append(f'<div data-mk-pane="{market}"{" hidden" if market == "KR" else ""}>{"".join(part)}</div>')
    body = [tabs, search, *panes,
            dk.muted("이름 옆에 분석 표시가 있는 종목은 뉴스 · 의견까지 다루는 종목 분석 페이지로, 나머지는 간단 정보로 갑니다. 막대는 1년 최저 ~ 최고 사이 오늘 위치입니다.")]
    html = f'<div data-design="2" style="font-family:-apple-system,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;font-size:19px;line-height:35px;color:#333;">{"".join(body)}</div>'
    return dk.formal(html)


def _no_media_opinions():
    """간단 정보 = 방송 · 뉴스 의견 카드 없음 (2026-11-12 사용자 · 기획 6-6: 한 목소리만 남는 화면 위험). 공용 의견 카드 함수에서 두 카드만 끈다 — 목업 안에서만."""
    sys.path.insert(0, os.path.join(EXP, "nvda-report"))
    import render_html as RH
    RH.picks_card = lambda *a, **k: ""
    RH.news_opinion_card = lambda *a, **k: ""


def main():
    _no_media_opinions()
    global LIST_DAY
    os.makedirs(OUT, exist_ok=True)
    syms = sorted({s["sym"] for s in SAMPLES} | {x[0] for x in LIST_US + LIST_KR} | {v[0] for v in BENCH.values()})
    df = yf.download(syms, period="1y", interval="1d", auto_adjust=False, group_by="ticker", progress=False, threads=True)
    data = {s: df[s] for s in syms if s in df.columns.get_level_values(0)}
    for s in SAMPLES:
        body, title = page_us_full(s) if s["market"] == "US" else page_kr_full(s)   # 둘 다 정식 종목과 같은 카드 (2026-11-12)
        body = re.sub(r"방송에서는[^.<]*\.\s*", "", body)   # 의견 요약의 방송 문장 — 간단 정보는 방송 의견을 싣지 않는다
        p = dk.write_mock(body, os.path.join(OUT, f'mock_quick_{s["sym"].split(".")[0]}.html'), title)
        print("만듦:", p)
    page = all_stocks(data)
    p = dk.write_mock(page, os.path.join(OUT, "mock_all_stocks.html"), "전체 종목")
    print("만듦:", p)
    kr = (page.replace('data-mk-pane="US">', 'data-mk-pane="US" hidden>', 1).replace('data-mk-pane="KR" hidden>', 'data-mk-pane="KR">', 1)   # 한국을 먼저 연 같은 목록 (2026-11-12 사용자: 한국 목록이 어디 있나)
          .replace("font-weight:700;color:#111;\">미국", "font-weight:400;color:#6B7280;\">미국", 1).replace("font-weight:400;color:#6B7280;\">한국", "font-weight:700;color:#111;\">한국", 1))
    p = dk.write_mock(kr, os.path.join(OUT, "mock_all_stocks_kr.html"), "전체 종목 (한국)")
    print("만듦:", p)


if __name__ == "__main__":
    main()
