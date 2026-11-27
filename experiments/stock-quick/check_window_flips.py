"""업계 카드 판정을 한 달 기준으로 바꾸면 얼마나 자주 뒤집히나 — 3개월 묶음 17개 첫 지표 + 업계 경기(BSI) 업황.

    GH_TOKEN=… .venv/bin/python experiments/stock-quick/check_window_flips.py [--flows F]

판정 규칙은 카드와 같다: 일감 카드 = 작년 같은 기간보다 ±5% 넘으면 늘고 · 줄고(그 사이 비슷함), 업계 경기 = ±3p.
뒤집힘 = 판정 말이 바뀐 달 수(1년당) · 되돌림 = 바뀐 뒤 두 달 안에 원래 말로 돌아온 횟수(1년당, 출렁임에 속은 횟수).
ECOS 지표는 2010년부터 다시 받고, 관세청 · KOSIS · 기계수주는 상태 파일에 있는 만큼(약 3년). AI 0 · 쓰기 0 · ECOS 읽기 약 12번.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE]
import mock_industry_tab as M  # noqa: E402

K, C = M.K, M.C


def back(m, n):
    y, mo = int(m[:4]), int(m[5:]) - n
    while mo <= 0:
        y, mo = y - 1, mo + 12
    return f"{y}-{mo:02d}"


def states(by, months, lim=5.0):
    out = []
    for m in sorted(by):
        span = [back(m, i) for i in range(months)]
        prev = [f"{int(x[:4]) - 1}{x[4:]}" for x in span]
        if any(x not in by for x in span + prev) or not sum(by[x] for x in prev):
            continue
        c = (sum(by[x] for x in span) / sum(by[x] for x in prev) - 1) * 100
        out.append((m, "늘" if c >= lim else "줄" if c <= -lim else "비슷"))
    return out


def flips(st):
    """(1년당 뒤집힘, 1년당 되돌림, 기간 년)."""
    if len(st) < 13:
        return None
    w = [s for _, s in st]
    ch = [i for i in range(1, len(w)) if w[i] != w[i - 1]]
    rev = sum(1 for i in ch if any(w[j] == w[i - 1] for j in range(i + 1, min(i + 3, len(w)))))
    yrs = len(w) / 12
    return len(ch) / yrs, rev / yrs, yrs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flows", default="")
    flows = M.load_flows(ap.parse_args().flows)
    key = C._ecos_key()
    rows = []
    for g, b in K.BIZ.items():
        if b.get("months", 1) < 2:
            continue
        k = b["inds"][0]
        meta = K.INDICATORS.get(k) or getattr(K, "DERIVED", {}).get(k) or ("derived", "", k)
        stat, item = meta[:2]
        ser = flows.get("industry", {}).get(k) or []
        src = "상태 파일"
        if stat not in ("customs", "kosis", "derived", "tourism") and not stat.startswith("mach") and item:
            try:
                r = C._ecos(key, stat, "M", "201001", "202612", item, n=5000)
                if len({x.get("ITEM_CODE2") for x in r}) > 1:
                    r = [x for x in r if "원화" in (x.get("ITEM_NAME2") or "")]
                got = [{"month": f"{x['TIME'][:4]}-{x['TIME'][4:]}", "v": float(x["DATA_VALUE"])} for x in r if x.get("DATA_VALUE")]
                if len(got) > len(ser):
                    ser, src = got, "ECOS 2010~"
                time.sleep(0.3)
            except Exception as e:   # noqa: BLE001
                print(f"[{g}] ECOS 실패 {e}")
        by = {x["month"]: x["v"] for x in ser}
        f1, f3 = flips(states(by, 1)), flips(states(by, 3))
        last1 = (states(by, 1) or [("", "")])[-1]
        last3 = (states(by, 3) or [("", "")])[-1]
        rows.append((g, meta[2], src, f1, f3, last1, last3))
    print("\n| 묶음 | 첫 지표 | 자료 | 한 달: 뒤집힘 / 되돌림 (1년당) | 3개월: 뒤집힘 / 되돌림 | 지금 판정 한 달 · 3개월 |")
    print("|---|---|---|---|---|---|")
    for g, name, src, f1, f3, l1, l3 in rows:
        fm = lambda f: f"{f[0]:.1f} / {f[1]:.1f} ({f[2]:.0f}년)" if f else "자료 짧음"
        print(f"| {g} | {name} | {src} | {fm(f1)} | {fm(f3)} | {l1[1]} · {l3[1]} ({l1[0]}) |")
    # 업계 경기 업황 — 전달 대비 vs 석 달 전 대비 (±3p)
    print("\n| 업계 경기 업종 | 전달 대비: 뒤집힘 / 되돌림 | 석 달 전 대비: 뒤집힘 / 되돌림 |\n|---|---|---|")
    agg = {1: [], 3: []}
    for ind, d in (flows.get("bsi") or {}).items():
        xa = d.get("AA") or []
        v = [x["v"] for x in xa]
        res = {}
        for n in (1, 3):
            st = [("", "좋" if v[i] - v[i - n] >= 3 else "나" if v[i] - v[i - n] <= -3 else "비") for i in range(n, len(v))]
            res[n] = flips(st)
            if res[n]:
                agg[n].append(res[n])
        name = next((nm for k2, (nm, *_r) in getattr(K, "BSI_INDUSTRY", {}).items() if k2 == ind), ind)
        if res[1] and res[3]:
            print(f"| {name} | {res[1][0]:.1f} / {res[1][1]:.1f} | {res[3][0]:.1f} / {res[3][1]:.1f} |")
    for n in (1, 3):
        if agg[n]:
            print(f"업계 경기 평균({'전달' if n == 1 else '석 달 전'} 대비): 뒤집힘 {sum(x[0] for x in agg[n]) / len(agg[n]):.1f} · 되돌림 {sum(x[1] for x in agg[n]) / len(agg[n]):.1f} (1년당, {len(agg[n])}업종)")


if __name__ == "__main__":
    main()
