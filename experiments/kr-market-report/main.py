"""한국 증시 리포트 — 장 마감 뒤 오늘 한국장 정리 (doc/기획/한국-증시-리포트-기획.md).
    python experiments/kr-market-report/main.py --cached   # kr-stocks 가 받아 둔 것(data/*.json)으로 그리기만
    python experiments/kr-market-report/main.py --cached --news-hours 120   # 방송 소식 샘플을 최근 5일치로 (지난 날 목업용)
결과 output/report_body.html (본문) · output/kr_report_mock.html (블로그 테마를 입힌 목업).

새로 모으는 자료 없음 — kr-stocks 수집 · 분석(analyze_kr.run) 결과를 받는다. AI 0회.
카드는 미국 데일리(질문 카드 · 막대, daily-report/cards.py)와 한국 목록 페이지(외국인 · 거래 · 금리 카드, render_kr)의 것을 그대로 쓴다.
툴팁은 뜻 · 오늘 두 줄 — 검증 결과(`기록상` 줄 · 관계 없음 안내)는 쓰지 않는다 (2026-11-01 가이드라인 1절 4-2).
"""
import datetime
import importlib.util
import json
import os
import re
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_KR = os.path.join(_HERE, "..", "kr-stocks")
sys.path.insert(0, _KR)
import analyze_kr  # noqa: E402
import collect_kr  # noqa: E402
import collect_kr_extra  # noqa: E402
import collect_kr_earn_dart as ED  # noqa: E402 — 실적 발표일 = DART 잠정실적 (2026-10-31)
import render_kr as RK  # noqa: E402 — sys.path 에 nvda-report · stock-radar 를 더한다
import universe_kr as U  # noqa: E402
import people_section  # noqa: E402 — `주요 인물 발언 전체 보기` 주소 (experiments 폴더, render_kr 가 sys.path 에 둔다)

_dk, R = RK._dk, RK.R
_spec = importlib.util.spec_from_file_location("daily_cards", os.path.join(_HERE, "..", "daily-report", "cards.py"))
C = importlib.util.module_from_spec(_spec)   # 데일리 cards.py — 같은 이름 모듈(render_html 등)이 겹쳐 경로로 읽는다
_spec.loader.exec_module(C)
_spec = importlib.util.spec_from_file_location("chart_spx", os.path.join(_HERE, "..", "daily-report", "chart_spx.py"))
CS = importlib.util.module_from_spec(_spec)   # 데일리 S&P 500 그래프 — 같은 모양으로 코스피 (2026-10-26 사용자: "미국 증시처럼 코스피 주가 그래프, 요약글 아래")
_spec.loader.exec_module(CS)
IMAGE_BRANCH = RK.IMAGE_BRANCH   # 한국 종목 그래프와 같은 휘발성 브랜치 (kr-images)

OUT = os.path.join(_HERE, "output")
DAILY_URL = f"{U.BLOG}/search/label/%EB%8D%B0%EC%9D%BC%EB%A6%AC%20%EB%B8%8C%EB%A6%AC%ED%95%91"   # 미국 증시 리포트 라벨(데일리 브리핑) 목록
TAB_TODAY, TAB_STOCKS, TAB_FLOW, TAB_MARKET, TAB_CAL, TAB_NEWS = "오늘", "종목", "수급", "시장", "일정", "뉴스"   # 뉴스 = 오늘 옆 탭, 미국 증시 리포트와 같게 (M81)   # 시장 탭은 수급에서 나눔 (M11)
INDEX = {U.BENCH: "코스피", U.KOSDAQ: "코스닥"}
CAL_DAYS, EARN_DAYS = 14, 30
GROUP_SHORT = {"반도체": "반도체", "2차전지": "2차전지", "바이오": "바이오", "방산 · 조선 · 원전": "방산 · 조선"}
UP, DOWN, NOTE = _dk.UP, _dk.DOWN, _dk.NOTE


def _dir(v):
    """답의 방향 → (카드 색, 답 글자 색) — 가이드라인 7-1 카드 색 = 답의 방향 (2026-11-07 사용자 M83, 미국 market._dir 와 같다).
    오름 · 많아짐 · 높음 = 주황 카드 · 빨강 답, 내림 · 줄어듦 · 낮음 = 파랑 카드 · 파랑 답, 0 · 없음 = 회색. 색은 좋고 나쁨이 아니라 증감 방향."""
    if v is None or v == 0:
        return "neutral", "#111"
    return ("positive", UP) if v > 0 else ("negative", DOWN)


def _dir_of(signs):
    """여러 값의 방향(+1 · −1 · 0) → 방향 있는 것이 모두 같은 쪽이면 그 색, 엇갈리거나 없으면 회색."""
    ss = {x for x in signs if x}
    return _dir(ss.pop() if len(ss) == 1 else 0)
def _s(v, d=2, unit="%"):
    """부호 붙은 값 — 반올림해 0 이면 부호 없이 (`+0bp` 가 증감 색으로 칠해지지 않게)."""
    if round(v, d) == 0:
        return f"{0:.{d}f}{unit}"
    return f"{v:+,.{d}f}{unit}".replace("-", "−")


def _md(day):
    d = datetime.date.fromisoformat(day)
    return f"{d.month}월 {d.day}일"


def _times(z):
    return f"{abs(z):.1f}배"


# ── 계산 ──────────────────────────────────────────────────────────────

def _count_year(vals, v):
    """지난 1년(오늘 제외) 중 |값| 이 오늘 이상이던 날 수."""
    past = [abs(x) for x in vals[-253:-1] if x is not None]
    return sum(1 for x in past if x >= abs(v)), len(past)


def index_day(bars):
    """하루 = 시가 갭(전일 종가 → 시가, 밤사이 몫) + 장중(시가 → 종가, 한국장 몫). 평소 범위는 종목 페이지와 같은 자(A.normal_range)."""
    t, p = bars[-1], bars[-2]
    gaps = [(bars[i]["open"] / bars[i - 1]["close"] - 1) * 100 if bars[i].get("open") else None for i in range(1, len(bars))]
    intra = [(bars[i]["close"] / bars[i]["open"] - 1) * 100 if bars[i].get("open") else None for i in range(1, len(bars))]
    out = {"day": t["day"], "close": t["close"], "ret": (t["close"] / p["close"] - 1) * 100, "gap": gaps[-1], "intra": intra[-1],
           "normal": analyze_kr.A.normal_range(bars, set())}
    out["gap_n"], out["n_past"] = _count_year(gaps, gaps[-1])
    out["intra_n"], _ = _count_year(intra, intra[-1])
    return out


def group_moves(stocks, kospi_ret):
    by = {s["sym"]: s for s in stocks}
    out = []
    for g, syms in U.WATCH:
        rs = [by[x]["ret_1d"] for x in syms if x in by]
        if rs:
            out.append({"name": g, "short": GROUP_SHORT.get(g, g), "avg": sum(rs) / len(rs), "n": len(rs), "vs": sum(rs) / len(rs) - kospi_ret,
                        "best": max((by[x] for x in syms if x in by), key=lambda s: abs(s["ret_1d"]))})
    return out


def _next_kr_day(days, d, same_day=False):
    return next((x for x in days if (x >= d if same_day else x > d)), None)


def calendar(day, kospi_bars, macro_rows):
    """14일 안 시장 일정 + 지난 2년 그 일정 뒤 KOSPI 움직임(중앙값 |%|). 미국 일정은 한국 다음 거래일, 국내 옵션 만기는 그날."""
    days = [b["day"] for b in kospi_bars]
    rets = RK._abs_rets(kospi_bars)
    normal = statistics.median(list(rets.values())[-252:])
    end = (datetime.date.fromisoformat(day) + datetime.timedelta(days=CAL_DAYS)).isoformat()
    two_y = (datetime.date.fromisoformat(day) - datetime.timedelta(days=730)).isoformat()
    rows = macro_rows + RK.kr_opex(two_y, end)
    effect = {}
    for r in rows:
        if two_y <= r["day"] < day:
            k = _next_kr_day(days, r["day"], same_day=r["kind"] == "KR_OPEX")
            if k in rets:
                effect.setdefault(r["kind"], []).append(rets[k])
    eff = {k: {"median": statistics.median(v), "n": len(v)} for k, v in effect.items() if len(v) >= 3}
    up = sorted((r for r in rows if day < r["day"] <= end), key=lambda r: r["day"])
    return {"upcoming": up, "effect": eff, "normal": normal}


def earnings(day, top, snap, extra):
    """상위 10개 중 30일 안 실적 발표 + 지난 실적 날 그 종목 움직임(중앙값 |%|, 최근 2년) vs 보통 날."""
    end = (datetime.date.fromisoformat(day) + datetime.timedelta(days=EARN_DAYS)).isoformat()
    out = []
    for s in top:
        ev = (extra.get("earnings") or {}).get(s["sym"]) or []
        nd, _ = ED.next_date(s["code"], next((e["day"] for e in ev if e["day"] > day), None), day)   # 잠정실적 기준 (종목 페이지와 같은 날, 2026-10-31)
        if not nd or nd > end:
            continue
        bars = snap["bars"][s["sym"]]
        days = [b["day"] for b in bars]
        rets = RK._abs_rets(bars)
        two_y = (datetime.date.fromisoformat(day) - datetime.timedelta(days=730)).isoformat()
        past = [rets[k] for k in (ED.reaction_day(s["code"], days, d) for d in ED.past(s["code"]) if two_y <= d < day) if k in rets]
        out.append({"s": s, "day": nd, "median": statistics.median(past) if len(past) >= 3 else None, "n": len(past),
                    "normal": statistics.median(list(rets.values())[-252:])})
    return sorted(out, key=lambda x: x["day"])


def build(a, snap, extra):
    bars = snap["bars"]
    idx = {k: index_day(bars[k]) for k in INDEX if len(bars.get(k) or []) > 60}
    top = sorted((s for s in a["stocks"] if s["in_top"]), key=lambda s: s["rank"])
    kr = idx[U.BENCH]
    return {"day": a["day"], "idx": idx, "kospi_bars": bars[U.BENCH], "top": top, "groups": group_moves(a["stocks"], kr["ret"]), "market": a.get("market") or {},
            "cal": calendar(a["day"], bars[U.BENCH], RK.us_calendar()), "earn": earnings(a["day"], top, snap, extra),
            "crash": a.get("crash") or {},   # 급락장에서 버틴 종목 — 홈 `주목할 종목` 과 같은 재료 (M64)
            "sectors": sector_moves(bars), "rs": rel_strength(bars, top), "bars": bars}   # 종목 탭 업종 · 고르게 · 코스닥 대형주 (M84)


def _cl(bars, sym):
    return [x["close"] for x in (bars.get(sym) or []) if x.get("close")]


def sector_moves(bars):
    """업종 ETF 12개(U.SECTOR_ETF_LIST — 한국 종목 페이지 업계 카드와 같은 묶음)의 하루 · 5거래일 등락과 5일 순위 대비 자리 변화 — 미국 sector_card 와 같은 재료 (M84)."""
    out = []
    for e, nm in U.SECTOR_ETF_LIST.items():
        c = _cl(bars, e)
        if len(c) > 6:
            out.append({"etf": e, "label": U.SECTOR_ETF_LABEL.get(e, e), "theme": nm, "ret_1d": (c[-1] / c[-2] - 1) * 100, "ret_5d": (c[-1] / c[-6] - 1) * 100})
    r5 = {x["etf"]: i for i, x in enumerate(sorted(out, key=lambda x: -x["ret_5d"]))}
    out.sort(key=lambda x: -x["ret_1d"])
    for i, x in enumerate(out):
        x["rank_change"] = r5[x["etf"]] - i   # + = 5일 순위보다 올라섬
    return out


def rel_strength(bars, top, n=5):
    """5거래일 코스닥 − 코스피 · 시총 상위 10개 평균 − 코스피 (%p) + 코스닥이 코스피를 웃돈 연속 일수 — 미국 rs_card(나스닥 · 러셀 2000 − S&P 500) 자리 (M84)."""
    k, q = _cl(bars, U.BENCH), _cl(bars, U.KOSDAQ)
    if len(k) <= n or len(q) <= n:
        return {}
    kr = (k[-1] / k[-1 - n] - 1) * 100
    tops = [(c[-1] / c[-1 - n] - 1) * 100 for c in (_cl(bars, s["sym"]) for s in top) if len(c) > n]
    streak = 0
    for i in range(1, min(len(k), len(q))):
        if q[-i] / q[-i - 1] > k[-i] / k[-i - 1]:
            streak += 1
        else:
            break
    return {"kosdaq": (q[-1] / q[-1 - n] - 1) * 100 - kr, "top10": (sum(tops) / len(tops) - kr) if tops else None, "streak": streak, "n_top": len(tops)}


# ── 화면 ──────────────────────────────────────────────────────────────

def _overnight(r):
    return {x["sym"]: x["before"] for x in (r["market"].get("overnight") or [])}


# 한 줄 답의 결과 단어 색 (2026-10-26 사용자: "늘어나면 빨간색, 나빠지면 파란색, 평소면 회색") — " · " 덩어리마다. 비싸짐은 싸짐보다 먼저 본다
WORD_GRAY = ("비슷", "그대로", "평소 수준", "평소 안")
WORD_UP = ("늘어남", "오름", "비싸짐", "순매수", "좋아짐", "활발", "강세")
WORD_DOWN = ("줄어듦", "내림", "싸짐", "순매도", "나빠짐", "한산", "약세")


def _word_color(chunk, default):
    for words, col in ((WORD_GRAY, "#111"), (WORD_UP, UP), (WORD_DOWN, DOWN)):   # 평소 · 비슷 = 검정 (2026-11-08 사용자: 회색 카드 답은 흐린 회색 말고 검정, 옛 회색)
        if any(w in chunk for w in words):
            return col
    return default


SMALL_WORDS = ("시가", "장중")
SMALL_WORD_FS = "14px"   # 숫자 위 작은 앞말 (2026-10-26 사용자: 13 → 14, 숫자 위로)


def _qc(title, state, theme, color, lines, **kw):
    """C.question_card 와 같고, 답을 덩어리마다 결과 단어 색으로. 단어가 없는 덩어리(숫자 · 건수)는 원래 색 + 증감 색(tint).
    `시가 −2.36% · 장중 +2.72%` 처럼 앞말이 SMALL_WORDS 이면 앞말을 숫자 위에 작게 올려 칸으로 나란히 (2026-10-26 사용자: 폰에서 두 줄로 꺾였다)."""
    if "\n" in str(state):   # 답을 여러 줄로 — `방산 · 조선` / `−3.4%p`, `9월 빚투 늘어남` / `대기 자금 늘어남` (2026-11-05 사용자 M63 · M65)
        rows = []
        for ln in str(state).split("\n"):
            ch = []
            for c in ln.split(" · "):
                col = _word_color(c, None)
                ch.append(f'<span style="color:{col};">{_dk.esc(c)}</span>' if col else f'<span style="color:{color};">{_dk.tint(_dk.esc(c))}</span>')
            rows.append(f'<span style="display:block;white-space:nowrap;">{" · ".join(ch)}</span>')
        return C.question_card(title, f'<span style="display:inline-block;text-align:right;">{"".join(rows)}</span>', theme, color, lines, **kw)
    parts = str(state).split(" · ")
    if len(parts) == 1 and parts[0].partition(" ")[0] in SMALL_WORDS and parts[0].partition(" ")[2]:   # 앞말 하나면 숫자 앞에 작게, 한 줄 (2026-10-29 사용자 M58: `시가 −2.36%`)
        w, _, rest = parts[0].partition(" ")
        sign = UP if rest.startswith("+") else DOWN if rest.startswith("−") else color
        return C.question_card(title, f'<span style="white-space:nowrap;color:{sign};"><span style="font-size:{SMALL_WORD_FS};font-weight:400;margin-right:5px;">{_dk.esc(w)}</span>{_dk.esc(rest)}</span>', theme, color, lines, **kw)
    if all(p.partition(" ")[0] in SMALL_WORDS and p.partition(" ")[2] for p in parts):
        cells = []
        for p in parts:
            w, _, rest = p.partition(" ")
            sign = UP if rest.startswith("+") else DOWN if rest.startswith("−") else color
            cells.append(f'<span style="display:inline-flex;flex-direction:column;align-items:flex-start;color:{sign};">'
                         f'<span style="font-size:{SMALL_WORD_FS};line-height:18px;font-weight:400;">{_dk.esc(w)}</span><span style="line-height:24px;">{_dk.esc(rest)}</span></span>')
        return C.question_card(title, f'<span style="display:inline-flex;align-items:flex-end;gap:12px;white-space:nowrap;">{"".join(cells)}</span>', theme, color, lines, **kw)
    chunks = []
    for c in parts:
        col = _word_color(c, None)
        chunks.append(f'<span style="color:{col};">{_dk.esc(c)}</span>' if col else f'<span style="color:{color};">{_dk.tint(_dk.esc(c))}</span>')
    return C.question_card(title, '<span style="white-space:nowrap;">' + " · ".join(chunks) + "</span>", theme, color, lines, **kw)


def seo_lead(r):
    k = r["idx"][U.BENCH]
    text = (f"{_md(r['day'])} 코스피는 {k['close']:,.2f}로 전일보다 {_s(k['ret'])} 움직여 마감했습니다. "
            f"시가는 {_s(k['gap'])}로 열렸고 장중(시가 → 종가)에는 {_s(k['intra'])} 움직였습니다.")
    q = r["idx"].get(U.KOSDAQ)
    if q:
        text += f" 코스닥은 {q['close']:,.2f}, {_s(q['ret'])}입니다."
    f = r["market"].get("foreign")
    if f and f["day"] == r["day"]:
        text += f" 외국인은 유가증권시장에서 {RK.eok(f['today'])} {'순매수' if f['today'] > 0 else '순매도'}했습니다."
    return f'<p data-seo-lead="1" style="{_dk.SEO_LEAD}">{_dk.tint(_dk.esc(text))}</p>'


ZOOM_ICON = ('<svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">'
             '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5 14 14M7 5v4M5 7h4"/></svg>')


def price_chart(day, bars):
    """코스피 30거래일 봉 + 5 · 20 · 60일선 + 볼린저 PNG — 데일리 sec_chart 와 같은 모양 (누르면 확대, data-zoom). 실패하면 그래프 없이."""
    ref = f"images/kospi-price-{day}.webp"
    try:
        CS.draw([b for b in bars if b.get("open")], os.path.join(OUT, ref), symbol="KOSPI")   # 그림 글자는 영문만 (CI 에 한글 폰트 없음)
    except Exception as e:  # noqa: BLE001
        print(f"[kr-report] 코스피 그래프 실패: {str(e)[:80]}")
        return ""
    url = _dk.esc(f"https://cdn.jsdelivr.net/gh/{CS._repo_slug()}@{IMAGE_BRANCH}/{ref}")
    return (f'<a href="{url}" data-zoom="1" target="_blank" rel="noopener" title="그래프 확대 보기" aria-label="그래프 확대 보기" '
            f'style="position:relative;display:block;margin:0 0 16px;max-width:1024px;">'
            f'<img src="{url}" alt="코스피 {CS.WINDOW}거래일 봉차트" style="width:100%;display:block;border:1px solid #eee;border-radius:8px;"/>'
            f'<span style="position:absolute;right:8px;bottom:8px;display:flex;align-items:center;justify-content:center;width:32px;height:32px;'
            f'background:rgba(255,255,255,.92);border:1px solid #E2E8F0;border-radius:8px;color:#111;">{ZOOM_ICON}</span></a>'
            + _dk.intraday_chart_fold("KS11", f"https://cdn.jsdelivr.net/gh/{CS._repo_slug()}@gh-pages/live_bars.json", precision=2))   # 종목 페이지와 같은 자리 · 같은 버튼 — 코스피 15분봉 (2026-11-06 사용자 P315)


def head_chart(r):
    """머리 그래프 — 코스피 · 코스닥 하루를 시가 갭 · 장중 · 종가로 나눈 막대 (데일리 S&P 500 그래프 자리)."""
    groups = [(INDEX[k], [v["gap"], v["intra"], v["ret"]]) for k, v in r["idx"].items()]
    amber = lambda v: C.AMBER   # noqa: E731
    chart = C.chart_card("", groups, [amber, C.sign_bg, C.gray], [C.sign_fg, C.sign_fg, C.sign_fg],   # 막대 색은 구분용, 숫자는 모두 증감 색 (M6)
                         [("시가 갭", C.AMBER), ("장중", C.PASTEL_UP), ("종가", C.GRAY_BAR)], keep_legend=True)   # 하루를 나눈 조각 — 범례 그대로 (2026-10-27)
    chart = chart.replace(f"margin:0 {_dk.CHART_CARD_X}px;", "margin:0;", 1)   # 카드 밖 맨 위 그래프 — 아래 질문 카드와 왼쪽 끝을 맞춘다 (2026-10-29 사용자 M37; −5px 는 색 카드 안 그래프용)
    return f'<div data-cards="1" style="margin:0 0 8px;">{chart}</div>'


def _often(n, total):
    """`지난 1년 이만큼 이상 67번` 만으로는 많은지 적은지 모른다 (2026-10-26 사용자) — 몇 날에 1번꼴인지 덧붙인다. 평범한 크기면 절반쯤(약 125번)."""
    if not n:
        return "지난 1년 중 가장 큰 크기"
    every = total / n
    return f"지난 1년 이만큼 이상 {n}번 · " + (f"{every:.0f}일에 1번꼴" if every >= 1.5 else "흔한 크기")


def open_card(r):
    """R2 왜 이렇게 시작했나 — 밤사이 미국(K24 · K25 통과 변수) → 시가 갭, 장중은 따로."""
    k = r["idx"][U.BENCH]
    ov = _overnight(r)
    ewy, sox = ov.get("EWY"), ov.get("^SOX")
    lines = []
    first = f"코스피는 {_s(k['gap'])} {'높게' if k['gap'] > 0 else '낮게'} 시작했습니다."   # `전일 종가보다` 는 시가 갭 뜻 그대로라 뺌 (2026-10-29 사용자 M33)
    if ewy and sox:
        first += f" 밤사이 미국에서 한국 주식 상장지수펀드(EWY)가 {_s(ewy['ret'])}, 미국 반도체 지수(SOX)가 {_s(sox['ret'])} 움직인 뒤였습니다."   # 미국 리포트와 같은 말 (2026-11-08, 약어 금지)
    lines.append((first, "plain"))
    same = (k["intra"] > 0) == (k["gap"] > 0)
    lines.append((f"장중에는 시가보다 {_s(k['intra'])} {'더 움직여' if same else '되돌려'} 하루 {_s(k['ret'])}로 마감했습니다.", "plain"))
    # 밤사이 미국 네 줄은 세로 막대로, 비교 대상 = 코스피 시가 갭 (2026-10-29 사용자 M34). VIX 는 포인트가 아니라 % 로 바꿔 단위를 맞춘다
    # 순서 = 코스피 시가와 관계 먼 것 → 가까운 것: 문장이 말하는 EWY · SOX 를 코스피 시가 바로 옆에, EWY(한국 주식 그 자체)가 맨 가까이 (2026-11-08 사용자)
    us = [(short, ov[t]) for t, short in (("^VIX", "VIX"), ("DX-Y.NYB", "달러지수"), ("^SOX", "SOX"), ("EWY", "EWY")) if ov.get(t)]
    pct = lambda b: b["ret"] / (b["close"] - b["ret"]) * 100 if b.get("points") and b["close"] != b["ret"] else b["ret"]   # noqa: E731
    gap_v = float(k["gap"])   # 같은 객체로 막대 색을 가른다
    groups = [(short, [pct(b)]) for short, b in us] + [("코스피 시가", [gap_v])]
    days = {b["day"] for _, b in us}
    when = f" · {_md(days.pop())} 종가" if len(days) == 1 else ""
    chart = C.chart_card(f"밤사이 미국{when} (%)", groups,
                         [lambda v: C.GRAY_BAR if v is gap_v else C.sign_bg(v)], [lambda v: NOTE if v is gap_v else C.sign_fg(v)],
                         [("비교 대상 : 코스피 시가", C.GRAY_BAR)], fmt=lambda v: _s(v, 2, ""))
    vix = ov.get("^VIX")
    if vix and vix.get("points"):
        chart += (f'<span style="display:block;margin-top:4px;font-size:{_dk.TINY};line-height:20px;color:{NOTE};word-break:keep-all;">'   # 약자 풀이 한 줄 (M44)
                  f'EWY = 한국 주식 상장지수펀드 · SOX = 미국 반도체 지수 · VIX = 변동성 지수 (포인트 변화 {_s(vix["ret"], 2, "p")}를 %로 바꿔 그림)</span>')
    lines.append((chart, "html"))
    lines.append(("row", "코스피 시가 갭", _s(k["gap"]), _often(k["gap_n"], k["n_past"])))
    lines.append(("row", "코스피 장중", _s(k["intra"]), "시가 → 종가 · " + _often(k["intra_n"], k["n_past"])))
    state = f"시가 {_s(k['gap'])}"   # `장중` 답은 뺌 (2026-10-29 사용자 M33)
    return _qc("왜 이렇게 시작했나?", state, *_dir(k["gap"]), lines)   # 툴팁 없음 — 문장 · 근거 줄(`시가 → 종가`)이 시가 갭 · 장중을 풀어 말한다 (2026-11-08 사용자: 카드와 겹치는 툴팁 생략, 가이드라인 11절)   # 오늘 탭은 모두 닫힘 (2026-11-08 사용자, 미국 오늘 탭과 같게 — 옛 P445 첫 카드 펼침)


def normal_card(r, parts=False):
    """R1 평소와 달랐나 — 데일리 normal_card 와 같은 자."""
    keys = [k for k in r["idx"] if r["idx"][k]["normal"]]
    outs = [k for k in keys if r["idx"][k]["normal"]["outside"]]
    state = "모두 평소 안" if not outs else " · ".join(INDEX[k] for k in outs) + " 평소 밖"
    lines = []
    for k in keys:
        v, n = r["idx"][k], r["idx"][k]["normal"]
        if n["outside"]:
            lines.append((f"{INDEX[k]} {_s(v['ret'])}는 평소 하루 움직임(±{n['sigma_pct']:.2f}%)의 {_times(n['z'])}로, 지난 1년에 {n['n_year']}번 있던 크기였습니다.", "plain"))
    if not outs:
        k = r["idx"][U.BENCH]
        lines.append((f"코스피 {_s(k['ret'])}는 평소 하루 움직임(±{k['normal']['sigma_pct']:.2f}%) 안이었습니다. 코스닥도 평소 범위 안이었습니다.", "plain"))
    outs_top = [s for s in r["top"] if (s.get("normal_range") or {}).get("outside")]
    lines.append((f"시총 상위 10개 중 평소 밖으로 움직인 종목은 {len(outs_top)}개입니다" + (f" ({' · '.join(s['name'] for s in outs_top)})." if outs_top else "."), "plain"))
    groups = [(INDEX[k], [r["idx"][k]["ret"], r["idx"][k]["normal"]["sigma_pct"] * (1 if r["idx"][k]["ret"] >= 0 else -1)]) for k in keys]
    lines.append((C.chart_card("오늘 움직임과 평소 하루 크기 (%)", groups, [C.sign_bg, C.gray], [C.sign_fg, C.note_fg],
                               [("오늘", C.sign_bg(r["idx"][U.BENCH]["ret"])), ("평소 하루 크기", C.GRAY_BAR)]), "html"))
    for k in keys:
        n = r["idx"][k]["normal"]
        lines.append(("row", INDEX[k], _s(r["idx"][k]["ret"]), f"평소 ±{n['sigma_pct']:.2f}% · {_times(n['z'])}"))
    k = r["idx"][U.BENCH]
    tip = ("하루 움직임이 그 지수의 평소 크기 안이었는지. 평소 크기는 최근 움직임에 무게를 더 둔 표준편차이고, 2배를 넘으면 평소 밖으로 봅니다\n"
           f"· 오늘 코스피 {_s(k['ret'])} : 평소의 {_times(k['normal']['z'])}, 지난 1년 중 이만큼 이상 움직인 날 {k['normal']['n_year']}번")
    if parts:   # `한국 증시 분위기는?` 카드 안 한 묶음 (2026-11-08 사용자 P448 — 미국 mood_card 와 같게)
        return ("평소와 달랐나?", state, *_dir_of([1 if r["idx"][x]["ret"] > 0 else -1 for x in outs]), lines, tip)
    return _qc("평소와 달랐나?", state,   # 옛 `움직임은 평소와 달랐나?` — 미국 P405 (2026-11-08)
               *_dir_of([1 if r["idx"][x]["ret"] > 0 else -1 for x in outs]), lines,   # 평소 밖 지수가 오른 쪽이면 주황 · 내린 쪽이면 파랑 · 없음 · 엇갈림 = 회색 (M83)
                tip=_dk.with_src(tip, "Yahoo Finance"))   # 펼침 = 첫 탭 첫 카드 하나만 (2026-11-08 사용자 P445)


NEWS_SHOWN = 5   # 방송은 5건만 펼쳐 두고 나머지는 `방송 n건 더 보기` (2026-10-30 사용자, 옛 3)
NEWS_HOURS = 48   # 최근 48시간 전부 (2026-10-30 사용자, 옛 24 = 그날만). 지난 날 목업에서 샘플을 보려면 --news-hours 120


def _kr_content(iss, n):
    """한국 증시 내용(media_feed.is_korea — 이슈의 국가 · 중심 종목)인 방송 이슈만, 최근 순. 어느 채널이든(매경TV · 삼성증권 · 증시각도기 · 블룸버그 …) 내용이 한국 증시면 싣는다.
    (2026-10-30 사용자. 옛 `_kr_channels` 는 한국 증시 채널 limitGroup=kr 만 — 증시각도기의 한국 시황이 빠지고, 삼성증권의 미국장 정리가 들어왔다)"""
    import media_feed   # noqa: E402 — kr_news 를 들여올 때 experiments 가 sys.path 에 더해진다 (news_section 에서만 불린다)
    out = [r for r in iss if r["category"] != "OTHER" and media_feed.is_korea(r)]
    return sorted(out, key=lambda r: str(r["published_at"]), reverse=True)[:n]


KR_PRICES = {}


def _daily_render():
    """데일리 render_html — 이름이 같은 모듈(엔비디아 render_html)이 겹쳐 경로로 읽는다. 뉴스 탭을 미국과 같은 코드로 그리려고 (M82)."""
    sys.path.insert(0, os.path.join(_HERE, "..", "daily-report"))
    spec = importlib.util.spec_from_file_location("daily_render_html", os.path.join(_HERE, "..", "daily-report", "render_html.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _prev_run_kst():
    """`N`(새 뉴스) 기준 = 지난 발행 시각(전 평일 16:10 KST) — 한국 리포트는 지난 글 상태를 따로 두지 않아 시각으로 정한다."""
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    d = now - datetime.timedelta(days=1)
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    t = d.replace(hour=16, minute=10, second=0, microsecond=0).astimezone(datetime.timezone.utc)
    return {"links": set(), "at": t.strftime("%Y-%m-%dT%H:%M")}


def news_section():
    """뉴스 탭 (2026-11-07 사용자 M80 · M81 · M82) — 미국 증시 리포트 뉴스 탭과 같은 코드(render_html.news_tab · news_pick.build):
    분야 칩 → 방향 막대(오늘 · 최근 7일) → 주요 뉴스 5줄(같은 사건 `n곳`) → 칩별 목록 · 팝업(방송 요약 다섯 줄 · 관련 종목).
    재료 = 한국 증시 내용(media_feed.is_korea) 방송 이슈 48시간. 기사는 아직 없다(한국 기사 수집 없음). AI = 같은 사건 묶기(news_stories, Groq 먼저)만 — 요약은 수집기 lines.
    읽지 못하면 자리만."""
    try:
        RH = _daily_render()
        mf, NP = RH.media_feed, RH.news_pick
        rows = [x for x in RH.kr_news.rows_now() if mf.is_korea(x)]   # 묶기 전에 한국 증시 내용만 — 미국 내용 줄과 한 이슈로 묶이지 않게
        now = datetime.datetime.now(datetime.timezone.utc)
        since7 = (now - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M")
        # 48시간 안 한국 증시 방송이 없으면 96시간까지 (2026-11-09 사용자: 월요일 16:10 은 주말이 끼어 48시간 안 한국 방송이 0 → 뉴스 탭이 비었다)
        for hours in (NEWS_HOURS, max(NEWS_HOURS, 96)):
            since = (now - datetime.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M")
            media = _kr_content(mf.issues(rows, since), 10 ** 6)
            if media:
                break
        series, names = {}, {}
        for x in media:   # 관련 종목 = 그날 한국 등락 (팝업 · 주요 뉴스 점수 `관련 자산 움직임`)
            for t in x.get("tickers") or []:
                c = mf.kr_code(t)
                if c and c in KR_PRICES:
                    names[t], series[t] = KR_PRICES[c][0], {"ret_1d": KR_PRICES[c][1]}
        built = NP.build({"news": []}, {"series": series}, media, summarize=False, prev=_prev_run_kst(),
                         all_channels={x["channel"] for x in rows if str(x["published_at"])[:16] >= since},
                         stories_cache=os.path.join(OUT, "state", "news_stories.json"), label="kr-report-stories")
        built["names"] = names
        if not built["stories"]:
            raise ValueError("뉴스 없음")
        dirs = mf.direction_counts(media)
        week = mf.direction_counts(_kr_content(mf.issues(rows, since7), 10 ** 6))
        return _dk.keep_tone(_dk.section("뉴스", RH.news_tab(built, dirs, week), tab=TAB_NEWS))   # 헤드라인체 그대로 · 탭 이름과 같은 제목은 테마가 숨긴다
    except Exception as e:  # noqa: BLE001
        print(f"[kr-report] 뉴스 못 읽음 (목업은 자리만): {str(e)[:120]}")
    # 독자 화면에 내부 안내(`뉴스 자리 — 발행 때 …`)가 나가던 것 (2026-11-09 사용자) → 독자 말 한 줄
    return _dk.section("뉴스", _dk.muted("최근 나흘 동안 한국 증시를 다룬 방송 뉴스가 없습니다."), tab=TAB_NEWS)


SORT_BTN = R.SORT_BTN
_title_with_sort = R.title_with_sort   # 목록 페이지와 같이 쓰려고 공용으로 옮김 (2026-10-29 P93)


def _top_row(s, r, first):
    n = s.get("normal_range") or {}
    sub = [f"<b>평소의 {_times(n['z'])}</b> · 1년에 {n['n_year']}번" if n.get("outside") else f"평소 ±{n['sigma_pct']:.1f}% 안" if n else ""]
    if s["tech"].get("gap") is not None:
        sub.append(f"시가 갭 {_s(s['tech']['gap'], 1)}")
    rec = U.PAIR_RECORD.get(s["sym"])
    moves = (s.get("pairs") or {}).get("moves") or []
    if rec and rec[2] and moves:   # 검증 통과한 연결만 (K17 ①)
        m = max(moves, key=lambda x: abs(x["ret"]))
        sub.append(f"밤사이 {m['sym']} {_s(m['ret'], 1)}")
    pcol = UP if s["ret_1d"] > 0 else DOWN if s["ret_1d"] < 0 else "#111"
    left = (f'<span style="display:inline-block;width:26px;color:{NOTE};font-weight:700;">{s["rank"]}</span>{RK.badge(s["sym"])}{_dk.esc(s["name"])}'
            f'<span style="display:block;padding-left:52px;font-size:{_dk.MICRO};line-height:20px;font-weight:400;color:{NOTE};">{_dk.tint(" · ".join(x for x in sub if x))}</span>')   # 보조 줄 증감 색 (M6)
    right = f'<span style="color:{pcol};">{RK.won(s["close"])}</span><br>{R._arrow(s["ret_1d"])}'
    row = R._row_html(left, right, first=first).replace(" 12px;", f" {_dk.ALIGN_PX}px;", 1)   # 카드 없이 구분선만 — 글자 시작선은 카드 밖 기준선 (M2)
    return row.replace("<span", f'<span data-row-link="1" data-href="{_dk.esc(U.page_url(s["sym"]))}" data-ret="{s["ret_1d"]:.4f}"', 1)


def top_section(r):
    """R3 시총 상위 10 — 홈 시총 TOP 10 과 겹치지 않게 **평소 밖으로 움직인 종목만 펼쳐 보이고** 나머지는 `평소 안 n개 보기` 접기 (2026-10-29 Claude 결정 M38).
    펼친 줄은 평소 범위 기준 크게 움직인 순, 오른쪽 버튼으로 상승순 · 하락순 (M3, 줄이 2개 이상일 때만 보임). 구분선만 (M2)."""
    xs = sorted(r["top"], key=lambda s: -abs((s.get("normal_range") or {}).get("z") or 0))
    outs = [s for s in xs if (s.get("normal_range") or {}).get("outside")]
    rest = [s for s in xs if s not in outs]
    rows = "".join(_top_row(s, r, i == 0) for i, s in enumerate(outs))
    rest_rows = "".join(_top_row(s, r, i == 0) for i, s in enumerate(rest))
    now = ("· 오늘 평소 밖 : " + " · ".join(f"{s['name']} {_s(s['ret_1d'])}" for s in outs)) if outs else "· 오늘 : 10개 모두 평소 범위 안"
    tip = ("한국 유가증권시장 시가총액 상위 10개 가운데 오늘 그 종목의 평소 크기 밖으로 움직인 종목. 나머지는 접어 두었고, 종가 · 등락은 홈 시총 TOP 10 에도 있습니다\n" + now)
    body = _title_with_sort("시총 상위 10개 중 평소와 다르게 움직인 종목은?", _dk.with_src(tip, "Yahoo Finance"), "kr-top10")
    if outs:
        body += f'<div style="margin:0 0 8px;font-size:{_dk.SMALL};"><span data-sort-list="kr-top10" style="display:block;">{rows}</span></div>'
    else:
        body += f'<p style="margin:0 0 8px;padding:0 {_dk.ALIGN_PX}px;color:#111;line-height:{_dk.LH_EMPH};">10개 모두 평소 범위 안이었습니다.</p>'
    if rest:
        body += _dk.fold(f"평소 안 {len(rest)}개 보기", f'<div style="font-size:{_dk.SMALL};"><span style="display:block;">{rest_rows}</span></div>')
    return body


def group_section(r):
    """R4 테마별 — 질문 카드 (2026-10-29 사용자 M45: 질문인데 답이 없었다). 답 = 코스피와 차이가 가장 큰 테마(코스피 대비 %p), 모두 1%p 안이면 `모두 코스피와 비슷`.
    펼치면 문장 → 그래프(테마 평균 vs 코스피) → 테마 줄. 묶음 = 홈 · 목록의 `테마 종목` 묶음 (M5)."""
    gs = r["groups"]
    if not gs:
        return ""
    k = r["idx"][U.BENCH]["ret"]
    top = max(gs, key=lambda g: abs(g["vs"]))
    chart = C.chart_card("테마 평균과 코스피 (%)", [(g["short"], [g["avg"], k]) for g in gs], [C.sign_bg, C.gray], [C.sign_fg, C.sign_fg],   # 코스피 막대는 회색, 숫자는 증감 색 (M6)
                         [("테마 평균", C.PASTEL_UP), ("코스피", C.GRAY_BAR)])
    if abs(top["vs"]) < 1:
        state = "모두 코스피와 비슷"
        first = f"테마 {len(gs)}개 모두 코스피와 1%p 안에서 움직였습니다. 가장 차이가 난 테마는 {top['name']}({_s(top['vs'], 1, '%p')})입니다."
    else:
        state = f"{top['short']} {_s(top['vs'], 1, '%p')}"   # 한 줄 (2026-11-08 미국 P405: 두 줄 답이 카드를 늘렸다, 옛 M63 두 줄)
        first = f"테마 {len(gs)}개 중 {top['name']}가 코스피보다 {abs(top['vs']):.1f}%p 더 {'올랐' if top['vs'] > 0 else '내렸'}습니다."
    first += f" 가장 크게 움직인 종목은 {top['best']['name']} {_s(top['best']['ret_1d'], 1)}입니다."
    lines = [(first, "plain"), (chart, "html")]
    lines += [("row", g["name"], _s(g["avg"]), f"코스피 대비 {_s(g['vs'], 2, '%p')} · 가장 크게 {g['best']['name']} {_s(g['best']['ret_1d'], 1)}") for g in gs]
    return _qc("테마의 움직임은?", state,   # 옛 `어느 테마가 움직였나?` — 미국 P405 (2026-11-08)
               *_dir(0 if abs(top["vs"]) < 1 else top["vs"]), lines)   # 툴팁 없음 — 카드와 겹침 (2026-11-08 사용자, 가이드라인 11절)


def _link_row(url, name, right_html, sub, bd, sub_html=None):
    """줄 전체 링크(data-row-link) — 질문 카드 근거 줄과 같은 글자 · 구분선 (가이드라인 10-9)."""
    return (f'<span data-row-link="1" data-href="{_dk.esc(url)}" style="display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 0;'
            f'border-top:1px solid {bd};font-size:{_dk.EMPH_Q};line-height:{_dk.LH_EMPH_Q};cursor:pointer;">'
            f'<span style="flex:1 1 auto;min-width:0;color:#111;"><span style="white-space:nowrap;">{_dk.esc(name)}</span>'
            f'<span style="display:block;margin-top:2px;font-size:{_dk.TINY};line-height:20px;color:{NOTE};">{sub_html or _dk.tint(_dk.esc(sub))}</span></span>'
            f'<span style="flex:none;font-weight:700;white-space:nowrap;">{right_html}</span></span>')


def _share_word(n, total):
    """몇 개 중 몇 개 → 말 (독자 문장에 건수 대신, 2026-11-07 사용자)."""
    f = n / total if total else 0
    return ("모두 올랐습니다" if f == 1 else "대부분 올랐습니다" if f >= 0.75 else "절반 넘게 올랐습니다" if f > 0.55 else "절반쯤 올랐습니다" if f >= 0.45
            else "절반이 못 되게 올랐습니다" if f > 0.25 else "일부만 올랐습니다" if f > 0 else "하나도 오르지 않았습니다")


def _card_rows(rows_html):
    """줄 목록을 질문 카드 안 흰 카드로 — 미국 market._rows_block 과 같은 틀."""
    return f'<span style="{_dk.MULTI}margin:0 {_dk.CHART_CARD_X}px;">{"".join(rows_html)}</span>'


def _rule_rows(rows_html, theme, n_show, label):
    """질문 카드 안 줄 목록 = 구분선 줄(15 · 보조 13) + `○○ n개 더 보기`(카드 머리 접기 버튼 모양 · 카드 폭 가득) — 미국 P400 · P417 공용 부품 (2026-11-08, 옛 M85 글자 버튼)."""
    return C.rows_fold(rows_html, n_show, label, theme)


def mega_card(r, title="상위 종목 움직임은?"):   # 옛 `시총 상위 10개 중 평소와 다르게 움직인 종목은?` — 미국 P413 과 같게 (2026-11-08 사용자)
    """시총 상위 10개 중 평소와 다르게 움직인 종목은? — 미국 market.mega_card 와 같은 질문 카드 (M84).
    M85(2026-11-07 사용자): 답 = 한 종목이면 그 종목 등락, 둘 이상이면 `n종목` · 설명 문장의 종목 이름 굵게 · 흰 카드 대신 구분선 ·
    평소 밖 종목만 보이고 나머지는 `평소 범위 안 n개 더 보기` 접기. 카드 색 = 평소 밖 종목들의 방향(엇갈리면 중립)."""
    xs = sorted(r["top"], key=lambda s: -abs((s.get("normal_range") or {}).get("z") or 0))
    if not xs:
        return ""
    outs = [s for s in xs if (s.get("normal_range") or {}).get("outside")]
    theme, ink = "neutral", "#111"
    b = lambda s: f"<b>{_dk.esc(s['name'])}</b> {_s(s['ret_1d'])}"
    if outs:
        theme, ink = _dir_of([(s["ret_1d"] > 0) - (s["ret_1d"] < 0) for s in outs])
        state = f"{outs[0]['name']} {_s(outs[0]['ret_1d'])}" if len(outs) == 1 else f"{len(outs)}종목"
        first = ("오늘 그 종목의 평소 하루 크기 밖으로 움직인 종목은 " + " · ".join(b(s) for s in outs) + "입니다. 나머지는 평소 범위 안이었습니다.")
    else:
        state = "모두 평소 범위 안"
        first = "시총 상위 10개 모두 그 종목의 평소 하루 크기 안에서 움직였습니다."
    rows = []
    for s in xs:
        n = s.get("normal_range") or {}
        sub = [f"<b>평소의 {_times(n['z'])}</b> · 1년에 {n['n_year']}번" if n.get("outside") else f"평소 ±{n['sigma_pct']:.1f}% 안" if n else ""]
        if s["tech"].get("gap") is not None:
            sub.append(f"시가 갭 {_s(s['tech']['gap'], 1)}")
        value = (_dk.arrow(s["ret_1d"]) + f'<span style="display:block;font-weight:400;font-size:{_dk.TINY};line-height:20px;color:{NOTE};">{RK.won(s["close"])}</span>')   # 가격은 등락 아래 작은 글씨 — 한 줄이면 `1,526,000원 ▲ 1.23%` 가 폰 폭을 넘어 카드가 밀렸다 (M85, Chrome 실측 457 > 420)
        row = _dk.crow(RK.badge(s["sym"]) + _dk.esc(s["name"]), value, " · ".join(x for x in sub if x), first=not rows, left=48, nowrap=True, sub_block=True)
        rows.append(row.replace("<span ", f'<span data-row-link="1" data-href="{_dk.esc(U.page_url(s["sym"]))}" ', 1))   # 줄 전체 = 종목 페이지 (가이드라인 10-9)
    label = f"평소 범위 안 {len(xs) - len(outs)}개 더 보기" if outs else f"{len(xs)}개 보기"
    # `고르게 올랐나?` 를 이 카드로 합침 (2026-11-08 사용자) — 오른 쪽이 몇 개인지(시총 상위 10개 · 업종) 문장 하나 + 줄 둘, 그 아래 종목 목록
    extra, _b_rows = _breadth_bits(r)
    if extra:
        first += " " + _dk.esc(extra)
    lines = [(first, "rich")] + [("row", nm, ud, note) for nm, ud, note in _breadth_rows(r)] + [(_rule_rows(rows, theme, len(outs), label), "html")]
    return C.end_fix(_qc(title, state, theme, ink, lines))   # 툴팁 없음 — 카드와 겹침 (2026-11-08 사용자, 가이드라인 11절)   # 펼침 = 첫 탭 첫 카드만 (P445)   # 버튼 아래 ~ 카드 끝 14


MOCK_SAMPLE = False


def mega_sample(r):
    """목업 전용 예시 — 평소 밖이 두 종목인 날 (M85). 블로그 본문(report_body.html)에는 넣지 않는다."""
    import copy
    rr = copy.deepcopy(r)
    xs = sorted(rr["top"], key=lambda s: -abs((s.get("normal_range") or {}).get("z") or 0))
    k = 0
    for s in xs:
        n = s.get("normal_range") or {}
        if not n:
            continue
        if not n.get("outside"):
            n.update(outside=True, z=max(abs(n.get("z") or 0), 2.1) * (1 if s["ret_1d"] >= 0 else -1), n_year=9)
        k += 1
        if k == 2:
            break
    return mega_card(rr, title="(목업 예시 · 두 종목) 상위 종목 움직임은?")


def sector_card(r):
    """어느 업종이 움직였나? — 미국 market.sector_card 와 같은 모양 (M84). 업종 ETF 12개 하루 막대 + 5일 순위 대비 자리. 답 = 가장 크게 움직인 업종."""
    ranked = r.get("sectors") or []
    if not ranked:
        return ""
    top, bot = ranked[0], ranked[-1]
    ups = sum(1 for x in ranked if x["ret_1d"] > 0)
    first = (f"업종은 {_share_word(ups, len(ranked))}. {'가장 오른' if top['ret_1d'] > 0 else '가장 덜 내린'} 업종은 {top['theme']} {_s(top['ret_1d'])}, "
             f"{'가장 내린' if bot['ret_1d'] < 0 else '가장 덜 오른'} 업종은 {bot['theme']} {_s(bot['ret_1d'])}입니다.")
    moved = [x for x in ranked if (x.get("rank_change") or 0) >= 3]
    if moved:
        first += " 5일 순위보다 크게 올라선 업종은 " + " · ".join(x["theme"] for x in moved) + "입니다."
    max_abs = max(abs(x["ret_1d"]) for x in ranked) or 1.0
    bars = []
    for x in ranked:
        d = x.get("rank_change")
        sub = "" if d is None else (f"5일 순위 대비 ▲{d}" if d > 0 else f"5일 순위 대비 ▼{-d}" if d < 0 else "5일 순위와 같음")
        bars.append((_dk.esc(x["theme"]), abs(x["ret_1d"]) / max_abs, UP if x["ret_1d"] >= 0 else DOWN, _dk.arrow(x["ret_1d"]), _dk.esc(" · ".join(y for y in (x["label"], sub) if y))))
    w = _dk.bar_widths([b[0] for b in bars], [b[3] for b in bars])
    rows = [_dk.bar_row(n, f, c, v, w, sb, first=(i == 0)) for i, (n, f, c, v, sb) in enumerate(bars)]
    big = max(ranked, key=lambda x: abs(x["ret_1d"]))
    # 툴팁 없음 — 카드와 겹침 (2026-11-08 사용자, 가이드라인 11절)
    # 옛 `어느 업종이 움직였나?` · 흰 상자 → 구분선 줄 15/13 · 막대 바탕 흰색 9px — 미국 P405 · P400 · P411 (2026-11-08)
    return _qc("업종의 움직임은?", f"{big['theme']} {_s(big['ret_1d'])}", *_dir(big["ret_1d"]), [(first, "plain"), (C.rows_block(rows, _dir(big["ret_1d"])[0]), "html")])


def _breadth_bits(r):
    """상위 종목 카드에 붙는 `고르게 올랐나` 문장 · 툴팁 조각 (옛 breadth_card 내용)."""
    ranked = r.get("sectors") or []
    if not ranked or not r.get("top"):
        return "", []
    up, dn = sum(1 for x in ranked if x["ret_1d"] > 0), sum(1 for x in ranked if x["ret_1d"] < 0)
    tu = sum(1 for s in r["top"] if s["ret_1d"] > 0)
    k = r["idx"][U.BENCH]["ret"]
    sent = f"시총 상위 10개는 {_share_word(tu, len(r['top']))}. 한국 주요 업종은 {_share_word(up, len(ranked))}."
    if (up > dn) != (k > 0) and up != dn:
        sent += f" 코스피는 업종 대부분과 다른 쪽이었습니다. 몇몇 큰 종목이 지수를 끌었습니다."
    return sent, [("시총 상위 10개", f"{tu}개 상승"), (f"업종 {len(ranked)}개", f"{up}개 상승")]


def _breadth_rows(r):
    ranked = r.get("sectors") or []
    if not ranked or not r.get("top"):
        return []
    ud = lambda a, b: f'<span style="display:inline-block;white-space:nowrap;"><span style="color:{UP};">▲&nbsp;{a}</span> <span style="font-weight:400;color:#9CA3AF;">/</span> <span style="color:{DOWN};">▼&nbsp;{b}</span></span>'   # noqa: E731   # 가운데 `/` 는 보통 굵기 (2026-11-08 사용자)
    tu, td = sum(1 for s in r["top"] if s["ret_1d"] > 0), sum(1 for s in r["top"] if s["ret_1d"] < 0)
    up, dn = sum(1 for x in ranked if x["ret_1d"] > 0), sum(1 for x in ranked if x["ret_1d"] < 0)
    return [("시총 상위 10개 상승 / 하락", ud(tu, td), "유가증권시장"), ("업종 상승 / 하락", ud(up, dn), f"업종 상장지수펀드 {len(ranked)}개")]


def rs_card(r, parts=False):
    """코스닥 · 대형주는 시장보다 셌나? — 미국 rs_card(기술주 · 소형주 vs S&P 500) 자리 (M84). 5거래일 코스닥 − 코스피 · 시총 상위 10개 평균 − 코스피 + 연속 일수."""
    rs = r.get("rs") or {}
    q, t = rs.get("kosdaq"), rs.get("top10")
    if q is None:
        return ""
    known = [(v, w) for v, w in ((q, "코스닥"), (t, "대형주")) if v is not None]
    strong = [w for v, w in known if v > 0]
    state = ("둘 다 강함" if len(strong) == 2 else "둘 다 약함" if not strong and len(known) == 2 else f"{strong[0]}만 강함" if strong and len(known) == 2
             else f"{known[0][1]} {'강함' if strong else '약함'}")
    sent = [f"코스닥은 코스피보다 {abs(q):.2f}%p {'앞섰' if q > 0 else '뒤졌' if q < 0 else '같았'}"]
    if t is not None:
        sent.append(f"시총 상위 10개 평균은 {abs(t):.2f}%p {'앞섰' if t > 0 else '뒤졌' if t < 0 else '같았'}")
    first = "최근 5거래일 동안 " + "고, ".join(sent) + "습니다."
    st = rs.get("streak")
    first += f" 코스닥이 코스피를 웃돈 날이 {st}일째 이어졌습니다." if st else " 오늘은 코스닥이 코스피를 웃돌지 못했습니다."
    lines = [(first, "plain"), ("row", "코스닥 − 코스피", _dk.arrow(q, 2, "%p"), "5거래일")]
    if t is not None:
        lines.append(("row", "시총 상위 10개 평균 − 코스피", _dk.arrow(t, 2, "%p"), "5거래일"))
    lines.append(("row", "코스닥이 코스피를 웃돈 연속 일수", f"{st}일", ""))
    tip = ("최근 5거래일 동안 코스닥(중소형 · 성장주) · 시총 상위 10개(대형주)가 코스피(시장 전체)보다 더 강했는지 견준 것\n"
           "· 오늘 : " + (" · ".join(strong) + " 쪽이 시장 전체보다 강했다" if strong else "둘 다 시장 전체보다 약했다") + "\n· 참고 : 값이 플러스면 앞에 적힌 쪽이 더 많이 올랐다는 뜻")
    if parts:   # 분위기 카드 안 묶음 (P448)
        return ("코스닥 · 대형주는 시장보다 셌나?", state, *_dir(len(strong) * 2 - len(known)), lines, tip)
    return _qc("코스닥 · 대형주는 시장보다 셌나?", state, *_dir(len(strong) * 2 - len(known)), lines, tip=_dk.with_src(tip, "Yahoo Finance"))


def notable_card(r):
    """급락한 날 버틴 종목은? (옛 `주목할 종목은?`, M64 → M84) — 홈 `주목할 종목`(crash_watch)과 같은 기준 위 3개. 옛 ① 평소 밖 한 종목은 시총 상위 10개 카드와 겹쳐 뺐다.
    답 = 1위 종목과 코스피 대비 %p, 카드 색 = 그 방향(버팀 = 코스피보다 위 → 주황). 줄을 누르면 종목 페이지."""
    import crash_watch as CW   # noqa: E402 — experiments/ (render_kr 가 sys.path 에 둔다)
    c = r.get("crash") or {}
    picks = [p for p in CW.notable(c) if p in U.BY_SYM][:3]
    if not picks:
        return ""
    bd = _dk.darken(_dk.lighten(_dk.lighten(C.CARD_DIR["neutral"][1]), 0.3), 0.02)
    pct = lambda v: f'<span style="color:{UP if v > 0 else DOWN if v < 0 else "#111"};">{_dk.esc(_s(v))}</span>'   # noqa: E731
    rows = "".join(_link_row(U.page_url(p), U.BY_SYM[p][1], pct(c["stocks"][p]["ret"]),
                             "", bd, sub_html=_dk.tint(_dk.esc(f"코스피보다 {_s(c['stocks'][p]['excess'], 1, '%p')} · 급락일 {c['stocks'][p]['held_total']}번 중 "))
                             + f'<span style="color:#111;">{c["stocks"][p]["held_n"]}번</span>' + " 버팀") for p in picks)   # 버틴 횟수 = 검정 (2026-11-08 사용자: 보라 그만, 옛 11-07 보라)
    top = c["stocks"][picks[0]]
    first = f"코스피가 {_md(c['day'])} {_s(c['index_ret'])} 내린 날 가장 잘 버틴 종목은 {U.BY_SYM[picks[0]][1]}로, 코스피보다 {_s(top['excess'], 1, '%p')} 앞섰습니다."
    tip = ("최근 코스피가 2% 넘게 내린 날 오르거나 덜 내려 버틴 종목(홈 주목할 종목 카드와 같은 기준) 위 3개\n"
           + "· 오늘 : " + " · ".join(U.BY_SYM[p][1] for p in picks))
    return _qc("급락한 날 버틴 종목은?", f"{U.BY_SYM[picks[0]][1]} {_s(top['excess'], 1, '%p')}",   # 한 줄 (P405)
                *_dir(top["excess"]), [(first, "plain"), (rows, "html")],
               tip=_dk.with_src(tip, "Yahoo Finance"))   # 펼침 = 첫 탭 첫 카드 하나만 (2026-11-08 사용자 P445)


# ── 수급 탭 — 질문 카드 (M7: 수치만이던 카드에 쉬운 문장 · 한 줄 답, 2026-10-26 사용자) ──

def _pos_word(v, lo, hi):
    p = (v - lo) / (hi - lo) * 100 if hi > lo else 50
    return "아래쪽 끝" if p <= 15 else "아래쪽" if p <= 40 else "가운데" if p < 60 else "위쪽" if p < 85 else "위쪽 끝"


def _bars(title, groups, fg, bg, fmt, legend_text=""):
    chart = C.col_chart(groups, [bg], [fg], fmt=fmt, right=True)   # 일별 막대 — 최신 오른쪽 (2026-10-31)
    if legend_text:   # 범례 자리 글(`날짜 : 10월 1일 ~ 23일`) — 왼쪽 5px · 넘겨 보기 오른쪽은 legend_top 이 (M40)
        chart = _dk.legend_top(chart, f'<span style="display:block;">{_dk.esc(legend_text)}</span>')
    return (f'{_dk.CHART_TITLE_M}{_dk.esc(title)}</span>'
            f'<span style="{_dk.MULTI}margin:0 {_dk.CHART_CARD_X}px;"><span style="display:block;padding:{_dk.CHART_CARD_PAD}px 12px 4px;">{chart}</span></span>')


def _day_groups(ser, scale=1e4):
    """일별 막대 — 최신 오른쪽(2026-10-31, 옛 P79 최신 왼쪽), 가로축은 날짜만, 달이 처음 나오는 막대에만 `10.23` 처럼 달을 붙인다 (2026-10-29 사용자 M40: `1 2 6 7 …` 이 무슨 숫자인지 몰랐다).
    돌려주는 것 = (groups, 범례 글 `날짜 : 10월 1일 ~ 23일`)."""
    groups, seen = [], set()
    for x in ser:
        m, d = int(x["day"][5:7]), int(x["day"][8:])
        groups.append((f"{m}.{d}" if m not in seen else str(d), [x["v"] / scale]))
        seen.add(m)
    a, b = ser[0]["day"], ser[-1]["day"]
    return groups, f"날짜 : {_md(a)} ~ {int(b[8:])}일" if a[:7] == b[:7] else f"날짜 : {_md(a)} ~ {_md(b)}"   # 같은 달이면 `10월 1일 ~ 23일`


def _flow(v, d, unit):
    """수급 값은 부호 대신 말로 — `9,778억 순매도` (2026-10-29 사용자 M42: −27.2조가 순매도인지 순매수인지 헷갈린다). 색은 design_kit.tint 가 말을 보고 칠한다."""
    if round(v, d) == 0:
        return f"0{unit} 보합"
    return f"{abs(v):,.{d}f}{unit} {'순매수' if v > 0 else '순매도'}"


def foreign_card(m):
    f = m.get("foreign")
    if not f:
        return ""
    buy, word = f["today"] > 0, "순매수" if f["today"] > 0 else "순매도"
    first = f"외국인은 {_md(f['day'])} 유가증권시장에서 {abs(f['today']):,.0f}억 원어치를 {'더 샀' if buy else '더 팔'}습니다({_s(f['today'], 0, '억')})."
    if f.get("z") is not None:
        first += f" 평소 하루 크기의 {abs(f['z']):.1f}배입니다."
    y0 = f["series"][-2] if len(f["series"]) >= 2 else None
    if y0 and y0["v"]:   # 어제와 견주기 (2026-10-29 사용자 M41)
        if (y0["v"] > 0) != buy:
            first += f" 어제 {'순매수' if y0['v'] > 0 else '순매도'}({_s(y0['v'], 0, '억')})에서 {word}로 돌아섰습니다."
        else:
            first += f" 어제({_s(y0['v'], 0, '억')})보다 {'더' if abs(f['today']) > abs(y0['v']) else '덜'} {'샀' if buy else '팔았'}습니다."
    if f["streak"] > 1:
        first += f" {f['streak']}일 연속 {'순매수' if f['streak_sign'] > 0 else '순매도'}입니다."
    lines = [(first, "plain")]
    rk = f.get("cum20_pct_rank")
    second = f"최근 20일 합계는 {_flow(f['cum20'] / 1e4, 1, '조')}입니다."   # 부호 대신 말로 (M42)
    if rk is not None:
        second += f" 과거 모든 20일 구간과 견주면 아래에서 {rk:.0f}% 지점으로, " + ("파는 쪽이 큰 편입니다." if rk <= 25 else "사는 쪽이 큰 편입니다." if rk >= 75 else "보통 범위입니다.")
    lines.append((second, "plain"))
    ser = f["series"][-15:]
    groups, when = _day_groups(ser)
    lines.append((_bars(f"최근 {len(ser)}거래일 외국인 순매수 (조 원)", groups, C.sign_fg, C.sign_bg, lambda v: _s(v, 1, ""), when), "html"))
    ks = {x["day"]: x["v"] for x in (m.get("kospi") or {}).get("series") or []}   # 같은 날 코스피 등락 — 두 번째 단 (M47)
    kd = sorted(ks)
    rets = [{"day": x["day"], "v": (ks[x["day"]] / ks[kd[kd.index(x["day"]) - 1]] - 1) * 100} for x in ser if x["day"] in ks and kd.index(x["day"]) > 0]
    if len(rets) == len(ser):
        g2, _ = _day_groups(rets, scale=1)
        lines.append((_bars("같은 날 코스피 하루 등락 (%)", g2, C.sign_fg, C.gray, lambda v: _s(v, 1, ""), "비교 대상 : 코스피 하루 등락"), "html"))
    y = f["series"][-2] if len(f["series"]) >= 2 else None
    lines.append(("row", "오늘", _flow(f["today"], 0, "억"), f"{f['streak']}일 연속 {word}" if f["streak"] > 1 else _md(f["day"])))
    if y:
        lines.append(("row", "어제", _flow(y["v"], 0, "억"), _md(y["day"])))
    lines.append(("row", "20일 합계", _flow(f["cum20"] / 1e4, 1, "조"), "최근 20거래일 순매수를 모두 더한 값(평균 아님)" + (f" · 과거 20일 구간 중 아래에서 {rk:.0f}%" if rk is not None else "")))   # M48
    lines.append(("row", "올해 합계", _flow(f["ytd"] / 1e4, 1, "조"), f"{f['day'][:4]}년 1월부터 더한 값"))
    if f.get("kosdaq_today") is not None:
        lines.append(("row", "코스닥 오늘", _flow(f["kosdaq_today"], 0, "억"), ""))
    tip = ("외국인 투자자가 유가증권시장에서 하루에 산 금액에서 판 금액을 뺀 것. 순매수 = 산 금액이 더 큼, 순매도 = 판 금액이 더 큼. 20일 합계 = 날마다의 순매수를 20일 더한 것(평균 아님)\n"
           f"· 오늘 {_flow(f['today'], 0, '억')} : 20일 합계 {_flow(f['cum20'] / 1e4, 1, '조')}")
    return _qc("외국인은 사고 있나?", f"오늘 {word}", *_dir(f["today"]), lines, tip=_dk.with_src(tip, RK.SRC))   # 펼침 = 첫 탭 첫 카드 하나만 (2026-11-08 사용자 P445)


HPAIR_BAR_H = 7   # 거래대금 가로 막대 두께 10 → 8 (2026-11-08 사용자: 세로 20% 줄임) → 7 (같은 날 10% 더, 7.2 → 정수 7)


def _hpair(items, mx):
    """가로 막대 묶음 — [(이름, 값, 색)], 같은 자(mx). 막대 끝 값 (M73)."""
    out = ""
    for lab, v, col in items:
        if not v:
            continue
        out += (f'<span style="display:flex;align-items:center;gap:8px;font-size:{_dk.TINY};line-height:22px;color:{NOTE};">'
                f'<span style="flex:none;width:60px;">{_dk.esc(lab)}</span>'
                f'<span style="flex:1 1 auto;height:{HPAIR_BAR_H}px;background:#fff;border-radius:3px;overflow:hidden;">'
                f'<span style="display:block;height:100%;width:{v / mx * 100:.0f}%;background:{col};border-radius:3px;"></span></span>'
                f'<span style="flex:none;width:48px;text-align:right;color:#111;font-weight:700;">{v / 1e4:.1f}조</span></span>')
    return f'<span style="display:block;margin:-10px 0 -4px;">{out}</span>'


def _range_bar(v, lo, hi, fmt):
    """1년 범위 막대 — 최저 ~ 최고 안 오늘 위치 (가격 범위 막대와 같은 뜻, M73)."""
    p = (v - lo) / (hi - lo) * 100 if hi > lo else 50
    return (f'<span style="display:block;margin:-6px 0 -4px;">'
            f'<span style="display:block;position:relative;height:12px;margin:0 6px;">'
            f'<span style="position:absolute;left:0;right:0;top:3px;height:6px;background:#E2E8F0;border-radius:3px;"></span>'
            f'<span style="position:absolute;left:calc({p:.1f}% - 6px);top:0;width:12px;height:12px;box-sizing:border-box;border-radius:50%;background:{_dk.CHART_MAIN};border:2px solid #fff;"></span></span>'
            f'<span style="display:flex;justify-content:space-between;font-size:{_dk.TINY};line-height:20px;color:{NOTE};margin-top:2px;">'
            f'<span>1년 최저 {_dk.esc(fmt(lo))}</span><span>최고 {_dk.esc(fmt(hi))}</span></span></span>')


def heat_card(m, parts=False):
    h, mc, n = m.get("heat"), m.get("mcap"), m.get("news")
    if not h:
        return ""
    tr = h.get("turnover_ratio") or 1
    state = "활발" if tr >= 1.5 else "한산" if tr < 0.7 else "평소 수준"
    lines = [(f"{_md(h['day'])} 유가증권시장 거래대금은 {h['turnover'] / 1e4:.1f}조 원으로 최근 20일 평균의 {tr:.1f}배였습니다. "
              + ("평소보다 거래가 많이 몰린 날입니다." if tr >= 1.5 else "평소보다 조용한 날입니다." if tr < 0.7 else "평소와 비슷한 수준입니다."), "plain")]
    if n:
        lines.append((f"뉴스심리지수는 {n['v']:.0f}로 1년 평균({n['avg_1y']:.0f})보다 {'높습니다' if n['v'] > n['avg_1y'] else '낮습니다'}. "
                      "100보다 크면 긍정적인 경제 기사가 더 많다는 뜻이고, 약 1주 늦게 나오는 실험적 통계입니다.", "plain"))
    ser = h.get("series60") or h["series"]   # 60거래일 선 — 늘고 주는 흐름이 보이게 (2026-11-05 사용자 M72, 옛 15거래일 막대)
    lines.append((_dk.trend_card(f"최근 {len(ser)}거래일 유가증권 거래대금 (조 원)", _dk.month_ticks([x["day"] for x in ser], every=1),
                                 [("거래대금", [x["v"] / 1e4 for x in ser], _dk.CHART_MAIN, "solid"),
                                  (f"1년 평균 {h['avg_1y'] / 1e4:.1f}조", [h["avg_1y"] / 1e4] * len(ser), _dk.CHART_CMP, "dash")], lambda v: f"{v:.1f}"), "html"))
    # 수치 줄 → 가로 막대 (2026-11-05 사용자 M73): 거래대금 = 오늘 · 20일 평균 한 쌍(네 막대 같은 자), 시가총액 = 1년 범위 안 위치
    pairs = [("유가증권 거래대금", h["turnover"], h.get("avg20"), f"20일 평균의 {tr:.1f}배 · 1년 중 아래에서 {h['pct_rank_1y']:.0f}%")]
    if h.get("kosdaq_turnover"):
        ka = h.get("kosdaq_avg20")
        pairs.append(("코스닥 거래대금", h["kosdaq_turnover"], ka, f"20일 평균의 {h['kosdaq_turnover'] / ka:.1f}배" if ka else ""))
    mx = max(v for _, a_, b_, _ in pairs for v in (a_, b_) if v)
    pair_lines = []
    for name, today, avg, note in pairs:
        pair_lines.append(("row", name, f"{today / 1e4:.1f}조 원", note))
        pair_lines.append((_hpair([("오늘", today, _dk.CHART_MAIN), ("20일 평균", avg, _dk.CHART_CMP)], mx), "html"))
    if parts:   # 거래대금 오늘 · 20일 평균 막대는 오늘 탭 `한국 증시 분위기는?` 안으로 (2026-11-08 사용자 P448) — 시장 탭 카드에서는 뺀다(겹침)
        tip = ("하루에 사고판 돈의 크기(거래대금)로 본 시장의 열기. 20일 평균보다 1.5배 이상이면 활발, 0.7배 아래면 한산으로 봅니다\n"
               f"· 오늘 {h['turnover'] / 1e4:.1f}조 원 : 20일 평균의 {tr:.1f}배")
        return ("시장은 얼마나 뜨겁나?", state, *_dir(1 if tr >= 1.5 else -1 if tr < 0.7 else 0), pair_lines, tip)
    if mc:
        lines.append(("row", "유가증권 시가총액", f"{mc['v'] / 1e4:,.0f}조 원", f"오늘 {_s(mc['chg_1d'])} · 1년 중 아래에서 {mc['pct_rank_1y']:.0f}%" if mc.get("chg_1d") is not None else ""))
        lines.append((_range_bar(mc["v"], mc["lo_1y"], mc["hi_1y"], lambda v: f"{v / 1e4:,.0f}조"), "html"))
    if n:
        lines.append(("row", "뉴스심리지수", f"{n['v']:.1f}", f"{_md(n['day'])} · 1년 평균 {n['avg_1y']:.1f}"))
    # 툴팁 없음 — 나누는 법(툴팁에만 있던 한 줄)을 첫 문장 아래 작은 회색 글씨로 옮겼다 (2026-11-08 사용자, 가이드라인 11절)
    lines.insert(1, ("20일 평균의 1.5배 이상이면 활발, 0.7배 아래면 한산으로 봅니다.", "note"))
    return _qc("시장은 얼마나 뜨겁나?", state, *_dir(1 if tr >= 1.5 else -1 if tr < 0.7 else 0), lines)


RATE_ROWS = (("base_rate", "한국은행 기준금리"), ("ktb3", "국고채 3년"), ("ktb10", "국고채 10년"), ("corp_aa", "회사채 AA−"), ("corp_bbb", "회사채 BBB−"))
FX_ROWS = (("usdkrw", "원/달러"), ("jpykrw100", "원/100엔"), ("cnykrw", "원/위안"))


def _on_days(x, days):
    """일별 값 → days 날짜에 맞춘 값(그날 없으면 앞 값으로 채움 — 기준금리 · 휴일)."""
    pts = sorted(((p["day"], p["v"]) for p in (x or {}).get("series") or []))
    out, j, last = [], 0, None
    for d in days:
        while j < len(pts) and pts[j][0] <= d:
            last = pts[j][1]
            j += 1
        out.append(last)
    return out


def _rate_charts(rt, fx):
    out = []
    k3, k10, base, bbb = (rt.get(k) for k in ("ktb3", "ktb10", "base_rate", "corp_bbb"))
    usd = fx.get("usdkrw")
    if k3 and k3.get("series"):
        days = [p["day"] for p in k3["series"]][-252:]
        lab = _dk.month_ticks(days, every=3)
        ser = [("국고채 3년", _on_days(k3, days), _dk.CHART_SERIES[0], "solid")]
        if k10:
            ser.append(("국고채 10년", _on_days(k10, days), _dk.CHART_SERIES[1], "solid"))
        if base:
            ser.append(("한국은행 기준금리", _on_days(base, days), _dk.CHART_CMP, "stepdash"))
        out.append((_dk.trend_card("최근 1년 국고채 금리 (%)", lab, ser, lambda v: f"{v:.2f}"), "html"))
        if bbb:
            sp = [a - b if a is not None and b is not None else None for a, b in zip(_on_days(bbb, days), _on_days(k3, days))]
            vs = [v for v in sp if v is not None]
            avg = sum(vs) / len(vs)
            out.append((_dk.trend_card("최근 1년 회사채 BBB− 와 국고채 3년 금리 차이 (%p)", lab,
                                       [("금리 차이", sp, _dk.CHART_MAIN, "solid"), (f"1년 평균 {avg:.2f}%p", [avg] * len(days), _dk.CHART_CMP, "dash")], lambda v: f"{v:.2f}"), "html"))
    if usd and usd.get("series"):
        days = [p["day"] for p in usd["series"]][-252:]
        vals = _on_days(usd, days)
        avg = sum(vals) / len(vals)
        out.append((_dk.trend_card("최근 1년 원/달러 환율 (원)", _dk.month_ticks(days, every=3),
                                   [("원/달러", vals, _dk.CHART_MAIN, "solid"), (f"1년 평균 {avg:,.0f}원", [avg] * len(days), _dk.CHART_CMP, "dash")], lambda v: f"{v:,.0f}"), "html"))
    return out


def rates_card(m):
    rt, fx = m.get("rates") or {}, m.get("fx") or {}
    k3, usd, bbb = rt.get("ktb3"), fx.get("usdkrw"), rt.get("corp_bbb")
    if not (k3 or usd):
        return ""
    st, lines, sg = [], [], []
    if k3 and k3.get("chg_n") is not None:
        bp = k3["chg_n"] * 100
        st.append("금리 내림" if bp <= -10 else "금리 오름" if bp >= 10 else "금리 그대로")
        sg.append(-1 if bp <= -10 else 1 if bp >= 10 else 0)
        lines.append((f"시장 금리(국고채 3년)는 {k3['v']:.2f}%로 20일 동안 {_s(k3['chg_n'], 2, '%p')} 움직여, 1년 범위({k3['lo_1y']:.2f}~{k3['hi_1y']:.2f}%)의 {_pos_word(k3['v'], k3['lo_1y'], k3['hi_1y'])}에 있습니다. "
                      + ("금리가 내리면 돈을 빌리는 비용이 줄어드는 쪽입니다." if bp <= -10 else "금리가 오르면 돈을 빌리는 비용이 늘어나는 쪽입니다." if bp >= 10 else "20일 동안 크게 바뀌지 않았습니다."), "plain"))
    if usd and usd.get("chg_n") is not None:
        pct = usd["chg_n"] / (usd["v"] - usd["chg_n"]) * 100
        st.append("원화 강세" if pct <= -1 else "원화 약세" if pct >= 1 else "환율 그대로")
        sg.append(-1 if pct <= -1 else 1 if pct >= 1 else 0)   # 환율 값의 증감 (원화 약세 = 환율 오름)
        lines.append((f"원/달러 환율은 {usd['v']:,.1f}원으로 20일 동안 {_s(usd['chg_n'], 1, '원')} 움직여, 1년 범위({usd['lo_1y']:,.0f}~{usd['hi_1y']:,.0f}원)의 {_pos_word(usd['v'], usd['lo_1y'], usd['hi_1y'])}에 있습니다. "
                      + ("환율이 내렸다는 건 원화 값이 올랐다는 뜻입니다." if pct <= -1 else "환율이 올랐다는 건 원화 값이 내렸다는 뜻입니다." if pct >= 1 else "원화 값은 20일 동안 크게 바뀌지 않았습니다."), "plain"))
    if bbb and k3 and bbb.get("chg_n") is not None and k3.get("chg_n") is not None:
        sp, d = bbb["v"] - k3["v"], bbb["chg_n"] - k3["chg_n"]
        lines.append((f"신용이 낮은 기업의 회사채(BBB−)와 국고채 3년의 금리 차이는 {sp:.2f}%p로 20일 전보다 {abs(d):.2f}%p {'넓어졌' if d > 0 else '좁아졌'}습니다. "
                      "차이가 넓어지면 기업이 돈을 빌리기 더 어려워졌다는 뜻입니다.", "plain"))
    lines += _rate_charts(rt, fx)   # 그래프로 그릴 수 있는 것은 그래프로 (2026-11-05 사용자 M70) — 문장 → 그래프 → 수치 줄 (M59)
    for key, name in RATE_ROWS:
        x = rt.get(key)
        if x:
            lines.append(("row", name, f"{x['v']:.2f}%", " · ".join(p for p in (f"오늘 {_s(x['chg_1d'] * 100, 0, 'bp')}" if x.get("chg_1d") is not None else "",
                                                                           f"20일 {_s(x['chg_n'] * 100, 0, 'bp')}" if x.get("chg_n") is not None else "", f"1년 {x['lo_1y']:.2f}~{x['hi_1y']:.2f}%") if p)))
    for key, name in FX_ROWS:
        x = fx.get(key)
        if x:
            lines.append(("row", name, f"{x['v']:,.1f}원", " · ".join(p for p in (f"오늘 {_s(x['chg_1d'], 1, '원')}" if x.get("chg_1d") is not None else "",
                                                                             f"20일 {_s(x['chg_n'], 1, '원')}" if x.get("chg_n") is not None else "", f"1년 {x['lo_1y']:,.0f}~{x['hi_1y']:,.0f}원") if p)))
    tip = ("시장 금리(국고채 · 회사채)와 원화 값(환율)의 지금 위치. 20일 동안 국고채 3년이 0.1%p 넘게 움직이면 내림 · 오름, 원/달러가 1% 넘게 움직이면 원화 강세 · 약세로 봅니다\n"
           "· 오늘 : " + " · ".join(st))
    return _qc("금리 · 환율은?", " · ".join(st), *_dir_of(sg), lines, tip=_dk.with_src(tip, RK.SRC))


# ── 월별 흐름 — 질문 카드 (M9: 월별 카드에도 한 줄 답 · 짧은 문장 "9월은 8월보다 …", 2026-10-26 사용자) ──

def _mo(mo):
    return f"{int(mo[5:])}월"


def _prev_mo(mo):
    y, m_ = int(mo[:4]), int(mo[5:])
    return f"{12 if m_ == 1 else m_ - 1}월"


def _qtr(q):
    return f"{q[-1]}분기"


def _cmp_word(v, prev, eps, up="늘었", down="줄었"):
    return None if prev is None or abs(v - prev) < eps else up if v > prev else down


_CHART_BLOCK = re.compile(r'<span style="display:block;border-top:1px solid #E2E8F0;padding:(?:\d+)px 12px 0;">')   # 흰 카드 안 그래프 덩어리 시작 (render_kr: MULTI_SEP + padding … 0)


def _span_end(html, i):
    """html[i] 에서 시작하는 <span …> 의 짝 </span> 바로 뒤 위치."""
    depth, k = 0, i
    for m in re.finditer(r"<span\b|</span>", html[i:]):
        depth += 1 if m.group(0) == "<span" else -1
        if depth == 0:
            return i + m.end()
    return len(html)


def _split_card(card_html):
    """옛 흰 카드 안쪽 → (수치 줄 html, [그래프 덩어리 안쪽 html])."""
    charts, rows, pos = [], "", 0
    for m in _CHART_BLOCK.finditer(card_html):
        if m.start() < pos:
            continue
        end = _span_end(card_html, m.start())
        rows += card_html[pos:m.start()]
        charts.append(card_html[m.end():end - len("</span>")])
        pos = end
    return rows + card_html[pos:], charts


def _chart_white(inner):
    """그래프 덩어리 → 제목(※)은 흰 카드 밖, 그래프만 흰 카드 (데일리 chart_card 와 같은 모양 · 여백)."""
    title = ""
    if inner.startswith(_dk.CHART_TITLE):
        e = _span_end(inner, 0)
        title, inner = _dk.CHART_TITLE_M + inner[len(_dk.CHART_TITLE):e], inner[e:]
        inner = inner.replace('<span style="display:block;height:6px;"></span>', "", 1)
    bottom = 0 if "data-chart-top" in inner else 4   # 범례 줄이 있으면 legend_top 이 아래 4px 를 둔다
    return title + f'<span style="{_dk.MULTI}margin:0 {_dk.CHART_CARD_X}px;"><span style="display:block;padding:{_dk.CHART_CARD_PAD}px 12px {bottom}px;">{inner}</span></span>'


LEVEL_BAR = _dk.CHART_MAIN   # 수준 값(PER · 배당수익률 · 풋/콜 · 거래금액)의 막대 = 주인공 주황 (2026-11-05 사용자 M74 · M75: 옛 청회색 #A7B4C6 은 비교 회색과 구분이 안 됐다)


def _cmp_chart(title, items, cmp_name, fmt, level=True):
    """달마다(또는 분기마다) 값 막대 + 회색 비교 대상 막대 (2026-10-29 사용자 M54 · M55 · M52: 월 · 분기 단위 비교 그래프).
    items = [(가로축 이름, 값, 비교 값)] 오래된 것 → 최신(최신 오른쪽, 2026-10-31). level=True 면 값 막대는 LEVEL_BAR(수준), False 면 증감 색(전년 대비 % 같은 ±값)."""
    groups = [(n, [v, c]) for n, v, c in items]
    main = (lambda v: LEVEL_BAR) if level else C.sign_bg
    lab = (lambda v: "#111") if level else C.sign_fg
    legend = ([(title.split(" (")[0].replace("최근 12개월 ", "").replace("최근 8분기 ", ""), LEVEL_BAR)] if level else []) + [(f"비교 대상 : {cmp_name}", C.GRAY_BAR)]
    return C.chart_card(title, groups, [main, C.gray], [lab, C.note_fg], legend, fmt=fmt, right=True)


def _cmp_line(title, items, cmp_name, fmt, name=None):
    """달마다 · 분기마다 수준 값의 흐름 = 선 + 비교 대상 회색 점선 (2026-11-05 사용자 M76: PER 처럼 높낮이 흐름을 보는 값은 선이 눈에 잘 들어온다).
    items = [(가로축 이름, 값, 비교 값)] 오래된 것 → 최신. 증감 값(전년 대비 % · 순매수 · 전달 대비)은 막대 그대로(_cmp_chart level=False)."""
    name = name or title.split(" (")[0]
    for w in ("최근 12개월 ", "최근 8분기 ", "최근 24개월 "):
        name = name.replace(w, "")
    return _dk.trend_card(title, [n for n, _, _ in items], [(name, [v for _, v, _ in items], _dk.CHART_MAIN, "solid"),
                                                            (cmp_name, [c for _, _, c in items], _dk.CHART_CMP, "dash")], fmt)


def _monthly_card(title, state, color, lines, sec_html, opened=False, charts_arg=(), drop_sec_charts=False, tip=True):
    """기존 카드(render_kr.sec_*)를 질문 카드 안 모양으로 (2026-10-26 사용자: "흰 카드는 막대 그래프만, 나머지 내용은 흰 카드가 있으면 안 돼") —
    수치 줄은 색 바탕 위 구분선 줄(위 외국인 · 금리 카드의 줄과 같은 글자), 그래프는 제목 밖 · 흰 카드. 툴팁은 그대로."""
    if not sec_html or "<div data-cards" not in sec_html:
        return ""
    i = sec_html.index("<div data-cards")
    body = sec_html[i:]
    a = body.index(">", body.index(f'<span style="{R.MULTI}">')) + 1   # 흰 카드 안쪽만
    inner = body[a:_span_end(body, body.index(f'<span style="{R.MULTI}">')) - len("</span>")]
    rows, charts = _split_card(inner)
    charts_extra = list(charts_arg)
    bd_row = _dk.darken(_dk.lighten(_dk.lighten(C.CARD_DIR["neutral"][1]), 0.3), 0.02)   # 질문 카드 줄 구분선과 같은 색
    pad = f"padding:{RK.PAD}px 12px;line-height:{R.LH_CARD};"
    rl = f"font-size:{_dk.EMPH_Q};line-height:{_dk.LH_EMPH_Q};"   # 근거 줄 18/30 — 종목 페이지 강조 카드 근거 줄과 같게 (2026-11-07 0-2, 옛 19/24 홀짝 어긋남)
    rows = (rows.replace(pad + R.MULTI_SEP, f"padding:10px 0;{rl}border-top:1px solid {bd_row};")
                .replace(pad + '"', f'padding:10px 0;{rl}border-top:1px solid {bd_row};"')
                .replace(f"color:#111;font-weight:700;font-size:{_dk.NAME};", "color:#111;font-weight:400;"))   # 줄 이름 = 질문 카드 줄과 같게(보통 굵기 · 카드 글자)
    # 순서 = 질문 → 답 → 설명 문장 → 그래프 → 보조 수치 줄 (2026-10-29 사용자 M59 — 옛 순서는 수치 줄이 그래프보다 먼저)
    out = list(lines) + [(c, "html") for c in charts_extra] + ([] if drop_sec_charts else [(_chart_white(c), "html") for c in charts])
    out += [(f'<span style="display:block;">{rows}</span>', "html")] if rows.strip() else []
    theme, color = color if isinstance(color, tuple) else ("neutral", color)   # color = _dir(...) 이면 (카드 색, 답 색) — 답의 방향 (M83)
    return _qc(title, state, theme, color, out, tip=RK._tip_of(sec_html[:i]) if tip else "", opened=opened)   # tip=False = 카드가 뜻 · 값을 다 말해 툴팁 생략 (2026-11-08 사용자, 가이드라인 11절)


def investors_card(m):
    im = m.get("investor_m") or {}
    who = [("foreign", "외국인"), ("inst", "기관"), ("indiv", "개인")]
    if not all(len(im.get(k) or []) >= 2 for k, _ in who):
        return ""
    mo = im["foreign"][-1]["month"]
    parts, buyers = [], []
    for k, name in who:
        v, p = im[k][-1]["v"] / 1e6, im[k][-2]["v"] / 1e6   # 백만 원 → 조 원
        if v > 0:
            buyers.append(name)
        word = "순매수" if v > 0 else "순매도"
        if (v > 0) != (p > 0):
            cmp_ = f"{_prev_mo(mo)} {'순매도' if p < 0 else '순매수'}에서 {word}로 돌아섰습니다."
        else:
            cmp_ = f"{_prev_mo(mo)}({_s(p, 1, '조')})보다 {'더 많이' if abs(v) > abs(p) else '덜'} {'샀' if v > 0 else '팔았'}습니다."
        head = f"{_mo(mo)} 유가증권시장에서 " if not parts else ""
        parts.append(f"{head}{name}은 {_s(v, 1, '조')} 원 {word}로, {cmp_}")
    lines = [(f'<span style="display:block;margin:10px 0 -6px;font-size:{_dk.TINY};line-height:20px;color:{NOTE};">(기관 · 개인은 월별 자료라 지난달까지입니다.)</span>', "html")]   # 시점이 헷갈리지 않게 (2026-10-29 사용자 M43)
    lines += [(x, "plain") for x in parts]
    if m.get("investor_share"):
        lines.append((RK.share_sentence(m["investor_share"]), "plain"))   # 거래 비중 — 지난달보다 누가 높아지고 낮아졌나 (M56)
    state = f"{_mo(mo)} " + ((" · ".join(buyers) + " 순매수") if buyers else "모두 순매도")   # 답에 달 이름 (M43)
    return _monthly_card("지난달 기관 · 개인은?", state, (_dir(1 if buyers else -1)), lines, RK.sec_investors(m), tip=False)


def funds_card(m):
    fm = m.get("funds_m") or {}
    items = [("credit_loan", "빚내서 산 돈(신용융자)", "빚투"), ("deposits", "주식을 사려고 기다리는 돈(투자자 예탁금)", "대기 자금"), ("margin_unpaid", "외상으로 산 뒤 못 갚은 돈(미수금)", None)]
    lines, st = [], []
    mo = None
    for k, name, short in items:
        x = fm.get(k)
        if not x or not x.get("prev"):
            continue
        v, p = x["last"]["v"] / 1e12, x["prev"]["v"] / 1e12
        mo = x["last"]["month"]
        pct = (v / p - 1) * 100
        w = None if abs(pct) < 1 else "늘었" if pct > 0 else "줄었"   # 1% 미만은 비슷
        lines.append((f"{name}은 {_mo(mo)} 말 {v:,.1f}조 원으로 " + (f"{_prev_mo(mo)}보다 {abs(v - p):,.1f}조 원({_s(pct, 1)}) {w}습니다." if w else f"{_prev_mo(mo)}과 거의 같습니다({_s(pct, 1)}).")
                      + f" 12개월 범위의 {_pos_word(x['last']['v'], x['lo12'], x['hi12'])}입니다.", "plain"))
        if short:
            st.append(f"{short} {'늘어남' if w == '늘었' else '줄어듦' if w == '줄었' else '비슷'}")
    if not lines:
        return ""
    charts = []
    cl, dp = fm.get("credit_loan") or {}, fm.get("deposits") or {}
    if len(cl.get("series") or []) >= 7 and len(dp.get("series") or []) >= 7:   # 달마다 전달 대비 증감 — 빚투 · 대기 자금 (M51)
        def diffs(x):
            ser = x["series"]
            return {ser[i]["month"]: (ser[i]["v"] - ser[i - 1]["v"]) / 1e12 for i in range(1, len(ser))}
        dc, dd = diffs(cl), diffs(dp)
        months = [mo_ for mo_ in sorted(dc) if mo_ in dd][-6:]
        groups = [(mo_[2:].replace("-", "."), [dc[mo_], dd[mo_]]) for mo_ in months]
        charts.append(C.chart_card("최근 6개월 전달 대비 증감 (조 원)", groups, [lambda v: _dk.CHART_SERIES[0], lambda v: _dk.CHART_SERIES[1]], [C.sign_fg, C.sign_fg],   # 여러 계열 색 (M75)
                                   [("신용융자 (빚투)", _dk.CHART_SERIES[0]), ("투자자 예탁금 (대기 자금)", _dk.CHART_SERIES[1])], fmt=lambda v: _s(v, 1, ""), right=True))
    state = f"{_mo(mo)} " + "\n".join(st)   # 두 줄 그대로 (M65) — 한 줄이면 360px 에서 제목이 한 글자씩 세로로 꺾였다 (2026-11-08 Chrome 실측, P405 예외)
    return _monthly_card("빚투 · 대기 자금은?", state, (_dir_of([1 if x.endswith("늘어남") else -1 if x.endswith("줄어듦") else 0 for x in st])), lines, RK.sec_funds(m), charts_arg=charts)   # 답에 달 이름 (M53)


def valuation_card(m):
    v = m.get("valuation") or {}
    per, dy = v.get("per"), v.get("div_yield")
    if not per:
        return ""
    mo = per["month"]
    w = _cmp_word(per["v"], per.get("prev"), 0.3, "높아졌", "낮아졌")
    first = (f"{_mo(mo)} 코스피 PER(주가 ÷ 이익)은 {per['v']:.1f}배로 " + (f"{_prev_mo(mo)}({per['prev']:.1f}배)보다 {w}습니다. " if w else f"{_prev_mo(mo)}과 비슷합니다. ")
             + ("이익에 견준 주가가 비싸진 쪽입니다. " if w == "높아졌" else "이익에 견준 주가가 싸진 쪽입니다. " if w == "낮아졌" else "")
             + f"12개월 범위의 {_pos_word(per['v'], per['lo12'], per['hi12'])}입니다.")
    lines = [(first, "plain")]
    if dy:
        dw = _cmp_word(dy["v"], dy.get("prev"), 0.02, "높아졌", "낮아졌")
        lines.append((f"배당수익률은 {dy['v']:.2f}%로 " + (f"{_prev_mo(mo)}보다 {dw}습니다." if dw else f"{_prev_mo(mo)}과 같은 수준입니다."), "plain"))
    state = f"{_mo(mo)} · {_prev_mo(mo)}보다 " + ("비싸짐" if w == "높아졌" else "싸짐" if w == "낮아졌" else "비슷")   # 답에 달 이름 (M53)
    charts = [_cmp_line("최근 12개월 KOSPI PER (배)", [(x["month"][2:].replace("-", "."), x["v"], per["avg_all"]) for x in per["series"][-12:]],
                         f"전체 기간 평균 {per['avg_all']:.1f}배", lambda v: f"{v:.1f}")]   # 비교 = 전체 평균 (M54)
    gap = v.get("yield_gap")
    if dy and gap:
        k3m = {}   # 비교 = 그달 국고채 3년 평균 — 달마다 바뀌는 채권 이자와 견준다 (M76, 옛 오늘 값 하나로 고정)
        for p_ in ((m.get("rates") or {}).get("ktb3") or {}).get("series") or []:
            k3m.setdefault(p_["day"][:7], []).append(p_["v"])
        charts.append(_cmp_line("최근 12개월 KOSPI 배당수익률 (%)", [(x["month"][2:].replace("-", "."), x["v"], (sum(k3m[x["month"]]) / len(k3m[x["month"]])) if k3m.get(x["month"]) else gap["ktb3"])
                                                                for x in dy["series"][-12:]],
                                "국고채 3년 (그달 평균)", lambda v: f"{v:.2f}"))   # 배당 vs 채권 이자 = 일드갭을 그림으로
    return _monthly_card("코스피는 비싼가?", state, (_dir(1 if w == "높아졌" else -1 if w == "낮아졌" else 0)), lines, RK.sec_valuation(m), charts_arg=charts, drop_sec_charts=True, tip=False)


def derivatives_card(m):
    d = m.get("derivatives")
    if not d or len(d.get("pc_series") or []) < 2:
        return ""
    mo, pc, prev = d["month"], d["put_call"], d["pc_series"][-2]["v"]
    w = _cmp_word(pc, prev, 0.05, "올랐", "내렸")
    lines = [(f"{_mo(mo)} 풋/콜 거래량 비율은 {pc:.2f}로 " + (f"{_prev_mo(mo)}({prev:.2f})보다 {w}습니다. " if w else f"{_prev_mo(mo)}({prev:.2f})과 비슷합니다. ")
              + ("하락에 대비하는 거래가 늘었다는 뜻입니다." if w == "올랐" else "하락에 대비하는 거래가 줄었다는 뜻입니다." if w == "내렸" else "")
              + (" 1보다 작아 오를 때 이익인 콜옵션이 더 많이 거래됐습니다." if pc < 1 else " 1보다 커서 내릴 때 이익인 풋옵션이 더 많이 거래됐습니다."), "plain")]
    state = f"{_mo(mo)} 하락 대비 " + ("늘어남" if w == "올랐" else "줄어듦" if w == "내렸" else "비슷")   # 답에 달 이름 (M53)
    charts = [_cmp_line("최근 12개월 풋/콜 거래량 비율", [(x["month"][2:].replace("-", "."), x["v"], 1.0) for x in d["pc_series"][-12:]],
                         "1.0 (풋 = 콜, 넘으면 하락 대비가 더 많음)", lambda v: f"{v:.2f}")]   # M54
    fa = d.get("fut_amt_avg")
    if fa and len(fa.get("series") or []) >= 2:
        ser = fa["series"][-12:]
        avg = sum(x["v"] for x in ser) / len(ser)
        charts.append(_cmp_line("최근 12개월 주가지수선물 하루 거래금액 (조 원)", [(x["month"][2:].replace("-", "."), x["v"] / 1e6, avg / 1e6) for x in ser],
                                 f"12개월 평균 {avg / 1e6:.1f}조", lambda v: f"{v:.1f}", name="선물 거래금액"))
    return _monthly_card("파생 시장 분위기는?", state, (_dir(1 if w == "올랐" else -1 if w == "내렸" else 0)), lines, RK.sec_derivatives(m), charts_arg=charts, drop_sec_charts=True, tip=False)


def macro_card(m):
    mac = m.get("macro") or {}
    better, worse = [], []
    for key, name, kind, sign, _ in RK.MACRO_ROWS:
        x = mac.get(key)
        if not x or x.get("prev") is None or not sign:
            continue
        d = (x["v"] - x["prev"]) * sign
        if abs(x["v"] - x["prev"]) < (0.5 if kind == "lvl" else 0.1):
            continue
        (better if d > 0 else worse).append(name.split(" (")[0])
    n = len(better) + len(worse)
    if not n:
        return ""
    lines = [(f"최근 발표된 경제 지표 가운데 직전 발표보다 좋아진 것은 {len(better)}개, 나빠진 것은 {len(worse)}개입니다. 물가는 낮아질수록 좋은 쪽으로 셉니다.", "plain")]
    if better:
        lines.append(("좋아진 것 : " + " · ".join(better), "plain"))
    if worse:
        lines.append(("나빠진 것 : " + " · ".join(worse), "plain"))
    charts = []
    ex, cpi = mac.get("exports"), mac.get("cpi")
    if ex and len(ex.get("series") or []) >= 2:   # 월별 지표라 분기 대신 12개월 (M55)
        charts.append(_cmp_line("최근 12개월 수출 전년 동월 대비 (%)", [(x["month"][2:].replace("-", "."), x["v"], ex["avg12"]) for x in ex["series"][-12:]],
                                f"12개월 평균 {_s(ex['avg12'], 1)}", lambda v: _s(v, 1, ""), name="수출 증가율"))   # 선 (2026-11-05 사용자 M78)
    if cpi and len(cpi.get("series") or []) >= 2:
        charts.append(_cmp_line("최근 12개월 소비자물가 전년 동월 대비 (%)", [(x["month"][2:].replace("-", "."), x["v"], 2.0) for x in cpi["series"][-12:]],
                                "한국은행 물가 목표 2%", lambda v: _s(v, 1, ""), name="물가 상승률"))   # 선 (M78)
    ix = (cpi or {}).get("index_series") or []
    if len(ix) >= 13:   # 물가 수준 — 우상향 선 + 해마다 2%씩 올랐다면 (2026-11-05 사용자 M71: "계속 상승하는데 우상향 그래프로 보고 싶다")
        v0, v1 = ix[0]["v"], ix[-1]["v"]
        path = [v0 * 1.02 ** (i / 12) for i in range(len(ix))]
        yrs = (len(ix) - 1) / 12
        lines.append((f"소비자물가지수는 {yrs:.0f}년 전 {v0:.1f}에서 {v1:.1f}로 {(v1 / v0 - 1) * 100:.1f}% 올랐습니다. 해마다 2%씩 올랐다면 {path[-1]:.1f}였을 것입니다.", "plain"))
        charts.append(_dk.trend_card(f"최근 {yrs:.0f}년 소비자물가지수 (2020년 = 100)", _dk.month_ticks([x["month"] for x in ix], every=6),
                                     [("소비자물가지수", [x["v"] for x in ix], _dk.CHART_MAIN, "solid"), ("해마다 2%씩 올랐다면", path, _dk.CHART_CMP, "dash")], lambda v: f"{v:.1f}"))
    return _monthly_card("경제 지표는?",   # 옛 `경제 바탕은 어떤가?` — 미국 P409 (2026-11-08)
                         f"좋아짐 {len(better)} · 나빠짐 {len(worse)}", (_dir(len(better) - len(worse))), lines, RK.sec_macro(m), charts_arg=charts, tip=False)   # 툴팁 없음 — 옛 툴팁(12개월 평균 기준 · `오래 가지 못했다` 시각)이 카드 답(직전 발표 대비)과 기준이 달랐다


def household_card(m):
    hh = m.get("household") or {}
    sur, buy, share = hh.get("hh_surplus"), hh.get("hh_stock_buy"), hh.get("hh_stock_share")
    if not sur or sur.get("yoy") is None:
        return ""
    q = sur["q"]
    lines = [(f"{_qtr(q)} 가구당 한 달에 쓰고 남은 돈(흑자액)은 {sur['v'] / 1e4:,.0f}만 원으로 1년 전 같은 분기보다 {_s(sur['yoy'], 1)} {'늘었' if sur['yoy'] > 0 else '줄었'}습니다.", "plain")]
    if buy and buy.get("same") is not None:
        lines.append((f"가계는 {_qtr(q)}에 주식을 {_s(buy['v'] / 1e3, 1, '조')} 원 {'순취득(산 쪽)' if buy['v'] > 0 else '순처분(판 쪽)'}했습니다. 1년 전 같은 분기는 {_s(buy['same'] / 1e3, 1, '조')} 원이었습니다.", "plain"))
    charts = []
    if share:   # 숫자는 빨강 굵게 + 8분기 그래프 (2026-11-05 사용자 M69: "엄청 중요한 건데")
        sq = {x["q"]: x["v"] for x in share["series"]}
        ago = sq.get(f"{int(share['q'][:4]) - 1}{share['q'][4:]}")
        lines.append((f'가계 금융자산 가운데 주식 비중은 <b style="font-weight:700;color:{UP};">{share["v"]:.1f}%</b>입니다.'
                      + (f" 1년 전 같은 분기({ago:.1f}%)보다 {abs(share['v'] - ago):.1f}%p {'높아졌' if share['v'] > ago else '낮아졌'}습니다." if ago else ""), "rich"))
        charts.append(_cmp_line("최근 8분기 가계 금융자산 중 주식 비중 (%)", [(_dk.q_axis(x["q"]), x["v"], sq.get(f"{int(x['q'][:4]) - 1}{x['q'][4:]}")) for x in share["series"][-8:]],
                                 "1년 전 같은 분기", lambda v: f"{v:.1f}", name="주식 비중"))
    state = "남는 돈 " + ("늘어남" if sur["yoy"] > 0 else "줄어듦")   # 분기 이름은 답에서 뺌 — 펼치면 문장 · 그래프 축에 있다 (2026-11-05 사용자 M68)
    byq = {x["q"]: x["v"] for x in sur.get("series_all") or sur["series"]}   # 앞 4분기의 1년 전 값까지 (M77)
    items = [(_dk.q_axis(x["q"]), x["v"] / 1e4, (byq.get(f"{int(x['q'][:4]) - 1}{x['q'][4:]}") or 0) / 1e4 or None) for x in sur["series"][-8:]]   # 비교 = 1년 전 같은 분기 (M52)
    charts.insert(0, _cmp_line("최근 8분기 가구당 월평균 흑자액 (만 원)", items, "1년 전 같은 분기", lambda v: f"{v:,.0f}", name="흑자액"))
    return _monthly_card("개인은 살 돈이 있나?", state, (_dir(sur["yoy"])), lines, RK.sec_household(m), charts_arg=charts, tip=False)


def flow_tab(r):
    """수급 탭 — 누가 사고팔았나 · 살 돈이 있나 (2026-10-26 사용자: 카드가 많아 탭을 나눔, M11). 매일 · 월별 · 분기가 섞여 있어 카드 문장에 기준 달을 적는다."""
    m = r["market"]
    body = foreign_card(m) + investors_card(m) + funds_card(m) + household_card(m)   # 소제목 줄(매일 · 달마다 · 분기마다)은 뺐다 (2026-10-29 사용자 M60) — 기준 시점은 답의 달 · 분기 이름이 말한다
    return _dk.section(TAB_FLOW, C.cards_grid(body), tab=TAB_FLOW) if body else ""


def market_tab(r):
    """시장 탭 — 시장 분위기 · 금리 환율 · 비싼가 · 파생 · 경제 바탕 (M11, 수급 탭에서 나눔)."""
    m = r["market"]
    body = heat_card(m) + rates_card(m) + valuation_card(m) + derivatives_card(m) + macro_card(m)   # 소제목 줄은 뺐다 (M60)
    return _dk.section(TAB_MARKET, C.cards_grid(body), tab=TAB_MARKET) if body else ""


def cal_card(r):
    c = r["cal"]
    up, eff = c["upcoming"], c["effect"]
    if not up:
        return _qc("다가오는 시장 일정은?", "없음", "neutral", "#111", [(f"앞으로 {CAL_DAYS}일 안에 잡힌 큰 일정이 없습니다.", "plain")], fold=False)
    names = " · ".join(f"{R._md_short(u['day'])} {RK._macro_name(u['kind'], u.get('label', ''))}" for u in up)
    lines = [(f"앞으로 {CAL_DAYS}일 안에 {names}가 있습니다.", "plain")]
    kinds = [k for k in dict.fromkeys(u["kind"] for u in up) if k in eff]
    if kinds:
        lines.append((C.chart_card("그 일정 뒤 코스피 움직임 (%)", [(RK._macro_name(k).split(" (")[-1].rstrip(")"), [eff[k]["median"], c["normal"]]) for k in kinds],
                                   [lambda v: C.AMBER, C.gray], [C.note_fg, C.note_fg], [("그 일정 뒤", C.AMBER), ("보통 날", C.GRAY_BAR)], fmt=lambda v: f"±{v:.1f}"), "html"))
    for u in up:
        e = eff.get(u["kind"]) or {}
        lines.append(("row", RK._macro_name(u["kind"], u.get("label", "")), R._md_short(u["day"]), f"코스피 보통 ±{e['median']:.1f}% ({e['n']}번)" if e else ""))
    return _qc("다가오는 시장 일정은?", f"{len(up)}건 · {CAL_DAYS}일 안", "soon", C.SOON, lines)   # 툴팁 없음 — 카드와 겹침 (2026-11-08 사용자, 가이드라인 11절)   # 펼침 = 첫 탭 첫 카드 하나만 (2026-11-08 사용자 P445)


def earn_card(r):
    es = r["earn"]
    if not es:
        return ""
    has = [e for e in es if e["median"] is not None]
    big = [e for e in has if e["median"] > e["normal"]]
    # 미국 대형주는 실적 날 2~6배였지만 한국 상위 10개는 그렇지 않았다(10-23 기준 9개 중 3개만 큼) — 문장은 데이터로 (미국 결론을 옮기지 않는다)
    lines = [(f"시총 상위 10개 중 {_dk.violet(f'{len(es)}개')}가 {EARN_DAYS}일 안에 실적을 발표합니다. 지난 실적 날 움직임이 보통 날보다 컸던 종목은 {len(has)}개 중 {_dk.violet(f'{len(big)}개')}였습니다.", "rich")]   # 몇 개 중 몇 개 = 보라 (2026-11-07 사용자)
    if has:
        lines.append((C.chart_card("지난 실적 날과 보통 날 움직임 (%)", [(e["s"]["name"], [e["median"], e["normal"]]) for e in has],
                                   [lambda v: C.AMBER, C.gray], [C.note_fg, C.note_fg], [("실적 날", C.AMBER), ("보통 날", C.GRAY_BAR)], fmt=lambda v: f"±{v:.1f}"), "html"))
    for e in es:
        lines.append(("row", e["s"]["name"], R._md_short(e["day"]), f"실적 날 보통 ±{e['median']:.1f}% ({e['n']}번) · 보통 날 ±{e['normal']:.1f}%" if e["median"] is not None else "지난 실적 날 기록 부족"))
    return _qc("상위 10개 실적 발표는?", f"{len(es)}개 · {EARN_DAYS}일 안", "soon", C.SOON, lines)   # 툴팁 없음 — 카드와 겹침 (2026-11-08 사용자, 가이드라인 11절)


# ── 오늘 탭 머리 · 분위기 · 기술지표 — 미국 증시 리포트 오늘 탭과 같은 틀 (2026-11-08 사용자 P446~P449) ──

IDX_PAD_R = 20   # 칸 오른쪽 여백 — 미국 render_html 과 같은 값 (P416)


def _ret_n(c, n):
    return (c[-1] / c[-1 - n] - 1) * 100 if len(c) > n else None


def _last5(c):
    return "".join("↑" if c[i] > c[i - 1] else "↓" if c[i] < c[i - 1] else "·" for i in range(len(c) - 5, len(c))) if len(c) > 5 else ""


def _idx_cell(name, close, ret, c):   # 칸 배경 = 그날 방향 카드 배경(오름 주황 · 내림 파랑 · 보합 회색) (2026-11-08 사용자)
    """지수 한 칸 — 이름 · `가격 ▲ 등락` 한 줄 · 아래 작은 회색 `5일 · 20일` 한 줄 · 최근 5일 (미국 _idx_cell 과 같은 모양)."""
    sub = [f"{d}일 {v:+.2f}%" for d, v in ((5, _ret_n(c, 5)), (20, _ret_n(c, 20))) if v is not None]
    lines = [_dk.tint(" · ".join(sub))] if sub else []
    l5 = _last5(c)
    if l5:
        lines.append("최근 5일 " + "".join(f'<b style="color:{UP if a == "↑" else DOWN if a == "↓" else NOTE};">{a}</b>' for a in l5))
    sub_html = "".join(f'<span style="display:block;white-space:nowrap;">{x}</span>' for x in lines)
    bg = "#fff"   # 칸 배경 흰색 — 방향 색 배경 없앰 (2026-11-08 사용자, 미국과 같게)
    return (f'<span data-idx-cell="1" style="display:block;flex:1 1 0;min-width:0;box-sizing:border-box;background:{bg};padding:{14 - _dk.VP}px {IDX_PAD_R}px {14 - _dk.VP}px 12px;">'
            f'<span style="display:block;font-weight:700;color:#111;font-size:{_dk.NAME};line-height:{_dk.LH_CARD};white-space:nowrap;">{_dk.esc(name)}</span>'
            f'<span style="display:block;margin-top:4px;line-height:25px;white-space:nowrap;"><span style="font-size:{_dk.NAME};color:#111;">{close:,.2f}</span> '
            f'<span style="font-size:{_dk.CHG_SIZE};">{_dk.small_chg(_dk.arrow(round(ret, 2)))}</span></span>'
            f'<span style="display:block;margin-top:6px;font-size:13px;line-height:19px;color:{_dk.SUB};">{sub_html}</span></span>')


def index_strip(r):
    """P446 지수 가로 카드 — 흰 카드 한 장 안에 코스피 · 코스닥 칸, 칸 사이 세로 구분선 (미국 sec_indices). 폭 = 위 막대 그래프와 같게."""
    cells, themes = [], []
    for k, nm in INDEX.items():
        if k in r["idx"]:
            cells.append(_idx_cell(nm, r["idx"][k]["close"], r["idx"][k]["ret"], _cl(r["bars"], k)))
            themes.append("neutral")   # 테두리 · 구분선도 회색 하나로 — 흰 카드 (2026-11-08 사용자, 미국과 같게)
    if not cells:
        return ""
    # 칸마다 강조 카드 모양 — 바깥선 = 그 방향 카드 테두리, 칸 사이 = 연한 구분선 (2026-11-08 사용자: 옛 회색 #E2E8F0, 미국과 같게)
    # 지수가 둘뿐이라 넘겨 보기 없이 위 막대 그래프와 같은 폭, 두 칸 반반 (2026-11-08 사용자, 미국은 4칸 넘겨 보기 P408)
    return (f'<div data-cards="1" style="margin:0 0 8px;">'
            f'<span style="display:flex;border-radius:8px;overflow:hidden;">{_dk.dir_cells(cells, themes)}</span></div>')


def _updown(v):
    return "오르고" if v > 0 else "내리고" if v < 0 else "제자리이고"


def lead(r):
    """P447 한 줄 결론(굵게) + 해설 한 문단 — 미국 sec_lead · _text_flow 자리. AI 없이 파이썬 문장 틀. 결론은 숫자 없이, 숫자는 문단에."""
    k, q = r["idx"].get(U.BENCH), r["idx"].get(U.KOSDAQ)
    if not k:
        return ""
    if q and (k["ret"] > 0) == (q["ret"] > 0):
        one = f"코스피 · 코스닥이 함께 {'오른' if k['ret'] > 0 else '내린'} 하루였습니다."
    elif q:
        one = f"코스피는 {_updown(k['ret'])} 코스닥은 {'올라' if q['ret'] > 0 else '내려'} 엇갈린 하루였습니다."
    else:
        one = f"코스피가 {'오른' if k['ret'] > 0 else '내린'} 하루였습니다."
    outs = [INDEX[x] for x in r["idx"] if (r["idx"][x].get("normal") or {}).get("outside")]
    if outs:
        one = one[:-5] + f"였고, {' · '.join(outs)} 움직임은 평소 범위를 벗어났습니다."
    sents = [f"코스피는 {k['close']:,.2f}로 {_s(k['ret'])}" + (f", 코스닥은 {q['close']:,.2f}로 {_s(q['ret'])} 마감했습니다." if q else " 마감했습니다.")]
    sec = r.get("sectors") or []
    if len(sec) >= 2:
        hi, lo = sec[0], sec[-1]
        sents.append(f"업종 가운데 가장 강한 쪽은 {hi['theme']}({_s(hi['ret_1d'])}), 가장 약한 쪽은 {lo['theme']}({_s(lo['ret_1d'])})였습니다.")
    f = (r.get("market") or {}).get("foreign")
    if f and f.get("day") == r["day"]:
        sents.append(f"외국인은 유가증권시장에서 {'순매수' if f['today'] > 0 else '순매도'}했습니다"
                     + (f"({f['streak']}일 연속)." if f.get("streak", 0) > 1 else "."))
    if r.get("top"):
        tu = sum(1 for s in r["top"] if s["ret_1d"] > 0)
        sents.append(f"시총 상위 10개는 {_share_word(tu, len(r['top']))}.")
    head = f'<div style="color:#111;font-weight:700;padding-left:{_dk.ALIGN_PX}px;">{_dk.esc(one)}</div>'
    para = (f'<div style="margin:0 0 6px;padding-left:{_dk.ALIGN_PX}px;word-break:keep-all;">'
            + " ".join(_dk.tint(_dk.esc(x)) for x in sents) + "</div>")
    return f'<div data-cards="1"><div style="margin:16px 0 8px;line-height:{_dk.LH_BODY};">{head}</div></div>' + para


def _nvda_config():
    spec = importlib.util.spec_from_file_location("nvda_config", os.path.join(_HERE, "..", "nvda-report", "config.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOOD_KIND = {"상승 추세": ("positive", UP), "단기 조정": ("neutral", "#111"), "조정장": ("negative", DOWN)}
MOOD_CHART_GAP = 26   # 미국 market.MOOD_CHART_GAP 과 같게
PART_NAME = {"지금 시장 흐름은?": ("최근 흐름", "코스피 · 20 · 50거래일 평균 가격"),
             "평소와 달랐나?": ("오늘 움직임", "코스피 · 코스닥 · 평소 대비"),   # 뜻 줄 한 줄 (360px)
             "코스닥 · 대형주는 시장보다 셌나?": ("코스닥 · 대형주", "최근 5거래일 · 코스피 대비"),
}   # ③ `거래대금 · 외국인` 머리 줄은 mood_card 가 직접 만든다   # 묶음 머리 = 짧은 명사 (미국 P404 와 같게)


def _ma(c, n):
    return sum(c[-n:]) / n if len(c) >= n else None


def kospi_flow(r):
    """최근 흐름 묶음 — 코스피가 20 · 50거래일 평균 가격 위인가 (미국 flow_card 와 같은 기준)."""
    c = _cl(r["bars"], U.BENCH)
    m20, m50 = _ma(c, 20), _ma(c, 50)
    if not (m20 and m50):
        return None
    a20, a50 = c[-1] > m20, c[-1] > m50
    state = "평균선 위" if a20 and a50 else "평균선 아래" if not a20 and not a50 else ("20일선 아래" if not a20 else "50일선 아래")
    w = c[-21:]
    ups = sum(1 for i in range(1, len(w)) if w[i] > w[i - 1])
    first = (f"코스피는 최근 20거래일 평균 가격보다 {'위' if a20 else '아래'}, 50거래일 평균 가격보다 {'위' if a50 else '아래'}에 있습니다. "
             f"20거래일 중 {ups}일 올랐고 {20 - ups}일 내렸습니다.")
    lines = [(first, "plain")] + [("row", f"{n}일 평균 가격 대비", _dk.arrow(round((c[-1] / m - 1) * 100, 2)), f"코스피 · 최근 {n}거래일 평균") for n, m in ((20, m20), (50, m50))]
    tip = f"코스피가 평균 가격선(최근 20 · 50거래일) 위에 있는지\n· 오늘 {state} : 20일선 {'위' if a20 else '아래'}, 50일선 {'위' if a50 else '아래'}"
    return ("지금 시장 흐름은?", state, *_dir(1 if a20 and a50 else -1 if not a20 and not a50 else 0), lines, tip)


def _part_row(q, state, ink, noline=False):
    name, note = PART_NAME.get(q, (q, ""))
    if str(state).startswith("<span"):
        val = state
    else:
        val = " · ".join(f'<span style="color:{_word_color(x, None) or ("#111" if ink in (NOTE, _dk.MUTED, "#999", "#9CA3AF") else ink)};">{_dk.tint(_dk.esc(x))}</span>' for x in str(state).split(" · "))
    return ("row", name, val, note) + (("noline",) if noline else ())


def mood_card(r):
    """P448 한국 증시 분위기는? — 미국 `미국 증시 분위기는?` 과 같은 규칙(1년 고점 · 200일 평균, nvda config 기준값), 값은 코스피 지수.
    변동성 지수(VKOSPI)는 모으지 않아 `불안 국면` 은 없다. 안에 묶음 넷: 최근 흐름 · 오늘 움직임(옛 `평소와 달랐나?`) · 코스닥 · 대형주(옛 종목 탭 카드) · 거래대금(시장 탭 카드에서)."""
    NC = _nvda_config()
    c = _cl(r["bars"], U.BENCH)
    if len(c) < NC.REGIME_HIGH_DAYS:
        return ""
    yr = c[-NC.REGIME_HIGH_DAYS:]
    lo, hi = min(yr), max(yr)
    ma = sum(c[-NC.REGIME_MA_DAYS:]) / NC.REGIME_MA_DAYS
    ph = (c[-1] / hi - 1) * 100
    phr = round(ph, 1)
    regime = "조정장" if phr <= NC.REGIME_CORRECTION_PCT or c[-1] < ma else "단기 조정" if phr <= NC.REGIME_PULLBACK_PCT else "상승 추세"
    theme, ink = MOOD_KIND[regime]
    line_col = _dk.darken(_dk.lighten(_dk.lighten(C.CARD_DIR[theme][1]), 0.3), 0.02)
    where = "1년 최고가 근처" if ph > -0.5 else f"1년 최고가보다 {abs(ph):.1f}% 아래"
    lines = [(f"1년 고점과 200일 평균으로 보면 코스피는 {where}이고, 200일 평균 가격보다 {'위' if c[-1] >= ma else '아래'}에 있습니다.", "plain")]
    # 묶음 셋 = 머리 줄(이름 · 답) 위에만 선, 묶음 안 수치 줄은 선 없이 촘촘히(tight), 둘째 묶음부터 위 여백(gap) (2026-11-08 사용자: 정보가 산발적 · 중복)
    # ① 최근 흐름 — 1년 범위 막대 · 20 · 50일 평균 가격 대비
    fl = kospi_flow(r)
    if fl:
        lines.append(_part_row(fl[0], fl[1], fl[3]))
    if hi > lo:
        at = lambda v: (v - lo) / (hi - lo) * 100  # noqa: E731
        hd = len(yr) - 1 - max(range(len(yr)), key=lambda i: yr[i])
        legend = "최고가 대비" + (" (오늘)" if hd <= 0 else f" ({hd}거래일 전)")
        lines.append((C.range_gauge(lo, hi, at(c[-1]), round(ph, 2), lambda v: f"{v:,.0f}", "", "가격 범위 (1년)", legend, "최고가 근처", marks=[("", at(ma))]), "html"))
    if fl:
        lines += [x + ("tight",) for x in fl[4] if x[0] == "row"]
    # ② 오늘 움직임 — 그래프 · 문장 하나 · 코스피 · 코스닥(평소 배수) · 5거래일 코스피 대비(옛 `코스닥 · 대형주` 묶음)
    nm = normal_card(r, parts=True)
    keys = [x for x in r["idx"] if r["idx"][x].get("normal")]
    if nm and keys:
        lines.append(_part_row(nm[0], nm[1], nm[3]) + ("gap",))
        lines += [x for x in nm[4] if isinstance(x, tuple) and len(x) == 2 and x[1] == "html"]
        outs = [x for x in keys if r["idx"][x]["normal"]["outside"]]
        eun = lambda n: n + ("은" if (ord(n[-1]) - 0xAC00) % 28 else "는")  # noqa: E731
        sent = ("코스피 · 코스닥 모두 평소 하루 움직임 안이었습니다." if not outs else
                " ".join(f"{eun(INDEX[x])} 평소 하루 움직임의 {_times(r['idx'][x]['normal']['z'])}로 평소 밖이었습니다." for x in outs))
        rs = r.get("rs") or {}
        q5, t5 = rs.get("kosdaq"), rs.get("top10")
        cmp_ = lambda v, who: f"{who} 코스피와 비슷했" if abs(v) < 0.5 else f"{who} 코스피보다 {'강했' if v > 0 else '약했'}"  # noqa: E731
        rel = [cmp_(v, w) for v, w in ((q5, "코스닥은"), (t5, "시총 상위 10개 평균은")) if v is not None]
        if rel:
            sent += " 최근 5거래일 동안 " + "고, ".join(rel) + "습니다."
        if rs.get("streak", 0) >= 2:
            sent += f" 코스닥이 코스피를 웃돈 날이 {rs['streak']}일째입니다."
        lines.append((sent, "plain"))
        for x in keys:
            n = r["idx"][x]["normal"]
            lines.append(("row", INDEX[x], _s(r["idx"][x]["ret"]), f"평소 ±{n['sigma_pct']:.2f}% · {_times(n['z'])}", "tight"))
        if q5 is not None:
            lines.append(("row", "코스닥 − 코스피", _dk.arrow(round(q5, 2), 2, "%p"), "5거래일", "tight"))
        if t5 is not None:
            lines.append(("row", "시총 상위 10개 − 코스피", _dk.arrow(round(t5, 2), 2, "%p"), "5거래일", "tight"))
    # ③ 거래대금 · 외국인 — 금액은 줄에 한 번만
    ht = heat_card(r["market"], parts=True) if (r["market"] or {}).get("heat") else None
    f = (r.get("market") or {}).get("foreign")
    has_f = bool(f and f.get("today") is not None)
    if ht or has_f:
        ans = ([f"거래 {ht[1]}"] if ht else []) + ([f"외국인 {'순매수' if f['today'] > 0 else '순매도'}"] if has_f else [])
        ans_html = "".join(f'<span style="display:block;white-space:nowrap;">{_part_row("", a_, NOTE)[2]}</span>' for a_ in ans)   # 답 둘은 두 줄 — 한 줄이면 이름 · 뜻이 눌린다 (360px)
        lines.append(("row", "거래대금 · 외국인", f'<span style="display:inline-block;text-align:right;">{ans_html}</span>', "유가증권 · 코스닥 · 하루", "gap"))
        if ht:
            lines += [x + ("tight",) if x[0] == "row" else x for x in ht[4]]
        if has_f:
            lines.append(("row", "외국인 유가증권", _flow(f["today"], 0, "억"), "", "tight"))   # 날짜는 머리 줄 `하루` 와 리포트 날짜가 말한다
            if f.get("kosdaq_today") is not None:
                lines.append(("row", "외국인 코스닥", _flow(f["kosdaq_today"], 0, "억"), "", "tight"))
    pb, cr = abs(NC.REGIME_PULLBACK_PCT), abs(NC.REGIME_CORRECTION_PCT)
    tip = ("한국 시장 전체(코스피)가 오르는 흐름인지, 쉬어 가는지, 흔들리는지. 미국 증시 리포트 `미국 증시 분위기는?` 과 같은 기준\n"
           f"· 오늘 {regime} : 코스피가 {where}, 200일 평균보다 {'위' if c[-1] >= ma else '아래'}\n"
           f"· 나누는 법 : 고점에서 {pb:.0f}% 안이면 상승 추세, {pb:.0f}~{cr:.0f}% 아래면 단기 조정, {cr:.0f}% 넘게 빠지거나 200일 평균 아래면 조정장")
    return C.question_card("한국 증시 분위기는?", regime, theme, ink, lines, tip=_dk.with_src(tip, "Yahoo Finance"))


def index_tech_card(r):
    """P449 지수 기술지표의 방향은? — 코스피 · 코스닥 라벨 전환 (미국 market.index_tech_card 와 같은 모양 · 같은 지표 · tech_signals). 답 · 색 = 코스피. 정보 전달만(가이드라인 1절 4-2)."""
    import tech_signals as TS
    tx = {k: TS.compute(r["bars"][k]) for k in INDEX if r["bars"].get(k)}
    keys = [k for k in INDEX if tx.get(k)]
    if not keys:
        return ""
    head = tx[keys[0]]
    theme, ink = TS.theme(head["net"], UP, DOWN, _dk.MUTED)
    line_col = _dk.darken(_dk.lighten(_dk.lighten(C.CARD_DIR[theme][1]), 0.3), 0.02)
    k5 = _ret_n(_cl(r["bars"], U.BENCH), 5)
    panels = []
    for n, k in enumerate(keys):
        c = _cl(r["bars"], k)
        rows = []
        x = r["idx"].get(k) or {}
        if x.get("normal"):
            rows.append(f'<span>하루 등락 <span style="font-size:{TS.WHY_FS};color:#6B7280;">평소 ±{x["normal"]["sigma_pct"]:.2f}%의 {_times(x["normal"]["z"])}</span></span><b>{_dk.arrow(round(x["ret"], 2))}</b>')
        for d in (20, 50):
            m = _ma(c, d)
            if m:
                rows.append(f'<span>{d}일 평균 가격 대비</span><b>{_dk.arrow(round((c[-1] / m - 1) * 100, 2))}</b>')
        w = c[-20:]
        fh, fl = (c[-1] / max(w) - 1) * 100, (c[-1] / min(w) - 1) * 100
        word = "고점 부근" if fh > -1 else "저점 부근" if fl < 1 else "박스 중간"
        rows.append(f'<span>20일 위치 <span style="font-size:{TS.WHY_FS};color:#6B7280;">{_dk.tint(_dk.esc(f"고점 {_s(fh)} · 저점 {_s(fl)}"))}</span></span><b>{word}</b>')
        if k != U.BENCH and k5 is not None and _ret_n(c, 5) is not None:
            rows.append(f'<span>코스피 대비 <span style="font-size:{TS.WHY_FS};color:#6B7280;">5거래일</span></span><b>{_dk.arrow(round(_ret_n(c, 5) - k5, 2), 2, "%p")}</b>')
        tl, _ = TS.card(tx[k], INDEX[k], UP, DOWN, _dk.MUTED)
        flow = TS._sub("오늘 · 흐름") + TS._table(rows, line_col)
        body_ = "".join(f'<div style="margin:0 0 12px;">{(flow if i == 1 else "") + h}</div>' for i, (h, _k) in enumerate(tl))
        panels.append(f'<div data-ixp="{n}"{"" if n == 0 else " hidden"}>{body_}</div>')
    last = len(keys) - 1

    def chip(i, k):
        return (f'<button type="button" data-chip="{_dk.esc(INDEX[k])}" data-ixc="{i}" aria-pressed="{"true" if i == 0 else "false"}" style="flex:1 0 auto;padding:6px 14px;margin:0;background:#fff;color:#333;font:inherit;'
                f'font-size:{_dk.TINY};line-height:{_dk.LH_TINY};cursor:pointer;white-space:nowrap;border:1px solid #E2E8F0;{"border-left:0;" if i else ""}'
                f'border-radius:{"7px" if i == 0 else "0"} {"7px" if i == last else "0"} {"7px" if i == last else "0"} {"7px" if i == 0 else "0"};">{_dk.esc(INDEX[k])}</button>')
    chips = (f'<div data-ix-chips="1" style="display:flex;overflow-x:auto;margin:6px 0 4px;-webkit-overflow-scrolling:touch;scrollbar-width:none;">'
             + "".join(chip(i, k) for i, k in enumerate(keys)) + "</div>")
    js = ("<script>(function(){var s=document.currentScript,b=s&&s.parentNode;if(!b)return;var cs=b.querySelectorAll('[data-ixc]'),ps=b.querySelectorAll('[data-ixp]');"
          "[].forEach.call(cs,function(c){c.addEventListener('click',function(){var i=c.getAttribute('data-ixc');"
          "[].forEach.call(cs,function(x){x.setAttribute('aria-pressed',x===c?'true':'false');});"
          "[].forEach.call(ps,function(p){p.hidden=p.getAttribute('data-ixp')!==i;});});});})();</script>")
    tip = ("코스피 · 코스닥의 오늘 움직임 · 평균 가격선 · 최근 한 달 자리와, 종목 페이지와 같은 기술지표 · 이동평균이 가리키는 방향. 라벨을 누르면 그 지수로 바뀝니다. 답은 코스피 기준\n"
           f"· 오늘 코스피 {head['word']} : 상승 − 하락을 전체로 나눈 값이 +0.5 넘으면 강한 상승, +0.15 넘으면 상승, −0.15 ~ +0.15 중립, 그 아래 하락 · 강한 하락")
    return C.question_card("지수 기술지표의 방향은?", head["word"], theme, ink, [(f'<div data-ix-tech="1">{chips}{"".join(panels)}{js}</div>', "html")], tip=_dk.with_src(tip, "Yahoo Finance"))



def body(r):
    parts = [
        _dk.WRAP_OPEN,
        _dk.report_stamp(_md(r["day"]), "오후 4시 10분 무렵"),   # 시계 줄 — 종목 페이지와 같게 (2026-11-05 사용자 M62)
        seo_lead(r),
        price_chart(r["day"], r["kospi_bars"]),   # 요약 바로 아래 (데일리의 S&P 500 그래프 자리)
        index_strip(r),   # 지수 가로 카드 = 오늘 탭 바로 아래, 막대 그래프 위 (2026-11-08 사용자 — 미국과 같은 자리, 옛 P446 막대 아래)
        head_chart(r),   # 제목 글자 없이 그래프만 (2026-10-26 사용자, M19)
        lead(r),   # 한 줄 결론 + 해설 문단 (P447, AI 없음)
        _dk.section(TAB_TODAY, C.cards_grid(open_card(r) + mood_card(r) + index_tech_card(r)), tab=TAB_TODAY),   # `평소와 달랐나?` 는 분위기 카드 안으로 (P448) · 기술지표 카드 (P449)
        news_section(),   # 뉴스 탭 = 오늘 바로 다음 (미국과 같은 자리, M81)
        _dk.section(TAB_STOCKS, C.cards_grid(group_section(r) + sector_card(r) + mega_card(r) + (mega_sample(r) if MOCK_SAMPLE else "") + notable_card(r)), tab=TAB_STOCKS),   # 미국 종목 카드처럼 질문 카드 6개, 테마가 먼저 (M46 · M84)
        flow_tab(r),
        market_tab(r),
        _dk.section(TAB_CAL, C.cards_grid(cal_card(r) + earn_card(r)), tab=TAB_CAL),
        RK.related(links=[("한국 시가총액 상위 10개 종목 주가", U.LIST_URL), ("미국 증시 리포트", DAILY_URL), ("미국 시가총액 상위 10개 종목 주가", U.US_LIST_URL),
                           ("주요 인물 발언 전체 보기", people_section.ALL_URL)]),   # 인물 발언 전체 목록도 함께 보는 페이지에 (2026-11-08 사용자)
        _dk.WRAP_CLOSE,   # 출처 · 면책 꼬리말 없음 — 블로그 공통 푸터
    ]
    return _dk.formal(_dk.fix_colons(_dk.align_titles("\n".join(p for p in parts if p))))


def title(day):
    return "한국 증시 리포트"   # 날짜 · '코스피 마감' 은 뺀다 (2026-10-26 사용자, M1) — 날짜는 맨 앞 요약에


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cached = "--cached" in sys.argv
    if "--news-hours" in sys.argv:
        NEWS_HOURS = int(sys.argv[sys.argv.index("--news-hours") + 1])
    snap, flows, hist = collect_kr.load() if cached else collect_kr.run()
    if snap is None:
        print("[kr-report] 시세 없음 — 자료 지연")
        sys.exit(0)
    a = analyze_kr.run(snap, flows, hist)
    KR_PRICES = {s["code"]: (s["name"], s.get("ret_1d")) for s in a["stocks"] if s.get("ret_1d") is not None}   # 방송 팝업 `관련 종목` (P355)
    extra = collect_kr_extra.load() if cached else collect_kr_extra.run()
    r = build(a, snap, extra or {})
    html = body(r)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "report_body.html"), "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:   # 게시 단계(publish_report.py)가 읽는다
        json.dump({"day": r["day"], "title": title(r["day"])}, f, ensure_ascii=False)
    MOCK_SAMPLE = True   # 목업에만 두 종목 예시 (M85) — 블로그 본문(report_body.html)은 위에서 이미 씀
    mock_html = body(r)
    mock = _dk.write_mock(mock_html, os.path.join(OUT, "kr_report_mock.html"), title(r["day"]))
    print(f"[kr-report] {r['day']} · {title(r['day'])} → {mock}")
