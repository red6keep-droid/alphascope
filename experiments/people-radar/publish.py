"""인물 발언 레이더 글 게시 (trump-trend/publish.py 와 같은 방식 — daily-report 의 publish_blogger 를 쓴다).

신호 0개면 게시하지 않는다 (기획 5절). 같은 날 글이 있으면 본문 · 제목 갱신.
실제 게시는 --publish 로만. 첫 게시 · 트럼프 리포트 대체 · 워크플로 연결은 사용자 확인 뒤 (기획 6절 진행).

    python publish.py            # dry-run
    python publish.py --publish
"""

import json
import os
import sys

import config
import render_html

sys.path.append(os.path.abspath(os.path.join(config.BASE_DIR, "..", "daily-report")))   # 뒤에 붙인다 — 이쪽 모듈 이름을 가리지 않게
import publish_blogger  # noqa: E402


def event_count(output_dir=None):
    path = os.path.join(output_dir or config.OUTPUT_DIR, "radar.json")
    if not os.path.exists(path):
        return -1
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("event_count") or 0


def match_titles(day):
    return [render_html.post_title(day), f"{render_html.SLUG_NAME} {day}"]


def publish(output_dir=None, do_publish=False):
    output_dir = output_dir or config.OUTPUT_DIR
    if event_count(output_dir) <= 0:
        print("[publish] 최근 24시간 신호 0개 — 오늘은 게시하지 않는다")
        return None
    with open(os.path.join(output_dir, "radar_body.html"), encoding="utf-8") as f:
        body = f.read()
    day = render_html.today_kst()
    title = render_html.post_title(day)
    if not do_publish:
        print(f"[publish dry-run] 제목: {title} · 본문 {len(body):,}자 · 라벨 {render_html.LABELS}")
        return None
    sys.path.append(os.path.abspath(os.path.join(config.BASE_DIR, "..", "trump-trend")))
    from importlib import util
    spec = util.spec_from_file_location("trump_publish", os.path.join(config.BASE_DIR, "..", "trump-trend", "publish.py"))
    tp = util.module_from_spec(spec)
    spec.loader.exec_module(tp)   # find_post_id · update_post 를 그대로 쓴다
    existing = tp.find_post_id(match_titles(day))
    if existing:
        url = tp.update_post(existing["id"], title, publish_blogger.with_related(body, render_html.LABELS, match_titles(day)), render_html.LABELS)
        print(f"[publish] 같은 날 글이 있어 본문 갱신: {url}")
    else:
        url = publish_blogger.publish(title, body, labels=render_html.LABELS, slug_title=f"{render_html.SLUG_NAME} {day}")
    with open(os.path.join(output_dir, "post_url.txt"), "w", encoding="utf-8") as f:
        f.write(url or "")
    return url


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    publish(do_publish="--publish" in sys.argv)
