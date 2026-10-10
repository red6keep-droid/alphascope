"""이벤트 판정(6절) · 상태판(7절) · 다가오는 것 · 점검표(8절) → output/nvda_analysis.json.

전부 파이썬. Gemini는 여기 없다. 이 JSON이 render_report(MD)·render_html·narrate의 유일한 입력이다.
"""

import datetime
import json
import os

import collect_calendar
import collect_edgar
import collect_market
import config
import db
import indicators

TECH_FIELDS = ["close", "ret_1d", "ret_vs_spy", "ret_vs_smh", "ret_vs_amd", "ret_vs_qqq", "gap", "range_pct",
               "volume", "vol_ratio_20d", "ma50", "ma200", "pct_from_52w_high", "rsi14", "ma_cross"]
KIND_PRIORITY = {"8k": 0, "10q": 0, "10k": 0, "form4": 1, "fedreg": 1, "court": 1, "calendar": 2, "newsroom": 2,
                 "analyst": 3, "news": 3, "blog": 3, "price": 4, "options": 5, "estimates": 6, "flows": 7, "news_volume": 8}


def update_technicals(conn):
    """일봉 → daily_state의 가격·거래량·기술 칸. 전 기간을 다시 계산한다 (결정적이라 멱등)."""
    bars = {s: collect_market.bars(conn, s) for s in config.SYMBOLS}
    rows = indicators.technical_rows(bars)
    for r in rows:
        row = {k: r.get(k) for k in TECH_FIELDS}
        row["day"] = r["day"]
        db.upsert(conn, "daily_state", row, ("day",))
    conn.commit()
    return len(rows)


def _state(conn, day):
    r = conn.execute("SELECT * FROM daily_state WHERE day = ?", (day,)).fetchone()
    return dict(r) if r else None


def _prev_state(conn, day):
    r = conn.execute("SELECT * FROM daily_state WHERE day < ? ORDER BY day DESC LIMIT 1", (day,)).fetchone()
    return dict(r) if r else None


def iv_rank(conn, day):
    vals = [r["iv_atm_30d"] for r in conn.execute(
        "SELECT iv_atm_30d FROM daily_state WHERE day <= ? AND iv_atm_30d IS NOT NULL ORDER BY day DESC LIMIT ?",
        (day, config.IV_RANK_WINDOW))]
    n = len(vals)
    if n < config.IV_RANK_WINDOW:
        return None, n
    cur, lo, hi = vals[0], min(vals), max(vals)
    return ((cur - lo) / (hi - lo) * 100 if hi > lo else 50.0), n


def _ev(area, kind, title, fact=None, url=None, direction="neutral", emphasis=False, source=None, published_at=None):
    return {"area": area, "kind": kind, "title": title, "fact": fact or title, "url": url, "direction": direction,
            "emphasis": emphasis, "source": source, "published_at": published_at}


def price_events(s):
    out = []
    if s.get("vol_ratio_20d") and s["vol_ratio_20d"] >= config.VOL_RATIO_EVENT:
        out.append(_ev("Flows", "price", f"거래량 20일 평균의 {s['vol_ratio_20d']:.1f}배",
                       f"거래량 {s['volume'] / 1e6:,.0f}M주 — 20일 평균 대비 {s['vol_ratio_20d']:.1f}배 (임계 {config.VOL_RATIO_EVENT}배)",
                       source="yfinance"))
    if s.get("range_pct") and s["range_pct"] >= config.RANGE_PCT_EVENT:
        out.append(_ev("Flows", "price", f"일중 변동폭 {s['range_pct']:.1f}%",
                       f"고가−저가가 종가의 {s['range_pct']:.1f}% (임계 {config.RANGE_PCT_EVENT}%)", source="yfinance"))
    if s.get("ret_vs_spy") is not None and abs(s["ret_vs_spy"]) >= config.REL_SPY_EVENT:
        d = "positive" if s["ret_vs_spy"] > 0 else "negative"
        out.append(_ev("Flows", "price", f"SPY 대비 {s['ret_vs_spy']:+.1f}%p",
                       f"NVDA {s['ret_1d']:+.2f}% · SPY 대비 {s['ret_vs_spy']:+.2f}%p (임계 ±{config.REL_SPY_EVENT}%p)",
                       direction=d, source="yfinance"))
    if s.get("ma_cross"):
        name = "골든 크로스" if s["ma_cross"] == "golden" else "데드 크로스"
        out.append(_ev("Flows", "price", f"50/200일선 {name}",
                       f"50일선 ${s['ma50']:,.2f} · 200일선 ${s['ma200']:,.2f}",
                       direction="positive" if s["ma_cross"] == "golden" else "negative", emphasis=True, source="yfinance"))
    return out


def near_high_event(conn, day, s):
    """52주 고점 −2% 이내 '진입일'만 — 전일은 밖이고 오늘 안이면."""
    if s.get("pct_from_52w_high") is None or s["pct_from_52w_high"] < config.NEAR_52W_HIGH_PCT:
        return []
    p = _prev_state(conn, day)
    if p and p.get("pct_from_52w_high") is not None and p["pct_from_52w_high"] >= config.NEAR_52W_HIGH_PCT:
        return []
    return [_ev("Flows", "price", "52주 고점권 진입", f"52주 고점 대비 {s['pct_from_52w_high']:+.1f}%",
                direction="positive", source="yfinance")]


def _extreme(rank):
    return rank is not None and (rank >= config.IV_RANK_HIGH or rank <= config.IV_RANK_LOW)


def option_events(conn, day, s, rank):
    out = []
    p = _prev_state(conn, day)
    # IV 랭크는 상태값이라 극단에 '들어간 날'만 이벤트 (전일도 극단이면 상태판 굵은 글씨로만)
    if _extreme(rank) and not (p and _extreme(p.get("iv_rank_60d"))):
        out.append(_ev("Flows", "options", f"IV 랭크 {rank:.0f}",
                       f"ATM 30일 IV {s['iv_atm_30d'] * 100:.1f}% — 60일 랭크 {rank:.0f} (임계 ≥{config.IV_RANK_HIGH} 또는 ≤{config.IV_RANK_LOW})",
                       source="yfinance options"))
    if p and p.get("pc_ratio_oi") and s.get("pc_ratio_oi"):
        chg = s["pc_ratio_oi"] / p["pc_ratio_oi"] - 1
        if abs(chg) >= config.PC_RATIO_CHG_EVENT:
            out.append(_ev("Flows", "options", f"풋/콜 비율(OI) 전일 대비 {chg * 100:+.0f}%",
                           f"P/C(OI) {p['pc_ratio_oi']:.2f} → {s['pc_ratio_oi']:.2f} (임계 ±{config.PC_RATIO_CHG_EVENT * 100:.0f}%)",
                           direction="negative" if chg > 0 else "positive", source="yfinance options"))
    # 특정 행사가 OI 급증 — 직전 스냅샷 날과 비교
    prev_day = conn.execute("SELECT MAX(day) FROM option_snapshots WHERE day < ?", (day,)).fetchone()[0]
    if prev_day:
        prev = {(r["expiry"], r["strike"]): r for r in conn.execute(
            "SELECT expiry, strike, call_oi, put_oi FROM option_snapshots WHERE day = ?", (prev_day,))}
        jumps = []
        for r in conn.execute("SELECT expiry, strike, call_oi, put_oi FROM option_snapshots WHERE day = ?", (day,)):
            q = prev.get((r["expiry"], r["strike"]))
            if not q:
                continue
            for side in ("call_oi", "put_oi"):
                cur, before = r[side] or 0, q[side] or 0
                if cur >= config.OI_JUMP_MIN and before > 0 and cur / before >= config.OI_JUMP_MULT:
                    jumps.append((cur / before, r["expiry"], r["strike"], side, before, cur))
        jumps.sort(reverse=True)
        for mult, exp, k, side, before, cur in jumps[:3]:
            lab = "콜" if side == "call_oi" else "풋"
            out.append(_ev("Flows", "options", f"{exp} ${k:,.0f} {lab} OI {mult:.1f}배",
                           f"미결제약정 {before:,.0f} → {cur:,.0f} (임계 {config.OI_JUMP_MULT}배 · OI ≥ {config.OI_JUMP_MIN:,})",
                           direction="positive" if lab == "콜" else "negative", source="yfinance options"))
    return out


def _revision_skew(s):
    """30일 상향:하향 비가 임계를 넘는 쪽. 'up' · 'down' · None."""
    up, down = s.get("revisions_up_30d"), s.get("revisions_down_30d")
    if up is None or down is None or (up + down) < 4:
        return None
    if (down == 0 and up >= 3) or (down and up / down >= config.REVISION_RATIO_EVENT):
        return "up"
    if (up == 0 and down >= 3) or (up and down / up >= config.REVISION_RATIO_EVENT):
        return "down"
    return None


def estimate_events(conn, day, s):
    out = []
    for key, lab in (("eps_est_cq_7d_chg_pct", "EPS"), ("rev_est_cq_7d_chg_pct", "매출")):
        v = s.get(key)
        if v is not None and abs(v) >= config.EST_CHG_EVENT_PCT:
            out.append(_ev("Earnings", "estimates", f"당분기 {lab} 컨센서스 7일 {v:+.1f}%",
                           f"{lab} 컨센서스가 7일 전 대비 {v:+.2f}% 이동 (임계 ±{config.EST_CHG_EVENT_PCT}%)",
                           direction="positive" if v > 0 else "negative", source="yfinance"))
    # 상향/하향 쏠림은 30일 누적 상태값 — 쏠림이 '생긴 날'만 이벤트, 이어지는 동안은 상태판에만
    skew = _revision_skew(s)
    p = _prev_state(conn, day)
    if skew and not (p and _revision_skew(p) == skew):
        up, down = s["revisions_up_30d"], s["revisions_down_30d"]
        if skew == "up":
            out.append(_ev("Earnings", "estimates", f"30일 EPS 상향 {up} · 하향 {down}",
                           f"상향:하향 비 {up}:{down} (임계 {config.REVISION_RATIO_EVENT:.0f}:1)", direction="positive", source="yfinance"))
        else:
            out.append(_ev("Earnings", "estimates", f"30일 EPS 상향 {up} · 하향 {down}",
                           f"하향:상향 비 {down}:{up} (임계 {config.REVISION_RATIO_EVENT:.0f}:1)", direction="negative", source="yfinance"))
    return out


def flow_events(conn, day, s):
    out = []
    p = _prev_state(conn, day)
    if s.get("shares_short") and s.get("shares_short_prior"):
        chg = (s["shares_short"] / s["shares_short_prior"] - 1) * 100
        if abs(chg) >= config.SHORT_INTEREST_CHG_EVENT_PCT and (not p or p.get("short_asof") != s.get("short_asof")):
            out.append(_ev("Flows", "flows", f"공매도 잔고 전 회차 대비 {chg:+.0f}%",
                           f"{s['shares_short_prior'] / 1e6:,.1f}M → {s['shares_short'] / 1e6:,.1f}M주 (기준 {s.get('short_asof')}, 임계 ±{config.SHORT_INTEREST_CHG_EVENT_PCT:.0f}%)",
                           direction="negative" if chg > 0 else "positive", source="yfinance"))
    return out


def item_events(conn, day):
    """공시·애널리스트·(②단계부터) 문서. 아직 어느 리포트에도 안 오른 것 + 오늘 리포트에 오른 것 (재실행 멱등).

    지난 리포트 날짜(meta last_report_day) 이후에 나온 것만 "오늘 바뀐 것"이다. 첫 실행의 90일 백필처럼
    그보다 오래된 미보고 항목은 reported_on='backfill'로 접어 두고 점검표 집계(내부자 순매도)에만 쓴다.
    """
    last = db.get_meta(conn, "last_report_day")
    if last and last < day:
        cutoff = last
    else:
        cutoff = (datetime.date.fromisoformat(day) - datetime.timedelta(days=config.EVENT_ITEM_MAX_AGE_DAYS)).isoformat()
    conn.execute("UPDATE items SET reported_on = 'backfill' WHERE reported_on IS NULL AND analyzed_at IS NOT NULL AND published_at < ?",
                 (cutoff,))
    rows = conn.execute(
        """SELECT * FROM items WHERE prefilter_reason IS NULL AND analyzed_at IS NOT NULL
             AND (reported_on IS NULL OR reported_on = ?) ORDER BY published_at DESC""", (day,)).fetchall()
    events, target_only = [], []
    for r in rows:
        raw = db.loads(r["raw_json"], {}) or {}
        if r["kind"] == "analyst" and not r["is_event"]:
            target_only.append({"title": r["title"], "published_at": r["published_at"], "direction": r["ai_direction"]})
            continue
        if not r["is_event"]:
            continue
        emphasis = False
        if r["kind"] == "form4":
            info = raw.get("form4") or {}
            # 강조: 계획 외 매도 · 매수 · 10% 보유자. 10b5-1 매도와 세금 납부·부여·증여는 금액만.
            emphasis = bool(info and ((info.get("shares_sold") and not info.get("is_plan"))
                                      or info.get("shares_bought") or info.get("is_ten_percent")))
        elif r["kind"] in ("8k", "10q", "10k"):
            emphasis = True
        elif r["kind"] in config.CLASSIFY_KINDS:
            emphasis = (r["ai_relevance"] or 0) >= 3 or (r["ai_area"] in config.PRIORITY_AREAS)
        events.append(_ev(r["ai_area"] or "Corporate", r["kind"], r["title"], r["ai_fact"] or r["summary"], r["url"],
                          r["ai_direction"] or "neutral", emphasis, r["source"], r["published_at"]))
    conn.execute("UPDATE items SET reported_on = ? WHERE reported_on IS NULL AND analyzed_at IS NOT NULL", (day,))
    db.set_meta(conn, "last_report_day", day)
    conn.commit()
    return events, target_only


def news_count(conn, day):
    """기준일에 나온 NVDA 기사 수(repeat·중복 포함, 키워드 탈락 제외) vs 직전 7일 하루 평균 (#48 헤드라인 톤)."""
    def count(d0, d1):
        return conn.execute(
            """SELECT COUNT(*) FROM items WHERE kind IN ('news','newsroom','blog')
                 AND (prefilter_reason IS NULL OR prefilter_reason LIKE 'duplicate_of:%')
                 AND published_at >= ? AND published_at < ?""", (d0, d1)).fetchone()[0]
    d = datetime.date.fromisoformat(day)
    today = count(day, (d + datetime.timedelta(days=1)).isoformat())
    week = count((d - datetime.timedelta(days=7)).isoformat(), day)
    # 수집 시작 전 날짜는 평균에서 뺀다
    first = conn.execute("SELECT MIN(published_at) FROM items WHERE kind IN ('news','newsroom','blog')").fetchone()[0]
    days = 7
    if first:
        covered = (d - max(d - datetime.timedelta(days=7), datetime.date.fromisoformat(first[:10]))).days
        days = max(min(covered, 7), 1)
    avg = week / days if week else None
    conn.execute("UPDATE daily_state SET news_count = ? WHERE day = ?", (today, day))
    conn.commit()
    return today, avg


def news_events(today, avg):
    if avg and avg > 0 and today >= 5 and today / avg >= config.NEWS_COUNT_EVENT_MULT:
        return [_ev("Other", "news_volume", f"NVDA 기사 수 7일 평균의 {today / avg:.1f}배",
                    f"기준일 {today}건 · 직전 7일 하루 평균 {avg:.1f}건 (임계 {config.NEWS_COUNT_EVENT_MULT:.0f}배)", source="rss")]
    return []


def upcoming_with_court(conn, day):
    """7일 창 전체 + 30일 창의 법원 일정(COURT)만. 날짜순."""
    rows = collect_calendar.upcoming(conn, day)
    seen = {(r["day"], r["kind"], r["label"]) for r in rows}
    for r in collect_calendar.upcoming(conn, day, config.COURT_LOOKAHEAD_DAYS):
        if r["kind"] == "COURT" and (r["day"], r["kind"], r["label"]) not in seen:
            rows.append(r)
    return sorted(rows, key=lambda r: (r["day"], r["kind"]))


def calendar_events(conn, day):
    out = []
    d0 = datetime.date.fromisoformat(day)
    nxt = collect_calendar.next_of(conn, "EARNINGS", day, config.SYMBOL)
    if nxt:
        diff = (datetime.date.fromisoformat(nxt) - d0).days
        if diff == 0:
            out.append(_ev("Earnings", "calendar", "NVDA 실적 발표일 (D0, 장 마감 후)", direction="uncertain", emphasis=True, source="calendar"))
        elif diff == 1:
            out.append(_ev("Earnings", "calendar", "NVDA 실적 발표 D-1", direction="uncertain", emphasis=True, source="calendar"))
    prev = conn.execute("SELECT MAX(day) FROM calendar WHERE kind = 'EARNINGS' AND symbol = ? AND day < ?",
                        (config.SYMBOL, day)).fetchone()[0]
    if prev and (d0 - datetime.date.fromisoformat(prev)).days == 1:
        out.append(_ev("Earnings", "calendar", "NVDA 실적 발표 다음 날 (D+1)", direction="uncertain", emphasis=True, source="calendar"))
    for c in collect_calendar.on_day(conn, day):
        if c["kind"] == "EARNINGS_PEER":
            out.append(_ev("Earnings", "calendar", f"{c['symbol']} 실적 발표일", source="calendar"))
        elif c["kind"] == "FOMC":
            out.append(_ev("Macro", "calendar", "FOMC 결정일", source="calendar"))
        elif c["kind"] == "COURT":
            out.append(_ev("Legal", "calendar", f"⚠ 오늘 {c['label']}", direction="uncertain", emphasis=True, source="calendar"))
        elif c["kind"] in ("TSMC_REV", "EVENT", "INDEX"):
            out.append(_ev("Supply" if c["kind"] == "TSMC_REV" else ("Product" if c["kind"] == "EVENT" else "Flows"),
                           "calendar", c["label"], source="calendar"))
    return out


def checklist(conn, day, s):
    """8절 점검표. ①단계에서 채워지는 것: forward_pe · insider_net_sold_90d · institutional_top10. 나머지는 미수집."""
    rows = []

    def add(metric, label, value=None, unit=None, asof=None, source=None, note=None, arrow=None, detail=None):
        rows.append({"metric": metric, "label": label, "value": value, "unit": unit, "asof": asof,
                     "source": source, "note": note, "arrow": arrow, "detail": detail})

    later = [("dc_revenue", "데이터센터 매출"), ("dc_revenue_yoy", "데이터센터 매출 YoY"), ("gross_margin_nongaap", "총마진 (non-GAAP)"),
             ("guidance_revenue_next", "다음 분기 매출 가이던스"), ("guidance_beat_pct", "가이던스 대비 실제"),
             ("china_revenue_pct", "중국 매출 비중"), ("top_customer_pct", "10% 이상 고객 비중"), ("buyback_amount", "분기 자사주 매입"),
             ("hyperscaler_capex_guidance", "하이퍼스케일러 capex 가이던스"), ("tsmc_revenue_yoy_3m", "TSMC 3개월 매출 YoY")]
    for m, lab in later:
        q = conn.execute("SELECT * FROM quarterly WHERE metric = ? ORDER BY fiscal_quarter DESC LIMIT 2", (m,)).fetchall()
        if q:
            cur = dict(q[0])
            arrow = None
            if len(q) > 1 and q[1]["value"] is not None and cur["value"] is not None:
                arrow = "↑" if cur["value"] > q[1]["value"] else ("↓" if cur["value"] < q[1]["value"] else "→")
            add(m, lab, cur["value"], cur["unit"], cur["fiscal_quarter"], cur["source"], arrow=arrow)
        else:
            add(m, lab, note="미수집 (④단계)")
    ins = collect_edgar.insider_net_sold(conn, day)
    add("insider_net_sold_90d", "90일 내부자 순매도", ins["net_sold_usd"], "USD", day, "EDGAR Form 4",
        detail=f"매도 ${ins['sold_usd'] / 1e6:,.1f}M · 매수 ${ins['bought_usd'] / 1e6:,.1f}M · 공시 {ins['filings']}건 (10b5-1 {ins['plan_filings']}건)")
    q = conn.execute("SELECT * FROM quarterly WHERE metric = 'institutional_top10' ORDER BY fiscal_quarter DESC LIMIT 2").fetchall()
    if q:
        cur = dict(q[0])
        arrow = None
        if len(q) > 1 and q[1]["value"] is not None:
            arrow = "↑" if cur["value"] > q[1]["value"] else ("↓" if cur["value"] < q[1]["value"] else "→")
        holders = db.loads(cur["value_json"])
        top3 = ", ".join(f"{h['holder']} {h['pct_held']:.1f}%" + (f" ({h['pct_change']:+.1f}%)" if h.get("pct_change") is not None else "")
                         for h in holders[:3])
        add("institutional_top10", "기관 상위 10곳 보유 합", cur["value"], "%", cur["fiscal_quarter"], "yfinance (13F 요약)", arrow=arrow, detail=top3)
    else:
        add("institutional_top10", "기관 상위 10곳 보유 합", note="미수집")
    add("forward_pe", "선행 PER (현재가 ÷ 12개월 선행 EPS)", s.get("forward_pe"), "배", day, "yfinance",
        note=None if s.get("forward_pe") else "미수집")
    n_pe = conn.execute("SELECT COUNT(*) FROM daily_state WHERE forward_pe IS NOT NULL").fetchone()[0]
    add("forward_pe_1y_pct", "선행 PER 1년 분위", note=f"집계 중 ({n_pe}/252일)" if n_pe < 252 else None,
        value=_percentile(conn, "forward_pe", s.get("forward_pe"), 252) if n_pe >= 252 else None, unit="분위")
    return rows


def _percentile(conn, col, value, n):
    if value is None:
        return None
    vals = [r[0] for r in conn.execute(f"SELECT {col} FROM daily_state WHERE {col} IS NOT NULL ORDER BY day DESC LIMIT ?", (n,))]
    return sum(1 for v in vals if v <= value) / len(vals) * 100 if vals else None


def status_board(s, rank, rank_n):
    """상태판 숫자 + 임계 초과 플래그. 렌더는 flag가 True인 칸을 굵게."""
    def cell(key, value, flag=False, fmt=None):
        return {"key": key, "value": value, "flag": bool(flag), "fmt": fmt}
    rc = db.loads(s.get("rating_counts_json"), {}) or {}
    return {
        "price": [
            cell("close", s.get("close"), fmt="usd"), cell("ret_1d", s.get("ret_1d"), fmt="pct_signed"),
            cell("ret_vs_spy", s.get("ret_vs_spy"), abs(s.get("ret_vs_spy") or 0) >= config.REL_SPY_EVENT, "pp_signed"),
            cell("ret_vs_smh", s.get("ret_vs_smh"), fmt="pp_signed"), cell("ret_vs_amd", s.get("ret_vs_amd"), fmt="pp_signed"),
            cell("gap", s.get("gap"), fmt="pct_signed"),
            cell("range_pct", s.get("range_pct"), (s.get("range_pct") or 0) >= config.RANGE_PCT_EVENT, "pct"),
            cell("vol_ratio_20d", s.get("vol_ratio_20d"), (s.get("vol_ratio_20d") or 0) >= config.VOL_RATIO_EVENT, "x"),
        ],
        "technical": [
            cell("ma50", s.get("ma50"), fmt="usd"), cell("ma200", s.get("ma200"), fmt="usd"),
            cell("pct_from_52w_high", s.get("pct_from_52w_high"), (s.get("pct_from_52w_high") or -99) >= config.NEAR_52W_HIGH_PCT, "pct_signed"),
            cell("rsi14", s.get("rsi14"), fmt="num1"), cell("ma_cross", s.get("ma_cross"), bool(s.get("ma_cross")), "text"),
        ],
        "options": [
            cell("iv_atm_30d", s.get("iv_atm_30d"), fmt="iv"),
            cell("iv_rank_60d", rank, rank is not None and (rank >= config.IV_RANK_HIGH or rank <= config.IV_RANK_LOW), "num0"),
            cell("implied_move_next_earnings", s.get("implied_move_next_earnings"), fmt="pct"),
            cell("pc_ratio_oi", s.get("pc_ratio_oi"), fmt="num2"), cell("pc_ratio_vol", s.get("pc_ratio_vol"), fmt="num2"),
            cell("gex_approx", s.get("gex_approx"), fmt="gex"), cell("gex_flip_strike", s.get("gex_flip_strike"), fmt="usd0"),
            cell("max_oi_strike_call", s.get("max_oi_strike_call"), fmt="usd0"), cell("max_oi_strike_put", s.get("max_oi_strike_put"), fmt="usd0"),
        ],
        "estimates": [
            cell("eps_est_cq", s.get("eps_est_cq"), fmt="usd2"),
            cell("eps_est_cq_7d_chg_pct", s.get("eps_est_cq_7d_chg_pct"), abs(s.get("eps_est_cq_7d_chg_pct") or 0) >= config.EST_CHG_EVENT_PCT, "pct_signed2"),
            cell("rev_est_cq", s.get("rev_est_cq"), fmt="usd_bn"),
            cell("rev_est_cq_7d_chg_pct", s.get("rev_est_cq_7d_chg_pct"), abs(s.get("rev_est_cq_7d_chg_pct") or 0) >= config.EST_CHG_EVENT_PCT, "pct_signed2"),
            cell("revisions_up_30d", s.get("revisions_up_30d"), fmt="int"), cell("revisions_down_30d", s.get("revisions_down_30d"), fmt="int"),
        ],
        "analysts": [
            cell("rating_counts", rc or None, fmt="ratings"), cell("pt_mean", s.get("pt_mean"), fmt="usd0"),
            cell("pt_median", s.get("pt_median"), fmt="usd0"), cell("pt_high", s.get("pt_high"), fmt="usd0"), cell("pt_low", s.get("pt_low"), fmt="usd0"),
        ],
        "flows": [
            cell("smh_shares_out", s.get("smh_shares_out"), fmt="int"), cell("soxx_shares_out", s.get("soxx_shares_out"), fmt="int"),
            cell("shares_short", s.get("shares_short"), fmt="shares_m"), cell("short_pct_float", s.get("short_pct_float"), fmt="pct2"),
            cell("short_asof", s.get("short_asof"), fmt="text"),
        ],
        "valuation": [cell("forward_pe", s.get("forward_pe"), fmt="num1")],
        "iv_rank_n": rank_n,
    }


def build(conn, day, run_date):
    update_technicals(conn)
    s = _state(conn, day)
    if not s:
        raise RuntimeError(f"daily_state에 {day} 행이 없다 — 일봉부터 확인")
    rank, rank_n = iv_rank(conn, day)
    if rank is not None:
        conn.execute("UPDATE daily_state SET iv_rank_60d = ? WHERE day = ?", (rank, day))
        conn.commit()
    item_evs, target_only = item_events(conn, day)
    n_news, news_avg = news_count(conn, day)
    events = (item_evs + calendar_events(conn, day) + price_events(s) + near_high_event(conn, day, s)
              + option_events(conn, day, s, rank) + estimate_events(conn, day, s) + flow_events(conn, day, s)
              + news_events(n_news, news_avg))
    # 강조 → 종류 우선순위 → 같은 종류 안에서는 최신이 위 (안정 정렬 두 번)
    events.sort(key=lambda e: e.get("published_at") or "", reverse=True)
    events.sort(key=lambda e: (0 if e["area"] in config.PRIORITY_AREAS else 1, 0 if e["emphasis"] else 1, KIND_PRIORITY.get(e["kind"], 9)))
    body, overflow = events[:config.MAX_EVENTS_IN_BODY], events[config.MAX_EVENTS_IN_BODY:]
    macro_today = [c for c in collect_calendar.on_day(conn, day) if c["kind"] in ("FOMC", "CPI", "NFP", "GDP", "PCE")]
    bars_last = collect_market.last_bar_day(conn)
    missing = db.loads(s.get("missing_fields_json"))
    n_snap_days = conn.execute("SELECT COUNT(DISTINCT day) FROM option_snapshots").fetchone()[0]
    n_items = {r["kind"]: r["n"] for r in conn.execute("SELECT kind, COUNT(*) n FROM items GROUP BY kind")}
    cases = [dict(r) for r in conn.execute("SELECT * FROM cases WHERE watch = 1 ORDER BY opened_at")]
    for c in cases:
        import cases_watch
        nxt = conn.execute("SELECT day, label FROM calendar WHERE kind = 'COURT' AND label LIKE ? AND day >= ? ORDER BY day LIMIT 1",
                           (cases_watch.short_name(c) + " — %", day)).fetchone()
        c["short_name"] = cases_watch.short_name(c)
        c["next_day"] = nxt["day"] if nxt else None
        c["next_label"] = nxt["label"].split(" — ", 1)[-1] if nxt else None
    analysis = {
        "generated_at": db.now_iso(), "run_date": run_date, "day": day,
        "is_latest_bar_today": bars_last == day,
        "headline": {k: s.get(k) for k in ("close", "ret_1d", "ret_vs_spy", "ret_vs_smh", "ret_vs_amd", "vol_ratio_20d", "gap")},
        "macro_today": [c["label"] for c in macro_today],
        "events": body, "events_overflow": overflow, "events_total": len(events),
        "analyst_target_only": target_only,
        "upcoming": upcoming_with_court(conn, day),
        "next_earnings": collect_calendar.next_of(conn, "EARNINGS", day, config.SYMBOL),
        "status": dict(status_board(s, rank, rank_n), news=[
            {"key": "news_count", "value": n_news, "flag": bool(news_avg and n_news >= 5 and n_news / news_avg >= config.NEWS_COUNT_EVENT_MULT), "fmt": "int"},
            {"key": "news_avg_7d", "value": news_avg, "flag": False, "fmt": "num1"},
            {"key": "news_pending", "value": conn.execute(
                "SELECT COUNT(*) FROM items WHERE kind IN ('news','newsroom','blog','fedreg','court') AND prefilter_reason IS NULL AND analyzed_at IS NULL"
            ).fetchone()[0], "flag": False, "fmt": "int"},
        ]),
        "cases": cases,
        "checklist": checklist(conn, day, s),
        "data_status": {"bars_last_day": bars_last, "state_collected_at": s.get("collected_at"), "missing_fields": missing,
                        "option_snapshot_days": n_snap_days, "iv_rank_days": rank_n, "items_by_kind": n_items,
                        "option_expiries": db.loads(s.get("option_expiries"))},
        "thresholds": {k: getattr(config, k) for k in dir(config) if k.endswith("_EVENT") or k.endswith("_EVENT_PCT")
                       or k in ("IV_RANK_HIGH", "IV_RANK_LOW", "OI_JUMP_MULT", "OI_JUMP_MIN", "NEAR_52W_HIGH_PCT")},
    }
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    path = os.path.join(config.OUTPUT_DIR, "nvda_analysis.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=1, default=str)
    print(f"[judge] {day} 이벤트 {len(events)}건 (본문 {len(body)} · 접힘 {len(overflow)}) · 다가오는 것 {len(analysis['upcoming'])}건 · "
          f"미수집 {missing or '없음'} → {path}")
    return analysis
