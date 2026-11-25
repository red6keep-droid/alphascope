"""홈 나누기 목업 — 미국 화면 · 한국 화면 (2026-11-10 사용자, 홈 수정 H35).

    python experiments/home-split/mock_home_split.py     # output/mock_home_us.html · mock_home_kr.html

실제 홈 미리보기(build_theme.py --preview → preview.html, 가짜 자료 포함)를 그대로 쓰고 두 가지만 바꾼다.
  (1) <body data-home-mkt="us"|"kr"> — alphaflow-home.html 의 H35 장치(CSS · HOME_MKT)가 그 시장만 보인다
  (2) 상단 메뉴 = 미국 · 한국 · 증시 전망 (목업에서는 미국 · 한국이 서로의 목업 파일로 간다)
적용 때: 메뉴는 build_theme.py 의 Blogger 메뉴, data-home-mkt 는 테마가 홈(/) = us · 고정 페이지 /p/korea.html = kr 로 붙인다.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "output")

FILES = {"us": "mock_home_us.html", "kr": "mock_home_kr.html"}


def nav(mkt, files=FILES):
    cur = lambda m: ' aria-current="page"' if m == mkt else ""
    return (
        '<nav class="menu-items" id="primary-menu" aria-label="주 메뉴">\n'
        # data-bar = 로고 줄 스위치 후보(지금 화면이 아닌 쪽 하나가 국기 data-flag 와 함께 보인다). 나머지(증시 전망)는 메뉴 아이콘 서랍에만 (2026-11-10 사용자)
        f'      <a class="nav-item" href="{files["us"]}"{cur("us")} data-bar="1" data-flag="us">미국</a>\n'
        f'      <a class="nav-item" href="{files["kr"]}"{cur("kr")} data-bar="1" data-flag="kr">한국</a>\n'
        '      <a class="nav-item" href="/p/forecast-list.html">증시 전망</a>\n'
        '    </nav>'
    )


KR_NEWS_PUBLIC = "https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/kr-news.json"


def kr_news():
    """한국 홈 주요 뉴스 재료 = 운영과 같은 kr-news.json(한국 증시 방송 이슈, kr-market-report main._home_news) (2026-11-24 사용자 "방송 뉴스라도 나와야").
    로컬 결과가 있으면 그것, 없으면 운영 gh-pages 공개 파일(읽기만). 못 받으면 None — 테마는 '불러올 수 없습니다'를 그린다. 옛 가짜 한국 뉴스 8건은 뺌"""
    lp = os.path.join(ROOT, "experiments", "kr-market-report", "output", "kr_news.json")
    try:
        if os.path.exists(lp):
            with open(lp, encoding="utf-8") as f:
                return json.load(f)
        import urllib.request
        with urllib.request.urlopen(KR_NEWS_PUBLIC, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print("[home-split] kr-news.json 못 받음:", str(e)[:120])
        return None


KR_FACTS_PUBLIC = "https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/kr-facts.json"


def kr_facts():
    """한국 홈 주요 뉴스의 사건별 사실 = 운영과 같은 gh-pages kr-facts.json(kr-facts.yml). 아직 없으면 받은 표본(news-posts/samples, fetch_samples.py)으로 같은 꼴을 만든다 (2026-11-24)."""
    try:
        import urllib.request
        with urllib.request.urlopen(KR_FACTS_PUBLIC, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        pass
    sd = os.path.join(ROOT, "experiments", "news-posts", "samples")
    fp, hp = os.path.join(sd, "facts_blog.json"), os.path.join(sd, "headlines.json")
    if not (os.path.exists(fp) and os.path.exists(hp)):
        print("[home-split] 사건별 사실 없음 — Pages 도 표본도 없음 (fetch_samples.py 로 받기)")
        return None
    import tempfile
    sys.path.insert(0, os.path.join(ROOT, "experiments", "news-posts"))
    import kr_facts_store as KS
    with open(fp, encoding="utf-8") as f, open(hp, encoding="utf-8") as g:
        fd, hd = json.load(f), json.load(g)
    with tempfile.TemporaryDirectory() as t:
        KS.write_store(t, fd, hd)
        with open(os.path.join(t, "kr", "facts", "latest.json"), encoding="utf-8") as f:
            return json.load(f)


_PICKS = []


def next_picks():
    if _PICKS:
        return _PICKS[0]
    _PICKS.append(_next_picks())
    return _PICKS[0]


def _next_picks():
    """홈 stocks.json 흉내 — 종목 = WATCH_NEXT 전부, 값 = 종목 모아보기 목업과 같은 실제 값(mock_stock_lists.load + extra_rows)."""
    sys.path[:0] = [os.path.join(ROOT, "experiments", "stock-lists")]
    try:
        import mock_stock_lists as ML
    except SystemExit:
        return None
    rows, _ = ML.load()
    syms = [x for _, g in ML.U.WATCH_NEXT for x in g]
    ML.extra_rows(rows, syms)
    stocks = []
    for x in dict.fromkeys(syms):
        r = rows.get(x)
        if not r:
            continue
        slug = (r.get("u") or "").split("/p/")[-1].replace(".html", "") if "/p/" in (r.get("u") or "") else ""
        stocks.append({"s": x, "name": r["n"], "sector": r["sec"], "p": r["c"], "cp": r["r"], "page": bool(slug), "slug": slug, "mc": r.get("cap") or 0})
    have = {x["s"] for x in stocks}
    day = max(r["d"] for r in rows.values() if r["m"] == "us")
    return {"day": day, "stocks": stocks, "watch": [{"group": g, "syms": [x for x in s if x in have]} for g, s in ML.U.WATCH_NEXT], "sectors": [], "events": []}


def split_html(src, mkt, files=FILES):
    """preview.html → 홈 나누기 화면(mkt = us | kr). 다른 목업(검색 · 질문하기 등)도 이걸 써서 지금 홈 기준으로 맞춘다 (2026-11-10)"""
    html = src
    html, n1 = re.subn(r'<body data-pv-view="home"', f'<body data-pv-view="home" data-home-mkt="{mkt}"', html, count=1)
    html, n2 = re.subn(r'<nav class="menu-items" id="primary-menu".*?</nav>', lambda m: nav(mkt, files), html, count=1, flags=re.S)
    html = html.replace('<a class="logo" href="/">', f'<a class="logo" href="{files["us"]}">', 1)
    # 미리보기 스크립트는 메뉴 첫 줄을 '현재'로 칠한다 — 이 목업에서는 그 시장 메뉴를
    html = html.replace("var homeLink = document.querySelector('.menu-items .nav-item');",
                        "var homeLink = document.querySelector('.menu-items .nav-item[aria-current]');", 1)
    # 미리보기 전환 막대(홈 · 목록 · 글 보기)는 이 목업과 상관없어 숨긴다
    html = html.replace("</head>", "<style>.pv-bar{display:none!important}</style>\n</head>", 1)
    # 증시 전망 카드 자료 = 로컬 forecast_daily 결과(experiments/issue_store/output/forecast/hypo.json) — 홈 화면이 그 나라 전망만 거르는지 본다 (2026-11-12)
    hp = os.path.join(ROOT, "experiments", "issue_store", "output", "forecast", "hypo.json")
    if os.path.exists(hp):
        with open(hp, encoding="utf-8") as f:
            html = html.replace("<head>", "<head>\n<script>window.PV_HYPO = " + f.read().replace("</", "<\\/") + ";</script>", 1)
    ip = os.path.join(ROOT, "experiments", "issue_store", "output", "issue", "issues.json")   # Hot Issue 카드 자료 = issue_watch_daily 결과 (2026-11-16)
    if os.path.exists(ip):
        with open(ip, encoding="utf-8") as f:
            html = html.replace("<head>", "<head>\n<script>window.PV_ISSUES = " + f.read().replace("</", "<\\/") + ";</script>", 1)
    # 업종 종목 탭 자료 = 간단 종목 실행이 올린 목록 파일(원격 브랜치 quick-us · quick-kr 의 _lists.json, `git fetch origin quick-us quick-kr` 뒤) (2026-11-18)
    lists = {}
    for m in ("us", "kr"):
        r = subprocess.run(["git", "show", f"origin/quick-{m}:{m}/_lists.json"], capture_output=True, cwd=ROOT)
        if r.returncode == 0:   # 업종 이름은 build_lists.sector11 로 다시 맞춘다 — 원격 파일이 고치기 전 판이어도 목업은 고친 뒤 모습 (2026-11-18)
            import json as _j
            sys.path.insert(0, os.path.join(ROOT, "experiments", "stock-lists"))
            sys.path[:0] = [os.path.join(ROOT, "experiments"), os.path.join(ROOT, "experiments", "stock-radar"), os.path.join(ROOT, "experiments", "kr-stocks")]
            import build_lists as BL
            d = _j.loads(r.stdout.decode("utf-8"))
            for x in d.get("rows", []):
                x["s"] = BL.sector11(x.get("s"))
            lists[m] = _j.dumps(d, ensure_ascii=False)
    if lists:
        html = html.replace("<head>", "<head>\n<script>window.PV_LISTS = {" + ",".join(f'"{m}":{t}' for m, t in lists.items()).replace("</", "<\\/") + "};</script>", 1)
    # 테마 종목 = 다음 테마 구성(universe.WATCH_NEXT) · 값 = 목록 파일 실제 값 (2026-11-18 사용자: 반도체를 하는 일로 넷 · 새 정식 후보)
    picks = next_picks()
    if picks:
        html = html.replace("<head>", "<head>\n<script>window.__PICKS = " + json.dumps(picks, ensure_ascii=False).replace("</", "<\\/") + ";</script>", 1)
        html = html.replace("else if (u.indexOf('stocks.json') >= 0) body = PV_PICKS;", "else if (u.indexOf('stocks.json') >= 0) body = (window.__PICKS || PV_PICKS);", 1)
    if mkt == "kr":   # 한국 홈 주요 뉴스 = 실제 kr-news.json (2026-11-24, 옛 가짜 한국 뉴스 2026-11-15)
        kn = kr_news()
        if kn:
            html = html.replace("<head>", "<head>\n<script>window.PV_KR_NEWS = " + json.dumps(kn, ensure_ascii=False).replace("</", "<\\/") + ";</script>", 1)
        try:   # Newfact 글(news-posts.json) = 운영 gh-pages 공개 파일 읽기만 — 홈 `오늘의 Newfact` 배지 줄 (2026-11-25)
            import urllib.request
            with urllib.request.urlopen(KR_FACTS_PUBLIC.replace("kr-facts.json", "news-posts.json"), timeout=20) as r:
                html = html.replace("<head>", "<head>\n<script>window.PV_NF_POSTS = " + r.read().decode("utf-8").replace("</", "<\\/") + ";</script>", 1)
        except Exception as e:  # noqa: BLE001
            print("[home-split] news-posts.json 못 받음:", str(e)[:120])
        kf = kr_facts()
        if kf:
            html = html.replace("<head>", "<head>\n<script>window.PV_KR_FACTS = " + json.dumps(kf, ensure_ascii=False).replace("</", "<\\/") + ";</script>", 1)
    # 주식 공부 배너 — gh-pages 에 올리기 전에는 로컬 그림을 그대로 넣어 본다 (2026-11-15)
    bp = os.path.join(ROOT, "experiments", "course", "banner", "home_banner.webp")
    if os.path.exists(bp):
        import base64
        with open(bp, "rb") as f:
            html = html.replace("https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/images/study/home_banner.webp",
                                "data:image/webp;base64," + base64.b64encode(f.read()).decode())
    if not (n1 and n2):
        sys.exit(f"바꿀 자리를 못 찾음 (body {n1} · 메뉴 {n2}) — preview.html 구조 확인")
    return html


def main():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, os.path.join(ROOT, "build_theme.py"), "--preview"], cwd=ROOT, env=env,
                   check=True, stdout=subprocess.DEVNULL)
    with open(os.path.join(ROOT, "preview.html"), encoding="utf-8") as f:
        src = f.read()
    os.makedirs(OUT, exist_ok=True)
    for mkt, name in FILES.items():
        html = split_html(src, mkt)
        title = "홈 나누기 — 미국 화면" if mkt == "us" else "홈 나누기 — 한국 화면"
        html = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", html, count=1, flags=re.S)
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(html)
        print("만듦:", os.path.join("experiments", "home-split", "output", name))


if __name__ == "__main__":
    main()
