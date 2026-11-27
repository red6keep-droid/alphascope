"""댓글 캐릭터 카드 — 불러오기 · AI 지시문 채우기 · 글 검사 (AI 없음, 글자 대조만).

characters.json (캐릭터 10명 카드) + characters_prompt.txt (지시문 틀).
나중에 characters.py 가 이 파일의 load · prompt · problems 를 그대로 쓴다.

검사 = 글 하나에 걸린 까닭 목록(빈 목록 = 통과):
  ① 숫자: 본문 숫자가 모두 재료 숫자 안에 있나(allowed 를 줄 때만)
  ② 금지어: banned.patterns
  ③ 길이: 제목 · 본문 · 문장 수, 줄표 없음
  ④ 말투: 캐릭터 style 규칙(어미 · 느낌표 · 물음표 · 첫 문장 · 문장 길이 · 쓰지 않는 말)
비슷한 글 검사(글자 3개 묶음 겹침)도 여기 있다 — 지난 글 목록은 부르는 쪽이 준다.

  python experiments/comments/characters_check.py     # 자체 시험: 카드 · 예시 글 · 그림 · 스티커 · 지시문
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CARD = os.path.join(HERE, "characters.json")
PROMPT = os.path.join(HERE, "characters_prompt.txt")
CROWN_AVAS = {"p03", "p11"}   # 머리 왕관 그림 = 캐릭터 왕관 표시와 겹쳐 쓰지 않음(mock_comments.CROWN_AVAS 와 같음)

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
DATE_LIKE = re.compile(r"\d+월\s*\d+일|\d{4}년|\d{1,2}-\d{1,2}")


def load():
    return json.load(open(CARD, encoding="utf-8"))


def sentences(text):
    return [s for s in SENT_SPLIT.split(text.strip()) if s]


def _style(c, text):
    st, out = c["style"], []
    ss = sentences(text)
    if not ss:
        return ["본문 없음"]
    last = ss[-1]
    if st.get("endings_any") and not any(last.endswith(e) for e in st["endings_any"]):
        out.append(f"말투: 끝 어미({' · '.join(st['endings_any'])}) 아님")
    if st.get("no_end_yo") and any(re.search(r"요[.!?]?$", s) for s in ss):
        out.append("말투: `요` 로 끝나는 문장")
    if st.get("no_bang") and "!" in text:
        out.append("말투: 느낌표")
    if st.get("needs_bang") and "!" not in text:
        out.append("말투: 느낌표 없음")
    if st.get("needs_q") and "?" not in text:
        out.append("말투: 물음표 없음")
    if st.get("last_ends_q") and not last.endswith("?"):
        out.append("말투: 질문으로 끝나지 않음")
    if "first_has_date_or" in st and not (DATE_LIKE.search(ss[0]) or any(w in ss[0] for w in st["first_has_date_or"])):
        out.append("말투: 첫 문장에 날짜 없음")
    if st.get("first_has_ellipsis") and "…" not in ss[0]:
        out.append("말투: 첫 문장에 말줄임 없음")
    if st.get("first_starts_with_name") and "," not in ss[0][:20]:
        out.append("말투: 이름 · 종목 먼저 쉼표로 끊지 않음")
    if st.get("needs_any") and not any(w in text for w in st["needs_any"]):
        out.append(f"말투: {' · '.join(st['needs_any'])} 없음")
    if st.get("max_sentence_chars"):
        long_ = [s for s in ss if len(s) > st["max_sentence_chars"]]
        if long_:
            out.append(f"말투: 문장이 {st['max_sentence_chars']}자 넘음({len(long_)}개)")
    for w in st.get("never", []):
        if w in text:
            out.append(f"말투: 쓰지 않는 말 `{w}`")
    return out


def problems(card, c, title, text, allowed=None):
    """글 하나 검사. allowed = 재료 숫자 문자열 모음(None 이면 숫자 검사 생략 — 예시 글 자체 시험용)."""
    lim, out = card["limits"], []
    if not title or len(title) > lim["title_max"]:
        out.append(f"길이: 제목 1 ~ {lim['title_max']}자 아님")
    if len(text) > lim["text_max"]:
        out.append(f"길이: 본문 {lim['text_max']}자 넘음")
    n = len(sentences(text))
    if not lim["sentences"][0] <= n <= lim["sentences"][1]:
        out.append(f"길이: 문장 {n}개({lim['sentences'][0]} ~ {lim['sentences'][1]} 아님)")
    if "—" in title + text:
        out.append("줄표")
    for p in card["banned"]["patterns"]:
        m = re.search(p, title + " " + text)
        if m:
            out.append(f"금지어 `{m.group(0)}`")
    if allowed is not None:
        norm = {a.replace(",", "") for a in allowed}
        bad = [n for n in NUM.findall(title + " " + text) if n.replace(",", "") not in norm]
        if bad:
            out.append(f"숫자: 재료에 없는 값 {len(bad)}개")
    return out + _style(c, text)


def _grams(s):
    s = re.sub(r"\s+", "", s)
    return {s[i:i + 3] for i in range(len(s) - 2)}


def too_similar(card, text, others):
    """다른 글(같은 캐릭터 지난 14일 · 그날 다른 캐릭터)과 글자 3개 묶음 겹침 비율 · 첫 글자가 같으면 True."""
    sim = card["similarity"]
    g = _grams(text)
    head = re.sub(r"\s+", "", text)[:sim["first_chars"]]
    for o in others:
        og = _grams(o)
        if g and og and len(g & og) / min(len(g), len(og)) > sim["trigram_overlap_max"]:
            return True
        if re.sub(r"\s+", "", o)[:sim["first_chars"]] == head:
            return True
    return False


def prompt(card, c, key_label, material, recent=(), parent=""):
    lim = card["limits"]
    return open(PROMPT, encoding="utf-8").read().format(
        name=c["name"], kind=c["kind"], personality=c["personality"], habit=c["habit"], sees=c["sees"],
        style_label=c["style"]["label"], never=" · ".join(c["style"].get("never", [])) or "없음",
        openers=" / ".join(c["openers"]), closers=" / ".join(c["closers"]),
        examples="\n".join(f"- {e}" for e in c["examples"]),
        recent="\n".join(f"- {r}" for r in recent) or "(없음)",
        key_label=key_label, material=material,
        parent=f"\n[답글을 다는 글 — 다른 Newfact 캐릭터의 글]\n{parent}\n" if parent else "",
        title_max=lim["title_max"], text_max=lim["text_max"], sent_min=lim["sentences"][0], sent_max=lim["sentences"][1])


def selftest():
    card, bad = load(), []
    cs = card["chars"]
    if len(cs) != 10:
        bad.append(f"캐릭터 {len(cs)}명")
    for k in ("id", "name", "avatar"):
        if len({c[k] for c in cs}) != len(cs):
            bad.append(f"{k} 겹침")
    lim = card["limits"]
    if sum(lim["slots"].values()) != lim["per_day"]:
        bad.append("세 때 상한 합 ≠ 하루 상한")
    avas = os.path.join(HERE, "output", "avatars")
    stk = os.path.join(HERE, "..", "course", "chars")
    for c in cs:
        if c["avatar"] in CROWN_AVAS or not c["avatar"].startswith("p"):
            bad.append(f"{c['name']}: 그림 {c['avatar']} (히어로 판 · 왕관 그림 제외)")
        if not os.path.exists(os.path.join(avas, c["avatar"] + ".webp")):
            bad.append(f"{c['name']}: 그림 파일 없음")
        if not 1 <= len(c["stickers"]) <= 2:
            bad.append(f"{c['name']}: 스티커 {len(c['stickers'])}개")
        for s in c["stickers"]:
            if not s.startswith(card["stickers_allowed_prefix"]) or not os.path.exists(os.path.join(stk, f"c_{s}.webp")):
                bad.append(f"{c['name']}: 스티커 {s}")
        if not set(c["slots"]) <= set(lim["slots"]):
            bad.append(f"{c['name']}: 자리 {c['slots']}")
        if not 5 <= len(c["examples"]) <= 8:
            bad.append(f"{c['name']}: 예시 {len(c['examples'])}개")
        for i, e in enumerate(c["examples"], 1):
            for p in problems(card, c, "제목", e):
                bad.append(f"{c['name']} 예시 {i}: {p}")
        for i, e in enumerate(c["examples"][1:], 2):   # 예시끼리 너무 닮았나(첫 예시 = 같은 사실 열 명 본보기라 뺌)
            if too_similar(card, e, c["examples"][1:i - 1]):
                bad.append(f"{c['name']} 예시 {i}: 앞 예시와 닮음")
        prompt(card, c, "kr-report", "(재료)", ["지난 글"], "부모 글")
    others = {c["name"]: c for c in cs}   # 다른 캐릭터 말투 규칙에 걸리는지 — 이름을 가려도 누구 글인지 갈리나
    for c in cs:
        for o in cs:
            if o is c:
                continue
            if all(not _style(o, e) for e in c["examples"][1:]):
                bad.append(f"{c['name']} 예시가 {o['name']} 말투 규칙도 전부 통과(규칙이 못 가름)")
    t = problems(card, others["물결이"], "제목", "오늘 3.2% 상승! 거래량은 평소의 2.1배예요!", allowed={"3.2", "2.1"})
    t2 = problems(card, others["물결이"], "제목", "오늘 3.2% 상승! 지금 사세요! 거래량은 평소의 9.9배예요!", allowed={"3.2", "2.1"})
    if t or len(t2) < 2:
        bad.append(f"검사 자체 시험 실패: {t} / {t2}")
    return bad


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    b = selftest()
    print("\n".join(b) if b else "캐릭터 카드 자체 시험 통과")
    sys.exit(1 if b else 0)
