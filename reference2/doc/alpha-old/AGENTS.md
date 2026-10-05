# Project Principles: Financial Data Integrity

## 1. Zero Tolerance for Fake Data
- **Absolute Rule:** Never use mock, placeholder, or "simulated" data for financial analysis, ticker symbols, or price performance.
- **Philosophy:** In quantitative finance, trust is the primary asset. Providing a "best guess" or fake data when the real data is inaccessible is a critical system failure.

## 2. Explicit Error Reporting
- If an API fails, a ticker is delisted, or technical analysis cannot be completed, the system **MUST** display a clear error message.
- Do not "fallback" to generic values.
- UI components must accurately reflect the lack of data (e.g., "Data Unavailable" or "API Error: [Details]") instead of showing zeros or dummy charts.

## 3. Data Provenance
- All extracted signals must be linked back to raw evidence in the source text.
- If the AI cannot find a specific ticker or date, it should return an error or null, and the UI must treat this as an incomplete record.
- **Reference Date Integrity:** The "Analysis Reference Date" (T-0) must strictly match the actual event or subtitle timestamp. Never use current system time as a default if a more specific timestamp (e.g., from a folder or metadata) is available.

## 4. User Experience: Korean First & Plain Language
- **Absolute Rule:** All UI titles, headers, labels, and analytical metrics must be strictly in Korean. 
- **Philosophy:** Our app's core philosophy is to explain things easily in Korean without using difficult English terms ("어려운 용어 '영어'를 쓰지 않고 한국어로 쉽게 설명한다가 기본 철학이다"). Financial technology should be completely accessible. 
- **Consistency:** Never use English terms like 'Alpha', 'Mentions', 'Spread Score', 'Bullish/Bearish', 'Ticker', 'Sentiment', etc. in the UI. Always translate them to plain, easy-to-understand Korean equivalents (e.g. '초과 수익률', '언급 횟수', '확산 점수', '상승/하락', '종목', '시장 심리' 등).
- **Enforcement:** Do not write code that violates this core philosophy.

## 5. Distinction Between Errors and Natural Lags
- **Absolute Rule:** Do not label missing future price data (e.g., waiting for T+3 performance) as a "Data Integrity Error."
- **Philosophy:** Market performance takes time to materialize. Use clear Korean descriptions such as "시장 데이터 수집 대기 중 (T+3)" instead of alarming error messages.

## 6. Institutional Narrative Synchronization (기관 내러티브 동기화)
- **Core Principle:** The recurrence of the same ticker and narrative across different sources/channels within a short period (T=0) is a **Positive Signal Amplification**, not a bug.
- **Spread Score (네트워크 확산 점수):** 
  - 각기 다른 매체(Channel)에서 동일한 서사가 포착될 때마다 점수가 상승합니다.
  - **계산식:** `COUNT(DISTINCT Channel_Name)`.
  - **Philosophy:** 한 매체가 여러 번 반복하는 것은 '채널 내 지속성(Intra-channel Persistence)'으로 보되, 시장의 합의(Consensus)를 의미하는 '확산(Spread)' 점수에는 1회만 반영합니다.
- **Backtest Strategy:** For synchronized signal clusters, the Analysis Reference Date (T-0) is fixed at the earliest detected occurrence.
- **Integrity Check:** Multiple outputs from the SAME Video ID are handled by the merge-then-analyze logic. If duplicates persist from a single ID, it is a processing failure. Output from DIFFERENT Video IDs is a valid "Consensus" signal.

## 7. Strict Error Feedback & System Transparency
- **Absolute Rule:** Any operational failure, API error, or logically invalid state MUST exhibit immediate, overt, and clear Korean error messages to the user.
- **Philosophy:** Do not swallow errors, do not use fallback dummy data, and do not let the system silently fail. If an action fails (e.g., updating a baseline analysis or deleting history), the exact cause of the failure must be articulated in the UI.
- **Implementation:** Global error states must be distinctly visualized (e.g., Red/Amber banners with exact error messages) and local component failures must display inline error states preventing the user from guessing what went wrong.

## 8. High-Density UI Design (고밀도 UI 디자인)
- **Absolute Rule:** 모바일 화면의 특성을 고려하여 공간을 효율적으로 구성한다. 불필요한 카드 디자인(여백이 많은 박스 형태)을 쓰지 않는다.
- **Absolute Rule:** 모든 본문(내용) 폰트는 18px 로 적용한다. (단, 부가 정보나 날짜 등은 예외)
- **Philosophy:** 타이틀과 내용은 가급적이면 한 줄에 표시하여 수직 스크롤을 최소화한다. 중복되는 의미의 타이틀은 쓰지 않는다. 최대한 밀도 있게 콘텐츠를 구성하며, 디자인적인 구분은 선(border)이나 약간의 배경색/텍스트 색상 차이를 통해 단순하게 구현한다.
- **Implementation:** Remove rounded cards, shadows, and excessive padding. Use simple borders or lines for structure. Align titles and values inline where possible.

## 9. Color System: Korean Market Standard
- **Rise (상승/Bullish):** 반드시 **빨간색(Red)** 계열을 사용한다.
- **Fall (하락/Bearish):** 반드시 **파란색(Blue)** 계열을 사용한다.
- **Accent (UI 포인트):** 기존의 파란색 대신 **파스텔톤 오렌지(Orange)** 베리에이션을 사용하여 전문적이고 따뜻한 느낌을 준다.
- **Comparison:** 벤치마크나 중립 상태는 무채색(Gray/Slate) 계열을 사용한다.
