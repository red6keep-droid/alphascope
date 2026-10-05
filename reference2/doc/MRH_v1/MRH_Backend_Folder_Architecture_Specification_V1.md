# MRH (Momentum Rotation Hunter)

# Backend Folder Architecture Specification V1

# 실제 서버 구조 명세서

---

# 제1장. 백엔드 설계 철학

## 1.1 핵심 철학

MRH 서버의 핵심은:

> **복잡한 초고빈도 퀀트 서버가 아니라

매일 저녁
1회 배치 수행 후
알림만 안정적으로 보내는 것**

이다.

---

## 1.2 시스템 핵심 역할

백엔드는 단 5개만 수행한다.

| 역할 | 설명 |
| :--- | :--- |
| 데이터 수집 | 외부 플랫폼 데이터 |
| 후보 계산 | 점수 계산 |
| 매수/매도 판단 | signal 생성 |
| 포트폴리오 관리 | 보유 상태 관리 |
| 모바일 푸시 | 사용자 알림 |

---

# 제2장. 실제 폴더 구조

## 2.1 전체 구조

```text
/backend

├── src
│
├── batch
│   ├── market
│   ├── scoring
│   ├── signals
│   ├── portfolio
│   ├── notifications
│   └── snapshots
│
├── services
│   ├── market
│   ├── indicators
│   ├── ranking
│   ├── portfolio
│   ├── notifications
│   └── logs
│
├── repositories
│
├── prisma
│
├── cron
│
├── utils
│
├── config
│
├── types
│
├── constants
│
└── scripts
```

---

# 제3장. batch 구조

## 3.1 목적

> **매일 저녁 자동 실행되는 핵심 엔진**

---

## 3.2 market/

```text
batch/market
```

역할:
* Yahoo Finance 수집
* Finnhub 수집
* 외부 플랫폼 급등주 수집
* 거래량 데이터 수집

---

## 3.3 scoring/

```text
batch/scoring
```

역할:
* continuation score 계산
* momentum 계산
* relative volume 계산
* exhaustion risk 계산

---

## 3.4 signals/

```text
batch/signals
```

역할:
* BUY 판단
* SELL 판단
* stop hit 판단
* ranking 생성

---

## 3.5 portfolio/

```text
batch/portfolio
```

역할:
* 포지션 상태 업데이트
* holding days 계산
* exposure 계산

---

## 3.6 notifications/

```text
batch/notifications
```

역할:
* Firebase Push 전송
* 매수 알림
* 매도 알림

---

## 3.7 snapshots/

```text
batch/snapshots
```

역할:
* parquet 저장
* daily snapshot 저장
* 백업 저장

---

# 제4장. services 구조

## 4.1 services 목적

> **실제 비즈니스 로직 계층**

---

## 4.2 market/

역할:
* API 호출
* 외부 데이터 normalize
* 데이터 validation

---

## 4.3 indicators/

역할:
* RVOL 계산
* Gap 계산
* Momentum 계산
* ATR 계산

---

## 4.4 ranking/

역할:
* candidate ranking
* score weighting
* top N selection

---

## 4.5 portfolio/

역할:
* stop logic
* position sizing
* holding management

---

## 4.6 notifications/

역할:
* push formatting
* Firebase wrapper
* retry logic

---

## 4.7 logs/

역할:
* system logs
* failure logs
* whipsaw logs

---

# 제5장. repositories 구조

## 5.1 목적

> **DB 접근 분리**

---

## 5.2 예시

```text
repositories/
├── candidate.repository.ts
├── market.repository.ts
├── portfolio.repository.ts
└── trade.repository.ts
```

---

# 제6장. prisma 구조

## 6.1 목적

> **DB schema 관리**

---

## 6.2 구조

```text
prisma/
├── schema.prisma
└── migrations/
```

---

# 제7장. cron 구조

## 7.1 목적

> **배치 자동 실행**

---

## 7.2 예시

```typescript
0 5 * * 1-5
```

의미:
> **미국 장 마감 이후 실행**

---

# 제8장. utils 구조

## 8.1 역할

공용 함수 저장.

예시:
```text
utils/
├── date.ts
├── math.ts
├── logger.ts
├── sleep.ts
└── retry.ts
```

---

# 제9장. config 구조

## 9.1 역할

환경 설정 관리.

예시:
```text
config/
├── env.ts
├── firebase.ts
├── supabase.ts
└── api.ts
```

---

# 제10장. types 구조

## 10.1 역할

TypeScript 타입 저장.

---

# 제11장. constants 구조

## 11.1 역할

상수 저장.

예시:
```text
constants/
├── scoring.ts
├── portfolio.ts
├── stoploss.ts
└── ranking.ts
```

---

# 제12장. scripts 구조

## 12.1 역할

수동 실행 스크립트.

예시:
```text
scripts/
├── backfill.ts
├── recalculate.ts
└── reset.ts
```

---

# 제13장. 실제 Daily Batch 흐름

## 13.1 핵심 흐름

> 1. 외부 플랫폼 급등주 수집
    ↓
2. OHLCV 수집
    ↓
3. 점수 계산
    ↓
4. 후보 ranking 생성
    ↓
5. BUY/SELL signal 생성
    ↓
6. portfolio 업데이트
    ↓
7. 모바일 push 전송
    ↓
8. snapshot 저장

---

# 제14장. 실제 MVP 핵심 파일

## 14.1 반드시 필요한 파일

```text
batchRunner.ts
signalEngine.ts
rankingEngine.ts
portfolioManager.ts
notificationService.ts
```

---

# 제15장. MVP에서 하지 않는 것

초기 MVP 제외:
* microservice
* kafka
* redis cluster
* websocket infra
* realtime stream
* kubernetes
* event sourcing

---

# 제16장. 서버의 진짜 역할

MRH 서버는:

> **AI 초고빈도 기관 시스템**

이 아니다.

핵심은:

> **매일 저녁

단순하고
안정적으로

후보 선정
→ signal 생성
→ push 전송

만 수행하는 것**

이다.
