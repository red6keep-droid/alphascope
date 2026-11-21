"""주식 강좌 목업 — 비공개 문서 저장소의 강좌 초안(마크다운)을 블로그 글 보기 모양으로 (2026-11-10 사용자: 목업에 구현).

    python experiments/course/render_course.py            # 문서 저장소 doc/기획/강좌/*.md → output/mock_*.html (맥 ~/Desktop · Windows D:/ 자동)
    python experiments/course/render_course.py <초안 폴더>

- 초안은 공개 저장소에 두지 않는다. 이 스크립트는 읽기만 하고, output/ 은 .gitignore (발행 전 글이 새지 않게).
- 마크다운은 강좌 초안이 쓰는 것만: # 제목 · ## 구획 · 문단 · 표 · 글머리표 · 번호 목록 · **굵게** · [링크](주소) · --- · ※ 안내.
- 맨 위 `> 초안 …` 줄과 `### 발행 전 확인` 아래는 독자용이 아니라 뺀다.
- 첫 문단 = 맨 위 요약(p[data-seo-lead]) — 다른 리포트와 같은 자리 · 같은 모양. 증감 숫자는 리포트처럼 색(tint).
- 꾸밈 (2026-11-10 사용자: 블로그가 너무 딱딱하다 — D:/auto-blogspot 의 꾸밈 테마 참고). 글에는 표시만, 모양은 여기 DECO 가 정한다:
    ==형광펜==  ++밑줄++  !!강조색!!  `> 💬 핵심 문장` = 말풍선(글마다 하나)  `- [v] 항목` = ✅ 체크 목록  이모지는 글에 직접
  빨강 · 파랑은 쓰지 않는다 — 사이트에서 빨강 = 오름 · 파랑 = 내림이라 강조색과 헷갈린다. 강조색 = 청록, 형광펜 = 노랑
"""
import base64
import glob
import html
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import design_kit as dk  # noqa: E402

# 초안 폴더 — 집(맥) · 회사(Windows) 어디서든 (2026-11-14 사용자: 집 · 회사 오가며 작업). 인자로 주면 그 폴더
_SRC_CANDIDATES = [os.path.expanduser("~/Desktop/alphascope-docs/doc/기획/강좌"), "D:/alphascope-docs/doc/기획/강좌"]
SRC = sys.argv[1] if len(sys.argv) > 1 else next((p for p in _SRC_CANDIDATES if os.path.isdir(p)), _SRC_CANDIDATES[-1])
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
SERIES = "주식 초보들이 경험하는 일반적인 착각"

P = f"font-size:{dk.BODY};line-height:{dk.LH_BODY};color:#333;margin:0 0 16px;word-break:keep-all;padding-left:{dk.ALIGN_PX}px;"
LI = f"font-size:{dk.BODY};line-height:{dk.LH_BODY};color:#333;margin:0 0 16px;padding-left:{dk.ALIGN_PX + 22}px;word-break:keep-all;"
DECO = {   # 강좌 글 꾸밈 — 색 · 모양은 여기 한 곳 (auto-blogspot themes.js 의 `정보형` 을 우리 색으로)
    "mark": "background:#FFF3A3;color:inherit;padding:1px 3px;border-radius:2px;",
    "u": "text-decoration:underline;text-decoration-color:#111;text-decoration-thickness:2px;text-underline-offset:5px;",
    "accent": "color:#0F766E;font-weight:700;",
    # 소제목 = 왼쪽 막대 대신 동그란 바탕 + 이모지 (2026-11-12 사용자: 세로 막대 말고 재밌는 아이콘). 이모지는 초안 `## 💡 제목` 맨 앞에 적는다
    "h2": "display:flex;align-items:center;gap:10px;margin:40px 0 16px;font-size:22px;line-height:32px;font-weight:700;color:#111;word-break:keep-all;",
    # 2026-11-15 사용자: 동그라미 바탕 없앰 — 소품 아이콘(네모 그림)만, 칸 = 아이콘 크기(36) 그대로라 모서리가 잘리지 않게
    "h2_icon": "flex:none;display:flex;align-items:center;justify-content:center;width:36px;height:36px;font-size:22px;line-height:36px;overflow:visible;",
    # 캐릭터 강조 = `> 🤷 문장` (💬 말고 다른 이모지로 시작하는 인용 줄) — 큰 캐릭터 + 굵은 한 문장 (2026-11-12 사용자)
    "char": "display:flex;align-items:center;gap:14px;margin:24px 0;padding:16px 18px;border-radius:16px;background:#FEF9E7;",
    "char_icon": "flex:none;font-size:44px;line-height:52px;",
    "char_text": "flex:1 1 auto;min-width:0;font-size:20px;line-height:30px;font-weight:700;color:#111;word-break:keep-all;",
    "bubble_char": "margin:2px 0 28px;text-align:center;font-size:44px;line-height:52px;",   # 말풍선 꼬리 아래 캐릭터
    # 안내 구획 = `## 📌 제목` (한계 · 밝혀 둘 것) — 아이콘 없이 작은 회색 글씨 (2026-11-12 사용자: 안내성 글은 작게 · 회색 · 딱딱하게)
    "note_h2": f"margin:36px 0 8px;padding:16px 0 0 {dk.ALIGN_PX}px;border-top:1px dashed #CBD5E1;font-size:{dk.TINY};line-height:{dk.LH_TINY};font-weight:700;color:{dk.NOTE};",
    "note_li": f"font-size:{dk.TINY};line-height:22px;color:{dk.NOTE};margin:0 0 16px;padding-left:{dk.ALIGN_PX + 18}px;word-break:keep-all;",
    "note_p": f"font-size:{dk.TINY};line-height:22px;color:{dk.NOTE};margin:0 0 10px;padding-left:{dk.ALIGN_PX}px;word-break:keep-all;",
    "bubble": "position:relative;max-width:560px;margin:28px auto 36px;padding:18px 22px;border-radius:20px;background:#ECFDF5;"
              f"text-align:center;font-size:{dk.BODY};line-height:32px;font-weight:700;color:#134E4A;word-break:keep-all;",
    "tail": "width:0;height:0;margin:-37px auto 0;border:12px solid transparent;border-top-color:#ECFDF5;border-bottom:0;",
    "check": f"list-style:none;margin:0 0 20px;padding:14px 16px;background:#F8FAFC;border-radius:12px;font-size:{dk.BODY};line-height:{dk.LH_BODY};color:#333;",   # 바탕 회색. `## 🔍` (무엇을 보면 되나) 구획 안 목록만 노랑 — CHECK_TAKE (2026-11-20 사용자)
}
# 캐릭터 그림 (2026-11-14 사용자 시트 → cut_chars.py). 초안에 `{상승이-놀람}` 처럼 적으면 그 자리에 그림 — 이모지 자리 셋(강조 줄 · 대결 · 말풍선 아래) 모두
# 상승이 = 신호 보고 산 사람 · 하락이 = 아무 날 산 사람 · 중심이 = 질문 · 설명하는 안내역
CHARS = {
    "상승이-매수": "up_buy", "상승이-놀람": "up_surprised", "상승이-식은땀": "up_sweat",
    "상승이-울상": "up_cry", "상승이-다급": "up_rush", "상승이-후회": "up_regret", "상승이-기다림": "up_wait",   # 2026-11-20 사용자 SVG → svg_to_webp.py
    "하락이-못마땅": "down_grumpy", "하락이-밝게": "down_happy",
    "하락이-시무룩": "down_sulky", "하락이-담담": "down_calm",   # 2026-11-20 사용자 SVG → 320 WebP
    "중심이-고민": "mid_think", "중심이-설명": "mid_explain",
    "중심이-주의": "mid_caution", "중심이-돋보기": "mid_magnifier",   # 2026-11-20 사용자 SVG(chars/src/*.svg) → 320 WebP
}
CHAR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chars")
CHAR_PX = {"line": 113, "vs": 150, "bubble": 125}   # 강조 줄 · 대결 · 말풍선 아래 — 2026-11-14 사용자: 캐릭터 부각, 30% 키움(72 · 96 · 80 → 94 · 125 · 104) 뒤 20% 더(→ 113 · 150 · 125)


IMG_BASE = None   # 발행 때 publish_course.py 가 gh-pages 주소로 채운다(…/images/study/). None = 목업(data URI)


def img_src(folder, name):
    """그림 주소 — 목업은 data URI, 발행은 IMG_BASE + 파일 이름 (캐릭터 · 아이콘 파일 이름은 겹치지 않는다)."""
    if IMG_BASE:
        return IMG_BASE + name + ".webp"
    with open(os.path.join(folder, name + ".webp"), "rb") as f:
        return "data:image/webp;base64," + base64.b64encode(f.read()).decode()


def char(tok, where):
    """`{이름-상황}` → 그림(목업은 data URI, 발행 때 gh-pages 주소로). 이모지면 그대로."""
    m = re.fullmatch(r"\{(.+?)\}", tok or "")
    if not m or m.group(1) not in CHARS:
        return tok
    src = img_src(CHAR_DIR, CHARS[m.group(1)])
    px = CHAR_PX[where]
    return f'<img src="{src}" alt="" width="{px}" height="{px}" style="display:block;width:{px}px;height:{px}px;max-width:none;border-radius:0;margin:0 auto;">'


def is_char(tok):
    return bool(re.fullmatch(r"\{(.+?)\}", tok or "")) and tok[1:-1] in CHARS


# 소품 아이콘 (2026-11-15 사용자 시트 → cut_icons.py). 초안은 지금처럼 이모지를 적고, 아래 표에 있는 이모지는 그림으로 바꾼다 — 없는 이모지는 그대로
ICONS = {
    "🎬": "theater", "🤔": "question", "📏": "ruler", "📉": "chart", "📈": "chart", "📊": "chart",
    "⚖": "scale", "🔍": "magnifier", "💡": "bulb", "🗺": "map", "✅": "check", "🎣": "hook", "✌": "calendars", "📅": "calendars", "📝": "memo", "⏳": "hourglass", "⌛": "hourglass",
}
CHECK_TAKE = "#FEF9E7"   # `## 🔍` 정리 구획의 체크 목록 바탕 = 캐릭터 강조 줄과 같은 노랑 (2026-11-20 사용자: 정리 상자만 노랑, 다른 목록은 회색)
ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
ICON_PX = {"h2": 36, "check": 22}   # 소제목 · 체크 목록 글머리. 소제목 = 바탕 없이 네모 아이콘 36 (2026-11-15 사용자: 동그라미 안 28 은 잘려 보임 → 동그라미 없앰)


def icon_html(tok, where):
    """border-radius:0 — 테마 `.post-body img { border-radius:12px }` 가 작은 아이콘 모서리를 둥글게 깎는다 (2026-11-15 사용자: 잘리지 않게, 네모 그대로). 이모지 → 소품 그림(목업은 data URI, 발행 때 gh-pages 주소로). 표에 없으면 이모지 그대로."""
    name = ICONS.get((tok or "").replace("\ufe0f", ""))
    if not name:
        return tok
    src = img_src(ICON_DIR, name)
    px = ICON_PX[where]
    va = "" if where == "h2" else "vertical-align:-5px;margin-right:4px;"
    return f'<img src="{src}" alt="" width="{px}" height="{px}" style="display:{"block" if where == "h2" else "inline-block"};width:{px}px;height:{px}px;max-width:none;border-radius:0;{va}">'


NOTE_UL = f"list-style:none;font-size:{dk.TINY};line-height:22px;color:{dk.NOTE};margin:0 0 16px;padding-left:{dk.ALIGN_PX + 3}px;word-break:keep-all;"   # 점 왼쪽 = 옛 disc 점 자리(본문 시작선 + 3)
BASIS = f"font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};margin:0 0 8px;padding-left:{dk.ALIGN_PX}px;word-break:keep-all;"
NOTE = f"font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};margin:24px 0 0;padding:12px 0 0 {dk.ALIGN_PX}px;border-top:1px solid #E2E8F0;word-break:keep-all;"


def inline(t, links):
    """**굵게** · [글](주소). 다른 편 .md 링크는 그 편 목업으로."""
    t = html.escape(t, quote=False).replace("&lt;br&gt;", "<br>")   # 초안의 <br> = 줄바꿈 (말풍선 등)
    t = re.sub(r"\*\*(.+?)\*\*", r'<b style="color:#111;">\1</b>', t)
    t = re.sub(r"`([^`]+)`", r'<b style="color:#111;font-weight:600;">\1</b>', t)   # `메뉴 이름` = 화면에 보이는 이름 → 굵게 (백틱은 독자에게 안 보이게)
    t = re.sub(r"==(.+?)==", lambda m: f'<mark style="{DECO["mark"]}">{m.group(1)}</mark>', t)
    t = re.sub(r"\+\+(.+?)\+\+", lambda m: f'<u style="{DECO["u"]}">{m.group(1)}</u>', t)
    t = re.sub(r"!!(.+?)!!", lambda m: f'<span style="{DECO["accent"]}">{m.group(1)}</span>', t)

    def link(m):
        href = links.get(m.group(2), m.group(2))
        return f'<a href="{html.escape(href)}" style="color:#1a73e8;text-decoration:none;">{m.group(1)}</a>'
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, t)


# 표 칸(세로 줄) 색 — 머리 줄 이름으로 정한다 (2026-11-14 사용자, 1편 표). 아주 연하게, 칸 구분만
#   `아무 날` = 연한 파랑 · 그 말대로 산 사람 칸(`2010년대` · `2020년 이후`) = 연한 빨강 · 결과 칸(`다음 날 하루`) = 연한 청록
# 표 규칙 = B6 (2026-11-20 사용자 확정, 시안 B · B1~B8 중): 세로줄 없이 가로줄만 · 머리 줄 연회색 면 + 아래 굵은 검은 줄 ·
# 그 말대로 산 쪽(시기 · 결과) 칸 = 아주 연한 녹색 면 + 굵은 검정 · 아무 날 칸 = 아주 연한 보라 면 + 회색 글자 · 그 밖 칸 = 면 없음.
# 칸 역할은 머리 줄 이름으로 정한다 — 새 편 표도 같은 이름을 쓰면 자동. 옛 모양(청록 머리 · 세로줄 · 연빨강 · 연파랑)은 11-20 에 바꿈
# 2026-11-20 사용자 2차(3편 발행 뒤): 머리 줄 아래 굵은 줄 2 → 1.5 · 모든 칸(머리 · 첫 칸 포함) 가운데 정렬 · 세로선 없음(첫 칸 고정 칸의 세로선도 뺌) ·
# 가로줄은 색 칸 위에서도 보이게 반투명 · 글자 색 = 칸 바탕 색이 섞인 검정(녹색 칸 = 녹색 섞인 검정, 아무 날 = 보라 섞인 검정, 아무 날도 굵게)
TABLE = {"head_bg": "#F3F4F6", "head_line": "1.5px solid #111", "row_line": "1px solid rgba(15,23,42,.11)", "pad": "10px 8px", "head_pad": "8px 8px"}
COL_ROLE = {   # 머리 줄 이름 → 역할
    "아무 날": "any", "아무 날 산 사람": "any",
    "2010년대": "main", "2020년 이후": "main", "다음 날 하루": "main", "그때 산 사람": "main", "실적 보고 산 사람": "main",
}
MAIN_FG, ANY_FG = "#15402A", "#33245E"   # 녹색 섞인 검정 · 보라 섞인 검정 (2026-11-20 사용자)
ROLE_STYLE = {   # 역할 → (칸 바탕, 칸 글자, 머리 글자 색)
    "main": ("#F0FDF4", f"font-weight:700;color:{MAIN_FG};", MAIN_FG),
    "any": ("#F5F3FF", f"font-weight:700;color:{ANY_FG};", ANY_FG),
    None: ("", "color:#333;", "#111"),
}
TABLE_TITLE = "margin:0;font-size:15px;line-height:22px;font-weight:700;color:#111;word-break:keep-all;"   # 표 제목 = 그래프 상자 제목과 같은 15/22 (2026-11-20 사용자: 13 → 15)
SWIPE_HINT = f"margin:0 0 0 auto;font-size:12px;line-height:22px;color:{dk.NOTE};white-space:nowrap;"   # `옆으로 넘겨 보기 ›` 회색 #9CA3AF → 안내 회색 #6B7280 (2026-11-20 사용자: 더 진하게)
# 넘겨 보기 그림자 = 그래프 넘겨 보기 그림자(design_kit data-sh)와 같은 꼴, 오른쪽 · 넘길 것이 남았을 때만 (2026-11-20 사용자: 잘 모를 수 있으니 그림자)
TABLE_SHADE = ('<span data-tshade="1" aria-hidden="true" style="position:absolute;top:0;bottom:0;right:0;width:14px;pointer-events:none;z-index:2;transition:opacity .15s;'
               'background:radial-gradient(farthest-side at 100% 50%,rgba(15,23,42,.18),rgba(15,23,42,0));"></span>')
TABLE_JS = ("<script>(function(){function u(w){var b=w.querySelector('[data-tscroll]');if(!b||!b.clientWidth)return;var m=b.scrollWidth-b.clientWidth,"
            "h=w.querySelector('[data-swipe-hint]'),s=w.querySelector('[data-tshade]');if(h)h.style.display=m>1?'':'none';if(s)s.style.opacity=(m-b.scrollLeft>1)?'1':'0';}"
            "function all(){var ws=document.querySelectorAll('[data-course-table]');for(var i=0;i<ws.length;i++){var w=ws[i],b=w.querySelector('[data-tscroll]');u(w);"
            "if(b&&!b._t){b._t=1;b.addEventListener('scroll',(function(x){return function(){u(x);};})(w),{passive:true});}}}"
            "if(document.readyState!=='loading')all();else document.addEventListener('DOMContentLoaded',all);window.addEventListener('load',all);"
            "window.addEventListener('resize',function(){setTimeout(all,30);});})();</script>")


KOME_UP = {"15": 1, "14": 1}   # ※ 를 1px 올림 (2026-11-20 사용자: 미들 정렬). 실측(노토 · 나눔바른 · 애플SD 15px 굵게): ※ 위아래 끝 가운데 = 글자 가운데지만 한글이 ※ 보다 위아래로 1.5px 길어 ※ 가 낮아 보인다


def kome(fs):
    """앞머리 ※ — 뒤 글자의 가운데 높이에 맞춘다."""
    return f'<span style="display:inline-block;position:relative;top:-{KOME_UP[fs]}px;">※</span>'


def table(lines, links, top=30, title=""):
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines if not re.match(r"^\s*\|?\s*-{3}", ln)]
    head, body = rows[0], rows[1:]
    role = [None if k == 0 else COL_ROLE.get(re.sub(r"[*`]", "", h).strip()) for k, h in enumerate(head)]
    # 폰에서 넘겨 보기 (2026-11-20 사용자: "표는 넘겨 보기로"): 첫 칸(행 이름)은 왼쪽에 고정(sticky, 세로선 없음) · 칸 4개 이상이면 넘칠 때만 `옆으로 넘겨 보기 ›` + 오른쪽 그림자
    stick = lambda bg: f"position:sticky;left:0;z-index:1;background:{bg};"
    th = "".join(f'<th style="padding:{TABLE["head_pad"]};background:{TABLE["head_bg"]};border-bottom:{TABLE["head_line"]};text-align:center;white-space:nowrap;'
                 f'{stick(TABLE["head_bg"]) if k == 0 else ""}'
                 f'font-size:13px;line-height:18px;font-weight:700;color:{ROLE_STYLE[role[k]][2]};">{inline(h, links)}</th>' for k, h in enumerate(head))
    td = lambda k, c: (f'<td style="padding:{TABLE["pad"]};border-bottom:{TABLE["row_line"]};white-space:nowrap;text-align:center;'
                       + ("font-weight:600;color:#111;" + stick("#fff") if k == 0 else (f"background:{ROLE_STYLE[role[k]][0]};" if ROLE_STYLE[role[k]][0] else "") + ROLE_STYLE[role[k]][1])
                       + f'">{inline(c, links)}</td>')
    trs = "".join("<tr>" + "".join(td(k, c) for k, c in enumerate(r)) + "</tr>" for r in body)
    swipe = True   # 칸 수와 상관없이 — 화면보다 넓을 때만 안내 · 그림자가 보인다(TABLE_JS), 3칸 표도 작은 폰에서 넘치면 같게 (2026-11-20 사용자)
    hint = (f'<span data-swipe-hint="1" style="{SWIPE_HINT}">옆으로 넘겨 보기 ›</span>' if swipe else "")
    # 표 제목 · 넘겨 보기 = 한 줄(제목 왼쪽 · 안내 오른쪽), 한 줄에 안 들어가면 안내가 윗줄로(wrap-reverse) (2026-11-20 사용자)
    cap = ""
    if title or hint:
        cap = (f'<div data-course-table-title="1" style="display:flex;flex-wrap:wrap-reverse;align-items:baseline;column-gap:12px;margin:0 0 8px;padding-left:{dk.ALIGN_PX}px;">'
               + (f'<p style="{TABLE_TITLE}">{kome("15")} {inline(title, links)}</p>' if title else "") + hint + "</div>")
    shade = TABLE_SHADE if swipe else ""
    css = '<style>@media (min-width:600px){[data-swipe-hint],[data-tshade]{display:none!important}}</style>' if swipe else ""   # JS 없이도 넓은 화면엔 안 보임
    # display:table — 테마가 글 안 표를 display:block 으로 바꿔 칸이 폭을 채우지 못한다(오른쪽이 비던 까닭)
    # 표 영역 ↔ 본문 글 사이 30px (2026-11-20 사용자: 20 → 30). 표 제목이 있으면 제목 위 30
    return dk.tint(f'<div data-course-table="1" style="margin:{30 if title else top}px 0 30px;">{css}{cap}<div style="position:relative;">'
                   f'<div data-tscroll="1" style="overflow-x:auto;-webkit-overflow-scrolling:touch;">'
                   '<table style="display:table;border-collapse:separate;border-spacing:0;width:100%;min-width:100%;margin:0;'
                   f'font-size:16px;line-height:{dk.LH_CARD};">' + f"<tr>{th}</tr>{trs}</table></div>{shade}</div></div>")


CHART_COLORS = [dk.CHART_MAIN, dk.CHART_CMP, dk.CHART_SERIES[1]]   # 2026-11-14 그래프 통일: 그래프 색 표 — 신호 쪽 주황 · 비교 기준(아무 날) 회색 · 셋째 청록 (옛 #F59E0B · #0F766E · #9AD1C8). 빨강 · 파랑은 안 씀(오름 · 내림 색)


def chart(lines, links, title=""):
    """`[그래프] 제목` 줄 바로 아래 표 → 묶음 가로 막대 (2026-11-12 사용자: 표를 그래프로 · 색 · 비교 대상 = 신호 받은 사람과 아무 날 산 사람을 나란히).
    첫 칸 = 묶음 이름(기간), 나머지 칸 = 계열(머리 줄 이름). 막대 길이는 표 전체에서 가장 큰 값 기준 — 묶음끼리도 길이를 견줄 수 있다. 값은 막대 오른쪽에 그대로."""
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines if not re.match(r"^\s*\|?\s*-{3}", ln)]
    head, body = rows[0], rows[1:]
    num = lambda c: float(re.sub(r"[^0-9.\-]", "", c.replace("−", "-")) or 0)
    top = max(abs(num(c)) for r in body for c in r[1:]) or 1
    out = []
    for r in body:
        bars = ""
        for k, c in enumerate(r[1:]):
            w = max(1, round(abs(num(c)) / top * 100))
            bars += ('<span style="display:flex;align-items:center;gap:10px;margin:6px 0 0;">'
                     f'<span style="flex:none;width:118px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};white-space:nowrap;">{html.escape(head[k + 1])}</span>'
                     '<span style="flex:1 1 0;min-width:0;display:block;">'
                     f'<span style="display:block;width:{w}%;min-width:4px;height:10px;border-radius:3px;background:{CHART_COLORS[k % len(CHART_COLORS)]};"></span></span>'
                     f'<span style="flex:none;width:64px;text-align:right;font-size:15px;line-height:22px;font-weight:700;white-space:nowrap;">{dk.tint(html.escape(c))}</span></span>')   # 값 글자 17 → 15 (2026-11-14 사용자: 2 줄임)
        out.append(f'<div style="padding:14px 0;{"border-top:1px solid #E2E8F0;" if out else ""}">'
                   f'<span style="display:block;font-size:17px;line-height:24px;font-weight:700;color:#111;">{inline(r[0], links)}</span>{bars}</div>')
    head_html = (f'<span style="display:block;padding:12px 0 0;font-size:15px;line-height:22px;font-weight:700;color:#134E4A;">{html.escape(title)}</span>' if title else "")
    return f'<div data-course-chart="1" style="margin:0 0 12px;padding:4px 16px;background:#F8FAFC;border-radius:12px;">{head_html}{"".join(out)}</div>'


VS_TONES = [("#FFF4DC", "#92400E"), ("#ECFDF5", "#134E4A")]   # 말풍선 바탕 · 글자 — 그래프 계열 색(주황 · 청록)과 같은 순서


def versus(items, links):
    """`[대결]` 아래 두 줄 `- 🤓 이름 | 하는 말` → 캐릭터 둘이 말풍선을 달고 나란히 (2026-11-12 사용자: 글의 핵심 비교를 캐릭터 두 명 + 말풍선으로 강조).
    이름 앞 점 색 = 바로 아래 그래프의 막대 색(CHART_COLORS 순서) — 누가 어느 막대인지 이어 준다."""
    cols = []
    for k, it in enumerate(items[:2]):
        who, _, rest = it.partition(" ")
        name, _, say = rest.partition("|")
        bg, fg = VS_TONES[k % 2]
        cols.append('<div style="flex:1 1 0;min-width:0;display:flex;flex-direction:column;align-items:center;">'
                    f'<div style="width:100%;box-sizing:border-box;flex:1 1 auto;display:flex;align-items:center;justify-content:center;padding:12px 10px;border-radius:16px;background:{bg};'
                    f'text-align:center;font-size:16px;line-height:24px;font-weight:700;color:{fg};word-break:keep-all;">{inline(say.strip(), links)}</div>'
                    f'<div style="width:0;height:0;border:10px solid transparent;border-top-color:{bg};border-bottom:0;"></div>'
                    f'<div aria-hidden="true" style="margin:2px 0 0;font-size:52px;line-height:60px;">{char(who, "vs")}</div>'
                    '<div style="display:flex;align-items:center;gap:6px;margin:4px 0 0;font-size:15px;line-height:22px;font-weight:700;color:#111;word-break:keep-all;text-align:center;">'
                    f'<span style="flex:none;width:10px;height:10px;border-radius:5px;background:{CHART_COLORS[k % len(CHART_COLORS)]};"></span>{inline(name.strip(), links)}</div></div>')
    vs = '<div aria-hidden="true" style="flex:none;align-self:center;font-size:14px;line-height:20px;font-weight:800;color:#9CA3AF;">VS</div>'
    return f'<div data-course-vs="1" style="display:flex;align-items:stretch;gap:8px;margin:24px 0 24px;">{vs.join(cols)}</div>'


def is_emoji(tok):
    """이모지 토큰인가 — 한글 · 영문 · 숫자 · 문장부호가 없는 덩어리. 0x2300 ~ 0x23FF = ⏳ ⌛ ⏰ (2026-11-20 모래시계 아이콘)."""
    return bool(tok) and all(ord(c) in (0x200D, 0xFE0F) or 0x2300 <= ord(c) <= 0x23FF or ord(c) >= 0x2600 and not 0x3000 <= ord(c) <= 0xD7FF for c in tok)


def next_card(text, href, links):
    """`## 다음 편` 구획 → 누르는 카드 (2026-11-10 사용자: 다음 편은 본문과 다르게). 문단 = `**#N 제목** — 소개`."""
    text = re.sub(r"^👉\s*", "", text.strip())
    head, _, teaser = text.partition(" — ")
    head = re.sub(r"\*\*(.+?)\*\*", r"\1", head)
    chev = ('<svg viewBox="0 0 16 16" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M6 3.5 10.5 8 6 12.5"/></svg>')
    ready = bool(href) and href != "#"   # 다음 편이 아직 없으면 누르지 않는 카드 + `준비 중` (2026-11-15 발행: 1편 다음 카드가 # 로 가던 것)
    tag = "a" if ready else "div"
    href_attr = f' href="{html.escape(href)}"' if ready else ""
    # 준비 중 = 편 제목 문장 끝에 붙는 라벨(사이트 공용 알약 neutral), 오른쪽 화살표 자리는 비운다 (2026-11-15 사용자). 다음 편이 발행되면 ready → 라벨이 빠지고 링크 + 화살표
    soon = "" if ready else dk.pill("준비 중", "neutral")
    if not ready:
        chev = ""
    return (f'<{tag}{href_attr} data-next="1" style="display:flex;align-items:center;gap:12px;margin:36px 0 8px;padding:16px 16px 16px 18px;'
            'background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;text-decoration:none;color:inherit;">'   # 사이트 회색 카드(design_kit CARD)와 같은 색 · 테두리 · 모서리 (2026-11-10 사용자)
            '<span style="flex:1 1 auto;min-width:0;">'
            '<span style="display:block;font-size:13px;line-height:18px;font-weight:700;color:#6B7280;margin:0 0 4px;">다음 편</span>'
            f'<span style="display:block;font-size:18px;line-height:27px;font-weight:700;color:#111;word-break:keep-all;">{inline(head, links)}{soon}</span>'
            + (f'<span style="display:block;margin-top:6px;font-size:15px;line-height:24px;color:#333;word-break:keep-all;">{inline(teaser, links)}</span>' if teaser else "")
            + '</span>' + (f'<span style="flex:none;color:#6B7280;">{chev}</span>' if chev else "") + f'</{tag}>')


def render(md, links, next_href="#"):
    md = md.split("### 발행 전 확인")[0]
    lines = [ln for ln in md.splitlines() if not ln.startswith("> 초안")]
    title, out, i, lead_done = "", [], 0, False
    table_title = ""   # 표 바로 위 굵은 한 줄(**…**) = 표 제목 — 표가 받아 넘겨 보기 안내와 한 줄로
    note_mode, chart_next, take_mode = False, None, False   # take_mode: `## 🔍` 정리 구획 안(체크 목록 바탕 노랑)
    gray = lambda h: h.replace('color:#111;', f'color:{dk.NOTE};')   # 안내 구획 안 굵은 글씨도 회색
    while i < len(lines):
        ln = lines[i].rstrip()
        if ln.startswith("# "):
            title = ln[2:].strip()
        elif ln.strip() == "## 다음 편":
            note_mode = False
            i += 1
            para = []
            while i < len(lines) and not re.match(r"^(#|---|※|자료:)", lines[i]):
                if lines[i].strip():
                    para.append(lines[i].strip())
                i += 1
            out.append(next_card(" ".join(para), next_href, links))
            continue
        elif ln.startswith("## "):
            icon, _, rest = ln[3:].strip().partition(" ")
            if not is_emoji(icon):
                icon, rest = "📖", ln[3:].strip()
            note_mode = icon.startswith("📌")
            take_mode = icon.startswith("🔍")
            if note_mode:
                out.append(f'<div data-course-note="1" style="{DECO["note_h2"]}">{inline(rest, links)}</div>')   # h2 가 아니라 div — 테마가 h2 글자 크기를 키운다
            else:
                out.append(f'<h2 style="{DECO["h2"]}"><span aria-hidden="true" style="{DECO["h2_icon"]}">{icon_html(icon, "h2")}</span><span>{inline(rest, links)}</span></h2>')
        elif ln.startswith("> 💬"):   # `> 💬 문장` 또는 `> 💬🧐 문장`(꼬리 아래 캐릭터 지정)
            who, _, said = ln[2:].strip().partition(" ")
            out.append(f'<div style="{DECO["bubble"]}">{dk.tint(inline(said.strip(), links))}</div><div style="{DECO["tail"]}"></div>'
                       f'<div aria-hidden="true" style="{DECO["bubble_char"]}">{char(who[1:], "bubble") or "🧐"}</div>')
        elif ln.startswith("> ") and (is_emoji(ln[2:].split(" ")[0]) or is_char(ln[2:].split(" ")[0])):
            who, _, said = ln[2:].strip().partition(" ")
            out.append(f'<div data-course-char="1" style="{DECO["char"]}"><span aria-hidden="true" style="{DECO["char_icon"]}">{char(who, "line")}</span>'
                       f'<span style="{DECO["char_text"]}">{dk.tint(inline(said.strip(), links))}</span></div>')
        elif ln.strip() == "[대결]":
            i += 1
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:].strip())
                i += 1
            out.append(versus(items, links))
            continue
        elif ln.startswith("[그래프]"):
            chart_next = ln[5:].strip()   # 뒤 글자 = 그래프 제목 (없으면 빈 글자)
        elif ln.startswith("- [v] "):
            items = []
            while i < len(lines) and lines[i].startswith("- [v] "):
                items.append(lines[i][6:].strip())
                i += 1
            out.append(f'<ul style="{DECO["check"].replace("#F8FAFC", CHECK_TAKE) if take_mode else DECO["check"]}">' + "".join(f'<li style="margin:4px 0;">{icon_html("✅", "check")} {dk.tint(inline(x, links))}</li>' for x in items) + "</ul>")
            continue
        elif ln.startswith("|"):
            blk = []
            while i < len(lines) and lines[i].startswith("|"):
                blk.append(lines[i])
                i += 1
            out.append(chart(blk, links, chart_next) if chart_next is not None else table(blk, links, 30, table_title))
            table_title = ""
            chart_next = None
            continue
        elif re.match(r"^(- |\d+\. )", ln):
            ordered = bool(re.match(r"^\d+\. ", ln))
            items = []
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i]).strip())
                i += 1
            tag = "ol" if ordered else "ul"
            if ordered and not note_mode:
                # 번호를 직접 그린다 — list-style outside 는 번호를 글 시작점 왼쪽에 매달아 `10.` 이 본문 기준선(ALIGN_PX) 밖으로 나갔다 (2026-11-15 사용자: 연재 순서).
                # 번호 칸 = 기준선에서 시작 · 폭 32 · 왼쪽 맞춤, 줄바꿈된 글은 번호 칸 오른쪽에 맞춘다
                out.append(f'<ol style="list-style:none;margin:0 0 16px;padding:0 0 0 {dk.ALIGN_PX}px;font-size:{dk.BODY};line-height:{dk.LH_BODY};color:#333;">' + "".join(
                    f'<li style="display:flex;margin:0 0 6px;padding:0;"><span style="flex:none;width:32px;">{k + 1}.</span>'
                    f'<span style="flex:1 1 auto;min-width:0;word-break:keep-all;">{dk.tint(inline(x, links))}</span></li>' for k, x in enumerate(items)) + "</ol>")
            elif note_mode and not ordered:
                # `자료 및 한계` 글머리 = 직접 그린 점 3px · 점 ~ 글 8 (기본 disc 점 ~ 글 12 에서 30% 줄임) · 점 자리는 그대로 (2026-11-20 사용자)
                out.append(f'<ul style="{NOTE_UL}">' + "".join(
                    f'<li style="display:flex;align-items:flex-start;gap:8px;margin:0 0 4px;"><span aria-hidden="true" style="flex:none;width:3px;height:3px;border-radius:50%;background:{dk.NOTE};margin-top:9px;"></span>'
                    f'<span style="flex:1 1 auto;min-width:0;">{gray(inline(x, links))}</span></li>' for x in items) + "</ul>")
            elif note_mode:
                out.append(f'<{tag} style="{DECO["note_li"]}">' + "".join(f'<li style="margin:0 0 4px;">{gray(inline(x, links))}</li>' for x in items) + f"</{tag}>")
            else:
                out.append(f'<{tag} style="{LI}">' + "".join(f'<li style="margin:0 0 6px;">{dk.tint(inline(x, links))}</li>' for x in items) + f"</{tag}>")
            continue
        elif ln.strip() == "---" or not ln.strip():
            pass
        elif ln.startswith("※"):   # 본문 안 근거 안내 — 그래프 위 작은 회색 한두 줄, 구분선 없이 (2026-11-14 사용자: 그래프가 어떻게 나왔는지 짧게)
            out.append(f'<p data-course-basis="1" style="{BASIS}">{kome("14")}{inline(ln[1:], links)}</p>')
        elif ln.startswith("자료:"):
            out.append(f'<p style="{NOTE}">{inline(ln, links)}</p>')
        elif ln.startswith("(") and ln.endswith(")"):
            out.append(f'<p style="margin:-22px 0 30px;padding-left:{dk.ALIGN_PX}px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};">{inline(ln, links)}</p>')
        else:
            para = [ln]
            while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"^(#|\||- |\d+\. |---|※|자료:|> )", lines[i + 1]):
                i += 1
                para.append(lines[i].rstrip())
            txt = dk.tint(inline(" ".join(para), links))
            nxt_ln = next((x for x in lines[i + 1:] if x.strip()), "")
            cap = re.fullmatch(r"\*\*(.+)\*\*", " ".join(para).strip())
            if cap and not note_mode and nxt_ln.startswith("|") and chart_next is None:   # 표 제목 = ※ + 작은 굵은 글씨, 위 30 · 표와 8 (2026-11-20 사용자)
                table_title = cap.group(1)   # 표가 제목 줄을 그린다 (넘겨 보기 안내와 한 줄, 2026-11-20 사용자)
            elif note_mode:
                out.append(f'<p style="{DECO["note_p"]}">{gray(inline(" ".join(para), links))}</p>')
            elif not lead_done:   # 첫 문단 = 맨 위 요약 (0편은 부제 구획 다음)
                out.append(f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">{txt}</p>')
                lead_done = True
            else:
                out.append(f'<p style="{P}">{txt}</p>')
        i += 1
    if any("data-tshade" in x for x in out):
        out.append(TABLE_JS)   # 넘겨 보기 안내 · 그림자 = 넘칠 때만, 끝까지 넘기면 그림자 끔
    return title, dk.align_titles(dk.WRAP_OPEN + "".join(out) + dk.WRAP_CLOSE)


SHARE_IMG = "share_study.jpg"   # 공유 썸네일 1200×600 (banner/, 2026-11-15 사용자: 주식 공부 글 · 목록은 이 그림, 다른 페이지는 공통 로고)


def share_tag():
    """본문 맨 앞 숨은 그림 — Blogger 가 첫 그림을 og:image(주소 붙여넣기 미리보기)로 쓰고, 테마 카카오톡 버튼이 data-share-img 를 썸네일로 쓴다. 발행 때만(IMG_BASE 있을 때)."""
    if not IMG_BASE:
        return ""
    return f'<img data-share-img="1" src="{IMG_BASE}{SHARE_IMG}" alt="" width="1200" height="600" hidden style="display:none">'


HEAD_SUB = "주식공부"   # 머리 줄 옆 아주 작은 글씨 — 검색어 (2026-11-20 사용자)
HEAD_LABEL = "주식 제대로 알기"   # 머리 줄(글 제목 자리)에 보일 메뉴 이름 (2026-11-10 사용자: 여기에 타이틀 쓰지 말고 메뉴명; 2026-11-14 이름 강좌 → 주식 공부; 2026-11-20 → 주식 제대로 알기 — Blogger 라벨은 `주식 공부` 그대로). 글 제목 · 검색 제목은 그대로
LIST_URL = "https://www.newfact.app/p/study.html"   # 머리 줄 화살표 · 목록 = 주식 공부 목록 고정 페이지(render_list.py --publish) — 옛 `주식 공부` 라벨 검색 (2026-11-15 사용자: 새 목록 페이지로 안 갔다)


def title_block(title):
    """본문 맨 위 제목 — 머리 줄에서 내려온 진짜 제목. `연재 이름 #N` 작은 청록 줄 + 편 제목 큰 글씨."""
    series, _, ep = title.partition(" — ")
    return (f'<div data-course-title="1" style="padding:24px {dk.ALIGN_PX}px 0;margin:0 0 20px;">'
            f'<div style="font-size:15px;line-height:22px;font-weight:700;color:#0F766E;margin:0 0 6px;">{html.escape(series)}</div>'
            f'<h1 style="margin:0;font-size:26px;line-height:36px;font-weight:800;color:#111;word-break:keep-all;">{html.escape(ep or title)}</h1></div>')


# 목업 전용 — 테마 JS 가 머리 줄을 다 만든 뒤 글자만 `강좌` 로. 실제 블로그는 테마(alphaflow-home.html)에 같은 동작을 넣는다(data-head-label)
MOCK_HEAD_JS = ("<script>(function(){function go(){var b=document.querySelector('[data-head-label]');if(!b)return;"
                "var l=document.querySelector('.post-title-label')||document.querySelector('.post-title');if(l){l.textContent=b.getAttribute('data-head-label');var t=b.getAttribute('data-head-sub');if(t){var s=document.createElement('span');s.textContent=' - '+t;s.style.cssText='font-size:11px;font-weight:500;opacity:.6;margin-left:3px;letter-spacing:0;';l.appendChild(s);}}}"
                "if(document.readyState==='complete')go();else window.addEventListener('load',go);})();</script>")


def main():
    os.makedirs(OUT, exist_ok=True)
    files = sorted(glob.glob(os.path.join(SRC, "*.md")))
    links = {os.path.basename(f): f"mock_{os.path.splitext(os.path.basename(f))[0]}.html" for f in files}
    for f in files:
        k = files.index(f)
        nxt = links[os.path.basename(files[k + 1])] if k + 1 < len(files) else "#"   # 다음 편 카드 = 다음 파일 목업 (아직 없으면 #)
        title, body = render(open(f, encoding="utf-8").read(), links, nxt)
        body = (f'<span data-head-label="{HEAD_LABEL}" data-head-sub="{HEAD_SUB}" hidden></span><span data-list-url="{LIST_URL}" data-nav="back" hidden></span>'
                + title_block(title) + body)
        path = dk.write_mock(body, os.path.join(OUT, links[os.path.basename(f)]), title)
        if path:
            pg = open(path, encoding="utf-8").read().replace("</body>", MOCK_HEAD_JS + "</body>", 1)
            open(path, "w", encoding="utf-8").write(pg)
        print(f"[강좌] {title} → {path}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
