"""Blogger API v3 클라이언트 (댓글 감지용)

daily-report 의 publish_blogger.py 와 동일한 OAuth refresh token 방식으로 인증한다.

환경변수:
    BLOGGER_CLIENT_ID / BLOGGER_CLIENT_SECRET / BLOGGER_REFRESH_TOKEN (필수)
    BLOG_URL (선택, 기본 alpha-scope.blogspot.com)
"""

import os

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

BLOGGER_API = "https://www.googleapis.com/blogger/v3"
TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/blogger"]
DEFAULT_BLOG_URL = "http://alpha-scope.blogspot.com/"
REQUIRED_ENV = ["BLOGGER_CLIENT_ID", "BLOGGER_CLIENT_SECRET", "BLOGGER_REFRESH_TOKEN"]


def _credentials():
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            "다음 환경 변수가 필요합니다: " + ", ".join(missing)
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


class BloggerClient:
    """댓글/게시글 조회용 최소 클라이언트"""

    def __init__(self):
        self.creds = _credentials()
        self._blog_id = None

    def _headers(self):
        return {"Authorization": f"Bearer {self.creds.token}"}

    @property
    def blog_id(self):
        if self._blog_id is None:
            blog_url = os.environ.get("BLOG_URL", DEFAULT_BLOG_URL)
            resp = requests.get(
                f"{BLOGGER_API}/blogs/byurl",
                params={"url": blog_url},
                headers=self._headers(),
                timeout=30,
            )
            resp.raise_for_status()
            self._blog_id = resp.json()["id"]
        return self._blog_id

    def self_id(self):
        """블로그 소유자(API 호출자)의 author id"""
        resp = requests.get(f"{BLOGGER_API}/users/self", headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()["id"]

    def list_comments(self):
        """블로그 전체 댓글 목록 (페이지 전체 수집)"""
        items = []
        token = None
        while True:
            params = {"fetchBodies": "true", "maxResults": "100"}
            if token:
                params["pageToken"] = token
            resp = requests.get(
                f"{BLOGGER_API}/blogs/{self.blog_id}/comments",
                headers=self._headers(),
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            items.extend(data.get("items", []))
            token = data.get("nextPageToken")
            if not token:
                break
        return items

    def get_post(self, post_id):
        resp = requests.get(
            f"{BLOGGER_API}/blogs/{self.blog_id}/posts/{post_id}",
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_latest_post(self):
        resp = requests.get(
            f"{BLOGGER_API}/blogs/{self.blog_id}/posts",
            headers=self._headers(),
            params={"maxResults": "1"},
            timeout=30,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            raise RuntimeError("블로그에 게시글이 없습니다.")
        return items[0]