"""간단 정보 데이터 — 853종목 종목마다 파일 하나 (2026-11-14, 기획 비공개 기획/회원-내-종목-기획.md 6-3-1 · 6-3-2).

    .venv/bin/python experiments/stock-quick/collect_quick.py --out DIR [--prev DIR] [--news FILE ...]

하루 한 번(평일 17:40 KST — 한국 장 마감 뒤, 미국은 지난밤 종가). AI 0 · Blogger 0 · 그림 0.
  1. 일봉 1년(yfinance 100개씩 묶음) — 종가 · 등락 · 52주 위치 · 평균선 · 거래량 · 1년 종가. 매일 1년 치를 새로 받으므로
     분할 · 무상증자는 야후가 고친 값이 그대로 들어온다(6-3-1).
  2. 미국 실적일 — Finnhub 실적 달력 1주씩 15번, 주 1회(_cache/earnings.json). 키는 첫 키만(price_source._key 와 같은 규칙).
  3. 미국 기사 — 이미 모은 기사 제목(--news, 상태 저장소 · gh-pages)에서 종목 이름이 정확히 나오는 것, 7일 · 3줄. AI 0.
  4. 한국 공시 — DART 공시 목록(list.json, 날짜 하나로 전 회사) 7일 · 3줄. 지분 보고 같은 잦은 공시는 뺀다.
  결과 DIR/
    version.json            기준일 · 종목 수 (발행 단계가 커밋 번호를 덧붙인다)
    bench.json              시장 지수 1년(S&P 500 · 코스피 · 코스닥) — 그래프 비교 선
    us/<티커>.json · kr/<코드>.json
    _cache/earnings.json · _cache/dart_list.json   다음 실행이 다시 쓰는 저장값
빈 값 막기: 오늘 일봉이 빈 종목은 --prev 의 전날 파일을 그대로(기준일 그대로). 받은 종목이 명단의 90% 밖이면 종료 코드 3 →
워크플로가 올리지 않는다(기록 없는 브랜치라 잘못 올리면 되돌릴 곳이 없다).
"""

import argparse
import datetime
import json
import math
import os
import re
import shutil
import sys
import time

import requests
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(EXP)
UA = {"User-Agent": "AlphaScope-quick/0.1"}
KST = datetime.timezone(datetime.timedelta(hours=9))
BENCH = {"US": ("^GSPC", "S&P 500"), "KOSPI": ("^KS11", "코스피"), "KOSDAQ": ("^KQ11", "코스닥")}
MIN_SHARE = 0.9
NEWS_DAYS, NEWS_MAX = 7, 3
sys.path.insert(0, EXP)
sys.path.insert(0, os.path.join(EXP, "stock-radar"))
sys.path.insert(0, os.path.join(EXP, "kr-stocks"))
import tech_signals as ts  # noqa: E402
sys.path.insert(0, HERE)
import render_quick as RQ  # noqa: E402


def load_env():
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.rstrip("\n").split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"\''))


def first_key(name):
    return (os.environ.get(name) or "").split(",")[0].strip()


def r4(x):
    """유효 숫자 5자리 — 파일을 작게(1년 종가 250개)."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return float(f"{x:.5g}")


def pct(a, b):
    return round((a / b - 1) * 100, 2) if a and b else None


def changes(closes, dates):
    """1일 · 1주 · 1달 · 연초 · 1년 등락(%)."""
    c = closes
    if len(c) < 2:
        return {}
    last = c[-1]
    out = {"1d": pct(last, c[-2]), "1w": pct(last, c[-6]) if len(c) > 5 else None,
           "1m": pct(last, c[-22]) if len(c) > 21 else None, "1y": pct(last, c[0]) if len(c) >= 240 else None}
    y = dates[-1][:4]
    prev_year = [v for d, v in zip(dates, c) if d[:4] < y]
    out["ytd"] = pct(last, prev_year[-1]) if prev_year else None
    return out


def series(df_one):
    """한 종목 일봉 → (날짜들, 종가들, 거래량들, 고가들, 저가들) — 종가가 빈 날은 뺀다. 고가 · 저가는 기술지표 계산에만(파일엔 안 넣음)."""
    d = df_one.dropna(subset=["Close"])
    hi = [float(v) if v == v else float(c) for v, c in zip(d["High"], d["Close"])]
    lo = [float(v) if v == v else float(c) for v, c in zip(d["Low"], d["Close"])]
    return ([str(i.date()) for i in d.index], [float(v) for v in d["Close"]], [float(v or 0) for v in d["Volume"].fillna(0)], hi, lo)


def tech(dates, c, hi, lo, market):
    """기술지표의 방향은? — 정식 종목과 같은 계산(tech_signals), 파일엔 요약만(일봉 · 주봉 · 월봉 전체 요약 + 지표 · 이동평균 개수)."""
    try:
        sig = ts.compute([{"day": d, "close": x, "high": h, "low": l} for d, x, h, l in zip(dates, c, hi, lo)], market)
    except Exception as e:  # noqa: BLE001
        print(f"[quick] 기술지표 실패: {str(e)[:80]}")
        return None
    if not sig:
        return None
    f = lambda a: {"net": round(a["net"], 3), "word": ts.word(a["net"]), "up": a["up"], "down": a["down"], "neutral": a["neutral"]} if a else None  # noqa: E731
    return {"d": f(sig["all"]), "w": f(sig.get("weekly")), "m": f(sig.get("monthly")),
            "ind": sig["counts"], "ma": sig["ma_counts"]}


def stock_file(meta, dates, c, v, hi_s, lo_s, today_by_market):
    last = c[-1]
    hi, lo = max(c[-250:]), min(c[-250:])
    ma = lambda n: sum(c[-n:]) / n if len(c) >= n else None  # noqa: E731
    m50, m200 = ma(50), ma(200)
    vol20 = sum(v[-21:-1]) / 20 if len(v) > 21 else None
    vr = (v[-1] / vol20) if vol20 else None
    status = "ok"
    if len(c) < 240:
        status = "short"   # 상장 1년 안 — 화면은 목록에만(6-3-2 ④)
    newest = today_by_market.get(meta["mk"])
    if newest and (datetime.date.fromisoformat(newest) - datetime.date.fromisoformat(dates[-1])).days > 7:
        status = "halted"  # 7일 넘게 새 봉 없음 — 거래정지로 표시
    d0 = datetime.date.fromisoformat(dates[0])
    return {
        "s": meta["sym"], "n": meta["ko"], "en": meta["en"], "m": meta["m"], "mk": meta["mk"],
        "sec": meta.get("sector"), "sub": meta.get("sub"), "full": bool(meta.get("full")),
        "d": dates[-1], "c": r4(last), "chg": changes(c, dates),
        "hi": r4(hi), "lo": r4(lo), "pos": round((last - lo) / (hi - lo), 3) if hi > lo else None,
        "off_hi": pct(last, hi), "ma50": r4(m50), "ma200": r4(m200),
        "vol": r4(v[-1]), "vol_ratio": round(vr, 2) if vr else None,
        "status": status, "tech": tech(dates, c, hi_s, lo_s, "kr" if meta["m"] == "KR" else "us"),
        "d0": dates[0], "dd": [(datetime.date.fromisoformat(x) - d0).days for x in dates], "px": [r4(x) for x in c],
    }


def download(syms):
    """100개씩 묶음 → {sym: (dates, closes, vols)}. 실패한 종목은 빠진다."""
    got = {}
    for i in range(0, len(syms), 100):
        chunk = syms[i:i + 100]
        try:
            df = yf.download(chunk, period="1y", interval="1d", group_by="ticker", auto_adjust=False,
                             threads=True, progress=False)
        except Exception as e:  # noqa: BLE001
            print(f"[quick] 묶음 {i} 실패: {str(e)[:120]}")
            continue
        for s in chunk:
            try:
                ser = series(df[s] if len(chunk) > 1 else df)
                if len(ser[1]) >= 2:
                    got[s] = ser
            except Exception:  # noqa: BLE001
                pass
        time.sleep(2)
    return got


# ── 미국 실적일 (Finnhub, 주 1회) ──────────────────────────────────
def earnings(cache_path, us_syms):
    cache = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}
    today = datetime.date.today()
    if cache.get("fetched") and (today - datetime.date.fromisoformat(cache["fetched"])).days < 7:
        return cache
    key = first_key("FINNHUB_API_KEY")
    if not key:
        print("[quick] FINNHUB_API_KEY 없음 — 실적일은 지난 값")
        return cache
    rows, calls = {}, 0
    d0 = today
    while d0 < today + datetime.timedelta(days=100):
        d1 = d0 + datetime.timedelta(days=6)
        try:
            j = requests.get("https://finnhub.io/api/v1/calendar/earnings", headers=UA, timeout=60,
                             params={"from": str(d0), "to": str(d1), "token": key}).json()
            calls += 1
            for e in j.get("earningsCalendar", []):
                sym = (e.get("symbol") or "").replace(".", "-")
                if sym in us_syms and (sym not in rows or e["date"] < rows[sym]["date"]):
                    rows[sym] = {"date": e["date"], "hour": e.get("hour") or ""}
        except Exception as e:  # noqa: BLE001
            print(f"[quick] Finnhub {d0} 실패: {str(e)[:80]}")
        d0 = d1 + datetime.timedelta(days=1)
        time.sleep(1.1)
    if len(rows) < len(cache.get("rows", {})) * 0.7:   # 크게 줄면 지난 값 유지
        print(f"[quick] 실적일 {len(rows)}건 — 지난 {len(cache.get('rows', {}))}건보다 크게 적어 지난 값 유지")
        return cache
    cache = {"fetched": str(today), "calls": calls, "rows": rows}
    print(f"[quick] 실적일 {len(rows)}종목 · Finnhub {calls}번")
    return cache


# ── 미국 기사 이름 찾기 (AI 0) ─────────────────────────────────────
SUFFIX = re.compile(r"[,.]?\s+(Inc|Corp|Corporation|Co|Company|Ltd|plc|Holdings|Group|Incorporated|N\.V|Class [A-C])\.?$", re.I)
AMBIG = {"Target", "Visa", "Block", "Apple", "Ball", "Gap", "Oracle", "Match", "Fox", "News", "Waters", "Mosaic", "Corning",
         "Equity", "Public", "General", "United", "American", "First", "Global", "Southern", "Progressive", "Republic",
         "Regions", "Principal", "Copart", "Dover", "Textron", "Masco", "Snap-on", "Loews", "Pool", "Insulet"}


NOISE = re.compile(r"\bETF\b|SPDR|iShares|xStock|Live Charts|Marketcap|Price Prediction|\bcrypto|Coinbase", re.I)   # ETF 이름 · 코인 시세 페이지에 회사 이름이 섞인 제목


def load_titles(paths):
    out = []
    for p in paths or []:
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            print(f"[quick] 기사 파일 못 읽음: {p}")
            continue
        items = d.values() if isinstance(d, dict) else d
        for it in items:
            if isinstance(it, dict) and it.get("title") and it.get("url") and not NOISE.search(it["title"]):
                out.append({"t": it["title"], "u": it["url"], "src": it.get("source") or "",
                            "d": (it.get("published_at") or it.get("date") or "")[:10]})
    seen, uniq = set(), []
    for it in sorted(out, key=lambda x: x["d"], reverse=True):
        if it["t"] not in seen:
            seen.add(it["t"])
            uniq.append(it)
    return uniq


def news_for(name_en, titles, cut):
    nm = name_en
    for _ in range(2):
        nm = SUFFIX.sub("", nm).strip()
    nm = re.sub(r"\s*\(.*?\)$", "", nm)
    if nm in AMBIG or len(nm) < 4:
        return []
    pat = re.compile(r"\b" + re.escape(nm) + r"\b")
    return [t for t in titles if t["d"] >= cut and pat.search(t["t"])][:NEWS_MAX]


# ── 한국 공시 (DART 공시 목록) ─────────────────────────────────────
SKIP_DISC = re.compile(r"소유상황보고서|임원ㆍ주요주주|주식등의대량보유|최대주주등소유주식|자기주식취득결과보고서|증권발행실적보고서|기업설명회")


def dart_list(cache_path, codes):
    cache = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {"days": {}}
    key = first_key("DART_API_KEY")
    today = datetime.datetime.now(KST).date()
    want = [today - datetime.timedelta(days=i) for i in range(NEWS_DAYS + 1)]
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
                j = requests.get("https://opendart.fss.or.kr/api/list.json", timeout=60,
                                 params={"crtfc_key": key, "bgn_de": ds, "end_de": ds, "page_no": page, "page_count": 100}).json()
                calls += 1
            except Exception as e:  # noqa: BLE001
                print(f"[quick] DART 목록 {ds} 실패: {str(e)[:80]}")
                rows = None
                break
            if j.get("status") not in ("000", "013"):   # 013 = 자료 없음
                print(f"[quick] DART 목록 {ds}: {j.get('status')} {j.get('message')}")
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
    print(f"[quick] DART 공시 목록 {calls}번 · 우리 종목 공시 {sum(len(v) for v in cache['days'].values())}건(7일)")
    return cache


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--prev", default="")
    ap.add_argument("--news", nargs="*", default=[])
    ap.add_argument("--limit", type=int, default=0, help="시험용 — 시장마다 앞 N종목만")
    a = ap.parse_args()

    ref = json.load(open(os.path.join(EXP, "ref", "quick_ref.json"), encoding="utf-8"))
    metas = []
    for sym, e in ref["us"].items():
        metas.append({"sym": sym, "m": "US", "mk": "US", "ko": e["ko"], "en": e["en"], "sector": e.get("sector"),
                      "sub": e.get("sub"), "full": e.get("full"), "dir": "us", "file": sym})
    for sym, e in ref["kr"].items():
        metas.append({"sym": sym, "m": "KR", "mk": e["market"], "ko": e["ko"], "en": e["en"], "sector": e.get("sector"),
                      "sub": e.get("sub_ours") or e.get("sub"), "full": e.get("full"), "dir": "kr", "file": sym.split(".")[0]})
    if a.limit:
        metas = [m for m in metas if m["m"] == "US"][:a.limit] + [m for m in metas if m["m"] == "KR"][:a.limit]
    out = a.out
    if os.path.exists(out):
        shutil.rmtree(out)
    for d in ("us", "kr", "_cache"):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    prev = a.prev if a.prev and os.path.isdir(a.prev) else ""

    t0 = time.time()
    syms = [m["sym"] for m in metas]
    bench_syms = [v[0] for v in BENCH.values()]
    got = download(syms + bench_syms)
    secs = round(time.time() - t0)
    newest = {}
    for m in metas:
        if m["sym"] in got:
            d = got[m["sym"]][0][-1]
            newest[m["mk"]] = max(newest.get(m["mk"], ""), d)

    # 시장 지수
    bench = {}
    for mk, (bs, bn) in BENCH.items():
        if bs in got:
            dates, c = got[bs][0], got[bs][1]
            d0 = datetime.date.fromisoformat(dates[0])
            bench[mk] = {"s": bs, "n": bn, "d": dates[-1], "chg": changes(c, dates), "d0": dates[0],
                         "dd": [(datetime.date.fromisoformat(x) - d0).days for x in dates], "px": [r4(x) for x in c]}
    json.dump(bench, open(os.path.join(out, "bench.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    # 덧붙일 것 — 실적일 · 기사 · 공시
    us_syms = {m["sym"] for m in metas if m["m"] == "US"}
    kr_codes = {m["file"] for m in metas if m["m"] == "KR"}
    for name in ("earnings.json", "dart_list.json"):
        if prev and os.path.exists(os.path.join(prev, "_cache", name)):
            shutil.copy(os.path.join(prev, "_cache", name), os.path.join(out, "_cache", name))
    earn = earnings(os.path.join(out, "_cache", "earnings.json"), us_syms)
    json.dump(earn, open(os.path.join(out, "_cache", "earnings.json"), "w", encoding="utf-8"), ensure_ascii=False)
    titles = load_titles(a.news)
    cut = str(datetime.date.today() - datetime.timedelta(days=NEWS_DAYS))
    disc = dart_list(os.path.join(out, "_cache", "dart_list.json"), kr_codes)
    json.dump(disc, open(os.path.join(out, "_cache", "dart_list.json"), "w", encoding="utf-8"), ensure_ascii=False)
    disc_by = {}
    for day in sorted(disc["days"], reverse=True):
        for it in disc["days"][day]:
            disc_by.setdefault(it["c"], []).append(it)

    full = RQ.full_index(ref)
    fresh = carried = missing = 0
    stats = {"short": 0, "halted": 0, "earn": 0, "news": 0, "disc": 0}
    for m in metas:
        path = os.path.join(out, m["dir"], m["file"] + ".json")
        if m["sym"] in got:
            dates, c, v, hi_s, lo_s = got[m["sym"]]
            f = stock_file(m, dates, c, v, hi_s, lo_s, newest)
            fresh += 1
        elif prev and os.path.exists(os.path.join(prev, m["dir"], m["file"] + ".json")):
            f = json.load(open(os.path.join(prev, m["dir"], m["file"] + ".json"), encoding="utf-8"))
            f["carried"] = True   # 오늘 못 받아 전날 값 — 기준일이 다르게 보인다
            carried += 1
        else:
            missing += 1
            continue
        if m["m"] == "US":
            e = earn.get("rows", {}).get(m["sym"])
            f["earn"] = e if e and e["date"] >= str(datetime.date.today()) else None
            f["news"] = [] if m.get("full") else news_for(m["en"], titles, cut)
        else:
            f["disc"] = [{"t": x["t"], "d": f"{x['d'][:4]}-{x['d'][4:6]}-{x['d'][6:]}",
                          "u": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={x['no']}"} for x in disc_by.get(m["file"], [])[:NEWS_MAX]]
        stats["short"] += f.get("status") == "short"
        stats["halted"] += f.get("status") == "halted"
        stats["earn"] += bool(f.get("earn"))
        stats["news"] += bool(f.get("news"))
        stats["disc"] += bool(f.get("disc"))
        json.dump(f, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        try:   # 화면 조각 — 고정 페이지 stock-quick 이 끼워 넣는다(render_quick)
            open(path[:-5] + ".html", "w", encoding="utf-8").write(RQ.render(f, bench, full))
        except Exception as e:  # noqa: BLE001
            stats["render_fail"] = stats.get("render_fail", 0) + 1
            print(f"[quick] 화면 조각 실패 {m['sym']}: {str(e)[:100]}")

    total = len(metas)
    sizes = [os.path.getsize(os.path.join(out, d, x)) for d in ("us", "kr") for x in os.listdir(os.path.join(out, d)) if x.endswith(".json")]
    hsizes = [os.path.getsize(os.path.join(out, d, x)) for d in ("us", "kr") for x in os.listdir(os.path.join(out, d)) if x.endswith(".html")]
    version = {"built": datetime.datetime.now(KST).isoformat(timespec="minutes"), "date": newest,
               "n": total, "fresh": fresh, "carried": carried, "missing": missing}
    json.dump(version, open(os.path.join(out, "version.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[quick] 일봉 {secs}초 · 받음 {fresh}/{total} · 전날 값 {carried} · 없음 {missing} · 기준일 {newest}")
    print(f"[quick] 1년 미만 {stats['short']} · 거래정지 {stats['halted']} · 실적일 {stats['earn']} · 기사 {stats['news']} · 공시 {stats['disc']}")
    if sizes:
        print(f"[quick] 종목 파일 평균 {sum(sizes) // len(sizes)}B · 최대 {max(sizes)}B · 합계 {sum(sizes) // 1024}KB")
    if hsizes:
        print(f"[quick] 화면 조각 {len(hsizes)}개 평균 {sum(hsizes) // len(hsizes) // 1024}KB · 합계 {sum(hsizes) // 1024 // 1024}MB · 실패 {stats.get('render_fail', 0)}")
    if fresh < total * MIN_SHARE:
        print(f"[quick] 받은 종목이 {MIN_SHARE:.0%} 밖 — 올리지 않는다")
        sys.exit(3)


if __name__ == "__main__":
    main()
