"""종목 특성 2단계 검증 — 돌(평소보다 훨씬 큰 날) (2026-11-23 사용자 "진행해").

전제(사용자와 하나씩 정함) = 비공개 alphascope-docs/doc/검증/종목-특성-2단계-검증.md 3절. 결과 = 같은 폴더 종목-특성-2단계-결과.md (이 스크립트가 쓴다).

    python experiments/stock-character/collect_earn_days.py --market us   # 먼저 실적일(미국 · 한국)
    python experiments/stock-character/collect_earn_days.py --market kr
    python experiments/stock-character/check_stage2.py                    # 853종목 (일봉 캐시 없으면 받는다)
    python experiments/stock-character/check_stage2.py --test             # 시험 — 시장마다 몇 업종 20여 종목, 문서 안 씀

자료 = 1단계와 같은 일봉(data/store/character/bars_{us,kr}.pkl) + 실적일(earn_days_{us,kr}.csv). AI 0 · 로컬 한 번.

돌 (전제 1):
  평소 = 그날 **전** 250거래일 하루 로그 수익률 표준편차(전날까지, 200일 이상 있을 때).
  그대로 돌 = |수익률| > 평소 × 3.
  나머지 = 수익률 − (지수 몫 + 업종 몫). 지수 몫 = 지수 민감도 × 지수 수익률, 업종 몫 = 업종 민감도 × (업종 중앙값 − 지수).
           민감도는 전날까지 250거래일 회귀(그날은 넣지 않는다).
  나머지 돌 = |나머지| > 나머지의 평소 × 3.
출처 (전제 3): 그대로 돌이 나머지 돌이기도 하면 종목 돌. 아니면 |지수 몫| 과 |업종 몫| 중 큰 쪽 → 시장 돌 / 업종 돌.
  나머지 돌인데 그대로 돌이 아니면 숨은 종목 돌. 종목 돌인데 그날 지수도 자기 평소 × 3 을 넘었으면 겹친 날로 센다.
실적일 (전제 2 · 5): 미국 = 접수 16:00 뒤면 다음 거래일, 아니면 그날 하루. 한국 = 공시일 당일 + 다음 거래일(이틀 창).
여운 (전제 4): 돌 다음 1 · 5 · 20거래일 나머지 누적 × 돌 방향 ÷ 나머지의 평소(= 평소 하루의 몇 배), 20일 안에 돌이 또 오면 그 전날까지.
  비교 대상 = 같은 종목 · 같은 구간의 돌 없는 날 뒤 같은 값. 종목 값 = 돌 평균 − 비교 대상 평균. 구간 안 돌 8개 미만이면 뺀다.
  가라앉는 날 수 = 돌 뒤 장중 폭이 자기 평소(전 250거래일 중앙값) × 1.5 아래로 처음 내려오는 날까지(60일에서 멈춤).

축:
  ④ n_stone 돌 잦기(1년당) · x_stone 돌 크기(평소의 몇 배, 중앙값) · n_own 나머지 돌 잦기(1년당)
  ⑤ aft1 · aft5 · aft20 여운 · calm 가라앉는 날 수
  ⑥ sh_mkt · sh_sec · sh_own 그대로 돌의 출처 몫 · sched 종목 자체 돌(숨은 것 포함) 중 실적일 몫 · hidden 숨은 종목 돌 몫
     earn_x 실적일 나머지 움직임(평소의 몇 배, 중앙값)
판정 기준은 1단계와 같은 셋(유지 · 겹침 · 업종 크기 빼고 남나) + 1단계에서 통과한 축과 겹치나.
"""

import csv
import datetime
import os
import sys

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)   # 빈 칸 평균(시험처럼 종목이 적을 때)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_stage1 as s1  # noqa: E402
import collect_earn_days as ce  # noqa: E402

STORE = s1.STORE
DOC = os.path.join(os.path.dirname(s1.DOC), "종목-특성-2단계-결과.md")
W, W_MIN = 250, 200            # 평소 = 전 250거래일(200일 이상 있을 때)
K = 3.0                        # 돌 = 평소 × 3
HS = (1, 5, 20)                # 여운 창
MIN_STONE = 8                  # 구간 안 돌 8개 미만이면 여운 · 출처 몫을 내지 않는다
MIN_OWN, MIN_EARN = 5, 6       # 예정된 몫 = 종목 자체 돌 5개 이상 · 실적일 움직임 = 실적일 6번 이상
CALM_X, CALM_CAP = 1.5, 60
VALID_COVER = 0.6              # 평소를 잴 수 있는 날이 구간 거래일의 60% 이상(맨 앞 구간은 첫 해가 평소 재는 데 쓰인다)
METRICS = [("n_stone", "④ 돌 잦기(1년당)"), ("x_stone", "④ 돌 크기(평소의 몇 배)"), ("n_own", "④ 나머지 돌 잦기(1년당)"),
           ("aft1", "⑤ 여운 1일"), ("aft5", "⑤ 여운 5일"), ("aft20", "⑤ 여운 20일"), ("calm", "⑤ 가라앉는 날 수"),
           ("sh_mkt", "⑥ 시장 돌 몫"), ("sh_sec", "⑥ 업종 돌 몫"), ("sh_own", "⑥ 종목 돌 몫"),
           ("sched", "⑥ 종목 자체 돌 중 실적일 몫"), ("hidden", "⑥ 숨은 종목 돌 몫"), ("earn_x", "⑥ 실적일 움직임(평소의 몇 배)")]
STAGE1 = [("hl", "1단계 장중 폭"), ("vol", "1단계 하루 등락 흩어짐"), ("beta", "1단계 지수 민감도"), ("idio", "1단계 혼자 움직이는 몫"), ("r2_sec", "1단계 업종 묶임")]
TEST_SECTORS = {"us": ["Information Technology", "Financials", "Consumer Staples"], "kr": None}
SRC = {"mkt": "시장 돌", "sec": "업종 돌", "own_sched": "종목 돌 · 실적일", "own_free": "종목 돌 · 예고 없음", "hidden": "숨은 종목 돌"}
KIND = {"8k202": "실적 발표 공시(8-K 2.02)", "10q": "분기보고서(10-Q)", "10k": "연간보고서(10-K)",
        "prelim": "잠정실적", "change30": "손익구조 변동 공시", "report": "분기 · 반기 · 사업보고서"}


# ─── 자료 ───────────────────────────────────────────────────────────────
def load_earn(mkt, test_syms=None):
    """{종목: [(공시일, 장 마감 뒤인가, 종류)]}. 시험 때는 수집기를 그 종목만 불러 바로 만든다."""
    out = {}
    if test_syms is not None:
        if mkt == "us":
            ciks = ce.us_cik_map()
            for s in test_syms:
                cik = ciks.get(s.upper())
                if cik:
                    out[s] = [(e["day"], e["after_close"] == 1, e["kind"]) for e in ce.us_events(ce.us_raw(s, cik, False))]
        else:
            _, corp = ce.universe()
            key = ce.dart_key()
            for s in test_syms:
                if corp.get(s):
                    out[s] = [(e["day"], False, e["kind"]) for e in ce.kr_events(ce.kr_raw(s, corp[s], key, False))]
        return out
    path = os.path.join(STORE, f"earn_days_{mkt}.csv")
    if not os.path.exists(path):
        raise SystemExit(f"{path} 없음 — 먼저 collect_earn_days.py --market {mkt}")
    for r in csv.DictReader(open(path, encoding="utf-8")):
        sym = r["sym"].replace(".", "-") if mkt == "us" else r["sym"]
        out.setdefault(sym, []).append((r["day"], r["after_close"] == "1", r["kind"]))
    return out


def earn_coverage(earn):
    by = {}
    for s, ev in earn.items():
        for day, _, kind in ev:
            b = by.setdefault(day[:4], {"syms": set(), "n": 0, "kinds": {}})
            b["syms"].add(s); b["n"] += 1
            b["kinds"][kind] = b["kinds"].get(kind, 0) + 1
    return by


# ─── 하루 단위 계산 ─────────────────────────────────────────────────────
def day_frame(d, r, m, k):
    """한 종목 전체 기간 → 하루마다 평소 · 나머지 · 돌 표시. d = 일봉, r = 로그 수익률, m = 지수, k = 업종 중앙값."""
    j = pd.concat([r.rename("r"), m.rename("m"), (k - m).rename("x")], axis=1, sort=True).dropna()
    if len(j) < W + 60:
        return None
    ro = j.rolling(W, min_periods=W_MIN)
    mean = ro.mean()
    v_m, v_x = ro["m"].var(), ro["x"].var()
    c_mx = j["m"].rolling(W, min_periods=W_MIN).cov(j["x"])
    c_my = j["m"].rolling(W, min_periods=W_MIN).cov(j["r"])
    c_xy = j["x"].rolling(W, min_periods=W_MIN).cov(j["r"])
    det = (v_m * v_x - c_mx ** 2).where(lambda z: z > 1e-18)
    bm = ((v_x * c_my - c_mx * c_xy) / det).shift(1)        # 전날까지의 민감도
    bx = ((v_m * c_xy - c_mx * c_my) / det).shift(1)
    a = (mean["r"] - (v_x * c_my - c_mx * c_xy) / det * mean["m"] - (v_m * c_xy - c_mx * c_my) / det * mean["x"]).shift(1)
    j["p_m"], j["p_x"] = bm * j["m"], bx * j["x"]
    j["res"] = j["r"] - a - j["p_m"] - j["p_x"]
    j["sd"] = j["r"].rolling(W, min_periods=W_MIN).std().shift(1)
    j["sd_res"] = j["res"].rolling(W, min_periods=W_MIN).std().shift(1)
    j["sd_m"] = j["m"].rolling(W, min_periods=W_MIN).std().shift(1)
    j["ok"] = j["sd"].notna() & j["sd_res"].notna() & (j["sd"] > 0) & (j["sd_res"] > 0)
    j["raw"] = j["ok"] & (j["r"].abs() > K * j["sd"])
    j["own"] = j["ok"] & (j["res"].abs() > K * j["sd_res"])
    j["mkt_big"] = j["m"].abs() > K * j["sd_m"]
    hl = np.log(d["high"] / d["low"]).reindex(j.index)
    j["hl_x"] = hl / hl.rolling(W, min_periods=W_MIN).median().shift(1)
    return j


def mark_earn(j, events, kr):
    """실적일 반응 날 표시. 미국 = 하루(접수 16시 뒤면 다음 거래일), 한국 = 공시일 당일 + 다음 거래일."""
    n = len(j)
    flag = np.zeros(n, bool)
    evs = []                                   # (반응 날 위치들, 종류)
    for day, after, kind in events:
        t = pd.Timestamp(day)
        p = j.index.searchsorted(t, side="right" if after else "left")
        if p >= n or (j.index[p] - t).days > 7:    # 거래정지 · 자료 끝
            continue
        pos = [p, p + 1] if kr and p + 1 < n else [p]
        flag[pos] = True
        evs.append((pos, kind))
    return flag, evs


def stones_of(j, earn_flag):
    """돌마다 한 줄 — 출처 · 크기 · 여운 · 가라앉는 날 수."""
    r, res, sd, sdr = j["r"].values, j["res"].values, j["sd"].values, j["sd_res"].values
    raw, own, hlx = j["raw"].values, j["own"].values, j["hl_x"].values
    pm, px, big = j["p_m"].values, j["p_x"].values, j["mkt_big"].values
    n = len(j)
    hit = np.flatnonzero(raw | own)
    rows = []
    for q, i in enumerate(hit):
        nxt = hit[q + 1] if q + 1 < len(hit) else n      # 다음 돌(그대로 · 나머지 어느 쪽이든)
        if raw[i] and own[i]:
            src = "own_sched" if earn_flag[i] else "own_free"
        elif raw[i]:
            src = "mkt" if abs(pm[i]) >= abs(px[i]) else "sec"
        else:
            src = "hidden"
        sign = np.sign(r[i]) if raw[i] else np.sign(res[i])
        row = {"date": j.index[i], "pos": i, "src": src, "raw": bool(raw[i]), "own": bool(own[i]), "sched": bool(earn_flag[i]),
               "up": sign > 0, "x": abs(r[i]) / sd[i], "x_res": abs(res[i]) / sdr[i], "overlap": bool(own[i] and big[i])}
        for h in HS:
            e = min(i + h, nxt - 1, n - 1)
            row[f"aft{h}"] = sign * np.nansum(res[i + 1:e + 1]) / sdr[i] if e > i else np.nan
        calm = np.nan
        for t in range(i + 1, min(i + 1 + CALM_CAP, n)):
            if hlx[t] < CALM_X:
                calm = t - i
                break
        row["calm"] = calm if not np.isnan(calm) else (CALM_CAP if i + CALM_CAP < n else np.nan)
        rows.append(row)
    return pd.DataFrame(rows)


def baseline(j):
    """돌 없는 날 뒤 같은 값(방향 × 뒤 h일 나머지 누적 ÷ 나머지의 평소) — 하루마다."""
    quiet = j["ok"] & ~j["raw"] & ~j["own"]
    out = {}
    for h in HS:
        fwd = j["res"].rolling(h).sum().shift(-h)
        out[h] = (np.sign(j["r"]) * fwd / j["sd_res"]).where(quiet)
    return pd.DataFrame(out)


# ─── 종목 · 구간 값 ─────────────────────────────────────────────────────
def measure(mkt, uni, bars, earn):
    idx = {b: s1.clean(bars[b]) for b in {v["bench"] for v in uni.values()} if b in bars}
    valid, rets = {}, {}
    for s in uni:
        if s not in bars:
            continue
        d = s1.clean(bars[s])
        if len(d) < 300:
            continue
        valid[s] = d.iloc[s1.SKIP_NEW:]
        rets[s] = np.log(valid[s]["close"]).diff()
    R = pd.DataFrame(rets)
    by_sec = {}
    for s in R.columns:
        by_sec.setdefault(uni[s]["sector"], []).append(s)
    sec_ret = {}
    for mem in by_sec.values():
        for s in mem:
            others = R[mem].drop(columns=[s])
            if others.shape[1] >= 3:
                sec_ret[s] = others.median(axis=1).where(others.notna().sum(axis=1) >= 3)
    mret = {b: np.log(d["close"]).diff() for b, d in idx.items()}
    end = max(d.index.max() for d in valid.values())
    blks = s1.blocks(end, 3)
    rows, stones, events, base_hit = [], [], [], {"n": 0, "hit": 0}
    base_sum = {h: [0.0, 0] for h in HS}                     # 돌 없는 날 뒤 값 — 시장 전체 평균용
    for s, d in valid.items():
        if s not in sec_ret or uni[s]["bench"] not in mret:
            continue
        j = day_frame(d, rets[s], mret[uni[s]["bench"]], sec_ret[s])
        if j is None:
            continue
        flag, evs = mark_earn(j, earn.get(s, []), mkt == "kr")
        st = stones_of(j, flag)
        base = baseline(j)
        for h in HS:
            base_sum[h][0] += float(base[h].sum())
            base_sum[h][1] += int(base[h].count())
        own = j["own"].values
        mine = []
        for pos, kind in evs:                                 # 실적일마다 반응
            okp = [p for p in pos if j["ok"].values[p]]
            if okp:
                mine.append({"sym": s, "date": j.index[pos[0]], "kind": kind, "hit": bool(own[okp].any()),
                               "x": float(np.max(np.abs(j["res"].values[okp]) / j["sd_res"].values[okp]))})
        # 실적일이 아닌 평소 창에 종목 자체 돌이 우연히 드는 비율(한국 이틀 창 · 미국 하루 창)
        okv = j["ok"].values
        width = 2 if mkt == "kr" else 1
        for t in range(0, len(j) - width, width):
            sl = slice(t, t + width)
            if okv[sl].all() and not flag[sl].any():
                base_hit["n"] += 1
                base_hit["hit"] += int(own[sl].any())
        if len(st):
            st.insert(0, "sym", s)
            stones.append(st)
        events += mine
        ev_df = pd.DataFrame(mine)
        for name, s0, e0 in blks:
            mdays = idx[uni[s]["bench"]]
            nday = ((mdays.index >= s0) & (mdays.index <= e0)).sum()
            db = d[(d.index >= s0) & (d.index <= e0)]
            jb = j[(j.index >= s0) & (j.index <= e0)]
            nv = int(jb["ok"].sum())
            if len(db) < s1.MIN_COVER * nday or nv < VALID_COVER * nday:
                continue
            sb = st[(st.date >= s0) & (st.date <= e0)] if len(st) else st
            rw = sb[sb.raw] if len(sb) else sb
            ow = sb[sb.own] if len(sb) else sb
            o = {"mkt": mkt, "L": 3, "block": name, "start": s0.date(), "sym": s, "sector": uni[s]["sector"],
                 "size": float(np.log((db["close"] * db["volume"]).median() + 1)), "stones": len(rw),
                 "n_stone": len(rw) / nv * 252, "n_own": len(ow) / nv * 252,
                 "x_stone": float(rw.x.median()) if len(rw) >= 3 else np.nan}
            if len(rw) >= MIN_STONE:
                bb = base[(base.index >= s0) & (base.index <= e0)]
                for h in HS:
                    o[f"aft{h}"] = float(rw[f"aft{h}"].mean() - bb[h].mean())
                o["calm"] = float(rw.calm.median())
                o["sh_mkt"], o["sh_sec"] = float((rw.src == "mkt").mean()), float((rw.src == "sec").mean())
                o["sh_own"] = float(rw.own.mean())
            if len(ow) >= MIN_OWN:
                o["sched"] = float(ow.sched.mean())
                o["hidden"] = float((ow.src == "hidden").mean())
            if len(ev_df):
                eb = ev_df[(ev_df.date >= s0) & (ev_df.date <= e0)]
                if len(eb) >= MIN_EARN:
                    o["earn_x"] = float(eb.x.median())
            rows.append(o)
    df = pd.DataFrame(rows)
    for c, _ in METRICS:
        if c not in df:
            df[c] = np.nan
    S = pd.concat(stones, ignore_index=True) if stones else pd.DataFrame()
    base_mean = {h: (v[0] / v[1] if v[1] else float("nan")) for h, v in base_sum.items()}
    return df, S, pd.DataFrame(events), base_hit, base_mean, end


# ─── 문서 ───────────────────────────────────────────────────────────────
f2 = s1.f2


def kind_table(S):
    """돌 종류의 성질 — 시장 전체(종목 특성이 아님). 출처 × 방향."""
    L = ["| 돌 종류 | 방향 | 돌 수 | 크기(평소의 몇 배, 중앙값) | 여운 1일 | 여운 5일 | 여운 20일 | 가라앉는 날 수(중앙값) |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for src, lbl in SRC.items():
        for up, dl in ((True, "오름"), (False, "내림")):
            x = S[(S.src == src) & (S.up == up)]
            if len(x) < 20:
                L.append(f"| {lbl} | {dl} | {len(x)} | — | — | — | — | — |")
                continue
            size = x.x.median() if src != "hidden" else x.x_res.median()
            L.append(f"| {lbl} | {dl} | {len(x)} | {size:.1f} | {x.aft1.mean():+.2f} | {x.aft5.mean():+.2f} | {x.aft20.mean():+.2f} | {x.calm.median():.0f} |")
    return "\n".join(L)


def write_doc(res, cov, counts, test):
    L = ["# 종목 특성 2단계 검증 결과 — 돌(평소보다 훨씬 큰 날)\n",
         f"만든 날 {datetime.date.today()} · 스크립트 `experiments/stock-character/check_stage2.py` · 전제 = `종목-특성-2단계-검증.md` 3절 · AI 0\n",
         "## 1. 자료 · 실적일 채움률\n",
         "일봉 = 1단계와 같음(yfinance 수정 주가 2005 ~, 지금 목록으로 과거를 봄 = 살아남은 종목만). 실적일 = 그 분기 숫자가 처음 공개된 공시.\n"]
    for mkt in ("us", "kr"):
        n_all, n_ok, n_earn = counts[mkt]
        L.append(f"**{'미국' if mkt == 'us' else '한국'}** — 목록 {n_all}종목 · 계산된 종목 {n_ok} · 실적일 있는 종목 {n_earn}\n")
        L.append("| 해 | 실적일 잡힌 종목 | 종목당 실적일 수(분기 4회 기준) | 종류 |\n|---|---:|---:|---|")
        for y in sorted(cov[mkt]):
            b = cov[mkt][y]
            kinds = " · ".join(f"{KIND.get(k, k)} {v}" for k, v in sorted(b["kinds"].items(), key=lambda z: -z[1]))
            L.append(f"| {y} | {len(b['syms'])} | {b['n'] / len(b['syms']):.2f} | {kinds} |")
        L.append("")
    for mkt in ("us", "kr"):
        r = res[mkt]
        df, S, E, J = r["df"], r["stones"], r["events"], r["judge"]
        no = "2" if mkt == "us" else "3"
        L.append(f"## {no}. {'미국' if mkt == 'us' else '한국'}\n")
        rec = df[df.start == df.start.max()]
        L.append(f"최근 3년 구간 {len(rec)}종목 — 그대로 돌 수 중앙값 {rec.stones.median():.0f}개(3년) · 돌 8개 미만이라 여운 · 출처 몫에서 빠진 종목 {int((rec.stones < MIN_STONE).sum())}\n")
        L.append("### 유지되나 — 붙은 두 3년 구간 순위 상관 (1 = 순위 그대로, 0 = 관계 없음)\n")
        L.append("| 축 | 최근 | 평균 | 최저 | 쌍 수 | 종목 수 | 업종·크기 R² | 잔차 최근 | 잔차 평균 |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for col, lbl in METRICS:
            for _, x in J[J.axis == col].iterrows():
                L.append(f"| {lbl} | {f2(x['recent'])} | {f2(x['mean'])} | {f2(x['min'])} | {x['npairs']} | {x['n']} | {f2(x['r2_secsize'])} | {f2(x['resid_recent'])} | {f2(x['resid_mean'])} |")
        L.append("\n### 겹치나 — 최근 3년 구간, 1단계 축 · 2단계 축끼리 순위 상관 (|ρ| ≥ 0.8 = 같은 것을 잰 것)\n")
        C = r["overlap"]
        cols = list(C.columns)
        L.append("| | " + " | ".join(cols) + " |")
        L.append("|---|" + "---:|" * len(cols))
        for a in cols:
            L.append(f"| {a} | " + " | ".join(("**" + f2(C.loc[a, b]) + "**") if a != b and abs(C.loc[a, b]) >= 0.8 else f2(C.loc[a, b]) for b in cols) + " |")
        L.append("\n### 돌 종류의 성질 — 시장 전체 (종목 특성이 아니라 돌 종류의 차이)\n")
        L.append("여운 = 돌 방향 × 뒤 나머지 누적 ÷ 나머지의 평소(평소 하루의 몇 배). + 는 이어 감, − 는 되돌림. 돌 없는 날 뒤 값(비교 대상): "
                 + " · ".join(f"{h}일 {r['base'][h]:+.2f}" for h in HS) + "\n")
        L.append(kind_table(S))
        own = S[S.own]
        L.append(f"\n- 종목 돌(그대로 + 나머지) 가운데 그날 지수도 자기 평소 × 3 을 넘은 겹친 날: {int(S[S.raw & S.own].overlap.sum())} / {int((S.raw & S.own).sum())}")
        L.append(f"- 종목 자체 돌(숨은 것 포함) {len(own)}개 중 실적일 몫 {own.sched.mean():.1%}")
        bh = r["base_hit"]
        L.append(f"- 실적일이 아닌 평소 {'이틀' if mkt == 'kr' else '하루'} 창에 종목 자체 돌이 우연히 드는 비율: {bh['hit'] / max(bh['n'], 1):.2%} ({bh['n']}창)\n")
        L.append("### 실적일 반응 — 공시 종류별\n")
        L.append("| 공시 종류 | 실적일 수 | 나머지 움직임(평소의 몇 배, 중앙값) | 종목 자체 돌이 된 비율 |\n|---|---:|---:|---:|")
        for k, g in sorted(E.groupby("kind"), key=lambda z: -len(z[1])):
            L.append(f"| {KIND.get(k, k)} | {len(g)} | {g.x.median():.2f} | {g.hit.mean():.1%} |")
        if mkt == "us":
            L.append("\n(미국은 반응 날 하루. 한국은 이틀 창 중 큰 쪽이라 미국 값과 바로 견주지 않는다)")
        L.append("\n### 예시 종목\n")
        L.append(r["examples"])
        L.append("")
    head = "\n## 4. 판정 · 다음\n"
    old = open(DOC, encoding="utf-8").read() if os.path.exists(DOC) else ""
    L.append(head + old.split(head, 1)[1] if head in old else head + "\n(아래는 결과를 보고 사람이 쓴다 — 다시 돌려도 이 절은 그대로 둔다)\n")
    text = "\n".join(L)
    if test:
        print(text)
        print("\n(시험 — 문서로 쓰지 않음)")
        return
    open(DOC, "w", encoding="utf-8").write(text)
    print(f"문서 → {DOC}")


def pick_test(mkt, uni):
    """시험 종목 — 업종 셋에서 8종목씩(업종 중앙값을 내려면 한 업종에 4종목 이상)."""
    secs = TEST_SECTORS[mkt]
    by = {}
    for s, v in uni.items():
        by.setdefault(v["sector"], []).append(s)
    if secs is None:
        secs = [k for k, _ in sorted(by.items(), key=lambda z: -len(z[1]))[:3]]
    ex = set(s1.EXAMPLES[mkt])
    out = []
    for k in secs:
        mem = sorted(by.get(k, []), key=lambda s: (s not in ex, s))
        out += mem[:8]
    return out


def main():
    test = "--test" in sys.argv
    refresh = "--refresh" in sys.argv
    s1.LENGTHS = [3]
    U = s1.universe()
    res, cov, counts = {}, {}, {}
    for mkt in ("us", "kr"):
        uni = U[mkt]
        benches = sorted({v["bench"] for v in uni.values()})
        if test:
            syms = pick_test(mkt, uni)
            uni = {s: uni[s] for s in syms}
            path = os.path.join(STORE, f"bars_{mkt}_test.pkl")
            if os.path.exists(path) and not refresh:
                bars = pd.read_pickle(path)
            else:
                os.makedirs(STORE, exist_ok=True)
                bars = s1.download(syms + benches)
                pd.to_pickle(bars, path)
            earn = load_earn(mkt, syms)
        else:
            bars = s1.load_bars(mkt, list(uni) + benches, refresh)
            earn = load_earn(mkt)
        df, S, E, base_hit, base, end = measure(mkt, uni, bars, earn)
        s1.METRICS = METRICS
        J = s1.judge(df)
        s1.METRICS = STAGE1
        d1, _ = s1.measure(mkt, uni, bars)                    # 1단계 축(겹침 확인용)
        rec = df[df.start == df.start.max()].set_index("sym")
        r1 = d1[d1.start == d1.start.max()].set_index("sym")
        both = r1[[c for c, _ in STAGE1]].join(rec[[c for c, _ in METRICS]], how="inner")
        s1.METRICS = METRICS
        res[mkt] = {"df": df, "stones": S, "events": E, "judge": J, "overlap": both.rank().corr(), "base_hit": base_hit,
                    "base": base, "examples": s1.examples(df, mkt, uni)}
        cov[mkt] = earn_coverage({s: v for s, v in earn.items() if s in uni})
        counts[mkt] = (len(uni), df.sym.nunique() if len(df) else 0, sum(1 for s in uni if earn.get(s)))
        print(f"[{mkt}] 종목 {counts[mkt]} · 돌 {len(S)} · 실적일 {len(E)} · 마지막 날 {end.date()}")
        if not test:
            df.to_csv(os.path.join(STORE, f"stage2_metrics_{mkt}.csv.gz"), index=False)
            S.to_csv(os.path.join(STORE, f"stage2_stones_{mkt}.csv.gz"), index=False)
    write_doc(res, cov, counts, test)


if __name__ == "__main__":
    main()
