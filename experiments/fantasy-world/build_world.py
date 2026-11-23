"""주식마을 3D 목업 2판 — 성능 틀 · 기술 마을 디테일 · 배치 파일 휴대폰 저장 (2026-11-23 사용자 "같이 넣어서 목업 만들어 줘").

    python experiments/fantasy-world/build_world.py

만드는 것 (output/ — 목업 서버가 내준다):
    world/layout_us-tech.json   마을 배치 = 고정 데이터. 종목 → 자리(θ, φ) · 이름 · 시가총액 · 주소, 버전 v(내용 해시).
                                휴대폰 IndexedDB 에 저장되고, 버전이 같으면 다시 받지 않는다.
    world/daily_us-tech.json    그날 숫자 = 하루 등락 · 업종 · 시장 중앙값 · 계절 · layout_v (약 2KB)
    mock_village_3d_v2.html     목업

배치 고정 규칙 (지도를 익히게 — 건물은 매일 같은 자리):
    - 이전 배치 파일이 있으면 기존 종목 자리는 그대로, 새 종목은 비어 있는 다음 자리, 빠진 종목은 자리를 비움.
    - 광장 가운데(자리 0) = 마을 시가총액 1위(성). 1위가 바뀌면 두 종목 자리만 맞바꾼다.
    - 길(6갈래) 위와 광장에는 건물을 놓지 않는다.
비교 기준은 1판(build_mock.py)과 같다.
"""
import hashlib
import json
import math
import os
import statistics as st

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "data", "us_lists_2026-11-20.json")
OUTD = os.path.join(BASE, "output")
WORLD = os.path.join(OUTD, "world")
KEY = "us-tech"
SECTORS = ("기술", "반도체")
R = 24.0
SPREAD = 0.105          # 황금각 나선 간격(라디안 · √k)
GOLD = 2.39996
ROADS = [math.radians(15 + 60 * k) for k in range(6)]
PLAZA = 0.24            # 광장 반지름(라디안)
ROAD_HALF = 1.8         # 길 가운데에서 건물까지 최소 거리(행성 단위)


def _free(th, ph):
    if th < PLAZA:
        return False
    for a in ROADS:
        d = (ph - a + math.pi) % (2 * math.pi) - math.pi
        if abs(d) < math.pi / 2 and abs(math.sin(d)) * math.sin(th) * R < ROAD_HALF:
            return False
    return True


def _slots():
    k = 1
    while True:
        th, ph = SPREAD * math.sqrt(k + 2.2), (k * GOLD) % (2 * math.pi)
        if _free(th, ph):
            yield k, round(th, 4), round(ph, 4)
        k += 1


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    allr = [r["r"] for r in d["rows"] if r.get("r") is not None]
    rows = [r for r in d["rows"] if r["s"] in SECTORS and r.get("c")]
    rows.sort(key=lambda r: -r["c"])
    by_t = {r["t"]: r for r in rows}
    os.makedirs(WORLD, exist_ok=True)
    lp = os.path.join(WORLD, f"layout_{KEY}.json")

    # ── 배치: 이전 자리 유지
    prev = json.load(open(lp, encoding="utf-8")) if os.path.exists(lp) else None
    slots = {}                        # t -> (k, th, ph)
    if prev:
        for s in prev["slots"]:
            if s["t"] in by_t:
                slots[s["t"]] = (s["k"], s["th"], s["ph"])
    used = {v[0] for v in slots.values()}
    leader = rows[0]["t"]
    if leader not in slots and 0 not in used:
        slots[leader] = (0, 0.0, 0.0)
        used.add(0)
    gen = _slots()
    for r in rows:
        if r["t"] in slots:
            continue
        while True:
            k, th, ph = next(gen)
            if k not in used:
                break
        slots[r["t"]] = (k, th, ph)
        used.add(k)
    # 광장 가운데 = 지금 1위 (바뀌었으면 맞바꿈)
    holder = next((t for t, v in slots.items() if v[0] == 0), None)
    if holder and holder != leader:
        slots[holder], slots[leader] = slots[leader], slots[holder]
    out_slots = sorted(({"t": t, "n": by_t[t]["n"], "c": round(by_t[t]["c"]), "u": by_t[t].get("u") or "",
                         "k": v[0], "th": v[1], "ph": v[2]} for t, v in slots.items()), key=lambda s: -s["c"])
    edge = round(max(s["th"] for s in out_slots) + 0.08, 4)
    body = {"key": KEY, "village": "기술 마을", "R": R, "plaza": PLAZA, "edge": edge,
            "roads": [round(a, 4) for a in ROADS], "spread": SPREAD, "slots": out_slots}
    v = hashlib.sha1(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:10]
    layout = {"v": v, "made": d["d"], **body}
    json.dump(layout, open(lp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    # ── 그날 숫자
    rs = [r["r"] for r in rows if r.get("r") is not None]
    sec_med, mkt_med = round(st.median(rs), 2), round(st.median(allr), 2)
    gap = sec_med - mkt_med
    season = "winter" if (gap <= -1 and sec_med < 0) else "summer" if (gap >= 1 and sec_med > 0) else "between"
    daily = {"date": d["d"], "key": KEY, "layout_v": v, "n_mkt": len(allr), "sec_med": sec_med, "mkt_med": mkt_med,
             "season": season, "r": {r["t"]: r["r"] for r in rows if r.get("r") is not None}}
    json.dump(daily, open(os.path.join(WORLD, f"daily_{KEY}.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    html = open(os.path.join(BASE, "world_v2.html"), encoding="utf-8").read()
    open(os.path.join(OUTD, "mock_village_3d_v2.html"), "w", encoding="utf-8").write(html)
    sz = lambda f: os.path.getsize(os.path.join(WORLD, f)) / 1024
    print(f"[world] 배치 v{v} {len(out_slots)}채 edge {edge} ({sz(f'layout_{KEY}.json'):.1f}KB) · "
          f"하루 {daily['date']} {season} ({sz(f'daily_{KEY}.json'):.1f}KB)")


if __name__ == "__main__":
    main()
