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
DIR_NOTE = "▲ 상승 쪽 = 주가에 유리하게 본 발언, ▼ 하락 쪽 = 불리하게 본(경고한) 발언"   # 카드 안내 줄은 뺐다(2026-11-11 사용자) — 문장이 이미 `주가에 유리 · 불리하게 본` 으로 풀어 쓴다. 요약 카드 안내 (2026-11-11 사용자: `AI 거품 · 부정` 은 부정의 부정으로 읽힌다)
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
             dk.pill(DIR_KO.get(d, d), d if d in ("positive", "negative") else "neutral", bare=True),   # 기사 줄 라벨은 옛 모양 그대로 (2026-11-08 사용자: 삼각형 라벨은 카드 안만)
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
    out += _credit([items[i] for i in ids if i in items and items[i].get("avatar")])   # CC 사진 출처 표기 의무 (2026-11-08 민간인 사진)
    out += (f'<p style="margin:0 0 8px;padding:0 {dk.ALIGN_PX}px;font-size:{dk.TINY};line-height:{dk.LH_TINY};">'
            f'<a href="{ALL_URL}" style="color:#111;font-weight:700;text-decoration:none;">주요 인물 발언 전체 보기 ›</a></p>')
    return out


PHOTO_META = os.path.join(os.path.dirname(os.path.abspath(__file__)), "people-radar", "ref", "people_photos.json")


def _credit(its):
    """사진 출처 줄 — CC BY · BY-SA 사진은 작성자 · 라이선스 표기 의무 (people-radar/render_html.photo_credit 과 같은 모양).
    render_html 을 import 하지 않는다 — experiments 아래 같은 이름 모듈이 여럿이라 엉뚱한 걸 부를 수 있다. 사진 여부 = 줄 아바타가 <img> 인지."""
    try:
        with open(PHOTO_META, encoding="utf-8") as f:
            ph = json.load(f)
    except (OSError, ValueError):
        return ""
    seen, out = set(), []
    for it in its:
        k, m = it.get("speaker"), ph.get(it.get("speaker"))
        if not m or k in seen or "<img" not in (it.get("avatar") or "") or not m.get("license", "").upper().startswith("CC"):
            continue
        seen.add(k)
        out.append(f'{dk.esc(it.get("name_ko") or k)} — {dk.esc(m.get("author") or "작성자 미상")}, '
                   f'<a href="{dk.esc(m["page"])}" target="_blank" rel="noopener" data-trhelp="skip" style="color:inherit;">{dk.esc(m["license"])}</a>')
    if not out:
        return ""
    return dk.credit_fold(" · ".join(out), dk.ALIGN_PX)


def _lean(d):
    """긍정 · 부정 건수 → (카드 색, 답 색, 쉬운 말). 질문 카드 색 = 답의 방향 (가이드라인 7-1)."""
    p, n = d.get("positive", 0), d.get("negative", 0)
    if p > n:
        return "positive", dk.UP, "주가에 유리하게 본 발언이 많았습니다"
    if n > p:
        return "negative", dk.DOWN, "주가에 불리하게 본(경고한) 발언이 많았습니다"
    return "neutral", "#111", ("주가에 유리하게 본 발언과 불리하게 본 발언이 반반이었습니다" if p else "방향이 없는 발언이었습니다")


def _igo(w):
    """이름 + 서술격 `이고` / `고` (`기업 이슈고` · `엔비디아고`, 받침 있으면 `이고`)."""
    return w + ("이고" if dk._tail(w) else "고")


def _issue(k):
    return dk.ISSUE_KO.get(k, "그 밖")


def _box(kind, text):
    """긍정 · 부정 라벨 = 기술지표 상승 · 하락 라벨과 같은 상자(삼각형 + 글자, tech_signals.box) — 긍정 = 상승 색 ▲, 부정 = 하락 색 ▼, 중립 = 가로 막대 (2026-11-08 사용자)."""
    import tech_signals as TS
    return TS.box(kind, text, dk.esc, fit=True)


def _dir_val(d):
    """근거 줄 값 = 라벨 `▲ 긍정 4` `▼ 부정 2` (라벨끼리 2px, dk.PILL_PAIR_GAP). 둘 다 없으면 `— 중립`."""
    parts = [_box(kind, f"{k} {d[key]}") for key, k, kind in (("positive", "상승 쪽", "up"), ("negative", "하락 쪽", "down")) if d.get(key)]   # 옛 `긍정` · `부정` — `AI 거품 · 부정` 이 "거품이 아니다"로 읽혀 (2026-11-11 사용자)
    if not parts:
        parts = [_box("flat", "중립")]
    return f'<span style="display:inline-flex;gap:{dk.PILL_PAIR_GAP}px;vertical-align:middle;">{"".join(parts)}</span>'


def _face(name, size=24, faces=None):
    """이름 앞 얼굴 동그라미 — 인물 발언 줄과 같은 것(자유 라이선스 사진, 없으면 성 첫 글자 · 인물군 색). 크기만 24."""
    av = (faces or {}).get(name) or next((it.get("avatar") for it in (load().get("items") or {}).values() if it.get("name_ko") == name and it.get("avatar")), "")   # faces = 이름 → 32px 아바타 (인물 발언 글이 레이더에서 바로 넘긴다)
    if not av:
        return ""
    return (av.replace("width:32px;height:32px;", f"width:{size}px;height:{size}px;").replace('width="32" height="32"', f'width="{size}" height="{size}"')
              .replace("font-size:14px;", f"font-size:{int(size * 0.45)}px;").replace("flex:none;", "flex:none;vertical-align:middle;margin-right:6px;", 1))


PEOPLE_CARDS_GAP = 28
NOTE_GRAY = "#6B7280"   # 기술지표 괄호 글 · 근거 줄 뜻과 같은 회색


def summary_card(qcard, sm=None, faces=None):
    """데일리 `인물 발언` 탭 맨 위 = 질문 카드 (2026-11-07 사용자 P380: "독자 질문하고 답하는 형식으로", 옛 P376 요약 상자).
    2026-11-08 사용자 P406: 큰 분야 → 좁은 이슈(세부 주제) — `인물들이 많이 말한 이슈는?` · `의견이 갈린 이슈는?` · `많이 언급된 종목은?`.
    qcard = daily-report/cards.question_card. 파이썬 셈만, AI 없음. 재료 없는 카드는 뺀다(빈 답 금지): 두 명 이상 말한 이슈가 없으면 ①, 맞선 이슈 · 종목이 없으면 ②."""
    # sm · faces 를 넘기면 그것으로 — 인물 발언 글(people-radar/render_html.sec_summary_cards)이 같은 카드를 맨 위에 쓴다 (2026-11-08 사용자). 없으면 상태 파일
    sm = sm if sm is not None else (load().get("summary") or {})
    out = []
    # ① 많이 말한 이슈 — 동점(인물 수 · 건수 같음)이면 `외 n개`
    iss = sm.get("issues") or []
    if iss:
        top = iss[0]
        ties = [t for t in iss[1:] if t["n"] == top["n"] and t["n_who"] == top["n_who"]]
        theme, ink, lean = _lean(top["dirs"])
        state = top["name"] + (f" 외 {len(ties)}개" if ties else "")
        first = f"오늘 인물 발언에서 가장 많이 나온 이슈는 {_igo(top['name'])}, 말한 인물은 {' · '.join(top['who'])}입니다. {lean}."
        if len(iss) > 1:
            first += f" 다음은 {' · '.join(t['name'] for t in iss[1:])} 순입니다." if not ties else f" {' · '.join(t['name'] for t in ties)}도 비슷하게 많이 나왔습니다."
        lines = [(first, "plain")] + [("row", t["name"], _dir_val(t["dirs"]), " · ".join(t["who"])) for t in iss]
        lines.append((f"오늘 인물 {sm.get('n_people', 0)}명 · 발언 {sm.get('n', 0)}건 기준, 두 명 이상이 말한 이슈만", "note"))
        out.append(qcard("인물들이 많이 말한 이슈는?", state, theme, ink, lines))   # 닫힌 채로 — 데일리 인물 발언 탭 카드 모두 닫힘 (2026-11-07 사용자)
    # ② 의견이 갈린 이슈 — 같은 이슈 · 같은 종목을 두고 다른 사람이 긍정 · 부정. 회색 (갈림 = 방향 없음)
    sp = sm.get("split") or []
    if sp:
        x = sp[0]
        first = f"{dk.josa(x['name'], '을')} 두고 {dk.josa(x['neg'][0], '은')} 하락 쪽, {dk.josa(x['pos'][0], '은')} 상승 쪽으로 봤습니다."
        if len(sp) > 1:
            first += f" {sp[1]['name']}에서도 의견이 갈렸습니다."
        lines = [(first, "plain")]
        for y in sp:   # 줄 = `반도체 [▼ 부정]` · 오른쪽 얼굴 + 이름 (2026-11-08 사용자: 기술지표 라벨처럼 · 얼굴 아이콘)
            for side, kind, word in (("neg", "down", "하락 쪽"), ("pos", "up", "상승 쪽")):
                who, n = y[side]
                # 한 줄 = `[▼ 부정] 발언 1건` (이슈 이름 · 세로 구분선 삭제 — 카드 답 · 첫 문장에 이슈가 있다, 2026-11-08 사용자) · 오른쪽 얼굴 + 이름
                lines.append(("row", f'<span style="display:inline-flex;align-items:center;gap:{dk.PILL_GAP}px;vertical-align:middle;white-space:nowrap;">{_box(kind, word)}'
                                     f'<span style="font-size:{dk.TINY};color:{NOTE_GRAY};">발언 {n}건</span></span>',
                              f'<span style="display:inline-flex;align-items:center;white-space:nowrap;">{_face(who, faces=faces)}{dk.esc(who)}</span>', ""))
        out.append(qcard("의견이 갈린 이슈는?", x["name"] + (f" 외 {len(sp) - 1}개" if len(sp) > 1 else ""), "neutral", "#111", lines))
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
    # 질문 카드 ~ 아래 발언 목록 첫 줄(얼굴) 10 → 30 (×3, 2026-11-08 사용자, Chrome 실측). 카드 아래 8 과 겹쳐 PEOPLE_CARDS_GAP 가 된다
    return f'<div style="margin:0 0 {PEOPLE_CARDS_GAP}px;">{"".join(out)}</div>' if out else ""


def person_cards(qcard, ps, name, report_only=False, next_event=None):
    """인물 페이지 맨 위 강조 카드(질문 카드) — `오늘 가장 많이 말한 이슈는?` · `최근 7일 가장 많이 말한 이슈는?` · `최근 7일 많이 언급한 종목은?`
    (2026-11-11 사용자). ps = stock_mentions.person_summary. 재료가 없는 카드는 뺀다(빈 답 금지): 이슈 · 종목은 2건 이상만. 파이썬 셈만, AI 없음."""
    out = []

    REPORT_NOTE = "이 인물의 발언은 모두 언론 보도로 옮긴 말입니다"   # 옛 읽는 법 카드 `발언 경로` 를 한 줄로 (2026-11-11 사용자)

    def issue_card(q, part, when, least=PERSON_MIN):
        iss = [x for x in part.get("issues") or [] if x["n"] >= least]
        if not iss:
            return
        top = iss[0]
        ties = [x for x in iss[1:] if x["n"] == top["n"]]
        theme, ink, lean = _lean(top["dirs"])
        if top["n"] < 2:   # 모두 1건 = `가장 많이` 가 아니다 — 말한 이슈를 그대로 (2026-11-11 Claude: 1건짜리를 `가장 많이` 로 쓰면 사실과 다르다)
            alld = {}
            for x in iss:
                for k, v in x["dirs"].items():
                    alld[k] = alld.get(k, 0) + v
            theme, ink, lean = _lean(alld)
            if sum(alld.values()) == 1:
                lean = lean.replace("발언이 많았습니다", "발언이었습니다")
            first = f"{when} {dk.josa(name, '은')} {' · '.join(x['name'] for x in iss[:PERSON_ROWS])} 이슈를 말했습니다. {lean}."
            lines = [(first, "plain")] + [("row", x["name"], _dir_val(x["dirs"]), "") for x in iss[:PERSON_ROWS]]
            out.append(qcard(q.replace("가장 많이 말한 이슈는?", "어떤 이슈를 말했나?"), top["name"] + (f" 외 {len(iss) - 1}개" if len(iss) > 1 else ""), theme, ink, lines))
            return
        first = f"{when} {name}의 발언 {part['n']}건 중 가장 많이 나온 이슈는 {top['name']}입니다(발언 {top['n']}건). {lean}."
        if len(iss) > 1:
            first += f" 다음은 {' · '.join(x['name'] for x in iss[1:PERSON_ROWS])} 순입니다."
        lines = [(first, "plain")] + [("row", x["name"], _dir_val(x["dirs"]), f"발언 {x['n']}건") for x in iss[:PERSON_ROWS]]
        if report_only and when != "오늘":
            lines.append((REPORT_NOTE, "note"))
        out.append(qcard(q, top["name"] + (f" 외 {len(ties)}개" if ties else ""), theme, ink, lines))

    issue_card("오늘 가장 많이 말한 이슈는?", ps.get("today") or {}, "오늘", 1)   # 오늘은 이슈마다 1건인 날이 많다 — 1건부터, 같으면 `외 n개`
    d7 = ps.get("d7") or {}
    issue_card("최근 7일 가장 많이 말한 이슈는?", d7, "최근 7일")
    st = [x for x in d7.get("stocks") or [] if x["n"] >= PERSON_MIN]
    if st:
        x = st[0]
        theme, ink, lean = _lean(x["dirs"])
        first = f"최근 7일 {name}이(가) 가장 많이 언급한 종목은 {x['name']}입니다(발언 {x['n']}건). {lean}."
        first = first.replace(f"{name}이(가)", dk.josa(name, "이"))
        if len(st) > 1:
            first += f" 다음은 {' · '.join(y['name'] for y in st[1:PERSON_ROWS])} 순입니다."
        lines = [(first, "plain")] + [("row", y["name"], _dir_val(y["dirs"]), f"발언 {y['n']}건") for y in st[:PERSON_ROWS]]
        out.append(qcard("최근 7일 많이 언급한 종목은?", x["name"], theme, ink, lines))
    if next_event:   # 옛 읽는 법 카드의 `다음 날짜` (연준 FOMC 등) — 일정이 있을 때만
        day, kind, left = next_event
        out.append(qcard("다음 일정은?", f"D-{left}", "neutral", "#111",
                         [(f"{day} {dk.josa(kind, '이')} 있습니다. 오늘부터 {left}일 남았습니다.", "plain"), ("row", kind, day, "")]))
    return f'<div data-person-cards="1" style="margin:0 0 {PEOPLE_CARDS_GAP}px;">{"".join(out)}</div>' if out else ""


PERSON_MIN, PERSON_ROWS = 2, 3   # 인물 카드: 2건 이상인 이슈 · 종목만 · 줄은 3개까지


def for_stock(sym):
    """종목 페이지 — 최근 7일 이 종목을 지목한 발언. 없으면 ""."""
    d = load()
    return _list(d.get("by_stock", {}).get(sym, []), d.get("items", {}))


def for_market():
    """미국 증시 리포트 — 최근 24시간 시장 관련도 높은 발언(인물마다 하나). 없으면 ""."""
    d = load()
    return _list(d.get("market", []), d.get("items", {}))
