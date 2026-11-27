"""목업 — 종목 `의견` 탭 맨 위 요약 문단 (옛 문단 / 지금 = 지난 기록일과 달라진 것부터).

지금 문단 = render_html.opinions_summary 를 그대로 부른다(상황만 넣음) — 화면 코드와 목업이 같은 문장.
옛 문단 = 2026-11-27 까지의 문장(전문가 → 방송 → Newfact 신호의 수준). 견줘 보려고 글자로만 남긴다.
    비교 대상 = 이 종목의 지난 기준 거래일 값(op_change.for_stock — 평균 목표가 · 신호 · 방송 의견 id).

기존 목업 output/mock_000660.html 의 요약 문단 자리에 상황 넷을 끼워 output/mock_op_summary_000660.html 로 쓴다. 읽기만 · 쓰기 · AI 0.
첫 상황의 평균 목표가는 기록에 있는 값, 날짜 · 며칠째와 나머지 셋은 문장 모양을 보려고 넣은 예시 값.
    python experiments/kr-stocks/mock_op_summary.py
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "..", "stock-radar"))
sys.path.insert(0, os.path.join(BASE, "..", "nvda-report"))
sys.path.insert(0, os.path.join(BASE, ".."))
import render_pages as RP  # noqa: E402
import signal_groups as SG  # noqa: E402
import stock_records as SR  # noqa: E402

R, dk = RP.R, RP._dk
NAME, DAY, PT = "SK하이닉스", "2026-11-05", 3157409
won = lambda v: f"{v:,.0f}원"   # noqa: E731
pick = lambda u, a: {"url": u, "speaker": "예시", "ticker": "000660", "action": a, "published_at": "2026-11-04T09:00:00+09:00"}   # noqa: E731
FLAT = [("2026-10-30", 3100000), ("2026-11-02", PT), ("2026-11-03", PT), ("2026-11-04", PT)]   # 11월 2일부터 같은 값
SIG0 = [("2026-11-03", 0), ("2026-11-04", 0)]   # 이틀 중립

OLD = ("전문가들은 SK하이닉스를 ▲ 상승 추세로 보고, 평균 목표가는 지금 주가보다 한참 위에 있습니다. 방송에서는 요즘 SK하이닉스 이야기가 조용합니다. "
       "Newfact 신호는 중립이고, 주가는 최근 며칠 ▲ 올랐습니다.")

# (상황 이름, 오늘 평균 목표가, 방송 의견, 오늘 신호, 지난 기록)
CASES = [
    ("바뀐 것이 없는 날", PT, [], 0, {"pt": FLAT, "sig": SIG0, "seen": set()}),
    ("전문가 목표가가 오른 날 (예시 값)", 3240000, [], 0, {"pt": FLAT, "sig": SIG0, "seen": set()}),
    ("목표가가 내리고 Newfact 신호도 바뀐 날 (예시 값)", 3098000, [], -1, {"pt": FLAT, "sig": SIG0, "seen": set()}),
    ("방송에서 새 의견이 나오고 Newfact 신호가 바뀐 날 (예시 값)", PT, [pick("a", "매수"), pick("b", "매수"), pick("c", "보유")], 1,
     {"pt": FLAT, "sig": SIG0, "seen": {SR.pick_id(pick("c", "보유"))}}),
]


def tag(text, sub=False):
    col, size = ("#475569", 13) if sub else ("#B45309", 14)
    return f'<div style="margin:{8 if sub else 22}px 0 4px;padding-left:6px;font-size:{size}px;font-weight:700;color:{col};">{text}</div>'


def plain(h):
    return re.sub(r"\s+", " ", re.sub(r"<svg.*?</svg>|<[^>]+>", "", h, flags=re.S)).strip()


def main():
    html = open(os.path.join(BASE, "output", "mock_000660.html"), encoding="utf-8").read()
    blocks = [tag("옛 문단 (2026-11-27 까지) — 어느 날이든 같은 말로 시작") + f'<p style="{dk.SEO_LEAD}{dk.TAB_LEAD_GAP}color:#64748B;">{OLD}</p>']
    for title, pm, picks, sg, ch in CASES:
        SG.horizon_votes = lambda rows, sg=sg: {"단기": (sg,)}
        p = dk.formal(R.opinions_summary(NAME, [{"key": "pt_mean", "value": pm}], None, picks, None, None, [("x", 1)], won, change=dict(ch, day=DAY)))
        blocks.append(tag(title) + p)
        print(title, "|", plain(p))
    html, n = re.subn(r'<p data-op-summary="1"[^>]*>.*?</p>', lambda m: "".join(blocks), html, count=1, flags=re.S)
    out = os.path.join(BASE, "output", "mock_op_summary_000660.html")
    open(out, "w", encoding="utf-8").write(html)
    print(out, "| 바꾼 자리", n)


if __name__ == "__main__":
    main()
