"""③단계 — 소송 추적 초기화를 위한 수동 검토 표 (기획서 13절 ③ · 3절 `cases`).

CourtListener에서 NVIDIA가 당사자인 도켓을 기획서 범위로만 받아 `output/cases_survey.md`에 낸다.
DB의 `cases` 테이블에는 쓰지 않는다 — 사람이 `watch` 열을 확정한 뒤 `cases_init.py`(③ 후반)가 읽는다.

범위 (기획서 13절): 증권(850)·반독점(410)은 전부, 특허(830)는 최근 1년 접수분.
분류는 CourtListener의 suitNature 코드로 결정적으로 매긴다 (Gemini 없음) — 코드가 비어 있으면 `other`로 두고 표에 표시한다.

    python experiments/nvda-report/cases_survey.py             # 표 + JSON
    python experiments/nvda-report/cases_survey.py --patent-days 730
"""

import argparse
import datetime
import json
import os
import re
import sys
import time

import requests

import config

SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"

# suitNature 코드(PACER nature of suit) → cases.category
NATURE_TO_CATEGORY = {
    "850": "securities", "3850": "securities",
    "410": "antitrust", "3410": "antitrust",
    "830": "patent", "3830": "patent", "835": "patent",
    "820": "copyright", "840": "trademark",
    "442": "employment", "710": "employment", "720": "employment", "790": "employment", "751": "employment",
    "190": "contract", "195": "contract", "196": "contract", "3190": "contract",
}


def _headers():
    token = os.environ.get("COURTLISTENER_TOKEN", "").strip()
    if not token:
        raise SystemExit("COURTLISTENER_TOKEN 없음 (.env)")
    return {"Authorization": f"Token {token}", "User-Agent": config.USER_AGENT}


def search_all(q, filed_after=None, max_pages=30):
    """v4 검색을 next 커서로 끝까지 받는다. (토큰 있으면 페이지당 1~2초)"""
    params = {"type": "d", "q": q, "order_by": "dateFiled desc"}
    if filed_after:
        params["filed_after"] = filed_after
    out, url, pages = [], SEARCH_URL, 0
    while url and pages < max_pages:
        r = requests.get(url, params=params if url == SEARCH_URL else None, headers=_headers(), timeout=config.COURTLISTENER_TIMEOUT)
        if r.status_code == 429:
            wait = int(r.headers.get("retry-after") or 5)
            print(f"  429 — {wait}s 대기"); time.sleep(wait); continue
        r.raise_for_status()
        j = r.json()
        out.extend(j.get("results", []))
        url, pages = j.get("next"), pages + 1
        if pages == 1:
            print(f"  count={j.get('count')}")
    return out


def category_of(d):
    code = (d.get("suitNature") or "").strip().split(" ")[0]
    return NATURE_TO_CATEGORY.get(code, "other" if code else "unknown")


def role_of(d):
    """사건명 'A v. B'에서 NVIDIA 위치로 역할 추정. 당사자 목록(party)으로 보강."""
    name = (d.get("caseName") or d.get("case_name_full") or "")
    parts = re.split(r"\s+v\.?\s+", name, maxsplit=1, flags=re.I)
    nv = re.compile(r"nvidia|mellanox", re.I)
    if len(parts) == 2:
        left, right = parts
        if nv.search(left) and not nv.search(right):
            return "plaintiff"
        if nv.search(right) and not nv.search(left):
            return "defendant"
        if nv.search(left) and nv.search(right):
            return "both"
    return "other"


def normalize(d, bucket):
    return {
        "case_id": f"cl:{d['docket_id']}",
        "docket_id": d.get("docket_id"),
        "bucket": bucket,
        "category": category_of(d),
        "suit_nature": d.get("suitNature") or "",
        "cause": d.get("cause") or "",
        "title": d.get("caseName") or d.get("case_name_full") or "",
        "court": (d.get("court_id") or "").upper(),
        "court_name": d.get("court") or "",
        "docket_number": d.get("docketNumber") or "",
        "filed": d.get("dateFiled") or "",
        "terminated": d.get("dateTerminated") or "",
        "role": role_of(d),
        "parties": [p.get("name") if isinstance(p, dict) else str(p) for p in (d.get("party") or [])][:6],
        "url": "https://www.courtlistener.com" + (d.get("docket_absolute_url") or ""),
    }


def propose_watch(c):
    """기본 제안: 종결되지 않은 증권·반독점 전부, 특허는 범위(최근 1년) 안이면. 항소심(ca*)은 1심이 있으면 중복이라 제외."""
    if c["terminated"]:
        return 0, "종결"
    if c["court"].startswith("CA") and c["court"] != "CAND":
        return 0, "항소심"
    if c["category"] in ("securities", "antitrust"):
        return 1, ""
    if c["category"] == "patent":
        return 1, ""
    return 0, "범위 밖"


def render(cases, total_count, patent_since, path):
    buckets = {}
    for c in cases:
        buckets.setdefault(c["bucket"], []).append(c)
    lines = [
        "# 엔비디아 리포트 — 소송 추적 초기화 검토 표 (③단계)", "",
        f"생성 {datetime.date.today()} · CourtListener `party:\"NVIDIA\"` 전체 **{total_count}건** 중 기획서 범위만: "
        f"증권·반독점 전부 + 특허 {patent_since} 이후 접수. 분류는 suitNature 코드(Gemini 없음).", "",
        "`제안` = 코드가 제안한 watch (종결·항소심·범위 밖은 0). **`확정` 열에 1/0을 적으면 `cases_init.py`가 읽는다.** 비우면 제안대로.", "",
        f"| 묶음 | 건수 | 제안 watch |", "| --- | ---: | ---: |",
    ]
    for b, cs in buckets.items():
        lines.append(f"| {b} | {len(cs)} | {sum(c['watch'] for c in cs)} |")
    lines.append("")
    for b, cs in buckets.items():
        lines += [f"## {b} ({len(cs)}건)", "",
                  "| # | 접수 | 법원 | 사건번호 | 사건명 | 유형 | 사유 | NVIDIA 역할 | 종결 | 제안 | 비고 | 확정 |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |"]
        for i, c in enumerate(sorted(cs, key=lambda x: x["filed"], reverse=True), 1):
            title = c["title"].replace("|", "¦")[:80]
            lines.append(f"| {i} | {c['filed']} | {c['court']} | [{c['docket_number']}]({c['url']}) | {title} | {c['suit_nature']} | "
                         f"{c['cause'].replace('|', '¦')[:40]} | {c['role']} | {c['terminated'] or ''} | {c['watch']} | {c['note']} |  |")
        lines.append("")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patent-days", type=int, default=365)
    args = ap.parse_args()
    patent_since = (datetime.date.today() - datetime.timedelta(days=args.patent_days)).isoformat()

    print("[survey] 전체 건수")
    r = requests.get(SEARCH_URL, params={"type": "d", "q": 'party:"NVIDIA"'}, headers=_headers(), timeout=config.COURTLISTENER_TIMEOUT)
    total_count = r.json().get("count")

    queries = [
        ("증권", 'party:"NVIDIA" AND suitNature:securities', None),
        ("반독점", 'party:"NVIDIA" AND suitNature:antitrust', None),
        ("특허(최근 1년)", 'party:"NVIDIA" AND suitNature:patent', patent_since),
    ]
    seen, cases = set(), []
    for bucket, q, since in queries:
        print(f"[survey] {bucket}: {q}" + (f" filed_after={since}" if since else ""))
        for d in search_all(q, since):
            if d["docket_id"] in seen:
                continue
            seen.add(d["docket_id"])
            c = normalize(d, bucket)
            c["watch"], c["note"] = propose_watch(c)
            cases.append(c)
        print(f"  누적 {len(cases)}건")

    out_dir = config.OUTPUT_DIR
    json.dump(cases, open(os.path.join(out_dir, "cases_survey.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    path = render(cases, total_count, patent_since, os.path.join(out_dir, "cases_survey.md"))
    print(f"[survey] {len(cases)}건 · 제안 watch {sum(c['watch'] for c in cases)} → {path}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    main()
