"""하버드 경제복잡도 Atlas — 나라 × 품목(HS92 4자리) × 연도 수출액 · 세계 점유율 · 수출 경쟁력 지수(RCA).

Atlas 는 Comtrade 를 나라끼리 맞춰 본 값(재수출 정리)이라 홍콩 · 싱가포르 중계가 부풀지 않는다.
키 없음. 다시 받을 수 있는 자료라 data/store/competitiveness/ 에 캐시만 둔다(git 제외).
기획: doc/기획/국가-경쟁력-기획.md

    python experiments/competitiveness/fetch_atlas.py            # 한국 + 경쟁국
    python experiments/competitiveness/fetch_atlas.py 410 156    # 고른 나라만
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

API = "https://atlas.hks.harvard.edu/api/graphql"
OUT = Path(__file__).resolve().parents[2] / "data" / "store" / "competitiveness"
YEAR_MIN, YEAR_MAX = 1995, 2024
# 한국 · 중국 · 일본 · 대만 · 미국 · 독일
COUNTRIES = {410: "KOR", 156: "CHN", 392: "JPN", 158: "TWN", 840: "USA", 276: "DEU"}


def gql(query):
    req = urllib.request.Request(API, data=json.dumps({"query": query}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    if d.get("errors"):
        raise RuntimeError(d["errors"])
    return d["data"]


def fetch_products():
    rows = gql("{ productHs92(productLevel: 4) { productId code nameShortEn nameEn topParent { nameShortEn } } }")["productHs92"]
    return {r["productId"]: {"code": r["code"], "name": r["nameShortEn"] or r["nameEn"],
                             "sector": (r.get("topParent") or {}).get("nameShortEn")} for r in rows}


def fetch_country(cid):
    q = (f"{{ countryProductYear(productClass: HS92, productLevel: 4, countryId: {cid}, "
         f"yearMin: {YEAR_MIN}, yearMax: {YEAR_MAX}) "
         "{ productId year exportValue importValue globalMarketShare exportRca } }")
    return gql(q)["countryProductYear"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "products_hs92_4.json").write_text(json.dumps(fetch_products(), ensure_ascii=False))
    ids = [int(a) for a in sys.argv[1:]] or list(COUNTRIES)
    for cid in ids:
        rows = fetch_country(cid)
        (OUT / f"cpy_{COUNTRIES.get(cid, cid)}.json").write_text(json.dumps(rows))
        print(f"[atlas] {COUNTRIES.get(cid, cid)}: {len(rows)}줄")
        time.sleep(1)


if __name__ == "__main__":
    main()
