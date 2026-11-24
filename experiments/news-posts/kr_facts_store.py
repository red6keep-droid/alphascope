"""한국 기사 공용 저장소 — 수집기 블로그 저장소(news-text-blog)의 사건별 사실(facts) · 기사 제목(headlines)을 날짜별 공개 JSON 으로 (2026-11-24 사용자).

    FIREBASE_SERVICE_ACCOUNT=<블로그 서비스 계정 키> python experiments/news-posts/kr_facts_store.py --out store
    python experiments/news-posts/kr_facts_store.py --out store --gcloud <gcloud 로그인 계정>      # 로컬 시험
    python experiments/news-posts/kr_facts_store.py --out store --samples                        # 받은 표본(samples/)으로만

- 읽기만: news-text-blog `facts`(정기 실행 07:00 · 16:30, 30일 보관) · `headlines`(07:00 · 14:40 · 16:30). 블로그 서비스 계정 = roles/datastore.viewer.
- 쓰는 것(--out 폴더 = 상태 브랜치 kr-facts 를 꺼낸 자리 → Cloudflare Pages `newfact-news` 에 통째로):
    kr/facts/{YYYY-MM-DD}.json  그날(KST) 가장 늦은 정기 실행의 사건 + 그날 기사 제목 전부. 수집기가 30일 뒤 지워도 여기엔 남는다(기록).
    kr/facts/latest.json        가장 최근 날 파일과 같은 내용 — 한국 홈 · 한국 증시 리포트 뉴스 탭이 읽는다
    kr/facts/index.json         날짜 목록(사건 수 · 제목 수)
    _headers                    CORS(블로그 도메인에서 읽기) · 캐시 10분
- 싣는 조건(요청 문서 15 · 16절, 사용자 11-23): 2곳 이상이 보도한 사건만 · 사실은 `sources` 2 이상만 · 발언은 verified 이고 익명 아닐 때만 인용.
  `copied` 사실은 수집기가 이미 뺐다. 언론사 이름 · 주소는 사실에 붙이지 않고, 같은 사건 제목 묶음(headlines)의 원문 보기로만.
  이 조건은 공개 여부 규칙이지 개수 상한이 아니다 — 조건을 넘은 사건 · 사실 · 제목은 전부 싣는다(자르기 없음).
- 비교 대상(헌법 제1조): 보도한 곳 수(`sourceCount`) · 숫자의 발표/예상(`numbers.kind`) · 숫자가 매체끼리 맞았나(`agreed`).
- AI 0 · 블로그 Firestore 0 · gh-pages 0.
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import design_kit as dk  # noqa: E402

KST = datetime.timezone(datetime.timedelta(hours=9))
MIN_SOURCES = 2   # news_render.FACTS_MIN_SOURCES 와 같은 값 — 화면과 저장 규칙을 하나로
DIR_KIND = {"up": "positive", "down": "negative", "neutral": "neutral"}
HEADERS = ("/kr/*\n  Access-Control-Allow-Origin: *\n  Cache-Control: public, max-age=600\n")


def _kst(iso):
    t = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    return (t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)).astimezone(KST)


def _quote(q):
    """확인된 · 이름 있는 발언만 남긴다. 아니면 None — 사실(what)은 그대로."""
    if q and q.get("verified") and not q.get("anonymous") and (q.get("text") or "").strip():
        return {k: q.get(k) or "" for k in ("speaker", "title", "venue", "text")}
    return None


def fact_line(f):
    """화면 한 줄 = what + 확인된 발언 + (출처 기관). news_render._fact_line 과 같은 글자."""
    line = (f.get("what") or "").strip()
    q = f.get("quote")
    if q:
        who = " ".join(x for x in (q.get("speaker"), q.get("title")) if x)
        line += f' "{q["text"]}"' + (f" ({who}" + (f", {q['venue']}" if q.get("venue") else "") + ")" if who else "")
    src = (f.get("origin") or "").strip()
    return line + (f" ({src})" if src and src not in line else "")


def clean_event(e, at):
    """공개해도 되는 칸만 · 조건 넘은 사실만. 사실이 하나도 안 남으면 None."""
    facts = []
    for f in e.get("facts") or []:
        if (f.get("sources") or 0) < MIN_SOURCES or not (f.get("what") or "").strip():
            continue
        g = {k: f.get(k) for k in ("what", "who", "when", "origin", "sources", "numbers", "stocks", "sector", "cat", "direction", "stage")}
        g["quote"] = _quote(f.get("quote"))
        g["line"] = fact_line(g)
        facts.append(g)
    if (e.get("sourceCount") or 0) < MIN_SOURCES or not facts:
        return None
    out = {k: e.get(k) for k in ("event", "cat", "direction", "stage", "sourceCount", "outletCount", "stocks", "sector", "numbers")}
    out.update(tag=dk.ISSUE_KO.get(e.get("cat"), "그 밖"), dir=DIR_KIND.get(e.get("direction"), "neutral"), at=at, facts=facts)
    return out


def runs_by_day(fact_docs):
    """facts 문서(part 여럿) → {날짜: 그날 가장 늦은 실행의 문서들}. ⑤ 가 지난 36시간을 다시 묶으므로 같은 날 실행끼리 합치지 않는다(사건 이름이 실행마다 달라 겹침)."""
    runs = {}
    for d in fact_docs:
        runs.setdefault(str(d.get("run")), []).append(d)
    days = {}
    for run, ds in runs.items():
        at = max(str(x.get("createdAt") or "") for x in ds)
        day = _kst(at).strftime("%Y-%m-%d")
        if day not in days or at > days[day][0]:
            days[day] = (at, run, sorted(ds, key=lambda x: x.get("part") or 1))
    return days


def day_file(day, at, run, docs, head_docs):
    seen, evs = set(), []
    for d in docs:
        for e in d.get("events") or []:
            if e.get("event") in seen:
                continue
            c = clean_event(e, at)
            if c:
                seen.add(e.get("event"))
                evs.append(c)
    evs.sort(key=lambda e: -(e.get("sourceCount") or 0))   # 많이 보도된 순
    urls, heads = set(), []
    for h in head_docs:
        for it in h.get("items") or []:
            u, t = it.get("url"), it.get("publishedAt") or it.get("foundAt") or ""
            if u and u not in urls and t.startswith(day):
                urls.add(u)
                heads.append({k: it.get(k) for k in ("event", "title", "outlet", "url", "cat", "stocks", "publishedAt", "foundAt")})
    heads.sort(key=lambda x: x.get("publishedAt") or x.get("foundAt") or "", reverse=True)
    # facts_section(fact_docs, head_docs, day) 에 그대로 넣을 수 있는 꼴 — facts = 문서 하나, headlines = 문서 하나
    return {"version": 1, "day": day, "run": run, "at": at,
            "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "count": len(evs), "headlineCount": len(heads),
            "facts": [{"run": run, "createdAt": at, "events": evs}],
            "headlines": [{"createdAt": at, "items": heads}]}


def write_store(out, fact_docs, head_docs):
    fdir = os.path.join(out, "kr", "facts")
    os.makedirs(fdir, exist_ok=True)
    days = runs_by_day(fact_docs)
    for day, (at, run, docs) in sorted(days.items()):
        with open(os.path.join(fdir, f"{day}.json"), "w", encoding="utf-8") as f:
            json.dump(day_file(day, at, run, docs, head_docs), f, ensure_ascii=False)
    # 목록 · 최신 = 폴더에 있는 날짜 파일 전부(지난 실행이 남긴 것 포함)로 다시
    index = []
    for name in sorted(os.listdir(fdir)):
        if len(name) == 15 and name.endswith(".json") and name[:4].isdigit():
            with open(os.path.join(fdir, name), encoding="utf-8") as f:
                d = json.load(f)
            index.append({"day": d["day"], "run": d["run"], "at": d["at"], "count": d["count"], "headlineCount": d["headlineCount"]})
    index.sort(key=lambda x: x["day"], reverse=True)
    if index:
        with open(os.path.join(fdir, f'{index[0]["day"]}.json'), encoding="utf-8") as f:
            latest = f.read()
        with open(os.path.join(fdir, "latest.json"), "w", encoding="utf-8") as f:
            f.write(latest)
    with open(os.path.join(fdir, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"days": index}, f, ensure_ascii=False)
    with open(os.path.join(out, "_headers"), "w", encoding="utf-8") as f:
        f.write(HEADERS)
    return days, index


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--gcloud", metavar="ACCOUNT")
    ap.add_argument("--samples", action="store_true", help="samples/facts_blog.json · samples/headlines.json 으로만")
    a = ap.parse_args()
    if a.samples:
        sd = os.path.join(HERE, "samples")
        fact_docs = json.load(open(os.path.join(sd, "facts_blog.json"), encoding="utf-8"))
        head_docs = json.load(open(os.path.join(sd, "headlines.json"), encoding="utf-8"))
    else:
        import fetch_samples as F
        c = F.gcloud_token(a.gcloud) if a.gcloud else F.creds()
        fact_docs, head_docs = F.docs(c, "facts"), F.docs(c, "headlines")
    days, index = write_store(a.out, fact_docs, head_docs)
    print(f"facts 문서 {len(fact_docs)}개 · headlines 문서 {len(head_docs)}개 → 이번에 쓴 날 {sorted(days)}")
    for x in index[:5]:
        print(f'  {x["day"]} 실행 {x["run"]} · 사건 {x["count"]} · 기사 제목 {x["headlineCount"]}')
    if not fact_docs:
        print("::warning::facts 문서 0 — 수집기 정기 실행 확인")


if __name__ == "__main__":
    main()
