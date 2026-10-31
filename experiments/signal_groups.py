"""판정 묶음 분류표 — 종목 페이지의 모든 판정에 같은 꼬리표(방향 · 기간 · 계열)를 붙인다 (doc/기획/데이터-기록-계획.md A5, 2026-10-31).

쓰는 곳
- 함께 보기(`Alpha Scope 데이터로 함께 보기`, render_html.together_block): 방송 의견 아래에 같은 종목의 판정을 상승 쪽 · 하락 쪽 · 중립으로 다시 놓는다 (A5-5 1단계, P172)
- 매일 기록(record_store verdicts — A5-4, 아직): 같은 꼬리표로 남겨야 나중에 검증 · 바깥 의견과 맞대 볼 수 있다

원칙 (A5-1)
- 방향은 관행 해석의 가설이다. 검증이 뒤집으면 여기서 바꾸고 SCHEME 을 올린다 — 기록에는 그때의 SCHEME 이 남는다
- 개수를 세서 결론 내지 않는다. 이 표는 나누어 놓을 뿐, 합계 · 종합 말은 만들지 않는다
- 같은 계열은 한 표 — 계열 꼬리표로 중복을 드러낸다 (이동평균 대비 · 기술지표는 둘 다 `가격`)
- 용어는 블로그와 같게: 상승 쪽 · 하락 쪽 · 중립. 방향이 없거나(일정 · 고점 회복) 가설이 둘인 것(볼린저)은 묶음에 넣지 않는다

함께 보기 줄 = (이름, 판정 말, 방향 +1 · −1 · 0, 탭, 카드 제목 앞부분, 기간) — render_html.together_block 이 읽는다.
"""

SCHEME = "2026-10-31a"   # 분류표 버전 — 방향 해석을 바꾸면 올린다

# 기간 꼬리표 (A5-2) — 기간이 다른 신호를 한 표로 세면 뜻이 없다. 함께 보기 줄마다 작은 글씨로 보인다
OPEN, DAYS, MONTH, QUARTER = "다음 날 시가", "며칠", "한 달", "분기"
# 계열 꼬리표 (A5-2)
PRICE, EARN, INDUSTRY, FLOW, MARKET, OUTSIDE = "가격", "실적과 예상", "업종과 경기", "수급", "시장", "바깥 의견"

UP, DOWN, FLAT = 1, -1, 0

# 카드 → 꼬리표. direction = {판정 말: 방향} — 표에 없는 말(판단 유보 · 비슷함 · 엇갈림 …)은 중립.
# 카드 제목 · 이름의 {biz} 는 한국 업계 이름, {sector} 는 미국 업종 이름 — item() 이 채운다.
TABLE = {
    "momentum":  dict(name="12개월 모멘텀", tab="오늘", card="", horizon=MONTH, family=PRICE,            # 카드 = 가격 카드(종목 이름으로 찾는다)
                      direction=None),   # 방향은 순위 구역으로 — momentum_item()
    "ma":        dict(name="평균선 대비", tab="오늘", card="", horizon=MONTH, family=PRICE,       # 20 · 60 · 120 · 200일 모두 위 → 상승 쪽 (추세 해석, A5-7 1)
                      direction=None),   # ma_item()
    "tech":      dict(name="기술지표 방향", tab="오늘", card="기술지표의 방향은?", horizon=DAYS, family=PRICE,
                      direction={"강한 상승": UP, "상승": UP, "하락": DOWN, "강한 하락": DOWN}),
    "overheat":  dict(name="과열 신호", tab="오늘", card="과열 신호는?", horizon=DAYS, family=PRICE,
                      direction=None),   # 해당 조건이 있으면 하락 쪽 — overheat_item()
    "pairs":     dict(name="밤사이 미국과 연결 종목", tab="오늘", card="함께 움직이는 종목은?", horizon=OPEN, family=MARKET,   # ✅ 다음 날 시가 갭만 (10-25 검증)
                      direction={"올랐음": UP, "내렸음": DOWN}),
    "revenue":   dict(name="회사 매출", tab="실적", card="회사는 돈을 더 벌고 있나?", horizon=QUARTER, family=EARN,
                      direction={"늘고 있음": UP, "줄고 있음": DOWN}),
    "eps":       dict(name="내년 이익 예상", tab="실적", card="내년 이익 예상은?", horizon=MONTH, family=EARN,
                      direction={"높아지는 중": UP, "낮아지는 중": DOWN}),
    "short":     dict(name="공매도 잔고", tab="실적", card="하락에 거는 돈은?", horizon=MONTH, family=FLOW,
                      direction={"늘어나는 중": DOWN, "줄어드는 중": UP}),
    "bsi":       dict(name="{biz} 업계 경기", tab="업계상황", card="{biz} 업계 경기는?", horizon=QUARTER, family=INDUSTRY,
                      direction={"좋아지는 중": UP, "나빠지는 중": DOWN}),
    "biz_work":  dict(name="{biz} 업계 {q}", tab="업계상황", card="{biz} 업계 {q}은?", horizon=QUARTER, family=INDUSTRY,   # 값 · 일감 · 수출 … (universe_kr.BIZ_Q)
                      direction={"오르는 중": UP, "내리는 중": DOWN, "늘고 있음": UP, "줄고 있음": DOWN, "넓어지는 중": UP, "좁아지는 중": DOWN, "커지는 중": UP, "줄어드는 중": DOWN}),
    "biz_money": dict(name="{biz} 업계 수익성", tab="업계상황", card="{biz} 업계 수익성은?", horizon=QUARTER, family=INDUSTRY,
                      direction={"나아짐": UP, "나빠짐": DOWN}),
    "sector_flow": dict(name="{sector} 업종 자금", tab="오늘", card="{sector}", horizon=DAYS, family=FLOW,   # 카드 제목 `반도체로 돈이 올까?` · `{sector} 업종으로 돈이 올까?` — 앞부분으로 찾는다
                        direction={"모이는 중": UP, "빠져나가는 중": DOWN}),
    "regime":    dict(name="시장 분위기", tab="오늘", card="시장 분위기는?", horizon=DAYS, family=MARKET,   # 종목이 아닌 시장
                      direction={"상승 추세": UP, "조정장": DOWN}),
    "shock":     dict(name="시장 충격 국면", tab="오늘", card="시장 충격 국면은?", horizon=DAYS, family=MARKET,
                      direction={"충격 국면 중": DOWN}),
}

# 함께 보기에 놓는 순서 — 주가에 가까운 것부터 (P142): 가격 → 실적과 예상 → 수급 → 업종과 경기 → 시장
ORDER = ["momentum", "ma", "tech", "overheat", "pairs", "revenue", "eps", "short", "sector_flow", "bsi", "biz_work", "biz_money", "regime", "shock"]


def _row(key, state, direction, **names):
    t = TABLE[key]
    fill = lambda x: x.format(**names) if names else x   # noqa: E731
    return (fill(t["name"]), state, direction, t["tab"], fill(t["card"]), t["horizon"])


def item(key, state, **names):
    """판정 말 → 함께 보기 줄. 방향표에 없는 말은 중립. state 가 없거나 판단 유보면 None(묶음에서 뺀다)."""
    if not state or state == "판단 유보":
        return None
    d = TABLE[key]["direction"] or {}
    return _row(key, state, d.get(state.lstrip("▲▼ "), FLAT), **names)   # 미국 기술지표 말은 `▼ 하락` 처럼 기호가 앞에 붙는다


def momentum_item(rank, total, name):
    """12개월 모멘텀 — 우리 종목 안 상위 25% → 상승 쪽 · 하위 25% → 하락 쪽 (K18 검증: 한국 35종목 안, 좁은 표본). 카드 = 가격 카드(제목이 종목 이름)."""
    if not rank or not total:
        return None
    d = UP if rank <= total / 4 else DOWN if rank > total * 3 / 4 else FLAT
    nm, _, _, tab, _, hz = _row("momentum", "", d)
    return (nm, f"{total}종목 중 {rank}위", d, tab, name, hz)


def ma_item(ma_rel, name):
    """지금 가격이 평균보다 — 20 · 60 · 120 · 200일 평균 모두 위면 상승 쪽, 모두 아래면 하락 쪽, 섞이면 중립 (추세 해석, 기술지표 이동평균 줄과 같은 말 · 같은 계열 = 한 표)."""
    get = lambda n: (ma_rel or {}).get(n, (ma_rel or {}).get(str(n)))   # noqa: E731
    vals = [get(n) for n in (20, 60, 120, 200)]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    above, below = sum(1 for v in vals if v > 0), sum(1 for v in vals if v < 0)
    n = len(vals)
    if above == n:
        st, d = f"{n}개 평균 모두 위", UP
    elif below == n:
        st, d = f"{n}개 평균 모두 아래", DOWN
    else:
        st, d = f"{above}개 위 · {below}개 아래", FLAT
    nm, _, _, tab, _, hz = _row("ma", "", d)
    return (nm, st, d, tab, name, hz)


def overheat_item(oh):
    """과열 신호 — 해당 조건이 하나라도 있으면 하락 쪽(관행 해석: 과열 = 되돌림). 없는 날은 카드도 없으니 줄도 없다."""
    if not oh or not oh.get("active"):
        return None
    return _row("overheat", f"{len(oh['active'])}개 조건 해당", DOWN)


def tags(key):
    """기록용 꼬리표 (A5-4) — direction 은 state 로 따로, 여기서는 기간 · 계열 · 분류표 버전."""
    t = TABLE[key]
    return {"horizon": t["horizon"], "family": t["family"], "scheme": SCHEME}
