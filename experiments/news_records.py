"""뉴스 분류 기록 — 8일 창으로 덮어쓰는 뉴스 처리 결과를 날짜별로 쌓는다.

    python experiments/news_records.py --source quick --store /tmp/qn/news.json --out <news-records 꺼낸 폴더>
    python experiments/news_records.py --source home  --store news_store_home.json --out <…>

- 새는 곳이던 것: 간단 종목 뉴스(quick-news-state news.json, 미국 452종목 · 하루 약 540건)와 홈 미국 뉴스(gh-pages news_store_home.json, CNBC)는
  KEEP_DAYS · STORE_DAYS = 8 이 지나면 분류(issue · area · market_dir · stage · scores · fact …)가 지워졌다. 그때의 모델 · 그때의 판단은 다시 못 만든다.
- 쓰는 곳: --out/records/{source}/{YYYY}/{MM-DD}.jsonl.gz — 날짜 = 기사 published_at(UTC). 한 줄 = 처리된 기사 한 건 그대로.
  처음 보는 item_id 만 덧붙인다(gzip 이어 쓰기 — 읽을 때 한 파일로 읽힘). 이미 쓴 줄은 고치지 않는다 — 나중에 다시 분류돼도 첫 판단이 기록.
  item_id 목록 = --out/records/{source}/seen.txt (한 줄에 하나).
- 크기: 간단 종목 하루 약 140KB · 홈 하루 수 KB(gzip, 11-24 어림) → 1년 약 50MB. 비공개 상태 저장소 news-records 브랜치(일반 푸시, 이력 유지).
- AI 0 · 수집 0 — 이미 만든 파일을 옮겨 적기만.
"""
import argparse
import gzip
import json
import os
import sys


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=["quick", "home"])
    ap.add_argument("--store", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if not os.path.exists(a.store):
        print(f"[news-records] {a.source}: 처리 결과 파일 없음 — 건너뜀")
        return
    with open(a.store, encoding="utf-8") as f:
        store = json.load(f)
    items = list(store.values()) if isinstance(store, dict) else list(store)
    base = os.path.join(a.out, "records", a.source)
    os.makedirs(base, exist_ok=True)
    seen_p = os.path.join(base, "seen.txt")
    seen = set()
    if os.path.exists(seen_p):
        with open(seen_p, encoding="utf-8") as f:
            seen = {x.strip() for x in f if x.strip()}
    by_day, new_ids = {}, []
    for it in items:
        iid = str(it.get("item_id") or "")
        if not iid or iid in seen:
            continue
        day = str(it.get("published_at") or it.get("published") or "")[:10] or "unknown"
        by_day.setdefault(day, []).append(it)
        new_ids.append(iid)
        seen.add(iid)
    for day, rows in sorted(by_day.items()):
        d = os.path.join(base, day[:4] if day != "unknown" else "unknown")
        os.makedirs(d, exist_ok=True)
        with gzip.open(os.path.join(d, f"{day[5:] if day != 'unknown' else 'unknown'}.jsonl.gz"), "at", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(seen_p, "a", encoding="utf-8") as f:
        for iid in new_ids:
            f.write(iid + "\n")
    print(f"[news-records] {a.source}: 처리 결과 {len(items)}건 중 새로 {len(new_ids)}건 기록 · 날짜 {sorted(by_day)} · 모두 {len(seen)}건")


if __name__ == "__main__":
    main()
