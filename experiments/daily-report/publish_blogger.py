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

import time

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


def find_post_by_title(title, blog_url=None, creds=None, max_results=15):
    """같은 제목의 글이 이미 게시돼 있으면 그 URL을, 없으면 None을 반환한다.

    cron 이중화(스케줄 누락 대비)로 하루에 두 번 실행될 수 있어, 같은 날짜 제목이
    이미 있으면 다시 게시하지 않는다. 제목은 report_title.daily_title()이 만든다.
    title 은 문자열 또는 목록 — 목록이면 그중 하나라도 같으면 같은 글 (report_title.match_titles: 새 · 옛 · 영문 제목, 2026-10-18).
    """
    blog_url = blog_url or os.environ.get("BLOG_URL", DEFAULT_BLOG_URL)
    creds = creds or _credentials()
    blog_id = _blog_id(creds, blog_url)
    resp = requests.get(
        f"{BLOGGER_API}/blogs/{blog_id}/posts",
        params={
            "maxResults": max_results,
            "fetchBodies": "false",
            "fetchImages": "false",
        },
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=30,
    )
    resp.raise_for_status()
    wanted = {t.strip() for t in ([title] if isinstance(title, str) else title)}
    for post in resp.json().get("items", []):
        if str(post.get("title", "")).strip() in wanted:
            return post.get("url") or post.get("id")
    return None


# 함께 보는 리포트 (검색 노출, 2026-10-18 사용자 — 가이드라인 10-5): 글끼리 HTML 링크로 잇는다. 게시 · 갱신 때 최근 글 목록을 읽어
# 같은 연재의 바로 앞 글 + 다른 두 연재의 최신 글 + 연재 목록 화면. 실패해도 게시는 그대로 한다(링크 없이).
SERIES = [("데일리 브리핑", "미국 증시 리포트"), ("엔비디아", "엔비디아 리포트"), ("트럼프 트렌드", "트럼프 SNS 트렌드")]   # (블로거 라벨, 목록 이름) — 라벨은 build_theme.NAV_LABELS 와 같다


def related_html(labels, self_titles, blog_url=None, creds=None):
    import html as _h
    from urllib.parse import quote
    blog_url = (blog_url or os.environ.get("BLOG_URL", DEFAULT_BLOG_URL)).replace("http://", "https://").rstrip("/")
    creds = creds or _credentials()
    blog_id = _blog_id(creds, blog_url)
    r = requests.get(f"{BLOGGER_API}/blogs/{blog_id}/posts", params={"maxResults": 25, "fetchBodies": "false", "fetchImages": "false"},
                     headers={"Authorization": f"Bearer {creds.token}"}, timeout=30)
    r.raise_for_status()
    own = {t.strip() for t in self_titles}
    posts = [p for p in r.json().get("items", []) if str(p.get("title", "")).strip() not in own and p.get("url")]
    mine = next((lb for lb, _ in SERIES if lb in (labels or [])), None)
    picks = []
    for lb, _ in sorted(SERIES, key=lambda x: x[0] != mine):   # 같은 연재 앞 글이 맨 위
        p = next((p for p in posts if lb in (p.get("labels") or [])), None)
        if p:
            picks.append(p)
    if not picks:
        return ""
    li = "".join(f'<li style="margin:0;line-height:34px;"><a href="{_h.escape(p["url"])}" style="color:#111;">{_h.escape(str(p["title"]).strip().replace(" — ", " "))}</a></li>' for p in picks)
    lists = " · ".join(f'<a href="{blog_url}/search/label/{quote(lb)}" style="color:#111;">{_h.escape(name)}</a>' for lb, name in SERIES)
    return ('<div data-related="1" style="margin:28px 0 0;padding-top:14px;border-top:1px solid #E2E8F0;font-size:16px;line-height:24px;">'
            '<div style="font-size:14px;line-height:20px;color:#6B7280;margin:0 0 4px;">함께 보는 리포트</div>'
            f'<ul style="list-style:none;margin:0 0 6px;padding:0;">{li}</ul>'
            f'<div style="font-size:14px;line-height:20px;color:#6B7280;">리포트 목록 : {lists}</div></div>')


def with_related(content, labels, self_titles, blog_url=None, creds=None):
    """본문 끝에 함께 보는 리포트를 붙인다. 이미 붙어 있으면(갱신) 새로 바꾼다. 목록을 못 읽으면 본문 그대로."""
    import re as _re
    content = _re.sub(r'<div data-related="1".*\Z', "", content, flags=_re.S)   # 맨 끝 블록만 붙이므로 끝까지 지운다
    try:
        return content + related_html(labels, self_titles, blog_url, creds)
    except Exception as e:  # noqa: BLE001
        print(f"[게시] 함께 보는 리포트 생략 ({str(e)[:80]})")
        return content


def publish(title, content, labels=None, blog_url=None, dry_run=False, slug_title=None):
    """새 글 게시. slug_title 이 있으면 그 영문 제목으로 먼저 올려 주소를 영문으로 정하고, 바로 진짜 제목으로 바꾼다
    (2026-10-18 시험: 제목을 바꿔도 Blogger 주소는 처음 것 그대로 — 검색 노출, 가이드라인 10-5). 바꾸기에 실패해 영문 제목 글이 남아도
    다음 실행이 report_title.match_titles 로 찾아 진짜 제목으로 갱신한다."""
    blog_url = blog_url or os.environ.get("BLOG_URL", DEFAULT_BLOG_URL)
    labels = labels or LABELS

    payload = {
        "kind": "blogger#post",
        "title": slug_title or title,
        "content": content,
        "labels": labels,
    }

    if dry_run:
        print("[게시 dry-run] 게시 대신 미리보기만 확인. title:", title)
        return None

    creds = _credentials()
    blog_id = _blog_id(creds, blog_url)
    content = payload["content"] = with_related(content, labels, [title] + ([slug_title] if slug_title else []), blog_url, creds)
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
    if slug_title and slug_title != title:
        for attempt in range(3):   # 영문 제목이 피드에 오래 남지 않게 바로 바꾼다
            r = requests.put(f"{BLOGGER_API}/blogs/{blog_id}/posts/{post['id']}",
                             headers={"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"},
                             json={"kind": "blogger#post", "id": post["id"], "title": title, "content": content, "labels": labels}, timeout=60)
            if r.ok:
                post_url = r.json().get("url") or post_url
                break
            print(f"[게시] 제목 바꾸기 실패 {r.status_code} (시도 {attempt + 1}/3)")
            time.sleep(5)
        else:
            r.raise_for_status()
    print(f"[게시 완료] {post_url}")
    return post_url
