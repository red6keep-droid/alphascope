"""이슈 모니터링 — 블로그 고정 페이지 본문 만들기 + 날마다 기록 (2026-11-13 사용자: 운영 연결 + 바로 공개).

    python experiments/issue_store/issue_watch_daily.py --state "$STATE_DIR"

화면은 목업과 같은 코드(mock_issue_watch.build, PUBLIC=True)로 그린다 — 목업에서 고친 것이 그대로 블로그에 간다.
- 본문 = output/issue/{slug}.html (issue-iran · issue-tariff · issue-export), 게시는 publish_issue.py
- 구글 뉴스 캐시 = {state}/records/issues/gnews_cache.json (지난 날은 다시 안 받는다, 60일 지나면 지움)
- 기록 = {state}/records/issues/{ID}.jsonl 하루 한 줄 (같은 날 다시 돌면 그 줄을 바꿔 씀)
AI = --ai 일 때만(하루 한 번): 새 사건의 방향 · 실제로 일어났나 · 단계를 묶어 판정(llm_chain json-backup-first, 20건 묶음 · 이슈마다 최대 5회 · 2분, 캐시 stage_ai.json).
새 수집 = 구글 뉴스 한국어 검색(이슈 3개 × 오늘 · 어제, 실행당 6번) · 시세 yfinance.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mock_issue_watch as IW  # noqa: E402

OUT = os.path.join(HERE, "output", "issue")


def save_log(rec_dir, iid, row):
    path = os.path.join(rec_dir, f"{iid}.jsonl")
    lines = []
    if os.path.exists(path):
        lines = [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
    lines = [x for x in lines if x.get("day") != row["day"]] + [row]
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines))


def home_cards(logs, made=None):
    """홈 `Hot Issue` 카드 자료(gh-pages issues.json) — 이슈마다 이름 · 페이지 · 최근 일주일 뉴스 쪽(바늘 말) · 평소보다 뉴스 많음. AI 0 (2026-11-16 사용자).
    바늘 말 색 = 좋은 쪽(종전 · 완화) 빨강 positive · 나쁜 쪽(확전 · 강화) 파랑 negative · 방향미정 = `향방미정` 회색."""
    import datetime as _dt
    out = []
    for iss in IW.ISSUES:
        row = logs.get(iss["id"]) or {}
        if not row:
            continue
        c = IW.CFG[iss["id"]]
        g = row.get("gauge") or "방향미정"
        kind = "positive" if c["good"] in g else "negative" if c["bad"] in g else "neutral"
        out.append({"id": iss["id"], "name": iss["name"], "url": f"/p/{c['slug']}.html", "gauge": "향방미정" if g == "방향미정" else g,
                    "kind": kind, "hot": bool(row.get("hot"))})
    return {"generated": made or _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="minutes"), "issues": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True, help="상태 저장소 폴더 (워크플로 STATE_DIR)")
    ap.add_argument("--ai", action="store_true", help="새 사건 AI 판정(하루 한 번 — 07:30 본 실행만). 없으면 저장된 판정만 쓴다")
    a = ap.parse_args()
    rec = os.path.join(a.state, "records", "issues")
    os.makedirs(rec, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    IW.PUBLIC = True
    IW.GN_CACHE = os.path.join(rec, "gnews_cache.json")
    IW.AI_CACHE = os.path.join(rec, "stage_ai.json")
    IW.AI_ON = a.ai
    pages = IW.build()
    for slug, body in pages.items():
        with open(os.path.join(OUT, f"{slug}.html"), "w", encoding="utf-8") as f:
            f.write(body)
        print(f"[issue-watch] {slug}: {len(body):,}자")
    for iid, row in IW.build.logs.items():
        save_log(rec, iid, row)
        print(f"[issue-watch] {iid}: {row['state']} · 48시간 {row['n48']}건 · 바늘 {row['gauge']}")
    hc = home_cards(IW.build.logs)
    with open(os.path.join(OUT, "issues.json"), "w", encoding="utf-8") as f:   # 홈 카드 — 워크플로가 deploy-forecast/ 로 옮겨 gh-pages 에 (07:30 본 실행)
        json.dump(hc, f, ensure_ascii=False)
    print(f"[issue-watch] 홈 카드 {len(hc['issues'])}개")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
