"""소리 없는 실패 알림 — continue-on-error 단계가 실패해도 실행은 `성공` 으로 끝나 아무 알림이 없던 것 (2026-11-24 사용자).

11-23 한국 증시 리포트: `Render KR market report` 가 TypeError 로 멈췄는데 실행은 성공 → 글이 안 나간 채 20:53 에 사람이 찾았다.
GitHub API 도 이런 단계를 success 로 적어서, 워크플로 안에서 steps.<id>.outcome 으로만 가릴 수 있다.

    python .github/scripts/soft_fail.py "한국 증시 리포트 그리기=${{ steps.kr_render.outcome }}" "…=…"

outcome 이 failure 인 것만 모아 Slack 한 통. SLACK_WEBHOOK_URL 이 없거나 실패가 없으면 조용히 끝난다. 이 스크립트는 실패하지 않는다(exit 0).
"""
import json
import os
import sys
import urllib.request

NAMES = {   # 워크플로 이름 → 한국어 (experiments/alert_ko.py NAMES 와 같게)
    "KR Stocks": "한국 종목 · 한국 증시 리포트",
    "NVDA Report": "엔비디아 · 시총 TOP 10 페이지",
    "Quick stock data (간단 정보 853종목)": "간단 정보 (853종목)",
}


def main():
    bad = [a.rsplit("=", 1)[0] for a in sys.argv[1:] if a.rsplit("=", 1)[-1] == "failure"]
    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not bad:
        print("소리 없는 실패 없음")
        return
    print("실패한 단계(실행은 계속): " + " · ".join(bad))
    if not url:
        return
    wf = os.environ.get("GITHUB_WORKFLOW", "")
    name = next((v for k, v in NAMES.items() if wf.startswith(k)), wf)
    link = f"https://github.com/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ.get('GITHUB_RUN_ID')}"
    text = (f"⚠️ 단계 실패 — {name}\n" + "".join(f"• {b}\n" for b in bad)
            + "실행은 계속 돌아 `성공` 으로 보이지만 이 단계에 기대는 글 · 페이지가 안 나갔을 수 있습니다.\n🔗 " + link)
    try:
        req = urllib.request.Request(url, data=json.dumps({"text": text, "unfurl_links": False}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=20)
    except Exception as e:  # noqa: BLE001
        print(f"Slack 보내기 실패: {type(e).__name__}")


if __name__ == "__main__":
    main()
