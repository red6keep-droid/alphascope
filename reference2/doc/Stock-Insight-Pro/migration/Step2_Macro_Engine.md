# Phase 2: Macro Economy Engine

시장 국면(Regime)을 판단하는 거시경제 엔진을 이식합니다. 이 엔진은 앱의 '눈' 역할을 합니다.

## 1. 데이터 수집 API 이식
- **파일**: `src/api/fred.ts`
- **로직**: FRED(Federal Reserve Economic Data)에서 다음 지표를 가져오는 함수를 이식합니다.
  - `T10Y2Y` (10년-2년 장단기 금리차)
  - `UNRATE` (실업률)
  - `CPIAUCSNS` (소비자 물가지수)

## 2. 매크로 서비스 로직
- **파일**: `src/services/fredService.ts`
- **핵심 알고리즘**:
  - 수집된 지표를 기반으로 `calculateMacroScore()` 수행.
  - 점수에 따라 `NORMAL`, `VOLATILE`, `PANIC_SELL` 등의 국면을 리턴.

## 3. 상태 저장소 연결
- **파일**: `src/store/useQuantStore.ts` 내 매크로 관련 부분.
- 수집된 매크로 데이터를 전역 상태에 저장하여 UI와 다른 엔진에서 참조할 수 있게 합니다.

## ✅ 검증 포인트
1. FRED API 호출 시 최신 경제 지표가 JSON 형태로 정상 수신되는가?
2. 현재 금리차(Inversion 여부)에 따라 매크로 점수가 의도한 대로 계산되는가?
3. 콘솔에 출력되는 `Regime` 값이 기존 앱의 진단과 일치하는가?

---
*다음 단계: [Step3_Portfolio_Data.md](Step3_Portfolio_Data.md)*
