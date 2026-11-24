"""뉴팩트 개성 있는 아이 찾기 게임 — 그래프 시안(B) 화면 틀을 원본 틀에서 만들어 낸다 (2026-11-24 사용자 "원본 페이지는 놔두고 추천하는 페이지를 시안용으로 다시 만들어").

원본 = look_band_page.html (그대로 둔다) → 시안 = look_band_page_b.html. look_band.py 가 두 틀로 output/mock_band.html · mock_band_b.html 을 같이 만든다.
시안에서 바뀌는 것은 종목 설명(접기 안)뿐: 글머리표 문장 대신
  ① 한 문장  ② 칸마다 범위 막대(회색 = 대부분의 종목 범위 · 주황 점 = 이 종목)  ③ 구간마다 시간 그래프(칸 바꿔 보기)
  ④ 실적 반응 범위 막대  ⑤ 발표마다 등락 세로 막대.
계산 · 설정 · 답은 원본과 같다. 원본 틀을 고치면 이 스크립트가 찾는 자리가 달라질 수 있다 — 그때는 assert 가 알려 준다.

    python experiments/stock-character/make_band_b.py     # 틀만 다시 만든다. 화면은 look_band.py
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "look_band_page.html")
DST = os.path.join(HERE, "look_band_page_b.html")

CSS = """
.rr{padding:12px 0 6px;border-top:1px solid var(--line)}.rr:first-of-type{border-top:0}
.rrh{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.rrn{font-size:16px;line-height:24px;font-weight:700;color:var(--ink)}.rrv{font-size:16px;line-height:24px;font-weight:700;color:var(--body);white-space:nowrap}
.rrs{font-size:14px;line-height:20px;color:var(--sub)}
.ds svg{display:block}.ds .ct{padding-left:0;margin-top:20px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 8px}
.chip{font:inherit;font-size:13px;line-height:19px;color:var(--sub);background:#fff;border:1px solid var(--line);border-radius:999px;padding:3px 9px;cursor:pointer}
.chip.on{color:var(--ink);font-weight:700;background:#F1F5F9;border-color:var(--c-cmp)}
.lg2{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:13px;line-height:19px;color:var(--sub);margin:6px 0 0}
.lg2 span{display:inline-flex;align-items:center;gap:5px}.lg2 u{display:inline-block;width:12px;height:8px;text-decoration:none;border-radius:2px}
.hs{overflow-x:auto}.hint{font-size:13px;line-height:19px;color:var(--faint);text-align:right}
.yt{position:relative;height:16px;margin-top:2px;font-size:12px;line-height:16px;color:var(--sub)}.yt span{position:absolute;top:0}
"""

# 그래프 도우미 — 실제 px 로 그린다(SVG 를 축소하지 않는다) · 색은 dk.CHART_*(주인공 주황 #F59E0B · 비교 회색 #CBD5E1 · 증감 #ED8E87 · #82B1F0)
JS = r"""
let LIM=null,USE=[];const CC={};
const cw=()=>Math.max(240,Math.min(626,(($('answer').clientWidth||320)-26)|0));
// 범위 막대 한 줄 — 회색 막대 = 대부분의 종목 범위, 주황 점 = 이 종목. 점이 막대 밖이면 범위 밖
function rangeRow(name,val,lo,hi,unit,dec,right,sub,max0){const W=cw(),H=48,pl=8,pr=8,max=max0||Math.max(hi,val)*1.15||1;
  const X=v=>Math.round(pl+Math.max(0,Math.min(v,max))/max*(W-pl-pr)),cx=X(val),x0=X(lo),x1=Math.max(x0+2,X(hi)),mid=Math.max(44,Math.min(W-44,Math.round((x0+x1)/2)));
  const anc=cx<34?'start':cx>W-34?'end':'middle',tx=anc==='start'?pl:anc==='end'?W-pr:cx;
  return `<div class="rr"><div class="rrh"><span class="rrn">${name}</span><span class="rrv">${right}</span></div>${sub?`<div class="rrs">${sub}</div>`:''}`+
    `<svg width="${W}" height="${H}" role="img" aria-label="${name} 이 종목 ${val.toFixed(dec)}${unit}, 대부분의 종목 ${lo.toFixed(dec)} ~ ${hi.toFixed(dec)}${unit}">`+
    `<line x1="${pl}" y1="26" x2="${W-pr}" y2="26" stroke="#EEF2F7" stroke-width="2"/><rect x="${x0}" y="22" width="${x1-x0}" height="8" rx="4" fill="#CBD5E1"/>`+
    `<circle cx="${cx}" cy="26" r="6" fill="#F59E0B" stroke="#fff" stroke-width="2"/>`+
    `<text x="${tx}" y="13" text-anchor="${anc}" font-size="13" font-weight="700" fill="#D97706">${val.toFixed(dec)}${unit}</text>`+
    `<text x="${mid}" y="45" text-anchor="middle" font-size="12" fill="#6B7280">${lo.toFixed(dec)} ~ ${hi.toFixed(dec)}${unit}</text></svg></div>`}
// 구간마다 시간 그래프 — 회색 띠 = 대부분의 종목 범위, 주황 선 = 이 종목, 점 = 범위 밖이던 구간
function timeChart(x,ci){const c=COLS[ci][0],np=LB.length,W=cw(),H=150,pl=30,pr=8,pt=8,pb=24,ps=[];
  for(let p=0;p<np;p++)if(x.v[p])ps.push(p);if(!ps.length)return '';
  const ymax=Math.max(...ps.map(p=>Math.max(x.v[p][c],LIM[p][ci][2])))*1.08||1,X=p=>Math.round(np>1?pl+p*(W-pl-pr)/(np-1):(pl+W-pr)/2),Y=v=>Math.round(H-pb-Math.max(0,v)/ymax*(H-pt-pb));
  const all=[...Array(np).keys()],band=all.map(p=>`${X(p)},${Y(LIM[p][ci][2])}`).concat(all.slice().reverse().map(p=>`${X(p)},${Y(LIM[p][ci][0])}`)).join(' ');
  const segs=[];let cur=[];for(let p=0;p<np;p++){if(x.v[p])cur.push(`${X(p)},${Y(x.v[p][c])}`);else if(cur.length){segs.push(cur);cur=[]}}if(cur.length)segs.push(cur);
  const dots=ps.filter(p=>x.st[ci][p]).map(p=>`<circle cx="${X(p)}" cy="${Y(x.v[p][c])}" r="3" fill="${x.st[ci][p]>0?'#ED8E87':'#82B1F0'}" stroke="#fff" stroke-width="1"/>`).join('');
  const ys=[];let last='';for(let p=0;p<np;p++){const y=LB[p].slice(0,4);if(y!==last){ys.push([X(p),y]);last=y}}   // 해가 바뀌는 구간에 세로선 + 연도. 다음 연도와 40px 안이면 앞의 것은 글자를 뺀다
  const yr=ys.map(([px,y],k)=>`<line x1="${px}" y1="${pt}" x2="${px}" y2="${H-pb}" stroke="#ECF0F5"/>`+(px<W-30&&(k===ys.length-1||ys[k+1][0]-px>=40)?`<text x="${px+2}" y="${H-7}" font-size="13" fill="#6B7280">${y}</text>`:'')).join('');
  const d=COLS[ci][2];
  return `<svg width="${W}" height="${H}" role="img" aria-label="구간마다 ${CN[ci]}">${yr}<line x1="${pl}" y1="${H-pb}" x2="${W-pr}" y2="${H-pb}" stroke="#CBD5E1"/>`+
    `<text x="${pl-4}" y="${pt+8}" text-anchor="end" font-size="10" fill="#6B7280">${ymax.toFixed(d)}</text><text x="${pl-4}" y="${H-pb}" text-anchor="end" font-size="10" fill="#6B7280">0</text>`+
    `<polygon points="${band}" fill="#E2E8F0"/>`+segs.map(s=>`<polyline points="${s.join(' ')}" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`).join('')+dots+`</svg>`}
function timeBlock(x){const ci=USE.includes(CC[x.s])?CC[x.s]:USE[0];if(ci==null)return '';const u0=COLS[ci][3],unit=u0==='개'?'일':u0;
  return `<span class="ct"><i>※</i> 구간마다 ${CN[ci]} <small>(${unit})</small></span>`+
    (USE.length>1?`<div class="chips">${USE.map(i=>`<button class="chip${i===ci?' on':''}" data-cc="${i}" data-s="${x.s}">${CN[i]}</button>`).join('')}</div>`:'')+timeChart(x,ci)+
    `<div class="lg2"><span><u style="background:#F59E0B"></u>이 종목</span><span><u style="background:#E2E8F0"></u>대부분의 종목 범위</span><span><u style="background:#ED8E87;width:8px;border-radius:50%"></u>범위 위쪽 밖</span><span><u style="background:#82B1F0;width:8px;border-radius:50%"></u>범위 아래쪽 밖</span></div>`}
// 발표마다 첫 거래일 등락 — 세로 막대(오름 #ED8E87 · 내림 #82B1F0), 숫자는 부호 + 증감 색. 넓으면 가로로 넘겨 본다
function earnBars(ev){const slot=38,pl=6,W=Math.max(cw(),pl*2+ev.length*slot),H=170,pt=20,pb=38,mp=Math.max(0,...ev.map(r=>r[1])),mn=Math.max(0,...ev.map(r=>-r[1])),k=(H-pt-pb-32)/((mp+mn)||1),y0=Math.round(pt+16+mp*k);
  let s='',last='';ev.forEach((r,i)=>{const cx=Math.round(pl+slot*i+slot/2),h=Math.max(1,Math.round(Math.abs(r[1])*k)),up=r[1]>=0,[y,m]=r[0].split('-');
    s+=`<rect x="${cx-7}" y="${up?y0-h:y0}" width="14" height="${h}" fill="${up?'#ED8E87':'#82B1F0'}"/>`+
      `<text x="${cx}" y="${up?y0-h-5:y0+h+14}" text-anchor="middle" font-size="13" font-weight="700" fill="${up?'#D93025':'#1A73E8'}">${up?'+':'−'}${Math.abs(r[1]).toFixed(1)}</text>`+
      `<text x="${cx}" y="${H-20}" text-anchor="middle" font-size="13" fill="#6B7280">${+m}월</text>`+(y!==last?`<text x="${cx}" y="${H-5}" text-anchor="middle" font-size="12" fill="#6B7280">${y}</text>`:'');last=y});
  return `${W>cw()?'<div class="hint">‹ 넘겨 보기</div>':''}<div class="hs"><svg width="${W}" height="${H}" role="img" aria-label="발표마다 첫 거래일 등락"><line x1="0" y1="${y0}" x2="${W}" y2="${y0}" stroke="#CBD5E1"/>${s}</svg></div>`}
"""

DESC = r"""  const desc=x=>{const head=`<div class="tips">${tipL('읽는 법',TIP_READ+'\n· 범위 막대 : 회색 막대가 대부분의 종목 범위이고 주황 점이 이 종목입니다. 점이 막대 밖이면 범위 밖입니다')}<i>·</i>${tipL('용어',TIP_TERM)}</div><p>${x.n<np?`이 종목은 자료가 있는 ${x.n}구간(${dur(x.n)})만 봤습니다. `:''}`;
    const lg=(x.runs||[]).filter(r=>r.n>=N),sh=(x.runs||[]).filter(r=>r.n<N),ls=x.runs&&x.runs[x.runs.length-1],whole=x.runs&&x.runs.length===1&&x.k===x.n&&x.n>=N;
    const ps=[];for(let p=0;p<np;p++)if(x.v[p])ps.push(p);
    // ② 칸마다 범위 막대 — 살펴본 구간 전체의 가운데 값끼리 견준다(시기별 차이는 ③ 시간 그래프가 보여 준다)
    const rows=use.map((ci,j)=>{const [c,,d,u0]=COLS[ci],unit=u0==='개'?'일':u0,[u,l]=x.per[j];
      return rangeRow(CN[ci],med(ps.map(p=>x.v[p][c])),med(ps.map(p=>LIM[p][ci][0])),med(ps.map(p=>LIM[p][ci][2])),unit,d,`${x.n}구간 중 ${vio((u+l)+'구간')}`,u&&l?`범위 위쪽 밖 ${u}구간 · 아래쪽 밖 ${l}구간`:u?'범위 위쪽 밖':l?'범위 아래쪽 밖':'범위 밖이던 구간 없음')}).join('');
    const s=x.es;
    const earn=`<span class="ct">실적 발표 뒤 첫 거래일의 반응${tip('실적 발표 뒤 첫 거래일의 반응',TIP_EARN)}</span>`+(!s?`<p class="tn">이 기간에는 견줄 만큼의 실적 발표(3번 이상)가 없습니다.</p>`:
      `<p class="tn" style="margin-top:0">최근 ${Y}년의 실적 발표 ${s.n}번</p>`+
      rangeRow('첫 거래일의 등락 크기',s.react,EB.react[0],EB.react[1],'%',1,'대체로 '+vio(s.react.toFixed(1)+'%'))+
      rangeRow('평소 하루 등락의 몇 배',s.times,EB.times[0],EB.times[1],'배',1,'대체로 '+vio(s.times.toFixed(1)+'배'))+
      rangeRow('그날 5% 넘게 움직인 비율',s.bigS,EB.bigS[0],EB.bigS[1],'%',0,`${s.n}번 중 ${vio(s.big+'번')}`,'',100)+
      (s.stay!=null?rangeRow('움직인 자리에 머문 비율',s.stay,EB.stay[0],EB.stay[1],'%',0,`${s.stN}번 중 ${vio(s.stK+'번')}`,'',100):'')+
      `<span class="ct"><i>※</i> 발표마다 첫 거래일 등락 <small>(%)</small></span>${earnBars(s.ev)}`);
    return head+`${!x.runs||!x.runs.length?'이 종목은 대부분의 종목 범위를 벗어난 구간이 없었습니다.':whole?`이 종목은 <b>살펴본 ${x.n}구간(${dur(x.n)}) 내내</b> 대부분의 종목 범위 밖에 있었습니다.`:lg.length?`이 종목의 개성이 드러난 시기는 ${vio(lg.length+'번')}입니다 (${lg.map(r=>`${spanK(r)}, ${dur(r.n)}`).join(' / ')}).`:'이 종목은 개성이 드러난 시기가 없었습니다.'}`+
      `${sh.length?` 이 밖에 ${N}구간보다 짧게 범위를 벗어났다가 돌아온 때가 ${vio(sh.length+'번')} 있었습니다.`:''} 가장 최근 구간(${lbk(LB[np-1])})에서는 ${!ls||x.tq?'대부분의 종목과 같은 범위 안입니다.':ls.n>=N?'여전히 범위 밖입니다.':`범위 밖입니다 (${ls.n}구간째).`}</p>`+
      `<span class="ct">대부분의 종목과 견준 값</span>${rows}<div data-tc="${x.s}">${timeBlock(x)}</div>`+earn};
"""


def main():
    s = open(SRC, encoding="utf-8").read()

    def rep(a, b):
        nonlocal s
        assert s.count(a) == 1, (s.count(a), a[:70])
        s = s.replace(a, b)

    def cut(start, end, new):
        nonlocal s
        i = s.index(start)
        j = s.index(end, i)
        s = s[:i] + new + s[j:]

    rep("<title>개성 있는 아이 찾기</title>", "<title>개성 있는 아이 찾기 (그래프 시안)</title>")
    rep("<h1>개성 있는 아이 찾기</h1>", "<h1>개성 있는 아이 찾기 (그래프 시안)</h1>")
    rep("</style>", CSS + "</style>")
    rep("function answer(lim){", JS + "function answer(lim){LIM=lim;")
    rep("const use=picked(),np=LB.length,band=+$('band').value;", "const use=picked(),np=LB.length,band=+$('band').value;USE=use;")
    cut("  const desc=x=>{", "  const sub=x=>", DESC)
    # 칸 바꿔 보기 — 그 종목의 시간 그래프만 다시 그린다
    rep("  const c=e.target.closest&&e.target.closest('[data-tab],[data-g],[data-c]');",
        "  const ch=e.target.closest&&e.target.closest('[data-cc]');if(ch){CC[ch.dataset.s]=+ch.dataset.cc;const x=D.find(d=>d.s===ch.dataset.s);ch.closest('[data-tc]').innerHTML=timeBlock(x);return}\n"
        "  const c=e.target.closest&&e.target.closest('[data-tab],[data-g],[data-c]');")
    open(DST, "w", encoding="utf-8").write(s)
    print(f"시안 틀 → {DST}")


if __name__ == "__main__":
    main()
