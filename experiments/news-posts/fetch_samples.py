"""수집기 블로그 저장소(news-text-blog)에서 목업 재료 받기 — 읽기만 (2026-11-23).

    FIREBASE_SERVICE_ACCOUNT=<블로그 서비스 계정 키 JSON 또는 파일 경로> python experiments/news-posts/fetch_samples.py
    python experiments/news-posts/fetch_samples.py --gcloud <gcloud 로그인 계정>            # 키 없이 그 PC gcloud 토큰으로 (2026-11-23)
    python experiments/news-posts/fetch_samples.py --gcloud <계정> --facts --extra            # 시안용 두 가지 더 (아래)

- 시안용, 수집기 원래 저장소(news-text-collector) 읽기만 — 그 저장소를 읽을 수 있는 gcloud 계정이 필요:
  --facts : 옛 시안 — 사건 묶기 결과(eventsets) 최근 두 실행 → 수집기 코드로 facts 모양 → samples/facts.json
            (블로그 저장소 facts 는 이 옵션 없이도 늘 samples/facts_blog.json 으로 받는다, 2026-11-24)
  --extra : 수집기 posts 중 v2 · 색 강조(==)가 든 글(검사 실패로 블로그에 안 온 글 포함) → samples/posts_extra.json (상세 화면 시안만, 홈 · 목록엔 안 씀)

- 블로그 서비스 계정에 news-text-blog 의 roles/datastore.viewer 가 있다(요청 문서 9절). 쓰기 · 지우기 없음.
- 받는 것: posts 전부(하루 다섯 편 안팎) · headlines 최근 문서(실행당 1개 안팎). 읽기 수 = 문서 수(하루 5만 한도에 비해 작음).
- 저장: samples/posts.json · samples/headlines.json (git 제외 — 제목 묶음에 기사 제목 · 주소가 있다). 키 · 토큰은 출력하지 않는다.
"""
import json
import os
import sys

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

PROJECT = "news-text-blog"
BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "samples")


def gcloud_token(account):
    import shutil
    import subprocess
    import types
    exe = shutil.which("gcloud") or "gcloud"   # 윈도우는 gcloud.cmd 라 이름만으로는 못 찾는다 (2026-11-24)
    tok = subprocess.check_output([exe, "auth", "print-access-token", f"--account={account}"], text=True).strip()
    return types.SimpleNamespace(token=tok)


def creds():
    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "").strip()
    if not raw:
        raise SystemExit("FIREBASE_SERVICE_ACCOUNT 환경 변수가 필요합니다 (블로그 서비스 계정 키 JSON 또는 파일 경로).")
    if not raw.startswith("{") and os.path.exists(raw):
        raw = open(raw, encoding="utf-8").read()
    c = service_account.Credentials.from_service_account_info(json.loads(raw), scopes=["https://www.googleapis.com/auth/datastore"])
    c.refresh(Request())
    return c


def val(v):
    k, x = next(iter(v.items()))
    if k == "mapValue":
        return {a: val(b) for a, b in (x.get("fields") or {}).items()}
    if k == "arrayValue":
        return [val(b) for b in x.get("values") or []]
    if k == "integerValue":
        return int(x)
    if k == "nullValue":
        return None
    return x


def docs(c, col, base=BASE):
    out, tok = [], None
    while True:
        r = requests.get(f"{base}/{col}", headers={"Authorization": f"Bearer {c.token}"},
                         params={"pageSize": 300, **({"pageToken": tok} if tok else {})}, timeout=30)
        if not r.ok:
            raise SystemExit(f"{col} 읽기 실패 {r.status_code}")
        j = r.json()
        out += [dict({a: val(b) for a, b in (d.get("fields") or {}).items()}, id=d["name"].rsplit("/", 1)[1]) for d in j.get("documents") or []]
        tok = j.get("nextPageToken")
        if not tok:
            return out


COLLECTOR = "https://firestore.googleapis.com/v1/projects/news-text-collector/databases/(default)/documents"
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
# 수집기 저장소 자리 — 맥은 옆 폴더 News-text, 회사 윈도우 PC 는 News-text/News-text (2026-11-24). NEWS_TEXT_DIR 로 바꿀 수 있다.
_CANDS = [os.environ.get("NEWS_TEXT_DIR", ""), os.path.join(_ROOT, "News-text"), os.path.join(_ROOT, "News-text", "News-text")]
COLLECT_PY = next((os.path.join(d, "worker", "collect.py") for d in _CANDS if d and os.path.exists(os.path.join(d, "worker", "collect.py"))),
                  os.path.join(_ROOT, "News-text", "worker", "collect.py"))


def _blog_event_fn():
    """수집기 코드의 blog_event(블로그로 넘기는 칸 고르기 · 언론사 칸 빼기)를 그대로 — 블로그가 따로 흉내 내지 않는다."""
    import re
    src = open(COLLECT_PY, encoding="utf-8").read()
    anon = re.search(r"^ANON\s*=.*$", src, re.M).group(0)
    ns = {}
    exec("import re\nfrom collections import Counter\n" + anon + "\n" + src[src.index("def _blog_quote("):src.index("def write_facts(")], ns)
    return ns["blog_event"]


def fetch_facts(c, runs=2):
    """eventsets 최근 runs 실행 → facts 문서 모양 [{run, createdAt, edition, events}]. 옛 실행(R21 · R22 전)은 빠진 칸을 기본값으로 채운다."""
    be = _blog_event_fn()
    sets = sorted(docs(c, "eventsets", COLLECTOR), key=lambda d: str(d.get("createdAt")), reverse=True)[:runs]
    out = []
    for d in sets:
        rows = []
        for e in d.get("events") or []:
            if not e.get("facts"):
                continue
            for k, v in (("sourceCount", 1), ("outletCount", 1), ("single", False), ("numbers", []), ("direction", "neutral"), ("stage", ""), ("cat", "")):
                e.setdefault(k, v)
            for f in e["facts"]:
                for k, v in (("who", ""), ("when", ""), ("numbers", []), ("stocks", []), ("sector", ""), ("cat", ""), ("direction", ""), ("stage", ""), ("origin", "")):
                    f.setdefault(k, v)
                f["numbers"] = [dict({"name": "", "value": "", "unit": "", "kind": "기타"}, **n) for n in f["numbers"]]
            for n in e["numbers"]:
                for k, v in (("sources", 1), ("agreed", True), ("kind", "기타"), ("unit", "")):
                    n.setdefault(k, v)
            rows.append(be(e))
        out.append({"run": d["id"], "part": 1, "parts": 1, "createdAt": str(d.get("createdAt")), "edition": d.get("edition"), "version": 1,
                    "count": len(rows), "copiedDropped": 0, "events": rows, "sample": "eventsets 변환(시안용)"})
    return out


def fetch_extra(c):
    import datetime
    keep = ("title", "summary", "body", "createdAt", "cat", "direction", "stage", "stocks", "sector", "slug", "version")
    out = []
    for x in docs(c, "posts", COLLECTOR):
        if x.get("version") == 2 and "==" in str(x.get("body") or ""):
            y = {k: x.get(k) for k in keep}
            y.update(id=x["id"], stocks=x.get("stocks") or [], status=x.get("status"),
                     date=(datetime.datetime.fromisoformat(str(x["createdAt"]).replace("Z", "+00:00")) + datetime.timedelta(hours=9)).strftime("%Y-%m-%d"))
            out.append(y)
    return out


if __name__ == "__main__":
    import argparse
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--gcloud", metavar="ACCOUNT", help="키 대신 이 gcloud 계정 토큰")
    ap.add_argument("--facts", action="store_true", help="시안: 수집기 eventsets → samples/facts.json")
    ap.add_argument("--extra", action="store_true", help="시안: 색 강조 든 수집기 v2 글 → samples/posts_extra.json")
    a = ap.parse_args()
    c = gcloud_token(a.gcloud) if a.gcloud else creds()
    os.makedirs(OUT, exist_ok=True)
    posts = docs(c, "posts")
    heads = docs(c, "headlines")   # 전부(30일 지나면 수집기가 지움) — 목업은 그중 가장 최근 날짜를 쓴다
    json.dump(posts, open(os.path.join(OUT, "posts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(heads, open(os.path.join(OUT, "headlines.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"posts {len(posts)}편 · headlines 문서 {len(heads)}개 (제목 {sum(len(d.get('items') or []) for d in heads)}건) → samples/")
    fb = docs(c, "facts")   # 블로그 저장소 사건별 사실(R17 ~ R22, 첫 문서 11-24) — 운영 kr_facts_store.py 와 같은 재료 (2026-11-24)
    json.dump(fb, open(os.path.join(OUT, "facts_blog.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"facts 문서 {len(fb)}개 → samples/facts_blog.json")
    if a.facts:
        fx = fetch_facts(c)
        json.dump(fx, open(os.path.join(OUT, "facts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("facts (시안)", [(d["run"], d["edition"], d["count"]) for d in fx])
    if a.extra:
        ex = fetch_extra(c)
        json.dump(ex, open(os.path.join(OUT, "posts_extra.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("색 강조 글 (시안)", [(x["id"], x.get("status")) for x in ex])
