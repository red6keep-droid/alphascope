# 인물 발언 레이더 (people-radar)

기획: [doc/인물-발언-레이더-기획.md](../../doc/인물-발언-레이더-기획.md). 트럼프 트렌드(`experiments/trump-trend`)를 여러 인물로 넓힌 파이프라인.
트럼프 리포트는 5단계에서 이 글로 대체할 때까지 그대로 돈다.

## 지금 있는 것 (2단계, 2026-10-19)

```
python collect.py            # 13명 × 1차 · 2차 소스 → data/people.db (약 25초, LLM 없음)
python collect.py burry fed  # 일부 인물만
```

| 수집기 | 인물 | 소스 | attribution |
|---|---|---|---|
| `cnn_archive` | 트럼프 | Truth Social (CNN 공개 아카이브, 20MB 통째로 받고 최근 72시간만) | self |
| `rss` | 트럼프 · 그리어 · 버리 | 백악관 presidential-actions · briefings-statements / USTR / 버리 Substack | office · office · self |
| `fed_speeches` · `fed_press` | 연준 | 연설 RSS(제목 쉼표 앞 = 연설자 → `sub_speaker`) · 보도자료 중 Monetary Policy 만 | self · office |
| `treasury_html` | 베센트 | 재무부 보도자료 목록 HTML (RSS 없음). 제목에 Bessent · Secretary 가 있으면 self | office / self |
| `ark_trades` | 우드 | arkfunds.io 매매 API (ARK 6개 펀드, 하루 = 한 행) | trade |
| `google_news` | 13명 전원 | 인물별 검색어, 최근 2일 · 제목 · 매체 · 링크만 | report (2차) |

- 인물 · 소스 · 검색어는 `config.PEOPLE` 한 곳. `start=True` 6명이 4단계 첫 인물, 나머지는 2차 전용(6단계)이지만 수집은 지금부터 한다.
- 같은 (인물, 링크)는 한 번만. 피드의 고정 글(USTR 2009년 글)은 수집 창(72시간)으로 걸러진다.
- 재무부 HTML 구조가 바뀌면 0건 → 실패로 기록된다.

## 첫 실행 (2026-10-19 일요일, Mac)

1차: 트럼프 45 · 백악관 1 · USTR 2 · 버리 1 · ARK 1 (재무부 · 연준은 주말이라 창 안 0).
2차: 트럼프 · 베센트 · 머스크 100(상한) · 올트먼 60 · 젠슨 황 53 · 연준(워시) 48 · 버리 · 우드 26 … 애크먼 4 · 티미라오스 2.
2차 제목 중 발언 형태(says · said · 따옴표 · 콜론)는 약 절반 — 나머지(해설 · 기사 모음 · 무관)는 3단계 인용 추출이 버린다.

## 3 · 4 · 5단계 (2026-10-19, 코드)

```
python main.py                       # 수집 → 인용 추출 → 분류 → 집계 → 서술 → 렌더 → 게시(dry-run)
python main.py --state output/state  # CI: statements.jsonl 불러오기 · 내보내기 (30일)
python main.py --publish             # 실제 게시 — 사용자 확인 뒤에만
```

| 모듈 | 하는 일 | LLM |
|---|---|---|
| `extract.py` | 2차 제목 → ① 이름 · 말한 형태 없는 것 버림 ② 같은 발언 묶기(인물 · 48시간 · 자카드 0.45) ③ 묶음 대표만: 직접 발언인가 · 한 문장 인용 · 같은 1차 항목 | `json-backup-first` 30묶음/호출 |
| `classify.py` | 1차 전부 + 2차 발언(1차와 안 겹친 것) → trump-trend 와 같은 8칸. 인물군별 프롬프트(policy · investor/commentator · ceo). 트럼프 Truth Social 은 trump-state 라벨 그대로 | `json-backup-first` 20건/호출 |
| `aggregate.py` | 24시간 · 관련도 ≥ 2 → 인물 × 주제 신호, 인물 순서, 7일 추이 변화, 데일리 시장 맥락 → `output/radar.json` | 없음 |
| `narrate.py` | 신호마다 한국어 헤드라인(명사형 48자) + 설명 한 문장(합니다체), 숫자 검사(fact_check) · 예측 말 금지 | `json-backup-first` 1회 |
| `render_html.py` | 탭 오늘(요약 · 머리 카드 · 인물별 발언 · 시장 맥락) / 추이 | 없음 |
| `publish.py` | 신호 0개면 게시 없음, 같은 날 글은 갱신 | — |
| `state_io.py` | statements 30일 JSONL | — |

`json-backup-first` = DeepSeek → Groq Qwen → Groq gpt-oss → Gemini lite (새 기능은 예비 먼저, llm_chain 머리말 10-19).
