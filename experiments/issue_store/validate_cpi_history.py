"""증시 전망 거시 기본 사례 = 물가 발표(CPI) — 기록상 비슷한 때 실측 (2026-11-08 사용자 "적용하고 검증해").

    python experiments/issue_store/validate_cpi_history.py      # 표 출력 + output/cpi_history.json

왜 CPI: FOMC 는 시장이 결과를 거의 알고 있어 선반영 사례(상황 13)에 맞고, 기본 화면(상황 1)은 결과를 미리 모르는 사건이어야 한다.
놀람 대리: 과거 예상치(컨센서스) 기록이 없어 발표 날 2년 금리 변화(DGS2, 전날 대비)로 가른다 — Kuttner(2001) 식.
  ≥ +5bp = 예상보다 높게 나온 날(뜨거움), ≤ −5bp = 예상보다 낮게 나온 날(식음), 그 사이 = 예상 근처.
기준점 = 발표 날 종가(08:30 발표라 그날 장이 반응을 담는다 — 틀 S 의 '결과 날 종가부터'). 발표 날 하루 반응도 따로.
평소 = 같은 기간 모든 거래일. 정확 이항 검정(validate_fomc_history.binom_p). 로컬 자료만, AI 0.
"""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_fomc_history import HZ, L, binom_p, fwd, stats  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BP = 0.05


def main():
    close = pd.read_parquet(os.path.join(ROOT, "data", "store", "bars", "_GSPC.parquet"))["close"].dropna()
    close.index = pd.to_datetime(close.index)
    y2 = pd.read_csv(os.path.join(ROOT, "data", "store", "fred", "DGS2.csv"), parse_dates=["day"]).set_index("day")["value"]
    rel = pd.read_csv(os.path.join(ROOT, "data", "store", "calendar", "econ_releases.csv"), parse_dates=["day"])
    cpi = sorted(set(rel[rel.subkind == "CPI"]["day"]))
    cpi = [d for d in cpi if d >= y2.index.min() + pd.Timedelta(days=5) and d in close.index]
    groups = {"뜨거움": [], "식음": [], "예상 근처": []}
    react = {k: [] for k in groups}
    for d in cpi:
        if d not in y2.index:
            continue
        prev = y2[y2.index < d]
        if prev.empty:
            continue
        dy = y2[d] - prev.iloc[-1]
        k = "뜨거움" if dy >= BP else "식음" if dy <= -BP else "예상 근처"
        i = close.index.get_loc(d)
        groups[k].append(i)
        react[k].append((close.iloc[i] / close.iloc[i - 1] - 1) * 100)
    i0, i1 = groups["예상 근처"][0] if groups["예상 근처"] else 0, len(close) - 1
    i0 = min(min(v) for v in groups.values() if v)
    base = {h: stats([fwd(close, i, h) for i in range(i0, i1)]) for h in HZ}
    base_day = [(close.iloc[i] / close.iloc[i - 1] - 1) * 100 for i in range(i0, i1)]
    res = {"line": L, "bp": BP, "period": [str(close.index[i0].date()), str(close.index[i1].date())], "base": base, "groups": {}}
    n_all = sum(len(v) for v in groups.values())
    print(f"CPI 발표 {n_all}번 ({res['period'][0]} ~) · 2년 금리 ±{BP * 100:.0f}bp 로 가름 · 기준 ±{L}%\n")
    bd = sorted(abs(x) for x in base_day)
    print(f"평소 하루 움직임 중앙값 {bd[len(bd) // 2]:.2f}%")
    for k, idx in groups.items():
        r = react[k]
        print(f"\n[{k}] {len(idx)}번 ({len(idx) / n_all * 100:.0f}%) · 발표 날 하루 오름 {sum(x > 0 for x in r)}/{len(r)} · 하루 움직임 중앙값 {sorted(abs(x) for x in r)[len(r) // 2]:.2f}% · 평균 {sum(r) / len(r):+.2f}%")
        res["groups"][k] = {"n": len(idx), "day_up": sum(x > 0 for x in r), "day_mean": round(sum(r) / len(r), 2)}
        for h in HZ:
            st = stats([fwd(close, i, h) for i in idx])
            b = base[h]
            st.update({"p_up": round(binom_p(st["up"], st["n"], b["up"] / b["n"]), 3), "p_over": round(binom_p(st["over"], st["n"], b["over"] / b["n"]), 3),
                       "p_under": round(binom_p(st["under"], st["n"], b["under"] / b["n"]), 3)})
            res["groups"][k][h] = st
            print(f"  {h:>2}일 n{st['n']:>4}  오름 {st['up'] / st['n'] * 100:3.0f}% (평소 {b['up'] / b['n'] * 100:.0f}%, p{st['p_up']:.2f})"
                  f"  +기준 {st['over'] / st['n'] * 100:3.0f}% (평소 {b['over'] / b['n'] * 100:.0f}%, p{st['p_over']:.2f})"
                  f"  −기준 {st['under'] / st['n'] * 100:3.0f}% (평소 {b['under'] / b['n'] * 100:.0f}%, p{st['p_under']:.2f})  중앙값 {st['median']:+.2f}")
    # 최근 뜨거운 날 셋 · 식은 날 셋 (한 달 뒤)
    res["recent"] = {}
    for k in ("뜨거움", "식음"):
        last3 = [i for i in groups[k] if i + 20 < len(close)][-3:]
        res["recent"][k] = [(str(close.index[i].date()), round(fwd(close, i, 20), 2)) for i in last3]
        print(f"\n최근 {k} 셋 (한 달 뒤): {res['recent'][k]}")
    out = os.path.join(os.path.dirname(__file__), "output", "cpi_history.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n→ {out}")


if __name__ == "__main__":
    main()
