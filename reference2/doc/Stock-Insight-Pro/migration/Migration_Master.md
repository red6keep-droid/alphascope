# Migration Master Guide: Stock Insight Pro

이 문서는 Stock Insight Pro 앱을 새로운 환경으로 이식하기 위한 통합 마스터 가이드입니다.

## 1. 핵심 철학 및 이식 원칙
- **생존 우선 (Survival Over Alpha)**: 모든 기능 이식의 목적은 '수익'이 아니라 '리스크 관리'입니다.
- **결정론적 수치 활용**: AI의 추론에 의존하기 전, 반드시 수학적으로 계산된 수치(ATR, 금리차 등)가 선행되어야 합니다.
- **단계별 검증**: 각 단계를 완료할 때마다 이전 앱과 결과값이 동일한지 반드시 검증합니다.

## 2. 전체 이식 로드맵
| 단계 | 주제 | 핵심 내용 |
| :--- | :--- | :--- |
| **Phase 1** | 인프라 구축 | 환경 변수, 폴더 구조, 공통 타입 설정 |
| **Phase 2** | 매크로 엔진 | FRED 데이터 연동 및 시장 국면(Regime) 판별 |
| **Phase 3** | 데이터 레이어 | KIS/TwelveData 시세 연동 및 상태 관리 |
| **Phase 4** | 핵심 로직 | 리스크 엔진 및 AI 나러티브 생성기 이식 |
| **Phase 5** | 통합 및 UI | UI 컴포넌트 연결 및 최종 QA |

## 3. 이식 전 체크리스트
- [ ] API Key 확보 (KIS, FRED, Gemini, TwelveData)
- [ ] Firebase 프로젝트 생성 및 설정 파일 준비
- [ ] TypeScript 환경 (Vite 권장) 확인
- [ ] 인코딩 설정 (UTF-8) 확인

---
*다음 단계: [Step1_Infrastructure.md](Step1_Infrastructure.md)*
