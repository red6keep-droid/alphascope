"""미디어 데일리 전체 실행: 수집(Firestore) → 묶기 → 서술 → 렌더 → 기록 → 게시.

    python main.py --phase 1                 # 1차 (07:55 컷) dry-run
    python main.py --phase 2 --publish       # 2차 — 같은 날 글 갱신
    python main.py --fixture --no-llm        # Firestore · LLM 없이 틀 확인
    python main.py --state output/state      # CI: records/ 를 상태 폴더에
"""

import argparse
import os
import sys

from dotenv import load_dotenv

import cluster
import collect
import config
import publish
import render_html

sys.path.append(os.path.join(config.BASE_DIR, ".."))   # 뒤에 붙인다 — 이쪽 모듈 이름을 가리지 않게
import ops_log  # noqa: E402,F401  — 운영 기록 (experiments/ops_log.py, 2026-10-23)
import record_store  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, choices=(1, 2), default=2)
    ap.add_argument("--edition", default=config.today_kst())
    ap.add_argument("--state", help="상태 폴더 (records/)")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--fixture", action="store_true", help="Firestore 대신 가짜 재료")
    a = ap.parse_args()
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    print("[1/5] 수집")
    cutoff = config.PHASE1_CUTOFF if a.phase == 1 else None
    if a.fixture:
        items = collect.fixture(a.edition)
        if cutoff:
            items = [r for r in items if r["createdAt"][11:16] <= f"{cutoff[0]:02d}:{cutoff[1]:02d}"]
    else:
        items = collect.fetch(a.edition, cutoff)
    collect.save(items, a.edition)

    print("[2/5] 묶기")
    media, rows = cluster.build(phase=a.phase)
    if a.state:
        record_store.append(a.state, "issues", rows)   # 우리 기록 — 방송이 다룬 이슈 (source=ytb). 요약 문장 · 자막 없음
        record_store.append(a.state, "verdicts", [{"date": a.edition, "as_of": a.edition, "source": "ytb", "id": f"media/{a.phase}", "target": "market",
                                                   "n_items": media["n_items"], "n_channels": media["n_channels"],
                                                   "top": [{"issue": c["issue"], "topic": c["topic"], "n_videos": c["n_videos"], "n_channels": c["n_channels"], "split": c["split"], "surprise": c["surprise"]}
                                                           for c in media["clusters"][:3]]}])
    if media["n_items"] < config.MIN_ITEMS:
        print(f"재료 {media['n_items']}건 < {config.MIN_ITEMS} — 오늘은 글을 만들지 않는다")
        return

    print("[3/5] 서술" + (" — 건너뜀" if a.no_llm else ""))
    np_ = os.path.join(config.OUTPUT_DIR, "narrative.json")
    if os.path.exists(np_):
        os.remove(np_)   # 지난 실행의 문장이 오늘 글에 붙지 않게
    if not a.no_llm:
        import narrate
        try:
            narrate.narrate()
        except Exception as e:  # noqa: BLE001
            print(f"[narrate] 실패 — 파이썬 문장으로 렌더: {e}")

    print("[4/5] 렌더")
    render_html.render()

    print("[5/5] 게시" + ("" if a.publish else " — dry-run"))
    publish.publish(do_publish=a.publish)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
