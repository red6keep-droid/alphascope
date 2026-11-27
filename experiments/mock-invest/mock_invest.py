"""모의투자 목업.

    python experiments/mock-invest/mock_invest.py   → output/mock_invest-*.html (목업 서버 `mock-invest` 묶음)

화면:
  mock_invest-start.html    설정 — 모의투자 소개 · 규칙 요약 · `10억 원 받고 시작하기` (아직 안 켠 회원)
  mock_invest-nvda.html     엔비디아 종목 페이지 + 아래 `모의투자` 줄 → 매수 창 열림
  mock_invest-005930.html   삼성전자 종목 페이지 + 매도 창 열림 (증권거래세 · 살 때 적은 이유)
  mock_invest-wallet.html   지갑 — 탭 자산 · 세금 · 기록 · 순위(잠김) · 설정
  mock_invest-ranking.html  순위가 열린 뒤 (참가자 100명 넘음)
값은 전부 예시: 가격 = 검색 색인 종가, 환율 = 11-06 KRW=X, 보유 · 거래 · 별명 = 지어낸 값. 인터넷 · AI 0.
글씨 · 색 · 종목 줄 · 버튼 꼴은 회원 `보유 종목` 목업(my-stocks/mock_my_stocks.py) 것을 그대로 쓴다.
"""
import html
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, EXP)
sys.path.insert(0, os.path.join(EXP, "my-stocks"))
import design_kit as dk  # noqa: E402
import mock_my_stocks as MS  # noqa: E402

OUT = os.path.join(HERE, "output")
esc = lambda t: html.escape(str(t), quote=False)
FX = 1356.34          # 원 · 달러 (예시, 11-06 KRW=X)
START = 1_000_000_000  # 처음 10억 원
FEE = {"us": 0.0025, "kr": 0.00015}   # 매매 수수료 = 키움증권 영웅문S# 기본(이벤트 없음): 국내 0.015%(KRX, 유관기관 포함) · 미국 온라인 0.25% (2026-11-21 키움 공식 페이지 확인, 기획 2-2)
TAX_KR_SELL = 0.002   # 증권거래세 2026 = 0.20%
FX_COST = 0.01        # 환전 비용 = 키움 환율 우대 없을 때 매매기준율 ± 1%
LOCK = {"us": 1.1, "kr": 1.3}   # 주문 가능 금액 묶기 = 마지막 종가 × (미국 +10% · 한국 상한가 +30%)
FILL = {"us": "11월 24일(화) 아침 6시, 미국 장 마감 종가로 체결됩니다.",
        "kr": "11월 23일(월) 오후 3시 30분, 장 마감 종가로 체결됩니다."}
FILL_SHORT = {"us": "11월 24일(화) 아침 체결", "kr": "11월 23일(월) 오후 체결"}
DISCLAIM = "가상의 돈입니다. 실제 거래 · 현금 바꾸기 · 상금은 없으며, 세금은 실제 신고와 다를 수 있습니다."

# 예시 지갑 (수량, 평균 매수가, 산 날, 살 때 적은 이유)
HOLD = {"NVDA": (1000, 182.40, "3월 5일", "데이터센터 매출이 두 분기 연속 예상을 넘었고, 다음 분기 안내도 올렸다."),
        "MSFT": (200, 0.93, "4월 22일", "클라우드 성장률이 다시 빨라지는지 보려고 일부만 샀다."),
        "005930.KS": (800, 168000, "3월 11일", "메모리 가격이 바닥을 지났다는 증권사 보고서가 이어졌다."),
        "000660.KS": (120, 1.08, "9월 2일", "HBM 공급 계약 뉴스 뒤 조정 받을 때 나눠 사기로 했다.")}   # 1 미만 · 1.x 값 = 지금 종가 × 배수(예시 손익을 만들려고)
CASH_KRW, CASH_USD = 0, 61_250.00   # 원화 = load() 가 총자산이 처음 대비 −2.4%(자산 흐름 그래프 마지막 값)가 되게 채운다
PENDING = [("NVDA", "매수", 500), ("005930.KS", "매도", 300)]


def load():
    st = MS.load()
    held = []
    for k, (q, a, day, why) in HOLD.items():
        s = st[k]
        if a < 5:
            a = round(s["p"]["c"] * a, 2 if s["m"] == "us" else -2)
        held.append((s, q, a, day, why))
    global CASH_KRW
    stock = sum(krw(s, q * s["p"]["c"]) for s, q, *_ in held)
    CASH_KRW = round(START * (1 - 0.024) - stock - CASH_USD * FX, -4)
    return st, held


def krw(s, v):
    return v * FX if s["m"] == "us" else v


def wonfmt(v):
    return f"{abs(v):,.0f}원"


def usd(v):
    return f"${abs(v):,.2f}"


def pctv(v):
    return f"{abs(v):.1f}%"


def day_label(s):
    """종가 날짜 = 한국 시간 하나 (미국 종가 = 다음 날 새벽, 운영 규칙 · 종목 페이지 머리와 같게)."""
    import datetime as _dt
    d = _dt.date.fromisoformat(s["p"]["d"])
    if s["m"] == "us":
        d += _dt.timedelta(days=1)
        return f"{d.month}월 {d.day}일 새벽 종가"
    return f"{d.month}월 {d.day}일 종가"


# ─────────────────────────── 지갑 ───────────────────────────

def totals(held):
    stock = sum(krw(s, q * s["p"]["c"]) for s, q, *_ in held)
    total = stock + CASH_KRW + CASH_USD * FX
    return stock, total


def wallet_head(held):
    """맨 위 = 총자산 · 처음 10억 대비 · 같은 기간 시장 (보유 종목 grand_card 와 같은 꼴)."""
    stock, total = totals(held)
    gain = total - START
    kind = "positive" if gain > 0 else "negative" if gain < 0 else "neutral"
    ROW = "display:flex;justify-content:space-between;align-items:baseline;gap:12px;"
    FS = 15
    GRID = f"display:grid;grid-template-columns:auto 1fr auto auto;column-gap:10px;align-items:baseline;font-size:{FS}px;line-height:22px;color:#333;"
    RULE = '<span aria-hidden="true" style="grid-column:1/-1;height:1px;background:#FEE6CA;margin:8px 0;"></span>'

    def cells(label, amount_html, rate_html=""):
        return (f'<span style="white-space:nowrap;font-size:{dk.TINY};color:{dk.NOTE};">{label}</span><span></span>'
                f'<span style="white-space:nowrap;text-align:right;">{rate_html}</span><span style="white-space:nowrap;text-align:right;">{amount_html}</span>')
    mkt = -6.8   # 같은 기간 시장(코스피 · S&P 500 반반, 예시)
    top = (f'<div style="{ROW}"><span style="font-size:17px;line-height:24px;font-weight:700;color:#111;white-space:nowrap;">총자산</span>'
           f'<span style="font-size:21px;line-height:28px;font-weight:800;color:#111;white-space:nowrap;">{MS.won_html(total, 21)}</span></div>')
    grid = [f'<span style="grid-column:1/-1;text-align:right;white-space:nowrap;font-size:{dk.TINY};color:{dk.NOTE};">처음 {MS.won_html(START, 14)} · 1회차 3월 2일 시작</span>',
            cells("수익 금액", MS.updown(gain, MS.won_html(gain, FS), FS, tri=False), MS.updown(gain, pctv(gain / START * 100), FS)),
            RULE,
            cells("같은 기간 시장", "", MS.updown(mkt, pctv(mkt), FS)),
            cells("시장 대비", "", MS.updown(gain / START * 100 - mkt, f"{abs(gain / START * 100 - mkt):.1f}%p", FS))]
    return dk.dcard(top + f'<div style="{GRID}margin:6px 0 0;">{"".join(grid)}</div>', kind)


def cash_card():
    lock = 500 * 154.83 * LOCK["us"]
    rows = [("원화", MS.won_html(CASH_KRW, 16), "주문 가능"),
            ("달러", f'{usd(CASH_USD)}', f"원화로 약 {wonfmt(CASH_USD * FX)}"),
            ("주문에 묶인 돈", f'{usd(lock)}', "체결 대기 주문 · 체결 뒤 남는 돈은 풀림")]
    out = "".join(dk.crow(esc(n), v, esc(sub), first=(i == 0), nowrap=True) for i, (n, v, sub) in enumerate(rows))
    btn = (f'<span style="display:block;padding:0 12px 14px;"><a data-mock="1" style="{MS.WHITE_BTN}width:100%;">달러 → 원화 바꾸기</a></span>')
    return f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{out}{btn}</span></div>'


def hold_rows(held):
    out = []
    for i, (s, q, a, *_) in enumerate(held):
        c, m = s["p"]["c"], s["m"]
        gain = (c - a) * q
        sub = esc(f"{q:,}주 · 평균 ") + (esc(usd(a)) if m == "us" else MS.won_html(a, 14))
        rule = '<span aria-hidden="true" style="flex:none;width:1px;height:10px;margin:0 8px;background:#CBD5E1;"></span>'
        chg = s["p"]["chg"] or 0
        right = (f'<span style="flex:none;display:flex;flex-direction:column;align-items:flex-end;white-space:nowrap;">'
                 f'<span style="display:flex;align-items:center;font-size:15px;line-height:22px;"><b style="font-weight:700;">{MS.updown(chg, pctv(chg), 15)}</b>{rule}'
                 f'{MS.updown(gain, pctv((c - a) / a * 100), 15)}</span>'
                 f'<span style="font-size:16px;line-height:24px;">{MS.updown(gain, MS.won_html(krw(s, gain), 16), 16, tri=False)}</span></span>')
        out.append(f'<span data-row-link="1" data-href="{esc(s["u"])}" style="{dk.MULTI_ROW}{"" if i == 0 else dk.MULTI_SEP}">{MS.stock_left(s, sub)}{right}</span>')
    return f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{"".join(out)}</span></div>'


def pending_card(st):
    rows = []
    for i, (k, side, q) in enumerate(PENDING):
        s = st[k]
        col = dk.UP if side == "매수" else dk.DOWN
        lab = f'<span style="display:inline-block;margin-right:6px;padding:0 6px;border:1px solid {col};border-radius:4px;color:{col};font-size:13px;line-height:20px;font-weight:700;">{side}</span>'
        left = MS.stock_left(s, lab + esc(f"{q:,}주 · {FILL_SHORT[s['m']]}"))
        rows.append(f'<span style="{dk.MULTI_ROW}{"" if i == 0 else dk.MULTI_SEP}">{left}<a data-mock="1" style="{MS.WHITE_BTN}font-size:14px;padding:6px 12px;">취소</a></span>')
    return f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{"".join(rows)}</span></div>'


def flow_chart():
    """자산 흐름 — 처음 10억 대비 % (월말, 예시) · 비교 = 같은 날 시장(코스피 · S&P 500 반반)."""
    days = ["2026-03-31", "2026-04-30", "2026-05-29", "2026-06-30", "2026-07-31", "2026-08-31", "2026-09-30", "2026-10-30", "2026-11-20"]
    me = [2.1, 5.8, 9.4, 7.2, 12.6, 15.3, 10.8, 4.1, -2.4]
    mk = [1.4, 3.9, 6.1, 5.0, 8.2, 9.7, 6.3, 0.9, -6.8]
    pct = lambda v: f"{v:+.1f}%".replace("-", "−")
    labels = [f"{int(d[5:7])}월" for d in days]
    return dk.trend_card("처음 10억 대비 (%)", labels, [("내 자산", me, dk.CHART_MAIN, "solid"), ("시장 (코스피 · S&P 500 반반)", mk, dk.CHART_CMP, "dash")], pct)


def tax_tab():
    """세금 탭 — 미국 주식 양도세 계산 줄 (예시: 테슬라 이익 · 애플 손실, 환율 차이가 들어감)."""
    sells = [("테슬라 500주", "산 날 1달러 1,380원 · 판 날 1,340원", 48_620_000),
             ("애플 300주", "산 날 1,372원 · 판 날 1,351원", -12_410_000)]
    net = sum(v for *_, v in sells)
    base = max(net - 2_500_000, 0)
    tax = round(base * 0.22, -3)
    head = dk.dcard(
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;"><span style="font-size:17px;line-height:24px;font-weight:700;color:#111;">올해 예상 양도세</span>'
        f'<span style="font-size:21px;line-height:28px;font-weight:800;color:#111;">{MS.won_html(tax, 21)}</span></div>'
        f'<div style="font-size:15px;line-height:22px;color:#333;margin:4px 0 0;">미국 주식 · 2027년 5월 신고 · 6월 1일 정산 때 지갑에서 빠집니다</div>', "neutral")
    rows = [(n, sub, MS.updown(v, MS.won_html(v, 16), 16, tri=False)) for n, sub, v in sells]
    rows += [("판 이익 · 손실 합계", "올해 1월 ~ 12월에 판 미국 주식", MS.won_html(net, 16)),
             ("기본 공제", "1년에 한 번", "− " + MS.won_html(2_500_000, 16)),
             ("세금 매기는 금액", "", MS.won_html(base, 16)),
             ("세율 22%", "양도소득세 20% + 지방소득세 2%", MS.won_html(tax, 16))]
    calc = "".join(dk.crow(esc(n), v, esc(sub), first=(i == 0), nowrap=True) for i, (n, sub, v) in enumerate(rows))
    calc_card = f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{calc}</span></div>'
    note = (f'<p style="{MS.SMALL}">수수료 · 환전 비용은 키움증권 영웅문S# 기본 요율(이벤트 우대 없음) 그대로입니다. 아직 팔지 않은 종목의 이익 · 손실은 올해 세금에 들어가지 않습니다. 판 금액과 산 금액은 각각 그날 환율로 원화로 바꿔 계산합니다.</p>')
    paid = [("매매 수수료", "한국 0.015% · 미국 0.25%", 2_467_000), ("환전 비용", "1달러마다 매매기준율의 1%", 5_210_000),
            ("배당 세금", "미국 15% · 한국 15.4% 떼고 입금", 165_000), ("증권거래세", "한국 주식 팔 때 0.20% · 올해 판 것 없음", 0)]   # 예시 거래 기록(record_tab)으로 계산한 값
    paid_rows = "".join(dk.crow(esc(n), MS.won_html(v, 16), esc(sub), first=(i == 0), nowrap=True) for i, (n, sub, v) in enumerate(paid))
    paid_card = f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{paid_rows}</span></div>'
    return (dk.section("세금", head + calc_card + note, one_line=True, tab="세금")
            + dk.section("올해 낸 비용은?", paid_card, one_line=True, tab="세금"))


def record_tab(st):
    trades = [("11월 14일", "매도", "애플", "300주 × $231.40", "실적 발표 뒤 아이폰 판매 안내가 낮아져서 정리했다."),
              ("10월 2일", "매수", "SK하이닉스", "50주 × 1,382,000원", "나눠 사기 두 번째."),
              ("9월 2일", "매수", "SK하이닉스", "70주 × 1,418,000원", "HBM 공급 계약 뉴스 뒤 조정 받을 때 나눠 사기로 했다."),
              ("8월 19일", "매도", "테슬라", "500주 × $331.20", "목표로 적어 둔 값에 왔다."),
              ("5월 14일", "배당", "마이크로소프트", "200주 × $0.91 = $182.00 − 세금 15%", ""),
              ("4월 22일", "매수", "마이크로소프트", "200주 × $455.10", "클라우드 성장률이 다시 빨라지는지 보려고 일부만 샀다."),
              ("3월 11일", "매수", "삼성전자", "800주 × 168,000원", "메모리 가격이 바닥을 지났다는 증권사 보고서가 이어졌다."),
              ("3월 5일", "매수", "엔비디아", "1,000주 × $182.40", "데이터센터 매출이 두 분기 연속 예상을 넘었고, 다음 분기 안내도 올렸다.")]
    COL = {"매수": dk.UP, "매도": dk.DOWN, "배당": "#6B7280"}

    def row(i, t):
        d, side, n, amt, why = t
        col = COL[side]
        lab = f'<span style="display:inline-block;margin-right:6px;padding:0 6px;border:1px solid {col};border-radius:4px;color:{col};font-size:13px;line-height:20px;font-weight:700;">{side}</span>'
        why_html = (f'<span style="display:block;margin:4px 0 0;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};white-space:normal;word-break:keep-all;">“{esc(why)}”</span>') if why else ""
        return (f'<span style="display:block;padding:{dk.SEP_GAP - dk.VP - 1}px 12px;{"" if i == 0 else dk.MULTI_SEP}">'
                f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:10px;"><span style="font-size:16px;line-height:24px;font-weight:700;color:#111;">{lab}{esc(n)}</span>'
                f'<span style="font-size:{dk.TINY};color:{dk.NOTE};white-space:nowrap;">{d}</span></span>'
                f'<span style="display:block;font-size:15px;line-height:22px;color:#333;">{esc(amt)}</span>{why_html}</span>')
    items = [row(i, t) for i, t in enumerate(trades)]
    shown, more = "".join(items[:5]), "".join(items[5:])
    log = dk.fold_card(shown, more, f"거래 {len(trades) - 5}건 더 보기") if more else ""
    years = [("2026년 · 1회차", "3월 2일 ~ 진행 중", -2.4, "시장 −6.8%")]
    yrows = "".join(dk.crow(esc(n), MS.updown(v, pctv(v), 16), esc(f"{sub} · {m}"), first=(i == 0), nowrap=True) for i, (n, sub, v, m) in enumerate(years))
    ycard = f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{yrows}</span></div>'
    return (dk.section("거래 기록은?", log, one_line=True, tab="기록")
            + dk.section("해마다 성적은?", ycard + f'<p style="{MS.SMALL}">12월 31일 정산 때 한 해 수익률 · 낸 세금 · 받은 배당을 한 줄로 남깁니다. 다시 시작한 회차도 지우지 않습니다.</p>', one_line=True, tab="기록"))


def progress(n, goal=100):
    w = round(n / goal * 100)
    return (f'<div style="margin:0 0 8px;padding:14px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;"><span style="font-size:17px;line-height:24px;font-weight:700;color:#111;">참가자 {n}명</span>'
            f'<span style="font-size:15px;line-height:22px;color:#333;">{goal}명이 되면 순위가 열립니다</span></div>'
            f'<div style="margin:10px 0 0;height:10px;background:#E2E8F0;border-radius:5px;overflow:hidden;"><div style="width:{w}%;height:100%;background:#111;"></div></div></div>')


def rank_locked():
    what = "".join(f'<li style="margin:0 0 6px;">{esc(t)}</li>' for t in (
        "별명 · 회차 · 기간(1개월 · 3개월 · 올해) 수익률",
        "가장 크게 잃은 폭 · 가장 큰 종목 비중 (한 종목에 몰아 1등 한 것이 드러나게)",
        "같은 기간 코스피 · S&P 500 줄이 순위 안에 끼어 있어, 시장보다 잘했는지 바로 보입니다"))
    return dk.section("순위", progress(37)
                      + f'<p style="{MS.P}">참가자 = 체결이 한 번이라도 된 회원입니다. 순위가 열리면 이렇게 보입니다.</p>'
                      + f'<ul style="font-size:{dk.BODY};line-height:{dk.LH_BODY};color:#333;margin:0 0 12px;padding-left:{dk.ALIGN_PX + 22}px;word-break:keep-all;">{what}</ul>',
                      one_line=True, tab="순위")


SWITCH = ('<span role="switch" aria-checked="{on}" style="flex:none;position:relative;display:inline-block;width:48px;height:28px;border-radius:14px;background:{bg};">'
          '<span style="position:absolute;top:2px;left:{x}px;width:24px;height:24px;border-radius:12px;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.25);"></span></span>')


def switch(on):
    return SWITCH.format(on="true" if on else "false", bg="#111" if on else "#CBD5E1", x=22 if on else 2)




def disclaim():
    return f'<p style="{MS.SMALL}margin:16px 0 0;">{esc(DISCLAIM)}</p>'


# 다시 시작 확인 창 (팝업 통일 기준: 제목 19/28 · 닫기 테두리 네모 32)
RESET_POP = ("""<style>[data-mi-pop][hidden]{display:none !important;}</style><div data-mi-pop="reset" hidden style="position:fixed;inset:0;z-index:60;background:rgba(15,23,42,.45);display:flex;align-items:center;justify-content:center;padding:16px;">
<div style="width:100%;max-width:420px;box-sizing:border-box;background:#fff;border-radius:12px;padding:20px;">
<div style="font-size:19px;line-height:28px;font-weight:700;color:#111;">다시 시작할까요?</div>
<div style="font-size:16px;line-height:26px;color:#333;margin:8px 0 16px;word-break:keep-all;">보유 종목 · 현금 · 체결 대기 주문이 지워지고 10억 원으로 시작합니다. 지금 회차(1회차 · ▼ 2.4%)는 기록에 남고, 그 회차에 낼 세금은 빠지지 않고 기록으로만 남습니다. 2026년에 남는 다시 시작은 1장입니다.</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;"><a data-mi-close="1" style="__B1__">취소</a><a data-mi-close="1" style="__B2__">다시 시작</a></div></div></div>""")


def wallet_page(st, held):
    us = [h for h in held if h[0]["m"] == "us"]
    kr = [h for h in held if h[0]["m"] == "kr"]
    body = (dk.cards(wallet_head(held) + hold_rows(us) + hold_rows(kr))
            + f'<div style="display:flex;justify-content:flex-end;margin:-2px 0 12px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};">종가 기준 · 1달러 {FX:,.0f}원{dk.tip(DISCLAIM)}</div>'
            + dk.h2("자산", tab="자산")
            + dk.section("체결 대기 주문은?", pending_card(st), one_line=True, tab="자산")
            + dk.section("현금은?", cash_card(), one_line=True, tab="자산")
            + dk.section("자산 흐름은?", flow_chart(), one_line=True, tab="자산")
            + tax_tab() + record_tab(st) + rank_locked()
            + f'<p style="{MS.SMALL}text-align:right;margin:16px 0 0;">모의투자 켜기 · 다시 시작 · 순위 이름은 <a href="mock_invest-mypage.html" style="color:#111;font-weight:700;">내 정보</a>에서 바꿉니다.</p>'
            + disclaim())
    write(body, "mock_invest-wallet.html", nav=("b", "wallet"), share=False, tail=RESET_POP.replace("__B1__", MS.WHITE_BTN).replace("__B2__", MS.WHITE_BTN + f"color:{dk.UP};"))


# ─────────────────────────── 순위 (열린 뒤) ───────────────────────────

NICKS = ["느긋한고래", "분할매수장인", "종가만본다", "반도체덕후", "배당모으기", "차트보는곰", "새벽미장러", "코스피지킴이", "천천히부자", "실적시즌",
         "장기투자자", "가치사냥꾼", "한종목올인", "달러모으기", "조용한황소", "꾸준한거북", "금리읽는밤", "리포트정독", "현금도비중", "꾸준히가자"]


def ranking_page():
    import random
    rnd = random.Random(7)
    people = []
    for i, n in enumerate(NICKS):
        r = round(rnd.uniform(-18, 26) if i else 41.3, 1)
        dd = round(rnd.uniform(4, 30) if i else 38.2, 1)
        top = rnd.choice([18, 22, 27, 31, 35, 42, 55]) if i else 94
        rnd_ = 2 if i in (5, 11) else 1
        people.append((n, rnd_, r, dd, top))
    people.append(("코스피", 0, -8.9, 0, 0))
    people.append(("S&P 500", 0, -4.7, 0, 0))
    people.sort(key=lambda x: -x[2])

    def row(i, rank, p):
        n, rd, r, dd, top = p
        if rd == 0:   # 시장 기준선 줄
            return (f'<span style="{dk.MULTI_ROW}{"" if i == 0 else dk.MULTI_SEP}background:#F8FAFC;">'
                    f'<span style="font-size:15px;line-height:22px;font-weight:700;color:{dk.NOTE};">— 시장 기준선 · {esc(n)}</span>'
                    f'<span style="font-size:15px;">{MS.updown(r, pctv(r), 15)}</span></span>')
        sub = f'{"2회차 · " if rd == 2 else ""}가장 크게 잃은 폭 {dd:.1f}% · 가장 큰 종목 {top}%'
        warn = f' style="color:{dk.UP};font-weight:700;"' if top >= 80 else ""
        sub_html = esc(sub).replace(f"가장 큰 종목 {top}%", f'<span{warn}>가장 큰 종목 {top}%</span>')
        return (f'<span style="{dk.MULTI_ROW}{"" if i == 0 else dk.MULTI_SEP}">'
                f'<span style="display:flex;align-items:flex-start;gap:10px;min-width:0;"><span style="flex:none;width:28px;font-size:16px;line-height:24px;font-weight:800;color:#111;text-align:right;">{rank}</span>'
                f'<span style="min-width:0;"><span style="display:block;font-size:16px;line-height:24px;font-weight:700;color:#111;">{esc(n)}</span>'
                f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};white-space:normal;">{sub_html}</span></span></span>'
                f'<span style="font-size:16px;line-height:24px;font-weight:700;">{MS.updown(r, pctv(r), 16)}</span></span>')
    rows, rank = [], 0
    for i, p in enumerate(people):
        if p[1]:
            rank += 1
        rows.append(row(i, rank, p))
    shown, more = "".join(rows[:5]), "".join(rows[5:])
    lst = dk.fold_card(shown, more, "3,807명 더 보기")
    TABS = "".join(f'<a data-mock="1" style="display:flex;align-items:center;justify-content:center;height:40px;font-size:15px;font-weight:700;{"color:#111;background:#F1F5F9;" if k == "3개월" else "color:#6B7280;background:#fff;"}{"" if j == 0 else "border-left:1px solid #E2E8F0;"}">{k}</a>'
                   for j, k in enumerate(("1개월", "3개월", "올해")))
    seg = f'<div style="display:grid;grid-template-columns:repeat(3,1fr);border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 10px;">{TABS}</div>'
    me = dk.dcard(f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;"><span style="font-size:17px;line-height:24px;font-weight:700;color:#111;">내 순위 · 공부하는개미</span>'
                  f'<span style="font-size:21px;line-height:28px;font-weight:800;color:#111;">1,204위</span></div>'
                  f'<div style="font-size:15px;line-height:22px;color:#333;margin:4px 0 0;">참가자 3,812명 중 상위 32% · 3개월 {MS.updown(-2.4, "2.4%", 15)} · 시장보다 잘한 사람 41%</div>', "neutral")
    body = (f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">가상의 10억 원으로 실전 규칙대로 투자한 참가자들의 성적입니다. 수익률과 함께 가장 크게 잃은 폭 · 가장 큰 종목 비중을 나란히 보여 드립니다.</p>'
            + seg + me + lst
            + f'<p style="{MS.SMALL}">순위 = 기간 수익률 · 회차가 바뀐 지 30일이 안 된 참가자는 빠짐 · 매일 장 마감 뒤 갱신. 가장 큰 종목 비중 80% 이상은 빨간 글씨.</p>'
            + disclaim())
    write(body, "mock_invest-ranking.html", label="모의투자 순위", nav=("b", "rank"))


# ─────────────────────────── 시작 (설정) ───────────────────────────

def start_page():
    rules = [("체결", "주문한 뒤 처음 오는 장 마감 종가로 체결됩니다. 장중 체결은 없습니다."),
             ("비용 · 세금", "키움증권 앱 기본 수수료(한국 0.015% · 미국 0.25%) · 환전 비용 1% · 증권거래세 0.20% · 배당 세금 · 미국 주식 양도세(250만 원 공제 뒤 22%)를 실전처럼 뗍니다."),
             ("달러", "미국 주식은 달러로 사고, 판 돈은 달러로 남습니다. 환율이 수익과 세금에 들어갑니다."),
             ("다시 시작", "충전은 없습니다. 1년에 2번 10억 원으로 다시 시작할 수 있고, 지난 기록은 남습니다."),
             ("순위", "참가자가 100명이 되면 열립니다. 별명과 성적만 보입니다.")]
    out = "".join(dk.crow(esc(n), "", esc(t), first=(i == 0), sub_block=True) for i, (n, t) in enumerate(rules))
    card = f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{out}</span></div>'
    body = (f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">가상의 10억 원으로 블로그의 853개 종목을 실전 규칙 그대로 사고팔아 봅니다. 내 생각이 맞았는지, 몇 년 동안 시장보다 잘했는지 기록으로 남습니다.</p>'
            + dk.cards(dk.dcard(f'<div style="display:flex;justify-content:space-between;align-items:center;gap:12px;"><span style="min-width:0;"><span style="display:block;font-size:17px;line-height:24px;font-weight:700;color:#111;">모의투자 켜기</span>'
                                f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};">켜면 종목 페이지 아래에 매수 · 매도 줄이 생깁니다</span></span>{switch(False)}</div>', "neutral"))
            + dk.section("어떻게 하나요?", card, one_line=True)
            + f'<a data-mock="1" style="{MS.BTN}margin:16px 0 8px;background:#111;color:#fff;">10억 원 받고 시작하기</a>'
            + f'<p style="{MS.SMALL}text-align:center;padding-left:0;">댓글과 같은 구글 로그인 · 별명을 씁니다. 매수 이유 한 줄은 본인만 봅니다.</p>'
            + disclaim())
    write(body, "mock_invest-start.html", label="모의투자", nav=("b", "me"))


# ─────────────────────────── 종목 페이지 + 주문 창 ───────────────────────────

BAR_CSS = """<style>
.mi-bar{position:fixed;left:0;right:0;bottom:0;z-index:44;display:flex;justify-content:center;pointer-events:none;}
.mi-bar>div{pointer-events:auto;width:100%;max-width:980px;box-sizing:border-box;background:#fff;border-top:1px solid #E2E8F0;box-shadow:0 -4px 16px rgba(15,23,42,.08);
  display:flex;align-items:center;gap:8px;padding:10px 14px;}
.mi-hold{flex:1 1 auto;min-width:0;}
.mi-hold>b{display:block;font-size:14px;line-height:20px;color:#6B7280;font-weight:700;}
.mi-hold>span{display:block;font-size:15px;line-height:22px;color:#111;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.mi-btn{flex:none;display:inline-flex;align-items:center;justify-content:center;width:84px;height:44px;border-radius:8px;border:0;color:#fff;font:inherit;font-size:16px;line-height:24px;font-weight:700;cursor:pointer;}
.mi-pad{height:72px;}
.mi-sheet{position:fixed;inset:0;z-index:60;background:rgba(15,23,42,.45);display:flex;align-items:flex-end;justify-content:center;}
.mi-sheet[hidden]{display:none;}
.mi-sheet>div{width:100%;max-width:560px;max-height:88vh;overflow-y:auto;box-sizing:border-box;background:#fff;border-radius:16px 16px 0 0;padding:16px 16px 20px;}
.mi-top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 12px;}
.mi-top b{font-size:19px;line-height:28px;color:#111;}
.mi-x{flex:none;display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border:1px solid #E2E8F0;border-radius:8px;background:#fff;color:#111;cursor:pointer;}
.mi-seg{display:grid;grid-template-columns:1fr 1fr;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;margin:0 0 12px;}
.mi-seg a{display:flex;align-items:center;justify-content:center;height:40px;font-size:15px;line-height:22px;font-weight:700;color:#6B7280;background:#fff;cursor:pointer;}
.mi-seg a+a{border-left:1px solid #E2E8F0;}
.mi-seg a.on-buy{color:#fff;background:%(up)s;} .mi-seg a.on-sell{color:#fff;background:%(down)s;}
.mi-lab{display:block;margin:0 0 4px;font-size:14px;line-height:20px;color:#6B7280;}
.mi-inp{display:block;width:100%%;box-sizing:border-box;height:52px;padding:0 12px;border:1px solid #CBD5E1;border-radius:8px;font-size:18px;line-height:26px;color:#111;background:#fff;}
.mi-chips{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:6px 0 12px;}
.mi-chips a{display:flex;align-items:center;justify-content:center;height:36px;border:1px solid #E2E8F0;border-radius:8px;font-size:14px;line-height:20px;font-weight:700;color:#111;cursor:pointer;}
.mi-rows{border:1px solid #E2E8F0;border-radius:8px;padding:4px 12px;margin:0 0 12px;}
.mi-row{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding:8px 0;font-size:15px;line-height:22px;color:#333;}
.mi-row+.mi-row{border-top:1px solid #F1F5F9;}
.mi-row span:first-child{color:#6B7280;font-size:14px;}
.mi-row.sum{font-weight:700;color:#111;}
.mi-when{display:flex;gap:6px;align-items:flex-start;margin:0 0 12px;padding:10px 12px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;font-size:14px;line-height:20px;color:#333;word-break:keep-all;}
.mi-why{margin:0 0 12px;padding:10px 12px;background:#FFF8E1;border:1px solid #F4D37A;border-radius:8px;font-size:14px;line-height:20px;color:#333;word-break:keep-all;}
.mi-go{display:flex;align-items:center;justify-content:center;width:100%%;height:52px;border:0;border-radius:10px;color:#fff;font:inherit;font-size:17px;line-height:24px;font-weight:700;cursor:pointer;}
.mi-fine{margin:10px 0 0;font-size:14px;line-height:20px;color:#6B7280;word-break:keep-all;}
[data-mi-side][hidden]{display:none !important;}
@media (max-width:900px){.mi-bar{bottom:calc(71px + env(safe-area-inset-bottom));}}
</style>""".replace("%(up)s", dk.UP).replace("%(down)s", dk.DOWN).replace("%%", "%")

X_SVG = '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>'
CLOCK = '<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true" style="flex:none;margin-top:2px;"><circle cx="8" cy="8" r="6.2"/><path d="M8 4.6V8l2.4 1.6"/></svg>'


def order_sheet(s, held_q, avg, bought_day, why):
    m, c = s["m"], s["p"]["c"]
    cur = (lambda v: usd(v)) if m == "us" else (lambda v: wonfmt(v))
    pend_sell = 300 if s["s"] == "005930.KS" else 0
    can_sell = held_q - pend_sell
    cash = CASH_USD + CASH_KRW / FX / (1 + FX_COST) if m == "us" else CASH_KRW
    max_buy = int(cash / (c * LOCK[m] * (1 + FEE[m])))
    avail = (f'{usd(CASH_USD)} + 원화 {wonfmt(CASH_KRW)}' if m == "us" else wonfmt(CASH_KRW))
    data = (f'data-c="{c}" data-m="{m}" data-fee="{FEE[m]}" data-lock="{LOCK[m]}" data-fx="{FX}" data-usd="{CASH_USD}" '
            f'data-avg="{avg}" data-maxbuy="{max_buy}" data-maxsell="{can_sell}"')
    chips = "".join(f'<a data-mi-chip="{p}">{t}</a>' for p, t in ((0.1, "10%"), (0.25, "25%"), (0.5, "50%"), (1, "최대")))
    buy = (f'<div data-mi-side="buy">'
           f'<div class="mi-rows"><div class="mi-row"><span>주문 가능</span><span>{esc(avail)}</span></div>'
           f'<div class="mi-row"><span>살 수 있는 수량</span><span>최대 {max_buy:,}주</span></div></div>'
           f'<label class="mi-lab">수량 (주)</label><input class="mi-inp" data-mi-q="buy" inputmode="numeric" value="{500 if m == "us" else 100}">'
           f'<div class="mi-chips" data-mi-for="buy">{chips}</div>'
           f'<div class="mi-rows" data-mi-calc="buy"></div>'
           f'<div class="mi-when">{CLOCK}<span>{FILL[m]} 그 전까지 지갑에서 취소할 수 있습니다.</span></div>'
           f'<label class="mi-lab">왜 사나요? (선택 · 본인만 봄 · 팔 때 다시 보여 드립니다)</label>'
           f'<input class="mi-inp" style="font-size:16px;margin:0 0 12px;" maxlength="100" placeholder="예: 다음 실적 발표 전까지 들고 간다">'
           f'<button class="mi-go" type="button" data-mi-go="buy" style="background:{dk.UP};">매수 주문</button></div>')
    why_box = (f'<div class="mi-why"><b>{esc(bought_day)}에 살 때 적은 이유</b><br>“{esc(why)}”</div>') if why else ""
    sell = (f'<div data-mi-side="sell" hidden>'
            f'<div class="mi-rows"><div class="mi-row"><span>보유</span><span>{held_q:,}주 · 평균 {cur(avg)}</span></div>'
            + (f'<div class="mi-row"><span>매도 대기</span><span>{pend_sell:,}주</span></div>' if pend_sell else "")
            + f'<div class="mi-row"><span>팔 수 있는 수량</span><span>{can_sell:,}주</span></div></div>'
            f'{why_box}'
            f'<label class="mi-lab">수량 (주)</label><input class="mi-inp" data-mi-q="sell" inputmode="numeric" value="{500 if m == "kr" else 400}">'
            f'<div class="mi-chips" data-mi-for="sell">{chips}</div>'
            f'<div class="mi-rows" data-mi-calc="sell"></div>'
            f'<div class="mi-when">{CLOCK}<span>{FILL[m]} 그 전까지 지갑에서 취소할 수 있습니다.</span></div>'
            f'<label class="mi-lab">왜 파나요? (선택 · 본인만 봄)</label>'
            f'<input class="mi-inp" style="font-size:16px;margin:0 0 12px;" maxlength="100" placeholder="예: 적어 둔 이유가 더는 맞지 않는다">'
            f'<button class="mi-go" type="button" data-mi-go="sell" style="background:{dk.DOWN};">매도 주문</button></div>')
    return (f'<div class="mi-sheet" data-mi-sheet {data} hidden><div>'
            f'<div class="mi-top"><b>{esc(s["n"])} · 모의투자</b><a class="mi-x" data-mi-x aria-label="닫기">{X_SVG}</a></div>'
            f'<div class="mi-seg"><a data-mi-tab="buy">매수</a><a data-mi-tab="sell">매도</a></div>'
            f'<div class="mi-rows"><div class="mi-row"><span>마지막 종가</span><span>{cur(c)} · {day_label(s)}</span></div></div>'
            f'{buy}{sell}<p class="mi-fine">수수료 · 환전 비용 = 키움증권 영웅문S# 기본 요율(이벤트 우대 없음). {esc(DISCLAIM)}</p></div></div>')


ORDER_JS = """<script>(function(){
var sh=document.querySelector('[data-mi-sheet]');if(!sh)return;
var c=+sh.dataset.c,m=sh.dataset.m,fee=+sh.dataset.fee,lock=+sh.dataset.lock,fx=+sh.dataset.fx,usd=+sh.dataset.usd,avg=+sh.dataset.avg;
var MAX={buy:+sh.dataset.maxbuy,sell:+sh.dataset.maxsell};
function money(v){return m==='us'?'$'+Math.abs(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}):Math.round(Math.abs(v)).toLocaleString('ko-KR')+'원';}
function won(v){return Math.round(Math.abs(v)).toLocaleString('ko-KR')+'원';}
function row(a,b,cls){return '<div class="mi-row'+(cls?' '+cls:'')+'"><span>'+a+'</span><span>'+b+'</span></div>';}
function calc(side){var q=Math.floor(+String(sh.querySelector('[data-mi-q='+side+']').value).replace(/,/g,''))||0;var box=sh.querySelector('[data-mi-calc='+side+']');
 var amt=q*c,f=amt*fee,h='';
 if(q>MAX[side]){box.innerHTML=row('수량이 많습니다','최대 '+MAX[side].toLocaleString('ko-KR')+'주');return;}
 if(side==='buy'){h+=row('예상 금액 (마지막 종가 기준)',money(amt))+row('수수료 '+(fee*100).toFixed(m==='us'?2:3)+'%',money(f));
   var lk=amt*lock*(1+fee);h+=row('주문에 묶이는 돈 (종가 +'+Math.round((lock-1)*100)+'% 여유)',money(lk),'sum');
   if(m==='us'){var need=Math.max(lk-usd,0);h+=row('원화에서 자동 환전',need>0?'약 '+won(need*fx*1.01)+' (1달러 '+Math.round(fx).toLocaleString('ko-KR')+'원 + 환전 비용 1%)':'없음 (달러로 충분)');}}
 else{var tax=m==='kr'?amt*0.002:0;h+=row('예상 금액 (마지막 종가 기준)',money(amt))+row('수수료 '+(fee*100).toFixed(m==='us'?2:3)+'%','− '+money(f));
   if(m==='kr')h+=row('증권거래세 0.20%','− '+money(tax));
   h+=row('받을 돈 (예상)',money(amt-f-tax),'sum');var g=(c-avg)*q-f-tax;
   h+=row('이번 매도 손익 (예상)','<span style="color:'+(g>=0?'#d93025':'#1a73e8')+';">'+(g>=0?'+':'−')+money(g)+'</span>');
   if(m==='us')h+=row('SEC 수수료','없음 (키움 기준)');
   if(m==='us')h+=row('양도세','올해 판 이익 · 손실에 더해져 내년 5월 22%');else h+=row('양도세','없음 (한국 주식 · 일반 투자자)');}
 box.innerHTML=h;}
function tab(side){sh.querySelectorAll('[data-mi-tab]').forEach(function(t){t.className=t.dataset.miTab===side?'on-'+side:'';});
 sh.querySelectorAll('[data-mi-side]').forEach(function(x){x.hidden=x.dataset.miSide!==side;});calc(side);}
sh.querySelectorAll('[data-mi-tab]').forEach(function(t){t.addEventListener('click',function(){tab(t.dataset.miTab);});});
sh.querySelectorAll('[data-mi-q]').forEach(function(i){i.addEventListener('input',function(){calc(i.dataset.miQ);});});
sh.querySelectorAll('[data-mi-chip]').forEach(function(ch){ch.addEventListener('click',function(){var side=ch.parentNode.dataset.miFor;
 sh.querySelector('[data-mi-q='+side+']').value=Math.max(1,Math.floor(MAX[side]*(+ch.dataset.miChip)));calc(side);});});
document.querySelectorAll('[data-mi-open]').forEach(function(b){b.addEventListener('click',function(){sh.hidden=false;tab(b.dataset.miOpen);});});
sh.querySelector('[data-mi-x]').addEventListener('click',function(){sh.hidden=true;});
sh.addEventListener('click',function(e){if(e.target===sh)sh.hidden=true;});
sh.querySelectorAll('[data-mi-go]').forEach(function(b){b.addEventListener('click',function(){alert('목업: 주문이 접수되면 지갑의 체결 대기 주문에 들어갑니다.');});});
var demo=document.body.getAttribute('data-mi-demo');if(demo){sh.hidden=false;tab(demo);}
})();</script>"""


def stock_page(base, out, s, hold, demo):
    q, avg, day, why = hold
    c = s["p"]["c"]
    g = (c - avg) / avg * 100
    hold_txt = f'{q:,}주 · 평균 {usd(avg) if s["m"] == "us" else wonfmt(avg)} · '
    bar = (f'<div class="mi-pad"></div><div class="mi-bar"><div><span class="mi-hold"><b>모의투자</b>'
           f'<span>{esc(hold_txt)}{MS.updown(g, pctv(g), 15)}</span></span>'
           f'<button class="mi-btn" type="button" data-mi-open="buy" style="background:{dk.UP};">매수</button>'
           f'<button class="mi-btn" type="button" data-mi-open="sell" style="background:{dk.DOWN};">매도</button></div></div>')
    page = open(base, encoding="utf-8").read()
    page = re.sub(r"<body", f'<body data-mi-demo="{demo}"', page, count=1)
    page = page.replace("</body>", BAR_CSS + bar + order_sheet(s, q, avg, day, why) + ORDER_JS + nav_html("a", "stock", unread=True) + "</body>", 1)
    open(os.path.join(OUT, out), "w", encoding="utf-8").write(page)
    print(f"[모의투자] {out}")


# ─────────────────────────── 공통 ───────────────────────────

POP_JS = ("<script>(function(){document.querySelectorAll('[data-mock]').forEach(function(e){e.addEventListener('click',function(ev){ev.preventDefault();});});"
          "document.querySelectorAll('[data-mi-open]').forEach(function(b){b.addEventListener('click',function(){var p=document.querySelector('[data-mi-pop='+b.getAttribute('data-mi-open')+']');if(p)p.hidden=false;});});"
          "document.querySelectorAll('[data-mi-close]').forEach(function(b){b.addEventListener('click',function(){b.closest('[data-mi-pop]').hidden=true;});});})();</script>")


# ─────────────────────────── 하단 메뉴 두 줄 + 토글 · 내 사진 → 내 정보 ───────────────────────────
# (키움 영웅문S# 캡처): 하단 메뉴가 많아지니 오른쪽 토글로 5칸씩 바꿔 보기.
#   첫 줄 = 지금 5칸 그대로(홈 · 증시 리포트 · 종목 · 증시 전망 · 인물 발언) · 둘째 줄 = 지갑 · 알림 · 보유 종목 · 순위 · 내 정보
#   토글 = 로그인 뒤에만 보인다(로그인 전 동작 안 되는 버튼은 노출 안 함, 2026-10-13 규칙) · 고른 줄은 이 브라우저에만 기억
#   읽지 않은 알림 = 알림 아이콘 빨간 점, 첫 줄을 보고 있으면 토글에도 빨간 점
ICON = {
    "wallet": "<rect x='3.5' y='6' width='17' height='13' rx='2.5'/><path d='M3.5 9.5h13a4 4 0 0 1 4 4'/><path d='M6 6l9-2.5 1.2 2.5'/><circle cx='16.5' cy='13.5' r='1.1'/>",
    "bell": "<path d='M6.5 16.5V11a5.5 5.5 0 0 1 11 0v5.5l1.5 1.5H5z'/><path d='M10 20.5a2.2 2.2 0 0 0 4 0'/>",
    "hold": "<rect x='3.5' y='7.5' width='17' height='12' rx='2'/><path d='M9 7.5V5.5a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 5.5v2'/><path d='M3.5 12.5h17'/>",
    "rank": "<path d='M8.5 20h7'/><path d='M12 16.5V20'/><path d='M7.5 4h9v5a4.5 4.5 0 0 1-9 0z'/><path d='M7.5 6H5a2.5 2.5 0 0 0 2.7 3.5M16.5 6H19a2.5 2.5 0 0 1-2.7 3.5'/>",
    "me": "<circle cx='12' cy='8.5' r='3.5'/><path d='M5 19.5c.9-3.3 3.6-5 7-5s6.1 1.7 7 5'/>",
}
ICON["hot"] = "<path d='M12 21c-3.9 0-6.5-2.6-6.5-6.2 0-3.4 2.4-5.5 3.6-8.3.5 1.7 1.4 2.8 2.6 3.4.3-2.6 1.6-4.9 3.6-6.4-.4 2.6.3 4.4 1.6 6.1 1 1.4 1.6 3 1.6 5.2 0 3.6-2.6 6.2-6.5 6.2z'/>"   # 핫이슈 = 불꽃
ICON["board"] = "<path d='M4 5.5h11a1.5 1.5 0 0 1 1.5 1.5v6A1.5 1.5 0 0 1 15 14.5H9l-3.5 3v-3H4A1.5 1.5 0 0 1 2.5 13V7A1.5 1.5 0 0 1 4 5.5z'/><path d='M19.5 9.5h.5a1.5 1.5 0 0 1 1.5 1.5v6a1.5 1.5 0 0 1-1.5 1.5h-1v2.5L16 18.5h-4.5'/>"   # 토론 = 말풍선 둘
TAB_NEW = [("hot", "핫이슈", "../../issue_store/output/mock_issue_watch.html", 2),
           ("board", "토론", "../../comments/output/mock_board.html", 2)]
SET_B = [("wallet", "지갑", "mock_invest-wallet.html"), ("bell", "알림", "mock_invest-alerts.html"),
         ("hold", "보유 종목", "../../my-stocks/output/mock_my-stocks.html"), ("rank", "순위", "mock_invest-ranking.html"),
         ("me", "내 정보", "mock_invest-mypage.html")]
NAV_CSS = """<style>
@media (max-width:900px){
 .as-tabbar{grid-template-columns:repeat(6,1fr) !important;}
 .as-tabbar.mi-two[data-set=a]{grid-template-columns:repeat(6,1fr) 52px !important;}
 .as-tabbar.mi-two[data-set=b]{grid-template-columns:repeat(5,1fr) 52px !important;}
 .as-tabbar.mi-two[data-set=a] a[data-set=b],.as-tabbar.mi-two[data-set=b] a[data-set=a]{display:none !important;}
 .as-tabbar a[data-set=b]{position:relative;}
 .mi-dot{position:absolute;top:9px;left:calc(50% + 6px);width:8px;height:8px;border-radius:4px;background:#d93025;box-shadow:0 0 0 2px #fff;}
 .mi-tog{position:relative;display:flex;align-items:center;justify-content:center;margin:12px 0;padding:0;border:0;border-left:1px solid #E2E8F0;background:none;cursor:pointer;-webkit-tap-highlight-color:transparent;}
 .mi-tog i{position:relative;display:block;width:22px;height:38px;box-sizing:border-box;border:2px solid #111;border-radius:11px;}
 .mi-tog i::after{content:'';position:absolute;left:3px;top:3px;width:12px;height:12px;border-radius:6px;background:#111;transition:top .15s;}
 .as-tabbar[data-set=b] .mi-tog i::after{top:19px;}
 .mi-tog .mi-dot{top:-3px;left:auto;right:9px;}
 .as-tabbar[data-set=b] .mi-tog .mi-dot{display:none;}
}
</style>"""


def theme_tabbar():
    """테마(index.html)의 하단 고정 메뉴를 그대로 가져온다 — 목업 틀(write_mock)에는 스타일만 있고 메뉴가 없다. 링크는 같은 화면의 목업으로."""
    t = open(os.path.join(EXP, "..", "index.html"), encoding="utf-8").read()
    i = t.index("<nav aria-label='주요 페이지' class='as-tabbar'>")
    nav = t[i:t.index("</nav>", i) + 6]
    for k, h in (("home", "../../home-split/output/mock_home_kr.html"), ("report", "../../kr-market-report/output/kr_report_mock.html"),
                 ("stock", "../../stock-lists/output/mock_stock-lists-live-kr.html"), ("forecast", "../../issue_store/output/mock_forecast-list-eh.html"),
                 ("people", "../../people-radar/output/radar_mock.html")):
        nav = re.sub(rf"(<a data-tab='{k}' href=')[^']*'", rf"\g<1>{h}'", nav)
    #: 첫 줄 6칸 = 홈 · 리포트 · 종목 · 전망 · 핫이슈 · 토론(인물 발언 뺌 → 전체 메뉴). 6칸 + 토글이면 칸 56(360 폰 51)이라 라벨 줄임
    nav = nav.replace("<span>증시 리포트</span>", "<span>리포트</span>").replace("<span>증시 전망</span>", "<span>전망</span>")
    nav = re.sub(r"\s*<a data-tab='people'.*?</a>", "", nav, flags=re.S)
    extra = "".join(f"<a data-tab='{k}' href='{h}'><svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true' stroke-width='{w}'>{ICON[k]}</svg><span>{t}</span></a>"
                    for k, t, h, w in TAB_NEW)
    return nav.replace("</nav>", extra + "</nav>")


def nav_html(set_, on, unread=True):
    """목업 페이지의 테마 하단 메뉴(.as-tabbar)에 둘째 줄 · 토글을 붙이고, 위쪽 로그인 버튼을 내 사진(→ 내 정보)으로 바꾼다."""
    import json as _j
    b = "".join(f"<a data-set='b' data-tab='{k}' href='{h}'><svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true' stroke-width='2'>{ICON[k]}</svg><span>{t}</span>"
                + ("<b class='mi-dot' aria-label='읽지 않은 알림'></b>" if k == "bell" and unread else "") + "</a>" for k, t, h in SET_B)
    tog = "<button class='mi-tog' type='button' aria-label='하단 메뉴 바꾸기'><i></i>" + ("<b class='mi-dot'></b>" if unread else "") + "</button>"
    js = ("<script>(function(){var nav=document.querySelector('.as-tabbar');if(!nav)return;nav.classList.add('mi-two');"
          "nav.querySelectorAll('a').forEach(function(a){a.setAttribute('data-set','a');});"
          "nav.insertAdjacentHTML('beforeend'," + _j.dumps(b + tog) + ");"
          
          "nav.setAttribute('data-set'," + _j.dumps(set_) + ");"
          "nav.querySelector('.mi-tog').addEventListener('click',function(){var n=nav.getAttribute('data-set')==='a'?'b':'a';nav.setAttribute('data-set',n);try{localStorage.setItem('mi-tabset',n);}catch(e){}});"
          "var on=" + _j.dumps(on) + ";setTimeout(function(){nav.querySelectorAll('a').forEach(function(a){a.classList.toggle('on',a.getAttribute('data-tab')===on);});},0);"
          "var lb=document.querySelector('.as-login-btn');if(lb){var a=document.createElement('a');a.className='as-login-btn';a.href='mock_invest-mypage.html';a.setAttribute('aria-label','내 정보');"
          "a.innerHTML='<span class=\"as-ini\">공</span>';lb.parentNode.replaceChild(a,lb);}"
          "})();</script>")
    return NAV_CSS + theme_tabbar() + js


# ─────────────────────────── 내 정보 (마이 페이지) ───────────────────────────
CHEV = ('<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="#9CA3AF" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex:none;">'
        '<path d="M6 3.5l4.5 4.5L6 12.5"/></svg>')


def link_rows(rows):
    """줄 전체가 링크(data-row-link) — 이름 · 보조 줄 왼쪽, 값 + › 오른쪽."""
    out = []
    for i, (name, sub, val, href) in enumerate(rows):
        out.append(f'<a href="{href}" style="{dk.MULTI_ROW}{"" if i == 0 else dk.MULTI_SEP}color:inherit;text-decoration:none;white-space:normal;">'
                   f'<span style="min-width:0;"><span style="display:block;font-size:16px;line-height:24px;font-weight:700;color:#111;">{name}</span>'
                   + (f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};word-break:keep-all;">{sub}</span>' if sub else "")
                   + f'</span><span style="flex:none;display:flex;align-items:center;gap:6px;font-size:15px;line-height:22px;color:#333;white-space:nowrap;">{val}{CHEV}</span></a>')
    return f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{"".join(out)}</span></div>'


def mypage(held):
    _, total = totals(held)
    g = (total - START) / START * 100
    prof = dk.cards(dk.dcard(
        '<div style="display:flex;align-items:center;gap:12px;">'
        '<span style="flex:none;display:flex;align-items:center;justify-content:center;width:48px;height:48px;border-radius:24px;background:#94A3B8;color:#fff;font-size:20px;font-weight:700;">공</span>'
        '<span style="min-width:0;flex:1 1 auto;"><span style="display:block;font-size:19px;line-height:28px;font-weight:700;color:#111;">공부하는개미</span>'
        f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};">반도체 위주로 천천히 공부하며 투자합니다</span></span>'
        f'<a href="../../comments/output/mock_comments_profile.html" style="{MS.WHITE_BTN}font-size:14px;padding:6px 12px;">프로필</a></div>', "neutral"))
    mine = link_rows([
        ("내 지갑", "모의투자 · 체결 대기 2건", MS.updown(g, pctv(g), 15), "mock_invest-wallet.html"),
        ("알림", "읽지 않은 알림 2개", '<span style="display:inline-flex;align-items:center;justify-content:center;min-width:22px;height:22px;padding:0 6px;box-sizing:border-box;border-radius:11px;background:#d93025;color:#fff;font-size:13px;font-weight:700;">2</span>', "mock_invest-alerts.html"),
        ("보유 종목", "직접 적은 실제 보유 · 5종목", MS.updown(8.4, "8.4%", 15), "../../my-stocks/output/mock_my-stocks.html"),
        ("모의투자 순위", "참가자 37명 · 100명이 되면 열립니다", "", "mock_invest-ranking.html"),
        ("내가 쓴 댓글", "12개", "", "../../comments/output/mock_comments_profile.html")])
    sw = [("모의투자 켜기", "끄면 종목 페이지의 매수 · 매도 줄과 하단 메뉴의 지갑 칸만 숨고, 지갑 · 기록은 남습니다.", switch(True)),
          ("순위에 별명 올리기", "끄면 순위에서 빠지고, 내 화면에서만 내 순위를 봅니다.", switch(True))]
    swr = "".join(f'<span style="{dk.MULTI_ROW}{"" if i == 0 else dk.MULTI_SEP}white-space:normal;"><span style="min-width:0;">'
                  f'<span style="display:block;font-size:16px;line-height:24px;font-weight:700;color:#111;">{esc(n)}</span>'
                  f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};word-break:keep-all;">{esc(sub)}</span></span>{x}</span>'
                  for i, (n, sub, x) in enumerate(sw))
    swcard = f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{swr}</span></div>'
    coupon = ''.join(f'<span aria-hidden="true" style="display:inline-flex;align-items:center;justify-content:center;width:44px;height:28px;margin-right:6px;border:1px dashed #111;border-radius:6px;font-size:13px;font-weight:700;color:#111;">{n}</span>' for n in ("1장", "2장"))
    reset = dk.dcard(
        f'<div style="display:flex;justify-content:space-between;align-items:center;gap:12px;"><span style="font-size:17px;line-height:24px;font-weight:700;color:#111;">다시 시작</span><span>{coupon}</span></div>'
        f'<div style="font-size:15px;line-height:22px;color:#333;margin:6px 0 10px;word-break:keep-all;">2026년에 2장 남았습니다. 해마다 1월 1일에 2장을 드리고, 남은 장은 다음 해로 넘어가지 않습니다. '
        f'다시 시작하면 10억 원으로 돌아가고, 지금 회차 기록은 1회차로 남습니다. 새 회차는 30일이 지나야 순위에 오릅니다.</div>'
        f'<a data-mock="1" data-mi-open="reset" style="{MS.WHITE_BTN}width:100%;">10억 원으로 다시 시작하기</a>', "neutral")
    acct = (f'<a data-mock="1" style="{MS.WHITE_BTN}width:100%;margin:0 0 8px;">로그아웃</a>'
            f'<p style="{MS.SMALL}">구글 계정으로 로그인했습니다. 이름 · 사진은 다른 사람에게 보이지 않고, 별명만 보입니다.</p>'
            f'<p style="{MS.SMALL}text-align:right;margin:12px 0 0;"><a data-mock="1" style="color:{dk.NOTE};text-decoration:underline;">모의투자 그만두고 기록 지우기</a> · '
            f'<a data-mock="1" style="color:{dk.NOTE};text-decoration:underline;">탈퇴하고 모든 내용 지우기</a></p>')
    body = (prof
            + dk.section("내 것", mine, one_line=True)
            + dk.section("모의투자 설정", swcard + reset, one_line=True)
            + dk.section("계정", acct, one_line=True))
    write(body, "mock_invest-mypage.html", label="내 정보", nav=("b", "me"), share=False,
          tail=RESET_POP.replace("__B1__", MS.WHITE_BTN).replace("__B2__", MS.WHITE_BTN + f"color:{dk.UP};"))


# ─────────────────────────── 알림 ───────────────────────────

def alerts_page():
    """알림 = 정산이 회원 지갑 파일에 적는 것(새 요청 0). 읽음 표시는 이 브라우저에만. 보관 = 지갑의 거래 기록에 전부 남고, 알림 목록은 최근 30일."""
    A = [  # (읽음, 날짜 시각, 종류, 제목, 보조)
        (False, "11월 20일 16:05", "배당", "삼성전자 배당이 들어왔습니다", "800주 × 370원 = 296,000원 − 세금 15.4% · 받은 돈 250,416원"),
        (False, "11월 14일 07:05", "체결", "애플 300주 매도가 체결되었습니다", "$231.40 · 받은 돈 $69,246.45 (수수료 0.25%) · 올해 양도세 계산에 들어갑니다"),
        (True, "11월 4일 07:05", "일부 체결", "마이크로소프트 매수가 일부만 체결되었습니다", "100주 중 64주 체결 · 36주는 체결 때 돈이 모자라 취소되었습니다"),
        (True, "10월 2일 16:05", "체결", "SK하이닉스 50주 매수가 체결되었습니다", "1,382,000원 · 수수료 0.015%"),
        (True, "9월 2일 16:05", "체결", "SK하이닉스 70주 매수가 체결되었습니다", "1,418,000원 · 수수료 0.015%"),
        (True, "8월 19일 07:05", "체결", "테슬라 500주 매도가 체결되었습니다", "$331.20 · 받은 돈 $165,186.00"),
        (True, "8월 6일 07:05", "배당", "마이크로소프트 배당이 들어왔습니다", "200주 × $0.91 = $182.00 − 세금 15% · 받은 돈 $154.70"),
    ]
    COL = {"체결": "#111", "일부 체결": dk.WARN, "배당": "#6B7280"}

    def row(i, a):
        read, when, kind, title, sub = a
        dot = "" if read else f'<span aria-label="읽지 않음" style="flex:none;width:8px;height:8px;margin:8px 0 0;border-radius:4px;background:{dk.UP};"></span>'
        lab = f'<span style="display:inline-block;margin-right:6px;padding:0 6px;border:1px solid {COL[kind]};border-radius:4px;color:{COL[kind]};font-size:13px;line-height:20px;font-weight:700;">{kind}</span>'
        return (f'<a href="mock_invest-wallet.html" style="display:flex;gap:8px;padding:{dk.SEP_GAP - dk.VP - 1}px 12px;{"" if i == 0 else dk.MULTI_SEP}color:inherit;text-decoration:none;{"" if read else "background:#FFFBF5;"}">'
                f'<span style="min-width:0;flex:1 1 auto;"><span style="display:flex;justify-content:space-between;gap:10px;"><span>{lab}</span>'
                f'<span style="font-size:{dk.TINY};line-height:20px;color:{dk.NOTE};white-space:nowrap;">{when}</span></span>'
                f'<span style="display:block;margin:4px 0 0;font-size:16px;line-height:24px;font-weight:{400 if read else 700};color:#111;word-break:keep-all;">{esc(title)}</span>'
                f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};word-break:keep-all;">{esc(sub)}</span></span>{dot}</a>')
    rows = [row(i, a) for i, a in enumerate(A)]
    lst = dk.fold_card("".join(rows[:5]), "".join(rows[5:]), f"알림 {len(rows) - 5}개 더 보기")
    body = (f'<div style="display:flex;justify-content:space-between;align-items:center;margin:0 0 10px;padding-left:{dk.ALIGN_PX}px;">'
            f'<span style="font-size:15px;line-height:22px;color:#333;">읽지 않은 알림 2개</span>'
            f'<a data-mock="1" style="{MS.WHITE_BTN}font-size:14px;padding:6px 12px;">모두 읽음</a></div>'
            + lst
            + f'<p style="{MS.SMALL}">체결 · 배당 · 세금 정산 알림은 한국 장 마감 뒤(오후 4시쯤) · 미국 장 마감 뒤(아침 7시쯤) 정산 때 생깁니다. '
              f'휴대전화 알림(푸시)은 보내지 않고, 블로그를 열면 하단 메뉴 알림 칸에 빨간 점으로 보입니다. 알림 목록은 최근 30일이고, 모든 기록은 지갑의 거래 기록에 남습니다.</p>')
    write(body, "mock_invest-alerts.html", label="알림", nav=("b", "bell"), share=False)


NO_SHARE = '<span data-no-share="1" hidden></span>'   # 본인만 보는 화면 = 공유 버튼 없음


def write(body, name, label="모의투자", tail="", nav=("b", ""), share=True):
    path = dk.write_mock(MS.head_label(label) + ("" if share else NO_SHARE) + dk.align_titles(dk.WRAP_OPEN + body + dk.WRAP_CLOSE), os.path.join(OUT, name), label)
    if path:
        pg = open(path, encoding="utf-8").read()
        pg = pg.replace("</body>", MS.MOCK_JS + tail + POP_JS + nav_html(*nav) + "</body>", 1)
        open(path, "w", encoding="utf-8").write(pg)
    print(f"[모의투자] {name}")


def main():
    os.makedirs(OUT, exist_ok=True)
    st, held = load()
    hold = {s["s"]: (q, a, d, w) for s, q, a, d, w in held}
    start_page()
    wallet_page(st, held)
    mypage(held)
    alerts_page()
    ranking_page()
    stock_page(os.path.join(EXP, "stock-radar", "output", "mock_NVDA.html"), "mock_invest-nvda.html", st["NVDA"], hold["NVDA"], "buy")
    stock_page(os.path.join(EXP, "kr-stocks", "output", "mock_005930.html"), "mock_invest-005930.html", st["005930.KS"], hold["005930.KS"], "sell")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
