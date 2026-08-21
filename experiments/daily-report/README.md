# 알파스코프 데일리 리포트 (experiments/daily-report)

미국 증시 데일리 브리핑을 매일 자동으로 만들어 Blogger(알파스코프 블로그)에 게시하는 **테스트용** 파이프라인입니다.
기존 루트의 `fetch_stocks.py` / `fetch_news.py` / 블로그 테마는 건드리지 않는 격리된 실험 폴더입니다.

## 구조

```
experiments/daily-report/
├── main.py                  # 파이프라인 실행 (--dry-run / --publish)
├── collect_fred.py          # FRED: 실업률(UNRATE), CPI(CPIAUCSL), VIX(VIXCLS)
├── collect_yahoo.py         # yfinance 지수(^GSPC ^IXIC ^DJI ^RUT ^VIX) + 급등주/관심종목 TOP5
├── collect_news.py          # CNBC RSS 20건 수집
├── generate_report.py       # Gemini 호출 → 한국어 분석 + 뉴스 선택 + 이미지 프롬프트
├── validate_report.py       # 구조/수치/뉴스 index/image_prompt 검증 (실패 시 중단)
├── generate_image.py        # 커버 이미지 생성 (Pollinations → HF fallback → WebP)
├── render_html.py           # 원본 숫자 + Gemini 문구 + 커버 이미지 → HTML
├── publish_blogger.py       # Blogger API v3 게시 (OAuth 2.0 Client ID + Refresh Token)
├── publish_saved.py         # 저장된 output/ 리포트 게시 (GitHub Actions 후속 단계용)
├── setup_oauth.py           # 1회 브라우저 승인 → refresh token 발급
├── verify_blogger.py        # 게시 없이 인증/블로그 연결 확인
├── prompts/daily_report.txt # Gemini 지시문
├── templates/report.html    # 리포트 HTML 템플릿
├── requirements.txt
└── .env.example             # 로컬용 키 템플릿 (직접 .env로 복사)
```

## 설계 핵심

- **숫자는 Python만 렌더링** — 지수 가격/등락률/거래량/경제지표는 수집 원본에서 직접 HTML로 만듭니다.
  Gemini는 한국어 분석 문구와 뉴스 선택(목록의 index)만 생성 → 숫자 조작/환각을 원천 차단합니다.
- **검증 후 게시** — 필수 필드 누락, 뉴스 index 오류 시 `exit(1)`로 중단하고 게시하지 않습니다.
- **기본 dry-run** — `--publish` 없이는 Blogger에 아무것도 올라가지 않습니다.
- **커버 이미지 자동 생성** — Gemini가 리포트와 함께 영문 이미지 프롬프트(`image_prompt`)를 출력하고,
  Pollinations.ai(1차, 키 불필요) → Hugging Face FLUX.1-schnell(2차 fallback, `HF_TOKEN` 필요) 순서로 생성합니다.
  고정 스타일 접미사(미니멀 3D 코퍼레이트 일러스트, 블루 계열, 문자 없음)를 붙여 매일 비슷한 톤을 유지하고,
  Pillow로 WebP(quality=80) 변환해 용량을 줄입니다.
- **이미지 호스팅은 GitHub** — Blogger API는 이미지 업로드를 지원하지 않으므로,
  워크플로우가 `output/images/{date}.webp`를 gh-pages 브랜치에 배포하고 jsDelivr CDN URL
  (`https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/images/{date}.webp`)을 게시글에 넣습니다.
  파일명에 날짜가 들어가 캐시 문제가 없고, 저장소가 살아 있는 한 링크가 유지됩니다.
- **게시 전 이미지 검증** — 워크플로우는 ①리포트+이미지 생성(dry-run) → ②gh-pages 배포 →
  ③jsDelivr purge·HTTP 200 확인 → ④`publish_saved.py` 게시 순서로 동작해,
  이미지 URL이 살아 있는 상태에서 글이 올라갑니다. 이미지 생성 실패 시 게시 단계는 중단됩니다.

## 준비 (1회성)

### 1. API 키

| 키 | 발급처 | 용도 |
|---|---|---|
| FRED_API_KEY | https://fred.stlouisfed.org/docs/api/api_key.html | 실업률/CPI/VIX 수집 |
| GEMINI_API_KEY | https://aistudio.google.com/app/apikey | 리포트 분석 (여러 키는 `;` 또는 `,`로 구분 → 앞 키가 한도 초과 시 다음 키로 자동 fallback) |
| HF_TOKEN | https://huggingface.co/settings/tokens (Read 권한) | 커버 이미지 fallback (Pollinations 실패 시에만 사용, 선택) |

### 2. Blogger 게시용 OAuth 2.0 (자동 게시를 켤 때만 필요)

> Blogger API는 사용자 계정 기반 OAuth 2.0을 요구한다. 서비스 계정(service account)은
> 초대 수락이 불가능해 동작하지 않으므로 **OAuth 클라이언트 ID + Refresh Token** 방식을 사용한다.

1. **Google Cloud Console** (https://console.cloud.google.com) → 프로젝트 생성 또는 선택
2. 검색창에서 **Blogger API** 검색 → **활성화**
3. **OAuth consent screen** → User type **External** → 본인 이메일을 Test users에 추가
   → **Publish App(Production)으로 전환**
   > ⚠️ "Testing" 상태로 두면 refresh token이 **7일마다 만료**된다. 검증 경고가 떠도
   > 본인 계정 사용에는 문제가 없으므로 Production 전환을 건너뛰지 말 것.
4. **APIs & Services > Credentials > Create Credentials > OAuth client ID**
   → Application type: **Desktop app** → `client_secret.json` 다운로드
5. `client_secret.json`을 **repo 밖**(예: `%USERPROFILE%\.blogger-oauth\`)에 보관한다.
   절대 리포에 두지 말 것 (`.gitignore`에 `client_secret*.json` 등록됨).
6. **1회 승인 → refresh token 발급**:
   ```powershell
   python experiments/daily-report/setup_oauth.py "%USERPROFILE%\.blogger-oauth\client_secret.json"
   python experiments/daily-report/setup_oauth.py "%USERPROFILE%\.blogger-oauth\client_secret.json" --save-env
   ```
   브라우저에서 **블로그 소유자 계정**으로 승인하면
   `BLOGGER_CLIENT_ID` / `BLOGGER_CLIENT_SECRET` / `BLOGGER_REFRESH_TOKEN`이 발급된다.
   (`--save-env`로 리포 루트 `.env`에 자동 기록 가능)
7. **연결 검증** (게시하지 않음, blogId만 확인):
   ```powershell
   python experiments/daily-report/verify_blogger.py
   ```
8. (권장) 값 추출 후 `client_secret.json`은 삭제한다. 액세스 토큰 자동 갱신에는
   client ID/secret/refresh token 3종만 있으면 충분하다.

### 3. 키 등록

**로컬 테스트용** — `.env.example`을 `.env`로 복사해 실 값을 채운다. `.env`는 `.gitignore`에 있어 push되지 않는다.
이 저장소 루트에는 이미 `.env`가 존재하며 `FRED_API_KEY`·`GEMINI_API_KEY`가 들어 있다. 리포 루트에서 실행하면 `main.py`가 자동으로 이 파일을 읽는다. (필요한 키가 없다면 루트 `.env`에만 추가하거나 `experiments/daily-report/.env`에 만들어도 된다.)

> ⚠️ 루트 `.env`는 `.gitignore`에 등록되어 있다. 등록 여부는 `git check-ignore .env`로 확인할 수 있다.

**GitHub Actions용** — 저장소 `Settings > Secrets and variables > Actions`에 등록한다:
- `FRED_API_KEY`
- `GEMINI_API_KEY`
- `HF_TOKEN` (커버 이미지 fallback용, 선택)
- `BLOGGER_CLIENT_ID` (자동 게시 전환 시)
- `BLOGGER_CLIENT_SECRET` (자동 게시 전환 시)
- `BLOGGER_REFRESH_TOKEN` (자동 게시 전환 시)

> ⚠️ 어떤 키도 코드·저장소·`.git`에 커밋하지 마세요. `.env`는 로컬 전용, Secrets는 GitHub 전용입니다.

## 실행

리포 루트에서:

```bash
# 단계별 확인: 로컬 수집
pip install -r experiments/daily-report/requirements.txt
python experiments/daily-report/collect_yahoo.py
python experiments/daily-report/collect_news.py

# 첫 실행 (수집→Gemini→검증→이미지→HTML, 게시 안 함)
python experiments/daily-report/main.py --dry-run

# 미리보기 확인
start experiments/daily-report/output/report.html

# 커버 이미지 생성기만 단독 테스트 (output/test_cover.webp 생성)
python experiments/daily-report/generate_image.py

# 실제 게시 (한 번만 사람이 직접 확인 후 사용)
# ⚠️ 로컬 게시 시 커버 이미지 URL은 gh-pages 배포 후에만 유효하다.
#    실게시는 GitHub Actions 수동 dispatch(publish 체크)를 권장.
python experiments/daily-report/main.py --publish
```

## 자동 실행 (GitHub Actions)

`.github/workflows/test-daily-report.yml`

- `schedule: cron '0 21 * * 1-5'` = 월~금 21:00 UTC (한국시간 다음날 06:00, 금요일 장 데이터는 토요일 아침 게시)
- **실행 순서**: ① `main.py` dry-run(리포트+커버 이미지 생성) → ② 이미지 gh-pages 배포 →
  ③ jsDelivr purge + HTTP 200 확인 → ④ publish 체크 시 `publish_saved.py`로 실제 게시 → ⑤ artifact 업로드
- **일정 실행은 항상 dry-run** — 생성물(`output/`, 커버 이미지 포함)이 workflow artifact로 업로드돼 웹에서 확인할 수 있습니다.
- **수동 실행(workflow_dispatch)에서 "publish" 체크박스를 켜면 그 실행만 실제 게시**를 합니다.
  게시에는 `BLOGGER_*` 3종 시크릿과, 이미지 fallback 대비 `HF_TOKEN` 시크릿을 권장합니다.
- 정가동(매일 자동 게시)으로 전환하려면:
  1. 워크플로우의 Publish 스텝 조건을 `if: inputs.publish` → `if: github.event_name == 'schedule' || inputs.publish` 로 변경
  2. 또는 그대로 두고 수동 dispatch로만 게시

## 테스트 순서 (권장)

1. 로컬에서 3개 collector 수집 확인 → 급등주/관심종목이 실제 종목인지 육안 확인
2. 로컬 dry-run → Gemini 리포트 JSON(`image_prompt` 포함)·HTML 미리보기·커버 이미지 WebP 확인
3. OAuth 셋업 후 `verify_blogger.py`로 연결 확인
4. 워크플로우 수동 실행(dry-run) → artifact + gh-pages 이미지 URL HTTP 200 확인
5. 이슈 없으면 수동 dispatch(publish 체크)로 게시 → Blogspot에서 커버 이미지 포함 게시글 확인
6. 이후 정가동 전환