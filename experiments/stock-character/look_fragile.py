"""뉴팩트 개성 있는 아이 찾기 게임 — 가설 2 다시: 민감 상태가 어떻게 끝났나 (2026-11-24 사용자 "순서대로 해").

길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md 7-12 · 7-13.
사용자 가설: 실적보다 돈이 많이 들어오면 거품 → 차익 실현으로 갑자기 폭락. 전고점 근처에 오래 머문 민감 상태에서는 작은 자극에도 쉽게 폭락.
7-12 첫 눈길은 "민감한 날의 내림 돌 횟수"를 셌다가 반대로 나왔다(한 번 떨어지면 상태에서 나가 버려 한쪽으로 기움). 여기서는 구간 하나하나가 **어떻게 끝났나**를 본다.

    python experiments/stock-character/look_fragile.py

민감 구간 = 종가가 최근 250일 고점의 10% 안에 20거래일 넘게 이어 머문 구간(최근 3년에 끝났거나 아직 이어지는 것).
끝 = 종가가 고점의 90% 아래로 내려간 첫날.
  빠르기      구간 안 마지막 고점 날 → 끝난 날까지 거래일. 갑자기 = 5일 이내 · 서서히 = 20일 넘게 · 그 사이 = 중간
  끝낸 돌      끝나기 전 5거래일 안의 가장 큰 하루 내림(−5% 이하일 때): 정해진 돌(실적) / 파도 돌 / 예고 없는 돌 / 돌 없이 끝남
  끝난 뒤      끝난 날부터 20거래일 안 가장 낮은 종가까지 더 내린 폭 · 60거래일 안에 다시 민감 구간 고점을 넘었나
  지속 기간    구간 길이(거래일) — 사용자 "전고점 도달 상태 지속 기간"
  들어오기 전 상승  구간 시작 전 120거래일 등락 — 거품 대신 보는 값(과거 재무 값이 없어서)
그림 = output/graphs/fragile_faces.png — 예고 없는 돌로 갑자기 끝난 구간들(끝난 날 앞뒤 60일, 아래 = 거래량 배수).
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
STORE = os.path.join(ROOT, "data", "store", "character")
OUT = os.path.join(HERE, "output", "graphs")
sys.path.insert(0, HERE)
import look_stones as LS  # noqa: E402
import look_money as LM  # noqa: E402

NEAR, STAY = 0.10, 20
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


def episodes(s, d, edays, waves):
    d = d[(d["open"] > 0) & (d["volume"] > 0)]
    c, idx = d["close"], d.index
    if len(c) < LS.DAYS + 400:
        return []
    ret = (c.pct_change() * 100).values
    hi = c.rolling(250, min_periods=120).max()
    near = (c >= hi * (1 - NEAR)).values
    sched = set()
    for _, e in edays.iterrows():
        p = idx.searchsorted(e["day"])
        if p < len(idx) and idx[p] == e["day"] and e["after_close"] == 1:
            p += 1
        sched.update((p, p + 1))
    out, n0, i, n = [], len(idx) - LS.DAYS, 0, len(idx)
    while i < n:
        if not near[i]:
            i += 1; continue
        j = i
        while j < n and near[j]:
            j += 1
        if j - i >= STAY and (j >= n0):                      # 최근 3년에 끝났거나 아직 이어짐
            seg = c.iloc[i:j]
            pk = int(np.argmax(seg.values)) + i
            ep = {"sym": s, "start": idx[i], "len": j - i, "peak_day": idx[pk], "ongoing": j >= n,
                  "runup": (c.iloc[i] / c.iloc[i - 120] - 1) * 100 if i >= 120 else np.nan}
            if j < n:
                ep["end"] = idx[j]
                ep["fall_days"] = j - pk
                win = range(max(pk, j - 5), j + 1)
                k = min(win, key=lambda q: ret[q])
                if ret[k] <= -LS.STONE:
                    ep["stone"], ep["stone_day"] = ret[k], idx[k]
                    ep["kind"] = "정해진" if k in sched else "파도" if idx[k] in waves else "예고 없는"
                else:
                    ep["stone"], ep["kind"] = np.nan, "돌 없이"
                after = c.iloc[j:j + 21]
                ep["more"] = (after.min() / c.iloc[j] - 1) * 100 if len(after) > 5 else np.nan
                top = seg.max()
                fut = c.iloc[j:j + 61]
                ep["back60"] = bool((fut > top).any()) if len(fut) >= 60 else None
                ep["_j"] = j
            out.append(ep)
        i = j
    for e in out:
        e["_d"] = d
    return out


def speed(x):
    return "갑자기" if x <= 5 else "서서히" if x > 20 else "중간"


def main():
    bars = pd.read_pickle(os.path.join(STORE, "bars_us.pkl"))
    earn = pd.read_csv(os.path.join(STORE, "earn_days_us.csv"), parse_dates=["day"])
    eg = {s: g for s, g in earn.groupby("sym")}
    C = pd.DataFrame({s: d["close"] for s, d in bars.items() if not s.startswith("^")})
    hit = C.pct_change().abs() * 100 >= LS.STONE
    share = (hit.sum(axis=1) / C.notna().sum(axis=1)).iloc[-LS.DAYS:]
    waves = set(share[share >= LS.WAVE_SHARE].index)
    grp = {s: g for g, syms in LM.GROUPS.items() for s in syms}
    eps = []
    for s in C.columns:
        if s in eg:
            for e in episodes(s, bars[s], eg[s], waves):
                e["group"] = grp.get(s, "그 밖")
                eps.append(e)
    E = pd.DataFrame([{k: v for k, v in e.items() if not k.startswith("_")} for e in eps])
    done = E[~E.ongoing].copy()
    done["speed"] = done.fall_days.map(speed)
    print(f"민감 구간 {len(E)}개 (끝난 것 {len(done)} · 지금 이어지는 것 {int(E.ongoing.sum())}) · 종목 {E.sym.nunique()}개 · 최근 3년")

    print("\n=== 묶음별 — 끝난 구간이 어떻게 끝났나 (배경용 요약. 주인공은 아래 이름)")
    order = ["늘 켜짐", "최근 1년에 켜짐", "켜졌다 꺼졌다", "잔잔 + 돌", "늘 잔잔", "그 밖"]
    for g in order:
        x = done[done.group == g]
        if not len(x):
            print(f"[{g}] 끝난 구간 없음"); continue
        sp = x.speed.value_counts()
        kd = x.kind.value_counts()
        print(f"[{g}] {len(x)}개 · 갑자기 {sp.get('갑자기', 0)} · 중간 {sp.get('중간', 0)} · 서서히 {sp.get('서서히', 0)} | 끝낸 돌: 예고 없는 {kd.get('예고 없는', 0)} · 정해진 {kd.get('정해진', 0)} · 파도 {kd.get('파도', 0)} · 돌 없이 {kd.get('돌 없이', 0)}"
              f" | 끝난 뒤 20일 더 내린 폭 가운데 {x.more.median():.0f}% · 60일 안 고점 회복 {int((x.back60 == True).sum())}/{int(x.back60.notna().sum())}")  # noqa: E712

    print("\n=== 지속 기간별 (모든 종목 — 오래 머물수록 갑자기 끝나나)")
    for lo, hi_, lb in ((20, 60, "20 ~ 60일"), (60, 120, "60 ~ 120일"), (120, 9999, "120일 넘게")):
        x = done[(done.len >= lo) & (done.len < hi_)]
        print(f"  {lb:10} {len(x):4}개 · 갑자기 {(x.speed == '갑자기').mean() * 100:.0f}% · 서서히 {(x.speed == '서서히').mean() * 100:.0f}% · 예고 없는 돌로 끝남 {(x.kind == '예고 없는').mean() * 100:.0f}% · "
              f"끝낸 돌 크기 가운데 {x.stone.median():.1f}% · 끝난 뒤 더 내린 폭 {x.more.median():.0f}%")
    print("=== 들어오기 전 120일 상승별 (거품 대신 보는 값)")
    for lo, hi_, lb in ((-999, 20, "20% 미만"), (20, 50, "20 ~ 50%"), (50, 9999, "50% 넘게")):
        x = done[(done.runup >= lo) & (done.runup < hi_)]
        print(f"  {lb:10} {len(x):4}개 · 갑자기 {(x.speed == '갑자기').mean() * 100:.0f}% · 서서히 {(x.speed == '서서히').mean() * 100:.0f}% · 예고 없는 돌로 끝남 {(x.kind == '예고 없는').mean() * 100:.0f}% · "
              f"끝낸 돌 크기 가운데 {x.stone.median():.1f}% · 끝난 뒤 더 내린 폭 {x.more.median():.0f}%")

    sud = done[(done.speed == "갑자기") & (done.kind == "예고 없는")].sort_values("stone")
    print(f"\n=== 예고 없는 돌로 갑자기 끝난 구간 {len(sud)}개 — 이름 · 끝난 날 · 머문 날 수 · 들어오기 전 상승 · 끝낸 돌 · 끝난 뒤 더 내림 · 60일 안 회복")
    for _, r in sud.head(30).iterrows():
        print(f"   {r.sym:6} [{r.group}] {r.end.date()} · {r.len}일 머묾 · 앞 120일 {r.runup:+.0f}% · 돌 {r.stone:.1f}% · 뒤 {r.more:.0f}% · 회복 {'예' if r.back60 else '아니오' if r.back60 is False else '아직'}")
    rep = sud.sym.value_counts()
    print("   같은 아이가 여러 번(반복): " + ", ".join(f"{s} {n}번" for s, n in rep[rep >= 2].items()))

    named = done[done.group != "그 밖"]
    print("\n=== 개성 명단 아이별 — 끝난 구간 수 · 갑자기 끝난 수 · 예고 없는 돌로 끝난 수")
    for g in order[:4]:
        x = named[named.group == g].groupby("sym").apply(lambda q: f"{len(q)}/{int((q.speed == '갑자기').sum())}/{int((q.kind == '예고 없는').sum())}")
        print(f"[{g}] " + ", ".join(f"{s} {v}" for s, v in x.items()))

    on = E[E.ongoing].sort_values("len", ascending=False)
    print(f"\n=== 지금 민감 구간에 있는 아이 {len(on)}명 (머문 날 수 긴 순, 위 25): " + ", ".join(f"{r.sym} {r.len}일" for _, r in on.head(25).iterrows()))
    print("   그중 개성 명단: " + ", ".join(f"{r.sym}[{r.group}] {r.len}일 · 앞 상승 {r.runup:+.0f}%" for _, r in on[on.group.isin(order[:3])].iterrows()))

    # 그림 — 예고 없는 돌로 갑자기 끝난 구간 16개
    pick = sud.head(16)
    byk = {(e["sym"], e.get("end")): e for e in eps if not e["ongoing"]}
    fig, axs = plt.subplots(8, 4, figsize=(22, 17), gridspec_kw={"height_ratios": [3, 1] * 4})
    for k, (_, r) in enumerate(pick.iterrows()):
        e = byk[(r.sym, r.end)]
        d, j = e["_d"], e["_j"]
        w = d.iloc[max(0, j - 90):j + 61]
        a, b = axs[(k // 4) * 2, k % 4], axs[(k // 4) * 2 + 1, k % 4]
        a.plot(w.index, w["close"], color="#1c2330", lw=1.0)
        a.axvline(r.end, color="#d0342c", lw=0.8, ls=":")
        a.axvspan(max(r.start, w.index[0]), r.end, color="#f6d9a8", alpha=0.35)
        a.set_title(f"{r.sym} [{r.group}] {r.end.date()} · {r.len}일 머묾 · 끝낸 돌 {r.stone:.1f}% · 뒤 20일 {r.more:.0f}%", fontsize=8, loc="left")
        vx = d["volume"] / d["volume"].rolling(250, min_periods=60).median()
        vx = vx.reindex(w.index)
        b.bar(w.index, vx.clip(upper=6), width=1.0, color=["#e08a00" if v >= 2 else "#c3c9d4" for v in vx.fillna(0)])
        b.set_ylim(0, 6); a.set_xticks([]); a.tick_params(labelsize=7); b.tick_params(labelsize=6)
    fig.suptitle("예고 없는 돌로 갑자기 끝난 민감 구간 (노란 띠 = 고점 10% 안에 머문 구간 · 빨간 점선 = 끝난 날 · 아래 = 거래량 배수)", x=0.01, ha="left", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, "fragile_faces.png"), dpi=85)
    E.round(2).to_csv(os.path.join(STORE, "fragile_us.csv"), index=False)


if __name__ == "__main__":
    main()
