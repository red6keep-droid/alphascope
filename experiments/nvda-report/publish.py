"""별도 글로 Blogger 게시 (기획서 10절). trump-trend publish.py와 같은 규칙 — daily-report의 publish_blogger를 가져다 쓰고,
같은 제목(같은 날짜)의 글이 있으면 다시 올리지 않는다.

    python experiments/nvda-report/publish.py            # dry-run
    python experiments/nvda-report/publish.py --publish  # 실제 게시
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


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    publish(do_publish="--publish" in sys.argv)
