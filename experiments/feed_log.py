"""주기 자료 받기 현황 — 분기 · 주 · 월마다 받는 자료가 제때 들어왔는지 운영 대시보드가 보게 남긴다 (2026-11-13 사용자 "잘 받고 있는지 모니터링").

수집 코드가 자료 하나를 확인할 때마다 feed() 를 한 번 부른다 → Cloudflare KV `feed:<이름>` 한 건을 덮어쓴다(가장 최근 상태만).
운영 대시보드(build_ops.py `수집` 탭 `주기 자료는 제때 받았나?`)가 feed: 로 시작하는 키를 모두 읽어 정상 · 늦음 · 실패로 칠한다.

- OPS_CF_ACCOUNT_ID · OPS_CF_KV_NAMESPACE_ID · OPS_CF_API_TOKEN 이 있을 때만 KV 에 보낸다(ops_log 와 같은 값).
- FEED_LOCAL 환경변수에 파일 경로가 있으면 그 파일에도 쓴다(로컬 목업 · 확인용).
- 실패해도 print 만 — 모니터링 기록 때문에 수집이 죽으면 안 된다.

판정에 쓰는 값:
  every_days = 확인 주기(예: 7). 마지막 확인이 이보다 2배 넘게 지났으면 `늦음`(실행이 안 돌고 있다).
  expect_new = 다음 새 자료가 나와야 할 날(ISO). 이 날이 지났는데 새 자료가 없으면 `늦음`(기관이 늦게 올렸을 수도 있다).
  ok=False = 받기 · 읽기 실패 → `실패`.
"""

import datetime
import json
import os
import sys

KST = datetime.timezone(datetime.timedelta(hours=9))
TTL_SECONDS = 400 * 86400


def now_iso():
    return datetime.datetime.now(KST).isoformat(timespec="seconds")


def feed(name, ok, label="", data_date="", got_new=False, error="", every_days=7, expect_new="", detail=""):
    """name = 표에 보일 자료 이름(예: `국민연금 대량보유 내역`). label = 지금 가진 자료(예: `2026년 3분기`), data_date = 그 기준일."""
    rec = {"name": name, "checked": now_iso(), "ok": bool(ok), "label": label, "data_date": data_date, "every_days": every_days,
           "expect_new": expect_new, "error": (error or "")[:200], "detail": (detail or "")[:200]}
    prev = _local_get(name)
    rec["last_new"] = now_iso() if got_new else (prev or {}).get("last_new", "")
    if not ok and prev:   # 실패해도 지금 가진 자료 이름은 지난 성공 값으로
        rec["label"] = rec["label"] or prev.get("label", "")
        rec["data_date"] = rec["data_date"] or prev.get("data_date", "")
    _local_put(name, rec)
    _kv_put(name, rec)
    if not ok:   # 실패는 Slack 운영 알림도 (notify 는 실행 끝에 묶어 한 번 보낸다)
        try:
            import notify
            notify.event("수집 실패", f"{name} — {rec['error'] or '받기 · 읽기 실패'} · 지난 자료({rec['label'] or '없음'})로 대신")
        except Exception:  # noqa: BLE001
            pass
    return rec


def _local_path():
    return os.environ.get("FEED_LOCAL", "").strip()


def _local_get(name):
    p = _local_path()
    if not p:
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f).get(name)
    except (OSError, ValueError):
        return None


def _local_put(name, rec):
    p = _local_path()
    if not p:
        return
    try:
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {}
        d[name] = rec
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError as e:
        print(f"[feed_log] 로컬 기록 실패: {e}", file=sys.__stdout__)


def _kv_put(name, rec):
    acc, ns, tok = (os.environ.get(k, "").strip() for k in ("OPS_CF_ACCOUNT_ID", "OPS_CF_KV_NAMESPACE_ID", "OPS_CF_API_TOKEN"))
    if not (acc and ns and tok):
        return
    try:
        import urllib.parse
        import requests
        key = urllib.parse.quote(f"feed:{name}", safe="")
        r = requests.put(f"https://api.cloudflare.com/client/v4/accounts/{acc}/storage/kv/namespaces/{ns}/values/{key}",
                         params={"expiration_ttl": TTL_SECONDS}, data=json.dumps(rec, ensure_ascii=False).encode("utf-8"),
                         headers={"Authorization": f"Bearer {tok}", "Content-Type": "text/plain; charset=utf-8"}, timeout=20)
        if r.status_code != 200:
            print(f"[feed_log] 기록 저장 실패 HTTP {r.status_code}", file=sys.__stdout__)
    except Exception as e:  # noqa: BLE001
        print(f"[feed_log] 기록 저장 실패: {type(e).__name__}", file=sys.__stdout__)


def status(rec, now=None):
    """기록 하나 → (`정상` · `늦음` · `실패`, 이유). 대시보드가 쓴다."""
    now = now or datetime.datetime.now(KST)
    if not rec.get("ok"):
        return "실패", rec.get("error") or "받기 · 읽기 실패"
    try:
        checked = datetime.datetime.fromisoformat(rec["checked"])
    except (KeyError, ValueError):
        return "실패", "확인 시각 없음"
    every = rec.get("every_days") or 7
    if (now - checked).days > every * 2:
        return "늦음", f"마지막 확인이 {(now - checked).days}일 전 — 정기 실행이 안 돌고 있을 수 있음"
    exp = rec.get("expect_new")
    if exp and now.date().isoformat() > exp:
        return "늦음", f"{exp} 이후 나와야 할 새 자료가 아직 없음 — 기관이 늦게 올렸을 수 있음"
    return "정상", ""
