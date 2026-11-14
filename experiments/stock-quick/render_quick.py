"""간단 정보 화면 조각 — 종목 파일(collect_quick) 하나 → 카드 HTML 하나 (2026-11-14, 기획 비공개 기획/회원-내-종목-기획.md 6-6).

카드 HTML 은 파이썬이 만들고(공용 카드 부품 cards · design_kit 그대로 — 여백 · 색 · 글자 규칙이 정식 종목과 같다),
블로그의 고정 페이지 `stock-quick` 하나가 주소 뒤 종목 코드(?s=)로 이 조각을 받아 끼워 넣기만 한다(quick_page.js).
접기 = details(브라우저 기본), PC 두 칸 = 테마 CSS(.post-body [data-grid]) 라 끼워 넣은 뒤에도 그대로 동작한다.
그림 파일 0 — 그래프는 SVG 글자로 조각 안에 들어 있다.

카드 순서(6-6): 안내 상자(기준일) · 첫 문장 · 오늘 주가는? · 기간별로는? · 1년 중 어디쯤? · 기술지표의 방향은? · 거래는 평소와 같나?
· 다음 실적 발표는?(미국, 있을 때) · 최근 공시는?(한국, 있을 때) · 이름이 나온 기사는?(미국, 있을 때) · 1년 흐름 · 안내 한 줄 · 함께 보는 페이지.
"""

import datetime
import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
for p in (EXP, os.path.join(EXP, "daily-report"), os.path.join(EXP, "stock-radar"), os.path.join(EXP, "kr-stocks")):
    if p not in sys.path:
        sys.path.insert(0, p)
import cards as C  # noqa: E402
import design_kit as dk  # noqa: E402
import universe as U  # noqa: E402
import universe_kr as K  # noqa: E402

LIST_URL = {"US": U.LIST_URL, "KR": K.LIST_URL}   # 전체 종목 목록(all-stocks)이 생기기 전까지 시장별 종목 목록
WHEN = "오후 5시 40분 무렵"
BENCH_KEY = {"US": "US", "KOSPI": "KOSPI", "KOSDAQ": "KOSDAQ"}


def esc(t):
    return html.escape(str(t), quote=False)


def money(v, market):
    return f"${v:,.2f}" if market == "US" else f"{v:,.0f}원"


def pct(v):
    return "" if v is None else f"{v:+.1f}%".replace("-", "−")


def color(v):
    return C.UP if (v or 0) > 0 else C.DOWN if (v or 0) < 0 else "#111"


def kday(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.month}월 {d.day}일"


def code(f):
    return f["s"].split(".")[0]


def _dates(obj):
    d0 = datetime.date.fromisoformat(obj["d0"])
    return [str(d0 + datetime.timedelta(days=x)) for x in obj["dd"]]


def _bench_on(days, b):
    """시장 지수 종가를 종목 날짜에 맞춘다 — 휴장일이 다르면 앞 값."""
    bm = dict(zip(_dates(b), b["px"]))
    out, last = [], None
    for d in days:
        last = bm.get(d, last)
        out.append(last)
    first = next((x for x in out if x is not None), None)
    return [x if x is not None else first for x in out]


def related(f, ref_full):
    """함께 보는 페이지 = 같은 업종의 정식 종목 2개(종목 분석) + 전체 종목 목록."""
    links = []
    for sym, (name, sector, url) in ref_full.items():
        if sym != f["s"] and sector == f.get("sec") and (sym.endswith((".KS", ".KQ")) == (f["m"] == "KR")):
            links.append((f"{name} 종목 분석", url))
        if len(links) >= 2:
            break
    return links + [("미국 종목 목록" if f["m"] == "US" else "한국 종목 목록", LIST_URL[f["m"]])]


def full_index(ref):
    """정식 종목 {sym: (한글 이름, 업종, 페이지 주소)} — 함께 보는 페이지용."""
    out = {}
    for sym, e in ref["us"].items():
        if e.get("full") and sym in U.BY_SYM:
            out[sym] = (e["ko"], e.get("sector"), U.page_url(sym))
    for sym, e in ref["kr"].items():
        if e.get("full") and sym in K.BY_SYM:
            out[sym] = (e["ko"], e.get("sector"), K.page_url(sym))
    return out


def render(f, bench, ref_full):
    m = f["m"]
    mk = BENCH_KEY.get(f["mk"], "US")
    b = bench.get(mk) or bench.get("US")
    bname = b["n"] if b else ("S&P 500" if m == "US" else "코스피")
    days, c = _dates(f), f["px"]
    bc = _bench_on(days, b) if b else None
    ch, bch = f.get("chg", {}), (b or {}).get("chg", {})
    d1 = ch.get("1d")

    day = datetime.date.fromisoformat(f["d"])   # 간단 정보는 평일 17:40 KST 한 번 갱신(quick-data.yml) — 정식 종목 페이지(07:30 · 16:10)와 시각이 다르다
    parts = [dk.report_stamp(dk.kst_close_day(day, "US"), WHEN, close="새벽 마감") if m == "US" else dk.report_stamp(dk.kst_close_day(day, "KR"), WHEN)]
    if f.get("full") and f["s"] in ref_full:   # 정식 종목 — 종목 분석 페이지가 따로 있다
        parts.append(f'<p style="font-size:16px;line-height:26px;margin:0 0 10px;padding-left:6px;color:#333;">이 종목은 뉴스 · 의견 · 실적까지 다룬 '
                     f'<a href="{ref_full[f["s"]][2]}" style="color:#111;font-weight:700;">{esc(f["n"])} 종목 분석</a> 페이지가 있습니다.</p>')
    if f.get("carried"):
        parts.append(dk.muted("오늘 가격을 받지 못해 지난 거래일 값입니다."))
    sub = f" · 세부 업종은 {esc(f['sub'])}" if f.get("sub") else ""
    move = "올랐" if (d1 or 0) > 0 else "내렸" if (d1 or 0) < 0 else "같았"
    lead = (f'{kday(f["d"])} {esc(f["n"])}({esc(code(f))}) 종가는 {money(f["c"], m)}{"으로" if m == "KR" else "로"} 전날보다 '
            f'<span style="color:{color(d1)};white-space:nowrap;">{pct(d1)}</span> {move}습니다. '
            f'업종은 {esc(f.get("sec") or "")}{sub}입니다.')
    if f.get("status") == "halted":
        lead = f'{esc(f["n"])}({esc(code(f))})은 {kday(f["d"])} 뒤로 거래가 없습니다. 거래정지일 수 있습니다.'
    parts.append(f'<p data-seo-lead="1" style="font-size:19px;line-height:35px;color:#333;margin:0 0 12px;word-break:keep-all;padding-left:6px;">{lead}</p>')

    q = []
    # 오늘 주가는?
    q.append(C.question_card("오늘 주가는?", pct(d1), dk.dir_theme(d1 or 0, 1), color(d1), [
        ("row", "종가", money(f["c"], m), ""),
        ("row", "전날 종가", money(c[-2], m) if len(c) > 1 else "", ""),
        ("row", f"{bname} 하루", f'<span style="color:{color(bch.get("1d"))};">{pct(bch.get("1d"))}</span>', "같은 날 시장"),
    ], opened=True))
    # 기간별로는?
    groups = [(nm, [ch.get(k), bch.get(k)]) for nm, k in (("1주", "1w"), ("1달", "1m"), ("연초", "ytd"), ("1년", "1y"))
              if ch.get(k) is not None and bch.get(k) is not None]
    if groups:
        nm_last, (a, bb) = groups[-1]
        ahead = a > bb
        chart = C.chart_card("기간별 등락", groups, [C.sign_bg, C.gray], [C.sign_fg, C.note_fg],
                             [(f["n"], C.PASTEL_UP), (bname, C.GRAY_BAR)], fmt=pct)
        q.append(C.question_card("기간별로는?", "시장보다 앞섬" if ahead else "시장보다 뒤처짐", "positive" if ahead else "negative",
                                 C.UP if ahead else C.DOWN, [
                                     (f"{nm_last} 동안 {pct(a)} 움직였고, 같은 기간 {bname}는 {pct(bb)}였습니다.", "plain"),
                                     (chart, "html"),
                                 ], opened=True))
    # 1년 중 어디쯤? — 1년 안 된 종목은 범위가 짧다
    if f.get("hi") and f.get("lo") and f.get("pos") is not None:
        pos, fh = f["pos"] * 100, f["off_hi"]
        gauge = C.range_gauge(f["lo"], f["hi"], pos, fh, lambda v: money(v, m), "", "1년 범위" if f["status"] != "short" else "상장 뒤 범위",
                              "최고 대비", "최고가 근처")
        where = "최고가 근처" if fh > -3 else "중간쯤" if pos > 35 else "최저가 쪽"
        q.append(C.question_card("1년 중 어디쯤?", where, "neutral", "#111", [
            (f"1년 최고가보다 {abs(fh):.1f}% 아래에 있습니다." if fh <= -0.5 else "1년 최고가 근처에 있습니다.", "plain"),
            (gauge, "html"),
        ]))
    # 기술지표의 방향은? — 정식 종목과 같은 계산(tech_signals) 요약
    t = f.get("tech") or {}
    if t.get("d"):
        w = t["d"]["word"]
        th = "positive" if "상승" in w else "negative" if "하락" in w else "neutral"
        rows = [("row", "일봉", t["d"]["word"], "하루 단위")]
        if t.get("w"):
            rows.append(("row", "주봉", t["w"]["word"], "한 주 단위"))
        rows.append(("상대강도 · 이동평균 같은 지표 스무여 개가 가리키는 가격 방향을 모은 것입니다.", "note"))
        q.append(C.question_card("기술지표의 방향은?", w, th, C.UP if th == "positive" else C.DOWN if th == "negative" else "#111", rows))
    # 거래는 평소와 같나?
    r = f.get("vol_ratio")
    if r:
        vt = "평소보다 많음" if r >= 1.5 else "평소보다 적음" if r <= 0.67 else "평소 수준"
        q.append(C.question_card("거래는 평소와 같나?", vt, "neutral", "#111", [
            ("최근 한 달 하루 평균 거래량과 비교했습니다. 거래가 크게 늘면 그날 소식이 있었는지 함께 보는 것이 좋습니다.", "plain"),
        ]))
    # 다음 실적 발표는? (미국)
    e = f.get("earn")
    if e:
        when = {"bmo": "장 시작 전", "amc": "장 마감 뒤"}.get(e.get("hour"), "")
        q.append(C.question_card("다음 실적 발표는?", kday(e["date"]), "neutral", "#111", [
            ("row", "발표일", f'{kday(e["date"])}{" " + when if when else ""}', "미국 날짜"),
            ("회사가 알린 날짜입니다. 바뀌면 다음 갱신 때 고쳐집니다.", "note"),
        ]))
    # 최근 공시는? (한국)
    if f.get("disc"):
        rows = [("row", f'<span><a href="{esc(x["u"])}" target="_blank" rel="noopener" style="color:#111;text-decoration:none;">{esc(x["t"])}</a></span>',
                 kday(x["d"]), "") for x in f["disc"]]
        q.append(C.question_card("최근 공시는?", kday(f["disc"][0]["d"]), "neutral", "#111",
                                 rows + [("금융감독원 전자공시(DART)에 올라온 최근 7일 공시입니다. 누르면 원문으로 갑니다.", "note")]))
    # 이름이 나온 기사는? (미국)
    if f.get("news"):
        rows = [("row", f'<span><a href="{esc(x["u"])}" target="_blank" rel="noopener" style="color:#111;text-decoration:none;">{esc(x["t"])}</a></span>',
                 kday(x["d"]) if x.get("d") else "", x.get("src") or "") for x in f["news"]]
        q.append(C.question_card("이름이 나온 기사는?", kday(f["news"][0]["d"]) if f["news"][0].get("d") else "최근 7일", "neutral", "#111",
                                 rows + [("최근 7일 기사 제목에 회사 이름이 나온 것입니다. 이 회사가 주인공이 아닌 기사도 섞일 수 있습니다.", "note")]))
    parts.append(C.cards_grid("".join(q)))

    # 1년 흐름 — 비교 = 시장 지수, 처음 = 0
    if bc and len(c) > 20:
        base, b0 = c[0], bc[0]
        series = [(f["n"], [(x / base - 1) * 100 for x in c], dk.CHART_MAIN, "solid"),
                  (bname, [(x / b0 - 1) * 100 if x else None for x in bc], dk.CHART_CMP, "dash")]
        ttl = "1년 전 대비 등락" if f["status"] != "short" else "상장 뒤 등락"
        parts.append(dk.section("1년 흐름", dk.trend_card(ttl, dk.month_ticks(days), series, pct)))
    parts.append(dk.muted("간단 정보는 가격 자료만 다룹니다. 의견 · 실적 · 소송은 종목 분석 페이지에서 다룹니다."))
    parts.append(dk.related_buttons(related(f, ref_full)))
    body = (f'<div data-design="2" data-quick="{esc(f["s"])}" data-quick-title="{esc(title(f))}" style="font-family:-apple-system,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;'
            f'font-size:19px;line-height:35px;color:#333;">{"".join(parts)}</div>')
    return dk.formal(body)


def title(f):
    return f'{f["n"]} {code(f)} 간단 정보'
