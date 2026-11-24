"""뉴팩트 개성 있는 아이 찾기 게임 (5단계 "왜"의 가설) — 신상표 + 민감 상태 첫 눈길 (2026-11-24 사용자 "그렇게 해").

길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md 7-11 · 7-12.
가설 1 (사용자): 개성 있는 아이 = 돈 · 관심이 몰린 아이(실적이 아니라 기대로 돈을 받은 아이), 평범한 아이 = 실적 · 현금흐름으로 값이 매겨진 아이.
가설 2 (사용자): 실적보다 돈이 많이 들어오면 거품 → 차익 실현으로 갑자기 폭락. 전고점 근처에 오래 머문 "민감 상태"에서는 작은 자극에도 쉽게 폭락.

    python experiments/stock-character/look_money.py

부유함 = ② 받은 돈이 실적보다 큼(매출 대비 주가 · 이익 대비 주가 · 적자 여부 · 영업현금흐름)을 가운데, ① 돈이 들어오는 중(거래대금 변화 · 주가 상승)을 곁에. ③ 관심(뉴스 수)은 아직 안 잼.
명단 = 7-8 · 7-10 에서 뽑은 이름(아래 GROUPS) + 배경으로 명단 밖 40명. 재무 = 야후(지금 값 — 과거 시점 값이 아님에 주의).
민감 상태 = 종가가 최근 250일 고점의 10% 안에 20거래일 넘게 이어 머문 날. 같은 아이의 민감한 날 / 아닌 날에 예고 없는 내림 돌(−5% 이하, 실적 · 파도 날 뺌)이 100일에 몇 번 떨어졌나.
"""

import json
import os
import sys
import time

import numpy as np
import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
STORE = os.path.join(ROOT, "data", "store", "character")
sys.path.insert(0, HERE)
import look_stones as LS  # noqa: E402

GROUPS = {
    "늘 켜짐": "BE SMCI COIN LITE COHR MRNA HOOD CVNA APP MRVL VRT INTC CIEN ALB AMD ECHO PLTR VST ON FSLR ANET NCLH XYZ CRWD ILMN".split(),
    "최근 1년에 켜짐": "MU WDC TER LRCX STX AMAT GLW FLEX KLAC DDOG HPE ORCL AXON FICO OKTA".split(),
    "켜졌다 꺼졌다": "FIX DELL TSLA P MPWR SKYD CEG UAL TPL CCL AVGO SW FCX TWLO".split(),
    "잔잔 + 돌": "CTSH IBM PTC FISV VRSK SCHW FDX TEL BSX PCG GOOG C GL AJG EIX".split(),
    "늘 잔잔": "BRK-B KO RSG PG L LIN WM JNJ".split(),
}
NEAR, STAY = 0.10, 20
CACHE = os.path.join(STORE, "info_us.json")


def infos(syms):
    c = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    keep = ("marketCap", "priceToSalesTrailing12Months", "trailingPE", "forwardPE", "profitMargins", "operatingCashflow",
            "freeCashflow", "totalRevenue", "revenueGrowth", "netIncomeToCommon", "sector", "industry", "shortName")
    for s in syms:
        if s in c:
            continue
        try:
            i = yf.Ticker(s).info
            c[s] = {k: i.get(k) for k in keep}
        except Exception as e:  # noqa: BLE001
            c[s] = {"err": str(e)[:60]}
        time.sleep(0.4)
    json.dump(c, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return c


def main():
    bars = pd.read_pickle(os.path.join(STORE, "bars_us.pkl"))
    earn = pd.read_csv(os.path.join(STORE, "earn_days_us.csv"), parse_dates=["day"])
    eg = {s: g for s, g in earn.groupby("sym")}
    C = pd.DataFrame({s: d["close"] for s, d in bars.items() if not s.startswith("^")})
    hit = C.pct_change().abs() * 100 >= LS.STONE
    share = (hit.sum(axis=1) / C.notna().sum(axis=1)).iloc[-LS.DAYS:]
    waves = set(share[share >= LS.WAVE_SHARE].index)
    named = [s for g in GROUPS.values() for s in g]
    rest = [s for s in C.columns if s not in named and s in eg]
    rng = np.random.default_rng(7)
    GROUPS["명단 밖 40명(배경)"] = sorted(rng.choice(rest, 40, replace=False))
    allsyms = [s for g in GROUPS.values() for s in g]
    info = infos(allsyms)

    rows = []
    for g, syms in GROUPS.items():
        for s in syms:
            if s not in bars or s not in eg:
                continue
            d = bars[s]
            d = d[(d["open"] > 0) & (d["volume"] > 0)]
            c = d["close"]
            dv = c * d["volume"]
            i = info.get(s, {})
            rev, ni, ocf = i.get("totalRevenue"), i.get("netIncomeToCommon"), i.get("operatingCashflow")
            # 민감 상태
            near = c >= c.rolling(250, min_periods=120).max() * (1 - NEAR)
            run = near.groupby((~near).cumsum()).cumsum()
            sens = (run >= STAY).shift(1, fill_value=False)        # 전날까지 20일 넘게 머묾 → 오늘이 민감한 날
            pr = LS.profile(s, d, eg[s], waves)
            if pr is None:
                continue
            ret = c.pct_change() * 100
            un_down = [t for t in pr["_un"] if ret[t] <= -LS.STONE]
            win = sens.iloc[-LS.DAYS:]
            ns, nn = int(win.sum()), int((~win).sum())
            ds = sum(bool(sens[t]) for t in un_down)
            dn = len(un_down) - ds
            rows.append({"group": g, "sym": s, "ret3y": (c.iloc[-1] / c.iloc[-LS.DAYS] - 1) * 100, "ret1y": (c.iloc[-1] / c.iloc[-252] - 1) * 100,
                         "dv_x": dv.iloc[-252:].mean() / dv.iloc[-LS.DAYS:-252].mean(),
                         "ps": i.get("priceToSalesTrailing12Months"), "pe": i.get("trailingPE"), "fpe": i.get("forwardPE"),
                         "loss": (ni is not None and ni < 0), "margin": (i.get("profitMargins") or np.nan) * 100,
                         "ocf_rev": (ocf / rev * 100) if ocf and rev else np.nan, "un": pr["un"], "lake": pr["lake"],
                         "sens_days": ns, "down_sens": ds, "down_not": dn,
                         "rate_sens": ds / ns * 100 if ns >= 40 else np.nan, "rate_not": dn / nn * 100 if nn >= 40 else np.nan})
    R = pd.DataFrame(rows)
    R.round(2).to_csv(os.path.join(STORE, "money_us.csv"), index=False)
    f = lambda x, d=0, u="": "  —" if pd.isna(x) else f"{x:,.{d}f}{u}"   # noqa: E731

    print("=== 가설 1 신상표 — 이름별 (재무 = 야후 지금 값)")
    print("칸: 3년 등락 · 최근 1년 거래대금이 그 앞 2년의 몇 배 | 매출 대비 주가(배) · 이익 대비 주가(배) · 순이익률 · 영업현금흐름 ÷ 매출 | 예고 없는 돌")
    for g in GROUPS:
        x = R[R.group == g]
        print(f"\n[{g}] {len(x)}명 — 가운데 값: 매출 대비 주가 {f(x.ps.median(), 1)}배 · 이익 대비 주가 {f(x.pe.median(), 0)}배 · 순이익률 {f(x.margin.median(), 0)}% · "
              f"적자 {int(x.loss.sum())}명 · 이익 대비 주가 없음(적자 등) {int(x.pe.isna().sum())}명 · 3년 등락 {f(x.ret3y.median(), 0)}% · 거래대금 {f(x.dv_x.median(), 1)}배")
        if g.startswith("명단 밖"):
            continue
        for _, r in x.iterrows():
            print(f"   {r.sym:6} {f(r.ret3y, 0):>6}% · 거래대금 {f(r.dv_x, 1):>4}배 | 매출 대비 {f(r.ps, 1):>5} · 이익 대비 {f(r.pe, 0):>4} · 순이익률 {f(r.margin, 0):>4}% · 현금흐름 {f(r.ocf_rev, 0):>4}%"
                  f"{' · 적자' if r.loss else ''} | 돌 {r.un}")

    print("\n=== 반례를 이름으로 (부유 = 매출 대비 주가 8배 넘음 또는 적자 · 개성 = 명단 ① 세 묶음)")
    rich = (R.ps >= 8) | R.loss
    pers = R.group.isin(["늘 켜짐", "최근 1년에 켜짐", "켜졌다 꺼졌다"])
    back = R.group.isin(["늘 잔잔", "명단 밖 40명(배경)", "잔잔 + 돌"])
    print(f"  개성 있는데 부유하지 않음({int((pers & ~rich).sum())}/{int(pers.sum())}명): " + ", ".join(f"{r.sym}({f(r.ps, 1)}배)" for _, r in R[pers & ~rich].iterrows()))
    print(f"  부유한데 명단 ① 에 없음({int((back & rich).sum())}/{int(back.sum())}명): " + ", ".join(f"{r.sym}({f(r.ps, 1)}배{' 적자' if r.loss else ''} · 돌 {r.un})" for _, r in R[back & rich].iterrows()))

    print(f"\n=== 가설 2 민감 상태 첫 눈길 — 1년 고점의 {int(NEAR * 100)}% 안에 {STAY}거래일 넘게 머문 날 vs 아닌 날, 예고 없는 내림 돌(−5% 이하)이 100일에 몇 번")
    for g in GROUPS:
        x = R[(R.group == g) & R.rate_sens.notna() & R.rate_not.notna()]
        if not len(x):
            print(f"[{g}] 견줄 아이 없음"); continue
        more = int((x.rate_sens > x.rate_not).sum()); less = int((x.rate_sens < x.rate_not).sum())
        print(f"[{g}] 견줄 수 있는 {len(x)}명 중 민감한 날에 더 잦음 {more}명 · 덜 잦음 {less}명 · 같음 {len(x) - more - less}명 | "
              f"합쳐서 민감한 날 100일에 {x.down_sens.sum() / x.sens_days.sum() * 100:.1f}번 · 아닌 날 {x.down_not.sum() / (LS.DAYS * len(x) - x.sens_days.sum()) * 100:.1f}번")
    x = R[R.group.isin(["늘 켜짐", "최근 1년에 켜짐", "켜졌다 꺼졌다"]) & R.rate_sens.notna()].sort_values("rate_sens", ascending=False)
    print("  개성 있는 아이 이름별(민감한 날 수 · 민감한 날 100일당 / 아닌 날 100일당): " + ", ".join(f"{r.sym} {r.sens_days}일 {r.rate_sens:.1f}/{r.rate_not:.1f}" for _, r in x.iterrows()))


if __name__ == "__main__":
    main()
