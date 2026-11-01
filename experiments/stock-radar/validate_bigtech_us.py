"""빅테크 회사별 업계 지표 검증 (2026-11-01 사용자: 빅테크는 회사마다 맞는 업계 동향 — 메타는 광고 등).

    python experiments/stock-radar/validate_bigtech_us.py          # 자료 받기 + 검증 → doc/검증/미국-빅테크-지표-검증.md

validate_industry_us.py 와 같은 식 · 같은 통과 기준(RULES) — 계산 함수를 그대로 가져다 쓴다.
옛 빅테크 카드(핵심 자본재 주문 → 다섯 종목 묶음)는 사업이 안 맞아(광고 · 클라우드 · 소비자 기기) 회사별 짝으로 다시 본다.
짝 · 예상 방향은 결과를 보기 전에 정했다(아래 PAIRS). 묶음은 회사 하나 — 그 회사 사정이 섞이는 한계가 있다.
"""
import datetime
import json
import os
import random

import pandas as pd

import validate_industry_us as V

OUT_MD = os.path.join(V.ROOT, "doc", "검증", "미국-빅테크-지표-검증.md")
OUT_JSON = os.path.join(V.BASE, "data", "validate_bigtech_us.json")
RAW_JSON = os.path.join(V.BASE, "data", "fred_bigtech.json")
AD_OLD, AD_NEW, AD_JOIN = "WPU365", "WPU366101", "2022-12-01"   # 인터넷 광고 생산자물가 — 2022-12 분류 바뀜, 겹치는 달 비율로 이어 붙인다

# 지표: (FRED 번호, 이름, 빈도, 변화 방식, 예상 방향)
SERIES = {
    "net_rev":     ("QREV519TUSY", "인터넷 정보서비스(검색포털 · 소셜) 매출", "Q", "pct", +1),
    "ad_ppi":      (f"{AD_OLD}+{AD_NEW}", "인터넷 광고 생산자물가", "M", "pct", +1),
    "hosting_rev": ("REV518TMSA", "데이터 처리 · 호스팅(클라우드) 매출", "Q", "pct", +1),
    "sw_rev":      ("REV5112TAXABL144QSA", "소프트웨어 회사 매출", "Q", "pct", +1),
    "sw_invest":   ("B985RC1Q027SBEA", "기업 소프트웨어 투자", "Q", "pct", +1),
    "elec_sales":  ("RSEAS", "전자제품 · 가전 매장 판매", "M", "pct", +1),
}
# 회사 → 지표 (결과 보기 전 확정)
PAIRS = [("META", "net_rev"), ("META", "ad_ppi"),
         ("GOOGL", "net_rev"), ("GOOGL", "ad_ppi"), ("GOOGL", "hosting_rev"),
         ("MSFT", "sw_rev"), ("MSFT", "hosting_rev"),
         ("ORCL", "sw_invest"), ("ORCL", "hosting_rev"),
         ("AAPL", "elec_sales")]
NAME = {"META": "메타", "GOOGL": "구글", "MSFT": "마이크로소프트", "ORCL": "오라클", "AAPL": "애플"}


def load_raw():
    key, raw = V._key(), {}
    for k, (sid, *_r) in SERIES.items():
        if k == "ad_ppi":
            old, new = dict(V.fetch_fred(AD_OLD, key)), dict(V.fetch_fred(AD_NEW, key))
            r = new[AD_JOIN] / old[AD_JOIN]   # 겹치는 달에서 옛 지수를 새 지수 눈금으로
            raw[k] = sorted([(d, v * r) for d, v in old.items() if d < AD_JOIN] + list(new.items()))
        else:
            raw[k] = V.fetch_fred(sid, key)
    json.dump({"fetched": datetime.date.today().isoformat(), **raw}, open(RAW_JSON, "w", encoding="utf-8"))
    return raw


def evaluate(sym, key, raw, px, rng):
    """V.evaluate 와 같은 계산 — INDICATORS 에 잠시 넣어 그대로 부른다."""
    sid, name, freq, kind, exp = SERIES[key]
    V.INDICATORS[f"{sym}:{key}"] = (sid, name, freq, kind, exp, [sym])
    res = V.evaluate(f"{sym}:{key}", raw[key], px, rng)
    res["sym"] = sym
    return res


def bh(results):
    """여러 번 시험 보정(Benjamini-Hochberg, q 0.05) — 회사 · 지표 짝 × 3 · 6개월."""
    ps = sorted((x["p"], r["key"], h) for r in results for h, x in r["horizons"].items() if h in (3, 6) and "p" in x)
    m, cut = len(ps), 0.0
    for i, (p, *_k) in enumerate(ps, 1):
        if p <= 0.05 * i / m:
            cut = p
    return m, cut, ps[0] if ps else None


def write_md(results, m, cut, best):
    L = ["# 미국 빅테크 회사별 업계 지표 검증", "",
         f"작성 {datetime.date.today().isoformat()} · 스크립트 `experiments/stock-radar/validate_bigtech_us.py` · 자료 FRED · 주가 30년 저장소 data/store", "",
         "## 왜 다시 봤나", "",
         "옛 빅테크 카드는 핵심 자본재 주문(공장 설비 주문) 하나를 다섯 종목에 붙였다 — 검증 6개월 −1.5%p(p 0.67), 사업도 안 맞음(광고 · 클라우드 · 소비자 기기). "
         "2026-11-01 사용자: 회사마다 맞는 업계 동향(메타 = 광고 등).", "",
         "## 미리 정한 기준 (결과를 보기 전)", "",
         "- 짝: " + " · ".join(f"{NAME[s]} ← {SERIES[k][1]}" for s, k in PAIRS) + ".",
         "- 신호 · 발표 지연 · 결과(S&P 500 대비 초과수익, 이후 1 · 3 · 6 · 12개월) · 플라시보 · 앞뒤 절반 = 미국 업종 지표 검증(doc/검증/미국-업종지표-검증.md)과 같음.",
         f"- {V.RULES}.",
         "- 인터넷 광고 생산자물가는 2022-12 분류가 바뀌어 겹치는 달 비율로 이어 붙였다(WPU365 → WPU366101).",
         "- 한계: 묶음이 회사 하나라 그 회사 사정(신제품 · 소송 · 실적)이 섞인다. 인터넷 정보서비스 매출은 2012년부터라 표본이 작다.", "",
         "## 결과 요약", "",
         "| 회사 | 지표 (FRED) | 기간 | 3개월 차이 (p) | 6개월 차이 (p) | 판정 |", "|---|---|---|---|---|---|"]
    for r in results:
        def cell(h):
            x = r["horizons"].get(h) or {}
            return f"표본 부족 (n {x.get('n', 0)})" if "spread" not in x else f"{x['spread']:+.1f}%p (p {x['p']:.3f}, n {x['n']})"
        verdict = f"✅ 통과 ({', '.join(f'{h}개월' for h in r['pass_h'])})" if r["pass"] else "참고 숫자"
        L.append(f"| {NAME[r['sym']]} | {r['name']} (`{r['fred']}`) | {r['from'] or '—'}~{r['to'] or ''} | {cell(3)} | {cell(6)} | {verdict} |")
    survive = [f"{NAME[r['sym']]} ← {r['name']} {h}개월({'예상 방향' if x['direction_ok'] else '예상과 반대'})"
               for r in results for h, x in r["horizons"].items() if h in (3, 6) and "p" in x and cut and x["p"] <= cut]
    L += ["", f"여러 번 시험 보정(BH, q 0.05): 시험 {m}번 · 보정 뒤 기준 p ≤ {cut:.3f} · "
          + (f"남는 것: {' · '.join(survive)}." if survive else "남는 것 없음."), "",
          "## 지표별 상세", ""]
    for r in results:
        L += [f"### {NAME[r['sym']]} ← {r['name']} (`{r['fred']}`, {'분기' if r['freq'] == 'Q' else '월'})", "",
              "| 기간 | 상위25% − 하위25% | p | n (독립) | 앞 절반 | 뒤 절반 | 판정 |", "|---|---|---|---|---|---|---|"]
        for h in V.HORIZONS:
            x = r["horizons"].get(h) or {}
            if "spread" not in x:
                L.append(f"| {h}개월 | 표본 부족 | | {x.get('n', 0)} | | | |")
                continue
            fh = "—" if x["first_half"] is None else f"{x['first_half']:+.1f}"
            sh = "—" if x["second_half"] is None else f"{x['second_half']:+.1f}"
            L.append(f"| {h}개월 | {x['spread']:+.2f}%p | {x['p']:.3f} | {x['n']} ({x['n_indep']}) | {fh} | {sh} | "
                     f"{'통과' if x['pass'] else ('방향 맞음' if x['direction_ok'] else '방향 반대')} |")
        L.append("")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L) + "\n")


def main():
    raw = load_raw()
    for k, rows in raw.items():
        print(f"[bigtech-val] {k:12} {rows[0][0]}~{rows[-1][0]} ({len(rows)})")
    px = V.monthly_prices(sorted({s for s, _k in PAIRS} | {V.BENCH}))
    rng = random.Random(V.SEED)
    results = [evaluate(s, k, raw, px, rng) for s, k in PAIRS]
    json.dump(results, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    m, cut, best = bh(results)
    write_md(results, m, cut, best)
    print(f"[bigtech-val] 통과 {sum(r['pass'] for r in results)} / {len(results)} · BH {m}번 기준 {cut:.3f} → {OUT_MD}")


if __name__ == "__main__":
    main()
