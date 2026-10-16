"""별도 글로 Blogger 게시 (기획서 10절). trump-trend publish.py와 같은 규칙 — daily-report의 publish_blogger를 가져다 쓰고,
같은 제목(같은 날짜)의 글이 있으면 **본문을 갱신한다** (2026-10-11: 디자인·코드가 바뀐 날 같은 글을 새 본문으로 다시 올릴 수 있게. 주소는 그대로).

    python experiments/nvda-report/publish.py            # dry-run
    python experiments/nvda-report/publish.py --publish  # 실제 게시
    python experiments/nvda-report/publish.py --guide-page   # 고정 페이지 "리포트 읽는 법" 올리기/갱신 (static/reading_guide.html)
    python experiments/nvda-report/publish.py --draft        # 비공개 초안 "[초안] …" 올리기/갱신 — 폰에서 Blogger 미리보기로 확인 (2026-10-16, 공개 테스트 글 금지)
"""

import os
import sys

import config
import report_title

DAILY_REPORT_DIR = os.path.join(config.BASE_DIR, "..", "daily-report")
sys.path.append(os.path.abspath(DAILY_REPORT_DIR))   # 뒤에 붙인다 — 앞에 넣으면 그쪽 render_html·report_title이 이쪽을 가린다
import publish_blogger  # noqa: E402


def publish(output_dir=None, do_publish=False):
    output_dir = output_dir or config.OUTPUT_DIR
    body_path = os.path.join(output_dir, "nvda_report_body.html")
    if not os.path.exists(body_path):
        raise FileNotFoundError(f"본문 없음: {body_path} — render_html 먼저")
    with open(body_path, "r", encoding="utf-8") as f:
        body = f.read()
    with open(os.path.join(output_dir, "title.txt"), "r", encoding="utf-8") as f:
        title = f.read().strip() or report_title.post_title(report_title.today_kst())
    if not do_publish:
        print(f"[publish dry-run] 제목: {title} · 본문 {len(body):,}자 · 라벨 {report_title.LABELS}")
        return None
    existing = find_post_id(title)
    if existing:
        url = update_post(existing["id"], title, body, report_title.LABELS)
        print(f"[publish] 같은 제목이 있어 본문 갱신: {url}")
    else:
        url = publish_blogger.publish(title, body, labels=report_title.LABELS)
    with open(os.path.join(output_dir, "post_url.txt"), "w", encoding="utf-8") as f:
        f.write(url or "")
    print(f"[publish] 게시: {url}")
    return url


def _api(blog_url=None):
    import requests
    blog_url = blog_url or os.environ.get("BLOG_URL", publish_blogger.DEFAULT_BLOG_URL)
    creds = publish_blogger._credentials()
    blog_id = publish_blogger._blog_id(creds, blog_url)
    return requests, f"{publish_blogger.BLOGGER_API}/blogs/{blog_id}", {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def find_post_id(title, max_results=15):
    """같은 제목의 글 — {"id", "url"} 또는 None (최근 max_results건 안에서)."""
    requests, base, headers = _api()
    r = requests.get(f"{base}/posts", params={"maxResults": max_results, "fetchBodies": "false", "fetchImages": "false"}, headers=headers, timeout=30)
    r.raise_for_status()
    for p in r.json().get("items", []):
        if str(p.get("title", "")).strip() == title.strip():
            return {"id": p["id"], "url": p.get("url")}
    return None


def update_post(post_id, title, content, labels):
    """기존 글의 본문·라벨을 바꾼다 (posts.update). 주소·게시 시각은 그대로."""
    requests, base, headers = _api()
    r = requests.put(f"{base}/posts/{post_id}", headers=headers, json={"kind": "blogger#post", "id": post_id, "title": title, "content": content, "labels": labels}, timeout=60)
    r.raise_for_status()
    return r.json().get("url")


def publish_draft(output_dir=None):
    """같은 본문을 비공개 초안으로 — 독자 · 검색엔진에 안 보이고 글 수에 들지 않는다. 제목 앞 `[초안]`, 라벨 없음. 같은 초안이 있으면 갱신.
    확인: 폰에서 blogger.com 에 로그인 → 글 목록 → 이 초안 → 미리보기 (실제 테마로 보인다)."""
    output_dir = output_dir or config.OUTPUT_DIR
    with open(os.path.join(output_dir, "nvda_report_body.html"), "r", encoding="utf-8") as f:
        body = f.read()
    with open(os.path.join(output_dir, "title.txt"), "r", encoding="utf-8") as f:
        title = "[초안] " + (f.read().strip() or report_title.post_title(report_title.today_kst()))
    requests, base, headers = _api()
    r = requests.get(f"{base}/posts", params={"status": "draft", "maxResults": 20, "fetchBodies": "false"}, headers=headers, timeout=30)
    r.raise_for_status()
    found = next((p for p in r.json().get("items", []) if str(p.get("title", "")).strip() == title), None)
    if found:
        r = requests.put(f"{base}/posts/{found['id']}", headers=headers, json={"kind": "blogger#post", "id": found["id"], "title": title, "content": body}, timeout=60)
        r.raise_for_status()
        print(f"[draft] 초안 갱신: {title} (id {found['id']})")
    else:
        r = requests.post(f"{base}/posts", params={"isDraft": "true"}, headers=headers, json={"kind": "blogger#post", "title": title, "content": body}, timeout=60)
        r.raise_for_status()
        print(f"[draft] 초안 생성: {title} (id {r.json().get('id')})")
    print("[draft] 폰에서 blogger.com 로그인 → 글 → 초안 → 미리보기")


GUIDE_TITLE = "리포트 읽는 법"
GUIDE_PATH = os.path.join(config.STATIC_DIR, "reading_guide.html")


def publish_guide_page(blog_url=None):
    """고정 페이지 "리포트 읽는 법" — 같은 제목의 페이지가 있으면 본문을 갱신, 없으면 새로 만든다 (가이드라인 3-4, 2026-10-11).
    Blogger pages API (posts 가 아니라 pages). 주소를 돌려주므로 config.GUIDE_URL 에 적는다."""
    import requests
    with open(GUIDE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    blog_url = blog_url or os.environ.get("BLOG_URL", publish_blogger.DEFAULT_BLOG_URL)
    creds = publish_blogger._credentials()
    blog_id = publish_blogger._blog_id(creds, blog_url)
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    base = f"{publish_blogger.BLOGGER_API}/blogs/{blog_id}/pages"
    r = requests.get(base, params={"fetchBodies": "false"}, headers=headers, timeout=30)
    r.raise_for_status()
    existing = next((p for p in r.json().get("items", []) if p.get("title") == GUIDE_TITLE), None)
    payload = {"kind": "blogger#page", "title": GUIDE_TITLE, "content": content}
    if existing:
        r = requests.put(f"{base}/{existing['id']}", headers=headers, json=payload, timeout=30)
    else:
        r = requests.post(base, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    page = r.json()
    print(f"[guide-page] {'갱신' if existing else '생성'}: {page.get('url')}")
    return page.get("url")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    if "--guide-page" in sys.argv:
        publish_guide_page()
    elif "--draft" in sys.argv:
        publish_draft()
    else:
        publish(do_publish="--publish" in sys.argv)
