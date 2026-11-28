"""ETF 페이지 새 카드 시안 셋 (개선 방안 6-38 · 6-45 · 6-41). 값은 지금 받은 일봉 · 운용사 파일로 계산한다. AI 0. 블로그에 나가지 않는다.

    .venv/bin/python experiments/stock-etf/mock_etf_new_cards.py   → output/mock_etf_new_cards.html (목업 서버 발행 예정 칸)

① 원화로 보면? — 한국 상장 미국 지수 ETF(TIGER 미국S&P500): 지수(달러) · 원/달러 · 원화로 바꾸면 · 이 ETF 실제를 나란히
② 이 ETF에 돈이 들어오나? — SPDR(SPY): 최근 5 · 20 · 60일 순유입, 비교 대상 = 같은 ETF 지난 1년 20일 순유입의 가운데 절반
③ 오래 들고 있으면? — 레버리지(SOXL): 같은 지수 1배(SOXX) × 3 과 실제를 기간별로
"""
import importlib.util
import os
import sys

import numpy as np
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [EXP]
import design_kit as dk  # noqa: E402
import etf_flows as F  # noqa: E402

spec = importlib.util.spec_from_file_location("dr_cards", os.path.join(EXP, "daily-report", "cards.py"))
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

PERIODS = (("1주", 5), ("1달", 21), ("3달", 63), ("1년", 252))


def pct(v, d=1):
    return f"{'+' if v >= 0 else '−'}{abs(v):.{d}f}%"


def tag(t, sub):
    return (f'<div style="margin:28px 0 8px;padding:8px 12px;background:#FEF3C7;border-radius:8px;font-size:15px;line-height:22px;color:#92400E;">'
            f'<b>{dk.esc(t)}</b> · {dk.esc(sub)}</div>')


def main():
    d = yf.download(["SPY", "KRW=X", "360750.KS", "SOXX", "SOXL"], period="2y", interval="1d", auto_adjust=False, progress=False)["Close"].ffill()

    def ret(c, n):
        s = d[c].dropna()
        return (s.iloc[-1] / s.iloc[-1 - n] - 1) * 100
    day = d.index[-1]
    md = f"{day.month}월 {day.day}일"

    # ① 원화로 보면?
    spy, fx, etf = ret("SPY", 252), ret("KRW=X", 252), ret("360750.KS", 252)
    won = ((1 + spy / 100) * (1 + fx / 100) - 1) * 100
    gap = etf - spy
    c1 = C.question_card("미국 SPY와 수익률이 왜 다른가?", f"환율 {pct(fx)}", "neutral", "#111", [
        (f"최근 1년 S&P 500을 따라가는 미국 SPY는 달러로 {pct(spy)}였습니다. 같은 1년 원/달러 환율이 {pct(fx)} 움직여, 원화로 바꾸면 {pct(won)}입니다. "
         f"TIGER 미국S&P500의 실제 1년 수익률은 {pct(etf)}로, 차이 {abs(gap):.1f}%p 가운데 대부분이 환율입니다.", "plain"),
        ("row", "S&P 500 (미국 SPY, 달러)", pct(spy), "최근 1년"),
        ("row", "원/달러 환율", pct(fx), "원화 값이 오르면 −"),
        ("row", "원화로 바꾸면", pct(won), "두 줄을 곱한 값"),
        ("row", "TIGER 미국S&P500 (이 ETF)", pct(etf), "실제, 분배금 제외"),
        ("환율을 막아 둔 상품(이름 끝 `(H)`)은 이 차이가 거의 없습니다", "note")])

    # ② 이 ETF에 돈이 들어오나?
    rows = F.history("SPY")
    fl = np.array([x[1] for x in F.daily_flows(rows)], dtype=float)
    aum = rows[-1][3]
    v = fl[-252 - 20:]
    s20 = np.array([v[i:i + 20].sum() for i in range(len(v) - 20)])
    lo, mid, hi = np.percentile(s20, 25), np.median(s20), np.percentile(s20, 75)
    now = {n: fl[-n:].sum() for n in (5, 20, 60)}
    usd = lambda x: f"{'+' if x >= 0 else '−'}{abs(x) / 1e8:,.0f}억 달러"  # noqa: E731
    where = "평소보다 많이 들어옴" if now[20] > hi else "평소보다 많이 빠짐" if now[20] < lo else "평소 범위"
    c2 = C.question_card("이 ETF에 돈이 들어오나?", where, "neutral", "#111", [
        (f"최근 20거래일 SPY에 {usd(now[20])}가 {'들어왔습니다' if now[20] >= 0 else '빠졌습니다'}(순자산의 {now[20] / aum * 100:.1f}%). "
         f"지난 1년 20거래일 순유입의 가운데 절반은 {usd(lo)} ~ {usd(hi)}였습니다.", "plain"),
        ("row", "최근 5거래일", usd(now[5]), ""),
        ("row", "최근 20거래일", usd(now[20]), f"지난 1년 가운데 절반 {usd(lo)} ~ {usd(hi)}"),
        ("row", "최근 60거래일", usd(now[60]), ""),
        (f"운용사(스테이트 스트리트)가 날마다 내는 좌수 × 기준가로 계산 · {rows[-1][0][5:7].lstrip('0')}월 {rows[-1][0][8:].lstrip('0')}일까지 · ETF 한 개로 들어온 돈이지 시장 전체의 돈이 아닙니다", "note")])

    # ③ 오래 들고 있으면?
    lines = []
    for nm, n in PERIODS:
        one, three = ret("SOXX", n), ret("SOXL", n)
        lines.append(("row", f"{nm}", pct(three), f"1배 {pct(one)} × 3 = {pct(one * 3)}"))
    one_y, three_y = ret("SOXX", 252), ret("SOXL", 252)
    c3 = C.question_card("오래 들고 있으면 3배가 되나?", "기간이 길수록 달라짐", "neutral", "#111", [
        (f"최근 1년 같은 지수를 1배로 따라가는 아이셰어즈 반도체(SOXX)는 {pct(one_y)}였습니다. 3배면 {pct(one_y * 3)}일 것 같지만 "
         f"디렉시온 반도체 3배는 {pct(three_y)}였습니다. 날마다 3배를 다시 맞추기 때문에, 오르내림이 클수록 오래 들고 있을 때 3배와 멀어집니다.", "plain"),
        *lines,
        ("오른쪽 = 이 ETF 실제 · 아래 회색 = 같은 기간 1배 ETF × 3", "note")])

    body = [tag("① 원화로 보면 (6-38)", f"한국 상장 미국 지수 ETF 의 `오늘` 탭 끝 — TIGER 미국S&P500 · {md} 기준"), c1,
            tag("② 돈이 들어오나 (6-45)", "운용사 좌수 자료가 있는 SPDR 19개만 (SPY · 업종 SPDR) — 자료 없는 ETF 는 카드 없음"), c2,
            tag("③ 오래 들고 있으면 (6-41)", "레버리지 · 인버스 ETF 5개 (SOXL · TQQQ · SQQQ · KODEX 레버리지 · 인버스2X) — 지금 기본 정보의 안내 문장을 숫자로"), c3]
    out = os.path.join(HERE, "output", "mock_etf_new_cards.html")
    dk.write_mock(dk.WRAP_OPEN + "".join(body) + dk.WRAP_CLOSE, out, "ETF — 새 카드 시안 셋")
    print(out, round(spy, 1), round(fx, 1), round(won, 1), round(etf, 1), usd(now[20]), usd(lo), usd(hi), round(one_y, 1), round(three_y, 1))


if __name__ == "__main__":
    main()
