"""기사 요약 다섯 줄 (news_summary) — 기사를 누르면 뜨는 팝업의 글 (2026-11-05 사용자 batch 8 ⑤: "요약글을 한 5줄 정도는", 8줄은 원문 대체 위험으로 5문장까지).

규칙 (저작권법 기준, doc/운영 지침과 같은 선) :
- 사실만 — 숫자 · 누가 · 무엇을 · 언제. 기자의 분석 · 전망 · 평가 말 · 인용 문장은 옮기지 않는다. 원문 문장 순서를 따라가지 않는다.
- 재료 = 제목 + 첫 문단(article_lead, 저장 · 공개 안 함) 또는 RSS 요약. 재료가 짧으면 줄 수를 줄인다 — 억지로 채우지 않는다.
- 한 줄 = 명사형 헤드라인체(news_store.detail_style_bad 로 걸러낸다). 숫자는 재료에 있는 것만(news_store._num_problem).
- 매체 이름 · 원문 링크는 팝업이 붙인다(출처 표시, 저작권법 제37조).
캐시 : cache_path JSON {item_id: {"lines", "model", "at", "n_src"}} — 같은 기사를 다시 요약하지 않는다. KEEP_DAYS 지나면 지운다.
사슬 = news (Groq qwen → gpt-oss → DeepSeek → Gemini lite). 한 호출 BATCH 건. 실패한 기사는 요약 줄(detail) 하나로 보인다 — 리포트는 나간다.
"""

import datetime
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import article_lead  # noqa: E402
import news_store  # noqa: E402

BATCH = 4          # Qwen 분당 출력 1,000토큰 — 기사당 다섯 줄 ≈ 200토큰
MAX_LINES = 5
MAX_LINE_CHARS = 70
SRC_MAX = 900
KEEP_DAYS = 7
PROMPT = """You write Korean fact summaries of English finance news for Korean readers. Output JSON only.

For each item you get "title" and "text" (the article's opening paragraphs or RSS summary). Write up to 5 lines in Korean.
Rules:
- One line = one fact: numbers, who, what, when. Noun-ending headline style (명사형): end with a noun or number such as 발표 · 인상 · 기록 · 예정 · 감소 · 탈환. Never end with -다 · -요 · -습니다. No period at the end.
- Only facts that are IN the text. Only numbers that appear in the title or text. No analysis, no outlook, no evaluation words, no quotes from the reporter or interviewees, no advice.
- Do not follow the text's sentence order; do not translate sentences — restate facts. Do not repeat the title.
- If the text is short, write fewer lines (1~3). Never pad. Each line max 70 Korean characters. Company names in Korean (엔비디아, 테슬라). Amounts: $1.3 billion = 13억 달러, 2.04%. Never use "—".
Return: {"items": [{"id": "<item id>", "lines": ["...", "..."]}]}
"""


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(path, cache):
    cut = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=KEEP_DAYS)).isoformat()
    cache = {k: v for k, v in cache.items() if v.get("at", "") >= cut}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)


def _check(lines, src):
    """줄 검사 — 문장체 · 영어 · 재료에 없는 숫자 · 너무 긴 줄은 뺀다. 남은 줄만."""
    out = []
    for ln in lines or []:
        ln = str(ln or "").replace("—", ", ").strip().rstrip(".")
        if not ln or len(ln) > MAX_LINE_CHARS or news_store.detail_style_bad(ln) or news_store._num_problem(ln, src):
            continue
        if ln not in out:
            out.append(ln)
    return out[:MAX_LINES]


def summarize(items, cache_path, lead_cache=None, label="summary", max_items=None):
    """items = [{"item_id", "title", "url", "snippet"(RSS 요약, 없을 수 있음)}] → {item_id: [줄]}. 캐시에 있으면 그대로.
    lead_cache = 첫 문단 캐시 파일(깃 밖). None 이면 기사를 열지 않고 snippet 만 쓴다."""
    cache = _load(cache_path) if cache_path else {}
    out = {x["item_id"]: cache[x["item_id"]]["lines"] for x in items if x.get("item_id") in cache}
    need = [x for x in items if x.get("item_id") and x["item_id"] not in cache and x.get("title")]
    if max_items:
        need = need[:max_items]
    if not need:
        return out
    news_store._env()
    from llm_chain import LLMPool, usage_line
    try:
        pool = LLMPool("news", label=label)
    except RuntimeError as e:
        print(f"[summary] {e} — 요약 없이")
        return out
    leads = {}
    if lead_cache:
        try:
            leads = article_lead.leads([x["url"] for x in need if x.get("url")], lead_cache)
        except Exception as e:  # noqa: BLE001
            print(f"[summary] 첫 문단 실패 — RSS 요약만 : {str(e)[:80]}")
    ok = 0
    for i in range(0, len(need), BATCH):
        part = need[i:i + BATCH]
        src = {x["item_id"]: (leads.get(x.get("url")) or x.get("snippet") or "")[:SRC_MAX] for x in part}
        payload = {"items": [{"id": x["item_id"], "title": x["title"], "text": src[x["item_id"]]} for x in part]}
        want = {x["item_id"] for x in part}

        def valid(r):
            rows = (r or {}).get("items") if isinstance(r, dict) else None
            if not isinstance(rows, list) or {str(x.get("id")) for x in rows if isinstance(x, dict)} != want:
                return "항목 불일치"
            return None

        try:
            res = pool.generate_json(PROMPT + json.dumps(payload, ensure_ascii=False), temperature=0.0, validate=valid)
        except RuntimeError as e:
            print(f"[summary] 요약 실패 — 남은 {len(need) - i}건은 다음 실행에서 : {str(e)[:120]}")
            break
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for row in res["items"]:
            x = next(y for y in part if y["item_id"] == row["id"])
            lines = _check(row.get("lines"), x["title"] + " " + src[x["item_id"]])
            cache[x["item_id"]] = {"lines": lines, "model": pool.last_model, "at": now, "n_src": len(src[x["item_id"]])}
            out[x["item_id"]] = lines
            ok += bool(lines)
        if cache_path:
            _save(cache_path, cache)
        print(f"[summary] {min(i + BATCH, len(need))}/{len(need)} ({pool.last_model})", flush=True)
    print(f"[summary] 요약 {ok}/{len(need)} · {usage_line()}")
    return out
