"""GitHub Actions용 상태 내보내기 · 불러오기 (trump-trend state_io 와 같은 방식).

런너는 매번 빈 환경이다. 다시 만들 수 없는 것 = LLM 결과(인용 추출 · 분류)와 수집 창(72시간)을 지난 항목.
statements 전체 행을 최근 STATE_KEEP_DAYS 일만 JSONL 로 남긴다 — 접힘 '인물별 추이'(7일)와 같은 발언 재수집 방지에 쓴다.
불러오기는 수집 앞에 돈다: 같은 id 는 수집기가 INSERT OR IGNORE 로 건너뛰어 LLM 결과가 유지된다.

    statements.jsonl   한 줄 = statements 한 행
"""

import datetime
import json
import os

STATE_KEEP_DAYS = 30


def import_state(conn, path):
    if not path or not os.path.exists(path):
        print(f"[state] 불러올 파일 없음: {path} (첫 실행이면 정상)")
        return 0
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(statements)")]
    n = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            keys = [c for c in cols if c in r]
            cur = conn.execute(f"INSERT OR IGNORE INTO statements({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)})",
                               [r[c] for c in keys])
            n += cur.rowcount
    conn.commit()
    print(f"[state] statements {n:,}행 불러옴 ← {path}")
    return n


def export_state(conn, path):
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=STATE_KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = [dict(r) for r in conn.execute("SELECT * FROM statements WHERE published_at >= ? ORDER BY published_at, id", (since,))]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[state] statements {len(rows):,}행 → {path}")
    return len(rows)
