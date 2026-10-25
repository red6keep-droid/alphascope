"""한국장 탭 `한국장에 영향을 줄 만한 소식` — 방송 소식 (2026-10-25 사용자: 미디어 데일리에서 데일리 한국장 탭으로).

- 글을 만들 때 render_html 이 그린다 — 그 시각 기준 최근 HOURS 시간(밤사이 미국 방송의 한국 이야기).
- 한국 아침 방송(당잠사 · 증시각도기, 07:30~08:30)은 데일리(07:00 쯤)보다 늦다. 그래서 미디어 데일리 실행(08:00 1차 · 10:15 2차)이
  끝난 뒤 이 파일을 실행해 **오늘 데일리 글의 이 칸만** 바꾼다(main, media-daily.yml). 다른 칸 · 제목 · 라벨은 그대로.
- 칸은 MARK_OPEN · MARK_CLOSE 주석 사이. 소식이 없어도 표시는 남긴다 — 나중 실행이 채울 수 있게.

    python experiments/daily-report/kr_news.py --dry-run   # 오늘 글을 찾아 바뀔 칸만 확인
    python experiments/daily-report/kr_news.py             # 갱신 (게시)
"""

import argparse
import datetime
import html as html_mod
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import design_kit as dk  # noqa: E402
import media_feed  # noqa: E402

TITLE = "한국장에 영향을 줄 만한 소식"
TAB = "한국장"   # render_html.TAB_KOREA 와 같다
MAX, HOURS = 6, 12   # 최근 12시간 — 어제 아침 한국 방송(전날 장 이야기)은 넣지 않는다
MARK_OPEN, MARK_CLOSE = "<!--kr-news-->", "<!--/kr-news-->"


def _kst_hm(iso):
    try:
        return datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(media_feed.KST).strftime("%H:%M")
    except ValueError:
        return ""


def rows_now():
    now = datetime.datetime.now(datetime.timezone.utc)
    return media_feed.rows(media_feed.load(now.astimezone(media_feed.KST).strftime("%Y-%m-%d"), days=2))


def section(rows, hours=HOURS):
    """표시 주석으로 감싼 구획 HTML. 공용 뉴스 카드: 방송 주제(영상 링크) / 방송 주장 / [한국 종목 · 분야] [방향] [예상 밖] [방송]  시각 · 채널.
    소식이 없으면 표시만 (빈 칸)."""
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M")
    items = []
    for r in media_feed.korea(media_feed.issues(rows, since), MAX):   # 같은 이슈는 한 줄로 정리한 뒤
        d = r["direction"]
        labels = " ".join([dk.pill(media_feed.kr_label(r), bare=True),
                           dk.pill({"positive": "긍정", "negative": "부정"}.get(d, "중립"), d if d in ("positive", "negative") else "neutral", bare=True)]
                          + ([dk.pill("예상 밖", "uncertain", bare=True)] if r["surprise"] else []) + [dk.pill(media_feed.LABEL, bare=True)])
        meta = [_kst_hm(r["published_at"]), r["channel"], f"방송 {r['n_channels']}곳" if r["n_channels"] > 1 else ""]
        items.append(dk.news_item(html_mod.escape(r["topic"]), r["url"], r["note"], (), labels, meta, ' data-trhelp="skip"'))
    body = dk.keep_tone(dk.section(TITLE, dk.item_rules(items, sub=True, indent=dk.ALIGN_PX), tab=TAB)) if items else ""   # 방송 소식 = 헤드라인체 그대로
    return MARK_OPEN + body + MARK_CLOSE


def finish(html):
    """render_html.build_body 끝과 같은 마무리 — 제목 시작선 · ':' 띄우기 · 합니다체(keep_tone 안은 그대로)."""
    return dk.formal(dk.fix_colons(dk.align_titles(html)))


def _today_post(creds, blog_id, titles):
    import requests
    import publish_blogger as pb
    r = requests.get(f"{pb.BLOGGER_API}/blogs/{blog_id}/posts", params={"maxResults": 15, "fetchBodies": "true", "fetchImages": "false"},
                     headers={"Authorization": f"Bearer {creds.token}"}, timeout=60)
    r.raise_for_status()
    wanted = {t.strip() for t in titles}
    return next((p for p in r.json().get("items", []) if str(p.get("title", "")).strip() in wanted), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"))
    import publish_blogger as pb
    import report_title
    creds = pb._credentials()
    blog_id = pb._blog_id(creds, os.environ.get("BLOG_URL", pb.DEFAULT_BLOG_URL))
    post = _today_post(creds, blog_id, report_title.match_titles(report_title.today_kst()))
    if not post:
        print("[한국장 소식] 오늘 데일리 글 없음 — 건너뜀 (주말 · 휴장 · 아직 게시 전)")
        return
    content = post.get("content") or ""
    if MARK_OPEN not in content or MARK_CLOSE not in content:
        print("[한국장 소식] 글에 칸 표시가 없음(표시를 넣기 전 글) — 건너뜀")
        return
    block = finish(section(rows_now()))
    new = re.sub(re.escape(MARK_OPEN) + r".*?" + re.escape(MARK_CLOSE), lambda _: block, content, count=1, flags=re.S)
    n = block.count(">방송<")
    if new == content:
        print(f"[한국장 소식] 바뀐 것 없음 ({n}줄)")
        return
    if a.dry_run:
        print(f"[한국장 소식 dry-run] {post.get('title')} — {n}줄로 바꿀 예정")
        return
    r = pb._write("put", f"{pb.BLOGGER_API}/blogs/{blog_id}/posts/{post['id']}",
                  headers={"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"},
                  json={"kind": "blogger#post", "id": post["id"], "title": post["title"], "content": new, "labels": post.get("labels") or []}, timeout=60)
    r.raise_for_status()
    print(f"[한국장 소식] {post.get('title')} — {n}줄로 갱신 {post.get('url')}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
