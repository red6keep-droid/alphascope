"""숫자 붙은 중복 고정 페이지 찾기 · 지우기.

11-21 www.newfact.app 연결 직후 publish_pages 가 기존 페이지를 못 찾아(새 도메인 주소 비교) 같은 이름 페이지를 다시 만들었다 →
Blogger 가 `/p/tesla-tsla-stock_0239068317.html` 처럼 뒤에 숫자를 붙임(20쪽, 0be3ab26 로 고침). 공개 주소는 404 — 지워졌는지 초안인지 API 로만 안다.

지우는 조건(둘 다): 주소 끝이 `_숫자.html` · 숫자 뗀 원래 주소의 페이지가 live 로 있다. 원래 주소가 없으면 지우지 않고 알리기만.
    python experiments/stock-radar/dup_pages.py            # 찾기만
    python experiments/stock-radar/dup_pages.py --delete   # 지우기
"""
import argparse
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "daily-report"))
import requests  # noqa: E402
import publish_blogger as PB  # noqa: E402

SUFFIX = re.compile(r"_\d{6,}\.html$")


def path_of(u):
    return re.sub(r"^https?://[^/]+", "", u or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", action="store_true")
    a = ap.parse_args()
    creds = PB._credentials()
    blog_id = PB._blog_id(creds, os.environ.get("BLOG_URL", PB.DEFAULT_BLOG_URL))
    h = {"Authorization": f"Bearer {creds.token}"}
    base = f"{PB.BLOGGER_API}/blogs/{blog_id}/pages"
    items, tok = [], None
    while True:
        p = {"fetchBodies": "false", "status": ["live", "draft"], "maxResults": 50}
        if tok:
            p["pageToken"] = tok
        r = requests.get(base, params=p, headers=h, timeout=60)
        r.raise_for_status()
        j = r.json()
        items += j.get("items", [])
        tok = j.get("nextPageToken")
        if not tok:
            break
    live = {path_of(x.get("url")) for x in items if x.get("status") == "LIVE"}
    dups = [x for x in items if SUFFIX.search(x.get("url") or "")]
    print(f"[중복] 전체 페이지 {len(items)}쪽 (live {sum(x.get('status') == 'LIVE' for x in items)} · 초안 {sum(x.get('status') == 'DRAFT' for x in items)}) · 숫자 붙은 주소 {len(dups)}쪽")
    gone = kept = 0
    for x in dups:
        orig = SUFFIX.sub(".html", path_of(x["url"]))
        ok = orig in live
        print(f"  {x.get('status')} {path_of(x['url'])} · 제목 {x.get('title', '')[:30]} · 원래 주소 {'있음' if ok else '없음 — 지우지 않음'}")
        if a.delete and ok:
            r = PB._write("delete", f"{base}/{x['id']}", headers=h, timeout=60)
            print(f"    지움 → {r.status_code}")
            gone += r.status_code in (200, 204)
            time.sleep(4)
        elif not ok:
            kept += 1
    print(f"[중복] {'지움 ' + str(gone) + '쪽 · ' if a.delete else '찾기만 · '}원래 주소 없어 남김 {kept}쪽")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
