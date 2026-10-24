"""업종별 기업경기조사(BSI) 검증 — 업황 · 매출 · 신규수주 · 채산성의 실적 · 전망이 그 업종 주가에 반영되나, 얼마나 빨리 (2026-10-25 사용자 "검증해").

    python experiments/kr-stocks/validate_bsi.py     # → doc/검증/한국-BSI-검증.md

validate_indicators.py 와 같은 방법(플라시보 · 앞뒤 절반 · 교차상관 띠) + 다중 검정 보정. 판정 기준은 결과를 보기 전에 정했다 (RULES).
- 신호 = BSI 값(100 기준 확산지수 — 수준을 그대로). 조사한 달 말에 발표되므로 발표 지연 0개월: M월 BSI 는 M월 말부터 쓴다.
- 결과 = 그 업종에 해당하는 우리 종목 묶음(동일가중)의 KOSPI 대비 초과수익, 이후 1 · 3 · 6 · 12개월.
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
import collect_kr as C  # noqa: E402
import universe_kr as U  # noqa: E402
import validate_indicators as V  # noqa: E402

ROOT = os.path.join(BASE, "..", "..")
OUT_MD = os.path.join(ROOT, "doc", "검증", "한국-BSI-검증.md")
OUT_JSON = os.path.join(BASE, "data", "validate_bsi.json")
SEED = 20261025
Q_FDR = 0.10
TESTED_H = (3, 6)   # 판정에 쓰는 기간 — 이 둘만 플라시보 p 를 내고 보정한다

# BSI 업종 → 우리 종목 묶음 (결과를 보기 전에 정함)
INDUSTRIES = {
    "C2600": ("전자 · 영상 · 통신장비", ["005930.KS", "000660.KS", "402340.KS", "042700.KS", "066570.KS"]),
    "C2800": ("전기장비", ["373220.KS", "006400.KS", "003670.KS", "247540.KQ", "086520.KQ"]),
    "C2000": ("화학물질 · 제품", ["051910.KS", "373220.KS", "006400.KS", "003670.KS"]),
    "C3000": ("자동차", ["005380.KS", "000270.KS"]),
    "C3100": ("조선 · 기타운수", ["329180.KS", "042660.KS", "009540.KS", "012450.KS", "064350.KS"]),
    "C2100": ("의료물질 · 의약품", ["207940.KS", "068270.KS", "196170.KQ"]),
    "C2400": ("1차 금속", ["005490.KS", "010130.KS"]),
    "F4100": ("건설업", ["028260.KS"]),
    "D3500": ("전기 · 가스 · 증기", ["015760.KS"]),
    "J5800": ("정보통신업", ["035420.KS", "035720.KS", "017670.KS"]),
}
ITEMS = {   # (실적 표 512Y007 항목, 전망 표 512Y008 항목, 이름)
    "biz": ("AA", "BA", "업황"),
    "sales": ("AB", "BB", "매출"),
    "orders": ("AD", "BD", "신규수주"),
    "margin": ("AE", "BE", "채산성"),
}
RULES = ("통과 = 3개월 또는 6개월에서 셋 다 + 보정: ① 상위 25% 달 − 하위 25% 달 이후 초과수익 차이가 + (BSI 높을수록 좋음) "
         "② 플라시보 p 를 Benjamini–Hochberg 로 보정한 q < 0.10 (판정 기간 3 · 6개월 × 80개 조합 = 160개 검정 전체에서) ③ 앞뒤 절반에서 같은 방향")


def fetch(stat, item, ind):
    rows = C._ecos(C._ecos_key(), stat, "M", "200001", datetime.date.today().strftime("%Y%m"), f"{item}/{ind}", n=1000)
    return pd.Series({pd.Period(x["TIME"][:4] + "-" + x["TIME"][4:6], "M"): float(x["DATA_VALUE"]) for x in rows if x.get("DATA_VALUE") not in (None, "")}).sort_index()


def bh(pvals):
    """Benjamini–Hochberg q 값."""
    n = len(pvals)
    order = sorted(range(n), key=lambda i: pvals[i])
    q = [0.0] * n
    prev = 1.0
    for rank, i in reversed(list(enumerate(order, 1))):
        prev = min(prev, pvals[i] * n / rank)
        q[i] = prev
    return q


def evaluate(sig, ex, rng):
    common = sig.index.intersection(ex.index)
    half = common[len(common) // 2] if len(common) else None
    out = {"horizons": {}}
    for h in (1, 3, 6, 12):
        f = V.fwd(ex, h)
        sp, n = V.spread(sig, f)
        if sp is None:
            out["horizons"][h] = {"n": n}
            continue
        a, _ = V.spread(sig[sig.index <= half], f)
        b, _ = V.spread(sig[sig.index > half], f)
        x = {"spread": float(sp), "n": n, "n_indep": n // h, "first_half": None if a is None else float(a), "second_half": None if b is None else float(b),
             "stable": bool(a is not None and b is not None and a > 0 and b > 0), "direction_ok": bool(sp > 0)}
        if h in TESTED_H:
            x["p"] = V.placebo_p(sig, f, sp, rng)
        out["horizons"][h] = x
    ll = V.lead_lag(sig, ex)
    valid = {k: v for k, v in ll.items() if v is not None}
    if valid:
        peak = max(valid, key=lambda k: abs(valid[k]))
        band = V.lead_lag_band(sig, ex, rng)
        out["lead_lag"] = {"peak_lag": peak, "peak_corr": valid[peak], "corr_0": valid.get(0), "band95": band,
                           "clear": bool(band is not None and abs(valid[peak]) > band and abs(peak) < 12 and valid[peak] > 0), "all": valid}
    return out


def main():
    rng = random.Random(SEED)
    print("[bsi] 주가 받기…")
    px = V.monthly_prices()
    results = []
    for ind, (ind_name, members) in INDUSTRIES.items():
        mem = [m for m in members if m in px.columns]
        ex = V.excess_returns(px, mem)
        for key, (a_item, f_item, item_name) in ITEMS.items():
            for kind, stat, item in (("실적", "512Y007", a_item), ("전망", "512Y008", f_item)):
                try:
                    sig = fetch(stat, item, ind)
                except Exception as e:   # noqa: BLE001
                    print(f"[bsi] {ind}/{item} 실패: {str(e)[:60]}")
                    continue
                r = evaluate(sig, ex, rng)
                r.update(industry=ind, industry_name=ind_name, item=key, item_name=item_name, kind=kind, members=[U.name(m) for m in mem],
                         start=str(sig.index.min()), last=str(sig.index.max()), last_value=float(sig.iloc[-1]))
                results.append(r)
                h3, h6 = r["horizons"].get(3, {}), r["horizons"].get(6, {})
                ll = r.get("lead_lag") or {}
                print(f"[bsi] {ind_name:12s} {item_name}{kind} 3m {h3.get('spread', float('nan')):+6.2f} p{h3.get('p', float('nan')):.3f} · "
                      f"6m {h6.get('spread', float('nan')):+6.2f} p{h6.get('p', float('nan')):.3f} · 시차 {ll.get('peak_lag')} r{ll.get('peak_corr', float('nan')):+.2f} {'뚜렷' if ll.get('clear') else ''}")
    # 다중 검정 보정 — 판정 기간 3 · 6개월의 p 전부
    refs = [(i, h) for i, r in enumerate(results) for h in TESTED_H if "p" in (r["horizons"].get(h) or {})]
    qs = bh([results[i]["horizons"][h]["p"] for i, h in refs])
    for (i, h), q in zip(refs, qs):
        x = results[i]["horizons"][h]
        x["q"] = q
        x["pass"] = bool(x["direction_ok"] and x["stable"] and q < Q_FDR)
    for r in results:
        r["pass_h"] = [h for h in TESTED_H if (r["horizons"].get(h) or {}).get("pass")]
        r["pass"] = bool(r["pass_h"])
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"built": datetime.date.today().isoformat(), "rules": RULES, "results": results}, f, ensure_ascii=False, default=str)
    write_md(results, f"{px.index.min()} ~ {px.index.max()}")
    print(f"[bsi] 통과 {sum(r['pass'] for r in results)}/{len(results)} · 뚜렷한 시차 {sum(1 for r in results if (r.get('lead_lag') or {}).get('clear'))} → {OUT_MD}")


def write_md(results, period):
    L = ["# 한국 업종별 기업경기조사(BSI) 검증", "",
         f"작성 {datetime.date.today().isoformat()} · 스크립트 `experiments/kr-stocks/validate_bsi.py` · 앞선 검증 [한국-업종지표-검증](한국-업종지표-검증.md)", "",
         "## 미리 정한 기준 (결과를 보기 전)", "",
         "- 신호: 업종별 BSI 값(100 기준, 한국은행 기업경기조사 512Y007 실적 · 512Y008 전망). 그달 말에 발표되므로 발표 지연 0개월.",
         "- 결과: 그 업종에 해당하는 우리 종목 묶음(동일가중)의 KOSPI 대비 초과수익, 이후 1 · 3 · 6 · 12개월.",
         f"- {RULES}.",
         "- 속도: BSI 값과 묶음의 지난 12개월 초과수익의 교차상관(시차 −12~+12). 음수 = 주가가 먼저. 우연 95% 띠를 넘고 ±12 끝이 아니며 + 방향일 때만 '뚜렷'.",
         f"- 기간: BSI 2009년 8월~ (업종별 표 시작), 주가 {period}.",
         "- 한계: 지금 종목 목록 묶음(생존 편향), 건설 · 전기가스는 한 종목, 묶음이 업종 정의와 완전히 같지 않다(예: 전기장비 = 배터리 셀 · 소재 회사).", "",
         "## 결과 요약", "",
         "| 업종 | 항목 | 3개월 차이 (q) | 6개월 차이 (q) | 판정 | 속도 |", "|---|---|---|---|---|---|"]
    for r in sorted(results, key=lambda r: (not r["pass"], not (r.get("lead_lag") or {}).get("clear"), r["industry"], r["item"], r["kind"])):
        def cell(h):
            x = r["horizons"].get(h) or {}
            if "spread" not in x:
                return f"표본 부족 (n {x.get('n', 0)})"
            return f"{x['spread']:+.1f}%p (p {x.get('p', float('nan')):.3f} · q {x.get('q', float('nan')):.2f}, n {x['n']})"
        ll = r.get("lead_lag") or {}
        speed = "—"
        if ll:
            k = ll["peak_lag"]
            where = (f"{-k}개월 주가가 먼저" if k < 0 else f"BSI 뒤 {k}개월" if k > 0 else "같은 달") + f" (r {ll['peak_corr']:+.2f})"
            speed = f"**{where}**" if ll.get("clear") else f"뚜렷하지 않음 (최대 {where}, 우연 {ll['band95']:.2f})" if ll.get("band95") is not None else where
        verdict = f"✅ 통과 ({', '.join(f'{h}개월' for h in r['pass_h'])})" if r["pass"] else "—"
        L.append(f"| {r['industry_name']} | {r['item_name']} {r['kind']} | {cell(3)} | {cell(6)} | {verdict} | {speed} |")
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
