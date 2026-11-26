"""Newfact 뉴스 발행기 — 뉴스 수집기 글(블로그 저장소 news-text-blog posts)을 블로그 새 글로 (2026-11-24 사용자 "그렇게 해").

블로그 AI 0 — 글은 수집기가 쓰고, 여기서는 읽기 · 검사 · 그리기(news_render) · 발행 · 기준일 고치기만.
기획 = 비공개 doc/기획/뉴스-글-발행-기획.md (3절 발행기 · 2절 비교 칸), 요청 문서 = News-text-doc/요청-알파스코프-뉴스-글-발행.md.

    python experiments/news-posts/publish_news.py publish --draft        # 새 글 → Blogger 초안 (시험)
    python experiments/news-posts/publish_news.py publish                # 새 글 → 공개 발행 (운영)
    python experiments/news-posts/publish_news.py refresh [--draft]      # 장 마감 뒤: 아침 글의 관련 종목 표를 그날 값으로 고쳐 씀
    python experiments/news-posts/publish_news.py publish --dry --gcloud <계정>   # Blogger 없이 output/publish/ 에 HTML 만 (로컬 확인)

기준일 (2026-11-24 사용자 "오전 기사는 우측에 기준일 표시하고 나가, 오후 때 기준일 다시 갱신하고 새로 고쳐"):
- 관련 종목 표 = 한국 장이 끝난(15:40 KST 뒤) 마지막 날 값. 아침 글은 전 거래일 값으로 나가고, 표 제목 줄 오른쪽에 `11.23 종가 기준`.
- refresh 가 기준일 < 글 날짜인 글을 다시 그려 같은 주소에 고쳐 쓴다(PUT 1회). 고치기 전 · 뒤 값은 records.jsonl 에 둘 다 남긴다.
- 방문자 요청 0 — 값은 글 HTML 에 박힌다.

멈추는 규칙:
- 이미 나간 글(본문 data-news-post = slug)은 다시 내지 않는다.
- 글 날짜가 사흘보다 오래되면 내지 않는다(`지남` 기록).
- 검사(권유 말투 · 제목 금지 낱말 · 빈 본문)에 걸리면 그 글만 내지 않고 exit 1(워크플로가 알린다). 다른 글은 낸다.
- Blogger 가 새 글을 거절(429)하면 멈추고 다음 실행에 맡긴다.
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, ".."))
sys.path.insert(0, os.path.join(BASE, "..", "daily-report"))
sys.path.insert(0, os.path.join(BASE, "..", "market-commentary"))
import news_render as NR  # noqa: E402

KST = datetime.timezone(datetime.timedelta(hours=9))
OUT = os.path.join(BASE, "output", "publish")
RAW = "https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages"
MAX_AGE_DAYS = 0   # 오늘 날짜(한국 시간) 기사만 발행 · 고쳐 씀 — 어제 이전 기사는 내지 않는다 (2026-11-24 사용자 "Newfact 에는 오늘 날짜 기사만")
GAP_LIVE, GAP_DRAFT = 600, 3   # 새 글 사이 — 공개는 10분(기획 3절, 11-20 새 글 거절 1회 사례), 초안은 짧게
ADVICE = re.compile(r"(?:매수|매도|사|팔|담으)세요|(?:매수|매도|투자|손절)하(?:세요|십시오|라)|비중을? ?(?:늘리|줄이)(?:세요|십시오)|추천합니다|권합니다|권유합니다|지금이 기회")
BAD_TITLE = re.compile(r"(폭망|대폭락 임박|무조건|100% 확실|확정적 상승|떡상|떡락)")   # 시황 해설 발행기와 같은 낱말


def log(msg):
    print(f"[뉴스 발행] {msg}", flush=True)


def kst_now():
    return datetime.datetime.now(KST)


def _get_json(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "alphascope"}), timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        log(f"못 받음 {url.rsplit('/', 1)[-1]} — {str(e)[:120]}")
        return None


# ── 재료 ──────────────────────────────────────────────────────────────

def read_posts(a):
    if a.posts_json:
        return json.load(open(a.posts_json, encoding="utf-8"))
    import fetch_samples as F
    c = F.gcloud_token(a.gcloud) if a.gcloud else F.creds()
    return F.docs(c, "posts")


def read_lists():
    """종목 모아보기 목록(간단 종목 실행이 매일 올림) — 관련 종목 이름 · 주소 · 테마 구성. 시황 해설 발행기와 같은 읽는 순서."""
    lists, themes = {}, {}
    for mk in ("kr", "us"):
        for url in (f"https://alpha-scope.pages.dev/{mk}/_lists.json",
                    f"https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@quick-{mk}/{mk}/_lists.json"):
            d = _get_json(url)
            if d and d.get("rows"):
                lists.update({r["t"]: dict(r, mk=mk) for r in d["rows"]})
                themes[mk] = d.get("themes") or []
                log(f"종목 목록 {mk} {len(d['rows'])}줄")
                break
    return lists, themes


def read_links():
    iss = (_get_json(f"{RAW}/issues.json") or {}).get("issues") or []
    hyp = (_get_json(f"{RAW}/hypo.json") or {}).get("open") or []
    return iss, hyp


_closes = {}


NAVER_INDEX = {"^KS11": "KOSPI", "^KQ11": "KOSDAQ"}


def _naver_closes(sym, days=20):
    """네이버 일봉 종가 {날짜: 종가} 최근 days 일 — 한국 지수 · 종목의 예비(collect_kr 와 같은 출처 · 같은 주소). 못 받으면 {}."""
    code = NAVER_INDEX.get(sym) or (sym.split(".")[0] if sym.endswith((".KS", ".KQ")) else None)
    if not code:
        return {}
    end = kst_now().date()
    start = end - datetime.timedelta(days=days)
    url = (f"https://api.finance.naver.com/siseJson.naver?symbol={code}&requestType=1"
           f"&startTime={start:%Y%m%d}&endTime={end:%Y%m%d}&timeframe=day")
    try:
        txt = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=10).read().decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        log(f"네이버 못 받음 {sym}: {str(e)[:80]}")
        return {}
    return {f"{d[:4]}-{d[4:6]}-{d[6:]}": float(c) for d, c in re.findall(r'\["(\d{8})",\s*[0-9.]+,\s*[0-9.]+,\s*[0-9.]+,\s*([0-9.]+)', txt)}


def closes_of(sym):
    """[(날짜, 종가)] 1년. 사슬 = 블로그 시세 규칙과 같게 (2026-11-26 사용자 "예비 2개 있다"):
    한국 지수 · 종목 = 야후 → 네이버(최근 20일 — 빈 날짜를 메우고 다른 종가는 네이버 값으로, collect_kr._fix_last 와 같은 규칙.
    한국투자증권 대조 파일은 집 IP 실행에만 있어 여기선 없음) · 미국 = 야후 → 실패하면 price_source 예비 사슬(FRED · Polygon · Twelve Data …).
    11-26 아침 야후 코스피 · 코스닥에 11-25 가 빠져 뉴스 기준일이 11-24 로 밀렸던 것. 못 받으면 빈 목록(그 종목만 빠진다)."""
    if sym not in _closes:
        rows = []
        try:
            import yfinance as yf
            h = yf.Ticker(sym).history(period="1y", auto_adjust=False)["Close"].dropna()
            rows = [(str(i.date()), float(v)) for i, v in h.items()]
        except Exception as e:  # noqa: BLE001
            log(f"야후 못 받음 {sym}: {str(e)[:80]}")
        nav = _naver_closes(sym)
        if nav:
            have = dict(rows)
            fixed = [d for d, c in nav.items() if d not in have or abs(have[d] - c) > 1e-6 * max(1.0, c)]
            if fixed:
                have.update(nav)
                rows = sorted(have.items())
                log(f"{sym} 네이버로 메움 · 바꿈: {', '.join(sorted(fixed)[-5:])}")
        elif not rows and not NAVER_INDEX.get(sym) and not sym.endswith((".KS", ".KQ")):
            try:
                import price_source
                rows = price_source.daily_closes(sym, str(kst_now().date() - datetime.timedelta(days=370)))
                if rows:
                    log(f"{sym} 야후 대신 예비 사슬 {len(rows)}일")
            except Exception as e:  # noqa: BLE001
                log(f"예비 사슬 못 받음 {sym}: {str(e)[:80]}")
        _closes[sym] = rows
    return _closes[sym]


def closed_through(now):
    """한국 장이 끝난 마지막 날 — 15:40 KST 뒤면 오늘, 아니면 어제(주말 · 휴장은 _move 가 마지막 거래일로)."""
    return now.strftime("%Y-%m-%d") if now.hour * 60 + now.minute >= 15 * 60 + 40 else (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")


# ── 검사 · 그리기 ──────────────────────────────────────────────────────

def check(post):
    bad = []
    for k in ("title", "body", "date", "slug"):
        if not str(post.get(k) or "").strip():
            bad.append(f"빈 칸 {k}")
    for where in ("title", "summary", "body"):
        m = ADVICE.search(str(post.get(where) or ""))
        if m:
            bad.append(f"권유 말투 ({where}): {m.group(0)}")
    m = BAD_TITLE.search(str(post.get("title") or ""))
    if m:
        bad.append(f"제목 금지 낱말: {m.group(0)}")
    return bad


def draw(post, lists, themes, issues, forecasts, now):
    market = NR.same_day(post, lists, closes_of, closed_through(now), now_kst=now, themes=themes)
    stored, html, meta = NR.render(post, market, lists, issues, forecasts)
    rows = [{"t": x["ticker"], "chg": x["chg_pct"], "vs": x.get("vs"), "base": x.get("base")} for x in market.get("stocks") or []]
    return stored, html, {**meta, "us_basis": market.get("us_basis"), "rows": rows}


def record(kind, post, meta, extra=None):
    """기록 한 줄 — 워크플로가 상태 저장소에 붙인다(기획 1절 `기록`: 사건 분류 × 관련 종목 × 그날 움직임)."""
    os.makedirs(OUT, exist_ok=True)
    row = {"kind": kind, "at": kst_now().isoformat(timespec="seconds"), "postId": post.get("id"), "slug": post.get("slug"),
           "date": post.get("date"), "cat": post.get("cat"), "direction": post.get("direction"),
           "basis": meta.get("basis"), "us_basis": meta.get("us_basis"), "stocks": meta.get("rows"), **(extra or {})}
    with open(os.path.join(OUT, "records.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ── Blogger ──────────────────────────────────────────────────────────

class Blog:
    def __init__(self):
        import publish_blogger as PB
        self.PB = PB
        self.creds = PB._credentials()
        self.id = PB._blog_id(self.creds, os.environ.get("BLOG_URL", PB.DEFAULT_BLOG_URL))

    def _h(self):
        return {"Authorization": f"Bearer {self.creds.token}", "Content-Type": "application/json"}

    def existing(self, drafts):
        """라벨 글(공개 · 초안) → {slug: Blogger 글}. 본문의 data-news-post 표시로 찾는다(제목은 수집기가 고칠 수 있어 쓰지 않는다)."""
        import requests
        out, tok = {}, None
        status = ["live", "draft"] if drafts else ["live"]
        while True:
            params = {"labels": NR.LABEL, "maxResults": 50, "fetchBodies": "true", "fetchImages": "false", "view": "ADMIN", "status": status}
            if tok:
                params["pageToken"] = tok
            r = requests.get(f"{self.PB.BLOGGER_API}/blogs/{self.id}/posts", params=params, headers=self._h(), timeout=60)
            r.raise_for_status()
            j = r.json()
            for p in j.get("items") or []:
                m = re.search(r'data-news-post="([^"]+)"', p.get("content") or "")
                if m and m.group(1) not in out:
                    out[m.group(1)] = p
            tok = j.get("nextPageToken")
            if not tok or len(out) >= 300:   # 최근 300편이면 사흘 치를 넉넉히 덮는다
                return out

    def create(self, title, html, slug, draft):
        if not draft:   # 공개 = 영문 주소로 먼저 올리고 한글 제목으로 바꾼다(기획 3절)
            return self.PB.publish(title, html, labels=[NR.LABEL], slug_title=slug.replace("-", " "))
        r = self.PB._write("post", f"{self.PB.BLOGGER_API}/blogs/{self.id}/posts/", params={"isDraft": "true"}, headers=self._h(),
                           json={"kind": "blogger#post", "title": title, "content": html, "labels": [NR.LABEL]}, timeout=60)
        r.raise_for_status()
        return r.json().get("url") or f"(초안 {r.json().get('id')})"

    def delete(self, post_id):
        r = self.PB._write("delete", f"{self.PB.BLOGGER_API}/blogs/{self.id}/posts/{post_id}", headers=self._h(), timeout=60)
        r.raise_for_status()

    def update(self, old, html):
        r = self.PB._write("put", f"{self.PB.BLOGGER_API}/blogs/{self.id}/posts/{old['id']}", headers=self._h(),
                           json={"kind": "blogger#post", "id": old["id"], "title": old.get("title"), "content": html, "labels": old.get("labels") or [NR.LABEL]}, timeout=60)
        r.raise_for_status()


# ── 단계 ────────────────────────────────────────────────────────────

def stage_publish(a):
    now = kst_now()
    posts = [p for p in read_posts(a) if p.get("slug")]
    log(f"수집기 글 {len(posts)}편")
    blog = None if a.dry else Blog()
    done = blog.existing(drafts=True) if blog else {}
    # 공개 발행 때 같은 글의 시험 초안이 있으면 지우고 공개로 다시 낸다(영문 주소 · 홈 카드) — 공개 글이 이미 있으면 건너뜀
    drafts = {} if a.draft else {s: bp for s, bp in done.items() if str(bp.get("status") or "").upper() == "DRAFT"}
    done = {s: bp for s, bp in done.items() if s not in drafts}
    oldest = (now.date() - datetime.timedelta(days=MAX_AGE_DAYS)).isoformat()
    todo = sorted((p for p in posts if p["slug"] not in done), key=lambda p: str(p.get("createdAt") or p.get("date")))
    if not todo:
        log("새 글 없음")
        if blog and not a.draft:
            write_card(blog)
        return 0
    lists, themes = read_lists()
    issues, forecasts = read_links()
    blocked, sent = 0, 0
    os.makedirs(OUT, exist_ok=True)
    for p in todo:
        if str(p.get("date") or "") < oldest:
            log(f"지남 — {p['slug']} ({p.get('date')}), 내지 않음")
            record("stale", p, {})
            continue
        bad = check(p)
        if bad:
            blocked += 1
            log(f"검사 걸림 — {p['slug']}: " + " · ".join(bad))
            record("blocked", p, {}, {"problems": bad})
            continue
        title, html, meta = draw(p, lists, themes, issues, forecasts, now)
        if a.dry:
            open(os.path.join(OUT, f"{p['slug']}.html"), "w", encoding="utf-8").write(html)
            log(f"dry — {title} · 기준 {meta['basis']} · 관련 종목 {len(meta['rows'])}")
            continue
        if a.limit and sent >= a.limit:
            log(f"이번 실행 상한 {a.limit}편 — 나머지는 다음 실행")
            break
        if sent:
            time.sleep(GAP_DRAFT if a.draft else GAP_LIVE)
        try:
            url = blog.create(title, html, p["slug"], a.draft)
        except Exception as e:  # noqa: BLE001
            if "429" in str(e):
                log("Blogger 새 글 거절(429) — 멈추고 다음 실행에")
                break
            raise
        if p["slug"] in drafts:   # 공개 글이 올라간 뒤에만 시험 초안을 지운다 (11-24 첫 공개 실행: 먼저 지우고 429 로 초안만 사라졌다)
            try:
                blog.delete(drafts[p["slug"]]["id"])
                log(f"시험 초안 지움 — {p['slug']}")
            except Exception as e:  # noqa: BLE001 — 초안이 남아도 공개 글은 나갔다
                log(f"시험 초안 못 지움 {p['slug']}: {str(e)[:80]}")
        sent += 1
        record("draft" if a.draft else "publish", p, meta, {"url": url})
        log(f"{'초안' if a.draft else '발행'} — {title} · 기준 {meta['basis']} · {url}")
    log(f"끝 — {'초안' if a.draft else '발행'} {sent}편 · 검사 걸림 {blocked}편")
    if blog and not a.draft:
        write_card(blog)
    return 1 if blocked else 0


def _text(html, attr):
    m = re.search(attr + r'[^>]*>(.*?)</p>', html or "", re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""


def write_card(blog):
    """홈 카드 `Newfact 주요 기사` 자료 = 오늘(한국 시간) 공개 글 전부 (2026-11-24 사용자 "홈 카드는 무조건 오늘 날짜 기사" — 7일 → 오늘)(제목 · 요약 한 줄 · 주소 · 발행 시각) → output/publish/news-posts.json.
    워크플로가 gh-pages news-posts.json 으로 올린다 — 방문자는 이 파일 하나만 읽는다(jsDelivr, 다른 홈 카드와 같은 방식). 자르지 않는다(화면이 5개 + 접기)."""
    import html as H
    live = blog.existing(drafts=False)
    today = kst_now().date().isoformat()
    items = []
    for slug, bp in live.items():
        pub = bp.get("published") or ""
        try:
            pday = datetime.datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone(KST).date().isoformat()
        except ValueError:
            continue
        nd = re.search(r'data-news-date="([\d-]+)"', bp.get("content") or "")
        if pday != today or not nd or nd.group(1) != today:   # 기사 날짜도 오늘 — 11-23 기사를 11-24 에 공개해도 홈 카드엔 안 싣는다 (2026-11-24 사용자)
            continue
        title = re.sub(r"^" + re.escape(NR.NAME) + r"\s*:\s*", "", bp.get("title") or "")
        items.append({"slug": slug, "title": H.unescape(title), "summary": H.unescape(_text(bp.get("content"), "data-seo-lead")),
                      "url": bp.get("url"), "published": pub, "date": nd.group(1)})
    items.sort(key=lambda x: x["published"], reverse=True)
    # recent = 최근 48시간 공개 글 + 관련 정보에 나온 한국 종목 코드 — 종목 페이지 · 한국 리포트 뉴스에 Newfact 글 줄로 (2026-11-26 사용자). 홈은 items 만 읽는다(그대로)
    recent, cut = [], datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=48)
    for slug, bp in live.items():
        try:
            pt = datetime.datetime.fromisoformat((bp.get("published") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if pt < cut:
            continue
        c = bp.get("content") or ""
        m = re.search(r'data-news-stocks="([^"]*)"', c)
        codes = [x for x in (m.group(1).split(",") if m else re.findall(r'data-href="[^"]*-(\d{6})-stock\.html"', c)) if re.fullmatch(r"\d{6}", x)]   # 옛 글(칸 없음) = 관련 정보 종목 줄 주소
        title = re.sub(r"^" + re.escape(NR.NAME) + r"\s*:\s*", "", bp.get("title") or "")
        recent.append({"slug": slug, "title": H.unescape(title), "summary": H.unescape(_text(c, "data-seo-lead")), "url": bp.get("url"),
                       "published": bp.get("published"), "stocks": list(dict.fromkeys(codes))})
    recent.sort(key=lambda x: x["published"], reverse=True)
    os.makedirs(OUT, exist_ok=True)
    json.dump({"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "items": items, "recent": recent},
              open(os.path.join(OUT, "news-posts.json"), "w", encoding="utf-8"), ensure_ascii=False)
    log(f"홈 카드 자료 {len(items)}편 · 최근 48시간 글 {len(recent)}편(종목 붙은 글 {sum(1 for x in recent if x['stocks'])})")


def stage_refresh(a):
    """기준일 < 글 날짜인 글(아침 글)을 그날 값으로 다시 그려 같은 주소에 고쳐 쓴다. 기준일이 안 바뀌면(휴장 · 아직 마감 전) 건드리지 않는다."""
    now = kst_now()
    blog = Blog()
    have = blog.existing(drafts=a.draft)
    oldest = (now.date() - datetime.timedelta(days=MAX_AGE_DAYS)).isoformat()
    stale = {}
    for slug, bp in have.items():
        c = bp.get("content") or ""
        d = re.search(r'data-news-date="([\d-]+)"', c)
        b = re.search(r'data-basis="([\d-]*)"', c)
        if d and d.group(1) >= oldest and (not b or b.group(1) < d.group(1)):
            stale[slug] = (bp, b.group(1) if b else "")
    if not stale:
        log("고칠 글 없음")
        return 0
    posts = {p["slug"]: p for p in read_posts(a) if p.get("slug") in stale}
    lists, themes = read_lists()
    issues, forecasts = read_links()
    fixed = 0
    for slug, (bp, old_basis) in stale.items():
        p = posts.get(slug)
        if not p:
            log(f"수집기에 글이 없어 못 고침 — {slug}")
            continue
        title, html, meta = draw(p, lists, themes, issues, forecasts, now)
        if not meta.get("basis") or meta["basis"] <= old_basis:
            log(f"기준일 그대로 {old_basis or '없음'} — {slug}")
            continue
        blog.update(bp, html)
        fixed += 1
        record("refresh", p, meta, {"before_basis": old_basis, "url": bp.get("url")})
        log(f"고쳐 씀 — {slug} · 기준 {old_basis} → {meta['basis']}")
    log(f"끝 — {fixed}편 고침")
    return 0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["publish", "refresh"])
    ap.add_argument("--draft", action="store_true", help="초안으로 (시험) — refresh 는 초안도 고친다")
    ap.add_argument("--dry", action="store_true", help="publish: Blogger 없이 output/publish/<slug>.html 만")
    ap.add_argument("--limit", type=int, default=0, help="publish: 이번 실행에 낼 최대 편수 (0 = 전부)")
    ap.add_argument("--posts-json", help="시험: 수집기 글 JSON 파일 (Firestore 대신)")
    ap.add_argument("--gcloud", metavar="ACCOUNT", help="로컬: 서비스 계정 키 없이 gcloud 계정 토큰으로 읽기")
    a = ap.parse_args()
    sys.exit(stage_publish(a) if a.stage == "publish" else stage_refresh(a))


if __name__ == "__main__":
    main()
