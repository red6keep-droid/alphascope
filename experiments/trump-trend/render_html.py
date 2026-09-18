"""trump_analysis.json (+ narrative.json) → Blogger 본문 HTML (기획서 10절, 별도 글).

기존 데일리 리포트(experiments/daily-report/render_html.py)와 같은 시각 규칙을 쓴다 —
18px 본문, 회색 밑줄 H2, 상승 빨강·하락 파랑, 좁은 화면에서 표만 가로 스크롤.
숫자는 여기서 파이썬이 그리고, 문장은 narrative.json에서만 가져온다.

출력:
    output/trump_report_body.html   Blogger에 올리는 본문
    output/trump_report.html        브라우저 미리보기 (본문을 감싼 것)
"""

import html as html_mod
import json
import os
import sys

import config
import report_title

H2 = "color:#111;border-bottom:2px solid #eee;padding-bottom:8px;margin-top:28px;"
UP, DOWN, MUTED = "#d93025", "#1a73e8", "#999"
DIR_KO = {"positive": "긍정", "negative": "부정", "neutral": "중립"}
SESSION_KO = {"regular": "정규장", "pre": "장전", "after": "장후", "closed": "휴장"}
DIR_COLOR = {"positive": UP, "negative": DOWN, "neutral": MUTED}

PREVIEW = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__</title></head>
<body style="max-width:900px;margin:0 auto;padding:16px;background:#fff;"><h1 style="font-size:26px;">__TITLE__</h1>__BODY__</body></html>"""


def _esc(t):
    return html_mod.escape(str(t), quote=False)


def _pct(v, digits=2):
    if v is None:
        return f'<span style="color:{MUTED};">—</span>'
    color = UP if v >= 0 else DOWN
    return f'<span style="color:{color};font-weight:bold;">{v:+.{digits}f}%</span>'


def _table(headers, rows, widths=None):
    th = "".join(f'<th style="border:1px solid #ddd;padding:6px 8px;background:#f5f5f5;text-align:left;white-space:nowrap;">{_esc(h)}</th>' for h in headers)
    body = "".join("<tr>" + "".join(f'<td style="border:1px solid #ddd;padding:6px 8px;">{c}</td>' for c in r) + "</tr>" for r in rows)
    return (f'<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;margin:8px 0;font-size:17px;">'
            f"<tr>{th}</tr>{body}</table></div>")


def _h2(t):
    return f'<h2 style="{H2}">{_esc(t)}</h2>'


def _muted(t):
    return f'<div style="color:{MUTED};font-size:16px;margin:6px 0;">{_esc(t)}</div>'


def _bullets(items):
    return "<ul style='margin:8px 0 8px 20px;'>" + "".join(f"<li style='margin:4px 0;'>{_esc(s)}</li>" for s in items) + "</ul>"


def _direction(d):
    return f'<span style="color:{DIR_COLOR.get(d, MUTED)};font-weight:bold;">{DIR_KO.get(d, d)}</span>'


# ── 섹션 ────────────────────────────────────────────────────────────────

def sec_lead(a, n):
    v = a["post_volume"]["last_24h"]
    ev = a["recent_events"]
    top = ev[0] if ev else None
    line = (f"지난 24시간 게시물 <b>{v['total']}</b>건 중 정책 관련 <b>{v['policy']}</b>건, 이벤트 <b>{len(ev)}</b>개."
            + (f" 가장 강한 발언은 <b>{_esc(top['topic'])}{' / ' + _esc(top['subtopic']) if top['subtopic'] else ''}</b> (강도 {top['intensity']})." if top else ""))
    out = f'<div style="font-size:20px;font-weight:bold;color:#111;">{line}</div>'
    if v["pending"]:
        out += _muted(f"⚠️ 최근 게시물 {v['pending']}건은 아직 분류되지 않아 오늘 항목이 불완전할 수 있습니다.")
    return out


def sec_recent(a):
    rows = []
    for e in a["recent_events"]:
        rows.append([
            _esc(report_title.kst_hm(e["first_post_at"])),
            f"<b>{_esc(e['topic'])}</b>" + (f" / {_esc(e['subtopic'])}" if e["subtopic"] else ""),
            _esc(e["target"]), _direction(e["direction"]), e["intensity"],
            e["post_count"] if e["post_count"] > 1 else "",
            _esc(SESSION_KO.get(e["session"], e["session"])),
            (f'<span style="color:{MUTED};">⚠️ 거시 발표 겹침</span>' if e["confounded_daily"] else ""),
        ])
    if not rows:
        return _muted("최근 24시간에 시장 관련 발언 이벤트가 없습니다.")
    return _table(["시각(KST)", "주제", "대상", "방향", "강도", "연타", "세션", ""], rows)


def sec_trends(a):
    rows = []
    for i, t in enumerate(a["trend_scores"][:8], 1):
        new = ' <span style="font-size:14px;color:#e8710a;">NEW</span>' if t["is_new_90d"] else ""
        rows.append([i, f"<b>{_esc(t['key'])}</b>{new}", f"<b>{t['score']:.0f}</b>",
                     f"{t['events_7d']} <span style='color:{MUTED};'>(직전 {t['events_prev_7d']})</span>",
                     f"{t['avg_intensity']:.1f}"])
    if not rows:
        return _muted("최근 7일 이벤트가 없어 점수를 내지 않습니다.")
    out = _table(["#", "주제", "점수", "7일 이벤트", "평균 강도"], rows)
    ne = a["new_entrants"]
    if ne["target"] or ne["symbol"]:
        out += _muted("7일 내 처음 등장 (직전 90일 없음): "
                      + ", ".join(ne["target"] + ne["symbol"]))
    return out


def sec_windows(a):
    blk = a["windows"].get("30D") or {}
    rows = []
    for r in [x for x in blk.get("dims", {}).get("topic", []) if x["events"] > 0][:8]:
        delta = f'<span style="color:{MUTED};">—</span>' if r["delta_events"] is None else _pct(r["delta_events"], 0).replace("%", "")
        rows.append([f"<b>{_esc(r['key'])}</b>", r["events"], f"{r['avg_intensity']:.1f}" if r["avg_intensity"] else "—",
                     f"{int((r['neg_ratio'] or 0) * 100)}%", delta])
    if not rows:
        return _muted("30일 데이터가 아직 없습니다.")
    note = "" if blk.get("compare_to_previous") else " · 직전 30일 데이터가 없어 변화량은 표시하지 않습니다"
    return _table(["주제", "이벤트", "평균 강도", "부정 비율", "Δ이벤트(직전 30일 대비)"], rows) + _muted("최근 30일 기준" + note)


def _x(v):
    if v is None:
        return f'<span style="color:{MUTED};">—</span>'
    weight = "bold" if v >= 1.5 else "normal"
    return f'<span style="font-weight:{weight};">{v:.2f}×</span>'


def _p(st):
    pl = (st or {}).get("placebo")
    if not pl:
        return f'<span style="color:{MUTED};">—</span>'
    if pl["indistinguishable"]:
        return f'<span style="color:{MUTED};">{pl["p_two_sided"]:.2f}</span>'
    return f'<b>{pl["p_two_sided"]:.2f}</b>'


def sec_reactions(a):
    today_keys = []
    for e in a["recent_events"]:
        for k in (e["topic"],):
            if k not in today_keys:
                today_keys.append(k)
    keys = today_keys or sorted(a["reactions"], key=lambda k: -a["reactions"][k]["counts"]["clean"])[:3]
    noise_p = a.get("config", {}).get("placebo_noise_p", config.PLACEBO_NOISE_P)
    out = []
    waiting = []
    for k in keys:
        blk = a["reactions"].get(k)
        if not blk:
            continue
        c = blk["counts"]
        rows = []
        for sym in config.ALL_SYMBOLS:
            hz = blk["symbols"].get(sym, {})
            st = hz.get("close")
            if not st or not st["publishable"]:
                continue
            g = lambda h: (hz.get(h) or {}).get("mean") if (hz.get(h) or {}).get("publishable") else None  # noqa: E731
            rows.append([f"<b>{sym}</b>", st["n"], _pct(g("immediate")), _pct(st["mean"]), _pct(g("next_close")),
                         _pct(g("d5")), f"{st['neg_pct']:.0f}%", _x(g("rel_range")), _x(g("rel_volume")), _p(st)])
        if rows:
            ik = c.get("immediate_kinds", {})
            out.append(f'<div style="margin-top:14px;font-weight:bold;">{_esc(k)} — 과거 clean 관측일 {c["clean"]}일'
                       f'<span style="color:{MUTED};font-weight:normal;"> (이벤트 {c["total"]} · 거시 발표 겹침 제외 {c["confounded"]}'
                       f' · 장외 {ik.get("gap", 0)} / 정규장 {ik.get("intraday", 0)})</span></div>'
                       + _table(["자산", "N", "즉각", "당일", "익일", "+5일", "하락 비율", "변동폭", "거래량", "p"], rows))
        else:
            waiting.append(f"{k} ({c['clean']}/{config.MIN_CLEAN_N})")
    if waiting:
        out.append(_muted("표본 축적 중 (clean 관측일 / 필요 20): " + ", ".join(waiting)))
    if not out:
        return _muted("오늘 이벤트 주제에 해당하는 과거 반응 데이터가 아직 없습니다.")
    out.append(_muted(
        f"수치는 {config.BENCHMARK} 대비 초과 반응(%)이며, {config.BENCHMARK}만 원수익률입니다. "
        f"즉각 = 장외 발언은 다음 개장 갭, 정규장 발언은 시가→종가. 변동폭·거래량은 직전 {config.REL_LOOKBACK_DAYS}거래일 평소 대비 배수(1.00× = 보통). "
        f"p = 같은 자산의 발언 없는 날에서 같은 수만큼 뽑았을 때 이 정도 평균이 우연히 나올 비율 — {noise_p:.2f} 이상(회색)이면 보통 날과 구분되지 않습니다. "
        f"발언 이후 관찰된 값이고 인과를 의미하지 않습니다."))
    return "".join(out)


def sec_why(a):
    rows, seen = [], set()
    for e in a["recent_events"]:
        if not e["rule_id"] or e["rule_id"] in seen:
            continue
        seen.add(e["rule_id"])
        rows.append([f"<b>{_esc(e['topic'])}</b>" + (f" / {_esc(e['subtopic'])}" if e["subtopic"] else ""),
                     _esc(e["path_text"] or "—"), _esc(e["etf"] or "—"), _esc(", ".join(e["affected"][:10]) or "—")])
    if not rows:
        return _muted("오늘 이벤트에 연결된 매핑 규칙이 없습니다.")
    return _table(["오늘 주제", "경로", "ETF", "관찰 종목"], rows) + _muted("정적 매핑 규칙(섹터 → ETF → 상위 10종목 + 본문 언급 기업)입니다. AI 판단이 아닙니다.")


def sec_narrative(n, key):
    if not n or not n.get(key):
        return _muted("서술 없음.")
    return _bullets(n[key])


def sec_footer(a):
    s = a["data_status"]
    return (f'<div style="margin-top:32px;padding-top:12px;border-top:1px solid #eee;font-size:15px;color:{MUTED};line-height:1.6;">'
            f"데이터: Truth Social 게시물 공개 아카이브(CNN) · 가격 Yahoo Finance · 거시 일정 FRED. "
            f"분류 Gemini, 집계·통계 파이썬. 이벤트 누적 {s['events_total']:,}개 · 가격 기준일 {_esc(s['bars_last_day'] or '—')}.<br>"
            f"이 글의 시장 반응 수치는 과거 발언 이후 <b>관찰된 값</b>이며 인과 관계나 향후 방향을 의미하지 않습니다. 투자 권고가 아닙니다.</div>")


# ── 조립 ─────────────────────────────────────────────────────────────────

def build_body(a, n):
    return "\n".join([
        '<div style="font-family:-apple-system,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;font-size:18px;line-height:1.7;color:#333;">',
        _h2("오늘 한 줄"), sec_lead(a, n),
        _h2("오늘의 발언"), sec_recent(a),
        _h2("급상승 주제 (7일)"), sec_trends(a),
        _h2("무엇이 달라졌나"), sec_narrative(n, "what_changed"),
        _h2("30일 흐름"), sec_windows(a),
        _h2("같은 주제의 과거 시장 반응"), sec_reactions(a),
        _h2("왜 이 종목인가"), sec_why(a),
        _h2("내일 볼 것"), sec_narrative(n, "watch_tomorrow"),
        sec_footer(a),
        "</div>",
    ])


def render(analysis_path=None, narrative_path=None, output_dir=None):
    output_dir = output_dir or config.OUTPUT_DIR
    analysis_path = analysis_path or os.path.join(output_dir, "trump_analysis.json")
    narrative_path = narrative_path or os.path.join(output_dir, "narrative.json")
    with open(analysis_path, "r", encoding="utf-8") as f:
        a = json.load(f)
    n = None
    if os.path.exists(narrative_path):
        with open(narrative_path, "r", encoding="utf-8") as f:
            n = json.load(f)

    title = report_title.post_title(report_title.today_kst())
    body = build_body(a, n)
    body_path = os.path.join(output_dir, "trump_report_body.html")
    preview_path = os.path.join(output_dir, "trump_report.html")
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
