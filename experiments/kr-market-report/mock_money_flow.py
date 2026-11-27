"""목업 — 한국 증시 리포트 수급 탭 맨 위 `증시에서 돈이 빠져나가나?` 카드 (개선 2번).

지금 수급 탭 카드(외국인 · 기관 개인 · 빚투 대기 자금)는 모두 오늘 대 어제 · 전달 대비라 몇 달에 걸친 흐름이 안 보인다.
이 카드는 같은 자료를 **12개월 고점 대비 · 몇 달째**로 묶어 상태만 말한다(앞날은 말하지 않는다). 새 수집 · AI 0 — flows.json 만 읽는다.
    python experiments/kr-market-report/mock_money_flow.py --flows <flows.json>     # kr-state 의 experiments/kr-stocks/data/flows.json
→ output/mock_money_flow.html

판정(시안): ① 대기 자금이 12개월 고점보다 10% 넘게 줄었나 ② 외국인이 석 달 이상 이어서 순매도했나 ③ 빚투가 고점보다 10% 넘게 줄었나.
둘 이상이면 `빠져나가는 중`, 반대(고점 5% 안 · 석 달 이상 순매수)가 둘 이상이면 `들어오는 중`, 그 밖은 `뚜렷하지 않음`. 거래대금은 활기라 판정에 넣지 않고 같이 보여 준다.
"""
import argparse
import collections
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import main as M  # noqa: E402

DROP_PCT, NEAR_PCT, STREAK = 10.0, 5.0, 3
dk = M._dk


def _mo(mo):
    return f"{int(mo[5:])}월"


def _peak(ser, scale):
    """최근 12개월 → (마지막 달, 마지막 값, 고점 달, 고점 값, 고점 대비 %)."""
    w = ser[-12:]
    last, top = w[-1], max(w, key=lambda x: x["v"])
    return last["month"], last["v"] / scale, top["month"], top["v"] / scale, (last["v"] / top["v"] - 1) * 100


def _streak(ser):
    """마지막 달부터 같은 방향으로 이어진 달 수 · 부호 · 그 합."""
    sign = 1 if ser[-1]["v"] > 0 else -1
    n, tot = 0, 0.0
    for x in reversed(ser):
        if (x["v"] > 0) != (sign > 0):
            break
        n, tot = n + 1, tot + x["v"]
    return n, sign, tot, ser[-n]["month"]


def money_card(d):
    fm, im, ind, daily = d["funds_m"], d["investor_m"], d["industry"], d["daily"]
    mo, dep, dmo, dtop, dpct = _peak(fm["deposits"], 1e12)
    _, crd, cmo, ctop, cpct = _peak(fm["credit_loan"], 1e12)
    _, tov, tmo, ttop, tpct = _peak(ind["kospi_turnover"], 1e9)
    n, sign, tot, since = _streak(im["foreign"])
    tot /= 1e6   # 백만 원 → 조 원
    out = sum([dpct <= -DROP_PCT, sign < 0 and n >= STREAK, cpct <= -DROP_PCT])
    inn = sum([dpct >= -NEAR_PCT, sign > 0 and n >= STREAK, cpct >= -NEAR_PCT])
    state = "빠져나가는 중" if out >= 2 else "들어오는 중" if inn >= 2 else "뚜렷하지 않음"
    word = "순매도" if sign < 0 else "순매수"

    lines = [(f"주식을 사려고 기다리는 돈(투자자 예탁금)은 {_mo(mo)} 말 {dep:,.1f}조 원으로, 최근 12개월 중 가장 많았던 {_mo(dmo)}({dtop:,.1f}조 원)보다 "
              f"{dtop - dep:,.1f}조 원({M._s(dpct, 1)}) 줄었습니다." if dpct <= -1 else
              f"주식을 사려고 기다리는 돈(투자자 예탁금)은 {_mo(mo)} 말 {dep:,.1f}조 원으로, 최근 12개월 중 가장 많은 수준입니다.", "plain")]
    second = f"외국인은 유가증권시장에서 {_mo(since)}부터 {_mo(mo)}까지 {n}개월 연속 {word}했고, 합계는 {abs(tot):,.1f}조 원입니다." if n > 1 else \
        f"외국인은 {_mo(mo)} 유가증권시장에서 {abs(tot):,.1f}조 원 {word}했습니다."
    cur = collections.defaultdict(float)   # 이번 달 — 일별 자료(억 원)
    for x in daily["foreign_kospi"]:
        cur[x["day"][:7]] += x["v"]
    last_day = daily["foreign_kospi"][-1]["day"]
    if last_day[:7] > mo:
        v = cur[last_day[:7]] / 1e4
        second += f" {_mo(last_day[:7])}도 {int(last_day[8:])}일까지 {abs(v):,.1f}조 원 {'순매도' if v < 0 else '순매수'}입니다."
    lines.append((second, "plain"))

    # 그래프 — 저마다의 12개월 고점을 100으로 놓은 흐름. 비교 대상 = 코스피 월말
    ks = collections.OrderedDict()
    for x in daily["kospi"]:
        ks[x["day"][:7]] = x["v"]
    months = [x["month"] for x in fm["deposits"][-12:]]
    def idx(vals):
        top = max(v for v in vals if v is not None)
        return [None if v is None else v / top * 100 for v in vals]
    dv = idx([x["v"] for x in fm["deposits"][-12:]])
    tv = idx([{x["month"]: x["v"] for x in ind["kospi_turnover"]}.get(m_) for m_ in months])
    kv = idx([ks.get(m_) for m_ in months])
    chart = dk.trend_card("최근 12개월 흐름 (저마다 가장 높았던 달 = 100)", [m_[2:].replace("-", ".") for m_ in months],
                          [("대기 자금 (투자자 예탁금)", dv, dk.CHART_MAIN, "solid"), ("하루 평균 거래대금", tv, dk.CHART_SERIES[1], "solid"), ("코스피 (월말)", kv, dk.CHART_CMP, "dash")],
                          lambda v: f"{v:,.0f}")
    lines.append((chart, "html"))

    k_last, k_top_mo = ks[mo], max(months, key=lambda m_: ks.get(m_) or 0)
    lines += [("row", "대기 자금", f"{dep:,.1f}조 원", f"12개월 고점({_mo(dmo)} {dtop:,.1f}조 원)보다 {M._s(dpct, 1)}"),
              ("row", "외국인", f"{n}개월 연속 {word}", f"{_mo(since)} ~ {_mo(mo)} 합계 {abs(tot):,.1f}조 원"),
              ("row", "빚투 (신용융자)", f"{crd:,.1f}조 원", f"12개월 고점({_mo(cmo)} {ctop:,.1f}조 원)보다 {M._s(cpct, 1)}"),
              ("row", "하루 평균 거래대금", f"{tov:,.1f}조 원", f"12개월 고점({_mo(tmo)} {ttop:,.1f}조 원)의 {tov / ttop * 100:.0f}% · 돈의 양이 아니라 사고파는 활기"),
              ("row", "같은 기간 코스피", f"{k_last:,.0f}", f"비교 대상 · {_mo(k_top_mo)} 말 {ks[k_top_mo]:,.0f}보다 {M._s((k_last / ks[k_top_mo] - 1) * 100, 1)}")]
    tip = ("주식시장에 들어와 있는 돈이 늘고 있는지 줄고 있는지, 몇 달 흐름으로 봅니다\n"
           f"· 나누는 법 : 대기 자금이 12개월 고점보다 {DROP_PCT:.0f}% 넘게 줄었나, 외국인이 {STREAK}개월 이상 이어서 순매도했나, 빚투가 고점보다 {DROP_PCT:.0f}% 넘게 줄었나. 셋 중 둘 이상이면 빠져나가는 중\n"
           "· 거래대금은 산 금액과 판 금액이 같아 돈이 빠졌는지를 말하지 않습니다. 활기로 같이 보여 줍니다\n"
           "· 지금 상태를 말하며, 앞으로의 주가를 말하지 않습니다")
    theme, color = M._dir(-1 if state == "빠져나가는 중" else 1 if state == "들어오는 중" else 0)
    return M._qc("증시에서 돈이 빠져나가나?", f"{_mo(mo)}까지 {state}", theme, color, lines, tip=dk.with_src(tip, M.RK.SRC), opened=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flows", required=True)
    a = ap.parse_args()
    d = json.load(open(a.flows, encoding="utf-8"))
    body = (dk.muted("한국 증시 리포트 → 수급 탭 맨 위에 놓을 새 카드입니다(지금 수급 탭 카드 넷은 그 아래 그대로). 판정 기준 숫자는 시안입니다.")
            + M.C.cards_grid(money_card(d)))
    print(dk.write_mock(body, os.path.join(BASE, "output", "mock_money_flow.html"), "증시에서 돈이 빠져나가나? — 수급 탭 새 카드"))


if __name__ == "__main__":
    main()
