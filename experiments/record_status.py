"""기록 현황 — 기록 대장(비공개 doc/기획/기록-대장.md)의 줄마다 '무엇이 얼마나 · 언제부터 언제까지 쌓였나'를 센다 (2026-11-24 사용자 "운영관리 현황에 기록 탭 기록현황").

    python experiments/record_status.py --mirror <alphascope-state 를 --mirror 로 받은 폴더> [--out FILE] [--kv]

- 언제: 밤 기록 사본 실행(state-backup.yml)이 이미 받은 상태 저장소로 센다 — 매시간 도는 운영 대시보드가 91MB 를 받지 않게.
- 결과: {"made", "items": [{name, asset, where, files, bytes, first, last, n}]} → --kv 면 운영 KV `dash:records` (운영 대시보드 기록 탭이 읽는다).
- 알림은 보내지 않는다(사용자 11-24 "빠진 날 알리지마") — 화면에 날짜만 보인다.
- 줄 = 기록 대장 1절. 대장에 줄을 더하면 여기 REGISTRY 에도 한 줄(경로 정규식). AI 0 · 수집 0.
"""
import argparse
import datetime
import gzip
import json
import os
import re
import subprocess
import sys

# (이름, 자산, 브랜치, 경로 정규식, 날짜 읽는 법) — 날짜 = name: 파일 이름의 날짜 · line: 줄의 date/day 칸 · keys: json 열쇠가 날짜 · gzname: {연}/{월-일}.jsonl.gz · none
REGISTRY = [
    ("미국 시장 그날 상태", "시장 상태", "report-state", r"/history/(\d{4}-\d{2}-\d{2})\.json$", "name"),
    ("미국 시장 판정 · 스냅샷 · 고른 뉴스", "시장 상태", "report-state", r"/records/(verdicts|snapshots|issues)/\d{4}(-\d{2})?\.jsonl$", "line"),
    ("한국 시장 그날 상태", "시장 상태", "kr-state", r"/records/market/\d{4}/(\d{4}-\d{2}-\d{2})\.json$", "name"),
    ("테마 상태 (구성 종목 포함)", "테마 상태", "nvda-state", r"/records/themes/\d{4}(-\d{2})?\.jsonl$", "line"),
    ("돈의 흐름 (업종 · 세부 업종 · ETF 순자산)", "테마 상태", "nvda-state", r"/radar/records/flows/\d{4}(-\d{2})?\.jsonl$", "line"),
    ("Hot Issue 단계 이력", "이슈 단계", "nvda-state", r"/output/state/records/issues/[A-Z_]+\.jsonl$", "line"),
    ("증시 전망 — 날마다 확인", "전망 · 결과", "nvda-state", r"/records/forecasts/EH-[\d-]+\.jsonl$", "line"),
    ("증시 전망 — 가설", "전망", "nvda-state", r"/records/hypotheses/", "none"),
    ("미국 종목 카드 판정 · 의견", "종목", "nvda-state", r"/radar/records/verdicts/\d{4}(-\d{2})?\.jsonl$", "line"),
    ("미국 종목 뉴스 분류 (정식 종목)", "이슈", "nvda-state", r"/radar/records/issues/\d{4}(-\d{2})?\.jsonl$", "line"),
    ("엔비디아 리포트 판정 · 이슈", "종목 · 이슈", "nvda-state", r"/output/state/records/(verdicts|issues)/\d{4}(-\d{2})?\.jsonl$", "line"),
    ("엔비디아 옵션 스냅샷", "종목", "nvda-state", r"/option_snapshots\.jsonl$", "line"),
    ("한국 종목 · 시장 판정", "종목 · 시장 상태", "kr-state", r"/data/records/verdicts/\d{4}(-\d{2})?\.jsonl$", "line"),
    ("한국 이익 예상", "종목", "kr-state", r"/est_history\.json$", "keys"),
    ("방송 이슈 분류", "이슈", "media-state", r"/records/(issues|verdicts)/\d{4}(-\d{2})?\.jsonl$", "line"),
    ("인물 발언 분류", "이슈", "radar-state", r"/records/(issues|verdicts)/\d{4}(-\d{2})?\.jsonl$", "line"),
    ("한국 기사 사건별 사실 (날짜 파일)", "이슈", "kr-facts", r"^kr/facts/(\d{4}-\d{2}-\d{2})\.json$", "name"),
    ("한국 기사 원본 (실행마다)", "이슈", "kr-facts", r"^kr/raw/", "none"),
    ("미국 뉴스 분류 — 간단 종목 452", "이슈", "news-records", r"^records/quick/(\d{4})/(\d{2}-\d{2})\.jsonl\.gz$", "gzname"),
    ("미국 뉴스 분류 — 홈 CNBC", "이슈", "news-records", r"^records/home/(\d{4})/(\d{2}-\d{2})\.jsonl\.gz$", "gzname"),
]


def git(mirror, *a):
    return subprocess.run(["git", "-c", "core.autocrlf=false", "-C", mirror, *a], capture_output=True, check=True).stdout


def _line_dates(raw):
    first = last = None
    n = 0
    for line in raw.splitlines():
        if not line.strip():
            continue
        n += 1
        try:
            d = json.loads(line)
        except ValueError:
            continue
        v = str(d.get("date") or d.get("day") or "")[:10]
        if re.match(r"\d{4}-\d{2}-\d{2}$", v):
            first = v if first is None or v < first else first
            last = v if last is None or v > last else last
    return first, last, n


def compute(mirror):
    heads = {}
    for b in git(mirror, "for-each-ref", "--format=%(refname:short)", "refs/heads").decode().split():
        heads[b] = git(mirror, "log", "-1", "--format=%cI", b).decode().strip()
    trees = {}
    items = []
    for name, asset, br, pat, how in REGISTRY:
        it = {"name": name, "asset": asset, "where": br, "files": 0, "bytes": 0, "first": None, "last": None, "n": 0, "head": heads.get(br)}
        if br not in heads:
            it["missing"] = True
            items.append(it)
            continue
        if br not in trees:
            trees[br] = [ln.split("\t", 1) for ln in git(mirror, "-c", "core.quotepath=false", "ls-tree", "-r", "-l", br).decode("utf-8").splitlines()]
        rx = re.compile(pat)
        dates = []
        for meta, path in trees[br]:
            m = rx.search(path)
            if not m:
                continue
            it["files"] += 1
            it["bytes"] += int(meta.split()[3])
            if how == "name":
                dates.append(m.group(1))
                it["n"] += 1
            elif how == "gzname":
                dates.append(f"{m.group(1)}-{m.group(2)}")
                raw = gzip.decompress(git(mirror, "cat-file", "blob", meta.split()[2]))
                it["n"] += sum(1 for x in raw.splitlines() if x.strip())
            elif how == "line":
                f, l, n = _line_dates(git(mirror, "cat-file", "blob", meta.split()[2]))
                dates += [x for x in (f, l) if x]
                it["n"] += n
            elif how == "keys":
                d = json.loads(git(mirror, "cat-file", "blob", meta.split()[2]))
                ks = [k for k in d if re.match(r"\d{4}-\d{2}-\d{2}$", str(k))]
                dates += ks
                it["n"] += len(ks)
            else:
                it["n"] += 1
        if dates:
            it["first"], it["last"] = min(dates), max(dates)
        items.append(it)
    return {"made": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "items": items}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--mirror", required=True)
    ap.add_argument("--out")
    ap.add_argument("--backup-manifest", help="같은 실행이 만든 사본 manifest — 사본 크기 · 시각을 같이 싣는다")
    ap.add_argument("--kv", action="store_true", help="운영 KV dash:records 로 올린다(OPS_CF_* 가 있을 때)")
    a = ap.parse_args()
    st = compute(a.mirror)
    if a.backup_manifest and os.path.exists(a.backup_manifest):
        m = json.load(open(a.backup_manifest, encoding="utf-8"))
        st["backup"] = {"made": m.get("made"), "gz": m.get("total_gz"), "biggest": m.get("biggest"), "where": "red9keep/News-doc state-backup/daily"}
    for it in st["items"]:
        print(f"{it['name'][:24]:24} {it['first'] or '-':10} ~ {it['last'] or '-':10} · {it['n']:>6}줄 · 파일 {it['files']:>3} · {it['bytes'] / 1e6:5.1f}MB")
    text = json.dumps(st, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    if a.kv:   # 표준 라이브러리만 — 사본 워크플로는 패키지를 설치하지 않는다 (운영 대시보드 build_ops.kv_put 과 같은 주소)
        import urllib.request
        acc, ns, tok = (os.environ.get(k, "").strip() for k in ("OPS_CF_ACCOUNT_ID", "OPS_CF_KV_NAMESPACE_ID", "OPS_CF_API_TOKEN"))
        if not (acc and ns and tok):
            print("::warning::OPS_CF 설정 없음 — dash:records 안 올림")
            return
        req = urllib.request.Request(f"https://api.cloudflare.com/client/v4/accounts/{acc}/storage/kv/namespaces/{ns}/values/dash:records",
                                     data=text.encode("utf-8"), method="PUT",
                                     headers={"Authorization": f"Bearer {tok}", "Content-Type": "text/plain; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"KV dash:records 올림 ({r.status})")


if __name__ == "__main__":
    main()
