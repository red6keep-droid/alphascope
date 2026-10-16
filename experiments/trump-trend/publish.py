"""별도 글로 Blogger 게시 (기획서 13절 ⑦ — 결정: 별도 글 시리즈).

기존 experiments/daily-report/publish_blogger.py(OAuth refresh token 방식)를 그대로 가져다 쓴다.
같은 제목(같은 날짜)의 글이 이미 있으면 다시 올리지 않는다 — cron 재실행·수동 실행 중복 방지.

    python experiments/trump-trend/publish.py            # dry-run: 제목·본문 크기만 출력
    python experiments/trump-trend/publish.py --publish  # 실제 게시
"""

import os
import sys

import config
import report_title

DAILY_REPORT_DIR = os.path.join(config.BASE_DIR, "..", "daily-report")
# 뒤에 붙인다 — 앞에 넣으면 daily-report의 render_html.py·report_title.py가 이쪽 모듈을 가린다.
sys.path.append(os.path.abspath(DAILY_REPORT_DIR))
import publish_blogger  # noqa: E402  (daily-report 모듈)


def event_count(output_dir=None):
    """최근 24시간 이벤트 수 (aggregate 가 쓴 trump_analysis.json). 파일이 없으면 -1."""
    import json
    path = os.path.join(output_dir or config.OUTPUT_DIR, "trump_analysis.json")
    if not os.path.exists(path):
        return -1
    with open(path, "r", encoding="utf-8") as f:
        return len(json.load(f).get("recent_events") or [])


def publish(output_dir=None, do_publish=False):
    output_dir = output_dir or config.OUTPUT_DIR
    # 이벤트 0건인 날은 게시하지 않는다 (2026-10-16 사용자: 발언 없는 날은 통계 반복뿐, 매일 볼 이유가 없다 — 인물-발언-레이더-기획 5절).
    # 렌더 · 상태 저장은 그대로. 다음 날 check_published 는 오늘 글이 없으니 정상 실행된다
    n = event_count(output_dir)
    if n == 0:
        print("[publish] 최근 24시간 이벤트 0건 — 오늘은 게시하지 않는다")
        return None
    body_path = os.path.join(output_dir, "trump_report_body.html")
    if not os.path.exists(body_path):
        raise FileNotFoundError(f"본문 없음: {body_path} — render_html 먼저")
    with open(body_path, "r", encoding="utf-8") as f:
        body = f.read()
    title = report_title.post_title(report_title.today_kst())

    if not do_publish:
        print(f"[publish dry-run] 제목: {title} · 본문 {len(body):,}자 · 라벨 {report_title.LABELS}")
        return None

    existing = find_post_id(title)
    if existing:   # 같은 제목이면 본문 갱신 — 디자인·코드가 바뀐 날 새 본문으로 다시 올린다 (2026-10-11). 주소는 그대로
        url = update_post(existing["id"], title, body, report_title.LABELS)
        print(f"[publish] 같은 제목이 있어 본문 갱신: {url}")
    else:
        url = publish_blogger.publish(title, body, labels=report_title.LABELS)
    with open(os.path.join(output_dir, "post_url.txt"), "w", encoding="utf-8") as f:
        f.write(url or "")
    return url


def _api(blog_url=None):
    import requests
    blog_url = blog_url or os.environ.get("BLOG_URL", publish_blogger.DEFAULT_BLOG_URL)
    creds = publish_blogger._credentials()
    blog_id = publish_blogger._blog_id(creds, blog_url)
    return requests, f"{publish_blogger.BLOGGER_API}/blogs/{blog_id}", {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def find_post_id(title, max_results=15):
    requests, base, headers = _api()
    r = requests.get(f"{base}/posts", params={"maxResults": max_results, "fetchBodies": "false", "fetchImages": "false"}, headers=headers, timeout=30)
    r.raise_for_status()
    for p in r.json().get("items", []):
        if str(p.get("title", "")).strip() == title.strip():
            return {"id": p["id"], "url": p.get("url")}
    return None


def update_post(post_id, title, content, labels):
    requests, base, headers = _api()
    r = requests.put(f"{base}/posts/{post_id}", headers=headers, json={"kind": "blogger#post", "id": post_id, "title": title, "content": content, "labels": labels}, timeout=60)
    r.raise_for_status()
    return r.json().get("url")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    publish(do_publish="--publish" in sys.argv)
