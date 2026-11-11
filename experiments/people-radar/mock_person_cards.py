"""인물 페이지 요약 카드 목업 (2026-11-11 사용자) — 상태 저장소의 마지막 레이더(radar.json) + 발언 기록(statements.jsonl)으로
7일 집계(person7)를 채워 실제 렌더러로 그린다. 인터넷 · AI 0. 글은 블로그에 나가지 않는다.

    git fetch state radar-state
    python experiments/people-radar/mock_person_cards.py   → output/mock_person_cards.html (목업 서버 `인물 발언` 묶음)
"""
import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE)]
import aggregate as A  # noqa: E402
import render_html as R  # noqa: E402
import design_kit as dk  # noqa: E402

REF, BASE = "state/radar-state", "experiments/people-radar/output/state/"


def _show(path):
    r = subprocess.run(["git", "show", f"{REF}:{BASE}{path}"], capture_output=True, text=True, encoding="utf-8", cwd=HERE)
    if r.returncode:
        sys.exit(f"상태 저장소를 못 읽었습니다 — 먼저 `git fetch state radar-state` ({r.stderr.strip()[:120]})")
    return r.stdout


def main():
    radar = json.loads(_show("radar.json"))
    narrative = json.loads(_show("narrative.json") or "null")
    rows = [json.loads(x) for x in _show("statements.jsonl").splitlines() if x.strip()]
    rows = [x for x in rows if x.get("analyzed_at") and not x.get("noise_reason") and (x.get("ai_market_relevance") or 0) >= A.RELEVANCE_EVENT_MIN]
    end = datetime.datetime.strptime(radar["generated_at"], "%Y-%m-%dT%H:%M:%SZ")
    now7 = []
    for d in range(A.TREND_DAYS):   # aggregate.history 와 같이 하루씩 묶는다
        lo, hi = (end - datetime.timedelta(days=d + 1)).strftime("%Y-%m-%dT%H:%M:%SZ"), (end - datetime.timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ")
        now7 += A.build_signals([x for x in rows if lo <= (x.get("published_at") or "") < hi])
    radar["person7"] = A.person_counts(now7)
    body = R.build_body(radar, narrative, R.today_kst())
    out = os.path.join(HERE, "output", "mock_person_cards.html")
    dk.write_mock(body, out, "주요 인물 발언 — 인물 카드 목업")
    print(out)
    for p in radar["people"]:
        c = radar["person7"].get(p["speaker"], {})
        print(f'  {p["name_ko"]}: 오늘 {len(p["signals"])} · 7일 {c.get("n", 0)}')


if __name__ == "__main__":
    main()
