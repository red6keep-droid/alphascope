"""③단계 — `cases` 테이블 초기화 (기획서 3절 `cases` · 13절 ③).

입력: `output/cases_survey.json` (cases_survey.py) + 아래 MANUAL 덮어쓰기 + `output/cases_survey.md`의 `확정` 열(1/0, 비우면 제안).
규칙 (2026-10-10 확정):
  - 저장: 미종결 사건 전부 + MANUAL에 있는 사건. 종결 사건은 저장하지 않는다.
  - watch=1: category='securities'이고 미종결 (+ MANUAL). "진행 중 사안" 섹션은 watch=1만 보여 준다.
  - 특허(NPE)는 watch=0으로 저장만 — 상태 전이(판결·합의·기각)가 생길 때만 이벤트.
멱등: INSERT OR REPLACE. status·last_activity_*는 이미 있는 행의 값을 보존한다 (전이는 cases_update가 쓴다).

    python experiments/nvda-report/cases_init.py            # 적용
    python experiments/nvda-report/cases_init.py --dry-run  # 표만
"""

import argparse
import json
import os
import re
import sys

import config
import db

# 사용자 수동 지정 (2026-10-10). CourtListener의 종결일이 틀렸거나 역할이 사건명에 없는 것.
MANUAL = {
    # In re NVIDIA Securities Litigation — CL은 2021-03-02 종결로 두지만 CA9 2023 파기환송 · 대법원 2024-12 상고 각하 → 지방법원 진행 중
    "cl:8490233": {"watch": 1, "status": "active", "role": "defendant",
                   "note": "CL 종결일 2021-03-02는 항소 전 기준. 2024-12 대법원 각하 후 지방법원 재개"},
    # Roots Informatics v. Microsoft — NVIDIA는 다수 피고 중 하나 (특허, NPE)
    "cl:72191993": {"role": "defendant"},
}


def confirmed_overrides(md_path):
    """검토 표의 `확정` 열(마지막 칸)에 1/0이 적힌 행만 읽는다. 사건번호로 매칭."""
    out = {}
    if not os.path.exists(md_path):
        return out
    for line in open(md_path, encoding="utf-8"):
        if not line.startswith("| ") or not line[2].isdigit():
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 12:
            continue
        m = re.search(r"\[([^\]]+)\]\(", cells[3])
        val = cells[-1]
        if m and val in ("0", "1"):
            out[m.group(1)] = int(val)
    return out


def build_rows(cases, md_overrides):
    rows, skipped = [], 0
    for c in cases:
        manual = MANUAL.get(c["case_id"], {})
        active = not c["terminated"] or manual.get("status") == "active"
        if not active:
            skipped += 1
            continue
        watch = 1 if (c["category"] == "securities" and active) else 0
        watch = manual.get("watch", watch)
        if c["docket_number"] in md_overrides:
            watch = md_overrides[c["docket_number"]]
        rows.append({
            "case_id": c["case_id"], "kind": "court",
            "title": c["title"], "court": c["court"], "docket_number": c["docket_number"], "url": c["url"],
            "role": manual.get("role", c["role"]), "category": c["category"],
            "status": manual.get("status", "active"),
            "opened_at": c["filed"], "watch": watch, "note": manual.get("note", ""),
        })
    return rows, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    cases = json.load(open(os.path.join(config.OUTPUT_DIR, "cases_survey.json"), encoding="utf-8"))
    md_overrides = confirmed_overrides(os.path.join(config.OUTPUT_DIR, "cases_survey.md"))
    rows, skipped = build_rows(cases, md_overrides)

    print(f"[cases] 검토 표 {len(cases)}건 → 저장 {len(rows)} (watch {sum(r['watch'] for r in rows)}) · 종결 제외 {skipped} · 확정 열 덮어쓰기 {len(md_overrides)}")
    for r in sorted(rows, key=lambda x: (-x["watch"], x["opened_at"]), reverse=False):
        print(f"  watch={r['watch']} {r['category']:10} {r['opened_at']} {r['court']:5} {r['docket_number']:16} {r['role']:9} {r['title'][:50]}" + (f"  — {r['note']}" if r['note'] else ""))
    if args.dry_run:
        return
    conn = db.connect()
    existing = {r["case_id"]: dict(r) for r in conn.execute("SELECT * FROM cases")}
    for r in rows:
        old = existing.get(r["case_id"], {})
        conn.execute(
            """INSERT OR REPLACE INTO cases(case_id, kind, title, court, docket_number, url, role, category, status,
                                            opened_at, last_activity_at, last_activity_summary, watch)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (r["case_id"], r["kind"], r["title"], r["court"], r["docket_number"], r["url"], r["role"], r["category"],
             old.get("status") or r["status"], r["opened_at"],
             old.get("last_activity_at"), old.get("last_activity_summary"), r["watch"]))
    db.set_meta(conn, "cases_initialized", db.now_iso())
    conn.commit()
    n_watch = conn.execute("SELECT COUNT(*) FROM cases WHERE watch = 1").fetchone()[0]
    print(f"[cases] 저장 완료 — cases {conn.execute('SELECT COUNT(*) FROM cases').fetchone()[0]}행 · watch {n_watch}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
