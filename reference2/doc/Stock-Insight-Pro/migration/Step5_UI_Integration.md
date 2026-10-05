# Phase 5: UI Integration & Final QA

모든 로직을 화면에 연결하고 최종적으로 점검하는 단계입니다.

## 1. UI 컴포넌트 이식
- **경로**: `src/components/`
- **핵심 컴포넌트**:
  - `MacroDashboard`: 현재 시장 국면을 시각화.
  - `StockList`: 보유 종목과 리스크 상태 표시.
  - `AINarrativeCard`: AI가 생성한 행동 지침 리포트 표시.
  - `RiskControlPanel`: 매매 버튼 활성/비활성 상태 제어.

## 2. 테마 및 인터랙션
- 국면에 따른 테마 색상 변경 (예: 위험 시 Dark/Red 테마).
- 로딩 상태(Skeleton UI) 처리.

## 3. 최종 통합 테스트 (QA)
- 전체 시나리오 테스트:
  1. 앱 실행 시 FRED 데이터 로드 확인.
  2. KIS 계좌 정보 로드 확인.
  3. 리스크 엔진 작동 및 AI 리포트 생성 확인.
  4. 최종 매매 지침의 수치가 논리적으로 타당한지 확인.

## 4. 배포 준비
- `npm run build`를 통한 빌드 무결성 확인.
- Firebase Hosting 또는 Vercel 설정 파일 확인.

## ✅ 최종 검증
1. 콘솔에 에러나 경고(Warning)가 없는가?
2. 기존 앱과 비교했을 때 분석 결과가 95% 이상 일치하는가?
3. "수면 보장" 철학에 맞게 지침이 직관적인가?

---
*축하합니다! 이식이 완료되었습니다.*
# Phase 4: Risk Control & AI Narrative

앱의 두뇌이자 가장 중요한 '리스크 관리' 및 'AI 리포트' 기능을 이식합니다.

## 1. 리스크 엔진 (Risk Engine)
- **파일**: `src/engine/riskEngine.ts`, `src/engine/stockRiskEngine.ts`
- **핵심 로직**:
  - **Trade Allowed**: 시장 국면이 `PANIC_SELL`이거나 변동성이 극심할 때 `tradeAllowed = false`를 강제하여 뇌동매매를 차단합니다.
  - **ATR 기반 손절선**: 각 종목의 변동성(ATR)을 계산하여 수학적인 익절/손절 가이드를 산출합니다.

## 2. AI 나러티브 엔진
- **파일**: `src/engine/aiNarrativeEngine.ts`, `src/services/aiService.ts`
- **프롬프트 엔지니어링**:
  - 국면별(Regime)로 AI가 출력해야 할 내용을 강제하는 프롬프트 템플릿을 이식합니다.
  - 예: `PANIC_SELL` 시 "관망하라"는 지시를 우선적으로 생성.
- **Gemini SDK 연동**: 수집된 수치 데이터를 프롬프트에 주입하여 최종 리포트를 생성합니다.

## 3. 결정론적 지침 생성
- AI의 답변이 오더라도, 최종 UI에는 "예약 주문 가격"과 같은 수치 데이터가 함께 표시되도록 로직을 결합합니다.

## ✅ 검증 포인트
1. 특정 종목의 리스크 점수가 계산되어 나오는가?
2. 위험 장세에서 "매수 권장하지 않음" 메시지가 명확히 출력되는가?
3. AI 리포트가 현재 시장 데이터(금리, 지수 등)를 정확히 반영하여 생성되는가?

---
*다음 단계: [Step5_UI_Integration.md](Step5_UI_Integration.md)*
