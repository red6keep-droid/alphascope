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

UP, DOWN, NOTE, TINY = _dk.UP, _dk.DOWN, _dk.NOTE, _dk.TINY
PAD = _dk.SEP_GAP - _dk.VP - 1
IMAGE_BRANCH = "kr-images"   # 한국 종목 그래프 전용 휘발성 브랜치 — 미국(radar-images)과 따로. 두 워크플로가 각자 그날 그림만으로 force push 하므로 같은 브랜치를 쓰면 서로 지운다
SRC = "한국은행 ECOS (자료: 한국거래소 · 금융투자협회)"


def _esc(t):
    return _dk.esc(t)


def _md(d):
    d = datetime.date.fromisoformat(str(d)[:10])
    return f"{d.month}월 {d.day}일"


def _sgn(v, digits=1):
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
    """종목 이름 앞 둥근 배지 — 한글 첫 글자 (미국은 로고 · 티커 두 글자, design_kit.ticker_logo). 운영지침 4-6: 제3자 로고 핫링크 없음."""
    ch = U.name(sym)[:1]
    fs = max(8, int(size * 0.5))
    return (f'<span aria-hidden="true" style="display:inline-block;width:{size}px;height:{size}px;line-height:{size}px;border-radius:50%;'
            f'vertical-align:-4px;margin-right:6px;background:#E2E8F0;color:#334155;font-size:{fs}px;font-weight:700;text-align:center;'
            f'white-space:nowrap;overflow:hidden;">{_esc(ch)}</span>')


def updated_line(a):
    return _dk.muted(f"마지막 갱신 {_dk.day(a['day'])} 한국 장 마감 기준")


def wrap(body):
    html = _dk.align_titles(_dk.WRAP_OPEN + body + _dk.WRAP_CLOSE)
    return _dk.formal(_dk.fix_colons(html))


def list_marker(url):
    return f'<span data-list-url="{_esc(url)}" hidden></span>'


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
    """맨 위 요약 (p[data-seo-lead]) — 날짜 · 종가 · 전일 대비 · 평소 범위 · 시총 순위 · 밤사이 짝. 파이썬 값만."""
    r = s["ret_1d"]
    move = f"전날보다 {abs(r):.2f}% {'올랐다' if r > 0 else '내렸다'}" if abs(r) >= 0.005 else "전날과 같았다"
    first = f"{_md(s['day'])} {s['name']}({s['code']}) 종가는 {won(s['close'])}으로 {move}."
    nr = s.get("normal_range")
    if nr:
        first += " 평소 하루 움직임 안의 변화였다." if abs(nr["z"]) < 2 else f" 평소 하루 움직임의 {abs(nr['z']):.1f}배였다."
    more = []
    if s.get("rank"):
        more.append(f"시가총액은 유가증권시장 {s['rank']}위({cap_text(s['cap'])})")
    pm = (s.get("pairs") or {}).get("moves") or []
    if pm:
        more.append("밤사이 미국 " + " · ".join(f"{m['sym']} {_sgn(m['ret'])}%" for m in pm))
    text = first + (" " + "이고, ".join(more) + "이다." if more else "")
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
            lines.append(f"· 기록상 : 짝이 밤사이 많이 오른 날(상위 25%)과 많이 내린 날(하위 25%)의 다음날 {s['name']} 수익 차이는 KOSPI 대비 평균 {_sgn(sp, 2)}%p 였다 ({y0}~2026, {n:,}거래일, 플라시보 · 앞뒤 절반 · 보정 통과). {U.GAP_NOTE}")
        else:
            lines.append(f"· 기록상 : {y0}~2026 {n:,}거래일에서 짝의 밤사이 움직임과 다음날 {s['name']} 사이에 뚜렷한 관계가 없었다 (차이 {_sgn(sp, 2)}%p) — 참고로만 둔다")
    adr = p.get("adr")
    if adr and adr["sym"] in U.ADR_RECORD:
        sp, n, y0 = U.ADR_RECORD[adr["sym"]]
        lines.append(f"· 기록상 (ADR) : {adr['sym']} 가 밤사이 많이 오른 날과 내린 날의 다음날 {s['name']} 수익 차이 {_sgn(sp, 2)}%p ({y0}~2026, {n:,}거래일, 통과) — 같은 회사라 짝보다 직접적이다. 역시 시가에 반영")
    if p.get("sox"):
        sp, n, tgt = U.OVERNIGHT_RECORD["SOX_SEMI"]
        lines.append(f"· 기록상 (SOX) : 필라델피아 반도체지수가 밤사이 많이 오른 날과 내린 날의 다음날 {tgt} 수익 차이 {_sgn(sp, 2)}%p (2000~2026, {n:,}거래일, 통과)")
    return "\n".join(lines)


def sec_pairs(s):
    """맨 위 카드 — 밤사이 미국 짝 · ADR(K24) · SOX(K25) → 오늘 이 종목 (기획 11-1: 종목 페이지의 주인공). 툴팁 `기록상` = 10-25 일별 검증."""
    p = s.get("pairs") or {}
    moves = p.get("moves") or []
    adr, sox = p.get("adr"), p.get("sox")
    if not moves and not adr and not sox:
        return ""
    r = s["ret_1d"]
    rows = ""
    first = True
    for m in moves:
        rows += R._row_html(f'{_dk.ticker_logo(m["sym"])}{_esc(m["sym"])}', R._arrow(m["ret"]), f"미국 {_md(m['day'])} 종가", first=first, inline_note=True)
        first = False
    if adr:
        rec = U.ADR_RECORD.get(adr["sym"])
        rows += R._row_html(f'{_dk.ticker_logo(adr["sym"])}{_esc(adr["sym"])} {_small("같은 회사 ADR")}', R._arrow(adr["ret"]),
                            f"미국 {_md(adr['day'])} 종가" + (f" · 기록상 다음날 차이 {_sgn(rec[0], 2)}%p ({rec[2]}~)" if rec else ""), first=first, inline_note=not rec)
        first = False
    if sox:
        sp = U.OVERNIGHT_RECORD["SOX_SEMI"][0]
        rows += R._row_html(f'SOX {_small("필라델피아 반도체")}', R._arrow(sox["ret"]), f"미국 {_md(sox['day'])} 종가 · 기록상 다음날 반도체 묶음 차이 {_sgn(sp, 2)}%p (2000~)", first=first)
        first = False
    rows += R._row_html(f'{badge(s["sym"])}{_esc(s["name"])}', R._arrow(r), f"오늘 {_md(s['day'])}", inline_note=True)
    vb = s["tech"].get("vs_bench")
    if vb is not None:
        rows += R._row_html("KOSPI 대비", R._arrow(vb, 2, "%p"), "오늘 이 종목 − KOSPI", inline_note=True)
    latest = p.get("latest") or []
    for m in latest:   # 한국 장 마감 뒤 나온 미국 종가 — 다음 한국장 전 참고. 짝마다 한 줄 (오른쪽 칸은 줄바꿈이 없어 폰에서 넘치지 않게)
        rows += R._row_html(f'{_dk.ticker_logo(m["sym"])}{_esc(m["sym"])} <span style="font-size:{_dk.MICRO};font-weight:400;color:{NOTE};">그 뒤 미국 종가</span>', R._arrow(m["ret"]),
                            f"미국 {_md(m['day'])} · 다음 한국장 전 참고", inline_note=False)
    return R._card_title("밤사이 미국 → 오늘 반응", pair_tip(s)) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


IND_SRC = {"derived": "한국은행 금리 통계", "121Y006": "한국은행 대출금리", "121Y002": "한국은행 수신금리", "151Y002": "한국은행 가계대출", "901Y054": "은행연합회 연체율", "402Y016": "한국은행 수출물가지수", "901Y039": "국가데이터처 광공업 생산", "901Y019": "한국전력공사", "901Y073": "한국석유공사", "901Y072": "에너지경제연구원",
           "901Y020": "국가데이터처 건설수주", "901Y105": "국가데이터처 주택건설인허가", "901Y074": "국가데이터처 미분양주택", "901Y149": "한국부동산원", "601Y003": "한국은행 신용카드"}


def _ind_value(r):
    v, kind = r["v"], r["kind"]
    if kind == "idx":
        return f"{v:.1f}"
    if kind == "cnt":
        return f"{v:,.0f}호"
    if kind == "won_m":
        return f"{v / 1e6:,.1f}조 원"
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
        rows += R._row_html(r["name"], f'<span style="color:#111;">{_ind_value(r)}</span>{chg}', note, first=i == 0)
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
        rows += R._row_html(n, right, f"{_md(x['day'])} · {note} · 1년 {x['lo_1y']:,.0f}~{x['hi_1y']:,.0f}원 · 기록상 이후 주가와 관계 없음(값만)")
    w = s.get("wti")
    if w:
        d1 = w.get("chg_1d")
        right = f'<span style="color:#111;">{w["v"]:.1f}달러</span>' + (f'<br><span style="font-size:{TINY};font-weight:400;color:{UP if d1 > 0 else DOWN if d1 < 0 else NOTE};">{_sgn(d1, 1)}%</span>' if d1 is not None else "")
        sp, n, y0 = U.WTI_RECORD
        rows += R._row_html("WTI 유가", right, f"{_md(w['day'])} · 20일 {_sgn(w['chg_n'], 1)}% · 1년 {w['lo_1y']:.0f}~{w['hi_1y']:.0f}달러 · 기록상 많이 오른 날과 내린 날의 다음날 {s['name']} 차이 {_sgn(sp, 2)}%p ({y0}~2026)")
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
    return R._card_title("업종 재료는?", _dk.with_src(tip, "한국은행 ECOS (자료: " + " · ".join(srcs) + ")" + (" · FRED" if w else ""))) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


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
        rows += R._row_html(f"{r['name']} BSI", f'<span style="color:{col};">{r["v"]:.0f}</span>{fc}', note, first=i == 0)
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
        rows += R._row_html(r["name"], f'<span style="color:#111;">{val}</span>{chg}', note, first=i == 0)
    f0 = xs[0]
    tip = ("업종 전체 회사들의 재무(한국은행 기업경영분석 — 설문이 아니라 실제 집계)와 그 업종이 은행에서 빌린 돈. 분기 끝 2~3달 뒤에 나와 종목 실적보다 늦다\n"
           f"· {f0['name']} {f0['v']:.1f}{'%' if f0['unit'] != '조 원' else ''} : {_qlabel(f0['q'])}" + (f", 전년 같은 분기보다 {_sgn(f0['chg'], 1)}{f0['chg_unit']}" if f0.get("chg") is not None else "") + "\n"
           "· 기록상 : 미검증 — 분기 자료가 2015년부터 46개뿐이라 수익 검증은 표본이 부족하고, 대출은 경기에 늦게 따라오는 지표로 알려져 있다. 시설자금이 늘면 투자 · 증설, 운전자금만 늘고 매출이 나쁘면 버티기 차입 쪽으로 읽히곤 한다 — 판정하지 않고 숫자만 둔다")
    return R._card_title("업종 재무 · 대출은? (분기)", _dk.with_src(tip, "한국은행 ECOS (기업경영분석 · 예금은행 산업별 대출)")) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


def range_tip(s):
    nr = s["normal_range"]
    k = abs(nr["z"])
    now = f"· 오늘 {_sgn(s['ret_1d'], 2)}% : 평소 하루 움직임(±{nr['sigma_pct']:.1f}%)의 {k:.1f}배" + (", 평소 범위 안" if k < 2 else ", 평소 범위 밖")
    return "최근 움직임으로 잰 이 종목의 보통 하루 등락 폭. 그 2배를 넘으면 평소 범위 밖으로 본다\n" + now


def _glance(s):
    tc = s.get("tech") or {}
    return {"headline": {"close": s["close"], "ret_1d": s["ret_1d"], "vol_ratio_20d": s.get("vol_ratio"), "range_pct": tc.get("range_pct"), "ret_vs_spy": tc.get("vs_bench")},
            "normal_range": s.get("normal_range")}


def price_card(s):
    """가격 카드 — 미국 종목 · 엔비디아와 같은 틀. 머리 = 가격 줄 + 작은 글씨, 펼치면 기간별 수익률 · 1년 범위 · 고점 회복 · 차트 지표."""
    r = s["ret_1d"]
    g = _glance(s)
    pcol = UP if r > 0 else DOWN if r < 0 else "#111"
    tone = R.ROW_UP if r > 0 else R.ROW_DOWN if r < 0 else ""
    bg, bd = ("#FFF7ED", "#FED7AA") if r > 0 else ("#EFF6FF", "#BFDBFE") if r < 0 else ("#fff", "#E2E8F0")
    price = (f'<span style="display:inline-flex;align-items:center;justify-content:flex-end;">'
             f'<span style="color:{pcol};font-weight:700;">{won(s["close"])}</span>&nbsp;{R._arrow(r)}'
             f'{R._fold_btn(_dk.lighten(bg), bd) if r else R.ACC_BTN}</span>')
    head = R._row("@@", price, tone).replace("margin:0 0 6px;", "margin:0;", 1)   # "@@" 는 ticker_logo 가 배지를 만들지 않는 자리표시 — 한글 이름도 isalnum 이라 "SK" 배지가 붙는다
    head = head.replace("@@", badge(s["sym"]) + _esc(s["name"]), 1)   # 한글 첫 글자 배지 + 종목 이름
    sub = R.glance_sub(g)
    if sub:
        head = head.replace("display:flex;", "display:flex;flex-wrap:wrap;", 1).replace("gap:12px;", "column-gap:12px;row-gap:2px;", 1)
        k = head.rstrip().rfind("</span>")
        head = head[:k] + sub.replace("S&P 500", "KOSPI") + head[k:]
    rows = sec_periods(s) + sec_year_range(s) + sec_drawdown(s) + sec_chart_indicators(s)
    return (f'<div data-cards="1" style="margin:0 0 8px;"><details data-acc="1"><summary style="list-style:none;cursor:pointer;display:block;">{head}</summary>'
            f'<div style="margin-top:8px;">{rows}</div></details></div>')


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
    card = f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}"><span style="display:block;padding:{PAD + 6}px 12px 0;">{chart}{legend}</span></span></div>'
    return R._card_title("기간별 수익률 (%)", periods_tip(s, ps)) + card


def year_tip(y):
    pct = y["pct_from_high"]
    where = "1년 최고가 근처" if pct > -0.5 else f"1년 최고가보다 {abs(pct):.1f}% 아래"
    return ("지난 1년 동안 가장 쌌던 값과 가장 비쌌던 값 사이에서 지금 어디쯤인지\n"
            f"· 오늘 {won(y['close'])} : {where}, 범위의 {max(0.0, min(100.0, y['pos_pct'])):.0f}% 지점")


def sec_year_range(s):
    """1년 가격 범위 — 엔비디아 sec_year_range 와 같은 모양, 원화."""
    y = s.get("year_range")
    if not y:
        return ""
    pos = max(0.0, min(100.0, y["pos_pct"]))
    head = (f'<span style="{R.MULTI_ROW}"><span style="flex:1 1 auto;min-width:0;font-weight:700;color:#111;font-size:{_dk.NAME};">최고가 대비</span>'
            f'<span style="flex:none;text-align:right;white-space:nowrap;{R.VAL}font-weight:700;">{R._arrow(y["pct_from_high"], 1)}</span></span>')
    track = (f'<span style="display:block;position:relative;height:8px;border-radius:4px;background:#E2E8F0;margin:6px 0 10px;">'
             f'<span style="position:absolute;left:0;top:0;height:8px;width:{pos:.1f}%;border-radius:4px;background:#BFDBFE;"></span>'
             f'<span style="position:absolute;top:-4px;left:{pos:.1f}%;width:16px;height:16px;margin-left:-8px;border-radius:50%;background:#111;border:2px solid #fff;box-sizing:border-box;"></span></span>')
    ends = (f'<span style="display:flex;justify-content:space-between;gap:12px;font-size:{TINY};line-height:20px;color:{NOTE};">'
            f'<span>최저 {won(y["low"])}</span><span>(오늘 {won(y["close"])})</span><span>최고 {won(y["high"])}</span></span>')
    body = f'<span style="display:block;padding:0 12px {PAD}px;">{track}{ends}</span>'
    return R._card_title("1년 가격 범위", year_tip(y)) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{head}{body}</span></div>'


def sec_drawdown(s):
    """고점 하락 후 가격 회복 — 이 종목과 KOSPI 같은 기간."""
    d = s.get("drawdown")
    if not d:
        return ""
    st, bn = d["stock"]["dd"], d["stock"].get("bench_dd") or {}
    span = R._span_label(d["stock"])
    sm = f'font-size:{TINY};font-weight:400;color:{NOTE};'
    head = R._row_html("지금", R._arrow(d["pct_from_high"], 1), f"1년 최고가 이후 {d['days_since_high']}거래일째", first=True, inline_note=True)
    rows, cols = "", []
    for lv in ("10", "20", "30"):
        x, y = st.get(lv) or {}, bn.get(lv) or {}
        if not x.get("n") or x.get("median_days") is None:
            continue
        right = f'<span style="{sm}">보통</span> {x["median_days"]}일' + (f'<br><span style="{sm}">KOSPI 보통 {y["median_days"]}일</span>' if y.get("median_days") is not None else "")
        rows += R._row_html(f'<span style="color:{DOWN};">−{lv}%</span> 넘게 내려가면', right, f"{span} 동안 {s['name']} {x['n']}번 발생")
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
                 f'<span style="color:#111;font-weight:700;white-space:nowrap;">회복에 1년 넘게 걸린 비율{R._tipx(tip)}</span>'
                 f'<span style="flex:none;font-size:{_dk.MICRO};font-weight:400;color:{NOTE};">({span} 기간 중)</span></span>')
        tail = f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px;font-size:{TINY};color:{NOTE};">{title}{tbl}</span>'
    x = d["pct_from_high"]
    lv = next((l for l in ("30", "20", "10") if -x > int(l) and (st.get(l) or {}).get("median_days") is not None), None)
    now = (f"\n· 지금 {_sgn(x)}% : −{lv}% 넘게 빠졌을 때 절반은 {st[lv]['median_days']}거래일 안에 최고가를 되찾았다" if lv else f"\n· 지금 {_sgn(x)}% : 1년 최고가에서 10% 안쪽")
    ttip = "주가가 최고가에서 크게 떨어졌을 때 그 최고가를 다시 넘기까지 걸린 거래일. '보통' 은 절반이 이보다 빨리 회복한 값" + now
    return R._card_title("고점 하락 후 가격 회복", ttip) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{R._fold_rows(head, rows + tail)}</span></div>'


def _no_record(tip):
    return "\n".join(x for x in tip.split("\n") if not x.startswith("· 기록상"))


def sec_chart_indicators(s):
    tc = s["tech"]
    deep = R._multi2([(f"{n}일 평균", R._arrow(v, 1)) for n, v in sorted(tc["ma_rel"].items(), key=lambda x: int(x[0]))])
    deep += R._multi2([("KOSPI 대비", R._arrow(tc.get("vs_bench"), 2, "%p"))])
    rsi, mc = tc.get("rsi14"), tc.get("ma_cross")
    mc_html = {"golden": f'<span style="color:{UP};font-weight:700;">골든크로스</span>', "death": f'<span style="color:{DOWN};font-weight:700;">데드크로스</span>'}.get(
        mc, f'<span style="color:{R.MUTED};">교차 없음</span>')
    items = []
    mom, mr = s.get("mom_12_1"), s.get("mom_rank")
    if mom is not None and mr:   # K18 — 우리 검증에서 유일하게 '다음 달' 과 이어진 가격 신호 (좁은 표본)
        sp, n, period = U.MOMENTUM_RECORD
        items.append((f"12개월 모멘텀 (최근 1개월 제외 · 우리 {mr[1]}종목 중 {mr[0]}위)", R._arrow(mom, 1),
                      "12개월 전 가격 대비 1개월 전 가격의 변화. 최근 1개월은 단기 되돌림이 섞여 빼는 것이 표준(12-1 모멘텀)\n"
                      f"· 오늘 {_sgn(mom, 1)}% : 우리 {mr[1]}종목 가운데 {mr[0]}위\n"
                      f"· 기록상 : 우리 종목 안에서 모멘텀 상위 25% − 하위 25% 의 다음 달 KOSPI 대비 수익 차이 {_sgn(sp, 2)}%p/월 ({period}, {n}개월, 플라시보 · 앞뒤 절반 통과) — 종목 35개 안의 좁은 표본이며 예고가 아니다"))
    items += [("시가 갭", R._arrow(tc.get("gap"), 2), R.gap_tip(tc.get("gap"))),
             (f"일중 변동폭 (고가−저가 · 흔히 {R.config.RANGE_PCT_EVENT:.0f}% 넘으면 큰 흔들림으로 봄)",
              f'<span style="color:#111;font-weight:700;">{tc["range_pct"]:.2f}%</span>' if tc.get("range_pct") is not None else "—"),
             ("단기 과열 온도 (RSI 14 · 흔히 70 넘으면 과열 · 30 아래면 침체로 읽음)",
              f'<span style="color:#111;font-weight:700;">{rsi:.1f}</span>' if rsi is not None else "—", _no_record(R.rsi_tip(rsi))),
             ("평균선 교차 (50일선이 200일선 위로 = 골든크로스)", mc_html, _no_record(R.cross_tip(mc)))]
    deep += R._multi(items)
    return (f'<details data-fold="1" data-label="차트 지표 보기" style="margin:0 0 8px;"><summary style="list-style:none;cursor:pointer;">{R._fold_row("차트 지표 보기")}</summary>'
            f'<div style="margin-top:6px;">{deep}</div></details>')


def _boll_lines(bb):
    """한 달 범위 카드 글 — 엔비디아 bollinger_lines 와 같은 구성, 원화. 검증 통계 줄은 없다."""
    lo, hi, c = bb["lower"], bb["upper"], bb["close"]
    inside = bb["state"] not in R.BOLL_THEME
    x, zone = R._gauge_x(c, lo, hi, max(hi - lo, 1e-9) / 2)
    names = [("하락 범위", R.RANGE_SIDE), (f"한 달 범위 {won(lo)}~{won(hi)}", 100 - 2 * R.RANGE_SIDE), ("상승 범위", R.RANGE_SIDE)]
    gauge = R._zone_gauge(x, zone, names, won(c), f"오늘 종가 {won(c)}, 한 달 범위 {won(lo)}~{won(hi)}")
    if inside:
        plain = f"최근 한 달 평소 {won(lo)}~{won(hi)}에서 움직였고, 오늘 {won(c)}으로 그 범위 안에 있다."
        where = "범위 안"
    else:
        low = bb["state"] == "하단 도달"
        zone_ko, days = ("하락" if low else "상승"), bb.get("days", 0)
        reach = "닿았다" if days <= 1 else f"{days}일째 닿아 있다"
        plain = f"최근 한 달 평소 {won(lo)}~{won(hi)}에서 움직였는데 오늘 {won(c)}으로 {zone_ko} 범위에 {reach}."
        where = f"{zone_ko} 범위"
    lines = [(plain, "plain"), (gauge, "html"), ("row", "한 달 범위", f"{won(lo)} ~ {won(hi)}", "20일 평균 ± 보통 흔들림 2배"), ("row", "오늘 종가", won(c), where)]
    if not inside and bb.get("days", 0) > 1:
        lines.append(("row", "연속", f"{bb['days']}일째", f"{where}에 머문 날"))
    return lines


def _boll_rule(bb):
    lo, hi, c = bb["lower"], bb["upper"], bb["close"]
    return ("최근 한 달(20거래일) 평균값에서 보통 흔들림의 2배만큼 위아래로 그은 범위. 가격은 대개 이 안에서 움직인다\n"
            f"· 오늘 {won(c)} : 범위 {won(lo)}~{won(hi)}" + (" 안" if bb["state"] not in R.BOLL_THEME else f" 밖({R.BOLL_STATE_KO.get(bb['state'], '')})"))


def sec_states(s):
    """상태 카드 — 한 달 범위(매일) · 과열(해당하는 날만). 시장 충격 · 시장 분위기 · 업종 자금은 미국 지표(VIX · 섹터 ETF)라 두지 않는다."""
    out = ""
    bb = s.get("bollinger")
    if bb and bb.get("lower") is not None:
        th, col = R.BOLL_THEME.get(bb["state"], ("neutral", R.MUTED))
        out += R._state_card("한 달간 변화 범위는?", R.BOLL_STATE_KO.get(bb["state"], "범위 안"), th, col, _boll_lines(bb), "", tip=_boll_rule(bb), fold=True, inline_notes=True)
    oh = s.get("overheat")
    if oh and oh["active"]:
        out += R._state_card("과열 신호는?", f"{len(oh['active'])}개 조건 해당", "neutral", R.MUTED, R.overheat_lines(oh), "", tip=_no_record(R.overheat_rule(oh)))
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>' if out else ""


def related(s=None):
    links = [("한국 시가총액 상위 10개 종목 주가", U.LIST_URL), ("미국 시가총액 상위 10개 종목 주가", U.US_LIST_URL)]
    if s:
        for m in (s.get("pairs") or {}).get("moves") or []:
            if m["sym"] in USU.BY_SYM:
                url = USU.NVDA_REPORTS_URL if m["sym"] in USU.REPORT_TYPE else USU.page_url(m["sym"])
                links.append((f"{USU.name(m['sym'])} {m['sym']} 주가 (미국 연결 짝)", url))
    items = "".join(_dk.dot_li(f'<a href="{_esc(u)}" style="color:#1a73e8;text-decoration:none;">{_esc(t)}</a>', size=3, color="#111", margin="4px 0") for t, u in links)
    return (f'<div data-related="1" style="margin-top:24px;"><div style="font-weight:700;color:#111;font-size:{_dk.EMPH_NAME};padding-left:{_dk.ALIGN_PX}px;">함께 보는 페이지</div>'
            f'<ul style="margin:6px 0 0;padding:0 0 0 {_dk.ALIGN_PX}px;list-style:none;font-size:{_dk.NAME};line-height:{R.LH_CARD};">{items}</ul></div>')


def detail_body(s, a):
    body = lead(s) + updated_line(a) + sec_chart(s) + sec_pairs(s) + sec_industry(s) + sec_bsi(s) + sec_fin(s) + price_card(s) + sec_states(s) + related(s) + list_marker(U.LIST_URL)
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
    rows = R._row_html("오늘", f'<span style="color:{UP if f["today"] > 0 else DOWN};">{_sgn(f["today"], 0)}억</span>', f"{_md(f['day'])} · {streak}", first=True, inline_note=True)
    rows += R._row_html("20일 누적", f'<span style="color:{UP if f["cum20"] > 0 else DOWN};">{_sgn(f["cum20"] / 1e4, 1)}조</span>',
                        f"과거 20일 구간 중 아래에서 {f['cum20_pct_rank']:.0f}% 지점" if f.get("cum20_pct_rank") is not None else "", inline_note=False)
    rows += R._row_html("올해 누적", f'<span style="color:{UP if f["ytd"] > 0 else DOWN};">{_sgn(f["ytd"] / 1e4, 1)}조</span>', f"{f['day'][:4]}년", inline_note=True)
    if f.get("kosdaq_today") is not None:
        rows += R._row_html("코스닥 오늘", f'<span style="color:{UP if f["kosdaq_today"] > 0 else DOWN};">{_sgn(f["kosdaq_today"], 0)}억</span>', "", inline_note=True)
    ser = f["series"][-FLOW_CHART_N:]
    chart = R._col_chart([(str(int(x["day"][8:])), [x["v"] / 1e4]) for x in ser], [R._sign_bg], [R._sign_fg], height=130, fmt=lambda v: f"{v:+.1f}".replace("-", "−"))   # 라벨 = 일(日)만 — 폰에서 "10.13" 은 두 줄로 끊긴다
    rows += (f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px 0;"><span style="display:block;font-weight:700;color:#111;font-size:{_dk.NAME};">최근 {len(ser)}거래일 외국인 순매수 (조 원) <span style="font-size:{_dk.MICRO};font-weight:400;color:{NOTE};">{_month_span(ser)}</span></span>'
             f'<span style="display:block;height:6px;"></span>{chart}</span>')
    return R._card_title("외국인은 사고 있나?", _dk.with_src(foreign_tip(f), SRC)) + f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}</span></div>'


def _month_span(ser):
    """막대 라벨이 일(日)만일 때 제목 옆에 `10월 1일~23일` 처럼 기간을 적는다."""
    a, b = ser[0]["day"], ser[-1]["day"]
    return f"{int(a[5:7])}월 {int(a[8:])}일~" + (f"{int(b[8:])}일" if a[:7] == b[:7] else f"{int(b[5:7])}월 {int(b[8:])}일")


FLOW_CHART_N = 15


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
    groups = [(mo[2:].replace("-", "."), [_v("foreign", mo), _v("inst", mo), _v("indiv", mo)]) for mo in months]
    colors = [lambda v: "#ED8E87" if (v or 0) >= 0 else "#82B1F0"] * 3
    chart = R._col_chart(groups, [lambda v: R._PASTEL_UP if (v or 0) >= 0 else R._PASTEL_DN, lambda v: "#A7B4C6", lambda v: "#D9DEE7"], [R._sign_fg, lambda v: NOTE, lambda v: NOTE], height=150,
                         fmt=lambda v: f"{v:+.0f}".replace("-", "−"))
    legend = R._legend_chips([("외국인", R._PASTEL_UP), ("기관", "#A7B4C6"), ("개인", "#D9DEE7")])
    last = months[-1]
    rows = "".join(R._row_html(n, f'<span style="color:{UP if (_v(k, last) or 0) > 0 else DOWN};">{_sgn(_v(k, last) or 0, 1)}조</span>', f"{last[:4]}년 {int(last[5:])}월 순매수", first=i == 0, inline_note=True)
                   for i, (n, k) in enumerate((("외국인", "foreign"), ("기관", "inst"), ("개인", "indiv"))))
    sh = (m or {}).get("investor_share")
    if sh:
        L = sh["last"]
        rows += R._row_html("거래 비중", f'<span style="color:#111;">개인 {L["indiv"]:.0f}%</span><br><span style="font-size:{TINY};font-weight:400;color:{NOTE};">외국인 {L["foreign"]:.0f}% · 기관 {L["inst"]:.0f}%</span>',
                            f"{L['month'][:4]}년 {int(L['month'][5:])}월 매수+매도 {L['total']:,.0f}조 중 · 개인 비중 12개월 {sh['indiv_lo12']:.0f}~{sh['indiv_hi12']:.0f}% · 개인 비중이 높아지면 과열로 읽히곤 한다")
        sch = R._col_chart([(x["month"][2:].replace("-", "."), [x["indiv"], x["foreign"], x["inst"]]) for x in sh["series"][-6:]],
                           [lambda v: "#D9DEE7", lambda v: R._PASTEL_UP, lambda v: "#A7B4C6"], [lambda v: NOTE] * 3, height=120, fmt=lambda v: f"{v:.0f}")
        rows += (f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px 0;"><span style="display:block;font-weight:700;color:#111;font-size:{_dk.NAME};">거래 비중 (%) — 개인 · 외국인 · 기관</span>'
                 f'<span style="display:block;height:6px;"></span>{sch}</span>')
    tip = ("한 달 동안 외국인 · 기관 · 개인이 각각 산 금액에서 판 금액을 뺀 것(유가증권 + 코스닥), 그리고 전체 거래에서 각자가 차지한 비중. 월별 자료라 지난달까지\n"
           f"· {last[:4]}년 {int(last[5:])}월 : 외국인 {_sgn(_v('foreign', last) or 0, 1)}조 · 기관 {_sgn(_v('inst', last) or 0, 1)}조 · 개인 {_sgn(_v('indiv', last) or 0, 1)}조")
    card = f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{rows}<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px 0;">{chart}{legend}</span></span></div>'
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
        rows += R._row_html(n, f"{v / 1e12:.1f}조", f"{x['last']['month'][:4]}년 {int(x['last']['month'][5:])}월{chg} · 12개월 범위의 {pos:.0f}% 지점 · {note}", first=i == 0)
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
    return R._row_html(name, right, f"{note}{chg} · 1년 {x['lo_1y']:.2f}~{x['hi_1y']:.2f}%", first=first)


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
        rows += R._row_html(n, right, f"{note}{chg} · 1년 {x['lo_1y']:,.0f}~{x['hi_1y']:,.0f}원", first=first)
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
        rows += R._row_html("유가증권 거래대금", f'<span style="color:#111;">{eok(h["turnover"])}</span>' + (f'<br><span style="font-size:{TINY};font-weight:400;color:{NOTE};">20일 평균의 {tr:.1f}배</span>' if tr else ""),
                            f"{_md(h['day'])} · {how} 거래됐다 · 1년 중 아래에서 {h['pct_rank_1y']:.0f}% 지점", first=True)
        first = False
        if h.get("volume"):
            rows += R._row_html("유가증권 거래량", f'<span style="color:#111;">{h["volume"] / 1e4:,.1f}억 주</span>', "", inline_note=True)
        if h.get("kosdaq_turnover"):
            rows += R._row_html("코스닥 거래대금", f'<span style="color:#111;">{eok(h["kosdaq_turnover"])}</span>',
                                f"거래량 {h['kosdaq_volume'] / 1e4:,.1f}억 주" if h.get("kosdaq_volume") else "", inline_note=True)
        mc = (m or {}).get("mcap")
        if mc:
            d1 = mc.get("chg_1d")
            rows += R._row_html("유가증권 시가총액", f'<span style="color:#111;">{mc["v"] / 1e4:,.0f}조 원</span>' + (f'<br><span style="font-size:{TINY};font-weight:400;color:{UP if d1 > 0 else DOWN if d1 < 0 else NOTE};">{_sgn(d1, 2)}%</span>' if d1 is not None else ""),
                                f"시장 전체 크기 · 1년 {mc['lo_1y'] / 1e4:,.0f}~{mc['hi_1y'] / 1e4:,.0f}조의 위에서 {100 - mc['pct_rank_1y']:.0f}% 지점")
        ser = h["series"][-FLOW_CHART_N:]
        chart = R._col_chart([(str(int(x["day"][8:])), [x["v"] / 1e4]) for x in ser], [lambda v: "#CBD5E1"], [lambda v: NOTE], height=120, fmt=lambda v: f"{v:.1f}")
        rows += (f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px 0;"><span style="display:block;font-weight:700;color:#111;font-size:{_dk.NAME};">최근 {len(ser)}거래일 거래대금 (조 원) <span style="font-size:{_dk.MICRO};font-weight:400;color:{NOTE};">{_month_span(ser)}</span></span>'
                 f'<span style="display:block;height:6px;"></span>{chart}</span>')
    if n:
        d = n["v"] - n["avg_1y"]
        rows += R._row_html("뉴스심리지수", f'<span style="color:{UP if d > 0 else DOWN};">{n["v"]:.1f}</span>' + f'<br><span style="font-size:{TINY};font-weight:400;color:{NOTE};">20일 평균 {n["avg20"]:.1f}</span>',
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
    rows += R._row_html("KOSPI 주가이익비율 (PER)", f'<span style="color:#111;">{per["v"]:.1f}배</span>', f"{mo} · 12개월 {per['lo12']:.1f}~{per['hi12']:.1f}배의 {_pos(per):.0f}% 지점 · 전체 기간 평균 {per['avg_all']:.1f}배", first=True)
    if dy:
        rows += R._row_html("KOSPI 배당수익률", f'<span style="color:#111;">{dy["v"]:.2f}%</span>', f"12개월 {dy['lo12']:.2f}~{dy['hi12']:.2f}% · 전체 기간 평균 {dy['avg_all']:.2f}%")
    if tr:
        rows += R._row_html("상장주식 회전율", f'<span style="color:#111;">{tr["v"]:.1f}%</span>', f"한 달 동안 손바뀜 비율 · 12개월 {tr['lo12']:.1f}~{tr['hi12']:.1f}%")
    yg = v.get("yield_gap")
    if yg:   # K29 — 값만
        rows += R._row_html("일드갭 (배당수익률 − 국고채 3년)", f'<span style="color:{UP if yg["v"] > 0 else DOWN};">{_sgn(yg["v"], 2)}%p</span>',
                            f"국고채 3년 {yg['ktb3']:.2f}% · 양수면 배당이 채권 이자보다 높다 · 기록상 이후 KOSPI 와 관계 없음(값만)")
    ser = per["series"][-12:]
    chart = R._col_chart([(x["month"][2:].replace("-", "."), [x["v"]]) for x in ser], [lambda v: "#CBD5E1"], [lambda v: NOTE], height=120, fmt=lambda v: f"{v:.1f}")
    rows += (f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px 0;"><span style="display:block;font-weight:700;color:#111;font-size:{_dk.NAME};">최근 12개월 KOSPI PER (배)</span>'
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
    rows = R._row_html("풋/콜 거래량 비율", f'<span style="color:{UP if pc > 1 else "#111"};">{pc:.2f}</span>', f"{mo} · 1 넘으면 풋(하락 대비)이 더 많이 거래됨 · 12개월 {d['pc_lo12']:.2f}~{d['pc_hi12']:.2f}", first=True)
    fa, oa = d.get("fut_amt_avg"), d.get("opt_amt_avg")
    if fa:
        rows += R._row_html("주가지수선물 하루 거래금액", f'<span style="color:#111;">{fa["v"] / 1e6:.1f}조</span>', f"{mo} 일평균 · 12개월 {fa['lo12'] / 1e6:.1f}~{fa['hi12'] / 1e6:.1f}조")
    if oa:
        rows += R._row_html("주가지수옵션 하루 거래대금", f'<span style="color:#111;">{oa["v"] / 1e6:.2f}조</span>', f"{mo} 일평균 · 12개월 {oa['lo12'] / 1e6:.2f}~{oa['hi12'] / 1e6:.2f}조")
    ser = d["pc_series"]
    chart = R._col_chart([(x["month"][2:].replace("-", "."), [x["v"]]) for x in ser], [lambda v: "#ED8E87" if v > 1 else "#CBD5E1"], [lambda v: NOTE], height=120, fmt=lambda v: f"{v:.2f}")
    rows += (f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px 0;"><span style="display:block;font-weight:700;color:#111;font-size:{_dk.NAME};">최근 12개월 풋/콜 거래량 비율</span>'
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
            chg = (f" · 전년 같은 분기보다 {_sgn(d, 1)}%p" if x.get("quarterly") else f" · 전달보다 {_sgn(d, 1)}{'%p' if kind == 'yoy' else ''}")
        mo = f"{x['month'][:4]}년 {x['month'][5:]}분기" if x.get("quarterly") else f"{x['month'][:4]}년 {int(x['month'][5:])}월"
        rng = "최근 4분기 범위" if x.get("quarterly") else "12개월 범위"
        rows += R._row_html(name, f'<span style="color:{col};">{txt}</span>', f"{mo}{chg} · {rng}의 {pos:.0f}% 지점 · {note}", first=first)
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
        rows += R._row_html(name, right, note, first=first)
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
        chart = R._col_chart([(x["q"][2:].replace("Q", "."), [x["v"] / 1e3]) for x in sb["series"]], [R._sign_bg], [R._sign_fg], height=120, fmt=lambda v: f"{v:+.1f}".replace("-", "−"))
        rows += (f'<span style="display:block;{R.MULTI_SEP}padding:{PAD}px 12px 0;"><span style="display:block;font-weight:700;color:#111;font-size:{_dk.NAME};">최근 {len(sb["series"])}분기 가계의 국내 주식 순취득 (조 원)</span>'
                 f'<span style="display:block;height:6px;"></span>{chart}</span>')
    c = hh.get("hh_credit")
    if c:
        rows += R._row_html("가계신용 잔액", f'<span style="color:#111;">{c["v"] / 1e3:,.0f}조 원</span>', f"{_qlabel(c['q'])} · 가계 빚 전체(대출 + 카드){yoy_txt(c)} · 빠르게 늘면 살 여력이 줄어든다")
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
        rows += R._row_html(x["label"], val, note, first=first)
        first = False
    k = (m or {}).get("kospi")
    if k and k.get("ret_1d") is not None:
        rows += R._row_html("KOSPI", R._arrow(k["ret_1d"]), f"오늘 {_md(k['day'])} 종가", inline_note=True)
    w = (m or {}).get("wti")
    if w and w.get("chg_1d") is not None:
        rows += R._row_html("WTI 유가", f'<span style="color:#111;">{w["v"]:.1f}달러</span><br><span style="font-size:{TINY};font-weight:400;color:{UP if w["chg_1d"] > 0 else DOWN};">{_sgn(w["chg_1d"], 1)}%</span>',
                            f"{_md(w['day'])} · 20일 {_sgn(w['chg_n'], 1)}% · 기록상 다음날 한국전력 차이 {_sgn(U.WTI_RECORD[0], 2)}%p (종목 카드)")
    latest = [x["latest"] for x in ov if x.get("latest")]
    for l in latest:
        rows += R._row_html(f'{_esc(U.US_MARKET.get(l["sym"], l["sym"]))} {_small("그 뒤 미국 종가")}',
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
    return R._row_html(left, right, first=first).replace("<span", '<span data-row-link="1"', 1)


def list_body(a):
    top = [s for s in a["stocks"] if s["in_top"]]
    rest = [s for s in a["stocks"] if not s["in_top"] and s.get("rank") and s["rank"] <= U.PEER_GROUP_N]
    card = lambda xs: f'<div data-cards="1" style="margin:0 0 8px;"><span style="{R.MULTI}">{"".join(list_row(s, i == 0) for i, s in enumerate(xs))}</span></div>'   # noqa: E731
    tip = ("한국 유가증권시장 보통주 가운데 회사 전체 값(주가 × 주식 수)이 가장 큰 10개. 우선주 · 코스닥은 뺀다\n"
           f"· 오늘 1위 : {top[0]['name']} {cap_text(top[0]['cap'])}\n"
           f"· 나누는 법 : 11위 밖으로 {U.SWAP_DAYS}거래일 연속 밀리면 후보 중 가장 높았던 종목과 바꾼다")
    body = (list_lead(a) + updated_line(a) + R._card_title("시가총액 순위", tip) + card(top)
            + (_dk.fold(f"후보 11~{len(top) + len(rest)}위 보기", card(rest)) if rest else "")
            + _dk.muted("종목 이름을 누르면 상세 페이지로 갑니다.")
            + sec_flows(a.get("market")) + related())
    return wrap(body)


def write_all(a, out_dir, snap=None):
    os.makedirs(out_dir, exist_ok=True)
    if snap:
        draw_charts(snap, a["stocks"], out_dir)
    pages = {"list": (U.LIST_TITLE, list_body(a))}
    for s in a["stocks"]:
        pages[s["code"]] = (U.page_title(s["sym"]), detail_body(s, a))
    for key, (title, body) in pages.items():
        with open(os.path.join(out_dir, f"{key}.html"), "w", encoding="utf-8") as f:
            f.write(body)
        _dk.write_mock(body, os.path.join(out_dir, f"mock_{key}.html"), title)
    return pages
