"""데일리 리포트 파이프라인 실행 (테스트)

사용법 (리포 루트에서):
    python experiments/daily-report/main.py            # dry-run: 수집~HTML만
    python experiments/daily-report/main.py --publish  # Blogger에 실제 게시

흐름:
    collect_fred + collect_yahoo + collect_news (+ collect_nowcast → state/records/snapshots)
    → report_input.json (+ prices.json: 분석용 시계열)
    → analyze → analysis.json, state/ (그림자 모드: 실패해도 리포트는 계속)
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
import json
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import notify  # noqa: E402  — 운영 알림 (experiments/notify.py, 2026-10-21)
import record_store  # noqa: E402  — 판정 · 이슈 누적 (experiments/record_store.py, 2026-10-22)

import analyze
import chart_spx
import collect_calendar
import collect_fred
import collect_news
import collect_nowcast
import collect_yahoo
import generate_image
import generate_report
import publish_blogger
import render_html
import report_title
import validate_report

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
INPUT_PATH = os.path.join(OUTPUT_DIR, "report_input.json")
PRICES_PATH = os.path.join(OUTPUT_DIR, "prices.json")
ANALYSIS_PATH = os.path.join(OUTPUT_DIR, "analysis.json")
REPORT_PATH = os.path.join(OUTPUT_DIR, "report.out.json")

DEFAULT_REPO_SLUG = "red6keep-droid/alphascope"


def _repo_slug():
    return os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO_SLUG


def collect():
    print("=" * 50)
    print("[1/6] 데이터 수집")
    print("=" * 50)

    macro = collect_fred.collect_fred()
    yahoo = collect_yahoo.collect_yahoo()
    news = collect_news.collect_news()
    try:   # 일정 탭 (D5) — 실패해도 리포트는 나간다
        calendar = collect_calendar.collect_calendar()
    except Exception as e:  # noqa: BLE001
        print(f"::warning::일정 수집 실패: {e!r}")
        calendar = None

    collect_fred.apply_fallbacks(macro, yahoo.get("history"), yahoo.get("indices"))

    today = report_title.today_kst()
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
        "calendar": calendar,
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(INPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(input_data, f, ensure_ascii=False, indent=2)
    print(f"report_input.json 저장 완료 -> {INPUT_PATH}")

    # 시계열은 Gemini 입력(report_input.json)에 섞지 않고 따로 둔다.
    history = yahoo.get("history")
    if history:
        with open(PRICES_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False)
        print(f"prices.json 저장 완료 -> {PRICES_PATH}")
    elif os.path.exists(PRICES_PATH):
        os.remove(PRICES_PATH)
    return input_data


def run_analysis():
    """그림자 모드. 결과는 analysis.json과 state/에만 남고 게시물에는 아직 안 쓴다.
    그래서 여기서 무엇이 실패하든 리포트를 멈추지 않는다."""
    print("=" * 50)
    print("[1.5/6] 분석")
    print("=" * 50)
    # 어제 파일이 남아 있으면 오늘 분석이 실패했을 때 그걸 오늘 것으로 렌더한다. 먼저 지운다.
    if os.path.exists(ANALYSIS_PATH):
        os.remove(ANALYSIS_PATH)
    if not os.path.exists(PRICES_PATH):
        print("::warning::시계열이 없어 분석을 건너뜁니다.")
        return None
    try:
        analyze.analyze(INPUT_PATH, PRICES_PATH, ANALYSIS_PATH)
        return ANALYSIS_PATH
    except Exception as e:
        print(f"::warning::분석 실패 (리포트는 계속 진행): {e!r}")
        if os.path.exists(ANALYSIS_PATH):
            os.remove(ANALYSIS_PATH)
        return None


def make_chart(input_data):
    """S&P 500 가격 그래프 (탭 위, 2026-10-18 사용자). 어제 그림이 오늘 글에 붙지 않게 먼저 지운다. 실패해도 리포트는 그래프 없이 나간다."""
    for name in ("chart.json", "chart_ref.txt"):
        path = os.path.join(OUTPUT_DIR, name)
        if os.path.exists(path):
            os.remove(path)
    as_of = None
    if os.path.exists(ANALYSIS_PATH):
        with open(ANALYSIS_PATH, "r", encoding="utf-8") as f:
            as_of = json.load(f).get("as_of")
    try:
        return chart_spx.run(input_data["date"], as_of=as_of, output_dir=OUTPUT_DIR)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::그래프 실패 — 그래프 없이 렌더: {e!r}")
        return None


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
    analysis_path = run_analysis()

    print("=" * 50)
    print("[2/6] Gemini 리포트 생성")
    print("=" * 50)
    generate_report.generate_report(INPUT_PATH, REPORT_PATH, analysis_path=analysis_path)

    print("=" * 50)
    print("[3/6] 검증")
    print("=" * 50)
    validate_report.validate(INPUT_PATH, REPORT_PATH, analysis_path=analysis_path)

    # 그날 판정 · 선정 뉴스(이슈 코드)를 report-state 의 records/ 에 덧붙인다 — 덮어쓰지 않는 우리 기록 (블로그-목적과-방향 6절 1번, 2026-10-22)
    try:
        with open(REPORT_PATH, encoding="utf-8") as f:
            _report = json.load(f)
        _analysis = None
        if analysis_path and os.path.exists(analysis_path):
            with open(analysis_path, encoding="utf-8") as f:
                _analysis = json.load(f)
        _v, _i = record_store.daily_rows(input_data, _report, _analysis)
        record_store.append(os.path.join(OUTPUT_DIR, "state"), "verdicts", _v)
        record_store.append(os.path.join(OUTPUT_DIR, "state"), "issues", _i)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::기록 저장 실패 (게시는 계속): {e!r}")

    # 발표 전 예상(연준 나우캐스트) 스냅샷 — 하루 1줄, 리포트 본문에는 아직 안 쓴다 (블로그-목적과-방향 6절 3번, 2026-10-22). 실패해도 계속
    try:
        record_store.append(os.path.join(OUTPUT_DIR, "state"), "snapshots", [collect_nowcast.collect(input_data["date"])])
    except Exception as e:  # noqa: BLE001
        print(f"::warning::나우캐스트 스냅샷 저장 실패 (게시는 계속): {e!r}")

    chart_ok = bool(make_chart(input_data))
    image_ok, cover_url = make_cover(input_data)
    # 그래프(chart_spx)가 커버 자리라 커버는 그래프가 없는 날만 쓰인다 (render_html.build_body). 커버 생성 실패가 그래프 있는 날의 게시까지
    # 막던 단일 실패점을 풀었다 — 둘 다 없을 때만 멈춘다 (2026-10-21, 운영지침 D6-2; "이미지 없이 게시하지 않는다"는 그대로)
    if should_publish and not image_ok and not chart_ok:
        print("[게시 중단] 그래프도 커버 이미지도 없습니다. 이미지 없이 게시하지 않습니다.")
        sys.exit(1)
    if should_publish and not image_ok:
        print("::warning::커버 이미지 생성 실패 — 그래프가 있어 그대로 진행합니다.")

    print("=" * 50)
    print("[5/6] HTML 렌더링")
    print("=" * 50)
    body, body_path, preview_path = render_html.render(
        INPUT_PATH, REPORT_PATH, OUTPUT_DIR, cover_url=cover_url, analysis_path=analysis_path
    )

    title = report_title.daily_title(input_data["date"])
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
        url = publish_blogger.publish(title, body, dry_run=False, slug_title=report_title.slug_title(input_data["date"]))
        if url:
            print(f"게시글 URL: {url}")
    else:
        publish_blogger.publish(title, body, dry_run=True)
        print("게시를 원하면 --publish 옵션을 붙여 실행하세요.")
        print(f"미리보기: {preview_path}")

    print("파이프라인 종료")


if __name__ == "__main__":
    # 데일리는 CNBC · FRED · 지수 · LLM · 커버 중 하나라도 죽으면 중단하는 구조 — 중단 이유를 Slack 으로 (2026-10-21, 운영지침 D6-2)
    try:
        main()
    except SystemExit as e:
        if e.code not in (0, None):
            notify.now(f"데일리 리포트 중단 (exit {e.code}) — 로그 확인")
        raise
    except Exception as e:  # noqa: BLE001
        notify.now(f"데일리 리포트 예외로 중단 — {type(e).__name__}: {str(e)[:160]}")
        raise
