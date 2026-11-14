"""블로그 팝업 유형 모음 목업 (2026-11-14 사용자: "팝업창도 제각각 — 샘플을 전부 모아 유형을 목업으로 정리, 그래프처럼").

틀(상자 · 닫기 · 가림막)은 테마 index.html CSS 를 그대로 읽어 쓰고, 안의 글은 최신 목업 출력물(output/*.html)의
[data-news-pop-body] · [data-tip] 을 그대로 꺼내 넣는다. 각 샘플은 폭 390 iframe — 테마의 폰 @media 가 그대로 걸린다.
그래프 확대(.img-pop)는 PNG 그림을 지울 예정이라 뺀다.

실행: python3 experiments/design-samples/build_popups.py → experiments/design-samples/output/mock_popups.html
"""
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "experiments"
OUT = Path(__file__).resolve().parent / "output" / "mock_popups.html"


def theme_css():
    t = (ROOT / "index.html").read_text(encoding="utf-8")
    return t.split("<b:skin version='1.0'><![CDATA[", 1)[1].split("]]></b:skin>", 1)[0]


def bodies(t):
    for m in re.finditer(r'<div data-news-pop-body="([^"]*)" data-news-pop-title="([^"]*)" hidden>', t):
        i, depth = m.end(), 1
        for mm in re.finditer(r"<(/?)div\b", t[i:]):
            depth += -1 if mm.group(1) else 1
            if depth == 0:
                yield m.group(1), m.group(2), t[i:i + mm.start()]
                break


def pick(rel, pred):
    t = (EXP / rel).read_text(encoding="utf-8")
    for pid, title, b in bodies(t):
        if pred(pid, title, b):
            return title, b
    raise SystemExit(f"샘플 없음: {rel}")


def respace(b):
    """종목 페이지 출력물은 다시 돌리지 않았다 — 뉴스 요약 줄의 옛 여백(11 위아래 · 들여쓰기 0)을 지금 코드 값(dk.pop_li_margin · POP_LI_PAD)으로 바꿔 넣는다."""
    import sys
    sys.path.insert(0, str(EXP))
    import design_kit as dk
    old = f"gap:7px;margin:{dk.POP_ITEM_GAP}px 0;\"><span style=\"flex:none;width:3px"
    parts = b.split(old)
    return parts[0] + "".join(f"gap:7px;margin:{dk.pop_li_margin(i)};padding-left:{dk.POP_LI_PAD}px;\"><span style=\"flex:none;width:3px" + x for i, x in enumerate(parts[1:]))


def tip(rel, nth):
    """테마 JS fill() 을 그대로 옮김 — 줄마다 칸, `· ` 글머리표, `용어 : 설명` 굵게, data-src → 출처 줄."""
    t = (EXP / rel).read_text(encoding="utf-8")
    m = list(re.finditer(r'data-tip="([^"]*)"([^>]*)', t))[nth]
    text = html.unescape(m.group(1))
    src = re.search(r'data-src="([^"]*)"', m.group(2))
    before = t[max(0, m.start() - 600):m.start()]
    before = before[:before.rfind("<")]   # ? 아이콘을 여는 태그 앞까지
    before = re.sub(r"</?(span|b|wbr)\b[^>]*>", "", before)   # 글자 안 태그(줄 안 묶음)는 이어 붙이고
    title = html.unescape(re.sub(r"<[^>]+>", "\n", before).strip().split("\n")[-1].strip())   # 블록 태그에서 끊어 마지막 덩어리 = 카드 제목 (테마 titleOf)
    out = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        b = re.match(r"^\s*[·•\-]\s+(.*)$", line)
        if b:
            lb = re.match(r"^([^·:=]{1,14}?) [:=] (.*)$", b.group(1))
            inner = f"<b>{html.escape(lb.group(1))}</b> : {html.escape(lb.group(2))}" if lb else html.escape(b.group(1))
            out.append(f'<div class="rt-pop-li"><span class="rt-pop-dot"></span><span>{inner}</span></div>')
        else:
            lm = re.match(r"^\s*([^·:=]{1,14}?) [:=] (.*)$", line)
            out.append(f'<div class="rt-pop-p has-label"><b>{html.escape(lm.group(1))}</b> : {html.escape(lm.group(2))}</div>' if lm
                       else f'<div class="rt-pop-p">{html.escape(line)}</div>')
    if src:
        out.append(f'<div class="rt-pop-src">출처 : {html.escape(src.group(1))} 데이터로 계산한 내용입니다.</div>')
    return title, "".join(out)


X = '<button type="button" class="rt-pop-close" aria-label="닫기">×</button>'
X_ROUND = ('<button type="button" class="as-acct-x" aria-label="닫기"><svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2" '
           'stroke-linecap="round" aria-hidden="true"><path d="M3 3l8 8M11 3l-8 8"/></svg></button>')


def box(title, body, cls="", body_cls="rt-pop-body", close=X, z=None):
    zs = f' style="z-index:{z}"' if z else ""
    return (f'<div class="rt-pop {cls}"{zs}><div class="rt-pop-box" role="dialog"><div class="rt-pop-head"><div class="rt-pop-title">{title}</div>{close}</div>'
            f'<div class="{body_cls}">{body}</div></div></div>')


PAGE = ('<div class="post-body" style="padding:24px 16px;">' + "".join(
    f'<div style="height:{h}px;margin:0 0 12px;border-radius:12px;background:#F1F5F9;"></div>' for h in (40, 160, 90, 220, 120, 180)) + "</div>")


def frame(inner, h=720, page=True, body_cls=""):
    doc = (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           f'<style>{CSS}\nbody{{margin:0;background:#fff;}}</style></head><body class="{body_cls}">{PAGE if page else ""}{inner}</body></html>')
    return f'<iframe srcdoc="{html.escape(doc, quote=True)}" style="width:390px;height:{h}px;border:1px solid #CBD5E1;border-radius:12px;background:#fff;flex:none;"></iframe>'


SHARE_ICONS = {
    "링크 복사": '<svg viewBox="0 0 24 24" width="20" height="20" style="fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;"><path d="M10 13a5 5 0 0 0 7.1.1l3-3a5 5 0 0 0-7.1-7.1l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.1-.1l-3 3a5 5 0 0 0 7.1 7.1l1.7-1.7"/></svg>',
    "Facebook": '<svg viewBox="0 0 24 24" width="20" height="20"><circle cx="12" cy="12" r="11" fill="currentColor"/></svg>',
    "X": '<svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M18.9 1.2h3.7l-8 9.2L24 22.8h-7.4l-5.8-7.6-6.6 7.6H.5l8.6-9.8L0 1.2h7.6l5.2 6.9Z"/></svg>',
    "카카오톡": '<svg viewBox="0 0 24 24" width="20" height="20"><ellipse cx="12" cy="11" rx="10.5" ry="8.2" fill="currentColor"/></svg>',
}


def samples():
    s = []
    # ── A. 가운데 상자 (.rt-pop) ─────────────────────────────
    t, b = tip("stock-radar/output/mock_NVDA.html", 4)
    s.append(("A1", "툴팁 팝업", "카드 제목 옆 ? 아이콘 · 모든 리포트", "테마 JS 가 data-tip 글을 줄마다 나눠 그린다 · 글 19/35(폰 16/32) · 점 3px 본문색 · 맨 아래 출처 줄",
              frame(box(t, b))))
    t, b = pick("kr-stocks/output/mock_035720.html", lambda p, ti, b: p.startswith("ev") and "grid-template-columns:1fr 1fr" in b)
    b = respace(b)
    s.append(("A2", "뉴스 요약 팝업", "뉴스 줄 누르기 · 종목 · 데일리 · 홈", "news-pop-body 16/26 위에 줄마다 인라인 19/28 · 점 3px 검정 · 관련 종목 칸 · 원문 보기 13px",
              frame(box(t, b, "news-pop", "rt-pop-body news-pop-body"))))
    t, b = pick("stock-radar/output/NVDA.html", lambda p, ti, b: p.startswith("pp"))
    b = respace(b)
    s.append(("A3", "인물 발언 팝업", "인물 발언 줄 · 종목 페이지", "뉴스 요약과 같은 줄 + 아래 `발언 더 보기` 버튼(14 굵게, 테두리 — 폰에서 두 줄로 꺾인다) · 원문 보기",
              frame(box(t, b, "news-pop", "rt-pop-body news-pop-body"))))
    t, b = pick("issue_store/output/mock_kr_why-forecast-2026-005.html", lambda p, ti, b: p.startswith("why") and "dashed" in b and "15px;line-height:22px" in b)
    t2, b2 = pick("issue_store/output/mock_kr_why-forecast-2026-005.html", lambda p, ti, b: p.startswith("whyart"))
    s.append(("A4", "전망 요인 팝업", "증시 전망 날짜 줄 `반등 요인` 등", "소제목 = 작은 아이콘 + 15/22 굵게 · 점선 구분(#CBD5E1) · 기사 줄 19/28 · 맨 아래 `신호 기준` 버튼 · 줄을 누르면 위에 한 겹 더(A4-2)",
              frame(box(t, b, "news-pop", "rt-pop-body news-pop-body"))))
    s.append(("A4-2", "팝업 위 팝업", "A4 안 기사 줄 누르기", "같은 상자를 위에 한 겹 더 · 뒤 팝업은 어둡게 두 번 덮인다",
              frame(box(t, b, "news-pop", "rt-pop-body news-pop-body") + box(t2, b2, "news-pop", "rt-pop-body news-pop-body", z=1001))))
    t, b = pick("issue_store/output/mock_forecast-cases.html", lambda p, ti, b: p.startswith("whyopen"))
    s.append(("A5", "향방미정 팝업", "증시 전망 타임라인 위 한 줄", "소제목 없이 기사 줄만 · 줄마다 날짜 · 매체",
              frame(box(t, b, "news-pop", "rt-pop-body news-pop-body"))))
    t, b = pick("issue_store/output/mock_issue_watch.html", lambda p, ti, b: p.startswith("iwday") and "dashed" in b)
    s.append(("A6", "이슈 날짜 팝업", "이슈 모니터링 날짜 줄 (다른 창 작업 중 · 커밋 전 목업)", "방향 소제목 19/28 굵게 · 방향 색 · 앞 아이콘 · 점선 구분 · `논의중` 라벨 · `기사 n건`",
              frame(box(t, b, "news-pop", "rt-pop-body news-pop-body"))))
    items = "".join(f'<li><span class="sharing-platform-button" role="button">{svg}<span class="platform-sharing-text">{n}</span></span></li>' for n, svg in SHARE_ICONS.items())
    s.append(("A7", "공유 팝업", "글 제목 옆 공유 버튼", "같은 상자 · 버튼 네 개(테두리 알약) · 글이 아니라 버튼만",
              frame(box("공유", f'<ul class="share-buttons">{items}</ul>', "share-pop", "share-pop-body"), 420)))
    G = '<svg viewBox="0 0 24 24" width="18" height="18"><circle cx="12" cy="12" r="10" fill="#4285F4"/></svg>'
    acct = ('<p class="as-acct-note">댓글에 쓰는 구글 계정으로 로그인합니다.</p>'
            f'<button type="button" class="as-acct-btn">{G}<span>Google 계정으로 로그인</span></button><p class="as-acct-err"></p>')
    s.append(("A8", "계정 팝업", "헤더 사람 아이콘", "같은 상자인데 폭 400 · 닫기만 회색 원(다른 팝업은 테두리 네모 ×) · 안내 14px · 버튼 16 굵게",
              frame(box("로그인", acct, "as-acct", close=X_ROUND), 420)))
    # ── B. 그 밖의 틀 ─────────────────────────────
    search = ('<div class="as-search-layer"><div class="as-search-box" role="dialog"><form class="as-search-form" onsubmit="return false">'
              '<input type="search" placeholder="종목 · 질문 검색" value="엔비디아 왜 떨어졌어"><button type="button" class="as-x">닫기</button></form>'
              '<div class="as-search-out"><div class="as-card"><header><h3>엔비디아</h3><span class="as-tk">NVDA</span><span class="as-mkt as-us">미국</span>'
              '<span class="as-day">11.13 종가</span></header><p class="as-say">오늘 <b class="as-dn">▼ 3.6%</b> 내렸습니다.</p>'
              '<div class="as-sec"><h4>왜 떨어졌나</h4><div class="as-row"><span class="as-k">기술주 급락</span><span class="as-v">11.13</span></div></div></div>'
              '<p class="as-hint">이렇게도 물어보세요</p><div class="as-chips"><button type="button">삼성전자 실적</button><button type="button">코스피 전망</button></div></div></div></div>')
    s.append(("B1", "검색 창", "헤더 돋보기", "위에서 내려오는 판(PC 폭 760 · 아래 모서리 16) · 폰은 화면 전체 · 닫기 = 글자 `닫기` · 글 15~20 · 행간 1.7 배수(정수 px 아님)",
              frame(search)))
    chat = ('<div class="as-chat"><header><b>질문하기</b><button type="button" class="as-x">닫기</button></header><div class="as-log">'
            '<div class="as-msg as-me">코스피 왜 올랐어?</div><div class="as-msg as-bot"><p>오늘 코스피는 반도체가 이끌었습니다.</p></div></div>'
            '<form onsubmit="return false"><input placeholder="질문을 적어 주세요"><button type="button">보내기</button></form><footer>AI 답변은 틀릴 수 있습니다</footer></div>')
    s.append(("B2", "질문하기 창", "오른쪽 아래 버튼 (지금 꺼 둠)", "PC 오른쪽 아래 400 패널(모서리 16) · 폰은 화면 전체 · 가림막 없음 · 닫기 = 글자",
              frame(chat)))
    close_svg = ('<button type="button" class="nav-close"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">'
                 '<path d="M3 3l10 10M13 3L3 13"/></svg></button>')
    links = "".join(f'<div class="menu-row"><a class="nav-item" href="#">{n}</a></div>' for n in
                    ("미국 증시 리포트", "한국 증시 리포트", "미국 시가총액 상위 10 종목", "한국 시가총액 상위 10 종목", "증시 전망", "주요 인물 발언", "방송 브리핑"))
    drawer = (f'<div class="nav-overlay"></div><nav class="menu-items is-open" style="display:flex;">{close_svg}'
              f'<div class="menu-mk"><a class="nav-item" href="#">미국</a><a class="nav-item" href="#">한국</a></div>{links}</nav>')
    s.append(("B3", "메뉴 서랍", "헤더 메뉴 아이콘", "오른쪽에서 밀려 나옴 · 가림막 투명(어둡게 하지 않음, 10-13 사용자) · 닫기 = 테두리 네모 36 + 선 ×",
              frame(drawer)))
    return s


DIFF = [
    ("닫기 버튼", "테두리 네모 32 · 글자 × (A1~A7)", "회색 원 32 · 선 × (A8 계정)", "테두리 네모 36 · 선 × (B3 서랍)", "글자 `닫기` (B1 · B2)"),
    ("가림막", "어둡게 .45 (A · B1)", "투명 (B3 서랍)", "없음 (B2 질문하기)", "아주 어둡게 .92 (그래프 확대 — 지울 것)"),
    ("상자 모서리 · 폭", "12 · 520 (A)", "12 · 400 (A8 계정)", "아래만 16 · 760 (B1 검색)", "16 · 400 (B2)"),
    ("본문 글자", "19/35 · 폰 16/32 (A1 툴팁)", "19/28 줄마다 인라인 (A2~A6)", "15 · 행간 1.6~1.7 배수 (B1 · B2)", "14 안내 · 16 버튼 (A8)"),
    ("글머리 점", "3px · 본문색 · 위 15 · 들여 8 (A1)", "3px · 검정 · 위 12 · 들여 0 (A2 · A3)", "3px · 검정 · 들여 7 (A4~A6)", ""),
    ("소제목", "없음 (A1 · A2 · A3 · A5)", "아이콘 + 15/22 굵게 검정 (A4)", "19/28 굵게 방향 색 + 아이콘 (A6)", ""),
    ("구분선", "제목 아래 실선 #E2E8F0 (A 전부)", "출처 위 실선 (A1)", "점선 #CBD5E1 (A4 · A6) — 그래프는 점선 없앴다", ""),
    ("맨 아래 줄", "출처 14px 회색 (A1)", "원문 보기 13px 밑줄 오른쪽 (A2 · A3)", "`발언 더 보기` 버튼 14 (A3)", "`신호 기준` 버튼 14 (A4)"),
]


def render():
    s = samples()
    cards = "".join(
        f'<section style="display:flex;flex-direction:column;gap:8px;width:390px;"><div style="display:flex;align-items:baseline;gap:8px;">'
        f'<b style="font-size:13px;color:#fff;background:#111;border-radius:6px;padding:2px 7px;">{k}</b><b style="font-size:18px;">{n}</b></div>'
        f'<div style="font-size:13px;color:#6B7280;line-height:19px;">{where}</div><div style="font-size:14px;color:#333;line-height:21px;min-height:42px;">{note}</div>{fr}</section>'
        for k, n, where, note, fr in s)
    rows = "".join(f'<tr><th>{r[0]}</th>' + "".join(f"<td>{c}</td>" for c in r[1:]) + "</tr>" for r in DIFF)
    doc = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>팝업 유형 모음</title><style>
body{{margin:0;padding:24px 16px 60px;font-family:-apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;color:#111;background:#F8FAFC;}}
h1{{font-size:24px;margin:0 0 6px;}} h2{{font-size:19px;margin:36px 0 12px;}} p.lead{{margin:0 0 4px;font-size:15px;color:#475569;line-height:24px;}}
.grid{{display:flex;flex-wrap:wrap;gap:28px 24px;}}
table{{border-collapse:collapse;background:#fff;font-size:14px;line-height:21px;}} th,td{{border:1px solid #E2E8F0;padding:8px 10px;text-align:left;vertical-align:top;}}
th{{background:#F1F5F9;white-space:nowrap;}} .wrap{{overflow-x:auto;}}
</style></head><body>
<h1>블로그 팝업 유형 모음</h1>
<p class="lead">틀 = 테마 index.html CSS 그대로 · 안의 글 = 최신 목업 출력물에서 그대로 꺼냄 · 폭 390(폰). 그래프 확대 팝업은 PNG 를 지울 예정이라 뺐습니다.</p>
<h2>무엇이 제각각인가</h2>
<div class="wrap"><table><tbody>{rows}</tbody></table></div>
<h2>A. 가운데 상자 (테마 .rt-pop) · B. 그 밖의 틀</h2>
<div class="grid">{cards}</div>
</body></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    print(OUT, len(s), "개")


CSS = theme_css()

if __name__ == "__main__":
    render()
