"""인물별 1차 · 2차 소스 → statements (기획 6절 2단계).

1차 수집기: cnn_archive(트럼프 Truth Social) · rss(백악관 · USTR · 버리 Substack) · fed_speeches · fed_press ·
treasury_html(재무부 보도자료, RSS 없음) · ark_trades(ARK 매매, arkfunds.io).
2차 수집기: google_news — 인물별 검색어, 기사 제목 · 매체 · 링크만 (본문은 저장하지 않는다).
LLM 은 쓰지 않는다. 같은 (인물, 링크)는 한 번만 들어간다. 수집 창(config.COLLECT_SINCE_HOURS) 밖은 버린다.

    python collect.py            # 전체
    python collect.py burry fed  # 일부 인물만
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


# ── 공통 ─────────────────────────────────────────────────────────────────

def strip_tags(text):
    if not text:
        return ""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html_mod.unescape(text)).strip()


def _iso(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_rfc822(text):
    try:
        return _iso(email.utils.parsedate_to_datetime((text or "").strip()))
    except (TypeError, ValueError):
        return None


def parse_iso(text):
    try:
        return _iso(datetime.datetime.fromisoformat((text or "").strip().replace("Z", "+00:00")))
    except ValueError:
        return None


def _hash(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def _get(url):
    r = requests.get(url, headers=HEADERS, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    return r


def _child(item, name):
    for c in item:
        if c.tag.split("}")[-1] == name:
            return c.text or ""
    return ""


def _rss_items(content):
    for it in ET.fromstring(content).iter("item"):
        yield {
            "title": strip_tags(_child(it, "title")),
            "link": (_child(it, "link") or "").strip(),
            "published": parse_rfc822(_child(it, "pubDate")),
            "category": strip_tags(_child(it, "category")),
            "body": strip_tags(_child(it, "encoded") or _child(it, "description")),
            "source": strip_tags(_child(it, "source")),
        }


def _row(collector, speaker, attribution, title, url, published, body=None, publisher=None,
         sub_speaker=None, source_kind="primary"):
    return {
        "id": f"{collector}:{_hash(url or title + published)}", "speaker": speaker, "sub_speaker": sub_speaker,
        "source_kind": source_kind, "attribution": attribution, "collector": collector,
        "publisher": publisher, "published_at": published, "title": title[:400],
        "body": (body or "")[:config.PRIMARY_BODY_MAX_CHARS] or None, "url": url,
    }


# ── 1차 수집기 ───────────────────────────────────────────────────────────

def c_rss(speaker, url, attribution):
    publisher = re.sub(r"^www\.", "", url.split("/")[2])
    out = []
    for it in _rss_items(_get(url).content):
        if it["title"] and it["link"] and it["published"]:
            out.append(_row("rss", speaker, attribution, it["title"], it["link"], it["published"],
                            body=it["body"], publisher=publisher))
    return out


def c_fed_speeches(speaker, url, attribution):
    # 제목이 "Waller, The Signaling Value of …" — 쉼표 앞이 연설자 성
    out = []
    for it in _rss_items(_get(url).content):
        if not (it["title"] and it["published"]):
            continue
        who = it["title"].split(",", 1)[0].strip().lower() if "," in it["title"] else None
        out.append(_row("fed_speeches", speaker, attribution, it["title"], it["link"], it["published"],
                        body=it["body"], publisher="federalreserve.gov", sub_speaker=who))
    return out


def c_fed_press(speaker, url, attribution):
    out = []
    for it in _rss_items(_get(url).content):
        if it["category"] in config.FED_MONETARY_CATEGORIES and it["published"]:
            out.append(_row("fed_press", speaker, attribution, it["title"], it["link"], it["published"],
                            body=it["body"], publisher="federalreserve.gov", sub_speaker="fomc"))
    return out


def c_treasury_html(speaker, _arg, attribution):
    # 목록 페이지: <a href=/news/press-releases/sb0662/ …>제목</a> … <time datetime=2026-10-15T17:00:00Z>
    page = _get(config.TREASURY_PRESS_URL).text
    pat = re.compile(r'<a href="?(/news/press-releases/[a-z]{2}\d+/?)"?[^>]*>([^<]+)</a>.*?<time datetime="?([0-9T:\-Z]+)',
                     re.S)
    out = []
    for path, title, ts in pat.findall(page):
        title = strip_tags(title)
        # 장관 본인 발언 · 성명은 self, 나머지(제재 · 통계)는 기관 발표
        attr = "self" if re.search(r"Bessent|Secretary", title) else attribution
        out.append(_row("treasury_html", speaker, attr, title, "https://home.treasury.gov" + path, parse_iso(ts),
                        publisher="treasury.gov"))
    if not out:
        raise RuntimeError("재무부 목록 구조가 바뀜 — 항목 0건")
    return out


def c_cnn_archive(speaker, _arg, attribution):
    data = _get(config.CNN_ARCHIVE_URL).json()
    if isinstance(data, dict):
        data = data.get("data") or data.get("posts") or []
    out = []
    for rec in data:
        content = strip_tags(rec.get("content") or "")
        ts = parse_iso(rec.get("created_at") or "")
        if not ts:
            continue
        title = content[:200] or "(미디어만 있는 게시물)"
        out.append(_row("cnn_archive", speaker, attribution, title, rec.get("url") or f"truth:{rec.get('id')}", ts,
                        body=content, publisher="truthsocial.com"))
    return out


def c_ark_trades(speaker, _arg, attribution):
    # 하루 = 한 행: 펀드 6개의 그날 매수 · 매도를 모아 제목 한 줄 + 본문 표
    by_day = {}
    for fund in config.ARK_FUNDS:
        try:
            trades = _get(config.ARK_TRADES_URL.format(fund=fund)).json().get("trades") or []
        except Exception as e:  # noqa: BLE001
            print(f"[collect]   ARK {fund} 실패: {str(e)[:100]}")
            continue
        for t in trades:
            by_day.setdefault(t["date"], []).append(t)
    out = []
    for day, trades in by_day.items():
        trades.sort(key=lambda t: -(t.get("etf_percent") or 0))
        buys = sorted({t["ticker"] for t in trades if t["direction"] == "Buy"})
        sells = sorted({t["ticker"] for t in trades if t["direction"] == "Sell"})
        title = f"ARK trades {day}: buy {', '.join(buys) or '-'} / sell {', '.join(sells) or '-'}"
        body = "\n".join(f'{t["fund"]} {t["direction"]} {t["ticker"]} {t["shares"]:,} shares ({t.get("etf_percent")}% of ETF)'
                         for t in trades)
        # 공시는 장 마감 뒤 저녁 — 시각은 그날 미국 동부 20:00 를 UTC 로 (정확한 시각 없음)
        ts = f"{day}T23:59:00Z"
        out.append(_row("ark_trades", speaker, attribution, title, f"https://ark-funds.com/trade-notifications#{day}", ts,
                        body=body, publisher="arkfunds.io"))
    return out


PRIMARY = {
    "rss": c_rss, "fed_speeches": c_fed_speeches, "fed_press": c_fed_press,
    "treasury_html": c_treasury_html, "cnn_archive": c_cnn_archive, "ark_trades": c_ark_trades,
}


# ── 2차 수집기 ───────────────────────────────────────────────────────────

def c_google_news(speaker, query):
    out = []
    for it in _rss_items(_get(config.gnews(query)).content):
        if not (it["title"] and it["link"] and it["published"]):
            continue
        publisher = it["source"] or "googlenews"
        title = re.sub(r"\s+-\s+[^-]{2,60}$", "", it["title"]).strip() or it["title"]   # " - 매체명" 떼기
        out.append(_row("google_news", speaker, "report", title, it["link"], it["published"],
                        publisher=publisher, source_kind="secondary"))
    return out


# ── 실행 ────────────────────────────────────────────────────────────────

def _insert(conn, rows, since):
    new = 0
    for r in rows:
        if not r["published_at"] or r["published_at"] < since:
            continue
        cur = conn.execute(
            """INSERT OR IGNORE INTO statements(id, speaker, sub_speaker, source_kind, attribution, collector, publisher,
                   published_at, title, body, url, collected_at)
               VALUES (:id, :speaker, :sub_speaker, :source_kind, :attribution, :collector, :publisher,
                   :published_at, :title, :body, :url, :collected_at)""",
            dict(r, collected_at=db.now_iso()))
        new += cur.rowcount
    return new


def collect(conn, only=None):
    since = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(hours=config.COLLECT_SINCE_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = []   # (인물, 소스, 받은 수, 창 안, 신규 | 오류)
    for key, p in config.PEOPLE.items():
        if only and key not in only:
            continue
        jobs = [(name, (lambda f=PRIMARY[name], a=arg, at=attr: f(key, a, at))) for name, arg, attr in p["primary"]]
        if p.get("news"):
            jobs.append(("google_news", lambda q=p["news"]: c_google_news(key, q)))
        for name, job in jobs:
            try:
                rows = job()
            except Exception as e:  # noqa: BLE001
                summary.append((key, name, 0, 0, f"실패: {str(e)[:100]}"))
                continue
            in_window = sum(1 for r in rows if r["published_at"] and r["published_at"] >= since)
            summary.append((key, name, len(rows), in_window, _insert(conn, rows, since)))
        conn.commit()
    for key, name, got, win, new in summary:
        print(f"[collect] {key:9s} {name:14s} 받음 {got:>6,} · 창 안 {win:>4} · 신규 {new}")
    return summary


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    collect(db.connect(), only=set(sys.argv[1:]) or None)
