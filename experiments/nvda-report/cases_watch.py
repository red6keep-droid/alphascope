"""③단계 — 추적 사건(cases.watch=1)의 도켓에서 **주가에 닿을 일정과 판결만** 뽑는다 (2026-10-10 사용자 결정: 단순하게).

하는 것
  1. 최신 도켓 문서 20건을 읽어 일정 명령문의 `... set for M/D/YYYY` 중 **결정으로 이어지는 것**(심리·재판·약식판결·기각 신청·집단소송 인증)만
     `calendar(kind='COURT')`에 넣는다. 조사 종료·보고서 기한·사건관리회의는 버린다. 수정 일정 명령이 오면 그 사건의 미래 COURT 행을 갈아 끼운다.
  2. 판결·합의·기각 **명령이 실제로 올라온 날**만 `items(kind='court')` 이벤트 한 줄 (relevance 3, Gemini 없음). cases.status를 바꾼다.
하지 않는 것: 특허(watch=0) 도켓 조회, 절차 문서 기록, Gemini 분류.

    python experiments/nvda-report/cases_watch.py            # 적용
    python experiments/nvda-report/cases_watch.py --dry-run  # 뽑힌 일정·판결만 출력
"""

import argparse
import datetime
import os
import re
import sys
import time

import requests

import config
import db

ENTRIES_URL = "https://www.courtlistener.com/api/rest/v4/docket-entries/"

# "<구절> set for M/D/YYYY" — 구절이 결정 성격이면 일정으로 채택
SET_FOR_RE = re.compile(r"([^.;]{0,120}?)\b(?:set|reset|continued) for\s+(\d{1,2})/(\d{1,2})/(\d{4})", re.I)
MILESTONES = [  # (구절 패턴, 한국어 라벨) — 위에서부터 첫 일치
    (re.compile(r"trial", re.I), "재판"),
    (re.compile(r"summary judgment", re.I), "약식판결 심리"),
    (re.compile(r"motion to dismiss", re.I), "기각 신청 심리"),
    (re.compile(r"class certification", re.I), "집단소송 인증 심리"),
    (re.compile(r"oral argument", re.I), "구두 변론"),
    (re.compile(r"(motion|motions) hearing|hearing on", re.I), "본안 신청 심리"),
]
SKIP_PHRASE_RE = re.compile(r"case management|status conference|scheduling conference|settlement conference|discovery", re.I)

# 판결·합의·기각 — 문서 설명 머리가 명령·판결류이고 본문에 결정 어구가 있을 때
RULING_HEAD_RE = re.compile(r"^\s*(ORDER|JUDGMENT|FINAL JUDGMENT|STIPULATION (OF|AND ORDER OF) DISMISSAL|NOTICE OF SETTLEMENT)", re.I)
RULINGS = [  # (패턴, 한국어, NVDA(피고) 기준 방향, cases.status 전이 또는 None)
    (re.compile(r"granting[^.]{0,80}motion to dismiss", re.I), "기각 신청 인용", "positive", None),
    (re.compile(r"denying[^.]{0,80}motion to dismiss", re.I), "기각 신청 기각", "negative", None),
    (re.compile(r"granting[^.]{0,80}summary judgment", re.I), "약식판결 인용", "uncertain", None),
    (re.compile(r"denying[^.]{0,80}summary judgment", re.I), "약식판결 기각", "uncertain", None),
    (re.compile(r"granting[^.]{0,80}class certification", re.I), "집단소송 인증", "negative", None),
    (re.compile(r"denying[^.]{0,80}class certification", re.I), "집단소송 인증 거부", "positive", None),
    (re.compile(r"(preliminary|final) approval[^.]{0,60}settlement|notice of settlement", re.I), "합의", "uncertain", "settled"),
    (re.compile(r"dismiss(al|ed)? with prejudice|order of dismissal|stipulation of dismissal", re.I), "소 취하·종결", "positive", "dismissed"),
    (re.compile(r"^\s*(final )?judgment", re.I), "판결", "uncertain", "closed"),
]
EXCLUDE_RE = re.compile(r"seal|administrative motion|pro hac vice|withdraw|extension of time|leave to file", re.I)


def short_name(case):
    t = case["title"]
    if re.match(r"in re", t, re.I):
        return "증권 집단소송 (In re NVIDIA)"
    m = re.split(r"\s+v\.?\s+", t, maxsplit=1, flags=re.I)
    return (m[0].strip()[:30] + " v. NVIDIA") if len(m) == 2 else t[:40]


def _headers():
    token = os.environ.get("COURTLISTENER_TOKEN", "").strip()
    return {"Authorization": f"Token {token}", "User-Agent": config.USER_AGENT} if token else None


def fetch_entries(docket_id, headers):
    r = requests.get(ENTRIES_URL, params={"docket": docket_id, "order_by": "-date_filed"}, headers=headers,
                     timeout=config.COURTLISTENER_TIMEOUT)
    if r.status_code == 429:
        print(f"  [court] 429 — docket {docket_id} 건너뜀")
        return []
    r.raise_for_status()
    return r.json().get("results", [])


def entry_text(e):
    d = (e.get("description") or "").strip()
    if not d and e.get("recap_documents"):
        d = (e["recap_documents"][0].get("description") or "").strip()
    return " ".join(d.split())


def milestones_from(entries, today):
    """최신 문서부터 훑어 라벨별로 첫(=가장 최근 명령의) 미래 날짜만 남긴다."""
    found = {}
    for e in entries:  # 최신 → 과거
        text = entry_text(e)
        for m in SET_FOR_RE.finditer(text):
            phrase = m.group(1)
            if SKIP_PHRASE_RE.search(phrase):
                continue
            label = next((ko for pat, ko in MILESTONES if pat.search(phrase)), None)
            if not label:
                continue
            try:
                day = datetime.date(int(m.group(4)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
            if day <= today or label in found:
                continue
            found[label] = (day.isoformat(), e.get("entry_number"), e.get("date_filed"))
    return found


def rulings_from(entries, since_day):
    out = []
    for e in entries:
        if (e.get("date_filed") or "") < since_day:
            continue
        text = entry_text(e)
        if not text or not RULING_HEAD_RE.search(text) or EXCLUDE_RE.search(text):
            continue
        for pat, ko, direction, status in RULINGS:
            if pat.search(text):
                out.append((e, ko, direction, status, text))
                break
    return out


def run(conn, day, dry_run=False):
    headers = _headers()
    if not headers:
        print("[court] COURTLISTENER_TOKEN 없음 — 추적 사건 건너뜀")
        return 0
    today = datetime.date.fromisoformat(day)
    cases = [dict(r) for r in conn.execute("SELECT * FROM cases WHERE watch = 1 AND kind = 'court'")]
    n_cal, n_rul, t0 = 0, 0, time.time()
    for c in cases:
        docket_id = c["case_id"].split(":")[-1]
        name = short_name(c)
        try:
            entries = fetch_entries(docket_id, headers)
        except Exception as e:  # noqa: BLE001
            print(f"  [court] {name} 조회 실패: {str(e)[:100]}")
            continue
        seen_key = f"court_seen_entry:{c['case_id']}"
        last_seen = db.get_meta(conn, seen_key)
        # 1) 일정 — 미래 COURT 행을 이 사건 기준으로 갈아 끼운다
        ms = milestones_from(entries, today)
        prefix = f"{name} — "
        for label, (d, num, filed) in sorted(ms.items(), key=lambda kv: kv[1][0]):
            print(f"  [court] {name}: {label} {d} (문서 #{num}, {filed})")
        if not dry_run:
            conn.execute("DELETE FROM calendar WHERE kind = 'COURT' AND label LIKE ? AND day > ?", (prefix + "%", day))
            for label, (d, num, filed) in ms.items():
                conn.execute("INSERT OR IGNORE INTO calendar(day, kind, label, symbol, source, confirmed) VALUES (?,?,?,?,?,1)",
                             (d, "COURT", prefix + label, None, f"courtlistener #{num}"))
            n_cal += len(ms)
        # 2) 판결·합의·기각 — 지난 확인 뒤(첫 실행은 N일) 올라온 것만 이벤트
        since = last_seen or (today - datetime.timedelta(days=config.COURT_RULING_BACKFILL_DAYS)).isoformat()
        for e, ko, direction, status, text in rulings_from(entries, since):
            filed = e.get("date_filed") or day
            item_id = f"court:{c['case_id']}:{e.get('id')}"
            print(f"  [court] {name}: {ko} ({filed}) — {text[:100]}")
            if dry_run:
                continue
            conn.execute(
                """INSERT OR IGNORE INTO items(item_id, kind, published_at, title, summary, url, source, raw_json, collected_at,
                       ai_area, ai_direction, ai_novelty, ai_relevance, ai_fact, ai_model, analyzed_at, is_event)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                (item_id, "court", f"{filed}T00:00:00Z", f"{name} — {ko}", text[:500], c["url"], "courtlistener",
                 db.dumps({"case_id": c["case_id"], "entry": e.get("entry_number"), "ruling": ko}), db.now_iso(),
                 "Legal", direction, "update", 3, f"{name}: {ko} ({filed}, 문서 #{e.get('entry_number')})", "rule", db.now_iso()))
            conn.execute("UPDATE cases SET last_activity_at = ?, last_activity_summary = ?, status = COALESCE(?, status) WHERE case_id = ?",
                         (filed, ko, status, c["case_id"]))
            n_rul += 1
        if not dry_run and entries:
            db.set_meta(conn, seen_key, max((e.get("date_filed") or "") for e in entries))
    if not dry_run:
        conn.commit()
    print(f"[court] 추적 {len(cases)}건 · 일정 {n_cal} · 판결 {n_rul} ({time.time() - t0:.0f}s)")
    return n_rul


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--day", default=datetime.date.today().isoformat())
    a = ap.parse_args()
    run(db.connect(), a.day, dry_run=a.dry_run)
