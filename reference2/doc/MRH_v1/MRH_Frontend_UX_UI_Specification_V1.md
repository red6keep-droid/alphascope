# MRH (Momentum Rotation Hunter)

# Frontend UX/UI Specification V1

# 모바일 앱 화면 구조 및 사용자 경험 명세서

---

# 제1장. 앱 UX 철학

## 1.1 핵심 철학

MRH 앱의 목적은:

> **복잡한 분석 플랫폼이 아니라

"오늘 무엇을 살 것인가"

를 빠르게 결정하게 만드는 것**

이다.

---

## 1.2 사용자 행동 원칙

사용자는:

* 차트 분석가가 아니다
* 퀀트 연구원이 아니다
* 매일 1시간 분석하지 않는다

핵심은:

> **5~30초 안에

행동 결정 가능해야 한다**

이다.

---

## 1.3 UI 핵심 원칙

| 원칙 | 설명 |
| :--- | :--- |
| 최소 클릭 | 빠른 행동 |
| 최소 정보 | 핵심만 표시 |
| 색상 직관화 | BUY/SELL 즉시 인식 |
| 점수 압축 | 복잡한 지표 제거 |
| 모바일 우선 | Desktop 후순위 |

---

# 제2장. 전체 앱 구조

## 2.1 메인 탭 구조

| 탭 | 목적 |
| :--- | :--- |
| Home | 오늘의 신호 |
| Candidates | 상위 후보 |
| Portfolio | 현재 보유 |
| History | 과거 기록 |
| System | 운영 상태 |

---

# 제3장. HOME 화면

## 3.1 목적

앱의 핵심 화면.

사용자는 대부분 이 화면만 본다.

---

## 3.2 핵심 역할

> **오늘 무엇을 살 것인가
오늘 무엇을 팔 것인가**

를 즉시 전달.

---

## 3.3 화면 구성

### SECTION 1 — Market Status

상단 상태 바.

표시:

| 항목 | 예시 |
| :--- | :--- |
| Market Mode | RISK ON |
| Top Sector | AI |
| Market Risk | NORMAL |
| Daily Candidates | 3 |

---

### SECTION 2 — BUY SIGNAL CARD

핵심 카드.

#### 표시 정보

| 항목 | 설명 |
| :--- | :--- |
| 티커 | NVDA |
| 상승률 | +7.2% |
| RVOL | 3.4x |
| Continuation Score | 88 |
| 섹터 | Semiconductor |
| 추천 손절 | -5% |

---

#### 핵심 UI 특징

BUY 카드:

* 초록 강조
* 큰 티커
* 큰 점수
* 최소 텍스트

---

### SECTION 3 — SELL SIGNAL CARD

보유 종목 청산 알림.

표시:

| 항목 | 설명 |
| :--- | :--- |
| 티커 | PLTR |
| 수익률 | +9.2% |
| 보유일 | 4일 |
| 종료 사유 | Momentum Weakness |

---

# 제4장. Candidates 화면

## 4.1 목적

오늘의 상위 continuation 후보 제공.

---

## 4.2 표시 기준

Top 1~5만 표시.

이유:

> **후보가 많아질수록

판단력이 무너진다**

---

## 4.3 카드 정보

| 항목 | 설명 |
| :--- | :--- |
| Rank | 순위 |
| Ticker | 종목 |
| Sector | 섹터 |
| Score | continuation score |
| RVOL | 거래량 |
| Gap | 갭 상승 |
| Exhaustion Risk | 과열 위험 |

---

# 제5장. Portfolio 화면

## 5.1 목적

현재 보유 상태 추적.

---

## 5.2 표시 항목

| 항목 | 설명 |
| :--- | :--- |
| 현재 수익률 | PnL |
| 보유일 | holding days |
| 현재 손절 거리 | stop distance |
| 현재 강도 | continuation strength |

---

## 5.3 핵심 UX

포트폴리오 화면은:

> **복잡한 자산 관리 도구가 아니라

현재 살아있는 포지션 확인**

에 집중한다.

---

# 제6장. History 화면

## 6.1 목적

과거 매매 기록 추적.

---

## 6.2 표시 항목

| 항목 | 설명 |
| :--- | :--- |
| 티커 | 종목 |
| 진입일 | entry |
| 청산일 | exit |
| 수익률 | pnl |
| 보유기간 | holding days |
| 종료 이유 | stop / weakness |

---

# 제7장. System 화면

## 7.1 목적

운영 품질 확인.

---

## 7.2 표시 항목

| 항목 | 설명 |
| :--- | :--- |
| False Breakout Rate | 실패율 |
| Stop Hit Frequency | 손절 빈도 |
| Avg Holding Days | 평균 보유 |
| Win Rate | 승률 |
| Avg Winner | 평균 수익 |
| Avg Loser | 평균 손실 |

---

# 제8장. Push Notification UX

## 8.1 핵심 철학

Push는:

> **알림이 아니라

행동 트리거**

이다.

---

## 8.2 BUY Push 구조

```
[BUY SIGNAL]

NVDA
Continuation Score: 88
RVOL: 3.4x

Suggested Stop:
-5%
```

---

## 8.3 SELL Push 구조

```
[SELL SIGNAL]

PLTR
PnL: +11.2%

Reason:
Momentum Weakness
```

---

# 제9장. 색상 정책

## 9.1 핵심 원칙

| 상태 | 색상 |
| :--- | :--- |
| BUY | Green |
| SELL | Red |
| HOLD | Blue |
| WARNING | Orange |
| SAFE MODE | Gray |

---

# 제10장. UX에서 제거해야 할 요소

## 10.1 제거 대상

초기 MVP에서 제거:

* 복잡한 차트
* 실시간 체결
* 호가창
* 옵션 체인
* 뉴스 피드
* AI 리포트
* 감성 분석

---

## 10.2 제거 이유

> **정보가 많을수록

행동은 느려진다**

---

# 제11장. 모바일 UX 핵심 목표

## 11.1 핵심 목표

사용자는 앱 진입 후:

> **30초 안에

매수/매도 판단 가능**

해야 한다.

---

# 제12장. 실제 사용자 행동 흐름

## 12.1 Daily User Flow

> Push Notification 수신
↓
앱 실행
↓
Top Signal 확인
↓
점수 확인
↓
직접 증권사 앱에서 매수
↓
다음날 SELL 여부 확인

---

# 제13장. 현재 UX 구조의 진짜 목적

MRH UX의 목적은:

> **복잡한 분석 경험**

이 아니다.

핵심은:

> **매일 가장 강한 momentum continuation 종목을

빠르고 단순하게 행동하게 만드는 것**

이다.
