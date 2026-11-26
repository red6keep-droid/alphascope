"""AlphaScope 시황 해설 — 글 화면 그리기 (목업 mock_story.py · 발행기 publish_commentary.py 공용, 2026-11-19 사용자 "목업 확정 → 발행기").

재료 = 수집기 글 columns/{날짜}-{am|pm} (format story, News-doc 23절) + 블로그 묶음 briefing/{날짜}-{am|pm}.json.
모양 = 디자인 가이드라인 14절 `시황 해설`(이 페이지 전용). AI 0 · 네트워크는 종목 페이지 목록(dk.stock_pages)만.

    from story_render import render
    title, html, meta = render(column, briefing, banner_url=…, banner_alt=…)
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, ".."))
sys.path.insert(0, os.path.join(BASE, "..", "kr-stocks"))
import design_kit as dk  # noqa: E402
import universe_kr as UKR  # noqa: E402  한국 종목 페이지 주소

BLOG = "https://www.newfact.app/"
LABELS = {"am": ["증시 시황", "미국 증시"], "pm": ["증시 시황", "한국 증시"]}   # Blogger 라벨 — `증시 시황` 하나로 아침 · 저녁을 모아 본다
REPORT_LABEL = {"am": ("미국 증시 리포트", "%EB%AF%B8%EA%B5%AD%20%EC%A6%9D%EC%8B%9C%20%EB%A6%AC%ED%8F%AC%ED%8A%B8"),
                "pm": ("한국 증시 리포트", "%ED%95%9C%EA%B5%AD%20%EC%A6%9D%EC%8B%9C%20%EB%A6%AC%ED%8F%AC%ED%8A%B8")}
FORECAST_URL = f"{BLOG}search/label/%EC%A6%9D%EC%8B%9C%20%EC%A0%84%EB%A7%9D"
# 지수 이름 (가이드라인 5절 `이름 (의미)`) — 묶음 이름 → 화면 이름
INDEX_NAMES = {"S&P 500": "S&P 500 (대형주)", "나스닥 종합": "나스닥 (기술주)", "나스닥": "나스닥 (기술주)", "다우존스": "다우존스 (우량주)",
               "러셀 2000": "러셀 2000 (소형주)", "코스피": "코스피", "코스닥": "코스닥"}

DOWN_W = r"(?:내리|내린|내려|하락|떨어|급락|빠지|빠졌|줄)"
UP_W = r"(?:오르|올랐|오른|상승|급등|뛰|늘)"
NUM = r"\d+(?:\.\d+)?(?:%p|%)"


def chg(v, unit="%", text=None):
    """증감 = 부호 숫자 + 증감 색 + 굵게. 마무리 fix_colons 가 삼각형(글자의 80% · 위로 1 · 숫자와 2)으로 바꾼다 (가이드라인 5절).
    글자 크기 그대로의 ▲ 를 박는 dk.arrow 는 쓰지 않는다 (2026-11-19 사용자 "삼각형 가이드에 맞나")."""
    if not v:
        return f'<span style="font-weight:700;">0.00{unit}</span>'
    col = dk.UP if v > 0 else dk.DOWN
    num = f"{v:+.2f}" if text is None else ("+" if v > 0 else "-") + text   # 문장 속 숫자는 원문 자릿수 그대로 (`55% 하락` 이 `55.00%` 로 찍히던 것, 2026-11-19)
    return f'<span style="color:{col};font-weight:700;white-space:nowrap;">{num}{unit}</span>'


def directional(html):
    """수집기 꼴 `2.39% 하락` · `0.05%p 상승` · `각각 1.91%, 1.72% 떨어졌다` → 삼각형 + 증감 색 (가이드라인 5절). `보합`은 그대로(삼각형 없음)."""
    def paint(m, up):
        nums = re.sub(r"(\d+(?:\.\d+)?)(%p|%)", lambda n: chg(float(n.group(1)) * (1 if up else -1), n.group(2), n.group(1)), m.group(1))
        return nums + m.group(2)
    for words, up in ((DOWN_W, False), (UP_W, True)):
        html = re.sub(r"((?:" + NUM + r"(?:,\s*)?)+)(\s*(?:씩\s*)?" + words + ")", lambda m, up=up: paint(m, up), html)
    return html


class Linker:
    """기사 속 종목 링크 — 글 전체에서 처음 나온 이름 하나만 보라 #7C3AED (가이드라인 10절). 페이지가 없는 종목은 글자 그대로."""

    def __init__(self, column, briefing, ink=None):
        self.ink = ink or INK
        names = {}
        for m in ((briefing or {}).get("close") or {}).get("movers") or []:
            if m.get("name") and m.get("ticker"):
                names[str(m["ticker"]).upper()] = m["name"]
        self.items = []
        for t in dict.fromkeys([str(x).upper() for x in column.get("tickers") or []] + list(names)):
            name, href = names.get(t), None
            if re.fullmatch(r"\d{6}", t):   # 한국 종목 코드
                sym = next((s for s in UKR.BY_SYM if s.split(".")[0] == t), None)
                if sym:
                    name, href = name or UKR.BY_SYM[sym][1], UKR.page_url(sym)
            else:
                href = dk.stock_href(t)
            if name and href:
                self.items.append((t, name, href))
        self.items.sort(key=lambda x: -len(x[1]))   # 긴 이름 먼저 (`SK하이닉스` 안의 `SK` 같은 겹침)
        self.seen = set()

    def __call__(self, html):
        for t, name, href in self.items:
            if t in self.seen or name not in html:
                continue
            html = re.sub(r"(?<![\w])" + re.escape(name),
                          f'<a href="{dk.esc(href)}" data-stock="{dk.esc(t)}" style="color:{self.ink};font-weight:400;text-decoration:none;">{name}</a>',
                          html, count=1)
            self.seen.add(t)
        return html


# 본문 줄바꿈 = 글자 단위(보통 글처럼) — 테마 .post-body 의 keep-all(띄어쓰기 단위)을 본문 문단에서만 푼다. 머리글 · 제목 영역은 keep-all 그대로
# (2026-11-25 사용자 "뉴스랑 시황 본문은 그냥 텍스트로 줄바꿈 — 요즘 뉴스 기사들처럼, 타이틀 영역은 제외")
BODY_WRAP = "word-break:normal;"


def para(html):
    return f'<p style="margin:0 0 14px;padding:0 0 0 {dk.ALIGN_PX}px;{BODY_WRAP}">{html}</p>'


IDX_CELL_PCT = 44   # 넘기는 지수 칸 폭 = 본문 폭의 44% → 두 칸(88%) + 셋째 칸 12% 걸침
IDX_SLIDE_CSS = "[data-idx-slide]>div::-webkit-scrollbar{display:none}"   # 스크롤 막대만 숨김 — 넘기는 쪽 흐린 그림자는 두지 않는다 (2026-11-19 사용자 "뿌옇게 하는 장치 삭제")


def index_row(indices):
    """지수 칸 — `한눈에 보기` 위, 본문 폭에 딱 맞게 한 화면에 2칸 (2026-11-19 사용자).
    한국 2칸 = 그대로 한 줄. 미국 4칸 = 옆으로 넘기는 줄 — 처음엔 S&P 500 · 나스닥 두 칸 + 다우존스가 오른쪽에 살짝 걸침, 넘기면 다우존스 · 러셀 2000.
    이름(괄호 풀이 포함) = 검정 · 종가 · 증감 = 증감 색(보합 검정) (같은 날 사용자)."""
    cells = []
    for x in indices:
        if x.get("close") is None or x.get("chg_pct") is None:
            continue
        ink = dk.UP if x["chg_pct"] > 0 else dk.DOWN if x["chg_pct"] < 0 else "#111"
        cells.append(f'<span style="font-weight:700;color:#111;font-size:{dk.NAME};line-height:{dk.LH_CARD};white-space:nowrap;display:block;">{dk.paren(dk.esc(INDEX_NAMES.get(x["name"], x["name"])))}</span>'
                     f'<span style="display:block;margin-top:4px;line-height:25px;white-space:nowrap;"><span style="font-size:{dk.NAME};color:{ink};">{x["close"]:,.2f}</span> '
                     f'<span style="font-size:{dk.CHG_SIZE};">{chg(x["chg_pct"])}</span></span>')
    if not cells:
        return ""
    n = len(cells)
    bd, line = dk.CARD_DIR["neutral"][1], dk.card_line("neutral")
    pad = f"padding:{14 - dk.VP}px 12px;"
    if n <= 2:
        inner = "".join(f'<span data-idx-cell="1" style="display:block;flex:1 1 0;min-width:0;box-sizing:border-box;background:#fff;{pad}{"" if k == 0 else f"border-left:1px solid {line};"}">{c}</span>'
                        for k, c in enumerate(cells))
        return (f'<div data-cards="1" style="margin:0 0 8px;"><span style="display:flex;border:1px solid {bd};border-radius:8px;overflow:hidden;">{inner}</span></div>')
    # 넘기는 줄 (2026-11-19 사용자 "가로로 긴 카드 한 장이 좌우로" — 종목 모아보기 업종 아래 탭 줄처럼): 넉 칸이 붙은 긴 카드 한 장(바깥 테두리 · 모서리 = 카드)이
    # 통째로 움직인다. 칸 폭 = 본문 폭의 44% → 처음 두 칸 + 셋째 칸이 오른쪽에 걸치고 카드 오른쪽 끝은 화면 밖(걸친 칸이 넘길 수 있다는 표시 — 흐린 그림자는 두지 않는다)
    w = f"min(calc((100vw - {2 * SIDE_PX}px) * {IDX_CELL_PCT / 100}), 220px)"   # 폰 = 본문 폭(화면 − 좌우 14)의 44% · PC 는 220 상한(PC 는 나중에 따로)
    inner = "".join(f'<span data-idx-cell="1" style="display:block;flex:0 0 auto;width:{w};box-sizing:border-box;background:#fff;{pad}scroll-snap-align:start;'
                    f'{"" if k == 0 else f"border-left:1px solid {line};"}">{c}</span>' for k, c in enumerate(cells))
    return (f'<div data-cards="1" data-idx-slide="1" style="margin:0 0 8px;">'
            f'<div style="overflow-x:auto;margin:0 -{SIDE_PX}px;padding:0 {SIDE_PX}px;scroll-padding:0 {SIDE_PX}px;scroll-snap-type:x proximity;-webkit-overflow-scrolling:touch;scrollbar-width:none;">'
            f'<span style="display:flex;width:max-content;border:1px solid {bd};border-radius:8px;overflow:hidden;">{inner}</span></div></div>')


GROUP_GAP = 10   # 묶음(구획 · 변수 1 · 2 · 3) 사이 +10 (2026-11-19 사용자) — 구획 제목 위 28 → 38, 둘째 변수부터 소제목 위 24 → 34
H2_TOP = 28 + GROUP_GAP
BIG_TOP = H2_TOP + 5   # `장을 움직인 변수` · `업종과 주요 종목` 큰 제목 위 +5 = 43 (2026-11-19 사용자)
INK = "#5012BB"   # 이 글의 보라 글씨(종목 링크 · 색 강조 · 머리글) — #7C3AED 에서 여러 번 진하게(#7637E1 → #7034D6 → #6A31CB → #5F2CB7) 뒤, 10% 진하게 + 채도 0.61 → 0.82 로 선명하게. 흰 바탕 대비 9.8(본문 #333 은 12.6) — 색 글씨가 검은 글씨와 같은 무게로 보이는 자리 (2026-11-19 사용자). 아이콘 · 바탕 보라는 그대로
FLOW_ICON = ("bars", "#059669")   # `업종과 주요 종목` = 강조형 네모(장을 움직인 변수와 같은 꼴), 녹색 = 정리 문장 녹색 카드(#ECFDF5)와 같은 계열 (2026-11-19 사용자)
OVERVIEW_ICON = ("pie", "#DDD6FE", dk.VIOLET)   # `한눈에 보기` = 기본형 원을 보라 카드보다 진하게 (증시 전망 팝업 방향 소제목처럼, 2026-11-19 사용자)
DRIVER_ICON = ("pulse", "#7C3AED")   # `장을 움직인 변수` = 강조형 보라 네모 (옛 `한눈에 보기` 아이콘, 2026-11-19 사용자)
TAKE_BG, TAKE_INK = "#ECFDF5", "#134E4A"   # 정리 문장 카드 = 녹색 확정 — 주식 공부 말풍선 색 (2026-11-19 사용자, 노랑 시안 버림 · 옛 보라 · 그 전 노랑 + 주황)
CARD_GAP = 8   # 이 구획 카드 사이 = 업종 카드 ~ 종목 카드 (ccard · white_card 아래 8)
FLOW_FS, FLOW_LH = "18px", "32px"   # `지수 · 업종 흐름` 문장 = 본문 19 보다 한 단계 작게 (날마다 숫자 · 종목만 바뀌는 글, 2026-11-19 사용자)
LISTS_URL = f"{BLOG}p/stock-lists.html"   # 종목 모아보기 — 업종 탭(히트맵) · 오늘 움직임 탭으로 보낸다 (2026-11-19 사용자)
TOP_N = 3   # 시황 글에는 3줄만, 나머지는 종목 모아보기로 (사용자 결정 — 잘린 줄이 가는 곳 = 그 페이지 탭)
SIDE_PX = 14   # 폰 본문 좌우 여백 — 배너를 화면 끝까지 (2026-11-19 사용자 "카드 말고 좌우 꽉 차게")


# 장 분위기 색 테마 (2026-11-20 사용자 "A안으로 적용" = 기본값 "flow"): 상승 = 주황 · 하락 = 파랑 · 보합 = 지금 보라. 머리글 색(MOOD_INK)은 그대로.
# 숫자 증감 색(빨강 #d93025 · 파랑 #1a73e8)과 겹치지 않게 글씨는 한 단계 진하게 — 주황 #A8400C(흰 바탕 대비 6.2) · 파랑 #1E40AF(8.7) · 보라 #5012BB(9.8).
# theme = None(옛 화면: 보라 + 업종 녹색) · "body"(한눈에 보기 · 장을 움직인 변수 · 종목 링크 · 색 강조) · "flow"(body + 업종과 주요 종목 아이콘 · 제목 · 정리 카드)
MOOD_THEME = {
    "up":   {"ink": "#A8400C", "solid": "#EA580C", "soft": ("#FED7AA", "#C2410C"), "card": dk.CARD_DIR["positive"][0], "take": (dk.CARD_DIR["positive"][0], "#7C2D12")},
    "down": {"ink": "#1E40AF", "solid": "#2563EB", "soft": ("#BFDBFE", "#1D4ED8"), "card": dk.CARD_DIR["negative"][0], "take": (dk.CARD_DIR["negative"][0], "#1E3A8A")},
    "flat": {"ink": INK, "solid": DRIVER_ICON[1], "soft": OVERVIEW_ICON[1:], "card": dk.CARD_DIR["uncertain"][0], "take": (dk.CARD_DIR["uncertain"][0], "#3B0F8C")},
}


def tinted(sec, color):
    """구획 제목 글자 색 = 앞 강조형 아이콘 색 (2026-11-19 사용자: 장을 움직인 변수 보라 · 업종과 주요 종목 녹색)."""
    return re.sub(r'(<h2[^>]*? style="[^"]*?)color:#111;', lambda m: m.group(1) + f"color:{color};", sec, count=1)


# 머리글 앞 장 분위기 아이콘 (2026-11-19 사용자가 그린 그림 셋, static/mood/ 96px 무손실 WebP · 각 3KB 안팎) — 캐릭터 대신
# 고르기 = 대표 지수(첫 칸: 코스피 · S&P 500) 등락: +0.3% 이상 상승 마감 · −0.3% 이하 하락 마감 · 그 사이 혼조 마감.
# 기준 실측(최근 10년): 혼조 = 코스피 27% · S&P 500 35% (±0.5% 면 미국 절반이 혼조라 너무 잦다). 사람이 고르지 않는다
MOOD_BASE = "https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/images/commentary/mood/"
MOOD_CUT = 0.3
MOOD_NAME = {"up": "상승 마감", "flat": "혼조 마감", "down": "하락 마감"}
MOOD_GAP = 15   # 아이콘 ~ 머리글 글자 (10 → 15, 2026-11-19 사용자)
MOOD_TOP = 11   # 줄 가운데에서 아래로 11 — 글자 윗선 맞춤(3) 뒤 사용자 "5 내려" · "3 더 내려" (2026-11-19)
MOOD_PX = 34   # 머리글 22/32 첫 줄 가운데 · 글자와 10 — 28 에서 20% 크게(33.6 → 34, 2026-11-19 사용자). 줄 높이 32 칸 안 가운데라 위아래 1 씩 넘친다
# 머리글 글자 색 = 아이콘 방향 색 (2026-11-19 사용자): 블로그가 늘 쓰는 증감 색 진하기(dk.UP #d93025 · dk.DOWN #1a73e8, 흰 바탕 대비 4.5 이상) · 혼조 = 거의 검정.
# 아이콘 화살표 색(#FF6768 · #2A8FFF · #A7A7A7)을 그대로 쓰는 시안은 흐려서(대비 2.4 ~ 3.3) 버림
MOOD_INK = {"up": dk.UP, "down": dk.DOWN, "flat": "#222"}


def mood_of(indices):
    cp = next((x["chg_pct"] for x in indices if x.get("chg_pct") is not None), None)
    if cp is None:
        return None
    return "up" if cp >= MOOD_CUT else "down" if cp <= -MOOD_CUT else "flat"


def iconed(sec, icon):   # 아이콘 ~ 글자 = h2 gap 10 + 1 = 11 (옛 −4 → 6, 2026-11-19 사용자 +5)
    """구획 제목 앞 아이콘. icon = 그림 이름(기본형 회색 원 22 · 글자와 6) 또는 이미 그린 HTML. 구획 제목 위 여백 +10."""
    ic = icon if icon.startswith("<") else dk.soft_icon(icon)
    sec = sec.replace("margin:28px 0 11px;", f"margin:{H2_TOP}px 0 11px;", 1)
    sec = re.sub(r'(<h2[^>]*? style="[^"]*?)padding:0;', lambda m: m.group(1) + f"padding:0 0 0 {dk.ALIGN_PX}px;", sec, count=1)   # 제목 시작(아이콘) = 본문 글자 시작선 6 (2026-11-19 사용자). 밑줄은 그대로 끝까지
    return re.sub(r"(<h2[^>]*>)", lambda m: m.group(1) + f'<span style="flex:none;display:flex;align-self:center;margin-right:1px;">{ic}</span>', sec, count=1)


WHO_PAREN = re.compile(r"\(([^()<>]{2,40}?(?:연구원|대표|애널리스트|증권|총재|이사|기자|매니저|최고경영자|CEO|장관|위원|교수|이코노미스트|전략가|연구소|리서치|캐피털|파리바|트러스트|은행|운용|연은|회장|사장|의장|창업자|파트너)[^()<>]{0,20})\)")
WHO_FS, WHO_INK = "17px", "#6B7280"   # 말한 사람 소속 · 직함 괄호 = 본문 19 − 2 · 회색 (2026-11-19 사용자 `(이창민 KB증권 연구원)` · `(하나증권)`)


def who(html):
    """말한 사람 소속 · 직함 괄호(괄호 포함)를 한 단계 작은 회색으로. 소속 낱말이 든 괄호만 — `(FTA)` 같은 약어 풀이는 그대로."""
    return WHO_PAREN.sub(lambda m: f'<span style="font-size:{WHO_FS};color:{WHO_INK};">({m.group(1)})</span>', html)


def take_away(text):
    """정리 문장(`이는 · 이 같은 · 이처럼 · 결국 …`)은 따로 카드가 되므로 앞 지시어를 떼고, `…음을 보여준다` 는 그 일 자체로 (2026-11-19 사용자 "이 문장이 이상해").
    `이 같은 업종 간 차이는` → `업종 간 차이는`. 수집기에는 처음부터 혼자 읽히는 문장으로 써 달라고 부탁함."""
    t = re.sub(r"^(?:이는|이처럼|결국|이 같은|이러한|이런)\s*,?\s*", "", text.strip())
    t = re.sub(r"(\S)음을 보여(?:준다|줍니다)\.$", r"\1다.", t)
    return t


def small_h2(sec):
    """구획 제목을 강조 카드 안 그래프 제목 크기(dk.NAME 16 · 행간 24 굵게)로 — 지수 · 업종 흐름 · 업종별로 볼 것 · 관전 포인트 (2026-11-19 사용자, `장을 움직인 변수` 는 22 그대로).
    폰 테마가 h2 에 20/26 !important 를 걸어서 글자는 안쪽 span 이 갖는다 (h2 는 flex 라 span 이 블록이 되어 행간도 span 것)."""
    return re.sub(r"(<h2[^>]*>)(.*?)(</h2>)", lambda m: f'{m.group(1)}{small_title(m.group(2))}{m.group(3)}', sec, count=1, flags=re.S)


def small_title(html):
    return f'<span style="font-size:{dk.NAME};line-height:{dk.LH_CARD};">{html}</span>'


def head_row(icon_html, title, tag="h2", margin="0 0 8px"):
    """카드 안 제목 줄 = 아이콘 + 16/24 굵게 (`한눈에 보기` · `관전 포인트` · `핵심 한 줄`)."""
    return (f'<{tag} style="display:flex;align-items:center;gap:6px;margin:{margin};padding:0;font-weight:700;color:#111;">'
            f'{icon_html}{small_title(title)}</{tag}>')


EMPH_MARK = re.compile(r"\*\*(.+?)\*\*", re.S)
TONE_MARK = re.compile(r"==(.+?)==", re.S)
TONE_INK = INK   # 색 글씨 강조 = 보라 하나로 통일 (2026-11-19 사용자 "빨간색 쓰지 말고 보라로" — 옛 주황 #C2410C)


def emph(html, on=True, tone=None):
    """문장 속 강조 두 가지 (2026-11-19 사용자 "굵게 하나, 굵지 않은 색 글씨 하나") — 수집기 표시, 한눈에 보기 · 장을 움직인 변수만.
    `**말**` = 굵게 #111 = 결과(무슨 일이 일어났나) · `==말==` = 보라 글씨(굵지 않게) = 원인 · 변수. 다른 칸에 온 표시는 지운다.
    증감 색 · 종목 링크를 먼저 칠한 뒤 바꾼다(dk.tint 는 태그가 든 덩어리를 건너뛰므로). 굵게 안의 종목 링크도 굵게."""
    if not on:
        return TONE_MARK.sub(r"\1", EMPH_MARK.sub(r"\1", html)).replace("**", "").replace("==", "")
    html = EMPH_MARK.sub(lambda m: '<b style="font-weight:700;color:#111;">' + m.group(1).replace("font-weight:400;", "font-weight:700;") + "</b>", html)
    html = TONE_MARK.sub(lambda m: f'<span style="color:{tone or TONE_INK};">{m.group(1)}</span>', html)
    return html.replace("**", "").replace("==", "")   # 짝이 안 맞아 남은 표시는 지운다(글자로 보이지 않게)


def points(items, link, pad=dk.ALIGN_PX):
    rows = []
    for p in items:
        when, _, what = p.partition(" — ") if " — " in p else ("", "", p)
        if re.fullmatch(r"\d{1,2}:\d{2}", when.strip()) and "첫 반응" in what:
            when = ""   # 장 시작 줄의 시각은 뺀다 (2026-11-19 사용자 "고정이면 삭제")
        lead = f'<b style="color:#111;">{dk.esc(when)}</b> : ' if when else ""
        rows.append(dk.dot_li(lead + emph(link(directional(dk.tint(dk.esc(what)))), False), lh=32, margin="12px 0").replace("font-size:18px;", "", 1))   # 행간 35 → 32 (2026-11-26 사용자 "3픽셀 줄여") — dot_li 가 행간 32 에 박는 18px 은 뺀다(글자는 ul 의 본문 −1)
    return f'<ul style="list-style:none;margin:-12px 0;padding:0 0 0 {pad}px;font-size:calc(1em - 1px);{BODY_WRAP}">{"".join(rows)}</ul>'   # 줄바꿈 = 본문처럼 글자 단위 (2026-11-26 사용자 "관전 포인트도 단어 말고 글자로")   # 글자 = 본문보다 1 작게(PC 19 → 18 · 폰 16 → 15, 2026-11-26 사용자 "관전 포인트 한 포인트 작게") · 음수 = 첫 · 끝 줄 12 지우기 (카드 안)


def md(iso):
    y, m, d = iso.split("-")
    return int(m), int(d)


def titles(column):
    """(화면 제목 줄, 저장 제목) — `11.17 증시 시황` · `11.17 증시 시황 : 그날 주제` (가이드 14절)."""
    m, d = md(column["date"])
    line = f"{m}.{d:02d} 증시 시황"
    return line, f"{line} : {column['title'].strip()}"


def out_btn(label, href):
    """블로그 안 다른 페이지로 가는 버튼 (가이드라인 10절, nvda-report render_html.out_btn 과 같은 꼴) — 흰 외곽선 · 14 굵게 · 높이 38 · 오른쪽 나가는 아이콘 · 같은 창."""
    return (f'<a href="{dk.esc(href)}" data-row-link="1" style="display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 12px;margin:0 0 8px;background:#fff;border:1px solid #E2E8F0;'
            f'border-radius:8px;font-size:{dk.TINY};line-height:{dk.LH_TINY};font-weight:700;color:#111;text-decoration:none;"><span>{dk.esc(label)}</span>{dk.OUT_ICON}</a>')


LIST_ROW_PAD = 16   # 종목 줄 위아래 = 종목 모아보기 줄(stock_lists.js ROW 16)
LOGO_Z, LOGO_GAP = 35, 11   # 종목 모아보기 로고 35 · 이름과 11


def logo(t, row):
    """종목 모아보기 줄 로고 (stock_lists.js logo) — 우리 gh-pages 로고, 없으면 티커 글자 배지(같은 색 고르기)."""
    st = f"display:inline-block;width:{LOGO_Z}px;height:{LOGO_Z}px;border-radius:50%;margin-right:{LOGO_GAP}px;"
    if row and row.get("lg"):
        return (f'<img src="{dk.LOGO_BASE}{dk.esc(row["lg"])}?v={dk.LOGO_VER}" alt="" width="{LOGO_Z}" height="{LOGO_Z}" loading="lazy" '
                f'style="{st}background:#fff;object-fit:cover;outline:1px solid #E2E8F0;outline-offset:-1px;">')
    bg, ink = dk.BADGE_COLORS[sum(map(ord, str(t))) % len(dk.BADGE_COLORS)]
    return (f'<span aria-hidden="true" style="{st}line-height:{LOGO_Z}px;background:{bg};color:{ink};font-size:15px;font-weight:700;text-align:center;overflow:hidden;">'
            f'{dk.esc(re.sub(r"[-.]", "", str(t))[:2])}</span>')


def _pct2(v, unit="%"):
    return f"{abs(v):.2f}{unit}".replace(".00", "") if v is not None else ""


def cmp_bits(chg, base, base_chg, usual=None):
    """종목 이름 아래 회색 비교 줄(헌법 제1조) — Newfact 뉴스 · 시황 같이 씀. `코스피보다 0.32%p 더 상승` · `평소 하루 움직임(1.6%)의 1.4배`.
    base = 비교 지수 이름(한국 = 코스피, 미국 = S&P 500), usual = 직전 60거래일 하루 등락률 절댓값 중앙값(없으면 둘째 줄 없음). 줄마다 한 비교."""
    bits = []
    wa = base + ("과" if base.endswith("500") else "와")   # S&P 500(오백)과 · 코스피와
    if chg is not None and base_chg is not None:
        v = round(chg - base_chg, 2)
        if abs(v) < 0.005:
            bits.append(f"{wa} 같은 폭")
        elif chg * base_chg < 0:   # 방향이 반대인 날
            bits.append(f'{wa} 반대로 {"상승" if chg > 0 else "하락"}')   # 상승 · 하락 (헌법 제10조)
        elif chg >= 0 and base_chg >= 0:
            bits.append(f'{base}보다 {_pct2(v, "%p")} {"더" if v > 0 else "덜"} 상승')
        else:
            bits.append(f'{base}보다 {_pct2(v, "%p")} {"더" if v < 0 else "덜"} 하락')
    if usual and chg is not None:
        r = abs(chg) / usual
        bits.append(f'평소 하루 움직임({_pct2(usual)})' + (f"의 {r:.1f}배" if r >= 1.5 else "과 비슷" if r >= 0.5 else "보다 작음"))
    return bits


def stock_row(x, row, slot, first, inline_sub=False, small=False, below=""):
    """종목 줄 = 종목 모아보기 규칙 (2026-11-19 사용자 "그 규칙으로 통일"): 로고 35 · 이름 16 굵게 · 보조 줄 14 회색(한국 = 업종, 미국 = 티커 · 업종) │ 오른쪽 증감 17 굵게 위 · 가격 15 증감 색 아래. 줄 전체가 그 종목 페이지로."""
    t, v = str(x.get("ticker") or ""), x["chg_pct"]
    sec = (row or {}).get("s") or ""
    sub = sec if slot == "pm" else " · ".join(y for y in (t, sec) if y)
    price = ""
    if row and row.get("p") is not None:
        p = row["p"]
        price = f"${p:,.2f}" if slot == "am" else f"{round(p):,}원"
    col = dk.UP if v > 0 else dk.DOWN if v < 0 else "#111"
    if inline_sub:   # 업종(보조 줄)을 이름 옆 같은 줄에 — 줄바꿈 없이 (2026-11-25 사용자, Newfact 뉴스 관련 정보 칸만)
        # 이름 줄 = 오른쪽 증감 줄과 같은 가로선 (2026-11-26 사용자 "엔비디아 위치는 고정하고 증감을 내려"): 이름은 옛 자리(오른쪽 두 줄 44 의 가운데 = 위에서 22) 그대로 — 왼쪽 묶음(35) 위 4.5 · 오른쪽 증감 줄(24) 위 10 → 증감 가운데도 22
        # below = 이름 아래 회색 비교 줄(뉴스) — 왼쪽 칸 안에 두어 오른쪽 증감 · 가격 높이와 상관없이 이름과의 간격이 고정 (2026-11-26 사용자 "왜 더 벌어졌나")
        left = (f'<span style="display:flex;align-items:flex-start;min-width:0;flex:1 1 auto;margin-top:4.5px;"><span style="flex:none;display:flex;align-items:center;">{logo(t, row)}</span>'
                f'<span style="min-width:0;flex:1 1 auto;margin-top:5.5px;"><span style="display:block;font-size:16px;line-height:24px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                f'<span style="font-weight:700;color:#111;">{dk.esc(x["name"])}</span>'
                + (f'<span style="margin-left:6px;font-size:{dk.TINY};color:#6B7280;">{dk.esc(sub)}</span>' if sub else "") + '</span>'
                + (f'<span style="display:block;margin-top:6px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:#6B7280;white-space:normal;word-break:keep-all;">{below}</span>' if below else "")
                + '</span></span>')
    else:
        left = (f'<span style="display:flex;align-items:center;min-width:0;flex:1 1 auto;"><span style="flex:none;display:flex;align-items:center;">{logo(t, row)}</span>'
                f'<span style="min-width:0;"><span style="display:block;font-size:16px;line-height:24px;font-weight:700;color:#111;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{dk.esc(x["name"])}</span>'
                + (f'<span style="display:block;font-size:{dk.TINY};line-height:20px;color:#6B7280;white-space:nowrap;">{dk.esc(sub)}</span>' if sub else "") + '</span></span>')
    cs, ps = (16, 14) if small else (int(dk.CHG_SIZE[:-2]), 15)   # 증감 · 가격 1px 작게 (2026-11-25 사용자, 뉴스 관련 정보 칸만)
    right = (f'<span style="flex:none;display:flex;flex-direction:column;align-items:flex-end;white-space:nowrap;{"margin-top:10px;" if inline_sub else ""}">'
             f'<span style="font-size:{cs}px;line-height:24px;">{chg(v)}</span>'
             + (f'<span style="font-size:{ps}px;line-height:20px;color:{col};">{price}</span>' if price else "") + '</span>')
    href = (row or {}).get("u") or (dk.stock_href(t) if not re.fullmatch(r"\d{6}", t) else "")
    attr = f' data-row-link="1" data-href="{dk.esc(href)}"' if href else ""
    sep = "" if first else "border-top:1px solid #E2E8F0;"
    return (f'<span{attr} style="display:flex;justify-content:space-between;gap:12px;padding:{LIST_ROW_PAD}px 12px;white-space:nowrap;line-height:24px;align-items:{"flex-start" if inline_sub else "center"};{sep}">'
            f'{left}{right}</span>')


def card_btn(label, href, pad):
    """카드 안 맨 아래 줄 = 다른 페이지로 가는 줄 (2026-11-19 사용자 "버튼을 카드 안으로") — 구분선 위 · 14 굵게 · 글자 + 나가는 아이콘을 가운데 정렬(사용자, 옛 오른쪽 정렬), 줄 전체가 링크."""
    return (f'<a href="{dk.esc(href)}" data-row-link="1" style="display:flex;justify-content:center;align-items:center;gap:8px;padding:{pad}px 12px;'
            f'border-top:1px solid #E2E8F0;font-size:{dk.TINY};line-height:{dk.LH_TINY};font-weight:700;color:#111;text-decoration:none;"><span>{dk.esc(label)}</span>{dk.OUT_ICON}</a>')


def white_card(inner):
    return f'<div data-cards="1" style="margin:0 0 8px;"><span style="display:block;background:#fff;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;">{inner}</span></div>'


def sector_name(x, check):
    """업종 줄 왼쪽 = 업종 그림(기본형 회색 원, 종목 로고와 같은 35 · 이름과 11) + 이름 16 굵게 │ 볼 것 14 회색 (2026-11-19 사용자).
    볼 것은 이름 옆에 이어 쓰고 칸이 모자랄 때만 저절로 다음 줄로 — 둘째 줄은 그림 아래로 들어가지 않는다. 그림이 없는 업종 이름은 추세선."""
    ic = dk.soft_icon(dk.sector_icon_name(x["name"]) or ("trend" if x["chg_pct"] >= 0 else "trend_down"), LOGO_Z)
    sub = (f'<span style="font-weight:400;color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};">{dk.VSEP}{check}</span>') if check else ""
    return (f'<span style="display:flex;align-items:center;gap:{LOGO_GAP}px;"><span style="flex:none;display:flex;">{ic}</span>'
            f'<span style="min-width:0;">{dk.esc(x["name"])}{sub}</span></span>')


def render(column, briefing, banner_url=None, banner_alt="", lists_live=True, lists=None, mood_base=MOOD_BASE, theme="flow"):
    """→ (저장 제목, 본문 HTML, meta). 수집기 칸이 비면 그 구획만 뺀다.
    mood_base = 장 분위기 아이콘 폴더 주소(None = 아이콘 없이 — 발행기가 그림이 아직 안 올라간 걸 알면 None).
    lists = 종목 모아보기 목록 파일 rows 를 티커로 찾는 표 {티커: 줄} — 종목 줄 가격 · 로고 · 업종 · 주소. 없으면 배지 · 가격 없이.
    lists_live = 종목 모아보기 페이지가 떠 있나. 떠 있으면 업종 · 종목 표는 3줄 + 그 페이지로 가는 버튼, 아니면 전부 싣고 5줄 뒤 접기(버릴 곳이 없으므로)."""
    col, br = column, briefing or {}
    slot = col["slot"]
    close = br.get("close") or {}
    indices = close.get("indices") or []
    th = MOOD_THEME[mood_of(indices) or "flat"] if theme else None   # 장 분위기 색 (시안). 아이콘이 없어도 지수로 고른다
    ink = th["ink"] if th else INK
    link = Linker(col, br, ink)

    def prose(text, strong=False):
        return who(emph(link(directional(dk.tint(dk.esc(dk.formal(text or ""))))), strong, ink))

    _, stored = titles(col)
    m, d = md(col["date"])
    td = br.get("trade_date") or col["date"]
    tm, tdd = md(td)
    basis = f'{tm}.{tdd:02d} {"미국" if slot == "am" else "한국"} 종가'   # 제목 줄 오른쪽 기준 줄 (테마가 [data-title-basis] 를 옮김)
    # 제목 줄(.pr-sticky) 아래 구분선 · 여백 14 를 이 글에서만 없앤다 — 배너가 제목 줄에 바로 붙게 (2026-11-19 사용자). 테마는 그대로
    # 표시 = 머리글의 data-headline (이 글에만 있음). data-commentary 는 테마가 기준 줄을 제목 줄로 옮길 때 사라져 쓰지 못한다
    # + 고정 제목 줄의 흰 바탕을 좌우 본문 여백(14)만큼 화면 끝까지 — 꽉 찬 배너가 스크롤로 밑을 지날 때 양옆 틈으로 비치지 않게 (같은 날 사용자)
    style = ('<style>body:has([data-headline]) .pr-sticky{border-bottom:0;margin-bottom:0;'
             f'box-shadow:-{SIDE_PX}px 0 0 var(--surface,#fff),{SIDE_PX}px 0 0 var(--surface,#fff);}}' + IDX_SLIDE_CSS + '</style>')
    body = [style + f'<p data-title-basis="1" data-commentary="{dk.esc(col["date"])}-{slot}" data-rev="{dk.esc(str(col.get("rev") or ""))}" style="margin:0 0 14px;font-size:13px;line-height:19px;color:#6B7280;">{basis}</p>']
    if banner_url:
        body.append(f'<figure data-bleed="1" style="margin:0 -{SIDE_PX}px 16px;"><img src="{dk.esc(banner_url)}" alt="{dk.esc(banner_alt or "AI 생성 이미지")}" '
                    f'width="900" height="374" style="display:block;width:100%;height:auto;border-radius:0;"></figure>')   # 테마 글 그림 모서리 12 를 끔
    head_txt = emph(directional(dk.tint(dk.esc(col["title"]))), False)   # 캐릭터는 넣지 않는다 (2026-11-19 사용자 "유아틱 · 전문가스러워야") — 대신 장 분위기 아이콘
    mood = mood_of(indices) if mood_base else None
    head_ink = MOOD_INK[mood] if mood else INK   # 아이콘이 없으면 보라 그대로
    if mood:   # 아이콘 = 첫 줄 가운데(줄 높이 32 칸 안), 둘째 줄은 아이콘 아래로 들어가지 않는다
        head_txt = (f'<span style="display:flex;align-items:flex-start;gap:{MOOD_GAP}px;"><span style="flex:none;display:flex;align-items:center;height:32px;">'
                    f'<img src="{dk.esc(mood_base)}market-{mood}.webp" alt="{MOOD_NAME[mood]}" title="{MOOD_NAME[mood]}" width="{MOOD_PX}" height="{MOOD_PX}" '
                    f'style="display:block;position:relative;top:{MOOD_TOP}px;width:{MOOD_PX}px;height:{MOOD_PX}px;border-radius:0;"></span><span style="min-width:0;">{head_txt}</span></span>')
    body.append(f'<h2 data-headline="1" style="margin:0 0 22px;padding:10px 0 0 {dk.ALIGN_PX}px;font-size:22px;line-height:32px;font-weight:700;color:{head_ink};'
                f'word-break:keep-all;">{head_txt}</h2>')
    # 같은 말 되풀이 없애기 (2026-11-19 사용자): 머리글 = 주제 한 번. 요약 문장(summary) · 핵심 한 줄(oneLine)은 화면에 올리지 않는다(머리글과 같은 말).
    # 글 머리 문단 표시(data-seo-lead · data-lead)는 `한눈에 보기` 문단이 맡는다. 한눈에 보기가 없는 글만 요약 문장을 올린다.
    lead_attr = 'data-seo-lead="1" data-lead="1" '
    body.append(index_row(indices))   # 지수 = 한눈에 보기 위 (2026-11-19 사용자)

    def soft_card(inner, head="", margin="0 0 8px", bg=dk.CARD_DIR["neutral"][0], pad=(18, 14), style="", attr="", left=None):
        return (f'<div style="background:{bg};border-radius:10px;padding:{pad[0] - dk.VP}px {pad[1]}px {pad[0] - dk.VP}px {pad[1] if left is None else left}px;margin:{margin};">'
                f'{head}<p {attr}style="margin:0;{BODY_WRAP}{style}">{inner}</p></div>')

    if col.get("overview"):   # 안쪽 여백 +5 (보이는 23 · 좌우 19)
        sb, si = th["soft"] if th else OVERVIEW_ICON[1:]
        head = head_row(dk.soft_icon(OVERVIEW_ICON[0], bg=sb, ink=si), "한눈에 보기")
        body.append(soft_card(prose(col["overview"], True), head, "8px 0 8px", th["card"] if th else dk.CARD_DIR["uncertain"][0], pad=(23, 19), attr=lead_attr))
    else:
        body.append(f'<p {lead_attr}style="{dk.SEO_LEAD}{BODY_WRAP}padding:0 0 0 {dk.ALIGN_PX}px;">'
                    f'{m}월 {d}일 {"아침" if slot == "am" else "저녁"}, {prose(col.get("summary") or "")}</p>')

    # 이유가 먼저 (시황 = 왜 움직였나), 숫자는 그 아래 표로
    drivers = [x for x in col.get("drivers") or [] if x.get("heading") and x.get("body")]
    if drivers:
        def sub(i, x):   # 소제목 시작 = 본문 글자 시작선 6 (2026-11-19 사용자)
            h = dk.sub_label(f'{i}. {dk.esc(x["heading"])}').replace("font-weight:700;margin:", f"font-weight:700;padding-left:{dk.ALIGN_PX}px;margin:", 1)
            return h if i == 1 else h.replace("margin:24px 0 10px;", f"margin:{24 + GROUP_GAP}px 0 10px;", 1)
        drv = "".join(sub(i, x)
                      + para(prose(x["body"], True)) for i, x in enumerate(drivers, 1))
        dc = th["solid"] if th else DRIVER_ICON[1]
        body.append(tinted(iconed(dk.section("장을 움직인 변수", drv, line=False), dk.solid_icon(DRIVER_ICON[0], dc)), dc).replace(f"margin:{H2_TOP}px 0 11px;", f"margin:{BIG_TOP}px 0 11px;", 1))

    # 지수 · 업종 흐름 = 숫자는 문장이 아니라 표 (2026-11-19 사용자 "숫자 나열 문장은 표로"). 묶음 숫자로 파이썬이 그린다 — 수집기 market 문단은 쓰지 않는다.
    # 업종 = 묶음 전체(크게 움직인 것부터, 5줄 + 접기) · 보조 줄 = 수집기 sectors[].check(다음 장에서 볼 것, 있는 업종만). 종목 = 묶음 movers 전체(크게 움직인 것부터, 5줄 + 접기).
    checks = {x.get("name"): x.get("check") or "" for x in col.get("sectors") or []}
    cp0 = next((x["chg_pct"] for x in indices if x.get("chg_pct") is not None), 0) or 0
    down_day = cp0 < 0   # 대표 지수가 내린 날은 많이 내린 업종부터 — 다 같이 내린 날 `오른 업종 3개` 는 덜 내린 업종이 된다
    secs = sorted([x for x in close.get("sectors") or [] if x.get("name") and x.get("chg_pct") is not None], key=lambda x: x["chg_pct"] if down_day else -x["chg_pct"])
    if not secs:   # 묶음에 업종이 없으면 수집기 것
        secs = [x for x in col.get("sectors") or [] if x.get("name") and x.get("chg_pct") is not None]
    movers = sorted([x for x in close.get("movers") or [] if x.get("name") and x.get("chg_pct") is not None], key=lambda x: -abs(x["chg_pct"]))
    pad = dk.SEP_GAP - 5 - 1   # 업종 줄 구분선 위아래 보이는 22 → 17
    mq = "?m=" + ("us" if slot == "am" else "kr")
    lists = lists or {}

    def tail(btn, tab):   # 3줄만 싣고 나머지는 종목 모아보기 탭으로 — 카드 안 맨 아래 줄
        return card_btn(btn, f"{LISTS_URL}{mq}#tab-{tab}", pad - dk.VP)

    wrap_up = str(col.get("takeaway") or "").strip()   # 수집기 새 칸(요청 26절). 없으면 옛 글의 market 끝 지시어 문장을 떼어 고침
    if not wrap_up:
        sents = re.split(r"(?<=다\.)\s+", (col.get("market") or "").strip())
        if len(sents) > 1 and re.match(r"(이는|이 같은|이처럼|이러한|결국)", sents[-1]):
            wrap_up = take_away(sents[-1])
    mk = ""
    if wrap_up:   # 정리 문장 = 구획 제목 바로 아래 (2026-11-19 사용자). 글씨 = 주식 공부와 같이 굵게
        plain = emph(directional(dk.tint(dk.esc(dk.formal(wrap_up)))), False)   # 종목 링크 · 보라 없이 전부 녹색 글씨 (2026-11-19 사용자)
        tb, ti = th["take"] if theme == "flow" else (TAKE_BG, TAKE_INK)
        mk += soft_card(plain, margin=f"0 0 {CARD_GAP}px", bg=tb, left=14 + 5 + 3,   # 글 앞 여백 +5 +3 = 22 (2026-11-19 사용자)
                          style=f"font-size:{FLOW_FS};line-height:{FLOW_LH};font-weight:700;color:{ti};")
    if secs:   # 업종 = 흰 카드 줄(구분선 17), 제목 줄 없음 (2026-11-19 사용자 "많이 오른 업종 같은 타이틀 삭제")
        rows = [(sector_name(x, emph(dk.esc(checks.get(x["name"]) or ""), False)), f'<span style="font-size:16px;">{chg(x["chg_pct"])}</span>', "", 78) for x in secs]   # 왼쪽 78% — 볼 것이 이름 옆 한 줄에 들어갈 자리 · 증감 16 = 아래 종목 줄 증감(stock_row small)과 같게 (2026-11-26 사용자, ccard 기본 17)
        if lists_live:
            c = dk.ccard(rows[:TOP_N], pad=pad)
            k = c.rindex("</span></div>")
            mk += c[:k] + tail("업종 전체 보기", "업종") + c[k:]
        else:
            mk += dk.ccard(rows, pad=pad, fold_at=5 if len(rows) > 6 else None, noun="업종")
    if movers:   # 종목 = 종목 모아보기 줄 규칙. 페이지가 없으면 자르지 않고 전부(접기 없이 — 버릴 곳이 없으므로)
        shown = movers[:TOP_N] if lists_live else movers
        # 줄 모양 = Newfact 뉴스 관련 정보와 같게 (2026-11-26 사용자 "시황 종목도 이런 디자인과 구성으로"): 업종을 이름 옆 · 증감 16 · 가격 14 · 이름 아래 회색 비교 줄
        bname = "S&P 500" if slot == "am" else "코스피"
        bchg = next((x["chg_pct"] for x in indices if x.get("name") == bname and x.get("chg_pct") is not None), None)
        def usual(x):   # 평소 하루 움직임 = 목록 파일 w — 목록 날짜가 이 장 날짜와 같을 때만(다른 날 기준이면 둘째 줄 없이)
            r = lists.get(str(x.get("ticker") or "").upper()) or {}
            return x.get("usual") or (r.get("w") if r.get("d") == td else None)
        inner = "".join(stock_row(x, lists.get(str(x.get("ticker") or "").upper()), slot, i == 0, inline_sub=True, small=True,
                                  below="<br>".join(dk.esc(y) for y in cmp_bits(x["chg_pct"], bname, bchg, usual(x))))
                        for i, x in enumerate(shown))
        mk += white_card(inner + (tail("오늘 움직인 종목 전체 보기", "오늘 움직임") if lists_live else ""))
    if mk:
        # 제목 = 내용대로 `업종과 주요 종목`(옛 `지수 · 업종 흐름` — 지수 칸은 한눈에 보기 위로 갔다) · 크기 = 장을 움직인 변수와 같은 구획 제목(22/28, 폰 20/26) (2026-11-19 사용자)
        fc = th["solid"] if theme == "flow" else FLOW_ICON[1]
        body.append(tinted(iconed(dk.section("업종과 주요 종목", mk, line=False), dk.solid_icon(FLOW_ICON[0], fc)), fc).replace(f"margin:{H2_TOP}px 0 11px;", f"margin:{BIG_TOP}px 0 11px;", 1))

    if col.get("points"):   # 회색 카드 — 핵심 한 줄은 뺐다(머리글과 같은 말)
        nb, nd = dk.CARD_DIR["neutral"]
        body.append(f'<div style="background:{nb};border:1px solid {nd};border-radius:10px;padding:{23 - dk.VP}px 19px;margin:{CARD_GAP}px 0 0;">'
                    + head_row(dk.soft_icon("target"), dk.esc(col.get("pointsTitle") or "관전 포인트"), margin="0 0 27px") + points(col["points"], link, pad=0) + '</div>')   # 제목 ~ 목록 12 → 27 (2026-11-19 사용자 "타이틀 아래 +15")

    # 글 끝 꼬리말 없음(가이드 2절 8). 함께 보는 페이지 = 공용 블록
    rep_name, rep_q = REPORT_LABEL[slot]
    body.append(dk.related_buttons([(rep_name, f"{BLOG}search/label/{rep_q}"), ("증시 전망", FORECAST_URL)]))
    html = dk.WRAP_OPEN + dk.fix_colons("".join(body)) + dk.WRAP_CLOSE
    return stored, html, {"labels": LABELS[slot], "basis": basis, "linked": sorted(link.seen)}
