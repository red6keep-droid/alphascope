"""한국 증시 리포트 게시 — main.py 가 만든 output/report_body.html 을 블로그 글 1편으로 (doc/기획/한국-증시-리포트-기획.md 5절).
    python experiments/kr-market-report/publish_report.py         # 게시
    python experiments/kr-market-report/publish_report.py --dry   # 확인만

제목은 매일 같은 `한국 증시 리포트`(M1)라 제목으로는 그날 글을 못 찾는다 → 라벨 목록에서 게시일(KST)로 찾는다.
GitHub cron 과 Cloudflare Worker 가 둘 다 도는 날 두 번째 실행은 여기서 건너뛴다.
주소는 영문 제목(날짜 포함)으로 먼저 정하고 한글 제목으로 바꾼다 — 데일리와 같은 방식(publish_blogger.publish slug_title).
게시한 글은 kr-stocks/data/report_posts.json 에 날짜 → 주소로 쌓는다(kr-state 에 보관, 기록 보존).
"""
import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "daily-report"))
import publish_blogger as PB  # noqa: E402

OUT = os.path.join(_HERE, "output")
POSTS = os.path.join(_HERE, "..", "kr-stocks", "data", "report_posts.json")
LABEL = "한국 증시 리포트"
LABELS = [LABEL, "한국 증시", "자동 리포트"]
SLUG_NAME = "korea stock market report"
KST = ZoneInfo("Asia/Seoul")


def _load_posts():
    try:
        with open(POSTS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def find_today(day, creds):
    """그날(KST) 게시된 이 연재 글 주소 — 없으면 None."""
    blog_id = PB._blog_id(creds, PB.DEFAULT_BLOG_URL)
    r = requests.get(f"{PB.BLOGGER_API}/blogs/{blog_id}/posts",
                     params={"labels": LABEL, "maxResults": 5, "fetchBodies": "false", "fetchImages": "false"},
                     headers={"Authorization": f"Bearer {creds.token}"}, timeout=30)
    r.raise_for_status()
    for p in r.json().get("items", []):
        pub = datetime.datetime.fromisoformat(p["published"]).astimezone(KST).strftime("%Y-%m-%d")
        if pub == day:
            return p.get("url")
    return None


def main(dry):
    with open(os.path.join(OUT, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    with open(os.path.join(OUT, "report_body.html"), encoding="utf-8") as f:
        body = f.read()
    day, title = meta["day"], meta["title"]
    posts = _load_posts()
    if day in posts:
        print(f"[kr-report] {day} 이미 게시됨 (기록) — 건너뜀: {posts[day]}")
        return
    if dry:
        print(f"[kr-report] dry-run — {day} · {title} · 본문 {len(body):,}자 · 라벨 {LABELS}")
        return
    url = find_today(day, PB._credentials())
    if not url:
        url = PB.publish(title, body, labels=LABELS, slug_title=f"{SLUG_NAME} {day}")
    else:
        print(f"[kr-report] {day} 이미 게시됨 (블로그) — 건너뜀: {url}")
    if url:
        posts[day] = url
        os.makedirs(os.path.dirname(POSTS), exist_ok=True)
        with open(POSTS, "w", encoding="utf-8") as f:
            json.dump(posts, f, ensure_ascii=False, indent=0, sort_keys=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main("--dry" in sys.argv)
