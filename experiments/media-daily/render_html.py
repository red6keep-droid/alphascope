"""media.json + narrative.json → output/media_body.html (Blogger 본문) · media.html (미리보기) · title.txt.

틀 (기획 11절 초안 — 발행하며 고친다):
    맨 앞 요약 한 줄(data-seo-lead)
    → 방송이 본 이슈 (카드마다: 제목 + 분야 · 예상 밖 · 데일리 다룸 라벨 / 설명 문장 / 시각 막대 / 영상 n ↗ · 방송 m · 종목)
    → 한국장에 영향을 줄 만한 소식(옛 한국 연결 — [한국 종목 · 기관] 주제 + 방향) → 방송에서 언급된 종목(글자만)
    → 장 초반에 이어 볼 것(2차, [채널] 주제) → 출처(영상 목록, 접기)   — 2026-10-23 사용자 정리
쓰지 않는 것: 요약 문장 · 자막 수치 · 종목 링크 · 가격 · 추천 어투. 영문 원문 제목은 출처 목록의 링크 글자로만.
"""

import json
import os
import re
import sys

import config

sys.path.insert(0, os.path.join(config.BASE_DIR, ".."))
import design_kit as dk  # noqa: E402

_esc = dk.esc
PREVIEW = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__</title></head>
<body style="max-width:900px;margin:0 auto;padding:16px;background:#fff;"><h1 style="font-size:26px;">__TITLE__</h1>__BODY__</body></html>"""
DAILY_LIST_URL = "https://alpha-scope.blogspot.com/search/label/%EB%8D%B0%EC%9D%BC%EB%A6%AC%20%EB%B8%8C%EB%A6%AC%ED%95%91"
SUB_STYLE = f"display:block;color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};margin-top:2px;"


def _short(ch):
    return config.CHANNEL_SHORT.get(ch, ch)


def _py_detail(c):
    """서술이 없을 때의 파이썬 문장 — 사실만."""
    verb = "엇갈리게 봤습니다" if c["split"] else {"bullish": "긍정적으로 봤습니다", "bearish": "부정적으로 봤습니다"}.get(max(c["stances"], key=c["stances"].get), "다뤘습니다")
    return f"{c['category_ko']} 이슈 '{c['topic']}' 를 방송 {c['n_channels']}곳 · 영상 {c['n_videos']}개가 {verb}."


# 이슈 카드 (2026-10-23 사용자: "제목 · 설명 문장 · 종목 · 영상 수가 중요, 시각은 그래프, 나머지는 불필요"):
#   제목 + 라벨(분야 · 예상 밖 · 데일리 다룸) / 설명 문장 16px / 시각 비율 막대(F) / `영상 n개 ↗ · 방송 n곳 · 종목 : …` 14px
#   발언자 · 채널 이름 나열 · 영상 링크 다섯 줄은 뺐다 — 영상은 대표 하나의 링크 아이콘, 전체는 맨 아래 출처 접기에
DETAIL_STYLE = f"display:block;font-size:{dk.NAME};line-height:{dk.LH_CARD};color:#333;margin:6px 0 12px;"
STANCE_PILL = {"bullish": "positive", "bearish": "negative", "neutral": "neutral"}
STANCE_BAR = [("bullish", "긍정", "positive"), ("bearish", "부정", "negative"), ("neutral", "중립", "neutral")]
# 한국 종목 — 요약 단계가 미국 장외 티커로 적는 것 (SSNLF(KR) 등). 모르는 티커는 그대로
KR_NAME = {"SSNLF": "삼성전자", "SSNNF": "삼성전자", "005930": "삼성전자", "000660": "SK하이닉스", "HXSCL": "SK하이닉스", "HYMTF": "현대차", "005380": "현대차", "LGEAF": "LG전자"}


PILL_ROW = "display:flex;flex-wrap:wrap;justify-content:flex-start;align-items:center;gap:3px;line-height:1;margin:4px 0 0;"   # 제목 아래 라벨 줄 — 왼쪽 정렬 · 사이 3px (2026-10-23 사용자)
def _link_pill(text, url, label, kind="area"):
    """링크가 든 라벨 — 라벨 모양 그대로 a 로. 링크 아이콘은 테마 CSS 가 붙인다 (외부 링크 공통). url 이 없으면 보통 라벨."""
    p = dk.pill(text, kind, bare=True)
    if not url:
        return p
    p = p.replace("<span ", f'<a href="{_esc(url)}" target="_blank" rel="noopener" data-trhelp="skip" title="{_esc(label)}" aria-label="{_esc(label)}" ', 1)
    return p[: -len("</span>")].replace("white-space:nowrap;", "white-space:nowrap;text-decoration:none;", 1) + "</a>"


def _obj(word):
    """'…'을 / '…'를 — 마지막 글자가 한글이면 받침으로, 아니면 '를'."""
    ch = (word or "x")[-1]
    return "을" if "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 else "를"


def interest(c, n_channels_today):
    """관심도 1~10 — config.INTEREST_* 의 식 (2026-10-23 사용자). 파이썬 계산."""
    ch = c["n_channels"] / max(1, n_channels_today)
    vid = min(1.0, c["n_videos"] / config.INTEREST_FULL_VIDEOS)
    return max(1, min(10, round(10 * (config.INTEREST_W_CH * ch + (1 - config.INTEREST_W_CH) * vid))))


def _interest_html(c, n_today):
    """`관심도 : 8 ?` — 홈 트럼프 · 인물 발언 카드의 `강도 : 8` 과 같은 모양(16px, 숫자만 굵게). 툴팁 = 계산법 · 오늘 값 · 출처."""
    score = interest(c, n_today)
    w = round(config.INTEREST_W_CH * 10)
    tip = dk.with_src(
        f"이 이슈를 방송이 얼마나 많이 다뤘는지 1~10으로 나타낸 점수입니다.\n"
        f"· 방송 = 오늘 방송 {n_today}곳 중 {c['n_channels']}곳\n"
        f"· 영상 = {c['n_videos']}개 ({config.INTEREST_FULL_VIDEOS}개 이상이면 만점)\n"
        f"계산 : 방송 비율 {w} · 영상 수 {10 - w} 비중. 몇 곳이 다뤘는지를 더 무겁게 봅니다. 방송의 시각(긍정 · 부정)과는 상관없습니다.",
        "유튜브 방송 요약")
    return (f'<span data-interest="{score}" style="font-size:{dk.NAME};line-height:{dk.LH_CARD};color:#111;font-weight:400;white-space:nowrap;display:inline-flex;align-items:center;">'
            f'관심도 : <b style="font-weight:700;margin-left:4px;">{score}</b>{dk.tip(tip)}</span>')


def _stance_bar(c, n_today):
    """시각 막대 — 블로그 기준 범례 막대(design_kit.legend_bar). 제목(`방송의 시각 n건`)은 뺐고 범례가 막대 위 왼쪽,
    오른쪽 `관심도 : n` (2026-10-23 사용자)."""
    s = c["stances"]
    segs = [(nm, s.get(k, 0), *dk.BAR_PASTEL[kind]) for k, nm, kind in STANCE_BAR]
    return dk.legend_bar("", segs, aside=_interest_html(c, n_today), legend_top=True)


def _cluster_item(i, c, narrative, n_today):
    """이슈 카드 — 제목 / 라벨 줄(오른쪽 정렬, 사이 2px) / 설명 문장 / 시각 막대(+ 영상 · 방송 수) / 종목 (2026-10-23 사용자).
    이슈마다의 영상 링크는 두지 않는다 — 대표 하나는 근거로 애매하고, 전체는 맨 아래 출처에 있다."""
    detail = (narrative or {}).get("items", {}).get(f"c{i}") or _py_detail(c)
    pills = [dk.pill(c["category_ko"], bare=True)] + ([dk.pill("예상 밖", "uncertain", bare=True)] if c["surprise"] else [])
    if c.get("daily"):
        pills.append(_link_pill("데일리 다룸", DAILY_LIST_URL, "데일리 리포트에서 자세히"))
    head = f'<span style="display:block;color:#111;font-weight:700;">{_esc(c["topic"])}</span>'   # 라벨 줄은 카드 맨 아래 (2026-10-23 사용자)
    syms = [t for t in c["tickers"] if "(비상장)" not in t]
    tick = f'<span style="{SUB_STYLE}">종목 : {_esc(" · ".join(syms[:8]))}</span>' if syms else ""
    return (f'{head}<span style="{DETAIL_STYLE}">{_esc(detail)}</span>'
            f'<span style="display:block;line-height:{dk.LH_CARD};">{_stance_bar(c, n_today)}</span>{tick}'
            f'<span data-pills="1" style="{PILL_ROW.replace("margin:4px 0 0;", "margin:10px 0 0;")}">{"".join(pills)}</span>')


def sec_lead(m, narrative, d):
    """맨 앞 요약 한 줄 (검색 결과 설명문 자리 — data-seo-lead). 2026-10-23 사용자: 두 줄 → 한 줄, 영상 수 · 묶음 수 같은 내부 숫자는 뺐다."""
    top = m["clusters"][0] if m["clusters"] else None
    _, mo, dd = d.split("-")
    md = f"{int(mo)}월 {int(dd)}일 "   # 날짜는 제목 오른쪽이 아니라 요약 맨 앞 (2026-10-23 사용자: 상세 화면의 제목 날짜 삭제 · 요약에 연도 없이)
    # 머리 한 줄은 파이썬이 센 숫자로 — 모델이 "방송 5곳" 처럼 수를 지어냈다 (2026-10-22 세 번째 CI, 100 미만 정수는 fact_check 가 보지 않는다)
    if top:
        view = "엇갈립니다" if top["split"] else {"bullish": "긍정 쪽입니다", "bearish": "부정 쪽입니다"}.get(max(top["stances"], key=top["stances"].get), "중립입니다")
        first = f"{md}밤사이 미국 방송 {top['n_channels']}곳이 '{top['topic']}'{_obj(top['topic'])} 가장 많이 다뤘고, 시각은 {view}."
    else:
        first = f"{md}밤사이 미국 방송이 다룬 이슈입니다."
    # data-lead: 홈 카드가 이 머리 구획(다음 h2 전까지 — 이슈 카드 포함)을 읽는다. 이슈 구획 제목을 없앴기 때문 (2026-10-23)
    # data-title-back: 테마가 글 제목 왼쪽에 홈으로 가는 네모 화살표를 붙인다 (인물 발언 상세와 같은 모양, 2026-10-23 사용자)
    out = f'<p data-seo-lead="1" data-lead="1" data-title-back="/" data-title-back-label="홈" style="{dk.SEO_LEAD}">{_esc(first)}</p>'
    if m["phase"] == 1:
        out += dk.muted("10시 15분에 Mad Money · 증시각도기를 더해 갱신합니다.")
    return out


def sec_issues(m, narrative):
    items = [_cluster_item(i, c, narrative, m["n_channels"]) for i, c in enumerate(m["clusters"])]
    return dk.item_cards(items, sub=True) if items else ""


def _kr_label(k):
    """한국장 소식 줄 앞 라벨 — 연결된 한국 종목 · 기업 이름, 없으면 분야 이름 (2026-10-23 사용자 안: `[삼성전자] 애플 첫 폴더블 아이폰 출시`)."""
    for t in k["tickers"]:
        if "(KR)" in t or "(비상장)" in t:
            base = t.replace("(KR)", "").replace("(비상장)", "").strip()
            return KR_NAME.get(base, base)
    return config.CATEGORY_KO.get(k["category"], "한국")


# 한국장 소식 · 장 초반에 이어 볼 것 = 홈 '주요 뉴스' 기사와 같은 모양 (2026-10-23 사용자: "카드 말고 구분선, 내용 간격 동일, 라벨은 내용 아래,
# 출처는 라벨이 아니라 주요 뉴스처럼 글자로"). 좌우 = 좌측 기준선 dk.ALIGN_PX (홈 실시간 뉴스 글자, 2026-10-24 사용자). 나머지 값은 alphaflow-home.html .news-item · .news-sum · .news-labels · .news-sub 와 같다
NEWS_LI = f"margin:0;padding:20px {dk.ALIGN_PX}px 25px;border-top:1px solid #E2E8F0;font-size:18px;line-height:34px;color:#111;word-break:keep-all;"
NEWS_LI_FIRST = f"margin:0;padding:2px {dk.ALIGN_PX}px 25px;font-size:18px;line-height:34px;color:#111;word-break:keep-all;"
NEWS_SUM = "display:block;margin-top:4px;font-size:16px;line-height:26px;font-weight:400;color:#333;word-break:keep-all;"
NEWS_LABELS = "display:flex;flex-wrap:wrap;align-items:center;gap:3px;margin-top:8px;line-height:20px;"
NEWS_SUB = f"font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};margin-left:3px;"   # 라벨 사이 3 + 3 = 홈 뉴스의 라벨 ~ 출처 6px


def _news_row(label, k):
    """한 줄 = 영상 하나: 제목(굵게, 그 영상 링크 — 홈 주요 뉴스처럼 제목이 원문 링크) / 설명 문장 / 라벨 줄 [라벨] [방향] [예상 밖] + 출처 글자(채널).
    label = 한국 종목 · 기관(한국장 소식), None = 라벨 없이 방향부터(장 초반에 이어 볼 것 — 채널은 출처 글자). 발언자는 쓰지 않는다."""
    url = k.get("url")
    topic = _esc(k["topic"])
    title = (f'<a href="{_esc(url)}" target="_blank" rel="noopener" data-trhelp="skip" style="color:#111;font-weight:700;text-decoration:none;">{topic}</a>'
             if url else f'<b style="color:#111;">{topic}</b>')
    note = f'<span style="{NEWS_SUM}">{_esc(k["note"])}</span>' if k.get("note") else ""
    pills = ([dk.pill(label, bare=True)] if label else []) + [dk.pill(config.STANCE_KO.get(k["stance"], "중립"), STANCE_PILL.get(k["stance"], "neutral"), bare=True)]
    if k.get("surprise") in (True, "surprise"):
        pills.append(dk.pill("예상 밖", "uncertain", bare=True))
    ch = _esc(_short(k.get("channel", "")))
    if url:   # 출처 글자 = 그 영상 링크 (끝 아이콘은 테마 CSS, 2026-10-23 사용자)
        src = (f'<a href="{_esc(url)}" target="_blank" rel="noopener" data-trhelp="skip" aria-label="{ch} 영상 보기" '
               f'style="{NEWS_SUB}text-decoration:none;white-space:nowrap;">{ch}</a>')
    else:
        src = f'<span style="{NEWS_SUB}">{ch}</span>'
    return f'{title}{note}<span data-pills="1" style="{NEWS_LABELS}">{"".join(pills)}{src}</span>'


def _news_list(rows):
    lis = "".join(f'<li style="{NEWS_LI_FIRST if i == 0 else NEWS_LI}">{r}</li>' for i, r in enumerate(rows))
    return f'<ul style="margin:0 0 8px;padding:0;list-style:none;">{lis}</ul>' if lis else ""


def sec_korea(m):
    return _news_list([_news_row(_kr_label(k), k) for k in m["korea"]])


ALIGN_PX = dk.ALIGN_PX   # 구획 제목 · 목록 · 종목 글 · 출처의 왼쪽 시작선 = 공통 좌측 기준선 (2026-10-24 사용자: 홈 실시간 뉴스에 맞춤)


def sec_tickers(m):
    if not m["tickers"]:
        return ""
    txt = " · ".join(f"{t['sym']}({t['n']})" for t in m["tickers"])
    return (f'<p style="margin:0 0 8px;padding:0 {ALIGN_PX}px;color:#333;word-break:keep-all;">{_esc(txt)}</p>'
            f'<p style="margin:0;padding:0 {ALIGN_PX}px;color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};">괄호는 언급한 영상 수. 언급 사실만 적으며 종목 의견이 아닙니다.</p>')


def sec_required(m):
    rows = []
    for ch in ("CNBC Mad Money", "증시각도기", "당잠사"):
        for r in m["required"].get(ch, []):
            rows.append(_news_row(None, {**r, "channel": ch}))   # 채널은 출처 글자 · 제목이 영상 링크 (2026-10-23)
    return _news_list(rows)


CHEV_BOX = ("display:inline-flex;align-items:center;justify-content:center;flex:none;width:28px;height:28px;"
            "border:1px solid #E2E8F0;border-radius:6px;background:#fff;color:#111;")   # H 아코디언 화살표 버튼 28px (가이드라인 2-1 H)


AI_MODEL_SLOT = "@@AI_MODEL@@"


def sec_sources(m, model=None):
    """출처 — 제목 `출처` 옆 열고 닫는 화살표 버튼만, 그 오른쪽에 `AI 서술 · 모델` (2026-10-23 사용자). 누르면 영상 목록.
    영어 제목 수십 줄은 읽을거리가 아니라 접어 둔다 — 출처 표시는 남고, 접힌 글도 검색엔진은 읽는다.
    AI 서술 줄이 여기 있으므로 render 는 design_kit.with_ai_model 을 부르지 않는다."""
    lis = "".join(dk.dot_li(f'<a href="{_esc(s["url"])}" target="_blank" rel="noopener" data-trhelp="skip" style="color:#1a73e8;text-decoration:none;">'
                            f'{_esc(_short(s["channel"]))} · {_esc(s["title"][:70])}</a>', size=2, color="#333", margin="6px 0")
                  for s in m["sources"])
    # 모델 이름은 build_body 의 fix_colons 뒤에 넣는다 — `groq:openai/…` 의 콜론이 띄어지지 않게 (AI_MODEL_SLOT)
    ai = f'<span data-ai-model="1" style="font-size:{dk.TINY};line-height:{dk.LH_TINY};font-weight:400;color:{dk.NOTE};">AI 서술 · {AI_MODEL_SLOT}</span>' if model else ""
    summary = (f'<summary aria-label="출처 영상 {len(m["sources"])}개 열고 닫기" style="list-style:none;cursor:pointer;display:flex;align-items:center;gap:10px;margin:28px 0 11px;padding-left:{ALIGN_PX}px;">'
               f'<span style="color:#111;font-size:{dk.H2_SIZE};line-height:{dk.LH_H2};font-weight:700;">출처</span>'
               f'<span style="{CHEV_BOX}">{dk.ACC_CHEV}</span>{ai}</summary>')
    return (f'<details data-acc="1" data-sources="1">{summary}'
            f'<ul style="margin:0 0 8px;padding:0 0 0 {ALIGN_PX + 2}px;list-style:none;font-size:{dk.TINY};line-height:{dk.LH_TINY};">{lis}</ul></details>')


def build_body(m, narrative, d):
    parts = [dk.WRAP_OPEN, sec_lead(m, narrative, d)]
    issues = sec_issues(m, narrative)
    if issues:
        parts.append(issues)   # 구획 제목 · 안내 없이 요약 바로 아래 (2026-10-23 사용자: "방송이 본 이슈 · 방송 · 영상 수가 많은 순" 삭제)
    korea = sec_korea(m)
    if korea:
        parts.append(dk.section("한국장에 영향을 줄 만한 소식", korea, line=True))   # 옛 제목 "한국 연결" · 제목 아래 구분선 (2026-10-23 사용자)
    tick = sec_tickers(m)
    if tick:
        parts.append(dk.section("방송에서 언급된 종목", tick))
    req = sec_required(m)
    if req and m["phase"] >= 2:
        parts.append(dk.section("장 초반에 이어 볼 것", req))   # 옆 안내(채널 이름) 삭제 (2026-10-23 사용자)
    parts.append(sec_sources(m, (narrative or {}).get("model")))
    parts.append(dk.WRAP_CLOSE)
    html = dk.align_titles("\n".join(parts), ALIGN_PX)   # 구획 제목도 같은 시작선
    return dk.fix_colons(dk.formal(html)).replace(AI_MODEL_SLOT, _esc((narrative or {}).get("model") or ""))


def render(media_path=None, narrative_path=None, output_dir=None):
    output_dir = output_dir or config.OUTPUT_DIR
    with open(media_path or os.path.join(output_dir, "media.json"), encoding="utf-8") as f:
        m = json.load(f)
    n = None
    np_ = narrative_path or os.path.join(output_dir, "narrative.json")
    if os.path.exists(np_):
        with open(np_, encoding="utf-8") as f:
            n = json.load(f)
    if m["n_items"] < config.MIN_ITEMS:
        print(f"[html] 재료 {m['n_items']}건 < {config.MIN_ITEMS} — 본문을 만들지 않는다 (게시 없음)")
        return None
    d = m["edition"]
    title = config.post_title(d)
    body = build_body(m, n, d)   # AI 서술 줄은 출처 줄 안 (sec_sources) — with_ai_model 을 부르지 않는다
    body_path = os.path.join(output_dir, "media_body.html")
    with open(body_path, "w", encoding="utf-8") as f:
        f.write(body)
    with open(os.path.join(output_dir, "media.html"), "w", encoding="utf-8") as f:
        f.write(PREVIEW.replace("__TITLE__", _esc(title)).replace("__BODY__", body))
    with open(os.path.join(output_dir, "title.txt"), "w", encoding="utf-8") as f:
        f.write(title)
    mock = dk.write_mock(body, os.path.join(output_dir, "media_mock.html"), title)
    print(f"[html] {len(body):,}자 → {body_path}" + (f" · 목업 {mock}" if mock else ""))
    return body_path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    render()
