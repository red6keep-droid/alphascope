"""④단계 — 보유 논리 점검표 (기획서 8절), SEC 원문만으로. Gemini 없음 (2026-10-10 사용자: 복잡하게 만들지 않는다).

소스 세 가지
  1. XBRL companyfacts API — 분기 매출(Revenues)·총이익(GrossProfit)·자사주 매입(PaymentsForRepurchaseOfCommonStock, 누적 → 분기 차분)
  2. 8-K 2.02 실적 보도자료(첨부 *pr.htm) — 데이터센터 매출·YoY·QoQ, 다음 분기 매출 가이던스, non-GAAP 총마진
  3. 10-Q/10-K 본문 — 지역별 매출 표(중국·홍콩 비중), 매출 기준 10% 이상 고객 비중
뺀 것 (2026-10-10 확정): 하이퍼스케일러 capex 가이던스, TSMC 월매출.

언제 도나: 첫 실행에 최근 N분기 백필, 그 뒤에는 EDGAR에 새 8-K 2.02 또는 10-Q/10-K가 올라온 날만 (meta `quarterly_seen_accessions`).
저장: `quarterly(fiscal_quarter, metric, value, unit, source, source_url, recorded_at, verified=1)`. 숫자는 원문 문장·표에서 그대로 긁는다.

    python experiments/nvda-report/extract_quarterly.py            # 적용
    python experiments/nvda-report/extract_quarterly.py --force    # 백필 다시
"""

import argparse
import html
import json
import os
import re
import sys

import requests

import collect_edgar
import config
import db

FACTS_URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{config.EDGAR_CIK}.json"
QUARTER_WORD = {"first": 1, "second": 2, "third": 3, "fourth": 4}
BACKFILL_QUARTERS = 5


def _get(url):
    return collect_edgar._get(url)


def _clean_html(raw):
    txt = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"\s+", " ", txt)


def _num(s):
    return float(s.replace(",", "").replace("$", "").strip())


def _put(conn, fq, metric, value, unit, source, url, value_json=None):
    conn.execute(
        """INSERT OR REPLACE INTO quarterly(fiscal_quarter, metric, value, value_json, unit, source, source_url, recorded_at, verified)
           VALUES (?,?,?,?,?,?,?,?,1)""",
        (fq, metric, value, db.dumps(value_json) if value_json is not None else None, unit, source, url, db.now_iso()))


# ---------- 1. XBRL ----------

def fiscal_quarter_of(fy, fp):
    return f"FY{fy}Q{ {'Q1': 1, 'Q2': 2, 'Q3': 3}.get(fp, 4)}"


def xbrl_quarters(facts, tag, cumulative=False):
    """{FYyyyyQn: value}. 분기 프레임(CY..Qn)이 있는 10-Q 값 + 10-K 연간에서 Q4 = 연간 − Q1~Q3 (cumulative이면 누적 차분)."""
    rows = [r for r in facts.get(tag, {}).get("units", {}).get("USD", []) if r.get("form") in ("10-Q", "10-K") and r.get("fy") and r.get("fp")]
    out, annual, ytd = {}, {}, {}
    for r in rows:
        fq = fiscal_quarter_of(r["fy"], r["fp"])
        start, end = r.get("start"), r.get("end")
        if not (start and end):
            continue
        days = (_d(end) - _d(start)).days
        if r["fp"] == "FY" and days > 300:
            annual[r["fy"]] = r["val"]
        elif r["fp"] in ("Q1", "Q2", "Q3"):
            if cumulative:
                if days > 100 or r["fp"] == "Q1":
                    ytd[fq] = r["val"]          # 누적(연초부터)
            elif 70 <= days <= 100:
                out[fq] = r["val"]              # 순수 분기
    if cumulative:
        for fq, v in ytd.items():
            fy, n = int(fq[2:6]), int(fq[-1])
            prev = ytd.get(f"FY{fy}Q{n - 1}") if n > 1 else 0.0
            if prev is not None:
                out[fq] = v - prev
        for fy, v in annual.items():
            q3 = ytd.get(f"FY{fy}Q3")
            if q3 is not None:
                out[f"FY{fy}Q4"] = v - q3
    else:
        for fy, v in annual.items():
            q = [out.get(f"FY{fy}Q{n}") for n in (1, 2, 3)]
            if all(x is not None for x in q):
                out[f"FY{fy}Q4"] = v - sum(q)
    return out


def _d(s):
    import datetime
    return datetime.date.fromisoformat(s)


def load_xbrl(conn, quarters):
    facts = _get(FACTS_URL).json()["facts"]["us-gaap"]
    rev = xbrl_quarters(facts, "Revenues") or xbrl_quarters(facts, "RevenueFromContractWithCustomerExcludingAssessedTax")
    gp = xbrl_quarters(facts, "GrossProfit")
    bb = xbrl_quarters(facts, "PaymentsForRepurchaseOfCommonStock", cumulative=True)
    n = 0
    for fq in quarters:
        if fq in rev:
            _put(conn, fq, "revenue", rev[fq], "USD", "SEC XBRL", FACTS_URL); n += 1
            if fq in gp and rev[fq]:
                _put(conn, fq, "gross_margin_gaap", round(gp[fq] / rev[fq] * 100, 1), "%", "SEC XBRL", FACTS_URL); n += 1
        if fq in bb:
            _put(conn, fq, "buyback_amount", bb[fq], "USD", "SEC XBRL (누적 차분)", FACTS_URL); n += 1
    return rev, n


# ---------- 2. 실적 보도자료 ----------

def _fq_from_text(txt):
    """보도자료 제목에서만 (앞 400자). 'Fourth Quarter and Fiscal 2026' · 'Second Quarter Fiscal 2027'."""
    head = txt[:400]
    m = re.search(r"(First|Second|Third|Fourth)[- ]Quarter (?:and |Results )?(?:for |of )?Fiscal (?:Year )?(\d{4})", head, re.I)
    return f"FY{m.group(2)}Q{QUARTER_WORD[m.group(1).lower()]}" if m else None


def _next_fq(fq):
    fy, n = int(fq[2:6]), int(fq[-1])
    return f"FY{fy}Q{n + 1}" if n < 4 else f"FY{fy + 1}Q1"


def press_release_url(accession):
    acc = accession.replace("-", "")
    j = _get(f"{collect_edgar.ARCHIVE_BASE}/{acc}/index.json").json()
    names = [i["name"] for i in j["directory"]["item"]]
    cands = [n for n in names if n.endswith(".htm") and re.search(r"pr\.htm$|ex99|ex-99|991", n, re.I)]
    return f"{collect_edgar.ARCHIVE_BASE}/{acc}/{cands[0]}" if cands else None


def extract_press_release(conn, url):
    txt = _clean_html(_get(url).text)
    fq = _fq_from_text(txt)
    if not fq:
        print(f"  [pr] 분기 식별 실패: {url}")
        return None
    n = 0
    m = re.search(r"Data Center revenue (?:was|of) \$\s?([\d.,]+) (billion|million)", txt)
    if m:
        v = _num(m.group(1)) * (1e9 if m.group(2) == "billion" else 1e6)
        _put(conn, fq, "dc_revenue", v, "USD", "실적 보도자료", url); n += 1
        y = re.search(r"Data Center revenue.{0,160}?(up|down) ([\d.]+)% from a year ago", txt)
        if y:
            _put(conn, fq, "dc_revenue_yoy", float(y.group(2)) * (1 if y.group(1) == "up" else -1), "%", "실적 보도자료", url); n += 1
        q = re.search(r"Data Center revenue.{0,160}?(up|down) ([\d.]+)% (?:from the previous quarter|from the prior quarter|sequentially)", txt)
        if q:
            _put(conn, fq, "dc_revenue_qoq", float(q.group(2)) * (1 if q.group(1) == "up" else -1), "%", "실적 보도자료", url); n += 1
    m = re.search(r"[Rr]evenue is expected to be \$\s?([\d.,]+) billion(?:, plus or minus ([\d.]+)%)?", txt)
    if m:
        _put(conn, _next_fq(fq), "guidance_revenue_next", _num(m.group(1)) * 1e9, "USD", f"실적 보도자료 ({fq} 발표)", url,
             value_json={"given_in": fq, "pm_pct": float(m.group(2)) if m.group(2) else None}); n += 1
    m = (re.search(r"GAAP and non-GAAP gross margins were both ([\d.]+)%", txt)
         or re.search(r"GAAP and non-GAAP gross margins were ([\d.]+)% and ([\d.]+)%", txt)
         or re.search(r"non-GAAP gross margins? (?:was|were|of) ([\d.]+)%", txt))
    if m:
        _put(conn, fq, "gross_margin_nongaap", float(m.group(m.lastindex)), "%", "실적 보도자료", url); n += 1
    print(f"  [pr] {fq}: {n}칸 ← {url.rsplit('/', 1)[-1]}")
    return fq


# ---------- 3. 10-Q / 10-K ----------

def extract_filing(conn, url, form, report_date):
    txt = _clean_html(_get(url).text)
    fq = _fq_from_report_date(report_date)
    n = 0
    # 지역별 매출 표 — "Geographic Revenue based upon Customer Headquarters Location: ... China (including Hong Kong) 7,880 ..." 첫 숫자 = 당분기(10-K는 연간)
    g = txt.find("Geographic Revenue based upon")
    seg = txt[g:g + 1500] if g >= 0 else ""
    m = re.search(r"China \(including Hong Kong\)\s+\$?\s?([\d,]+)", seg)
    t = re.search(r"Total revenue \$?\s?([\d,]+)", seg[m.end():]) if m else None
    if m and t and _num(t.group(1)):
        _put(conn, fq, "china_revenue_pct", round(_num(m.group(1)) / _num(t.group(1)) * 100, 1), "%", f"{form} 지역별 매출 표" + (" (연간)" if form == "10-K" else ""), url,
             value_json={"china_musd": _num(m.group(1)), "total_musd": _num(t.group(1)), "period": "annual" if form == "10-K" else "quarter"}); n += 1
    # 매출 기준 10% 이상 고객 — "For the second quarter of fiscal year 2027, one direct customer represented 16% of total revenue"
    #   (10-K는 "For fiscal year 2026, ..."). 그 기간의 직접·간접 고객 문장을 하나씩 골라 합산. 반기·누적 문장은 제외
    period_re = r"For fiscal year \d{4}," if form == "10-K" else r"For the (?:first|second|third|fourth) quarter of fiscal year \d{4},"
    found = {}
    for m in re.finditer(period_re + r" (?:one|two|three|four|five|six) (direct|indirect) customers? represented ([^.]*?) of total revenue", txt):
        kind, nums = m.group(1), [float(x) for x in re.findall(r"(\d{1,2})\s?%", m.group(2))]
        if nums and kind not in found:
            found[kind] = nums
    if found:
        allp = [x for v in found.values() for x in v]
        _put(conn, fq, "top_customer_pct", round(sum(allp), 1), "%", f"{form} 집중도 주석 (직접 {len(found.get('direct', []))} · 간접 {len(found.get('indirect', []))})", url,
             value_json=found); n += 1
    print(f"  [{form}] {fq}: {n}칸 ← {url.rsplit('/', 1)[-1]}")
    return fq


def _fq_from_report_date(report_date):
    """NVDA 회계연도: 1월 말 종료. 분기말 월 4→Q1, 7→Q2, 10→Q3, 1→Q4 (FY = 그 해 + 1 또는 1월이면 그 해)."""
    y, mth = int(report_date[:4]), int(report_date[5:7])
    q = {4: 1, 5: 1, 7: 2, 8: 2, 10: 3, 11: 3, 1: 4, 2: 4}.get(mth)
    fy = y if mth <= 2 else y + 1
    return f"FY{fy}Q{q}" if q else None


# ---------- 계산 ----------

def derive(conn):
    """guidance_beat_pct = 실제 매출 / 그 분기 가이던스 − 1. dc_revenue_qoq·yoy = 연속 분기 값에서 계산 (보도자료에 없을 때)."""
    n = 0
    dc = {r["fiscal_quarter"]: r["value"] for r in conn.execute("SELECT fiscal_quarter, value FROM quarterly WHERE metric = 'dc_revenue'")}
    for fq, v in dc.items():
        for metric, ref in (("dc_revenue_qoq", _prev_fq(fq)), ("dc_revenue_yoy", _prev_fq(_prev_fq(_prev_fq(_prev_fq(fq)))))):
            if dc.get(ref) and not conn.execute("SELECT 1 FROM quarterly WHERE metric = ? AND fiscal_quarter = ?", (metric, fq)).fetchone():
                _put(conn, fq, metric, round((v / dc[ref] - 1) * 100, 1), "%", "계산 (연속 분기 데이터센터 매출)", None); n += 1
    for r in conn.execute("SELECT fiscal_quarter, value FROM quarterly WHERE metric = 'guidance_revenue_next'").fetchall():
        act = conn.execute("SELECT value FROM quarterly WHERE metric = 'revenue' AND fiscal_quarter = ?", (r["fiscal_quarter"],)).fetchone()
        if act and act["value"] and r["value"]:
            _put(conn, r["fiscal_quarter"], "guidance_beat_pct", round((act["value"] / r["value"] - 1) * 100, 1), "%", "계산 (실제 ÷ 가이던스)", None); n += 1
    return n


# ---------- 실행 ----------

def run(conn, force=False):
    subs = collect_edgar.fetch_submissions()
    earnings = [s for s in subs if s["form"] == "8-K" and "2.02" in (s["items"] or "")][:BACKFILL_QUARTERS]
    filings = [s for s in subs if s["form"] in ("10-Q", "10-K")][:BACKFILL_QUARTERS]
    seen = set(db.loads(db.get_meta(conn, "quarterly_seen_accessions"), []) or [])
    todo_pr = [s for s in earnings if force or s["accession"] not in seen]
    todo_f = [s for s in filings if force or s["accession"] not in seen]
    if not todo_pr and not todo_f:
        print("[quarterly] 새 실적 공시 없음")
        return 0
    quarters = set()
    for s in todo_pr:
        url = press_release_url(s["accession"])
        if url:
            fq = extract_press_release(conn, url)
            if fq:
                quarters.add(fq)
        seen.add(s["accession"])
    for s in todo_f:
        url = f"{collect_edgar.ARCHIVE_BASE}/{s['accession'].replace('-', '')}/{s['primary_doc']}"
        fq = extract_filing(conn, url, s["form"], s["report_date"])
        if fq:
            quarters.add(fq)
        seen.add(s["accession"])
    # XBRL은 전 분기 한 번에 (분기 목록 = 보도자료·10-Q에서 본 분기 + 그 이전 4개)
    all_q = set(quarters)
    for fq in list(quarters):
        for _ in range(4):
            fq = _prev_fq(fq); all_q.add(fq)
    rev, n_x = load_xbrl(conn, sorted(all_q))
    n_d = derive(conn)
    db.set_meta(conn, "quarterly_seen_accessions", db.dumps(sorted(seen)))
    conn.commit()
    rows = conn.execute("SELECT COUNT(*) FROM quarterly").fetchone()[0]
    print(f"[quarterly] 보도자료 {len(todo_pr)} · 10-Q/K {len(todo_f)} · XBRL {n_x}칸 · 계산 {n_d}칸 → quarterly {rows}행")
    return rows


def _prev_fq(fq):
    fy, n = int(fq[2:6]), int(fq[-1])
    return f"FY{fy}Q{n - 1}" if n > 1 else f"FY{fy - 1}Q4"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    run(db.connect(), force=a.force)
