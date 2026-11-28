"""상승 중 신용 갈림 검증 V10 — 시장이 상승 자리(최고점 대비 −10% 안)인데 신용 가산금리가 벌어지는 중이면,
뒤 여섯 달 안에 −10% 넘게 빠지는 일이 잦았나. 기준은 비공개 doc/기획/거시-흐름-지도.md 5-2 절 V10 (돌리기 전 고정).

    .venv/bin/python experiments/issue_store/uptrend_credit_check.py

- 자리 = cycle_position_check.positions (V8 정의 그대로).
- 조건 C = 상승 자리 그리고 Baa 회사채 가산금리(BAA10Y_long, 전날 값) 60거래일 +0.35%p 이상 (금리 · 신용 국면 검증 ③ B1 과 같은 선).
- 조건 H = 상승 자리 그리고 하이일드 대리(HYG ÷ IEI) 60거래일 변화가 2007 ~ 분포 아래 10% (B1 이 Baa 변화 위 10% 쯤이라 같은 드묾으로).
- 결과 = 뒤 63 · 126거래일 수익률 · 창 안 −10% 넘게 빠짐. 사건 = 조건이 63거래일 넘게 꺼졌다 다시 켜진 첫날.
- 비교 대상 둘: ① 상승 자리의 아무 날(같은 자리에서 조건만 다를 때) ② 같은 기간 아무 날. 플라시보 2,000번 · 앞뒤 절반.
결과: experiments/issue_store/results/uptrend_credit.md (깃 밖).
"""
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from normal_range import load_close  # noqa: E402
from cycle_position_check import positions, forward, episodes, GAP  # noqa: E402

FRED = os.path.join(os.path.abspath(os.path.join(_HERE, "..", "..")), "data", "store", "fred")
OUT = os.path.join(_HERE, "results")
HS = (63, 126)
NBOOT = 2000
rng = np.random.default_rng(20261128)


def spaced_random(k, valid):
    picks = []
    for i in rng.permutation(valid):
        if all(abs(i - j) > GAP for j in picks):
            picks.append(i)
            if len(picks) >= k:
                break
    return np.array(picks)


def boot_p(obs, k, pool, stat):
    b = np.array([stat(spaced_random(k, pool)) for _ in range(NBOOT)])
    return min(1.0, 2 * min((b >= obs).mean(), (b <= obs).mean()))


def main():
    spx = load_close("^GSPC")
    vix = load_close("^VIX")
    pos = positions(spx, vix)
    d = pd.read_csv(os.path.join(FRED, "BAA10Y_long.csv"))
    baa = pd.Series(d["value"].astype(float).values, pd.to_datetime(d["day"]))
    baa = baa[~baa.index.duplicated()].sort_index()
    baa = baa.reindex(baa.index.union(spx.index)).ffill(limit=5).reindex(spx.index)
    baa[baa.index < pd.Timestamp("1986-01-02")] = np.nan
    baa_chg = baa.shift(1) - baa.shift(61)
    ratio = (load_close("HYG") / load_close("IEI")).reindex(spx.index)
    hy_chg = ratio / ratio.shift(60) - 1
    hy_cut = hy_chg.dropna().quantile(0.10)
    fw = forward(spx)
    up = (pos == "상승").values
    n = len(spx)

    conds = {
        "C Baa 60일 +0.35%p 이상": (baa_chg >= 0.35).values & up, "기간_C": baa_chg.notna().values & (spx.index >= "1990-01-02"),
        "H 하이일드 대리 60일 아래 10%": (hy_chg < hy_cut).values & up, "기간_H": hy_chg.notna().values,
    }
    lines = ["# 상승 중 신용 갈림 V10", "", f"자료 끝 {spx.index[-1].date()} · 하이일드 대리 아래 10% 선 = 60일 {hy_cut * 100:.2f}%", "",
             "| 조건 | 창 | 기간 | 사건 | 오른 사건 | 상승 자리 아무 날 | 아무 날 | 중앙 사건 | 상승 자리 | 아무 날 | p(상승 자리) | p(아무 날) | −10% 사건 | 상승 자리 | 아무 날 | p(상승 자리, −10%) | 앞뒤 | 판정 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    detail = []
    for name, key in (("C Baa 60일 +0.35%p 이상", "기간_C"), ("H 하이일드 대리 60일 아래 10%", "기간_H")):
        live = conds[key]
        sig = conds[name] & live
        for h in HS:
            r, dd = fw[h]
            ok = ~np.isnan(r)
            valid_all = np.where(live & ok)[0]
            valid_up = np.where(live & ok & up)[0]
            ev = episodes(sig & ok)
            k = len(ev)
            if k == 0:
                lines.append(f"| {name} | {h} | | 0 |" + " |" * 14)
                continue
            med = np.median(r[ev])
            crash = (dd[ev] < -0.10).mean()
            p_up = boot_p(med, k, valid_up, lambda s: np.median(r[s]))
            p_all = boot_p(med, k, valid_all, lambda s: np.median(r[s]))
            p_cr = boot_p(crash, k, valid_up, lambda s: (dd[s] < -0.10).mean())
            half = valid_all[len(valid_all) // 2]
            sides = []
            for e_part, v_part in ((ev[ev < half], valid_up[valid_up < half]), (ev[ev >= half], valid_up[valid_up >= half])):
                sides.append(np.sign((dd[e_part] < -0.10).mean() - (dd[v_part] < -0.10).mean()) if len(e_part) else 0)
            same = sides[0] == sides[1] and sides[0] != 0
            verdict = ("다름" if p_cr < .05 and same else "차이 없음") if k >= 30 else "n번 중 m번"
            per = f"{spx.index[valid_all[0]].year} ~ {spx.index[valid_all[-1]].year}"
            lines.append(f"| {name} | {h} | {per} | {k} | {int((r[ev] > 0).sum())}/{k} | {(r[valid_up] > 0).mean() * 100:.0f}% | {(r[valid_all] > 0).mean() * 100:.0f}% | "
                         f"{med * 100:+.1f}% | {np.median(r[valid_up]) * 100:+.1f}% | {np.median(r[valid_all]) * 100:+.1f}% | {p_up:.3f} | {p_all:.3f} | "
                         f"{int((dd[ev] < -0.10).sum())}/{k} | {(dd[valid_up] < -0.10).mean() * 100:.0f}% | {(dd[valid_all] < -0.10).mean() * 100:.0f}% | {p_cr:.3f} | "
                         f"{'같음' if same else '갈림'} | {verdict} |")
            if h == 126:
                for i in ev:
                    detail.append(f"| {name[:1]} | {spx.index[i].date()} | {baa_chg.iloc[i]:+.2f} | {hy_chg.iloc[i] * 100 if not np.isnan(hy_chg.iloc[i]) else float('nan'):+.1f}% | "
                                  f"{spx.iloc[i] / spx.cummax().iloc[i] * 100 - 100:.1f}% | {fw[63][0][i] * 100:+.1f}% | {r[i] * 100:+.1f}% | {dd[i] * 100:.1f}% |")
    lines += ["", "## 사건마다 (126일 창)", "", "| 조건 | 날 | Baa 60일 | 하이일드 대리 60일 | 최고점 대비 | 63일 뒤 | 126일 뒤 | 126일 안 최대 낙폭 |", "|---|---|---|---|---|---|---|---|"] + detail
    i = n - 1
    lines += ["", "## 지금", "",
              f"- {spx.index[i].date()} 자리 **{pos.iloc[i]}** · Baa 60일 {baa_chg.iloc[i]:+.2f}%p (선 +0.35) · 하이일드 대리 60일 {hy_chg.iloc[i] * 100:+.2f}% (선 {hy_cut * 100:.2f}%) · "
              f"C {'켜짐' if conds['C Baa 60일 +0.35%p 이상'][i] else '꺼짐'} · H {'켜짐' if conds['H 하이일드 대리 60일 아래 10%'][i] else '꺼짐'}"]
    recent = pd.DataFrame({"자리": pos, "Baa60": baa_chg, "HY60%": hy_chg * 100})["2026-09-01":].iloc[::5]
    lines += ["", "```", recent.round(2).to_string(), "```"]
    with open(os.path.join(OUT, "uptrend_credit.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
