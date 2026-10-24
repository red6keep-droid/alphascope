"""밤사이 신호(미국 t 종가) → 한국 t+1 수익을 시가 갭 · 시가→종가 로 나눈다 — 2026-10-25 일별 검증 결과가 "다음날 시가에서 끝나는지" 확인용.
    python experiments/kr-stocks/validate_gap.py
결과(10-25): 종가→종가 차이의 전부가 시가 갭, 시가→종가는 0 또는 되돌림(−0.15~−0.36) — 한국-일별-사건-검증.md 결론 절.
"""
import numpy as np, pandas as pd, yfinance as yf
us = ["EWY","^SOX","^VIX","NVDA","MU","TSLA","JPM","PKX"]
kr = ["^KS11","005930.KS","000660.KS","373220.KS","055550.KS","005490.KS"]
raw = yf.download(us+kr, start="2000-01-01", auto_adjust=True, progress=False, threads=3)
O, C = raw["Open"], raw["Close"]
ksC = C["^KS11"]
def sig_of(syms, chg=False):
    s = (C[syms].diff().mean(axis=1) if chg else C[syms].pct_change(fill_method=None).mean(axis=1)*100).dropna()
    idx = ksC.dropna().index
    pos = np.clip(idx.searchsorted(s.index, side="right")-1, 0, len(idx)-1)
    s.index = idx[pos]; return s[~s.index.duplicated(keep="last")]
def spread(sig, y):
    j = pd.concat([sig, y], axis=1, join="inner").dropna(); j.columns=["s","y"]
    lo, hi = j.s.quantile(.25), j.s.quantile(.75)
    return j.y[j.s>=hi].mean()-j.y[j.s<=lo].mean(), len(j)
rows=[]
for name, syms, chg, tgt, rel in [("EWY→KOSPI",["EWY"],False,"^KS11",False),("SOX→KOSPI",["^SOX"],False,"^KS11",False),("VIX변화→KOSPI",["^VIX"],True,"^KS11",False),
                                  ("NVDA·MU→하이닉스",["NVDA","MU"],False,"000660.KS",True),("AAPL·MU·NVDA→삼성전자",["MU","NVDA"],False,"005930.KS",True),
                                  ("TSLA→LG엔솔",["TSLA"],False,"373220.KS",True),("JPM→신한",["JPM"],False,"055550.KS",True),("PKX→POSCO",["PKX"],False,"005490.KS",True)]:
    c, o = C[tgt], O[tgt]
    cc = (c.shift(-1)/c-1)*100          # t종가→t+1종가
    gap = (o.shift(-1)/c-1)*100          # t종가→t+1시가
    oc = (c.shift(-1)/o.shift(-1)-1)*100 # t+1시가→t+1종가
    if rel:
        kcc=(ksC.shift(-1)/ksC-1)*100; kgap=(O["^KS11"].shift(-1)/ksC-1)*100; koc=(ksC.shift(-1)/O["^KS11"].shift(-1)-1)*100
        cc, gap, oc = cc-kcc, gap-kgap, oc-koc
    s = sig_of(syms, chg)
    a,n = spread(s,cc); b,_=spread(s,gap); e,_=spread(s,oc)
    rows.append((name,n,a,b,e))
print(f"{'신호→대상':24s} {'n':>5s} {'종가→종가':>9s} {'시가갭':>8s} {'시가→종가':>9s}")
for r in rows: print(f"{r[0]:24s} {r[1]:5d} {r[2]:+9.2f} {r[3]:+8.2f} {r[4]:+9.2f}")
