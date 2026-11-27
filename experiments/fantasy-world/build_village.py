"""주식을 행성으로 보기 — 마을 화면 시안 (평평한 땅 · 붙박이 + 손님 집).

    python experiments/fantasy-world/build_village.py

만드는 것 (output/):
    village/layout_us.<버전>.json   고정 자료 — 업종마다 붙박이 자리(순서 = 자리 번호) · 종목 이름 · 주소. 버전 = 내용 해시.
                                    운영에서는 고정 그림 저장소(img_store.py, Pages newfact-img)의 world/ 로 간다 — 이름에 버전이 있어
                                    캐시(일주일)가 길어도 안전하고, 붙박이가 바뀐 날에만 새 파일이 생긴다. 휴대폰에도 저장(IndexedDB)한다.
    village/daily_us.json           날마다 바뀌는 숫자 — 등락 · 시가총액 · 시장 중앙값 · 지금 쓸 배치 파일 이름. 운영에서는 gh-pages 쪽.
    mock_village_flat.html          시안 (원본 = village_flat.html)
    mock_village_polish.html        다듬은 판 (원본 = village_polish.html — 모양 · 빛만 다름)


붙박이 규칙:
    자리 25개(성 1 + 24). 처음에는 시가총액 순. 그 뒤로는 자리를 지킨다 — 시가총액 29위 밖으로 밀려야 자리를 내주고(문턱),
    빈자리에는 붙박이가 아닌 종목 중 시가총액이 가장 큰 종목이 들어온다. 성(자리 0)은 늘 1위 — 바뀌면 두 종목만 맞바꾼다.
화면 규칙:
    손님 = 붙박이가 아닌 종목 중 오늘 업종 중앙값에서 가장 멀리 움직인 종목(오름 · 내림 번갈아). 무엇을 세울지는 화면이 고른다.
    마을 계절 · 날씨 = 보이는 집이 아니라 업종 전체 종목으로 계산.  빠진 종목 = 화면 아래 접는 목록.
"""
import glob
import hashlib
import json
import os
import statistics as st

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "data", "us_lists_2026-11-20.json")
OUTD = os.path.join(BASE, "output")
VD = os.path.join(OUTD, "village")
N_FIXED = 25          # 성 1 + 붙박이 24
KEEP_RANK = 29        # 이 순위 밖으로 밀리면 자리를 내준다


def _fixed(rows, prev):
    """rows = 시가총액 순. prev = 이전 붙박이 티커(자리 순서) 또는 None."""
    rank = {r["t"]: i for i, r in enumerate(rows)}
    n = min(N_FIXED, len(rows))
    if not prev:
        return [r["t"] for r in rows[:n]]
    slots = [t if t in rank and rank[t] < KEEP_RANK else None for t in prev[:n]]
    slots += [None] * (n - len(slots))
    used = {t for t in slots if t}
    spare = (r["t"] for r in rows if r["t"] not in used)
    slots = [t or next(spare) for t in slots]
    lead = rows[0]["t"]
    if slots[0] != lead:                       # 성 = 1위
        if lead in slots:
            i = slots.index(lead)
            slots[0], slots[i] = slots[i], slots[0]
        else:
            slots[0] = lead
    return slots


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    os.makedirs(VD, exist_ok=True)
    dp = os.path.join(VD, "daily_us.json")
    prev = {}
    if os.path.exists(dp):
        lf = os.path.join(VD, json.load(open(dp, encoding="utf-8")).get("layout_file", ""))
        if os.path.isfile(lf):
            prev = {s["name"]: s["fixed"] for s in json.load(open(lf, encoding="utf-8"))["sectors"]}
    allr = [r["r"] for r in d["rows"] if r.get("r") is not None]
    by = {}
    for r in d["rows"]:
        if r.get("c"):
            by.setdefault(r["s"], []).append(r)
    secs = sorted(by.items(), key=lambda kv: -sum(r["c"] for r in kv[1]))
    lay_secs, q, changed = [], {}, 0
    for name, rows in secs:
        rows.sort(key=lambda r: -r["c"])
        fx = _fixed(rows, prev.get(name))
        changed += bool(prev.get(name)) and fx != prev[name]
        lay_secs.append({"name": name, "fixed": fx,
                         "stocks": sorted(({"t": r["t"], "n": r["n"], "u": r.get("u") or ""} for r in rows), key=lambda x: x["t"])})
        for r in rows:
            q[r["t"]] = [r.get("r"), round(r["c"])]
    body = {"market": "미국", "n_fixed": N_FIXED, "sectors": lay_secs}
    v = hashlib.sha1(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:10]
    lname = f"layout_us.{v}.json"
    for f in glob.glob(os.path.join(VD, "layout_us.*.json")):
        if os.path.basename(f) != lname:
            os.remove(f)                       # 목업 폴더만 정리 — 운영 고정 저장소에서는 옛 버전을 한동안 남긴다
    json.dump({"v": v, **body}, open(os.path.join(VD, lname), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    daily = {"date": d["d"], "market": "미국", "layout_v": v, "layout_file": lname,
             "mkt_med": round(st.median(allr), 2), "n_mkt": len(allr), "q": q}
    json.dump(daily, open(dp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    old = os.path.join(VD, "us.json")
    if os.path.exists(old):
        os.remove(old)
    html = open(os.path.join(BASE, "village_flat.html"), encoding="utf-8").read()
    open(os.path.join(OUTD, "mock_village_flat.html"), "w", encoding="utf-8").write(html)
    html = open(os.path.join(BASE, "village_polish.html"), encoding="utf-8").read()       # 다듬은 판 (2026-11-23)
    open(os.path.join(OUTD, "mock_village_polish.html"), "w", encoding="utf-8").write(html)
    html = open(os.path.join(BASE, "city_weather.html"), encoding="utf-8").read()          # 날씨 도시 판 — 지금 중심 시안 (2026-11-23)
    open(os.path.join(OUTD, "mock_city_weather.html"), "w", encoding="utf-8").write(html)
    kb = lambda f: os.path.getsize(os.path.join(VD, f)) / 1024
    print(f"[village] {d['d']} sectors {len(secs)} stocks {len(q)} layout v{v} {kb(lname):.1f}KB"
          f" changed {changed} daily {kb('daily_us.json'):.1f}KB")


if __name__ == "__main__":
    main()
