"""인물 발언 구획 — 미국 종목 페이지 `오늘` 탭(뉴스 아래) · 미국 증시 리포트 `오늘` 탭(뉴스 아래) (2026-11-07 사용자, 목업).

재료 = 인물 레이더가 쓰는 people_mentions.json (people-radar/stock_mentions.py). 모양 = 공용 뉴스 카드(news_item, 인물 발언 글과 같음).
3줄 보이고 나머지는 접기, 맨 아래 `주요 인물 발언 전체 보기` 링크. 발언이 없으면 구획을 통째로 뺀다(빈 답 금지).
"""

import datetime
import json
import re
import os

import design_kit as dk

KST = datetime.timezone(datetime.timedelta(hours=9))
PATH = os.environ.get("PEOPLE_MENTIONS_JSON") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "people-radar", "output", "state", "people_mentions.json")
ALL_URL = "https://alpha-scope.blogspot.com/search/label/%EC%9D%B8%EB%AC%BC%20%EB%B0%9C%EC%96%B8"   # 라벨 `인물 발언` 목록 — 발행 때 최신 글 주소로
SHOWN = 5   # 5건 + 10건씩 더 보기 (2026-11-07 사용자 P340, 옛 3)
TOPIC_KO = {"Trade": "무역", "Fed": "연준 · 금리", "Tax": "세금", "Energy": "에너지", "Immigration": "이민", "Regulation": "규제",
            "Geopolitics": "지정학", "Company": "기업", "Stock Call": "종목 의견", "Position": "매매", "Sector Call": "업종 의견",
            "Macro Warning": "거시 경고", "Market Outlook": "시장 전망", "Policy": "정책 의견", "Product": "제품", "Investment": "투자",
            "Earnings": "실적", "Deal": "거래 · 제휴", "Industry View": "업계 평가", "Politics": "정치"}   # people-radar/config.TOPIC_KO 와 같게
DIR_KO = {"positive": "긍정", "negative": "부정", "neutral": "중립"}
_data = None


def load():
    global _data
    if _data is None:
        try:
            with open(PATH, encoding="utf-8") as f:
                _data = json.load(f)
        except (OSError, ValueError):
            _data = {}
    return _data


def _when(iso):
    dt = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).astimezone(KST)
    return dt.strftime("%m.%d %H:%M")


def _person_url(it):
    """`빌 애크먼 발언 더 보기` — 최신 인물 발언 글의 그 인물 화면(#person-키, 테마가 바로 연다). 글 주소를 모르면 라벨 목록 (P371)."""
    base = load().get("post_url")
    return f"{base}#person-{it['speaker']}" if base else ALL_URL


def _row(it):
    meta = [_when(it["at"])]
    if it["n_reports"]:
        meta.append(f"보도 {it['n_reports']}곳")
    if it["publisher"] and it["publisher"] != "googlenews" and not it["primary"] and re.fullmatch(r"[\x20-\x7E가-힣·]+", it["publisher"]):   # 아랍어 등 못 읽는 매체명은 뺀다
        meta.append(it["publisher"])
    d = it["direction"]
    pills = [dk.pill(dk.ISSUE_KO.get(it.get("issue") or "OTHER", "그 밖"), bare=True),   # 분야 라벨 = 기록 이슈 코드 이름 (2026-11-07 사용자 P339, 옛: 인물 주제)
             dk.pill(DIR_KO.get(d, d), d if d in ("positive", "negative") else "neutral", bare=True),
             dk.pill(f"강도 {it['intensity']}", bare=True)]
    row = dk.news_item(dk.esc(it["headline"]), it["url"], it["detail"], (), " ".join(pills), meta)
    if it.get("avatar"):   # 왼쪽 얼굴 동그라미 (2026-11-07 사용자 P368)
        row = f'<div style="display:flex;gap:12px;align-items:flex-start;">{it["avatar"]}<div style="flex:1 1 auto;min-width:0;">{row}</div></div>'
    lines = it.get("pop") or []
    if len(lines) >= 2:   # 누르면 짧은 팝업 (P366): 발언 요약 · 닿는 곳 · 새로운가 · 다음 날짜
        pid = dk.news_pop_id("pp", it["id"])
        body = dk.news_pop_body(pid, it["headline"], lines)   # 링크는 아래 버튼 줄이 맡는다
        src = it.get("publisher") if not it.get("primary") and it.get("publisher") != "googlenews" else ""
        # 버튼 줄 = 양쪽 (P372): 왼쪽 `빌 애크먼 발언 더 보기` = 공식 더 보기 버튼(흰 바탕 · 회색 외곽선), 오른쪽 `원문 보기` 작은 글자 링크
        btns = (f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin:16px 0 0;">'
                f'<a href="{dk.esc(_person_url(it))}" style="{dk.FOLD_BTN}display:inline-flex;text-decoration:none;">{dk.esc(it["name_ko"])} 발언 더 보기</a>'
                + (f'<a href="{dk.esc(it["url"])}" target="_blank" rel="noopener" data-trhelp="skip" style="font-size:13px;line-height:19px;color:{dk.SUB};text-decoration:underline;text-underline-offset:3px;white-space:nowrap;">'
                   f'원문 보기{f" ({dk.esc(src)})" if src else ""} {dk.LINK_ICON}</a>' if it.get("url") else "") + "</span>")
        row = dk.news_pop_wrap(row, pid) + body[:-len("</div>")] + btns + "</div>"
    return row


def _list(ids, items):
    rows = [_row(items[i]) for i in ids if i in items]
    if not rows:
        return ""
    out = dk.more_list(rows, "인물 발언", SHOWN, indent=dk.ALIGN_PX)
    out += (f'<p style="margin:0 0 8px;padding:0 {dk.ALIGN_PX}px;font-size:{dk.TINY};line-height:{dk.LH_TINY};">'
            f'<a href="{ALL_URL}" style="color:#111;font-weight:700;text-decoration:none;">주요 인물 발언 전체 보기 ›</a></p>')
    return out


def _lean(d):
    """긍정 · 부정 건수 → (카드 색, 답 색, 쉬운 말). 질문 카드 색 = 답의 방향 (가이드라인 7-1)."""
    p, n = d.get("positive", 0), d.get("negative", 0)
    if p > n:
        return "positive", dk.UP, "긍정 쪽이 많았습니다"
    if n > p:
        return "negative", dk.DOWN, "부정 쪽이 많았습니다"
    return "neutral", "#111", ("긍정과 부정이 반반이었습니다" if p else "방향이 없는 발언이었습니다")


def _igo(w):
    """이름 + 서술격 `이고` / `고` (`기업 이슈고` · `엔비디아고`, 받침 있으면 `이고`)."""
    return w + ("이고" if dk._tail(w) else "고")


def _issue(k):
    return dk.ISSUE_KO.get(k, "그 밖")


def _dir_val(d):
    """근거 줄 값 = `긍정 4 · 부정 2` (증감 색, 같은 종류 나열)."""
    parts = [f'<span style="color:{c};">{k} {d[key]}</span>' for key, k, c in (("positive", "긍정", dk.UP), ("negative", "부정", dk.DOWN)) if d.get(key)]
    return "<span>" + " · ".join(parts) + "</span>" if parts else "<span>중립</span>"


def summary_card(qcard):
    """데일리 `인물 발언` 탭 맨 위 = 질문 카드 3개 (2026-11-07 사용자 P380: "독자 질문하고 답하는 형식으로", 옛 P376 요약 상자).
    qcard = daily-report/cards.question_card. 파이썬 셈만, AI 없음. 재료 없으면 "". 갈린 분야가 없으면 그 카드는 뺀다(빈 답 금지)."""
    sm = load().get("summary") or {}
    tp = sm.get("topics") or []
    if not tp:
        return ""
    out = []
    # ① 많이 나온 분야 — 동점(건수 · 인물 수 같음)이면 `외 n개`
    top = tp[0]
    ties = [t for t in tp[1:] if t["n"] == top["n"] and t.get("n_who", 0) == top.get("n_who", 0)]
    theme, ink, lean = _lean(top["dirs"])
    state = _issue(top["issue"]) + (f" 외 {len(ties)}개" if ties else "")
    first = (f"오늘 인물 발언에서 가장 많이 나온 분야는 {_igo(_issue(top['issue']))}, 말한 인물은 {' · '.join(top['who'])}입니다. {lean}.")
    if len(tp) > 1:
        first += f" 다음은 {' · '.join(_issue(t['issue']) for t in tp[1:])} 순입니다." if not ties else f" {' · '.join(_issue(t['issue']) for t in ties)}도 비슷하게 많이 나왔습니다."
    lines = [(first, "plain")] + [("row", _issue(t["issue"]), _dir_val(t["dirs"]), " · ".join(t["who"])) for t in tp]
    lines.append((f"오늘 인물 {sm.get('n_people', 0)}명 · 발언 {sm.get('n', 0)}건 기준", "note"))
    out.append(qcard("인물들이 가장 많이 말한 분야는?", state, theme, ink, lines))   # 닫힌 채로 — 데일리 인물 발언 탭 카드 모두 닫힘 (2026-11-07 사용자, 옛 P380 첫 카드 펼침)
    # ② 의견이 갈린 분야 — 회색 (갈림 = 방향 없음)
    sp = sm.get("split") or []
    if sp:
        x = sp[0]
        first = f"{dk.josa(_issue(x['issue']), '을')} 두고 {dk.josa(x['neg'][0], '은')} 부정, {dk.josa(x['pos'][0], '은')} 긍정 쪽이었습니다."
        if len(sp) > 1:
            first += f" {_issue(sp[1]['issue'])}에서도 의견이 갈렸습니다."
        lines = [(first, "plain")]
        for y in sp:
            lines += [("row", f"{_issue(y['issue'])} 부정 쪽", f'<span style="color:{dk.DOWN};">{dk.esc(y["neg"][0])}</span>', f"발언 {y['neg'][1]}건"),
                      ("row", f"{_issue(y['issue'])} 긍정 쪽", f'<span style="color:{dk.UP};">{dk.esc(y["pos"][0])}</span>', f"발언 {y['pos'][1]}건")]
        out.append(qcard("의견이 갈린 분야는?", _issue(x["issue"]) + (f" 외 {len(sp) - 1}개" if len(sp) > 1 else ""), "neutral", "#111", lines))
    # ③ 많이 언급된 종목 — 색 = 그 종목 발언의 우세 방향
    st = sm.get("stocks") or []
    if st:
        x = st[0]
        theme, ink, lean = _lean(x.get("dirs") or {})
        first = f"인물들이 가장 많이 언급한 종목은 {_igo(x['name'])}, {' · '.join(x['who'])}의 발언에 나왔습니다. {lean}."
        if len(st) > 1:
            first += f" 다음은 {' · '.join(y['name'] for y in st[1:])} 순입니다."
        lines = [(first, "plain")] + [("row", y["name"], _dir_val(y.get("dirs") or {}), " · ".join(y["who"])) for y in st]
        out.append(qcard("많이 언급된 종목은?", x["name"], theme, ink, lines))
    return "".join(out)


def for_stock(sym):
    """종목 페이지 — 최근 7일 이 종목을 지목한 발언. 없으면 ""."""
    d = load()
    return _list(d.get("by_stock", {}).get(sym, []), d.get("items", {}))


def for_market():
    """미국 증시 리포트 — 최근 24시간 시장 관련도 높은 발언(인물마다 하나). 없으면 ""."""
    d = load()
    return _list(d.get("market", []), d.get("items", {}))
