"""media.json → output/narrative.json — 머리 한 줄 + 이슈 묶음마다 한 문장 (한 호출).

숫자 · 순서 · 영상 수는 파이썬이 만든다. 여기서는 묶음의 소주제 · 방송 주장(note) · 방향을 **우리 말 한 문장**으로 줄이는 일만.
검사: 한 문장 · 140자 이내 · 예측 · 권유 말 금지(BANNED) · 숫자는 입력에 있는 것만(fact_check). 전부 실패하면 렌더가 파이썬 문장으로 대신한다.
사슬: config.NARRATE_CHAIN (예비 공급자 먼저 — 운영지침 3-2).
"""

import json
import os
import re
import sys

import config

sys.path.insert(0, os.path.join(config.BASE_DIR, ".."))
import fact_check  # noqa: E402
from llm_chain import LLMPool, usage_line  # noqa: E402

DETAIL_MAX = 140
LEAD_MAX = 80
BANNED = re.compile(r"(전망됩니다|예상됩니다|것으로 보입니다|오를 것|내릴 것|매수 추천|매수 권유|매도 추천|매도 권유|투자 기회|주목해야|사야|팔아야|추천합니다)")
PROMPT = """너는 시장 리서치 블로그의 편집자다. 아래 JSON 은 어젯밤 ~ 오늘 아침 미국 경제 방송(CNBC · 블룸버그 · 폭스 · WSJ · 한국 유튜브 채널)이 다룬 이슈 묶음이다.
묶음마다 한국어 한 문장을 써서 JSON 객체 하나로만 답하라 (설명 · 마크다운 금지):

{"lead": "...", "items": [{"id": "<묶음 id 그대로>", "detail": "..."}]}

lead: 가장 위 묶음(방송이 가장 많이 다룬 이슈)을 80자 이내 한 문장으로 — "방송 m곳이 ○○를 다뤘고, 시각은 (일치/엇갈림)" 꼴. 합니다체.
detail: 묶음마다 한 문장, 합니다체, 140자 이내. **무슨 일이 있었고 방송들이 그것을 어떻게 봤는지**(긍정 · 부정 · 엇갈림)만.
        입력의 topic · notes · stances 에 있는 사실만 쓴다. 입력에 없는 숫자 · 종목 · 인물을 만들지 말 것.
        시장 전망 · 투자 판단 · "~할 것" 예측 · 매수 · 매도 권유를 쓰지 말 것. 방송의 주장은 "방송은 ~로 봤습니다" 처럼 방송의 것으로 둔다.
        "~고 말했습니다" · "~고 보도했습니다" 같은 인용 꼬리를 반복하지 말 것.
종목은 회사 이름을 한국어로 쓰고 티커는 괄호 (예: 엔비디아(NVDA)). 사람 이름은 한국어 표기.

INPUT:
"""


def _inputs(media):
    items = []
    for i, c in enumerate(media["clusters"]):
        items.append({"id": f"c{i}", "category_ko": c["category_ko"], "topic": c["topic"], "topics": c["topics"], "n_videos": c["n_videos"], "n_channels": c["n_channels"],
                      "channels": c["channels"], "stances": c["stances"], "surprise": c["surprise"], "tickers": c["tickers"], "speakers": c["speakers"], "notes": c["notes"]})
    return items


def _ok(text, limit, source):
    t = str(text or "").strip()
    if not t or len(t) > limit or BANNED.search(t):
        return None
    if len(fact_check.split_sentences(t)) > 1:
        return None
    if fact_check.check([t], source) is not True and fact_check.drop_bad(t, source) != t:
        return None
    return t


def narrate(media_path=None, out_path=None):
    media_path = media_path or os.path.join(config.OUTPUT_DIR, "media.json")
    with open(media_path, encoding="utf-8") as f:
        media = json.load(f)
    inputs = _inputs(media)
    if not inputs:
        print("[narrate] 이슈 묶음 없음 — 서술 생략")
        return None
    pool = LLMPool(chain=config.NARRATE_CHAIN, label="media-daily")
    ids = {x["id"] for x in inputs}

    def validate(obj):
        # llm_chain.generate_json: 예외 = 탈락, 반환값이 None 이 아니면 그것으로 바꿔 쓴다 — 그래서 True 를 돌려주면 안 된다 (2026-10-22 CI 에서 'bool' 오류)
        ok = isinstance(obj, dict) and isinstance(obj.get("items"), list) and any(isinstance(i, dict) and i.get("id") in ids for i in obj["items"])
        if not ok:
            raise ValueError("items 가 없거나 id 가 맞지 않음")
        return None

    try:
        res = pool.generate_json(PROMPT + json.dumps(inputs, ensure_ascii=False), temperature=0.2, validate=validate)
    except Exception as e:  # noqa: BLE001
        print(f"[narrate] 전부 실패 — 파이썬 문장으로 대신: {str(e)[:100]}")
        return None
    out = {"model": getattr(pool, "last_model", None), "lead": _ok(res.get("lead"), LEAD_MAX, inputs), "items": {}}
    for it in res.get("items") or []:
        if isinstance(it, dict) and it.get("id") in ids:
            d = _ok(it.get("detail"), DETAIL_MAX, inputs)
            if d:
                out["items"][it["id"]] = d
    out_path = out_path or os.path.join(config.OUTPUT_DIR, "narrative.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"[narrate] {len(out['items'])}/{len(inputs)} 문장 · 머리 {'있음' if out['lead'] else '없음'} · {out['model']} → {out_path}")
    print(usage_line())
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(config.BASE_DIR, "..", "..", ".env"))
    narrate()
