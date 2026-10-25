"""radar.json (+ narrative.json) → Blogger 본문 HTML (기획 9절, 2026-10-25 다시 기획). 숫자 · 순서 · 머리 문장은 파이썬, 헤드라인 · 설명 · 경로 문장은 narrative.json.

구획: 맨 앞 요약(p[data-seo-lead]) → 인물 목록(이름 · 오늘 가장 강한 발언 · 닿는 곳) → (숨김) h2 발언 + 인물별 발언 묶음 + 읽는 법 카드.
발언 카드 = 헤드라인 → 인물 · 시각 · 출처 → 설명 → 닿는 곳(경로 → 자산 + 한 문장) → 그날 시장(D 일 등락 · 평소 대비) → 새로운가 → 다음 날짜 → 라벨.
인물 페이지 끝 = 말과 행동 · 신뢰 기록 (정보 수집 중, 90일 뒤).
문체: 헤드라인 = 명사형(keep_tone), 그 밖 = 합니다체(dk.formal). 출처 · 면책 꼬리말 없음 — 블로그 공통 푸터.
출력: output/radar_body.html · output/radar.html(미리보기) · output/title.txt · output/radar_mock.html(테마 목업, 로컬만)
"""

import datetime
import html as html_mod
import json
import os
import sys

import config
import paths

sys.path.insert(0, os.path.join(config.BASE_DIR, "..", "stock-radar"))
try:
    import universe as _uni   # 종목 한국어 이름 (테슬라 · 엔비디아 …)
except Exception:  # noqa: BLE001
    _uni = None

sys.path.insert(0, os.path.join(config.BASE_DIR, ".."))
import design_kit as dk  # noqa: E402

KST = datetime.timezone(datetime.timedelta(hours=9))
TITLE_NAME = "주요 인물 발언"   # 2026-10-21 사용자: "트럼프 · 연준 · 월가 인물 발언"은 너무 길다 — 짧게, 제목에 날짜 없음(날짜는 본문 글자)
SLUG_NAME = "market moving remarks"
LABELS = ["인물 발언", "미국 증시", "자동 리포트"]
MAX_SIGNALS_PER_PERSON = 3
SEO_LEAD_MAX = 120
COLLECT_SINCE = "2026-10-22"   # record_store 가 발언 · 신호를 쌓기 시작한 날 (데이터-기록-계획 A3-1 2번)
COLLECT_OPEN = "2027-01-20"    # 90일 뒤 — 말 대 행동 · 신뢰 기록을 여는 날 (기획 9-1, 2026-10-25 사용자: 영역은 두고 "정보 수집 중")
REF_DIFF = 1.15   # 과거 참고: 발언 날 중앙값이 아무 날의 이 배수 이상일 때만 "더 움직였다", 아니면 "차이 없음" (판단 유보 규칙)
REL_BIG = 1.5     # 그날 시장: 평소의 이 배수 이상이면 "평소의 n배" 를 쓴다

PREVIEW = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__</title></head>
<body style="max-width:900px;margin:0 auto;padding:16px;background:#fff;"><h1 style="font-size:26px;">__TITLE__</h1>__BODY__</body></html>"""

_esc = dk.esc


def today_kst():
    return datetime.datetime.now(KST).strftime("%Y-%m-%d")


def korean_date(d):
    y, m, dd = d.split("-")[:3]
    return f"{int(y)}년 {int(m)}월 {int(dd)}일"


def korean_md(d):
    _, m, dd = d.split("-")[:3]
    return f"{int(m)}월 {int(dd)}일"


def post_title(d):
    return TITLE_NAME   # 날짜는 제목이 아니라 본문 첫 줄 글자로 (2026-10-21 사용자). 발행 쪽 '같은 글 찾기'는 제목 대신 주소 날짜로 (publish.py)


GROUP_COLOR = {"policy": "#1D4ED8", "investor": "#B45309", "commentator": "#7C3AED", "ceo": "#0F766E"}   # 인물군 색 — 동그라미 배지
PHOTOS_PATH = os.path.join(config.BASE_DIR, "ref", "people_photos.json")   # speaker → {file, license, author, page} (위키미디어 공용 자유 라이선스)
PHOTO_BASE = "https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/images/people/"   # 우리 gh-pages 에 복사해 둔 사진 (핫링크 아님). 목업은 로컬 images/people
PHOTO_PUBLIC = {"trump", "bessent", "lutnick", "greer", "fed"}   # 공직자(+기관)만 사진 (2026-10-21 사용자 결정: "공적인 사람만"). 민간인은 초상권 · 퍼블리시티권 때문에 글자 동그라미
REFS_PATH = os.path.join(config.BASE_DIR, "ref", "reaction_refs.json")   # 과거 참고치 (reaction_refs.py) — 인물 × 주제, 지금은 트럼프 × 무역 · 연준 × Fed 둘
PATH_KO = {"self": "본인 글", "office": "기관 발표", "trade": "매매 공시", "report": "보도"}


def _photos():
    try:
        with open(PHOTOS_PATH, encoding="utf-8") as f:
            return {k: v for k, v in json.load(f).items() if k in PHOTO_PUBLIC}
    except (OSError, ValueError):
        return {}


def _refs():
    try:
        with open(REFS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _avatar(p, size=40):
    """이름 앞 동그라미 — 얼굴 사진(2026-10-21 사용자: "조그맣게라도 얼굴을"; 운영지침 4-6 의 인물 사진 금지는 사용자 결정으로 예외, 자유 라이선스 사진만 · 출처 표기는 공통 푸터 크레딧).
    사진이 없는 인물은 성(姓) 첫 글자 · 인물군 색."""
    ph = _photos().get(p["speaker"])
    if ph:
        return (f'<img src="{PHOTO_BASE}{_esc(ph["file"])}" alt="" width="{size}" height="{size}" loading="lazy" '
                f'style="flex:none;width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;background:#F1F5F9;border:1px solid #E2E8F0;"/>')
    ch = p["name_ko"].split()[-1][0]
    return (f'<span aria-hidden="true" style="display:inline-flex;flex:none;align-items:center;justify-content:center;width:{size}px;height:{size}px;border-radius:50%;'
            f'background:{GROUP_COLOR.get(p["group"], "#94A3B8")};color:#fff;font-size:{int(size * 0.45)}px;font-weight:700;line-height:1;">{ch}</span>')


def kst_hm(utc_iso):
    dt = datetime.datetime.strptime(utc_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(KST).strftime("%m-%d %H:%M")


def _topic(t):
    return config.TOPIC_KO.get(t, t)


def _dir_pill(d):
    return dk.pill(config.DIR_KO.get(d, d), d if d in ("positive", "negative") else "neutral", bare=True)


def _card(s, cards):
    """narrate 카드 {headline, detail, path} — 없으면 None (영문 원문을 그대로 내보내지 않는다, 운영지침 4-3 · D3-1f)."""
    return (cards or {}).get(s["lead"]["id"])


def _names(p):
    """그 인물을 부르는 말 — 긴 것부터 (2026-10-25 사용자: 인물 페이지 안에서는 이름을 되풀이하지 않는다)."""
    full = p["name_ko"]
    last = full.split()[-1]
    extra = {"trump": ["트럼프 대통령", "도널드 트럼프"], "fed": ["연준", "연방준비제도", "워시 의장", "케빈 워시"], "wood": ["캐시 우드", "ARK"],
             "huang": ["엔비디아 CEO 젠슨 황"], "musk": ["테슬라 CEO 일론 머스크"], "altman": ["오픈AI CEO 샘 올트먼"]}.get(p["speaker"], [])
    return sorted({full, last, *extra}, key=len, reverse=True)


def _split_head(p, h):
    """헤드라인 '일론 머스크, 스카이댄스 …' → ('일론 머스크, ', '스카이댄스 …'). 이름으로 시작하지 않으면 ('', h)."""
    for n in _names(p):
        for sep in (", ", " , ", " "):
            if h.startswith(n + sep) and len(h) > len(n) + len(sep):
                return h[:len(n) + len(sep)], h[len(n) + len(sep):]
    return "", h


_JOSA = ("이 ", "가 ", "은 ", "는 ", "도 ")


def _strip_subject(p, t):
    """설명 '일론 머스크가 스카이댄스에 …' → '스카이댄스에 …' (주어 이름 + 조사만, 문장 가운데 이름은 그대로)."""
    for n in _names(p):
        for j in _JOSA:
            if t.startswith(n + j) and len(t) > len(n) + len(j) + 4:
                return t[len(n) + len(j):]
    return t


def _sub(x, color=None):
    return f'<span style="display:block;color:{color or dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};margin-top:2px;">{x}</span>'


# ── 발언 카드 줄 (기획 9-4) ───────────────────────────────────────────────

def _asset_name(sym):
    """`테슬라(TSLA)` — 종목은 한국어 이름(종목 레이더 목록에 있을 때), ETF · 지수는 경로표 이름."""
    if sym in paths.ASSET_KO:
        return paths.asset_label(sym)
    try:
        return f"{_uni.name(sym)}({sym})" if _uni else sym
    except KeyError:
        return sym


def _path_line(s, card):
    """`테슬라(TSLA) : 장기 인도량 목표 상향, 생산 규모 · 점유율 기대 자극` (2026-10-25 사용자: 자산 이름을 앞에, 뉴스 문체).
    AI 구절이 없으면 `자산 : 경로 이름`."""
    pth = s.get("path")
    if not pth:
        return []
    # 종목은 상세 페이지가 있으면 파란색 링크 · 없으면 검정, 굵게 없음 (2026-10-25 사용자). ETF · 지수 · 유가 · 환율은 검정
    names = " · ".join(dk.stock_link(a, _esc(_asset_name(a))) for a in pth["assets"])
    why = dk.headline((card or {}).get("path") or "") or paths.CHANNEL_KO[pth["channel"]]
    return [_sub(dk.keep_tone(f'{names} : {_esc(why)}'), "#111")]


def _reaction_line(s):
    """`그날 시장 : 10-23 · 유가(WTI) −1.2% · 에너지 업종(XLE) +0.8% (평소의 1.6배)` — 등락은 dk.tint 가 색을 칠한다. 종가 전이면 "장 마감 뒤 표시"."""
    r = s.get("reaction")
    if not r:
        return []
    parts = []
    for a in r["assets"]:
        if a.get("pending"):
            continue
        v = f'{a["bp"]:+.1f}bp' if "bp" in a else f'{a["ret"]:+.2f}%'
        rel = f' (평소의 {a["rel"]}배)' if a.get("rel") and a["rel"] >= REL_BIG else ""
        parts.append(f'{paths.asset_label(a["symbol"])} {v}{rel}')
    basis = " (보도 기준)" if s["source_kind"] != "primary" else ""
    m = r.get("market")
    if parts and m:
        parts.append(f'시장 전체 S&P 500 {m["ret"]:+.2f}%')   # 비교 대상 — 그 자산만 움직였는지, 시장이 다 같이 움직였는지
    if not parts:
        return [_sub(f'<b style="color:#111;">그날 시장</b>{_esc(basis)} : {_esc(r["day"][5:].replace("-", "."))} 장 마감 뒤 표시', "#111")]
    text = f'<b style="color:#111;">그날 시장</b>{_esc(basis)} : {_esc(r["day"][5:].replace("-", "."))} · ' + _esc(" · ".join(parts))
    return [_sub(dk.tint(text), "#111")]


def _novelty_line(s):
    n = s.get("novelty")
    if not n:
        return []
    # 라벨 없이 보조 줄 글자(시각 · 출처와 같은 회색 14px) — 2026-10-25 사용자
    if n.get("first30"):
        return [_sub("30일 만에 처음 나온 주제")]
    if n.get("streak", 0) >= 2:
        return [_sub(f'{n["streak"]}일째 같은 주제')]
    return []


def _next_line(s):
    n = s.get("next")
    if not n:
        return []
    return [_sub(f'<b style="color:#111;">다음 날짜</b> : {_esc(korean_md(n["day"]))} {_esc(n["kind"])} (D-{n["days_left"]})', "#111")]


def _signal_item(p, s, cards):
    c = _card(s, cards)
    if not c:
        return ""   # 서술 없는 신호는 싣지 않는다 (영문 원문 노출 금지) — sec_people 이 빈 항목을 거른다
    h, detail = c["headline"], _strip_subject(p, c.get("detail") or "")
    who_h, rest_h = _split_head(p, h)
    # 이름은 화면에서 숨기되 글자에는 남긴다 — 홈 인물 발언 카드가 이 헤드라인 글자를 그대로 읽어 "누가"를 보여 준다 (index.html radarRows)
    h_html = (f'<span style="display:none;">{_esc(who_h)}</span>' if who_h else "") + _esc(rest_h)
    url = s["lead"]["url"] if (s["lead"]["url"] or "").startswith("http") else None
    who = s["lead"]["sub_speaker"].title() if p["speaker"] == "fed" and s["lead"]["sub_speaker"] not in (None, "fomc") else ""
    meta = ([who] if who else []) + [kst_hm(s["first_at"])]   # 인물 이름은 뺀다 — 인물 페이지 제목과 겹친다 (2026-10-25 사용자). 연준은 연설자만
    if s["source_kind"] == "primary":
        meta.append(PATH_KO.get(s["attribution"], "원문"))
    if s["n_reports"]:
        meta.append(f"보도 {s['n_reports']}곳")
    pub = (s["lead"].get("publisher") or "").strip()   # 매체명을 보이는 글자로 (2026-10-21, 운영지침 D4-3)
    if pub and pub != "googlenews" and s["source_kind"] != "primary":
        meta.append(pub)
    subs = _path_line(s, c) + _novelty_line(s) + _next_line(s)   # 요약 줄(detail)은 공용 카드가 헤드라인 바로 아래 검정으로 (2026-10-25 사용자)   # 그날 시장 줄은 뺐다 (2026-10-25 사용자: 발언 효과로 오해 · 카드마다 반복 · 해석 어려움) — 값은 기록(record_store)에만 쌓아 90일 뒤 통계로
    if not s.get("path"):   # 닿는 곳이 없는 발언만 대상 줄 (닿는 곳이 있으면 자산 이름이 대상이다)
        targets = [x for x in s["companies"][:4]] + [config.SECTOR_KO.get(x, x) for x in s["sectors"][:2]]
        if targets:
            subs.append(_sub("대상 : " + _esc(" · ".join(targets))))
    pills = [dk.pill(_topic(s["topic"]), bare=True), _dir_pill(s["direction"]), dk.pill(f"강도 {s['intensity']}", bare=True)]
    # 공용 뉴스 카드 (design_kit.news_item) — 라벨 줄 오른쪽에 시각 · 출처 · 보도 수 (2026-10-25 사용자)
    return dk.news_item(h_html, url, detail, subs, " ".join(pills), meta)


# ── 구획 ────────────────────────────────────────────────────────────────

def sec_seo_lead(r, d, cards):
    """글 맨 앞 두 줄 (2026-10-21 사용자): 첫 줄 = 가장 강한 발언(인물, 내용), 둘째 줄 = 날짜 · 최근 24시간 발언 수 · 인물 수."""
    _, m, dd = d.split("-")
    top = r["people"][0]["signals"][0] if r["people"] else None
    c = _card(top, cards) if top else None
    first = f"<b>가장 강한 발언</b> : {_esc(c['headline'])}" if c else ""
    second = f"{int(m)}월 {int(dd)}일 기준 최근 24시간 시장 발언 {r['event_count']}건 · {r['people_count']}명"
    if r.get("only_reports"):
        second += " · 오늘은 보도된 발언만"
    lines = [x for x in (first, second) if x]
    return f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">{"<br>".join(lines)}</p>'


def _collecting_card():
    """말 대 행동 · 신뢰 기록 — 영역은 두고 "정보 수집 중" (2026-10-25 사용자). 90일 뒤 record_store 기록으로 채운다."""
    sub = (f"{korean_date(COLLECT_SINCE)}부터 발언과 그 뒤 행동(행정명령 · 관세 발효 · 매매 · 실적 발표)을 기록하고 있습니다. "
           f"90일이 쌓이는 {korean_date(COLLECT_OPEN)} 뒤에 이 자리에서 보여 드립니다.")
    return dk.state_card("말과 행동 · 신뢰 기록", kind="neutral", right_html=dk.pill("정보 수집 중", "neutral", bare=True), sub_html=_esc(sub))


def sec_people(r, cards):
    """인물별 발언 묶음 — 인물마다 <div data-person-page> (소제목 · 발언 카드 · 더 보기 · 말과 행동 카드). 화면에서는 테마 JS 가 처음에 숨기고,
    인물 목록에서 인물을 누르면 그 묶음을 옮겨 보여 준다. JS 없으면 목록 아래 그대로 보인다. 홈 인물 발언 카드는 h2 '발언' 뒤의 소제목(data-sub) · li 를 읽는다."""
    out = []
    for p in r["people"]:
        items = [x for x in (_signal_item(p, s, cards) for s in p["signals"]) if x]
        if not items:
            continue
        shown, more = items[:MAX_SIGNALS_PER_PERSON], items[MAX_SIGNALS_PER_PERSON:]
        page = [dk.sub_label(f"{p['name_ko']} ({p['title_ko']})"), dk.item_rules(shown, sub=True, indent=dk.ALIGN_PX)]
        if more:
            # 펼친 목록의 첫 기사 위에도 구분선 (2026-10-21 사용자: 기사 영역은 더 보기를 펼쳐도 선이 이어져야 한다)
            ml = dk.item_rules(more, sub=True, indent=dk.ALIGN_PX).replace(f"padding:2px {dk.ALIGN_PX}px ", f"padding:{dk.RULE_GAP - dk.NEWS_VP}px {dk.ALIGN_PX}px ", 1).replace("line-height:" + dk.LH_BODY + ";", "line-height:" + dk.LH_BODY + ";box-shadow:inset 0 1px 0 #E2E8F0;", 1)
            page.append(dk.fold(f"{p['name_ko']} 발언 {len(more)}건 더 보기", ml).replace("margin-top:8px;margin-bottom:8px;", "margin:0 0 8px;", 1))
        page.append(_collecting_card())
        out.append(f'<div data-person-page="{p["speaker"]}">{"".join(page)}</div>')
    return "".join(out)


def _list_row(p, cards, first):
    """인물 목록 한 줄 (기획 9-4): 동그라미 · 이름 · 직함, 아래 오늘 가장 강한 발언 헤드라인, 그 아래 닿는 곳 자산. 건수 · 7일 비교는 없다."""
    top = p["signals"][0]
    c = _card(top, cards) or {}
    head = _split_head(p, c.get("headline") or "")[1]   # 줄에 이름이 이미 있다
    pth = top.get("path")
    touch = " · ".join(paths.asset_label(a) for a in pth["assets"]) if pth else ""
    chev = ('<svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M6 4l4 4-4 4"/></svg>')
    photo = (' data-photo="' + PHOTO_BASE + _esc(_photos()[p["speaker"]]["file"]) + '"') if p["speaker"] in _photos() else ""
    n = len(p["signals"])
    return (
        f'<a href="#" data-person="{p["speaker"]}" data-name="{_esc(p["name_ko"])}" data-title="{_esc(p["title_ko"])}"{photo} '
        f'style="display:flex;align-items:flex-start;gap:12px;padding:13px {dk.ALIGN_PX}px;{"" if first else "border-top:1px solid #E2E8F0;"}color:#111;text-decoration:none;cursor:pointer;">'
        f'{_avatar(p)}'
        f'<span style="flex:1 1 auto;min-width:0;">'
        f'<span style="display:block;font-size:{dk.SMALL};line-height:{dk.LH_CARD};"><b>{_esc(p["name_ko"])}</b> <span style="color:{dk.SUB};font-size:{dk.TINY};">{_esc(p["title_ko"])} · 오늘 {n}건</span></span>'
        + (f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:#111;margin-top:2px;word-break:keep-all;">{dk.keep_tone(_esc(head))}</span>' if head else "")
        + (f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};margin-top:2px;">닿는 곳 : {_esc(touch)}</span>' if touch else "")
        + f'</span><span style="flex:none;color:#94A3B8;display:inline-flex;margin-top:10px;">{chev}</span></a>')


def sec_people_list(r, cards):
    rows = [_list_row(p, cards, i == 0) for i, p in enumerate(r["people"])]
    return f'<div data-people-list="1" style="margin:0 0 8px;">{"".join(rows)}</div>'


def _ref_text(sp, prof, refs):
    """과거 참고 — 참고치가 있는 인물 × 주제면 한 줄, 없으면 "정보 수집 중" (영역 유지, 2026-10-25 사용자)."""
    have = refs.get(sp) or {}
    topic = next((t["name"] for t in prof["topics"] if t["name"] in have), None)
    if not topic:
        return ("정보 수집 중 · 이 인물의 주제별 발언이 90일 쌓이면 \"같은 종류의 발언이 있던 날 시장\"을 보여 드립니다.", "")
    v = have[topic]
    sym = refs.get("symbol", "S&P 500")
    if v["base_abs"] and v["med_abs"] / v["base_abs"] >= REF_DIFF:
        text = f'{v["label"]} {sym} 은 보통 ±{v["med_abs"]}% 움직였습니다. {v["base_label"]} ±{v["base_abs"]}% 보다 컸습니다.'
    else:
        text = f'{v["label"]} {sym} 은 보통 ±{v["med_abs"]}% 움직였습니다. {v["base_label"]}(±{v["base_abs"]}%)과 차이가 없었습니다.'
    sub = f'{v["period"]} {v["n"]}일 · 오른 날 {v["up_pct"]}% ({v["base_label"]} {v["base_up"]}%) · 단순 비교, 플라시보 검정 전'
    return (text, sub)


def _head_row(title, body_html, first, right=""):
    return (f'<span style="display:block;padding:{17 - dk.VP}px 12px;{"" if first else dk.MULTI_SEP}">'
            f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;">'
            f'<span style="font-weight:700;color:#111;font-size:16px;line-height:22px;">{_esc(title)}</span>'
            + (f'<span style="text-align:right;color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};">{right}</span>' if right else "")
            + f'</span><span style="display:block;margin-top:4px;">{body_html}</span></span>')


def sec_person_head(r):
    """인물 상세 첫 카드 `이 사람 말 읽는 법` (기획 9-4) — 발언 경로 · 과거 참고(또는 정보 수집 중) · 다음 날짜. 평소엔 숨김, 테마 JS 가 제목 아래로 옮긴다
    (data-person-strip 이름은 테마 JS 호환용). 건수 통계 카드(대상 국가 · 말한 것 · 키워드)는 뺐다 — 뜻이 없다 (2026-10-25 사용자)."""
    refs = _refs()
    out = []
    for p in r["people"]:
        prof = (r.get("profiles") or {}).get(p["speaker"])
        if not prof:
            continue
        rows = []
        pth = " · ".join(f'{PATH_KO.get(k, k)} {v}' for k, v in sorted(prof["paths"].items(), key=lambda kv: -kv[1]))
        why = ("본인 글 · 기관 발표는 직접 낸 말이고, 보도는 언론이 옮긴 말이라 앞뒤 맥락이 빠졌을 수 있습니다." if prof["paths"].get("report")
               else "모두 본인 글 · 기관 발표라 직접 낸 말 그대로입니다.")
        rows.append(("발언 경로", f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:#111;">{_esc(pth)}</span>'
                     f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};margin-top:2px;">{_esc(why)}</span>', "최근 30일"))
        text, sub = _ref_text(p["speaker"], prof, refs)
        rows.append(("과거 참고", f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:#111;word-break:keep-all;">{_esc(text)}</span>'
                     + (f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};margin-top:2px;">{_esc(sub)}</span>' if sub else ""), ""))
        nxt = next((s["next"] for s in p["signals"] if s.get("next")), None)
        if nxt:
            rows.append(("다음 날짜", f'<span style="font-size:{dk.TINY};line-height:{dk.LH_TINY};color:#111;">{_esc(korean_md(nxt["day"]))} {_esc(nxt["kind"])}</span>',
                         f'<b style="color:#111;">D-{nxt["days_left"]}</b>'))
        head = (f'<span style="display:block;padding:{14 - dk.VP}px 12px 0;font-size:{dk.TINY};line-height:{dk.LH_TINY};font-weight:700;color:#111;">이 사람 말 읽는 법</span>')
        body = "".join(_head_row(t, b, i == 0, right=rt) for i, (t, b, rt) in enumerate(rows))
        body = body.replace(f'padding:{17 - dk.VP}px 12px;">', f'padding:{17 - dk.VP}px 12px;{dk.MULTI_SEP}">', 1)
        card = f'<div data-cards="1" style="margin:0 0 8px;"><span style="{dk.MULTI}">{head}{body}</span></div>'
        out.append(f'<div data-person-strip="{p["speaker"]}" hidden>{card}</div>')
    return "".join(out)


def build_body(r, n, d):
    """글 = 맨 앞 요약 → 인물 목록(이름 · 오늘 가장 강한 발언 · 닿는 곳) → (숨김) 인물별 발언 묶음 · 읽는 법 카드 (기획 9-4, 2026-10-25).
    인물을 누르면 테마 JS 가 목록 자리에 이름 제목 · 읽는 법 카드 · 발언 카드 · 말과 행동 카드를 보여 준다. 언급 대상 · 키워드 · 7일 비교는 뺐다."""
    cards = (n or {}).get("cards")
    body = "\n".join([
        dk.WRAP_OPEN,
        sec_seo_lead(r, d, cards),
        sec_people_list(r, cards),
        dk.h2("발언", line=True).replace("<h2 ", '<h2 data-person-pages="1" ', 1),   # 홈 카드가 읽는 구획 제목 — 화면에서는 JS 가 숨긴다
        sec_people(r, cards),
        sec_person_head(r),
        dk.WRAP_CLOSE,
    ])
    return dk.fix_colons(dk.formal(dk.align_titles(body)))   # 카드 밖 구획 제목은 좌측 기준선(ALIGN_PX) (2026-10-23 사용자)


def render(radar_path=None, narrative_path=None, output_dir=None):
    output_dir = output_dir or config.OUTPUT_DIR
    with open(radar_path or os.path.join(output_dir, "radar.json"), encoding="utf-8") as f:
        r = json.load(f)
    n = None
    np_ = narrative_path or os.path.join(output_dir, "narrative.json")
    if os.path.exists(np_):
        with open(np_, encoding="utf-8") as f:
            n = json.load(f)
    if not r["event_count"]:
        print("[html] 신호 0개 — 본문을 만들지 않는다 (게시 없음)")
        return None
    d = today_kst()
    title = post_title(d)
    body = build_body(r, n, d)   # 글 끝 "AI 서술" 줄 없음 — 공통 푸터의 AI 고지와 중복 (2026-10-25 사용자)
    body_path = os.path.join(output_dir, "radar_body.html")
    with open(body_path, "w", encoding="utf-8") as f:
        f.write(body)
    with open(os.path.join(output_dir, "radar.html"), "w", encoding="utf-8") as f:
        f.write(PREVIEW.replace("__TITLE__", _esc(title)).replace("__BODY__", body))
    with open(os.path.join(output_dir, "title.txt"), "w", encoding="utf-8") as f:
        f.write(title)
    mock = dk.write_mock(body, os.path.join(output_dir, "radar_mock.html"), title)
    print(f"[html] {len(body):,}자 → {body_path}" + (f" · 목업 {mock}" if mock else ""))
    return body_path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    render()
