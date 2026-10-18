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
    rows, first = "", True
    if e.get("next"):
        left = (datetime.date.fromisoformat(e["next"]) - datetime.date.fromisoformat(today)).days
        rows += R._row_html("다음 실적 발표", f"{left}일 뒤" if left > 0 else "오늘", f"{_md(e['next'])} 예정", first=True, inline_note=True)
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
    return R._card_title("실적 발표 후 가격 변동", earn_tip(s, e)) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


def related(s):
    """함께 보는 리포트 (가이드라인 10-5 4) — HTML 링크라 검색엔진이 따라간다."""
    links = [("미국 시가총액 상위 10개 종목 주가", U.LIST_URL), ("엔비디아(NVDA) 주가 리포트", U.NVDA_REPORTS_URL)]
    items = "".join(f'<li style="margin:4px 0;"><a href="{_esc(u)}" style="color:#1a73e8;text-decoration:none;">{_esc(t)}</a></li>' for t, u in links)
    return (f'<div data-related="1" style="margin-top:24px;"><div style="font-weight:700;color:#111;font-size:{_dk.EMPH_NAME};">함께 보는 페이지</div>'
            f'<ul style="margin:6px 0 0;padding-left:20px;font-size:{_dk.NAME};line-height:{R.LH_CARD};">{items}</ul></div>')


def detail_body(s, today):
    return wrap(lead(s) + updated_line(s) + price_card(s) + sec_periods(s) + sec_year_range(s) + sec_earnings(s, today)
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
