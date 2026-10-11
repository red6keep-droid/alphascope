"""nvda_analysis.json (+ narrative.json) → Blogger 본문 HTML (기획서 10절). 섹션·라벨은 render_report(MD)와 같고 시각 규칙은 trump-trend와 같다
— 18px 본문, 회색 밑줄 H2, 상승 빨강·하락 파랑, 좁은 화면에서 표만 가로 스크롤. 숫자는 파이썬이 그리고 문장은 narrative.json에서만.

출력:
    output/nvda_report_body.html   Blogger 본문
    output/nvda_report.html        브라우저 미리보기
    output/title.txt               게시 제목
"""

import datetime
import html as html_mod
import json
import os
import re
import sys

import config
import render_report as rr
import report_title

# 구획 제목 (디자인-가이드라인.md 2절): 아래 여백 14px. 구분선은 바로 아래가 글(목록·문장)일 때만 — 카드·표·그림이 오면 그 테두리가 경계라 선을 긋지 않는다
H2 = "color:#111;margin:28px 0 14px;padding:0;"
H2_LINE = "border-bottom:2px solid #eee;padding-bottom:8px;"
_NO_LINE_START = re.compile(r'^\s*(<div style="(?:overflow-x:auto;|background:)|<img\b)')   # 표 래퍼 · 카드 · 그림
UP, DOWN, MUTED, WARN = "#d93025", "#1a73e8", "#999", "#e8710a"
# 글자 크기 체계 (디자인-가이드라인.md 3절): 본문은 바깥 div의 18px 하나 — 강조한다고 키우지 않는다. 라벨·안내·날짜는 한 단계 작게(16px), 범례·면책은 14px
SMALL, TINY = "16px", "14px"
# 강조 카드 (가이드라인 2절): 크기 대신 연한 배경 카드로 강조. 라벨 pill 색
CARD = "background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:12px 14px;"           # 기본 카드 (오늘 한 줄)
CARD_EMPH = "background:#FFF7ED;border:1px solid #FFEDD5;border-radius:10px;padding:10px 14px;"       # 강조 카드 (법무·규제 이벤트)
PILL = {"area": ("#F1F5F9", "#334155"), "positive": ("#FEE2E2", "#B91C1C"), "negative": ("#DBEAFE", "#1D4ED8"),
        "uncertain": ("#FFEDD5", "#C2410C"), "neutral": ("#F1F5F9", "#64748B")}
DIR_COLOR = {"positive": UP, "negative": DOWN, "uncertain": WARN, "neutral": MUTED}
PREVIEW = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__</title></head>
<body style="max-width:900px;margin:0 auto;padding:16px;background:#fff;"><h1 style="font-size:26px;">__TITLE__</h1>__BODY__</body></html>"""


def _esc(t):
    return html_mod.escape(str(t), quote=False)


def _signed(v, digits=2, suffix="%"):
    if v is None:
        return f'<span style="color:{MUTED};">—</span>'
    return f'<span style="color:{UP if v >= 0 else DOWN};font-weight:bold;">{v:+.{digits}f}{suffix}</span>'


WRAP_AT = 24   # 이보다 긴 글자 칸만 줄바꿈 허용 (어절 단위) — 나머지는 한 줄로


def _cell(c):
    """표 칸 — 모바일에서 글자를 좁은 칸에 밀어 넣지 않는다 (2026-10-11 사용자).

    짧은 칸은 nowrap: 열이 좁아지면 표가 옆으로 넘쳐 가로 스크롤이 된다(테마 .post-body table이 overflow-x:auto).
    긴 문장 칸만 넓이를 확보해(min-width) 어절 단위로만 줄을 바꾼다. 테마의 overflow-wrap:anywhere(글자 중간 끊김)는 칸에서 끈다.
    """
    text = re.sub(r"<[^>]+>", "", str(c))
    if len(text) > WRAP_AT:
        return f'<td style="border:1px solid #ddd;padding:6px 8px;min-width:18em;word-break:keep-all;overflow-wrap:normal;">{c}</td>'
    return f'<td style="border:1px solid #ddd;padding:6px 8px;white-space:nowrap;">{c}</td>'


def _table(headers, rows):
    th = "".join(f'<th style="border:1px solid #ddd;padding:6px 8px;background:#f5f5f5;text-align:left;white-space:nowrap;">{_esc(h)}</th>' for h in headers)
    body = "".join("<tr>" + "".join(_cell(c) for c in r) + "</tr>" for r in rows)
    return (f'<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;margin:0 0 8px;">'
            f"<tr>{th}</tr>{body}</table></div>")


def _h2(t, line=True):
    return f'<h2 style="{H2}{H2_LINE if line else ""}">{_esc(t)}</h2>'


def _section(title, html):
    """제목 + 내용. 내용의 첫 요소가 카드·표·그림이면 제목 밑 구분선을 뺀다 (2026-10-11 사용자 규칙)."""
    return _h2(title, line=not _NO_LINE_START.match(html or "")) + (html or "")


INFO_ICON = ('<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" style="vertical-align:-2px;margin-right:4px;" fill="none" stroke="currentColor" stroke-width="1.6">'
             '<circle cx="8" cy="8" r="6.5"/><path d="M8 7.2v4" stroke-linecap="round"/><circle cx="8" cy="5" r=".9" fill="currentColor" stroke="none"/></svg>')
NOTE = "#6B7280"   # 안내 줄 회색 (테마 gray-500)


def _note(t):
    """구획 안내 줄 — 내용 아래, 본문보다 한 단계 작게(15px), 회색, 안내 아이콘 (디자인-가이드라인.md 2절).

    제목에 넣던 조건·범위("7일 이내 · 법원 일정 30일", "15건")를 여기로 옮긴다. 홈 카드는 border-top 요소를 건너뛰므로 카드에 섞이지 않는다.
    """
    return f'<div style="margin:8px 0 4px;padding-top:6px;border-top:1px solid #f3f3f3;font-size:{SMALL};color:{NOTE};">{INFO_ICON}{_esc(t)}</div>'


UL = "margin:0 0 8px 20px;padding:0;list-style:disc;"   # 위 여백 0 — 제목 아래 14px는 제목이 갖는다   # 모든 목록 공통 — 글머리표 기준선이 구획마다 달라지지 않게 (디자인-가이드라인 3절)
LI = "margin:6px 0;"


def _ul(items_html):
    return f"<ul style='{UL}'>" + "".join(items_html) + "</ul>"


def _muted(t):
    return f'<div style="color:{MUTED};font-size:{SMALL};margin:6px 0;">{_esc(t)}</div>'


def _pill(text, kind):
    bg, fg = PILL.get(kind, PILL["neutral"])
    return (f'<span style="display:inline-block;background:{bg};color:{fg};border-radius:999px;padding:1px 9px;'
            f'font-size:{SMALL};font-weight:700;line-height:1.5;white-space:nowrap;vertical-align:1px;">{_esc(text)}</span>')


def _tag(area, direction):
    """영역·방향 라벨 — 알약 두 개, 본문보다 한 단계 작게 (가이드라인 5절 라벨)."""
    return _pill(rr.AREA_KO.get(area, area), "area") + " " + _pill(rr.DIR_KO.get(direction, direction), direction)


# ── 섹션 ────────────────────────────────────────────────────────────────

def _notice(a):
    ds = a["data_status"]
    parts = []
    if ds.get("test_mode"):
        parts.append(f"<b>🧪 테스트 운영 중</b> — {_esc(config.TEST_NOTICE)}")
    if ds.get("items_pending"):
        parts.append(f"⚠️ 기사 {ds['items_pending']}건이 아직 분류되지 않아 오늘 항목이 불완전할 수 있습니다 (다음 실행에서 이어서 분류).")
    if not parts:
        return ""
    return ('<div style="background:#fff8e1;border:1px solid #f4d37a;border-radius:6px;padding:10px 14px;line-height:1.6;margin:0 0 12px;">'
            + "<br>".join(parts) + "</div>")


TILE = ("display:inline-block;vertical-align:top;margin:0 6px 6px 0;padding:6px 10px;background:#fff;border:1px solid #E2E8F0;"
        "border-radius:8px;white-space:nowrap;line-height:1.4;")
TICKER = f"display:block;font-size:{TINY};font-weight:700;color:#64748B;letter-spacing:.3px;"


def _arrow(v, digits=2, unit="%"):
    """증감 표기 (가이드라인 4절·graph-v1 arrow): ▲ 상승 빨강 · ▼ 하락 파랑 · 0은 회색. 부호 대신 삼각형, 숫자는 절댓값."""
    if v is None:
        return f'<span style="color:{MUTED};">—</span>'
    col = UP if v > 0 else DOWN if v < 0 else MUTED
    tri = "▲" if v > 0 else "▼" if v < 0 else "–"
    return f'<span style="color:{col};font-weight:700;">{tri} {abs(v):.{digits}f}{unit}</span>'


def sec_headline(a):
    """오늘 한 줄 — 티커 타일 카드 (2026-10-11 사용자: 티커 활용, 카드 정보 디자인, ▲▼ 삼각형, 가격까지 등락색).

    카드 안은 span(인라인 블록)만 — 홈 카드의 linesOf가 이 div를 잎 요소로 보고 한 줄로 읽는다.
    """
    h = a["headline"]
    if h.get("close") is None:
        return f'<div style="{CARD}">휴장 — 시세는 다음 거래일에 채워집니다. 공시·기사·일정만 아래에 있습니다.</div>'
    r = h.get("ret_1d")
    pcol = UP if (r or 0) > 0 else DOWN if (r or 0) < 0 else "#111"
    # span 사이의 공백은 홈 카드가 textContent 로 읽을 때 단어를 띄우기 위한 것 (화면에서는 타일 사이 작은 틈)
    main = (f'<span style="{TILE}padding:8px 12px;"><span style="{TICKER}">NVDA</span> '
            f'<span style="color:{pcol};font-weight:700;">${h["close"]:,.2f}</span> {_arrow(r)}</span> ')
    tiles = ""
    for key, tk in (("ret_vs_spy", "SPY"), ("ret_vs_smh", "SMH"), ("ret_vs_amd", "AMD"), ("ret_vs_avgo", "AVGO")):
        tiles += f'<span style="{TILE}"><span style="{TICKER}">{tk} 대비</span> {_arrow(h.get(key), 2, "%p")}</span> '
    vr = h.get("vol_ratio_20d")
    vcol = WARN if (vr or 0) >= config.VOL_RATIO_EVENT else "#111"
    tiles += (f'<span style="{TILE}"><span style="{TICKER}">거래량 · 20일 평균 대비</span> '
              f'<span style="color:{vcol};font-weight:700;">{_esc(rr.fmt(vr, "x"))}</span></span> ')
    extra = ""
    if a.get("macro_today"):
        extra = f'<span style="{TILE}"><span style="{TICKER}">거시 일정</span> {_esc(", ".join(a["macro_today"]))}</span>'
    out = f'<div style="{CARD}padding-bottom:6px;">{main}{tiles}{extra}</div>'
    if not a.get("is_latest_bar_today"):
        out += _muted("기준 거래일이 최신이 아닐 수 있습니다 — 일봉 수집 상태를 확인하세요.")
    return out


def sec_chart(output_dir=None):
    """① 아래 가격 그래프 (chart_price.py가 만든 chart.json). 없으면 빈 문자열.

    설명 글자는 그림 안에 영문으로 있고, 여기엔 5·20·30일 변화율 한 줄만 둔다 — 홈 카드가 ① 구획의 줄을 그대로 읽어
    "오늘 한 줄" 아래에 붙이므로 누적 방향이 홈에서도 보인다. <img>는 글자가 없어 카드에 잡히지 않는다.
    """
    path = os.path.join(output_dir or config.OUTPUT_DIR, "chart.json")
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        c = json.load(f)
    ch = c.get("changes") or {}
    parts = [f"{n}일 {_signed(ch[n], 1)}" for n in ("5", "20", "30") if ch.get(n) is not None]   # _signed는 색 span을 포함한 HTML
    line = " · ".join(parts) + " (종가 기준 변화)" if parts else ""
    return (f'<img src="{_esc(c["url"])}" alt="NVDA {c.get("window", 30)}거래일 봉차트" '
            f'style="width:100%;max-width:1024px;display:block;margin:12px 0 6px;border:1px solid #eee;border-radius:8px;"/>'
            + (f'<div style="color:#333;">{line}</div>' if line else "")
            # 범례 줄은 border-top 을 달아 홈 카드가 건너뛰게 한다 (카드는 border-top 요소를 출처·면책으로 보고 거른다)
            + '<div style="margin-top:4px;padding-top:4px;border-top:1px solid #f3f3f3;font-size:{TINY};color:#999;">'
              '30거래일 봉차트 · 5·20·60일선 · 볼린저(20, 2σ) · 세로 점선은 5·20거래일 전 · 상승 빨강, 하락 파랑</div>')


LINK_ICON = ('<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" style="vertical-align:-2px;" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
             '<path d="M9 3h4v4"/><path d="M13 3 7 9"/><path d="M11 9v4H3V5h4"/></svg>')


def _link_icon(url, label):
    """출처 링크는 아이콘만 (2026-10-11 사용자: 출처 텍스트 링크, 특히 영문 제목은 필요 없다). 제목은 툴팁(title)으로만."""
    if not url:
        return ""
    return (f' <a href="{_esc(url)}" title="{_esc(label)}" aria-label="{_esc(label)}" target="_blank" rel="noopener" '
            f'style="color:#1a73e8;text-decoration:none;white-space:nowrap;">{LINK_ICON}</a>')


def _event_html(e):
    tag = _tag(e["area"], e["direction"])
    src = rr.SOURCE_KO.get(e.get("source") or "", e.get("source") or "")
    if e["kind"] in rr.DOC_KINDS:
        head = _esc(e["fact"])
        link = _link_icon(e.get("url"), f"{src}: {e['title'][:90]}")   # 원문 제목은 툴팁에만
        fact = ""
    else:
        head = _esc(e["title"])
        link = _link_icon(e.get("url"), f"{src} 원문")
        fact = f" — {_esc(e['fact'])}" if e.get("fact") and e["fact"] != e["title"] else ""
    when = f' <span style="color:{MUTED};font-size:{SMALL};white-space:nowrap;">({_esc(e["published_at"][:10])})</span>' if e.get("published_at") else ""   # 날짜가 두 줄로 쪼개지지 않게
    inner = f"{tag} · {head}{fact}{link}{when}"
    if e.get("emphasis"):   # 법무·규제 등 우선 영역: 굵게·크게 대신 연한 배경 카드 (가이드라인 2절)
        return f'<div style="{CARD_EMPH}margin:0 0 8px;">{inner}</div>'
    return f'<li style="{LI}">{inner}</li>'


def sec_events(a):
    if not a["events"]:
        return _muted("오늘은 임계값을 넘은 이벤트가 없습니다 — 공시·기사·가격·옵션·추정치 어느 쪽도 기준에 걸리지 않았다는 뜻입니다.")
    cards = [e for e in a["events"] if e.get("emphasis")]
    plain = [e for e in a["events"] if not e.get("emphasis")]
    out = "".join(_event_html(e) for e in cards) + (_ul(_event_html(e) for e in plain) if plain else "")
    if a["events_overflow"]:
        out += (f'<details style="margin:6px 0;"><summary style="cursor:pointer;color:{MUTED};">그 외 {len(a["events_overflow"])}건</summary>'
                + _ul(_event_html(dict(e, emphasis=False)) for e in a["events_overflow"]) + "</details>")
    if a.get("analyst_target_only"):
        out += _muted(f"목표가만 바뀐 애널리스트 {len(a['analyst_target_only'])}건 (등급 변경 아님): "
                      + " · ".join(t["title"] for t in a["analyst_target_only"][:6]))
    return out


def sec_upcoming(a):
    d0 = datetime.date.fromisoformat(a["day"])
    rows = []
    for c in a["upcoming"]:
        dn = (datetime.date.fromisoformat(c["day"]) - d0).days
        conf = "" if c.get("confirmed", 1) else " (추정)"
        extra = ""
        if c["kind"] == "EARNINGS":
            im = next((x["value"] for x in a["status"]["options"] if x["key"] == "implied_move_next_earnings"), None)
            extra = f" · implied move ±{im:.1f}%" if im else ""
        kind = rr.KIND_KO.get(c["kind"], c["kind"])
        label = _esc(c["label"] + conf + extra)
        if c["kind"] == "COURT":
            label = f'<span style="color:{WARN};">{label}</span>'
        rows.append([f"D{dn:+d}" if dn else "D0", _esc(c["day"]), _esc(kind), label])
    if not rows:
        return _muted("잡힌 일정이 없습니다.")
    return _table(["D-n", "날짜", "종류", "내용"], rows)


def sec_status(a):
    st = a["status"]
    out = []
    for group in ("price", "technical", "options", "estimates", "analysts", "flows", "valuation", "news"):
        cells = st.get(group) or []
        if not cells:
            continue
        rows = []
        for c in cells:
            v = rr.fmt(c["value"], c["fmt"])
            if c["value"] is None or c["value"] == "":
                hint = config.MISSING_HINTS.get(c["key"], config.MISSING_DEFAULT_HINT)
                if c["key"] == "iv_rank_60d":
                    hint += f" (현재 {st.get('iv_rank_n', 0)}/{config.IV_RANK_WINDOW}일)"
                rows.append([_esc(rr.LABEL_KO.get(c["key"], c["key"])), f'<span style="color:{MUTED};">{_esc(hint)}</span>'])
                continue
            rows.append([_esc(rr.LABEL_KO.get(c["key"], c["key"])), f"<b>{_esc(v)}</b>" if c["flag"] else _esc(v)])
        out.append(f'<div style="margin-top:10px;font-weight:bold;">{_esc(rr.GROUP_KO[group])}</div>' + _table(["지표", "값"], rows))
    return "".join(out)


def sec_cases(a):
    if not a["cases"]:
        return _muted("추적 사안 없음.")
    rows = []
    for c in a["cases"]:
        nxt = f"{c['next_day']} {c['next_label']}" if c.get("next_day") else "잡힌 일정 없음"
        last = f" · 최근 {c['last_activity_at'][:10]} {c['last_activity_summary']}" if c.get("last_activity_summary") else ""
        rows.append([_esc(c.get("short_name") or c["title"]) + _link_icon(c.get("url"), "도켓 보기"),
                     _esc(c.get("status") or "—"), _esc(nxt + last)])
    return _table(["사건", "상태", "다음 일정"], rows)


def sec_checklist(a):
    rows = []
    for r in a["checklist"]:
        if r.get("value") is None:
            v = f'<span style="color:{MUTED};">{_esc(r.get("note") or "이번 실행에서 받지 못함 — 다음 실행에서 재시도")}</span>'
        elif r["unit"] == "USD":
            v = f"${r['value'] / 1e9:,.2f}B" if abs(r["value"]) >= 1e9 else f"${r['value'] / 1e6:,.1f}M"
        elif r["unit"] in ("%", "% of shares"):
            v = f"{r['value']:.1f}%"
        elif r["unit"] == "배":
            v = f"{r['value']:.1f}배"
        else:
            v = f"{r['value']:,}"
        if r.get("arrow"):
            color = UP if r["arrow"] == "↑" else (DOWN if r["arrow"] == "↓" else MUTED)
            v = f'{v} <span style="color:{color};font-weight:bold;">{r["arrow"]}</span>'
        rows.append([_esc(r["label"]), v, _esc(r.get("asof") or "—"), _esc(r.get("detail") or r.get("source") or "—")])
    return _table(["지표", "값", "기준일", "비고"], rows)


def sec_narrative(a, n):
    if not n or not n.get("today"):
        return _muted("오늘은 이벤트가 없어 해석을 생략합니다." if not a["events"] else "서술을 만들지 못했습니다 — 수치 섹션만 참고하세요.")
    return _ul(f"<li style='{LI}'>{_esc(s)}</li>" for s in n["today"])


def sec_footer(a):
    ds = a["data_status"]
    return (f'<div style="margin-top:32px;padding-top:12px;border-top:1px solid #eee;font-size:{TINY};color:{MUTED};line-height:1.6;">'
            f"데이터: yfinance(일봉·옵션·추정치·애널리스트·기관·공매도) · SEC EDGAR(Form 4·8-K·10-Q·XBRL) · FRED(거시 일정) · "
            f"NVIDIA 뉴스룸·블로그 · CNBC · Google News · Federal Register · CourtListener · trump-trend. "
            f"분류 Gemini, 판정·계산 파이썬. 생성 {_esc(a['generated_at'])} (UTC) · 기준 거래일 {_esc(a['day'])} · 일봉 마지막 {_esc(ds['bars_last_day'] or '—')}.<br>"
            f"이 글은 보유 종목의 <b>사실 추적</b>입니다. 매수·매도 판단을 담지 않으며, 사건과 가격 변화 사이의 인과를 단정하지 않습니다. "
            f"옵션 지표는 장 마감 후 1회 스냅샷이고 GEX는 조잡한 근사입니다. 트럼프 과거 반응 통계는 다중 검정 보정(q)을 거친 값만 인용합니다. 투자 권고가 아닙니다.</div>")


# ── 조립 ─────────────────────────────────────────────────────────────────

def build_body(a, n):
    return "\n".join([
        '<div style="font-family:-apple-system,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;font-size:18px;line-height:1.7;color:#333;">',
        _notice(a),
        _muted(f"기준 거래일(뉴욕) {a['day']}"),
        _section("오늘 한 줄", sec_headline(a) + sec_chart()),
        _section("오늘 바뀐 것", sec_events(a) + _note(f"오늘 {a['events_total']}건 · 본문 {len(a['events'])} · 접힘 {len(a['events_overflow'])}")),
        _section("예정", sec_upcoming(a) + _note(f"{config.CALENDAR_LOOKAHEAD_DAYS}일 이내 일정 · 법원 일정은 {config.COURT_LOOKAHEAD_DAYS}일")),
        _section("상태판", sec_status(a)),
        _section("진행 중 사안", sec_cases(a)),
        _section("보유 논리 점검표", sec_checklist(a)),
        _section("오늘의 해석", sec_narrative(a, n)),
        sec_footer(a),
        "</div>",
    ])


def render(analysis_path=None, narrative_path=None, output_dir=None):
    output_dir = output_dir or config.OUTPUT_DIR
    analysis_path = analysis_path or os.path.join(output_dir, "nvda_analysis.json")
    narrative_path = narrative_path or os.path.join(output_dir, "narrative.json")
    with open(analysis_path, "r", encoding="utf-8") as f:
        a = json.load(f)
    n = None
    if os.path.exists(narrative_path):
        with open(narrative_path, "r", encoding="utf-8") as f:
            n = json.load(f)
    title = report_title.post_title(a.get("run_date") or report_title.today_kst())
    body = build_body(a, n)
    body_path = os.path.join(output_dir, "nvda_report_body.html")
    preview_path = os.path.join(output_dir, "nvda_report.html")
    with open(body_path, "w", encoding="utf-8") as f:
        f.write(body)
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(PREVIEW.replace("__TITLE__", _esc(title)).replace("__BODY__", body))
    with open(os.path.join(output_dir, "title.txt"), "w", encoding="utf-8") as f:
        f.write(title)
    print(f"[html] {len(body):,}자 → {body_path} · 미리보기 {preview_path}")
    return body_path, preview_path, title


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    render()
