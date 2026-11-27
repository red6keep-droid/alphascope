"""홈 증시시황 카드 목업.

    python experiments/market-commentary/mock_home_commentary.py   # → output/mock_home_commentary.html (비교) + 화면 6개

실제 홈 미리보기(home-split 의 split_html = 지금 홈 기준)에 시황 카드 안을 끼운다. 블로그 · gh-pages 쓰기 0, AI 0.
  ( 3차: 옛 C(증시 카드 안 한 줄) 버림 · 세 안 모두 실적 발표 배너 바로 밑 = 홈 맨 위 쪽)
  A 카드형 — 실적 발표 배너 밑 첫 카드: 제목 줄(미국 증시시황 · 날짜 시각) + 배너 그림 + 머리글(그날 주제)
  B 배너 카드형 — 실적 발표 배너 밑, 그림만 카드 폭(둥근 모서리 · 그림자, 주식 공부 배너 같은 꼴)
  C 배너 + 실적 한 줄 — 맨 위 시황 배너(좌우 꽉 · 모서리 직선) + 바로 밑에 실적 발표를 한 줄로(로고 · 종목 · 실적 발표 · D-n, 날짜 · 시각 줄 뺌)
  → C 로 결정. 4차: 편 이름 알약 = 시각 빼고 `미국 증시시황` 만 · 11px · 제목 글자 바로 위(5 띄움) · 그림 안 `AI 생성 이미지` 삭제(alt 로)
    · 실적 한 줄 높이 +10 · 로고 왼쪽 5 · `D-Day` · 증시 카드 날짜 `11.17 아침` · 증시 카드 요약 글자 = 인물 발언 줄과 같게
    · 카드 순서 = 증시 → Hot Issue → 증시 전망 → 주요 인물 발언 → 주목할 종목 → 시장 흐름과 종목 → 시총 TOP 10
미국 홈 = 아침 편(am, 08:40 발행 `미국 증시시황`) · 한국 홈 = 저녁 편(pm, 21:00 발행 `한국 증시시황`).
배너 그림 = banner.compose + 기본 배너(static/default) — Workers AI 를 부르지 않는다.
미국 · 한국 증시 카드 하루 그래프 = 실제 카드 재료(gh-pages cards/report.json · kr-report.json 11-17 사본, static/sample_cards) — 미리보기는 카드 재료가 없어 글자만 나오던 것.
"""
import base64
import io
import os
import re
import subprocess
import sys
from contextlib import redirect_stdout

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "output")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "experiments", "home-split"))
import banner as B  # noqa: E402
from mock_home_split import split_html  # noqa: E402

EDITIONS = {   # 가짜 글 (목업 전용) — 제목 = 수집기 title(그날 주제), 배너 = 수집기 banner 칸
    "us": {"name": "미국 증시시황", "when": "11월 17일 08:40", "mood": "down", "bg": "down.webp", "slot": "am",
           "title": "앤트로픽 IPO와 엔비디아 악재에 기술주 급락, 나스닥 2.47% 하락",
           "banner": {"titles": [["기술주 내림 뒤", "엔비디아 실적 기다림"]], "keys": ["미국 기술 업종 약세", "반도체 관망", "한국장 첫 반응"]}},
    "kr": {"name": "한국 증시시황", "when": "11월 17일 21:00", "mood": "up", "bg": "up.webp", "slot": "pm",
           "title": "반도체 대형주 반등에 코스피 1.12% 상승, 외국인 사흘 만에 돌아와",
           "banner": {"titles": [["반도체 대형주 반등", "코스피 다시 오름"]], "keys": ["반도체 강세", "조선 오름", "밤 미국 실적 대기"]}},
}
ICON = ("<span class='report-icon' style='background:#0369A1;' aria-hidden='true'><svg viewBox='0 0 16 16' fill='none' stroke='currentColor' "
        "stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'><rect x='2' y='2.5' width='12' height='11' rx='1.5'/>"
        "<path d='M4.5 10.5l2.2-2.4 1.8 1.6 3-3.4'/></svg></span>")

CSS = """<style>
/* 홈 증시시황 카드 (목업) */
.cm-card { gap: 12px !important; padding-top: 14px !important; }
.cm-banner { display: block; width: 100%; height: auto; aspect-ratio: 900 / 350; border-radius: 8px; background: #06121A; }
.cm-head { margin: 0; font-family: var(--report-font); font-size: 17px; line-height: 26px; font-weight: 700; color: #111;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
/* B — 그림만 카드 폭: 둥근 모서리 12 · 카드 그림자 (주식 공부 배너와 같은 꼴) */
.cm-boxed { margin: 0; }
.cm-boxed a { display: block; position: relative; border-radius: 12px; overflow: hidden; -webkit-tap-highlight-color: transparent;
  box-shadow: 0 10px 22.5px -5px rgba(0,0,0,.029), 0 8px 9px -6px rgba(0,0,0,.029); }
.cm-boxed a:active { opacity: .85; }
.cm-boxed img { display: block; width: 100%; height: auto; aspect-ratio: 900 / 350; }
/* C — 시황 배너 좌우 꽉 차게 · 모서리 직선, 로고 줄에 붙임 */
.cm-wide { position: relative; margin: calc(-1 * var(--card-gap)) calc(50% - 50vw) 0; background: #06121A; }
.cm-wide a { display: block; position: relative; border-radius: 0; -webkit-tap-highlight-color: transparent; }
.cm-wide a:active { opacity: .85; }
.cm-wide img { display: block; width: 100%; height: auto; aspect-ratio: 900 / 350; border-radius: 0; }
/* 편 이름 알약 — 제목 글자 왼쪽 끝(그림 가로 8.1%)에 맞추고, 제목 글자 윗선(그림 높이 25.4%, 두 줄 제목 실측)에서 5 위.
   한 줄 큰 제목(104px)이 나가는 날은 제목 윗선이 달라 — 적용 때 발행기가 배너를 그리며 윗선 비율을 카드 파일에 같이 적는다 */
.cm-pill { position: absolute; left: 8.1%; bottom: calc(74.6% + 5px); padding: 2px 8px; border-radius: 999px; background: rgba(6,18,26,.72);
  color: #fff; font-size: 11px; line-height: 16px; font-weight: 600; }
/* C — 실적 발표 배너를 한 줄로 (기존 일정 배너 그대로, 모양만): 로고 24 · 종목 이름 · 실적 발표 · D-n, 날짜 · 시각 줄은 숨김. 높이 44 */
#event-banner.cm-strip .eb-slide { gap: 8px; padding: 11.5px 72px 11.5px 7px; }   /* 높이 54 → 47 */   /* 오른쪽 72 = 점 6개(9 × 6 + 2 × 5 = 64) + 8 — 긴 이름이 점과 겹치지 않게 */   /* 높이 54 · 로고 왼쪽 5 더 (12 → 7) */
#event-banner.cm-strip .stock-avatar { width: 24px; height: 24px; font-size: 10px; }
#event-banner.cm-strip .eb-text { flex-direction: row; align-items: center; gap: 8px; }
#event-banner.cm-strip .eb-kicker, #event-banner.cm-strip .eb-title-line { display: contents; }
#event-banner.cm-strip .eb-name { order: 1; min-width: 0; font-size: 15px; line-height: 24px; font-weight: 700; letter-spacing: 0; }
#event-banner.cm-strip .eb-title { order: 2; font-size: 14px; line-height: 24px; font-weight: 500; color: rgba(255, 255, 255, .85); }
#event-banner.cm-strip .eb-dday { order: 3; font-size: 12px; line-height: 19px; padding: 0 6px; align-self: center; }
#event-banner.cm-strip .eb-when, #event-banner.cm-strip .eb-more { display: none; }
/* 증시 카드 요약 = 주요 인물 발언 줄과 같은 글자 18 · 행간 34 (PC 901 이상은 둘 다 이미 16 · 32) */
#report-card .report-columns li, #kr-report-card .report-columns li { font-size: 18px; line-height: 34px; }
#event-banner.cm-strip .eb-dots { top: 0; bottom: 0; right: 8px; left: auto; align-items: center; }
</style>"""


# 실적 한 줄 — `실적 발표` 는 이름 길이와 상관없이 늘 보인다.
# 넘치는 이름만 끝을 … 로 줄인다 — 폰 360 에서 이름 칸 128px(한글 약 9자). 실적 발표 · D-n 은 줄지 않음.
LONG_CSS = """<style>#event-banner.cm-strip .eb-name { flex: 0 1 auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }</style>"""
# 샘플 일정 — 853종목 중 이름이 가장 긴 종목(미국 ARE · 한국 한국타이어앤테크놀로지)을 오늘(D-Day)로, 다음으로 긴 종목 · 짧은 종목을 뒤에
SAMPLE_EVENTS = {
    "us": [("ARE", "알렉산드리아 리얼 에스테이트 이퀴티스", 0, "amc"), ("FRT", "페더럴리얼티인베스트먼트트러스트", 1, "bmo"), ("XOM", "엑손모빌", 3, "bmo")],
    "kr": [("161390", "한국타이어앤테크놀로지", 0, None), ("445680", "큐리옥스바이오시스템즈", 2, None), ("000270", "기아", 3, None)],
}



# Hot Issue 게시일 샘플 — issues.json 에는 아직 칸이 없다(적용 때 issue_watch_daily 가 페이지 연 날짜를 posted 로 적는다, 수집 · AI 0)
ISSUE_POSTED = {"IRAN": "11.13", "TARIFF": "11.13", "EXPORT": "11.13", "NVDA_CEO": "11.16"}

# 5차 시안 — 편 이름 상자 · Hot Issue 라벨 자리 · 롤링
OPTS = {   #: 시안 3(롤링)으로 결정 — 시안 1(검정 상자 · 라벨 오른쪽) · 2(흰 상자 · 라벨 아래)는 지움(커밋 이력에 있음)
    "c": {"pill": "dark", "issue": "below", "roll": True},
}
PILL_CSS = {
    "dark": ".cm-pill { border-radius: 0; }",   # 검정 둥근 알약 → 네모 상자
    "white": ".cm-pill { border-radius: 0; background: #fff; color: #111; }",
}
ISSUE_OLD = "labels.appendChild(el('span', 'news-sub', '최근 일주일 뉴스' + (q.hot ? ' · 평소보다 많음' : '')));"
ISSUE_NEW = {   # `최근 일주일 뉴스 · 평소보다 많음` 삭제
    "right": "d.classList.add('is-right');",
    "below": "if (q.posted) labels.appendChild(el('span', 'news-sub', q.posted + ' 게시'));",
}
ISSUE_CSS = """<style>
/* 라벨 오른쪽 — 질문 왼쪽 · 라벨 오른쪽 한 줄 */
#issue-card .kv-row.plain-row.is-right { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
#issue-card .kv-row.plain-row.is-right .news-labels { flex: none; margin: 0; }
</style>"""
ROLL_CSS = """<style>
/* 롤링 — 한 줄(질문 + 라벨 · 게시일)씩 아래에서 위로. 펼침 버튼 = 제목 줄 오른쪽 끝 */
.roll-btn { flex: none; display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; margin: -4px -6px -4px 0;
  padding: 0; border: 0; border-radius: 6px; background: none; color: #6B7280; cursor: pointer; -webkit-tap-highlight-color: transparent; }
.roll-btn:active { background: #F3F4F6; }
.roll-btn svg { transition: transform .2s; }
.roll-btn[aria-expanded="true"] svg { transform: rotate(180deg); }
.roll-btn[hidden] { display: none; }
.home-cards .report-title .report-card-date { margin-right: 4px; }
.is-roll { position: relative; overflow: hidden; height: var(--roll-h, 68px); }
.is-roll > .kv-row.plain-row { position: absolute; left: 0; right: 0; top: 0; margin: 0 !important; padding-top: 4px !important; border-top: 0 !important;
  transform: translateY(100%); transition: transform .45s ease; }
.is-roll > .kv-row.plain-row.is-cur { transform: translateY(0); }
.is-roll > .kv-row.plain-row.is-out { transform: translateY(-100%); }
@media (prefers-reduced-motion: reduce) { .is-roll > .kv-row.plain-row { transition: none; } }
</style>"""
ROLL_JS = """<script>(function(){
var CHEV='<svg viewBox="0 0 16 16" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6l4 4 4-4"/></svg>';
var MS=3500, still=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
function setup(colId,hook){
  var col=document.getElementById(colId),box=document.querySelector('[data-hook="'+hook+'"]');if(!col||!box)return;
  var head=col.querySelector('.report-title'),btn=document.createElement('button');
  btn.type='button';btn.className='roll-btn';btn.setAttribute('aria-expanded','false');btn.setAttribute('aria-label','모두 보기');btn.innerHTML=CHEV;btn.hidden=true;head.appendChild(btn);
  var open=false,cur=0,timer=null;
  function rows(){return [].slice.call(box.children).filter(function(r){return r.classList.contains('plain-row');});}
  function stop(){if(timer){clearInterval(timer);timer=null;}}
  function apply(){
    var rs=rows();stop();btn.hidden=rs.length<2;btn.setAttribute('aria-expanded',String(open));btn.setAttribute('aria-label',open?'접기':'모두 보기');
    rs.forEach(function(r){r.classList.remove('is-cur','is-out');});
    if(open||rs.length<2){box.classList.remove('is-roll');box.style.removeProperty('--roll-h');return;}
    box.classList.add('is-roll');
    var h=0;rs.forEach(function(r){h=Math.max(h,r.offsetHeight);});box.style.setProperty('--roll-h',h+'px');
    cur=0;rs[0].style.transition='none';rs[0].classList.add('is-cur');void rs[0].offsetHeight;rs[0].style.transition='';   // 첫 줄은 움직임 없이 바로
    if(!still)timer=setInterval(next,MS);
  }
  function next(){
    var rs=rows();if(rs.length<2)return;var a=rs[cur%rs.length];cur=(cur+1)%rs.length;var b=rs[cur];
    a.classList.remove('is-cur');a.classList.add('is-out');b.classList.add('is-cur');
    setTimeout(function(){a.style.transition='none';a.classList.remove('is-out');void a.offsetHeight;a.style.transition='';},480);
  }
  btn.addEventListener('click',function(ev){ev.preventDefault();ev.stopPropagation();open=!open;apply();});
  new MutationObserver(function(){setTimeout(apply,0);}).observe(box,{childList:true});
  apply();
}
setup('issue-col','issue-rows');setup('hypo-col','hypo-rows');
})();</script>"""


def _sample_js():
    """미리보기의 가짜 fetch 는 cards/ 를 404 로 돌린다 → 그 앞에서 카드 재료 사본을 준다(생성 시각은 지금으로 — 4일 지나 버리는 일 없게)."""
    import json
    cards = {}
    for name in ("report", "kr-report"):
        with open(os.path.join(HERE, "static", "sample_cards", f"{name}.json"), encoding="utf-8") as f:
            cards[name] = json.load(f)
    return ("<script>(function(){var C=" + json.dumps(cards, ensure_ascii=False).replace("</", "<\\/") + ";var E=" + json.dumps(SAMPLE_EVENTS, ensure_ascii=False) + ";var P=" + json.dumps(ISSUE_POSTED) + ";var inner;"
            "function w(url){var u=String(url),m=u.match(/cards\\/(kr-report|report)\\.json/);"
            "if(m){var j=JSON.parse(JSON.stringify(C[m[1]]));j.generated=new Date().toISOString();"
            "return Promise.resolve({ok:true,status:200,json:function(){return Promise.resolve(j);}});}"
            "var r=inner.apply(this,arguments),mk=/stocks\\.json/.test(u)?'us':(/\\/kr\\.json/.test(u)?'kr':(/issues\\.json/.test(u)?'is':''));"
            "if(!mk||!r||!r.then)return r;"
            "return r.then(function(res){var jf=res.json;res.json=function(){return jf.call(res).then(function(j){"
            "if(j&&mk==='is'){(j.issues||[]).forEach(function(q){q.posted=P[q.id]||'';});return j;}"
            "if(j){var t=new Date(Date.now()+9*3600000);j.events=E[mk].map(function(e){var d=new Date(t.getTime()+e[2]*86400000).toISOString().slice(0,10);"
            "return {kind:'earnings',day:d,when:e[3],s:e[0],name:e[1],slug:e[0].toLowerCase()+'-stock'};});}return j;});};return res;});}"
            "inner=window.fetch;Object.defineProperty(window,'fetch',{configurable:true,get:function(){return w;},set:function(v){inner=v;}});})();</script>")


SAMPLE_JS = _sample_js()


# 카드 순서 (목업에서만 — 적용 때 테마 마크업 순서를 옮긴다)
ORDER_JS = """<script>
(function(){var ids=['us-report-col','kr-report-col','issue-col','hypo-col','radar-col','notable-col'];
var first=document.getElementById(ids[0]);if(!first)return;var box=first.parentNode;
ids.forEach(function(id){var n=document.getElementById(id);if(n&&n.parentNode===box)box.appendChild(n);});
var rest=[].slice.call(box.children).filter(function(n){return ids.indexOf(n.id)<0;});rest.forEach(function(n){box.appendChild(n);});})();
</script>"""


def banners():
    out = {}
    for mkt, e in EDITIONS.items():
        bg = Image.open(os.path.join(B.DEFAULT_DIR, e["bg"])).convert("RGB")
        with redirect_stdout(io.StringIO()):
            im = B.compose(bg, {"mood": e["mood"], "date": "2026-11-17", "slot": e["slot"]}, e["banner"])
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=82)
        im.save(os.path.join(OUT, f"home-commentary-{mkt}.webp"), "WEBP", quality=82)
        out[mkt] = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
    return out


def card_a(e, img):
    return (f"<div class='report-col' id='commentary-col'>\n"
            f"<h3 class='report-title'>{ICON}{e['name']}<span class='report-card-date'>{e['when']}</span></h3>\n"
            f"<a class='report-card cm-card' href='#'><img class='cm-banner' src='{img}' width='900' height='350' alt='{e['name']}. "
            f"{' '.join(e['banner']['titles'][0])}'/><p class='cm-head'>{e['title']}</p></a>\n</div>\n")


def card_b(e, img, cls="cm-boxed"):
    return (f"<section class='{cls}' aria-label='{e['name']}'><a href='#'><img src='{img}' width='900' height='350' "
            f"alt='{e['name']}. {e['title']} (AI 생성 이미지)'/><span class='cm-pill'>{e['name']}</span></a></section>\n")


def build(src, mkt, variant, img):
    e = EDITIONS[mkt]
    files = {"us": f"mock_home_commentary_{variant}_us.html", "kr": f"mock_home_commentary_{variant}_kr.html"}
    html = split_html(src, mkt, files)
    eb_re = r"(<section class=['\"]event-banner['\"].*?</section>)"
    if variant == "a":   # 실적 발표 배너 밑 첫 카드 (증시 카드 앞)
        html, n = re.subn(r"(<div class=['\"]report-col['\"] id=['\"]us-report-col['\"])", lambda m: card_a(e, img) + "\n              " + m.group(1), html, count=1)
    elif variant == "b":   # 실적 발표 배너 밑, 그림만 카드 폭
        html, n = re.subn(eb_re, lambda k: k.group(1) + "\n        " + card_b(e, img), html, count=1, flags=re.S)
    else:   # c 계열 — 시황 배너 맨 위(좌우 꽉) + 실적 발표 한 줄을 그 밑에 붙임 — 둘 다 위 여백을 당겨 사이가 붙는다
        html, n = re.subn(eb_re, lambda k: card_b(e, img, "cm-wide") + "\n        " + k.group(1).replace("class=\"event-banner\"", "class=\"event-banner cm-strip\"").replace("class='event-banner'", "class='event-banner cm-strip'"), html, count=1, flags=re.S)
    html = html.replace("</head>", "<style>.home-cards > .cm-wide, .home-cards > .cm-boxed { grid-column: 1 / -1; }</style></head>", 1)
    if not n:
        sys.exit(f"끼울 자리 못 찾음 ({variant} · {mkt}) — index.html 주석 확인")
    html = html.replace("</head>", CSS + "\n</head>", 1)
    if variant.startswith("c"):   # 4차 — 테마 코드 몇 군데를 목업에서만 바꿔 본다. 적용 때 alphaflow-home.html 에 같은 수정
        html = html.replace("left === 0 ? 'D-DAY' :", "left === 0 ? 'D-Day' :", 1)
        # 홈 날짜 표기 = `11.17 아침` — 카드 머리 · 구획 날짜가 모두 dayKo 하나를 거친다
        old_day = "return p.length === 3 ? Number(p[1]) + '월 ' + Number(p[2]) + '일 ' + (part || '기준') : '';"
        new_day = "return p.length === 3 ? ('0' + Number(p[1])).slice(-2) + '.' + ('0' + Number(p[2])).slice(-2) + ' ' + (part || '기준') : '';"
        if old_day not in html:
            sys.exit("dayKo 를 못 찾음")
        html = html.replace(old_day, new_day, 1)
        html = html.replace("</head>", LONG_CSS + "</head>", 1)
        html = html.replace("</body>", ORDER_JS + "</body>", 1)
        o = OPTS.get(variant)
        if o:   # Hot Issue · 증시 전망 줄 롤링(위아래)은 11-18 좌우 배너로 바뀌어 테마에 들어갔다(alphaflow-home.html) — 여기서는 편 이름 상자만
            html = html.replace("</head>", "<style>" + PILL_CSS[o["pill"]] + "</style></head>", 1)
    html = html.replace("<head>", "<head>\n" + SAMPLE_JS, 1)
    html = re.sub(r"<title>.*?</title>", f"<title>홈 증시시황 {variant.upper()} — {'미국' if mkt == 'us' else '한국'}</title>", html, count=1, flags=re.S)
    with open(os.path.join(OUT, files[mkt]), "w", encoding="utf-8") as f:
        f.write(html)
    return files[mkt]


VARIANTS = [   #: C 로 결정(A · B 지움) → 5차 시안 3(롤링)으로 결정(시안 1 · 2 지움)
    ("c", "C안 (결정)", "맨 위 = 시황 배너(좌우 꽉 · 모서리 직선), `미국 증시시황` 검정 네모 상자는 제목 바로 위, 그 밑에 실적 발표 한 줄. "
          "Hot Issue · 증시 전망 = 한 줄(질문 + 라벨 · 게시일)씩 3.5초마다 아래에서 위로, 제목 줄 오른쪽 펼침 버튼 = 전부 보기. "
          "카드 순서 = 증시 → Hot Issue → 증시 전망 → 주요 인물 발언 → 주목할 종목 → 시장 흐름과 종목 → 시총 TOP 10."),
]


def main():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, os.path.join(ROOT, "build_theme.py"), "--preview"], cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
    with open(os.path.join(ROOT, "preview.html"), encoding="utf-8") as f:
        src = f.read()
    os.makedirs(OUT, exist_ok=True)
    imgs = banners()
    rows = []
    for v, name, why in VARIANTS:
        us, kr = build(src, "us", v, imgs["us"]), build(src, "kr", v, imgs["kr"])
        rows.append(f"<section><h2>{name}</h2><p>{why}</p><div class='pair'>"
                    f"<figure><figcaption>미국 홈 · 아침 편 <a href='{us}'>크게</a></figcaption><iframe src='{us}' loading='lazy'></iframe></figure>"
                    f"<figure><figcaption>한국 홈 · 저녁 편 <a href='{kr}'>크게</a></figcaption><iframe src='{kr}' loading='lazy'></iframe></figure>"
                    "</div></section>")
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>홈 증시시황 카드</title><style>
body{{margin:0;background:#f5f6f8;color:#111;font-family:"Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif}}
main{{max-width:1400px;margin:0 auto;padding:24px 16px 60px}}h1{{font-size:22px;margin:0 0 8px}}
.intro{{font-size:15px;line-height:1.7;color:#333;margin:0 0 20px}}.intro li{{margin:2px 0}}
section{{margin:0 0 36px}}h2{{font-size:19px;margin:0 0 4px}}section>p{{font-size:14px;line-height:1.6;color:#444;margin:0 0 12px;max-width:900px}}
.pair{{display:flex;flex-wrap:wrap;gap:20px}}figure{{margin:0}}figcaption{{font-size:13px;color:#555;margin:0 0 6px}}
iframe{{width:390px;height:1000px;border:1px solid #d6dbe1;border-radius:14px;background:#fff;max-width:calc(100vw - 32px)}}
</style></head><body><main><h1>홈 증시시황 — C안 (결정)</h1>
<ul class="intro">
<li>미국 홈 = 아침 편 <b>미국 증시시황</b>(08:40 발행, 미국 마감 해설) · 한국 홈 = 저녁 편 <b>한국 증시시황</b>(21:00 발행, 한국 마감 해설)</li>
<li>그림 = 글 맨 위 배너(900×350) 그대로 — 새로 그리지 않음. 목업은 기본 배너 사진으로 그림</li>
<li>그 편이 아직 없을 때(발행 전 · 쉬는 날) = 가장 최근 편을 날짜와 함께, 4일 넘게 새 편이 없으면 카드 숨김</li>
</ul>
{''.join(rows)}</main></body></html>"""
    with open(os.path.join(OUT, "mock_home_commentary.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print("만듦: experiments/market-commentary/output/mock_home_commentary.html (+ 미국 · 한국 화면)")


if __name__ == "__main__":
    main()
