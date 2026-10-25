"""기사 첫 문단 — 뉴스 요약 줄이 제목을 되풀이하지 않게 (공용, 2026-10-25 people-radar/article.py 에서 옮김).

Google News 주소를 원래 기사 주소로 풀고(batchexecute), 기사의 설명(meta description) + 첫 문단 몇 개를 짧게 가져온다.
- AI 입력으로만 쓴다. 기사 문장을 화면 · 공개 브랜치에 옮기지 않는다 — 모델이 우리 말로 사실만 요약한다 (운영지침 4-3 · D3-1f)
- 캐시: 부르는 쪽이 정한 파일(주소 → {real, lead}) — 같은 기사를 다시 받지 않는다. 깃에 넣지 않는다(각 data/)
- 유료 · 차단 · 자바스크립트 기사는 빈 값 → 요약 줄 없이
쓰는 곳: 인물 발언 보도 신호(people-radar/article.py) · 종목 페이지 기사 분류(stock-radar/collect_news.py).
"""

import concurrent.futures
import html
import json
import os
import re
import urllib.parse

import certifi
import requests

LEAD_MAX = 900
TIMEOUT = 20
WORKERS = 3   # 6 → 3: 구글 뉴스 주소 풀기가 한꺼번에 몰리면 429 (2026-10-25)
UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")}
_BAD = re.compile(r"(\{|\}|css-|Sign in|Subscribe|cookie|newsletter|Posts from this topic|All rights reserved|javascript)", re.I)


def _cache(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(c, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False)


class RateLimited(Exception):
    """구글 뉴스가 요청을 막았다 (429 · sorry 페이지) — 이번 실행은 남은 주소를 건너뛰고, 캐시에 남기지 않아 다음 실행에서 다시."""


def decode_gnews(url):
    """news.google.com/rss/articles/<id> → 원래 기사 주소. 실패하면 None."""
    if "news.google.com" not in (url or ""):
        return url
    aid = urllib.parse.urlparse(url).path.rstrip("/").split("/")[-1]
    r = requests.get(f"https://news.google.com/articles/{aid}", headers=UA, timeout=TIMEOUT, verify=certifi.where())
    if r.status_code == 429 or "/sorry/" in r.url:
        raise RateLimited("google 429")
    page = r.text
    sg, ts = re.search(r'data-n-a-sg="([^"]+)"', page), re.search(r'data-n-a-ts="([^"]+)"', page)
    if not (sg and ts):
        return None
    inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
             aid, int(ts.group(1)), sg.group(1)]
    body = "f.req=" + urllib.parse.quote(json.dumps([[["Fbv4je", json.dumps(inner), None, "generic"]]]))
    r = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute", data=body, timeout=TIMEOUT, verify=certifi.where(),
                      headers={**UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    arr = json.loads(r.text.split("\n\n")[1])[:-2]
    return json.loads(arr[0][2])[1]


def lead_text(real_url):
    """기사 설명 + 첫 문단들 (LEAD_MAX 자). 메뉴 · 스타일 · 구독 문구는 거른다."""
    t = requests.get(real_url, headers=UA, timeout=TIMEOUT, verify=certifi.where()).text
    parts = []
    m = re.search(r'<meta[^>]+(?:name|property)="(?:og:)?description"[^>]+content="([^"]+)"', t)
    if m:
        parts.append(html.unescape(m.group(1)).strip())
    for x in re.findall(r"<p[^>]*>(.*?)</p>", t, re.S):
        x = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", x))).strip()
        if 80 <= len(x) <= 700 and not _BAD.search(x) and x not in parts:
            parts.append(x)
        if sum(len(p) for p in parts) >= LEAD_MAX:
            break
    return " ".join(parts)[:LEAD_MAX]


_blocked = False


def _one(url):
    global _blocked
    if _blocked:
        return None
    try:
        real = decode_gnews(url)
        return {"real": real, "lead": lead_text(real) if real else ""}
    except RateLimited:
        _blocked = True
        return None
    except Exception as e:  # noqa: BLE001
        return {"real": None, "lead": "", "error": str(e)[:80]}


def leads(urls, cache_path):
    """주소 목록 → {주소: 첫 문단}. 캐시(cache_path)에 있으면 그대로, 없는 것만 병렬로 받는다."""
    c = _cache(cache_path)
    need = [u for u in dict.fromkeys(urls) if u and u not in c]
    if need:
        with concurrent.futures.ThreadPoolExecutor(WORKERS) as ex:
            for u, v in zip(need, ex.map(_one, need)):
                if v is not None:   # 막혀서 못 본 주소는 캐시에 남기지 않는다 — 다음 실행에서 다시 (2026-10-25: 한 번에 400건을 받다 구글 429, 실패가 영구 캐시됐다)
                    c[u] = v
        _save(c, cache_path)
        ok = sum(1 for u in need if (c.get(u) or {}).get("lead"))
        print(f"[article] 기사 첫 문단 {ok}/{len(need)} 받음 (캐시 {len(c)})" + (" · 구글 뉴스가 막아 나머지는 다음 실행에서" if _blocked else ""))
    return {u: (c.get(u) or {}).get("lead", "") for u in urls}
