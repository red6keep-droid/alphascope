"""수집기 블로그 저장소(news-text-blog)에서 목업 재료 받기 — 읽기만 (2026-11-23).

    FIREBASE_SERVICE_ACCOUNT=<블로그 서비스 계정 키 JSON 또는 파일 경로> python experiments/news-posts/fetch_samples.py

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


def docs(c, col):
    out, tok = [], None
    while True:
        r = requests.get(f"{BASE}/{col}", headers={"Authorization": f"Bearer {c.token}"},
                         params={"pageSize": 300, **({"pageToken": tok} if tok else {})}, timeout=30)
        if not r.ok:
            raise SystemExit(f"{col} 읽기 실패 {r.status_code}")
        j = r.json()
        out += [dict({a: val(b) for a, b in (d.get("fields") or {}).items()}, id=d["name"].rsplit("/", 1)[1]) for d in j.get("documents") or []]
        tok = j.get("nextPageToken")
        if not tok:
            return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    c = creds()
    os.makedirs(OUT, exist_ok=True)
    posts = docs(c, "posts")
    heads = docs(c, "headlines")   # 전부(30일 지나면 수집기가 지움) — 목업은 그중 가장 최근 날짜를 쓴다
    json.dump(posts, open(os.path.join(OUT, "posts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(heads, open(os.path.join(OUT, "headlines.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"posts {len(posts)}편 · headlines 문서 {len(heads)}개 (제목 {sum(len(d.get('items') or []) for d in heads)}건) → samples/")
