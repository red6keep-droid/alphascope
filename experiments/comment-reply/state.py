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


def save(processed):
    data = _read()
    data[KEY] = [str(i) for i in processed]
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
