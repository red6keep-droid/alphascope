"""재설계 구획 (doc/데일리-리포트-기획.md 6절, 2026-10-18) — 독자 질문 D1 ~ D6 · K1 ~ K3 에 답하는 질문 카드.

숫자는 analysis.json(파이썬)에서, 문장은 여기 고정 틀(합니다체). Gemini 문구는 쓰지 않는다.
근거 등급(기획 5절 B1): 튼튼한 기록은 "~했습니다", 시기에 따라 다른 기록은 시기를 붙이고, 표본이 적은 것은 보여 주지 않는다.
"""

import datetime

import cards as C
import design_kit as dk

INDEX_NAME = {"^GSPC": "S&P 500", "^IXIC": "나스닥", "^DJI": "다우", "^RUT": "러셀 2000", "^SOX": "미국 반도체 지수"}
INDEX_SHORT = {"^GSPC": "S&P 500", "^IXIC": "나스닥", "^DJI": "다우", "^RUT": "러셀"}
# 대형주 10개 = 홈 시총 TOP 10 (fetch_stocks.TICKERS · stock-radar/universe.py, 2026-10-18 JPM → LLY)
MEGA_KO = {"NVDA": "엔비디아", "AAPL": "애플", "MSFT": "마이크로소프트", "GOOGL": "알파벳(구글)", "AMZN": "아마존", "META": "메타",
           "AVGO": "브로드컴", "TSLA": "테슬라", "BRK-B": "버크셔 해서웨이", "LLY": "일라이 릴리"}
MEGA_SHORT = {"NVDA": "엔비디아", "AAPL": "애플", "MSFT": "MS", "GOOGL": "구글", "AMZN": "아마존", "META": "메타",
              "AVGO": "브로드컴", "TSLA": "테슬라", "BRK-B": "버크셔", "LLY": "릴리"}
MACRO_KO = {"FOMC": "금리 결정 (FOMC)", "CPI": "소비자물가 (CPI)", "NFP": "고용 보고서", "PCE": "물가 (PCE)", "GDP": "성장률 (GDP)", "OPEX": "월간 옵션 만기"}
MACRO_SHORT = {"FOMC": "FOMC", "CPI": "CPI", "NFP": "고용", "PCE": "PCE", "GDP": "GDP", "OPEX": "옵션 만기"}
# 표본이 적어 화면에서 빼는 짝 (기획 4-1: LG에너지솔루션은 2022년 상장, 크게 움직인 밤 17 · 23번 — 판단 유보)
PAIR_HIDE = {"373220.KS"}
MIN_BUCKET = 30
SOON_DAYS = 7


def _s(v, d=2, unit="%"):
    return f"{v:+.{d}f}{unit}".replace("-", "−")


def _md(day):
    d = datetime.date.fromisoformat(day)
    return f"{d.month}월 {d.day}일"


_DIGIT_JONG = {"0": True, "1": True, "2": False, "3": True, "4": False, "5": False, "6": True, "7": True, "8": True, "9": False}


def eun(word):
    """은 / 는 — 마지막 글자 받침으로 (숫자는 읽는 소리로: S&P 500 → 은, 나스닥 → 은, 다우 → 는)."""
    ch = str(word).strip()[-1:]
    if "가" <= ch <= "힣":
        return word + ("은" if (ord(ch) - 0xAC00) % 28 else "는")
    return word + ("은" if _DIGIT_JONG.get(ch, False) else "는")


def _times(z):
    return f"{abs(z):.1f}배"


# ── 오늘 탭 ─────────────────────────────────────────────────────────────

def normal_card(a, opened=True):
    """D3 오늘 움직임은 평소와 달랐나 — 지수별 평소 범위 (엔비디아 W1 과 같은 자)."""
    nr = a.get("normal") or {}
    keys = [k for k in ("^GSPC", "^IXIC", "^DJI", "^RUT") if k in nr]
    if not keys:
        return ""
    outs = [k for k in keys if nr[k]["outside"]]
    state = "모두 평소 안" if not outs else " · ".join(INDEX_SHORT[k] for k in outs) + " 평소 밖"
    sp = nr.get("^GSPC")
    lines = []
    if not outs and sp:
        lines.append((f"S&P 500은 {_s(sp['ret_pct'])}로 평소 하루 움직임(±{sp['sigma_pct']:.2f}%) 안이었습니다. 다른 지수도 모두 평소 범위 안이었습니다.", "plain"))
    for k in outs:
        n = nr[k]
        lines.append((f"{INDEX_NAME[k]} {_s(n['ret_pct'])}는 평소 하루 움직임(±{n['sigma_pct']:.2f}%)의 {_times(n['z'])}로, 지난 1년에 {n['n_year']}번 있던 크기였습니다.", "plain"))
    if outs:
        lines.append(("S&P 500 종목 기준, 평소 국면에 평소 범위 밖으로 움직인 다음 날 사고판 결과는 아무 날과 구분되지 않았습니다.", "plain"))
    groups = [(INDEX_SHORT[k], [nr[k]["ret_pct"], nr[k]["sigma_pct"] if nr[k]["ret_pct"] >= 0 else -nr[k]["sigma_pct"]]) for k in keys]
    lines.append((C.chart_card("오늘 움직임과 평소 하루 크기 (%)", groups, [C.sign_bg, C.gray], [C.sign_fg, C.note_fg],
                               [("오늘", C.sign_bg(sp["ret_pct"] if sp else 1)), ("평소 하루 크기", C.GRAY_BAR)]), "html"))
    for k in keys:
        n = nr[k]
        lines.append(("row", INDEX_NAME[k], _s(n["ret_pct"]), f"평소 ±{n['sigma_pct']:.2f}% · {_times(n['z'])}"))
    tip = ("하루 움직임이 그 지수의 평소 크기 안이었는지. 평소 크기는 최근 움직임에 무게를 더 둔 표준편차이고, 2배를 넘으면 평소 밖으로 봅니다\n"
           + (f"· 오늘 S&P 500 {_s(sp['ret_pct'])} : 평소의 {_times(sp['z'])}, 지난 1년 중 이만큼 이상 움직인 날 {sp['n_year']}번\n" if sp else "")
           + "· 기록상 : 평소 밖으로 움직인 다음 날 사고판 결과는 평소 국면에서 아무 날과 다르지 않았습니다 (S&P 500 종목, 약 30년)")
    return C.question_card("오늘 움직임은 평소와 달랐나?", state, "neutral", "#111", lines, tip=tip, opened=opened)


def shock_card(a):
    """D6 충격 표시 — 충격 국면일 때만 (기획 5절 B3)."""
    sh = a.get("shock") or {}
    if not sh.get("active"):
        return ""
    lines = [("VIX가 35를 넘은 뒤 아직 25 아래로 내려오지 않았습니다. 이런 충격 국면에는 평소 범위의 자가 잘 맞지 않습니다.", "plain"),
             ("기록상 충격 국면에 크게 내린 날 판 경우는 그냥 들고 있던 경우보다 특히 나빴습니다 (S&P 500 종목, 서로 다른 충격 9번이라 대략으로 봅니다).", "plain"),
             ("row", "VIX", f"{sh['vix']:.2f}", "35 이상에서 시작 · 25 아래에서 끝")]
    tip = ("시장 전체가 크게 흔들리는 기간인지. VIX가 35 이상이 되면 시작, 25 아래로 내려오면 끝으로 봅니다\n"
           f"· 오늘 VIX {sh['vix']:.2f} : 충격 국면 {sh.get('days_in') or 1}거래일째\n"
           "· 기록상 : 이 기간의 급락 날 매도는 들고 있기보다 특히 나빴습니다")
    return C.question_card("시장 충격 국면인가?", f"{sh.get('days_in') or 1}거래일째", "uncertain", "#92400E", lines, tip=tip, opened=True)


def market_now_card(a):
    """D6 지금 시장은 — 옛 점수 · 신호등 대신 사실만 (기획 5절 B5). 우리 검증은 툴팁."""
    se = a.get("series") or {}
    spy = se.get("SPY") or {}
    pos = (a.get("position") or {}).get("sp500") or {}
    vix = a.get("vix") or {}
    rates = a.get("rates") or {}
    rc = a.get("regime_check") or {}
    a20, a50 = spy.get("above_ma20"), spy.get("above_ma50")
    if a20 is None or a50 is None:
        return ""
    state = "평균선 위" if a20 and a50 else "평균선 아래" if not a20 and not a50 else ("20일선 아래" if not a20 else "50일선 아래")
    lines = [("점수나 신호등으로 묶지 않고 사실만 보여 드립니다. 이런 사실을 묶은 시장 상태 점수는 기록상 앞날을 가르지 못했습니다.", "plain"),
             ("row", "S&P 500 추세", f"20일선 {'위' if a20 else '아래'} · 50일선 {'위' if a50 else '아래'}", "최근 20 · 50거래일 평균 가격과 비교")]
    if pos.get("from_high_pct") is not None:
        lines.append(("row", "20일 고점 대비", _s(pos["from_high_pct"]), "최근 20거래일 가장 높던 종가와 비교"))
    if vix.get("now") is not None:
        lines.append(("row", "VIX", f"{vix['now']:.2f}", f"5거래일 전 {vix['prev_5d']:.2f}" if vix.get("prev_5d") is not None else "시장이 예상하는 흔들림"))
    if rates.get("us10y_change_5d_bp") is not None:
        lines.append(("row", "10년물 금리 (5일)", f"{int(rates['us10y_change_5d_bp']):+d}bp".replace("-", "−"), f"지금 {rates['us10y']:.2f}%" if rates.get("us10y") else ""))
    up = rc.get("up20") or {}
    tip = ("시장 흐름을 이루는 사실들 (추세 · 흔들림 · 금리)\n"
           f"· 오늘 {state} : S&P 500(SPY)이 20일선 {'위' if a20 else '아래'}, 50일선 {'위' if a50 else '아래'}\n"
           + (f"· 기록상 : 2008년 이후 이 사실들을 묶은 점수가 높던 날 · 중간 날 · 낮던 날, 20거래일 뒤 S&P 500이 오른 비율은 {up.get('Risk-On')}% · {up.get('Neutral')}% · {up.get('Risk-Off')}%로 같았습니다"
              if up else "· 기록상 : 이 사실들을 묶은 점수는 앞날을 가르지 못했습니다"))
    return C.question_card("지금 시장 흐름은?", state, "neutral", "#111", lines, tip=tip)


# ── 한국장 탭 ───────────────────────────────────────────────────────────

DIFF_MIN = 0.10   # 시기별 장중이 아무 날과 이만큼(%p) 넘게 달라야 "그 시기에 있었다"로 본다


def _decade_check(rec):
    """시기마다 같은 방향이었나 (대원칙: 묶지 않고 조건과 함께). 앞 두 시기(2000 · 2010년대)가 같은 방향이면 보여 주고,
    2020년 이후만 약하면 그 조건을 붙인다. 앞 두 시기가 엇갈리면 None — 보여 주지 않는다 (판단 유보, 빈 답 대신 생략)."""
    ds = {d["from"]: d for d in rec.get("decades") or []}
    if not ds.get("2000") or not ds.get("2010"):
        return None
    sign = 1 if rec["intra"] > 0 else -1
    strong = lambda d: (d["intra"] - d["intra_any"]) * sign >= DIFF_MIN   # noqa: E731
    if not (strong(ds["2000"]) and strong(ds["2010"])):
        return None
    names = {"2000": "2000년대", "2010": "2010년대", "2020": "2020년 이후"}
    text = "시기별 장중 : " + " · ".join(f"{names[k]} {_s(d['intra'])}" for k, d in ds.items()) + "."
    if ds.get("2020") and not strong(ds["2020"]):
        text += " 2020년 이후에는 이 경향이 거의 없었습니다."
    return text


def _bucket_text(p, who):
    rec, b = p.get("record"), p.get("bucket")
    if b in ("up", "down") and rec and rec["n"] >= MIN_BUCKET and _decade_check(rec) is not None:
        word = "오른" if b == "up" else "내린"
        return (f"미국 쪽이 평소의 2배 넘게 {word} 밤 다음 날, {eun(who)} 평균 {_s(rec['gap'])}로 시작했고 시작 뒤 장중에는 평균 {_s(rec['intra'])}였습니다 "
                f"(아무 날 {_s(p['intra_any'])}, {rec['n']}번). 시작 뒤 반대로 간 날이 {rec['against']}%였습니다.", _decade_check(rec))
    if b == "normal" and rec:
        return (f"오늘처럼 평범한 밤 다음 날 {eun(who)} 평균 {_s(rec['gap'])}로 시작했고, 시작 뒤 장중 흐름은 아무 날과 같았습니다.", "")
    if b in ("up", "down"):   # 기록이 시기마다 엇갈림 — 크기만 말한다
        return (f"오늘 미국 쪽 움직임은 평소의 {_times(p['us_z'])}였습니다. 이런 밤 다음 날 장중 흐름은 시기마다 엇갈려 경향으로 보지 않습니다.", "")
    if b == "mid":
        return (f"오늘 미국 쪽 움직임은 평소의 {_times(p['us_z'])}로, 크게 움직인 밤(2배 이상)은 아니었습니다.", "")
    return ("", "")


def seo_korea(a):
    """글 맨 앞 요약의 코스피 문장 (검색 노출) — 그날 S&P 500 크기에 따라 문장이 바뀐다. 매일 같은 문장이 되지 않게 오늘 숫자를 넣는다."""
    ks = next((p for p in a.get("korea") or [] if p["kr"] == "^KS11"), None)
    if not ks:
        return ""
    rec, b, since = ks.get("record"), ks.get("bucket"), ks["first"][:4]
    if b in ("up", "down") and rec and _decade_check(rec) is not None:
        word = "오른" if b == "up" else "내린"
        return (f"S&P 500이 평소의 {_times(ks['us_z'])}로 크게 {word} 밤이었고, {since}년 이후 이런 밤 다음 날 코스피는 평균 {_s(rec['gap'])}로 시작했습니다.")
    return (f"S&P 500 움직임은 평소의 {_times(ks['us_z'])}였고, {since}년 이후 기록에서 미국 밤사이 움직임은 다음 날 코스피 시작 가격에 절반가량 미리 반영됐습니다.")


def korea_open_card(a, opened=True):
    """K1 오늘 한국장에 미국장이 얼마나 닿나 — 코스피 ← S&P 500."""
    ks = next((p for p in a.get("korea") or [] if p["kr"] == "^KS11"), None)
    if not ks:
        return ""
    first_year = ks["first"][:4]
    lines = [(f"{first_year}년 이후 기록에서 미국 밤사이 움직임은 다음 날 코스피 시작 가격에 절반가량 미리 들어갔습니다 (시작 가격 상관 {ks['corr']:.2f}). "
              "그래서 시작 가격은 이미 미국장을 반영한 값입니다.", "plain")]
    t1, t2 = _bucket_text(ks, "코스피")
    if t1:
        lines.append((t1, "plain"))
    if t2:
        lines.append((t2, "plain"))
    bk = ks.get("buckets") or {}
    if bk:
        order = [("크게 오른 밤", "up"), ("평범한 밤", "normal"), ("크게 내린 밤", "down")]
        groups = [(nm, [bk[k]["gap"], bk[k]["intra"]]) for nm, k in order if k in bk]
        lines.append((C.chart_card(f"다음 날 코스피 평균 ({first_year}년 이후, %)", groups, [C.amber, C.gray], [C.sign_fg, C.sign_fg],
                                   [("시작 (전날 종가 대비)", C.AMBER), ("장중 (시작 → 종가)", C.GRAY_BAR)]), "html"))
    lines.append(("row", "S&P 500 (밤사이)", _s(ks["us_ret"]), f"평소의 {_times(ks['us_z'])}"))
    tip = ("미국 증시가 밤사이 움직인 만큼이 다음 날 한국 증시 시작 가격에 얼마나 들어가는지\n"
           f"· 오늘 S&P 500 {_s(ks['us_ret'])} : 평소의 {_times(ks['us_z'])}\n"
           "· 기록상 : 크게 움직인 밤 다음 날 시작 가격을 따라가면 장중에 되돌린 날이 더 많았습니다. 코스피 지수는 2019년까지 뚜렷했습니다")
    state = f"S&P 500 {_s(ks['us_ret'])}"
    return C.question_card("오늘 한국장에 얼마나 닿나?", state, "neutral", "#111", lines, tip=tip, opened=opened)


def korea_pairs_card(a):
    """K2 이어진 국내 종목 — 짝마다 오늘 미국 쪽 움직임과 기록."""
    ps = [p for p in a.get("korea") or [] if p["kr"] != "^KS11" and p["kr"] not in PAIR_HIDE]
    if not ps:
        return ""
    lead = max(ps, key=lambda p: abs(p["us_z"]))
    lines = [("국내 종목마다 함께 보는 미국 쪽 움직임입니다. 오른쪽 값은 지난밤 미국 쪽 등락이고, 상관이 1에 가까울수록 다음 날 시작 가격이 미국 쪽을 따라갔습니다.", "plain")]
    for p in ps:
        t1, t2 = _bucket_text(p, p["kr_name"])
        if p["bucket"] in ("up", "down") and t1.startswith("미국 쪽이"):
            lines.append(f"{p['kr_name']} : {t1}" + (f" {t2}" if t2 else ""))
    weak = [p for p in ps if p["corr"] < 0.45]
    if weak:
        lines.append((" · ".join(p["kr_name"] for p in weak) + "와 미국 쪽의 연결은 약했습니다 (상관 0.45 아래, 장중 경향 없음).", "note"))
    for p in ps:
        lines.append(("row", p["kr_name"], _s(p["us_ret"]), f"짝 : {p['us_name']} · 상관 {p['corr']:.2f}"))
    tip = ("한국 종목과 흔히 같이 보는 미국 지수 · 종목의 지난밤 움직임\n"
           f"· 오늘 {lead['us_name']} {_s(lead['us_ret'])} : 평소의 {_times(lead['us_z'])}\n"
           "· 기록상 : 반도체 짝(삼성전자 · SK하이닉스)은 시작 가격 상관 0.6 안팎, 테슬라와 2차전지는 0.4 안팎이었습니다 (2000년 이후)")
    return C.question_card("이어진 국내 종목은?", f"{lead['us_name']} {_s(lead['us_ret'])}", "neutral", "#111", lines, tip=tip)


def fx_card(a):
    """K3 · D4 환율 · 원화로 본 S&P 500."""
    fx = a.get("fx") or {}
    if fx.get("krw") is None:
        return ""
    spx = ((a.get("series") or {}).get("^GSPC") or {}).get("ret_1d")
    kc = (a.get("krw_check") or {}).get("big_down") or {}
    lines = []
    if fx.get("spx_won") is not None and spx is not None:
        lines.append((f"원화로 보면 오늘 S&P 500은 {_s(fx['spx_won'])}였습니다 (달러 기준 {_s(spx)}, 원/달러 {_s(fx['ret_1d'])}).", "plain"))
    lines += [("row", "원/달러 (1일)", _s(fx["ret_1d"]), "오르면 원화 약세"),
              ("row", "원/달러 (5일)", _s(fx["ret_5d"]), "")]
    if fx.get("spx_won") is not None:
        lines.append(("row", "원화로 본 S&P 500", _s(fx["spx_won"]), f"달러 기준 {_s(spx)}" if spx is not None else ""))
    tip = ("1달러가 몇 원인지와, 미국 주식을 원화로 들고 있을 때의 하루 등락\n"
           f"· 오늘 {fx['krw']:,.2f}원 : 하루 {_s(fx['ret_1d'])}\n"
           + (f"· 기록상 : S&P 500이 크게 내린 날({kc['n']}번, 2003년 이후) 원화 약세가 덜어 준 몫은 평균 {abs(kc['spx'] - kc['won']):.1f}%p였고, 그런 날의 {kc['cushion_share']}%에서만 덜어 줬습니다"
              if kc else ""))
    return C.question_card("환율은?", f"{fx['krw']:,.2f}원", "neutral", "#111", lines, tip=tip)


# ── 시장 탭 ─────────────────────────────────────────────────────────────

def mega_rows(a):
    """D4 대형주 10개 — 평소 범위 기준 크게 움직인 순. 급등주 · 거래 상위 목록 대신 (기획 5절 B6)."""
    nr = a.get("normal") or {}
    se = a.get("series") or {}
    syms = [s for s in MEGA_KO if s in nr]
    syms.sort(key=lambda s: -abs(nr[s]["z"]))
    rows = []
    for s in syms:
        n = nr[s]
        price = (se.get(s) or {}).get("last")
        value = (f'<span style="font-weight:400;">${price:,.2f}</span> ' if price else "") + dk.arrow(n["ret_pct"])
        sub = (f"<b>평소의 {_times(n['z'])}</b> · 1년에 {n['n_year']}번" if n["outside"] else f"평소 ±{n['sigma_pct']:.2f}% 안 · {_times(n['z'])}")
        rows.append(dk.crow(dk.ticker_logo(s) + C.esc(MEGA_KO[s]), value, sub, first=not rows, left=48, nowrap=True, sub_block=True))
    return rows


def mega_tip(a):
    nr = a.get("normal") or {}
    outs = [s for s in MEGA_KO if s in nr and nr[s]["outside"]]
    now = ("· 오늘 평소 밖 " + " · ".join(f"{MEGA_KO[s]} {_s(nr[s]['ret_pct'])}" for s in outs)) if outs else "· 오늘 : 10개 모두 평소 범위 안"
    return ("미국 시가총액 상위 10개 회사의 하루 움직임을 그 종목의 평소 크기와 비교한 것. 크게 움직인 순서로 놓았습니다\n" + now
            + "\n· 기록상 : 평소 밖으로 오른 다음 날 산 결과는 평소 국면에서 아무 날과 다르지 않았습니다 (S&P 500 종목, 약 30년)")


# ── 일정 탭 ─────────────────────────────────────────────────────────────

def _theme_for(day, today):
    left = (datetime.date.fromisoformat(day) - datetime.date.fromisoformat(today)).days
    return ("soon", C.SOON) if left <= SOON_DAYS else ("neutral", "#111")


def macro_cal_card(a, opened=True):
    cal = a.get("calendar") or {}
    items = [x for x in cal.get("items") or [] if x["kind"] != "EARNINGS"]
    days = cal.get("days") or 14
    if not items:
        return C.question_card("다가오는 경제 일정은?", "없음", "neutral", "#111",
                               [(f"앞으로 {days}일 안에 잡힌 큰 경제 일정이 없습니다.", "plain")], opened=opened)
    names = " · ".join(f"{MACRO_KO[x['kind']]}({_md(x['day'])})" for x in items)
    eff = {}
    for x in items:
        if x.get("effect"):
            eff.setdefault(x["kind"], x["effect"])
    first = f"앞으로 {days}일 안에 {names}가 있습니다."
    lines = [(first, "plain")]
    if eff:
        normal = next(iter(eff.values()))["normal"]
        big = [k for k, e in eff.items() if e["median"] >= normal * 1.2]
        same = [k for k, e in eff.items() if e["median"] < normal * 1.2]
        msg = f"2020년 이후 이런 날 S&P 500은 보통 ±{min(e['median'] for e in eff.values()):.2f}~{max(e['median'] for e in eff.values()):.2f}% 움직였고, 보통 날은 ±{normal:.2f}%였습니다."
        if same:
            msg += " " + " · ".join(MACRO_SHORT[k] for k in same) + " 날은 보통 날과 거의 같았습니다."
        if big:
            msg += " " + " · ".join(MACRO_SHORT[k] for k in big) + " 날은 보통 날보다 컸습니다."
        lines.append((msg, "plain"))
        groups = [(MACRO_SHORT[k], [e["median"], e["normal"]]) for k, e in eff.items()]
        lines.append((C.chart_card("그날 S&P 500 움직임 (2020년 이후, %)", groups, [C.amber, C.gray], [C.note_fg, C.note_fg],
                                   [("그 일정 날", C.AMBER), ("보통 날", C.GRAY_BAR)], fmt=lambda v: f"±{v:.2f}"), "html"))
    for x in items:
        e = x.get("effect")
        lines.append(("row", MACRO_KO[x["kind"]], _md(x["day"]), f"그날 S&P 500 보통 ±{e['median']:.2f}% ({e['n']}번)" if e else ""))
    theme, col = _theme_for(items[0]["day"], cal.get("from") or items[0]["day"])
    tip = ("금리 결정 · 물가 · 고용 같은 경제 발표와 옵션 만기처럼 시장 전체가 함께 보는 일정\n"
           f"· {days}일 안 {len(items)}건 : 가장 가까운 일정은 {MACRO_KO[items[0]['kind']]} {_md(items[0]['day'])}\n"
           "· 기록상 : 1996년 이후 일정 날의 S&P 500 움직임을 일정 없는 날과 견줬습니다. 일정이 있다고 늘 크게 움직이지는 않았습니다")
    return C.question_card("다가오는 경제 일정은?", f"{len(items)}건 · {days}일 안", theme, col, lines, tip=tip, opened=opened)


def earnings_cal_card(a):
    cal = a.get("calendar") or {}
    items = [x for x in cal.get("items") or [] if x["kind"] == "EARNINGS"]
    days = cal.get("days") or 14
    if not items:
        return C.question_card("대형주 실적 발표는?", "없음", "neutral", "#111", [(f"앞으로 {days}일 안에 대형주 10개의 실적 발표가 없습니다.", "plain")])
    names = " · ".join(f"{MEGA_KO[x['symbol']]}({_md(x['day'])})" for x in items)
    lines = [(f"앞으로 {days}일 안에 {names} 실적 발표가 있습니다.", "plain")]
    eff = [(x["symbol"], x["effect"]) for x in items if x.get("effect")]
    if eff:
        mult = [e["median"] / e["normal"] for _, e in eff if e["normal"]]
        lines.append((f"2010년 이후 이 회사들은 발표 다음 날 보통 그 종목 평소 하루의 {min(mult):.0f}~{max(mult):.0f}배를 움직였습니다. 내 종목의 실적 날은 평소와 다른 날입니다.", "plain"))
        groups = [(MEGA_SHORT[s], [e["median"], e["normal"]]) for s, e in eff]
        lines.append((C.chart_card("발표 다음 날 그 종목 움직임 (%)", groups, [C.amber, C.gray], [C.note_fg, C.note_fg],
                                   [("발표 다음 날", C.AMBER), ("그 종목 보통 날", C.GRAY_BAR)], fmt=lambda v: f"±{v:.1f}"), "html"))
    for x in items:
        e = x.get("effect")
        when = _md(x["day"]) + (" 장 마감 뒤" if x.get("after_close") else "")
        lines.append(("row", f"{MEGA_KO[x['symbol']]} ({x['symbol']})", when, f"다음 날 보통 ±{e['median']:.1f}% · 평소 ±{e['normal']:.1f}%" if e else ""))
    lines.append(("발표일은 회사가 확정하기 전 추정일일 수 있습니다.", "note"))
    theme, col = _theme_for(items[0]["day"], cal.get("from") or items[0]["day"])
    tip = ("미국 시가총액 상위 10개 회사의 실적 발표일\n"
           f"· {days}일 안 {len(items)}곳 : 가장 가까운 발표는 {MEGA_KO[items[0]['symbol']]} {_md(items[0]['day'])}\n"
           "· 기록상 : 2010년 이후 회사마다 60번 안팎의 발표 다음 날 움직임을 그 종목 보통 날과 견줬습니다")
    return C.question_card("대형주 실적 발표는?", f"{len(items)}곳 · {days}일 안", theme, col, lines, tip=tip)
