"""media.json + narrative.json → output/media_body.html (Blogger 본문) · media.html (미리보기) · title.txt.

틀 (기획 11절 초안 — 발행하며 고친다):
    맨 앞 요약 한 줄(data-seo-lead)
    → 방송이 가장 많이 다룬 이슈 순위 (공용 카드: n. 주제 / 설명 / 관련 페이지 / 라벨 · 관심도 · 방송 n곳 — 2026-10-25 짧은 순위 글로)
    → 끝   — 2026-10-23 사용자 정리 · 한국장 소식은 미국 데일리 `한국장` 탭으로 옮겼다 (2026-10-25)
    `방송에서 언급된 종목` · `장 초반에 이어 볼 것` 은 뺐다 (2026-10-25 사용자 '나' 안 — 이슈 줄은 종목 페이지 · 데일리 · 홈으로 흩어 보낸다, media_feed)
    맨 아래 출처(영상 목록, 접기)는 뺐다 (2026-10-25 사용자: 제목 · 채널 글자가 이미 그 영상 링크라 같은 링크의 반복)
쓰지 않는 것: 요약 문장 · 자막 수치 · 가격 · 추천 어투. 종목은 상세 페이지가 있으면 링크(색 그대로, 2026-10-25 사용자 — 10-23 의 '종목 링크 없음'을 바꿈). 영문 원문 제목은 쓰지 않는다.
"""

import json
import os
import re
import sys

import config

sys.path.insert(0, os.path.join(config.BASE_DIR, ".."))
import design_kit as dk  # noqa: E402
import media_feed  # noqa: E402  — 별칭 · 종목 페이지 목록 (방송 줄 나눠 보내기와 같은 표)

_esc = dk.esc
PREVIEW = """<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>__TITLE__</title></head>
<body style="max-width:900px;margin:0 auto;padding:16px;background:#fff;"><h1 style="font-size:26px;">__TITLE__</h1>__BODY__</body></html>"""
DAILY_LIST_URL = "https://alpha-scope.blogspot.com/search/label/%EB%8D%B0%EC%9D%BC%EB%A6%AC%20%EB%B8%8C%EB%A6%AC%ED%95%91"
SUB_STYLE = f"display:block;color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};margin-top:2px;"


def _py_detail(c):
    """서술이 없을 때의 파이썬 문장 — 사실만."""
    verb = "엇갈리게 봤습니다" if c["split"] else {"bullish": "긍정적으로 봤습니다", "bearish": "부정적으로 봤습니다"}.get(max(c["stances"], key=c["stances"].get), "다뤘습니다")
    return f"{c['category_ko']} 이슈 '{c['topic']}' 를 방송 {c['n_channels']}곳 · 영상 {c['n_videos']}개가 {verb}."


# 이슈 카드 (2026-10-23 사용자: "제목 · 설명 문장 · 종목 · 영상 수가 중요, 시각은 그래프, 나머지는 불필요"):
#   제목 + 라벨(분야 · 예상 밖 · 데일리 다룸) / 설명 문장 16px / 시각 비율 막대(F) / `영상 n개 ↗ · 방송 n곳 · 종목 : …` 14px
#   발언자 · 채널 이름 나열 · 영상 링크 다섯 줄은 뺐다 — 여러 방송을 모은 결과라 카드의 방송 · 영상 수로 충분 (2026-10-25)
STANCE_PILL = {"bullish": "positive", "bearish": "negative", "neutral": "neutral"}


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


def _names(c):
    """이 이슈가 간 종목 페이지 — 종목 상세가 있는 티커만, 한국어 이름 링크 (색 그대로). 비상장 · 한국 종목은 뺀다."""
    out = []
    for t in c["tickers"]:
        sym = media_feed.ALIAS.get(str(t).upper(), str(t).upper())
        if sym in media_feed.UNI.BY_SYM and sym not in out:
            out.append(sym)
    return [dk.stock_link(x, _esc(media_feed.UNI.name(x))) for x in out[:6]]


def _cluster_item(i, c, narrative, n_today):
    """순위 한 줄 (2026-10-25 사용자 '나' 안: 미디어 데일리 = 오늘 방송이 가장 많이 다룬 이슈 순위). 공용 뉴스 카드(news_item) 모양:
        n. 주제 / 설명 문장(AI 서술) / 관련 페이지 : 종목 링크 / [분야] [방향] [예상 밖] [관심도 n] (데일리 다룸)  방송 n곳 · 영상 n개
    이슈마다의 줄은 종목 페이지 · 데일리 · 홈으로 흩어 보내고(media_feed), 여기는 모아 보는 순위만 — 시각 막대 · 종목 수 줄은 뺐다."""
    detail = (narrative or {}).get("items", {}).get(f"c{i}") or _py_detail(c)
    st = c["stances"]
    view = "엇갈림" if c["split"] else config.STANCE_KO.get(max(st, key=st.get), "중립")
    kind = "uncertain" if c["split"] else STANCE_PILL.get(max(st, key=st.get), "neutral")
    pills = [dk.pill(c["category_ko"], bare=True), dk.pill(view, kind, bare=True)] + ([dk.pill("예상 밖", "uncertain", bare=True)] if c["surprise"] else [])
    pills.append(dk.pill(f"관심도 {interest(c, n_today)}", bare=True))
    if c.get("daily"):
        pills.append(_link_pill("데일리 다룸", DAILY_LIST_URL, "데일리 리포트에서 자세히"))
    names = _names(c)
    subs = [f'<span style="{SUB_STYLE}">관련 페이지 : {" · ".join(names)}</span>'] if names else []   # 상세 페이지 링크 (2026-10-25 사용자)
    return dk.news_item(f"{i + 1}. {_esc(c['topic'])}", None, detail, subs, " ".join(pills), [f"방송 {c['n_channels']}곳 · 영상 {c['n_videos']}개"])


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


ALIGN_PX = dk.ALIGN_PX   # 구획 제목 · 목록 · 종목 글 · 출처의 왼쪽 시작선 = 공통 좌측 기준선 (2026-10-24 사용자: 홈 실시간 뉴스에 맞춤)


def build_body(m, narrative, d):
    parts = [dk.WRAP_OPEN, sec_lead(m, narrative, d)]
    issues = sec_issues(m, narrative)
    if issues:
        parts.append(issues)   # 구획 제목 · 안내 없이 요약 바로 아래 (2026-10-23 사용자: "방송이 본 이슈 · 방송 · 영상 수가 많은 순" 삭제)
    # `방송에서 언급된 종목` · `장 초반에 이어 볼 것` 은 뺐다 (2026-10-25 사용자 '나' 안) — 종목 이야기는 종목 페이지 뉴스로, 짧은 순위 글만 남긴다.
    # `한국장에 영향을 줄 만한 소식` 은 미국 데일리 `한국장` 탭으로 옮겼다 (2026-10-25 사용자, daily-report sec_korea_news)
    parts.append(dk.WRAP_CLOSE)
    html = dk.align_titles("\n".join(parts), ALIGN_PX)   # 구획 제목도 같은 시작선
    return dk.fix_colons(dk.formal(html))   # 글 끝 "AI 서술" 줄 없음 — 공통 푸터의 AI 고지와 중복 (2026-10-25 사용자)


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
    body = build_body(m, n, d)
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
