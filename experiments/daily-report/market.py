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


def _up_down(up, down):
    """상승 / 하락 개수 — ▲ 빨강 · ▼ 파랑."""
    return (f'<span style="color:{UP};white-space:nowrap;">▲&nbsp;{up}</span> / '
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


def _rows_block(rows_html):
    """줄 목록(dk.crow · dk.bar_row)을 질문 카드 안 흰 카드로 — 카드 안 카드(data-cards)를 겹치지 않게 MULTI 틀만 쓴다."""
    return f'<span style="{dk.MULTI}margin:0 {dk.CHART_CARD_X}px;">{"".join(rows_html)}</span>'


def _rows_fold(rows_html, n_show, label):
    """질문 카드 안 줄 목록 — 앞 n_show 줄만 보이고 나머지는 같은 흰 카드 안 `○○ n개 더 보기` (테마 details[data-fold], dk.fold_card 와 같은 버튼).
    2026-11-07 사용자 P381 · P382: 평소 밖 종목 · 맨 위 업종만 보이고 나머지는 접기."""
    rows_html = list(rows_html)
    if len(rows_html) <= n_show:
        return _rows_block(rows_html)
    return (f'<span style="{dk.MULTI}margin:0 {dk.CHART_CARD_X}px;"><span data-grid="2" style="display:block;">{"".join(rows_html[:n_show])}</span>'
            f'<details data-acc="1" data-fold="1" data-label="{C.esc(label)}"><summary style="{dk.FOLD_IN_CARD}"><span>{C.esc(label)}</span> {dk.ACC_CHEV}</summary>'
            f'<span data-grid="2" style="display:block;border-top:1px solid #E2E8F0;">{"".join(rows_html[n_show:])}</span></details></span>')


def _two_line(name, pct, ink):
    """답 두 줄 — 이름 줄바꿈 등락, 오른쪽 정렬 (normal_card 두 지수 답과 같은 꼴, P382)."""
    return f'<span style="display:inline-block;text-align:right;color:{ink};">{C.esc(name)}<br>{C.esc(_s(pct))}</span>'


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

def mega_card(a):
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
    lines = [(first, "plain"), (_rows_fold(rows, len(outs), f"평소 범위 안 {len(rows) - len(outs)}개 더 보기"), "html")]
    return C.question_card("시총 상위 10개 중 평소와 다르게 움직인 종목은?", state, theme, ink, lines)


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
             (_rows_fold(rows, 1, f"업종 {len(ranked) - 1}개 더 보기"), "html")]
    tip = (f"미국 공식 업종 {len(ranked)}개를 대표 상장지수펀드(ETF)로 본 하루 등락. 막대 길이는 등락 크기, 아래 줄은 최근 5일 순위와 견준 자리 변화. "
           "반도체처럼 업종 안의 세부 업종은 속한 업종 아래 따로 두고 순위에는 넣지 않습니다\n"
           f"· 오늘 : {top['theme']} {_s(top['ret_1d'])} ~ {bot['theme']} {_s(bot['ret_1d'])}")
    big = max(ranked, key=lambda r: abs(r["ret_1d"]))   # 답 = 가장 크게 움직인 업종 (한국 리포트 `어느 테마가 움직였나?` 와 같은 기준) · 카드 색 = 그 방향
    theme, ink = _dir(big["ret_1d"])
    return C.question_card("어느 업종이 움직였나?", _two_line(big["theme"], big["ret_1d"], ink), theme, ink, lines, tip=dk.with_src(tip, SRC_PRICE))


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
        lines.append((_rows_block([dk.bar_row(n, f, c, v, w, sb, first=(i == 0)) for i, (n, f, c, v, sb) in enumerate(bars)]), "html"))
    tip = ("업종을 가로질러 같은 이야기로 묶은 종목들의 하루 등락 평균. 공식 업종이 아니라 서로 겹칠 수 있고, 업종 개수 셈에는 넣지 않습니다\n"
           f"· 오늘 : {big[0]['name']} {_s(big[1])}")
    return C.question_card("어느 테마가 움직였나?", _two_line(big[0]["name"], round(big[1], 2), ink), theme, ink, lines, tip=dk.with_src(tip, SRC_PRICE))


def breadth_card(a, prev):
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
    state = _span(f'<span style="color:{UP};">▲&nbsp;{up}</span> / <span style="color:{DOWN};">▼&nbsp;{dn}</span>')   # 오른 · 내린 개수 — 근거 줄 `상승 / 하락` 과 같은 표기
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
    tip = (f"오늘 {what} 가운데 오른 쪽이 얼마나 되는지\n· 오늘 {b['ratio']:.1f}% : {n_all}개 중 {up}개가 올랐다"
           "\n· 참고 : 동일가중 − 시총가중은 종목을 똑같이 담은 지수와 큰 회사 위주 지수의 차이. 플러스면 상승이 넓게 퍼졌다는 뜻")
    return C.question_card("고르게 올랐나?", state, theme, ink, lines, tip=dk.with_src(tip, SRC_PRICE))


# ── 4 ~ 6 시장의 결 ───────────────────────────────────────────────────

def rs_card(a, prev, parts=False):
    """4. 기술주 · 소형주는 시장보다 셌나? — 답 `기술주 ▲ · 소형주 ▼`. 5거래일 상대강도(나스닥 100 · 러셀 2000 vs S&P 500, 상장지수펀드 QQQ · IWM · SPY — 2026-11-07 P384: 나스닥 종합과 다르다) + 연속 일수."""
    rs = a.get("rs") or {}
    prs = (prev or {}).get("rs") or {}
    q, i = rs.get("qqq_spy_5d"), rs.get("iwm_spy_5d")
    if q is None and i is None:
        return ""
    sent = []
    if q is not None:
        sent.append(f"나스닥 100(기술주)은 S&P 500보다 {abs(q):.2f}%p {'앞섰' if q > 0 else '뒤졌' if q < 0 else '같았'}")
    if i is not None:
        sent.append(f"러셀 2000(소형주)은 {abs(i):.2f}%p {'앞섰' if i > 0 else '뒤졌' if i < 0 else '같았'}")
    strong = [w for v, w in ((q, "기술주"), (i, "소형주")) if v is not None and v > 0]
    known = [w for v, w in ((q, "기술주"), (i, "소형주")) if v is not None]
    # 답은 말로 — `기술주 ▼ · 소형주 ▼` 는 폰에서 제목을 네 줄로 밀었다 (2026-11-07 목업)
    state = ("둘 다 강함" if len(strong) == 2 else "둘 다 약함" if not strong and len(known) == 2 else f"{strong[0]}만 강함" if strong and len(known) == 2
             else f"{known[0]} {'강함' if strong else '약함'}")   # 명사형 — 문장형은 dk.formal 이 `~습니다` 로 바꾼다
    first = "최근 5거래일 동안 " + "고, ".join(sent) + "습니다."
    streak = rs.get("qqq_streak")
    if streak:
        first += f" 나스닥 100이 S&P 500을 웃돈 날이 {int(streak)}일째 이어졌습니다."
    elif streak == 0:
        first += " 오늘은 나스닥 100이 S&P 500을 웃돌지 못했습니다."
    lines = [(first, "plain")]
    # 나스닥 100 · 러셀 2000 − S&P 500 줄은 뺐다 — 지수별 5거래일 S&P 500 대비는 `지수 기술지표의 방향은?` 카드 라벨 안 (2026-11-07 사용자 P392). 문장에 같은 숫자가 있다
    if streak:   # 0일이면 줄을 뺀다 — 문장이 `웃돌지 못했습니다` 로 말한다 (2026-11-07)
        lines.append(("row", "나스닥 100이 앞선 날", f"{int(streak)}일 연속", ""))
    won = [w for k, w in (("qqq_spy_5d", "기술주"), ("iwm_spy_5d", "소형주")) if (rs.get(k) or 0) > 0]
    tip = ("최근 5거래일 동안 나스닥 100(기술주) · 러셀 2000(소형주)이 S&P 500(시장 전체)보다 더 강했는지 견준 것\n"
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
    spy = se.get("SPY") or {}
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
    ma = lambda n, up: f'<span style="color:{UP if up else DOWN};">{n}일선 {"위" if up else "아래"}</span>'  # noqa: E731
    lines = [(first, "plain"),
             ("row", "S&P 500 추세", f'<span style="display:inline-block;text-align:right;">{ma(20, a20)}<br>{ma(50, a50)}</span>', "최근 20 · 50거래일 평균 가격과 비교")]
    # 지수별 `20일 위치` 줄은 `지수 기술지표의 방향은?` 카드 라벨 안으로 옮겼다 (2026-11-07 사용자 P392: 지수 수치를 한 카드에)
    tip = ("S&P 500이 평균 가격선(최근 20 · 50거래일) 위에 있는지와, 최근 한 달 고점 · 저점 사이에서 지금 어디쯤인지\n"
           f"· 오늘 {state} : 20일선 {'위' if a20 else '아래'}, 50일선 {'위' if a50 else '아래'}"
           "\n· 20일 위치 : 고점과 1% 안이면 고점 부근, 저점과 1% 안이면 저점 부근, 그 사이는 박스 중간. 고점 부근이면서 한 달에 5% 넘게 오르면 과열 주의")
    if parts:   # `미국 증시 분위기는?` 카드 안 한 묶음으로 (2026-11-07 사용자)
        return ("지금 시장 흐름은?", state, theme, ink, lines, dk.with_src(tip, SRC_PRICE))
    return C.question_card("지금 시장 흐름은?", state, theme, ink, lines, tip=dk.with_src(tip, SRC_PRICE))   # 오늘 탭 중간이라 접힘 — 탭 첫 카드만 펼침 (P216, 2026-11-07 시장 탭 없앰)


def vix_card(a):
    """6. 시장은 얼마나 긴장했나? — 답 = 변동성 지수 값 + 5거래일 증감. 1년 범위 막대(종목 페이지 `가격 범위 (1년)` 부품) — 그래프에는 비교 대상(9절).
    35 · 25 기준은 오늘 탭 충격 카드(기획 5절 B3)와 같다 — 늘 같은 안내라 작은 회색 줄."""
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
    lines = [(first, "plain")]
    if lo is not None and hi is not None and v.get("pos_pct") is not None:
        gauge_tip = f"최근 1년(252거래일) 동안 변동성 지수의 가장 낮았던 값과 가장 높았던 값 사이에서 오늘 값의 자리\n· 오늘 {now:.2f} : 1년 최고 대비 {_s(v['pct_from_high'], 1)}"
        lines.append((C.range_gauge(lo, hi, v["pos_pct"], v["pct_from_high"], lambda x: f"{x:.2f}", dk.with_src(gauge_tip, SRC_PRICE),
                                    "변동성 지수 범위 (1년)", "1년 최고 대비", "1년 최고 근처", v.get("high_days")), "html"))
    if v.get("prev_5d") is not None:
        lines.append(("row", "5거래일 전", f"{v['prev_5d']:.2f}", ""))   # 1년 최고 · 최저는 범위 막대 아래에 있어 줄로 되풀이하지 않는다
    lines.append(("35를 넘으면 시장 충격 국면이 시작되고, 25 아래로 내려오면 끝난 것으로 봅니다 (오늘 탭 충격 카드와 같은 기준).", "note"))
    tip = ("변동성 지수 (VIX)는 앞으로 한 달 동안 S&P 500이 얼마나 흔들릴지를 옵션 가격으로 매긴 값. 높을수록 시장이 긴장했다는 뜻\n"
           f"· 오늘 {now:.2f} : " + (f"5거래일 전보다 {abs(chg):.2f} {'높다' if chg > 0 else '낮다' if chg < 0 else '같다'}" if chg is not None else "5거래일 전 값 없음"))
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


def rates_card(a, macro):
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
    tip = ("미국 국채 금리의 오늘 값과 변화. 10년물은 주식 · 집값 · 달러에 두루 닿는 기준 금리로, 10년물 − 2년물 차이는 경기 전망을 볼 때 흔히 씁니다\n"
           f"· 오늘 10년물 {v10:.2f}% : " + (f"하루 {_s(d1)}p" if d1 is not None else "변화 값 없음")
           + "\n· 금리와 성장주 : 5거래일 동안 10년물이 0.1%p 넘게 움직이고 나스닥이 반대로 가면 `부담` · `동반`, 같이 가면 `견조`, 그 밖은 `중립`")
    return C.question_card("금리는 어떻게 움직였나?", state, theme, ink, lines, tip=dk.with_src(tip, f"{SRC_FRED} · {SRC_PRICE}"))


def economy_card(macro):
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
    lines.append(("고용과 물가는 한 달에 한 번 나와 날마다 바뀌지 않습니다. 발표 날짜는 일정 탭에 있습니다.", "note"))
    tip = ("미국 고용(실업률)과 물가(소비자물가지수, 1982 ~ 1984년 = 100)의 가장 최근 달 값과 전월 대비 변화\n· 오늘 : " + " · ".join(now))
    signs = {(x > 0) - (x < 0) for x in dirs}
    theme, ink = _dir(signs.pop() if len(signs) == 1 else 0)   # 둘 다 오름 = 주황 · 둘 다 내림 = 파랑 · 엇갈림 · 없음 = 회색 (증감 방향, 좋고 나쁨이 아니다)
    return C.question_card("경제 바탕은 어떤가?", _span(" · ".join(parts)), theme, ink, lines, tip=dk.with_src(tip, SRC_FRED))


def index_cards(a, prev):
    """오늘 탭 첫 덩어리(주요 지수 아래) — 같은 지수를 근거로 쓰는 카드: 흐름(20 · 50일) → 기술주 · 소형주(5거래일) (2026-11-07 사용자 P384).
    `오늘 움직임은 평소와 달랐나?`(sections.normal_card) · 충격 카드는 render_html 이 이 앞에 둔다."""
    a = a or {}
    mood = mood_card(a, prev)
    if not mood:   # 분위기 값이 없는 날은 옛 카드 셋을 따로
        mood = sx.normal_card(a, opened=False) + flow_card(a) + rs_card(a, prev)
    return "".join(x for x in (mood, index_tech_card(a, prev)) if x)   # 세 카드 → `미국 증시 분위기는?` 한 카드 (2026-11-07 사용자) · 지수 기술지표 카드 = 덩어리 끝 (P392)


def move_cards(a, prev):
    """둘째 덩어리 — 무엇이 움직였나: 대형주 10개 → 업종 → 테마 → 고르게."""
    a = a or {}
    return "".join(x for x in (mega_card(a), sector_card(a), theme_card(a), breadth_card(a, prev)) if x)


def base_cards(a, macro):
    """셋째 덩어리 — 시장 바탕: 긴장 → 금리 → 경제."""
    a, macro = a or {}, macro or {}
    return "".join(x for x in (vix_card(a), rates_card(a, macro), economy_card(macro)) if x)


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
        if s_.get("above_ma20") is not None and s_.get("above_ma50") is not None:
            w = lambda d, up: f'<span style="color:{UP if up else DOWN};">{d}일선 {"위" if up else "아래"}</span>'  # noqa: E731
            rows.append(f'<span>평균 가격선</span><b>{w(20, s_["above_ma20"])} · {w(50, s_["above_ma50"])}</b>')
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


MOOD_KIND = {"상승 추세": ("positive", UP), "단기 조정": ("neutral", "#111"), "조정장": ("negative", DOWN), "불안 국면": ("uncertain", "#92400E")}   # nvda config REGIME_DIRECTION 과 같은 방향


def _part_head(q, state, ink, tip, line_col, first):
    """한 카드 안 묶음 머리 — 옛 카드의 질문(+ ? 툴팁) 왼쪽 · 답 오른쪽, 묶음 사이 가는 선."""
    if ink == "#111":
        ink = MUTED
    ans = state if str(state).startswith("<span") else dk.tint(C.esc(state))
    return (f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;{"" if first else f"border-top:1px solid {line_col};padding-top:14px;margin-top:6px;"}'
            f'font-weight:700;font-size:17px;line-height:25px;color:#111;"><span style="min-width:0;">{C.esc(q)}{dk.tip_icon(tip) if tip else ""}</span>'
            f'<span style="flex:none;text-align:right;color:{ink};">{ans}</span></span>')


def mood_card(a, prev):
    """미국 증시 분위기는? — 종목 페이지와 같은 질문 · 같은 답(상승 추세 · 단기 조정 · 조정장 · 불안 국면, analyze.market_mood) (2026-11-07 사용자).
    안에 옛 카드 셋을 묶음으로: `오늘 움직임은 평소와 달랐나?` · `지금 시장 흐름은?` · `기술주 · 소형주는 시장보다 셌나?` — 각 묶음 머리에 옛 질문 · 답 · 툴팁 그대로."""
    m = a.get("mood") or {}
    if not m.get("regime"):
        return ""
    theme, ink = MOOD_KIND.get(m["regime"], ("neutral", "#111"))
    line_col = dk.darken(dk.lighten(dk.lighten(dk.CARD_DIR[theme][1]), 0.3), 0.02)
    ph = m["pct_from_high"]
    where = "1년 최고가 근처" if ph > -0.5 else f"1년 최고가보다 {abs(ph):.1f}% 아래"
    first = f"S&P 500은 {where}이고, 200일 평균 가격보다 {'위' if m['above_ma200'] else '아래'}에 있습니다."
    if m["regime"] == "불안 국면" and m.get("vix") is not None:
        first += f" 변동성 지수(VIX)가 {m['vix']:.1f}로 {m['vix_high']:.0f}을 넘었습니다."
    lines = [(first, "plain")]
    parts = [x for x in (sx.normal_card(a, parts=True), flow_card(a, parts=True), rs_card(a, prev, parts=True)) if x]
    for i, (q, st, _th, ik, ls, tp) in enumerate(parts):
        lines.append((_part_head(q, st, ik, tp, line_col, False), "html"))
        lines += ls
    pb, cr = abs(m["pullback"]), abs(m["correction"])
    tip = ("미국 시장 전체(S&P 500)가 오르는 흐름인지, 쉬어 가는지, 흔들리는지. 종목 페이지 `미국 증시 분위기는?` 과 같은 기준\n"
           f"· 오늘 {m['regime']} : S&P 500이 {where}, 200일 평균보다 {'위' if m['above_ma200'] else '아래'}\n"
           f"· 나누는 법 : 고점에서 {pb:.0f}% 안이면 상승 추세, {pb:.0f}~{cr:.0f}% 아래면 단기 조정, {cr:.0f}% 넘게 빠지거나 200일 평균 아래면 조정장, 변동성 지수 {m['vix_high']:.0f} 이상이면 불안 국면")
    return C.question_card("미국 증시 분위기는?", m["regime"], theme, ink, lines, tip=dk.with_src(tip, SRC_PRICE))
