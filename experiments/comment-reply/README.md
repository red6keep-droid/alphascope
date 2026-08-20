# 알파스코프 댓글 자동 답글 (experiments/comment-reply)

블로그에 새 댓글이 달리면 감지 → Gemini로 답글 생성 → **Slack으로 알림**까지 자동.
최종 등록(붙여넣기)만 사람이 하는 **반자동** 방식.

> 공식 Blogger API를 사용하며, 댓글 *작성(insert)*은 API에 존재하지 않으므로
> 생성된 답글을 관리자가 복사/붙여넣기해 직접 등록합니다. (가장 안전한 방식)

## 동작 흐름

```
comments.listByBlog (주기 폴링)
  → 새 댓글 감지 (내가 쓴 댓글·중복·스팸 제외)
  → Gemini 가 답글 생성
  → 답글 + 원글/관리자 링크를 Slack 으로 전송
  → 관리자가 링크에서 답글 복사/붙여넣기 → 등록
```

## 구조

```
experiments/comment-reply/
├── main.py               # 파이프라인 실행 (--send / --dry-run / --baseline / --test-*)
├── blogger_client.py     # Blogger API 댓글/게시글 조회 (OAuth refresh token)
├── generate_reply.py     # Gemini 답글 생성 (다중 키 fallback)
├── notify_slack.py       # Slack 인커밍 웹훅 알림 전송
├── state.py              # 처리 완료 댓글 ID 추적 (output/state.json)
├── prompts/comment_reply.txt
├── requirements.txt
└── .env.example
```

## 준비 (1회성)

1. **Blogger OAuth 3종** — `experiments/daily-report/` 에서 이미 발급 한 값
   (`BLOGGER_CLIENT_ID` / `BLOGGER_CLIENT_SECRET` / `BLOGGER_REFRESH_TOKEN`) 재사용.
2. **Slack 인커밍 웹훅** —
   [api.slack.com/apps](https://api.slack.com/apps) 에서 앱 생성
   → 왼쪽 **Incoming Webhooks** 활성화 → 워크스페이스/채널에 **Add New Webhook**
   → `https://hooks.slack.com/services/...` 형태의 `SLACK_WEBHOOK_URL` 발급.
3. **Gemini 키** — `GEMINI_API_KEY` (리포 루트 `.env` 값 재사용).

로컬 `.env` (리포 루트) 에:
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## 실행

```powershell
# 1) 현재 댓글을 '처리됨'으로 등록 (첫 실행 시 반드시 한 번: 오래된 댓글로 알림 안 보내게)
python experiments/comment-reply/main.py --baseline

# 2) Slack 연동 확인
python experiments/comment-reply/main.py --test-notification

# 3) 가상 댓글로 감지~생성 흐름 확인 (전송 없이 미리보기)
python experiments/comment-reply/main.py --test-comment "오늘 리포트 잘 봤습니다!"

# 4) 실제 전송까지 검증 (가상 댓글)
python experiments/comment-reply/main.py --test-comment "오늘 리포트 잘 봤습니다!" --send

# 5) 실제 감지 실행 (전송 없이 미리보기)
python experiments/comment-reply/main.py

# 6) 실제 감지 + Slack 발송
python experiments/comment-reply/main.py --send
```

## 자동 실행 (GitHub Actions)

`.github/workflows/comment-reply.yml`

- `schedule: cron '*/5 * * * *'` — 5분마다 감지. **일정 실행은 알림 발송을 켠 상태로 동작.**
- 처리 이력(`output/state.json`)은 별도 브랜치 `comment-state` 에 저장되어
  실행 간 중복 알림을 방지합니다.
- `workflow_dispatch` — "notify" 체크박스로 발송 on/off, "test_comment" 로 테스트 가능.
- Secrets: `BLOGGER_CLIENT_ID`, `BLOGGER_CLIENT_SECRET`, `BLOGGER_REFRESH_TOKEN`,
  `GEMINI_API_KEY`, `SLACK_WEBHOOK_URL`

> ⚠️ GitHub Actions schedule 은 트래픽에 따라 지연될 수 있습니다(공개 repo 특히).
> 더 촘촘한 실시간 반응이 필요하면 로컬 작업 스케줄러(Windows 작업)로
> `python .../main.py --send` 를 주기 실행하는 방식도 가능합니다.

## 기타

- 답글은 사람이 확인 후 등록하므로 AI 오답이 블로그에 그대로 올라갈 위험이 없습니다.
- 스팸성 댓글은 Gemini 판단(SPAM) 후 알림에서 표시되며, 관리자가 스팸 처리하면 됩니다.