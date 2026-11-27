"""운영 현황 메모 — Claude 가 읽고 답을 단다. 저장 = Cloudflare KV memo:item:{id} 메모마다 키 하나 (관리자 Worker infra/ops-console 이 같은 키를 읽고 씀).

    python experiments/ops-dashboard/memo.py list            # 열린 메모(열림 · 확인 중 · 보류)
    python experiments/ops-dashboard/memo.py list --all      # 해결한 것까지
    python experiments/ops-dashboard/memo.py note 3 --status 확인 중 --text "원인 찾는 중"
    python experiments/ops-dashboard/memo.py note 3 --status 해결 --text "원인 … · 고친 것 … · 커밋 abc1234"
    python experiments/ops-dashboard/memo.py add --kind 리스크 --text "점검하다 찾은 것"

번호(#n) = 쓴 시각 순서의 자리(화면과 같음). 메모마다 키가 따로라 연달아 써도 서로 덮어쓰지 않는다.
같은 메모를 1분 안에 두 번 고치면 KV 가 퍼지기 전 값을 읽을 수 있다 — 한 번에 하나씩, 고친 뒤 list 로 확인.
wrangler 로그인(npx wrangler login)으로 읽고 쓴다 — 키를 파일 · 환경값에 두지 않는다. 메모는 지우지 않는다(상태 · 답만 덧붙임).
"""
import argparse
import datetime as dt
import json
import os
import random
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONSOLE = os.path.join(ROOT, "infra", "ops-console")
PREFIX = "memo:item:"
STATES = ("열림", "확인 중", "보류", "해결")
OPEN = ("열림", "확인 중", "보류")
KST = dt.timezone(dt.timedelta(hours=9))


def wrangler(*args, missing_ok=False):
    cmd = ["npx", "--no-install", "wrangler", "kv", "key", *args, "--binding", "OPS_KV", "--remote"]
    r = subprocess.run(cmd, cwd=CONSOLE, capture_output=True, text=True, encoding="utf-8", shell=(os.name == "nt"))
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip()
        if missing_ok and ("404" in msg or "not found" in msg.lower()):
            return ""
        sys.exit(f"wrangler 실패 — {msg[-300:]}")
    return r.stdout


def load():
    """메모 전부 — 시간순, no = 화면 번호."""
    names = [k["name"] for k in json.loads(wrangler("list", "--prefix", PREFIX) or "[]")]
    items = []
    for n in names:
        out = wrangler("get", n, missing_ok=True).strip()
        if out:
            items.append(json.loads(out))
    items.sort(key=lambda x: x["id"])
    for i, x in enumerate(items, 1):
        x["no"] = i
    return items


def put(x):
    x = {k: v for k, v in x.items() if k != "no"}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(x, f, ensure_ascii=False)
        path = f.name
    try:
        wrangler("put", PREFIX + x["id"], "--path", path)
    finally:
        os.remove(path)


def stamp(iso):
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(KST)
    return f"{t.month}.{t.day} {t:%H:%M}"


def who(by):
    return "Claude" if by == "Claude" else "관리자"


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list")
    ls.add_argument("--all", action="store_true")
    ad = sub.add_parser("add")   # Claude 가 점검하다 찾은 문제 · 리스크를 메모로 남김
    ad.add_argument("--kind", choices=("문제", "리스크"), default="리스크")
    ad.add_argument("--text", required=True)
    nt = sub.add_parser("note")
    nt.add_argument("no", type=int, help="화면 번호 #n")
    nt.add_argument("--status", choices=STATES)
    nt.add_argument("--text", default="")
    a = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    stamp_now = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    if a.cmd == "add":
        mid = now.strftime("%Y%m%d%H%M%S") + f"{now.microsecond // 1000:03d}" + f"{random.getrandbits(16):04x}"
        put({"id": mid, "kind": a.kind, "text": a.text.strip(), "at": stamp_now, "by": "Claude", "status": "열림", "log": []})
        print(f"남김 (id {mid}) — 화면 번호는 list 로 확인")
        return

    items = load()
    if a.cmd == "list":
        shown = [x for x in items if a.all or x.get("status") in OPEN]
        if not shown:
            print("열린 메모 없음")
        for x in shown:
            print(f"#{x['no']} [{x['status']}] {x['kind']} · {stamp(x['at'])} {who(x.get('by'))}")
            print("   " + x["text"].replace("\r\n", "\n").replace("\n", "\n   "))
            for l in x.get("log") or []:
                print(f"   → {stamp(l['at'])} {who(l.get('by'))}" + (f" · {l['status']}" if l.get("status") else "")
                      + (f" — {l['note']}" if l.get("note") else ""))
        return
    x = next((i for i in items if i["no"] == a.no), None)
    if not x:
        sys.exit(f"#{a.no} 메모 없음")
    if not a.status and not a.text.strip():
        sys.exit("--status 나 --text 중 하나는 넣어야 합니다")
    if a.status:
        x["status"] = a.status
    x.setdefault("log", []).append({"at": stamp_now, "by": "Claude", "status": a.status or "", "note": a.text.strip()})
    put(x)
    print(f"#{a.no} → {x['status']} 저장")


if __name__ == "__main__":
    main()
