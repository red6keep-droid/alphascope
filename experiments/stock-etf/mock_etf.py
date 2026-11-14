"""ETF 종목 페이지 목업 — A안: ETF 마다 고정 페이지, 종목 페이지와 같은 틀에서 되는 칸만 (2026-11-12 사용자 "A안으로 가야지").

    python experiments/stock-etf/mock_etf.py      # output/mock_etf_<티커>.html

설계 (Claude, 2026-11-12):
  탭 = 오늘 · 구성 · 기본 정보.
  오늘   = 종목 페이지 오늘 탭과 같은 카드(1년 선 그래프 · 하루 경로 · 가격 카드 · 증시 분위기 · 기술지표 · 상태 카드) — 계산 · 카드는 정식 종목 것 그대로.
  구성   = `무엇을 담고 있나?` 상위 10 보유 종목(비중 막대) + 업종 비중. 미국 ETF = 야후 펀드 자료.
           한국 상장 ETF 가 미국 지수를 따라가면 같은 지수의 미국 ETF 구성을 출처와 함께(etf_universe 의 `같은 지수`), 한국 지수 ETF 는 공공데이터포털
           증권상품시세정보(활용 신청 필요) 전까지 탭 생략 — 빈 답 금지(판단 유보 규칙).
  기본 정보 = 따라가는 것 · 운용사 · 1년 보수 · 순자산 · 상장일 · 분배금 수익률(있는 것만).
  빼는 것 = 매수의견 · 실적 · 뉴스 · 방송 · 소송 · 옵션 · 기업 (ETF 는 회사가 아니다 · AI 0).
  함께 보는 페이지 = 같은 것을 따라가는 다른 ETF(미국 · 한국 상장 둘 다).
"""

import datetime
import os
import re
import sys

import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [EXP, os.path.join(EXP, "daily-report"), os.path.join(EXP, "stock-quick")]
import design_kit as dk  # noqa: E402
import cards as C  # noqa: E402
import etf_universe as E  # noqa: E402
import mock_quick as Q  # noqa: E402

OUT = os.path.join(HERE, "output")
SAMPLES = ["SOXX", "SPY", "381180.KS", "069500.KS"]
SECTOR_KO = {"technology": "정보기술", "financial_services": "금융", "healthcare": "헬스케어", "consumer_cyclical": "경기 소비재", "communication_services": "커뮤니케이션",
             "industrials": "산업재", "consumer_defensive": "필수 소비재", "energy": "에너지", "utilities": "유틸리티", "realestate": "부동산", "basic_materials": "소재"}
FAMILY_KO = {"iShares": "아이셰어즈(블랙록)", "State": "스테이트 스트리트", "Vanguard": "뱅가드", "Invesco": "인베스코", "Schwab": "찰스 슈왑", "JPMorgan": "JP모건",
             "VanEck": "반에크", "Direxion": "디렉시온", "ProShares": "프로셰어즈", "ARK": "아크 인베스트", "SPDR": "스테이트 스트리트"}
NAME_KO = {"NVDA": "엔비디아", "AMD": "AMD", "MU": "마이크론", "AVGO": "브로드컴", "INTC": "인텔", "QCOM": "퀄컴", "TXN": "텍사스 인스트루먼트", "AMAT": "어플라이드 머티리얼즈",
           "LRCX": "램리서치", "KLAC": "KLA", "ADI": "아날로그 디바이스", "MRVL": "마벨", "TSM": "TSMC", "ASML": "ASML", "MCHP": "마이크로칩", "NXPI": "NXP", "ON": "온세미",
           "AAPL": "애플", "MSFT": "마이크로소프트", "AMZN": "아마존", "GOOGL": "알파벳 A", "GOOG": "알파벳 C", "META": "메타", "TSLA": "테슬라", "BRK-B": "버크셔 해서웨이",
           "BRK.B": "버크셔 해서웨이", "JPM": "JP모건", "LLY": "일라이 릴리", "V": "비자", "MPWR": "모놀리식 파워", "COHR": "코히런트", "TER": "테라다인"}


def info(sym):
    by = {t[0]: t for t in E.US + E.KR}[sym]
    return {"sym": sym, "name": by[1], "tracks": by[2], "market": "KR" if sym.endswith(".KS") else "US"}


def fund(sym):
    """야후 펀드 자료 — 미국 ETF 만 나온다. 실제는 주 1회(구성은 자주 안 바뀐다)."""
    t = yf.Ticker(sym)
    i = t.info or {}
    out = {"family": i.get("fundFamily"), "fee": i.get("netExpenseRatio"), "aum": i.get("totalAssets"), "yield": i.get("yield"),
           "since": datetime.date.fromtimestamp(i["fundInceptionDate"]).isoformat() if i.get("fundInceptionDate") else None, "top": [], "sectors": []}
    try:
        fd = t.funds_data
        th = fd.top_holdings
        out["top"] = [(k, v["Name"], float(v["Holding Percent"]) * 100) for k, v in th.head(10).iterrows()]
        out["sectors"] = sorted(((SECTOR_KO.get(k, k), v * 100) for k, v in (fd.sector_weightings or {}).items() if v and v >= 0.01), key=lambda x: -x[1])[:5]
    except Exception as e:  # noqa: BLE001
        print(f"[etf] {sym} 구성 없음: {str(e)[:60]}")
    return out


def weight_rows(items):
    """비중 줄 — 이름 · 막대 · %. 막대 길이 = 그 표 안 최대 비중 대비."""
    mx = max(w for _, w in items) or 1
    rows = []
    for name, w in items:
        bar = dk.hbar(w, mx, dk.CHART_MAIN, "72px")   # 줄 막대 = dk.hbar(10 · 모서리 3 · 바탕 #F1F5F9), 비중 = 주인공 크기 주황 (2026-11-14 그래프 통일, 옛 8 · 4 · 회색)
        rows.append((name, f'{bar}<span style="font-variant-numeric:tabular-nums;">{w:.1f}%</span>', ""))
    return dk.ccard(rows).replace('data-cards="1" ', "")


def tab_holdings(f, src_note=""):
    if not f["top"]:
        return ""
    names = [(dk.esc(NAME_KO.get(s, n)) + (f' <span style="font-size:14px;color:#6B7280;">{dk.esc(s)}</span>' if NAME_KO.get(s, n) != s else ""), w) for s, n, w in f["top"]]
    top_sum = sum(w for _, w in names)
    out = dk.section("무엇을 담고 있나?", weight_rows(names)
                     + dk.muted(f"상위 10종목이 전체의 {top_sum:.0f}%입니다." + (" " + src_note if src_note else "")))
    if f["sectors"] and f["sectors"][0][1] < 99:
        out += dk.section("업종 비중은?", weight_rows(f["sectors"]))
    return out


def tab_basic(meta, f):
    rows = [("따라가는 것", dk.esc(meta["tracks"]), "")]
    if f.get("family"):
        rows.append(("운용사", dk.esc(FAMILY_KO.get(f["family"].split(" ")[0], f["family"])), ""))
    if f.get("fee") is not None:
        rows.append(("1년 보수", f'{f["fee"]:.2f}%', ""))
    if f.get("aum"):
        rows.append(("순자산", _big_usd(f["aum"]), ""))
    if f.get("since"):
        rows.append(("상장일", f["since"].replace("-", ". ") + ".", ""))
    if f.get("yield"):
        rows.append(("분배금 수익률(1년)", f'{f["yield"] * 100:.2f}%', ""))
    return dk.section("어떤 ETF 인가?", dk.ccard(rows).replace('data-cards="1" ', ""))


def _big_usd(v):
    return f"{v / 1e12:.2f}조 달러" if v >= 1e12 else f"{v / 1e8:,.0f}억 달러"


def same_index(meta):
    """같은 것을 따라가는 다른 ETF — 함께 보는 페이지 버튼."""
    return [(f"{t[1]} {t[0].split('.')[0]}", f"mock_etf_{t[0].split('.')[0]}.html") for t in E.US + E.KR if t[2] == meta["tracks"] and t[0] != meta["sym"]]


def us_page(meta):
    """미국 ETF — 정식 종목 계산 · 카드(mock_quick.page_us_full 와 같은 길), 탭만 ETF 용."""
    sys.path.insert(0, os.path.join(EXP, "stock-radar"))
    import universe as U
    sym = meta["sym"]
    if sym not in U.BY_SYM:
        U.CANDIDATES.append((sym, meta["name"], f"{sym.lower()}-etf", "반도체" if "반도체" in meta["tracks"] else "기술"))
        U.BY_SYM[sym] = U.CANDIDATES[-1]
        if "반도체" not in meta["tracks"]:
            U.SECTOR_OVERRIDE[sym] = (U.BENCH, "S&P 500")   # 업종 대비 = 넓은 지수 ETF 는 시장 그 자체와
    import collect
    import analyze
    import render_pages as RP
    syms = sorted({sym, U.BENCH, "^VIX", "SMH", *collect.SECTOR_ETFS})
    bars = collect._bars(syms)
    snap = {"fetched_at": "", "bars": bars, "caps": {sym: None}, "earnings": {sym: []}, "history": Q.history_stats([sym, U.BENCH])}
    s = analyze.stock(sym, snap)
    b = s.pop("_bars")
    s["tech"] = analyze.technical(b, snap, sym)
    s["market_regime"], s["market_shock"] = analyze.market_regime(snap), analyze.market_shock(snap)
    s["sector_flow"], s["bollinger"] = None, analyze.bollinger(b)
    s["overheat"], s["drawdown"] = analyze.overheat(b, s["tech"]), analyze.drawdown(b, s["year_range"], snap, sym)
    s.update(peer_moves=[], in_top=False, rank=None, industry_us=None, mom_12_1=None)
    R = RP.R
    days = [x["day"] for x in b][-252:]
    c = [x["close"] for x in b][-252:]
    bmap = {x["day"]: x["close"] for x in bars[U.BENCH]}
    bc = [bmap.get(d) for d in days]
    bc = [x if x is not None else next(y for y in bc if y is not None) for x in bc]
    series = [(meta["name"], [(x / c[0] - 1) * 100 for x in c], dk.CHART_MAIN, "solid"),   # 그래프 색 = 주인공 주황 (2026-11-14 그래프 통일, 옛 오름 · 내림 색)
              ("S&P 500", [(x / bc[0] - 1) * 100 for x in bc], dk.CHART_CMP, "dash")]
    line = dk.trend_card("1년 전 대비 등락", dk.month_ticks(days), series, Q.pct)
    tab_today = (line + R.day_path_chart(s["tech"].get("path"), s["tech"].get("bench_path"), meta["name"], "S&P 500")
                 + RP.price_card(s, s["day"]) + RP.sec_regime(s) + RP.sec_tech(s) + RP.sec_states(s))
    f = fund(sym)
    hold = tab_holdings(f)
    body = (dk.price_stamp(s["day"], "US") + RP.lead(s)
            + R._section("오늘", tab_today, line=False, tab="오늘")
            + (R._section("구성", hold, tab="구성") if hold else "")
            + R._section("기본 정보", tab_basic(meta, f), tab="기본 정보")
            + dk.related_buttons(same_index(meta)))
    return RP.wrap(body)


def kr_page(meta):
    """한국 상장 ETF — 한국 정식 종목 계산 · 카드(mock_quick.page_kr_full), 오늘 탭만 남기고 구성 · 기본 정보 탭을 붙인다."""
    sym, code = meta["sym"], meta["sym"].split(".")[0]
    sys.path.insert(0, os.path.join(EXP, "kr-stocks"))
    import render_kr
    mom = render_kr.sec_momentum
    render_kr.sec_momentum = lambda x: "" if x.get("sym") == sym else mom(x)   # 12개월 모멘텀 = 우리 종목 안 순위 — ETF 는 순위에 넣지 않는다
    body, _ = Q.page_kr_full({"sym": sym, "name": meta["name"], "slug": code, "kr_sector": "ETF", "kr_etf": "091160.KS" if "반도체" in meta["tracks"] else "266370.KS"})
    # 오늘 탭 뒤 탭(매수의견 · 실적 · 업계상황 · 뉴스 · 기업 …)은 회사 자료라 뺀다 — 오늘 탭 끝까지만
    m = re.search(r'<h2[^>]*data-tab="[^"]*"[^>]*>', body)
    tabs = [x for x in re.finditer(r'<h2[^>]*data-tab="([^"]*)"', body)]
    if len(tabs) >= 2:
        body = body[:tabs[1].start()]
    elif m is None:
        print("[etf] 한국 탭 머리를 못 찾음 — 전체를 둔다")
    us_twin = next((t for t in E.US if t[2] == meta["tracks"]), None)
    f = {"top": [], "sectors": []}
    note = ""
    if us_twin and "미국" in meta["name"]:
        f = fund(us_twin[0])
        note = f"같은 지수를 따라가는 미국 상장 {us_twin[0]} 기준입니다."
        f.update(family=None, fee=None, aum=None, since=None, **{"yield": None})
    meta["family"] = meta["name"].split(" ")[0]
    hold = tab_holdings(f, note)
    basic_rows = {"family": {"KODEX": "삼성자산운용", "TIGER": "미래에셋자산운용", "ACE": "한국투자신탁운용"}.get(meta["family"])}
    body += ((render_kr.R._section("구성", hold, tab="구성") if hold else "")
             + render_kr.R._section("기본 정보", tab_basic(meta, {**f, **basic_rows}), tab="기본 정보")
             + dk.related_buttons(same_index(meta)) + "</div>")
    return body


def main():
    Q._no_media_opinions()
    os.makedirs(OUT, exist_ok=True)
    for sym in SAMPLES:
        meta = info(sym)
        body = us_page(meta) if meta["market"] == "US" else kr_page(meta)
        p = dk.write_mock(body, os.path.join(OUT, f"mock_etf_{sym.split('.')[0]}.html"), f'{meta["name"]} {sym.split(".")[0]} 주가')
        print("만듦:", p)


if __name__ == "__main__":
    main()
