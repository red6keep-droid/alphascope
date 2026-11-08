"""신호 서명 매일 스캔 — 그림자 모드 (기획 증시-전망-기획 8-19 3-b, 2026-11-08). 독자에게 아무것도 내보내지 않는다.

    python experiments/issue_store/signal_scan.py               # 미리보기: 오늘 결과를 화면에
    python experiments/issue_store/signal_scan.py --state DIR   # 기록: DIR/records/signals/scan.jsonl 에 하루 한 줄 덧붙임

하는 일 (AI 0 · 외부 쓰기 0):
1. 지표판(signal_signatures.BOARD, 29개) 최근 120거래일을 직접 받는다 — yfinance(일봉) · FRED 공개 CSV. 로컬 data/store 없이 CI 에서 돈다.
2. 지표마다 오늘 하루 z(직전 60거래일 σ 배수) · 10거래일 누적 z.
3. 경보 = 하루 3σ 지표 2개 이상(검증 D: 연 17번, 5일 안 사건 27% vs 평소 14%) · 느린 경보 = 10일 2σ 지표 2개 이상.
4. 서명 후보 = 오늘 + 어제 반응 벡터 ↔ results/signal_centroids.json(검증 3-a 의 묶음 평균) 코사인 상위 3. 사건 전 분류는 우연 수준이라 **경보 날만** 적는다.
기록 칸: day · alarm · slow · movers(지표 · 하루 z · 10일 z) · candidates(묶음 · 유사도) · n_board(받은 지표 수) · rules.
1~2달 쌓은 뒤 "경보 뒤 5일 안 실제 사건 · 서명 후보가 그날 뉴스 이슈 코드와 맞았나" 를 잰다(뉴스 대조는 그때 — 지금은 가격 쪽만).
"""
import argparse
import datetime as dt
import io
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import signal_signatures as SS  # noqa: E402  — 지표판 · 기준을 검증과 같은 것으로

RULES = "SIG-2026-11-08a"
CENT = os.path.join(HERE, "results", "signal_centroids.json")
Z_DAY, Z_SLOW, N_MIN, BASE = SS.Z_DAY, 2.0, SS.N_MIN, SS.BASE
YAHOO = {   # 지표판 파일 이름 → yfinance 심볼
    "CL_F": "CL=F", "GC_F": "GC=F", "DX-Y.NYB": "DX-Y.NYB", "JPY_X": "JPY=X", "KRW_X": "KRW=X", "_TNX": "^TNX", "_IRX": "^IRX",
    "_VIX": "^VIX", "_OVX": "^OVX", "_MOVE": "^MOVE", "HG_F": "HG=F", "NG_F": "NG=F", "ZW_F": "ZW=F", "TLT": "TLT", "HYG": "HYG",
    "LQD": "LQD", "ITA": "ITA", "JETS": "JETS", "XLE": "XLE", "XLF": "XLF", "XLK": "XLK", "XLU": "XLU", "EEM": "EEM", "FXI": "FXI",
    "EWY": "EWY", "BTC-USD": "BTC-USD",
}


def fetch(days=200):
    """{지표 이름: 종가 Series} — 실패한 지표는 빠진다(그날 n_board 로 남긴다)."""
    start = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    out = {}
    names = {SS.BOARD[n][0].split("/", 1)[1]: n for n in SS.BOARD}
    ysyms = {YAHOO[f]: names[f] for f in YAHOO if f in names}
    try:
        import yfinance as yf
        df = yf.download(list(ysyms), start=start, progress=False, auto_adjust=True, threads=False)["Close"]
        for sym, name in ysyms.items():
            if sym in df and df[sym].notna().sum() > BASE:
                s = df[sym].dropna()
                s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
                out[name] = s
    except Exception as e:  # noqa: BLE001
        print(f"[signal] yfinance 실패: {type(e).__name__}")
    import requests
    for f, name in names.items():
        if f in YAHOO:
            continue
        try:   # FRED 공개 CSV (fetch_fred_daily 와 같은 방식, 키 없음)
            r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={f}&cosd={start}", headers={"User-Agent": "alphascope-research/1.0"}, timeout=30)
            d = pd.read_csv(io.StringIO(r.text))
            s = pd.to_numeric(d.iloc[:, 1], errors="coerce")
            s.index = pd.to_datetime(d.iloc[:, 0])
            out[name] = s.dropna()
        except Exception as e:  # noqa: BLE001
            print(f"[signal] FRED {f} 실패: {type(e).__name__}")
    return out


def scan(px):
    spx_days = None
    for k in ("기술", "에너지", "금융", "유틸리티"):   # 미국 거래일 달력 = 섹터 ETF 날짜
        if k in px:
            spx_days = px[k].index
            break
    if spx_days is None:
        return None
    cal = spx_days.sort_values()
    ch = {}
    for name, s in px.items():
        how = SS.BOARD[name][1]
        s = s.reindex(cal)
        ch[name] = (np.log(s.where(s > 0)).diff() if how == "pct" else s.diff())
    ch = pd.DataFrame(ch)
    sd = ch.rolling(BASE, min_periods=int(BASE * 0.8)).std().shift(1)
    day = cal[-1]
    zd = (ch.iloc[-1] / sd.iloc[-1])
    z10 = ch.iloc[-10:].sum(min_count=8) / (sd.iloc[-11] * np.sqrt(10))
    zr = ch.iloc[-2:].sum(min_count=2) / (sd.iloc[-1] * np.sqrt(2))
    alarm = int((zd.abs() >= Z_DAY).sum()) >= N_MIN
    slow = int((z10.abs() >= Z_SLOW).sum()) >= N_MIN
    movers = sorted([(n, round(float(zd[n]), 1), round(float(z10[n]), 1)) for n in ch.columns
                     if pd.notna(zd[n]) and (abs(zd[n]) >= Z_DAY or (pd.notna(z10[n]) and abs(z10[n]) >= Z_SLOW))], key=lambda x: -abs(x[1]))
    cands = []
    if alarm or slow:
        cent = json.load(open(CENT, encoding="utf-8"))["families"]
        for fam, vec in cent.items():
            c = pd.Series({k: v[0] for k, v in vec.items()})
            sim = SS.cos(zr.reindex(c.index), c)
            if pd.notna(sim):
                cands.append((fam, round(sim, 2)))
        cands = sorted(cands, key=lambda x: -x[1])[:3]
    return {"day": day.strftime("%Y-%m-%d"), "alarm": alarm, "slow": slow, "movers": movers[:10], "candidates": cands,
            "n_board": int(ch.iloc[-1].notna().sum()), "rules": RULES}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=None)
    a = ap.parse_args()
    px = fetch()
    row = scan(px) if px else None
    if not row:
        print("[signal] 지표를 받지 못해 오늘 스캔 없음")
        return 0   # 그림자 모드 — 실패해도 다른 단계를 막지 않는다, 알림도 없음
    tag = "경보" if row["alarm"] else ("느린 경보" if row["slow"] else "조용")
    print(f'[signal] {row["day"]} {tag} · 지표 {row["n_board"]}/{len(SS.BOARD)} · 움직인 것 '
          + (", ".join(f"{n} {d:+.1f}σ(10일 {t:+.1f})" for n, d, t in row["movers"][:5]) or "없음")
          + (" · 서명 후보 " + ", ".join(f"{f} {s:.2f}" for f, s in row["candidates"]) if row["candidates"] else ""))
    if a.state:
        d = os.path.join(a.state, "records", "signals")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "scan.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
