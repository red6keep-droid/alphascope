"""종목 주가(간단 종목, 미국) 뉴스 — Finnhub 기사 목록 + 원문 첫 문단 → 공용 분류 · 요약.

왜 Finnhub: 구글 뉴스 주소 풀기는 한 IP 에서 시작 약 1분 뒤 막힌다(11-15 실측 — 동시 3개 198건 · 1초 간격 36건 · 2초 간격 23건).
  Finnhub company-news = 종목당 평일 하루 4.16건 · 요약 글 86% · 막힘 0, 그 링크로 원문에 직접 들어가면 첫 문단 75%(막힘 0) — 기억 quick-news-plan.
흐름 (AI 는 4 · 5 단계만, 사슬 news-quick = 3.1 lite → 3.5 lite → Gemma 4 26B):
  1. Finnhub company-news 종목마다 1번(1.1초 간격 — 분당 60 한도)  2. 최근 HOURS 시간 · 아직 없는 기사 · 종목당 PER_STOCK 건(최신)
  3. 첫 문단 = Finnhub 링크 → 원문(3개 동시, 막는 사이트는 건너뜀), 못 받으면 Finnhub 요약 글 — **실행 중에만 쓰고 저장하지 않는다**(운영지침 4-3)
  4. 공용 분류 news_store.classify (정식 종목과 같은 지시문 · 검사 · 결과 모양, 25건 묶음 · 묶음에 나온 회사만)
  5. 화면에 낼 기사(관련도 1 이상 · 사실 문장 있음, 종목당 SUMMARY_PER 건)만 공용 요약 news_summary.summarize (5건 묶음)
저장 (--state, 워크플로 = 비공개 상태 저장소 quick-news-state, 기록 없이 덮어씀): news.json(분류 결과, KEEP_DAYS) · summaries.json(팝업 다섯 줄)
화면 연결은 3단계(종목 주가 조각) — 이 파일은 받아 두기만 한다(그림자).

    .venv/bin/python experiments/stock-quick/quick_news.py --state DIR [--limit N] [--no-ai] [--max-calls N]
"""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [EXP]
import article_lead  # noqa: E402
import news_store  # noqa: E402
import news_summary  # noqa: E402

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
HOURS = 24            # 이보다 오래된 기사는 새로 받지 않는다 (정식 CLASSIFY_HOURS 와 같게)
PER_STOCK = 3         # 종목당 한 실행 새 기사 상한 — 11-15 실측: 452종목 하루 약 940건
SUMMARY_PER = 2       # 종목당 요약(팝업) 기사 상한
KEEP_DAYS = 8
MAX_CALLS = 60        # 분류 호출 상한 (25건 묶음 — 1,500건)
SUMMARY_MAX = 300     # 요약 기사 상한 (8건 묶음 — 약 38회)
GAP = 1.1             # Finnhub 분당 60
BLOCKED_HOSTS = ("benzinga.com", "seekingalpha.com", "chartmill.com", "fintel.io", "barchart.com")   # 11-15 실측 403 — 열지 않고 요약 글로


def _load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(path, v):
    tmp = path + ".tmp"
    json.dump(v, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, path)


def _key(title):
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def finnhub_key():
    return (os.environ.get("FINNHUB_API_KEY") or "").split(",")[0].strip()


def fetch(sym, key, day_from, day_to):
    for attempt in range(2):
        r = requests.get("https://finnhub.io/api/v1/company-news", params={"symbol": sym.replace("-", "."), "from": day_from, "to": day_to, "token": key}, timeout=30)
        if r.status_code == 429 and attempt == 0:
            time.sleep(60)
            continue
        r.raise_for_status()
        return r.json() or []
    return []


def register(ref):
    """간단 종목을 공용 처리의 종목 명단(news_store.U 사본) · 영문 이름표(EN)에 얹는다 — 이 실행 안에서만."""
    U = news_store.U
    for s, e in ref.items():
        if s not in U.BY_SYM:
            U.CANDIDATES.append((s, e.get("ko") or s, s.lower(), "기술"))
            U.BY_SYM[s] = U.CANDIDATES[-1]
        news_store.EN.setdefault(s, e.get("en") or s)


def lead_of(url):
    """Finnhub 링크 → 원문 → 첫 문단. 막는 사이트 · 실패는 빈 값."""
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20, allow_redirects=True)
        host = urllib.parse.urlparse(r.url).netloc
        if not r.ok or any(h in host for h in BLOCKED_HOSTS):
            return host, ""
        return host, article_lead.lead_text(r.url)
    except Exception:  # noqa: BLE001
        return "?", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--limit", type=int, default=0, help="시험용 — 앞 N종목만")
    ap.add_argument("--only", default="", help="시험용 — 이 종목들만(쉼표)")
    ap.add_argument("--no-ai", action="store_true", help="받기 · 첫 문단만 (분류 · 요약 없음)")
    ap.add_argument("--max-calls", type=int, default=MAX_CALLS)
    a = ap.parse_args()
    t0 = time.time()
    os.makedirs(a.state, exist_ok=True)
    news_p, summ_p = os.path.join(a.state, "news.json"), os.path.join(a.state, "summaries.json")
    ref = {s: e for s, e in json.load(open(os.path.join(EXP, "ref", "quick_ref.json"), encoding="utf-8"))["us"].items() if not e.get("full")}
    syms = sorted(ref)
    if a.only:
        syms = [s for s in syms if s in {x.strip() for x in a.only.split(",")}]
    if a.limit:
        syms = syms[:a.limit]
    register(ref)
    key = finnhub_key()
    if not key:
        sys.exit("FINNHUB_API_KEY 없음")

    now = datetime.datetime.now(datetime.timezone.utc)
    hours = HOURS * 3 if now.astimezone(datetime.timezone(datetime.timedelta(hours=9))).weekday() == 1 else HOURS   # 화요일(KST 06:40) = 토요일 아침 실행 뒤 72시간(주말 · 월요일 미국 장) — 일 · 월 아침엔 실행이 없다
    cut = now - datetime.timedelta(hours=hours)
    keep = (now - datetime.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    store = {k: v for k, v in _load(news_p, {}).items() if v.get("published_at", "") >= keep}
    seen = {_key(v["title"]): k for k, v in store.items()}

    # 1 · 2. 기사 목록
    fails, got, new = [], 0, {}
    day_from, day_to = cut.date().isoformat(), now.date().isoformat()
    for i, s in enumerate(syms):
        if i:
            time.sleep(GAP)
        try:
            rows = fetch(s, key, day_from, day_to)
        except Exception as e:  # noqa: BLE001
            fails.append(f"{s}:{str(e)[:50]}")
            continue
        got += len(rows)
        rows = sorted((r for r in rows if r.get("datetime") and r.get("headline") and r.get("url")), key=lambda r: -r["datetime"])
        k = 0
        for r in rows:
            at = datetime.datetime.fromtimestamp(r["datetime"], datetime.timezone.utc)
            if at < cut or k >= PER_STOCK:
                continue
            tk = _key(r["headline"])
            if tk in seen:   # 다른 종목 · 지난 실행에서 이미 — 종목만 덧붙인다
                q = store.get(seen[tk]) or new.get(seen[tk])
                if q is not None and s not in q["queries"]:
                    q["queries"].append(s)
                continue
            iid = hashlib.sha1(tk.encode()).hexdigest()[:12]
            new[iid] = {"title": r["headline"], "url": r["url"], "source": r.get("source") or "", "published_at": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "query": s, "queries": [s], "item_id": iid, "feed": "finnhub", "_summary": (r.get("summary") or "").strip()}
            seen[tk] = iid
            k += 1
    t_list = time.time() - t0
    print(f"[quick-news] Finnhub {len(syms)}종목 · 실패 {len(fails)} {fails[:3]} · 받은 기사 {got} · 새 기사 {len(new)} · {t_list:.0f}초")

    # 3. 첫 문단 (실행 중에만)
    t1 = time.time()
    with concurrent.futures.ThreadPoolExecutor(3) as ex:
        res = dict(zip(new, ex.map(lambda k: lead_of(new[k]["url"]), new)))
    n_lead = 0
    for k, v in new.items():
        lead = res[k][1]
        n_lead += bool(lead)
        v["snippet"] = (lead or v.pop("_summary", "") or "")[:news_summary.SRC_MAX]   # 900자 — 분류는 news_store 가 SNIPPET(500)으로 잘라 쓰고, 요약은 900자 다 (11-15: 500자로 넘겨 두 줄 이상 요약이 42% 뿐이었다)
        v.pop("_summary", None)
    print(f"[quick-news] 첫 문단 {n_lead}/{len(new)} · 요약 글로 대신 {sum(1 for k, v in new.items() if not res[k][1] and v['snippet'])} · {time.time() - t1:.0f}초")
    store.update(new)

    def save(st):   # 첫 문단 · 요약 글(snippet)은 저장하지 않는다
        _save(news_p, {k: {f: x for f, x in v.items() if f != "snippet"} for k, v in st.items()})

    if a.no_ai:
        save(store)
        print(f"[quick-news] AI 없이 끝 · 보관 {len(store)}건 · 전체 {time.time() - t0:.0f}초")
        return

    # 4. 분류 (snippet 이 있는 이번 기사 + 지난 실행에서 탈락한 것)
    news_store.classify(store, save, lead_cache=None, label="quick-news", hours=hours, chains=("news-quick",), batch=25, item_companies=True, max_calls=a.max_calls)
    save(store)

    # 5. 요약 — 화면에 낼 기사만, 종목당 SUMMARY_PER 건 (관련도 높은 것 · 최신)
    pick, per = [], {}
    for v in sorted(store.values(), key=lambda v: v["published_at"], reverse=True):
        if v["item_id"] not in new or not v.get("fact"):
            continue
        sc = [x for x in v.get("scores") or [] if x.get("relevance", 0) >= 1]
        if not sc:
            continue
        top = max(sc, key=lambda x: x["relevance"])["ticker"]
        if per.get(top, 0) >= SUMMARY_PER:
            continue
        per[top] = per.get(top, 0) + 1
        pick.append({"item_id": v["item_id"], "title": v["title"], "url": v["url"], "snippet": v.get("snippet") or ""})
    out = news_summary.summarize(pick, cache_path=summ_p, lead_cache=None, label="quick-summary", max_items=SUMMARY_MAX, chain="news-quick", batch=5)   # 8건이면 3.1 lite 가 자주 항목 불일치 → 대체 모델로 호출 낭비 (11-15 실측)
    two = sum(1 for x in pick if len(out.get(x["item_id"]) or []) >= 2)
    cls = [v for k, v in store.items() if k in new]
    print(f"[quick-news] 분류됨 {sum(1 for v in cls if v.get('ai_model'))}/{len(cls)} · 관련도 2 이상 {sum(1 for v in cls if any(x.get('relevance', 0) >= 2 for x in v.get('scores') or []))}"
          f" · 요약 대상 {len(pick)} · 두 줄 이상 {two} · 보관 {len(store)}건 · 전체 {time.time() - t0:.0f}초")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv

    load_dotenv(os.path.join(EXP, "..", ".env"))
    main()
