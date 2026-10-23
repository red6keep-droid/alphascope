# 운영 현황 페이지 (관리자 전용)

날짜(KST)별로 다섯 리포트(데일리 · 트럼프 · NVDA · 인물 레이더 · 미디어 데일리)가 **발행됐는지 · 왜 안 됐는지**,
**어떤 AI 모델이 예비로 넘어갔는지**, **정보 수집에서 어떤 오류가 났는지**를 한 화면에 보여 준다.

```
리포트 실행 (GitHub Actions)
  └ experiments/ops_log.py — 실행이 끝날 때 운영 기록 1건 → Cloudflare KV (OPS_KV, 180일 보관)
운영 페이지 (이 Worker, *.workers.dev)
  ├ Cloudflare Access — 관리자 이메일 로그인(일회용 코드)만 통과
  ├ Worker 가 Access 토큰을 다시 검증 (설정이 비어 있으면 전부 거부)
  └ KV 운영 기록 + GitHub Actions 실행 목록 → 화면
```

저장소가 공개라 운영 기록은 `*-state` 브랜치 · gh-pages 에 두지 않는다. 기록을 보내기 전에 환경변수의 키 · 토큰 값과 URL 의 `key=` · `token=` 은 `***` 로 지운다.

## 설정 (한 번)

비밀값은 채팅 · 문서 · 커밋에 붙여 넣지 말고, 아래 명령의 입력 창이나 대시보드에만 넣는다.

### 1. KV 와 Worker

```
cd infra/ops-console
npx wrangler kv namespace create OPS_KV        # 나온 id 를 wrangler.toml 의 kv_namespaces.id 에
npx wrangler secret put GITHUB_TOKEN           # 선택 — Fine-grained 토큰, 이 저장소 Actions: Read-only 만
npx wrangler deploy
```

배포 직후에는 ACCESS_* 가 비어 있어 모든 요청이 403 이다 (정상).

### 2. Cloudflare Access (로그인 잠금)

1. Cloudflare 대시보드 → Workers & Pages → `alphascope-ops-console` → Settings → Domains & Routes → `workers.dev` 의 **Cloudflare Access 켜기**.
2. Zero Trust → Access → Applications 에 생긴 애플리케이션의 정책을 **관리자 이메일만 Allow** 로 둔다 (로그인 방식: One-time PIN).
3. 그 애플리케이션의 **Application Audience (AUD) Tag** 와 팀 도메인(`<팀>.cloudflareaccess.com`)을 `wrangler.toml` 의 `ACCESS_AUD` · `ACCESS_TEAM_DOMAIN` 에, 관리자 이메일을 `ADMIN_EMAILS` 에 넣고 다시 `npx wrangler deploy`.

### 3. 리포트가 기록을 보내게 (GitHub 저장소 Secrets)

Cloudflare 대시보드 → My Profile → API Tokens → Create Token → 권한 **Account · Workers KV Storage · Edit** 하나만.

GitHub 저장소 → Settings → Secrets and variables → Actions 에 셋:

| 이름 | 값 |
|---|---|
| `OPS_CF_ACCOUNT_ID` | Cloudflare 계정 ID |
| `OPS_CF_KV_NAMESPACE_ID` | 1단계의 KV id |
| `OPS_CF_API_TOKEN` | 위 API 토큰 |

셋 중 하나라도 없으면 ops_log 는 아무것도 보내지 않는다 — 리포트는 예전과 똑같이 돈다.

## 한도 (무료)

| 항목 | 사용량 | 무료 한도 |
|---|---|---|
| KV 쓰기 | 리포트 실행마다 1~3건, 하루 약 10~20건 | 하루 1,000 |
| KV 목록 · 읽기 | 페이지를 열 때만 | 하루 1,000 · 100,000 |
| Worker 요청 | 페이지를 열 때만 | 하루 100,000 |
| GitHub API | 페이지 1회에 6번 | 토큰 있으면 시간당 5,000 (없으면 60) |
| Access | 관리자 1명 | 50명까지 무료 |

AI 호출 · 시세 API 는 쓰지 않는다 (이미 끝난 실행의 결과를 읽기만).

## 판정 규칙 (src/index.js `verdict`)

발행 · 갱신 · 이미 있음 → 진행 중 → 잡히지 않은 예외(에러로 중단) → "게시하지 않는다" 줄(미발행 + 이유) → 워크플로 실패 →
dry-run → 기록 없음 → 예정 없는 요일 → 오늘이면 "아직 안 돎", 지난 날이면 "실행 없음(예약 누락)".
