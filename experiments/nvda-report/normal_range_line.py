"""맨 위 한 줄 (W1) · 시장 충격 표시 (W2) — doc/리포트-재설계/4단계-세부-계획.md · doc/리포트-재설계/적용-기준-3단계.md A2 · A3.

자는 검증된 평소 범위 (doc/리포트-재설계/평소-범위-검증-계획.md C1 · C5 · C10):
- σ = EWMA (λ 0.94, 종가 대비 종가 로그 수익률, 실적 반응일 제외), 전날 종가까지의 값으로 오늘을 잰다
- 평소 범위 밖 = |z| ≥ 2 (실패 비용 검증 F2 와 같은 경계)
- "1년에 몇 번" = 지난 252거래일 중 |z| 가 오늘 이상이었던 날 수
- 시장 충격 = VIX 종가 ≥ 35 시작 · < 25 끝. 흔들림 가라앉는 시간 = 충격 첫 5거래일 EWMA 최대 ÷ 시작 전 252일 σ 로 세 묶음 (C10)
숫자는 전부 파이썬, 문장은 render_html 의 고정 틀.
"""

import math

import collect_market
import config

LAM = 0.94
Z_OUT = 2.0
VIX_IN, VIX_OUT = 35.0, 25.0
# C10 결과 (평소-범위-검증-계획.md 9-1): 경계 1.53 · 1.84배, 회복 일수 중앙값 · 사분위
RECOVERY = [(1.53, "작음", 13, (8, 28)), (1.84, "중간", 36, (21, 80)), (float("inf"), "큼", 52, (37, 89))]


def _earnings_reaction_days(conn, days):
    """실적 발표일 → 반응일. 엔비디아는 장 마감 뒤 발표 → 다음 거래일 (C6)."""
    out = set()
    for r in conn.execute("SELECT day FROM calendar WHERE kind = 'EARNINGS' AND (symbol = ? OR symbol IS NULL)", (config.SYMBOL,)):
        d = r["day"]
        nxt = [x for x in days if x > d]
        if nxt:
            out.add(nxt[0])
    return out


def _std(xs):
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def series(conn, day):
    """오늘까지 날짜 · 로그 수익률 · 전날까지 EWMA σ(오늘 잰 자) · 그날까지 EWMA σ · 252일 σ(전날까지) · z."""
    bars = [b for b in collect_market.bars(conn, config.SYMBOL) if b["day"] <= day]
    days = [b["day"] for b in bars]
    earn = _earnings_reaction_days(conn, days)
    rows, var, hist = [], None, []
    for i in range(1, len(bars)):
        r = math.log(bars[i]["close"] / bars[i - 1]["close"])
        d = days[i]
        sd_before = math.sqrt(var) if var else None
        s252 = _std(hist[-252:]) if len(hist) >= 200 else None
        if d not in earn:   # 실적 반응일은 자에 넣지 않는다 (C1 · C6)
            var = r * r if var is None else LAM * var + (1 - LAM) * r * r
            hist.append(r)
        rows.append({"day": d, "r": r, "sd": sd_before, "sd_now": math.sqrt(var) if var else None, "s252": s252,
                     "z": (r / sd_before) if sd_before else None, "earn": d in earn})
    return rows


def market_shock(conn, day):
    """VIX 상태 기계 — 오늘 종가 기준 충격 안인지, 시작일."""
    v = [dict(r) for r in conn.execute("SELECT day, close FROM daily_bars WHERE symbol = '^VIX' AND day <= ? AND close IS NOT NULL ORDER BY day", (day,))]
    inside, start = False, None
    for x in v:
        if not inside and x["close"] >= VIX_IN:
            inside, start = True, x["day"]
        elif inside and x["close"] < VIX_OUT:
            inside, start = False, None
    return {"active": inside, "start": start, "vix": v[-1]["close"] if v else None}


def compute(conn, day):
    rows = series(conn, day)
    if len(rows) < 260 or rows[-1]["day"] != day or rows[-1]["sd"] is None:
        return None
    t = rows[-1]
    z = t["z"]
    past = [abs(x["z"]) for x in rows[-253:-1] if x["z"] is not None and not x["earn"]]
    n_year = sum(1 for x in past if x >= abs(z))
    out = {"ret_log": t["r"], "ret_pct": (math.exp(t["r"]) - 1) * 100, "sigma_pct": t["sd"] * 100, "z": z,
           "outside": abs(z) >= Z_OUT, "n_year": n_year, "n_past": len(past), "earnings_day": t["earn"]}
    ms = market_shock(conn, day)
    if ms["active"]:
        idx = next((i for i, x in enumerate(rows) if x["day"] >= ms["start"]), None)
        early = None
        if idx is not None and rows[idx]["s252"]:
            seg = [x["sd_now"] for x in rows[idx:idx + 5] if x["sd_now"]]
            early = max(seg) / rows[idx]["s252"] if seg else None
        ms["days_in"] = len(rows) - idx if idx is not None else None
        ms["early_x"] = early
        ms["early_complete"] = idx is not None and len(rows) - idx >= 5
        if early is not None:
            for edge, name, med, (q1, q3) in RECOVERY:
                if early < edge:
                    ms["recovery"] = {"group": name, "median_days": med, "q1": q1, "q3": q3}
                    break
    out["market_shock"] = ms
    return out
