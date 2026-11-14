"""ETF 고정 페이지 본문 — A안 (2026-11-12 사용자 "A안으로 가야지" · "계속 진행해줘"). 목업 = mock_etf.py 와 같은 화면.

    python experiments/stock-etf/etf_pages.py --market us   # stock-radar/data/snapshot.json 을 읽어 output/<티커>.html
    python experiments/stock-etf/etf_pages.py --market kr   # kr-stocks/data/snapshot.json → output/<코드>.html

- 일봉은 각 실행이 이미 받은 snapshot(etf_universe 티커를 묶음 다운로드에 얹었다)만 읽는다 — 새 가격 수집 없음. AI 0.
- 구성 · 기본 정보(야후 펀드 자료)는 주 1회만 받는다 — data/etf_fund.json (미국 = stock-radar/data, 한국 = kr-stocks/data → 각 상태 저장소에 같이 보관).
- 계산 · 카드는 정식 종목 것(stock-radar analyze · render_pages / kr-stocks analyze_kr · render_kr). 탭 = 오늘 · 구성 · 기본 정보.
  빼는 것 = 매수의견 · 실적 · 뉴스 · 방송 · 소송 · 옵션 · 기업 · 12개월 모멘텀 순위(ETF 는 우리 종목 순위에 넣지 않는다).
- 한국 analyze_kr.run 은 시총 순위 상태 파일을 고쳐 쓰므로 부르지 않는다 — 종목별 계산(stock)만.
"""

import argparse
import datetime
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [EXP, os.path.join(EXP, "daily-report")]
import design_kit as dk  # noqa: E402
import cards as C  # noqa: E402
import etf_universe as E  # noqa: E402
import candle_chart as CC  # noqa: E402 — 봉차트(페이지 안 실제 차트, 2026-11-13)

OUT = os.path.join(HERE, "output", "pages")   # 실행 결과(저장소에 올리지 않음) — 목업은 output/mock_etf_*.html (mock_etf.py)
FUND_MAX_AGE = 7   # 일 — 구성 · 보수 · 순자산은 자주 안 바뀐다
# 시장별 상태 파일 — 각 실행의 상태 저장소(stock-radar/data → nvda-state radar/, kr-stocks/data → kr 상태)에 같이 보관한다
def data_dir(market):
    return os.path.join(EXP, "stock-radar" if market == "us" else "kr-stocks", "data")


def live_path(market):
    """발행된 ETF 페이지 키 (publish_etf.py 가 쓴다) — 함께 보는 페이지 버튼이 아직 없는 페이지로 가지 않게."""
    return os.path.join(data_dir(market), "etf_pages_live.json")

SECTOR_KO = {"technology": "정보기술", "financial_services": "금융", "healthcare": "헬스케어", "consumer_cyclical": "경기 소비재", "communication_services": "커뮤니케이션",
             "industrials": "산업재", "consumer_defensive": "필수 소비재", "energy": "에너지", "utilities": "유틸리티", "realestate": "부동산", "basic_materials": "소재"}
FAMILY_KO = {"iShares": "아이셰어즈(블랙록)", "State": "스테이트 스트리트", "SPDR": "스테이트 스트리트", "Vanguard": "뱅가드", "Invesco": "인베스코", "Schwab": "찰스 슈왑",
             "JPMorgan": "JP모건", "VanEck": "반에크", "Direxion": "디렉시온", "ProShares": "프로셰어즈", "ARK": "아크 인베스트"}
KR_FAMILY = {"KODEX": "삼성자산운용", "TIGER": "미래에셋자산운용", "ACE": "한국투자신탁운용"}
NAME_KO = {"NVDA": "엔비디아", "MU": "마이크론", "AVGO": "브로드컴", "INTC": "인텔", "QCOM": "퀄컴", "TXN": "텍사스 인스트루먼트", "AMAT": "어플라이드 머티리얼즈",
           "LRCX": "램리서치", "ADI": "아날로그 디바이스", "MRVL": "마벨", "TSM": "TSMC", "MCHP": "마이크로칩", "NXPI": "NXP", "ON": "온세미",
           "AAPL": "애플", "MSFT": "마이크로소프트", "AMZN": "아마존", "GOOGL": "알파벳 A", "GOOG": "알파벳 C", "META": "메타", "TSLA": "테슬라", "BRK-B": "버크셔 해서웨이",
           "BRK.B": "버크셔 해서웨이", "JPM": "JP모건", "LLY": "일라이 릴리", "V": "비자", "MPWR": "모놀리식 파워", "COHR": "코히런트", "TER": "테라다인",
           "ORCL": "오라클", "NFLX": "넷플릭스", "COST": "코스트코", "WMT": "월마트", "PLTR": "팔란티어", "CSCO": "시스코", "IBM": "IBM", "CRM": "세일즈포스",
           "XOM": "엑슨모빌", "UNH": "유나이티드헬스", "HD": "홈디포", "PG": "P&G", "KO": "코카콜라", "PEP": "펩시코", "ABBV": "애브비", "MRK": "머크", "CVX": "셰브론",
           "GS": "골드만삭스", "CAT": "캐터필러", "AMGN": "암젠", "MCD": "맥도날드", "COIN": "코인베이스", "ROKU": "로쿠", "SHOP": "쇼피파이", "HOOD": "로빈후드"}
MOCK_ONLY = ("<!--mock-only-->", "<!--/mock-only-->")   # 한국 render_kr 과 같은 표시 — 목업에만
REAL_ONLY = ("<!--real-only-->", "<!--/real-only-->")   # 발행 본문에만


# ── 구성 · 기본 정보 (야후 펀드 자료, 주 1회) ──

def fund_path(market):
    return os.path.join(data_dir(market), "etf_fund.json")


def _fetch_fund(sym):
    import yfinance as yf
    t = yf.Ticker(sym)
    i = t.info or {}
    out = {"at": datetime.date.today().isoformat(), "family": i.get("fundFamily"), "fee": i.get("netExpenseRatio"), "aum": i.get("totalAssets"),
           "yield": i.get("yield"), "since": datetime.date.fromtimestamp(i["fundInceptionDate"]).isoformat() if i.get("fundInceptionDate") else None,
           "top": [], "sectors": []}
    fd = t.funds_data
    th = fd.top_holdings
    out["top"] = [[k, v["Name"], round(float(v["Holding Percent"]) * 100, 2)] for k, v in th.head(10).iterrows()]
    out["sectors"] = sorted(([SECTOR_KO.get(k, k), round(v * 100, 2)] for k, v in (fd.sector_weightings or {}).items() if v and v >= 0.01), key=lambda x: -x[1])[:5]
    return out


def funds(market, syms):
    """미국 ETF 펀드 자료 — 7일 지난 것만 다시 받는다. 실패하면 지난 값 그대로."""
    path = fund_path(market)
    try:
        with open(path, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        cache = {}
    today = datetime.date.today()
    got, tried, fails = 0, 0, []
    for sym in syms:
        old = cache.get(sym)
        if old and (today - datetime.date.fromisoformat(old["at"])).days < FUND_MAX_AGE:
            continue
        tried += 1
        try:
            cache[sym] = _fetch_fund(sym)
            got += 1
        except Exception as e:  # noqa: BLE001
            fails.append(f"{sym} {str(e)[:60]}")
            print(f"[etf] {sym} 구성 받기 실패 (지난 값 유지): {str(e)[:80]}")
        time.sleep(1)
    if got:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
        print(f"[etf] 구성 · 기본 정보 {got}개 새로 받음 → {path}")
    if tried and market == "us":   # 운영 대시보드 `주기 자료는 제때 받았나?` (2026-11-13) — 한국 실행의 미국 짝 ETF 는 예비라 미국 실행 것만
        try:
            import feed_log
            ats = sorted(v.get("at") or "" for k, v in cache.items() if k in syms)
            feed_log.feed("미국 ETF 구성 · 보수 (야후)", ok=not fails, label=f"{len([k for k in syms if k in cache])}/{len(syms)}개", data_date=ats[-1] if ats else "",
                          got_new=got > 0, error=" / ".join(fails)[:200], every_days=FUND_MAX_AGE)
        except Exception as e:  # noqa: BLE001
            print(f"[etf] 받기 현황 기록 건너뜀: {e!r}")
    return cache


# ── 카드 ──

def weight_rows(items):
    """비중 줄 — 이름 · 막대 · %. 막대 길이 = 그 표 안 최대 비중 대비."""
    mx = max(w for _, w in items) or 1
    rows = []
    for name, w in items:
        bar = dk.hbar(w, mx, dk.CHART_MAIN, "72px")   # 줄 막대 = dk.hbar(10 · 모서리 3 · 바탕 #F1F5F9), 비중 = 주인공 크기 주황 (2026-11-14 그래프 통일, 옛 8 · 4 · 회색)
        rows.append((name, f'{bar}<span style="font-variant-numeric:tabular-nums;">{w:.1f}%</span>', ""))
    return dk.ccard(rows).replace('data-cards="1" ', "")


def tab_holdings(f, src_note="", link=None):
    """link = (글자, 주소) — src_note 안의 `@링크@` 자리를 출처 링크로 (muted 는 글자를 이스케이프한다)."""
    """구획 제목마다 data-tab — 테마는 표시 없는 h2 를 첫 탭(오늘)으로 옮긴다 (2026-11-12 목업에서 `어떤 ETF 인가?` 가 오늘 탭에 나온 것)."""
    if not f or not f.get("top"):
        return ""
    names = []
    for s, n, w in f["top"]:
        nm = NAME_KO.get(s, n)
        chip = nm != s and not str(s).isdigit()   # 한국 종목(6자리 코드)은 이름만 — 코드 칩은 미국 티커에만
        names.append((dk.esc(nm) + (f' <span style="font-size:14px;color:#6B7280;">{dk.esc(s)}</span>' if chip else ""), w))
    top_sum = sum(w for _, w in names)
    note = dk.muted(f"상위 10종목이 전체의 {top_sum:.0f}%입니다." + (" " + src_note if src_note else ""))
    if link:
        note = note.replace("@링크@", f'<a href="{dk.esc(link[1])}" style="color:inherit;text-decoration:underline;">{dk.esc(link[0])}</a>')
    out = dk.section("무엇을 담고 있나?", weight_rows(names) + note, tab="구성")
    if f.get("sectors") and f["sectors"][0][1] < 99:
        out += dk.section("업종 비중은?", weight_rows([tuple(x) for x in f["sectors"]]), tab="구성")
    return out


def _big_usd(v):
    return f"{v / 1e12:.2f}조 달러" if v >= 1e12 else f"{v / 1e8:,.0f}억 달러"


def fee_text(v):
    """1년 보수 — 0.0068% 같은 아주 낮은 보수도 0.01% 로 뭉개지지 않게 (한국 미국 지수 ETF, 2026-11-13)."""
    return f"{v:.2f}%" if v >= 0.1 else f"{v:.4f}".rstrip("0").rstrip(".") + "%"


def _big_krw(v):
    return f"{v / 1e12:,.1f}조 원" if v >= 1e12 else f"{v / 1e8:,.0f}억 원"


def trade_value(bars, n=20):
    """하루 평균 거래대금(최근 n거래일, 종가 × 거래량) — 사고팔기 쉬운가 (2026-11-13 P549). 원 또는 달러."""
    xs = [x["close"] * x["volume"] for x in bars[-n:] if x.get("volume")]
    return sum(xs) / len(xs) if len(xs) >= n // 2 else None


def tab_basic(sym, f, bars=None):
    rows = [("따라가는 지수", dk.esc(E.BY_SYM[sym][2]), "")]
    fam = (f or {}).get("family")
    if fam:
        rows.append(("운용사", dk.esc(FAMILY_KO.get(fam.split(" ")[0], fam)), ""))
    if (f or {}).get("fee") is not None:
        rows.append(("1년 보수", fee_text(f["fee"]), ""))
    if (f or {}).get("aum"):
        rows.append(("순자산", _big_usd(f["aum"]), ""))
    if (f or {}).get("aum_krw"):
        rows.append(("순자산", _big_krw(f["aum_krw"]), ""))
    tv = trade_value(bars) if bars else None
    if tv:   # 사고팔기 쉬운가 (2026-11-13 P549) — 이미 받은 일봉만
        rows.append(("하루 평균 거래대금", _big_krw(tv) if sym.endswith(".KS") else _big_usd(tv), "최근 20거래일"))
    if (f or {}).get("since"):
        rows.append(("상장일", f["since"].replace("-", ". ") + ".", ""))
    if (f or {}).get("yield"):
        rows.append(("분배금 수익률(1년)", f'{f["yield"] * 100:.2f}%', ""))
    why = E.EXPLAIN.get(E.BY_SYM[sym][2])
    src = (f or {}).get("source")
    note = (why or "") + (f" 보수 · 순자산 출처 : {src}." if src else "")
    return dk.section("어떤 ETF 인가?", dk.ccard(rows).replace('data-cards="1" ', "") + (dk.muted(note.strip()) if note.strip() else ""), tab="기본 정보")


def theme_of(sym):
    """비교 묶음 — 같은 지수, 또는 같은 테마(지수 이름에 `2차전지` · `반도체`가 들고 한국 지수끼리). 레버리지 · 인버스는 따로."""
    idx = E.BY_SYM[sym][2]
    if "2배" in idx:
        return idx
    for k in ("2차전지",):
        if k in idx:
            return k
    return idx


def compare_card(sym, bars_all, kfund):
    """`비슷한 ETF와 비교하면?` (2026-11-13 P548) — 같은 묶음 한국 상장 ETF 의 1년 등락 · 보수 · 순자산. 추천 X, 차이만. 둘 이상일 때만."""
    peers = [t[0] for t in E.KR if theme_of(t[0]) == theme_of(sym)]
    if len(peers) < 2:
        return ""
    rows = []
    for p in peers:
        b = bars_all.get(p) or []
        if len(b) < 200:
            continue
        r1 = (b[-1]["close"] / b[max(0, len(b) - 253)]["close"] - 1) * 100
        f = kfund.get(p) or {}
        bits = [f"보수 {fee_text(f['fee'])}"] if f.get("fee") is not None else []
        if f.get("aum_krw"):
            bits.append(f"순자산 {_big_krw(f['aum_krw'])}")
        name = E.BY_SYM[p][1]
        nm = f"<b>{dk.esc(name)}</b>" if p == sym else f'<a href="{dk.esc(E.page_url(p))}" style="color:#111;">{dk.esc(name)}</a>'
        sub = " · ".join(bits) + (f" · 따라가는 지수 {dk.esc(E.BY_SYM[p][2])}" if E.BY_SYM[p][2] != E.BY_SYM[sym][2] else "")
        rows.append((nm, f"1년 {pct(r1)}", f'<span style="font-size:14px;color:#6B7280;">{sub}</span>' if sub else ""))
    if len(rows) < 2:
        return ""
    return dk.section("비슷한 ETF와 비교하면?", dk.ccard(rows).replace('data-cards="1" ', "")
                      + dk.muted("같은 것을 담는 한국 상장 ETF 입니다. 1년 등락은 분배금을 빼고 계산했습니다."), tab="기본 정보")


def related(sym, live, href=None):
    """함께 보는 페이지 = 같은 것을 따라가는 다른 ETF. 발행 본문 = 같은 시장은 발행된 것만(live), 목업 = 전부.
    다른 시장 페이지는 그 실행의 기록이 여기 없어 거르지 않는다 — 처음 만드는 날(하루 10개 상한)만 잠깐 없는 주소일 수 있다."""
    href = href or E.page_url

    def buttons(xs):
        out = [(E.BY_SYM[x][1] if x.endswith(".KS") else f"{E.BY_SYM[x][1]} {x}", href(x)) for x in xs]
        return dk.related_buttons(out) if out else ""
    allx = E.same_tracks(sym)
    pub = [x for x in allx if live is None or x.endswith(".KS") != sym.endswith(".KS") or E.key(x) in live]
    if pub == allx:
        return buttons(allx)
    return MOCK_ONLY[0] + buttons(allx) + MOCK_ONLY[1] + REAL_ONLY[0] + buttons(pub) + REAL_ONLY[1]


def pct(v):
    return f"{v:+.1f}%".replace("-", "−")


def line_card(name, days, c, bench_days_close, bench_name):
    bc = [bench_days_close.get(d) for d in days]
    first = next((y for y in bc if y is not None), None)
    if first is None:
        return ""
    bc = [x if x is not None else first for x in bc]
    series = [(name, [(x / c[0] - 1) * 100 for x in c], dk.CHART_MAIN, "solid"),   # 그래프 색 = 가이드라인 4절 (주인공 주황 · 비교 회색 점선)
              (bench_name, [(x / bc[0] - 1) * 100 for x in bc], dk.CHART_CMP, "dash")]
    return dk.trend_card("1년 전 대비 등락", dk.month_ticks(days), series, pct)


E_MOCK, E_REAL = ("<!--etf-mock-->", "<!--/etf-mock-->"), ("<!--etf-real-->", "<!--/etf-real-->")
MOCK_AVG = 0.97   # 목업에만 보이는 `내 평단 (예시)` = 마지막 종가의 97% — 실제 페이지엔 없다(회원 본인 화면에서만 브라우저가 그린다, 회원 기능 때)


def candle(name, bars, dec):
    """맨 위 = 봉차트(일 · 주 · 월 · 넘겨보기 · 확대 · 전체 화면 지표) — 옛 `1년 전 대비 등락` 선 그래프 자리 (2026-11-13 사용자). 1년 비교는 `기간별 수익률` 막대에 있다."""
    real = CC.card(name, bars, dec, title="")   # 제목 없음 (2026-11-13 사용자: `가격 흐름` 삭제)
    if not real:
        return ""
    last = bars[-1]["close"]
    mock = CC.card(name, bars, dec, avg={"price": round(last * MOCK_AVG, dec), "label": "내 평단"}, title="")
    gap = '<div style="height:20px;"></div>'   # 차트와 탭 사이 20 더 (2026-11-14 사용자)
    return E_MOCK[0] + mock + gap + E_MOCK[1] + E_REAL[0] + real + gap + E_REAL[1] + CC.SCRIPT   # ETF 전용 표시 — 한국 ETF 본문은 render_kr 를 거치며 mock-only 를 먼저 지운다


def load_live(market):
    try:
        with open(live_path(market), encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


# ── 미국 ──

def us_pages(snap, live, fund):
    sys.path.insert(0, os.path.join(EXP, "stock-radar"))
    import universe as U
    import analyze
    import render_pages as RP
    R = RP.R
    snap = dict(snap, caps=dict(snap.get("caps") or {}), earnings=dict(snap.get("earnings") or {}))
    pages = {}
    for sym, name, tracks, _a in E.US:
        b0 = snap["bars"].get(sym) or []
        if len(b0) < 30:
            print(f"[etf] {sym}: 일봉 부족 — 건너뜀")
            continue
        if sym not in U.BY_SYM:   # 정식 계산이 이름 · 업종 칸을 읽는다 — 이 실행 안에서만
            U.CANDIDATES.append((sym, name, E.slug(sym), "반도체" if "반도체" in tracks else "기술"))
            U.BY_SYM[sym] = U.CANDIDATES[-1]
            if "반도체" not in tracks:
                U.SECTOR_OVERRIDE[sym] = (U.BENCH, "S&P 500")   # 넓은 지수 ETF 의 업종 대비 = 시장 그 자체
        snap["caps"].setdefault(sym, None)
        snap["earnings"].setdefault(sym, [])
        try:
            s = analyze.stock(sym, snap)
            b = s.pop("_bars")
            s["tech"] = analyze.technical(b, snap, sym)
            s["market_regime"], s["market_shock"] = analyze.market_regime(snap), analyze.market_shock(snap)
            s["sector_flow"], s["bollinger"] = None, analyze.bollinger(b)
            s["overheat"], s["drawdown"] = analyze.overheat(b, s["tech"]), analyze.drawdown(b, s["year_range"], snap, sym)
            s.update(peer_moves=[], in_top=False, rank=None, industry_us=None, mom_12_1=None)
            days = [x["day"] for x in b][-252:]
            today = (R.day_path_chart(s["tech"].get("path"), s["tech"].get("bench_path"), name, "S&P 500")
                     + RP.price_card(s, s["day"]) + RP.sec_regime(s) + RP.sec_tech(s) + RP.sec_states(s))
            f = fund.get(sym) or {}
            hold = tab_holdings(f)
            body = (dk.price_stamp(s["day"], "US") + RP.lead(s)
                    + candle(name, b0, 2)   # 차트 = 탭 위 (2026-11-13 사용자)
                    + R._section("오늘", today, line=False, tab="오늘")
                    + (R._section("구성", hold, tab="구성") if hold else "")
                    + R._section("기본 정보", tab_basic(sym, f, b0), tab="기본 정보")
                    + related(sym, live))
            pages[E.key(sym)] = (E.page_title(sym), RP.wrap(body))
        except Exception as e:  # noqa: BLE001 — 한 ETF 실패가 나머지를 막지 않게
            print(f"::warning::[etf] {sym} 페이지 실패: {e!r}")
    return pages


# ── 한국 ──

ALIAS_SYM = ("SECTOR_ETF", "PAIRS", "TRADE_TAG")              # 종목 키 표 중 업종 칸만 (연결 성적 PAIR_RECORD · 회사 소개 ABOUT 은 회사 것이라 뺀다)
ALIAS_IN = ("BSI_INDUSTRY", "FIN_INDUSTRY", "LOAN_INDUSTRY")    # {업종 코드: (이름, [종목])}
ALIAS_CODE = ("BIZ_OF",)                                      # {종목 코드: 사업 묶음}


def alias_kr(K, rep, etf):
    """한국 업종 ETF 를 대표 종목의 업종 칸에 잇는다 — 업계 카드 · 미국과 연결이 대표 종목과 같은 자료를 읽게 (이 실행 안에서만)."""
    for n in ALIAS_SYM:
        d = getattr(K, n)
        if rep in d:
            d[etf] = d[rep]
    for n in ALIAS_IN:
        for _code, (_name, syms) in getattr(K, n).items():
            if rep in syms and etf not in syms:
                syms.append(etf)
    for n in ALIAS_CODE:
        d = getattr(K, n)
        if E.key(rep) in d:
            d[E.key(etf)] = d[E.key(rep)]


MOVE_DAYS = 60   # `함께 움직이는 종목은?` 선 그래프 = 최근 60거래일(약 3개월) — 점이 24개 넘으면 끝 값만 (dk.trend_card)


def _sgn(v):
    return f"{v:+.2f}".replace("-", "−")


def move_state(name, day, ret_1d, us, us_ret, us_day, peer, peer_ret):
    """강조 카드 답 (2026-11-13 사용자 P538 "강조 카드 안에" → Claude 설계): 종목 페이지 `함께 움직이는 종목은?` 과 같은 뜻 —
    밤사이 미국 비교 대상이 올랐나 · 내렸나(±0.5% 기준, render_kr.pairs_state 와 같은 문턱). 미국 비교가 없으면(코스닥 150) 같은 날 대표 종목.
    → (답, 테마, 설명 문장) 또는 None."""
    base, who, when = (us_ret, us, f"밤사이(미국 {us_day[5:].replace('-', '.')} 종가) ") if us_ret is not None else (peer_ret, peer, "오늘 ")
    if base is None:
        return None
    state, theme = ("올랐음", "positive") if base >= 0.5 else ("내렸음", "negative") if base <= -0.5 else ("비슷함", "neutral")
    sent = (f"{when}{dk.josa(who, '은')} {_sgn(base)}%였고, 오늘 {dk.josa(name, '은')} {_sgn(ret_1d)}%였습니다." if ret_1d is not None and us_ret is not None
            else f"{when}{dk.josa(who, '은')} {_sgn(base)}%였습니다.")
    return state, theme, sent


def move_card(sym, snap, stocks, K, s=None):
    """`함께 움직이는 종목은?` (2026-11-12 사용자: 비교 종목 그래프처럼 선 그래프, 값은 주인공 선 끝에만) — 종목 페이지 같은 이름 카드의 ETF 판.
    주인공 = 이 ETF(주황 실선), 비교 = 같은 업종 대표 종목(시가총액 1위, 청록 점선) · 밤사이 미국(연보라 점선). 점선은 끝 값을 달지 않는다.
    미국 값은 한국 날짜 d 에 `d 보다 앞선 마지막 미국 종가`(밤사이) — 미국과 연결 카드와 같은 기준.
    2026-11-13 P538: 강조 카드 안에(답 = move_state, 펼친 채로 — 그래프가 카드의 본문)."""
    idx = E.BY_SYM[sym][2]
    caps = snap.get("caps") or {}
    b = (snap["bars"].get(sym) or [])[-MOVE_DAYS:]
    if len(b) < 20:
        return ""
    days = [x["day"] for x in b]
    rep = E.KR_REP.get(idx)
    peer = None
    if rep:
        g = (K.groups(rep) or [None])[0]
        cands = [c for c in stocks if g in c[4]]
    elif idx.startswith("코스피 200") or idx.startswith("코스닥 150"):
        mk = ".KS" if idx.startswith("코스피") else ".KQ"
        cands = [c for c in stocks if c[0].endswith(mk)]
    else:
        cands = []
    cands = sorted((c for c in cands if caps.get(c[0])), key=lambda c: -caps[c[0]])
    if cands:
        peer = cands[0]

    def norm(vals):
        first = next((v for v in vals if v is not None), None)
        return [None if v is None else (v / first - 1) * 100 for v in vals] if first else None
    series = [(E.BY_SYM[sym][1], norm([x["close"] for x in b]), dk.CHART_MAIN, "solid")]
    if peer:
        m = {x["day"]: x["close"] for x in snap["bars"].get(peer[0]) or []}
        v = norm([m.get(d) for d in days])
        if v and sum(x is not None for x in v) >= 20:
            series.append((peer[1], v, dk.CHART_SERIES[1], "thin"))   # 비교 = 얇은 실선 (2026-11-13 사용자: 점선 둘은 눈이 아프다)
    peer_ret = None
    if peer:
        pb = snap["bars"].get(peer[0]) or []
        if len(pb) >= 2 and pb[-1]["day"] == days[-1] and pb[-2]["close"]:
            peer_ret = (pb[-1]["close"] / pb[-2]["close"] - 1) * 100
    us = E.KR_US_LINE.get(idx)
    us_ret = us_day = None
    if us:
        ub = sorted((snap.get("us_bars") or {}).get(us[0]) or [], key=lambda x: x["day"])
        vals, k = [], -1
        for d in days:   # d 보다 앞선 마지막 미국 종가
            while k + 1 < len(ub) and ub[k + 1]["day"] < d:
                k += 1
            vals.append(ub[k]["close"] if k >= 0 else None)
        v = norm(vals)
        if v and sum(x is not None for x in v) >= 20:
            series.append((us[1], v, dk.CHART_SERIES[2], "thin"))
        if k >= 1 and ub[k - 1]["close"]:   # 마지막 한국 날짜 앞의 미국 하루 등락 = 강조 카드 답
            us_ret, us_day = (ub[k]["close"] / ub[k - 1]["close"] - 1) * 100, ub[k]["day"]
    if len(series) < 2:
        return ""
    chart = dk.trend_card("최근 3개월 등락 (%)", dk.month_ticks(days, every=1), series, pct)
    note = "미국 값은 한국 장이 열리기 전 마지막 미국 종가입니다." if us else ""
    name = E.BY_SYM[sym][1]
    ret_1d = (s or {}).get("ret_1d")
    st = move_state(name, days[-1], ret_1d, us[1] if us else None, us_ret, us_day, peer[1] if peer else None, peer_ret)
    if not st:   # 답을 낼 재료가 없으면 예전처럼 그래프만
        return dk.section("함께 움직이는 종목은?", chart + (dk.muted(note) if note else ""), tab="오늘")
    sys.path.insert(0, os.path.join(EXP, "nvda-report"))
    import render_html as R
    state, theme, sent = st
    col = {"positive": C.UP, "negative": C.DOWN}.get(theme, "#111")   # 회색 카드 답 = 검정 (가이드라인 7절, 2026-11-08)
    lines = [(sent, "plain"), (chart + (dk.excl_note(note) if note else ""), "html")]   # 안내 = 느낌표 + 작은 회색 (2026-11-13 사용자, 가이드라인 8절 안내형)
    return R._state_card("함께 움직이는 종목은?", state, theme, col, lines, "", fold=True, opened=True)


def kr_pages(snap, flows, hist, live, us_fund, kfund=None):
    kfund = kfund or {}
    sys.path.insert(0, os.path.join(EXP, "kr-stocks"))
    import universe_kr as K
    import analyze_kr
    import render_kr
    render_kr.draw_charts = lambda *a, **k: None   # 종목 봉차트 그림은 정식 종목만 — ETF 는 1년 선 그래프(브라우저)
    render_kr.list_body = lambda *a, **k: ""        # 시총 목록 페이지는 정식 종목 것 — ETF 는 순위가 없다
    syms = [t[0] for t in E.KR if len(snap["bars"].get(t[0]) or []) >= 30]
    for sym in E.KR_SYMS:
        if sym not in syms:
            print(f"[etf] {sym}: 일봉 부족 — 건너뜀")
    stocks_kr = list(K.CANDIDATES)   # 정식 한국 종목 — `같은 업종 종목은?` 재료
    for sym in syms:   # 이 실행 안에서만 후보에 더한다 — 정식 종목 페이지는 main_kr 가 이미 그렸다. 순위 계산(run)은 부르지 않는다
        tracks = E.BY_SYM[sym][2]
        rep = E.KR_REP.get(tracks)
        K.CANDIDATES.append((sym, E.BY_SYM[sym][1], E.slug(sym), K.sector(rep) if rep else "ETF", list(K.groups(rep)) if rep else []))
        K.BY_SYM[sym] = K.CANDIDATES[-1]
        if rep:
            alias_kr(K, rep, sym)
    stocks = [x for x in (analyze_kr.stock(sym, snap, hist, flows) for sym in syms) if x]
    if not stocks:
        return {}
    day = max(s["day"] for s in stocks)
    market = analyze_kr.flows(flows, snap["bars"].get(K.BENCH)) or {}
    market["overnight"] = analyze_kr.overnight(snap, day)
    mr = analyze_kr.A.market_regime({"bars": {analyze_kr.NC.REGIME_BENCHMARK: snap["bars"].get(K.BENCH) or []}})
    for s in stocks:   # 순위 · 모멘텀 순위 없음 (mom_rank 가 없으면 카드가 빠진다)
        s.update(market_regime=mr, sector_flow=analyze_kr.sector_flow(snap, s["sym"]), fx=market.get("fx"), crash=None, rank=None, in_top=False)
    a = {"day": day, "fetched_at": snap.get("fetched_at"), "stocks": stocks, "market": market, "crash": {}}
    kbench = {x["day"]: x["close"] for x in snap["bars"].get(K.BENCH) or []}

    def chart(s):   # 봉차트 그림 자리 → 오늘 탭 머리 + 1년 선 그래프 (미국 ETF 와 같게)
        b = snap["bars"][s["sym"]][-252:]
        return candle(s["name"], snap["bars"][s["sym"]], 0) + render_kr.R._section("오늘", "", line=False, tab="오늘")   # 차트 = 탭 위(증시 리포트와 같은 자리, 2026-11-13 사용자)
    render_kr.sec_chart = chart
    render_kr.sec_pairs = lambda s, a=None: move_card(s["sym"], snap, stocks_kr, K, s)   # 종목 페이지 `함께 움직이는 종목은?` 자리 → ETF 는 선 그래프
    tmp = os.path.join(OUT, "_kr_tmp")
    extra = {"stocks": {}, "earnings": {}, "revenue": {"series": {}}, "company": {}}
    render_kr.write_all(a, tmp, snap, media=[], extra=extra)
    pages = {}
    for s in stocks:
        sym, code = s["sym"], s["code"]
        try:
            with open(os.path.join(tmp, f"{code}.html"), encoding="utf-8") as f:
                body = f.read()
            nxt = next((m for m in re.finditer(r'<h2[^>]*data-tab="([^"]*)"', body) if m.group(1) != "오늘"), None)
            cut = nxt is not None
            if cut:   # 오늘 탭 뒤(매수의견 · 실적 · 업계상황 · 기업 …)는 회사 자료라 뺀다 — 업계상황은 아래에서 ETF 것으로 다시 붙인다
                body = body[:nxt.start()]
            # 구성 · 보수 · 순자산 = 운용사 상품 페이지 (2026-11-13 P547 · P540, 운영지침 D4-15-2). 레버리지 · 인버스는 선물로 배수를 만들어 담은 종목 표가 움직임을 말하지 않아 구성 탭을 뺀다
            kf = dict(kfund.get(sym) or {})
            lev = "2배" in E.BY_SYM[sym][2]
            hold = ""
            if kf.get("top") and not lev:
                at = kf.get("at") or ""
                src = f"{int(at[5:7])}월 {int(at[8:10])}일 기준입니다. 출처 : @링크@" if at else ""
                hold = tab_holdings({"top": kf["top"], "sectors": []}, src, (kf.get("source") or "운용사", kf.get("url") or ""))
            elif not lev:   # 운용사 자료가 없을 때만 예전 길 — 같은 지수 미국 ETF 구성
                twin = next((t[0] for t in E.US if t[2] == E.BY_SYM[sym][2]), None) if "미국" in E.BY_SYM[sym][1] else None
                f = dict(us_fund.get(twin) or {}) if twin else {}
                hold = tab_holdings(f, f"같은 지수를 따라가는 미국 상장 {twin} 기준입니다.") if twin else ""
            ind = (render_kr.card_sector_flow(s) + render_kr.card_industry_mood(s) + render_kr.card_industry_work(s) + render_kr.card_industry_money(s))
            basic = {"family": KR_FAMILY.get(E.BY_SYM[sym][1].split(" ")[0]), "fee": kf.get("fee"), "aum_krw": kf.get("aum_krw"), "since": kf.get("since"),
                     "source": kf.get("source") if (kf.get("fee") is not None or kf.get("aum_krw")) else None}
            body += ((render_kr.R._section("업계상황", f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{ind}</div>', tab="업계상황") if ind else "")
                     + (render_kr.R._section("구성", hold, tab="구성") if hold else "")
                     + render_kr.R._section("기본 정보", tab_basic(sym, basic, snap["bars"].get(sym)) + compare_card(sym, snap["bars"], kfund), tab="기본 정보") + related(sym, live) + ("</div>" if cut else ""))   # 잘라낸 본문의 바깥 틀 닫기
            pages[code] = (E.page_title(sym), body)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[etf] {sym} 페이지 실패: {e!r}")
    return pages


def write(pages, mock=True):
    os.makedirs(OUT, exist_ok=True)
    for key, (title, body) in pages.items():
        real = re.sub(r"<!--(?:etf-)?mock(?:-only)?-->.*?<!--/(?:etf-)?mock(?:-only)?-->", "", body, flags=re.S)
        real = re.sub(r"<!--/?(?:real-only|etf-real)-->", "", real)
        body = re.sub(r"<!--(?:etf-)?real(?:-only)?-->.*?<!--/(?:etf-)?real(?:-only)?-->", "", body, flags=re.S)
        body = re.sub(r"<!--/?(?:mock-only|etf-mock)-->", "", body)
        with open(os.path.join(OUT, f"{key}.html"), "w", encoding="utf-8") as f:
            f.write(real)
        if mock:   # 목업 = output/mock_etf_<키>.html — 목업 서버가 블로그 주소(/p/<키>-etf.html)를 이 파일로 바꿔 연다
            dk.write_mock(body, os.path.join(HERE, "output", f"mock_etf_{key}.html"), title)
    print(f"[etf] 페이지 {len(pages)}개 → {OUT}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=("us", "kr"), required=True)
    a = ap.parse_args()
    live = load_live(a.market)
    if a.market == "us":
        with open(os.path.join(EXP, "stock-radar", "data", "snapshot.json"), encoding="utf-8") as f:
            snap = json.load(f)
        pages = us_pages(snap, live, funds("us", E.US_SYMS))
    else:
        sys.path.insert(0, os.path.join(EXP, "kr-stocks"))
        import collect_kr
        snap, flows, hist = collect_kr.load()
        # 한국 ETF 중 미국 지수를 따라가는 것 = 같은 지수 미국 ETF 구성 — 한국 실행이 따로 받아 둔다(미국 실행 자료는 이 실행에 없다)
        twins = sorted({t[0] for k in E.KR if "미국" in k[1] for t in E.US if t[2] == k[2]})
        import kr_holdings as KH   # 운용사 상품 페이지 구성 · 보수 · 순자산, 주 1회 (2026-11-13 P547)
        kfund = KH.fetch_all(E.KR_SYMS, os.path.join(data_dir("kr"), "etf_kr_holdings.json"))
        pages = kr_pages(snap, flows, hist, live, funds("kr", twins), kfund)
    write(pages)
    # 본문이 너무 적으면 자료가 덜 받아진 날 — 실패 코드(발행 단계는 continue-on-error 로 건너뜀)
    want = {"us": len(E.US) // 2, "kr": len(E.KR) // 2}[a.market]
    sys.exit(0 if len(pages) >= want else 1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()


# ── 종목 목록 페이지의 ETF 구획 (2026-11-12 사용자 "목록 페이지도 보여줘. 목업 페이지에도 보여줘") ──
LIST_SHOW = 6   # 처음 보이는 줄 — 나머지는 `ETF 더 보기` 접기 (후보 11~20위 접기와 같은 틀)


def _list_rows(market, bars, syms):
    sys.path.insert(0, os.path.join(EXP, "nvda-report"))
    import render_html as R
    items = []
    for sym in syms:
        b = bars.get(sym) or []
        if len(b) < 2:
            continue
        c, p = b[-1]["close"], b[-2]["close"]
        r = (c / p - 1) * 100 if p else 0.0
        pcol = C.UP if r > 0 else C.DOWN if r < 0 else "#111"
        price = f"${c:,.2f}" if market == "us" else f"{c:,.0f}원"
        logo = dk.ticker_logo(sym) if market == "us" else ""   # 한국 ETF 는 로고 없이 (한국 목록의 배지는 종목 코드용)
        left = (f'{logo}<a href="{dk.esc(E.page_url(sym))}" style="color:#111;text-decoration:none;">{dk.esc(E.BY_SYM[sym][1])}</a>'
                f'<span style="display:block;padding-left:{26 if logo else 0}px;font-size:{dk.MICRO};line-height:20px;font-weight:400;color:{dk.NOTE};">'
                f'{dk.esc(E.key(sym))} · {dk.esc(E.BY_SYM[sym][2])}</span>')
        items.append((left, f'<span style="color:{pcol};">{price}</span><br>{R._arrow(r)}', r))
    if not items:
        return ""

    def card(xs):   # 줄 전체가 ETF 페이지로 가는 터치 영역 (종목 목록 줄과 같다)
        rows = "".join(R._row_html(lf, rt, first=i == 0).replace("<span", f'<span data-row-link="1" data-ret="{r:.4f}"', 1) for i, (lf, rt, r) in enumerate(xs))
        return f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'
    more = items[LIST_SHOW:]
    return dk.section("ETF", card(items[:LIST_SHOW])) + (dk.fold(f"ETF {len(more)}개 더 보기", card(more)) if more else "")


def list_section(market, bars):
    """목록 페이지 ETF 구획 — 발행 본문은 발행된 ETF 페이지(etf_pages_live.json)만, 목업은 전부. 없는 페이지로 링크하지 않게."""
    try:
        syms = E.US_SYMS if market == "us" else E.KR_SYMS
        live = load_live(market)
        everything = _list_rows(market, bars, syms)
        published = _list_rows(market, bars, [s for s in syms if E.key(s) in live])
        return MOCK_ONLY[0] + everything + MOCK_ONLY[1] + REAL_ONLY[0] + published + REAL_ONLY[1]
    except Exception as e:  # noqa: BLE001 — ETF 구획이 실패해도 목록은 나간다
        print(f"::warning::[etf] 목록 구획 실패: {e!r}")
        return ""
