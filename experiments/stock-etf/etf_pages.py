"""ETF 고정 페이지 본문 — A안. 목업 = mock_etf.py 와 같은 화면.

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

SHOWN = 5   # 구성 줄 — 5개 펼침 + 나머지 `종목 n개 더 보기`


def _hold_sym(code):
    """구성 줄의 종목 코드 → 우리 키. 한국 6자리 = 로고 · 페이지 목록에서 .KS / .KQ 를 찾는다, 미국 = 티커 그대로."""
    c = str(code or "").strip().upper()
    if c.isdigit() and len(c) == 6:
        known = dk._logo_files()
        pages = dk.stock_pages()
        return next((c + x for x in (".KS", ".KQ") if c + x in known or c + x in pages), c + ".KS")
    return c.replace(".", "-")


def _hold_name(sym, raw):
    """이름 — 한국 종목은 운용사 표기 그대로, 미국 종목은 한글 이름이 있으면 그것, 없으면 티커(긴 영문 회사명은 막대를 밀어낸다)."""
    if sym.endswith((".KS", ".KQ")):
        return raw
    return NAME_KO.get(sym) or (sym if re.fullmatch(r"[A-Z][A-Z\-]{0,5}", sym) else raw)


ROW_GAP = 20   # 구성 줄 사이 보이는 여백 — 구분선 없이
BAR_H = 8      # 구성 막대 두께 10 → 8
VAL_PX = 15    # 구성 비중 % 글자 19 → 17 → 16 → 15 굵게
NAME_PX = 15   # 구성 종목 이름 15 굵게
BAR_FRAC = 0.7   # 막대 = 막대 칸의 70%
NAME_MAX = 200   # 이름 칸 최대 px — 이름은 자르지 않는다(가장 긴 한국 종목 이름 10자 ≈ 160 + 로고 28). 넘는 이름(긴 영문)만 끝 말줄임


def _text_px(t, latin=9, wide=16):
    """15px 굵은 글자 폭 추정 — 한글 16, 그 밖 9 (16px 보통 실측 10자 ≈ 136 → 15px 굵게 약 150, 2026-11-16)."""
    return sum(wide if ord(ch) > 0x2E80 else latin for ch in str(t)) + 2


def weight_card(items):
    """비중 막대 카드 — 이름 앞 로고(dk.name_logo) · 막대(가장 긴 이름 + 14 뒤에서 시작, 모두 같은 길이, dk.bar_row) · 비중 %.
    items = [(우리 키, 이름, 비중)]. 막대 길이 = 이 카드 안 최대 비중 대비, 색 = 부호 없는 크기 주황(가이드라인 9절).
    줄 전체 = 그 종목 페이지(있을 때, 가이드라인 10-9). 5개 펼침 + 나머지 카드 안 접기."""
    if not items:
        return ""
    mx = max(w for _, _, w in items) or 1

    def nm(sym, name):
        logo = dk.name_logo(sym, name, 20) if sym else ""
        return f'<span style="display:inline-flex;align-items:center;">{logo}{dk.esc(name)}</span>'
    vals = [f"{w:.1f}%" for _, _, w in items]
    # 칸 폭 = 숫자(px) — 줄마다 모든 이름을 숨겨 겹치는 dk.bar_widths 는 줄 수의 제곱(503줄 = 본문 1.2MB)이라. 이름 = 로고 28 + 글자 폭 추정, 최대 NAME_MAX
    widths = (min(NAME_MAX, (28 if any(sy for sy, _, _ in items) else 0) + max(_text_px(n) for _, n, _ in items)), max(_text_px(v, 10) for v in vals))
    widths = (widths[0], widths[1] * VAL_PX // 19)   # 값 글자 19 → 15 만큼 칸도
    rows = []
    for i, ((sym, name, w), v) in enumerate(zip(items, vals)):
        row = dk.bar_row(nm(sym, name), w / mx, dk.CHART_MAIN, v, widths, first=i == 0, sep=False, bar_h=BAR_H, val_px=VAL_PX, pad=ROW_GAP // 2, lh="20px", name_w=700, name_px=NAME_PX, bar_frac=BAR_FRAC, val_gap=5)
        rows.append(dk.stock_row_link(row, sym))
    box = dk.MULTI + f"padding-top:{ROW_GAP // 2}px;"   # 카드 가장자리 ~ 첫 줄 = 줄 사이 반쪽 + 위 여백 → 보이는 20
    if len(rows) <= SHOWN:
        return f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{box}padding-bottom:{ROW_GAP // 2}px;">{"".join(rows)}</span></div>'
    out = dk.fold_card("".join(rows[:SHOWN]), "".join(rows[SHOWN:]), f"종목 {len(rows) - SHOWN}개 더 보기", box=box)
    return out.replace('<span data-grid="2" style="display:block;border-top:1px solid #E2E8F0;">', '<span data-grid="2" style="display:block;">', 1)   # 펼친 줄 위 구분선도 없음 (버튼 위 선만)


def tab_holdings(f, src_note="", link=None, name="", at_note=""):
    """구성 탭 — 기업 탭과 같은 틀: 탭 맨 위 문장(dk.TAB_LEAD_GAP) · 비중 막대 카드 · 출처 안내 줄.
    한국 ETF = 운용사 구성 전부(n종목), 미국 ETF = 야후가 주는 상위 10종목뿐(그 밖은 야후에 없다 — 외부 한도).
    link = (글자, 주소) — src_note 안의 `@링크@` 자리를 출처 링크로. 구획 제목마다 data-tab (테마는 표시 없는 h2 를 첫 탭으로 옮긴다)."""
    if not f or not f.get("top"):
        return ""
    items = []
    for code, raw, w in f["top"]:
        sym = _hold_sym(code)
        items.append((sym, _hold_name(sym, raw), float(w)))
    n_all = f.get("n") or 0
    whole = n_all and len(items) >= n_all   # 전체 목록을 받았나 (한국 운용사 자료)
    k = min(SHOWN, len(items))
    top_k = sum(w for *_, w in items[:k])
    who = dk.josa(name, "은") if name else "이 ETF 는"
    if whole:
        lead = f"{who} {n_all}종목을 담고 있습니다. 비중이 큰 {k}종목이 전체의 {top_k:.0f}%입니다."
    else:
        top10 = sum(w for *_, w in items)
        lead = f"{who} 비중이 큰 {len(items)}종목에 전체의 {top10:.0f}%를 담고 있습니다."
    note = dk.muted(src_note) if src_note else ""
    if link and note:   # 운용사 출처 = 카드 아래 오른쪽 정렬
        note = note.replace("@링크@", f'<a href="{dk.esc(link[1])}" style="color:inherit;text-decoration:underline;" target="_blank" rel="nofollow noopener">{dk.esc(link[0])}</a>')
        note = note.replace(dk.GUIDE_IND, "text-align:right;", 1).replace(dk.INFO_ICON, "", 1)   # 아이콘 없이
    lead_html = f'<p style="{dk.TAB_LEAD_GAP}color:#111;line-height:33px;word-break:keep-all;">{dk.esc(lead)}</p>'
    if at_note:   # 기준일 = 카드 오른쪽 위 작은 회색 — 문장 → 카드 27 은 그대로(문장 아래 8 + 기준일 19 + 0)
        lead_html = (lead_html.replace(dk.TAB_LEAD_GAP, dk.TAB_LEAD_GAP.replace(" 27px;", " 8px;"), 1)
                     + f'<div style="text-align:right;color:{dk.NOTE};font-size:13px;line-height:19px;margin:0 0 6px;">{dk.esc(at_note)}</div>')
    out = lead_html + weight_card(items) + note
    if f.get("sectors") and f["sectors"][0][1] < 99:
        out += dk.section("업종 비중은?", weight_card([("", n, w) for n, w in f["sectors"]]), tab="구성")
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


INFO_NAME_W = 98   # 기본 정보 이름 칸 — `따라가는 지수`(7자, 14px) 한 줄. 기업 탭 _info_rows 는 68(4자 이름)


def info_rows(rows):
    """이름 · 값 줄 묶음(흰 카드) — 기업 탭 기본 정보(render_kr._info_rows · render_pages.sec_company)와 같은 모양: 구분선 없이 14/22, 이름 회색 · 값 검정."""
    out = "".join(f'<span style="display:flex;gap:12px;padding:3px 12px;font-size:{dk.TINY};line-height:22px;">'
                  f'<span style="flex:0 0 {INFO_NAME_W}px;color:{dk.NOTE};white-space:nowrap;">{dk.esc(k)}</span>'
                  f'<span style="flex:1 1 auto;min-width:0;color:#111;word-break:keep-all;overflow-wrap:anywhere;">{v}</span></span>' for k, v in rows if v)
    pad = dk.SEP_GAP - dk.VP - 1 - 3
    return f'<div data-cards="1" style="margin:0 0 8px;"><span style="{dk.MULTI}padding:{pad}px 0;display:block;">{out}</span></div>'


def tab_basic(sym, f, bars=None):
    """기본 정보 탭 — 기업 탭과 같은 틀: 탭 맨 위 소개 문장(따라가는 지수 + 풀이) · 흰 카드 이름 · 값 줄.
    옛 `어떤 ETF 인가?` 제목 · 줄 카드 · 맨 아래 풀이 안내 줄 → 소개 문장으로."""
    f = f or {}
    name, idx = E.BY_SYM[sym][1], E.BY_SYM[sym][2]
    why = E.EXPLAIN.get(idx, "")
    if idx == "운용사 직접 운용":
        lead = f"{dk.josa(name, '은')} 정해진 지수 없이 운용사가 종목을 고릅니다."
    else:
        lead = f"{dk.josa(name, '은')} {dk.josa(idx, '을')} 따라갑니다." + (f" {why}" if why else "")
    kr = sym.endswith(".KS")
    fam = f.get("family")
    tv = trade_value(bars) if bars else None
    sub = lambda t: f'<span style="display:block;color:{dk.NOTE};">{dk.esc(t)}</span>'   # noqa: E731 — 값 아래 회색 한 줄 (기업 탭 국민연금 줄과 같은 꼴)
    rows = [("따라가는 지수", dk.esc(idx) if idx != "운용사 직접 운용" else "없음 (운용사가 직접 고름)"),
            ("운용사", dk.esc(FAMILY_KO.get(fam.split(" ")[0], fam)) if fam else ""),
            ("1년 보수", fee_text(f["fee"]) if f.get("fee") is not None else ""),
            ("순자산", _big_usd(f["aum"]) if f.get("aum") else _big_krw(f["aum_krw"]) if f.get("aum_krw") else ""),
            ("담은 종목", f"{f['n']:,}종목" if f.get("n") else ""),
            ("하루 거래대금", ((_big_krw(tv) if kr else _big_usd(tv)) + sub("최근 20거래일 평균")) if tv else ""),   # 사고팔기 쉬운가 (2026-11-13 P549) — 이미 받은 일봉만
            ("분배금 수익률", f'{f["yield"] * 100:.2f}%' + sub("최근 1년") if f.get("yield") else ""),
            ("상장일", f["since"].replace("-", ". ") + "." if f.get("since") else ""),
            ("상장", f"코스피 · 종목 코드 {E.key(sym)}" if kr else f"티커 {sym}")]
    src = f.get("source")
    note = dk.muted(f"보수 · 순자산 · 담은 종목은 {src} 자료입니다.") if src else ""
    return f'<p style="{dk.TAB_LEAD_GAP}color:#111;line-height:33px;word-break:keep-all;">{dk.esc(lead)}</p>' + info_rows(rows) + note


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
        nm = dk.esc(name) + (f' <span style="font-weight:400;font-size:14px;color:{dk.NOTE};">(이 ETF)</span>' if p == sym else "")
        sub = " · ".join(bits) + (f" · 따라가는 지수 {dk.esc(E.BY_SYM[p][2])}" if E.BY_SYM[p][2] != E.BY_SYM[sym][2] else "")
        val = _R()._arrow(r1, 1)   # 1년 수익률 — 기간은 제목 괄호에, 증감 = ▲▼ + 색 (가이드라인 5절)
        rows.append((nm, val, f'<span style="font-size:14px;color:{dk.NOTE};">{sub}</span>' if sub else "", p))
    if len(rows) < 2:
        return ""
    short = dk.short_values([r[:3] for r in rows])
    parts = []
    for i, (nm, val, sub, p) in enumerate(rows):
        row = dk.crow(nm, val, sub, first=i == 0, short=short)
        if p != sym:   # 다른 ETF 줄 전체 = 그 ETF 페이지 (가이드라인 10-9) — 이 ETF 줄은 링크 없이
            row = row.replace("<span ", f'<span data-row-link="1" data-href="{dk.esc(E.page_url(p))}" ', 1)
        parts.append(row)
    card = f'<div style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{"".join(parts)}</span></div>'
    # 제목 = 그래프 제목 꼴 ※ (구획 h2 · 밑줄 없이), 구성 탭 안
    title = (f'<div style="margin:28px 0 {dk.CHART_TITLE_GAP}px;padding-left:{dk.ALIGN_PX}px;">{dk.CHART_TITLE}비슷한 ETF와 비교하면? '
             f'<span style="font-weight:400;font-size:{dk.TINY};color:{dk.NOTE};">(1년 수익률)</span></span></div>')
    return title + card + dk.muted("같은 것을 담는 한국 상장 ETF 입니다. 1년 수익률은 분배금을 빼고 계산했습니다.").replace(dk.INFO_ICON, "", 1)   # 아이콘 없이


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


def _R():
    sys.path.insert(0, os.path.join(EXP, "nvda-report"))
    import render_html as R
    return R


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
    return dk.trend_card("1년 수익률", dk.month_ticks(days), series, pct)


E_MOCK, E_REAL = ("<!--etf-mock-->", "<!--/etf-mock-->"), ("<!--etf-real-->", "<!--/etf-real-->")
MOCK_AVG = 0.97   # 목업에만 보이는 `내 평단 (예시)` = 마지막 종가의 97% — 실제 페이지엔 없다(회원 본인 화면에서만 브라우저가 그린다, 회원 기능 때)


def candle(name, bars, dec, kr_code=None):
    """맨 위 = 봉차트(일 · 주 · 월 · 넘겨보기 · 확대 · 전체 화면 지표) — 옛 `1년 전 대비 등락` 선 그래프 자리. 1년 비교는 `기간별 수익률` 막대에 있다."""
    real = CC.card(name, bars, dec, title="")   # 제목 없음
    if not real:
        return ""
    last = bars[-1]["close"]
    mock = CC.card(name, bars, dec, avg={"price": round(last * MOCK_AVG, dec), "label": "내 평단"}, title="")
    gap = '<div style="height:20px;"></div>'   # 차트와 탭 사이 20 더
    return E_MOCK[0] + mock + CC.kr_live(kr_code, always=True) + gap + E_MOCK[1] + E_REAL[0] + real + CC.kr_live(kr_code) + gap + E_REAL[1] + CC.SCRIPT   # 한국 ETF = 장중 네이버 링크   # ETF 전용 표시 — 한국 ETF 본문은 render_kr 를 거치며 mock-only 를 먼저 지운다


def load_live(market):
    try:
        with open(live_path(market), encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return set()


# ── 미국 ──

US_SECTOR = {"XLK": ("XLK", "기술")}   # 업종 ETF 자신 = 그 업종 자금 흐름 (반도체 ETF 는 universe 업종 `반도체` = SMH)
US_BASE = {"SOXL": "SOXX", "TQQQ": "QQQ", "SQQQ": "QQQ"}   # 레버리지 · 인버스 → 같은 지수 1배 ETF
TOP_MIN = 3.0   # 비중 1위가 이보다 작으면(러셀 2000 · 프리미엄 인컴) 그 종목 하나가 ETF 를 말하지 않는다


def us_move_card(sym, snap, f, s):
    """미국 ETF `함께 움직이는 종목은?`.
    비교 = 레버리지 · 인버스면 같은 지수 1배 ETF, 아니면 담은 비중 1위 종목(TOP_MIN% 이상, 일봉이 있을 때). 없으면(채권 · 금 · 고르게 담은 ETF) 카드 없음."""
    peer = None
    if sym in US_BASE:
        peer = (US_BASE[sym], E.BY_SYM[US_BASE[sym]][1])
    else:
        for tk, nm, w in f.get("top") or []:
            tk = str(tk).replace(".", "-")
            if w >= TOP_MIN and len(snap["bars"].get(tk) or []) >= 20:
                peer = (tk, NAME_KO.get(tk, nm))
            break
    b = (snap["bars"].get(sym) or [])[-MOVE_DAYS:]
    if not peer or len(b) < 20:
        return ""
    days = [x["day"] for x in b]
    m = {x["day"]: x["close"] for x in snap["bars"].get(peer[0]) or []}

    def norm(vals):
        first = next((v for v in vals if v is not None), None)
        return [None if v is None else (v / first - 1) * 100 for v in vals] if first else None
    pv = norm([m.get(d) for d in days])
    if not pv or sum(x is not None for x in pv) < 20:
        return ""
    name = E.BY_SYM[sym][1]
    series = [(name, norm([x["close"] for x in b]), dk.CHART_MAIN, "solid"), (peer[1], pv, dk.CHART_SERIES[1], "thin")]
    chart = dk.trend_card("최근 3개월 수익률 (%)", dk.month_ticks(days, every=1), series, pct)
    pb = snap["bars"].get(peer[0]) or []
    peer_ret = (pb[-1]["close"] / pb[-2]["close"] - 1) * 100 if len(pb) >= 2 and pb[-1]["day"] == days[-1] and pb[-2]["close"] else None
    if peer_ret is None:
        return ""
    state, theme = ("올랐음", "positive") if peer_ret >= 0.5 else ("내렸음", "negative") if peer_ret <= -0.5 else ("비슷함", "neutral")
    when = dk.kst_close_day(days[-1], "US") + " 새벽"   # 독자 = 한국 시간 (2026-11-14 날짜 규칙)
    who = "같은 지수를 1배로 따라가는 " + peer[1] if sym in US_BASE else f"가장 많이 담은 {peer[1]}"
    sent = f"{when} {dk.josa(who, '은')} {_sgn(peer_ret)}%였고, {dk.josa(name, '은')} {_sgn(s['ret_1d'])}%였습니다."
    sys.path.insert(0, os.path.join(EXP, "nvda-report"))
    import render_html as R
    col = {"positive": C.UP, "negative": C.DOWN}.get(theme, "#111")
    return R._state_card("함께 움직이는 종목은?", state, theme, col, [(sent, "plain"), (chart, "html")], "", fold=True, opened=True)


def us_pages(snap, live, fund):
    sys.path.insert(0, os.path.join(EXP, "stock-radar"))
    import universe as U
    import analyze
    import industry_us
    import render_pages as RP
    try:
        fred = industry_us.load()   # 미국 종목 실행(main.py)이 같은 날 받아 둔 FRED — 없으면 업계 통계 카드 없이
    except Exception:  # noqa: BLE001
        fred = {}
    R = RP.R
    snap = dict(snap, caps=dict(snap.get("caps") or {}), earnings=dict(snap.get("earnings") or {}))
    pages = {}
    crash = RP.CW.compute(snap["bars"], "us", [t[0] for t in E.US])   # 급락장에서 어땠나? — 종목 페이지와 같은 계산 · 카드
    for sym, name, tracks, _a in E.US:
        b0 = snap["bars"].get(sym) or []
        if len(b0) < 30:
            print(f"[etf] {sym}: 일봉 부족 — 건너뜀")
            continue
        if sym not in U.BY_SYM:   # 정식 계산이 이름 · 업종 칸을 읽는다 — 이 실행 안에서만
            U.CANDIDATES.append((sym, name, E.slug(sym), "반도체" if "반도체" in tracks else "기술"))
            U.BY_SYM[sym] = U.CANDIDATES[-1]
            if sym in US_SECTOR:
                U.SECTOR_OVERRIDE[sym] = US_SECTOR[sym]
            elif "반도체" not in tracks:
                U.SECTOR_OVERRIDE[sym] = (U.BENCH, "S&P 500")   # 넓은 지수 ETF 의 업종 대비 = 시장 그 자체
        if "반도체" in tracks:
            industry_us.SYM_BIZ[sym] = "semi"   # 업계 통계 = 반도체 업계(FRED) — 한국 테마 ETF 의 업계상황 탭과 같게 (2026-11-14)
        snap["caps"].setdefault(sym, None)
        snap["earnings"].setdefault(sym, [])
        try:
            s = analyze.stock(sym, snap)
            b = s.pop("_bars")
            s["tech"] = analyze.technical(b, snap, sym)
            s["market_regime"], s["market_shock"] = analyze.market_regime(snap), analyze.market_shock(snap)
            industry = "반도체" in tracks or sym in US_SECTOR   # 업종 하나를 담는 ETF 만 업계상황 탭 (지수형은 업계가 하나가 아니다)
            s["sector_flow"], s["bollinger"] = (analyze.sector_flow(snap, sym) if industry else None), analyze.bollinger(b)
            s["overheat"], s["drawdown"] = analyze.overheat(b, s["tech"]), analyze.drawdown(b, s["year_range"], snap, sym)
            s.update(peer_moves=[], in_top=False, rank=None, industry_us=None, mom_12_1=None, crash=RP.CW.for_stock(crash, sym))
            days = [x["day"] for x in b][-252:]
            f = fund.get(sym) or {}
            s["industry_us"] = industry_us.build(sym, fred) if industry else None
            mv = us_move_card(sym, snap, f, s)
            today = (R.day_path_chart(s["tech"].get("path"), s["tech"].get("bench_path"), name, "S&P 500")
                     + RP.price_card(s, s["day"]) + RP.sec_regime(s) + RP.sec_tech(s)
                     + (f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{mv}</div>' if mv else "") + RP.sec_states(s))
            ind = RP.sec_industry_tab(s) if (s["sector_flow"] or s["industry_us"]) else ""
            hold = tab_holdings(f, name=name)
            body = (dk.price_stamp(s["day"], "US") + RP.lead(s)
                    + candle(name, b0, 2)   # 차트 = 탭 위
                    + R._section("오늘", today, line=False, tab="오늘") + RP.sec_crash(s)
                    + (R._section("업계상황", ind, tab="업계상황") if ind else "")   # 한국 ETF 와 같은 자리 (2026-11-14)
                    + (R._section("구성", hold, tab="구성") if hold else "")
                    + R._section("기본 정보", tab_basic(sym, f, b0), tab="기본 정보")
                    + related(sym, live))
            if sym in E.BY_SYM[sym][1].split():   # `인베스코 QQQ` 처럼 티커가 이름의 일부 — 테마가 제목 티커를 꼬리로 옮기지 않게
                body = '<span data-title-keep-ticker="1" hidden></span>' + body
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
    """강조 카드 답: 종목 페이지 `함께 움직이는 종목은?` 과 같은 뜻 —
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
    """`함께 움직이는 종목은?` — 종목 페이지 같은 이름 카드의 ETF 판.
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
            series.append((peer[1], v, dk.CHART_SERIES[1], "thin"))   # 비교 = 얇은 실선
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
    chart = dk.trend_card("최근 3개월 수익률 (%)", dk.month_ticks(days, every=1), series, pct)
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
    lines = [(sent, "plain"), (chart + (dk.excl_note(note) if note else ""), "html")]   # 안내 = 느낌표 + 작은 회색
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
    crash = render_kr.RP.CW.compute(snap["bars"], "kr", syms)   # 급락장에서 어땠나? — 종목 페이지와 같은 계산 · 카드
    for s in stocks:   # 순위 · 모멘텀 순위 없음 (mom_rank 가 없으면 카드가 빠진다)
        s.update(market_regime=mr, sector_flow=analyze_kr.sector_flow(snap, s["sym"]), fx=market.get("fx"), crash=render_kr.RP.CW.for_stock(crash, s["sym"]),
                 rank=None, in_top=False)
    a = {"day": day, "fetched_at": snap.get("fetched_at"), "stocks": stocks, "market": market, "crash": {}}
    kbench = {x["day"]: x["close"] for x in snap["bars"].get(K.BENCH) or []}

    def chart(s):   # 봉차트 그림 자리 → 오늘 탭 머리 + 1년 선 그래프 (미국 ETF 와 같게)
        b = snap["bars"][s["sym"]][-252:]
        return candle(s["name"], snap["bars"][s["sym"]], 0, kr_code=s.get("code")) + render_kr.R._section("오늘", "", line=False, tab="오늘")   # 차트 = 탭 위
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
                hold = tab_holdings({"top": kf["top"], "sectors": [], "n": kf.get("n")}, "출처 : @링크@", (kf.get("source") or "운용사", kf.get("url") or ""), E.BY_SYM[sym][1],
                                    at_note=f"{int(at[5:7])}월 {int(at[8:10])}일 기준" if at else "")   # 기준일 = 카드 오른쪽 위, 출처 = 카드 아래 오른쪽
            elif not lev:   # 운용사 자료가 없을 때만 예전 길 — 같은 지수 미국 ETF 구성
                twin = next((t[0] for t in E.US if t[2] == E.BY_SYM[sym][2]), None) if "미국" in E.BY_SYM[sym][1] else None
                f = dict(us_fund.get(twin) or {}) if twin else {}
                hold = tab_holdings(f, f"같은 지수를 따라가는 미국 상장 {twin} 구성입니다.", name=E.BY_SYM[sym][1]) if twin else ""
            ind = (render_kr.card_sector_flow(s) + render_kr.card_industry_mood(s) + render_kr.card_industry_work(s) + render_kr.card_industry_money(s))
            basic = {"family": KR_FAMILY.get(E.BY_SYM[sym][1].split(" ")[0]), "fee": kf.get("fee"), "aum_krw": kf.get("aum_krw"), "since": kf.get("since"), "n": kf.get("n"),
                     "source": kf.get("source") if (kf.get("fee") is not None or kf.get("aum_krw")) else None}
            cmp = compare_card(sym, snap["bars"], kfund)   # 구성 탭 끝, 구성 탭이 없는 ETF(레버리지 · 인버스)는 기본 정보 끝
            body += ((render_kr.R._section("업계상황", f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{ind}</div>', tab="업계상황") if ind else "")
                     + (render_kr.R._section("구성", hold + cmp, tab="구성") if hold else "")
                     + render_kr.R._section("기본 정보", tab_basic(sym, basic, snap["bars"].get(sym)) + ("" if hold else cmp), tab="기본 정보") + related(sym, live) + ("</div>" if cut else ""))   # 잘라낸 본문의 바깥 틀 닫기
            pages[code] = (E.page_title(sym), dk.formal(body))   # 업계상황 · 구성 · 기본 정보 탭은 wrap 뒤에 붙어 합니다체를 안 거쳤다 (2026-11-26 블로그 반말 점검)
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


# ── 종목 목록 페이지의 ETF 구획 ──
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
        logo = dk.ticker_logo(sym) if market == "us" or sym in dk._logo_files() else ""   # 한국 ETF = 운용사 로고 사본이 있을 때만 (2026-11-16, 숫자 코드 배지는 쓰지 않는다)
        left = (f'{logo}<a href="{dk.esc(E.page_url(sym))}" style="color:#111;text-decoration:none;">{dk.esc(E.BY_SYM[sym][1])}</a>'
                f'<span style="display:block;padding-left:{26 if logo else 0}px;font-size:{dk.MICRO};line-height:20px;font-weight:400;color:{dk.NOTE};">'
                f'{dk.esc(E.key(sym))} · {dk.esc(E.BY_SYM[sym][2])}</span>')
        items.append((left, f'{R._arrow(r)}<br><span style="color:{pcol};">{price}</span>', r))   # 증감 위 · 가격 아래
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
