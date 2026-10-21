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
import render_html
import report_title

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DEFAULT_REPO_SLUG = "red6keep-droid/alphascope"


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _chart_or_cover(body, repo_slug, cover_url):
    """S&P 500 그래프(탭 위, 2026-10-18)가 CDN 에서 열리지 않으면 깨진 그림 대신 커버 이미지로 바꿔 올린다. 그래프가 없으면 본문 그대로."""
    chart_ref = _read(os.path.join(OUTPUT_DIR, "chart_ref.txt")) if os.path.exists(os.path.join(OUTPUT_DIR, "chart_ref.txt")) else ""
    if not chart_ref:
        return body
    chart_url = f"https://cdn.jsdelivr.net/gh/{repo_slug}@gh-pages/{chart_ref}"
    try:
        requests.head(chart_url, timeout=30, allow_redirects=True).raise_for_status()
        print(f"그래프 확인 완료: {chart_url}")
        return body
    except Exception as e:  # noqa: BLE001
        print(f"::warning::그래프 URL 확인 실패 ({e}) — 커버 이미지로 바꿔 게시합니다.")
    start = body.find('<a href="' + chart_url + '" data-zoom="1"')
    end = body.find("</a>", start)
    if start < 0 or end < 0:
        return body
    if not cover_url:
        print("그래프 CDN 확인 실패 + 커버 없음 — 이미지 없이는 게시하지 않습니다.")
        sys.exit(1)
    return body[:start] + render_html._cover_image(cover_url) + body[end + 4:]


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

    repo_slug = os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO_SLUG
    chart_ref_path = os.path.join(OUTPUT_DIR, "chart_ref.txt")
    chart_ref = _read(chart_ref_path) if os.path.exists(chart_ref_path) else ""
    cover_url = None
    if image_ref:
        cover_url = f"https://cdn.jsdelivr.net/gh/{repo_slug}@gh-pages/{image_ref}"
        try:
            resp = requests.head(cover_url, timeout=30, allow_redirects=True)
            resp.raise_for_status()
            print(f"커버 이미지 확인 완료: {cover_url}")
        except Exception as e:
            print(f"::warning::커버 이미지 URL 확인 실패 ({cover_url}): {e}")
            cover_url = None
    if not cover_url and not chart_ref:
        # 그래프도 커버도 없으면 게시하지 않는다 (이미지 없는 글 금지는 그대로). 커버만 없는 날은 그래프로 간다 (2026-10-21, 운영지침 D6-2)
        print("그래프(chart_ref.txt)도 커버 이미지도 없음 — 이미지 없이는 게시하지 않습니다.")
        sys.exit(1)
    body = _chart_or_cover(body, repo_slug, cover_url)
    if '<a href="https://cdn.jsdelivr.net/gh/' not in body and not cover_url:
        print("그래프 URL 을 확인하지 못했고 커버 이미지도 없음 — 게시를 중단합니다.")
        sys.exit(1)

    # cron 이중화로 하루 두 번 실행될 수 있다. check_published.py가 앞단에서 걸러주지만,
    # 확인 실패나 두 실행이 겹치는 경우를 대비한 2차 방어.
    force = "--force" in sys.argv or os.environ.get("PUBLISH_FORCE", "").lower() == "true"
    if not force:
        d = report_title.date_of(title)
        existing = publish_blogger.find_post_by_title(report_title.match_titles(d) + [title] if d else title)   # 옛 제목(줄표) · 영문 제목으로 남은 그날 글도 같은 글
        if existing:
            print(f"같은 제목의 글이 이미 있습니다: {existing}")
            print("중복 게시를 건너뜁니다. (다시 올리려면 --force)")
            return

    d = report_title.date_of(title)
    url = publish_blogger.publish(title, body, dry_run=False, slug_title=report_title.slug_title(d) if d else None)   # 영문 주소 (2026-10-18)
    if url:
        print(f"게시글 URL: {url}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
