"""종목 페이지 매일 기록 — 카드 판정 · 애널리스트 · 방송 의견 · 종목 뉴스 분류를 record_store 에 덧붙인다
(doc/기획/데이터-기록-계획.md A5-4 · A5-6 2단계, 2026-11-01 사용자: "그렇게 진행해").

왜: 한국 35 · 미국 64 종목 페이지의 판정은 매일 다시 그려지며 사라졌고(A3-1 8), 미국 종목 뉴스 분류(news.json)는 8일만 남는다.
방송 의견 · 이익 예상 · 뉴스 분류는 우리가 그날 만든 것이라 지나면 다시 못 만든다 — 호재 · 리스크가 가격에 어떻게 반응했나(2부 이슈 저장소)의 재료.

    verdicts  {sym}/{key}         카드 판정 — signal_groups 꼬리표(방향 · 기간 · 계열 · 분류표 버전) 그대로
              {sym}/analysts      애널리스트 등급 분포 · 목표가 (계열 = 바깥 의견)
              {sym}/pick/{해시}    방송 의견 한 건 — 인물별 (A5-7 2: 인물별로 남긴다). date = 영상 게시일(KST) — 5일 동안 매일 다시 보여도 한 줄
    issues    news/{item_id}      미국 종목 뉴스 분류 한 건(news_store) — 이슈 코드 · 종목별 관련도 · 방향. date = 기사 게시일(KST)
한국 종목의 방송 이슈는 미디어 데일리가 이미 media-state 에 쌓는다 — 여기서는 다시 쓰지 않는다.
나중 결과(1 · 5 · 20일)는 쓰지 않는다 — 읽는 쪽이 일봉으로 계산한다(record_store 원칙). 실패해도 게시는 계속(record_store.append 가 삼킨다).
"""

import datetime
import hashlib

import record_store
import signal_groups as SG

KST = datetime.timezone(datetime.timedelta(hours=9))
PICK_DIR = {"매수": SG.UP, "매도": SG.DOWN}   # 보유 · 관망 = 중립 (A5-3 바깥 의견: 매수 → 상승 쪽 · 매도 → 하락 쪽)


def _kst_day(iso):
    try:
        d = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return (d.astimezone(KST) if d.tzinfo else d).strftime("%Y-%m-%d")
    except ValueError:
        return str(iso)[:10]


def verdict_rows(date, source, s, got, picks=(), name=None):
    """한 종목의 판정 줄. got = {signal_groups 키: 함께 보기 줄(이름, 판정 말, 방향, 탭, 카드, 기간)} — 페이지와 같은 helper 로 만든 것."""
    sym, nm = s["sym"], name or s.get("name")
    base = {"date": date, "as_of": s.get("day") or date, "source": source, "target": sym, "sym": sym, "name": nm}
    rows = [dict(base, id=f"{sym}/{k}", card=it[4], label=it[0], state=it[1], direction=it[2], **SG.tags(k))
            for k, it in got.items() if it and k not in ("analysts", "picks")]   # 애널리스트 · 방송 의견은 아래에서 더 자세히 (P218 에서 전망 줄로도 들어옴)
    cells = {c.get("key"): c.get("value") for c in s.get("analysts") or [] if c.get("key")}
    if cells:
        rows.append(dict(base, id=f"{sym}/analysts", card="애널리스트 의견은?", family=SG.OUTSIDE, scheme=SG.SCHEME, close=s.get("close"), value=cells))
    for p in picks:
        h = hashlib.sha1(f"{p.get('url', '').split('&t=')[0].split('?t=')[0]}|{p.get('speaker')}|{p.get('ticker')}".encode()).hexdigest()[:12]
        rows.append({"date": _kst_day(p.get("published_at")), "as_of": s.get("day") or date, "source": source, "target": sym, "sym": sym, "name": nm,
                     "id": f"{sym}/pick/{h}", "card": "방송 의견은?", "family": SG.OUTSIDE, "scheme": SG.SCHEME,
                     "state": p.get("action"), "direction": PICK_DIR.get(p.get("action"), SG.FLAT),
                     "speaker": p.get("speaker"), "own": p.get("own"), "channel": p.get("channel"), "target_price": p.get("target"),
                     "currency": p.get("currency"), "reason": p.get("reason"), "published_at": p.get("published_at"), "url": p.get("url"),
                     "close": s.get("close")})
    return rows


NEWS_KEYS = ("title", "url", "source", "published_at", "area", "issue", "subtopic", "scope", "countries", "scheduled", "surprise", "opinion", "scores", "fact", "ai_model")


def news_rows(news):
    """미국 종목 뉴스 분류(news_store 결과, {item_id: 기사}) → issues 줄. 분류가 없는(AI 가 막힌) 기사는 뺀다 — 화면도 `판단 유보`."""
    rows = []
    for k, it in (news or {}).items():
        if not it.get("scores"):
            continue
        r = {x: it.get(x) for x in NEWS_KEYS if it.get(x) is not None and x != "source"}
        r.update({"date": _kst_day(it.get("published_at")), "source": "radar", "id": f"news/{k}", "target": "stock", "source_name": it.get("source")})   # source = 우리 파이프라인, source_name = 매체
        rows.append(r)
    return rows


def save(state_dir, verdicts, issues=()):
    record_store.append(state_dir, "verdicts", verdicts)
    if issues:
        record_store.append(state_dir, "issues", list(issues))
