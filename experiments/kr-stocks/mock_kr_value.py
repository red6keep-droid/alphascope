"""목업 — 한국 종목 실적 탭 새 카드 둘 (개선 1-14 · 1-12, 미국 틀 가져오기 · 11-27 A안 확정).

① `발표 때 예상을 넘었나?` = render_kr.card_beat ② `이익에 비해 주가 수준은?` = render_kr.card_value (A안: KOSPI 전체 PER · 이 종목 분기 말).
발행 코드 함수를 그대로 불러 기존 한국 종목 목업(output/mock_005930.html · mock_000660.html)의 실적 탭에 끼운다 → output/mock_kr_value_{코드}.html.
정식 실행(collect_kr_extra → extra["beat"])이 돈 뒤에는 mock_005930.html 자체에 두 카드가 나오므로 이 목업은 그때까지만 쓴다. 읽기만 · 쓰기 · AI 0.
    python experiments/kr-stocks/mock_kr_value.py --fin <dart_fin_all.json> --flows <flows.json>
"""
import argparse
import datetime
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import render_kr as K  # noqa: E402
import collect_kr_extra as C  # noqa: E402
import collect_kr_fin as KF  # noqa: E402
import universe_kr as U  # noqa: E402

CARD_RE = re.compile(r'<div style="background:[^"]*border-radius:10px;padding:18px 14px;margin:0 0 8px;line-height:32px;"><details')


def card_spans(html, start):
    """start 뒤 카드마다 (시작, 끝, 제목 글자)."""
    out = []
    for m in CARD_RE.finditer(html, start):
        i, depth, j = m.start(), 0, m.start()
        for t in re.finditer(r"<(/?)div\b", html[i:]):
            depth += -1 if t.group(1) else 1
            if depth == 0:
                j = i + t.end() + 1
                break
        out.append((i, j, re.sub(r"<[^>]+>", "", html[i:i + 3000])[:40]))
    return out


def main():
    import yfinance as yf
    ap = argparse.ArgumentParser()
    ap.add_argument("--fin", default=os.path.join(BASE, "data", "dart_fin_all.json"))
    ap.add_argument("--flows", default=os.path.join(BASE, "data", "flows.json"))
    a = ap.parse_args()
    fin = json.load(open(a.fin, encoding="utf-8"))
    per = json.load(open(a.flows, encoding="utf-8"))["more_m"]["per"]
    K.KOSPI_PER = {"month": per[-1]["month"], "v": per[-1]["v"], "series": per[-24:]}
    snap = json.load(open(os.path.join(BASE, "data", "snapshot.json"), encoding="utf-8"))
    qref = json.load(open(os.path.join(BASE, "..", "ref", "quick_ref.json"), encoding="utf-8"))["kr"]
    for sym in ("005930.KS", "000660.KS"):
        code = sym.split(".")[0]
        html = open(os.path.join(BASE, "output", f"mock_{code}.html"), encoding="utf-8").read()
        bars = snap["bars"][sym]
        day = bars[-1]["day"]
        nxt = re.search(r"다음 실적 발표는 (\d+)월 (\d+)일", re.sub(r"<[^>]+>", "", html))   # 목업 페이지 `다음 실적 발표는?` 과 같은 날
        nxt_day = None
        if nxt:
            y = int(day[:4]) + (1 if int(nxt.group(1)) < int(day[5:7]) else 0)
            nxt_day = f"{y}-{int(nxt.group(1)):02d}-{int(nxt.group(2)):02d}"
        s = {"sym": sym, "name": U.name(sym), "day": day, "cap": snap["caps"][sym], "close": bars[-1]["close"], "_bars": bars,
             "_fin_rows": KF._rows(fin.get(qref[sym]["corp"]) or {}, datetime.date.fromisoformat(day)), "_beat": C._beat(yf.Ticker(sym)),
             "calendar_cards": {"earnings": {"day": nxt_day}}}
        spans = card_spans(html, html.find('data-tab="실적"'))
        eps_at = next(i for i, j, h in spans if h.startswith("이익 예상"))
        sched = next(k for k, (i, j, h) in enumerate(spans) if h.startswith("다음 실적 발표"))
        end = spans[sched - 1][1]
        html = html[:end] + K.card_value(s) + html[end:]
        html = html[:eps_at] + K.card_beat(s) + html[eps_at:]
        out = os.path.join(BASE, "output", f"mock_kr_value_{code}.html")
        open(out, "w", encoding="utf-8").write(html)
        print(out)


if __name__ == "__main__":
    main()
