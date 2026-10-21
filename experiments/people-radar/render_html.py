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
TITLE_NAME = "트럼프 · 연준 · 월가 인물 발언"   # 검색어 = 가장 많이 찾는 인물 · 기관 (Claude 확정 2026-10-19, 일괄 설명 대기)
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
    return f"{TITLE_NAME} {korean_date(d)}"


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
    """검색 결과 요약 문단 — 파이썬 값만. data-lead · data-cards 를 달지 않는다 (홈 카드 파서가 머리로 읽지 않게)."""
    _, m, dd = d.split("-")
    names = [p["name_ko"] for p in r["people"]]
    text = f"{int(m)}월 {int(dd)}일 최근 24시간 시장 관련 발언은 {r['event_count']}건, 말한 사람은 {', '.join(names[:4])}" + (" 등" if len(names) > 4 else "") + "입니다."
    top = r["people"][0]["signals"][0] if r["people"] else None
    h = _card_text(top, cards)[0] if top else None
    if h:
        more = f" 가장 강한 발언은 {h}입니다."
        if len(text + more) <= SEO_LEAD_MAX:
            text += more
    return f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">{_esc(text)}</p>'


def sec_head(r, cards):
    """머리 강조 카드 — 인물 수 · 건수, 아래 줄 가장 강한 발언 (홈 카드가 data-lead 로 읽는다)."""
    top = r["people"][0]["signals"][0]
    h, _ = _card_text(top, cards)
    sub = f"가장 강한 발언 : {_esc(h)}" if h else ""   # 헤드라인이 "인물, 무엇" 이라 이름을 따로 붙이지 않는다. 서술이 없으면 줄을 뺀다
    if r.get("only_reports"):
        sub = (sub + " " if sub else "") + "(오늘은 보도된 발언만 있습니다)"
    card = dk.state_card(f"발언 {r['event_count']}건 · {r['people_count']}명", kind="neutral", sub_html=sub)
    return dk.cards(card)


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
    if s["source_kind"] == "secondary":
        pills.append(dk.pill("보도된 발언", bare=True))
    lab = f'<span style="display:block;line-height:1;margin:8px 0 0;">{" ".join(pills)}</span>'
    return f"{head}{sub_html}{lab}"


def sec_people(r, cards):
    out = []
    for p in r["people"]:
        items = [x for x in (_signal_item(p, s, cards) for s in p["signals"]) if x]
        if not items:
            continue
        shown, more = items[:MAX_SIGNALS_PER_PERSON], items[MAX_SIGNALS_PER_PERSON:]
        out.append(dk.sub_label(f"{p['name_ko']} ({p['title_ko']})"))
        out.append(dk.item_rules(shown, sub=True))
        if more:
            out.append(dk.fold(f"{p['name_ko']} 발언 {len(more)}건 더 보기", dk.item_rules(more, sub=True)))
    return "".join(out)


REGIME_KO = {"Risk-On": "위험 선호", "Risk-Off": "위험 회피", "Neutral": "중립"}   # daily-report render_html.TERM_KO 와 같다


def sec_market(r):
    m = r.get("market")
    if not m or m.get("score") is None:
        return ""
    rows = [("시장 상태 점수", f"{m['score']}점", _esc(f"{REGIME_KO.get(m.get('label'), m.get('label') or '')} · 전날 대비 {m['delta']:+d}점" if m.get("delta") is not None else REGIME_KO.get(m.get("label"), m.get("label") or ""))),
            ("S&P 500", dk.arrow(m.get("spx_1d")), ""), ("나스닥", dk.arrow(m.get("ndx_1d")), "")]
    return dk.ccard(rows) + dk.muted(f"미국 증시 리포트 기준 · {m.get('as_of') or ''} 종가")


def sec_trend(r):
    rows = [(f"{_esc(t['name_ko'])} · {_esc(_topic(t['topic']))}", f"{t['days7']}건", _esc(f"직전 7일 {t['prev7']}건"))
            for t in r.get("trend_changes", [])[:12]]
    return dk.ccard(rows) if rows else ""


def build_body(r, n, d):
    cards = (n or {}).get("cards")
    trend = sec_trend(r)
    market = sec_market(r)
    body = "\n".join([
        dk.WRAP_OPEN,
        sec_seo_lead(r, d, cards),
        sec_head(r, cards),
        dk.section("발언", sec_people(r, cards), tab=TAB_TODAY),
        dk.section("오늘 시장 맥락", market, tab=TAB_TODAY) if market else "",
        dk.section(TAB_TREND, trend + dk.muted("최근 7일 신호 수가 직전 7일과 달라진 인물 · 주제만 보여 줍니다."), tab=TAB_TREND) if trend else "",
        dk.WRAP_CLOSE,
    ])
    return dk.fix_colons(dk.formal(body))


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
    body = dk.with_ai_model(build_body(r, n, d), (n or {}).get("model"))   # 글 끝 "AI 서술 · 모델명" (운영지침 D3-1d)
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
