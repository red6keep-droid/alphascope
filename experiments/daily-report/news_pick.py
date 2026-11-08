"""미국 데일리 뉴스 재료 정리 (2026-11-05 사용자 batch 8 ③ · ⑤ · ⑬) — 기사(CNBC) 와 유튜브 방송 주제를 **같은 뉴스끼리 묶고**, 규칙으로 `꼭 볼 뉴스` 를 고르고,
팝업(요약 다섯 줄 · 관련 종목 오늘 등락 · 몇 곳이 다뤘나)의 재료를 만든다. 그리는 일은 render_html.sec_news.

왜 규칙인가 : 데일리 AI 가 고른 3~5건은 기준이 보이지 않았다(사용자). 점수는 전부 우리 데이터 — 다룬 방송 수 · 관련 자산의 그날 움직임 · 예상 밖 표시 · 최근성.
             툴팁에 그대로 적는다. AI 는 묶기(news_stories) · 요약(news_summary)만.
"""

import datetime
import hashlib
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, ".."))
import media_feed  # noqa: E402
import news_stories  # noqa: E402
import news_summary  # noqa: E402

STATE_DIR = os.path.join(BASE, "output", "state")
DATA_DIR = os.path.join(BASE, "output", "data")   # 깃 밖 — 첫 문단 캐시
PICK_N = 5
LIST_SHOWN = 10
RECENT_HOURS = 12
MOVE_CAP = 4.0
STOCKS_URL = "https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages/stocks.json"
_stocks = None




def _seed_home_summaries(cache_path):
    """gh-pages 의 홈 요약 캐시(news_summaries_home.json, 열쇠 = 같은 item_id)를 데일리 캐시에 없는 것만 채운다. 못 받으면 그냥 지나간다."""
    import requests
    try:
        home = requests.get("https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages/news_summaries_home.json", timeout=15).json()
    except Exception:  # noqa: BLE001
        return
    cache = news_summary._load(cache_path)
    add = {k: v for k, v in home.items() if k not in cache and isinstance(v, dict) and v.get("lines")}
    if add:
        cache.update(add)
        news_summary._save(cache_path, cache)
        print(f"[news_pick] 홈 요약 {len(add)}건 재사용")


# 뉴스 탭 분야 탭 = 8개 묶음 (2026-11-07 사용자 P357: 18개 분류를 전부 탭으로 만들어 너무 많았다 — 탭에만, 줄 라벨 · 기록은 18개 그대로).
# 근거 = 방송 이슈 12일 1,467건 하루 평균 — 하루 10건 안팎씩 되게 작은 분야를 뜻이 가까운 큰 탭에 붙였다
TAB_GROUP = {"AI_CAPEX": "AI · 반도체", "EARNINGS": "실적 · 기업", "CORP_EVENT": "실적 · 기업", "INVESTOR_CALLS": "실적 · 기업",
             "RATES_FED": "금리 · 경기", "INFLATION": "금리 · 경기", "GROWTH_JOBS": "금리 · 경기",
             "FISCAL_POLITICS": "정치 · 규제", "REGULATION": "정치 · 규제", "GEOPOLITICS": "지정학 · 무역", "TARIFF_TRADE": "지정학 · 무역",
             "OIL_ENERGY": "유가 · 원자재"}   # 나머지(수급 · 신용 · 환율 · 부동산 · 암호화폐 · 그 밖) = 시장 · 기타


def tab_of(theme_ko):
    import issue_codes
    code = next((c for c, n in issue_codes.ISSUE_KO.items() if n == theme_ko), "OTHER")
    return TAB_GROUP.get(code, "시장 · 기타")


def tab_order(picks, rest):
    """분야 탭 순서 (P358): 주요 뉴스 1번 기사의 탭 → 2번 … (같은 탭은 한 번) → 나머지 탭은 그날 건수 많은 순. 값 = [(탭, 건수)]."""
    counts = {}
    for g in picks + rest:
        t = tab_of(g["theme"])
        counts[t] = counts.get(t, 0) + 1
    order = list(dict.fromkeys(tab_of(g["theme"]) for g in picks))
    order += [t for t, _ in sorted(counts.items(), key=lambda kv: -kv[1]) if t not in order]
    return [(t, counts[t]) for t in order]

def _issue_ko(n):
    """CNBC 기사 분야 = 기록 이슈 코드 이름 (2026-11-07 사용자 P339). 옛 theme(8개 화면 어휘)은 issue 가 없을 때만."""
    import issue_codes
    iss = n.get("issue")
    return issue_codes.ISSUE_KO.get(iss) if iss in issue_codes.ISSUE_KO else (n.get("theme") or "그 밖")

def item_id(link):
    return hashlib.sha1(str(link or "").encode()).hexdigest()[:12]   # fetch_news._iid · collect_news.process 와 같은 열쇠


def _iso(s):
    """'YYYY-MM-DD HH:MM:SS'(UTC, 기사) · ISO(방송) → 'YYYY-MM-DDTHH:MM' 비교용."""
    s = str(s or "").replace(" ", "T")
    return s[:16]


def stocks():
    """{티커: {name, p, cp}} — 홈 종목 카드가 쓰는 gh-pages stocks.json (오늘 등락). 못 읽으면 {}."""
    global _stocks
    if _stocks is not None:
        return _stocks
    data = None
    try:
        path = os.environ.get("STOCK_PAGES_JSON")
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        else:
            import urllib.request
            with urllib.request.urlopen(urllib.request.Request(STOCKS_URL, headers={"User-Agent": "alphascope"}), timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[news_pick] 종목 등락 목록 없음 : {str(e)[:80]}")
    _stocks = {x["s"]: x for x in ((data or {}).get("stocks") or []) if x.get("s")}
    global _notable
    _notable = (data or {}).get("notable") or {}
    return _stocks


_notable = None


def notable():
    """같은 stocks.json 의 `notable` — 최근 급락일에 버틴 종목(종목 레이더 crash_watch, 홈 `주목할 종목` 카드와 같은 재료). 데일리 `급락한 날 버틴 종목은?` (2026-11-08 사용자). 못 읽으면 {}."""
    if _notable is None:
        stocks()
    return _notable or {}


def prev_run():
    """지난 실행의 기사 주소 집합 · 시각 — `N`(새 뉴스) 표시용. state/last 는 이번 실행 전 마지막 글."""
    try:
        with open(os.path.join(STATE_DIR, "last", "report_input.json"), encoding="utf-8") as f:
            d = json.load(f)
        return {"links": {x.get("link") for x in d.get("news") or []}, "at": _iso(str(d.get("updated_at") or "").replace("Z", ""))}
    except (OSError, ValueError):
        return {"links": set(), "at": ""}


def build(input_data, analysis, media_lines, now=None, summarize=True, all_channels=None, prev=None, stories_cache=None, label="daily-stories"):
    """재료 → {"stories", "picks", "rest", "chips", "n_channels_all", "channels_all", "prev", "lines", "stocks"}.
    media_lines = media_feed.market_top(issues) (시장 · 업종 이슈, 48시간). analysis 는 없을 수 있다.
    한국 증시 리포트(M82) = 기사 없이 방송만, prev · stories_cache 를 따로 준다 (미국 데일리 상태를 쓰지 않게)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    series = (analysis or {}).get("series") or {}
    sx = stocks()
    prev = prev if prev is not None else prev_run()
    items, src = [], {}
    for i, n in enumerate(input_data.get("news") or []):
        if not (n.get("headline_ko") or n.get("title")):
            continue
        it = {"id": item_id(n.get("link")), "kind": "article", "text": n.get("headline_ko") or n.get("title") or "", "theme": _issue_ko(n),
              "published_at": _iso(n.get("published")), "index": i, "url": n.get("link"), "source": n.get("source") or "CNBC",
              "detail": n.get("detail_ko") or "", "related": [s for s in (n.get("related") or []) if isinstance(s, str)],
              "surprise": n.get("surprise"), "market_dir": n.get("market_dir"), "title": n.get("title") or "", "snippet": n.get("summary") or "",
              "new": n.get("link") not in prev["links"]}
        items.append(it)
        src[it["id"]] = it
    for r in media_lines or []:
        it = {"id": "m" + str(r["id"]), "kind": "media", "text": r["topic"], "theme": r.get("theme") or "기타", "published_at": _iso(r["published_at"]),
              "url": r.get("url"), "source": r.get("channel") or "", "detail": r.get("note") or "", "related": list(r.get("tickers") or [])[:4],
              "surprise": r.get("surprise"), "market_dir": "uncertain" if r.get("split") else r.get("direction"), "channels": list(r.get("channels") or []),
              "n_videos": r.get("n_videos") or 1, "title": r["topic"],   # lines = 수집기 요약 다섯 줄 (batch 9 ⑧)
              "lines": [str(x) for x in (r.get("lines") or []) if x][:5], "new": _iso(r["published_at"]) > prev["at"] if prev["at"] else False}
        items.append(it)
        src[it["id"]] = it
    stories = news_stories.group(items, cache_path=stories_cache or os.path.join(STATE_DIR, "news_stories.json"), label=label)
    story_of = {it["id"]: g for g in stories for it in g["items"]}
    recent = (now - datetime.timedelta(hours=RECENT_HOURS)).strftime("%Y-%m-%dT%H:%M")

    def move(it):
        best = 0.0
        for s in it.get("related") or []:
            v = (series.get(s) or {}).get("ret_1d")
            if v is None and s in sx:
                v = sx[s].get("cp")
            if v is not None:
                best = max(best, abs(float(v)))
        return min(best, MOVE_CAP)

    for g in stories:   # 대표 = 요약 줄이 있는 최신 기사 → 없으면 최신 기사 → 최신 방송
        arts = [x for x in g["items"] if x["kind"] == "article"]
        g["rep"] = next((x for x in arts if x.get("detail")), arts[0] if arts else g["items"][0])
        g["new"] = any(x.get("new") for x in g["items"])
        why = []
        score = 0.0
        if g["n_channels"] >= 2:
            score += min(g["n_channels"], 10) * 2
            why.append(f"방송 {g['n_channels']}곳")
        mv = max((move(x) for x in g["items"]), default=0.0)
        if mv >= 1:
            score += mv
            why.append(f"관련 자산 {mv:.1f}% 움직임")
        if any(x.get("surprise") for x in g["items"]):
            score += 2
            why.append("예상 밖")
        if any(x.get("market_dir") in ("positive", "negative") for x in g["items"]):
            score += 1
            why.append("시장 방향 있음")
        if g["latest"] >= recent:
            score += 1
            why.append("12시간 안")
        g["score"], g["why"] = score, why
    ranked = sorted(stories, key=lambda g: g["latest"], reverse=True)   # 점수가 같으면 최근 것
    ranked.sort(key=lambda g: -g["score"])
    picks = [g for g in ranked if g["score"] > 0][:PICK_N]
    pick_ids = {g["id"] for g in picks}
    rest = sorted([g for g in stories if g["id"] not in pick_ids], key=lambda g: g["latest"], reverse=True)
    chips = {}
    for g in rest:
        chips[g["theme"]] = chips.get(g["theme"], 0) + 1
    lines = {}
    if os.environ.get("NEWS_NO_AI"):
        lines = {k: v["lines"] for k, v in news_summary._load(os.path.join(STATE_DIR, "news_summaries.json")).items()}
    if summarize and not os.environ.get("NEWS_NO_AI"):   # NEWS_NO_AI=1: 캐시된 요약만 (목업 · 다시 그리기)
        reps = [g["rep"] for g in picks + rest if g["rep"]["kind"] == "article"]
        _seed_home_summaries(os.path.join(STATE_DIR, "news_summaries.json"))   # 홈(06:45)이 이미 요약한 CNBC 기사는 다시 AI 에 보내지 않는다 (2026-11-07 P342)
        try:
            lines = news_summary.summarize([{"item_id": x["id"], "title": x["title"], "url": x["url"], "snippet": x["snippet"]} for x in reps],
                                           cache_path=os.path.join(STATE_DIR, "news_summaries.json"), lead_cache=os.path.join(DATA_DIR, "leads.json"), label="daily-summary")
        except Exception as e:  # noqa: BLE001
            print(f"[news_pick] 요약 실패 — 요약 줄 하나로 : {str(e)[:100]}")
    all_ch = sorted(set(all_channels) if all_channels else {c for r in (media_lines or []) for c in (r.get("channels") or [])})   # 분모 = 48시간 안 영상이 있던 방송 전부
    return {"stories": stories, "picks": picks, "rest": rest, "chips": chips, "story_of": story_of, "lines": lines, "stocks": sx,
            "channels_all": all_ch, "n_channels_all": len(all_ch), "series": series, "prev": prev, "n_items": len(items)}


def as_report_news(built):
    """꼭 볼 뉴스 → report.out.json 의 news 칸 모양 [{index, why}] — 기록(record_store.daily_rows) · 검증이 보는 것. 기사가 대표인 묶음만(방송 대표는 index 가 없다)."""
    out = []
    for g in built["picks"]:
        if g["rep"]["kind"] == "article":
            out.append({"index": g["rep"]["index"], "why": " · ".join(g["why"]), "story": g["name"], "n_channels": g["n_channels"]})
    return out
