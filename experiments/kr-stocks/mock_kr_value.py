"""목업 — 한국 종목 실적 탭 새 카드 둘 (개선 1-14 · 1-12, 미국 틀 가져오기).

① `발표 때 예상을 넘었나?` — 미국 peer_cards.beat_card 그대로(원 · 한국 안내). 예상 · 실제 1주당 이익 = Yahoo Finance(한국 종목도 줌).
② `이익에 비해 주가 수준은?` — A안(추천) KOSPI 전체 PER · 이 종목 3년 흐름과 견줌 / B안 정식 종목 시총 상위 20개 안 순위(미국 카드 모양).

기존 한국 종목 목업(output/mock_005930.html · mock_000660.html)의 실적 탭에 끼워 output/mock_kr_value_{코드}.html 로 쓴다. 읽기만 · 쓰기 · AI 0.
    python experiments/kr-stocks/mock_kr_value.py --fin <dart_fin_all.json> --flows <flows.json>
"""
import argparse
import datetime
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "..", "stock-radar"))
sys.path.insert(0, os.path.join(BASE, "..", "nvda-report"))
sys.path.insert(0, os.path.join(BASE, ".."))
import peer_cards as P  # noqa: E402
import render_pages as RP  # noqa: E402
import collect_kr_fin as KF  # noqa: E402
import universe_kr as U  # noqa: E402

R, dk = RP.R, RP._dk
SEOUL = ZoneInfo("Asia/Seoul")
WON = lambda v: f"{v:,.0f}원".replace("-", "−")   # noqa: E731
TOP_N = 20


def jo(v):
    return f"{v / 1e12:,.1f}조 원" if abs(v) >= 1e12 else f"{v / 1e8:,.0f}억 원"


# ---------------------------------------------------------------- 자료

def earn_yahoo(sym):
    """미국 peer_cards._earn 과 같은 모양 — 발표일은 서울 날짜로(야후는 미국 시각)."""
    import yfinance as yf
    t = yf.Ticker(sym)
    rows = {}
    ed = t.get_earnings_dates(limit=16)
    for d, r in (ed.iterrows() if ed is not None else []):
        day = d.astimezone(SEOUL).date().isoformat()
        rows[day] = {"day": day, "est": P._num(r.get("EPS Estimate")), "act": P._num(r.get("Reported EPS"))}
    hist = []
    eh = t.earnings_history
    for q, r in (eh.iterrows() if eh is not None else []):
        hist.append({"end": q.date().isoformat(), "est": P._num(r.get("epsEstimate")), "act": P._num(r.get("epsActual"))})
    est = None
    try:
        ee = t.earnings_estimate
        if ee is not None and "0q" in ee.index:
            est = [float(ee.loc["0q", "avg"]), int(ee.loc["0q", "numberOfAnalysts"])]
    except Exception:  # noqa: BLE001
        pass
    return {"dates": sorted(rows.values(), key=lambda x: x["day"]), "hist": hist, "finnhub": []}, est


def quarter_rows(fin, corp, today):
    return KF._rows(fin.get(corp) or {}, today)


def ttm(rows, k, upto=None):
    rs = [r for r in rows if upto is None or r["end"] <= upto]
    last4 = [r.get(k) for r in rs[-4:]]
    return sum(last4) if len(last4) == 4 and None not in last4 else None


def month_close(sym, start):
    import yfinance as yf
    h = yf.Ticker(sym).history(start=start, interval="1mo", auto_adjust=False)
    return {d.strftime("%Y-%m"): float(v) for d, v in h["Close"].items() if v > 0}


# ---------------------------------------------------------------- 카드

KR_BEAT_TIP = ("실적 발표 때 실제 1주당 이익(EPS)이 애널리스트 예상 평균보다 높았는지 낮았는지. 1주당 이익은 회사 순이익을 주식 수로 나눈 값\n"
               "· 나누는 법 : 마지막 발표의 1주당 이익이 예상보다 높으면 예상 넘음, 낮으면 예상 밑돎. 예상과 0.5% 안이면 같음\n"
               "· 예상 : 발표 직전 애널리스트 평균(Yahoo Finance 집계). 한국은 매출 예상을 받을 수 있는 무료 자료가 없어 1주당 이익만 견준다\n"
               "· 참고 : 잠정실적(공시)이 먼저 나와도 1주당 이익은 분기보고서 기준 값으로 견준다")


def beat(name, sym, day):
    e, est = earn_yahoo(sym)
    log = {day: {"eps0q": est}} if est else None
    got = P.beat_card(name, e, [], day, log, None, money=WON, unit="원", bil=jo, rev_note="", tip=KR_BEAT_TIP)
    return got


def _state_vs(pe, base):
    r = pe / base
    return "시장보다 낮음" if r < 0.8 else "시장보다 높음" if r > 1.25 else "시장 수준"


THEME = {"시장보다 낮음": ("positive", R.UP), "시장보다 높음": ("negative", R.DOWN), "업종보다 낮음": ("positive", R.UP), "업종보다 높음": ("negative", R.DOWN)}


def value_a(name, sym, rows, cap, px_now, kospi):
    """A안 — 비교 = KOSPI 전체 PER(한국거래소 월) · 이 종목 지난 3년 분기 말."""
    ni = ttm(rows, "ni")
    eq = rows[-1].get("equity") if rows else None
    k = kospi[-1]
    kmo = f"{int(k['month'][5:])}월"
    shares = cap / px_now
    mc = month_close(sym, rows[0]["end"][:8] + "01")
    kby = {x["month"]: x["v"] for x in kospi}
    hist = []
    for r in rows:
        m = r["end"][:7]
        t = ttm(rows, "ni", r["end"])
        if t and t > 0 and m in mc:
            hist.append((r["cq"], mc[m] * shares / t, kby.get(m)))
    lines = []
    if not ni or ni <= 0:
        pb = cap / eq if eq else None
        state = "판단 유보"
        lines.append((f"{dk.josa(name, '는')} 지난 1년 순이익이 적자라 주가수익비율을 계산하지 않습니다." + (f" 주가순자산비율(시가총액 ÷ 자본)은 {pb:.1f}배입니다." if pb else ""), "plain"))
        return state, lines, ""
    pe = cap / ni
    state = _state_vs(pe, k["v"])
    word = "높습니다" if pe > k["v"] else "낮습니다"
    lines.append((f"{name}의 주가수익비율(시가총액 ÷ 지난 1년 순이익)은 {pe:.1f}배로, {kmo} KOSPI 전체 {k['v']:.1f}배보다 {word}. "
                   "높을수록 이익에 비해 주가가 높게 매겨져 있다는 뜻입니다.", "plain"))
    if len(hist) >= 4:
        labels = [dk.q_axis(q) for q, _, _ in hist]
        chart = R.line_chart(labels, [(name, [v for _, v, _ in hist], R.LINE_THIS, False), ("KOSPI 전체", [kv for _, _, kv in hist], R.LINE_GRAY, True)],
                             lambda v: f"{v:,.1f}", "배")
        lines.append((f'{dk.CHART_TITLE_M}분기 말 주가수익비율, {R._esc(name)}와 KOSPI 전체</span>{chart}', "html"))
    lines.append(("row", "주가수익비율 (지난 1년)", f"{pe:.1f}배", f"시가총액 {jo(cap)} ÷ 순이익 {jo(ni)}"))
    lines.append(("row", "KOSPI 전체 주가수익비율", f"{k['v']:.1f}배", f"{kmo} · 한국거래소 월 자료 · 12개월 {min(x['v'] for x in kospi[-12:]):.1f} ~ {max(x['v'] for x in kospi[-12:]):.1f}배"))
    if eq:
        lines.append(("row", "주가순자산비율", f"{cap / eq:.1f}배", "시가총액 ÷ 자본"))
    if len(hist) >= 8:
        vs = [v for _, v, _ in hist[:-1]]
        below = sum(1 for v in vs if v < pe)
        where = f"{len(hist) // 4}년 중 가장 낮음" if below == 0 else f"{len(hist) // 4}년 중 가장 높음" if below == len(vs) else f"분기 말 {len(vs)}번 중 지금보다 낮았던 때 {below}번"
        lines.append(("row", f"주가수익비율 {len(hist) // 4}년 범위", f"{min(vs):.0f} ~ {max(vs):.0f}배", f"지금 {pe:.1f}배 · {where}"))
    tip = ("이익에 비해 주가가 얼마나 높게 매겨져 있는지를 KOSPI 전체와 견준 것. 싸다 · 비싸다를 판정하지 않는다\n"
           "· 나누는 법 : 이 종목 주가수익비율이 KOSPI 전체의 1.25배를 넘으면 시장보다 높음, 0.8배 아래면 시장보다 낮음, 그 사이는 시장 수준\n"
           "· 순이익 : 금융감독원 전자공시(OpenDART) 분기 · 사업보고서, 최근 4분기 합(연결)\n"
           "· 분기 말 값 : 그달 마지막 종가 × 지금 주식 수 ÷ 그때까지 1년 순이익 — 그 사이 주식 수가 바뀌었으면 조금 다르다\n"
           "· 참고 : 반도체처럼 이익이 크게 오르내리는 업종은 이익이 꼭대기일 때 배수가 낮게 보인다")
    return state, lines, tip


def value_b(name, sym, peers):
    """B안 — 비교 = 정식 종목 시총 상위 20개(실적 탭의 다른 카드와 같은 묶음) 안 순위. 미국 value_card 모양."""
    me = peers.get(sym) or {}
    oth = [v for s, v in peers.items() if s != sym]
    rows = []
    for k, lb, mean in (("pe", "주가수익비율 (지난 1년)", "시가총액 ÷ 지난 1년 순이익"), ("pb", "주가순자산비율", "시가총액 ÷ 자본")):
        rk = P._rank(me.get(k), [o.get(k) for o in oth], True)
        if rk:
            rows.append(dict(rk, lb=P.AXIS[k], name=lb, k=k, val=f"{me[k]:.1f}배", med_s=f"{rk['med']:.1f}배", mean=mean))
    base = next((x for x in rows if x["k"] == "pe"), None)
    if not base:
        return None
    state = ("업종보다 낮음", "업종 수준", "업종보다 높음")[P._zone(base["pct"])].replace("업종", "상위 20개")
    first = (f"{name}의 {base['name']}은 {base['val']}로, 한국 시총 상위 {base['n']}개 가운데 높은 쪽부터 {base['rank']}번째입니다. "
             "높을수록 이익에 비해 주가가 높게 매겨져 있다는 뜻입니다.")
    lines = [(first, "plain"), (f'{dk.CHART_TITLE_M}시총 상위 {base["n"]}개 안 위치 (위로 갈수록 높음)</span>{P.rank_chart(R, dk, rows, base["lb"], top_word="가장 높음", bottom_word="가장 낮음", flip=True)}', "html")]
    lines += P.values_rows(rows)
    tip = ("이익 · 자본에 비해 주가가 얼마나 높게 매겨져 있는지를 한국 시총 상위 20개(업종이 섞인 묶음)와 견준 위치\n"
           "· 나누는 법 : 주가수익비율이 높은 쪽 4분의 1이면 상위 20개보다 높음, 낮은 쪽 4분의 1이면 낮음, 그 사이는 상위 20개 수준")
    return state, lines, tip


# ---------------------------------------------------------------- 끼우기

CARD_RE = re.compile(r'<div style="background:[^"]*border-radius:10px;padding:18px 14px;margin:0 0 8px;line-height:32px;"><details')


def card_spans(html, start):
    """start 뒤 카드마다 (시작, 끝, 제목 글자)."""
    out = []
    for m in CARD_RE.finditer(html, start):
        i, depth, j = m.start(), 0, m.start()
        for t in re.finditer(r"<(/?)div\b", html[i:]):
            depth += -1 if t.group(1) else 1
            if depth == 0:
                j = i + t.end() + 1
                break
        head = re.sub(r"<[^>]+>", "", html[i:i + 3000])
        out.append((i, j, head[:40]))
    return out


def tag(text):
    return f'<div style="margin:14px 0 6px;padding-left:6px;font-size:14px;font-weight:700;color:#B45309;">{text}</div>'


def card(title, got, opened=False):
    state, lines, tip = got
    th, col = THEME.get(state, R.EXPECT_THEME.get(state, ("neutral", "#111")))
    return R._state_card(title, state, th, col, lines, "", tip=tip, fold=True, opened=opened)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fin", default=os.path.join(BASE, "data", "dart_fin_all.json"))
    ap.add_argument("--flows", default=os.path.join(BASE, "data", "flows.json"))
    ap.add_argument("--day", default="")   # 비우면 목업 페이지와 같은 날(스냅샷 마지막 봉)
    a = ap.parse_args()
    fin = json.load(open(a.fin, encoding="utf-8"))
    kospi = json.load(open(a.flows, encoding="utf-8"))["more_m"]["per"]
    snap = json.load(open(os.path.join(BASE, "data", "snapshot.json"), encoding="utf-8"))
    qref = json.load(open(os.path.join(BASE, "..", "ref", "quick_ref.json"), encoding="utf-8"))["kr"]
    a.day = a.day or snap["bars"]["005930.KS"][-1]["day"]
    today = datetime.date.fromisoformat(a.day)
    P.init_theme()
    caps = snap["caps"]
    px = {s: b[-1]["close"] for s, b in snap["bars"].items() if b}
    off = [s for s in U.BY_SYM if s in caps and s in qref]
    top = sorted(off, key=lambda s: -caps[s])[:TOP_N]
    peers = {}
    for s in top:
        rows = quarter_rows(fin, qref[s]["corp"], today)
        ni, eq = ttm(rows, "ni"), (rows[-1].get("equity") if rows else None)
        peers[s] = {"pe": caps[s] / ni if ni and ni > 0 else None, "pb": caps[s] / eq if eq else None}
    for sym in ("005930.KS", "000660.KS"):
        code = sym.split(".")[0]
        src = os.path.join(BASE, "output", f"mock_{code}.html")
        html = open(src, encoding="utf-8").read()
        name = U.name(sym)
        rows = quarter_rows(fin, qref[sym]["corp"], today)
        b = beat(name, sym, a.day)
        va = value_a(name, sym, rows, caps[sym], px[sym], kospi)
        vb = value_b(name, sym, peers)
        sec = html.find('data-tab="실적"')
        spans = card_spans(html, sec)
        eps_at = next(i for i, j, h in spans if h.startswith("이익 예상"))
        sched = next(k for k, (i, j, h) in enumerate(spans) if h.startswith("다음 실적 발표"))
        bal_end = spans[sched - 1][1]   # 주요 일정 앞 마지막 카드 뒤 = 미국 카드 순서(주가 수준이 실적 카드 끝)
        new_beat = tag("새 카드 — 발표 때 예상을 넘었나? (미국 카드 그대로)") + (card("발표 때 예상을 넘었나?", b) if b else "")
        new_val = (tag("A안 (추천) — 이익에 비해 주가 수준은? · 비교 = KOSPI 전체 · 이 종목 3년") + card("이익에 비해 주가 수준은?", va)
                   + (tag("B안 — 같은 카드 · 비교 = 한국 시총 상위 20개 안 순위(미국 카드 모양)") + card("이익에 비해 주가 수준은?", vb) if vb else ""))
        html = html[:bal_end] + new_val + html[bal_end:]
        html = html[:eps_at] + new_beat + html[eps_at:]
        out = os.path.join(BASE, "output", f"mock_kr_value_{code}.html")
        open(out, "w", encoding="utf-8").write(html)
        print(out, "| 발표 카드", b[0] if b else None, "| A", va[0], "| B", vb[0] if vb else None)


if __name__ == "__main__":
    main()
