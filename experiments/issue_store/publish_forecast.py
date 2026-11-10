"""증시 전망 고정 페이지 게시 — 공개 전망 n장 + 목록 1장 (기획 증시-전망-기획 5절 2 · 14-1 5, 2026-11-08).

    python experiments/issue_store/publish_forecast.py          # 실제 게시 (forecast_daily.py 가 만든 output/forecast/*.html)
    python experiments/issue_store/publish_forecast.py --dry    # 무엇을 만들고 / 갱신할지만

종목 고정 페이지(stock-radar/publish_pages.py)와 같은 방식:
- 주소는 영문 — 처음 만들 때 제목을 slug(`forecast-2`)로 만들어 주소(/p/forecast-2.html)를 정하고 바로 한글 제목(질문)으로 바꾼다.
- 이미 있는 페이지는 주소로 찾아 본문 · 제목만 바꾼다. 바뀐 것이 없으면 쓰지 않는다(해시, 운영지침 D2-2).
- 429 는 기다렸다 다시, 끝까지 429 면 이 실행의 나머지 쓰기를 멈춘다.
게시 대상 = hypotheses/EH-*.json 의 공개 전망(publish 가 False 아님)만 — forecast_daily 와 같은 고르기. 목업 모듈은 읽지 않는다.
인증 = 데일리 publish_blogger 와 같은 BLOGGER_* 환경 변수. AI 0.
"""
import glob
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "daily-report"))
import hypo_pages as H  # noqa: E402

assert "forecast_cases" not in sys.modules, "목업 모듈을 읽으면 안 된다 (가상 숫자 차단)"

OUT = os.path.join(HERE, "output", "forecast")
HASHES = os.path.join(HERE, "output", "forecast_page_hashes.json")   # 워크플로가 nvda-state 의 forecast/ 에서 꺼내고 넣는다
LIST_TITLE = "증시 전망"   # 목록 페이지 한글 제목 = 홈 카드 이름


def _norm(u):
    return str(u or "").replace("http://", "https://").rstrip("/")


def _digest(title, content):
    return hashlib.sha1((title + "\n" + content).encode("utf-8")).hexdigest()


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def targets():
    """(키 = slug, 한글 제목, 영문 제목, 주소, 본문 파일) — 본문이 없는 것은 건너뛴다(그날 판정 실패 등)."""
    regs = H.load_regs(os.environ.get("STATE_DIR"))   # 손으로 만든 hypotheses/ + 자동 등록(상태 저장소 records/hypotheses, 워크플로 STATE_DIR) (2026-11-11)
    rows = [(fc["slug"], fc["title"]) for r in regs for fc in H.forecasts(r, public=True)] + [(H.LIST_SLUG, LIST_TITLE)]
    out = []
    for slug, title in rows:
        path = os.path.join(OUT, f"{slug}.html")
        if os.path.exists(path):
            out.append((slug, title, slug, H.page_url(slug), path))
        else:
            print(f"[forecast-pages] {slug}: 본문 없음 — 건너뜀")
    return out


def _call(requests, method, url, **kw):
    for wait in (0, 20, 45, 90, 180):
        if wait:
            print(f"[forecast-pages] 429 — {wait}초 뒤 다시")
            time.sleep(wait)
        r = getattr(requests, method)(url, timeout=60, **kw)
        if r.status_code != 429:
            r.raise_for_status()
            return r
    r.raise_for_status()
    return r


def publish(dry=False):
    rows = targets()
    if dry:
        hashes = _load(HASHES, {})
        for key, title, slug, url, path in rows:
            content = open(path, encoding="utf-8").read()
            print(f"[forecast-pages] {'변경 없음' if hashes.get(key) == _digest(title, content) else '게시'} {key}: {title} → {url}")
        return True
    import requests
    import publish_blogger
    import notify

    creds = publish_blogger._credentials()
    blog_id = publish_blogger._blog_id(creds, os.environ.get("BLOG_URL", publish_blogger.DEFAULT_BLOG_URL))
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    base = f"{publish_blogger.BLOGGER_API}/blogs/{blog_id}/pages"
    items, token = [], None
    while True:   # 페이지 목록은 쪽으로 온다 — 끝까지 읽어야 이미 있는 페이지를 중복으로 만들지 않는다 (종목 페이지 2026-10-18 사고)
        params = {"fetchBodies": "false", "status": ["live", "draft"], "maxResults": 50}
        if token:
            params["pageToken"] = token
        j = _call(requests, "get", base, params=params, headers=headers).json()
        items += j.get("items", [])
        token = j.get("nextPageToken")
        if not token:
            break
    by_url = {_norm(p.get("url")): p for p in items}
    hashes = _load(HASHES, {})
    made = updated = unchanged = failed = 0
    for key, title, slug, url, path in rows:
        content = open(path, encoding="utf-8").read()
        digest = _digest(title, content)
        page = by_url.get(_norm(url))
        if page and hashes.get(key) == digest:
            unchanged += 1
            continue
        try:
            if page:
                r = _call(requests, "put", f"{base}/{page['id']}", headers=headers, json={"kind": "blogger#page", "id": page["id"], "title": title, "content": content})
                updated += 1
            else:
                new = _call(requests, "post", base, headers=headers, json={"kind": "blogger#page", "title": slug, "content": content}).json()
                time.sleep(2)
                r = _call(requests, "put", f"{base}/{new['id']}", headers=headers, json={"kind": "blogger#page", "id": new["id"], "title": title, "content": content})
                if _norm(r.json().get("url")) != _norm(url):
                    print(f"::warning::[forecast-pages] {key}: 주소가 계획({url})과 다름 → {r.json().get('url')}")
                made += 1
            hashes[key] = digest
            print(f"[forecast-pages] {'갱신' if page else '생성'} {key}: {r.json().get('url')}")
        except Exception as e:  # noqa: BLE001 — 한 장 실패가 나머지를 막지 않게
            failed += 1
            print(f"::warning::[forecast-pages] {key} 실패: {str(e)[:200]}")
            if getattr(getattr(e, "response", None), "status_code", None) == 429:
                notify.event("블로거 429", f"증시 전망 페이지 {key} — 백오프 후에도 429, 이 실행의 나머지 쓰기 중단")
                break
        time.sleep(4)
    os.makedirs(os.path.dirname(HASHES), exist_ok=True)
    with open(HASHES, "w", encoding="utf-8") as f:
        json.dump(hashes, f, ensure_ascii=False, indent=0, sort_keys=True)
    print(f"[forecast-pages] 생성 {made} · 갱신 {updated} · 변경 없음 {unchanged} · 실패 {failed}")
    if failed:
        try:
            import forecast_alerts as FA
            FA.save_failed("Blogger 증시 전망 페이지", RuntimeError(f"{failed}장 실패"))
        except Exception:  # noqa: BLE001 — 알림이 죽어도 게시 결과는 그대로
            pass
    return failed == 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(HERE, "..", "..", ".env"))
    except ImportError:
        pass
    sys.exit(0 if publish(dry="--dry" in sys.argv) else 1)
