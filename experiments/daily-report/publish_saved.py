"""저장된 리포트(output/)를 Blogger에 게시 (GitHub Actions 후속 단계용)

main.py는 워크플로우에서 항상 dry-run으로 실행되어 output/에
report_body.html / title.txt / image_ref.txt를 남긴다.
워크플로우는 커버 이미지를 gh-pages에 배포·검증한 뒤 이 스크립트로 게시해,
이미지 URL이 살아 있는 상태에서 글이 올라가도록 한다.

게시 조건:
    - title.txt / report_body.html 존재
    - 봉차트(data-candle)는 조건 아님 — 없으면 봉차트 없이 게시 (2026-11-21 사용자, 운영지침 D6-2. 옛 11-16 "봉차트 없으면 중단" 폐지)
    - 같은 제목의 글이 아직 없음 (cron 이중화 대비 중복 방지)

사용법:
    python experiments/daily-report/publish_saved.py
    python experiments/daily-report/publish_saved.py --force  # 중복 확인 무시
"""

import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import ops_log  # noqa: E402,F401  — 운영 기록 (experiments/ops_log.py, 2026-10-23): 게시 결과 · 중단 이유
import publish_blogger
import render_html
import report_title

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DEFAULT_REPO_SLUG = "red6keep-droid/alphascope"


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _write_meta(title, url, day, body):
    """홈 카드 재료용(home_card.py, H31 2026-11-05): output/post_meta.json + 실제 올린 본문 published_body.html"""
    with open(os.path.join(OUTPUT_DIR, "post_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"title": title, "url": url, "day": str(day) if day else None}, f, ensure_ascii=False)
    with open(os.path.join(OUTPUT_DIR, "published_body.html"), "w", encoding="utf-8") as f:
        f.write(body)


def main():
    body_path = os.path.join(OUTPUT_DIR, "report_body.html")
    title_path = os.path.join(OUTPUT_DIR, "title.txt")

    for p in (body_path, title_path):
        if not os.path.exists(p):
            print(f"파일 없음: {p} — 먼저 main.py를 실행하세요.")
            sys.exit(1)

    title = _read(title_path)
    body = open(body_path, "r", encoding="utf-8").read()

    if not title or not body.strip():
        print("제목 또는 본문이 비어 있어 게시를 중단합니다.")
        sys.exit(1)

    if "data-candle=" not in body:   # 맨 위 봉차트가 없으면 그 자리만 빼고 게시 (2026-11-21 사용자, 운영지침 D6-2 — 옛 11-16 게시 중단 폐지)
        print("::warning::본문에 S&P 500 봉차트 없음 — 봉차트 없이 게시")

    # cron 이중화로 하루 두 번 실행될 수 있다. check_published.py가 앞단에서 걸러주지만,
    # 확인 실패나 두 실행이 겹치는 경우를 대비한 2차 방어.
    force = "--force" in sys.argv or os.environ.get("PUBLISH_FORCE", "").lower() == "true"
    if not force:
        d = report_title.date_of(title)
        existing = publish_blogger.find_post_by_title(report_title.match_titles(d) + [title] if d else title)   # 옛 제목(줄표) · 영문 제목으로 남은 그날 글도 같은 글
        if existing:
            print(f"같은 제목의 글이 이미 있습니다: {existing}")
            print("중복 게시를 건너뜁니다. (다시 올리려면 --force)")
            if str(existing).startswith("http"):
                _write_meta(title, existing, d, body)   # 카드 JSON 은 다시 만든다
            return

    d = report_title.date_of(title)
    url = publish_blogger.publish(title, body, dry_run=False, slug_title=report_title.slug_title(d) if d else None)   # 영문 주소 (2026-10-18)
    if url:
        print(f"게시글 URL: {url}")
        _write_meta(title, url, d, body)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
