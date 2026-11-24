"""Newfact 주요 기사 · 한국 기사 제목 묶음 — 블로그 화면 목업 (2026-11-23 사용자 "여기서 새로 그려").

    python experiments/news-posts/mock_news_post.py

- 재료: samples/posts.json · samples/headlines.json 이 있으면 그것(수집기 블로그 저장소에서 받은 실제 자료 — fetch_samples.py, git 제외).
  없으면 아래 SAMPLE_POST(11-18 시황 해설 시험 글의 사실로 블로그가 손으로 쓴 예시) · SAMPLE_HEADLINES(지어낸 예시, 매체 · 주소 가짜).
- 같은 날 시장 움직임 = yfinance 일봉(코스피 · 코스닥 · 종목). 장중 값은 쓰지 않는다(오늘은 15:40 KST 뒤에만).
- 출력: output/mock_news_post*.html · output/mock_news_headlines.html. AI 0 · 쓰기 0.
"""
import datetime
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, ".."))
import design_kit as dk  # noqa: E402
import news_render as NR  # noqa: E402

OUT = os.path.join(BASE, "output")
SAMPLES = os.path.join(BASE, "samples")
LISTS = {mk: os.path.join(BASE, "..", "stock-lists", "output", "lists", mk, "_lists.json") for mk in ("kr", "us")}   # 한국 + 미국 (2026-11-23 사용자 "미국 종목도")

SAMPLE_POST = {
    "id": "sample-1",
    "title": "엔비디아 호실적 뒤 삼성전자 · SK하이닉스 반등, 외국인 매도 구조는 남아",
    "summary": "엔비디아가 3분기 실적과 4분기 전망을 내놓은 뒤 나흘 내리던 삼성전자와 SK하이닉스가 함께 반등했습니다. 외국인 순매도가 두 종목에 몰리는 구조는 그대로입니다.",
    "body": ("엔비디아가 **3분기 매출 1,158억 달러**를 발표하고 4분기 매출 전망을 약 1,300억 달러로 내놓았습니다. "
             "==AI 데이터센터 투자가 이어진다는 숫자==가 나오면서, 앤트로픽 상장에 자금이 쏠릴 것이라는 우려로 나흘 연속 내렸던 국내 반도체주에 매수세가 들어왔습니다.\n\n"
             "삼성전자와 SK하이닉스는 이날 함께 **반등**했습니다. 두 종목 주가는 고점보다 평균 55% 낮아진 상태였고, "
             "==과도한 우려가 이미 주가에 반영됐다는 분석==(이창민 KB증권 연구원)이 나왔습니다.\n\n"
             "다만 올해 외국인 순매도의 85%가 두 종목에 몰려 있습니다. "
             "==MSCI 지수 비중 상한을 넘을 때마다 매도가 나오는 구조==(하나증권)도 **그대로 남아 있습니다**."),
    "date": "2026-11-18", "cat": "AI_CAPEX", "direction": "up", "stage": "confirmed",
    "stocks": [{"name": "삼성전자", "code": "005930"}, {"name": "SK하이닉스", "code": "000660"}, {"name": "엔비디아", "code": ""}],   # 미국 종목 = 수집기처럼 코드 빈 값
    "sector": "기술", "slug": "nvidia-earnings-samsung-hynix-rebound", "version": 2,
}


def _fake(no, ev, cat, title, h, m):
    return {"title": title, "outlet": f"예시 매체 {no}", "url": f"https://www.outlet-{no}.example/news/{1000 + no * 7 + h}",
            "publishedAt": f"2026-11-18T{h:02d}:{m:02d}:00+09:00", "foundAt": None, "event": ev, "cat": cat, "stocks": []}


SAMPLE_HEADLINES = [{"run": "sample", "part": 1, "parts": 1, "version": 1, "items": [
    _fake(1, "반도체 반등", "AI_CAPEX", "가상 반도체 대형주 일제히 반등, 외국인 닷새 만에 순매수", 15, 41),
    _fake(2, "반도체 반등", "AI_CAPEX", "예시 기사: 메모리 업황 우려 덜며 반도체주 강세", 15, 52),
    _fake(3, "반도체 반등", "AI_CAPEX", "예시 기사: 반도체 두 종목이 지수 상승의 절반 이상 차지", 16, 5),
    _fake(4, "정책금리 동결 전망", "RATES_FED", "가상 중앙은행, 다음 주 금리 동결 무게", 14, 10),
    _fake(5, "정책금리 동결 전망", "RATES_FED", "예시 기사: 환율 부담에 금리 인하 미룰 듯", 13, 2),
    _fake(6, "가상 제조사 A 공장 증설", "CORP_EVENT", "가상 제조사 A, 해외 공장 증설 계약 체결", 11, 30),
    _fake(7, "가상 제조사 A 공장 증설", "CORP_EVENT", "예시 기사: 제조사 A 증설 규모 1조 원대", 12, 15),
    _fake(8, "대출 규제 완화 검토", "REGULATION", "가상 금융당국, 대출 규제 완화 검토", 10, 0),
    _fake(9, "유가 하락", "OIL_ENERGY", "예시 기사: 국제 유가 사흘째 하락", 9, 20),
    _fake(10, "유가 하락", "OIL_ENERGY", "예시 기사: 원유 재고 늘며 유가 약세", 9, 45),
    _fake(11, "유가 하락", "OIL_ENERGY", "예시 기사: 정유주 약세, 유가 내림세 영향 지켜봐야", 10, 40),
    _fake(12, "유가 하락", "OIL_ENERGY", "예시 기사: 항공주는 유가 하락에 강세", 11, 5),
    _fake(13, "유가 하락", "OIL_ENERGY", "예시 기사: 산유국 증산 논의 이어져", 8, 30),
    _fake(14, "가상 지수 마감", "MARKET_STRUCTURE", "가상 지수 2% 오른 채 마감", 15, 35),
    _fake(15, "환율 하락", "FX_GLOBAL", "예시 기사: 원 · 달러 환율 1,400원 아래로", 15, 50),
]}]


def load(name, fallback):
    p = os.path.join(SAMPLES, name)
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8")), True
    return fallback, False


_cache = {}
import re as _re0
_svg = _re0.search(r"<svg class='logo-full'.*?</svg>", open(os.path.join(BASE, "..", "..", "index.html"), encoding="utf-8").read(), _re0.S)
LOGO_TPL = f"<template data-nf-logo>{_svg.group(0)}</template>" if _svg else ""


def closes_of(sym):
    if sym not in _cache:
        import yfinance as yf
        h = yf.Ticker(sym).history(period="1y", auto_adjust=False)["Close"].dropna()
        _cache[sym] = [(str(i.date()), float(v)) for i, v in h.items()]
    return _cache[sym]


def closed_through():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    return now.strftime("%Y-%m-%d") if now.hour * 60 + now.minute >= 15 * 60 + 40 else (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(OUT, exist_ok=True)
    lists = {r["t"]: dict(r, mk=mk) for mk, p in LISTS.items() if os.path.exists(p) for r in json.load(open(p, encoding="utf-8"))["rows"]}
    themes = {mk: json.load(open(p, encoding="utf-8")).get("themes") or [] for mk, p in LISTS.items() if os.path.exists(p)}   # 테마 구성 = 종목 모아보기와 같은 파일
    _iss = os.path.join(BASE, "..", "issue_store", "output", "issue", "issues.json")      # Hot Issue · 증시 전망 = 홈 카드와 같은 파일
    _hyp = os.path.join(BASE, "..", "issue_store", "output", "forecast", "hypo.json")
    issues = json.load(open(_iss, encoding="utf-8"))["issues"] if os.path.exists(_iss) else []
    forecasts = json.load(open(_hyp, encoding="utf-8"))["open"] if os.path.exists(_hyp) else []
    posts, real = load("posts.json", [SAMPLE_POST])
    print("글 재료:", "수집기 실제 글" if real else "예시 글", len(posts), "편")
    upto = closed_through()
    jobs = [("mock_news_post.html" if i == 0 else f"mock_news_post_{i + 1}.html", post)
            for i, post in enumerate(sorted(posts, key=lambda p: str(p.get("createdAt") or p["date"]), reverse=True))]
    extra, _ = load("posts_extra.json", [])   # 시안만: 수집기 원래 저장소의 v2 글 중 보라 강조가 든 것(검사 실패라 블로그엔 안 옴) — 홈 카드 · 목록엔 넣지 않는다
    extra_jobs = [(f"mock_news_post_{len(jobs) + k + 1}.html", post) for k, post in enumerate(extra)]
    for name, post in jobs + extra_jobs:
        market = NR.same_day(post, lists, closes_of, upto, themes=themes)
        _, html, meta = NR.render(post, market, lists, issues, forecasts)
        html = html.replace(dk.WRAP_OPEN, dk.WRAP_OPEN + LOGO_TPL, 1)   # 목업만: 머리 줄 로고가 없어 테마 JS 가 쓸 로고 원본
        out = os.path.join(OUT, name)
        print(dk.write_mock(html, out, NR.titles(post)[0]) or "index.html 없음", "· 기준", meta["basis"], "· 관련 종목", len(market["stocks"]), [s["name"] for s in market["stocks"]][:6],
              "· 함께 보는 페이지", [t for t, _ in NR.follow_links(post, market, lists, issues, forecasts)])
    docs, real_h = load("headlines.json", SAMPLE_HEADLINES)
    day = max(str(it.get("publishedAt") or it.get("foundAt") or "")[:10] for d in docs for it in d.get("items") or [])
    sec = NR.headlines_section(docs, day)
    page = dk.WRAP_OPEN + sec + dk.WRAP_CLOSE
    print(dk.write_mock(page, os.path.join(OUT, "mock_news_headlines.html"), "한국 증시 리포트 · 뉴스 (한국 기사 묶음)"),
          "·", "수집기 실제 제목" if real_h else "예시 제목", "·", day)
    # 사건별 사실 = 블로그 저장소 facts(수집기 R17 ~ R22, 첫 문서 11-24 07:46) → 운영과 같은 kr_facts_store 꼴로 (2026-11-24).
    # 표본(samples/facts_blog.json)이 없으면 옛 시안(facts.json = eventsets 변환)으로.
    fb = os.path.join(BASE, "samples", "facts_blog.json")
    if os.path.exists(fb):
        import tempfile
        import kr_facts_store as KS
        with tempfile.TemporaryDirectory() as t:
            KS.write_store(t, json.load(open(fb, encoding="utf-8")), docs)
            kf = json.load(open(os.path.join(t, "kr", "facts", "latest.json"), encoding="utf-8"))
        page = dk.WRAP_OPEN + NR.facts_section(kf["facts"], kf["headlines"], kf["day"]) + dk.WRAP_CLOSE
        print(dk.write_mock(page, os.path.join(OUT, "mock_news_facts.html"), "한국 증시 리포트 · 뉴스 (사건별 사실)"), "·", kf["day"],
              "· 사건", kf["count"], "· 기사 제목", kf["headlineCount"])
    facts, real_f = load("facts.json", [])
    if real_f and not os.path.exists(fb):   # 옛 시안 = 수집기 eventsets 를 facts 모양으로 바꾼 표본(ca7a6b8 전이라 사실마다 보도 수 1 → 사건 기준만)
        fday = max(str(d.get("createdAt"))[:10] for d in facts)
        import difflib
        import re as _re

        def _key(t):
            return _re.sub(r"[^0-9가-힣a-zA-Z]", "", t)

        for d in facts:   # 시안만: R22(수집기가 같은 사실끼리 묶기) 전 자료라 비슷한 문장을 블로그에서 대신 합친다 — 합친 수를 sources 로
            for e in d["events"]:
                kept = []
                for f in e["facts"]:
                    k = _key(f["what"])
                    hit = next((g for g in kept if difflib.SequenceMatcher(None, k, g["_k"]).ratio() >= 0.55), None)
                    if hit:
                        hit["sources"] += 1
                    else:
                        kept.append(dict(f, _k=k, sources=1))
                e["facts"] = sorted(kept, key=lambda f: -f["sources"])
        page = dk.WRAP_OPEN + NR.facts_section(facts, docs, fday, fact_min=1) + dk.WRAP_CLOSE
        print(dk.write_mock(page, os.path.join(OUT, "mock_news_facts.html"), "한국 증시 리포트 · 뉴스 (사건별 사실)"), "·", fday,
              "· 사건", len(NR.fact_events(facts)))

    # ── 한국 홈 카드 `Newfact 주요 기사` (2026-11-23 사용자 "홈 카드도 새로") — 한국 홈 목업(home-split)에 끼워 본다 ──
    # 자리 = 한국 증시 리포트 카드 바로 아래 · 꼴 = 홈 주요 뉴스와 같은 줄(제목 17 굵게 · 요약 16 · 라벨 + 날짜), 5편 + 더 보기(버리지 않음).
    # 제목 = 글 제목 줄과 같은 Newfact 로고 + 작은 `주요 기사`. 적용 때 자료 = Pages posts/index.json(앱 대비 원칙 4절), 방문자 요청 1번.
    import html as _h
    home = os.path.join(BASE, "..", "home-split", "output", "mock_home_kr.html")
    if os.path.exists(home):
        svg = _svg.group(0).replace("class='logo-full'", "class='nf-home-logo'") if _svg else ""
        rows = []
        for k, (name, post) in enumerate(jobs):
            d = NR.DIR_KIND.get(post.get("direction"), "neutral")
            tags = (f'<span class="news-tag">{_h.escape(dk.ISSUE_KO.get(post.get("cat"), "그 밖"))}</span>'
                    f'<span class="news-tag issue-tag {d}">{_h.escape(dk.DIR_KO.get(d))}</span>')
            y, m, dd = post["date"].split("-")
            summ = (post.get("summary") or "").strip()
            rows.append(f'<article class="news-item"{" hidden data-news-more=1" if k >= 5 else ""}><a href="{name}">{_h.escape(post["title"])}</a>'
                        + (f'<span class="news-sum">{_h.escape(summ)}</span>' if summ else "")
                        + f'<span class="news-labels">{tags}<span class="news-sub">{int(m)}.{dd}</span></span></article>')
        last = max(post["date"] for _, post in jobs)
        card = ('<style>#nf-posts-col .report-title{gap:8px;}'
                '.nf-home-logo{width:96px;height:22px;flex:none;display:block;}'
                '.nf-home-sub{display:inline-flex;align-items:center;gap:8px;font-size:13px;line-height:19px;font-weight:400;letter-spacing:0;color:#6B7280;}.nf-home-sub::before{content:'';width:1px;height:13px;background:#CBD5E1;}'
                '#nf-posts-card{gap:0;}#nf-posts-card .news-item:first-child{padding-top:0;}#nf-posts-card .news-item:last-child{padding-bottom:0;}</style>'
                '<div class="report-col" id="nf-posts-col">'
                f'<h3 class="report-title">{svg}<span class="nf-home-sub">주요 기사</span>'
                f'<span class="report-card-date">{int(last[5:7])}.{last[8:10]}</span></h3>'
                f'<div class="report-card" id="nf-posts-card">{"".join(rows)}</div></div>')
        src = open(home, encoding="utf-8").read()
        mark = '<!-- 엔비디아 리포트 카드는 삭제'   # 한국 증시 카드 바로 다음
        page = src.replace(mark, card + mark, 1)
        page = page.replace('href="mock_home_us.html"', 'href="../../home-split/output/mock_home_us.html"').replace('href="mock_home_kr.html"', 'href="mock_news_home_kr.html"')
        page = _re0.sub(r"<title>.*?</title>", "<title>Newfact 주요 기사 — 한국 홈 카드</title>", page, count=1, flags=_re0.S)
        out = os.path.join(OUT, "mock_news_home_kr.html")
        open(out, "w", encoding="utf-8").write(page)
        print(out, "· 홈 카드", len(rows), "편")

    # ── 한국 홈 맨 아래 `주요 뉴스` — 테마가 직접 그린다(2026-11-24): 방송 이슈(kr-news.json) + 한국 기사 공용 저장소 사건별 사실(gh-pages kr-facts.json, kr-facts.yml).
    # 재료는 홈 나누기 목업(mock_home_split.py)이 실제 파일(없으면 samples 표본)로 넣어 둔다 — 여기서 따로 섞지 않는다(옛 덮어쓰기 11-23 ~ 11-24).
