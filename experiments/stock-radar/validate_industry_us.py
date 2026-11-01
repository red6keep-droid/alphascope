"""미국 업계 지표 검증 — 공식 통계(FRED)가 그 업종 종목의 시장 대비 수익에 반영되나 (2026-11-01 사용자: 미국 종목에도 업계 카드).

    python experiments/stock-radar/validate_industry_us.py          # 자료 받기 + 검증 → doc/검증/미국-업종지표-검증.md
    python experiments/stock-radar/validate_industry_us.py --fetch  # 자료만 받아 기간 확인 (검증 계산 없음)

한국 업종 지표 검증(kr-stocks/validate_indicators.py)과 같은 방법 · 같은 통과 기준 — 결과를 보기 전에 아래 RULES · EXPECT · 묶음을 정했다. 계산은 전부 코드, AI 없음.
- 신호 = 지표의 전년 같은 달(분기) 대비 변화(%, 비율 지표는 %p). 발표 지연 = 월 자료 1개월 · 분기 자료 3개월(분기 끝 달 기준).
- 결과 = 업종 묶음(이 블로그 미국 종목 중 그 업종, 동일가중 · 그달 이력이 있는 종목만)의 S&P 500(SPY) 대비 초과수익, 이후 1 · 3 · 6 · 12개월.
- 주가 = 30년 저장소 data/store/bars (수정주가, 분석 1999~) — 지표 검증 기준(validation-30y-basis).
- 플라시보 = 신호를 통째로 무작위 칸 밀기 1,000번. 앞뒤 절반 = 신호 · 주가가 둘 다 있는 달의 가운데에서 나눈다.
"""
import datetime
import json
import os
import random
import sys
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", ".."))
STORE = os.path.join(ROOT, "data", "store", "bars")
OUT_MD = os.path.join(ROOT, "doc", "검증", "미국-업종지표-검증.md")
OUT_JSON = os.path.join(BASE, "data", "validate_industry_us.json")
RAW_JSON = os.path.join(BASE, "data", "fred_industry.json")
HORIZONS = (1, 3, 6, 12)
N_PLACEBO = 1000
MIN_N = 60          # 월 자료 최소 달 수
MIN_NQ = 40         # 분기 자료 최소 분기 수
SEED = 20261101
BENCH = "SPY"
START = "1999-01"

# 업종 묶음 — 이 블로그 미국 종목(universe.CANDIDATES)의 업종 그대로, 지표가 재는 사업에 맞는 종목만 (결과를 보기 전에 정함)
SEMI = ["NVDA", "AVGO", "MU", "AMD", "INTC", "TSM", "ASML", "LRCX", "AMAT"]
BIGTECH = ["AAPL", "GOOGL", "MSFT", "META", "ORCL"]
STAPLES = ["WMT", "KO", "PG", "PM", "COST"]
RETAIL_BIG = ["WMT", "COST"]
ENERGY = ["XOM", "CVX", "COP", "SLB", "EOG"]
UTIL = ["CEG", "NEE", "SO", "VST"]
PHARMA = ["LLY", "JNJ", "ABBV"]
BANKS = ["JPM", "BRK-B"]
CARDS = ["V", "MA", "JPM"]
INDUSTRIAL = ["CAT", "GE", "VRT"]

# 키: (FRED 번호, 이름, 빈도 M/Q/W, 변화 pct(%) · diff(%p), 예상 방향 +1 오르면 좋음 · −1 나쁨, 묶음)
INDICATORS = {
    "semi_ip":      ("IPG3344S", "반도체 생산지수", "M", "pct", +1, SEMI),
    "tech_orders":  ("A34SNO", "컴퓨터 · 전자제품 신규 주문", "M", "pct", +1, SEMI),
    "semi_ppi":     ("PCU33443344", "반도체 생산자물가", "M", "pct", +1, SEMI),
    "tech_profit":  ("N501RC1Q027SBEA", "컴퓨터 · 전자제품 업종 기업이익", "Q", "pct", +1, SEMI),
    "capex_orders": ("NEWORDER", "핵심 자본재 주문 (기업 설비투자)", "M", "pct", +1, BIGTECH),
    "retail_gm":    ("RSGMS", "종합소매(대형마트) 판매", "M", "pct", +1, RETAIL_BIG),
    "retail_all":   ("RSXFS", "소매판매 (외식 제외)", "M", "pct", +1, STAPLES),
    "retail_profit": ("N415RC1Q027SBEA", "소매업 기업이익", "Q", "pct", +1, RETAIL_BIG),
    "building_mat": ("RSBMGESD", "건자재 · 원예 판매", "M", "pct", +1, ["HD"]),
    "food_service": ("RSFSDP", "외식 판매", "M", "pct", +1, ["MCD"]),
    "nonstore":     ("RSNSR", "무점포(온라인) 판매", "M", "pct", +1, ["AMZN"]),
    "auto_sales":   ("TOTALSA", "신차 판매", "M", "pct", +1, ["TSLA"]),
    "auto_ip":      ("IPG3361T3S", "자동차 · 부품 생산지수", "M", "pct", +1, ["TSLA"]),
    "bank_loans":   ("TOTLL", "은행 대출", "W", "pct", +1, BANKS),
    "card_delinq":  ("DRCCLACBS", "카드 연체율", "Q", "diff", -1, CARDS),
    "wti":          ("MCOILWTICO", "유가 (WTI)", "M", "pct", +1, ENERGY),
    "oil_profit":   ("N404RC1Q027SBEA", "석유 · 석탄 제품 업종 기업이익", "Q", "pct", +1, ENERGY),
    "power_ip":     ("IPG2211S", "전력 생산지수", "M", "pct", +1, UTIL),
    "power_cpi":    ("CUSR0000SEHF01", "전기요금 (소비자물가)", "M", "pct", +1, UTIL),
    "util_profit":  ("N419RC1Q027SBEA", "전기 · 가스 업종 기업이익", "Q", "pct", +1, UTIL),
    "pharma_ip":    ("IPG3254S", "의약품 생산지수", "M", "pct", +1, PHARMA),
    "pharma_ppi":   ("PCU32543254", "의약품 생산자물가", "M", "pct", +1, PHARMA),
    "nonres_build": ("PNRESCONS", "비주거 건설 지출", "M", "pct", +1, INDUSTRIAL),
    "chem_ip":      ("IPG325S", "화학 생산지수", "M", "pct", +1, ["LIN"]),
}

RULES = ("통과 = 3개월 또는 6개월 가운데 하나에서 셋 다: ① 신호 상위 25% 달 − 하위 25% 달의 이후 초과수익 차이가 예상 방향 "
         "② 그 차이가 플라시보(신호를 통째로 무작위 칸 밀기 1,000번) 대비 p < 0.05 ③ 표본을 앞뒤 절반으로 나눠도 같은 방향")


# ── 자료 ────────────────────────────────────────────────────────────────

def _key():
    k = os.environ.get("FRED_API_KEY")
    if not k and os.path.exists(os.path.join(ROOT, ".env")):
        for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
            if line.startswith("FRED_API_KEY="):
                k = line.split("=", 1)[1].strip().strip("\"'")
    if not k:
        sys.exit("FRED_API_KEY 없음")
    return k


def fetch_fred(sid, key):
    q = urllib.parse.urlencode({"series_id": sid, "api_key": key, "file_type": "json", "observation_start": "1990-01-01"})
    obs = json.load(urllib.request.urlopen(f"https://api.stlouisfed.org/fred/series/observations?{q}", timeout=60))["observations"]
    return [(o["date"], float(o["value"])) for o in obs if o["value"] not in (".", "")]


def load_raw(refresh):
    if not refresh and os.path.exists(RAW_JSON):
        return json.load(open(RAW_JSON, encoding="utf-8"))
    key, raw = _key(), {}
    for k, (sid, *_r) in INDICATORS.items():
        try:
            raw[k] = fetch_fred(sid, key)
        except Exception as e:  # noqa: BLE001
            print(f"[us-val] {k} ({sid}) 실패: {str(e)[:80]}")
    os.makedirs(os.path.dirname(RAW_JSON), exist_ok=True)
    json.dump({"fetched": datetime.date.today().isoformat(), **raw}, open(RAW_JSON, "w", encoding="utf-8"))
    return {"fetched": datetime.date.today().isoformat(), **raw}


def series(rows, freq):
    """월 자료로 맞춘다 — 주간은 달 평균, 분기는 분기 끝 달에만 값(전년 대비 = 4분기 전)."""
    s = pd.Series({pd.Timestamp(d): v for d, v in rows}).sort_index()
    if freq == "W":
        s = s.groupby(s.index.to_period("M")).mean()
    elif freq == "Q":
        s.index = (s.index + pd.offsets.QuarterEnd(0)).to_period("M")
    else:
        s.index = s.index.to_period("M")
    return s[~s.index.duplicated(keep="last")]


def monthly_prices(syms):
    px = {}
    for s in syms:
        p = os.path.join(STORE, f"{s}.parquet")
        if not os.path.exists(p):
            continue
        c = pd.read_parquet(p)["close"].dropna()
        c.index = pd.to_datetime(c.index).to_period("M")
        px[s] = c.groupby(level=0).last()
    return pd.DataFrame(px)


# ── 계산 (한국 검증과 같은 식) ─────────────────────────────────────────

def signal(s, freq, kind):
    k = 4 if freq == "Q" else 12
    if freq == "Q":   # 분기 끝 달만 — 4칸 전 = 1년 전 분기
        return (s - s.shift(k)) if kind == "diff" else (s / s.shift(k) - 1) * 100
    return (s - s.shift(k)) if kind == "diff" else (s / s.shift(k) - 1) * 100


def excess_returns(px, members):
    r = px.pct_change(fill_method=None)
    basket = r[[m for m in members if m in r]].mean(axis=1, skipna=True)
    return ((basket - r[BENCH]) * 100).dropna()


def fwd(ex, h):
    return ex[::-1].rolling(h).sum()[::-1].shift(-1)


def spread(sig, f, min_n):
    d = pd.concat([sig, f], axis=1, keys=["s", "f"]).dropna()
    if len(d) < min_n:
        return None, len(d)
    q1, q3 = d["s"].quantile(0.25), d["s"].quantile(0.75)
    return d.loc[d["s"] >= q3, "f"].mean() - d.loc[d["s"] <= q1, "f"].mean(), len(d)


def placebo_p(sig, f, actual, rng, min_n):
    vals = sig.dropna()
    n, hits = len(vals), 0
    for _ in range(N_PLACEBO):
        k = rng.randint(4, n - 4) if n > 12 else rng.randint(1, n - 1)
        sp, _ = spread(pd.Series(np.roll(vals.values, k), index=vals.index), f, min_n)
        if sp is not None and abs(sp) >= abs(actual):
            hits += 1
    return (hits + 1) / (N_PLACEBO + 1)


def evaluate(key, raw, px, rng):
    sid, name, freq, kind, exp, members = INDICATORS[key]
    lag = 3 if freq == "Q" else 1
    s = series(raw, freq)
    sig = signal(s, freq, kind).dropna()
    sig.index = sig.index + lag
    sig = sig[sig.index >= pd.Period(START, "M")]
    have = [m for m in members if m in px]
    ex = excess_returns(px, have)
    min_n = MIN_NQ if freq == "Q" else MIN_N
    res = {"key": key, "fred": sid, "name": name, "freq": freq, "members": have, "expect": exp,
           "from": str(sig.index.min()) if len(sig) else None, "to": str(sig.index.max()) if len(sig) else None, "horizons": {}}
    common = sig.index.intersection(ex.index)
    half = common[len(common) // 2] if len(common) else None
    passed = []
    for h in HORIZONS:
        f = fwd(ex, h)
        sp, n = spread(sig, f, min_n)
        if sp is None:
            res["horizons"][h] = {"n": n}
            continue
        p = placebo_p(sig, f, sp, rng, min_n)
        a, _ = spread(sig[sig.index <= half], f, min_n // 2)
        b, _ = spread(sig[sig.index > half], f, min_n // 2)
        stable = a is not None and b is not None and np.sign(a) == np.sign(b) == np.sign(exp)
        ok = bool(np.sign(sp) == np.sign(exp) and p < 0.05 and stable)
        step = 3 if freq == "Q" else 1
        res["horizons"][h] = {"spread": float(sp), "n": n, "n_indep": max(1, n * step // h), "p": p, "first_half": None if a is None else float(a),
                              "second_half": None if b is None else float(b), "direction_ok": bool(np.sign(sp) == np.sign(exp)), "stable": bool(stable), "pass": ok}
        if ok and h in (3, 6):
            passed.append(h)
    res["pass"], res["pass_h"] = bool(passed), passed
    return res


# ── 문서 ────────────────────────────────────────────────────────────────

def write_md(results, fetched):
    L = ["# 미국 업종 지표 검증", "",
         f"작성 {datetime.date.today().isoformat()} · 스크립트 `experiments/stock-radar/validate_industry_us.py` · 자료 FRED(받은 날 {fetched}) · 주가 30년 저장소 data/store", "",
         "## 미리 정한 기준 (결과를 보기 전)", "",
         "- 신호: 지표의 전년 같은 달(분기) 대비 변화(%, 연체율은 %p). 발표 지연 = 월 자료 1개월 · 분기 자료 3개월.",
         "- 결과: 업종 묶음(이 블로그 미국 종목 중 그 사업, 동일가중 · 그달 이력이 있는 종목만)의 S&P 500(SPY) 대비 초과수익, 이후 1 · 3 · 6 · 12개월.",
         f"- {RULES}. 분기 자료는 분기 끝 달만 표본(n = 분기 수).",
         "- 한국 업종 지표 검증(doc/검증/한국-업종지표-검증.md)과 같은 식 · 같은 기준. 분석 시작 1999-01.",
         "- 한계: 묶음은 지금 종목 목록이라 생존 편향이 있다. 한 종목 묶음(홈디포 · 맥도날드 · 아마존 · 테슬라 · 린데)은 그 회사 사정이 섞인다. 같은 묶음에 지표가 여럿이라 우연 통과 가능성이 커진다(여러 번 시험).", "",
         "## 결과 요약", "",
         "| 지표 (FRED) | 묶음 | 기간 | 3개월 차이 (p) | 6개월 차이 (p) | 판정 |", "|---|---|---|---|---|---|"]
    for r in results:
        def cell(h):
            x = r["horizons"].get(h) or {}
            if "spread" not in x:
                return f"표본 부족 (n {x.get('n', 0)})"
            return f"{x['spread']:+.1f}%p (p {x['p']:.3f}, n {x['n']})"
        verdict = f"✅ 통과 ({', '.join(f'{h}개월' for h in r['pass_h'])})" if r["pass"] else "참고 숫자"
        L.append(f"| {r['name']} (`{r['fred']}`) | {', '.join(r['members'][:4])}{' 외' if len(r['members']) > 4 else ''} | {r['from'] or '—'}~{r['to'] or ''} | {cell(3)} | {cell(6)} | {verdict} |")
    L += ["", "## 지표별 상세", ""]
    for r in results:
        L += [f"### {r['name']} (`{r['fred']}`, {'분기' if r['freq'] == 'Q' else '월'})", "",
              f"- 묶음: {', '.join(r['members'])} · 예상 방향 {'오르면 좋음' if r['expect'] > 0 else '오르면 나쁨'}", "",
              "| 기간 | 상위25% − 하위25% | p | n (독립) | 앞 절반 | 뒤 절반 | 판정 |", "|---|---|---|---|---|---|---|"]
        for h in HORIZONS:
            x = r["horizons"].get(h) or {}
            if "spread" not in x:
                L.append(f"| {h}개월 | 표본 부족 | | {x.get('n', 0)} | | | |")
                continue
            fh = "—" if x["first_half"] is None else f"{x['first_half']:+.1f}"
            sh = "—" if x["second_half"] is None else f"{x['second_half']:+.1f}"
            L.append(f"| {h}개월 | {x['spread']:+.2f}%p | {x['p']:.3f} | {x['n']} ({x['n_indep']}) | {fh} | {sh} | "
                     f"{'통과' if x['pass'] else ('방향 맞음' if x['direction_ok'] else '방향 반대')} |")
        L.append("")
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L) + "\n")


def main():
    fetch_only = "--fetch" in sys.argv
    raw = load_raw(refresh=fetch_only or "--refresh" in sys.argv)
    fetched = raw.pop("fetched", "")
    for k, rows in raw.items():
        print(f"[us-val] {k:13} {INDICATORS[k][0]:16} {rows[0][0]}~{rows[-1][0]} ({len(rows)})")
    syms = sorted({m for v in INDICATORS.values() for m in v[5]} | {BENCH})
    px = monthly_prices(syms)
    print(f"[us-val] 주가 {len(px.columns)}종목 (없음: {[s for s in syms if s not in px]})")
    if fetch_only:
        return
    rng = random.Random(SEED)
    results = [evaluate(k, raw[k], px, rng) for k in INDICATORS if k in raw]
    json.dump(results, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_md(results, fetched)
    print(f"[us-val] 통과 {sum(r['pass'] for r in results)} / {len(results)} → {OUT_MD}")


if __name__ == "__main__":
    main()
