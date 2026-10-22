"""미디어 데일리 게시 (people-radar/publish.py 와 같은 방식 — daily-report 의 publish_blogger · trump-trend 의 update_post).

같은 날 글이 있으면(2차 10:15) 본문 갱신, 없으면(1차 08:00) 새 글. 재료가 MIN_ITEMS 미만이면 게시하지 않는다.
주소는 slug_title "media daily YYYY-MM-DD" 로 고정 → 같은 날 글 찾기는 주소의 날짜로.

    python publish.py            # dry-run
    python publish.py --publish
"""

import json
import os
import sys

import config

sys.path.append(os.path.abspath(os.path.join(config.BASE_DIR, "..", "daily-report")))   # 뒤에 붙인다 — 이쪽 모듈 이름을 가리지 않게
import publish_blogger  # noqa: E402


def item_count(output_dir=None):
    path = os.path.join(output_dir or config.OUTPUT_DIR, "media.json")
    if not os.path.exists(path):
        return -1
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("n_items") or 0


def labels():
    return config.LABELS + (["테스트 중"] if config.TEST_MODE else [])


def find_same_day(tp, day):
    requests, base, headers = tp._api()
    r = requests.get(f"{base}/posts", params={"maxResults": 15, "fetchBodies": "false", "fetchImages": "false"}, headers=headers, timeout=30)
    r.raise_for_status()
    slug = f"{config.SLUG_NAME} {day}".replace(" ", "-")
    for p in r.json().get("items", []):
        if slug in str(p.get("url", "")) or str(p.get("title", "")).strip() == config.post_title(day):
            return {"id": p["id"], "url": p.get("url")}
    return None


def publish(output_dir=None, do_publish=False):
    output_dir = output_dir or config.OUTPUT_DIR
    if item_count(output_dir) < config.MIN_ITEMS:
        print(f"[publish] 재료 {item_count(output_dir)}건 < {config.MIN_ITEMS} — 오늘은 게시하지 않는다")
        return None
    body_path = os.path.join(output_dir, "media_body.html")
    if not os.path.exists(body_path):
        print("[publish] 본문 없음 — 게시하지 않는다")
        return None
    with open(body_path, encoding="utf-8") as f:
        body = f.read()
    with open(os.path.join(output_dir, "media.json"), encoding="utf-8") as f:
        day = json.load(f)["edition"]
    title = config.post_title(day)
    if not do_publish:
        print(f"[publish dry-run] 제목: {title} · 본문 {len(body):,}자 · 라벨 {labels()}")
        return None
    from importlib import util
    spec = util.spec_from_file_location("trump_publish", os.path.join(config.BASE_DIR, "..", "trump-trend", "publish.py"))
    tp = util.module_from_spec(spec)
    spec.loader.exec_module(tp)   # _api · update_post 를 그대로 쓴다
    existing = find_same_day(tp, day)
    if existing:
        url = tp.update_post(existing["id"], title, publish_blogger.with_related(body, labels(), [title]), labels())
        print(f"[publish] 같은 날 글이 있어 본문 갱신: {url}")
    else:
        url = publish_blogger.publish(title, body, labels=labels(), slug_title=f"{config.SLUG_NAME} {day}")
    with open(os.path.join(output_dir, "post_url.txt"), "w", encoding="utf-8") as f:
        f.write(url or "")
    return url


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    publish(do_publish="--publish" in sys.argv)
