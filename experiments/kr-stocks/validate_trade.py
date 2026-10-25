"""K12 · K13 · K14 월별 검증 — 수출입물가 · 교역조건 · 무역지수(물량 · 금액) · 월평균 환율 → 수출형 · 수입원료형 묶음 (2026-10-25 "검증해").
validate_indicators 의 틀(사분위 · 통째 밀기 플라시보 1,000 · 앞뒤 절반 · 교차상관 띠) 그대로, 지표 목록만 다르다.
    python experiments/kr-stocks/validate_trade.py   # → doc/검증/한국-무역지표-검증.md
"""
import datetime
import json
import os
import random
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import universe_kr as U  # noqa: E402
import validate_indicators as V  # noqa: E402

ROOT = os.path.join(BASE, "..", "..")
OUT_MD = os.path.join(ROOT, "doc", "검증", "한국-무역지표-검증.md")
OUT_JSON = os.path.join(BASE, "data", "validate_trade.json")
SEED = 20261025

EXPORT = ["005930.KS", "000660.KS", "005380.KS", "000270.KS", "373220.KS", "006400.KS", "329180.KS", "042660.KS", "009540.KS", "012450.KS", "207940.KS", "068270.KS", "005490.KS", "010130.KS", "051910.KS"]
DOMESTIC = ["105560.KS", "055550.KS", "086790.KS", "032830.KS", "000810.KS", "035420.KS", "035720.KS", "017670.KS", "015760.KS", "028260.KS"]
SEMI = ["005930.KS", "000660.KS", "402340.KS", "042700.KS"]
BATT = ["373220.KS", "006400.KS", "003670.KS", "247540.KQ", "086520.KQ"]
AUTO = ["005380.KS", "000270.KS"]
STEEL = ["005490.KS", "010130.KS"]
BIO = ["207940.KS", "068270.KS", "196170.KQ"]
KEPCO = ["015760.KS"]
CHEM = ["051910.KS"]

# (키, 표, 항목, 이름, 신호 종류 yoy|yoy_diff, 예상 방향, 묶음, 설명)
TESTS = [
    ("tot", "403Y005", "A", "순상품 교역조건지수", "yoy", +1, EXPORT, "K12 수출 단가 ÷ 수입 단가"),
    ("tot_inc", "403Y005", "B", "소득 교역조건지수", "yoy", +1, EXPORT, "K12"),
    ("expx_krw", "402Y014", "*AA", "수출물가 총지수 (원화)", "yoy", +1, EXPORT, "K12 단가 + 환율"),
    ("impx_oil", "401Y015", "201121AA", "수입물가 원유", "yoy", -1, KEPCO + CHEM, "K12 원가"),
    ("impx_lng", "401Y015", "201122AA", "수입물가 천연가스(LNG)", "yoy", -1, KEPCO, "K12 한전 원가"),
    ("impx_coal", "401Y015", "20111AA", "수입물가 석탄", "yoy", -1, KEPCO, "K12"),
    ("impx_iron", "401Y015", "201211AA", "수입물가 철광석", "yoy", -1, STEEL, "K12 철강 원가"),
    ("vol_semi", "403Y002", "30911AA", "수출물량 반도체", "yoy", +1, SEMI, "K13"),
    ("amt_semi", "403Y001", "30911AA", "수출금액 반도체", "yoy", +1, SEMI, "K13"),
    ("vol_batt", "403Y002", "31013AA", "수출물량 전지", "yoy", +1, BATT, "K13 2차전지 첫 실물 지표"),
    ("amt_batt", "403Y001", "31013AA", "수출금액 전지", "yoy", +1, BATT, "K13"),
    ("vol_car", "403Y002", "312111AA", "수출물량 승용차", "yoy", +1, AUTO, "K13"),
    ("amt_car", "403Y001", "312111AA", "수출금액 승용차", "yoy", +1, AUTO, "K13"),
    ("vol_steel", "403Y002", "3071AA", "수출물량 철강1차제품", "yoy", +1, STEEL, "K13"),
    ("vol_pharma", "403Y002", "30541AA", "수출물량 의약품", "yoy", +1, BIO, "K13 2016~"),
    ("amt_pharma", "403Y001", "30541AA", "수출금액 의약품", "yoy", +1, BIO, "K13 2016~"),
    ("usdkrw_m", "731Y004", "0000001", "원/달러 월평균 (+ = 원화 약세)", "yoy", +1, EXPORT, "K14 수출형"),
    ("usdkrw_m_dom", "731Y004", "0000001", "원/달러 월평균 → 내수형", "yoy", -1, DOMESTIC, "K14 내수형"),
    ("jpykrw_m", "731Y004", "0000002", "원/100엔 월평균 (+ = 엔 대비 원화 약세)", "yoy", +1, AUTO + ["329180.KS", "042660.KS", "009540.KS"] + STEEL, "K14 일본 경쟁 업종"),
]


def fetch(stat, item):
    rows = V.C._ecos(V.C._ecos_key(), stat, "M", "199001", datetime.date.today().strftime("%Y%m"), item, n=5000)
    codes2 = {x.get("ITEM_CODE2") for x in rows}
    if len(codes2) > 1:
        names = {x.get("ITEM_CODE2"): x.get("ITEM_NAME2", "") for x in rows}
        pick = next((c for c, n in names.items() if "원화" in (n or "")), next(iter(names)))
        rows = [x for x in rows if x.get("ITEM_CODE2") == pick]
    return pd.Series({pd.Period(x["TIME"][:4] + "-" + x["TIME"][4:6], "M"): float(x["DATA_VALUE"]) for x in rows if x.get("DATA_VALUE") not in (None, "")}).sort_index()


def evaluate(sig_raw, ex, exp, rng):
    sig = sig_raw.shift(V.LAG).dropna()
    common = sig.index.intersection(ex.index)
    half = common[len(common) // 2] if len(common) else None
    res = {"from": str(sig.index.min()) if len(sig) else None, "horizons": {}, "pass_h": []}
    for h in V.HORIZONS:
        f = V.fwd(ex, h)
        sp, n = V.spread(sig, f)
        if sp is None:
            res["horizons"][h] = {"n": n}
            continue
        p = V.placebo_p(sig, f, sp, rng)
        a, _ = V.spread(sig[sig.index <= half], f)
        b, _ = V.spread(sig[sig.index > half], f)
        stable = a is not None and b is not None and np.sign(a) == np.sign(b) == np.sign(exp)
        ok = bool(np.sign(sp) == np.sign(exp) and p < 0.05 and stable)
        res["horizons"][h] = {"spread": float(sp), "n": n, "n_indep": n // h, "p": p, "first_half": a, "second_half": b, "stable": bool(stable), "pass": ok}
        if ok and h in (3, 6):
            res["pass_h"].append(h)
    ll = V.lead_lag(sig_raw.dropna(), ex)
    valid = {k: v for k, v in ll.items() if v is not None}
    if valid:
        peak = max(valid, key=lambda k: abs(valid[k]))
        band = V.lead_lag_band(sig_raw.dropna(), ex, rng)
        res["lead_lag"] = {"peak_lag": peak, "peak_corr": valid[peak], "corr_0": valid.get(0), "band95": band,
                           "clear": bool(band is not None and abs(valid[peak]) > band and abs(peak) < 12 and np.sign(valid[peak]) == np.sign(exp))}
    res["pass"] = bool(res["pass_h"])
    return res


def main():
    rng = random.Random(SEED)
    px = V.monthly_prices()
    results = []
    for key, stat, item, name, kind, exp, members, note in TESTS:
        try:
            s = fetch(stat, item)
        except Exception as e:   # noqa: BLE001
            print(f"[trade] {key} 실패: {str(e)[:60]}")
            continue
        sig = (s / s.shift(12) - 1) * 100 if kind == "yoy" else s - s.shift(12)
        mem = [m for m in members if m in px.columns]
        r = evaluate(sig, V.excess_returns(px, mem), exp, rng)
        r.update(key=key, name=name, expect=exp, members=[U.name(m) for m in mem], note=note, last=str(s.index.max()), last_yoy=float(sig.dropna().iloc[-1]) if len(sig.dropna()) else None)
        results.append(r)
        h3, h6 = r["horizons"].get(3, {}), r["horizons"].get(6, {})
        ll = r.get("lead_lag") or {}
        print(f"[trade] {name:28s} 3m {h3.get('spread', float('nan')):+6.1f} p{h3.get('p', float('nan')):.3f} · 6m {h6.get('spread', float('nan')):+6.1f} p{h6.get('p', float('nan')):.3f} · {'통과' if r['pass'] else '—'} · 시차 {ll.get('peak_lag')} r{ll.get('peak_corr', float('nan')):+.2f}{' 뚜렷' if ll.get('clear') else ''}")
    # BH
    refs = [(i, h) for i, r in enumerate(results) for h in (3, 6) if "p" in (r["horizons"].get(h) or {})]
    for (i, h), q in zip(refs, V.__dict__.get("bh", lambda ps: ps)([results[i]["horizons"][h]["p"] for i, h in refs])):
        results[i]["horizons"][h]["q"] = q
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"built": datetime.date.today().isoformat(), "results": results}, f, ensure_ascii=False, default=str)
    L = ["# 한국 무역 · 환율 월별 지표 검증 (K12 · K13 · K14)", "", f"작성 {datetime.date.today().isoformat()} · 스크립트 `experiments/kr-stocks/validate_trade.py` · 틀은 [한국-업종지표-검증](한국-업종지표-검증.md)과 같다(발표 지연 1개월 · 사분위 · 통째 밀기 플라시보 1,000 · 앞뒤 절반 · 교차상관 띠)", "",
         "| 지표 | 묶음 | 예상 | 시작 | 3개월 차이 (p) | 6개월 차이 (p) | 판정 | 속도 |", "|---|---|---|---|---|---|---|---|"]
    for r in sorted(results, key=lambda r: (not r["pass"], not (r.get("lead_lag") or {}).get("clear"))):
        def cell(h):
            x = r["horizons"].get(h) or {}
            return f"표본 부족 (n {x.get('n', 0)})" if "spread" not in x else f"{x['spread']:+.1f}%p (p {x['p']:.3f}, n {x['n']})"
        ll = r.get("lead_lag") or {}
        speed = "—"
        if ll:
            k = ll["peak_lag"]
            w = (f"{-k}개월 주가가 먼저" if k < 0 else f"지표 뒤 {k}개월" if k > 0 else "같은 달") + f" (r {ll['peak_corr']:+.2f})"
            speed = f"**{w}**" if ll.get("clear") else f"뚜렷하지 않음 — 최대 {w}, 우연 {ll['band95']:.2f}" if ll.get("band95") is not None else w
        L.append(f"| {r['name']} | {', '.join(r['members'][:3])}{' 외' if len(r['members']) > 3 else ''} | {'+' if r['expect'] > 0 else '−'} | {r['from']} | {cell(3)} | {cell(6)} | {'✅ 통과' if r['pass'] else '참고 숫자'} | {speed} |")
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    tail = ""   # 손으로 쓴 '## 결론' 아래는 다시 만들 때 보존
    if os.path.exists(OUT_MD):
        old = open(OUT_MD, encoding="utf-8").read()
        if "\n## 결론" in old:
            tail = old[old.index("\n## 결론"):]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n" + tail)
    print(f"[trade] 통과 {sum(r['pass'] for r in results)}/{len(results)} → {OUT_MD}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
