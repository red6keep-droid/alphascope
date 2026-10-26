"""한국 증시 리포트 — 장 마감 뒤 오늘 한국장 정리 (doc/기획/한국-증시-리포트-기획.md).
    python experiments/kr-market-report/main.py --cached   # kr-stocks 가 받아 둔 것(data/*.json)으로 그리기만
    python experiments/kr-market-report/main.py --cached --news-hours 120   # 방송 소식 샘플을 최근 5일치로 (지난 날 목업용)
결과 output/report_body.html (본문) · output/kr_report_mock.html (블로그 테마를 입힌 목업).

새로 모으는 자료 없음 — kr-stocks 수집 · 분석(analyze_kr.run) 결과를 받는다. AI 0회.
카드는 미국 데일리(질문 카드 · 막대, daily-report/cards.py)와 한국 목록 페이지(외국인 · 거래 · 금리 카드, render_kr)의 것을 그대로 쓴다.
`기록상` 은 2026-10-25 검증 통과한 것만 (밤사이 미국 → 다음날 시가) — 관계 없던 것은 universe_kr.NO_RECORD 문구 그대로 (기획 3절).
"""
import datetime
import importlib.util
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
import render_kr as RK  # noqa: E402 — sys.path 에 nvda-report · stock-radar 를 더한다
import universe_kr as U  # noqa: E402

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
TAB_TODAY, TAB_STOCKS, TAB_FLOW, TAB_MARKET, TAB_CAL = "오늘", "종목", "수급", "시장", "일정"   # 시장 탭은 수급에서 나눔 (M11)
INDEX = {U.BENCH: "코스피", U.KOSDAQ: "코스닥"}
CAL_DAYS, EARN_DAYS = 14, 30
GROUP_SHORT = {"반도체": "반도체", "2차전지": "2차전지", "바이오": "바이오", "방산 · 조선 · 원전": "방산 · 조선"}
UP, DOWN, NOTE = _dk.UP, _dk.DOWN, _dk.NOTE
def _s(v, d=2, unit="%"):
    """부호 붙은 값 — 반올림해 0 이면 부호 없이 (`+0bp` 가 증감 색으로 칠해지지 않게)."""
    if round(v, d) == 0:
        return f"{0:.{d}f}{unit}"
    return f"{v:+,.{d}f}{unit}".replace("-", "−")


def _md(day):
    d = datetime.date.fromisoformat(day)
    return f"{d.month}월 {d.day}일"


def _rec(text):
    """기록상 문구(universe_kr.NO_RECORD, 반말)를 합니다체로 — "없었다 (2004~2026)" 처럼 괄호가 붙으면 design_kit.formal 이 못 바꾼다."""
    return re.sub(r"([었았])다 \(", r"\1습니다 (", text)


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
        nxt = next((e for e in ev if day < e["day"] <= end), None)
        if not nxt:
            continue
        bars = snap["bars"][s["sym"]]
        days = [b["day"] for b in bars]
        rets = RK._abs_rets(bars)
        past = [rets[k] for k in (_next_kr_day(days, e["day"], same_day=e.get("when") != "amc") for e in ev if e["day"] < day) if k in rets]
        out.append({"s": s, "day": nxt["day"], "median": statistics.median(past) if len(past) >= 3 else None, "n": len(past),
                    "normal": statistics.median(list(rets.values())[-252:])})
    return sorted(out, key=lambda x: x["day"])


def build(a, snap, extra):
    bars = snap["bars"]
    idx = {k: index_day(bars[k]) for k in INDEX if len(bars.get(k) or []) > 60}
    top = sorted((s for s in a["stocks"] if s["in_top"]), key=lambda s: s["rank"])
    kr = idx[U.BENCH]
    return {"day": a["day"], "idx": idx, "kospi_bars": bars[U.BENCH], "top": top, "groups": group_moves(a["stocks"], kr["ret"]), "market": a.get("market") or {},
            "cal": calendar(a["day"], bars[U.BENCH], RK.us_calendar()), "earn": earnings(a["day"], top, snap, extra)}


# ── 화면 ──────────────────────────────────────────────────────────────

def _overnight(r):
    return {x["sym"]: x["before"] for x in (r["market"].get("overnight") or [])}


# 한 줄 답의 결과 단어 색 (2026-10-26 사용자: "늘어나면 빨간색, 나빠지면 파란색, 평소면 회색") — " · " 덩어리마다. 비싸짐은 싸짐보다 먼저 본다
WORD_GRAY = ("비슷", "그대로", "평소 수준", "평소 안")
WORD_UP = ("늘어남", "오름", "비싸짐", "순매수", "좋아짐", "활발", "강세")
WORD_DOWN = ("줄어듦", "내림", "싸짐", "순매도", "나빠짐", "한산", "약세")


def _word_color(chunk, default):
    for words, col in ((WORD_GRAY, NOTE), (WORD_UP, UP), (WORD_DOWN, DOWN)):
        if any(w in chunk for w in words):
            return col
    return default


SMALL_WORDS = ("시가", "장중")
SMALL_WORD_FS = "14px"   # 숫자 위 작은 앞말 (2026-10-26 사용자: 13 → 14, 숫자 위로)


def _qc(title, state, theme, color, lines, **kw):
    """C.question_card 와 같고, 답을 덩어리마다 결과 단어 색으로. 단어가 없는 덩어리(숫자 · 건수)는 원래 색 + 증감 색(tint).
    `시가 −2.36% · 장중 +2.72%` 처럼 앞말이 SMALL_WORDS 이면 앞말을 숫자 위에 작게 올려 칸으로 나란히 (2026-10-26 사용자: 폰에서 두 줄로 꺾였다)."""
    parts = str(state).split(" · ")
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
    ref = f"images/kospi-price-{day}.png"
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
            f'background:rgba(255,255,255,.92);border:1px solid #E2E8F0;border-radius:8px;color:#111;">{ZOOM_ICON}</span></a>')


def head_chart(r):
    """머리 그래프 — 코스피 · 코스닥 하루를 시가 갭 · 장중 · 하루로 나눈 막대 (데일리 S&P 500 그래프 자리)."""
    groups = [(INDEX[k], [v["gap"], v["intra"], v["ret"]]) for k, v in r["idx"].items()]
    amber = lambda v: C.AMBER   # noqa: E731
    chart = C.chart_card("", groups, [amber, C.sign_bg, C.gray], [C.sign_fg, C.sign_fg, C.sign_fg],   # 막대 색은 구분용, 숫자는 모두 증감 색 (M6)
                         [("시가 갭", C.AMBER), ("장중", C.PASTEL_UP), ("하루", C.GRAY_BAR)])
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
    first = f"코스피는 전일 종가보다 {_s(k['gap'])} {'높게' if k['gap'] > 0 else '낮게'} 시작했습니다."
    if ewy and sox:
        first += f" 밤사이 미국에서 한국 ETF(EWY)가 {_s(ewy['ret'])}, 반도체 지수(SOX)가 {_s(sox['ret'])} 움직인 뒤였습니다."
    lines.append((first, "plain"))
    same = (k["intra"] > 0) == (k["gap"] > 0)
    lines.append((f"장중에는 시가보다 {_s(k['intra'])} {'더 움직여' if same else '되돌려'} 하루 {_s(k['ret'])}로 마감했습니다.", "plain"))
    us = [(label, unit, ov[t]) for t, (label, unit) in {"EWY": ("EWY (미국 상장 한국 ETF)", "%"), "^SOX": ("SOX (미국 반도체 지수)", "%"), "^VIX": ("VIX (미국 변동성)", "p"), "DX-Y.NYB": ("달러지수 (달러 가치)", "%")}.items() if ov.get(t)]
    days = {b["day"] for _, _, b in us}
    if len(days) == 1:   # 같은 날 종가면 줄마다 쓰지 않고 위에 한 번 — 작은 회색 머리줄 (2026-10-26 사용자: "미국 10월 22일 종가가 계속 반복")
        lines.append((f'<span style="display:block;font-size:{_dk.TINY};line-height:{_dk.LH_TINY};color:{NOTE};margin:4px 0 -10px;">밤사이 미국 · {_md(days.pop())} 종가</span>', "html"))
        lines += [("row", label, _s(b["ret"], 2, unit), "") for label, unit, b in us]
    else:
        lines += [("row", label, _s(b["ret"], 2, unit), f"미국 {_md(b['day'])} 종가") for label, unit, b in us]
    lines.append(("row", "코스피 시가 갭", _s(k["gap"]), _often(k["gap_n"], k["n_past"])))
    lines.append(("row", "코스피 장중", _s(k["intra"]), "시가 → 종가 · " + _often(k["intra_n"], k["n_past"])))
    recs = " · ".join(f"{U.US_MARKET[t].split(' ')[0]} {_s(U.OVERNIGHT_RECORD[t][0], 2, '')}" for t in ("EWY", "^SOX", "^VIX", "DX-Y.NYB"))
    tip = ("하루 움직임을 시가 갭(전일 종가 → 오늘 시가)과 장중(시가 → 종가)으로 나눈 것. 한국 장이 닫힌 사이 열린 미국 장의 결과는 시가에 먼저 반영됩니다\n"
           f"· 오늘 : 시가 갭 {_s(k['gap'])} · 장중 {_s(k['intra'])}" + (f" · 밤사이 EWY {_s(ewy['ret'])} · SOX {_s(sox['ret'])}" if ewy and sox else "") + "\n"
           f"· 기록상 : 밤사이 많이 오른 날(상위 25%)과 많이 내린 날(하위 25%)의 다음날 KOSPI 차이 {recs} %p (2000~2026). 이 차이는 시가에 다 반영됐고 장중엔 더 가지 않았습니다")
    state = f"시가 {_s(k['gap'])} · 장중 {_s(k['intra'])}"
    return _qc("왜 이렇게 시작했나?", state, "neutral", "#111", lines, tip=_dk.with_src(tip, "Yahoo Finance"), opened=True)


def normal_card(r):
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
           f"· 오늘 코스피 {_s(k['ret'])} : 평소의 {_times(k['normal']['z'])}, 지난 1년 중 이만큼 이상 움직인 날 {k['normal']['n_year']}번\n"
           "· 기록상 : 한국 지수에서는 평소 밖 움직임 다음 날을 검증하지 않았습니다 — 크기만 봅니다")
    return _qc("오늘 움직임은 평소와 달랐나?", state, "neutral", "#111", lines, tip=_dk.with_src(tip, "Yahoo Finance"), opened=True)


NEWS_SHOWN = 3   # 방송은 3건만 펼쳐 두고 나머지는 `방송 n건 더 보기` (2026-10-26 사용자)
NEWS_HOURS = 24   # 그날 방송만. 지난 날 목업에서 샘플을 보려면 --news-hours 120 (2026-10-26 사용자: "공통 기사 룰로 샘플 몇 개")


def _kr_channels(iss, n):
    """한국 증시 채널(수집기 limitGroup=kr — 매경TV · MTN · 미래에셋 · 삼성증권 …) 방송 이슈만, 최근 순. 미국 방송의 한국 이야기는 미국 데일리 한국장 탭 몫."""
    out = [r for r in iss if r["category"] != "OTHER" and "kr" in (r.get("groups") or [r.get("group")])]
    return sorted(out, key=lambda r: str(r["published_at"]), reverse=True)[:n]


def news_section():
    """R8 방송 소식 — 공용 뉴스 카드(kr_news.section = 뉴스 형식 통일 2절: 헤드라인 · 방송 주장 · [종목 · 분야] [방향] [예상 밖] [방송] 시각 · 채널).
    목업에서 읽지 못하면 자리만 보인다."""
    try:
        sys.path.insert(0, os.path.join(_HERE, "..", "daily-report"))
        import kr_news
        rows = [x for x in kr_news.rows_now() if x.get("group") == "kr"]   # 묶기 전에 한국 채널만 — 미국 방송과 한 이슈로 묶이면 대표 채널이 미국이 된다
        html = kr_news.section(rows, hours=NEWS_HOURS, pick=_kr_channels, shown=NEWS_SHOWN).replace(kr_news.TITLE, "오늘 한국 증시 방송").replace(f'data-tab="{kr_news.TAB}"', f'data-tab="{TAB_TODAY}"')
        if "<h2" in html:
            return html
    except Exception as e:  # noqa: BLE001
        print(f"[kr-report] 방송 줄 못 읽음 (목업은 자리만): {str(e)[:80]}")
    return _dk.section("오늘 한국 증시 방송", _dk.muted("방송 줄 자리 — 발행 때 한국 증시 채널 방송(공용 뉴스 처리)으로 채웁니다."), tab=TAB_TODAY)


SORT_BTN = ('<button type="button" class="sort-toggle" data-sort-for="{key}" data-state="" aria-label="정렬" hidden="hidden">'
            '<span class="sort-in"><svg class="sort-tri" viewBox="0 0 10 10" aria-hidden="true"><path d="M5 1.5 9.5 8.5H.5z"/></svg>'
            '<span class="sort-txt">상승순</span></span></button>')   # 홈 H12 버튼과 같은 마크업 — 테마 JS(data-sort-for)가 보이게 하고 정렬한다. JS 가 없으면 숨은 채


def _title_with_sort(title, tip, key):
    """카드 제목 줄 + 오른쪽 정렬 버튼 (M3)."""
    t = R._card_title(title, tip)
    t = t.replace('<div style="', '<div style="display:flex;align-items:center;gap:8px;', 1)
    return t[:-len("</div>")] + SORT_BTN.format(key=key) + "</div>"


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
    """R3 시총 상위 10 — 처음은 평소 범위 기준 크게 움직인 순, 오른쪽 버튼으로 상승순 · 하락순 (M3). 홈 시총 TOP 10 목록처럼 구분선만 (M2)."""
    xs = sorted(r["top"], key=lambda s: -abs((s.get("normal_range") or {}).get("z") or 0))
    rows = "".join(_top_row(s, r, i == 0) for i, s in enumerate(xs))
    outs = [s for s in xs if (s.get("normal_range") or {}).get("outside")]
    now = ("· 오늘 평소 밖 : " + " · ".join(f"{s['name']} {_s(s['ret_1d'])}" for s in outs)) if outs else "· 오늘 : 10개 모두 평소 범위 안"
    tip = ("한국 유가증권시장 시가총액 상위 10개의 오늘 움직임을 그 종목의 평소 크기와 비교한 것. 처음엔 크게 움직인 순서, 오른쪽 버튼으로 상승순 · 하락순\n" + now + "\n"
           "· 기록상 : 밤사이 연결 미국 종목이 많이 오른 날과 내린 날의 다음날 차이는 35종목 중 20개에서 확인됐고, 시가에서 끝났습니다 (그 종목만 `밤사이` 를 적습니다)")
    return (_title_with_sort("시총 상위 10개는 어떻게 움직였나?", _dk.with_src(tip, "Yahoo Finance"), "kr-top10")
            + f'<div style="margin:0 0 8px;font-size:{_dk.SMALL};"><span data-sort-list="kr-top10" style="display:block;">{rows}</span></div>')   # 안내 줄 삭제 (M4)


def group_section(r):
    """R4 테마별 — 테마 평균 vs KOSPI. 묶음 = 홈 · 목록의 `테마 종목` 묶음과 같아 이름도 테마 (M5)."""
    gs = r["groups"]
    if not gs:
        return ""
    k = r["idx"][U.BENCH]["ret"]
    chart = C.chart_card("테마 평균과 코스피 (%)", [(g["short"], [g["avg"], k]) for g in gs], [C.sign_bg, C.gray], [C.sign_fg, C.sign_fg],   # 코스피 막대는 회색, 숫자는 증감 색 (M6)
                         [("테마 평균", C.PASTEL_UP), ("코스피", C.GRAY_BAR)])
    rows = "".join(R._row_html(_dk.esc(g["name"]), R._arrow(g["avg"]), _dk.tint(f"코스피 대비 {_s(g['vs'], 2, '%p')} · 가장 크게 {g['best']['name']} {_s(g['best']['ret_1d'], 1)}"), first=i == 0)
                   for i, g in enumerate(gs))
    tip = ("테마(홈 · 목록의 테마 종목 묶음)마다 오늘 등락의 단순 평균을 코스피와 견준 것\n"
           "· 오늘 : " + " · ".join(f"{g['short']} {_s(g['avg'], 1)}" for g in gs) + "\n"
           "· 기록상 : 테마 하루 움직임으로 이후를 말하지 않습니다 — 오늘 어디가 움직였나만 봅니다")
    return (R._card_title("어느 테마가 움직였나?", tip)
            + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}"><span style="display:block;padding:{RK.PAD + 6}px 12px 0;">{chart}</span>{rows}</span></div>')


# ── 수급 탭 — 질문 카드 (M7: 수치만이던 카드에 쉬운 문장 · 한 줄 답, 2026-10-26 사용자) ──

def _pos_word(v, lo, hi):
    p = (v - lo) / (hi - lo) * 100 if hi > lo else 50
    return "아래쪽 끝" if p <= 15 else "아래쪽" if p <= 40 else "가운데" if p < 60 else "위쪽" if p < 85 else "위쪽 끝"


def _bars(title, groups, fg, bg, fmt):
    return (f'{_dk.CHART_TITLE_M}{_dk.esc(title)}</span>'
            f'<span style="{_dk.MULTI}margin:0 {_dk.CHART_CARD_X}px;"><span style="display:block;padding:{_dk.CHART_CARD_PAD}px 12px 4px;">{C.col_chart(groups, [bg], [fg], fmt=fmt)}</span></span>')


def foreign_card(m):
    f = m.get("foreign")
    if not f:
        return ""
    buy, word = f["today"] > 0, "순매수" if f["today"] > 0 else "순매도"
    first = f"외국인은 {_md(f['day'])} 유가증권시장에서 {abs(f['today']):,.0f}억 원어치를 {'더 샀' if buy else '더 팔'}습니다({_s(f['today'], 0, '억')})."
    if f.get("z") is not None:
        first += f" 평소 하루 크기의 {abs(f['z']):.1f}배입니다."
    if f["streak"] > 1:
        first += f" {f['streak']}일 연속 {'순매수' if f['streak_sign'] > 0 else '순매도'}입니다."
    lines = [(first, "plain")]
    rk = f.get("cum20_pct_rank")
    second = f"최근 20일 합계는 {_s(f['cum20'] / 1e4, 1, '조')}입니다."
    if rk is not None:
        second += f" 과거 모든 20일 구간과 견주면 아래에서 {rk:.0f}% 지점으로, " + ("파는 쪽이 큰 편입니다." if rk <= 25 else "사는 쪽이 큰 편입니다." if rk >= 75 else "보통 범위입니다.")
    lines.append((second, "plain"))
    lines.append((f"기록상 : {_rec(U.NO_RECORD['foreign'])}. 오늘 누가 사고팔았는지를 보는 칸입니다.", "note"))
    ser = f["series"][-15:]
    lines.append((_bars(f"최근 {len(ser)}거래일 외국인 순매수 (조 원)", [(str(int(x["day"][8:])), [x["v"] / 1e4]) for x in ser], C.sign_fg, C.sign_bg, lambda v: _s(v, 1, "")), "html"))
    lines.append(("row", "오늘", _s(f["today"], 0, "억"), f"{f['streak']}일 연속 {word}" if f["streak"] > 1 else word))
    lines.append(("row", "20일 누적", _s(f["cum20"] / 1e4, 1, "조"), f"과거 20일 구간 중 아래에서 {rk:.0f}%" if rk is not None else ""))
    lines.append(("row", "올해 누적", _s(f["ytd"] / 1e4, 1, "조"), f"{f['day'][:4]}년"))
    if f.get("kosdaq_today") is not None:
        lines.append(("row", "코스닥 오늘", _s(f["kosdaq_today"], 0, "억"), ""))
    tip = ("외국인 투자자가 유가증권시장에서 하루에 산 금액에서 판 금액을 뺀 것. 양수면 사는 쪽, 음수면 파는 쪽\n"
           f"· 오늘 {_s(f['today'], 0, '억')} : 20일 누적 {_s(f['cum20'] / 1e4, 1, '조')}\n"
           f"· 기록상 : {_rec(U.NO_RECORD['foreign'])}")
    return _qc("외국인은 사고 있나?", f"오늘 {word}", "neutral", UP if buy else DOWN, lines, tip=_dk.with_src(tip, RK.SRC), opened=True)


def heat_card(m):
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
    lines.append((f"기록상 : {_rec(U.NO_RECORD['heat'])}. 오늘 시장 분위기를 보는 칸입니다.", "note"))
    ser = h["series"][-15:]
    lines.append((_bars(f"최근 {len(ser)}거래일 거래대금 (조 원)", [(str(int(x["day"][8:])), [x["v"] / 1e4]) for x in ser], C.note_fg, C.gray, lambda v: f"{v:.1f}"), "html"))
    lines.append(("row", "유가증권 거래대금", f"{h['turnover'] / 1e4:.1f}조 원", f"20일 평균의 {tr:.1f}배 · 1년 중 아래에서 {h['pct_rank_1y']:.0f}%"))
    if h.get("kosdaq_turnover"):
        lines.append(("row", "코스닥 거래대금", f"{h['kosdaq_turnover'] / 1e4:.1f}조 원", ""))
    if mc:
        lines.append(("row", "유가증권 시가총액", f"{mc['v'] / 1e4:,.0f}조 원", f"오늘 {_s(mc['chg_1d'])} · 1년 중 아래에서 {mc['pct_rank_1y']:.0f}%" if mc.get("chg_1d") is not None else ""))
    if n:
        lines.append(("row", "뉴스심리지수", f"{n['v']:.1f}", f"{_md(n['day'])} · 1년 평균 {n['avg_1y']:.1f}"))
    tip = ("하루에 사고판 돈의 크기(거래대금)로 본 시장의 열기. 20일 평균보다 1.5배 이상이면 활발, 0.7배 아래면 한산으로 봅니다\n"
           f"· 오늘 {h['turnover'] / 1e4:.1f}조 원 : 20일 평균의 {tr:.1f}배\n"
           f"· 기록상 : {_rec(U.NO_RECORD['heat'])}")
    return _qc("시장은 얼마나 뜨겁나?", state, "neutral", "#111", lines, tip=_dk.with_src(tip, RK.SRC))


RATE_ROWS = (("base_rate", "한국은행 기준금리"), ("ktb3", "국고채 3년"), ("ktb10", "국고채 10년"), ("corp_aa", "회사채 AA−"), ("corp_bbb", "회사채 BBB−"))
FX_ROWS = (("usdkrw", "원/달러"), ("jpykrw100", "원/100엔"), ("cnykrw", "원/위안"))


def rates_card(m):
    rt, fx = m.get("rates") or {}, m.get("fx") or {}
    k3, usd, bbb = rt.get("ktb3"), fx.get("usdkrw"), rt.get("corp_bbb")
    if not (k3 or usd):
        return ""
    st, lines = [], []
    if k3 and k3.get("chg_n") is not None:
        bp = k3["chg_n"] * 100
        st.append("금리 내림" if bp <= -10 else "금리 오름" if bp >= 10 else "금리 그대로")
        lines.append((f"시장 금리(국고채 3년)는 {k3['v']:.2f}%로 20일 동안 {_s(k3['chg_n'], 2, '%p')} 움직여, 1년 범위({k3['lo_1y']:.2f}~{k3['hi_1y']:.2f}%)의 {_pos_word(k3['v'], k3['lo_1y'], k3['hi_1y'])}에 있습니다. "
                      + ("금리가 내리면 돈을 빌리는 비용이 줄어드는 쪽입니다." if bp <= -10 else "금리가 오르면 돈을 빌리는 비용이 늘어나는 쪽입니다." if bp >= 10 else "20일 동안 크게 바뀌지 않았습니다."), "plain"))
    if usd and usd.get("chg_n") is not None:
        pct = usd["chg_n"] / (usd["v"] - usd["chg_n"]) * 100
        st.append("원화 강세" if pct <= -1 else "원화 약세" if pct >= 1 else "환율 그대로")
        lines.append((f"원/달러 환율은 {usd['v']:,.1f}원으로 20일 동안 {_s(usd['chg_n'], 1, '원')} 움직여, 1년 범위({usd['lo_1y']:,.0f}~{usd['hi_1y']:,.0f}원)의 {_pos_word(usd['v'], usd['lo_1y'], usd['hi_1y'])}에 있습니다. "
                      + ("환율이 내렸다는 건 원화 값이 올랐다는 뜻입니다." if pct <= -1 else "환율이 올랐다는 건 원화 값이 내렸다는 뜻입니다." if pct >= 1 else "원화 값은 20일 동안 크게 바뀌지 않았습니다."), "plain"))
    if bbb and k3 and bbb.get("chg_n") is not None and k3.get("chg_n") is not None:
        sp, d = bbb["v"] - k3["v"], bbb["chg_n"] - k3["chg_n"]
        lines.append((f"신용이 낮은 기업의 회사채(BBB−)와 국고채 3년의 금리 차이는 {sp:.2f}%p로 20일 전보다 {abs(d):.2f}%p {'넓어졌' if d > 0 else '좁아졌'}습니다. "
                      "차이가 넓어지면 기업이 돈을 빌리기 더 어려워졌다는 뜻입니다.", "plain"))
    lines.append((f"기록상 : {_rec(U.NO_RECORD['rates_fx'])}. 오늘 상태를 보는 칸입니다.", "note"))
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
           "· 오늘 : " + " · ".join(st) + "\n"
           f"· 기록상 : {_rec(U.NO_RECORD['rates_fx'])}")
    return _qc("금리 · 환율은?", " · ".join(st), "neutral", "#111", lines, tip=_dk.with_src(tip, RK.SRC))


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


def _monthly_card(title, state, color, lines, sec_html, opened=False):
    """기존 카드(render_kr.sec_*)를 질문 카드 안 모양으로 (2026-10-26 사용자: "흰 카드는 막대 그래프만, 나머지 내용은 흰 카드가 있으면 안 돼") —
    수치 줄은 색 바탕 위 구분선 줄(위 외국인 · 금리 카드의 줄과 같은 글자), 그래프는 제목 밖 · 흰 카드. 툴팁은 그대로."""
    if not sec_html or "<div data-cards" not in sec_html:
        return ""
    i = sec_html.index("<div data-cards")
    body = sec_html[i:]
    a = body.index(">", body.index(f'<span style="{R.MULTI}">')) + 1   # 흰 카드 안쪽만
    inner = body[a:_span_end(body, body.index(f'<span style="{R.MULTI}">')) - len("</span>")]
    rows, charts = _split_card(inner)
    bd_row = _dk.darken(_dk.lighten(_dk.lighten(C.CARD_DIR["neutral"][1]), 0.3), 0.02)   # 질문 카드 줄 구분선과 같은 색
    pad = f"padding:{RK.PAD}px 12px;line-height:{R.LH_CARD};"
    rows = (rows.replace(pad + R.MULTI_SEP, f"padding:10px 0;line-height:{R.LH_CARD};border-top:1px solid {bd_row};")
                .replace(pad + '"', f'padding:10px 0;line-height:{R.LH_CARD};border-top:1px solid {bd_row};"')
                .replace(f"color:#111;font-weight:700;font-size:{_dk.NAME};", "color:#111;font-weight:400;"))   # 줄 이름 = 질문 카드 줄과 같게(보통 굵기 · 카드 글자)
    out = lines + ([(f'<span style="display:block;">{rows}</span>', "html")] if rows.strip() else [])
    out += [(_chart_white(c), "html") for c in charts]
    return _qc(title, state, "neutral", color, out, tip=RK._tip_of(sec_html[:i]), opened=opened)


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
    lines = [(x, "plain") for x in parts]
    state = (" · ".join(buyers) + " 순매수") if buyers else "모두 순매도"
    return _monthly_card("기관 · 개인은?", state, "#111", lines, RK.sec_investors(m))


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
    return _monthly_card("빚투 · 대기 자금은?", " · ".join(st), "#111", lines, RK.sec_funds(m))


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
    lines.append((f"기록상 : {_rec(U.NO_RECORD['valuation'])}. 비싼지 싼지의 지금 상태를 보는 칸입니다.", "note"))
    state = f"{_prev_mo(mo)}보다 " + ("비싸짐" if w == "높아졌" else "싸짐" if w == "낮아졌" else "비슷")
    return _monthly_card("코스피는 비싼가?", state, "#111", lines, RK.sec_valuation(m))


def derivatives_card(m):
    d = m.get("derivatives")
    if not d or len(d.get("pc_series") or []) < 2:
        return ""
    mo, pc, prev = d["month"], d["put_call"], d["pc_series"][-2]["v"]
    w = _cmp_word(pc, prev, 0.05, "올랐", "내렸")
    lines = [(f"{_mo(mo)} 풋/콜 거래량 비율은 {pc:.2f}로 " + (f"{_prev_mo(mo)}({prev:.2f})보다 {w}습니다. " if w else f"{_prev_mo(mo)}({prev:.2f})과 비슷합니다. ")
              + ("하락에 대비하는 거래가 늘었다는 뜻입니다." if w == "올랐" else "하락에 대비하는 거래가 줄었다는 뜻입니다." if w == "내렸" else "")
              + (" 1보다 작아 오를 때 이익인 콜옵션이 더 많이 거래됐습니다." if pc < 1 else " 1보다 커서 내릴 때 이익인 풋옵션이 더 많이 거래됐습니다."), "plain")]
    state = "하락 대비 " + ("늘어남" if w == "올랐" else "줄어듦" if w == "내렸" else "비슷")
    return _monthly_card("파생 시장 분위기는?", state, "#111", lines, RK.sec_derivatives(m))


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
    return _monthly_card("경제 바탕은 어떤가?", f"좋아짐 {len(better)} · 나빠짐 {len(worse)}", "#111", lines, RK.sec_macro(m))


def household_card(m):
    hh = m.get("household") or {}
    sur, buy, share = hh.get("hh_surplus"), hh.get("hh_stock_buy"), hh.get("hh_stock_share")
    if not sur or sur.get("yoy") is None:
        return ""
    q = sur["q"]
    lines = [(f"{_qtr(q)} 가구당 한 달에 쓰고 남은 돈(흑자액)은 {sur['v'] / 1e4:,.0f}만 원으로 1년 전 같은 분기보다 {_s(sur['yoy'], 1)} {'늘었' if sur['yoy'] > 0 else '줄었'}습니다.", "plain")]
    if buy and buy.get("same") is not None:
        lines.append((f"가계는 {_qtr(q)}에 주식을 {_s(buy['v'] / 1e3, 1, '조')} 원 {'순취득(산 쪽)' if buy['v'] > 0 else '순처분(판 쪽)'}했습니다. 1년 전 같은 분기는 {_s(buy['same'] / 1e3, 1, '조')} 원이었습니다.", "plain"))
    if share:
        lines.append((f"가계 금융자산 가운데 주식 비중은 {share['v']:.1f}%입니다.", "plain"))
    state = "남는 돈 " + ("늘어남" if sur["yoy"] > 0 else "줄어듦")
    return _monthly_card("개인은 살 돈이 있나?", state, "#111", lines, RK.sec_household(m))


def flow_tab(r):
    """수급 탭 — 누가 사고팔았나 · 살 돈이 있나 (2026-10-26 사용자: 카드가 많아 탭을 나눔, M11). 매일 · 월별 · 분기가 섞여 있어 카드 문장에 기준 달을 적는다."""
    m = r["market"]
    body = foreign_card(m) + investors_card(m) + funds_card(m) + household_card(m)
    return _dk.section(TAB_FLOW, C.cards_grid(body), tab=TAB_FLOW) if body else ""


def market_tab(r):
    """시장 탭 — 시장 분위기 · 금리 환율 · 비싼가 · 파생 · 경제 바탕 (M11, 수급 탭에서 나눔)."""
    m = r["market"]
    body = heat_card(m) + rates_card(m) + valuation_card(m) + derivatives_card(m) + macro_card(m)
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
    tip = ("미국 금리 결정 · 물가 · 고용 발표와 국내 옵션 만기처럼 시장 전체가 함께 보는 일정\n"
           f"· {CAL_DAYS}일 안 {len(up)}건 : 가장 가까운 일정은 {RK._macro_name(up[0]['kind'], up[0].get('label', ''))} {R._md_short(up[0]['day'])}\n"
           f"· 참고 : 최근 2년 그 일정 뒤 코스피 움직임 크기를 보통 날(±{c['normal']:.1f}%)과 견줬습니다. 미국 일정은 한국 다음 거래일로 셉니다. 한국은행 금리 결정 일정은 출처를 확인한 뒤 넣습니다")
    return _qc("다가오는 시장 일정은?", f"{len(up)}건 · {CAL_DAYS}일 안", "soon", C.SOON, lines, tip=_dk.with_src(tip, "FRED · Yahoo Finance"), opened=True)


def earn_card(r):
    es = r["earn"]
    if not es:
        return ""
    has = [e for e in es if e["median"] is not None]
    big = [e for e in has if e["median"] > e["normal"]]
    # 미국 대형주는 실적 날 2~6배였지만 한국 상위 10개는 그렇지 않았다(10-23 기준 9개 중 3개만 큼) — 문장은 데이터로 (미국 결론을 옮기지 않는다)
    lines = [(f"시총 상위 10개 중 {len(es)}개가 {EARN_DAYS}일 안에 실적을 발표합니다. 지난 실적 날 움직임이 보통 날보다 컸던 종목은 {len(has)}개 중 {len(big)}개였습니다.", "plain")]
    if has:
        lines.append((C.chart_card("지난 실적 날과 보통 날 움직임 (%)", [(e["s"]["name"], [e["median"], e["normal"]]) for e in has],
                                   [lambda v: C.AMBER, C.gray], [C.note_fg, C.note_fg], [("실적 날", C.AMBER), ("보통 날", C.GRAY_BAR)], fmt=lambda v: f"±{v:.1f}"), "html"))
    for e in es:
        lines.append(("row", e["s"]["name"], R._md_short(e["day"]), f"실적 날 보통 ±{e['median']:.1f}% ({e['n']}번) · 보통 날 ±{e['normal']:.1f}%" if e["median"] is not None else "지난 실적 날 기록 부족"))
    tip = ("시총 상위 10개 회사의 다음 실적 발표일. 발표 시각은 대부분 장 시작 전이라 그날 움직임으로 셉니다\n"
           f"· 가장 가까운 발표 : {es[0]['s']['name']} {R._md_short(es[0]['day'])}\n"
           "· 참고 : 최근 2년 지난 실적 날 움직임 크기(방향 없음)를 보통 날과 견줬습니다")
    return _qc("상위 10개 실적 발표는?", f"{len(es)}개 · {EARN_DAYS}일 안", "soon", C.SOON, lines, tip=_dk.with_src(tip, "Yahoo Finance"))


def body(r):
    parts = [
        _dk.WRAP_OPEN,
        seo_lead(r),
        price_chart(r["day"], r["kospi_bars"]),   # 요약 바로 아래 (데일리의 S&P 500 그래프 자리)
        head_chart(r),   # 제목 글자 없이 그래프만 (2026-10-26 사용자, M19)
        _dk.section(TAB_TODAY, C.cards_grid(open_card(r) + normal_card(r)), tab=TAB_TODAY),
        news_section(),
        _dk.section(TAB_STOCKS, top_section(r) + group_section(r), tab=TAB_STOCKS),
        flow_tab(r),
        market_tab(r),
        _dk.section(TAB_CAL, C.cards_grid(cal_card(r) + earn_card(r)), tab=TAB_CAL),
        RK.related(links=[("한국 시가총액 상위 10개 종목 주가", U.LIST_URL), ("미국 증시 리포트", DAILY_URL), ("미국 시가총액 상위 10개 종목 주가", U.US_LIST_URL)]),
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
    extra = collect_kr_extra.load() if cached else collect_kr_extra.run()
    r = build(a, snap, extra or {})
    html = body(r)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "report_body.html"), "w", encoding="utf-8") as f:
        f.write(html)
    mock = _dk.write_mock(html, os.path.join(OUT, "kr_report_mock.html"), title(r["day"]))
    print(f"[kr-report] {r['day']} · {title(r['day'])} → {mock}")
