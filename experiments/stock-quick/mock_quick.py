"""간단 종목 정보 목업 — 정식 종목(종목 분석 페이지)이 아닌 종목을 가격 자료만으로 보여 주는 화면 (2026-11-12 사용자 "목업 적용해", 기획 = 비공개 기획/회원-내-종목-기획.md 6-6).

    python experiments/stock-quick/mock_quick.py      # output/mock_quick_<종목>.html · output/mock_all_stocks.html

실제 적용 때는 고정 페이지 하나(stock-quick?s=코드)를 테마 JS 가 search/<시장>-lite.json 으로 그린다.
목업은 같은 화면을 파이썬으로 미리 그린다 — 카드 · 막대 · 범위 막대 · 선 그래프는 종목 페이지 · 데일리와 같은 공용 부품(design_kit · daily-report/cards).
자료 = yfinance 1년 일봉 묶음 + 실적일(회사 캘린더). AI 0.
"""

import datetime
import os
import sys

import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, EXP)
sys.path.insert(0, os.path.join(EXP, "daily-report"))
import design_kit as dk  # noqa: E402
import cards as C  # noqa: E402

OUT = os.path.join(HERE, "output")
LIST_DAY = ""

# 예시 — 정식 종목 목록(미국 64 · 한국 35)에 없는 종목. 업종 · 세부 업종은 분류 세 층(taxonomy) 말로
SAMPLES = [
    {"sym": "UBER", "name": "우버", "market": "US", "sector": "산업재", "sub": "운송 · 플랫폼", "peers": [("엔비디아 NVDA 주가", "#"), ("테슬라 TSLA 주가", "#")]},
    {"sym": "SBUX", "name": "스타벅스", "market": "US", "sector": "경기 소비재", "sub": "외식", "peers": [("맥도날드 MCD 주가", "#"), ("코스트코 COST 주가", "#")]},
    {"sym": "259960.KS", "name": "크래프톤", "market": "KR", "sector": "커뮤니케이션", "sub": "게임", "peers": [("NAVER 035420 주가", "#"), ("카카오 035720 주가", "#")]},
]
BENCH = {"US": ("^GSPC", "S&P 500"), "KR": ("^KS11", "코스피")}
# 전체 종목 목록 목업에 같이 싣는 종목 (정식 몇 개 + 간단 정보 몇 개)
LIST_US = [("NVDA", "엔비디아", "반도체", True), ("AAPL", "애플", "정보기술", True), ("UBER", "우버", "산업재", False), ("SBUX", "스타벅스", "경기 소비재", False),
           ("PLTR", "팔란티어", "정보기술", False), ("NKE", "나이키", "경기 소비재", False), ("SHOP", "쇼피파이", "정보기술", False), ("DE", "디어", "산업재", False)]


def money(v, market):
    return f"${v:,.2f}" if market == "US" else f"{v:,.0f}원"


def pct(v):
    return f"{v:+.1f}%".replace("-", "−")


def color(v):
    return C.UP if v > 0 else C.DOWN if v < 0 else "#111"


def ret(c, n):
    return (c[-1] / c[-1 - n] - 1) * 100 if len(c) > n else None


def ytd(days, c):
    y = days[-1][:4]
    i = next((k for k, d in enumerate(days) if d[:4] == y), 0)
    base = c[i - 1] if i else c[0]
    return (c[-1] / base - 1) * 100


def earnings(sym):
    try:
        ds = (yf.Ticker(sym).calendar or {}).get("Earnings Date") or []
        today = datetime.date.today()
        fut = sorted(d for d in ds if d >= today)
        return fut[0] if fut else None
    except Exception:  # noqa: BLE001
        return None


def stamp(day_text, text):
    """맨 위 안내 상자 — 종목 페이지 report_stamp 와 같은 모양, 문구만 간단 정보용."""
    return dk.report_stamp(day_text, "").replace(" · 매 거래일 장을 마감한 뒤 발행되는 리포트입니다. ()", " · " + text)


def kday(d):
    return f"{d.month}월 {d.day}일"


def page(s, df, bdf):
    sub = df.dropna(subset=["Close"])
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    if s["market"] == "KR" and sub.index[-1].strftime("%Y-%m-%d") == now.strftime("%Y-%m-%d") and now.hour < 16:
        sub = sub.iloc[:-1]   # 장중 봉 — 종가가 아니다
    days = [i.strftime("%Y-%m-%d") for i in sub.index]
    c = [float(x) for x in sub["Close"]]
    vol = [float(x or 0) for x in sub["Volume"]]
    b = bdf.dropna(subset=["Close"])
    bmap = {i.strftime("%Y-%m-%d"): float(x) for i, x in zip(b.index, b["Close"])}
    bc = [bmap.get(d) for d in days]
    for k in range(1, len(bc)):   # 휴장일이 다르면 앞 값
        bc[k] = bc[k] if bc[k] is not None else bc[k - 1]
    bc = [x if x is not None else bc[next(j for j in range(len(bc)) if bc[j] is not None)] for x in bc]
    m, bname = s["market"], BENCH[s["market"]][1]
    last = datetime.date.fromisoformat(days[-1])
    d1 = ret(c, 1)

    parts = [stamp(kday(last) + ("(미국 시간)" if m == "US" else ""), "가격 자료만으로 만든 간단 정보입니다. 매 거래일 장을 마감한 뒤 한 번 갱신됩니다.")]
    lead = (f'{kday(last)} {s["name"]}({s["sym"].split(".")[0]}) 종가는 {money(c[-1], m)}로 전날보다 '
            f'<span style="color:{color(d1)};white-space:nowrap;">{pct(d1)}</span> {"올랐" if d1 > 0 else "내렸" if d1 < 0 else "같았"}습니다. '
            f'업종은 {s["sector"]} · 세부 업종은 {s["sub"]}입니다.')
    parts.append(f'<p data-seo-lead="1" style="font-size:19px;line-height:35px;color:#333;margin:0 0 12px;word-break:keep-all;padding-left:6px;">{lead}</p>')

    q = []
    # 1. 오늘 주가는?
    q.append(C.question_card("오늘 주가는?", pct(d1), dk.dir_theme(d1, 1), color(d1), [
        ("row", "종가", money(c[-1], m), ""),
        ("row", "전날 종가", money(c[-2], m), ""),
        ("row", f"{bname} 하루", f'<span style="color:{color(ret(bc, 1))};">{pct(ret(bc, 1))}</span>', "같은 날 시장"),
    ], opened=True))
    # 2. 기간별로는?
    per = [("1주", 5), ("1달", 21), ("연초", None), ("1년", len(c) - 1)]
    groups, ahead = [], 0
    for nm, n in per:
        a = ytd(days, c) if n is None else ret(c, n)
        bb = ytd(days, bc) if n is None else ret(bc, n)
        groups.append((nm, [a, bb]))
        ahead += a > bb
    yr, byr = groups[-1][1]
    ans = "시장보다 앞섬" if yr > byr else "시장보다 뒤처짐"
    chart = C.chart_card("기간별 등락", groups, [C.sign_bg, C.gray], [C.sign_fg, C.note_fg], [(s["name"], C.PASTEL_UP), (bname, C.GRAY_BAR)], fmt=pct)
    q.append(C.question_card("기간별로는?", ans, "positive" if yr > byr else "negative", C.UP if yr > byr else C.DOWN, [
        (f"1년 동안 {pct(yr)} 움직였고, 같은 기간 {bname}는 {pct(byr)}였습니다.", "plain"),
        (chart, "html"),
    ], opened=True))
    # 3. 1년 중 어디쯤?
    hi, lo = max(c[-252:]), min(c[-252:])
    pos = (c[-1] - lo) / (hi - lo) * 100 if hi > lo else 50
    fh = (c[-1] / hi - 1) * 100
    gauge = C.range_gauge(lo, hi, pos, fh, lambda v: money(v, m), "", "1년 범위", "최고 대비", "최고가 근처")
    where = "최고가 근처" if fh > -3 else "중간쯤" if pos > 35 else "최저가 쪽"
    q.append(C.question_card("1년 중 어디쯤?", where, "neutral", "#111", [
        (f"1년 최고가보다 {abs(fh):.1f}% 아래에 있습니다." if fh <= -0.5 else "1년 최고가 근처에 있습니다.", "plain"),
        (gauge, "html"),
    ], opened=True))
    # 4. 추세는?
    ma50 = sum(c[-50:]) / 50
    ma200 = sum(c[-200:]) / 200 if len(c) >= 200 else None
    up = c[-1] > ma50 and (ma200 is None or c[-1] > ma200)
    dn = c[-1] < ma50 and (ma200 is None or c[-1] < ma200)
    st, th, col = ("▲상승", "positive", C.UP) if up else ("▼하락", "negative", C.DOWN) if dn else ("중립", "neutral", "#111")
    q.append(C.question_card("추세는?", st, th, col, [
        ("row", "50일 평균선", "위" if c[-1] > ma50 else "아래", f"{money(ma50, m)}"),
        ("row", "200일 평균선", "위" if ma200 and c[-1] > ma200 else "아래", f"{money(ma200, m)}" if ma200 else ""),
        ("평균선은 최근 며칠 동안의 종가 평균입니다. 종가가 두 선 위에 있으면 상승, 아래에 있으면 하락으로 봅니다.", "note"),
    ]))
    # 5. 거래는 평소와 같나?
    avg = sum(vol[-21:-1]) / 20 if len(vol) > 21 else None
    r = vol[-1] / avg if avg else None
    vt = "평소보다 많음" if r and r >= 1.5 else "평소보다 적음" if r and r <= 0.67 else "평소 수준"
    q.append(C.question_card("거래는 평소와 같나?", vt, "neutral", "#111", [
        ("최근 한 달 하루 평균 거래량과 비교했습니다. 거래가 크게 늘면 그날 소식이 있었는지 함께 보는 것이 좋습니다.", "plain"),
    ]))
    # 6. 다음 실적 발표는? — 없으면 카드 생략
    e = earnings(s["sym"])
    if e:
        q.append(C.question_card("다음 실적 발표는?", kday(e), "neutral", "#111", [
            ("회사가 알린 날짜입니다. 바뀌면 다음 갱신 때 고쳐집니다.", "note"),
        ]))
    parts.append(C.cards_grid("".join(q)))

    # 1년 가격 선 그래프 — 비교 = 시장 지수, 1년 전 = 0
    base, bb0 = c[0], bc[0]
    series = [(s["name"], [(x / base - 1) * 100 for x in c], C.UP if c[-1] >= base else C.DOWN, "solid"),
              (bname, [(x / bb0 - 1) * 100 for x in bc], "#94A3B8", "dash")]
    parts.append(dk.section("1년 흐름", dk.trend_card("1년 전 대비 등락", dk.month_ticks(days), series, pct)))   # 1년 일별 = 끝 값만 · 점 없음 (ends_only 는 40일 전망 그래프용 날마다 점)
    parts.append(dk.muted("간단 정보는 가격 자료만 다룹니다. 뉴스 · 의견 · 소송은 종목 분석 페이지에서 다룹니다."))
    parts.append(dk.related_buttons(s["peers"] + [("전체 종목 목록", "mock_all_stocks.html")]))
    body = f'<div data-design="2" style="font-family:-apple-system,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;font-size:19px;line-height:35px;color:#333;">{"".join(parts)}</div>'
    title = f'{s["name"]} {s["sym"].split(".")[0]} 간단 정보'
    return dk.formal(body), title


def all_stocks(data):
    """전체 종목 목록 — 업종별 표: 이름 · 하루 등락 · 1년 범위 위치. 정식 종목은 이름 옆 `분석`."""
    rows = {}
    for sym, name, sector, full in LIST_US:
        df = data.get(sym)
        if df is None:
            continue
        c = [float(x) for x in df.dropna(subset=["Close"])["Close"]]
        d1 = ret(c, 1)
        hi, lo = max(c[-252:]), min(c[-252:])
        pos = (c[-1] - lo) / (hi - lo) * 100 if hi > lo else 50
        tag = ('<span style="margin-left:6px;padding:1px 6px;border:1px solid #E2E8F0;border-radius:4px;font-size:12px;line-height:16px;color:#6B7280;font-weight:600;">분석</span>' if full else "")
        bar = (f'<span style="display:inline-block;position:relative;width:64px;height:6px;border-radius:3px;background:#E2E8F0;vertical-align:middle;margin-right:8px;">'
               f'<span style="position:absolute;left:{pos:.0f}%;top:-3px;width:8px;height:12px;margin-left:-4px;border-radius:2px;background:#1a73e8;"></span></span>')
        href = "#" if full else f"mock_quick_{sym}.html"
        nm = f'<a href="{href}" style="color:#111;text-decoration:none;">{dk.esc(name)}</a> <span style="font-size:14px;color:#6B7280;">{sym}</span>{tag}'
        rows.setdefault(sector, []).append((nm, f'{bar}<span style="color:{color(d1)};">{pct(d1)}</span>', ""))
    search = ('<div style="margin:0 0 16px;"><input type="search" placeholder="종목 이름이나 코드로 찾기" '
              'style="width:100%;box-sizing:border-box;border:1px solid #E2E8F0;border-radius:999px;padding:10px 16px;font:inherit;font-size:16px;"></div>')
    tabs = '<p style="margin:0 0 12px;font-size:15px;"><b>미국</b> · <span style="color:#6B7280;">한국</span></p>'
    body = [stamp(LIST_DAY, "AlphaScope 가 다루는 모든 종목입니다."), tabs, search]
    for sector, rs in rows.items():
        body.append(dk.section(sector, dk.ccard(rs).replace('data-cards="1" ', '')))   # data-cards 는 테마가 탭 카드로 옮긴다 — 목록 표엔 쓰지 않음
    body.append(dk.muted("이름 옆에 분석 표시가 있는 종목은 뉴스 · 의견까지 다루는 종목 분석 페이지로, 나머지는 간단 정보로 갑니다. 막대는 1년 최저 ~ 최고 사이 오늘 위치입니다."))
    html = f'<div data-design="2" style="font-family:-apple-system,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;font-size:19px;line-height:35px;color:#333;">{"".join(body)}</div>'
    return dk.formal(html)


def main():
    global LIST_DAY
    os.makedirs(OUT, exist_ok=True)
    syms = sorted({s["sym"] for s in SAMPLES} | {x[0] for x in LIST_US} | {v[0] for v in BENCH.values()})
    df = yf.download(syms, period="1y", interval="1d", auto_adjust=False, group_by="ticker", progress=False, threads=True)
    data = {s: df[s] for s in syms if s in df.columns.get_level_values(0)}
    for s in SAMPLES:
        body, title = page(s, data[s["sym"]], data[BENCH[s["market"]][0]])
        p = dk.write_mock(body, os.path.join(OUT, f'mock_quick_{s["sym"].split(".")[0]}.html'), title)
        print("만듦:", p)
    LIST_DAY = kday(datetime.date.fromisoformat(data["AAPL"].dropna(subset=["Close"]).index[-1].strftime("%Y-%m-%d"))) + "(미국 시간)"
    p = dk.write_mock(all_stocks(data), os.path.join(OUT, "mock_all_stocks.html"), "전체 종목")
    print("만듦:", p)


if __name__ == "__main__":
    main()
