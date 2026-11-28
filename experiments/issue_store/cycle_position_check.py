"""순환 자리 검증 V8 — 날마다 시장이 상승 · 하락 · 안정 · 회복 중 어느 자리인지(그날 알 수 있던 값만) 정하고,
자리마다 뒤 석 달 · 여섯 달이 아무 날과 달랐나를 본다. 기준은 비공개 doc/기획/거시-흐름-지도.md 5-2 절에 결과 보기 전 고정.

    .venv/bin/python experiments/issue_store/cycle_position_check.py

자리 (그날까지의 값만):
- 상승 = 지금까지의 최고 종가 대비 −10% 안.
- 하락 자리(최고점 대비 −10% 넘게 아래) 안에서 — 회복 > 안정 > 하락 순으로 먼저 맞는 것:
  회복 = 하락 자리에 들어간 뒤의 최저 종가(그날까지) 대비 +10% 넘게 위.
  안정 = 그 최저 종가가 20거래일 넘게 새로 나오지 않았고 VIX < 25.
  하락 = 나머지.
VIX 가 1990 ~ 이라 S&P 500 은 1990 ~ 날을 센다(최고점은 1927 ~ 전체로). 코스피(1997 ~)도 VIX 를 쓴다(한국 변동성 지수 대리, 11-06 과 같음).

결과 = 뒤 63 · 126거래일 수익률 · 창 안 최대 낙폭 · −10% 넘게 빠짐. 비교 대상 = 같은 기간 아무 날.
사건 = 그 자리에 63거래일 넘게 없다가 다시 들어간 첫날. 플라시보 = 서로 63거래일 넘게 떨어진 아무 날을 사건 수만큼 2,000번.
판정 = p < .05 · 앞뒤 절반 같은 쪽 · 사건 30 이상. 30 미만은 "n번 중 m번".
결과: experiments/issue_store/results/cycle_position.md · cycle_position_days.csv (깃 밖).
"""
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from normal_range import load_close  # noqa: E402

OUT = os.path.join(_HERE, "results")
GAP = 63
HS = (63, 126)
NBOOT = 2000
POS = ["상승", "하락", "안정", "회복"]
rng = np.random.default_rng(20261128)


def positions(c, vix, confirm=1):
    """confirm = 10% 선을 며칠 이어서 넘어야 자리를 바꾸나(들어갈 때 · 나올 때 같게). 1 = 검증 V8 그대로(하루),
    3 = 상태판 규칙(11-28 사용자 A안 — 하루짜리 출렁임에 자리가 바뀌지 않게)."""
    v = c.values
    vx = vix.reindex(c.index).ffill(limit=5).values
    out = np.empty(len(v), dtype=object)
    peak = v[0]
    below, cnt = False, 0
    low = low_i = None
    for i, x in enumerate(v):
        peak = max(peak, x)
        under = x < peak * 0.9
        if under != below:
            cnt += 1
            if cnt >= confirm:
                below, cnt = under, 0
                if below:   # 들어간 날까지 이어진 날들 중 최저가
                    j = i - confirm + 1
                    k = j + int(np.argmin(v[j:i + 1]))
                    low, low_i = v[k], k
                else:
                    low = low_i = None
        else:
            cnt = 0
        if not below:
            out[i] = "상승"
            continue
        if x < low:
            low, low_i = x, i
        if x > low * 1.10:
            out[i] = "회복"
        elif i - low_i > 20 and not np.isnan(vx[i]) and vx[i] < 25:
            out[i] = "안정"
        else:
            out[i] = "하락"
    return pd.Series(out, c.index)


def forward(c):
    v = c.values
    n = len(v)
    res = {}
    for h in HS:
        r = np.full(n, np.nan)
        dd = np.full(n, np.nan)
        for i in range(n - h):
            w = v[i + 1:i + h + 1]
            r[i] = w[-1] / v[i] - 1
            dd[i] = w.min() / v[i] - 1
        res[h] = (r, dd)
    return res


def episodes(mask):
    idx = np.where(mask)[0]
    out, last = [], -10 ** 9
    for i in idx:
        if i - last > GAP:
            out.append(i)
        last = i
    return np.array(out, dtype=int)


def spaced_random(k, valid):
    picks = []
    for i in rng.permutation(valid):
        if all(abs(i - j) > GAP for j in picks):
            picks.append(i)
            if len(picks) >= k:
                break
    return np.array(picks)


def study(label, c, pos, start):
    fw = forward(c)
    idx = np.arange(len(c))
    live = idx[(c.index >= pd.Timestamp(start))]
    rows = []
    for h in HS:
        r, dd = fw[h]
        valid = live[~np.isnan(r[live])]
        base_up = (r[valid] > 0).mean()
        base_med = np.median(r[valid])
        base_crash = (dd[valid] < -0.10).mean()
        for p in POS:
            m = np.zeros(len(c), bool)
            m[valid] = (pos.values[valid] == p)
            ev = episodes(m)
            ev = ev[~np.isnan(r[ev])]
            dayshare = m[valid].mean()
            k = len(ev)
            row = {"자": label, "창": h, "자리": p, "날 비율": dayshare, "사건": k}
            if k == 0:
                rows.append(row)
                continue
            med = np.median(r[ev])
            boots = np.array([np.median(r[spaced_random(k, valid)]) for _ in range(NBOOT)])
            pval = min(1.0, 2 * min((boots >= med).mean(), (boots <= med).mean()))
            half = valid[len(valid) // 2]
            sides = []
            for part, part_valid in ((ev[ev < half], valid[valid < half]), (ev[ev >= half], valid[valid >= half])):
                sides.append(np.sign(np.median(r[part]) - np.median(r[part_valid])) if len(part) else 0)
            # 날 단위(겹침 있음, 참고)
            dsel = valid[pos.values[valid] == p]
            row.update({
                "상승 사건": f"{int((r[ev] > 0).sum())}/{k}", "상승 아무 날": base_up,
                "중앙 사건": med, "중앙 아무 날": base_med, "p": pval,
                "앞뒤": "같음" if sides[0] == sides[1] and sides[0] != 0 else "갈림",
                "−10% 사건": f"{int((dd[ev] < -0.10).sum())}/{k}", "−10% 아무 날": base_crash,
                "날 단위 중앙": np.median(r[dsel]) if len(dsel) else np.nan,
                "날 단위 −10%": (dd[dsel] < -0.10).mean() if len(dsel) else np.nan,
                "판정": ("다름" if pval < .05 and sides[0] == sides[1] and sides[0] != 0 else "차이 없음") if k >= 30 else "n번 중 m번",
                "사건 날짜": " · ".join(str(c.index[i].date()) for i in ev),
            })
            rows.append(row)
    return pd.DataFrame(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    vix = load_close("^VIX")
    spx = load_close("^GSPC")
    ks = load_close("^KS11")
    conf = int(sys.argv[sys.argv.index("--confirm") + 1]) if "--confirm" in sys.argv else 1
    tag = "" if conf == 1 else f"_c{conf}"
    ps, pk = positions(spx, vix, conf), positions(ks, vix, conf)
    res = pd.concat([study("S&P 500", spx, ps, "1990-01-02"), study("코스피", ks, pk, "1997-01-01")])

    pct = lambda v: "" if pd.isna(v) else f"{v * 100:+.1f}%"
    pp = lambda v: "" if pd.isna(v) else f"{v * 100:.0f}%"
    lines = ["# 순환 자리 V8", "", f"자료 끝: {spx.index[-1].date()}", "",
             "| 자 | 창 | 자리 | 날 비율 | 사건 | 오른 사건 | 아무 날 | 중앙 사건 | 아무 날 | p | 앞뒤 | −10% 사건 | 아무 날 | 날 단위 중앙 | 날 단위 −10% | 판정 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in res.iterrows():
        if r["사건"] == 0:
            lines.append(f"| {r['자']} | {r['창']} | {r['자리']} | {pp(r['날 비율'])} | 0 |||||||||||")
            continue
        lines.append(f"| {r['자']} | {r['창']} | {r['자리']} | {pp(r['날 비율'])} | {r['사건']} | {r['상승 사건']} | {pp(r['상승 아무 날'])} | "
                     f"{pct(r['중앙 사건'])} | {pct(r['중앙 아무 날'])} | {r['p']:.3f} | {r['앞뒤']} | {r['−10% 사건']} | {pp(r['−10% 아무 날'])} | "
                     f"{pct(r['날 단위 중앙'])} | {pp(r['날 단위 −10%'])} | {r['판정']} |")
    lines += ["", "## 사건 날짜 (126일 창)", ""]
    for _, r in res[res["창"] == 126].iterrows():
        if r["사건"]:
            lines.append(f"- {r['자']} {r['자리']}: {r['사건 날짜']}")
    lines += ["", "## 지금 자리", ""]
    for lab, c, p in (("S&P 500", spx, ps), ("코스피", ks, pk)):
        last = p.iloc[-1]
        run = (p[::-1] != last).idxmax() if (p != last).any() else p.index[0]
        lines.append(f"- {lab} {c.index[-1].date()}: **{last}** (이 자리 들어온 날 = {run.date()} 다음 거래일) · 최고점 대비 {c.iloc[-1] / c.cummax().iloc[-1] * 100 - 100:.1f}%")
    lines += ["", "## 해마다 자리 비율 (S&P 500)", ""]
    yr = ps[ps.index >= "1990"].groupby(ps[ps.index >= "1990"].index.year).value_counts(normalize=True).unstack().fillna(0)
    lines.append("| 해 | " + " | ".join(POS) + " |")
    lines.append("|---|" + "---|" * len(POS))
    for y, r in yr.iterrows():
        lines.append(f"| {y} | " + " | ".join(f"{r.get(p, 0) * 100:.0f}%" for p in POS) + " |")
    with open(os.path.join(OUT, f"cycle_position{tag}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    pd.DataFrame({"S&P 500": ps, "코스피": pk}).to_csv(os.path.join(OUT, f"cycle_position_days{tag}.csv"))
    print("\n".join(lines[:4 + 2 + len(res)]))
    print("\n".join(l for l in lines if l.startswith("- ") and "**" in l))


if __name__ == "__main__":
    main()
