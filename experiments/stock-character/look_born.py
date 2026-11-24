"""뉴팩트 개성 있는 아이 찾기 게임 — 5단계 "왜": 개성이 태어난 때를 사용자 가설 ㉠의 순서로 본다, 한 명씩 (2026-11-24 사용자 "그렇게 해").

길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md 7-11(가설 ㉠ 가-3: 돈 · 관심이 들어옴 → 끊김 → 급등락) · 7-13(민감 구간) · 7-14(순서) · 7-22.
사용자: "왜 이 애가 개성이 되었는지. 왜 개성이 있는 애가 생겼는지. 그 배경을 찾으라고 했잖아."
새 문턱 없음 — 앞 걸음의 정의 그대로:
  구간          look_band 의 20거래일 구간 37개(최근 3년)
  거래 주식 수 배수  구간 평균 거래 주식 수 ÷ 그 종목 첫 1년(12구간) 가운데 값 (7-14 — 주가가 올라 거래대금이 저절로 커지는 것을 빼려고 주식 수)
  주가 배수       구간 끝 종가 ÷ 첫 1년 가운데 값 (7-14)
  예고 없는 돌 · 평소 하루 폭  look_band 값
  처음 넘은 때     두 구간 이어서 넘은 첫 구간 — 거래 1.5배 · 주가 +30% · 돌 3개 (7-14)
  돌이 잦았던 때   예고 없는 돌 수가 대부분의 종목 범위(가운데 80%) 위 끝을 넘은 구간이 2구간 넘게 이어진 덩어리
  민감 구간       종가가 1년 고점의 10% 안에 20거래일 넘게 머문 구간 · 어떻게 끝났나 (7-13 look_fragile.episodes)
비교 대상(헌법 제1조) = 같은 구간 S&P 500 종목의 가운데 80%. 판정하지 않는다(점검 16) — 순서와 이름 · 날짜만. 관심(뉴스 수)은 자료가 없어 안 봄. 새 호출 0.

    python experiments/stock-character/look_born.py LITE     # → output/mock_born_LITE.html — 목업 목록 `개성 있는 아이 찾기 게임`
"""

import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import look_band as LB  # noqa: E402
import look_fragile as LF  # noqa: E402
from look_order import first_on  # noqa: E402
from look_why import q  # noqa: E402

W, BAND = 20, 80
ATTN = os.path.join(LB.STORE, "attn")     # 관심 자료 원본(깃 밖) — 한 번 받으면 다시 안 부른다
UA = {"User-Agent": "research-script/1.0"}


def attn(sym, query, wiki, d0, d1):
    """관심 = 남이 날마다 세어 둔 기록 둘(2026-11-24 사용자 "그렇게 해봐" — 한 명 시험, 손으로 한 번).
    GDELT 기사 수: 이름이 나온 온라인 기사 수와 그날 GDELT 가 본 전체 기사 수(하루 한 줄씩, 2017 ~). 5초에 한 번만 부른다.
    위키백과 조회수: 영어 문서의 달마다 조회수(넘겨주기 이름은 따로 세어져 있어 문서 이름을 정확히 줘야 한다)."""
    import io
    import time
    import pandas as pd
    import requests
    os.makedirs(ATTN, exist_ok=True)
    gp, wp = os.path.join(ATTN, f"{sym}_gdelt.csv"), os.path.join(ATTN, f"{sym}_wiki.json")
    if query and not os.path.exists(gp):
        r = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", headers=UA, timeout=90, params={
            "query": f'"{query}"', "mode": "timelinevolraw", "format": "csv", "startdatetime": d0.replace("-", "") + "000000", "enddatetime": d1.replace("-", "") + "235959"})
        if r.ok and r.text.lstrip("\ufeff").startswith("Date,"):
            open(gp, "w", encoding="utf-8").write(r.text.lstrip("\ufeff"))
        else:
            print("  GDELT 못 받음:", r.text[:80])
        time.sleep(6)
    if wiki and not os.path.exists(wp):
        r = requests.get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/{wiki}/monthly/{d0.replace('-', '')}/{d1.replace('-', '')}", headers=UA, timeout=30)
        if r.ok:
            json.dump({"title": wiki, "items": [[x["timestamp"][:6], x["views"]] for x in r.json().get("items", [])]}, open(wp, "w"))
    g = None
    if os.path.exists(gp):
        g = pd.read_csv(io.StringIO(open(gp, encoding="utf-8").read()), parse_dates=["Date"]).pivot(index="Date", columns="Series", values="Value")
    w = json.load(open(wp)) if os.path.exists(wp) else None
    return g, w


def main():
    sym = sys.argv[1] if len(sys.argv) > 1 else "LITE"
    opt = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)     # news="Lumentum" wiki=Lumentum — 관심 자료(없으면 그 줄은 화면에서 빠짐)
    R = LB.compute()
    rows, labels, days, cuts = R["rows"], R["labels"][W], R["days"], R["cuts"][W]
    np_, t = len(labels), (100 - BAND) / 200
    me = next(x for x in rows if x["s"] == sym)

    def mult(s):
        d = R["bars"][s]
        d = d[(d["open"] > 0) & (d["volume"] > 0)].reindex(days)
        vol = np.array([d["volume"].iloc[a:b].mean() for a, b in cuts])
        px = np.array([(lambda c: c.iloc[-1] if len(c) else np.nan)(d["close"].iloc[a:b].dropna()) for a, b in cuts])
        if np.isnan(vol[:12]).all():
            return None
        return vol / np.nanmedian(vol[:12]), px / np.nanmedian(px[:12])
    ex = {x["s"]: m for x in rows if (m := mult(x["s"])) is not None}

    def band(vals):
        v = sorted(float(a) for a in vals if a == a)
        return [round(q(v, t), 3), round(q(v, 1 - t), 3)]
    # 칸 넷: 주가 배수 · 거래 주식 수 배수 · 예고 없는 돌 · 평소 하루 폭 — 구간마다 [이 종목 값, 범위 아래 끝, 위 끝]
    series = []
    for name, unit, dec, get in (("주가", "배", 1, lambda s, p: ex[s][1][p] if s in ex else np.nan),
                                 ("거래 주식 수", "배", 1, lambda s, p: ex[s][0][p] if s in ex else np.nan),
                                 ("예고 없는 돌 수", "일", 0, lambda s, p: next(x for x in rows if x["s"] == s)["w"][W][p][1] if next(x for x in rows if x["s"] == s)["w"][W][p] else np.nan),
                                 ("평소 하루 폭", "%", 1, lambda s, p: next(x for x in rows if x["s"] == s)["w"][W][p][0] if next(x for x in rows if x["s"] == s)["w"][W][p] else np.nan)):
        pts = []
        for p in range(np_):
            if name in ("주가", "거래 주식 수"):
                allv = [ex[s][1 if name == "주가" else 0][p] for s in ex]
            else:
                allv = [x["w"][W][p][1 if name == "예고 없는 돌 수" else 0] for x in rows if x["w"][W][p]]
            v = get(sym, p)
            pts.append([None if v != v else round(float(v), 2)] + band(allv))
        series.append({"name": name, "unit": unit, "dec": dec, "pts": pts})
    px, vx, st = [[pt[0] for pt in s["pts"]] for s in series[:3]]
    # 관심 — 구간마다 기사 수가 그때 전체 기사에서 차지한 몫 ÷ 첫 1년 가운데 값. 다른 종목 것은 안 받아 대부분의 종목 범위는 없다(비교 대상 = 전체 기사 · 자기 첫 1년)
    g, wiki = attn(sym, opt.get("news"), opt.get("wiki"), str(days[0].date()), str(R["last"].date()))
    news = None
    if g is not None:
        cnt, share, tot = [], [], []
        for lb in labels:
            a_, b_ = lb.split(" ~ ")
            seg = g[(g.index >= a_) & (g.index <= b_)]
            cnt.append(int(seg["Article Count"].sum()))
            tot.append(float(seg["Total Monitored Articles"].sum()))
            share.append(seg["Article Count"].sum() / max(1, seg["Total Monitored Articles"].sum()))
        base = float(np.median(share[:12])) or 1e-12
        # GDELT 가 그 구간에 본 전체 기사 수가 평소(가운데 값)의 절반도 안 되면 자료가 얇은 구간 — 몫이 부풀려지므로 값을 비운다(2026-09 뒤 전체 수가 크게 줆)
        thin = [v < 0.5 * float(np.median(tot)) for v in tot]
        nx = [None if th else round(v / base, 2) for v, th in zip(share, thin)]
        series.insert(2, {"name": "기사 수", "unit": "배", "dec": 1, "pts": [[v, None, None] for v in nx], "noband": 1})
        news = {"query": opt.get("news"), "cnt": cnt, "first": first_on([0 if v is None else v for v in nx], 1.5), "thin": [labels[p][:7] for p in range(np_) if thin[p]], "base": round(float(np.median(cnt[:12])), 1)}
    nz = lambda a: [0 if v is None else v for v in a]
    first = {"돌 3일": first_on(nz(st), 3), "주가 +30%": first_on(nz(px), 1.3), "거래 주식 수 1.5배": first_on(nz(vx), 1.5)}
    if news:
        first["기사 수 1.5배"] = news["first"]
    SI = next(i for i, s_ in enumerate(series) if s_["name"] == "예고 없는 돌 수")
    VI = next(i for i, s_ in enumerate(series) if s_["name"] == "거래 주식 수")
    # 돌이 잦았던 때 = 돌 수가 범위 위 끝을 넘은 구간이 2구간 넘게 이어진 덩어리
    busy, cur = [], None
    for p in range(np_):
        v, hi = series[SI]["pts"][p][0], series[SI]["pts"][p][2]
        if v is not None and v > hi:
            cur = cur or [p, p]
            cur[1] = p
        else:
            if cur and cur[1] > cur[0]:
                busy.append(cur)
            cur = None
    if cur and cur[1] > cur[0]:
        busy.append(cur)
    runs = []
    for a, b in busy:
        p0 = px[a - 1] if a and px[a - 1] is not None else px[a]
        runs.append({"a": a, "b": b, "px0": p0, "px1": px[b], "pmax": max(px[a:b + 1]), "pmin": min(px[a:b + 1]),
                     "vol": round(float(np.median(vx[a:b + 1])), 1), "volhi": round(float(np.median([series[VI]["pts"][p][2] for p in range(a, b + 1)])), 1),
                     "st": int(sum(st[a:b + 1])), "open": b == np_ - 1,
                     "news": round(float(np.median([pt[0] for pt in series[2]["pts"][a:b + 1] if pt[0] is not None] or [0])), 1) if news else None,
                     "ncnt": int(sum(c for c, pt in zip(news["cnt"][a:b + 1], series[2]["pts"][a:b + 1]) if pt[0] is not None)) if news else None})
    eg = R["earn"][R["earn"]["sym"] == sym]
    eps = []
    for e in LF.episodes(sym, R["bars"][sym], eg, R["waves"]):
        eps.append({"start": str(e["start"].date()), "len": int(e["len"]), "end": str(e["end"].date()) if "end" in e else None, "kind": e.get("kind"),
                    "stone": None if e.get("stone") is None or e["stone"] != e["stone"] else round(float(e["stone"]), 1),
                    "runup": None if e["runup"] != e["runup"] else round(float(e["runup"])), "fall": int(e["fall_days"]) if "fall_days" in e else None})
    data = {"sym": sym, "ko": me["k"] or sym, "labels": labels, "last": str(R["last"].date()), "series": series, "first": first, "runs": runs, "eps": eps, "nkids": len(rows), "news": news, "wiki": wiki}
    head = open(os.path.join(HERE, "look_band_page.html"), encoding="utf-8").read()
    head = re.sub(r"<title>.*?</title>", f"<title>{data['ko']} 개성이 태어난 때</title>", head[:head.index("</style>")])
    page = open(os.path.join(HERE, "look_born_page.html"), encoding="utf-8").read()
    out = os.path.join(HERE, "output", f"mock_born_{sym}.html")
    open(out, "w", encoding="utf-8").write(head + page.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
    ym = lambda p: labels[p][:7] if p is not None else "없음"
    print(f"화면 → {out}")
    print("  처음 넘은 때: " + " · ".join(f"{k} {ym(v)}" for k, v in first.items()))
    for r in runs:
        print(f"  돌이 잦았던 때 {ym(r['a'])} ~ {labels[r['b']][13:20]} · 돌 {r['st']}일 · 주가 {r['px0']:.2f} → {r['px1']:.2f}배 · 거래 {r['vol']}배(범위 위 끝 {r['volhi']})")
    for e in eps:
        print(f"  민감 구간 {e['start']} {e['len']}일 → 끝 {e['end']} {e['kind']} {e['stone']} · 앞 120일 {e['runup']}%")


if __name__ == "__main__":
    main()
