"""뉴팩트 개성 있는 아이 찾기 게임 (A 갈래 · 2단계 후보 명단) — 예고 없는 돌, S&P 500 (2026-11-24 사용자 "지금 그렇게 해").

길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md 0-6 점검표 · 7-10.
돌 = 하루 ±5% (모든 종목 같은 잣대). 정해진 돌 = 실적 반응 날과 그다음 날. 파도 돌 = 그날 무리의 20% 넘는 종목에 돌이 떨어진 날(시장 전체가 흔들린 날 —
파도는 종목 특성을 무너뜨리므로 따로 뺀다, 길잡이 3-1). **예고 없는 돌 = 그 밖의 날의 돌.**
이 스크립트는 명단을 뽑는다 — 명단에 없다고 평범이라는 뜻이 아니다(점검표 7).

    python experiments/stock-character/look_stones.py

종목마다(최근 3년):
  예고 없는 돌 수 · 그중 거래량 실린 비율(250일 중앙값의 2배) · 20일 안에 돌 전 자리로 돌아온 비율
  켜진 조각 수 = 3년을 60거래일 조각 12개로 나눠 예고 없는 돌이 2개 넘게 떨어진 조각 수 (반복 · 언제)
  호수 = 하루 폭 중앙값
명단 둘: ① 예고 없는 돌이 많은 아이 ② 호수는 잔잔한데(무리 아래쪽 절반) 예고 없는 돌이 떨어지는 아이(조합 — 점검표 9)
그림: output/graphs/stones_sorted.png(줄 세움) · stones_faces.png(뽑힌 아이들 그래프 — 빨강 = 예고 없는 돌, 회색 = 정해진 돌, 아래 = 거래량)
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
STORE = os.path.join(ROOT, "data", "store", "character")
OUT = os.path.join(HERE, "output", "graphs")
DAYS, PIECE, STONE, VOL2 = 756, 60, 5.0, 2.0
WAVE_SHARE = 0.20   # 그날 무리의 20% 넘게 돌 = 파도 날
MARK = ["TSLA", "MSFT", "JPM", "KO", "NVDA", "AMD"]
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def sched_days(idx, edays):
    """정해진 돌로 치는 날(위치) — 공시 접수일 당일 · 다음 거래일, 16시 뒤 접수면 그다음 날까지.
    2026-11-24: 접수일 당일을 넣음 — 찰스 슈왑처럼 아침에 발표하고 공시는 16시 넘어 접수하는 회사의 진짜 반응 날이 예고 없는 돌로 잡혔다."""
    out = set()
    for _, e in edays.iterrows():
        p = idx.searchsorted(e["day"])
        out.update((p, p + 1))
        if p < len(idx) and idx[p] == e["day"] and e["after_close"] == 1:
            out.add(p + 2)
    return out


def react_days(idx, ret, edays, start):
    """실적 반응 날(위치) 목록 + 이 회사가 `아침 발표 · 오후 접수`로 보이는지.
    16시 뒤 접수한 발표들에서 접수 당일 등락 크기 가운데 값이 다음 날의 1.5배 이상이면(4번 넘게 있을 때) 당일을 반응 날로 본다. 아니면 다음 거래일."""
    rows = []
    for _, e in edays.iterrows():
        p = idx.searchsorted(e["day"])
        if p >= len(idx):
            continue
        rows.append((p, bool(idx[p] == e["day"] and e["after_close"] == 1)))
    late = [p for p, ac in rows if ac and idx[p] >= start and p + 1 < len(idx)]
    early = False
    if len(late) >= 4:
        a0 = np.nanmedian([abs(ret[p]) for p in late])
        a1 = np.nanmedian([abs(ret[p + 1]) for p in late])
        early = bool(a0 >= 1.5 * a1)
    pos = [p if (not ac or early) else p + 1 for p, ac in rows]
    return [p for p in pos if p < len(idx)], early


def profile(s, d, edays, waves):
    d = d[(d["open"] > 0) & (d["volume"] > 0)]
    if len(d) < DAYS + 260:
        return None
    c, idx = d["close"], d.index
    ret = (c.pct_change() * 100).values
    volx = (d["volume"] / d["volume"].rolling(250, min_periods=60).median()).values
    rng = ((d["high"] - d["low"]) / c * 100).values
    sched = sched_days(idx, edays)
    n0 = len(idx) - DAYS
    st = [i for i in range(n0, len(idx)) if abs(ret[i]) >= STONE]
    wv = [i for i in st if idx[i] in waves and i not in sched]
    un = [i for i in st if i not in sched and idx[i] not in waves]
    back = []
    for i in un:
        if i + 20 >= len(idx):
            continue
        pre, after = c.iloc[i - 1], c.iloc[i + 1:i + 21]
        back.append(bool((after >= pre).any() if ret[i] < 0 else (after <= pre).any()))
    pieces = [sum(1 for i in un if n0 + k * PIECE <= i < n0 + (k + 1) * PIECE) for k in range(DAYS // PIECE)]
    return {"sym": s, "lake": float(np.median(rng[n0:])), "stones": len(st), "sched": len(st) - len(un) - len(wv), "wave": len(wv), "un": len(un),
            "un_vol": float(np.mean([volx[i] >= VOL2 for i in un])) if un else np.nan,
            "un_back": float(np.mean(back)) if back else np.nan, "on_pieces": sum(x >= 2 for x in pieces), "pieces": pieces,
            "_d": d.iloc[n0:], "_un": [idx[i] for i in un], "_sc": [idx[i] for i in st if i in sched], "_wv": [idx[i] for i in wv]}


def face(axp, axv, r):
    d = r["_d"]
    axp.plot(d.index, d["close"], color="#1c2330", lw=0.9)
    axp.set_yscale("log")
    axp.scatter(r["_sc"], d["close"].reindex(r["_sc"]), s=14, color="#9aa3b2", zorder=3)
    axp.scatter(r["_wv"], d["close"].reindex(r["_wv"]), s=14, color="#2f6fdb", zorder=3)
    axp.scatter(r["_un"], d["close"].reindex(r["_un"]), s=14, color="#d0342c", zorder=4)
    vx = d["volume"] / d["volume"].rolling(250, min_periods=60).median()
    axv.bar(d.index, vx.clip(upper=6), width=1.5, color=["#e08a00" if v >= 2 else "#c3c9d4" for v in vx.fillna(0)])
    axv.set_ylim(0, 6)
    axp.set_title(f"{r['sym']} · 호수 {r['lake']:.1f}% · 예고 없는 돌 {r['un']} (정해진 {r['sched']} · 파도 {r['wave']}) · 켜진 조각 {r['on_pieces']}/12 · "
                  f"거래량 실림 {r['un_vol'] * 100:.0f}% · 되돌림 {r['un_back'] * 100:.0f}%", fontsize=8, loc="left")
    axp.set_xticks([]); axp.set_yticks([], minor=True); axp.tick_params(labelsize=7); axv.tick_params(labelsize=7)


def main():
    bars = pd.read_pickle(os.path.join(STORE, "bars_us.pkl"))
    earn = pd.read_csv(os.path.join(STORE, "earn_days_us.csv"), parse_dates=["day"])
    eg = {s: g for s, g in earn.groupby("sym")}
    C = pd.DataFrame({s: d["close"] for s, d in bars.items() if not s.startswith("^")})
    hit = (C.pct_change().abs() * 100 >= STONE)
    share = (hit.sum(axis=1) / C.notna().sum(axis=1)).iloc[-DAYS:]
    waves = set(share[share >= WAVE_SHARE].index)
    print(f"파도 날(그날 무리의 {int(WAVE_SHARE * 100)}% 넘게 돌) {len(waves)}일: " + ", ".join(f"{d.date()}({share[d] * 100:.0f}%)" for d in sorted(waves)))
    rows = [r for s, d in bars.items() if not s.startswith("^") and s in eg and (r := profile(s, d, eg[s], waves))]
    R = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]).set_index("sym")
    by = {r["sym"]: r for r in rows}
    med = R.un.median()
    mad = max((R.un - med).abs().median() * 1.4826, 1.0)
    R["z"] = (R.un - med) / mad
    R["lake_pct"] = R.lake.rank(pct=True)
    print(f"종목 {len(R)}개 · 최근 3년 · 무리 한가운데 = 예고 없는 돌 {med:.0f}개 · 무리 폭 {mad:.1f}")
    print(f"무리에서 3폭 넘게 위 {int((R.z > 3).sum())}종목 · 5폭 넘게 위 {int((R.z > 5).sum())}종목 · 예고 없는 돌이 0개인 종목 {int((R.un == 0).sum())}")

    far = R[R.z > 5].sort_values("un", ascending=False)
    print(f"\n① 예고 없는 돌이 아주 많은 아이 (5폭 넘게 위, {len(far)}명) — 이름 · 돌 수 · 켜진 조각/12 · 호수 · 거래량 실림 · 되돌림")
    def shape(pc):
        a, b = sum(pc[:8]), sum(pc[8:])          # 앞 2년(8조각) · 최근 1년(4조각)
        if sum(x >= 2 for x in pc) >= 11:
            return "늘 켜짐"
        if b / 4 >= 3 * max(a / 8, 0.5):
            return "최근 1년에 켜짐"
        if a / 8 >= 3 * max(b / 4, 0.5):
            return "최근 1년에 꺼짐"
        return "켜졌다 꺼졌다"
    far = far.assign(shape=[shape(by[s]["pieces"]) for s in far.index])
    for sh in ("늘 켜짐", "최근 1년에 켜짐", "최근 1년에 꺼짐", "켜졌다 꺼졌다"):
        g = far[far["shape"] == sh]
        print(f"   [{sh}] {len(g)}명: " + ", ".join(f"{s} {r.un:.0f}" for s, r in g.iterrows()))
    for s, r in far.head(6).iterrows():
        print(f"   {s:6} {r.un:4.0f}개 · {r.on_pieces:2.0f}/12 · 호수 {r.lake:.1f}% · 거래량 {r.un_vol * 100:3.0f}% · 되돌림 {r.un_back * 100:3.0f}% · 조각별 {by[s]['pieces']}")
    for s in ("TSLA", "GLW", "STX", "MU"):
        if s in far.index:
            print(f"   {s:6} [{far['shape'][s]}] 조각별 {by[s]['pieces']}")
    mid = R[(R.z > 3) & (R.z <= 5)].sort_values("un", ascending=False)
    print(f"\n   꽤 많은 아이 (3 ~ 5폭, {len(mid)}명): " + ", ".join(f"{s} {r.un:.0f}" for s, r in mid.iterrows()))

    calm = R[(R.lake_pct <= 0.5) & (R.un >= 4)].sort_values(["un", "on_pieces"], ascending=False)
    print(f"\n② 호수는 잔잔한데(무리 아래쪽 절반) 예고 없는 돌이 4개 넘게 떨어진 아이 ({len(calm)}명)")
    for s, r in calm.head(15).iterrows():
        print(f"   {s:6} {r.un:3.0f}개 · {r.on_pieces:.0f}/12 · 호수 {r.lake:.1f}%(아래에서 {r.lake_pct * 100:.0f}%) · 거래량 {r.un_vol * 100:3.0f}% · 되돌림 {r.un_back * 100:3.0f}% · 조각별 {by[s]['pieces']}")

    burst = R[(R.un >= 6) & (R.on_pieces <= 2)].sort_values("un", ascending=False)
    print(f"\n③ 한두 조각에만 몰려 떨어진 아이 (돌 6개 넘는데 켜진 조각 2 이하, {len(burst)}명): "
          + ", ".join(f"{s} {r.un:.0f}개 {by[s]['pieces']}" for s, r in burst.head(8).iterrows()))
    print("\n표시 종목: " + " | ".join(f"{s} 예고 없는 {R.un[s]:.0f} · 정해진 {R.sched[s]:.0f} · 켜진 조각 {R.on_pieces[s]:.0f}/12 · 조각별 {by[s]['pieces']}" for s in MARK if s in R.index))

    os.makedirs(OUT, exist_ok=True)
    v = R.un.sort_values()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(range(len(v)), v.values, color="#1c2330", lw=1.2)
    for k, col in ((3, "#e08a00"), (5, "#d0342c")):
        ax.axhline(med + k * mad, color=col, lw=0.6, ls=":")
    for s in MARK:
        if s in v.index:
            p = list(v.index).index(s)
            ax.scatter([p], [v[s]], s=26, zorder=3); ax.annotate(s, (p, v[s]), fontsize=8, xytext=(-26, 6), textcoords="offset points")
    ax.set_title("예고 없는 돌(실적일이 아닌 날의 ±5%) 수 · 최근 3년 · S&P 500 줄 세움 (주황 = 3폭 · 빨강 = 5폭)", fontsize=10, loc="left")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "stones_sorted.png"), dpi=100); plt.close(fig)

    picks = list(far.index[:8]) + list(calm.index[:6]) + list(burst.index[:2])
    picks = list(dict.fromkeys(picks))[:16]
    fig, axs = plt.subplots(8, 4, figsize=(22, 17), gridspec_kw={"height_ratios": [3, 1] * 4})
    for k, s in enumerate(picks):
        face(axs[(k // 4) * 2, k % 4], axs[(k // 4) * 2 + 1, k % 4], by[s])
    for k in range(len(picks), 16):
        axs[(k // 4) * 2, k % 4].axis("off"); axs[(k // 4) * 2 + 1, k % 4].axis("off")
    fig.suptitle("뽑힌 아이들 — 1 · 2줄 = 예고 없는 돌이 아주 많은 아이, 3줄부터 = 호수는 잔잔한데 돌이 떨어지는 아이 · 한두 조각에 몰린 아이 (빨강 = 예고 없는 돌 · 회색 = 정해진 돌 · 파랑 = 파도 날 돌 · 아래 = 거래량 배수)",
                 x=0.01, ha="left", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.97)); fig.savefig(os.path.join(OUT, "stones_faces.png"), dpi=85); plt.close(fig)
    R.drop(columns=["pieces"]).round(3).to_csv(os.path.join(STORE, "stones_us.csv"))
    print("\n그림 →", OUT)


if __name__ == "__main__":
    main()
