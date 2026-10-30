"""기술 지표는 어느 쪽을 가리키나 — 인베스팅닷컴 '기술적 분석' 화면의 지표 12 · 이동평균 6×2 · 피벗 5가지를 우리 일봉으로 계산 (2026-10-30 사용자). AI 없음.

용어 = 상승 · 하락 · 중립 하나로 (2026-10-30 사용자 P99: "오름 쪽 · 내림 쪽은 돌려 말하기 — 상승 · 하락, 화살표, 강한 상승 · 강한 하락").
  블로그는 매수 · 매도라고 쓰지 않는다 — 지표가 가리키는 가격 방향을 그대로 적고 판단은 독자가 한다 (법적 경계 선 4).
  오실레이터는 과매수 = 하락 · 과매도 = 상승으로 세고 줄에 (과매수) · (과매도)를 작게 붙인다. 이동평균은 종가가 선 위 ▲ · 아래 ▼.
  요약 = 강한 상승 · 상승 · 중립 · 하락 · 강한 하락, 색 = 상승 빨강 · 하락 파랑의 연한 상태 카드 톤(theme). 임계값은 널리 쓰는 기본값(RSI 70/30, 스토캐스틱 80/20, CCI ±100, Williams −20/−80, ADX 25).
인베스팅닷컴과 값이 다를 수 있다 — 그 표는 시간봉 기준으로 보이고(10-30 점검: 5일 이동평균이 최근 5일 종가 평균과 안 맞음), 우리는 일봉 · 주봉 · 월봉.

    compute(bars) → {"as_of", "close", "rows": [...], "counts", "net", "word", "ma": [...], "ma_counts", "pivot": {...}, "weekly": counts, "monthly": counts}
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


def label_html(label, up_color, down_color, muted, esc):
    """지표 줄 라벨 — 화살표 + 상승 · 하락(굵게, 증감 색), 오실레이터 까닭은 작은 회색 (과매수) · (과매도)."""
    if label in (OVER, UNDER):
        main, why = (DNW, OVER) if label == OVER else (UPW, UNDER)
    elif label == WEAK:
        main, why = MID, WEAK
    else:
        main, why = label, ""
    arrow = "▲ " if main == UPW else "▼ " if main == DNW else ""
    col = up_color if main == UPW else down_color if main == DNW else muted
    out = f'<span style="color:{col};font-weight:700;white-space:nowrap;">{arrow}{esc(main)}</span>'
    if why:
        out += f' <span style="font-size:14px;font-weight:400;color:{muted};white-space:nowrap;">({esc(why)})</span>'
    return out


def moving_averages(bars):
    c = [b["close"] for b in bars]
    out = []
    for n in (5, 10, 20, 50, 100, 200):
        s = _sma(c, n)
        e = _ema(c, n)[-1] if len(c) >= n else None
        out.append({"n": n, "sma": s, "ema": e, "sma_above": None if s is None else c[-1] > s, "ema_above": None if e is None else c[-1] > e})
    return out


def pivots(prev, today_open=None):
    """전날 고가 · 저가 · 종가로 오늘의 피벗 — 클래식 · 피보나치 · 카마릴라 · 우디 · 디마크 (인베스팅닷컴과 같은 공식)."""
    h, l, c = prev["high"], prev["low"], prev["close"]
    o = prev.get("open") or c
    p = (h + l + c) / 3
    rng = h - l
    classic = {"S3": l - 2 * (h - p), "S2": p - rng, "S1": 2 * p - h, "P": p, "R1": 2 * p - l, "R2": p + rng, "R3": h + 2 * (p - l)}
    fib = {"S3": p - rng, "S2": p - 0.618 * rng, "S1": p - 0.382 * rng, "P": p, "R1": p + 0.382 * rng, "R2": p + 0.618 * rng, "R3": p + rng}
    cam = {"S3": c - rng * 1.1 / 4, "S2": c - rng * 1.1 / 6, "S1": c - rng * 1.1 / 12, "P": p, "R1": c + rng * 1.1 / 12, "R2": c + rng * 1.1 / 6, "R3": c + rng * 1.1 / 4}
    pw = (h + l + 2 * (today_open or c)) / 4
    woodie = {"S3": None, "S2": pw - rng, "S1": 2 * pw - h, "P": pw, "R1": 2 * pw - l, "R2": pw + rng, "R3": None}
    x = h + 2 * l + c if c < o else 2 * h + l + c if c > o else h + l + 2 * c
    demark = {"S3": None, "S2": None, "S1": x / 2 - h, "P": x / 4, "R1": x / 2 - l, "R2": None, "R3": None}
    return {"클래식": classic, "피보나치": fib, "카마릴라": cam, "우디": woodie, "디마크": demark}


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


def compute(bars):
    bars = [b for b in bars if b.get("close")]
    if len(bars) < 30:
        return None
    rows = indicators(bars)
    cnt = counts(rows)
    ma = moving_averages(bars)
    mac = {"above": sum(1 for m in ma for k in ("sma_above", "ema_above") if m[k] is True),
           "below": sum(1 for m in ma for k in ("sma_above", "ema_above") if m[k] is False)}
    out = {"as_of": bars[-1]["day"], "close": bars[-1]["close"], "rows": rows, "counts": cnt, "net": cnt["net"], "word": word(cnt["net"]),
           "ma": ma, "ma_counts": mac, "pivot": pivots(bars[-1]) if bars[-1].get("high") is not None else None}
    for kind, key in (("W", "weekly"), ("M", "monthly")):
        rb = resample(bars, kind)
        out[key] = counts(indicators(rb)) if len(rb) >= 30 else None
    return out


# ---------------------------------------------------------------- 그리기 (nvda-report render_html._state_card 의 lines)

def gauge_svg(net, up_color=GAUGE_UP, down_color=GAUGE_DN, gray="#CBD5E1", width=200):
    """반원 게이지 — 왼쪽(연파랑) 하락, 가운데 회색 중립, 오른쪽(연빨강) 상승. 바늘 = net (−1 … +1). 색은 파스텔 고정 (P99)."""
    cx, cy, r = width / 2, width / 2 - 10, width / 2 - 16

    def pt(a):   # a: 0(왼쪽) … 180(오른쪽) 도
        rad = math.radians(180 - a)
        return cx + r * math.cos(rad), cy - r * math.sin(rad)

    def arc(a0, a1, color, w=10):
        x0, y0 = pt(a0)
        x1, y1 = pt(a1)
        return f'<path d="M{x0:.1f},{y0:.1f} A{r},{r} 0 0 1 {x1:.1f},{y1:.1f}" stroke="{color}" stroke-width="{w}" fill="none" stroke-linecap="butt"/>'
    arcs = arc(2, 60, down_color) + arc(60, 120, gray) + arc(120, 178, up_color)
    a = 90 + max(-1.0, min(1.0, net)) * 80
    x, y = pt(a)
    needle = f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="#111" stroke-width="2"/><circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" fill="#111"/>'
    lab = (f'<text x="{pt(8)[0]:.0f}" y="{cy + 18:.0f}" font-size="12" fill="#6B7280" text-anchor="middle">하락</text>'
           f'<text x="{cx:.0f}" y="{cy - r - 14:.0f}" font-size="12" fill="#6B7280" text-anchor="middle">중립</text>'
           f'<text x="{pt(172)[0]:.0f}" y="{cy + 18:.0f}" font-size="12" fill="#6B7280" text-anchor="middle">상승</text>')
    return (f'<svg viewBox="0 0 {width} {cy + 26:.0f}" width="{width}" height="{cy + 26:.0f}" aria-hidden="true" style="display:block;margin:4px auto 0;">'
            f'{arcs}{needle}{lab}</svg>')


def card(sig, name, up_color, down_color, muted="#6B7280"):
    """(lines, tip) — _state_card 줄. 사실만: 개수 · 게이지 · 지표 줄(값 | 라벨) · 이동평균 줄 · 주봉 · 월봉 개수 · 피벗(접기 대신 줄)."""
    import html as _h
    cnt = sig["counts"]
    first = (f"{sig['as_of'][5:7].lstrip('0')}월 {sig['as_of'][8:10].lstrip('0')}일 종가 기준 지표 11개 가운데 상승 {cnt['up']}개, 중립 {cnt['neutral']}개, 하락 {cnt['down']}개다. "
             f"이동평균 12개(단순 · 지수 각 6개) 가운데 종가가 선 위(상승)인 것 {sig['ma_counts']['above']}개, 아래(하락) {sig['ma_counts']['below']}개다.")
    for key, lab in (("weekly", "주봉"), ("monthly", "월봉")):
        w = sig.get(key)
        if w:
            first += f" {lab}으로는 상승 {w['up']}개, 중립 {w['neutral']}개, 하락 {w['down']}개다."   # 가운뎃점이면 증감 색 덩어리가 문장을 건너 칠해졌다 (10-30 목업)
    def lab_html(label, d):
        return label_html(label, up_color, down_color, muted, _h.escape)
    lines = [(first, "plain"), (gauge_svg(sig["net"]), "html")]
    for r in sig["rows"]:
        lines.append(("row", r["name"], f'<span style="font-weight:700;color:#111;">{_h.escape(r["text"])}</span>&nbsp;&nbsp;{lab_html(r["label"], r["dir"])}', r["hint"], True))
    for m in sig["ma"]:
        def one(v, above):
            if v is None:
                return "—"
            arrow = f'<span style="color:{up_color if above else down_color};font-weight:700;">{"▲" if above else "▼"}</span>'   # 두 값이 한 줄이라 화살표만 (폭, P99)
            return f'<span style="font-weight:700;color:#111;">{v:,.0f}</span> {arrow}'
        lines.append(("row", f"이동평균 {m['n']}일", f'{one(m["sma"], m["sma_above"])}&nbsp;·&nbsp;{one(m["ema"], m["ema_above"])}', "", True))   # 뜻은 툴팁 한 줄 — 여섯 줄 같은 문장 (10-30)
    pv = sig.get("pivot")
    if pv:
        for nm, d in pv.items():
            # 한 줄에 일곱 숫자면 폰 폭을 넘어 페이지 전체가 옆으로 밀렸다 (10-30 목업: 화면 726px, 카드 답 글자 잘림) — P 한 줄 + S·R 짝 세 줄
            ln = [f"P {d['P']:,.0f}"] if d.get("P") is not None else []
            for i in ("1", "2", "3"):
                pair = [f"{k} {d[k]:,.0f}" for k in ("S" + i, "R" + i) if d.get(k) is not None]
                if pair:
                    ln.append(" · ".join(pair))
            lines.append(("row", f"피벗 {nm}", "\n".join(ln), ""))   # 뜻 줄은 툴팁으로 — 다섯 줄 같은 문장 · 값이 여러 줄이면 뜻 칸이 줄바꿈 없이 폭을 넘었다 (10-30)
    tip = ("널리 쓰는 기술 지표 11개와 이동평균 12개가 지금 가격의 어느 방향을 가리키는지, 우리 일봉으로 계산했다\n"
           "· 상승 · 하락 · 중립 : 지표마다 흔히 쓰는 기준으로 나눴다. 과매수는 하락, 과매도는 상승으로 센다\n"
           "· 강한 상승 · 강한 하락 : (상승 개수 − 하락 개수) ÷ 11 이 ±0.5 를 넘을 때. ±0.15 안은 중립. ATR 은 방향이 없어 개수에서 뺀다\n"
           "· 이동평균 : 단순 · 지수 값 옆 ▲ 는 종가가 선 위(상승), ▼ 는 아래(하락)\n"
           "· 피벗 : 전날 고가 · 저가 · 종가로 계산한 오늘의 기준선. P 가 가운데, S 는 아래 · R 은 위\n"
           "· 참고 : 같은 지표라도 일봉 · 주봉 · 월봉에서 반대로 나오곤 한다. 다른 사이트와는 봉 단위 · 기준값이 달라 값이 다를 수 있다")
    return lines, tip
