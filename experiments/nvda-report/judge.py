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
import normal_range_line
import trump_bridge

TECH_FIELDS = ["close", "ret_1d", "ret_vs_spy", "ret_vs_smh", "ret_vs_amd", "ret_vs_qqq", "ret_vs_avgo", "gap", "range_pct", "ret_sigma_20d",
               "volume", "vol_ratio_20d", "ma50", "ma200", "pct_from_52w_high", "rsi14", "ma_cross"]
KIND_PRIORITY = {"8k": 0, "10q": 0, "10k": 0, "form4": 1, "13dg": 1, "fedreg": 1, "court": 1, "trump": 1, "calendar": 2, "newsroom": 2,
                 "analyst": 3, "news": 3, "blog": 3, "regime": 2, "sector_flow": 2, "price": 4, "options": 5, "estimates": 6, "flows": 7, "news_volume": 8}


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


def _ev(area, kind, title, fact=None, url=None, direction="neutral", emphasis=False, source=None, published_at=None, speaker=None):
    return {"area": area, "kind": kind, "title": title, "fact": fact or title, "url": url, "direction": direction,
            "emphasis": emphasis, "source": source, "published_at": published_at,
            "speaker": speaker if speaker and speaker != "none" else None}   # 발언자 라벨 (2026-10-11)


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
        out.append(_ev("Flows", "options", f"변동성 순위 {rank:.0f}",
                       f"30일 내재변동성 {s['iv_atm_30d'] * 100:.1f}% — 최근 60일 중 순위 {rank:.0f} (임계 ≥{config.IV_RANK_HIGH} 또는 ≤{config.IV_RANK_LOW})",
                       source="yfinance options"))
    if p and p.get("pc_ratio_oi") and s.get("pc_ratio_oi"):
        chg = s["pc_ratio_oi"] / p["pc_ratio_oi"] - 1
        if abs(chg) >= config.PC_RATIO_CHG_EVENT:
            out.append(_ev("Flows", "options", f"풋/콜 비율(미결제약정) 전일 대비 {chg * 100:+.0f}%",
                           f"풋/콜 비율 {p['pc_ratio_oi']:.2f} → {s['pc_ratio_oi']:.2f} (임계 ±{config.PC_RATIO_CHG_EVENT * 100:.0f}%)",
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
            out.append(_ev("Flows", "options", f"{exp} ${k:,.0f} {lab} 미결제약정 {mult:.1f}배",
                           f"미결제약정 {before:,.0f} → {cur:,.0f} (임계 {config.OI_JUMP_MULT}배 · 미결제약정 ≥ {config.OI_JUMP_MIN:,})",
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
    for key, lab in (("eps_est_cq_7d_chg_pct", "주당순이익"), ("rev_est_cq_7d_chg_pct", "매출")):
        v = s.get(key)
        if v is not None and abs(v) >= config.EST_CHG_EVENT_PCT:
            out.append(_ev("Earnings", "estimates", f"이번 분기 {lab} 예상 7일 {v:+.1f}%",
                           f"{lab} 예상치(애널리스트 평균)가 7일 전 대비 {v:+.2f}% 이동 (임계 ±{config.EST_CHG_EVENT_PCT}%)",
                           direction="positive" if v > 0 else "negative", source="yfinance"))
    # 상향/하향 쏠림은 30일 누적 상태값 — 쏠림이 '생긴 날'만 이벤트, 이어지는 동안은 상태판에만
    skew = _revision_skew(s)
    p = _prev_state(conn, day)
    if skew and not (p and _revision_skew(p) == skew):
        up, down = s["revisions_up_30d"], s["revisions_down_30d"]
        if skew == "up":
            out.append(_ev("Earnings", "estimates", f"30일 주당순이익 예상 상향 {up} · 하향 {down}",
                           f"상향:하향 비 {up}:{down} (임계 {config.REVISION_RATIO_EVENT:.0f}:1)", direction="positive", source="yfinance"))
        else:
            out.append(_ev("Earnings", "estimates", f"30일 주당순이익 예상 상향 {up} · 하향 {down}",
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
    # FINRA 장외 공매도 비율 — 20일 평균에서 ±FINRA_SHORT_RATIO_DEV_PP 이상 벗어난 날 (2026-10-11)
    r, avg = s.get("finra_short_ratio"), s.get("finra_short_ratio_avg20")
    if r is not None and avg is not None and abs(r - avg) >= config.FINRA_SHORT_RATIO_DEV_PP:
        out.append(_ev("Flows", "flows", f"장외 공매도 비율 {r:.0f}% (20일 평균 {avg:.0f}%)",
                       f"FINRA 보고 장외 거래 중 공매도 {r:.1f}% — 20일 평균 {avg:.1f}% (임계 ±{config.FINRA_SHORT_RATIO_DEV_PP:.0f}%p)",
                       direction="negative" if r > avg else "positive", source="finra"))
    # 반도체 ETF 발행주식수 5거래일 변화 (2026-10-11 수집 시작)
    for key, name in (("smh_shares_out", "SMH"), ("soxx_shares_out", "SOXX")):
        cur = s.get(key)
        prior = conn.execute(f"SELECT {key} AS v FROM daily_state WHERE day < ? AND {key} IS NOT NULL ORDER BY day DESC LIMIT 5", (day,)).fetchall()
        if cur and len(prior) >= 5 and prior[-1]["v"]:
            chg = (cur / prior[-1]["v"] - 1) * 100
            if abs(chg) >= config.ETF_SHARES_5D_EVENT_PCT:
                out.append(_ev("Flows", "flows", f"{name} 발행주식수 5일 {chg:+.1f}%",
                               f"{prior[-1]['v'] / 1e6:,.2f}M → {cur / 1e6:,.2f}M주 (임계 ±{config.ETF_SHARES_5D_EVENT_PCT:.0f}%) — ETF 자금 {'유입' if chg > 0 else '유출'}",
                               direction="positive" if chg > 0 else "negative", source="yfinance"))
    return out


def finra_avg(conn, day):
    """기준일 직전 FINRA_AVG_DAYS 거래일의 장외 공매도 비율 평균 (기준일 제외). 20일이 안 쌓였으면 None."""
    rows = conn.execute("SELECT finra_short_ratio AS v FROM daily_state WHERE day < ? AND finra_short_ratio IS NOT NULL ORDER BY day DESC LIMIT ?",
                        (day, config.FINRA_AVG_DAYS)).fetchall()
    return (sum(r["v"] for r in rows) / len(rows)) if len(rows) >= config.FINRA_AVG_DAYS else None


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
        elif r["kind"] == "13dg":
            emphasis = "13D" in (r["title"] or "")   # 경영 관여 목적 신고만 강조
        elif r["kind"] in config.CLASSIFY_KINDS:
            emphasis = (r["ai_relevance"] or 0) >= 3 or (r["ai_area"] in config.PRIORITY_AREAS)
        events.append(_ev(r["ai_area"] or "Corporate", r["kind"], r["title"], r["ai_fact"] or r["summary"], r["url"],
                          r["ai_direction"] or "neutral", emphasis, r["source"], r["published_at"],
                          speaker=(r["ai_speaker"] if "ai_speaker" in r.keys() else None)))
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

    # ④ (2026-10-10): SEC 원문에서 추출(extract_quarterly). capex 가이던스·TSMC 월매출은 뺐다
    later = [("revenue", "분기 매출"), ("dc_revenue", "데이터센터 매출"), ("dc_revenue_yoy", "데이터센터 매출 (전년 동기 대비)"), ("dc_revenue_qoq", "데이터센터 매출 (직전 분기 대비)"),
             ("gross_margin_nongaap", "총이익률 (조정 기준 non-GAAP)"), ("guidance_revenue_next", "다음 분기 매출 (회사 전망)"), ("guidance_beat_pct", "회사 전망 대비 실제 매출"),
             ("china_revenue_pct", "중국(홍콩 포함) 매출 비중"), ("top_customer_pct", "10% 이상 고객 비중 합"), ("buyback_amount", "분기 자사주 매입")]
    for m, lab in later:
        q = conn.execute("SELECT * FROM quarterly WHERE metric = ? ORDER BY fiscal_quarter DESC LIMIT 2", (m,)).fetchall()
        if q:
            cur = dict(q[0])
            arrow = None
            if len(q) > 1 and q[1]["value"] is not None and cur["value"] is not None:
                arrow = "↑" if cur["value"] > q[1]["value"] else ("↓" if cur["value"] < q[1]["value"] else "→")
            detail = cur["source"]
            if m == "guidance_revenue_next" and cur.get("value_json"):
                vj = db.loads(cur["value_json"], {}) or {}
                detail = f"{cur['source']} · ±{vj.get('pm_pct')}%" if vj.get("pm_pct") else cur["source"]
            add(m, lab, cur["value"], cur["unit"], cur["fiscal_quarter"], cur["source"], arrow=arrow, detail=detail)
        else:
            add(m, lab, note="미수집")
    ins = collect_edgar.insider_net_sold(conn, day)
    add("insider_net_sold_90d", "90일 임원·내부자 순매도", ins["net_sold_usd"], "USD", day, "SEC 임원 거래 공시 (Form 4)",
        detail=f"매도 ${ins['sold_usd'] / 1e6:,.1f}M · 매수 ${ins['bought_usd'] / 1e6:,.1f}M · 공시 {ins['filings']}건 (사전 매도 계획 {ins['plan_filings']}건)")
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
    add("forward_pe", "선행 주가수익비율 (주가 ÷ 12개월 예상 주당순이익)", s.get("forward_pe"), "배", day, "yfinance",
        note=None if s.get("forward_pe") else "미수집")
    n_pe = conn.execute("SELECT COUNT(*) FROM daily_state WHERE forward_pe IS NOT NULL").fetchone()[0]
    add("forward_pe_1y_pct", "선행 주가수익비율 1년 분위 (최근 1년 중 위치, 0~100)", note=f"집계 중 ({n_pe}/252일)" if n_pe < 252 else None,
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
            cell("ret_vs_avgo", s.get("ret_vs_avgo"), fmt="pp_signed"),
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
            cell("finra_short_ratio", s.get("finra_short_ratio"),
                 s.get("finra_short_ratio") is not None and s.get("finra_short_ratio_avg20") is not None
                 and abs(s["finra_short_ratio"] - s["finra_short_ratio_avg20"]) >= config.FINRA_SHORT_RATIO_DEV_PP, "pct"),
            cell("finra_short_ratio_avg20", s.get("finra_short_ratio_avg20"), fmt="pct"),
        ],
        "valuation": [cell("forward_pe", s.get("forward_pe"), fmt="num1")],
        "iv_rank_n": rank_n,
    }


def market_regime(conn, day):
    """시장 국면 — S&P 500(SPY) 종가 기준 규칙 네 구간 (config.REGIME_*, 기획서 7절). 상태만 적는다 — 매수·매도·비중·관망 어휘 없음 (2026-10-11 사용자).
    전환 판정은 meta `market_regime`에 둔 전 거래일 국면과 비교한다. 같은 날 재실행은 멱등(prev_regime 유지)."""
    bars = [b for b in collect_market.bars(conn, config.REGIME_BENCHMARK) if b["day"] <= day]
    if len(bars) < config.REGIME_MA_DAYS:
        return None
    closes = [b["close"] for b in bars]
    close = closes[-1]
    pct_from_high = (close / max(closes[-config.REGIME_HIGH_DAYS:]) - 1) * 100
    ma = sum(closes[-config.REGIME_MA_DAYS:]) / config.REGIME_MA_DAYS
    above_ma = close >= ma
    vrow = conn.execute("SELECT close FROM daily_bars WHERE symbol = '^VIX' AND day <= ? AND close IS NOT NULL ORDER BY day DESC LIMIT 1", (day,)).fetchone()
    vix = vrow["close"] if vrow else None
    streak = 0   # 연속 등락일 (종가): +n 상승 · −n 하락 · 0 보합
    for i in range(len(closes) - 1, 0, -1):
        d = closes[i] - closes[i - 1]
        if d == 0 or (streak and (d > 0) != (streak > 0)):
            break
        streak += 1 if d > 0 else -1
    if vix is not None and vix >= config.REGIME_VIX_HIGH:
        regime = "불안 국면"
    elif pct_from_high <= config.REGIME_CORRECTION_PCT or not above_ma:
        regime = "조정장"
    elif pct_from_high <= config.REGIME_PULLBACK_PCT:
        regime = "단기 조정"
    else:
        regime = "상승 추세"
    raw = db.get_meta(conn, "market_regime")
    last = json.loads(raw) if raw else {}
    if last.get("day") == day:
        prev = last.get("prev_regime")
    elif last.get("day") and last["day"] > day:
        prev = None   # 과거 날짜 재판정 — 전환 판단도 meta 갱신도 하지 않는다
    else:
        prev = last.get("regime")
    if not (last.get("day") and last["day"] > day):
        db.set_meta(conn, "market_regime", json.dumps({"day": day, "regime": regime, "prev_regime": prev}, ensure_ascii=False))
        conn.commit()
    return {"regime": regime, "prev_regime": prev, "changed": bool(prev and prev != regime), "pct_from_high": pct_from_high,
            "above_ma200": above_ma, "ma200": ma, "pct_vs_ma200": (close / ma - 1) * 100, "vix": vix, "streak": streak, "benchmark": config.REGIME_BENCHMARK, "bar_day": bars[-1]["day"]}


def _rel_return(conn, symbol, day, n, spy_closes=None):
    """symbol의 최근 n거래일 수익률 − SPY 같은 기간 수익률 (%p). 일봉이 모자라면 None."""
    c = [b["close"] for b in collect_market.bars(conn, symbol) if b["day"] <= day]
    if len(c) < n + 1:
        return None
    r = (c[-1] / c[-n - 1] - 1) * 100
    if spy_closes is None:
        spy_closes = [b["close"] for b in collect_market.bars(conn, config.BENCHMARK) if b["day"] <= day]
    if len(spy_closes) < n + 1:
        return None
    return r - (spy_closes[-1] / spy_closes[-n - 1] - 1) * 100


def _prev_from_meta(conn, key, day, cur):
    """전 거래일 상태를 meta에서 읽고 오늘 상태를 적는다 (시장 국면과 같은 규칙: 같은 날 재실행 멱등, 과거 날짜 재판정은 건드리지 않음)."""
    raw = db.get_meta(conn, key)
    last = json.loads(raw) if raw else {}
    if last.get("day") == day:
        prev = last.get("prev")
    elif last.get("day") and last["day"] > day:
        return None
    else:
        prev = last.get("cur")
    db.set_meta(conn, key, json.dumps({"day": day, "cur": cur, "prev": prev}, ensure_ascii=False))
    conn.commit()
    return prev


def sector_flow(conn, day, s):
    """반도체 자금 방향 — SMH가 20거래일 동안 S&P 500보다 ±SECTOR_FLOW_PP 이상 앞서면 '모이는 중', 뒤지면 '빠져나가는 중' (2026-10-11 사용자 승인).
    SMH 발행주식수 5일 변화가 있고 방향이 반대면 '뚜렷하지 않음'으로 내린다. 같은 창에서 앞선 섹터·뒤처진 섹터 둘씩을 이름으로 돌려준다."""
    n = config.SECTOR_FLOW_DAYS
    spy = [b["close"] for b in collect_market.bars(conn, config.BENCHMARK) if b["day"] <= day]
    rel = _rel_return(conn, config.SECTOR_FLOW_ETF, day, n, spy)
    if rel is None:
        return None
    state = "모이는 중" if rel >= config.SECTOR_FLOW_PP else "빠져나가는 중" if rel <= -config.SECTOR_FLOW_PP else "뚜렷하지 않음"
    shares_5d = None   # 확인용: SMH 발행주식수 5거래일 변화 (쌓인 뒤)
    cur = s.get("smh_shares_out")
    prior = conn.execute("SELECT smh_shares_out AS v FROM daily_state WHERE day < ? AND smh_shares_out IS NOT NULL ORDER BY day DESC LIMIT 5", (day,)).fetchall()
    if cur and len(prior) >= 5 and prior[-1]["v"]:
        shares_5d = (cur / prior[-1]["v"] - 1) * 100
        if state != "뚜렷하지 않음" and abs(shares_5d) >= config.ETF_SHARES_5D_EVENT_PCT and ((shares_5d > 0) != (state == "모이는 중")):
            state = "뚜렷하지 않음"   # 가격 방향과 실제 자금이 엇갈림
    sectors = []
    for etf, name in config.SECTOR_ETFS.items():
        r = _rel_return(conn, etf, day, n, spy)
        if r is not None:
            sectors.append({"etf": etf, "name": name, "rel": r})
    sectors.sort(key=lambda x: x["rel"], reverse=True)
    for i, x in enumerate(sectors, 1):
        x["rank"] = i
    smh_rank = 1 + sum(1 for x in sectors if x["rel"] > rel)   # 반도체를 11개 섹터와 같이 세웠을 때 순위 (2026-10-11 사용자: 순위를 알려주기)
    prev = _prev_from_meta(conn, "sector_flow", day, state)
    return {"state": state, "prev": prev, "changed": bool(prev and prev != state), "rel_pp": rel, "days": n,
            "shares_5d": shares_5d, "sectors": sectors, "smh_rank": smh_rank, "n_sectors": len(sectors),
            "leaders": sectors[:2], "laggards": sectors[-2:][::-1] if len(sectors) >= 2 else []}


def sector_flow_events(sf):
    if not sf or not sf.get("changed"):
        return []
    lead = " · ".join(f"{x['name']} {x['rel']:+.1f}%p" for x in sf["leaders"])
    return [_ev("Flows", "sector_flow", f"반도체 자금 — {sf['prev']} → {sf['state']}",
                f"반도체 ETF(SMH) {sf['days']}일 S&P 500 대비 {sf['rel_pp']:+.1f}%p · 같은 기간 앞선 섹터 {lead}",
                direction=config.SECTOR_FLOW_DIRECTION.get(sf["state"], "neutral"), source="yfinance")]


def bollinger(conn, day, stats_path=None):
    """볼린저 밴드(20, 2σ) 위치 — %B, 하단·상단 도달, 연속 일수, 진입일 여부, 상장 이후 통계 (2026-10-11 사용자: 하단 도달 카드)."""
    closes = [b["close"] for b in collect_market.bars(conn, config.SYMBOL) if b["day"] <= day]
    w = config.BOLL_WINDOW
    if len(closes) < w + 1:
        return None

    def pctb_at(i):
        win = closes[i - w + 1:i + 1]
        ma = sum(win) / w
        sd = (sum((x - ma) ** 2 for x in win) / (w - 1)) ** 0.5
        lo, hi = ma - config.BOLL_SIGMA * sd, ma + config.BOLL_SIGMA * sd
        return (closes[i] - lo) / (hi - lo) if hi > lo else 0.5, lo, hi, ma

    pb, lo, hi, ma = pctb_at(len(closes) - 1)
    state = "하단 도달" if pb <= 0 else "상단 도달" if pb >= 1 else "밴드 안"
    days = 0   # 연속 일수 (하단 이하 또는 상단 이상)
    if state != "밴드 안":
        for i in range(len(closes) - 1, w - 1, -1):
            p = pctb_at(i)[0]
            if (p <= 0) if state == "하단 도달" else (p >= 1):
                days += 1
            else:
                break
    stats = None
    try:
        with open(stats_path or config.HISTORY_STATS_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)
    except (OSError, ValueError):
        pass
    return {"pctb": pb, "lower": lo, "upper": hi, "ma20": ma, "close": closes[-1], "state": state, "days": days,
            "entered": state != "밴드 안" and days == 1, "stats": stats}


def bollinger_events(bb):
    """하단·상단 진입일만 이벤트 (연속 구간 첫날). 사실만 — 지시어 없음."""
    if not bb or not bb.get("entered"):
        return []
    low = bb["state"] == "하단 도달"
    return [_ev("Flows", "price", f"볼린저 밴드 {bb['state']}",
                f"종가 ${bb['close']:,.2f} · {'하단' if low else '상단'} ${(bb['lower'] if low else bb['upper']):,.2f} (20일 평균 ${bb['ma20']:,.2f} {'−' if low else '+'} 2σ) · %B {bb['pctb']:.2f}",
                direction="negative" if low else "positive", source="yfinance")]


def overheat(conn, day, s, stats=None):
    """과열 지표 — RSI14 ≥ 80 · 200일 평균 대비 +40% · 20일 +25% 중 해당하는 조건과 상장 이후 진입일 통계 (2026-10-11 사용자: "이익 실현 구간").
    구간을 지시하지 않는다 — 조건에 닿은 날 과거 빈도만. 새로 들어간 조건은 meta `overheat`(전 거래일 집합)과 비교해 이벤트."""
    closes = [b["close"] for b in collect_market.bars(conn, config.SYMBOL) if b["day"] <= day]
    if len(closes) < 21:
        return None
    ret20 = (closes[-1] / closes[-21] - 1) * 100
    dist200 = ((closes[-1] / s["ma200"]) - 1) * 100 if s.get("ma200") else None
    rsi = s.get("rsi14")
    values = {"rsi80": rsi, "ma200_40": dist200, "ret20_25": ret20}
    active = [k for k, ok in (("rsi80", rsi is not None and rsi >= config.OVERHEAT_RSI),
                              ("ma200_40", dist200 is not None and dist200 >= config.OVERHEAT_MA200_PCT),
                              ("ret20_25", ret20 >= config.OVERHEAT_RET20_PCT)) if ok]
    prev = _prev_from_meta(conn, "overheat", day, active)
    entered = [k for k in active if not prev or k not in prev]
    if stats is None:
        try:
            with open(config.HISTORY_STATS_PATH, "r", encoding="utf-8") as f:
                stats = json.load(f)
        except (OSError, ValueError):
            stats = None
    return {"active": active, "entered": entered, "values": values, "stats": stats}


def overheat_events(oh):
    if not oh or not oh.get("entered"):
        return []
    out = []
    for k in oh["entered"]:
        v = oh["values"].get(k)
        st = ((oh.get("stats") or {}).get(k)) or {}
        base = ((oh.get("stats") or {}).get("base")) or {}
        since = str((oh.get("stats") or {}).get("from") or "")[:4]
        tail = f" · {since + '년 이후' if since.isdigit() else '과거'} 진입 {st['n']}회, 20일 뒤 상승 {st['up20']}% (아무 날 {base.get('up20')}%)" if st and base else ""
        out.append(_ev("Flows", "price", f"과열 지표 진입 — {config.OVERHEAT_KEYS[k]}",
                       f"{config.OVERHEAT_KEYS[k]} (현재 {v:.1f}{'%' if k != 'rsi80' else ''}){tail}", direction="uncertain", source="yfinance"))
    return out


def regime_events(mr):
    """국면이 전 거래일과 달라진 날만 이벤트 (기획서 6절). 사실만 — 지시어 없음."""
    if not mr or not mr.get("changed"):
        return []
    fact = f"S&P 500 고점 대비 {mr['pct_from_high']:+.1f}% · 200일 평균 {'위' if mr['above_ma200'] else '아래'}" + (f" · VIX {mr['vix']:.1f}" if mr.get("vix") is not None else "")
    return [_ev("Macro", "regime", f"시장 국면 전환 — {mr['prev_regime']} → {mr['regime']}", fact,
                direction=config.REGIME_DIRECTION.get(mr["regime"], "neutral"), source="calendar")]


# "N" 라벨 (2026-10-11 사용자: 새로운 데이터에 N) — 가끔 바뀌는 칸만, 전 리포트와 값이 다른 그날만. 매일 바뀌는 칸(가격·옵션·비율)은 대상이 아니다
OCCASIONAL_STATUS_KEYS = ("ma_cross", "revisions_up_30d", "revisions_down_30d", "shares_short", "short_asof", "short_pct_float",
                          "smh_shares_out", "soxx_shares_out", "pt_mean", "pt_median", "pt_high", "pt_low", "rating_counts")


def occasional_values(analysis):
    """가끔 바뀌는 칸의 현재 값 묶음 — 키는 렌더가 N을 붙일 자리와 같다."""
    v = {}
    for group in ("technical", "estimates", "analysts", "flows"):
        for c in analysis["status"].get(group) or []:
            if c["key"] in OCCASIONAL_STATUS_KEYS:
                v["status:" + c["key"]] = c["value"]
    for r in analysis["checklist"]:
        v["checklist:" + r["metric"]] = [r.get("value"), r.get("asof")]
    for c in analysis["upcoming"]:
        v[f"calendar:{c['kind']}:{c['day']}:{c['label']}"] = bool(c.get("confirmed", 1))
    for c in analysis["cases"]:
        v["case:" + c["case_id"]] = [c.get("status"), c.get("next_day"), c.get("last_activity_at")]
    if analysis.get("market_regime"):
        v["regime"] = analysis["market_regime"]["regime"]
    if analysis.get("sector_flow"):
        v["sector_flow"] = analysis["sector_flow"]["state"]
    return v


def new_flags(conn, day, cur):
    """전 리포트 값 묶음(meta new_values)과 비교해 달라진 키 목록. 첫 실행(이전 묶음 없음)은 빈 목록. 같은 날 재실행 멱등, 과거 날짜 재판정은 건드리지 않는다."""
    raw = db.get_meta(conn, "new_values")
    last = json.loads(raw) if raw else {}
    cur = json.loads(json.dumps(cur))   # 저장 형식(JSON)으로 맞춰 비교
    if last.get("day") == day:
        prev = last.get("prev")
    elif last.get("day") and last["day"] > day:
        return []
    else:
        prev = last.get("cur")
    db.set_meta(conn, "new_values", json.dumps({"day": day, "cur": cur, "prev": prev}, ensure_ascii=False))
    conn.commit()
    if not prev:
        return []
    return sorted(k for k, val in cur.items() if k not in prev or prev[k] != val)


def _direction_counts(evs):
    out = {"positive": 0, "negative": 0, "uncertain": 0, "neutral": 0}
    for e in evs:
        d = e.get("direction") or "neutral"
        out[d if d in out else "neutral"] += 1
    return out


def build(conn, day, run_date):
    update_technicals(conn)
    s = _state(conn, day)
    if not s:
        raise RuntimeError(f"daily_state에 {day} 행이 없다 — 일봉부터 확인")
    s["finra_short_ratio_avg20"] = finra_avg(conn, day)   # 상태판·이벤트가 같이 쓴다 (2026-10-11)
    rank, rank_n = iv_rank(conn, day)
    if rank is not None:
        conn.execute("UPDATE daily_state SET iv_rank_60d = ? WHERE day = ?", (rank, day))
        conn.commit()
    item_evs, target_only = item_events(conn, day)
    n_news, news_avg = news_count(conn, day)
    mr = market_regime(conn, day)
    if mr and s.get("fng_score") is not None:   # 공포·탐욕 지수 (collect_fng) — 시장 국면 글머리표에
        import collect_fng
        mr["fng"] = {"score": s["fng_score"], "rating": s.get("fng_rating"), "rating_ko": collect_fng.RATING_KO.get(s.get("fng_rating") or "", s.get("fng_rating") or "")}
    sf = sector_flow(conn, day, s)
    bb = bollinger(conn, day)
    oh = overheat(conn, day, s, (bb or {}).get("stats"))
    events = (item_evs + calendar_events(conn, day) + regime_events(mr) + sector_flow_events(sf) + bollinger_events(bb) + overheat_events(oh) + trump_bridge.events(day) + price_events(s) + near_high_event(conn, day, s)
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
        "headline": {k: s.get(k) for k in ("close", "ret_1d", "ret_vs_spy", "ret_vs_smh", "ret_vs_amd", "ret_vs_avgo", "vol_ratio_20d", "gap", "range_pct", "ret_sigma_20d")},
        "macro_today": [c["label"] for c in macro_today],
        "normal_range": normal_range_line.compute(conn, day),   # 평소 범위 (EWMA 자) · 시장 충격 (2026-10-17, 4단계 W1 · W2)
        "market_regime": mr,   # 시장 국면 (2026-10-11): 글 머리 한 줄 + ⓘ 규칙
        "sector_flow": sf,     # 반도체 자금 방향 (2026-10-11): 글 머리 한 줄 + ⓘ 쉬운 설명
        "bollinger": bb,       # 볼린저 밴드 (2026-10-11): 하단·상단 도달 때만 카드
        "overheat": oh,        # 과열 지표 (2026-10-11): 조건 하나라도 해당하면 카드
        "events": body, "events_overflow": overflow, "events_total": len(events),
        # 뉴스 구획 막대 (2026-10-11 사용자): 오늘 = 이 리포트의 이벤트 전체, 7일 = 문서 이벤트(items.is_event) 최근 7일
        "direction_counts": {
            "today": _direction_counts(events),
            "week": _direction_counts([dict(r) for r in conn.execute(
                "SELECT ai_direction AS direction FROM items WHERE is_event = 1 AND published_at >= date(?, '-6 days')", (day,))]),
        },
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
                        "option_expiries": db.loads(s.get("option_expiries")),
                        "items_pending": conn.execute(
                            f"""SELECT COUNT(*) FROM items WHERE kind IN ({','.join("'" + k + "'" for k in config.CLASSIFY_KINDS)})
                                AND prefilter_reason IS NULL AND analyzed_at IS NULL AND published_at >= ?""",
                            ((datetime.date.fromisoformat(day) - datetime.timedelta(days=config.CLASSIFY_SINCE_DAYS)).isoformat(),)).fetchone()[0],
                        "test_mode": config.TEST_MODE},
        "thresholds": {k: getattr(config, k) for k in dir(config) if k.endswith("_EVENT") or k.endswith("_EVENT_PCT")
                       or k in ("IV_RANK_HIGH", "IV_RANK_LOW", "OI_JUMP_MULT", "OI_JUMP_MIN", "NEAR_52W_HIGH_PCT")},
    }
    analysis["new_flags"] = new_flags(conn, day, occasional_values(analysis))   # "N" 라벨 (2026-10-11)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    path = os.path.join(config.OUTPUT_DIR, "nvda_analysis.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=1, default=str)
    print(f"[judge] {day} 이벤트 {len(events)}건 (본문 {len(body)} · 접힘 {len(overflow)}) · 다가오는 것 {len(analysis['upcoming'])}건 · "
          f"미수집 {missing or '없음'} → {path}")
    return analysis
