"""차트 읽기 — 종목 페이지 맨 위 차트를 캐릭터가 말로 풀어 주는 문장 틀. AI 없음(일봉 → tech_signals → 정해진 문장).

    block(bars, name, market) → 차트 카드 바로 아래에 넣는 HTML(버튼 + 닫힌 채팅). 계산이 안 되면 "" — 페이지 만들기를 막지 않는다.
    여닫기 = candle_chart.js 끝의 클릭 위임(data-ct-btn) — 853종목 페이지처럼 조각을 끼워 넣어도 돈다(끼운 <script> 는 안 돈다).
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
import html
import re

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


# ---------------------------------------------------------------- 화면 (목업 chart-talk/mock_chart_talk.py 와 실제 종목 페이지가 같이 쓴다)
IMG_BASE = "https://img.newfact.app/chart/"   # 캐릭터 컷 = chart-talk/chars → img_store.py 로 Pages newfact-img 에
FACE = {"up": ("up_hello", "up_mid", "up_bye"), "down": ("down_hello", "down_mid", "down_bye"),
        "mid": ("mid_hello", "mid_mid", "mid_bye")}   # 인사 · 가운데 · 끝인사 컷
TONE = {"up": ("#FFF7EE", "#FEE6CA"), "down": ("#EFF6FF", "#D6E8FE"), "mid": ("#F8FAFC", "#E2E8F0")}   # design_kit.CARD_DIR 과 같은 색
PX = 96   # 캐릭터 크기
PX_CUT = {"up_hello": 86, "up_bye": 86}   # 컷마다 다르게 (상승이 인사 · 끝인사 = 10% 작게)
CSS = """<style>
.ct-btn{display:flex;align-items:center;justify-content:center;gap:6px;width:calc(100% + 10px);height:40px;box-sizing:border-box;margin:2px -5px 0;padding:0;
  background:#fff;border:1px solid #E2E8F0;border-radius:8px;font:inherit;font-size:15px;line-height:22px;font-weight:700;color:#111;cursor:pointer;}
.ct-btn:active{background:#F3F4F6;}
.ct-btn [data-ct-arrow]{transition:transform .2s;}
.ct-btn[aria-expanded=true] [data-ct-arrow]{transform:rotate(180deg);}
.ct-box{margin:2px -5px 0;padding:14px 12px;border-radius:8px;}
.ct-row{margin:8px 0 0;opacity:0;transform:translateY(6px);transition:opacity .3s,transform .3s;}
.ct-row.on{opacity:1;transform:none;}
.ct-talk{display:flex;align-items:flex-end;gap:12px;}
.ct-talk.ct-left{flex-direction:row-reverse;}
.ct-talk.ct-left .ct-say::after{right:auto;left:-6px;border-top:0;border-right:0;border-bottom:1px solid var(--bd);border-left:1px solid var(--bd);}
.ct-say b{font-weight:700;}
.ct-up{color:#B91C1C;font-weight:700;white-space:nowrap;}
.ct-dn{color:#1D4ED8;font-weight:700;white-space:nowrap;}
.ct-up i,.ct-dn i{font-style:normal;font-size:12px;vertical-align:1px;margin-right:2px;}
.ct-talk img{display:block;flex:0 0 auto;}
.ct-talk .ct-say{position:relative;flex:1 1 auto;min-width:0;}
.ct-talk .ct-say::after{content:"";position:absolute;right:-6px;bottom:var(--tail);width:10px;height:10px;box-sizing:border-box;background:#fff;
  border-top:1px solid var(--bd);border-right:1px solid var(--bd);transform:rotate(45deg);}
.ct-say{box-sizing:border-box;padding:10px 12px;border-radius:14px;background:#fff;border:1px solid var(--bd);font-size:15px;line-height:23px;color:#111;word-break:keep-all;}
.ct-pic{display:block;width:100%;max-width:280px;height:auto;margin:2px auto 8px;}
</style>"""
R_, B_ = "#DC2626", "#2563EB"   # 상승 빨강 · 하락 파랑 (평균선 그림의 지금 종가 선과 같은 색)


def candles(spec):
    """봉 아이콘 — spec = [(색, 몸통 위, 몸통 아래, 꼬리 위, 꼬리 아래), …] 왼쪽부터. 면으로 채운 몸통 + 얇은 꼬리."""
    w = 4 if len(spec) == 2 else 3
    xs = [3.5, 10.5] if len(spec) == 2 else [2, 6.5, 11]
    out = ""
    for (col, top, bot, wt, wb), x in zip(spec, xs):
        cx = x + w / 2
        out += (f'<path d="M{cx} {wt}v{top - wt}M{cx} {bot}v{wb - bot}" stroke="{col}" stroke-width="1.5" stroke-linecap="round"/>'
                f'<rect x="{x}" y="{top}" width="{w}" height="{bot - top}" rx="0.75" fill="{col}"/>')
    return out


ICON = ('<svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">'
        + candles([(R_, 4, 10, 2, 12.5), (B_, 6, 12, 3.5, 14.5)]) + '</svg>')   # 봉 둘 · 빨강 → 파랑 · 면으로 채움 16px (2026-11-27 A안 확정)
ARROW = '<svg data-ct-arrow width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#111" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 5l4 4 4-4"/></svg>'
UP, DN, AVG, AVG2, INK, MUTE = "#ED8E87", "#82B1F0", "#F8CE8C", "#CFC4FA", "#111111", "#64748B"   # 평균선 둘은 연하게(종가 선과 대비)
LINE = {"up": "#DC2626", "down": "#2563EB", "mid": "#475569"}   # 지금 종가 선 · 지금 값 점 = 그날 흐름 색
TXT = 'font-family="inherit" font-size="12" fill="' + MUTE + '"'


def _line(ys, color, w=1):
    step = 200 // (len(ys) - 1)
    return f'<polyline points="{" ".join(f"{16 + i * step},{y}" for i, y in enumerate(ys))}" fill="none" stroke="{color}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>'


def pic_avg(pos, mood):
    """예시 그림 — 종가 선(검정)과 평균선. 모양만 보여 주는 그림이라 실제 값이 아니다(그림 아래 `예시 그림`)."""
    flip = pos in ("above", "split_down")   # 아래 꼴을 위아래로 뒤집으면 위 꼴
    two = pos in ("split_up", "split_down", "mixed")
    price = [30, 22, 34, 28, 44, 40, 58, 52, 70, 64, 74] if not two else [20, 30, 26, 42, 50, 62, 74, 80, 72, 64, 58]
    long_ = [26, 28, 30, 32, 35, 38, 41, 44, 47, 50, 53] if not two else [22, 24, 26, 28, 31, 34, 37, 40, 43, 45, 47]
    short = [24, 26, 29, 33, 40, 48, 57, 66, 71, 71, 68]
    f = (lambda ys: [96 - y for y in ys]) if flip else (lambda ys: ys)
    price, long_, short = f(price), f(long_), f(short)
    ink = LINE[mood]
    out = _line(long_, AVG) + (_line(short, AVG2) if two else "") + _line(price, ink, 1.5)
    out += f'<circle cx="216" cy="{price[-1]}" r="4" fill="{ink}"/><text x="226" y="{price[-1] + 4}" {TXT} fill="{ink}" font-weight="700">지금 종가</text>'
    out += f'<text x="226" y="{long_[-1] + (4 if not two else (-4 if not flip else 12))}" {TXT}>{"긴 평균선" if two else "평균선"}</text>'
    if two:
        out += f'<text x="226" y="{short[-1] + (16 if not flip else -8)}" {TXT}>짧은 평균선</text>'
    return f'<svg class="ct-pic" viewBox="0 0 300 96" role="img" aria-label="종가와 평균선 예시 그림">{out}</svg>'


def pic_rsi(v, mood):
    x = 20 + round(v / 100 * 240)
    out = (f'<rect x="20" y="34" width="72" height="12" rx="6" fill="{DN}" opacity="0.5"/><rect x="92" y="34" width="96" height="12" fill="#E2E8F0"/>'
           f'<rect x="188" y="34" width="72" height="12" rx="6" fill="{UP}" opacity="0.5"/><rect x="86" y="34" width="12" height="12" fill="#E2E8F0"/><rect x="182" y="34" width="12" height="12" fill="#E2E8F0"/>'
           f'<rect x="139" y="30" width="2" height="20" fill="#94A3B8"/>'
           f'<circle cx="{x}" cy="40" r="7" fill="{LINE[mood]}" stroke="#fff" stroke-width="2"/><text x="{x}" y="22" text-anchor="middle" {TXT} fill="{LINE[mood]}" font-weight="700">{v:.1f}</text>')
    for val, lab in ((30, "30"), (50, "50"), (70, "70")):
        out += f'<text x="{20 + round(val / 100 * 240)}" y="66" text-anchor="middle" {TXT}>{lab}</text>'
    out += f'<text x="20" y="84" {TXT}>낮은 자리 (과매도)</text><text x="260" y="84" text-anchor="end" {TXT}>높은 자리 (과매수)</text>'
    return f'<svg class="ct-pic" viewBox="0 0 280 90" role="img" aria-label="상대강도지수 {v:.1f}">{out}</svg>'


def pic_vol(ratio, day):
    base = 32
    h = max(4, min(72, round(base * ratio)))
    col = {"up": UP, "down": DN, "flat": "#CBD5E1"}[day]
    out = (f'<rect x="70" y="{84 - base}" width="44" height="{base}" rx="3" fill="#CBD5E1"/><text x="92" y="100" text-anchor="middle" {TXT}>평소 (20일 평균)</text>'
           f'<rect x="170" y="{84 - h}" width="44" height="{h}" rx="3" fill="{col}"/><text x="192" y="100" text-anchor="middle" {TXT}>마지막 거래일</text>'
           f'<text x="192" y="{84 - h - 6}" text-anchor="middle" {TXT} fill="{INK}" font-weight="700">{ratio:.1f}배</text>'
           f'<rect x="50" y="84" width="184" height="1" fill="#CBD5E1"/>')
    top = 84 - max(h, base) - 24
    return f'<svg class="ct-pic" viewBox="0 {top} 280 {104 - top}" role="img" aria-label="거래량 평소의 {ratio:.1f}배">{out}</svg>'


def picture(p, mood):
    if not p:
        return ""
    return pic_avg(p["pos"], mood) if p["kind"] == "avg" else pic_rsi(p["value"], mood) if p["kind"] == "rsi" else pic_vol(p["ratio"], p["day"])


def rich(text):
    """문장 틀의 표시 → 화면. `**굵게**` · `{+상승 색}`(▲) · `{-하락 색}`(▼)."""
    t = html.escape(text)
    t = re.sub(r"\{\+(.+?)\}", r'<span class="ct-up"><i>▲</i>\1</span>', t)
    t = re.sub(r"\{-(.+?)\}", r'<span class="ct-dn"><i>▼</i>\1</span>', t)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def said(line, mood, who=None, left=False, img=None):
    """말풍선 한 줄 — 그림이 위, 글이 아래. who(캐릭터 컷)가 있으면 캐릭터가 옆에 서고 말풍선 꼬리가 캐릭터를 가리킨다(가운데 컷만 왼쪽).
    캐릭터 그림은 loading=lazy — 닫힌 채팅 안이라 버튼을 누른 사람만 받는다."""
    px = PX_CUT.get(who, PX)
    say = f'<div class="ct-say">{picture(line["pic"], mood)}{rich(line["text"])}</div>'
    if not who:
        return f'<div class="ct-row">{say}</div>'
    src = img(who) if img else IMG_BASE + who + ".webp"
    return (f'<div class="ct-row ct-talk{" ct-left" if left else ""}" style="--tail:{px // 3}px;">{say}'
            f'<img src="{src}" alt="" loading="lazy" width="{px}" height="{px}" style="width:{px}px;height:{px}px;"></div>')


def render(t, img=None, rows_hook=None):
    """talk() 결과 → HTML. img = 컷 이름 → 그림 주소(목업 = data URI). rows_hook(line, cut) → 그 줄 앞에 넣을 HTML(목업 시안 이름표)."""
    (bg, bd), cuts = TONE[t["mood"]], dict(zip(("hello", "mid", "bye"), FACE[t["mood"]]))
    rows = ""
    for x in t["lines"]:
        who = cuts.get(x["cut"])
        rows += (rows_hook(x, who) if rows_hook else "") + said(x, t["mood"], who, x["cut"] == "mid", img)
    return ("<!--ct-->" + CSS + f'<button class="ct-btn" type="button" data-ct-btn aria-expanded="false">{ICON}<span data-ct-word>차트 읽기</span>{ARROW}</button>'
            f'<div class="ct-box" data-ct-box hidden style="--bd:{bd};background:{bg};border:1px solid {bd};">{rows}</div><!--/ct-->')   # 앞뒤 표시 = 목업이 이 덩이를 찾아 바꾼다


def block(bars, name, market="us"):
    """종목 페이지 차트 카드 바로 아래 — 버튼 + 닫힌 채팅. 봉이 모자라거나 계산이 깨지면 "" (페이지는 그대로 만든다)."""
    try:
        t = talk(bars or [], name, market) if len(bars or []) >= 60 else None
        return render(t) if t else ""
    except Exception as e:   # noqa: BLE001 — 차트 읽기 하나 때문에 종목 페이지 발행을 막지 않는다
        print(f"[차트 읽기] {name} 건너뜀: {e!r}")
        return ""
