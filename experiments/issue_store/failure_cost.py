"""실패 비용 검증 — doc/실패-비용-검증-계획.md F1 ~ F6 (결과 보기 전 고정).

    .venv/bin/python experiments/issue_store/failure_cost.py --check   # 사전 점검 (검증 아님)
    .venv/bin/python experiments/issue_store/failure_cost.py           # 검증 ("검증해" 때만)

먼저: fetch_bars.py · fetch_earnings_edgar.py · fetch_fx_krw.py · fetch_failure_inputs.py

F1 대상 = 15종목(모든 날) + 그날 S&P 500 소속 종목(소속인 날만, fja05680/sp500). 일봉이 소속 기간을 덮지 않으면
   (첫 봉이 소속 시작 30일 뒤 · 마지막 봉이 소속 끝 30일 전 · 소속 중 10일 넘는 빈칸) 다른 회사로 보고 뺌,
   removed.csv 의 ticker_reused · 이름 불일치도 뺌. 판정 P3 · P4, P1 · P2 참고, 소속 중 계산 비율 표시
F2 z = 하루 로그 수익률 ÷ 전날 종가까지 EWMA σ (normal_range.prepare). 급락 z ≤ −2 · 급등 z ≥ 2, 3σ 칸 = 첫날 |z| ≥ 3
   (2σ 칸은 3σ 포함 전체). 실행 = 다음 날 시가(open) · 그날 종가(close). 전량. 첫날 뒤 20거래일 안 같은 방향 = 같은 묶음
F3 판 사람: vs 들고 있기 · vs 아무 날(플라시보). 현금 = DTB3. 다시 사기 ① 안 돌아옴 ② 그날 종가까지 EWMA σ ≤ 사건 첫날
   252일 σ × 1.25 (평소 범위 계획 8) ③ 종가 ≥ 판 값 → 신호 다음 날 시가에 삼, 기간 끝까지 없으면 현금
   산 사람(급등): 그 뒤 수익률 vs 같은 종목 × 시기 아무 날
F4 기간 20 · 60 판정, 250 참고. 끝 = 첫날 t 로부터 h 거래일 뒤 종가(두 실행 같은 끝). 차이 = 실수 쪽 − 비교 쪽 로그 수익률.
   보고 중앙값 · 실수 비율(< 0) · 하위 10% · 수. 플라시보 2,000번, 하위 5% 밖 특히 나쁨 · 상위 5% 밖 특히 좋음,
   P3 · P4 둘 다 같은 쪽일 때만. 묶음 < 20 표본 부족
F5 시장 충격(VIX ≥ 35 ~ < 25) → 실적(15종목, 반응일) → 종목 충격(|r| ≥ 252일 σ × 4, 20거래일) → 평소, 첫날 기준
F6 매매 한 번 0.1%. 원화판 = 판 뒤 원화 환전(편도 0.25%) · 한국 3개월 금리(KR3M 월별) · 다시 살 때 재환전. 세금 없음
결과: results/failure_cost.md · failure_cost_*.csv
"""

import argparse
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

from bollinger_by_stock import STOCKS
from normal_range import (BARS, CAL, DATA, LAM, OUT, PERIODS, START, earnings_days, load_close, market_shock,
                          period_of, prepare)

Z2, Z3 = 2.0, 3.0
GROUP = 20
HS, JUDGE_H = [20, 60, 250], [20, 60]
REC_K = 1.25
COST, FX_COST = 0.001, 0.0025
N_DRAW, TAIL, MIN_N = 2000, 0.05, 20
JUDGE_P = ["P3", "P4"]
EXECS = ["open", "close"]
REBUYS = ["none", "calm", "even"]       # ① 안 돌아옴 ② 흔들림 회복 ③ 판 값
BUCKETS = ["시장 충격", "실적", "종목 충격", "평소"]
SLACK = pd.Timedelta(days=30)


# ---------- F1 소속 ----------

def membership():
    """티커 → [(시작, 끝)] (구성 목록에 나온 첫날 ~ 마지막 날). 목록 마지막 날 이후는 그대로 소속으로 둠."""
    comp = pd.read_csv(os.path.join(CAL, "sp500_components.csv"))
    comp["date"] = pd.to_datetime(comp.date)
    comp = comp.sort_values("date")
    last = comp.date.iloc[-1]
    spans, open_, prev = {}, {}, set()
    for d, s in zip(comp.date, comp.tickers):
        cur = {t.replace(".", "-") for t in s.split(",")}
        for t in cur - prev:
            open_[t] = d
        for t in prev - cur:
            spans.setdefault(t, []).append((open_.pop(t), prev_d))
        prev, prev_d = cur, d
    for t, a in open_.items():
        spans.setdefault(t, []).append((a, pd.Timestamp("2099-12-31")))
    return spans, last


def bar_frame(sym):
    f = os.path.join(BARS, sym + ".parquet")
    if not os.path.exists(f):
        return None
    b = pd.read_parquet(f)
    b.index = pd.to_datetime(b.index).tz_localize(None).normalize()
    b = b[~b.index.duplicated()]
    return b[(b.close > 0)].dropna(subset=["close"])


def screen(spans, last):
    """소속 티커마다 일봉이 같은 회사로 보이는지. 반환 DataFrame(ticker, ok, why, 첫 봉 · 마지막 봉)."""
    rem = pd.read_csv(os.path.join(DATA, "removed.csv"))
    bad = {s.replace(".", "-") for s in rem[(rem.status == "ticker_reused") |
                                          ((rem.status != "no_data") & (rem.name_match == False))].symbol}  # noqa: E712
    rows = []
    for t, sp in spans.items():
        sp = [(a, b) for a, b in sp if b >= START]
        if not sp:
            continue
        b = bar_frame(t)
        why = ""
        if b is None or b.empty:
            why = "일봉 없음"
        elif t in bad:
            why = "removed.csv 재사용 · 이름 불일치"
        else:
            idx = b.index
            for a, e in sp:
                a2, e2 = max(a, START), min(e, last, idx[-1] + SLACK + pd.Timedelta(days=1))
                if idx[0] > a2 + SLACK:
                    why = "첫 봉이 소속 시작 뒤"
                elif e <= last and idx[-1] < e - SLACK:
                    why = "마지막 봉이 소속 끝 전"
                else:
                    seg = idx[(idx >= a2) & (idx <= e2)]
                    if len(seg) > 1 and (np.diff(seg.values).max() / np.timedelta64(1, "D")) > 10:
                        why = "소속 중 빈칸 > 10일"
                if why:
                    break
        rows.append({"ticker": t, "ok": why == "", "why": why, "spans": sp,
                     "removed_later": all(e <= last for _, e in sp)})
    return pd.DataFrame(rows)


def coverage(scr):
    out = []
    for name, a, b in PERIODS:
        a, b = pd.Timestamp(a), pd.Timestamp(b)
        m = scr[[any(s <= b and e >= a for s, e in sp) for sp in scr.spans]]
        out.append({"period": name, "members": len(m), "ok": int(m.ok.sum()),
                    "pct": round(100 * m.ok.mean(), 1), "removed_later": int(m.removed_later.sum()),
                    "removed_later_ok": int((m.removed_later & m.ok).sum())})
    return pd.DataFrame(out)


# ---------- 금리 · 환율 ----------

def rates(idx):
    """거래일마다 하루 로그 이자 (미 국채 · 한국), 원/달러 로그 수준."""
    def daily(name):
        s = load_close(name)
        s = s.reindex(s.index.union(idx)).ffill().reindex(idx)
        return (np.log1p(s / 100) / 252).fillna(0).values
    fx = load_close("DEXKOUS")
    fx = np.log(fx.reindex(fx.index.union(idx)).ffill().reindex(idx)).values
    return daily("DTB3"), daily("KR3M"), fx


# ---------- 한 종목 ----------

def first_hit(cond, start, stop):
    """start ≤ j < stop 에서 cond 가 참인 첫 j, 없으면 -1."""
    if start >= stop:
        return -1
    k = np.flatnonzero(cond[start:stop])
    return start + int(k[0]) if len(k) else -1


def outcomes(o, c, calm_sd, base, us, kr, fx, t, ex):
    """기준 날 t, 실행 ex 에서: 들고 있기 · 산 사람 · 판 사람(다시 사기 셋 · 달러 / 원화). h 별 dict, 끝이 없으면 None."""
    n = len(c)
    e = t + 1 if ex == "open" else t
    if e >= n:
        return None
    p = o[e] if ex == "open" else c[e]
    if not np.isfinite(p) or p <= 0:
        return None
    lp = np.log(p)
    lc = np.log(c)
    cus = np.concatenate([[0.0], np.cumsum(us)])   # cus[j] = 0..j-1 이자 합
    ckr = np.concatenate([[0.0], np.cumsum(kr)])
    hmax = t + max(HS)
    stop = min(hmax, n - 1)
    sig = {"none": -1,
           "calm": first_hit(calm_sd <= REC_K * base, t + 1, stop) if np.isfinite(base) else -1,
           "even": first_hit(c >= p, t + 1, stop)}
    res = {}
    for h in HS:
        E = t + h
        if E >= n:
            res[h] = None
            continue
        hold = lc[E] - lp
        r = {"hold": hold, "buy": hold + np.log(1 - COST)}
        hold_krw = hold + fx[E] - fx[e]
        for rb, j in sig.items():
            k = j + 1 if j >= 0 else -1          # 다시 사는 날 (시가)
            if k < 0 or k > E or not np.isfinite(o[k]) or o[k] <= 0:
                k = -1
            # 현금 이자: e 장 이후 ~ 다시 사는 날 시가(또는 E 종가). 이자는 거래일 단위 근사
            end_cash = k if k >= 0 else E + 1
            usd = np.log(1 - COST) + (cus[end_cash] - cus[e + 1])
            krw = np.log(1 - COST) + np.log(1 - FX_COST) + (ckr[end_cash] - ckr[e + 1])
            if k >= 0:
                stock = lc[E] - np.log(o[k]) + np.log(1 - COST)
                usd += stock
                krw += np.log(1 - FX_COST) + stock + fx[E] - fx[k]
            r["sell_" + rb] = usd - hold
            r["sellkrw_" + rb] = krw - hold_krw
            r["back_" + rb] = k >= 0
        res[h] = r
    return res


def bucket_of(P, earn_days, t):
    if P["mshock"].values[t]:
        return "시장 충격"
    if earn_days is not None and P["earn"].values[t]:
        return "실적"
    if P["sshock"].values[t]:
        return "종목 충격"
    return "평소"


def stock_days(sym, spans, rate_cache):
    """한 종목: (기준 날 행 DataFrame, 아무 날 행 DataFrame). 아무 날 = 유효한 모든 날."""
    b = bar_frame(sym)
    if b is None or len(b) < 300:
        return None
    idx = b.index
    c, o = b.close.values.astype(float), b.open.values.astype(float)
    o = np.where((o > 0) & np.isfinite(o), o, np.nan)
    r = pd.Series(np.log(c), index=idx).diff()
    is15 = sym in STOCKS
    if is15:
        edays, _ = earnings_days(sym, idx)
        earn = pd.Series(idx.isin(list(edays)), index=idx)
    else:
        earn = pd.Series(False, index=idx)
    P = prepare(r, earn, market_shock(idx))
    sd = P["sd"]["ewma"].values
    z = r.values / sd
    r_in = r.where(~earn)
    calm_sd = np.sqrt((r_in ** 2).ewm(alpha=1 - LAM, adjust=False, ignore_na=True).mean()).values  # 그날 종가까지
    base = P["s252"].values
    us, kr, fx = rates(idx)

    member = np.ones(len(idx), bool)
    if spans is not None:
        member[:] = False
        for a, e in spans:
            member |= (idx >= a) & (idx <= e)
    valid = member & (idx >= START) & np.isfinite(z) & np.isfinite(base)
    per = np.array([period_of(d) for d in idx], dtype=object)

    def rows_for(ts, extra):
        out = []
        for t in ts:
            for ex in EXECS:
                res = outcomes(o, c, calm_sd, base[t], us, kr, fx, t, ex)
                if res is None:
                    continue
                for h, rr in res.items():
                    if rr is None:
                        continue
                    row = {"symbol": sym, "t": idx[t], "period": per[t], "exec": ex, "h": h}
                    row.update(extra(t))
                    row.update(rr)
                    out.append(row)
        return out

    # 기준 날 → 묶음
    ev, cnt = [], {}
    for direction, hit in (("drop", z <= -Z2), ("spike", z >= Z2)):
        hv = hit & valid
        last = -10 ** 9
        for t in np.flatnonzero(hv):
            if t - last <= GROUP:
                continue
            ev.append(t)
            cnt[(direction, t)] = int(hv[t:t + GROUP + 1].sum())   # 묶음 안 횟수 (첫날 포함)
            last = t
    E = rows_for(sorted(ev), lambda t: {})
    for row in E:
        t = idx.get_loc(row["t"])
        d0 = "drop" if z[t] < 0 else "spike"
        row.update({"dir": d0, "z": round(float(z[t]), 2), "tier3": abs(z[t]) >= Z3,
                    "bucket": bucket_of(P, edays if is15 else None, t), "n_in_group": cnt[(d0, t)]})
    A = rows_for(np.flatnonzero(valid & np.isin(per, JUDGE_P)), lambda t: {})
    return pd.DataFrame(E), pd.DataFrame(A)


# ---------- 판정 ----------

def placebo(pool, ev_vals, rng):
    """사건 중앙값이 아무 날 같은 수 중앙값 분포에서 어디인가 → (분위, 판정)."""
    n = len(ev_vals)
    if n < MIN_N or len(pool) < n * 2:
        return np.nan, "표본 부족"
    med = np.median(ev_vals)
    # 사건은 20거래일 넘게 떨어져 있음 → 아무 날도 21일 블록에서 서로 다른 블록 n 개, 블록 안 하루씩 (사전 점검에서 고침)
    nb = len(pool) // (GROUP + 1)
    if nb < n:
        return np.nan, "표본 부족"
    blocks = np.argsort(rng.random((N_DRAW, nb)), axis=1)[:, :n]
    pick = blocks * (GROUP + 1) + rng.integers(0, GROUP + 1, size=(N_DRAW, n))
    draws = np.median(pool[pick], axis=1)
    q = float((draws < med).mean() + 0.5 * (draws == med).mean())
    return q, ("특히 나쁨" if q < TAIL else "특히 좋음" if q > 1 - TAIL else "구분 안 됨")


def cells(sym, E, A, rng):
    """한 종목 칸 표. 판 사람 지표 = sell_* (클수록 판 쪽이 나음 → 실수 비용은 음수), 산 사람 = buy."""
    rows = []
    if E.empty:
        return rows
    for (per, d, ex, h), g in E.groupby(["period", "dir", "exec", "h"]):
        for tier in (False, True):
            gt = g[g.tier3] if tier else g
            for bk in BUCKETS + ["전체"]:
                gb = gt if bk == "전체" else gt[gt.bucket == bk]
                if gb.empty:
                    continue
                pool = A[(A.period == per) & (A.exec == ex) & (A.h == h)] if not A.empty else A
                metrics = ["sell_none", "sell_calm", "sell_even", "sellkrw_none", "sellkrw_calm", "sellkrw_even"] \
                    if d == "drop" else ["buy"]
                for m in metrics:
                    v = gb[m].values
                    row = {"symbol": sym, "period": per, "dir": d, "exec": ex, "h": h, "tier": "3σ" if tier else "2σ",
                           "bucket": bk, "metric": m, "n": len(v), "median": float(np.median(v)),
                           "mistake_pct": float((v < 0).mean() * 100) if d == "drop" else np.nan,
                           "p10": float(np.quantile(v, 0.1))}
                    if d == "drop" and m.startswith("sell_"):
                        row["back_pct"] = float(gb["back_" + m[5:]].mean() * 100)
                    judge = per in JUDGE_P and h in JUDGE_H and not m.startswith("sellkrw") and bk != "전체" \
                        and len(pool)
                    if judge:
                        pv = pool[m].values
                        row["anyday_median"] = float(np.median(pv))
                        row["q"], row["verdict"] = placebo(pv, v, rng)
                    rows.append(row)
    return rows


def work(args):
    sym, spans, seed = args
    try:
        out = stock_days(sym, spans, None)
    except Exception as e:  # noqa: BLE001
        return sym, None, None, repr(e)
    if out is None:
        return sym, None, None, "짧음"
    E, A = out
    rng = np.random.default_rng(seed)
    return sym, E, pd.DataFrame(cells(sym, E, A, rng)), ""


# ---------- 사전 점검 ----------

def check():
    t0 = time.time()
    spans, last = membership()
    print(f"구성 목록 마지막 날 {last.date()} — 그 뒤는 마지막 목록 그대로")
    # 1) removed.csv 대조
    rem = pd.read_csv(os.path.join(DATA, "removed.csv"))
    rem["sym"] = rem.symbol.str.replace(".", "-", regex=False)
    rem["removed"] = pd.to_datetime(rem.removed)
    hit = near = 0
    miss = []
    for s, d in zip(rem.sym, rem.removed):
        ends = [e for _, e in spans.get(s, []) if e < pd.Timestamp("2099-01-01")]
        if any(abs((e - d).days) <= 7 for e in ends):
            hit += 1
        elif any(abs((e - d).days) <= 60 for e in ends):
            near += 1
        else:
            miss.append((s, d.date(), [x.date() for x in ends]))
    print(f"\n[1] removed.csv {len(rem)}건 중 구성 목록 퇴출일 ±7일 일치 {hit} · ±60일 {near} · 불일치 {len(miss)}")
    for m in miss[:15]:
        print("    불일치", m)
    gone16 = {t for t, sp in spans.items() for _, e in sp if pd.Timestamp("2016-01-01") <= e <= last}
    print(f"    구성 목록에서 2016 ~ 퇴출 티커 {len(gone16)}, 그중 removed.csv 에 없음 {len(gone16 - set(rem.sym))}")
    # 2) 일봉 거르기 · 비율
    scr = screen(spans, last)
    print(f"\n[2] 1999 ~ 소속 티커 {len(scr)}: 사용 {int(scr.ok.sum())} · 제외 사유", scr.why.value_counts().to_dict())
    print(coverage(scr).to_string(index=False))
    # 3) 시가 품질
    ok = scr[scr.ok].ticker.tolist() + [s for s in STOCKS if s not in set(scr.ticker)]
    bad_open = tot = same = 0
    for s in ok:
        b = bar_frame(s)
        b = b[b.index >= START]
        tot += len(b)
        bad_open += int(((b.open <= 0) | b.open.isna()).sum())
        same += int((b.open == b.close).sum())
    print(f"\n[3] 시가: {tot:,}일 중 0 · 빈 값 {bad_open} · 시가 = 종가 {same} ({100 * same / tot:.2f}%)")
    # 4) 금리 · 환율 덮는 범위
    for nm in ["DTB3", "KR3M", "DEXKOUS"]:
        s = load_close(nm)
        print(f"[4] {nm}: {s.index[0].date()} ~ {s.index[-1].date()}, 1999 ~ 빈 값 없음 = {s[s.index >= START].notna().all()}")
    # 5) 묶음 수 (손익 안 봄)
    print("\n[5] 칸별 묶음 수 (실행 open · h 20 기준, 손익은 계산하지만 출력 안 함)")
    jobs = [(s, None, 0) for s in STOCKS] + [(t, sp, 0) for t, sp in zip(scr[scr.ok].ticker, scr[scr.ok].spans)
                                             if t not in STOCKS]
    with Pool(8) as pool:
        res = pool.map(_count, jobs, chunksize=4)
    C = pd.concat([r for r in res if r is not None])
    C["group"] = np.where(C.symbol.isin(STOCKS), "15종목", "소속 전체")
    for g, gg in C.groupby("group"):
        piv = gg.groupby(["period", "dir", "tier", "bucket"]).n.agg(["median", lambda x: (x >= MIN_N).mean() * 100])
        piv.columns = ["종목당 중앙값", f"≥{MIN_N} 비율%"]
        print(f"\n  {g}\n" + piv.round(0).to_string())
    print(f"\n{time.time() - t0:.0f}초")


def _count(args):
    sym, spans, _ = args
    try:
        out = stock_days_events_only(sym, spans)
    except Exception as e:  # noqa: BLE001
        print("오류", sym, repr(e), file=sys.stderr)
        return None
    return out


def stock_days_events_only(sym, spans):
    """묶음 수만 (손익 계산 없음)."""
    b = bar_frame(sym)
    if b is None or len(b) < 300:
        return None
    idx = b.index
    r = pd.Series(np.log(b.close.values.astype(float)), index=idx).diff()
    is15 = sym in STOCKS
    if is15:
        edays, _ = earnings_days(sym, idx)
        earn = pd.Series(idx.isin(list(edays)), index=idx)
    else:
        earn = pd.Series(False, index=idx)
    P = prepare(r, earn, market_shock(idx))
    z = r.values / P["sd"]["ewma"].values
    member = np.ones(len(idx), bool)
    if spans is not None:
        member[:] = False
        for a, e in spans:
            member |= (idx >= a) & (idx <= e)
    valid = member & (idx >= START) & np.isfinite(z) & np.isfinite(P["s252"].values)
    rows = []
    for d, hit in (("drop", z <= -Z2), ("spike", z >= Z2)):
        last = -10 ** 9
        for t in np.flatnonzero(hit & valid):
            if t - last <= GROUP:
                continue
            last = t
            bk = bucket_of(P, edays if is15 else None, t)
            for tier in ("2σ", "3σ") if abs(z[t]) >= Z3 else ("2σ",):
                rows.append((sym, period_of(idx[t]), d, tier, bk))
    df = pd.DataFrame(rows, columns=["symbol", "period", "dir", "tier", "bucket"])
    full = pd.MultiIndex.from_product([[sym], [p for p, _, _ in PERIODS], ["drop", "spike"], ["2σ", "3σ"], BUCKETS],
                                      names=["symbol", "period", "dir", "tier", "bucket"])
    n = df.groupby(["symbol", "period", "dir", "tier", "bucket"]).size().reindex(full, fill_value=0).rename("n")
    n = n.reset_index()
    if spans is not None:   # 소속이 아닌 시기는 빼기
        keep = [any(a <= pd.Timestamp(pb) and e >= pd.Timestamp(pa) for a, e in spans) for _, pa, pb in PERIODS]
        n = n[n.period.isin([p for (p, _, _), k in zip(PERIODS, keep) if k])]
    if not is15:
        n = n[n.bucket != "실적"]
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        check()
    else:
        sys.exit("검증 실행은 아직 연결 전 — 사전 점검 뒤 run_all 을 붙인다")


if __name__ == "__main__":
    main()
