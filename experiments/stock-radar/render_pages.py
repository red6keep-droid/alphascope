"""시총 TOP 10 목록 페이지 · 간단형 상세 페이지 HTML (doc/기획/종목-레이더-기획.md 10-3 · 10-10, 1단계 = 숫자와 실적일만).

카드 모양은 엔비디아 리포트 가격 카드 펼침(가이드라인 2-4 11-1)과 같게 — 그 렌더러의 작은 조각(_row · _row_html · _col_chart …)을 그대로 쓴다.
툴팁은 뜻 · 오늘 (+ 참고) (2-6). `기록상` 줄은 두지 않는다(가이드라인 1절 4-2, 2026-11-01).
"""

import datetime
from zoneinfo import ZoneInfo
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "nvda-report"))

import design_kit as _dk  # noqa: E402
import people_section  # noqa: E402  — 인물 발언 구획 (2026-11-07 사용자, 목업)
import media_feed  # noqa: E402
import news_store  # noqa: E402  — 공용 뉴스 처리 (헤드라인 · 요약 줄 고르기)
import chart_price as CP  # noqa: E402
import render_html as R  # noqa: E402
import signal_groups as SG  # noqa: E402 — 판정 묶음 분류표 (함께 보기, A5)

import universe as U  # noqa: E402
import court  # noqa: E402 — 소송 일정 (P270)
import crash_watch as CW  # noqa: E402 — 급락장에서 어땠나? (오늘 탭, 2026-11-04)

UP, DOWN, NOTE, TINY = _dk.UP, _dk.DOWN, _dk.NOTE, _dk.TINY
PAD = _dk.SEP_GAP - _dk.VP - 1


def _esc(t):
    return _dk.esc(t)


def _md(d):
    d = datetime.date.fromisoformat(str(d)[:10])
    return f"{d.month}월 {d.day}일"


def _sgn(v):
    return f"{v:+.1f}".replace("-", "−")


def cap_text(c):
    """시가총액 → `5.17조 달러` · `9,940억 달러`."""
    if not c:
        return "—"
    if c >= 1e12:
        return f"{c / 1e12:.2f}조 달러"
    return f"{c / 1e8:,.0f}억 달러"


def updated_line(a):
    return _dk.muted(f"마지막 갱신 {_dk.day(a['day'])} 장 마감 기준")


def wrap(body):
    html = _dk.align_titles(_dk.WRAP_OPEN + body + _dk.WRAP_CLOSE)
    return _dk.formal(_dk.fix_colons(html))   # 카드 밖 구획 제목은 좌측 기준선(ALIGN_PX) (2026-10-23 사용자) · 반말 문장 끝은 합니다체 (2026-10-18 사용자)


def list_marker(url):
    """글 아래 테마 [목록] 버튼이 갈 곳 (테마 JS 가 읽는다, 2026-10-18 사용자: 하단 목록 · TOP 은 엔비디아 글과 공통). 화면에는 안 보인다."""
    return f'<span data-list-url="{_esc(url)}" data-nav="back" hidden></span>'   # data-nav=back : 홈에서 왔으면 `홈으로`, 아니면 `목록으로` (2026-10-29 사용자 P94)


def home_marker():
    """글 아래 버튼을 늘 `홈으로` (목록 · 읽는 법 페이지, 2026-10-29 사용자 P94). 화면에는 안 보인다."""
    return '<span data-nav="home" hidden></span>'


# ---------------------------------------------------------------- 상세 (간단형)

def lead(s):
    """맨 위 요약 1~2문장 (p[data-seo-lead], 가이드라인 10-5) — 날마다 달라지는 글. 파이썬 값만, 평가 · 예측 없음."""
    r = s["ret_1d"]
    move = f"전날보다 {abs(r):.2f}% {'올랐다' if r > 0 else '내렸다'}" if abs(r) >= 0.005 else "전날과 같았다"
    close = f"${s['close']:,.2f}"
    first = f"{_md(s['day'])} {s['name']}({s['sym']}) 종가는 {_dk.josa(close, '로')} {move}."   # `$347.73로` → `으로` (P69)
    nr = s.get("normal_range")
    if nr:
        first += (" 실적 발표에 처음 반응한 날이었다." if nr["earnings_day"] else
                  " 평소 하루 움직임 안의 변화였다." if abs(nr["z"]) < 2 else f" 평소 하루 움직임의 {abs(nr['z']):.1f}배였다.")
    first += R.gap_sentence((s.get("tech") or {}).get("gap"))   # 시가 갭은 평소 범위 바로 뒤 (P80)
    more = []
    if s.get("rank"):
        more.append(f"시가총액은 미국 {s['rank']}위({cap_text(s['cap'])})")
    nxt = (s.get("earnings") or {}).get("next")
    if nxt:
        more.append(f"다음 실적 발표는 {_md(nxt)} 예정")
    text = first + (" " + "이고, ".join(more) + "이다." if more else "")
    return f'<p data-seo-lead="1" style="{_dk.SEO_LEAD}">{_dk.tint(_esc(text))}</p>'   # 요약 문장의 증감도 색 (가이드라인 3-3, 2026-10-21)


def range_tip(s):
    nr = s["normal_range"]
    k = abs(nr["z"])
    now = (f"· 오늘 {_sgn(s['ret_1d'])}% : 실적 발표에 반응한 날이라 평소 범위로 재지 않는다" if nr["earnings_day"] else
           f"· 오늘 {_sgn(s['ret_1d'])}% : 평소 하루 움직임(±{nr['sigma_pct']:.1f}%)의 {k:.1f}배" + (", 평소 범위 안" if k < 2 else ", 평소 범위 밖"))
    return "최근 움직임으로 잰 이 종목의 보통 하루 등락 폭. 그 2배를 넘으면 평소 범위 밖으로 본다\n" + now


def _glance(s):
    """NVDA 리포트 가격 카드 함수(glance_sub · glance_rows)가 읽는 모양으로 옮긴다 — 같은 규칙 · 같은 문구."""
    tc = s.get("tech") or {}
    nr = dict(s["normal_range"], market_shock=s.get("market_shock")) if s.get("normal_range") else None
    return {"headline": {"close": s["close"], "ret_1d": s["ret_1d"], "vol_ratio_20d": s.get("vol_ratio"),
                         "range_pct": tc.get("range_pct"), "ret_vs_spy": tc.get("vs_spy")}, "normal_range": nr}


def price_card(s, today):
    """가격 카드 — NVDA 리포트 sec_headline 과 같은 틀 (2026-10-18 리포트 개편 구조).
    머리 = 가격 줄 + 작은 글씨 한 줄(평소 범위 · 거래량), 오른쪽 접기 버튼. 펼치면 1층(기간별 수익률 · 1년 범위 · 고점 회복 · 실적)과 2층 `차트 정보 보기`.
    거래량 카드는 따로 두지 않는다 — 머리 작은 글씨에 늘 있다 (NVDA 2026-10-18 사용자)."""
    r = s["ret_1d"]
    g = _glance(s)
    pcol = UP if r > 0 else DOWN if r < 0 else "#111"
    tone = R.ROW_UP if r > 0 else R.ROW_DOWN if r < 0 else ""   # 엔비디아 가격 카드와 같은 강조 카드 높이(위아래 여백 · 행간 32) — design_kit 의 ROW_UP 에는 강조 여백이 없다 (2026-10-23 사용자)
    bg, bd = ("#FFF7EE", "#FEE6CA") if r > 0 else ("#EFF6FF", "#D6E8FE") if r < 0 else ("#fff", "#E2E8F0")
    price = R.price_value(f'<span style="color:{pcol};font-weight:700;white-space:nowrap;">${s["close"]:,.2f}</span>', R._arrow(r),
                          R._fold_btn(_dk.lighten(bg), bd) if r else R.ACC_BTN)   # 길면 등락이 아래 줄로 (P61)
    head = R.price_row(R._row(s["sym"], price, tone)).replace("margin:0 0 6px;", "margin:0;", 1)
    sub = R.glance_sub(g)   # 엔비디아와 같은 함수 · 같은 짧은 문구
    if sub:
        head = head.replace("display:flex;", "display:flex;flex-wrap:wrap;", 1).replace("gap:12px;", "column-gap:12px;row-gap:2px;", 1)
        k = head.rstrip().rfind("</span>")
        head = head[:k] + sub + head[k:]
    rows = R.glance_rows(g)   # 가격 범위 (1년) · 기간별 수익률 · 고점 회복 · 차트 정보 보기는 강조 카드 안 (2026-10-26 사용자). 옛 `다음 실적 발표` 접기 줄은 뺐다 — 실적 탭 `주요 일정` 의 `다음 실적 발표는?` 와 같은 내용, 한국 가격 카드와 같게 (2026-11-01 사용자 P261)
    return (f'<div data-cards="1" style="margin:0 0 8px;"><details data-acc="1"><summary style="list-style:none;cursor:pointer;display:block;">{head}</summary>'
            f'{R.price_in(bg, bd, [sec_year_range(s), R.in_card(sec_drawdown(s), join=True), sec_month_range(s), R.in_card(sec_periods(s), white=True), sec_momentum(s), sec_chart_indicators(s)])}{R.rows_after(rows)}</details></div>')


IMAGE_BRANCH = "radar-images"   # 종목 그래프 전용 브랜치 — 매 실행 그날 그림만 담아 덮어쓴다(이력 없음). 지난 그림은 남지 않는다 (2026-10-20 사용자: 이미지는 휘발성)


def chart_url(sym):
    """가격 그래프 주소 — 고정 페이지라 파일 이름도 고정(날짜 없음). 게시 때 radar-images 브랜치에 올리고 jsDelivr 캐시를 비운다.
    gh-pages(keep_files)에 두면 매일 49장이 커밋 이력에 쌓여 저장소가 커진다 — 그래서 따로 (2026-10-20)."""
    return f"https://cdn.jsdelivr.net/gh/{CP._repo_slug()}@{IMAGE_BRANCH}/images/{chart_ref(sym)}"


def chart_ref(sym):
    return f"radar-{U.BY_SYM[sym][2]}-price.png"


def sec_chart(s):
    """가격 그래프 — NVDA 리포트 sec_chart 와 같은 자리 · 모양 (본문 맨 앞 요약 아래, 확대 보기)."""
    if not s.get("chart"):
        return ""
    url = chart_url(s["sym"])
    zoom = ('<svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">'
            '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5 14 14M7 5v4M5 7h4"/></svg>')
    return (f'<a href="{_esc(url)}" data-zoom="1" target="_blank" rel="noopener" title="그래프 확대 보기" aria-label="그래프 확대 보기" '
            f'style="position:relative;display:block;margin:0 0 16px;max-width:1024px;">'
            f'<img src="{_esc(url)}" alt="{_esc(s["sym"])} {CP.WINDOW}거래일 봉차트" style="width:100%;display:block;border:1px solid #eee;border-radius:8px;"/>'
            f'<span style="position:absolute;right:8px;bottom:8px;display:flex;align-items:center;justify-content:center;width:32px;height:32px;'
            f'background:rgba(255,255,255,.92);border:1px solid #E2E8F0;border-radius:8px;color:#111;">{zoom}</span></a>'
            + _dk.tv_chart_fold(s["sym"].replace("-", "."), "America/New_York", s["sym"]))   # 장중 차트 접힘 줄 — 펼칠 때만 TradingView (2026-11-05). BRK-B → BRK.B


def draw_charts(snap, stocks, out_dir):
    """종목마다 봉차트 PNG (NVDA chart_price.draw 그대로) → output/images/. 시가가 빈 날은 종가로 채운다."""
    for s in stocks:
        bars = [dict(b, open=b["open"] if b.get("open") else b["close"]) for b in (snap["bars"].get(s["sym"]) or [])][-(CP.WINDOW + CP.LOOKBACK):]
        if len(bars) < 2:
            continue
        CP.draw(bars, os.path.join(out_dir, "images", chart_ref(s["sym"])), s["sym"])
        s["chart"] = True
    sb = [dict(b, open=b["open"] if b.get("open") else b["close"]) for b in (snap["bars"].get(U.BENCH) or [])][-(CP.WINDOW + CP.LOOKBACK):]
    if len(sb) >= 2:   # 미국 증시 분위기 카드 펼침의 S&P 500 그래프 (P215) — S&P 500 ETF(SPY) 일봉, 종목 그래프와 같은 그림 · 고정 이름(radar-*.png 라 배포 · 캐시 비우기에 함께)
        CP.draw(sb, os.path.join(out_dir, "images", SPX_REF), "S&P 500")


SPX_REF = "radar-sp500-price.png"


def sec_periods(s):
    ps = s.get("periods") or []
    if not ps:
        return ""
    chart = R._col_chart([(p["label"], [p["stock"], p.get("spy")]) for p in ps[::-1]], [R._sign_bg, lambda v: R._GRAY_BAR], [R._sign_fg, lambda v: NOTE], right=True)   # 1년 → 1주 (P165)
    legend = R._legend_chips([(f"{s['name']} 오름", R._PASTEL_UP), (f"{s['name']} 내림", R._PASTEL_DN), ("S&P 500", R._GRAY_BAR)])
    card = f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}"><span style="display:block;padding:{_dk.CHART_CARD_PAD}px 12px 0;">{_dk.legend_top(chart, legend)}</span></span></div>'
    return R._card_title("기간별 수익률 (%, 배당 포함)") + card   # 툴팁 없음 — 그래프가 기간 · S&P 500 비교를, 제목 괄호가 `배당 포함` 을 말한다 (2026-11-08 사용자: 카드와 겹치는 툴팁 생략, 가이드라인 11절)


def year_tip(y):
    pct = y["pct_from_high"]
    where = "1년 최고가 근처" if pct > -0.5 else f"1년 최고가보다 {abs(pct):.1f}% 아래"
    return ("지난 1년 동안 가장 쌌던 값과 가장 비쌌던 값 사이에서 지금 어디쯤인지\n"
            f"· 오늘 ${y['close']:,.2f} : {where}, 범위의 {max(0.0, min(100.0, y['pos_pct'])):.0f}% 지점")


def sec_year_range(s):
    """가격 범위 (1년) — 가격 정보 강조 카드 안 (R.year_range_in, 2026-10-26 사용자)."""
    y = s.get("year_range")
    if not y:
        return ""
    return R.year_range_in(y, lambda v: f"${v:,.2f}", year_tip(y), (s.get("drawdown") or {}).get("days_since_high"))


def sec_month_range(s):
    """한 달간 변화 범위 — 고점 회복 문장 아래 (2026-10-31 사용자 P155: 1년 범위 → 회복 문장 → 한 달 범위), 옛 오늘 탭 상태 카드 (P150)."""
    bb = s.get("bollinger")
    if not bb or bb.get("lower") is None:
        return ""
    th, col = R.BOLL_THEME.get(bb["state"], ("neutral", R.MUTED))
    return ("white", R.month_range_in(bb, lambda v: f"${v:,.0f}", "", R.BOLL_STATE_KO.get(bb["state"], "범위 안"), col, top=0))


def sector_lines(sf):
    return R.sector_lines(sf, "S&P 500")


def sec_tech(s):
    """기술지표의 방향은? (옛 제목 기술 지표는 어느 쪽을 가리키나?, P121) (2026-10-30 사용자) — 한국 종목 페이지와 같은 카드 (experiments/tech_signals)."""
    sig = (s.get("tech") or {}).get("signals")
    if not sig:
        return ""
    import tech_signals
    lines, tip = tech_signals.card(sig, s["name"], UP, DOWN, R.MUTED)
    th, col = tech_signals.theme(sig["net"], UP, DOWN, R.MUTED)   # 상승 빨강 · 하락 파랑의 연한 카드 (P99)
    card = R._state_card("기술지표의 방향은?", sig["word"], th, col, lines, "", tip=tip, fold=True)
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{card}</div>'


def _kr_links(sym):
    """한국 페이지의 `밤사이 미국 연결 짝`(universe_kr.PAIRS)을 거꾸로 — 이 미국 종목을 짝으로 둔 한국 종목 [(이름, 기록 %p, 통과?)], 통과 · 차이 큰 순 (P263)."""
    import importlib.util
    path = os.path.join(_HERE, "..", "kr-stocks", "universe_kr.py")
    spec = importlib.util.spec_from_file_location("universe_kr", path)
    UK = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(UK)
    out = []
    for ksym, (us, _why) in UK.PAIRS.items():
        if sym in us and ksym in UK.BY_SYM and ksym in UK.PAIR_RECORD:
            sp, _n, ok, _y0 = UK.PAIR_RECORD[ksym]
            out.append((UK.name(ksym), sp, ok, [U.peer_name(x) for x in us]))
    return sorted(out, key=lambda x: (not x[2], -x[1]))


def sec_pairs(s):
    """`함께 움직이는 종목은?` — 한국 페이지와 같은 자리 · 같은 막대 (2026-11-01 사용자 P263: 한국과 비슷한 포맷).
    ① 함께 보는 회사(경쟁 · 공급 · 고객, universe.PEERS)의 오늘 등락 + 이 종목 · S&P 500 ② 한국 연결 종목 = 한국 페이지 `밤사이 미국` 짝을 거꾸로, 검증 기록(다음 날 시가).
    답 = 함께 보는 회사가 같이 올랐나 · 내렸나. 같은 날 함께 움직인 것은 앞날 신호가 아니라 전망 카드 개수에는 넣지 않는다 (verdict_items 에 없음)."""
    moves = s.get("peer_moves") or []
    links = _kr_links(s["sym"])
    if not moves and not links:
        return ""
    rets = [r for _, _, r in moves]
    ups, downs = sum(1 for x in rets if x >= 0.5), sum(1 for x in rets if x <= -0.5)
    state = "판단 유보" if not rets else "엇갈림" if ups and downs else "같이 올랐음" if ups else "같이 내렸음" if downs else "비슷함"
    theme, col = {"엇갈림": ("uncertain", R.SOON), "같이 올랐음": ("positive", R.UP), "같이 내렸음": ("negative", R.DOWN)}.get(state, ("neutral", R.MUTED))
    lines = []
    if moves:
        day = _md(s["day"])
        lines.append((f"오늘({day}) 함께 보는 회사는 " + ", ".join(f"{U.peer_name(p)} {_sgn(r)}%" for p, _, r in moves)   # 쉼표 — ` · ` 로 이으면 짧은 덩어리를 이름까지 통째로 칠한다(_dk.tint)
                      + f"였고, {_dk.josa(s['name'], '은')} {_sgn(s['ret_1d'])}%였다.", "plain"))
        rows = [(U.peer_name(p), role, r, "us") for p, role, r in moves] + [(s["name"], "", s["ret_1d"], "me")]
        vs = s["tech"].get("vs_spy")
        if vs is not None:
            rows.append(("S&P 500", "", s["ret_1d"] - vs, "bench"))
        lines.append((R.pair_bars([(f"함께 보는 회사 ({day})", rows)]), "html"))
    ok = [x for x in links if x[2]][:4]
    if ok:   # 한국 연결 종목 — 검증 통과한 것만, 다음 날 시가 차이
        lines.append((f'{_dk.CHART_TITLE_M}한국 연결 종목 <span style="font-weight:400;font-size:{R.TINY};color:{R.NOTE};">(다음 날 시가)</span></span>', "html"))
        for k, (nm, sp, _ok, us) in enumerate(ok):
            lines.append(("row", nm, f"{_sgn(sp)}%p", f"{_dk.josa(' · '.join(us), '이')} 많이 오른 밤과 내린 밤의 차이", False, k == 0))
    R.add_small_note(lines, "±0.5% 넘게 움직인 회사만 오른 곳 · 내린 곳으로 셉니다.")   # 옛 툴팁의 기준을 카드 작은 글씨로 — 툴팁 없음 (2026-11-08 사용자: 카드와 겹치는 툴팁 생략, 가이드라인 11절)
    card = R._state_card("함께 움직이는 종목은?", state, theme, col, lines, "", fold=True)
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{card}</div>'


def sec_regime(s):
    """`미국 증시 분위기는?` (2026-11-01 사용자 P214: 옛 `시장 분위기는?` · 기술지표 카드 위로). 펼치면 첫 문장 아래 S&P 500 봉차트(P215) → 고점 대비 줄."""
    mr = s.get("market_regime")
    if not mr:
        return ""
    th, col = R.REGIME_THEME.get(mr["regime"], ("neutral", R.MUTED))
    lines = R.regime_lines(mr)
    if s.get("chart"):
        lines.insert(1, R.index_chart_line(f"https://cdn.jsdelivr.net/gh/{CP._repo_slug()}@{IMAGE_BRANCH}/images/{SPX_REF}", f"images/{SPX_REF}", "S&P 500"))
    card = R._state_card("미국 증시 분위기는?", mr["regime"], th, col, lines, "", fold=True)   # 툴팁 없음 — 근거 줄마다 나누는 법이 있다 (2026-11-08 사용자: 카드와 겹치는 툴팁 생략, 가이드라인 11절)
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{card}</div>'


def sec_states(s):
    """상태 카드 — NVDA 리포트와 같은 카드 · 규칙. 업종 카드만 종목의 업종 ETF 로. 시장 충격 · 한 달 범위 · 과열은 해당하는 날만."""
    out = ""
    ms = s.get("market_shock") or {}
    if ms.get("active"):
        out += R._state_card("시장 충격 국면은?", "충격 국면 중", "uncertain", R.SOON, R.shock_lines(ms), "", tip=R.shock_tip(ms), fold=True)
    # `미국 증시 분위기는?` 은 기술지표 카드 위로 옮겼다 (sec_regime, 2026-11-01 사용자 P214)
    # 업종 자금 카드는 `업계상황` 탭으로 옮겼다 (2026-10-31 사용자: 업종 전체 이야기 — 한국처럼 다른 탭)
    # `한 달간 변화 범위는?` 상태 카드는 가격 카드 펼침(가격 범위 (1년) 아래)으로 옮겼다 (2026-10-31 사용자 P150)
    # `애널리스트 · 방송 의견은?` 은 `의견` 탭으로 옮겼다 (2026-11-01 사용자 P196: 오늘 탭이 너무 길다)
    oh = s.get("overheat")
    if oh and oh["active"]:
        out += R._state_card("과열 신호는?", f"{len(oh['active'])}개 조건 해당", "neutral", R.MUTED, R.overheat_lines(oh), "", tip=R.overheat_rule(oh))
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>' if out else ""


def sec_momentum(s):
    """12개월 모멘텀 — 한국과 같은 카드(R.momentum_in). 미국은 검증을 통과하지 못해(64종목 −0.30%p/월 p .51, doc/검증/미국-모멘텀-검증.md)
    함께 보기 방향 분류에 넣지 않는다 (2026-10-31 사용자)."""
    mom, mr = s.get("mom_12_1"), s.get("mom_rank")
    if mom is None or not mr:
        return ""
    rank, total = mr
    tip = ("12개월 전 가격 대비 1개월 전 가격의 변화. 최근 1개월은 단기 되돌림이 섞여 빼는 것이 표준(12-1 모멘텀)\n"
           f"· 오늘 {_sgn(mom)}% : 우리 {total}종목 가운데 {rank}위")
    return ("white", R.momentum_in(s["name"], mom, rank, total, s.get("mom_peers_median"), s.get("mom_bench"), "S&P 500", tip))


def _fred_value(sid, v):
    """FRED 값 → 읽기 쉬운 글. 소매 · 주문 · 건설 = 백만 달러, 은행 대출 = 십억 달러, 신차 = 백만 대(연율), 기업이익 = 십억 달러(연율)."""
    if sid.startswith(("RS", "NEWORDER", "PNRES", "A34")):
        return f"{v / 100:,.0f}억 달러"
    if sid == "TOTLL":
        return f"{v / 1000:,.1f}조 달러"
    if sid == "TOTALSA":
        return f"{v * 100:,.0f}만 대"
    if sid == "MCOILWTICO":
        return f"{v:,.1f}달러"
    if sid.endswith("SBEA"):
        return f"{v * 10:,.0f}억 달러"
    if sid.startswith(("QREV", "REV")):   # 서비스 업종 분기 매출 — 백만 달러
        return f"{v / 100:,.0f}억 달러"
    return f"{v:,.1f}"   # 지수


def _fred_scale(sid):
    """그래프 숫자 나누기 · 단위 — 단위는 그래프 오른쪽 위."""
    if sid.startswith(("RS", "NEWORDER", "PNRES", "A34")):
        return 100, "억 달러"
    if sid == "TOTLL":
        return 1000, "조 달러"
    if sid == "TOTALSA":
        return 0.01, "만 대"
    if sid == "MCOILWTICO":
        return 1, "달러"
    if sid.endswith("SBEA"):
        return 0.1, "억 달러"
    if sid.startswith(("QREV", "REV")):
        return 100, "억 달러"
    return 1, ""


def _when(m, q=False):
    y, mo = int(m[:4]), int(m[5:])
    return f"{y}년 {(mo - 1) // 3 + 1}분기" if q else f"{y}년 {mo}월"


def _fred_chart(x, title, q=False):
    """올해 vs 작년 같은 때 선 그래프 — 한국 업계 카드(_yoy_chart)와 같은 모양. 월 자료 12개월 · 분기 자료 4분기."""
    div, unit = _fred_scale(x["fred"])
    by = {r["month"]: r["v"] / div for r in x["series"]}
    pts = []
    for r in x["series"][-(4 if q else 12):]:
        prev = by.get(f"{int(r['month'][:4]) - 1}{r['month'][4:]}")
        if prev is not None:
            lab = f"{(int(r['month'][5:]) - 1) // 3 + 1}분기" if q else f"{int(r['month'][5:])}월"
            pts.append((lab, r["v"] / div, prev))
    if len(pts) < 2:
        return []
    fmt = lambda v: f"{v:,.1f}" if abs(v) < 100 else f"{v:,.0f}"   # noqa: E731
    chart = R.line_chart([p[0] for p in pts], [("올해", [p[1] for p in pts], R.LINE_THIS, False), ("작년 같은 때", [p[2] for p in pts], R.LINE_GRAY, True)], fmt, unit)
    return [(f'{_dk.CHART_TITLE_M}{_esc(title)}</span>{chart}', "html")]


def industry_cards(s):
    """미국 업계 카드 — `○○ 업계 생산은?` · `제품 값은?` · `수익성은?` (2026-11-01 사용자 P268: 한국처럼 방향까지). 재료 = industry_us.build."""
    d = s.get("industry_us")
    if not d:
        return ""
    out = ""
    for x in d["works"]:
        up = x["state"] in ("늘고 있음", "오르는 중")
        theme, col = ("neutral", R.MUTED) if x["state"] in ("판단 유보", "비슷함") else ("positive", R.UP) if up else ("negative", R.DOWN)
        q = x.get("quarterly", False)
        unit = "분기" if q else "달"
        head = f"{_dk.josa(x['name'], '은')} {_when(x['month'], q)} {_dk.josa(_fred_value(x['fred'], x['v']), '로')} 1년 전 같은 {unit}보다 {_sgn(x['chg'])}%였다."
        note = ("분기 자료라 2~3달 늦게 나옵니다." if q else "월별 자료라 1~2달 늦게 나옵니다.") + " 1년 전보다 5% 넘게 바뀌면 방향을 적습니다."   # 옛 툴팁 기준을 문장 작은 글씨로 (2026-11-08)
        lines = [(head + R.small_note(note), "plain")]
        lines += _fred_chart(x, f"{x['name']}, 올해와 작년 같은 {unit}", q=q)
        lines.append(("row", x["name"], _fred_value(x["fred"], x["v"]), f"{_when(x['month'], q)} · 1년 전보다 {_sgn(x['chg'])}%"))
        out += R._state_card(f"{x.get('biz', d['biz'])} 업계 {x['q']}", x["state"], theme, col, lines, "", fold=True)   # 툴팁 없음 (2026-11-08 사용자: 카드와 겹치는 툴팁 생략, 가이드라인 11절)
    m = d.get("money")
    if m:
        theme, col = {"나아짐": ("positive", R.UP), "나빠짐": ("negative", R.DOWN)}.get(m["state"], ("neutral", R.MUTED))
        head = f"{_dk.josa(m['name'], '은')} {_when(m['month'], True)} {_dk.josa(_fred_value(m['fred'], m['v']), '로')} 1년 전 같은 분기보다 {_sgn(m['chg'])}%였다."
        lines = [(head + R.small_note("분기 자료라 2~3달 늦게 나오고, 1년치로 환산한 금액입니다. 1년 전보다 10% 넘게 바뀌면 방향을 적습니다."), "plain")]
        lines += _fred_chart(m, f"{m['name']}, 올해와 작년 같은 분기", q=True)
        lines.append(("row", "업종 기업이익", _fred_value(m["fred"], m["v"]), f"{_when(m['month'], True)} · 1년 전보다 {_sgn(m['chg'])}%"))
        out += R._state_card(f"{d['biz']} 업계 수익성은?", m["state"], theme, col, lines, "", fold=True)
    return out


def sec_industry_tab(s):
    """`업계상황` 탭 (2026-10-31 사용자: 한국처럼 업종 이야기는 따로) — 업종 자금 카드(펼침) + 업계 카드(FRED, 2026-11-01 P268)."""
    sf = s.get("sector_flow")
    card = ""
    if sf:
        th, col = R.FLOW_THEME.get(sf["state"], ("neutral", R.MUTED))
        title = f"{sf['name']} 업계 자금 흐름은?"   # 옛 `○○ 업계 자금 흐름은?` — 앞날이 아니라 지난 20거래일, 회사 매출이 아니라 주식 쪽 돈 (2026-11-01 사용자 P198)
        card = R._state_card(title, sf["state"], th, col, sector_lines(sf), "", fold=True, opened=True)   # 툴팁 없음 — 근거 줄에 유입 · 유출 기준 · 순위가 있다 (2026-11-08 사용자: 카드와 겹치는 툴팁 생략, 가이드라인 11절)   # 탭 첫 강조 카드는 펼침 (P216)
    card += industry_cards(s)
    if not card:
        return _dk.muted("이 종목은 업계 자료를 아직 연결하지 않았습니다.")
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{card}</div>'


STATE_KO = {"CA": "캘리포니아", "WA": "워싱턴", "TX": "텍사스", "NY": "뉴욕", "MA": "매사추세츠", "IL": "일리노이", "NJ": "뉴저지", "GA": "조지아", "NC": "노스캐롤라이나",
            "VA": "버지니아", "OH": "오하이오", "MN": "미네소타", "CO": "콜로라도", "FL": "플로리다", "PA": "펜실베이니아", "MI": "미시간", "NV": "네바다", "AZ": "애리조나",
            "IN": "인디애나", "CT": "코네티컷", "MD": "메릴랜드", "TN": "테네시", "DE": "델라웨어", "WI": "위스콘신", "OR": "오리건"}


def _person(n):
    return re.sub(r"\s+", " ", re.sub(r"^(Mr|Ms|Mrs|Dr)\.\s*", "", n or "")).strip()


def sec_company(s):
    """`기업` 탭 (2026-10-31 사용자: 한국처럼 미국에도) — 소개(연차보고서로 직접 쓴 고정 문구, universe.ABOUT — 한국 universe_kr.ABOUT 와 같은 틀, 2026-11-01)
    + 기본 정보(야후 회사 개요). 평가 · 전망 · 추천 없음. 칸이 없으면 그 줄만 뺀다."""
    c = s.get("company") or {}
    about = U.ABOUT.get(s["sym"], "")
    intro = f'<p style="margin:0 0 12px;padding:0 {_dk.ALIGN_PX}px;color:#111;line-height:33px;word-break:keep-all;">{_esc(about)}</p>' if about else ""   # 한국 sec_company 와 같은 모양
    if not c.get("name"):
        return intro or _dk.muted("기업 정보를 아직 받지 못했습니다.")
    url = c.get("website") or ""
    url_short = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")   # f-string 밖에서 — Python 3.10 은 f-string 안 백슬래시를 못 읽는다
    place = " · ".join(x for x in (c.get("city"), STATE_KO.get(c.get("state"), c.get("state")) if c.get("country") == "United States" else c.get("country")) if x)
    rows = [("정식 이름", _esc(c["name"])), ("대표", _esc(_person(c.get("ceo")))), ("본사", _esc(place)),
            ("홈페이지", f'<a href="{_esc(url)}" style="color:inherit;text-decoration:none;" target="_blank" rel="nofollow noopener">{_esc(url_short)}</a>' if url else ""),
            ("직원", f"{c['employees']:,}명" if c.get("employees") else ""), ("결산", f"{c['fy_month']}월" if c.get("fy_month") else ""),
            ("상장", " · ".join(x for x in (_esc(c.get("exchange") or ""), f"티커 {s['sym']}", f"{c['listed']}년부터" if c.get("listed") else "") if x)),
            ("업종", _esc(U.BY_SYM[s["sym"]][3]) if s["sym"] in U.BY_SYM and len(U.BY_SYM[s["sym"]]) > 3 else "")]
    if s.get("rank"):
        rows.append(("시가총액", f"미국 {s['rank']}위 ({cap_text(s.get('cap'))})"))
    out = "".join(f'<span style="display:flex;gap:12px;padding:3px 12px;font-size:{_dk.TINY};line-height:22px;">'
                  f'<span style="flex:0 0 68px;color:{R.NOTE};white-space:nowrap;">{_esc(k)}</span>'
                  f'<span style="flex:1 1 auto;min-width:0;color:#111;word-break:keep-all;overflow-wrap:anywhere;">{v}</span></span>' for k, v in rows if v)   # 한국 _info_rows 와 같은 모양
    return intro + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}padding:{PAD - 3}px 0;display:block;">{out}</span></div>'


def sec_chart_indicators(s):
    """`지금 가격이 평균보다` 그래프 — 가격 카드 끝. `차트 정보 보기` 접기(S&P 500 대비 · 업종 ETF 대비 하루치)는 뺐다 (2026-10-31 사용자, 한국 P139 와 같게):
    S&P 500 대비는 하루 흐름 그래프 종가 막대와 같은 값, 업종 ETF 대비는 `업계 자금 흐름은?` 카드가 한 달 기준으로 같은 질문."""
    tc = s["tech"]
    return R.ma_chart(tc["ma_rel"], tc.get("bench_ma_rel"), s["name"], "S&P 500", last=True)   # 가격 카드 끝 — 흰 카드 아래 = 좌우 8px (한국 P140 과 같게)


def sec_drawdown(s):
    """고점 하락 후 가격 회복 — 이 종목과 S&P 500 (NVDA 리포트는 기술주 15개와 견준다). 숫자 = 절반은 이 거래일 안에 회복."""
    d = s.get("drawdown")
    if not d:
        return ""
    st, sp = d["stock"]["dd"], d["stock"]["spy_dd"]   # S&P 500 은 이 종목과 같은 기간
    span = R._span_label(d["stock"])
    cols = []
    for lv in ("10", "20", "30"):
        x, y = st.get(lv) or {}, sp.get(lv) or {}
        if not x.get("n") or x.get("median_days") is None:
            continue
        if x.get("recovered") and y.get("recovered"):
            cols.append((lv, x["over_year"] / x["recovered"] * 100, y["over_year"] / y["recovered"] * 100))
    tail = ""
    if cols:
        vb = "border-left:1px solid #E2E8F0;"
        cell = lambda txt, first=False: (f'<span style="flex:1 1 0;min-width:0;box-sizing:border-box;padding:0 8px;text-align:{"left" if first else "center"};{"" if first else vb}">{txt}</span>')   # noqa: E731
        tbl_head = cell(f'<span style="color:{DOWN};font-weight:700;">하락비율</span>', True) + "".join(cell(f'<span style="color:{DOWN};font-weight:700;">−{lv}%</span>') for lv, _, _ in cols)
        r1 = cell(_esc(s["name"]), True) + "".join(cell(f"{a:.0f}%") for _, a, _ in cols)
        r2 = cell("S&amp;P 500", True) + "".join(cell(f"{b:.0f}%") for _, _, b in cols)
        tbl = "".join(f'<span style="display:flex;align-items:stretch;line-height:24px;">{r}</span>' for r in (tbl_head, r1, r2))
        title = (f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:0 0 4px;">'
                 f'<span style="color:#111;font-weight:700;white-space:nowrap;">회복에 1년 넘게 걸린 비율</span></span>')   # `(약 30년 기간 중)` 은 뺐다 — 기간은 머리 작은 줄에 (2026-10-27 P17 · P24)
        tail = f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px;font-size:{TINY};color:{NOTE};">{title}{tbl}</span>'
    return R.dd_block(s["name"], st, sp, "S&P 500", span, d["pct_from_high"], "", tail)   # 툴팁 없음 — 머리 문장이 지금 구간 · 보통 회복 일수를 말한다 (2026-11-08 사용자: 카드와 겹치는 툴팁 생략, 가이드라인 11절)   # 영역 제목 없이 한 덩이 · 구간 막대 (2026-10-27 P24 · P28)


def related(s):
    """함께 보는 리포트 (가이드라인 10-5 4) — HTML 링크라 검색엔진이 따라간다."""
    links = [("미국 시가총액 상위 10개 종목 주가", U.LIST_URL)] + ([] if s["sym"] == "NVDA" else [("엔비디아 NVDA 주가", U.page_url("NVDA"))])   # 엔비디아도 고정 페이지 (2026-11-01 사용자)
    links.append(("주요 인물 발언 전체 보기", people_section.ALL_URL))   # 인물 발언 전체 목록 (2026-11-08 사용자) — 발언 카드 맨 아래 링크와 같은 주소
    return R.related_buttons(links)   # 전부 나가는 버튼 (2026-10-31 사용자 P160, 옛 점 글머리표 링크)


# ---------------------------------------------------------------- 애널리스트 · 탭 셋 (NVDA 리포트 build_body 와 같은 순서 · 같은 카드)

PEER_LABEL = "시총 상위 20개"
MAX_EVENTS = 8      # 뉴스 목록에 펼쳐 두는 수, 나머지는 `그 외 n건`
MAX_ISSUES = 5      # 중요 이슈 줄 수 (10-3 : 7일, 관련도 높은 순 최대 5줄)
MAX_MEDIA = 5       # 방송 줄 최대 수 — 실적 주간엔 한 종목에 하루 십여 줄이라 최근 것만 (2026-10-25)
NEWS = {}           # 이 실행의 분류된 기사 (write_all 이 채운다)
PICKS = []          # 방송에서 나온 종목 의견 (media_feed.picks, 최근 5거래일 PICK_SINCE) — `방송 의견은?` 카드 (2026-10-29 P89 · 11-04 P290)
BARS = {}           # 종목별 일봉 (snap["bars"]) — 의견 탭 맨 위 `최근 5거래일 의견과 주가` 종가 선 · 의견 창 (P290). write_all 이 채운다
PICK_SINCE = ""     # 방송 · 뉴스 의견 컷 (ISO UTC) = S&P 500 일봉 기준 최근 5거래일의 첫날 0시 뉴욕 (R.pick_window, P290)
NY = ZoneInfo("America/New_York")   # 의견 시각 → 미국 날짜 (종가 날짜와 같은 기준, P290)
MEDIA = []          # 방송 이슈 (media_feed.issues — 같은 이슈는 이미 한 줄로, 최근 24시간) — write_all 이 한 번 읽는다
TODAY_HOURS = 24    # 뉴스 목록 = 오늘자만 (2026-10-25 사용자). 아침 실행이라 KST 날짜로 자르면 미국 밤사이 뉴스가 빠진다 → 최근 24시간
NOW = None          # 페이지를 만드는 시각 (UTC) — write_all 이 정한다. 목업은 환경 변수 RADAR_NOW(ISO)


def _ts(iso):
    """'2026-10-24T22:15:00Z' · '+00:00' · 날짜만 → 비교용 'YYYY-MM-DDTHH:MM' (UTC)."""
    iso = str(iso or "")
    return iso[:16] if "T" in iso else iso[:10] + "T00:00"


def _since():
    return (NOW - datetime.timedelta(hours=TODAY_HOURS)).strftime("%Y-%m-%dT%H:%M")


def _rename(x, name):
    """NVDA 카드 함수의 글에서 `엔비디아` · `기술주 15개` 를 이 종목 · 비교 묶음으로 — 카드 판정 · 모양은 그대로 쓴다."""
    if isinstance(x, str):
        return x.replace("엔비디아", name).replace("기술주 15개", PEER_LABEL)
    if isinstance(x, (list, tuple)):
        return type(x)(_rename(v, name) for v in x)
    return x


def _sub_head(t):
    return f'<span style="display:block;margin:10px 0 6px;font-weight:700;color:#111;font-size:{_dk.NAME};">{R._esc(t)}</span>'


def _picks(s):
    return [p for p in PICKS if p["market"] == "US" and p["ticker"] == s["sym"]]


def card_opinions(s):
    """`애널리스트 의견은?` · `방송 의견은?` · 함께 보기 — 공용 R.opinions_cards (한국 · 미국 같은 카드, 2026-11-01 사용자 P197)."""
    ps = [p for p in PICKS if p["market"] == "US" and p["ticker"] == s["sym"]]
    return R.opinions_cards(s["name"], s.get("analysts") or [], s.get("close"), ps, lambda v: f"${v:,.2f}", lambda: together_items(s),
                            broker=s.get("broker") or [], news_ops=_news_opinions(s),
                            closes=[b["close"] for b in (BARS.get(s["sym"]) or [])[-R.PICK_SHOW_DAYS:]])   # 증권사 · 뉴스 의견 (P275) · 맨 위 요약 문단은 opinions_cards 안 (P295 · P296 주가 배경)


BROKER_TITLE_RE = re.compile(r"upgrade|downgrade|price target|target (cut|raised|lowered|bump)|initiat|reiterat|\brating\b", re.I)   # 증권사 등급 기사 = 증권사 카드와 같은 일


def _news_opinions(s):
    """`뉴스 의견은?` 재료 — 해설 · 투자 의견 기사(NVDA labels 의 의견 매체 · 의견형 제목) 중 이 종목 관련도 1 이상, 최근 5거래일(PICK_SINCE), 최신 먼저.
    주가 움직임만 다룬 기사 · 2차 출처(news_store._cap 의 나머지 조건)와 증권사 등급 기사는 뺀다."""
    import labels
    cut = _ts(PICK_SINCE)
    out = []
    for x in (NEWS or {}).values():
        sc = next((c for c in x.get("scores") or [] if c["ticker"] == s["sym"]), None)
        if not sc or sc["relevance"] < 1 or _ts(x["published_at"]) < cut or BROKER_TITLE_RE.search(x["title"]):
            continue
        src = (x.get("source") or "").lower()
        if not (any(p in src for p in labels.OPINION_PUBLISHERS) or labels.OPINION_TITLE_RE.search(x["title"])):
            continue
        out.append({"source": x.get("source") or "", "title": news_store.headline(x) or x.get("title_ko") or x["title"], "direction": sc["direction"],
                    "url": x.get("url"), "published_at": x["published_at"]})
    return sorted(out, key=lambda r: r["published_at"], reverse=True)


def sec_opinions(s):
    """`의견` 탭 (2026-11-01 사용자 P196 · P197, 한국과 같게) — `애널리스트 의견은?` · `방송 의견은?` 강조 카드 둘(접힌 채) + 함께 보기 흰 카드."""
    card = card_opinions(s)
    return card or _dk.muted("의견이 아직 없습니다.")   # 두 카드 격자 + 함께 보기는 R.opinions_cards 가 감싼다


def sec_earnings_tab(s):
    """`실적` 탭 (P196 · P197, 한국 sec_earnings_tab 과 같게) — 다음 실적 발표는?(펼침) → 실적 · 기대 카드 → `주요 일정` 제목 → 함께 보는 회사 일정 · 시장 일정."""
    # `다음 실적 발표는?` 도 `주요 일정` 제목 아래 첫 카드로 (2026-11-01 사용자 P251) — 탭 첫 카드 = 돈을 더 버나(펼침, P216)
    return (sec_expect(s) + R.group_title("주요 일정") + sec_calendar(s, ("earnings", "peers", "macro"), open_first=False, extra_cards=court_card(s)))


EPS_DIR = {"높아지는 중": 1, "낮아지는 중": -1, "그대로": 0}


def together_items(s):
    """`Alpha Scope 데이터로 함께 보기` 줄 — verdict_items 를 SG.ORDER(주가에 가까운 것부터) 순서로."""
    got = verdict_items(s)
    return {"items": [got[k] for k in SG.ORDER if got.get(k)], "news": _week_news(s), "sched": _sched(s)}   # 호재 · 리스크 · 앞둔 일정 (P218)


def _week_news(s):
    """최근 7일 이 종목 기사(관련도 1 이상) → 전망 카드 재료 (뉴스 · 방송 분위기 줄 · 호재 · 리스크). 오늘 탭 뉴스 방향 막대와 같은 기사."""
    if not NEWS:
        return []
    return [{"issue": x.get("issue"), "direction": sc["direction"], "title": news_store.headline(x) or x.get("fact") or x.get("title"), "url": x.get("url"),
             "published_at": x.get("published_at")} for x, sc in _news_for(s, NEWS)[1] if sc["relevance"] >= 1]


SCHED_DAYS = 30   # 앞둔 일정 = 30일 안 (P218)


def _sched(s):
    """앞둔 일정 — 이 종목 실적 · 가장 가까운 함께 보는 회사 실적 · 가장 가까운 시장 일정, 30일 안만. 줄 = (글, `n일 뒤`, 탭, 카드)."""
    cc, d0 = s.get("calendar_cards") or {}, datetime.date.fromisoformat(s["day"])
    left = lambda d: (datetime.date.fromisoformat(d) - d0).days   # noqa: E731
    out = []
    e = cc.get("earnings")
    if e and 0 <= e["left"] <= SCHED_DAYS:
        out.append((f"실적 발표 ({R._md_short(e['day'])})", f"{e['left']}일 뒤", "실적", "다음 실적 발표는?", "earn"))   # 다섯째 = 관련 기사 종류 (P265)
    up = [u for u in (cc.get("peers") or {}).get("upcoming_all") or (cc.get("peers") or {}).get("upcoming") or [] if left(u["day"]) <= SCHED_DAYS]
    if up:
        out.append((f"{U.peer_name(up[0]['symbol'])} 실적 발표 ({R._md_short(up[0]['day'])})", f"{left(up[0]['day'])}일 뒤", "실적", "함께 보는 회사 일정은?"))
    mu = (cc.get("macro") or {}).get("upcoming") or []
    if mu:
        nm = R.cal_cards.MACRO_KO.get(mu[0]["kind"], mu[0].get("label", ""))
        out.append((f"{nm} ({R._md_short(mu[0]['day'])})", f"{left(mu[0]['day'])}일 뒤", "실적", "시장 전체를 흔들 일정은?", mu[0]["kind"]))
    return out


def _industry_items(s):
    """업계 카드 판정 → 신호 카드 줄 (P268) — 일감 · 값 둘까지 + 수익성. 카드 제목과 같은 이름(`반도체 업계 생산`)."""
    d = s.get("industry_us") or {}
    out = {}
    for k, x in zip(("biz_work", "biz_work2"), d.get("works") or []):
        out[k] = SG.item(k, x["state"], biz=x.get("biz", d["biz"]), q=x["q"][:-2])
    if d.get("money"):
        out["biz_money"] = SG.item("biz_money", d["money"]["state"], biz=d["biz"])
    return out


def verdict_items(s):
    """`Alpha Scope 데이터로 함께 보기` 줄 (P142 → P172: 분류표 signal_groups 로 페이지의 모든 방향 판정). 순서 = SG.ORDER."""
    ex, tc = s.get("expect") or {}, s.get("tech") or {}
    sig, sf, mr, ms = tc.get("signals"), s.get("sector_flow"), s.get("market_regime"), s.get("market_shock") or {}
    got = {
        "ma": SG.ma_item(tc.get("ma_rel"), s["name"]),
        "tech": SG.item("tech", sig["word"]) if sig else None,
        "overheat": SG.overheat_item(s.get("overheat")),
        "revenue": SG.item("revenue", (ex.get("revenue") or {}).get("state")),
        "eps": SG.item("eps", (ex.get("eps") or {}).get("state")),
        "short": SG.item("short", (ex.get("short") or {}).get("state")),
        "sector_flow": SG.item("sector_flow", sf["state"], sector=sf["name"]) if sf else None,
        **_industry_items(s),
        "regime": SG.item("regime", mr["regime"], mkt="미국") if mr else None,
        "shock": SG.item("shock", "충격 국면 중") if ms.get("active") else None,
        "news": SG.news_item(_week_news(s)),   # 뉴스 · 방송 분위기 (P218)
        "analysts": SG.item("analysts", (R.analysts_verdict({"status": {"analysts": s.get("analysts") or []}, "headline": {"close": s.get("close")}}) or (None,))[0]),
        "picks": SG.item("picks", R.picks_word(_picks(s))) if _picks(s) else None,
        "broker": SG.item("broker", R.broker_word(s.get("broker") or [])),   # 증권사 목표가 변경 (2026-11-03 신호에 넣음)
        "news_ops": SG.item("news_ops", R.news_op_word(_news_opinions(s)) if NOW else None),   # 뉴스 의견
    }
    return got


def sec_targets(s):
    """옛 애널리스트 흰 카드 — card_opinions 로 합쳐 비운다 (P90)."""
    return ""


def _news_for(s, news):
    """이 종목 점수가 있는 분류된 기사 → NVDA 이벤트 모양. 관련도 1 이상, 7일 (목록은 _today_list 가 24시간으로 자른다)."""
    cut = (datetime.date.fromisoformat(s["day"]) - datetime.timedelta(days=7)).isoformat()
    out, counted = [], []
    for x in news.values():
        sc = next((c for c in x.get("scores") or [] if c["ticker"] == s["sym"]), None)
        if not sc or x["published_at"][:10] < cut:
            continue
        counted.append((x, sc))
        prio = x["area"] in R.config.PRIORITY_AREAS
        if not x.get("fact"):
            continue   # 사실 문장 검사에서 두 번 탈락한 기사 = 영문 원제를 그대로 싣게 되므로 뺀다. 방향 집계(counted)에는 남는다 (2026-10-21, 운영지침 D3-1f)
        if sc["relevance"] >= 1:   # 목록이 오늘자만이 된 뒤로 관련도 1(업종 맥락)도 싣는다 — `오늘 n건` 막대와 목록 기사 수를 맞춘다 (2026-10-25). 중요 이슈는 아래에서 2 이상만
            out.append({"area": x["area"], "kind": "news", "title": x["title"], "fact": x["fact"], "headline": news_store.headline(x), "detail": news_store.summary(x),   # 목록 헤드라인 = 원제 번역 · 요약 줄 (공용 뉴스 처리, 2026-10-25). 중요 이슈는 fact 그대로
                        "has_fact": True, "url": x.get("url"), "direction": sc["direction"], "issue": x.get("issue"),
                        "pop_key": x.get("item_id"), "pop_lines": SUMMARY.get(x.get("item_id")) or [], "pop_kind": "기사", "pop_source": x.get("source") or "",   # 요약 다섯 줄 팝업 (2026-11-07 사용자 P341)
                        "emphasis": sc["relevance"] >= 3 or prio, "source": x.get("source"), "published_at": x["published_at"], "rel": sc["relevance"], "prio": prio})
    for f in s.get("filings") or []:   # SEC 공시 — NVDA 리포트처럼 기사와 같은 목록에 (제목은 파이썬 규칙, AI 없음)
        if f["filed"] >= cut:
            out.append({"area": f["area"], "kind": "form4" if f["form"] == "4" else "8k", "title": f["title"], "fact": f["title"], "url": f["url"],
                        "direction": f["direction"], "emphasis": f["emphasis"], "source": "edgar", "published_at": f["at"], "rel": 0, "prio": False, "has_fact": False})
    out.sort(key=lambda e: e["published_at"], reverse=True)
    out.sort(key=lambda e: (not e["prio"], not e["emphasis"]))
    return out, counted


def _today_list(s, events):
    """뉴스 목록 = 최근 24시간 기사 · 공시 + 방송 줄. 방송 = 이 종목이 중심인 이슈 + 이 종목이 속한 업종 이슈 (media_feed.for_page, 2026-10-25 사용자).
    방송 줄은 중요 이슈에는 넣지 않는다 (의견 섞임). 정렬은 _news_for 그대로(법무 · 규제 → 강조 → 최근)."""
    since = _since()
    media = sorted(media_feed.for_page(MEDIA, s["sym"]), key=lambda r: str(r["published_at"]), reverse=True)[:MAX_MEDIA]   # MEDIA = 정리된 이슈(같은 이슈는 한 줄)
    today = [e for e in events if _ts(e["published_at"]) >= since] + [media_feed.event(r, _dk.n_channels_of(MEDIA)) for r in media]
    today.sort(key=lambda e: _ts(e["published_at"]), reverse=True)
    today.sort(key=lambda e: (not e["prio"], not e["emphasis"]))
    return today


def sec_crash(s, dc=None, src="Yahoo Finance"):
    """`주목할 종목` 구획 — `급락장에서 어땠나?` 카드 (2026-11-04 사용자: 홈 `주목할 종목` 줄을 누르면 이유 카드). 최근 두 거래일 안 급락일에 버틴 종목만, 사실만 —
    그날 등락 · 지수와 차이 · 최근 2년 급락일 n번 중 m번 · 그날 뉴스 방향 · 업종 자금 · 실적 일정. 왜 버텼는지는 단정하지 않는다(crash_watch). 한국(render_kr)도 같은 함수."""
    x = s.get("crash")
    if not x or not x.get("recent") or not x.get("held"):
        return ""
    first, lines = CW.card_lines(x, s["name"])
    lines = [(first, "plain")] + lines
    if dc is not None and x["day"] == x["latest_bar"]:   # 급락일이 최근 거래일이면 오늘 뉴스 방향(최근 24시간) — 아래 `뉴스` 막대와 같은 수
        parts = [f"{R.rr.DIR_KO[d]} {dc[d]}건" for d in ("positive", "negative", "uncertain", "neutral") if dc.get(d)]
        lines.append(("row", "그날 뉴스 방향", " · ".join(parts) if parts else "기사 없음", "최근 24시간 기사 · 공시 · 방송"))
    sf = s.get("sector_flow")
    if sf:
        lines.append(("row", "업종 자금 흐름", sf["state"], f"{sf['name']} 업종 ETF 최근 20거래일, 시장 대비"))
    nxt = (s.get("earnings") or {}).get("next")
    if nxt:
        gap = (datetime.date.fromisoformat(nxt) - datetime.date.fromisoformat(x["day"])).days
        if 0 <= gap <= 30:
            lines.append(("row", "실적 발표", f"{_md(nxt)} ({gap}일 뒤)", "급락일 기준"))
    card = R._state_card("급락장에서 어땠나?", "주목", "positive", R.UP, lines, "", tip=_dk.with_src(CW.tip(x), src), fold=True, opened=True)
    return R._section("주목할 종목", f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{card}</div>', tab="오늘")


def sec_today_tab(s, news):
    """오늘 탭 — (급락일이면 `주목할 종목` 카드) · 중요 이슈(파이썬 틀 : 관련도 높은 사실 문장 최대 5줄) · 뉴스(방향 막대 + 기사). AI 는 분류에만 쓴다."""
    if not news:   # 오늘 탭은 늘 둔다 — 없으면 가격 카드 · 상태 카드가 다음 탭(실적과 기대)으로 들어간다
        note = _dk.muted("뉴스를 아직 받지 못했습니다. 다음 갱신 때 채웁니다.")
        return sec_crash(s) + R._section("중요 이슈", note, tab="오늘") + R._section("뉴스", "", line=False, tab="오늘")
    events, counted = _news_for(s, news)
    since = _since()
    dc = {"today": {}, "week": {}}
    for x, sc in counted:
        if sc["relevance"] < 1:
            continue
        dc["week"][sc["direction"]] = dc["week"].get(sc["direction"], 0) + 1
        if _ts(x["published_at"]) >= since:   # `오늘` 막대 = 목록과 같은 최근 24시간 (2026-10-25)
            dc["today"][sc["direction"]] = dc["today"].get(sc["direction"], 0) + 1
    top = sorted((e for e in events if e["rel"] >= 2 and e["has_fact"]), key=lambda e: e["published_at"], reverse=True)
    top = sorted(top, key=lambda e: -e["rel"])[:MAX_ISSUES]   # 관련도 높은 순, 같으면 최근 순
    issues = [(f"{R.rr.AREA_KO.get(e['area'], e['area'])} {_dk.headline(e['fact'])}", e.get("url")) for e in top if e["has_fact"]]   # (글, 기사 주소) — 줄을 누르면 그 기사가 열린다 (2026-10-23 사용자)   # 명사형 헤드라인체 (데일리 · NVDA 중요 이슈와 같게)
    today = _today_list(s, events)
    a = {"events": today[:MAX_EVENTS], "events_overflow": today[MAX_EVENTS:MAX_EVENTS + 12], "direction_counts": dc}
    issue_html = R.sec_narrative(a, {"today": issues}) if issues else _dk.muted("최근 7일 동안 이 종목을 주로 다룬 큰 소식이 없습니다.")
    return sec_crash(s, dc["today"]) + _dk.keep_tone(R._section("중요 이슈", issue_html, tab="오늘")   # 뉴스 · 중요 이슈는 합니다체로 바꾸지 않는다 (2026-10-18 사용자)
                         + (R._section("뉴스", R.sec_direction_bars(dict(a, empty_text="오늘은 이 종목을 다룬 뉴스가 없습니다.")) + (R.sec_events(a) if today else ""), line=False, tab="오늘")
                            if today or sum(dc["week"].values()) else "")   # 최근 7일 뉴스가 없으면 구획 숨김 · 오늘 0건 안내 = 막대 자리, 아이콘 없음 (2026-11-08 사용자)
                         + sec_people(s))


def sec_people(s):
    """오늘 탭 뉴스 아래 — 최근 7일 이 종목을 지목한 인물 발언 3줄 + 접기 + 전체 보기 (2026-11-07 사용자). 없으면 구획을 뺀다."""
    body = people_section.for_stock(s["sym"])
    return R._section("인물 발언", body, line=False, tab="오늘") if body else ""   # `최근 7일` 뺌 — 줄마다 시각 (P369)


def _bil(v):
    """달러 → `1,234억 달러` (음수는 −). None 이면 `미수집` — 0 으로 적지 않는다 (운영지침, 2026-10-30)."""
    if v is None:
        return "미수집"
    if 0 < abs(v) < 0.5e8:   # 5천만 달러 아래는 `0억 달러` 로 보이지 않게 만 달러로 (ANET · HOOD 설비 투자, 2026-11-02 P280)
        return f"{round(v / 1e6) * 100:,}만 달러".replace("-", "−")
    return f"{v / 1e8:,.0f}억 달러".replace("-", "−")


US_MONEY = {   # 돈 카드의 나라별 글 — 한국 종목(render_kr)은 원 · DART 로 바꿔 넣는다 (2026-11-04)
    "money": _bil, "scale": 1e8, "unit": "억 달러", "fmt": lambda v: f"{v:,.0f}".replace("-", "−"),
    "src": "SEC", "form": "10-Q", "src_note": "회사가 SEC 에 낸 분기 · 연간 보고서", "stmt": "SEC 에 낸 현금흐름표", "data": "SEC EDGAR",
    "partial": "최근 분기 SEC 자료가 아직 없다", "rnd": True,   # rnd = 연구개발비 줄을 두나 (한국 주요 재무제표에는 없다)
}


def card_capex(c, L=US_MONEY):
    """돈을 어디에 쓰나? (2026-10-30 사용자: 기업별 자본 지출 · 자금 조달 현황) — 사실만, 판단 문장 없음. 출처 = 그 분기 10-Q · 10-K 색인 링크.
    첫 문장 = 최근 분기 설비 투자 · 1년 전 대비 · 영업으로 번 돈 대비 · 연구개발비. 그래프 = 8분기 설비 투자 vs 영업으로 번 돈(억 달러). 줄 = 최근 4분기 합.
    L = 통화 · 출처 글(US_MONEY, 한국은 render_kr.KR_MONEY) — 카드 모양 · 줄 · 툴팁은 두 나라가 같다."""
    M = L["money"]
    cap, ocf, rnd = c.get("capex"), c.get("ocf"), c.get("rnd")
    if cap is None:   # 은행 · 보험처럼 설비 투자 줄이 따로 없는 회사
        first = f"최근 분기({R._fd(c['end'])}까지 석 달) 현금흐름표에 설비 투자 항목이 따로 없다(은행 · 보험처럼 영업 자산이 다른 회사). 영업으로 번 돈은 {M(ocf)}였다."
    else:
        first = f"최근 분기({R._fd(c['end'])}까지 석 달) 설비 투자는 {M(cap)}"
        first += f"로 1년 전보다 {abs(c['capex_yoy']):.0f}% {'늘었다' if c['capex_yoy'] >= 0 else '줄었다'}." if c.get("capex_yoy") is not None else "다."
    if cap is not None and ocf:
        first += f" 같은 석 달 영업으로 번 돈 {M(ocf)}의 {cap / ocf * 100:.0f}%였다." if ocf > 0 else f" 같은 석 달 영업으로 번 돈은 {M(ocf)}였다."
    if rnd is not None:
        first += f" 연구개발비는 {M(rnd)}다."
    # 버튼으로 하나씩 보는 선 그래프 (2026-11-03 사용자) — 영업으로 번 돈 · 설비 투자 · 잉여 현금(= 잉여현금흐름, 음수는 0 선 아래). 설비 투자 줄 없는 회사(JPM)는 둘
    scale, fmt, unit = L["chart"]([b[k] for b in c["bars"] for k, _, _ in CASH_SERIES if b.get(k) is not None]) if L.get("chart") else (L["scale"], L["fmt"], L["unit"])
    ser = [(nm, [None if b.get(k) is None else b[k] / scale for b in c["bars"]], col) for k, nm, col in CASH_SERIES if any(b.get(k) is not None for b in c["bars"])]
    chart = line_tabs(f"lt-{c['sym']}-cash", [_dk.q_axis(b["cq"]) for b in c["bars"]], ser, fmt, unit)
    lines = [(first, "plain"), (f'{_dk.CHART_TITLE_M}분기 {" · ".join(nm for nm, _, _ in ser)} ({unit})</span>{chart}', "html")]
    sm, n4 = c["sum4"], c["n4"]
    tag = f"최근 {n4}분기 합" if n4 == 4 else "최근 4분기 없음"
    nil = L["partial"] if c.get("partial") else None   # Yahoo 로 더한 분기는 설비 투자 · 영업으로 번 돈뿐 (P280)
    if sm.get("capex") is not None:
        note = tag + (f" · 그 전 4분기보다 {R._sgn(c['chg4'], 0)}%" if c.get("chg4") is not None else "")
        if sm.get("ocf"):
            note += f" · 영업으로 번 돈의 {sm['capex'] / sm['ocf'] * 100:.0f}%"
        lines.append(("row", "설비 투자", M(sm["capex"]), note))
    else:
        lines.append(("row", "설비 투자", "미수집", "회사가 이 항목을 따로 적지 않았다"))
    # 현금 창출력 (2026-11-03 사용자: 매출 흐름 · 이익 흐름 · 현금 흐름 · 잉여현금흐름을 따로) — 영업으로 번 돈은 순이익과, 잉여현금흐름은 매출 성장과 나란히
    if sm.get("ocf") is not None:
        note = tag + (f" · 순이익 {M(sm['ni'])}의 {sm['ocf'] / sm['ni'] * 100:.0f}%" if sm.get("ni") and sm["ni"] > 0 and sm["ocf"] > 0 else "")   # 은행(JPM)은 영업현금흐름이 음수로 나오기도 — 비율 생략
        lines.append(("row", "영업으로 번 돈", M(sm["ocf"]), note))
    if sm.get("fcf") is not None:
        if c.get("fcf_chg4") is not None and sm["fcf"] > 0:
            note = tag + f" · 그 전 4분기보다 {R._sgn(c['fcf_chg4'], 0)}%"
        elif sm.get("fcf_prev") is not None:   # 부호가 바뀌면(AMZN 2026) 비율 대신 값으로
            note = tag + f" · 그 전 4분기는 {M(sm['fcf_prev'])}"
        else:
            note = tag
        if c.get("rev_chg4") is not None:
            note += f" (같은 기간 매출 {R._sgn(c['rev_chg4'], 0)}%)"
        lines.append(("row", "잉여현금흐름", M(sm["fcf"]), note))
    elif sm.get("capex") is None:
        lines.append(("row", "잉여현금흐름", "미수집", "설비 투자 줄이 없어 계산하지 않았다"))
    if L.get("rnd", True):
        lines.append(("row", "연구개발비", M(sm.get("rnd")), tag if sm.get("rnd") is not None else nil or "회사가 이 항목을 따로 적지 않았다"))
    if sm.get("debt_in") is not None or sm.get("debt_out") is not None:
        lines.append(("row", "빌린 돈 (채권 · 차입)", M(sm.get("debt_in")), tag + (f" · 갚은 돈 {M(sm['debt_out'])}" if sm.get("debt_out") is not None else "")))
    else:
        lines.append(("row", "빌린 돈 (채권 · 차입)", "미수집", nil or "이 기간 발행 · 상환을 따로 적지 않았다"))
    if sm.get("stock_in") and sm["stock_in"] > 0:   # 음수(세금 원천징수 차감 등)는 안 보인다
        lines.append(("row", "주식 발행으로 들어온 돈", M(sm["stock_in"]), tag))
    lines.append(("row", "자사주 매입", M(sm.get("buyback")), tag if sm.get("buyback") is not None else nil or "이 기간 매입을 따로 적지 않았다"))
    lines.append(("row", "배당", M(sm.get("div")), tag if sm.get("div") is not None else nil or "이 기간 배당을 따로 적지 않았다"))
    # 주주환원 여력 (2026-11-04 사용자: "배당과 자사주 매입 여력이 있는가") — 배당 + 자사주를 잉여현금흐름과 견준다. 사실만, 많다 · 적다 말 없음
    ret = [sm.get("div"), sm.get("buyback")]
    if any(v is not None for v in ret):
        tot, f4 = sum(v or 0 for v in ret), sm.get("fcf")
        note = tag + (f" · 잉여현금흐름의 {tot / f4 * 100:.0f}%" if f4 and f4 > 0 else " · 잉여현금흐름이 마이너스" if f4 is not None and f4 <= 0 else "")
        lines.append(("row", "주주에게 돌려준 돈 (배당 + 자사주)", M(tot), note))
    if sm.get("lease"):
        lines.append(("row", "금융리스 상환", M(sm["lease"]), tag + " · 리스로 들여온 설비의 원금"))
    if c.get("cash") is not None:
        lines.append(("row", "현금", M(c["cash"]), f"{R._fd(c['end'])} 기준"))
    if c.get("debt") is not None:
        lines.append(("row", "장기 부채", M(c["debt"]), f"{R._fd(c['end'])} 기준"))
    if c.get("src"):
        lines.append(("row", "출처", f'<a href="{_esc(c["src"])}" target="_blank" rel="noopener" style="color:inherit;">{L["src"]} {_esc(c.get("form") or L["form"])} ›</a>', L["src_note"], True))
    # 긴 용어 풀이 툴팁 (2026-11-03 사용자: "너무 헷갈리니 매출 · 순이익 · 영업으로 번 돈 · 잉여 현금 · 설비 투자 · 배당 · 현금을 예를 들어 아주 자세히") — 가이드라인 2-6 길이 규칙의 예외.
    # 예는 한 회사의 한 분기(억 달러)로 숫자를 이어 간다 : 매출 100 → 순이익 20 → 영업으로 번 돈 30 → 설비 투자 12 → 잉여 현금 18 → 배당 · 자사주 10 → 현금 잔액 58. 매출 카드 툴팁의 예와 같은 숫자
    tip = (f"회사가 번 돈을 어디에 쓰고, 모자란 돈을 어떻게 끌어오는지, 회사가 {L['stmt']} 그대로. 용어가 헷갈리기 쉬워 한 회사의 한 분기를 예로 든다({L['unit']})\n"
           "· 매출 : 석 달 동안 물건 · 서비스를 판 금액. 장부 기준이라 외상으로 팔아 아직 못 받은 돈도 들어간다. 예 100\n"
           "· 순이익 : 매출에서 원가 · 인건비 · 이자 · 세금 등 모든 비용을 뺀 장부상 이익. 예 매출 100에서 비용 80을 빼 20\n"
           "· 영업으로 번 돈 : 본업을 돌리며 실제로 통장에 들어온 현금에서 나간 현금을 뺀 것(영업현금흐름). 순이익과 다른 까닭은 장부와 현금이 다르기 때문. 공장 · 장비 값을 해마다 나눠 적는 감가상각은 장부 비용이지만 현금이 나가지 않아 다시 더하고, 외상 매출은 장부에는 있지만 현금이 안 들어와 뺀다. 예 순이익 20에 감가상각 10을 더해 30\n"
           "· 설비 투자 : 데이터 센터 · 공장 · 장비처럼 오래 쓰는 자산을 사는 데 쓴 돈(자본 지출). 사업을 이어 가려면 꼭 써야 하는 돈이라 영업으로 번 돈에서 먼저 뺀다. 리스로 들여온 설비는 여기에 안 들어가 `금융리스 상환` 줄을 따로 둔다. 예 12\n"
           "· 잉여 현금 : 영업으로 번 돈에서 설비 투자를 뺀 것(잉여현금흐름). 빚 갚기 · 배당 · 자사주 매입 · 새 사업에 자유롭게 쓸 수 있어 '남는 돈' 이라 부른다. 설비 투자가 번 돈보다 크면 마이너스가 되고 그래프에서 0 선 아래로 내려간다. 매출 성장률과 나란히 두면 외형만 크는지 현금 창출까지 느는지 보인다. 예 30에서 12를 빼 18\n"
           "· 배당 : 잉여 현금 가운데 주주에게 현금으로 나눠 준 돈. 자사주 매입은 회사가 자기 주식을 사들여 주식 수를 줄이는 것으로, 배당과 함께 주주에게 돌려주는 두 가지 방법. 예 배당 5 · 자사주 5\n"
           "· 주주에게 돌려준 돈 : 배당과 자사주 매입을 더한 것. 잉여 현금의 몇 % 인지가 돌려줄 여력. 100% 를 넘으면 그 기간 남은 돈보다 많이 돌려준 것이라, 모자란 만큼 현금 잔액이 줄거나 빌린 돈으로 메운다. 예 10, 잉여 현금 18의 56%\n"
           "· 현금 : 분기 말 회사 통장에 남아 있는 돈(잔액). 위 줄들은 석 달 동안 움직인 돈이고, 현금과 장기 부채는 그날의 잔액이라 서로 더하거나 빼지 않는다. 예 지난 분기 말 50에 잉여 현금 18을 더하고 배당 · 자사주 10을 빼 58\n"
           "· 빌린 돈 · 갚은 돈 : 채권을 찍거나 은행에서 빌린 돈과 갚은 돈. 잉여 현금이 모자라면 여기서 메우고, 남으면 갚는 데 쓴다\n"
           "· 순이익 대비 % : 영업으로 번 돈 줄의 비율. 100% 언저리면 장부 이익이 현금으로 잘 바뀌는 것, 훨씬 낮으면 외상이 쌓이거나 재고에 돈이 묶인 것\n"
           "· 그래프 : 왼쪽 위 버튼을 누르면 그 선만 색과 숫자가 보이고 나머지는 회색 선으로 남는다\n"
           "· 늘리는 중 · 줄이는 중 : 최근 4분기 설비 투자 합이 그 전 4분기 합보다 10% 넘게 많으면 늘리는 중, 10% 넘게 적으면 줄이는 중. 분기 값은 들쭉날쭉해 합으로 본다"
           + ("\n· 이 회사는 SEC 공용 자료에 빈 분기가 있어 설비 투자 · 영업으로 번 돈 일부를 Yahoo Finance 분기 현금흐름으로 채웠다. 4분기 합을 견줄 수 없으면 최근 분기를 1년 전 같은 분기와 비교한다" if c.get("yahoo") else ""))
    return lines, _dk.with_src(tip, f"{L['data']} · Yahoo Finance" if c.get("yahoo") else L["data"])   # P280


PROFIT_ROWS = (("gp", "매출총이익", "매출에서 만드는 데 든 돈을 뺀 몫"), ("opinc", "영업이익", "본업에서 남긴 돈"), ("ni", "순이익", "세금 · 이자까지 다 뺀 최종 이익"))
LT_GRAY = R.LT_GRAY   # 안 누른 선 (공용)
_S1, _S2, _S3 = _dk.CHART_SERIES   # 여러 계열 = 그래프 색 표 ⑤ 주황 · 청록 · 연보라 (가이드라인 8-0 · 0-5, 2026-11-06 사용자)
MARGIN_SERIES = (("gp", "매출총이익률", _S1), ("opinc", "영업이익률", _S2), ("ni", "순이익률", _S3))
CASH_SERIES = (("ocf", "영업으로 번 돈", _S1), ("capex", "설비 투자", _S2), ("fcf", "잉여 현금", _S3))


line_tabs = R.line_tabs   # 공용으로 옮김 (render_html, 2026-11-04 P294 — 의견 그림 · 한국 종목도 쓴다)


def margin_chart(ms, sym):
    """분기 이익률 버튼 선 그래프 (2026-11-03 사용자) — 매출총이익률 · 영업이익률 · 순이익률 (매출 대비 %), 회사가 안 적는 항목은 버튼 자체를 뺀다.
    금액이 아니라 % 인 까닭 = 매출 1,800억 옆에 순이익 200억을 두면 이익 선이 바닥에 붙는다."""
    ser = [(nm, [m.get(k) for m in ms], col) for k, nm, col in MARGIN_SERIES if any(m.get(k) is not None for m in ms)]
    chart = line_tabs(f"lt-{sym}-margin", [_dk.q_axis(m["cq"]) for m in ms], ser, lambda v: f"{v:,.0f}".replace("-", "−"), "%")
    return f'{_dk.CHART_TITLE_M}분기 이익률 (매출 대비 %)</span>{chart}' if chart else ""


def card_revenue(c):
    """NVDA 매출 카드 + 이익률 그래프 + 이익 줄 셋 (2026-11-03 사용자: 매출이 실제 이익으로 이어지나). 값 = 같은 분기 · 1년 전 대비 · 매출 대비 %. 안 적는 항목은 `미수집`."""
    lines, tip = R.card_revenue(c)
    p = c.get("profit")
    if not p:
        return lines, tip
    lines = list(lines)
    if c.get("margins"):
        html = margin_chart(c["margins"], c["sym"])
        if html:
            lines.insert(2, (html, "html"))   # 매출 그래프 바로 아래
    for k, name, mean in PROFIT_ROWS:
        x = p[k]
        if x["v"] is None:
            lines.append(("row", name, "미수집", "회사가 이 항목을 따로 적지 않았다"))
            continue
        note = f"매출의 {x['pct']:.0f}%" if x["pct"] is not None else mean
        note += f" · 1년 전보다 {R._sgn(x['yoy'], 0)}%" if x["yoy"] is not None else (" · 1년 전은 적자" if x["v"] > 0 else "")
        lines.append(("row", name, _bil(x["v"]), note))
    # 이익 줄 용어 풀이 — 돈 카드 툴팁과 같은 예(매출 100 → 순이익 20)로 이어진다 (2026-11-03 사용자: 예를 들어 자세히)
    tip = tip.replace("\n· 나누는 법", "\n· 매출 : 석 달 동안 물건 · 서비스를 판 금액. 장부 기준이라 외상으로 팔아 아직 못 받은 돈도 들어간다. 예 한 회사의 한 분기 100(억 달러)\n"
                      "· 매출총이익 : 매출에서 그 물건을 만드는 데 든 돈(원가)을 뺀 것. 제품 자체로 얼마나 남기는지. 예 100에서 원가 60을 빼 40, 매출의 40%\n"
                      "· 영업이익 : 매출총이익에서 인건비 · 광고 · 연구개발 같은 영업비를 뺀 것, 본업에서 남긴 돈. 예 40에서 15를 빼 25\n"
                      "· 순이익 : 영업이익에서 이자 · 세금까지 뺀 최종 이익. 예 25에서 5를 빼 20. 매출이 늘어도 이 줄들이 따라 늘지 않으면 외형만 커진 것. 실제 현금과는 다른데, 그 차이는 `돈을 어디에 쓰나?` 툴팁에\n"
                      "· 이익률 그래프 : 각 이익을 그 분기 매출로 나눈 %. 왼쪽 위 버튼을 누르면 그 선만 색과 숫자\n· 나누는 법", 1)
    return lines, tip


def sec_expect(s, open_first=True):
    """실적과 기대 탭 — NVDA 리포트 sec_expect 와 같은 질문 카드 넷 + 돈을 어디에 쓰나(2026-10-30). 비교 묶음 = 시총 상위 20개 (중앙값)."""
    ex = s.get("expect") or {}
    spec = [("회사는 돈을 더 벌고 있나?", "revenue", card_revenue), (R.EPS_TITLE, "eps", R.card_eps),
            ("시장 예상 흔들림은?", "move", R.card_move), ("하락에 거는 돈은?", "short", R.card_short), ("돈을 어디에 쓰나?", "capex", card_capex)]
    out = ""
    for i, (title, key, fn) in enumerate(spec):
        c = ex.get(key)
        if key == "capex" and not c:   # 외국 회사(TSM · ASML, 20-F) · 은행처럼 표가 없는 회사는 카드 자체를 안 둔다 — '다음 실행에서 다시' 가 아니다
            continue
        if c:
            lines, tip = _rename(fn(c), s["name"])
            state = c["state"]
        else:
            lines, tip, state = [("이번 실행에서 재료를 받지 못했다. 다음 실행에서 다시 받는다.", "plain")], "", "판단 유보"
        lines = list(lines)
        if key == "move" and s.get("options_status"):   # 옛 시장 지표 탭의 옵션 칸 — 접기(`자세한 지표 보기`) 없이 펼친 안에 (2026-11-01 사용자 P262, 한국 카드처럼)
            a = {"status": s["options_status"]}
            blk = R.status_block(a, "options", "옵션 지표")
            if blk:
                lines.append((blk, "html"))
        theme, col = R.EXPECT_THEME.get(state, ("neutral", R.MUTED))
        out += R._state_card(title, state, theme, col, lines, "", tip=tip, fold=True, opened=open_first and i == 0)
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>'


WHEN_KO = {"bmo": "장 시작 전", "amc": "장 마감 뒤"}


def cal_earnings(s, c):
    """NVDA cal_earnings 그대로 + 발표 시각 · 날짜 출처만 이 종목 값으로 (확정 · 추정 구분이 없는 Yahoo 일정)."""
    lines, tip, state, left = R.cal_earnings(dict(c, confirmed=True))
    when = WHEN_KO.get(c.get("when"))

    def fix(x):
        x = _rename(x, s["name"])
        if isinstance(x, str):
            x = x.replace("장 마감 뒤 · 회사 확정", (when + " · " if when else "") + "Yahoo Finance 일정")
            x = x.replace(" 장 마감 뒤로,", f" {when}로," if when else ",")
        return x
    return [tuple(fix(v) for v in ln) for ln in lines], fix(tip), state, left


ROLE_ORDER = ("고객", "공급", "협력", "경쟁", "동종", "유통", "보유")   # 동종 · 유통 : 2026-10-20 추가 종목 (같은 업종 회사 · 파는 곳)


def cal_peers(s, c):
    """함께 보는 회사 실적 — NVDA cal_peers 와 같은 비교(그 회사 발표 다음 날 이 종목 vs 이 종목 보통 날), 회사 목록은 종목마다 정한 것(universe.PEERS).
    옛 카드 밖 `전체 일정 보기` 범위(LIST_DAYS 60일)까지 카드 안에 (2026-11-01 사용자 P197, 한국과 같게)."""
    up, nm, roles = c.get("upcoming_all") or c["upcoming"], s["name"], c["roles"]
    days = R.cal_cards.LIST_DAYS
    kinds = " · ".join(r for r in ROLE_ORDER if r in roles.values())
    what = "큰 보유 종목" if kinds == "보유" else f"{kinds} 회사"
    if not up:
        return [(f"앞으로 {days}일 안에 실적을 발표하는 {nm}의 {what}가 없다.", "plain")], "", "없음", None
    names = [f"{U.peer_name(u['symbol'])}({R._md_short(u['day'])})" for u in up]
    syms = [x for x in dict.fromkeys(u["symbol"] for u in up) if c["effect"].get(x, {}).get("median")]
    soon = " · ".join(r for r in ROLE_ORDER if r in {roles.get(u["symbol"]) for u in up})   # 기간 안에 발표하는 회사의 관계만
    first = f"앞으로 {days}일 안에 {_dk.josa(' · '.join(names), '가')} 실적을 발표한다. {nm}의 {'큰 보유 종목' if soon == '보유' else soon + ' 회사'}다."
    if syms:
        eff = [c["effect"][x]["median"] for x in syms]
        rng = f"±{min(eff):.1f}%" if f"{min(eff):.1f}" == f"{max(eff):.1f}" else f"±{min(eff):.1f}~{max(eff):.1f}%"
        who = "이 회사들의" if len(syms) > 1 else "이 회사의"
        first += f" 최근 2년 {who} 발표 다음 날 {nm} 주가는 보통 {rng} 움직였다({nm} 보통 날 ±{c['normal']:.1f}%)."
    lines = [(first, "plain")]
    if syms:
        chart = R._chart_card([(U.peer_name(x), [c["effect"][x]["median"], c["normal"]]) for x in syms], [lambda v: R._AMBER, R._gray], [R._note_fg, R._note_fg],
                              [(f"그 회사 발표 다음 날 {nm}", R._AMBER), (f"{nm} 보통 날", R._GRAY_BAR)], fmt=lambda v: f"±{v:.1f}")
        lines.append((f'{_dk.CHART_TITLE_M}발표 다음 날 {_esc(nm)} 움직임 (%)</span>{chart}', "html"))
    for u in up:
        e = c["effect"].get(u["symbol"]) or {}
        lines.append(("row", f"{U.peer_name(u['symbol'])} ({u['symbol']})", R._md_short(u["day"]),
                      roles.get(u["symbol"], "") + (f" · 다음 날 {nm} 보통 ±{e['median']:.1f}% ({e['n']}번)" if e.get("median") else "")))
    left = (datetime.date.fromisoformat(up[0]["day"]) - datetime.date.fromisoformat(s["day"])).days
    return lines, "", f"{len(up)}곳", left   # 툴팁 없음 — 문장이 고객 · 공급 · 경쟁 회사와 일정을 말한다 (2026-11-08 사용자: 카드와 겹치는 툴팁 생략, 가이드라인 11절)


def cal_macro(c):
    """시장 전체 일정 — 가장 가까운 1~2개만 한 줄로, 전체는 미국 증시 리포트 `일정` 탭으로 (2026-10-31 사용자 P144: 모든 종목에 같은 공통 정보는
    공통 정보 보는 곳으로). 엔비디아 리포트는 R.cal_macro(전체 카드) 그대로. 링크는 발행 때 최신 글로 바뀐다(publish_pages.DAILY_LATEST)."""
    up = c["upcoming"]
    link = R.out_btn("미국 증시 리포트 일정에서 전체 보기", f"{U.DAILY_REPORTS_URL}#tab-일정")   # 나가는 버튼 (P148)
    if not up:
        return [("앞으로 30일 안에 잡힌 큰 경제 일정이 없다.", "plain"), (link, "html")], "", "없음", None
    name = lambda u: R.cal_cards.MACRO_KO.get(u["kind"], u["label"])   # noqa: E731
    near = " · ".join(f"{name(u)}({R._md_short(u['day'])})" for u in up[:2])
    first = f"가장 가까운 큰 일정은 {near}이다." + (f" 30일 안에 모두 {len(up)}건이 있다." if len(up) > 2 else "")
    return [(first, "plain"), (link, "html")], "", f"{len(up)}건", None   # 툴팁 없음 (2026-11-08 사용자: 카드와 겹치는 툴팁 생략, 가이드라인 11절)


def sec_calendar(s, keys=("earnings", "peers", "macro"), open_first=True, extra_cards=""):
    """일정 카드 — NVDA 리포트 sec_calendar 와 같은 질문 카드(실적 · 같은 업종 실적 · 시장 일정). 소송 카드는 extra_cards (court_card, P270).
    옛 `일정` 탭, 지금은 `실적` 탭 안(sec_earnings_tab, P196) — keys 로 고른 카드만. 카드 밖 `전체 일정 보기` 는 없앴다(P197, 함께 보는 회사 카드 안으로)."""
    cc = s.get("calendar_cards") or {}
    specs = [("다음 실적 발표는?", "earnings", lambda c: cal_earnings(s, c)), ("함께 보는 회사 일정은?", "peers", lambda c: cal_peers(s, c)),   # 360px 한 줄 (P163, 옛 P156 실적 일정은?)
             ("시장 전체를 흔들 일정은?", "macro", cal_macro)]
    out, first = "", open_first
    for title, key, fn in specs:
        c = cc.get(key)
        if key not in keys or not c:
            continue
        lines, tip, state, extra = fn(c)
        theme, col = R._soon_theme(extra)
        out += R._state_card(_josa(title), state, theme, col, lines, "", tip=_josa(tip), fold=True, opened=first)
        first = False
    out += extra_cards
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>' if out else ""


def _josa(t):
    """`○○와(과)` → 받침에 맞는 조사 하나 (이름 끝 글자 기준, 영문 · 숫자는 `와`)."""
    def pick(m):
        ch = m.group(1)
        has = "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 != 0
        return ch + ("과" if has else "와")
    return re.sub(r"(.)와\(과\)", pick, t)


def detail_body(s, today, news=None):
    """NVDA 리포트 순서 : 맨 위 요약 → 그래프 → 가격 카드(펼치면 1층 · 2층) → 상태 카드. 갱신 날짜 줄은 뺐다 — 요약 첫 마디에 날짜가 있다 (2026-10-18 사용자)."""
    return wrap(_dk.report_stamp(_md(s["day"]) + "(미국 시간)", "한국 시간 아침 7시 30분 무렵") + lead(s) + sec_chart(s) + R.day_path_chart(s["tech"].get("path"), s["tech"].get("bench_path"), s["name"], "S&P 500") + price_card(s, today) + sec_regime(s) + sec_tech(s) + sec_pairs(s) + sec_states(s) + sec_targets(s)
                + sec_today_tab(s, news or {})
                + R._section("매수의견", sec_opinions(s), tab="매수의견")   # 애널리스트 · 방송 의견 — 오늘 탭에서 옮김 (2026-11-01 사용자 P196) · 탭 이름 붙여 쓴 `매수의견` (P203)
                + R._section("실적", sec_earnings_tab(s), tab="실적")   # 옛 `일정` 탭을 합침 (P196)
                + R._section("업계상황", sec_industry_tab(s), tab="업계상황")   # 한국과 같은 탭 (2026-10-31 사용자)
                + R._section("기업", sec_company(s), tab="기업")   # 한국과 같은 탭 (2026-10-31 사용자)
                + related(s) + list_marker(U.LIST_URL))   # 출처 · 투자 권유 꼬리말은 뺐다 — 블로그 공통 푸터가 맡는다 (2026-10-18 사용자)


# ---------------------------------------------------------------- 소송 일정 (P270)

COURT = {}   # court.json — 추적 사건의 법원 일정 (write_all 이 채운다)


def court_card(s):
    """진행 중 소송 일정은? — 추적하는 증권 소송(court_watch.json)이 있고 잡힌 법원 일정이 있는 종목만. 엔비디아 리포트 cal_court 그대로 (2026-11-01 사용자 P270)."""
    c = court.card(s["sym"], s["day"], COURT)
    if not c:
        return ""
    lines, tip, state, (theme, col) = R.cal_court(c)
    return R._state_card("진행 중 소송 일정은?", state, theme, col, _rename(lines, s["name"]), "", tip=_rename(tip, s["name"]), fold=True)


# ---------------------------------------------------------------- 목록

def list_lead(a):
    top = [s for s in a["stocks"] if s["in_top"]]
    up = sum(1 for s in top if s["ret_1d"] > 0)
    first = top[0]
    text = (f"{_md(a['day'])} 종가 기준 미국 시가총액 1위는 {first['name']}({first['sym']}), {cap_text(first['cap'])}이다. "
            f"상위 10개 중 {up}개가 오르고 {len(top) - up}개가 내렸다.")
    return f'<p data-seo-lead="1" style="{_dk.SEO_LEAD}">{_esc(text)}</p>'


def detail_url(s):
    return U.NVDA_REPORTS_URL if s["sym"] in U.REPORT_TYPE else U.page_url(s["sym"])


def list_row(s, first):
    r = s["ret_1d"]
    pcol = UP if r > 0 else DOWN if r < 0 else "#111"
    left = (f'<span style="display:inline-block;width:26px;color:{NOTE};font-weight:700;">{s["rank"]}</span>{_dk.ticker_logo(s["sym"])}'
            f'<a href="{_esc(detail_url(s))}" style="color:#111;text-decoration:none;">{_esc(s["name"])}</a>'
            f'<span style="display:block;padding-left:52px;font-size:{_dk.MICRO};line-height:20px;font-weight:400;color:{NOTE};">{_esc(s["sym"])} · {cap_text(s["cap"])}</span>')   # 순위 26 + 로고 26 만큼 들여 이름 글자에 맞춘다
    right = f'<span style="color:{pcol};">${s["close"]:,.2f}</span><br>{R._arrow(r)}'
    # 줄 전체가 상세로 가는 터치 영역 — 테마 터치 장치가 [data-row-link] 를 읽는다 (2026-10-19 사용자: 이름만이 아니라 한 행을 터치)
    return R._row_html(left, right, first=first).replace("<span", f'<span data-row-link="1" data-ret="{r:.4f}"', 1)


def list_body(a):
    top = [s for s in a["stocks"] if s["in_top"]]
    rest = [s for s in a["stocks"] if not s["in_top"] and s.get("rank") and s["rank"] <= U.PEER_GROUP_N]   # 목록은 시총 상위 20위까지 — 48개 확대 뒤에도 같은 목록 (2026-10-20)
    card = lambda xs, key="": f'<div data-cards="1" style="margin:0 0 8px;"><span{f" data-sort-list={chr(34)}{key}{chr(34)}" if key else ""} style="{R.MULTI}">{"".join(list_row(s, i == 0) for i, s in enumerate(xs))}</span></div>'   # noqa: E731   key = 정렬 버튼이 다시 놓는 목록 (P93)
    tip = ("미국 S&P 500 종목 가운데 회사 전체 값(주가 × 주식 수)이 가장 큰 10개\n"
           f"· 오늘 1위 : {top[0]['name']} {cap_text(top[0]['cap'])}\n"
           f"· 나누는 법 : 11위 밖으로 {U.SWAP_DAYS}거래일 연속 밀리면 후보 중 가장 높았던 종목과 바꾼다")
    body = (_dk.report_stamp(_md(a["day"]) + "(미국 시간)", "한국 시간 아침 7시 30분 무렵")   # 맨 위 안내 상자 = 상세 페이지와 같게 (2026-11-07 0-1, 옛 `마지막 갱신` 회색 한 줄)
            + list_lead(a) + R.title_with_sort("시가총액 순위", tip, "us-cap10") + card(top, "us-cap10")
            + _dk.fold(f"후보 11~{len(top) + len(rest)}위 보기", card(rest))
            + _dk.muted("종목 이름을 누르면 상세 페이지로 갑니다.")
            + R.related_buttons([("엔비디아 NVDA 주가", U.page_url("NVDA"))]))   # 함께 보는 페이지 — 한국 목록 · 상세 페이지처럼 (2026-11-07)
    return wrap(body + home_marker())


SUMMARY = {}   # 기사 요약 다섯 줄 {item_id: [줄]} — data/news_summaries.json (news_summary 캐시, 상태 브랜치 radar/ 에 남는다)
SUMMARY_PATH = os.path.join(_HERE, "data", "news_summaries.json")
SUMMARY_MAX = 40   # 하루 새로 요약하는 기사 상한 — Groq 하루 토큰 보호 (2026-11-07 P341, CLAUDE.md 한도 표)


def summarize_shown(a, news):
    """목록에 실리는 기사(최근 24시간 · 관련도 1 이상 · 사실 문장 있음)만 요약 — 이미 요약한 기사는 캐시. 실패해도 페이지는 나간다(요약 줄 하나 + 원문)."""
    import news_summary
    seen, items = set(), []
    since = _since()
    for s in a["stocks"]:
        for e in _news_for(s, news)[0]:
            k = e.get("pop_key")
            if e["kind"] == "news" and k and k not in seen and _ts(e["published_at"]) >= since:
                seen.add(k)
                items.append({"item_id": k, "title": e["title"], "url": e.get("url"), "snippet": e.get("detail") or ""})
    try:
        news_summary.summarize(items, cache_path=SUMMARY_PATH, lead_cache=os.path.join(_HERE, "data", "leads.json"), label="radar-summary", max_items=SUMMARY_MAX)
    except Exception as e:  # noqa: BLE001
        print(f"[radar] 기사 요약 실패 — 요약 줄 하나로 : {str(e)[:100]}")
    print(f"[radar] 팝업 대상 기사 {len(items)}건")


def write_all(a, out_dir, snap=None, news=None, media=None, summarize=False):
    os.makedirs(out_dir, exist_ok=True)
    global SUMMARY
    global MEDIA, NOW, NEWS, COURT
    COURT = court.load()   # 그날 court.fetch() 가 쓴 것 (main) — 없으면 소송 카드 없이
    NEWS = news or {}   # 전망 카드 뉴스 · 방송 분위기 · 호재 · 리스크 (P218)
    NOW = (datetime.datetime.fromisoformat(os.environ["RADAR_NOW"].replace("Z", "+00:00")) if os.environ.get("RADAR_NOW")
           else datetime.datetime.now(datetime.timezone.utc))
    global PICKS, BARS, PICK_SINCE
    BARS = (snap or {}).get("bars") or {}
    PICK_SINCE = R.pick_window(BARS.get(U.BENCH) or [], NY, now=NOW)[1]   # 의견 창 = S&P 500 최근 5거래일 (P290)
    if media is None:   # 영상은 한 번(30일) 읽어 뉴스(24시간) · 방송 의견(5일)에 나눠 쓴다 — Firestore `in` 30개 한도
        vids = media_feed.load(NOW.astimezone(media_feed.KST).strftime("%Y-%m-%d"), days=R.PICK_DAYS - 1)
        media = media_feed.issues(media_feed.rows(vids), _since())
        PICKS = media_feed.picks(vids, PICK_SINCE)   # 최근 5거래일 (2026-11-04 P290, 옛 48시간 10-31)
    MEDIA = media
    if summarize and news:
        summarize_shown(a, news)
    try:
        import news_summary
        SUMMARY = {k: v["lines"] for k, v in news_summary._load(SUMMARY_PATH).items()}
    except Exception:  # noqa: BLE001
        SUMMARY = {}
    if snap:
        draw_charts(snap, [s for s in a["stocks"] if s["sym"] not in U.REPORT_TYPE], out_dir)
    pages = {"list": (U.LIST_TITLE, list_body(a))}
    for s in a["stocks"]:
        if s["sym"] not in U.REPORT_TYPE:
            pages[s["sym"]] = (U.page_title(s["sym"]), detail_body(s, a["day"], news))
    for key, (title, body) in pages.items():
        with open(os.path.join(out_dir, f"{key}.html"), "w", encoding="utf-8") as f:
            f.write(body)
        _dk.write_mock(body, os.path.join(out_dir, f"mock_{key}.html"), title)
    return pages
