"""RSS → items (kind = newsroom · blog · news). 기획서 2절 뉴스 묶음.

뉴스룸(공식 보도자료)·블로그·CNBC 2종·Google News(q=Nvidia, 7일) — 제목·요약·링크·발행시각만 저장한다.
외부 기사 본문은 저장하지 않는다. 뉴스룸 보도자료는 1차 자료이므로 본문(태그 제거)을 raw_json에 둔다.
키워드 1차 필터와 중복 표시는 dedupe.py가 한다 — 여기서는 새 것만 넣는다.
"""

import datetime
import email.utils
import hashlib
import html as html_mod
import re
import sys
import xml.etree.ElementTree as ET

import requests

import config
import db

HEADERS = {"User-Agent": config.BROWSER_USER_AGENT}


def strip_tags(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_date(text):
    if not text:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(text.strip())
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _child_text(item, name):
    """네임스페이스 유무와 무관하게 자식 요소 텍스트."""
    for c in item:
        if c.tag.split("}")[-1] == name:
            return c.text or ""
    return ""


def parse_feed(content, kind, source):
    root = ET.fromstring(content)
    out = []
    feed_kind, feed_source = kind, source
    for it in root.iter("item"):
        kind, source = feed_kind, feed_source
        title = strip_tags(_child_text(it, "title"))
        link = (_child_text(it, "link") or "").strip()
        if not title or not link:
            continue
        publisher = source
        if source == "googlenews":
            publisher = strip_tags(_child_text(it, "source")) or "googlenews"
            # Google News 제목은 " - 매체명"으로 끝난다
            title = re.sub(r"\s+-\s+[^-]{2,40}$", "", title).strip() or title
        desc = strip_tags(_child_text(it, "description"))
        if source == "googlenews":
            desc = ""   # 설명이 제목 링크의 HTML 반복이라 비운다
        published = parse_date(_child_text(it, "pubDate")) or parse_date(_child_text(it, "modDate"))
        guid = (_child_text(it, "guid") or "").strip() or link
        key = hashlib.sha1(guid.encode("utf-8")).hexdigest()[:16]
        raw = {"publisher": publisher, "guid": guid}
        # 뉴스룸 "All News" 피드(releases.xml)는 블로그 글(blogs.nvidia.com)과 보도자료(nvidianews.nvidia.com/news/…)를 섞어 준다 —
        # 링크 도메인으로 종류를 가른다 (2026-10-08 확인: 20건 중 보도자료 2건)
        if kind == "newsroom" and "blogs.nvidia.com" in link:
            kind, source, publisher = "blog", "nvidiablog", "nvidiablog"
        if kind == "newsroom":
            body = strip_tags(_child_text(it, "content") or _child_text(it, "encoded"))
            if body:
                raw["body"] = body[:config.NEWSROOM_BODY_MAX_CHARS]
            cats = _child_text(it, "categories")
            if cats:
                raw["categories"] = cats
        out.append({
            "item_id": f"{kind}:{key}", "kind": kind, "published_at": published or db.now_iso(),
            "title": title[:300], "summary": desc[:500] or None, "url": link, "source": publisher if source == "googlenews" else source,
            "raw_json": db.dumps(raw),
        })
    return out


def collect(conn):
    existing = {r["item_id"] for r in conn.execute("SELECT item_id FROM items WHERE kind IN ('newsroom','blog','news')")}
    existing_urls = {r["url"] for r in conn.execute("SELECT url FROM items WHERE kind IN ('newsroom','blog','news') AND url IS NOT NULL")}
    total_new = 0
    for name, (kind, source, url) in config.FEEDS.items():
        try:
            r = requests.get(url, headers=HEADERS, timeout=config.HTTP_TIMEOUT)
            r.raise_for_status()
            rows = parse_feed(r.content, kind, source)
        except Exception as e:  # noqa: BLE001
            print(f"[feeds] {name} 실패: {str(e)[:120]}")
            continue
        new = 0
        for row in rows:
            if row["item_id"] in existing or row["url"] in existing_urls:
                continue
            conn.execute(
                """INSERT OR IGNORE INTO items(item_id, kind, published_at, title, summary, url, source, raw_json, collected_at)
                   VALUES (:item_id, :kind, :published_at, :title, :summary, :url, :source, :raw_json, :collected_at)""",
                dict(row, collected_at=db.now_iso()))
            existing.add(row["item_id"])
            existing_urls.add(row["url"])
            new += 1
        total_new += new
        print(f"[feeds] {name}: {len(rows)}건 중 신규 {new}")
    conn.commit()
    print(f"[feeds] 신규 합계 {total_new}건")
    return total_new


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    collect(db.connect())
