"""종목 고정 페이지 게시 — 목록 1 + 간단형 상세 (후보 수 − NVDA), 새 페이지는 하루 universe.NEW_PAGES_PER_RUN 개까지 (doc/기획/종목-레이더-기획.md 10-3 · 10-8 1단계, 2026-10-18 사용자 "발행까지").

    python experiments/stock-radar/publish_pages.py            # 실제 게시 (main.py 가 만든 output/*.html)
    python experiments/stock-radar/publish_pages.py --dry      # 무엇을 만들고 / 갱신할지만
    python experiments/stock-radar/publish_pages.py TSLA list  # 일부만

- 주소는 영문: 처음 만들 때 영문 제목(universe.slug_title)으로 만들어 주소를 정하고 바로 한글 제목으로 바꾼다 (10-9 시험 · 엔비디아 읽는 법 페이지와 같은 방법).
- 이미 있는 페이지는 주소(universe.page_url · LIST_URL)로 찾아 본문 · 제목만 바꾼다. 주소는 바뀌지 않는다.
- 리포트형(NVDA) 링크: 목록 페이지의 임시 링크(엔비디아 라벨 목록)를 오늘 엔비디아 글 주소(nvda-report/output/post_url.txt)로 바꾼다. 없으면 라벨 목록 그대로.
- 그래프 PNG 는 먼저 gh-pages 에 올라가 있어야 한다 (워크플로 · 첫 게시는 손으로).
Blogger pages API. 인증은 데일리 publish_blogger 와 같다(BLOGGER_* 환경 변수).
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
import universe as U  # noqa: E402
import notify  # noqa: E402  — 운영 알림 (experiments/notify.py, 2026-10-21)

OUT = os.path.join(BASE, "output")
NVDA_POST_URL = os.path.join(BASE, "..", "nvda-report", "output", "post_url.txt")
# 마지막으로 올린 본문의 해시 — 같으면 PUT 하지 않는다 (2026-10-21, 운영지침 D2-2: 매 실행 전부 PUT → 하루 50회 쓰기, 실행 994초).
# nvda-state 의 radar/ 에 같이 보관한다 (nvda-report.yml)
HASHES = os.path.join(BASE, "data", "page_hashes.json")
PAGES_LIVE = os.path.join(BASE, "data", "pages_live.json")   # 발행된 페이지 키 목록 — home_feed.py 가 읽는다


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


DAILY_LATEST = ""   # 미국 증시 리포트 최신 글 주소 — publish 가 한 번 찾는다 (P144)


def _latest_daily(requests, blog_id, headers):
    """라벨 `데일리 브리핑` 최신 글 주소. 못 찾으면 "" (링크는 라벨 목록 그대로)."""
    try:
        r = requests.get(f"{publish_blogger.BLOGGER_API}/blogs/{blog_id}/posts", params={"labels": "데일리 브리핑", "maxResults": 1, "fetchBodies": "false",
                                                                                         "fetchImages": "false", "orderBy": "published"}, headers=headers, timeout=60)
        r.raise_for_status()
        return ((r.json().get("items") or [{}])[0]).get("url") or ""
    except Exception as e:  # noqa: BLE001
        print(f"[pages] 미국 증시 리포트 최신 글 못 찾음 — 라벨 목록 링크로: {str(e)[:80]}")
        return ""


def _body(path):
    with open(path, encoding="utf-8") as f:
        body = f.read()
    if DAILY_LATEST:   # 일정 탭 `미국 증시 리포트 일정에서 전체 보기` → 최신 글의 일정 탭 (P144)
        body = body.replace(U.DAILY_REPORTS_URL, DAILY_LATEST)
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
    global DAILY_LATEST
    DAILY_LATEST = _latest_daily(requests, blog_id, headers)
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
    hashes = _load_hashes()
    made = updated = failed = waiting = new_tries = unchanged = 0
    stopped = False
    for key, title, slug, url, path in targets(only):
        page = by_url.get(_norm(url))
        if not page and new_tries >= U.NEW_PAGES_PER_RUN:   # 새 페이지는 실행 한 번에 상한까지 — 나머지는 다음 날 (2026-10-20 사용자: "하루에 조금씩")
            waiting += 1
            continue
        content = _body(path)
        digest = _digest(title, content)
        if page and hashes.get(key) == digest:   # 바뀐 것이 없으면 쓰지 않는다 (운영지침 2-2)
            unchanged += 1
            continue
        new_tries += 0 if page else 1   # 만들다 실패한 것도 센다 — 429 가 나는 날 더 밀어붙이지 않게
        if dry:
            print(f"[pages] {'갱신' if page else '생성'} {key}: {title} → {url}")
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
                    print(f"::warning::[pages] {key}: 주소가 계획({url})과 다름 → {got}")
                made += 1
            hashes[key] = digest
            print(f"[pages] {'갱신' if page else '생성'} {key}: {r.json().get('url')}")
        except Exception as e:  # noqa: BLE001 — 한 페이지 실패가 나머지를 막지 않게 (429 끝까지 실패는 예외 — 아래)
            failed += 1
            print(f"::warning::[pages] {key} 실패: {str(e)[:200]}")
            if getattr(getattr(e, "response", None), "status_code", None) == 429:
                # 백오프(20·45·90·180초)를 다 쓰고도 429 — 더 밀어붙이면 스팸 신호. 이 실행의 나머지 쓰기는 멈춘다 (운영지침 2-2 · D2-3, 2026-10-21)
                notify.event("블로거 429", f"고정 페이지 {key} — 백오프 후에도 429, 이 실행의 나머지 쓰기 중단")
                stopped = True
                break
        time.sleep(4)   # API 버스트를 피한다 (1초 간격은 6번째부터 429)
    if not dry:
        _save_hashes(hashes)
        # 실제로 있는 페이지 목록 — 홈 카드(home_feed.py)가 없는 페이지로 링크하지 않게 (2026-10-21)
        live = sorted({key for key, *_r, url, _p in targets() if _norm(url) in by_url} | {k for k in hashes})
        with open(PAGES_LIVE, "w", encoding="utf-8") as f:
            json.dump(live, f, ensure_ascii=False)
    print(f"[pages] 생성 {made} · 갱신 {updated} · 변경 없음 {unchanged} · 실패 {failed}"
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
