# AlphaFlow YouTube Subtitle Engine 명세서 (Opinion Intelligence Specification)

| 버전 | 날짜 | 작성자 | 주요 내용 |
| :--- | :--- | :--- | :--- |
| **V1.0** | 2026-06-01 | GitHub Copilot | 유튜브 자막 기반 내러티브 추출 및 전문가 확신도 분석 엔진 설계 |

---

## 1. 엔진 철학: "맥락에서 확신으로(Context to Conviction)"
본 엔진은 단순히 영상을 요약하는 도구가 아니다. 시장 전문가들의 대화 맥락(Context)을 분석하여 **현재 시장이 어떤 주제에 열광하고 있는지(Narrative)**와 **그 주장의 강도가 어느 정도인지(Conviction)**를 측정하는 '여론 센서'다.

*   **변환 프로세스**: 영상 자막(Raw) → 텍스트 전처리(Denoising) → 내러티브 카테고리 맵핑 → 전문가 확신도 산출
*   **핵심 가치**: 심리적 흐름 파악. 뉴스가 '사실'을 알린다면, 유튜브는 그 사실이 시장 참여자들에게 '어떻게 해석되고 확산되는지'를 읽어낸다.

---

## 2. 데이터 수집 및 처리 레이어

### 2.1 수집 대상 (Core Channels)
*   **글로벌**: CNBC, Bloomberg Technology, Yahoo Finance Live
*   **국내**: 한국경제TV(당잠사), 삼프로TV, 매드머니(Cramer)

### 2.2 전처리 로직 (Denoising)
*   **불필요 어구 제거**: 자막 특유의 추임새, 중복 단어, 오타 자동 보정
*   **토큰 최적화**: 30,000자 이상의 긴 자막을 핵심 맥락 유지하며 압축하여 AI 입력 비용 절감

---

## 3. 분석 및 추출 로직 (Extraction Engine)

### 3.1 5대 고정 내러티브 택소노미 (Narrative Taxonomy)
모든 전문가의 발언을 다음 5가지 범주 중 하나 이상으로 연결한다.
1.  **Infra_Buildout**: 인프라 투자 및 공급망 확충 (예: "데이터센터 증설")
2.  **Product_Launch_Demand**: 신제품 출시 및 수요 폭증 (예: "아이폰 AI 기능 탑재")
3.  **Monetization_Proof**: 수익화 증명 및 실적 개선 (예: "SaaS 구독 매출 증가")
4.  **Valuation_Concern**: 밸류에이션 부담 및 고점 경고 (예: "멀티플 과도")
5.  **Regulation_Macro_Risk**: 규제 및 거시 경제 리스크 (예: "대중국 수출 규제")

### 3.2 전문가 확신도 (Conviction Score)
단순 긍부정이 아닌 발언의 '세기'를 1~100점으로 산출한다.
*   **가중치 요소**: 반복 언급 횟수, 강력한 단어 선택(Must, Game-changer 등), 근거 데이터 제시 여부

---

## 4. 데이터 구조 (Data Structure)

### 4.1 SUBTITLE_SIGNAL 테이블
```json
{
  "ticker": "AMD",
  "channel_name": "당잠사",
  "narrative": "Infra_Buildout",
  "sentiment": "Bullish",
  "conviction_score": 85,
  "korean_summary": "MI300X 공급 확대 및 빅테크와의 추가 파트너십 가능성 강조",
  "raw_quote": "이번 분기부터 실질적인 점유율 확대가 눈에 띌 것입니다",
  "event_date": "2026-06-01"
}
```

---

## 5. 지능형 결합 로직 (The Bridge)

### 5.1 Reconfirmation (내러티브 강화)
*   **동작**: 동일 종목이 서로 다른 2개 이상의 우량 채널에서 3일 이내 반복 언급될 경우
*   **결과**: 시스템 상태를 `RECONFIRMED`로 변경하고 사용자에게 고신뢰 알림 발송

### 5.2 Divergence 감지 (괴리 발생)
*   **동작**: 뉴스는 호재(Fact: Earnings Beat)인데, 유튜브 전문가 의견은 부정적(Opinion: Demand Peak)일 경우
*   **결과**: '주의(Caution)' 상태값을 부여하고 퀀트 데이터 확인(Layer 2)을 강제함

---

## 6. 뉴스 엔진과의 비교 (News vs YouTube)

| 기능 | News Event Engine (Fact) | YouTube Subtitle Engine (Opinion) |
| :--- | :--- | :--- |
| **분석 단위** | 사건(Event) 중심 | 맥락(Context) 중심 |
| **주요 출력** | 8대 이벤트 카테고리 | 5대 고정 내러티브 |
| **신뢰 기준** | SEC 공시, 언론사 공신력 | 전문가 확신도, 반복 언급 |
| **시스템 기여** | **에너지의 시작 (NEW)** | **에너지의 유지/연장 (KEEP/EXTEND)** |

---

## 7. 구현 로드맵
1.  **Phase 1**: 현재의 `analyzeDangjamsa`, `analyzeMadMoney` 로직을 5대 내러티브 체계로 표준화
2.  **Phase 2**: 여러 영상의 분석 결과를 시간축으로 병합하는 '내러티브 타임라인' UI 구현
3.  **Phase 3**: 뉴스 이벤트 엔진과 데이터베이스 연동 및 상호 보완 로직 구현
