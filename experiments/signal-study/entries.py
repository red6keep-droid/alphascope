"""r02 — ③ 눌림 (P0~P4, 중심) · ② 상승 포착 (U1~U6, 대조군). output/r02_entries.md

규칙은 계획 3절에 2026-09-24 고정된 것 그대로. 결과를 보고 바꾸지 않는다.

② 상승 포착 (T일 마감)                        ③ 눌림 — 추세 = 종가 > 50일선 이고 20일선 > 50일선
  U1 당일 +3~6%                                 P1 추세 · 20일 고점 대비 −3~−8% · 당일 종가 > 전일 종가
  U2 당일 +6~12%                                P2 추세 · 5일선 아래 1~3일 마감 뒤 5일선 위로 복귀한 날
  U3 당일 +3%↑ 이고 RVOL ≥ 1.5                  P3 추세 · 3일 연속 하락 뒤 첫 상승일
  U4 2일 연속 상승, 누적 +4%↑                    P4 급등일(+5%↑ · RVOL ≥ 2) 뒤 2~5일 안에 급등일 종가 대비 −2~−6% 되돌림 후 상승 마감
  U5 20일 신고가 마감                            P0 대조: 추세 조건 없이 3일 연속 하락 뒤 첫 상승일
  U6 U5 이고 종가 > 50일선

청산: 고정 1 · 2 · 3 · 5 · 10 · 20일 + 규칙 청산
  U: 첫 하락 마감 다음 날 시가 매도 · 손절 −7% / 목표 +10% (최대 20일)
  P: 5일선 아래로 마감하면 다음 날 시가 매도 · 손절 −7% / 목표 +10%
"""

import os
import sys

import numpy as np
import pandas as pd

import common
import config


def signals(D):
    C, O, H, L, V = D.C, D.O, D.H, D.L, D.V
    ret1 = C / C.shift(1) - 1
    rvol = V / V.shift(1).rolling(20).mean()
    up = C > C.shift(1)
    ma5, ma20, ma50 = C.rolling(5).mean(), C.rolling(20).mean(), C.rolling(50).mean()
    # 연속 상승·하락 길이
    def streak(cond):
        v = cond.astype(int).values
        out = np.zeros_like(v)
        for i in range(1, len(v)):
            out[i] = np.where(v[i] == 1, out[i - 1] + 1, 0)
        return pd.DataFrame(out, index=cond.index, columns=cond.columns)
    Lup = streak(up)
    Ldn = streak(C < C.shift(1))
    Lbelow5 = streak(C < ma5)
    hi20 = C.rolling(20).max()
    trend = (C > ma50) & (ma20 > ma50)

    U = {
        "U1 당일 +3~6%": (ret1 >= 0.03) & (ret1 < 0.06),
        "U2 당일 +6~12%": (ret1 >= 0.06) & (ret1 <= 0.12),
        "U3 +3%↑ · RVOL≥1.5": (ret1 >= 0.03) & (rvol >= 1.5),
        "U4 2일 연속 · 누적 +4%↑": (Lup == 2) & (C / C.shift(2) - 1 >= 0.04),
        "U5 20일 신고가 마감": C >= hi20,
        "U6 20일 신고가 · 종가>50일선": (C >= hi20) & (C > ma50),
    }
    dd20 = C / hi20.shift(1) - 1          # 어제까지의 20일 고점 대비
    spike = (ret1 >= 0.05) & (rvol >= 2)
    p4 = pd.DataFrame(False, index=C.index, columns=C.columns)
    for d in range(2, 6):
        pull = C / C.shift(d) - 1
        p4 |= spike.shift(d).fillna(False).astype(bool) & (pull <= -0.02) & (pull >= -0.06) & up
    P = {
        "P1 추세 · 고점 −3~−8% · 양전환": trend & (dd20 <= -0.03) & (dd20 >= -0.08) & up,
        "P2 추세 · 5일선 1~3일 이탈 후 복귀": trend & (C > ma5) & (Lbelow5.shift(1) >= 1) & (Lbelow5.shift(1) <= 3),
        "P3 추세 · 3일 연속 하락 뒤 첫 상승": trend & (Ldn.shift(1) == 3) & up,
        "P4 급등 후 2~5일 −2~−6% 되돌림 · 상승 마감": p4,
        "P0 대조 · 추세 없이 3일 하락 뒤 첫 상승": (Ldn.shift(1) == 3) & up,
    }
    exits = {"U": (C < C.shift(1)), "P": (C < ma5)}    # 규칙 청산 조건 (그 날 마감 → 다음 날 시가 매도)
    return U, P, exits


def block(D, name, mask, keys, seed):
    md = [f"**{name}**", "", common.HEADER]
    for k in keys:
        h = k if isinstance(k, int) else 20
        m = common.cluster(mask, h)
        s = common.evaluate(D, m, k, placebo=True, seed=seed + (k if isinstance(k, int) else 50))
        lab = f"{k}일" if isinstance(k, int) else {"rule_U": "첫 하락 마감 매도", "rule_P": "5일선 이탈 매도", "br": "손절 −7 / 목표 +10"}[k]
        if s is not None and not isinstance(k, int):
            ed = D.exit_days[k].values[m.values & D.fwd[k].notna().values]
            lab += f" (평균 {np.nanmean(ed):.1f}일)"
        md.append(common.fmt_row(lab, s))
    md.append("")
    return md


def splits(D, name, mask, h, sec_axis):
    md = [f"### {name} · {h}일 보유 — 분할", ""]
    m = common.cluster(mask, h)
    md.append(common.split_table(D, m, h, D.period, "구간"))
    md.append(common.year_table(D, m, h) + "\n")
    md.append(common.split_table(D, m, h, common.bool_axis(D.earn_adj, "실적 ±1일", "실적 아님"), "실적 인접"))
    md.append(common.split_table(D, m, h, D.vix_bucket, "공포 (VIX)"))
    md.append(common.split_table(D, m, h, D.rate_dir, "금리 방향"))
    if D.regime is not None:
        md.append(common.split_table(D, m, h, D.regime, "섹터 국면"))
    md.append(common.split_table(D, m, h, sec_axis, "섹터"))
    return md


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    D = common.load()
    reg_path = os.path.join(common.OUT, "r01_regime.pkl")
    D.regime = pd.read_pickle(reg_path) if os.path.exists(reg_path) else None
    U, P, exits = signals(D)
    common.register_rule_exit(D, "rule_U", exits["U"])
    common.register_rule_exit(D, "rule_P", exits["P"])
    common.register_stop_target(D, "br", config.STOP, config.TARGET)
    ok = D.signal_ok
    sec_axis = pd.DataFrame(np.tile(np.array([D.sector[s] for s in D.syms]), (len(D.days), 1)), index=D.days, columns=D.syms)

    md = ["# r02 — ③ 눌림 · ② 상승 포착", "",
          f"S&P 500 {len(D.syms)}종목 · {config.STUDY_START} ~ {D.days.max().date()} · 전제 조건 1~7 (계획 2절). 규칙 정의는 `entries.py` 머리말.",
          "r01 결론(연속 상승 뒤 약한 반전)에 따라 ③ 눌림이 중심, ② 는 대조군. 규칙 청산의 괄호는 평균 보유일.", "", common.LEGEND, ""]

    md += ["## 신호 빈도", "", "| 규칙 | 신호 (종목·날) | 하루 평균 | 신호 없는 날 | 실적 ±1일 비율 |", "| --- | ---: | ---: | ---: | ---: |"]
    for name, m in {**P, **U}.items():
        mm = m & ok
        n = int(mm.values.sum()); per_day = mm.sum(axis=1); days_ok = (D.spy_ok & D.study)
        md.append(f"| {name} | {n:,} | {per_day[days_ok].mean():.1f} | {(per_day[days_ok] == 0).mean():.0%} | {(mm & D.earn_adj).values.sum() / max(n, 1):.0%} |")
    md.append("")

    md += ["## ③ 눌림 — 규칙별 · 청산별", ""]
    for i, (name, m) in enumerate(P.items()):
        md += block(D, name, m & ok, common.HORIZONS + ["rule_P", "br"], seed=1000 + i * 100)
    md += ["## ② 상승 포착 (대조군) — 규칙별 · 청산별", ""]
    for i, (name, m) in enumerate(U.items()):
        md += block(D, name, m & ok, common.HORIZONS + ["rule_U", "br"], seed=2000 + i * 100)

    md += ["## 분할 — ③ 눌림 P1~P4, 5일 · 20일 보유", ""]
    for name, m in P.items():
        if name.startswith("P0"):
            continue
        for h in (5, 20):
            md += splits(D, name, m & ok, h, sec_axis)
    md += ["## 분할 — ② 상승 포착 U3 · U6, 5일 보유 (실적 인접만)", ""]
    for name in ["U3 +3%↑ · RVOL≥1.5", "U6 20일 신고가 · 종가>50일선"]:
        m = common.cluster(U[name] & ok, 5)
        md.append(f"**{name}**\n")
        md.append(common.split_table(D, m, 5, common.bool_axis(D.earn_adj, "실적 ±1일", "실적 아님"), "실적 인접"))
        md.append(common.split_table(D, m, 5, D.period, "구간"))

    # 생존 편향 — P1~P4 · U3 5일
    md += ["## 생존 편향 — 제외 종목 95개 포함 (5일 보유)", "", "| 규칙 | 현재 500 승률 | 차이 %p | 포함 승률 | 차이 %p | 승률 변화 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    D2 = common.load(include_removed=True)
    U2, P2, _ = signals(D2)
    for name in [k for k in P if not k.startswith("P0")] + ["U3 +3%↑ · RVOL≥1.5"]:
        src1 = P.get(name, U.get(name)); src2 = P2.get(name, U2.get(name))
        s1 = common.evaluate(D, common.cluster(src1 & ok, 5), 5)
        s2 = common.evaluate(D2, common.cluster(src2 & D2.signal_ok, 5), 5)
        md.append(f"| {name} | {s1['win']:.1%} | {s1['diff'] * 100:+.1f} | {s2['win']:.1%} | {s2['diff'] * 100:+.1f} | {(s2['win'] - s1['win']) * 100:+.2f} |")
    md.append("")

    path = os.path.join(common.OUT, "r02_entries.md")
    open(path, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(f"→ {path}")


if __name__ == "__main__":
    main()
