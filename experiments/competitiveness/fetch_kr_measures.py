"""테마 카드 '값을 정할 힘' · '몫' 을 보도 대신 숫자로 — 관세청 수출 단가 · 한국은행 수출물가 · 전자공시 영업이익률.

- 관세청 품목별 수출(공공데이터포털 15100475, DATA_GO_KR_API_KEY): HS 4자리 × 해마다 금액(달러) · 무게(kg) · 나라별 금액.
  단가 = 금액 ÷ 무게. 올해는 받은 달까지라 작년 같은 달까지와 견준다.
- 한국은행 수출물가지수(402Y014, ECOS_API_KEY): 달러 기준(D) 월별 — 환율 효과를 뺀 값.
- 전자공시 주요계정(fnlttSinglAcnt, DART_API_KEY): 테마 종목 매출 · 영업이익, 사업보고서(1년) · 반기보고서.
다시 받을 수 있는 자료라 data/store/competitiveness/kr_measures.json 에 캐시만 둔다(git 제외).

    python experiments/competitiveness/fetch_kr_measures.py
"""
import datetime
import io
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "data" / "store" / "competitiveness" / "kr_measures.json"
sys.path.insert(0, str(HERE))
from mock_themes import THEMES  # noqa: E402

TODAY = datetime.date.today()
Y0 = 2019
# 관세청 HS 4자리 — 테마 카드 codes + 양극재
HS = sorted({c for t in THEMES for c in (t["codes"] or [])} | {"2841"})
# 한국은행 수출물가 품목(달러 기준)
ECOS_ITEMS = {"집적회로": "309112AA", "화장품": "305622AA", "LCD 디스플레이": "309211AA", "변압기": "310121AA",
              "전지": "310131AA", "열연강판": "307125AA", "합성수지": "305211AA"}
DART_YEARS = range(TODAY.year - 5, TODAY.year)
OP_NAMES = ("영업이익", "영업이익(손실)")
REV_NAMES = ("매출액", "수익(매출액)", "매출", "영업수익")


def _key(name):
    k = os.environ.get(name, "").strip()
    if not k:
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
            k = os.environ.get(name, "").strip()
        except ImportError:
            pass
    return k


def customs(key):
    """{hs: {year: {"usd", "kg", "months", "by": {나라코드: usd}}}} — 올해는 받은 달까지."""
    out = {}
    for hs in HS:
        for y in range(Y0, TODAY.year + 1):
            r = requests.get("https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList",
                             params={"serviceKey": key, "strtYymm": f"{y}01", "endYymm": f"{y}12", "hsSgn": hs}, timeout=90)
            root = ET.fromstring(r.content)
            if root.findtext("header/resultCode") != "00":
                print(f"[관세청] {hs}/{y}: {(root.findtext('header/resultMsg') or '')[:60]}")
                continue
            d = {"usd": 0.0, "kg": 0.0, "months": set(), "by": {}}
            for it in root.findall("body/items/item"):
                ym = it.findtext("year") or ""
                if not (len(ym) == 7 and ym[4] == "."):   # 총계 줄은 뺀다
                    continue
                usd, kg = float(it.findtext("expDlr") or 0), float(it.findtext("expWgt") or 0)
                d["usd"] += usd
                d["kg"] += kg
                d["months"].add(int(ym[5:]))
                cc = it.findtext("statCd") or "-"
                d["by"][cc] = d["by"].get(cc, 0.0) + usd
            d["months"] = sorted(d["months"])
            out.setdefault(hs, {})[str(y)] = d
            time.sleep(0.3)
        print(f"[관세청] {hs} 완료")
    return out


def customs_ytd(key, hs, y, last_month):
    """작년 같은 달까지 — 올해 받은 달 수에 맞춰 견주기용."""
    r = requests.get("https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList",
                     params={"serviceKey": key, "strtYymm": f"{y}01", "endYymm": f"{y}{last_month:02d}", "hsSgn": hs}, timeout=90)
    root = ET.fromstring(r.content)
    usd = kg = 0.0
    by = {}
    for it in root.findall("body/items/item"):
        ym = it.findtext("year") or ""
        if len(ym) == 7 and ym[4] == ".":
            u = float(it.findtext("expDlr") or 0)
            usd += u
            kg += float(it.findtext("expWgt") or 0)
            cc = it.findtext("statCd") or "-"
            by[cc] = by.get(cc, 0.0) + u
    return {"usd": usd, "kg": kg, "months": list(range(1, last_month + 1)), "by": by}


def ecos(key):
    out = {}
    for name, code in ECOS_ITEMS.items():
        url = f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/1000/402Y014/M/{Y0}01/{TODAY:%Y%m}/{code}/D"
        j = requests.get(url, timeout=30).json()
        rows = (j.get("StatisticSearch") or {}).get("row") or []
        out[name] = [{"month": f'{r["TIME"][:4]}-{r["TIME"][4:]}', "v": float(r["DATA_VALUE"])} for r in rows]
        print(f"[ECOS] {name}: {len(rows)}달")
    return out


def dart(key):
    """{종목코드: {"2024": {"rev", "op"}, "2025H1": {...}}} — 연결 우선."""
    r = requests.get("https://opendart.fss.or.kr/api/corpCode.xml", params={"crtfc_key": key}, timeout=60)
    xml = zipfile.ZipFile(io.BytesIO(r.content)).read("CORPCODE.xml")
    want = {code for t in THEMES for _, code, _ in t["stocks"]}
    corp = {}
    for el in ET.fromstring(xml).iter("list"):
        sc = (el.findtext("stock_code") or "").strip()
        if sc in want:
            corp[sc] = el.findtext("corp_code")
    periods = [(str(y), y, "11011") for y in DART_YEARS] + [(f"{y}H1", y, "11012") for y in (TODAY.year - 1, TODAY.year)]
    out = {}
    for sc in sorted(want):
        if sc not in corp:
            print(f"[DART] {sc} 고유번호 없음")
            continue
        for label, y, rc in periods:
            j = requests.get("https://opendart.fss.or.kr/api/fnlttSinglAcnt.json",
                             params={"crtfc_key": key, "corp_code": corp[sc], "bsns_year": str(y), "reprt_code": rc}, timeout=30).json()
            time.sleep(0.2)
            if j.get("status") != "000":
                continue
            rows = j.get("list") or []
            for fs in ("CFS", "OFS"):
                pick = lambda names: next((x for x in rows if x.get("fs_div") == fs and x.get("account_nm") in names), None)
                rv, op = pick(REV_NAMES), pick(OP_NAMES)
                if rv and op:
                    num = lambda v: float(str(v).replace(",", "")) if v not in (None, "", "-") else None
                    # 반기보고서는 thstrm_add_amount(누적)가 있으면 그것, 없으면 thstrm_amount
                    a = (lambda x: num(x.get("thstrm_add_amount")) or num(x.get("thstrm_amount"))) if rc == "11012" else (lambda x: num(x.get("thstrm_amount")))
                    out.setdefault(sc, {})[label] = {"rev": a(rv), "op": a(op), "fs": fs}
                    break
        print(f"[DART] {sc}: {sorted(out.get(sc, {}))}")
    return out


def main():
    ck, ek, dk = _key("DATA_GO_KR_API_KEY"), _key("ECOS_API_KEY"), _key("DART_API_KEY")
    print(f"키: 관세청 {'있음' if ck else '없음'} · ECOS {'있음' if ek else '없음'} · DART {'있음' if dk else '없음'}")
    try:
        prev = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}
    res = {"built": TODAY.isoformat()}
    if ck:
        res["customs"] = customs(ck)
        for hs, ys in res["customs"].items():
            cur = ys.get(str(TODAY.year))
            if cur and cur["months"] and len(cur["months"]) < 12:
                ys[f"{TODAY.year - 1}ytd"] = customs_ytd(ck, hs, TODAY.year - 1, max(cur["months"]))
                time.sleep(0.3)
    res["ecos"] = ecos(ek) if ek else prev.get("ecos")
    res["dart"] = dart(dk) if dk else prev.get("dart")
    res.setdefault("customs", prev.get("customs"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
