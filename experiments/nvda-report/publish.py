"""별도 글로 Blogger 게시 (기획서 10절). trump-trend publish.py와 같은 규칙 — daily-report의 publish_blogger를 가져다 쓰고,
같은 제목(같은 날짜)의 글이 있으면 다시 올리지 않는다.

    python experiments/nvda-report/publish.py            # dry-run
    python experiments/nvda-report/publish.py --publish  # 실제 게시
    python experiments/nvda-report/publish.py --guide-page   # 고정 페이지 "리포트 읽는 법" 올리기/갱신 (static/reading_guide.html)
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
    existing = publish_blogger.find_post_by_title(title)
    if existing:
        print(f"[publish] 이미 게시됨 — 건너뜀: {existing}")
        return existing
    url = publish_blogger.publish(title, body, labels=report_title.LABELS)
    with open(os.path.join(output_dir, "post_url.txt"), "w", encoding="utf-8") as f:
        f.write(url or "")
    print(f"[publish] 게시: {url}")
    return url


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
    else:
        publish(do_publish="--publish" in sys.argv)
