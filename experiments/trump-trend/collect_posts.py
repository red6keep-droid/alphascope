"""CNN Truth archive → 새 게시물만 SQLite에 저장 (기획서 1·2절).

archive는 2022년부터 전체 게시물이 담긴 JSON 하나(약 20MB)다. 매일 통째로 받아
DB에 없는 id만 넣는다. 새로 들어온 행은 data/raw/posts/YYYY-MM-DD.jsonl 에도 남긴다.
"""

import datetime
import json
import os
import sys

import requests

import config
import db
import prefilter


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm_ts(value):
    """'2026-09-15T03:54:14.586Z' → '2026-09-15T03:54:14Z' (UTC 고정)."""
    dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_archive(url=config.CNN_ARCHIVE_URL):
    print(f"[posts] archive 요청: {url}")
    resp = requests.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=config.HTTP_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        data = data.get("data") or data.get("posts") or []
    print(f"[posts] archive 게시물 {len(data):,}건")
    return data


def normalize(record):
    content = record.get("content") or ""
    media = record.get("media") or []
    return {
        "id": str(record["id"]),
        "published_at": _norm_ts(record["created_at"]),
        "content": content,
        "source": config.SOURCE_NAME,
        "source_url": record.get("url"),
        "media_count": len(media),
        "noise_reason": prefilter.noise_reason(content, len(media)),
    }


def upsert_new(conn, records):
    existing = {r["id"] for r in conn.execute("SELECT id FROM trump_posts")}
    now = _utc_now()
    new_rows = []
    for rec in records:
        if not rec.get("id") or str(rec["id"]) in existing:
            continue
        row = normalize(rec)
        row["collected_at"] = now
        new_rows.append(row)

    conn.executemany(
        """INSERT OR IGNORE INTO trump_posts
           (id, published_at, content, source, source_url, media_count, collected_at, noise_reason)
           VALUES (:id, :published_at, :content, :source, :source_url, :media_count, :collected_at, :noise_reason)""",
        new_rows,
    )
    conn.commit()
    return new_rows


def write_raw_snapshot(new_rows):
    if not new_rows:
        return None
    os.makedirs(config.RAW_POSTS_DIR, exist_ok=True)
    day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(config.RAW_POSTS_DIR, f"{day}.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        for row in new_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def refilter(conn):
    """사전 필터 규칙이 바뀌었을 때 전체 행의 noise_reason을 다시 계산한다.
    분류가 끝난 행도 noise_reason이 붙으면 이벤트에서 빠진다 (cluster가 noise_reason IS NULL만 본다)."""
    rows = conn.execute("SELECT id, content, media_count, noise_reason FROM trump_posts").fetchall()
    changes = []
    for r in rows:
        new = prefilter.noise_reason(r["content"], r["media_count"])
        if new != r["noise_reason"]:
            changes.append((new, r["id"]))
    conn.executemany("UPDATE trump_posts SET noise_reason = ? WHERE id = ?", changes)
    conn.commit()
    print(f"[posts] 사전 필터 재적용 — {len(rows):,}행 중 {len(changes):,}행 변경")
    return len(changes)


def collect(conn):
    records = fetch_archive()
    new_rows = upsert_new(conn, records)
    path = write_raw_snapshot(new_rows)
    total = conn.execute("SELECT COUNT(*) FROM trump_posts").fetchone()[0]
    noisy = sum(1 for r in new_rows if r["noise_reason"])
    print(f"[posts] 신규 {len(new_rows):,}건 (사전 필터 노이즈 {noisy:,}) · 누적 {total:,}건"
          + (f" · 원본 {path}" if path else ""))
    db.set_meta(conn, "posts_last_collected_at", _utc_now())
    conn.commit()
    return len(new_rows)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    collect(db.connect())
