"""뉴팩트 개성 있는 아이 찾기 게임 — 평범의 범위 · 간격을 사용자가 조절해 보는 화면 (2026-11-24 사용자).

길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md 0-0(바닥 규칙) · 0-1-1.
사용자: "중간값이 평범이지, 여기를 대략 80% 잡아 줘." · "평범의 범위도 조절하게 해 줘. 90% 최고 · 70% 최소."
        "20일 · 60일 · 120일 · 200일 간격이 더 좋은데." → **과거를 그 간격으로 잘라 조각마다** 본다(사용자 확인).
        첫 판 = 3년 통째, 둘째 판 = 최근 N일 한 구간 — 둘 다 틀렸다.
→ 조각마다 그 조각 안에서 중간값을 가운데 둔 가운데 N%(기본 80, 70 ~ 90)가 평범. 아이마다 평범 밖이던 조각 수(되풀이)를 센다.

    python experiments/stock-character/look_band.py     # → output/mock_band.html — 목업 목록 http://localhost:8800/ 의 `개성 있는 아이 찾기 게임`

화면 틀 = look_band_page.html (같은 폴더). 자료 = data/store/character/bars_us.pkl · earn_days_us.csv. 미국 S&P 500.
과거 범위 = 화면에서 최근 1 · 2 · 3년 중 고름(2026-11-24 사용자 "범위는 안 늘린다. 1년 · 2년 · 3년도 선택하게 해 줘") — 3년치 조각을 담고 화면이 뒤에서부터 잘라 쓴다.
칸 넷(조각마다 다시 잼, 모든 아이 같은 잣대): 평소 하루 폭(호수) · 예고 없는 돌 수(실적 · 파도 날이 아닌 ±5%) · 방향 크기(조각 처음 → 끝 등락) · 거래량 튄 날 수(평소의 2배).
"""

import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
STORE = os.path.join(ROOT, "data", "store", "character")
OUT = os.path.join(HERE, "output", "mock_band.html")
sys.path.insert(0, HERE)
import look_stones as LS  # noqa: E402

WINS = [20, 60, 120, 200]
SPAN = 756          # 담아 두는 과거(거래일) = 3년. 더 늘리지 않는다(사용자). 화면에서 1 · 2 · 3년을 고른다
ROSTER = {"COIN": "A", "BE": "A", "SMCI": "A", "BRK-B": "A", "KO": "A", "RSG": "A", "PG": "A", "L": "A", "LIN": "A", "WM": "A", "JNJ": "A",
          "TSLA": "B", "MSI": "C", "MSFT": "미정", "SCHW": "미정",
          # D = 단체 그룹 — 같은 때 같이 움직인 무리(2026-11-24 사용자 "그룹으로 일단 해놔 D 단체 그룹"). 메모리 · 저장장치 · 반도체 장비 · 전자부품 아홉(길잡이 7-19). 코닝은 B 에서 여기로.
          "MU": "D", "WDC": "D", "STX": "D", "LRCX": "D", "AMAT": "D", "KLAC": "D", "TER": "D", "GLW": "D", "FLEX": "D"}


def main():
    page = open(os.path.join(HERE, "look_band_page.html"), encoding="utf-8").read()
    bars = pd.read_pickle(os.path.join(STORE, "bars_us.pkl"))
    earn = pd.read_csv(os.path.join(STORE, "earn_days_us.csv"), parse_dates=["day"])
    eg = {s: g for s, g in earn.groupby("sym")}
    ref = json.load(open(os.path.join(ROOT, "experiments", "ref", "quick_ref.json"), encoding="utf-8"))["us"]
    C = pd.DataFrame({s: d["close"] for s, d in bars.items() if not s.startswith("^")})
    hit = C.pct_change().abs() * 100 >= LS.STONE
    share = hit.sum(axis=1) / C.notna().sum(axis=1)
    waves = set(share[share >= LS.WAVE_SHARE].index)
    days = C.index[-SPAN:]
    last = days[-1]
    # 조각 = 맨 끝(기준일)에서 거꾸로 W일씩. 왼쪽 = 옛날.
    cuts = {W: [(SPAN - W * (k + 1), SPAN - W * k) for k in range(SPAN // W)][::-1] for W in WINS}
    labels = {W: [f"{days[a].date()} ~ {days[b - 1].date()}" for a, b in cuts[W]] for W in WINS}
    rows = []
    for s, d in bars.items():
        if s.startswith("^") or s not in eg:
            continue
        d = d[(d["open"] > 0) & (d["volume"] > 0)]
        if len(d) < 300 or d.index.max() != last:
            continue
        idx = d.index
        sched = LS.sched_days(idx, eg[s])
        ret = (d["close"].pct_change() * 100).values
        un = pd.Series([bool(abs(r) >= LS.STONE and i not in sched and t not in waves) for i, (t, r) in enumerate(zip(idx, ret))], index=idx)
        f = pd.DataFrame({"c": d["close"], "rng": (d["high"] - d["low"]) / d["close"] * 100, "un": un.astype(float),
                          "vs": (d["volume"] / d["volume"].rolling(250, min_periods=60).median() >= LS.VOL2).astype(float)}).reindex(days)
        prev = d["close"].reindex(C.index).shift(1).reindex(days)
        w = {}
        for W in WINS:
            ps = []
            for a, b in cuts[W]:
                g = f.iloc[a:b]
                if g["c"].notna().sum() < W * 0.9 or pd.isna(prev.iloc[a]):
                    ps.append(None)                    # 상장 전 · 자료가 모자란 조각
                    continue
                ps.append([round(float(g["rng"].median()), 2), int(g["un"].sum()),
                           round(abs(float(g["c"].dropna().iloc[-1] / prev.iloc[a] - 1)) * 100, 1), int(g["vs"].sum())])
            w[W] = ps
        rows.append({"s": s, "k": (ref.get(s.replace("-", ".")) or ref.get(s) or {}).get("ko"), "g": ROSTER.get(s), "w": w})
    cols = [[0, "평소 하루 폭 (호수)", 1, "%", "그 조각에서 하루 동안 얼마나 오르내렸나(가운데 값)"],
            [1, "예고 없는 돌 수", 0, "개", "실적 · 파도 날이 아닌 날에 ±5% 넘게 움직인 횟수"],
            [2, "방향 크기", 0, "%", "조각 처음과 끝의 등락 크기(오름 · 내림 구분 없이)"],
            [3, "거래량 튄 날 수", 0, "일", "거래량이 평소(지난 250일 가운데 값)의 2배를 넘은 날"]]
    html = (page.replace("__DATA__", json.dumps(rows, ensure_ascii=False, separators=(",", ":"))).replace("__COLS__", json.dumps(cols, ensure_ascii=False))
            .replace("__N__", str(len(rows))).replace("__LAST__", str(last.date())).replace("__FIRST__", str(days[0].date()))
            .replace("__WINS__", json.dumps(WINS)).replace("__LABELS__", json.dumps(labels)))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(html)
    print(f"화면 → {OUT} · 아이 {len(rows)}명 · {days[0].date()} ~ {last.date()} · 조각 수 "
          + " · ".join(f"{W}일 {len(cuts[W])}" for W in WINS) + f" · {os.path.getsize(OUT) // 1024}KB")


if __name__ == "__main__":
    main()
