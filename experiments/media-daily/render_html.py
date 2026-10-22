"""media.json + narrative.json → output/media_body.html (Blogger 본문) · media.html (미리보기) · title.txt.

틀 (기획 11절 초안 — 발행하며 고친다):
    맨 앞 요약 두 줄(data-seo-lead) → 머리 카드(방송이 가장 많이 다룬 이슈 · 우리 숫자 한 줄)
    → 방송이 본 이슈 (상위 n, 카드마다: 소주제 · 영상 n · 채널 m · 방향 · 예상 밖 · 발언자 · [데일리 다룸 →] · 영상 링크)
    → 한국 연결 → 방송에서 언급된 종목(글자만) → 장 초반에 이어 볼 것(2차) → 출처(영상 목록)
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


def _who(name):
    """발언자 한국어 표기 — 아는 이름만 (config.SPEAKER_KO), 소속 괄호는 뗀다."""
    base = re.sub(r"\s*\(.*?\)\s*$", "", str(name or "")).strip()
    return config.SPEAKER_KO.get(base, base)


def _stance_text(c):
    s = c["stances"]
    parts = [f"{config.STANCE_KO[k]} {v}" for k, v in sorted(s.items(), key=lambda kv: -kv[1]) if v]
    return ("시각 엇갈림 : " if c["split"] else "시각 : ") + " · ".join(parts)


def _py_detail(c):
    """서술이 없을 때의 파이썬 문장 — 사실만."""
    verb = "엇갈리게 봤습니다" if c["split"] else {"bullish": "긍정적으로 봤습니다", "bearish": "부정적으로 봤습니다"}.get(max(c["stances"], key=c["stances"].get), "다뤘습니다")
    return f"{c['category_ko']} 이슈 '{c['topic']}' 를 방송 {c['n_channels']}곳 · 영상 {c['n_videos']}개가 {verb}."


def _cluster_item(i, c, narrative):
    detail = (narrative or {}).get("items", {}).get(f"c{i}") or _py_detail(c)
    head = f'<span style="color:#111;font-weight:700;">{_esc(c["topic"])}</span>'
    meta = [f"영상 {c['n_videos']}개", f"채널 {c['n_channels']}곳 ({' · '.join(_short(x) for x in c['channels'][:4])})", _stance_text(c)]
    if c["surprise"]:
        meta.append("예상 밖")
    subs = [_esc(" · ".join(meta)), _esc(detail)]
    if c["speakers"]:
        subs.append("발언 : " + _esc(" · ".join(_who(x) for x in c["speakers"][:3])))
    if c["tickers"]:
        subs.append("종목 : " + _esc(" · ".join(t for t in c["tickers"] if "(비상장)" not in t)[:120]))
    if c.get("daily"):
        subs.append(f'데일리 리포트가 다룬 이슈 — <a href="{DAILY_LIST_URL}" style="color:#1a73e8;text-decoration:none;">데일리에서 자세히 →</a>')
    links = " · ".join(f'<a href="{_esc(v["url"])}" target="_blank" rel="noopener" data-trhelp="skip" style="color:#1a73e8;text-decoration:none;">{_esc(_short(v["channel"]))}</a>'
                       for v in c["videos"][:5])
    subs.append("영상 : " + links)
    sub_html = "".join(f'<span style="{SUB_STYLE}">{x}</span>' for x in subs)
    pills = [dk.pill(c["category_ko"], bare=True)] + ([dk.pill("데일리 다룸", bare=True)] if c.get("daily") else [])
    lab = f'<span style="display:block;line-height:1;margin:8px 0 0;">{" ".join(pills)}</span>'
    return f"{head}{sub_html}{lab}"


def sec_lead(m, narrative, d):
    top = m["clusters"][0] if m["clusters"] else None
    _, mo, dd = d.split("-")
    first = (narrative or {}).get("lead") or (f"방송 {top['n_channels']}곳이 '{top['topic']}' 를 가장 많이 다뤘습니다." if top else "")
    second = f"{int(mo)}월 {int(dd)}일 아침 기준 영상 {m['n_items']}개 · 채널 {m['n_channels']}곳 · 이슈 묶음 {m['n_clusters']}개"
    if m["phase"] == 1:
        second += " · 10시 15분에 Mad Money · 증시각도기를 더해 갱신합니다"
    return f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">{_esc(first)}<br>{_esc(second)}</p>'


def sec_issues(m, narrative):
    items = [_cluster_item(i, c, narrative) for i, c in enumerate(m["clusters"])]
    return dk.item_cards(items) if items else ""


def sec_korea(m):
    rows = []
    for k in m["korea"]:
        who = _who((k["speakers"] or [_short(k["channel"])])[0])
        text = f"{who} — {k['topic']} ({config.STANCE_KO.get(k['stance'], '')}{' · 예상 밖' if k['surprise'] == 'surprise' else ''})"
        syms = " · ".join(t.replace("(KR)", "") for t in k["tickers"][:4])
        link = f'<a href="{_esc(k["url"])}" target="_blank" rel="noopener" data-trhelp="skip" style="color:#1a73e8;text-decoration:none;">{_esc(_short(k["channel"]))}</a>'
        rows.append(f'<span style="color:#111;">{_esc(text)}</span><span style="{SUB_STYLE}">{("종목 : " + _esc(syms) + " · ") if syms else ""}영상 : {link}</span>')
    return dk.item_cards(rows) if rows else ""


def sec_tickers(m):
    if not m["tickers"]:
        return ""
    txt = " · ".join(f"{t['sym']}({t['n']})" for t in m["tickers"])
    return (f'<p style="margin:0 0 8px;color:#333;word-break:keep-all;">{_esc(txt)}</p>'
            f'<p style="margin:0;color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};">괄호는 언급한 영상 수. 언급 사실만 적으며 종목 의견이 아닙니다.</p>')


def sec_required(m):
    rows = []
    for ch in ("CNBC Mad Money", "증시각도기", "당잠사"):
        for r in m["required"].get(ch, []):
            who = _who((r["speakers"] or [_short(ch)])[0])
            text = f"{who} — {r['topic']} ({config.STANCE_KO.get(r['stance'], '')})"
            syms = " · ".join(t for t in r["tickers"][:4] if "(비상장)" not in t)
            link = f'<a href="{_esc(r["url"])}" target="_blank" rel="noopener" data-trhelp="skip" style="color:#1a73e8;text-decoration:none;">{_esc(_short(ch))}</a>'
            rows.append(f'<span style="color:#111;">{_esc(text)}</span><span style="{SUB_STYLE}">{("종목 : " + _esc(syms) + " · ") if syms else ""}영상 : {link}</span>')
    return dk.item_cards(rows) if rows else ""


def sec_sources(m):
    lis = "".join(f'<li style="margin:4px 0;"><a href="{_esc(s["url"])}" target="_blank" rel="noopener" data-trhelp="skip" style="color:#1a73e8;text-decoration:none;">'
                  f'{_esc(_short(s["channel"]))} · {_esc(s["title"][:70])}</a></li>' for s in m["sources"])
    return f'<ul style="margin:0;padding-left:18px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:#333;">{lis}</ul>'


def build_body(m, narrative, d):
    parts = [dk.WRAP_OPEN, sec_lead(m, narrative, d)]
    issues = sec_issues(m, narrative)
    if issues:
        parts.append(dk.section("방송이 본 이슈", issues, summary="영상 · 채널 수가 많은 순"))
    korea = sec_korea(m)
    if korea:
        parts.append(dk.section("한국 연결", korea))
    tick = sec_tickers(m)
    if tick:
        parts.append(dk.section("방송에서 언급된 종목", tick))
    req = sec_required(m)
    if req and m["phase"] >= 2:
        parts.append(dk.section("장 초반에 이어 볼 것", req, summary="Mad Money · 증시각도기 · 당잠사"))
    parts.append(dk.section("출처", sec_sources(m), summary=f"영상 {m['n_items']}개"))
    parts.append(dk.WRAP_CLOSE)
    return dk.fix_colons(dk.formal("\n".join(parts)))


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
    body = dk.with_ai_model(build_body(m, n, d), (n or {}).get("model"))
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
