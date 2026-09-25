# backtest/ — 10년치 데이터 보관소

알파 종목 매수 타이밍 검증([doc/알파-종목-매수-타이밍-검증-계획.md](../doc/알파-종목-매수-타이밍-검증-계획.md))에 쓰는
2015-06 ~ 현재 데이터를 여기에 모은다. `data/`는 gitignore — 이 컴퓨터에만 있고, 지우면 아래 명령으로 다시 받는다.

| 파일 | 내용 | 출처 · 다시 받기 |
| --- | --- | --- |
| `data/bars.pkl` | S&P 500 500종목 + 섹터 ETF 11 + SPY + VIX 일봉 (OHLCV, 분할·배당 반영) · 68 MB | yfinance · `.venv/bin/python experiments/signal-study/main.py --refresh-prices` |
| `data/universe.csv` | S&P 500 종목 · GICS 섹터 · 섹터 ETF · **편입일(`added`)** | Wikipedia · `--refresh-universe`, 편입일은 `extra_data.py` |
| `data/removed.csv` · `data/removed.pkl` | 2016년 이후 지수에서 **빠진 종목** 218개의 제외일·사유·판정(`status`), 그중 일봉을 받을 수 있는 95종목 (생존 편향 측정용). 인수·합병으로 사라진 114종목은 yfinance에 없음. 티커가 다른 회사에 재사용된 9종목은 회사명 대조로 제외 | Wikipedia "Historical components" · `extra_data.py` |
| `data/earnings.csv` | 종목별 실적 발표일 · **EPS 예상·실제·서프라이즈(%)** 499종목 43,126건 (XEL·XOM·XYL·XYZ 없음) | yfinance · `extra_data.py` |
| `data/macro.pkl` | TLT · IEF · ^TNX · ^IRX · HYG · LQD · CL=F (WTI) · GC=F (금) · HG=F (구리) · DX-Y.NYB (달러 인덱스) · ^GSPC · ^IXIC · ^DJI · ^RUT 일봉 · SPY_long (2014-06~, 200일선용) · 1.8 MB | yfinance (2026-09-24 수집) |
| `data/fred_*.csv` | UNRATE · CPIAUCSL · FEDFUNDS (월간) · DGS10 · DGS2 (일간) | FRED CSV, 키 불필요 |

읽는 코드: `experiments/signal-study/config.py`의 `DATA_DIR`이 이 폴더를 가리킨다.

## results/ — 회차별 결과 (커밋함)

| 폴더 | 내용 |
| --- | --- |
| `results/r01/` | 2026-09-24 · 데이터 점검 · ⓪ 섹터 순환 · ① 연속 상승. 요약은 계획 문서 8절 |
| `results/r02/` | 2026-09-24 · ③ 눌림 P0~P4 · ② 상승 포착 U1~U6 · 규칙 청산 3종 |
| `results/r03/` | 2026-09-24 · 승자의 사전 특징 — 분기 상위 20% 지속성 · 특징 16개 · 성장 대용치 |
| `results/r04/` | 2026-09-24 · 관심 종목(거래대금 급증 상위 10) — 진입 시점 · 보유 · 방향 · 10종목 2주 포트폴리오 · 거시 연관 |
| `results/r05/` | 2026-09-25 · 월 단위 종목 선택 — 모멘텀 · 성장 · 저변동성 · 조합 · 국면 스위치 · 손절, 10/20/50종목, 기대값·낙폭 |
| `results/r06/` | 2026-09-25 · 관심 종목 5개 + 낙폭 사다리 — 참조 지수 고점 대비 −20/−30/−40% 비중 조절, 20일 복귀, 교체 주기 5~60일 |
