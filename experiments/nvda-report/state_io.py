"""GitHub Actions용 상태 내보내기·불러오기 (⑤단계, 2026-10-10).

러너는 매번 빈 DB로 시작한다. trump-trend처럼 테이블별로 고르지 않고 **모든 테이블을 JSONL 한 벌로** 내보내고 그대로 되돌린다
— 테이블이 10개이고 다 작아서(DB 0.9 MB) 코드가 짧은 쪽이 낫다. 텍스트라 git delta 압축이 잘 된다.

    output/state/<table>.jsonl   한 줄 = 행 하나 (컬럼명 포함)

불러오기: `INSERT OR IGNORE` (meta만 OR REPLACE). 로컬 DB에 이미 있는 행은 건드리지 않는다 — 새로 받은 값이 우선.
내보내기: 판정 뒤에 돈다 (분류·추출·판정 결과까지 담기게).
"""

import json
import os

import db

TABLES = ["items", "daily_state", "option_snapshots", "calendar", "cases", "quarterly", "monthly", "filings_text", "daily_bars", "meta"]


def import_state(conn, state_dir):
    if not state_dir or not os.path.isdir(state_dir):
        print(f"[state] 불러올 디렉터리 없음: {state_dir} (첫 실행이면 정상)")
        return 0
    total = 0
    for table in TABLES:
        path = os.path.join(state_dir, f"{table}.jsonl")
        if not os.path.exists(path):
            continue
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        if not rows:
            continue
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({table})")]
        keep = [c for c in cols if c in rows[0]]
        verb = "INSERT OR REPLACE" if table == "meta" else "INSERT OR IGNORE"
        conn.executemany(
            f"{verb} INTO {table}({', '.join(keep)}) VALUES ({', '.join('?' for _ in keep)})",
            [tuple(r.get(c) for c in keep) for r in rows])
        total += len(rows)
        print(f"[state] {table}: {len(rows):,}행")
    conn.commit()
    return total


def export_state(conn, state_dir):
    os.makedirs(state_dir, exist_ok=True)
    total = 0
    for table in TABLES:
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
        with open(os.path.join(state_dir, f"{table}.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        total += len(rows)
    print(f"[state] {len(TABLES)}개 테이블 {total:,}행 → {state_dir}")
    return total
