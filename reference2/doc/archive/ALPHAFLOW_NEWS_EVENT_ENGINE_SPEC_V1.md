# AlphaFlow News Event Engine 명세서 (Event Intelligence Specification)

| 버전 | 날짜 | 작성자 | 주요 내용 |
| :--- | :--- | :--- | :--- |
| V1.0 | 2026-06-01 | GitHub Copilot | 뉴스-이벤트 변환 엔진 설계 및 8대 이벤트 카테고리 정의 |
| V1.1 | 2026-06-01 | GitHub Copilot | 비용 최적화 배치 분류(Batch Sifting) 레이어 및 모델 강제 규정 추가 |
| **V1.2** | **2026-06-01** | **GitHub Copilot** | **데이터 영속성 전략 수립 및 데이터 오염 방지(Anti-Contamination) 로직 추가** |

---

## 1. 엔진 철학: "뉴스에서 이벤트로(News to Event)"
본 엔진은 단순한 뉴스 수집기가 아니다. 뉴스를 읽는 시스템이 아닌, **뉴스를 투자 의사결정이 가능한 '투자 이벤트(Investment Event)'로 변환**하는 지능형 레이어다.

### 1.1 AI 모델 엔진 규정 (Mandatory)
*   **사용 금지**: `gemini-1.5-flash` (구형 엔진으로 퀀트 분석 정확도 저하)
*   **표준 모델**: `gemini-3.1-flash-lite` (최신 3.1 엔진 사용 필수)

---

## 2. 데이터 수집 레이어 (Acquisition Layer)
... (기존 내용 유지)

---

## 2.5 배치 분류 레이어 (Layer 1.5: Batch Sifting) - *Cost Optimized*
무료 플랜의 API 호출 제한(RPD 1,500회)을 극복하고 하루 수만 건의 뉴스를 처리하기 위한 핵심 전략이다.
*   **동작**: 뉴스 제목 50~100개를 하나의 리스트로 묶어 AI에게 전송.
*   **필터링**: AI는 리스트 중 '8대 이벤트'에 해당하는 뉴스 번호와 카테고리만 1차 선별.
*   **효율성**: API 호출 횟수를 최대 99% 절감하여 대량의 데이터 처리 가능.

---

## 3. 이벤트 추출 엔진 (Event Extraction Engine)
... (기존 내용 유지)

### Tier A: 실시간 시장 뉴스
*   **소스**: Yahoo Finance, MarketWatch, Benzinga, Investing.com
*   **항목**: 제목, 본문, 발행 시간, 출처, URL, 관련 티커

### Tier B: SEC 공식 공시 (The Fact)
*   **소스**: SEC EDGAR (RSS/API)
*   **핵심 서식**: 
    *   **8-K**: 주요 기업 이벤트 (계약, 경영진 교체 등)
    *   **Form 4**: 내부자/CEO 매수 및 매도
    *   **10-Q/K**: 분기/연간 실적 보고서

### Tier C: 보도자료 (PR News)
*   **소스**: Business Wire, GlobeNewswire, PR Newswire
*   **핵심 이벤트**: 신규 수주, 전략적 파트너십, M&A

---

## 3. 이벤트 추출 엔진 (Event Extraction Engine)
수집된 뉴스를 다음 **8대 핵심 카테고리**로 분류하고 정형화된 데이터로 출력한다.

| 카테고리 | 이벤트 타입 (Event Type) | 설명 |
| :--- | :--- | :--- |
| **1. EARNINGS** | BEAT, MISS, GUIDANCE_UP/DOWN | 실적 발표 및 향후 전망치 조정 |
| **2. ANALYST** | TARGET_UP/DOWN, RATING_UP/DOWN | IB의 목표가 및 투자의견 변경 |
| **3. BUSINESS** | NEW_CONTRACT, PARTNERSHIP, PRODUCT_LAUNCH | 사업 확장, 신규 수주, 제품 출시 |
| **4. INSIDER** | CEO_BUY, INSIDER_BUY/SELL | 내부자 매수/매매 (SEC Form 4 기반) |
| **5. CAPITAL** | BUYBACK, OFFERING, CAPITAL_RAISE | 자사주 매입, 유상증자, 자금 조달 |
| **6. REGULATION** | FDA_APPROVAL, ANTITRUST, EXPORT_RESTRICTION | 규제 승인, 반독점 조사, 수출 제한 |
| **7. MACRO** | RATE_CUT/HIKE, CPI, PPI, NFP | 거시 지표 및 금리 결정 (섹터 영향 분석) |
| **8. THEME** | AI, NUCLEAR, DEFENSE, ROBOTICS | 특정 테마 내러티브 강화 (섹터 순환매 탐지) |

---

## 4. 데이터 저장 전략 및 영속성 (Data Persistence Strategy)

### 4.1 데이터 생애 주기 (Data Life-cycle)
시스템 부하 및 비용 최적화를 위해 데이터를 단계별로 관리한다.
1.  **Raw Headlines (휘발성)**: 수집된 수만 건의 뉴스 제목은 저장하지 않고 메모리(또는 캐시) 상에서 배치 분류(Sifting) 후 즉시 파기한다.
2.  **Selected Events (영구적)**: AI가 선별한 상위 1%의 핵심 투자 이벤트만 **Firestore(DB)에 영구 저장**한다.
3.  **Performance Logs (업데이트)**: 저장된 이벤트에 대해 T+1~T+60일간의 수익률 데이터를 매일 누적 업데이트한다.

### 4.2 NEWS_EVENT 테이블 (영구 저장 대상)
```json
{
  "ticker": "NVDA",
  "event_type": "PARTNERSHIP_EXPANSION",
  "impact_score": 92,
  "impact_reason": "MSFT와의 대규모 인프라 공급 계약, 가이던스 상향 가능성 농후",
  "theme": "AI",
  "sentiment": "POSITIVE",
  "strength": "HIGH",
  "source": "Yahoo Finance",
  "published_at": "2026-06-01T09:00:00Z",
  "primary_entity": "NVDA",
  "secondary_entities": ["ORCL"]
}
```

---

## 5. Impact Score 측정 기준 (Quantitative Energy)
이벤트의 실제 파급력을 0~100점 사이의 정량적 수치로 산출한다.

1.  **계약/시장 규모 (40%)**: 계약 금액의 절대 액수 및 시장 점유율 변화 폭.
2.  **상대 기업 규모 (30%)**: 파트너사 또는 경쟁사의 위상 (Tier 1 빅테크 vs 일반 기업).
3.  **재무 실질 영향 (20%)**: 매출 비중 변화 및 가이던스 수정 가능성.
4.  **내러티브 독점성 (10%)**: 해당 테마 내에서의 희소성 및 최초 보도 여부.

---

## 6. 데이터 무결성 및 오염 방지 (Data Integrity & Anti-Noise)
뉴스 데이터의 오염(가짜 뉴스, 클릭베이트, 중복 기사)을 방지하기 위해 3단계 검증 시스템을 적용한다.

### 6.1 출처 신뢰도 가중치 (Source Weighting)
*   **Level 1 (Highest)**: SEC 공식 공시 (8-K, Form 4 등). 조작 불가능한 'Fact'로 간주.
*   **Level 2 (High)**: 주요 경제 언론사 (Bloomberg, Reuters, CNBC, WSJ).
*   **Level 3 (Normal)**: 일반 금융 뉴스 및 보도자료 사이트.

### 6.2 교차 검증 (Consensus Validation)
*   동일한 이벤트가 서로 다른 독립된 출처(예: Reuters와 Yahoo Finance)에서 동시 보도될 경우 해당 이벤트의 신뢰 점수를 가산한다.
*   단일 출처의 자극적인 헤드라인은 '이벤트 추출 엔진'에서 'STRENGTH: LOW'로 분류하거나 기각한다.

### 6.3 가격 행동 확인 (Price-Action Sanity Check)
*   **필터**: "역대급 호재"라는 뉴스가 떴으나, 시장의 가격과 거래량(MRH 지표)이 전혀 반응하지 않는다면 '오염된 데이터' 또는 '시장 무시 재료'로 판단하여 `WARNING` 상태를 부여한다.
*   즉, 뉴스(내러티브)와 가격(실체)의 괴리(Divergence)를 상시 감시한다.

---

## 7. 지능형 로직 (Intelligence Layer)

### 7.1 Reconfirmation (보유 연장)
이미 보유 중인 종목에 대해 새로운 'POSITIVE' 카테고리 이벤트가 발생할 경우, 기존 모멘텀의 수명이 연장된 것으로 간주하고 상태를 `RECONFIRMED`로 격상한다.

### 7.2 Risk Engine (상시 경고)
`REGULATION_REJECTION`, `CEO_RESIGNATION`, `GUIDANCE_DOWN` 등 고위험 이벤트 발생 시 즉시 `WARNING` 신호를 발생시키고 청산 검토 단계로 진입시킨다.

### 7.3 MRH 결합 (Confirmation)
*   **AlphaFlow**: "PARTNERSHIP (POSITIVE)" 감지
*   **MRH**: "거래량 폭증 + RS 상향 + 전고점 돌파" 확인
*   **결과**: 최종 `CONFIRMED` 신호 생성

---

## 8. 구현 로드맵
1.  **Phase 1**: Yahoo Finance & SEC RSS 수집기 구현
2.  **Phase 2**: LLM 기반 이벤트 추출기(Layer 2) 프롬프트 고도화
3.  **Phase 3**: 데이터베이스 `NewsEvent` 스키마 확장 및 분석 결과 연결
