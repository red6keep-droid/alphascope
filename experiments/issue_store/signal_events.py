"""신호 서명 검증용 사건표 늘리기 (기획 증시-전망-기획 8-19 3-a, 2026-11-08).

    .venv/bin/python experiments/issue_store/signal_events.py   → results/signal_events.csv

세 출처를 합친다 (AI 0):
1. events_curated.csv (159건, 손으로 확인한 사건) — 겹치면 이것이 이긴다.
2. data/store/calendar/shocks.csv 의 설명(explained_by) — 2000~, 같은 설명은 첫 날만(에피소드가 며칠 이어져도 사건 하나).
   설명 첫 토막을 아래 KEYWORDS 순서대로 맞춰 묶음을 정한다. 아무것도 안 맞으면 버린다.
3. GPR(지정학 위험 지수, 신문 기사 수 기반) 급등일 — 가격과 상관없이 뉴스로 잡힌 지정학 날짜. log GPR 이 직전 60일 평균 + 3σ 넘는 날, 20거래일 안 연속은 첫 날만.
   묶음 = `지정학 (GPR)` — 가격에서 뽑지 않았으니 "가격이 뉴스보다 먼저 움직였나" 를 공정하게 잴 수 있는 유일한 표본.
합칠 때 3거래일 안에 이미 사건이 있으면 버린다(우선: 1 > 2 > 3).
"""
import os
import re
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STORE = os.path.join(ROOT, "data", "store")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "signal_events.csv")
GPR_Z = float(next((a.split("=")[1] for a in sys.argv if a.startswith("--gpr-z=")), 3.0))   # 민감도 확인용 (기본 3σ)

# 사건표 subkind → 묶음 (지정학을 셋으로 나눔, 3-a)
CURATED_FAMILY = {
    "전쟁 · 테러": "전쟁 · 테러", "재난 · 팬데믹": "재난 · 팬데믹", "선거 · 정치": "선거 · 정치", "휴전 · 종전": "휴전 · 종전",
    "유가 충격": "유가 충격",
    "해외 금융위기": "금융 위기", "금융기관 부실 · 신용경색": "금융 위기",
    "연준 긴축 신호": "금리 긴축", "연준 완화": "금리 완화", "해외 중앙은행": "금리 긴축",
    "관세 · 무역": "정책 · 규제", "규제 (수출 · 반독점)": "정책 · 규제", "미국 재정 · 부채한도": "정책 · 규제",
    "환율 · 개입": "환율",
    "시장 구조 사고": "시장 충격", "기술주 · 반도체 급락": "시장 충격", "투매 뒤 반등 · 바닥": "반등 · 바닥",
    "경제지표 충격": "지표 · 실적", "실적 · 전망": "지표 · 실적", "기업 사업 소식": "지표 · 실적", "애널리스트 의견": "지표 · 실적",
}

# 설명 글 → 묶음. 위에서부터 먼저 맞는 것 (휴전이 전쟁보다, 바닥이 지표보다 먼저)
KEYWORDS = [
    ("휴전 · 종전", r"휴전|종전|정전 협정|평화 협정|평화 합의"),
    ("전쟁 · 테러", r"전쟁|침공|테러|공습|미사일|폭격|군사|유혈|분쟁|개전|핵실험|이스라엘|하마스|이란|북한|러시아군|지정학"),
    ("재난 · 팬데믹", r"코로나|팬데믹|변이|오미크론|델타|지진|쓰나미|허리케인|원전|사스|에볼라|독감|홍수|대유행"),
    ("유가 충격", r"유가|OPEC|감산|증산|원유|WTI|산유|브렌트"),
    ("금융 위기", r"파산|리먼|은행|신용 ?경색|부도|디폴트|모라토리엄|구제금융|정크|신용등급|등급 강등|월드컴|엔론|LTCM|SVB|크레디트|재정위기|금융위기|위기"),
    ("금리 완화", r"인하|완화|양적|QE|비둘기"),
    ("금리 긴축", r"인상|긴축|매파|테이퍼"),
    ("환율", r"위안|엔화|환율|페소|절하|개입|루블|리라|통화 ?위기|원화"),
    ("정책 · 규제", r"관세|무역|규제|수출 통제|반독점|셧다운|부채한도|재정 절벽|세금|감세|보조금"),
    ("선거 · 정치", r"선거|대선|총선|국민투표|브렉시트|탄핵|당선"),
    ("반등 · 바닥", r"바닥|반등|반전|저점"),
    ("지표 · 실적", r"CPI|PPI|PCE|고용|GDP|실적|소매|ISM|주택|지표|FOMC|매출|가이던스"),
    ("시장 충격", r"폭락|급락|블랙|볼마게돈|거품|청산|플래시|매도|붕괴"),
]


def classify(text):
    t = str(text).split(" · ")[0]
    for fam, pat in KEYWORDS:
        if re.search(pat, t):
            return fam
    return None


def main():
    cal = pd.read_parquet(os.path.join(STORE, "bars", "_GSPC.parquet")).index
    cal = pd.DatetimeIndex(cal).tz_localize(None).normalize()
    cal = cal[cal >= "1995-01-01"]
    pos = lambda d: cal.searchsorted(pd.Timestamp(d))

    rows = []
    cur = pd.read_csv(os.path.join(HERE, "events_curated.csv"))
    for _, e in cur.iterrows():
        rows.append({"start": e["start"], "family": CURATED_FAMILY.get(e["subkind"], "그 밖"), "title": e["title"], "source": "사건표"})

    sh = pd.read_csv(os.path.join(STORE, "calendar", "shocks.csv"))
    sh = sh[(sh["day"] >= "2000-01-01") & sh["explained_by"].notna()].sort_values("day")
    seen = set()
    n_drop = 0
    for _, e in sh.iterrows():
        key = str(e["explained_by"]).split(" · ")[0].strip()
        if key in seen:
            continue
        seen.add(key)
        fam = classify(key)
        if not fam:
            n_drop += 1
            continue
        rows.append({"start": e["day"], "family": fam, "title": key, "source": f"충격({e['market']})"})

    g = pd.read_csv(os.path.join(STORE, "calendar", "gpr_daily.csv"), parse_dates=["day"]).set_index("day")["gpr"]
    lg = np.log(g[g > 0])
    z = (lg - lg.rolling(60).mean().shift(1)) / lg.rolling(60).std().shift(1)
    last = None
    for d, v in z[(z >= GPR_Z) & (z.index >= "2000-01-01")].items():
        i = pos(d)
        if i >= len(cal):
            continue
        if last is not None and i - last < 20:
            continue
        last = i
        rows.append({"start": cal[i].strftime("%Y-%m-%d"), "family": "지정학 (GPR)", "title": f"GPR 급등 {d:%Y-%m-%d} (z {v:.1f})", "source": "GPR"})

    out, taken = [], []
    for r in rows:   # 우선순위대로 들어 있음: 사건표 → 충격 → GPR
        i = pos(r["start"])
        if any(abs(i - j) <= 3 for j in taken):
            continue
        taken.append(i)
        out.append(r)
    df = pd.DataFrame(out).sort_values("start")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"사건 {len(df)}건 (설명이 묶음에 안 맞아 버린 충격 {n_drop}건)")
    print(df.groupby(["family", "source"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
