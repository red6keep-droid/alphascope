"""회원 `내 종목` 목업 (2026-11-12 사용자 "일단 기본으로 목업으로 적용해줘") — 비공개 기획 `doc/기획/회원-내-종목-기획.md` 3절 기본값 그대로.

    python experiments/my-stocks/mock_my_stocks.py   → output/mock_my-stocks-*.html (목업 서버 `my-stocks` 묶음)

화면 세 가지:
  mock_my-stocks-guest.html  로그인 전 — 무엇을 하는 곳 · 남은 자리 · 구글 로그인
  mock_my-stocks.html        로그인 뒤 — 총액 · 총 수익률(원화 환산, 미국 · 한국 따로 두 줄) · 보유 종목 줄 · 소식 · 종목 넣기 · 맨 아래 작은 글씨
  mock_my-stocks-full.html   자리가 찼을 때
기본값(열린 질문): 운영자는 보지 않는다 · 자동 선착순 10명 · 알림 없음.
가격 = 검색 색인(site-search/output/search_index.json, 블로그가 이미 올리는 것) 종가. 보유 수량 · 평균 매수가는 예시 값이다. 인터넷 · AI 0.
"""
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import design_kit as dk  # noqa: E402
import tech_signals as TS  # noqa: E402  — 판정 라벨 = 채운 상자 (가이드라인 8절, U3)

OUT = os.path.join(HERE, "output")
INDEX = os.path.join(HERE, "..", "site-search", "output", "search_index.json")
SEATS, TAKEN = 10, 7   # 예시: 10자리 중 7자리 찼다
FX, FX_DAY = 1356.34, "2026-11-06"   # 원 · 달러 환율(daily-report prices.json KRW=X 마지막 값). 실제는 검색 색인에 환율 한 칸을 더해 같이 읽는다
NAME = "보유 종목"   # 메뉴 · 머리 줄 이름 (2026-11-12 사용자: `내 종목` → `보유 종목`)

# 예시 보유 (수량, 평균 매수가) — 이익 · 손실이 섞이게
HOLD = {"NVDA": (30, 152.40), "MSFT": (10, 545.00), "TSLA": (12, 260.00),
        "005930.KS": (50, 168000), "000660.KS": (5, 1420000)}

esc = lambda t: html.escape(str(t), quote=False)
P = f"font-size:{dk.BODY};line-height:{dk.LH_BODY};color:#333;margin:0 0 12px;word-break:keep-all;padding-left:{dk.ALIGN_PX}px;"
SMALL = f"font-size:{dk.TINY};line-height:22px;color:{dk.NOTE};margin:0 0 6px;padding-left:{dk.ALIGN_PX}px;word-break:keep-all;"
BTN = ("display:flex;align-items:center;justify-content:center;gap:10px;width:100%;box-sizing:border-box;height:52px;border-radius:10px;"
       "font-size:17px;line-height:24px;font-weight:700;text-decoration:none;cursor:pointer;")
G_LOGO = ('<svg viewBox="0 0 18 18" width="18" height="18" aria-hidden="true"><path fill="#4285F4" d="M17.6 9.2c0-.6-.1-1.2-.2-1.8H9v3.4h4.8a4.1 4.1 0 0 1-1.8 2.7v2.2h2.9c1.7-1.6 2.7-3.9 2.7-6.5z"/>'
          '<path fill="#34A853" d="M9 18c2.4 0 4.5-.8 6-2.2l-2.9-2.2c-.8.5-1.8.9-3.1.9-2.4 0-4.4-1.6-5.1-3.8H.9v2.3A9 9 0 0 0 9 18z"/>'
          '<path fill="#FBBC05" d="M3.9 10.7a5.4 5.4 0 0 1 0-3.4V5H.9a9 9 0 0 0 0 8l3-2.3z"/>'
          '<path fill="#EA4335" d="M9 3.6c1.3 0 2.5.5 3.5 1.4l2.6-2.6A9 9 0 0 0 .9 5l3 2.3C4.6 5.2 6.6 3.6 9 3.6z"/></svg>')


def load():
    d = json.load(open(INDEX, encoding="utf-8"))
    return {s["s"]: s for s in d["stocks"]}


def money(v, m, sign=False):
    s = "+" if sign and v > 0 else ("−" if v < 0 else "")
    a = abs(v)
    return f"{s}${a:,.2f}" if m == "us" else f"{s}{a:,.0f}원"


def pct(v):
    return f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.1f}%"


def updown(v, text, px, tri=True):
    """증감 = ▲ 빨강 · ▼ 파랑 · 0 회색 + 절댓값 글자 (2026-11-12 사용자: + 대신 증감 삼각형, 삼각형은 숫자보다 작게).
    삼각형 = 숫자 글자의 80% · 위로 1 (가이드라인 1절 크기표 `dk.emph_tri` 와 같은 규칙). text 는 부호 없는 절댓값 글자."""
    col = dk.UP if v > 0 else dk.DOWN if v < 0 else dk.MUTED
    tri = ("▲" if v > 0 else "▼" if v < 0 else "") if tri else ""   # tri=False = 금액(원) — 삼각형 없이 색만 (2026-11-12 사용자: 금액은 삼각형 빼기)
    t = f'<span data-tri="1" style="font-size:{round(px * 0.8)}px;vertical-align:1px;margin-right:2px;">{tri}</span>' if tri else ""
    return f'<span style="color:{col};white-space:nowrap;">{t}{text if "<" in text else esc(text)}</span>'


def won_html(v, px):
    """가격 `5,322,651 원` — 숫자 뒤 띄어 쓰고 `원`은 보통 굵기 · 숫자보다 2px 작게 (2026-11-12 사용자: 모든 가격의 원)."""
    return f'{abs(v):,.0f}<span style="font-weight:400;font-size:{px - 2}px;"> 원</span>'


def won(v):
    return f"{abs(v):,.0f}원"


def code(s):
    return s["s"].split(".")[0]


def total_card(rows, m):
    cost = sum(q * a for _, q, a in rows)
    val = sum(q * s["p"]["c"] for s, q, _ in rows)
    gain = val - cost
    day = max(s["p"]["d"] for s, _, _ in rows)
    kind = "positive" if gain > 0 else "negative" if gain < 0 else "neutral"   # 카드 색 = 답 방향 (가이드라인 7-1)
    head = "미국 종목" if m == "us" else "한국 종목"
    body = (f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;">'
            f'<span style="font-size:17px;line-height:24px;font-weight:700;color:#111;">{head}</span>'
            f'<span style="font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};">{day[5:7].lstrip("0")}월 {day[8:].lstrip("0")}일 종가</span></div>'
            f'<div style="margin:6px 0 0;font-size:26px;line-height:34px;font-weight:800;">{dk.tint(esc(money(gain, m, True)) + " · " + esc(pct(gain / cost * 100)))}</div>'
            f'<div style="font-size:15px;line-height:22px;color:#333;">평가 금액 {esc(money(val, m))} · 산 금액 {esc(money(cost, m))}</div>')
    return dk.dcard(body, kind)


def grand_card(held):
    """맨 위 = 보유 종목 전체 (2026-11-12 사용자):
      총 평가 금액                   38,647,671원   ← 이름 굵게 · 금액 26px 굵게, 오른쪽
      수익 금액 5,322,651원              ▲ 16.0%   ← 아래 네 줄 = 16px 보통 굵기 이름 + 금액 왼쪽, 수익률 오른쪽(굵게, 같은 크기)
      매수 금액 33,325,020원
      미국 종목 · 3종목 4,137,651원      ▲ 23.2%
      한국 종목 · 2종목 1,185,000원       ▲ 7.6%
      현재 환율 1달러 1,356원
    금액은 원화 · 삼각형 없이 증감 색만, 수익률은 ▲▼ + 증감 색. 금액과 수익률 사이 점 없음. 미국 종목은 환율로 원화 환산해 더한다."""
    krw = lambda s, v: v * FX if s["m"] == "us" else v
    cost = sum(krw(s, q * a) for s, q, a in held)
    val = sum(krw(s, q * s["p"]["c"]) for s, q, a in held)
    gain = val - cost
    kind = "positive" if gain > 0 else "negative" if gain < 0 else "neutral"   # 카드 색 = 답 방향 (가이드라인 7-1)
    ROW = "display:flex;justify-content:space-between;align-items:baseline;gap:12px;"
    FS = 16   # 아래 줄 글자 · 수익률 한 크기 (2026-11-12 사용자: 증감 정보는 다 같은 크기)
    # 아래 네 줄 = 세 칸 격자: 이름 | 금액(왼쪽 정렬, 네 줄이 같은 세로선) | 수익률(오른쪽). 모두 보통 굵기 (2026-11-12 사용자)
    GRID = f"display:grid;grid-template-columns:auto 1fr auto auto;column-gap:10px;align-items:baseline;font-size:{FS}px;line-height:24px;color:#333;font-weight:400;"
    RULE = '<span aria-hidden="true" style="grid-column:1/-1;height:1px;background:#FEE6CA;margin:8px 0;"></span>'

    def cells(label, amount_html, rate_html=""):
        # 이름(회색 14) | (빈 칸) | 수익률 | 금액(맨 오른쪽 끝) — 등락률을 금액 앞에 (2026-11-12 사용자)
        return (f'<span style="white-space:nowrap;font-size:{dk.TINY};color:{dk.NOTE};">{label}</span><span></span>'
                f'<span style="white-space:nowrap;text-align:right;">{rate_html}</span><span style="white-space:nowrap;text-align:right;">{amount_html}</span>')

    top = (f'<div style="{ROW}"><span style="font-size:17px;line-height:24px;font-weight:700;color:#111;white-space:nowrap;">총 평가 금액</span>'
           f'<span style="font-size:21px;line-height:28px;font-weight:800;color:#111;white-space:nowrap;">{won_html(val, 21)}</span></div>')   # 30 → 28 → 26 → 23 → 21 (2026-11-12 사용자)
    grid = [f'<span style="grid-column:1/-1;text-align:right;white-space:nowrap;font-size:{dk.TINY};color:{dk.NOTE};">매수 금액 {won_html(cost, 14)}</span>',   # 매수 금액 = 수익 금액 위 · `매수 금액 33,325,020 원` 한 덩어리 오른쪽 정렬, 회색 작은 글씨 (2026-11-12 사용자)
            cells("수익 금액", updown(gain, won_html(gain, FS), FS, tri=False), updown(gain, f"{abs(gain / cost * 100):.1f}%", FS))]
    for m, head in (("us", "미국"), ("kr", "한국")):   # `미국 3종목` (2026-11-12 사용자: `미국 종목` → `미국`)
        rows = [h for h in held if h[0]["m"] == m]
        if not rows:
            continue
        c = sum(krw(s, q * a) for s, q, a in rows)
        v = sum(krw(s, q * s["p"]["c"]) for s, q, _ in rows)
        if m == "us":
            grid.append(RULE)
        grid.append(cells(f'{head} {len(rows)}종목',
                          updown(v - c, won_html(v - c, FS), FS, tri=False), updown(v - c, f"{abs((v - c) / c * 100):.1f}%", FS)))
    sub = [f'<div style="{GRID}margin:6px 0 0;">{"".join(grid)}</div>']
    fx = ""   # 환율 줄 삭제 (2026-11-12 사용자) — 계산 기준은 맨 아래 작은 글씨
    return dk.dcard(top + "".join(sub) + fx, kind)


def stock_rows(rows, m):
    """종목 줄 (2026-11-12 사용자):  [로고] 엔비디아           오늘 ▲ 2.3% | ▲ 35.6%
                                           30주 · 평균 $152.40           | 2,209,071원
    - 이름 = 한글만(티커 · 종목 코드 삭제). 보조 줄은 로고 뒤 이름 글자 왼쪽 선에 맞춤
    - 오늘 등락 = 보조 줄에서 빼서 오른쪽 수익률 앞에, 사이 세로 구분선
    - 숫자는 모두 보통 굵기(이름만 굵게). 수익률 ▲▼ + 증감 색, 수익금(원화)은 색만"""
    out = []
    LOGO = 22
    for i, (s, q, a) in enumerate(rows):
        c = s["p"]["c"]
        gain = (c - a) * q
        chg = s["p"]["chg"] or 0
        gk = gain * FX if m == "us" else gain   # 수익금 = 원화 (미국 종목은 환율로 바꿈, 평균 매수가는 산 통화 그대로)
        left = stock_left(s, esc(f"{q:,}주 · 평균 ") + (esc(money(a, m)) if m == "us" else won_html(a, 14)))   # 원 = 띄우고 2 작게
        # 오른쪽 = 윗줄 `오늘 등락(굵게) | 수익률`(15px, 사이 세로 구분선) · 아랫줄 수익금(보통) — `오늘` 글자 없음 (2026-11-12 사용자)
        rule = '<span aria-hidden="true" style="flex:none;width:1px;height:10px;margin:0 8px;background:#CBD5E1;"></span>'   # 세로 구분선 = 글자 15 의 70% → 10 (2026-11-12 사용자)
        right = (f'<span style="flex:none;display:flex;flex-direction:column;align-items:flex-end;white-space:nowrap;">'
                 f'<span style="display:flex;align-items:center;font-size:15px;line-height:22px;"><b style="font-weight:700;">{updown(chg, f"{abs(chg):.1f}%", 15)}</b>{rule}'
                 f'{updown(gain, f"{abs((c - a) / a * 100):.1f}%", 15)}</span>'
                 f'<span style="font-size:16px;line-height:24px;font-weight:400;">{updown(gain, won_html(gk, 16), 16, tri=False)}</span></span>')   # 굵게 = 오늘 등락만, 수익금은 보통 (2026-11-12 사용자)
        row = (f'<span style="{dk.MULTI_ROW}{"" if i == 0 else dk.MULTI_SEP}">{left}'
               f'{right}</span>')
        out.append(row.replace("<span ", f'<span data-row-link="1" data-href="{esc(s["u"])}" ', 1))
    return f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{"".join(out)}</span></div>'


def news_block(held):
    """내 종목 소식 — 종목 페이지에 이미 있는 것만: 추세(200일 평균선) · 다음 실적 발표 · 최근 뉴스 제목."""
    trend = []
    for s, _, _ in held:
        ma = (s.get("t") or {}).get("ma") or []
        last = next((x for x in ma if x[0] == 200), None)
        if not last:
            continue
        up = bool(last[2])
        lab = TS.box("up", "상승", esc) if up else TS.box("down", "하락", esc)   # 판정 = 채운 상자(종목 페이지 평균선 대비 줄과 같은 꼴, U3) — 옛 외곽선 라벨은 뉴스 영역 · 긍정 · 부정용
        trend.append((f'{dk.ticker_logo(s["s"], 22)}{esc(s["n"])}', f'{lab}', f'200일 평균선 {"위" if up else "아래"}'))
    rows = [dk.crow(n, v, sub, first=(i == 0), nowrap=True) for i, (n, v, sub) in enumerate(trend)]
    trend_card = f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{"".join(rows)}</span></div>'

    ev = sorted(((s["ne"], s) for s, _, _ in held if s.get("ne")), key=lambda x: x[0])
    ev_rows = [dk.crow(dk.ticker_logo(s["s"], 22) + esc(s["n"]), f'{int(d[5:7])}월 {int(d[8:])}일', "실적 발표", first=(i == 0), nowrap=True) for i, (d, s) in enumerate(ev[:4])]
    ev_card = f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{"".join(ev_rows)}</span></div>'

    items = sorted(((d, t, src, s) for s in [h[0] for h in held] for d, t, src in (s.get("news") or [])[:2]), reverse=True)[:5]
    news_card = (f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">'
                 + "".join(f'<span style="display:block;padding:{dk.SEP_GAP - dk.VP - 1}px 12px;{"" if i == 0 else dk.MULTI_SEP}">{x}</span>'
                           for i, x in enumerate(dk.news_item(esc(t), None, meta=(f'{int(d[5:7])}월 {int(d[8:])}일', s["n"])) for d, t, src, s in items))
                 + "</span></div>") if items else ""
    return (dk.section("추세는?", trend_card, one_line=True, tab="추세")
            + dk.section("다음 실적 발표는?", ev_card, one_line=True, tab="일정")
            + (dk.section("최근 뉴스는?", news_card, one_line=True, tab="뉴스") if news_card else ""))


WHITE_BTN = ("display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box;background:#fff;border:1px solid #B5BAC0;border-radius:8px;"
             "color:#111;font-size:16px;line-height:24px;font-weight:700;padding:11px 12px;white-space:nowrap;cursor:pointer;")   # 흰 버튼 = 가이드라인 10절 `.cm-login` 모양


def stock_left(s, sub_html):
    """종목 줄 왼쪽 — 로고 · 한글 이름(굵게 16) · 보조 줄(회색 14, 이름 글자 선) — `수익` 탭 종목 줄과 같은 간격 · 배치 (2026-11-12 사용자)."""
    return (f'<span style="display:flex;align-items:flex-start;min-width:0;flex:1 1 auto;">'
            f'<span style="flex:none;display:flex;height:24px;align-items:center;">{dk.ticker_logo(s["s"], 22).replace("vertical-align:-4px;", "vertical-align:0;")}</span>'
            f'<span style="min-width:0;">'
            f'<span style="display:block;font-size:16px;line-height:24px;font-weight:700;color:#111;white-space:nowrap;">{esc(s["n"])}</span>'
            f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};white-space:nowrap;">{sub_html}</span></span></span>')


# 연필 · 휴지통 — 아이콘 꼴 규칙(가이드라인 8절: viewBox 16 선 그림 · 선 1.6 · 끝 둥글게). 실제 적용 때 design_kit.ICON_GLYPHS 로 옮긴다
EDIT_GLYPH = '<path d="M10.5 2.5l3 3L6 13H3v-3l7.5-7.5z"/><path d="M9 4l3 3"/>'
TRASH_GLYPH = '<path d="M2.5 4.5h11M6 4.5V3h4v1.5M4 4.5l.7 9h6.6l.7-9"/><path d="M6.8 7v4.5M9.2 7v4.5"/>'
ICON_BTN = ("display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box;width:36px;height:36px;background:#fff;"
            "border:1px solid #E2E8F0;border-radius:8px;color:#111;cursor:pointer;")   # 머리 줄 뒤로 가기 버튼(.pr-back)과 같은 꼴 — 36 · 테두리 #E2E8F0 · 모서리 8 · 그림 20 (2026-11-12 사용자)


def icon_btn(glyph, label):
    return (f'<a data-mock="1" role="button" aria-label="{label}" title="{label}" style="{ICON_BTN}">'
            f'<svg viewBox="0 0 16 16" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{glyph}</svg></a>')


# 아래 고정 입력 칸 — 폰 · 태블릿(900 이하)은 테마 하단 고정 메뉴(71 + 안전 영역) 바로 위, PC 는 화면 맨 아래. 글 폭(--shell 980) 안에 맞춤
SHEET_CSS = ("<style>.ms-sheet{position:fixed;left:0;right:0;bottom:0;z-index:43;display:flex;justify-content:center;pointer-events:none;}"
             ".ms-sheet>details{pointer-events:auto;width:100%;max-width:980px;box-sizing:border-box;background:#fff;border-top:1px solid #E2E8F0;"
             "box-shadow:0 -4px 16px rgba(15,23,42,.08);border-radius:12px 12px 0 0;padding:0 14px 14px;}"
             ".ms-sheet summary{list-style:none;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;padding:12px 0;"
             "color:#111;font-size:14px;line-height:20px;font-weight:700;}"   # 펼치기 버튼(dk.FOLD_IN_CARD) 꼴 — 가운데 14/20 굵게 + 화살표 16
             ".ms-sheet .acc-chev{transform:rotate(180deg);}"   # 위로 열리는 칸이라 닫힘 = 위 화살표, 열림 = 아래 화살표
             ".ms-sheet summary::-webkit-details-marker{display:none;}"
             ".ms-sheet details[open] .acc-chev{transform:none;}"
             ".ms-pad{height:72px;}"
             "@media (max-width:900px){.ms-sheet{bottom:calc(71px + env(safe-area-inset-bottom));}}</style>")


def add_form(held):
    """`종목 관리` 탭 (2026-11-12 사용자): 제목 없음 · 안내 문구 없음.
    ① 지금 보유 종목 = `수익` 탭과 같은 줄 + 오른쪽 아이콘 버튼 연필(고치기) · 휴지통(빼기)
    ② `보유 종목 입력` = 화면 아래 고정 칸, 눌러 열고 닫음(기본 닫힘). 입력 줄(종목 | 수량 | 평균 매수가) 세 줄 ·
       버튼 두 칸 `+ 줄 추가` · `보유 종목 저장`(흰 테두리 버튼) — 10개를 넣어도 저장은 한 번(Firestore 쓰기 1회, 기획 3-2)"""
    sub = lambda s, q, a: esc(f"{q:,}주 · 평균 ") + (esc(money(a, s["m"])) if s["m"] == "us" else won_html(a, 14))
    rows = "".join(
        f'<span style="{dk.MULTI_ROW}{"" if i == 0 else dk.MULTI_SEP}">{stock_left(s, sub(s, q, a))}'
        f'<span style="flex:none;display:flex;gap:6px;">{icon_btn(EDIT_GLYPH, "고치기")}{icon_btn(TRASH_GLYPH, "빼기")}</span></span>'
        for i, (s, q, a) in enumerate(held))
    held_card = f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{rows}</span></div>'

    inp = ("display:block;width:100%;box-sizing:border-box;height:52px;padding:0 12px;border:1px solid #CBD5E1;border-radius:8px;"
           "font-size:18px;line-height:26px;color:#111;background:#fff;min-width:0;")   # 입력 칸 크게 44 → 52 · 글자 16 → 18 (2026-11-12 사용자)
    head = f"font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};"
    COLS = "display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr) minmax(0,1.3fr);gap:6px;"
    lines = "".join(f'<div style="{COLS}margin:0 0 6px;"><input data-mock="1" style="{inp}" placeholder="{ph}"><input data-mock="1" style="{inp}" inputmode="numeric" placeholder="주">'
                    f'<input data-mock="1" style="{inp}" inputmode="decimal" placeholder="$ · 원"></div>'
                    for ph in ("엔비디아 · 005930", "", ""))
    chev = dk.ACC_CHEV
    sheet = (SHEET_CSS + f'<div class="ms-pad"></div><div class="ms-sheet"><details{" open" if not held else ""}>'   # 보유 종목이 없으면 처음부터 열림
             f'<summary><span>보유 종목 입력</span>{chev}</summary>'
             f'<div style="{COLS}margin:0 0 6px;"><span style="{head}">종목</span><span style="{head}">수량</span><span style="{head}">평균 매수가</span></div>'
             f'{lines}'
             f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:6px 0 0;">'
             f'<a data-mock="1" style="{WHITE_BTN}">+ 줄 추가</a><a data-mock="1" style="{WHITE_BTN}">보유 종목 저장</a></div>'
             f'</details></div>')
    return held_card, sheet


def basis_note():
    """카드 아래 오른쪽 한 줄 `블로그 종목 페이지의 종가 기준입니다 ?` — 나머지 안내는 ? 팝업 안 (2026-11-12 사용자: 맨 아래 작은 글씨를 팝업으로)."""
    text = "\n".join([
        "· 수수료 · 세금 : 반영하지 않습니다.",
        f"· 미국 종목 : 금액은 현재 환율(1달러 {FX:,.0f}원)로 원화로 바꾸고, 수익률은 달러 그대로 계산합니다.",
        "· 적어 주신 내용 : 본인만 볼 수 있습니다. 운영자는 열람하지 않으며, 장애 대응 때만 최소한으로 확인합니다.",
        "· 추천 없음 : 공개 페이지의 정보를 보유 종목만 모아 보여 드립니다. 종목 추천이나 매매 판단을 드리지 않습니다.",
        "· 자리 : 60일 동안 열지 않으면 다음 분께 넘기고 적어 주신 내용을 지웁니다."])
    return (f'<div style="display:flex;justify-content:flex-end;align-items:center;margin:-2px 0 12px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};">'
            f'종가 기준입니다{dk.tip(text)}</div>')   # 문구 = `종가 기준입니다` 만 (2026-11-12 사용자)


def leave_link():
    """탈퇴 = `종목 관리` 탭 맨 아래 작은 회색 링크 (안내 글을 팝업으로 옮기며 자리를 옮김)."""
    return f'<p style="{SMALL}text-align:right;margin:12px 0 0;"><a data-mock="1" style="color:{dk.NOTE};text-decoration:underline;">탈퇴하고 내용 지우기</a></p>'


def fine_print(member=True):
    lines = ["계산 기준: 블로그 종목 페이지와 같은 종가입니다. 수수료 · 세금은 반영하지 않습니다. 미국 종목 금액은 현재 환율로 원화로 바꾸고, 수익률은 달러 그대로 계산합니다.",
             "적어 주신 종목 · 수량 · 평균 매수가는 본인만 볼 수 있습니다. 운영자는 열람하지 않으며, 장애 대응 때만 최소한으로 확인합니다.",
             "이 화면은 공개 페이지의 정보를 보유 종목만 모아 보여 드리는 것입니다. 종목 추천이나 매매 판단을 드리지 않습니다.",
             "60일 동안 열지 않으면 자리를 다음 분께 넘기고 적어 주신 내용을 지웁니다."]
    out = "".join(f'<p style="{SMALL}">{esc(t)}</p>' for t in lines)
    if member:
        out += f'<p style="{SMALL}"><a data-mock="1" style="color:{dk.NOTE};text-decoration:underline;">탈퇴하고 내용 지우기</a></p>'
    return f'<div data-related="1" style="margin:32px 0 0;padding:16px 0 0;border-top:1px solid #E2E8F0;">{out}</div>'   # data-related = 테마 탭 밖, 어느 탭에서나 맨 아래 (U5)


def seats_bar(taken):
    w = round(taken / SEATS * 100)
    return (f'<div style="margin:0 0 8px;padding:14px 14px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;"><span style="font-size:17px;line-height:24px;font-weight:700;color:#111;">시범 운영 {SEATS}자리</span>'
            f'<span style="font-size:17px;line-height:24px;font-weight:700;color:#111;">{SEATS - taken}자리 남음</span></div>'
            f'<div style="margin:10px 0 0;height:10px;background:#E2E8F0;border-radius:5px;overflow:hidden;"><div style="width:{w}%;height:100%;background:#111;"></div></div></div>')


def head_label(label=NAME):
    return f'<span data-head-label="{label}" hidden></span>'


MOCK_JS = ("<script>(function(){function go(){var b=document.querySelector('[data-head-label]');if(b){var l=document.querySelector('.post-title-label')||document.querySelector('.post-title');"
           "if(l)l.textContent=b.getAttribute('data-head-label');}document.querySelectorAll('[data-mock]').forEach(function(e){e.addEventListener('click',function(ev){ev.preventDefault();});});}"
           "if(document.readyState==='complete')go();else window.addEventListener('load',go);})();</script>")


def write(body, name, title):
    path = dk.write_mock(head_label() + dk.align_titles(dk.WRAP_OPEN + body + dk.WRAP_CLOSE), os.path.join(OUT, name), title)
    if path:
        pg = open(path, encoding="utf-8").read().replace("</body>", MOCK_JS + "</body>", 1)
        open(path, "w", encoding="utf-8").write(pg)
    print(f"[보유 종목] {name}")


def main():
    os.makedirs(OUT, exist_ok=True)
    st = load()
    held = [(st[k], q, a) for k, (q, a) in HOLD.items() if k in st]
    us = [h for h in held if h[0]["m"] == "us"]
    kr = [h for h in held if h[0]["m"] == "kr"]

    # 로그인 뒤
    body = (dk.cards(grand_card(held))   # 맨 위 = 총액 · 총 수익률. 글 머리 카드(data-lead) — 첫 h2 앞. 테마는 data-lead(없으면 첫 data-cards)부터 첫 h2 전까지를 머리로 옮긴다: h2 뒤에 두면 종목 줄 카드가 맨 아래로 밀렸다
            + stock_rows(us, "us") + stock_rows(kr, "kr") + basis_note()   # 안내 = 맨 끝 카드(종목 줄) 아래 오른쪽 (2026-11-12 사용자)   # 총액 바로 아래 = 보유 종목, 제목 없이 (U1 `보유 종목 n개` 삭제)
            + dk.h2("수익", tab="수익")   # 첫 탭 `수익` — 탭 이름과 같은 제목은 테마가 숨긴다. 머리(총액 · 종목 줄)가 이 첫 탭으로 들어간다 (U5)
            + news_block(held)
            + dk.section("종목 관리", "".join([add_form(held)[0], leave_link(), add_form(held)[1]]), one_line=True, tab="종목 관리"))   # 제목 = 탭 이름과 같게 → 테마가 숨김 (2026-11-12 사용자: `종목 넣기 · 고치기` 제목 삭제)   # 맨 아래 작은 글씨 → 총액 카드 아래 ? 팝업 (2026-11-12 사용자)
    write(body, "mock_my-stocks.html", NAME)

    # 로그인 뒤 · 아직 아무것도 안 적었을 때 — 탭 없이 안내 카드 + 아래 입력 칸 열림 (2026-11-12 사용자: 처음엔 어떻게 보이나)
    empty = (dk.dcard(f'<div style="font-size:17px;line-height:26px;font-weight:700;color:#111;">아직 적어 둔 보유 종목이 없습니다</div>'
                      f'<div style="font-size:15px;line-height:24px;color:#333;margin:4px 0 0;">아래 칸에 종목 · 수량 · 평균 매수가를 적고 저장하면, 여기에 총 평가 금액과 수익률이 보입니다.</div>')
             + add_form([])[1])
    write(empty, "mock_my-stocks-empty.html", NAME)

    # 로그인 전
    what = "".join(f'<li style="margin:0 0 6px;">{esc(t)}</li>' for t in (
        "보유 종목 · 수량 · 평균 매수가를 적어 두면 수익금 · 수익률을 매일 종가로 계산합니다.",
        "보유 종목의 추세 · 다음 실적 발표 · 최근 뉴스를 한 화면에 모아 봅니다.",
        "증권사 계좌는 연결하지 않습니다. 직접 적은 숫자만 씁니다."))
    guest = (f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">보유 종목을 적어 두면, 총액 · 수익률과 그 종목들의 소식을 한 화면에 모아 보여 드립니다.</p>'
             + seats_bar(TAKEN)
             + f'<a data-mock="1" style="{BTN}margin:16px 0 8px;background:#fff;color:#111;border:1px solid #CBD5E1;">{G_LOGO}구글 계정으로 시작하기</a>'
             + f'<p style="{SMALL}text-align:center;padding-left:0;">댓글에 쓰는 로그인과 같습니다. 이름 · 사진은 화면에 보이지 않습니다.</p>'
             + dk.section("무엇을 하나요?", f'<ul style="font-size:{dk.BODY};line-height:{dk.LH_BODY};color:#333;margin:0 0 12px;padding-left:{dk.ALIGN_PX + 22}px;word-break:keep-all;">{what}</ul>', one_line=True)
             + fine_print(member=False))
    write(guest, "mock_my-stocks-guest.html", NAME)

    # 자리 찼음
    full = (f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">시범 운영 {SEATS}자리가 모두 찼습니다.</p>'
            + seats_bar(SEATS)
            + f'<p style="{P}">60일 동안 열지 않은 분의 자리는 비워집니다. 자리가 나면 이 화면에 다시 `구글 계정으로 시작하기`가 보입니다.</p>'
            + fine_print(member=False))
    write(full.replace("`구글 계정으로 시작하기`", "<b style=\"color:#111;\">구글 계정으로 시작하기</b>"), "mock_my-stocks-full.html", NAME)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
