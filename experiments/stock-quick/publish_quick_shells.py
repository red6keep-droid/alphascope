"""종목 주가(간단 종목) 전용 고정 페이지 — 종목마다 주소 하나 (2026-11-15 사용자).

왜: `/p/stock.html?s=코드` 하나로는 Blogger 가 대표 주소(canonical · og:url)에서 `?s=` 를 떼어, 구글이 768종목을 한 페이지로 보고
    공유 링크도 종목 코드가 빠진다(11-15 실제 블로그로 확인). 종목마다 `/p/<영문이름>-<티커>-stock.html` 을 만든다.
본문 = 서버 글(검색 · 공유 미리보기가 읽는 것) + 아주 작은 불러오기 코드.
  - 서버 글: 기업 소개 두 문장(company_intro — 페이지마다 다른 글, 11-10 `크롤링됨 - 색인 안 됨` 대응) + 상장 · 업종 줄.
    방문 때는 불러오기 코드가 그날 조각(정식 렌더러 카드)으로 바꿔 끼운다 — 조각에도 같은 소개가 맨 앞 요약 아래 · `기업` 탭에 있다.
  - 불러오기 코드: 페이지 스크립트 묶음(js/quick.js = quick_page.js + 봉차트)을 Pages → jsDelivr 순으로 받아 실행.
    스크립트를 고쳐도 768쪽을 다시 쓰지 않는다 — 페이지는 소개가 바뀔 때만 고쳐 쓴다(해시가 같으면 건너뜀).
쓰기: 새 페이지 하루 NEW_CAP(50) · 고쳐 쓰기 하루 UPDATE_CAP(100), 4초 간격, 429 백오프 후에도 429 면 그 실행 멈춤(publish_pages 와 같은 규칙).
     소개가 아직 없는 종목은 만들지 않는다(같은 틀만 있는 페이지를 먼저 내보내지 않게).
기록: --cache(비공개 quick-state)/shells.json {sym: {"url", "id", "hash"}} — 브라우저용 주소표는 Pages /shells.json {파일 이름: 주소}.

    .venv/bin/python experiments/stock-quick/publish_quick_shells.py --cache DIR --bundle   # js/quick.js 다시 만들기(스크립트를 고친 뒤)
    .venv/bin/python experiments/stock-quick/publish_quick_shells.py --cache DIR --mock UBER,SBUX,259960.KS   # 목업 · 닮음 측정
    .venv/bin/python experiments/stock-quick/publish_quick_shells.py --cache DIR --publish [--map OUT.json]  # Blogger 에 (워크플로)
"""
import argparse
import difflib
import hashlib
import html as html_mod
import itertools
import json
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [HERE, EXP, os.path.join(EXP, "stock-radar"), os.path.join(EXP, "kr-stocks"), os.path.join(EXP, "daily-report")]
import design_kit as dk  # noqa: E402
import company_intro as CI  # noqa: E402

NEW_CAP, UPDATE_CAP = 50, 100
BUNDLE = os.path.join(HERE, "pages_static", "js", "quick.js")   # 저장소에 둔다 — Pages 가 같은 폴더를 올리고, jsDelivr(@main)가 예비
PAGES = "https://alpha-scope.pages.dev/"
JSD = "https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@main/experiments/stock-quick/pages_static/"
DROP = {"inc", "corp", "corporation", "co", "ltd", "company", "plc", "limited", "the", "nv", "sa", "ag", "se", "llc", "lp", "holdings", "group"}

LOADER = ("<script>(function(){var u=['" + PAGES + "js/quick.js','" + JSD + "js/quick.js'];"
          "for(var i=0;i<u.length;i++){try{var x=new XMLHttpRequest();x.open('GET',u[i],false);x.send(null);"
          "if(x.status===200&&x.responseText){(0,eval)(x.responseText);return;}}catch(e){}}})();</script>")


def bundle():
    """quick_page.js + 봉차트(candle_chart.SCRIPT 안쪽) — 조각을 끼운 뒤 봉차트를 그리게 이 순서."""
    import candle_chart as CC
    js = open(os.path.join(HERE, "quick_page.js"), encoding="utf-8").read()
    cc = re.sub(r"^\s*<script>|</script>\s*$", "", CC.SCRIPT.strip())
    os.makedirs(os.path.dirname(BUNDLE), exist_ok=True)
    out = "/* 만든 파일 — 고치지 말 것: experiments/stock-quick/publish_quick_shells.py --bundle (quick_page.js + candle_chart.SCRIPT) */\n" + js + "\n;\n" + cc + "\n"
    open(BUNDLE, "w", encoding="utf-8").write(out)
    return out


def file_of(sym):
    return sym.split(".")[0]


def slug(sym, e):
    words = [w for w in re.split(r"[^a-z0-9]+", (e.get("en") or "").lower().replace("&", " and ")) if w and w not in DROP]
    tick = file_of(sym).lower().replace(".", "-")
    words = words or [tick]
    name = ""
    for w in words:   # 이름 부분 22자 안 — Blogger 가 긴 제목 주소를 자른다
        if len(name) + len(w) + (1 if name else 0) > 22:
            break
        name = f"{name}-{w}" if name else w
    name = name or words[0][:22]
    return f"{tick}-stock" if name == tick else f"{name}-{tick}-stock"   # 이름 = 티커(Uber → UBER)면 한 번만


def title(sym, e):
    ko = e.get("ko") or e.get("en") or sym
    if sym.endswith((".KS", ".KQ")):
        return f"{ko} 주가"
    return f"{sym} 주가" if ko == sym else f"{ko} {sym} 주가"


def info_line(sym, e):
    kr = sym.endswith((".KS", ".KQ"))
    mk = {"KOSPI": "유가증권시장", "KOSDAQ": "코스닥"}.get(e.get("market"), "유가증권시장") if kr else "미국 증시"
    parts = [f"{mk} 상장", f"{'종목 코드' if kr else '티커'} {file_of(sym)}", e.get("sector")]
    sub = e.get("sub_ours") or e.get("sub")
    if sub and sub != e.get("sector"):
        parts.append(sub)
    return " · ".join(p for p in parts if p)


def body(sym, e, intro):
    """서버 글 — 기업 소개 · 상장 · 업종. 방문 때 불러오기 코드가 #as-quick 안을 그날 조각으로 바꾼다."""
    import universe as U
    import universe_kr as K
    server = (f'<p data-seo-lead="1" style="{dk.SEO_LEAD}padding-left:{dk.ALIGN_PX}px;">{dk.esc(intro)}</p>'
              f'<p style="margin:0 0 12px;padding-left:{dk.ALIGN_PX}px;font-size:14px;line-height:22px;color:{dk.NOTE};">{dk.esc(info_line(sym, e))}</p>')
    root = (f'<div id="as-quick" data-default="{file_of(sym)}" data-list-us="{U.LIST_URL}" data-list-kr="{K.LIST_URL}">'
            f'{dk.formal(server)}</div>\n')
    return root + LOADER


def server_text(sym, e, intro):
    """닮음 측정용 — 검색엔진이 스크립트 없이 읽는 글(제목 + 서버 글)."""
    t = html_mod.unescape(re.sub(r"<script.*?</script>", " ", body(sym, e, intro), flags=re.S))
    return title(sym, e) + " " + re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)).strip()


def similarity(texts, pairs=400, seed=7):
    """평균 닮음 — 글자 순서 비교(difflib) 0~100. 쌍이 많으면 표본."""
    keys = list(texts)
    allp = list(itertools.combinations(keys, 2))
    if len(allp) > pairs:
        allp = random.Random(seed).sample(allp, pairs)
    if not allp:
        return None
    return round(100 * sum(difflib.SequenceMatcher(None, texts[a], texts[b]).ratio() for a, b in allp) / len(allp), 1)


def targets(ref, intros):
    """소개가 있는 간단 종목만 — 정식 종목(full)은 종목 분석 페이지가 있다."""
    out = []
    for m in ("us", "kr"):
        for s, e in sorted((ref.get(m) or {}).items()):
            if not e.get("full") and intros.get(s):
                out.append((s, e))
    return out


def publish(cache, ref, intros, new_cap=NEW_CAP, update_cap=UPDATE_CAP, dry=False):
    import requests
    import publish_blogger as PB
    import publish_pages as PP   # _call(429 백오프) · _norm 그대로
    path = os.path.join(cache, "shells.json")
    done = CI._load(path, {})
    creds = PB._credentials()
    blog_id = PB._blog_id(creds, os.environ.get("BLOG_URL", PB.DEFAULT_BLOG_URL))
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    base = f"{PB.BLOGGER_API}/blogs/{blog_id}/pages"
    made = updated = same = waiting = failed = 0
    stopped = False
    for s, e in targets(ref, intros):
        content, t = body(s, e, intros[s]), title(s, e)
        h = hashlib.sha256((t + "\n" + content).encode("utf-8")).hexdigest()[:16]
        rec = done.get(s)
        if rec and rec.get("hash") == h:
            same += 1
            continue
        if (not rec and made >= new_cap) or (rec and updated >= update_cap):
            waiting += 1
            continue
        if dry:
            print(f"[shells] {'고침' if rec else '새로'} {s}: {t} → /p/{slug(s, e)}.html")
            made += 0 if rec else 1
            updated += 1 if rec else 0
            continue
        try:
            if rec:
                r = PP._call(requests, "put", f"{base}/{rec['id']}", headers=headers, json={"kind": "blogger#page", "id": rec["id"], "title": t, "content": content})
                updated += 1
            else:
                made += 1   # 실패도 센다 — 429 나는 날 더 밀어붙이지 않게
                r = PP._call(requests, "post", base, headers=headers, json={"kind": "blogger#page", "title": slug(s, e).replace("-", " "), "content": content})
                new = r.json()
                time.sleep(2)
                r = PP._call(requests, "put", f"{base}/{new['id']}", headers=headers, json={"kind": "blogger#page", "id": new["id"], "title": t, "content": content})
            j = r.json()
            done[s] = {"url": j.get("url"), "id": j.get("id"), "hash": h}
            print(f"[shells] {'고침' if rec else '새로'} {s}: {j.get('url')}")
        except Exception as ex:  # noqa: BLE001
            failed += 1
            print(f"::warning::[shells] {s} 실패: {str(ex)[:200]}")
            if getattr(getattr(ex, "response", None), "status_code", None) == 429:
                stopped = True
                break
        finally:
            if not dry:
                CI._save(path, done)   # 한 쪽마다 — 중간에 멈춰도 만든 주소를 잃지 않게
        time.sleep(4)
    print(f"[shells] 새로 {made} · 고침 {updated} · 그대로 {same} · 다음으로 미룸 {waiting} · 실패 {failed}"
          + (" · 429 로 멈춤" if stopped else "") + f" · 전체 {len(done)}쪽")
    return done


def write_map(done, out_path):
    """브라우저용 주소표 {파일 이름(UBER · 259960): 주소} — /p/stock.html?s= 가 전용 페이지로 넘긴다."""
    m = {file_of(s): r["url"] for s, r in done.items() if r.get("url")}
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    json.dump(m, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return len(m)


def mock(cache, ref, intros, only):
    """목업 — 검색엔진이 보는 서버 글(왼쪽) · 방문자가 보는 화면(불러온 뒤)은 목업 서버에서 data-local 로."""
    out = os.path.join(HERE, "output")
    os.makedirs(out, exist_ok=True)
    rows = []
    for s, e in targets(ref, intros):
        if s not in only:
            continue
        b = body(s, e, intros[s]).replace(f'data-default="{file_of(s)}"', f'data-default="{file_of(s)}" data-local="quick-data/"')
        b = b.replace(LOADER, '<script src="quick-data/js/quick.js"></script>')
        p = dk.write_mock(b, os.path.join(out, f"mock_shell_{file_of(s)}.html"), title(s, e))
        rows.append((s, title(s, e), f"/p/{slug(s, e)}.html", server_text(s, e, intros[s]), p))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--bundle", action="store_true")
    ap.add_argument("--mock", default="")
    ap.add_argument("--measure", action="store_true", help="소개가 있는 전 종목 서버 글 닮음")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--map", default="")
    a = ap.parse_args()
    ref = CI._load(os.path.join(EXP, "ref", "quick_ref.json"), {})
    CI.apply(a.cache)
    intros = CI.load(a.cache)
    if a.bundle:
        print(f"[shells] 묶음 {len(bundle()):,}자 → {BUNDLE}")
    if a.mock:
        for s, t, u, txt, p in mock(a.cache, ref, intros, {x.strip() for x in a.mock.split(",")}):
            print(f"{s} · {t} · {u}\n   서버 글: {txt}\n   목업: {p}")
    if a.measure:
        texts = {s: server_text(s, e, intros[s]) for s, e in targets(ref, intros)}
        print(f"[shells] 서버 글 닮음 평균 {similarity(texts)}% (종목 {len(texts)})")
    if a.publish or a.dry:
        done = publish(a.cache, ref, intros, dry=a.dry)
        if a.map:
            print(f"[shells] 주소표 {write_map(done, a.map)}쪽 → {a.map}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv

    load_dotenv(os.path.join(EXP, "..", ".env"))
    main()
