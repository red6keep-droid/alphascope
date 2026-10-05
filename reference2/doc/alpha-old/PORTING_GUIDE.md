# 퀀트 촉매 분석 엔진 (Quant Catalyst Engine) 이식 가이드

본 문서는 현재 구축된 "퀀트 촉매 분석 엔진"을 다른 프로젝트나 외부 애플리케이션으로 이식(Porting)하거나 확장할 때 필요한 모든 지식을 망라한 **종합 기술 명세서**입니다. 폴더 구조의 설계 철학부터 핵심 파일의 코드 라인 레벨의 상세한 설명, 그리고 복사해야 할 구성 요소를 빠짐없이 다룹니다.

---

## 1. 시스템 아키텍처 개요

본 애플리케이션은 **React 기반 단일 페이지 애플리케이션(SPA)**과 **Express 기반 백엔드 API 서버**가 결합된 `Full-Stack 하이브리드 아키텍처`로 설계되었습니다.

- **Frontend Environment**: Vite 기반 React, TypeScript, Tailwind CSS v4, Framer Motion (애니메이션)
- **Backend Environment**: Express.js (Node.js), TypeScript
- **AI Engine**: Google Gemini API (@google/genai SDK) - 비정형 데이터(유튜브 자막)에서 정형 데이터(json) 추출용
- **Market Data**: Yahoo Finance API (yahoo-finance2) - 백테스트 및 초과 수익률(Alpha) 산출용
- **Database**: Firebase Firestore - 비동기/배치 분석 결과의 영구 저장, 상태 공유 목적

이 아키텍처의 가장 큰 특징은 **데이터 수집/분석 단계(AI)**와 **시장 성과 검증 단계(Market)**를 완전히 분리한 뒤, UI 단에서 이를 하나의 `Insight`로 합쳐 실시간에 가깝게 사용자에게 보여준다는 점입니다.

---

## 2. 디렉토리 구조 및 설계 철학

프로젝트의 폴더 구조는 각각의 관심사(Concern)를 명확히 분리하여 재사용성과 가독성을 극대화하기 위해 설계되었습니다.

```text
├── server.ts                    # [백엔드] 애플리케이션의 핵심 API 및 정적 서빙 게이트웨이
├── src/
│   ├── App.tsx                  # [프론트엔드] 메인 컨테이너 및 전역 상태(State), 화면 라우팅 관리
│   ├── components/
│   │   └── TickerInsights.tsx   # 특정 티커(종목)의 분석 데이터와 차트를 표현하는 고밀도 UI 컴포넌트
│   ├── engine/
│   │   └── AnalysisEngine.ts    # 프론트엔드와 백엔드를 이어주는 비즈니스 로직(AI 데이터 가공 및 DB 저장)
│   ├── lib/
│   │   ├── firebase.ts          # 데이터베이스 통신 추상화
│   │   └── utils.ts             # Tailwind 클래스 병합 등의 공통 유틸리티 (cn 등)
│   ├── types.ts                 # 전역 TypeScript 타입 정의 (인터페이스, Enum 강제)
│   └── index.css                # 글로벌 스타일 (폰트 및 Tailwind 환경 설정)
└── package.json                 # 패키지 매니저 구성 및 구동 스크립트
```

### 각 폴더의 설계 철학
*   **`server.ts`가 Root에 위치하는 이유**: Vite/SPA의 정적 에셋 서빙과 함께 API 프록시 역할을 동시에 수행하기 위함입니다. 빌드 시 단일 CJS 파일(server.cjs)로 번들링되어 배포 환경에서의 유연성을 확보합니다.
*   **`/src/engine/`의 존재 이유**: 단순 API 호출 로직을 UI 코드(`App.tsx`)에 두지 않고, 비즈니스 흐름(분석 요청 → AI 파싱 → DB 저장 → 실패 시 에러 핸들링 로직)을 독립된 레이어로 분리해 UI 컴포넌트를 가볍게 유지하기 위함입니다.
*   **`/src/components/` (컴포넌트 폴더)**: 시각적 표현에만 집중합니다. 데이터를 어떻게 가져올지는 관여하지 않고(Dumb component), 부모 컨테이너(`App.tsx`)가 넘겨준 `props`를 어떻게 **고밀도(High-Density)** 디자인으로 화면에 예쁘게 그릴지만 고민합니다.

---

## 3. 핵심 모듈별 상세 코드 가이드

이식을 위해서는 아래 설명하는 핵심 모듈의 작동 원리를 반드시 이해해야 합니다.

### 3.1 백엔드 코어 (API 및 AI 프록시): `server.ts`
`server.ts`는 프론트엔드의 비동기 연산 요청을 받아 외부 API를 호출하고 다시 돌려주는 게이트웨이입니다. 보안이 필요한 키(Gemini API 키)는 브라우저에 절대 노출하지 않고 이 파일 안에서만 사용됩니다.

*   **`app.post('/api/analyze')`**: 프론트엔드에서 보낸 텍스트 파일(유튜브 자막 등) 내용을 바탕으로 Gemini 모델에 분석을 요청합니다.
    *   *핵심 원칙*: 내부에 긴 "시스템 프롬프트(System Instruction)"가 존재하며, 이를 통해 AI가 정형화된 JSON만 반환하도록 강제합니다. (5대 택소노미 등). 이식할 때 이 프롬프트를 유지해야 데이터 스키마가 깨지지 않습니다.
*   **`app.post('/api/backtest')`**: 분석 기준일(Event Date)과 티커(Ticker), 벤치마크 인덱스를 받아 야후 파이낸스(Yahoo Finance)에서 과거 데이터를 조회합니다.
    *   *예외 처리*: 해당 종목이 비상장사 이거나, 데이터를 찾을 수 없을 때 (예: "No data found" 에러) 이를 조용히 삼키지 않고, UI에서 사용자가 확인할 수 있도록 `isUnavailable: true` 플래그와 명확한 한글(`시장 데이터 미보유`) 에러 메시지를 반환합니다.

### 3.2 분석 오케스트레이터: `/src/engine/AnalysisEngine.ts`
순수 React 영역과 서버(Backend) 파트를 잇는 다리 역할이며, 모든 분석 파이프라인의 오케스트레이션을 담당합니다.

*   `analyzeMergedText` 함수:
    1.  서버의 `/api/analyze`에 원본 텍스트를 던져 JSON 시그널 배열을 얻습니다.
    2.  유효한 시그널이 없는 영상은 "REJECTED" 상태로 DB에 저장해 재분석을 방지합니다.
    3.  시그널 배열 속 각 항목(Ticker)에 대해 `/api/backtest`를 호출해 금융 성과 데이터를 채웁니다.
    4.  결합된 `Augmented Signal` 데이터를 Firebase DB에 최종 저장합니다.
    5.  앱 내에서 "프로필에 저장되었습니다"라고 알 수 있도록 `saveAnalysisHook`을 호출합니다.

### 3.3 메인 애플리케이션 상태 컨테이너: `/src/App.tsx`
앱 전체의 전역 상태(State), 배치 파이프라인(Batch Pipeline), 탭(Tab) 라우팅을 통합하여 관리하는 대규모 컨테이너입니다.

*   **상태 관리 (`useMemo`, `useState`)**: `allHistory`, `upcomingEvents`, `backtestResults` 등의 상태를 관리하며, Firestore의 실시간 스냅샷 리스너(`onSnapshot`)를 활용해 누군가 백그라운드에서 분석을 완료하면 즉각 프론트엔드 UI에 변경사항이 동기화됩니다.
*   **배치 처리 큐 (`processQueue`)**: 프론트엔드에 있는 기능으로, 사용자가 유튜브 플레이리스트 채널 스크래핑을 요청해 다량의 작업이 들어오면 순차적으로 (비동기 큐잉 형식) 하나씩 API를 찔러 넣는 로직을 담고 있습니다. 중간에 사용자가 다른 탭으로 이동해도 `isBatchProcessing` React Ref를 통해 작업을 끊지 않고 유지합니다.
*   **통합 초과 수익률(Alpha) 계산기**: `performanceSummary` 객체가 모든 시그널들의 알파 값을 모아서 산술 평균을 계산하는 로직을 가집니다. 앱 하단의 "엔진 가동 (필터후 초과 수익률)" 부분입니다.

### 3.4 데이터 시각화 및 밀집 카드: `/src/components/TickerInsights.tsx`
`App.tsx`에서 넘겨준 개별 종목 데이터 `item`을 렌더링하는 시각 중심 파일입니다.

*   **도표 라이브러리 사용도**: `recharts` 라이브러리를 활용해 주가의 궤적과 상승/하락 폭을 그립니다.
*   **디자인 구현**: Tailwind CSS를 사용해 공간 낭비가 없는 "High-Density(고밀도)" UI를 그립니다. `grid`와 `col-span`을 활용하여 모바일 화면에서도 모든 지표가 직관적으로 보이게 설계되었습니다. 알파(Alpha) 값의 양/음에 따라 정확하게 한국 시장 표준 색상(상승 = Red, 하락 = Blue)을 적용하는 코드가 들어있습니다.

---

## 4. 디자인 및 UI 철학 (Korean-First & High-Density)

이식하거나 확장할 때 코딩 스타일이나 디자인이 깨지지 않도록 아래의 철학을 엄수해야 합니다.

1.  **용어 통일 (No English)**:
    - 영문 데이터가 오더라도 UI 에서는 한글로 번역하여 사용합니다. (Alpha → 초과 수익률, Ticker → 종목 코드 / 종목, Sentiment → 시장 심리, Bullish/Bearish → 상승/하락)
2.  **색상 체계 (Standardized)**:
    - **상승(Bullish)**: 북미의 그린/레드 방식이 아닌 한국의 **빨간색(Red 계열, `text-red-500`)**을 사용합니다.
    - **하락(Bearish)**: 한국의 **파란색(Blue 계열, `text-blue-500`)**을 사용합니다.
    - **액센트(UI 포인트)**: 오렌지색(`text-orange-500`)을 사용하여 전문적이고 따뜻한 느낌을 제공합니다.
3.  **고밀도 레이아웃**:
    - 라운드 카드 디자인에서 내부 `padding`은 최소한으로 잡으며, 요소 간의 공백(margin)을 줄입니다.
    - 여러 정보는 여러 줄(Row)이 아닌 세로 구분선(`divide-x`)을 둔 가로 한 줄(Inline)로 구성하여 화면 스크롤 피로도를 줄여야 합니다.

---

## 5. 필수 환경 변수 및 설정 (.env)

이식 시 새 프로젝트의 루트에 아래의 환경 변수들을 반드시 셋업해야 합니다. 이 환경변수가 없으면 서버 기동 중 오류가 발생합니다.

```env
# AI 엔진 (Google Gemini - 백엔드에서만 사용)
GEMINI_API_KEY=your_gemini_api_key

# Database (Firebase - 프론트엔드가 DB에 직접 붙을 때 사용)
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...
VITE_FIREBASE_PROJECT_ID=...
VITE_FIREBASE_STORAGE_BUCKET=...
VITE_FIREBASE_MESSAGING_SENDER_ID=...
VITE_FIREBASE_APP_ID=...
```

---

## 6. 이식 수행 가이드 (Step-by-step)

1.  **초기 세팅**: 타겟 애플리케이션의 뼈대를 Vite (React-TS) + Express 로 구축합니다.
2.  **패키지 설치**: `package.json` 코어 의존성을 설치합니다.
    *   `npm install @google/genai firebase yahoo-finance2 express typescript` (백엔드 성격)
    *   `npm install recharts lucide-react motion` (프론트엔드 성격)
3.  **Config 파일 복사**: 프로젝트 루트 디렉토리에 있는 `tsconfig.json`, `vite.config.ts`, `tailwind.config.js`(또는 index.css 내 @theme)를 이관합니다.
4.  **파일 복사 순서**:
    *   1순위) `server.ts` : API를 먼저 안정적으로 띄우는 것이 먼저입니다.
    *   2순위) `src/types.ts` 및 `src/lib/firebase.ts` : 데이터의 형태를 맞춥니다.
    *   3순위) `src/engine/AnalysisEngine.ts` : 비즈니스 로직을 이관합니다.
    *   4순위) `src/components/TickerInsights.tsx`, `src/App.tsx` : 마지막으로 UI를 덮어씌웁니다.
5.  **테스트**: `npm run dev` 스크립트를 통해 `server.ts`가 3000포트에서 Vite Middleware와 함께 띄워지는지 확인하고 에러 로그가 없는지 점검합니다.

이 가이드를 철저히 따른다면 어떠한 Node.js 컨테이너 환경에서도 기존 퀀트 촉매 분석 엔진을 100% 동일한 컨디션으로 이식할 수 있습니다. 추가적인 문의는 `SYSTEM_DESIGN.md` 문서를 병행 참조하십시오.
