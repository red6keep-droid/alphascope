"""옛 시장 탭 질문 카드 8개 — 2026-11-07 오후 시장 탭을 없애고 오늘 탭 `오늘 움직임은 평소와 달랐나?` 아래로 옮겼다 (사용자: "시장 탭을 오늘 탭으로 다 옮기자").
처음: 2026-11-07 사용자 "시장 탭도 종목 페이지처럼 질문하고 답하는 형태로".

옛 구획(대형주 · 시장 폭 · 달라진 것 · 섹터 · 금리·지표)과 Gemini 해설(change · sector · macro_comment)을 대신한다 —
숫자는 analysis.json(파이썬), 문장은 여기 고정 틀(합니다체). 오늘 · 한국장 · 일정 탭(sections.py)과 같은 방식.
순서 = 무엇이 움직였나(1 ~ 3) → 시장의 결(4 ~ 6) → 바탕(7 · 8). 한국 증시 리포트에 같은 뜻의 질문이 있으면 문구를 같게 했다
(`시총 상위 10개 중 평소와 다르게 움직인 종목은?` · `경제 바탕은 어떤가?`). 답을 만들 값이 없는 날은 그 카드를 뺀다(빈 답 반복 금지).
카드는 정보만 — 단일 변수 단언 금지(가이드라인 1절): "금리가 올라 성장주가 불리" 같은 문장은 쓰지 않는다.
펼친 순서 = 쉬운 문장 → 그래프 → 수치 줄 (한국 증시 리포트 M59 와 같게).
"""

import cards as C
import design_kit as dk
import sections as sx
import taxonomy as TX   # 업종 · 세부 업종 · 테마 공용 분류표 (P385)

UP, DOWN, MUTED = dk.UP, dk.DOWN, dk.MUTED
SRC_PRICE = "Yahoo Finance"
SRC_FRED = "FRED"
INDEX_ROWS = (("sp500", "^GSPC", "S&P 500"), ("nasdaq", "^IXIC", "나스닥"), ("russell", "^RUT", "러셀 2000"))   # 20일 위치 줄
POSITION_NOW = {"20일 고점 부근": "고점 근처", "단기 고점 부근 · 과열 주의": "고점 근처인데 한 달 새 5% 넘게 올라 과열 주의",
                "20일 저점 부근": "저점 근처", "박스 중간": "고점과 저점 사이"}   # analyze.position_stats 라벨 → 쉬운 말
_s = sx._s


def _span(html_text):
    """질문 카드 답을 HTML 그대로 쓰려면 `<span` 으로 시작해야 한다 (cards.question_card)."""
    return f"<span>{html_text}</span>"


def _tri(v):
    """방향만 — ▲ 빨강 · ▼ 파랑 · – 회색 (숫자 없이)."""
    col = UP if v > 0 else DOWN if v < 0 else MUTED
    return f'<span style="color:{col};">{"▲" if v > 0 else "▼" if v < 0 else "–"}</span>'


SLASH_GRAY = "#9CA3AF"   # `▲ n / ▼ n` 가운데 `/` — 보통 굵기 · 연한 회색 (2026-11-08 사용자)


def _up_down(up, down):
    """상승 / 하락 개수 — ▲ 빨강 · ▼ 파랑."""
    return (f'<span style="color:{UP};white-space:nowrap;">▲&nbsp;{up}</span> <span style="font-weight:400;color:{SLASH_GRAY};">/</span> '
            f'<span style="color:{DOWN};white-space:nowrap;">▼&nbsp;{down}</span>')


def _dir(v):
    """결과 방향 → (카드 색, 답 글자 색). 증감 카드 (가이드라인 7-1 · 4절): 오름 = 주황 카드 · 빨강 답, 내림 = 파랑 카드 · 파랑 답, 0 · 없음 = 회색.
    답에는 보라를 쓰지 않는다 (2026-11-07 사용자: "답변 컬러는 상승이냐 하락이냐의 컬러")."""
    if v is None or v == 0:
        return "neutral", "#111"
    return ("positive", UP) if v > 0 else ("negative", DOWN)


def _ans_arrow(v, digits, unit):
    """답 칸의 증감 — 답 글자와 같은 굵기 (dk.arrow 는 700)."""
    return dk.arrow(v, digits, unit).replace("font-weight:700;", "", 1)


# 줄 목록 · 더 보기 부품은 cards.py 로 옮겼다 — 한국 증시 리포트도 같이 쓴다 (2026-11-08 사용자: 미국 기준으로 한국 맞추기)
_rows_block, _rows_fold, _end_fix, more_details, _flat, _line_col = C.rows_block, C.rows_fold, C.end_fix, C.more_details, C.flat_rows, C.line_col


def _one_line(name, pct, ink):
    """답 한 줄 — 이름 + 등락 (2026-11-08 사용자 P405: 두 줄 답이 카드 세로를 늘렸다 — 옛 P382 `_two_line` 두 줄)."""
    return f'<span style="color:{ink};white-space:nowrap;">{C.esc(name)} {C.esc(_s(pct))}</span>'


def _pos_word(pct):
    return "아래쪽 끝" if pct <= 15 else "아래쪽" if pct <= 40 else "가운데" if pct < 60 else "위쪽" if pct < 85 else "위쪽 끝"


def _mon(day):
    return f"{int(str(day)[5:7])}월" if day and len(str(day)) >= 7 else ""


def pos_label(label):
    """20일 위치 라벨 — 고점·저점은 굵게, 라벨 전체 증감 색 (고점 빨강 · 저점 파랑, 2026-10-12 사용자)."""
    if not label:
        return ""
    col = UP if "고점" in label else DOWN if "저점" in label else None
    t = C.esc(label).replace("고점", '<span style="font-weight:700;">고점</span>').replace("저점", '<span style="font-weight:700;">저점</span>')
    return f'<span style="color:{col};">{t}</span>' if col else f"<span>{t}</span>"


# ── 1 ~ 3 무엇이 움직였나 ─────────────────────────────────────────────

def mega_card(a, prev=None):
    """1. 시총 상위 10개 중 평소와 다르게 움직인 종목은? — 답 = 평소 밖 종목 수 `1종목`(없으면 `모두 평소 안`), 카드 색 = 가장 크게 벗어난 종목의 방향.
    펼치면 평소 밖 종목 줄만 보이고, 평소 안 종목은 `평소 범위 안 n개 더 보기` 안. 툴팁 없음 (2026-11-07 사용자 P381)."""
    nr = a.get("normal") or {}
    syms = [s for s in sx.MEGA_KO if s in nr]
    if not syms:
        return ""
    outs = sorted((s for s in syms if nr[s]["outside"]), key=lambda s: -abs(nr[s]["z"]))
    theme, ink = "neutral", "#111"
    if outs:
        theme, ink = _dir(nr[outs[0]]["ret_pct"])
        state = f"{len(outs)}종목"
        first = ("오늘 그 종목의 평소 하루 움직임보다 크게 움직인 종목은 " + " · ".join(f"{sx.MEGA_KO[s]} {_s(nr[s]['ret_pct'])}" for s in outs)
                 + "입니다. 나머지는 평소 범위 안이었습니다.")
    else:
        state = "모두 평소 안"
        first = f"{len(syms)}개 모두 그 종목의 평소 하루 움직임 안에서 움직였습니다."
    rows = sx.mega_rows(a)   # 평소에서 벗어난 크기 순 — 평소 밖 종목이 앞
    # `고르게 올랐나?` 를 합침 (2026-11-08 사용자): 문장 이어 붙이고, 시총 상위 10개 상승 / 하락 + 옛 고르게 카드 근거 줄 → 그 아래 종목 목록
    br = breadth_card(a, prev, parts=True) or ("", [])
    if br[0]:
        first += " " + br[0]
    tu, td = sum(1 for s in syms if nr[s]["ret_pct"] > 0), sum(1 for s in syms if nr[s]["ret_pct"] < 0)
    b_rows = [("row", f"시총 상위 {len(syms)}개 상승 / 하락", _span(_up_down(tu, td)), "미국 시가총액 상위")] + br[1]
    lines = [(first, "plain")] + b_rows + [(_rows_fold(rows, len(outs), f"평소 범위 안 {len(rows) - len(outs)}개 더 보기", theme), "html")]
    return _end_fix(C.question_card("상위 종목 움직임은?", state,   # 옛 `시총 상위 10개 중 평소와 다르게 움직인 종목은?` (2026-11-08 사용자 P413)
                           theme, ink, lines))


BLOG = "https://alpha-scope.blogspot.com"
US_LIST_URL = f"{BLOG}/p/us-market-cap-top10.html"


def notable_card():
    """급락한 날 버틴 종목은? — 한국 증시 리포트 notable_card 와 같은 카드 (2026-11-08 사용자). 재료 = 홈 `주목할 종목`(gh-pages stocks.json notable, 종목 레이더 crash_watch:
    S&P 500 이 2% 넘게 내린 가장 최근 날 오르거나 지수보다 2%p 넘게 덜 내린 후보 종목, 지수와 차이 큰 순) 위 3개. 답 = 1위 종목 · S&P 500 대비 %p, 카드 색 = 그 방향. 줄 = 종목 페이지."""
    import news_pick   # noqa: E402 — 같은 stocks.json 을 이미 한 번 읽는다(뉴스 관련 종목 등락)
    n = news_pick.notable()
    picks = (n.get("stocks") or [])[:3]
    if not picks or not n.get("day") or n.get("index_ret") is None:
        return ""
    bd = dk.darken(dk.lighten(dk.lighten(C.CARD_DIR["neutral"][1]), 0.3), 0.02)
    pct = lambda v: f'<span style="color:{UP if v > 0 else DOWN if v < 0 else "#111"};">{C.esc(_s(v))}</span>'  # noqa: E731
    rows = ""
    for p in picks:
        url = f"{BLOG}/p/{p['slug']}.html" if p.get("page") and p.get("slug") else US_LIST_URL
        sub = dk.tint(C.esc(f"S&P 500보다 {_s(p['ex'], 1, '%p')} · 급락일 {p['held_total']}번 중 ")) + f'<span style="color:#111;">{p["held_n"]}번</span>' + " 버팀"   # 버틴 횟수 = 검정 (2026-11-08 사용자: 보라 그만)
        rows += (f'<span data-row-link="1" data-href="{C.esc(url)}" style="display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 0;'
                 f'border-top:1px solid {bd};font-size:{dk.EMPH_Q};line-height:{dk.LH_EMPH_Q};cursor:pointer;">'
                 f'<span style="flex:1 1 auto;min-width:0;color:#111;"><span style="white-space:nowrap;">{C.esc(p["name"])}</span>'
                 f'<span style="display:block;margin-top:2px;font-size:{dk.TINY};line-height:20px;color:{C.NOTE};">{sub}</span></span>'
                 f'<span style="flex:none;font-weight:700;white-space:nowrap;">{pct(p["cp"])}</span></span>')
    top = picks[0]
    ro = "로" if (ord(top["name"][-1]) - 0xAC00) % 28 in (0, 8) or not ("가" <= top["name"][-1] <= "힣") else "으로"
    first = f"S&P 500이 {sx._md(n['day'])} {_s(n['index_ret'])} 내린 날 가장 잘 버틴 종목은 {top['name']}{ro}, S&P 500보다 {_s(top['ex'], 1, '%p')} 앞섰습니다."
    tip = ("최근 S&P 500이 2% 넘게 내린 날 오르거나 덜 내려 버틴 종목(홈 주목할 종목 카드와 같은 기준) 위 3개\n"
           "· 오늘 : " + " · ".join(p["name"] for p in picks))
    theme, ink = _dir(top["ex"])
    state = _span(f'<span style="color:{ink};white-space:nowrap;">{C.esc(top["name"])} {_s(top["ex"], 1, "%p")}</span>')   # 글자 그대로 — tint 가 이름에 밑줄 링크를 달지 않게
    return C.question_card("급락한 날 버틴 종목은?", state, theme, ink,
                           [(first, "plain"), (rows, "html")], tip=dk.with_src(tip, SRC_PRICE))


def sector_card(a):
    """2. 어느 업종이 움직였나? — 공식 업종 11개만(분류표 TX.SECTORS, P385). 답 = 가장 크게 움직인 업종 · 등락 두 줄(P382), 카드 색 = 그 방향.
    반도체(세부 업종, 기술 안)는 순위 · 개수 · 답에 넣지 않고 기술 줄 바로 아래 따로 한 줄. 막대는 맨 위(가장 오른 업종) 한 줄만, 나머지는 펼침."""
    sec = a.get("sectors") or {}
    allr = sec.get("ranked_1d") or []
    ranked = sorted((dict(r, theme=TX.SECTORS[r["etf"]]) for r in allr if r["etf"] in TX.SECTORS), key=lambda r: -r["ret_1d"])
    if not ranked:
        return ""
    r5 = {r["etf"]: i for i, r in enumerate(sorted(ranked, key=lambda r: -(r.get("ret_5d") or 0)))}   # 5일 순위도 업종 11개 안에서 다시
    for i, r in enumerate(ranked):
        r["rank_change"] = r5[r["etf"]] - i if r.get("ret_5d") is not None else None
    subs = {TX.SUB_INDUSTRIES[r["etf"]][1]: dict(r, theme=TX.SUB_INDUSTRIES[r["etf"]][0]) for r in allr if r["etf"] in TX.SUB_INDUSTRIES}   # 속한 업종 ETF → 세부 업종 줄
    top, bot = ranked[0], ranked[-1]
    ups = sum(1 for r in ranked if r["ret_1d"] > 0)
    top_word = "가장 오른" if top["ret_1d"] > 0 else "가장 덜 내린"
    bot_word = "가장 내린" if bot["ret_1d"] < 0 else "가장 덜 오른"
    first = (f"업종 {len(ranked)}개 중 {ups}개가 올랐습니다. {top_word} 업종은 {top['theme']} {_s(top['ret_1d'])}, "
             f"{bot_word} 업종은 {bot['theme']} {_s(bot['ret_1d'])}입니다.")
    for parent, sub in subs.items():
        first += f" {TX.SECTORS.get(parent, parent)} 업종 안의 {sub['theme']}는 {_s(sub['ret_1d'])}였습니다."
    moved = [r for r in ranked if (r.get("rank_change") or 0) >= 3]
    if moved:
        first += " 5일 순위보다 세 계단 넘게 올라선 업종은 " + " · ".join(r["theme"] for r in moved) + "입니다."
    max_abs = max(abs(r["ret_1d"]) for r in ranked + list(subs.values())) or 1.0
    bars = []
    for r in ranked:
        d = r.get("rank_change")
        sub = "" if d is None else (f"5일 순위 대비 ▲{d}" if d > 0 else f"5일 순위 대비 ▼{-d}" if d < 0 else "5일 순위와 같음")
        bars.append((C.esc(r["theme"]), abs(r["ret_1d"]) / max_abs, UP if r["ret_1d"] >= 0 else DOWN, dk.arrow(r["ret_1d"]), C.esc(" · ".join(x for x in (r["etf"], sub) if x))))
        if r["etf"] in subs:   # 세부 업종은 속한 업종 바로 아래 — 순위 없음
            x = subs[r["etf"]]
            bars.append((C.esc(f"{x['theme']} ({r['theme']} 안)"), abs(x["ret_1d"]) / max_abs, UP if x["ret_1d"] >= 0 else DOWN, dk.arrow(x["ret_1d"]), C.esc(f"{x['etf']} · 세부 업종, 순위에 넣지 않음")))
    w = dk.bar_widths([b[0] for b in bars], [b[3] for b in bars])
    rows = [dk.bar_row(n, f, c, v, w, sb, first=(i == 0)) for i, (n, f, c, v, sb) in enumerate(bars)]
    names = lambda rs: " · ".join(r["theme"] for r in rs)  # noqa: E731
    lines = [(first, "plain"), (f"오늘 앞선 세 업종은 {names(ranked[:3])}, 뒤처진 세 업종은 {names(ranked[-3:][::-1])}입니다.", "plain"),
             (_rows_fold(rows, 1, f"업종 {len(ranked) - 1}개 더 보기", _dir(max(ranked, key=lambda r: abs(r["ret_1d"]))["ret_1d"])[0]), "html")]
    big = max(ranked, key=lambda r: abs(r["ret_1d"]))   # 답 = 가장 크게 움직인 업종 (한국 리포트 `어느 테마가 움직였나?` 와 같은 기준) · 카드 색 = 그 방향
    theme, ink = _dir(big["ret_1d"])
    return _end_fix(C.question_card("업종의 움직임은?", _one_line(big["theme"], big["ret_1d"], ink), theme, ink, lines))   # 툴팁 없음 — 카드 문장 · 근거 줄이 뜻과 값을 다 말한다 (2026-11-08 사용자: 카드와 겹치는 툴팁 생략, 가이드라인 11절)


def theme_card(a):
    """어느 테마가 움직였나? — 테마(TX.THEMES, 업종을 가로지르는 묶음, 기록하지 않음) 구성 종목 하루 등락의 단순 평균 (2026-11-07 P383 · P385).
    지금 테마 = 하이퍼스케일러 하나(이미 모으는 시총 상위 10개 가격만, 새 수집 없음). 답 = 가장 크게 움직인 테마 · 평균 두 줄, 카드 색 = 그 방향.
    구성 종목 값이 일부 빠지면 있는 종목만, 모두 없으면 그 테마를 뺀다."""
    se = a.get("series") or {}
    spx = (se.get("^GSPC") or {}).get("ret_1d")
    got = []
    for key, t in TX.THEMES.items():
        vals = [(m, (se.get(m) or {}).get("ret_1d")) for m in t["members"]]
        vals = [(m, v) for m, v in vals if v is not None]
        if vals:
            got.append((t, sum(v for _, v in vals) / len(vals), vals))
    if not got:
        return ""
    big = max(got, key=lambda g: abs(g[1]))
    theme, ink = _dir(round(big[1], 2))
    lines = []
    max_abs = max([abs(v) for _, _, vals in got for _, v in vals] + [abs(g[1]) for g in got]) or 1.0
    for t, avg, vals in got:
        sent = f"{t['name']}는 {t['desc']}입니다. " + " · ".join(sx.MEGA_KO.get(m, m) for m, _ in vals) + f" {len(vals)}곳 평균은 {_s(avg)}"
        if spx is not None:
            gap = avg - spx
            sent += f"로, S&P 500({_s(spx)})보다 {abs(gap):.2f}%p {'높았' if gap > 0 else '낮았' if gap < 0 else '같았'}습니다."
        else:
            sent += "입니다."
        lines.append((sent, "plain"))
        bars = [(C.esc(f"{t['name']} 평균"), abs(avg) / max_abs, UP if avg >= 0 else DOWN, dk.arrow(round(avg, 2)), "")]
        bars += [(C.esc(sx.MEGA_KO.get(m, m)), abs(v) / max_abs, UP if v >= 0 else DOWN, dk.arrow(v), C.esc(m)) for m, v in sorted(vals, key=lambda x: -x[1])]
        w = dk.bar_widths([b[0] for b in bars], [b[3] for b in bars])
        lines.append((_rows_block([dk.bar_row(n, f, c, v, w, sb, first=(i == 0)) for i, (n, f, c, v, sb) in enumerate(bars)], theme), "html"))
    ans = (_span(f'<span style="color:{ink};">{C.esc(_s(round(big[1], 2)))}</span>') if len(got) == 1   # 테마가 하나면 답 = 등락만 — 이름까지 넣으면 360px 에서 제목이 두 줄 (2026-11-08 사용자 P410)
           else _one_line(big[0]["name"], round(big[1], 2), ink))
    return C.question_card("테마의 움직임은?", ans, theme, ink, lines)   # 툴팁 없음 — 카드 문장 · 근거 줄이 뜻과 값을 다 말한다 (2026-11-08 사용자: 카드와 겹치는 툴팁 생략, 가이드라인 11절)


def breadth_card(a, prev, parts=False):
    """3. 고르게 올랐나? — 답 `11개 중 N개 상승`(보라). 동일가중 − 시총가중이 `큰 회사 몇 곳만 올렸나`의 직접 답.
    옛 상승 비율 등급(양호 · 보통 · 취약)은 뺐다 — 앞날을 가르지 못한 등급 (기획 5절 B5)."""
    b = a.get("breadth") or {}
    if b.get("ratio") is None:
        return ""
    pb = (prev or {}).get("breadth") or {}
    if b.get("mode") == "full":
        up, dn, what = b.get("advancers"), b.get("decliners"), "S&P 500 종목"
    else:
        up, dn, what = b.get("sectors_up"), b.get("sectors_down"), "미국 주요 업종"
    if up is None or dn is None:
        return ""
    n_all = up + dn
    theme, ink = _dir(up - dn)   # 오른 쪽이 많으면 주황 · 내린 쪽이 많으면 파랑 · 같으면 회색 — 몇 개 중 몇 개라도 방향이 있으면 증감 색 (5절)
    state = _span(f'<span style="color:{UP};">▲&nbsp;{up}</span> <span style="font-weight:400;color:{SLASH_GRAY};">/</span> <span style="color:{DOWN};">▼&nbsp;{dn}</span>')   # 오른 · 내린 개수 — 근거 줄 `상승 / 하락` 과 같은 표기
    first = f"{what} {n_all}개 중 {up}개가 올라 상승 비율은 {b['ratio']:.1f}%입니다."
    if pb.get("ratio") is not None:
        first += f" 어제는 {pb['ratio']:.1f}%였습니다."
    r1, r5 = b.get("rsp_spy_1d"), b.get("rsp_spy_5d")
    if r1 is not None:
        first += (f" 종목을 똑같이 담은 지수가 큰 회사 위주 지수보다 {abs(r1):.2f}%p 앞서, 오늘 상승은 넓게 퍼졌습니다." if r1 > 0
                  else f" 큰 회사 위주 지수가 종목을 똑같이 담은 지수보다 {abs(r1):.2f}%p 앞서, 오늘은 몇몇 대형주가 지수를 끌었습니다." if r1 < 0
                  else " 종목을 똑같이 담은 지수와 큰 회사 위주 지수는 오늘 같았습니다.")
    lines = [(first, "plain"),
             ("row", "상승 비율", f"{b['ratio']:.1f}%", f"어제 {pb['ratio']:.1f}%" if pb.get("ratio") is not None else "어제 값 없음"),
             ("row", "상승 / 하락", _up_down(up, dn), what)]
    if b.get("mode") == "full" and b.get("new_high_52w") is not None:
        lines.append(("row", "52주 신고가 / 신저가", f"{b['new_high_52w']} / {b['new_low_52w']}", ""))
    if r1 is not None:
        lines.append(("row", "동일가중 − 시총가중", dk.arrow(r1, 2, "%p"), "오늘 하루"))
    if r5 is not None:
        lines.append(("row", "동일가중 − 시총가중", dk.arrow(r5, 2, "%p"), "5거래일"))
    if parts:   # `상위 종목 움직임은?` 카드 안으로 (2026-11-08 사용자 — 한국 P461 과 같게): 문장 · 근거 줄만
        return first, [("row", ("업종" if b.get("mode") != "full" else "S&P 500 종목") + " 상승 / 하락", *x[2:]) if x[1] == "상승 / 하락" else x for x in lines[1:]]   # 이름에 무엇의 상승 / 하락인지
    tip = (f"오늘 {what} 가운데 오른 쪽이 얼마나 되는지\n· 오늘 {b['ratio']:.1f}% : {n_all}개 중 {up}개가 올랐다"
           "\n· 참고 : 동일가중 − 시총가중은 종목을 똑같이 담은 지수와 큰 회사 위주 지수의 차이. 플러스면 상승이 넓게 퍼졌다는 뜻")
    return C.question_card("고르게 올랐나?", state, theme, ink, lines, tip=dk.with_src(tip, SRC_PRICE))


# ── 4 ~ 6 시장의 결 ───────────────────────────────────────────────────

def rs_card(a, prev, parts=False):
    """4. 기술주 · 소형주는 시장보다 셌나? — 최근 5거래일 나스닥 종합 · 러셀 2000 등락 − S&P 500(%p, 지수 기준 analyze.index_rs) + 나스닥이 웃돈 연속 일수.
    2026-11-07 사용자: 상장지수펀드(QQQ · IWM · SPY) 대신 지수로 — `지수 기술지표의 방향은?` 의 S&P 500 대비와 같은 값. 지수 값이 없는 옛 analysis 는 상장지수펀드 값."""
    ri = a.get("rs_idx") or {}
    if ri.get("nasdaq_5d") is not None or ri.get("russell_5d") is not None:
        q, i, streak, nq = ri.get("nasdaq_5d"), ri.get("russell_5d"), ri.get("nasdaq_streak"), "나스닥"
    else:
        rs = a.get("rs") or {}
        q, i, streak, nq = rs.get("qqq_spy_5d"), rs.get("iwm_spy_5d"), rs.get("qqq_streak"), "나스닥 100"
    if q is None and i is None:
        return ""
    sent = []
    if q is not None:
        sent.append(f"{nq}(기술주)은 S&P 500보다 {abs(q):.2f}%p {'앞섰' if q > 0 else '뒤졌' if q < 0 else '같았'}")
    if i is not None:
        sent.append(f"러셀 2000(소형주)은 {abs(i):.2f}%p {'앞섰' if i > 0 else '뒤졌' if i < 0 else '같았'}")
    strong = [w for v, w in ((q, "기술주"), (i, "소형주")) if v is not None and v > 0]
    known = [w for v, w in ((q, "기술주"), (i, "소형주")) if v is not None]
    # 답은 말로 — `기술주 ▼ · 소형주 ▼` 는 폰에서 제목을 네 줄로 밀었다 (2026-11-07 목업)
    state = ("둘 다 강함" if len(strong) == 2 else "둘 다 약함" if not strong and len(known) == 2 else f"{strong[0]}만 강함" if strong and len(known) == 2
             else f"{known[0]} {'강함' if strong else '약함'}")   # 명사형 — 문장형은 dk.formal 이 `~습니다` 로 바꾼다
    first = "최근 5거래일 동안 " + "고, ".join(sent) + "습니다."
    if streak:
        first += f" {nq}이 S&P 500을 웃돈 날이 {int(streak)}일째 이어졌습니다."
    elif streak == 0:
        first += f" 오늘은 {nq}이 S&P 500을 웃돌지 못했습니다."
    lines = [(first, "plain")]
    # 지수별 5거래일 S&P 500 대비 줄은 `지수 기술지표의 방향은?` 카드 라벨 안 (P392). 문장에 같은 숫자가 있다
    if streak:   # 0일이면 줄을 뺀다 — 문장이 `웃돌지 못했습니다` 로 말한다
        lines.append(("row", f"{nq}이 앞선 날", f"{int(streak)}일 연속", ""))
    won = [w for v, w in ((q, "기술주"), (i, "소형주")) if (v or 0) > 0]
    tip = (f"최근 5거래일 동안 {nq}(기술주) · 러셀 2000(소형주)이 S&P 500(시장 전체)보다 더 강했는지 견준 것\n"
           "· 오늘 : " + (" · ".join(won) + " 쪽이 시장 전체보다 강했다" if won else "둘 다 시장 전체보다 약했다")
           + "\n· 참고 : 값이 플러스면 앞에 적힌 쪽이 더 많이 올랐다는 뜻")
    theme, ink = _dir(len(strong) * 2 - len(known))   # 둘 다 강함 = 주황 · 둘 다 약함 = 파랑 · 엇갈림 = 회색
    if parts:   # `미국 증시 분위기는?` 카드 안 한 묶음으로 (2026-11-07 사용자)
        return ("기술주 · 소형주는 시장보다 셌나?", state, theme, ink, lines, dk.with_src(tip, SRC_PRICE))
    return C.question_card("기술주 · 소형주는 시장보다 셌나?", state, theme, ink, lines, tip=dk.with_src(tip, SRC_PRICE))


def flow_card(a, parts=False):
    """지금 시장 흐름은? — 옛 오늘 탭 카드(sections.market_now_card, D6)와 `고점에서 얼마나 떨어져 있나?` 를 합쳤다 (2026-11-07 사용자: 오늘 · 시장 탭 겹침).
    오늘 탭 = 오늘 하루에 일어난 일, 시장 탭 = 지금 시장의 상태. 변동성 지수 · 금리는 각자 카드가 있어 여기 두지 않는다.
    답 = S&P 500(SPY)이 20 · 50일 평균선 위인가. 둘 다 위 = 주황, 둘 다 아래 = 파랑, 엇갈림 = 회색 (답에 보라 금지, 7-1 — 옛 P330 엇갈림 보라를 바꿨다)."""
    se = a.get("series") or {}
    spy = se.get("^GSPC") or {}   # 지수 기준 (2026-11-07 사용자: 지수 기술지표 카드와 같은 값, 옛 SPY)
    pos = a.get("position") or {}
    sp = pos.get("sp500") or {}
    a20, a50 = spy.get("above_ma20"), spy.get("above_ma50")
    if a20 is None or a50 is None:
        return ""
    state = "평균선 위" if a20 and a50 else "평균선 아래" if not a20 and not a50 else ("20일선 아래" if not a20 else "50일선 아래")
    theme, ink = _dir(1 if a20 and a50 else -1 if not a20 and not a50 else 0)
    first = (f"S&P 500은 최근 20거래일 평균 가격보다 {'위' if a20 else '아래'}, 50거래일 평균 가격보다 {'위' if a50 else '아래'}에 있습니다.")
    fh, fl, label = sp.get("from_high_pct"), sp.get("from_low_pct"), sp.get("position_label") or ""
    if fh is not None:
        first += f" 최근 20거래일 고점보다 {abs(fh):.2f}% 아래" + (f", 저점보다 {abs(fl):.2f}% 위" if fl is not None else "") + f"입니다({POSITION_NOW.get(label, label)})."
    s0 = se.get("^GSPC") or {}
    if s0.get("up_days_20") is not None:
        first += f" 20거래일 중 {s0['up_days_20']}일 올랐고 {s0['down_days_20']}일 내렸습니다."
    lines = [(first, "plain")]
    for n in (20, 50):   # 값 = 평균 가격 대비 % (7-1: 방향 글자만 있는 값 금지, 2026-11-07)
        if spy.get("last") and spy.get(f"ma{n}"):
            lines.append(("row", f"{n}일 평균 가격 대비", dk.arrow(round((spy["last"] / spy[f"ma{n}"] - 1) * 100, 2)), f"S&P 500 · 최근 {n}거래일 평균"))
    # 지수별 `20일 위치` 줄은 `지수 기술지표의 방향은?` 카드 라벨 안으로 옮겼다 (2026-11-07 사용자 P392: 지수 수치를 한 카드에)
    tip = ("S&P 500이 평균 가격선(최근 20 · 50거래일) 위에 있는지와, 최근 한 달 고점 · 저점 사이에서 지금 어디쯤인지\n"
           f"· 오늘 {state} : 20일선 {'위' if a20 else '아래'}, 50일선 {'위' if a50 else '아래'}"
           "\n· 20일 위치 : 고점과 1% 안이면 고점 부근, 저점과 1% 안이면 저점 부근, 그 사이는 박스 중간. 고점 부근이면서 한 달에 5% 넘게 오르면 과열 주의")
    if parts:   # `미국 증시 분위기는?` 카드 안 한 묶음으로 (2026-11-07 사용자)
        return ("지금 시장 흐름은?", state, theme, ink, lines, dk.with_src(tip, SRC_PRICE))
    return C.question_card("지금 시장 흐름은?", state, theme, ink, lines, tip=dk.with_src(tip, SRC_PRICE))   # 오늘 탭 중간이라 접힘 — 탭 첫 카드만 펼침 (P216, 2026-11-07 시장 탭 없앰)


def vix_card(a, parts=False):
    """6. 변동성 지수 — 답 = 변동성 지수 값 + 5거래일 증감. 1년 범위 막대(종목 페이지 `가격 범위 (1년)` 부품) — 그래프에는 비교 대상(9절).
    2026-11-08 사용자 P403: 따로 카드(`시장은 얼마나 긴장했나?`) 대신 `미국 증시 분위기는?` 안 `기술주 · 소형주` 아래 묶음 — 막대 먼저, 그 아래 문장.
    5거래일 전 값은 막대 안 회색 눈금 + 글자(옛 `5거래일 전` 줄 삭제). 35 · 25 기준은 오늘 탭 충격 카드(기획 5절 B3)와 같다 — 늘 같은 안내라 작은 회색 줄."""
    v = a.get("vix") or {}
    now = v.get("now")
    if now is None:
        return ""
    chg = v.get("change_5d")
    theme, ink = _dir(chg)   # 5거래일 증감 방향 (값이 오르면 ▲ 빨강 — 증감 색 규칙, 좋고 나쁨이 아니다)
    state = _span(f'<span style="color:{ink};">{now:.2f}</span>' + (f" {_ans_arrow(chg, 2, '')}" if chg is not None else ""))   # 값 + 5거래일 증감
    first = f"변동성 지수 (VIX)는 {now:.2f}"
    if v.get("prev_5d") is not None and chg is not None:
        first += f"로 5거래일 전({v['prev_5d']:.2f})보다 {abs(chg):.2f} {'올랐' if chg > 0 else '내렸' if chg < 0 else '같'}습니다."
    else:
        first += "입니다."
    lo, hi = v.get("low_1y"), v.get("high_1y")
    if lo is not None and hi is not None and v.get("pos_pct") is not None:
        first += f" 최근 1년 범위({lo:.2f}~{hi:.2f})의 {_pos_word(v['pos_pct'])}에 있습니다."
    sh = a.get("shock") or {}
    if sh.get("active"):
        first += f" 지금은 시장 충격 국면 {sh.get('days_in') or 1}거래일째입니다."
    lines = []
    if lo is not None and hi is not None and v.get("pos_pct") is not None:
        ref = None
        if v.get("prev_5d") is not None and hi > lo:
            ref = ("", (v["prev_5d"] - lo) / (hi - lo) * 100)   # 눈금 · 구간만, 글자 `5거래일 전 19.42` 는 삭제 (2026-11-08 사용자 P412 — 문장에 값이 있다)
        lines.append((C.range_gauge(lo, hi, v["pos_pct"], v["pct_from_high"], lambda x: f"{x:.2f}", "",   # 툴팁 없음 — 최저 · 최고 · 오늘 자리를 막대가 보여 준다 (2026-11-08 사용자)
                                   
                                    "변동성 지수 범위 (1년)", "1년 최고 대비", "1년 최고 근처", ref=ref), "html"))   # 최고가 며칠 전인지는 싣지 않는다 (2026-11-07 사용자: 종목 페이지처럼)
    lines.append((first, "plain"))   # 문장은 막대 아래 (P403)
    lines.append(("35를 넘으면 시장 충격 국면이 시작되고, 25 아래로 내려오면 끝난 것으로 봅니다 (오늘 탭 충격 카드와 같은 기준).", "note"))
    tip = ("변동성 지수 (VIX)는 앞으로 한 달 동안 S&P 500이 얼마나 흔들릴지를 옵션 가격으로 매긴 값. 높을수록 시장이 긴장했다는 뜻\n"
           f"· 오늘 {now:.2f} : " + (f"5거래일 전보다 {abs(chg):.2f} {'높다' if chg > 0 else '낮다' if chg < 0 else '같다'}" if chg is not None else "5거래일 전 값 없음"))
    if parts:
        return ("시장은 얼마나 긴장했나?", state, theme, ink, lines, dk.with_src(tip, SRC_PRICE))
    return C.question_card("시장은 얼마나 긴장했나?", state, theme, ink, lines, tip=dk.with_src(tip, SRC_PRICE))


# ── 7 · 8 바탕 ────────────────────────────────────────────────────────

def _val_chg(rec, unit, digits=2):
    """값 + 단위, 뒤에 직전 관측 대비 증감(%p, 증감 색). 직전 값이 없으면 값만. 옛 bp 표기는 약어 금지 규칙(11절)에 따라 %p 로."""
    if not rec or rec.get("value") is None:
        return dk.dash()
    out = f'<span style="font-weight:400;">{rec["value"]:.{digits}f}{unit}</span>'
    if rec.get("prev") is None or round(rec["value"] - rec["prev"], digits) == 0:   # 변화 0 은 값만 (`– 0.00%p` 를 두지 않는다)
        return out
    return f"{out} {dk.arrow(rec['value'] - rec['prev'], digits, '%p')}"


def rates_card(a, macro, parts=False):
    """7. 금리는 어떻게 움직였나? — 답 = 10년물 값 + 하루 변화(%p). 줄 = 10년물(1일 · 5일) · 2년물 · 10년 − 2년 · 기준금리 · 금리와 성장주."""
    rt = a.get("rates") or {}
    rec10 = macro.get("us10y") or {}
    v10 = rt.get("us10y") if rt.get("us10y") is not None else rec10.get("value")
    if v10 is None:
        return ""
    d1 = rt.get("us10y_change_1d_bp") / 100 if rt.get("us10y_change_1d_bp") is not None else None
    d5 = rt.get("us10y_change_5d_bp") / 100 if rt.get("us10y_change_5d_bp") is not None else None
    day10 = a.get("as_of") if rt.get("us10y") is not None else rec10.get("date", "")
    theme, ink = _dir(round(d1, 2) if d1 is not None else None)   # 하루 변화 방향
    state = _span(f'<span style="color:{ink};">{v10:.2f}%</span>' + (f" {_ans_arrow(d1, 2, '%p')}" if d1 is not None else ""))   # 값 + 하루 증감
    first = f"미국 10년물 국채 금리는 {v10:.2f}%"
    if d1 is not None:
        first += f"로 하루 {abs(d1):.2f}%p {'올랐' if d1 > 0 else '내렸' if d1 < 0 else '같'}"
        if d5 is not None:
            first += f"고, 5거래일로는 {abs(d5):.2f}%p {'올랐' if d5 > 0 else '내렸' if d5 < 0 else '같'}"
        first += "습니다."
    else:
        first += "입니다."
    y2, sp, ff = macro.get("us2y") or {}, macro.get("spread_10_2") or {}, macro.get("fed_funds") or {}
    tail = []
    if y2.get("value") is not None:
        tail.append(f"2년물은 {y2['value']:.2f}%")
    if sp.get("value") is not None:
        tail.append(f"10년물과 2년물의 차이는 {_s(sp['value'])}p")
    if ff.get("value") is not None:
        tail.append(f"기준금리는 {ff['value']:.2f}%")
    if tail:
        first += " " + ", ".join(tail) + "입니다."
    note10 = " · ".join(x for x in ((f"1일 {_s(d1)}p · 5일 {_s(d5)}p" if d1 is not None and d5 is not None else ""), dk.day(day10)) if x)
    lines = [(first, "plain"), ("row", "10년물", f"{v10:.2f}%", note10)]
    for key, name, unit in (("us2y", "2년물", "%"), ("spread_10_2", "10년 − 2년", "%p"), ("fed_funds", "기준금리", "%")):
        rec = macro.get(key) or {}
        if rec.get("value") is not None:
            lines.append(("row", name, _val_chg(rec, unit), dk.day(rec.get("date", ""))))
    if rt.get("growth_label"):
        lines.append(("row", "금리와 성장주", rt["growth_label"], "최근 5거래일"))   # 같은 카드 안 한 줄 — 관계 서술은 값으로만 (단일 변수 단언 금지)
    tip = ("미국 국채 금리의 오늘 값과 변화. 10년물은 주식 · 집값 · 달러에 두루 연결되는 기준 금리로, 10년물 − 2년물 차이는 경기 전망을 볼 때 흔히 씁니다\n"
           f"· 오늘 10년물 {v10:.2f}% : " + (f"하루 {_s(d1)}p" if d1 is not None else "변화 값 없음")
           + "\n· 금리와 성장주 : 5거래일 동안 10년물이 0.1%p 넘게 움직이고 나스닥이 반대로 가면 `부담` · `동반`, 같이 가면 `견조`, 그 밖은 `중립`")
    if parts:   # `시장 환경은?` 카드 안 한 묶음 (2026-11-08 사용자 P404)
        return ("금리는 어떻게 움직였나?", state, theme, ink, lines, dk.with_src(tip, f"{SRC_FRED} · {SRC_PRICE}"))
    return C.question_card("금리의 움직임은?", state, theme, ink, lines, tip=dk.with_src(tip, f"{SRC_FRED} · {SRC_PRICE}"))   # 옛 `금리는 어떻게 움직였나?` (2026-11-08 사용자 P409)


def _man(v):
    """219000 → `21.9만` (실업수당 청구 건수)."""
    return f"{v / 10000:,.1f}만"


def _wk(day):
    """FRED 주간 기준일(토요일) → `11월 1일로 끝난 주`."""
    return f"{int(str(day)[5:7])}월 {int(str(day)[8:10])}일로 끝난 주" if day and len(str(day)) >= 10 else "최근 주"


def claims_lines(macro):
    """주간 실업수당 청구 — 문장 하나 + 줄 둘(신규 · 계속). 사실만 (값 · 전주 대비 · 4주 평균), 좋다 · 나쁘다 판정 없음 (2026-11-09 사용자)."""
    c, c4, cc = macro.get("claims") or {}, macro.get("claims_4wk") or {}, macro.get("claims_cont") or {}
    if c.get("value") is None:
        return []
    d = c["value"] - c["prev"] if c.get("prev") is not None else None
    s = f"{_wk(c.get('date'))} 신규 실업수당 청구는 {_man(c['value'])} 건으로 " + (
        (f"전주보다 {_man(abs(d))} 건 {'늘었' if d > 0 else '줄었'}습니다." if d else "전주와 같습니다.") if d is not None else "나왔습니다.")
    if c4.get("value") is not None:
        s += f" 들쭉날쭉한 주간 값을 고른 4주 평균은 {_man(c4['value'])} 건입니다."
    out = [(s, "plain"),
           ("row", "실업수당 신규 청구", f"{_man(c['value'])} 건", " · ".join(x for x in (
               dk.day(c.get("date", "")) + " 주", f"전주 {_man(c['prev'])}" if c.get("prev") is not None else "",
               f"4주 평균 {_man(c4['value'])}" if c4.get("value") is not None else "") if x))]
    if cc.get("value") is not None:
        out.append(("row", "실업수당 계속 청구", f"{_man(cc['value'])} 건", " · ".join(x for x in (
            dk.day(cc.get("date", "")) + " 주", f"전주 {_man(cc['prev'])}" if cc.get("prev") is not None else "") if x)))
    return out


def economy_card(macro, parts_out=False):
    """8. 경제 바탕은 어떤가? — 한 달에 한 번 나오는 값(실업률 · 소비자물가지수). 답 = 둘의 전월 대비 방향."""
    un, cpi = macro.get("unemployment_rate") or {}, macro.get("cpi") or {}
    if un.get("value") is None and cpi.get("value") is None:
        return ""
    parts, sent, lines, now, dirs = [], [], [], [], []
    if un.get("value") is not None:
        d = (un["value"] - un["prev"]) if un.get("prev") is not None else None
        dirs += [d] if d is not None else []
        parts.append(f"실업률 {_tri(d)}" if d is not None else f"실업률 {un['value']:.1f}%")   # 답은 방향만 — 숫자까지 넣으면 폰에서 제목이 세로로 찌그러진다 (2026-11-07 목업)
        sent.append(f"{_mon(un.get('date'))} 실업률은 {un['value']:.1f}%로 " + (f"전월보다 {abs(d):.1f}%p {'올랐' if d > 0 else '내렸'}습니다." if d else "전월과 같습니다."))
        lines.append(("row", "실업률", f"{un['value']:.1f}%", " · ".join(x for x in (dk.day(un.get("date", "")), f"전월 {un['prev']:.1f}%" if un.get("prev") is not None else "") if x)))
        now.append(f"실업률 {un['value']:.1f}%")
    if cpi.get("value") is not None:
        pct = (cpi["value"] / cpi["prev"] - 1) * 100 if cpi.get("prev") else None
        dirs += [pct] if pct is not None else []
        parts.append(f"물가 {_tri(pct)}" if pct is not None else f"물가지수 {cpi['value']:.1f}")
        sent.append(f"{_mon(cpi.get('date'))} 소비자물가지수({cpi['value']:.1f})는 " + (f"전월보다 {abs(pct):.1f}% {'올랐' if pct > 0 else '내렸'}습니다." if pct else "전월과 같습니다."))
        lines.append(("row", "소비자물가지수", f"{cpi['value']:.1f}", " · ".join(x for x in (dk.day(cpi.get("date", "")), f"전월 대비 {_s(pct, 1)}" if pct is not None else "") if x)))
        now.append(f"물가 전월 대비 {_s(pct, 1)}" if pct is not None else f"물가지수 {cpi['value']:.1f}")
    lines.insert(0, (" ".join(sent), "plain"))
    cl = claims_lines(macro)
    lines += cl
    lines.append(("고용과 물가는 한 달에 한 번, 실업수당 청구는 매주 목요일에 나와 날마다 바뀌지 않습니다. 발표 날짜는 일정 탭에 있습니다." if cl
                  else "고용과 물가는 한 달에 한 번 나와 날마다 바뀌지 않습니다. 발표 날짜는 일정 탭에 있습니다.", "note"))
    tip = ("미국 고용(실업률)과 물가(소비자물가지수, 1982 ~ 1984년 = 100)의 가장 최근 달 값과 전월 대비 변화\n· 오늘 : " + " · ".join(now))
    signs = {(x > 0) - (x < 0) for x in dirs}
    theme, ink = _dir(signs.pop() if len(signs) == 1 else 0)   # 둘 다 오름 = 주황 · 둘 다 내림 = 파랑 · 엇갈림 · 없음 = 회색 (증감 방향, 좋고 나쁨이 아니다)
    if parts_out:   # `시장 환경은?` 카드 안 한 묶음 (P404)
        return ("경제 바탕은 어떤가?", _span(" · ".join(parts)), theme, ink, lines, dk.with_src(tip, SRC_FRED))
    return C.question_card("경제 지표는?", _span(" · ".join(parts)), theme, ink, lines)   # 툴팁 없음 — 카드 문장 · 근거 줄이 뜻과 값을 다 말한다 (2026-11-08 사용자: 카드와 겹치는 툴팁 생략, 가이드라인 11절)   # 옛 `경제 바탕은 어떤가?` — 금리 카드와 짝 (P409)


def index_cards(a, prev):
    """오늘 탭 첫 덩어리(주요 지수 아래) — 같은 지수를 근거로 쓰는 카드: 흐름(20 · 50일) → 기술주 · 소형주(5거래일) (2026-11-07 사용자 P384).
    `오늘 움직임은 평소와 달랐나?`(sections.normal_card) · 충격 카드는 render_html 이 이 앞에 둔다."""
    a = a or {}
    mood = mood_card(a, prev)
    if not mood:   # 분위기 값이 없는 날은 옛 카드 셋을 따로
        mood = sx.normal_card(a, opened=False) + flow_card(a) + rs_card(a, prev)
    return "".join(x for x in (mood, index_tech_card(a, prev)) if x)   # 세 카드 → `미국 증시 분위기는?` 한 카드 (2026-11-07 사용자) · 지수 기술지표 카드 = 덩어리 끝 (P392)


def move_cards(a, prev):
    """둘째 덩어리 — 무엇이 움직였나: 고르게 → 대형주 10개 → 업종 → 테마 (2026-11-08 사용자 P402: `고르게 올랐나?` 를 첫 카드로)."""
    a = a or {}
    return "".join(x for x in (mega_card(a, prev), sector_card(a), theme_card(a), notable_card()) if x)


SRC_CFTC = "CFTC"


def _ct(v):
    """−372318 → `순매도 37.2만 계약` · 10073 → `순매수 1.0만 계약`."""
    return f"{'순매수' if v >= 0 else '순매도'} {abs(v) / 10000:.1f}만 계약"


def cftc_card(cftc):
    """헤지펀드 선물은? — CFTC 레버리지 펀드의 S&P 500 · 나스닥 100 선물 순포지션, 3년 범위 막대 (2026-11-09 사용자).
    사실만 (값 · 전주 대비 · 3년 범위 안 자리). 위험 점수 · 판정 없음 — 극단 포지션이 급락을 앞서는지는 검증 전.
    답 = 두 선물의 3년 범위 자리, 카드 색 = S&P 500 순포지션 전주 대비 방향 (증감 색, 좋고 나쁨이 아니다)."""
    cftc = cftc or {}
    ks = [k for k in ("sp500", "nasdaq") if (cftc.get(k) or {}).get("net") is not None]
    if not ks:
        return ""
    short = {"sp500": "S&P", "nasdaq": "나스닥"}
    state = _span(" · ".join(f"{short[k]} {cftc[k]['pos_pct']}%" for k in ks))
    head = cftc[ks[0]]
    theme, ink = _dir(head["net"] - head["prev"] if head.get("prev") is not None else None)
    lines = []
    for i, k in enumerate(ks):
        x = cftc[k]
        yrs = max(1, round(x.get("weeks", 156) / 52))
        lines.append((C.range_gauge(x["lo"], x["hi"], x["pos_pct"], 0, lambda v: _ct(v).replace(" 계약", ""), "",
                                    f"{x['name']} 선물 순포지션 ({yrs}년)", f"{yrs}년 범위 안 자리", f"{x['pos_pct']}% 지점"), "html"))
        d = x["date"]
        s = (f"{int(d[5:7])}월 {int(d[8:10])}일(화) 기준 " if i == 0 else "") + f"헤지펀드의 {x['name']} 선물 순포지션은 {_ct(x['net'])}"
        if x.get("prev") is not None:
            ch = x["net"] - x["prev"]
            s += (f"으로, 전주({_ct(x['prev'])})보다 {abs(ch) / 10000:.1f}만 계약 {'매수' if ch > 0 else '매도'} 쪽으로 움직였습니다." if ch
                  else f"으로 전주와 같습니다.")
        else:
            s += "입니다."
        s += f" 최근 {yrs}년 범위의 {x['pos_pct']}% 지점입니다."
        lines.append((s, "plain"))
        am = x.get("am") or {}
        if am.get("net") is not None:   # 같은 선물의 반대편 큰손 — 자산운용사 · 연기금 (2026-11-09 사용자)
            ach = am["net"] - am["prev"] if am.get("prev") is not None else None
            lines.append(("row", "자산운용사 · 연기금", _ct(am["net"]), " · ".join(t for t in (
                f"전주보다 {abs(ach) / 10000:.1f}만 계약 {'매수' if ach > 0 else '매도'} 쪽" if ach else ("전주와 같음" if ach == 0 else ""),
                f"{yrs}년 범위의 {am['pos_pct']}% 지점") if t)))
    lines.append(("헤지펀드는 주식을 사고 선물을 파는 거래를 많이 해서 S&P 500 선물은 보통 순매도 쪽입니다. 그래서 방향보다 몇 년 범위의 어디쯤인지를 봅니다. "
                  "범위 끝에 있다고 곧 사거나 판다는 뜻은 아닙니다.", "note"))
    # 2026-11-09 사용자 "넣는데 오른다는 거야? 하락한다는 거야?" — 둘 다 아님. 크게 빠진 주 46번 중 80% 되삼(position_check · 비공개 doc/검증/헤지펀드-포지션-급락-검증.md),
    # 그 뒤 4주는 반등 · 추가 하락 모두 평소보다 컸다 → 방향 신호 아님을 같은 줄에
    # 같은 날 사용자 "자산운용사 · 연기금 줄 추가" — 크게 빠진 주에 판 쪽은 자산운용사 · 연기금(46번 중 45번), 받은 쪽이 헤지펀드
    lines.append(("2009년 이후 S&P 500이 크게 빠진 주에 이 선물을 판 쪽은 거의 늘 자산운용사 · 연기금(46번 중 45번)이었고, 헤지펀드는 80%에서 되샀습니다. "
                  "팔아 둔 선물을 정리한 것으로, 그 뒤 주가가 오른다거나 내린다는 신호는 아닙니다.", "note"))
    lines.append(("화요일 포지션을 그 주 금요일에 발표해 며칠 같은 값이 이어집니다.", "note"))
    tip = ("미국 상품선물거래위원회(CFTC)가 매주 내는 선물 포지션 중 `레버리지 펀드`(헤지펀드 등)의 매수 계약 − 매도 계약. "
           "0% 지점 = 최근 몇 년 중 가장 매도 쪽, 100% 지점 = 가장 매수 쪽. 자산운용사 · 연기금 줄은 같은 선물의 `자산운용사`(연기금 · 뮤추얼 펀드 등) 값\n· 이번 주 : "
           + " · ".join(f"{cftc[k]['name']} {_ct(cftc[k]['net'])}" for k in ks))
    if any(cftc[k].get("source") for k in ks):
        tip += "\n· 이번 주 값을 못 받아 지난번 받은 값입니다"
    return C.question_card("헤지펀드 선물은?", state, theme, ink, lines, tip=dk.with_src(tip, SRC_CFTC))


def base_cards(a, macro, cftc=None):
    """셋째 덩어리 — 시장 환경: `금리의 움직임은?` · `경제 지표는?` 두 카드 (2026-11-08 사용자 P409, P404 한 카드 묶음을 되돌림). 긴장(변동성 지수)은 분위기 카드 안(P403)."""
    a, macro = a or {}, macro or {}
    return "".join(x for x in (rates_card(a, macro), economy_card(macro), cftc_card(cftc)) if x)   # 헤지펀드 선물 포지션 = 덩어리 끝 (2026-11-09 사용자)


def env_card(a, macro):
    """시장 환경은? — 묶음 `금리 움직임` · `경제 지표` (옛 카드 `금리는 어떻게 움직였나?` · `경제 바탕은 어떤가?`). 답 · 카드 색 = 10년물 금리 값 + 하루 증감
    (날마다 바뀌는 쪽 — 경제 지표는 한 달에 한 번, 7-1 카드 색 = 답 방향). 금리 값이 없는 날은 경제 지표가 답."""
    ps = [x for x in (rates_card(a, macro, parts=True), economy_card(macro, parts_out=True)) if x]
    if not ps:
        return ""
    q0, state, theme, ink, _l, _t = ps[0]
    if q0 == "금리는 어떻게 움직였나?":   # 답 = `금리 ▲ 0.02%p` — 값까지 넣으면 360px 에서 제목이 두 줄 (Chrome 실측), 값은 바로 아래 묶음 머리에
        d1 = (a.get("rates") or {}).get("us10y_change_1d_bp")
        if d1 is not None:
            state = _span(f'<span style="color:{ink};">금리 {_ans_arrow(d1 / 100, 2, "%p")}</span>')
    lines = []
    for q, st, _th, ik, ls, _tp in ps:
        lines.append(_part_row(q, st, ik, noline=not lines))   # 첫 묶음 머리는 위 선 없음 — 카드 머리 아래 선과 겹치지 않게
        lines += ls
    tip = ("미국 국채 금리(10년물 · 2년물 · 기준금리)의 오늘 값과 변화, 고용(실업률) · 물가(소비자물가지수)의 가장 최근 달 값. 답은 10년물 금리와 하루 변화\n"
           + "\n".join(t.split("\n", 1)[1] for _q, _s2, _th, _ik, _ls, t in ps if "\n" in t))
    return C.question_card("시장 환경은?", state, theme, ink, lines, tip=tip)


IDX_POS = {"^GSPC": "sp500", "^IXIC": "nasdaq", "^DJI": "dow", "^RUT": "russell"}   # analysis.position 키


def index_tech_card(a, prev):
    """지수 기술지표의 방향은? — 지수 4개(S&P 500 · 나스닥 · 다우 · 러셀 2000) 라벨을 눌러 바꿔 보는 한 카드 (2026-11-07 사용자 P392).
    라벨 안 = ① 오늘 · 흐름(오늘 등락 · 평소 배수 · 20 · 50일선 · 20일 위치 · 5거래일 S&P 500 대비 — `평소와 달랐나?` · `시장 흐름` · `기술주 · 소형주` 카드의 지수 숫자를 여기로)
    ② 종목 페이지 `기술지표의 방향은?` 과 같은 게이지 · 지표 · 이동평균(tech_signals.card). 답 · 카드 색 = S&P 500 전체 요약. 라벨 전환은 글 안 짧은 스크립트(테마 붙여넣기 없음).
    정보 전달만 — 지수 기술지표 판정은 검증한 적 없다(가이드라인 1절 4-2)."""
    import tech_signals as TS
    tx = a.get("tech_idx") or {}
    keys = [k for k in ("^GSPC", "^IXIC", "^DJI", "^RUT") if k in tx]
    if not keys:
        return ""
    nr, se, pos = a.get("normal") or {}, a.get("series") or {}, a.get("position") or {}
    head = tx[keys[0]]
    theme, ink = TS.theme(head["net"], UP, DOWN, MUTED)
    line_col = dk.darken(dk.lighten(dk.lighten(dk.CARD_DIR[theme][1]), 0.3), 0.02)
    spx5 = (se.get("^GSPC") or {}).get("ret_5d")
    panels = []
    for n, k in enumerate(keys):
        rows = []
        if k in nr:
            x = nr[k]
            rows.append(f'<span>하루 등락 <span style="font-size:{TS.WHY_FS};color:#6B7280;">평소 ±{x["sigma_pct"]:.2f}%의 {sx._times(x["z"])}</span></span><b>{dk.arrow(x["ret_pct"])}</b>')   # `오늘` → `하루 등락` (2026-11-07 사용자: 오늘이라고 쓰면 무엇인지 모른다) — 평소 ± = 그 지수의 평소 하루 움직임 크기
        s_ = se.get(k) or {}
        for d in (20, 50):   # 값 = 평균 가격 대비 % (7-1: 방향 글자만 있는 값 금지, 2026-11-07)
            if s_.get("last") and s_.get(f"ma{d}"):
                rows.append(f'<span>{d}일 평균 가격 대비</span><b>{dk.arrow(round((s_["last"] / s_[f"ma{d}"] - 1) * 100, 2))}</b>')
        p = pos.get(IDX_POS[k]) or {}
        if p.get("from_high_pct") is not None:
            note = f"고점 {_s(p['from_high_pct'])}" + (f" · 저점 {_s(p['from_low_pct'])}" if p.get("from_low_pct") is not None else "")
            rows.append(f'<span>20일 위치 <span style="font-size:{TS.WHY_FS};color:#6B7280;">{dk.tint(C.esc(note))}</span></span><b>{pos_label(p.get("position_label")) or "—"}</b>')
        if k != "^GSPC" and spx5 is not None and s_.get("ret_5d") is not None:
            rows.append(f'<span>S&amp;P 500 대비 <span style="font-size:{TS.WHY_FS};color:#6B7280;">5거래일</span></span><b>{dk.arrow(round(s_["ret_5d"] - spx5, 2), 2, "%p")}</b>')
        lines, _ = TS.card(tx[k], sx.INDEX_NAME[k], UP, DOWN, MUTED)
        flow = (TS._sub("오늘 · 흐름") + TS._table(rows, line_col)) if rows else ""
        # 순서 = 게이지(전체 요약 · 기술지표 · 이동평균) → 오늘 · 흐름 → 기술지표 표 → 이동평균 표 (2026-11-07 사용자: 오늘 · 흐름은 `기술지표` 글자 위)
        body = "".join(f'<div style="margin:0 0 12px;">{(flow if i == 1 else "") + h}</div>' for i, (h, _k) in enumerate(lines))
        panels.append(f'<div data-ixp="{n}"{"" if n == 0 else " hidden"}>{body}</div>')
    last = len(keys) - 1
    def chip(i, k):
        on = i == 0
        # 뉴스 탭 분야 탭과 같은 단추(data-chip) — 선택 = 굵은 검정 + 1px 검정 외곽선(테마 CSS [data-chip][aria-pressed=true], P332 · P344) (2026-11-07 사용자: 주요 뉴스 탭과 통일)
        return (f'<button type="button" data-chip="{C.esc(sx.INDEX_NAME[k])}" data-ixc="{i}" aria-pressed="{"true" if on else "false"}" style="flex:1 0 auto;padding:6px 14px;margin:0;background:#fff;color:#4B5563;font:inherit;'
                f'font-size:{dk.TINY};line-height:{dk.LH_TINY};cursor:pointer;white-space:nowrap;border:1px solid #E2E8F0;{"border-left:0;" if i else ""}'
                f'border-radius:{"7px" if i == 0 else "0"} {"7px" if i == last else "0"} {"7px" if i == last else "0"} {"7px" if i == 0 else "0"};">{C.esc(sx.INDEX_NAME[k])}</button>')
    chips = (f'<div data-ix-chips="1" style="display:flex;overflow-x:auto;margin:6px 0 4px;-webkit-overflow-scrolling:touch;scrollbar-width:none;">'
             + "".join(chip(i, k) for i, k in enumerate(keys)) + "</div>")
    js = ("<script>(function(){var s=document.currentScript,b=s&&s.parentNode;if(!b)return;var cs=b.querySelectorAll('[data-ixc]'),ps=b.querySelectorAll('[data-ixp]');"
          "[].forEach.call(cs,function(c){c.addEventListener('click',function(){var i=c.getAttribute('data-ixc');"
          "[].forEach.call(cs,function(x){x.setAttribute('aria-pressed',x===c?'true':'false');});"
          "[].forEach.call(ps,function(p){p.hidden=p.getAttribute('data-ixp')!==i;});});});})();</script>")
    html = f'<div data-ix-tech="1">{chips}{"".join(panels)}{js}</div>'
    tip = ("지수 4개의 오늘 움직임 · 평균 가격선 · 최근 한 달 자리와, 종목 페이지와 같은 기술지표 11개 · 이동평균 12개가 가리키는 방향. 라벨을 누르면 그 지수로 바뀝니다. 답은 S&P 500 기준\n"
           f"· 오늘 S&P 500 {head['word']} : 상승 − 하락을 전체로 나눈 값이 +0.5 넘으면 강한 상승, +0.15 넘으면 상승, −0.15 ~ +0.15 중립, 그 아래 하락 · 강한 하락")
    return C.question_card("지수 기술지표의 방향은?", head["word"], theme, ink, [(html, "html")], tip=dk.with_src(tip, SRC_PRICE))


MOOD_CHART_GAP = 26   # 구분선 ~ `오늘 움직임과 평소 하루 크기` 제목 (px) — 가격 범위 제목 위 여백과 같게 실측
MOOD_KIND = {"상승 추세": ("positive", UP), "단기 조정": ("neutral", "#111"), "조정장": ("negative", DOWN), "불안 국면": ("uncertain", "#92400E")}   # nvda config REGIME_DIRECTION 과 같은 방향


PART_NAME = {"평소와 달랐나?": ("오늘 움직임", "지수 4개 · 평소 하루 움직임과 비교"),
             "지금 시장 흐름은?": ("최근 흐름", "S&P 500 · 20 · 50거래일 평균 가격"),
             "기술주 · 소형주는 시장보다 셌나?": ("기술주 · 소형주", "최근 5거래일 · S&P 500 대비"),
             "시장은 얼마나 긴장했나?": ("VIX 5거래일 전 대비", ""),   # `변동성 지수` 이름 삭제 — 바로 위 막대 제목 · 아래 문장과 겹친다 (2026-11-08 사용자 P412)
             "금리는 어떻게 움직였나?": ("금리 움직임", "10년물 국채 · 하루"),
             "경제 바탕은 어떤가?": ("경제 지표", "실업률 · 소비자물가지수 · 전월 대비")}   # 묶음 제목 = 짧은 명사 (2026-11-08 사용자 P404)   # 묶음 머리 = 근거 줄(이름 · 값 · 뜻) — 옛 카드의 답이 오른쪽 값 (2026-11-07 사용자: 그래프 제목 모양 취소)


def _part_row(q, state, ink, noline=False):
    """한 카드 안 묶음 머리 — 근거 줄 꼴 `("row", 이름, 값, 뜻)`: 왼쪽 명사형 이름 · 오른쪽 옛 카드의 답(그 방향 색) · 아래 회색 뜻 (가이드라인 7-1 근거 줄)."""
    name, note = PART_NAME.get(q, (q, ""))
    col = "#111" if ink in ("#111", MUTED) else ink
    val = state if str(state).startswith("<span") else f'<span style="color:{col};">{dk.tint(C.esc(state))}</span>'
    return ("row", name, val, note) + (("noline",) if noline else ())


def mood_card(a, prev):
    """미국 증시 분위기는? — 종목 페이지와 같은 질문 · 같은 답(상승 추세 · 단기 조정 · 조정장 · 불안 국면, analyze.market_mood) (2026-11-07 사용자).
    안에 옛 카드 셋을 묶음으로: `오늘 움직임은 평소와 달랐나?` · `지금 시장 흐름은?` · `기술주 · 소형주는 시장보다 셌나?` — 각 묶음 머리에 옛 질문 · 답 · 툴팁 그대로."""
    m = a.get("mood") or {}
    if not m.get("regime"):
        return ""
    theme, ink = MOOD_KIND.get(m["regime"], ("neutral", "#111"))
    line_col = dk.darken(dk.lighten(dk.lighten(dk.CARD_DIR[theme][1]), 0.3), 0.02)   # 근거 줄 구분선과 같은 색
    ph = m["pct_from_high"]
    where = "1년 최고가 근처" if ph > -0.5 else f"1년 최고가보다 {abs(ph):.1f}% 아래"
    first = f"1년 고점과 200일 평균으로 보면 S&P 500은 {where}이고, 200일 평균 가격보다 {'위' if m['above_ma200'] else '아래'}에 있습니다."   # 첫 문장 괄호 설명 금지 (7-1)
    # 20일 · 50일 평균 문장은 뺐다 — 바로 아래 `최근 흐름` 묶음이 같은 말을 한다 (2026-11-07 사용자: 반복)
    if m["regime"] == "불안 국면" and m.get("vix") is not None:
        first += f" 변동성 지수(VIX)가 {m['vix']:.1f}로 {m['vix_high']:.0f}을 넘었습니다."
    lines = [(first, "plain")]
    if m.get("low_1y") is not None and m.get("high_1y", 0) > m["low_1y"]:   # 1년 범위 막대 + 200일 평균 눈금 (2026-11-07 사용자: 종목 페이지 `가격 범위 (1년)` 막대 · 목표가 막대 눈금처럼)
        lo, hi = m["low_1y"], m["high_1y"]
        at = lambda v: (v - lo) / (hi - lo) * 100  # noqa: E731
        f0 = lambda v: f"{v:,.0f}"  # noqa: E731
        avg_marks = [("", at(m["ma200"]))]   # 눈금은 200일 평균만(20 · 50일은 넣었다가 뺐다) · 눈금 글자 `200일 평균 7,325` 삭제 (2026-11-07 사용자)
        hd = m.get("high_days")
        legend = "최고가 대비" + ("" if hd is None else " (오늘)" if hd <= 0 else f" ({hd}거래일 전)")   # 종목 페이지 `가격 범위 (1년)` 과 같은 머리 (같은 날 사용자)
        # 제목에서 `(1년)` 뺌 — 범례 `1년 최고 대비` 와 겹친다 · 최고가 며칠 전인지 · 툴팁 없음 (2026-11-07 사용자: 정보 과잉)
        lines.append((C.range_gauge(lo, hi, at(m["last"]), m["pct_from_high"], f0, "", "가격 범위 (1년)", legend, "최고가 근처",
                                    marks=avg_marks), "html"))
    parts = [x for x in (flow_card(a, parts=True), sx.normal_card(a, parts=True), rs_card(a, prev, parts=True), vix_card(a, parts=True)) if x]   # 변동성 지수 = 기술주 · 소형주 아래 (2026-11-08 사용자 P403)   # 최근 흐름(20 · 50일 평균 대비)을 가격 범위 막대 바로 아래로 — 첫 문장 · 막대와 같은 평균 가격 이야기 (2026-11-07 사용자)
    for k, (q, st, _th, ik, ls, _tp) in enumerate(parts):   # 묶음 = 머리 근거 줄(이름 · 옛 답) → 그 묶음의 문장 · 그래프 · 수치 줄
        if q in ("평소와 달랐나?", "시장은 얼마나 긴장했나?"):   # 변동성 지수도 막대 먼저 (P403)   # 그래프(오늘 움직임과 평소 하루 크기)를 `오늘 움직임` 줄 위로 (2026-11-08 사용자)
            charts = [x for x in ls if isinstance(x, tuple) and len(x) == 2 and x[1] == "html"]
            # 위 수치 줄(50일 평균 가격 대비) 아래 구분선 + 선에서 그래프 제목까지 = 가격 범위 제목 위 여백과 같게 (2026-11-08 사용자) — MOOD_CHART_GAP 은 Chrome 실측으로 맞춘 값
            lines += [(f'<span data-mood-sep="1" style="display:block;border-top:1px solid {line_col};margin-top:-6px;padding-top:{MOOD_CHART_GAP}px;">{h}</span>', "html") for h, _k in charts[:1]] + charts[1:]
            ls = [x for x in ls if x not in charts]
        lines.append(_part_row(q, st, ik, noline=(lines[-1][1] == "html")))   # 가로 막대 · 그래프 바로 아래 줄은 위 선 없음 (9절)
        lines += ls
    pb, cr = abs(m["pullback"]), abs(m["correction"])
    tip = ("미국 시장 전체(S&P 500)가 오르는 흐름인지, 쉬어 가는지, 흔들리는지. 종목 페이지 `미국 증시 분위기는?` 과 같은 기준\n"
           f"· 오늘 {m['regime']} : S&P 500이 {where}, 200일 평균보다 {'위' if m['above_ma200'] else '아래'}\n"
           f"· 나누는 법 : 고점에서 {pb:.0f}% 안이면 상승 추세, {pb:.0f}~{cr:.0f}% 아래면 단기 조정, {cr:.0f}% 넘게 빠지거나 200일 평균 아래면 조정장, 변동성 지수 {m['vix_high']:.0f} 이상이면 불안 국면")
    return C.question_card("미국 증시 분위기는?", m["regime"], theme, ink, lines, tip=dk.with_src(tip, SRC_PRICE))
