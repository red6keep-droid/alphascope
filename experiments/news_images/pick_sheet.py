"""자료 사진 줄이기 — 완료/ 안에서 사진이 많은 주제만 보여 주고, 뺄 사진을 눌러 2~3장만 남긴다.

  python pick_sheet.py               # 완료/고르기.html (주제마다 4장 이상인 폴더만)
  python pick_sheet.py --over 3      # 기준 바꾸기
  python pick_sheet.py --apply ~/Downloads/고르기-결정.json
      # 고른(빼기) 사진 → 사용안함/<같은 경로>(이유 '사용자 고르기')

지우지 않는다. 회사 사진(1_기업-사진)은 회사마다 3장 이하라 대상이 아니다.
"""
import argparse, csv, html, json, os, shutil

BASE = os.path.expanduser("~/Desktop/Newfact-그림-검수")
DONE = os.path.join(BASE, "완료")
TRASH = os.path.join(BASE, "사용안함")
LIST = os.path.join(TRASH, "사용안함-목록.csv")
IMG = (".jpg", ".jpeg", ".png", ".webp")


def folders():
    g = {}
    for dp, dn, fn in os.walk(DONE):
        rel = os.path.relpath(dp, DONE)
        if rel.startswith("1_") or rel == ".":
            continue
        imgs = sorted(f for f in fn if f.lower().endswith(IMG))
        if imgs:
            g[rel] = [os.path.join(rel, f) for f in imgs]
    return dict(sorted(g.items()))


def build(over):
    with open(os.path.join(DONE, "출처.csv"), encoding="utf-8-sig") as f:
        src = {r["file"]: r for r in csv.DictReader(f)}
    big = {k: v for k, v in folders().items() if len(v) > over}
    toc = "".join(f"<a href='#g{i}'>{html.escape(k.split('/',1)[1])} <i>{len(v)}</i></a>" for i, (k, v) in enumerate(big.items()))
    body = []
    for i, (k, v) in enumerate(big.items()):
        body.append(f"<section id='g{i}' data-g='{html.escape(k)}'><h2>{html.escape(k.replace('_', ' '))} "
                    f"<span class=n>남음 <b>{len(v)}</b> / {len(v)}</span></h2>"
                    f"<div class=g>")
        for p in v:
            r = src.get(p, {})
            link = f" · <a href='{html.escape(r['source'])}' target=_blank>원본</a>" if r.get("source") else ""
            body.append(f"<div class=c data-f='{html.escape(p)}'><img loading=lazy src='{html.escape(p)}'>"
                        f"<div class=t>{html.escape(r.get('license',''))} · {html.escape(r.get('artist','')[:40])}{link}</div></div>")
        body.append("</div></section>")
    page = f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>자료 사진 고르기</title><style>
body{{font-family:-apple-system,sans-serif;margin:0;background:#f4f4f5;color:#111}}
.bar{{position:sticky;top:0;z-index:5;background:#fff;border-bottom:1px solid #ddd;padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}}
.bar b{{font-size:16px}} .bar button{{font-size:14px;padding:8px 14px;border-radius:8px;border:1px solid #ccc;background:#fff;cursor:pointer}}
.bar .save{{background:#2563eb;color:#fff;border-color:#2563eb}} .cnt{{font-size:14px;color:#444}}
.help{{padding:0 16px;font-size:13px;color:#555}} .toc{{padding:10px 16px;display:flex;flex-wrap:wrap;gap:6px}}
.toc a{{font-size:13px;background:#fff;border:1px solid #ddd;border-radius:6px;padding:4px 8px;color:#111;text-decoration:none}}
.toc a.done{{background:#dcfce7;border-color:#16a34a}} i{{font-style:normal;color:#888}}
main{{padding:0 16px 80px}} h2{{font-size:16px;margin:28px 0 8px}} .n{{font-size:13px;font-weight:400;color:#666;margin-left:8px}} .n b{{color:#dc2626}} section.ok .n b{{color:#16a34a}}
.g{{display:flex;flex-wrap:wrap;gap:8px}} .c{{width:300px;background:#fff;border:3px solid transparent;border-radius:8px;overflow:hidden;font-size:11px;cursor:pointer;position:relative}}
.c img{{width:300px;height:200px;object-fit:cover;display:block;background:#e5e5e5}} .c .t{{padding:6px 8px;color:#555}} .c a{{color:#2563eb}}
.c.k{{border-color:#dc2626}} .c.k img{{opacity:.3}} .c.k::after{{content:"빼기";position:absolute;top:8px;left:8px;background:#dc2626;color:#fff;font-weight:700;font-size:13px;padding:3px 8px;border-radius:6px}}
</style>
<div class=bar><b>자료 사진 고르기</b><span class=cnt>주제 {len(big)}개 · 3장 이하로 줄인 주제 <b id=nd>0</b></span>
<button class=save onclick="save()">결정 저장</button><button onclick="if(confirm('고른 것을 모두 지울까요?')){{K.clear();paint()}}">고른 것 지우기</button></div>
<p class=help>뺄 사진을 누르세요(<b style="color:#dc2626">빼기</b>, 다시 누르면 취소). 주제마다 남은 장수가 보이고, 3장 이하가 되면 초록으로 바뀝니다. 저장 뒤 뺀 사진은 사용안함으로 옮깁니다(지우지 않음). 다 고르신 뒤 <b>결정 저장</b> → 다운로드 폴더 <code>고르기-결정.json</code>.</p>
<div class=toc>{toc}</div><main>{''.join(body)}</main>
<script>
const KEY='newfact-pick-out-v1';let K=new Set();try{{K=new Set(JSON.parse(localStorage.getItem(KEY)||'[]'))}}catch(e){{}}
function paint(){{let d=0;document.querySelectorAll('section').forEach((s,i)=>{{const cs=s.querySelectorAll('.c');let n=cs.length;cs.forEach(c=>{{const k=K.has(c.dataset.f);c.classList.toggle('k',k);n-=k}});
const ok=n<=3;s.classList.toggle('ok',ok);s.querySelector('.n b').textContent=n;document.querySelector(`.toc a[href="#${{s.id}}"]`).classList.toggle('done',ok);d+=ok}});
nd.textContent=d;try{{localStorage.setItem(KEY,JSON.stringify([...K]))}}catch(e){{}}}}
document.addEventListener('click',e=>{{if(e.target.closest('a'))return;const c=e.target.closest('.c');if(!c)return;const f=c.dataset.f;K.has(f)?K.delete(f):K.add(f);paint()}});
function save(){{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify({{빼기:[...K]}},null,1)],{{type:'application/json'}}));a.download='고르기-결정.json';a.click()}}
paint();
</script>"""
    with open(os.path.join(DONE, "고르기.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print(f"고르기.html — 주제 {len(big)}개 · 사진 {sum(map(len, big.values()))}장")


def apply(path):
    drop = set(json.load(open(os.path.expanduser(path), encoding="utf-8"))["빼기"])
    with open(os.path.join(DONE, "출처.csv"), encoding="utf-8-sig") as f:
        src_rows = list(csv.DictReader(f))
    src = {r["file"]: r for r in src_rows}
    with open(LIST, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out = []
    for k, v in folders().items():
        for p in v:
            if p not in drop:
                continue
            dst = os.path.join(TRASH, p)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(os.path.join(DONE, p), dst)
            rows = [r for r in rows if r["file"] != p]
            rows.append({"file": p, "reason": "사용자 고르기", "value": "", "title": src.get(p, {}).get("title", "")})
            out.append(p)
    with open(LIST, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "reason", "value", "title"])
        w.writeheader()
        w.writerows(rows)
    gone = set(out)
    with open(os.path.join(DONE, "출처.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(src_rows[0].keys()))
        w.writeheader()
        w.writerows(r for r in src_rows if r["file"] not in gone)
    print(f"사용안함으로 {len(out)}장")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--over", type=int, default=3)
    ap.add_argument("--apply")
    a = ap.parse_args()
    if a.apply:
        apply(a.apply)
    build(a.over)
