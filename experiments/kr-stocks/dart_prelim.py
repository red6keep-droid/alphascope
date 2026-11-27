"""한국 종목 잠정실적 숫자 — DART `영업(잠정)실적(공정공시)` 원문 표를 파이썬으로 읽는다. AI 0.

왜: 주가가 움직이는 날은 잠정실적 공시날이다(collect_kr_earn_dart). 분기보고서는 몇 주 뒤에 나와서, 그 사이 `회사는 돈을 더 벌고 있나?` 카드가 한 분기 늦었다.
공시 꼴(거래소 서식)이 회사마다 같다 — `1. 연결실적내용` 표: 매출액 · 영업이익 · 법인세비용차감전계속사업이익 · 당기순이익 · 지배기업 소유주지분 순이익,
줄마다 당해실적 / 누계실적, 칸 = 당기 · 전기 · 전기대비 증감율 · 흑자적자전환 · 전년동기 · 전년동기대비 증감율 · 흑자적자전환. 단위는 표 머리(억원 · 백만원 · 천원 · 원).

어디서 받나: 하루 공시 목록(collect_kr_dart.filings, 이미 받는 7일 목록)에 잠정실적 줄이 보이면 그 접수번호 원문 하나(document.xml). 캐시에 한 번도 없는 회사는
처음 한 번만 그 회사 최근 120일 목록(list.json)에서 찾는다. 정정 공시([기재정정])는 같은 분기 값을 덮는다.
캐시 = {종목 코드: {"rcept", "day"(공시일), "period"(당기 시작 ~ 끝), "unit", "rows": {rev · opinc · pretax · ni · ni_own: {"q", "prev", "qoq", "yoy_v", "yoy", "turn_q", "turn_y"}}}}

    python experiments/kr-stocks/dart_prelim.py 259960 010140      # 시험 — 받아서 출력
"""

import datetime
import io
import json
import os
import re
import sys
import time
import zipfile
from html import unescape

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
API = "https://opendart.fss.or.kr/api"
CACHE = os.path.join(BASE, "data", "dart_prelim.json")
FIRST_DAYS = 120
NAMES = (("rev", r"^매출액"), ("opinc", r"^영업이익"), ("pretax", r"^법인세비용차감전"), ("ni_own", r"^지배기업"), ("ni", r"^당기순이익"))
UNIT = {"조원": 1e12, "억원": 1e8, "백만원": 1e6, "천원": 1e3, "원": 1.0}


def _key():
    return os.environ.get("DART_API_KEY", "").strip()


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(path, d):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def is_prelim(title):
    return "영업(잠정)실적" in (title or "")


def _cells(xml):
    """원문 → 표 칸 글자 목록(순서대로)."""
    t = re.sub(r"<T[DHE][^>]*>", "\x01", xml, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    return [re.sub(r"\s+", " ", unescape(c)).strip() for c in t.split("\x01")]


def _num(c):
    c = (c or "").replace(",", "").strip()
    neg = c.startswith("(") and c.endswith(")")
    c = c.strip("()")
    try:
        v = float(c)
    except ValueError:
        return None
    return -v if neg else v


def parse(xml):
    """잠정실적 원문 → {"period", "unit", "rows"} 또는 None(표가 없는 꼴 — 현대차 · 기아 월 판매 실적 등)."""
    cells = _cells(xml)
    unit = next((UNIT[m.group(1)] for c in cells for m in [re.search(r"단위\s*:\s*(조원|억원|백만원|천원|원)", c)] if m), None)
    start = next((i for i, c in enumerate(cells) if c == "실적기간"), 0)   # 정정 공시는 앞에 `정정일자` 날짜가 먼저 온다 (삼성전자 10-29)
    dates = [c for c in cells[start:] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", c)]
    if unit is None or len(dates) < 2:
        return None
    rows = {}
    for i, c in enumerate(cells):
        nm = c.replace(" ", "")
        key = next((k for k, pat in NAMES if re.search(pat, nm)), None)
        if not key or key in rows or i + 9 > len(cells) or cells[i + 1] != "당해실적":
            continue
        q, prev, qoq, turn_q, yv, yoy, turn_y = cells[i + 2:i + 9]
        if _num(q) is None:
            continue
        rows[key] = {"q": _num(q) * unit, "prev": None if _num(prev) is None else _num(prev) * unit, "qoq": _num(qoq),
                     "yoy_v": None if _num(yv) is None else _num(yv) * unit, "yoy": _num(yoy),
                     "turn_q": turn_q if "전환" in turn_q else "", "turn_y": turn_y if "전환" in turn_y else ""}
    if "rev" not in rows and "opinc" not in rows:
        return None
    return {"period": [dates[0], dates[1]], "unit": unit, "rows": rows, "fs": "연결" if "연결" in "".join(cells[:40]) else "별도"}


def document(key, rcept):
    r = requests.get(f"{API}/document.xml", params={"crtfc_key": key, "rcept_no": rcept}, timeout=60)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    return z.read(z.namelist()[0]).decode("utf-8", errors="replace")


def _rcept(url):
    m = re.search(r"rcpNo=(\d+)", url or "")
    return m.group(1) if m else ""


def _first_list(key, corp):
    """캐시에 없는 회사 — 최근 FIRST_DAYS 일 거래소 공시 가운데 잠정실적(연결 기준 먼저) 최신 한 건."""
    bgn = (datetime.date.today() - datetime.timedelta(days=FIRST_DAYS)).strftime("%Y%m%d")
    r = requests.get(f"{API}/list.json", params={"crtfc_key": key, "corp_code": corp, "bgn_de": bgn, "pblntf_ty": "I", "page_count": 100}, timeout=30).json()
    pre = [x for x in r.get("list") or [] if is_prelim(x.get("report_nm"))]
    cons = [x for x in pre if "연결" in x["report_nm"]]
    pick = sorted(cons or pre, key=lambda x: x["rcept_no"])
    return [{"rcept": x["rcept_no"], "day": f'{x["rcept_dt"][:4]}-{x["rcept_dt"][4:6]}-{x["rcept_dt"][6:]}', "t": x["report_nm"]} for x in pick[-1:]]


def run(codes, corp_map, disc=None, cache_path=CACHE, first_cap=60):
    """codes = [종목 코드], corp_map = {종목 코드: DART 회사 번호}, disc = {종목 코드: [{t, d, u}]} (7일 공시 목록). → 캐시(dict)."""
    key = _key()
    cache = _load(cache_path)
    if not key:
        print("[prelim] DART_API_KEY 없음 — 캐시만")
        return cache
    calls = first = 0
    for code in codes:
        todo = [{"rcept": _rcept(x.get("u")), "day": x["d"], "t": x["t"]} for x in (disc or {}).get(code) or [] if is_prelim(x.get("t"))]
        todo = [x for x in todo if x["rcept"]]
        if not todo and code not in cache and corp_map.get(code) and first < first_cap:
            first += 1
            try:
                todo = _first_list(key, corp_map[code])
                calls += 1
            except Exception as e:  # noqa: BLE001
                print(f"[prelim] {code} 목록 실패: {str(e)[:80]}")
            if not todo:
                cache[code] = {"none": str(datetime.date.today())}
        cons = [x for x in todo if "연결" in x["t"]]
        for x in sorted(cons or todo, key=lambda x: x["rcept"]):
            if (cache.get(code) or {}).get("rcept", "") >= x["rcept"]:
                continue
            try:
                got = parse(document(key, x["rcept"]))
                calls += 1
            except Exception as e:  # noqa: BLE001
                print(f"[prelim] {code} {x['rcept']} 원문 실패: {str(e)[:80]}")
                continue
            if got:
                cache[code] = dict(got, rcept=x["rcept"], day=x["day"], fixed=x["t"].startswith("[기재정정]"))
            time.sleep(0.2)
    _save(cache_path, cache)
    print(f"[prelim] 호출 {calls}번 · 처음 살핀 회사 {first} · 잠정실적 있는 회사 {sum(1 for v in cache.values() if v.get('rows'))}")
    return cache


def load(cache_path=CACHE):
    return _load(cache_path)


if __name__ == "__main__":
    sys.path.insert(0, BASE)
    import collect_kr_dart as D
    cm = D.corp_codes(_key())
    c = run(sys.argv[1:], cm, cache_path=os.environ.get("PRELIM_CACHE", CACHE))
    for k in sys.argv[1:]:
        print(k, json.dumps(c.get(k), ensure_ascii=False)[:600])
