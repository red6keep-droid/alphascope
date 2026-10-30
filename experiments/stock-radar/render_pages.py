"""시총 TOP 10 목록 페이지 · 간단형 상세 페이지 HTML (doc/기획/종목-레이더-기획.md 10-3 · 10-10, 1단계 = 숫자와 실적일만).

카드 모양은 엔비디아 리포트 가격 카드 펼침(가이드라인 2-4 11-1)과 같게 — 그 렌더러의 작은 조각(_row · _row_html · _col_chart …)을 그대로 쓴다.
툴팁은 뜻 · 오늘 · 참고 세 줄(2-6). 이 종목들은 우리 검증을 하지 않았으므로 `기록상` 줄을 두지 않는다(지표 검증 대원칙: 종목마다 따로).
"""

import datetime
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "nvda-report"))

import design_kit as _dk  # noqa: E402
import media_feed  # noqa: E402
import news_store  # noqa: E402  — 공용 뉴스 처리 (헤드라인 · 요약 줄 고르기)
import chart_price as CP  # noqa: E402
import render_html as R  # noqa: E402

import universe as U  # noqa: E402

UP, DOWN, NOTE, TINY = _dk.UP, _dk.DOWN, _dk.NOTE, _dk.TINY
PAD = _dk.SEP_GAP - _dk.VP - 1


def _esc(t):
    return _dk.esc(t)


def _md(d):
    d = datetime.date.fromisoformat(str(d)[:10])
    return f"{d.month}월 {d.day}일"


def _sgn(v):
    return f"{v:+.1f}".replace("-", "−")


def cap_text(c):
    """시가총액 → `5.17조 달러` · `9,940억 달러`."""
    if not c:
        return "—"
    if c >= 1e12:
        return f"{c / 1e12:.2f}조 달러"
    return f"{c / 1e8:,.0f}억 달러"


def updated_line(a):
    return _dk.muted(f"마지막 갱신 {_dk.day(a['day'])} 장 마감 기준")


def wrap(body):
    html = _dk.align_titles(_dk.WRAP_OPEN + body + _dk.WRAP_CLOSE)
    return _dk.formal(_dk.fix_colons(html))   # 카드 밖 구획 제목은 좌측 기준선(ALIGN_PX) (2026-10-23 사용자) · 반말 문장 끝은 합니다체 (2026-10-18 사용자)


def list_marker(url):
    """글 아래 테마 [목록] 버튼이 갈 곳 (테마 JS 가 읽는다, 2026-10-18 사용자: 하단 목록 · TOP 은 엔비디아 글과 공통). 화면에는 안 보인다."""
    return f'<span data-list-url="{_esc(url)}" data-nav="back" hidden></span>'   # data-nav=back : 홈에서 왔으면 `홈으로`, 아니면 `목록으로` (2026-10-29 사용자 P94)


def home_marker():
    """글 아래 버튼을 늘 `홈으로` (목록 · 읽는 법 페이지, 2026-10-29 사용자 P94). 화면에는 안 보인다."""
    return '<span data-nav="home" hidden></span>'


# ---------------------------------------------------------------- 상세 (간단형)

def lead(s):
    """맨 위 요약 1~2문장 (p[data-seo-lead], 가이드라인 10-5) — 날마다 달라지는 글. 파이썬 값만, 평가 · 예측 없음."""
    r = s["ret_1d"]
    move = f"전날보다 {abs(r):.2f}% {'올랐다' if r > 0 else '내렸다'}" if abs(r) >= 0.005 else "전날과 같았다"
    close = f"${s['close']:,.2f}"
    first = f"{_md(s['day'])} {s['name']}({s['sym']}) 종가는 {_dk.josa(close, '로')} {move}."   # `$347.73로` → `으로` (P69)
    nr = s.get("normal_range")
    if nr:
        first += (" 실적 발표에 처음 반응한 날이었다." if nr["earnings_day"] else
                  " 평소 하루 움직임 안의 변화였다." if abs(nr["z"]) < 2 else f" 평소 하루 움직임의 {abs(nr['z']):.1f}배였다.")
    first += R.gap_sentence((s.get("tech") or {}).get("gap"))   # 시가 갭은 평소 범위 바로 뒤 (P80)
    more = []
    if s.get("rank"):
        more.append(f"시가총액은 미국 {s['rank']}위({cap_text(s['cap'])})")
    nxt = (s.get("earnings") or {}).get("next")
    if nxt:
        more.append(f"다음 실적 발표는 {_md(nxt)} 예정")
    text = first + (" " + "이고, ".join(more) + "이다." if more else "")
    return f'<p data-seo-lead="1" style="{_dk.SEO_LEAD}">{_dk.tint(_esc(text))}</p>'   # 요약 문장의 증감도 색 (가이드라인 3-3, 2026-10-21)


def range_tip(s):
    nr = s["normal_range"]
    k = abs(nr["z"])
    now = (f"· 오늘 {_sgn(s['ret_1d'])}% : 실적 발표에 반응한 날이라 평소 범위로 재지 않는다" if nr["earnings_day"] else
           f"· 오늘 {_sgn(s['ret_1d'])}% : 평소 하루 움직임(±{nr['sigma_pct']:.1f}%)의 {k:.1f}배" + (", 평소 범위 안" if k < 2 else ", 평소 범위 밖"))
    return "최근 움직임으로 잰 이 종목의 보통 하루 등락 폭. 그 2배를 넘으면 평소 범위 밖으로 본다\n" + now


def _glance(s):
    """NVDA 리포트 가격 카드 함수(glance_sub · glance_rows)가 읽는 모양으로 옮긴다 — 같은 규칙 · 같은 문구."""
    tc = s.get("tech") or {}
    nr = dict(s["normal_range"], market_shock=s.get("market_shock")) if s.get("normal_range") else None
    return {"headline": {"close": s["close"], "ret_1d": s["ret_1d"], "vol_ratio_20d": s.get("vol_ratio"),
                         "range_pct": tc.get("range_pct"), "ret_vs_spy": tc.get("vs_spy")}, "normal_range": nr}


def price_card(s, today):
    """가격 카드 — NVDA 리포트 sec_headline 과 같은 틀 (2026-10-18 리포트 개편 구조).
    머리 = 가격 줄 + 작은 글씨 한 줄(평소 범위 · 거래량), 오른쪽 접기 버튼. 펼치면 1층(기간별 수익률 · 1년 범위 · 고점 회복 · 실적)과 2층 `차트 정보 보기`.
    거래량 카드는 따로 두지 않는다 — 머리 작은 글씨에 늘 있다 (NVDA 2026-10-18 사용자)."""
    r = s["ret_1d"]
    g = _glance(s)
    pcol = UP if r > 0 else DOWN if r < 0 else "#111"
    tone = R.ROW_UP if r > 0 else R.ROW_DOWN if r < 0 else ""   # 엔비디아 가격 카드와 같은 강조 카드 높이(위아래 여백 · 행간 32) — design_kit 의 ROW_UP 에는 강조 여백이 없다 (2026-10-23 사용자)
    bg, bd = ("#FFF7ED", "#FEE2C1") if r > 0 else ("#EFF6FF", "#D1E5FE") if r < 0 else ("#fff", "#E2E8F0")
    price = R.price_value(f'<span style="color:{pcol};font-weight:700;white-space:nowrap;">${s["close"]:,.2f}</span>', R._arrow(r),
                          R._fold_btn(_dk.lighten(bg), bd) if r else R.ACC_BTN)   # 길면 등락이 아래 줄로 (P61)
    head = R.price_row(R._row(s["sym"], price, tone)).replace("margin:0 0 6px;", "margin:0;", 1)
    sub = R.glance_sub(g)   # 엔비디아와 같은 함수 · 같은 짧은 문구
    if sub:
        head = head.replace("display:flex;", "display:flex;flex-wrap:wrap;", 1).replace("gap:12px;", "column-gap:12px;row-gap:2px;", 1)
        k = head.rstrip().rfind("</span>")
        head = head[:k] + sub + head[k:]
    rows = R.glance_rows(g) + sec_earnings(s, today)   # 가격 범위 (1년) · 기간별 수익률 · 고점 회복 · 차트 정보 보기는 강조 카드 안 (2026-10-26 사용자)
    return (f'<div data-cards="1" style="margin:0 0 8px;"><details data-acc="1"><summary style="list-style:none;cursor:pointer;display:block;">{head}</summary>'
            f'{R.price_in(bg, bd, [sec_year_range(s), R.in_card(sec_drawdown(s), join=True), R.in_card(sec_periods(s), white=True), sec_chart_indicators(s)])}{R.rows_after(rows)}</details></div>')


IMAGE_BRANCH = "radar-images"   # 종목 그래프 전용 브랜치 — 매 실행 그날 그림만 담아 덮어쓴다(이력 없음). 지난 그림은 남지 않는다 (2026-10-20 사용자: 이미지는 휘발성)


def chart_url(sym):
    """가격 그래프 주소 — 고정 페이지라 파일 이름도 고정(날짜 없음). 게시 때 radar-images 브랜치에 올리고 jsDelivr 캐시를 비운다.
    gh-pages(keep_files)에 두면 매일 49장이 커밋 이력에 쌓여 저장소가 커진다 — 그래서 따로 (2026-10-20)."""
    return f"https://cdn.jsdelivr.net/gh/{CP._repo_slug()}@{IMAGE_BRANCH}/images/{chart_ref(sym)}"


def chart_ref(sym):
    return f"radar-{U.BY_SYM[sym][2]}-price.png"


def sec_chart(s):
    """가격 그래프 — NVDA 리포트 sec_chart 와 같은 자리 · 모양 (본문 맨 앞 요약 아래, 확대 보기)."""
    if not s.get("chart"):
        return ""
    url = chart_url(s["sym"])
    zoom = ('<svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">'
            '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5 14 14M7 5v4M5 7h4"/></svg>')
    return (f'<a href="{_esc(url)}" data-zoom="1" target="_blank" rel="noopener" title="그래프 확대 보기" aria-label="그래프 확대 보기" '
            f'style="position:relative;display:block;margin:0 0 16px;max-width:1024px;">'
            f'<img src="{_esc(url)}" alt="{_esc(s["sym"])} {CP.WINDOW}거래일 봉차트" style="width:100%;display:block;border:1px solid #eee;border-radius:8px;"/>'
            f'<span style="position:absolute;right:8px;bottom:8px;display:flex;align-items:center;justify-content:center;width:32px;height:32px;'
            f'background:rgba(255,255,255,.92);border:1px solid #E2E8F0;border-radius:8px;color:#111;">{zoom}</span></a>')


def draw_charts(snap, stocks, out_dir):
    """종목마다 봉차트 PNG (NVDA chart_price.draw 그대로) → output/images/. 시가가 빈 날은 종가로 채운다."""
    for s in stocks:
        bars = [dict(b, open=b["open"] if b.get("open") else b["close"]) for b in (snap["bars"].get(s["sym"]) or [])][-(CP.WINDOW + CP.LOOKBACK):]
        if len(bars) < 2:
            continue
        CP.draw(bars, os.path.join(out_dir, "images", chart_ref(s["sym"])), s["sym"])
        s["chart"] = True


def periods_tip(s, ps):
    p = ps[-1]
    now = ""
    if p.get("spy") is not None:
        d = p["stock"] - p["spy"]
        now = (f"\n· {p['label']} {_sgn(p['stock'])}% : 같은 기간 S&P 500({_sgn(p['spy'])}%)보다 "
               + (f"{abs(d):.1f}%p 앞섰다" if d > 0 else f"{abs(d):.1f}%p 뒤처졌다" if d < 0 else "같았다"))
    return "지금 가격이 1주 · 1개월 · 3개월 · 6개월 · 1년 전보다 얼마나 오르거나 내렸는지. 배당을 넣어 계산했다" + now


def sec_periods(s):
    ps = s.get("periods") or []
    if not ps:
        return ""
    chart = R._col_chart([(p["label"], [p["stock"], p.get("spy")]) for p in ps], [R._sign_bg, lambda v: R._GRAY_BAR], [R._sign_fg, lambda v: NOTE])
    legend = R._legend_chips([(f"{s['name']} 오름", R._PASTEL_UP), (f"{s['name']} 내림", R._PASTEL_DN), ("S&P 500", R._GRAY_BAR)])
    card = f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}"><span style="display:block;padding:{_dk.CHART_CARD_PAD}px 12px 0;">{_dk.legend_top(chart, legend)}</span></span></div>'
    return R._card_title("기간별 수익률 (%)", periods_tip(s, ps)) + card


def year_tip(y):
    pct = y["pct_from_high"]
    where = "1년 최고가 근처" if pct > -0.5 else f"1년 최고가보다 {abs(pct):.1f}% 아래"
    return ("지난 1년 동안 가장 쌌던 값과 가장 비쌌던 값 사이에서 지금 어디쯤인지\n"
            f"· 오늘 ${y['close']:,.2f} : {where}, 범위의 {max(0.0, min(100.0, y['pos_pct'])):.0f}% 지점")


def sec_year_range(s):
    """가격 범위 (1년) — 가격 정보 강조 카드 안 (R.year_range_in, 2026-10-26 사용자)."""
    y = s.get("year_range")
    return R.year_range_in(y, lambda v: f"${v:,.2f}", year_tip(y), (s.get("drawdown") or {}).get("days_since_high")) if y else ""


def earn_tip(s, e):
    when = {"bmo": "장 시작 전", "amc": "장 마감 뒤"}
    now = ""
    if e.get("median_abs") is not None:
        times = e["median_abs"] / e["normal_abs"] if e.get("normal_abs") else None
        now = (f"\n· 보통 ±{e['median_abs']:.1f}% : 최근 {len(e['moves'])}번 중 절반은 이보다 작게, 절반은 크게 움직였다"
               + (f". 보통 날의 약 {times:.0f}배" if times and times >= 1.5 else ""))
    return ("회사가 석 달마다 실적을 발표하면 그 뒤 첫 거래일에 가격이 크게 움직이곤 한다. 오른 날 · 내린 날을 가리지 않고 크기만 본다" + now +
            "\n· 참고 : 발표 시각이 장 시작 전이면 그날, 장 마감 뒤면 다음 거래일을 반응일로 센다")


def sec_earnings(s, today):
    e = s.get("earnings") or {}
    if not e.get("next") and not e.get("moves"):
        return ""
    head, rows, first = "", "", True
    if e.get("next"):
        left = (datetime.date.fromisoformat(e["next"]) - datetime.date.fromisoformat(today)).days
        head = R._row_html("다음 실적 발표", f"{left}일 뒤" if left > 0 else "오늘", f"{_md(e['next'])} 예정", first=True, inline_note=True)
        first = False
    if e.get("median_abs") is not None:
        n = len(e["moves"])
        times = e["median_abs"] / e["normal_abs"] if e.get("normal_abs") else None
        note = f"최근 {n}번 기준" + (f" · 보통 날 하루 ±{e['normal_abs']:.1f}%의 약 {times:.0f}배" if times and times >= 1.5 else "")
        rows += R._row_html("발표 다음 날 보통 변동", f"±{e['median_abs']:.1f}%", note, first=first)
        chart = R._col_chart([(f"{m['day'][2:4]}.{m['day'][5:7]}", [m["ret"]]) for m in e["moves"][::-1]], [R._sign_bg], [R._sign_fg], height=130)   # 최신이 왼쪽 (2026-10-28 사용자 P79)
        rows += (f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px 0;">'
                 f'{_dk.CHART_TITLE}최근 {n}번의 실적 발표 다음 날 (%)</span>'
                 f'<span style="display:block;height:6px;"></span>{chart}</span>')
    if head and rows:   # 다음 발표 줄 오른쪽 접기 버튼 — 보통 변동 · 최근 8번은 펼쳤을 때만 (2026-10-18 사용자)
        k = head.rfind("</span></span>")
        head = head[:k] + R.ACC_BTN + head[k:]
        head = head.replace("align-items:flex-start;", "align-items:center;", 1)
        inner = f'<details data-acc="1"><summary style="list-style:none;cursor:pointer;display:block;">{head}</summary>{rows}</details>'
    else:
        inner = head + rows
    return R._card_title("실적 발표 후 가격 변동", earn_tip(s, e)) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{inner}</span></div>'


def _no_record(tip):
    """NVDA 리포트 툴팁에서 `· 기록상 : …` 줄을 뺀다 — 우리 검증은 엔비디아 · 기술주 기준이라 다른 종목에 옮기지 않는다 (지표 검증 대원칙)."""
    return "\n".join(x for x in tip.split("\n") if not x.startswith("· 기록상"))


def sector_lines(sf):
    pp, rel, n = R.config.SECTOR_FLOW_PP, sf["rel_pp"], sf["days"]
    more = f"{abs(rel):.1f}%p 앞섰다" if rel > 0.05 else (f"{abs(rel):.1f}%p 뒤처졌다" if rel < -0.05 else "비슷하게 움직였다")
    tail = {"모이는 중": f"차이가 +{pp:.0f}%p를 넘어 돈이 {sf['name']} 쪽으로 모이는 중이다.",
            "빠져나가는 중": f"차이가 −{pp:.0f}%p 아래라 돈이 {sf['name']} 쪽에서 빠지는 중이다."}.get(sf["state"], f"차이가 ±{pp:.0f}%p 안이라 돈의 방향은 뚜렷하지 않다.")
    lines = [(f"최근 {n}거래일 {sf['name']} 업종 ETF({sf['etf']})가 S&P 500보다 {more}. {tail}", "plain"),
             (R.flow_gauge(sf, sf["name"]), "html"),   # 엔비디아 반도체 자금 카드와 같은 막대 (2026-10-23 사용자: 새 그래프 모든 페이지)
             ("row", f"{sf['name']} vs 시장 ({n}일)", f"{_sgn(rel)}%p", f"+{pp:.0f}%p 넘으면 유입 · −{pp:.0f}%p 아래면 유출", False, True),
             ("row", "업종 순위", f"{sf['n_pool']}개 중 {sf['rank']}위", "같은 기간 수익률 순")]
    secs = sf.get("sectors") or []
    if secs:
        lines.append(("row", "앞선 업종", "\n".join(f"{x['name']} {_sgn(x['rel'])}%p" for x in secs[:2]), "시장보다 많이 오른 업종"))
        lines.append(("row", "뒤처진 업종", "\n".join(f"{x['name']} {_sgn(x['rel'])}%p" for x in secs[-2:][::-1]), "시장보다 내린 업종"))
    return lines


def sector_rule(sf):
    pp, rel = R.config.SECTOR_FLOW_PP, sf["rel_pp"]
    return (f"투자자 돈이 {sf['name']} 업종으로 들어오는지 빠지는지, 최근 한 달 수익률을 시장과 견줘 본다\n"
            f"· 오늘 {_sgn(rel)}%p : {sf['name']} 업종이 시장보다 {abs(rel):.1f}%p {'앞섰다' if rel > 0 else '뒤처졌다'}, {sf['n_pool']}개 업종 중 {sf['rank']}위\n"
            f"· 나누는 법 : 시장보다 {pp:.0f}%p 넘게 앞서면 모이는 중, {pp:.0f}%p 넘게 뒤지면 빠져나가는 중, 그 사이는 뚜렷하지 않음")


def sec_tech(s):
    """기술지표의 방향은? (옛 제목 기술 지표는 어느 쪽을 가리키나?, P121) (2026-10-30 사용자) — 한국 종목 페이지와 같은 카드 (experiments/tech_signals)."""
    sig = (s.get("tech") or {}).get("signals")
    if not sig:
        return ""
    import tech_signals
    lines, tip = tech_signals.card(sig, s["name"], UP, DOWN, R.MUTED)
    th, col = tech_signals.theme(sig["net"], UP, DOWN, R.MUTED)   # 상승 빨강 · 하락 파랑의 연한 카드 (P99)
    card = R._state_card("기술지표의 방향은?", sig["word"], th, col, lines, "", tip=tip, fold=True)
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{card}</div>'


def sec_states(s):
    """상태 카드 — NVDA 리포트와 같은 카드 · 규칙. 업종 카드만 종목의 업종 ETF 로. 시장 충격 · 한 달 범위 · 과열은 해당하는 날만."""
    out = ""
    ms = s.get("market_shock") or {}
    if ms.get("active"):
        out += R._state_card("시장 충격 국면은?", "충격 국면 중", "uncertain", R.WARN, R.shock_lines(ms), "", tip=_no_record(R.shock_tip(ms)), fold=True)
    mr = s.get("market_regime")
    if mr:
        th, col = R.REGIME_THEME.get(mr["regime"], ("neutral", R.MUTED))
        out += R._state_card("시장 분위기는?", mr["regime"], th, col, R.regime_lines(mr), "", tip=_dk.with_src(R.regime_rule(mr), "Yahoo Finance · CNN"), fold=True)
    sf = s.get("sector_flow")
    if sf:
        th, col = R.FLOW_THEME.get(sf["state"], ("neutral", R.MUTED))
        title = "반도체로 돈이 올까?" if sf["name"] == "반도체" else f"{sf['name']} 업종으로 돈이 올까?"
        out += R._state_card(title, sf["state"], th, col, sector_lines(sf), "", tip=sector_rule(sf), fold=True)
    bb = s.get("bollinger")
    if bb and bb.get("lower") is not None:   # 매일 — 범위 안이어도 오늘 가격의 위치를 본다 (2026-10-23 사용자)
        th, col = R.BOLL_THEME.get(bb["state"], ("neutral", R.MUTED))
        out += R._state_card("한 달간 변화 범위는?", R.BOLL_STATE_KO.get(bb["state"], "범위 안"), th, col,
                             R.bollinger_lines(bb), "", tip=R.bollinger_rule(bb), fold=True, inline_notes=True)
    out += card_opinions(s)   # 애널리스트 · 방송 의견 한 카드 — 한 달 범위 아래 (2026-10-29 P89 · P90)
    oh = s.get("overheat")
    if oh and oh["active"]:
        out += R._state_card("과열 신호는?", f"{len(oh['active'])}개 조건 해당", "neutral", R.MUTED, R.overheat_lines(oh), "", tip=_no_record(R.overheat_rule(oh)))
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>' if out else ""


def sec_chart_indicators(s):
    """2층 · 접힘 `차트 정보 보기` — NVDA 리포트와 같은 칸, 하루 비교는 S&P 500 · 업종 ETF."""
    tc = s["tech"]
    etf = U.sector_etf(s["sym"])[0]
    ma = R.ma_chart(tc["ma_rel"], tc.get("bench_ma_rel"), s["name"], "S&P 500")   # `지금 가격이 평균보다` 그래프는 접기 밖 — 그 아래 `차트 정보 보기` 버튼 (2026-10-29 사용자 P83)
    deep = ""   # 평균선 대비 = 세로 막대 + S&P 500 같은 값 (2026-10-27 사용자 P37)
    deep += R._multi2([("S&P 500 대비", R._arrow(tc.get("vs_spy"), 2, "%p")), (f"{etf} 대비", R._arrow(tc.get("vs_sector"), 2, "%p"))])
    rsi, mc = tc.get("rsi14"), tc.get("ma_cross")
    mc_html = {"golden": f'<span style="color:{UP};font-weight:700;">골든크로스</span>', "death": f'<span style="color:{DOWN};font-weight:700;">데드크로스</span>'}.get(
        mc, f'<span style="color:{R.MUTED};">교차 없음</span>')
    items = [(f"일중 변동폭 (고가−저가 · 흔히 {R.config.RANGE_PCT_EVENT:.0f}% 넘으면 큰 흔들림으로 봄)",
              f'<span style="color:#111;font-weight:700;">{tc["range_pct"]:.2f}%</span>' if tc.get("range_pct") is not None else "—"),
             ("단기 과열 온도 (RSI 14 · 흔히 70 넘으면 과열 · 30 아래면 침체로 읽음)",
              f'<span style="color:#111;font-weight:700;">{rsi:.1f}</span>' if rsi is not None else "—", _no_record(R.rsi_tip(rsi))),
             ("평균선 교차 (50일선이 200일선 위로 = 골든크로스)", mc_html, _no_record(R.cross_tip(mc)))]
    deep += R._multi(items)
    return ma + (f'<details data-fold="1" data-label="차트 정보 보기" style="margin:0 0 8px;"><summary style="list-style:none;cursor:pointer;">{R._fold_row("차트 정보 보기")}</summary>'
            f'<div style="margin-top:6px;">{deep}</div></details>')


def sec_drawdown(s):
    """고점 하락 후 가격 회복 — 이 종목과 S&P 500 (NVDA 리포트는 기술주 15개와 견준다). 숫자 = 절반은 이 거래일 안에 회복."""
    d = s.get("drawdown")
    if not d:
        return ""
    st, sp = d["stock"]["dd"], d["stock"]["spy_dd"]   # S&P 500 은 이 종목과 같은 기간
    span = R._span_label(d["stock"])
    cols = []
    for lv in ("10", "20", "30"):
        x, y = st.get(lv) or {}, sp.get(lv) or {}
        if not x.get("n") or x.get("median_days") is None:
            continue
        if x.get("recovered") and y.get("recovered"):
            cols.append((lv, x["over_year"] / x["recovered"] * 100, y["over_year"] / y["recovered"] * 100))
    tail = ""
    if cols:
        vb = "border-left:1px solid #E2E8F0;"
        cell = lambda txt, first=False: (f'<span style="flex:1 1 0;min-width:0;box-sizing:border-box;padding:0 8px;text-align:{"left" if first else "center"};{"" if first else vb}">{txt}</span>')   # noqa: E731
        tbl_head = cell(f'<span style="color:{DOWN};font-weight:700;">하락비율</span>', True) + "".join(cell(f'<span style="color:{DOWN};font-weight:700;">−{lv}%</span>') for lv, _, _ in cols)
        r1 = cell(_esc(s["name"]), True) + "".join(cell(f"{a:.0f}%") for _, a, _ in cols)
        r2 = cell("S&amp;P 500", True) + "".join(cell(f"{b:.0f}%") for _, _, b in cols)
        tbl = "".join(f'<span style="display:flex;align-items:stretch;line-height:24px;">{r}</span>' for r in (tbl_head, r1, r2))
        tip = "크게 떨어진 일 가운데, 최고가를 되찾기까지 1년(250거래일) 넘게 걸린 경우의 비율"
        title = (f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:0 0 4px;">'
                 f'<span style="color:#111;font-weight:700;white-space:nowrap;">회복에 1년 넘게 걸린 비율{R._tipx(tip)}</span></span>')   # `(약 30년 기간 중)` 은 뺐다 — 기간은 머리 작은 줄에 (2026-10-27 P17 · P24)
        tail = f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px;font-size:{TINY};color:{NOTE};">{title}{tbl}</span>'
    x = d["pct_from_high"]
    lv = next((l for l in ("30", "20", "10") if -x > int(l) and (st.get(l) or {}).get("median_days") is not None), None)
    now = (f"\n· 지금 {_sgn(x)}% : −{lv}% 넘게 빠졌을 때 절반은 {st[lv]['median_days']}거래일 안에 최고가를 되찾았다" if lv else
           f"\n· 지금 {_sgn(x)}% : 1년 최고가에서 10% 안쪽")
    ttip = (f"주가가 최고가에서 크게 떨어졌을 때 그 최고가를 다시 넘기까지 걸린 거래일. '보통' 은 절반이 이보다 빨리 회복한 값" + now)
    return R.dd_block(s["name"], st, sp, "S&P 500", span, d["pct_from_high"], ttip, tail)   # 영역 제목 없이 한 덩이 · 구간 막대 (2026-10-27 P24 · P28)


def related(s):
    """함께 보는 리포트 (가이드라인 10-5 4) — HTML 링크라 검색엔진이 따라간다."""
    links = [("미국 시가총액 상위 10개 종목 주가", U.LIST_URL), ("엔비디아 NVDA 주가", U.NVDA_REPORTS_URL)]
    items = "".join(_dk.dot_li(f'<a href="{_esc(u)}" style="color:#1a73e8;text-decoration:none;">{_esc(t)}</a>', size=3, color="#111", margin="4px 0") for t, u in links)
    # 제목 · 목록 모두 좌측 기준선(ALIGN_PX) — 목록은 점 글머리표(다른 글머리표와 같은 점), 점이 기준선 (2026-10-23 사용자, 2026-10-24 홈 뉴스 선으로)
    return (f'<div data-related="1" style="margin-top:24px;"><div style="font-weight:700;color:#111;font-size:{_dk.EMPH_NAME};padding-left:{_dk.ALIGN_PX}px;">함께 보는 페이지</div>'
            f'<ul style="margin:6px 0 0;padding:0 0 0 {_dk.ALIGN_PX}px;list-style:none;font-size:{_dk.NAME};line-height:{R.LH_CARD};">{items}</ul></div>')


# ---------------------------------------------------------------- 애널리스트 · 탭 셋 (NVDA 리포트 build_body 와 같은 순서 · 같은 카드)

PEER_LABEL = "시총 상위 20개"
MAX_EVENTS = 8      # 뉴스 목록에 펼쳐 두는 수, 나머지는 `그 외 n건`
MAX_ISSUES = 5      # 중요 이슈 줄 수 (10-3 : 7일, 관련도 높은 순 최대 5줄)
MAX_MEDIA = 5       # 방송 줄 최대 수 — 실적 주간엔 한 종목에 하루 십여 줄이라 최근 것만 (2026-10-25)
PICKS = []          # 방송에서 나온 종목 의견 (media_feed.picks, 최근 R.PICK_DAYS 일) — `방송에서 나온 의견은?` 카드 (2026-10-29 P89)
MEDIA = []          # 방송 이슈 (media_feed.issues — 같은 이슈는 이미 한 줄로, 최근 24시간) — write_all 이 한 번 읽는다
TODAY_HOURS = 24    # 뉴스 목록 = 오늘자만 (2026-10-25 사용자). 아침 실행이라 KST 날짜로 자르면 미국 밤사이 뉴스가 빠진다 → 최근 24시간
NOW = None          # 페이지를 만드는 시각 (UTC) — write_all 이 정한다. 목업은 환경 변수 RADAR_NOW(ISO)


def _ts(iso):
    """'2026-10-24T22:15:00Z' · '+00:00' · 날짜만 → 비교용 'YYYY-MM-DDTHH:MM' (UTC)."""
    iso = str(iso or "")
    return iso[:16] if "T" in iso else iso[:10] + "T00:00"


def _since():
    return (NOW - datetime.timedelta(hours=TODAY_HOURS)).strftime("%Y-%m-%dT%H:%M")


def _rename(x, name):
    """NVDA 카드 함수의 글에서 `엔비디아` · `기술주 15개` 를 이 종목 · 비교 묶음으로 — 카드 판정 · 모양은 그대로 쓴다."""
    if isinstance(x, str):
        return x.replace("엔비디아", name).replace("기술주 15개", PEER_LABEL)
    if isinstance(x, (list, tuple)):
        return type(x)(_rename(v, name) for v in x)
    return x


def _sub_head(t):
    return f'<span style="display:block;margin:10px 0 6px;font-weight:700;color:#111;font-size:{_dk.NAME};">{R._esc(t)}</span>'


def card_opinions(s):
    """`애널리스트 · 방송 의견은?` (2026-10-29 사용자 P90) — 애널리스트 의견 · 목표가(옛 sec_targets 흰 카드)와 방송 의견(picks)을 한 상태 카드에, 묶음 둘로.
    머릿수는 합치지 않는다(44명 + 1건 X). 답 = 애널리스트 다수(R.analysts_verdict) — 방송은 건수가 적어 답을 좌우하지 않는다. 애널리스트가 없으면 방송만으로 `매수` 등.
    색은 회색(남의 의견 — 블로그 추천 아님, 매수 추천 금지 원칙). 둘 다 없으면 카드 없음."""
    a = {"status": {"analysts": s.get("analysts") or []}, "headline": {"close": s.get("close")}}
    verdict = R.analysts_verdict(a) if s.get("analysts") else None
    ps = [p for p in PICKS if p["market"] == "US" and p["ticker"] == s["sym"]]
    if not verdict and not ps:
        return ""
    money = lambda v: f"${v:,.2f}"   # noqa: E731
    cnt = R.picks_count(ps) if ps else ""
    if verdict:
        state, text = verdict
        text += f" 방송에서는 {R.picks_sentence(ps)} 나왔다." if ps else ""
    else:
        state = " · ".join(dict.fromkeys(p["action"] for p in ps))
        text = f"{s['name']}에 대한 {R.picks_sentence(ps)} 방송에서 나왔다. 애널리스트 집계는 없다."
    lines = [(text, "plain")]   # `블로그 의견 아님` 안내는 뺐다 (P92)
    if verdict:
        lines.append((R.analysts_block(a), "html"))   # 묶음 제목은 안쪽 `애널리스트 N명 의견` 막대 제목이 대신한다
    if ps:
        lines.append((R.picks_rows(ps, s.get("close"), money), "html"))   # 방송 묶음은 `매수 의견` 제목 · 구분선 (P92)
    tip = ("애널리스트(Yahoo Finance 집계)의 등급 분포 · 평균 등급 · 목표가와, 방송(유튜브 경제 채널) 요약에서 나온 이 종목 의견을 한 카드에 모은 것\n"
           f"· 지금 : {state}" + (f" · 방송 {cnt}" if ps else "") + "\n"
           "· 나누는 법 : 애널리스트 중 매수(강매수 포함)가 절반 넘으면 매수, 보유가 절반 넘으면 보유, 매도 쪽이 절반 넘으면 매도, 아니면 엇갈림. 방송 건수는 답에 넣지 않는다\n"
           "· 읽는 법 : 누가 어떤 이유로 말했는지 보는 칸이다. 적중률은 검증하지 않았고, 이 블로그의 추천이 아니다")
    theme, col = R.pick_theme(state)   # 매수면 오름 색 강조 카드 (P92)
    return R._state_card("애널리스트 · 방송 의견은?", state, theme, col, lines, "", tip=_dk.with_src(tip, "Yahoo Finance · 유튜브 방송 요약"), fold=True)


def sec_targets(s):
    """옛 애널리스트 흰 카드 — card_opinions 로 합쳐 비운다 (P90)."""
    return ""


def _news_for(s, news):
    """이 종목 점수가 있는 분류된 기사 → NVDA 이벤트 모양. 관련도 1 이상, 7일 (목록은 _today_list 가 24시간으로 자른다)."""
    cut = (datetime.date.fromisoformat(s["day"]) - datetime.timedelta(days=7)).isoformat()
    out, counted = [], []
    for x in news.values():
        sc = next((c for c in x.get("scores") or [] if c["ticker"] == s["sym"]), None)
        if not sc or x["published_at"][:10] < cut:
            continue
        counted.append((x, sc))
        prio = x["area"] in R.config.PRIORITY_AREAS
        if not x.get("fact"):
            continue   # 사실 문장 검사에서 두 번 탈락한 기사 = 영문 원제를 그대로 싣게 되므로 뺀다. 방향 집계(counted)에는 남는다 (2026-10-21, 운영지침 D3-1f)
        if sc["relevance"] >= 1:   # 목록이 오늘자만이 된 뒤로 관련도 1(업종 맥락)도 싣는다 — `오늘 n건` 막대와 목록 기사 수를 맞춘다 (2026-10-25). 중요 이슈는 아래에서 2 이상만
            out.append({"area": x["area"], "kind": "news", "title": x["title"], "fact": x["fact"], "headline": news_store.headline(x), "detail": news_store.summary(x),   # 목록 헤드라인 = 원제 번역 · 요약 줄 (공용 뉴스 처리, 2026-10-25). 중요 이슈는 fact 그대로
                        "has_fact": True, "url": x.get("url"), "direction": sc["direction"],
                        "emphasis": sc["relevance"] >= 3 or prio, "source": x.get("source"), "published_at": x["published_at"], "rel": sc["relevance"], "prio": prio})
    for f in s.get("filings") or []:   # SEC 공시 — NVDA 리포트처럼 기사와 같은 목록에 (제목은 파이썬 규칙, AI 없음)
        if f["filed"] >= cut:
            out.append({"area": f["area"], "kind": "form4" if f["form"] == "4" else "8k", "title": f["title"], "fact": f["title"], "url": f["url"],
                        "direction": f["direction"], "emphasis": f["emphasis"], "source": "edgar", "published_at": f["at"], "rel": 0, "prio": False, "has_fact": False})
    out.sort(key=lambda e: e["published_at"], reverse=True)
    out.sort(key=lambda e: (not e["prio"], not e["emphasis"]))
    return out, counted


def _today_list(s, events):
    """뉴스 목록 = 최근 24시간 기사 · 공시 + 방송 줄. 방송 = 이 종목이 중심인 이슈 + 이 종목이 속한 업종 이슈 (media_feed.for_page, 2026-10-25 사용자).
    방송 줄은 중요 이슈에는 넣지 않는다 (의견 섞임). 정렬은 _news_for 그대로(법무 · 규제 → 강조 → 최근)."""
    since = _since()
    media = sorted(media_feed.for_page(MEDIA, s["sym"]), key=lambda r: str(r["published_at"]), reverse=True)[:MAX_MEDIA]   # MEDIA = 정리된 이슈(같은 이슈는 한 줄)
    today = [e for e in events if _ts(e["published_at"]) >= since] + [media_feed.event(r) for r in media]
    today.sort(key=lambda e: _ts(e["published_at"]), reverse=True)
    today.sort(key=lambda e: (not e["prio"], not e["emphasis"]))
    return today


def sec_today_tab(s, news):
    """오늘 탭 — 중요 이슈(파이썬 틀 : 관련도 높은 사실 문장 최대 5줄) · 뉴스(방향 막대 + 기사). AI 는 분류에만 쓴다."""
    if not news:   # 오늘 탭은 늘 둔다 — 없으면 가격 카드 · 상태 카드가 다음 탭(실적과 기대)으로 들어간다
        note = _dk.muted("뉴스를 아직 받지 못했습니다. 다음 갱신 때 채웁니다.")
        return R._section("중요 이슈", note, tab="오늘") + R._section("뉴스", "", line=False, tab="오늘")
    events, counted = _news_for(s, news)
    since = _since()
    dc = {"today": {}, "week": {}}
    for x, sc in counted:
        if sc["relevance"] < 1:
            continue
        dc["week"][sc["direction"]] = dc["week"].get(sc["direction"], 0) + 1
        if _ts(x["published_at"]) >= since:   # `오늘` 막대 = 목록과 같은 최근 24시간 (2026-10-25)
            dc["today"][sc["direction"]] = dc["today"].get(sc["direction"], 0) + 1
    top = sorted((e for e in events if e["rel"] >= 2 and e["has_fact"]), key=lambda e: e["published_at"], reverse=True)
    top = sorted(top, key=lambda e: -e["rel"])[:MAX_ISSUES]   # 관련도 높은 순, 같으면 최근 순
    issues = [(f"{R.rr.AREA_KO.get(e['area'], e['area'])} {_dk.headline(e['fact'])}", e.get("url")) for e in top if e["has_fact"]]   # (글, 기사 주소) — 줄을 누르면 그 기사가 열린다 (2026-10-23 사용자)   # 명사형 헤드라인체 (데일리 · NVDA 중요 이슈와 같게)
    today = _today_list(s, events)
    a = {"events": today[:MAX_EVENTS], "events_overflow": today[MAX_EVENTS:MAX_EVENTS + 12], "direction_counts": dc}
    issue_html = R.sec_narrative(a, {"today": issues}) if issues else _dk.muted("최근 7일 동안 이 종목을 주로 다룬 큰 소식이 없습니다.")
    return _dk.keep_tone(R._section("중요 이슈", issue_html, tab="오늘")   # 뉴스 · 중요 이슈는 합니다체로 바꾸지 않는다 (2026-10-18 사용자)
                         + R._section("뉴스", R.sec_direction_bars(a) + (R.sec_events(a) if today else _dk.muted("오늘은 새 뉴스가 없습니다.")), line=False, tab="오늘"))


def _bil(v):
    """달러 → `1,234억 달러` (음수는 −). None 이면 `미수집` — 0 으로 적지 않는다 (운영지침, 2026-10-30)."""
    if v is None:
        return "미수집"
    return f"{v / 1e8:,.0f}억 달러".replace("-", "−")


def card_capex(c):
    """돈을 어디에 쓰나? (2026-10-30 사용자: 기업별 자본 지출 · 자금 조달 현황) — 사실만, 판단 문장 없음. 출처 = 그 분기 10-Q · 10-K 색인 링크.
    첫 문장 = 최근 분기 설비 투자 · 1년 전 대비 · 영업으로 번 돈 대비 · 연구개발비. 그래프 = 8분기 설비 투자 vs 영업으로 번 돈(억 달러). 줄 = 최근 4분기 합."""
    cap, ocf, rnd = c.get("capex"), c.get("ocf"), c.get("rnd")
    if cap is None:   # 은행 · 보험처럼 설비 투자 줄이 따로 없는 회사
        first = f"최근 분기({R._fd(c['end'])}까지 석 달) 현금흐름표에 설비 투자 항목이 따로 없다(은행 · 보험처럼 영업 자산이 다른 회사). 영업으로 번 돈은 {_bil(ocf)}였다."
    else:
        first = f"최근 분기({R._fd(c['end'])}까지 석 달) 설비 투자는 {_bil(cap)}"
        first += f"로 1년 전보다 {abs(c['capex_yoy']):.0f}% {'늘었다' if c['capex_yoy'] >= 0 else '줄었다'}." if c.get("capex_yoy") is not None else "다."
    if cap is not None and ocf:
        first += f" 같은 석 달 영업으로 번 돈 {_bil(ocf)}의 {cap / ocf * 100:.0f}%였다." if ocf > 0 else f" 같은 석 달 영업으로 번 돈은 {_bil(ocf)}였다."
    if rnd is not None:
        first += f" 연구개발비는 {_bil(rnd)}다."
    groups = [(_dk.q_axis(b["cq"]), [None if b["capex"] is None else b["capex"] / 1e8, None if b["ocf"] is None else b["ocf"] / 1e8]) for b in c["bars"][::-1]]   # 최신이 왼쪽 (P79)
    chart = R._chart_card(groups, [lambda v: R._AMBER, R._gray], [R._note_fg, R._note_fg], [("설비 투자", R._AMBER), ("영업으로 번 돈", R._GRAY_BAR)],
                          fmt=lambda v: f"{v:,.0f}".replace("-", "−"))
    lines = [(first, "plain"), (f'{_dk.CHART_TITLE_M}분기 설비 투자와 영업으로 번 돈 (억 달러)</span>{chart}', "html")]
    sm, n4 = c["sum4"], c["n4"]
    tag = f"최근 {n4}분기 합" if n4 == 4 else "최근 4분기 없음"
    if sm.get("capex") is not None:
        note = tag + (f" · 그 전 4분기보다 {R._sgn(c['chg4'], 0)}%" if c.get("chg4") is not None else "")
        if sm.get("ocf"):
            note += f" · 영업으로 번 돈의 {sm['capex'] / sm['ocf'] * 100:.0f}%"
        lines.append(("row", "설비 투자", _bil(sm["capex"]), note))
    else:
        lines.append(("row", "설비 투자", "미수집", "회사가 이 항목을 따로 적지 않았다"))
    lines.append(("row", "연구개발비", _bil(sm.get("rnd")), tag if sm.get("rnd") is not None else "회사가 이 항목을 따로 적지 않았다"))
    if sm.get("debt_in") is not None or sm.get("debt_out") is not None:
        lines.append(("row", "빌린 돈 (채권 · 차입)", _bil(sm.get("debt_in")), tag + (f" · 갚은 돈 {_bil(sm['debt_out'])}" if sm.get("debt_out") is not None else "")))
    else:
        lines.append(("row", "빌린 돈 (채권 · 차입)", "미수집", "이 기간 발행 · 상환을 따로 적지 않았다"))
    if sm.get("stock_in") and sm["stock_in"] > 0:   # 음수(세금 원천징수 차감 등)는 안 보인다
        lines.append(("row", "주식 발행으로 들어온 돈", _bil(sm["stock_in"]), tag))
    lines.append(("row", "자사주 매입", _bil(sm.get("buyback")), tag if sm.get("buyback") is not None else "이 기간 매입을 따로 적지 않았다"))
    lines.append(("row", "배당", _bil(sm.get("div")), tag if sm.get("div") is not None else "이 기간 배당을 따로 적지 않았다"))
    if sm.get("lease"):
        lines.append(("row", "금융리스 상환", _bil(sm["lease"]), tag + " · 리스로 들여온 설비의 원금"))
    if c.get("cash") is not None:
        lines.append(("row", "현금", _bil(c["cash"]), f"{R._fd(c['end'])} 기준"))
    if c.get("debt") is not None:
        lines.append(("row", "장기 부채", _bil(c["debt"]), f"{R._fd(c['end'])} 기준"))
    if c.get("src"):
        lines.append(("row", "출처", f'<a href="{_esc(c["src"])}" target="_blank" rel="noopener" style="color:inherit;">SEC {_esc(c.get("form") or "10-Q")} ›</a>', "회사가 SEC 에 낸 분기 · 연간 보고서", True))
    tip = ("회사가 번 돈을 어디에 쓰고, 모자란 돈을 어떻게 끌어오는지 — 회사가 SEC 에 낸 현금흐름표 그대로\n"
           "· 설비 투자 : 데이터 센터 · 공장 · 장비처럼 오래 쓰는 자산을 사는 데 쓴 돈(자본 지출). 리스로 들여온 설비는 여기에 안 들어가 `금융리스 상환` 줄을 따로 둔다\n"
           "· 늘리는 중 · 줄이는 중 : 최근 4분기 합이 그 전 4분기 합보다 10% 넘게 많으면 늘리는 중, 10% 넘게 적으면 줄이는 중 — 분기 값은 들쭉날쭉해 합으로 본다\n"
           "· 참고 : 회사마다 회계 분기가 달라 다른 회사와 같은 달력 분기가 아닐 수 있다. 항목 이름이 달라 못 읽은 것은 `미수집`으로 두고 0 으로 적지 않는다")
    return lines, _dk.with_src(tip, "SEC EDGAR")


def sec_expect(s):
    """실적과 기대 탭 — NVDA 리포트 sec_expect 와 같은 질문 카드 넷 + 돈을 어디에 쓰나(2026-10-30). 비교 묶음 = 시총 상위 20개 (중앙값)."""
    ex = s.get("expect") or {}
    spec = [("회사는 돈을 더 벌고 있나?", "revenue", R.card_revenue), ("애널리스트 전망은?", "eps", R.card_eps),
            ("시장 예상 흔들림은?", "move", R.card_move), ("하락에 거는 돈은?", "short", R.card_short), ("돈을 어디에 쓰나?", "capex", card_capex)]
    out = ""
    for i, (title, key, fn) in enumerate(spec):
        c = ex.get(key)
        if key == "capex" and not c:   # 외국 회사(TSM · ASML, 20-F) · 은행처럼 표가 없는 회사는 카드 자체를 안 둔다 — '다음 실행에서 다시' 가 아니다
            continue
        if c:
            lines, tip = _rename(fn(c), s["name"])
            state = c["state"]
        else:
            lines, tip, state = [("이번 실행에서 재료를 받지 못했다. 다음 실행에서 다시 받는다.", "plain")], "", "판단 유보"
        lines = list(lines)
        if key == "move" and s.get("options_status"):   # 옛 시장 지표 탭의 옵션 칸 — NVDA sec_expect 와 같은 `자세한 지표 보기`
            a = {"status": s["options_status"]}
            lines.append((R._detail_fold(R._status_group(a, "options")), "html"))
        theme, col = R.EXPECT_THEME.get(state, ("neutral", R.MUTED))
        out += R._state_card(title, state, theme, col, lines, "", tip=tip, fold=True, opened=i == 0)
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>'


WHEN_KO = {"bmo": "장 시작 전", "amc": "장 마감 뒤"}


def cal_earnings(s, c):
    """NVDA cal_earnings 그대로 + 발표 시각 · 날짜 출처만 이 종목 값으로 (확정 · 추정 구분이 없는 Yahoo 일정)."""
    lines, tip, state, left = R.cal_earnings(dict(c, confirmed=True))
    when = WHEN_KO.get(c.get("when"))

    def fix(x):
        x = _rename(x, s["name"])
        if isinstance(x, str):
            x = x.replace("장 마감 뒤 · 회사 확정", (when + " · " if when else "") + "Yahoo Finance 일정")
            x = x.replace(" 장 마감 뒤로,", f" {when}로," if when else ",")
        return x
    return [tuple(fix(v) for v in ln) for ln in lines], fix(tip), state, left


ROLE_ORDER = ("고객", "공급", "협력", "경쟁", "동종", "유통", "보유")   # 동종 · 유통 : 2026-10-20 추가 종목 (같은 업종 회사 · 파는 곳)


def cal_peers(s, c):
    """함께 보는 회사 실적 — NVDA cal_peers 와 같은 비교(그 회사 발표 다음 날 이 종목 vs 이 종목 보통 날), 회사 목록은 종목마다 정한 것(universe.PEERS)."""
    up, nm, roles = c["upcoming"], s["name"], c["roles"]
    kinds = " · ".join(r for r in ROLE_ORDER if r in roles.values())
    what = "큰 보유 종목" if kinds == "보유" else f"{kinds} 회사"
    if not up:
        return [(f"앞으로 30일 안에 실적을 발표하는 {nm}의 {what}가 없다.", "plain")], "", "없음", None
    names = [f"{U.peer_name(u['symbol'])}({R._md_short(u['day'])})" for u in up]
    syms = [x for x in dict.fromkeys(u["symbol"] for u in up) if c["effect"].get(x, {}).get("median")]
    soon = " · ".join(r for r in ROLE_ORDER if r in {roles.get(u["symbol"]) for u in up})   # 30일 안에 발표하는 회사의 관계만
    first = f"앞으로 30일 안에 {' · '.join(names)}가 실적을 발표한다. {nm}의 {'큰 보유 종목' if soon == '보유' else soon + ' 회사'}다."
    if syms:
        eff = [c["effect"][x]["median"] for x in syms]
        rng = f"±{min(eff):.1f}%" if f"{min(eff):.1f}" == f"{max(eff):.1f}" else f"±{min(eff):.1f}~{max(eff):.1f}%"
        who = "이 회사들의" if len(syms) > 1 else "이 회사의"
        first += f" 최근 2년 {who} 발표 다음 날 {nm} 주가는 보통 {rng} 움직였다({nm} 보통 날 ±{c['normal']:.1f}%)."
    lines = [(first, "plain")]
    if syms:
        chart = R._chart_card([(U.peer_name(x), [c["effect"][x]["median"], c["normal"]]) for x in syms], [lambda v: R._AMBER, R._gray], [R._note_fg, R._note_fg],
                              [(f"그 회사 발표 다음 날 {nm}", R._AMBER), (f"{nm} 보통 날", R._GRAY_BAR)], fmt=lambda v: f"±{v:.1f}")
        lines.append((f'{_dk.CHART_TITLE_M}발표 다음 날 {_esc(nm)} 움직임 (%)</span>{chart}', "html"))
    for u in up:
        e = c["effect"].get(u["symbol"]) or {}
        lines.append(("row", f"{U.peer_name(u['symbol'])} ({u['symbol']})", R._md_short(u["day"]),
                      roles.get(u["symbol"], "") + (f" · 다음 날 {nm} 보통 ±{e['median']:.1f}% ({e['n']}번)" if e.get("median") else "")))
    left = (datetime.date.fromisoformat(up[0]["day"]) - datetime.date.fromisoformat(s["day"])).days
    listed = " · ".join(f"{U.peer_name(x)}({r})" for x, r in roles.items())
    tip = (f"{nm}와(과) 사업으로 이어진 회사({listed})의 실적 발표. 이 회사들의 실적 소식에 {nm} 주가도 함께 움직이곤 한다\n"
           f"· 30일 안 {len(up)}곳 : 가장 가까운 발표는 {U.peer_name(up[0]['symbol'])} {R._md_short(up[0]['day'])}\n"
           "· 참고 : 최근 2년, 회사마다 8번 안팎이라 숫자는 대략으로 본다")
    return lines, tip, f"{len(up)}곳 · 30일 안", left


def _all_list(s, items):
    kinds = dict(R.rr.KIND_KO, EARNINGS=f"{s['name']} 실적", EARNINGS_PEER="함께 보는 회사 실적")
    d0 = datetime.date.fromisoformat(s["day"])
    rows = [(f'<span style="color:#111;">{_esc(R._d(c["day"]))}</span>', R._pill(kinds.get(c["kind"], c["kind"]), "area"),
             f'<span style="color:#111;">{_esc(c["label"])}</span>', "", f'<span style="color:#111;">{R._dn(d0, c["day"])}</span>') for c in items]
    return R._gcard(rows) if rows else _dk.muted("잡힌 일정이 없습니다.")


def sec_calendar(s):
    """캘린더 탭 — NVDA 리포트 sec_calendar 와 같은 질문 카드(실적 · 같은 업종 실적 · 시장 일정). 소송 카드는 없다(추적하는 사건이 없다)."""
    cc = s.get("calendar_cards") or {}
    specs = [("다음 실적 발표는?", "earnings", lambda c: cal_earnings(s, c)), ("함께 보는 회사 실적은?", "peers", lambda c: cal_peers(s, c)),
             ("시장 전체를 흔들 일정은?", "macro", R.cal_macro)]
    out, first = "", True
    for title, key, fn in specs:
        c = cc.get(key)
        if not c:
            continue
        lines, tip, state, extra = fn(c)
        theme, col = R._soon_theme(extra)
        out += R._state_card(_josa(title), state, theme, col, lines, "", tip=_josa(tip), fold=True, opened=first)
        first = False
    fold = (f'<details data-fold="1" data-label="전체 일정 보기"><summary style="list-style:none;cursor:pointer;">{R._fold_row("전체 일정 보기")}</summary>'
            f'<div style="margin-top:6px;">{_all_list(s, cc.get("all") or [])}</div></details>')
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>' + fold


def _josa(t):
    """`○○와(과)` → 받침에 맞는 조사 하나 (이름 끝 글자 기준, 영문 · 숫자는 `와`)."""
    def pick(m):
        ch = m.group(1)
        has = "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 != 0
        return ch + ("과" if has else "와")
    return re.sub(r"(.)와\(과\)", pick, t)


def detail_body(s, today, news=None):
    """NVDA 리포트 순서 : 맨 위 요약 → 그래프 → 가격 카드(펼치면 1층 · 2층) → 상태 카드. 갱신 날짜 줄은 뺐다 — 요약 첫 마디에 날짜가 있다 (2026-10-18 사용자)."""
    return wrap(lead(s) + sec_chart(s) + R.day_path_chart(s["tech"].get("path"), s["tech"].get("bench_path"), s["name"], "S&P 500") + price_card(s, today) + sec_tech(s) + sec_states(s) + sec_targets(s)
                + sec_today_tab(s, news or {})
                + R._section("실적", sec_expect(s), tab="실적")
                + R._section("캘린더", sec_calendar(s), tab="캘린더")
                + related(s) + list_marker(U.LIST_URL))   # 출처 · 투자 권유 꼬리말은 뺐다 — 블로그 공통 푸터가 맡는다 (2026-10-18 사용자)


# ---------------------------------------------------------------- 목록

def list_lead(a):
    top = [s for s in a["stocks"] if s["in_top"]]
    up = sum(1 for s in top if s["ret_1d"] > 0)
    first = top[0]
    text = (f"{_md(a['day'])} 종가 기준 미국 시가총액 1위는 {first['name']}({first['sym']}), {cap_text(first['cap'])}이다. "
            f"상위 10개 중 {up}개가 오르고 {len(top) - up}개가 내렸다.")
    return f'<p data-seo-lead="1" style="{_dk.SEO_LEAD}">{_esc(text)}</p>'


def detail_url(s):
    return U.NVDA_REPORTS_URL if s["sym"] in U.REPORT_TYPE else U.page_url(s["sym"])


def list_row(s, first):
    r = s["ret_1d"]
    pcol = UP if r > 0 else DOWN if r < 0 else "#111"
    left = (f'<span style="display:inline-block;width:26px;color:{NOTE};font-weight:700;">{s["rank"]}</span>{_dk.ticker_logo(s["sym"])}'
            f'<a href="{_esc(detail_url(s))}" style="color:#111;text-decoration:none;">{_esc(s["name"])}</a>'
            f'<span style="display:block;padding-left:52px;font-size:{_dk.MICRO};line-height:20px;font-weight:400;color:{NOTE};">{_esc(s["sym"])} · {cap_text(s["cap"])}</span>')   # 순위 26 + 로고 26 만큼 들여 이름 글자에 맞춘다
    right = f'<span style="color:{pcol};">${s["close"]:,.2f}</span><br>{R._arrow(r)}'
    # 줄 전체가 상세로 가는 터치 영역 — 테마 터치 장치가 [data-row-link] 를 읽는다 (2026-10-19 사용자: 이름만이 아니라 한 행을 터치)
    return R._row_html(left, right, first=first).replace("<span", f'<span data-row-link="1" data-ret="{r:.4f}"', 1)


def list_body(a):
    top = [s for s in a["stocks"] if s["in_top"]]
    rest = [s for s in a["stocks"] if not s["in_top"] and s.get("rank") and s["rank"] <= U.PEER_GROUP_N]   # 목록은 시총 상위 20위까지 — 48개 확대 뒤에도 같은 목록 (2026-10-20)
    card = lambda xs, key="": f'<div data-cards="1" style="margin:0 0 8px;"><span{f" data-sort-list={chr(34)}{key}{chr(34)}" if key else ""} style="{R.MULTI}">{"".join(list_row(s, i == 0) for i, s in enumerate(xs))}</span></div>'   # noqa: E731   key = 정렬 버튼이 다시 놓는 목록 (P93)
    tip = ("미국 S&P 500 종목 가운데 회사 전체 값(주가 × 주식 수)이 가장 큰 10개\n"
           f"· 오늘 1위 : {top[0]['name']} {cap_text(top[0]['cap'])}\n"
           f"· 나누는 법 : 11위 밖으로 {U.SWAP_DAYS}거래일 연속 밀리면 후보 중 가장 높았던 종목과 바꾼다")
    body = (list_lead(a) + updated_line(a) + R.title_with_sort("시가총액 순위", tip, "us-cap10") + card(top, "us-cap10")
            + _dk.fold(f"후보 11~{len(top) + len(rest)}위 보기", card(rest))
            + _dk.muted("종목 이름을 누르면 상세 페이지로 갑니다. 엔비디아는 매일 나오는 리포트로 갑니다."))
    return wrap(body + home_marker())


def write_all(a, out_dir, snap=None, news=None, media=None):
    os.makedirs(out_dir, exist_ok=True)
    global MEDIA, NOW
    NOW = (datetime.datetime.fromisoformat(os.environ["RADAR_NOW"].replace("Z", "+00:00")) if os.environ.get("RADAR_NOW")
           else datetime.datetime.now(datetime.timezone.utc))
    global PICKS
    if media is None:   # 영상은 한 번(30일) 읽어 뉴스(24시간) · 방송 의견(30일)에 나눠 쓴다 — Firestore `in` 30개 한도
        vids = media_feed.load(NOW.astimezone(media_feed.KST).strftime("%Y-%m-%d"), days=R.PICK_DAYS - 1)
        media = media_feed.issues(media_feed.rows(vids), _since())
        PICKS = media_feed.picks(vids, (NOW - datetime.timedelta(days=R.PICK_DAYS)).strftime("%Y-%m-%d"))
    MEDIA = media
    if snap:
        draw_charts(snap, [s for s in a["stocks"] if s["sym"] not in U.REPORT_TYPE], out_dir)
    pages = {"list": (U.LIST_TITLE, list_body(a))}
    for s in a["stocks"]:
        if s["sym"] not in U.REPORT_TYPE:
            pages[s["sym"]] = (U.page_title(s["sym"]), detail_body(s, a["day"], news))
    for key, (title, body) in pages.items():
        with open(os.path.join(out_dir, f"{key}.html"), "w", encoding="utf-8") as f:
            f.write(body)
        _dk.write_mock(body, os.path.join(out_dir, f"mock_{key}.html"), title)
    return pages
