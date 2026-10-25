# cron-trigger

GitHub Actions 예약 실행(cron)은 보장되지 않는다. 몇 시간 늦거나 통째로 빠진다
(2026-10-13에는 데일리·트럼프·NVDA가 전부 오지 않았다). 이 Cloudflare Worker가 같은 시각에
`workflow_dispatch`를 `scheduled=true`로 걸고, 워크플로는 그 실행을 스케줄 실행과 똑같이 취급한다
(자동 게시, Gemini 서술, `TRUMP_PUBLISH`/`NVDA_PUBLISH` 게이트).

시각은 **뉴욕 현지 시각**으로 정한다 (2026-10-16). 미국장 마감(16:00 뉴욕)에 묶여 있어야 하는데, UTC로 고정하면
서머타임이 끝나는 날(11월 첫 일요일) 데일리가 장 마감 순간에 돌아 종가가 확정되기 전 데이터로 쓴다.
cron 하나(`0,15,30 21-23 * * *` UTC)가 서머타임·표준시 양쪽 후보 시각에 깨어나고, Worker가 뉴욕 시각이
`JOBS` 키와 같을 때만 건다.

| 뉴욕 | KST 서머타임 (3월 둘째 일~11월 첫 일) | KST 표준시 | 워크플로 |
|---|---|---|---|
| 17:00 (월~금) | 06:00 | 07:00 | test-daily-report.yml |
| 17:15 | 06:15 | 07:15 | trump-trend.yml |
| 17:30 | 06:30 | 07:30 | nvda-report.yml (트럼프가 올린 trump-state를 읽으므로 15분 뒤) |
| 18:00 | 07:00 | 08:00 | people-radar.yml (trump-state · report-state 를 읽는다. 같은 날 글은 갱신만) |
| 18:30 (월~금) | 07:30 | 08:30 | test-daily-report.yml 재시도 |

고빈도 수집도 같은 Worker가 건다 (2026-10-22). GitHub cron 만으로는 하루 15분 시세 96회 중 7회,
2시간 뉴스 12회 중 4회만 돌았다. 간격 작업이라 시각은 UTC 로 판단하고, 두 워크플로에는 `scheduled` 입력이 없어 inputs 없이 건다.

| 간격 | 워크플로 |
|---|---|
| 뉴욕 10:00 ~ 15:00 매시 + 16:20 (월~금) | update.yml (홈 시세) — 종가 기준 블로그(기획/블로그-목적과-방향 5절): 마감 20분 뒤 확정 1회 + 장중 매시. 15분 수집은 뺐다 |

한국 시각 표 (`KST_JOBS`, 2026-10-22) — 한국 방송 시각에 묶인 작업은 서머타임을 따르지 않는다:

| KST | 워크플로 |
|---|---|
| 06:45 · 21:45 (매일) | news.yml (홈 주요 뉴스, 2026-10-25 2시간마다 → 하루 두 번) |
| 08:00 (월~금) | media-daily.yml phase=1 (미디어 데일리 1차) |
| 10:15 (월~금) | media-daily.yml phase=2 (같은 글 갱신) |

분을 서로 비켜 둔다(리포트 :00 · :15 · :30, 시세 :00 · :20, 뉴스 :45) — 모두 gh-pages 에 push 하므로 같은 분에 돌면 한쪽이 거부된다.
시세는 뉴욕 시각 표(JOBS)에 있어 서머타임을 따라간다. cron 은 `0,15,20,30,45 * * * *` 하나.

GitHub cron도 그대로 둔다. 둘 다 도는 날은 뒤에 도는 실행이 `check_published.py`로
오늘 글이 이미 있는 것을 보고 건너뛴다. 수동 실행(`scheduled` 끔)은 이 확인을 하지 않는다.

## 배포

1. GitHub fine-grained token 발급 — Settings → Developer settings → Fine-grained tokens.
   Repository access: `red6keep-droid/alphascope`만. Permissions: **Actions: Read and write**만.
2. 배포 (Cloudflare 무료 계정이면 충분. cron 트리거 3개를 쓴다 — 무료 플랜 한도는 계정당 5개):

   ```
   cd infra/cron-trigger
   npx wrangler login
   npx wrangler secret put GITHUB_TOKEN   # 1의 토큰 붙여넣기
   npx wrangler deploy
   ```

워크플로에 `scheduled` 입력이 생긴 커밋이 **main에 올라간 뒤** 배포해야 한다.
그 전에는 GitHub API가 "Unexpected inputs"(422)로 거부한다.

## 확인

- Cloudflare 대시보드 → Workers → alphascope-cron-trigger → Logs/Cron Events
- 로컬 시험: `npx wrangler dev --test-scheduled` 후
  `curl "http://localhost:8787/__scheduled?cron=45+22+*+*+*"` — **실제로 dispatch가 걸리고 글이 게시된다.**
- 시각을 바꾸면 `src/index.js`의 `JOBS` 키(뉴욕 시각)를 고치고, 새 시각의 UTC 후보 두 개(뉴욕 + 4h · + 5h)가
  `wrangler.toml`의 `crons`에 들어 있는지 확인한다. 워크플로 파일의 `schedule:` cron(예비, UTC 고정)도
  계절과 상관없이 장 마감 뒤가 되도록 맞춰 둔다.
- 로컬 시험 예: `curl "http://localhost:8787/__scheduled?cron=0,15,30+21-23+*+*+*"` — 이때는 현재 시각 기준이라
  대부분 아무것도 걸지 않는다.
