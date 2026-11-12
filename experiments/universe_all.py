"""전체 종목 범위 (universe_all) — 최종 목표 약 850종목의 명단 (2026-11-12 사용자 "그렇게 적용", 기획 = 비공개 기획/회원-내-종목-기획.md 6-5-1).

    python experiments/universe_all.py      # ref/universe_all.json 다시 만들기 (분기 1회 — 지수 편입 · 제외를 따라간다)

미국 = S&P 500 구성 종목 — datasets/s-and-p-500-companies (ODC-PDDL, 원 출처 위키백과 목록). GICS 업종 · 세부 업종도 같이.
한국 = 코스피 시가총액 상위 200 + 코스닥 상위 150 (코스피200 · 코스닥150 에 가깝게) — 보통주만(우선주 · 스팩 제외).
       시가총액은 로고 저장소(MrChartist/global-stock-logos, 고정 커밋)의 메타데이터 값. 한국거래소 구성 종목표는 약관상 자동 수집을 하지 않는다(운영지침 D4-15).
정식 종목(stock-radar · kr-stocks universe)은 이 명단과 별개로 그대로 — 이 명단은 간단 종목 · 로고 · 검색 범위의 바탕.
"""

import csv
import datetime
import io
import json
import os
import re
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "ref", "universe_all.json")
SP500 = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
LOGO_META = "https://raw.githubusercontent.com/MrChartist/global-stock-logos/0f4bf995d9c90d752461ebb7f7604da3290f97a1/companies-metadata.json"
KOSPI_N, KOSDAQ_N = 200, 150
SKIP_NAME = re.compile(r"Pfd|Preferred|SPAC|Special Purpose|기업인수목적|스팩|ETF|ETN|REIT", re.I)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AlphaScope-universe/0.1"})
    return urllib.request.urlopen(req, timeout=60).read()


def us():
    rows = list(csv.DictReader(io.StringIO(get(SP500).decode("utf-8"))))
    return [{"sym": r["Symbol"].replace(".", "-"), "name": r["Security"], "sector": r["GICS Sector"], "sub": r["GICS Sub-Industry"]} for r in rows]


CLS_CACHE = os.path.join(BASE, "ref", "kr_market_cls.json")   # 종목 코드 → Y(코스피) · K(코스닥) · N · E — DART 기업개황 corp_cls, 한 번 받은 것은 다시 안 부른다


def _all_corp_codes(key):
    """상장사 전체 종목 코드 → DART 고유번호 (corpCode.xml 한 번). collect_kr_dart.corp_codes 는 정식 35종목만 남겨서 여기서는 따로."""
    import io as _io
    import xml.etree.ElementTree as ET
    import zipfile
    z = zipfile.ZipFile(_io.BytesIO(get(f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={key}")))
    m = {}
    for el in ET.fromstring(z.read("CORPCODE.xml")).iter("list"):
        sc = (el.findtext("stock_code") or "").strip()
        if sc:
            m[sc] = el.findtext("corp_code")
    return m


def _market_cls(codes):
    """DART 기업개황의 시장 구분 — 로고 메타데이터는 코스닥까지 전부 .KS 로 적어 둬서 쓸 수 없다 (2026-11-12 확인)."""
    import sys
    import time
    sys.path.insert(0, os.path.join(BASE, "kr-stocks"))
    import collect_kr_dart as KD
    try:
        with open(CLS_CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        cache = {}
    need = [c for c in codes if c not in cache]
    if need:
        key = KD._key()
        corp = _all_corp_codes(key) if key else {}
        for c in need:
            if c not in corp:
                continue   # 상장 폐지 등 — 저장하지 않고 넘김
            try:
                r = json.loads(get(f"{KD.API}/company.json?crtfc_key={key}&corp_code={corp[c]}"))
                if r.get("status") == "000":
                    cache[c] = r.get("corp_cls")
            except Exception as e:  # noqa: BLE001 — 키 값이 섞이지 않게 앞부분만
                print(f"[universe_all] {c} 시장 구분 실패: {type(e).__name__}")
            time.sleep(0.15)
        with open(CLS_CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=0)
    return cache


def kr():
    meta = json.loads(get(LOGO_META))
    items = meta.values() if isinstance(meta, dict) else meta
    rows = []
    for x in items:
        if not isinstance(x, dict) or x.get("country") != "South Korea":
            continue
        code = (x.get("yahooTicker") or "").split(".")[0]
        if not re.fullmatch(r"\d{5}0", code) or SKIP_NAME.search(x.get("company") or "") or not x.get("marketCap"):
            continue   # 보통주(끝자리 0)만
        rows.append({"code": code, "name": x.get("company"), "cap": x["marketCap"], "industry": x.get("industry")})
    rows = sorted(rows, key=lambda r: -r["cap"])[:700]   # 상위 700 안에서 코스피 200 · 코스닥 150 이 찬다
    cls = _market_cls([r["code"] for r in rows])
    ks = [dict(r, sym=r["code"] + ".KS", market="KOSPI") for r in rows if cls.get(r["code"]) == "Y"][:KOSPI_N]
    kq = [dict(r, sym=r["code"] + ".KQ", market="KOSDAQ") for r in rows if cls.get(r["code"]) == "K"][:KOSDAQ_N]
    return ks + kq


def load():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"us": [], "kr": []}


def main():
    d = {"built": datetime.date.today().isoformat(), "us": us(), "kr": kr(),
         "_note": "미국 = S&P 500 (datasets/s-and-p-500-companies, ODC-PDDL) · 한국 = 코스피 시총 상위 200 + 코스닥 상위 150, 보통주 (시총 = 로고 저장소 메타데이터)"}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print(f"[universe_all] 미국 {len(d['us'])} · 한국 {len(d['kr'])} (코스피 {sum(1 for r in d['kr'] if r['market'] == 'KOSPI')} · 코스닥 {sum(1 for r in d['kr'] if r['market'] == 'KOSDAQ')}) → {OUT}")


if __name__ == "__main__":
    main()
