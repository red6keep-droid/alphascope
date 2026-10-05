# Phase 1: Infrastructure & Project Setup

이 단계에서는 새 앱의 뼈대와 환경 설정을 구성합니다.

## 1. 의존성 패키지 설치
`package.json`을 참조하여 다음 핵심 라이브러리들을 설치합니다.
```bash
# 핵심 통신 및 상태 관리
npm install axios zustand @google/generative-ai firebase

# 기술 지표 및 데이터 처리
npm install technicalindicators yahoo-finance2 date-fns

# UI 프레임워크 (선택 사항)
npm install lucide-react tailwind-merge clsx
```

## 2. 환경 변수 설정 (.env)
루트 폴더에 `.env` 파일을 생성하고 다음 항목을 기입합니다.
- `VITE_KIS_CANOE_KEY`: 한국투자증권 API Key
- `VITE_KIS_CANOE_SECRET`: 한국투자증권 Secret
- `VITE_FRED_API_KEY`: FRED 경제 데이터 API Key
- `VITE_GEMINI_API_KEY`: Google Gemini API Key
- `VITE_TWELVE_DATA_KEY`: Twelve Data API Key (해외 시세용)

## 3. 폴더 구조 생성
`src/` 하위에 다음 구조를 미리 생성합니다.
- `src/api/`: 외부 통신 모듈
- `src/engine/`: 핵심 계산 알고리즘
- `src/services/`: 비즈니스 로직 처리
- `src/store/`: 상태 관리 (Zustand)
- `src/types/`: TypeScript 타입 정의

## 4. 공통 타입 및 유틸리티 이식
- **파일**: [src/types/types.ts](../src/types/types.ts) (경로 확인 필요)
- **내용**: `Stock`, `MacroData`, `RiskReport`, `Regime` 등의 전역 인터페이스를 가장 먼저 복사합니다.

## ✅ 검증 포인트
1. `npm run dev` 실행 시 에러 없이 빈 화면이 나오는가?
2. `.env` 파일의 변수들이 `import.meta.env`를 통해 정상적으로 읽히는가?
3. `types.ts` 복사 후 타입 에러가 발생하지 않는가?

---
*다음 단계: [Step2_Macro_Engine.md](Step2_Macro_Engine.md)*
