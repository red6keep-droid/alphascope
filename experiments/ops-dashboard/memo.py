"""운영 현황 메모 — Claude 가 읽고 답을 단다. 저장 = Cloudflare KV memo:all (관리자 Worker infra/ops-console 이 같은 키를 읽고 씀).

    python experiments/ops-dashboard/memo.py list            # 열린 메모(열림 · 확인 중 · 보류)
    python experiments/ops-dashboard/memo.py list --all      # 해결한 것까지
    python experiments/ops-dashboard/memo.py note 3 --status 확인 중 --text "원인 찾는 중"
    python experiments/ops-dashboard/memo.py note 3 --status 해결 --text "원인 … · 고친 것 … · 커밋 abc1234"

wrangler 로그인(npx wrangler login)으로 읽고 쓴다 — 키를 파일 · 환경값에 두지 않는다. 메모는 지우지 않는다(상태 · 답만 덧붙임).
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONSOLE = os.path.join(ROOT, "infra", "ops-console")
KEY = "memo:all"
STATES = ("열림", "확인 중", "보류", "해결")
OPEN = ("열림", "확인 중", "보류")
KST = dt.timezone(dt.timedelta(hours=9))


def wrangler(*args):
    cmd = ["npx", "--no-install", "wrangler", "kv", "key", *args, "--binding", "OPS_KV", "--remote"]
    r = subprocess.run(cmd, cwd=CONSOLE, capture_output=True, text=True, encoding="utf-8", shell=(os.name == "nt"))
    if r.returncode != 0:
        sys.exit(f"wrangler 실패 — {(r.stderr or r.stdout).strip()[-300:]}")
    return r.stdout


def load():
    out = wrangler("get", KEY).strip()
    if not out or out.startswith("Value not found"):
        return {"next": 1, "items": []}
    return json.loads(out)


def save(m):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False)
        path = f.name
    try:
        wrangler("put", KEY, "--path", path)
    finally:
        os.remove(path)


def stamp(iso):
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(KST)
    return f"{t.month}.{t.day} {t:%H:%M}"


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list")
    ls.add_argument("--all", action="store_true")
    nt = sub.add_parser("note")
    nt.add_argument("id", type=int)
    nt.add_argument("--status", choices=STATES)
    nt.add_argument("--text", default="")
    a = ap.parse_args()

    m = load()
    if a.cmd == "list":
        items = [x for x in m["items"] if a.all or x.get("status") in OPEN]
        if not items:
            print("열린 메모 없음")
        for x in sorted(items, key=lambda x: x["id"]):
            print(f"#{x['id']} [{x['status']}] {x['kind']} · {stamp(x['at'])} {'Claude' if x.get('by') == 'Claude' else '관리자'}")
            print("   " + x["text"].replace("\n", "\n   "))
            for l in x.get("log") or []:
                print(f"   → {stamp(l['at'])} {'Claude' if l.get('by') == 'Claude' else '관리자'}"
                      + (f" · {l['status']}" if l.get("status") else "") + (f" — {l['note']}" if l.get("note") else ""))
        return
    x = next((i for i in m["items"] if i["id"] == a.id), None)
    if not x:
        sys.exit(f"#{a.id} 메모 없음")
    if not a.status and not a.text.strip():
        sys.exit("--status 나 --text 중 하나는 넣어야 합니다")
    if a.status:
        x["status"] = a.status
    x.setdefault("log", []).append({"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                                    "by": "Claude", "status": a.status or "", "note": a.text.strip()})
    save(m)
    print(f"#{a.id} → {x['status']} 저장")


if __name__ == "__main__":
    main()
