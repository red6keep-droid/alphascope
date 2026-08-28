"""오늘(KST) 날짜의 데일리 브리핑이 이미 게시됐는지 확인 (게시하지 않음)

GitHub Actions의 cron은 부하가 높으면 지연되거나 조용히 누락된다(실제로
2026-08-26/27 스케줄이 실행되지 않았다). 그래서 cron을 하루 두 번 걸어두고,
이 스크립트로 같은 날 중복 게시를 막는다.

이미 게시돼 있으면 이후 파이프라인 전체를 건너뛰므로 Gemini 호출과
커버 이미지 생성 비용도 아낀다.

GITHUB_OUTPUT에 already_published=true|false 를 기록한다.
확인 자체가 실패하면 false로 기록해 그날 리포트가 누락되지 않게 한다.
(중복 게시는 publish_saved.py의 2차 확인에서 다시 걸러진다.)

사용법:
    python experiments/daily-report/check_published.py
"""

import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import publish_blogger
import report_title


def _set_output(already_published):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"already_published={'true' if already_published else 'false'}\n")


def main():
    load_dotenv()

    title = report_title.daily_title(report_title.today_kst())
    print(f"확인할 제목: {title}")

    try:
        url = publish_blogger.find_post_by_title(title)
    except Exception as e:
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
