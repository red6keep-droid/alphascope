"""한국 종목 실적 발표일 = DART 영업(잠정)실적(공정공시) 접수일 (2026-10-31 사용자: 실적 발표는 중요 — 미루지 말고).

야후 한국 실적일은 확정실적 · 컨퍼런스콜 날이라 주가 반응과 맞지 않았다(K26, 10-25 검증). 주가가 움직이는 날은 잠정실적 공시다.
- OpenDART 공시검색(list.json, 공시 유형 I = 거래소공시) 에서 보고서 이름에 `영업(잠정)실적` 이 든 것, 정정(`[기재정정]`)은 뺀다.
  연결 기준 공시가 있는 회사는 그것만(현대차 · 기아는 연결 아닌 `영업(잠정)실적` 으로 매달 판매 실적을 낸다). SK스퀘어처럼 잠정 공시가 없는 회사는 빈 칸.
- 한 분기에 잠정 공시가 둘(분기 초 잠정 · 한 달 뒤 확정 무렵 잠정)인 회사가 있다 → 40일 안에 앞선 것이 있으면 뒤의 것은 뺀다(첫 발표만).
- 공시 시각은 목록 · 원문 어디에도 없다 → 반응일 규칙은 가격으로 정한다(validate 쪽, 이 파일은 날짜만).
- 캐시 data/dart_earn.json — 하루 한 번이면 충분, 새 공시만 붙는다.

    python experiments/kr-stocks/collect_kr_earn_dart.py      # 받기 → data/dart_earn.json
"""
import datetime
import json
import os
import sys
import time

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
API = "https://opendart.fss.or.kr/api/list.json"
CORP = os.path.join(BASE, "data", "dart_corp.json")
OUT = os.path.join(BASE, "data", "dart_earn.json")
START = "20150101"
GAP_DAYS = 40


def _key():
    return os.environ.get("DART_API_KEY", "").strip()


def filings(key, corp_code, bgn, end):
    out, page = [], 1
    while True:
        r = requests.get(API, params=dict(crtfc_key=key, corp_code=corp_code, bgn_de=bgn, end_de=end, pblntf_ty="I", page_no=page, page_count=100), timeout=30).json()
        if r.get("status") == "013":   # 조회된 데이터 없음
            break
        if r.get("status") != "000":
            raise RuntimeError(f"DART {r.get('status')} {r.get('message')}")
        out += r.get("list", [])
        if page >= int(r.get("total_page", 1)):
            break
        page += 1
        time.sleep(0.2)
    return out


def first_prelim(rows):
    """잠정실적 첫 공시 날짜들 (정정 빼고, 40일 안 뒤엣것 빼고)."""
    pre = [x for x in rows if "영업(잠정)실적" in x["report_nm"] and not x["report_nm"].startswith("[기재정정]")]   # [첨부추가] 는 첫 공시라 둔다 (LG에너지솔루션)
    cons = [x for x in pre if "연결재무제표기준" in x["report_nm"]]
    days = sorted({x["rcept_dt"] for x in (cons or pre)})   # 연결 기준이 있으면 그것만 — 현대차 · 기아의 `영업(잠정)실적` 은 매달 판매 실적이다
    keep = []
    for d in days:
        dt = datetime.datetime.strptime(d, "%Y%m%d").date()
        if keep and (dt - keep[-1]).days < GAP_DAYS:
            continue
        keep.append(dt)
    return [d.isoformat() for d in keep]


def run(codes=None):
    key = _key()
    if not key:
        raise SystemExit("DART_API_KEY 없음")
    cmap = json.load(open(CORP))["map"]
    old = json.load(open(OUT)) if os.path.exists(OUT) else {"days": {}}
    end = datetime.date.today().strftime("%Y%m%d")
    for code in codes or sorted(cmap):
        prev = old["days"].get(code) or []
        bgn = (datetime.date.fromisoformat(prev[-1]) - datetime.timedelta(days=GAP_DAYS)).strftime("%Y%m%d") if prev else START
        rows = filings(key, cmap[code], bgn, end)
        new = first_prelim(rows)
        merged = sorted(set(prev) | set(new))
        # 이어 붙일 때 40일 규칙을 다시 건다
        keep = []
        for d in merged:
            dt = datetime.date.fromisoformat(d)
            if keep and (dt - datetime.date.fromisoformat(keep[-1])).days < GAP_DAYS:
                continue
            keep.append(d)
        old["days"][code] = keep
        print(code, len(keep), keep[-3:])
    old["built"] = datetime.date.today().isoformat()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(old, f, ensure_ascii=False, indent=1)
    return old


_cache = None


def load():
    global _cache
    if _cache is None:
        _cache = json.load(open(OUT)) if os.path.exists(OUT) else {"days": {}}
    return _cache


def past(code):
    """지난 잠정실적 공시일 (오래된 것부터)."""
    return (load().get("days") or {}).get(code) or []


def next_date(code, ynext, day):
    """다음 실적 발표일 — (날짜, 어림 여부). 잠정실적은 미리 알리지 않으므로 1년 전 같은 분기 공시일 + 52주(같은 요일)를 어림으로 둔다.
    야후 날짜(대개 확정실적 · 컨퍼런스콜)가 그 어림과 7일 안이면 야후, 아니면 어림(삼성전자 · LG전자처럼 분기 초 잠정이 3주쯤 이르다)."""
    est = next((e for e in ((datetime.date.fromisoformat(d) + datetime.timedelta(days=364)).isoformat() for d in past(code)) if e > day), None)
    if ynext and (not est or abs((datetime.date.fromisoformat(ynext) - datetime.date.fromisoformat(est)).days) <= 7):
        return ynext, False
    return (est, True) if est else (ynext, False)


def reaction_day(code, days, d):
    """공시일 d 의 주가 반영일 — 장 마감 뒤 공시 회사(universe_kr.EARN_NEXT_DAY)는 다음 거래일, 아니면 그날(휴일이면 다음 거래일)."""
    import universe_kr as U
    after = code in U.EARN_NEXT_DAY
    return next((x for x in days if (x > d if after else x >= d)), None)


if __name__ == "__main__":
    run(sys.argv[1:] or None)
