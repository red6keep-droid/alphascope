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
DETAIL_MAX = 100
PATH_MAX = 70
RESTATE = 0.6   # 요약의 낱말 가운데 헤드라인 낱말이 이 비율 이상이면 되풀이로 보고 비운다


def _overlap(h, d):
    """헤드라인 · 요약의 2글자 조각 겹침 비율 (요약 기준). 조사 · 끝말에 덜 흔들리게 낱말이 아니라 조각."""
    g = lambda t: {t[i:i + 2] for i in range(len(t) - 1)} if t else set()
    hs, ds = g(re.sub(r"[^가-힣A-Za-z0-9]", "", h)), g(re.sub(r"[^가-힣A-Za-z0-9]", "", re.sub(r"(했습니다|입니다|습니다|밝혔|말했|강조했)", "", d)))
    return len(hs & ds) / len(ds) if ds else 0
PATH_TEMPLATE = re.compile(r"(직접 연결되는|닿는 자리입니다|먼저 닿는)")   # 예문 틀을 베낀 문장은 버린다 (10-25 첫 실행에서 전부 같은 틀)
NARRATE_BATCH = 16   # 한 호출 신호 수 — 52개를 한 번에 보내면 Groq 가 413 (10-25)
BANNED = re.compile(r"(전망됩니다|예상됩니다|것으로 보입니다|오를 것|내릴 것|매수 추천|매수 권유|매도 추천|투자 기회|주목해야)")   # 매매 공시의 "매수"는 사실이라 막지 않는다
PROMPT = """너는 시장 리서치 블로그의 편집자다. 아래 JSON 은 미국 정책 결정자 · 투자자 · CEO 의 최근 발언 신호 목록이다.
신호마다 한국어로 두 가지를 써서 JSON 객체 하나로만 답하라 (설명 · 마크다운 금지):

{"items": [{"id": "<신호 id 그대로>", "headline": "...", "detail": "...", "path": "..."}]}

headline: 48자 이내 명사형 헤드라인. "인물, 무엇" 형태. 끝은 명사 (예: "베센트, 이란 전쟁 뒤 물가 하락 전망" · "캐시 우드, 아처 에비에이션 1,210만 달러 매수").
          "~했다" · "~이다" 같은 서술형 끝말과 마침표 금지.
detail: 주요 뉴스 문체 한 줄 — 명사 · 명사구로 끝내고 마침표 없음 ("~했습니다" · "~입니다" · "~했다" 금지), 90자 이내.
        **헤드라인에 없는 사실**만 — "body"(본문 · 기사 첫 문단)에서 배경 · 이유 · 조건 · 시점 · 함께 나온 숫자 · 관련 회사.
        헤드라인을 말만 바꿔 되풀이하지 말 것 (헤드라인 "오스틴 사이버캡 플릿 10배 성장" 에 "오스틴 사이버캡 차량 10배 증가" 는 금지).
        예: "출시 약 한 달 만의 증가, 연말까지 일반 승객용 로보택시 운행 목표"
            "중동 국부펀드 · 로렌 파월 잡스 등과 같은 시기 투자, 비용 절감 · 주가 부양용 자금"
            "2년 연속 판매 감소 속 제시된 연간 인도량 목표"
        body 에 헤드라인 밖의 사실이 없으면 detail 은 빈 문자열 "".
        인물 이름 · 직함 · 인용 꼬리("~고 말해" · "보도") 금지. 원문에 있는 사실 · 숫자만. 시장 영향 · 앞날 · 투자 판단 금지.
        "attribution" 이 "office" 면 기관 발표다 ("백악관 발표, ~").
path: 입력에 "channel"(경로 이름) 과 "assets"(닿는 자산) 가 있는 신호만. 주요 뉴스 문체 한 구절 — 명사 · 명사구로 끝내고 마침표 없음, 60자 이내.
      화면은 "<자산 이름> : <path>" 로 보인다 — **자산 이름을 path 안에 쓰지 말 것**. 발언 내용이 그 자산에 미치는 작용(수요 · 공급 · 원가 · 금리 기대 · 규제 · 관심)만.
      방향은 "~ 압력" · "~ 기대 자극" · "~ 재료" 까지, "오를 것 · 내릴 것 · 전망 · 예상" 같은 예측 · 단정 금지. 숫자 금지.
      반드시 "무엇이(발언의 구체 내용) → 어떤 기대 · 압력" 두 부분을 다 쓴다. "투자 압력" · "판매 압력" 처럼 내용 없는 두세 단어는 금지.
      예: "정제 · 물류 용량 확대로 공급 쪽 내림 압력" · "장기 인도량 목표 상향, 생산 규모 · 점유율 기대 자극" · "네오클라우드 수요 지속, GPU 주문 기대"
          "아처 · 조비 매수 공시로 당일 관심 집중" · "사이버캡 운행 대수 급증, 로보택시 매출 기대 자극" · "엔터테인먼트 지분 투자, 본업과 거리 있는 자금 이동"
      "channel" 이 없는 신호는 path 를 비운다("").
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
    import article
    import paths
    sec = [s["lead"]["url"] for p in radar["people"] for s in p["signals"] if s["source_kind"] != "primary" and not s["lead"]["body"]]
    got = article.leads(sec) if sec else {}   # 보도 발언 — 기사 설명 + 첫 문단 (2026-10-25 사용자: 요약이 제목을 되풀이한다)
    out = []
    for p in radar["people"]:
        for s in p["signals"]:
            ld = s["lead"]
            row = {"id": ld["id"], "speaker": f'{p["name_ko"]} ({p["title_ko"]})', "attribution": s["attribution"],
                   "topic": s["topic"], "subtopic": s["subtopic"],
                   "text": _units(ld["quote"] or ld["title"]), "body": _units((ld["body"] or got.get(ld["url"], ""))[:900]),
                   "also_reported": [_units(o["title"]) for o in s["others"]][:3]}
            if s.get("path"):   # 경로표가 정한 자산만 (기획 9-2)
                row["channel"] = paths.CHANNEL_KO[s["path"]["channel"]]
                row["assets"] = [paths.asset_label(a) for a in s["path"]["assets"]]
            out.append(row)
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
        d = d.rstrip(".").strip()
        if d and (len(d) > DETAIL_MAX or re.search(r"(습니다|니다|했다|이다|한다|됐다)$", d)):
            why.append("설명 형식(뉴스 문체)")
        if d and _overlap(h, d) >= RESTATE:
            d = ""   # 헤드라인 되풀이 — 줄을 비운다 (2026-10-25 사용자)
        pth = str(it.get("path") or "").strip().rstrip(".").strip()
        pth = re.sub(r"^[^:：]{1,40}\)\s*[:：]\s*", "", pth)   # "테슬라(TSLA) : …" — 자산 이름은 화면이 붙인다
        if pth and len(re.sub(r"\s", "", pth)) < 10:
            pth = ""   # 내용 없는 두세 단어 ("투자 압력")
        if pth and (len(pth) > PATH_MAX or re.search(r"(습니다|니다|했다|이다|한다|닿는다)$", pth) or re.search(r"\d", pth) or PATH_TEMPLATE.search(pth)):
            pth = ""   # 경로 문장은 선택 — 형식이 틀리거나 틀 문장이면 그 줄만 비운다 (카드는 경로 이름 · 뜻 한 줄로 선다)
        if BANNED.search(h + " " + d + " " + pth):
            why.append("예측 · 권유 말")
        probs = fact_check.check([h, d], by_id[it["id"]])
        if probs:
            why.append(f"숫자 {probs[0]}")
        if why:
            bad.append((it["id"], why))
            continue
        out[it["id"]] = {"headline": h, "detail": d, "path": pth}
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
    pool = LLMPool(config.NARRATE_CHAIN, label="people-narrate", skip_when_day_out=config.SKIP_WHEN_DAY_OUT)
    got = {}
    for i in range(0, len(src), NARRATE_BATCH):
        chunk = src[i:i + NARRATE_BATCH]
        try:
            got.update(pool.generate_json(PROMPT + json.dumps(chunk, ensure_ascii=False, indent=1), temperature=0.2,
                                          validate=lambda v, c=chunk: _validate(v, c)))
        except RuntimeError as e:
            print(f"[narrate] 묶음 {i // NARRATE_BATCH + 1} 실패: {str(e)[:160]}")
    if not got:
        print("[narrate] 실패 — 카드는 원문 제목으로")
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
