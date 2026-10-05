# MRH (Momentum Rotation Hunter)

# Prisma ORM Schema Specification V1

# Prisma 실제 구현 명세서

---

# 제1장. Prisma 도입 목적

## 1.1 핵심 목적

Prisma의 목적은:

> **SQL 직접 관리보다

안정적이고 빠른 CRUD 개발**

이다.

---

# 1.2 Prisma 선택 이유

| 이유 | 설명 |
| :--- | :--- |
| Type Safety | TypeScript 연동 |
| 빠른 개발 | CRUD 자동화 |
| 유지보수 | schema 기반 |
| Supabase 호환 | PostgreSQL 지원 |

---

# 제2장. 설치 구조

## 2.1 설치 패키지

```bash
npm install prisma @prisma/client
```

---

## 2.2 Prisma 초기화

```bash
npx prisma init
```

---

# 제3장. .env 구조

## 3.1 DATABASE_URL

```env
DATABASE_URL="postgresql://..."
```

---

# 제4장. Prisma Schema 전체 구조

## 4.1 schema.prisma

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
```

---

# 제5장. Ticker Model

## 5.1 Prisma Model

```prisma
model Ticker {
  id            String   @id @default(uuid())
  ticker        String   @unique

  companyName   String?
  sector        String?
  industry      String?

  marketCap     BigInt?

  isActive      Boolean  @default(true)

  createdAt     DateTime @default(now())
}
```

---

# 제6장. DailyMarketData Model

## 6.1 Prisma Model

```prisma
model DailyMarketData {
  id                  String   @id @default(uuid())

  ticker              String

  tradeDate           DateTime

  open                Float?
  high                Float?
  low                 Float?
  close               Float?

  volume              BigInt?

  dailyChangePct      Float?
  rvol                Float?
  gapPct              Float?

  createdAt           DateTime @default(now())

  @@index([ticker, tradeDate])
}
```

---

# 제7장. CandidateSignal Model

## 7.1 Prisma Model

```prisma
model CandidateSignal {
  id                     String   @id @default(uuid())

  ticker                 String

  tradeDate              DateTime

  continuationScore      Float?

  dailyMomentumScore     Float?
  rvolScore              Float?
  sectorScore            Float?
  closeStrengthScore     Float?

  exhaustionRisk         Float?

  ranking                Int?

  signalType             SignalType?

  signalReason           String?

  createdAt              DateTime @default(now())

  @@index([tradeDate, ranking])
}
```

---

# 제8장. PortfolioPosition Model

## 8.1 Prisma Model

```prisma
model PortfolioPosition {
  id                      String   @id @default(uuid())

  ticker                  String

  entryPrice              Float?
  currentPrice            Float?

  quantity                Float?

  stopLossPct             Float?

  holdingDays             Int?

  continuationStrength    Float?

  positionStatus          PositionStatus

  createdAt               DateTime @default(now())

  closedAt                DateTime?
}
```

---

# 제9장. TradeLog Model

## 9.1 Prisma Model

```prisma
model TradeLog {
  id                String   @id @default(uuid())

  ticker            String

  action            SignalType?

  entryPrice        Float?
  exitPrice         Float?

  pnlPct            Float?

  holdingDays       Int?

  exitReason        String?

  createdAt         DateTime @default(now())

  @@index([ticker, createdAt])
}
```

---

# 제10장. NotificationLog Model

## 10.1 Prisma Model

```prisma
model NotificationLog {
  id                  String   @id @default(uuid())

  ticker              String?

  notificationType    SignalType?

  message             String?

  sentStatus          Boolean @default(false)

  createdAt           DateTime @default(now())
}
```

---

# 제11장. BatchLog Model

## 11.1 Prisma Model

```prisma
model BatchLog {
  id                  String   @id @default(uuid())

  batchDate           DateTime

  batchStatus         BatchStatus

  totalCandidates     Int?

  totalSignals        Int?

  errorMessage        String?

  createdAt           DateTime @default(now())
}
```

---

# 제12장. SystemLog Model

## 12.1 Prisma Model

```prisma
model SystemLog {
  id                String   @id @default(uuid())

  logType          String

  ticker           String?

  description      String?

  severity         String?

  createdAt        DateTime @default(now())
}
```

---

# 제13장. Enum 구조

## 13.1 PositionStatus

```prisma
enum PositionStatus {
  OPEN
  CLOSED
}
```

---

## 13.2 SignalType

```prisma
enum SignalType {
  BUY
  SELL
  HOLD
}
```

---

## 13.3 BatchStatus

```prisma
enum BatchStatus {
  SUCCESS
  FAIL
  SAFE_MODE
}
```

---

# 제14장. Prisma Migration

## 14.1 Migration 생성

```bash
npx prisma migrate dev --name init
```

---

## 14.2 Prisma Client 생성

```bash
npx prisma generate
```

---

# 제15장. Prisma Client 구조

## 15.1 db.ts

```typescript
import { PrismaClient } from '@prisma/client'

export const prisma = new PrismaClient()
```

---

# 제16장. Candidate 저장 예시

## 16.1 예시 코드

```typescript
await prisma.candidateSignal.create({
  data: {
    ticker: 'PLTR',
    continuationScore: 84,
    ranking: 1,
    signalType: 'BUY'
  }
})
```

---

# 제17장. Candidate 조회 예시

## 17.1 Top Candidates

```typescript
const topCandidates =
  await prisma.candidateSignal.findMany({
    orderBy: {
      continuationScore: 'desc'
    },
    take: 3
  })
```

---

# 제18장. MVP에서 하지 않는 것

초기 MVP 제외:

* 복잡한 relation
* nested transaction
* real-time DB
* tick storage
* orderbook storage

---

# 제19장. 현재 Prisma 구조의 진짜 목적

MRH Prisma 구조는:

> **기관급 복합 퀀트 ORM**

이 아니다.

핵심은:

> **매일 발생하는

signal
ranking
portfolio
logs

를
빠르고 안정적으로 관리하는 것**

이다.
