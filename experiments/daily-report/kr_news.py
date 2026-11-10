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

TITLE = "한국 종목과 연결된 미국 뉴스"   # 2026-11-07 사용자 P373 (옛 `한국장에 영향을 줄 만한 소식` — 한국 증시 리포트와 같은 뉴스였다)
KR_REPORT_URL = "https://alpha-scope.blogspot.com/search/label/%ED%95%9C%EA%B5%AD%20%EC%A6%9D%EC%8B%9C%20%EB%A6%AC%ED%8F%AC%ED%8A%B8"   # 한국 증시 리포트 목록 — 한국 증시 이야기는 그쪽에
TAB = "한국장"   # render_html.TAB_KOREA 와 같다
HOURS, SHOWN = 48, 5   # 최근 48시간 전부, 앞 5건만 펼치고 나머지는 접기 (2026-10-30 사용자). 옛: 6건 · 12시간(어제 아침 한국 방송은 뺌)
MARK_OPEN, MARK_CLOSE = "<!--kr-news-->", "<!--/kr-news-->"


def rows_now():
    now = datetime.datetime.now(datetime.timezone.utc)
    return media_feed.rows(media_feed.load(now.astimezone(media_feed.KST).strftime("%Y-%m-%d"), days=8))   # 목록 48시간 + 방향 막대 `최근 7일` (P143) — edition 여드레


def section(rows, hours=HOURS, pick=None, shown=SHOWN, prices=None):
    """표시 주석으로 감싼 구획 HTML. 공용 뉴스 카드: 방송 주제(영상 링크) / 방송 주장 / [한국 종목 · 분야] [방향] [예상 밖]  시각 · 채널 · 방송 n곳.
    소식이 없으면 표시만 (빈 칸)."""
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M")
    items = []
    n_all = dk.n_channels_of(media_feed.issues(rows, since))   # 분모 = 이 시간 안 방송 채널 수 (P338)
    for r in (pick or media_feed.us_to_kr)(media_feed.issues(rows, since), None):   # 같은 이슈는 한 줄로 정리한 뒤 — 전부(상한 없음, 2026-10-30). pick: 고르는 규칙(기본 media_feed.korea = 한국 증시 내용, 채널 무관 — 2026-10-30)
        if len([x for x in (r.get("lines") or []) if x]) < 2:   # 요약 두 줄 못 되는 방송 줄은 싣지 않는다 (2026-11-10 사용자)
            continue
        d = r["direction"]
        dd = "uncertain" if r.get("split") else d if d in ("positive", "negative") else "neutral"
        labels = " ".join([dk.pill(media_feed.kr_label(r), bare=True),
                           dk.pill(dk.DIR_KO[dd], dd, bare=True)]   # 방향 라벨 = 막대와 같은 네 단어 중 하나, 섞이면 `불확실` (2026-11-07 사용자 P335) — 옛 `중립` + `엇갈림` 두 개
                          + ([dk.pill("예상 밖", "uncertain", bare=True)] if r["surprise"] else []))
        count = dk.channel_count(r["n_channels"], n_all) if r["n_channels"] > 1 else ""   # 곳 수 막대 = 라벨 다음 줄 (P338 · P348)   # `방송` 라벨은 뺀다 — 메타의 채널 · 방송 n곳과 같은 정보 (2026-10-26 사용자)
        meta = [dk.news_when(r["published_at"]), r["channel"]]
        item = dk.news_item(html_mod.escape(r["topic"]), r["url"], r["note"], (), labels, meta, ' data-trhelp="skip"', count_html=count)
        if len(r.get("lines") or []) >= 2:   # 누르면 요약 다섯 줄 팝업 (2026-11-07 사용자 P337, 데일리 뉴스 탭과 같게)
            pid = dk.news_pop_id("kr", r.get("id") or r["url"])
            item = dk.news_pop_wrap(item, pid) + dk.news_pop_body(pid, r["topic"], r["lines"], source=r["channel"], kind="방송", url=r["url"],
                                                                   related=media_feed.kr_related(r, prices) if prices else ())   # 관련 종목 = 그날 한국 등락 (P355, 데일리 한국장 탭은 prices 없음 — 장 열기 전)
        items.append(item)
    lst = dk.more_list(items, "뉴스", shown or len(items), indent=dk.ALIGN_PX, first_top=18)   # 5건 + 10건씩 더 보기 (2026-11-07 사용자 P340)   # 종목 페이지 뉴스와 같은 여백 — 아래 19 · 방향 막대 아래 첫 기사 위 18(NEWS_FIRST_TOP) (2026-11-07 0절)
    now = datetime.datetime.now(datetime.timezone.utc)
    within = lambda h: (pick or media_feed.us_to_kr)(media_feed.issues(rows, (now - datetime.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M")), None)   # noqa: E731
    lst = dk.direction_bars(media_feed.direction_counts(within(24)), media_feed.direction_counts(within(24 * 7))) + lst   # 엔비디아처럼 오늘 · 최근 7일 방향 막대 (2026-10-31 사용자 P143)
    if items and pick is None:   # 데일리 한국장 탭 끝 — 한국 증시 이야기는 한국 증시 리포트로 (P373)
        lst += (f'<p style="margin:0 0 8px;padding:0 {dk.ALIGN_PX}px;font-size:{dk.TINY};line-height:{dk.LH_TINY};">'
                f'<a href="{KR_REPORT_URL}" style="color:#111;font-weight:700;text-decoration:none;">한국 증시 이야기는 한국 증시 리포트에서 보기 ›</a></p>')
    body = dk.keep_tone(dk.section(TITLE, lst, tab=TAB)) if items else ""   # 방송 소식 = 헤드라인체 그대로
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
