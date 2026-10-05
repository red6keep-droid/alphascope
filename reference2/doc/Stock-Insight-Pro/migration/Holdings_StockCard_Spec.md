# 상세 정보 명세: 보유자산 종목 카드 (Stock Card)

이 문서는 홈 화면의 '보유자산' 탭에서 각 종목을 나타내는 **InsightCard (종목 카드)** 컴포넌트의 상세 구성과 로직을 설명합니다.

## 1. 개요
종목 카드는 단순히 가격을 보여주는 것을 넘어, **거시경제(Macro), 기술적 지표(Technical), 리스크 엔진(V3 Risk)**의 데이터를 통합하여 사용자에게 즉각적인 "행동 지표(Actionable Orders)"를 제공하는 핵심 UI 유닛입니다. 또한, 보유 중인 자산의 리스트를 관리하고 평단가/수량을 입력하여 수익률을 추적하는 기능을 포함합니다.

## 2. 자산 관리 프로세스 (Add & Manage)

### A. 종목 리스트 관리 (Stock Management Modal)
- **진입 경로**: 홈 화면 우측 상단의 'Settings' 아이콘 또는 '자산입력' 모달 내의 '+' 버튼.
- **주요 기능**:
  - **종목 추가**: 티커(Ticker)를 입력하여 `myStocks` 리스트에 새 종목 추가 (`resolveTicker`를 통해 유효성 검증).
  - **종목 삭제**: `Trash2` 아이콘을 클릭하여 리스트에서 제거.
  - **순서 변경**: `ChevronUp/Down` 버튼으로 종목의 노출 순서 조정.
  - **관심 종목 이동**: `ArrowRightLeft` 버튼으로 '보유자산'과 '관심자산' 간의 빠른 이동.

### B. 상세 자산 데이터 입력 (Portfolio Entry Modal)
- **진입 경로**: 홈 화면의 '자산입력' 버튼.
- **주요 기능**:
  - **평균 단가 입력**: 해당 종목의 매수 평균 가격($) 설정.
  - **보유 수량 입력**: 현재 보유 중인 주식 수(주) 설정.
  - **실시간 수익률 계산**: `(현재가 - 평단가) / 평단가` 로직에 따라 실시간 ROI 및 평가 손익 표시.
  - **데이터 영속성**: 입력된 데이터는 `usePortfolioStore.ts`를 통해 로컬 스토리지 또는 Firebase에 동기화됨.

## 3. 카드 구성 요소 (상세)

### A. 헤더 (Header)
- **로고 및 티커**: 종목 심볼과 TickerLogo.
- **실시간 가격**: 현재가 및 전일 대비 변동률(%).
- **상태 태그**: `NORMAL`, `VOLATILE`, `PANIC_SELL` 등 현재 시장 국면 표시.

### B. 내 자산 정보 (My Portfolio Info)
- **평균 단가 (Avg Price)**: 내가 매수한 평균 가격.
- **보유 수량 (Quantity)**: 현재 보유 중인 주식 수.
- **수익률 (P/L %)**: `(현재가 - 평균단가) / 평균단가 * 100`.
- **평가 손익**: 실제 통화 단위의 손익 금액.
- **편집 기능**: '자산입력' 버튼을 통해 평균 단가와 수량을 직접 수정 가능.

### C. 전략 선택기 (Strategy Selector)
- **전략 모드**: 
  - `LONG_TERM`: 우량주 장기 홀딩 전략 (낮은 매매 빈도).
  - `SWING`: 단기 추세 스윙 전략 (기술적 지표 중심).
- **영향**: 선택된 전략에 따라 하단의 AI 지침과 리스크 가이드(손절선 등)가 달라집니다.

### D. 기술적 상태 태그 (Technical Tags)
- 7가지 핵심 지표의 상태를 시각화:
  - **추세**: 상승, 하락, 횡보.
  - **모멘텀**: 강함, 약함 (MACD 기반).
  - **과열도**: 과매수, 과매도 (RSI 기반).
  - **시장 힘**: 강세, 약세 (ADX 기반).
  - **변동성**: 확장, 수축 (BB Width 기반).

### E. AI 핵심 브리핑 (AI Narrative)
- **결정론적 요약**: 현재 수치(RSI, 가격 등)를 기반으로 한 핵심 진단.
- **예약 행동 지침**: "자기 전 $XX 가격에 매수 예약", "현재는 관망" 등의 구체적 지시 사항.

### F. 리스크 엔진 V3 결과 (Decision Layer)
- **권장 행동**: `BUY`, `HOLD`, `SELL`, `AVOID(리스크필터)`.
- **리스크 등급**: `초고위험`, `주의`, `안전` 등의 라벨링.
- **손절가(SL) / 목표가(TP)**: 변동성(ATR)을 반영한 수학적 가격 제안.

### G. 백테스트 지표 (Historical Backtest)
- 해당 종목과 선택한 전략의 **과거 승률(Win Rate)** 및 **연평균 수익률(CAGR)** 표시.

## 4. 핵심 로직: Decision Layer (의사결정 레이어)
카드의 최종 권장 행동(`action`)은 다음 우선순위로 결정됩니다:
1. **Trade Allowed 체크**: 시장 전체가 `PANIC_SELL`이거나 리스크 시스템이 거래를 차단하면 무조건 `AVOID`.
2. **V3 Risk Engine**: 개별 종목의 변동성이 임계치를 넘으면 `AVOID` 또는 `HOLD`로 강제 고정.
3. **Multi-Factor Model**: 재무 점수(Fundamental) + 기술 점수(Technical) + 뉴스 심리(Sentiment)를 결합하여 최종 점수 산출.

## 5. 사용자 인터랙션
- **클릭 시 확장**: 카드를 클릭하면 상세 차트 및 더 깊은 분석 내용이 펼쳐짐.
- **분석 버튼**: 클릭 시 상세 '분석 페이지'로 이동하여 캔들 차트와 재무 제표 확인 가능.
- **즐겨찾기/삭제**: 관심 종목 등록 또는 보유 자산 리스트에서 제거.

## 6. 관련 폴더 및 파일 구조

이식 작업 시 다음 구조를 참고하여 관련 파일을 구성합니다.

```text
src/
├── api/
│   ├── kis.ts                # 한국투자증권 API (계좌 조회, 시세 데이터)
│   └── twelveData.ts         # 해외 종목 실시간 시세 데이터
├── components/
│   ├── InsightCard.tsx       # [핵심] 홈 화면의 개별 종목 카드 컴포넌트
│   ├── modals/
│   │   └── PortfolioEntryModal.tsx  # 평단가, 수량 입력 및 수익률 계산 모달
│   └── SharedComponents.tsx  # TickerLogo 등 공통 UI 요소
├── engine/
│   ├── riskEngine.ts         # 전체 시장 국면(Regime) 관리 엔진
│   └── stockRiskEngine.ts    # 개별 종목의 리스크 및 손절선 계산 엔진
├── store/
│   ├── usePortfolioStore.ts  # [중요] 사용자의 자산 데이터 저장소
│   └── useQuantStore.ts      # 전체 앱의 퀀트 상태 및 종목 리스트 관리
└── types/
    └── types.ts              # StockInsight, PortfolioData 등 공통 타입 정의
```

---
*참조 파일*: [src/components/InsightCard.tsx](../../src/components/InsightCard.tsx), [src/engine/stockRiskEngine.ts](../../src/engine/stockRiskEngine.ts)
