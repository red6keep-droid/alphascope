"""증시 전망 — 전망 고정 페이지 · 목록 고정 페이지 · 홈 카드 JSON 렌더러.

    python experiments/issue_store/hypo_pages.py      # 목업 3장 + hypo.json 을 output/ 에 쓴다 (그 다음 home_mock.py, mock_server 가 보여 준다)

독자 기준 틀 (2026-11-06 사용자: "일반 독자 관점에서 다시 — 질문 · A/B · 유보 라벨 없이, 심플하게, 설명은 툴팁"):
- 전망 하나 = 사건 하나 + 갈래 둘(더 빠진다 · 되돌아온다) + 숫자 하나. 번호는 `전망 1`.
- 상태 한 마디: 지켜보는 중 → 결과: ○○ 쪽 / 어느 쪽도 아님. 지지 · 반대 · 유보 · A · B 는 내부 말(장부)에만.
- 검증 규칙(네 축 · 이슈 코드 · 에피소드)은 맨 아래 `자세히` 접기와 툴팁에만. 등록 JSON 의 가설 A · B · C 와 숫자 기준은 그대로.
- 화면 날짜는 `11.05`(월.일), 연도가 필요하면 `2026.11.06`.
- 2026-11-06 사용자(P319): 결과 카드 공통 제목 `전망 결과` · 날짜 줄 삭제 · 라벨 모양 교환(실제 결과 = 노랑, 대기 = 회색) · `이 전망이 맞으면` 에 지속 조건 없음(방향을 맞혔으면 맞은 것)
  · `다른 설명은?` → `앞으로 볼 것은?`(위험은 주의사항으로: 얼마나 오래 가나 · 무엇이 되돌리나, 숫자 없이) · 같은 사건에 전망 2(반등) 사전 등록 — 전망 = reg["forecasts"] 목록.
"""
import json
import os
import sys
from datetime import date, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
import design_kit as dk  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "daily-report"))
import cards as qc  # noqa: E402
import tech_signals as TS  # noqa: E402  종목 페이지 강조 카드 안 라벨 박스(BOX: 연한 바탕 · 연한 외곽선 · 굵게 · 같은 폭)  데일리 질문 카드(강조 카드 + 근거 줄 + 카드 안 그래프) 그대로

BLOG = "https://alpha-scope.blogspot.com/"
LIST_SLUG = "forecast-list"
CARD_NAME = "증시 전망"
MARK = {"○": "#15803D", "△": "#C2410C", "✗": "#B91C1C"}
AXES = [("dir", "방향"), ("scope", "범위"), ("timing", "시점"), ("size", "크기")]
TWO_COL = "display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;margin:0 0 8px;"
STATE = {"watch": "neutral", "f1": "negative", "f2": "positive", "neither": "area", "counter": "uncertain"}   # 상태 알약 색




def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def page_url(slug):
    return f"{BLOG}p/{slug}.html"


def md(iso):
    p = str(iso).split("-")
    return f"{p[1]}.{p[2]}" if len(p) == 3 else ".".join(p)


def ymd(iso):
    return str(iso)[:10].replace("-", ".")


def fmt_pp(v):
    return "—" if v is None else ("0.0%p" if abs(v) < 0.05 else f"{v:+.1f}%p")


def mark(m):
    return f'<b style="color:{MARK.get(m, "#111")};font-weight:700;">{dk.esc(m)}</b>'


def sec(title, html, tips):
    return dk.section(title, html, aside=dk.tips_right(tips))


def status_pill(st):
    return dk.pill(st["text"], kind=STATE.get(st["state"], "neutral"), bare=True)


def phase_pill(key):
    text, kind = PHASES[key]
    return dk.pill(text, kind=kind, bare=True)


# ---------------------------------------------------------------- 상태 문장 — 숫자를 문장으로 (2026-11-06 사용자)
# 매일 하나. 출발점(사건 결과일) 뒤 날마다 반도체 vs 시장(rel) · 반도체 하루 등락(d) · 연속 하락일(streak) · 바닥(trough) · 바닥에서 되돌린 비율(recov) · VIX 로 가른다.
# 라벨은 독자 말 일곱 가지뿐. 지지 · 반대 · 유보 · D+n 은 쓰지 않는다.
PHASES = {   # 짧은 이름 — 자세한 풀이는 문장(상태 카드 · 날마다 한 줄)에서 (2026-11-06 사용자: "하락 전망 이렇게 짧게")
    "early":     ("하락 조짐", "neutral"),
    "ongoing":   ("하락 전망", "negative"),
    "deepening": ("하락 전망", "negative"),
    "easing":    ("해소 중", "uncertain"),
    "resolved":  ("해소", "good"),
    "opposite":  ("상승 전망", "positive"),
    "neutral":   ("변화 없음", "neutral"),
    "start":     ("지켜보는 중", "neutral"),   # 등록한 날 — 아직 잴 것이 없다
}
PHASES_REBOUND = {   # 전망 2(반등 — 되돌림 vs 지속) 의 독자 말. 키는 같고 말만 다르다
    "early":     ("변화 없음", "neutral"),
    "ongoing":   ("지속 중", "negative"),
    "deepening": ("지속 중", "negative"),
    "easing":    ("되돌림 조짐", "uncertain"),
    "resolved":  ("되돌림", "good"),
    "opposite":  ("되돌림", "good"),
    "neutral":   ("변화 없음", "neutral"),
    "start":     ("지켜보는 중", "neutral"),
}


def labels_for(fc):
    return PHASES_REBOUND if fc.get("kind") == "rebound" else PHASES


import re as _re
_SIGNED = _re.compile(r"(?<![\w.])([+\-−]\d+(?:\.\d+)?%p?)")
_GAP = _re.compile(r"(\d+(?:\.\d+)?%p?)(\s*(?:더 빠졌|더 빠진|뒤처짐|더 올랐|더 오르))")


def num_html(text):
    """증감 숫자 = 증감 색 + 굵게 (가이드 3-3-1, 2026-11-06 사용자). 부호 있는 숫자는 부호로, `7.9%p 더 빠졌습니다` 처럼 부호 없는 차이는 뒤 말로 방향을 정한다."""
    h = dk.esc(text)
    h = _SIGNED.sub(lambda m: f'<b style="color:{dk.UP if m.group(1)[0] == "+" else dk.DOWN};">{m.group(1)}</b>', h)
    return _GAP.sub(lambda m: f'<b style="color:{dk.DOWN if ("빠" in m.group(2) or "뒤처" in m.group(2)) else dk.UP};">{m.group(1)}</b>{m.group(2)}', h)


def phase_of(rel, d, streak, trough, recov, vix, side="down"):
    """하루치 숫자 → (국면 키, 문장). side="down" = 하락 전망이 실제 결과 쪽일 때."""
    pp = lambda v: f"{abs(v):.1f}%p"   # noqa: E731
    if rel >= 3:
        return "opposite", f"반도체가 시장보다 {pp(rel)} 더 올랐습니다. 하락 전망과 반대로 가고 있습니다."
    if trough <= -3 and recov >= 0.5 and vix < 22:
        return "resolved", f"바닥({pp(trough)} 뒤처짐)에서 절반 넘게 되찾았고 불안 지수(VIX {vix:.0f})도 가라앉았습니다. 이벤트는 해소됐고, 이제 다른 국면입니다."
    if trough <= -3 and recov >= 0.25:
        return "easing", f"바닥({pp(trough)} 뒤처짐)에서 {recov * 100:.0f}% 되돌렸습니다. 해소되어 가는 중입니다."
    if d <= -5:
        return "deepening", f"반도체가 하루 {d:+.1f}% 급락해 시장보다 {pp(rel)} 더 빠졌습니다. 하락 전망대로 깊어지는 중입니다."
    if rel <= -3 and streak >= 3:
        return "deepening", f"{streak}일 연속 하락으로 시장보다 {pp(rel)} 더 빠졌습니다. 하락 전망대로 깊어지는 중입니다."
    if rel <= -3:
        return "ongoing", f"반도체가 시장보다 {pp(rel)} 더 빠진 채 머물고 있습니다. 하락 전망대로 진행 중입니다."
    if rel <= -1:
        return "early", f"반도체가 시장보다 {pp(rel)} 약합니다. 하락 전망의 전조입니다."
    return "neutral", "반도체와 시장이 비슷하게 움직이고 있습니다. 아직 어느 쪽도 아닙니다."


def phase_of_rebound(rel, d, streak, trough, recov, vix):
    """전망 2(반등) 의 하루치 → (국면 키, 문장). 자는 전망 1 과 같다(선거 결과일 11.04 대비 반도체 vs 시장). 바닥에서 얼마나 되돌렸나로 가른다."""
    pp = lambda v: f"{abs(v):.1f}%p"   # noqa: E731
    if trough <= -3 and recov >= 0.5 and vix < 22:
        return "resolved", f"바닥({pp(trough)} 뒤처짐)에서 절반 넘게 되찾았고 불안 지수(VIX {vix:.0f})도 가라앉았습니다. 되돌림 쪽입니다."
    if trough <= -3 and recov >= 0.25:
        return "easing", f"바닥({pp(trough)} 뒤처짐)에서 {recov * 100:.0f}% 되돌렸습니다. 되돌림 조짐입니다."
    if d <= -2 and rel <= trough + 0.5:
        return "deepening", f"반도체가 하루 {d:+.1f}% 더 빠져 시장보다 {pp(rel)} 뒤처졌습니다. 지속 쪽으로 가고 있습니다."
    if rel <= -3 and streak >= 3:
        return "ongoing", f"{streak}일 연속 하락으로 시장보다 {pp(rel)} 뒤처져 있습니다. 지속 쪽입니다."
    return "neutral", f"시장보다 {pp(rel)} 뒤처진 채 바닥 근처에 머물고 있습니다. 아직 어느 쪽도 아닙니다."


def phase_log(days, sox, spx, vix, base_i, prefix=None, start_i=None, fn=phase_of, start_text=None):
    """출발점(base_i = 자의 기준일) 뒤 날마다 (날짜, 국면 키, 문장). start_i = 적기 시작하는 날(전망 2 는 등록일, 자는 그대로 11.04).
    prefix = {날짜: 앞에 붙일 말} (선거 결과 등). fn = 국면 함수(전망 1 phase_of · 전망 2 phase_of_rebound)."""
    out, streak, trough = [], 0, 0.0
    start_i = base_i if start_i is None else start_i
    for i in range(start_i, len(days)):
        if sox[i] is None:
            break
        rel = (sox[i] / sox[base_i] - 1) * 100 - (spx[i] / spx[base_i] - 1) * 100
        d = (sox[i] / sox[i - 1] - 1) * 100 if i else 0.0
        streak = streak + 1 if d < 0 else 0
        trough = min(trough, rel)
        recov = (rel - trough) / (-trough) if trough < 0 else 0.0
        if i == start_i and start_text:
            key, text = "start", start_text
        elif i == base_i:
            key, text = "neutral", "선거 결과가 나왔습니다. 여기서부터 잽니다."
            if d <= -2:
                key, text = "early", f"결과 당일 반도체만 {d:+.1f}% 내렸습니다. 하락 전망의 전조입니다."
        else:
            key, text = fn(rel, d, streak, trough, recov, vix[i])
        if prefix and days[i] in prefix:
            text = prefix[days[i]] + " " + text
        out.append({"day": days[i], "phase": key, "text": text, "rel": rel})
    return out




# ---------------------------------------------------------------- 전망 페이지 — 공용 카드 유형만 쓴다 (가이드라인 2-1: 상태 카드 · C 카드 · D 카드 · 뉴스 카드 · 한 줄 수치 카드 · 펼침 버튼). 새 모양 · 새 색 · 새 px 없음

CHAIN = {"done": ("확인", "down"), "wait": ("대기", "flat"), "no": ("해당 없음", "flat")}   # 2026-11-06 사용자(P319): 대기 = 회색(옛 실제 결과 모양), 실제 결과 = 노랑(옛 대기 모양)   # 종목 페이지 지표 줄 라벨 박스와 같은 모양 (2026-11-06 사용자: "블로그 라벨 샘플대로"). 확인 = 그 갈래 방향 색   # 강조 카드 안 라벨 = 영역 라벨(흰 바탕 · 회색 외곽선, 가이드 5절) (2026-11-06 사용자)
PHASE_CARD = {"early": "neutral", "ongoing": "negative", "deepening": "negative", "easing": "uncertain", "resolved": "good", "opposite": "good", "neutral": "neutral", "start": "neutral"}


def _plain_card(rows_html):
    """C 카드 상자 — 줄 순서가 뜻(고리)이라 데스크톱 2열(data-grid=2)로 나누지 않는다."""
    return f'<div data-cards="1" style="margin:0 0 8px;"><span style="{dk.MULTI}">{"".join(rows_html)}</span></div>'


def _scenario_card(sc, hit, theme="negative", watch=False):
    """결과별 전망 = 데일리 질문 카드(강조 카드 · 접기, 가이드 2-7) 그대로 — 첫 줄 조건(18px 굵게) + 라벨 · 오른쪽 결과(줄바꿈 없음) + 공식 접기 버튼.
    펼치면 고리 줄(18px 이름 · 오른쪽 확인/대기/— 라벨 · 아래 근거 14px)과 `이 전망이 맞으면`.
    실제 결과 쪽 = 그 방향 강조 카드(하락이면 하락 강조 카드), 처음부터 펼침. 일어나지 않은 쪽 = 회색 기본 카드 · 회색 글자, 접힘 (2026-11-06 사용자).
    watch = 아직 결과 전(전망 2 등록 직후): 두 갈래 다 기본 카드 · 답 `지켜보는 중` · 첫 갈래만 펼침.
    `이 전망이 맞으면` 은 방향과 자(3%p)만 — 지속 조건 없음(2026-11-06 사용자: 금방 되돌려도 하락했다는 것이 중요)."""
    th = theme if hit else "neutral"
    ink = PHASE_INK.get(th, "#111") if hit else ("#111" if watch else dk.MUTED)
    lines = [("row", c["step"], c["state"], c["ev"]) for c in sc["chain"]] + [("row", "이 전망이 맞으면", "", sc["win"])]   # 근거 줄의 증감은 질문 카드 tint 가 색을 입힌다
    answer = sc["name"] if hit else ("지켜보는 중" if watch else "일어나지 않음")
    html = qc.question_card(sc["cond"], answer, th, ink, lines, fold=True, opened=hit or (watch and sc["no"] == 1))
    down_side = any(w in sc["name"] for w in ("하락", "지속"))
    for st, (word, kind) in CHAIN.items():   # 근거 줄 값 = 라벨 박스 (질문 카드 값 칸은 글자라 바꿔 끼운다)
        k = (("down" if down_side else "up") if (hit or watch) else "flat") if kind == "down" else kind
        b = TS.box(k, word, dk.esc, sym=False, fit=True)
        html = html.replace(f'font-weight:700;word-break:keep-all;">{st}</span>', f'font-weight:700;word-break:keep-all;">{b}</span>')
        html = html.replace(f'font-weight:700;white-space:nowrap;">{st}</span>', f'font-weight:700;white-space:nowrap;">{b}</span>')
    if hit:   # 실제 결과 쪽만 조건 글자 바로 뒤 라벨
        last = dk.esc(sc["cond"]).rpartition(" ")[2]
        html = html.replace(f'{last}</span>', f'{last}<span style="display:inline-block;margin-left:8px;vertical-align:2px;">{TS.box("caution", "실제 결과", dk.esc, sym=False, fit=True)}</span></span>', 1)
    if not hit and not watch:   # 비활성 — 글자 회색
        html = html.replace("color:#111;", f"color:{dk.MUTED};")
    return html


END_PULL = 21   # 크롬 실측: 당기기 전 그래프 카드 아래 22 · 좌우 10 → 아래도 10 (P140). 음수 여백이 ul −9 와 겹쳐 가장 큰 것만 먹으므로 12 + 9


def _now_block(reg, fc, state):
    """현재 증시는? = 데일리 질문 카드(강조 카드, 가이드 2-7) — 첫 줄 질문 · 답, 쉬운 말 한 줄, 근거 줄, 카드 안 그래프."""
    b, bl = reg["base"], reg["baseline"]
    rel, rec, vix = state.get("rel"), state.get("recovery"), state.get("vix", b["vix"])
    log = state.get("log") or [{"phase": "neutral", "text": ""}]
    key = log[-1]["phase"]
    theme = PHASE_DIR[key]
    sent = log[-1]["text"].split(". ")[0] + "." if log[-1]["text"] else ""
    lines = [("SENTENCE_SLOT", "plain"),
             ("row", "반도체 vs 시장", fmt_pp(rel), fc.get("ruler_from", "선거 결과일 11.04 대비")),
             ("row", "반도체 회복", f"{rec:.0f}%" if rec is not None else "—", fc.get("recov_note", "11.05 하루 낙폭 대비")),
             ("row", "불안 지수 (VIX)", f"{vix:.1f}", "")]
    days, vals = state.get("days", []), state.get("rel_series", [])
    if days:
        n = len(days)
        labels = [md(d) if i in state.get("label_at", []) else "" for i, d in enumerate(days)]
        g = dk.trend_card("반도체 vs 시장 (%p)", labels,
                          [("반도체 vs 시장", vals, dk.CHART_MAIN, "solid"), ("+3%p", [3.0] * n, "#93C5FD", "dash"), ("-3%p", [-3.0] * n, "#FCA5A5", "dash"),
                           (f'평소 {bl["rel20"]:+.1f}', [bl["rel20"]] * n, dk.CHART_CMP, "dash")], fmt_pp)
        # 강조 카드가 그래프 흰 카드로 끝나면 아래 여백 = 그래프 카드 좌우 여백 (가이드 변경 이력 2026-10-31 P140) — li 아래 12 · ul −9 · 카드 아래 패딩을 당긴다
        lines.append((f'<span data-end-chart="1" style="display:block;margin:0 0 -{END_PULL}px;">{g}</span>', "html"))
    tip = state.get("tip_now", "")
    html = qc.question_card("현재 증시는?", labels_for(fc)[key][0], theme if theme in qc.CARD_DIR else "neutral", PHASE_INK.get(theme, "#111"), lines,
                            fold=True, opened=True)   # `현재 증시는?` 옆 툴팁 없음 (2026-11-06 사용자)
    return html.replace("SENTENCE_SLOT", num_html(sent))   # 질문 카드 쉬운 말은 tint(esc) 라 굵게가 안 된다 — 자리표를 증감 색 · 굵게 문장으로   # 질문이 카드 첫 줄, 오른쪽 답 + 공식 접기 버튼 (2026-11-06 사용자)


def _journal(state):
    """진행 경과 = 뉴스 목록 모양(design_kit.item_rules — 카드 없이 기사 사이 가로 구분선, 제목 굵게 · 라벨 · 날짜). 최신 5개 + 나머지 펼침."""
    log = list(reversed(state.get("log") or []))
    if not log:
        return dk.muted("결과일 다음 거래일부터 날마다 하나씩 쌓입니다")
    def item(e):
        text, kind = PHASES[e["phase"]]
        return dk.news_item(num_html(e["text"]), labels=dk.pill(text, kind=kind, bare=True), meta=[md(e["day"])])
    out = dk.item_rules([item(e) for e in log[:5]], sub=True, indent=dk.ALIGN_PX, first_top=18)   # 종목 페이지 뉴스와 같게: 좌측 기준선 6 · 첫 기사 위 18 (엔비디아 NEWS_FIRST_TOP)
    if len(log) > 5:
        out += dk.fold(f"지난 {len(log) - 5}일 더 보기", dk.item_rules([item(e) for e in log[5:]], sub=True, indent=dk.ALIGN_PX))
    return out


def _next_card(fc):
    """앞으로 볼 것은? — 위험은 주의사항처럼 (2026-11-06 사용자: 방향은 맞았지만 언제 회복되나 · 어떤 자극으로 되돌리나는 앞으로의 몫 — 독자에게 알린다).
    숫자 없이 말로, 펼친 채. 옛 `다른 설명은?`(규제 · 되돌림 · AI 투자 둔화의 사후 채점)은 내부 장부로만 — 독자 결론을 깎지 않는다."""
    nx = fc["next"]
    lines = [(nx["lead"], "plain")] + list(nx["lines"])
    if nx.get("tail"):
        lines.append((nx["tail"], "plain"))
    return qc.question_card(nx.get("title", "앞으로 볼 것은?"), nx.get("answer", "지켜보는 중"), "neutral", "#111", lines, fold=True, opened=True)


def _more_cards(reg, fc):
    """더 알아보기 — 질문 카드(데일리 질문 카드). 표 · ○△✗ · σ · 이슈 코드 같은 내부 말 없이 쉬운 문장 + 그래프 (2026-11-06 사용자: "독자에게 어렵다, 맥락에 맞게").
    전망 1(선거) = 선거 전후 그래프 카드 + 앞으로 볼 것. 전망 2(반등) = 앞으로 볼 것(갈림 조건)만."""
    if fc.get("kind") == "rebound":
        return _next_card(fc)
    rows = reg["event_table"]["rows"]
    num = lambda x: float(x.replace("−", "-")) if x else None   # noqa: E731
    groups = [(r[0][:5], [num(r[3]), num(r[1])]) for r in rows]   # 반도체(SOX) · S&P 500
    chart = qc.chart_card("선거 전후 하루 등락 (%)", groups, [qc.sign_bg, qc.gray], [qc.sign_fg, qc.note_fg],
                          [("반도체", qc.sign_bg(-1)), ("S&P 500", qc.GRAY_BAR)], fmt=lambda v: f"{v:+.1f}".replace("-", "−"))
    sox = {r[0][:5]: r[3] for r in rows}
    c1 = qc.question_card("선거 전후 반도체는?", f"11.05 {sox['11.05']}%", "negative", dk.DOWN, [
        ("SENT1", "plain"),
        (f'<span data-end-chart="1" style="display:block;margin:0 0 -{END_PULL}px;">{chart}</span>', "html")], fold=True, opened=False)
    c1 = c1.replace("SENT1", num_html("선거 결과가 나온 다음 날(11.05) 반도체는 하루 -12.25% 빠져 1994년 이후 두 번째로 큰 하락이었습니다. "
                                      "선거 전인 10.30 에도 이미 -7.2% 빠졌습니다."))
    return c1 + _next_card(fc)


PHASE_TEXT_INK = {"early": dk.DOWN, "ongoing": dk.DOWN, "deepening": dk.DOWN, "easing": "#C2410C", "resolved": dk.UP, "opposite": dk.UP, "neutral": "#111", "start": "#111"}


def _day_entry(e, first, bd, phases=PHASES):
    """하루 = 날짜 · 국면(둘 다 강조 카드 첫 줄 글자 18px 굵게, 국면은 방향 색) + 아래 문장(16px, 증감 색 · 굵게). 모든 날 같은 모양."""
    return (f'<div style="padding:{0 if first else 14 - dk.VP}px 0 {14 - dk.VP}px;{"" if first else "border-top:1px solid " + bd + ";"}">'
            f'<span style="display:flex;align-items:baseline;gap:10px;font-size:{dk.EMPH_Q};line-height:{dk.LH_EMPH_Q};font-weight:700;">'
            f'<span style="color:#111;white-space:nowrap;">{dk.esc(md(e["day"]))}</span>'
            f'<span style="color:{PHASE_TEXT_INK[e["phase"]]};">{dk.esc(phases[e["phase"]][0])}</span></span>'
            f'<span style="display:block;margin-top:2px;font-size:{dk.NAME};line-height:{dk.LH_CARD};color:#333;word-break:keep-all;">{num_html(e["text"])}</span></div>')


def _top_card(fc, log, theme):
    """상단 강조 카드 (2026-11-06 사용자): 오늘(가장 최근 날) → `지난 경과 보기` 카드 안 펼침 줄(공용 fold_card 버튼과 같은 모양:
    카드 폭 · 위 구분선 · 14px 굵게 · 화살표, 누르면 버튼 위로 펼치고 `접기`). 지난 날도 같은 모양으로 날짜 내림차순 — 오늘 줄은 내일이 되면 지난 경과로 내려간다.
    게시 · 선거 · 결과 날짜 줄은 카드 안이 아니라 **카드 위**(구획 제목 `전망 결과` 와 카드 사이, 카드 밖 안내 줄 — 왼쪽 12px 들여쓰기 · 14px 회색, 가이드 1절 6)
    (2026-11-06 사용자 P320: "카드 영역에서 빼고 그 카드 위에 배치"). 결과는 오른쪽 끝. 전망마다 fc["dates"] = [[이름, 값], …], 없으면 게시 · 선거 · 결과."""
    bg, bd = dk.CARD_DIR.get(theme, dk.CARD_DIR["neutral"])
    ph = labels_for(fc)
    items = fc.get("dates") or [["게시", fc["posted"]], ["선거", fc["event"][:5]], ["결과", f'{fc["outcome"]["date"]} {fc["outcome"]["text"]}']]
    dates = (f'<span style="display:flex;flex-wrap:wrap;gap:4px 16px;margin:0 0 8px;{dk.GUIDE_IND}'
             f'font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};">'
             + "".join(f'<span style="white-space:nowrap;{"margin-left:auto;" if i == len(items) - 1 else ""}">{dk.esc(k)} : <b style="color:#111;">{dk.esc(v)}</b></span>'
                       for i, (k, v) in enumerate(items))
             + "</span>")
    days = list(reversed(log))   # 최신이 위
    body = _day_entry(days[0], True, bd, ph)
    if len(days) > 1:
        more = "".join(_day_entry(e, False, bd, ph) for e in days[1:])
        btn = dk.FOLD_IN_CARD.replace("#E2E8F0", bd)
        # 버튼 줄만 카드 좌우 · 아래 끝까지(카드 폭 펼침 줄), 펼친 날들은 글 기준선 그대로 — 테마 JS 가 펼친 칸을 버튼 위로 옮긴다
        body += (f'<details data-acc="1" data-fold="1" data-label="지난 경과 보기" style="margin:0;">'
                 f'<summary style="{btn}margin:0 -14px -{dk.EMPH_PAD - dk.VP_EMPH}px;"><span>지난 경과 보기</span> {dk.ACC_CHEV}</summary>'
                 f'<div>{more}</div></details>')
    return dates + dk.dcard(body, theme=theme)


def forecasts(reg):
    return reg.get("forecasts") or [reg["forecast"]]


def forecast_body(reg, state=None, fc=None):
    state = state or {}
    fc = fc or forecasts(reg)[0]
    ph = labels_for(fc)
    log = state.get("log") or []
    latest = log[-1] if log else {"day": fc["outcome"]["date"], "phase": "start", "text": fc.get("start_text", "선거 결과가 나왔습니다. 여기서부터 잽니다."), "rel": 0.0}
    label = ph[latest["phase"]][0]
    rel = state.get("rel")
    rel_t = fmt_pp(rel)
    theme = PHASE_DIR[latest["phase"]]
    concl = _top_card(fc, log or [latest], theme)
    head = f'<div data-lead="1" style="margin:0 0 8px;">{dk.section("전망 결과", concl, line=False)}</div>'   # 공통 제목 `전망 결과` (2026-11-06 사용자 P319 ②)   # data-lead: 홈 카드가 머리로 읽고, 테마 JS 가 옛 엔비디아 글로 오인해 첫 카드를 옮기지 않게
    hit = fc["status"]["state"]
    watch = hit == "watch"
    sides = '<div>' + "".join(_scenario_card(sc, hit == f'f{sc["no"]}', theme, watch=watch) for sc in fc["scenarios"]) + "</div>"
    # 툴팁 = 뜻 한 문장 + `· 오늘 값 : 풀이` 한 줄 (가이드 2-6). 공식 · 표본 수 · 규칙 목록 없음
    over = abs(rel or 0) >= 3
    tip_now = ("반도체 vs 시장은 선거 결과일 뒤 반도체 지수가 시장보다 얼마나 더 움직였나입니다\n"
               f"· 오늘 {rel_t} : 반도체가 시장보다 {abs(rel or 0):.1f}%p 더 {'빠졌고' if (rel or 0) < 0 else '올랐고'}, "
               + ("3%p 금을 넘었습니다" if over else "아직 3%p 금 안입니다"))
    body = (head
            + dk.section(fc.get("sides_title", "선거 결과별 전망"), sides, line=False)   # 제목 아래 구분선 없음 (2026-11-06 사용자)
            + _now_block(reg, fc, dict(state, tip_now=tip_now))   # 구획 제목 없이 — `현재 증시는?` 는 카드 첫 줄. 카드 사이 8 = 종목 페이지 강조 카드 사이 (2026-11-06 사용자)
            + dk.section("더 알아보기", _more_cards(reg, fc), line=False)
            + sec("다른 전망", dk.dot_ul([dk.dot_li(f'<a href="{page_url(o["slug"])}" style="color:#111;">전망 {o["no"]} · {dk.esc(o["title"])}</a>', size=3, lh=dk.LH_BODY, margin=dk.LI_MARGIN)
                                       for o in forecasts(reg) if o["slug"] != fc["slug"]]
                                      + [dk.dot_li(f'<a href="{page_url(LIST_SLUG)}" style="color:#111;">{dk.esc(CARD_NAME)} 전체 목록</a>', size=3, lh=dk.LH_BODY, margin=dk.LI_MARGIN)]), []))
    return dk.fix_colons(f'<div data-list-url="{page_url(LIST_SLUG)}" data-seo-lead="{dk.esc(seo_lead(fc))}">{body}</div>')


def seo_lead(fc):
    return f'증시 전망 {fc["no"]} — {fc["title"]} 두 갈래, 지금 {fc["status"]["text"]}'


def forecast_title(fc):
    return fc["title"]   # 번호 · `— 증시 전망` 없이 (2026-11-06 사용자)


# ---------------------------------------------------------------- 목록 페이지

PHASE_DIR = {"early": "neutral", "ongoing": "negative", "deepening": "negative", "easing": "uncertain", "resolved": "positive", "opposite": "positive", "neutral": "neutral", "start": "neutral"}
PHASE_INK = {"negative": dk.DOWN, "positive": dk.UP}


def _row(fc, state):
    """목록 한 장 = 홈 뉴스 기사 글자(제목 18px 굵게 · 행간 34, 2026-11-06 사용자) + 분류 라벨 · 게시일 + 오른쪽 답(국면 한 마디).
    하락이면 하락 강조 카드(CARD_DIR negative · 위아래 24), 상승이면 상승 강조 카드, 그 밖은 기본 카드 — dcard 그대로."""
    log = state.get("log") or []
    key = log[-1]["phase"] if log else "start"
    word = labels_for(fc)[key][0]
    theme = PHASE_DIR[key]
    tags = dk.pill_row("".join(dk.pill(t, kind="area", bare=True) for t in fc.get("tags", [])))
    left = (f'<a href="{page_url(fc["slug"])}" style="display:block;color:#111;font-weight:700;font-size:18px;line-height:34px;text-decoration:none;word-break:keep-all;">'
            f'{dk.esc(fc["title"])}</a>'
            # 라벨 줄 = 뉴스 카드 라벨 줄(design_kit.news_item) 그대로: 라벨끼리 2px · 라벨과 메타 10px · 위 8 · 14px 메타 회색
            f'<span style="display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;margin:8px 0 1px;line-height:1;">{tags}'
            f'<span style="color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};">{dk.esc(fc["posted"])} 게시</span></span>')
    right = f'<b style="color:{PHASE_INK.get(theme, "#111")};font-size:{dk.BODY};white-space:nowrap;">{dk.esc(word)}</b>'
    inner = (f'<div data-row-link="1" style="display:flex;justify-content:space-between;align-items:center;gap:12px;">'
             f'<div style="{dk.COL_L}">{left}</div><div style="{dk.COL_R}">{right}</div></div>')
    return dk.dcard(inner, theme=theme)


def list_body(regs, states=None, done=()):
    """states = {전망 slug: 상태}. 전망 번호 순."""
    states = states or {}
    pairs = [(reg, fc) for reg in regs for fc in forecasts(reg)]
    rows = [_row(fc, states.get(fc["slug"], {})) for _, fc in pairs]
    opened = "".join(rows) if rows else dk.muted("지금 지켜보는 전망이 없습니다")
    first = states.get(pairs[0][1]["slug"], {}) if pairs else {}
    log = first.get("log") or []
    today = f'· 오늘 {dk.esc(labels_for(pairs[0][1])[log[-1]["phase"]][0])} : {dk.esc(log[-1]["text"])}' if log else "· 오늘 : 아직 결과 전입니다"
    tip = "큰 사건마다 시장의 설명을 결과별로 미리 적어 두고, 사건 뒤 날마다 숫자를 한 마디로 바꿔 확인합니다\n" + today
    sec1 = f'<div style="margin:12px 0 0;">{opened}</div>'   # 구획 제목 `지켜보는 전망` 없음 — 페이지 제목 `증시 전망` 바로 아래 카드 (2026-11-06 사용자)
    if done:
        body2 = dk.table(["전망", "결과", "최종"], [list(c) for c in done])
    else:
        body2 = f'<div style="padding:6px 0 4px {dk.ALIGN_PX}px;font-size:{dk.NAME};line-height:{dk.LH_CARD};color:{dk.MUTED};">아직 없습니다</div>'
    sec2 = sec("끝난 전망", body2, [("안내", "확인이 끝난 전망은 지우지 않고 여기 쌓입니다")])
    return dk.fix_colons(f'<div data-list-url="{BLOG}" data-seo-lead="증시 전망, 큰 사건 뒤 시장의 설명을 미리 적어 두고 숫자로 확인한 기록">{sec1 + sec2}</div>')


# ---------------------------------------------------------------- 홈 카드 JSON

def home_card(regs, states=None, generated=""):
    states = states or {}
    out = {"id": "hypo-card", "label": CARD_NAME, "generated": generated, "list_url": page_url(LIST_SLUG), "open": [], "done_count": 0}
    for reg in regs:
        for fc in forecasts(reg):
            st = states.get(fc["slug"], {})
            log = st.get("log") or [{"day": "", "phase": "start", "text": ""}]
            out["open"].append({"no": fc["no"], "eh": reg["id"], "title": fc["title"], "url": page_url(fc["slug"]),
                                "posted": fc["posted"], "tags": fc.get("tags", []), "event": fc["event"], "outcome": fc["outcome"],
                                "phase": {"key": log[-1]["phase"], "label": labels_for(fc)[log[-1]["phase"]][0]},
                                "latest": log[-1]})
    return out


# ---------------------------------------------------------------- 목업

def _mock_state(reg, data):
    rec = [r for r in data["recent"] if r["d"] >= "2026-11-02"]
    base = next(r for r in rec if r["d"] == "2026-11-04")   # 출발점 = 선거 결과일 종가 (전망 1 · 2 의 자)
    days = [r["d"] for r in rec]
    vals = [(r["sox"] / base["sox"] - 1) * 100 - (r["spx"] / base["spx"] - 1) * 100 for r in rec]
    b = reg["base"]
    d = date.fromisoformat(days[-1])
    while len(days) < len(rec) + 20:
        d += timedelta(days=1)
        if d.weekday() < 5 and d.isoformat() != "2026-11-26":
            days.append(d.isoformat()); vals.append(None)
    last = next(v for v in reversed(vals) if v is not None)   # 마지막 실제 값 (뒤는 빈 자리)
    bi = days.index("2026-11-04")
    sox = [r["sox"] for r in rec] + [None] * (len(days) - len(rec))
    spx, vix = [r["spx"] for r in rec], [r["vix"] for r in rec]
    log = phase_log(days, sox, spx, vix, bi, prefix={"2026-11-04": "선거 결과 민주당 승리."})
    st = {"log": log, "rel": last, "recovery": 0.0, "vix": b["vix"], "days": days, "rel_series": vals,
          "label_at": [2, len(rec) + 4, len(days) - 1], "today": "2026-11-06"}   # 11.02 · 11.04 결과 · 11.05 · 11.12 · 12.04
    # 전망 2(반등) — 자는 같고(11.04 대비), 등록한 11.05 종가부터 적는다. 11.06 시세는 표본에 없어 등록 줄 하나
    log2 = phase_log(days, sox, spx, vix, bi, start_i=days.index("2026-11-05"), fn=phase_of_rebound,
                     start_text="11.05 급락 뒤 반등 전망을 적었습니다. 여기서부터 봅니다.")
    return st, dict(st, log=log2)


if __name__ == "__main__":
    out_dir = os.path.join(_HERE, "output")
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):   # 옛 질문 목업 정리
        if f.startswith("mock_eh-") or f == "mock_hypothesis-list.html":
            os.remove(os.path.join(out_dir, f))
    reg = load(os.path.join(_HERE, "hypotheses", "EH-2026-001.json"))
    data = load(sys.argv[1] if len(sys.argv) > 1 else os.path.join(_HERE, "hypotheses", "EH-2026-001_prices.json"))   # 목업 그래프 · 기준선 = 저장소의 시세 표본 (yfinance 로 만든 것, 2026-11-06) — 집 · 태블릿에서도 같은 목업
    fcs = forecasts(reg)
    st1, st2 = _mock_state(reg, data) if data["recent"] else ({}, {})
    states = {fcs[0]["slug"]: st1, fcs[1]["slug"]: st2} if len(fcs) > 1 else {fcs[0]["slug"]: st1}

    def local(html):
        return html.replace(f"{BLOG}p/", "mock_")
    for fc in fcs:
        print(dk.write_mock(local(forecast_body(reg, states[fc["slug"]], fc)), os.path.join(out_dir, f'mock_{fc["slug"]}.html'), forecast_title(fc)))
    print(dk.write_mock(local(list_body([reg], states)), os.path.join(out_dir, f"mock_{LIST_SLUG}.html"), f"{CARD_NAME}"))
    with open(os.path.join(out_dir, "hypo.json"), "w", encoding="utf-8") as f:
        json.dump(home_card([reg], states, "2026-11-06T04:00:00Z"), f, ensure_ascii=False, indent=1)
