# 금융 미디어 요약 분석 기능 이식 가이드 (당잠사 & 매드머니)

이 문서는 AlphaFlow 프로젝트의 핵심 기능 중 하나인 '당잠사' 및 '매드머니' 유튜브 자막 요약 분석 기능을 타 서비스나 앱에 이식하기 위한 상세 명세서입니다.

---

## 1. 개요
이 기능은 유튜브 자막(Subtitle) 데이터를 입력받아 AI(Gemini)를 통해 정형화된 금융 분석 리포트(JSON)로 변환합니다. 채널의 특성에 따라 서로 다른 프롬프트와 카테고리 체계를 적용하는 것이 핵심입니다.

## 2. 채널별 분석 명세

### 2.1 당잠사 (당신이 잠든 사이)
매일 아침 미국 시장의 주요 지표와 뉴스를 종합적으로 브리핑하는 데 최적화되어 있습니다.

#### [AI 시스템 프롬프트]
```text
너는 월스트리트 헤지펀드의 시니어 퀀트 애널리스트다.
입력되는 텍스트는 매일 아침 미국 시장을 브리핑하는 '당잠사' 채널의 유튜브 자막이다. 
이 자막을 분석하여 아래의 [14개 메인 카테고리] 분류 체계에 맞춰 핵심만 요약하라.

[14개 메인 카테고리 풀(Pool)]
1. 오늘의 핵심 요약, 2. 글로벌 헤드라인, 3. 미국 증시 마감, 4. 국채 및 금리, 5. 달러와 환율, 6. 원자재 시장, 7. 경제지표, 8. 섹터별 움직임, 9. 핫 이슈 종목, 10. 기업 실적, 11. AI·반도체, 12. 월가 의견, 13. 이번 주 경제 일정, 14. 투자 인사이트

[절대 지시 규칙]
1. 동적 렌더링: 원문에 언급되지 않은 카테고리는 배열에서 완전히 삭제할 것.
2. MECE 원칙: 동일 내용을 중복 카테고리에 넣지 말 것.
3. 형식: 인사말 없이 지정된 JSON 포맷으로만 출력할 것.
```

#### [출력 데이터 구조 (Schema)]
```json
{
  "channel_name": "string",
  "summary_date": "YYYY-MM-DD",
  "contents": [
    {
      "category_name": "string",
      "items": ["string"]
    }
  ]
}
```

---

### 2.2 매드머니 (Mad Money)
시장의 심리(Sentiment), 내러티브, 그리고 개별 종목의 투자의견을 추출하는 데 집중합니다.

#### [AI 시스템 프롬프트]
```text
너는 월스트리트 최상위 헤지펀드의 시니어 퀀트 애널리스트이자 'AI 마켓 내러티브 엔진'이다.
입력되는 텍스트는 미국 주식 시장을 다루는 금융 유튜브 방송의 자막이다.
너의 임무는 방송의 두서없는 대화 속에서 '시장의 심리(Sentiment)', '스마트 머니의 흐름(Flow)', '메가 트렌드(AI/Macro)'를 포착하여 정량화된 JSON 리포트를 작성하는 것이다.

[핵심 카테고리 분류 체계]
1. 시장 총평, 2. 거시경제, 3. 시장 심리, 4. AI / 데이터센터, 5. 반도체, 6. IPO / 신규상장, 7. 기관 자금 흐름, 8. 섹터별 흐름, 9. 개별 종목 분석, 10. 기업 실적, 11. 경제 일정, 12. 투자 전략, 13. CEO 인터뷰

[절대 지시 규칙]
1. 센티먼트 태깅: 각 카테고리에 'sentiment' 필드(Risk-On, Bearish, Neutral 등) 필수 기재.
2. 종목 티커 명시: 기업 언급 시 반드시 괄호 안에 티커 포함 (예: NVIDIA (NVDA)).
3. 동적 배열: 언급되지 않은 카테고리는 배열에서 제외.
```

#### [출력 데이터 구조 (Schema)]
```json
{
  "summary_date": "YYYY-MM-DD",
  "channel_name": "string",
  "contents": [
    {
      "category": "string",
      "sub_category": "string",
      "sentiment": "string",
      "items": ["string"]
    }
  ]
}
```

---

## 3. 기술 구현 가이드

### 3.1 워크플로우 (Workflow)
1.  **자막 수집**: 외부 스토리지(Firebase Storage 등)에서 `.txt` 형태의 자막 파일을 로드합니다.
2.  **채널 판별**: 파일 경로나 메타데이터에서 `channelName`을 추출합니다.
    -   `당잠사` 인지 `Mad Money` 인지에 따라 적용할 프롬프트와 스키마를 결정합니다.
3.  **AI 추론 (LLM)**:
    -   **Model**: `gemini-1.5-flash` 이상 권장.
    -   **Config**: `responseMimeType: "application/json"`, `temperature: 0.1` 설정으로 결과의 일관성 유지.
4.  **데이터 저장**: 분석된 JSON 결과를 데이터베이스(Firestore)의 `daily_summaries` 컬렉션에 저장합니다.

### 3.2 핵심 코드 로직 (Node.js/TypeScript 기준)
```typescript
// 채널에 따른 프롬프트 및 스키마 선택 로직
let reqConfig: any = { responseMimeType: "application/json", temperature: 0.1 };

if (channelName === "당잠사") {
    reqConfig.systemInstruction = DANGJAMSA_PROMPT;
    reqConfig.responseSchema = DANGJAMSA_SCHEMA;
} else if (channelName.includes("Mad Money")) {
    reqConfig.systemInstruction = MADMONEY_PROMPT;
    reqConfig.responseSchema = MADMONEY_SCHEMA;
}

// AI 호출
const resultRaw = await genAI.models.generateContent({
    model: "gemini-1.5-flash",
    contents: [{ role: "user", parts: [{ text: mergedText }] }],
    config: reqConfig
});
```

## 4. 이식 시 주의사항
-   **토큰 제한**: 자막 원문이 매우 길 경우(10만 자 이상), AI 모델의 컨텍스트 제한에 걸릴 수 있으므로 적절한 절삭(Truncate)이 필요합니다.
-   **비용 최적화**: 매번 전체 자막을 분석하는 대신, 이미 분석된 `videoId`가 DB에 있는지 먼저 확인하는 캐싱 로직이 필수적입니다.
-   **환각(Hallucination) 방지**: 프롬프트에 `[절대 지시 규칙]`을 명시하여 AI가 임의로 카테고리를 생성하거나 소설을 쓰지 않도록 제어해야 합니다.
