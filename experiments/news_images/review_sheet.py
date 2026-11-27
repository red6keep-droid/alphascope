"""자료 사진 사용자 검수표 — 지금 폴더에 남은 그림만 보여 주고, 눌러서 빼기 · 살리기를 고른다.

  python review_sheet.py            # ~/Desktop/Newfact-그림-검수/검수표.html 다시 만들기(완료/ 는 안 보임)
  python review_sheet.py --skip-logos   # 로고 빼고
  python review_sheet.py --apply ~/Downloads/검수-결정.json
                                    # 검수표에서 저장한 결정대로 옮기기(빼기 → 사용안함/, 살리기 → 제자리)

지우지 않는다. 빼기 = 사용안함/<원래 경로> + 사용안함-목록.csv 에 이유 '사용자 검수' 한 줄.
"""
import argparse, csv, html, json, os, shutil

ROOT = os.path.expanduser("~/Desktop/Newfact-그림-검수")
TRASH = os.path.join(ROOT, "사용안함")
LIST = os.path.join(TRASH, "사용안함-목록.csv")
IMG = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def sources():
    with open(os.path.join(ROOT, "출처.csv"), encoding="utf-8-sig") as f:
        return {r["file"]: r for r in csv.DictReader(f)}


def scan(base):
    out = []
    for dp, dn, fn in os.walk(base):
        dn.sort()
        for f in sorted(fn):
            if f.lower().endswith(IMG):
                out.append(os.path.relpath(os.path.join(dp, f), base))
    return out


def card(rel, src, r, logo):
    meta = (f"{html.escape(r.get('license', ''))} · {html.escape(r.get('artist', '')[:50])}" if r else "출처 없음")
    link = f" · <a href='{html.escape(r['source'])}' target=_blank>원본</a>" if r and r.get("source") else ""
    return (f"<div class='c{' logo' if logo else ''}' data-f='{html.escape(rel)}'><img loading=lazy src='{html.escape(src)}'>"
            f"<div class=t><b>{html.escape(os.path.basename(rel))}</b><br>{meta}{link}</div></div>")


def build(skip_logos=False):
    src = sources()
    keep = [p for p in scan(ROOT) if not p.startswith(("사용안함", "완료"))   # 완료 = 사용자가 이미 확정한 사진
            and not (skip_logos and p.startswith("2_기업-로고"))]
    out = scan(TRASH)
    reasons = {}
    if os.path.exists(LIST):
        with open(LIST, encoding="utf-8-sig") as f:
            reasons = {r["file"]: r["reason"] for r in csv.DictReader(f)}

    def groups(files):
        g = {}
        for p in files:
            g.setdefault(os.path.dirname(p), []).append(p)
        return g

    gk, go = groups(keep), groups(out)
    toc = "".join(f"<a href='#k{i}'>{html.escape(g)} <i>{len(v)}</i></a>" for i, (g, v) in enumerate(gk.items()))
    body = []
    for i, (g, v) in enumerate(gk.items()):
        body.append(f"<h2 id='k{i}'>{html.escape(g)} <i>{len(v)}</i></h2><div class=g>")
        body += [card(p, p, src.get(p), "로고" in g) for p in v]
        body.append("</div>")
    tbody = []
    for i, (g, v) in enumerate(go.items()):
        tbody.append(f"<h2>{html.escape(g)} <i>{len(v)}</i></h2><div class=g>")
        for p in v:
            tbody.append(card(p, "사용안함/" + p, src.get(p), "로고" in g).replace(
                "<div class=t>", f"<div class=t><span class=why>{html.escape(reasons.get(p, ''))}</span><br>", 1))
        tbody.append("</div>")

    page = f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Newfact 자료 사진 검수</title><style>
body{{font-family:-apple-system,sans-serif;margin:0;background:#f4f4f5;color:#111}}
.bar{{position:sticky;top:0;z-index:5;background:#fff;border-bottom:1px solid #ddd;padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}}
.bar b{{font-size:16px}} .bar button{{font-size:14px;padding:8px 14px;border-radius:8px;border:1px solid #ccc;background:#fff;cursor:pointer}}
.bar button.on{{background:#111;color:#fff;border-color:#111}} .bar .save{{background:#2563eb;color:#fff;border-color:#2563eb}}
.cnt{{font-size:14px;color:#444}} .cnt em{{font-style:normal;font-weight:700;color:#dc2626}} .cnt u{{text-decoration:none;font-weight:700;color:#16a34a}}
.toc{{padding:10px 16px;display:flex;flex-wrap:wrap;gap:6px}} .toc a{{font-size:13px;background:#fff;border:1px solid #ddd;border-radius:6px;padding:4px 8px;color:#111;text-decoration:none}}
i{{font-style:normal;color:#888;font-weight:400}} main{{padding:0 16px 80px}} h2{{font-size:16px;margin:28px 0 8px}}
.help{{padding:0 16px;font-size:13px;color:#555}}
.g{{display:flex;flex-wrap:wrap;gap:8px}} .c{{width:240px;background:#fff;border:3px solid transparent;border-radius:8px;overflow:hidden;font-size:11px;cursor:pointer;position:relative}}
.c img{{width:240px;height:160px;object-fit:cover;display:block;background:#e5e5e5}} .c.logo img{{object-fit:contain;background:#fff}}
.c .t{{padding:6px 8px;color:#555;word-break:break-all}} .c .t b{{color:#111}} .c a{{color:#2563eb}} .why{{color:#b45309}}
.c.x{{border-color:#dc2626}} .c.x img{{opacity:.35}} .c.x::after{{content:"빼기";position:absolute;top:8px;left:8px;background:#dc2626;color:#fff;font-weight:700;font-size:13px;padding:3px 8px;border-radius:6px}}
.c.s{{border-color:#16a34a}} .c.s::after{{content:"살리기";position:absolute;top:8px;left:8px;background:#16a34a;color:#fff;font-weight:700;font-size:13px;padding:3px 8px;border-radius:6px}}
#out{{display:none}} body.trash #in{{display:none}} body.trash #out{{display:block}}
</style>
<div class=bar><b>자료 사진 검수</b>
<button id=b1 class=on onclick="tab(0)">남은 그림 {len(keep)}</button><button id=b2 onclick="tab(1)">사용안함 {len(out)}</button>
<span class=cnt>빼기 <em id=nx>0</em> · 살리기 <u id=ns>0</u></span>
<button class=save onclick="save()">결정 저장</button><button onclick="if(confirm('고른 것을 모두 지울까요?')){{X.clear();S.clear();paint()}}">고른 것 지우기</button></div>
<p class=help>남은 그림을 누르면 <b style="color:#dc2626">빼기</b>, 다시 누르면 취소. 사용안함 탭에서 누르면 <b style="color:#16a34a">살리기</b>. 고른 것은 이 브라우저에 저장되니 나눠서 보셔도 됩니다. 다 보신 뒤 <b>결정 저장</b> → 다운로드 폴더에 <code>검수-결정.json</code> 이 생기면 알려 주세요.</p>
<div id=in><div class=toc>{toc}</div><main>{''.join(body)}</main></div>
<div id=out><main>{''.join(tbody)}</main></div>
<script>
const K='newfact-review-v1';let X=new Set(),S=new Set();
try{{const d=JSON.parse(localStorage.getItem(K)||'{{}}');X=new Set(d.x||[]);S=new Set(d.s||[])}}catch(e){{}}
function store(){{try{{localStorage.setItem(K,JSON.stringify({{x:[...X],s:[...S]}}))}}catch(e){{}}}}
function paint(){{document.querySelectorAll('#in .c').forEach(c=>c.classList.toggle('x',X.has(c.dataset.f)));
document.querySelectorAll('#out .c').forEach(c=>c.classList.toggle('s',S.has(c.dataset.f)));
nx.textContent=X.size;ns.textContent=S.size;store()}}
document.addEventListener('click',e=>{{if(e.target.closest('a'))return;const c=e.target.closest('.c');if(!c)return;
const set=c.closest('#in')?X:S,f=c.dataset.f;set.has(f)?set.delete(f):set.add(f);paint()}});
function tab(t){{document.body.classList.toggle('trash',t==1);b1.classList.toggle('on',t==0);b2.classList.toggle('on',t==1);scrollTo(0,0)}}
function save(){{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify({{빼기:[...X],살리기:[...S]}},null,1)],{{type:'application/json'}}));a.download='검수-결정.json';a.click()}}
paint();
</script>"""
    with open(os.path.join(ROOT, "검수표.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print(f"검수표.html — 남은 {len(keep)} · 사용안함 {len(out)}")


def apply(path):
    d = json.load(open(os.path.expanduser(path), encoding="utf-8"))
    src = sources()
    rows = []
    if os.path.exists(LIST):
        with open(LIST, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    moved = back = 0
    for rel in d.get("빼기", []):
        a, b = os.path.join(ROOT, rel), os.path.join(TRASH, rel)
        if os.path.exists(a):
            os.makedirs(os.path.dirname(b), exist_ok=True)
            shutil.move(a, b)
            rows = [r for r in rows if r["file"] != rel]
            rows.append({"file": rel, "reason": "사용자 검수", "value": "", "title": src.get(rel, {}).get("title", "")})
            moved += 1
    for rel in d.get("살리기", []):
        a, b = os.path.join(TRASH, rel), os.path.join(ROOT, rel)
        if os.path.exists(a):
            os.makedirs(os.path.dirname(b), exist_ok=True)
            shutil.move(a, b)
            rows = [r for r in rows if r["file"] != rel]
            back += 1
    with open(LIST, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "reason", "value", "title"])
        w.writeheader()
        w.writerows(rows)
    print(f"빼기 {moved} · 살리기 {back}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply")
    ap.add_argument("--skip-logos", action="store_true", help="로고는 빼고 보기(새 후보만 볼 때)")
    a = ap.parse_args()
    if a.apply:
        apply(a.apply)
    build(a.skip_logos)
