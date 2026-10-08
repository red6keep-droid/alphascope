"""Federal Register · CourtListener → items (kind = fedreg · court). 기획서 2절 규제·법원 묶음.

- Federal Register: 용어 3개(`Nvidia` · `advanced computing` · `semiconductor export`)로 어제 이후 문서. 브라우저 UA 필수(Cloudflare).
  SEC의 거래소 자율규제 공지(ETF 구성종목으로 NVDA 언급)는 1차에서 제외한다.
- CourtListener: `party:"NVIDIA"` 도켓 검색, filed_after = 지난 확인일. 응답이 100초 넘게 걸리므로 실패해도 리포트는 나간다.
  추적 도켓의 신규 문서(진행 중 사안 갱신)는 ③단계.
"""

import datetime
import os
import sys
import time

import requests

import config
import db

FEDREG_URL = "https://www.federalregister.gov/api/v1/documents.json"
CL_SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"


def fedreg_prefilter(title, agencies):
    """연방관보 1차 필터 사유. None이면 분류 대상."""
    agencies = [a for a in (agencies or []) if a]
    if agencies and all(a in config.FEDREG_SKIP_AGENCIES for a in agencies):
        return "sec_sro_notice"
    if any(any(allow.lower() in a.lower() for allow in config.FEDREG_ALLOW_AGENCIES) for a in agencies):
        return None
    t = f" {(title or '').lower()} "
    if any(k in t for k in config.FEDREG_TITLE_KEYWORDS):
        return None
    return "fedreg_offtopic"


def collect_fedreg(conn):
    since = db.get_meta(conn, "fedreg_last_date") or (
        datetime.date.today() - datetime.timedelta(days=config.FEDREG_BACKFILL_DAYS)).isoformat()
    headers = {"User-Agent": config.BROWSER_USER_AGENT, "Accept": "application/json"}
    existing = {r["item_id"] for r in conn.execute("SELECT item_id FROM items WHERE kind = 'fedreg'")}
    new, skipped, latest = 0, 0, since
    for term in config.FEDREG_TERMS:
        params = {"conditions[term]": term, "conditions[publication_date][gte]": since, "order": "newest", "per_page": 50,
                  "fields[]": ["document_number", "title", "type", "abstract", "publication_date", "html_url", "agencies", "action"]}
        try:
            r = requests.get(FEDREG_URL, params=params, headers=headers, timeout=config.HTTP_TIMEOUT)
            r.raise_for_status()
            docs = r.json().get("results", [])
        except Exception as e:  # noqa: BLE001
            print(f"[fedreg] '{term}' 실패: {str(e)[:120]}")
            continue
        for d in docs:
            latest = max(latest, d.get("publication_date") or since)
            item_id = f"fedreg:{d['document_number']}"
            if item_id in existing:
                continue
            agencies = [a.get("name") or a.get("raw_name") or "" for a in (d.get("agencies") or [])]
            reason = fedreg_prefilter(d.get("title"), agencies)
            if reason:
                skipped += 1
            conn.execute(
                """INSERT OR IGNORE INTO items(item_id, kind, published_at, title, summary, url, source, raw_json, collected_at, prefilter_reason)
                   VALUES (?, 'fedreg', ?, ?, ?, ?, 'federalregister', ?, ?, ?)""",
                (item_id, f"{d['publication_date']}T00:00:00Z", (d.get("title") or "")[:300],
                 ((d.get("abstract") or d.get("action") or "")[:500]) or None, d.get("html_url"),
                 db.dumps({"type": d.get("type"), "agencies": agencies, "term": term}), db.now_iso(), reason))
            existing.add(item_id)
            new += 1
        time.sleep(0.5)
    # 필터 규칙이 바뀌었을 때 분류 전 행에 재적용 (멱등)
    for r in conn.execute("SELECT item_id, title, raw_json FROM items WHERE kind = 'fedreg' AND analyzed_at IS NULL").fetchall():
        reason = fedreg_prefilter(r["title"], (db.loads(r["raw_json"], {}) or {}).get("agencies"))
        conn.execute("UPDATE items SET prefilter_reason = ? WHERE item_id = ?", (reason, r["item_id"]))
    db.set_meta(conn, "fedreg_last_date", latest)
    conn.commit()
    print(f"[fedreg] 신규 {new}건 (1차 제외 {skipped}) · 기준 {since} 이후")
    return new


def collect_courts(conn):
    token = os.environ.get("COURTLISTENER_TOKEN", "").strip()
    if not token:
        print("[court] COURTLISTENER_TOKEN 없음 — 건너뜀")
        return 0
    since = db.get_meta(conn, "court_last_filed") or (
        datetime.date.today() - datetime.timedelta(days=config.COURTLISTENER_BACKFILL_DAYS)).isoformat()
    headers = {"Authorization": f"Token {token}", "User-Agent": config.USER_AGENT}
    params = {"type": "d", "q": config.COURTLISTENER_QUERY, "order_by": "dateFiled desc", "filed_after": since}
    t0 = time.time()
    try:
        r = requests.get(CL_SEARCH_URL, params=params, headers=headers, timeout=config.COURTLISTENER_TIMEOUT)
        if r.status_code == 429:
            print(f"[court] 429 — retry-after {r.headers.get('retry-after')}s. 이번 실행은 건너뜀")
            return 0
        r.raise_for_status()
        results = r.json().get("results", [])
    except Exception as e:  # noqa: BLE001
        print(f"[court] 검색 실패 ({time.time() - t0:.0f}s): {str(e)[:120]}")
        return 0
    existing = {r_["item_id"] for r_ in conn.execute("SELECT item_id FROM items WHERE kind = 'court'")}
    new, latest = 0, since
    for d in results:
        filed = d.get("dateFiled") or since
        latest = max(latest, filed)
        item_id = f"court:{d['docket_id']}"
        if item_id in existing:
            continue
        name = d.get("caseName") or d.get("case_name_full") or ""
        nature = d.get("suitNature") or ""
        cause = d.get("cause") or ""
        title = f"{name} ({d.get('court_id', '').upper()} {d.get('docketNumber', '')})"
        summary = " · ".join(x for x in (f"접수 {filed}", nature and f"유형 {nature}", cause and f"사유 {cause}") if x)
        url = "https://www.courtlistener.com" + (d.get("docket_absolute_url") or "")
        conn.execute(
            """INSERT OR IGNORE INTO items(item_id, kind, published_at, title, summary, url, source, raw_json, collected_at)
               VALUES (?, 'court', ?, ?, ?, ?, 'courtlistener', ?, ?)""",
            (item_id, f"{filed}T00:00:00Z", title[:300], summary[:500] or None, url,
             db.dumps({"docket_id": d.get("docket_id"), "court_id": d.get("court_id"), "docket_number": d.get("docketNumber"),
                       "suit_nature": nature, "cause": cause, "parties": (d.get("party") or [])[:10], "date_terminated": d.get("dateTerminated")}),
             db.now_iso()))
        existing.add(item_id)
        new += 1
    db.set_meta(conn, "court_last_filed", latest)
    conn.commit()
    print(f"[court] 도켓 {len(results)}건 중 신규 {new} ({time.time() - t0:.0f}s) · 기준 {since} 이후")
    return new


def collect(conn, skip_courts=False):
    n = collect_fedreg(conn)
    if not skip_courts:
        n += collect_courts(conn)
    return n


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    collect(db.connect())
