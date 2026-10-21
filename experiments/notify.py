"""운영 알림 — 수집 소스 실패 · 0건 · 미게시 · 토큰 문제를 Slack 한 채널로 (2026-10-21, doc/운영/블로그-운영-지침.md D6-3).

예전에는 Slack 알림이 LLM 한도(llm_chain) 와 댓글 처리에만 있었다. yfinance · CNN 아카이브 · CNBC 가 죽어도
print 로그에만 남아 Actions 화면을 열어야 보였고, 트럼프 리포트는 소스가 죽으면 소리 없이 안 나갔다.

쓰는 법 (파이프라인 폴더에서 experiments/ 를 sys.path 에 넣고):
    import notify
    notify.event("수집 실패", "CNN 아카이브 — HTTP 503")      # 모아 뒀다가 프로세스 끝에 한 번에
    notify.now("홈 시세 0건 — 배포하지 않음")                  # 바로 보낸다 (중단 직전처럼 atexit 를 못 믿을 때)

SLACK_WEBHOOK_URL 이 없으면 아무것도 보내지 않는다(로컬 실행). 보내기 실패는 print 만 — 알림 때문에 리포트가 죽으면 안 된다.
워크플로 자체의 실패(파이썬 밖 단계)는 각 .yml 의 `if: failure()` 단계가 같은 웹훅으로 보낸다.
"""

import atexit
import os
from collections import Counter

import requests

EVENTS = Counter()


def _run_name():
    return os.environ.get("GITHUB_WORKFLOW") or "로컬 실행"


def _run_link():
    if os.environ.get("GITHUB_RUN_ID"):
        return f"\n🔗 https://github.com/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    return ""


def _post(text):
    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        return False
    try:
        requests.post(url, json={"text": text, "unfurl_links": False}, timeout=20)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[notify] Slack 알림 실패: {e}")
        return False


def event(kind, detail):
    """모아 뒀다가 프로세스가 끝날 때 한 번에 보낸다. kind: "수집 실패" · "0건" · "미게시" · "토큰" 등."""
    print(f"[notify] {kind} — {detail}")
    EVENTS[f"{kind} — {detail}"] += 1


def now(text):
    """바로 보낸다. sys.exit 직전처럼 atexit 를 기다릴 수 없을 때."""
    print(f"[notify] {text}")
    _post(f"🚨 {_run_name()}\n{text}{_run_link()}")


def _flush():
    if not EVENTS:
        return
    lines = [f"⚠️ 운영 알림 — {_run_name()}", ""]
    for k, n in EVENTS.most_common():
        lines.append(f"• {k}" + (f" ×{n}" if n > 1 else ""))
    lines.append(_run_link())
    _post("\n".join(lines))


atexit.register(_flush)
