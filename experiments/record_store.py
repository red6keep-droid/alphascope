"""기록 저장소 — 우리가 매일 만든 판정 · 이슈를 덮어쓰지 않고 연도별 JSONL 에 덧붙인다.

왜: 블로그 목적(doc/기획/블로그-목적과-방향.md 6절 1번) — 남이 갖지 못한 기록이 경쟁력. 지금은 판정(analysis.json · radar.json 등)이
매일 덮어써져 "같은 일이 과거에는 어떻게 됐나" 를 뒤에 계산할 수 없다 (데이터-기록-계획 A3-1 ②, 2026-10-22 사용자: "진행해").

어디에: 각 파이프라인의 상태 폴더(STATE_DIR) 아래 records/{kind}/{YYYY}.jsonl — 워크플로가 상태 폴더를 통째로 상태 브랜치에
올리므로 새 브랜치 · 새 단계 없이 쌓인다. 네 리포트가 같은 모양으로 쓰니 뒤에 한 번에 읽는다 (기록 계획 2부의 issue-store 브랜치는
한 브랜치에 네 워크플로가 push 하면 거부되는 문제가 있어 파이프라인별 브랜치로 — 읽는 쪽이 합친다).

종류(kind):
    verdicts  우리 판정 — 날짜 · 대상 · 상태 · 값 · 근거. "그날 우리가 뭐라 했나" (A4 적중 기록의 재료)
    issues    분류된 이슈 — 이슈 코드(experiments/issue_codes.py) · 범위 · 종목 · 강도 · 방향 · 출처. "그날 무슨 일이 있었나"

공통 칸: date(리포트 날짜 KST) · as_of(기준 거래일) · source(daily · nvda · trump · radar) · id(같은 날 안에서 고유).
같은 (date, id) 가 이미 있으면 바꾼다 — 같은 날 다시 돌려도 두 줄이 되지 않는다. 반응(1 · 5 · 20일 뒤)은 여기 쓰지 않고
읽는 쪽이 일봉으로 계산한다 — 기록은 "그날 알 수 있었던 것" 만.

    record_store.append(state_dir, "verdicts", rows)
    record_store.read(state_dir, "issues", year=2026)
"""

import json
import os

REQUIRED = ("date", "source", "id")


def _path(state_dir, kind, year):
    return os.path.join(state_dir, "records", kind, f"{year}.jsonl")


def read(state_dir, kind, year):
    path = _path(state_dir, kind, year)
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def append(state_dir, kind, rows):
    """rows 를 연도별 파일에 덧붙인다. 같은 (date, id) 는 새 줄로 바꾼다. 쓴 줄 수를 돌려준다. 실패해도 예외를 내지 않는다 — 기록은
    게시를 막지 않는다 (운영지침 D6-2 와 같은 원칙)."""
    if not state_dir or not rows:
        return 0
    try:
        by_year = {}
        for r in rows:
            if any(not r.get(k) for k in REQUIRED):
                continue
            by_year.setdefault(str(r["date"])[:4], []).append(r)
        n = 0
        for year, new in by_year.items():
            old = read(state_dir, kind, year)
            keys = {(r["date"], r["id"]) for r in new}
            kept = [r for r in old if (r.get("date"), r.get("id")) not in keys]
            path = _path(state_dir, kind, year)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                for r in kept + new:
                    f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
            n += len(new)
        print(f"[records] {kind} {n}줄 → {os.path.join(state_dir, 'records', kind)}")
        return n
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[records] {kind} 저장 실패 (게시는 계속): {e!r}")
        return 0


def _issue_from_topic(topic):
    """트럼프 트렌드 주제 → 이슈 코드 (experiments/issue_codes.FROM_PEOPLE_TOPIC 과 같은 표)."""
    try:
        import issue_codes
        return issue_codes.FROM_PEOPLE_TOPIC.get(str(topic or ""), "OTHER")
    except Exception:  # noqa: BLE001
        return "OTHER"


def _num(v, digits=2):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else round(f, digits)


# ---------------------------------------------------------------- 파이프라인별 행 만들기 (모양을 한 곳에)

def daily_rows(input_data, report, analysis):
    """데일리 리포트 → verdicts 1줄(시장) + issues(선정 뉴스마다 1줄). analysis 는 없을 수 있다(그림자 모드)."""
    date = input_data.get("date")
    a = analysis or {}
    sr = a.get("series") or {}
    idx = (input_data.get("market") or {}).get("indices") or {}
    pos = (a.get("position") or {}).get("sp500") or {}
    verdict = {
        "date": date, "as_of": a.get("as_of") or date, "source": "daily", "id": "market", "target": "market", "symbols": ["^GSPC", "^IXIC", "^DJI"],
        "one_line": (report or {}).get("one_line"),
        "spx_1d": _num((sr.get("^GSPC") or {}).get("ret_1d")) if sr else _num((idx.get("sp500") or {}).get("change_pct")),
        "ndx_1d": _num((sr.get("^IXIC") or {}).get("ret_1d")) if sr else _num((idx.get("nasdaq") or {}).get("change_pct")),
        "vix": _num(((a.get("vix") or {}).get("now")) if a else (idx.get("vix") or {}).get("price")),
        "spx_position": pos.get("position_label"),
        "breadth": (a.get("breadth") or {}).get("label"),
        "rates": (a.get("rates") or {}).get("growth_label"),
        "regime": ((a.get("regime") or {}).get("label")),
        "status": a.get("status"),
    }
    issues = []
    news = input_data.get("news") or []
    for i, it in enumerate((report or {}).get("news") or []):
        k = it.get("index")
        src = news[k] if isinstance(k, int) and 0 <= k < len(news) else {}
        issues.append({
            "date": date, "as_of": verdict["as_of"], "source": "daily", "id": f"news{i}", "issue": it.get("issue") or "OTHER",
            "subtopic": it.get("subtopic") or "", "scope": it.get("scope"), "symbols": [s for s in (it.get("related") or []) if isinstance(s, str)],
            "theme": it.get("theme"), "scheduled": bool(it.get("scheduled")), "surprise": it.get("surprise"),
            "title": src.get("title") or it.get("title_ko"), "title_ko": it.get("title_ko"), "why": it.get("why"),
            "publisher": src.get("source"), "url": src.get("link"), "published": src.get("published"),
        })
    return [verdict], issues


def nvda_rows(analysis):
    """엔비디아 리포트 → verdicts 1줄(상태판 flag 가 선 칸 · 헤드라인 수치) + issues(이벤트마다 1줄)."""
    date, day = analysis.get("run_date"), analysis.get("day")
    h = analysis.get("headline") or {}
    st = analysis.get("status") or {}
    flags = {sec: [x["key"] for x in (st.get(sec) or []) if isinstance(x, dict) and x.get("flag")] for sec in ("price", "technical", "options", "flows", "valuation")}
    verdict = {
        "date": date, "as_of": day, "source": "nvda", "id": "NVDA", "target": "stock", "symbols": ["NVDA"],
        "close": _num(h.get("close")), "ret_1d": _num(h.get("ret_1d")), "ret_vs_spy": _num(h.get("ret_vs_spy")), "ret_vs_smh": _num(h.get("ret_vs_smh")),
        "vol_ratio_20d": _num(h.get("vol_ratio_20d")), "gap": _num(h.get("gap")), "flags": {k: v for k, v in flags.items() if v},
        "next_earnings": analysis.get("next_earnings"), "events_total": analysis.get("events_total"),
    }
    issues = []
    for i, e in enumerate(analysis.get("events") or []):
        issues.append({
            "date": date, "as_of": day, "source": "nvda", "id": f"event{i}", "issue": e.get("issue") or "", "area": e.get("area"), "kind": e.get("kind"),
            "scope": "stock", "symbols": ["NVDA"], "direction": e.get("direction"), "emphasis": bool(e.get("emphasis")),
            "title": e.get("title"), "fact": e.get("fact"), "publisher": e.get("source"), "url": e.get("url"), "published": e.get("published_at"),
        })
    return [verdict], issues


def trump_rows(analysis, date):
    """트럼프 트렌드 → issues(최근 24시간 이벤트마다 1줄) + verdicts(추이 점수 상위 — 그날 "뜨는 주제" 판정)."""
    issues = []
    for e in analysis.get("recent_events") or []:
        issues.append({
            "date": date, "as_of": e.get("effective_day") or date, "source": "trump", "id": e.get("event_id") or f"{e.get('topic')}/{e.get('first_post_at')}",
            "issue": e.get("issue") or _issue_from_topic(e.get("topic")), "topic": e.get("topic"), "subtopic": e.get("subtopic"), "scope": "market", "symbols": e.get("symbols") or [],
            "target": e.get("target"), "direction": e.get("direction"), "intensity": e.get("intensity"), "post_count": e.get("post_count"),
            "session": e.get("session"), "published": e.get("first_post_at"),
        })
    verdicts = [{
        "date": date, "as_of": date, "source": "trump", "id": "trend", "target": "market",
        "top_trends": [{"key": t.get("key"), "score": t.get("score"), "events_7d": t.get("events_7d"), "delta": (t.get("events_7d") or 0) - (t.get("events_prev_7d") or 0)}
                       for t in (analysis.get("trend_scores") or [])[:5]],
        "posts_24h": ((analysis.get("post_volume") or {}).get("last_24h") or {}).get("total"),
        "policy_24h": ((analysis.get("post_volume") or {}).get("last_24h") or {}).get("policy"),
    }]
    return verdicts, issues


def radar_rows(radar, date):
    """인물 발언 레이더 → issues(신호마다 1줄) + verdicts 1줄(그날 신호 수 · 1순위 인물 · 시장 맥락)."""
    issues = []
    people = radar.get("people") or []
    for p in people:
        for j, s in enumerate(p.get("signals") or []):
            lead = s.get("lead") or {}
            issues.append({
                "date": date, "as_of": date, "source": "radar", "id": f"{p.get('speaker')}/{j}", "speaker": p.get("speaker"), "speaker_ko": p.get("name_ko"),
                "issue": s.get("issue") or "", "topic": s.get("topic"), "subtopic": s.get("subtopic"), "scope": "market",
                "symbols": s.get("companies") or [], "sectors": s.get("sectors") or [], "countries": s.get("countries") or [],
                "direction": s.get("direction"), "intensity": s.get("intensity"), "relevance": s.get("relevance"), "score": s.get("score"),
                "source_kind": s.get("source_kind"), "n_reports": s.get("n_reports"),
                "title": lead.get("title"), "quote": lead.get("quote"), "publisher": lead.get("publisher"), "url": lead.get("url"), "published": s.get("first_at"),
            })
    verdicts = [{
        "date": date, "as_of": date, "source": "radar", "id": "radar", "target": "market",
        "event_count": radar.get("event_count"), "people_count": radar.get("people_count"),
        "lead_speaker": people[0].get("speaker") if people else None, "only_reports": radar.get("only_reports"),
        "market": radar.get("market"),
    }]
    return verdicts, issues
