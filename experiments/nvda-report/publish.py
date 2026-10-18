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
    day = report_title.date_of(title) or report_title.today_kst()
    existing = find_post_id(report_title.match_titles(day) + [title])   # 옛 제목(줄표) · 영문 제목으로 남은 그날 글도 같은 글 (2026-10-18)
    if existing:
        url = update_post(existing["id"], title, publish_blogger.with_related(body, report_title.LABELS, report_title.match_titles(day) + [title]), report_title.LABELS)
        print(f"[publish] 같은 제목이 있어 본문 갱신: {url}")
    else:
        url = publish_blogger.publish(title, body, labels=report_title.LABELS, slug_title=report_title.slug_title(day))   # 영문 주소
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
        if str(p.get("title", "")).strip() in {t.strip() for t in ([title] if isinstance(title, str) else title)}:   # 목록 = 그날 제목들
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
    # Blogger 미리보기는 테마 JS(접기 · 탭)를 돌리지 않아 펼침 안 내용을 볼 수 없다 (2026-10-16 사용자) → 초안은 모든 접기를 연 채로
    body = body.replace('<details data-acc="1">', '<details data-acc="1" open>').replace('<details data-fold="1"', '<details open')   # data-fold 를 떼서 테마 JS(펼친 내용을 버튼 위로 옮겨 숨긴다)가 건드리지 않게 — 2026-10-17 사용자: 초안에서 차트 지표 보기가 감춰져 확인이 안 된다
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
GUIDE_SLUG_TITLE = "nvda report guide"   # 영문 주소 /p/nvda-report-guide.html (검색 노출, 2026-10-18 — 처음 만들 때만 이 제목, 바로 한글로)
GUIDE_OLD_URL = "https://alpha-scope.blogspot.com/p/blog-page.html"   # 2026-10-11 한글 제목으로 만든 옛 주소 — 옮김 안내만 남긴다
GUIDE_PATH = os.path.join(config.STATIC_DIR, "reading_guide.html")


def publish_guide_page(blog_url=None):
    """고정 페이지 "리포트 읽는 법" — config.GUIDE_URL 의 페이지가 있으면 본문을 갱신, 없으면 영문 제목으로 만든 뒤 한글 제목으로 바꾼다 (가이드라인 3-4 · 10-5).
    옛 주소(GUIDE_OLD_URL) 페이지는 지우지 않고 새 주소로 가는 안내로 바꾼다 — 이미 발행된 글의 꼬리가 옛 주소를 가리킨다.
    Blogger pages API (posts 가 아니라 pages)."""
    import html as _h
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
    pages = r.json().get("items", [])
    norm = lambda u: str(u or "").replace("http://", "https://").rstrip("/")   # noqa: E731
    existing = next((p for p in pages if norm(p.get("url")) == norm(config.GUIDE_URL)), None)
    if existing:
        r = requests.put(f"{base}/{existing['id']}", headers=headers, json={"kind": "blogger#page", "id": existing["id"], "title": GUIDE_TITLE, "content": content}, timeout=30)
        r.raise_for_status()
        page = r.json()
    else:
        r = requests.post(base, headers=headers, json={"kind": "blogger#page", "title": GUIDE_SLUG_TITLE, "content": content}, timeout=30)
        r.raise_for_status()
        page = r.json()
        r = requests.put(f"{base}/{page['id']}", headers=headers, json={"kind": "blogger#page", "id": page["id"], "title": GUIDE_TITLE, "content": content}, timeout=30)
        r.raise_for_status()
        page = r.json()
        if norm(page.get("url")) != norm(config.GUIDE_URL):
            print(f"[guide-page] 주의: 새 주소 {page.get('url')} 가 config.GUIDE_URL({config.GUIDE_URL}) 과 다르다 — config 를 맞출 것")
    old = next((p for p in pages if norm(p.get("url")) == norm(GUIDE_OLD_URL)), None)
    if old and norm(page.get("url")) != norm(GUIDE_OLD_URL):
        new_url = _h.escape(page.get("url") or config.GUIDE_URL)
        moved = (f'<div data-design="2" style="font-family:-apple-system,\'Apple SD Gothic Neo\',\'Malgun Gothic\',sans-serif;font-size:19px;line-height:34px;color:#333;">'
                 f'<p>리포트 읽는 법 페이지는 새 주소로 옮겼습니다.</p><p><a href="{new_url}" style="color:#1a73e8;">리포트 읽는 법 바로 가기</a></p></div>')
        r = requests.put(f"{base}/{old['id']}", headers=headers, json={"kind": "blogger#page", "id": old["id"], "title": "리포트 읽는 법 (옮김)", "content": moved}, timeout=30)
        r.raise_for_status()
        print(f"[guide-page] 옛 주소는 옮김 안내로: {old.get('url')}")
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
