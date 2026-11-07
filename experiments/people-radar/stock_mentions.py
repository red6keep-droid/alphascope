"""인물 발언 → 종목 페이지 · 미국 증시 리포트용 JSON (2026-11-07 사용자: 인물 발언을 종목 · 증시 리포트에 붙이기, 목업).

인물 레이더 실행이 끝날 때 radar.json(최근 24시간 신호) + narrative.json(한국어 헤드라인)을 받아 지난 기록과 합쳐
output/state/people_mentions.json 을 쓴다. 이 파일은 radar-state 브랜치에 남고, 종목(03:36) · 데일리(07:30) 실행이 읽는다.

    by_stock[티커] = 최근 7일 그 종목을 지목한 발언 (관련도 · 강도 · 최근 순)
    market        = 최근 24시간 시장 관련도 3 발언 (강도 순, 인물마다 하나)
    items[id]     = 발언 한 건 (헤드라인 · 요약 · 인물 · 시각 · 매체 · 보도 수 · 주제 · 방향 · 강도 · 대상 종목)

지목 규칙: 대상 종목이 2개 이하이거나, 헤드라인 · 요약에 그 종목 한국어 이름이 있을 때만 — 한 기사가 종목 다섯을 늘어놓은 경우
(크레이머 '자일럼이 듀폰보다 못하다' 에 엔비디아가 끼는 것)는 그 종목 발언이 아니다.

목업: python experiments/people-radar/stock_mentions.py --from-git   # radar-state 지난 7일 커밋에서 모은다
"""

import datetime
import json
import os
import subprocess
import sys

import config

sys.path.insert(0, os.path.join(config.BASE_DIR, "..", "stock-radar"))
try:
    import universe as _uni
except Exception:  # noqa: BLE001
    _uni = None

DAYS = 7
OUT = os.path.join(config.BASE_DIR, "output", "state", "people_mentions.json")
GIT_RADAR = "experiments/people-radar/output/state/radar.json"
GIT_NARR = "experiments/people-radar/output/state/narrative.json"


def _ko(sym):
    try:
        return _uni.name(sym) if _uni else ""
    except KeyError:
        return ""


def _item(p, s, card):
    return {"id": s["lead"]["id"], "speaker": p["speaker"], "name_ko": p["name_ko"], "title_ko": p["title_ko"],
            "headline": card["headline"], "detail": card.get("detail") or "",
            "url": s["lead"]["url"] if (s["lead"].get("url") or "").startswith("http") else None,
            "at": s["first_at"], "publisher": (s["lead"].get("publisher") or "").strip(), "primary": s["source_kind"] == "primary",
            "n_reports": s.get("n_reports") or 0, "topic": s["topic"], "issue": s.get("issue") or "OTHER", "direction": s["direction"],
            "intensity": s["intensity"], "relevance": s.get("relevance") or 0, "companies": s.get("companies") or []}


def _points_at(it, sym):
    if len(it["companies"]) <= 2:
        return True
    name = _ko(sym)
    return bool(name) and (name in it["headline"] or name in it["detail"])


def build(snapshots, now=None, prior=None):
    """snapshots = [(radar, cards)] 오래된 것부터. 같은 발언(id)은 마지막 것. prior = 지난 실행의 items(7일 누적)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    since7 = (now - datetime.timedelta(days=DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    since1 = (now - datetime.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    items = {k: v for k, v in (prior or {}).items() if v.get("at", "") >= since7}
    for radar, cards in snapshots:
        for p in radar.get("people", []):
            for s in p["signals"]:
                c = (cards or {}).get(s["lead"]["id"])
                if c and s["first_at"] >= since7:   # 한국어 헤드라인이 없는 발언은 싣지 않는다 (영문 원문 노출 금지, 운영지침 4-3)
                    items[s["lead"]["id"]] = _item(p, s, c)
    by_stock = {}
    for it in items.values():
        for sym in it["companies"]:
            if _points_at(it, sym):
                by_stock.setdefault(sym, []).append(it["id"])
    for sym, ids in by_stock.items():   # 관련도 · 강도 높은 순, 같으면 최근 순
        by_stock[sym] = sorted(ids, key=lambda i: (-items[i]["relevance"], -items[i]["intensity"], -_epoch(items[i]["at"])))[:8]
    market, seen = [], set()
    for it in sorted((x for x in items.values() if x["at"] >= since1 and x["relevance"] >= 3), key=lambda x: (-x["intensity"], -_epoch(x["at"]))):
        if it["speaker"] in seen:
            continue
        seen.add(it["speaker"])
        market.append(it["id"])
    used = set(market) | {i for ids in by_stock.values() for i in ids}
    return {"generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "days": DAYS, "market": market[:6], "by_stock": by_stock,
            "items": {i: items[i] for i in used}}


def _epoch(iso):
    return datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp()


def _git_json(rev, path):
    r = subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def from_git(ref="state/radar-state"):
    revs = subprocess.run(["git", "log", "--format=%H", f"--since={DAYS + 1} days ago", ref], capture_output=True, text=True).stdout.split()
    snaps = []
    for rev in reversed(revs):
        radar, narr = _git_json(rev, GIT_RADAR), _git_json(rev, GIT_NARR)
        if radar and narr:
            snaps.append((radar, narr.get("cards") or {}))
    last = snaps[-1][0]["generated_at"] if snaps else None
    now = datetime.datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc) if last else None
    return build(snaps, now)


def write(data, path=OUT):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"[mentions] 종목 {len(data['by_stock'])}개 · 시장 {len(data['market'])}건 · 발언 {len(data['items'])}건 → {path}")


def update(radar_path, narrative_path, path=OUT):
    """정기 실행 끝 (people-radar main.py) — 지난 파일(상태 브랜치 radar-state 에서 불러옴)의 7일 발언 + 오늘 신호 · 한국어 헤드라인. 실패해도 글은 나간다."""
    try:
        with open(radar_path, encoding="utf-8") as f:
            radar = json.load(f)
        cards = {}
        if os.path.exists(narrative_path):
            with open(narrative_path, encoding="utf-8") as f:
                cards = (json.load(f) or {}).get("cards") or {}
        prior = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                prior = (json.load(f) or {}).get("items") or {}
        write(build([(radar, cards)], prior=prior), path)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[mentions] 종목 · 증시 리포트용 발언 파일 실패 (글은 계속): {e!r}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--from-git" in sys.argv:
        write(from_git())
