"""저장된 리포트(output/)를 Blogger에 게시 (GitHub Actions 후속 단계용)

main.py는 워크플로우에서 항상 dry-run으로 실행되어 output/에
report_body.html / title.txt / image_ref.txt를 남긴다.
워크플로우는 커버 이미지를 gh-pages에 배포·검증한 뒤 이 스크립트로 게시해,
이미지 URL이 살아 있는 상태에서 글이 올라가도록 한다.

게시 조건:
    - title.txt / report_body.html 존재
    - image_ref.txt 존재 + jsDelivr CDN URL HTTP 200 (커버 이미지 보장)
    - 같은 제목의 글이 아직 없음 (cron 이중화 대비 중복 방지)

사용법:
    python experiments/daily-report/publish_saved.py
    python experiments/daily-report/publish_saved.py --force  # 중복 확인 무시
"""

import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import publish_blogger

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DEFAULT_REPO_SLUG = "red6keep-droid/alphascope"


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def main():
    body_path = os.path.join(OUTPUT_DIR, "report_body.html")
    title_path = os.path.join(OUTPUT_DIR, "title.txt")
    image_ref_path = os.path.join(OUTPUT_DIR, "image_ref.txt")

    for p in (body_path, title_path, image_ref_path):
        if not os.path.exists(p):
            print(f"파일 없음: {p} — 먼저 main.py를 실행하세요.")
            sys.exit(1)

    title = _read(title_path)
    body = open(body_path, "r", encoding="utf-8").read()
    image_ref = _read(image_ref_path)

    if not title or not body.strip():
        print("제목 또는 본문이 비어 있어 게시를 중단합니다.")
        sys.exit(1)

    if not image_ref:
        print("image_ref.txt가 비어 있음 — 커버 이미지 없이는 게시하지 않습니다.")
        sys.exit(1)

    repo_slug = os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO_SLUG
    cover_url = f"https://cdn.jsdelivr.net/gh/{repo_slug}@gh-pages/{image_ref}"
    try:
        resp = requests.head(cover_url, timeout=30, allow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        print(f"커버 이미지 URL 확인 실패 ({cover_url}): {e}")
        print("이미지가 배포되지 않았거나 CDN 반영 전입니다. 게시를 중단합니다.")
        sys.exit(1)
    print(f"커버 이미지 확인 완료: {cover_url}")

    # cron 이중화로 하루 두 번 실행될 수 있다. check_published.py가 앞단에서 걸러주지만,
    # 확인 실패나 두 실행이 겹치는 경우를 대비한 2차 방어.
    force = "--force" in sys.argv or os.environ.get("PUBLISH_FORCE", "").lower() == "true"
    if not force:
        existing = publish_blogger.find_post_by_title(title)
        if existing:
            print(f"같은 제목의 글이 이미 있습니다: {existing}")
            print("중복 게시를 건너뜁니다. (다시 올리려면 --force)")
            return

    url = publish_blogger.publish(title, body, dry_run=False)
    if url:
        print(f"게시글 URL: {url}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
