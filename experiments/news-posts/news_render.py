"""Newfact 주요 기사 — 뉴스 수집기(News-text) 글을 블로그 글 화면으로 그리기 (목업 · 나중 발행기 공용, 2026-11-23 사용자 "여기서 새로 그려").

재료 = 수집기 블로그 저장소 `news-text-blog` posts/{postId} (version 2 칸: title · summary · body · date · cat · direction · stage · stocks · sector · slug)
      + 블로그가 붙이는 `같은 날 시장 움직임` 숫자(market, 아래 same_day 꼴).
모양 = 요청 문서(News-text-doc/요청-알파스코프-뉴스-글-발행.md) 12 · 14절 — 시황 해설과 같은 꾸밈, 그림 없음:
    제목 줄 `Newfact 주요 기사` → 큰 머리글(기사 제목) → 라벨(분류 · 방향 · 단계) → 맨 앞 요약 → 본문(**결과** 굵게 · ==이유== 색 글씨)
    → 같은 날 시장 움직임(지수 칸 + 관련 종목, 코스피 · 평소 움직임과 견줌) → 함께 보는 페이지 → 공통 푸터.
참고 기사(언론사 · 기사 제목 · 링크)는 싣지 않는다(요청 7절 Q5). AI 0.

    from news_render import render
    title, html, meta = render(post, market, lists=…)
"""
import os
import re
import statistics
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, ".."))
sys.path.insert(0, os.path.join(BASE, "..", "market-commentary"))
sys.path.insert(0, os.path.join(BASE, "..", "kr-stocks"))
import design_kit as dk  # noqa: E402
import story_render as SR  # noqa: E402  시황 해설과 같은 꾸밈(강조 · 증감 색 · 종목 줄 · 지수 칸)
import universe_kr as UKR  # noqa: E402

BLOG = SR.BLOG
NAME = "Newfact 주요 기사"   # 글 이름 = 제목 줄 · 연재 라벨 (요청 12 · 14절. 4절의 옛 라벨 `Newfact 뉴스` 는 12절에서 이 이름으로)
LABEL_Q = "Newfact%20%EC%A3%BC%EC%9A%94%20%EA%B8%B0%EC%82%AC"
KR_REPORT = f"{BLOG}search/label/%ED%95%9C%EA%B5%AD%20%EC%A6%9D%EC%8B%9C%20%EB%A6%AC%ED%8F%AC%ED%8A%B8"
DIR_KIND = {"up": "positive", "down": "negative", "neutral": "neutral"}
STAGE_KO = {"confirmed": "확정", "discussing": "논의 중"}   # 방향 + 단계 두 칸 (논의 중 뉴스도 방향을 붙인다)
USUAL_N = 60   # 평소 움직임 = 직전 60거래일 하루 등락 폭(절댓값)의 중앙값
INDEX = [("^KS11", "코스피"), ("^KQ11", "코스닥")]


# ── 같은 날 시장 움직임 숫자 (블로그 데이터 — 지금은 yfinance 일봉) ──
def _ret(closes):
    return [(closes[i][0], closes[i][1] / closes[i - 1][1] * 100 - 100) for i in range(1, len(closes))]


def _move(closes, day):
    """closes = [(날짜 'YYYY-MM-DD', 종가)] 오래된 날부터 → day 이하 마지막 거래일의 {day, chg, usual}."""
    rets = [r for r in _ret(closes) if r[0] <= day]
    if not rets:
        return None
    d, chg = rets[-1]
    prev = [abs(v) for _, v in rets[-1 - USUAL_N:-1]]
    return {"day": d, "chg": round(chg, 2), "usual": round(statistics.median(prev), 2) if len(prev) >= 20 else None}


def kr_symbol(code):
    sym = next((s for s in UKR.BY_SYM if s.split(".")[0] == code), None)
    return sym or f"{code}.KS"


def same_day(post, lists, closes_of, closed_through):
    """→ market = {"basis", "indices": [{name, close, chg_pct, usual}], "stocks": [{ticker, name, chg_pct, usual, vs}]}.
    closes_of(symbol) → [(날짜, 종가)]. closed_through = 마감이 끝난 마지막 날(장중 값은 쓰지 않는다).
    종목 = 수집기 stocks 중 블로그 한국 종목 목록(lists)과 코드 · 이름이 모두 맞는 것만 (요청 8절 Q9)."""
    day = min(post["date"], closed_through)
    out = {"indices": [], "stocks": []}
    k = None
    for sym, name in INDEX:
        cl = closes_of(sym)
        m = _move(cl, day) if cl else None
        if not m:
            continue
        out["basis"] = out.get("basis") or m["day"]
        close = next(v for d, v in cl if d == m["day"])
        out["indices"].append({"name": name, "close": close, "chg_pct": m["chg"], "usual": m["usual"]})
        k = k if k is not None else m["chg"]
    for st in post.get("stocks") or []:
        code, name = str(st.get("code") or ""), (st.get("name") or "").strip()
        row = lists.get(code)
        if not (re.fullmatch(r"\d{6}", code) and row and row.get("n") == name):
            continue
        cl = closes_of(kr_symbol(code))
        m = _move(cl, day) if cl else None
        if not m or m["day"] != out.get("basis"):
            continue
        out["stocks"].append({"ticker": code, "name": name, "chg_pct": m["chg"], "usual": m["usual"],
                              "vs": round(m["chg"] - k, 2) if k is not None else None})
    return out


# ── 화면 ──
def _paras(body):
    return [p.strip() for p in re.split(r"\n\s*\n|\n", body or "") if p.strip()]


def _first_sentence(body):
    t = SR.emph(" ".join(_paras(body))[:400], False)
    m = re.match(r"(.+?다\.)", t)
    return m.group(1) if m else t


def _pct(v, unit="%"):
    return f"{abs(v):.2f}{unit}".replace(".00", "") if v is not None else ""


def _cmp_line(x, kospi):
    """종목 줄 아래 회색 한 줄 = 비교 두 개 (헌법 제1조): `코스피보다 0.32%p 더 · 평소 하루 1.6%의 1.4배`. 인과 말은 넣지 않는다 (요청 Q10)."""
    bits = []
    if x.get("vs") is not None and kospi is not None:
        v, c = x["vs"], x["chg_pct"]
        if abs(v) < 0.005:
            bits.append("코스피와 같은 폭")
        elif c * kospi < 0:   # 방향이 반대인 날
            bits.append(f'코스피와 반대로 {"오름" if c > 0 else "내림"}')
        elif c >= 0 and kospi >= 0:
            bits.append(f'코스피보다 {_pct(v, "%p")} {"더" if v > 0 else "덜"} 오름')
        else:
            bits.append(f'코스피보다 {_pct(v, "%p")} {"더" if v < 0 else "덜"} 내림')
    if x.get("usual"):
        r = abs(x["chg_pct"]) / x["usual"] if x["usual"] else 0
        bits.append(f'평소 하루 움직임({_pct(x["usual"])})' + (f"의 {r:.1f}배" if r >= 1.5 else "과 비슷" if r >= 0.5 else "보다 작음"))
    return " · ".join(bits)


def market_section(market, lists, ink):
    idx = market.get("indices") or []
    if not idx:
        return ""
    kospi = next((x["chg_pct"] for x in idx if x["name"] == "코스피"), None)
    inner = SR.index_row(idx)
    stocks = market.get("stocks") or []
    if stocks:
        rows = []
        for i, x in enumerate(stocks):
            r = SR.stock_row(x, lists.get(x["ticker"]), "pm", i == 0)
            line = _cmp_line(x, kospi)
            if line:
                r = r.replace(f"padding:{SR.LIST_ROW_PAD}px 12px;", f"padding:{SR.LIST_ROW_PAD}px 12px 6px;", 1)
                r += (f'<span style="display:block;padding:0 12px {SR.LIST_ROW_PAD}px {12 + SR.LOGO_Z + SR.LOGO_GAP}px;font-size:{dk.TINY};line-height:{dk.LH_TINY};'
                      f'color:#6B7280;word-break:keep-all;">{dk.esc(line)}</span>')
            rows.append(r)
        inner += SR.white_card("".join(rows))
    b = market.get("basis") or ""
    note = f"{int(b[5:7])}.{b[8:10]} 종가 기준. 같은 날 움직임을 나란히 적은 것으로, 기사 때문에 움직였다는 뜻은 아닙니다." if b else ""
    inner += dk.excl_note(note, margin="10px 0 0") if note else ""
    sec = dk.section("같은 날 시장 움직임", inner, line=False)
    return SR.tinted(SR.iconed(sec, dk.solid_icon("bars", ink)), ink).replace(f"margin:{SR.H2_TOP}px 0 11px;", f"margin:{SR.BIG_TOP}px 0 11px;", 1)


def titles(post):
    """(제목 줄, 저장 제목) — 테마가 저장 제목의 ` : ` 앞만 제목 줄에 보여 준다(시황 해설과 같은 장치, 본문에 [data-headline] 이 있을 때)."""
    return NAME, f"{NAME} : {post['title'].strip()}"


def render(post, market, lists=None):
    """→ (저장 제목, 본문 HTML, meta). summary 가 비면 본문 첫 문장(요청 12절 대체 규칙). 종목이 안 맞으면 지수만."""
    lists = lists or {}
    th = SR.MOOD_THEME["flat"]   # 글 전체 = 보라 테마 하나 (2026-11-23 사용자 "전체적으로 보라색") — 기사 방향으로 색을 바꾸지 않는다(방향은 라벨이 말한다)
    ink = th["ink"]
    col = {"tickers": [s.get("code") for s in post.get("stocks") or [] if s.get("code") in lists]}
    link = SR.Linker(col, {"close": {"movers": [{"name": lists[c]["n"], "ticker": c} for c in col["tickers"]]}}, ink)

    def prose(text, strong=True):
        return SR.who(SR.emph(link(SR.directional(dk.tint(dk.esc(dk.formal(text or ""))))), strong, ink))

    _, stored = titles(post)
    y, m, d = post["date"].split("-")
    style = ('<style>body:has([data-headline]) .pr-sticky{border-bottom:0;margin-bottom:0;}</style>')
    body = [style + f'<p data-title-basis="1" data-news-post="{dk.esc(post.get("slug") or "")}" style="margin:0 0 14px;font-size:13px;line-height:19px;color:#6B7280;">{int(m)}.{d} 기사</p>']
    body.append(f'<h2 data-headline="1" style="margin:0 0 14px;padding:10px 0 0 {dk.ALIGN_PX}px;font-size:26px;line-height:38px;font-weight:700;color:#111;word-break:keep-all;">'
                f'<span style="display:block;font-size:26px;line-height:38px;">{SR.emph(dk.esc(post["title"]), False)}</span></h2>')   # 폰 테마가 h2 에 20/26 !important — 크기는 안쪽 span 이 갖는다
    pills = [dk.pill(dk.ISSUE_KO.get(post.get("cat"), "그 밖"), "area", bare=True),
             dk.pill(dk.DIR_KO.get(DIR_KIND.get(post.get("direction"), "neutral")), DIR_KIND.get(post.get("direction"), "neutral"), bare=True)]
    if post.get("stage") in STAGE_KO:
        pills.append(dk.pill(STAGE_KO[post["stage"]], "neutral", bare=True))
    body.append(f'<p style="margin:0 0 18px;padding:0 0 0 {dk.ALIGN_PX}px;line-height:1;">{dk.pill_row("".join(pills))}</p>')
    summary = (post.get("summary") or "").strip() or _first_sentence(post.get("body"))
    body.append(f'<div style="background:{th["card"]};border-radius:10px;padding:{23 - dk.VP}px 19px;margin:0 0 26px;">'
                f'<p data-seo-lead="1" data-lead="1" style="margin:0;word-break:keep-all;font-weight:700;color:#111;">{prose(SR.emph(summary, False), False)}</p></div>')
    for p in _paras(post.get("body")):
        body.append(SR.para(prose(p)))
    body.append(market_section(market, lists, th["solid"]))
    rel = []
    first = next((s for s in market.get("stocks") or []), None)
    if first and lists.get(first["ticker"], {}).get("u"):
        rel.append((f'{first["name"]} 종목 페이지', BLOG.rstrip("/") + lists[first["ticker"]]["u"]))
    rel += [("한국 증시 리포트", KR_REPORT), (f"지난 {NAME}", f"{BLOG}search/label/{LABEL_Q}")]
    body.append(dk.related_buttons(rel))
    html = dk.WRAP_OPEN + dk.fix_colons("".join(body)) + dk.WRAP_CLOSE
    return stored, html, {"labels": [NAME], "slug": post.get("slug"), "basis": market.get("basis"), "linked": sorted(link.seen)}


# ── 한국 기사 제목 묶음 (요청 10 · 11절 headlines) — 미국 뉴스와 같은 묶음 꼴 ──
def _hm(iso):
    return f"{int(iso[5:7])}.{iso[8:10]} {iso[11:16]}" if iso and len(iso) >= 16 else ""


def headline_bundles(docs, day):
    """headlines 문서들(그날 실행 여럿) → 묶음 목록. url 로 겹친 것을 빼고(가벼운 회차 · 16:30 회차 겹침, Q12), 같은 event 끼리 2 ~ 4줄 묶음.
    한 줄뿐인 사건은 기사 한 줄(원문 링크). 최근 시각부터. 버리는 것 없음 — 화면은 5개 + 더 보기."""
    seen, ev = set(), {}
    for doc in docs:
        for it in doc.get("items") or []:
            u = it.get("url")
            at = it.get("publishedAt") or it.get("foundAt") or ""
            if not u or u in seen or not at.startswith(day):
                continue
            seen.add(u)
            ev.setdefault(it.get("event") or it.get("title"), []).append(dict(it, at=at))
    out = []
    for name, rows in ev.items():
        rows.sort(key=lambda r: r["at"])
        sizes = dk.bundle_sizes(len(rows)) or [1]
        i = 0
        for n in sizes:
            part, i = rows[i:i + n], i + n
            out.append({"event": name, "rows": part, "at": max(r["at"] for r in part), "cat": part[0].get("cat")})
    out.sort(key=lambda b: b["at"], reverse=True)
    return out


def headline_item(b, k):
    rows = b["rows"]
    outlets = list(dict.fromkeys(r.get("outlet") for r in rows if r.get("outlet")))
    src = (outlets[0] + (f" 외 {len(outlets) - 1}곳" if len(outlets) > 1 else "")) if outlets else ""
    labels = dk.pill(dk.ISSUE_KO.get(b.get("cat"), "그 밖"), "area") if b.get("cat") else ""
    head = dk.esc(rows[0]["title"])
    if len(rows) == 1:
        return dk.news_item(head, rows[0]["url"], "", (), labels, [_hm(b["at"]), src], ' data-trhelp="skip"')
    inner = dk.news_item(head, None, rows[1]["title"], (), labels, [_hm(b["at"]), src])
    pid = dk.news_pop_id("kh", f'{b["event"]}:{k}')
    return dk.news_pop_wrap(inner, pid) + dk.bundle_pop_body(pid, rows[0]["title"], [{"line": r["title"], "source": r.get("outlet"), "url": r["url"]} for r in rows])


def headlines_section(docs, day, title="한국 주요 뉴스"):
    bs = headline_bundles(docs, day)
    if not bs:
        return dk.section(title, dk.muted("오늘은 아직 들어온 한국 기사가 없습니다."))
    return dk.section(title, dk.more_list([headline_item(b, k) for k, b in enumerate(bs)], noun="뉴스"))
