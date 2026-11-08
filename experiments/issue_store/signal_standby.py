"""대기 시나리오 장전 — 뉴스로 걸고, 가격으로 확인 (기획 증시-전망-기획 8-19, 2026-11-08 사용자: "왜 설계만 하나").

검증 3-a 결론대로: 전쟁 · 휴전 같은 지정학은 가격이 미리 움직이지 않는다 → 장전은 **뉴스**(공용 뉴스 처리의 이슈 코드 · 제목)로 건다.
가격은 ① 격발 후보(사슬 고리 지표가 예상 방향으로 움직였나) ② 서명 일치(그날 반응이 그 사건 종류 모양인가)에만 쓴다.
그림자 모드 — 독자 노출 · 알림 없음. 전망 등록(틀 R · S)으로 넘기는 일은 자동 등록(기획 8-6) 때.

signal_scan.py 가 매일 부른다 (update). 단독 실행 = 미리보기:
    python experiments/issue_store/signal_standby.py
기록 (state 있을 때):
    records/standby/armed.json        지금 장전된 시나리오 (최대 MAX_ARMED, 같은 사슬 하나)
    records/standby/standby.jsonl     장전 · 격발 후보 · 서명 일치 · 내림 사건 한 줄씩
    records/standby/news_counts.jsonl 날마다 주제별 48시간 기사 수 — 평소 값(기준선)이 쌓인다
AI 0. 뉴스 = gh-pages news_store_home.json (공용 뉴스 처리 결과, 하루 두 번 갱신 · 약 일주일 보관).
"""
import collections
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import chains as CH  # noqa: E402
import signal_signatures as SS  # noqa: E402

NEWS_URL = "https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages/news_store_home.json"
RULES = "SB-2026-11-08a"
N_MIN, X_BASE, MAX_ARMED, LIFE_DAYS = 3, 2.0, 5, 30   # 48시간 3건 이상 · 평소의 2배 · 동시 5 · 30일 뒤 내림
FIRE_LINKS = 2                                          # 격발 후보 = 사슬 고리 지표 2개 이상이 예상 방향으로 (10일 2σ 또는 하루 3σ)

# 주제 → (사슬, 이슈 코드, 글 패턴, 서명 묶음). 한 기사는 위에서부터 먼저 맞는 주제 하나 — 휴전이 전쟁보다 먼저
TOPICS = [
    ("CEASEFIRE", {"GEOPOLITICS"}, r"ceasefire|cease-fire|truce|peace (talks|deal|agreement|plan|accord)|armistice|휴전|종전|평화 ?(협상|합의|협정|안)|정전", "휴전 · 종전"),
    ("SANCTIONS_LIFT", {"GEOPOLITICS", "REGULATION", "OIL_ENERGY"}, r"(lift|ease|easing|remov|relax)\w* (of )?sanction|sanctions? (relief|lifted|eased)|제재 ?(해제|완화)", "유가 급락"),
    ("WAR", {"GEOPOLITICS"}, r"airstrike|air strike|strikes? on|attack|invasion|invade|missile|escalat|drone|troops|offensive|공습|공격|침공|미사일|확전|교전|드론|폭격", "전쟁 · 테러"),
    ("OIL_SUPPLY_RETURN", {"OIL_ENERGY"}, r"output (hike|increase|boost|rise)|raise (output|production)|supply (return|resum)|production (resum|restart)|증산|공급 재개|생산 재개", "유가 급락"),
    ("OIL_SPIKE", {"OIL_ENERGY", "GEOPOLITICS"}, r"output cut|production cut|supply (disruption|cut|shock)|hormuz|tanker|refinery (attack|fire)|감산|공급 차질|호르무즈|유조선", "유가 급등"),
    ("REGULATION", {"REGULATION"}, r"export control|chip (ban|export)|antitrust (suit|probe|case)|entity list|수출 ?통제|반도체 수출|반독점 (소송|조사)|거래 제한 명단", "정책 · 규제"),   # 넓은 말(금지 · 조사)은 뺐다 — 정치 기부 금지 같은 기사가 걸림
    ("TARIFF", {"TARIFF_TRADE"}, r"tariff|trade war|관세|무역 ?전쟁", "정책 · 규제"),
]
_PAT = [(cid, iss, re.compile(p, re.I), fam) for cid, iss, p, fam in TOPICS]
TEXT_ONLY = {"CEASEFIRE", "SANCTIONS_LIFT", "WAR", "OIL_SUPPLY_RETURN", "OIL_SPIKE", "TARIFF"}   # 이슈 코드가 비었거나 OTHER 인 기사(종목 레이더 뉴스 대부분)는 뜻이 분명한 주제만 글로
_BOARD_BY_FILE = {path.split("/", 1)[1]: name for name, (path, _) in SS.BOARD.items()}


RADAR_NEWS = os.path.join(HERE, "..", "stock-radar", "data", "news.json")   # 같은 워크플로의 종목 레이더 뉴스(약 일주일 · 회사 위주) — 있으면 더한다


def load_news(path=None):
    """홈 공용 뉴스(gh-pages) + 종목 레이더 뉴스(있으면). 같은 주소는 하나만."""
    out, seen = [], set()
    for src in ([path] if path else [NEWS_URL]) + [RADAR_NEWS]:
        try:
            if src.startswith("http"):
                import requests
                d = requests.get(src, timeout=30, headers={"User-Agent": "alphascope-research/1.0"}).json()
            elif os.path.exists(src):
                d = json.load(open(src, encoding="utf-8"))
            else:
                continue
        except Exception as e:  # noqa: BLE001
            print(f"[standby] 뉴스 못 받음({os.path.basename(src)}): {type(e).__name__}")
            continue
        for it in (d.values() if isinstance(d, dict) else d):
            key = it.get("url") or it.get("item_id")
            if key and key not in seen:
                seen.add(key)
                out.append(it)
    if not out:
        print("[standby] 뉴스 없음 — 오늘 장전 판단 없음")
    return out


def topic_of(item):
    text = " ".join(str(item.get(k) or "") for k in ("title", "title_ko", "fact", "fact_en", "subtopic"))
    iss = item.get("issue")
    loose = iss in (None, "", "OTHER")
    for cid, codes, pat, _ in _PAT:
        if (iss in codes or (loose and cid in TEXT_ONLY)) and pat.search(text):
            return cid
    return None


def _ts(item):
    try:
        return dt.datetime.fromisoformat(str(item.get("published_at", "")).replace("Z", "+00:00"))
    except ValueError:
        return None


def counts(items, now):
    """주제별 (최근 48시간 기사, 그 앞 기간의 48시간당 평균) — 뉴스 보관 기간(약 일주일) 안에서."""
    recent, before, oldest = collections.defaultdict(list), collections.Counter(), now
    for it in items:
        t = _ts(it)
        cid = topic_of(it)
        if not t or not cid:
            continue
        oldest = min(oldest, t)
        if now - t <= dt.timedelta(hours=48):
            recent[cid].append(it)
        else:
            before[cid] += 1
    span = max(0.0, (now - dt.timedelta(hours=48) - oldest).total_seconds() / 172800)   # 앞 기간 = 48시간 몇 개분
    return recent, {cid: (before[cid] / span if span >= 1 else None) for cid, *_ in TOPICS}


def _read_jsonl(path):
    try:
        return [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
    except OSError:
        return []


def baseline(cid, hist, store_base):
    """평소 48시간 기사 수 — 쌓인 기록(최근 30일 중앙값)이 5일 이상이면 그것, 아니면 뉴스 보관 기간 평균. 둘 다 없으면 None."""
    vals = [h["n"].get(cid, 0) for h in hist[-30:]]
    if len(vals) >= 5:
        vals = sorted(vals)
        return float(vals[len(vals) // 2])
    return store_base.get(cid)


def update(state_dir=None, z=None, cands=(), day=None, news_path=None):
    """매일 한 번. z = {보드 지표 이름: (하루 z, 10일 z)} — signal_scan 이 넘긴다. cands = 오늘 서명 후보 [(묶음, 유사도)]."""
    now = dt.datetime.now(dt.timezone.utc)
    day = day or now.strftime("%Y-%m-%d")
    d = os.path.join(state_dir, "records", "standby") if state_dir else None
    armed = json.load(open(os.path.join(d, "armed.json"), encoding="utf-8")) if d and os.path.exists(os.path.join(d, "armed.json")) else []
    hist = _read_jsonl(os.path.join(d, "news_counts.jsonl")) if d else []
    items = load_news(news_path)
    recent, store_base = counts(items, now) if items else ({}, {})
    log = []

    # ① 장전 — 뉴스
    for cid, codes, _, fam in TOPICS:
        n = len(recent.get(cid, []))
        base = baseline(cid, hist, store_base)
        hot = n >= N_MIN and (base is None or n >= X_BASE * max(base, 0.5))
        if not hot or any(a["chain"] == cid for a in armed) or len(armed) >= MAX_ARMED:
            continue
        ch = CH.CHAINS.get(cid, {})
        heads = sorted(recent[cid], key=lambda it: str(it.get("published_at")), reverse=True)[:3]
        ctry = collections.Counter(c for it in recent[cid] for c in (it.get("countries") if isinstance(it.get("countries"), list) else []))
        a = {"id": f"SB-{day.replace('-', '')}-{cid}", "chain": cid, "name": ch.get("name", cid), "family": fam, "armed": day,
             "expires": (dt.date.fromisoformat(day) + dt.timedelta(days=LIFE_DAYS)).isoformat(), "status": "장전",
             "evidence": {"n48": n, "base48": None if base is None else round(base, 1),
                          "headlines": [(it.get("title_ko") or it.get("title") or "")[:120] for it in heads], "countries": [c for c, _ in ctry.most_common(3)]},
             "links": [(nm, px, sg) for nm, px, sg, *_ in ch.get("links", [])], "forks": ch.get("forks", []), "fired": None, "signature": None, "rules": RULES}
        armed.append(a)
        log.append({"day": day, "event": "장전", "id": a["id"], "chain": cid, "n48": n, "base48": a["evidence"]["base48"]})

    # ② 격발 후보 · 서명 일치 — 가격 / ③ 내림 — 30일
    keep = []
    for a in armed:
        if day >= a["expires"]:
            log.append({"day": day, "event": "내림", "id": a["id"], "chain": a["chain"], "fired": a.get("fired")})
            continue
        if z and not a.get("fired"):
            hits = []
            for nm, px, sg in a["links"]:
                b = _BOARD_BY_FILE.get(px)
                if b in z:
                    zd, z10 = z[b]
                    if (zd is not None and sg * zd >= SS.Z_DAY) or (z10 is not None and sg * z10 >= 2.0):
                        hits.append((nm, b, round(zd or 0, 1), round(z10 or 0, 1)))
            if len(hits) >= FIRE_LINKS:
                a["fired"] = {"day": day, "links": hits}
                a["status"] = "격발 후보"
                log.append({"day": day, "event": "격발 후보", "id": a["id"], "chain": a["chain"], "links": hits})
        if cands and not a.get("signature") and any(f == a["family"] for f, _ in cands):
            a["signature"] = {"day": day, "candidates": list(cands)}
            log.append({"day": day, "event": "서명 일치", "id": a["id"], "chain": a["chain"], "candidates": list(cands)})
        keep.append(a)
    armed = keep

    today_counts = {"day": day, "n": {cid: len(recent.get(cid, [])) for cid, *_ in TOPICS}, "items": len(items)}
    if d:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "armed.json"), "w", encoding="utf-8") as f:
            json.dump(armed, f, ensure_ascii=False, indent=1)
        with open(os.path.join(d, "news_counts.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(today_counts, ensure_ascii=False) + "\n")
        if log:
            with open(os.path.join(d, "standby.jsonl"), "a", encoding="utf-8") as f:
                for row in log:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
    hot = ", ".join(f"{c} {n}" for c, n in today_counts["n"].items() if n) or "없음"
    print(f"[standby] {day} 뉴스 {len(items)}건 · 48시간 주제별 {hot} · 장전 {len(armed)}개"
          + "".join(f"\n  - {a['status']} {a['name']} ({a['armed']} ~ {a['expires']}) 근거 {a['evidence']['n48']}건 · 평소 {a['evidence']['base48']}"
                    + (f" · 격발 {a['fired']['day']}" if a.get("fired") else "") for a in armed))
    return armed, log


if __name__ == "__main__":
    update(news_path=sys.argv[1] if len(sys.argv) > 1 else None)
