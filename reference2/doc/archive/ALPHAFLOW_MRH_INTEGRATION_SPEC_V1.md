# AlphaFlow + MRH 통합 시스템 명세서 (Integration Specification)

| 버전 | 날짜 | 작성자 | 주요 내용 |
| :--- | :--- | :--- | :--- |
| V1.0 | 2026-06-01 | GitHub Copilot | 초기 통합 아키텍처 및 4계층 레이어 설계 수립 |
| V1.1 | 2026-06-01 | GitHub Copilot | 멀티 소스 Discovery 및 소스별 가변 가중치(Adaptive Scoring) 도입 |
| V1.2 | 2026-06-01 | GitHub Copilot | 시스템 철학 전면 개편: 점수 중심에서 지속성 관찰 중심으로 전환 |
| V1.3 | 2026-06-01 | GitHub Copilot | Discovery Layer 추가, RECONFIRMED 상태 도입 및 지속성 측정 지표 구체화 |
| V1.4 | 2026-06-01 | GitHub Copilot | 공신력 있는 뉴스 소스(Authoritative News)를 Discovery 메인 소스로 강화 |
| V1.5 | 2026-06-01 | GitHub Copilot | 비용 효율적 데이터 소스(SEC EDGAR, Yahoo News 등) 최적화 및 단계별 확장 전략 수립 |
| **V1.6** | **2026-06-01** | **GitHub Copilot** | **AI 모델 강제 규정: gemini-1.5-flash 사용 금지 및 gemini-3.1-flash-lite 도입** |

---

## 1. 시스템 정체성: "상승 에너지 추적 시스템"
본 시스템은 미래 가격을 예측하지 않는다. 우리는 종목을 예측하는 것이 아니라, 시장에 이미 발생한 **상승 에너지의 생성, 강화, 유지, 약화, 소멸 과정**을 정밀하게 추적한다.

---

## 1.1 AI 모델 엔진 규정 (Mandatory)
본 시스템의 안정적인 분석 성능을 위해 다음과 같은 모델 사용 규칙을 강제한다.
*   **사용 금지 모델**: `gemini-1.5-flash` (구형 버전으로 인해 최신 퀀트 시그널 분석 부적합)
*   **표준 모델**: `gemini-3.1-flash-lite` (최신 3.1 엔진의 추론 능력과 속도 활용)
*   **요구 사항**: 해당 모델 사용을 위해 `@google/genai` SDK를 **버전 2.0.0 이상**으로 업데이트해야 한다.

---

## 2. 5계층 통합 아키텍처 (Revised Energy Layer)

### Layer 0: Discovery Layer (Multi-Source & Cost-Efficient)
수천 개의 종목 중 유망 후보를 수집하는 '공급망' 역할을 수행한다. 초기 구축 단계(V1)에서는 비용 효율성을 극대화하기 위해 **공개 데이터 및 우회 피드**를 적극 활용한다.

*   **Source A (SEC EDGAR - Core)**: 미국 증권거래위원회(SEC) 공식 공시. 8-K(중요 이벤트), 10-Q/K(실적), Form 4(내부자 매수) 등 가장 강력한 '팩트' 데이터 소스.
*   **Source B (Open News Feed)**: Yahoo Finance News(Reuters/AP 전재), MarketWatch, Investing.com, Benzinga 무료 피드 등을 통한 실시간 호재 감지.
*   **Source C (Narrative - Video/SNS)**: 유튜브(당잠사, CNBC 등) 자막 및 Reddit(API/RSS)을 통한 내러티브 확산도 및 시장 분위기 분석.
*   **Source D (Market Scanners)**: Finviz, TradingView, Yahoo Screener 등을 활용한 가격 돌파, 거래량 급증 종목 자동 수집.
*   **Source E (Analyst Sentiment)**: MarketBeat, Yahoo Finance 등을 통한 애널리스트 등급 변경(Upgrade) 및 목표주가 상향 정보 수집.

### Layer 1: AlphaFlow (Narrative Monitor)
*   **역할**: 호재/악재의 발생 및 내러티브의 질적 변화 감지
*   **핵심 질문**: "상승의 '이유'가 여전히 유효한가? 공신력 있는 매체나 SEC 공시에서 새로운 강력한 호재가 추가되었는가?"

### Layer 2: MRH (Price Action Monitor)
*   **역할**: 가격 행동을 통한 에너지 실체 증명
*   **핵심 질문**: "뉴스 보도 후 시장의 돈이 실제로 유입되고 있는가? 가격이 전고점을 뚫고 유지되는가?"

### Layer 3: Confirmation Engine (에너지 상태 판독기)
점수(Score)보다 **확인된 에너지 상태(Energy Status)**를 우선한다.

| 상태 (Status) | 판단 근거 | 전략적 권고 |
| :--- | :--- | :--- |
| **NEW** | 어느 한쪽 소스에서 초기 탐지됨 | **관찰 시작 / 유니버스 등록** |
| **CONFIRMED** | AlphaFlow(호재) + MRH(강세) 이중 확인 완료 | **신규 진입 권장** |
| **RECONFIRMED** | 기존 상승 중 추가 호재 발생 + 거래량 재폭발 | **보유 연장 / 불타기(Add-on)** |
| **WARNING** | 한쪽 엔진의 이탈 감지 (예: 뉴스는 좋으나 거래량 급감) | **부분 청산 / 리스크 관리** |
| **EXHAUSTED** | 양쪽 엔진 모두 에너지 소멸 감지 | **전량 청산 (Exit)** |

### Layer 4: Persistence Timeline (이벤트 타임라인)
종목의 생애 주기를 시각화하고 모든 이벤트를 시간축으로 기록한다.
*   **예시 (NVDA)**:
    *   `T+0`: AI 투자 확대 뉴스 발생 (**NEW**)
    *   `T+2`: 52주 신고가 돌파 및 거래량 증가 (**CONFIRMED**)
    *   `T+5`: 기관 목표가 대폭 상향 (**RECONFIRMED**)
    *   `T+12`: 거래량 소폭 감소 감지 (**KEEP HOLD**)
    *   `T+18`: 실적 발표 후 재료 소멸 뉴스 (**WARNING**)
    *   `T+20`: 주요 이평선 이탈 (**EXHAUSTED**)

---

## 3. 지속성 측정 공식 (Persistence Metrics)

### 3.1 AlphaFlow 지속성 (질적 지표)
1.  **News Frequency**: 특정 테마/종목의 언급 빈도 유지 여부
2.  **SEC Event Integrity**: 8-K 등 중요 공시 후 후속 보도 및 시장 반응 지속 여부
3.  **Authority Weight**: 대형 기관 리포트 발행 및 SEC Form 4(내부자 매수) 발생 여부
4.  **Narrative Diffusion**: 유튜브/Reddit 등 SNS에서 내러티브가 대중에게 확산되는 속도

### 3.2 MRH 지속성 (양적 지표)
... (기존 내용 유지)

---

## 4. 포지션 관리 엔진 (Energy-Based Execution)
... (기존 내용 유지)

---

## 5. 단계별 데이터 확장 전략 (Phased Expansion)
AlphaFlow는 데이터 비용과 품질의 균형을 위해 2단계로 나누어 확장한다.

### Phase 1: 기반 구축 (Cost-Efficient)
*   **목표**: 최소 비용으로 AlphaFlow의 핵심 로직 검증 및 80% 이상의 성과 달성
*   **데이터 소스**: SEC EDGAR, Yahoo Finance News, Finviz, YouTube, Reddit RSS
*   **강점**: 사실상 무료로 운영 가능하며, SEC 공시라는 강력한 팩트 기반 데이터 확보 가능

### Phase 2: 고도화 (Institutional Pro)
*   **목표**: 정보의 속도(Latency)와 정밀도를 기관급으로 격상
*   **데이터 소스**: Reuters/Bloomberg 전용 피드, Benzinga Pro API, Polygon.io News API 등
*   **강점**: 뉴스 발생 후 수 초 내 분석 가능, 고해상도 애널리스트 원문 데이터 확보

---

## 6. 시스템의 철학적 기반
... (기존 내용 유지)
