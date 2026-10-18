"""시총 TOP 10 목록 페이지 · 간단형 상세 페이지 HTML (doc/종목-레이더-기획.md 10-3 · 10-10, 1단계 = 숫자와 실적일만).

카드 모양은 엔비디아 리포트 가격 카드 펼침(가이드라인 2-4 11-1)과 같게 — 그 렌더러의 작은 조각(_row · _row_html · _col_chart …)을 그대로 쓴다.
툴팁은 뜻 · 오늘 · 참고 세 줄(2-6). 이 종목들은 우리 검증을 하지 않았으므로 `기록상` 줄을 두지 않는다(지표 검증 대원칙: 종목마다 따로).
"""

import datetime
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "nvda-report"))

import design_kit as _dk  # noqa: E402
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
    return _dk.fix_colons(_dk.WRAP_OPEN + body + _dk.WRAP_CLOSE)


def foot():
    return _dk.footer("가격 · 시가총액 · 실적 발표일 : Yahoo Finance 일봉, 하루 한 번 장 마감 뒤 갱신",
                      "이 페이지는 사실 기록이며 투자 권유가 아닙니다.")


def button(label, url):
    return (f'<a href="{_esc(url)}" style="{_dk.FOLD_BTN}text-decoration:none;margin:20px 0 8px;">{_esc(label)}</a>')


# ---------------------------------------------------------------- 상세 (간단형)

def lead(s):
    """맨 위 요약 1~2문장 (p[data-seo-lead], 가이드라인 10-5) — 날마다 달라지는 글. 파이썬 값만, 평가 · 예측 없음."""
    r = s["ret_1d"]
    move = f"전날보다 {abs(r):.2f}% {'올랐다' if r > 0 else '내렸다'}" if abs(r) >= 0.005 else "전날과 같았다"
    first = f"{_md(s['day'])} {s['name']}({s['sym']}) 종가는 ${s['close']:,.2f}로 {move}."
    nr = s.get("normal_range")
    if nr:
        first += (" 실적 발표에 처음 반응한 날이었다." if nr["earnings_day"] else
                  " 평소 하루 움직임 안의 변화였다." if abs(nr["z"]) < 2 else f" 평소 하루 움직임의 {abs(nr['z']):.1f}배였다.")
    more = []
    if s.get("rank"):
        more.append(f"시가총액은 미국 {s['rank']}위({cap_text(s['cap'])})")
    nxt = (s.get("earnings") or {}).get("next")
    if nxt:
        more.append(f"다음 실적 발표는 {_md(nxt)} 예정")
    text = first + (" " + "이고, ".join(more) + "이다." if more else "")
    return f'<p data-seo-lead="1" style="font-size:{_dk.NAME};line-height:{R.LH_CARD};color:#333;margin:0 0 12px;word-break:keep-all;">{_esc(text)}</p>'


def range_tip(s):
    nr = s["normal_range"]
    k = abs(nr["z"])
    now = (f"· 오늘 {_sgn(s['ret_1d'])}% : 실적 발표에 반응한 날이라 평소 범위로 재지 않는다" if nr["earnings_day"] else
           f"· 오늘 {_sgn(s['ret_1d'])}% : 평소 하루 움직임(±{nr['sigma_pct']:.1f}%)의 {k:.1f}배" + (", 평소 범위 안" if k < 2 else ", 평소 범위 밖"))
    return ("최근 움직임으로 잰 이 종목의 보통 하루 등락 폭. 그 2배를 넘으면 평소 범위 밖으로 본다\n" + now +
            "\n· 참고 : 크게 움직였다는 사실만 말한다. 오르내림의 방향은 말하지 않는다")


def price_card(s):
    r = s["ret_1d"]
    pcol = UP if r > 0 else DOWN if r < 0 else "#111"
    tone = _dk.ROW_UP if r > 0 else _dk.ROW_DOWN if r < 0 else ""
    price = f'<span style="color:{pcol};font-weight:700;">${s["close"]:,.2f}</span>&nbsp;{R._arrow(r)}'
    head = R._row(s["sym"], price, tone)
    nr = s.get("normal_range")
    if nr:
        k = abs(nr["z"])
        txt = (f"실적 발표 반응일 · 평소의 {k:.1f}배" if nr["earnings_day"] else
               ("평소 범위 안" + (f" · 평소의 {k:.1f}배" if k >= 1 else "")) if k < 2 else f"평소 범위 밖 · 평소의 {k:.1f}배")
        txt += f" (평소 하루 ±{nr['sigma_pct']:.1f}%)"
        if s.get("vol_ratio") and s["vol_ratio"] >= 1.5:
            txt += f" · 거래량 평소의 {s['vol_ratio']:.1f}배"
        sub = (f'<span style="flex:0 0 100%;min-width:0;display:block;text-align:right;margin-top:3px;font-size:{TINY};line-height:20px;color:{NOTE};'
               f'font-weight:400;white-space:normal;word-break:keep-all;">{R._tipx(range_tip(s))}{_esc(txt)}</span>')
        head = head.replace("display:flex;", "display:flex;flex-wrap:wrap;", 1).replace("gap:12px;", "column-gap:12px;row-gap:2px;", 1)
        k2 = head.rstrip().rfind("</span>")
        head = head[:k2] + sub + head[k2:]
    return f'<div data-cards="1">{head}</div>'


def periods_tip(s, ps):
    p = ps[-1]
    now = ""
    if p.get("spy") is not None:
        d = p["stock"] - p["spy"]
        now = (f"\n· {p['label']} {_sgn(p['stock'])}% : 같은 기간 S&P 500({_sgn(p['spy'])}%)보다 "
               + (f"{abs(d):.1f}%p 앞섰다" if d > 0 else f"{abs(d):.1f}%p 뒤처졌다" if d < 0 else "같았다"))
    return "지금 가격이 1주 · 1개월 · 3개월 · 6개월 · 1년 전보다 얼마나 오르거나 내렸는지. 배당을 넣어 계산했다" + now + "\n· 참고 : 지난 수익률이라 앞으로를 말하지 않는다"


def sec_periods(s):
    ps = s.get("periods") or []
    if not ps:
        return ""
    chart = R._col_chart([(p["label"], [p["stock"], p.get("spy")]) for p in ps], [R._sign_bg, lambda v: R._GRAY_BAR], [R._sign_fg, lambda v: NOTE])
    legend = R._legend_chips([(f"{s['name']} 오름", R._PASTEL_UP), (f"{s['name']} 내림", R._PASTEL_DN), ("S&P 500", R._GRAY_BAR)])
    card = f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}"><span style="display:block;padding:{PAD + 6}px 12px 0;">{chart}{legend}</span></span></div>'
    return R._card_title("기간별 수익률 (%)", periods_tip(s, ps)) + card


def year_tip(y):
    pct = y["pct_from_high"]
    where = "1년 최고가 근처" if pct > -0.5 else f"1년 최고가보다 {abs(pct):.1f}% 아래"
    return ("지난 1년 동안 가장 쌌던 값과 가장 비쌌던 값 사이에서 지금 어디쯤인지\n"
            f"· 오늘 ${y['close']:,.2f} : {where}, 범위의 {max(0.0, min(100.0, y['pos_pct'])):.0f}% 지점\n"
            "· 참고 : 범위 안의 위치일 뿐, 오를지 내릴지를 말하지 않는다")


def sec_year_range(s):
    y = s.get("year_range")
    if not y:
        return ""
    return R.sec_year_range({"year_range": y}).replace(R._tipx(R.year_tip(y)), R._tipx(year_tip(y)), 1)


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
        chart = R._col_chart([(f"{m['day'][2:4]}.{m['day'][5:7]}", [m["ret"]]) for m in e["moves"]], [R._sign_bg], [R._sign_fg], height=130)
        rows += (f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px 0;">'
                 f'<span style="display:block;font-weight:700;color:#111;font-size:{_dk.NAME};">최근 {n}번의 실적 발표 다음 날 (%)</span>'
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
             ("row", f"{sf['name']} vs 시장 ({n}일)", f"{_sgn(rel)}%p", f"+{pp:.0f}%p 넘으면 유입 · −{pp:.0f}%p 아래면 유출"),
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


def sec_states(s):
    """상태 카드 — NVDA 리포트와 같은 카드 · 규칙. 업종 카드만 종목의 업종 ETF 로. 시장 충격 · 한 달 범위 · 과열은 해당하는 날만."""
    out = ""
    ms = s.get("market_shock") or {}
    if ms.get("active"):
        out += R._state_card("시장 충격 국면은?", "충격 국면 중", "uncertain", R.WARN, R.shock_lines(ms), "", tip=_no_record(R.shock_tip(ms)), fold=True)
    mr = s.get("market_regime")
    if mr:
        th, col = R.REGIME_THEME.get(mr["regime"], ("neutral", R.MUTED))
        out += R._state_card("시장 분위기는?", mr["regime"], th, col, R.regime_lines(mr), "", tip=R.regime_rule(mr), fold=True)
    sf = s.get("sector_flow")
    if sf:
        th, col = R.FLOW_THEME.get(sf["state"], ("neutral", R.MUTED))
        title = "반도체로 돈이 올까?" if sf["name"] == "반도체" else f"{sf['name']} 업종으로 돈이 올까?"
        out += R._state_card(title, sf["state"], th, col, sector_lines(sf), "", tip=sector_rule(sf), fold=True)
    bb = s.get("bollinger")
    if bb and bb["state"] in R.BOLL_THEME:
        th, col = R.BOLL_THEME[bb["state"]]
        out += R._state_card("한 달간 변화 범위는?", {"하단 도달": "하락 범위에 닿음", "상단 도달": "상승 범위에 닿음"}[bb["state"]], th, col,
                             R.bollinger_lines(bb), "", tip=R.bollinger_rule(bb), fold=True, inline_notes=True)
    oh = s.get("overheat")
    if oh and oh["active"]:
        out += R._state_card("과열 신호는?", f"{len(oh['active'])}개 조건 해당", "neutral", R.MUTED, R.overheat_lines(oh), "", tip=_no_record(R.overheat_rule(oh)))
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>' if out else ""


def sec_volume(s):
    vr = s.get("vol_ratio")
    v = f'<span style="font-weight:700;">{vr:.1f}배</span>' if vr else f'<span style="color:{R.MUTED};">—</span>'
    return f'<div data-cards="1" style="margin:0 0 8px;">{R._multi_single([("거래량 (평소의 몇 배)", v, R.vol_tip(vr))])}</div>'


def sec_chart_indicators(s):
    """2층 · 접힘 `차트 지표 보기` — NVDA 리포트와 같은 칸, 하루 비교는 S&P 500 · 업종 ETF."""
    tc = s["tech"]
    etf = U.sector_etf(s["sym"])[0]
    deep = R._multi2([(f"{n}일 평균", R._arrow(v, 1)) for n, v in sorted(tc["ma_rel"].items(), key=lambda x: int(x[0]))])
    deep += R._multi2([("S&P 500 대비", R._arrow(tc.get("vs_spy"), 2, "%p")), (f"{etf} 대비", R._arrow(tc.get("vs_sector"), 2, "%p"))])
    rsi, mc = tc.get("rsi14"), tc.get("ma_cross")
    mc_html = {"golden": f'<span style="color:{UP};font-weight:700;">골든크로스</span>', "death": f'<span style="color:{DOWN};font-weight:700;">데드크로스</span>'}.get(
        mc, f'<span style="color:{R.MUTED};">교차 없음</span>')
    items = [("시가 갭", R._arrow(tc.get("gap"), 2), R.gap_tip(tc.get("gap"))),
             (f"일중 변동폭 (고가−저가 · 흔히 {R.config.RANGE_PCT_EVENT:.0f}% 넘으면 큰 흔들림으로 봄)",
              f'<span style="color:#111;font-weight:700;">{tc["range_pct"]:.2f}%</span>' if tc.get("range_pct") is not None else "—"),
             ("단기 과열 온도 (RSI 14 · 흔히 70 넘으면 과열 · 30 아래면 침체로 읽음)",
              f'<span style="color:#111;font-weight:700;">{rsi:.1f}</span>' if rsi is not None else "—", _no_record(R.rsi_tip(rsi))),
             ("평균선 교차 (50일선이 200일선 위로 = 골든크로스)", mc_html, _no_record(R.cross_tip(mc)))]
    deep += R._multi(items)
    return (f'<details data-fold="1" data-label="차트 지표 보기" style="margin:0 0 8px;"><summary style="list-style:none;cursor:pointer;">{R._fold_row("차트 지표 보기")}</summary>'
            f'<div style="margin-top:6px;">{deep}</div></details>')


def sec_drawdown(s):
    """고점 하락 후 가격 회복 — 이 종목과 S&P 500 (NVDA 리포트는 기술주 15개와 견준다). 숫자 = 절반은 이 거래일 안에 회복."""
    d = s.get("drawdown")
    if not d:
        return ""
    st, sp = d["stock"]["dd"], d["stock"]["spy_dd"]   # S&P 500 은 이 종목과 같은 기간
    span = R._span_label(d["stock"])
    sm = f'font-size:{TINY};font-weight:400;color:{NOTE};'
    rows = R._row_html("지금", R._arrow(d["pct_from_high"], 1), f"1년 최고가 이후 {d['days_since_high']}거래일째", first=True, inline_note=True)
    cols = []
    for lv in ("10", "20", "30"):
        x, y = st.get(lv) or {}, sp.get(lv) or {}
        if not x.get("n") or x.get("median_days") is None:
            continue
        right = f'<span style="{sm}">보통</span> {x["median_days"]}일' + (f'<br><span style="{sm}">S&amp;P 500 보통 {y["median_days"]}일</span>' if y.get("median_days") is not None else "")
        rows += R._row_html(f'<span style="color:{DOWN};">−{lv}%</span> 넘게 내려가면', right, f"{span} 동안 {s['name']} {x['n']}번 발생")
        if x.get("recovered") and y.get("recovered"):
            cols.append((lv, x["over_year"] / x["recovered"] * 100, y["over_year"] / y["recovered"] * 100))
    tail = ""
    if cols:
        vb = "border-left:1px solid #E2E8F0;"
        cell = lambda txt, first=False: (f'<span style="flex:1 1 0;min-width:0;box-sizing:border-box;padding:0 8px;text-align:{"left" if first else "center"};{"" if first else vb}">{txt}</span>')   # noqa: E731
        head = cell(f'<span style="color:{DOWN};font-weight:700;">하락비율</span>', True) + "".join(cell(f'<span style="color:{DOWN};font-weight:700;">−{lv}%</span>') for lv, _, _ in cols)
        r1 = cell(_esc(s["name"]), True) + "".join(cell(f"{a:.0f}%") for _, a, _ in cols)
        r2 = cell("S&amp;P 500", True) + "".join(cell(f"{b:.0f}%") for _, _, b in cols)
        tbl = "".join(f'<span style="display:flex;align-items:stretch;line-height:24px;">{r}</span>' for r in (head, r1, r2))
        tip = "크게 떨어진 일 가운데, 최고가를 되찾기까지 1년(250거래일) 넘게 걸린 경우의 비율\n· 참고 : 지난 기록이라 앞으로도 그렇다는 뜻은 아니다"
        title = (f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:0 0 4px;">'
                 f'<span style="color:#111;font-weight:700;white-space:nowrap;">회복에 1년 넘게 걸린 비율{R._tipx(tip)}</span>'
                 f'<span style="flex:none;font-size:{_dk.MICRO};font-weight:400;color:{NOTE};">({span} 기간 중)</span></span>')
        tail = f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px;font-size:{TINY};color:{NOTE};">{title}{tbl}</span>'
    x = d["pct_from_high"]
    lv = next((l for l in ("30", "20", "10") if -x > int(l) and (st.get(l) or {}).get("median_days") is not None), None)
    now = (f"\n· 지금 {_sgn(x)}% : −{lv}% 넘게 빠졌을 때 절반은 {st[lv]['median_days']}거래일 안에 최고가를 되찾았다" if lv else
           f"\n· 지금 {_sgn(x)}% : 1년 최고가에서 10% 안쪽")
    ttip = (f"주가가 최고가에서 크게 떨어졌을 때 그 최고가를 다시 넘기까지 걸린 거래일. '보통' 은 절반이 이보다 빨리 회복한 값" + now +
            "\n· 참고 : 지난 기록이라 앞으로를 말하지 않는다")
    return R._card_title("고점 하락 후 가격 회복", ttip) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}{tail}</span></div>'


def related(s):
    """함께 보는 리포트 (가이드라인 10-5 4) — HTML 링크라 검색엔진이 따라간다."""
    links = [("미국 시가총액 상위 10개 종목 주가", U.LIST_URL), ("엔비디아(NVDA) 주가 리포트", U.NVDA_REPORTS_URL)]
    items = "".join(f'<li style="margin:4px 0;"><a href="{_esc(u)}" style="color:#1a73e8;text-decoration:none;">{_esc(t)}</a></li>' for t, u in links)
    return (f'<div data-related="1" style="margin-top:24px;"><div style="font-weight:700;color:#111;font-size:{_dk.EMPH_NAME};">함께 보는 페이지</div>'
            f'<ul style="margin:6px 0 0;padding-left:20px;font-size:{_dk.NAME};line-height:{R.LH_CARD};">{items}</ul></div>')


def detail_body(s, today):
    return wrap(lead(s) + updated_line(s) + price_card(s) + sec_states(s) + sec_periods(s) + sec_year_range(s) + sec_drawdown(s) + sec_earnings(s, today)
                + sec_volume(s) + sec_chart_indicators(s)
                + button("시총 TOP 10 목록", U.LIST_URL) + related(s) + foot())


# ---------------------------------------------------------------- 목록

def list_lead(a):
    top = [s for s in a["stocks"] if s["in_top"]]
    up = sum(1 for s in top if s["ret_1d"] > 0)
    first = top[0]
    text = (f"{_md(a['day'])} 종가 기준 미국 시가총액 1위는 {first['name']}({first['sym']}), {cap_text(first['cap'])}이다. "
            f"상위 10개 중 {up}개가 오르고 {len(top) - up}개가 내렸다.")
    return f'<p data-seo-lead="1" style="font-size:{_dk.NAME};line-height:{R.LH_CARD};color:#333;margin:0 0 12px;word-break:keep-all;">{_esc(text)}</p>'


def detail_url(s):
    return U.NVDA_REPORTS_URL if s["sym"] in U.REPORT_TYPE else U.page_url(s["sym"])


def list_row(s, first):
    r = s["ret_1d"]
    pcol = UP if r > 0 else DOWN if r < 0 else "#111"
    left = (f'<span style="display:inline-block;width:26px;color:{NOTE};font-weight:700;">{s["rank"]}</span>{_dk.ticker_logo(s["sym"])}'
            f'<a href="{_esc(detail_url(s))}" style="color:#111;text-decoration:none;">{_esc(s["name"])}</a>'
            f'<span style="display:block;padding-left:52px;font-size:{_dk.MICRO};line-height:20px;font-weight:400;color:{NOTE};">{_esc(s["sym"])} · {cap_text(s["cap"])}</span>')   # 순위 26 + 로고 26 만큼 들여 이름 글자에 맞춘다
    right = f'<span style="color:{pcol};">${s["close"]:,.2f}</span><br>{R._arrow(r)}'
    return R._row_html(left, right, first=first)


def list_body(a):
    top = [s for s in a["stocks"] if s["in_top"]]
    rest = [s for s in a["stocks"] if not s["in_top"]]
    card = lambda xs: f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{"".join(list_row(s, i == 0) for i, s in enumerate(xs))}</span></div>'   # noqa: E731
    tip = ("미국 S&P 500 종목 가운데 회사 전체 값(주가 × 주식 수)이 가장 큰 10개\n"
           f"· 오늘 1위 : {top[0]['name']} {cap_text(top[0]['cap'])}\n"
           f"· 나누는 법 : 11위 밖으로 {U.SWAP_DAYS}거래일 연속 밀리면 후보 중 가장 높았던 종목과 바꾼다")
    body = (list_lead(a) + updated_line(a) + R._card_title("시가총액 순위", tip) + card(top)
            + _dk.fold(f"후보 11~{len(a['stocks'])}위 보기", card(rest))
            + _dk.muted("종목 이름을 누르면 상세 페이지로 갑니다. 엔비디아는 매일 나오는 리포트로 갑니다.") + foot())
    return wrap(body)


def write_all(a, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    pages = {"list": (U.LIST_TITLE, list_body(a))}
    for s in a["stocks"]:
        if s["sym"] not in U.REPORT_TYPE:
            pages[s["sym"]] = (U.page_title(s["sym"]), detail_body(s, a["day"]))
    for key, (title, body) in pages.items():
        with open(os.path.join(out_dir, f"{key}.html"), "w", encoding="utf-8") as f:
            f.write(body)
        _dk.write_mock(body, os.path.join(out_dir, f"mock_{key}.html"), title)
    return pages
