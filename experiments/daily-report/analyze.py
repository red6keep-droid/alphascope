"""분석: 수집 원본 + 시계열 → analysis.json

LLM 호출이 없다. 순수 산술이고 같은 입력이면 같은 출력이다.
계산하는 것은 doc/데일리-리포트-파이프라인.md 2부 B절의 B-1 ~ B-10:

    1D/5D/20D 수익률 · 이동평균 · 연속성 · 20일 고저점 대비 위치 · 상대강도
    시장 폭(프록시) · 섹터 로테이션 · 금리 ↔ 성장주 · Regime Score · 상태판 · 내일 체크

임계값과 배점은 초기값이다. 그림자 모드로 이력을 쌓은 뒤 조정한다.
점수·라벨·레벨은 전부 여기서 만들어지고, Gemini는 이 값을 설명만 한다.

입력:
    report_input.json   수집 원본 (macro · indices · gainers · most_active · news)
    prices.json         collect_yahoo.collect_history()의 결과
    state/regime.jsonl  어제까지의 점수 이력 (없으면 score_prev = null)
출력:
    analysis.json               계산 결과 + raw(원본)
    state/history/{date}.json   raw를 뺀 분석 결과 (report-state 브랜치에 쌓인다)
    state/regime.jsonl          한 줄 요약 추가 (같은 날짜는 덮어쓴다)

사용법 (리포 루트에서, report_input.json과 prices.json이 있어야 한다):
    python experiments/daily-report/analyze.py
"""

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STATE_DIR = os.path.join(OUTPUT_DIR, "state")

INDEX_SYMBOL = {
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "dow": "^DJI",
    "russell": "^RUT",
    "vix": "^VIX",
}

SECTOR_THEME = {
    "SMH": "AI / 반도체",
    "XLK": "기술",
    "XLF": "금융",
    "XLE": "에너지",
    "XLV": "헬스케어",
    "XLY": "소비 (경기민감)",
    "XLP": "소비 (필수)",
    "XLU": "유틸리티",
    "XLI": "산업",
    "XLB": "소재",
    "XLRE": "리츠",
    "XLC": "통신",
}
# 시장 폭 프록시의 분모. SMH는 테마라 빼고 섹터 11개만 센다.
BREADTH_SECTORS = ["XLK", "XLF", "XLE", "XLV", "XLP", "XLY", "XLU", "XLI", "XLB", "XLRE", "XLC"]

REGIME_RISK_ON = 70
REGIME_RISK_OFF = 45

GREEN, YELLOW, RED = "🟢", "🟡", "🔴"


# ---------------------------------------------------------------- 기본 산술

def _pct(a, b):
    """a가 b 대비 몇 % 인지. b가 0이거나 없으면 None."""
    if a is None or b is None or b == 0:
        return None
    return round((a / b - 1) * 100, 2)


def _ret(close, n):
    if len(close) <= n:
        return None
    return _pct(close[-1], close[-1 - n])


def _ma(close, n):
    if len(close) < n:
        return None
    return round(sum(close[-n:]) / n, 4)


def _streak(close):
    """마지막 날 방향이 연속된 일수. 부호가 방향(+상승, −하락). 보합은 끊는다."""
    if len(close) < 2:
        return 0
    direction = 1 if close[-1] > close[-2] else -1 if close[-1] < close[-2] else 0
    if direction == 0:
        return 0
    n = 0
    for i in range(len(close) - 1, 0, -1):
        d = 1 if close[i] > close[i - 1] else -1 if close[i] < close[i - 1] else 0
        if d != direction:
            break
        n += 1
    return n * direction


def _arrows(close, n=5):
    out = []
    for i in range(max(1, len(close) - n), len(close)):
        out.append("↑" if close[i] > close[i - 1] else "↓" if close[i] < close[i - 1] else "→")
    return out


def _updown_days(close, n=20):
    ups = downs = 0
    for i in range(max(1, len(close) - n), len(close)):
        if close[i] > close[i - 1]:
            ups += 1
        elif close[i] < close[i - 1]:
            downs += 1
    return ups, downs


def series_stats(close):
    """B-1 · B-2. close는 오래된 것 → 최신 순."""
    ma20 = _ma(close, 20)
    ma50 = _ma(close, 50)
    ma20_prev = _ma(close[:-5], 20) if len(close) >= 25 else None
    last = close[-1] if close else None
    ups, downs = _updown_days(close)
    return {
        "last": round(last, 4) if last is not None else None,
        "ret_1d": _ret(close, 1),
        "ret_5d": _ret(close, 5),
        "ret_20d": _ret(close, 20),
        "ma20": ma20,
        "ma50": ma50,
        "above_ma20": (last > ma20) if (last is not None and ma20 is not None) else None,
        "above_ma50": (last > ma50) if (last is not None and ma50 is not None) else None,
        "ma20_slope": (1 if ma20 > ma20_prev else -1 if ma20 < ma20_prev else 0)
        if (ma20 is not None and ma20_prev is not None) else None,
        "streak": _streak(close),
        "last5": _arrows(close),
        "up_days_20": ups,
        "down_days_20": downs,
        "bars": len(close),
    }


def position_stats(close):
    """B-3. 20일 고저점 대비 위치와 라벨."""
    if len(close) < 21:
        return None
    window = close[-20:]
    high, low, last = max(window), min(window), close[-1]
    from_high = _pct(last, high)
    from_low = _pct(last, low)
    ret_20d = _ret(close, 20)
    if from_high is not None and from_high > -1 and ret_20d is not None and ret_20d > 5:
        label = "단기 고점 부근 · 과열 주의"
    elif from_high is not None and from_high > -1:
        label = "20일 고점 부근"
    elif from_low is not None and from_low < 1:
        label = "20일 저점 부근"
    else:
        label = "박스 중간"
    return {
        "high_20d": round(high, 4),
        "low_20d": round(low, 4),
        "from_high_pct": from_high,
        "from_low_pct": from_low,
        "position_label": label,
    }


def _diff(a, b):
    if a is None or b is None:
        return None
    return round(a - b, 2)


def _rs_streak(close_a, close_b):
    """a의 일간 수익률이 b를 웃돈 날이 연속된 일수."""
    n = min(len(close_a), len(close_b))
    if n < 2:
        return 0
    a, b = close_a[-n:], close_b[-n:]
    streak = 0
    for i in range(n - 1, 0, -1):
        ra = a[i] / a[i - 1] - 1
        rb = b[i] / b[i - 1] - 1
        if ra > rb:
            streak += 1
        else:
            break
    return streak


# ---------------------------------------------------------------- 구간 규칙

def breadth_proxy(series):
    """B-5 프록시. 섹터 ETF 11개 중 상승 개수와 RSP−SPY."""
    ups = downs = counted = 0
    for etf in BREADTH_SECTORS:
        r = (series.get(etf) or {}).get("ret_1d")
        if r is None:
            continue
        counted += 1
        if r >= 0:
            ups += 1
        else:
            downs += 1
    ratio = round(ups / counted * 100, 1) if counted else None
    if ratio is None:
        label = None
    elif ratio >= 65:
        label = f"{GREEN} 양호"
    elif ratio >= 45:
        label = f"{YELLOW} 보통"
    else:
        label = f"{RED} 취약"
    rsp, spy = series.get("RSP") or {}, series.get("SPY") or {}
    return {
        "mode": "proxy",
        "sectors_up": ups,
        "sectors_down": downs,
        "sectors_counted": counted,
        "ratio": ratio,
        "label": label,
        "rsp_spy_1d": _diff(rsp.get("ret_1d"), spy.get("ret_1d")),
        "rsp_spy_5d": _diff(rsp.get("ret_5d"), spy.get("ret_5d")),
    }


def sector_rotation(series):
    """B-6. 1D 순위와 5D 순위 변화."""
    rows = []
    for etf, theme in SECTOR_THEME.items():
        s = series.get(etf)
        if not s or s.get("ret_1d") is None:
            continue
        rows.append({"etf": etf, "theme": theme, "ret_1d": s["ret_1d"],
                     "ret_5d": s.get("ret_5d"), "ret_20d": s.get("ret_20d")})
    by_5d = sorted([r for r in rows if r["ret_5d"] is not None],
                   key=lambda r: r["ret_5d"], reverse=True)
    rank_5d = {r["etf"]: i + 1 for i, r in enumerate(by_5d)}
    ranked = sorted(rows, key=lambda r: r["ret_1d"], reverse=True)
    for i, r in enumerate(ranked, 1):
        r["rank_1d"] = i
        r["rank_5d"] = rank_5d.get(r["etf"])
        r["rank_change"] = (r["rank_5d"] - i) if r["rank_5d"] else None
    return {
        "ranked_1d": ranked,
        "leaders": [r["etf"] for r in ranked[:3]],
        "laggards": [r["etf"] for r in ranked[-3:]][::-1],
    }


def rates_block(prices, series, macro):
    """B-7. 당일 10Y는 ^TNX, 나머지는 FRED."""
    tnx = (prices.get("series") or {}).get("^TNX") or {}
    close = tnx.get("close") or []
    us10y = round(close[-1], 2) if close else None
    chg_1d = round((close[-1] - close[-2]) * 100) if len(close) >= 2 else None
    chg_5d = round((close[-1] - close[-6]) * 100) if len(close) >= 6 else None

    def fred(key):
        rec = macro.get(key)
        return rec.get("value") if isinstance(rec, dict) else None

    qqq_5d = (series.get("QQQ") or {}).get("ret_5d")
    if chg_5d is None or qqq_5d is None:
        label = None
    elif chg_5d >= 10 and qqq_5d < 0:
        label = "금리 상승이 성장주에 부담"
    elif chg_5d <= -10 and qqq_5d > 0:
        label = "금리 하락과 성장주 강세 동반"
    elif chg_5d >= 10 and qqq_5d > 0:
        label = "금리 상승에도 성장주 견조"
    else:
        label = "금리 영향 중립"
    return {
        "us10y": us10y,
        "us10y_fred": fred("us10y"),
        "us2y": fred("us2y"),
        "spread_10_2": fred("spread_10_2"),
        "fed_funds": fred("fed_funds"),
        "us10y_change_1d_bp": chg_1d,
        "us10y_change_5d_bp": chg_5d,
        "growth_label": label,
    }


def regime_score(series, breadth, vix, rates, rs):
    """B-8. 다섯 요소, 합 100."""
    spy = series.get("SPY") or {}
    trend = 0
    if spy.get("above_ma20"):
        trend += 10
    if spy.get("above_ma50"):
        trend += 10
    if (spy.get("ma20_slope") or 0) > 0:
        trend += 5

    ratio = breadth.get("ratio")
    if ratio is None:
        breadth_pts = 8
    elif ratio >= 70:
        breadth_pts = 20
    elif ratio >= 55:
        breadth_pts = 14
    elif ratio >= 45:
        breadth_pts = 8
    else:
        breadth_pts = 0

    v = vix.get("now")
    if v is None:
        vol = 8
    elif v < 15:
        vol = 20
    elif v < 20:
        vol = 14
    elif v < 25:
        vol = 8
    elif v < 30:
        vol = 3
    else:
        vol = 0
    if (vix.get("change_5d") or 0) < -2:
        vol = min(20, vol + 2)

    bp = rates.get("us10y_change_5d_bp")
    if bp is None:
        rates_pts = 6
    elif bp <= -10:
        rates_pts = 15
    elif bp <= 0:
        rates_pts = 11
    elif bp <= 10:
        rates_pts = 6
    else:
        rates_pts = 0

    tlt = series.get("TLT") or {}
    hyg = series.get("HYG") or {}
    appetite = 0
    if (rs.get("qqq_spy_5d") or 0) > 0:
        appetite += 5
    if (rs.get("iwm_spy_5d") or 0) > 0:
        appetite += 5
    spy_tlt = _diff(spy.get("ret_5d"), tlt.get("ret_5d"))
    if spy_tlt is not None and spy_tlt > 0:
        appetite += 5
    if (hyg.get("ret_5d") or 0) > 0:
        appetite += 5

    score = trend + breadth_pts + vol + rates_pts + appetite
    if score >= REGIME_RISK_ON:
        label, light = "Risk-On", GREEN
    elif score >= REGIME_RISK_OFF:
        label, light = "Neutral", YELLOW
    else:
        label, light = "Risk-Off", RED
    return {
        "score": score,
        "label": label,
        "light": light,
        "components": {
            "trend": {"score": trend, "max": 25},
            "breadth": {"score": breadth_pts, "max": 20},
            "volatility": {"score": vol, "max": 20},
            "rates": {"score": rates_pts, "max": 15},
            "risk_appetite": {"score": appetite, "max": 20},
        },
    }


def status_board(series, breadth, vix, rates, position):
    """B-9. 신호등 5개와 종합."""
    spy = series.get("SPY") or {}
    above = int(bool(spy.get("above_ma20"))) + int(bool(spy.get("above_ma50")))
    trend = GREEN if above == 2 else YELLOW if above == 1 else RED

    v = vix.get("now")
    volatility = None if v is None else GREEN if v < 18 else YELLOW if v <= 25 else RED

    ratio = breadth.get("ratio")
    breadth_light = None if ratio is None else GREEN if ratio >= 55 else YELLOW if ratio >= 45 else RED

    bp = rates.get("us10y_change_5d_bp")
    rates_light = None if bp is None else GREEN if bp <= 5 else YELLOW if bp <= 15 else RED

    ret_20d = spy.get("ret_20d")
    from_high = (position.get("SPY") or {}).get("from_high_pct")
    if ret_20d is None:
        overheat = None
    elif ret_20d >= 6 and from_high is not None and from_high > -0.5:
        overheat = RED
    elif ret_20d >= 4:
        overheat = YELLOW
    else:
        overheat = GREEN

    lights = [trend, volatility, breadth_light, rates_light, overheat]
    known = [l for l in lights if l]
    overall = RED if RED in known else YELLOW if known.count(YELLOW) >= 2 else GREEN
    return {
        "trend": trend,
        "volatility": volatility,
        "breadth": breadth_light,
        "rates": rates_light,
        "overheat": overheat,
        "overall": overall,
    }


def watch_list(series, position, vix, rates, breadth, sectors, regime):
    """B-10. 후보를 규칙으로 만들고 우선순위대로 5개."""
    out = []
    spx = position.get("sp500") or {}
    spx_s = series.get("^GSPC") or {}

    # 레인지가 좁으면 고점·저점이 둘 다 2% 안에 들어온다. 가까운 쪽 하나만 본다.
    near_high = spx.get("from_high_pct") is not None and spx["from_high_pct"] > -2
    near_low = spx.get("from_low_pct") is not None and spx["from_low_pct"] < 2
    if near_high and near_low:
        if abs(spx["from_high_pct"]) <= abs(spx["from_low_pct"]):
            near_low = False
        else:
            near_high = False
    if near_high:
        out.append({"id": "spx_high", "metric": "S&P 500 20일 고점",
                    "level": round(spx["high_20d"], 2), "direction": "상향 돌파 여부"})
    if near_low:
        out.append({"id": "spx_low", "metric": "S&P 500 20일 저점",
                    "level": round(spx["low_20d"], 2), "direction": "하향 이탈 여부"})
    ma20 = spx_s.get("ma20")
    if ma20 and spx_s.get("last") and abs(_pct(spx_s["last"], ma20) or 99) < 1:
        out.append({"id": "spx_ma20", "metric": "S&P 500 20일선",
                    "level": round(ma20, 2), "direction": "회복/이탈 여부"})
    v = vix.get("now")
    if v is not None:
        for th in (20, 25):
            if abs(v - th) <= 3:
                out.append({"id": f"vix_{th}", "metric": "VIX", "level": th,
                            "direction": "상향 돌파 여부"})
                break
    if rates.get("us10y") is not None:
        y = rates["us10y"]
        level = round((int(y * 10) + 1) / 10, 1)
        out.append({"id": "us10y_level", "metric": "미국 10년물 금리 (%)",
                    "level": level, "direction": "상향 돌파 여부"})
    ratio = breadth.get("ratio")
    if ratio is not None and 40 <= ratio <= 60:
        out.append({"id": "breadth_50", "metric": "섹터 상승 비율 (%)",
                    "level": 50, "direction": "50% 유지 여부"})
    leaders = sectors.get("leaders") or []
    if leaders:
        top = next((r for r in sectors["ranked_1d"] if r["etf"] == leaders[0]), None)
        if top and top.get("rank_5d") and top["rank_5d"] <= 3:
            out.append({"id": "leader_rs", "metric": f"주도 섹터 {top['etf']} ({top['theme']})",
                        "level": "1D·5D 모두 상위 3위", "direction": "상대강도 유지 여부"})
    score = regime.get("score")
    if score is not None:
        for th in (REGIME_RISK_OFF, REGIME_RISK_ON):
            if abs(score - th) <= 5:
                out.append({"id": "regime_flip", "metric": "Regime Score",
                            "level": th, "direction": "등급 전환 여부"})
                break
    return out[:5]


# ---------------------------------------------------------------- 이력

def _load_prev_regime(state_dir, today):
    path = os.path.join(state_dir, "regime.jsonl")
    if not os.path.exists(path):
        return None
    prev = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("date") and rec["date"] < today:
                if prev is None or rec["date"] > prev["date"]:
                    prev = rec
    return prev


def _save_history(state_dir, analysis):
    hist_dir = os.path.join(state_dir, "history")
    os.makedirs(hist_dir, exist_ok=True)
    date = analysis["date"]

    slim = {k: v for k, v in analysis.items() if k != "raw"}
    with open(os.path.join(hist_dir, f"{date}.json"), "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False, indent=2)

    line = {
        "date": date,
        "as_of": analysis.get("as_of"),
        "score": analysis["regime"]["score"],
        "label": analysis["regime"]["label"],
        "components": {k: v["score"] for k, v in analysis["regime"]["components"].items()},
        "overall": analysis["status"]["overall"],
        "breadth_ratio": analysis["breadth"].get("ratio"),
        "vix": analysis["vix"].get("now"),
        "us10y": analysis["rates"].get("us10y"),
        "spy_ret_1d": (analysis["series"].get("SPY") or {}).get("ret_1d"),
    }
    path = os.path.join(state_dir, "regime.jsonl")
    kept = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    if json.loads(raw).get("date") == date:
                        continue  # 같은 날 재실행이면 덮어쓴다
                except ValueError:
                    continue
                kept.append(raw)
    kept.append(json.dumps(line, ensure_ascii=False))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(kept) + "\n")


# ---------------------------------------------------------------- 진입점

def analyze(input_path, prices_path, output_path, state_dir=STATE_DIR):
    with open(input_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    with open(prices_path, "r", encoding="utf-8") as f:
        prices = json.load(f)

    today = raw.get("date")
    closes = {sym: rec["close"] for sym, rec in (prices.get("series") or {}).items() if rec.get("close")}

    series = {sym: series_stats(c) for sym, c in closes.items()}

    position = {}
    for key, sym in INDEX_SYMBOL.items():
        if key != "vix" and sym in closes:
            p = position_stats(closes[sym])
            if p:
                position[key] = p
    for sym in ("SPY", "QQQ", "IWM"):
        if sym in closes:
            p = position_stats(closes[sym])
            if p:
                position[sym] = p

    vix_close = closes.get("^VIX") or []
    vix = {
        "now": round(vix_close[-1], 2) if vix_close else None,
        "prev_5d": round(vix_close[-6], 2) if len(vix_close) >= 6 else None,
        "change_5d": round(vix_close[-1] - vix_close[-6], 2) if len(vix_close) >= 6 else None,
    }

    g = lambda s: series.get(s) or {}
    rs = {
        "qqq_spy_5d": _diff(g("QQQ").get("ret_5d"), g("SPY").get("ret_5d")),
        "iwm_spy_5d": _diff(g("IWM").get("ret_5d"), g("SPY").get("ret_5d")),
        "rsp_spy_5d": _diff(g("RSP").get("ret_5d"), g("SPY").get("ret_5d")),
        "qqq_streak": _rs_streak(closes.get("QQQ") or [], closes.get("SPY") or []),
    }

    breadth = breadth_proxy(series)
    sectors = sector_rotation(series)
    rates = rates_block(prices, series, raw.get("macro") or {})
    regime = regime_score(series, breadth, vix, rates, rs)
    status = status_board(series, breadth, vix, rates, position)
    watch = watch_list(series, position, vix, rates, breadth, sectors, regime)

    prev = _load_prev_regime(state_dir, today)
    regime["score_prev"] = prev["score"] if prev else None
    regime["prev_date"] = prev["date"] if prev else None
    regime["delta"] = (regime["score"] - prev["score"]) if prev else None

    symbols = sorted(set(closes) | {q["symbol"] for q in raw.get("gainers", []) + raw.get("most_active", []) if q.get("symbol")})

    # 시계열의 마지막 종가가 fast_info 당일가와 다르면 시계열에 오늘 바가 아직 없는 것이다.
    # 날짜 비교는 주말·휴장에 오탐이 나서 가격으로 본다.
    as_of = prices.get("as_of")
    spot = ((raw.get("market") or {}).get("indices") or {}).get("sp500", {}).get("price")
    hist_last = (series.get("^GSPC") or {}).get("last")
    gap = _pct(hist_last, spot) if (spot and hist_last) else None
    stale = gap is not None and abs(gap) > 0.1

    analysis = {
        "date": today,
        "as_of": as_of,
        "history_stale": stale,
        "history_gap_pct": gap,
        "series": series,
        "position": position,
        "vix": vix,
        "rs": rs,
        "breadth": breadth,
        "sectors": sectors,
        "rates": rates,
        "regime": regime,
        "status": status,
        "watch": watch,
        "symbols": symbols,
        "raw": raw,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    _save_history(state_dir, analysis)

    comps = " · ".join(f"{k} {v['score']}/{v['max']}" for k, v in regime["components"].items())
    prev_txt = f" (어제 {regime['score_prev']}, {regime['delta']:+d})" if prev else " (이력 없음)"
    print(f"[분석] 기준일 {as_of}" + (f" — 시계열이 당일가와 {gap:+.2f}% 차이 (오늘 바 누락 의심)" if stale else ""))
    print(f"[분석] Regime {regime['light']} {regime['label']} {regime['score']}/100{prev_txt}")
    print(f"[분석]   {comps}")
    print(f"[분석] 상태판 {status['overall']}  추세 {status['trend']} 변동성 {status['volatility']} "
          f"폭 {status['breadth']} 금리 {status['rates']} 과열 {status['overheat']}")
    print(f"[분석] 시장 폭({breadth['mode']}) {breadth['ratio']}% {breadth['label']}  "
          f"주도 {sectors['leaders']}  약세 {sectors['laggards']}")
    print(f"[분석] 내일 체크 {[w['id'] for w in watch]}")
    print(f"analysis.json 저장 완료 -> {output_path}")
    return analysis


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    analyze(
        os.path.join(OUTPUT_DIR, "report_input.json"),
        os.path.join(OUTPUT_DIR, "prices.json"),
        os.path.join(OUTPUT_DIR, "analysis.json"),
    )
