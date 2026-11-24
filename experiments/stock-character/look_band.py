"""뉴팩트 개성 있는 아이 찾기 게임 — 평범의 범위를 사용자가 조절해 보는 화면 (2026-11-24 사용자).

길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md 0-1-1.
사용자: "중간값이 평범이지, 여기를 대략 80% 잡아 줘." · "기간을 20 · 60 · 120일로 나눈 것처럼 평범의 범위도 조절하게 해 줘. 90% 최고 · 70% 최소. 변화되는 것도 보고 싶다."
→ 평범 = 중간값을 가운데 둔 가운데 N%(기본 80, 70 ~ 90). 그 바깥(아래쪽 · 위쪽)이 개성 후보.

    python experiments/stock-character/look_band.py     # → output/mock_band.html (자료를 안에 담은 한 파일) — 목업 목록 http://localhost:8800/ 의 `개성 있는 아이 찾기 게임`

먼저 돌려 둘 것: look_stones.py(stones_us.csv) · look_earn.py(earn_react_us.csv). 미국 S&P 500 · 최근 3년.
칸 넷: 평소 하루 폭(호수) · 예고 없는 돌 수 · 실적 날 등락 · 실적 때 평소의 몇 배.
"""

import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
STORE = os.path.join(ROOT, "data", "store", "character")
OUT = os.path.join(HERE, "output", "mock_band.html")   # 목업 목록(http://localhost:8800/)에 뜨게 mock_ 이름
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
<h1>평범의 범위 — 가운데 몇 %를 평범으로 볼까</h1>
<div class="sub">뉴팩트 개성 있는 아이 찾기 게임 · 미국 S&amp;P 500 __N__명 · 최근 3년(~ __LAST__) · 평범 = 중간값을 가운데 둔 가운데 N%, 그 바깥이 개성 후보</div>
<div class="bar"><div>평범 = 가운데 <b id="bv">80</b>% <span style="color:var(--mute);font-size:13px">(아래쪽 <span id="tv">10</span>% · 위쪽 <span id="tv2">10</span>% 가 바깥)</span></div>
<input id="band" type="range" min="70" max="90" step="1" value="80"><div class="ticks"><span>70% (평범 좁게 · 개성 많이)</span><span>80%</span><span>90% (평범 넓게 · 개성 적게)</span></div>
<div class="sum" id="sum"></div></div>
<div id="cards"></div>
<div class="card"><h2>지금 그룹 명단 아이들 — 칸마다 어디에 있나</h2><div class="rng">↓ = 평범 아래쪽 바깥 · ↑ = 위쪽 바깥 · · = 평범 안. 범위를 바꾸면 같이 바뀝니다.</div><div id="roster"></div>
<div class="note">그룹 A · B · C 는 그림으로 확인한 아이만 넣은 첫 판입니다(문서 0-2-1). 이 화면은 숫자 네 칸만 봅니다 — 시기에 따라 달라지는 것(테슬라 · 코닝)은 여기 안 보입니다.</div></div>
</main><script>
const D=__DATA__, COLS=__COLS__;
const q=(a,p)=>{const i=(a.length-1)*p,f=Math.floor(i);return a[f]+(a[Math.min(f+1,a.length-1)]-a[f])*(i-f)};
const fmt=(v,d)=>v.toFixed(d);
function names(list,c,d){const one=x=>`<span>${x.g?`<span class="tag">${x.g}</span> `:''}${x.k||x.s} <i>${fmt(x[c],d)}</i></span>`;
  const head=list.slice(0,5).map(one).join(''),rest=list.slice(5);
  return head+(rest.length?`<details><summary>나머지 ${rest.length}명 펼치기</summary>${rest.map(one).join('')}</details>`:'')||'<i>없음</i>'}
function draw(){const b=+document.getElementById('band').value,t=(100-b)/2;
  bv.textContent=b;tv.textContent=tv2.textContent=(t%1?t.toFixed(1):t);
  const state={};let html='';
  for(const [c,label,d,unit,why] of COLS){const vals=D.map(x=>x[c]).filter(v=>v!=null).sort((x,y)=>x-y);
    const lo=q(vals,t/100),hi=q(vals,1-t/100),md=q(vals,.5);
    const zeroLow=(lo===vals[0]);   // 아래쪽 끝에 같은 값(0개)이 몰려 있으면 그 값인 아이를 아래쪽으로
    const isLo=x=>zeroLow?x[c]<=lo:x[c]<lo,isHi=x=>x[c]>hi;
    const L=D.filter(isLo).sort((x,y)=>x[c]-y[c]),H=D.filter(isHi).sort((x,y)=>y[c]-x[c]);
    D.forEach(x=>{(state[x.s]=state[x.s]||{})[c]=isLo(x)?-1:isHi(x)?1:0});
    const n=vals.length,W=1000,Hh=120,max=q(vals,.995),min=vals[0],X=i=>i/(n-1)*W,Y=v=>Hh-6-(Math.min(v,max)-min)/(max-min||1)*(Hh-16);
    const pts=vals.map((v,i)=>`${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ');
    const x0=X(L.length-0.5),x1=X(n-H.length-0.5);
    const marks=D.filter(x=>x.g&&x[c]!=null).map(x=>{const i=vals.indexOf(x[c]);return `<circle cx="${X(i)}" cy="${Y(x[c])}" r="4" fill="${state[x.s][c]<0?'#2f6fdb':state[x.s][c]>0?'#d0342c':'#6b7485'}"><title>${x.k||x.s} ${fmt(x[c],d)}</title></circle>`}).join('');
    html+=`<div class="card"><h2>${label}</h2><div class="rng">중간값 ${fmt(md,d)}${unit} · <b>평범 = ${fmt(lo,d)} ~ ${fmt(hi,d)}${unit}</b> · 아래쪽 ${L.length}명 · 평범 ${n-L.length-H.length}명 · 위쪽 ${H.length}명 — ${why}</div>
    <svg viewBox="0 0 ${W} ${Hh}" preserveAspectRatio="none"><rect x="${x0}" y="0" width="${x1-x0}" height="${Hh}" fill="#eef4ff"/><polyline points="${pts}" fill="none" stroke="#1c2330" stroke-width="1.6" vector-effect="non-scaling-stroke"/>${marks}</svg>
    <div class="note">아이들을 작은 값 → 큰 값 순서로 줄 세운 선. 파란 바탕 = 평범. 점 = 그룹 명단 아이.</div>
    <div class="cols"><div class="side lo"><h3>아래쪽 바깥 ${L.length}명 (작은 순)</h3><div class="names">${names(L,c,d)}</div></div>
    <div class="side hi"><h3>위쪽 바깥 ${H.length}명 (큰 순)</h3><div class="names">${names(H,c,d)}</div></div></div></div>`}
  cards.innerHTML=html;
  const k=D.map(x=>COLS.filter(([c])=>state[x.s][c]).length),cnt=m=>k.filter(v=>m(v)).length;
  sum.innerHTML=`네 칸 모두 평범 안 <b>${cnt(v=>v===0)}명</b> · 한 칸에서만 바깥 ${cnt(v=>v===1)}명 · 두 칸 ${cnt(v=>v===2)}명 · 세 칸 넘게 <b>${cnt(v=>v>=3)}명</b>`;
  const sym=v=>v<0?'<span class="dn">↓</span>':v>0?'<span class="up">↑</span>':'<span class="mid">·</span>';
  roster.innerHTML='<table><tr><th>아이</th><th>그룹</th>'+COLS.map(([c,l])=>`<th>${l.split('(')[0]}</th>`).join('')+'</tr>'+
   D.filter(x=>x.g).sort((a,b)=>a.g.localeCompare(b.g)).map(x=>`<tr><td>${x.k||x.s} (${x.s})</td><td>${x.g}</td>`+COLS.map(([c,l,d])=>`<td>${sym(state[x.s][c])} ${fmt(x[c],d)}</td>`).join('')+'</tr>').join('')+'</table>'}
band.addEventListener('input',draw);draw();
</script></body></html>"""


def main():
    S = pd.read_csv(os.path.join(STORE, "stones_us.csv")).set_index("sym")
    R = pd.read_csv(os.path.join(STORE, "earn_react_us.csv")).set_index("sym")
    D = S.join(R[["react", "times"]], how="inner")
    ref = json.load(open(os.path.join(ROOT, "experiments", "ref", "quick_ref.json"), encoding="utf-8"))["us"]
    bars_last = pd.read_pickle(os.path.join(STORE, "bars_us.pkl"))["MSFT"].index.max().date()
    rows = [{"s": s, "k": (ref.get(s.replace("-", ".")) or ref.get(s) or {}).get("ko"), "g": ROSTER.get(s),
             "lake": round(float(r.lake), 2), "un": int(r.un), "react": round(float(r.react), 2), "times": round(float(r.times), 2)} for s, r in D.iterrows()]
    cols = [["lake", "평소 하루 폭 (호수)", 1, "%", "평소에 하루 동안 얼마나 오르내리나"],
            ["un", "예고 없는 돌 수 (3년)", 0, "개", "실적 · 파도 날이 아닌 날에 ±5% 넘게 움직인 횟수"],
            ["react", "실적 날 등락", 1, "%", "실적 발표 때 하루 움직임(3년 가운데 값)"],
            ["times", "실적 때 평소의 몇 배", 1, "배", "실적 날 움직임 ÷ 그 앞 평소 움직임"]]
    html = (PAGE.replace("__DATA__", json.dumps(rows, ensure_ascii=False)).replace("__COLS__", json.dumps(cols, ensure_ascii=False))
            .replace("__N__", str(len(rows))).replace("__LAST__", str(bars_last)))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(html)
    print("화면 →", OUT)
    # 터미널용: 70 · 80 · 90 에서 어떻게 달라지나
    for b in (70, 80, 90):
        t = (100 - b) / 200
        k = pd.Series(0, index=D.index)
        line = []
        for c, lb, d, u, _ in cols:
            lo, hi = D[c].quantile(t), D[c].quantile(1 - t)
            low = (D[c] <= lo) if lo == D[c].min() else (D[c] < lo)
            high = D[c] > hi
            k += (low | high).astype(int)
            line.append(f"{lb.split(' (')[0]} {lo:.{d}f} ~ {hi:.{d}f}{u}")
        print(f"가운데 {b}%: " + " · ".join(line) + f" | 네 칸 모두 평범 {int((k == 0).sum())}명 · 한 칸 {int((k == 1).sum())} · 두 칸 {int((k == 2).sum())} · 세 칸 넘게 {int((k >= 3).sum())}")


if __name__ == "__main__":
    main()
