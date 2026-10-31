"""한국 종목 페이지 · 목록 페이지 HTML (기획 11-4). 미국 간단형 상세(stock-radar/render_pages.py)의 틀을 따르되
원화 · KOSPI 비교 · 미국 연결 짝 카드(맨 위) · 자금 흐름(목록 페이지) 로 바꾸고, 옵션 · 공시 · 애널리스트 · 뉴스 · 실적 칸은 두지 않는다.
카드 조각(_row_html · _col_chart · _state_card …)은 엔비디아 리포트 렌더러(R)를 그대로 쓴다. 툴팁은 뜻 · 오늘 · 기록상 세 줄 — `기록상` 은 2026-10-24~25 검증(doc/검증/한국-*.md) 결과만,
관계가 없던 것은 "관계 없음" 을 그대로 적는다. 2026-10-25 밤: 기획 11-8 후보(K1~K30 중 자료 있는 것)를 전부 넣은 상태 — 사용자가 보고 뺀다.
"""
import datetime
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "nvda-report"))
import design_kit as _dk  # noqa: E402
import chart_price as CP  # noqa: E402
import render_html as R  # noqa: E402
import universe_kr as U  # noqa: E402
sys.path.insert(0, os.path.join(_HERE, "..", "stock-radar"))
import universe as USU  # noqa: E402 — 미국 종목 주소(함께 보는 페이지의 연결 짝 링크)
import media_feed  # noqa: E402 — 방송 뉴스 (`오늘` 탭)
import re  # noqa: E402
from collections import Counter  # noqa: E402
from html import unescape as html_unescape  # noqa: E402
import analyze_tabs as AT  # noqa: E402 — 미국 종목 `실적과 기대` 판정(card_revenue · card_eps)을 그대로 — stock-radar

UP, DOWN, NOTE, TINY = _dk.UP, _dk.DOWN, _dk.NOTE, _dk.TINY
PAD = _dk.SEP_GAP - _dk.VP - 1
IMAGE_BRANCH = "kr-images"   # 한국 종목 그래프 전용 휘발성 브랜치 — 미국(radar-images)과 따로. 두 워크플로가 각자 그날 그림만으로 force push 하므로 같은 브랜치를 쓰면 서로 지운다
SRC = "한국은행 ECOS (자료: 한국거래소 · 금융투자협회)"


def _row_html(left_html, right_html, note="", **kw):
    """R._row_html 과 같고 보조 줄(note)의 증감에 색 — 이미 태그가 든 보조 줄은 그대로 (2026-10-26 사용자: "증감 표현에 있는 모든 정보는 증감 컬러", 리포트 M6)."""
    return R._row_html(left_html, right_html, _dk.tint(note) if note and "<" not in note else note, **kw)


def _esc(t):
    return _dk.esc(t)


def _md(d):
    d = datetime.date.fromisoformat(str(d)[:10])
    return f"{d.month}월 {d.day}일"


def _sgn(v, digits=1):
    if round(v, digits) == 0:   # 0 은 부호 없이 — `−0.0%p` 가 증감 색으로 칠해지지 않게 (2026-10-26 리포트 M9)
        return f"{0:.{digits}f}"
    return f"{v:+.{digits}f}".replace("-", "−")


def won(v, digits=0):
    """원화 — 천 단위 쉼표, 소수 없음. 예 215,500원."""
    return f"{v:,.{digits}f}원"


def cap_text(c):
    """시가총액 → `1,403조 원` · `9,800억 원`."""
    if not c:
        return "—"
    if c >= 1e12:
        return f"{c / 1e12:,.0f}조 원" if c >= 1e13 else f"{c / 1e12:.1f}조 원"
    return f"{c / 1e8:,.0f}억 원"


def eok(v):
    """억원 값(ECOS 일별) → `9,778억 원` · `27.2조 원`."""
    a = abs(v)
    return f"{a / 1e4:.1f}조 원" if a >= 1e4 else f"{a:,.0f}억 원"


def badge(sym, size=20):
    """종목 이름 앞 둥근 로고 — 우리 gh-pages 사본(ref/ticker_logos.json 의 005930.KS 등, 운영지침 4-6)이 있으면 로고,
    없으면 한글 첫 글자 배지 (2026-10-25 사용자: "한국 기업의 티커 로고도 제대로 나오게")."""
    if sym in _dk._logo_files():
        return _dk.ticker_logo(sym, size)
    ch = U.name(sym)[:1]
    fs = max(8, int(size * 0.5))
    return (f'<span aria-hidden="true" style="display:inline-block;width:{size}px;height:{size}px;line-height:{size}px;border-radius:50%;'
            f'vertical-align:-4px;margin-right:6px;background:#E2E8F0;color:#334155;font-size:{fs}px;font-weight:700;text-align:center;'
            f'white-space:nowrap;overflow:hidden;">{_esc(ch)}</span>')


def wrap(body):
    html = _dk.align_titles(_dk.WRAP_OPEN + body + _dk.WRAP_CLOSE)
    return _dk.formal(_dk.fix_colons(html))


def list_marker(url):
    return f'<span data-list-url="{_esc(url)}" data-nav="back" hidden></span>'   # data-nav=back : 홈에서 왔으면 `홈으로`, 아니면 `목록으로` (2026-10-29 사용자 P94)


def home_marker():
    """글 아래 버튼을 늘 `홈으로` (목록 · 읽는 법 페이지, 2026-10-29 사용자 P94). 화면에는 안 보인다."""
    return '<span data-nav="home" hidden></span>'


# ---------------------------------------------------------------- 그래프

def chart_ref(sym):
    return f"radar-{U.BY_SYM[sym][2]}-price.png"


def chart_url(sym):
    return f"https://cdn.jsdelivr.net/gh/{CP._repo_slug()}@{IMAGE_BRANCH}/images/{chart_ref(sym)}"


def sec_chart(s):
    if not s.get("chart"):
        return ""
    url = chart_url(s["sym"])
    zoom = ('<svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">'
            '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5 14 14M7 5v4M5 7h4"/></svg>')
    return (f'<a href="{_esc(url)}" data-zoom="1" target="_blank" rel="noopener" title="그래프 확대 보기" aria-label="그래프 확대 보기" '
            f'style="position:relative;display:block;margin:0 0 16px;max-width:1024px;">'
            f'<img src="{_esc(url)}" alt="{_esc(s["name"])} {CP.WINDOW}거래일 봉차트" style="width:100%;display:block;border:1px solid #eee;border-radius:8px;"/>'
            f'<span style="position:absolute;right:8px;bottom:8px;display:flex;align-items:center;justify-content:center;width:32px;height:32px;'
            f'background:rgba(255,255,255,.92);border:1px solid #E2E8F0;border-radius:8px;color:#111;">{zoom}</span></a>')


def draw_charts(snap, stocks, out_dir):
    for s in stocks:
        bars = [dict(b, open=b["open"] if b.get("open") else b["close"]) for b in (snap["bars"].get(s["sym"]) or [])][-(CP.WINDOW + CP.LOOKBACK):]
        if len(bars) < 2:
            continue
        CP.draw(bars, os.path.join(out_dir, "images", chart_ref(s["sym"])), s["code"])
        s["chart"] = True


# ---------------------------------------------------------------- 상세

def lead(s):
    """맨 위 요약 (p[data-seo-lead]) — 날짜 · 종가 · 전일 대비 · 평소 범위만. 파이썬 값만.
    (2026-10-25 사용자: 종목 코드 숫자 · 매일 같은 `시가총액 1위` · 처음부터 애플 · 엔비디아 이야기는 뺀다 — 이 종목을 보러 온 독자에게 이 종목 가격이 먼저)"""
    r = s["ret_1d"]
    move = f"전날보다 {abs(r):.2f}% {'올랐다' if r > 0 else '내렸다'}" if abs(r) >= 0.005 else "전날과 같았다"
    text = f"{_md(s['day'])} {s['name']} 종가는 {won(s['close'])}으로 {move}."
    nr = s.get("normal_range")
    if nr:
        text += " 평소 하루 움직임 안의 변화였다." if abs(nr["z"]) < 2 else f" 평소 하루 움직임의 {abs(nr['z']):.1f}배였다."
    text += R.gap_sentence((s.get("tech") or {}).get("gap"))   # 시가 갭 상승 · 하락 (2026-10-28 사용자 P80)
    return f'<p data-seo-lead="1" style="{_dk.SEO_LEAD}">{_dk.tint(_esc(text))}</p>'


def _small(t):
    return f'<span style="font-size:{_dk.MICRO};font-weight:400;color:{NOTE};">{t}</span>'


def pair_tip(s):
    p = s["pairs"]
    why = p.get("why") or ""
    lines = ["이 종목과 같은 재료로 움직이는 미국 종목(과 같은 회사의 미국 상장 ADR). 미국 종가는 한국 장이 열리기 전(한국 시간 새벽)에 나오므로 '밤사이' 미국 움직임 뒤 오늘 한국장의 반응을 나란히 둔다"]
    if why and p.get("moves"):
        lines.append(f"· 연결 이유 : {why}")
    rec = U.PAIR_RECORD.get(s["sym"])
    if rec and p.get("moves"):
        sp, n, ok, y0 = rec
        if ok:
            lines.append(f"· 기록상 : 연결 종목이 밤사이 많이 오른 날(상위 25%)과 많이 내린 날(하위 25%)의 다음날 {s['name']} 수익 차이는 KOSPI 대비 평균 {_sgn(sp, 2)}%p 였다 ({y0}~2026, {n:,}거래일, 플라시보 · 앞뒤 절반 · 보정 통과). {U.GAP_NOTE}")
        else:
            lines.append(f"· 기록상 : {y0}~2026 {n:,}거래일에서 연결 종목의 밤사이 움직임과 다음날 {s['name']} 사이에 뚜렷한 관계가 없었다 (차이 {_sgn(sp, 2)}%p) — 참고로만 둔다")
    adr = p.get("adr")
    if adr and adr["sym"] in U.ADR_RECORD:
        sp, n, y0 = U.ADR_RECORD[adr["sym"]]
        lines.append(f"· 기록상 (ADR) : {adr['sym']} 가 밤사이 많이 오른 날과 내린 날의 다음날 {s['name']} 수익 차이 {_sgn(sp, 2)}%p ({y0}~2026, {n:,}거래일, 통과) — 같은 회사라 연결 종목보다 직접적이다. 역시 시가에 반영")
    if p.get("sox"):
        sp, n, tgt = U.OVERNIGHT_RECORD["SOX_SEMI"]
        lines.append(f"· 기록상 (SOX) : 필라델피아 반도체지수가 밤사이 많이 오른 날과 내린 날의 다음날 {tgt} 수익 차이 {_sgn(sp, 2)}%p (2000~2026, {n:,}거래일, 통과)")
    return "\n".join(lines)


def _us_name(sym):
    return USU.name(sym) if sym in USU.BY_SYM else sym


def _pair_bars(groups, note=""):
    """밤사이 미국 · 오늘 한국 세로 막대 (2026-10-27 사용자 P31: "세로 막대, 길면 넘겨 보기" — P27 가로 막대를 바꿈). 공용 _col_chart 한 시리즈,
    막대마다 색 — 미국 연결은 오름 빨강 · 내림 파랑, 이 종목은 진하게, KOSPI 회색. 두 묶음은 같은 간격으로 이어 그린다(P57). 가로축 이름 아래 줄 = 연결 이유.
    흰 카드 폭은 상태 카드 안 다른 막대(_zone_gauge)와 같다."""
    cols, kinds = [], []
    for _, rows in groups:   # 두 묶음 사이 빈 칸은 뺐다 — 모든 막대 같은 간격 (2026-10-28 사용자 P57)
        for nm, sub, v, kind in rows:
            cols.append((nm + (f"\n{sub}" if sub else ""), [v]))
            kinds.append(kind)

    def color_at(i, k, v):
        kind = kinds[i]
        if kind == "bench":
            return R._GRAY_BAR, NOTE
        bg = R._PASTEL_UP if v >= 0 else R._PASTEL_DN
        return (_dk.darken(bg, 0.2) if kind == "me" else bg), (UP if v > 0 else DOWN if v < 0 else "#111")
    chart = R._col_chart(cols, [R._sign_bg], [R._sign_fg], fmt=lambda v: f"{v:+.1f}".replace("-", "−"), color_at=color_at)
    title = " → ".join(g for g, _ in groups)
    tail = f'<span style="display:block;margin:6px 0 0;font-size:{TINY};line-height:20px;color:{NOTE};word-break:keep-all;">{_esc(note)}</span>' if note else ""
    return (f'<span style="display:block;margin:0 0 8px;font-weight:700;color:#111;font-size:{_dk.NAME};">{_dk.CHART_MARK}{R._paren(_esc(title + " (%)"))}</span>'
            f'<span style="{R.MULTI}margin:0 {_dk.CHART_CARD_X - 2}px;"><span style="display:block;padding:{_dk.CHART_CARD_PAD}px 12px 0;">{chart}</span></span>{tail}')


def _mates(s, n=6):
    """같은 테마(없으면 같은 업종)의 한국 종목 — 기업 탭 `같은 묶음` 과 같은 규칙 (P153: 오늘 탭 함께 움직이는 종목 카드로)."""
    mates = [x for x in U.CANDIDATES if x[0] != s["sym"] and set(x[4]) & set(U.groups(s["sym"]))] or [x for x in U.CANDIDATES if x[0] != s["sym"] and x[3] == U.sector(s["sym"])]
    return mates[:n]


def sec_pairs(s, a=None):
    """`미국과 연결` 펼침 카드 (2026-10-25 사용자: "짝" 대신 "연결" · 가격 카드 다음 · 펼침 카드로). 접힌 머리 = 밤사이 연결 종목이 어땠나(올랐음 · 내렸음 · 엇갈림),
    펼치면 연결 종목 · ADR(K24) · SOX(K25) 줄과 오늘 이 종목 · KOSPI 대비, 한국 장 뒤 나온 미국 종가. 툴팁 `기록상` = 10-25 일별 검증."""
    p = s.get("pairs") or {}
    moves = p.get("moves") or []
    adr, sox = p.get("adr"), p.get("sox")
    if not moves and not adr and not sox:
        return ""
    rets = [m["ret"] for m in moves] + ([adr["ret"]] if adr else [])
    ups, downs = sum(1 for x in rets if x >= 0.5), sum(1 for x in rets if x <= -0.5)
    state, theme, col = (("엇갈림", "uncertain", R.SOON) if ups and downs else ("올랐음", "positive", UP) if ups else ("내렸음", "negative", DOWN) if downs
                         else ("비슷함", "neutral", R.MUTED))
    day = (moves or [adr or sox])[0]["day"]
    lines = [(f"밤사이(미국 {_md(day)} 종가) 연결 종목은 " + " · ".join(f"{_us_name(m['sym'])} {_sgn(m['ret'])}%" for m in moves)
              + f", 오늘 {_dk.josa(s['name'], '은')} {_sgn(s['ret_1d'])}%였다.", "plain")]
    # 숫자 줄 목록 → 가운데 0 가로 막대 두 묶음 (2026-10-27 사용자 P27: "퍼센트만 쭉 있어 빨리 안 읽힌다, 삼성전자 · 지수와 비교 그래프")
    why = [w.strip() for w in (p.get("why") or "").split("·")]
    role = dict(zip([m["sym"] for m in moves], why)) if len(why) == len(moves) else {}   # 이유가 종목 수와 맞을 때만 나눠 붙인다 — `마이크론 · 메모리`
    us = [(_us_name(m["sym"]), role.get(m["sym"], ""), m["ret"], "us") for m in moves]
    if adr:
        us.append((adr["sym"], "같은 회사 ADR", adr["ret"], "us"))
    if sox:
        us.append(("SOX", "반도체지수", sox["ret"], "us"))
    kr = [(s["name"], "", s["ret_1d"], "me")]
    vb = s["tech"].get("vs_bench")
    if vb is not None:
        kr.append(("KOSPI", "", s["ret_1d"] - vb, "bench"))
    # `그 뒤 미국 종가 … 다음 한국장 전 참고` 줄은 뺐다 — 정기 실행(16:10 KST)엔 그 미국장이 아직 안 끝나 늦게 돌 때만 나오고, 무슨 값인지 읽히지 않았다 (2026-10-28 사용자 P58)
    lines.append((_pair_bars([(f"밤사이 미국 ({_md(day)} 종가)", us), (f"오늘 한국 ({_md(s['day'])})", kr)]), "html"))
    # 같은 묶음 한국 종목의 오늘 등락 — 미국 부분과 같은 막대 (2026-10-31 사용자 P153: 제목 `함께 움직이는 종목은?`, 기업 탭의 `함께 움직이는 종목` 을 여기로)
    by = {x["sym"]: x for x in (a or {}).get("stocks") or []}
    group = [(x[1], "", by[x[0]]["ret_1d"], "us") for x in _mates(s) if x[0] in by and by[x[0]].get("ret_1d") is not None]
    if group:
        lines.append((_pair_bars([(f"같은 묶음 한국 종목 ({_md(s['day'])})", group)]), "html"))
    return R._state_card("함께 움직이는 종목은?", state, theme, col, lines, "", tip=pair_tip(s), fold=True)   # 답은 밤사이 미국 기준 그대로(검증 통과한 신호)


IND_SRC = {"derived": "한국은행 금리 통계", "121Y006": "한국은행 대출금리", "121Y002": "한국은행 수신금리", "151Y002": "한국은행 가계대출", "901Y054": "은행연합회 연체율", "402Y016": "한국은행 수출물가지수", "901Y039": "국가데이터처 광공업 생산", "901Y019": "한국전력공사", "901Y073": "한국석유공사", "901Y072": "에너지경제연구원",
           "901Y020": "국가데이터처 건설수주", "901Y105": "국가데이터처 주택건설인허가", "901Y074": "국가데이터처 미분양주택", "901Y149": "한국부동산원", "601Y003": "한국은행 신용카드"}


def _ind_value(r):
    v, kind = r["v"], r["kind"]
    if kind == "idx":
        return f"{v:.1f}"
    if kind == "cnt":
        return f"{v:,.0f}호"
    if kind == "won_m":
        return f"{v / 1e6:,.1f}조 원" if abs(v) >= 1e6 else f"{v / 1e2:,.0f}억 원"   # 1조 아래는 억 원 (발전설비 수주, 2026-10-31)
    if kind == "usd":
        return f"{v / 1e8:,.1f}억 달러"   # 관세청 수출금액 (방산, 2026-10-31)
    if kind == "won_b":
        return f"{v / 1e3:,.0f}조 원"
    if kind == "pct":
        return f"{v:.2f}%"
    if kind == "mwh":
        return f"{v / 1e4:,.0f}만 MWh"
    if kind == "kbbl":
        return f"{v / 1e3:,.1f}백만 배럴"
    if kind == "ktoe":
        return f"{v / 1e3:,.1f}백만 TOE"
    if kind == "ton":
        return f"{v / 1e4:,.1f}만 톤"
    return f"{v:,.0f}"


def sec_industry(s):
    """업종 재료는? — 이 종목의 테마 · 업종에 닿는 월별 실물 지표 (ECOS). 재료가 쌓이는지 보는 칸이지 전망이 아니다 (기획 11-4, 2026-10-24 사용자)."""
    rows_data = s.get("industry") or []
    if not rows_data:
        return ""
    rows = ""
    for i, r in enumerate(rows_data):
        mo = f"{r['month'][:4]}년 {int(r['month'][5:])}월"
        cmp_txt = "전년 같은 달보다" if r["cmp"] == "yoy" else "전달보다"
        unit = "%p" if r["kind"] == "pct" else "%"
        chg = f'<br><span style="font-size:{TINY};font-weight:400;color:{UP if r["chg"] > 0 else DOWN if r["chg"] < 0 else NOTE};">{_sgn(r["chg"], 2 if unit == "%p" else 1)}{unit}</span>' if r.get("chg") is not None else ""
        note = f"{mo} · {cmp_txt} {_sgn(r['chg'], 2 if unit == '%p' else 1)}{unit} · 12개월 범위의 {r['pos12']:.0f}% 지점" if r.get("chg") is not None else f"{mo} · 12개월 범위의 {r['pos12']:.0f}% 지점"
        if r.get("note"):
            note += f" · {r['note']}"
        rows += _row_html(r["name"], f'<span style="color:#111;">{_ind_value(r)}</span>{chg}', note, first=i == 0)
    # K14 환율 (수출형 · 수입 원료형 · 일본 경쟁 업종) · K21 WTI (한국전력) — 값만. 검증에서 이후 주가와 관계 없음 / WTI 는 다음날 한전과 관계 있음(시가 반영)
    fx = s.get("fx") or {}
    fx_keys = []
    if s.get("trade_tag") in ("수출형", "수입 원료형"):
        fx_keys.append(("usdkrw", "원/달러", "오르면 원화 약세 · 수출 대금은 늘고 수입 원가는 오른다"))
    if s["sym"] in U.JPY_COMPETE:
        fx_keys.append(("jpykrw100", "원/100엔", "일본 경쟁 업종 — 오르면 엔 대비 원화 약세"))
    for k, n, note in fx_keys:
        x = fx.get(k)
        if not x:
            continue
        d1 = x.get("chg_1d")
        right = f'<span style="color:#111;">{x["v"]:,.1f}원</span>' + (f'<br><span style="font-size:{TINY};font-weight:400;color:{UP if d1 > 0 else DOWN if d1 < 0 else NOTE};">{_sgn(d1, 1)}원</span>' if d1 is not None else "")
        rows += _row_html(n, right, f"{_md(x['day'])} · {note} · 1년 {x['lo_1y']:,.0f}~{x['hi_1y']:,.0f}원 · 기록상 이후 주가와 관계 없음(값만)")
    w = s.get("wti")
    if w:
        d1 = w.get("chg_1d")
        right = f'<span style="color:#111;">{w["v"]:.1f}달러</span>' + (f'<br><span style="font-size:{TINY};font-weight:400;color:{UP if d1 > 0 else DOWN if d1 < 0 else NOTE};">{_sgn(d1, 1)}%</span>' if d1 is not None else "")
        sp, n, y0 = U.WTI_RECORD
        rows += _row_html("WTI 유가", right, f"{_md(w['day'])} · 20일 {_sgn(w['chg_n'], 1)}% · 1년 {w['lo_1y']:.0f}~{w['hi_1y']:.0f}달러 · 기록상 많이 오른 날과 내린 날의 다음날 {s['name']} 차이 {_sgn(sp, 2)}%p ({y0}~2026)")
    rec = []
    for r in rows_data:
        v = U.VALIDATED_LEAD.get(r["key"])
        if v:
            if v["months"] == 0:
                rec.append(f"· 기록상 : {v['basket']} 주가와 {r['name']}은 같은 달에 움직였다 ({v['period']}, 상관 {v['corr']:.2f}) — 동행 확인용")
            else:
                rec.append(f"· 기록상 : {v['basket']} 주가가 {r['name']}보다 약 {v['months']}개월 먼저 움직였다 ({v['period']}, 상관 {v['corr']:.2f})"
                           + (f" · {U.DOWNTURN_NOTE[r['key']]}" if r["key"] in U.DOWNTURN_NOTE else "") + " — 이 숫자는 확인용이지 예고가 아니다")
        if r["key"] in U.CONTRA_NOTE:
            rec.append(f"· 기록상 (역행) : {U.CONTRA_NOTE[r['key']]}")
    srcs = sorted({IND_SRC.get(r["src_stat"], "한국은행 ECOS") for r in rows_data})
    first = rows_data[0]
    tag = s.get("trade_tag")
    tip = ("이 종목이 속한 업종의 실물 숫자 — 단가 · 수요 · 물량이 쌓이는지 본다. 월별 자료라 1~2달 늦게 나오고, 주가는 이보다 먼저 움직이곤 한다 (전망 아님)\n"
           f"· {first['name']} {_ind_value(first)} : " + (f"{'전년 같은 달' if first['cmp'] == 'yoy' else '전달'}보다 {_sgn(first['chg'], 2 if first['kind'] == 'pct' else 1)}{'%p' if first['kind'] == 'pct' else '%'}" if first.get("chg") is not None else "비교값 없음")
           + (f"\n· 분류 : {tag} — 환율 · 교역조건 · 수출입물가 · 수출 물량은 값만 둔다 ({U.NO_RECORD['fx_stock']})" if tag and (fx_keys or w) else "")
           + ("\n" + "\n".join(rec) if rec else "\n· 기록상 : 1996~2026 우리 검증에서 이 업종 지표는 발표 뒤 주가와 뚜렷한 관계를 보이지 않았다 — 참고 숫자"))
    return R._card_title("업계 재료는?", _dk.with_src(tip, "한국은행 ECOS (자료: " + " · ".join(srcs) + ")" + (" · FRED" if w else ""))) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


def sec_bsi(s):
    """K1~K6 업종 체감 경기 — 업종별 BSI 실적(값) · 전망(작은 글씨), 역대 백분위. 툴팁 `기록상` = 시차(K3) · 약한 후보(K4) · 바닥권 사후 검증(K5) · 역행(K6)."""
    b = s.get("bsi")
    if not b or not b.get("rows"):
        return ""
    rows = ""
    for i, r in enumerate(b["rows"]):
        mo = f"{r['month'][:4]}년 {int(r['month'][5:])}월"
        fc = f'<br><span style="font-size:{TINY};font-weight:400;color:{NOTE};">다음 달 전망 {r["forecast"]:.0f}</span>' if r.get("forecast") is not None else ""
        col = UP if r["v"] >= 100 else "#111"
        note = f"{mo} 실적 · 전달보다 {_sgn(r['chg'], 0)}p · 12개월 범위의 {r['pos12']:.0f}% 지점 · 2009년 이후 아래에서 {r['pct_all']:.0f}% 지점"
        rows += _row_html(f"{r['name']} BSI", f'<span style="color:{col};">{r["v"]:.0f}</span>{fc}', note, first=i == 0)
    rec = b.get("record") or {}
    lines = []
    if rec.get("lead"):
        lines.append(f"· 기록상 : {rec['lead']} — 확인용이지 예고가 아니다")
    if rec.get("contra"):
        lines.append(f"· 기록상 (역행) : {rec['contra']}")
    if rec.get("weak"):
        lines.append(f"· 참고 : {rec['weak']}")
    bt = rec.get("bottom")
    bottom_now = False
    if bt:
        row = next((r for r in b["rows"] if bt["item"] in (r["item"], r.get("f_item"))), None)
        cur = (row.get("forecast_pct_all") if bt["kind"] == "전망" else row.get("pct_all")) if row else None
        bottom_now = cur is not None and cur <= 25
        state = f"지금 {row['name']} {bt['kind']}은 역대 아래에서 {cur:.0f}% 지점 — " + ("하위 25% 안" if bottom_now else "하위 25% 밖") if cur is not None else ""
        lines.append(f"· 기록상 (사후 검증) : {b['industry_name']} {row['name'] if row else ''} {bt['kind']} BSI 가 역대 하위 25% 였던 달 뒤 {bt['h']}개월, 이 업종 묶음은 KOSPI 보다 평균 {_sgn(bt['spread'], 1)}%p 였다 "
                     f"(2009~2026, 다중 검정 보정 뒤 q {bt['q']:.3f}, 앞뒤 절반 같은 방향). 결과를 보고 세운 가설이라 새 자료로 다시 확인해야 한다. {state}")
    if not lines:
        lines.append("· 기록상 : 2009~2026 우리 검증에서 이 업종 BSI 는 발표 뒤 주가와 뚜렷한 관계를 보이지 않았다 — 참고 숫자")
    f0 = b["rows"][0]
    tip = ("한국은행이 매달 기업에 업황 · 매출 · 신규수주 · 채산성이 좋은지 나쁜지 물어 만든 지수(100 기준, 보통 100 아래). 실적은 이달 답, 전망은 다음 달 답. 실물 지표보다 1~2달 빠르다\n"
           f"· {b['industry_name']} {f0['name']} {f0['v']:.0f} : 전달보다 {_sgn(f0['chg'], 0)}p, 2009년 이후 아래에서 {f0['pct_all']:.0f}% 지점\n" + "\n".join(lines))
    head = _dk.muted(f"{b['industry_name']} 업종 · 역대 하위 25% 안 (사후 검증 기록은 설명 참고)") if bottom_now else ""
    return R._card_title("업종 체감 경기는? (BSI)", _dk.with_src(tip, "한국은행 ECOS 기업경기조사")) + head + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


def sec_fin(s):
    """K10 업종 분기 기업경영분석 · K15 산업별 대출 — 값만. 미검증(분기 46개 · 대출은 후행)."""
    xs = s.get("fin") or []
    if not xs:
        return ""
    rows = ""
    for i, r in enumerate(xs):
        if r["unit"] == "조 원":
            val = f"{r['v'] / 1e3:,.0f}조 원"
        else:
            val = f"{r['v']:.1f}%"
        chg = f'<br><span style="font-size:{TINY};font-weight:400;color:{UP if r["chg"] > 0 else DOWN if r["chg"] < 0 else NOTE};">{_sgn(r["chg"], 1)}{r["chg_unit"]}</span>' if r.get("chg") is not None else ""
        rng = (f"{r['lo4'] / 1e3:,.0f}~{r['hi4'] / 1e3:,.0f}조" if r["unit"] == "조 원" else f"{r['lo4']:.1f}~{r['hi4']:.1f}%").replace("-", "−")
        note = f"{_qlabel(r['q'])}" + (f" · 전년 같은 분기보다 {_sgn(r['chg'], 1)}{r['chg_unit']}" if r.get("chg") is not None else "") + f" · 최근 4분기 {rng} · {r['note']}"
        rows += _row_html(r["name"], f'<span style="color:#111;">{val}</span>{chg}', note, first=i == 0)
    f0 = xs[0]
    tip = ("업종 전체 회사들의 재무(한국은행 기업경영분석 — 설문이 아니라 실제 집계)와 그 업종이 은행에서 빌린 돈. 분기 끝 2~3달 뒤에 나와 종목 실적보다 늦다\n"
           f"· {f0['name']} {f0['v']:.1f}{'%' if f0['unit'] != '조 원' else ''} : {_qlabel(f0['q'])}" + (f", 전년 같은 분기보다 {_sgn(f0['chg'], 1)}{f0['chg_unit']}" if f0.get("chg") is not None else "") + "\n"
           "· 기록상 : 미검증 — 분기 자료가 2015년부터 46개뿐이라 수익 검증은 표본이 부족하고, 대출은 경기에 늦게 따라오는 지표로 알려져 있다. 시설자금이 늘면 투자 · 증설, 운전자금만 늘고 매출이 나쁘면 버티기 차입 쪽으로 읽히곤 한다 — 판정하지 않고 숫자만 둔다")
    return R._card_title("업종 재무 · 대출은? (분기)", _dk.with_src(tip, "한국은행 ECOS (기업경영분석 · 예금은행 산업별 대출)")) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


# ---------------------------------------------------------------- `업종` 탭 = 독자 질문 카드 셋 (2026-10-25 사용자: "수치는 펼침 안으로, 이 수치가 무슨 역할인지 재해석")
# 접힌 머리 = 질문 + 한 단어 답(지난 값과 비교한 사실, 앞날 아님), 펼치면 한 문장 · 그래프(작년 같은 때와 나란히 — 가이드라인 1-4-1 비교 대상) · 수치 줄.
# 기록상 · 출처는 질문 옆 ? 툴팁 — 옛 sec_industry · sec_bsi · sec_fin 의 툴팁 그대로.

_THIS, _LAST = "#9CC0F2", R._GRAY_BAR   # 올해 막대 · 작년 같은 때 막대


def _yoy_groups(series, key, label, n=6):
    """마지막 n 개 시점마다 (이름, [올해 값, 작년 같은 때 값]) — 작년 값이 없는 시점은 뺀다."""
    by = {x[key]: x["v"] for x in series}
    out = []
    for x in series[-n:]:
        prev = by.get(f"{int(x[key][:4]) - 1}{x[key][4:]}")
        if prev is not None:
            out.append((label(x[key]), [x["v"], prev]))
    return out[::-1]   # 최신이 왼쪽 — 넘겨 보기는 오른쪽(과거)으로 (2026-10-28 사용자 P79, 위 봉차트는 그대로)


LINE_THIS = "#5B8DEF"   # 선 그래프 이 종목(올해) 선 — 그래프 비교 목업에서 정한 파랑 (P161)


def _yoy_chart(title, groups, fmt, unit="", now="올해", then="작년 같은 때"):
    """올해 vs 작년 같은 때 — 선 그래프 (2026-10-31 사용자 P161: 업계 상황 탭부터, 옛 막대 최신 왼쪽). groups = _yoy_groups(최신이 앞) 그대로 받아 뒤집는다."""
    if not groups:
        return []
    gs = groups[::-1]   # 오래된 것 → 최신
    chart = R.line_chart([g for g, _ in gs], [(now, [v[0] for _, v in gs], LINE_THIS, False), (then, [v[1] for _, v in gs], R.LINE_GRAY, True)], fmt, unit)
    return [(f'{_dk.CHART_TITLE_M}{_esc(title)}</span>{chart}', "html")]


def _tip_of(html):
    """옛 칸(sec_industry · sec_bsi · sec_fin)의 ? 툴팁 글과 출처를 그대로 가져온다 — 기록상 · 출처 글을 한 곳에서만 쓰게."""
    t, src = re.search(r'data-tip="([^"]*)"', html), re.search(r'data-src="([^"]*)"', html)
    return _dk.with_src(html_unescape(t.group(1)), html_unescape(src.group(1))) if t and src else (html_unescape(t.group(1)) if t else "")


def _mo(m):
    return f"{int(m[5:])}월"


def _chart_unit(kind):
    """그래프 숫자는 짧게 — 단위는 그래프 제목에."""
    return {"won_m": (1e6, "조 원"), "won_b": (1e3, "조 원"), "mwh": (1e4, "만 MWh"), "kbbl": (1e3, "백만 배럴"), "ktoe": (1e3, "백만 TOE"), "ton": (1e4, "만 톤"),
            "cnt": (1, "호"), "pct": (1, "%"), "idx": (1, ""), "usd": (1e8, "억 달러")}.get(kind, (1, ""))


def _fin_short(s, name):
    """`기계 · 전기 · 전자 매출액 영업이익률` → `매출액 영업이익률` — 기업경영분석 업종 이름만 뗀다(다른 분류인 대출 잔액 이름은 그대로, P68)."""
    ind = U.fin_industry(s["sym"])[1]
    return name[len(ind) + 1:] if ind and name.startswith(ind + " ") else name


def card_industry_mood(s):
    """이 업종 경기는 좋아지고 있나? — 한국은행 기업경기조사(BSI) 업황 실적. 답 = 석 달 전보다 3p 넘게 오르면 좋아지는 중, 내리면 나빠지는 중."""
    b = s.get("bsi")
    if not b or not b.get("rows"):
        return ""
    f0 = b["rows"][0]
    ser = f0.get("series") or []
    d3 = f0["v"] - ser[-4]["v"] if len(ser) >= 4 else f0.get("chg") or 0
    state, theme, col = (("좋아지는 중", "positive", UP) if d3 >= 3 else ("나빠지는 중", "negative", DOWN) if d3 <= -3 else ("비슷함", "neutral", R.MUTED))
    v0 = f"{f0['v']:.0f}"
    lines = [(f"{b['industry_name']} 회사들이 느끼는 {f0['name']} 경기(BSI)는 {_dk.josa(v0, '로')} 석 달 전보다 {_sgn(d3, 0)}p, "
              f"2009년 이후 아래에서 {f0['pct_all']:.0f}% 지점이다." + R.small_note("100보다 낮으면 나쁘다고 답한 회사가 더 많다는 뜻입니다."), "plain")]   # 늘 같은 안내는 작은 글씨 (P67)
    lines += _yoy_chart(f"{f0['name']} 경기(BSI), 올해와 작년 같은 달", _yoy_groups(ser, "month", _mo, n=12), lambda v: f"{v:.0f}")   # `업황 BSI` → `업황 경기(BSI)` (P66) · 선 그래프 12개월 (P161)
    for r in b["rows"]:
        lines.append(("row", f"{r['name']} 경기(BSI)", f"{r['v']:.0f}", f"{r['month'][:4]}년 {int(r['month'][5:])}월 실적 · 전달보다 {_sgn(r['chg'], 0)}p · 2009년 이후 아래에서 {r['pct_all']:.0f}% 지점"
                      + (f" · 다음 달 전망 {r['forecast']:.0f}" if r.get("forecast") is not None else "")))
    return R._state_card(f"{U.biz_name(s['sym'])} 업계 경기는?", state,   # `[업계] 업계 경기는?` — 한 회사 얘기로 읽히지 않게 (2026-10-31 사용자 P151, 옛 업종 경기는?)
                          theme, col, lines, "", tip=_tip_of(sec_bsi(s)), fold=True)


# 답 낱말 — 사업 묶음 질문에 맞춘다 (2026-10-31 사용자: "메모리 반도체 값은? · 이자 마진은? 처럼 짧게, 방향은 답이")
BIZ_WORDS = {"price": ("오르는 중", "내리는 중"), "qty": ("늘고 있음", "줄고 있음"), "margin": ("넓어지는 중", "좁아지는 중"), "size": ("커지는 중", "줄어드는 중")}


def _window_change(r0, months):
    """(바뀐 정도, 문장 앞부분) — months = 1 이면 1년 전 같은 달, 3 이면 최근 3개월 합 vs 1년 전 같은 3개월 합 (수주 · 방산 인도처럼 달마다 출렁이는 것)."""
    by = {x["month"]: x["v"] for x in r0.get("series") or []}
    last = r0["month"]

    def back(m, n):   # 'YYYY-MM' 에서 n 달 전
        y, mo = int(m[:4]), int(m[5:]) - n
        while mo <= 0:
            y, mo = y - 1, mo + 12
        return f"{y}-{mo:02d}"
    span = [back(last, i) for i in range(months)]
    prev = [f"{int(m[:4]) - 1}{m[4:]}" for m in span]
    if any(m not in by for m in span + prev):
        return None, ""
    now, old = sum(by[m] for m in span), sum(by[m] for m in prev)
    if r0["kind"] == "pct":
        return (now - old) / months, ""
    if not old:
        return None, ""
    return (now / old - 1) * 100, (f"{int(span[-1][5:])}~{int(last[5:])}월" if months > 1 else "")


def _name_josa(name, j):
    """이름 뒤 조사 — 끝의 괄호(`(전차 · 무기 · 탄약)`)는 보지 않고 앞말로 정한다 (2026-10-31: `수출액 (…)는` → `수출액 (…)은`)."""
    base = re.sub(r"\s*\([^)]*\)\s*$", "", name)
    return name + _dk.josa(base, j)[len(base):]


def card_industry_work(s):
    """업종 실물 지표 카드 — 2026-10-31 부터 사업 묶음(U.BIZ)마다 질문 · 지표 · 답 낱말 · 비교 기간 (doc/검증/한국-업종지표-재선정.md).
    옛 제목 `이 업종에 일감이 늘고 있나?` 는 묶음이 없는 종목에만. 답 = 1년 전보다 5% 넘게(금리는 0.5%p) 늘면 늘고 있음 · 줄면 줄고 있음."""
    rows_data = s.get("industry") or []
    if not rows_data:
        return ""
    b = U.biz(s["sym"]) or {"q": "이 업종에 일감이 늘고 있나?", "mode": "qty", "months": 1}
    r0 = rows_data[0]
    months = b["months"]
    chg, span_txt = _window_change(r0, months)
    lim = 0.5 if r0["kind"] == "pct" else 5
    up_w, dn_w = BIZ_WORDS[b["mode"]]
    state, theme, col = (("판단 유보", "neutral", R.MUTED) if chg is None else (up_w, "positive", UP) if chg >= lim
                         else (dn_w, "negative", DOWN) if chg <= -lim else ("비슷함", "neutral", R.MUTED))
    unit = "%p" if r0["kind"] == "pct" else "%"
    v0 = _ind_value(r0)
    if months > 1 and chg is not None:
        by = {x["month"]: x["v"] for x in r0.get("series") or []}
        tot = dict(r0, v=sum(v for m, v in sorted(by.items())[-months:]))
        head = (f"{_name_josa(r0['name'], '은')} 최근 3개월({r0['month'][:4]}년 {span_txt}) 합이 {_dk.josa(_ind_value(tot), '로')} "
                f"1년 전 같은 3개월보다 {_sgn(chg, 1)}{unit}.")
        note = "월별 자료라 1~2달 늦게 나오고, 큰 계약이 들어온 달에 크게 튑니다. 그래서 3개월을 묶어 봅니다."
    else:
        head = (f"{_name_josa(r0['name'], '은')} {r0['month'][:4]}년 {int(r0['month'][5:])}월 "
                + (f"{_dk.josa(v0, '로')} 1년 전 같은 달보다 {_sgn(chg, 1)}{unit}." if chg is not None else f"{v0}다."))
        note = "월별 자료라 1~2달 늦게 나오고, 주가는 이보다 먼저 움직이곤 합니다."
    lines = [(head + R.small_note(note), "plain")]   # 늘 같은 안내는 작은 글씨 (P67)
    div, u = _chart_unit(r0["kind"])
    scaled = [dict(x, v=x["v"] / div) for x in r0.get("series") or []]   # 단위를 먼저 나눠 그린다 — 막대 숫자만 나누면 세로 눈금이 5000000 처럼 원래 숫자로 나왔다 (2026-10-31)
    chart_name = r0["name"].replace(" (전차 · 무기 · 탄약)", "")   # 그래프 제목엔 품목 괄호를 빼고 (2026-10-31 사용자 P135) — 근거 줄 · 툴팁에는 그대로
    lines += _yoy_chart(f"{chart_name}, 올해와 작년 같은 달", _yoy_groups(scaled, "month", _mo, n=12),
                        lambda v: f"{v:,.1f}" if abs(v) < 100 else f"{v:,.0f}", unit=u)   # 단위는 그래프 오른쪽 위 (P161)
    for r in rows_data:
        cmp_txt = "전년 같은 달보다" if r["cmp"] == "yoy" else "전달보다"
        u2 = "%p" if r["kind"] == "pct" else "%"
        lines.append(("row", r["name"], _ind_value(r), f"{r['month'][:4]}년 {int(r['month'][5:])}월" + (f" · {cmp_txt} {_sgn(r['chg'], 2 if u2 == '%p' else 1)}{u2}" if r.get("chg") is not None else "")
                      + (f" · {r['note']}" if r.get("note") else "")))
    title = f"{U.biz_name(s['sym'])} 업계 {U.BIZ_Q[b['group']]}" if b.get("group") else b["q"]   # `가전 업계 수출은?` (P151)
    return R._state_card(title, state, theme, col, lines, "", tip=_tip_of(sec_industry(s)), fold=True)


def card_industry_money(s):
    """업종 회사들의 돈 버는 힘은? — 한국은행 기업경영분석(업종 전체 집계) 이익률. 답 = 1년 전 같은 분기보다 0.5%p 넘게 오르면 나아짐."""
    xs = [r for r in s.get("fin") or [] if r["unit"] != "조 원"]
    if not xs:
        return ""
    r0 = next((r for r in xs if "이익률" in r["name"]), xs[0])
    d = r0.get("chg")
    state, theme, col = (("판단 유보", "neutral", R.MUTED) if d is None else ("나아짐", "positive", UP) if d >= 0.5
                         else ("나빠짐", "negative", DOWN) if d <= -0.5 else ("비슷함", "neutral", R.MUTED))
    lines = [(f"{_dk.josa(r0['name'], '은')} {_qlabel(r0['q'])} {r0['v']:.1f}%" + (f"로 1년 전 같은 분기보다 {_sgn(d, 1)}%p." if d is not None else "다.")
              + R.small_note("설문이 아니라 업종 전체 회사를 모은 실제 집계이고, 분기 끝 2~3달 뒤에 나옵니다."), "plain")]   # 늘 같은 안내는 작은 글씨 (P67)
    # 업종 이름은 위 문장에서 한 번만 — 그래프 제목 · 근거 줄은 `매출액 영업이익률` 처럼 (2026-10-28 사용자 P68)
    lines += _yoy_chart(f"{_fin_short(s, r0['name'])}, 올해와 작년 같은 분기 (%)", _yoy_groups(r0.get("series") or [], "q", _dk.q_axis, n=8), lambda v: f"{v:.1f}", now="이번 분기", then="작년 같은 분기")
    for r in s.get("fin") or []:   # 산업별 대출(늦게 따라오는 지표)도 여기 — 질문 카드로 따로 두지 않는다
        val = f"{r['v'] / 1e3:,.0f}조 원" if r["unit"] == "조 원" else f"{r['v']:.1f}%"
        lines.append(("row", _fin_short(s, r["name"]), val, f"{_qlabel(r['q'])}" + (f" · 전년 같은 분기보다 {_sgn(r['chg'], 1)}{r['chg_unit']}" if r.get("chg") is not None else "") + f" · {r['note']}"))
    return R._state_card(f"{U.biz_name(s['sym'])} 업계 수익성은?",   # `[업계] 업계 수익성은?` (P151, 옛 회사들의 돈 버는 힘은?)
                          state, theme, col, lines, "", tip=_tip_of(sec_fin(s)), fold=True)


def sec_industry_tab(s):
    out = card_industry_mood(s) + card_industry_work(s) + card_industry_money(s)
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>' if out else _dk.muted("이 종목은 업계 자료를 아직 연결하지 않았습니다.")


def range_tip(s):
    nr = s["normal_range"]
    k = abs(nr["z"])
    now = f"· 오늘 {_sgn(s['ret_1d'], 2)}% : 평소 하루 움직임(±{nr['sigma_pct']:.1f}%)의 {k:.1f}배" + (", 평소 범위 안" if k < 2 else ", 평소 범위 밖")
    return "최근 움직임으로 잰 이 종목의 보통 하루 등락 폭. 그 2배를 넘으면 평소 범위 밖으로 본다\n" + now


def _glance(s):
    tc = s.get("tech") or {}
    return {"headline": {"close": s["close"], "ret_1d": s["ret_1d"], "vol_ratio_20d": s.get("vol_ratio"), "range_pct": tc.get("range_pct"), "ret_vs_spy": tc.get("vs_bench")},
            "normal_range": s.get("normal_range")}


LONG_NAME_W = 109   # 가격 줄 이름 칸 = 360px 폰 카드 안쪽의 36% (nvda-report PRICE_ROW_L)
PRICE_INNER_W = 302   # 360px 폰 가격 카드 안쪽 폭 (332 − 테두리 2 − 좌우 14 × 2, P137)
PRICE_BTN_GAP = 12   # 가격 · % 오른쪽 끝 ~ 접기 버튼 = 상태 카드 답 ~ 버튼 (P137)


def price_card(s):
    """가격 카드 — 미국 종목 · 엔비디아와 같은 틀. 머리 = 가격 줄 + 작은 글씨, 펼치면 기간별 수익률 · 1년 범위 · 고점 회복 · 차트 지표."""
    r = s["ret_1d"]
    g = _glance(s)
    pcol = UP if r > 0 else DOWN if r < 0 else "#111"
    tone = R.ROW_UP if r > 0 else R.ROW_DOWN if r < 0 else ""
    bg, bd = ("#FFF7EE", "#FEE6CA") if r > 0 else ("#EFF6FF", "#D6E8FE") if r < 0 else ("#fff", "#E2E8F0")
    close_html = f'<span style="color:{pcol};font-weight:700;white-space:nowrap;">{won(s["close"])}</span>'
    btn = R._fold_btn(_dk.lighten(bg), bd) if r else R.ACC_BTN
    # 한 줄에 들어가면 `가격 ▲ %` 한 줄, 넘치면 가격 위 · 증감 아래 두 줄 — 판단은 브라우저가 한다(그 폰의 글꼴 · 폭 · 그날 값으로).
    # 가격 · 증감 묶음 = 오른쪽 맞춤 flex-wrap: 두 줄이 되면 줄마다 오른쪽 끝이 같다(P135 끝선), 접기 버튼은 묶음 오른쪽(P137 288 · 300~331).
    # (2026-10-31 사용자: "에코프로처럼 이름이 짧으면 줄 바꿈이 되면 안 된다", P138. P137 은 모두 두 줄이었다 — 서버 글자 폭 어림은 경계에서 틀려 에코프로를 놓쳤다)
    name_fs = 18
    pw = R._est_w(won(s["close"]), 18)   # 두 줄로도 넘치면 이름을 17 → 16px (P137: 옛 줄이 16px 넘쳐 버튼이 카드 밖)
    for fs in (18, 17, 16):
        name_fs = fs
        if 26 + R._est_w(s["name"], fs) + 8 + pw + 12 + 31 <= PRICE_INNER_W:
            break
    price = (f'<span style="display:flex;justify-content:flex-end;align-items:center;column-gap:{PRICE_BTN_GAP}px;">'   # 가격 · % 오른쪽 끝 ~ 버튼 12 = 상태 카드 답 ~ 버튼
             f'<span style="display:flex;flex:0 1 auto;min-width:0;flex-wrap:wrap;justify-content:flex-end;align-items:baseline;column-gap:6px;">{close_html} '
             f'<span style="white-space:nowrap;margin-top:{-2 if r else 6}px;">{R._arrow(r)}</span></span>{btn}</span>')   # 두 줄일 때 가격 ~ 증감 7px (P136) — 등락 0 인 날은 흰 카드 · 줄 높이 24 라 +6 (P137). 한 줄일 땐 기준선 맞춤이라 영향 없음
    head = R.price_row(R._row("@@", price, tone)).replace("margin:0 0 6px;", "margin:0;", 1)
    head = head.replace(R.PRICE_ROW_L, "flex:0 0 auto;min-width:0;white-space:nowrap;", 1)
    head = head.replace("align-items:center;", "align-items:flex-start;", 1)   # 이름 = 가격과 같은 줄 (P135 — 가운데 맞춤이면 두 줄 사이에 떴다)
    head = head.replace("gap:12px;", "gap:8px;", 1)   # 이름 ~ 가격 8 (P137)   # "@@" 는 ticker_logo 가 배지를 만들지 않는 자리표시 — 한글 이름도 isalnum 이라 "SK" 배지가 붙는다
    nm = _esc(s["name"]) if name_fs == 18 else f'<span style="font-size:{name_fs}px;">{_esc(s["name"])}</span>'
    head = head.replace("@@", badge(s["sym"]) + nm, 1)   # 한글 첫 글자 배지 + 종목 이름
    sub = R.glance_sub(g)
    if sub:
        head = head.replace("display:flex;", "display:flex;flex-wrap:wrap;", 1).replace("gap:12px;", "column-gap:12px;row-gap:2px;", 1).replace("gap:8px;", "column-gap:8px;row-gap:2px;", 1)
        k = head.rstrip().rfind("</span>")
        sub_html = sub.replace("S&P 500", "KOSPI")
        # 증감 줄 아래 ~ 작은 글씨 8px (P135). 작은 글씨는 스스로 % 끝선(288)에 맞춰져 있다 — 오른쪽 여백을 더하면 이중으로 들어간다 (P137)
        sub_html = f'<span style="display:block;flex-basis:100%;margin-top:2px;">{sub_html}</span>'
        head = head[:k] + sub_html + head[k:]
    rows = ""   # 가격 범위 (1년) · 기간별 수익률 · 고점 회복 · 차트 정보 보기는 모두 강조 카드 안 (2026-10-26 사용자)
    return (f'<div data-cards="1" style="margin:0 0 8px;"><details data-acc="1"><summary style="list-style:none;cursor:pointer;display:block;">{head}</summary>'
            f'{R.price_in(bg, bd, [sec_year_range(s), R.in_card(sec_drawdown(s), join=True), sec_month_range(s), R.in_card(sec_periods(s), white=True), sec_momentum(s), sec_chart_indicators(s)])}{R.rows_after(rows)}</details></div>')


def periods_tip(s, ps):
    p = ps[-1]
    now = ""
    if p.get("spy") is not None:
        d = p["stock"] - p["spy"]
        now = (f"\n· {p['label']} {_sgn(p['stock'])}% : 같은 기간 KOSPI({_sgn(p['spy'])}%)보다 "
               + (f"{abs(d):.1f}%p 앞섰다" if d > 0 else f"{abs(d):.1f}%p 뒤처졌다" if d < 0 else "같았다"))
    return "지금 가격이 1주 · 1개월 · 3개월 · 6개월 · 1년 전보다 얼마나 오르거나 내렸는지. 배당을 넣어 계산했다" + now


def sec_periods(s):
    ps = s.get("periods") or []
    if not ps:
        return ""
    chart = R._col_chart([(p["label"], [p["stock"], p.get("spy")]) for p in ps], [R._sign_bg, lambda v: R._GRAY_BAR], [R._sign_fg, lambda v: NOTE])
    legend = R._legend_chips([(f"{s['name']} 오름", R._PASTEL_UP), (f"{s['name']} 내림", R._PASTEL_DN), ("KOSPI", R._GRAY_BAR)])
    card = f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}"><span style="display:block;padding:{_dk.CHART_CARD_PAD}px 12px 0;">{_dk.legend_top(chart, legend)}</span></span></div>'
    return R._card_title("기간별 수익률 (%)", periods_tip(s, ps)) + card


def year_tip(y):
    pct = y["pct_from_high"]
    where = "1년 최고가 근처" if pct > -0.5 else f"1년 최고가보다 {abs(pct):.1f}% 아래"
    return ("지난 1년 동안 가장 쌌던 값과 가장 비쌌던 값 사이에서 지금 어디쯤인지\n"
            f"· 오늘 {won(y['close'])} : {where}, 범위의 {max(0.0, min(100.0, y['pos_pct'])):.0f}% 지점")


def sec_year_range(s):
    """가격 범위 (1년) — 가격 정보 강조 카드 안 (R.year_range_in, 2026-10-26 사용자), 원화."""
    y = s.get("year_range")
    if not y:
        return ""
    return R.year_range_in(y, won, year_tip(y), (s.get("drawdown") or {}).get("days_since_high"))


def sec_month_range(s):
    """한 달간 변화 범위 — 고점 회복 문장 아래 (2026-10-31 사용자 P155: 1년 범위 → 회복 문장 → 한 달 범위), 옛 오늘 탭 상태 카드 (P150)."""
    bb = s.get("bollinger")
    if not bb or bb.get("lower") is None:
        return ""
    th, col = R.BOLL_THEME.get(bb["state"], ("neutral", R.MUTED))
    return ("white", R.month_range_in(bb, won, _boll_rule(bb), R.BOLL_STATE_KO.get(bb["state"], "범위 안"), col, top=0))


def sec_drawdown(s):
    """고점 하락 후 가격 회복 — 이 종목과 KOSPI 같은 기간."""
    d = s.get("drawdown")
    if not d:
        return ""
    st, bn = d["stock"]["dd"], d["stock"].get("bench_dd") or {}
    span = R._span_label(d["stock"])
    cols = []
    for lv in ("10", "20", "30"):
        x, y = st.get(lv) or {}, bn.get(lv) or {}
        if not x.get("n") or x.get("median_days") is None:
            continue
        if x.get("recovered") and y.get("recovered"):
            cols.append((lv, x["over_year"] / x["recovered"] * 100, y["over_year"] / y["recovered"] * 100))
    tail = ""
    if cols:
        vb = "border-left:1px solid #E2E8F0;"
        cell = lambda txt, first=False: (f'<span style="flex:1 1 0;min-width:0;box-sizing:border-box;padding:0 8px;text-align:{"left" if first else "center"};{"" if first else vb}">{txt}</span>')   # noqa: E731
        th = cell(f'<span style="color:{DOWN};font-weight:700;">하락비율</span>', True) + "".join(cell(f'<span style="color:{DOWN};font-weight:700;">−{lv}%</span>') for lv, _, _ in cols)
        r1 = cell(_esc(s["name"]), True) + "".join(cell(f"{a:.0f}%") for _, a, _ in cols)
        r2 = cell("KOSPI", True) + "".join(cell(f"{b:.0f}%") for _, _, b in cols)
        tbl = "".join(f'<span style="display:flex;align-items:stretch;line-height:24px;">{r}</span>' for r in (th, r1, r2))
        tip = "크게 떨어진 일 가운데, 최고가를 되찾기까지 1년(250거래일) 넘게 걸린 경우의 비율"
        title = (f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:0 0 4px;">'
                 f'<span style="color:#111;font-weight:700;white-space:nowrap;">회복에 1년 넘게 걸린 비율{R._tipx(tip)}</span></span>')   # `(약 30년 기간 중)` 은 뺐다 — 기간은 머리 작은 줄에 (2026-10-27 P17 · P24)
        tail = f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px;font-size:{TINY};color:{NOTE};">{title}{tbl}</span>'
    x = d["pct_from_high"]
    lv = next((l for l in ("30", "20", "10") if -x > int(l) and (st.get(l) or {}).get("median_days") is not None), None)
    now = (f"\n· 지금 {_sgn(x)}% : −{lv}% 넘게 빠졌을 때 절반은 {st[lv]['median_days']}거래일 안에 최고가를 되찾았다" if lv else f"\n· 지금 {_sgn(x)}% : 1년 최고가에서 10% 안쪽")
    ttip = "주가가 최고가에서 크게 떨어졌을 때 그 최고가를 다시 넘기까지 걸린 거래일. '보통' 은 절반이 이보다 빨리 회복한 값" + now
    return R.dd_block(s["name"], st, bn, "KOSPI", span, d["pct_from_high"], ttip, tail)   # 영역 제목 없이 한 덩이 · 구간 막대 (2026-10-27 P24 · P28)


def _no_record(tip):
    return "\n".join(x for x in tip.split("\n") if not x.startswith("· 기록상"))


def sec_chart_indicators(s):
    """`지금 가격이 평균보다` 그래프 — `차트 정보 보기` 접기는 없앴다 (P139: 일중 변동폭 · 단기 과열 온도 · 평균선 교차는 `기술지표의 방향은?` 의
    ATR · RSI · 이동평균 크로스와 겹쳐 빼고, 남은 12개월 모멘텀은 기간별 수익률 아래로)."""
    tc = s["tech"]
    # 평균선 대비 = 세로 막대 + KOSPI 같은 값 (2026-10-27 사용자 P37). `KOSPI 대비` 줄은 뺐다 — 밤사이 미국과 연결 그래프의 이 종목 · KOSPI 막대와 같은 값
    return R.ma_chart(tc["ma_rel"], tc.get("bench_ma_rel"), s["name"], "KOSPI", last=True)   # 가격 카드 끝 — 흰 카드 아래 = 좌우 8px (P140)


def sec_momentum(s):
    """12개월 모멘텀 — 기간별 수익률 아래 (P139). 그래프로 (2026-10-31 사용자 P155): A안 = 순위 위치 막대(왼쪽 하위 25% · 오른쪽 상위 25%, 점 = 이 종목, 말풍선 = 값),
    B안(목업에서만) = 세로 막대 셋(이 종목 · 35종목 중앙값 · KOSPI). 사용자가 고르면 하나만 남긴다. 1년 흐름 · 우리 종목 안 순위라 기술지표 카드(ROC 12일)와 다르다."""
    mom, mr = s.get("mom_12_1"), s.get("mom_rank")
    if mom is None or not mr:   # K18 — 우리 검증에서 유일하게 '다음 달' 과 이어진 가격 신호 (좁은 표본)
        return ""
    sp, n, period = U.MOMENTUM_RECORD
    rank, total = mr
    tip = ("12개월 전 가격 대비 1개월 전 가격의 변화. 최근 1개월은 단기 되돌림이 섞여 빼는 것이 표준(12-1 모멘텀)\n"
           f"· 오늘 {_sgn(mom, 1)}% : 우리 {total}종목 가운데 {rank}위\n"
           f"· 기록상 : 우리 종목 안에서 모멘텀 상위 25% − 하위 25% 의 다음 달 KOSPI 대비 수익 차이 {_sgn(sp, 2)}%p/월 ({period}, {n}개월, 플라시보 · 앞뒤 절반 통과) — 종목 35개 안의 좁은 표본이며 예고가 아니다")
    x = (total - rank) / max(total - 1, 1) * 100   # 오른쪽 = 1위
    zone = 2 if rank <= total / 4 else 0 if rank > total * 3 / 4 else 1
    names = [("하위 25%", 25), (f"우리 {total}종목 순위", 50), ("상위 25%", 25)]
    gauge = R._zone_gauge(x, zone, names, f"{mom:+.1f}%".replace("-", "−"), f"12개월 모멘텀 {mom:+.1f}%, {total}종목 중 {rank}위", last=False)
    gauge = gauge.replace(f"margin:0 {_dk.CHART_CARD_X - 2}px 0px;", f"margin:0 {_dk.CHART_CARD_X}px;", 1)
    col = UP if zone == 2 else DOWN if zone == 0 else "#111"
    head = (f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:0 0 8px;">'
            f'<span style="font-weight:700;color:#111;font-size:{_dk.NAME};">{_dk.CHART_MARK}{R._paren(_esc("12개월 모멘텀 (최근 1개월 제외)"))}{R._tipx(tip)}</span>'
            f'<span style="flex:none;font-weight:700;color:{col};font-size:{_dk.NAME};white-space:nowrap;">{total}종목 중 {rank}위</span></span>')
    out = head + gauge
    med, bench = s.get("mom_peers_median"), s.get("mom_bench")
    if med is not None:   # B안 — 목업에서만 (MOCK_ONLY)
        groups = [(s["name"], [mom]), (f"우리 {total}종목 중앙값", [med])] + ([("KOSPI", [bench])] if bench is not None else [])
        chart = R._col_chart(groups, [R._sign_bg], [R._sign_fg], fmt=lambda v: f"{v:+.1f}".replace("-", "−"),
                             color_at=lambda i, k, v: ((_dk.darken(R._PASTEL_UP if v >= 0 else R._PASTEL_DN, 0.2) if i == 0 else R._GRAY_BAR if i > 0 else None), (UP if v > 0 else DOWN if v < 0 else "#111") if i == 0 else NOTE))
        b = (f'<div style="margin:12px 0 6px;padding:6px 10px;border:1px dashed #F59E0B;border-radius:6px;font-size:{TINY};line-height:20px;color:#92400E;">목업 B안 — 세로 막대(이 종목 · 중앙값 · KOSPI). 위 A안(순위 막대)과 하나 고르기</div>'
             f'<span style="{R.MULTI}margin:0 {_dk.CHART_CARD_X}px;"><span style="display:block;padding:{_dk.CHART_CARD_PAD}px 12px 0;">{chart}</span></span>')
        out += MOCK_ONLY_OPEN + b + MOCK_ONLY_CLOSE
    return ("white", out)


def _boll_lines(bb):
    """한 달 범위 카드 글 — 엔비디아 bollinger_lines 와 같은 구성, 원화. 검증 통계 줄은 없다."""
    lo, hi, c = bb["lower"], bb["upper"], bb["close"]
    inside = bb["state"] not in R.BOLL_THEME
    x, zone = R._gauge_x(c, lo, hi, max(hi - lo, 1e-9) / 2)
    names = [("하락 범위", R.RANGE_SIDE), (f"한 달 범위 {won(lo)}~{won(hi)}", 100 - 2 * R.RANGE_SIDE), ("상승 범위", R.RANGE_SIDE)]
    gauge = R._zone_gauge(x, zone, names, won(c), f"오늘 종가 {won(c)}, 한 달 범위 {won(lo)}~{won(hi)}", last=inside or bb.get("days", 0) <= 1)   # 아래 `연속` 줄이 없을 때만 카드 끝
    if inside:
        plain = f"최근 한 달 평소 {won(lo)}~{won(hi)}에서 움직였고, 오늘 {won(c)}으로 그 범위 안에 있다."
        where = "범위 안"
    else:
        low = bb["state"] == "하단 도달"
        zone_ko, days = ("하락" if low else "상승"), bb.get("days", 0)
        reach = "닿았다" if days <= 1 else f"{days}일째 닿아 있다"
        plain = f"최근 한 달 평소 {won(lo)}~{won(hi)}에서 움직였는데 오늘 {won(c)}으로 {zone_ko} 범위에 {reach}."
        where = f"{zone_ko} 범위"
    lines = [(plain, "plain"), (gauge, "html")]   # 범위 · 종가 줄은 막대가 보여 주니 뺀다 (2026-10-25 사용자)
    if not inside and bb.get("days", 0) > 1:
        lines.append(("row", "연속", f"{bb['days']}일째", f"{where}에 머문 날"))
    return lines


def _boll_rule(bb):
    lo, hi, c = bb["lower"], bb["upper"], bb["close"]
    return ("최근 한 달(20거래일) 평균값에서 보통 흔들림의 2배만큼 위아래로 그은 범위. 가격은 대개 이 안에서 움직인다\n"
            f"· 오늘 {won(c)} : 범위 {won(lo)}~{won(hi)}" + (" 안" if bb["state"] not in R.BOLL_THEME else f" 밖({R.BOLL_STATE_KO.get(bb['state'], '')})"))


def sec_tech(s):
    """기술지표의 방향은? (옛 제목 기술 지표는 어느 쪽을 가리키나?, P121) (2026-10-30 사용자: 인베스팅닷컴 기술적 분석 화면처럼 — 용어 상승 · 하락 · 중립, P99) — experiments/tech_signals."""
    sig = (s.get("tech") or {}).get("signals")
    if not sig:
        return ""
    import tech_signals
    lines, tip = tech_signals.card(sig, s["name"], UP, DOWN, R.MUTED)
    th, col = tech_signals.theme(sig["net"], UP, DOWN, R.MUTED)   # 상승 빨강 · 하락 파랑의 연한 카드 (P99)
    card = R._state_card("기술지표의 방향은?", sig["word"], th, col, lines, "", tip=tip, fold=True)
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{card}</div>'


def sec_states(s):
    """상태 카드 — 한 달 범위(매일) · 과열(해당하는 날만). 시장 충격 · 시장 분위기 · 업종 자금은 미국 지표(VIX · 섹터 ETF)라 두지 않는다."""
    out = ""
    # `한 달간 변화 범위는?` 상태 카드는 가격 카드 펼침(가격 범위 (1년) 아래)으로 옮겼다 (2026-10-31 사용자 P150)
    out += card_picks(s)   # 방송 의견 — 한 달 범위 바로 아래 (2026-10-29 사용자 P88)
    oh = s.get("overheat")
    if oh and oh["active"]:
        out += R._state_card("과열 신호는?", f"{len(oh['active'])}개 조건 해당", "neutral", R.MUTED, R.overheat_lines(oh), "", tip=_no_record(R.overheat_rule(oh)))
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>' if out else ""


def related(s=None, links=None):
    """함께 보는 페이지 — links 를 주면 그 목록으로 (한국 증시 리포트가 자기 자신을 빼고 쓴다)."""
    links = list(links) if links else [("한국 증시 리포트", U.REPORT_URL), ("한국 시가총액 상위 10개 종목 주가", U.LIST_URL), ("미국 시가총액 상위 10개 종목 주가", U.US_LIST_URL)]
    if s:
        for m in (s.get("pairs") or {}).get("moves") or []:
            if m["sym"] in USU.BY_SYM:
                url = USU.NVDA_REPORTS_URL if m["sym"] in USU.REPORT_TYPE else USU.page_url(m["sym"])
                links.append((f"{USU.name(m['sym'])} {m['sym']} 주가 (미국과 연결)", url))
    return R.related_buttons(links)   # 전부 나가는 버튼 (2026-10-31 사용자 P160, 옛 점 글머리표 링크)


MAX_NEWS = 8        # `오늘` 탭에 펼쳐 두는 방송 줄, 나머지는 `그 외 n건`
TODAY_HOURS = 24    # 오늘자만 — 미국 종목 페이지와 같다 (2026-10-25 사용자)
MOCK_ONLY_OPEN, MOCK_ONLY_CLOSE = "<!--mock-only-->", "<!--/mock-only-->"   # 이 사이는 목업에만 (발행 본문에서 지운다, P155 · P158)
REAL_ONLY_OPEN, REAL_ONLY_CLOSE = "<!--real-only-->", "<!--/real-only-->"   # 이 사이는 발행 본문에만 (목업에서 지운다)
MOCK_NEWS = "<!--mock-news-->"   # 목업 전용 자리 — 발행 본문에서는 지운다 (2026-10-27 P26)
PICKS = []          # 방송에서 나온 종목 의견 (media_feed.picks, 최근 PICK_DAYS 일) — 실적과 기대 탭 `방송 의견` 카드 (P85)
PICK_DAYS = R.PICK_DAYS
MEDIA = []          # 방송 이슈 (media_feed.issues — 같은 이슈는 이미 한 줄로) — write_all 이 한 번 읽는다
MEDIA_WEEK = []     # 최근 7일 방송 이슈 — 뉴스 방향 막대 `최근 7일` (P143)


def sec_today(s):
    """`오늘` 탭 — 방송 뉴스 (2026-10-25 사용자: 한국 종목 뉴스는 방송 자막 뉴스로). 이 종목이 중심인 이슈 + 이 종목 묶음(반도체 · 2차전지 …)의 업종 이슈,
    한국 증시 채널 · 미국 채널 모두. 공용 뉴스 카드(엔비디아 · 미국 종목 페이지와 같은 _event_html): 주제 / 방송 주장 / [영역] [방향] [방송]  시각 · 채널."""
    ev = [media_feed.event(r) for r in sorted(media_feed.for_kr_page(MEDIA, s["code"]), key=lambda r: str(r["published_at"]), reverse=True)]
    bars = R.sec_direction_bars({"direction_counts": {"today": media_feed.direction_counts(media_feed.for_kr_page(MEDIA, s["code"])),
                                                      "week": media_feed.direction_counts(media_feed.for_kr_page(MEDIA_WEEK, s["code"]))}})   # 엔비디아처럼 오늘 · 최근 7일 방향 막대 (2026-10-31 사용자 P143)
    if not ev:
        return bars + _dk.muted("오늘은 이 종목을 다룬 방송 소식이 없습니다.") + MOCK_NEWS   # 목업에서만 샘플 카드로 바뀐다 (P26)
    return bars + R.sec_events({"events": ev[:MAX_NEWS], "events_overflow": ev[MAX_NEWS:MAX_NEWS + 12]})


def mock_news():
    """목업 전용 뉴스 샘플 (2026-10-27 사용자 P26: "공용 뉴스 카드로 우선 샘플") — 이 종목 방송이 없을 때 최근 한국 채널 방송 4건을 공용 카드로.
    발행 본문에는 들어가지 않는다 (write_all 이 MOCK_NEWS 를 지운다)."""
    ev = [media_feed.event(r) for r in media_feed.korea(MEDIA, 4)]
    if not ev:
        return ""
    return (f'<div style="margin:12px 0 6px;padding:6px 10px;border:1px dashed #F59E0B;border-radius:6px;font-size:{TINY};line-height:20px;color:#92400E;">'
            f'목업 샘플 — 이 종목 방송이 없어 최근 한국 채널 방송으로 카드 모양만 보여 줍니다 (발행 글에는 없음)</div>'
            + R.sec_events({"events": ev, "events_overflow": []}))


KR_PEER_LABEL = "한국 시총 상위 20개"


def _krw(x):
    """미국 카드 글의 달러 표기를 원화로 — `1,714,995억 달러` → `171.5조 원`, `$72,281.41` → `72,281원`. 카드 판정 · 모양은 그대로."""
    if isinstance(x, str):
        x = re.sub(r"([\d,]+)억 달러", lambda m: eok(float(m.group(1).replace(",", ""))), x)
        x = re.sub(r"\$([\d,]+(?:\.\d+)?)", lambda m: won(float(m.group(1).replace(",", ""))), x)
        return _JOSA_AFTER_WON.sub(lambda m: _dk.josa(m.group(1), m.group(2)), x)   # `달러로` 를 옮긴 `원로` → `원으로` (P69)
    if isinstance(x, (list, tuple)):
        return type(x)(_krw(v) for v in x)
    return x


_JOSA_AFTER_WON = re.compile(r"(\d[\d,.]*(?:조 원|억 원|원))(으로|로|은|는|이|가|을|를)(?=[\s,.]|$)")
_JOSA_NAME = re.compile(r"엔비디아(은|는|이|가|을|를|과|와|으로|로)(?=[\s,.·)]|$)")


def _rename(x, name):
    if isinstance(x, str):
        x = _JOSA_NAME.sub(lambda m: _dk.josa(name, m.group(1)), x)   # `엔비디아는` → `LG화학은` (P69)
        return _krw(x.replace("엔비디아", name).replace("기술주 15개", KR_PEER_LABEL))
    if isinstance(x, (list, tuple)):
        return type(x)(_rename(v, name) for v in x)
    return x


def build_expect(s, extra, group):
    """`실적과 기대` 재료 — 미국 종목과 같은 판정(stock-radar analyze_tabs). 비교 묶음 = 한국 시총 상위 20개."""
    s["expect"] = {}
    for k, f in (("revenue", AT.card_revenue), ("eps", AT.card_eps)):
        try:
            s["expect"][k] = f(s["sym"], extra, group)
        except Exception as e:  # noqa: BLE001
            print(f"[kr] {s['sym']} {k} 실패: {e}")
            s["expect"][k] = None


def sec_expect(s):
    """`실적과 기대` 탭 — 미국 종목과 같은 질문 카드 둘 (2026-10-25 사용자). `시장 예상 흔들림은?`(옵션) · `하락에 거는 돈은?`(공매도)은
    한국 자료가 없어 뺐다 — 개별 종목 옵션이 없고, 공매도는 Yahoo 에 없으며 한국거래소 자료는 약관 확인 전."""
    ex = s.get("expect") or {}
    out = ""
    for i, (title, key, fn) in enumerate((("회사는 돈을 더 벌고 있나?", "revenue", R.card_revenue), (R.EPS_TITLE, "eps", R.card_eps))):
        c = ex.get(key)
        if c:
            lines, tip = _rename(fn(c), s["name"])
            dart = any(r.get("src") == "dart" for r in s.get("_revenue_rows") or [])
            tip = tip.replace("SEC EDGAR", "금융감독원 전자공시(OpenDART)" if dart else "Yahoo Finance")   # 미국 카드의 출처 글 → 한국 출처
            state = c["state"]
        else:
            lines, tip, state = [("이번 실행에서 재료를 받지 못했다. 다음 실행에서 다시 받는다.", "plain")], "", "판단 유보"
        theme, col = R.EXPECT_THEME.get(state, ("neutral", R.MUTED))
        out += R._state_card(title, state, theme, col, list(lines), "", tip=tip, fold=True, opened=i == 0)
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>'


def card_picks(s):
    """방송 의견 카드 — 공용 R.picks_card (한국 · 미국 종목 같은 카드, 2026-10-29 P88 · P89). 원화 · 지금 가격 대비."""
    ps = [p for p in PICKS if p["market"] == "KR" and p["ticker"].split(".")[0] == s["code"]]
    together = R.together_block(together_items(s)) if ps else ""
    real = R.picks_card(s["name"], ps, s.get("close"), won, R.PICK_HOURS, together=together)
    if s["code"] != MOCK_PICKS_CODE or len(ps) >= 5:
        return real
    # 목업 샘플 — 다른 종목의 최근 의견을 빌려 5건 (2026-10-31 사용자 P158: 의견이 여럿일 때 접기 UX 보기). 발행 본문엔 real 만
    extra = [dict(p, ticker=s["sym"]) for p in sorted((p for p in PICKS if p["market"] == "KR" and p["ticker"].split(".")[0] != s["code"]), key=lambda p: str(p["published_at"]), reverse=True)]
    sample = R.picks_card(s["name"], (ps + extra)[:5], s.get("close"), won, R.PICK_HOURS, together=R.together_block(together_items(s)))
    note = (f'<div style="margin:12px 0 6px;padding:6px 10px;border:1px dashed #F59E0B;border-radius:6px;font-size:{TINY};line-height:20px;color:#92400E;">'
            f'목업 샘플 — 다른 종목 의견을 빌려 5건으로 채움 (발행 글에는 실제 {len(ps)}건)</div>')
    return MOCK_ONLY_OPEN + note + sample + MOCK_ONLY_CLOSE + REAL_ONLY_OPEN + real + REAL_ONLY_CLOSE


MOCK_PICKS_CODE = "247540"   # 에코프로비엠 — 방송 의견 5건 샘플 (P158)


EPS_DIR = {"높아지는 중": 1, "낮아지는 중": -1, "그대로": 0}


def together_items(s):
    """`Alpha Scope 데이터로 함께 보기` 줄 (P142) — 주가에 가까운 것부터: 내년 이익 예상 · 기술지표 방향 · 업종 경기. 방향 = 기록 계획 A5-3 분류표."""
    out = []
    eps = (s.get("expect") or {}).get("eps")
    if eps:
        out.append(("내년 이익 예상", eps["state"], EPS_DIR.get(eps["state"], 0), "실적", R.EPS_TITLE))
    sig = (s.get("tech") or {}).get("signals")
    if sig:
        out.append(("기술지표 방향", sig["word"], (sig["net"] > 0) - (sig["net"] < 0), "오늘", "기술지표의 방향은?"))
    b = s.get("bsi")
    if b and b.get("rows"):
        f0 = b["rows"][0]
        ser = f0.get("series") or []
        d3 = f0["v"] - ser[-4]["v"] if len(ser) >= 4 else f0.get("chg") or 0
        st = "좋아지는 중" if d3 >= 3 else "나빠지는 중" if d3 <= -3 else "비슷함"   # card_industry_mood 와 같은 기준
        bn = U.biz_name(s["sym"])
        out.append((f"{bn} 업계 경기", st, {"좋아지는 중": 1, "나빠지는 중": -1}.get(st, 0), "업계 상황", f"{bn} 업계 경기는?"))
    return out


# ---------------------------------------------------------------- `캘린더` 탭 (2026-10-25 사용자) — 미국 종목 캘린더 탭과 같은 질문 카드 셋.
# 한국 실적일 · 미국과 연결 종목 실적일 = collect_kr_extra(Yahoo), 시장 일정 = 미국 FOMC · 물가 · 고용(엔비디아 리포트 calendar — origin/nvda-state) + 국내 옵션 만기(둘째 목요일, 계산).
# 그날 움직임은 이 종목 · KOSPI 의 최근 2년 일봉으로 — 미국 일정은 한국 시간 다음 날 장에 반영되므로 그 다음 거래일.

import statistics  # noqa: E402
import subprocess  # noqa: E402
import cal_cards as CC  # noqa: E402 — 미국 종목과 같은 창(30일) · 다가옴(7일) · 일정 이름

US_MACRO = ("FOMC", "CPI", "NFP", "PCE", "GDP")
KR_OPEX_LABEL = "국내 옵션 만기"


def _abs_rets(bars):
    return {bars[i]["day"]: abs(bars[i]["close"] / bars[i - 1]["close"] - 1) * 100 for i in range(1, len(bars)) if bars[i - 1]["close"]}


def _signed_ret(bars, day):
    i = next((k for k, b in enumerate(bars) if b["day"] == day), None)
    return (bars[i]["close"] / bars[i - 1]["close"] - 1) * 100 if i and bars[i - 1]["close"] else None


def us_calendar():
    """미국 경제 일정 — 엔비디아 리포트가 쌓는 calendar(origin/nvda-state JSONL). 없으면 로컬 nvda.db. 둘 다 없으면 []."""
    root = os.path.join(_HERE, "..", "..")
    try:
        out = subprocess.run(["git", "show", "origin/nvda-state:experiments/nvda-report/output/state/calendar.jsonl"], capture_output=True, text=True, timeout=30, cwd=root)
        if out.returncode == 0 and out.stdout.strip():
            import json
            return [r for r in (json.loads(x) for x in out.stdout.splitlines() if x.strip()) if r.get("kind") in US_MACRO]
    except Exception as e:  # noqa: BLE001
        print(f"[kr] 미국 일정 git 읽기 실패: {str(e)[:80]}")
    db = os.path.join(_HERE, "..", "nvda-report", "data", "nvda.db")
    if os.path.exists(db):
        import sqlite3
        conn = sqlite3.connect(db)
        try:
            q = f"SELECT day, kind, label FROM calendar WHERE kind IN ({','.join('?' * len(US_MACRO))})"
            return [{"day": r[0], "kind": r[1], "label": r[2]} for r in conn.execute(q, US_MACRO)]
        finally:
            conn.close()
    return []


def kr_opex(start, end):
    """국내 주식 옵션 · 선물 만기 — 매달 둘째 목요일 (휴장이면 앞당겨지는 날은 반영하지 않는다)."""
    d0, d1 = datetime.date.fromisoformat(start), datetime.date.fromisoformat(end)
    out, y, m = [], d0.year, d0.month
    while (y, m) <= (d1.year, d1.month):
        first = datetime.date(y, m, 1)
        thu = first + datetime.timedelta(days=(3 - first.weekday()) % 7 + 7)
        if d0 <= thu <= d1:
            out.append({"day": thu.isoformat(), "kind": "KR_OPEX", "label": KR_OPEX_LABEL})
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def build_calendar(s, snap, extra, macro_rows):
    """s["calendar_cards"] — earnings · peers(미국과 연결 종목) · macro. 미국 종목 analyze_tabs 와 같은 칸."""
    bars = snap["bars"][s["sym"]]
    days = [b["day"] for b in bars]
    two_y = (datetime.date.fromisoformat(s["day"]) - datetime.timedelta(days=730)).isoformat()
    rets = _abs_rets(bars)
    normal = statistics.median(list(rets.values())[-252:]) if rets else None
    day = s["day"]
    end = (datetime.date.fromisoformat(day) + datetime.timedelta(days=CC.WINDOW)).isoformat()
    end_all = (datetime.date.fromisoformat(day) + datetime.timedelta(days=CC.LIST_DAYS)).isoformat()
    cards = {}
    ev = (extra.get("earnings") or {}).get(s["sym"]) or []
    nxt = next((x["day"] for x in ev if x["day"] > day), None)
    past = [x["day"] for x in ev if two_y <= x["day"] <= day]
    moves = [{"day": d, "ret": _signed_ret(bars, CC._next_trading(days, d, same_day=True))} for d in past]
    moves = [m for m in moves if m["ret"] is not None][-8:]
    if nxt:
        cards["earnings"] = {"day": nxt, "left": (datetime.date.fromisoformat(nxt) - datetime.date.fromisoformat(day)).days, "bars": moves,
                             "median": statistics.median(abs(m["ret"]) for m in moves) if moves else None, "normal": normal}
    pairs = (U.PAIRS.get(s["sym"]) or ([], ""))[0]
    if pairs:
        up, up_all, effect = [], [], {}
        for p in pairs:
            evs = ((extra.get("pair_earnings") or {}).get(p)) or []
            up += [{"symbol": p, "day": x["day"]} for x in evs if day < x["day"] <= end]
            up_all += [{"symbol": p, "day": x["day"]} for x in evs if day < x["day"] <= end_all]
            hits = [rets.get(CC._next_trading(days, x["day"])) for x in evs if two_y <= x["day"] < day]   # 미국 장 마감 뒤 발표 → 한국 다음 거래일
            hits = [h for h in hits if h is not None]
            effect[p] = {"median": statistics.median(hits) if hits else None, "n": len(hits)}
        cards["peers"] = {"upcoming": sorted(up, key=lambda x: x["day"]), "upcoming_all": sorted(up_all, key=lambda x: x["day"]), "effect": effect, "normal": normal}
    kb = snap["bars"].get(U.BENCH) or []
    kdays = [b["day"] for b in kb]
    krets = _abs_rets(kb)
    rows = [r for r in macro_rows if two_y <= r["day"] <= end_all] + kr_opex(two_y, end_all)
    meff = {}
    for kind in US_MACRO + ("KR_OPEX",):
        hits = [krets.get(CC._next_trading(kdays, r["day"], same_day=kind == "KR_OPEX")) for r in rows if r["kind"] == kind and r["day"] < day]
        hits = [h for h in hits if h is not None]
        if hits:
            meff[kind] = {"median": statistics.median(hits), "n": len(hits)}
    cards["macro"] = {"upcoming": sorted((r for r in rows if day < r["day"] <= end), key=lambda r: r["day"]), "effect": meff,
                      "normal": statistics.median(list(krets.values())[-252:]) if krets else None,
                      "rows": sorted((r for r in rows if r["day"] > day), key=lambda r: r["day"])}
    s["calendar_cards"] = cards


def _macro_name(k, label=""):
    return KR_OPEX_LABEL if k == "KR_OPEX" else CC.MACRO_KO.get(k, label)


def cal_earn_card(s, c):
    nm = s["name"]
    r = c["median"] / c["normal"] if c.get("median") and c.get("normal") else None
    first = f"{nm}의 다음 실적 발표는 {R._md_short(c['day'])}로 {c['left']}일 남았다."   # `(Yahoo Finance 일정이라 바뀔 수 있음)` → 문장 끝 작은 글씨 (P70)
    if r:
        first += f" 지난 {len(c['bars'])}번 발표 날 주가는 보통 ±{c['median']:.1f}% 움직여 평소 하루(±{c['normal']:.1f}%)의 약 {r:.1f}배였다."
    lines = [(first + R.small_note("일정이 변동될 수 있습니다."), "plain")]   # 옛 `(Yahoo Finance 일정이라 바뀔 수 있음)` (P70)
    if c["bars"]:
        chart = R._col_chart([(f"{b['day'][2:4]}.{b['day'][5:7]}", [b["ret"]]) for b in c["bars"][::-1]], [R._sign_bg], [R._sign_fg], height=130)   # 최신이 왼쪽 (2026-10-28 사용자 P71 · P79)
        pad = _dk.SEP_GAP - _dk.VP - 1
        lines.append((f'{_dk.CHART_TITLE_M}최근 {len(c["bars"])}번의 실적 발표 날 (%)</span>'
                      f'<span style="{R.MULTI}margin:0 {_dk.CHART_CARD_X}px;"><span style="display:block;padding:{_dk.CHART_CARD_PAD}px 12px 4px;">{chart}</span></span>', "html"))
    lines.append(("row", "발표일", R._md_short(c["day"]), "Yahoo Finance 일정"))
    if c.get("median"):
        lines.append(("row", "발표 날 보통", f"±{c['median']:.1f}%", f"지난 {len(c['bars'])}번 중앙값"))
    if c.get("normal"):
        lines.append(("row", "평소 하루", f"±{c['normal']:.1f}%", "최근 1년 중앙값"))
    tip = ("회사가 석 달마다 실적을 발표하는 날 주가가 크게 움직이곤 한다. 한국 회사는 장 전 · 장중 발표가 많아 그날 움직임을 본다. 오른 날 · 내린 날을 가리지 않고 크기만 본다\n"
           f"· {c['left']}일 남음 : {R._md_short(c['day'])}\n· 나누는 법 : {CC.SOON_DAYS}일 안으로 다가오면 카드가 보라색")
    return lines, _dk.with_src(tip, "Yahoo Finance"), f"{c['left']}일 남음", c["left"]


def cal_pair_card(s, c):
    nm, up = s["name"], c["upcoming"]
    usn = lambda x: USU.name(x) if x in USU.BY_SYM else x   # noqa: E731
    if not up:
        return [(f"앞으로 30일 안에 실적을 발표하는 {nm}의 미국 연결 종목이 없다.", "plain")], "", "없음", None
    syms = [x for x in dict.fromkeys(u["symbol"] for u in up) if c["effect"].get(x, {}).get("median")]
    names = " · ".join(usn(u["symbol"]) + "(" + R._md_short(u["day"]) + ")" for u in up)
    first = f"앞으로 30일 안에 {names}가 실적을 발표한다. {_dk.josa(nm, '와')} 같은 재료로 움직이는 미국 종목이다."
    if syms and c.get("normal"):
        eff = [c["effect"][x]["median"] for x in syms]
        first += f" 최근 2년 이 회사들의 발표 다음 날 {nm} 주가는 보통 ±{min(eff):.1f}~{max(eff):.1f}% 움직였다({nm} 보통 날 ±{c['normal']:.1f}%)."
    lines = [(first, "plain")]
    if syms and c.get("normal"):
        chart = R._chart_card([(usn(x), [c["effect"][x]["median"], c["normal"]]) for x in syms], [lambda v: R._AMBER, R._gray], [R._note_fg, R._note_fg],
                              [(f"미국과 연결 회사 발표 다음 날 {nm}", R._AMBER), (f"{nm} 보통 날", R._GRAY_BAR)], fmt=lambda v: f"±{v:.1f}")
        lines.append((f'{_dk.CHART_TITLE_M}발표 다음 날 {_esc(nm)} 움직임 (%)</span>{chart}', "html"))
    for u in up:
        e = c["effect"].get(u["symbol"]) or {}
        lines.append(("row", f"{usn(u['symbol'])} ({u['symbol']})", R._md_short(u["day"]), "미국과 연결" + (f" · 다음 날 {nm} 보통 ±{e['median']:.1f}% ({e['n']}번)" if e.get("median") else "")))
    left = (datetime.date.fromisoformat(up[0]["day"]) - datetime.date.fromisoformat(s["day"])).days
    tip = (f"{_dk.josa(nm, '와')} 같은 재료로 움직이는 미국 종목(미국과 연결)의 실적 발표. 미국 장 마감 뒤 나오는 발표는 한국 시간 다음 날 장에 반영된다\n"
           f"· 30일 안 {len(up)}곳 : 가장 가까운 발표는 {usn(up[0]['symbol'])} {R._md_short(up[0]['day'])}\n· 참고 : 최근 2년, 회사마다 8번 안팎이라 숫자는 대략으로 본다")
    return lines, _dk.with_src(tip, "Yahoo Finance"), f"{len(up)}곳 · 30일 안", left


def cal_macro_card(s, c):
    """시장 전체 일정 — 가장 가까운 1~2개만 한 줄로 요약하고, 전체는 한국 증시 리포트 `일정` 탭으로 (2026-10-31 사용자 P144: 모든 종목에 같은 공통 정보는
    공통 정보 보는 곳으로). 옛 그래프 · 일정별 줄은 리포트 쪽에 있다."""
    up = c["upcoming"]
    link = R.out_btn("한국 증시 리포트 일정에서 전체 보기", f"{U.latest_report_url()}#tab-{CAL_TAB}")   # 나가는 버튼 (P148)
    if not up:
        return [("앞으로 30일 안에 잡힌 큰 일정이 없다.", "plain"), (link, "html")], "", "없음", None
    near = " · ".join(_macro_name(u["kind"], u.get("label", "")) + "(" + R._md_short(u["day"]) + ")" for u in up[:2])
    first = f"가장 가까운 큰 일정은 {near}이다." + (f" 30일 안에 모두 {len(up)}건이 있다." if len(up) > 2 else "")
    tip = ("미국 금리 결정 · 물가 · 고용 발표와 국내 옵션 만기처럼 시장 전체가 함께 보는 일정. 모든 종목에 같은 내용이라 전체 일정과 지난 일정 뒤 KOSPI 움직임은 한국 증시 리포트 `일정` 탭에 모았다\n"
           f"· 30일 안 {len(up)}건 : 가장 가까운 일정은 {_macro_name(up[0]['kind'], up[0].get('label', ''))} {R._md_short(up[0]['day'])}")
    return [(first, "plain"), (link, "html")], _dk.with_src(tip, "FRED · Yahoo Finance"), f"{len(up)}건 · 30일 안", None


CAL_TAB = "일정"   # 한국 증시 리포트 일정 탭 이름 (kr-market-report TAB_CAL) — 테마가 #tab-일정 으로 연다


def _all_items(s):
    cc = s.get("calendar_cards") or {}
    end = (datetime.date.fromisoformat(s["day"]) + datetime.timedelta(days=CC.LIST_DAYS)).isoformat()
    items = []
    e = cc.get("earnings")
    if e and e["day"] <= end:
        items.append((e["day"], f"{s['name']} 실적", f"{s['name']} 실적 발표"))
    usn = lambda x: USU.name(x) if x in USU.BY_SYM else x   # noqa: E731
    items += [(u["day"], "미국과 연결 실적", f"{usn(u['symbol'])} 실적 발표") for u in (cc.get("peers") or {}).get("upcoming_all") or []]
    # 시장 공통 일정은 뺐다 — 한국 증시 리포트 `일정` 탭에 (P144). 여기는 이 종목 일정만
    return sorted(items)


def _all_list(s, items):
    d0 = datetime.date.fromisoformat(s["day"])
    rows = [(f'<span style="color:#111;">{_esc(R._d(d))}</span>', R._pill(k, "area"), f'<span style="color:#111;">{_esc(t)}</span>', "", f'<span style="color:#111;">{R._dn(d0, d)}</span>')
            for d, k, t in items]
    return R._gcard(rows) if rows else ""


def sec_calendar(s):
    """`일정` 탭 — 다음 실적 발표는? · 미국과 연결 종목 실적은? · 시장 전체를 흔들 일정은?(요약 + 리포트 링크) + 전체 일정 보기(이 종목 일정만)."""
    cc = s.get("calendar_cards") or {}
    out, first = "", True
    for title, key, fn in (("다음 실적 발표는?", "earnings", cal_earn_card), ("미국과 연결 종목 실적 일정은?", "peers", cal_pair_card), ("시장 전체를 흔들 일정은?", "macro", cal_macro_card)):   # 일정 탭 질문엔 `일정` (P156)
        c = cc.get(key)
        if not c:
            continue
        lines, tip, state, left = fn(s, c)
        theme, col = R._soon_theme(left)
        out += R._state_card(title, state, theme, col, lines, "", tip=tip, fold=True, opened=first)
        first = False
    items = _all_items(s)
    lst = _all_list(s, items)
    fold = (R.empty_card("잡힌 일정이 없습니다.") if not lst   # 일정이 없으면 버튼 대신 안내 카드 (P148)
            else lst if len(items) <= R.LIST_SHOWN   # 3개 이하는 접기 없이 바로 (P157)
            else (f'<details data-fold="1" data-label="전체 일정 보기"><summary style="list-style:none;cursor:pointer;">{R._fold_row("전체 일정 보기")}</summary>'
                  f'<div style="margin-top:6px;">{lst}</div></details>'))
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>' + fold


def _ymd(d):
    return f"{d[:4]}년 {int(d[4:6])}월 {int(d[6:8])}일" if len(d or "") == 8 and d.isdigit() else ""


def _info_rows(rows, px=None, lh=22, name_w=68):
    """이름 · 값 줄 묶음(흰 카드) — 구분선 없이, 이름 · 값 모두 14px (2026-10-29 사용자 P87). 값이 길어(주소 · 영문 이름) 이름 칸은 좁게.
    px · lh = 글자 크기 · 행간 (`함께 움직이는 종목` 은 한 단계 작게 13 · 20, 같은 날 P96)."""
    out = "".join(f'<span style="display:flex;gap:12px;padding:3px 12px;font-size:{px or TINY};line-height:{lh}px;">'
                  f'<span style="flex:0 0 {name_w}px;color:{NOTE};white-space:nowrap;">{_esc(k)}</span>'
                  f'<span style="flex:1 1 auto;min-width:0;color:#111;word-break:keep-all;overflow-wrap:anywhere;">{v}</span></span>' for k, v in rows)
    return f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}padding:{PAD - 3}px 0;display:block;">{out}</span></div>'


def sec_company(s):
    """`기업 정보` 탭 (2026-10-29 사용자 P84) — 한 줄 소개(직접 쓴 고정 문구, universe_kr.ABOUT) · 기본 정보(OpenDART 기업개황) · 같은 묶음 종목.
    평가 · 전망 · 추천은 없다. DART 칸이 없으면 그 줄만 뺀다."""
    c = s.get("company") or {}
    about = U.ABOUT.get(s["code"], "")
    out = f'<p style="margin:0 0 12px;padding:0 {_dk.ALIGN_PX}px;color:#111;line-height:{_dk.LH_EMPH};word-break:keep-all;">{_esc(about)}</p>' if about else ""
    url = c.get("hm_url") or ""
    href = url if url.startswith("http") else f"https://{url}" if url else ""
    rows = [("정식 이름", _esc(c.get("corp_name", ""))), ("영문 이름", _esc(c.get("corp_name_eng", ""))), ("대표", _esc(c.get("ceo_nm", ""))),
            ("설립", _esc(_ymd(c.get("est_dt", "")))), ("본사", _esc(re.sub(r"\s+", " ", c.get("adres", "")))),
            ("홈페이지", f'<a href="{_esc(href)}" style="color:#1a73e8;text-decoration:none;" rel="nofollow noopener">{_esc(url)}</a>' if url else ""),
            ("결산", f"{int(c['acc_mt'])}월" if (c.get("acc_mt") or "").isdigit() else ""),
            ("상장", f"{U.market(s['sym'])} · 종목 코드 {s['code']}"),
            ("업종", _esc(" · ".join([U.sector(s["sym"])] + list(U.groups(s["sym"])))))]
    if s.get("rank"):
        rows.append(("시가총액", f"한국 {s['rank']}위 ({cap_text(s.get('cap'))})"))
    out += _info_rows([(k, v) for k, v in rows if v])   # 흰 카드 하나, 제목 · 접기 없이 (P154 — P146 의 접기를 되돌림). 출처(OpenDART)는 공통 푸터
    # `함께 움직이는 종목` 은 오늘 탭 `함께 움직이는 종목은?` 카드로 옮겼다 (P153)
    return out


def detail_body(s, a):
    """탭 위 = 요약 · 그래프. `오늘` 탭 = 가격 카드 · 미국과 연결(펼침) · 상태 카드 · 방송 뉴스 (미국 종목 페이지처럼 테마가 첫 카드부터 오늘 탭으로 옮긴다).
    `업종` 탭 = 업종 재료 · 체감 경기 · 경영 분석
    (2026-10-25 사용자: 미국 종목 페이지처럼 탭 — 실적과 기대 · 캘린더는 다음 단계)."""
    body = (f'<span data-kr-code="{s["code"]}" hidden></span>'   # 제목에 종목 코드를 쓰지 않으므로 테마가 로고(KR_<코드>)를 이 표시로 찾는다 (2026-10-25)
            + lead(s) + sec_chart(s) + R.day_path_chart(s["tech"].get("path"), s["tech"].get("bench_path"), s["name"], "KOSPI") + price_card(s) + sec_tech(s) + sec_pairs(s, a) + sec_states(s)   # 기술 지표 카드는 가격 카드 바로 아래 (2026-10-30)
            + _dk.keep_tone(R._section("뉴스", sec_today(s), tab="오늘"))   # 뉴스는 헤드라인체 그대로
            + R._section("실적", sec_expect(s), tab="실적")
            + R._section("업계 상황", sec_industry_tab(s), tab="업계 상황")   # 업종 → 업계 상황 (2026-10-31 사용자 P151)
            + R._section("일정", sec_calendar(s), tab="일정")   # 캘린더 → 일정 (P145)
            + R._section("기업", sec_company(s), tab="기업")   # 기업정보 → 기업 (2026-10-31 P145: 탭은 짧게 — 360px 폰에서 다섯째 탭이 잘렸다)
            + related(s) + list_marker(U.LIST_URL))
    return wrap(body)


# ---------------------------------------------------------------- 자금 흐름 (목록 페이지 · 홈 한국 시장 흐름 탭의 재료)

def foreign_tip(f):
    k = abs(f["z"]) if f.get("z") is not None else None
    now = f"· 오늘 {_sgn(f['today'], 0)}억 원 : " + (f"평소 하루 순매수 크기의 {k:.1f}배" if k is not None else "") + f", 20일 누적 {_sgn(f['cum20'] / 1e4, 1)}조 원"
    return ("외국인 투자자가 유가증권시장에서 하루에 산 금액에서 판 금액을 뺀 것. 양수면 사는 쪽, 음수면 파는 쪽\n" + now +
            (f"\n· 참고 : 20일 누적은 과거 모든 20일 구간과 견줘 아래에서 {f['cum20_pct_rank']:.0f}% 지점" if f.get("cum20_pct_rank") is not None else "")
            + f"\n· 기록상 : {U.NO_RECORD['foreign']} — 지금 상태를 보는 칸이지 앞을 말하지 않는다")


def sec_foreign(m):
    f = (m or {}).get("foreign")
    if not f:
        return ""
    sign_word = "순매수" if f["today"] > 0 else "순매도"
    streak = f"{f['streak']}일 연속 {'순매수' if f['streak_sign'] > 0 else '순매도'}" if f["streak"] > 1 else sign_word
    rows = _row_html("오늘", f'<span style="color:{UP if f["today"] > 0 else DOWN};">{_sgn(f["today"], 0)}억</span>', f"{_md(f['day'])} · {streak}", first=True, inline_note=True)
    rows += _row_html("20일 누적", f'<span style="color:{UP if f["cum20"] > 0 else DOWN};">{_sgn(f["cum20"] / 1e4, 1)}조</span>',
                        f"과거 20일 구간 중 아래에서 {f['cum20_pct_rank']:.0f}% 지점" if f.get("cum20_pct_rank") is not None else "", inline_note=False)
    rows += _row_html("올해 누적", f'<span style="color:{UP if f["ytd"] > 0 else DOWN};">{_sgn(f["ytd"] / 1e4, 1)}조</span>', f"{f['day'][:4]}년", inline_note=True)
    if f.get("kosdaq_today") is not None:
        rows += _row_html("코스닥 오늘", f'<span style="color:{UP if f["kosdaq_today"] > 0 else DOWN};">{_sgn(f["kosdaq_today"], 0)}억</span>', "", inline_note=True)
    ser = f["series"][-FLOW_CHART_N:]
    chart = R._col_chart([(str(int(x["day"][8:])), [x["v"] / 1e4]) for x in ser[::-1]], [R._sign_bg], [R._sign_fg], height=130, fmt=lambda v: f"{v:+.1f}".replace("-", "−"))   # 라벨 = 일(日)만 — 폰에서 "10.13" 은 두 줄로 끊긴다
    rows += (f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px 0;">{_dk.CHART_TITLE}최근 {len(ser)}거래일 외국인 순매수 (조 원) <span style="font-size:{_dk.MICRO};font-weight:400;color:{NOTE};">{_month_span(ser)}</span></span>'
             f'<span style="display:block;height:6px;"></span>{chart}</span>')
    return R._card_title("외국인은 사고 있나?", _dk.with_src(foreign_tip(f), SRC)) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


def _month_span(ser):
    """막대 라벨이 일(日)만일 때 제목 옆에 `10월 1일~23일` 처럼 기간을 적는다."""
    a, b = ser[0]["day"], ser[-1]["day"]
    return f"{int(a[5:7])}월 {int(a[8:])}일~" + (f"{int(b[8:])}일" if a[:7] == b[:7] else f"{int(b[5:7])}월 {int(b[8:])}일")


FLOW_CHART_N = 15


WHO_NAMES = ("외국인", "기관", "개인")
WHO_COLORS = ("#F5B971", "#A7B4C6", "#D9DEE7")   # 주황 · 청회색 · 연회색 — 증감 색 · 비교 회색(#CBD5E1)과 다른 고정 색 (M50)


def share_sentence(sh):
    """`9월에 사고판 돈 854조 원 가운데 개인 31% · 외국인 36% · 기관 27%였습니다. 8월보다 개인 · 외국인 · 기관 모두 낮아졌습니다(−1 · −2 · −1%p).` (2026-10-29 사용자 M56: 달마다 누가 높아지고 낮아졌는지)."""
    ser = sh.get("series") or []
    if not ser:
        return ""
    L = ser[-1]
    mo = int(L["month"][5:])
    out = f"{mo}월에 사고판 돈 {sh['last']['total']:,.0f}조 원 가운데 개인 {L['indiv']:.0f}% · 외국인 {L['foreign']:.0f}% · 기관 {L['inst']:.0f}%였습니다."
    if len(ser) >= 2:
        P = ser[-2]
        pm = int(P["month"][5:])
        d = {k: round(L[k]) - round(P[k]) for k in ("indiv", "foreign", "inst")}
        names = {"indiv": "개인", "foreign": "외국인", "inst": "기관"}
        up = [names[k] for k in d if d[k] > 0]
        dn = [names[k] for k in d if d[k] < 0]
        same = [names[k] for k in d if d[k] == 0]
        bits = []
        if up:
            bits.append(" · ".join(up) + "은 높아지고")
        if dn:
            bits.append(" · ".join(dn) + "은 낮아졌")
        if same:
            bits.append(" · ".join(same) + "은 그대로")
        chg = " · ".join(f"{names[k]} {'+' if d[k] > 0 else '−' if d[k] < 0 else ''}{abs(d[k])}%p" for k in ("indiv", "foreign", "inst"))
        out += f" {pm}월보다 " + ", ".join(bits).replace("낮아졌,", "낮아졌고,") + ("습니다" if bits and bits[-1].endswith("낮아졌") else "입니다") + f"({chg})."
    out += f" 개인 비중은 12개월 {sh['indiv_lo12']:.0f}~{sh['indiv_hi12']:.0f}%였고, 높아지면 과열로 읽히곤 합니다."
    return out


def sec_investors(m):
    inv = (m or {}).get("investor_m")
    if not inv or not inv.get("foreign"):
        return ""
    months = [x["month"] for x in inv["foreign"]][-6:]
    def _v(k, mo):
        for x in inv.get(k) or []:
            if x["month"] == mo:
                return x["v"] / 1e6   # 백만원 → 조원
        return None
    # 세 주체는 고정 색 (증감 색이 아님 — 증감 색이면 범례 규칙이 외국인 칩을 지워 `기관 · 개인` 만 남았다, 2026-10-29 사용자 M50 · M56)
    groups = [(mo[2:].replace("-", "."), [_v("foreign", mo), _v("inst", mo), _v("indiv", mo)]) for mo in months[::-1]]   # 최신이 왼쪽 (P79)
    chart = R._col_chart(groups, [lambda v: c for c in WHO_COLORS], [R._sign_fg, R._sign_fg, R._sign_fg], height=150,   # 순매수 숫자는 모두 증감 색 (M6)
                         fmt=lambda v: f"{v:+.0f}".replace("-", "−"))
    legend = R._legend_chips(list(zip(WHO_NAMES, WHO_COLORS)))
    last = months[-1]
    rows = "".join(_row_html(n, f'<span style="color:{UP if (_v(k, last) or 0) > 0 else DOWN};">{_sgn(_v(k, last) or 0, 1)}조</span>', f"{last[:4]}년 {int(last[5:])}월 순매수", first=i == 0, inline_note=True)
                   for i, (n, k) in enumerate((("외국인", "foreign"), ("기관", "inst"), ("개인", "indiv"))))
    sh = (m or {}).get("investor_share")
    if sh:
        L = sh["last"]
        # 날짜는 위 줄처럼 괄호 안에 짧게, 설명(사고판 돈 · 12개월 범위 · 과열)은 카드 문장으로 (2026-10-29 사용자 M56)
        rows += _row_html("거래 비중", f'<span style="color:#111;">개인 {L["indiv"]:.0f}%</span><br><span style="font-size:{TINY};font-weight:400;color:{NOTE};">외국인 {L["foreign"]:.0f}% · 기관 {L["inst"]:.0f}%</span>',
                            f"{L['month'][:4]}년 {int(L['month'][5:])}월", inline_note=True)
        sch = R._col_chart([(x["month"][2:].replace("-", "."), [x["foreign"], x["inst"], x["indiv"]]) for x in sh["series"][-6:][::-1]],   # 순매수 그래프와 같은 순서 · 같은 색
                           [lambda v: c for c in WHO_COLORS], [lambda v: NOTE] * 3, height=120, fmt=lambda v: f"{v:.0f}")
        rows += (f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px 0;">{_dk.CHART_TITLE}거래 비중 (%) — 그달 사고판 돈 중 각자의 몫</span>'
                 f'<span style="display:block;height:6px;"></span>{_dk.legend_top(sch, R._legend_chips(list(zip(WHO_NAMES, WHO_COLORS))))}</span>')
    tip = ("한 달 동안 외국인 · 기관 · 개인이 각각 산 금액에서 판 금액을 뺀 것(유가증권 + 코스닥), 그리고 전체 거래에서 각자가 차지한 비중. 월별 자료라 지난달까지\n"
           f"· {last[:4]}년 {int(last[5:])}월 : 외국인 {_sgn(_v('foreign', last) or 0, 1)}조 · 기관 {_sgn(_v('inst', last) or 0, 1)}조 · 개인 {_sgn(_v('indiv', last) or 0, 1)}조")
    card = f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}<span style="display:block;{R.MULTI_SEP}padding:{_dk.CHART_CARD_PAD}px 12px 0;">{_dk.CHART_TITLE}최근 {len(months)}개월 순매수 (조 원)</span><span style="display:block;height:6px;"></span>{_dk.legend_top(chart, legend)}</span></span></div>'   # 제목 없던 그래프에 ※ 제목 (2026-10-26)
    return R._card_title("기관 · 개인은?", _dk.with_src(tip, SRC)) + card


def sec_funds(m):
    fm = (m or {}).get("funds_m")
    if not fm:
        return ""
    names = (("credit_loan", "신용융자 잔고", "빚내서 산 주식 — 많을수록 급락 때 반대매매 압력"),
             ("margin_unpaid", "위탁매매 미수금", "결제 못 한 외상 — 이틀 뒤 반대매매 대상"),
             ("deposits", "투자자 예탁금", "증권 계좌에 대기 중인 돈"))
    rows = ""
    for i, (k, n, note) in enumerate(names):
        x = fm.get(k)
        if not x:
            continue
        v, pv = x["last"]["v"], (x["prev"] or {}).get("v")
        chg = f" · 전달 대비 {_sgn((v / pv - 1) * 100, 1)}%" if pv else ""
        pos = (v - x["lo12"]) / (x["hi12"] - x["lo12"]) * 100 if x["hi12"] > x["lo12"] else 50
        rows += _row_html(n, f"{v / 1e12:.1f}조", f"{x['last']['month'][:4]}년 {int(x['last']['month'][5:])}월{chg} · 12개월 범위의 {pos:.0f}% 지점 · {note}", first=i == 0)
    c = fm.get("credit_loan") or {}
    tip = ("빚투 · 대기 자금 — 신용융자가 12개월 범위의 위쪽이면 급락 때 강제 매도가 커질 수 있는 상태, 예탁금이 늘면 살 돈이 쌓인 상태. 월별 자료라 지난달까지\n"
           + (f"· 신용융자 {c['last']['month'][:4]}년 {int(c['last']['month'][5:])}월 : {c['last']['v'] / 1e12:.1f}조 원 (12개월 {c['lo12'] / 1e12:.1f}~{c['hi12'] / 1e12:.1f}조)" if c else ""))
    return R._card_title("빚투 · 대기 자금은?", _dk.with_src(tip, SRC)) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'




def _rate_row(name, x, note, first=False):
    if not x:
        return ""
    chg = f" · 20일 {_sgn(x['chg_n'] * 100, 0)}bp" if x.get("chg_n") is not None else ""
    d1 = f"{_sgn(x['chg_1d'] * 100, 0)}bp" if x.get("chg_1d") is not None else ""
    right = f'<span style="color:#111;">{x["v"]:.2f}%</span>' + (f'<br><span style="font-size:{TINY};font-weight:400;color:{UP if x["chg_1d"] > 0 else DOWN if x["chg_1d"] < 0 else NOTE};">{d1}</span>' if d1 else "")
    return _row_html(name, right, f"{note}{chg} · 1년 {x['lo_1y']:.2f}~{x['hi_1y']:.2f}%", first=first)


def sec_rates_fx(m):
    """금리 · 환율 — 국고채 3년 · 10년 · 회사채 AA- · BBB- · 기준금리, 원/달러 · 원/엔 · 원/위안 (ECOS 일별)."""
    rt, fx = (m or {}).get("rates") or {}, (m or {}).get("fx") or {}
    if not rt and not fx:
        return ""
    rows = ""
    first = True
    for k, n, note in (("base_rate", "한국은행 기준금리", "정책 금리"), ("ktb3", "국고채 3년", "단기 시장금리의 기준"), ("ktb10", "국고채 10년", "장기 금리 · 성장주 할인율"),
                       ("corp_aa", "회사채 AA−", "우량 기업 조달 금리"), ("corp_bbb", "회사채 BBB−", "낮은 등급 기업 조달 금리")):
        r = _rate_row(n, rt.get(k), note, first=first)
        if r:
            rows += r
            first = False
    for k, n, note in (("usdkrw", "원/달러", "매매기준율 · 오르면 원화 약세"), ("jpykrw100", "원/100엔", "매매기준율"), ("cnykrw", "원/위안", "매매기준율")):
        x = fx.get(k)
        if not x:
            continue
        d1 = x.get("chg_1d")
        right = f'<span style="color:#111;">{x["v"]:,.1f}원</span>' + (f'<br><span style="font-size:{TINY};font-weight:400;color:{UP if d1 > 0 else DOWN if d1 < 0 else NOTE};">{_sgn(d1, 1)}원</span>' if d1 is not None else "")
        chg = f" · 20일 {_sgn(x['chg_n'], 1)}원" if x.get("chg_n") is not None else ""
        rows += _row_html(n, right, f"{note}{chg} · 1년 {x['lo_1y']:,.0f}~{x['hi_1y']:,.0f}원", first=first)
        first = False
    k3, usd = rt.get("ktb3"), fx.get("usdkrw")
    tip = ("금리가 오르면 빚투 비용과 성장주 할인율이 오르고, 원/달러가 오르면(원화 약세) 외국인은 환차손을 피해 팔기 쉽다. 외국인 수급과 같이 보는 배경 숫자\n"
           + (f"· 오늘 국고채 3년 {k3['v']:.2f}% ({_sgn(k3['chg_1d'] * 100, 0)}bp)" if k3 and k3.get("chg_1d") is not None else "")
           + (f" · 원/달러 {usd['v']:,.1f}원 ({_sgn(usd['chg_1d'], 1)}원)" if usd and usd.get("chg_1d") is not None else "")
           + f"\n· 기록상 : {U.NO_RECORD['rates_fx']} — 배경 숫자로만 둔다")
    return R._card_title("금리 · 환율은?", _dk.with_src(tip, "한국은행 ECOS (자료: 한국은행 · 서울외국환중개)")) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


def sec_heat(m):
    """시장 열기 — 거래대금(오늘 vs 20일 평균) · 거래량 · 뉴스심리지수."""
    h, n = (m or {}).get("heat"), (m or {}).get("news")
    if not h and not n:
        return ""
    rows, first = "", True
    if h:
        tr = h.get("turnover_ratio")
        how = "평소보다 많이" if tr and tr >= 1.5 else "평소보다 적게" if tr and tr < 0.7 else "평소와 비슷하게"
        rows += _row_html("유가증권 거래대금", f'<span style="color:#111;">{eok(h["turnover"])}</span>' + (f'<br><span style="font-size:{TINY};font-weight:400;color:{NOTE};">20일 평균의 {tr:.1f}배</span>' if tr else ""),
                            f"{_md(h['day'])} · {how} 거래됐다 · 1년 중 아래에서 {h['pct_rank_1y']:.0f}% 지점", first=True)
        first = False
        if h.get("volume"):
            rows += _row_html("유가증권 거래량", f'<span style="color:#111;">{h["volume"] / 1e4:,.1f}억 주</span>', "", inline_note=True)
        if h.get("kosdaq_turnover"):
            rows += _row_html("코스닥 거래대금", f'<span style="color:#111;">{eok(h["kosdaq_turnover"])}</span>',
                                f"거래량 {h['kosdaq_volume'] / 1e4:,.1f}억 주" if h.get("kosdaq_volume") else "", inline_note=True)
        mc = (m or {}).get("mcap")
        if mc:
            d1 = mc.get("chg_1d")
            rows += _row_html("유가증권 시가총액", f'<span style="color:#111;">{mc["v"] / 1e4:,.0f}조 원</span>' + (f'<br><span style="font-size:{TINY};font-weight:400;color:{UP if d1 > 0 else DOWN if d1 < 0 else NOTE};">{_sgn(d1, 2)}%</span>' if d1 is not None else ""),
                                f"시장 전체 크기 · 1년 {mc['lo_1y'] / 1e4:,.0f}~{mc['hi_1y'] / 1e4:,.0f}조의 위에서 {100 - mc['pct_rank_1y']:.0f}% 지점")
        ser = h["series"][-FLOW_CHART_N:]
        chart = R._col_chart([(str(int(x["day"][8:])), [x["v"] / 1e4]) for x in ser[::-1]], [lambda v: "#CBD5E1"], [lambda v: NOTE], height=120, fmt=lambda v: f"{v:.1f}")
        rows += (f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px 0;">{_dk.CHART_TITLE}최근 {len(ser)}거래일 거래대금 (조 원) <span style="font-size:{_dk.MICRO};font-weight:400;color:{NOTE};">{_month_span(ser)}</span></span>'
                 f'<span style="display:block;height:6px;"></span>{chart}</span>')
    if n:
        d = n["v"] - n["avg_1y"]
        rows += _row_html("뉴스심리지수", f'<span style="color:{UP if d > 0 else DOWN};">{n["v"]:.1f}</span>' + f'<br><span style="font-size:{TINY};font-weight:400;color:{NOTE};">20일 평균 {n["avg20"]:.1f}</span>',
                            f"{_md(n['day'])} · 100 위면 긍정 기사가 많음 · 1년 평균 {n['avg_1y']:.1f} · 1년 중 아래에서 {n['pct_rank_1y']:.0f}% 지점 · 한국은행 실험적 통계, 약 1주 늦게 나옴", first=first)
    tip = ("돈이 얼마나 활발히 오가는지(거래대금)와 경제 뉴스의 분위기(뉴스심리지수 — 한국은행이 경제 기사 문장을 긍정 · 부정으로 나눠 지수화, 100이 기준). 급등 · 급락 날은 거래대금이 평소의 1.5배를 넘곤 한다\n"
           + (f"· 오늘 거래대금 {eok(h['turnover'])} : 20일 평균의 {h['turnover_ratio']:.1f}배" if h and h.get("turnover_ratio") else "")
           + (f"\n· 뉴스심리 {n['v']:.1f} ({_md(n['day'])}) : 1년 평균 {n['avg_1y']:.1f}" if n else "")
           + f"\n· 기록상 : {U.NO_RECORD['heat']} — 열기는 그날의 상태이지 신호가 아니었다")
    return R._card_title("시장은 얼마나 뜨겁나?", _dk.with_src(tip, SRC)) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


def sec_valuation(m):
    """KOSPI 는 비싼가 — PER · 배당수익률 · 회전율 (월, 한국거래소 자료)."""
    v = (m or {}).get("valuation")
    if not v or not v.get("per"):
        return ""
    def _pos(x):
        return (x["v"] - x["lo12"]) / (x["hi12"] - x["lo12"]) * 100 if x["hi12"] > x["lo12"] else 50
    rows = ""
    per, dy, tr = v["per"], v.get("div_yield"), v.get("turnover_ratio")
    mo = f"{per['month'][:4]}년 {int(per['month'][5:])}월"
    rows += _row_html("KOSPI 주가이익비율 (PER)", f'<span style="color:#111;">{per["v"]:.1f}배</span>', f"{mo} · 12개월 {per['lo12']:.1f}~{per['hi12']:.1f}배의 {_pos(per):.0f}% 지점 · 전체 기간 평균 {per['avg_all']:.1f}배", first=True)
    if dy:
        rows += _row_html("KOSPI 배당수익률", f'<span style="color:#111;">{dy["v"]:.2f}%</span>', f"12개월 {dy['lo12']:.2f}~{dy['hi12']:.2f}% · 전체 기간 평균 {dy['avg_all']:.2f}%")
    if tr:
        rows += _row_html("상장주식 회전율", f'<span style="color:#111;">{tr["v"]:.1f}%</span>', f"한 달 동안 손바뀜 비율 · 12개월 {tr['lo12']:.1f}~{tr['hi12']:.1f}%")
    yg = v.get("yield_gap")
    if yg:   # K29 — 값만
        rows += _row_html("일드갭 (배당수익률 − 국고채 3년)", f'<span style="color:{UP if yg["v"] > 0 else DOWN};">{_sgn(yg["v"], 2)}%p</span>',
                            f"국고채 3년 {yg['ktb3']:.2f}% · 양수면 배당이 채권 이자보다 높다 · 기록상 이후 KOSPI 와 관계 없음(값만)")
    ser = per["series"][-12:]
    chart = R._col_chart([(x["month"][2:].replace("-", "."), [x["v"]]) for x in ser[::-1]], [lambda v: "#CBD5E1"], [lambda v: NOTE], height=120, fmt=lambda v: f"{v:.1f}")
    rows += (f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px 0;">{_dk.CHART_TITLE}최근 12개월 KOSPI PER (배)</span>'
             f'<span style="display:block;height:6px;"></span>{chart}</span>')
    tip = ("시장 전체가 이익에 견줘 얼마나 비싼지(PER, 높을수록 비쌈)와 배당으로 돌려주는 비율. 월별 자료라 지난달까지\n"
           f"· {mo} PER {per['v']:.1f}배 : 12개월 범위의 {_pos(per):.0f}% 지점" + (f" · 배당수익률 {dy['v']:.2f}%" if dy else "")
           + f"\n· 기록상 : {U.NO_RECORD['valuation']} — 비싼가 싼가의 상태 설명용")
    return R._card_title("KOSPI는 비싼가?", _dk.with_src(tip, SRC)) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


def sec_derivatives(m):
    """파생 시장 분위기 — 월별 풋/콜 거래량 비율 · 선물 · 옵션 일평균 거래대금 (ECOS 는 월별만. 일별 풋콜비율은 한국거래소 유료)."""
    d = (m or {}).get("derivatives")
    if not d:
        return ""
    mo = f"{d['month'][:4]}년 {int(d['month'][5:])}월"
    pc = d["put_call"]
    rows = _row_html("풋/콜 거래량 비율", f'<span style="color:{UP if pc > 1 else "#111"};">{pc:.2f}</span>', f"{mo} · 1 넘으면 풋(하락 대비)이 더 많이 거래됨 · 12개월 {d['pc_lo12']:.2f}~{d['pc_hi12']:.2f}", first=True)
    fa, oa = d.get("fut_amt_avg"), d.get("opt_amt_avg")
    if fa:
        rows += _row_html("주가지수선물 하루 거래금액", f'<span style="color:#111;">{fa["v"] / 1e6:.1f}조</span>', f"{mo} 일평균 · 12개월 {fa['lo12'] / 1e6:.1f}~{fa['hi12'] / 1e6:.1f}조")
    if oa:
        rows += _row_html("주가지수옵션 하루 거래대금", f'<span style="color:#111;">{oa["v"] / 1e6:.2f}조</span>', f"{mo} 일평균 · 12개월 {oa['lo12'] / 1e6:.2f}~{oa['hi12'] / 1e6:.2f}조")
    ser = d["pc_series"]
    chart = R._col_chart([(x["month"][2:].replace("-", "."), [x["v"]]) for x in ser[::-1]], [lambda v: "#ED8E87" if v > 1 else "#CBD5E1"], [lambda v: NOTE], height=120, fmt=lambda v: f"{v:.2f}")
    rows += (f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px 0;">{_dk.CHART_TITLE}최근 12개월 풋/콜 거래량 비율</span>'
             f'<span style="display:block;height:6px;"></span>{chart}</span>')
    tip = ("선물 · 옵션 시장의 분위기. 풋옵션(내릴 때 이익)이 콜옵션보다 많이 거래되면 하락에 대비하는 투자자가 많다는 뜻. 월별 자료라 지난달까지 — 일별 풋콜비율은 거래소 유료 자료라 두지 않는다\n"
           f"· {mo} 풋/콜 {pc:.2f} : 12개월 {d['pc_lo12']:.2f}~{d['pc_hi12']:.2f}")
    return R._card_title("파생 시장 분위기는?", _dk.with_src(tip, SRC)) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


MACRO_ROWS = [   # (키, 이름, 표기, 해석 방향: +1 높을수록 좋음 · −1 낮을수록 좋음 · 0 중립, 한 줄 설명)
    ("cpi", "소비자물가", "yoy", -1, "전년 동월 대비 · 높으면 금리 인하가 늦어진다"),
    ("ppi", "생산자물가", "yoy", -1, "전년 동월 대비 · 기업 원가 압력"),
    ("exports", "수출", "yoy", +1, "전년 동월 대비 · 한국 기업 이익의 바탕 (관세청)"),
    ("ip", "전산업 생산", "yoy", +1, "전년 동월 대비 (농림어업 제외)"),
    ("emp_insured", "고용보험 가입자", "yoy", +1, "전년 동월 대비 · 고용 대리 지표 (미국 고용 지표 자리)"),
    ("lead_cycle", "경기 선행지수 순환변동치", "lvl", +1, "100 위면 경기 흐름이 추세보다 위 (국가데이터처)"),
    ("esi", "경제심리지수", "lvl", +1, "100 기준 · 기업 + 소비자 심리 합성"),
    ("csi", "소비자심리지수", "lvl", +1, "100 위면 낙관이 많음"),
    ("bsi", "기업 업황 BSI (전산업)", "lvl", +1, "100 위면 좋다는 기업이 많음 — 보통 100 아래"),
    ("op_margin", "기업 매출액영업이익률 (전산업 · 분기)", "pct", +1, "한국은행 기업경영분석 · 분기 자료라 한 분기 늦게 · 비교는 전년 같은 분기"),
    ("tot", "순상품 교역조건지수", "lvl", 0, "수출 단가 ÷ 수입 단가 (2020=100) · 기록상 높았던 달 뒤 수출형 묶음은 오히려 부진했다(1991~2026, 사후 관찰) — 값만 (K12)"),
]


def sec_macro(m):
    """경제 바탕 — 물가 · 수출 · 생산 · 고용 · 심리 (월별, ECOS). 코스피가 올라도 바탕이 약하면 반영이 안 될 수 있다는 시각(2026-10-24 사용자)으로,
    지표마다 12개월 범위 위치를 보여 주고 '1년 평균보다 나은 지표 n개' 를 센다. 판정 · 전망은 하지 않는다."""
    mc = (m or {}).get("macro")
    if not mc:
        return ""
    rows, better, n, first = "", 0, 0, True
    for key, name, kind, sign, note in MACRO_ROWS:
        x = mc.get(key)
        if not x:
            continue
        v, avg = x["v"], x["avg12"]
        good = (v - avg) * sign > 0 if sign else False
        if sign:   # 방향 없는 지표(교역조건)는 세지 않는다
            n += 1
            better += 1 if good else 0
        pos = (v - x["lo12"]) / (x["hi12"] - x["lo12"]) * 100 if x["hi12"] > x["lo12"] else 50
        txt = (f"{_sgn(v, 1)}%" if kind == "yoy" else f"{v:.1f}%" if kind == "pct" else f"{v:.1f}")
        col = "#111" if not sign else (UP if good else DOWN)
        chg = ""
        if x.get("prev") is not None:
            d = v - x["prev"]
            chg = (f" · 전년 같은 분기보다 {_sgn(d, 1)}%p" if x.get("quarterly") else f" · 전달보다 {_sgn(d, 1)}{'%p' if kind == 'yoy' else 'p'}")
        mo = f"{x['month'][:4]}년 {x['month'][5:]}분기" if x.get("quarterly") else f"{x['month'][:4]}년 {int(x['month'][5:])}월"
        rng = "최근 4분기 범위" if x.get("quarterly") else "12개월 범위"
        rows += _row_html(name, f'<span style="color:{col};">{txt}</span>', f"{mo}{chg} · {rng}의 {pos:.0f}% 지점 · {note}", first=first)
        first = False
    if not rows:
        return ""
    tip = ("주식 시장의 바탕이 되는 경제 숫자들. 물가는 낮을수록, 수출 · 생산 · 고용 · 심리는 높을수록 시장에 우호적으로 읽는다. 월별 자료라 1~2달 늦게 나온다\n"
           f"· 지금 : {n}개 지표 중 {better}개가 지난 12개월 평균보다 나은 쪽 (전망 아님 — 코스피가 올라도 바탕이 약하면 오래 가지 못했다는 시각의 점검표)")
    head = _dk.muted(f"{n}개 지표 중 {better}개가 지난 12개월 평균보다 나은 쪽 (전망 아님)")
    return R._card_title("경제 바탕은 어떤가?", _dk.with_src(tip, "한국은행 ECOS (자료: 국가데이터처 · 관세청 · 한국고용정보원 · 한국은행)")) + head + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


def _qlabel(q):
    return f"{q[:4]}년 {q[5:]}분기"


def sec_household(m):
    """개인은 살 돈이 있나 — 가계 흑자(소득에서 쓰고 남은 돈) · 가계가 보유한 주식과 분기 순취득 · 가계신용 (분기, ECOS). 소득 자체보다 '남는 돈' 과 '실제로 주식에 넣은 돈' 이 매수 여력에 가깝다 (2026-10-24 사용자 질문에서)."""
    hh = (m or {}).get("household")
    if not hh:
        return ""
    rows, first = "", True
    def row(name, right, note):
        nonlocal rows, first
        rows += _row_html(name, right, note, first=first)
        first = False
    def yoy_txt(x, unit="%"):
        return f" · 전년 같은 분기보다 {_sgn(x['yoy'], 1)}%" if x and x.get("yoy") is not None else ""
    s, r, d = hh.get("hh_surplus"), hh.get("hh_surplus_rate"), hh.get("hh_disp_income")
    if s:
        rate = f"<br><span style=\"font-size:{TINY};font-weight:400;color:{NOTE};\">흑자율 {r['v']:.1f}%</span>" if r else ""
        row("가구당 월평균 흑자액", f'<span style="color:#111;">{s["v"] / 1e4:,.0f}만 원</span>{rate}',
            f"{_qlabel(s['q'])} · 소득에서 소비 · 세금을 빼고 남은 돈 = 저축 · 투자 여력{yoy_txt(s)}" + (f" · 흑자율은 전년 같은 분기 {r['same']:.1f}%" if r and r.get("same") is not None else ""))
    if d:
        row("가구당 월평균 처분가능소득", f'<span style="color:#111;">{d["v"] / 1e4:,.0f}만 원</span>', f"{_qlabel(d['q'])} · 전국 1인 이상 가구 · 명목{yoy_txt(d)}")
    st, sh, sb = hh.get("hh_stock"), hh.get("hh_stock_share"), hh.get("hh_stock_buy")
    if st:
        share = f"<br><span style=\"font-size:{TINY};font-weight:400;color:{NOTE};\">금융자산의 {sh['v']:.1f}%</span>" if sh else ""
        row("가계가 보유한 국내 주식", f'<span style="color:#111;">{st["v"] / 1e3:,.0f}조 원</span>{share}',   # 십억원 → 조원
            f"{_qlabel(st['q'])} · 자금순환표 잔액(시가){yoy_txt(st)}" + (f" · 비중 최근 4분기 {sh['lo4']:.1f}~{sh['hi4']:.1f}%" if sh else ""))
    if sb:
        v = sb["v"] / 1e3   # 십억 → 조
        row("가계의 국내 주식 순취득", f'<span style="color:{UP if v > 0 else DOWN};">{_sgn(v, 1)}조 원</span>', f"{_qlabel(sb['q'])} 한 분기 동안 산 금액 − 판 금액 · 양수면 개인이 주식을 늘림")
        chart = R._col_chart([(_dk.q_axis(x["q"]), [x["v"] / 1e3]) for x in sb["series"][::-1]], [R._sign_bg], [R._sign_fg], height=120, fmt=lambda v: f"{v:+.1f}".replace("-", "−"))
        rows += (f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px 0;">{_dk.CHART_TITLE}최근 {len(sb["series"])}분기 가계의 국내 주식 순취득 (조 원)</span>'
                 f'<span style="display:block;height:6px;"></span>{chart}</span>')
    c = hh.get("hh_credit")
    if c:
        rows += _row_html("가계신용 잔액", f'<span style="color:#111;">{c["v"] / 1e3:,.0f}조 원</span>', f"{_qlabel(c['q'])} · 가계 빚 전체(대출 + 카드){yoy_txt(c)} · 빠르게 늘면 살 여력이 줄어든다")
    tip = ("개인이 주식을 살 여력이 있나를 소득이 아니라 '남는 돈' 과 '실제로 넣은 돈' 으로 본다. 분기 자료라 한 분기 늦게\n"
           + (f"· 흑자액 {s['v'] / 1e4:,.0f}만 원{yoy_txt(s)}" if s else "")
           + (f" · 가계 주식 순취득 {_sgn(sb['v'] / 1e3, 1)}조 원" if sb else ""))
    return R._card_title("개인은 살 돈이 있나?", _dk.with_src(tip, "한국은행 ECOS (자료: 국가데이터처 가계동향조사 · 한국은행 자금순환 · 가계신용)")) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


def sec_overnight(m):
    """K24 · K25 밤사이 미국은? — EWY(한국 ETF) · SOX · VIX · 달러지수 밤사이 움직임 → 오늘 KOSPI. 10-25 검증에서 다음날 KOSPI 를 가장 잘 설명한 변수들 — 효과는 시가에서 끝난다."""
    ov = (m or {}).get("overnight") or []
    if not ov:
        return ""
    rows, first = "", True
    for x in ov:
        b, rec = x["before"], x.get("record")
        val = (f'<span style="color:{UP if b["ret"] > 0 else DOWN if b["ret"] < 0 else "#111"};">{_sgn(b["ret"], 2)}p</span>' if b["points"] else R._arrow(b["ret"]))
        note = f"미국 {_md(b['day'])} 종가" + (f" · 기록상 다음날 {rec[2]} 차이 {_sgn(rec[0], 2)}%p" if rec else "")
        rows += _row_html(x["label"], val, note, first=first)
        first = False
    k = (m or {}).get("kospi")
    if k and k.get("ret_1d") is not None:
        rows += _row_html("KOSPI", R._arrow(k["ret_1d"]), f"오늘 {_md(k['day'])} 종가", inline_note=True)
    w = (m or {}).get("wti")
    if w and w.get("chg_1d") is not None:
        rows += _row_html("WTI 유가", f'<span style="color:#111;">{w["v"]:.1f}달러</span><br><span style="font-size:{TINY};font-weight:400;color:{UP if w["chg_1d"] > 0 else DOWN};">{_sgn(w["chg_1d"], 1)}%</span>',
                            f"{_md(w['day'])} · 20일 {_sgn(w['chg_n'], 1)}% · 기록상 다음날 한국전력 차이 {_sgn(U.WTI_RECORD[0], 2)}%p (종목 카드)")
    latest = [x["latest"] for x in ov if x.get("latest")]
    for l in latest:
        rows += _row_html(f'{_esc(U.US_MARKET.get(l["sym"], l["sym"]))} {_small("그 뒤 미국 종가")}',
                            (f'<span style="color:{UP if l["ret"] > 0 else DOWN};">{_sgn(l["ret"], 2)}p</span>' if l["points"] else R._arrow(l["ret"])), f"미국 {_md(l['day'])} · 다음 한국장 전 참고")
    by = {x["sym"]: x["before"]["ret"] for x in ov}
    recs = " · ".join(f"{U.US_MARKET[t].split(' ')[0]} {_sgn(U.OVERNIGHT_RECORD[t][0], 2)}" for t in ("EWY", "^SOX", "^VIX", "DX-Y.NYB") if t in U.OVERNIGHT_RECORD)
    tip = ("한국 장이 닫힌 뒤 열리는 미국 장의 결과 — 미국에서 거래되는 한국 ETF(EWY) · 반도체 지수(SOX) · 변동성(VIX) · 달러. 다음날 한국 시가에 가장 먼저 반영되는 정보\n"
           + "· 밤사이 : " + " · ".join(f"{U.US_MARKET[t].split(' ')[0]} {_sgn(by[t], 2)}{'p' if t in U.US_MARKET_POINTS else '%'}" for t in by) + "\n"
           f"· 기록상 : 각 변수가 밤사이 많이 오른 날(상위 25%)과 많이 내린 날(하위 25%)의 다음날 KOSPI 수익 차이 — {recs} %p (2000~2026, 약 5,900거래일, 모두 플라시보 · 앞뒤 절반 · 보정 통과). {U.GAP_NOTE}")
    return R._card_title("밤사이 미국은?", _dk.with_src(tip, "Yahoo Finance · FRED")) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


def sec_flows(m):
    """시장 흐름 — 질문 카드: 밤사이 미국(K24 · K25) · 외국인 · 기관/개인 · 빚투 · 금리/환율 · 열기(거래대금 · 뉴스심리) · 비싼가(PER · 일드갭) · 파생(월) · 경제 바탕 · 가계."""
    out = sec_overnight(m) + sec_foreign(m) + sec_investors(m) + sec_funds(m) + sec_rates_fx(m) + sec_heat(m) + sec_valuation(m) + sec_derivatives(m) + sec_macro(m) + sec_household(m)
    h2 = f'<h2 style="color:#111;font-size:22px;font-weight:700;line-height:28px;margin:28px 0 11px;padding:0;">시장 흐름</h2>'
    return h2 + out if out else ""


# ---------------------------------------------------------------- 목록

def list_lead(a):
    top = [s for s in a["stocks"] if s["in_top"]]
    up = sum(1 for s in top if s["ret_1d"] > 0)
    first = top[0]
    text = (f"{_md(a['day'])} 종가 기준 한국 유가증권시장 시가총액 1위는 {first['name']}({first['code']}), {cap_text(first['cap'])}이다. "
            f"상위 10개 중 {up}개가 오르고 {len(top) - up}개가 내렸다.")
    f = (a.get("market") or {}).get("foreign")
    if f:
        text += f" 외국인은 유가증권시장에서 {eok(f['today'])} {'순매수' if f['today'] > 0 else '순매도'}했다."
    return f'<p data-seo-lead="1" style="{_dk.SEO_LEAD}">{_dk.tint(_esc(text))}</p>'


def list_row(s, first):
    r = s["ret_1d"]
    pcol = UP if r > 0 else DOWN if r < 0 else "#111"
    left = (f'<span style="display:inline-block;width:26px;color:{NOTE};font-weight:700;">{s["rank"]}</span>{badge(s["sym"])}'
            f'<a href="{_esc(U.page_url(s["sym"]))}" style="color:#111;text-decoration:none;">{_esc(s["name"])}</a>'
            f'<span style="display:block;padding-left:52px;font-size:{_dk.MICRO};line-height:20px;font-weight:400;color:{NOTE};">{_esc(s["code"])} · {cap_text(s["cap"])}</span>')
    right = f'<span style="color:{pcol};">{won(s["close"])}</span><br>{R._arrow(r)}'
    return _row_html(left, right, first=first).replace("<span", f'<span data-row-link="1" data-ret="{r:.4f}"', 1)


def list_body(a):
    top = [s for s in a["stocks"] if s["in_top"]]
    rest = [s for s in a["stocks"] if not s["in_top"] and s.get("rank") and s["rank"] <= U.PEER_GROUP_N]
    card = lambda xs, key="": f'<div data-cards="1" style="margin:0 0 8px;"><span{f" data-sort-list={chr(34)}{key}{chr(34)}" if key else ""} style="{R.MULTI}">{"".join(list_row(s, i == 0) for i, s in enumerate(xs))}</span></div>'   # noqa: E731   key = 정렬 버튼이 다시 놓는 목록 (P93)
    tip = ("한국 유가증권시장 보통주 가운데 회사 전체 값(주가 × 주식 수)이 가장 큰 10개. 우선주 · 코스닥은 뺀다\n"
           f"· 오늘 1위 : {top[0]['name']} {cap_text(top[0]['cap'])}\n"
           f"· 나누는 법 : 11위 밖으로 {U.SWAP_DAYS}거래일 연속 밀리면 후보 중 가장 높았던 종목과 바꾼다")
    body = (list_lead(a) + R.title_with_sort("시가총액 순위", tip, "kr-cap10") + card(top, "kr-cap10")
            + (_dk.fold(f"후보 11~{len(top) + len(rest)}위 보기", card(rest)) if rest else "")
            + _dk.muted("종목 이름을 누르면 상세 페이지로 갑니다.")
            + related())   # 시장 흐름 카드는 한국 증시 리포트로 옮김 — 목록은 미국처럼 순위만 (2026-10-26 사용자, 리포트 기획 M8)
    return wrap(body + home_marker())


def write_all(a, out_dir, snap=None, media=None, extra=None):
    os.makedirs(out_dir, exist_ok=True)
    if extra and snap:
        caps = snap.get("caps") or {}
        group = set(sorted((c[0] for c in U.CANDIDATES if caps.get(c[0])), key=lambda x: -caps[x])[:U.PEER_GROUP_N])   # 한국 시총 상위 20개
        for s in a["stocks"]:
            s["company"] = (extra.get("company") or {}).get(s["code"]) or {}   # 기업 정보 탭 — DART 기업개황 (P84)
            build_expect(s, extra, group)
            s["_revenue_rows"] = ((extra.get("revenue") or {}).get("series") or {}).get(s["sym"]) or []   # 매출 출처(DART · Yahoo) 표시용
        macro_rows = us_calendar()
        for s in a["stocks"]:
            try:
                build_calendar(s, snap, extra, macro_rows)
            except Exception as e:  # noqa: BLE001 — 캘린더가 실패해도 페이지는 만든다
                print(f"[kr] {s['sym']} 캘린더 실패: {e}")
    global MEDIA
    if media is None:
        now = datetime.datetime.now(datetime.timezone.utc)
        since = (now - datetime.timedelta(hours=TODAY_HOURS)).strftime("%Y-%m-%dT%H:%M")
        vids = media_feed.load(now.astimezone(media_feed.KST).strftime("%Y-%m-%d"), days=PICK_DAYS - 1)   # Firestore `in` 은 30개까지 — 오늘 포함 30일. 한 번 읽어 뉴스(24시간) · 방송 의견(30일)에 나눠 쓴다
        media = media_feed.issues(media_feed.rows(vids), since)
        global MEDIA_WEEK
        MEDIA_WEEK = media_feed.issues(media_feed.rows(vids), (now - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M"))   # 뉴스 방향 막대 `최근 7일` (P143)
        media_feed.diag(vids, media)   # 재료 진단 로그 — 채널 묶음 · 범위 · 종목별 배정 (2026-10-30 사용자: 분배 점검)
        global PICKS
        PICKS = media_feed.picks(vids, (now - datetime.timedelta(hours=R.PICK_HOURS)).isoformat())   # 48시간 (2026-10-31)
    MEDIA = media
    moms = sorted(x["mom_12_1"] for x in a["stocks"] if x.get("mom_12_1") is not None)
    kb = [b["close"] for b in (snap or {}).get("bars", {}).get(U.BENCH) or []] if snap else []
    bench_mom = (kb[-21] / kb[-252] - 1) * 100 if len(kb) >= 252 else None   # KOSPI 12-1 모멘텀 (B안 목업)
    for s in a["stocks"]:
        s["mom_peers_median"] = moms[len(moms) // 2] if moms else None
        s["mom_bench"] = bench_mom
    if snap:
        draw_charts(snap, a["stocks"], out_dir)
    pages = {"list": (U.LIST_TITLE, list_body(a))}
    for s in a["stocks"]:
        pages[s["code"]] = (U.page_title(s["sym"]), detail_body(s, a))
    sample = mock_news()
    for key, (title, body) in pages.items():
        real = re.sub(f"{MOCK_ONLY_OPEN}.*?{MOCK_ONLY_CLOSE}", "", body, flags=re.S).replace(REAL_ONLY_OPEN, "").replace(REAL_ONLY_CLOSE, "")
        mock = re.sub(f"{REAL_ONLY_OPEN}.*?{REAL_ONLY_CLOSE}", "", body, flags=re.S).replace(MOCK_ONLY_OPEN, "").replace(MOCK_ONLY_CLOSE, "")
        with open(os.path.join(out_dir, f"{key}.html"), "w", encoding="utf-8") as f:
            f.write(real.replace(MOCK_NEWS, ""))
        _dk.write_mock(mock.replace(MOCK_NEWS, sample), os.path.join(out_dir, f"mock_{key}.html"), title)
    return pages
