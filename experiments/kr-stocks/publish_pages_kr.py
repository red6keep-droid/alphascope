"""한국 종목 고정 페이지 게시 — 목록 1 + 종목 35 (기획 11-4). 미국 stock-radar/publish_pages.py 와 같은 규칙:
새 페이지는 실행 한 번에 NEW_PAGES_PER_RUN 개까지, 호출 사이 4초, 429 백오프(20 · 45 · 90 · 180초) 뒤에도 429 면 그 실행의 나머지 쓰기 중단 + 알림,
본문 해시가 같으면 PUT 하지 않는다 (운영지침 2-2 · D2-2 · D2-3).

    python experiments/kr-stocks/publish_pages_kr.py            # 실제 게시 (main_kr.py 가 만든 output/*.html)
    python experiments/kr-stocks/publish_pages_kr.py --dry      # 무엇을 만들고 / 갱신할지만
    python experiments/kr-stocks/publish_pages_kr.py 005930 list   # 일부만 (키 = 종목 코드 · list)

- 주소는 영문: 처음 만들 때 영문 제목(universe_kr.slug_title)으로 만들어 주소를 정하고 바로 한글 제목으로 바꾼다.
- 이미 있는 페이지는 주소로 찾아 본문 · 제목만 바꾼다.
- 그래프 PNG 는 먼저 kr-images 브랜치에 올라가 있어야 한다 (워크플로).
"""
import hashlib
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "daily-report"))
sys.path.insert(0, os.path.join(BASE, ".."))
import publish_blogger  # noqa: E402
import universe_kr as U  # noqa: E402
import notify  # noqa: E402

OUT = os.path.join(BASE, "output")
HASHES = os.path.join(BASE, "data", "page_hashes.json")      # kr-state 브랜치에 보관 (kr-stocks.yml)
PAGES_LIVE = os.path.join(BASE, "data", "pages_live.json")   # 발행된 페이지 키 — home_feed_kr.py 가 읽는다


def _load_hashes():
    try:
        with open(HASHES, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_hashes(h):
    os.makedirs(os.path.dirname(HASHES), exist_ok=True)
    with open(HASHES, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=0, sort_keys=True)


def _digest(title, content):
    return hashlib.sha1((title + "\n" + content).encode("utf-8")).hexdigest()


def _norm(u):
    return str(u or "").replace("http://", "https://").rstrip("/")


def targets(only=None):
    """(키, 한글 제목, 영문 제목, 주소, 본문 파일). 키 = 'list' · 종목 코드."""
    rows = [("list", U.LIST_TITLE, U.LIST_SLUG_TITLE, U.LIST_URL)]
    rows += [(U.code(s), U.page_title(s), U.slug_title(s), U.page_url(s)) for s, *_ in U.CANDIDATES]
    out = []
    for key, title, slug, url in rows:
        if only and key not in only:
            continue
        path = os.path.join(OUT, f"{key}.html")
        if os.path.exists(path):
            out.append((key, title, slug, url, path))
        else:
            print(f"[kr-pages] {key}: 본문 없음 ({path}) — 건너뜀")
    return out


def _call(requests, method, url, **kw):
    for wait in (0, 20, 45, 90, 180):
        if wait:
            print(f"[kr-pages] 429 — {wait}초 뒤 다시")
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
    items, token = [], None
    while True:   # 페이지 목록은 쪽 단위 — 끝까지 읽는다 (첫 쪽만 읽어 중복을 만든 적이 있다, 2026-10-18)
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
    hashes = _load_hashes()
    made = updated = failed = waiting = new_tries = unchanged = 0
    stopped = False
    for key, title, slug, url, path in targets(only):
        page = by_url.get(_norm(url))
        if not page and new_tries >= U.NEW_PAGES_PER_RUN:
            waiting += 1
            continue
        with open(path, encoding="utf-8") as f:
            content = f.read()
        digest = _digest(title, content)
        if page and hashes.get(key) == digest:
            unchanged += 1
            continue
        new_tries += 0 if page else 1
        if dry:
            print(f"[kr-pages] {'갱신' if page else '생성'} {key}: {title} → {url}")
            continue
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
                    print(f"::warning::[kr-pages] {key}: 주소가 계획({url})과 다름 → {got}")
                made += 1
            hashes[key] = digest
            print(f"[kr-pages] {'갱신' if page else '생성'} {key}: {r.json().get('url')}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"::warning::[kr-pages] {key} 실패: {str(e)[:200]}")
            if getattr(getattr(e, "response", None), "status_code", None) == 429:
                notify.event("블로거 429", f"한국 고정 페이지 {key} — 백오프 후에도 429, 이 실행의 나머지 쓰기 중단")
                stopped = True
                break
        time.sleep(4)
    if not dry:
        _save_hashes(hashes)
        live = sorted({key for key, *_r, url, _p in targets() if _norm(url) in by_url} | {k for k in hashes})
        os.makedirs(os.path.dirname(PAGES_LIVE), exist_ok=True)
        with open(PAGES_LIVE, "w", encoding="utf-8") as f:
            json.dump(live, f, ensure_ascii=False)
    print(f"[kr-pages] 생성 {made} · 갱신 {updated} · 변경 없음 {unchanged} · 실패 {failed}"
          + (f" · 다음 실행으로 미룸 {waiting} (하루 새 페이지 {U.NEW_PAGES_PER_RUN}개까지)" if waiting else "")
          + (" · 429 로 중단" if stopped else ""))
    return failed == 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv

    load_dotenv(os.path.join(BASE, "..", "..", ".env"))
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ok = publish(only=set(args) or None, dry="--dry" in sys.argv)
    sys.exit(0 if ok else 1)
