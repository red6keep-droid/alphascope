"""Blogger OAuth 연결 검증 (게시 없음)

BLOGGER_CLIENT_ID / BLOGGER_CLIENT_SECRET / BLOGGER_REFRESH_TOKEN 로 Blogger API에
접속해 blogId와 블로그 정보를 확인한다. 게시는 하지 않는다. --publish 전환 전에
반드시 1회 실행해서 확인한다.

사용법:
    python experiments/daily-report/verify_blogger.py

확인 내용:
- OAuth refresh token으로 액세스 토큰 자동 갱신 성공 여부
- 대상 블로그(기본 alpha-scope.blogspot.com) 정보 + blogId
"""

import sys

from dotenv import load_dotenv

import publish_blogger

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv()

    creds = publish_blogger._credentials()
    blog_url = publish_blogger.DEFAULT_BLOG_URL
    try:
        blog_id = publish_blogger._blog_id(creds, blog_url)
    except Exception as e:
        print(f"[검증 실패] Blogger API 호출 오류: {e}")
        print("  → 3개 값이 올바른지, 앱이 Production 상태인지, 블로그 소유자 계정으로 승인했는지 확인하세요.")
        sys.exit(1)

    print(f"[검증 성공] 인증 OK, blogId = {blog_id}")
    print(f"  대상 블로그 URL: {blog_url}")
    print("'--publish'로 실제 게시할 준비가 되었습니다.")