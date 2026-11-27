"""한국 종목 ↔ 미국 연결 종목 — 후보는 AI, 검증은 정식과 같은 코드.

정식(kr-stocks/universe_kr.PAIRS · PAIR_RECORD)은 후보를 사람이 고르고 validate_daily.run_overnight 로 검증했다. 여기서는 후보 고르기만 AI 로 바꾼다.
  1. --pick : 한국 종목 350(간단 316 + 정식 35)마다 사업으로 이어진 미국 종목(S&P 500 명단 안) 최대 3개 + 이유. 사슬 news-quick(3.1 lite → 3.5 lite → Gemma), 10종목 묶음.
     데이터에서 상관을 찾아 고르지 않는다 — 사업 관계로 먼저 고르고(가설), 데이터는 검증에만 (지표 검증 원칙).
  2. --validate : validate_daily 의 함수 그대로 — 신호 = 연결 종목 밤사이 수익 평균(미국 t 종가 → 한국 t 종가 시점에 알려진 것), 대상 = 한국 종목 다음 1 · 5거래일 수익 − 그 시장 지수.
     통과 기준(결과 보기 전에 정함): ① 상위 25% − 하위 25% 차이가 + ② 플라시보(통째 밀기 500회) p < 0.05 ③ 앞뒤 절반 같은 방향 ④ 350개를 함께 시험하므로 BH q < 0.10 (정식 35개보다 엄격).
     정식과 다른 점: 코스닥 종목은 코스닥 지수 대비(정식은 모두 코스피 대비).
저장: experiments/ref/kr_us_links_candidates.json · kr_us_links.json (통과 · 기록). 화면 연결은 결과 확인 뒤.

    .venv/bin/python experiments/stock-quick/kr_us_links.py --pick
    .venv/bin/python experiments/stock-quick/kr_us_links.py --validate
"""
import argparse
import json
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [EXP, os.path.join(EXP, "kr-stocks")]

REF = os.path.join(EXP, "ref", "quick_ref.json")
CAND = os.path.join(EXP, "ref", "kr_us_links_candidates.json")
OUT = os.path.join(EXP, "ref", "kr_us_links.json")
BATCH = 10
MAX_PICK = 3
Q_MAX = 0.10
SEED = 20261115

PROMPT = """너는 한국 · 미국 주식 산업 분석가다. 아래 한국 상장사마다, 사업으로 직접 이어진 미국 상장사를 0~3개 고른다.
이어짐 = 그 미국 회사의 실적 · 주가가 움직이면 이 한국 회사 사업에도 같은 방향 영향이 가는 관계:
  고객(한국 회사 제품을 사는 미국 회사), 공급(부품 · 장비를 대는 미국 회사), 같은 수요(같은 최종 시장을 같이 타는 미국 동종 회사), 지분 · 계열.
규칙:
- 미국 회사는 반드시 아래 [미국 명단]의 티커만. 명단에 없으면 고르지 않는다.
- 분명하지 않으면 고르지 않는다(빈 목록). 단순히 같은 업종이라는 이유만으로 큰 회사를 고르지 않는다 — 실제 사업 연결이 있는 것만.
- 이유는 한국어 명사구 20자 안팎(예: "HBM 메모리 수요", "스마트폰 카메라 모듈 고객").
출력 = JSON 객체 하나: {"한국코드": [{"t": "티커", "rel": "고객|공급|같은 수요|지분", "why": "이유"}], ...} — 모든 한국 코드를 키로 넣는다.

[미국 명단] (티커 이름)
"""


def load_ref():
    return json.load(open(REF, encoding="utf-8"))


def pick():
    from llm_chain import LLMPool
    ref = load_ref()
    us = ref["us"]
    us_list = "\n".join(f"{t} {e.get('en', '')}" for t, e in sorted(us.items()))
    have = json.load(open(CAND, encoding="utf-8")) if os.path.exists(CAND) else {}
    todo = [k for k in sorted(ref["kr"]) if k not in have]
    pool = LLMPool("news-quick", label="kr-us-links")
    calls = 0
    for i in range(0, len(todo), BATCH):
        part = todo[i:i + BATCH]
        body = "\n".join(f"{k}\t{ref['kr'][k].get('ko')}\t{ref['kr'][k].get('en')}\t{ref['kr'][k].get('industry_en') or ''}\t{ref['kr'][k].get('sub_ours') or ref['kr'][k].get('sub') or ''}"
                         for k in part)
        calls += 1
        try:
            val = pool.generate_json(PROMPT + us_list + "\n\n[한국 상장사] (코드 · 이름 · 영문 · 업종 · 세부 업종)\n" + body, temperature=0.1, max_tokens=4000)
        except Exception as e:  # noqa: BLE001
            print(f"[links] 묶음 {i} 실패 — 다음 실행에 이어서: {str(e)[:120]}")
            break
        for k in part:
            rows = (val or {}).get(k) if isinstance(val, dict) else None
            ok = []
            for r in rows or []:
                t = str((r or {}).get("t") or "").upper().replace(".", "-").strip()
                if t in us and t not in [x["t"] for x in ok]:
                    ok.append({"t": t, "rel": str(r.get("rel") or "")[:6], "why": re.sub(r"\s+", " ", str(r.get("why") or ""))[:30]})
            have[k] = {"pairs": ok[:MAX_PICK], "model": pool.last_model or ""}
        json.dump(have, open(CAND, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"[links] {min(i + BATCH, len(todo))}/{len(todo)} · 호출 {calls}")
    n = sum(1 for v in have.values() if v["pairs"])
    print(f"[links] 후보 {n}/{len(have)}종목 · 쌍 {sum(len(v['pairs']) for v in have.values())} · AI {calls}번")


def prices(syms):
    import pandas as pd
    import yfinance as yf
    t0 = time.time()
    px = {}
    for i in range(0, len(syms), 150):
        df = yf.download(syms[i:i + 150], start="2000-01-01", interval="1d", auto_adjust=True, group_by="ticker", progress=False, threads=4)
        for s in syms[i:i + 150]:
            try:
                c = df[s]["Close"].dropna()
            except KeyError:
                continue
            c.index = pd.to_datetime(c.index).tz_localize(None).normalize()
            px[s] = c[~c.index.duplicated(keep="last")]
        time.sleep(2)
    px = pd.DataFrame(px)
    print(f"[links] 일봉 {px.shape[1]}/{len(syms)} · {time.time() - t0:.0f}초")
    return px


def one_test(V, px, k, ps, rng):
    """미국 짝(들) 밤사이 수익 평균 → 한국 종목 다음 1 · 5거래일(그 시장 지수 대비). validate_daily.test 그대로."""
    bench = "^KQ11" if k.endswith(".KQ") else "^KS11"
    idx = px[bench].pct_change(fill_method=None).dropna() * 100
    sig = (px[ps].pct_change(fill_method=None).mean(axis=1) * 100).dropna()
    sig.index = V.us_to_kr_signal_day(sig.index, idx.index)
    sig = sig[~sig.index.duplicated(keep="last")]
    tgt = (px[k].pct_change(fill_method=None) * 100 - idx).dropna()
    return V.test(k, "links", sig, tgt, (1, 5), +1, rng)


def validate():
    import validate_daily as V
    cand = json.load(open(CAND, encoding="utf-8"))
    ks = [k for k, v in cand.items() if v["pairs"]]
    us = sorted({p["t"] for k in ks for p in cand[k]["pairs"]})
    t0 = time.time()
    px = prices(ks + us + ["^KS11", "^KQ11"])
    rng = random.Random(SEED)
    res = []
    for n_done, k in enumerate(ks):
        ps = [p["t"] for p in cand[k]["pairs"] if p["t"] in px]
        if not ps or k not in px:
            continue
        r = one_test(V, px, k, ps, rng)
        r["pairs"] = ps
        res.append(r)
        if n_done % 25 == 0:
            print(f"[links] 검증 {n_done}/{len(ks)} · {time.time() - t0:.0f}초")
    # BH — 종목마다 가장 작은 p(1 · 5일)로, 350개 함께
    ps_ = [min((h.get("p", 1.0) for h in r["h"].values() if "p" in h), default=1.0) for r in res]
    qs = V.bh(ps_)
    out = {}
    for r, q in zip(res, qs):
        h1 = r["h"].get(1) or {}
        best = min((h for h in r["h"] if "p" in r["h"][h]), key=lambda h: r["h"][h]["p"], default=None)
        k = r["name"]
        out[k] = {"pairs": r["pairs"], "why": {p["t"]: p["why"] for p in cand[k]["pairs"]}, "rel": {p["t"]: p["rel"] for p in cand[k]["pairs"]},
                  "spread1": h1.get("spread"), "n": h1.get("n"), "p1": h1.get("p"), "best_h": best, "q": q, "from": r["from"],
                  "pass_raw": r["pass"], "pass": bool(r["pass"] and q < Q_MAX)}
    json.dump({"built": time.strftime("%Y-%m-%d"), "rule": f"p<0.05 · 앞뒤 절반 · BH q<{Q_MAX} · 코스닥은 코스닥 지수 대비", "links": out},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"[links] 검증 {len(out)}종목 · 통과(원 기준) {sum(v['pass_raw'] for v in out.values())} · 통과(BH 포함) {sum(v['pass'] for v in out.values())} · {time.time() - t0:.0f}초")


def validate_each():
    """짝 하나씩 — 묶음 평균은 강한 짝 덕에 약한 짝도 같이 통과했다(SK하이닉스 ← MSFT 등).
    기준(결과 보기 전): 짝 하나의 신호로 같은 검정(+ 방향 · 플라시보 p<0.05 · 앞뒤 절반) + 짝 전체(278개) BH q<0.10. 화면 = 통과한 짝만."""
    import validate_daily as V
    cand = json.load(open(CAND, encoding="utf-8"))
    pairs = [(k, p) for k, v in cand.items() for p in v["pairs"]]
    t0 = time.time()
    px = prices(sorted({k for k, _ in pairs}) + sorted({p["t"] for _, p in pairs}) + ["^KS11", "^KQ11"])
    rng = random.Random(SEED)
    res = []
    for i, (k, p) in enumerate(pairs):
        if k not in px or p["t"] not in px:
            continue
        r = one_test(V, px, k, [p["t"]], rng)
        res.append((k, p, r))
        if i % 40 == 0:
            print(f"[links] 짝 검증 {i}/{len(pairs)} · {time.time() - t0:.0f}초")
    qs = V.bh([min((h.get("p", 1.0) for h in r["h"].values() if "p" in h), default=1.0) for _, _, r in res])
    links = {}
    for (k, p, r), q in zip(res, qs):
        h1 = r["h"].get(1) or {}
        best = min((h for h in r["h"] if "p" in r["h"][h]), key=lambda h: r["h"][h]["p"], default=None)
        e = links.setdefault(k, {"pairs": [], "tested": []})
        row = {"t": p["t"], "rel": p["rel"], "why": p["why"], "spread1": h1.get("spread"), "n": h1.get("n"), "p1": h1.get("p"),
               "best_h": best, "q": q, "from": r["from"], "pass_raw": r["pass"], "pass": bool(r["pass"] and q < Q_MAX)}
        e["tested"].append(row)
        if row["pass"]:
            e["pairs"].append(p["t"])
    for e in links.values():
        e["pass"] = bool(e["pairs"])
    json.dump({"built": time.strftime("%Y-%m-%d"), "rule": f"짝 하나씩 · p<0.05 · 앞뒤 절반 · 짝 {len(res)}개 BH q<{Q_MAX} · 코스닥은 코스닥 지수 대비", "links": links},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"[links] 짝 {len(res)}개 · 통과 짝 {sum(r['pass'] for e in links.values() for r in e['tested'])} · 통과 종목 {sum(e['pass'] for e in links.values())} · {time.time() - t0:.0f}초")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(EXP, "..", ".env"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick", action="store_true")
    ap.add_argument("--validate", action="store_true", help="종목마다 짝 묶음 평균 (1차)")
    ap.add_argument("--each", action="store_true", help="짝 하나씩 (화면 기준)")
    a = ap.parse_args()
    if a.pick:
        pick()
    if a.validate:
        validate()
    if a.each:
        validate_each()
