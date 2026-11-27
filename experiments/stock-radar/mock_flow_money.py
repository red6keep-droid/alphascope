"""목업 — 미국 종목 `○○ 업계 자금 흐름은?` 카드에 ETF 로 실제 들어온 돈 줄 붙이기 (개선 3-2).

발행 코드(render_html.sector_lines)를 그대로 부른다. 실제 돈 = etf_flows.fund(운용사 좌수 이력, 지금 받아 옴). 수익 차이 값은 --rel 로 준다(기록 records/flows 의 rel20).
    python experiments/stock-radar/mock_flow_money.py --rel XLK=-11.2 XLE=-3.8
→ output/mock_flow_money.html.  읽기만 · 쓰기 · AI 0.
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
NAMES = {"XLK": "기술", "XLE": "에너지", "XLF": "금융", "XLV": "헬스케어"}


def card(etf, rel, with_fund):
    pp = R.config.SECTOR_FLOW_PP
    sf = {"etf": etf, "name": NAMES.get(etf, etf), "state": "모이는 중" if rel >= pp else "빠져나가는 중" if rel <= -pp else "뚜렷하지 않음",
          "rel_pp": rel, "days": 20, "sectors": [], "rank": 1, "n_pool": 11}
    if with_fund:
        sf["fund"] = etf_flows.fund(etf)
    th, col = R.FLOW_THEME.get(sf["state"], ("neutral", R.MUTED))
    c = R._state_card(f"{sf['name']} 업계 자금 흐름은?", sf["state"], th, col, RP.sector_lines(sf), "", tip=R.sector_tip("S&P 500"), fold=True, opened=True)
    return f'<div data-cards="1" style="margin:0 0 8px;">{c}</div>'


def label(name, what):
    return f'<div style="margin:26px 0 8px;font-size:16px;line-height:24px;color:#111;"><b style="color:#7C3AED;">{name}</b><span style="color:#6B7280;"> — {what}</span></div>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rel", nargs="+", default=["XLK=-11.2", "XLE=-3.8"])
    a = ap.parse_args()
    rels = [(x.split("=")[0], float(x.split("=")[1])) for x in a.rel]
    body = dk.muted("미국 종목 → 업계상황 탭 맨 위 카드입니다. 운용사가 날마다 내는 ETF 좌수로 실제 들어오고 나간 돈을 세어 문장 하나와 줄 하나를 더합니다. 판정(답)은 지금처럼 수익 차이 기준 그대로입니다.")
    for etf, rel in rels:
        body += label(f"지금 · {NAMES.get(etf, etf)}", "오늘 적용한 문장 · 툴팁까지") + card(etf, rel, False)
        body += label(f"실제 돈 붙임 · {NAMES.get(etf, etf)}", "둘째 문장 + `ETF에 실제 들어온 돈` 줄") + card(etf, rel, True)
    print(dk.write_mock(dk.formal(body) if hasattr(dk, "formal") else body, os.path.join(BASE, "output", "mock_flow_money.html"), "업계 자금 흐름 카드 — ETF에 실제 들어온 돈"))


if __name__ == "__main__":
    main()
