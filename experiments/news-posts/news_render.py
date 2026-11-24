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
import datetime
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
NAME = "Newfact 주요 기사"   # 글 이름 = 제목 줄 (요청 12 · 14절)
LABEL = "Newfact 뉴스"   # 연재 라벨 = 지난 글 목록 (2026-11-24 사용자 결정 — 제목 줄 이름과 따로)
LABEL_Q = "Newfact%20%EB%89%B4%EC%8A%A4"
KR_REPORT = f"{BLOG}search/label/%ED%95%9C%EA%B5%AD%20%EC%A6%9D%EC%8B%9C%20%EB%A6%AC%ED%8F%AC%ED%8A%B8"
DIR_KIND = {"up": "positive", "down": "negative", "neutral": "neutral"}
STAGE_KO = {"confirmed": "확정", "discussing": "논의 중"}   # 화면에 싣지 않는다 — 단계 라벨 뺌 (2026-11-23 사용자 "확정 라벨은 빼"). 라벨 = 분야 · 방향 둘
USUAL_N = 60   # 평소 움직임 = 직전 60거래일 하루 등락 폭(절댓값)의 중앙값
INDEX = [("^KS11", "코스피"), ("^KQ11", "코스닥")]
US_INDEX = [("^GSPC", "S&P 500"), ("^IXIC", "나스닥")]   # 미국 종목이 있을 때만 — 미국 종목의 비교 대상 = S&P 500 (같은 시장 전체, 2026-11-23 사용자 "미국 종목도 싣게")


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


def match_stocks(post, lists):
    """수집기 stocks → [(ticker, name, "kr" | "us")]. 한국 = 코드 · 이름이 블로그 한국 목록과 모두 맞을 때(요청 8절 Q9).
    미국 = 수집기가 코드를 비워 보내므로(6자리만 받음) 이름이 블로그 미국 목록의 한글 이름과 똑같을 때만(2026-11-23 사용자). 목록에 없는 종목은 싣지 않는다."""
    by_name = {r["n"]: t for t, r in lists.items() if r.get("mk") == "us"}
    out, seen = [], set()
    for st in post.get("stocks") or []:
        code, name = str(st.get("code") or ""), (st.get("name") or "").strip()
        row = lists.get(code)
        if re.fullmatch(r"\d{6}", code) and row and row.get("n") == name:
            hit = (code, name, "kr")
        elif name in by_name:
            hit = (by_name[name], name, "us")
        else:
            continue
        if hit[0] not in seen:
            seen.add(hit[0])
            out.append(hit)
    return out


THEME_PAT = {   # 테마 이름(블로그 _lists.json themes) → 글 낱말 (기획 3-3 ②, 2026-11-23 다시 살림 — 11-22 목업의 관련 종목 25개)
    "kr": {"반도체": r"반도체|메모리|HBM|D램|디램|낸드|파운드리",
           "2차전지": r"2차 ?전지|이차 ?전지|배터리|양극재|음극재|전기차",
           "바이오": r"바이오|제약|신약|임상",
           "방산·조선·원전": r"방산|방위 ?산업|조선|선박|원전|원자력|SMR"},
    "us": {"AI 칩": r"AI ?(칩|반도체)|GPU|엔비디아|가속기",
           "메모리": r"메모리|HBM|D램|디램|낸드",
           "칩 생산": r"파운드리|TSMC|위탁 ?생산",
           "반도체 장비": r"반도체 ?장비|노광|ASML",
           "데이터 센터": r"데이터 ?센터",
           "우주항공": r"우주|위성|발사체|항공우주",
           "가상자산": r"비트코인|가상 ?자산|암호 ?화폐|코인",
           "에너지": r"유가|원유|천연가스|정유",
           "양자 컴퓨터": r"양자",
           "하이퍼스케일러": r"클라우드|하이퍼스케일러|빅테크|오픈AI|앤트로픽|구글|마이크로소프트|아마존|메타"},
}


def _text(post):
    return " ".join(str(post.get(k) or "") for k in ("title", "summary", "body", "sector"))


NAME_STOP = {"나스닥", "코스피", "코스닥", "다우존스"}   # 지수 · 시장 이름과 같은 종목(나스닥 Inc. NDAQ) — 글의 `나스닥 시장` 에 걸리던 것


def related_stocks(post, lists, themes=None):
    """→ [(ticker, name, mk, why)] 관련 종목 전부(자르지 않음 — 화면은 5개 + 더 보기). why = "기사" | 테마 이름.
    ① 수집기 stocks(match_stocks) ② 글에 이름이 그대로 나온 블로그 종목(한글 이름 3글자 이상 — `기아` 같은 두 글자는 낱말 속에서 잘못 걸려 뺀다)
    ③ 글 낱말이 테마에 걸리면 그 테마 구성 종목(한국 · 미국). 블로그 목록에 있는 종목만."""
    text = _text(post)
    out, seen = [], set()

    def add(t, why):
        r = lists.get(t)
        if r and t not in seen:
            seen.add(t)
            out.append((t, r["n"], r.get("mk") or ("kr" if re.fullmatch(r"\d{6}", t) else "us"), why))
    for t, _, _ in match_stocks(post, lists):
        add(t, "기사")
    for t, r in sorted(lists.items(), key=lambda kv: -(kv[1].get("c") or 0)):
        n = r.get("n") or ""
        if len(n) >= 3 and n not in NAME_STOP and n in text:
            add(t, "기사")
    for mk, pats in THEME_PAT.items():
        for name, members in (themes or {}).get(mk, []):
            pat = pats.get(name)
            if pat and re.search(pat, text, re.I):
                for t in members:
                    add(t, name)
    return out


def us_day(post_date, now_kst):
    """미국 종목 기준일 = 한국 날짜로 글 날짜까지 마감한 마지막 미국 거래일. 미국 D일 종가는 한국 D+1일 아침(06:30 뒤 확정으로 본다)에 나온다(날짜 = 한국 시간 하나로)."""
    ready = now_kst.date() if now_kst.hour * 60 + now_kst.minute >= 6 * 60 + 30 else now_kst.date() - datetime.timedelta(days=1)
    last = min(datetime.date.fromisoformat(post_date), ready)
    return str(last - datetime.timedelta(days=1))


def _close_kst(us_d):
    return str(datetime.date.fromisoformat(us_d) + datetime.timedelta(days=1))


def _indices(pairs, closes_of, day):
    out = []
    for sym, name in pairs:
        cl = closes_of(sym)
        m = _move(cl, day) if cl else None
        if m:
            out.append({"name": name, "day": m["day"], "close": next(v for d, v in cl if d == m["day"]), "chg_pct": m["chg"], "usual": m["usual"]})
    return out


def same_day(post, lists, closes_of, closed_through, now_kst=None, themes=None):
    """→ market = {"basis", "indices", "us_basis", "us_indices", "stocks": [{ticker, name, mk, chg_pct, usual, base, vs}]}.
    closes_of(symbol) → [(날짜, 종가)]. closed_through = 한국 마감이 끝난 마지막 날(장중 값은 쓰지 않는다).
    종목 = match_stocks. 비교 대상(헌법 제1조) = 한국 종목은 코스피, 미국 종목은 S&P 500 — 같은 시장 전체 · 같은 날."""
    now_kst = now_kst or datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    day = min(post["date"], closed_through)
    out = {"indices": _indices(INDEX, closes_of, day), "us_indices": [], "stocks": []}
    out["basis"] = out["indices"][0]["day"] if out["indices"] else None
    k = next((x["chg_pct"] for x in out["indices"] if x["name"] == "코스피"), None)
    hits = related_stocks(post, lists, themes)
    if any(h[2] == "us" for h in hits):
        out["us_indices"] = _indices(US_INDEX, closes_of, us_day(post["date"], now_kst))
        out["us_basis"] = out["us_indices"][0]["day"] if out["us_indices"] else None
    spx = next((x["chg_pct"] for x in out["us_indices"] if x["name"] == "S&P 500"), None)
    for t, name, mk, why in hits:
        cl = closes_of(kr_symbol(t) if mk == "kr" else t)
        basis, base, bchg = (out.get("basis"), "코스피", k) if mk == "kr" else (out.get("us_basis"), "S&P 500", spx)
        m = _move(cl, basis) if cl and basis else None
        if not m or m["day"] != basis:
            continue
        out["stocks"].append({"ticker": t, "name": name, "mk": mk, "why": why, "chg_pct": m["chg"], "usual": m["usual"], "base": base,
                              "vs": round(m["chg"] - bchg, 2) if bchg is not None else None, "base_chg": bchg})
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


def _cmp_line(x):
    """종목 줄 아래 회색 한 줄 = 비교 두 개 (헌법 제1조): `코스피보다 0.32%p 더 · 평소 하루 1.6%의 1.4배` (미국 종목은 S&P 500). 인과 말은 넣지 않는다 (요청 Q10)."""
    bits = []
    b, kospi = x.get("base") or "코스피", x.get("base_chg")
    wa = b + ("과" if b.endswith("500") else "와")   # S&P 500(오백)과 · 코스피와
    if x.get("vs") is not None and kospi is not None:
        v, c = x["vs"], x["chg_pct"]
        if abs(v) < 0.005:
            bits.append(f"{wa} 같은 폭")
        elif c * kospi < 0:   # 방향이 반대인 날
            bits.append(f'{wa} 반대로 {"오름" if c > 0 else "내림"}')
        elif c >= 0 and kospi >= 0:
            bits.append(f'{b}보다 {_pct(v, "%p")} {"더" if v > 0 else "덜"} 오름')
        else:
            bits.append(f'{b}보다 {_pct(v, "%p")} {"더" if v < 0 else "덜"} 내림')
    if x.get("usual"):
        r = abs(x["chg_pct"]) / x["usual"] if x["usual"] else 0
        bits.append(f'평소 하루 움직임({_pct(x["usual"])})' + (f"의 {r:.1f}배" if r >= 1.5 else "과 비슷" if r >= 0.5 else "보다 작음"))
    return bits   # 줄마다 한 비교 — 화면은 줄바꿈으로 (2026-11-23 사용자)


def _md(d):
    return f"{int(d[5:7])}.{d[8:10]}"


def _idx_card(cells_src):
    """지수 칸 = 카드 하나를 넷(2 × 2)으로 — 코스피 · 코스닥 / S&P 500 · 나스닥 (2026-11-23 사용자 "하나의 카드로 4등분"). 한국만이면 한 줄 둘.
    칸 꼴 = 시황 해설 지수 칸(SR.index_row)과 같은 이름 · 종가 · 증감."""
    cells = []
    for x in cells_src:
        if x.get("close") is None or x.get("chg_pct") is None:
            continue
        ink = dk.UP if x["chg_pct"] > 0 else dk.DOWN if x["chg_pct"] < 0 else "#111"
        cells.append(f'<span style="font-weight:700;color:#111;font-size:{dk.NAME};line-height:{dk.LH_CARD};white-space:nowrap;display:block;">{dk.paren(dk.esc(SR.INDEX_NAMES.get(x["name"], x["name"])))}</span>'
                     f'<span style="display:block;margin-top:4px;line-height:25px;white-space:nowrap;"><span style="font-size:{dk.NAME};color:{ink};">{x["close"]:,.2f}</span> '
                     f'<span style="font-size:{dk.CHG_SIZE};">{SR.chg(x["chg_pct"])}</span></span>')
    if not cells:
        return ""
    line = dk.card_line("neutral")
    pad = f"padding:{14 - dk.VP}px 12px;"
    inner = "".join(f'<span data-idx-cell="1" style="display:block;min-width:0;box-sizing:border-box;background:#fff;{pad}'
                    f'{"" if k % 2 == 0 else f"border-left:1px solid {line};"}{"" if k < 2 else f"border-top:1px solid {line};"}">{c}</span>' for k, c in enumerate(cells))
    return (f'<div data-cards="1" style="margin:0 0 8px;"><span style="display:grid;grid-template-columns:1fr 1fr;border:1px solid {dk.CARD_DIR["neutral"][1]};'
            f'border-radius:8px;overflow:hidden;">{inner}</span></div>')


STOCKS_SHOWN = 2   # 관련 종목 = 2개 펼침 + 카드 안 더 보기 (2026-11-23 사용자 "페이지를 길게 만들지 마", 옛 5)
WHITE_BOX = "display:block;background:#fff;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;"


def market_section(market, lists, ink):
    idx, us_idx = market.get("indices") or [], market.get("us_indices") or []
    if not idx and not us_idx:
        return ""
    inner = _idx_card(idx + us_idx)   # 비교 기준 지수 — 미국 두 칸은 미국 종목이 있을 때만
    stocks = market.get("stocks") or []
    if stocks:
        rows = []
        for i, x in enumerate(stocks):
            r = SR.stock_row(x, lists.get(x["ticker"]), "am" if x.get("mk") == "us" else "pm", i in (0, STOCKS_SHOWN))   # 미국 = 달러 · 티커 · 업종
            line = _cmp_line(x)
            if line:
                r = r.replace(f"padding:{SR.LIST_ROW_PAD}px 12px;", f"padding:{SR.LIST_ROW_PAD}px 12px 6px;", 1)
                r += (f'<span style="display:block;padding:0 12px {SR.LIST_ROW_PAD}px {12 + SR.LOGO_Z + SR.LOGO_GAP}px;font-size:{dk.TINY};line-height:{dk.LH_TINY};'
                      f'color:#6B7280;word-break:keep-all;">{"<br>".join(dk.esc(x) for x in line)}</span>')
            rows.append(r)
        if len(rows) > STOCKS_SHOWN:   # 전부 싣고 접기 — 버튼은 카드 안 맨 아래 줄(dk.fold_card, `관련 종목 n개 더 보기 ⌄`)
            inner += dk.fold_card("".join(rows[:STOCKS_SHOWN]), "".join(rows[STOCKS_SHOWN:]), f"관련 종목 {len(rows) - STOCKS_SHOWN}개 더 보기", box=WHITE_BOX)
        else:
            inner += SR.white_card("".join(rows))
    # 기준일 = 제목 줄 오른쪽 작은 회색 (2026-11-24 사용자 "오전 기사는 우측에 기준일 표시하고 나가, 오후 때 다시 갱신") — 아침 글은 전 거래일, 장 마감 뒤 발행기(publish_news refresh)가 그날 값으로 고친다
    b, ub = market.get("basis") or "", market.get("us_basis") or ""
    if b and ub:
        note = f"한국 {_md(b)} · 미국 {_md(_close_kst(ub))} 아침 종가 기준"
    elif b:
        note = f"{_md(b)} 종가 기준"
    elif ub:
        note = f"미국 {_md(_close_kst(ub))} 아침 종가 기준"
    else:
        note = ""
    aside = (f'<span data-basis="{dk.esc(b)}" style="margin-left:auto;font-size:13px;line-height:19px;font-weight:400;color:#6B7280;white-space:nowrap;">'
             f'{dk.esc(note)}</span>') if note else ""
    sec = dk.section("관련 종목" if stocks else "같은 날 지수", inner, line=False, aside=aside)   # 이름 = 관련 종목 (기획 3-3, 수혜주 X)
    sec = SR.tinted(SR.iconed(sec, dk.solid_icon("bars", ink, size=20)), ink).replace(f"margin:{SR.H2_TOP}px 0 11px;", f"margin:{SR.BIG_TOP}px 0 11px;", 1)
    return sec.replace("font-size:22px;font-weight:700;line-height:28px;", f"font-size:{dk.NAME};font-weight:700;line-height:{dk.LH_CARD};", 1)   # 제목 = 지수 칸 이름(코스피) 크기 16/24 (2026-11-23 사용자 "공간 효율")


ISSUE_PAT = {"IRAN": r"이란|호르무즈", "TARIFF": r"관세(?!청)|무역 ?전쟁", "EXPORT": r"수출 ?통제|거래 제한 명단",
             "NVDA_CEO": r"젠슨 ?황|엔비디아 (CEO|최고경영자)"}   # Hot Issue 열쇠(이슈 페이지 mock_issue_watch.ISSUES pat 의 한국어 쪽)
MARKET_CATS = {"MARKET_STRUCTURE", "RATES_FED", "FX_GLOBAL", "INFLATION", "GROWTH_JOBS", "FISCAL_POLITICS", "CREDIT_BANKS", "TARIFF_TRADE", "GEOPOLITICS"}   # 시장 전체 사건 → 한국 증시 전망


def follow_links(post, market, lists, issues=(), forecasts=()):
    """함께 보는 페이지에 싣는 연결 (기획 3-4 `이어서 보기`, 11-23 사용자: 따로 칸 없이 함께 보는 페이지로) — 기사에 이어지는 우리 서비스 전부, 맞는 것만(빈 칸 금지). 링크는 발행 때 박는다(방문자 요청 0).
    종목 페이지(기사에 나온 종목) · Hot Issue(낱말) · 증시 전망(기사 종목 이름이 걸린 전망, 시장 전체 사건이면 한국 전망) · 테마(종목 모아보기) · 지난 기사."""
    text = _text(post)
    out = []
    for x in market.get("stocks") or []:
        r = lists.get(x["ticker"]) or {}
        if x.get("why") == "기사" and r.get("u"):
            out.append((f'{x["name"]} 종목 페이지', BLOG.rstrip("/") + r["u"]))
    for it in issues:
        pat = ISSUE_PAT.get(it.get("id"))
        if pat and re.search(pat, text, re.I):
            out.append((f'Hot Issue · {it.get("q") or it.get("name")}', BLOG.rstrip("/") + it["url"] if it["url"].startswith("/") else it["url"]))
    names = [x["name"] for x in market.get("stocks") or [] if x.get("why") == "기사"]
    for f in forecasts:
        hit = any(n and n in (f.get("event") or "") + (f.get("title") or "") for n in names)
        if hit or (post.get("cat") in MARKET_CATS and f.get("market") == "kr" and "종목" not in " ".join(f.get("tags") or [])):
            out.append((f'증시 전망 · {f["title"]}', f["url"]))
    if post.get("cat") in MARKET_CATS:
        out.append(("증시 전망 · 지금 지켜보는 전망 전부", f"{BLOG}p/forecast-list.html"))
    for th in dict.fromkeys(x["why"] for x in market.get("stocks") or [] if x.get("why") not in (None, "기사")):
        out.append((f"테마 · {th} 종목 모아보기", f"{BLOG}p/stock-lists.html"))
    seen, uniq = set(), []
    for t, u in out:
        if u not in seen or t.startswith("테마"):
            seen.add(u)
            uniq.append((t, u))
    return uniq


def titles(post):
    """(제목 줄, 저장 제목) — 테마가 저장 제목의 ` : ` 앞만 제목 줄에 보여 준다(시황 해설과 같은 장치, 본문에 [data-headline] 이 있을 때)."""
    return NAME, f"{NAME} : {post['title'].strip()}"


def render(post, market, lists=None, issues=(), forecasts=()):
    """lists = 한국 · 미국 목록을 합친 {티커: 행(mk = kr | us)}. → (저장 제목, 본문 HTML, meta). summary 가 비면 본문 첫 문장(요청 12절 대체 규칙). 종목이 안 맞으면 지수만."""
    lists = lists or {}
    th = SR.MOOD_THEME["flat"]   # 글 전체 = 보라 테마 하나 (2026-11-23 사용자 "전체적으로 보라색") — 기사 방향으로 색을 바꾸지 않는다(방향은 라벨이 말한다)
    ink = th["ink"]
    col = {"tickers": [x["ticker"] for x in market.get("stocks") or [] if x.get("why") == "기사"]}
    link = SR.Linker(col, {"close": {"movers": [{"name": lists[c]["n"], "ticker": c} for c in col["tickers"]]}}, ink)

    def prose(text, strong=True):
        return SR.who(SR.emph(link(SR.directional(dk.tint(dk.esc(dk.formal(text or ""))))), strong, ink))

    _, stored = titles(post)
    y, m, d = post["date"].split("-")
    style = ('<style>body:has([data-headline]) .pr-sticky{border-bottom:0;margin-bottom:0;}</style>')
    body = [style + f'<p data-title-basis="1" data-news-post="{dk.esc(post.get("slug") or "")}" data-news-date="{dk.esc(post["date"])}" data-post-id="{dk.esc(post.get("id") or "")}" style="margin:0 0 14px;font-size:13px;line-height:19px;color:#6B7280;">{int(m)}.{d} 기사</p>']
    body.append(f'<h2 data-headline="1" style="margin:0 0 14px;padding:25px 0 0 {dk.ALIGN_PX}px;font-size:26px;line-height:38px;font-weight:700;color:#111;word-break:keep-all;">'
                f'<span style="display:block;font-size:26px;line-height:38px;">{SR.emph(dk.esc(post["title"]), False)}</span></h2>')   # 폰 테마가 h2 에 20/26 !important — 크기는 안쪽 span 이 갖는다
    pills = [dk.pill(dk.ISSUE_KO.get(post.get("cat"), "그 밖"), "area", bare=True),
             dk.pill(dk.DIR_KO.get(DIR_KIND.get(post.get("direction"), "neutral")) + "적", DIR_KIND.get(post.get("direction"), "neutral"), bare=True)]   # 상세 = 긍정적 · 부정적 · 중립적 (2026-11-23 사용자, 목록 라벨은 두 글자 그대로)
    body.append(f'<p style="margin:0 0 18px;padding:0 0 0 {dk.ALIGN_PX}px;line-height:1;display:flex;justify-content:flex-end;">{dk.pill_row("".join(pills))}</p>')   # 라벨 = 오른쪽 정렬 (2026-11-23 사용자)
    summary = (post.get("summary") or "").strip() or _first_sentence(post.get("body"))
    body.append(f'<div style="background:{th["card"]};border-radius:10px;padding:{23 - dk.VP}px 19px;margin:0 0 26px;">'
                f'<p data-seo-lead="1" data-lead="1" style="margin:0;word-break:keep-all;font-weight:700;color:#111;">{prose(SR.emph(summary, False), False)}</p></div>')
    for p in _paras(post.get("body")):
        body.append(SR.para(prose(p)))
    body.append(market_section(market, lists, th["solid"]))
    rel = follow_links(post, market, lists, issues, forecasts)   # 이어서 보기 칸을 따로 두지 않고 함께 보는 페이지에 합친다 (2026-11-23 사용자)
    rel += [("한국 증시 리포트", KR_REPORT), (f"지난 {LABEL}", f"{BLOG}search/label/{LABEL_Q}")]
    body.append(f'<div data-related="1" data-related-all="1" style="margin-top:49px;">{dk.related_title("함께 보는 페이지")}{dk.related_rows(rel)}</div>')   # 이 글만 3줄 상한 없이(테마도 data-related-all 은 안 자름) — 연결되는 서비스 전부
    html = dk.WRAP_OPEN + dk.fix_colons("".join(body)) + dk.WRAP_CLOSE
    return stored, html, {"labels": [LABEL], "slug": post.get("slug"), "basis": market.get("basis"), "linked": sorted(link.seen)}


# ── 한국 기사 제목 묶음 (요청 10 · 11절 headlines) — 미국 뉴스와 같은 묶음 꼴 ──
def _hm(iso):
    return f"{int(iso[5:7])}.{iso[8:10]} {iso[11:16]}" if iso and len(iso) >= 16 else ""


def _title_key(t):
    return re.sub(r"[^가-힣A-Za-z0-9]", "", re.sub(r"\[[^\]]*\]|\([^)]*\)", "", str(t or "")))


def headline_bundles(docs, day):
    """headlines 문서들(그날 실행 여럿) → 묶음 목록. url 로 겹친 것을 빼고(가벼운 회차 · 16:30 회차 겹침, Q12), 같은 event 끼리 2 ~ 4줄 묶음.
    한 줄뿐인 사건은 기사 한 줄(원문 링크). 최근 시각부터. 버리는 것 없음 — 화면은 5개 + 더 보기."""
    import difflib
    seen, ev, titles = set(), {}, []
    for doc in docs:
        for it in sorted(doc.get("items") or [], key=lambda x: str(x.get("publishedAt") or x.get("foundAt") or "")):
            u = it.get("url")
            at = it.get("publishedAt") or it.get("foundAt") or ""
            if not u or u in seen or not at.startswith(day):
                continue
            seen.add(u)
            # 같은 제목은 하나만 (2026-11-24 사용자 "같은 제목의 기사는 하나만 — 상식") — 괄호 머리말 · 띄어쓰기 · 문장부호를 빼고 85% 이상 같으면 먼저 나온 것만.
            # 수집기 sourceCount 의 `제목 85% 이상 같은 기사는 한 곳`(요청 16절)과 같은 기준. 주소만 다른 같은 기사(YTN 두 번)가 두 줄로 나오던 것
            t = _title_key(it.get("title"))
            if t and any(t == x or difflib.SequenceMatcher(None, t, x).ratio() >= 0.85 for x in titles):
                continue
            titles.append(t)
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


# ── 사건별 사실 층 (요청 15 · 16절, 2026-11-23 사용자 "오늘자 사실로 시안") ──
# 같은 날 facts 문서 중 가장 늦은 실행의 문서(part 여럿)만 쓴다. 2곳 이상이 보도한 사건만 사실로 싣고,
# 사실 한 줄은 `sources` 2 이상만(R22 — 수집기 ca7a6b8 전 자료는 사실마다 1이라 사건 기준만 쓴다: fact_min=1).
# 비교 대상(헌법 제1조) = 보도한 곳 수. 발언은 verified · 익명 아님만 인용. 같은 event 제목 묶음은 팝업 `원문 보기` 로.
FACTS_MIN_SOURCES = 2


def fact_events(fact_docs, min_sources=FACTS_MIN_SOURCES):
    seen, out = set(), []
    last = max((str(d.get("run")) for d in fact_docs), key=lambda r: max(str(d.get("createdAt") or "") for d in fact_docs if str(d.get("run")) == r), default=None)
    for doc in [d for d in fact_docs if str(d.get("run")) == last]:   # 그날 가장 늦은 실행만 — ⑤ 는 지난 36시간을 다시 묶어 앞 실행을 다 담는다(사건 이름이 실행마다 달라 합치면 겹침)
        for e in doc.get("events") or []:
            if e.get("event") in seen or (e.get("sourceCount") or 0) < min_sources:
                continue
            seen.add(e.get("event"))
            out.append(dict(e, at=str(doc.get("createdAt") or "")))
    out.sort(key=lambda e: e["at"], reverse=True)
    out.sort(key=lambda e: -(e.get("sourceCount") or 0))   # 많이 보도된 순, 같으면 늦은 실행 먼저
    return out


def fact_parts(f):
    """사실 한 줄 = (글, 출처). 글 = what + 확인된 발언(따옴표), 출처 = 말한 사람 직함 · 자리 · 출처 기관(정부 발표 · 공시 …).
    출처는 괄호로 붙이지 않고 팝업이 작은 회색 `- 출처` 로 그린다(발언자와 같은 꼴, 2026-11-24 사용자). kr_facts_store.fact_parts 와 같은 규칙."""
    line = (f.get("what") or "").strip()
    by = []
    q = f.get("quote") or {}
    if q.get("verified") and not q.get("anonymous") and q.get("text"):
        line += f' "{q["text"]}"'
        who = " ".join(x for x in (q.get("speaker"), q.get("title")) if x)
        if who:
            by.append(who + (f", {q['venue']}" if q.get("venue") else ""))
    src = (f.get("origin") or "").strip()
    if src and src not in line and not any(src in b for b in by):
        by.append(src)
    return line, " · ".join(by)


def fact_item(e, k, rows_by_event, fact_min=FACTS_MIN_SOURCES):
    facts = [f for f in e.get("facts") or [] if (f.get("sources") or 1) >= fact_min] or []
    if not facts:
        return ""
    d = DIR_KIND.get(e.get("direction"), "neutral")
    labels = dk.pill(dk.ISSUE_KO.get(e.get("cat"), "그 밖"), "area") + dk.pill(dk.DIR_KO.get(d), d)
    meta = [f'보도 {e.get("sourceCount")}곳']   # `사실 n개` 는 뺌 (2026-11-24 사용자)
    inner = dk.news_item(dk.esc(e["event"]), None, facts[0]["what"], (), labels, meta)
    pid = dk.news_pop_id("kf", f'{e["event"]}:{k}')
    rows = [{"line": e["event"]}] + [dict(zip(("line", "by"), fact_parts(f))) for f in facts]
    # `원문 보기` 는 달지 않는다 (2026-11-24 사용자) — 사건 이름이 맞는 기사만 이어져 9곳 보도에 1곳만 출처처럼 보였다. 근거 = `보도 n곳` · 줄 끝 발표 주체(- 정부 발표)
    body = dk.bundle_pop_body(pid, e["event"], [r for r in rows if r.get("line") or r.get("url")])
    return dk.news_pop_wrap(inner, pid) + body


def facts_section(fact_docs, head_docs, day, title="한국 주요 뉴스", fact_min=FACTS_MIN_SOURCES, tab=None):
    """위 = 사실로 정리된 사건(보도 2곳 이상, 많이 보도된 순) · 아래 = 그 밖의 기사 제목 묶음(사실 층에 들어간 사건 제목은 원문 보기로 옮겨 빼고).
    둘 다 전부 싣고 5개 + 더 보기."""
    evs = fact_events(fact_docs)
    by_ev = {}
    for b in headline_bundles(head_docs, day):
        by_ev.setdefault(b["event"], []).extend(b["rows"])
    items = [x for x in (fact_item(e, k, by_ev, fact_min) for k, e in enumerate(evs)) if x]
    used = {e["event"] for e in evs}
    rest = [b for b in headline_bundles(head_docs, day) if b["event"] not in used]
    top = dk.section(title, dk.more_list(items, noun="사건") if items else dk.muted("오늘은 아직 2곳 이상이 보도한 사건이 없습니다."), tab=tab)
    low = dk.section("그 밖의 기사", dk.more_list([headline_item(b, k) for k, b in enumerate(rest)], noun="뉴스"), tab=tab) if rest else ""
    return top + low
