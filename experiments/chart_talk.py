"""차트 읽기 — 종목 페이지 맨 위 차트를 캐릭터가 말로 풀어 주는 문장 틀. AI 없음(일봉 → tech_signals → 정해진 문장).

    talk(bars, name, market) → {"mood": "up" | "down" | "mid", "who": 캐릭터 이름, "as_of": 날짜, "net", "lines": [{"text", "pic", "cut"}, …]}
    cut = 그 말풍선 옆에 캐릭터가 서는 자리("hello" 인사 · "mid" 가운데 · "bye" 끝인사, 없으면 None).
    pic = 말풍선에 붙는 그림의 자료(그림은 화면 쪽이 그린다, 없으면 None).
        {"kind": "avg", "pos": "above" | "below" | "split_up" | "split_down" | "mixed"} · {"kind": "rsi", "value"} · {"kind": "vol", "ratio", "day": "up" | "down" | "flat"}
    글 속 표시 = `**굵게**` · `{+상승 색 글}`(앞에 ▲) · `{-하락 색 글}`(앞에 ▼). 화면 쪽이 바꾼다.

누가 말하나 = `기술지표의 방향은?` 카드의 전체 요약(tech_signals.compute 의 net)과 같은 기준.
    net ≥ 0.15 상승이 · net ≤ −0.15 하락이 · 그 사이 분석이(상승 · 하락이 팽팽한 날).
캐릭터 말투(이 기능에서만) — 사실 문장은 셋이 같고, 인사 · 가운데 한마디 · 끝인사만 다르다.
    상승이 = 신이 났지만 들뜨지 않으려는 친구 · 하락이 = 독자가 상승을 바라는 걸 알아 아쉬워하지만 있는 그대로 말하는 친구 · 분석이 = 저울을 든 심판.
비교 대상(헌법 제1조) = 평균선(종가 ↔ 그 종목의 지난 n일 평균) · 지난 1년 상대강도지수 분포 · 평소 거래량(20일 평균) · 주봉(일봉과 갈리는지).
용어 = 상승 · 하락 · 중립. 매수 · 매도 · 앞날 예측 문장은 쓰지 않는다. 줄표를 쓰지 않는다. 독자에게 보이는 말은 `차트`(주식 공부 글과 같은 말).
"""
import tech_signals as T

WHO = {"up": "상승이", "down": "하락이", "mid": "분석이"}
VOL_BIG, VOL_SMALL = 1.5, 0.7   # 평소(20일 평균)의 몇 배부터 많다 · 적다고 말하나
YEAR = 250                      # 지난 1년 = 250거래일
WORD = {"up": "{+상승}", "down": "{-하락}", "mid": "**중립**"}
HELLO = {"up": "안녕하세요, 상승이예요! 제가 나왔다는 건 오늘 차트가 기분 좋은 모양이라는 뜻이에요. {day} 종가까지의 **{name}** 차트를 읽어 드릴게요.",
         "down": "안녕하세요, 하락이예요. 제가 나왔다는 건… 네, 반가운 차트는 아니라는 뜻이에요. {day} 종가까지의 **{name}** 차트를 있는 그대로 읽어 드릴게요.",
         "mid": "안녕하세요, 분석이예요. 상승이도 하락이도 못 나온 날이라 제가 저울을 들고 나왔어요. {day} 종가까지의 **{name}** 차트를 읽어 드릴게요."}
BYE = {"up": "신이 나도 여기까지는 차트 모양만 읽은 거예요. **왜 움직였는지**는 아래 뉴스와 실적에서 같이 보세요!",
       "down": "아쉽지만 오늘 차트는 여기까지예요. 차트는 모양만 보여 줘요. **왜 움직였는지**는 아래 뉴스와 실적에서 같이 보세요.",
       "mid": "오늘 저울은 여기까지예요. 차트는 모양만 보여 줘요. **왜 움직였는지**는 아래 뉴스와 실적에서 같이 보세요."}


def _days(ns):
    return " · ".join(f"{n}일" for n in ns)


def _mood(net):
    return "up" if net >= 0.15 else "down" if net <= -0.15 else "mid"


def _say_flow(sig, mood):
    a = sig["all"]
    tot = a["up"] + a["down"] + a["neutral"]
    ups, dns = f"**{a['up']}개**가 {{+상승}} 쪽", f"**{a['down']}개**가 {{-하락}} 쪽"
    count = f"기술 지표와 평균선 {tot}개 가운데 {dns if mood == 'down' else ups}, {ups if mood == 'down' else dns}을 가리켜요."
    if mood == "mid":
        return "지금은 상승과 하락이 **팽팽해서** 어느 한쪽이라고 말하기 어려워요. " + count
    flow = "{+상승 흐름}" if mood == "up" else "{-하락 흐름}"
    return f"지금은 {flow}{'이 **뚜렷해요**' if abs(sig['net']) >= 0.5 else ' 쪽으로 기울어 있어요'}. " + count


def _say_avg(sig, market):
    ma = {r["n"]: r for r in sig["ma"]}
    ps = [n for n in T.ARRAY_PERIODS[market] if n in ma and ma[n]["sma"] is not None]
    if not ps:
        return None
    up = [n for n in ps if ma[n]["sma_above"]]
    dn = [n for n in ps if not ma[n]["sma_above"]]
    s = "평균선은 최근 며칠 종가의 평균을 이은 선이에요. "
    if not dn:
        return {"text": s + f"지금 종가는 {_days(ps)} 평균선 **위에 모두** 올라와 있어요. 짧게 봐도 길게 봐도 {{+상승}} 쪽이에요.", "pic": {"kind": "avg", "pos": "above"}}
    if not up:
        return {"text": s + f"지금 종가는 {_days(ps)} 평균선 **아래에 모두** 내려와 있어요. 짧게 봐도 길게 봐도 {{-하락}} 쪽이에요.", "pic": {"kind": "avg", "pos": "below"}}
    if up == ps[:len(up)]:
        return {"text": s + f"지금 종가는 {_days(up)} 평균선 위로는 올라왔지만 **{_days(dn)} 평균선 아래**예요. 짧게 보면 반등, 길게 보면 아직 {{-하락}} 쪽이라 **갈려요**.",
                "pic": {"kind": "avg", "pos": "split_up"}}
    if dn == ps[:len(dn)]:
        return {"text": s + f"지금 종가는 {_days(dn)} 평균선 아래로 내려왔지만 **{_days(up)} 평균선 위**예요. 짧게 보면 밀렸고, 길게 보면 아직 {{+상승}} 쪽이라 **갈려요**.",
                "pic": {"kind": "avg", "pos": "split_down"}}
    return {"text": s + f"지금 종가는 {_days(up)} 평균선 위, {_days(dn)} 평균선 아래예요. 보는 기간에 따라 방향이 **갈려요**.", "pic": {"kind": "avg", "pos": "mixed"}}


def _say_recent(c, mood):
    """가운데 한마디 — 최근 20거래일 등락에 캐릭터의 마음을 붙인다."""
    if len(c) < 21:
        return None
    r = (c[-1] / c[-21] - 1) * 100
    s = f"최근 20거래일 동안 {'{+' if r >= 0 else '{-'}{abs(r):.1f}% {'상승' if r >= 0 else '하락'}}}했어요. "
    if mood == "up":
        s += "보고 있으면 저도 신이 나요!" if r >= 0 else "그래도 흐름은 아직 상승 쪽이에요."
    elif mood == "down":
        s += "저도 아쉬워요." if r < 0 else "그래도 흐름은 아직 하락 쪽이에요."
    else:
        s += "그런데도 지표들은 팽팽하게 갈려 있어요."
    return s


def _say_rsi(sig, c):
    row = next((x for x in sig["rows"] if x["key"] == "rsi" and x["value"] is not None), None)
    if not row:
        return None
    v = row["value"]
    s = f"상승한 날과 하락한 날의 힘을 견주는 상대강도지수(RSI)는 **{v:.1f}**, "
    s += ("70을 넘어 평소 범위를 벗어난 **높은 자리(과매수)**예요." if v >= 70 else "30 아래로 평소 범위를 벗어난 **낮은 자리(과매도)**예요." if v <= 30
          else "가운데 선 50 위라 {+상승} 쪽이에요." if v >= 50 else "가운데 선 50 아래라 {-하락} 쪽이에요.")
    past = [x for x in T._rsi(c)[-YEAR:] if x is not None]
    if len(past) >= 60:
        low = sum(1 for x in past if x < v) / len(past) * 100
        if low >= 70:
            s += f" 지난 1년 가운데 **높은 쪽 {max(1, round(100 - low))}%** 안에 드는 값이에요."
        elif low <= 30:
            s += f" 지난 1년 가운데 **낮은 쪽 {max(1, round(low))}%** 안에 드는 값이에요."
    return {"text": s, "pic": {"kind": "rsi", "value": round(v, 1)}}


def _say_volume(bars, sig, mood):
    v = [b.get("volume") or 0 for b in bars]
    c = [b["close"] for b in bars]
    s, pic = "", None
    if len(v) >= 21 and sum(v[-21:-1]) and v[-1]:
        x = v[-1] / (sum(v[-21:-1]) / 20)
        day = "up" if c[-1] > c[-2] else "down" if c[-1] < c[-2] else "flat"
        did = {"up": "가격이 {+상승}한 ", "down": "가격이 {-하락}한 ", "flat": ""}[day]
        size = "평소보다 많았어요" if x >= VOL_BIG else "평소보다 적었어요" if x <= VOL_SMALL else "평소와 비슷했어요"
        s = f"{did}마지막 거래일의 거래량은 평소(20일 평균)의 **{x:.1f}배**로 {size}."
        pic = {"kind": "vol", "ratio": float(f"{x:.1f}"), "day": day}
    w = sig.get("weekly")
    if w:
        wm = _mood(w["net"])
        if wm == mood:
            s += " 주봉으로 넓혀 봐도 " + ("팽팽해요." if mood == "mid" else f"같은 {WORD[wm]} 흐름이에요.")
        else:
            s += f" 주봉으로 넓혀 보면 {WORD[wm]} 쪽이라 일봉과 **갈려요**."
    return {"text": s.strip(), "pic": pic} if s else None


def talk(bars, name, market="us"):
    """bars = [{"day", "open", "high", "low", "close", "volume"}, …] (오래된 날부터). 봉이 모자라 계산되지 않는 말풍선은 뺀다."""
    sig = T.compute(bars, market)
    if not sig or not sig.get("rows"):
        return None
    c = [b["close"] for b in bars]
    mood = _mood(sig["net"])
    day = f"{int(sig['as_of'][5:7])}월 {int(sig['as_of'][8:10])}일"
    recent = _say_recent(c, mood)
    lines = [{"text": HELLO[mood].format(day=day, name=name), "pic": None, "cut": "hello"},
             {"text": _say_flow(sig, mood), "pic": None},
             _say_avg(sig, market),
             {"text": recent, "pic": None, "cut": "mid"} if recent else None,
             _say_rsi(sig, c),
             _say_volume(bars, sig, mood),
             {"text": BYE[mood], "pic": None, "cut": "bye"}]
    return {"mood": mood, "who": WHO[mood], "as_of": sig["as_of"], "net": sig["net"], "lines": [dict({"cut": None}, **x) for x in lines if x]}
