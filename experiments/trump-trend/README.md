# 트럼프 SNS 트렌드 리포트 (experiments/trump-trend)

Trump의 Truth Social 게시물을 매일 수집해 분류하고, **이벤트 단위**로 묶어 트렌드와 시장의 **초과 반응**을 계산하는
그림자 모드 파이프라인이다. 어디에도 게시하지 않는다. 산출물은 `output/trump_report.md` 하나다.

기획·설계 근거: [doc/트럼프-SNS-트렌드-리포트-기획.md](../../doc/트럼프-SNS-트렌드-리포트-기획.md)

## 구조

```
experiments/trump-trend/
├── main.py             # 실행 (수집 → 가격 → 캘린더 → 분류 → 이벤트 → 스터디 → 집계 → MD)
├── config.py           # 확정값 전부 (enum · 가중치 · 임계값 · 유니버스 · 배치 크기)
├── db.py               # SQLite 스키마 (trump_posts · trump_events · event_reactions · daily_bars · macro_calendar)
├── collect_posts.py    # CNN Truth archive JSON → 새 id만 저장 + 사전 필터
├── prefilter.py        # 1단계 노이즈 필터 (no_text / bare_reshare / self_repost / greeting / too_short)
├── labels.py           # subtopic 표기 통일 (Tariffs → Tariff). 쓰기·읽기 양쪽에서 적용
├── review_sample.py    # ④ 수동 검증용 표본 50개 → output/review_sample.md
├── collect_prices.py   # yfinance 일봉 → daily_bars (첫 실행 2y 백필)
├── calendar_macro.py   # FOMC(정적) + FRED 릴리스(CPI·NFP·GDP·PCE) + 관찰 종목 실적일
├── gemini_client.py    # 다중 키 라운드로빈 · 429 쿨다운 · 503 백오프
├── classify_posts.py   # 배치 Gemini 분류 → ai_* 컬럼 (항목별 검증)
├── mapping_rules.json  # 섹터 → ETF → 상위 10종목 정적 규칙
├── mapping.py          # 규칙 적용 (첫 일치 하나)
├── cluster_events.py   # event_id · 방향/강도 재계산 · 세션 · 기준일 · confounded_daily
├── event_study.py      # 일봉 OHLCV로 구간 7개(즉각·당일·익일·+3D·+5D·변동폭·거래량 배수) · SPY 대비 초과 반응 · 플라시보 풀
├── aggregate.py        # 창별 트렌드 · Trend Score · 반응 통계 + 플라시보 검정 → output/trump_analysis.json
├── narrate.py          # (선택) Gemini 서술 → output/narrative.json
├── render_report.py    # → output/trump_report.md (그림자 모드 점검용)
├── render_html.py      # → output/trump_report_body.html (Blogger 본문) + trump_report.html (미리보기)
├── report_title.py     # 글 제목 규칙 "트럼프 발언 트렌드 — YYYY년 M월 D일" · 라벨
├── publish.py          # Blogger 게시 (daily-report의 publish_blogger 재사용, 같은 제목 있으면 건너뜀)
├── prompts/classify.txt · prompts/narrate.txt
├── data/               # trump.db + raw/posts/*.jsonl  (gitignore)
└── output/             # 산출물 (gitignore)
```

## 실행

리포 루트의 `.env`에서 `GEMINI_API_KEY`(여러 키는 `;` 구분)와 `FRED_API_KEY`를 읽는다.

```powershell
pip install -r experiments/trump-trend/requirements.txt

# 전체 (분류는 한 번에 최대 40배치 = 600건. 남은 건 다음 실행이 이어받는다)
python experiments/trump-trend/main.py

# Gemini 없이 — 수집·가격·집계·렌더만
python experiments/trump-trend/main.py --skip-classify

# 분류만 조금 (3배치 = 45건)
python experiments/trump-trend/main.py --skip-collect --skip-prices --skip-calendar --max-batches 3

# Gemini 서술까지
python experiments/trump-trend/main.py --narrate

# 사전 필터 규칙을 바꾼 뒤 — 전체 행 noise_reason 재계산 (분류 결과는 유지)
python experiments/trump-trend/main.py --refilter --skip-classify

# ④ 수동 검증 표본
python experiments/trump-trend/review_sample.py
```

첫 실행은 archive 전체(약 3만 6천 건, 2022년~)를 DB에 넣고 일봉 2년치를 받는다. 이후 실행은 새 게시물만 추가한다.

## 게시 — 별도 글 시리즈

리포트는 데일리 브리핑에 끼우지 않고 **별도 글**로 나간다 (기획서 13절 ⑦ 결정, 2026-09-16).

| 항목 | 값 |
| --- | --- |
| 제목 | `트럼프 발언 트렌드 — 2026년 9월 16일` (같은 날짜면 같은 문자열 → 중복 게시 방지 기준) |
| 라벨 | 트럼프 트렌드 · 미국 증시 · 자동 리포트 |
| 본문 | `render_html.py`가 만든 `trump_report_body.html`. 오늘 한 줄 → 오늘의 발언 → 급상승 주제 → 무엇이 달라졌나 → 30일 흐름 → 과거 시장 반응 → 왜 이 종목인가 → 내일 볼 것 → 출처·면책 |
| 게시 모듈 | `publish.py` — `experiments/daily-report/publish_blogger.py`의 OAuth 경로 재사용. Blogger 시크릿 3개 동일 |

**기본은 dry-run이다.** 로컬 `main.py`도, Actions 스케줄도 `--publish`가 없으면 본문만 만들고 올리지 않는다.

- 로컬 실제 게시: `python experiments/trump-trend/main.py --publish`
- **Actions 스케줄 게시 켜기: 저장소 변수 `TRUMP_PUBLISH` = `true`** (Settings → Secrets and variables → Actions → Variables). 코드 변경 없이 그림자 모드 종료
- Actions 수동 실행: `publish` 입력을 켠 그 실행만 게시

미리보기는 `output/trump_report.html`을 브라우저로 연다. 같은 파일이 `trump-state` 브랜치에도 매일 저장된다.

## 자동 실행 — GitHub Actions

[`.github/workflows/trump-trend.yml`](../../.github/workflows/trump-trend.yml)이 **매일 22:30 UTC(07:30 KST)** 에 돈다. 주말 포함.
시크릿은 기존 `GEMINI_API_KEY`·`FRED_API_KEY`를 그대로 쓴다. `workflow_dispatch`로 수동 실행도 된다.

런너는 매번 빈 환경이므로 상태를 브랜치에 남긴다. 게시물은 archive에서, 캘린더는 API에서, 이벤트·반응은 재계산으로
매번 복원된다. Gemini 분류 결과(`classifications.jsonl`)는 다시 만들 수 없어 저장하고, 일봉(`daily_bars.csv`)은 다시 받을 수
있지만 yfinance가 깨지는 날에도 리포트가 나오도록 저장한다 — 덕분에 매 실행 2년치 대신 최근 한 달만 받는다.

```
trump-state (2026-09-18부터 매일 이전 커밋 위에 커밋 — git log 로 특정 날의 리포트·분류 결과를 되찾을 수 있다)
└── experiments/trump-trend/output/state/
    ├── classifications.jsonl   # id + ai_* 컬럼. 다시 만들 수 없는 상태
    ├── daily_bars.csv          # 일봉 OHLCV 전체 (약 5,500행). 있으면 1개월 갱신, 없으면 2년치 백필
    ├── trump_report.md         # 그날 리포트 — GitHub에서 바로 읽는다
    ├── trump_report.html · trump_analysis.json · narrative.json · title.txt
```

실행 순서: 상태 브랜치 fetch → `main.py --import-state … --export-state … --import-bars … --export-bars … --narrate`
→ 상태+리포트를 브랜치에 커밋·push → 아티팩트 업로드. 저장 단계는 작업 트리를 checkout 하지 않고 임시 인덱스 + `commit-tree`로
커밋을 만든다 (checkout 하면 방금 만든 `output/state`가 옛 버전으로 덮어써진다). 트리가 전날과 같으면 커밋하지 않는다.
push는 `--force` 없음 — 원격이 앞서 있으면 거부된다.
분류 결과는 분류 직후 바로 내보내므로 뒤 단계가 실패해도 Gemini 호출은 낭비되지 않는다.
첫 실행부터 90일 백필이 시작되며 하루 40배치씩 3일에 걸쳐 끝난다.

로컬 실행과 배타적이지 않다. 로컬 DB에서 내보낸 파일을 상태 브랜치에 넣으면 이미 끝난 백필을 그대로 이어받는다:

```powershell
python experiments/trump-trend/main.py --skip-classify --export-state experiments/trump-trend/output/state/classifications.jsonl
```

## 설계 핵심

- **숫자는 파이썬, 문장은 Gemini.** Gemini는 게시물에 라벨을 붙이는 입력과 집계 JSON을 문장으로 옮기는 출력, 두 자리만 맡는다.
  시장 영향(`market_impact`)은 AI가 판단하지 않고 가격으로 계산한다.
- **게시물 1개 ≠ 이벤트 1개.** 같은 topic+subtopic+target이 60분 이내면 하나의 `event_id`. 방향은 intensity 가중 다수결, 강도는 최대값.
  반응 통계는 전부 이벤트 단위.
- **노이즈는 버리지 않고 표시.** `noise_reason`(사전 필터)과 `ai_market_relevance` 0–3(Gemini)으로 용도별 임계값을 다르게 쓴다.
  게시량 통계는 전체, 트렌드는 relevance ≥ 1, 이벤트는 ≥ 2.
- **초과 반응.** `abn = 자산 수익률 − SPY 수익률`. 구간은 전부 일봉 OHLCV (분봉은 쓰지 않는다 — 2026-09-18 결정):
  `immediate`(장외 게시물은 다음 개장 갭 `ret_gap`, 정규장 게시물은 시가→종가 `ret_intraday`) · `close` · `next_close` · `d3` · `d5`.
  방향 무관 지표로 `rel_range`·`rel_volume`(측정일 (고−저)/종가 · 거래량 ÷ 직전 20거래일, 1.0 = 보통)을 함께 낸다.
- **플라시보 검정.** publishable 통계마다 같은 자산의 비이벤트 날(이벤트 측정일·거시 발표일 제외)에서 N개를 1,000회 뽑아
  평균 분포를 만들고, 관측 평균이 그보다 극단적인 비율을 양측 p로 낸다. p ≥ 0.10이면 `indistinguishable` — 리포트는 `~`/회색으로
  표시하고 서술은 그 수치를 관찰 대상의 근거로 들지 않는다. 시드가 문자열이라 실행마다 같은 값이다.
- **confounded 플래그.** `confounded_daily`는 반응 측정일에 FOMC·CPI·NFP·GDP·PCE·관찰 종목 실적이 있으면 true.
  통계는 clean 이벤트만, N < 20이면 표를 내지 않는다. (분 단위 플래그 `confounded_intraday`는 분봉과 함께 제거했다.)
- **같은 날은 관측 하나.** 일 단위 구간에서 같은 주제의 이벤트가 같은 거래일에 여럿이면 수익률이 같으므로
  (주제, 기준일, 측정일)로 합쳐 N을 센다. 리포트의 "같은 날 합침" 수가 그 개수다.
- **Trend Score는 가중합.** 빈도 0.35 · 강도 0.30 · 최근성 0.25 · 신규성 0.10, 성분은 순위 백분위 0–100. 곱셈 아님.
- **비교 구간은 같은 길이끼리.** 3D/3D · 7D/7D · 30D/30D · 90D/90D. 직전 구간 데이터가 없으면 수준값만.

## 기획서와 다른 점 · 알아둘 것

| 항목 | 상태 |
| --- | --- |
| 원본 스냅샷 | Parquet 대신 **JSONL** (`data/raw/posts/YYYY-MM-DD.jsonl`). pyarrow 의존을 피했다. 내용은 같다 |
| 분봉 | **쓰지 않는다 (2026-09-18 결정).** 대신 일봉 OHLCV로 갭·장중·+3D·+5D·변동폭·거래량 배수를 잰다. 옛 `ret_5m/15m/60m`·`confounded_intraday` 컬럼은 스키마에서 제거, 옛 DB는 첫 연결 때 두 테이블을 자동 재생성 |
| 실적 발표일 | yfinance `earnings_dates`. 관찰 종목(NVDA·TSLA·AAPL)만. 신뢰도는 보통 |
| FOMC 일정 | `config.FOMC_DECISION_DATES` 정적 목록 (2025–2026). **연도가 바뀌면 갱신** |
| FRED 키 없을 때 | FOMC만 반영 → `confounded_daily` 과소 판정. 로그에 경고 |
| Gemini 무료 한도 | 배치 15건 × 최대 40배치/실행. 503(수요 폭주)은 지수 백오프, 429는 키별 60초 쿨다운. 한도 숫자는 코드에 박지 않았다 |
| 분류 대상 범위 | 최근 90일, 최신 글부터. 첫 실행 기준 약 1,300건 → 3~4회 실행으로 백필 완료 |
| 이벤트·반응 테이블 | 매 실행 **전부 재생성**. 규칙이 결정적이라 같은 입력 → 같은 event_id |
| 검증 실패 항목 | `analyzed_at` NULL로 남아 다음 실행이 재시도 |

## 산출물 읽는 법

`output/trump_report.md`의 **데이터 상태** 절을 먼저 본다. "최근 24시간 미분류 N건" 경고가 있으면
오늘의 발언·이벤트가 불완전하다 — 분류를 한 번 더 돌린다. **과거 반응 이력**은 clean N ≥ 20인 주제만 표가 나온다.
그 전까지는 "표본이 쌓이는 중"으로 표시된다. 90일 백필이 끝나면 Trade/Fed 같은 큰 주제부터 표가 생긴다.
표의 `p` 열이 `~`(MD) 또는 회색(HTML)이면 그 평균은 발언 없는 날과 구분되지 않는다는 뜻이다 — 값이 커 보여도 근거로 쓰지 않는다.

## 검증 기록

| 날짜 | 내용 | 결과 |
| --- | --- | --- |
| 2026-09-15 | 90일 백필 (3회 실행, 85배치) | 1,295건 분류 · 검증 탈락 0 · 실패 0 · 이벤트 206개 |
| 2026-09-15 | ④ 50개 수동 검증 (`output/review_sample.md`) | 사전 필터 17/17 · Gemini 분류 30/33 · **전체 94%**. 불일치 3건은 전부 relevance/intensity가 한 단계 높은 쪽. 놓친 글 없음 |
| 2026-09-15 | 서술(`--narrate`) 시험 | 금지 표현 검증 통과. 통계 인용 시 N 병기 확인 |

검증에서 나온 조정: `Tariffs`/`Tariff` 분리 집계 → `labels.py` 정규화 추가 · 자기 재게시(`RT @realDonaldTrump…`) 원문과 이중 계산 → `self_repost` 필터 추가 ·
같은 주제 이벤트가 같은 거래일에 여럿일 때 N 과대 → 관측일 단위로 합침.

## 다음 단계 (기획서 13절)

- ④ (완료) 추가 표본은 `review_sample.py --seed N` 으로 다른 50개를 뽑아 반복. Company 주제 relevance 과대 경향은 프롬프트 보강 후보
- ⑤ Trend Score 순위가 직관과 맞는지 보고 가중치·클러스터 간격 조정. 현재 7D 이벤트가 주제당 1~2개라 2주 더 쌓인 뒤 판단
- ⑥ (2026-09-18 마감) 분봉은 하지 않는다. 일봉 구간 확장(즉각·+3D·+5D·배수)과 플라시보 검정으로 대신했다. 남은 후보: 주제별 거시 자산(USD/CNH·원유·10년물·금·VIX) 추가
- ⑦ (구현 완료 · 게시 대기) 별도 글로 결정. HTML 렌더·게시 경로·Actions 게이트까지 있다. 그림자 모드 2주 뒤 저장소 변수 `TRUMP_PUBLISH=true`로 켠다
