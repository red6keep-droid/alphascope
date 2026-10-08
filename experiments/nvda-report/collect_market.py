"""시세·옵션·추정치·애널리스트·보유/공매도 → daily_bars · option_snapshots · daily_state · items(analyst) (기획서 2절).

전부 yfinance, 키 없음. 옵션 체인은 장 마감 후 1회 스냅샷이라 장중 흐름은 없다.
어느 수집기가 실패해도 다음으로 넘어가고, 그 칸은 missing_fields_json에 적어 리포트에 "—"로 나간다.
"""

import datetime
import sys
import time

import pandas as pd
import yfinance as yf

import config
import db
import indicators


# ── 일봉 (trump-trend collect_prices와 같은 방식) ──────────────────────────

def _has_history(conn, symbol):
    row = conn.execute("SELECT COUNT(*) FROM daily_bars WHERE symbol = ?", (symbol,)).fetchone()
    return row[0] > 200


def fetch_daily(symbols, period):
    df = yf.download(symbols, period=period, interval="1d", auto_adjust=False,
                     group_by="ticker", progress=False, threads=True)
    rows = []
    for sym in symbols:
        try:
            sub = df[sym] if isinstance(df.columns, pd.MultiIndex) else df
        except KeyError:
            print(f"[prices] {sym}: 데이터 없음")
            continue
        sub = sub.dropna(subset=["Close"])
        for idx, r in sub.iterrows():
            rows.append((
                sym, idx.strftime("%Y-%m-%d"),
                float(r["Open"]), float(r["High"]), float(r["Low"]), float(r["Close"]),
                float(r["Volume"]) if pd.notna(r["Volume"]) else None,
            ))
    return rows


def collect_bars(conn, force_backfill=False):
    symbols = config.SYMBOLS
    backfill = [s for s in symbols if force_backfill or not _has_history(conn, s)]
    update = [s for s in symbols if s not in backfill]
    total = 0
    for group, period in ((backfill, config.PRICE_BACKFILL_PERIOD), (update, config.PRICE_UPDATE_PERIOD)):
        if not group:
            continue
        print(f"[prices] {len(group)}개 심볼 · period={period}: {', '.join(group)}")
        rows = fetch_daily(group, period)
        conn.executemany(
            """INSERT INTO daily_bars(symbol, day, open, high, low, close, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(symbol, day) DO UPDATE SET
                 open=excluded.open, high=excluded.high, low=excluded.low,
                 close=excluded.close, volume=excluded.volume""",
            rows,
        )
        total += len(rows)
    conn.commit()
    last = last_bar_day(conn)
    print(f"[prices] {total:,}행 갱신 · {config.SYMBOL} 마지막 거래일 {last}")
    return total


def bars(conn, symbol):
    return [dict(r) for r in conn.execute(
        "SELECT day, open, high, low, close, volume FROM daily_bars WHERE symbol = ? AND close IS NOT NULL ORDER BY day",
        (symbol,))]


def last_bar_day(conn):
    return conn.execute("SELECT MAX(day) FROM daily_bars WHERE symbol = ?", (config.SYMBOL,)).fetchone()[0]


def close_on(conn, symbol, day):
    row = conn.execute("SELECT close FROM daily_bars WHERE symbol = ? AND day = ?", (symbol, day)).fetchone()
    return row["close"] if row else None


# ── 옵션 ───────────────────────────────────────────────────────────────────

def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(v) else v


def _mid(row):
    bid, ask, last = _num(row.get("bid")), _num(row.get("ask")), _num(row.get("lastPrice"))
    if bid and ask and ask > 0:
        return (bid + ask) / 2
    return last if last and last > 0 else None


def _clean_iv(v):
    v = _num(v)
    return v if v is not None and 0 < v < 3 else None


def _chain(t, expiry, attempts=3):
    for i in range(attempts):
        try:
            c = t.option_chain(expiry)
            if c.calls is not None and not c.calls.empty:
                return c
        except Exception as e:  # noqa: BLE001
            print(f"[options] {expiry} 실패 ({i + 1}/{attempts}): {e}")
        time.sleep(2)
    return None


def pick_expiries(expiries, day, next_earnings_day):
    """가까운 만기 4개 + 30일을 감싸는 만기 둘 + (실적이 45일 안이면) 실적 직후 만기."""
    d0 = datetime.date.fromisoformat(day)
    future = [e for e in expiries if (datetime.date.fromisoformat(e) - d0).days >= 1]
    chosen = list(future[:config.OPTION_NEAR_EXPIRIES])
    dtes = [(e, (datetime.date.fromisoformat(e) - d0).days) for e in future]
    below = [e for e, d in dtes if d <= config.OPTION_IV_TARGET_DAYS]
    above = [e for e, d in dtes if d >= config.OPTION_IV_TARGET_DAYS]
    for e in ([below[-1]] if below else []) + ([above[0]] if above else []):
        if e not in chosen:
            chosen.append(e)
    earnings_expiry = None
    if next_earnings_day:
        ed = datetime.date.fromisoformat(next_earnings_day)
        if 0 <= (ed - d0).days <= config.OPTION_EARNINGS_LOOKAHEAD_DAYS:
            after = [e for e in future if datetime.date.fromisoformat(e) > ed]
            if after:
                earnings_expiry = after[0]
                if earnings_expiry not in chosen:
                    chosen.append(earnings_expiry)
    return chosen, earnings_expiry


def collect_options(conn, t, day, spot, next_earnings_day):
    """옵션 체인 스냅샷 → option_snapshots, 지표 dict 반환. 실패하면 빈 dict."""
    try:
        expiries = list(t.options)
    except Exception as e:  # noqa: BLE001
        print(f"[options] 만기 목록 실패: {e}")
        return {}, []
    chosen, earnings_expiry = pick_expiries(expiries, day, next_earnings_day)
    if not chosen:
        return {}, []
    snap_rows, expiry_iv = [], {}
    tot_call_oi = tot_put_oi = tot_call_vol = tot_put_vol = 0.0
    implied_move = None
    lo, hi = spot * (1 - config.OPTION_STRIKE_BAND), spot * (1 + config.OPTION_STRIKE_BAND)
    for e in chosen:
        c = _chain(t, e)
        if c is None:
            print(f"[options] {e}: 체인 없음")
            continue
        calls = c.calls.drop_duplicates("strike").set_index("strike")
        puts = c.puts.drop_duplicates("strike").set_index("strike")
        tot_call_oi += float(calls["openInterest"].fillna(0).sum())
        tot_put_oi += float(puts["openInterest"].fillna(0).sum())
        tot_call_vol += float(calls["volume"].fillna(0).sum())
        tot_put_vol += float(puts["volume"].fillna(0).sum())
        strikes = sorted(set(calls.index) | set(puts.index))
        atm = min(strikes, key=lambda k: abs(k - spot)) if strikes else None
        ivs = []
        for df in (calls, puts):
            if atm in df.index:
                iv = _clean_iv(df.loc[atm, "impliedVolatility"])
                if iv:
                    ivs.append(iv)
        if ivs:
            expiry_iv[e] = sum(ivs) / len(ivs)
        if e == earnings_expiry and atm is not None:
            cm = _mid(calls.loc[atm].to_dict()) if atm in calls.index else None
            pm = _mid(puts.loc[atm].to_dict()) if atm in puts.index else None
            if cm and pm:
                implied_move = (cm + pm) / spot * 100
        for k in strikes:
            if k < lo or k > hi:
                continue
            cr = calls.loc[k].to_dict() if k in calls.index else {}
            pr = puts.loc[k].to_dict() if k in puts.index else {}
            snap_rows.append({
                "day": day, "expiry": e, "strike": float(k),
                "call_oi": _num(cr.get("openInterest")) or 0.0, "put_oi": _num(pr.get("openInterest")) or 0.0,
                "call_iv": _clean_iv(cr.get("impliedVolatility")), "put_iv": _clean_iv(pr.get("impliedVolatility")),
                "call_vol": _num(cr.get("volume")) or 0.0, "put_vol": _num(pr.get("volume")) or 0.0,
                "call_mid": _mid(cr) if cr else None, "put_mid": _mid(pr) if pr else None,
            })
        time.sleep(0.5)
    if not snap_rows:
        return {}, chosen
    # 품질 게이트 — Yahoo는 미국 자정(≈04:00 UTC) 뒤 다음 장 전까지 호가·OI·IV를 0으로 리셋한 체인을 준다 (2026-10-08 04:34 UTC 확인).
    # 그 상태를 저장하면 정상 스냅샷을 덮어쓰므로, 불량이면 저장하지 않고 미수집으로 둔다.
    quoted = sum(1 for r in snap_rows if (r["call_mid"] or r["put_mid"]))
    iv30_probe = indicators.atm_iv_interpolated(expiry_iv, day)
    bad = []
    if tot_call_oi + tot_put_oi <= 0:
        bad.append("OI 합 0")
    if quoted < len(snap_rows) * config.OPTION_MIN_QUOTED_FRACTION:
        bad.append(f"호가 있는 행 {quoted}/{len(snap_rows)}")
    if not iv30_probe or not (config.OPTION_IV_SANE[0] <= iv30_probe <= config.OPTION_IV_SANE[1]):
        bad.append(f"ATM IV30 {iv30_probe and round(iv30_probe * 100, 2)}%")
    if bad:
        print(f"[options] 체인 불량 — 저장 안 함 ({' · '.join(bad)}). 장 마감 후~미국 자정 사이에 다시 받는다")
        return {}, chosen
    conn.execute("DELETE FROM option_snapshots WHERE day = ?", (day,))
    conn.executemany(
        """INSERT INTO option_snapshots(day, expiry, strike, call_oi, put_oi, call_iv, put_iv, call_vol, put_vol, call_mid, put_mid)
           VALUES (:day, :expiry, :strike, :call_oi, :put_oi, :call_iv, :put_iv, :call_vol, :put_vol, :call_mid, :put_mid)""",
        snap_rows)
    cutoff = (datetime.date.fromisoformat(day) - datetime.timedelta(days=config.OPTION_SNAPSHOT_KEEP_DAYS)).isoformat()
    conn.execute("DELETE FROM option_snapshots WHERE day < ?", (cutoff,))
    conn.commit()

    gex, flip = indicators.gex_approx(snap_rows, spot, day)
    by_call = max(snap_rows, key=lambda r: r["call_oi"])
    by_put = max(snap_rows, key=lambda r: r["put_oi"])
    iv30 = indicators.atm_iv_interpolated(expiry_iv, day)
    metrics = {
        "iv_atm_30d": iv30,
        "implied_move_next_earnings": implied_move,
        "pc_ratio_oi": (tot_put_oi / tot_call_oi) if tot_call_oi else None,
        "pc_ratio_vol": (tot_put_vol / tot_call_vol) if tot_call_vol else None,
        "gex_approx": gex, "gex_flip_strike": flip,
        "max_oi_strike_call": by_call["strike"], "max_oi_strike_put": by_put["strike"],
        "option_expiries": db.dumps(chosen),
    }
    msg = f"[options] 만기 {len(chosen)}개 · 스냅샷 {len(snap_rows)}행"
    if iv30:
        msg += f" · ATM IV30 {iv30 * 100:.1f}%"
    if metrics["pc_ratio_oi"]:
        msg += f" · P/C(OI) {metrics['pc_ratio_oi']:.2f}"
    if implied_move:
        msg += f" · implied move {implied_move:.1f}% ({earnings_expiry})"
    print(msg)
    return metrics, chosen


# ── 추정치 · 애널리스트 · 보유/공매도 ────────────────────────────────────────

def _loc(df, idx, col):
    try:
        v = df.loc[idx, col]
        return None if pd.isna(v) else float(v)
    except Exception:  # noqa: BLE001
        return None


def collect_estimates(t):
    out = {}
    try:
        ee = t.earnings_estimate
        out["eps_est_cq"] = _loc(ee, "0q", "avg")
        out["eps_est_ny"] = _loc(ee, "+1y", "avg")
    except Exception as e:  # noqa: BLE001
        print(f"[estimates] earnings_estimate 실패: {e}")
    try:
        tr = t.eps_trend
        cur, ago = _loc(tr, "0q", "current"), _loc(tr, "0q", "7daysAgo")
        out["eps_est_cq_7d_chg_pct"] = (cur / ago - 1) * 100 if cur and ago else None
    except Exception as e:  # noqa: BLE001
        print(f"[estimates] eps_trend 실패: {e}")
    try:
        re_ = t.revenue_estimate
        out["rev_est_cq"] = _loc(re_, "0q", "avg")
    except Exception as e:  # noqa: BLE001
        print(f"[estimates] revenue_estimate 실패: {e}")
    try:
        rv = t.eps_revisions
        up, down = _loc(rv, "0q", "upLast30days"), _loc(rv, "0q", "downLast30days")
        out["revisions_up_30d"] = int(up) if up is not None else None
        out["revisions_down_30d"] = int(down) if down is not None else None
    except Exception as e:  # noqa: BLE001
        print(f"[estimates] eps_revisions 실패: {e}")
    return out


ACTION_KO = {"up": " (상향)", "down": " (하향)", "init": " (신규 커버)"}
PT_ACTION_KO = {"Raises": "상향", "Lowers": "하향", "Maintains": "유지", "Initiates": "신규"}


def collect_analysts(conn, t, day):
    out = {}
    try:
        rec = t.recommendations
        if rec is not None and not rec.empty:
            r0 = rec.iloc[0]
            out["rating_counts_json"] = db.dumps({k: int(r0[k]) for k in ("strongBuy", "buy", "hold", "sell", "strongSell")})
    except Exception as e:  # noqa: BLE001
        print(f"[analysts] recommendations 실패: {e}")
    try:
        pt = t.analyst_price_targets or {}
        out["pt_mean"], out["pt_high"], out["pt_low"], out["pt_median"] = (
            pt.get("mean"), pt.get("high"), pt.get("low"), pt.get("median"))
    except Exception as e:  # noqa: BLE001
        print(f"[analysts] price_targets 실패: {e}")
    # 등급·목표가 변경 → items(kind=analyst). 지난번 본 시각 이후만 새로 넣는다 (첫 실행은 14일).
    try:
        ud = t.upgrades_downgrades
        if ud is not None and not ud.empty:
            ud = ud.sort_index(ascending=False)
            last_seen = db.get_meta(conn, "analyst_last_seen")
            since = last_seen or (datetime.date.fromisoformat(day) - datetime.timedelta(days=14)).isoformat()
            new, newest = 0, None
            for ts, r in ud.iterrows():
                stamp = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
                if stamp <= since:
                    continue
                newest = max(newest or stamp, stamp)
                firm = str(r.get("Firm") or "").strip()
                to_g, from_g = str(r.get("ToGrade") or "").strip(), str(r.get("FromGrade") or "").strip()
                action = str(r.get("Action") or "").strip()
                pt_action = str(r.get("priceTargetAction") or "").strip()
                cur_pt, prior_pt = _num(r.get("currentPriceTarget")), _num(r.get("priorPriceTarget"))
                cur_pt, prior_pt = (cur_pt or None), (prior_pt or None)
                grade_changed = action in ("up", "down", "init") or bool(from_g and to_g and from_g != to_g)
                parts = [firm]
                if grade_changed:
                    parts.append((f"{from_g} → " if from_g else "") + to_g + ACTION_KO.get(action, ""))
                elif to_g:
                    parts.append(f"{to_g} 유지")
                if cur_pt:
                    if prior_pt and prior_pt != cur_pt:
                        pt_txt = f"목표가 ${prior_pt:,.0f} → ${cur_pt:,.0f}"
                        if pt_action:
                            pt_txt += f" ({PT_ACTION_KO.get(pt_action, pt_action)})"
                    else:
                        pt_txt = f"목표가 ${cur_pt:,.0f} 유지"
                    parts.append(pt_txt)
                text = " · ".join(p for p in parts if p)
                item_id = f"analyst:{ts.strftime('%Y%m%d%H%M%S')}:{firm.lower().replace(' ', '_')}"
                if action == "up" or pt_action == "Raises":
                    direction = "positive"
                elif action == "down" or pt_action == "Lowers":
                    direction = "negative"
                else:
                    direction = "neutral"
                conn.execute(
                    """INSERT OR IGNORE INTO items(item_id, kind, published_at, title, summary, url, source, raw_json, collected_at,
                           ai_area, ai_direction, ai_novelty, ai_relevance, ai_fact, analyzed_at, is_event)
                       VALUES (?, 'analyst', ?, ?, NULL, NULL, 'yfinance', ?, ?, 'Earnings', ?, 'new', 2, ?, ?, ?)""",
                    (item_id, stamp, text,
                     db.dumps({"firm": firm, "to": to_g, "from": from_g, "action": action, "pt_action": pt_action,
                               "pt": cur_pt, "pt_prior": prior_pt}),
                     db.now_iso(), direction, text, db.now_iso(), 1 if grade_changed else 0))
                new += 1
            if newest:
                db.set_meta(conn, "analyst_last_seen", newest)
            conn.commit()
            print(f"[analysts] 변경 {new}건 신규 (기준 {since[:10]} 이후)")
    except Exception as e:  # noqa: BLE001
        print(f"[analysts] upgrades_downgrades 실패: {e}")
    return out


def collect_holdings(conn, t, day, close):
    out = {}
    try:
        info = t.info or {}
        out["shares_short"] = info.get("sharesShort")
        out["shares_short_prior"] = info.get("sharesShortPriorMonth")
        spf = info.get("shortPercentOfFloat")
        out["short_pct_float"] = spf * 100 if spf else None
        asof = info.get("dateShortInterest")
        out["short_asof"] = datetime.datetime.fromtimestamp(asof, datetime.timezone.utc).strftime("%Y-%m-%d") if asof else None
        fwd_eps = info.get("forwardEps")
        out["forward_pe"] = (close / fwd_eps) if close and fwd_eps else None
    except Exception as e:  # noqa: BLE001
        print(f"[holdings] info 실패: {e}")
    try:
        ih = t.institutional_holders
        if ih is not None and not ih.empty:
            asof = str(ih.iloc[0]["Date Reported"])[:10]
            rows = []
            for _, r in ih.iterrows():
                chg = _num(r.get("pctChange"))
                rows.append({"holder": str(r["Holder"]), "pct_held": float(r["pctHeld"]) * 100,
                             "shares": float(r["Shares"]), "pct_change": chg * 100 if chg is not None else None})
            db.upsert(conn, "quarterly", {
                "fiscal_quarter": asof, "metric": "institutional_top10",
                "value": sum(r["pct_held"] for r in rows), "value_json": db.dumps(rows), "unit": "% of shares",
                "source": "yfinance institutional_holders", "source_url": None, "recorded_at": db.now_iso(), "verified": 1,
            }, ("fiscal_quarter", "metric"))
            conn.commit()
            print(f"[holdings] 기관 상위 {len(rows)}곳 (기준일 {asof}) · 공매도 {out.get('shares_short')} ({out.get('short_asof')})")
    except Exception as e:  # noqa: BLE001
        print(f"[holdings] institutional_holders 실패: {e}")
    return out


# ── 상태판 한 행 ────────────────────────────────────────────────────────────

STATE_FIELDS_MARKET = [
    "iv_atm_30d", "implied_move_next_earnings", "pc_ratio_oi", "pc_ratio_vol", "gex_approx", "gex_flip_strike",
    "max_oi_strike_call", "max_oi_strike_put", "option_expiries",
    "eps_est_cq", "eps_est_cq_7d_chg_pct", "rev_est_cq", "rev_est_cq_7d_chg_pct",
    "revisions_up_30d", "revisions_down_30d", "eps_est_ny",
    "rating_counts_json", "pt_mean", "pt_high", "pt_low", "pt_median",
    "shares_short", "shares_short_prior", "short_pct_float", "short_asof", "forward_pe",
]
# 아직 수집기가 없는 칸 (④단계) — 미수집 목록에 세지 않는다
STATE_FIELDS_LATER = ["smh_shares_out", "soxx_shares_out", "news_count"]


def collect_state(conn, day, next_earnings_day=None, skip_options=False):
    """옵션·추정치·애널리스트·보유를 모아 daily_state[day]에 쓴다. 가격·기술 칸은 judge가 일봉에서 채운다."""
    t = yf.Ticker(config.SYMBOL)
    close = close_on(conn, config.SYMBOL, day)
    merged = {}
    if not skip_options and close:
        try:
            m, _ = collect_options(conn, t, day, close, next_earnings_day)
            merged.update(m)
        except Exception as e:  # noqa: BLE001
            print(f"[options] 실패 — 옵션 칸 비움: {e}")
    merged.update(collect_estimates(t))
    merged.update(collect_analysts(conn, t, day))
    merged.update(collect_holdings(conn, t, day, close))
    # 매출 컨센서스 7일 변화는 yfinance에 이력이 없어 우리 스냅샷으로 잰다
    if merged.get("rev_est_cq"):
        week_ago = (datetime.date.fromisoformat(day) - datetime.timedelta(days=7)).isoformat()
        row = conn.execute(
            "SELECT rev_est_cq FROM daily_state WHERE day <= ? AND rev_est_cq IS NOT NULL ORDER BY day DESC LIMIT 1",
            (week_ago,)).fetchone()
        merged["rev_est_cq_7d_chg_pct"] = (merged["rev_est_cq"] / row["rev_est_cq"] - 1) * 100 if row and row["rev_est_cq"] else None
    row = {"day": day, "collected_at": db.now_iso()}
    row.update({f: merged.get(f) for f in STATE_FIELDS_MARKET})
    db.upsert(conn, "daily_state", row, ("day",))
    # 미수집은 저장된 행 기준으로 센다 — 재실행(--skip-options)에서 전 실행의 값이 남아 있으면 미수집이 아니다.
    # implied move는 실적이 창 안에 없으면 당연히 없고, 매출 7일 변화는 이력이 7일 쌓여야 생긴다 — 둘 다 미수집이 아니다.
    stored = dict(conn.execute("SELECT * FROM daily_state WHERE day = ?", (day,)).fetchone())
    missing = [f for f in STATE_FIELDS_MARKET if stored.get(f) is None
               and not (f == "implied_move_next_earnings" and not next_earnings_day)
               and f != "rev_est_cq_7d_chg_pct"]
    conn.execute("UPDATE daily_state SET missing_fields_json = ? WHERE day = ?", (db.dumps(missing), day))
    conn.commit()
    print(f"[state] {day} 상태판 {len(STATE_FIELDS_MARKET) - len(missing)}/{len(STATE_FIELDS_MARKET)}칸 · 미수집 {missing or '없음'}")
    return stored


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    conn = db.connect()
    collect_bars(conn, force_backfill="--backfill" in sys.argv)
    collect_state(conn, last_bar_day(conn))
