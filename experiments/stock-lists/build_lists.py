"""하단 메뉴 `종목` 페이지(/p/stock-lists.html)가 읽는 목록 파일 — 시장마다 <out>/us/_lists.json · <out>/kr/_lists.json (2026-11-17 사용자 "1단계 구현 진행해").
기획 = 비공개 기획/종목-탭-그룹-목록-기획.md 3-1. 목업 = mock_stock_lists.py.

    python experiments/stock-lists/build_lists.py --qd /tmp/qd --cache /tmp/qcache --search /tmp/search --shells /tmp/qd/shells.json

간단 종목 실행(quick-data.yml)이 수집 직후 돌린다 → /tmp/qd/<시장>/ 에 쓰므로 같은 Pages 배포(/us/_lists.json)와 quick-us · quick-kr 브랜치에 그대로 실린다.
새 수집 · AI · Blogger · gh-pages 쓰기 0 — 이미 있는 값만 합친다:
  /tmp/qd/<시장>/<코드>.json    간단 종목 가격 요약(collect_quick.stock_file): 종가 · 등락 · 거래량 배수 · 52주 고가 대비 · 업종
  /tmp/qcache/kr/cap_rank.json   한국 시가총액(DART 주식 수 × 종가)
  /tmp/qcache/detail_cache.json  미국 간단 종목 기업 정보의 주식 수(야후 sharesOutstanding, 90일 주기) → 시가총액 = 주식 수 × 종가
  /tmp/search/<시장>.json        정식 검색 색인(gh-pages search/) — S&P 500 · 코스피 200 · 코스닥 150 밖 정식 종목(테마 묶음의 TSM · 아이온큐 등) · 정식 시가총액 · ETF
기계용 파일이라 자르지 않고 전부 싣는다(화면은 10개씩 — 받는 쪽이 고른다). 한 줄 = {t 코드, n 이름, s 업종, p 종가, r 등락률, v 거래량 배수, h 52주 고가 대비 %, c 시가총액, u 주소(경로만), lg 로고 파일}.
"""
import argparse
import json
import os
import sys
import urllib.request
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [EXP, os.path.join(EXP, "stock-radar"), os.path.join(EXP, "kr-stocks")]
import taxonomy  # noqa: E402
import universe as U  # noqa: E402
import universe_kr as UK  # noqa: E402

SKIP = {"version.json", "bench.json", "_lists.json"}

# 업종 = GICS 11개만 (taxonomy 세 층). 정식 검색 색인의 옛 분류(`반도체` · `결제` …)는 업종으로 올린다 — 간단 명단 밖 정식 종목(TSMC · ASML)이
# `반도체` 업종 칸을 따로 만들어 홈 `업종 종목` 반도체에 2종목만 보였다 (2026-11-18 사용자 "반도체는 딸랑 두 개뿐이야?")
SECTOR_NAMES = set(taxonomy.SECTORS.values())
SECTOR_ALIAS = {name: taxonomy.SECTORS[parent] for name, parent in taxonomy.SUB_INDUSTRIES.values()}
SECTOR_ALIAS.update({"결제": "금융", "빅테크": "기술", "소비 · 플랫폼": "경기 소비재"})


def sector11(name):
    """업종 이름 → GICS 11 중 하나. 모르는 이름은 `기타` (목록이 업종 칸을 새로 만들지 않게)."""
    if name in SECTOR_NAMES:
        return name
    return SECTOR_ALIAS.get(name or "", "기타")


def _load(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _path(url):
    """https://www.newfact.app/p/x.html → /p/x.html (블로그 안 주소만 — 파일이 작아지고, 폰 주소 ?m=1 에서도 같은 블로그로 간다)."""
    if not url:
        return None
    u = urlparse(url)
    return u.path + (("?" + u.query) if u.query else "")


def _r(x, n=2):
    return None if x is None else round(float(x), n)


def themes(m):
    """묶음 = 홈 `테마 종목`과 같은 표(universe WATCH) + 미국은 taxonomy.THEMES. 종목은 줄의 t(접미사 없는 코드)로."""
    if m == "us":
        g = [[n, list(syms)] for n, syms in U.WATCH] + [[t["name"], list(t["members"])] for t in taxonomy.THEMES.values()]
    else:
        g = [[n.replace(" · ", "·"), list(syms)] for n, syms in UK.WATCH]
    return [[n, [s.split(".")[0] for s in syms]] for n, syms in g]


DATA_URL = "https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages/data.json"   # 미국 데일리 실행(07:30)이 올리는 지수 · 대형주 · 업종 ETF


def _get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "alpha-scope/lists"}), timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[lists] 못 받음 {url.rsplit('/', 1)[-1]}: {e}")
        return None


def sector_etf(day, data=None):
    """미국 업종 11개 = 섹터 ETF(XLK · XLF …) 등락 {업종 이름: %} — 증시 시황 아침 편 업종 줄(build_briefing.build_am)과 같은 값 (2026-11-20 사용자).
    업종 탭 지도 색 · 숫자가 이것을 쓴다(옛 = 종목 단순 평균 → 11-19 기술 −1.50 · 시황 −2.75). 장 날짜가 목록과 다르거나 못 받으면 {} (화면은 단순 평균)."""
    names = {n.replace(" ", ""): n for n in SECTOR_NAMES}   # data.json `경기소비재` → 목록 `경기 소비재`
    if data is None and day:
        # 먼저 시황 아침 편 묶음(briefing/{미국 장 다음 날}-am.json) — 시황 업종 줄 그 숫자. data.json 은 묶음 뒤에도 고쳐져(11-20 10:49) 0.01 씩 어긋난다
        import datetime
        key = (datetime.date.fromisoformat(day) + datetime.timedelta(days=1)).isoformat()   # 금요일 장 → 토요일 묶음(토요일 실행이 만든다)
        br = _get(DATA_URL.replace("data.json", f"briefing/{key}-am.json"))
        if br and br.get("trade_date") == day and (br.get("close") or {}).get("sectors"):
            out = {names[x["name"].replace(" ", "")]: x["chg_pct"] for x in br["close"]["sectors"]
                   if x.get("chg_pct") is not None and (x.get("name") or "").replace(" ", "") in names}
            if out:
                print(f"[lists] 업종 ETF = 시황 묶음 {key}-am ({len(out)}개)")
                return out
    if data is None:
        data = _get(DATA_URL)
        if not data:
            return {}
    if not day or data.get("trade_date") != day:
        print(f"[lists] data.json 날짜 {data.get('trade_date')} ≠ 목록 {day} — 업종 ETF 없이")
        return {}
    return {names[s["name"].replace(" ", "")]: _r(s["cp"]) for s in data.get("sectors") or []
            if s.get("cp") is not None and (s.get("name") or "").replace(" ", "") in names}


def build(m, qd, cache, search, shells, logos):
    rows = {}
    folder = os.path.join(qd, m)
    for f in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not f.endswith(".json") or f in SKIP:
            continue
        d = _load(os.path.join(folder, f))
        if not d or not d.get("c") or d.get("status") == "halted":
            continue
        code = f[:-5]
        rows[d["s"]] = {"t": code, "n": d.get("n") or code, "s": sector11(d.get("sec")), "p": d["c"], "r": _r((d.get("chg") or {}).get("1d")),
                        "v": _r(d.get("vol_ratio")), "h": _r(d.get("off_hi")), "d": d.get("d"), "u": _path(shells.get(code))}
    # 정식 검색 색인 — 정식 주소 · 시가총액, 간단 명단 밖 정식 종목은 줄을 새로
    idx = _load(os.path.join(search, f"{m}.json"), {}) or {}
    for s in idx.get("stocks", []):
        p = s.get("p") or {}
        row = rows.get(s["s"])
        if row is None and p.get("c"):
            row = rows[s["s"]] = {"t": s["s"].split(".")[0], "n": s["n"], "s": sector11(s.get("sec")), "p": p["c"], "r": _r(p.get("chg")),
                                  "v": _r(p["v"] / p["va"]) if p.get("va") and p.get("v") else None,
                                  "h": _r((p["c"] / p["h52"][0] - 1) * 100) if p.get("h52") else None, "d": p.get("d")}
        if row is not None:
            row["u"] = _path(s.get("u"))
            if s.get("cap"):
                row["c"] = s["cap"]
    # 시가총액 — 한국 = cap_rank(정식 · 간단 같은 셈), 미국 간단 = 주식 수 × 종가
    if m == "kr":
        for sym, x in ((_load(os.path.join(cache, "kr", "cap_rank.json"), {}) or {}).get("caps") or {}).items():
            if sym in rows and x.get("cap"):
                rows[sym]["c"] = x["cap"]
    else:
        st = (_load(os.path.join(cache, "detail_cache.json"), {}) or {}).get("stocks") or {}
        for sym, row in rows.items():
            sh = ((st.get(sym) or {}).get("company") or {}).get("v") or {}
            if not row.get("c") and isinstance(sh, dict) and sh.get("shares"):
                row["c"] = sh["shares"] * row["p"]
    out = []
    for sym, row in rows.items():
        if row.get("c"):
            row["c"] = round(row["c"])
        lg = logos.get(sym.upper())
        if lg:
            row["lg"] = lg["file"]
        if not row.get("u"):
            row.pop("u", None)   # 화면이 /p/stock.html?s=코드 로
        out.append({k: v for k, v in row.items() if v is not None and k != "d"})
    etf = []
    for e in idx.get("etfs", []):
        p = e.get("p") or {}
        if p.get("c"):
            x = {"t": e["s"].split(".")[0], "n": e["n"], "s": e.get("tr") or "", "p": p["c"], "r": _r(p.get("chg")), "u": _path(e.get("u"))}
            lg = logos.get(e["s"].upper())
            if lg:
                x["lg"] = lg["file"]
            etf.append({k: v for k, v in x.items() if v is not None})
    day = max((r.get("d") or "" for r in rows.values()), default="")
    doc = {"m": m, "d": day, "rows": sorted(out, key=lambda r: -(r.get("c") or 0)), "themes": themes(m), "etf": etf,
           "note": "종목 페이지 목록용 — experiments/stock-lists/build_lists.py"}
    if m == "us":
        sec = sector_etf(day)
        if sec:
            doc["sec_etf"] = sec
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qd", required=True, help="간단 종목 결과 폴더(us/ · kr/) — 여기 <시장>/_lists.json 으로 쓴다")
    ap.add_argument("--cache", default="", help="간단 종목 저장값(quick-state)")
    ap.add_argument("--search", default="", help="정식 검색 색인 폴더(us.json · kr.json)")
    ap.add_argument("--shells", default="", help="간단 종목 전용 페이지 주소표 {코드: 주소}")
    ap.add_argument("--out", default="", help="쓰는 폴더(기본 = --qd)")
    a = ap.parse_args()
    shells = _load(a.shells, {}) or {} if a.shells else {}
    logos = (_load(os.path.join(EXP, "ref", "ticker_logos.json"), {}) or {}).get("logos") or {}
    for m in ("us", "kr"):
        doc = build(m, a.qd, a.cache, a.search, shells, logos)
        if len(doc["rows"]) < 50:   # 자료가 덜 받아진 날 — 쓰지 않는다(전날 파일 · 화면 안내)
            print(f"::warning::[lists] {m} 종목 {len(doc['rows'])}개 — 쓰지 않음")
            continue
        out = os.path.join(a.out or a.qd, m, "_lists.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        print(f"[lists] {m} {doc['d']} 종목 {len(doc['rows'])} · 시총 {sum(1 for r in doc['rows'] if r.get('c'))} · 주소 {sum(1 for r in doc['rows'] if r.get('u'))}"
              f" · 묶음 {len(doc['themes'])} · ETF {len(doc['etf'])} · {os.path.getsize(out) / 1024:.0f}KB")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
