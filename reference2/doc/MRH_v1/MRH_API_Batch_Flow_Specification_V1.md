# MRH (Momentum Rotation Hunter)

# API & Batch Flow Specification V1

# API · 실행 흐름 · 모바일 연동 명세서

---

# 제1장. API 시스템 목적

## 1.1 핵심 목적

MRH API의 목적은:

> **매일 생성된 continuation 후보를

모바일 앱에
빠르고 안정적으로 전달하는 것**

이다.

---

# 1.2 시스템 철학

MRH는:

* 초고빈도 API
* 실시간 트레이딩 API
* 초저지연 시스템

이 아니다.

핵심은:

> **하루 1회 안정적으로 신호를 전달하는 것**

이다.

---

# 제2장. 전체 실행 흐름

## 2.1 Daily Execution Flow

> 미국 장 종료
↓
외부 플랫폼 후보 수집
↓
Yahoo/Finnhub/KIS 데이터 수집
↓
Continuation Score 계산
↓
Exhaustion Filter 적용
↓
Top Candidate 선정
↓
DB 저장
↓
Push Notification 전송
↓
모바일 앱 조회 가능

---

# 제3장. 시스템 구조

## 3.1 전체 아키텍처

| 계층 | 역할 |
| :--- | :--- |
| Mobile App | 사용자 UI |
| API Server | 데이터 제공 |
| Batch Engine | 매일 점수 계산 |
| PostgreSQL | 데이터 저장 |
| Firebase | Push 알림 |
| Supabase | Backend 플랫폼 |

---

# 제4장. API 설계 철학

## 4.1 핵심 철학

MRH API는:

> **복잡한 분석 API보다

"지금 무엇을 사야 하는가"

를 빠르게 전달해야 한다**

---

## 4.2 MVP 원칙

MVP에서는:

* REST API만 사용
* GraphQL 미사용
* WebSocket 미사용
* 실시간 스트리밍 미사용

---

# 제5장. API Endpoint 구조

## 5.1 핵심 Endpoint

| Endpoint | 목적 |
| :--- | :--- |
| /signals/today | 오늘 신호 |
| /signals/history | 과거 기록 |
| /portfolio | 현재 보유 |
| /market/status | 시장 상태 |
| /logs/system | 운영 로그 |
| /candidates/top | 상위 후보 |

---

# 제6장. Today Signals API

## 6.1 목적

오늘의 BUY/SELL 신호 제공.

---

## 6.2 Endpoint

```http
GET /signals/today
```

---

## 6.3 Response 구조

```json
[
  {
    "ticker": "PLTR",
    "companyName": "Palantir",
    "signalType": "BUY",
    "continuationScore": 84,
    "dailyChangePct": 7.2,
    "rvol": 3.1,
    "sector": "Software",
    "stopLossPct": -5,
    "exhaustionRisk": "LOW"
  }
]
```

---

# 제7장. Top Candidates API

## 7.1 목적

상위 continuation 후보 제공.

---

## 7.2 Endpoint

```http
GET /candidates/top
```

---

## 7.3 Response

```json
[
  {
    "ticker": "NVDA",
    "score": 88,
    "sector": "Semiconductor",
    "rank": 1
  }
]
```

---

# 제8장. Portfolio API

## 8.1 목적

현재 보유 상태 제공.

---

## 8.2 Endpoint

```http
GET /portfolio
```

---

## 8.3 Response

```json
[
  {
    "ticker": "PLTR",
    "entryPrice": 42.5,
    "currentPrice": 47.8,
    "pnlPct": 12.4,
    "holdingDays": 4,
    "stopLossPct": -5
  }
]
```

---

# 제9장. Market Status API

## 9.1 목적

현재 시장 상태 제공.

---

## 9.2 Endpoint

```http
GET /market/status
```

---

## 9.3 Response

```json
{
  "spyTrend": "BULLISH",
  "marketRisk": "NORMAL",
  "topSector": "AI",
  "riskMode": "ON"
}
```

---

# 제10장. System Logs API

## 10.1 목적

운영 품질 추적.

---

## 10.2 Endpoint

```http
GET /logs/system
```

---

## 10.3 Response

```json
[
  {
    "type": "FALSE_BREAKOUT",
    "ticker": "XYZ",
    "severity": "MEDIUM",
    "createdAt": "2026-05-28"
  }
]
```

---

# 제11장. Batch Engine 상세 흐름

## 11.1 Daily Batch 시작

미국 시장 종료 후 자동 시작.

---

## 11.2 실행 순서

### STEP 1 — External Candidate Fetch

수집:
* Top Gainers
* RVOL 급증
* Sector Leaders

---

### STEP 2 — Market Data Fetch

수집:
* OHLCV
* Volume
* Sector
* Market Cap

---

### STEP 3 — Signal Calculation

계산:
* continuation score
* exhaustion risk
* ranking

---

### STEP 4 — Filtering

제거:
* climax move
* weak close
* excessive gap

---

### STEP 5 — Ranking

최종: Top 1~3 압축.

---

### STEP 6 — Save DB

저장:
* signals
* scores
* logs

---

### STEP 7 — Push Notification

사용자에게: BUY/SELL 전송.

---

# 제12장. Push Notification 시스템

## 12.1 BUY 메시지

예시:

```text
[BUY SIGNAL]

PLTR
Score: 84
RVOL: 3.1x
Sector: AI Software

Suggested Stop:
-5%
```

---

## 12.2 SELL 메시지

예시:

```text
[SELL SIGNAL]

PLTR
Reason:
Continuation Weakness

PnL:
+9.2%
```

---

# 제13장. Cron Schedule 구조

## 13.1 Daily Schedule

| 작업 | 실행 |
| :--- | :--- |
| Candidate Fetch | Daily |
| Market Fetch | Daily |
| Score Calculation | Daily |
| Push Notification | Daily |
| Snapshot Backup | Daily |

---

# 제14장. SAFE MODE 흐름

## 14.1 목적

오작동 방지.

---

## 14.2 SAFE MODE 진입 조건

| 조건 | 동작 |
| :--- | :--- |
| 데이터 누락 | BUY 중단 |
| API 오류 | SAFE MODE |
| 비정상 score | 경고 |

---

## 14.3 SAFE MODE 정책

SAFE MODE 시:
* 신규 BUY 금지
* SELL만 허용
* 사용자 경고 전송

---

# 제15장. 모바일 앱 연동 철학

## 15.1 핵심 원칙

앱은:

> **분석 플랫폼보다

빠른 행동 도구**

에 가까워야 한다.

---

## 15.2 사용자 행동 흐름

> Push Notification 수신
↓
앱 진입
↓
Top Candidate 확인
↓
5초 내 판단
↓
직접 매수

---

# 제16장. 현재 API 시스템의 진짜 역할

MRH API 시스템은:

> **실시간 초고속 트레이딩 엔진**

이 아니다.

핵심은:

> **매일 미국 시장에서
가장 강한 continuation 후보를

안정적으로 사용자에게 전달하는 것**

이다.
