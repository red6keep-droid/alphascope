"""주식 강좌 목업 — 비공개 문서 저장소의 강좌 초안(마크다운)을 블로그 글 보기 모양으로 (2026-11-10 사용자: 목업에 구현).

    python experiments/course/render_course.py            # D:/alphascope-docs/doc/기획/강좌/*.md → output/mock_*.html
    python experiments/course/render_course.py <초안 폴더>

- 초안은 공개 저장소에 두지 않는다. 이 스크립트는 읽기만 하고, output/ 은 .gitignore (발행 전 글이 새지 않게).
- 마크다운은 강좌 초안이 쓰는 것만: # 제목 · ## 구획 · 문단 · 표 · 글머리표 · 번호 목록 · **굵게** · [링크](주소) · --- · ※ 안내.
- 맨 위 `> 초안 …` 줄과 `### 발행 전 확인` 아래는 독자용이 아니라 뺀다.
- 첫 문단 = 맨 위 요약(p[data-seo-lead]) — 다른 리포트와 같은 자리 · 같은 모양. 증감 숫자는 리포트처럼 색(tint).
- 꾸밈 (2026-11-10 사용자: 블로그가 너무 딱딱하다 — D:/auto-blogspot 의 꾸밈 테마 참고). 글에는 표시만, 모양은 여기 DECO 가 정한다:
    ==형광펜==  ++밑줄++  !!강조색!!  `> 💬 핵심 문장` = 말풍선(글마다 하나)  `- [v] 항목` = ✅ 체크 목록  이모지는 글에 직접
  빨강 · 파랑은 쓰지 않는다 — 사이트에서 빨강 = 오름 · 파랑 = 내림이라 강조색과 헷갈린다. 강조색 = 청록, 형광펜 = 노랑
"""
import glob
import html
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import design_kit as dk  # noqa: E402

SRC = sys.argv[1] if len(sys.argv) > 1 else "D:/alphascope-docs/doc/기획/강좌"
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
    "h2_icon": "flex:none;display:flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:20px;background:#ECFDF5;font-size:22px;line-height:40px;",
    # 캐릭터 강조 = `> 🤷 문장` (💬 말고 다른 이모지로 시작하는 인용 줄) — 큰 캐릭터 + 굵은 한 문장 (2026-11-12 사용자)
    "char": "display:flex;align-items:center;gap:14px;margin:24px 0;padding:16px 18px;border-radius:16px;background:#FEF9E7;",
    "char_icon": "flex:none;font-size:44px;line-height:52px;",
    "char_text": "flex:1 1 auto;min-width:0;font-size:20px;line-height:30px;font-weight:700;color:#111;word-break:keep-all;",
    "bubble_char": "margin:2px 0 28px;text-align:center;font-size:44px;line-height:52px;",   # 말풍선 꼬리 아래 캐릭터
    # 안내 구획 = `## 📌 제목` (한계 · 밝혀 둘 것) — 아이콘 없이 작은 회색 글씨 (2026-11-12 사용자: 안내성 글은 작게 · 회색 · 딱딱하게)
    "note_h2": f"margin:36px 0 8px;padding:16px 0 0 {dk.ALIGN_PX}px;border-top:1px solid #E2E8F0;font-size:{dk.TINY};line-height:{dk.LH_TINY};font-weight:700;color:{dk.NOTE};",
    "note_li": f"font-size:{dk.TINY};line-height:22px;color:{dk.NOTE};margin:0 0 16px;padding-left:{dk.ALIGN_PX + 18}px;word-break:keep-all;",
    "note_p": f"font-size:{dk.TINY};line-height:22px;color:{dk.NOTE};margin:0 0 10px;padding-left:{dk.ALIGN_PX}px;word-break:keep-all;",
    "bubble": "position:relative;max-width:560px;margin:28px auto 36px;padding:18px 22px;border-radius:20px;background:#ECFDF5;"
              f"text-align:center;font-size:{dk.BODY};line-height:32px;font-weight:700;color:#134E4A;word-break:keep-all;",
    "tail": "width:0;height:0;margin:-37px auto 0;border:12px solid transparent;border-top-color:#ECFDF5;border-bottom:0;",
    "check": f"list-style:none;margin:0 0 20px;padding:14px 16px;background:#F8FAFC;border-radius:12px;font-size:{dk.BODY};line-height:{dk.LH_BODY};color:#333;",
}
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


def table(lines, links):
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines if not re.match(r"^\s*\|?\s*-{3}", ln)]
    head, body = rows[0], rows[1:]
    # 강좌 표 — 화면 폭을 꽉 채우고(오른쪽 빈 칸 없이) 머리 줄에 청록 바탕 (2026-11-12 사용자). 칸 폭은 고르게, 좁으면 표만 가로 스크롤
    th = "".join(f'<th style="border:1px solid #CFE9E3;padding:8px 10px;background:#ECFDF5;text-align:{"left" if k == 0 else "right"};white-space:nowrap;'
                 f'font-size:{dk.TINY};line-height:{dk.LH_TINY};color:#134E4A;font-weight:700;">{inline(h, links)}</th>' for k, h in enumerate(head))
    trs = "".join("<tr>" + "".join(f'<td style="border:1px solid #E2E8F0;padding:8px 10px;white-space:nowrap;text-align:{"left" if k == 0 else "right"};'
                                   f'{"color:#111;font-weight:600;" if k == 0 else ""}">{inline(c, links)}</td>' for k, c in enumerate(r)) + "</tr>" for r in body)
    # display:table — 테마가 글 안 표를 display:block 으로 바꿔 칸이 폭을 채우지 못한다(오른쪽이 비던 까닭)
    return dk.tint(f'<div data-course-table="1" style="overflow-x:auto;margin:0 0 12px;"><table style="display:table;border-collapse:collapse;width:100%;min-width:100%;margin:0;'
                   f'font-size:17px;line-height:{dk.LH_CARD};">' + f"<tr>{th}</tr>{trs}</table></div>")


CHART_COLORS = ["#F59E0B", "#0F766E", "#9AD1C8"]   # 계열 색 — 첫 계열(신호 쪽) 주황 · 둘째(아무 날 = 비교 기준) 청록 · 옅은 청록. 빨강 · 파랑은 안 씀(오름 · 내림 색)


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
                     f'<span style="display:block;width:{w}%;min-width:4px;height:16px;border-radius:4px;background:{CHART_COLORS[k % len(CHART_COLORS)]};"></span></span>'
                     f'<span style="flex:none;width:64px;text-align:right;font-size:17px;line-height:24px;font-weight:700;white-space:nowrap;">{dk.tint(html.escape(c))}</span></span>')
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
                    f'<div aria-hidden="true" style="margin:2px 0 0;font-size:52px;line-height:60px;">{who}</div>'
                    '<div style="display:flex;align-items:center;gap:6px;margin:4px 0 0;font-size:15px;line-height:22px;font-weight:700;color:#111;word-break:keep-all;text-align:center;">'
                    f'<span style="flex:none;width:10px;height:10px;border-radius:5px;background:{CHART_COLORS[k % len(CHART_COLORS)]};"></span>{inline(name.strip(), links)}</div></div>')
    vs = '<div aria-hidden="true" style="flex:none;align-self:center;font-size:14px;line-height:20px;font-weight:800;color:#9CA3AF;">VS</div>'
    return f'<div data-course-vs="1" style="display:flex;align-items:stretch;gap:8px;margin:24px 0 24px;">{vs.join(cols)}</div>'


def is_emoji(tok):
    """이모지 토큰인가 — 한글 · 영문 · 숫자 · 문장부호가 없는 덩어리."""
    return bool(tok) and all(ord(c) in (0x200D, 0xFE0F) or ord(c) >= 0x2600 and not 0x3000 <= ord(c) <= 0xD7FF for c in tok)


def next_card(text, href, links):
    """`## 다음 편` 구획 → 누르는 카드 (2026-11-10 사용자: 다음 편은 본문과 다르게). 문단 = `**#N 제목** — 소개`."""
    text = re.sub(r"^👉\s*", "", text.strip())
    head, _, teaser = text.partition(" — ")
    head = re.sub(r"\*\*(.+?)\*\*", r"\1", head)
    chev = ('<svg viewBox="0 0 16 16" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M6 3.5 10.5 8 6 12.5"/></svg>')
    return (f'<a href="{html.escape(href)}" data-next="1" style="display:flex;align-items:center;gap:12px;margin:36px 0 8px;padding:16px 16px 16px 18px;'
            'background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;text-decoration:none;color:inherit;">'   # 사이트 회색 카드(design_kit CARD)와 같은 색 · 테두리 · 모서리 (2026-11-10 사용자)
            '<span style="flex:1 1 auto;min-width:0;">'
            '<span style="display:block;font-size:13px;line-height:18px;font-weight:700;color:#6B7280;margin:0 0 4px;">다음 편</span>'
            f'<span style="display:block;font-size:18px;line-height:27px;font-weight:700;color:#111;word-break:keep-all;">{inline(head, links)}</span>'
            + (f'<span style="display:block;margin-top:6px;font-size:15px;line-height:24px;color:#333;word-break:keep-all;">{inline(teaser, links)}</span>' if teaser else "")
            + f'</span><span style="flex:none;color:#6B7280;">{chev}</span></a>')


def render(md, links, next_href="#"):
    md = md.split("### 발행 전 확인")[0]
    lines = [ln for ln in md.splitlines() if not ln.startswith("> 초안")]
    title, out, i, lead_done = "", [], 0, False
    note_mode, chart_next = False, None   # note_mode: `## 📌` 안내 구획 안(다음 ## 까지) · chart_next: `[그래프]` 다음 표
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
            if note_mode:
                out.append(f'<div data-course-note="1" style="{DECO["note_h2"]}">{inline(rest, links)}</div>')   # h2 가 아니라 div — 테마가 h2 글자 크기를 키운다
            else:
                out.append(f'<h2 style="{DECO["h2"]}"><span aria-hidden="true" style="{DECO["h2_icon"]}">{icon}</span><span>{inline(rest, links)}</span></h2>')
        elif ln.startswith("> 💬"):   # `> 💬 문장` 또는 `> 💬🧐 문장`(꼬리 아래 캐릭터 지정)
            who, _, said = ln[2:].strip().partition(" ")
            out.append(f'<div style="{DECO["bubble"]}">{dk.tint(inline(said.strip(), links))}</div><div style="{DECO["tail"]}"></div>'
                       f'<div aria-hidden="true" style="{DECO["bubble_char"]}">{who[1:] or "🧐"}</div>')
        elif ln.startswith("> ") and is_emoji(ln[2:].split(" ")[0]):
            who, _, said = ln[2:].strip().partition(" ")
            out.append(f'<div data-course-char="1" style="{DECO["char"]}"><span aria-hidden="true" style="{DECO["char_icon"]}">{who}</span>'
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
            out.append(f'<ul style="{DECO["check"]}">' + "".join(f'<li style="margin:4px 0;">✅ {dk.tint(inline(x, links))}</li>' for x in items) + "</ul>")
            continue
        elif ln.startswith("|"):
            blk = []
            while i < len(lines) and lines[i].startswith("|"):
                blk.append(lines[i])
                i += 1
            out.append(chart(blk, links, chart_next) if chart_next is not None else table(blk, links))
            chart_next = None
            continue
        elif re.match(r"^(- |\d+\. )", ln):
            ordered = bool(re.match(r"^\d+\. ", ln))
            items = []
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i]).strip())
                i += 1
            tag = "ol" if ordered else "ul"
            if note_mode:
                out.append(f'<{tag} style="{DECO["note_li"]}">' + "".join(f'<li style="margin:0 0 4px;">{gray(inline(x, links))}</li>' for x in items) + f"</{tag}>")
            else:
                out.append(f'<{tag} style="{LI}">' + "".join(f'<li style="margin:0 0 6px;">{dk.tint(inline(x, links))}</li>' for x in items) + f"</{tag}>")
            continue
        elif ln.strip() == "---" or not ln.strip():
            pass
        elif ln.startswith("※") or ln.startswith("자료:"):
            out.append(f'<p style="{NOTE}">{inline(ln, links)}</p>')
        elif ln.startswith("(") and ln.endswith(")"):
            out.append(f'<p style="margin:-4px 0 16px;padding-left:{dk.ALIGN_PX}px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};">{inline(ln, links)}</p>')
        else:
            para = [ln]
            while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"^(#|\||- |\d+\. |---|※|자료:|> )", lines[i + 1]):
                i += 1
                para.append(lines[i].rstrip())
            txt = dk.tint(inline(" ".join(para), links))
            if note_mode:
                out.append(f'<p style="{DECO["note_p"]}">{gray(inline(" ".join(para), links))}</p>')
            elif not lead_done:   # 첫 문단 = 맨 위 요약 (0편은 부제 구획 다음)
                out.append(f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">{txt}</p>')
                lead_done = True
            else:
                out.append(f'<p style="{P}">{txt}</p>')
        i += 1
    return title, dk.align_titles(dk.WRAP_OPEN + "".join(out) + dk.WRAP_CLOSE)


HEAD_LABEL = "강좌"   # 머리 줄(글 제목 자리)에 보일 메뉴 이름 (2026-11-10 사용자: 여기에 타이틀 쓰지 말고 메뉴명). 글 제목 · 검색 제목은 그대로
LIST_URL = "https://alpha-scope.blogspot.com/search/label/%EA%B0%95%EC%A2%8C"   # 머리 줄 화살표 · [목록] = 강좌 글 목록


def title_block(title):
    """본문 맨 위 제목 — 머리 줄에서 내려온 진짜 제목. `연재 이름 #N` 작은 청록 줄 + 편 제목 큰 글씨."""
    series, _, ep = title.partition(" — ")
    return (f'<div data-course-title="1" style="padding:24px {dk.ALIGN_PX}px 0;margin:0 0 20px;">'
            f'<div style="font-size:15px;line-height:22px;font-weight:700;color:#0F766E;margin:0 0 6px;">{html.escape(series)}</div>'
            f'<h1 style="margin:0;font-size:26px;line-height:36px;font-weight:800;color:#111;word-break:keep-all;">{html.escape(ep or title)}</h1></div>')


# 목업 전용 — 테마 JS 가 머리 줄을 다 만든 뒤 글자만 `강좌` 로. 실제 블로그는 테마(alphaflow-home.html)에 같은 동작을 넣는다(data-head-label)
MOCK_HEAD_JS = ("<script>(function(){function go(){var b=document.querySelector('[data-head-label]');if(!b)return;"
                "var l=document.querySelector('.post-title-label')||document.querySelector('.post-title');if(l)l.textContent=b.getAttribute('data-head-label');}"
                "if(document.readyState==='complete')go();else window.addEventListener('load',go);})();</script>")


def main():
    os.makedirs(OUT, exist_ok=True)
    files = sorted(glob.glob(os.path.join(SRC, "*.md")))
    links = {os.path.basename(f): f"mock_{os.path.splitext(os.path.basename(f))[0]}.html" for f in files}
    for f in files:
        k = files.index(f)
        nxt = links[os.path.basename(files[k + 1])] if k + 1 < len(files) else "#"   # 다음 편 카드 = 다음 파일 목업 (아직 없으면 #)
        title, body = render(open(f, encoding="utf-8").read(), links, nxt)
        body = (f'<span data-head-label="{HEAD_LABEL}" hidden></span><span data-list-url="{LIST_URL}" data-nav="back" hidden></span>'
                + title_block(title) + body)
        path = dk.write_mock(body, os.path.join(OUT, links[os.path.basename(f)]), title)
        if path:
            pg = open(path, encoding="utf-8").read().replace("</body>", MOCK_HEAD_JS + "</body>", 1)
            open(path, "w", encoding="utf-8").write(pg)
        print(f"[강좌] {title} → {path}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
