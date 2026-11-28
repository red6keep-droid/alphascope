"""ETF 분배금 시안 (개선 방안 6-43) — 야후 분배금 이력으로 `분배금은 얼마 · 언제?`. AI 0. 블로그에 나가지 않는다.

    .venv/bin/python experiments/stock-etf/mock_etf_dividend.py   → output/mock_etf_dividend.html (목업 서버 발행 예정 칸)

지금 = 기본 정보 `분배금 수익률 1.00% (최근 1년)` 한 줄(미국만, 한국 없음)
시안 A = 기본 정보 탭 질문 카드 — 최근 1년 합 · 분배율 · 주는 달 · 마지막 지급 · 1년 전 같은 기간, 비교 대상 = 같은 묶음 ETF 분배율
시안 B = 기본 정보 줄만 늘림 — `1.00% · 3 · 6 · 9 · 12월 · 마지막 9월 18일 1.89달러`
"""
import datetime
import importlib.util
import os
import sys

import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [EXP]
import design_kit as dk  # noqa: E402
import etf_universe as E  # noqa: E402

spec = importlib.util.spec_from_file_location("dr_cards", os.path.join(EXP, "daily-report", "cards.py"))
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

SHOW = (("SPY", ["VOO"]), ("SCHD", []), ("069500.KS", ["102110.KS"]), ("360750.KS", ["379800.KS", "360200.KS"]))


def div_info(sym):
    t = yf.Ticker(sym)
    dv = t.dividends
    px = t.history(period="5d")["Close"].dropna()
    if not len(dv) or not len(px):
        return None
    dv.index = dv.index.tz_localize(None)
    now = datetime.datetime.now()
    y1 = dv[dv.index > now - datetime.timedelta(days=365)]
    y0 = dv[(dv.index > now - datetime.timedelta(days=730)) & (dv.index <= now - datetime.timedelta(days=365))]
    months = sorted({d.month for d in y1.index})
    return {"sum": float(y1.sum()), "prev": float(y0.sum()), "n": len(y1), "months": months, "last": (dv.index[-1], float(dv.iloc[-1])),
            "price": float(px.iloc[-1]), "yield": float(y1.sum()) / float(px.iloc[-1]) * 100}


def money(sym, v):
    return f"{v:,.0f}원" if sym.endswith(".KS") else f"{v:,.2f}달러"


def name(sym):
    nm = E.BY_SYM[sym][1]
    return nm if sym.endswith(".KS") or sym in nm.split() else f"{nm} {sym}"


def card_a(sym, peers):
    d = div_info(sym)
    if not d:
        return ""
    mo = " · ".join(f"{m}" for m in d["months"]) + "월"
    ld, lv = d["last"]
    chg = (d["sum"] / d["prev"] - 1) * 100 if d["prev"] else None
    first = (f"최근 1년 {dk.josa(name(sym), '은')} {d['n']}번, 모두 {dk.josa(money(sym, d['sum']), '을')} 나눠 줬습니다. 지금 가격으로 치면 {d['yield']:.2f}%입니다. "
             f"주로 {mo}에 줍니다.")
    lines = [(first, "plain"),
             ("row", "최근 1년 분배금", money(sym, d["sum"]), f"{d['n']}번" + (f" · 1년 전 같은 기간 {money(sym, d['prev'])}" if d["prev"] else "")),
             ("row", "분배율", f"{d['yield']:.2f}%", "최근 1년 합 ÷ 지금 가격"),
             ("row", "마지막 지급", money(sym, lv), f"{ld.month}월 {ld.day}일 분배락 — 이날부터 산 사람은 이번 분배금을 못 받음")]
    for p in peers:
        pd_ = div_info(p)
        if pd_:
            lines.append(("row", f"{name(p)} 분배율", f"{pd_['yield']:.2f}%", "같은 지수 다른 ETF"))
    lines.append(("분배금을 받으면 가격이 그만큼 내려 시작합니다 · 세금을 떼기 전 금액 · 야후 파이낸스 분배금 이력", "note"))
    ans = f"1년 {d['yield']:.2f}%"
    return C.question_card("분배금은 얼마 · 언제 주나?", ans, "neutral", "#111", lines), d


def row_b(sym, d):
    ld, lv = d["last"]
    mo = " · ".join(str(m) for m in d["months"]) + "월"
    return (f'<div style="padding:12px {dk.ALIGN_PX}px;border:1px solid #E2E8F0;border-radius:8px;margin:0 0 8px;font-size:{dk.TINY};line-height:22px;">'
            f'<span style="display:flex;justify-content:space-between;gap:12px;"><span style="color:{dk.SUB};">분배금 수익률</span>'
            f'<span style="text-align:right;color:#111;">{d["yield"]:.2f}%<span style="display:block;color:{dk.NOTE};">최근 1년 · {mo} · 마지막 분배락 {ld.month}월 {ld.day}일 {money(sym, lv)}</span></span></span></div>')


def tag(t, sub):
    return (f'<div style="margin:28px 0 8px;padding:8px 12px;background:#FEF3C7;border-radius:8px;font-size:15px;line-height:22px;color:#92400E;">'
            f'<b>{dk.esc(t)}</b> · {dk.esc(sub)}</div>')


def main():
    a, b = [], []
    for sym, peers in SHOW:
        r = card_a(sym, peers)
        if not r:
            continue
        a.append(r[0])
        b.append(f'<p style="margin:12px 0 4px;font-weight:700;">{dk.esc(name(sym))}</p>' + row_b(sym, r[1]))
    body = [tag("지금", "미국 = 기본 정보 `분배금 수익률 1.00% (최근 1년)` 한 줄 · 한국 = 없음"),
            tag("시안 A (추천)", "기본 정보 탭 질문 카드 — 얼마 · 언제 · 마지막 지급 · 1년 전과 · 같은 지수 다른 ETF 분배율"),
            f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{"".join(a)}</div>',
            tag("시안 B", "기본 정보 줄만 늘림 — 비교 대상 없음"), "".join(b)]
    out = os.path.join(HERE, "output", "mock_etf_dividend.html")
    dk.write_mock(dk.WRAP_OPEN + "".join(body) + dk.WRAP_CLOSE, out, "ETF — 분배금 시안")
    print(out)


if __name__ == "__main__":
    main()
