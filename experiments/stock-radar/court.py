"""소송 일정 — 모든 미국 종목 (2026-11-01 사용자 P270, 엔비디아 리포트 소송 카드를 넓힘).

엔비디아 기준 그대로 : 종결 안 된 증권 소송(주주 집단소송 등) 중 회사가 피고인 사건만 추적한다. 특허 · 계약은 보지 않는다. AI 없음.
  1. 조사 (사람 손) — `python court.py --survey` : 종목마다 CourtListener 검색 → court_survey.md 후보 표(종목마다 바로 저장, 끊기면 이어서).
     사람이 확인해 court_watch.json 에 적는다 (저장소에 커밋 — 우리가 고른 목록이라 다시 모을 수 없다).
  2. 매일 — fetch() : 추적 사건의 최신 법원 문서 20건에서 `... set for 날짜` 결정 일정만 뽑는다 (nvda-report cases_watch 규칙 그대로).
     뽑은 미래 일정은 data/court.json 에 쌓는다 (최근 문서 20건 밖으로 밀려난 일정도 남게). 상태 브랜치 radar/ 에 보관.
  3. card(sym, day) → {"cases": [{name, label, day, left}]} — render_html.cal_court 가 그린다.
"""

import datetime
import json
import os
import re
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "nvda-report"))

import cases_watch as CW  # noqa: E402 — 일정 · 문서 읽기 규칙 (엔비디아와 같은 정규식)
import config as NC  # noqa: E402

WATCH_PATH = os.path.join(_HERE, "court_watch.json")
DATA = os.path.join(_HERE, "data", "court.json")
SURVEY_MD = os.path.join(_HERE, "court_survey.md")       # 조사 결과 · 진행 기록 — 한 번 하는 일이라 끊겨도 이어 간다 (2026-11-01 사용자)
SURVEY_JSON = os.path.join(_HERE, "court_survey.json")   # 종목마다 끝나는 즉시 저장, 다시 돌리면 끝난 종목은 건너뜀
SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"

# 법원 당사자 이름 검색어 (사건명에 실제로 쓰이는 이름 — 옛 이름 포함). 정규식은 사건명 `A v. B` 의 B(피고) 쪽 확인용
PARTY = {
    "NVDA": ["NVIDIA"], "AAPL": ["Apple Inc"], "GOOGL": ["Alphabet", "Google"], "MSFT": ["Microsoft"], "AMZN": ["Amazon.com"],
    "META": ["Meta Platforms", "Facebook"], "AVGO": ["Broadcom"], "TSLA": ["Tesla"], "BRK-B": ["Berkshire Hathaway"], "LLY": ["Eli Lilly"],
    "MU": ["Micron Technology"], "WMT": ["Walmart"], "JPM": ["JPMorgan Chase"], "AMD": ["Advanced Micro Devices"], "V": ["Visa Inc"],
    "XOM": ["Exxon Mobil"], "JNJ": ["Johnson & Johnson"], "MA": ["Mastercard"], "ABBV": ["AbbVie"], "INTC": ["Intel Corporation", "Intel Corp"],
    "TSM": ["Taiwan Semiconductor"], "ASML": ["ASML Holding"], "LRCX": ["Lam Research"], "AMAT": ["Applied Materials"], "ORCL": ["Oracle Corporation", "Oracle Corp"],
    "ANET": ["Arista Networks"], "VRT": ["Vertiv"], "EQIX": ["Equinix"], "CEG": ["Constellation Energy"], "CRWV": ["CoreWeave"],
    "SPCX": ["Space Exploration Technologies"], "RKLB": ["Rocket Lab"], "KO": ["Coca-Cola Company"], "PG": ["Procter & Gamble"], "PM": ["Philip Morris International"],
    "NFLX": ["Netflix"], "DIS": ["Walt Disney"], "HD": ["Home Depot"], "MCD": ["McDonald's Corporation"], "CAT": ["Caterpillar"],
    "GE": ["General Electric", "GE Aerospace"], "COST": ["Costco Wholesale"], "CVX": ["Chevron Corporation"], "LIN": ["Linde"], "NEM": ["Newmont"],
    "WELL": ["Welltower"], "PLD": ["Prologis"], "NEE": ["NextEra Energy"], "SO": ["Southern Company"], "COP": ["ConocoPhillips"],
    "SLB": ["Schlumberger"], "EOG": ["EOG Resources"], "COIN": ["Coinbase"], "MSTR": ["MicroStrategy", "Strategy Inc"], "HOOD": ["Robinhood Markets"],
    "MARA": ["Marathon Digital", "MARA Holdings"], "CRCL": ["Circle Internet"], "VST": ["Vistra"], "SMR": ["NuScale Power"], "IONQ": ["IonQ"],
    "RGTI": ["Rigetti Computing"], "QBTS": ["D-Wave Quantum"], "QUBT": ["Quantum Computing Inc"], "IBM": ["International Business Machines"],
}


def _headers():
    token = os.environ.get("COURTLISTENER_TOKEN", "").strip()
    return {"Authorization": f"Token {token}", "User-Agent": NC.USER_AGENT} if token else None


class Limited(Exception):
    """CourtListener 요청 한도 — args[0] = 기다릴 초."""


def _search(q, headers, max_pages=5):
    import requests
    params, url, out, pages = {"type": "d", "q": q, "order_by": "dateFiled desc"}, SEARCH_URL, [], 0
    while url and pages < max_pages:
        r = requests.get(url, params=params if url == SEARCH_URL else None, headers=headers, timeout=NC.COURTLISTENER_TIMEOUT)
        if r.status_code == 429:
            wait = int(r.headers.get("retry-after") or 5)
            if wait > int(os.environ.get("COURT_MAX_WAIT", "60")):   # 무료 한도 (Actions 조사는 COURT_MAX_WAIT=3900 으로 기다렸다 이어 간다, 2026-11-02) — 몇십 분 기다리라면 여기서 멈춘다. 끝난 종목은 저장돼 있어 다시 돌리면 이어 간다 (2026-11-01 33분 대기로 멈춘 것처럼 보였다)
                raise Limited(wait)
            time.sleep(wait)
            continue
        r.raise_for_status()
        j = r.json()
        out += j.get("results", [])
        url, pages = j.get("next"), pages + 1
    return out


def _defendant(title, names):
    """사건명 `A v. B` 에서 B 쪽에만 회사 이름이 있으면 피고. `In re <회사>` 도 피고(증권 집단소송 이름 꼴)."""
    pat = re.compile("|".join(re.escape(n.split()[0] if len(n.split()[0]) > 4 else n) for n in names), re.I)
    if re.match(r"in re", title, re.I):
        return bool(pat.search(title))
    parts = re.split(r"\s+v\.?\s+", title, maxsplit=1, flags=re.I)
    return len(parts) == 2 and bool(pat.search(parts[1])) and not pat.search(parts[0])


def _survey_md(out):
    todo = [s for s in PARTY if s not in out]
    lines = ["# 소송 추적 후보 (court.py --survey)", "",
             f"갱신 {datetime.datetime.now():%Y-%m-%d %H:%M} · 종결 안 된 1심 증권 소송 중 회사가 피고 · **조사 {len(out)}/{len(PARTY)}종목**"
             + (f" · 남음 : {' '.join(todo)}" if todo else " · 끝"), "",
             "다시 돌리면 남은 종목부터 이어 간다 (`python court.py --survey`). 한 종목만 다시 = `python court.py --survey --redo AAPL`.", ""]
    for sym, v in out.items():
        rows = v["rows"]
        lines += [f"## {sym} ({len(rows)}건 · {v['at']})", ""] + [f"- {r['filed']} {r['court']} [{r['title']}]({r['url']}) · docket {r['docket_id']}" for r in rows] + [""]
    open(SURVEY_MD, "w", encoding="utf-8").write("\n".join(lines))


def survey(syms=None, redo=False):
    """후보 표 — 종결 안 된 1심(지방법원) 증권 소송 중 회사가 피고인 것. 사람이 보고 court_watch.json 에 옮긴다.
    종목 하나가 끝날 때마다 court_survey.json · .md 에 저장 → 끊겨도 다시 돌리면 남은 종목부터."""
    headers = _headers()
    if not headers:
        raise SystemExit("COURTLISTENER_TOKEN 없음 (.env)")
    out = json.load(open(SURVEY_JSON, encoding="utf-8")) if os.path.exists(SURVEY_JSON) else {}
    for sym in syms or PARTY:
        if sym in out and not redo:
            continue
        t0, seen, rows = time.time(), set(), []
        try:
            found = [d for name in PARTY[sym] for d in _search(f'party:"{name}" AND suitNature:securities', headers)]
        except Limited as e:
            print(f"[court] 요청 한도 ({e.args[0]}초 대기 요구) — {e.args[0] // 60 + 1}분 뒤 다시 돌리면 {sym} 부터 이어 간다 ({len(out)}/{len(PARTY)} 끝)", flush=True)
            _survey_md(out)
            return out
        for name in [None]:
            for d in found:
                court = (d.get("court_id") or "").lower()
                title = d.get("caseName") or ""
                if d["docket_id"] in seen or d.get("dateTerminated") or (court.startswith("ca") and court != "cand"):
                    continue
                seen.add(d["docket_id"])
                if not _defendant(title, PARTY[sym]):
                    continue
                rows.append({"docket_id": d["docket_id"], "title": title, "court": court.upper(), "filed": d.get("dateFiled") or "",
                             "nature": d.get("suitNature") or "", "url": "https://www.courtlistener.com" + (d.get("docket_absolute_url") or "")})
        out[sym] = {"at": f"{datetime.datetime.now():%Y-%m-%d %H:%M}", "rows": sorted(rows, key=lambda r: r["filed"], reverse=True)}
        json.dump(out, open(SURVEY_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        _survey_md(out)
        print(f"[court] {sym}: 후보 {len(rows)}건 ({time.time() - t0:.0f}s) · {len(out)}/{len(PARTY)}", flush=True)
    return out


def watch():
    return json.load(open(WATCH_PATH, encoding="utf-8")) if os.path.exists(WATCH_PATH) else {}


def load():
    return json.load(open(DATA, encoding="utf-8")) if os.path.exists(DATA) else {}


def fetch(day=None):
    """추적 사건마다 최신 문서 20건 → 결정 일정. 새로 읽은 사건은 그 사건의 미래 일정을 갈아 끼우고, 못 읽은 사건은 전에 쌓은 것을 둔다."""
    headers = _headers()
    store = load()
    if not headers:
        print("[court] COURTLISTENER_TOKEN 없음 — 전에 받은 일정만")
        return store
    today = datetime.date.fromisoformat(day) if day else datetime.date.today()
    n = 0
    for sym, cases in watch().items():
        for c in cases:
            key = str(c["docket_id"])
            if n:
                time.sleep(3)   # 사건 사이 간격 — 짧게 몰리면 CourtListener 가 429 로 막는다 (2026-11-10, 17건)
            try:
                entries = CW.fetch_entries(key, headers)
            except Exception as e:  # noqa: BLE001
                print(f"[court] {sym} {c['name']} 조회 실패: {str(e)[:100]}")
                continue
            if not entries:
                continue
            ms = CW.milestones_from(entries, today)
            store[key] = {"sym": sym, "name": c["name"], "dates": sorted(({"label": k, "day": v[0]} for k, v in ms.items()), key=lambda x: x["day"]),
                          "status": CW.case_status(entries)}   # 합의 · 정지 (2026-11-10) — 합의는 일정이 없어도 카드에 `합의 진행 중`
            n += 1
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    json.dump(store, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[court] 추적 사건 {n}건 읽음")
    return store


def card(sym, day, store):
    """이 종목의 다가오는 법원 일정 — 사건마다 가장 가까운 것 하나 (엔비디아 cal_cards.card_court 와 같은 모양)."""
    d0 = datetime.date.fromisoformat(day)
    out = []
    for v in store.values():
        if v.get("sym") != sym:
            continue
        nxt = next((x for x in v["dates"] if x["day"] > day), None)
        if nxt:
            out.append({"name": v["name"], "day": nxt["day"], "label": nxt["label"], "left": (datetime.date.fromisoformat(nxt["day"]) - d0).days})
        elif v.get("status") == "settled":   # 원칙적 합의로 일정이 멈춘 사건 — 날짜 없이 한 줄 (2026-11-10 사용자)
            out.append({"name": v["name"], "day": None, "label": "합의 진행 중", "left": None})
    out.sort(key=lambda x: (x["day"] is None, x["day"] or ""))
    return {"cases": out} if out else None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_HERE, "..", "..", ".env"))
    if "--survey" in sys.argv:
        survey([a for a in sys.argv[1:] if not a.startswith("--")] or None, redo="--redo" in sys.argv)
    else:
        fetch()
