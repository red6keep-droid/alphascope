# 미국/한국 시장 서사 분석기 이식 가이드 (Migration Guide)

본 문서는 현재 구축된 "데이터 파이프라인 (Firebase Storage) + AI 추출 엔진 (Gemini) + 퀀트 백테스트 (yfinance) + 시각화 대시보드 (React)" 시스템을 다른 애플리케이션이나 프로젝트로 이식하기 위한 통합 가이드입니다.

---

## 1. 시스템 개요 및 아키텍처

본 시스템은 월스트리트 헤지펀드의 데이터 추출 방식을 모티브로 하여, 금융 미디어(유튜브 자막 등)의 텍스트 데이터를 분석하고 시장의 프레이밍 전환을 추적하며, 실제 주가 백테스트를 통해 초과 수익률(Alpha)을 검증하는 풀스택 웹 애플리케이션입니다.

- **프론트엔드**: React, Tailwind CSS, Recharts (차트 시각화), Lucide-react (아이콘)
- **백엔드**: Node.js, Express (API 서버)
- **데이터 저장소**: Firebase Storage (자막 텍스트 파일 호스팅)
- **AI 엔진**: Google Gemini AI (`@google/genai` SDK)
- **금융 데이터**: Yahoo Finance (`yahoo-finance2`)

---

## 2. 필수 의존성 (Dependencies)

새로운 시스템의 `package.json`에 다음 패키지들을 설치해야 합니다.

### 백엔드 (Node.js/Express)
```bash
npm install express firebase-admin @google/genai yahoo-finance2
```

### 프론트엔드 (React)
```bash
npm install recharts lucide-react clsx tailwind-merge
```

---

## 3. 핵심 모듈 및 코드 이식 가이드

시스템을 크게 3가지 주요 파이프라인으로 나누어 이식합니다.

### Step 1: Firebase Storage 데이터 파이프라인 연동
자막 파일이 저장된 Firebase Storage에서 목록 및 텍스트 데이터를 읽어오는 로직입니다.

**백엔드 필수 설정:**
1. Firebase 프로젝트 설정에서 서비스 계정 비공개 키(`firebase_key.json`)를 발급받아 프로젝트 루트에 위치시킵니다.
2. 백엔드에서 Firebase Admin SDK를 초기화합니다.

```typescript
import admin from 'firebase-admin';

// Firebase 초기화 로직
admin.initializeApp({
  credential: admin.credential.cert(require('./firebase_key.json'))
});

// 1) 파일 목록 읽기 API
app.get('/api/firebase-storage-list', async (req, res) => {
  const bucket = admin.storage().bucket('YOUR_BUCKET_NAME.firebasestorage.app');
  const [files] = await bucket.getFiles({ prefix: 'ai_ready_texts/' });
  // ... 파일 필터링 및 응답 ...
});

// 2) 파일 내용 읽기 API
app.post('/api/firebase-storage-read', async (req, res) => {
  const bucket = admin.storage().bucket('YOUR_BUCKET_NAME.firebasestorage.app');
  const file = bucket.file(req.body.filePath);
  const [content] = await file.download();
  res.json({ text: content.toString('utf-8') });
});
```

### Step 2: Gemini AI 기반 퀀트 서사 분석 엔진
텍스트 데이터를 입력받아 프롬프트를 통해 5대 고정 택소노미(주요 프레임) 중 하나로 분류하고, 제이슨(JSON) 규격으로 반환받는 로직입니다.

- **환경 변수**: `GEMINI_API_KEY` 설정 필수.
- AI SDK는 프론트엔드 또는 백엔드 어디서든 활용 가능하지만, 시스템에서는 프론트엔드에서 직접 호출하는 방식을 채택했습니다(원할 경우 백엔드로 이관 가능).

**AI 추출 핵심 프롬프트 및 스키마 (TypeScript):**
```typescript
import { GoogleGenAI, Type } from '@google/genai';

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
const systemPrompt = `
너는 월스트리트 헤지펀드의 시니어 퀀트 데이터 추출 엔진이다.
1. 명시적 엔티티: 명확하게 언급된 기업의 공식 티커만 추출. [AI 및 반도체] 한정.
2. 5대 고정 택소노미: Infra_Buildout, Product_Launch_Demand, Monetization_Proof, Valuation_Concern, Regulation_Macro_Risk 중 1개 선택.
3. 시간 출처 타입: explicit_datetime, earnings_reference, unknown_or_relative 중 택 1.
`;

const response = await ai.models.generateContent({
  model: 'gemini-3-flash-preview',
  contents: `[분석할 자막 원문]:\n${transcript}`,
  config: {
    systemInstruction: systemPrompt,
    responseMimeType: 'application/json',
    responseSchema: { /* JSON Schema 정의 */ }
  }
});
const aiData = JSON.parse(response.text!);
```

### Step 3: 주가 백테스트 및 초과 수익률 계산 (Yahoo Finance)
AI가 추출한 티커 기호를 기반으로 Yahoo Finance에서 실제 주가를 가져와 벤치마크(예: SOXX)와 비교하는 백테스트 로직입니다. 

**백엔드 API 구현 (`/api/backtest`):**
```typescript
import YahooFinance from 'yahoo-finance2';
const yahooFinance = new YahooFinance();

// 주가 데이터 요청
const queryOptions = { period1: '시작일', period2: '종료일', interval: '1d' };
const [tickerResult, benchResult] = await Promise.all([
  yahooFinance.chart(ticker, queryOptions),
  yahooFinance.chart(benchmark, queryOptions)
]);

// 데이터 정규화 및 수익률 계산 로직
const t0_ticker = tickerResult.quotes[0].close;
const t3_ticker = tickerResult.quotes[3].close;
const alpha_3d = ((t3_ticker - t0_ticker) / t0_ticker) * 100 - /* 벤치마크 수익률 */;
```

---

## 4. 프론트엔드 UI/UX 이식 (React/Tailwind)

본 시스템은 직관적인 데이터 레이아웃을 사용합니다. 프론트엔드 이식 시 다음 컴포넌트 구조를 참고하세요.

1. **제어 패널 (Sidebar)**: Firebase Storage 경로, 벤치마크 티커 설정 관리 요소 배치.
2. **섹션 A (AI 내러티브 추출 결과)**: AI가 분류한 5대 택소노미, 시장 분위기, 확신도, 발췌 원문을 카드 형태로 시각화.
3. **섹션 B (초과 수익률 검증)**: 계산된 T+3, T+5 초과 수익률(Alpha) 수치를 표시.
4. **차트 (Recharts)**: 주가 흐름을 선형 그래프로 시각화 (종목 vs 벤치마크 누적 수익률 비교).

---

## 5. 배포 및 보안 주의사항

- **키 파일 노출 금지**: `firebase_key.json` 파일은 반드시 `.gitignore` 등에 포함하여 외부에 노출되지 않도록 설정해야 합니다. (기존 환경 파일 참고)
- **API 키 관리**: `GEMINI_API_KEY`는 서버의 보안 환경 변수 또는 클라우드 플랫폼의 Secrets Manager 등을 활용하여 주입되게 구성하세요.
