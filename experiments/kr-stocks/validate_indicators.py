"""업종 재료 지표 검증 — 실물 숫자가 테마 주가에 반영되나, 된다면 얼마나 빨리 (기획 11-7-1, 2026-10-24 사용자 "검증해").

    python experiments/kr-stocks/validate_indicators.py     # ECOS 전 기간 + yfinance 월말 종가 → doc/검증/한국-업종지표-검증.md

판정 기준은 결과를 보기 전에 정했다 (아래 RULES). 계산은 전부 코드 — AI 는 쓰지 않는다.
- 신호 = 지표의 전년 동월 대비 변화(%, 금리 · 연체율은 %p). M월 지표는 M+1월 말에 안다고 보고(발표 지연 1개월) 그때부터 수익을 센다.
- 결과 = 테마 묶음(그 지표를 쓰는 종목 동일가중)의 KOSPI 대비 초과수익, 이후 1 · 3 · 6 · 12개월.
- 플라시보 = 신호 시계열을 무작위 칸만큼 통째로 밀기(circular shift) 1,000번 — 자기상관을 유지해 겹치는 창의 과대평가를 막는다.
- 속도 = 지표 전년비와 묶음의 지난 12개월 초과수익의 교차상관(시차 −12 ~ +12). 음수 시차에서 가장 크면 주가가 먼저 움직였다.
"""
import datetime
import json
import os
import random
import sys

import numpy as np
import pandas as pd
import yfinance as yf

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import collect_kr as C  # noqa: E402
import universe_kr as U  # noqa: E402

ROOT = os.path.join(BASE, "..", "..")
OUT_MD = os.path.join(ROOT, "doc", "검증", "한국-업종지표-검증.md")
OUT_JSON = os.path.join(BASE, "data", "validate_indicators.json")
HORIZONS = (1, 3, 6, 12)
LAG = 1                 # 발표 지연 (개월)
N_PLACEBO = 1000
MIN_MONTHS = 60
SEED = 20261024

# 예상 방향: +1 = 지표가 오르면 그 업종에 좋다 · −1 = 나쁘다 (결과를 보기 전에 정함)
EXPECT = {"dram_px": +1, "flash_px": +1, "sys_semi_px": +1, "semi_equip_px": +1, "storage_px": +1, "pharma_px": +1, "pharma_raw_px": +1,
          "ship_engine_px": +1, "rv_px": +1, "car_engine_px": +1, "steel_px": +1, "steel_prod": +1, "power_use": +1, "oil_use": +1,
          "energy_supply": +1, "constr_orders": +1, "housing_permits": +1, "unsold_homes": -1, "house_px": +1, "card_spend": +1,
          "loan_rate": +1, "dep_rate": -1, "hh_loans_bank": +1, "delinq_hh": -1, "delinq_corp": -1, "nim_spread": +1}

RULES = ("통과 = 3개월 또는 6개월 가운데 하나에서 셋 다: ① 신호 상위 25% 달 − 하위 25% 달의 이후 초과수익 차이가 예상 방향 "
         "② 그 차이가 플라시보(신호를 통째로 무작위 칸 밀기 1,000번) 대비 p < 0.05 ③ 표본을 앞뒤 절반으로 나눠도 같은 방향")


# ── 데이터 ──────────────────────────────────────────────────────────────

def fetch_indicator(key, stat, item):
    rows = C._ecos(C._ecos_key(), stat, "M", "199501", datetime.date.today().strftime("%Y%m"), item, n=5000)
    codes2 = {x.get("ITEM_CODE2") for x in rows}
    if len(codes2) > 1:   # collect_kr 와 같은 규칙: 수출물가는 원화 기준 줄, 그 밖은 합계(가장 큰) 줄
        names = {x.get("ITEM_CODE2"): x.get("ITEM_NAME2", "") for x in rows}
        if stat == "402Y016":
            pick = next((c for c, n in names.items() if "원화" in (n or "")), next(iter(names)))
        else:
            tot = {}
            for x in rows:
                if x.get("DATA_VALUE") not in (None, ""):
                    tot[x.get("ITEM_CODE2")] = tot.get(x.get("ITEM_CODE2"), 0.0) + float(x["DATA_VALUE"])
            pick = max(tot, key=tot.get)
        rows = [x for x in rows if x.get("ITEM_CODE2") == pick]
    s = pd.Series({pd.Period(x["TIME"][:4] + "-" + x["TIME"][4:6], "M"): float(x["DATA_VALUE"]) for x in rows if x.get("DATA_VALUE") not in (None, "")}).sort_index()
    return s


def indicators():
    out = {}
    for key, (stat, item, *_r) in U.INDICATORS.items():
        try:
            out[key] = fetch_indicator(key, stat, item)
        except Exception as e:   # noqa: BLE001
            print(f"[val] {key} 실패: {str(e)[:80]}")
    for key, (a, b, *_r) in U.DERIVED.items():
        if a in out and b in out:
            out[key] = (out[a] - out[b]).dropna()
    return out


def monthly_prices():
    syms = [c[0] for c in U.CANDIDATES] + [U.BENCH]
    df = yf.download(syms, start="2000-01-01", interval="1mo", auto_adjust=True, group_by="ticker", progress=False, threads=3)
    px = {}
    for s in syms:
        try:
            c = df[s]["Close"].dropna()
        except KeyError:
            continue
        c.index = c.index.to_period("M")
        px[s] = c[~c.index.duplicated(keep="last")]
    return pd.DataFrame(px)


def baskets():
    """지표 → 그 지표를 쓰는 종목들 (universe_kr.indicators_for 를 뒤집는다)."""
    b = {}
    for s, *_r in U.CANDIDATES:
        for k in U.indicators_for(s):
            b.setdefault(k, []).append(s)
    return b


# ── 계산 ────────────────────────────────────────────────────────────────

def signal(series, key):
    kind = (U.DERIVED.get(key) or U.INDICATORS.get(key))[3]
    return (series - series.shift(12)) if kind == "pct" else (series / series.shift(12) - 1) * 100


def excess_returns(px, members):
    r = px.pct_change(fill_method=None)
    basket = r[members].mean(axis=1, skipna=True)                   # 동일가중 — 그달 이력이 있는 종목만
    return ((basket - r[U.BENCH]) * 100).dropna()   # %p


def fwd(ex, h):
    """t 월 말 이후 h개월 누적 초과수익 (단순 합 근사)."""
    return ex[::-1].rolling(h).sum()[::-1].shift(-1)


def spread(sig, f):
    d = pd.concat([sig, f], axis=1, keys=["s", "f"]).dropna()
    if len(d) < MIN_MONTHS:
        return None, len(d)
    q1, q3 = d["s"].quantile(0.25), d["s"].quantile(0.75)
    return d.loc[d["s"] >= q3, "f"].mean() - d.loc[d["s"] <= q1, "f"].mean(), len(d)


def placebo_p(sig, f, actual, rng):
    vals = sig.dropna()
    n = len(vals)
    hits = 0
    for _ in range(N_PLACEBO):
        k = rng.randint(12, n - 12) if n > 30 else rng.randint(1, n - 1)
        shifted = pd.Series(np.roll(vals.values, k), index=vals.index)
        sp, _ = spread(shifted, f)
        if sp is not None and abs(sp) >= abs(actual):
            hits += 1
    return (hits + 1) / (N_PLACEBO + 1)


def lead_lag(sig, ex):
    ret12 = ex.rolling(12).sum()
    out = {}
    for k in range(-12, 13):
        d = pd.concat([sig, ret12.shift(-k)], axis=1).dropna()
        out[k] = float(d.corr().iloc[0, 1]) if len(d) >= MIN_MONTHS else None
    return out


def lead_lag_band(sig, ex, rng, n=200):
    """플라시보 — 신호를 통째로 밀었을 때 '시차 −12~+12 중 가장 큰 |상관|' 의 95% 지점. 실제 최대가 이보다 작으면 뚜렷한 시차가 없다."""
    vals = sig.dropna()
    if len(vals) < 40:
        return None
    mx = []
    for _ in range(n):
        k = rng.randint(12, len(vals) - 12)
        sh = pd.Series(np.roll(vals.values, k), index=vals.index)
        ll = [v for v in lead_lag(sh, ex).values() if v is not None]
        if ll:
            mx.append(max(abs(v) for v in ll))
    return float(np.percentile(mx, 95)) if mx else None


def evaluate(key, ind, px, members, rng):
    sig = signal(ind, key).shift(LAG).dropna()
    ex = excess_returns(px, members)
    exp = EXPECT.get(key, +1)
    res = {"key": key, "members": [U.name(m) for m in members], "expect": exp, "from": str(sig.index.min()) if len(sig) else None, "horizons": {}}
    common = sig.index.intersection(ex.index)   # 앞뒤 절반 = 신호 · 주가가 둘 다 있는 달의 가운데에서 나눈다
    half = common[len(common) // 2] if len(common) else None
    passed = []
    for h in HORIZONS:
        f = fwd(ex, h)
        sp, n = spread(sig, f)
        if sp is None:
            res["horizons"][h] = {"n": n}
            continue
        p = placebo_p(sig, f, sp, rng)
        a, _ = spread(sig[sig.index <= half], f)
        b, _ = spread(sig[sig.index > half], f)
        stable = a is not None and b is not None and np.sign(a) == np.sign(b) == np.sign(exp)
        ok = np.sign(sp) == np.sign(exp) and p < 0.05 and stable
        res["horizons"][h] = {"spread": float(sp), "n": n, "n_indep": n // h, "p": p, "first_half": None if a is None else float(a), "second_half": None if b is None else float(b),
                              "direction_ok": bool(np.sign(sp) == np.sign(exp)), "stable": bool(stable), "pass": bool(ok)}
        if ok and h in (3, 6):
            passed.append(h)
    raw = signal(ind, key).dropna()
    ll = lead_lag(raw, ex)
    valid = {k: v for k, v in ll.items() if v is not None}
    if valid:
        peak = max(valid, key=lambda k: abs(valid[k]))
        band = lead_lag_band(raw, ex, rng)
        clear = band is not None and abs(valid[peak]) > band and abs(peak) < 12 and np.sign(valid[peak]) == np.sign(exp)
        res["lead_lag"] = {"peak_lag": peak, "peak_corr": valid[peak], "corr_0": valid.get(0), "band95": band, "clear": bool(clear), "all": valid}
    res["pass"] = bool(passed)
    res["pass_h"] = passed
    return res


# ── 문서 ────────────────────────────────────────────────────────────────

def _name(key):
    return (U.DERIVED.get(key) or U.INDICATORS.get(key))[2]


def write_md(results, period):
    L = ["# 한국 업종 재료 지표 검증", "",
         f"작성 {datetime.date.today().isoformat()} · 스크립트 `experiments/kr-stocks/validate_indicators.py` · 기획 [종목-레이더-기획 11-7-1](../기획/종목-레이더-기획.md)", "",
         "## 미리 정한 기준 (결과를 보기 전)", "",
         f"- 신호: 지표의 전년 동월 대비 변화(금리 · 연체율은 %p). 발표 지연 {LAG}개월 — M월 지표는 M+{LAG}월 말부터 쓴다.",
         "- 결과: 테마 묶음(그 지표를 쓰는 종목 동일가중, 그달 이력이 있는 종목만)의 KOSPI 대비 초과수익, 이후 1 · 3 · 6 · 12개월.",
         f"- {RULES}.",
         "- 속도: 지표 전년비와 묶음의 지난 12개월 초과수익의 교차상관(시차 −12 ~ +12개월). 시차 k = 주가를 k개월 뒤로 민 것 — **음수면 주가가 지표보다 먼저**, 양수면 지표 뒤에 주가.",
         f"- 기간: 주가 {period} (yfinance 월말 · 배당 반영), 지표는 ECOS 에서 받을 수 있는 전 기간. 표본 n = 지표 · 주가가 둘 다 있는 달 수, `독립` = n ÷ 기간(겹치지 않는 창 수).",
         "- 한계: 묶음은 지금 종목 목록이라 생존 편향이 있다(사라진 종목 없음). 월말 종가 · 단순 합 근사. 같은 지표를 여러 묶음이 쓰면 묶음이 겹친다.", "",
         "## 결과 요약", "",
         "| 지표 | 묶음 | 시작 | 3개월 차이 (p) | 6개월 차이 (p) | 판정 | 속도 (상관 최대 시차) |", "|---|---|---|---|---|---|---|"]
    for r in results:
        def cell(h):
            x = r["horizons"].get(h) or {}
            if "spread" not in x:
                return f"표본 부족 (n {x.get('n', 0)})"
            return f"{x['spread']:+.1f}%p (p {x['p']:.3f}, n {x['n']} · 독립 {x['n_indep']})"
        ll = r.get("lead_lag") or {}
        speed = "—"
        if ll:
            k = ll["peak_lag"]
            where = (f"{-k}개월 주가가 먼저" if k < 0 else f"지표 뒤 {k}개월" if k > 0 else "같은 달") + f" (상관 {ll['peak_corr']:+.2f})"
            speed = f"**{where}**" if ll.get("clear") else f"뚜렷하지 않음 — 최대 {where}, 우연 95% {ll['band95']:.2f}" if ll.get("band95") is not None else where
        verdict = f"✅ 통과 ({', '.join(f'{h}개월' for h in r['pass_h'])})" if r["pass"] else "참고 숫자"
        L.append(f"| {_name(r['key'])} | {', '.join(r['members'][:3])}{' 외' if len(r['members']) > 3 else ''} | {r['from'] or '—'} | {cell(3)} | {cell(6)} | {verdict} | {speed} |")
    L += ["", "## 지표별 상세", ""]
    for r in results:
        L += [f"### {_name(r['key'])} (`{r['key']}`)", "", f"- 묶음: {', '.join(r['members'])} · 예상 방향 {'오르면 좋음' if r['expect'] > 0 else '오르면 나쁨'}", ""]
        L += ["| 기간 | 상위25% − 하위25% | p | n (독립) | 앞 절반 | 뒤 절반 | 판정 |", "|---|---|---|---|---|---|---|"]
        for h in HORIZONS:
            x = r["horizons"].get(h) or {}
            if "spread" not in x:
                L.append(f"| {h}개월 | 표본 부족 | | {x.get('n', 0)} | | | |")
                continue
            fh = "—" if x["first_half"] is None else f"{x['first_half']:+.1f}"
            sh = "—" if x["second_half"] is None else f"{x['second_half']:+.1f}"
            L.append(f"| {h}개월 | {x['spread']:+.2f}%p | {x['p']:.3f} | {x['n']} ({x['n_indep']}) | {fh} | {sh} | {'통과' if x['pass'] else ('방향 맞음' if x['direction_ok'] else '방향 반대')} |")
        ll = r.get("lead_lag")
        if ll:
            row = " · ".join(f"{k:+d}: {v:+.2f}" for k, v in sorted(ll["all"].items()) if k % 3 == 0)
            L += ["", f"- 교차상관(3개월 간격): {row}",
                  f"- 가장 큰 시차 {ll['peak_lag']:+d}개월 (상관 {ll['peak_corr']:+.2f}) · 같은 달 {ll['corr_0']:+.2f} · 우연으로도 나오는 최대 |상관| 95% 지점 {ll['band95']:.2f} → "
                  + ("**뚜렷한 시차**" if ll.get("clear") else "뚜렷하지 않음") if ll.get("corr_0") is not None and ll.get("band95") is not None else ""]
        L.append("")
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def main():
    rng = random.Random(SEED)
    print("[val] ECOS 지표 전 기간 받기…")
    ind = indicators()
    print(f"[val] 지표 {len(ind)}개 · 주가 받기…")
    px = monthly_prices()
    period = f"{px.index.min()} ~ {px.index.max()}"
    bk = baskets()
    results = []
    for key in list(U.INDICATORS) + list(U.DERIVED):
        if key not in ind or key not in bk:
            continue
        members = [m for m in bk[key] if m in px.columns]
        if not members:
            continue
        r = evaluate(key, ind[key], px, members, rng)
        results.append(r)
        h3, h6 = r["horizons"].get(3, {}), r["horizons"].get(6, {})
        print(f"[val] {key:15s} 3m {h3.get('spread', float('nan')):+6.2f} p{h3.get('p', float('nan')):.3f} · 6m {h6.get('spread', float('nan')):+6.2f} p{h6.get('p', float('nan')):.3f} · "
              f"{'통과' if r['pass'] else '—'} · 시차 {(r.get('lead_lag') or {}).get('peak_lag')}")
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"built": datetime.date.today().isoformat(), "period": period, "rules": RULES, "results": results}, f, ensure_ascii=False, default=str)
    write_md(results, period)
    print(f"[val] → {OUT_MD}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
