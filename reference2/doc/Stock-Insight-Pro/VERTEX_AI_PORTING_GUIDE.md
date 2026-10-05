# Vertex AI SDK 통합 및 마이클로 서비스 이식 가이드 (Porting Guide)

본 문서는 **Stock Insight Pro**의 핵심 AI 엔진인 'Vertex AI (Gemini 2.0 Flash) 기반 내러티브 퀀트 엔진'을 다른 프로젝트나 새로운 환경에 이식할 때 필요한 기술적 명세와 절차를 다룹니다.

---

## 1. 전제 조건 및 환경 설정

이식하려는 환경에서 다음 패키지가 설치되어 있어야 합니다.

```bash
# 필수 배키지 설치
npm install @google/genai express typescript dot-env
```

`.env` 파일에 다음과 같은 환경 변수가 필요합니다.
- `GEMINI_API_KEY`: Google AI Studio에서 발급받은 API 키.

---

## 2. 핵심 아키텍처: [Macro + Micro] 하이브리드 엔진

이 앱의 차별점은 **단순 주가 분석이 아닌, 거시경제(Macro)와 개별종목(Micro) 데이터를 결합**하여 AI가 해석을 내린다는 점입니다.

### 전송 데이터 스키마 (Payload Schema)
백엔드 `/api/generate-narrative`로 전달되는 데이터 구조는 다음과 같습니다:

```json
{
  "ticker": "AAPL",
  "engineResult": {
    "actionZone": "보수적 관망 (Hold)",
    "penaltyPercent": 25,
    "explanations": [...],  // 결정론적 엔진의 상세 근거
    "primaryState": "BULL",
    "coherence": 0.85
  },
  "macroMetrics": {
    "macroScore": 2.5,
    "instScore": 1.2,
    "rsi": 55,
    "sentiment": 60,
    "yieldSpread": -0.15,
    "hySpread": 3.8
  },
  "portfolio": { ... }, // 사용자 보유 수량 및 단가
  "newsBias": "NEUTRAL",
  "dailyPriceChange": "+1.2%"
}
```

---

## 3. Vertex AI (Gemini) 프롬프트 엔지니어링 전략

이식 시 가장 중요한 부분은 `System Instruction`입니다. 이 앱은 AI의 '환각'을 방지하기 위해 다음 원칙을 준수합니다.

1.  **Strict Output Format**: 반드시 지정된 마크다운 섹션(### 🎯 1단계 ~ 6단계)으로 출력하도록 강제합니다.
2.  **Deterministic First**: AI가 마음대로 판단하기 전에, 이미 계산된 `engineResult`의 수치를 절대적 진실로 받아들이고 이를 '해석'하게 합니다.
3.  **Survival Priority**: "1인용 퀀트 비서"로서 수익보다 MDD(최대 낙폭) 방어를 강조하는 페르소나를 부여합니다.

---

## 4. 백엔드 구현 (Server-side Implementation)

`server.ts` 또는 API 라우터에서 다음과 같이 Vertex AI SDK를 호출합니다.

```typescript
import { GoogleGenerativeAI } from "@google/genai";

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const model = genAI.getGenerativeModel({ 
  model: "gemini-2.0-flash", // 또는 최신 모델
  systemInstruction: "당신은 1인용 퀀트 비서입니다..." 
});

// 주요 로직
const prompt = `
  종목: ${ticker}
  결정론적 엔진 결과: ${JSON.stringify(engineResult)}
  매크로 지표: ${JSON.stringify(macroMetrics)}
  ... (추가 데이터 주입)
`;

const result = await model.generateContent(prompt);
const response = await result.response;
const text = response.text();
```

---

## 5. 프론트엔드 통합 (Frontend Hook)

`useQuantStore.ts`와 같은 전역 상태 관리자에서 다음과 같이 트리거합니다.

1.  `useNarrativeStore.getState().narrativeState.lastInput`에서 공용 매크로 지표를 확보합니다.
2.  분석하려는 종목의 `engineResult`를 준비합니다.
3.  백엔드로 `fetch` 요청을 보냅니다.

---

## 6. 주의 사항 (Best Practices)

-   **API 키 보안**: 절대로 클라이언트 사이드(`VITE_` 접두사 등)에서 API 키를 노출하지 마십시오. 반드시 백엔드 프록시를 통해 호출해야 합니다.
-   **Fallback UI**: AI API 응답이 늦어지거나 실패할 경우를 대비해, 결정론적 엔진 결과(숫자 지표)만이라도 즉시 보여주는 Fallback UI를 반드시 구현하십시오.
-   **Token Limit**: 컨텍스트 윈도우가 충분하더라도, 응답 속도를 위해 불필요한 뉴스 전문 등은 요약해서 전달하십시오.

---

본 가이드는 기술적 최소 요건을 다룹니다. 상세 코드는 `src/server.ts`와 `src/store/useQuantStore.ts`를 참조하십시오.
