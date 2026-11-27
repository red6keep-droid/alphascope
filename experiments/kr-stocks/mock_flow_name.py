"""목업 — `○○ 업계 자금 흐름은?` 카드의 말을 재는 것(업종 ETF 수익률 − 시장)에 맞추기 (개선 1-7).

기존 한국 종목 목업(output/mock_005930.html)의 카드를 그대로 꺼내 `지금` · `A안` · `B안` 세 장을 한 화면에 세로로 놓는다 → output/mock_flow_name.html.
읽기만 · 쓰기 · AI 0. 미국 종목 카드도 같은 함수(render_html.sector_lines)라 모양이 같다.
    python experiments/kr-stocks/mock_flow_name.py
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, ".."))
import design_kit as dk  # noqa: E402
import mock_kr_value as M  # noqa: E402

TIP = "업종 ETF 수익률을 시장(KOSPI)과 견준 값입니다. 실제로 들어오고 나간 금액을 센 것은 아닙니다."


def _swap(html, pairs):
    for a, b in pairs:
        if a not in html:
            raise SystemExit(f"바꿀 글을 못 찾음: {a[:40]}")
        html = html.replace(a, b)
    return html


def _label(name, what):
    return (f'<div style="margin:26px 0 8px;font-size:16px;line-height:24px;color:#111;"><b style="color:#7C3AED;">{name}</b>'
            f'<span style="color:#6B7280;"> — {what}</span></div>')


def main():
    page = open(os.path.join(BASE, "output", "mock_005930.html"), encoding="utf-8").read()
    now = next(page[i:j] for i, j, t in M.card_spans(page, 0) if "자금 흐름" in t)
    a = _swap(now, [('<span style="white-space:nowrap;">흐름은?</span>', '<span style="white-space:nowrap;">흐름은?</span>' + dk.tip(TIP)),
                    ("아래라 돈이 반도체 쪽에서 빠지는 중입니다.", "아래라 주가 흐름으로 보면 돈이 반도체 쪽에서 빠지는 중입니다.")])
    b = _swap(now, [('반도체 업계 자금 <span style="white-space:nowrap;">흐름은?</span>', '반도체 업계 주가는 <span style="white-space:nowrap;">시장보다?</span>'),
                    ("</span>\xa0빠져나가는 중</span>", "</span>\xa0약함</span>"),
                    ("판정 빠져나가는 중", "판정 약함"),
                    ("아래라 돈이 반도체 쪽에서 빠지는 중입니다.", "아래라 반도체 업계 주가가 시장보다 약합니다."),
                    ("빠져나가는&nbsp;중", "약함"), ("모이는&nbsp;중", "강함"), ("뚜렷하지&nbsp;않음", "비슷함"),
                    ("넘으면 유입", "넘으면 강함"), ("아래면 유출", "아래면 약함")])
    wrap = '<div data-cards="1" style="margin:0 0 8px;">{}</div>'
    body = (dk.muted("한국 · 미국 종목 업계상황 탭 맨 위 카드입니다. 재는 것은 업종 ETF 20거래일 수익률과 시장의 차이인데, 지금 말은 돈이 실제로 빠진 것처럼 읽힙니다.")
            + _label("지금", "제목 · 답 · 문장이 모두 돈의 말") + wrap.format(now)
            + _label("A안 (추천)", "제목 · 답은 그대로, 문장에 `주가 흐름으로 보면` + 제목 옆 ? 툴팁. 신호 이름 · 기록은 안 바뀜") + wrap.format(a)
            + _label("B안", "제목 · 답 · 눈금까지 재는 것 그대로(강함 · 비슷함 · 약함). 신호 이름과 기록 값의 말이 바뀜") + wrap.format(b))
    out = os.path.join(BASE, "output", "mock_flow_name.html")
    print(dk.write_mock(body, out, "업계 자금 흐름 카드 — 말 고치기 시안"))


if __name__ == "__main__":
    main()
