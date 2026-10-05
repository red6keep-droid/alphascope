# MRH (Momentum Rotation Hunter)

# Database Schema Specification V1

# 데이터베이스 구조 명세서

---

# 제1장. DB 설계 철학

## 1.1 핵심 철학

MRH DB의 목적은:

> **복잡한 퀀트 데이터 웨어하우스가 아니라

매일 발생하는
signal · ranking · portfolio · log

를 안정적으로 기록하는 것**

이다.

---

# 1.2 MVP 원칙

MVP에서는:

* 단순성 우선
* 유지보수 최소화
* 빠른 구현
* 운영 안정성

을 우선한다.

---

# 1.3 DB 구조 방향

초기 MVP 구조:

| 항목 | 선택 |
| :--- | :--- |
| DB | PostgreSQL |
| 플랫폼 | Supabase |
| ORM | Prisma |
| 저장 전략 | Daily Snapshot |
| 실시간 데이터 | 사용 안함 |

---

# 제2장. 전체 테이블 구조

## 2.1 핵심 테이블

| 테이블 | 목적 |
| :--- | :--- |
| tickers | 종목 정보 |
| daily_market_data | 일봉 데이터 |
| candidate_signals | 매수 후보 |
| portfolio_positions | 보유 상태 |
| trade_logs | 매매 기록 |
| batch_logs | 배치 상태 |
| notification_logs | 알림 기록 |
| system_logs | 운영 로그 |

---

# 제3장. tickers 테이블

## 3.1 목적

종목 기본 정보 저장.

---

## 3.2 컬럼 구조

| 컬럼 | 타입 | 설명 |
| :--- | :--- | :--- |
| id | uuid | PK |
| ticker | text | 종목 코드 |
| company_name | text | 회사명 |
| sector | text | 섹터 |
| industry | text | 산업 |
| market_cap | bigint | 시가총액 |
| is_active | boolean | 활성 여부 |
| created_at | timestamp | 생성일 |

---

# 제4장. daily_market_data 테이블

## 4.1 목적

일별 시장 데이터 저장.

---

## 4.2 컬럼 구조

| 컬럼 | 타입 | 설명 |
| :--- | :--- | :--- |
| id | uuid | PK |
| ticker | text | 종목 |
| trade_date | date | 거래일 |
| open | numeric | 시가 |
| high | numeric | 고가 |
| low | numeric | 저가 |
| close | numeric | 종가 |
| volume | bigint | 거래량 |
| daily_change_pct | numeric | 하루 상승률 |
| rvol | numeric | 상대 거래량 |
| gap_pct | numeric | 갭 비율 |
| created_at | timestamp | 저장 시간 |

---

# 제5장. candidate_signals 테이블

## 5.1 목적

매수 후보 저장.

---

## 5.2 핵심 역할

MRH 핵심 테이블.

매일 생성되는:

* continuation 후보
* ranking
* score

를 저장한다.

---

## 5.3 컬럼 구조

| 컬럼 | 타입 | 설명 |
| :--- | :--- | :--- |
| id | uuid | PK |
| ticker | text | 종목 |
| trade_date | date | 생성일 |
| continuation_score | numeric | 핵심 점수 |
| daily_momentum_score | numeric | 모멘텀 |
| rvol_score | numeric | 거래량 점수 |
| sector_score | numeric | 섹터 점수 |
| close_strength_score | numeric | 종가 강도 |
| exhaustion_risk | numeric | 과열 위험 |
| ranking | integer | 순위 |
| signal_type | text | BUY/SELL |
| signal_reason | text | 신호 이유 |
| created_at | timestamp | 생성 시간 |

---

# 제6장. portfolio_positions 테이블

## 6.1 목적

현재 보유 상태 추적.

---

## 6.2 컬럼 구조

| 컬럼 | 타입 | 설명 |
| :--- | :--- | :--- |
| id | uuid | PK |
| ticker | text | 종목 |
| entry_price | numeric | 진입가 |
| current_price | numeric | 현재가 |
| quantity | numeric | 수량 |
| stop_loss_pct | numeric | 손절 |
| holding_days | integer | 보유일 |
| continuation_strength | numeric | 현재 강도 |
| position_status | text | OPEN/CLOSED |
| created_at | timestamp | 생성일 |
| closed_at | timestamp | 종료일 |

---

# 제7장. trade_logs 테이블

## 7.1 목적

실제 매매 기록 저장.

---

## 7.2 컬럼 구조

| 컬럼 | 타입 | 설명 |
| :--- | :--- | :--- |
| id | uuid | PK |
| ticker | text | 종목 |
| action | text | BUY/SELL |
| entry_price | numeric | 진입 |
| exit_price | numeric | 청산 |
| pnl_pct | numeric | 수익률 |
| holding_days | integer | 보유기간 |
| exit_reason | text | 종료 이유 |
| created_at | timestamp | 생성일 |

---

# 제8장. notification_logs 테이블

## 8.1 목적

Push 알림 기록.

---

## 8.2 컬럼 구조

| 컬럼 | 타입 | 설명 |
| :--- | :--- | :--- |
| id | uuid | PK |
| ticker | text | 종목 |
| notification_type | text | BUY/SELL |
| message | text | 메시지 |
| sent_status | boolean | 전송 성공 |
| created_at | timestamp | 생성일 |

---

# 제9장. batch_logs 테이블

## 9.1 목적

Daily Batch 상태 저장.

---

## 9.2 컬럼 구조

| 컬럼 | 타입 | 설명 |
| :--- | :--- | :--- |
| id | uuid | PK |
| batch_date | date | 실행일 |
| batch_status | text | SUCCESS/FAIL |
| total_candidates | integer | 후보 개수 |
| total_signals | integer | 신호 개수 |
| error_message | text | 오류 |
| created_at | timestamp | 생성일 |

---

# 제10장. system_logs 테이블

## 10.1 목적

운영 품질 추적.

---

## 10.2 핵심 역할

실전 운영에서:

> **전략보다 운영 품질 추적이 더 중요**

하다.

---

## 10.3 저장 항목

| 항목 | 목적 |
| :--- | :--- |
| False Breakout | 실패 패턴 |
| Stop Hit Frequency | 손절 빈도 |
| Re-entry Failure | 재진입 실패 |
| Slippage | 비용 |
| Missed Winner | 놓친 종목 |
| Turnover Leakage | 회전율 손실 |

---

## 10.4 컬럼 구조

| 컬럼 | 타입 | 설명 |
| :--- | :--- | :--- |
| id | uuid | PK |
| log_type | text | 로그 종류 |
| ticker | text | 종목 |
| description | text | 설명 |
| severity | text | LOW/MEDIUM/HIGH |
| created_at | timestamp | 생성일 |

---

# 제11장. Daily Snapshot 구조

## 11.1 목적

운영 안정성 확보.

---

## 11.2 Snapshot 저장 구조

> /data/YYYY-MM-DD/

구조 사용.

---

## 11.3 저장 파일

| 파일 | 목적 |
| :--- | :--- |
| candidates.parquet | 후보 저장 |
| scores.parquet | 점수 저장 |
| market.parquet | 시장 데이터 |
| logs.parquet | 운영 로그 |

---

# 제12장. 인덱스 전략

## 12.1 핵심 인덱스

| 테이블 | 인덱스 |
| :--- | :--- |
| daily_market_data | ticker + trade_date |
| candidate_signals | trade_date + ranking |
| portfolio_positions | position_status |
| trade_logs | ticker + created_at |

---

# 제13장. 데이터 보관 정책

## 13.1 MVP 정책

초기 MVP:

| 데이터 | 정책 |
| :--- | :--- |
| 일봉 데이터 | 장기 보관 |
| 신호 로그 | 영구 보관 |
| 배치 로그 | 영구 보관 |
| 오류 로그 | 영구 보관 |

---

## 13.2 삭제 금지

삭제 금지:
* trade history
* stop hit logs
* failed signals

이유:

> **실패 기록이

전략 개선의 핵심 데이터**

이기 때문.

---

# 제14장. SAFE MODE 지원 구조

## 14.1 목적

데이터 이상 감지.

---

## 14.2 SAFE MODE 저장

저장 항목:
* missing data
* corrupted rows
* abnormal scores
* batch failure

---

# 제15장. 현재 DB의 진짜 역할

MRH DB는:

> **거대한 퀀트 데이터 플랫폼**

이 아니다.

핵심은:

> **매일 발생하는
signal · ranking · portfolio · logs

를 단순하고 안정적으로 유지하는 것**

이다.
