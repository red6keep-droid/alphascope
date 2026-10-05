# MRH (Momentum Rotation Hunter)

# Backend System Specification V1

# 서버 · 배치 · 데이터 흐름 명세서

---

# 제1장. 백엔드 시스템 목적

## 1.1 핵심 역할

백엔드의 목적은:

> **매일 미국 시장 종료 후

강한 continuation 후보를 자동 수집하고
점수 계산 후
사용자에게 알림을 전송하는 것**

이다.

---

# 1.2 시스템 철학

MRH 백엔드는:

* 초고빈도 시스템
* 실시간 트레이딩 시스템
* 자동매매 시스템

이 아니다.

핵심은:

> **하루 1회 안정적으로 동작하는 저복잡성 배치 시스템**

이다.

---

# 제2장. 시스템 전체 구조

## 2.1 전체 흐름

> 외부 급등주 후보 수집
↓
시장 데이터 수집
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

---

# 제3장. 데이터 소스 구조

## 3.1 데이터 소스

| 역할 | 플랫폼 |
| :--- | :--- |
| 가격 데이터 | Yahoo Finance |
| 종목 메타정보 | Finnhub Free |
| 시장 상태 | KIS |
| 급등주 후보 | TradingView Scanner |
| 뉴스 확인 | Finviz |

---

## 3.2 MVP 원칙

MVP에서는:

> **무료 API 기반만 사용**

한다.

유료 데이터 금지.

---

# 제4장. Daily Batch 시스템

## 4.1 실행 시간

미국 시장 마감 이후 실행.

권장:

| 항목 | 시간 |
| :--- | :--- |
| 데이터 수집 | 미국 장 종료 후 |
| 점수 계산 | +10~20분 |
| 알림 전송 | 계산 완료 직후 |

---

## 4.2 Daily Batch 단계

### STEP 1 — 급등주 후보 수집

외부 플랫폼에서:
* 상승률 상위
* 거래량 급증
* sector movers

수집.

---

### STEP 2 — 종목 데이터 수집

수집 데이터:

| 항목 | 설명 |
| :--- | :--- |
| OHLCV | 가격 |
| Volume | 거래량 |
| Market Cap | 시총 |
| Sector | 섹터 |
| Relative Strength | 상대강도 |

---

### STEP 3 — Continuation Score 계산

계산 항목:
* Daily Momentum
* RVOL
* Closing Strength
* Gap Risk
* Sector Strength
* Relative Strength

---

### STEP 4 — Exhaustion Filter 적용

제외 대상:
* climax move
* long upper wick
* parabolic extension
* excessive gap

---

### STEP 5 — Top Candidate 선정

최종: 1~3개만 선정.

---

### STEP 6 — DB 저장

저장:
* 후보
* 점수
* 이유
* 로그

---

### STEP 7 — Push Notification 전송

사용자 모바일로:
* BUY
* SELL

알림 전송.

---

# 제5장. 시스템 모듈 구조

## 5.1 모듈 구성

| 모듈 | 역할 |
| :--- | :--- |
| collector | 데이터 수집 |
| scoring | 점수 계산 |
| filter | 위험 제거 |
| ranking | 순위 계산 |
| notifier | 알림 전송 |
| logger | 로그 저장 |

---

# 제6장. Collector 모듈

## 6.1 역할

외부 플랫폼 데이터 수집.

---

## 6.2 핵심 원칙

MRH는:

> **전체 시장 직접 스캔보다 강한 후보만 빠르게 압축 수집**

을 우선한다.

---

## 6.3 수집 대상

| 대상 | 목적 |
| :--- | :--- |
| Top Gainers | 핵심 |
| High RVOL | 중요 |
| Sector Leaders | 중요 |
| Strong Continuation | 중요 |

---

# 제7장. Scoring Engine

## 7.1 역할

후보별 continuation 가능성 점수화.

---

## 7.2 계산 구조

| 항목 | 점수 |
| :--- | :--- |
| Daily Momentum | 25 |
| RVOL | 20 |
| Close Strength | 15 |
| Sector Strength | 10 |
| Relative Strength | 15 |
| Gap Risk | -10 |
| Exhaustion | -20 |

---

## 7.3 핵심 원칙

점수 목적:

> **"얼마나 더 갈 가능성이 높은가"**

판단.

---

# 제8장. Filter Engine

## 8.1 목적

가짜 breakout 제거.

---

## 8.2 제거 대상

| 상태 | 이유 |
| :--- | :--- |
| 장대 윗꼬리 | distribution |
| 거래량 부족 | 약한 breakout |
| 과도한 갭상승 | exhaustion |
| climax move | risk |

---

# 제9장. Ranking Engine

## 9.1 목적

최종 후보 압축.

---

## 9.2 우선순위

정렬 기준:
1. Continuation Score
2. RVOL
3. Sector Strength
4. Market Cap
5. Closing Strength

---

## 9.3 핵심 원칙

MRH는:

> **좋은 종목 많이 찾기보다 최상위 후보 몇 개만 남기는 것**

을 우선한다.

---

# 제10장. Notification Engine

## 10.1 목적

사용자 행동 유도.

---

## 10.2 BUY 알림 조건

전송 조건:
* 상위 후보 선정
* minimum score 통과
* exhaustion 위험 없음

---

## 10.3 SELL 알림 조건

조건:
* 손절
* continuation 약화
* 거래량 붕괴
* score 급락

---

## 10.4 알림 철학

알림은:

> **복잡한 분석보다 즉시 행동 가능해야 한다**

---

# 제11장. Logging System

## 11.1 목적

운영 품질 추적.

---

## 11.2 저장 로그

| 항목 | 목적 |
| :--- | :--- |
| Signal Generated | 신호 기록 |
| Signal Failed | 실패 분석 |
| Stop Hit | 손절 분석 |
| False Breakout | 노이즈 추적 |
| Rebound Miss | missed winner 추적 |
| Holding Duration | 평균 보유기간 |

---

# 제12장. SAFE MODE 시스템

## 12.1 목적

데이터 이상 시 오작동 방지.

---

## 12.2 SAFE MODE 진입 조건

| 조건 | 동작 |
| :--- | :--- |
| 데이터 수집 실패 | 알림 중지 |
| 거래량 데이터 오류 | 후보 제외 |
| 가격 데이터 오류 | SAFE MODE |

---

## 12.3 SAFE MODE 동작

SAFE MODE 시:
* 신규 BUY 금지
* SELL만 허용
* 사용자 경고 전송

---

# 제13장. 비용 최소화 철학

## 13.1 핵심 원칙

MRH는:

> **복잡한 인프라보다 운영 안정성을 우선**

한다.

---

## 13.2 MVP 인프라 원칙

초기 MVP:

| 항목 | 구조 |
| :--- | :--- |
| Backend | Supabase |
| Batch | Cron |
| Storage | Postgres |
| Push | Firebase |
| Frontend | React Native |

---

# 제14장. 현재 시스템의 진짜 역할

MRH Backend는:

> **자동 수익 시스템**

이 아니다.

핵심은:

> **매일 시장에서 가장 강한 continuation 후보를 안정적으로 압축 전달하는 것**

이다.
