"""봉차트 카드 — 페이지 안에서 직접 그리는 실제 차트(candle_chart.js) 의 Python 쪽 (2026-11-13 사용자: "그림 말고 실제 차트").

    card(name, bars, dec=0, avg=None) → 제목 + 흰 카드 + [data-candle] (자료 = 최근 2년 일봉, 주봉 · 월봉 · 지표는 브라우저 계산)
    SCRIPT → <script>…</script> (한 페이지에 한 번 — 스크립트가 스스로 한 번만 돈다). 나중에 테마(index.html)로 옮기면 SCRIPT 는 빼도 된다.
새 수집 · AI 0. 자료 = 각 실행이 이미 받은 snapshot 일봉.
"""
import html
import json
import os

import design_kit as dk

HERE = os.path.dirname(os.path.abspath(__file__))
DAYS = 520   # 2년 남짓 — 200일 평균이 1년 내내 보이게


def _js():
    with open(os.path.join(HERE, "candle_chart.js"), encoding="utf-8") as f:
        return f.read()


SCRIPT = "<script>" + _js() + "</script>"


def card(name, bars, dec=0, avg=None, title="가격 흐름"):
    """bars = [{day, open, high, low, close, volume}] (오래된 것 → 최신). avg = {"price": 값, "label": "내 평단"} — 회원 본인 화면에서만(공개 HTML 엔 넣지 않는다)."""
    rows = []
    for b in bars[-DAYS:]:
        c = b.get("close")
        if not c:
            continue
        o = b.get("open") or c
        rows.append([b["day"], round(o, dec + 2), round(max(b.get("high") or c, o, c), dec + 2), round(min(b.get("low") or c, o, c), dec + 2), round(c, dec + 2), int(b.get("volume") or 0)])
    if len(rows) < 20:
        return ""
    d = {"name": name, "dec": dec, "bars": rows}
    if avg:
        d["avg"] = avg
    data = html.escape(json.dumps(d, ensure_ascii=False, separators=(",", ":")), quote=True)
    head = f'{dk.CHART_TITLE_M}{dk.esc(title)}</span>' if title else ""
    return (head + f'<span style="{dk.MULTI}margin:0 {dk.CHART_CARD_X}px;"><span style="display:block;padding:{dk.CHART_CARD_PAD}px 12px;">'
            f'<div data-candle="{data}" style="min-height:300px;"></div></span></span>')
