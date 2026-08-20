"""데일리 리포트 파이프라인 실행 (테스트)

사용법 (리포 루트에서):
    python experiments/daily-report/main.py            # dry-run: 수집~HTML만
    python experiments/daily-report/main.py --publish  # Blogger에 실제 게시

흐름:
    collect_fred + collect_yahoo + collect_news
    → report_input.json
    → generate_report (Gemini) → report.out.json
    → validate_report (실패 시 중단)
    → render_html → output/{report.html, report_body.html}
    → publish_blogger (--publish 시)
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

KST = datetime.timezone(datetime.timedelta(hours=9))


def _korean_date(date_str):
    try:
        y, m, d = str(date_str).split("-")[:3]
        return f"{int(y)}년 {int(m)}월 {int(d)}일"
    except Exception:
        return date_str


def collect():
    print("=" * 50)
    print("[1/5] 데이터 수집")
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
    print("[2/5] Gemini 리포트 생성")
    print("=" * 50)
    generate_report.generate_report(INPUT_PATH, REPORT_PATH)

    print("=" * 50)
    print("[3/5] 검증")
    print("=" * 50)
    validate_report.validate(INPUT_PATH, REPORT_PATH)

    print("=" * 50)
    print("[4/5] HTML 렌더링")
    print("=" * 50)
    body, body_path, preview_path = render_html.render(INPUT_PATH, REPORT_PATH, OUTPUT_DIR)

    title = f"미국 증시 데일리 브리핑 — {_korean_date(input_data['date'])}"
    print(f"제목: {title}")

    print("=" * 50)
    print("[5/5] 게시")
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