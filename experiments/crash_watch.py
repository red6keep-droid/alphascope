"""급락장에서 버틴 종목 — 홈 `주목할 종목` 카드 · 종목 페이지 `오늘` 탭 `급락장에서 어땠나?` 카드 재료 (2026-11-04 사용자, 11-02 녹음 메모).

규칙 (판단 없음, 사실만):
- 급락일 = 지수(미국 S&P 500 = SPY, 한국 코스피 = ^KS11) 하루 수정 종가가 CRASH_PCT 넘게 내린 날. 가진 일봉(약 2년) 안에서 센다.
- 버틴 종목 = 그날 올랐거나, 지수보다 HOLD_PP 넘게 덜 내린 종목. 우리 후보(미국 64 · 한국 35) 안에서만.
- 홈 카드는 가장 최근 급락일 하루의 버틴 종목. 급락일이 아닌 날도 그 날짜를 적어 그대로 보여 준다(빈 카드 대신 "마지막 급락일 ○월 ○일").
- 종목마다 급락일 n번 중 m번 버텼는지 같이 센다 — 늘 덜 움직이는 종목(유틸리티 · 필수소비재)과 그날만 버틴 종목이 구분된다.
- 이건 신호가 아니라 기록이다. "앞으로도 버틴다" 는 말은 어디에도 쓰지 않는다(알파 검증을 거치지 않았다).
"""

import datetime

CRASH_PCT = 2.0   # 지수가 이만큼 넘게 내린 날
HOLD_PP = 2.0     # 지수보다 이만큼 넘게 덜 내리면 버틴 것
INDEX = {"us": ("SPY", "S&P 500"), "kr": ("^KS11", "코스피")}


def _rets(bars):
    """일봉 → {날: 하루 수정 종가 등락 %}. 수정 종가(adj)가 없는 날은 뺀다."""
    out = {}
    for p, b in zip(bars, bars[1:]):
        if p.get("adj") and b.get("adj"):
            out[b["day"]] = (b["adj"] / p["adj"] - 1) * 100
    return out


def compute(bars, market, syms, pct=CRASH_PCT, hold_pp=HOLD_PP):
    """bars = {종목: 일봉 목록}, syms = 우리 후보. → {"day": 최근 급락일, "index_ret", "days": [(날, 지수 %)], "stocks": {종목: {...}}, ...}. 급락일이 없으면 day None."""
    isym, iname = INDEX[market]
    idx = _rets(bars.get(isym) or [])
    crash = sorted((d, r) for d, r in idx.items() if r <= -pct)
    latest_bar = max(idx) if idx else None
    out = {"market": market, "index": iname, "index_sym": isym, "pct": pct, "hold_pp": hold_pp, "latest_bar": latest_bar, "days": crash,
           "day": crash[-1][0] if crash else None, "index_ret": crash[-1][1] if crash else None, "stocks": {},
           "recent": bool(crash) and crash[-1][0] in sorted(idx)[-2:]}   # 최근 두 거래일 안의 급락 — 종목 페이지 카드는 이때만 (뉴스 줄 48시간 규칙과 같은 뜻)
    if not crash:
        return out
    day = out["day"]
    for sym in syms:
        r = _rets(bars.get(sym) or [])
        hist = [(d, r[d], r[d] - ir) for d, ir in crash if d in r]
        held = [x for x in hist if x[1] >= 0 or x[2] >= hold_pp]
        if day not in r:
            continue
        ret, ex = r[day], r[day] - out["index_ret"]
        out["stocks"][sym] = {"ret": ret, "excess": ex, "held": ret >= 0 or ex >= hold_pp, "held_n": len(held), "held_total": len(hist)}
    return out


def for_stock(c, sym):
    """종목 하나의 카드 재료 — compute 결과 + 그 종목 값. 그날 값이 없으면 None."""
    x = (c or {}).get("stocks", {}).get(sym)
    if not x:
        return None
    return {k: c[k] for k in ("market", "index", "pct", "hold_pp", "latest_bar", "day", "index_ret", "recent")} | x | {"n_days": len(c["days"])}


def notable(c):
    """홈 카드 줄 — 최근 급락일에 버틴 종목, 지수와 차이 큰 순."""
    return sorted((sym for sym, x in (c or {}).get("stocks", {}).items() if x["held"]), key=lambda s: -c["stocks"][s]["excess"])


def _sgn(v, d=1):
    return f"{v:+.{d}f}".replace("-", "−")


def _josa(w, a, b):
    """받침 있으면 a(은 · 이), 없으면 b(는 · 가). 영문 · 숫자로 끝나는 이름(S&P 500 · P&G)은 b."""
    ch = w[-1]
    if ch.isdigit():   # 숫자는 읽는 소리로 — 0 · 1 · 3 · 6 · 7 · 8 은 받침(영 · 일 · 삼 · 육 · 칠 · 팔), 2 · 4 · 5 · 9 는 없음 (S&P 500 → 500이)
        return a if ch in "013678" else b
    return (a if (ord(ch) - 0xAC00) % 28 else b) if "가" <= ch <= "힣" else b


def _md(day):
    d = datetime.date.fromisoformat(day)
    return f"{d.month}월 {d.day}일"


def card_lines(x, name):
    """종목 페이지 카드 줄 — 첫 문장 + 사실 줄. 뉴스 · 업종 · 실적 줄은 부르는 쪽(미국 · 한국 자료가 다름)이 덧붙인다."""
    up = x["ret"] >= 0
    first = (f"{_md(x['day'])} {x['index']}{_josa(x['index'], '이', '가')} {_sgn(x['index_ret'])}% 내린 날 {name}{_josa(name, '은', '는')} {_sgn(x['ret'])}% "
             + ("올랐다" if up else "내렸다") + f". 지수보다 {_sgn(x['excess'])}%p " + ("앞섰다." if up else "덜 내렸다."))
    rows = [("row", "그날 등락", f"{_sgn(x['ret'])}%", f"{x['index']} {_sgn(x['index_ret'])}%"),
            ("row", "지수와 차이", f"{_sgn(x['excess'])}%p", "이 종목 등락 − 지수 등락"),
            ("row", "최근 2년 급락일", f"{x['held_total']}번 중 {x['held_n']}번", f"{x['index']}{_josa(x['index'], '이', '가')} {x['pct']:.0f}% 넘게 내린 날 가운데 올랐거나 {x['hold_pp']:.0f}%p 넘게 덜 내린 날")]
    return first, rows


def tip(x):
    return (f"{x['index']}{_josa(x['index'], '이', '가')} 하루 {x['pct']:.0f}% 넘게 내린 날, 이 종목은 어땠나. 홈 `주목할 종목` 카드와 같은 기준\n"
            f"· 버텼다 : 그날 올랐거나 지수보다 {x['hold_pp']:.0f}%p 넘게 덜 내린 것. 등락은 배당을 넣은 수정 종가\n"
            "· 왜 버텼는지는 단정하지 않는다 — 그날 이 종목 주변에 있었던 일(뉴스 방향 · 업종 자금 · 실적 일정)을 나란히 둘 뿐\n"
            "· 최근 2년 급락일 n번 중 m번 : 늘 덜 움직이는 종목(유틸리티 · 필수소비재)인지, 그날만 버틴 것인지 가르는 수\n"
            "· 앞으로도 버틴다는 뜻이 아니다. 이 줄은 기록이지 신호가 아니다")
