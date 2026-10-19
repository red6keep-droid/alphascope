"""시총 TOP 10 고정 페이지 게시 — 목록 1 + 간단형 상세 19 (doc/종목-레이더-기획.md 10-3 · 10-8 1단계, 2026-10-18 사용자 "발행까지").

    python experiments/stock-radar/publish_pages.py            # 실제 게시 (main.py 가 만든 output/*.html)
    python experiments/stock-radar/publish_pages.py --dry      # 무엇을 만들고 / 갱신할지만
    python experiments/stock-radar/publish_pages.py TSLA list  # 일부만

- 주소는 영문: 처음 만들 때 영문 제목(universe.slug_title)으로 만들어 주소를 정하고 바로 한글 제목으로 바꾼다 (10-9 시험 · 엔비디아 읽는 법 페이지와 같은 방법).
- 이미 있는 페이지는 주소(universe.page_url · LIST_URL)로 찾아 본문 · 제목만 바꾼다. 주소는 바뀌지 않는다.
- 리포트형(NVDA) 링크: 목록 페이지의 임시 링크(엔비디아 라벨 목록)를 오늘 엔비디아 글 주소(nvda-report/output/post_url.txt)로 바꾼다. 없으면 라벨 목록 그대로.
- 그래프 PNG 는 먼저 gh-pages 에 올라가 있어야 한다 (워크플로 · 첫 게시는 손으로).
Blogger pages API. 인증은 데일리 publish_blogger 와 같다(BLOGGER_* 환경 변수).
"""

import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "daily-report"))
import publish_blogger  # noqa: E402
import universe as U  # noqa: E402

OUT = os.path.join(BASE, "output")
NVDA_POST_URL = os.path.join(BASE, "..", "nvda-report", "output", "post_url.txt")


def _norm(u):
    return str(u or "").replace("http://", "https://").rstrip("/")


def targets(only=None):
    """(키, 한글 제목, 영문 제목, 주소, 본문 파일)"""
    rows = [("list", U.LIST_TITLE, U.LIST_SLUG_TITLE, U.LIST_URL)]
    rows += [(s, U.page_title(s), U.slug_title(s), U.page_url(s)) for s, *_ in U.CANDIDATES if s not in U.REPORT_TYPE]
    out = []
    for key, title, slug, url in rows:
        if only and key not in only:
            continue
        path = os.path.join(OUT, f"{key}.html")
        if os.path.exists(path):
            out.append((key, title, slug, url, path))
        else:
            print(f"[pages] {key}: 본문 없음 ({path}) — 건너뜀")
    return out


def _body(path):
    with open(path, encoding="utf-8") as f:
        body = f.read()
    if os.path.exists(NVDA_POST_URL):
        url = open(NVDA_POST_URL, encoding="utf-8").read().strip()
        if url:
            body = body.replace(U.NVDA_REPORTS_URL, url)
    return body


def _call(requests, method, url, **kw):
    """429(요청 제한)면 기다렸다 다시 — 처음 20개를 만들 때 10개가 429 로 실패했다 (2026-10-18)."""
    for wait in (0, 20, 45, 90, 180):
        if wait:
            print(f"[pages] 429 — {wait}초 뒤 다시")
            time.sleep(wait)
        r = getattr(requests, method)(url, timeout=60, **kw)
        if r.status_code != 429:
            r.raise_for_status()
            return r
    r.raise_for_status()
    return r


def publish(only=None, dry=False):
    import requests

    blog_url = os.environ.get("BLOG_URL", publish_blogger.DEFAULT_BLOG_URL)
    creds = publish_blogger._credentials()
    blog_id = publish_blogger._blog_id(creds, blog_url)
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    base = f"{publish_blogger.BLOGGER_API}/blogs/{blog_id}/pages"
    # 페이지 목록은 한 번에 10개씩 온다 — 다음 쪽(nextPageToken)까지 다 읽는다.
    # 첫 쪽만 읽어 이미 있는 10개를 "없다"고 보고 _숫자 주소의 중복 페이지 10개를 만든 적이 있다 (2026-10-18 CI 첫 실행)
    items, token = [], None
    while True:
        params = {"fetchBodies": "false", "status": ["live", "draft"], "maxResults": 50}
        if token:
            params["pageToken"] = token
        r = _call(requests, "get", base, params=params, headers=headers)
        j = r.json()
        items += j.get("items", [])
        token = j.get("nextPageToken")
        if not token:
            break
    by_url = {_norm(p.get("url")): p for p in items}
    made = updated = failed = 0
    for key, title, slug, url, path in targets(only):
        page = by_url.get(_norm(url))
        if dry:
            print(f"[pages] {'갱신' if page else '생성'} {key}: {title} → {url}")
            continue
        content = _body(path)
        try:
            if page:
                r = _call(requests, "put", f"{base}/{page['id']}", headers=headers, json={"kind": "blogger#page", "id": page["id"], "title": title, "content": content})
                updated += 1
            else:
                r = _call(requests, "post", base, headers=headers, json={"kind": "blogger#page", "title": slug, "content": content})
                new = r.json()
                time.sleep(2)
                r = _call(requests, "put", f"{base}/{new['id']}", headers=headers, json={"kind": "blogger#page", "id": new["id"], "title": title, "content": content})
                got = r.json().get("url")
                if _norm(got) != _norm(url):
                    print(f"::warning::[pages] {key}: 주소가 계획({url})과 다름 → {got}")
                made += 1
            print(f"[pages] {'갱신' if page else '생성'} {key}: {r.json().get('url')}")
        except Exception as e:  # noqa: BLE001 — 한 페이지 실패가 나머지를 막지 않게
            failed += 1
            print(f"::warning::[pages] {key} 실패: {str(e)[:200]}")
        time.sleep(4)   # API 버스트를 피한다 (1초 간격은 6번째부터 429)
    print(f"[pages] 생성 {made} · 갱신 {updated} · 실패 {failed}")
    return failed == 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv

    load_dotenv(os.path.join(BASE, "..", "..", ".env"))
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ok = publish(only=set(args) or None, dry="--dry" in sys.argv)
    sys.exit(0 if ok else 1)
