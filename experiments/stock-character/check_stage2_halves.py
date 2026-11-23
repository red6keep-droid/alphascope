"""종목 특성 2단계 — 홀짝 반쪽 확인 (2026-11-23 사용자 "홀짝 확인 먼저 해").

질문: 2단계 축의 구간끼리 순위 상관이 낮은 것이 ① 표본이 적어 잴 수 없어서인가 ② 시기마다 바뀌는 상태라서인가.
방법: 같은 종목 · 같은 3년 구간 안의 돌(실적일)을 날짜 순으로 번갈아 홀 · 짝 두 반쪽으로 나눠 축을 따로 재고,
      종목들 사이에서 두 반쪽 순위 상관을 낸다. 잦기는 돌을 나누면 반쪽 개수가 같아지므로 홀수 달 · 짝수 달로 나눈다.
      반쪽은 표본이 절반이라 스피어만-브라운 보정(2r ÷ (1 + r))으로 온 구간 신뢰도를 어림한다.
읽는 법: 신뢰도 = 한 구간 안에서 잰 값이 얼마나 믿을 만한가(잴 수 있는 상한). 구간끼리 상관은 이 상한을 넘을 수 없다.
  신뢰도 < 0.3                        → 잴 수 없음(표본이 적음) — 특성인지 아닌지 모른다
  신뢰도 ≥ 0.3, 구간끼리 < 신뢰도 × 0.5 → 상태(한 구간 안에선 일관, 구간이 바뀌면 달라짐)
  그 밖                               → 특성 쪽(잴 수 있는 만큼 이어짐)
여운은 돌 없는 날 비교 대상을 빼지 않은 값으로 잰다(같은 값을 두 반쪽에서 빼면 반쪽끼리 상관이 부풀려진다).

    python experiments/stock-character/check_stage2_halves.py    # check_stage2.py 를 먼저 돌려 일봉 · 실적일 캐시가 있어야 한다

결과 = 비공개 alphascope-docs/doc/검증/종목-특성-2단계-결과.md 5절(이 절만 다시 쓴다). AI 0 · 수집 0.
"""

import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_stage1 as s1  # noqa: E402
import check_stage2 as s2  # noqa: E402

MIN_HALF = 4                   # 반쪽에 돌 4개(온 구간 8개 기준의 절반)
MIN_HALF_OWN, MIN_HALF_EARN = 3, 3
AXES = [("n_stone", "④ 돌 잦기"), ("x_stone", "④ 돌 크기"), ("n_own", "④ 나머지 돌 잦기"),
        ("aft1", "⑤ 여운 1일"), ("aft5", "⑤ 여운 5일"), ("aft20", "⑤ 여운 20일"), ("calm", "⑤ 가라앉는 날 수"),
        ("sh_mkt", "⑥ 시장 돌 몫"), ("sh_sec", "⑥ 업종 돌 몫"), ("sh_own", "⑥ 종목 돌 몫"),
        ("sched", "⑥ 종목 자체 돌 중 실적일 몫"), ("hidden", "⑥ 숨은 종목 돌 몫"), ("earn_x", "⑥ 실적일 움직임")]


def half_values(sb, eb, days):
    """한 종목 · 한 구간 → {0: 축 값, 1: 축 값}. sb = 그 구간 돌, eb = 그 구간 실적일, days = 그 구간 거래일."""
    out = {0: {}, 1: {}}
    mpar = (days.month % 2).values
    for h in (0, 1):
        nd = int((mpar == h).sum())
        if nd > 50:
            mm = (sb.date.dt.month % 2 == h)
            out[h]["n_stone"] = int((sb.raw & mm).sum()) / nd * 252
            out[h]["n_own"] = int((sb.own & mm).sum()) / nd * 252
    rw = sb[sb.raw].sort_values("date").reset_index(drop=True)
    ow = sb[sb.own].sort_values("date").reset_index(drop=True)
    for h in (0, 1):
        r = rw.iloc[h::2]
        if len(r) >= 2:
            out[h]["x_stone"] = float(r.x.median())
        if len(r) >= MIN_HALF:
            for k in s2.HS:
                out[h][f"aft{k}"] = float(r[f"aft{k}"].mean())
            out[h]["calm"] = float(r.calm.median())
            out[h]["sh_mkt"] = float((r.src == "mkt").mean())
            out[h]["sh_sec"] = float((r.src == "sec").mean())
            out[h]["sh_own"] = float(r.own.mean())
        o = ow.iloc[h::2]
        if len(o) >= MIN_HALF_OWN:
            out[h]["sched"] = float(o.sched.mean())
            out[h]["hidden"] = float((o.src == "hidden").mean())
        if len(eb):
            e = eb.sort_values("date").iloc[h::2]
            if len(e) >= MIN_HALF_EARN:
                out[h]["earn_x"] = float(e.x.median())
    return out


def run(mkt, U):
    uni = U[mkt]
    benches = sorted({v["bench"] for v in uni.values()})
    bars = s1.load_bars(mkt, list(uni) + benches, False)
    earn = s2.load_earn(mkt)
    df, S, E, _, _, end = s2.measure(mkt, uni, bars, earn)
    S["date"] = pd.to_datetime(S["date"])
    E["date"] = pd.to_datetime(E["date"])
    Sg, Eg = dict(tuple(S.groupby("sym"))), dict(tuple(E.groupby("sym")))
    rows = []
    for name, s0, e0 in s1.blocks(end, 3):
        for s in df[df.block == name].sym:
            d = bars[s]
            days = d.index[(d.index >= s0) & (d.index <= e0)]
            sb = Sg.get(s, S.iloc[:0])
            sb = sb[(sb.date >= s0) & (sb.date <= e0)]
            eb = Eg.get(s, E.iloc[:0])
            eb = eb[(eb.date >= s0) & (eb.date <= e0)]
            hv = half_values(sb, eb, days)
            for h in (0, 1):
                rows.append({"block": name, "start": s0, "sym": s, "half": h, **hv[h]})
    H = pd.DataFrame(rows)
    s2_metrics = [(c, l) for c, l in s2.METRICS]
    s1.METRICS = s2_metrics
    J = s1.judge(df).set_index("axis")
    names = sorted(H.block.unique(), key=lambda n: H[H.block == n].start.iloc[0], reverse=True)
    out = []
    for col, lbl in AXES:
        rs, ns = [], []
        for n in names:
            b = H[H.block == n]
            if col not in b:
                continue
            a = b[b.half == 0].set_index("sym")[col]
            c = b[b.half == 1].set_index("sym")[col]
            r, k = s1.spearman(a, c)
            if not np.isnan(r):
                rs.append(r); ns.append(k)
        r_recent = rs[0] if rs else np.nan
        r_mean = float(np.mean(rs)) if rs else np.nan
        rel = lambda r: 2 * r / (1 + r) if not np.isnan(r) and r > -0.99 else np.nan
        cross = J.loc[col, "mean"] if col in J.index else np.nan
        relm = rel(r_mean)
        if np.isnan(relm) or relm < 0.3:
            verdict = "잴 수 없음(표본)"
        elif np.isnan(cross) or cross < relm * 0.5:
            verdict = "상태(구간마다 바뀜)"
        else:
            verdict = "특성 쪽"
        out.append({"axis": col, "label": lbl, "half_recent": r_recent, "half_mean": r_mean, "n": ns[0] if ns else 0,
                    "rel": relm, "cross_recent": J.loc[col, "recent"] if col in J.index else np.nan, "cross_mean": cross, "verdict": verdict})
    return pd.DataFrame(out)


def write(res):
    f2 = s1.f2
    L = ["\n## 5. 홀짝 반쪽 확인 — 잴 수 없어서인가, 시기마다 바뀌어서인가\n",
         "(스크립트 `check_stage2_halves.py` 가 이 절만 쓴다 · 2026-11-23 사용자 \"홀짝 확인 먼저 해\")\n",
         "같은 3년 구간 안의 돌(실적일)을 날짜 순으로 번갈아 두 반쪽으로 나눠 종목 순위가 맞는지 잰다. 잦기는 홀수 달 · 짝수 달로 나눈다. "
         "신뢰도 = 반쪽 상관을 온 구간으로 보정한 값(스피어만-브라운) = 한 구간 안에서 잴 수 있는 상한. 구간끼리 상관은 이 상한을 넘을 수 없다.\n",
         "판정: 신뢰도 < 0.3 → 잴 수 없음(표본) · 구간끼리 평균 < 신뢰도 × 0.5 → 상태(구간마다 바뀜) · 그 밖 → 특성 쪽. "
         "여운은 돌 없는 날 비교 대상을 빼지 않고 잰다(두 반쪽에서 같은 값을 빼면 반쪽 상관이 부풀려짐).\n"]
    for mkt in ("us", "kr"):
        R = res[mkt]
        L.append(f"### {'미국' if mkt == 'us' else '한국'}\n")
        L.append("| 축 | 반쪽 상관 최근 | 반쪽 상관 평균 | 종목 수 | 신뢰도(보정) | 구간끼리 최근 | 구간끼리 평균 | 판정 |\n|---|---:|---:|---:|---:|---:|---:|---|")
        for _, x in R.iterrows():
            L.append(f"| {x['label']} | {f2(x['half_recent'])} | {f2(x['half_mean'])} | {x['n']} | {f2(x['rel'])} | {f2(x['cross_recent'])} | {f2(x['cross_mean'])} | {x['verdict']} |")
        L.append("")
    text = "\n".join(L)
    doc = open(s2.DOC, encoding="utf-8").read()
    head = "\n## 5. 홀짝 반쪽 확인"
    keep_tail = ""
    if head in doc:
        before, after = doc.split(head, 1)
        nxt = after.find("\n## 6.")
        keep_tail = after[nxt:] if nxt >= 0 else ""
        doc = before
    open(s2.DOC, "w", encoding="utf-8").write(doc.rstrip() + "\n" + text + keep_tail)
    print(text)
    print(f"문서 → {s2.DOC}")


def main():
    s1.LENGTHS = [3]
    U = s1.universe()
    res = {m: run(m, U) for m in ("us", "kr")}
    write(res)


if __name__ == "__main__":
    main()
