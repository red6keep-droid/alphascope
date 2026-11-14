"""간단 정보 화면의 덧붙이는 조각 — 함께 보는 페이지 · 이름이 나온 기사(미국) · 최근 공시(한국) · 정식 종목으로 넘기기 (2026-11-14).

화면 본체는 정식 종목 렌더러 그대로다(full_us.py · full_kr.py — 2026-11-14 사용자 "TIGER 2차전지처럼 · 정식 종목과 거의 차이 없게").
여기에는 정식 화면에 없는 간단 정보만의 조각을 둔다. 옛 `카드 7개짜리 별도 화면`(같은 날 오전 판)은 기획 6-6 과 어긋나 지웠다.
"""

import datetime
import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
for p in (EXP, os.path.join(EXP, "daily-report"), os.path.join(EXP, "stock-radar"), os.path.join(EXP, "kr-stocks")):
    if p not in sys.path:
        sys.path.insert(0, p)
import cards as C  # noqa: E402
import design_kit as dk  # noqa: E402
import universe as U  # noqa: E402
import universe_kr as K  # noqa: E402

LIST_URL = {"US": U.LIST_URL, "KR": K.LIST_URL}   # 전체 종목 목록(all-stocks)이 생기기 전까지 시장별 종목 목록


def esc(t):
    return html.escape(str(t), quote=False)


def kday(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.month}월 {d.day}일"


def related(f, ref_full):
    """함께 보는 페이지 = 같은 업종의 정식 종목 2개(종목 분석) + 시장별 종목 목록."""
    links = []
    for sym, (name, sector, url) in ref_full.items():
        if sym != f["s"] and sector == f.get("sec") and (sym.endswith((".KS", ".KQ")) == (f["m"] == "KR")):
            links.append((f"{name} 종목 분석", url))
        if len(links) >= 2:
            break
    return links + [("미국 종목 목록" if f["m"] == "US" else "한국 종목 목록", LIST_URL[f["m"]])]


def full_index(ref):
    """정식 종목 {sym: (한글 이름, 업종, 페이지 주소)} — 함께 보는 페이지 · 넘기기용. 간단 종목을 정식 명단에 얹기(full_us · full_kr) 전에 부른다."""
    out = {}
    for sym, e in ref["us"].items():
        if e.get("full") and sym in U.BY_SYM:
            out[sym] = (e["ko"], e.get("sector"), U.page_url(sym))
    for sym, e in ref["kr"].items():
        if e.get("full") and sym in K.BY_SYM:
            out[sym] = (e["ko"], e.get("sector"), K.page_url(sym))
    return out


def extra_cards(f):
    """오늘 탭 끝 — 최근 공시는?(한국, DART 7일) · 이름이 나온 기사는?(미국, 이미 모은 기사 제목 7일). 없으면 ""(빈 답 금지). 기획 6-3-2 ③."""
    q = []
    if f.get("disc"):
        rows = [("row", f'<span><a href="{esc(x["u"])}" target="_blank" rel="noopener" style="color:#111;text-decoration:none;">{esc(x["t"])}</a></span>',
                 kday(x["d"]), "") for x in f["disc"]]
        q.append(C.question_card("최근 공시는?", kday(f["disc"][0]["d"]), "neutral", "#111",
                                 rows + [("금융감독원 전자공시(DART)에 올라온 최근 7일 공시입니다. 누르면 원문으로 갑니다.", "note")]))
    if f.get("news"):
        rows = [("row", f'<span><a href="{esc(x["u"])}" target="_blank" rel="noopener" style="color:#111;text-decoration:none;">{esc(x["t"])}</a></span>',
                 kday(x["d"]) if x.get("d") else "", x.get("src") or "") for x in f["news"]]
        q.append(C.question_card("이름이 나온 기사는?", kday(f["news"][0]["d"]) if f["news"][0].get("d") else "최근 7일", "neutral", "#111",
                                 rows + [("최근 7일 기사 제목에 회사 이름이 나온 것입니다. 이 회사가 주인공이 아닌 기사도 섞일 수 있습니다.", "note")]))
    return C.cards_grid("".join(q)) if q else ""


def redirect(name, url):
    """정식 종목(종목 분석 페이지가 있는 종목)으로 들어오면 그 페이지로 넘긴다 — quick_page.js 가 data-redirect 를 읽는다. 못 넘기면 버튼."""
    return (f'<div data-quick-title="{esc(name)} 주가" data-redirect="{esc(url)}">'
            + dk.muted(f"{esc(dk.josa(name, '은'))} 종목 분석 페이지에서 자세히 다룹니다.") + dk.related_buttons([(f"{name} 종목 분석 보기", url)]) + "</div>")
