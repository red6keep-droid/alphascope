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


def publish(output_dir=None, do_publish=False):
    output_dir = output_dir or config.OUTPUT_DIR
    body_path = os.path.join(output_dir, "trump_report_body.html")
    if not os.path.exists(body_path):
        raise FileNotFoundError(f"본문 없음: {body_path} — render_html 먼저")
    with open(body_path, "r", encoding="utf-8") as f:
        body = f.read()
    title = report_title.post_title(report_title.today_kst())

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
    return url


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    publish(do_publish="--publish" in sys.argv)
