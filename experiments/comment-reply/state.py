"""처리한 댓글 ID 추적 (같은 댓글에 두 번 답하지 않게)

state 파일은 experiments/comment-reply/output/state.json — output/ 은 .gitignore 대상.
GitHub Actions 에서는 comment-state 브랜치에 보관해 실행 간 이어 간다.

2026-10-14 Firestore 이전: 키를 "fs_processed" 로 바꿨다. 예전 "processed" 는 블로거 댓글 ID 라 남겨만 둔다.
"fs_processed" 가 없으면 load() 가 None — main 이 첫 실행으로 보고 기준선만 잡는다.
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STATE_FILE = os.path.join(OUTPUT_DIR, "state.json")
KEY = "fs_processed"


def _read():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load():
    data = _read()
    if KEY not in data:
        return None
    return [str(i) for i in data[KEY]]


SINCE_KEY = "fs_last_created"   # 이어 읽을 시각 — 다음 실행은 이보다 10분 앞부터만 읽는다 (2026-10-21 3일 → 2026-11-09 10분)


def last_created():
    return _read().get(SINCE_KEY)


DAY_KEY = "fs_day"   # {"date": "YYYY-MM-DD"(KST), "replies": n} — 하루 AI 답글 상한용 (2026-11-09)


def day_count(today):
    d = _read().get(DAY_KEY) or {}
    return int(d.get("replies", 0)) if d.get("date") == today else 0


def save(processed, newest_created=None, day=None, day_add=0):
    """newest_created = 다음 실행이 이어 읽을 시각(못 다룬 가장 오래된 댓글, 없으면 가장 최근 댓글).
    2026-11-09 전에는 max() 로 앞으로만 갔다 — 이제 남은 댓글이 있으면 그 시각에 머문다."""
    data = _read()
    data[KEY] = [str(i) for i in processed]
    if newest_created:
        data[SINCE_KEY] = newest_created
    if day:
        data[DAY_KEY] = {"date": day, "replies": day_count(day) + day_add}
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
