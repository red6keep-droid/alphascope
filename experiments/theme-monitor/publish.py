"""테마 고정 페이지 게시 — 없으면 만들고(영문 제목으로 주소를 정한 뒤 한글 제목으로), 있으면 바뀐 것만 갱신 (doc/기획/테마-모니터-기획.md 7절 3단계).

    python experiments/theme-monitor/publish.py          # output/<slug>.html 을 게시
    python experiments/theme-monitor/publish.py --dry    # 무엇을 만들고 / 갱신할지만

종목 페이지 게시(stock-radar/publish_pages.py)와 같은 규칙 · 같은 함수: 429 백오프, 호출 사이 4초, 본문 해시가 같으면 PUT 안 함,
429 가 백오프 끝까지 나면 나머지 쓰기 중단 (운영지침 2-2). 제목에 기준 날짜가 있어 날짜가 바뀌면 갱신된다.
"""

import hashlib
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "daily-report"))
sys.path.insert(0, os.path.join(_HERE, "..", "stock-radar"))

import publish_blogger  # noqa: E402
import publish_pages as PP  # noqa: E402
import themes as T  # noqa: E402
import notify  # noqa: E402

OUT = os.path.join(_HERE, "output")
HASHES = os.path.join(_HERE, "data", "page_hashes.json")     # nvda-state 의 themes/ 에 보관 (워크플로)


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def publish(dry=False):
    import requests

    analysis = _load(os.path.join(OUT, "themes_analysis.json"))
    if not analysis:
        print("[theme-pages] themes_analysis.json 없음 — main.py 먼저")
        return False
    import theme_render as TR
    blog_url = os.environ.get("BLOG_URL", publish_blogger.DEFAULT_BLOG_URL)
    creds = publish_blogger._credentials()
    blog_id = publish_blogger._blog_id(creds, blog_url)
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    base = f"{publish_blogger.BLOGGER_API}/blogs/{blog_id}/pages"
    items, token = [], None
    while True:   # 페이지 목록은 다음 쪽까지 다 읽는다 (publish_pages 와 같은 이유)
        params = {"fetchBodies": "false", "status": ["live", "draft"], "maxResults": 50}
        if token:
            params["pageToken"] = token
        j = PP._call(requests, "get", base, params=params, headers=headers).json()
        items += j.get("items", [])
        token = j.get("nextPageToken")
        if not token:
            break
    by_url = {PP._norm(p.get("url")): p for p in items}
    hashes = _load(HASHES)
    made = updated = unchanged = failed = 0
    for t in T.THEMES:
        path = os.path.join(OUT, f"{t['slug']}.html")
        if not os.path.exists(path):
            print(f"[theme-pages] {t['key']}: 본문 없음 — 건너뜀")
            continue
        with open(path, encoding="utf-8") as f:
            content = f.read()
        title = TR.page_title(t, analysis["day"])
        url = T.page_url(t)
        page = by_url.get(PP._norm(url))
        digest = hashlib.sha1((title + "\n" + content).encode("utf-8")).hexdigest()
        if page and hashes.get(t["key"]) == digest:
            unchanged += 1
            continue
        if dry:
            print(f"[theme-pages] {'갱신' if page else '생성'} {t['key']}: {title} → {url}")
            continue
        try:
            if page:
                r = PP._call(requests, "put", f"{base}/{page['id']}", headers=headers, json={"kind": "blogger#page", "id": page["id"], "title": title, "content": content})
                updated += 1
            else:
                r = PP._call(requests, "post", base, headers=headers, json={"kind": "blogger#page", "title": T.slug_title(t), "content": content})
                new = r.json()
                time.sleep(2)
                r = PP._call(requests, "put", f"{base}/{new['id']}", headers=headers, json={"kind": "blogger#page", "id": new["id"], "title": title, "content": content})
                got = r.json().get("url")
                if PP._norm(got) != PP._norm(url):
                    print(f"::warning::[theme-pages] {t['key']}: 주소가 계획({url})과 다름 → {got}")
                    notify.event("테마 페이지 주소", f"{t['key']} 계획 {url} · 실제 {got} — themes.py slug 를 실제 주소로 고칠 것")
                made += 1
            hashes[t["key"]] = digest
            print(f"[theme-pages] {'갱신' if page else '생성'} {t['key']}: {r.json().get('url')}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"::warning::[theme-pages] {t['key']} 실패: {str(e)[:200]}")
            if getattr(getattr(e, "response", None), "status_code", None) == 429:
                notify.event("블로거 429", f"테마 페이지 {t['key']} — 백오프 후에도 429, 나머지 중단")
                break
        time.sleep(4)
    if not dry:
        os.makedirs(os.path.dirname(HASHES), exist_ok=True)
        with open(HASHES, "w", encoding="utf-8") as f:
            json.dump(hashes, f, ensure_ascii=False, indent=0, sort_keys=True)
    print(f"[theme-pages] 생성 {made} · 갱신 {updated} · 변경 없음 {unchanged} · 실패 {failed}")
    return failed == 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_HERE, "..", "..", ".env"))
    sys.exit(0 if publish(dry="--dry" in sys.argv) else 1)
