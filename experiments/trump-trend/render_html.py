"""trump_analysis.json (+ narrative.json) → Blogger 본문 HTML (기획서 10절, 별도 글).

시각 규칙은 디자인-가이드라인.md 와 experiments/design_kit.py (2026-10-11): 18px 본문, 21px 구획 제목, C 카드, ⓘ 안내 글 14px, 라벨 알약, 표는 통계 행렬(과거 반응)에만.
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

# 시각 규칙은 디자인-가이드라인.md — 공통 조각 experiments/design_kit.py (2026-10-11 사용자: 데일리·트럼프도 새 디자인 규칙으로)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import design_kit as dk  # noqa: E402

UP, DOWN, MUTED = dk.UP, dk.DOWN, dk.MUTED
DIR_KO = {"positive": "긍정", "negative": "부정", "neutral": "중립"}
SESSION_KO = {"regular": "정규장", "pre": "장전", "after": "장후", "closed": "휴장"}

PREVIEW = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__</title></head>
<body style="max-width:900px;margin:0 auto;padding:16px;background:#fff;"><h1 style="font-size:26px;">__TITLE__</h1>__BODY__</body></html>"""

_esc = dk.esc


def _pct(v, digits=2, unit="%"):
    return dk.arrow(v, digits, unit)


def _dir_pill(d):
    return dk.pill(DIR_KO.get(d, d), d if d in ("positive", "negative") else "neutral")


# ── 구획 ────────────────────────────────────────────────────────────────

def sec_lead(a, n):
    """글 머리(제목 없음, data-lead): 24시간 집계 C 카드 + 가장 강한 발언 한 줄. 홈 카드는 이 묶음을 '(머리)'로 읽는다."""
    v = a["post_volume"]["last_24h"]
    ev = a["recent_events"]
    top = ev[0] if ev else None
    rows = [("게시물 (지난 24시간)", f"{v['total']}건"), ("정책 관련", f"{v['policy']}건"), ("시장 관련 이벤트", f"{len(ev)}개")]
    if top:
        rows.append(("가장 강한 발언", f"{_esc(top['topic'])}{' / ' + _esc(top['subtopic']) if top['subtopic'] else ''} · 강도 {top['intensity']}"))
    out = dk.cards(dk.multi(rows))
    if v["pending"]:
        out += dk.muted(f"최근 게시물 {v['pending']}건은 아직 분류되지 않아 오늘 항목이 불완전할 수 있습니다.")
    return out


def sec_recent(a):
    """발언 — C 카드: 주제/하위주제 + 방향·세션 라벨, 보조 줄에 시각·대상·연타, 값은 강도."""
    rows = []
    for e in a["recent_events"]:
        name = f"<b>{_esc(e['topic'])}</b>" + (f" / {_esc(e['subtopic'])}" if e["subtopic"] else "") + " " + _dir_pill(e["direction"]) + " " + dk.pill(SESSION_KO.get(e["session"], e["session"]))
        sub = [report_title.kst_hm(e["first_post_at"]), f"대상 {e['target']}" if e.get("target") else ""]
        if e["post_count"] > 1:
            sub.append(f"연타 {e['post_count']}")
        if e["confounded_daily"]:
            sub.append("거시 발표 겹침")
        rows.append((name, f"강도 {e['intensity']}", _esc(" · ".join(x for x in sub if x))))
    if not rows:
        return dk.muted("최근 24시간에 시장 관련 발언 이벤트가 없습니다.")
    return dk.ccard(rows, left="65%")


def sec_trends(a):
    """급상승 주제 (7일) — C 카드: 주제(+N: 90일 내 처음), 값 점수, 보조 줄 7일 이벤트·평균 강도."""
    rows = []
    for i, t in enumerate(a["trend_scores"][:8], 1):
        name = f"{i}. {_esc(t['key'])}" + (dk.NEW_PILL if t["is_new_90d"] else "")
        rows.append((name, f"{t['score']:.0f}점", _esc(f"7일 이벤트 {t['events_7d']} (직전 {t['events_prev_7d']}) · 평균 강도 {t['avg_intensity']:.1f}")))
    if not rows:
        return dk.muted("최근 7일 이벤트가 없어 점수를 내지 않습니다.")
    out = dk.ccard(rows, left="65%")
    ne = a["new_entrants"]
    if ne["target"] or ne["symbol"]:
        out += dk.note("7일 내 처음 등장 (직전 90일 없음): " + ", ".join(ne["target"] + ne["symbol"]))
    return out


def sec_windows(a):
    """30일 흐름 — C 카드: 주제, 값 이벤트 수, 보조 줄 평균 강도·부정 비율·직전 30일 대비."""
    blk = a["windows"].get("30D") or {}
    rows = []
    for r in [x for x in blk.get("dims", {}).get("topic", []) if x["events"] > 0][:8]:
        delta = "직전 30일 대비 —" if r["delta_events"] is None else f"직전 30일 대비 {r['delta_events']:+.0f}%"
        rows.append((_esc(r["key"]), f"{r['events']}건",
                     _esc(f"평균 강도 {r['avg_intensity']:.1f} · 부정 비율 {int((r['neg_ratio'] or 0) * 100)}% · {delta}" if r["avg_intensity"] else delta)))
    if not rows:
        return dk.muted("30일 데이터가 아직 없습니다.")
    note = "최근 30일 기준" + ("" if blk.get("compare_to_previous") else " · 직전 30일 데이터가 없어 변화량은 표시하지 않습니다")
    return dk.ccard(rows, left="55%") + dk.note(note)


def _x(v):
    if v is None:
        return dk.dash()
    return f'<span style="font-weight:{"700" if v >= 1.5 else "400"};">{v:.2f}×</span>'


def _p(st):
    """p (보정 전) + q (주제 안 다중 검정 BH 보정). 회색 = 보통 날과 구분 안 됨, 굵게 = 보정 뒤에도 유의."""
    pl = (st or {}).get("placebo")
    if not pl:
        return dk.dash()
    q = pl.get("q_bh")
    q_html = f'<span style="color:{MUTED};font-size:{dk.TINY};"> q{q:.2f}</span>' if q is not None else ""
    if pl["indistinguishable"]:
        return f'<span style="color:{MUTED};">{pl["p_two_sided"]:.2f}</span>{q_html}'
    if pl.get("robust"):
        return f'<b>{pl["p_two_sided"]:.2f}</b>{q_html}'
    return f'{pl["p_two_sided"]:.2f}{q_html}'


def sec_reactions(a):
    """과거 반응 — 자산 × 구간 통계 행렬이라 표를 쓴다 (가이드라인 7절 예외). 주제마다 소제목 + 표, 읽는 법은 ⓘ 안내 줄."""
    today_keys = []
    for e in a["recent_events"]:
        if e["topic"] not in today_keys:
            today_keys.append(e["topic"])
    keys = today_keys or sorted(a["reactions"], key=lambda k: -a["reactions"][k]["counts"]["clean"])[:3]
    noise_p = a.get("config", {}).get("placebo_noise_p", config.PLACEBO_NOISE_P)
    out, waiting = [], []
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
            out.append(dk.sub_label(f"{k} — 과거 관측일 {c['clean']}일 (이벤트 {c['total']} · 거시 발표 겹침 제외 {c['confounded']} · 장외 {ik.get('gap', 0)} / 정규장 {ik.get('intraday', 0)} · 검정 {c.get('tests', 0)}개)")
                       + dk.table(["자산", "N", "즉각", "당일", "익일", "+5일", "하락 비율", "변동폭", "거래량", "p · q"], rows))
        else:
            waiting.append(f"{k} ({c['clean']}/{config.MIN_CLEAN_N})")
    if waiting:
        out.append(dk.muted("표본 축적 중 (관측일 / 필요 20): " + ", ".join(waiting)))
    if not out:
        return dk.muted("오늘 이벤트 주제에 해당하는 과거 반응 데이터가 아직 없습니다.")
    out.append(dk.note(
        f"수치는 {config.BENCHMARK} 대비 초과 반응(%)이며, {config.BENCHMARK}만 원수익률입니다. "
        f"즉각 = 장외 발언은 다음 개장 갭, 정규장 발언은 시가→종가. 변동폭·거래량은 직전 {config.REL_LOOKBACK_DAYS}거래일 평소 대비 배수(1.00× = 보통). "
        f"p = 발언 없는 날에서 같은 수만큼 뽑았을 때 이 정도 평균이 우연히 나올 비율 — {noise_p:.2f} 이상(회색)이면 보통 날과 구분되지 않습니다. "
        f"q = 한 주제에서 자산 × 구간 수십 개를 한꺼번에 검정한 데 대한 보정값(Benjamini–Hochberg) — {noise_p:.2f} 미만(굵게)인 값만 보정 뒤에 남는 것으로 봅니다. "
        f"+5일 구간은 창이 겹쳐 독립 표본이 아닙니다. 발언 이후 관찰된 값이고 인과를 의미하지 않습니다."))
    return "".join(out)


def sec_why(a):
    """관찰 종목 — C 카드: 주제, 값 ETF, 보조 줄 경로·관찰 종목."""
    rows, seen = [], set()
    for e in a["recent_events"]:
        if not e["rule_id"] or e["rule_id"] in seen:
            continue
        seen.add(e["rule_id"])
        name = f"<b>{_esc(e['topic'])}</b>" + (f" / {_esc(e['subtopic'])}" if e["subtopic"] else "")
        rows.append((name, _esc(e["etf"] or "—"), _esc(f"경로 {e['path_text'] or '—'} · 관찰 {', '.join(e['affected'][:10]) or '—'}")))
    if not rows:
        return dk.muted("오늘 이벤트에 연결된 매핑 규칙이 없습니다.")
    return dk.ccard(rows, left="65%") + dk.note("정적 매핑 규칙(섹터 → ETF → 상위 10종목 + 본문 언급 기업)입니다. AI 판단이 아닙니다.")


def sec_narrative(n, key):
    if not n or not n.get(key):
        return dk.muted("서술 없음.")
    return dk.bullets(n[key])


def sec_footer(a):
    s = a["data_status"]
    return dk.footer(
        f"데이터: Truth Social 게시물 공개 아카이브(CNN) · 가격 Yahoo Finance · 거시 일정 FRED. 분류 Gemini, 집계·통계 파이썬. "
        f"이벤트 누적 {s['events_total']:,}개 · 가격 기준일 {_esc(dk.day(s['bars_last_day']) or '—')}.",
        "이 글의 시장 반응 수치는 과거 발언 이후 관찰된 값이며 인과 관계나 향후 방향을 의미하지 않습니다. 투자 권고가 아닙니다.")


# ── 조립 (구획 제목은 짧은 명사 — 가이드라인 2절. 홈 카드 CARDS: speech = (머리)·달라진 것, watch = 내일 볼 것) ──

def build_body(a, n):
    return "\n".join([
        dk.WRAP_OPEN,
        sec_lead(a, n),
        dk.section("발언", sec_recent(a)),
        dk.section("급상승 주제", sec_trends(a), summary="최근 7일"),
        dk.section("달라진 것", sec_narrative(n, "what_changed")),
        dk.section("30일 흐름", sec_windows(a)),
        dk.section("과거 반응", sec_reactions(a), summary="오늘 주제의 과거 발언 뒤 시장 반응"),
        dk.section("관찰 종목", sec_why(a)),
        dk.section("내일 볼 것", sec_narrative(n, "watch_tomorrow")
                   + dk.note("관찰 대상은 위 과거 반응에서 고른 값입니다. 주제당 수십 개 조합을 검정했으므로 보정 q가 함께 작은 값만 근거로 삼으며, "
                             "+3일·+5일은 창이 겹친 관측입니다. 인과나 방향 예측이 아닙니다.")),
        sec_footer(a),
        dk.WRAP_CLOSE,
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
