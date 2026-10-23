"""radar.json (+ narrative.json) → Blogger 본문 HTML (기획 3절). 숫자 · 순서 · 머리 문장은 파이썬, 카드 헤드라인 · 설명은 narrative.json.

구획 (탭 둘):
  오늘   맨 앞 요약(p[data-seo-lead]) → 머리 강조 카드(인물 · 건수 · 가장 강한 발언) → 발언(인물 순, 신호마다 기사형 항목) → 오늘 시장 맥락
  추이   인물별 추이(최근 7일 vs 직전 7일, 달라진 줄만) — 없으면 탭째 생략
문체: 헤드라인 = 명사형(뉴스 문체, keep_tone), 그 밖 = 합니다체(dk.formal). 출처 · 면책 꼬리말 없음 — 블로그 공통 푸터.
'내일 볼 것'(과거 반응 통계)은 아직 없다 — 1차 발언 90일이 쌓인 뒤(기획 6절 7단계). 트럼프 반응 통계는 트럼프 리포트에 남아 있다.

출력: output/radar_body.html · output/radar.html(미리보기) · output/title.txt · output/radar_mock.html(테마 목업, 로컬만)
"""

import datetime
import html as html_mod
import json
import os
import sys

import config

sys.path.insert(0, os.path.join(config.BASE_DIR, ".."))
import design_kit as dk  # noqa: E402

KST = datetime.timezone(datetime.timedelta(hours=9))
TITLE_NAME = "주요 인물 발언"   # 2026-10-21 사용자: "트럼프 · 연준 · 월가 인물 발언"은 너무 길다 — 짧게, 제목에 날짜 없음(날짜는 본문 글자)
SLUG_NAME = "market moving remarks"
LABELS = ["인물 발언", "미국 증시", "자동 리포트"]
TAB_TODAY, TAB_TREND = "오늘", "추이"
MAX_SIGNALS_PER_PERSON = 3
SEO_LEAD_MAX = 120

PREVIEW = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__</title></head>
<body style="max-width:900px;margin:0 auto;padding:16px;background:#fff;"><h1 style="font-size:26px;">__TITLE__</h1>__BODY__</body></html>"""

_esc = dk.esc


def today_kst():
    return datetime.datetime.now(KST).strftime("%Y-%m-%d")


def korean_date(d):
    y, m, dd = d.split("-")[:3]
    return f"{int(y)}년 {int(m)}월 {int(dd)}일"


def post_title(d):
    return TITLE_NAME   # 날짜는 제목이 아니라 본문 첫 줄 글자로 (2026-10-21 사용자). 발행 쪽 '같은 글 찾기'는 제목 대신 주소 날짜로 (publish.py)


GROUP_COLOR = {"policy": "#1D4ED8", "investor": "#B45309", "commentator": "#7C3AED", "ceo": "#0F766E"}   # 인물군 색 — 동그라미 배지
STRIP_COLORS = ["#1D4ED8", "#B45309", "#0F766E", "#7C3AED", "#BE123C", "#4D7C0F"]   # 인물 띠의 주제 색(인물마다 많이 말한 순으로 고정 배정), 그 밖은 회색
STRIP_OTHER = "#94A3B8"
BAR_NOW, BAR_PREV = "#0F766E", "#CBD5E1"   # 주제 반복 막대 — 최근 7일 · 직전 7일


PHOTOS_PATH = os.path.join(config.BASE_DIR, "ref", "people_photos.json")   # speaker → {file, license, author, page} (위키미디어 공용 자유 라이선스)
PHOTO_BASE = "https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/images/people/"   # 우리 gh-pages 에 복사해 둔 사진 (핫링크 아님). 목업은 로컬 images/people


PHOTO_PUBLIC = {"trump", "bessent", "lutnick", "greer", "fed"}   # 공직자(+기관)만 사진 (2026-10-21 사용자 결정: "공적인 사람만"). 민간인은 초상권 · 퍼블리시티권 때문에 글자 동그라미


def _photos():
    try:
        with open(PHOTOS_PATH, encoding="utf-8") as f:
            return {k: v for k, v in json.load(f).items() if k in PHOTO_PUBLIC}
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
            f'background:{GROUP_COLOR.get(p["group"], STRIP_OTHER)};color:#fff;font-size:{int(size * 0.45)}px;font-weight:700;line-height:1;">{ch}</span>')


def kst_hm(utc_iso):
    dt = datetime.datetime.strptime(utc_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(KST).strftime("%m-%d %H:%M")


def _topic(t):
    return config.TOPIC_KO.get(t, t)


def _dir_pill(d):
    return dk.pill(config.DIR_KO.get(d, d), d if d in ("positive", "negative") else "neutral", bare=True)


def _card_text(s, cards):
    """(헤드라인, 설명). 서술(narrate)이 없는 신호는 (None, "") — 영문 원문(quote · 기사 제목)을 그대로 내보내지 않는다
    (2026-10-21, 운영지침 4-3 · D3-1f: 매체 문장 재배포 금지). 호출자가 None 이면 그 항목을 뺀다."""
    c = (cards or {}).get(s["lead"]["id"])
    if c:
        return c["headline"], c["detail"]
    return None, ""


# ── 구획 ────────────────────────────────────────────────────────────────

def sec_seo_lead(r, d, cards):
    """글 맨 앞 두 줄 (2026-10-21 사용자): 첫 줄 = 가장 강한 발언(인물, 내용), 둘째 줄 = 날짜 · 최근 24시간 발언 수 · 인물 수.
    이름 나열 · 상태 카드("발언 N건 · M명")는 뺐다 — 위 글자와 겹친다. 파이썬 값만, data-lead 없음 (홈 카드가 머리로 읽지 않게)."""
    _, m, dd = d.split("-")
    top = r["people"][0]["signals"][0] if r["people"] else None
    h = _card_text(top, cards)[0] if top else None
    first = f"<b>가장 강한 발언</b> : {_esc(h)}" if h else ""   # 헤드라인이 "인물, 무엇" 꼴이라 이름을 따로 붙이지 않는다
    second = f"{int(m)}월 {int(dd)}일 기준 최근 24시간 시장 발언 {r['event_count']}건 · {r['people_count']}명"
    if r.get("only_reports"):
        second += " · 오늘은 보도된 발언만"
    lines = [x for x in (first, second) if x]
    return f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">{"<br>".join(lines)}</p>'


def _signal_item(p, s, cards):
    h, detail = _card_text(s, cards)
    if not h:
        return ""   # 서술 없는 신호는 싣지 않는다 (영문 원문 노출 금지) — sec_people 이 빈 항목을 거른다
    url = s["lead"]["url"] if (s["lead"]["url"] or "").startswith("http") else None
    head = (f'<a href="{_esc(url)}" target="_blank" rel="noopener" style="color:#111;font-weight:700;text-decoration:none;">{_esc(h)}</a>'
            if url else f"<span style='color:#111;font-weight:700;'>{_esc(h)}</span>")
    head = dk.keep_tone(head)   # 헤드라인은 명사형 그대로 (가이드라인: 뉴스 · 중요 이슈 문체)
    who = s["lead"]["sub_speaker"].title() if p["speaker"] == "fed" and s["lead"]["sub_speaker"] not in (None, "fomc") else ""
    meta = [f"{p['name_ko']}{' ' + who if who else ''}", kst_hm(s["first_at"])]
    if s["source_kind"] == "primary":
        meta.append({"self": "본인 글", "office": "기관 발표", "trade": "매매 공시"}.get(s["attribution"], "원문"))
    if s["n_reports"]:
        meta.append(f"보도 {s['n_reports']}곳")
    pub = (s["lead"].get("publisher") or "").strip()   # 매체명을 보이는 글자로 (2026-10-21, 운영지침 D4-3)
    if pub and pub != "googlenews" and s["source_kind"] != "primary":
        meta.append(pub)
    targets = [x for x in s["companies"][:4]] + [config.SECTOR_KO.get(x, x) for x in s["sectors"][:2]]
    subs = [_esc(" · ".join(meta))]
    if detail:
        subs.append(_esc(detail))
    if targets:
        subs.append("대상 : " + _esc(" · ".join(targets)))
    sub_html = "".join(f'<span style="display:block;color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};margin-top:2px;">{x}</span>'
                       for x in subs)
    pills = [dk.pill(_topic(s["topic"]), bare=True), _dir_pill(s["direction"]), dk.pill(f"강도 {s['intensity']}", bare=True)]
    # `보도된 발언` 라벨은 뺐다 (2026-10-21 사용자) — 보조 줄의 `보도 N곳 · 매체` 가 같은 뜻이고, 1차 자료는 `본인 글 · 기관 발표 · 매매 공시` 로 구분된다
    lab = f'<span style="display:block;line-height:1;margin:8px 0 0;">{" ".join(pills)}</span>'
    return f"{head}{sub_html}{lab}"


def sec_people(r, cards):
    """인물별 발언 묶음 — 인물마다 <div data-person-page> (소제목 · 발언 목록 · 더 보기). 화면에서는 테마 JS 가 처음에 숨기고,
    인물 목록에서 인물을 누르면 그 묶음을 복제해 보여 준다 (2026-10-21 사용자: 탭 없이 인물 목록 → 인물 상세). JS 없으면 목록 아래 그대로 보인다.
    홈 인물 발언 카드는 h2 '발언' 뒤의 소제목(data-sub) · li 를 읽는다 — 묶음 div 안이어도 찾는다."""
    out = []
    for p in r["people"]:
        items = [x for x in (_signal_item(p, s, cards) for s in p["signals"]) if x]
        if not items:
            continue
        shown, more = items[:MAX_SIGNALS_PER_PERSON], items[MAX_SIGNALS_PER_PERSON:]
        wide = lambda html: html   # 기사 목록 좌우 = 좌측 기준선 13px (item_rules indent, 구분선은 전체 폭) — 옛 +6(화면 가장자리 20) 규칙은 2026-10-23 사용자 기준선 13 으로 대체
        page = [dk.sub_label(f"{p['name_ko']} ({p['title_ko']})"), wide(dk.item_rules(shown, sub=True, indent=dk.ALIGN_PX))]
        if more:
            # 펼친 목록의 첫 기사 위에도 구분선 (2026-10-21 사용자: 기사 영역은 더 보기를 펼쳐도 선이 이어져야 한다 — 표 카드와 다름).
            # 펼친 목록은 별도 ul 이라 첫 li 에 선이 없고, 펼침 안쪽 위 여백 8 도 선 위에 있으면 안 된다
            ml = dk.item_rules(more, sub=True, indent=dk.ALIGN_PX).replace(f"padding:2px {dk.ALIGN_PX}px ", f"padding:{dk.RULE_GAP - dk.NEWS_VP}px {dk.ALIGN_PX}px ", 1).replace("line-height:" + dk.LH_BODY + ";", "line-height:" + dk.LH_BODY + ";box-shadow:inset 0 1px 0 #E2E8F0;", 1)
            fold = dk.fold(f"{p['name_ko']} 발언 {len(more)}건 더 보기", wide(ml)).replace("margin-top:8px;margin-bottom:8px;", "margin:0 0 8px;", 1)
            page.append(fold)
        out.append(f'<div data-person-page="{p["speaker"]}">{"".join(page)}</div>')
    return "".join(out)


REGIME_KO = {"Risk-On": "위험 선호", "Risk-Off": "위험 회피", "Neutral": "중립"}   # daily-report render_html.TERM_KO 와 같다


def sec_market(r):
    m = r.get("market")
    if not m or m.get("score") is None:
        return ""
    rows = [("시장 상태 점수", f"{m['score']}점", _esc(f"{REGIME_KO.get(m.get('label'), m.get('label') or '')} · 전날 대비 {m['delta']:+d}점" if m.get("delta") is not None else REGIME_KO.get(m.get("label"), m.get("label") or ""))),
            ("S&P 500", dk.arrow(m.get("spx_1d")), ""), ("나스닥", dk.arrow(m.get("ndx_1d")), "")]
    return dk.ccard(rows) + dk.muted(f"미국 증시 리포트 기준 · {m.get('as_of') or ''} 종가")


def _count_line(a, b, unit="건"):
    """`최근 7일 9건` 오른쪽 값과 `직전 7일 3건` 보조 줄 — 늘었으면 빨강 ▲, 줄었으면 파랑 ▼ (부호 규칙), 같으면 회색."""
    diff = a - b
    if diff > 0:
        d = f'<span style="color:{dk.UP};">▲{diff}</span>'
    elif diff < 0:
        d = f'<span style="color:{dk.DOWN};">▼{-diff}</span>'
    else:
        d = f'<span style="color:{dk.NOTE};">변화 없음</span>'
    return f"{a}{unit}", f"직전 7일 {b}{unit} {d}"


def sec_people_list(r):
    """추이 탭 인물 목록 (2026-10-21 사용자: 추이 탭이 먼저, 인물 사진 동그라미 + 이름이 세로로 쭉, 누르면 그 인물의 발언).
    한 줄 = 동그라미 · 이름 · 직함 · 오늘 건수 왼쪽, 최근 7일 건수 · 직전 7일 비교 오른쪽. 오늘 발언한 인물만, 강한 순(오늘 탭과 같다).
    줄을 누르면 테마 JS 가 오늘 탭의 그 인물 구획(data-person)을 복제해 목록 자리에 보여 주고 '목록으로' 버튼을 단다."""
    pt = r.get("people_trend") or {}
    rows = []
    for i, p in enumerate(r["people"]):
        t = pt.get(p["speaker"], {})
        val, sub = _count_line(t.get("days7", len(p["signals"])), t.get("prev7", 0))
        chev = ('<svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M6 4l4 4-4 4"/></svg>')
        rows.append(
            f'<a href="#" data-person="{p["speaker"]}" data-name="{_esc(p["name_ko"])}" data-title="{_esc(p["title_ko"])}"{(' data-photo="' + PHOTO_BASE + _esc(_photos()[p["speaker"]]["file"]) + '"') if p["speaker"] in _photos() else ""} style="display:flex;align-items:center;gap:12px;padding:13px {dk.ALIGN_PX}px;{"" if i == 0 else "border-top:1px solid #E2E8F0;"}'
            f'color:#111;text-decoration:none;cursor:pointer;">'
            f'{_avatar(p)}'
            f'<span style="flex:1 1 auto;min-width:0;"><span style="display:block;font-size:{dk.SMALL};line-height:{dk.LH_CARD};font-weight:700;">{_esc(p["name_ko"])}</span>'
            f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};">{_esc(p["title_ko"])} · 오늘 {len(p["signals"])}건</span></span>'
            f'<span style="flex:none;text-align:right;"><span style="display:block;font-size:{dk.SMALL};line-height:{dk.LH_CARD};font-weight:700;">{val}</span>'
            f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};">{sub}</span></span>'
            f'<span style="flex:none;color:#94A3B8;display:inline-flex;">{chev}</span></a>')
    return f'<div data-people-list="1" style="margin:0 0 8px;">{"".join(rows)}</div>'


def sec_topic_bars(r):
    """주제 반복 막대 (2026-10-21 사용자: 같은 얘기를 며칠 동안 반복하는지 통계 그래프) — 주제마다 최근 7일 · 직전 7일 가로 막대 한 쌍(비교 대상, 가이드라인 1-4-1),
    오른쪽 `N일째`(오늘까지 이어진 날수), 아래 줄 말한 인물과 건수. 최근 7일 많은 순 8개."""
    rows = [t for t in (r.get("topic_trend") or []) if t["days7"] or t["prev7"]][:8]
    if not rows:
        return ""
    mx = max(max(t["days7"], t["prev7"]) for t in rows) or 1
    out = []
    for t in rows:
        streak = f'<span style="font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};">{t["streak"]}일째 이어짐</span>' if t["streak"] >= 2 else ""
        who = " · ".join(f'{_esc(s["name_ko"])} {s["n"]}' for s in t["speakers"][:4])
        def bar(v, color):
            w = max(2, round(v / mx * 100)) if v else 0
            return (f'<span style="display:block;height:12px;border-radius:0 4px 4px 0;background:{color};width:{w}%;"></span>'
                    f'<span style="font-size:{dk.TINY};line-height:{dk.LH_TINY};font-weight:700;color:#111;text-align:right;">{v}</span>')
        out.append(
            f'<div style="padding:12px 0 10px;border-top:1px solid #E2E8F0;">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;font-size:{dk.SMALL};line-height:{dk.LH_CARD};"><b>{_esc(_topic(t["topic"]))}</b>{streak}</div>'
            f'<div style="display:grid;grid-template-columns:64px 1fr 28px;gap:4px 8px;align-items:center;margin:6px 0 4px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};">'
            f'<span>최근 7일</span>{bar(t["days7"], BAR_NOW)}<span>직전 7일</span>{bar(t["prev7"], BAR_PREV)}</div>'
            f'<div style="font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};">{who}</div></div>')
    return f'<div data-topic-bars="1" style="margin:0 0 8px;">{"".join(out)}</div>'


def _legend(right=""):
    """막대 범례 한 줄 — 긍정(빨강) · 부정(파랑) · 중립(회색), 막대 끝 숫자 = 전체 (2026-10-21 사용자: 범례 줄, 우측 숫자 삭제)."""
    sq = lambda c: f'<span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:{c};vertical-align:-1px;margin-right:4px;"></span>'
    return (f'<div style="text-align:right;font-size:12px;line-height:16px;color:{dk.NOTE};">'
            f'<span>{sq(dk.UP)}긍정 &nbsp;{sq(dk.DOWN)}부정 &nbsp;{sq("#CBD5E1")}중립</span></div>')   # 우측 끝 정렬, "막대 끝 숫자 = 전체" 설명은 삭제 (2026-10-21 사용자)


def _thin_bar(f, mx):
    """얇은 비율 막대(6px) + 끝에 전체 건수. 길이 = 전체 / 카드 최대."""
    segs = "".join(f'<span style="display:block;width:{f[k] / f["n"] * 100:.1f}%;background:{c};"></span>'
                   for k, c in (("positive", dk.UP), ("negative", dk.DOWN), ("neutral", "#CBD5E1")) if f.get(k))
    return (f'<span style="display:flex;align-items:center;gap:3px;margin-top:0;">'
            f'<span style="display:flex;height:6px;border-radius:3px;overflow:hidden;flex:0 0 auto;width:{max(4, round(f["n"] / (mx or 1) * 80))}%;background:#F1F5F9;">{segs}</span>'
            f'<b style="font-size:{dk.TINY};line-height:{dk.LH_TINY};color:#111;">{f["n"]}</b></span>')


def _dir_split(dirs, total):
    """긍정 · 부정 · 중립 비율 막대(빨강 · 파랑 · 회색) + 글자 한 줄 (2026-10-21 사용자: 기술에 부정적인 발언인지 긍정적인 발언인지)."""
    if not total:
        return ""
    parts = [("positive", dk.UP, "긍정"), ("negative", dk.DOWN, "부정"), ("neutral", "#CBD5E1", "중립")]
    segs = "".join(f'<span style="display:block;width:{dirs.get(k, 0) / total * 100:.1f}%;background:{c};"></span>' for k, c, _ in parts if dirs.get(k))
    text = " · ".join(f'<span style="color:{c if k != "neutral" else dk.NOTE};white-space:nowrap;">{lab} {dirs[k]}</span>' for k, c, lab in parts if dirs.get(k))
    return (f'<span style="display:flex;height:6px;max-width:260px;border-radius:3px;overflow:hidden;margin:6px 0 3px;background:#F1F5F9;">{segs}</span>'
            f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};">{text}</span>')


BADGE_COLORS = ["#0E7490", "#7C3AED", "#B45309", "#15803D", "#BE123C", "#1D4ED8", "#4D7C0F", "#9F1239", "#0F766E", "#6D28D9"]   # 홈 종목 줄 아바타와 같은 색 규칙(feedColor)


def _ticker_badge(sym, size=24):
    """종목 이름 앞 둥근 티커 배지 — 홈 종목 줄의 색 아바타와 같은 모양(티커 두 글자 · 흰 글자 · 티커별 고정 색). 연한 회색 배지는 안 보인다는 지적 (2026-10-21 사용자)."""
    sym = str(sym or "").strip().upper()
    h = 0
    for ch in sym:
        h = (h * 31 + ord(ch)) % 997
    txt = sym.replace("-", "").replace(".", "")[:2]
    return (f'<span aria-hidden="true" style="display:inline-block;width:{size}px;height:{size}px;line-height:{size}px;border-radius:50%;vertical-align:-6px;margin-right:8px;'
            f'background:{BADGE_COLORS[h % len(BADGE_COLORS)]};color:#fff;font-size:{int(size * 0.46)}px;font-weight:700;text-align:center;letter-spacing:-.2px;white-space:nowrap;overflow:hidden;">{txt}</span>')


def _target_row(t, first, mx):
    """언급 대상 한 줄 (2026-10-21 사용자): 제목(기술 · NVDA)과 같은 줄 오른쪽 끝에 누가 몇 번, 아래 얇은 비율 막대 + 끝에 전체 건수."""
    name = _esc(t["name"]) if t["kind"] == "company" else _esc(config.SECTOR_KO.get(t["name"], t["name"]))
    if t["kind"] == "company":
        name = _ticker_badge(t["name"]) + name
    who = " · ".join(f'<span style="white-space:nowrap;">{_esc(s["name_ko"])} {s["n"]}</span>' for s in t["speakers"][:4])
    f = dict(t.get("dirs") or {}, n=t["n"])
    return (f'<span style="display:block;padding:{17 - dk.VP}px 12px;{"" if first else dk.MULTI_SEP}">'
            f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;">'
            f'<span style="font-weight:700;color:#111;font-size:16px;line-height:22px;">{name}</span>'
            f'<span style="flex:1 1 auto;text-align:right;color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};">{who}</span></span>'
            f'{_thin_bar(f, mx)}</span>')


def sec_targets(r):
    """최근 7일 많이 언급된 종목 · 섹터 — 이름 · 건수 한 줄, 아래 누가 몇 번, 긍정 · 부정 비율 막대. 5개 보이고 나머지는 접기 (2026-10-21 사용자).
    ccard 대신 직접 그린다 — ccard 의 보조 줄은 '·' 덩어리 처리로 한 덩어리마다 줄이 바뀌었다."""
    tg = (r.get("targets7") or [])[:12]
    mx = tg[0]["n"] if tg else 1
    rows = [_target_row(t, i == 0, mx) for i, t in enumerate(tg)]
    if not rows:
        return ""
    legend = f'<span style="display:block;padding:{20 - dk.VP}px 12px 0;">{_legend()}</span>'
    if len(rows) > 5:
        more = [_target_row(t, True, mx) if i == 0 else rows[5 + i] for i, t in enumerate(tg[5:])]   # 펼친 첫 줄은 위 선 없음 — 펼침 상자가 선을 갖는다 (겹침 수정, 2026-10-21 사용자)
        return dk.fold_card(legend + "".join(rows[:5]), "".join(more), f"대상 {len(rows) - 5}개 더 보기")
    return f'<div data-cards="1" style="margin:0 0 8px;"><span style="{dk.MULTI}">{legend}{"".join(rows)}</span></div>'


SUBTOPIC_KO_PATH = os.path.join(config.BASE_DIR, "ref", "subtopic_ko.json")   # 세부 주제 영어 → 한국어 (narrate 가 채움, 누적) — ref/ 는 깃에 남는다


def _subtopic_ko():
    try:
        with open(SUBTOPIC_KO_PATH, encoding="utf-8") as f:
            return {k.lower(): v for k, v in json.load(f).items()}
    except (OSError, ValueError):
        return {}


def sec_strips(r):
    """인물별 '많이 말한 키워드' — 인물 상세(인물을 눌렀을 때) 제목 아래, 기사 위. 평소엔 숨김(hidden), 테마 JS 가 옮겨 보여 준다.
    (2026-10-21 사용자: 하루 몇 번 말했는지는 중요하지 않다 → 날짜별 막대 삭제, 가장 많이 말한 주제가 중요한데 에너지 · 지정학으로는 모르겠다 → 키워드)
    키워드 = 최근 30일 세부 주제(분류 LLM 의 짧은 명사구) 건수 순 6개. 막대 = 긍정(빨강) · 부정(파랑) · 중립(회색) 비율, 오른쪽 건수, 아래 숫자.
    한국어 표기는 subtopic_ko.json — 없으면 영어 그대로(짧은 명사구라 읽힌다). data-person-strip 이름은 테마 JS 호환용 그대로."""
    ko = _subtopic_ko()
    out = []
    for p in r["people"]:
        kws = (r.get("keywords") or {}).get(p["speaker"]) or []
        if not kws:
            continue
        mx = kws[0]["n"] or 1
        total = sum(k["n"] for k in kws)
        # 키워드 글자 14px 굵게, 그 아래 얇은 막대(6px) + 끝에 전체 건수. 범례는 카드 머리 한 줄, 우측 숫자 열 없음 (2026-10-21 사용자)
        rows = "".join(
            f'<div style="margin-top:8px;">'
            f'<span style="display:block;color:#111;font-size:{dk.TINY};line-height:16px;font-weight:700;word-break:keep-all;">{_esc(ko.get(f["key"].lower()) or config.TOPIC_KO.get(f["key"], f["key"]))}</span>'
            f'{_thin_bar(f, mx)}</div>' for f in kws)
        out.append(
            f'<div data-person-strip="{p["speaker"]}" hidden style="margin:0 0 8px;padding:{14 - dk.VP}px 14px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">'
            f'<span style="font-size:{dk.TINY};line-height:{dk.LH_TINY};font-weight:700;color:#111;">최근 30일 발언 {total}건</span>{_legend()}</div>'
            f'{rows}</div>')   # 한 줄: 왼쪽 최근 30일 발언 N건(키워드 제목 자리), 오른쪽 범례 (2026-10-21 사용자)   # 제목 줄(많이 말한 키워드 · 최근 30일 발언 N건) 원복 (2026-10-21 사용자), 범례는 그 아래 우측
    return "".join(out)


def build_body(r, n, d):
    """탭 없음 (2026-10-21 저녁 사용자): 글 = 인물 목록(바로 시작, 머리 글 · 안내 글 없음) → 언급 대상 → (숨김) 인물별 발언 묶음 · 30일 띠.
    인물을 누르면 테마 JS 가 목록 자리에 인물 이름 제목(왼쪽 네모 화살표 = 목록으로) · 30일 띠 · 발언 목록을 보여 준다.
    주제 반복 막대 · 오늘 탭 · 시장 맥락 · 머리 두 줄은 뺐다 (주제 건수만으로는 무엇을 말했는지 안 보이고, 오늘 탭은 인물 상세와 같은 내용)."""
    cards = (n or {}).get("cards")
    targets = sec_targets(r)
    body = "\n".join([
        dk.WRAP_OPEN,
        sec_seo_lead(r, d, cards),   # 목록 화면의 요약 두 줄은 유지 (2026-10-21 사용자) — 인물 상세에서는 JS 가 숨긴다
        sec_people_list(r),
        dk.section("언급 대상", targets) if targets else "",   # 안내 글 없음 (2026-10-21 사용자)
        dk.h2("발언", line=True).replace("<h2 ", '<h2 data-person-pages="1" ', 1),   # 홈 카드가 읽는 구획 제목 — 화면에서는 JS 가 숨긴다
        sec_people(r, cards),
        sec_strips(r),
        dk.WRAP_CLOSE,
    ])
    return dk.fix_colons(dk.formal(dk.align_titles(body)))   # 카드 밖 구획 제목은 좌측 기준선 13px (2026-10-23 사용자)


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
    body = dk.with_ai_model(build_body(r, n, d), (n or {}).get("model"), dk.ALIGN_PX)   # 글 끝 "AI 서술 · 모델명" (운영지침 D3-1d)
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
