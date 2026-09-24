# 신호 스터디 (experiments/signal-study)

"특정 주식이 조건에 맞는 상승을 시작했을 때 사면 수익이 날 확률은?"에 과거 데이터로 답하는 일회성 스터디.
어디에도 게시하지 않는다. 산출물은 `output/results.md`(표) 와 `output/events.csv`(신호 목록) 둘이다.

규칙은 `reference2/doc/MRH_v1/MRH_Signal_Engine_Core_Specification_V1.md` 6~10장의 값을 그대로 쓴다 (2026-09-24 확정).
손절 −7% / 목표 +10% 는 같은 날 사용자가 정했다.

## 방법

1. **유니버스** — 현재 S&P 500 구성 종목 + GICS 섹터 (Wikipedia). 섹터 → SPDR ETF(XLK·XLF·…)로 대응.
2. **일봉** — yfinance, 2015-06 ~, 분할·배당 반영가. 종목 + 섹터 ETF + SPY + VIX.
3. **모든 (종목, 거래일)에 대해** 조건값(당일 상승률 · RVOL · 종가 위치 · 5일 누적 · 섹터 ETF 20일선)과
   매수 결과(3·5·7일 보유, 손절/목표)를 미리 계산한다 — `outcomes.py`.
4. **신호** = 조건 다섯 개 모두 충족. 같은 종목 5거래일 안 재발생은 첫 날만. 진입은 **다음 거래일 시가**.
5. **통계** — 승률(비용 후) + Wilson 95% 구간 · 평균/중앙값 · SPY 대비 초과.
6. **플라시보** — 같은 종목의 비신호 날을 같은 수만큼 1,000회 재추출해 "아무 날 샀을 때" 승률 분포를 만들고,
   관측 승률이 그 이상일 확률 p 를 낸다. **승률 자체가 아니라 이 차이가 조건의 효과다.**
7. 기간(탐색 ~2022 / 검증 2023~) · 국면(RISK ON/OFF) · 실적 인접 · 조건 절제 · 연도 · 섹터로 나눠 본다.

## 구조

```
experiments/signal-study/
├── main.py        # 실행
├── config.py      # 확정값 전부 (규칙 · 보유 · 비용 · 검정)
├── universe.py    # S&P 500 목록 + 섹터 (data/universe.csv 캐시)
├── prices.py      # 일봉 (data/bars.pkl) · 실적일 (data/earnings.csv)
├── outcomes.py    # 조건값 · 매수 결과 — 모든 날
├── study.py       # 신호 · 군집 · 통계 · 플라시보 · 절제
├── render.py      # → output/results.md · output/events.csv
├── data/          # 캐시 (gitignore)
└── output/        # 산출물 (gitignore)
```

## 실행

리포 루트의 `.venv` (Python 3.12) 를 쓴다.

```bash
.venv/bin/pip install -r experiments/signal-study/requirements.txt
.venv/bin/python experiments/signal-study/main.py                   # 캐시 재사용 (두 번째부터 ~1분)
.venv/bin/python experiments/signal-study/main.py --refresh-prices  # 일봉 다시 받기
.venv/bin/python experiments/signal-study/main.py --skip-earnings   # 실적일 수집 생략
```

첫 실행은 일봉 약 520심볼(1~2분) 과 실적일 503종목(2~3분)을 받는다.

## 규칙을 바꿀 때

`config.py` 의 `RULE` · `HORIZONS` · `STOP` · `TARGET` 만 고치고 다시 돌린다. 단, **탐색 구간 표만 보고 고칠 것.**
검증 구간(2023~)을 보면서 규칙을 다듬으면 그 구간의 숫자는 더 이상 검증이 아니다.

## 한계

- 생존 편향: 현재 지수 구성으로 과거를 본다. 상장폐지·퇴출 종목이 빠져 승률이 실제보다 좋게 나온다.
- 체결 가정: 다음 날 시가, 손절·목표가 정확히 체결. 실제는 더 나쁘다.
- XLC(2018-06)·XLRE(2015-10) 상장 전에는 그 섹터 종목의 신호가 빠진다.
- 이 스터디는 과거 빈도다. 미래 확률이 아니다.
