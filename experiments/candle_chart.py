"""봉차트 카드 — 페이지 안에서 직접 그리는 실제 차트(candle_chart.js) 의 Python 쪽.

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


MOCK_AVG = 0.97   # 목업에만 보이는 `내 평단` 예시 = 마지막 종가의 97% (실제 페이지엔 없다 — 회원 본인 화면에서만, 회원 기능 때)
GAP = '<div style="height:20px;"></div>'   # 차트와 탭 사이 20
NAVER_KR = "https://m.stock.naver.com/domestic/stock/{code}/total"
NAVER_KOSPI = "https://m.stock.naver.com/domestic/index/KOSPI/total"


def kr_live(code, always=False, url=None):
    """한국 종목 봉차트 오른쪽 아래(탭 위) `실시간 가격은 네이버 증권에서 보기 ↗` — 장중(평일 9:00~15:30 한국 시간)에만 보이고 장이 끝나면 사라진다
. 켜고 끄기 = candle_chart.js krLive(1분마다). always = 목업용(시각과 상관없이 보임).
    url = 종목 페이지가 아닌 곳(한국 증시 리포트 코스피 = NAVER_KOSPI). 새 호출 0 — 링크만."""
    if not (code or url):
        return ""
    link = (f'<a href="{html.escape(url or NAVER_KR.format(code=code), quote=True)}" target="_blank" rel="noopener" data-trhelp="skip" '
            f'style="font-size:13px;line-height:19px;color:{dk.SUB};text-decoration:underline;text-underline-offset:3px;">'
            f'실시간 가격은 네이버 증권에서 보기 {dk.LINK_ICON}</a>')
    return (f'<div data-kr-live="{"always" if always else "1"}" style="display:{"flex" if always else "none"};justify-content:flex-end;margin:8px 0 0;">'
            f'{link}</div>')


def page_block(name, bars, dec=0, kr_code=None):
    """종목 페이지 맨 위 봉차트 한 덩이.
    목업 = `내 평단` 예시가 있는 차트, 발행 본문 = 없는 차트 — render_pages · render_kr 의 mock-only / real-only 표시로 가른다. 자료가 모자라면 "".
    kr_code = 한국 종목 코드 → 차트 아래 장중 네이버 링크(kr_live, 목업은 늘 보임)."""
    real = card(name, bars, dec, title="")
    if not real:
        return ""
    last = bars[-1]["close"]
    mock = card(name, bars, dec, avg={"price": round(last * MOCK_AVG, dec), "label": "내 평단"}, title="")
    return ("<!--mock-only-->" + mock + kr_live(kr_code, always=True) + GAP + "<!--/mock-only--><!--real-only-->" + real + kr_live(kr_code) + GAP
            + "<!--/real-only-->" + SCRIPT)
