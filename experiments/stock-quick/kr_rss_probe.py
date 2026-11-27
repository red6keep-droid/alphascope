"""한국 간단 종목 뉴스 — 언론사 RSS 제목 모으기 시험.

왜: 한국 간단 종목(316)에 뉴스를 붙이려면 언론사 RSS 제목을 직접 받아야 한다(네이버 · API 안 씀). 피드마다 담긴 기간이 3시간 ~ 일주일로 달라
    한 번 받아서는 하루 기준 숫자를 알 수 없다 → 2시간마다 며칠 모아, 하루에 몇 종목이 걸리나 · 매체별 기여를 센다.
AI 0 · 화면 0. 저장 = 제목 · 매체 · 링크 · 발행 시각 · 처음 본 시각만(RSS 설명 글 · 본문은 받지도 저장하지도 않는다).
매체 = 11-16 조사에서 robots 가 막지 않는 12곳. 아시아경제(robots 검색 로봇만 허용)는 넣지 않는다 — 우회 금지.

    python experiments/stock-quick/kr_rss_probe.py --state DIR            # 한 번 받기 (워크플로 2시간마다)
    python experiments/stock-quick/kr_rss_probe.py --state DIR --report   # 모은 것으로 하루 기준 숫자
"""
import argparse
import concurrent.futures
import datetime
import email.utils
import html
import importlib.util
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
KST = datetime.timezone(datetime.timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (compatible; AlphaScope-rss/1.0)"}
KEEP_DAYS = 10
FEEDS = {
    "한국경제": ["https://www.hankyung.com/feed/finance", "https://www.hankyung.com/feed/economy", "https://www.hankyung.com/feed/it", "https://www.hankyung.com/feed/all-news"],
    "매일경제": ["https://www.mk.co.kr/rss/50200011/", "https://www.mk.co.kr/rss/30000001/"],
    "머니투데이": ["https://rss.mt.co.kr/mt_news.xml"],   # rss 호스트는 robots 없음(허용). 본 사이트는 검색 로봇만 — 링크는 열지 않는다
    "이데일리": ["http://rss.edaily.co.kr/stock_news.xml", "http://rss.edaily.co.kr/edaily_news.xml"],
    "서울경제": ["https://www.sedaily.com/rss/finance"],
    "파이낸셜뉴스": ["https://www.fnnews.com/rss/r20/fn_realnews_stock.xml", "https://www.fnnews.com/rss/r20/fn_realnews_all.xml"],
    "헤럴드경제": ["https://biz.heraldcorp.com/rss/google/finance", "https://biz.heraldcorp.com/rss/google/newsAll"],
    "이투데이": ["https://rss.etoday.co.kr/eto/finance_news.xml", "https://rss.etoday.co.kr/eto/etoday_news_all.xml"],
    "뉴시스": ["https://newsis.com/RSS/economy.xml", "https://newsis.com/RSS/sokbo.xml"],
    "전자신문": ["https://rss.etnews.com/Section901.xml", "https://rss.etnews.com/03.xml"],
    "비즈니스포스트": ["https://www.businesspost.co.kr/rss/Article.xml"],
    "조선비즈": ["https://biz.chosun.com/arc/outboundfeeds/rss/category/stock/?outputType=xml", "https://biz.chosun.com/arc/outboundfeeds/rss/?outputType=xml"],
}
OFF = {m.strip() for m in os.environ.get("KR_RSS_OFF", "").split(",") if m.strip()}   # 매체 끄기 스위치 (삭제 요청 등)


def _date(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s.replace(",", ", ", 1) if re.match(r"\w{3},\S", s) else s)
    except (TypeError, ValueError):
        d = None
        for f in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
            try:
                d = datetime.datetime.strptime(s, f)
                break
            except ValueError:
                pass
    if d is None:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=KST)).astimezone(KST).isoformat(timespec="minutes")


def _fetch(job):
    media, url = job
    try:
        t = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 — 그 피드만 이번 회차 건너뜀
        return media, url, None, str(e)[:80]
    out = []
    for it in re.findall(r"<item[\s>](.*?)</item>", t, re.S):
        ti = re.search(r"<title>(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?</title>", it, re.S)
        ln = re.search(r"<link>(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?</link>", it, re.S)
        dt = re.search(r"<(?:pubDate|dc:date)>([^<]+)<", it)
        if ti:
            out.append({"title": " ".join(html.unescape(re.sub(r"<[^>]+>", "", ti.group(1))).split()),
                        "link": html.unescape(ln.group(1)).strip() if ln else "", "pub": _date(dt.group(1)) if dt else None})
    return media, url, out, None


def collect(state):
    path = os.path.join(state, "titles.jsonl")
    old = []
    if os.path.exists(path):
        old = [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
    seen = {(r["media"], r["link"] or r["title"]) for r in old}
    now = datetime.datetime.now(KST)
    jobs = [(m, u) for m, us in FEEDS.items() if m not in OFF for u in us]
    new, fails = [], []
    with concurrent.futures.ThreadPoolExecutor(4) as ex:
        for media, url, items, err in ex.map(_fetch, jobs):
            if items is None:
                fails.append(f"{media} {url} — {err}")
                continue
            for r in items:
                k = (media, r["link"] or r["title"])
                if k in seen:
                    continue
                seen.add(k)
                new.append(dict(r, media=media, seen=now.isoformat(timespec="minutes")))
    cut = (now - datetime.timedelta(days=KEEP_DAYS)).isoformat()
    keep = [r for r in old + new if r["seen"] >= cut]
    os.makedirs(state, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in keep:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    runs = os.path.join(state, "runs.jsonl")
    with open(runs, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now.isoformat(timespec="minutes"), "new": len(new), "fails": fails}, ensure_ascii=False) + "\n")
    print(f"[kr-rss] 새 제목 {len(new)} · 저장 {len(keep)} · 피드 실패 {len(fails)}/{len(jobs)}")
    for x in fails:
        print("  실패:", x)


def _quick_names():
    q = json.load(open(os.path.join(EXP, "ref", "quick_ref.json"), encoding="utf-8"))["kr"]
    spec = importlib.util.spec_from_file_location("universe_kr", os.path.join(EXP, "kr-stocks", "universe_kr.py"))
    uk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(uk)
    return {k: (e["ko"], e["market"]) for k, e in q.items() if k not in uk.BY_SYM}


_AFTER = set("은는이가을를의도에와과로·,…'\"’”)]?!:/- ")


def hit(name, title):
    """이름 앞이 글자가 아니고, 뒤가 끝 · 조사 · 문장부호 — `두산` 이 `두산에너빌리티` 에 걸리지 않게."""
    for mo in re.finditer(re.escape(name), title):
        a, b = mo.start(), mo.end()
        if (a == 0 or not re.match(r"[가-힣A-Za-z0-9]", title[a - 1])) and (b == len(title) or title[b] in _AFTER):
            return True
    return False


def report(state):
    rows = [json.loads(x) for x in open(os.path.join(state, "titles.jsonl"), encoding="utf-8") if x.strip()]
    names = _quick_names()
    days = {}
    for r in rows:
        d = (r.get("pub") or r["seen"])[:10]
        if d < rows[0]["seen"][:10]:   # 첫 회차 전에 나온 기사(피드에 남아 있던 옛 기사)는 하루 기준에서 뺀다
            continue
        for k, (nm, mk) in names.items():
            if hit(nm, r["title"]):
                days.setdefault(d, {}).setdefault(k, set()).add(r["media"])
    n_k = sum(1 for _, mk in names.values() if mk == "KOSPI")
    print(f"모은 제목 {len(rows)} · 간단 한국 {len(names)}종목(코스피 {n_k} · 코스닥 {len(names) - n_k})")
    allk, media = set(), {}
    for d in sorted(days):
        st = days[d]
        allk |= set(st)
        kp = sum(1 for k in st if names[k][1] == "KOSPI")
        print(f"  {d}: 걸린 종목 {len(st)} (코스피 {kp} · 코스닥 {len(st) - kp}) · 2곳 이상 {sum(1 for v in st.values() if len(v) >= 2)}")
        for k, v in st.items():
            for m in v:
                media.setdefault(m, set()).add(k)
    print(f"  전체 기간 한 번이라도 걸린 종목 {len(allk)}")
    for m in sorted(media, key=lambda m: -len(media[m])):
        only = sum(1 for k in media[m] if all(m2 == m for d in days.values() for m2 in d.get(k, ())))
        print(f"  {m}: 걸린 종목 {len(media[m])} · 혼자만 잡은 종목 {only}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    report(a.state) if a.report else collect(a.state)


if __name__ == "__main__":
    main()
