"""뉴팩트 개성 있는 아이 찾기 게임 — 평범의 범위 · 기간을 사용자가 조절해 보는 화면 (2026-11-24 사용자).

길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md 0-1-1.
사용자: "중간값이 평범이지, 여기를 대략 80% 잡아 줘." · "기간을 20 · 60 · 120일로 나눈 것처럼 평범의 범위도 조절하게 해 줘. 90% 최고 · 70% 최소."
        "왜 3년으로 했지? 20일 · 60일 · 120일 · 200일 간격이 더 좋은데." — 첫 판은 3년 통째 숫자로 만들어 물을 흐렸다(점검표 4번). **기간 = 최근 20 · 60 · 120 · 200거래일만.**
→ 평범 = 고른 기간 안에서, 중간값을 가운데 둔 가운데 N%(기본 80, 70 ~ 90). 그 바깥(아래쪽 · 위쪽)이 개성 후보.

    python experiments/stock-character/look_band.py     # → output/mock_band.html — 목업 목록 http://localhost:8800/ 의 `개성 있는 아이 찾기 게임`

자료 = data/store/character/bars_us.pkl · earn_days_us.csv. 미국 S&P 500.
칸 넷(기간마다 다시 잼, 모든 아이 같은 잣대): 평소 하루 폭(호수) · 예고 없는 돌 수(실적 · 파도 날이 아닌 ±5%) · 방향 크기(그 기간 등락) · 거래량 튄 날 수(평소의 2배).
실적 반응 칸은 뺐다 — 20 ~ 200일 안에는 실적이 0 ~ 3번뿐이라 잴 수 없다.
"""

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
STORE = os.path.join(ROOT, "data", "store", "character")
OUT = os.path.join(HERE, "output", "mock_band.html")   # 목업 목록(http://localhost:8800/)에 뜨게 mock_ 이름
sys.path.insert(0, HERE)
import look_stones as LS  # noqa: E402
WINS = [20, 60, 120, 200]
ROSTER = {"COIN": "A", "BE": "A", "SMCI": "A", "BRK-B": "A", "KO": "A", "RSG": "A", "PG": "A", "L": "A", "LIN": "A", "WM": "A", "JNJ": "A",
          "TSLA": "B", "GLW": "B", "MSI": "C", "MSFT": "미정", "SCHW": "미정"}

PAGE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>평범의 범위</title><style>
:root{--ink:#1c2330;--mute:#6b7485;--line:#e3e6ec;--band:#eef4ff;--lo:#2f6fdb;--hi:#d0342c;--bg:#fff}
body{margin:0;background:#f6f7f9;color:var(--ink);font:15px/1.6 "Malgun Gothic","Apple SD Gothic Neo",sans-serif}
main{max-width:1060px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:20px;margin:0 0 4px}.sub{color:var(--mute);font-size:13px;margin-bottom:14px}
.bar{position:sticky;top:0;background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:14px;z-index:5}
.bar b{font-size:22px}.bar input{width:100%;margin:6px 0 2px}.ticks{display:flex;justify-content:space-between;color:var(--mute);font-size:12px}
.sum{margin-top:8px;font-size:14px}
.per{margin-bottom:8px;font-size:14px}.per button{font:inherit;margin-left:6px;padding:4px 12px;border:1px solid var(--line);border-radius:16px;background:#fff;cursor:pointer}.per button.on{background:#1c2330;color:#fff;border-color:#1c2330}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:12px}
.card h2{font-size:16px;margin:0 0 2px}.card .rng{color:var(--mute);font-size:13px;margin-bottom:6px}
svg{width:100%;height:120px;display:block}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:8px}
@media(max-width:640px){.cols{grid-template-columns:1fr}}
.side h3{font-size:13px;margin:0 0 4px}.lo h3{color:var(--lo)}.hi h3{color:var(--hi)}
.names{font-size:13px;word-break:keep-all}.names span{display:inline-block;margin:0 8px 2px 0}.names i{color:var(--mute);font-style:normal}
details summary{cursor:pointer;color:var(--mute);font-size:12px;margin-top:2px}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:5px 6px;text-align:center}
th:first-child,td:first-child{text-align:left}.dn{color:var(--lo);font-weight:700}.up{color:var(--hi);font-weight:700}.mid{color:#b3bac6}
.tag{display:inline-block;min-width:18px;padding:0 5px;border-radius:9px;background:#1c2330;color:#fff;font-size:11px;text-align:center}
.note{color:var(--mute);font-size:12px;margin-top:6px}
</style></head><body><main>
<h1>평범의 범위 — 어느 기간에서, 가운데 몇 %를 평범으로 볼까</h1>
<div class="sub">뉴팩트 개성 있는 아이 찾기 게임 · 미국 S&amp;P 500 __N__명 · 기준일 __LAST__ · 평범 = 고른 기간 안에서 중간값을 가운데 둔 가운데 N%, 그 바깥이 개성 후보</div>
<div class="bar"><div class="per">기간 <span id="wins"></span></div><div>평범 = 가운데 <b id="bv">80</b>% <span style="color:var(--mute);font-size:13px">(아래쪽 <span id="tv">10</span>% · 위쪽 <span id="tv2">10</span>% 가 바깥)</span></div>
<input id="band" type="range" min="70" max="90" step="1" value="80"><div class="ticks"><span>70% (평범 좁게 · 개성 많이)</span><span>80%</span><span>90% (평범 넓게 · 개성 적게)</span></div>
<div class="sum" id="sum"></div></div>
<div id="cards"></div>
<div class="card"><h2>지금 그룹 명단 아이들 — 칸마다 어디에 있나</h2><div class="rng">↓ = 평범 아래쪽 바깥 · ↑ = 위쪽 바깥 · · = 평범 안. 기간 · 범위를 바꾸면 같이 바뀝니다.</div><div id="roster"></div>
<div class="note">그룹 A · B · C 는 그림으로 확인한 아이만 넣은 첫 판입니다(문서 0-2-1). 이 화면은 고른 기간의 숫자 네 칸만 봅니다. 실적 때의 반응은 20 ~ 200일 안에 실적이 0 ~ 3번뿐이라 여기 없습니다.</div></div>
</main><script>
const D=__DATA__, COLS=__COLS__, WINS=__WINS__;let W=60;
wins.innerHTML=WINS.map(w=>`<button data-w="${w}">최근 ${w}일</button>`).join('');
wins.addEventListener('click',e=>{if(e.target.dataset.w){W=+e.target.dataset.w;draw()}});
const q=(a,p)=>{const i=(a.length-1)*p,f=Math.floor(i);return a[f]+(a[Math.min(f+1,a.length-1)]-a[f])*(i-f)};
const fmt=(v,d)=>v.toFixed(d);
function names(list,c,d){const one=x=>`<span>${x.g?`<span class="tag">${x.g}</span> `:''}${x.k||x.s} <i>${fmt(x.v[c],d)}</i></span>`;
  const head=list.slice(0,5).map(one).join(''),rest=list.slice(5);
  return head+(rest.length?`<details><summary>나머지 ${rest.length}명 펼치기</summary>${rest.map(one).join('')}</details>`:'')||'<i>없음</i>'}
function draw(){const b=+document.getElementById('band').value,t=(100-b)/2;
  bv.textContent=b;tv.textContent=tv2.textContent=(t%1?t.toFixed(1):t);
  const state={};let html='';[...wins.children].forEach(b=>b.classList.toggle('on',+b.dataset.w===W));D.forEach(x=>{x.v=x.w[W]});
  for(const [c,label,d,unit,why] of COLS){const vals=D.map(x=>x.v[c]).sort((x,y)=>x-y);
    const lo=q(vals,t/100),hi=q(vals,1-t/100),md=q(vals,.5);
    const isLo=x=>x.v[c]<lo,isHi=x=>x.v[c]>hi;   // 선과 같은 값은 평범 안(0개가 절반인 칸에서 절반이 바깥으로 나가지 않게)
    const L=D.filter(isLo).sort((x,y)=>x.v[c]-y.v[c]),H=D.filter(isHi).sort((x,y)=>y.v[c]-x.v[c]);
    D.forEach(x=>{(state[x.s]=state[x.s]||{})[c]=isLo(x)?-1:isHi(x)?1:0});
    const n=vals.length,W=1000,Hh=120,max=q(vals,.995),min=vals[0],X=i=>i/(n-1)*W,Y=v=>Hh-6-(Math.min(v,max)-min)/(max-min||1)*(Hh-16);
    const pts=vals.map((v,i)=>`${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ');
    const x0=X(L.length-0.5),x1=X(n-H.length-0.5);
    const marks=D.filter(x=>x.g).map(x=>{const i=vals.indexOf(x.v[c]);return `<circle cx="${X(i)}" cy="${Y(x.v[c])}" r="4" fill="${state[x.s][c]<0?'#2f6fdb':state[x.s][c]>0?'#d0342c':'#6b7485'}"><title>${x.k||x.s} ${fmt(x.v[c],d)}</title></circle>`}).join('');
    html+=`<div class="card"><h2>${label}</h2><div class="rng">중간값 ${fmt(md,d)}${unit} · <b>평범 = ${fmt(lo,d)} ~ ${fmt(hi,d)}${unit}</b> · 아래쪽 ${L.length}명 · 평범 ${n-L.length-H.length}명 · 위쪽 ${H.length}명 — ${why}</div>
    <svg viewBox="0 0 ${W} ${Hh}" preserveAspectRatio="none"><rect x="${x0}" y="0" width="${x1-x0}" height="${Hh}" fill="#eef4ff"/><polyline points="${pts}" fill="none" stroke="#1c2330" stroke-width="1.6" vector-effect="non-scaling-stroke"/>${marks}</svg>
    <div class="note">아이들을 작은 값 → 큰 값 순서로 줄 세운 선. 파란 바탕 = 평범. 점 = 그룹 명단 아이.</div>
    <div class="cols"><div class="side lo"><h3>아래쪽 바깥 ${L.length}명 (작은 순)</h3><div class="names">${names(L,c,d)}</div></div>
    <div class="side hi"><h3>위쪽 바깥 ${H.length}명 (큰 순)</h3><div class="names">${names(H,c,d)}</div></div></div></div>`}
  cards.innerHTML=html;
  const k=D.map(x=>COLS.filter(([c])=>state[x.s][c]).length),cnt=m=>k.filter(v=>m(v)).length;
  sum.innerHTML=`최근 ${W}일 — 네 칸 모두 평범 안 <b>${cnt(v=>v===0)}명</b> · 한 칸에서만 바깥 ${cnt(v=>v===1)}명 · 두 칸 ${cnt(v=>v===2)}명 · 세 칸 넘게 <b>${cnt(v=>v>=3)}명</b>`;
  const sym=v=>v<0?'<span class="dn">↓</span>':v>0?'<span class="up">↑</span>':'<span class="mid">·</span>';
  roster.innerHTML='<table><tr><th>아이</th><th>그룹</th>'+COLS.map(([c,l])=>`<th>${l.split('(')[0]}</th>`).join('')+'</tr>'+
   D.filter(x=>x.g).sort((a,b)=>a.g.localeCompare(b.g)).map(x=>`<tr><td>${x.k||x.s} (${x.s})</td><td>${x.g}</td>`+COLS.map(([c,l,d])=>`<td>${sym(state[x.s][c])} ${fmt(x.v[c],d)}</td>`).join('')+'</tr>').join('')+'</table>'}
band.addEventListener('input',draw);draw();
</script></body></html>"""


def main():
    bars = pd.read_pickle(os.path.join(STORE, "bars_us.pkl"))
    earn = pd.read_csv(os.path.join(STORE, "earn_days_us.csv"), parse_dates=["day"])
    eg = {s: g for s, g in earn.groupby("sym")}
    ref = json.load(open(os.path.join(ROOT, "experiments", "ref", "quick_ref.json"), encoding="utf-8"))["us"]
    C = pd.DataFrame({s: d["close"] for s, d in bars.items() if not s.startswith("^")})
    hit = C.pct_change().abs() * 100 >= LS.STONE
    share = hit.sum(axis=1) / C.notna().sum(axis=1)
    waves = set(share[share >= LS.WAVE_SHARE].index)
    last = C.index.max()
    rows = []
    for s, d in bars.items():
        if s.startswith("^") or s not in eg:
            continue
        d = d[(d["open"] > 0) & (d["volume"] > 0)]
        if len(d) < 520 or d.index.max() != last:
            continue
        c, idx = d["close"], d.index
        ret = (c.pct_change() * 100).values
        rng = ((d["high"] - d["low"]) / c * 100).values
        volx = (d["volume"] / d["volume"].rolling(250, min_periods=60).median()).values
        sched = LS.sched_days(idx, eg[s])
        n = len(idx)
        w = {}
        for W in WINS:
            a = n - W
            un = sum(1 for i in range(a, n) if abs(ret[i]) >= LS.STONE and i not in sched and idx[i] not in waves)
            w[W] = [round(float(np.median(rng[a:])), 2), un, round(abs(float(c.iloc[-1] / c.iloc[a - 1] - 1)) * 100, 1),
                    int(np.nansum(volx[a:] >= LS.VOL2))]
        rows.append({"s": s, "k": (ref.get(s.replace("-", ".")) or ref.get(s) or {}).get("ko"), "g": ROSTER.get(s), "w": w})
    cols = [[0, "평소 하루 폭 (호수)", 1, "%", "그 기간에 하루 동안 얼마나 오르내렸나(가운데 값)"],
            [1, "예고 없는 돌 수", 0, "개", "실적 · 파도 날이 아닌 날에 ±5% 넘게 움직인 횟수"],
            [2, "방향 크기", 0, "%", "그 기간 처음과 끝의 등락 크기(오름 · 내림 구분 없이)"],
            [3, "거래량 튄 날 수", 0, "일", "거래량이 평소(지난 250일 가운데 값)의 2배를 넘은 날"]]
    html = (PAGE.replace("__DATA__", json.dumps(rows, ensure_ascii=False)).replace("__COLS__", json.dumps(cols, ensure_ascii=False))
            .replace("__N__", str(len(rows))).replace("__LAST__", str(last.date())).replace("__WINS__", json.dumps(WINS)))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(html)
    print(f"화면 → {OUT} · 아이 {len(rows)}명 · 기준일 {last.date()}")
    for W in WINS:   # 터미널용: 기간마다 가운데 80% 의 범위
        line = []
        for i, lb, dg, u, _ in cols:
            v = pd.Series([r["w"][W][i] for r in rows])
            line.append(f"{lb.split(' (')[0]} {v.quantile(.1):.{dg}f} ~ {v.quantile(.9):.{dg}f}{u}(가운데 {v.median():.{dg}f})")
        print(f"최근 {W}일 · 가운데 80%: " + " · ".join(line))


if __name__ == "__main__":
    main()
