"""Blogger API v3 게시 (OAuth 2.0 Client ID + Refresh Token)

사용자 계정 기반 OAuth 2.0 방식이다. 데스크톱 OAuth 클라이언트로 1회 브라우저 승인을
받아 refresh token을 발급받고(setup_oauth.py), 이후에는 refresh token으로
액세스 토큰을 자동 갱신해 게시한다.

환경 변수 (로컬 .env / GitHub Actions Secrets):
    BLOGGER_CLIENT_ID       OAuth 클라이언트 ID
    BLOGGER_CLIENT_SECRET   OAuth 클라이언트 시크릿
    BLOGGER_REFRESH_TOKEN   1회 승인으로 발급받은 refresh token

셋업:
1. Google Cloud Console에서 OAuth 클라이언트 ID(데스크톱 앱) 생성, client_secret.json 다운로드
2. Blogger API 활성화, OAuth consent screen을 Production으로 게시
3. python experiments/daily-report/setup_oauth.py <client_secret.json 경로>
   → refresh token 발급
4. 세 값을 .env / GitHub Secrets에 등록
"""

import os

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

BLOGGER_API = "https://www.googleapis.com/blogger/v3"
TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/blogger"]
DEFAULT_BLOG_URL = "http://alpha-scope.blogspot.com/"
LABELS = ["데일리 브리핑", "미국 증시", "자동 리포트"]

REQUIRED_ENV = ["BLOGGER_CLIENT_ID", "BLOGGER_CLIENT_SECRET", "BLOGGER_REFRESH_TOKEN"]


def _credentials():
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            "다음 환경 변수가 필요합니다: "
            + ", ".join(missing)
            + " (setup_oauth.py로 refresh token을 발급받아 .env / GitHub Secrets에 등록)"
        )
    creds = Credentials(
        token=None,
        refresh_token=os.environ["BLOGGER_REFRESH_TOKEN"],
        token_uri=TOKEN_URI,
        client_id=os.environ["BLOGGER_CLIENT_ID"],
        client_secret=os.environ["BLOGGER_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def _blog_id(creds, blog_url):
    resp = requests.get(
        f"{BLOGGER_API}/blogs/byurl",
        params={"url": blog_url},
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def publish(title, content, labels=None, blog_url=None, dry_run=False):
    blog_url = blog_url or os.environ.get("BLOG_URL", DEFAULT_BLOG_URL)
    labels = labels or LABELS

    payload = {
        "kind": "blogger#post",
        "title": title,
        "content": content,
        "labels": labels,
    }

    if dry_run:
        print("[게시 dry-run] 게시 대신 미리보기만 확인. title:", title)
        return None

    creds = _credentials()
    blog_id = _blog_id(creds, blog_url)
    resp = requests.post(
        f"{BLOGGER_API}/blogs/{blog_id}/posts/",
        headers={
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    post = resp.json()
    post_url = post.get("url")
    print(f"[게시 완료] {post_url}")
    return post_url
