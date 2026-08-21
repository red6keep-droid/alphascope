"""데일리 리포트 파이프라인 실행 (테스트)

사용법 (리포 루트에서):
    python experiments/daily-report/main.py            # dry-run: 수집~HTML만
    python experiments/daily-report/main.py --publish  # Blogger에 실제 게시

흐름:
    collect_fred + collect_yahoo + collect_news
    → report_input.json
    → generate_report (Gemini) → report.out.json
    → validate_report (실패 시 중단)
    → generate_image (Pollinations → HF fallback) → output/images/{date}.webp
    → render_html → output/{report.html, report_body.html}
    → title.txt / image_ref.txt 기록 (GitHub Actions 후속 단계용)
    → publish_blogger (--publish 시)

GitHub Actions에서는 이 스크립트를 항상 dry-run으로 실행한 뒤,
이미지를 gh-pages에 배포하고 publish_saved.py로 게시한다(2단계 분리).
"""

import argparse
import datetime
import json
import os
import sys

from dotenv import load_dotenv

import collect_fred
import collect_news
import collect_yahoo
import generate_image
import generate_report
import publish_blogger
import render_html
import validate_report

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
INPUT_PATH = os.path.join(OUTPUT_DIR, "report_input.json")
REPORT_PATH = os.path.join(OUTPUT_DIR, "report.out.json")

DEFAULT_REPO_SLUG = "red6keep-droid/alphascope"

KST = datetime.timezone(datetime.timedelta(hours=9))


def _korean_date(date_str):
    try:
        y, m, d = str(date_str).split("-")[:3]
        return f"{int(y)}년 {int(m)}월 {int(d)}일"
    except Exception:
        return date_str


def _repo_slug():
    return os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO_SLUG


def collect():
    print("=" * 50)
    print("[1/6] 데이터 수집")
    print("=" * 50)

    macro = collect_fred.collect_fred()
    yahoo = collect_yahoo.collect_yahoo()
    news = collect_news.collect_news()

    today = datetime.datetime.now(KST).strftime("%Y-%m-%d")
    input_data = {
        "date": today,
        "updated_at": yahoo.get("updated_at"),
        "macro": macro,
        "market": {
            "indices": yahoo["indices"],
        },
        "gainers": yahoo["gainers"],
        "most_active": yahoo["most_active"],
        "news": news,
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(INPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(input_data, f, ensure_ascii=False, indent=2)
    print(f"report_input.json 저장 완료 -> {INPUT_PATH}")
    return input_data


def make_cover(input_data):
    """커버 이미지를 생성하고 (성공 여부, 공개 URL)을 반환한다."""
    print("=" * 50)
    print("[4/6] 커버 이미지 생성")
    print("=" * 50)

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        image_prompt = str(json.load(f).get("image_prompt") or "").strip()

    date_slug = input_data["date"]
    image_ref = f"images/{date_slug}.webp"
    images_dir = os.path.join(OUTPUT_DIR, "images")
    os.makedirs(images_dir, exist_ok=True)
    image_path = os.path.join(images_dir, f"{date_slug}.webp")

    ok = bool(image_prompt) and generate_image.generate_image(image_prompt, image_path)
    if not ok:
        return False, None

    cover_url = f"https://cdn.jsdelivr.net/gh/{_repo_slug()}@gh-pages/{image_ref}"
    print(f"커버 이미지 URL: {cover_url}")
    return True, cover_url


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="알파스코프 데일리 리포트")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--publish", action="store_true",
                       help="리포트를 Blogger에 실제 게시")
    group.add_argument("--dry-run", action="store_true", default=True,
                       help="수집~HTML까지만 생성하고 게시하지 않음 (기본)")
    args = parser.parse_args()

    should_publish = args.publish or os.environ.get("PUBLISH_BLOG", "").lower() == "true"

    input_data = collect()

    print("=" * 50)
    print("[2/6] Gemini 리포트 생성")
    print("=" * 50)
    generate_report.generate_report(INPUT_PATH, REPORT_PATH)

    print("=" * 50)
    print("[3/6] 검증")
    print("=" * 50)
    validate_report.validate(INPUT_PATH, REPORT_PATH)

    image_ok, cover_url = make_cover(input_data)
    if should_publish and not image_ok:
        print("[게시 중단] 커버 이미지 생성 실패. 이미지 없이 게시하지 않습니다.")
        sys.exit(1)

    print("=" * 50)
    print("[5/6] HTML 렌더링")
    print("=" * 50)
    body, body_path, preview_path = render_html.render(
        INPUT_PATH, REPORT_PATH, OUTPUT_DIR, cover_url=cover_url
    )

    title = f"미국 증시 데일리 브리핑 — {_korean_date(input_data['date'])}"
    print(f"제목: {title}")

    # GitHub Actions 후속 단계(이미지 배포/게시)가 읽는 메타 파일
    with open(os.path.join(OUTPUT_DIR, "title.txt"), "w", encoding="utf-8") as f:
        f.write(title + "\n")
    with open(os.path.join(OUTPUT_DIR, "image_ref.txt"), "w", encoding="utf-8") as f:
        f.write((f"images/{input_data['date']}.webp" if image_ok else "") + "\n")

    print("=" * 50)
    print("[6/6] 게시")
    print("=" * 50)
    if should_publish:
        url = publish_blogger.publish(title, body, dry_run=False)
        if url:
            print(f"게시글 URL: {url}")
    else:
        publish_blogger.publish(title, body, dry_run=True)
        print("게시를 원하면 --publish 옵션을 붙여 실행하세요.")
        print(f"미리보기: {preview_path}")

    print("파이프라인 종료")


if __name__ == "__main__":
    main()
