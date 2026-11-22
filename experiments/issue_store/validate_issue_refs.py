"""Hot Issue 비교 지표 검증 (2026-11-22 사용자: "뉴팩트는 늘 비교 대상이 있어야 한다 — 무엇과 비교하면 잘 전달되나").

질문: 이슈마다 화면에 나란히 둘 지표 후보가, 지난 같은 종류 사건 날에 정말 그 방향으로 반응했나 — 사건 하나하나로.
원칙 (doc/검증/HotIssue-비교지표-검증.md 1절):
- 사건 = Hot Issue 화면이 이미 쓰는 사건표 분류(mock_issue_watch.IF_SIDES 와 같은 규칙) — 화면과 같은 사건을 본다
- 움직임 = 사건 첫 거래일 하루(전날 종가 → 그날 종가) · 5거래일. 상대 지표는 두 수익률의 차(%p)
- 기준 = 그 지표 자신의 평소 흔들림(직전 250거래일 하루 움직임 표준편차 × √기간) → z. z ≥ 1 이면서 맞는 방향 = `반응`
- 우연 대조 = 같은 계산을 그 지표의 아무 날 전부에 — `아무 날 반응 비율`. 사건 날 비율과 나란히 (판정 문턱으로 쓰지 않는다: 30년은 기준선 · 사례용)
- 결과 = 사건별 표가 먼저, 합친 숫자는 뒤 참고
자료 = data/store/bars (30년 저장소, 로컬).

    .venv/bin/python experiments/issue_store/validate_issue_refs.py   → experiments/issue_store/results/issue_refs_*.csv + 표 출력
"""
import os
import re

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
BARS = os.path.join(ROOT, "data", "store", "bars")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
HZ = (1, 5)
WIN = 250

# 지표 = (이름, 기호, 빼는 기호 또는 None) — 빼는 기호가 있으면 상대 지표(%p)
IND = {
    "spx": ("S&P 500", "_GSPC", None),
    "vix": ("불안 지수(VIX)", "_VIX", None),
    "oil": ("유가(WTI)", "CL_F", None),
    "gold": ("금", "GC_F", None),
    "xle": ("에너지 업종 − S&P 500", "XLE", "_GSPC"),
    "ita": ("방산 − S&P 500", "ITA", "_GSPC"),
    "sox": ("반도체 지수 − S&P 500", "_SOX", "_GSPC"),
    "xli": ("산업재 − S&P 500", "XLI", "_GSPC"),
    "xly": ("소비재(수입 많은 업종) − S&P 500", "XLY", "_GSPC"),
    "fxi": ("중국 대형주 ETF − S&P 500", "FXI", "_GSPC"),
    "cny": ("위안화 약세(달러당 위안)", "CNY_X", None),
    "dxy": ("달러 지수", "DX-Y.NYB", None),
    "nvda": ("엔비디아 − 반도체 지수", "NVDA", "_SOX"),
    "amat": ("장비(어플라이드) − 반도체 지수", "AMAT", "_SOX"),
}

# 이슈 = 쪽마다 사건 고르는 규칙(IF_SIDES 와 같음) + 지표별 `확전 · 강화` 때 기대 방향(+1 오름 · −1 내림). 반대쪽(종전 · 완화)은 부호를 뒤집어 본다
ISSUES = {
    "IRAN": {"name": "이란 전쟁", "up": "확전", "down": "종전",
             "sides": {"확전": dict(sub="전쟁 · 테러", inc=r"이란|이라크|이스라엘|사우디|리비아|하마스", exc=None),
                       "종전": dict(sub="휴전 · 종전", inc=None, exc=None)},
             "ind": {"oil": 1, "xle": 1, "ita": 1, "gold": 1, "vix": 1, "spx": -1}},
    "TARIFF": {"name": "관세", "up": "확전", "down": "완화",
               "sides": {"확전": dict(sub="관세 · 무역", inc=None, exc=r"유예|합의|휴전|타결"),
                         "완화": dict(sub="관세 · 무역", inc=r"유예|합의|휴전|타결", exc=None)},
               "ind": {"spx": -1, "vix": 1, "sox": -1, "xli": -1, "xly": -1, "fxi": -1, "cny": 1, "dxy": 1}},
    "EXPORT": {"name": "반도체 수출 통제", "up": "강화", "down": "완화",
               "sides": {"강화": dict(sub="규제 (수출 · 반독점)", inc=r"수출", exc=None)},
               "ind": {"sox": -1, "nvda": -1, "amat": -1, "spx": -1}},
}


def close(sym):
    b = pd.read_parquet(os.path.join(BARS, f"{sym}.parquet"))
    s = b["close"].astype(float)
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s[~s.index.duplicated()].dropna()


_C = {}


def series(key):
    """지표 하루 수익률(%) — 상대 지표는 차(%p). 두 쪽 다 있는 날만."""
    if key in _C:
        return _C[key]
    _, a, b = IND[key]
    ra = close(a).pct_change() * 100
    if b:
        rb = close(b).pct_change() * 100
        r = (ra - rb).dropna()
    else:
        r = ra.dropna()
    _C[key] = r
    return r


def move(r, t0, h):
    """사건 첫 거래일(t0 이상 첫 날)부터 h거래일 움직임 합(%·%p)과 z(직전 WIN일 하루 표준편차 × √h)."""
    idx = r.index.searchsorted(pd.Timestamp(t0))
    if idx >= len(r) or idx < WIN:
        return None
    m = r.iloc[idx:idx + h].sum()
    sd = r.iloc[idx - WIN:idx].std() * np.sqrt(h)
    return (round(float(m), 2), round(float(m / sd), 2) if sd > 0 else None, r.index[idx].date().isoformat())


def placebo(r, sign, h):
    """아무 날 전부: sign·z ≥ 1 비율(반응) · sign·움직임 > 0 비율(방향만)."""
    roll = r.rolling(h).sum().shift(-(h - 1))
    sd = r.rolling(WIN).std().shift(1) * np.sqrt(h)
    z = (roll / sd).dropna()
    return float((sign * z >= 1).mean()), float((sign * z > 0).mean())


def pick(ev, rule):
    """사건표에서 그 쪽 사건 — 세부 분류(subkind) + 제목 · 세부 낱말 포함(inc) · 제외(exc). IF_SIDES 와 같은 규칙."""
    s = ev[ev.subkind == rule["sub"]]
    txt = s.title.fillna("") + " " + s.detail.fillna("")
    if rule.get("inc"):
        s, txt = s[txt.str.contains(rule["inc"])], txt[txt.str.contains(rule["inc"])]
    if rule.get("exc"):
        s = s[~txt.str.contains(rule["exc"])]
    return s


def run():
    ev = pd.read_csv(os.path.join(ROOT, "experiments", "issue_store", "events_curated.csv"))
    os.makedirs(OUT, exist_ok=True)
    rows, summ = [], []
    for iid, iss in ISSUES.items():
        for side, rule in iss["sides"].items():
            flip = 1 if side == iss["up"] else -1
            evs = pick(ev, rule)
            for _, e in evs.iterrows():
                for k, sgn in iss["ind"].items():
                    for h in HZ:
                        m = move(series(k), e.start, h)
                        rows.append({"issue": iid, "side": side, "start": e.start, "title": e.title[:40], "ind": k, "h": h,
                                     "move": m[0] if m else None, "z": m[1] if m else None, "day0": m[2] if m else None,
                                     "want": sgn * flip,
                                     "hit": (m is not None and m[1] is not None and sgn * flip * m[1] >= 1)})
            for k, sgn in iss["ind"].items():
                for h in HZ:
                    sub = [x for x in rows if x["issue"] == iid and x["side"] == side and x["ind"] == k and x["h"] == h and x["z"] is not None]
                    p_hit, p_dir = placebo(series(k), sgn * flip, h)
                    summ.append({"issue": iid, "side": side, "ind": k, "h": h, "n": len(sub),
                                 "hit": sum(x["hit"] for x in sub), "dir": sum((x["want"] * x["move"]) > 0 for x in sub),
                                 "placebo_hit": round(p_hit, 3), "placebo_dir": round(p_dir, 3)})
    df, sm = pd.DataFrame(rows), pd.DataFrame(summ)
    df.to_csv(os.path.join(OUT, "issue_refs_events.csv"), index=False)
    sm.to_csv(os.path.join(OUT, "issue_refs_summary.csv"), index=False)
    return df, sm


if __name__ == "__main__":
    df, sm = run()
    pd.set_option("display.width", 220)
    for (iid, side), g in df[df.h == 1].groupby(["issue", "side"], sort=False):
        t = g.pivot_table(index=["start", "title"], columns="ind", values="z", aggfunc="first")
        print(f"\n### {ISSUES[iid]['name']} · {side} — 하루 z (평소 흔들림의 몇 배, 부호 = 실제 방향)")
        print(t.to_string())
    print("\n### 요약 (반응 = 맞는 방향 z≥1)")
    sm["ev_rate"] = (sm.hit / sm.n).round(2)
    print(sm.to_string(index=False))
