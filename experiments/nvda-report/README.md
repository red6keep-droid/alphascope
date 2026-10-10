# 엔비디아 데일리 리포트 — 코드

기획서: [`doc/엔비디아-리포트-기획.md`](../../doc/엔비디아-리포트-기획.md) · 이벤트 정의: [`doc/엔비디아-리포트-이벤트-정의.md`](../../doc/엔비디아-리포트-이벤트-정의.md)

NVDA 한 종목의 **사실 추적** 리포트다. 매수·매도 신호를 만들지 않는다. 숫자는 파이썬이 계산하고 Gemini는 문서 분류와 (⑤단계부터) 문장만 맡는다.

## 상태

- **①단계 뼈대 완료 (2026-10-08).** Gemini 없이 수집 → 판정 → MD. 연속 실행 멱등.
- **②단계 문서 수집·분류 구현 완료 (2026-10-08).** 뉴스룸·블로그·CNBC·Google News·연방관보·CourtListener → 중복 제거 → Gemini 분류 → 보정 규칙.
  30일치 111건 분류, 검증 탈락 0, 이벤트 24건. **50건 수동 검증 48/50 = 96% (2026-10-10, 1차 Claude·최종 사용자)** — ng 2건(NVIDIA 자체 소비자 제품 가격 변경 → rel 2~3·new, 고객사 제품 출시 → rel 2)은 프롬프트 예시로 반영. rel 1의 novelty는 채점하지 않기로 함. `review_sample.py`에 Gemini가 본 `입력 요약` 열 추가.
- **③ 소송 부분 완료 (2026-10-10):** `cases_survey.py`(검토 표) → `cases_init.py`(`cases` 12행, watch 2 = 증권만) → `cases_watch.py`(매일: watch=1 도켓의 일정 명령문에서 심리·재판 날짜만 `calendar(COURT)`로, 판결·합의·기각 명령만 `items(court)` 이벤트). 사용자 지시: **단순하게 — 주가에 닿을 판결이 잡혀 있을 때만 미리 경고.** 법원 일정은 30일 창(`COURT_LOOKAHEAD_DAYS`). 남은 것: 트럼프 브리지 · 법적 기사 모니터링 강화.
- ④(점검표 추출) · ⑤(서술·HTML·Actions) · ⑥(30일 그림자)는 아직이다.

```
experiments/nvda-report/
├── main.py              # 실행 (일봉 → 캘린더 → 상태판 → EDGAR → 문서 → 중복 제거·분류 → 판정 → MD)
├── config.py            # 확정값·임계값 전부 (6절 임계값은 초안)
├── db.py                # SQLite 스키마 — items · daily_state · option_snapshots · calendar · cases · quarterly · monthly · filings_text · daily_bars · meta
├── indicators.py        # 기술 지표(RSI·이평·52주·거래량 배수) · 옵션 수식(BS 감마·GEX 근사·IV 보간)
├── collect_market.py    # yfinance — 일봉 5심볼 · 옵션 체인 스냅샷 · 추정치 · 애널리스트(items analyst) · 기관/공매도
├── collect_edgar.py     # SEC EDGAR — Form 4(XML 파싱, 10b5-1) · 8-K(Item) · 10-Q/10-K(URL) → items
├── collect_calendar.py  # FOMC(정적) · FRED(CPI·NFP·GDP·PCE) · 실적 12종목 · OPEX/INDEX(셋째 금요일) · static/events.json
├── collect_feeds.py     # RSS — 뉴스룸(releases.xml, 도메인으로 보도자료/블로그 분리) · 블로그 · CNBC 2종 · Google News q=Nvidia 7일
├── collect_regulatory.py# Federal Register(용어 3개, 브라우저 UA) · CourtListener(party:"NVIDIA" 도켓, 100초+)
├── dedupe.py            # 키워드 1차 필터(news만) · 제목 토큰 자카드 ≥ 0.6 중복 표시 (공식 소스가 대표)
├── classify_items.py    # Gemini 배치 분류(20건, 오래된 것부터) → ai_* · is_event. 검증 탈락 2회면 classify_failed
├── labels.py            # 결정적 보정 — 해설 매체·주가 기사 relevance 상한 1·repeat / 같은 사건 병합(사실 2-gram 자카드 ≥ 0.30)
├── gemini_client.py     # trump-trend 복사본 + "Extra data" 파싱 보강
├── review_sample.py     # 수동 검증 표본 50건 → output/review_sample.md
├── cases_survey.py      # ③ CourtListener suitNature 쿼리(증권·반독점·특허 1년) → output/cases_survey.md/.json 검토 표
├── cases_init.py        # ③ 검토 표 + MANUAL 덮어쓰기 → cases 테이블 (watch=1은 증권만)
├── cases_watch.py       # ③ watch=1 도켓 → 심리·재판 일정(calendar COURT, 30일 경고) · 판결·합의·기각 명령(items court 이벤트). Gemini 없음
├── judge.py             # 이벤트 판정 · 상태판 · 다가오는 것 · 점검표 · 기사 수 → output/nvda_analysis.json
├── render_report.py     # → output/nvda_report.md · title.txt
├── prompts/classify.txt # 영역 enum · 관련성 기준표 · 신규성 규칙 · 1차 행위 규칙
├── static/events.json   # GTC · Computex · CES (연 1회 수동 갱신, 추정일은 confirmed=false)
├── data/nvda.db         # gitignore
└── output/              # gitignore
```

## 실행

리포 루트의 `.env`에서 `FRED_API_KEY` · `GEMINI_API_KEY`(여러 키는 `;`) · `COURTLISTENER_TOKEN`을 읽는다.

```powershell
pip install -r experiments/nvda-report/requirements.txt

python experiments/nvda-report/main.py                  # 전체 (첫 실행 약 3분: 일봉 2y · EDGAR 90일 · 문서 30일 분류 6배치 · CourtListener 100초)
python experiments/nvda-report/main.py --skip-classify  # Gemini 없이 (수집·중복 제거·판정·렌더)
python experiments/nvda-report/main.py --skip-courts    # CourtListener 없이 (느리다)
python experiments/nvda-report/main.py --skip-options   # 옵션 체인 없이
python experiments/nvda-report/main.py --day 2026-10-06 # 특정 거래일 기준 판정·렌더
python experiments/nvda-report/review_sample.py         # 수동 검증 표본
python experiments/nvda-report/labels.py --verbose      # 보정·병합 결과 보기
```

결과: `output/nvda_report.md` (점검용 MD) · `output/nvda_analysis.json` (렌더·서술의 유일한 입력) · `output/review_sample.md`.

## 설계에서 못 박은 것

### ①단계 (2026-10-08)

| 항목 | 결정 | 이유 |
| --- | --- | --- |
| 거시 캘린더 테이블 | trump-trend의 `macro_calendar`를 따로 두지 않고 `calendar` 한 테이블에 kind로 섞는다 | "다가오는 것"을 한 쿼리로 읽는다 |
| trump-trend 코드 재사용 | import 공유가 아니라 **복사·개조** (`collect_prices` → `collect_market.collect_bars`, `calendar_macro` → `collect_calendar`, `gemini_client` 복사) | 양쪽 다 `config`·`db` 모듈명을 써서 sys.path 공유가 충돌한다 |
| 기준 거래일 | NVDA 마지막 일봉 날짜. 제목 날짜는 실행일(KST) | KST 아침에 전날 뉴욕 장을 본다 |
| 공시·문서의 "오늘 바뀐 것" 범위 | `reported_on IS NULL`인 항목 중 **지난 리포트 날짜(meta `last_report_day`) 이후** 발행분. 첫 실행은 3일. 그보다 오래된 백필분은 `reported_on='backfill'` | 백필이 첫 리포트에 한꺼번에 뜨지 않게. 재실행은 `reported_on = day`로 멱등 |
| 상태값 조건의 발화 | IV 랭크 극단·30일 상향/하향 쏠림은 **들어간 날만** 이벤트 | 매일 같은 줄이 반복되는 것을 막는다 |
| Form 4 꼬리표 | 공개시장 매도·매수(S·P)에만 `[10b5-1 계획]`/`[계획 외]`. 세금 납부(F)·부여(A)·증여(G)는 거래 종류만 | 비매매 거래에 "계획 외"가 붙으면 오해 |
| Form 4 강조 | 계획 외 매도 · 매수 · 10% 보유자 | 기획 6절 |
| 옵션 만기 선택 | 가까운 4개 + 30일을 감싸는 둘 + 실적이 45일 안이면 실적 직후 만기 | 주간 만기만으로는 30일 IV를 보간할 수 없다 |
| 옵션 스냅샷 범위 | 현재가 ±30% 행사가만 저장, P/C 비율은 전체 체인으로 | 90일 보관 용량 |
| EPS 7일 변화 | yfinance `eps_trend`의 `7daysAgo` 열 | 이력 불필요. 매출 7일 변화는 우리 스냅샷(7일 뒤부터) |
| 선행 PER | 종가 ÷ yfinance `forwardEps`(12개월 선행) | "다음 4분기 합"은 yfinance가 2분기까지만 준다 |
| 실적일 | 미래 실적일은 매 실행 지우고 다시 넣는다. NVDA는 `Ticker.calendar` 우선 | 추정일 변경 대응. 미래 실적일은 `confirmed=0`("추정") |

### ②단계 (2026-10-08)

| 항목 | 결정 | 이유 |
| --- | --- | --- |
| 뉴스룸 피드 | `releases.xml` 하나만 쓰고 **링크 도메인으로 보도자료(newsroom)/블로그(blog)를 가른다.** 카테고리 피드(`cats/*.xml`)는 2021년에 멈춰 안 쓴다 | "All News" 피드가 둘을 섞어 준다 (20건 중 보도자료 2) |
| Reuters | 공식 RSS 대신 **Google News RSS `q=Nvidia when:7d`** (100건, 매체명은 `<source>`) | Reuters 피드 가용성 미확인. Google News가 로이터·FT·블룸버그를 다 덮는다 |
| 외부 기사 본문 | 저장하지 않는다. 제목·요약·링크만. Google News는 설명도 비운다(제목 반복) | 기획 원칙 |
| 연방관보 1차 필터 | SEC 자율규제 공지 제외 + **허용 기관(BIS·상무부·ITC·USTR·FTC·DOJ·OSTP·재무부) 또는 제목 키워드(semiconductor·export·China·tariff…)일 때만** 분류 | "Nvidia" 전문 검색이 HFC 배분·약가 모델까지 끌어온다 (21건 중 11건 무관) |
| CourtListener | `type=d` 도켓 검색, `filed_after` = 지난 확인일, 타임아웃 180초, 429·타임아웃이면 그 실행은 건너뜀 | 검색 한 번에 100초 (2026-10-08). 도켓별 신규 문서 추적은 ③ |
| 분류 순서 | **오래된 것부터** | 최신부터 하면 원보도가 나중 기사의 "repeat"로 밀린다 (확인됨) |
| 신규성 두 겹 | Gemini `recent_facts`(저장된 7일치) + 프롬프트의 같은 배치 규칙 + **`labels.dedupe_facts`**(같은 영역·±2일 이벤트의 사실 문장 글자 2-gram 자카드 ≥ 0.30 → repeat) | 같은 배치의 형제 기사는 Gemini가 서로 모른다 — 밀수 체포 5건이 전부 "new"였다 |
| 해설·주가 기사 상한 | `labels.adjust` — Motley Fool·TIKR·Seeking Alpha 등 매체, "Why/What/Prediction/Should you…" 제목, 신고가·시총·CEO 자산 제목(행위 단어 없을 때) → relevance ≤ 1 · repeat. Yahoo Finance는 전재가 많아 제외 | 첫 분류에서 논평이 relevance 2~3·new로 올라와 ②가 18건이었다 → 11건 |
| Form 4·8-K·애널리스트 | Gemini를 거치지 않는다 (수집 시 `analyzed_at` 채움) | 구조화 공시 |
| 기사 수 지표 | 기준일 기사 수(repeat·중복 포함, 키워드 탈락 제외) ÷ 직전 7일 하루 평균 ≥ 2 **and** ≥ 5건 → 이벤트 | #48 헤드라인 톤 |

### ③단계 (2026-10-10)

| 항목 | 결정 | 이유 |
| --- | --- | --- |
| 추적 범위 | `cases_survey.py`가 suitNature 쿼리 3개(증권·반독점 전부, 특허 1년)로 433건 중 59건만 받는다. 저장은 미종결 12건, **watch=1은 증권 2건** | 사용자: 특허 NPE 소송 10건이 ⑤에 늘 떠 있는 것은 원치 않음. 반독점은 전부 종결(최근 2008) |
| CL 종결일 수동 덮어쓰기 | `cases_init.MANUAL` — 4:18-cv-07669는 CL이 2021 종결로 두지만 2023 파기환송·2024-12 대법원 각하 후 진행 중(도켓 문서 2026-10-08까지 확인) | CL의 dateTerminated는 항소 전 기준일 수 있다 |
| 도켓 문서 처리 | **분류하지 않는다.** 일정 명령문의 `… set for M/D/YYYY` 중 심리·재판·약식판결·기각 신청·집단소송 인증만 캘린더로, 명령문 머리가 ORDER/JUDGMENT이고 결정 어구가 있을 때만 이벤트. Gemini 호출 0 | 사용자: "리포트를 복잡하게 만들지 마라. 주가에 영향 줄 판결이 예정될 때만 미리 경고" |
| 경고 창 | 법원 일정만 30일, 나머지 캘린더는 7일 | 판결은 포지션을 미리 생각할 시간이 필요 |
| ⑤ 섹션 | 사건명·상태·다음 일정 세 칸. 판결은 ②로 간다 | 단순화 |
| 수정 일정 명령 | 그 사건의 미래 COURT 행을 지우고 최신 명령 기준으로 다시 넣는다 | 2026-05-04 수정 일정이 4월 일정을 대체한 사례 |
| 첫 실행 판결 소급 | 3일(`COURT_RULING_BACKFILL_DAYS`) | 2026-03-25 집단소송 인증 명령 같은 과거 판결이 첫 리포트에 뜨지 않게 |

## 소스 확인 (실제 호출)

| 소스 | 결과 |
| --- | --- |
| yfinance 일봉·옵션 체인·추정치·eps_trend·애널리스트·기관·공매도·실적일 | 전부 응답. 옵션 체인 만기 6개 210행 |
| SEC EDGAR submissions · Form 4 XML · 8-K index | 응답. Form 4에 `aff10b5One` 플래그 |
| FRED release dates | 응답 |
| NVIDIA `releases.xml` · 블로그 `feed/` · CNBC Top/Tech · Google News RSS | 응답. 첫 수집 172건 |
| Federal Register API | **기본 UA는 Cloudflare 403**, 브라우저 UA로 200 |
| CourtListener `search/?type=d` | 익명 호출 **약 100초**, 토큰 있으면 **1~2초** (2026-10-10). 30일 신규 도켓 1건 (특허) |
| CourtListener `docket-entries/?docket=` | 토큰으로 1초. 4:18-cv-07669 문서 366건, 일정 명령문(#296)에 `Motion Hearing set for 5/20/2027`·`Trial set for 8/17/2027`. Hu 사건(53건)은 최근 문서 설명이 비어 있음(RECAP 미수집) |
| TSMC IR 월매출 | 브라우저 UA로도 403 — ④단계에서 뉴스 RSS 대체 |

## 알아둘 함정

- **옵션 체인은 미국 장 마감 후 ~ 미국 자정(≈ 20:00–04:00 UTC) 사이에 받아야 한다.** 그 밖의 시각에 Yahoo는 호가 0·OI 0·IV≈0으로 리셋된 체인을 준다 (2026-10-08 04:34 UTC에 확인 — ATM IV 0.4%, P/C 31). `collect_options`의 품질 게이트가 그런 체인을 버리고 미수집으로 두지만, 그날 스냅샷은 비게 된다. Actions 22:45 UTC는 창 안이다. 로컬 점검은 `--skip-options`로.
- IV 랭크(60일)·선행 PER 1년 분위는 스냅샷이 쌓여야 켜진다. **매일 돌려야 쌓인다.**
- `upgrades_downgrades`는 첫 실행에 최근 14일만. 그 뒤는 meta `analyst_last_seen` 이후만.
- EDGAR `User-Agent`는 `config.EDGAR_USER_AGENT`(환경변수로 덮어쓸 수 있음). 없으면 403.
- `daily_state`의 가격·기술 칸은 매 실행 전 기간을 다시 계산한다. 옵션·추정치 칸은 수집한 날만 있다.
- 분류 결과를 지우고 다시 돌리면(`analyzed_at=NULL`) 신규성이 달라진다 — `recent_facts`에 남은 형제 기사의 사실 때문에 원보도가 "repeat"가 될 수 있다. 과거 행은 지우지 말고, 규칙 변경은 `labels.py`(멱등)로.
- `labels.adjust`는 Gemini 값을 **깎기만** 한다. 올리는 규칙은 두지 않는다.
- Google News 링크는 리다이렉트 URL이다. 원문 주소가 필요하면 ⑤단계에서 풀어야 한다.
- 이벤트 임계값은 전부 초안이다. ⑥단계에서 "오늘 바뀐 것" 하루 1~3건이 되도록 `config`만 바꾼다.
