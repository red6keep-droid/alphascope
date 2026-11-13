# 운영 현황 페이지 (관리자 전용)

날짜(KST)별로 다섯 리포트(데일리 · 트럼프 · NVDA · 인물 레이더 · 미디어 데일리)가 **발행됐는지 · 왜 안 됐는지**,
**어떤 AI 모델이 예비로 넘어갔는지**, **정보 수집에서 어떤 오류가 났는지**를 한 화면에 보여 준다.

```
리포트 실행 (GitHub Actions)
  └ experiments/ops_log.py — 실행이 끝날 때 운영 기록 1건 → Cloudflare KV (OPS_KV, 180일 보관)
운영 페이지 (이 Worker, *.workers.dev)
  ├ GitHub 로그인 — ADMIN_GITHUB_LOGINS 계정만 통과, 서명된 세션 쿠키 12시간 (설정이 비어 있으면 전부 거부)
  └ KV 운영 기록 + GitHub Actions 실행 목록 → 화면

Cloudflare Access 는 Zero Trust 무료 플랜도 카드 등록이 필요해 쓰지 않는다 (2026-10-23 사용자).
```

## 운영 대시보드 (2026-11-13)

```
ops-dashboard.yml (매시 50분 UTC · 수동)
  └ experiments/ops-dashboard/build_ops.py — 운영 기록(KV) · GitHub 실행 목록 · gh-pages 파일 · Blogger 피드 · 상태 저장소 브랜치 시각
      → 블로그 테마 CSS · JS 로 감싼 한 페이지 → KV dash:html (+ dash:hist = gh-pages 크기 날짜별)
이 Worker
  ├ /          = KV dash:html 그대로 (없으면 /runs 로)
  ├ /runs      = 날짜별 실행 화면 (예전 첫 화면)
  └ /fb-login  = 블로그 메뉴 `운영 현황` 이 Firebase ID 토큰을 POST — 구글 공개 키로 서명 · 프로젝트 · 만료 확인,
                 ADMIN_FIREBASE_UIDS 만 통과 → 같은 세션 쿠키(12시간). Origin 이 BLOG_ORIGIN 이 아니면 거부
```

블로그 메뉴 줄은 주인이 그 기기에서 댓글 구글 로그인을 한 번 하면 보인다(localStorage `as-admin`). 방문자 요청 0.
GitHub 로그인(/login)은 그대로 남긴다(예비 입구).

| 칸 | 자료 |
|---|---|
| 요약 | 아래 탭들의 판정을 모음 — 손이 필요한 곳 · 지켜볼 곳 |
| 화면 | gh-pages data · kr · news · cards/* · hypo 의 갱신 시각, search/us · kr 의 종목별 가격 날짜 |
| 발행 | 워크플로별 오늘 실행(GitHub API) + 운영 기록의 글 · 페이지 수, Blogger 피드 14일 새 글 |
| 수집 | 운영 기록의 수집 경고 · 운영 알림을 소스 이름으로 묶음 |
| AI | 운영 기록 llm.usage 의 req · tok (llm_chain, 11-13부터) — Gemini 는 태평양 자정부터, Groq · NVIDIA 는 최근 24시간 |
| 기록 | 상태 저장소 7개 브랜치(워크플로가 시각만 받음) · 공개 3개 브랜치 · gh-pages 크기 |
| 전망 | gh-pages hypo.json 진행 중 · 끝난 수 |

배포: `npx wrangler deploy` (사용자 확인 뒤). Secrets 는 그대로 — 새 값은 [vars] 의 공개 값 셋뿐(FIREBASE_PROJECT_ID · ADMIN_FIREBASE_UIDS · BLOG_ORIGIN).

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

배포 직후에는 로그인 설정이 비어 있어 모든 요청이 403 이다 (정상).

### 2. GitHub 로그인 (잠금)

1. GitHub(`red6keep-droid`) → Settings → Developer settings → OAuth Apps → **New OAuth App**
   - Homepage URL: `https://alphascope-ops-console.red6keep.workers.dev`
   - Authorization callback URL: `https://alphascope-ops-console.red6keep.workers.dev/callback`
2. 만든 앱의 **Client ID** 를 `wrangler.toml` `[vars]` 의 `GITHUB_CLIENT_ID` 에 (비밀 아님).
3. **Generate a new client secret** → `npx wrangler secret put GITHUB_CLIENT_SECRET` 입력 창에 붙여 넣는다 (또는 대시보드 Settings → Variables and Secrets → Add → 종류 Secret).
4. `SESSION_SECRET` 은 무작위 값 — 이미 넣어 두었다 (2026-10-23). 바꾸면 모든 로그인이 풀린다.
5. `npx wrangler deploy`.

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
| 대시보드 만들기 (ops-dashboard.yml) | 매시 1회 = 하루 24회 · KV 목록 2 · 읽기 약 30 ~ 60 · 쓰기 2 / 회 | KV 쓰기 하루 1,000 중 48 · 읽기 100,000 중 약 1,500 |
| GitHub OAuth App | 로그인할 때만 | 무료 |

AI 호출 · 시세 API 는 쓰지 않는다 (이미 끝난 실행의 결과를 읽기만).

## 판정 규칙 (src/index.js `verdict`)

발행 · 갱신 · 이미 있음 → 진행 중 → 잡히지 않은 예외(에러로 중단) → "게시하지 않는다" 줄(미발행 + 이유) → 워크플로 실패 →
dry-run → 기록 없음 → 예정 없는 요일 → 오늘이면 "아직 안 돎", 지난 날이면 "실행 없음(예약 누락)".
