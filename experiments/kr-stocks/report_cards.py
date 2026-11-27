"""한국 종목 실적 탭 — 분기보고서 · 잠정실적에서 읽은 것.

정식 · 간단 공통(AI 0):
  prelim_lines   `회사는 돈을 더 벌고 있나?` 맨 위 — 분기보고서보다 먼저 나온 잠정실적 숫자(dart_prelim). 보고서가 나오면 작은 글씨 한 줄(언제 먼저 나왔나)만.
  balance_card   `회사 살림은 튼튼한가?` — 재무상태표 잔액(collect_kr_fin SUMS · liab ~ recv): 부채비율 · 바로 쓸 수 있는 돈 · 빌린 돈 · 재고 · 받을 돈 · 미리 받은 돈.
정식만(Gemini lite, dart_biz):
  segment_card   `어디서 돈을 버나?` — 같은 보고서 안의 올해 누적 · 지난해 부문 비중. 부문 이름이 해마다 바뀌는 회사가 많아(삼성전자 사업부 → 제품, NAVER · 한화오션 재편) 보고서끼리 잇지 않는다.
  backlog_card   `일감은 얼마나 쌓였나?` — 수주잔고(보고서마다) · 최근 4분기 매출과 견줌. 수주를 적는 회사만.
카드는 사실만(가이드라인 1절 4-2 단일 변수 단언 금지) — 답 = 사실 그 자체(현금이 더 많음 · 늘고 있음).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
for p in (EXP, os.path.join(EXP, "nvda-report"), os.path.join(EXP, "stock-radar")):
    if p not in sys.path:
        sys.path.insert(0, p)
import design_kit as _dk  # noqa: E402
import render_html as R  # noqa: E402

SEG_COLORS = (_dk.CHART_SERIES[0], _dk.CHART_SERIES[1], _dk.CHART_SERIES[2], "#F9A8D4", "#CBD5E1")   # 부문 막대 — 주황 · 청록 · 연보라 · 분홍 · 회색(기타). 빨강 · 파랑(상승 · 하락)은 쓰지 않는다
COMPARE = "#9CA3AF"   # 비교 선(분기 매출 · 최근 4분기 매출) — 회색
CONTRACT_MIN = 0.05   # 미리 받은 돈이 최근 4분기 매출의 5% 넘을 때만 줄 · 선 (조선 · 방산 · 건설)
SEG_MIN = 0.03


def _won(v):
    if v is None:
        return "미수집"
    s = f"{v / 1e12:,.1f}조 원" if abs(v) >= 1e12 else f"{v / 1e8:,.0f}억 원"
    return s.replace("-", "−")


def _pct(a, b):
    return (a / b - 1) * 100 if a is not None and b and b > 0 and a >= 0 else None


def _md(iso):
    return f"{int(iso[5:7])}월 {int(iso[8:10])}일"


def _q_name(end):
    return {"03-31": "1분기", "06-30": "2분기", "09-30": "3분기", "12-31": "4분기"}[end[5:]]


def _rcept_day(src):
    """DART 보고서 주소의 접수번호 앞 8자리 = 접수일."""
    import re
    m = re.search(r"rcpNo=(\d{8})", src or "")
    return f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else None


# ---------------------------------------------------------------- 잠정실적

def _chg(x):
    """잠정실적 한 항목 → `1년 전보다 +12% · 직전 분기보다 −25%` (흑자 · 적자 전환은 말로)."""
    a = x["turn_y"] or (f"1년 전보다 {R._sgn(x['yoy'], 0)}%" if x.get("yoy") is not None else "")
    b = x["turn_q"] or (f"직전 분기보다 {R._sgn(x['qoq'], 0)}%" if x.get("qoq") is not None else "")
    a = a.replace("적자전환", "1년 전 흑자에서 적자 전환").replace("흑자전환", "1년 전 적자에서 흑자 전환") if x["turn_y"] else a
    b = b.replace("적자전환", "직전 분기 흑자에서 적자 전환").replace("흑자전환", "직전 분기 적자에서 흑자 전환") if x["turn_q"] else b
    return " · ".join(t for t in (a, b) if t)


def prelim_lines(p, rows):
    """→ (맨 위에 넣을 줄들, 작은 글씨 한 줄). p = dart_prelim 캐시 한 회사, rows = collect_kr_fin 분기 줄."""
    if not p or not p.get("rows"):
        return [], ""
    end = p["period"][1]
    last = rows[-1]["end"] if rows else ""
    q = f"{end[2:4]}년 {_q_name(end)}" if end[5:] in ("03-31", "06-30", "09-30", "12-31") else ""
    if end <= last:   # 보고서가 이미 나왔다 — 언제 먼저 나왔는지만
        r = next((x for x in rows if x["end"] == end), None)
        rd = _rcept_day((r or {}).get("src"))
        if not rd or rd <= p["day"]:
            return [], ""
        return [], f"{q} 숫자는 {_md(p['day'])} 잠정실적 공시로 먼저 나왔고, {_md(rd)} {r.get('form') or '분기보고서'}로 확정됐습니다."
    x = p["rows"]
    out = [(f"{q} 실적은 {_md(p['day'])} 잠정실적 공시로 먼저 나왔다. 분기보고서가 나오기 전이라 아래 그래프에는 아직 없다.", "plain")]
    for k, name in (("rev", "매출"), ("opinc", "영업이익"), ("ni", "순이익")):
        if x.get(k):
            out.append(("row", f"{name} (잠정)", _won(x[k]["q"]), _chg(x[k])))
    return out, ""


# ---------------------------------------------------------------- 재무상태표

def balance_card(name, rows, money_note="회사가 금융감독원 전자공시(DART)에 낸 분기 · 반기 · 사업보고서의 재무상태표"):
    """`회사 살림은 튼튼한가?` → (카드 HTML) 또는 "". 은행 · 보험(재고 · 매출채권 없음 · 부채비율 500% 넘음)은 뜻이 달라 두지 않는다."""
    rows = [r for r in rows or [] if r.get("liab") is not None and r.get("equity")]
    if not rows:
        return ""
    r = rows[-1]
    ago = next((x for x in rows if x["end"] == f"{int(r['end'][:4]) - 1}{r['end'][4:]}"), None)
    dr = r["liab"] / r["equity"] * 100 if r["equity"] > 0 else None
    if dr is None or (dr > 500 and r.get("inv") is None and r.get("recv") is None):
        return ""
    liquid = r.get("liquid") if r.get("liquid") is not None else r.get("cash")
    borrow = r.get("borrow")
    rev4 = sum(x.get("rev") or 0 for x in rows[-4:]) if len(rows) >= 4 else None
    net = liquid - borrow if liquid is not None and borrow is not None else None
    close = net is not None and abs(net) < max(liquid or 0, borrow or 0) * 0.05   # 5% 안이면 `비슷함` — 1.1조 대 1.1조(삼성중공업)를 한쪽으로 말하지 않는다
    state, theme, col = (("비슷함", "neutral", "#111") if close else ("현금이 더 많음", "positive", R.UP) if net is not None and net >= 0
                         else ("빌린 돈이 더 많음", "negative", R.DOWN) if net is not None else ("판단 유보", "neutral", R.MUTED))
    day = R._fd(r["end"])
    first = f"{day} 기준 {name}의 부채는 자본의 {dr:.0f}%다."
    if net is not None:
        first += (f" 바로 쓸 수 있는 돈 {_won(liquid)}이 빌린 돈 {_won(borrow)}보다 {_won(net)} 많다." if net >= 0
                  else f" 빌린 돈 {_won(borrow)}이 바로 쓸 수 있는 돈 {_won(liquid)}보다 {_won(-net)} 많다.")
    lines = [(first, "plain")]
    # 그래프 — 재고 · 받을 돈 · (미리 받은 돈) 과 분기 매출(비교, 회색). 8분기, 단위는 값 크기로
    use_c = r.get("contract") is not None and rev4 and r["contract"] >= rev4 * CONTRACT_MIN
    keys = [("inv", "재고"), ("recv", "받을 돈")] + ([("contract", "미리 받은 돈")] if use_c else [])
    bars = rows[-8:]
    keys = [(k, nm) for k, nm in keys if any(b.get(k) is not None for b in bars)]
    if keys:
        import render_kr
        vals = [b[k] for b in bars for k, _ in keys + [("rev", "")] if b.get(k) is not None]
        scale, fmt, unit = render_kr._won_chart(vals)
        ser = [(nm, [None if b.get(k) is None else b[k] / scale for b in bars], c) for (k, nm), c in zip(keys, _dk.CHART_SERIES)]
        ser.append(("분기 매출", [None if b.get("rev") is None else b["rev"] / scale for b in bars], COMPARE))
        sym = "".join(ch for ch in name if ch.isalnum()) or "x"
        chart = R.line_tabs(f"lt-{sym}-bal", [_dk.q_axis(b["cq"]) for b in bars], ser, fmt, unit)
        if chart:
            lines.append((f'{_dk.CHART_TITLE_M}분기 말 {" · ".join(nm for _, nm in keys)} · 분기 매출 ({unit})</span>{chart}', "html"))
    lines.append(("row", "부채비율 (부채 ÷ 자본)", f"{dr:.0f}%", f"1년 전 {ago['liab'] / ago['equity'] * 100:.0f}%" if ago and ago.get("liab") is not None and ago.get("equity") else "1년 전 미수집"))
    if liquid is not None:
        lines.append(("row", "바로 쓸 수 있는 돈", _won(liquid), "현금 · 단기 예금 · 단기 투자"))
    if borrow is not None:
        lines.append(("row", "빌린 돈", _won(borrow), "차입금 · 사채 (리스 빼고)"))
    rev_y = _pct(r.get("rev"), (ago or {}).get("rev"))
    for k, nm, mean in (("inv", "재고", "팔려고 쌓아 둔 물건"), ("recv", "받을 돈 (매출채권)", "팔았는데 아직 못 받은 돈")) + ((("contract", "미리 받은 돈 (계약부채)", "일을 끝내기 전에 먼저 받은 돈"),) if use_c else ()):
        if r.get(k) is None:
            continue
        g = _pct(r[k], (ago or {}).get(k))
        note = mean + (f" · 1년 전보다 {R._sgn(g, 0)}%" if g is not None else "") + (f" (같은 분기 매출 {R._sgn(rev_y, 0)}%)" if g is not None and rev_y is not None and k != "contract" else "")
        lines.append(("row", nm, _won(r[k]), note))
    if r.get("src"):
        lines.append((R.src_line(money_note, r["src"], f'DART {r.get("form") or "분기보고서"}'), "html"))
    tip = ("분기 말 하루의 잔액(재무상태표)이다. 위 카드들의 석 달 동안 움직인 돈과 다르다.\n"
           "· 부채비율 : 갚아야 할 돈 전부(부채)를 주주 몫(자본)으로 나눈 것. 업종마다 보통 수준이 다르다\n"
           "· 바로 쓸 수 있는 돈 · 빌린 돈 : 현금 · 단기 예금 · 단기 투자와, 이자를 내고 빌린 차입금 · 사채. 리스 부채는 넣지 않았다\n"
           "· 재고 · 받을 돈 : 매출보다 빨리 늘면 덜 팔리거나 돈 받기가 늦어진 것일 수 있다. 그래프에 분기 매출을 함께 그렸다\n"
           "· 미리 받은 돈 : 배 · 무기 · 건물처럼 오래 만드는 일을 맡고 먼저 받은 돈(계약부채). 늘면 앞으로 매출이 될 일감이 쌓인 것\n"
           "· 현금이 더 많음 · 빌린 돈이 더 많음 : 바로 쓸 수 있는 돈과 빌린 돈 가운데 큰 쪽, 차이가 5% 안이면 비슷함")
    return R._state_card("회사 살림은 튼튼한가?", state, theme, col, lines, "", tip=_dk.with_src(tip, "금융감독원 전자공시(OpenDART)"), fold=True)


# ---------------------------------------------------------------- 사업 부문 · 수주 (정식만)

def _segs(v):
    """보고서 하나 → [(부문, 올해, 지난해)] 큰 순. 같은 부문 줄(수출 · 내수)은 더한다."""
    acc = {}
    for x in v.get("rows") or []:
        a = acc.setdefault(x.get("seg") or "기타", [0.0, 0.0])
        a[0] += x.get("cur") or 0
        a[1] += x.get("prev") or 0
    return sorted(((k, a, b) for k, (a, b) in acc.items() if a > 0 or b > 0), key=lambda t: -t[1])


def segment_card(name, biz):
    """`어디서 돈을 버나?` — 가장 최근 보고서의 부문 비중, 올해 누적과 지난해. 부문이 하나뿐이거나(한화오션 해양 99%) 못 읽었으면 ""."""
    if not biz:
        return ""
    v = biz[-1]
    segs = _segs(v)
    tot_c, tot_p = sum(s[1] for s in segs), sum(s[2] for s in segs)
    if len([s for s in segs if tot_c and s[1] / tot_c >= SEG_MIN]) < 2:
        return ""
    big = [s for s in segs if s[1] / tot_c >= SEG_MIN][:4]
    rest = [s for s in segs if s not in big]
    if rest:
        big.append(("그 밖", sum(s[1] for s in rest), sum(s[2] for s in rest)))
    unit = {"조원": 1e12, "억원": 1e8, "백만원": 1e6, "천원": 1e3, "원": 1.0}[v["unit"]]
    cur_l = "올해 1~3월" if v["end"][5:] == "03-31" else "올해 1~6월" if v["end"][5:] == "06-30" else "올해 1~9월" if v["end"][5:] == "09-30" else f"{v['end'][:4]}년"
    prev_l = f"{int(v['end'][:4]) - 1}년" + ("" if v["end"][5:] != "12-31" else "")
    if v["end"][5:] == "12-31":
        cur_l, prev_l = f"{v['end'][:4]}년", f"{int(v['end'][:4]) - 1}년"
    top = big[0]
    sh_c, sh_p = top[1] / tot_c * 100, (top[2] / tot_p * 100 if tot_p else None)
    first = f"{cur_l} {name} 매출 {_won(tot_c * unit)} 가운데 {_dk.josa(top[0], '이')} {sh_c:.0f}%로 가장 컸다."
    if sh_p is not None:
        first += f" {prev_l}에는 {sh_p:.0f}%였다."
    segcols = [(nm, c, p, col) for (nm, c, p), col in zip(big, SEG_COLORS[:len(big) - (1 if rest else 0)] + ((SEG_COLORS[-1],) if rest else ()))]
    bar = lambda lab, idx: _dk.legend_bar(lab, [(nm, (c if idx == 0 else p), col, "#111") for nm, c, p, col in segcols])   # noqa: E731
    chart = bar(cur_l, 0) + (f'<span style="display:block;height:{_dk.BAR_GROUP_GAP - 5}px;"></span>' + bar(prev_l, 1) if tot_p else "")
    card = f'<span style="{R.MULTI}margin:0 {_dk.CHART_CARD_X}px;"><span style="display:block;padding:{_dk.CHART_CARD_PAD}px 12px;">{chart}</span></span>'
    lines = [(first, "plain"), (f'{_dk.CHART_TITLE_M}사업 부문별 매출 비중 (%)</span>{card}', "html")]
    for nm, c, p, _ in segcols:
        note = f"비중 {c / tot_c * 100:.0f}%" + (f" · {prev_l} {p / tot_p * 100:.0f}%" if tot_p else "")
        lines.append(("row", nm, _won(c * unit), note))
    R.add_small_note(lines, f"회사가 분기보고서에 적은 부문 이름 그대로입니다. {cur_l}은 누적, {prev_l}은 한 해 전체라 금액보다 비중을 견줍니다.")
    state = f"{top[0]} {sh_c:.0f}%"
    return R._state_card("어디서 돈을 버나?", state, "neutral", "#111", lines, "", tip="", fold=True)


def backlog_card(name, biz, rows):
    """`일감은 얼마나 쌓였나?` — 보고서마다 수주잔고, 비교 = 최근 4분기 매출. 수주를 적는 회사만."""
    pts = [(v["end"], v["backlog"]["total"] * {"조원": 1e12, "억원": 1e8, "백만원": 1e6, "천원": 1e3, "원": 1.0}[v["unit"]])
           for v in biz or [] if v.get("backlog") and v["backlog"].get("total")]
    if len(pts) < 2:
        return ""
    rev4 = {}
    for i in range(3, len(rows or [])):
        if all(rows[j].get("rev") is not None for j in range(i - 3, i + 1)):
            rev4[rows[i]["end"]] = sum(rows[j]["rev"] for j in range(i - 3, i + 1))
    end, bl = pts[-1]
    prev_end, prev_bl = pts[-2]
    chg = (bl / prev_bl - 1) * 100
    state, theme, col = ("늘고 있음", "positive", R.UP) if chg > 3 else ("줄고 있음", "negative", R.DOWN) if chg < -3 else ("그대로", "neutral", "#111")
    yrs = bl / rev4[end] if rev4.get(end) else None
    first = (f"{R._fd(end)} 기준 {name}의 수주잔고(받아 놓고 아직 만들지 않은 일감)는 {_won(bl)}으로, 석 달 전보다 "
             + (f"{abs(chg):.0f}% {'늘었다' if chg > 0 else '줄었다'}." if round(chg) else "거의 그대로다."))
    if yrs:
        first += f" 최근 4분기 매출로 나누면 약 {yrs:.1f}년치 일감이다."
    import render_kr
    vals = [b for _, b in pts] + [rev4[e] for e, _ in pts if rev4.get(e)]
    scale, fmt, unit = render_kr._won_chart(vals)
    ser = [("수주잔고", [b / scale for _, b in pts], _dk.CHART_MAIN), ("최근 4분기 매출", [rev4[e] / scale if rev4.get(e) else None for e, _ in pts], COMPARE)]
    sym = "".join(ch for ch in name if ch.isalnum()) or "x"
    chart = R.line_tabs(f"lt-{sym}-backlog", [_dk.q_axis(f"{e[:4]}Q{int(e[5:7]) // 3}") for e, _ in pts], ser, fmt, unit)
    lines = [(first, "plain")]
    if chart:
        lines.append((f'{_dk.CHART_TITLE_M}분기 말 수주잔고 · 최근 4분기 매출 ({unit})</span>{chart}', "html"))
    lines.append(("row", "수주잔고", _won(bl), f"{R._fd(end)} 기준 · 석 달 전 {_won(prev_bl)}"))
    if yrs:
        lines.append(("row", "몇 년치 일감", f"약 {yrs:.1f}년", "수주잔고 ÷ 최근 4분기 매출"))
    items = [it for it in (biz[-1].get("backlog") or {}).get("items") or [] if it.get("v")]
    for it in items if len(items) > 1 else []:   # 품목이 하나뿐이면 합계 줄과 같다 — 빼기
        if True:
            lines.append(("row", it["name"], _won(it["v"] * {"조원": 1e12, "억원": 1e8, "백만원": 1e6, "천원": 1e3, "원": 1.0}[biz[-1]["unit"]]), "품목별 수주잔고"))
    R.add_small_note(lines, "회사가 분기보고서 `매출 및 수주상황`에 적은 수주잔고입니다.")
    tip = ("수주잔고 : 계약은 했지만 아직 만들어 넘기지 않은 일의 남은 금액. 배 · 무기 · 발전 설비처럼 몇 년에 걸쳐 만드는 회사는 이 값이 앞으로의 매출이 된다.\n"
           "· 몇 년치 일감 : 수주잔고를 최근 4분기 매출로 나눈 것. 지금 속도로 만들면 몇 년 걸릴 일이 쌓였는지\n"
           "· 늘고 있음 · 줄고 있음 : 석 달 전보다 3% 넘게 늘거나 줄면")
    return R._state_card("일감은 얼마나 쌓였나?", state, theme, col, lines, "", tip=_dk.with_src(tip, "금융감독원 전자공시(OpenDART) 분기보고서"), fold=True)
