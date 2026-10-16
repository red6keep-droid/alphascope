# 2026-10-16 세션 임시 스크립트를 저장소로 옮김 (집에서 이어가기 위해). 경로(HERE 아래 nvda/·trump/ 상태 브랜치 사본, .env 키 이름)는 환경에 맞춰 바꿀 것.
# 사용: 상태 브랜치를 git archive 로 cmp/nvda·cmp/trump 에 풀고  python -I compare_gemini_models.py gemini-3.5-flash-lite,gemini-3.6-flash
"""후보 Gemini 모델의 분류 정확도 비교 — 상태 브랜치의 gemini-3.5-flash 라벨을 기준으로 칸 단위 일치율.
usage: python -I compare.py gemini-3.5-flash,gemini-3.5-flash-lite,...
"""
import collections
import json
import os
import sys
import time

ROOT = "D:/Alpha-Scope.blogspot/experiments"
HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = sys.argv[1].split(",")
N_NVDA, N_TRUMP = 40, 30

sys.path.insert(0, "C:/Users/futechsoft/AppData/Local/Programs/Python/Python312/Lib/site-packages")
from dotenv import dotenv_values  # noqa: E402
import requests  # noqa: E402

ENV = dotenv_values("D:/Alpha-Scope.blogspot/.env")
sys.path.insert(0, ROOT)
import llm_chain  # noqa: E402

STATUS = collections.Counter()
CUR = [None]
_post = requests.post


def post(url, *a, **kw):
    r = _post(url, *a, **kw)
    if "generativelanguage" in url:
        STATUS[(CUR[0], r.status_code)] += 1
    return r


requests.post = post
FORCE_KEY = os.environ.get("CMP_KEY", "").strip()   # DAILY · NVDA · TRUMP — 비우면 NVDA 는 NVDA 키, 트럼프는 트럼프 키
_parse = llm_chain.parse_json
PARSE_FAILS = [0]


def parse_json(text):
    try:
        return _parse(text)
    except Exception:
        PARSE_FAILS[0] += 1
        with open(os.path.join(HERE, f"parsefail_{CUR[0]}_{PARSE_FAILS[0]}.txt"), "w", encoding="utf-8") as f:
            f.write(text or "")
        raise


llm_chain.parse_json = parse_json
PKG_MODS =("config", "db", "labels", "prefilter", "classify_items", "classify_posts", "collect_posts")


def load_pkg(name):
    for m in PKG_MODS:
        sys.modules.pop(m, None)
    sys.path = [p for p in sys.path if not p.startswith(ROOT + "/")]
    sys.path.insert(0, ROOT + "/" + name)


def run_model(model, fn):
    llm_chain.STEPS["gemini"]["model"] = model
    llm_chain._EXHAUSTED_KEYS.clear()   # 하루 한도는 모델별 — 앞 모델의 한도가 다음 모델을 막지 않게
    CUR[0] = model
    pool = llm_chain.LLMPool("json-gemini", label=f"cmp-{model}")
    t = time.time()
    out = {}
    for batch in fn(pool):
        out.update(batch)
    return out, time.time() - t


RESULTS = {}

# ---------------------------------------------------------------- NVDA
load_pkg("nvda-report")
import config  # noqa: E402
import classify_items  # noqa: E402

os.environ["GEMINI_API_KEY"] = ENV[f"GEMINI_API_KEY_{FORCE_KEY or 'NVDA'}"].strip().strip('"')
rows = [json.loads(l) for l in open(os.path.join(HERE, "nvda/experiments/nvda-report/output/state/items.jsonl"), encoding="utf-8") if l.strip()]
truth = sorted((r for r in rows if r.get("ai_model") == "gemini-3.5-flash" and r["kind"] in config.CLASSIFY_KINDS), key=lambda r: r["published_at"])
sample = truth[-N_NVDA:]
batches = [sample[i:i + config.CLASSIFY_BATCH_SIZE] for i in range(0, len(sample), config.CLASSIFY_BATCH_SIZE)]
head = classify_items._load_prompt()
analyzed = [r for r in rows if r.get("analyzed_at") and r.get("ai_fact") and (r.get("ai_relevance") or 0) >= 1]


def nvda_facts(batch):
    ids = {b["item_id"] for b in batch}
    end = max(b["published_at"] for b in batch)
    since = end[:10]
    import datetime
    since = (datetime.date.fromisoformat(since) - datetime.timedelta(days=config.NOVELTY_WINDOW_DAYS)).isoformat()
    cand = [r for r in analyzed if r["item_id"] not in ids and since <= r["published_at"] <= end]
    cand.sort(key=lambda r: r["published_at"], reverse=True)
    return [f"{r['published_at'][:10]} [{r['ai_area']}] {r['ai_fact']}" for r in cand[:config.NOVELTY_CONTEXT_MAX]]


NVDA_FIELDS = ("ai_area", "ai_direction", "ai_novelty", "ai_relevance")
print(f"[nvda] 기준 {len(truth)}건 중 최근 {len(sample)}건 · {len(batches)}배치")
for model in MODELS:
    def fn(pool):
        for b in batches:
            try:
                yield {v["item_id"]: v for v in classify_items.classify_batch(pool, head, b, nvda_facts(b))}
            except Exception as e:  # noqa: BLE001
                print(f"[nvda] {model} 배치 실패: {str(e)[:150]}")
                yield {}
    out, dt = run_model(model, fn)
    per = collections.Counter()
    missing = 0
    for t in sample:
        v = out.get(t["item_id"])
        if not v:
            missing += 1
            continue
        for f in NVDA_FIELDS:
            per[f] += v[f] == t[f]
    RESULTS.setdefault(model, {})["nvda"] = {"match": sum(per.values()), "cells": len(sample) * len(NVDA_FIELDS), "per": dict(per), "missing": missing, "sec": round(dt)}
    print(f"[nvda] {model}: {sum(per.values())}/{len(sample) * len(NVDA_FIELDS)} {dict(per)} 누락 {missing} {dt:.0f}s")

# ---------------------------------------------------------------- Trump
load_pkg("trump-trend")
import config  # noqa: E402,F811
import classify_posts  # noqa: E402
import collect_posts  # noqa: E402

os.environ["GEMINI_API_KEY"] = ENV[f"GEMINI_API_KEY_{FORCE_KEY or 'TRUMP'}"].strip().strip('"')
cls = [json.loads(l) for l in open(os.path.join(HERE, "trump/experiments/trump-trend/output/state/classifications.jsonl"), encoding="utf-8") if l.strip()]
gem = {r["id"]: r for r in cls if r.get("ai_model") == "gemini-3.5-flash"}
recs = [collect_posts.normalize(x) for x in collect_posts.fetch_archive()]
cand = sorted((r for r in recs if r["id"] in gem and r["noise_reason"] is None), key=lambda r: r["published_at"], reverse=True)[:N_TRUMP]
tbatches = [cand[i:i + config.CLASSIFY_BATCH_SIZE] for i in range(0, len(cand), config.CLASSIFY_BATCH_SIZE)]
thead = classify_posts._load_prompt()
T_FIELDS = ("ai_topic", "ai_direction", "ai_intensity", "ai_market_relevance")
print(f"[trump] 기준 {len(gem)}건 중 아카이브에 있는 최근 {len(cand)}건 · {len(tbatches)}배치")
for model in MODELS:
    def fn(pool):
        for b in tbatches:
            try:
                yield {v["id"]: v for v in classify_posts.classify_batch(pool, thead, b)}
            except Exception as e:  # noqa: BLE001
                print(f"[trump] {model} 배치 실패: {str(e)[:150]}")
                yield {}
    out, dt = run_model(model, fn)
    per = collections.Counter()
    near = 0
    missing = 0
    for p in cand:
        t = gem[p["id"]]
        v = out.get(p["id"])
        if not v:
            missing += 1
            continue
        for f in T_FIELDS:
            per[f] += v[f] == t[f]
        near += abs(v["ai_intensity"] - t["ai_intensity"]) <= 1
        near += abs(v["ai_market_relevance"] - t["ai_market_relevance"]) <= 1
    RESULTS[model]["trump"] = {"match": sum(per.values()), "cells": len(cand) * len(T_FIELDS), "per": dict(per), "near": near, "missing": missing, "sec": round(dt)}
    print(f"[trump] {model}: {sum(per.values())}/{len(cand) * len(T_FIELDS)} {dict(per)} ±1 {near}/{len(cand) * 2} 누락 {missing} {dt:.0f}s")

print("\n=== 요약 (기준: 상태 브랜치의 gemini-3.5-flash 라벨) ===")
print(f"{'model':26} {'NVDA 일치':>10} {'누락':>4} {'초':>5}   {'트럼프 일치':>10} {'±1':>7} {'누락':>4} {'초':>5}   HTTP")
for m in MODELS:
    n, t = RESULTS[m]["nvda"], RESULTS[m]["trump"]
    codes = " ".join(f"{c}×{k}" for (mm, c), k in sorted(STATUS.items()) if mm == m)
    print(f"{m:26} {n['match']:>4}/{n['cells']:<5} {n['missing']:>4} {n['sec']:>5}   {t['match']:>4}/{t['cells']:<5} {t['near']:>3}/{len(cand) * 2:<3} {t['missing']:>4} {t['sec']:>5}   {codes}")
json.dump({"results": RESULTS, "status": {f"{m} {c}": k for (m, c), k in STATUS.items()}}, open(os.path.join(HERE, "results.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
