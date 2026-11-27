"""한국 종목 분기 매출 — 금융감독원 OpenDART 단일회사 주요계정.

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
COMPANY = os.path.join(BASE, "data", "dart_company.json")   # 기업개황 (기업 정보 탭, 2026-10-29 P84) — 한 달에 한 번
COMPANY_KEYS = ("corp_name", "corp_name_eng", "ceo_nm", "corp_cls", "adres", "hm_url", "ir_url", "induty_code", "est_dt", "acc_mt")
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


def company():
    """종목 코드 → OpenDART 기업개황(company.json) 일부 칸. 한 달 안에 받은 것은 캐시 그대로. 키가 없으면 캐시만."""
    c = _load(COMPANY)
    fresh = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    if c.get("built", "") >= fresh and c.get("map"):
        return c["map"]
    key = _key()
    if not key:
        return c.get("map") or {}
    codes = corp_codes(key)
    m = {}
    for sym, *_ in U.CANDIDATES:
        code = sym.split(".")[0]
        corp = codes.get(code)
        if not corp:
            continue
        try:
            r = requests.get(f"{API}/company.json", params={"crtfc_key": key, "corp_code": corp}, timeout=30).json()
        except (requests.RequestException, ValueError) as e:
            print(f"[dart] {code} 기업개황 실패: {str(e)[:80]}")
            continue
        if r.get("status") == "000":
            m[code] = {k: (r.get(k) or "").strip() for k in COMPANY_KEYS}
        time.sleep(0.2)
    if m:
        _save(COMPANY, {"built": datetime.date.today().isoformat(), "map": m})
    return m or c.get("map") or {}


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


# ── 최근 공시 목록 · 발행 주식 수 — 한국 정식 · 간단 종목이 같이 쓴다 ──
KST = datetime.timezone(datetime.timedelta(hours=9))
FILINGS = os.path.join(BASE, "data", "dart_list.json")   # 정식 실행 = kr-state, 간단 실행 = quick-state 에 따로
SHARES = os.path.join(BASE, "data", "dart_shares.json")
SKIP_DISC = re.compile(r"소유상황보고서|임원ㆍ주요주주|주식등의대량보유|최대주주등소유주식|자기주식취득결과보고서|증권발행실적보고서|기업설명회")
SHARES_DAYS = 90   # 발행 주식 수는 증자 · 소각 때만 바뀐다 — 90일마다 다시


def filings(cache_path, codes, key=None, days=7, tag="kr"):
    """최근 days 일 공시 목록(공시 검색 list.json — 하루 전체를 쪽마다 받아 우리 종목만 남긴다). 이틀 지난 날은 다시 안 받는다.
    → {"days": {YYYYMMDD: [{c: 종목 코드, t: 보고서 이름, no: 접수 번호, d: 접수일}]}, "calls": n}"""
    cache = _load(cache_path) or {"days": {}}
    cache.setdefault("days", {})
    key = key if key is not None else _key()
    today = datetime.datetime.now(KST).date()
    want = [today - datetime.timedelta(days=i) for i in range(days + 1)]
    calls = 0
    for day in want:
        ds = day.strftime("%Y%m%d")
        if ds in cache["days"] and day < today - datetime.timedelta(days=1):
            continue   # 이틀 지난 날은 다 받은 것으로 — 오늘 · 어제만 다시
        if not key:
            break
        rows, page = [], 1
        while True:
            try:
                j = requests.get(f"{API}/list.json", timeout=60,
                                 params={"crtfc_key": key, "bgn_de": ds, "end_de": ds, "page_no": page, "page_count": 100}).json()
                calls += 1
            except Exception as e:  # noqa: BLE001
                print(f"[{tag}] DART 목록 {ds} 실패: {str(e)[:80]}")
                rows = None
                break
            if j.get("status") not in ("000", "013"):   # 013 = 자료 없음
                print(f"[{tag}] DART 목록 {ds}: {j.get('status')} {j.get('message')}")
                rows = None
                break
            for it in j.get("list", []) or []:
                sc = it.get("stock_code") or ""
                if sc in codes and not SKIP_DISC.search(it.get("report_nm", "")):
                    rows.append({"c": sc, "t": re.sub(r"\s+", " ", it["report_nm"]).strip(), "no": it["rcept_no"], "d": it["rcept_dt"]})
            if page >= int(j.get("total_page") or 1):
                break
            page += 1
            time.sleep(0.3)
        if rows is not None:
            cache["days"][ds] = rows
    keep = {d.strftime("%Y%m%d") for d in want}
    cache["days"] = {k: v for k, v in cache["days"].items() if k in keep}
    cache["calls"] = calls
    print(f"[{tag}] DART 공시 목록 {calls}번 · 우리 종목 공시 {sum(len(v) for v in cache['days'].values())}건({days}일)")
    return cache


def filings_by_code(cache):
    """{종목 코드: [{t, d: YYYY-MM-DD, u}]} 새것 먼저 — 화면 `최근 공시는?` 재료. 자르지 않는다."""
    out = {}
    for day in sorted((cache or {}).get("days", {}), reverse=True):
        for it in cache["days"][day]:
            d = it["d"]
            out.setdefault(it["c"], []).append({"t": it["t"], "d": f"{d[:4]}-{d[4:6]}-{d[6:]}",
                                                "u": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={it['no']}"})
    return out


def _num(v):
    v = re.sub(r"[^\d]", "", str(v or ""))
    return int(v) if v else None


def shares(cache_path, corps, key=None, tag="kr", minutes=None):
    """보통주 발행 주식 총수(주식의 총수 현황 stockTotqySttus) — 시가총액 = 이 수 × 종가(한국거래소 시가총액과 같은 셈, 자기주식 포함).
    corps = {sym: DART 회사 번호}. 가장 최근 정기 보고서부터 찾는다(1 · 3분기 보고서는 칸이 비어 오는 회사가 많아 반기 · 사업보고서로 넘어감).
    캐시 {sym: {"n": 주식 수, "at": 받은 날, "rp": "2026-11012"}} — SHARES_DAYS 마다 다시, 못 찾은 회사는 7일 뒤 다시. → {sym: 주식 수}"""
    cache = _load(cache_path)
    key = key if key is not None else _key()
    today = datetime.date.today()
    y = today.year
    order = [(y, "11014"), (y, "11012"), (y, "11013"), (y - 1, "11011"), (y - 1, "11014"), (y - 1, "11012")]
    calls = got = 0
    t0 = time.time()
    for sym, corp in sorted(corps.items()):
        if minutes and time.time() - t0 > minutes * 60:   # 시간 상한(간단 종목) — 남은 회사는 다음 실행에, 받은 것은 저장 (2026-11-16)
            print(f"[{tag}] 발행 주식 수 {minutes}분 넘음 — 나머지는 다음 실행에")
            break
        e = cache.get(sym) or {}
        age = (today - datetime.date.fromisoformat(e["at"])).days if e.get("at") else None
        if age is not None and age < (SHARES_DAYS if e.get("n") else RETRY_DAYS):
            continue
        if not key or not corp:
            continue
        found = None
        for yr, rc in order:
            try:
                j = requests.get(f"{API}/stockTotqySttus.json", timeout=30,
                                 params={"crtfc_key": key, "corp_code": corp, "bsns_year": str(yr), "reprt_code": rc}).json()
                calls += 1
            except Exception as ex:  # noqa: BLE001
                print(f"[{tag}] {sym} 주식 수 실패: {str(ex)[:80]}")
                break
            time.sleep(0.2)
            row = next((x for x in j.get("list") or [] if (x.get("se") or "").strip() == "보통주"), None) if j.get("status") == "000" else None
            n = _num(row.get("istc_totqy")) if row else None
            if n:
                found = {"n": n, "at": today.isoformat(), "rp": f"{yr}-{rc}"}
                break
        cache[sym] = found or {"n": e.get("n"), "at": today.isoformat(), "rp": e.get("rp"), "miss": True}   # 못 찾으면 옛 값 유지
        got += bool(found)
    _save(cache_path, cache)
    out = {s: v["n"] for s, v in cache.items() if v.get("n") and s in corps}
    print(f"[{tag}] DART 발행 주식 수 호출 {calls}번 · 새로 {got} · 쓸 수 있는 {len(out)}/{len(corps)}종목")
    return out


def cap_ranks(caps):
    """{sym: 시가총액} → {sym: 순위} — 보통주만(우선주 = 코드 끝자리가 0 이 아닌 것), 코스피 · 코스닥 함께 큰 순."""
    ranked = sorted((s for s, v in caps.items() if v and s.split(".")[0].endswith("0")), key=lambda s: -caps[s])
    return {s: i for i, s in enumerate(ranked, 1)}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    s = run()
    for sym in ("005930.KS", "000660.KS", "105560.KS"):
        print(sym, [(r["cq"], round(r["rev"] / 1e12, 1), None if r["yoy"] is None else round(r["yoy"], 1)) for r in s.get(sym, [])][-6:])
