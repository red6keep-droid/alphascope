# backtest/ — 10년치 데이터 보관소

알파 종목 매수 타이밍 검증([doc/알파-종목-매수-타이밍-검증-계획.md](../doc/알파-종목-매수-타이밍-검증-계획.md))에 쓰는
2015-06 ~ 현재 데이터를 여기에 모은다. `data/`는 gitignore — 이 컴퓨터에만 있고, 지우면 아래 명령으로 다시 받는다.

| 파일 | 내용 | 출처 · 다시 받기 |
| --- | --- | --- |
| `data/bars.pkl` | S&P 500 500종목 + 섹터 ETF 11 + SPY + VIX 일봉 (OHLCV, 분할·배당 반영) · 68 MB | yfinance · `.venv/bin/python experiments/signal-study/main.py --refresh-prices` |
| `data/universe.csv` | S&P 500 종목 · GICS 섹터 · 섹터 ETF (편입일 열 추가 예정) | Wikipedia · `--refresh-universe` |
| `data/earnings.csv` | 종목별 실적 발표일 | yfinance · `--refresh-earnings` |
| `data/macro.pkl` | TLT · IEF · ^TNX · ^IRX · HYG · LQD · CL=F · ^GSPC · ^IXIC · ^DJI · ^RUT 일봉 · 1.4 MB | yfinance (2026-09-24 수집) |
| `data/fred_*.csv` | UNRATE · CPIAUCSL · FEDFUNDS (월간) · DGS10 · DGS2 (일간) | FRED CSV, 키 불필요 |

읽는 코드: `experiments/signal-study/config.py`의 `DATA_DIR`이 이 폴더를 가리킨다.
