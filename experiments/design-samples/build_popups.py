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


def frame(inner, h=720, page=True, body_cls="", extra_css=""):
    doc = (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           f'<style>{CSS}\nbody{{margin:0;background:#fff;}}{extra_css}</style></head><body class="{body_cls}">{PAGE if page else ""}{inner}</body></html>')
    return f'<iframe srcdoc="{html.escape(doc, quote=True)}" style="width:390px;height:{h}px;border:1px solid #CBD5E1;border-radius:12px;background:#fff;flex:none;"></iframe>'


# 공유 아이콘 = 테마 index.html ICONS 그대로(링크 · 페이스북 · X · 카카오톡) + Simple Icons 13.21.0(텔레그램 · 스레드) + 밴드 앱 아이콘 모양 선 그림(arcticons:band — 밴드는 공개 묶음에 없다). 단색 currentColor (10-23 사용자)
SHARE_ICONS = {
    '링크 복사': '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" style="flex:none;width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;"><path d="M10 13a5 5 0 0 0 7.100.1l3-3a5 5 0 0 0-7.100-7.100l-1.700 1.700"/><path d="M14 11a5 5 0 0 0-7.100-.1l-3 3a5 5 0 0 0 7.100 7.100l1.700-1.700"/></svg>',
    'Facebook': '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" style="flex:none;width:20px;height:20px;fill:currentColor;"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.990 4.388 10.954 10.125 11.854v-8.385H7.078v-3.470h3.047V9.430c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.830c-1.491 0-1.956.925-1.956 1.874v2.250h3.328l-.532 3.470h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>',
    'X': '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" style="flex:none;width:20px;height:20px;fill:currentColor;"><path d="M18.901 1.153h3.680l-8.040 9.190L24 22.846h-7.406l-5.800-7.584-6.638 7.584H.474l8.600-9.830L0 1.154h7.594l5.243 6.932ZM17.610 20.644h2.039L6.486 3.240H4.298Z"/></svg>',
    '카카오톡': '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" style="flex:none;width:20px;height:20px;fill:currentColor;"><path d="M12 3c5.799 0 10.500 3.664 10.500 8.185 0 4.520-4.701 8.184-10.500 8.184a13.500 13.500 0 0 1-1.727-.110l-4.408 2.883c-.501.265-.678.236-.482-.486l.998-3.770C2.682 16.700 1.500 14.536 1.500 11.185 1.500 6.664 6.201 3 12 3Z"/></svg>',
}


SHARE_MORE = [
    ('텔레그램', '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" style="flex:none;width:20px;height:20px;fill:currentColor;"><path fill="currentColor" d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>'),
    ('밴드', '<svg viewBox="0 0 48 48" width="20" height="20" aria-hidden="true" style="flex:none;width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:3.5;stroke-linecap:round;stroke-linejoin:round;"><path d="M16.2 27.9V8.4a3.9 3.9 0 0 0-3.9-3.9a3.9 3.9 0 0 0-3.9 3.9v19.5"/><path d="M16.2 14.387A15.602 15.602 0 1 1 8.4 27.9"/><path d="M16.2 19.18a11.7 11.7 0 1 1-3.9 8.72V8.4"/><circle cx="24" cy="27.9" r="7.8"/></svg>'),
    ('스레드', '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" style="flex:none;width:20px;height:20px;fill:currentColor;"><path fill="currentColor" d="M12.186 24h-.007c-3.581-.024-6.334-1.205-8.184-3.509C2.35 18.44 1.5 15.586 1.472 12.01v-.017c.03-3.579.879-6.43 2.525-8.482C5.845 1.205 8.6.024 12.18 0h.014c2.746.02 5.043.725 6.826 2.098 1.677 1.29 2.858 3.13 3.509 5.467l-2.04.569c-1.104-3.96-3.898-5.984-8.304-6.015-2.91.022-5.11.936-6.54 2.717C4.307 6.504 3.616 8.914 3.589 12c.027 3.086.718 5.496 2.057 7.164 1.43 1.783 3.631 2.698 6.54 2.717 2.623-.02 4.358-.631 5.8-2.045 1.647-1.613 1.618-3.593 1.09-4.798-.31-.71-.873-1.3-1.634-1.75-.192 1.352-.622 2.446-1.284 3.272-.886 1.102-2.14 1.704-3.73 1.79-1.202.065-2.361-.218-3.259-.801-1.063-.689-1.685-1.74-1.752-2.964-.065-1.19.408-2.285 1.33-3.082.88-.76 2.119-1.207 3.583-1.291a13.853 13.853 0 0 1 3.02.142c-.126-.742-.375-1.332-.75-1.757-.513-.586-1.308-.883-2.359-.89h-.029c-.844 0-1.992.232-2.721 1.32L7.734 7.847c.98-1.454 2.568-2.256 4.478-2.256h.044c3.194.02 5.097 1.975 5.287 5.388.108.046.216.094.321.142 1.49.7 2.58 1.761 3.154 3.07.797 1.82.871 4.79-1.548 7.158-1.85 1.81-4.094 2.628-7.277 2.65Zm1.003-11.69c-.242 0-.487.007-.739.021-1.836.103-2.98.946-2.916 2.143.067 1.256 1.452 1.839 2.784 1.767 1.224-.065 2.818-.543 3.086-3.71a10.5 10.5 0 0 0-2.215-.221z"/></svg>'),
    ('더 보기', '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" style="flex:none;width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;"><path d="M12 3v12"/><path d="M8 7l4-4 4 4"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/></svg>'),
]


def samples():
    s = []
    # ── A. 가운데 상자 (.rt-pop) ─────────────────────────────
    t, b = tip("stock-radar/output/mock_NVDA.html", 4)
    s.append(("A1", "툴팁 팝업", "카드 제목 옆 ? 아이콘 · 모든 리포트", "테마 JS 가 data-tip 글을 줄마다 나눠 그린다 · 글 19/28 · 묶음 사이 21 · 맨 아래 출처 13",
              frame(box(t, b))))
    t, b = pick("kr-stocks/output/mock_035720.html", lambda p, ti, b: p.startswith("ev") and "grid-template-columns:1fr 1fr" in b)
    b = respace(b)
    s.append(("A2", "뉴스 요약 팝업", "뉴스 줄 누르기 · 종목 · 데일리 · 홈", "요약 줄 19/28 · 줄 사이 21 · 관련 종목 칸 · 원문 보기 13",
              frame(box(t, b, "news-pop", "rt-pop-body news-pop-body"))))
    t, b = pick("stock-radar/output/NVDA.html", lambda p, ti, b: p.startswith("pp"))
    b = respace(b).replace('display:flex;justify-content:space-between;align-items:center;gap:12px;margin:16px 0 0;', 'display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px 12px;margin:16px 0 0;', 1)
    b = b.replace('display:inline-flex;text-decoration:none;">', 'display:inline-flex;text-decoration:none;white-space:nowrap;">', 1).replace('style="font-size:13px;line-height:19px;color:#6B7280;text-decoration:underline', 'style="margin-left:auto;font-size:13px;line-height:19px;color:#6B7280;text-decoration:underline', 1)
    s.append(("A3", "인물 발언 팝업", "인물 발언 줄 · 종목 페이지", "뉴스 요약과 같은 줄 + `발언 더 보기` 버튼(한 줄) · 좁으면 원문 보기가 다음 줄 오른쪽",
              frame(box(t, b, "news-pop", "rt-pop-body news-pop-body"))))
    t, b = pick("issue_store/output/mock_kr_why-forecast-2026-005.html", lambda p, ti, b: p.startswith("why") and "dashed" in b and "15px;line-height:22px" in b)
    t2, b2 = pick("issue_store/output/mock_kr_why-forecast-2026-005.html", lambda p, ti, b: p.startswith("whyart"))
    s.append(("A4", "전망 요인 팝업", "증시 전망 날짜 줄 `반등 요인` 등", "일반 분류 소제목(아이콘 + 15 굵게) · 점선 구분 · 줄 사이 21 · `신호 기준` 버튼 · 줄을 누르면 위에 한 겹 더(A4-2)",
              frame(box(t, b, "news-pop", "rt-pop-body news-pop-body"))))
    s.append(("A4-2", "팝업 위 팝업", "A4 안 기사 줄 누르기", "같은 상자를 위에 한 겹 더 · 뒤 팝업은 어둡게 두 번 덮인다",
              frame(box(t, b, "news-pop", "rt-pop-body news-pop-body") + box(t2, b2, "news-pop", "rt-pop-body news-pop-body", z=1001))))
    t, b = pick("issue_store/output/mock_forecast-cases.html", lambda p, ti, b: p.startswith("whyopen"))
    s.append(("A5", "향방미정 팝업", "증시 전망 타임라인 위 한 줄", "소제목 없이 기사 줄만 · 줄 사이 21",
              frame(box(t, b, "news-pop", "rt-pop-body news-pop-body"))))
    t, b = pick("issue_store/output/mock_issue_watch.html", lambda p, ti, b: p.startswith("iwday") and "dashed" in b)
    s.append(("A6", "이슈 날짜 팝업", "이슈 모니터링 날짜 줄 (다른 창 작업 중 · 커밋 전 목업)", "기준 팝업 — 방향 묶음 소제목(아이콘 + 19 굵게 방향 색) · 점선 구분 · 줄 사이 21",
              frame(box(t, b, "news-pop", "rt-pop-body news-pop-body"))))
    more = [(n, svg) for n, svg in SHARE_ICONS.items() if n != "링크 복사"] + SHARE_MORE
    tiles = "".join(f'<li><span class="sharing-platform-button" role="button">{svg}<span class="platform-sharing-text">{n}</span></span></li>' for n, svg in more)
    main = f'<li class="share-main"><span class="sharing-platform-button" role="button">{SHARE_ICONS["링크 복사"]}<span class="platform-sharing-text">링크 복사</span></span></li>'
    s.append(("A7", "공유 팝업", "글 제목 옆 공유 버튼", "짧은 창 400 · 링크 복사 큰 버튼(48 · 16 굵게) · 아래 4칸 격자, 칸 = 실제 로고 22 위 · 이름 12 보통 아래 · `더 보기`는 폰에서만",
              frame(box("공유", f'<ul class="share-buttons">{main}{tiles}</ul>', "share-pop", "share-pop-body"), 460)))
    G = '<svg viewBox="0 0 24 24" width="18" height="18"><circle cx="12" cy="12" r="10" fill="#4285F4"/></svg>'
    acct = ('<p class="as-acct-note">댓글에 쓰는 구글 계정으로 로그인합니다.</p>'
            f'<button type="button" class="as-acct-btn">{G}<span>Google 계정으로 로그인</span></button><p class="as-acct-err"></p>')
    s.append(("A8", "계정 팝업", "헤더 사람 아이콘", "짧은 창 400 · 안내 14 · 버튼 16 굵게 · 내용 시작 26",
              frame(box("로그인", acct, "as-acct", close=X_ROUND), 420)))
    # ── B. 그 밖의 틀 ─────────────────────────────
    search = ('<div class="as-search-layer"><div class="as-search-box" role="dialog"><form class="as-search-form" onsubmit="return false">'
              '<input type="search" placeholder="종목 · 질문 검색" value="엔비디아 왜 떨어졌어"><button type="button" class="as-x" aria-label="닫기"><svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="16"/><path d="M11.5 11.5l9 9M20.5 11.5l-9 9"/></svg></button></form>'
              '<div class="as-search-out"><div class="as-card"><header><h3>엔비디아</h3><span class="as-tk">NVDA</span><span class="as-mkt as-us">미국</span>'
              '<span class="as-day">11.13 종가</span></header><p class="as-say">오늘 <b class="as-dn">▼ 3.6%</b> 내렸습니다.</p>'
              '<div class="as-sec"><h4>왜 떨어졌나</h4><div class="as-row"><span class="as-k">기술주 급락</span><span class="as-v">11.13</span></div></div></div>'
              '<p class="as-hint">이렇게도 물어보세요</p><div class="as-chips"><button type="button">삼성전자 실적</button><button type="button">코스피 전망</button></div></div></div></div>')
    s.append(("B1", "검색 창", "헤더 돋보기", "위에서 내려오는 판(PC 760) · 폰은 화면 전체 · 닫기 회색 원 · 행간 정수 px",
              frame(search)))
    chat = ('<div class="as-chat"><header><b>AlphaScope에 물어보기</b><button type="button" class="as-x" aria-label="닫기"><svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="16"/><path d="M11.5 11.5l9 9M20.5 11.5l-9 9"/></svg></button></header><div class="as-log">'
            '<div class="as-msg as-me">코스피 왜 올랐어?</div><div class="as-msg as-bot"><p>오늘 코스피는 반도체가 이끌었습니다.</p></div></div>'
            '<form onsubmit="return false"><input placeholder="질문을 적어 주세요"><button type="button">보내기</button></form><footer>AI 답변은 틀릴 수 있습니다</footer></div>')
    s.append(("B2", "질문하기 창", "오른쪽 아래 버튼 (지금 꺼 둠)", "PC 오른쪽 아래 400 패널 · 폰은 화면 전체 · 닫기 회색 원 · 행간 정수 px",
              frame(chat)))
    close_svg = ('<button type="button" class="nav-close"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">'
                 '<path d="M3 3l10 10M13 3L3 13"/></svg></button>')
    links = "".join(f'<div class="menu-row"><a class="nav-item" href="#">{n}</a></div>' for n in
                    ("미국 증시 리포트", "한국 증시 리포트", "미국 시가총액 상위 10 종목", "한국 시가총액 상위 10 종목", "증시 전망", "주요 인물 발언", "방송 브리핑"))
    drawer = (f'<div class="nav-overlay"></div><nav class="menu-items is-open" style="display:flex;">{close_svg}'
              f'<div class="menu-mk"><a class="nav-item" href="#">미국</a><a class="nav-item" href="#">한국</a></div>{links}</nav>')
    s.append(("B3", "메뉴 서랍", "헤더 메뉴 아이콘", "오른쪽에서 밀려 나옴 · 가림막 투명(10-13 사용자) · 닫기 회색 원 32",
              frame(drawer)))
    return s


DIFF = [   # 2026-11-14 사용자 결정 — 기준 = 이슈 날짜 팝업(이란 전쟁 뉴스)
    ("닫기 버튼", "모두 회색 원 32 · #EEF0F3 · #4B5563 × 선 2 — 11-12 닫기 통일 규칙 그대로 (팝업 · 서랍 · 검색 · 질문하기 · 계정)"),
    ("가림막", "rgba(15,23,42,.45), 화면보다 위아래 100 더 덮는다 — 폰 아래쪽이 밝게 남던 것 고침 (서랍은 투명 그대로, 10-13 사용자)"),
    ("팝업 글씨", "19/28 하나 (툴팁도 · 폰도) — 옛 툴팁 19/35 · 폰 16/32"),
    ("간격", "내용 시작 = 구분선 아래 26 · 글머리 줄 사이 21 · 소제목 ~ 첫 줄 11 · 들여쓰기 7"),
    ("글머리 점", "3px · #111 · 위 12"),
    ("소제목 두 가지", "방향 묶음 = 아이콘 + 19/28 굵게 방향 색(A6) · 일반 분류 = 아이콘 + 15/22 굵게 검정(A4)"),
    ("묶음 사이 구분선", "점선 1px #CBD5E1 (위 15 · 아래 30)"),
    ("맨 아래 줄", "작은 글자(원문 보기 · 출처) = 13/19 #6B7280 · 버튼 = 더 보기 버튼 하나(14 굵게 · 테두리, 글자 한 줄)"),
    ("폭", "짧은 창(계정 · 공유) 400 · 나머지 520"),
    ("검색 · 질문하기 글씨", "행간 배수(1.6 · 1.7) → 정수 px (13/21 · 15/24 · 16/27)"),
]


def render():
    s = samples()
    cards = "".join(
        f'<section style="display:flex;flex-direction:column;gap:8px;width:390px;"><div style="display:flex;align-items:baseline;gap:8px;">'
        f'<b style="font-size:13px;color:#fff;background:#111;border-radius:6px;padding:2px 7px;">{k}</b><b style="font-size:18px;">{n}</b></div>'
        f'<div style="font-size:13px;color:#6B7280;line-height:19px;">{where}</div><div style="font-size:14px;color:#333;line-height:21px;min-height:42px;">{note}</div>{fr}</section>'
        for k, n, where, note, fr in s)
    rows = "".join(f'<tr><th>{r[0]}</th><td>{r[1]}</td></tr>' for r in DIFF)
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
<h2>정한 규칙 (2026-11-14)</h2>
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
