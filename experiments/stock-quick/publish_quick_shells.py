"""종목 주가(간단 종목) 전용 고정 페이지 — 종목마다 주소 하나.

왜: `/p/stock.html?s=코드` 하나로는 Blogger 가 대표 주소(canonical · og:url)에서 `?s=` 를 떼어, 구글이 768종목을 한 페이지로 보고
    공유 링크도 종목 코드가 빠진다(11-15 실제 블로그로 확인). 종목마다 `/p/<영문이름>-<티커>-stock.html` 을 만든다.
본문 = 서버 글(검색 · 공유 미리보기가 읽는 것) + 아주 작은 불러오기 코드.
  - 서버 글: 기업 소개 두 문장(company_intro — 페이지마다 다른 글, 11-10 `크롤링됨 - 색인 안 됨` 대응) + 상장 · 업종 줄.
    방문 때는 불러오기 코드가 그날 조각(정식 렌더러 카드)으로 바꿔 끼운다 — 조각에도 같은 소개가 맨 앞 요약 아래 · `기업` 탭에 있다.
  - 불러오기 코드: 페이지 스크립트 묶음(js/quick.js = quick_page.js + 봉차트)을 Pages → jsDelivr 순으로 받아 실행.
    스크립트를 고쳐도 768쪽을 다시 쓰지 않는다 — 페이지는 소개가 바뀔 때만 고쳐 쓴다(해시가 같으면 건너뜀).
쓰기: 새 페이지 하루 NEW_CAP(25) · 고쳐 쓰기 하루 UPDATE_CAP(100), 4초 간격, 429 백오프 후에도 429 면 그 실행 멈춤(publish_pages 와 같은 규칙).
     새 페이지 = 밤 23:40 따로 실행(quick-shells-new.yml, --new-only)만, 한국 날짜 하루 합계 NEW_CAP(cache/shells_new_day.json).
     장 마감 실행(quick-data)은 --no-new 로 고쳐 쓰기만 (: 실행마다 50쪽 · 하루 약 100쪽을 몰아 만든 직후
     Blogger 가 4시간 넘게 새 글을 막아 17:00 · 21:00 시황이 빠졌다).
     소개가 아직 없는 종목은 만들지 않는다(같은 틀만 있는 페이지를 먼저 내보내지 않게).
기록: --cache(비공개 quick-state)/shells.json {sym: {"url", "id", "hash"}} — 브라우저용 주소표는 Pages /shells.json {파일 이름: 주소}.

    .venv/bin/python experiments/stock-quick/publish_quick_shells.py --cache DIR --bundle   # js/quick.js 다시 만들기(스크립트를 고친 뒤)
    .venv/bin/python experiments/stock-quick/publish_quick_shells.py --cache DIR --mock UBER,SBUX,259960.KS   # 목업 · 닮음 측정
    .venv/bin/python experiments/stock-quick/publish_quick_shells.py --cache DIR --publish [--map OUT.json]  # Blogger 에 (워크플로)
"""
import argparse
import datetime
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

NEW_CAP, UPDATE_CAP = 25, 100   # 새 페이지 하루 50 → 25
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


# ── 검색용 사실 요약 ─────────────────────────────────────────────
# 검색엔진은 스크립트 없이 읽는 본문만 확실히 본다(네이버는 스크립트를 거의 안 돌린다). 그날 주가처럼 날마다 바뀌는 값은
# 넣지 않는다 — 768쪽을 날마다 고쳐 써야 하고(UPDATE_CAP 100), 검색엔진도 날마다 다시 읽지 않아 낡은 값이 남는다.
# 분기에 한 번 바뀌는 것만: 최근 분기 실적 · 다음 실적 발표일 · 같은 업종 종목 분석 · 연관 종목. 해시가 같으면 다시 쓰지 않는다.
# 링크는 정식 종목 페이지만(주소가 바뀌지 않는다) — 간단 종목 이름은 글자로만(전용 페이지가 생길 때마다 해시가 바뀌지 않게).
Q_MONTHS = {"11013": (1, 3), "11012": (4, 6), "11014": (7, 9), "11011": (10, 12)}


def _money(v, kr):
    if kr:
        if abs(v) >= 1e12:
            jo, eok = divmod(round(abs(v) / 1e8), 10000)
            return ("−" if v < 0 else "") + (f"{jo:,}조 {eok:,}억 원" if eok else f"{jo:,}조 원")
        return f"{v / 1e8:,.0f}억 원".replace("-", "−")
    return f"{v / 1e8:,.0f}억 달러".replace("-", "−")


def _chg(new, old):
    """1년 전보다 — 흑자 · 적자가 바뀌면 말로, 아니면 %."""
    if new is None or old is None or old == 0:
        return ""
    if old < 0 <= new:
        return "1년 전 적자에서 흑자로 돌아섰습니다"
    if new < 0 <= old:
        return "1년 전 흑자에서 적자로 돌아섰습니다"
    if new < 0 and old < 0:   # 두 해 다 적자 — 적자 폭이 줄었나 늘었나
        return f"적자 폭이 1년 전보다 {'줄었' if new > old else '늘었'}습니다"
    p = (new - old) / abs(old) * 100
    return f"1년 전보다 {abs(p):.0f}% {'늘었' if p >= 0 else '줄었'}습니다"


def _quarter_line(span, rev, rev_old, op, op_old, kr):
    """`2026년 7~9월 분기 매출은 148억 달러로 1년 전보다 20% 늘었습니다. 영업이익은 …` — 실적 탭 첫 문장과 같은 말."""
    (y, m1, m2) = span
    out = f"{y}년 {m1}~{m2}월 분기 매출은 "
    c = _chg(rev, rev_old)
    out += f"{dk.josa(_money(rev, kr), '로')} {c}." if c else f"{_money(rev, kr)}입니다."
    if op is not None:
        word = "영업이익" if op >= 0 else "영업손실"
        c = _chg(op, op_old)
        out += f" {word}은 " + (f"{dk.josa(_money(abs(op), kr), '로')} {c}." if c else f"{_money(abs(op), kr)}입니다.")
    return out


def _us_quarter(sym, sec):
    rows = (sec.get("rev") or {}).get(sym) or []
    if not rows:
        return ""
    last = rows[-1]
    old = next((r for r in rows if r.get("cq") == f"{int(last['cq'][:4]) - 1}{last['cq'][4:]}"), None)
    cash = {c.get("cq"): c for c in (sec.get("cash") or {}).get(sym) or []}
    op = (cash.get(last["cq"]) or {}).get("opinc")
    op_old = (cash.get(old["cq"]) or {}).get("opinc") if old else None
    s, en = last["start"], last["end"]
    rev_old = old["rev"] if old else (last["rev"] / (1 + last["yoy"] / 100) if last.get("yoy") is not None else None)
    return _quarter_line((int(en[:4]), int(s[5:7]), int(en[5:7])), last["rev"], rev_old, op, op_old, False)


def _kr_quarter(code, cache_kr):
    """정기보고서(dart_fin_all) 와 잠정실적(dart_prelim) 중 더 최근 분기 — 같으면 정기보고서. 4분기 = 사업보고서 연간 − 3분기 누적."""
    corp = (cache_kr["corp"].get("map") or {}).get(code)
    fa = cache_kr["fin_all"].get(corp) or {}

    def q(key):
        v = (fa.get(key) or {}).get("v")
        if not v:
            return None
        rev, op = (v.get("rev") or [None])[0], (v.get("opinc") or [None])[0]
        if key.endswith("11011"):   # 사업보고서 = 연간 → 3분기 누적을 뺀다
            q3 = (fa.get(key[:5] + "11014") or {}).get("v") or {}
            r3, o3 = (q3.get("rev") or [None, None])[1], (q3.get("opinc") or [None, None])[1]
            rev = rev - r3 if rev is not None and r3 is not None else None
            op = op - o3 if op is not None and o3 is not None else None
        return (rev, op) if rev is not None else None

    best = None
    for key in sorted(fa, key=lambda k: (k[:4], Q_MONTHS.get(k[5:], (0, 0))[1]), reverse=True):
        got = q(key)
        if got:
            y, (m1, m2) = int(key[:4]), Q_MONTHS[key[5:]]
            old = q(f"{y - 1}-{key[5:]}") or (None, None)
            best = ((y, m1, m2), got[0], old[0], got[1], old[1])
            break
    p = cache_kr["prelim"].get(code) or {}
    if p.get("period") and p.get("rows", {}).get("rev"):
        s, en = p["period"]
        span = (int(en[:4]), int(s[5:7]), int(en[5:7]))
        if not best or (span[0], span[2]) > (best[0][0], best[0][2]):
            r, o = p["rows"]["rev"], (p["rows"].get("opinc") or {})
            best = (span, r.get("q"), r.get("yoy_v"), o.get("q"), o.get("yoy_v"))
    return _quarter_line(best[0], *best[1:], True) if best and best[1] is not None else ""


def _next_earn(sym, cache, today):
    """다음 실적 발표일 — 미국 = 회사 발표 예정일(earn_us), 한국 = 1년 전 같은 분기 잠정실적 날 + 364일 `무렵`(화면과 같은 어림)."""
    if sym.endswith((".KS", ".KQ")):
        days = (cache["kr"]["earn"].get("days") or {}).get(file_of(sym)) or []
        est = sorted(d for d in (str(datetime.date.fromisoformat(x) + datetime.timedelta(days=364)) for x in days) if d >= today)
        import collect_kr_earn_dart as KE
        if est and (datetime.date.fromisoformat(est[0]) - datetime.date.fromisoformat(today)).days <= KE.SKIP_DAYS:
            return (est[0], True)
        # 어림이 한 분기를 건너뛴다 = 그 분기는 잠정실적을 안 내는 회사(4분기를 3월 사업보고서로 대신하는 곳이 많다, 316종목 중 약 50곳)
        # → 법정 제출 기한(12월 결산: 분기 45일 · 사업보고서 90일). `4월 무렵` 처럼 틀린 날을 쓰지 않는다.
        import collect_kr_earn_dart as KE   # 화면 카드와 같은 기한 (2026-11-17)
        return (KE.deadline(today), "deadline")
    rows = (cache["earn_us"].get("rows") or {}).get(sym) or []
    nxt = sorted(r["day"] for r in rows if r.get("day", "") >= today)
    return (nxt[0], False) if nxt else None


def _fd(d):
    return f"{int(d[:4])}년 {int(d[5:7])}월 {int(d[8:10])}일"


def load_facts(cache_dir):
    """발행 단계가 한 번 읽는 캐시 묶음 (비공개 quick-state)."""
    j = lambda *p: CI._load(os.path.join(cache_dir, *p), {})  # noqa: E731
    return {"sec": j("sec_us.json"), "earn_us": j("earn_us.json"),
            "kr": {"corp": j("kr", "dart_corp.json"), "fin_all": j("kr", "dart_fin_all.json"), "prelim": j("kr", "dart_prelim.json"), "earn": j("kr", "dart_earn.json")},
            "links": (CI._load(os.path.join(EXP, "ref", "kr_us_links.json"), {}).get("links") or {})}


def _full_pages(ref):
    """정식 종목 {sym: (이름, 업종, 세부 업종, 주소)} — 링크는 이것만."""
    import universe as U
    import universe_kr as K
    out = {}
    for m, mod in (("us", U), ("kr", K)):
        for s, e in (ref.get(m) or {}).items():
            if e.get("full") and s in mod.BY_SYM:
                out[s] = (e.get("ko") or s, e.get("sector"), e.get("sub_ours") or e.get("sub"), mod.page_url(s))
    return out


def _name(ref, s):
    e = (ref.get("kr" if s.endswith((".KS", ".KQ")) else "us") or {}).get(s) or {}
    return e.get("ko") or s


def facts(sym, e, ref, fx, today=None):
    """검색용 사실 요약 [(제목, 글 html)] — 없는 것은 그 줄만 뺀다(빈 답 금지)."""
    today = today or datetime.date.today().isoformat()
    kr = sym.endswith((".KS", ".KQ"))
    name = e.get("ko") or sym
    rows = []
    qline = _kr_quarter(file_of(sym), fx["kr"]) if kr else _us_quarter(sym, fx["sec"])
    nx = _next_earn(sym, fx, today)
    earn = ""
    if qline:
        earn = dk.esc(qline)
    if nx:
        nxt = (f"다음 실적은 법정 제출 기한인 {_fd(nx[0])}까지 나옵니다." if nx[1] == "deadline"
               else f"다음 실적 발표는 {_fd(nx[0])} 무렵입니다." if nx[1] else f"다음 실적 발표는 {_fd(nx[0])} 예정입니다.")
        earn += (" " if earn else "") + dk.esc(nxt)
    if earn:
        rows.append((f"{name} 실적은?", earn))
    full = fx.setdefault("_full", _full_pages(ref))
    same = [(n, u) for s, (n, sec, sub, u) in full.items() if s != sym and s.endswith((".KS", ".KQ")) == kr and sub and sub == (e.get("sub_ours") or e.get("sub"))]
    label = e.get("sub_ours") or e.get("sub")
    if not same:
        same = [(n, u) for s, (n, sec, sub, u) in full.items() if s != sym and s.endswith((".KS", ".KQ")) == kr and sec and sec == e.get("sector")]
        label = e.get("sector")
    if same:
        rows.append((f"같은 업종({label}) 종목은?", " · ".join(f'<a href="{u}">{dk.esc(n)} 종목 분석</a>' for n, u in same)))
    if kr:
        pairs = (fx["links"].get(sym) or {}).get("pairs") or []
        side = "미국 연관 종목"
    else:
        pairs = sorted(k for k, v in fx["links"].items() if sym in (v.get("pairs") or []))
        side = "한국 연관 종목"
    if pairs:
        cell = lambda s: f'<a href="{full[s][3]}">{dk.esc(full[s][0])}</a>' if s in full else dk.esc(_name(ref, s))  # noqa: E731
        rows.append((f"함께 움직이는 {'미국' if kr else '한국'} 종목은?",
                     f"{side}: " + " · ".join(cell(s) for s in pairs) + dk.esc(" — 지난 기록에서 미국 장이 크게 움직인 다음 날 한국 장이 같은 쪽으로 움직인 짝입니다.")))
    # `이 페이지에서 보는 것` 같은 공통 안내 줄은 넣지 않는다 — 모든 쪽에 같은 글이라 닮음만 올린다(509종목 측정: 넣으면 47.5% · 빼면 34.9%, 지금 40.8%)
    return rows


def facts_html(rows):
    h2 = f"margin:24px 0 8px;padding-left:{dk.ALIGN_PX}px;font-size:17px;line-height:26px;font-weight:700;color:#111;"
    p = f"margin:0 0 12px;padding-left:{dk.ALIGN_PX}px;font-size:15px;line-height:24px;color:#333;word-break:keep-all;"
    return "".join(f'<h2 style="{h2}">{dk.esc(t)}</h2><p style="{p}">{b}</p>' for t, b in rows)


def body(sym, e, intro, fx=None, ref=None):
    """서버 글 — 기업 소개 · 상장 · 업종 + 검색용 사실 요약(fx 가 있을 때). 방문 때 불러오기 코드가 #as-quick 안을 그날 조각으로 바꾼다."""
    import universe as U
    import universe_kr as K
    server = (f'<p data-seo-lead="1" style="{dk.SEO_LEAD}padding-left:{dk.ALIGN_PX}px;">{dk.esc(intro)}</p>'
              f'<p style="margin:0 0 12px;padding-left:{dk.ALIGN_PX}px;font-size:14px;line-height:22px;color:{dk.NOTE};">{dk.esc(info_line(sym, e))}</p>')
    if fx is not None:
        server += facts_html(facts(sym, e, ref or {}, fx))
    root = (f'<div id="as-quick" data-default="{file_of(sym)}" data-list-us="{U.STOCKS_URL}" data-list-kr="{K.STOCKS_URL}">'
            f'{dk.formal(server)}</div>\n')
    return root + LOADER


def server_text(sym, e, intro, fx=None, ref=None):
    """닮음 측정용 — 검색엔진이 스크립트 없이 읽는 글(제목 + 서버 글)."""
    t = html_mod.unescape(re.sub(r"<script.*?</script>", " ", body(sym, e, intro, fx, ref), flags=re.S))
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


def targets(ref, intros, markets=("us", "kr")):
    """소개가 있는 간단 종목만 — 정식 종목(full)은 종목 분석 페이지가 있다. markets = 이 실행이 맡는 시장(한국 실행은 한국 페이지만, 2026-11-20)."""
    out = []
    for m in markets:
        for s, e in sorted((ref.get(m) or {}).items()):
            if not e.get("full") and intros.get(s):
                out.append((s, e))
    return out


def _day_kst():
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)).date().isoformat()


def publish(cache, ref, intros, new_cap=NEW_CAP, update_cap=UPDATE_CAP, dry=False, markets=("us", "kr")):
    import requests
    import publish_blogger as PB
    import publish_pages as PP   # _call(429 백오프) · _norm 그대로
    path = os.path.join(cache, "shells.json")
    done = CI._load(path, {})
    day_path = os.path.join(cache, "shells_new_day.json")   # 새 페이지 하루 합계 — 손 실행 · 늦은 예비가 겹쳐도 하루 NEW_CAP 안
    day = CI._load(day_path, {})
    made_today = day.get("made", 0) if day.get("date") == _day_kst() else 0
    new_cap = max(0, min(new_cap, NEW_CAP - made_today))
    creds = PB._credentials()
    blog_id = PB._blog_id(creds, os.environ.get("BLOG_URL", PB.DEFAULT_BLOG_URL))
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    base = f"{PB.BLOGGER_API}/blogs/{blog_id}/pages"
    fx = load_facts(cache)
    made = updated = same = waiting = failed = 0
    stopped = False
    for s, e in targets(ref, intros, markets):
        content, t = body(s, e, intros[s], fx, ref), title(s, e)
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
                CI._save(day_path, {"date": _day_kst(), "made": made_today + made})
        time.sleep(4)
    print(f"[shells] 새로 {made}(오늘 합계 {made_today + made}/{NEW_CAP}) · 고침 {updated} · 그대로 {same} · 다음으로 미룸 {waiting} · 실패 {failed}"
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
    fx = load_facts(cache)
    for s, e in targets(ref, intros):
        if s not in only:
            continue
        # 검색엔진이 스크립트 없이 읽는 글 — 불러오기 코드 없이 (2026-11-17 A안 목업)
        seo = body(s, e, intros[s], fx, ref).replace(LOADER, "")
        dk.write_mock(seo, os.path.join(out, f"mock_shell_{file_of(s)}_seo.html"), title(s, e))
        b = body(s, e, intros[s], fx, ref).replace(f'data-default="{file_of(s)}"', f'data-default="{file_of(s)}" data-local="quick-data/"')
        b = b.replace(LOADER, '<script src="quick-data/js/quick.js"></script>')
        p = dk.write_mock(b, os.path.join(out, f"mock_shell_{file_of(s)}.html"), title(s, e))
        rows.append((s, title(s, e), f"/p/{slug(s, e)}.html", server_text(s, e, intros[s], fx, ref), p))
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
    ap.add_argument("--no-new", action="store_true", help="새 페이지는 만들지 않고 고쳐 쓰기만 (장 마감 실행, 2026-11-24)")
    ap.add_argument("--new-only", action="store_true", help="새 페이지만 — 고쳐 쓰기 안 함 (밤 23:40 따로 실행, 2026-11-24)")
    ap.add_argument("--market", choices=("all", "us", "kr"), default="all",
                    help="이 실행이 맡는 시장 — 한국 장 마감 실행이 미국 페이지(알파벳 순 10~24분)를 고치느라 늦지 않게 (2026-11-20 사용자)")
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
        print(f"[shells] 서버 글 닮음 평균 — 지금 {similarity(texts)}% (종목 {len(texts)})")
        fx = load_facts(a.cache)
        texts = {s: server_text(s, e, intros[s], fx, ref) for s, e in targets(ref, intros)}
        print(f"[shells] 서버 글 닮음 평균 — 사실 요약 넣은 뒤 {similarity(texts)}% · 평균 글자 수 {sum(map(len, texts.values())) // max(len(texts), 1)}")
    if a.publish or a.dry:
        done = publish(a.cache, ref, intros, dry=a.dry,
                       new_cap=0 if a.no_new else NEW_CAP, update_cap=0 if a.new_only else UPDATE_CAP, markets=("us", "kr") if a.market == "all" else (a.market,))
        if a.map:
            print(f"[shells] 주소표 {write_map(done, a.map)}쪽 → {a.map}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv

    load_dotenv(os.path.join(EXP, "..", ".env"))
    main()
