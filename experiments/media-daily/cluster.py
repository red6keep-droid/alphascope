"""materials.json → output/media.json — 이슈 묶음 · 한국 연결 · 언급 종목 · 데일리 중복 표시 · 필수 채널 발언. AI 없음.

묶기: 분류(category)가 같고, 소주제(topic) 낱말이 겹치거나 종목이 겹치면 같은 묶음 (전달 자료 6장 2번 — 표현이 달라도 합친다).
순서: 채널 수 → 영상 수 → 주도 이슈(issues[0])로 나온 횟수. 강도 숫자는 만들지 않는다 — 센 것만 (수집기 데이터-설계 "강도는 묶음 안에서 센다").
데일리 중복: 그날 데일리(report-state records/issues, source=daily)와 분류 + (종목 겹침 또는 소주제 낱말 겹침)으로 맞춘다.
겹치면 빼지 않고 표시만 — 글은 짧게 + 데일리 링크 (기획 11절, 2026-10-22 사용자).
"""

import json
import os
import re
import subprocess
import sys
from collections import Counter

import config

sys.path.insert(0, os.path.join(config.BASE_DIR, ".."))
import issue_codes  # noqa: E402
import record_store  # noqa: E402

_WORD = re.compile(r"[가-힣A-Za-z0-9]{2,}")
_STOP = {"기대", "전망", "우려", "논쟁", "강세", "약세", "상승", "하락", "증가", "감소", "영향", "관련", "지속", "확대", "축소", "가능성", "발표", "소식"}


def _words(t):
    return {w.lower() for w in _WORD.findall(str(t or "")) if w not in _STOP}


def _clean_sym(s):
    """'삼성전자(KR)' · 'SPACEX(비상장)' 는 그대로 두되 비교용으로는 괄호 앞만."""
    return re.sub(r"\(.*?\)$", "", str(s or "")).strip().upper()


def _similar(a, b):
    if a["category"] != b["category"]:
        return False
    if set(_clean_sym(x) for x in a["tickers"]) & set(_clean_sym(x) for x in b["tickers"]):
        return True
    wa, wb = _words(a["topic"]), _words(b["topic"])
    return bool(wa and wb and len(wa & wb) >= max(1, min(2, min(len(wa), len(wb)) // 2)))


def _issue_rows(items):
    rows = []
    for it in items:
        for k, iss in enumerate(it.get("issues") or []):
            cat = iss.get("category") or "OTHER"
            rows.append({
                "video": it["id"], "channel": it.get("channelName") or "", "title": it.get("title") or "", "url": it.get("url") or "",
                "published": it.get("publishedAt"), "created": it.get("createdAt"), "speakers": it.get("speakers") or [],
                "k": k, "category": cat if cat in config.CATEGORY_KO else "OTHER", "topic": str(iss.get("topic") or "").strip(),
                "stance": iss.get("stance") if iss.get("stance") in config.STANCE_KO else "neutral",
                "surprise": iss.get("surprise") if iss.get("surprise") in config.SURPRISE_KO else "unknown",
                "scope": iss.get("scope"), "tickers": [str(t) for t in (iss.get("tickers") or []) if t], "country": iss.get("country") or "",
                "horizon": iss.get("horizon"), "note": str(iss.get("note") or "")[:200],
            })
    return rows


def build_clusters(rows):
    clusters = []
    for r in rows:
        if r["category"] == "OTHER":
            continue
        home = None
        for c in clusters:
            if any(_similar(r, x) for x in c["rows"]):
                home = c
                break
        if home is None:
            home = {"category": r["category"], "rows": []}
            clusters.append(home)
        home["rows"].append(r)
    out = []
    for c in clusters:
        rs = c["rows"]
        videos = {r["video"] for r in rs}
        channels = Counter(r["channel"] for r in rs)
        stances = Counter(r["stance"] for r in rs)
        lead_n = sum(1 for r in rs if r["k"] == 0)
        topic = Counter(r["topic"] for r in rs if r["topic"]).most_common(1)
        tickers = Counter(t for r in rs for t in r["tickers"])
        out.append({
            "category": c["category"], "category_ko": config.CATEGORY_KO[c["category"]], "issue": issue_codes.FROM_YTB_CATEGORY.get(c["category"], "OTHER"),
            "topic": topic[0][0] if topic else config.CATEGORY_KO[c["category"]], "topics": sorted({r["topic"] for r in rs if r["topic"]})[:6],
            "n_videos": len(videos), "n_channels": len(channels), "channels": [k for k, _ in channels.most_common()], "lead_n": lead_n,
            "stances": dict(stances), "split": len([s for s in stances if stances[s]]) > 1 and max(stances.values()) < sum(stances.values()),
            "surprise": any(r["surprise"] == "surprise" for r in rs), "scope": Counter(r["scope"] for r in rs if r["scope"]).most_common(1)[0][0] if any(r["scope"] for r in rs) else None,
            "tickers": [t for t, _ in tickers.most_common(6)], "countries": sorted({r["country"] for r in rs if r["country"]}),
            "speakers": [s for s, _ in Counter(sp for r in rs for sp in r["speakers"]).most_common(3)],
            "notes": [r["note"] for r in rs if r["note"]][:3],   # 서술 입력용 (글에 그대로 싣지 않는다)
            "videos": [{"channel": r["channel"], "title": r["title"], "url": r["url"]} for r in {r["video"]: r for r in rs}.values()],
            "daily": None,
        })
    out.sort(key=lambda c: (-c["n_channels"], -c["n_videos"], -c["lead_n"]))
    return [c for c in out if c["n_videos"] >= config.MIN_CLUSTER]


def korea_links(rows):
    """한국 연결 — country=KR · "(KR)" 종목 · 한국어 채널의 이슈. 발언자 이름 붙여 한 줄씩 쓸 재료."""
    out, seen = [], set()
    for r in rows:
        kr = r["country"] == "KR" or any("(KR)" in t for t in r["tickers"])
        if not kr or r["category"] == "OTHER":
            continue
        key = (r["category"], r["topic"])
        if key in seen:
            continue
        seen.add(key)
        out.append({k: r[k] for k in ("channel", "title", "url", "category", "topic", "stance", "surprise", "tickers", "country", "note", "speakers")})
    return out[:6]


def mentioned_tickers(items):
    """방송에서 언급된 종목 — 심볼 · 언급 영상 수만 (글자로만 보여 준다 — 2026-10-22 사용자). '(비상장)' 은 뺀다."""
    c = Counter()
    for it in items:
        for t in set(str(x) for x in (it.get("tickers") or [])):
            if "(비상장)" in t or not t:
                continue
            c[t] += 1
    return [{"sym": s, "n": n} for s, n in c.most_common(20)]


def required_channel_items(rows, korea):
    """2차 '장 초반에 이어 볼 것' — Mad Money · 증시각도기 · 당잠사의 이슈 줄 (채널마다 2개까지). 한국 연결에 이미 있는 줄은 뺀다."""
    out, shown = {}, {(k["channel"], k["topic"]) for k in korea}
    for r in rows:
        if r["channel"] in config.REQUIRED_CHANNELS and r["category"] != "OTHER" and (r["channel"], r["topic"]) not in shown:
            out.setdefault(r["channel"], [])
            if len(out[r["channel"]]) < 2:
                out[r["channel"]].append({k: r[k] for k in ("channel", "title", "url", "category", "topic", "stance", "surprise", "tickers", "note", "speakers")})
    return out


def _daily_issues(edition):
    """그날 데일리가 기록한 이슈 (report-state records/issues, source=daily). 로컬 상태 폴더 → 없으면 origin/report-state."""
    year = edition[:4]
    local = os.path.join(config.BASE_DIR, "..", "daily-report", "output", "state")
    rows = record_store.read(local, "issues", year)
    if not rows:
        try:
            txt = subprocess.run(["git", "show", f"origin/report-state:experiments/daily-report/output/state/records/issues/{year}.jsonl"],
                                 capture_output=True, text=True, check=True, cwd=config.BASE_DIR).stdout
            rows = [json.loads(l) for l in txt.splitlines() if l.strip()]
        except Exception as e:  # noqa: BLE001
            print(f"[cluster] 데일리 기록 없음 ({str(e)[:60]}) — 중복 표시 생략")
            return []
    return [r for r in rows if r.get("source") == "daily" and r.get("date") == edition]


def mark_daily_overlap(clusters, edition):
    daily = _daily_issues(edition)
    if not daily:
        return 0
    n = 0
    for c in clusters:
        for d in daily:
            if d.get("issue") != c["issue"]:
                continue
            dt = set(_clean_sym(x) for x in (d.get("symbols") or []))
            ct = set(_clean_sym(x) for x in c["tickers"])
            words_d = _words(d.get("subtopic")) | _words(d.get("title_ko")) | _words(d.get("title"))
            if (dt & ct) or any(_words(t) & words_d for t in c["topics"]):
                c["daily"] = {"title_ko": d.get("title_ko") or d.get("title"), "subtopic": d.get("subtopic")}
                n += 1
                break
    return n


def ytb_records(rows, edition):
    """우리 기록(records/issues, source=ytb) — 영상 × 이슈 한 줄. 요약 문장 · 자막은 안 담는다."""
    out = []
    for r in rows:
        out.append({"date": edition, "as_of": edition, "source": "ytb", "id": f"{r['video']}/{r['k']}", "issue": issue_codes.FROM_YTB_CATEGORY.get(r["category"], "OTHER"),
                    "category": r["category"], "subtopic": r["topic"], "stance": r["stance"], "surprise": r["surprise"], "scope": r["scope"],
                    "symbols": r["tickers"], "country": r["country"], "horizon": r["horizon"], "channel": r["channel"], "title": r["title"], "url": r["url"],
                    "published": r["published"]})
    return out


def build(materials_path=None, out_path=None, phase=2):
    materials_path = materials_path or os.path.join(config.OUTPUT_DIR, "materials.json")
    with open(materials_path, encoding="utf-8") as f:
        m = json.load(f)
    items, edition = m["items"], m["edition"]
    rows = _issue_rows(items)
    clusters = build_clusters(rows)
    n_overlap = mark_daily_overlap(clusters, edition)
    out = {
        "edition": edition, "phase": phase, "n_items": len(items), "n_channels": len({it.get("channelName") for it in items}),
        "channels": dict(Counter(it.get("channelName") for it in items)),
        "clusters": clusters[:config.TOP_ISSUES], "n_clusters": len(clusters), "n_daily_overlap": n_overlap,
        "korea": korea_links(rows), "tickers": mentioned_tickers(items), "required": required_channel_items(rows, korea_links(rows)),
        "sources": [{"channel": it.get("channelName"), "title": it.get("title"), "url": it.get("url")} for it in items],
    }
    out_path = out_path or os.path.join(config.OUTPUT_DIR, "media.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"[cluster] 영상 {len(items)} · 채널 {out['n_channels']} · 이슈 묶음 {len(clusters)}(데일리 겹침 {n_overlap}) · 한국 연결 {len(out['korea'])} · 종목 {len(out['tickers'])} → {out_path}")
    return out, ytb_records(rows, edition)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build()
