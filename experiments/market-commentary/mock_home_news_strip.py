"""홈 실적 한 줄 자리 — 실적 일정이 없는 날 주요 뉴스 롤링 목업.

    python experiments/market-commentary/mock_home_news_strip.py   # → output/mock_home_news_strip_us.html · _kr.html

- 바탕 = 지금 테마(alphaflow-home.html, C안 들어간 것)의 홈 미리보기(build_theme --preview). 실적 일정만 비운다.
- 지금 테마는 일정이 없으면 그 자리에 주식 공부 배너(11-15) — 목업은 그 자리를 주요 뉴스 줄 롤링으로 바꾼다(주식 공부 배너는 홈 아래쪽에 따로 있다).
- 미국 = 홈 주요 뉴스와 같은 news.json(gh-pages, 번역 제목). 한국 = 한국 증시 리포트 뉴스 탭과 같은 재료(한국 증시 방송 이슈) — 목업은 11-19 사본(samples/, git 제외).
- 아래 STRIP_JS · STRIP_CSS 가 그대로 테마에 들어갈 코드다. AI · 수집 · 쓰기 0.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "output")
KR_SAMPLE = os.path.join(HERE, "samples", "kr_news_2026-11-19.json")

STRIP_CSS = """<style>
/* 실적 한 줄 자리 — 일정이 없는 날 주요 뉴스 줄. 같은 한 줄 칸(높이 47) · 같은 바탕색 돌림 · 같은 점 */
#event-banner .eb-news { gap: 8px; }
#event-banner .eb-news .eb-tag { flex: none; font-size: 12px; line-height: 19px; padding: 0 6px; border-radius: 4px; background: rgba(255, 255, 255, .2); color: #fff; font-weight: 700; }
#event-banner .eb-news .eb-headline { flex: 1 1 auto; min-width: 0; font-size: 15px; line-height: 24px; font-weight: 700; color: #fff;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; letter-spacing: 0; }
</style>"""

# 테마 setEvents 의 `일정이 없으면 주식 공부 배너` 줄을 이 함수 부르기로 바꾼다
STUDY_LINE = "if (ready) { box.style.setProperty('--eb-bg', STUDY_BG); track.appendChild(studySlide()); dotBox.hidden = true; }"
NEWS_LINE = "if (ready) newsStrip(box, track, dotBox);"
STRIP_JS = r"""
  /* 일정이 없는 날 = 주요 뉴스 줄 롤링.
     미국 = 홈 주요 뉴스와 같은 news.json · 한국 = 한국 증시 리포트 뉴스 탭과 같은 재료(한국 증시 방송 이슈, kr-news.json).
     최근 24시간 · 최신 5줄. 줄을 누르면 미국 = 홈 아래 주요 뉴스로 · 한국 = 한국 증시 리포트(최신 글). 줄이 없으면 칸을 숨긴다 */
  var NEWS_STRIP_N = 5, KR_NEWS_URL = GH + 'kr-news.json', stripNewsCache = {};
  function newsStrip(box, track, dotBox) {
    var mk = HOME_MKT || 'us';
    var p = stripNewsCache[mk] || (stripNewsCache[mk] = fetch((mk === 'kr' ? KR_NEWS_URL : NEWS_URL) + '?v=' + Math.floor(Date.now() / 6e5))
      .then(function (r) { return r.json(); }));
    p.then(function (j) {
      if (pickEvents().length) return;   /* 그 사이 일정이 왔으면 일정이 먼저 */
      var since = Date.now() - 24 * 3600e3;
      var items = (j.items || []).filter(function (it) {
        var s = String(it.published || it.at || '').replace(' ', 'T'), t = s ? Date.parse(/[Z+]/.test(s.slice(10)) ? s : s + 'Z') : 0;   /* 두 파일 모두 UTC 시각 */
        return (it.title_ko || it.title) && (!t || t >= since);
      }).slice(0, NEWS_STRIP_N);
      if (!items.length) { box.hidden = true; return; }
      track.textContent = ''; dotBox.textContent = '';
      items.forEach(function (it, i) {
        var a = el('a', 'eb-slide eb-news');
        if (mk === 'kr') { a.href = '/search/label/' + encodeURIComponent('한국 증시 리포트'); a.setAttribute('data-latest', '한국 증시 리포트'); }
        else {
          a.href = '#news-list';
          a.addEventListener('click', function (e) { var n = document.querySelector('.news-section'); if (n) { e.preventDefault(); n.scrollIntoView({ behavior: 'smooth', block: 'start' }); } });
        }
        a.appendChild(el('span', 'eb-tag', 'News'));   /* 라벨 = 미국 · 한국 모두 영어 `News`, 한국 `방송` 라벨 따로 두지 않음 */
        a.appendChild(el('span', 'eb-headline', it.title_ko || it.title));
        track.appendChild(a);
        var d = el('button', 'eb-dot'); d.type = 'button'; d.setAttribute('aria-label', (i + 1) + '번째 뉴스');
        d.addEventListener('click', function () { ebGo(i); ebStart(); });
        dotBox.appendChild(d);
      });
      dotBox.hidden = items.length < 2;
      box.hidden = false; ebIndex = 0; ebGo(0); ebStart();
    }).catch(function () { box.hidden = true; });
  }
"""


def us_news():
    """미국 = 지금 홈이 읽는 news.json (gh-pages) — 목업도 실제 파일."""
    with urllib.request.urlopen("https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages/news.json", timeout=30) as r:
        return json.load(r)


def build(src, mkt, news, kr_news):
    html = src
    themed = "function newsStrip(" in html   # 11-19 테마에 들어간 뒤 = 테마 코드 그대로(목업은 자료만 흉내)
    if not themed:
        if STUDY_LINE not in html:
            sys.exit("주식 공부 줄을 못 찾음 — 테마가 바뀌었나")
        html = html.replace(STUDY_LINE, NEWS_LINE, 1)
        i = html.index("  function setEvents(market, list) {")
        html = html[:i] + STRIP_JS + html[i:]
    # 미리보기 가짜 자료: 일정 비우기 · 뉴스 = 실제 news.json / 한국 방송 사본
    html = html.replace("    else if (u.indexOf('news.json') >= 0) body = PV_NEWS;",
                        "    else if (u.indexOf('kr-news.json') >= 0) body = window.PV_KR_NEWS;\n    else if (u.indexOf('news.json') >= 0) body = window.PV_US_NEWS;", 1)
    shim = ("<script>window.PV_US_NEWS = " + json.dumps(news, ensure_ascii=False) + ";window.PV_KR_NEWS = " + json.dumps(kr_news, ensure_ascii=False) +
            ";</script>")
    html = html.replace("<head>", "<head>\n" + shim, 1)
    html = re.sub(r"(var PV_PICKS = )", r"\1", html)
    html = html.replace("window.PV_EVENT_HREF = function", "PV_PICKS.events = []; PV_KR.events = [];\n  window.PV_EVENT_HREF = function", 1)
    html = re.sub(r"<body([^>]*)>", lambda m: f"<body{m.group(1)} data-home-mkt=\"{mkt}\">", html, count=1)
    if not themed:
        html = html.replace("</head>", STRIP_CSS + "</head>", 1)
    html = re.sub(r"<title>.*?</title>", f"<title>홈 · {'미국' if mkt == 'us' else '한국'} · 일정 없는 날 뉴스 줄</title>", html, count=1, flags=re.S)
    out = os.path.join(OUT, f"mock_home_news_strip_{mkt}.html")
    open(out, "w", encoding="utf-8").write(html)
    return out


def main():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, os.path.join(ROOT, "build_theme.py"), "--preview"], cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
    src = open(os.path.join(ROOT, "preview.html"), encoding="utf-8").read()
    kr = json.load(open(KR_SAMPLE, encoding="utf-8")) if os.path.exists(KR_SAMPLE) else {"items": []}
    news = us_news()
    for mkt in ("us", "kr"):
        print(build(src, mkt, news, kr))


if __name__ == "__main__":
    main()
