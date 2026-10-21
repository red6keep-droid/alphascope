"""분류된 발언 → output/radar.json (기획 3절 · 5절). LLM 없음.

신호 = 같은 인물 · 같은 주제(+하위주제) · 최근 24시간의 시장 관련 발언(관련도 ≥ RELEVANCE_EVENT_MIN) 묶음.
  1차와 2차가 같이 있으면 1차가 대표(원문 링크), 2차는 '보도 매체 수'로만 남는다.
인물 순서 = 가장 강한 신호의 (강도, 관련도, 보도 매체 수). 신호 0개면 게시하지 않는다 (publish 가 event_count 를 본다).
접힘 '인물별 추이' = 최근 7일 인물 × 주제 신호 수 — 직전 7일과 달라진 줄만 (매일 같은 표를 내지 않는다, 기획 3절).
오늘 시장 맥락 = 데일리 리포트 이력(report-state)의 시장 상태 점수 · S&P 500 · 나스닥 하루 등락 — 없으면 구획 생략.
"""

import datetime
import json
import os
import subprocess
import sys

import config
import db

RELEVANCE_EVENT_MIN = 2   # trump-trend 와 같다
WINDOW_HOURS = 24
TREND_DAYS = 7


def _ago(**kw):
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(**kw)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _labeled(conn, since, until=None):
    q = """SELECT * FROM statements WHERE analyzed_at IS NOT NULL AND noise_reason IS NULL
             AND ai_market_relevance >= ? AND published_at >= ?"""
    args = [RELEVANCE_EVENT_MIN, since]
    if until:
        q += " AND published_at < ?"
        args.append(until)
    return conn.execute(q + " ORDER BY published_at", args).fetchall()


def _loads(v):
    try:
        return json.loads(v) if v else []
    except ValueError:
        return []


def build_signals(rows):
    sig = {}
    for r in rows:
        key = (r["speaker"], r["ai_topic"], (r["ai_subtopic"] or "").strip().lower())
        s = sig.setdefault(key, {"speaker": key[0], "topic": r["ai_topic"], "subtopic": r["ai_subtopic"] or "",
                                 "items": [], "companies": [], "sectors": [], "countries": []})
        s["items"].append(r)
        for f, col in (("companies", "ai_mentioned_companies"), ("sectors", "ai_target_sector"), ("countries", "ai_target_country")):
            s[f] += [x for x in _loads(r[col]) if x not in s[f]]
    out = []
    for s in sig.values():
        items = s.pop("items")
        prim = [r for r in items if r["source_kind"] == "primary"]
        lead = max(prim or items, key=lambda r: (r["ai_intensity"], r["ai_market_relevance"]))
        dirs = [r["ai_direction"] for r in items]
        s.update({
            "intensity": max(r["ai_intensity"] for r in items),
            "relevance": max(r["ai_market_relevance"] for r in items),
            "direction": lead["ai_direction"] if dirs.count(lead["ai_direction"]) * 2 >= len(dirs) else max(set(dirs), key=dirs.count),
            "source_kind": "primary" if prim else "secondary",
            "attribution": lead["attribution"],
            "n_primary": len(prim),
            "n_reports": sum((r["group_size"] or 1) for r in items if r["source_kind"] == "secondary"),
            "first_at": items[0]["published_at"], "last_at": items[-1]["published_at"],
            "lead": {"id": lead["id"], "title": lead["title"], "quote": lead["quote"], "url": lead["url"],
                     "publisher": lead["publisher"], "body": (lead["body"] or "")[:600], "sub_speaker": lead["sub_speaker"]},
            "others": [{"title": r["title"], "url": r["url"], "publisher": r["publisher"], "kind": r["source_kind"]}
                       for r in items if r["id"] != lead["id"]][:5],
        })
        # 순서 점수 = 관련도 × 10 + 강도 + 보도 매체 수(10 상한) — 많이 보도된 발언 = 시장이 주목한 발언 (10-19 Claude 확정)
        s["score"] = s["relevance"] * 10 + s["intensity"] + min(s["n_reports"], 10)
        out.append(s)
    out.sort(key=lambda s: -s["score"])
    return out


def by_person(signals):
    people = {}
    for s in signals:
        people.setdefault(s["speaker"], []).append(s)
    order = sorted(people, key=lambda k: -people[k][0]["score"])
    return [{"speaker": k, "name_ko": config.PEOPLE[k]["name_ko"], "title_ko": config.PEOPLE[k]["title_ko"],
             "group": config.PEOPLE[k]["group"], "signals": people[k]} for k in order]


def trend_changes(conn):
    """인물 × 주제 신호 수: 최근 7일 vs 직전 7일 — 달라진 줄만."""
    def counts(since, until):
        c = {}
        for s in build_signals(_labeled(conn, since, until)):
            c[(s["speaker"], s["topic"])] = c.get((s["speaker"], s["topic"]), 0) + 1
        return c
    # 신호는 24시간 단위가 아니라 기간 전체 묶음이라, 날짜별로 따로 세어 더한다
    def daily(days_from, days_to):
        total = {}
        for d in range(days_from, days_to):
            for k, v in counts(_ago(days=d + 1), _ago(days=d)).items():
                total[k] = total.get(k, 0) + v
        return total
    now7, prev7 = daily(0, TREND_DAYS), daily(TREND_DAYS, TREND_DAYS * 2)
    rows = []
    for k in set(now7) | set(prev7):
        a, b = now7.get(k, 0), prev7.get(k, 0)
        if a != b:
            rows.append({"speaker": k[0], "name_ko": config.PEOPLE[k[0]]["name_ko"], "topic": k[1], "days7": a, "prev7": b})
    rows.sort(key=lambda r: (-r["days7"], -(r["days7"] - r["prev7"])))
    return rows


KEYWORDS_MAX = 6   # 인물 상세 '많이 말한 키워드' 수
STRIP_DAYS = 30   # 인물 발언 띠 — 최근 30일 vs 직전 30일 (2026-10-21 사용자: 반복 발언 통계 그래프)


def history(conn):
    """날짜별 신호를 60일 치 모아 추이 탭 재료를 만든다 (2026-10-21 사용자: 인물 목록 · 주제 반복 · 대상 통계).
    신호는 24시간 단위가 아니라 기간 전체 묶음이라 하루씩 따로 세어 더한다 (trend_changes 와 같은 이유).
    people_trend: 인물별 최근 7일 · 직전 7일 신호 수(전원). topic_trend: 주제별 7일 · 직전 7일 · 말한 인물 · 며칠째 이어지는지.
    targets7: 최근 7일 언급 종목 · 섹터와 누가 몇 번. strips: 인물별 60일 띠(하루 신호 수 · 가장 많은 주제)."""
    days = []   # days[d] = d일 전 하루의 신호 목록 (0 = 오늘)
    for d in range(STRIP_DAYS * 2):
        days.append(build_signals(_labeled(conn, _ago(days=d + 1), _ago(days=d))))

    def window(a, b):
        return [s for d in range(a, b) for s in days[d]]

    now7, prev7 = window(0, TREND_DAYS), window(TREND_DAYS, TREND_DAYS * 2)

    def count_by(sigs, key):
        c = {}
        for s in sigs:
            c[key(s)] = c.get(key(s), 0) + 1
        return c

    pn, pp = count_by(now7, lambda s: s["speaker"]), count_by(prev7, lambda s: s["speaker"])
    people_trend = {k: {"days7": pn.get(k, 0), "prev7": pp.get(k, 0)} for k in set(pn) | set(pp)}

    tn, tp = count_by(now7, lambda s: s["topic"]), count_by(prev7, lambda s: s["topic"])
    topic_trend = []
    for t in set(tn) | set(tp):
        streak = 0
        for d in range(STRIP_DAYS):   # 오늘부터 거슬러 올라가며 그 주제 신호가 있는 날이 이어지는 수
            if any(s["topic"] == t for s in days[d]):
                streak += 1
            else:
                break
        who = {}
        for s in now7:
            if s["topic"] == t:
                who[s["speaker"]] = who.get(s["speaker"], 0) + 1
        topic_trend.append({"topic": t, "days7": tn.get(t, 0), "prev7": tp.get(t, 0), "streak": streak,
                            "speakers": [{"speaker": k, "name_ko": config.PEOPLE[k]["name_ko"], "n": v}
                                         for k, v in sorted(who.items(), key=lambda kv: -kv[1])]})
    topic_trend.sort(key=lambda r: (-r["days7"], -(r["days7"] - r["prev7"])))

    tg = {}
    for s in now7:
        for kind, names in (("company", s["companies"]), ("sector", s["sectors"])):
            for n in names:
                e = tg.setdefault((kind, n), {"kind": kind, "name": n, "n": 0, "speakers": {}, "dirs": {"positive": 0, "negative": 0, "neutral": 0}})
                e["n"] += 1
                e["dirs"][s["direction"] if s["direction"] in e["dirs"] else "neutral"] += 1   # 그 대상에 긍정 · 부정 · 중립 몇 번 (2026-10-21 사용자)
                e["speakers"][s["speaker"]] = e["speakers"].get(s["speaker"], 0) + 1
    targets7 = sorted(({"kind": e["kind"], "name": e["name"], "n": e["n"], "dirs": e["dirs"],
                        "speakers": [{"speaker": k, "name_ko": config.PEOPLE[k]["name_ko"], "n": v}
                                     for k, v in sorted(e["speakers"].items(), key=lambda kv: -kv[1])]}
                       for e in tg.values()), key=lambda r: -r["n"])

    strips = {}
    for d, sigs in enumerate(days):
        for s in sigs:
            cell = strips.setdefault(s["speaker"], [{"n": 0, "topic": None, "by_topic": {}} for _ in range(STRIP_DAYS * 2)])[d]
            cell["n"] += 1
            bt = cell["by_topic"].setdefault(s["topic"], {"n": 0, "positive": 0, "negative": 0, "neutral": 0})   # 주제별 건수 · 방향 (2026-10-21 사용자: 긍정 · 부정도)
            bt["n"] += 1
            bt[s["direction"] if s["direction"] in bt else "neutral"] += 1
    for cells in strips.values():
        for c in cells:
            c["topic"] = max(c["by_topic"].items(), key=lambda kv: kv[1]["n"])[0] if c["n"] else None
    # 인물별 키워드 = 최근 30일 세부 주제(ai_subtopic, 분류 LLM 이 "Tariff" · "Oil Prices" 처럼 짧은 명사구로 통일) 건수 · 긍정 · 부정 (2026-10-21 사용자:
    # "에너지 · 지정학 · 무역으로는 모르겠다, 키워드로"). 세부 주제가 없으면 큰 주제. 한국어 표기는 narrate 가 채우는 subtopic_ko.json (render 가 읽는다)
    kw = {}
    for s in window(0, STRIP_DAYS):
        key = (s.get("subtopic") or "").strip() or s["topic"]
        e = kw.setdefault(s["speaker"], {}).setdefault(key.lower(), {"key": key, "n": 0, "positive": 0, "negative": 0, "neutral": 0})
        e["n"] += 1
        e[s["direction"] if s["direction"] in e else "neutral"] += 1
    keywords = {sp: sorted(d.values(), key=lambda x: -x["n"])[:KEYWORDS_MAX] for sp, d in kw.items()}
    return {"people_trend": people_trend, "topic_trend": topic_trend, "targets7": targets7, "strips": strips, "keywords": keywords}


def market_context():
    """데일리 리포트 최신 이력 — 로컬은 상태 브랜치에서, CI 는 꺼내 둔 파일에서. 실패하면 None."""
    hist_dir = os.path.join(config.BASE_DIR, "..", "daily-report", "output", "state", "history")
    try:
        if os.path.isdir(hist_dir) and os.listdir(hist_dir):
            with open(os.path.join(hist_dir, sorted(os.listdir(hist_dir))[-1]), encoding="utf-8") as f:
                d = json.load(f)
        else:
            names = subprocess.run(["git", "ls-tree", "--name-only", "origin/report-state",
                                    "experiments/daily-report/output/state/history/"], capture_output=True, text=True,
                                   check=True, cwd=config.BASE_DIR).stdout.split()
            d = json.loads(subprocess.run(["git", "show", f"origin/report-state:{sorted(names)[-1]}"], capture_output=True,
                                          text=True, check=True, cwd=config.BASE_DIR).stdout)
    except Exception as e:  # noqa: BLE001
        print(f"[aggregate] 시장 맥락 없음: {str(e)[:80]}")
        return None
    rg, sr = d.get("regime") or {}, d.get("series") or {}
    return {"as_of": d.get("as_of"), "score": rg.get("score"), "label": rg.get("label"), "delta": rg.get("delta"),
            "spx_1d": (sr.get("^GSPC") or {}).get("ret_1d"), "ndx_1d": (sr.get("^IXIC") or {}).get("ret_1d")}


def build(conn, path=None):
    signals = build_signals(_labeled(conn, _ago(hours=WINDOW_HOURS)))
    people = by_person(signals)
    pend = conn.execute("""SELECT COUNT(*) FROM statements WHERE published_at >= ? AND noise_reason IS NULL AND analyzed_at IS NULL
                             AND (source_kind='primary' OR (group_id=id AND is_statement=1 AND dup_of_primary IS NULL))""",
                        (_ago(hours=WINDOW_HOURS),)).fetchone()[0]
    out = {
        "generated_at": db.now_iso(), "window_hours": WINDOW_HOURS,
        "event_count": len(signals), "people_count": len(people),
        "only_reports": bool(signals) and all(s["source_kind"] == "secondary" for s in signals),
        "pending": pend,
        "people": people,
        "trend_changes": trend_changes(conn),
        "market": market_context(),
    }
    out.update(history(conn))   # 추이 탭 — 인물 목록 · 주제 반복 막대 · 언급 대상 · 인물 띠 (2026-10-21 사용자)
    path = path or os.path.join(config.OUTPUT_DIR, "radar.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"[aggregate] 신호 {len(signals)}개 · 인물 {len(people)}명 · 추이 변화 {len(out['trend_changes'])}줄 · 미분류 {pend} → {path}")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build(db.connect())
