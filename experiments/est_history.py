"""애널리스트 추정치 · 등급 · 목표가(· 공매도) 날짜별 기록 — 야후는 오늘 값만 주므로 매일 쌓아야 나중에 검증할 수 있다 (기획 K16, 2026-10-31 사용자 batch 4).

한국(kr-stocks/collect_kr_extra) · 미국(stock-radar/collect_extra) 이 받은 날 한 번 부른다. 파일은 각자의 data/est_history.json,
워크플로가 상태 브랜치(kr-state · nvda-state radar/)에 보존한다 — 덮어쓰지 않고 날짜 칸만 더한다(같은 날 다시 돌면 그날 칸만 바뀐다).
    {"YYYY-MM-DD": {"<티커>": {"eps": {...}, "analysts": {...}, "short": {...}}}}
"""
import json
import os

KEYS = ("eps", "analysts", "short")


def append(path, day, stocks):
    try:
        with open(path, encoding="utf-8") as f:
            h = json.load(f)
    except (OSError, ValueError):
        h = {}
    row = {sym: {k: v[k] for k in KEYS if v.get(k)} for sym, v in (stocks or {}).items()}
    row = {sym: v for sym, v in row.items() if v}
    if not row:
        return h
    h[day] = row
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False)
    print(f"[est] {day} · {len(row)}종목 기록 → {os.path.basename(path)} ({len(h)}일째)")
    return h
