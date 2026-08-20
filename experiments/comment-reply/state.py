"""처리 완료 댓글 ID 추적 (중복 알림 방지)

state 파일은 experiments/comment-reply/output/state.json 에 저장된다.
디렉토리는 .gitignore 에 등록되어 있어 커밋되지 않는다.
GitHub Actions 에서는 별도 분기(comment-state)로 보관해 실행 간 지속시킨다.
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STATE_FILE = os.path.join(OUTPUT_DIR, "state.json")


def load():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [str(i) for i in data.get("processed", [])]
        except Exception:
            return []
    return []


def save(processed):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"processed": [str(i) for i in processed]}, f, ensure_ascii=False, indent=2)