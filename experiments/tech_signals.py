"""기술지표의 방향은? (카드 제목, P121) — 인베스팅닷컴 '기술적 분석' 화면의 지표 12 · 이동평균 6×2 를 우리 일봉으로 계산 (2026-10-30 사용자). AI 없음.
피벗 5가지는 뺐다 (10-30 사용자 P100: 장중 단타용 기준선이라 종가 블로그 독자에게 쓸모가 적고, 검증한 적 없고, 숫자 스무 개가 초보에게 어렵다).

용어 = 상승 · 하락 · 중립 하나로 (2026-10-30 사용자 P99: "오름 쪽 · 내림 쪽은 돌려 말하기 — 상승 · 하락, 화살표, 강한 상승 · 강한 하락").
  블로그는 매수 · 매도라고 쓰지 않는다 — 지표가 가리키는 가격 방향을 그대로 적고 판단은 독자가 한다 (법적 경계 선 4).
  오실레이터는 과매수 = 하락 · 과매도 = 상승으로 세고 줄에 (과매수) · (과매도)를 작게 붙인다. 이동평균은 종가가 선 위 ▲ · 아래 ▼.
  요약 = 강한 상승 · 상승 · 중립 · 하락 · 강한 하락, 색 = 상승 빨강 · 하락 파랑의 연한 상태 카드 톤(theme). 임계값은 널리 쓰는 기본값(RSI 70/30, 스토캐스틱 80/20, CCI ±100, Williams −20/−80, ADX 25).
인베스팅닷컴과 값이 다를 수 있다 — 그 표는 시간봉 기준으로 보이고(10-30 점검: 5일 이동평균이 최근 5일 종가 평균과 안 맞음), 우리는 일봉 · 주봉 · 월봉.

    compute(bars) → {"as_of", "close", "rows": [...], "counts", "net", "word", "ma": [...], "ma_counts", "weekly": counts, "monthly": counts}
    card(sig, name) → (lines, tip)  — nvda-report render_html._state_card 에 넣는 줄
"""

import datetime
import math

OVER, UNDER, MID, UPW, DNW = "과매수", "과매도", "중립", "상승", "하락"
WEAK = "추세 약함"
GAUGE_UP, GAUGE_DN = "#ED8E87", "#82B1F0"   # 게이지는 그래프 파스텔(cards.PASTEL_UP · PASTEL_DN) — 새빨간 · 새파란 면 금지 (P99)


def _ema(xs, n):
    k, out, e = 2 / (n + 1), [], None
    for x in xs:
        e = x if e is None else x * k + e * (1 - k)
        out.append(e)
    return out


def _wilder(xs, n):
    out, e = [], None
    for i, x in enumerate(xs):
        if e is None:
            if i + 1 < n:
                out.append(None)
                continue
            e = sum(xs[:n]) / n
        else:
            e = (e * (n - 1) + x) / n
        out.append(e)
    return out


def _sma(xs, n):
    return sum(xs[-n:]) / n if len(xs) >= n else None


def _rsi(c, n=14):
    d = [c[i] - c[i - 1] for i in range(1, len(c))]
    up = _wilder([max(x, 0) for x in d], n)
    dn = _wilder([max(-x, 0) for x in d], n)
    out = [None] * (len(c))
    for i in range(len(d)):
        if up[i] is None:
            continue
        out[i + 1] = 100.0 if dn[i] == 0 else 100 - 100 / (1 + up[i] / dn[i])
    return out


def _level(v, hi, lo):
    return None if v is None else OVER if v > hi else UNDER if v < lo else MID


def _dir_of(label):
    return {OVER: -1, UNDER: 1, UPW: 1, DNW: -1}.get(label, 0)


def indicators(bars):
    """일봉(또는 주봉 · 월봉) 목록 → 지표 줄 12개 [{key, name, value, text(값 표시), label, dir, hint}]."""
    c = [b["close"] for b in bars]
    h = [b["high"] if b.get("high") is not None else b["close"] for b in bars]
    l = [b["low"] if b.get("low") is not None else b["close"] for b in bars]
    n = len(c)
    rows = []
    if n < 30:
        return rows

    def add(key, name, value, label, hint, fmt="{:,.1f}"):
        rows.append({"key": key, "name": name, "value": value, "text": "—" if value is None else fmt.format(value).replace("-", "−"),
                     "label": label or "—", "dir": _dir_of(label), "hint": hint})
    rsi = _rsi(c)
    r = rsi[-1]
    add("rsi", "RSI(14)", r, _level(r, 70, 30), "흔히 70 넘으면 과매수 · 30 아래면 과매도로 읽음")
    # STOCH(9,6): %K 9일, %D 6일 단순 평균
    k = []
    for i in range(8, n):
        hh, ll = max(h[i - 8:i + 1]), min(l[i - 8:i + 1])
        k.append(50.0 if hh == ll else (c[i] - ll) / (hh - ll) * 100)
    st = _sma(k, 6)
    add("stoch", "STOCH(9,6)", st, _level(st, 80, 20), "9일 고가 · 저가 사이에서 종가의 위치(6일 평균) · 80 위 과매수 · 20 아래 과매도")
    rr = [x for x in rsi if x is not None]
    if len(rr) >= 14:
        w = rr[-14:]
        sr = 50.0 if max(w) == min(w) else (rr[-1] - min(w)) / (max(w) - min(w)) * 100
    else:
        sr = None
    add("stochrsi", "STOCHRSI(14)", sr, _level(sr, 80, 20), "RSI 를 다시 14일 범위에서 본 값 · 80 위 과매수 · 20 아래 과매도")
    e12, e26 = _ema(c, 12), _ema(c, 26)
    macd = [a - b for a, b in zip(e12, e26)]
    sig = _ema(macd, 9)
    add("macd", "MACD(12,26)", macd[-1], UPW if macd[-1] > sig[-1] else DNW, "12일 · 26일 지수 평균의 차 — 신호선(9일) 위면 상승, 아래면 하락", "{:,.0f}" if abs(macd[-1]) >= 100 else "{:,.2f}")
    # ADX(14) + DI
    tr, pdm, mdm = [], [], []
    for i in range(1, n):
        tr.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
        up, dn = h[i] - h[i - 1], l[i - 1] - l[i]
        pdm.append(up if up > dn and up > 0 else 0.0)
        mdm.append(dn if dn > up and dn > 0 else 0.0)
    atr, pw, mw = _wilder(tr, 14), _wilder(pdm, 14), _wilder(mdm, 14)
    dx, pdi, mdi = [], None, None
    for a, p, m in zip(atr, pw, mw):
        if a is None or not a:
            continue
        pdi, mdi = 100 * p / a, 100 * m / a
        dx.append(0.0 if pdi + mdi == 0 else 100 * abs(pdi - mdi) / (pdi + mdi))
    adx = _wilder(dx, 14)[-1] if len(dx) >= 14 else None
    adx_label = None if adx is None else (WEAK if adx < 25 else (UPW if pdi > mdi else DNW))
    add("adx", "ADX(14)", adx, adx_label, "추세의 세기 — 25 아래면 뚜렷한 추세 없음, 그 위면 +DI · −DI 가운데 큰 쪽")
    hh, ll = max(h[-14:]), min(l[-14:])
    wr = None if hh == ll else (hh - c[-1]) / (hh - ll) * -100
    add("wr", "Williams %R", wr, None if wr is None else (OVER if wr > -20 else UNDER if wr < -80 else MID), "14일 고가 · 저가 사이 종가 위치 · −20 위 과매수 · −80 아래 과매도")
    tp = [(a + b + d) / 3 for a, b, d in zip(h, l, c)]
    w = tp[-14:]
    m = sum(w) / 14
    md = sum(abs(x - m) for x in w) / 14
    cci = None if md == 0 else (tp[-1] - m) / (0.015 * md)
    add("cci", "CCI(14)", cci, _level(cci, 100, -100), "평균 가격에서 얼마나 벗어났나 · +100 위 과매수 · −100 아래 과매도")
    a14 = atr[-1]
    atr_pct = a14 / c[-1] * 100 if a14 else None
    hist = [x / y * 100 for x, y in zip(atr[-250:], c[-250:]) if x]
    med = sorted(hist)[len(hist) // 2] if hist else None
    atr_label = None if atr_pct is None or med is None else ("변동성 큼" if atr_pct > med * 1.3 else "변동성 낮음" if atr_pct < med * 0.7 else "변동성 보통")
    rows.append({"key": "atr", "name": "ATR(14)", "value": a14, "text": "—" if a14 is None else f"{a14:,.0f} ({atr_pct:.1f}%)", "label": atr_label or "—", "dir": 0,
                 "hint": "하루 평균 진폭 · 1년 평소보다 30% 넘게 크면 큼, 작으면 낮음"})
    hl = c[-1] - (hh + ll) / 2
    add("hl", "Highs/Lows(14)", hl, UPW if hl > 0 else DNW if hl < 0 else MID, "14일 고가 · 저가의 가운데보다 종가가 위면 상승 · 아래면 하락", "{:,.0f}")
    # Ultimate Oscillator (7 · 14 · 28)
    bp, trr = [], []
    for i in range(1, n):
        lo = min(l[i], c[i - 1])
        bp.append(c[i] - lo)
        trr.append(max(h[i], c[i - 1]) - lo)
    def avg(k):
        s = sum(trr[-k:])
        return sum(bp[-k:]) / s if s else None
    a7, a14_, a28 = avg(7), avg(14), avg(28)
    uo = None if None in (a7, a14_, a28) else 100 * (4 * a7 + 2 * a14_ + a28) / 7
    add("uo", "Ultimate Oscillator", uo, _level(uo, 70, 30), "7 · 14 · 28일 매수 압력의 가중 평균 · 70 위 과매수 · 30 아래 과매도")
    roc = (c[-1] / c[-13] - 1) * 100 if n > 13 else None
    add("roc", "ROC(12)", roc, None if roc is None else (UPW if roc > 0 else DNW if roc < 0 else MID), "12일 전보다 몇 % 올랐나 · 0 위 상승 · 아래 하락", "{:+.2f}%")
    e13 = _ema(c, 13)[-1]
    bb = (h[-1] - e13) + (l[-1] - e13)
    add("bb", "Bull/Bear Power(13)", bb, UPW if bb > 0 else DNW if bb < 0 else MID, "오늘 고가 · 저가가 13일 지수 평균보다 위면 상승 · 아래면 하락", "{:,.0f}")
    return rows


def counts(rows):
    cnt = {"up": sum(1 for r in rows if r["dir"] > 0), "down": sum(1 for r in rows if r["dir"] < 0),
           "neutral": sum(1 for r in rows if r["dir"] == 0 and r["key"] != "atr")}
    tot = cnt["up"] + cnt["down"] + cnt["neutral"]
    cnt["net"] = (cnt["up"] - cnt["down"]) / tot if tot else 0.0
    return cnt


def word(net):
    """카드 답 — 개수 비율 (상승 − 하락) ÷ 11: ±0.5 넘으면 강한, ±0.15 넘으면 상승 · 하락, 그 사이 중립 (P99)."""
    return "▲ 강한 상승" if net >= 0.5 else "▲ 상승" if net >= 0.15 else "▼ 강한 하락" if net <= -0.5 else "▼ 하락" if net <= -0.15 else "중립"


def theme(net, up_color, down_color, muted):
    """(상태 카드 theme, 답 글자 색) — 상승 = positive(연한 주황 바탕 · 빨강 글자), 하락 = negative(연한 파랑 바탕 · 파랑 글자), 중립 = 회색. 바탕을 진하게 채우지 않는다 (P99)."""
    return ("positive", up_color) if net >= 0.15 else ("negative", down_color) if net <= -0.15 else ("neutral", muted)


# 이동평균 기간 · 배열 · 크로스 — 시장 관행대로 (P119, 사용자: "한국 종목만 60일 · 120일")
#   한국 증권사 앱 = 5 · 20 · 60 · 120일(배열), 20 · 60일선(크로스) / 미국 = 20 · 50 · 200일(배열), 50 · 200일선(크로스)
MA_PERIODS = {"us": (5, 10, 20, 50, 100, 200), "kr": (5, 10, 20, 60, 120, 200)}
ARRAY_PERIODS = {"us": (20, 50, 200), "kr": (5, 20, 60, 120)}
CROSS_PAIR = {"us": (50, 200), "kr": (20, 60)}


def _sma_series(c, n):
    out, acc = [], 0.0
    for i, x in enumerate(c):
        acc += x
        if i >= n:
            acc -= c[i - n]
        out.append(acc / n if i >= n - 1 else None)
    return out


def ma_array(c, periods):
    """정배열(짧은 선 > 긴 선 순서) · 역배열(거꾸로) · 혼조 — 종가 단순 평균 기준."""
    vals = [_sma(c, n) for n in periods]
    if None in vals:
        return None
    if all(a > b for a, b in zip(vals, vals[1:])):
        return {"periods": periods, "state": "정배열", "dir": 1}
    if all(a < b for a, b in zip(vals, vals[1:])):
        return {"periods": periods, "state": "역배열", "dir": -1}
    return {"periods": periods, "state": "혼조", "dir": 0}


def ma_cross(c, pair):
    """가장 최근 골든크로스(짧은 선이 긴 선 위로) · 데드크로스(아래로)와 며칠 전인지 (거래일)."""
    s, l = _sma_series(c, pair[0]), _sma_series(c, pair[1])
    d = [None if a is None or b is None else a - b for a, b in zip(s, l)]
    for i in range(len(d) - 1, 0, -1):
        if d[i] is not None and d[i - 1] is not None and (d[i] > 0) != (d[i - 1] > 0):
            return {"pair": pair, "kind": "골든크로스" if d[i] > 0 else "데드크로스", "dir": 1 if d[i] > 0 else -1, "days_ago": len(d) - 1 - i}
    return None


def moving_averages(bars, periods=MA_PERIODS["us"]):
    c = [b["close"] for b in bars]
    out = []
    for n in periods:
        s = _sma(c, n)
        e = _ema(c, n)[-1] if len(c) >= n else None
        out.append({"n": n, "sma": s, "ema": e, "sma_above": None if s is None else c[-1] > s, "ema_above": None if e is None else c[-1] > e})
    return out


def resample(bars, kind):
    """일봉 → 주봉(월~금) · 월봉. 마지막 묶음은 진행 중인 주 · 달."""
    out, cur, key = [], None, None
    for b in bars:
        d = datetime.date.fromisoformat(b["day"])
        k = d.isocalendar()[:2] if kind == "W" else (d.year, d.month)
        if k != key:
            if cur:
                out.append(cur)
            cur, key = {"day": b["day"], "open": b.get("open") or b["close"], "high": b.get("high") or b["close"], "low": b.get("low") or b["close"], "close": b["close"]}, k
        else:
            cur["high"] = max(cur["high"], b.get("high") or b["close"])
            cur["low"] = min(cur["low"], b.get("low") or b["close"])
            cur["close"] = b["close"]
            cur["day"] = b["day"]
    if cur:
        out.append(cur)
    return out


def ma_counts(ma):
    up = sum(1 for m in ma for k in ("sma_above", "ema_above") if m[k] is True)
    dn = sum(1 for m in ma for k in ("sma_above", "ema_above") if m[k] is False)
    return {"up": up, "down": dn, "neutral": 0, "net": (up - dn) / (up + dn) if up + dn else 0.0}


def overall(ic, mc):
    """전체 요약 = 기술 지표(방향 있는 11개) + 이동평균(12개)을 한데 센 비율 — 인베스팅닷컴 '요약' 게이지 자리 (P101)."""
    up, dn = ic["up"] + mc["up"], ic["down"] + mc["down"]
    tot = up + dn + ic["neutral"]
    return {"up": up, "down": dn, "neutral": ic["neutral"], "net": (up - dn) / tot if tot else 0.0}


def _frame(bars, market="us"):
    rows, ma = indicators(bars), moving_averages(bars, MA_PERIODS[market])
    ic, mc = counts(rows), ma_counts(ma)
    return rows, ma, ic, mc, overall(ic, mc)


def compute(bars, market="us"):
    """일봉 → 전체 요약 · 기술 지표 · 이동평균 세 묶음 (인베스팅닷컴 기술적 분석과 같은 구성, 피벗 제외 · P100 · P101). 주봉 · 월봉은 전체 요약만.
    market = "kr" 이면 이동평균 5 · 10 · 20 · 60 · 120 · 200일, 배열 5 · 20 · 60 · 120, 크로스 20 · 60 (P119)."""
    market = market if market in MA_PERIODS else "us"
    bars = [b for b in bars if b.get("close")]
    if len(bars) < 30:
        return None
    rows, ma, ic, mc, al = _frame(bars, market)
    closes = [b["close"] for b in bars]
    out = {"as_of": bars[-1]["day"], "close": bars[-1]["close"],
           "net": al["net"], "word": word(al["net"]), "all": al,   # 카드 답 = 전체 요약
           "rows": rows, "counts": ic, "ind_net": ic["net"],
           "ma": ma, "ma_counts": {"above": mc["up"], "below": mc["down"]}, "ma_net": mc["net"],
           "market": market, "array": ma_array(closes, ARRAY_PERIODS[market]), "cross": ma_cross(closes, CROSS_PAIR[market])}
    for kind, key in (("W", "weekly"), ("M", "monthly")):
        rb = resample(bars, kind)
        out[key] = _frame(rb, market)[4] if len(rb) >= 30 else None
    return out


# ---------------------------------------------------------------- 그리기 (nvda-report render_html._state_card 의 lines)

# 게이지 다섯 칸 — 강한 하락 · 하락 · 중립 · 상승 · 강한 상승 (인베스팅닷컴 적극 매도 ~ 적극 매수 자리, P101). 색은 연한 톤(BAR_PASTEL 계열), 바깥 둘이 조금 진하다
ZONES = [(-1.0, -0.5, "강한 하락", "#82B1F0"), (-0.5, -0.15, "하락", "#BCD3F5"), (-0.15, 0.15, "중립", "#E2E8F0"),
         (0.15, 0.5, "상승", "#F8C4BF"), (0.5, 1.0, "강한 상승", "#ED8E87")]


# 지표 줄 라벨 박스 (10-30 사용자 P102): 바탕이 칠해진 사각 박스 안에 기호 + 글자, 같은 폭이라 세로 열이 맞는다. 색 = 공용 라벨(design_kit.PILL) 톤
# 10-30 사용자 P103: 버튼 말고 라벨 느낌 — 외곽선 연하게, 셋 다 연한 바탕(하락 바탕이 하락 카드 바탕과 같아 색이 없어 보였다), 가로 짧게 · 높이 그대로
BOX = {"up": ("#FDE8E8", "#F6CACA", "#B91C1C"), "down": ("#DCE9FC", "#C3D7F5", "#1D4ED8"), "flat": ("#E8EDF3", "#D6DEE8", "#475569")}
BOX_W = 50
DIVIDER = '<span aria-hidden="true" style="display:inline-block;width:1px;height:11px;margin:0 6px;background:#CBD5E1;vertical-align:-1px;"></span>'   # 세로 구분선: 글자 14px 의 80% = 11.2 → 11px, 양옆 6 (P116, 정수 규칙)
PAIR_GAP = 5   # 작은 게이지 카드 둘 사이 = 전체요약 카드와의 위 여백 (P108 · P114: 8 → 5, −40%)
TABLE_FS, TABLE_LH, WHY_FS = "15px", "23px", "13px"   # P113: 줄 높이 − 글자 = 짝수(위아래 여백 정수) — 15/23 · 13/19 · 14/22   # P104: 표 줄만 16 → 15 (사용자 "구분선으로 나눠 있는 정보만 한 포인트")   # 표 글자 18 → 16 (사용자 "두 단계 작게", 한 단계 = 1px · P96 과 같은 셈) · 괄호 글 14 → 13


# 이동평균 기간 옆 설명 (P109) — 거래일 기준 대략의 달력 길이 (20거래일 ≈ 1달)
MA_WHAT = {5: "1주", 10: "2주", 20: "1달", 50: "2.5달", 60: "3달", 100: "5달", 120: "6달", 200: "10달"}
# 지표 이름 옆 아주 작은 설명 (P108, 사용자: "구분명이 무엇인지 짧게, 줄바꿈 되면 안 돼") — 2~5자
WHAT = {"rsi": "상대강도", "stoch": "9일 위치", "stochrsi": "RSI 위치", "macd": "추세 전환", "adx": "추세 세기", "wr": "14일 위치",
        "cci": "평균 이탈", "atr": "하루 진폭", "hl": "고저 중간", "uo": "3기간 종합", "roc": "변화율", "bb": "13일선 대비"}


def _mark(kind):
    """박스 안 기호 — ▲ · ▼ 는 같은 크기 삼각형, 중립은 삼각형 폭만 한 가로 막대 (10-30 사용자)."""
    if kind == "up":
        return '<svg viewBox="0 0 10 10" width="9" height="9" aria-hidden="true" style="flex:none;"><path d="M5 1.2 9.4 8.6H.6z" fill="currentColor"/></svg>'
    if kind == "down":
        return '<svg viewBox="0 0 10 10" width="9" height="9" aria-hidden="true" style="flex:none;"><path d="M5 8.8 9.4 1.4H.6z" fill="currentColor"/></svg>'
    return '<svg viewBox="0 0 10 10" width="9" height="9" aria-hidden="true" style="flex:none;"><rect x=".6" y="4" width="8.8" height="2" rx="1" fill="currentColor"/></svg>'


def box(kind, text, esc, sym=True):
    """라벨 하나 — 기호(▲ · ▼ · 가로 막대) + 글자, 고정 폭이라 열이 맞는다."""
    bg, bd, fg = BOX[kind]
    return (f'<span style="display:inline-flex;align-items:center;justify-content:center;gap:3px;width:{BOX_W}px;box-sizing:border-box;flex:none;'
            f'padding:3px 0 2px;background:{bg};border:1px solid {bd};border-radius:4px;color:{fg};font-size:14px;line-height:18px;font-weight:700;white-space:nowrap;">'
            f'{_mark(kind) if sym else ""}{esc(text)}</span>')


def label_box(label, esc):
    """(괄호 글 HTML, 박스 HTML) — 과매수 → (과매수) + [▼ 하락], 추세 약함 → (추세 약함) + [— 중립], ATR → (변동성) + [보통]."""
    why = ""
    if label in (OVER, UNDER):
        main, why = (DNW, OVER) if label == OVER else (UPW, UNDER)
    elif label == WEAK:
        main, why = MID, WEAK
    elif label.startswith("변동성 "):
        main, why = label.split(" ", 1)[1], "변동성"
    else:
        main = label
    kind = "up" if main == UPW else "down" if main == DNW else "flat"
    b = box(kind, main, esc, sym=main in (UPW, DNW, MID))
    w = f'<span style="font-size:{WHY_FS};line-height:19px;color:#6B7280;white-space:nowrap;">({esc(why)})</span>' if why else ""
    return w, b


def _table(rows_html, line, keep=(0,)):
    """줄 묶음 — 구분선은 keep 번째 줄 위에만(제목 아래 · 머리 줄 아래), 나머지 줄 사이 선은 없다 (P105).
    줄 위아래 9 → 5px: 줄 한 칸 높이(라벨 25 + 여백)가 약 20% 줄어든다."""
    return "".join(f'<span style="display:flex;justify-content:space-between;align-items:center;gap:8px;padding:{9 if i in keep else 5}px 0 5px;'
                   f'border-top:1px solid {line if i in keep else "transparent"};font-size:{TABLE_FS};line-height:{TABLE_LH};color:#111;">{r}</span>'
                   for i, r in enumerate(rows_html))


# 게이지 치수 — 모두 정수 px (P113, 사용자: "간격은 모두 정수로, 소수점 찍지 마").
# 작은 게이지는 폰(360px) 칸 안쪽 폭 134 그대로 그려 축소(옛 150 → 0.89배, 간격이 소수가 되던 원인)를 없앤다.
#   폭 · 반지름 · 위 여백 · 호 두께 · 바늘 두께 · 가운데 원 반지름 · 바늘 끝 ~ 호 안쪽 · 아래 여백(가운데 원 아래 ~ 그림 끝)
GAUGE_BIG = dict(width=260, r=90, top=30, arc=14, needle=3, hub=5, tip_gap=15, bottom=25)   # bottom 23 → 25: 칸 이름(강한 하락 · 강한 상승) ~ 답 글자 5 → 7px (+30%, 6.5 → 7, P123)
GAUGE_SMALL = dict(width=134, r=55, top=10, arc=10, needle=2, hub=3, tip_gap=10, bottom=11)   # bottom 6 → 11: 가운데 원 ~ 답 글자 9 → 14px (+50%, P114)


def gauge_svg(net, size="big"):
    """반원 게이지 다섯 칸 + 바늘 + (큰 것만) 칸 이름. 바늘 = net (−1 … +1), 왼쪽 끝 = −1.
    양 끝(강한 하락 · 강한 상승)은 호 끝 아래, 가운데 셋은 호 바깥 위 — 옆에 두면 폭 안에서 잘렸다 (10-30 목업)."""
    g = GAUGE_BIG if size == "big" else GAUGE_SMALL
    labels = size == "big"
    width, r = g["width"], g["r"]
    cx, cy = width // 2, r + g["top"]

    def ang(v):   # −1 → 180° (왼쪽), +1 → 0° (오른쪽)
        return math.radians(90 - max(-1.0, min(1.0, v)) * 90)

    def pt(v, rr):
        a = ang(v)
        return cx + rr * math.cos(a), cy - rr * math.sin(a)
    arcs = ""
    for lo, hi, _, col in ZONES:
        x0, y0 = pt(lo + 0.012, r)
        x1, y1 = pt(hi - 0.012, r)
        arcs += f'<path d="M{x0:.1f},{y0:.1f} A{r},{r} 0 0 1 {x1:.1f},{y1:.1f}" stroke="{col}" stroke-width="{g["arc"]}" fill="none"/>'
    labs = ""
    for i, (lo, hi, name, _) in enumerate(ZONES if labels else []):
        if i in (0, 4):   # 양 끝: 호 끝 바로 아래 가운데
            x, y = pt(-1.0 if i == 0 else 1.0, r)
            labs += f'<text x="{x:.0f}" y="{cy + 22}" font-size="12" fill="#6B7280" text-anchor="middle">{name}</text>'
            continue
        x, y = pt((lo + hi) / 2, r + 18)
        anchor = "end" if x < cx - 8 else "start" if x > cx + 8 else "middle"
        labs += f'<text x="{x:.0f}" y="{y + 4:.0f}" font-size="12" fill="#6B7280" text-anchor="{anchor}">{name}</text>'
    x, y = pt(net, r - g["arc"] // 2 - g["tip_gap"])   # 바늘 끝 ~ 호 안쪽 = tip_gap (P111: 옛 5 · 3.4 의 3배 → 15 · 10)
    needle = (f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#111" stroke-width="{g["needle"]}" stroke-linecap="round"/>'
              f'<circle cx="{cx}" cy="{cy}" r="{g["hub"]}" fill="#111"/>')
    h = cy + g["hub"] + g["bottom"]
    return (f'<svg viewBox="0 0 {width} {h}" width="{width}" height="{h}" aria-hidden="true" style="display:block;max-width:100%;height:auto;margin:0 auto;">'
            f'{arcs}{labs}{needle}</svg>')


POPULAR = "#6D28D9"   # 많이 보는 지표 = 이름 앞 보라 점 (P120: 옛 P119 이름 글자 보라 · 범례는 뺌), 테마 --badge-violet — RSI · 스토캐스틱 · MACD · 배열 · 크로스
POPULAR_KEYS = ("rsi", "stoch", "macd")
# 점 = 3px 원, 글머리표가 아니라 글자 윗선에서 1px 아래 (줄 높이 23 · 글자 15 → 줄 위 4 + 1 = 5px), 글자와 3px — 모두 정수
POP_DOT = f'<span aria-hidden="true" style="display:inline-block;width:3px;height:3px;border-radius:50%;background:{POPULAR};vertical-align:top;margin:5px 3px 0 0;"></span>'


def _sub(title, note=""):
    """카드 안 묶음 제목 — 인베스팅닷컴 '기술적 지표' · '이동평균' 구획 자리. 굵게, 아래 줄 구분선은 첫 줄이 맡는다. note = 오른쪽 작은 글(보라 범례)."""
    n = f'<span style="font-size:{WHY_FS};line-height:19px;font-weight:400;color:{POPULAR};">{note}</span>' if note else ""
    return (f'<span style="display:flex;justify-content:space-between;align-items:baseline;margin:18px 0 2px;font-weight:700;color:#111;font-size:18px;">'
            f'<span>{title}</span>{n}</span>')   # 19 → 18 (P105)


# 전체요약 답 아래 ~ 개수 줄 6 → 8 (P118) → 10px (+20%, 9.6 → 10, P119: margin-bottom 4)
# 제목 위 보이는 여백 14 → 20px (+40%, 19.6 → 20, P117) = 카드 위 여백 10 + 제목 margin-top 6 + 줄 높이 반쪽 4. 기준일(absolute top 10)은 그대로
def _tri_small(w, px):
    """답 앞 ▲ · ▼ 를 글자의 약 80% 크기로 (P112, 사용자: "삼각형 20% 더 작게") — 정수 px (P113: 19 → 15 · 18 → 14)."""
    if w[:1] in "▲▼":
        return f'<span style="font-size:{px}px;vertical-align:1px;">{w[0]}</span>{w[1:]}'
    return w


def _gauge_block(title, c, extra, up_color, down_color, muted, small=False, corner=""):
    """흰 카드(design_kit.MULTI) 안에 [오른쪽 위 corner] · 제목(가운데) · 게이지 · 답 · 개수 · extra (P107: 제목 · 기준일을 카드 안으로).
    small = 나란히 놓는 작은 게이지(칸 이름 없음). 큰 게이지 카드는 다른 그래프처럼 양쪽 5px 넓게(CHART_CARD_X)."""
    import design_kit as _dk
    w = word(c["net"])
    col = up_color if c["net"] >= 0.15 else down_color if c["net"] <= -0.15 else muted
    cnt = f'상승 {c["up"]} · 중립 {c["neutral"]} · 하락 {c["down"]}' if c.get("neutral") else f'상승 {c["up"]} · 하락 {c["down"]}'
    mx = 0 if small else _dk.CHART_CARD_X
    # 기준일 = 카드 안 오른쪽 위, 제목과 같은 높이 (두 줄이라 좁아 가운데 제목과 겹치지 않는다, P114)
    # 오른쪽 8 → 13px (+5, P124)
    top = (f'<span style="position:absolute;top:{_dk.CHART_CARD_PAD}px;right:13px;'
           f'text-align:right;font-size:14px;line-height:20px;color:{muted};">{corner}</span>') if corner else ""
    return (f'<span style="{_dk.MULTI}position:relative;margin:{"0" if small else f"6px {mx}px 0"};text-align:center;"><span style="display:block;padding:{_dk.CHART_CARD_PAD}px 8px;">'   # 좌우 8 — 세 카드 같게 (P116: 개수 · 주봉 · 월봉 한 줄 자리)
            f'{top}<span style="display:block;font-weight:700;color:#111;margin:6px 0 4px;font-size:{"14px" if small else "16px"};line-height:{"22px" if small else "24px"};">{title}</span>'   # 작은 게이지 제목 15 → 14 (P115)   # 17 → 16 · 작은 게이지 16 → 15 (P108)
            f'{gauge_svg(c["net"], "small" if small else "big")}'
            f'<span style="display:block;font-weight:700;color:{col};{"font-size:17px;line-height:23px;" if small else "font-size:19px;line-height:25px;margin-bottom:4px;"}">{_tri_small(w, 13 if small else 15)}</span>'   # 작은 게이지 답 18 → 17 · 삼각형 14 → 13 (P115)   # 작은 게이지 답 19 → 18 (P112)
            f'<span style="display:flex;flex-wrap:wrap;justify-content:center;margin-bottom:4px;font-size:14px;line-height:20px;color:{muted};"><span style="white-space:nowrap;">{cnt}</span>'   # 맨 아래 줄 ~ 카드 아래 13 → 17px (+30%, 16.9 → 17, P122)
            + (f'<span style="white-space:nowrap;">{extra}</span>' if extra else "") + '</span></span></span>')   # extra = 같은 줄 구분선 뒤 · 폭이 모자라면 그 묶음만 다음 줄 (P116)   # extra = 같은 줄 뒤 (P116)


def card(sig, name, up_color, down_color, muted="#6B7280"):
    """(lines, tip) — _state_card 줄 (P101: 인베스팅닷컴처럼 세 묶음).
    ① 전체 요약 게이지(+ 주봉 · 월봉 답) ② 기술 지표 게이지 + 지표 줄(이름 | 값 · 라벨, 뜻 줄 없음) ③ 이동평균 게이지 + 기간 줄(단순 | 지수)."""
    import html as _h
    day = f"{sig['as_of'][5:7].lstrip('0')}월 {sig['as_of'][8:10].lstrip('0')}일"
    al = sig.get("all") or {"up": 0, "down": 0, "neutral": 0, "net": sig["net"]}
    mc = {"up": sig["ma_counts"]["above"], "down": sig["ma_counts"]["below"], "neutral": 0, "net": sig.get("ma_net", 0.0)}
    frames = []
    for key, lab in (("weekly", "주봉"), ("monthly", "월봉")):
        w = sig.get(key)
        if w:
            col = up_color if w["net"] >= 0.15 else down_color if w["net"] <= -0.15 else muted
            frames.append(f'{lab} <b style="color:{col};">{_tri_small(word(w["net"]), 11)}</b>')   # 삼각형 14 의 80% = 11px (P116, 게이지 답과 같은 규칙)
    import design_kit as _dk
    # 게이지는 게이지끼리 맨 위 (10-30 사용자): 전체 요약 크게(칸 이름) → 기술 지표 · 이동평균 작게 나란히(색만 같게)
    pair = (f'<span style="display:flex;gap:{PAIR_GAP}px;margin:{PAIR_GAP}px {_dk.CHART_CARD_X}px 4px;">'   # 위 여백 = 두 카드 사이 (P108)   # 두 카드 바깥 선 = 전체 요약 카드 바깥 선 (P106)
            f'<span style="flex:1 1 0;min-width:0;">{_gauge_block("기술지표", sig["counts"], "", up_color, down_color, muted, small=True)}</span>'
            f'<span style="flex:1 1 0;min-width:0;">{_gauge_block("이동평균", mc, "", up_color, down_color, muted, small=True)}</span></span>')
    lines = [('<span style="display:block;height:6px;"></span>' + _gauge_block("전체요약", al,
                           (DIVIDER + " · ".join(frames)) if frames else "",   # 주봉 · 월봉 = 개수 줄 오른쪽, 세로 구분선 뒤 (P116)
                           up_color, down_color, muted, corner=f"{day} 종가<br>일봉 기준")   # 두 줄 · 가운뎃점 없이 (P114)   # 기준일 = 전체 요약 카드 안 오른쪽 위 (P107)
              + pair, "html"),
             ]
    import design_kit as _dk
    th, _ = theme(sig["net"], up_color, down_color, muted)
    line = _dk.darken(_dk.lighten(_dk.lighten(_dk.CARD_DIR[th][1]), 0.3), 0.02)   # _state_card 의 줄 구분선과 같은 색
    trs = []
    for r in sig["rows"]:
        w, bx = label_box(r["label"], _h.escape)
        what = WHAT.get(r["key"], "")
        nm = (POP_DOT if r["key"] in POPULAR_KEYS else "") + _h.escape(r["name"])
        trs.append(f'<span style="min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{nm}'   # 폭이 모자라는 날(긴 이름 + 괄호 글)은 설명 끝이 … 로 — 줄바꿈 없음 (P108)
                   + (f'<span style="margin-left:4px;font-size:{WHY_FS};line-height:19px;color:#6B7280;">{what}</span>' if what else "") + '</span>'   # 괄호 글(과매도)과 같은 13px 회색 (P109)
                   f'<span style="display:inline-flex;align-items:center;gap:6px;flex:none;">{w}<b style="font-weight:700;">{_h.escape(r["text"])}</b>{bx}</span>')   # (과매도) → 숫자 → 라벨: 숫자가 라벨 바로 왼쪽에 열로 (P103)
    lines.append((_sub("기술지표") + _table(trs, line), "html"))
    COLW = f"display:inline-flex;align-items:center;justify-content:flex-end;gap:4px;min-width:{BOX_W + 58}px;"   # 숫자 + 라벨 한 칸 — 인베스팅닷컴처럼 값마다 상승 · 하락 (P103, 옛 ▲ · ▼)

    def one(v, above):
        if v is None:
            return f'<span style="{COLW}">—</span>'
        return f'<span style="{COLW}"><span>{v:,.0f}</span>{box("up" if above else "down", UPW if above else DNW, _h.escape)}</span>'
    HEAD = f"font-size:{WHY_FS};line-height:19px;color:#6B7280;"   # 머리 줄 = 기간 옆 설명(1주 · 2주)과 같은 글씨 (P114)
    note = f"font-size:{WHY_FS};line-height:19px;color:#6B7280;"
    top_rows = []
    ar, cr = sig.get("array"), sig.get("cross")
    if ar:
        kind = "up" if ar["dir"] > 0 else "down" if ar["dir"] < 0 else "flat"
        top_rows.append(f'<span style="min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{POP_DOT}{ar["state"]}'
                        f'<span style="margin-left:4px;{note}">{" · ".join(str(n) for n in ar["periods"])}일</span></span>'
                        f'<span style="display:inline-flex;align-items:center;gap:6px;flex:none;">{box(kind, UPW if kind == "up" else DNW if kind == "down" else MID, _h.escape)}</span>')
    if cr:
        kind = "up" if cr["dir"] > 0 else "down"
        top_rows.append(f'<span style="min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{POP_DOT}{cr["kind"]}'
                        f'<span style="margin-left:4px;{note}">{cr["pair"][0]} · {cr["pair"][1]}일선</span></span>'
                        f'<span style="display:inline-flex;align-items:center;gap:6px;flex:none;"><b style="font-weight:700;">{cr["days_ago"]}일 전</b>{box(kind, UPW if kind == "up" else DNW, _h.escape)}</span>')
    mrs = top_rows + [f'<span style="{HEAD}">기간</span><span style="display:inline-flex;gap:6px;{HEAD}"><span style="{COLW}">단순</span><span style="{COLW}">지수</span></span>']
    for m in sig["ma"]:
        mrs.append(f'<span style="min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{m["n"]}일<span style="margin-left:4px;font-size:{WHY_FS};line-height:19px;color:#6B7280;">{MA_WHAT.get(m["n"], "")}</span></span>'
                   f'<span style="display:inline-flex;gap:6px;flex:none;">{one(m["sma"], m["sma_above"])}{one(m["ema"], m["ema_above"])}</span>')
    nt = len(top_rows)   # 선 = 제목 아래 · 기간 머리 줄 위 · 머리 줄 아래 (배열 · 크로스 줄이 있으면 그 아래에 머리 줄)
    lines.append((_sub("이동평균") + _table(mrs, line, keep=tuple(sorted({0, nt, nt + 1}))), "html"))
    tip = ("널리 쓰는 기술지표 11개와 이동평균 12개가 지금 가격의 어느 방향을 가리키는지, 우리 일봉으로 계산했다\n"
           "· 전체요약 : 기술지표와 이동평균을 한데 센 것. (상승 − 하락) ÷ 전체 가 +0.5 넘으면 강한 상승, +0.15 넘으면 상승, −0.15 ~ +0.15 중립, 그 아래 하락 · 강한 하락\n"
           "· 기술지표 : RSI · 스토캐스틱 · CCI · Williams %R · Ultimate 는 과매수면 하락, 과매도면 상승으로 센다. MACD · ROC · Highs/Lows · Bull/Bear 는 0 이나 기준선 위면 상승. ADX 는 25 아래면 중립. ATR 은 방향이 없어 개수에서 뺀다\n"
           "· 이동평균 : 5 ~ 200일 단순 · 지수 평균(한국 종목은 60 · 120일, 미국은 50 · 100일). 종가가 선 위면 상승, 아래면 하락\n"
           "· 정배열 · 역배열 : 짧은 평균선이 긴 선보다 차례로 위면 정배열, 차례로 아래면 역배열, 섞이면 혼조(한국 5 · 20 · 60 · 120일, 미국 20 · 50 · 200일)\n"
           "· 골든크로스 · 데드크로스 : 짧은 평균선이 긴 선을 위로 뚫으면 골든, 아래로 뚫으면 데드. 가장 최근 것과 며칠(거래일) 전인지(한국 20 · 60일선, 미국 50 · 200일선)\n"
           "· 이름 앞 보라 점 : 개인 투자자가 많이 보는 지표(RSI · 스토캐스틱 · MACD · 배열 · 크로스)\n"
           "· 참고 : 같은 지표라도 일봉 · 주봉 · 월봉에서 반대로 나오곤 한다. 다른 사이트와는 봉 단위 · 기준값이 달라 값이 다를 수 있다")
    return lines, tip
