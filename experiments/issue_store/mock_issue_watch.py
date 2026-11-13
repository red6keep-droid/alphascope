"""이슈 모니터링 목업 (2026-11-13 사용자: "이슈 모니터링으로 별도 페이지 — 평소 계속 지켜보다가 주식이 선반영되는 낌새가 보이면 포착, 동향 파악").

    python experiments/issue_store/mock_issue_watch.py   → output/mock_issue_watch.html

예측판이 아니라 동향판 — 사실 세 가지만 매일 적는다:
  ① 얼마나 화제인가 = 이 이슈 기사 수 (공용 뉴스 처리 news_store_home.json + 종목 레이더 뉴스, signal_standby.load_news)
  ② 시장이 먼저 움직이나 = 사슬 사전(chains.CEASEFIRE) 고리 지표의 10거래일 움직임 · 평소의 몇 배(signal_scan 과 같은 셈)
  ③ 이렇게 되면 = 사슬 갈림점 + 사건표(events_curated.csv) 같은 종류 사례의 당일 · 20거래일 뒤 실제 움직임
검증 3-a(기획 8-19): 전쟁 · 지정학은 가격이 미리 움직이지 않았다(7~8건, 가설) → 화면은 "포착했다" 를 말하지 않는다.
이슈 = 키워드 묶음(ISSUES). signal_standby 의 주제 정규식은 이란 기사 대부분을 놓쳐서(11-10 `긴장 완화 기대` 등) 이슈는 이름으로 모으고, 기사마다 쪽(종전 · 확전 · 미정)을 붙인다.
쪽 · 단계는 목업에선 글 패턴 — 운영 땐 공용 뉴스 처리(Groq, 이미 도는 호출)의 칸으로 옮길지 정한다. AI 0 · 새 수집 0 · 블로그에 안 나감.
"""
import datetime as dt
import json
import os
import re
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))
import chains as CH  # noqa: E402
import design_kit as dk  # noqa: E402
import hypo_pages as H  # noqa: E402
import signal_standby as SB  # noqa: E402
import cards as qc  # noqa: E402  — 질문 카드(강조 카드 + 접기, 가이드라인 2-7) · hypo_pages 가 daily-report 를 경로에 넣는다

OUT = os.path.join(_HERE, "output")
KST = dt.timezone(dt.timedelta(hours=9))
RULES = "IW-2026-11-13a (목업)"

# 지켜보는 이슈 — 키워드로 모은다. by = 자동(뉴스가 평소 2배) · 운영자(직접 추가)
ISSUES = [
    {"id": "IRAN", "name": "이란 전쟁", "q": "이란 전쟁, 끝나면 시장은?", "by": "운영자",
     "pat": r"이란|Iran|호르무즈|Hormuz|게심|Qeshm", "chain": "CEASEFIRE", "cases": ("휴전 · 종전",),
     "gq": "이란 전쟁 OR 이란 휴전 OR 이란 종전 OR 호르무즈"},
    {"id": "TARIFF", "name": "관세", "q": "관세, 다시 오르나?", "by": "자동", "pat": r"관세(?!청)|tariff|무역 ?전쟁|trade war", "chain": "TARIFF", "gq": "트럼프 관세 OR 상호 관세 OR 관세 협상"},
    {"id": "EXPORT", "name": "반도체 수출 통제", "q": "반도체 수출 통제, 넓어지나?", "by": "자동",
     "pat": r"수출 ?통제|export control|chip (ban|export)|거래 제한 명단|entity list", "chain": "REGULATION", "gq": "반도체 수출 통제 OR 수출 통제 엔비디아"},
]
# 기사 쪽 — 위에서부터 먼저 맞는 것 (종전 쪽 · 확전 쪽 · 방향 미정)
SIDE_PAT = [
    ("멀어짐", r"필요 ?없|불필요|교착|희망 적|결렬|거부|황당"),   # 협상이 멀어지는 말은 확전 쪽보다 먼저
    ("종전", r"휴전|종전|평화|끝날|끝나|마무리|종식|긴장 완화|완화 기대|협상 진전|진전 시|합의|ceasefire|truce|peace|de-?escalat"),
    ("확전", r"공격|타격|공습|미사일|위협|확전|제재|일촉즉발|봉쇄|폭발|기뢰|피격|파괴|나포|격추|attack|strike|missile|escalat"),
]
SIDE_NAME = {"멀어짐": "확전", "종전": "종전", "확전": "확전"}
SIDE_KIND = {"종전": "positive", "확전": "negative", "방향 미정": "neutral"}   # 종전 = 시장에 좋은 쪽 빨강 · 확전 = 나쁜 쪽 파랑 — 증시 전망 `전망A · B` · 뉴스 긍정 · 부정과 같은 색 (2026-11-13 사용자)
def josa(w, pair):
    """받침에 맞춘 조사 — pair = ("은", "는") · ("이", "가")."""
    c = w.rstrip()[-1]
    has = "가" <= c <= "힣" and (ord(c) - 0xAC00) % 28 != 0
    return w + (pair[0] if has else pair[1])


def side_pill(side, pop=False):
    """쪽 라벨 — 종전쪽 빨강 · 확전쪽 파랑(뉴스 긍정 · 부정), 방향미정 = 증시 전망 `향방미정` 라벨과 같은 회색(바탕 #F8FAFC · 테두리 #E2E8F0, H.open_pill) (2026-11-13 사용자).
    pop = 팝업 줄 앞(flex 줄 안, H.news_pill)."""
    k = SIDE_KIND[side]
    if k == "neutral":
        bg, bd = dk.CARD_DIR["neutral"]
        if pop:
            return H.news_pill(SIDE_LABEL[side], (bg, bd, dk.PILL["neutral"][1]), inline=False)
        return H.open_pill().replace(f">{H.OPEN_TITLE}<", f">{SIDE_LABEL[side]}<", 1)
    if pop:
        return H.news_pill(SIDE_LABEL[side], (dk.PILL_BG.get(k, "#fff"), *dk.PILL[k]), inline=False)
    return dk.pill(SIDE_LABEL[side], k, bare=True)


SIDE_LABEL = {"종전": "종전", "확전": "확전", "방향 미정": "방향미정"}   # `쪽` 없이 — 증시 전망 `반등` · `지속` 과 같게 (2026-11-11 · 11-13 사용자)   # 라벨 글자는 띄어쓰기 없이 (가이드라인 8절, `논의중` · `시장예상` 과 같게)
TALK = re.compile(r"[“”\"]|선언|밝혀|말했|발언|검토|기대|희망|우려|위험|경고|가능|전망|분석|어떻게|맞설|which|could|would", re.I)

# 가격 — 사슬 고리 지표(yfinance) + 비교
LINK_SYM = {"CL_F": "CL=F", "_VIX": "^VIX", "XLK": "XLK", "EWY": "^KS11", "ITA": "ITA", "GC_F": "GC=F", "XLE": "XLE", "JETS": "JETS"}
LINK_NAME = {"CL_F": "유가 (WTI)", "_VIX": "변동성 지수 (VIX)", "XLK": "미국 기술 업종", "EWY": "코스피", "ITA": "미국 방산 업종",
             "GC_F": "금", "XLE": "미국 에너지 업종", "JETS": "미국 항공 업종"}
EXTRA_LINKS = [("에너지 업종 약세", "XLE", -1), ("항공 강세 (연료비 ↓)", "JETS", +1)]   # 공급 복귀 사슬(OIL_SUPPLY_RETURN)에서   # 공급 복귀 사슬에서 — 그림자 스캔 11-09 · 11-10 에 움직인 둘
CASE_COLS = [("유가", "CL=F"), ("S&P 500", "^GSPC"), ("한국 (EWY)", "EWY"), ("에너지", "XLE"), ("방산", "ITA")]
Z_CLEAR, Z_SOME, BASE = 2.0, 1.0, 60
# 지표 묶음 — 한 줄로 세면 서로 다른 이유(11-05 반도체 급락)로 움직인 주식이 유가 쪽 신호를 가린다 (2026-11-13 실측: 유가 쪽 3개 모두 종전 방향, 주식 쪽 3개 반대)
GROUPS = [("유가", ("CL_F", "XLE", "JETS")), ("주식", ("XLK", "EWY", "ITA")), ("안전 자산", ("_VIX", "GC_F"))]   # `쪽` 없이 (2026-11-13 사용자)


def news_rows(items, pat):
    rx = re.compile(pat, re.I)
    out = []
    for it in items:
        txt = " ".join(str(it.get(k) or "") for k in ("title", "title_ko", "fact", "fact_en"))
        t = SB._ts(it)
        if not t or not rx.search(txt):
            continue
        side = "방향 미정"
        for nm, p in SIDE_PAT:
            if re.search(p, txt, re.I):
                side = SIDE_NAME[nm]
                break
        out.append({"t": t, "title": it.get("title_ko") or it.get("title") or "", "fact": it.get("fact") or "", "url": it.get("url"),
                    "src": it.get("source") or "", "gn": bool(it.get("_gn")), "side": side, "stage": "논의 · 발언" if TALK.search(txt) else "일어난 일", "issue": it.get("issue")})
    return sorted(out, key=lambda r: r["t"], reverse=True)


GN_CACHE = os.path.join(OUT, "_gnews_cache.json")   # 목업용 — 지난 날은 다시 안 받는다(운영은 이 페이지가 하루 두 번 받아 상태 브랜치에 쌓는다)
GN_CAP = 100   # 구글 뉴스 RSS 한 번 = 100건까지 — 닿은 날은 `100건 넘음` 으로 표시


def gnews(iss, days):
    """이슈 검색어로 구글 뉴스(한국어) — 하루씩 나눠 받는다(14일 한 번에 받으면 100건 상한에 앞날이 잘린다). 같은 주소 · 같은 제목은 하나만."""
    import requests, time, urllib.parse as U, xml.etree.ElementTree as ET, email.utils as eu
    cache = json.load(open(GN_CACHE, encoding="utf-8")) if os.path.exists(GN_CACHE) else {}
    today = days[-1]
    out, capped = [], set()
    for d in days:
        key = f'{iss["id"]}|{d}'
        if key not in cache or d >= (dt.date.fromisoformat(today) - dt.timedelta(days=1)).isoformat():
            d1 = (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()
            url = f'https://news.google.com/rss/search?q={U.quote(iss["gq"] + f" after:{d} before:{d1}")}&hl=ko&gl=KR&ceid=KR:ko'
            try:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
                its = ET.fromstring(r.content).findall(".//item")
                cache[key] = [{"title": i.findtext("title") or "", "url": i.findtext("link"), "src": i.findtext("source") or "",
                               "t": eu.parsedate_to_datetime(i.findtext("pubDate")).isoformat()} for i in its]
            except Exception as e:  # noqa: BLE001
                print(f"[gnews] {key} 못 받음: {type(e).__name__}")
                continue
            time.sleep(0.7)
        if len(cache.get(key, [])) >= GN_CAP:
            capped.add(d)
        out.extend(cache.get(key, []))
    os.makedirs(OUT, exist_ok=True)
    json.dump(cache, open(GN_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    items = []
    for x in out:
        title = re.sub(r"\s+-\s+[^-]+$", "", x["title"])   # 끝 `- 언론사` 떼기
        items.append({"title_ko": title, "title": title, "url": x["url"], "source": x["src"], "published_at": x["t"], "_gn": True})
    return items, capped


def merge_rows(*lists):
    """같은 주소 · 같은 제목(공백 · 기호 빼고 앞 24자)은 하나만 — 공용 뉴스(번역 · 요약 있음)를 먼저."""
    seen, out = set(), []
    for rs in lists:
        for r in rs:
            k1, k2 = r.get("url"), re.sub(r"[\W_]+", "", r["title"])[:24]
            if k1 in seen or k2 in seen:
                continue
            seen.update({k1, k2})
            out.append(r)
    return sorted(out, key=lambda r: r["t"], reverse=True)


def news_level(rows, at, base_days=28):
    """`at` 시각 기준 48시간 기사 수 · 평소(직전 28일의 48시간 평균) · 뉴스 늘어남."""
    n48 = sum(at - dt.timedelta(hours=48) < r["t"] <= at for r in rows)
    old = [r for r in rows if at - dt.timedelta(days=base_days) < r["t"] <= at - dt.timedelta(hours=48)]
    first = min((r["t"] for r in rows), default=at)
    span = max(1.0, (at - dt.timedelta(hours=48) - max(first, at - dt.timedelta(days=base_days))).total_seconds() / 172800)
    base = len(old) / span if old else None
    return n48, base, n48 >= 3 and n48 >= 2 * max(base or 0, 0.5)


def history(px, chain_id, rows, n=10):
    """지난 n 거래일 상태 — 그날 종가까지의 가격 · 그날 밤(KST 23시)까지의 뉴스로 다시 셈 (목업 = 거슬러 셈, 운영 = 날마다 기록)."""
    end = min(px[LINK_SYM[f]].dropna().index[-1] for _, f, _, *_ in CH.CHAINS[chain_id]["links"] if LINK_SYM.get(f) in px)
    cal = px["^GSPC"].dropna()
    cal = cal[cal.index <= end].index[-n:]
    out = []
    for d in cal:
        links = link_rows(px, chain_id, end=d)
        g = group_state(links)
        at = dt.datetime.combine((d + pd.Timedelta(days=1)).date(), dt.time(8, 0), tzinfo=KST)   # 뉴욕 종가 = 한국 다음 날 아침
        n48, base, hot = news_level(rows, at)
        st, _ = state_of(n48, base, g)
        out.append({"day": d.strftime("%Y-%m-%d"), "state": st, "n48": n48,
                    "groups": {gname: w for gname, w, *_ in g}})
    return out


def history_line(hist):
    """같은 상태가 이어진 날을 묶어 한 줄로 — `10.30 ~ 11.03 조용함 → 11.04 ~ 11.11 …`."""
    runs = []
    for h in hist:
        if runs and runs[-1][2] == h["state"]:
            runs[-1][1] = h["day"]
        else:
            runs.append([h["day"], h["day"], h["state"]])
    rows = []
    for a, b, st in runs:
        when = H.md(a) if a == b else f"{H.md(a)} ~ {H.md(b)}"
        kind = "uncertain" if "움직이는" in st or "늘고" in st else "area" if "조금" in st or "늘어남" in st else "neutral"
        rows.append((dk.esc(when), dk.esc(short(st)), "", None, True))
    return rows


SUM_URL = "https://raw.githubusercontent.com/red6keep-droid/alphascope/gh-pages/news_summaries_home.json"   # 홈 주요 뉴스 팝업 요약 다섯 줄 (fetch_news.SUM_FILE)


def _iid(link):
    import hashlib
    return hashlib.sha1(link.encode()).hexdigest()[:12]   # fetch_news._iid 와 같은 셈


def pop_lines():
    """기사 id → 요약 줄 (홈 주요 뉴스 팝업과 같은 캐시 — 새 AI 호출 없음)."""
    import requests
    try:
        d = requests.get(SUM_URL, timeout=20).json()
    except Exception as e:  # noqa: BLE001
        print(f"[요약] 못 받음: {type(e).__name__}")
        return {}
    return {k: v.get("lines") or [] for k, v in d.items() if isinstance(v, dict)}


def daily_counts(rows, days):
    c = {d: {"종전": 0, "확전": 0, "방향 미정": 0} for d in days}
    for r in rows:
        d = r["t"].astimezone(KST).date().isoformat()
        if d in c:
            c[d][r["side"]] += 1
    return c


def prices():
    import yfinance as yf
    syms = sorted(set(LINK_SYM.values()) | {s for _, s in CASE_COLS} | {"BZ=F", "EWY"})
    df = yf.download(syms, start="2002-10-01", progress=False, auto_adjust=True, threads=False)["Close"]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df


def z10(s, end=None):
    """signal_scan.scan 과 같은 셈 — 10거래일 로그 누적 ÷ (직전 60거래일 하루 σ × √10). VIX 도 비율(pct). end = 모든 지표가 있는 마지막 날."""
    s = s.dropna()
    s = s[s > 0]
    if end is not None:
        s = s[s.index <= end]
    ch = np.log(s).diff()
    sd = ch.rolling(BASE, min_periods=int(BASE * 0.8)).std().shift(1)
    z = ch.iloc[-10:].sum() / (sd.iloc[-11] * np.sqrt(10))
    pct = (s.iloc[-1] / s.iloc[-11] - 1) * 100
    return float(z), float(pct), s.index[-11], s.index[-1]


def link_rows(px, chain_id, end=None):
    ch = CH.CHAINS[chain_id]
    links = [(nm, f, sg) for nm, f, sg, *_ in ch["links"]] + EXTRA_LINKS
    out = []
    if end is None:
        end = min(px[LINK_SYM[f]].dropna().index[-1] for _, f, _ in links if LINK_SYM.get(f) in px and f != "EWY")   # 코스피는 미국보다 하루 먼저 닫는다 — 미국 마지막 날에 맞춘다   # ETF 가 선물보다 하루 늦게 들어오는 날(yfinance) — 같은 날에 맞춘다
    for nm, f, sg in links:
        sym = LINK_SYM.get(f)
        if not sym or sym not in px:
            continue
        z, pct, d0, d1 = z10(px[sym], end)
        sz = sg * z
        state = "뚜렷하게" if sz >= Z_CLEAR else "조금" if sz >= Z_SOME else "반대로" if sz <= -Z_SOME else "평소 범위"
        out.append({"key": f, "name": LINK_NAME[f], "why": nm, "sg": sg, "z": z, "pct": pct, "state": state, "d0": d0, "d1": d1, "extra": (nm, f, sg) in EXTRA_LINKS})
    return out


def cases(px, kinds):
    ev = pd.read_csv(os.path.join(_HERE, "events_curated.csv"))
    ev = ev[ev["subkind"].isin(kinds)]
    out = []
    for _, e in ev.iterrows():
        cal = px["^GSPC"].dropna().index
        i = cal.searchsorted(pd.Timestamp(e["start"]))
        if i >= len(cal) or i < 1:
            continue
        row = {"day": cal[i].strftime("%Y-%m-%d"), "title": e["title"].split(" — ")[0], "src": e["note"].split(" http")[0] if isinstance(e["note"], str) else ""}
        for nm, s in CASE_COLS:
            x = px[s].reindex(cal)
            a, b = x.iloc[i - 1], x.iloc[i]
            c = x.iloc[i + 20] if i + 20 < len(cal) else np.nan
            row[nm] = (None if np.isnan(a) or np.isnan(b) else (b / a - 1) * 100, None if np.isnan(a) or np.isnan(c) else (c / a - 1) * 100)
        out.append(row)
    return out


CASE_EXP = {"유가": -1, "S&P 500": +1, "한국 (EWY)": +1, "에너지": -1, "방산": -1}   # 흔한 설명의 방향 (chains.CEASEFIRE + 공급 복귀)


def case_gap(rows):
    """흔한 설명과 사례가 어긋난 지표 — 그날 움직임이 있는 사례 모두에서 반대였으면 한 줄 (위 표 `흔한 설명은 내림` 과 아래 표가 다르게 보이는 자리)."""
    out = []
    for nm, sg in CASE_EXP.items():
        v = [r[nm][0] for r in rows if r.get(nm) and r[nm][0] is not None]
        if len(v) >= 2 and all(x * sg < 0 for x in v):
            out.append(f'{nm}은 흔한 설명({"내림" if sg < 0 else "오름"})과 달리 {len(v)}번 모두 그날 {"올랐습니다" if sg < 0 else "내렸습니다"}')
    return (" " + " · ".join(out) + ".") if out else ""


# ───────────── 화면
def arrow(v, d=1):
    """증감 = 부호 숫자 + 증감 색 + 굵게 — 공용 마무리 fix_colons 가 ▲ · ▼(그 자리 글자의 80%, dk.tri_span)로 바꾼다 (가이드라인 5절).
    dk.arrow 는 ▲ 를 글자 크기 그대로 써서 쓰지 않는다 (2026-11-13 사용자: 삼각형 디자인 규칙)."""
    if v is None:
        return f'<span style="color:{dk.SUB};">—</span>'
    if round(v, d) == 0:
        return f'<span style="font-weight:700;white-space:nowrap;">{0:.{d}f}%</span>'
    return f'<span style="color:{dk.UP if v > 0 else dk.DOWN};font-weight:700;white-space:nowrap;">{"+" if v > 0 else "−"}{abs(v):.{d}f}%</span>'


def group_state(links):
    """묶음마다: 종전 방향 1배 넘는 지표 수 · 2배 넘는 것 · 반대 1배 넘는 것 → 한 마디."""
    by = {r["key"]: r for r in links}
    out = []
    for g, keys in GROUPS:
        rs = [by[k] for k in keys if k in by]
        ok = sum(r["sg"] * r["z"] >= Z_SOME for r in rs)
        clear = sum(r["sg"] * r["z"] >= Z_CLEAR for r in rs)
        rev = sum(r["sg"] * r["z"] <= -Z_SOME for r in rs)
        word = ("종전 방향으로 움직이는 중" if ok >= 2 and clear >= 1 else "종전 방향으로 조금" if ok >= 2 else
                "반대로 움직이는 중" if rev >= 2 else "평소 범위")
        out.append((g, word, ok, len(rs), rs))
    return out


def state_of(news48, base48, groups):
    hot = news48 >= 3 and (base48 is None or news48 >= 2 * max(base48, 0.5))
    moving = [g for g, w, *_ in groups if w == "종전 방향으로 움직이는 중"]
    if moving and hot:   # `시장 함께` 는 주식 쪽이 반대로 갈 때도 같이 움직인다고 읽힌다 → 움직인 묶음 이름을 쓴다
        return (f"뉴스 늘고 {josa(moving[0], ('이', '가'))} 종전 방향으로" if len(moving) == 1 else "뉴스 늘고 시장이 종전 방향으로"), "uncertain"
    if moving:
        return (f"{josa(moving[0], ('이', '가'))} 종전 방향으로" if len(moving) == 1 else "시장이 종전 방향으로"), "uncertain"   # `먼저` 는 선반영 단언(검증 3-a) → 사실만
    some = [g for g, w, *_ in groups if w == "종전 방향으로 조금"]   # 묶음 줄은 `조금` 인데 머리는 `조용함` 이면 어긋난다 (11-13: 하루 더 들어오자 유가 2.1배 → 1.8배로 머리만 `조용함` 이 됐다)
    if some:
        who = josa(some[0], ("이", "가")) if len(some) == 1 else "시장이"   # 위 `뉴스 늘고 유가가 종전 방향으로` 와 같은 꼴
        return ("뉴스 늘고 " if hot else "") + f"{who} 종전 방향으로 조금", "area"
    if hot:
        return "뉴스 늘어남", "neutral"
    return "조용함", "neutral"


def short(st):
    """목록 · 지난 2주 칸의 짧은 말 (500px 에서 오른쪽 칸에 들어가게 — 긴 말은 `지금은` 카드 오른쪽에만). 방향은 이 페이지가 종전 쪽만 보므로 뺀다."""
    if st == "조용함" or st == "뉴스 늘어남":
        return st
    who = "유가" if "유가" in st else "시장"
    return ("뉴스 · " if "뉴스" in st else "") + who + (" 조금 움직임" if "조금" in st and "뉴스" not in st else " 조금" if "조금" in st else " 움직임")


def head_card(st, kind, news48, base48, groups, sides48=None, asof=""):
    news = f'48시간 이란 기사 {news48}건' + (f' (종전 {sides48[0]} · 확전 {sides48[1]})' if sides48 and news48 else '') + (f' · 평소 {base48:.1f}건' if base48 is not None else '')

    def gline(w, ok, n, rs):   # 괄호 안 숫자는 그 말과 같은 쪽만 — `평소 범위 (0개 종전 방향)` 처럼 줄 표시와 어긋나지 않게
        rev = sum(r["sg"] * r["z"] <= -Z_SOME for r in rs)
        return w + (f' ({n}개 중 {rev}개 반대 방향)' if "반대" in w else f' ({n}개 중 {ok}개 종전 방향)' if "종전" in w else "")
    items = [("뉴스", news)] + [(g, gline(w, ok, n, rs)) for g, w, ok, n, rs in groups] + ([("기준", asof)] if asof else [])
    tipt = ("뉴스 = 이 이슈 기사 수가 평소의 2배 · 3건 넘으면 `뉴스 늘어남`.\n"
            "시장 = 종전이면 움직인다고 흔히 설명하는 지표를 묶음별로 — 묶음 안 2개 이상이 그 방향으로 평소보다 크게(하나는 2배 넘게) 움직이면 `움직이는 중`.\n"
            "예측이 아니라 지금까지 일어난 일입니다.")
    return dk.state_card(f'지금은{dk.tip(tipt)}', kind=kind, right_html=dk.esc(st), items=items)


def list_card(rows):
    out = []
    for r in rows:
        on = r["state"] != "조용함"
        lab = f'<span style="font-weight:{dk.STATE_VAL_W};color:{qc.SOON if on else "#111"};white-space:nowrap;">{dk.esc(short(r["state"]))}</span>'   # 라벨 대신 값 글자 — 띄어쓰기 든 긴 말은 라벨로 쓰지 않는다 (8절)
        out.append((dk.esc(r["name"]), lab, dk.esc(f'48시간 기사 {r["n48"]}건' ), None, True, True))
    return dk.ccard(out)


def news_chart(counts):
    days = list(counts)
    labels = [H.md(d) if i in (0, len(days) // 2, len(days) - 1) else "" for i, d in enumerate(days)]
    series = [("종전 기사", [counts[d]["종전"] for d in days], qc.PASTEL_UP, "solid"),
              ("확전 기사", [counts[d]["확전"] for d in days], qc.PASTEL_DN, "solid")]   # 라벨과 같은 빨강 · 파랑 (2026-11-13 사용자)   # 방향 미정은 선에서 뺀다 — 회색 점선은 범례가 `비교 대상` 이 된다. 건수는 아래 한 줄에
    return dk.trend_card("날마다 이란 기사 (건)", labels, series, lambda v: f"{v:.0f}" if float(v).is_integer() else "", ends_only=True)   # 건수 축에 0.5 없음


def link_card(links, groups):
    rows = []
    for g, w, ok, n, rs in groups:
        rows.append((f'<b>{dk.esc(g)}</b>', dk.pill(w, "uncertain" if "움직이는 중" in w and "반대" not in w else "area", bare=True), "", None, True))
        rows.extend(_link_row(r) for r in rs)
    d0, d1 = links[0]["d0"], links[0]["d1"]
    return d0, d1, rows


def _link_row(r):
    exp = "내림" if r["sg"] < 0 else "오름"
    kind = {"뚜렷하게": "uncertain", "조금": "area", "반대로": "negative", "평소 범위": "neutral"}[r["state"]]
    name = dk.esc(r["name"])
    sub = f'흔한 설명은 {exp} · 평소의 {abs(r["z"]):.1f}배 {"같은" if r["sg"] * r["z"] > 0 else "반대"} 방향'
    return (name, arrow(r["pct"]) + " " + dk.pill(r["state"], kind), dk.esc(sub), None, True, True)


def link_sec(links, groups):
    d0, d1, rows = link_card(links, groups)
    tipt = (f"최근 10거래일({H.md(d0.strftime('%Y-%m-%d'))} 종가 → {H.md(d1.strftime('%Y-%m-%d'))} 종가) 움직임.\n"
            "평소의 몇 배 = 이 지표가 보통 10거래일에 움직이는 폭(직전 60거래일 기준)의 몇 배인지.\n"
            "· 뚜렷하게 = 예상 방향으로 2배 넘게\n· 조금 = 1~2배\n· 반대로 = 반대 방향 1배 넘게\n"
            "예상 방향은 시장에서 흔히 쓰는 설명(교과서 · 언론)이고, 우리 주장은 아닙니다.")
    return dk.section("시장이 먼저 움직이나?", dk.ccard(rows) + dk.muted(f"최근 10거래일 {H.md(d0.strftime('%Y-%m-%d'))} → {H.md(d1.strftime('%Y-%m-%d'))} 종가"),
                      aside=dk.tips_right([("읽는 법", tipt)]))


def oil_chart(px):
    s = px["BZ=F"].dropna()
    s = s[s.index >= "2026-01-02"]
    days = [d.strftime("%Y-%m-%d") for d in s.index]
    marks = {"2026-03-02": "개전", "2026-04-08": "휴전", days[-1]: H.md(days[-1])}
    labels = [marks.get(d, "") for d in days]
    for k, v in marks.items():   # 휴일이면 다음 거래일에
        if k not in days:
            j = next((i for i, d in enumerate(days) if d > k), None)
            if j is not None:
                labels[j] = v
    gr = dk.trend_card("브렌트유 (달러, 올해)", labels, [("브렌트유", [round(v, 1) for v in s], dk.CHART_MAIN, "solid")], lambda v: f"{v:.0f}")   # 점이 많아 날마다 동그라미 없이 끝 값만
    pk = s[s.index >= "2026-03-02"]
    peak, peak_d = float(pk.max()), pk.idxmax().strftime("%Y-%m-%d")
    now = float(s.iloc[-1])
    pre = float(s[s.index < "2026-02-28"].iloc[-1])
    rc = s.iloc[-30:]   # 최근 30거래일 고점 → 지금 을 먼저 (10월에 다시 3월 고점까지 올랐다 — `오른 폭의 절반을 내려놓았다` 는 한 방향으로 내린 것처럼 읽힌다)
    rh, rd = float(rc.max()), rc.idxmax().strftime("%Y-%m-%d")
    pre_d = H.md(s[s.index < '2026-02-28'].index[-1].strftime('%Y-%m-%d'))
    line = (f"최근 고점({H.md(rd)}) {rh:.0f}달러 → 지금({H.md(days[-1])}) {now:.0f}달러, {(now / rh - 1) * 100:.0f}%. ".replace("-", "−") if rh > now * 1.05 else f"지금({H.md(days[-1])}) {now:.0f}달러. ")
    line += f"전쟁 전({pre_d}) {pre:.0f}달러 · 올해 가장 높았던 날({H.md(peak_d)}) {peak:.0f}달러."
    return gr, line


def cases_card(rows):
    if not rows:
        return ""
    th = "".join(f'<th style="padding:6px 6px;text-align:right;font-weight:600;color:{dk.SUB};font-size:14px;white-space:nowrap;">{dk.esc(n)}</th>' for n, _ in CASE_COLS)
    body = ""
    for r in rows:
        for j, (lab, k) in enumerate((("그날", 0), ("20거래일 뒤", 1))):
            bt = "border-top:1px solid #E2E8F0;" if j == 0 else ""
            cells = "".join(f'<td style="padding:6px 6px;text-align:right;white-space:nowrap;font-size:15px;{bt}">{arrow(r[n][k]) if r[n] else "—"}</td>' for n, _ in CASE_COLS)
            first = f'<td rowspan="2" style="padding:8px 6px;vertical-align:top;font-size:15px;line-height:22px;{bt}"><b>{H.md(r["day"]) if r["day"][:4] == str(dt.date.today().year) else r["day"].replace("-", ".")}</b><br>' \
                    f'<span style="color:#333;">{dk.esc(r["title"])}</span></td>' if j == 0 else ""
            body += f'<tr>{first}<td style="padding:6px 6px;color:{dk.SUB};font-size:14px;white-space:nowrap;{bt}">{lab}</td>{cells}</tr>'
    tbl = (f'<div style="overflow-x:auto;margin:0 0 8px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;"><table style="border-collapse:collapse;width:100%;min-width:560px;">'
           f'<tr><th style="padding:6px;text-align:left;font-weight:600;color:{dk.SUB};font-size:14px;">사례</th><th></th>{th}</tr>{body}</table></div>')
    return tbl


def forks_card(chain_id):
    ch = CH.CHAINS[chain_id]
    rows = [(dk.esc(a), dk.esc(b.replace("전쟁 사슬로 돌아감", "유가 오름 · 위험 회피로 돌아감")), "", 45) for a, b in ch["forks"]]   # `사슬` = 내부 말
    return dk.ccard(rows, left=45)


def bridge_card(px):
    """증시 전망으로 넘어가는 자리 — 에너지 업종 vs S&P 500 하루 움직임이 평소 3배 · 2.5%p (forecast_register 기준)."""
    e, s = px["XLE"].dropna(), px["^GSPC"].dropna()
    idx = e.index.intersection(s.index)
    rel = (e.reindex(idx).pct_change() - s.reindex(idx).pct_change()) * 100   # forecast_register 와 같은 단순 수익률 차
    sd = rel.rolling(60, min_periods=48).std().shift(1)
    z = (rel / sd).iloc[-10:]
    j = z.abs().idxmax()
    hit = abs(z[j]) >= 3 and abs(rel[j]) >= 2.5
    word = "더 빠져" if rel[j] < 0 else "더 올라"
    now = (f'{H.md(j.strftime("%Y-%m-%d"))}에 에너지 업종이 S&P 500 보다 {abs(rel[j]):.1f}%p {word}(평소의 {abs(z[j]):.1f}배) 이 기준을 넘었습니다. 전망을 자동으로 만들기 시작한 11.11 전이라 그날 전망은 없습니다.' if hit else
           f'최근 10거래일 가장 컸던 날은 {H.md(j.strftime("%Y-%m-%d"))} {abs(rel[j]):.1f}%p (평소의 {abs(z[j]):.1f}배).')
    rows = [("가격이 크게 움직이면", '에너지 업종이 S&P 500 보다 하루에 평소의 3배 · 2.5%p 넘게 움직이면 다음 날 ‘급락 뒤’ 증시 전망으로. ' + now),
            ("날짜가 잡히면", "휴전 서명 · 협상 시한처럼 날짜가 정해지면 → 사건 전 전망 (합의 · 결렬 두 갈래)")]
    return dk.state_card("증시 전망으로 넘어가는 때", items=rows)


# ───────────── 같은 사건 묶기 (AI 0) — 기사 수백 건을 그대로 늘어놓지 않고 사건 한 줄 + 보도 n곳 + 원문 링크 몇 개 (2026-11-13 사용자)
EV_SIM, EV_HOURS, EV_MIN_SRC, EV_LINKS = 0.3, 36, 3, 3   # 제목 글자 둘씩 겹침(자카드) · 같은 사건으로 보는 시간 폭 · 위 목록에 올리는 보도 곳 수 · 원문 링크 수


def _grams(t):
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", t)
    t = re.sub(r"[\W_]+", "", t)
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _clean_title(t):
    """사건 줄 = 대표 제목에서 `[속보]` · `(종합)` · 그림 문자 · 끝 `- 매체` 를 뗀 것."""
    t = re.sub(r"\[[^\]]*\]|\((?:종합|종합\d보|상보|영상)[^)]*\)", "", t)
    t = re.sub(r"\s+-\s+[^-]{1,20}$", "", t)
    t = re.sub(r"[\U0001F000-\U0001FAFF☀-➿️]", "", t)
    t = re.sub(r"\s*[:|]\s*(?:국제|정치|경제|세계|뉴스|사회|IT|증권|글로벌|월드)[^:|]{0,6}$", "", t)   # 끝 섹션 이름 `: 국제`
    return re.sub(r"\s+", " ", t).strip()


def cluster(rows):
    """최신 → 과거 순으로, 시간 폭 안 묶음의 앞 6건과 가장 많이 겹치는 묶음에 넣는다."""
    out = []
    for r in rows:
        g = r.setdefault("_g", _grams(r["title"]))
        best, bs = None, 0.0
        for cl in out:
            if abs((cl[0]["t"] - r["t"]).total_seconds()) > EV_HOURS * 3600:
                continue
            sim = max(len(g & m["_g"]) / max(1, len(g | m["_g"])) for m in cl[:6])
            if sim > bs:
                best, bs = cl, sim
        if best is not None and bs >= EV_SIM:
            best.append(r)
        else:
            out.append([r])
    return out


def _major(cl, key, skip):
    c = {}
    for m in cl:
        c[m[key]] = c.get(m[key], 0) + 1
    named = {k: v for k, v in c.items() if k != skip}
    return max(named, key=named.get) if named and max(named.values()) * 2 >= max(1, len(cl) - c.get(skip, 0)) else skip


def event_of(cl):
    """묶음 → 사건 한 줄. 대표 = 다른 기사들과 가장 많이 겹치는 제목(가운데 기사). 공용 뉴스(우리 말 사실 줄)가 들어 있으면 그것을 쓴다."""
    own = next((m for m in cl if not m["gn"] and m.get("fact")), None)
    rep = max(cl, key=lambda m: sum(len(m["_g"] & o["_g"]) / max(1, len(m["_g"] | o["_g"])) for o in cl))
    srcs, links = [], []
    for m in sorted(cl, key=lambda m: m["t"]):   # 먼저 보도한 곳부터
        if m["src"] and m["src"] not in srcs:
            srcs.append(m["src"])
            if len(links) < EV_LINKS and m.get("url"):
                links.append((m["src"], m["url"]))
    return {"title": own["fact"] if own else _clean_title(rep["title"]), "n_src": len(srcs), "n": len(cl), "links": links,
            "first": min(m["t"] for m in cl), "last": max(m["t"] for m in cl),
            "side": _major(cl, "side", "방향 미정"), "talk": sum(m["stage"] != "일어난 일" for m in cl) * 2 >= len(cl), "own": own, "rep": rep}


def _src_links(links):
    a = " · ".join(f'<a href="{dk.esc(u)}" target="_blank" rel="nofollow noopener" style="color:inherit;text-decoration:none;">{dk.esc(n)}</a>' for n, u in links)
    return f'<span style="display:block;margin:4px 0 0;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};">원문 : {a}</span>'


def event_item(ev, sums):
    labs = side_pill(ev["side"]) + (dk.pill("논의중", "neutral", bare=True) if ev["talk"] else "")
    meta = (dk.news_when(ev["first"].isoformat()), f'보도 {ev["n_src"]}곳' if ev["n_src"] > 1 else (ev["links"][0][0] if ev["links"] else ""))
    own = ev["own"]
    lines = (sums.get(_iid(own["url"] or "")) or []) if own else []
    if len(lines) >= 2:   # 공용 뉴스 요약 줄이 있는 사건 — 줄 전체를 눌러 팝업 (가이드라인 10절)
        pid = dk.news_pop_id("iw", own["url"])
        return (dk.news_pop_wrap(dk.news_item(dk.esc(ev["title"]), None, labels=labs, meta=meta), pid)
                + dk.news_pop_body(pid, ev["title"], lines, source=own["src"], kind="기사", url=own["url"])), True
    return dk.news_item(dk.esc(ev["title"]), None, subs=[_src_links(ev["links"])], labels=labs, meta=meta), False


def small_row(ev):
    """한두 곳만 보도한 기사 = 작은 한 줄 (제목 링크 · 날짜 · 매체) — 버리지 않고 접어 둔다."""
    u = ev["links"][0][1] if ev["links"] else None
    t = dk.esc(ev["title"])
    head = f'<a href="{dk.esc(u)}" target="_blank" rel="nofollow noopener" style="color:#111;text-decoration:none;">{t}</a>' if u else t
    meta = " · ".join(x for x in (H.md(ev["first"].astimezone(KST).date().isoformat()), " · ".join(n for n, _ in ev["links"][:2])) if x)
    return (f'<div style="padding:9px {dk.ALIGN_PX}px;border-top:1px solid #E2E8F0;font-size:16px;line-height:26px;word-break:keep-all;">{head}'
            f'<span style="display:block;font-size:13px;line-height:19px;color:{dk.SUB};">{dk.esc(meta)}</span></div>')


# ───────────── 관련 뉴스 = 막대 두 개 + 타임라인 (2026-11-13 사용자: "우리 뉴스 긍정 · 부정 그래프처럼 · 뉴스 타임라인 · 누르면 그날 사실 블릿 · 끝에 - 기사 22건")
SIDE_BAR = {"종전": dk.BAR_PASTEL["positive"], "확전": dk.BAR_PASTEL["negative"], "방향 미정": dk.BAR_PASTEL["neutral"]}   # 뉴스 방향 막대의 긍정 · 부정 · 중립 색 그대로 (2026-11-13 사용자: 종전 = 빨강 · 확전 = 파랑)
TL_SHOWN = 5   # 타임라인 처음에 보이는 날 — 나머지는 `지난 n일 더 보기` (증시 전망 타임라인과 같은 5)


def side_bars(today_rows, rows):
    """뉴스 방향 막대(dk.direction_bars 의 펼친 꼴)와 같은 흰 카드 — 오늘 · 최근 2주 막대 두 개를 위아래로."""
    def bar(label, rs):
        c = {k: sum(r["side"] == k for r in rs) for k in SIDE_BAR}
        return dk.legend_bar(f"{label} {len(rs)}건", [(SIDE_LABEL[k], c[k], *SIDE_BAR[k]) for k in SIDE_BAR])
    a, b = bar("오늘", today_rows), bar("최근 2주", rows)
    gap = f'<span style="display:block;height:{dk.BAR_GROUP_GAP - 5}px;"></span>' if a and b else ""
    return (f'<div style="margin:0 0 8px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;padding:{dk.SEP_GAP - 3}px 12px {dk.SEP_GAP - 3 - 10}px;">'
            f'{a}{gap}{b}</div>')


ONE_HARD = re.compile(r"폭발|공격|타격|공습|격추|피격|나포|봉쇄|개방|휴전|정전|합의|서명|타결|결렬|철수|파병|발사|사망|제재|발효|승인|통과")   # 실제로 일어난 일 낱말
ONE_WIRE = {"연합뉴스", "뉴스1", "뉴시스", "연합인포맥스", "연합뉴스TV"}   # 속보를 먼저 내는 통신사


def one_pick(e):
    """한 곳만 보도한 사건 중 팝업에 올릴 것 — 따옴표 발언이 아닌 `일어난 일` + 사건 낱말, 또는 통신사 기사 (AI 0, 2026-11-13 사용자: 23건 다 펼치지 말고 다른 방법).
    막 터진 사실(유조선 폭발 · 기지 공격)은 처음엔 한 곳만 보도할 수 있다. 반응 · 해설 · 칼럼은 빠진다."""
    return (not e["talk"] and bool(ONE_HARD.search(e["title"]))) or bool(e["links"] and e["links"][0][0] in ONE_WIRE)


def _day_pop(pid, day, evs):
    """그날 팝업 = 사건마다 한 줄(사실) + 끝 꼬리 `- 기사 n건` — 증시 전망 근거 팝업 줄(H._pop_li)과 같은 모양. 쪽마다 라벨 하나 + 블릿.
    두 곳 이상 보도한 사건 + 한 곳만이라도 one_pick 에 맞는 사건. 나머지 한 곳만 보도는 팝업에 싣지 않는다 (옛 `그 밖에 n건` 줄 삭제, 2026-11-13 사용자)."""
    lis = ""
    many = [e for e in evs if e["n"] >= 2 or one_pick(e)] or evs[:1]
    many.sort(key=lambda e: (-e["n"], e["first"]))
    groups = sorted({e["side"] for e in many}, key=lambda k: -sum(e["n"] for e in many if e["side"] == k))   # 쪽마다 라벨 하나 + 그 아래 블릿 (2026-11-13 사용자) — 기사 많은 쪽 먼저
    for gi, side in enumerate(groups):
        lis += (f'<span style="display:flex;align-items:center;gap:8px;margin:{H.POP_SUB_FIRST if gi == 0 else H.POP_SUB_GAP - 10}px 0 0;padding-left:{H.POP_LI_PAD}px;line-height:1;">'
                f'{side_pill(side, pop=True)}<span aria-hidden="true" style="flex:1;height:0;border-top:1px dashed {H.TL_LINE};"></span></span>')   # 라벨 오른쪽 가로 점선 · 세로 가운데 (2026-11-13 사용자) — 타임라인 점선과 같은 회색
        for e in [e for e in many if e["side"] == side]:
            lis += H._pop_li(e["title"], f'기사 {e["n"]}건', talk=e["talk"])
    title = f'{H.md(day)} 이란 전쟁 뉴스'
    return f'<div data-news-pop-body="{dk.esc(pid)}" data-news-pop-title="{dk.esc(title)}" hidden>{lis}</div>'


def news_timeline(evs, days_desc):
    """날짜별 한 줄 = 그날 가장 많이 보도된 사건 + `기사 n건`. 줄을 누르면 그날 사건 전부(많이 보도된 순) 팝업."""
    by = {}
    for e in evs:
        by.setdefault(e["first"].astimezone(KST).date().isoformat(), []).append(e)
    rows, pops = [], ""
    days = [d for d in days_desc if by.get(d)]
    for i, d in enumerate(days):
        es = sorted(by[d], key=lambda e: (-e["n"], e["first"]))
        top, n = es[0], sum(e["n"] for e in es)
        pid = dk.news_pop_id("iwday", d)
        lab = side_pill(top["side"]) + (dk.pill("논의중", "neutral", bare=True) if top["talk"] else "")
        node = (f'<span style="display:inline-block;width:{H.TL_DOT}px;height:{H.TL_DOT}px;box-sizing:border-box;border:2px solid {H.TL_LINE};border-radius:50%;background:#fff;"></span>')
        content = (f'<div data-news-pop="{dk.esc(pid)}" role="button" tabindex="0" style="cursor:pointer;padding:0 0 {H.TL_DAY_GAP}px;">'
                   f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:16px;line-height:24px;">'
                   f'<b style="color:#111;">{H.md(d)}</b></div>'   # `기사 n건` 삭제 (2026-11-13 사용자)
                   f'<div style="display:flex;align-items:center;gap:4px;margin:2px 0 0;font-size:16px;line-height:26px;color:#111;word-break:keep-all;">'
                   f'<span style="flex:0 1 auto;min-width:0;">{dk.esc(top["title"])}</span>{H._CHEV_R}</div>'   # 줄 끝 › = 증시 전망 타임라인 근거 줄과 같은 것
                   f'<div style="margin:6px 0 0;line-height:1;">{dk.pill_row(lab)}'
                   + '</div></div>')   # `외 사건 n개` 삭제 — 기사 수와 헷갈린다, 개수는 팝업 · 막대가 말한다 (2026-11-13 사용자)
        rows.append(H._tl_row(node, 24, 0, content, i == 0, i == len(days) - 1))
        pops += _day_pop(pid, d, es)
    shown, rest = rows[:TL_SHOWN], rows[TL_SHOWN:]
    out = "".join(shown)
    if rest:
        out += dk.fold(f"지난 {len(rest)}일 더 보기", "".join(rest))
    return out + pops


# ───────────── 질문 카드 (강조 카드 · 펼침 — 데일리 · 증시 전망 갈래 카드와 같은 qc.question_card, 2026-11-13 사용자 "강조 카드의 펼침 열림 디자인")
VIOLET = qc.SOON


def _theme(on):
    """움직임 · 뉴스 늘어남 = 보라 카드(방향이 주가 오름 · 내림이 아니라 `종전 쪽` 이라 빨강 · 파랑을 쓰지 않는다), 아니면 회색."""
    return ("uncertain", VIOLET) if on else ("neutral", "#111")


def _sp(html):
    return f"<span>{html}</span>"   # 근거 줄 값 · 이름이 HTML 이면 <span 으로 시작해야 그대로 쓴다


def _ttl(t):
    """카드 안 그래프 · 표 제목 — 그래프 제목과 같은 `※` + 16/24 굵게."""
    return f'<div style="margin:6px 0 6px;font-size:16px;line-height:24px;font-weight:700;color:#111;">※ {dk.esc(t)}</div>'


def q_news(iran, counts, days, r48):
    n48, base = iran["n48"], iran["base48"]
    ratio = n48 / base if base else None
    th, ink = _theme(iran["hot"])
    ans = f"평소의 {ratio:.1f}배" if ratio else f"{n48}건"
    a, b = sum(r["side"] == "종전" for r in r48), sum(r["side"] == "확전" for r in r48)
    first = ((f"최근 48시간 이란 기사는 {n48}건으로 평소({base:.0f}건)의 {ratio:.1f}배입니다. " if ratio else f"최근 48시간 이란 기사는 {n48}건입니다. ")
             + f"종전 {a}건 · 확전 {b}건 · 방향미정 {n48 - a - b}건입니다.")
    r2w = [x for x in iran["rows"] if x["t"].astimezone(KST).date().isoformat() >= days[0]]
    t, w = sum(x["side"] == "종전" for x in r2w), sum(x["side"] == "확전" for x in r2w)
    cap = sorted(c for c in iran["capped"] if c in days)
    note = f"최근 2주 {len(r2w)}건 : 종전 {t} · 확전 {w} · 방향미정 {len(r2w) - t - w}" + (f". {', '.join(H.md(d) for d in cap)}은 100건 넘게 나와 100건까지만 셌습니다." if cap else "")
    tip = ("종전 = 휴전 · 협상 진전 · 긴장 완화 소식\n확전 = 공격 · 위협 · 제재 · 협상이 멀어지는 말\n"
           "출처 : 알파스코프 뉴스 모음(CNBC) + 구글 뉴스 한국어 검색, 방송은 아직 안 셈\n평소 = 직전 4주 동안 48시간마다 나온 기사 수의 평균")
    lines = [(first, "plain"), (news_chart(counts), "html"), (note, "note")]
    return qc.question_card("얼마나 화제인가?", ans, th, ink, lines, tip=tip, opened=True), r2w   # 첫 카드만 펼침 (데일리 P216 과 같게)


def q_market(links, groups, oil_gr, oil_line):
    d0, d1 = links[0]["d0"], links[0]["d1"]
    moving = [g for g, wd, *_ in groups if "종전 방향" in wd]
    on = bool(moving)
    th, ink = _theme(on)
    by_w = {g: wd for g, wd, *_ in groups}
    ans = (f'{moving[0]}{"만" if len(moving) == 1 else " 외"} {"조금" if "조금" in by_w[moving[0]] else "움직임"}') if on else "평소 범위"
    parts = []
    for g, wd, ok, n, rs in groups:
        if "종전 방향" in wd:
            parts.append(f"{g} 지표 {n}개 중 {ok}개가 종전 때 흔히 설명하는 방향으로 움직였습니다")
        elif "반대" in wd:
            parts.append(f"{josa(g, ('은', '는'))} 반대로 움직였습니다")
    calm = [g for g, wd, *_ in groups if wd == "평소 범위"]
    first = (". ".join(parts) + ". " if parts else "") + (f"{josa(' · '.join(calm), ('은', '는'))} 평소 범위입니다." if calm else "")
    lines = [(f"최근 10거래일({H.md(d0.strftime('%Y-%m-%d'))} → {H.md(d1.strftime('%Y-%m-%d'))} 종가) 기준입니다. " + first, "plain")]
    for gi, (g, wd, ok, n, rs) in enumerate(groups):
        kind = "uncertain" if "종전 방향" in wd else "area"
        lines.append(("row", _sp(f"<b>{dk.esc(g)}</b>"), f"{n}개 중 {ok}개", wd, *(("gap",) if gi else ())))
        for r in rs:
            exp = "내림" if r["sg"] < 0 else "오름"
            sub = f'흔한 설명은 {exp} · 평소의 {abs(r["z"]):.1f}배 {"같은" if r["sg"] * r["z"] > 0 else "반대"} 방향'
            lines.append(("row", r["name"], arrow(r["pct"]), sub, "tight"))
    lines += [(oil_gr, "html")] + ([(oil_line, "note")] if oil_line else [])
    tip = ("평소의 몇 배 = 이 지표가 보통 10거래일에 움직이는 폭(직전 60거래일 기준)의 몇 배인지.\n"
           "· 뚜렷하게 = 흔한 설명 방향으로 2배 넘게\n· 조금 = 1~2배\n· 반대로 = 반대 방향 1배 넘게\n"
           "흔한 설명 = 시장에서 흔히 쓰는 설명(교과서 · 언론), 우리 주장이 아님.\n"
           "묶음 오른쪽 = 흔한 설명 방향으로 평소보다 크게(1배 넘게) 움직인 지표 수")
    return qc.question_card("시장이 먼저 움직이나?", ans, th, ink, lines, tip=tip)


def q_history(hist):
    changes = sum(1 for a, b in zip(hist, hist[1:]) if a["state"] != b["state"])
    lines = [(f"최근 {len(hist)}거래일 동안 상태가 {changes}번 바뀌었습니다.", "plain")]
    for when_html, pill_html, *_ in history_line(hist):
        lines.append(("row", when_html, pill_html, ""))
    lines.append(("같은 기준으로 날마다 다시 센 상태. 미국 종가 기준이라 날짜는 뉴욕 날짜입니다.", "note"))
    tip = "오늘 한 번 보는 것보다, 상태가 언제 바뀌었는지가 중요합니다.\n기준선 근처에서는 하루 사이에 `움직임` ↔ `조금` 으로 바뀔 수 있습니다."
    return qc.question_card("지난 2주는?", f"{changes}번 바뀜", "neutral", "#111", lines, tip=tip)


def q_if(chain_id, cs):
    ch = CH.CHAINS[chain_id]
    lines = [("row", a, "", b.replace("전쟁 사슬로 돌아감", "유가 오름 · 위험 회피로 돌아감")) for a, b in ch["forks"]]
    lines += [(_ttl("지난 휴전 · 종전 때 실제로는") + cases_card(cs), "html"),
              ("3번뿐이라 ‘보통 이렇다’고 말할 수는 없습니다. 03.31 과 04.08 은 20거래일이 겹칩니다. 04.08 휴전 뒤 전쟁은 다시 이어졌습니다(10월 해협 공격 · 11.07 타격)." + case_gap(cs), "note")]
    tip = ("갈림 = 시장에서 흔히 쓰는 설명(교과서 · 언론), 우리 주장이 아님.\n"
           "사례 = 알파스코프 사건표의 `휴전 · 종전` 날, 그날 종가와 20거래일 뒤 종가를 전날 종가와 비교\n"
           "한국 (EWY) = 미국에 상장된 한국 증시 ETF, 미국 장 시간에 같이 잴 수 있어서")
    return qc.question_card("이렇게 되면?", f"지난 사례 {len(cs)}번", "neutral", "#111", lines, tip=tip)


def q_bridge(px):
    """증시 전망으로 넘어가는 자리 — 에너지 업종 vs S&P 500 하루 움직임이 평소 3배 · 2.5%p (forecast_register 기준)."""
    e, s = px["XLE"].dropna(), px["^GSPC"].dropna()
    idx = e.index.intersection(s.index)
    rel = (e.reindex(idx).pct_change() - s.reindex(idx).pct_change()) * 100
    sd = rel.rolling(60, min_periods=48).std().shift(1)
    z = (rel / sd).iloc[-10:]
    j = z.abs().idxmax()
    hit = abs(z[j]) >= 3 and abs(rel[j]) >= 2.5
    word = "더 빠져" if rel[j] < 0 else "더 올라"
    now = (f'{H.md(j.strftime("%Y-%m-%d"))}에 에너지 업종이 S&P 500 보다 {abs(rel[j]):.1f}%p {word}(평소의 {abs(z[j]):.1f}배) 이 기준을 넘었습니다. '
           f'전망을 자동으로 만들기 시작한 11.11 전이라 그날 전망은 없습니다.' if hit else
           f'최근 10거래일 가장 컸던 날은 {H.md(j.strftime("%Y-%m-%d"))} {abs(rel[j]):.1f}%p (평소의 {abs(z[j]):.1f}배)입니다.')
    lines = [(now, "plain"),
             ("row", "가격이 크게 움직이면", "", "에너지 업종이 S&P 500 보다 하루에 평소의 3배 · 2.5%p 넘게 움직이면 다음 날 ‘급락 뒤’ 증시 전망으로"),
             ("row", "날짜가 잡히면", "", "휴전 서명 · 협상 시한처럼 날짜가 정해지면 사건 전 전망으로 (합의 · 결렬 두 갈래)")]
    return qc.question_card("증시 전망으로 넘어가나?", "아직" if not hit else f"{H.md(j.strftime('%Y-%m-%d'))} 기준 넘음", "neutral", "#111", lines)


def build():
    items = SB.load_news()
    now = dt.datetime.now(dt.timezone.utc)
    today = now.astimezone(KST).date()
    days = [(today - dt.timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    gdays = [(today - dt.timedelta(days=i)).isoformat() for i in range(41, -1, -1)]   # 평소 = 직전 28일 → 지난 2주 상태까지 거슬러 세려면 42일
    px = prices()

    watch = []
    for iss in ISSUES:
        gn, capped = gnews(iss, gdays)
        rows = merge_rows(news_rows(items, iss["pat"]), news_rows(gn, iss["pat"]))
        n48, base, hot = news_level(rows, now)
        watch.append({**iss, "rows": rows, "n48": n48, "base48": base, "hot": hot, "capped": capped,
                      "n_store": sum(not r["gn"] for r in rows), "n_gn": sum(r["gn"] for r in rows)})

    iran = watch[0]
    links = link_rows(px, iran["chain"])
    groups = group_state(links)
    st, kind = state_of(iran["n48"], iran["base48"], groups)
    for w in watch:
        w["state"] = st if w is iran else ("뉴스 늘어남" if w["hot"] else "조용함")
    hist = history(px, iran["chain"], iran["rows"])
    json.dump({"issue": iran["id"], "rules": RULES, "made": now.isoformat(), "days": hist}, open(os.path.join(OUT, "issue_state_log.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)   # 운영 = 상태 브랜치 records/issues/ 에 하루 한 줄

    counts = daily_counts(iran["rows"], days[:-1])   # 오늘은 하루가 덜 지나 뚝 떨어져 보인다 — 다 지난 날만
    oil_gr, oil_line = oil_chart(px)
    cs = cases(px, iran["cases"])

    lead = ('<p style="margin:0 0 12px;padding:0 6px;font-size:16px;line-height:26px;color:#333;word-break:keep-all;">'
            '독자들이 궁금해하는 이슈를 매일 지켜봅니다. 예측이 아니라, <b>뉴스가 늘었는지</b> · <b>시장이 먼저 움직이는지</b>를 그날그날 사실로 적습니다. '
            '가격이 크게 움직이거나 날짜가 잡히면 증시 전망으로 넘어갑니다.</p>')
    top = dk.section("지켜보는 이슈", lead + list_card(watch), line=True)

    q = (f'<h2 style="{dk.H2}margin:34px 0 11px;display:flex;align-items:flex-start;gap:8px;">'
         f'<span style="display:flex;flex:none;align-items:center;height:1lh;">{H.scale_icon(24)}</span>'
         f'<span style="flex:1 1 auto;min-width:0;word-break:keep-all;">{dk.esc(iran["q"])}</span></h2>')
    r48 = [r for r in iran["rows"] if now - r["t"] <= dt.timedelta(hours=48)]
    asof = f'시장 {H.md(links[0]["d1"].strftime("%Y-%m-%d"))} 종가 · 뉴스 {H.md(today.isoformat())} {now.astimezone(KST):%H}시까지'
    head = head_card(st, kind, iran["n48"], iran["base48"], groups, (sum(r["side"] == "종전" for r in r48), sum(r["side"] == "확전" for r in r48)), asof)

    c_news, r2w = q_news(iran, counts, days, r48)
    news_n = len(r2w)
    qcards = (c_news + q_market(links, groups, oil_gr, oil_line) + q_history(hist) + q_if(iran["chain"], cs) + q_bridge(px))
    qcards = f'<div style="margin:0 0 8px;">{qcards}</div>'

    sums = pop_lines()
    evs = sorted((event_of(cl) for cl in cluster(r2w)), key=lambda e: e["first"], reverse=True)
    today_rows = [r for r in r2w if r["t"].astimezone(KST).date() == today]
    sec_list = dk.section("관련 뉴스", side_bars(today_rows, r2w)
                          + H.timeline_title().replace("</span>Timeline", "</span>News Timeline", 1)
                          + f'<div style="margin:4px 0 0;">{news_timeline(evs, days[::-1])}</div>',   # 증시 전망처럼 영어 제목 (2026-11-13 사용자)
                          line=False)   # 제목 아래 구분선 · 오른쪽 `읽는 법` 없음 (2026-11-13 사용자)
    n_pop = 0

    op = H.operator_box([
        ("규칙", RULES), ("모으기", f"키워드 /{iran['pat']}/ — 공용 뉴스(CNBC 8일 보관) {iran['n_store']}건 + 구글 뉴스 한국어(하루씩, 42일) {iran['n_gn']}건, 겹침 제거. 100건 상한 닿은 날 {', '.join(sorted(iran['capped'])) or '없음'}"),
        ("11-02 ~ 11-04 빈칸", "수집 버그 아님 — 공용 뉴스는 CNBC 만 · 8일 보관(STORE_DAYS 8), 목업이 같이 읽던 종목 레이더 뉴스는 로컬 사본(11-02). 이 페이지는 자기 기록을 따로 쌓는다"),
        ("지난 2주", "목업 = 오늘 가진 가격 · 뉴스로 거슬러 셈. 운영 = 날마다 그날 값을 기록(issue_state_log.json → 상태 브랜치)"),
        ("코스피", "최근 10거래일 줄만 ^KS11 (미국 마지막 날까지). 사건표는 미국 장 같은 시간이라 EWY 유지"),
        ("방향 · 단계", "목업 = 글 패턴(SIDE_PAT · TALK). 운영 땐 공용 뉴스 처리 Groq 칸으로 옮길지 결정"),
        ("묶기", f"기사 {len(r2w)}건 → 사건 {len(evs)}개 (제목 글자 둘씩 겹침 {EV_SIM} · {EV_HOURS}시간 안, 사건 날짜 = 첫 보도 날). AI 0"),
        ("팝업 한 곳만", "한 곳만 보도한 사건은 one_pick(따옴표 발언 아닌 사건 낱말 ONE_HARD, 또는 통신사 ONE_WIRE)만 올림 — 11-13 24건 중 7, 11-12 34건 중 6. 나머지는 팝업에 없음"),
        ("사건 줄", "공용 뉴스(CNBC)가 든 묶음 = 우리 말 사실 줄(fact). 국내 기사만인 묶음 = 가운데 기사 제목에서 [속보] · (종합) · 그림 문자를 뗀 것 — 우리 말로 다시 쓰려면 AI 한 줄 필요(미정)"),
        ("팝업", f"요약 줄 2개 이상 = {n_pop}건 (홈 news_summaries_home.json = CNBC 만)"),
        ("standby 정규식", f"CEASEFIRE 48시간 {sum(SB.topic_of(x) == 'CEASEFIRE' for x in items)}건 — 이 페이지 키워드 묶음보다 적게 잡힘"),
        ("그림자 스캔", "11-09 · 11-10 서명 1위 휴전 · 종전(0.65 · 0.39), 장전 없음(뉴스 3건 미달)"),
        ("검증 3-a", "전쟁 · 테러 사건 전 신호 1.12배(7건) · GPR 0.84~1.17 — 화면에 ‘포착’ 단언 금지"),
        ("상태 규칙", "뉴스 늘어남 = 48시간 ≥ 3 · 평소 2배 / 시장 = 묶음(유가 · 주식 · 안전 자산) 안 2개 이상 종전 방향 1σ, 하나는 2σ"),
        ("놓친 등록", "11-04 유가 −8.3% · XLE vs S&P −6.3%p 3.9σ = 틀 R 기준 넘음. 자동 등록(11-11~) 전이라 미등록. 거슬러 등록하지 않음"),
    ])
    body = (top + q + head + qcards + sec_list + op)
    body = body.replace('data-cards="1" ', "")   # data-cards 는 테마(엔비디아 탭) JS 가 글 머리로 옮긴다 — 이 페이지 카드는 제자리에
    body = dk.fix_colons(f'<div data-head-title="이슈 모니터링" data-seo-lead="{dk.esc("이슈 모니터링 — " + iran["q"] + " 지금 " + st)}">{body}</div>')
    return body


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print(dk.write_mock(build(), os.path.join(OUT, "mock_issue_watch.html"), "이슈 모니터링"))
