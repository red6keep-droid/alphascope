"""한국 ETF 구성종목(PDF) — 운용사 상품 페이지가 부르는 공개 자료에서 받는다 (2026-11-13 사용자 결정: 운용사 페이지 수집 = 감수한 위험).

    python experiments/stock-etf/kr_holdings.py            # etf_universe.KR 전부 받아 표로 찍는다(캐시 안 씀)

- 출처는 운용사 셋만: KODEX = 삼성자산운용(www.samsungfund.com), TIGER = 미래에셋자산운용(investments.miraeasset.com/tigeretf),
  ACE = 한국투자신탁운용(www.aceetf.co.kr · 자료 서버 papi.aceetf.co.kr). 네이버 · 구글 · KRX 정보데이터시스템은 쓰지 않는다.
  robots.txt: 미래에셋 `Allow: /tigeretf/`, 삼성 `allow: /`, ACE `Allow:/` (papi.aceetf.co.kr 는 robots.txt 없음 = 404).
- 예의: 요청 사이 2초 이상, 보통 브라우저 User-Agent, 한 번에 하나씩. 로그인 · 토큰 · 쿠키 필요 없음.
- 운용사별 요청 수(종목 1개당): 미래에셋 2(상품 페이지 HTML + 구성 JSON) · 삼성 2~3(상품 찾기 + 상품 JSON + 전체 구성) · ACE 3~4(찾기 + 기본 정보 + 구성).
- AI 0. 주 1회(fetch_all 의 max_age_days=7)만 다시 받는다.

엔드포인트(페이지 JS 에서 찾은 것 — 사이트 개편 때 깨질 수 있다):
  미래에셋  상품 페이지  /tigeretf/ko/product/search/detail/index.do?ksdFund=<ISIN>   (총보수 · 상장일 · 순자산총액은 이 HTML 에서)
            구성 JSON   /tigeretf/ko/product/chart/prdct-item-list.ajax?ksdFund=<ISIN>&prfPrd=Week01&listCnt=1000  (트리맵이 부르는 것)
  삼성      상품 찾기   /api/v1/kodex/product.do?...&srchVal=<6자리>      → fId(예 2ETF01)
            상품 JSON   /api/v1/kodex/product/<fId>.do                  (info.product.bosuInfo · listD · nav(억원), pdf 앞 30줄 + totalCnt)
            전체 구성   /api/v1/kodex/product-pdf/<fId>.do?gijunYMD=YYYY.MM.DD
  ACE       찾기        https://papi.aceetf.co.kr/api/funds?searchValue=<6자리>   → fundCd(예 K55101D78195) · stdDt · lstdDt · nastAmt
            기본 정보   /api/funds/<fundCd>/product                      (total_FEE %, listingDate, nastAmt 원)
            구성        /api/funds/<fundCd>/pdf?page=1&size=1000&std_dt=YYYYMMDD   (std_dt 없으면 400)
"""

import datetime
import html as html_lib
import json
import os
import re
import sys
import time

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
GAP = 2.0          # 초 — 요청 사이 최소 간격
TIMEOUT = 30
TOP_N = 10

MIRAE = "https://investments.miraeasset.com/tigeretf"
SAMSUNG = "https://www.samsungfund.com"
ACE_WEB = "https://www.aceetf.co.kr"
ACE_API = "https://papi.aceetf.co.kr"

SOURCE = {"KODEX": "삼성자산운용", "TIGER": "미래에셋자산운용", "ACE": "한국투자신탁운용"}

# 현금 · 예금 · 선물 · 증거금 줄 — 종목으로 세지 않는다
_NOT_STOCK = re.compile(r"원화예금|예금|현금|설정현금액|선물|증거금|미수|미지급|\bCASH\b|\bFUT|futures?", re.I)

_s = requests.Session()
_s.headers.update({"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"})
_last = [0.0]


def _get(url, params=None, referer=None, origin=None, as_json=True):
    """한 번에 하나, 직전 요청과 GAP 초 이상 띄운다."""
    wait = _last[0] + GAP - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    headers = {}
    if referer:
        headers["Referer"] = referer
    if origin:
        headers["Origin"] = origin
    if as_json:
        headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
    try:
        r = _s.get(url, params=params, headers=headers, timeout=TIMEOUT)
    finally:
        _last[0] = time.monotonic()
    r.raise_for_status()
    return r.json() if as_json else r.text


# ── 공통 ──

def code6(sym):
    return sym.split(".")[0]


def isin(code):
    """한국 주식 · ETF 6자리 → ISIN (KR7 + 코드 + 00 + 검사 숫자, ISO 6166 룬 방식)."""
    body = "KR7" + code + "00"
    digits = "".join(str(int(c, 36)) for c in body)
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return body + str((10 - total % 10) % 10)


def brand(name):
    for b in SOURCE:
        if name.startswith(b):
            return b
    raise ValueError(f"운용사 모름: {name}")


def _iso(ymd):
    s = re.sub(r"\D", "", str(ymd or ""))
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) >= 8 else None


def _num(x):
    if x is None:
        return None
    try:
        return float(str(x).replace(",", "").strip())
    except ValueError:
        return None


def _code(c):
    """종목 코드 맞추기 — 한국 = 6자리, 미국 = 야후식 티커('AAPL US Equity' · 'AAPL US' → AAPL, 'BRK/B US' → BRK-B).
    티커를 못 얻으면 ISIN 그대로."""
    c = re.sub(r"\s+", " ", str(c or "")).strip()
    m = re.match(r"^([A-Z0-9./]+) (US|UW|UN|UQ)( EQUITY)?$", c, re.I)
    if m:
        return m.group(1).upper().replace("/", "-").replace(".", "-")
    return c


def _is_stock(code, name):
    code = (code or "").strip()
    if code.startswith("KRD"):          # 원화예금 등 (KRD010010001)
        return False
    return not _NOT_STOCK.search(name or "")


def _pack(rows, at, source, url, fee=None, since=None, aum=None):
    """rows = [(코드, 이름, 비중 %)] — 현금 · 선물 빼고 비중 큰 순 10개."""
    stocks = [(c, n, w) for c, n, w in rows if _is_stock(c, n)]
    stocks.sort(key=lambda r: -(r[2] or 0))
    out = {"at": at, "source": source, "url": url,
           "top": [[_code(c), n, round(w, 2)] for c, n, w in stocks[:TOP_N] if w is not None],
           "n": len(stocks)}
    if fee is not None:
        out["fee"] = fee
    if since:
        out["since"] = since
    if aum:
        out["aum_krw"] = int(aum)
    if not out["at"]:
        raise ValueError("기준일 없음")
    return out


# ── 미래에셋 (TIGER) ──

def _text(html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&#37;", "%").replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", t)


# 같은 이름의 두 종류 주식 — 미래에셋 표는 이름이 같아(`Alphabet Inc`) 이름 → 티커가 겹친다, ISIN 으로 먼저 (2026-11-13 목업에서 알파벳 C 가 두 번)
ISIN_TICKER = {"US02079K3059": "GOOGL", "US02079K1079": "GOOG", "US35137L1052": "FOXA", "US35137L2043": "FOX", "US65249B1098": "NWSA", "US65249B2088": "NWS"}


def _mirae(sym):
    ksd = isin(code6(sym))
    page = f"{MIRAE}/ko/product/search/detail/index.do?ksdFund={ksd}"
    html = _get(page, as_json=False)   # 없는 ISIN 이어도 200 빈 껍데기 — 아래 구성 JSON 이 비어 실패한다
    t = _text(html)
    fee = since = aum = None
    m = re.search(r"총보수\s*연\s*([\d.]+)\s*%", t)
    if m:
        fee = float(m.group(1))
    m = re.search(r"상장일\s*(\d{4})[.-](\d{2})[.-](\d{2})", t)
    if m:
        since = "-".join(m.groups())
    m = re.search(r"순자산총액\s*([\d,]+)\s*억원", t)
    if m:
        aum = int(m.group(1).replace(",", "")) * 10**8
    data = _get(f"{MIRAE}/ko/product/chart/prdct-item-list.ajax",
                params={"ksdFund": ksd, "prfPrd": "Week01", "listCnt": 1000}, referer=page)
    rows = data.get("rtnData") or []
    if not rows:
        raise ValueError(f"미래에셋 구성 비어 있음 ({ksd})")
    at = _iso(rows[0].get("wkdate"))
    def own_code(r):   # 한국 = 6자리 memItemcode, 해외 = memItemcode "0" → ISIN(code)
        c = (r.get("memItemcode") or "").strip()
        return c if c and c != "0" else r.get("code")
    items = [(own_code(r), r.get("memItemname"), _num(r.get("stockRate"))) for r in rows]
    if any(r.get("memItemgb") == "2" for r in rows[:TOP_N]):
        # 해외 종목은 JSON 에 티커가 없다(memItemcode "0", code = ISIN) — 표(엑셀과 같은 목록) 첫 쪽에서 이름 → 티커
        tbl = _get(f"{MIRAE}/ko/product/search/detail/pdfListAjax.ajax",
                   params={"ksdFund": ksd, "pageIndex": 1, "firstIndex": 0, "listCnt": TOP_N + 5}, referer=page, as_json=False)
        tick = {}
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, re.S):
            td = [html_lib.unescape(re.sub(r"<[^>]+>|\s+", " ", x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(td) >= 2 and td[0]:
                tick[td[1]] = td[0]
        items = [(ISIN_TICKER.get(c) or tick.get(n, c), n, w) for c, n, w in items]
    return _pack(items, at, SOURCE["TIGER"], page, fee, since, aum)


# ── 삼성 (KODEX) ──

def _samsung(sym):
    code = code6(sym)
    hits = _get(f"{SAMSUNG}/api/v1/kodex/product.do",
                params={"ordrColm": "NAV", "ordrSort": "DESC", "pageNo": 1, "srchTerm": "w", "srchVal": code},
                referer=f"{SAMSUNG}/etf/product/list.do")
    fid = next((h["fId"] for h in hits if h.get("stkTicker") == code), None)
    if not fid:
        raise ValueError(f"삼성 상품 찾기 실패 ({code})")
    page = f"{SAMSUNG}/etf/product/view.do?id={fid}"
    d = _get(f"{SAMSUNG}/api/v1/kodex/product/{fid}.do", referer=page)
    p = (d.get("info") or {}).get("product") or {}
    pdf = d.get("pdf") or {}
    ymd = str(pdf.get("gijunYMD") or "")
    rows = pdf.get("list") or []
    if int(pdf.get("totalCnt") or 0) > len(rows) and len(ymd) == 8:
        full = _get(f"{SAMSUNG}/api/v1/kodex/product-pdf/{fid}.do",
                    params={"gijunYMD": f"{ymd[:4]}.{ymd[4:6]}.{ymd[6:]}"}, referer=page)
        rows = (full.get("pdf") or {}).get("list") or rows
    if not rows:
        raise ValueError(f"삼성 구성 비어 있음 ({fid})")
    m = re.match(r"\s*([\d.]+)\s*%", p.get("bosuInfo") or "")
    fee = float(m.group(1)) if m else None
    nav = _num(p.get("nav"))   # 순자산, 억원 (사이트 표기 `순자산(억원)`)
    items = [(r.get("itmNo"), r.get("secNm"), _num(r.get("ratio"))) for r in rows]
    return _pack(items, _iso(ymd), SOURCE["KODEX"], page, fee, _iso(p.get("listD")), nav * 10**8 if nav else None)


# ── 한국투자 (ACE) ──

def _ace(sym):
    code = code6(sym)
    hdr = {"referer": ACE_WEB + "/", "origin": ACE_WEB}
    found = _get(f"{ACE_API}/api/funds", params={"searchValue": code, "page": 1, "size": 10}, **hdr)
    f = next((x for x in found.get("data") or [] if (x.get("badge") or {}).get("stockCode") == code
              or x.get("stockCd") == isin(code)), None)
    if not f:
        raise ValueError(f"ACE 상품 찾기 실패 ({code})")
    fcd = f["fundCd"]
    page = f"{ACE_WEB}/fund/{fcd}"
    hdr["referer"] = page
    info = _get(f"{ACE_API}/api/funds/{fcd}/product", **hdr)
    std = str(f.get("stdDt") or found.get("std_DT") or "")
    pdf = _get(f"{ACE_API}/api/funds/{fcd}/pdf", params={"page": 1, "size": 1000, "std_dt": std}, **hdr)
    last = str(pdf.get("last_STD_DT") or "")
    if last.isdigit() and std.isdigit() and last > std:     # 더 새 구성(다음 거래일 바스켓)이 올라와 있으면 그것으로
        pdf = _get(f"{ACE_API}/api/funds/{fcd}/pdf", params={"page": 1, "size": 1000, "std_dt": last}, **hdr)
    rows = pdf.get("pdfList") or []
    if not rows:
        raise ValueError(f"ACE 구성 비어 있음 ({fcd})")
    fee = _num(info.get("total_FEE"))       # 이미 % 단위 (예 0.0047 = 연 0.0047%)
    items = [(r.get("jm_KSC_CD"), r.get("sec_NM"), _num(r.get("wg"))) for r in rows]
    return _pack(items, _iso(pdf.get("std_DT") or rows[0].get("std_DT")), SOURCE["ACE"], page, fee,
                 _iso(info.get("listingDate") or f.get("lstdDt")), info.get("nastAmt") or f.get("nastAmt"))


# ── 바깥에서 부르는 것 ──

def fetch(sym, name=None):
    """sym = '305540.KS'. name 이 없으면 etf_universe 에서 찾는다. 실패하면 예외."""
    if name is None:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import etf_universe as E
        name = E.BY_SYM[sym][1]
    b = brand(name)
    return {"KODEX": _samsung, "TIGER": _mirae, "ACE": _ace}[b](sym)


def fetch_all(syms, cache_path, max_age_days=7):
    """7일 지난 것만 다시 받는다. 실패하면 지난 값 그대로. 캐시 기준 = 받은 날(got), 'at' 은 운용사가 밝힌 구성 기준일."""
    try:
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        cache = {}
    today = datetime.date.today()
    got = 0
    for sym in syms:
        old = cache.get(sym)
        stamp = old and (old.get("got") or old.get("at"))
        if stamp and (today - datetime.date.fromisoformat(stamp)).days < max_age_days:
            continue
        try:
            new = fetch(sym)
            new["got"] = today.isoformat()
            cache[sym] = new
            got += 1
        except Exception as e:  # noqa: BLE001
            print(f"[etf] {sym} 한국 구성 받기 실패 (지난 값 유지): {str(e)[:80]}")
    if got:
        os.makedirs(os.path.dirname(os.path.abspath(cache_path)), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
        print(f"[etf] 한국 구성 {got}개 새로 받음 → {cache_path}")
    return cache


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import etf_universe as E
    only = sys.argv[1:]
    fails = []
    for sym, name, *_ in E.KR:
        if only and code6(sym) not in only:
            continue
        try:
            d = fetch(sym, name)
        except Exception as e:  # noqa: BLE001
            fails.append((sym, name, str(e)[:120]))
            print(f"{code6(sym)} {name:<24} 실패: {str(e)[:120]}")
            continue
        top3 = " · ".join(f"{n} {w}" for _, n, w in d["top"][:3]) or "(주식 없음)"
        s10 = sum(w for *_, w in d["top"])
        aum = f"{d['aum_krw'] / 1e8:,.0f}억" if d.get("aum_krw") else "-"
        print(f"{code6(sym)} {name:<24} {d['source']:<9} {d['at']} n={d['n']:<4} 상위10합={s10:5.1f}  "
              f"보수={d.get('fee', '-')} 상장={d.get('since', '-')} 순자산={aum} | {top3}")
    if fails:
        print(f"\n실패 {len(fails)}개:")
        for f in fails:
            print(" ", *f)
