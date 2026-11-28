"""거시 흐름 검증용 긴 과거 — FRED 경기 · 고용 · 금융 여건 계열을 전 기간 한 번 받는다(정기 실행 아님).

    .venv/bin/python experiments/issue_store/fetch_macro_history.py

저장: data/store/fred/{id}.csv (day, value) — fetch_fred_daily.py 와 같은 꼴. 그쪽은 1995 ~ 만 두니 여기 계열은 겹치지 않게 따로.
날짜 = FRED 의 관측 날짜(주간 계열은 그 주 끝, 월 · 분기 계열은 그 기간 첫날). **발표는 더 늦다** —
검증에서 "그날 알 수 있던 값"으로 쓰려면 아래 LAG 만큼 밀어서 쓴다. 지금 값은 고쳐진 최신 판(발표 당시 값 아님).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from fetch_fred_daily import OUT, fetch  # noqa: E402

SERIES = {   # id: (이름, 주기, 발표까지 대략 늦음 — 검증에서 밀어 쓸 날수)
    "USREC": ("미국 침체 달 표시(전미경제연구소, 사후 판정)", "월", None),   # 사후 대조용으로만
    "UNRATE": ("실업률", "월", 35),
    "ICSA": ("신규 실업수당 청구", "주", 5),
    "IC4WSA": ("신규 실업수당 4주 평균", "주", 5),
    "INDPRO": ("산업생산", "월", 45),
    "GDPC1": ("실질 국내총생산", "분기", 120),
    "NFCI": ("시카고 연준 금융여건지수", "주", 5),
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for sid, (name, freq, lag) in SERIES.items():
        df = fetch(sid, start="1900-01-01")
        df.to_csv(os.path.join(OUT, f"{sid}.csv"), index=False)
        print(f"{name} ({sid}, {freq}): {df['day'].iloc[0]} ~ {df['day'].iloc[-1]} · {len(df)}행 · 발표 늦음 {lag}일")


if __name__ == "__main__":
    main()
