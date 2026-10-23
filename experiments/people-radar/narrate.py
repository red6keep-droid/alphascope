"""radar.json → output/narrative.json — 신호마다 한국어 헤드라인 + 설명 한 문장 (기획 3절 카드 요약, 한 호출).

머리 한 줄 · 숫자 · 순서는 파이썬(render)이 만든다. 여기서는 원문(1차 본문 · 2차 인용 · 기사 제목)을 한국어로 옮겨 줄이는 일만.
검사: 헤드라인 48자 이내 · 명사형(헤드라인체) · 설명 한 문장 · 숫자는 원문에 있는 것만(fact_check) · 앞날 예측 말 금지.
사슬은 config.NARRATE_CHAIN — 예비 공급자 먼저 (llm_chain 머리말 2026-10-19). 전부 실패하면 카드는 원문 제목으로 (render).
"""

import json
import os
import re
import sys

import config

sys.path.insert(0, os.path.join(config.BASE_DIR, ".."))
import fact_check  # noqa: E402
from llm_chain import LLMPool, usage_line  # noqa: E402

HEAD_MAX = 48
DETAIL_MAX = 140
BANNED = re.compile(r"(전망됩니다|예상됩니다|것으로 보입니다|오를 것|내릴 것|매수 추천|매수 권유|매도 추천|투자 기회|주목해야)")   # 매매 공시의 "매수"는 사실이라 막지 않는다
PROMPT = """너는 시장 리서치 블로그의 편집자다. 아래 JSON 은 미국 정책 결정자 · 투자자 · CEO 의 최근 발언 신호 목록이다.
신호마다 한국어로 두 가지를 써서 JSON 객체 하나로만 답하라 (설명 · 마크다운 금지):

{"items": [{"id": "<신호 id 그대로>", "headline": "...", "detail": "..."}]}

headline: 48자 이내 명사형 헤드라인. "인물, 무엇" 형태. 끝은 명사 (예: "베센트, 이란 전쟁 뒤 물가 하락 전망" · "캐시 우드, 아처 에비에이션 1,210만 달러 매수").
          "~했다" · "~이다" 같은 서술형 끝말과 마침표 금지.
detail: 한 문장, 합니다체("~했습니다" · "~입니다"), 140자 이내. 원문에 있는 사실만 — 무엇을 말했는지 또는 했는지, 대상(국가 · 회사 · 자산)과 숫자.
        발언 내용을 바로 서술한다. 인물 이름 · 직함을 다시 쓰지 말고(헤드라인에 있다), "~고 말했습니다" · "~고 밝혔습니다" · "~것으로 보도됐습니다" 같은
        인용 꼬리를 붙이지 말 것 (누가 말했는지 · 보도인지는 카드의 다른 줄이 보여 준다).
        예: "미국이 러시아산 원유 구매를 이유로 유럽 동맹국에 인도 · 중국 2차 관세를 요청했으나 거부당했습니다."
            "엔화를 지키기 위한 미국의 개입을 옹호하며 안정적인 엔화가 매우 중요하다고 했습니다." 가 아니라 "엔화를 지키기 위한 미국의 개입을 옹호했고, 안정적인 엔화가 매우 중요하다는 입장입니다."
        시장 영향 · 앞으로의 방향 · 투자 판단을 쓰지 말 것. 원문에 없는 숫자를 만들지 말 것.
        "attribution" 이 "office" 면 본인이 아니라 기관 발표다 ("백악관은 ~ 발표했습니다").
종목은 회사 이름을 한국어로 쓰고 티커는 괄호 (예: 테슬라(TSLA)). 사람 이름은 한국어 표기.

INPUT:
"""


_WORD_UNIT = [(re.compile(r"(\d+(?:\.\d+)?)\s*(billion|bn)\b", re.I), r"\1B"), (re.compile(r"(\d+(?:\.\d+)?)\s*million\b", re.I), r"\1M"),
              (re.compile(r"(\d+(?:\.\d+)?)\s*trillion\b", re.I), r"\1T")]


def _units(text):
    """'$60 billion' → '$60B' — 공용 숫자 검사(fact_check)가 단위 글자만 읽는다 (10-19: 600억 달러가 원문에 없는 숫자로 탈락)."""
    for rx, rep in _WORD_UNIT:
        text = rx.sub(rep, text or "")
    return text


def _source(radar):
    out = []
    for p in radar["people"]:
        for s in p["signals"]:
            ld = s["lead"]
            out.append({"id": ld["id"], "speaker": f'{p["name_ko"]} ({p["title_ko"]})', "attribution": s["attribution"],
                        "topic": s["topic"], "subtopic": s["subtopic"],
                        "text": _units(ld["quote"] or ld["title"]), "body": _units(ld["body"][:500]),
                        "also_reported": [_units(o["title"]) for o in s["others"]][:3]})
    return out


def _validate(v, src, min_ratio=0.7):
    ids = {x["id"] for x in src}
    items = v.get("items") if isinstance(v, dict) else v
    if not isinstance(items, list):
        raise ValueError("items 없음")
    by_id = {x["id"]: x for x in src}
    out, bad = {}, []
    for it in items:
        if not isinstance(it, dict) or it.get("id") not in ids:
            continue
        h, d = str(it.get("headline") or "").strip().rstrip("."), str(it.get("detail") or "").strip()
        why = []
        if not h or len(h) > HEAD_MAX or re.search(r"(했다|이다|됐다|있다)$", h):
            why.append("헤드라인 형식")
        if not d or len(d) > DETAIL_MAX or d.count(". ") > 0 or not d.endswith("다."):
            why.append("설명 형식")
        if BANNED.search(h + " " + d):
            why.append("예측 · 권유 말")
        probs = fact_check.check([h, d], by_id[it["id"]])
        if probs:
            why.append(f"숫자 {probs[0]}")
        if why:
            bad.append((it["id"], why))
            continue
        out[it["id"]] = {"headline": h, "detail": d}
    for i, why in bad:
        print(f"[narrate] 탈락 {i}: {', '.join(why)}")
    if len(out) < max(1, int(len(ids) * min_ratio)):
        raise ValueError(f"통과 {len(out)}/{len(ids)}")
    return out


SUBTOPIC_KO_PATH = os.path.join(config.BASE_DIR, "ref", "subtopic_ko.json")   # ref/ 는 깃에 남는다 (render_html 과 같은 경로)
SUBTOPIC_PROMPT = """아래 JSON 배열은 미국 시장 뉴스의 짧은 영어 명사구(세부 주제)다. 각각을 2~4 어절의 한국어 명사구로 옮겨 JSON 객체 하나로만 답하라
(설명 · 마크다운 금지): {"<영어 그대로>": "<한국어>", ...}. 회사 이름은 한국어 표기(티커 금지), 고유명사는 통용 표기. 예: "Tariff" → "관세", "Oil Prices" → "유가",
"Memory Chips" → "메모리 반도체", "Rocket Lab" → "로켓랩", "Put Options" → "풋옵션", "ARK Daily Trades" → "ARK 일일 매매".

INPUT:
"""


def translate_subtopics(radar, pool):
    """radar.keywords 의 세부 주제 가운데 subtopic_ko.json 에 없는 것만 한 번에 번역해 누적한다 (2026-10-21 사용자: 키워드로). 실패하면 영어 그대로 보인다."""
    try:
        with open(SUBTOPIC_KO_PATH, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        cache = {}
    have = {k.lower() for k in cache}
    need = sorted({k["key"] for kws in (radar.get("keywords") or {}).values() for k in kws if k["key"].lower() not in have and k["key"] not in config.TOPIC_KO})
    if not need:
        return cache
    def _check(v):   # generate_json 의 validate 는 탈락이면 예외, 통과면 None — bool 을 돌려주면 그 값이 결과가 된다
        if not isinstance(v, dict) or sum(1 for k in need if isinstance(v.get(k), str) and 0 < len(v[k]) <= 24) < len(need) * 0.7:
            raise ValueError("세부 주제 번역 70% 미만")

    try:
        got = pool.generate_json(SUBTOPIC_PROMPT + json.dumps(need, ensure_ascii=False), temperature=0.1, validate=_check)
    except RuntimeError as e:
        print(f"[narrate] 세부 주제 번역 실패 — 영어 그대로: {str(e)[:120]}")
        return cache
    for k in need:
        v = got.get(k)
        if isinstance(v, str) and 0 < len(v.strip()) <= 24:
            cache[k] = v.strip()
    os.makedirs(os.path.dirname(SUBTOPIC_KO_PATH), exist_ok=True)
    with open(SUBTOPIC_KO_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    print(f"[narrate] 세부 주제 번역 {len(need)}개 → {SUBTOPIC_KO_PATH}")
    return cache


def narrate(radar_path=None, out_path=None):
    radar_path = radar_path or os.path.join(config.OUTPUT_DIR, "radar.json")
    out_path = out_path or os.path.join(config.OUTPUT_DIR, "narrative.json")
    with open(radar_path, encoding="utf-8") as f:
        radar = json.load(f)
    src = _source(radar)
    if not src:
        print("[narrate] 신호 0개 — 서술 생략")
        return None
    pool = LLMPool(config.NARRATE_CHAIN, label="people-narrate")
    try:
        got = pool.generate_json(PROMPT + json.dumps(src, ensure_ascii=False, indent=1), temperature=0.2,
                                 validate=lambda v: _validate(v, src))
    except RuntimeError as e:
        print(f"[narrate] 실패 — 카드는 원문 제목으로: {str(e)[:160]}")
        return None
    rest = [x for x in src if x["id"] not in got]
    if rest:   # 검사에 떨어진 카드만 한 번 더 — 영어 원문 카드가 남지 않게
        try:
            got.update(pool.generate_json(PROMPT + json.dumps(rest, ensure_ascii=False, indent=1), temperature=0.2,
                                          validate=lambda v: _validate(v, rest, min_ratio=0.01)))
        except RuntimeError as e:
            print(f"[narrate] 다시 쓰기 실패 {len(rest)}건 — 원문 제목으로: {str(e)[:120]}")
    out = {"model": pool.last_model, "cards": got}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    translate_subtopics(radar, pool)
    print(f"[narrate] 카드 {len(got)}/{len(src)} · {pool.last_model} → {out_path} · {usage_line()}")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    narrate()
