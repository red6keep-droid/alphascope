# issue_store — 이슈 저장소 · 30년 데이터 (기획: doc/기획/데이터-기록-계획.md 2부 · doc/검증/볼린저-이슈별-검증-계획.md)

데이터는 깃 밖 `data/store/` (gitignore). 코드와 사람이 고치는 사건표만 여기.

| 파일 | 하는 일 | 결과 |
|---|---|---|
| `fetch_bars.py` | 일봉 전체 기간 (yfinance, 증분) — NVDA + 시장 · 섹터 · VIX · 금리 · 엔화 · 달러 · 원유 · 금 | `data/store/bars/*.parquet`, `manifest.json` |
| `fetch_calendar.py` | 경제지표 발표일 13종 (FRED release/dates) | `data/store/calendar/econ_releases.csv` |
| `fetch_fomc.py` | FOMC 회의 (연준 홈페이지) + 결정 (DFEDTAR · DFEDTARU) | `data/store/calendar/fomc.csv` |
| `build_calendar_misc.py` | 실적(9월 백테스트 earnings.csv) · 옵션 만기 · 분기 말 | `earnings.csv`, `market_structure.csv` |
| `events_curated.csv` | **큰 사건표 — 사람이 고친다** (시작일 · 기간 · 종류 · 대상) | 깃에 올림 |
| `event_vocab.py` | 사건표 세부 종류 **고정 어휘 21개** + 세부 종류별 대분류 (2026-10-17 확정). 원래 표현은 `detail` 칸. 사건표를 고친 뒤 한 번 돌리면 정리 · 검사 | `events_curated.csv` 덮어씀 |

다른 PC에서: `.venv/bin/pip install pyarrow` 뒤 위 네 스크립트를 순서대로 (FRED_API_KEY 필요).
