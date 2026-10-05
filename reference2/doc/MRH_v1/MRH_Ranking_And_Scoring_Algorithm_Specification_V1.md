# MRH (Momentum Rotation Hunter)

# MRH_Ranking_And_Scoring_Algorithm_Specification_V1

# Ranking & Scoring 엔진 명세서

---

# 제1장. Ranking Engine 철학

## 1.1 핵심 철학
MRH의 핵심은:

```
"좋은 기업 찾기"
```
가 아니다.

핵심은:

```
"지금 시장에서 가장 강한 흐름"
```
을 찾는 것이다.

---

# 1.2 시스템 본질
MRH는:

```
장기 가치평가 시스템
```
이 아니다.

또한:

```
복잡한 AI 예측 시스템
```
도 아니다.

실제 역할은:

```
매일 발생하는
강한 단기 continuation 후보를
우선순위화하는 것
```
이다.

---

# 제2장. Ranking Engine 전체 구조

# 2.1 전체 흐름

```
후보 수집
↓
Normalization
↓
개별 점수 계산
↓
Penalty 적용
↓
최종 Ranking
↓
Top 1~3 선정
```

---

# 2.2 핵심 목적
MRH는:

```
"상승한 종목"
```
이 아니라:

```
"내일도 추가 상승 가능성이 높은 종목"
```
을 찾는다.

---

# 제3장. 최종 점수 구조

# 3.1 최종 점수

```
Continuation Score
=
Momentum
+
RVOL
+
Sector
+
Close Strength
-
Exhaustion Risk
```

---

# 3.2 총점 구조
| 항목 | 최대 점수 |
| :--- | :--- |
| Daily Momentum | 35 |
| Relative Volume | 25 |
| Sector Strength | 20 |
| Close Strength | 20 |
| Exhaustion Penalty | -30 |

---

# 제4장. Daily Momentum Score

# 4.1 목적

```
오늘 얼마나 강했는가
```
판단.

---

# 4.2 핵심 원칙
MRH는:

```
너무 약한 종목
```
도 싫어하고:

```
너무 과열된 종목
```
도 경계한다.

---

# 4.3 점수 예시
| 하루 상승률 | 점수 |
| :--- | :--- |
| +3% 미만 | 0 |
| +5% | 15 |
| +8% | 25 |
| +10~12% | 35 |
| +20% 이상 | penalty 후보 |

---

# 제5장. Relative Volume Score

# 5.1 목적

```
실제 자금 유입 확인
```

---

# 5.2 계산 구조

```
RVOL
=
오늘 거래량
÷
20일 평균 거래량
```

---

# 5.3 점수 예시
| RVOL | 점수 |
| :--- | :--- |
| < 1.5 | 0 |
| 1.5 | 10 |
| 2.0 | 18 |
| 3.0 이상 | 25 |

---

# 제6장. Sector Strength Score

# 6.1 목적

```
섹터 전체 흐름 확인
```

---

# 6.2 핵심 논리
강한 종목은:

```
강한 섹터 내부에서
계속 발생하는 경우 많음
```

---

# 6.3 섹터 ETF 예시
| 섹터 | ETF |
| :--- | :--- |
| AI/Semi | SMH |
| Tech | XLK |
| Energy | XLE |
| Financial | XLF |

---

# 6.4 점수 예시
| 섹터 ETF 상태 | 점수 |
| :--- | :--- |
| 약세 | 0 |
| 중립 | 10 |
| 강세 추세 | 20 |

---

# 제7장. Close Strength Score

# 7.1 목적

```
종가까지 매수세 유지 여부
```
판단.

---

# 7.2 계산 방식

```
(close - low)
÷
(high - low)
```

---

# 7.3 해석
| 결과 | 의미 |
| :--- | :--- |
| 0.2 이하 | 약함 |
| 0.5 | 중립 |
| 0.8 이상 | 매우 강함 |

---

# 제8장. Exhaustion Risk Penalty

# 8.1 목적

```
이미 끝물인지 확인
```

---

# 8.2 핵심 이유
MRH는:

```
초기 continuation
```
을 원하지:

```
마지막 blow-off
```
를 추격하지 않는다.

---

# 8.3 위험 조건
| 조건 | penalty |
| :--- | :--- |
| +20% 이상 급등 | -10 |
| 윗꼬리 과도 | -8 |
| 장중 급락 | -10 |
| 거래량 급감 | -5 |

---

# 제9장. Outlier 처리

# 9.1 목적

```
비정상 급등 왜곡 제거
```

---

# 9.2 제거 대상
| 조건 | 행동 |
| :--- | :--- |
| +40% 이상 급등 | 제외 가능 |
| penny stock | 제외 |
| volume 부족 | 제외 |

---

# 제10장. Ranking Tie-Break Rules

# 10.1 동점 처리
우선순위:

```
1. RVOL
2. Sector Strength
3. Close Strength
```

---

# 제11장. 최종 후보 선택

# 11.1 최종 선정 수
최대:

```
1~3개
```

---

# 11.2 핵심 이유
MRH는:

```
강한 흐름 집중 추적
```
이 목적.

---

# 제12장. No Trade Zone

# 12.1 목적

```
애매한 후보 강제 매매 방지
```

---

# 12.2 조건
| 조건 | 행동 |
| :--- | :--- |
| 최고 점수 < 60 | 신규 진입 금지 |
| 후보 간 점수 차이 미미 | HOLD 가능 |

---

# 제13장. Market Risk Filter

# 13.1 목적

```
시장 전체 붕괴 시 공격 억제
```

---

# 13.2 Risk OFF 조건
| 조건 | 행동 |
| :--- | :--- |
| SPY 200MA 하회 | caution |
| VIX 급등 | position 축소 |
| RSP 약세 | 신규 진입 제한 |

---

# 제14장. 실제 운영 핵심

# 14.1 중요한 사실
MRH는:

```
매일 예측 성공
```
을 목표로 하지 않는다.

---

# 14.2 실제 핵심
핵심은:

```
작은 손실 여러 번
+
강한 winner 몇 번 크게 먹기
```
구조 유지.

---

# 제15장. MVP에서 하지 않는 것
초기 MVP 제외:

- AI scoring
- LLM ranking
- sentiment NLP
- options flow
- dark pool
- tick prediction

---

# 제16장. Ranking Engine의 진짜 역할
MRH Ranking Engine은:

```
미래를 예측하는 AI
```
가 아니다.

실제 역할은:

```
오늘 시장에서
가장 강한 continuation 흐름을
우선순위화하는 것
```
이다.
