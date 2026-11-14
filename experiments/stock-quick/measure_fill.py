"""간단 정보 빈 칸 실측 — 코드 짜기 전에 카드별로 값이 얼마나 채워지나 (2026-11-14 사용자 "그렇게 반영 · 계속 진행", 기획 6-3-2 ④).

    .venv/bin/python experiments/stock-quick/measure_fill.py

한 번만 손으로 돌린다(정식 실행 07:30 · 16:10 KST 피해서). 결과 = output/fill_measure.json + 화면 요약.
  A. 853종목 일봉 1년 묶음(yfinance, 100개씩) — 받힘 · 1년 미만 · 거래 멈춤 · 분할 기록
  B. 표본 50종목(미국 25 · 한국 25) 야후 상세 — 의견 · 목표가 · 공매도 · 실적일 · 분기 매출
  C. Finnhub 실적 달력 한 번 — 앞으로 100일 미국 · 한국 몇 종목이 잡히나
  D. SEC companyfacts 표본 미국 25 — 분기 매출 항목이 있나
  E. DART — 한글 회사명(고유번호 목록) · 여러 회사 재무 한 번(표본 한국 25)
  F. 위키데이터 — 미국 503 한국어 이름
  G. 이미 모은 기사(상태 저장소 · gh-pages) 제목에서 간단 종목 이름이 7일 안에 몇 번 나오나
바깥 요청에 개인 정보(메일 등)를 넣지 않는다 — User-Agent 는 일반 이름.
"""

import datetime
import io
import json
import os
import random
import re
import subprocess
import sys
import time
import zipfile
import xml.etree.ElementTree as ET

import requests
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(EXP)
OUT = os.path.join(HERE, "output", "fill_measure.json")
UA = {"User-Agent": "AlphaScope-measure/0.1"}
sys.path.insert(0, os.path.join(EXP, "stock-radar"))
sys.path.insert(0, os.path.join(EXP, "kr-stocks"))
import universe as U  # noqa: E402
import universe_kr as K  # noqa: E402


def env(name):
    v = os.environ.get(name)
    if v:
        return v
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"\'')
    return None


uni = json.load(open(os.path.join(EXP, "ref", "universe_all.json"), encoding="utf-8"))
FULL = set(U.BY_SYM) | set(K.BY_SYM)
US = [r["sym"] for r in uni["us"]]
KR = [r["sym"] for r in uni["kr"]]
ALL = US + KR
res = {"measured": datetime.datetime.now().isoformat(timespec="minutes"), "n_us": len(US), "n_kr": len(KR),
       "full_in_universe": len([s for s in ALL if s in FULL])}
print(f"명단 미국 {len(US)} · 한국 {len(KR)} · 그중 정식 {res['full_in_universe']}")

# ── A. 일봉 1년 묶음 ─────────────────────────────────────────────
t0 = time.time()
daily = {}
for i in range(0, len(ALL), 100):
    chunk = ALL[i:i + 100]
    try:
        df = yf.download(chunk, period="1y", interval="1d", group_by="ticker", actions=True,
                         auto_adjust=False, threads=True, progress=False)
    except Exception as e:  # noqa: BLE001
        print("묶음 실패", i, e)
        df = None
    for s in chunk:
        try:
            d = df[s] if df is not None else None
            c = d["Close"].dropna() if d is not None else []
            sp = d["Stock Splits"].fillna(0) if d is not None and "Stock Splits" in d else []
            daily[s] = {"rows": int(len(c)), "last": str(c.index[-1].date()) if len(c) else None,
                        "splits": [f"{ix.date()} {v:g}" for ix, v in sp[sp > 0].items()] if len(sp) else []}
        except Exception:  # noqa: BLE001
            daily[s] = {"rows": 0, "last": None, "splits": []}
    time.sleep(2)
res["A_seconds"] = round(time.time() - t0)
lasts = sorted({v["last"] for v in daily.values() if v["last"]})
newest = {m: max((daily[s]["last"] or "") for s in grp) for m, grp in (("US", US), ("KR", KR))}


def summarize(grp, m):
    empty = [s for s in grp if daily[s]["rows"] == 0]
    short = [s for s in grp if 0 < daily[s]["rows"] < 240]
    stale = [s for s in grp if daily[s]["last"] and daily[s]["last"] < newest[m]
             and (datetime.date.fromisoformat(newest[m]) - datetime.date.fromisoformat(daily[s]["last"])).days > 7]
    split = {s: daily[s]["splits"] for s in grp if daily[s]["splits"]}
    return {"empty": empty, "short_lt_1y": short, "stale_gt_7d": stale, "splits": split, "newest": newest[m]}


res["A"] = {"US": summarize(US, "US"), "KR": summarize(KR, "KR")}
for m in ("US", "KR"):
    a = res["A"][m]
    print(f"A {m}: 빈 {len(a['empty'])} · 1년 미만 {len(a['short_lt_1y'])} · 7일 넘게 멈춤 {len(a['stale_gt_7d'])} · 분할 기록 {len(a['splits'])}")
print(f"A 걸린 시간 {res['A_seconds']}초")

# ── 표본 50 ───────────────────────────────────────────────────────
random.seed(20261114)
us_light = [s for s in US if s not in FULL]
kospi = [r["sym"] for r in uni["kr"] if r["market"] == "KOSPI" and r["sym"] not in FULL]
kosdaq = [r["sym"] for r in uni["kr"] if r["market"] == "KOSDAQ" and r["sym"] not in FULL]
S_US = random.sample(us_light, 25)
S_KR = random.sample(kospi, 10) + random.sample(kosdaq, 15)
res["sample"] = {"US": S_US, "KR": S_KR}

# ── B. 야후 상세 ─────────────────────────────────────────────────
B = {}
for s in S_US + S_KR:
    t = yf.Ticker(s)
    row = {}
    try:
        info = t.info or {}
        row["analysts"] = bool(info.get("numberOfAnalystOpinions"))
        row["target"] = bool(info.get("targetMeanPrice"))
        row["recommend"] = info.get("recommendationKey") not in (None, "none")
        row["short"] = bool(info.get("sharesShort"))
        row["shares"] = bool(info.get("sharesOutstanding"))
        row["name_info"] = info.get("longName") or info.get("shortName")
    except Exception as e:  # noqa: BLE001
        row["info_error"] = str(e)[:80]
    try:
        cal = t.calendar or {}
        ed = cal.get("Earnings Date") if isinstance(cal, dict) else None
        row["earnings_date"] = [str(x) for x in ed] if ed else None
    except Exception:  # noqa: BLE001
        row["earnings_date"] = None
    try:
        q = t.quarterly_income_stmt
        row["q_revenue"] = bool(q is not None and not q.empty and "Total Revenue" in q.index
                                and q.loc["Total Revenue"].dropna().size > 0)
    except Exception:  # noqa: BLE001
        row["q_revenue"] = False
    B[s] = row
    time.sleep(0.7)
res["B"] = B


def rate(keys, field):
    v = [B[k].get(field) for k in keys]
    return f"{sum(1 for x in v if x)}/{len(v)}"


for m, keys in (("US", S_US), ("KR", S_KR)):
    print(f"B {m}: 의견 {rate(keys, 'recommend')} · 애널리스트 수 {rate(keys, 'analysts')} · 목표가 {rate(keys, 'target')}"
          f" · 공매도 {rate(keys, 'short')} · 실적일 {rate(keys, 'earnings_date')} · 분기 매출 {rate(keys, 'q_revenue')}")

# ── C. Finnhub 실적 달력 ─────────────────────────────────────────
fk = (env("FINNHUB_API_KEY") or "").split(",")[0].strip()   # 첫 키만 — 키 돌려 쓰기는 약관상 우회(price_source._key 와 같은 규칙)
if fk:
    today = datetime.date.today()
    try:
        j = requests.get("https://finnhub.io/api/v1/calendar/earnings", headers=UA, timeout=60,
                         params={"from": str(today), "to": str(today + datetime.timedelta(days=100)), "token": fk}).json()
        syms = {e.get("symbol") for e in j.get("earningsCalendar", [])}
        us_hit = [s for s in US if s.replace("-", ".") in syms or s in syms]
        kr_hit = [s for s in KR if s in syms or s.split(".")[0] in syms]
        res["C"] = {"rows": len(syms), "US_hit": len(us_hit), "KR_hit": len(kr_hit),
                    "US_miss_sample": [s for s in US if s not in us_hit][:20]}
        print(f"C Finnhub 100일: 전체 {len(syms)} · 미국 {len(us_hit)}/{len(US)} · 한국 {len(kr_hit)}/{len(KR)}")
    except Exception as e:  # noqa: BLE001
        res["C"] = {"error": str(e)[:120]}
        print("C 실패", e)

# ── D. SEC companyfacts ──────────────────────────────────────────
REV = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
       "RevenuesNetOfInterestExpense", "InterestAndDividendIncomeOperating"]
try:
    tick = requests.get("https://www.sec.gov/files/company_tickers.json", headers=UA, timeout=60)
    tick.raise_for_status()
    cik = {v["ticker"].replace(".", "-"): v["cik_str"] for v in tick.json().values()}
    D = {"cik_found": sum(1 for s in US if s in cik)}
    hit = {}
    for s in S_US:
        if s not in cik:
            hit[s] = "no_cik"
            continue
        r = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik[s]:010d}.json", headers=UA, timeout=60)
        time.sleep(0.2)
        if r.status_code != 200:
            hit[s] = f"http {r.status_code}"
            continue
        g = r.json().get("facts", {}).get("us-gaap", {})
        best = None
        for tag in REV:
            for u in g.get(tag, {}).get("units", {}).get("USD", []):
                if (u.get("fp") or "").startswith("Q") or u.get("form") == "10-Q":
                    if not best or u["end"] > best[1]:
                        best = (tag, u["end"])
        hit[s] = best
    D["sample"] = hit
    D["recent"] = sum(1 for v in hit.values() if isinstance(v, tuple) and v[1] >= "2026-06-01")
    res["D"] = D
    print(f"D SEC: CIK {D['cik_found']}/{len(US)} · 표본 분기 매출(26-06 이후) {D['recent']}/{len(S_US)}")
except Exception as e:  # noqa: BLE001
    res["D"] = {"error": str(e)[:160]}
    print("D 실패", e)

# ── E. DART ─────────────────────────────────────────────────────
dk = env("DART_API_KEY")
if dk:
    try:
        z = requests.get("https://opendart.fss.or.kr/api/corpCode.xml", params={"crtfc_key": dk}, timeout=120)
        root = ET.fromstring(zipfile.ZipFile(io.BytesIO(z.content)).read("CORPCODE.xml"))
        by_stock = {}
        for el in root.iter("list"):
            sc = (el.findtext("stock_code") or "").strip()
            if sc:
                by_stock[sc] = (el.findtext("corp_code"), el.findtext("corp_name"))
        codes = [r["code"] for r in uni["kr"]]
        E = {"name_ko": sum(1 for c in codes if c in by_stock),
             "name_examples": [by_stock[c][1] for c in codes[:5] if c in by_stock]}
        corps = [by_stock[s.split(".")[0]][0] for s in S_KR if s.split(".")[0] in by_stock]
        got = {}
        for rc in ("11014", "11012"):   # 3분기 · 반기
            j = requests.get("https://opendart.fss.or.kr/api/fnlttMultiAcnt.json", timeout=60,
                             params={"crtfc_key": dk, "corp_code": ",".join(corps), "bsns_year": "2026", "reprt_code": rc}).json()
            E[f"multi_{rc}_status"] = j.get("status")
            for it in j.get("list", []) or []:
                if it.get("account_nm") in ("매출액", "수익(매출액)", "영업수익", "매출") or "매출" in (it.get("account_nm") or ""):
                    got.setdefault(it["stock_code"], rc)
            if got:
                break
        E["revenue_hit"] = f"{len(got)}/{len(corps)}"
        E["revenue_miss"] = [s for s in S_KR if s.split(".")[0] not in got]
        res["E"] = E
        print(f"E DART: 한글 이름 {E['name_ko']}/{len(codes)} 예 {E['name_examples']} · 여러 회사 매출 {E['revenue_hit']}")
        res["_kr_names"] = {c: by_stock[c][1] for c in codes if c in by_stock}
    except Exception as e:  # noqa: BLE001
        res["E"] = {"error": str(e)[:160]}
        print("E 실패", e)

# ── F. 위키데이터 한국어 이름 ───────────────────────────────────────
Q = """SELECT ?t ?ko WHERE { ?c p:P414 ?st . ?st ps:P414 ?ex ; pq:P249 ?t . VALUES ?ex { wd:Q13677 wd:Q82059 }
  ?c rdfs:label ?ko . FILTER(LANG(?ko) = "ko") }"""
try:
    r = requests.get("https://query.wikidata.org/sparql", params={"query": Q, "format": "json"},
                     headers={**UA, "Accept": "application/sparql-results+json"}, timeout=120)
    r.raise_for_status()
    ko = {}
    for b in r.json()["results"]["bindings"]:
        ko.setdefault(b["t"]["value"].replace(".", "-"), b["ko"]["value"])
    hitf = [s for s in US if s in ko]
    res["F"] = {"US_ko": len(hitf), "examples": {s: ko[s] for s in hitf[:12]},
                "miss_examples": [s for s in US if s not in ko][:15]}
    res["_us_names"] = {s: ko[s] for s in hitf}
    print(f"F 위키데이터 한국어 이름: 미국 {len(hitf)}/{len(US)} 예 {list(res['F']['examples'].items())[:6]}")
except Exception as e:  # noqa: BLE001
    res["F"] = {"error": str(e)[:160]}
    print("F 실패", e)


# ── G. 이미 모은 기사 제목에서 이름 찾기 ─────────────────────────────
def git_json(ref, path):
    try:
        return json.loads(subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True, check=True).stdout)
    except Exception:  # noqa: BLE001
        return None


titles = []
for ref, path in (("state/nvda-state", "experiments/nvda-report/output/state/radar/news.json"),
                  ("origin/gh-pages", "news_store_home.json"),
                  ("state/report-state", "experiments/daily-report/output/state/news_stories.json")):
    d = git_json(ref, path)
    items = d.values() if isinstance(d, dict) else (d or [])
    for it in items:
        if isinstance(it, dict) and it.get("title"):
            titles.append((it["title"], (it.get("published_at") or it.get("date") or "")[:10]))
cut = str(datetime.date.today() - datetime.timedelta(days=7))
recent = [t for t, d in titles if d >= cut]
SUFFIX = re.compile(r"[,.]?\s+(Inc|Corp|Corporation|Co|Company|Ltd|plc|Holdings|Group|Incorporated|N\.V|Class [A-C])\.?$", re.I)
AMBIG = {"Target", "Visa", "Block", "Apple", "Ball", "Gap", "Oracle", "Match", "Fox", "News", "Waters", "Mosaic",
         "Corning", "Equity", "Public", "General", "United", "American", "First", "Global", "Southern"}
hits = {}
for r in uni["us"]:
    if r["sym"] in FULL:
        continue
    nm = r["name"]
    for _ in range(2):
        nm = SUFFIX.sub("", nm).strip()
    if nm in AMBIG or len(nm) < 4:
        continue
    pat = re.compile(r"\b" + re.escape(nm) + r"\b")
    n = sum(1 for t in recent if pat.search(t))
    if n:
        hits[r["sym"]] = n
kr_names = res.get("_kr_names", {})
kr_hits = {}
for r in uni["kr"]:
    if r["sym"] in FULL:
        continue
    nm = kr_names.get(r["code"])
    if not nm or len(nm) < 2:
        continue
    n = sum(1 for t in recent if nm in t)
    if n:
        kr_hits[r["sym"]] = n
res["G"] = {"titles_all": len(titles), "titles_7d": len(recent), "US_light": len(us_light), "US_hit": len(hits),
            "KR_light": len(kospi) + len(kosdaq), "KR_hit": len(kr_hits),
            "US_top": sorted(hits.items(), key=lambda x: -x[1])[:15], "KR_top": sorted(kr_hits.items(), key=lambda x: -x[1])[:10]}
print(f"G 기사 제목 7일 {len(recent)}건(전체 {len(titles)}) · 미국 간단 {len(hits)}/{len(us_light)} · 한국 간단 {len(kr_hits)}/{len(kospi) + len(kosdaq)}")
print("  미국 많이 나온 것", res["G"]["US_top"][:8])

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print("저장", OUT)
