"""오늘(KST) 같은 워크플로가 실패했다가 이번 실행에서 게시에 성공했을 때만 Slack 에 '다시 성공' 알림.

평소 성공에는 아무것도 보내지 않는다 (2026-11-10 사용자: "발행 실패 뒤 성공 알림까지, 일반 성공 알림은 안 돼").
실패 알림(🚨 워크플로 실패)은 job 이 failure 로 끝날 때 나가므로, 오늘 failure 로 끝난 실행이 있으면 실패 알림이 나간 것으로 본다.

    python .github/scripts/notify_recovered.py "<이름>" <post_meta.json>

환경: SLACK_WEBHOOK_URL, GITHUB_TOKEN(actions: read), GITHUB_REPOSITORY, GITHUB_WORKFLOW_REF, GITHUB_RUN_ID, GITHUB_SERVER_URL
어떤 오류도 워크플로를 멈추지 않는다 (알림은 덤).
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def main():
    label, meta_path = sys.argv[1], sys.argv[2]
    hook = os.environ.get("SLACK_WEBHOOK_URL")
    token = os.environ.get("GITHUB_TOKEN")
    if not hook or not token or not os.path.exists(meta_path):
        print("알림 건너뜀 (웹훅 · 토큰 · 게시 기록 중 없음)")
        return
    repo = os.environ["GITHUB_REPOSITORY"]
    # owner/repo/.github/workflows/x.yml@refs/heads/main → x.yml
    wf = os.environ["GITHUB_WORKFLOW_REF"].split("@")[0].rsplit("/", 1)[-1]
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    since = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    q = urllib.parse.urlencode({"status": "failure", "per_page": 50,
                                "created": ">=" + since.strftime("%Y-%m-%dT%H:%M:%SZ")})
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/{wf}/runs?{q}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        runs = [x for x in json.load(r).get("workflow_runs", []) if str(x.get("id")) != run_id]
    if not runs:
        print("오늘 실패한 실행 없음 — 평소 성공은 알리지 않는다")
        return
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    text = (f"✅ 다시 성공 — {label} 게시됨 (오늘 실패 {len(runs)}회 뒤)\n"
            f"📝 {meta.get('title', '')}\n{meta.get('url', '')}\n"
            f"🔗 {server}/{repo}/actions/runs/{run_id}")
    data = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    urllib.request.urlopen(urllib.request.Request(hook, data=data, headers={"Content-Type": "application/json"}), timeout=20)
    print(f"다시 성공 알림 보냄 (오늘 실패 {len(runs)}회)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 알림 실패로 워크플로를 멈추지 않는다
        print(f"::warning::다시 성공 알림 실패: {type(e).__name__}")
