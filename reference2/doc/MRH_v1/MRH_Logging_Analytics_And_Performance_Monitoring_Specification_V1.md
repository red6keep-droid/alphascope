# MRH (Momentum Rotation Hunter)

# MRH_Logging_Analytics_And_Performance_Monitoring_Specification_V1

# 운영 로그 · 성능 분석 · 전략 모니터링 명세서

---

# 제1장. Monitoring 시스템 철학

## 1.1 핵심 철학
MRH에서 가장 중요한 건:

```
좋아 보이는 백테스트
```
가 아니다.

실제 중요한 건:

```
실제 운영 중
시스템이 어떻게 망가지는가
```
를 추적하는 것이다.

---

# 1.2 핵심 관점 변화
MRH는 이제:

```
전략 설계 단계
```
를 거의 끝냈다.

이제 중요한 건:

```
운영 관측
+
실전 로그 축적
```
이다.

---

# 제2장. Monitoring 시스템 역할

# 2.1 핵심 역할
Monitoring 시스템은:

```
수익률 자랑 도구
```
가 아니다.

실제 역할:

```
시스템 퇴화 감지
+
운영 leakage 측정
+
위험 행동 탐지
```

---

# 2.2 반드시 측정할 것
MRH는 반드시 아래를 기록:

- false breakout
- false continuation
- missed rebound
- excessive turnover
- delayed re-entry
- slippage accumulation

---

# 제3장. Daily Trading Log 구조

# 3.1 핵심 목적

```
모든 의사결정 기록
```

---

# 3.2 저장 항목
| 항목 | 설명 |
| :--- | :--- |
| ticker | 종목 |
| entry_date | 진입일 |
| exit_date | 청산일 |
| entry_price | 진입가 |
| exit_price | 청산가 |
| holding_days | 보유일 |
| pnl_pct | 수익률 |
| exit_reason | 종료 사유 |

---

# 3.3 Exit Reason 구조
| 코드 | 의미 |
| :--- | :--- |
| STOP_LOSS | 손절 |
| TRAILING_EXIT | 추세 종료 |
| TIME_STOP | 시간 종료 |
| RISK_OFF | 시장 위험 |
| MANUAL_EXIT | 수동 종료 |

---

# 제4장. Signal Quality Monitoring

# 4.1 핵심 목적

```
신호 품질 검증
```

---

# 4.2 측정 항목
| 항목 | 의미 |
| :--- | :--- |
| signal_count | 총 신호 |
| profitable_signals | 수익 신호 |
| failed_signals | 실패 신호 |
| avg_winner | 평균 수익 |
| avg_loser | 평균 손실 |

---

# 4.3 핵심 분석
MRH는:

```
승률
```
보다:

```
winner / loser 비율
```
을 중요하게 봄.

---

# 제5장. Whipsaw Monitoring

# 5.1 매우 중요
실전 시스템을 죽이는 핵심:

```
반복적인 잘못된 방향 전환
```

---

# 5.2 측정 항목
| 항목 | 설명 |
| :--- | :--- |
| false_crisis_count | 잘못된 Risk OFF |
| immediate_rebound | 직후 반등 |
| repeated_reentry | 반복 진입 |
| switch_frequency | 상태 전환 빈도 |

---

# 5.3 경고 조건
| 조건 | 의미 |
| :--- | :--- |
| 월 5회 이상 whipsaw | 위험 |
| repeated stopouts | 위험 |
| excessive switching | 점검 필요 |

---

# 제6장. Turnover Leakage Monitoring

# 6.1 핵심 목적

```
과도한 거래 비용 탐지
```

---

# 6.2 측정 항목
| 항목 | 설명 |
| :--- | :--- |
| monthly_turnover | 월 회전율 |
| avg_holding_days | 평균 보유 |
| fee_total | 누적 수수료 |
| slippage_total | 누적 슬리피지 |

---

# 6.3 위험 상태
| 상태 | 의미 |
| :--- | :--- |
| turnover 급증 | 과민 반응 |
| holding 급감 | noise trading 위험 |

---

# 제7장. Recovery Delay Monitoring

# 7.1 핵심 목적

```
재진입이 너무 느린지 확인
```

---

# 7.2 측정 항목
| 항목 | 설명 |
| :--- | :--- |
| rebound_miss_pct | 놓친 반등 |
| reentry_delay_days | 재진입 지연 |
| vshape_miss_count | 급반등 미포착 |

---

# 7.3 핵심 이유
Continuation 전략은:

```
하락 회피
```
대신:

```
강한 반등 놓침
```
위험 존재.

---

# 제8장. Exposure Monitoring

# 8.1 목적

```
노출도 과다 방지
```

---

# 8.2 기록 항목
| 항목 | 설명 |
| :--- | :--- |
| avg_exposure | 평균 노출 |
| max_exposure | 최대 노출 |
| cash_ratio | 현금 비중 |
| sector_concentration | 섹터 집중 |

---

# 8.3 핵심 확인
MRH는 반드시 확인:

```
실제로 너무 tech 편향 아닌가?
```

---

# 제9장. Strategy Health Dashboard

# 9.1 핵심 목적

```
전략 상태 실시간 확인
```

---

# 9.2 Dashboard 핵심 지표
| 지표 | 의미 |
| :--- | :--- |
| rolling_sharpe | 전략 건강 |
| rolling_drawdown | 위험 |
| win_rate | 참고 |
| avg_winner | 중요 |
| avg_loser | 중요 |

---

# 제10장. Kill Switch Monitoring

# 10.1 목적

```
전략 퇴화 탐지
```

---

# 10.2 발동 조건
| 조건 | 행동 |
| :--- | :--- |
| rolling Sharpe 붕괴 | 경고 |
| whipsaw 폭증 | 점검 |
| 장기 underperform | 중단 검토 |

---

# 10.3 핵심 철학

```
모든 전략은 언젠가 퇴화 가능
```

---

# 제11장. 운영 피로도 Monitoring

# 11.1 매우 중요
개인 시스템 최대 적:

```
운영 피로
```

---

# 11.2 측정 항목
| 항목 | 설명 |
| :--- | :--- |
| 하루 확인 시간 | 측정 |
| 알림 과다 여부 | 측정 |
| 수동 개입 횟수 | 기록 |

---

# 11.3 목표

```
30~60분 내 운영 가능
```
유지.

---

# 제12장. Snapshot Integrity Monitoring

# 12.1 목적

```
데이터 품질 유지
```

---

# 12.2 검증 항목
| 항목 | 행동 |
| :--- | :--- |
| null ratio > 5% | 격리 |
| duplicate 급증 | 경고 |
| missing OHLCV | 폐기 |

---

# 제13장. Weekly Review 시스템

# 13.1 목적

```
주간 전략 상태 점검
```

---

# 13.2 리뷰 항목
| 항목 | 질문 |
| :--- | :--- |
| 손절 증가 | 왜 증가했나 |
| turnover 증가 | 과민반응인가 |
| missed rebound | 너무 늦었나 |
| 집중도 증가 | 위험한가 |

---

# 제14장. Monthly Review 시스템

# 14.1 핵심 목적

```
SPY 대비 가치 검증
```

---

# 14.2 반드시 비교
| 항목 | 비교 대상 |
| :--- | :--- |
| CAGR | 비교 |
| MDD | 비교 |
| Recovery | 비교 |
| Exposure-adjusted return | 비교 |

---

# 14.3 가장 중요한 질문

```
이 복잡성이
정말 Buy & Hold보다 가치 있는가?
```

---

# 제15장. MVP에서 하지 않는 것
초기 MVP 제외:

- AI anomaly detection
- predictive ML monitoring
- reinforcement optimization
- real-time portfolio optimization

---

# {16장}. Monitoring 시스템의 진짜 역할
MRH Monitoring 시스템은:

```
수익률 자랑 시스템
```
이 아니다.

실제 역할은:

```
전략이 실제 운영 환경에서
어떻게 망가지는지
조기에 발견하는 것
```
이다.
