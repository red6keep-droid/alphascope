# newfact-board — 토론(댓글) 쓰기 API

기획: alphascope-docs `doc/기획/댓글-토론방-기획.md` · 앱 대비: alphascope-docs `doc/운영/앱-대비-설계-원칙.md`

```
읽기  방문자(블로그 · 앱) → board.newfact.app/v1/{열쇠}/index.json · b/{n}.json · t/{글 id}.json   (R2 공개 + Cloudflare 캐시 1분, Worker 안 거침)
쓰기  회원 → api.newfact.app/v1/…  (이 Worker: Firebase ID 토큰 → 규칙 → D1 원본 → R2 파일 다시 만들기)
```

## API

| 주소 | 하는 일 |
|---|---|
| `POST /v1/post` `{key, title, text, sym?, where?{url,label}}` | 글 |
| `POST /v1/reply` `{post, text, sym?}` | 답글 |
| `POST /v1/react` `{item, v: 'up'│'down'│null}` | 좋아요 · 싫어요 · 바꾸기 · 취소 |
| `POST /v1/report` `{item, why: ad│abuse│privacy│false│etc}` | 신고(3명이면 바로 가림) |
| `DELETE /v1/item` `{item}` | 내 글 · 답글 지우기(주인은 모두) |
| `GET /v1/me?key=` | 별명 · 남은 수 · 그 자리 내 표 |
| `GET /v1/me/items?before=` | 내가 쓴 글 20개씩 |
| `PUT /v1/profile` `{nick?, intro?}` | 별명(2~12자 · 30일 · 겹침 금지) · 소개 100자 |
| `/v1/admin/new?since=` · `hidden` · `reply` · `remove` · `hide` · `restore` · `ban` · `import` | 운영(ADMIN_KEY) — 댓글 봇 · 운영 콘솔 |

열쇠 = `stock-{티커 소문자}` · `p-{고정 페이지 주소 이름}` · `post-{글 주소 이름}` · `market-kr` · `market-us` · `kr-report` (Blogger 글 번호 쓰지 않음 — 앱 대비).
오류 = `{error: 코드, message: 독자에게 보일 문장}` + 상태 번호(400 · 401 · 403 · 404 · 409 · 429).

## 시험

```sh
cd infra/board && sh test/run.sh     # 로컬 D1 · R2 로 88경우(2026-11-22 전부 맞음)
```

## 처음 만들기 (red6 계정)

```sh
npx wrangler d1 create newfact-board                 # 나온 id → wrangler.toml database_id
npx wrangler d1 execute newfact-board --remote --file schema.sql
npx wrangler r2 bucket create newfact-board
npx wrangler secret put ADMIN_KEY                    # 32자 넘는 무작위 값 — 댓글 봇 · 운영 콘솔 비밀값에도
npx wrangler deploy                                  # api.newfact.app 연결(custom_domain)
```
대시보드: R2 `newfact-board` → 설정 → 공개 주소 `board.newfact.app` 연결 → 캐시 규칙(`board.newfact.app` = 캐시 대상 · 원본 머리말 따름) → `curl -sI` 두 번으로 `cf-cache-status: HIT` · `age` 60 넘지 않는지 확인.
