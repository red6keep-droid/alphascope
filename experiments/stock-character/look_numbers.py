"""눈으로 본 꼴을 쉬운 숫자로 옮기기 — 네 종목 · 2개월 조각 (2026-11-24, 길잡이 4절 2 · 3번).

길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md 7-1절(그림 본 것) → 이 숫자가 그림과 맞는지 확인용.
모든 종목 같은 잣대(돌 = 하루 ±5%) — 자기 평소 대비로 재지 않는다(길잡이 5절).

    python experiments/stock-character/look_numbers.py
"""

import sys

import numpy as np
import pandas as pd
import yfinance as yf

SYMS = sys.argv[1:] or ["JPM", "TSLA", "MSFT", "CRCL"]
PIECE = 42          # 2개월 ≈ 42거래일
STONE = 5.0         # 돌 = 하루 등락 ±5% (모든 종목 같은 잣대)
VOL2 = 2.0          # 거래량 = 1년 평소(중앙값)의 2배


def load(s):
    d = yf.download(s, period="2y", interval="1d", auto_adjust=True, progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.rename(columns=str.lower).dropna(subset=["close"])
    d = d[(d["open"] > 0) & (d["volume"] > 0)].iloc[-252:].copy()
    d["ret"] = d["close"].pct_change() * 100
    d["rng"] = (d["high"] - d["low"]) / d["close"] * 100
    d["volx"] = d["volume"] / d["volume"].median()
    return d


def earn_days(s):
    try:
        e = yf.Ticker(s).get_earnings_dates(limit=12)
        return {i.tz_localize(None).normalize() for i in e.index} if e is not None else set()
    except Exception:  # noqa: BLE001
        return set()


def calm_back(d, i):
    """돌 뒤 ① 물결 평온 — 돌 다음 날부터 5일 평균 하루 폭이 돌 앞 20일 하루 폭 중앙값의 1.2배 안으로 들어온 첫날(거래일).
    40일 안에 안 오면 '40일+', 자료가 먼저 끝나면 '아직(n일째)'."""
    lake = d["rng"].iloc[max(0, i - 20):i].median()
    after = d["rng"].iloc[i + 1:i + 46].rolling(5).mean()
    for k, v in enumerate(after.values):
        if k >= 4 and v <= lake * 1.2:
            return k - 3   # 5일 창의 첫날 기준
    left = len(d) - 1 - i
    return "40일+" if left >= 45 else f"아직({left}일째)"


def price_back(d, i, cap=120):
    """돌 뒤 ② 가격 회복 — 종가가 돌 전날 종가로 되돌아온 첫날(거래일). 내린 돌 = 되오름, 오른 돌 = 되밀림.
    cap 일 안에 안 오면 '안 돌아옴(계단)', 자료가 먼저 끝나면 '아직(n일째)'. 함께 20일 뒤 돌 크기의 몇 %를 되돌렸나."""
    pre, at = d["close"].iloc[i - 1], d["close"].iloc[i]
    down = at < pre
    days = None
    for k in range(i + 1, min(len(d), i + 1 + cap)):
        c = d["close"].iloc[k]
        if (down and c >= pre) or (not down and c <= pre):
            days = k - i
            break
    left = len(d) - 1 - i
    if days is None:
        days = "안 돌아옴" if left >= cap else f"아직({left}일째)"
    give = None
    if i + 20 < len(d):
        give = (d["close"].iloc[i + 20] - at) / (pre - at) * 100   # 100 = 돌 전 자리, 0 = 돌 자리 그대로, 음수 = 돌 방향으로 더 감
    return days, give


def main():
    for s in SYMS:
        d = load(s)
        ed = earn_days(s)
        near_earn = lambda t: any(abs((t.normalize() - x).days) <= 1 for x in ed)   # noqa: E731 — 발표 당일 · 다음 날(장 마감 뒤 발표)
        print(f"\n=== {s}  {d.index[0].date()} ~ {d.index[-1].date()}  (실적일 {len(ed)}개 받음)")
        print(f"{'조각':12} {'등락':>6} {'호수(폭)':>8} {'돌':>4} {'거래량실린돌':>10} {'거래량만':>8}")
        n = len(d)
        for k in range(6):
            c = d.iloc[max(0, n - PIECE * (6 - k)): n - PIECE * (5 - k)]
            if len(c) < 5:
                continue
            st = c["ret"].abs() >= STONE
            print(f"{c.index[0].strftime('%y.%m')}~{c.index[-1].strftime('%m'):>2}월  {(c['close'].iloc[-1] / c['close'].iloc[0] - 1) * 100:+5.0f}% "
                  f"{c['rng'].median():7.1f}% {int(st.sum()):4} {int((st & (c['volx'] >= VOL2)).sum()):10} "
                  f"{int(((c['volx'] >= VOL2) & (c['ret'].abs() < 2)).sum()):8}")
        stones = [i for i in range(1, n) if abs(d["ret"].iloc[i]) >= STONE]
        if stones and len(stones) <= 25:
            print("  돌 하나하나: 날짜 · 등락 · 거래량 배수 · 실적일 근처 · ① 물결 평온까지 · ② 가격 돌 전 자리까지 · 20일 뒤 되돌린 몫")
            for i in stones:
                t = d.index[i]
                pb, give = price_back(d, i)
                g = "—" if give is None else f"{give:+.0f}%"
                print(f"   {t.date()}  {d['ret'].iloc[i]:+6.1f}%  {d['volx'].iloc[i]:4.1f}배  {'실적' if near_earn(t) else '  - '}  "
                      f"① {str(calm_back(d, i)):>10}  ② {str(pb):>10}  {g:>6}")
        elif stones:
            ce = sum(near_earn(d.index[i]) for i in stones)
            cbs = [calm_back(d, i) for i in stones]
            pbs = [price_back(d, i) for i in stones]
            ok1 = [x for x in cbs if isinstance(x, int)]
            ok2 = [x for x, _ in pbs if isinstance(x, int)]
            gv = [g for _, g in pbs if g is not None]
            print(f"  돌 {len(stones)}개 — 실적일 근처 {ce}개")
            print(f"   ① 물결 평온까지 중앙값 {np.median(ok1):.0f}일 · 40일+ {cbs.count('40일+')}개 · 아직 {sum(isinstance(x, str) and x.startswith('아직') for x in cbs)}개")
            print(f"   ② 가격 돌 전 자리까지 중앙값 {np.median(ok2):.0f}일(돌아온 {len(ok2)}개) · 안 돌아옴 {sum(x == '안 돌아옴' for x, _ in pbs)}개 · 아직 {sum(isinstance(x, str) and x.startswith('아직') for x, _ in pbs)}개"
                  f" · 20일 뒤 되돌린 몫 중앙값 {np.median(gv):+.0f}%")


if __name__ == "__main__":
    main()
