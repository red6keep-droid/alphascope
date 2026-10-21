"""오늘(KST) 날짜의 데일리 브리핑이 이미 게시됐는지 확인 (게시하지 않음)

GitHub Actions의 cron은 부하가 높으면 지연되거나 조용히 누락된다(실제로
2026-08-26/27 스케줄이 실행되지 않았다). 그래서 cron을 하루 두 번 걸어두고,
이 스크립트로 같은 날 중복 게시를 막는다.

이미 게시돼 있으면 이후 파이프라인 전체를 건너뛰므로 Gemini 호출과
커버 이미지 생성 비용도 아낀다.

GITHUB_OUTPUT에 already_published=true|false 를 기록한다.
확인 자체가 실패하면 false로 기록해 그날 리포트가 누락되지 않게 한다.
(중복 게시는 publish_saved.py의 2차 확인에서 다시 걸러진다.)

트럼프·NVDA 시리즈도 같은 방식으로 확인한다(--series). 그쪽 publish.py는 같은 제목이면
덮어쓰므로 중복 글은 생기지 않지만, 외부 cron과 GitHub cron이 둘 다 도는 날
Gemini 호출과 상태 커밋이 두 번 일어나는 것을 막는다 (2026-10-13).

사용법:
    python experiments/daily-report/check_published.py                  # 데일리
    python experiments/daily-report/check_published.py --series trump   # 트럼프 SNS 트렌드
    python experiments/daily-report/check_published.py --series nvda    # 엔비디아 리포트
"""

import argparse
import importlib.util
import os
import sys

from dotenv import load_dotenv
from google.auth.exceptions import RefreshError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import notify  # noqa: E402  — 운영 알림 (experiments/notify.py, 2026-10-21)
import publish_blogger
import report_title

EXPERIMENTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERIES_DIRS = {"trump": "trump-trend", "nvda": "nvda-report"}


def _set_output(already_published):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"already_published={'true' if already_published else 'false'}\n")


def _title(series):
    if series == "daily":
        return report_title.match_titles(report_title.today_kst())
    # 시리즈마다 report_title.py가 있어 이름이 겹친다. 파일 경로로 따로 불러온다.
    # nvda의 report_title은 같은 폴더의 config를 import하므로 그 폴더를 경로 앞에 둔다.
    series_dir = os.path.join(EXPERIMENTS, SERIES_DIRS[series])
    sys.path.insert(0, series_dir)
    spec = importlib.util.spec_from_file_location(
        f"{series}_report_title", os.path.join(series_dir, "report_title.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.match_titles(module.today_kst())   # 새 · 옛(줄표) · 영문 제목 모두 그날 글 (2026-10-18)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--series", choices=["daily", *SERIES_DIRS], default="daily")
    args = parser.parse_args()

    load_dotenv()

    title = _title(args.series)
    print(f"확인할 제목: {' / '.join(title)}")

    try:
        url = publish_blogger.find_post_by_title(title)
    except Exception as e:
        # refresh token 이 무효(만료 · 철회 · 비밀번호 변경 · 50개 초과)면 뒤 단계가 다 돌아도 게시에서 실패한다 —
        # Gemini 를 헛쓰기 전에 여기서 멈추고 알린다 (2026-10-21, 운영지침 D2-6 · 10절). 네트워크 같은 일시 오류는 예전처럼 진행
        if isinstance(e, RefreshError) or "invalid_grant" in str(e):
            notify.now("Blogger OAuth 토큰 무효 (invalid_grant) — setup_oauth.py 로 재발급 후 BLOGGER_REFRESH_TOKEN 교체. 파이프라인 중단")
            sys.exit(1)
        print(f"::warning::게시 여부 확인 실패 ({e}) — 게시되지 않은 것으로 간주하고 진행합니다.")
        _set_output(False)
        return

    if url:
        print(f"이미 게시됨: {url} — 이후 단계를 모두 건너뜁니다.")
        _set_output(True)
    else:
        print("오늘 게시된 글이 없습니다 — 파이프라인을 진행합니다.")
        _set_output(False)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    main()
