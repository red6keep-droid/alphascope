"""재설계 계산 (doc/기획/데일리-리포트-기획.md 4 ~ 6절) — analyze.analyze 가 부르고 analysis.json 에 붙인다.

- normal  (D3): 지수 · 대형주의 평소 범위. EWMA σ(λ 0.94, 로그 수익률), 전날까지의 σ 로 오늘을 잰다. |z| ≥ 2 = 평소 밖,
                "1년에 몇 번" = 지난 252거래일 중 |z| 가 오늘 이상이었던 날 수 (엔비디아 normal_range_line 과 같은 자)
- shock   (D6): VIX 종가 ≥ 35 시작 · < 25 끝 (엔비디아 W2 와 같은 상태 기계)
- korea   (K1 · K2): 오늘 미국 쪽 움직임의 크기 → 기록상 같은 크기의 밤 다음 날 한국 (static/daily_stats.json)
- fx      (K3 · D4): 원/달러 하루 변화 · 원화로 본 S&P 500
- calendar(D5): 앞으로 14일 일정 + 그 일정 날의 기록상 움직임
숫자는 전부 여기서, 문장은 render_html 의 고정 틀.
"""

import json
import math
import os

BASE = os.path.dirname(os.path.abspath(__file__))
STATS = os.path.join(BASE, "static", "daily_stats.json")
LAM, Z_OUT = 0.94, 2.0
VIX_IN, VIX_OUT = 35.0, 25.0
NORMAL_SYMBOLS = ["^GSPC", "^IXIC", "^DJI", "^RUT", "^SOX",
                  "NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "AVGO", "TSLA", "BRK-B", "LLY"]


def load_stats():
    try:
        with open(STATS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def normal_range(close):
    """close 목록(오래된 → 오늘) → 오늘 z 와 1년 횟수. 길이가 모자라면 None."""
    if not close or len(close) < 60:
        return None
    var, zs = None, []
    sd_before = None
    for i in range(1, len(close)):
        if not close[i - 1] or not close[i]:
            continue
        r = math.log(close[i] / close[i - 1])
        sd_before = math.sqrt(var) if var else None
        zs.append(r / sd_before if sd_before else None)
        var = r * r if var is None else LAM * var + (1 - LAM) * r * r
    z = zs[-1]
    if z is None or not sd_before:
        return None
    past = [abs(x) for x in zs[-253:-1] if x is not None]
    ret = (close[-1] / close[-2] - 1) * 100
    return {"ret_pct": round(ret, 2), "sigma_pct": round(sd_before * 100, 2), "z": round(z, 2),
            "outside": abs(z) >= Z_OUT, "n_year": sum(1 for x in past if x >= abs(z)), "n_past": len(past)}


def market_shock(vix_close):
    inside, start_i = False, None
    for i, v in enumerate(vix_close or []):
        if not inside and v >= VIX_IN:
            inside, start_i = True, i
        elif inside and v < VIX_OUT:
            inside, start_i = False, None
    return {"active": inside, "days_in": (len(vix_close) - start_i) if inside else None,
            "vix": round(vix_close[-1], 2) if vix_close else None}


def _bucket(z):
    if z is None:
        return None
    return "up" if z >= Z_OUT else "down" if z <= -Z_OUT else "normal" if abs(z) < 1 else "mid"


def korea(normal, stats):
    """짝마다 오늘 미국 쪽 z → 기록상 같은 크기의 밤. 1 ≤ |z| < 2 (mid) 는 기록 묶음이 없어 시작 가격 관계(beta)만."""
    out = []
    for p in stats.get("korea") or []:
        n = normal.get(p["us"])
        if not n:
            continue
        b = _bucket(n["z"])
        rec = (p.get("buckets") or {}).get(b) if b in ("up", "down", "normal") else None
        out.append({"kr": p["kr"], "kr_name": p["kr_name"], "us": p["us"], "us_name": p["us_name"],
                    "us_ret": n["ret_pct"], "us_z": n["z"], "bucket": b, "beta": p["beta_gap"], "corr": p["corr_gap"],
                    "r2": p["r2_gap"], "intra_any": p["intra_any"], "first": p["first"], "record": rec,
                    "buckets": {k: {"gap": v["gap"], "intra": v["intra"], "n": v["n"]} for k, v in (p.get("buckets") or {}).items()}})
    return out


FX_DAYS = 60   # 한국장 탭 `환율은?` 그래프 = 최근 60거래일 (2026-11-05 사용자 batch 8 ⑭: 숫자 줄을 가로 선 그래프로)


def fx(closes, series, dates=None):
    c = closes.get("KRW=X") or []
    spx = (series.get("^GSPC") or {}).get("ret_1d")
    if len(c) < 6:
        return None
    r1 = (c[-1] / c[-2] - 1) * 100
    won = ((1 + spx / 100) * (1 + r1 / 100) - 1) * 100 if spx is not None else None
    out = {"krw": round(c[-1], 2), "ret_1d": round(r1, 2), "ret_5d": round((c[-1] / c[-6] - 1) * 100, 2),
           "spx_won": round(won, 2) if won is not None else None}
    hist = _fx_hist(closes, dates or {})
    if hist:
        out["hist"] = hist
    return out


def _fx_hist(closes, dates):
    """최근 FX_DAYS 거래일 원/달러 · 원화로 본 S&P 500 (처음 = 100) — S&P 500 거래일 기준, 환율은 그날 또는 그 전 마지막 값.
    야후 환율의 튀는 값(자릿수 오류)은 build_daily_stats 와 같이 하루 10% 넘게 뛴 값을 뺀다."""
    kd, kc = dates.get("KRW=X") or [], closes.get("KRW=X") or []
    sd, sc = dates.get("^GSPC") or [], closes.get("^GSPC") or []
    if len(kd) != len(kc) or len(sd) != len(sc) or len(sd) < 2:
        return None
    k, prev = {}, None
    for d, v in zip(kd, kc):
        if v is None or (prev is not None and abs(v / prev - 1) > 0.1):
            continue
        k[d] = v
        prev = v
    kdays = sorted(k)
    if not kdays:
        return None
    days, spx = sd[-FX_DAYS:], sc[-FX_DAYS:]
    krw, j = [], 0
    for d in days:
        while j + 1 < len(kdays) and kdays[j + 1] <= d:
            j += 1
        krw.append(k[kdays[j]] if kdays[j] <= d else None)
    if sum(v is not None for v in krw) < 2:
        return None
    base_k, base_s = next(v for v in krw if v is not None), spx[0]
    return {"days": days,
            "krw": [round(v, 2) if v is not None else None for v in krw],
            "spx_usd": [round(s / base_s * 100, 2) for s in spx],
            "spx_won": [round(s / base_s * (v / base_k) * 100, 2) if v is not None else None for s, v in zip(spx, krw)]}


def calendar(raw_cal, stats):
    if not raw_cal:
        return None
    macro = stats.get("macro") or {}
    earn = stats.get("earnings") or {}
    items = []
    for it in raw_cal.get("items") or []:
        x = dict(it)
        if it["kind"] == "EARNINGS":
            e = earn.get(it.get("symbol"))
            if e:
                x["effect"] = {"median": e["median"], "normal": e["normal"], "n": e["n"]}
        else:
            k = (macro.get("kinds") or {}).get(it["kind"])
            if k:
                recent = (k.get("periods") or {}).get("2020") or {}
                x["effect"] = {"median": recent.get("median", k["median"]), "normal": recent.get("normal", macro.get("normal")),
                               "n": recent.get("n", k["n"]), "since": "2020" if recent else macro.get("from", "")[:4]}
        items.append(x)
    return {"from": raw_cal.get("from"), "to": raw_cal.get("to"), "days": raw_cal.get("days"), "items": items}


def build(raw, closes, series, dates=None):
    stats = load_stats()
    normal = {}
    for s in NORMAL_SYMBOLS:
        n = normal_range(closes.get(s))
        if n:
            normal[s] = n
    return {
        "normal": normal,
        "shock": market_shock(closes.get("^VIX")),
        "korea": korea(normal, stats),
        "fx": fx(closes, series, dates or {}),
        "calendar": calendar(raw.get("calendar"), stats),
        "regime_check": stats.get("regime"),
        "krw_check": stats.get("krw"),
        "stats_built": stats.get("built"),
    }
