"""기록 사본 — 비공개 상태 저장소(alphascope-state)의 모든 브랜치를 '지금 내용 한 벌'로 묶는다 (2026-11-24 사용자, 헌법 제4조 8항 "기록은 한 곳에만 두지 않는다").

    python experiments/state_backup.py --mirror <alphascope-state 를 --mirror 로 받은 폴더> --out <사본 폴더> [--prev <지난 사본의 manifest.json>]

- 왜 한 벌인가: 이력까지 복사하면 91MB(11-24) + 한 주 55MB 씩 는다(날마다 다시 쓰는 큰 작업 파일 때문). 기록은 덧붙이기만 하는 파일이라
  최신 한 벌에 과거가 다 들어 있다 → 한 벌 = 압축 26MB(11-24 실측).
- 만드는 것: --out/alphascope-state/{브랜치}.tar.gz (git archive 그대로) · --out/manifest.json
    manifest = 브랜치마다 커밋 · 커밋 시각 · 파일 수 · 크기, 기록 파일(records/ · history/ · raw/ · 날짜 파일)마다 크기.
- 줄어듦 검사(--prev): 지난 사본보다 **기록 파일이 사라졌거나 작아졌으면** 종료 코드 3 — 부르는 쪽이 사본을 덮어쓰지 않고 알린다.
  (원본이 지워진 날 사본까지 따라 지워지지 않게. 작업 파일 · 통째로 덮어쓰는 브랜치는 검사하지 않는다.)
- 올리는 곳 · 세대(날마다 1 + 주마다 4)는 워크플로(state-backup.yml)가 맡는다. AI 0 · 수집 0.
"""
import argparse
import datetime
import gzip
import json
import os
import re
import subprocess
import sys

RECORD = re.compile(r"(^|/)records/|/history/|(^|/)regime\.jsonl$|option_snapshots\.jsonl$|est_history\.json$|(^|/)kr/raw/|(^|/)kr/facts/\d{4}-")
# 덧붙이기만 하는 파일 — 작아지면 안 된다. (kr/facts 의 latest.json · index.json, records 안의 덮어쓰는 json 은 뺌)
APPEND = re.compile(r"\.jsonl(\.gz)?$|(^|/)kr/raw/|/history/\d{4}-\d{2}-\d{2}\.json$|(^|/)kr/facts/\d{4}-\d{2}-\d{2}\.json$|seen\.txt$")


def git(mirror, *a):
    return subprocess.run(["git", "-C", mirror, *a], capture_output=True, check=True).stdout


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--mirror", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prev")
    a = ap.parse_args()
    dst = os.path.join(a.out, "alphascope-state")
    os.makedirs(dst, exist_ok=True)
    man = {"made": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "branches": {}}
    total = 0
    for b in git(a.mirror, "for-each-ref", "--format=%(refname:short)", "refs/heads").decode().split():
        sha, at = git(a.mirror, "log", "-1", "--format=%H %cI", b).decode().split()
        files, recs, size = 0, {}, 0
        for line in git(a.mirror, "-c", "core.quotepath=false", "ls-tree", "-r", "-l", b).decode("utf-8").splitlines():
            meta, path = line.split("\t", 1)
            n = int(meta.split()[3])
            files, size = files + 1, size + n
            if RECORD.search(path):
                recs[path] = n
        tar = git(a.mirror, "archive", "--format=tar", b)
        p = os.path.join(dst, f"{b}.tar.gz")
        with gzip.GzipFile(p, "wb", compresslevel=6, mtime=0) as f:   # mtime 0 — 내용이 같으면 파일도 같게
            f.write(tar)
        total += os.path.getsize(p)
        man["branches"][b] = {"commit": sha, "at": at, "files": files, "bytes": size, "gz": os.path.getsize(p), "records": recs}
        print(f"{b:18} 커밋 {sha[:8]} {at[:16]} · 파일 {files} · 압축 {os.path.getsize(p) / 1e6:.1f}MB · 기록 파일 {len(recs)}")
    shrunk = []
    if a.prev and os.path.exists(a.prev):
        with open(a.prev, encoding="utf-8") as f:
            prev = json.load(f)
        for b, pb in (prev.get("branches") or {}).items():
            now = (man["branches"].get(b) or {}).get("records") or {}
            if b not in man["branches"]:
                if pb.get("records"):
                    shrunk.append(f"{b}: 브랜치가 없어짐")
                continue
            for path, n in (pb.get("records") or {}).items():
                if not APPEND.search(path):
                    continue
                if path not in now:
                    shrunk.append(f"{b}:{path} 없어짐")
                elif now[path] < n and not path.endswith(".gz"):   # gzip 은 다시 묶으면 조금 달라질 수 있어 크기 비교 안 함(없어짐만 본다)
                    shrunk.append(f"{b}:{path} {n} → {now[path]} 바이트")
    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    print(f"한 벌 {len(man['branches'])} 브랜치 · 압축 합계 {total / 1e6:.1f}MB")
    if shrunk:
        print(f"::error::기록이 줄었다 {len(shrunk)}건 — 사본을 덮어쓰지 않는다: " + " | ".join(shrunk[:10]))
        sys.exit(3)


if __name__ == "__main__":
    main()
