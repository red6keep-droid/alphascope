"""홈 Hot Issue · 증시 전망 카드 = 좌우로 넘어가는 배너.

** 적용 끝 (11-18) — 테마(alphaflow-home.html · index.html)에 들어가 이 스크립트는 더 돌리지 않는다(고리 코드가 바뀌어 돌면 멈춤). 홈 모습 = mock_home_commentary.py C안 · home-split. 시안 기록용. **

    python experiments/market-commentary/mock_home_issue_banner.py   # → output/mock_home_issue_banner.html (비교) + 시안별 미국 홈

바탕 = 홈 증시시황 C안(mock_home_commentary.build) 그대로, 미국 증시 카드 여백 · Hot Issue · 증시 전망 카드만 바꾼다.
한 건 = 한 장. 4초마다 왼쪽으로 넘어가고(마지막 → 첫 장도 왼쪽으로 이어짐), 손가락으로 밀면 넘어가며 누르는 동안은 멈춘다.
자료 = issues.json · hypo.json 칸 그대로 — 새 수집 · AI 0.

결정 이력
  Hot Issue = 흰색 + 빨강 상자(옅은 톤 · 진한 색 면 · 사진 시안 모두 버림). 카드 틀 · 여백 = 다른 홈 카드와 같음.
  6차: 미국 증시 카드 — 제목 ↔ 그래프 −5 · 그래프 ↔ 요약 −5 · 요약 아래 −5.
       머리 줄 = 라벨 상자 + 점(바로 옆) … 날짜(공통 날짜 자리, 오른쪽). 라벨 ↔ 질문 6 → 16(+10).
       증시 전망도 같은 배너 — 라벨 · 점 · 날짜 · 넘김 같음, 펼침 삼각 화살표 · 태그(종목 · 조정) · 게시일 삭제.
       글자 = 강조(이슈 이름 · 전망 대상)만 굵게, 나머지 보통 — 전부 검정.
       증시 전망 오른쪽 그림 = 시안 4개(갈림길 · 저울 · 두 갈래 화살표 · 사건 날짜 패).
  7차: 증시 전망 그림 = 시소(가로 막대 기울기 = 그날 전망 방향, 계기판처럼 단순하게), 시안 5개 · 나머지 그림 삭제. 계기판 바늘 3 짧게(반원과 여백).
  8차: 시소 5(연한 막대 + 끝 점) 기준 — 가운데 점 대신 계기판 바늘 같은 핀 위에 막대. 핀 바닥 · 접합 · 끝 점 경우의 수로 시안 6개, 다른 시소 삭제.
  9차: 완전 다른 컨셉 — 그래프 아이콘(상승 · 하락 · 횡보), 시안 6개 · 더미 세 장 롤링. 핀 시소는 보관(p5 진한 막대만 삭제).
  10차: 그래프 2(연한 선 + 끝 점)만 남김 — 가로 62(−20%) · 지그재그 두 높이 · 끝 = 안쪽 점(지름 8) / 없음 / 선과 한 몸 화살표, 시안 6개.
  11차: 확정 = 가파름 1 · 안쪽 점, 횡보만 가로 68(+10%). 나머지 삭제.
블로그 · gh-pages 쓰기 0, AI 0. 목업 전용 — 고르면 alphaflow-home.html renderIssues · renderHypo 를 바꾼다.
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "output")
sys.path.insert(0, HERE)
import mock_home_commentary as MC  # noqa: E402

VARIANTS = {   # 11차: 가파름 1 · 안쪽 점. 횡보(회색)만 가로 +10% (62 → 68). 나머지 시안 삭제
    "h1": ("확정 · 가파름 1 · 안쪽 점", "연한 선(굵기 8) + 끝 안쪽 점(지름 8, 계기판 반원 위 점과 같음). 상승 · 하락 가로 62 · 횡보 71."),
}

CSS = """<style>
/* ===== 미국 증시 카드 여백 — 제목 ↔ 그래프 16 → 11 · 그래프 ↔ 요약 18 → 13 · 요약 아래 33 → 28 ===== */
#report-card { padding-top: 11px; padding-bottom: 11px; gap: 13px; }

/* ===== 배너 카드 (Hot Issue · 증시 전망) — 카드 틀 = 홈 카드 기본(.home-cards .report-col) 그대로 =====
   안쪽 = 좌우 16 더(글자 왼쪽 = 카드 끝에서 26) · 위아래 14(카드 끝에서 30, 다른 카드 제목 줄 위 · 마지막 줄 아래와 같음).
   머리 줄 = 라벨 상자 + 점 … 날짜(.report-card-date 공통 자리) · 라벨 ↔ 질문 16. 넘어가는 것 = 질문 + 오른쪽 그림 한 장씩.
   높이 152 = 1 + 16 + 14 + 머리 20 + 16 + 질문 두 줄 56 + 14 + 16 + 1 */
.ib { position: relative; margin: 0 16px; padding: 14px 0; touch-action: pan-y; -webkit-user-select: none; user-select: none; }
.ib-head { display: flex; align-items: center; gap: 8px; height: 20px; margin-bottom: 16px; }
.ib-head .report-card-date { margin-left: auto; }
.ib-box { flex: none; padding: 0 8px; border-radius: 6px; color: #fff; font-size: 11px; line-height: 18px; font-weight: 700; }
.ib-view { overflow: hidden; }
.ib-track { display: flex; transition: transform .45s ease; will-change: transform; }
.ib-slide { flex: 0 0 100%; min-width: 0; position: relative; display: block; height: 56px; padding-right: 112px; box-sizing: border-box;
  color: #111; text-decoration: none; -webkit-tap-highlight-color: transparent; }
.ib-slide:active { opacity: .7; }
.ib-q { margin: 0; font-family: var(--report-font); font-size: 20px; line-height: 28px; color: #111; word-break: keep-all; overflow-wrap: anywhere;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.ib-em { font-weight: 700; }
.ib-rest { font-weight: 400; }
.ib-art { position: absolute; right: 0; top: 0; width: 100px; height: 56px; }
.ib-slide.negative .ib-art { color: #1D4ED8; } .ib-slide.positive .ib-art { color: #B91C1C; } .ib-slide.neutral .ib-art { color: #475569; }   /* 바늘 = 방향 색 */
.ib-dots { display: flex; gap: 5px; color: #475569; pointer-events: none; }
.ib-dots i { display: block; width: 6px; height: 6px; border-radius: 3px; background: currentColor; opacity: .3; transition: width .3s, opacity .3s; }
.ib-dots i.on { width: 16px; opacity: 1; }
@media (prefers-reduced-motion: reduce) { .ib-track { transition: none; } }
</style>"""

BASE_JS = r"""
function e(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
/* 강조 나누기 — lead(전망 대상 · 사건 이름)로 시작하면 그 부분, 아니면 쉼표 앞. 강조 = 굵게, 나머지 = 보통 (둘 다 검정) */
function ibSplit(t,lead){t=String(t||'');var n=0;if(lead&&t.indexOf(lead)===0)n=lead.length;else{var i=t.indexOf(',');if(i>0)n=i+1;}
 if(!n)return '<span class="ib-rest">'+e(t)+'</span>';return '<span class="ib-em">'+e(t.slice(0,n))+'</span> <span class="ib-rest">'+e(t.slice(n).trim())+'</span>';}
/* Hot Issue 반원 바늘 — 이슈 페이지 게이지를 줄인 그림. 왼쪽 나쁜 쪽 · 오른쪽 좋은 쪽, 뚜렷이면 끝까지 */
function ibNet(q){var k=q.kind||'neutral',g=q.gauge||'';var s=/뚜렷/.test(g)?0.8:0.45;return k==='negative'?-s:(k==='positive'?s:0);}
function ibGauge(q){var a=Math.PI*(1-(ibNet(q)+1)/2),x=50+29.8*Math.cos(a),y=50-29.8*Math.sin(a);   /* 바늘 길이 29.8 — 반원 안쪽 끝(36)과 여백 3 더 */
 return '<svg class="ib-art" viewBox="0 0 100 56" aria-hidden="true"><path d="M10 50a40 40 0 0 1 80 0" fill="none" stroke="currentColor" stroke-opacity=".3" stroke-width="8" stroke-linecap="round"/>'+
 '<path d="M10 50a40 40 0 0 1 80 0" fill="none" stroke="currentColor" stroke-width="8" stroke-linecap="round" stroke-dasharray="1 200" stroke-dashoffset="'+(-((ibNet(q)+1)/2*125.7))+'"/>'+
 '<line x1="50" y1="50" x2="'+x.toFixed(1)+'" y2="'+y.toFixed(1)+'" stroke="currentColor" stroke-width="3" stroke-linecap="round"/><circle cx="50" cy="50" r="5" fill="currentColor"/></svg>';}
/* 롤링 배너 — col 의 기존 제목 줄 · 카드는 숨기고 그 자리에 배너. 날짜 = 홈 공통 날짜(genKo) */
function ibMount(colId,cardId,label,color,date,slides){
 var col=document.getElementById(colId);if(!col||!slides.length)return;
 var host=col.querySelector('.ib-host');if(!host){host=document.createElement('div');host.className='ib-host';
  col.querySelector('.report-title').style.display='none';document.getElementById(cardId).style.display='none';col.appendChild(host);}
 var n=slides.length,dots=n>1?'<div class="ib-dots" aria-hidden="true">'+slides.map(function(_,i){return '<i'+(i?'':' class="on"')+'></i>';}).join('')+'</div>':'';
 host.innerHTML='<div class="ib" role="region" aria-roledescription="carousel" aria-label="'+e(label)+'"><div class="ib-head"><span class="ib-box" style="background:'+color+'">'+e(label)+'</span>'+dots+
  '<span class="report-card-date">'+e(date||'')+'</span></div><div class="ib-view"><div class="ib-track">'+slides.concat(n>1?[slides[0]]:[]).join('')+'</div></div></div>';   /* 끝에 첫 장 복사 — 마지막 → 첫 장도 왼쪽으로 */
 var box=host.querySelector('.ib'),tr=host.querySelector('.ib-track'),ds=[].slice.call(host.querySelectorAll('.ib-dots i')),cur=0,timer=null,MS=4000;
 var still=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
 function go(i,anim){tr.style.transition=anim===false?'none':'';cur=i;tr.style.transform='translateX('+(-100*i)+'%)';ds.forEach(function(d,k){d.classList.toggle('on',k===i%n);});}
 tr.addEventListener('transitionend',function(){if(cur===n){go(0,false);void tr.offsetHeight;tr.style.transition='';}});
 function play(){stop();if(n>1&&!still)timer=setInterval(function(){go(cur+1);},MS);}
 function stop(){if(timer){clearInterval(timer);timer=null;}}
 /* 손가락으로 밀기 — 가로로 40px 넘게 밀면 넘김, 누르는 동안 멈춤. 민 뒤에는 링크로 가지 않음 */
 var x0=null,y0=0,dx=0,moved=false;
 box.addEventListener('pointerdown',function(ev){x0=ev.clientX;y0=ev.clientY;dx=0;moved=false;stop();tr.style.transition='none';});
 box.addEventListener('pointermove',function(ev){if(x0===null)return;dx=ev.clientX-x0;if(Math.abs(dx)>6&&Math.abs(dx)>Math.abs(ev.clientY-y0))moved=true;
  if(moved)tr.style.transform='translateX(calc('+(-100*cur)+'% + '+dx+'px))';});
 function end(){if(x0===null)return;x0=null;tr.style.transition='';
  if(moved&&dx<-40&&n>1)go(cur+1);else if(moved&&dx>40&&n>1){if(cur===0){go(n,false);void tr.offsetHeight;tr.style.transition='';go(n-1);}else go(cur-1);}else go(cur);play();}
 box.addEventListener('pointerup',end);box.addEventListener('pointercancel',end);box.addEventListener('pointerleave',end);
 box.addEventListener('click',function(ev){if(moved){ev.preventDefault();ev.stopPropagation();}},true);
 n>1&&play();
}
window.IB_ISSUES=function(j,date){var rows=(j&&j.issues)||[];
 ibMount('issue-col','issue-card','Hot Issue','#E53E3E',date,rows.map(function(q){
  return '<a class="ib-slide '+e(q.kind||'neutral')+'" href="'+e(q.url||'#')+'"><p class="ib-q">'+ibSplit(q.q||q.name,'')+'</p>'+ibGauge(q)+'</a>';}));};
/* 증시 전망 — event `11.12 브로드컴 급등` → 날짜 · 대상(브로드컴) · 사건 말(급등). 강조 = 제목이 `대상 실적` 으로 시작하면 그 부분, 아니면 쉼표 앞 */
function fcEv(q){var m=String(q.event||'').match(/^(\d+\.\d+)\s+(.*?)\s*(급등|급락|실적)?$/)||[];return {day:m[1]||'',who:m[2]||'',word:m[3]||''};}
window.IB_HYPO=function(rows,date){if(window.IB_DUMMY)rows=IB_DUMMY;   /* 목업: 더미 세 장 */
 ibMount('hypo-col','hypo-card','증시 전망','#7C3AED',date,rows.map(function(q){var ev=fcEv(q),lead=ev.word==='실적'?(ev.who+' 실적'):'',ln=q.lean!=null?q.lean:(LEAN_SAMPLE[q.eh]||0);
  return '<a class="ib-slide" href="'+e(q.url||'#')+'"><p class="ib-q">'+ibSplit(q.title,lead)+'</p>'+ART[String(ln)]+'</a>';}));};
"""

LEAN_INK = {1: "#B91C1C", -1: "#1D4ED8", 0: "#475569"}   # 계기판 바늘과 같은 색 — 상승 쪽 빨강 · 하락 쪽 파랑 · 지켜보는 중 회색
TILT = 14   # 기운 각도(도) — 조짐이 보이는 날. 수평 = 지켜보는 중


def seesaw(v, lean):
    """핀 시소 아이콘 (100 × 56) — 계기판과 같은 짜임: 연한 막대(= 연한 반원) + 진한 핀(= 바늘) + 둥근 점(= 가운데 점).
    lean = 오늘 전망 기울기(+1 상승 쪽 · −1 하락 쪽 · 0 지켜보는 중). 오른쪽 끝이 올라가면 상승 · 내려가면 하락."""
    import math
    c = LEAN_INK[lean]
    cy, half = 20, 38   # 막대 축 = 핀 꼭대기 (50, 20) · 핀 바닥 = (50, 50) — 계기판 가운데 점과 같은 높이
    rot = f' transform="rotate({-TILT * lean} 50 {cy})"' if lean else ""
    dx, dy = half * math.cos(math.radians(TILT * abs(lean))), half * math.sin(math.radians(TILT)) * lean
    up, dn = (50 + dx, cy - dy), (50 - dx, cy + dy)   # 오른쪽 끝 · 왼쪽 끝 (lean 0 이면 수평)
    if lean < 0:
        up, dn = dn, up   # 올라간 끝 = 왼쪽
    solid = v == "p5"
    bar = f'<line x1="{50 - half}" y1="{cy}" x2="{50 + half}" y2="{cy}" stroke="{c}"{"" if solid else " stroke-opacity=\".3\""} stroke-width="8" stroke-linecap="round"{rot}/>'
    pin = f'<line x1="50" y1="{cy}" x2="50" y2="50" stroke="{c}" stroke-width="3" stroke-linecap="round"/>'
    foot = (f'<line x1="42" y1="50" x2="58" y2="50" stroke="{c}" stroke-width="3" stroke-linecap="round"/>' if v == "p2"
            else f'<circle cx="50" cy="50" r="5" fill="{c}"/>')
    joint = ""
    if v == "p2":
        joint = f'<circle cx="50" cy="{cy}" r="3" fill="{c}"/>'
    elif v == "p3":
        joint = f'<circle cx="50" cy="{cy}" r="5" fill="#fff" stroke="{c}" stroke-width="3"/>'
    elif v == "p4":
        pin = f'<line x1="50" y1="{cy - 7}" x2="50" y2="50" stroke="{c}" stroke-width="3" stroke-linecap="round"/>'
        joint = f'<circle cx="50" cy="{cy - 8}" r="3" fill="{c}"/>'
    ends = ""
    if lean and v != "p5":
        ends = f'<circle cx="{up[0]:.1f}" cy="{up[1]:.1f}" r="6" fill="{c}"/>'
        if v == "p6":
            ends += f'<circle cx="{dn[0]:.1f}" cy="{dn[1]:.1f}" r="6" fill="{c}" fill-opacity=".45"/>'
    body = (bar + pin if v == "p4" else pin + bar) + foot + joint + ends   # 못 머리(p4)는 핀이 막대 위로 보이게 나중에
    return f'<svg class="ib-art" viewBox="0 0 100 56" aria-hidden="true">{body}</svg>'


LINES = {   # 꺾은선 점 (100 × 56) — 가로 19 ~ 81(62, 옛 78의 80%) · 가파름 1 / 2
    1: {1: [(19, 44), (38, 24), (54, 34), (81, 10)], 2: [(19, 48), (38, 18), (54, 32), (81, 6)]},
    -1: {1: [(19, 10), (38, 30), (54, 20), (81, 44)], 2: [(19, 6), (38, 36), (54, 22), (81, 48)]},
    0: {1: [(15, 30), (36, 20), (54, 36), (86, 26)],   # 횡보 = 가로 71 (68 × 1.05, 12차)
        2: [(19, 32), (38, 14), (54, 42), (81, 26)]},
}


def chart_icon(v, lean):
    """그래프 아이콘 (100 × 56) — lean +1 상승(빨강) · −1 하락(파랑) · 0 횡보(회색). 선 = 연하게(.3) 굵기 8.
    끝: 안쪽 점(지름 8 = 선 굵기, 계기판 반원 위 점과 같음) · 없음 · 화살표(선과 같은 연한 색 한 몸 — 묶음에 투명도를 줘 겹친 곳이 진해지지 않게)."""
    import math
    c = LEAN_INK[lean]
    steep = 2 if v in ("h2", "h4", "h6") else 1
    pts = LINES[lean][steep]
    ex, ey = pts[-1]
    if v in ("h5", "h6"):
        px, py = pts[-2]
        L = math.hypot(ex - px, ey - py)
        ux, uy = (ex - px) / L, (ey - py) / L
        nx, ny = -uy, ux
        bx, by = ex - 12 * ux, ey - 12 * uy   # 화살촉 밑변 = 끝에서 12 앞 · 폭 18 (선 8보다 넓게)
        pl = " ".join(f"{x},{y}" for x, y in pts[:-1]) + f" {bx:.1f},{by:.1f}"
        head = (f'<path d="M{ex + 2 * ux:.1f} {ey + 2 * uy:.1f} L{bx + 9 * nx:.1f} {by + 9 * ny:.1f} L{bx - 9 * nx:.1f} {by - 9 * ny:.1f}Z" '
                f'fill="{c}" stroke="{c}" stroke-width="2" stroke-linejoin="round"/>')
        body = (f'<g opacity=".3"><polyline points="{pl}" fill="none" stroke="{c}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>{head}</g>')
    else:
        pl = " ".join(f"{x},{y}" for x, y in pts)
        body = f'<polyline points="{pl}" fill="none" stroke="{c}" stroke-opacity=".3" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>'
        if v in ("h1", "h2"):
            body += f'<circle cx="{ex}" cy="{ey}" r="4" fill="{c}"/>'
    return f'<svg class="ib-art" viewBox="0 0 100 56" aria-hidden="true">{body}</svg>'


# 목업 더미 — 증시 전망 세 장이 상승 · 하락 · 횡보 그림을 차례로 보이게. 제목 = hypo.json 실제 제목, 기울기만 더미.
DUMMY = [{"title": "엔비디아 실적 뒤 반도체는?", "event": "11.17 엔비디아 실적", "lean": 1, "url": "#"},
         {"title": "브로드컴 급등, 조정 올까 더 오를까?", "event": "11.12 브로드컴 급등", "lean": -1, "url": "#"},
         {"title": "기아 급락, 반등할까 더 빠질까?", "event": "11.10 기아 급락", "lean": 0, "url": "#"}]


# 목업 샘플 기울기 — hypo.json 에는 아직 칸이 없다. 적용 때 forecast_daily 가 그날 타임라인 마지막 국면 방향(log 의 dir)을 lean 으로 적는다(수집 · AI 0).
# 실제 11-18 값: EH-2026-005 기아 = 하락 지속 조짐(−1), 나머지 = 지켜보는 중(0). 브로드컴(007)만 상승 쪽 보기로 +1 샘플
LEAN_SAMPLE = {"EH-2026-002": 0, "EH-2026-007": 1, "EH-2026-005": -1, "EH-2026-008": 0}

def build(src, v, img):
    tmp = tempfile.mkdtemp()
    MC.OUT = tmp   # C안 원본 출력 파일을 덮어쓰지 않게 임시 폴더로
    fn = MC.build(src, "us", "c", img)
    with open(os.path.join(tmp, fn), encoding="utf-8") as f:
        html = f.read()
    hooks = [("if (j.generated) setDate('issue-card', genKo(j.generated));", " if (window.IB_ISSUES) window.IB_ISSUES(j, genKo(j.generated));"),   # renderIssues 끝
             ("if (j.generated) setDate('hypo-card', genKo(j.generated));", " if (window.IB_HYPO && rows.length) window.IB_HYPO(rows, genKo(j.generated));")]   # renderHypo 끝 (그 나라 전망만 거른 rows)
    for anchor, add in hooks:
        if anchor not in html:
            sys.exit(f"고리를 못 찾음: {anchor}")
        html = html.replace(anchor, anchor + add, 1)
    import json
    art = ("var ART=" + json.dumps({str(k): chart_icon(v, k) for k in (1, 0, -1)}) + ";var LEAN_SAMPLE=" + json.dumps(LEAN_SAMPLE)
           + ";var IB_DUMMY=" + json.dumps(DUMMY, ensure_ascii=False) + ";")
    html = html.replace("</head>", CSS + "<script>" + BASE_JS + art + "</script></head>", 1)
    html = re.sub(r"<title>.*?</title>", f"<title>홈 배너 카드 {VARIANTS[v][0]}</title>", html, count=1, flags=re.S)
    name = f"mock_home_issue_banner_{v}.html"
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(html)
    return name


def main():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, os.path.join(ROOT, "build_theme.py"), "--preview"], cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
    with open(os.path.join(ROOT, "preview.html"), encoding="utf-8") as f:
        src = f.read()
    os.makedirs(OUT, exist_ok=True)
    keep = MC.OUT
    MC.OUT = tempfile.mkdtemp()
    img = MC.banners()["us"]
    MC.OUT = keep
    for old in ("w", "fa", "fb", "fc", "fd", "s1", "s2", "s3", "s4", "s5", "p5", "g1", "g2", "g3", "g4", "g5", "g6", "h2", "h3", "h4", "h5", "h6"):   # 지난 시안 파일 (핀 시소 p1~p4 · p6 = mock_home_pin_seesaw_*.html 로 보관, 목업 목록 /archive)
        p = os.path.join(OUT, f"mock_home_issue_banner_{old}.html")
        if os.path.exists(p):
            os.remove(p)
    rows = []
    for v, (name, why) in VARIANTS.items():
        fn = build(src, v, img)
        icons = "".join(f"<span class='ic'>{chart_icon(v, k).replace('class=\"ib-art\"', 'width=\"100\" height=\"56\"')}<i>{t}</i></span>"
                        for k, t in ((1, "상승"), (-1, "하락"), (0, "횡보")))
        rows.append(f"<figure><figcaption><b>{name}</b> <a href='{fn}'>크게</a><span>{why}</span><div class='icons'>{icons}</div></figcaption><iframe src='{fn}' loading='lazy'></iframe></figure>")
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>홈 배너 카드 시안</title><style>
body{{margin:0;background:#f5f6f8;color:#111;font-family:"Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif}}
main{{max-width:1720px;margin:0 auto;padding:24px 16px 60px}}h1{{font-size:22px;margin:0 0 8px}}
.intro{{font-size:15px;line-height:1.7;color:#333;margin:0 0 20px}}
.grid{{display:flex;flex-wrap:wrap;gap:20px}}figure{{margin:0;width:390px;max-width:calc(100vw - 32px)}}
figcaption{{font-size:13px;line-height:1.55;color:#444;margin:0 0 8px;min-height:150px}}.icons{{display:flex;gap:12px;margin-top:8px;padding:10px;background:#fff;border-radius:10px}}.ic{{display:flex;flex-direction:column;align-items:center;gap:4px}}.ic i{{font-style:normal;font-size:12px;color:#7A7A7A}}figcaption b{{font-size:16px;color:#111}}figcaption span{{display:block;margin-top:4px}}
iframe{{width:100%;height:1100px;border:1px solid #d6dbe1;border-radius:14px;background:#fff}}
</style></head><body><main><h1>홈 Hot Issue · 증시 전망 — 배너 카드 (증시 전망 그래프 아이콘 확정)</h1>
<ul class="intro">
<li>미국 증시 카드 = 제목 ↔ 그래프 · 그래프 ↔ 요약 · 요약 아래 각 5 줄임</li>
<li>Hot Issue · 증시 전망 = 같은 배너: 라벨 상자 + 점(바로 옆) … 오른쪽 날짜(다른 카드 날짜 자리), 라벨 ↔ 질문 +10. 한 건 = 한 장, 4초마다 왼쪽으로 · 손가락으로 밀어도 넘어감</li>
<li>글자 = 강조만 굵게(이슈 이름 · 전망 대상), 나머지 보통 — 전부 검정. 증시 전망 태그(종목 · 조정) · 게시일 · 펼침 화살표 삭제</li>
<li>그래프 아이콘 = 그날 전망이 기우는 쪽: 상승(빨강) · 하락(파랑) · 횡보 = 어느 쪽도 아님(회색). 색 · 굵기 8 = 계기판과 같음</li>\n<li>Hot Issue 계기판 = 바늘을 3 줄여 반원과 여백(모든 시안 같음). 증시 전망은 더미 세 장(상승 · 하락 · 횡보)이 4초마다 넘어감. 핀 시소 시안은 목업 목록 /archive 에 보관</li>
</ul>
<div class="grid">{''.join(rows)}</div></main></body></html>"""
    with open(os.path.join(OUT, "mock_home_issue_banner.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print("만듦: experiments/market-commentary/output/mock_home_issue_banner.html (+ 확정안)")


if __name__ == "__main__":
    main()
