"""한국 종목 분기 매출 — 금융감독원 OpenDART 단일회사 주요계정 (2026-10-25 사용자: "실적 탭에 1년밖에 없나" → DART 로).

Yahoo 는 최근 5~6분기만 줘서 `1년 전 대비` 가 1분기뿐이었다. DART 는 2015년부터 분기 · 반기 · 사업보고서를 준다.
- 보고서마다 thstrm_amount = 그 석 달(분기 · 반기 보고서) · 1년치(사업보고서) → 4분기 = 1년치 − 3분기까지 누적(thstrm_add_amount).
- 연결재무제표(CFS) 먼저, 없으면 별도(OFS). 계정 = 매출액(은행 · 보험처럼 매출액이 없는 회사는 빈 칸 → 카드는 `판단 유보`).
- 캐시 data/dart_fin.json — 이미 받은 보고서는 다시 받지 않는다. 아직 안 나온 보고서는 7일마다 다시 물어본다.
약관(opendart.fss.or.kr 이용약관, 10-25 확인): 무료 · 상업 이용 금지 조항 없음(공공데이터법 준용) · 키는 1개, 제3자에게 쓰게 하지 않음 · 하루 호출 한도는 홈페이지 게시.
첫 실행 약 35종목 × 4년 × 4보고서 ≈ 520번, 그 뒤로는 새 보고서만.

    python experiments/kr-stocks/collect_kr_dart.py     # 받기 → data/dart_fin.json, 분기 매출 줄 수 출력
"""

import datetime
import io
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
import zipfile

import requests

import universe_kr as U

BASE = os.path.dirname(os.path.abspath(__file__))
API = "https://opendart.fss.or.kr/api"
CORP = os.path.join(BASE, "data", "dart_corp.json")
CACHE = os.path.join(BASE, "data", "dart_fin.json")
YEARS = 4   # 1년 전 대비 8분기 (미국 카드와 같은 막대 수) — 4년치 보고서
REPORTS = [("11013", "03-31"), ("11012", "06-30"), ("11014", "09-30"), ("11011", "12-31")]   # 1분기 · 반기 · 3분기 · 사업보고서
REV_NAMES = ("매출액", "수익(매출액)", "매출")
RETRY_DAYS = 7


def _key():
    k = os.environ.get("DART_API_KEY", "").strip()
    if k:
        return k
    path = os.path.join(BASE, "..", "..", ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            a, _, v = line.strip().partition("=")
            if a == "DART_API_KEY":
                return re.split(r"\s+#", v, 1)[0].strip().strip('"')
    return ""


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def corp_codes(key):
    """종목 코드 → DART 회사 고유번호. 한 달에 한 번 corpCode.xml(압축)을 받아 우리 35개만 남긴다."""
    c = _load(CORP)
    if c.get("built", "") >= (datetime.date.today() - datetime.timedelta(days=30)).isoformat() and c.get("map"):
        return c["map"]
    r = requests.get(f"{API}/corpCode.xml", params={"crtfc_key": key}, timeout=60)
    r.raise_for_status()
    xml = zipfile.ZipFile(io.BytesIO(r.content)).read("CORPCODE.xml")
    want = {c[0].split(".")[0] for c in U.CANDIDATES}
    m = {}
    for el in ET.fromstring(xml).iter("list"):
        sc = (el.findtext("stock_code") or "").strip()
        if sc in want:
            m[sc] = el.findtext("corp_code")
    _save(CORP, {"built": datetime.date.today().isoformat(), "map": m})
    return m


def _amount(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _report(key, corp, year, rc):
    """보고서 하나의 매출 — {"rev": 그 석 달 · 1년치, "add": 누적} 또는 {"none": 날짜}(아직 없음 · 계정 없음)."""
    r = requests.get(f"{API}/fnlttSinglAcnt.json", params={"crtfc_key": key, "corp_code": corp, "bsns_year": str(year), "reprt_code": rc}, timeout=30).json()
    if r.get("status") != "000":
        return {"none": datetime.date.today().isoformat(), "status": r.get("status")}
    rows = r.get("list") or []
    for fs in ("CFS", "OFS"):
        x = next((x for x in rows if x.get("fs_div") == fs and x.get("account_nm") in REV_NAMES), None)
        if x and _amount(x.get("thstrm_amount")) is not None:
            return {"rev": _amount(x["thstrm_amount"]), "add": _amount(x.get("thstrm_add_amount")), "fs": fs}
    return {"none": datetime.date.today().isoformat(), "status": "no-revenue"}


def run():
    """→ {종목 티커: [{end, rev, cq, yoy}]} (Yahoo 매출 줄과 같은 모양). 키가 없으면 {}."""
    key = _key()
    if not key:
        print("[dart] DART_API_KEY 없음 — 건너뜀 (Yahoo 매출만)")
        return {}
    codes = corp_codes(key)
    cache = _load(CACHE)
    today = datetime.date.today()
    calls = 0
    for sym, *_ in U.CANDIDATES:
        corp = codes.get(sym.split(".")[0])
        if not corp:
            continue
        mine = cache.setdefault(corp, {})
        for year in range(today.year - YEARS + 1, today.year + 1):
            for rc, mmdd in REPORTS:
                end = datetime.date.fromisoformat(f"{year}-{mmdd}")
                if end >= today:
                    continue
                k = f"{year}-{rc}"
                got = mine.get(k)
                if got and ("rev" in got or got["none"] >= (today - datetime.timedelta(days=RETRY_DAYS)).isoformat()):
                    continue
                mine[k] = _report(key, corp, year, rc)
                calls += 1
                time.sleep(0.2)
        _save(CACHE, cache)
    out = {}
    for sym, *_ in U.CANDIDATES:
        mine = cache.get(codes.get(sym.split(".")[0]) or "", {})
        rows = []
        for year in range(today.year - YEARS + 1, today.year + 1):
            q = {rc: mine.get(f"{year}-{rc}") or {} for rc, _ in REPORTS}
            for i, (rc, mmdd) in enumerate(REPORTS):
                rev = q[rc].get("rev")
                if rc == "11011":   # 4분기 = 1년치 − 3분기까지 누적
                    q3 = q["11014"].get("add")
                    rev = rev - q3 if rev is not None and q3 is not None else None
                if rev is not None:
                    rows.append({"end": f"{year}-{mmdd}", "rev": rev, "cq": f"{year}Q{i + 1}", "src": "dart"})
        by = {r["cq"]: r["rev"] for r in rows}
        for r in rows:
            prev = by.get(f"{int(r['cq'][:4]) - 1}{r['cq'][4:]}")
            r["yoy"] = (r["rev"] / prev - 1) * 100 if prev else None
        if rows:
            out[sym] = rows
    n_yoy = sum(1 for v in out.values() for r in v if r["yoy"] is not None)
    print(f"[dart] 호출 {calls}번 · 매출 {len(out)}종목 · 1년 전 대비 {n_yoy}칸")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    s = run()
    for sym in ("005930.KS", "000660.KS", "105560.KS"):
        print(sym, [(r["cq"], round(r["rev"] / 1e12, 1), None if r["yoy"] is None else round(r["yoy"], 1)) for r in s.get(sym, [])][-6:])
