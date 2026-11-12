"""기사 요약 다섯 줄 (news_summary) — 기사를 누르면 뜨는 팝업의 글 (2026-11-05 사용자 batch 8 ⑤: "요약글을 한 5줄 정도는", 8줄은 원문 대체 위험으로 5문장까지).

규칙 (저작권법 기준, doc/운영 지침과 같은 선) :
- 사실만 — 숫자 · 누가 · 무엇을 · 언제. 기자의 분석 · 전망 · 평가 말 · 인용 문장은 옮기지 않는다. 원문 문장 순서를 따라가지 않는다.
- 재료 = 제목 + 첫 문단(article_lead, 저장 · 공개 안 함) 또는 RSS 요약. 재료가 짧으면 줄 수를 줄인다 — 억지로 채우지 않는다.
- 한 줄 = 명사형 헤드라인체(news_store.detail_style_bad 로 걸러낸다). 숫자는 재료에 있는 것만(news_store._num_problem).
- 매체 이름 · 원문 링크는 팝업이 붙인다(출처 표시, 저작권법 제37조).
줄 태그 (2026-11-11 사용자 — 한 기사 안의 시장 · 업종 · 종목 · 규제 이야기를 사실 줄 단위로 나눈다, 증시 전망 근거 · 더보기 팝업 재료):
  tags[i] = {"scope": market|sector|stock, "tickers": [우리 종목만], "sector": 업종 ETF | None, "issue": 이슈 코드, "dir": positive|negative|uncertain|neutral,
             "stage": done|talk} 또는 None(태그 탈락 — 줄은 살린다). 논의 중이어도 방향은 붙인다(`불확실`은 좋고 나쁨 자체가 갈릴 때만).
  업종은 모델이 고른 ETF 가 목록 밖이면 줄의 종목 → universe.sector_etf 로. 화면에는 독자 말로만 (내부 부호 금지).
캐시 : cache_path JSON {item_id: {"lines", "tags", "model", "at", "n_src"}} — 같은 기사를 다시 요약하지 않는다. KEEP_DAYS 지나면 지운다.
사슬 = news (Groq qwen → gpt-oss → DeepSeek → Gemini lite). 한 호출 BATCH 건. 실패한 기사는 요약 줄(detail) 하나로 보인다 — 리포트는 나간다.
"""

import datetime
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import article_lead  # noqa: E402
import hedge_check  # noqa: E402  — 원문의 `대략 · 예상` 이 빠진 줄 바로잡기 (2026-11-12 사용자)
import news_store  # noqa: E402

BATCH = 3          # Qwen 분당 출력 1,000토큰 — 기사당 다섯 줄 + 줄 태그 ≈ 290토큰 (11-11 태그 추가로 4 → 3, 4건이면 약 1,160 으로 넘친다)
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
Then tag each line (labeling only — no prediction, no judgment of importance):
- "o" = what the line is about: "m" (US market as a whole: rates, inflation, jobs, the index), "s:<ETF>" (one sector, ETF from SECTORS), or the US ticker(s) of the company that is the SUBJECT of the line joined by "," (e.g. "NVDA" or "NVDA,AMD").
  Never put a company's ticker on a line about its competitor, customer or peer ("BYD sales rise" is not "TSLA") — use that company's sector "s:<ETF>" instead. A line about a non-US or unlisted company also gets its sector.
- "i" = ONE topic code from ISSUES.
- "d" = sign for that subject, as the line states it: "+" good, "-" bad, "?" good or bad itself is unclear / mixed, "0" plain fact with no sign.
  A stock price or market value move by itself (rose 16%, record high, lost $477 billion of value) is "0" with "i" "MARKET_STRUCTURE" — it is the result, not news about the business. Index or sector sell-offs tied to a stated cause take the cause's topic and sign.
  The sign of a plan or a talk is the sign the thing would have if it happened: "considering wider chip export curbs" = "-", "officials discuss a rate cut" = "+" for "m",
  "weighs a special dividend" = "+" (same as a dividend raise), "considers selling $95B of new shares" = "-" (dilution, same as a share sale). Never use "0" or "?" just because it is not final —
  "0" only if the thing would have no sign even when done (a scheduled date, a name change); "?" only if even when done it could go either way (merger talks with no terms).
- "k" = "d" if it happened / was decided, announced, released or filed; "t" if it is considered, discussed, proposed, negotiated, reportedly planned or rumored.
SECTORS: SMH semiconductors, XLK tech (software, hardware, IT services), XLC communication (internet, media, telecom), XLY consumer discretionary (cars and EVs, retail, travel), XLP consumer staples, XLF financials, XLV health care, XLE energy, XLI industrials, XLB materials, XLRE real estate, XLU utilities.
ISSUES: __ISSUES__
Return: {"items": [{"id": "<item id>", "lines": [{"t": "<Korean line>", "o": "NVDA", "i": "EARNINGS", "d": "+", "k": "d"}]}]}
"""
SECTORS = ("SMH", "XLK", "XLC", "XLY", "XLP", "XLF", "XLV", "XLE", "XLI", "XLB", "XLRE", "XLU")
_D = {"+": "positive", "-": "negative", "?": "uncertain", "0": "neutral"}
_K = {"d": "done", "t": "talk"}


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


def _tag(r):
    """줄 태그 부호 → {"scope", "tickers", "sector", "issue", "dir", "stage"}. 어휘 밖 값이 하나라도 있으면 None (줄은 살린다)."""
    if not isinstance(r, dict):
        return None
    o, i, d, k = (str(r.get(q) or "").strip() for q in ("o", "i", "d", "k"))
    if i not in news_store.issue_codes.ISSUES or d not in _D or k not in _K:
        return None
    tickers, sector = [], None
    if o.upper() in SECTORS:
        o = "s:" + o   # 접두 없이 ETF 만 준 경우
    if o.lower() == "m":
        scope = "market"
    elif o.lower().startswith("s:"):
        scope, sector = "sector", o[2:].strip().upper()
        if sector not in SECTORS:
            return None
    else:
        tickers = [t for t in (q.strip().upper() for q in o.split(",")) if t in news_store.U.BY_SYM]
        if not tickers:
            return None   # 우리 종목 밖 회사 — 대상 없이 줄만
        scope = "stock"
        etfs = {news_store.U.sector_etf(t)[0] for t in tickers}
        sector = etfs.pop() if len(etfs) == 1 else None
    return {"scope": scope, "tickers": tickers, "sector": sector, "issue": i, "dir": _D[d], "stage": _K[k]}


PRICE_LINE = re.compile(r"(주가|시가총액|시총|종가|지수|선물|주식시장|증시|나스닥|S&P|다우)[^,]*(\d[\d.,]*\s*(%|포인트|달러)|급등|급락|상승|하락|최고|최저|감소|증가|반등|탈환|붕괴|매도세|매수세|랠리|기록)")
ACTION_LINE = re.compile(r"(계약|수주|인수|승인|규제|소송|출시|가이던스|매출|순이익|배당|자사주|리콜|조사|관세|금리|물가|인플레이션|고용|실업|우려)")   # 원인이 같이 적힌 줄은 근거로 남긴다


PCT_MOVE = re.compile(r"\d[\d.,]*\s*%\s*(하락|상승|급락|급등|반등|떨어|올라)")   # `ASML, 5% 하락` 처럼 주가 낱말 없이 등락만


def _price_only(ln):
    """주가 · 시가총액 움직임만 적은 줄 — 결과일 뿐 근거가 아니다 (11-11 시험: 모델이 `16% 급등` 에 + 를 붙였다). 행동 낱말이 같이 있으면 아니다."""
    return bool(PRICE_LINE.search(ln) or PCT_MOVE.search(ln)) and not ACTION_LINE.search(ln)


HEDGED = []   # 이번 실행에서 말투를 바로잡은 줄 — summarize 가 세어 출력 · 캐시에 남긴다


def _check(lines, src):
    """줄 검사 — 문장체 · 영어 · 재료에 없는 숫자 · 너무 긴 줄은 뺀다. → (남은 줄, 줄 태그). 줄은 옛 형식(문자열)도 받는다."""
    out, tags = [], []
    for r in lines or []:
        ln = r.get("t") if isinstance(r, dict) else r
        ln = str(ln or "").replace("—", ", ").strip().rstrip(".")
        if not ln or len(ln) > MAX_LINE_CHARS or news_store.detail_style_bad(ln) or news_store._num_problem(ln, src):
            continue
        ln, hw = hedge_check.hedge(ln, src)   # 원문이 어림 · 예상으로 말한 숫자 = `약` · `(예상)` (2026-11-12 사용자: 추정이 사실처럼 읽히던 것)
        if hw:
            HEDGED.append((ln, hw))
        if ln not in out:
            out.append(ln)
            t = _tag(r)
            if t and _price_only(ln):
                t.update(dir="neutral", issue="MARKET_STRUCTURE", price=True)   # 근거 집계에서 뺀다 (줄은 팝업에 그대로)
            tags.append(t)
    return out[:MAX_LINES], tags[:MAX_LINES]


def summarize(items, cache_path, lead_cache=None, label="summary", max_items=None):
    """items = [{"item_id", "title", "url", "snippet"(RSS 요약, 없을 수 있음)}] → {item_id: [줄]}. 캐시에 있으면 그대로.
    lead_cache = 첫 문단 캐시 파일(깃 밖). None 이면 기사를 열지 않고 snippet 만 쓴다."""
    cache = _load(cache_path) if cache_path else {}
    # 요약이 두 줄 못 된 기사(팝업 없이 원문 링크로 나감)는 한 번만 다시 — 재료가 RSS 요약뿐이었던 것을 첫 문단으로 (2026-11-10 사용자: 뉴스를 눌렀는데 원문으로 나감)
    redo = {k for k, v in cache.items() if len(v.get("lines") or []) < 2 and not v.get("retry")} if lead_cache else set()
    out = {x["item_id"]: cache[x["item_id"]]["lines"] for x in items if x.get("item_id") in cache}
    need = [x for x in items if x.get("item_id") and (x["item_id"] not in cache or x["item_id"] in redo) and x.get("title")]
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
            # 탈락은 예외로 — llm_chain.generate_json 은 validate 가 돌려준 값을 답으로 바꿔 쓴다. 문자열을 돌려주던 때(11-11 22:47 UTC)
            # 그 문자열이 답이 되어 res["items"] 에서 'string indices must be integers' 로 요약 전체가 멈췄다 (2026-11-12)
            if not isinstance(rows, list) or not all(isinstance(x, dict) for x in rows) or {str(x.get("id")) for x in rows} != want:
                raise ValueError("항목 불일치")
            if any(not isinstance(x.get("lines"), list) or not all(isinstance(q, (str, dict)) for q in x["lines"]) for x in rows):
                raise ValueError("줄 형식 불일치")   # 11-11 시험: 줄 태그를 붙인 뒤 모양이 어긋난 답이 한 번 있었다 → 다음 모델로
            return None

        try:
            res = pool.generate_json(PROMPT.replace("__ISSUES__", ", ".join(news_store.issue_codes.ISSUES)) + json.dumps(payload, ensure_ascii=False), temperature=0.0, validate=valid)
        except RuntimeError as e:
            print(f"[summary] 요약 실패 — 남은 {len(need) - i}건은 다음 실행에서 : {str(e)[:120]}")
            break
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for row in res["items"]:
            x = next(y for y in part if y["item_id"] == str(row["id"]))
            lines, tags = _check(row.get("lines"), x["title"] + " " + src[x["item_id"]])
            cache[x["item_id"]] = {"lines": lines, "tags": tags, "model": pool.last_model, "at": now, "n_src": len(src[x["item_id"]]), **({"retry": True} if x["item_id"] in redo else {})}
            out[x["item_id"]] = lines
            ok += bool(lines)
        if cache_path:
            _save(cache_path, cache)
        print(f"[summary] {min(i + BATCH, len(need))}/{len(need)} ({pool.last_model})", flush=True)
    print(f"[summary] 요약 {ok}/{len(need)} · {usage_line()}" + (f" · 말투 바로잡음 {len(HEDGED)}줄" if HEDGED else ""))
    for ln, hw in HEDGED[:5]:
        print(f"[summary]   {'·'.join(hw)} : {ln}")
    return out
