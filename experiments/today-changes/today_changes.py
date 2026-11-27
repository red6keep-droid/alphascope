"""오늘 달라진 것 — 후보 계산.

AI 0 · 새 수집 0(목업 단계는 평소 흔들림만 yfinance 로 받는다 — 정식 때는 각 실행이 이미 받은 시세를 쓴다).
재료 = gh-pages 자료 파일(data.json · stocks.json · kr.json · issues.json · hypo.json) + 상태 기록(records/issues · records/forecasts).

달라짐의 종류 (기획 2절) · 순서 = 결과 → 상태 → 움직임 → 일정:
  결과  미리 적은 전망의 판정이 남
  상태  Hot Issue 쪽 · 전망 국면이 전날과 다름
  움직임  지수 = 늘 한 줄(그 지수 자신의 평소 하루 움직임의 몇 배)
          업종 · 종목 = **시장 대비 움직임**이 그 자신의 평소(직전 60거래일)보다 SECTOR_Z · STOCK_Z 배 넘게 큼
          — 시장 전체가 빠진 날 모든 종목이 줄줄이 올라오지 않게(시장 몫은 지수 줄이 말한다)
  일정  오늘 · 다음 거래일 실적 발표
줄 = {kind, what, change, dir, cmp, href, z} — 문장은 틀, "때문에" 없음(헌법 제2조), 줄마다 비교 대상(제1조).

    .venv/bin/python experiments/today-changes/today_changes.py [--state 상태폴더]   → output/today_us.json · today_kr.json
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "output")
BLOG = "https://www.newfact.app"
BASE = 60          # 평소 = 직전 60거래일 (Hot Issue · 전망과 같은 셈)
STOCK_Z = 2.0      # 종목: 시장 대비 움직임이 평소의 2배 넘게 — 그림자 실행으로 다듬을 값
SECTOR_Z = 1.5     # 업종: 1.5배
INDEX = {"us": ("S&P 500", "^GSPC"), "kr": ("코스피", "^KS11")}


def gh(name):
    r = subprocess.run(["git", "show", f"origin/gh-pages:{name}"], capture_output=True, cwd=ROOT)
    return json.loads(r.stdout.decode("utf-8")) if r.returncode == 0 else None


def returns(syms):
    """하루 수익률(%) 표 — 열 = 기호. 목업 단계만 yfinance."""
    import yfinance as yf
    df = yf.download(sorted(set(syms)), period="8mo", progress=False, auto_adjust=True, threads=False)["Close"]
    return df.pct_change() * 100


def z_of(s, day):
    """그날 값 ÷ 직전 BASE 거래일 표준편차. (값, 배수) — 못 구하면 (None, None)."""
    s = s.dropna()
    s = s[s.index <= day]
    if len(s) < BASE + 1:
        return None, None
    sd = s.iloc[-BASE - 1:-1].std()
    v = float(s.iloc[-1])
    return v, (float(v / sd) if sd and sd > 0 else None)


def sign(v, unit="%"):
    return f"{'▲' if v > 0 else '▼'}{abs(v):.1f}{unit}"


def times(z):
    return f"평소의 {abs(z):.1f}배" if z is not None else ""


def moves(mkt, rows):
    """움직임 — 지수 한 줄 + 시장 대비로 평소보다 크게 움직인 업종 · 종목."""
    import pandas as pd
    src = gh("stocks.json") if mkt == "us" else gh("kr.json")
    if not src:
        return None
    day = pd.Timestamp(src["day"])
    nm, isym = INDEX[mkt]
    key = (lambda x: x["s"]) if mkt == "us" else (lambda x: x["sym"])
    stocks = [x for x in src["stocks"] if x.get("cp") is not None]
    rt = returns([key(x) for x in stocks] + [isym])
    iv, iz = z_of(rt[isym], day)
    if iv is None:
        return src["day"]
    quiet = iz is not None and abs(iz) < 1
    rows.append({"kind": "움직임", "what": nm, "change": sign(iv), "dir": 1 if iv > 0 else -1,
                 "cmp": "평소 범위" if quiet else times(iz), "z": abs(iz or 0) + 100,   # 지수 = 움직임 맨 앞
                 "href": f"{BLOG}/search/label/" + ("미국%20증시%20리포트" if mkt == "us" else "한국%20증시%20리포트")})
    rel = rt.sub(rt[isym], axis=0)
    # 종목마다 시장 대비 움직임의 평소 대비 배수
    hit = {}
    for x in stocks:
        k = key(x)
        if k in rel:
            v, z = z_of(rel[k], day)
            if z is not None:
                hit[x["s"]] = (x, v, z)
    # 업종 = 종목의 sector 칸으로 묶음(2종목 이상). 업종 줄이 서면 그 업종 종목은 업종 줄 안으로 — 급락한 날 수십 줄이 되지 않게 (2026-11-22)
    groups = {}
    for x in stocks:
        if x.get("sector") and key(x) in rel:
            groups.setdefault(x["sector"], []).append(x)
    grouped = set()
    for sec, xs in groups.items():
        if len(xs) < 2:
            continue
        v, z = z_of(rel[[key(x) for x in xs]].mean(axis=1), day)
        if z is None or abs(z) < SECTOR_Z:
            continue
        same = sorted([h for h in (hit.get(x["s"]) for x in xs) if h and h[1] * v > 0 and abs(h[2]) >= 1], key=lambda h: -abs(h[2]))
        grouped |= {h[0]["s"] for h in same}
        rows.append({"kind": "움직임", "what": f"{sec} 업종", "change": f"{nm}보다 {sign(v, '%p')}", "dir": 1 if v > 0 else -1,
                     "cmp": f"{times(z)} · {len(xs)}종목 평균", "z": abs(z), "href": f"{BLOG}/p/stock-lists.html?m={mkt}",
                     "members": [{"name": h[0]["name"], "change": sign(h[0]["cp"]), "rel": f"{nm}보다 {sign(h[1], '%p')}", "times": times(h[2]),
                                  "href": f'{BLOG}/p/{h[0]["slug"]}.html' if h[0].get("page") and h[0].get("slug") else ""} for h in same]})
    for s, (x, v, z) in hit.items():
        if s in grouped or abs(z) < STOCK_Z:
            continue
        rows.append({"kind": "움직임", "what": x["name"], "change": sign(x["cp"]), "dir": 1 if x["cp"] > 0 else -1,
                     "cmp": f"{nm}보다 {sign(v, '%p')} · {times(z)}", "z": abs(z),
                     "href": f'{BLOG}/p/{x["slug"]}.html' if x.get("page") and x.get("slug") else f"{BLOG}/p/stock-lists.html?m={mkt}"})
    for e in src.get("events") or []:   # 일정 — 오늘 · 다음 거래일 실적
        d = dt.date.fromisoformat(e["day"])
        if e.get("kind") == "earnings" and 0 <= (d - dt.date.today()).days <= 3:
            when = {"amc": "장 마감 뒤", "bmo": "장 시작 전"}.get(e.get("when"), "")
            rows.append({"kind": "일정", "what": f'{e["name"]} 실적', "change": f"{d:%m.%d} {when}".strip(), "dir": 0, "cmp": "", "z": 0,
                         "href": f'{BLOG}/p/{e["slug"]}.html' if e.get("slug") else BLOG})
    return src["day"]


def last_two(path, key):
    """기록 파일에서 가장 최근 날 줄과 그 앞 날 줄 (같은 날 여러 줄이면 마지막)."""
    by = {}
    try:
        for line in open(path, encoding="utf-8"):
            j = json.loads(line)
            if key(j):
                by[j["day"]] = j
    except (OSError, ValueError):
        return None, None
    ds = sorted(by)
    return (by[ds[-1]], by[ds[-2]] if len(ds) > 1 else None) if ds else (None, None)


def states(mkt, rows, state_dir):
    """결과 · 상태 — Hot Issue 쪽(미국 화면) · 전망 국면 · 판정."""
    if not state_dir:
        return
    if mkt == "us":
        for it in (gh("issues.json") or {}).get("issues", []):
            cur, prev = last_two(os.path.join(state_dir, "records", "issues", f'{it["id"]}.jsonl'), lambda j: j.get("gauge"))
            if cur and prev and cur["gauge"] != prev["gauge"]:
                rows.append({"kind": "상태", "what": it["name"], "change": f'{prev["gauge"]} → {cur["gauge"]}', "dir": 0,
                             "cmp": "최근 일주일 뉴스 기준", "z": 0, "href": BLOG + it["url"]})
    for q in (gh("hypo.json") or {}).get("open", []):
        if (q.get("market") or "us") != mkt:
            continue
        cur, prev = last_two(os.path.join(state_dir, "records", "forecasts", f'{q["eh"]}.jsonl'), lambda j: j.get("slug") in q["url"])
        if not cur:
            continue
        if cur.get("result") and not (prev and prev.get("result")):
            ov = cur.get("overlap")
            rows.append({"kind": "결과", "what": q["title"], "change": cur["result"], "dir": 0,
                         "cmp": f'{ov["event"]} 겹침 · 성적에는 따로' if ov else "미리 적은 기준대로", "z": 0, "href": q["url"]})
        elif prev and cur.get("label") != prev.get("label"):
            rows.append({"kind": "상태", "what": q["title"], "change": f'{prev["label"]} → {cur["label"]}', "dir": 0,
                         "cmp": "미리 적은 기준 대비", "z": 0, "href": q["url"]})


def build(mkt, state_dir=None):
    rows = []
    day = moves(mkt, rows)
    states(mkt, rows, state_dir)
    order = {"결과": 0, "상태": 1, "움직임": 2, "일정": 3}
    rows.sort(key=lambda r: (order[r["kind"]], -r["z"]))
    return {"market": mkt, "day": day, "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rows": rows}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=None)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for m in ("us", "kr"):
        j = build(m, a.state)
        with open(os.path.join(OUT, f"today_{m}.json"), "w", encoding="utf-8") as f:
            json.dump(j, f, ensure_ascii=False, indent=1)
        print(f"== {m} {j['day']} · {len(j['rows'])}줄")
        for r in j["rows"]:
            print(f"  [{r['kind']}] {r['what']} | {r['change']} | {r['cmp']}" + (" | " + " · ".join(m["name"] for m in r["members"]) if r.get("members") else ""))
