"""trump_analysis.json (+ narrative.json) → output/trump_report.md (기획서 10절).

표는 여기서 파이썬이 그린다. Gemini 문장은 narrative.json이 있을 때만 끼워 넣는다.
그림자 모드 산출물이라 Markdown이다. 데일리 리포트에 편입할 때 HTML 렌더를 붙인다.
"""

import json
import os
import sys

import config

DIR_KO = {"positive": "긍정", "negative": "부정", "neutral": "중립"}
SESSION_KO = {"regular": "정규장", "pre": "장전", "after": "장후", "closed": "휴장"}


def _pct(v):
    return "—" if v is None else f"{v:+.2f}%"


def _row(cells):
    return "| " + " | ".join(str(c) for c in cells) + " |"


def _table(headers, rows):
    if not rows:
        return "_데이터 없음_\n"
    out = [_row(headers), _row(["---"] * len(headers))]
    out += [_row(r) for r in rows]
    return "\n".join(out) + "\n"


def section_status(a):
    s, v = a["data_status"], a["post_volume"]["last_24h"]
    lines = [
        f"- 생성 시각: {a['generated_at']} (UTC)",
        f"- 게시물 누적 {s['posts_total']:,} · 분류 완료 {s['posts_classified']:,} · "
        f"최근 {s['classify_since_days']}일 분류 대기 {s['posts_pending_recent']:,} (범위 밖 미분류 {s['posts_pending_all_time']:,}건은 의도적)",
        f"- 이벤트 {s['events_total']:,} (첫 이벤트 {s['events_first_at'] or '—'}) · 가격 마지막 거래일 {s['bars_last_day'] or '—'}",
        f"- 지난 24시간: 게시물 {v['total']} · 노이즈 {v['noise']} · 정책 글 {v['policy']} · 미분류 {v['pending']}",
    ]
    if v["pending"]:
        lines.append(f"- ⚠️ 최근 24시간 게시물 {v['pending']}건이 아직 분류되지 않았다. 오늘의 발언·이벤트가 불완전할 수 있다.")
    return "\n".join(lines) + "\n"


def section_recent(a):
    rows = []
    for e in a["recent_events"]:
        tag = " ⚠️" if e["confounded_daily"] else ""
        rows.append([
            e["first_post_at"][5:16].replace("T", " "),
            f"{e['topic']}" + (f" / {e['subtopic']}" if e["subtopic"] else ""),
            e["target"], DIR_KO.get(e["direction"], e["direction"]), e["intensity"],
            e["post_count"], SESSION_KO.get(e["session"], e["session"]), (e["effective_day"] or "—") + tag,
        ])
    return _table(["시각(UTC)", "주제", "대상", "방향", "강도", "연타", "세션", "반응 측정일"], rows)


def section_trends(a):
    rows = []
    for i, t in enumerate(a["trend_scores"], 1):
        new = " 🆕" if t["is_new_90d"] else ""
        c = t["components"]
        rows.append([i, t["key"] + new, t["score"], f"{t['events_7d']} ({t['events_prev_7d']})",
                     t["avg_intensity"], f"F{c['frequency']} I{c['intensity']} R{c['recency']} N{c['novelty']}"])
    return _table(["#", "주제", "점수", "7D 이벤트 (직전)", "평균 강도", "성분"], rows)


def section_windows(a):
    out = []
    for w, blk in a["windows"].items():
        rows = []
        for r in [x for x in blk["dims"]["topic_subtopic"] if x["events"] > 0][:8]:
            delta = "—" if r["delta_events"] is None else f"{r['delta_events']:+d}"
            rows.append([r["key"], r["events"], r["posts"], r["avg_intensity"] or "—",
                         f"{int((r['neg_ratio'] or 0) * 100)}%", delta])
        note = "" if blk["compare_to_previous"] else " (직전 구간 데이터 없음 — 수준값만)"
        out.append(f"**{w}**{note}\n\n" + _table(["주제", "이벤트", "게시물", "평균 강도", "부정 비율", "Δ이벤트"], rows))
    ne = a["new_entrants"]
    if ne["target"] or ne["symbol"]:
        out.append("**7일 내 신규 등장 (직전 90일 없음)** — 대상: "
                   + (", ".join(ne["target"]) or "없음") + " · 종목: " + (", ".join(ne["symbol"]) or "없음") + "\n")
    return "\n".join(out)


def _x(v):
    return "—" if v is None else f"{v:.2f}×"


def _p(st):
    pl = (st or {}).get("placebo")
    if not pl:
        return "—"
    return f"{pl['p_two_sided']:.2f}" + ("~" if pl["indistinguishable"] else "")


def section_reactions(a):
    """오늘 이벤트 주제의 과거 반응. publishable(N ≥ MIN_CLEAN_N)만 표로, 나머지는 축적 현황.

    구간은 전부 일봉: 즉각(장외 글은 갭, 정규장 글은 시가→종가) · 당일 · 익일 · +3D · +5D 초과 반응(%),
    변동폭·거래량 배수(1.0 = 직전 20거래일 보통). p는 플라시보 양측 p, '~'는 무작위 날과 구분되지 않음.
    """
    today_keys = []
    for e in a["recent_events"]:
        for k in (f"{e['topic']} / {e['subtopic']}" if e["subtopic"] else None, e["topic"]):
            if k and k not in today_keys:
                today_keys.append(k)
    keys = today_keys or sorted(a["reactions"], key=lambda k: -a["reactions"][k]["counts"]["clean"])[:5]
    noise_p = a.get("config", {}).get("placebo_noise_p", config.PLACEBO_NOISE_P)

    out = []
    for k in keys:
        blk = a["reactions"].get(k)
        if not blk:
            continue
        c = blk["counts"]
        ik = c.get("immediate_kinds", {})
        head = (f"**{k}** — 이벤트 {c['total']} · clean 관측일 {c['clean']} · confounded {c['confounded']}"
                f" · 같은 날 합침 {c.get('same_day_merged', 0)} · 종가 대기 {c['pending']}"
                f" · 즉각 구간: 갭 {ik.get('gap', 0)} / 장중 {ik.get('intraday', 0)}")
        rows = []
        for sym in config.ALL_SYMBOLS:
            hz = blk["symbols"].get(sym, {})
            st = hz.get("close")
            if not st or not st["publishable"]:
                continue
            g = lambda h: (hz.get(h) or {}).get("mean") if (hz.get(h) or {}).get("publishable") else None  # noqa: E731
            rows.append([sym, st["n"], _pct(g("immediate")), _pct(st["mean"]), _pct(st["median"]),
                         _pct(g("next_close")), _pct(g("d3")), _pct(g("d5")), f"{st['neg_pct']:.0f}%",
                         _x(g("rel_range")), _x(g("rel_volume")), _p(st)])
        if rows:
            out.append(head + "\n\n" + _table(
                ["자산", "N", "즉각", "당일", "중앙값", "익일", "+3D", "+5D", "Neg%", "변동폭", "거래량", "p"], rows))
        else:
            out.append(head + f"\n\n_clean N이 {config.MIN_CLEAN_N} 미만 — 통계를 내지 않는다. 표본이 쌓이는 중._\n")
    if not out:
        return "_오늘 이벤트에 해당하는 주제가 없다._\n"
    out.append(f"_즉각 = 장외 게시물은 다음 개장 갭, 정규장 게시물은 시가→종가. 변동폭·거래량은 직전 {config.REL_LOOKBACK_DAYS}거래일 대비 배수. "
               f"p = 같은 자산의 비이벤트 날에서 N개를 뽑은 평균이 관측 평균보다 극단적인 비율(양측, {config.PLACEBO_RESAMPLES}회). "
               f"{noise_p:.2f} 이상(~)이면 무작위 날과 구분되지 않는다._\n")
    return "\n".join(out)


def section_why(a):
    rows = []
    seen = set()
    for e in a["recent_events"]:
        if not e["rule_id"] or e["rule_id"] in seen:
            continue
        seen.add(e["rule_id"])
        rows.append([e["rule_id"], e["path_text"] or "—", e["etf"] or "—", ", ".join(e["affected"][:10]) or "—"])
    return _table(["규칙", "경로", "ETF", "영향 종목 (상위 10 + 언급)"], rows)


def section_narrative(n, key, fallback):
    if not n or not n.get(key):
        return f"_{fallback}_\n"
    return "\n".join(f"- {s}" for s in n[key]) + "\n"


def render(analysis_path=None, narrative_path=None, output_path=None):
    analysis_path = analysis_path or os.path.join(config.OUTPUT_DIR, "trump_analysis.json")
    narrative_path = narrative_path or os.path.join(config.OUTPUT_DIR, "narrative.json")
    output_path = output_path or os.path.join(config.OUTPUT_DIR, "trump_report.md")
    with open(analysis_path, "r", encoding="utf-8") as f:
        a = json.load(f)
    n = None
    if os.path.exists(narrative_path):
        with open(narrative_path, "r", encoding="utf-8") as f:
            n = json.load(f)

    day = a["generated_at"][:10]
    md = [
        f"# Trump Daily Market Trend — {day}",
        "",
        "> 그림자 모드 산출물. 게시되지 않는다. 표는 파이썬 계산값, 문장은 Gemini 서술.",
        "> 시장 반응은 **관찰된 값**이며 발언과의 인과를 의미하지 않는다.",
        "",
        "## 데이터 상태", section_status(a),
        "## 오늘의 발언 (최근 24시간 이벤트)", section_recent(a),
        "## 🔥 급상승 트렌드 (7D · Trend Score)", section_trends(a),
        "## 무엇이 달라졌나", section_narrative(n, "what_changed", "Gemini 서술 없음 (--narrate 로 생성)"),
        "## 창별 트렌드", section_windows(a),
        "## 과거 반응 이력 (clean 이벤트 · SPY 대비 초과 반응 % · 배수 · 플라시보 p)", section_reactions(a),
        "## 왜 이 종목인가", section_why(a),
        "## 내일 볼 것", section_narrative(n, "watch_tomorrow", "Gemini 서술 없음 (--narrate 로 생성)"),
    ]
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"[render] → {output_path}")
    return output_path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    render()
