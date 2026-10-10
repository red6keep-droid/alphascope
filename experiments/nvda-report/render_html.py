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
import sys

import config
import render_report as rr
import report_title

H2 = "color:#111;border-bottom:2px solid #eee;padding-bottom:8px;margin-top:28px;"
UP, DOWN, MUTED, WARN = "#d93025", "#1a73e8", "#999", "#e8710a"
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


def _table(headers, rows):
    th = "".join(f'<th style="border:1px solid #ddd;padding:6px 8px;background:#f5f5f5;text-align:left;white-space:nowrap;">{_esc(h)}</th>' for h in headers)
    body = "".join("<tr>" + "".join(f'<td style="border:1px solid #ddd;padding:6px 8px;">{c}</td>' for c in r) + "</tr>" for r in rows)
    return (f'<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;margin:8px 0;font-size:17px;">'
            f"<tr>{th}</tr>{body}</table></div>")


def _h2(t):
    return f'<h2 style="{H2}">{_esc(t)}</h2>'


def _muted(t):
    return f'<div style="color:{MUTED};font-size:16px;margin:6px 0;">{_esc(t)}</div>'


def _tag(area, direction):
    return (f'<span style="background:#f1f3f4;border-radius:4px;padding:1px 6px;font-size:15px;">{_esc(rr.AREA_KO.get(area, area))}</span> '
            f'<span style="color:{DIR_COLOR.get(direction, MUTED)};font-weight:bold;font-size:15px;">{_esc(rr.DIR_KO.get(direction, direction))}</span>')


# ── 섹션 ────────────────────────────────────────────────────────────────

def sec_headline(a):
    h = a["headline"]
    if h.get("close") is None:
        return f'<div style="font-size:20px;font-weight:bold;">휴장 — 시세 섹션 없음</div>'
    line = (f'<b>NVDA ${h["close"]:,.2f}</b> ({_signed(h["ret_1d"])}) · SPY 대비 {_signed(h.get("ret_vs_spy"), 2, "%p")} · '
            f'SMH 대비 {_signed(h.get("ret_vs_smh"), 2, "%p")} · AMD 대비 {_signed(h.get("ret_vs_amd"), 2, "%p")} · '
            f'거래량 20일 평균의 {_esc(rr.fmt(h.get("vol_ratio_20d"), "x"))}')
    if a.get("macro_today"):
        line += f' · 거시 일정: {_esc(", ".join(a["macro_today"]))}'
    out = f'<div style="font-size:20px;color:#111;">{line}</div>'
    if not a.get("is_latest_bar_today"):
        out += _muted("기준 거래일이 최신이 아닐 수 있습니다 — 일봉 수집 상태를 확인하세요.")
    return out


def _event_html(e):
    tag = _tag(e["area"], e["direction"])
    src = rr.SOURCE_KO.get(e.get("source") or "", e.get("source") or "")
    if e["kind"] in rr.DOC_KINDS:
        head = f"<b>{_esc(e['fact'])}</b>" if e["emphasis"] else _esc(e["fact"])
        link = (f' <a href="{_esc(e["url"])}" style="color:#1a73e8;">{_esc(src)}: {_esc(e["title"][:70])}</a>' if e.get("url")
                else f' <span style="color:{MUTED};">({_esc(src)}: {_esc(e["title"][:70])})</span>')
        fact = ""
    else:
        head = f"<b>{_esc(e['title'])}</b>" if e["emphasis"] else _esc(e["title"])
        link = f' <a href="{_esc(e["url"])}" style="color:#1a73e8;">출처</a>' if e.get("url") else ""
        fact = f" — {_esc(e['fact'])}" if e.get("fact") and e["fact"] != e["title"] else ""
    when = f' <span style="color:{MUTED};font-size:15px;">({_esc(e["published_at"][:10])})</span>' if e.get("published_at") else ""
    return f'<li style="margin:6px 0;">{tag} · {head}{fact}{link}{when}</li>'


def sec_events(a):
    if not a["events"]:
        return _muted("특이 이벤트 없음.")
    out = "<ul style='margin:8px 0 8px 20px;padding:0;'>" + "".join(_event_html(e) for e in a["events"]) + "</ul>"
    if a["events_overflow"]:
        out += (f'<details style="margin:6px 0;"><summary style="cursor:pointer;color:{MUTED};">그 외 {len(a["events_overflow"])}건</summary>'
                "<ul style='margin:8px 0 8px 20px;padding:0;'>" + "".join(_event_html(e) for e in a["events_overflow"]) + "</ul></details>")
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
            label = f'<b style="color:{WARN};">{label}</b>'
        rows.append([f"D{dn:+d}" if dn else "D0", _esc(c["day"]), _esc(kind), label])
    if not rows:
        return _muted(f"{config.CALENDAR_LOOKAHEAD_DAYS}일 내 일정 없음 (법원 일정은 {config.COURT_LOOKAHEAD_DAYS}일).")
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
            if c["key"] == "iv_rank_60d" and c["value"] is None:
                v = f"집계 중 ({st.get('iv_rank_n', 0)}/{config.IV_RANK_WINDOW}일)"
            rows.append([_esc(rr.LABEL_KO.get(c["key"], c["key"])), f"<b>{_esc(v)}</b>" if c["flag"] else _esc(v)])
        out.append(f'<div style="margin-top:10px;font-weight:bold;">{_esc(rr.GROUP_KO[group])}</div>' + _table(["지표", "값"], rows))
    ds = a["data_status"]
    if ds.get("missing_fields"):
        out.append(_muted("미수집: " + ", ".join(ds["missing_fields"])))
    return "".join(out)


def sec_cases(a):
    if not a["cases"]:
        return _muted("추적 사안 없음.")
    rows = []
    for c in a["cases"]:
        nxt = f"{c['next_day']} {c['next_label']}" if c.get("next_day") else "잡힌 일정 없음"
        last = f" · 최근 {c['last_activity_at'][:10]} {c['last_activity_summary']}" if c.get("last_activity_summary") else ""
        rows.append([f'<a href="{_esc(c["url"])}" style="color:#1a73e8;">{_esc(c.get("short_name") or c["title"])}</a>',
                     _esc(c.get("status") or "—"), _esc(nxt + last)])
    return _table(["사건", "상태", "다음 일정"], rows)


def sec_checklist(a):
    rows = []
    for r in a["checklist"]:
        if r.get("value") is None:
            v = _esc(r.get("note") or "미수집")
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


def sec_narrative(n):
    if not n or not n.get("today"):
        return _muted("오늘의 해석 없음 (이벤트 0건이거나 서술 생략).")
    return "<ul style='margin:8px 0 8px 20px;'>" + "".join(f"<li style='margin:4px 0;'>{_esc(s)}</li>" for s in n["today"]) + "</ul>"


def sec_footer(a):
    ds = a["data_status"]
    return (f'<div style="margin-top:32px;padding-top:12px;border-top:1px solid #eee;font-size:15px;color:{MUTED};line-height:1.6;">'
            f"데이터: yfinance(일봉·옵션·추정치·애널리스트·기관·공매도) · SEC EDGAR(Form 4·8-K·10-Q·XBRL) · FRED(거시 일정) · "
            f"NVIDIA 뉴스룸·블로그 · CNBC · Google News · Federal Register · CourtListener · trump-trend. "
            f"분류 Gemini, 판정·계산 파이썬. 생성 {_esc(a['generated_at'])} (UTC) · 기준 거래일 {_esc(a['day'])} · 일봉 마지막 {_esc(ds['bars_last_day'] or '—')}.<br>"
            f"이 글은 보유 종목의 <b>사실 추적</b>입니다. 매수·매도 판단을 담지 않으며, 사건과 가격 변화 사이의 인과를 단정하지 않습니다. "
            f"옵션 지표는 장 마감 후 1회 스냅샷이고 GEX는 조잡한 근사입니다. 트럼프 과거 반응 통계는 다중 검정 보정(q)을 거친 값만 인용합니다. 투자 권고가 아닙니다.</div>")


# ── 조립 ─────────────────────────────────────────────────────────────────

def build_body(a, n):
    return "\n".join([
        '<div style="font-family:-apple-system,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;font-size:18px;line-height:1.7;color:#333;">',
        _muted(f"기준 거래일(뉴욕) {a['day']}" + ("" if a.get("published_mode") else " · 그림자 모드")),
        _h2("① 오늘 한 줄"), sec_headline(a),
        _h2(f"② 오늘 바뀐 것 ({a['events_total']}건)"), sec_events(a),
        _h2(f"③ 다가오는 것 ({config.CALENDAR_LOOKAHEAD_DAYS}일 이내 · 법원 일정 {config.COURT_LOOKAHEAD_DAYS}일)"), sec_upcoming(a),
        _h2("④ 상태판"), sec_status(a),
        _h2("⑤ 진행 중 사안"), sec_cases(a),
        _h2("⑥ 보유 논리 점검표"), sec_checklist(a),
        _h2("⑦ 오늘의 해석"), sec_narrative(n),
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
