# MRH (Momentum Rotation Hunter)

# Technical Implementation Specification V1

# 실제 구현 명세서

---

# 제1장. 프로젝트 목표

## 1.1 MVP 목표

MRH MVP의 목표는 단 하나다.

> **매일 미국 시장 종료 후

가장 강한 continuation 후보 1~3개를 탐지하고

모바일로 BUY / SELL 알림을 보내는 것**

이다.

---

# 1.2 MVP에서 하지 않는 것

초기 MVP에서 제외:

* 자동매매
* 실시간 체결
* 초단타
* AI 예측
* 뉴스 감성분석
* 옵션 데이터
* 복잡한 차트
* 초고빈도 데이터

---

# 제2장. 최종 기술 스택

## 2.1 Frontend

| 항목 | 선택 |
| :--- | :--- |
| Framework | React Native Expo |
| Language | TypeScript |
| Navigation | Expo Router |
| State | Zustand |
| UI | NativeWind |
| Chart | Victory Native |

---

## 2.2 Backend

| 항목 | 선택 |
| :--- | :--- |
| Backend | Next.js |
| API | Next.js Route Handler |
| ORM | Prisma |
| Runtime | Node.js |
| Scheduler | Supabase Cron |

---

## 2.3 Database

| 항목 | 선택 |
| :--- | :--- |
| DB | PostgreSQL |
| Hosting | Supabase |
| Backup | Daily Snapshot |

---

## 2.4 Push System

| 항목 | 선택 |
| :--- | :--- |
| Push | Firebase FCM |
| Mobile Token | Expo Push Token |

---

## 2.5 Hosting

| 항목 | 선택 |
| :--- | :--- |
| Frontend | Expo EAS |
| Backend | Vercel |
| DB | Supabase |

---

# 제3장. 프로젝트 폴더 구조

## 3.1 Frontend 구조

```
/app
  /home
  /portfolio
  /history
  /system

/components
  /cards
  /layout
  /buttons

/store
/api
/types
/utils
/constants
```

---

## 3.2 Backend 구조

```
/src
  /api
  /batch
  /services
  /scoring
  /filters
  /notifications
  /db
  /utils
```

---

# 제4장. 핵심 실행 흐름

## 4.1 Daily Execution Pipeline

> 미국장 종료
↓
외부 플랫폼 Candidate 수집
↓
OHLCV 데이터 수집
↓
Score 계산
↓
Exhaustion Filter
↓
Top 1~3 선정
↓
DB 저장
↓
Push Notification
↓
모바일 표시

---

# 제5장. 외부 플랫폼 구조

## 5.1 외부 플랫폼 역할

외부 플랫폼은:

> **시장 전체 스캔을 대신 수행**

한다.

MRH는:

> **후보를 재평가하는 시스템**

이다.

---

## 5.2 무료 기반 플랫폼

초기 무료 MVP:

| 플랫폼 | 역할 |
| :--- | :--- |
| Yahoo Finance | OHLCV |
| Finviz | Top Gainers |
| Finnhub Free | Market Data |
| KIS API | 보조 검증 |

---

## 5.3 초기 후보 수집 기준

수집 대상:

| 조건 | 기준 |
| :--- | :--- |
| 하루 상승률 | +5% 이상 |
| RVOL | 2배 이상 |
| 거래대금 | 일정 수준 이상 |
| 미국 대형주 | 우선 |
| 섹터 리더 | 우선 |

---

# 제6장. Score Engine

## 6.1 Continuation Score 구조

> Continuation Score =
Momentum +
RVOL +
Sector Strength +
Close Strength -
Exhaustion Risk

---

## 6.2 Momentum Score

| 조건 | 점수 |
| :--- | :--- |
| +5~7% | +20 |
| +7~10% | +30 |
| +10% 이상 | +15 |

이유:

> **너무 큰 상승은
오히려 exhaustion 가능성 증가**

---

## 6.3 RVOL Score

| RVOL | 점수 |
| :--- | :--- |
| 2x | +10 |
| 3x | +20 |
| 4x 이상 | +25 |

---

## 6.4 Sector Strength

| 조건 | 점수 |
| :--- | :--- |
| 당일 강한 섹터 | +15 |
| 약한 섹터 | 0 |

---

## 6.5 Close Strength

| 조건 | 점수 |
| :--- | :--- |
| 종가가 고가 근처 | +15 |
| 윗꼬리 큼 | -10 |

---

## 6.6 Exhaustion Risk

| 조건 | 감점 |
| :--- | :--- |
| +15% 이상 급등 | -15 |
| 장대 윗꼬리 | -10 |
| Gap 과도 | -10 |

---

# 제7장. 매수 규칙

## 7.1 BUY 조건

최종 조건:

| 항목 | 조건 |
| :--- | :--- |
| Score | 70 이상 |
| RVOL | 2배 이상 |
| 상승률 | +5% 이상 |
| 종가 강도 | 강함 |
| Exhaustion | 낮음 |

---

## 7.2 매수 개수 제한

| 항목 | 제한 |
| :--- | :--- |
| 하루 신규 진입 | 최대 1 |
| 전체 보유 | 최대 3 |
| 동일 섹터 | 최대 1 |

---

# 제8장. 매도 규칙

## 8.1 핵심 철학

> **수익은 열어두고
손실은 빠르게 끊는다**

---

## 8.2 손절 구조

초기 MVP:

| 상태 | 손절 |
| :--- | :--- |
| 일반 | -5% |
| 초고변동 | -7% |
| 약한 continuation | -3% |

---

## 8.3 SELL 조건

| 조건 | 설명 |
| :--- | :--- |
| 손절 도달 | 즉시 SELL |
| continuation 붕괴 | SELL |
| 거래량 급감 | SELL |
| 장대 음봉 | SELL |
| 7거래일 초과 | 부분 청산 고려 |

---

# 제9장. Position Management

## 9.1 보유 기간

| 항목 | 기준 |
| :--- | :--- |
| 평균 보유 | 3~7일 |
| 최대 보유 | 10거래일 |
| 예외 | 강한 trend |

---

## 9.2 핵심 철학

MRH는:

> **Winner Rotation System**

이다.

장기투자 시스템이 아니다.

---

# 제10장. Notification System

## 10.1 BUY Push

```
[BUY SIGNAL]

PLTR
Score: 84
RVOL: 3.1x
Sector: AI Software

Suggested Stop:
-5%
```

---

## 10.2 SELL Push

```
[SELL SIGNAL]

PLTR
PnL: +9.2%

Reason:
Momentum Weakness
```

---

# 제11장. Batch Scheduler

## 11.1 Daily Batch Time

| 작업 | 시간 |
| :--- | :--- |
| Candidate Fetch | 미국장 종료 후 |
| Score Calculation | 이후 즉시 |
| Push Send | 계산 완료 후 |

---

# 제12장. SAFE MODE

## 12.1 SAFE MODE 조건

| 조건 | 동작 |
| :--- | :--- |
| API 실패 | BUY 중단 |
| 데이터 누락 | SAFE MODE |
| 비정상 Score | 경고 |

---

## 12.2 SAFE MODE 정책

SAFE MODE 시:

* 신규 BUY 금지
* SELL만 허용
* 사용자 알림 전송

---

# 제13장. 운영 로그 시스템

## 13.1 반드시 기록할 로그

| 로그 | 목적 |
| :--- | :--- |
| False Breakout | 실패 분석 |
| Stop Hit Rate | 손절 빈도 |
| Avg Winner | 평균 승자 |
| Avg Loser | 평균 패자 |
| Rebound Miss | 놓친 상승 |
| Turnover Leakage | 회전 손실 |

---

# 제14장. MVP 핵심 성공 조건

## 14.1 성공 기준

MRH의 핵심은:

> **매일 가장 강한 continuation 종목을
안정적으로 탐지하는 것**

이다.

---

## 14.2 실패 조건

아래 발생 시 실패:

* 지나친 turnover
* repeated false breakout
* stop hit explosion
* delayed SELL
* signal inconsistency

---

# 제15장. 현재 시스템의 진짜 정체성

MRH는:

> **초고수익 AI 퀀트 시스템**

이 아니다.

본질은:

> **미국 시장의 강한 momentum continuation 종목을

짧게 회전하며 추적하는

개인용 tactical momentum rotation system**

이다.
