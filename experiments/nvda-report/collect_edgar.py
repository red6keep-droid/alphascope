"""SEC EDGAR → items (kind = form4 · 8k · 10q · 10k). 기획서 2절 EDGAR 묶음.

submissions JSON(최근 1,000건)에서 지난 실행 이후 접수된 공시만 고른다.
- Form 4: XML을 파싱해 거래자·직책·거래(코드·수량·가격·취득/처분)·10b5-1 플래그를 raw_json에 넣는다. Gemini 불필요.
- 8-K: Item 번호 목록과 본문 URL. Item 8.01의 Gemini 요약은 ②단계.
- 10-Q · 10-K: URL만. 본문 저장과 수치 추출은 ④단계.

User-Agent 필수, 10 req/s 제한 — 호출 사이에 0.15초 쉰다.
"""

import datetime
import re
import sys
import time
import xml.etree.ElementTree as ET

import requests

import config
import db

SUBMISSIONS_URL = f"https://data.sec.gov/submissions/CIK{config.EDGAR_CIK}.json"
ARCHIVE_BASE = f"https://www.sec.gov/Archives/edgar/data/{int(config.EDGAR_CIK)}"
HEADERS = {"User-Agent": config.EDGAR_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
KIND_BY_FORM = {"4": "form4", "8-K": "8k", "10-Q": "10q", "10-K": "10k"}
TX_CODE_KO = {"S": "매도", "P": "매수", "M": "옵션 행사", "F": "세금 납부용 처분", "A": "부여", "G": "증여",
              "C": "전환", "D": "처분(기타)", "J": "기타"}
ITEM_KO = {
    "1.01": "중요 계약 체결", "1.02": "중요 계약 종료", "2.01": "자산 인수·처분 완료", "2.02": "실적 발표",
    "2.03": "직접 재무 의무 발생", "2.05": "구조조정 비용", "3.02": "미등록 증권 매각", "5.02": "임원·이사 변경",
    "5.03": "정관 변경", "5.07": "주주총회 결과", "7.01": "Reg FD 공시", "8.01": "기타 사건", "9.01": "재무제표·첨부",
}


def _get(url, **kw):
    time.sleep(config.EDGAR_REQUEST_GAP_SECONDS)
    r = requests.get(url, headers=HEADERS, timeout=config.HTTP_TIMEOUT, **kw)
    r.raise_for_status()
    return r


def fetch_submissions():
    j = _get(SUBMISSIONS_URL).json()
    rec = j["filings"]["recent"]
    n = len(rec["form"])
    desc = rec.get("primaryDocDescription") or [""] * n
    items = rec.get("items") or [""] * n
    out = []
    for i in range(n):
        out.append({
            "form": rec["form"][i], "filing_date": rec["filingDate"][i], "report_date": rec["reportDate"][i],
            "accepted_at": rec["acceptanceDateTime"][i], "accession": rec["accessionNumber"][i],
            "primary_doc": rec["primaryDocument"][i], "items": items[i], "description": desc[i],
        })
    return out


def _text(el, path):
    if el is None:
        return ""
    x = el.find(path)
    return (x.text or "").strip() if x is not None and x.text else ""


def parse_form4(xml_text):
    root = ET.fromstring(xml_text)
    owner = root.find("reportingOwner")
    rel = owner.find("reportingOwnerRelationship") if owner is not None else None
    info = {
        "owner": _text(owner, "reportingOwnerId/rptOwnerName"),
        "owner_cik": _text(owner, "reportingOwnerId/rptOwnerCik"),
        "is_director": _text(rel, "isDirector") == "1",
        "is_officer": _text(rel, "isOfficer") == "1",
        "is_ten_percent": _text(rel, "isTenPercentOwner") == "1",
        "title": _text(rel, "officerTitle"),
        "period": _text(root, "periodOfReport"),
        "aff10b5one": _text(root, "aff10b5One") == "1",
        "transactions": [],
        "derivative_count": len(root.findall("derivativeTable/derivativeTransaction")),
    }
    footnotes = " ".join((f.text or "") for f in root.findall("footnotes/footnote"))
    info["mentions_10b5_1"] = bool(re.search(r"10b5-?1", footnotes, re.I))
    for tx in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        shares = _text(tx, "transactionAmounts/transactionShares/value")
        price = _text(tx, "transactionAmounts/transactionPricePerShare/value")
        post = _text(tx, "postTransactionAmounts/sharesOwnedFollowingTransaction/value")
        info["transactions"].append({
            "date": _text(tx, "transactionDate/value"),
            "code": _text(tx, "transactionCoding/transactionCode"),
            "shares": float(shares) if shares else None,
            "price": float(price) if price else None,
            "ad": _text(tx, "transactionAmounts/transactionAcquiredDisposedCode/value"),
            "post_shares": float(post) if post else None,
            "security": _text(tx, "securityTitle/value"),
        })
    txs = info["transactions"]
    info["sold_usd"] = sum((t["shares"] or 0) * (t["price"] or 0) for t in txs if t["code"] == "S")
    info["bought_usd"] = sum((t["shares"] or 0) * (t["price"] or 0) for t in txs if t["code"] == "P")
    info["shares_sold"] = sum((t["shares"] or 0) for t in txs if t["code"] == "S")
    info["shares_bought"] = sum((t["shares"] or 0) for t in txs if t["code"] == "P")
    info["is_plan"] = bool(info["aff10b5one"] or info["mentions_10b5_1"])
    return info


def _form4_xml_url(accession):
    acc = accession.replace("-", "")
    idx = _get(f"{ARCHIVE_BASE}/{acc}/index.json").json()
    names = [it["name"] for it in idx["directory"]["item"]]
    xmls = [n for n in names if n.lower().endswith(".xml") and not n.lower().startswith("xsl")]
    return f"{ARCHIVE_BASE}/{acc}/{xmls[0]}" if xmls else None


def _role(info):
    if info["is_ten_percent"]:
        return "10% 보유자"
    if info["is_officer"] and info["title"]:
        return info["title"]
    if info["is_director"]:
        return "이사"
    return "내부자"


def _form4_title(info):
    """공개시장 매도·매수가 있을 때만 10b5-1 꼬리표를 단다. 세금 납부·부여·증여·옵션 행사는 거래 종류만 적는다."""
    if info["shares_sold"] and not info["shares_bought"]:
        what = f"매도 {info['shares_sold']:,.0f}주 · 약 ${info['sold_usd'] / 1e6:,.1f}M"
    elif info["shares_bought"] and not info["shares_sold"]:
        what = f"매수 {info['shares_bought']:,.0f}주 · 약 ${info['bought_usd'] / 1e6:,.1f}M"
    elif info["shares_sold"] or info["shares_bought"]:
        what = f"매도 {info['shares_sold']:,.0f}주 · 매수 {info['shares_bought']:,.0f}주"
    else:
        codes = sorted({TX_CODE_KO.get(t["code"], t["code"]) for t in info["transactions"] if t["code"]})
        what = " · ".join(codes) if codes else "파생 거래만"
        return f"Form 4 — {info['owner']} ({_role(info)}): {what}"
    plan = "10b5-1 계획" if info["is_plan"] else "계획 외"
    return f"Form 4 — {info['owner']} ({_role(info)}): {what} [{plan}]"


def _direction(info):
    if info["shares_bought"] and info["bought_usd"] >= info["sold_usd"]:
        return "positive"
    if info["shares_sold"]:
        return "neutral" if info["is_plan"] else "negative"
    return "neutral"


def collect(conn, since_days=None):
    today = datetime.date.today()
    since = db.get_meta(conn, "edgar_last_filing_date")
    if not since:
        since = (today - datetime.timedelta(days=since_days or config.EDGAR_BACKFILL_DAYS)).isoformat()
    filings = fetch_submissions()
    existing = {r["item_id"] for r in conn.execute("SELECT item_id FROM items WHERE kind IN ('form4','8k','10q','10k')")}
    new, counts, latest = 0, {}, since
    for f in filings:
        kind = KIND_BY_FORM.get(f["form"])
        if not kind or f["filing_date"] < since:
            continue
        latest = max(latest, f["filing_date"])
        item_id = f"{kind}:{f['accession']}"
        if item_id in existing:
            continue
        acc = f["accession"].replace("-", "")
        url = f"{ARCHIVE_BASE}/{acc}/{f['primary_doc']}"
        raw = dict(f)
        summary, direction, area = None, "neutral", "Corporate"
        if kind == "form4":
            area = "Flows"
            info = None
            try:
                xml_url = _form4_xml_url(f["accession"])
                info = parse_form4(_get(xml_url).text) if xml_url else None
            except Exception as e:  # noqa: BLE001
                print(f"[edgar] Form 4 {f['accession']} 파싱 실패: {e}")
            if info:
                raw["form4"] = info
                title = _form4_title(info)
                direction = _direction(info)
                summary = "; ".join(
                    f"{t['date']} {TX_CODE_KO.get(t['code'], t['code'])} {t['shares']:,.0f}주"
                    + (f" @ ${t['price']:,.2f}" if t["price"] else "")
                    for t in info["transactions"] if t["shares"])
            else:
                title = f"Form 4 — {f['accession']} (파싱 실패, 원문 확인)"
        elif kind == "8k":
            items = [i.strip() for i in (f["items"] or "").split(",") if i.strip()]
            raw["item_list"] = items
            title = ("8-K — " + ", ".join(f"Item {i} {ITEM_KO.get(i, '')}".strip() for i in items)) if items else "8-K"
            area = "Earnings" if "2.02" in items else "Corporate"
            summary = f["description"] or None
        else:
            title = f"{f['form']} — {f['description'] or '분기·연간 보고서'} (보고 기간 {f['report_date']})"
            area = "Earnings"
        conn.execute(
            """INSERT OR IGNORE INTO items(item_id, kind, published_at, title, summary, url, source, raw_json, collected_at,
                   ai_area, ai_direction, ai_novelty, ai_relevance, ai_fact, analyzed_at, is_event)
               VALUES (?, ?, ?, ?, ?, ?, 'edgar', ?, ?, ?, ?, 'new', 3, ?, ?, 1)""",
            (item_id, kind, f["accepted_at"].replace(".000Z", "Z"), title, summary, url, db.dumps(raw), db.now_iso(),
             area, direction, title, db.now_iso()))
        new += 1
        counts[kind] = counts.get(kind, 0) + 1
    db.set_meta(conn, "edgar_last_filing_date", latest)
    conn.commit()
    print(f"[edgar] 신규 {new}건 {counts or ''} (기준 {since} 이후) · 다음 기준일 {latest}")
    return new


def insider_net_sold(conn, day, window_days=config.INSIDER_WINDOW_DAYS):
    """점검표 insider_net_sold_90d — Form 4 raw_json 집계 (매도 − 매수, 달러)."""
    since = (datetime.date.fromisoformat(day) - datetime.timedelta(days=window_days)).isoformat()
    sold = bought = 0.0
    n = plan = 0
    for r in conn.execute("SELECT raw_json FROM items WHERE kind = 'form4' AND published_at >= ?", (since,)):
        info = (db.loads(r["raw_json"], {}) or {}).get("form4")
        if not info:
            continue
        sold += info.get("sold_usd", 0) or 0
        bought += info.get("bought_usd", 0) or 0
        n += 1
        plan += 1 if info.get("is_plan") else 0
    return {"net_sold_usd": sold - bought, "sold_usd": sold, "bought_usd": bought,
            "filings": n, "plan_filings": plan, "since": since}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    collect(db.connect())
