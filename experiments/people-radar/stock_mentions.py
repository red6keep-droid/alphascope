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
import paths

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


def _pop_lines(s, card):
    """팝업 줄 (2026-11-07 사용자 P366) — 새 AI 없이 레이더가 만든 한국어 재료만. 영어 원문 인용은 싣지 않는다(운영지침 4-3)."""
    out = []
    if card.get("detail"):
        out.append(card["detail"])
    pth = s.get("path")
    if pth and pth.get("assets"):
        why = card.get("path") or paths.CHANNEL_KO.get(pth.get("channel"), "")
        out.append(" · ".join((paths.asset_label(a) if a in paths.ASSET_KO else f"{_ko(a)}({a})" if _ko(a) else a) for a in pth["assets"]) + (f" : {why}" if why else ""))   # 종목은 `엔비디아(NVDA)` (인물 발언 글과 같게)
    n = s.get("novelty") or {}
    if n.get("first30"):
        out.append("30일 만에 처음 나온 주제")
    elif n.get("streak", 0) >= 2:
        out.append(f"{n['streak']}일째 같은 주제")
    nx = s.get("next")
    if nx and nx.get("day"):
        _, m, d = nx["day"].split("-")
        out.append(f"다음 날짜 : {int(m)}월 {int(d)}일 {nx.get('kind', '')}".strip())
    return out   # `보도 : 매체` 줄은 뺐다 — 매체는 원문 링크 글자에 (2026-11-07 사용자 P370)


def _avatar(p):
    """줄 왼쪽 얼굴 동그라미 (2026-11-07 사용자 P368) — 인물 발언 글과 같은 것(사진, 없으면 성 첫 글자 · 인물군 색)."""
    try:
        import render_html
        return render_html._avatar(p, 32)
    except Exception:  # noqa: BLE001
        return ""


def _item(p, s, card):
    return {"pop": _pop_lines(s, card), "avatar": _avatar(p),"id": s["lead"]["id"], "speaker": p["speaker"], "name_ko": p["name_ko"], "title_ko": p["title_ko"],
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


# 세부 주제(ai_subtopic) 같은 뜻 합치기 — 분류 모델이 같은 이야기를 다른 말로 붙인다 (2026-11-08 사용자 P406). 소문자 키 → 대표 영어 키(subtopic_ko.json 의 키)
SUBTOPIC_SAME = {"chips": "Semiconductors", "semiconductor": "Semiconductors", "semiconductors": "Semiconductors", "ai chips": "Semiconductors",
                 "roadster": "Tesla Roadster", "artificial intelligence": "AI", "ai": "AI", "tariffs": "Tariff", "tariff": "Tariff"}
SUBTOPIC_KO_PATH = os.path.join(config.BASE_DIR, "ref", "subtopic_ko.json")   # narrate.translate_subtopics 가 채운다 (깃에 남는다)
SUBTOPIC_BROAD = {"ai", "artificial intelligence", "economy", "markets", "stock market", "stocks", "technology", "investing", "earnings"}   # 좁은 이슈가 아니다 — 큰 분야와 같은 문제(P406)라 셈에서 뺀다
ISSUE_MIN_WHO = 2   # 많이 말한 이슈 = 두 명 이상이 말한 이슈만 — 없으면 카드 생략 (빈 답 금지)


def _subtopic_ko():
    try:
        with open(SUBTOPIC_KO_PATH, encoding="utf-8") as f:
            return {k.lower(): v for k, v in json.load(f).items()}
    except (OSError, ValueError):
        return {}


def _issue_key(sub, ko):
    """세부 주제 → (대표 키, 한국어). 비었거나 한국어 표기가 없으면 None — 영어 원문은 독자에게 보이지 않는다 (운영지침 4-3)."""
    k = (sub or "").strip()
    if not k:
        return None
    k = SUBTOPIC_SAME.get(k.lower(), k)
    if k.lower() in SUBTOPIC_BROAD:
        return None
    name = ko.get(k.lower())
    return (k, name) if name else None


def summary(radar):
    """인물 발언 탭 맨 위 요약 (2026-11-07 사용자 P376) — 오늘(레이더 24시간) 신호만, 파이썬 셈 · AI 없음.
    2026-11-08 사용자 P406: 큰 분야(`기업 사건` · `투자자 매매 · 의견`)는 범위가 넓어 뜻이 없다 → 좁은 이슈(세부 주제, 예 관세 · AI 거품 · 반도체).
    issues = 많이 말한 이슈 3 (두 명 이상) [{key, name, n, n_who, who, dirs}] · split = 의견이 갈린 이슈 · 종목 — 같은 이슈(또는 같은 종목)를 두고
    다른 사람이 긍정 · 부정으로 맞선 것만 [{name, pos (이름, 건수), neg (이름, 건수), n}] (옛: 분야로만 묶어 다른 종목끼리도 '갈림') · stocks = 많이 언급된 종목 3."""
    from collections import Counter, defaultdict
    ko = _subtopic_ko()
    sig = [(p, s) for p in radar.get("people", []) for s in p["signals"]]
    by, names = defaultdict(list), {}
    for p, s in sig:
        ik = _issue_key(s.get("subtopic"), ko)
        if ik:
            by[ik[0]].append((p["name_ko"], s["direction"]))
            names[ik[0]] = ik[1]
    issues = []
    for k, v in sorted(by.items(), key=lambda kv: (-len({n for n, _ in kv[1]}), -len(kv[1]))):   # 말한 인물 수 먼저, 같으면 건수
        who = list(dict.fromkeys(n for n, _ in v))
        if len(who) >= ISSUE_MIN_WHO:
            issues.append({"key": k, "name": names[k], "n": len(v), "n_who": len(who), "who": who[:4], "dirs": dict(Counter(d for _, d in v))})
    comp, cdir = defaultdict(list), defaultdict(Counter)
    for p, s in sig:
        for c in s.get("companies") or []:
            comp[c].append((p["name_ko"], s["direction"]))
            cdir[c][s["direction"]] += 1   # 그 종목 발언의 방향 — 질문 카드 색 (P380)
    split = []
    for name, v in [(names[k], v) for k, v in by.items()] + [(_ko(c) or c, v) for c, v in comp.items()]:
        pos = Counter(n for n, d in v if d == "positive")
        neg = Counter(n for n, d in v if d == "negative")
        if not pos or not neg:
            continue
        pa = pos.most_common(1)[0]
        na = next((x for x in neg.most_common() if x[0] != pa[0]), None)   # 양쪽은 다른 사람 — 한 사람이 오락가락한 건 `갈림` 이 아니다
        if na:
            split.append({"name": name, "pos": pa, "neg": na, "n": sum(pos.values()) + sum(neg.values())})
    split.sort(key=lambda x: -x["n"])
    stocks = [{"sym": c, "name": _ko(c) or c, "n": len(v), "who": list(dict.fromkeys(n for n, _ in v))[:3], "dirs": dict(cdir[c])}
              for c, v in sorted(comp.items(), key=lambda kv: -len(kv[1]))[:3] if len(v) >= 2]
    return {"issues": issues[:3], "split": split[:2], "stocks": stocks, "n_people": len(radar.get("people", [])), "n": len(sig)}


def person_summary(today_sigs, p7):
    """인물 페이지 요약 카드 재료 (2026-11-11 사용자: "인물마다 많이 한 말 · 이슈 카드, 오늘 · 최근 7일") — 파이썬 셈, AI 없음.
    today_sigs = 레이더 그 인물 signals(24시간), p7 = radar["person7"][speaker](aggregate.person_counts, 7일).
    → {"today": {n, dirs, issues}, "d7": {n, dirs, issues, stocks}} · issues · stocks = [{name, n, dirs}] 건수 순. 한국어 이름이 없는 세부 주제는 뺀다(영문 노출 금지)."""
    from collections import Counter
    ko = _subtopic_ko()

    def merge_issues(pairs):
        by, names = {}, {}
        for sub, dirs in pairs:
            ik = _issue_key(sub, ko)
            if not ik:
                continue
            e = by.setdefault(ik[0], Counter())
            e.update({k: v for k, v in dirs.items() if v})
            names[ik[0]] = ik[1]
        return [{"name": names[k], "n": sum(c.values()), "dirs": dict(c)} for k, c in sorted(by.items(), key=lambda kv: -sum(kv[1].values()))]

    today = {"n": len(today_sigs), "dirs": dict(Counter(x["direction"] for x in today_sigs)),
             "issues": merge_issues([(x.get("subtopic"), {x["direction"]: 1}) for x in today_sigs])}
    p7 = p7 or {}
    d7 = {"n": p7.get("n", 0), "dirs": p7.get("dirs") or {},
          "issues": merge_issues(list((p7.get("subs") or {}).items())),
          "stocks": [{"name": _ko(c) or c, "n": sum(v.values()), "dirs": v} for c, v in sorted((p7.get("companies") or {}).items(), key=lambda kv: -sum(kv[1].values()))]}
    return {"today": today, "d7": d7}


def build(snapshots, now=None, prior=None, post_url=None):
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
    return {"generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "days": DAYS, "post_url": post_url,
            "summary": summary(snapshots[-1][0]) if snapshots else {}, "market": market[:6], "by_stock": by_stock,
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
    pu = os.path.join(config.BASE_DIR, "output", "post_url.txt")   # 목업 = 로컬에 남은 마지막 게시 주소
    return build(snaps, now, post_url=open(pu, encoding="utf-8").read().strip() if os.path.exists(pu) else None)


def write(data, path=OUT):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"[mentions] 종목 {len(data['by_stock'])}개 · 시장 {len(data['market'])}건 · 발언 {len(data['items'])}건 → {path}")


def update(radar_path, narrative_path, path=OUT, post_url_path=None):
    """정기 실행 끝 (people-radar main.py) — 지난 파일(상태 브랜치 radar-state 에서 불러옴)의 7일 발언 + 오늘 신호 · 한국어 헤드라인. 실패해도 글은 나간다."""
    try:
        with open(radar_path, encoding="utf-8") as f:
            radar = json.load(f)
        cards = {}
        if os.path.exists(narrative_path):
            with open(narrative_path, encoding="utf-8") as f:
                cards = (json.load(f) or {}).get("cards") or {}
        prior, old = {}, {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                old = json.load(f) or {}
            prior = old.get("items") or {}
        url = old.get("post_url")   # 오늘 게시가 없으면(dry-run · 0건) 지난 글 주소 그대로
        if post_url_path and os.path.exists(post_url_path):
            url = open(post_url_path, encoding="utf-8").read().strip() or url
        write(build([(radar, cards)], prior=prior, post_url=url), path)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[mentions] 종목 · 증시 리포트용 발언 파일 실패 (글은 계속): {e!r}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--from-git" in sys.argv:
        write(from_git())
