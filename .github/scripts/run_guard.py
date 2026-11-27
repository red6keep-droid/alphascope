"""정기 실행 중복 막기 — 이 실행이 맡은 일을 다른 실행이 이미 했나(또는 하는 중인가).

    python .github/scripts/run_guard.py --workflow quick-data.yml --job quick [--title-suffix "· kr"]

왜: Cloudflare Worker 가 정시에 걸고, GitHub cron 은 예비로 둔다. 예비가 6~10시간 늦게 오는 날이 잦다
    (11-17: 06:40 간단 종목 뉴스 예비가 13:09 에 와 AI 까지 18분 다시 돌았다 · 어제 16:10 한국 종목 예비가 새벽 01:57 에 와
    홈 증시 전망 파일을 02:28 판으로 덮었다 · 17:40 한국 간단 종목 예비가 03:54 에 와 46분 다시 받았다).
    옛 장치 `최근 6시간 안 성공` 은 6시간 넘게 늦은 예비를 못 막았다.

어떻게:
  - GitHub 예약(schedule): 그 cron 의 예정 시각을 거꾸로 계산해 `예정 − 90분` 뒤에 시작된 실행을 본다 — 몇 시간 늦게 와도 같은 칸으로 센다.
    90분 = 서머타임 철에 Worker(뉴욕 시각)가 UTC cron 보다 한 시간 일찍 거는 것까지.
  - Worker · 이어 붙인 실행(workflow_dispatch scheduled=true · workflow_run): 옛 그대로 최근 6시간.
  - `한 것` = 본 잡(--job)이 성공으로 끝난 실행, 또는 아직 돌고 있는 실행. 확인 잡만 돌고 본 잡을 건너뛴 실행은 세지 않는다
    (그런 실행이 `성공` 으로 남아 뒤 실행을 잘못 막지 않게).
  - 사람이 누른 실행(scheduled 아님)은 이 스크립트를 부르지 않는다 — 늘 돈다.

출력: GITHUB_OUTPUT 에 skip=true|false. API 를 못 읽으면 skip=false(돌린다 — 빠지는 것보다 한 번 더 도는 쪽).
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

UTC = dt.timezone.utc
KST = dt.timezone(dt.timedelta(hours=9))


def _field(spec, lo, hi):
    out = set()
    for part in spec.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/")
            step = int(s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            a, b = (int(x) for x in part.split("-"))
        else:
            a = b = int(part)
        out.update(range(a, b + 1, step))
    return out


def planned_time(cron, now):
    """now 이전(같거나)의 가장 가까운 예정 시각 (UTC). 못 찾으면 None."""
    m, h, dom, mon, dow = cron.split()
    M, H, D, MO = _field(m, 0, 59), _field(h, 0, 23), _field(dom, 1, 31), _field(mon, 1, 12)
    W = {x % 7 for x in _field(dow, 0, 7)}
    t = now.replace(second=0, microsecond=0)
    for _ in range(60 * 48):
        if t.minute in M and t.hour in H and t.day in D and t.month in MO and (t.weekday() + 1) % 7 in W:
            return t
        t -= dt.timedelta(minutes=1)
    return None


def api(path):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}{path}",
        headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--job", required=True, help="본 잡 이름 — 이 잡이 성공한 실행만 `한 것` 으로 센다")
    ap.add_argument("--title-suffix", default="", help="실행 이름이 이 글자로 끝나는 것만 (간단 종목 주가 = 시장별)")
    a = ap.parse_args()

    now = dt.datetime.now(UTC)
    me = int(os.environ["GITHUB_RUN_ID"])
    cron = os.environ.get("SCHEDULE", "")
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and cron:
        p = planned_time(cron, now)
        since = (p or now - dt.timedelta(hours=6)) - dt.timedelta(minutes=90 if p else 0)
        why = f"예비 실행 · 예정 {p.astimezone(KST):%m-%d %H:%M} KST · {int((now - p).total_seconds() // 60)}분 늦음" if p else "예비 실행 · 예정 시각 계산 실패 → 최근 6시간"
    else:
        since = now - dt.timedelta(hours=6)
        why = "정시 · 이어 붙인 실행 → 최근 6시간"

    skip, seen = False, []
    try:
        runs = api(f"/actions/workflows/{a.workflow}/runs?created=%3E%3D{since:%Y-%m-%dT%H:%M:%SZ}&per_page=50").get("workflow_runs", [])
        for r in runs:
            if r["id"] == me or r["event"] not in ("schedule", "workflow_dispatch", "workflow_run"):
                continue
            if a.title_suffix and not (r.get("display_title") or "").endswith(a.title_suffix):
                continue
            if r["status"] != "completed":
                seen.append(f"{r['id']} 도는 중"); skip = True; break
            if r["conclusion"] != "success":
                continue
            jobs = api(f"/actions/runs/{r['id']}/jobs?per_page=50").get("jobs", [])
            if any(j["name"] == a.job and j.get("conclusion") == "success" for j in jobs):
                seen.append(f"{r['id']} 성공"); skip = True; break
    except Exception as e:  # 못 읽으면 돌린다
        print(f"실행 목록을 못 읽음 — 돌린다: {e!r}")
        skip = False

    print(f"[중복 확인] {a.workflow} {a.title_suffix} · {why} · 기준 {since.astimezone(KST):%m-%d %H:%M} KST 뒤 · "
          f"{'이미 함(' + ', '.join(seen) + ') → 건너뜀' if skip else '한 실행 없음 → 돈다'}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"skip={'true' if skip else 'false'}\n")


if __name__ == "__main__":
    sys.exit(main())
