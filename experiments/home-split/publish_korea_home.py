"""한국 홈 고정 페이지 만들기 (홈 나누기 H35, 2026-11-10 사용자).

    python experiments/home-split/publish_korea_home.py            # 확인만 (블로그에 쓰지 않음)
    python experiments/home-split/publish_korea_home.py --publish  # 페이지 1개 만들기 (이미 있으면 제목 · 본문만 맞춤)

- 주소 /p/korea.html, 제목 build_theme.KR_HOME_TITLE. 테마는 이 제목으로 한국 화면을 알아보고
  홈과 같은 카드 화면을 한국 시장(data-home-mkt="kr")으로 그린다. 페이지 본문은 화면에 그리지 않는다.
- 주소는 영문: 처음 만들 때 영문 제목(korea)으로 만들어 주소를 정하고 바로 한글 제목으로 바꾼다 (publish_pages.py 와 같은 방법).
- 한 번만 돌리면 된다. 블로거 쓰기 = 생성 1 + 제목 바꾸기 1.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments", "daily-report"))

from build_theme import KR_HOME_SLUG, KR_HOME_TITLE  # noqa: E402
import publish_blogger  # noqa: E402

# 본문 = 검색용 설명 한 단락. 화면에는 테마가 카드를 그리므로 보이지 않는다 (블로거 페이지 본문이 비면 저장이 안 된다)
CONTENT = ('<p data-seo-lead="1">코스피 · 코스닥 마감과 한국 증시 리포트, 시가총액 상위 종목 주가, '
           '실적 발표 일정, 급락장에서 버틴 종목을 매 거래일 장 마감 뒤 정리합니다.</p>')


def _norm(u):
    return (u or "").split("?")[0].replace("http://", "https://").rstrip("/")


def main(publish):
    import requests

    blog_url = os.environ.get("BLOG_URL", publish_blogger.DEFAULT_BLOG_URL)
    want = _norm(f"{blog_url.rstrip('/')}/p/{KR_HOME_SLUG}.html")
    creds = publish_blogger._credentials()
    blog_id = publish_blogger._blog_id(creds, blog_url)
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    base = f"{publish_blogger.BLOGGER_API}/blogs/{blog_id}/pages"
    items, token = [], None
    while True:   # 페이지 목록은 쪽으로 온다 — 끝까지 읽어야 중복을 만들지 않는다 (publish_pages 2026-10-18 사고)
        params = {"fetchBodies": "false", "status": ["live", "draft"], "maxResults": 50}
        if token:
            params["pageToken"] = token
        r = requests.get(base, params=params, headers=headers, timeout=60)
        r.raise_for_status()
        j = r.json()
        items += j.get("items", [])
        token = j.get("nextPageToken")
        if not token:
            break
    page = next((p for p in items if _norm(p.get("url")) == want), None)
    print(f"[korea] 주소 {want} · 제목 '{KR_HOME_TITLE}' · {'있음 (id ' + page['id'] + ')' if page else '없음'}")
    if not publish:
        print("[korea] 확인만 — 만들려면 --publish")
        return True
    body = {"kind": "blogger#page", "title": KR_HOME_TITLE, "content": CONTENT}
    if page:
        if page.get("title") == KR_HOME_TITLE:
            print("[korea] 이미 맞음 — 쓰지 않음")
            return True
        r = requests.put(f"{base}/{page['id']}", headers=headers, json=dict(body, id=page["id"]), timeout=60)
        r.raise_for_status()
        print(f"[korea] 제목 맞춤: {r.json().get('url')}")
        return True
    r = requests.post(base, headers=headers, json={"kind": "blogger#page", "title": KR_HOME_SLUG, "content": CONTENT}, timeout=60)
    r.raise_for_status()
    new = r.json()
    time.sleep(2)
    r = requests.put(f"{base}/{new['id']}", headers=headers, json=dict(body, id=new["id"]), timeout=60)
    r.raise_for_status()
    got = r.json().get("url")
    print(f"[korea] 만듦: {got}" + ("" if _norm(got) == want else f"  ⚠ 계획 주소({want})와 다름 — 테마 메뉴 주소를 고쳐야 함"))
    return True


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, ".env"))
    sys.exit(0 if main("--publish" in sys.argv) else 1)
