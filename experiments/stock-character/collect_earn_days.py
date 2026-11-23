"""종목 특성 2단계 자료 — 853종목 실적일 (2026-11-23 사용자, 전제 = 비공개 alphascope-docs/doc/검증/종목-특성-2단계-검증.md 3절).

실적일 = 그 분기 숫자가 처음 공개된 공시.
  미국: SEC EDGAR 8-K 2.02항(실적 발표) 접수 시각. 없는 분기는 10-Q · 10-K 제출 시각.
        접수가 16:00(미 동부) 뒤면 반응 날 = 다음 거래일(after_close = 1), 아니면 그날.
  한국: DART 잠정실적(`영업(잠정)실적`) → 손익구조 변동 공시(`매출액또는손익구조`) → 분기 · 반기 · 사업보고서 가운데 가장 이른 것.
        DART 에는 접수 시각이 없다 → 반응 창 = 공시일 당일 + 다음 거래일(이틀 창, 검증 스크립트가 처리).
한 분기 첫 발표만: 앞선 실적일 뒤 40일 안의 것은 뺀다(kr-stocks/collect_kr_earn_dart.py 와 같은 규칙).
정정 공시([기재정정] 등)는 뺀다.

    python experiments/stock-character/collect_earn_days.py --market us            # 미국 전부
    python experiments/stock-character/collect_earn_days.py --market kr            # 한국 전부
    python experiments/stock-character/collect_earn_days.py --market us --only AAPL,KO   # 시험

원본(회사별 공시 목록) = data/store/character/earn_raw/{us,kr}/종목.json — 있으면 다시 받지 않는다(--refresh 로 다시).
결과 = data/store/character/earn_days_{us,kr}.csv (깃 밖): sym, day(공시일), kind, after_close, period, accepted
AI 0 · 로컬 한 번. 부르는 횟수: EDGAR 회사당 1 + 옛 목록 파일 수(초당 5회로 늦춤) · DART 회사당 공시 유형 둘 × 쪽수(키당 하루 2만 회).
EDGAR 는 연락처가 든 User-Agent 가 필요하다(없으면 403) — 환경 변수 또는 .env 의 EDGAR_USER_AGENT(이름 + 블로그 문의 메일).
"""

import argparse
import csv
import datetime
import json
import os
import re
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
STORE = os.path.join(ROOT, "data", "store", "character")
RAW = os.path.join(STORE, "earn_raw")
START = "2005-01-01"
GAP_DAYS = 40                  # 앞선 실적일 뒤 40일 안의 발표는 같은 분기 것으로 보고 뺀다
CALLS = {"edgar": 0, "dart": 0}


def universe():
    u = json.load(open(os.path.join(ROOT, "experiments", "ref", "universe_all.json"), encoding="utf-8"))
    ref = json.load(open(os.path.join(ROOT, "experiments", "ref", "quick_ref.json"), encoding="utf-8"))
    us = [r["sym"] for r in u["us"]]
    kr = {r["sym"]: ref["kr"].get(r["sym"], {}).get("corp") for r in u["kr"]}
    return us, kr


def _day(s):
    return datetime.date.fromisoformat(s[:10])


def first_only(events):
    """날짜 순으로 보며 앞선 것 뒤 40일 안이면 뺀다. events = [{day, ...}] (day = YYYY-MM-DD)."""
    keep = []
    for e in sorted(events, key=lambda x: (x["day"], x.get("accepted", ""))):
        if keep and (_day(e["day"]) - _day(keep[-1]["day"])).days < GAP_DAYS:
            continue
        keep.append(e)
    return keep


# ─── 미국: EDGAR ────────────────────────────────────────────────────────
def _env(name):
    """환경 변수 → 없으면 저장소 .env 의 같은 이름 줄."""
    v = os.environ.get(name, "").strip()
    env = os.path.join(ROOT, ".env")
    if not v and os.path.exists(env):
        for line in open(env, encoding="utf-8"):
            if line.startswith(name + "="):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
    return v


def edgar_get(url):
    ua = _env("EDGAR_USER_AGENT")
    if not ua:
        raise SystemExit("EDGAR_USER_AGENT 없음 — .env 에 `EDGAR_USER_AGENT=이름 문의메일` (SEC 는 연락처 없는 요청을 거절한다)")
    for wait in (0, 2, 10):
        time.sleep(0.2 + wait)                       # 초당 5회 아래(SEC 한도 초당 10회)
        CALLS["edgar"] += 1
        r = requests.get(url, headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}, timeout=30)
        if r.status_code == 200:
            return r.json()
        if r.status_code not in (429, 503):
            break
    raise RuntimeError(f"EDGAR {r.status_code} {url}")


def us_cik_map():
    path = os.path.join(RAW, "us_cik.json")
    if not os.path.exists(path):
        d = edgar_get("https://www.sec.gov/files/company_tickers.json")
        m = {v["ticker"].upper(): int(v["cik_str"]) for v in d.values()}
        os.makedirs(RAW, exist_ok=True)
        json.dump(m, open(path, "w"))
    return json.load(open(path))


def us_raw(sym, cik, refresh):
    """회사 공시 목록에서 8-K · 10-Q · 10-K 줄만 추려 원본으로 둔다."""
    path = os.path.join(RAW, "us", f"{sym}.json")
    if os.path.exists(path) and not refresh:
        return json.load(open(path))
    sub = edgar_get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    blocks = [sub["filings"]["recent"]]
    for f in sub["filings"].get("files", []):
        if f.get("filingTo", "9999") < START:        # 2005 전 묶음은 안 받는다
            continue
        blocks.append(edgar_get(f"https://data.sec.gov/submissions/{f['name']}"))
    rows = []
    for b in blocks:
        for form, filed, acc, items, rep, no in zip(b["form"], b["filingDate"], b["acceptanceDateTime"], b["items"], b["reportDate"], b["accessionNumber"]):
            if form in ("8-K", "10-Q", "10-K") and filed >= START:
                rows.append({"form": form, "filed": filed, "accepted_utc": acc, "items": items or "", "report": rep or "", "acc": no})
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump({"cik": cik, "rows": rows}, open(path, "w"))
    return {"cik": cik, "rows": rows}


def _et(utc):
    """EDGAR acceptanceDateTime(UTC) → 미 동부 시각. 서머타임은 3월 둘째 일요일 ~ 11월 첫째 일요일(2007 ~), 그 전은 4월 첫째 ~ 10월 마지막 일요일."""
    t = datetime.datetime.fromisoformat(utc.replace("Z", "").split(".")[0])
    y = t.year

    def nth_sunday(month, n):
        d = datetime.date(y, month, 1)
        d += datetime.timedelta(days=(6 - d.weekday()) % 7)
        return d + datetime.timedelta(weeks=n - 1)

    if y >= 2007:
        a, b = nth_sunday(3, 2), nth_sunday(11, 1)
    else:
        last = datetime.date(y, 10, 31)
        a, b = nth_sunday(4, 1), last - datetime.timedelta(days=(last.weekday() + 1) % 7)
    dst = datetime.datetime(a.year, a.month, a.day, 7) <= t < datetime.datetime(b.year, b.month, b.day, 6)
    return t - datetime.timedelta(hours=4 if dst else 5)


def us_events(raw):
    ev = []
    for r in raw["rows"]:
        et = _et(r["accepted_utc"])
        e = {"day": et.date().isoformat(), "accepted": et.strftime("%Y-%m-%dT%H:%M"), "after_close": int(et.hour >= 16), "period": r["report"]}
        if r["form"] == "8-K" and "2.02" in r["items"]:
            ev.append({**e, "kind": "8k202"})
        elif r["form"] in ("10-Q", "10-K"):
            ev.append({**e, "kind": r["form"].lower().replace("-", "")})
    rel = first_only([e for e in ev if e["kind"] == "8k202"])
    out = list(rel)
    for rep in [e for e in ev if e["kind"] != "8k202"]:
        # 그 분기 끝(period) 뒤 ~ 보고서 제출일 사이에 실적 발표 공시가 있으면 그것이 첫 공개 — 없을 때만 보고서 날을 쓴다
        lo = rep["period"] or (_day(rep["day"]) - datetime.timedelta(days=100)).isoformat()
        if not any(lo < x["day"] <= rep["day"] for x in rel):
            out.append(rep)
    return first_only(out)


# ─── 한국: DART ─────────────────────────────────────────────────────────
def dart_key():
    k = _env("DART_API_KEY")
    if not k:
        raise SystemExit("DART_API_KEY 없음")
    return k


def dart_list(key, corp, ty):
    out, page = [], 1
    while True:
        time.sleep(0.2)
        CALLS["dart"] += 1
        r = requests.get("https://opendart.fss.or.kr/api/list.json", timeout=30, params=dict(
            crtfc_key=key, corp_code=corp, bgn_de=START.replace("-", ""), end_de=datetime.date.today().strftime("%Y%m%d"),
            pblntf_ty=ty, page_no=page, page_count=100)).json()
        if r.get("status") == "013":                 # 조회된 데이터 없음
            break
        if r.get("status") != "000":
            raise RuntimeError(f"DART {r.get('status')} {r.get('message')}")
        out += [{"nm": x["report_nm"], "dt": x["rcept_dt"]} for x in r.get("list", [])]
        if page >= int(r.get("total_page", 1)):
            break
        page += 1
    return out


def kr_raw(sym, corp, key, refresh):
    path = os.path.join(RAW, "kr", f"{sym}.json")
    if os.path.exists(path) and not refresh:
        return json.load(open(path))
    d = {"corp": corp, "A": dart_list(key, corp, "A"), "I": dart_list(key, corp, "I")}   # A = 정기공시 · I = 거래소공시
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(d, open(path, "w"), ensure_ascii=False)
    return d


_PERIOD = re.compile(r"\((\d{4})\.(\d{2})\)")


def kr_events(raw):
    iso = lambda s: f"{s[:4]}-{s[4:6]}-{s[6:]}"
    fixed = lambda nm: "정정" in nm.split("]")[0] if nm.startswith("[") else False
    reports = []
    for x in raw["A"]:
        m = _PERIOD.search(x["nm"])
        if m and not fixed(x["nm"]) and any(k in x["nm"] for k in ("분기보고서", "반기보고서", "사업보고서")):
            y, mo = int(m.group(1)), int(m.group(2))
            end = (datetime.date(y + mo // 12, mo % 12 + 1, 1) - datetime.timedelta(days=1)).isoformat()
            reports.append({"day": iso(x["dt"]), "kind": "report", "after_close": "", "period": end, "accepted": ""})
    early = []
    for x in raw["I"]:
        if fixed(x["nm"]):
            continue
        if "영업(잠정)실적" in x["nm"]:
            early.append({"day": iso(x["dt"]), "kind": "prelim", "cons": "연결재무제표기준" in x["nm"]})
        elif "매출액또는손익구조" in x["nm"]:
            early.append({"day": iso(x["dt"]), "kind": "change30", "cons": True})
    out, used = [], set()
    for rep in sorted(reports, key=lambda e: e["day"]):
        cand = [e for e in early if rep["period"] < e["day"] <= rep["day"]]
        if any(e["cons"] for e in cand):             # 연결 기준이 있으면 그것만 — 현대차 · 기아의 연결 아닌 잠정실적은 매달 판매 실적이다
            cand = [e for e in cand if e["cons"]]
        if cand:
            e = min(cand, key=lambda z: z["day"])
            used.add(e["day"])
            out.append({"day": e["day"], "kind": e["kind"], "after_close": "", "period": rep["period"], "accepted": ""})
        else:
            out.append(rep)
    if reports:                                      # 마지막 보고서 뒤에 나온 잠정실적(보고서가 아직 안 나온 최근 분기)
        last = max(r["day"] for r in reports)
        tail = [e for e in early if e["day"] > last]
        if any(e["cons"] for e in tail):
            tail = [e for e in tail if e["cons"]]
        out += [{"day": e["day"], "kind": e["kind"], "after_close": "", "period": "", "accepted": ""} for e in tail]
    return first_only(out)


# ─── 실행 ───────────────────────────────────────────────────────────────
def coverage(rows, market):
    """채움률 — 해마다 종목당 실적일 수(분기 4회 기준)와 공시 종류."""
    by = {}
    for r in rows:
        y = r["day"][:4]
        b = by.setdefault(y, {"syms": set(), "n": 0, "kinds": {}})
        b["syms"].add(r["sym"]); b["n"] += 1
        b["kinds"][r["kind"]] = b["kinds"].get(r["kind"], 0) + 1
    print(f"\n[{market}] 채움률 — 해 · 실적일 잡힌 종목 수 · 종목당 실적일 수 · 종류")
    for y in sorted(by):
        b = by[y]
        print(f"  {y}  {len(b['syms']):4d}종목  {b['n'] / len(b['syms']):.2f}회  {dict(sorted(b['kinds'].items()))}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=["us", "kr"], required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    us, kr = universe()
    only = [s.strip() for s in a.only.split(",") if s.strip()]
    rows, miss = [], []
    if a.market == "us":
        ciks = us_cik_map()
        for i, sym in enumerate(only or us):
            cik = ciks.get(sym.upper().replace(".", "-"))
            if not cik:
                miss.append(sym); continue
            try:
                ev = us_events(us_raw(sym, cik, a.refresh))
            except Exception as e:
                miss.append(f"{sym}({e})"); continue
            rows += [{"sym": sym, **e} for e in ev]
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}종목 · EDGAR {CALLS['edgar']}회", flush=True)
    else:
        key = dart_key()
        for i, sym in enumerate(only or sorted(kr)):
            corp = kr.get(sym)
            if not corp:
                miss.append(sym); continue
            try:
                ev = kr_events(kr_raw(sym, corp, key, a.refresh))
            except Exception as e:
                miss.append(f"{sym}({e})"); continue
            rows += [{"sym": sym, **e} for e in ev]
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}종목 · DART {CALLS['dart']}회", flush=True)
    coverage(rows, a.market)
    print(f"\n부른 횟수 EDGAR {CALLS['edgar']} · DART {CALLS['dart']} · 못 받은 종목 {len(miss)}: {miss[:20]}")
    if only:
        for r in rows[-12:]:
            print("  ", r)
        print("(시험 — 파일로 쓰지 않음)")
        return
    os.makedirs(STORE, exist_ok=True)
    out = os.path.join(STORE, f"earn_days_{a.market}.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sym", "day", "kind", "after_close", "period", "accepted"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["sym"], r["day"])))
    print(f"저장 {out} ({len(rows)}줄)")


if __name__ == "__main__":
    main()
