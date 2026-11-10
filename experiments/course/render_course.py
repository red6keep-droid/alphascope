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
    "h2": f"display:block;margin:40px 0 16px;padding:2px 0 2px 12px;border-left:5px solid #0F766E;font-size:22px;line-height:32px;font-weight:700;color:#111;",
    "bubble": "position:relative;max-width:560px;margin:28px auto 36px;padding:18px 22px;border-radius:20px;background:#ECFDF5;"
              f"text-align:center;font-size:{dk.BODY};line-height:32px;font-weight:700;color:#134E4A;word-break:keep-all;",
    "tail": "width:0;height:0;margin:-37px auto 36px;border:12px solid transparent;border-top-color:#ECFDF5;border-bottom:0;",
    "check": f"list-style:none;margin:0 0 20px;padding:14px 16px;background:#F8FAFC;border-radius:12px;font-size:{dk.BODY};line-height:{dk.LH_BODY};color:#333;",
}
NOTE = f"font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};margin:24px 0 0;padding:12px 0 0 {dk.ALIGN_PX}px;border-top:1px solid #E2E8F0;word-break:keep-all;"


def inline(t, links):
    """**굵게** · [글](주소). 다른 편 .md 링크는 그 편 목업으로."""
    t = html.escape(t, quote=False)
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
    return dk.tint(dk.table(head, [[inline(c, links) for c in r] for r in body]))


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
            + (f'<span style="display:block;margin-top:6px;font-size:15px;line-height:24px;color:#4B5563;word-break:keep-all;">{inline(teaser, links)}</span>' if teaser else "")
            + f'</span><span style="flex:none;color:#6B7280;">{chev}</span></a>')


def render(md, links, next_href="#"):
    md = md.split("### 발행 전 확인")[0]
    lines = [ln for ln in md.splitlines() if not ln.startswith("> 초안")]
    title, out, i, lead_done = "", [], 0, False
    while i < len(lines):
        ln = lines[i].rstrip()
        if ln.startswith("# "):
            title = ln[2:].strip()
        elif ln.strip() == "## 다음 편":
            i += 1
            para = []
            while i < len(lines) and not re.match(r"^(#|---|※|자료:)", lines[i]):
                if lines[i].strip():
                    para.append(lines[i].strip())
                i += 1
            out.append(next_card(" ".join(para), next_href, links))
            continue
        elif ln.startswith("## "):
            out.append(f'<h2 style="{DECO["h2"]}">{inline(ln[3:].strip(), links)}</h2>')
        elif ln.startswith("> 💬"):
            out.append(f'<div style="{DECO["bubble"]}">{dk.tint(inline(ln[4:].strip(), links))}</div><div style="{DECO["tail"]}"></div>')
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
            out.append(table(blk, links))
            continue
        elif re.match(r"^(- |\d+\. )", ln):
            ordered = bool(re.match(r"^\d+\. ", ln))
            items = []
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i]).strip())
                i += 1
            tag = "ol" if ordered else "ul"
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
            if not lead_done:   # 첫 문단 = 맨 위 요약 (0편은 부제 구획 다음)
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
    return (f'<div data-course-title="1" style="padding:4px {dk.ALIGN_PX}px 0;margin:0 0 20px;">'
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
