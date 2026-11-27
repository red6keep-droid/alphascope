"""목업 — `○○ 업계 자금 흐름은?` 카드에 ETF 로 들어온 돈을 선 그래프로 (개선 3-2, 5거래일 단위 · 1개월 단위 두 안).

운용사 좌수 이력(etf_flows.history)으로 순유입을 쌓아 올린 선. 발행 코드(render_html.sector_lines)의 줄 사이에 그래프만 끼운다.
    python experiments/stock-radar/mock_flow_chart.py --rel XLK=-11.2 XLE=-3.8
→ output/mock_flow_chart.html.  읽기만 · 쓰기 · AI 0.
"""
import argparse
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, ".."))
import design_kit as dk  # noqa: E402
import etf_flows  # noqa: E402
import render_pages as RP  # noqa: E402

R = RP.R
NAMES = {"XLK": "기술", "XLE": "에너지"}


daily_flows = etf_flows.daily_flows   # 분할 날을 맞춰 센다


def weekly(rows, n=12, step=5):
    """최근 n×step 거래일 — step 거래일마다 쌓인 순유입(억 달러). 처음 = 0."""
    fl = daily_flows(rows)[-n * step:]
    labels, vals, acc = [], [], 0.0
    for k in range(0, len(fl), step):
        chunk = fl[k:k + step]
        acc += sum(v for _, v in chunk)
        d = chunk[-1][0]
        labels.append(f"{int(d[5:7])}.{int(d[8:])}")
        vals.append(acc / 1e8)
    return labels, vals


def monthly(rows, n=12):
    """최근 n개월 — 달마다 쌓인 순유입(억 달러)."""
    by = {}
    for d, v in daily_flows(rows):
        by[d[:7]] = by.get(d[:7], 0.0) + v
    months = sorted(by)[-n:]
    labels, vals, acc = [], [], 0.0
    for m in months:
        acc += by[m]
        labels.append(m[2:].replace("-", "."))
        vals.append(acc / 1e8)
    return labels, vals


def card(etf, rel, mode, rows):
    pp = R.config.SECTOR_FLOW_PP
    sf = {"etf": etf, "name": NAMES.get(etf, etf), "state": "모이는 중" if rel >= pp else "빠져나가는 중" if rel <= -pp else "뚜렷하지 않음",
          "rel_pp": rel, "days": 20, "sectors": [], "rank": 1, "n_pool": 11, "fund": etf_flows.summary(rows)}
    lines = RP.sector_lines(sf)
    if mode:
        labels, vals = weekly(rows) if mode == "w" else weekly(rows, n=24) if mode == "w24" else monthly(rows)
        title = (f"최근 {len(labels) * 5}거래일 ETF에 들어온 돈 (5거래일마다 쌓은 값, 억 달러)" if mode in ("w", "w24") else f"최근 {len(labels)}개월 ETF에 들어온 돈 (달마다 쌓은 값, 억 달러)")
        chart = dk.trend_card(title, labels, [(f"{etf} 순유입 누적", vals, dk.CHART_MAIN, "solid"), ("0 (들어온 돈 = 나간 돈)", [0.0] * len(vals), dk.CHART_CMP, "guide")],
                              lambda v: f"{v:+,.0f}".replace("-", "−"))
        lines.insert(3, (chart, "html"))
    th, col = R.FLOW_THEME.get(sf["state"], ("neutral", R.MUTED))
    c = R._state_card(f"{sf['name']} 업계 자금 흐름은?", sf["state"], th, col, lines, "", tip=R.sector_tip("S&P 500"), fold=True, opened=True)
    return f'<div data-cards="1" style="margin:0 0 8px;">{c}</div>'


def label(name, what):
    return f'<div style="margin:26px 0 8px;font-size:16px;line-height:24px;color:#111;"><b style="color:#7C3AED;">{name}</b><span style="color:#6B7280;"> — {what}</span></div>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rel", nargs="+", default=["XLK=-11.2", "XLE=-3.8"])
    a = ap.parse_args()
    body = dk.muted("미국 종목 → 업계상황 탭 맨 위 카드입니다. 하루하루 값 대신, ETF에 들어온 돈을 쌓아 올린 선으로 흐름을 봅니다. 선이 올라가면 들어오는 중, 내려가면 나가는 중입니다.")
    for x in a.rel:
        etf, rel = x.split("=")[0], float(x.split("=")[1])
        rows = etf_flows.history(etf)
        nm = NAMES.get(etf, etf)
        body += label(f"지금 · {nm}", "오늘 연결한 모습(문장 + 줄, 그래프 없음)") + card(etf, rel, None, rows)
        body += label(f"A안 · {nm}", "5거래일 단위 — 최근 60거래일(약 석 달), 점 12개") + card(etf, rel, "w", rows)
        body += label(f"B안 · {nm}", "1개월 단위 — 최근 12개월, 점 12개") + card(etf, rel, "m", rows)
        body += label(f"C안 (추천) · {nm}", "5거래일 단위 그대로, 범위만 120거래일(약 여섯 달)로 — 점 24개, 옆으로 넘겨 보기") + card(etf, rel, "w24", rows)
    print(dk.write_mock(dk.formal(body), os.path.join(BASE, "output", "mock_flow_chart.html"), "업계 자금 흐름 카드 — 들어온 돈 선 그래프 (5거래일 · 1개월)"))


if __name__ == "__main__":
    main()
