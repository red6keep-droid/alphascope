"""상세 페이지 2 · 3 탭 재료 — 애널리스트 · 이익 예상 · 공매도 · 옵션 · 분기 매출. AI 없음, 무료 (NVDA 리포트 expect · collect_market 과 같은 정의).

- 매일 (yfinance) : 애널리스트 등급 분포 · 목표가, 내년 1주당 이익 예상 추이, 공매도, 30일 옵션 내재변동성(ATM), 실적 직후 만기 스트래들
- 매일 (yfinance 옵션 체인) : 옵션 상태판 — 30일 내재변동성 · 실적 직후 만기 스트래들 · 풋/콜 비율 · 최다 미결제 행사가 (NVDA collect_options 와 같은 정의, 감마 근사는 뺀다)
- 매일 (SEC submissions) : 임원 거래(Form 4) · 수시 공시(8-K) — 구조화된 공시라 AI 없이 읽는다 (NVDA collect_edgar 의 파서 재사용)
- 주 1회 (SEC XBRL companyfacts) : 분기 매출 — 후보 20개 전부. 비교 묶음 = 후보 20개 중앙값 (NVDA 리포트의 기술주 15개 자리)
- 주 1회 (yfinance) : 함께 보는 회사(universe.PEERS) 가운데 후보 밖 종목의 실적 일정
결과는 data/extra.json (snapshot.json 과 따로 — 같은 날 다시 그릴 때 다시 받지 않게) · data/iv_history.json (변동성 순위용, 날마다 쌓는다).
"""

import datetime
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "nvda-report"))
import expect as EX  # noqa: E402  — _eps · _short · _atm_iv · revenue_series 를 그대로 쓴다

import universe as U  # noqa: E402

EXTRA = os.path.join(BASE, "data", "extra.json")
IV_HIST = os.path.join(BASE, "data", "iv_history.json")
EDGAR_DAYS = 30   # 공시는 최근 30일만 받아 둔다 (화면은 7일)
REV_MAX_AGE_DAYS = 7
EARN_LOOKAHEAD = 45   # 실적 발표가 이 안이면 실적 직후 만기 스트래들을 잰다 (NVDA config.OPTION_EARNINGS_LOOKAHEAD_DAYS)


def _analysts(t):
    out = {}
    rec = t.recommendations
    if rec is not None and not rec.empty:
        r0 = rec.iloc[0]
        out["rating_counts"] = {k: int(r0[k]) for k in ("strongBuy", "buy", "hold", "sell", "strongSell")}
    pt = t.analyst_price_targets or {}
    for k in ("mean", "median", "high", "low"):
        if pt.get(k):
            out["pt_" + k] = float(pt[k])
    return out


def _mid(row):
    bid, ask, last = row.get("bid") or 0, row.get("ask") or 0, row.get("lastPrice") or 0
    return (bid + ask) / 2 if bid and ask else (last or None)


def _straddle(t, spot, day, next_earn):
    """실적 직후 첫 만기의 ATM 콜 + 풋 중간값 ÷ 현재가 (%) — NVDA collect_options 의 implied_move_next_earnings 와 같은 값."""
    if not next_earn or not 0 <= (datetime.date.fromisoformat(next_earn) - datetime.date.fromisoformat(day)).days <= EARN_LOOKAHEAD:
        return None
    after = [e for e in t.options if e > next_earn]
    if not after:
        return None
    ch = t.option_chain(after[0])
    calls, puts = ch.calls.set_index("strike"), ch.puts.set_index("strike")
    atm = min(set(calls.index) & set(puts.index), key=lambda k: abs(k - spot))
    cm, pm = _mid(calls.loc[atm].to_dict()), _mid(puts.loc[atm].to_dict())
    return (cm + pm) / spot * 100 if cm and pm else None


def _options(t, spot, day, next_earn):
    """옵션 상태판 — NVDA collect_market.collect_options 와 같은 만기 고르기 · 같은 값 (DB 저장 · 감마 근사 없음).
    Yahoo 가 미국 자정 뒤 OI · 호가를 0 으로 비운 체인을 주는 때는 None (다음 실행에서 다시)."""
    import collect_market as CM
    import indicators
    chosen, earn_exp = CM.pick_expiries(list(t.options), day, next_earn)
    oi = {"c": 0.0, "p": 0.0}
    vol = {"c": 0.0, "p": 0.0}
    by_strike, exp_iv, implied = {}, {}, None
    lo, hi = spot * (1 - CM.config.OPTION_STRIKE_BAND), spot * (1 + CM.config.OPTION_STRIKE_BAND)
    for e in chosen:
        c = CM._chain(t, e, attempts=2)
        if c is None:
            continue
        calls, puts = c.calls.drop_duplicates("strike").set_index("strike"), c.puts.drop_duplicates("strike").set_index("strike")
        oi["c"] += float(calls["openInterest"].fillna(0).sum())
        oi["p"] += float(puts["openInterest"].fillna(0).sum())
        vol["c"] += float(calls["volume"].fillna(0).sum())
        vol["p"] += float(puts["volume"].fillna(0).sum())
        strikes = sorted(set(calls.index) | set(puts.index))
        atm = min(strikes, key=lambda k: abs(k - spot)) if strikes else None
        ivs = [v for df in (calls, puts) if atm in df.index for v in [CM._clean_iv(df.loc[atm, "impliedVolatility"])] if v]
        if ivs:
            exp_iv[e] = sum(ivs) / len(ivs)
        if e == earn_exp and atm in calls.index and atm in puts.index:
            cm, pm = CM._mid(calls.loc[atm].to_dict()), CM._mid(puts.loc[atm].to_dict())
            implied = (cm + pm) / spot * 100 if cm and pm else None
        for k in strikes:
            if lo <= k <= hi:
                s = by_strike.setdefault(float(k), [0.0, 0.0])
                s[0] += float(calls.loc[k, "openInterest"] or 0) if k in calls.index and calls.loc[k, "openInterest"] == calls.loc[k, "openInterest"] else 0
                s[1] += float(puts.loc[k, "openInterest"] or 0) if k in puts.index and puts.loc[k, "openInterest"] == puts.loc[k, "openInterest"] else 0
    iv30 = indicators.atm_iv_interpolated(exp_iv, day)
    if oi["c"] + oi["p"] <= 0 or not iv30:
        return None
    return {"iv_atm_30d": iv30, "implied_move_next_earnings": implied,
            "pc_ratio_oi": oi["p"] / oi["c"] if oi["c"] else None, "pc_ratio_vol": vol["p"] / vol["c"] if vol["c"] else None,
            "max_oi_strike_call": max(by_strike, key=lambda k: by_strike[k][0]) if by_strike else None,
            "max_oi_strike_put": max(by_strike, key=lambda k: by_strike[k][1]) if by_strike else None}


def _one(args, only=None):
    sym, spot, day, next_earn = args
    import yfinance as yf
    t = yf.Ticker(sym)
    out = {}
    for key, f in (("analysts", lambda: _analysts(t)), ("eps", lambda: EX._eps(t)), ("short", lambda: EX._short(t)),
                   ("options", lambda: _options(t, spot, day, next_earn))):
        if only and key not in only:
            continue
        try:
            out[key] = f()
        except Exception as e:   # noqa: BLE001
            print(f"[extra] {sym} {key} 실패 : {e}")
            out[key] = None
    o = out.get("options") or {}
    out["iv"] = o.get("iv_atm_30d")          # 실적과 기대 `시장은 큰 움직임을 예상하나?` 의 재료 = 상태판과 같은 값 (NVDA 와 같다)
    out["straddle"] = o.get("implied_move_next_earnings")
    if not out["iv"] and (not only or "options" in only):   # 상태판 체인이 비었으면 예전 방식(30일 근처 만기 ATM) 한 번
        try:
            out["iv"] = EX._atm_iv(t, spot, day)
            out["straddle"] = out["straddle"] or _straddle(t, spot, day, next_earn)
        except Exception as e:   # noqa: BLE001
            print(f"[extra] {sym} 옵션 예비 실패 : {e}")
    return sym, out


def iv_history(stocks, day):
    """30일 내재변동성을 날마다 쌓아 변동성 순위(최근 60거래일 중 0~100)를 낸다 — NVDA judge.iv_rank 와 같은 식. 60일 전에는 None + 쌓인 날 수."""
    try:
        with open(IV_HIST, encoding="utf-8") as f:
            h = json.load(f)
    except (OSError, ValueError):
        h = {}
    window = EX.config.IV_RANK_WINDOW
    for sym, v in stocks.items():
        if v.get("iv"):
            h.setdefault(sym, {})[day] = v["iv"]
        vals = [x for _, x in sorted(h.get(sym, {}).items())][-window:]
        v["iv_rank_n"] = len(vals)
        v["iv_rank"] = ((vals[-1] - min(vals)) / (max(vals) - min(vals)) * 100 if max(vals) > min(vals) else 50.0) if len(vals) >= window else None
    with open(IV_HIST, "w", encoding="utf-8") as f:
        json.dump(h, f)


def peer_earnings(have):
    """함께 보는 회사 가운데 후보 20개 밖 종목의 실적 일정 (주 1회). 후보 안 종목은 snapshot 의 실적일을 쓴다."""
    if have and (datetime.date.today() - datetime.date.fromisoformat(have["built"])).days < REV_MAX_AGE_DAYS:
        return have
    import collect
    syms = sorted({p for v in U.PEERS.values() for p in v} - set(U.BY_SYM))
    with ThreadPoolExecutor(6) as ex:
        dates = dict(ex.map(collect._earnings, syms))
    print(f"[extra] 함께 보는 회사 실적일 {sum(1 for v in dates.values() if v)}/{len(syms)}종목")
    return {"built": datetime.date.today().isoformat(), "dates": dates}


def edgar(have, cik):
    """임원 거래(Form 4) · 수시 공시(8-K) 최근 30일 — NVDA collect_edgar 의 파서 · 제목 · 방향 규칙을 그대로. 한 번 읽은 공시는 다시 받지 않는다."""
    import collect_edgar as CE
    keep = {k: v for k, v in (have or {}).items() if v["filed"] >= (datetime.date.today() - datetime.timedelta(days=EDGAR_DAYS)).isoformat()}
    cut = (datetime.date.today() - datetime.timedelta(days=EDGAR_DAYS)).isoformat()
    for sym, *_ in U.CANDIDATES:
        if sym in U.REPORT_TYPE or sym not in cik:
            continue
        try:
            rec = EX._sec(f"https://data.sec.gov/submissions/CIK{cik[sym]}.json")["filings"]["recent"]
        except Exception as e:   # noqa: BLE001
            print(f"[extra] {sym} 공시 목록 실패 : {e}")
            continue
        base = f"https://www.sec.gov/Archives/edgar/data/{int(cik[sym])}"
        for i, form in enumerate(rec["form"]):
            if form not in ("4", "8-K") or rec["filingDate"][i] < cut:
                continue
            acc = rec["accessionNumber"][i]
            key = f"{sym}:{acc}"
            if key in keep:
                continue
            row = {"sym": sym, "form": form, "filed": rec["filingDate"][i], "at": rec["acceptanceDateTime"][i].replace(".000Z", "Z"),
                   "url": f"{base}/{acc.replace('-', '')}/{rec['primaryDocument'][i]}"}
            if form == "4":
                try:
                    idx = EX._sec(f"{base}/{acc.replace('-', '')}/index.json")
                    xml = [it["name"] for it in idx["directory"]["item"] if it["name"].lower().endswith(".xml") and not it["name"].lower().startswith("xsl")]
                    if not xml:
                        continue
                    import requests
                    r = requests.get(f"{base}/{acc.replace('-', '')}/{xml[0]}", headers={"User-Agent": EX.config.EDGAR_USER_AGENT}, timeout=60)
                    r.raise_for_status()
                    info = CE.parse_form4(r.text)
                except Exception as e:   # noqa: BLE001
                    print(f"[extra] {sym} Form 4 {acc} 실패 : {e}")
                    continue
                row.update(title=CE._form4_title(info), direction=CE._direction(info), area="Flows",
                           emphasis=bool((info["shares_sold"] and not info["is_plan"]) or info["shares_bought"] or info["is_ten_percent"]))
            else:
                items = [x.strip() for x in (rec.get("items") or [""] * len(rec["form"]))[i].split(",") if x.strip()]
                row.update(title=("수시 공시 8-K · " + ", ".join(f"Item {x} {CE.ITEM_KO.get(x, '')}".strip() for x in items)) if items else "수시 공시 8-K",
                           direction="neutral", area="Earnings" if "2.02" in items else "Corporate", emphasis=True)
            keep[key] = row
    print(f"[extra] 공시 {len(keep)}건 (최근 {EDGAR_DAYS}일 · Form 4 {sum(1 for v in keep.values() if v['form'] == '4')})")
    return keep


def revenue(have):
    if have and (datetime.date.today() - datetime.date.fromisoformat(have["built"])).days < REV_MAX_AGE_DAYS:
        return have
    tickers = EX._sec("https://www.sec.gov/files/company_tickers.json")
    cik = {v["ticker"]: str(v["cik_str"]).zfill(10) for v in tickers.values()}
    series = {}
    for sym, *_ in U.CANDIDATES:
        try:
            series[sym] = EX.revenue_series(cik[sym])
        except Exception as e:   # noqa: BLE001
            print(f"[extra] {sym} 매출 실패 : {e}")
    print(f"[extra] 분기 매출 {len(series)}/{len(U.CANDIDATES)}종목 (SEC XBRL)")
    return {"built": datetime.date.today().isoformat(), "series": series}


def run(snap):
    have = load() or {}
    day = max(b[-1]["day"] for b in snap["bars"].values() if b)
    out = {"day": day, "revenue": have.get("revenue")}
    if have.get("day") == day and have.get("stocks"):
        out.update(stocks=have["stocks"], spy_iv=have.get("spy_iv"))
    else:
        jobs = []
        for sym, *_ in U.CANDIDATES:
            bars = snap["bars"].get(sym) or []
            nxt = next((e["day"] for e in snap["earnings"].get(sym) or [] if e["day"] >= day), None)
            if bars:
                jobs.append((sym, bars[-1]["close"], day, nxt))
        with ThreadPoolExecutor(6) as ex:
            out["stocks"] = dict(ex.map(_one, jobs))
        _, spy = _one((U.BENCH, snap["bars"][U.BENCH][-1]["close"], day, None), only=("options",))   # S&P 500 은 옵션만 (ETF 라 재무 값이 없다)
        out["spy_iv"] = spy.get("iv")
    iv_history(out["stocks"], day)
    try:
        out["revenue"] = revenue(have.get("revenue"))
    except Exception as e:   # noqa: BLE001
        print(f"[extra] 매출 수집 실패 — 지난 값으로 계속 : {e}")
    try:
        out["peer_earnings"] = peer_earnings(have.get("peer_earnings"))
    except Exception as e:   # noqa: BLE001
        print(f"[extra] 함께 보는 회사 실적일 실패 — 지난 값으로 계속 : {e}")
        out["peer_earnings"] = have.get("peer_earnings")
    try:
        tickers = EX._sec("https://www.sec.gov/files/company_tickers.json")
        cik = {v["ticker"]: str(v["cik_str"]).zfill(10) for v in tickers.values()}
        out["edgar"] = edgar(have.get("edgar"), cik)
    except Exception as e:   # noqa: BLE001
        print(f"[extra] 공시 수집 실패 — 지난 값으로 계속 : {e}")
        out["edgar"] = have.get("edgar")
    with open(EXTRA, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    ok = sum(1 for v in out["stocks"].values() if v.get("iv"))
    print(f"[extra] {day} · {len(out['stocks'])}종목 (옵션 {ok}) → {EXTRA}")
    return out


def load():
    try:
        with open(EXTRA, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
