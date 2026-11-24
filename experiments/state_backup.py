"""기록 사본 — 비공개 상태 저장소(alphascope-state)의 모든 브랜치를 '지금 내용 한 벌'로, 파일마다 따로 압축해 둔다 (2026-11-24 사용자, 헌법 제4조 8항 "기록은 한 곳에만 두지 않는다").

    python experiments/state_backup.py --mirror <alphascope-state 를 --mirror 로 받은 폴더> --out <사본 폴더> [--prev <지난 사본의 manifest.json>]

- 왜 한 벌인가: 이력까지 복사하면 91MB(11-24) + 한 주 55MB 씩 는다(날마다 다시 쓰는 큰 작업 파일 때문). 기록은 덧붙이기만 하는 파일이라
  최신 한 벌에 과거가 다 들어 있다 → 한 벌 = 압축 약 27MB(11-24 실측).
- 왜 파일마다인가(11-24 사용자 "여유가 있는지 확인해야"): 브랜치 통째 묶음은 ① 하나가 1 ~ 2년 뒤 GitHub 파일 한도(50MB 경고 · 100MB 거부)에 닿고
  ② 한 줄만 바뀌어도 묶음 전체가 새 파일이 된다. 파일마다 압축하면 안 바뀐 파일은 같은 내용 → git 이 다시 올리지 않는다.
- 만드는 것: --out/alphascope-state/{브랜치}/{원래 경로}.gz (이미 .gz 인 파일은 그대로) · --out/manifest.json
    압축이 SPLIT_MB 를 넘으면 `.gz.000` · `.gz.001` … 조각으로 나눈다(되살리기 = 이어 붙인 뒤 gunzip). 넘은 파일은 manifest `big` 에.
    manifest = 브랜치마다 커밋 · 커밋 시각 · 파일 수 · 크기, 기록 파일(records/ · history/ · raw/ · 날짜 파일)마다 크기.
- 줄어듦 검사(--prev): 지난 사본보다 **기록 파일이 사라졌거나 줄 수가 줄었으면** 종료 코드 3 — 부르는 쪽이 사본을 덮어쓰지 않고 알린다.
  (원본이 지워진 날 사본까지 따라 지워지지 않게. 작업 파일 · 통째로 덮어쓰는 브랜치는 검사하지 않는다.)
- 조각으로 나눈 파일이 있으면 종료 코드 4 — 사본은 만들어졌고(올려도 됨), 부르는 쪽이 알림만 보낸다(기록 구조를 손볼 때).
- 올리는 곳 · 세대(날마다 1 + 주마다 4)는 워크플로(state-backup.yml)가 맡는다. AI 0 · 수집 0.
"""
import argparse
import datetime
import gzip
import io
import json
import os
import re
import subprocess
import sys
import tarfile

SPLIT_MB = 40   # GitHub 파일 경고 50MB 아래
RECORD = re.compile(r"(^|/)records/|/history/|(^|/)regime\.jsonl$|option_snapshots\.jsonl$|est_history\.json$|(^|/)kr/raw/|(^|/)kr/facts/\d{4}-")
# 덧붙이기만 하는 파일 — 작아지면 안 된다. (kr/facts 의 latest.json · index.json, records 안의 덮어쓰는 json 은 뺌)
APPEND = re.compile(r"\.jsonl(\.gz)?$|(^|/)kr/raw/|/history/\d{4}-\d{2}-\d{2}\.json$|(^|/)kr/facts/\d{4}-\d{2}-\d{2}\.json$|seen\.txt$")


def git(mirror, *a):
    # 줄바꿈 변환 끔 — 윈도우 git(core.autocrlf=true)은 archive 에서 줄마다 CR 을 붙여 원본과 달라진다(11-24 첫 사본이 그랬고, 줄어듦 검사가 잡음)
    return subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", "-C", mirror, *a], capture_output=True, check=True).stdout


def write_file(dst_dir, path, data, big):
    """원래 경로 그대로 + .gz. 이미 gzip 이면 그대로. SPLIT_MB 넘으면 조각."""
    is_gz = path.endswith(".gz")
    blob = data if is_gz else gzip.compress(data, compresslevel=6, mtime=0)   # mtime 0 — 내용이 같으면 파일도 같게
    base = os.path.join(dst_dir, path if is_gz else path + ".gz")
    os.makedirs(os.path.dirname(base), exist_ok=True)
    lim = SPLIT_MB * 1024 * 1024
    if len(blob) <= lim:
        with open(base, "wb") as f:
            f.write(blob)
        return len(blob)
    for i in range(0, len(blob), lim):
        with open(f"{base}.{i // lim:03d}", "wb") as f:
            f.write(blob[i:i + lim])
    big.append(f"{path} {len(blob) / 1e6:.0f}MB → {(len(blob) + lim - 1) // lim}조각")
    return len(blob)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--mirror", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prev")
    a = ap.parse_args()
    dst = os.path.join(a.out, "alphascope-state")
    os.makedirs(dst, exist_ok=True)
    man = {"made": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "format": "file-gz-1", "split_mb": SPLIT_MB, "branches": {}, "big": []}
    total, biggest = 0, (0, "")
    for b in git(a.mirror, "for-each-ref", "--format=%(refname:short)", "refs/heads").decode().split():
        sha, at = git(a.mirror, "log", "-1", "--format=%H %cI", b).decode().split()
        files, recs, size, gz_sum = 0, {}, 0, 0
        with tarfile.open(fileobj=io.BytesIO(git(a.mirror, "archive", "--format=tar", b))) as t:
            for m in t.getmembers():
                if not m.isfile():
                    continue
                data = t.extractfile(m).read()
                files, size = files + 1, size + len(data)
                if RECORD.search(m.name):   # 줄로 쌓는 파일은 줄 수도 — 같은 날 줄을 고쳐 쓰면 바이트는 줄 수 있어도 줄 수는 안 준다
                    recs[m.name] = {"bytes": len(data), "lines": data.count(b"\n")} if re.search(r"\.jsonl$|seen\.txt$", m.name) else {"bytes": len(data)}
                n = write_file(os.path.join(dst, b), m.name, data, man["big"])
                gz_sum += n
                if n > biggest[0]:
                    biggest = (n, f"{b}/{m.name}")
        total += gz_sum
        man["branches"][b] = {"commit": sha, "at": at, "files": files, "bytes": size, "gz": gz_sum, "records": recs}
        print(f"{b:18} 커밋 {sha[:8]} {at[:16]} · 파일 {files} · 압축 {gz_sum / 1e6:.1f}MB · 기록 파일 {len(recs)}")
    man["total_gz"], man["biggest"] = total, {"path": biggest[1], "gz": biggest[0]}
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
            for path, was in (pb.get("records") or {}).items():
                if not APPEND.search(path):
                    continue
                if path not in now:
                    # 연도 파일을 월별로 옮긴 날(record_store monthly, 2026-11-24) — 같은 폴더의 {연}-MM.jsonl 줄 합이 옛 줄 수 이상이면 정상
                    mo = re.match(r"(.*/)(\d{4})\.jsonl$", path)
                    if mo and isinstance(was, dict) and was.get("lines") is not None:
                        parts = [v for k, v in now.items() if re.match(re.escape(mo.group(1)) + mo.group(2) + r"-\d{2}\.jsonl$", k)]
                        if parts and sum((v or {}).get("lines") or 0 for v in parts if isinstance(v, dict)) >= was["lines"]:
                            continue
                    shrunk.append(f"{b}:{path} 없어짐")
                    continue
                # 줄어듦 = 줄 수가 줄었을 때만(같은 날 · 같은 대상 줄을 고쳐 쓰는 것은 정상 — record_store 규칙, 11-24 NVDA_CEO.jsonl 1434 → 1421 바이트 오탐).
                # 날짜 파일 · 원본 gzip 은 같은 날 다시 쓰거나 다시 묶을 수 있어 없어짐만 본다. 옛 manifest(숫자 하나)는 없어짐만.
                w_lines = was.get("lines") if isinstance(was, dict) else None
                n_lines = (now[path] or {}).get("lines") if isinstance(now[path], dict) else None
                if w_lines is not None and n_lines is not None and n_lines < w_lines:
                    shrunk.append(f"{b}:{path} {w_lines} → {n_lines}줄")
    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    print(f"한 벌 {len(man['branches'])} 브랜치 · 압축 합계 {total / 1e6:.1f}MB · 가장 큰 파일 {biggest[1]} {biggest[0] / 1e6:.1f}MB")
    if shrunk:
        print(f"::error::기록이 줄었다 {len(shrunk)}건 — 사본을 덮어쓰지 않는다: " + " | ".join(shrunk[:10]))
        sys.exit(3)
    if man["big"]:
        print(f"::warning::압축 {SPLIT_MB}MB 넘는 파일 {len(man['big'])}개를 조각으로 나눔 — 기록 구조(연도별 · 월별 나누기)를 손볼 때: " + " | ".join(man["big"]))
        sys.exit(4)


if __name__ == "__main__":
    main()
