"""공용 뉴스 처리 (news_store) — 기사 한 건을 **한 번만** AI 로 처리해 여러 리포트가 같은 결과를 쓴다 (doc/기획/뉴스-형식-통일.md 3절 · 4절 6단계, 2026-10-25 사용자: "공용 처리부터").

1단계(10-25): 종목 페이지(stock-radar/collect_news.py)의 분류를 여기로 옮겼다 — 지금 가장 완성된 처리라 공용의 바탕으로 쓴다.
다음: 홈 주요 뉴스(fetch_news.py, CNBC) · 미국 데일리 뉴스가 같은 함수로 처리하고 결과를 나눠 쓴다. 엔비디아 리포트는 따로 둔다(발언자 · 신규성 · 법무 같은 전용 판단).
기사와 방송 사이 중복 · 표현이 다른 같은 사건은 거르지 않는다 (10-25 사용자: 다른 글처럼 느껴지면 그대로).

- 분류 : 기사마다 **한 번만**, 한 호출 BATCH 건. 제목 번역(title_ko — 목록 헤드라인) · 사실 문장(fact — 종목 페이지 중요 이슈) · 요약 줄(detail) ·
  종목별 관련도 · 방향(scores) · 영역(area) · 이슈 코드 · 범위 · 영어 문장(fact_en). 테마 · 관련 종목은 이 칸에서 파이썬이 정한다(theme · related).
- 헤드라인 = 원제를 옮긴 번역 (2026-10-25 사용자: "왜 제목 그대로 표현 안 하고 가공하나") — 사실 문장은 요약 줄이 비었을 때의 요약 · 중요 이슈용.
- 재료 : 제목 + 최근 LEAD_HOURS 기사의 첫 문단(article_lead — AI 입력으로만, 저장 · 공개 안 함) 또는 RSS 요약(snippet).
- 사슬 : `news` · `news-alt` 를 배치마다 번갈아 — Groq(qwen · gpt-oss) 먼저, DeepSeek, 맨 뒤 Gemini lite (2026-10-25 사용자: Gemini 는 다른 곳에 아낀다).
  Groq 가 정식 — 예비 답을 다음 실행에서 Gemini 로 다시 받는 규칙 · 관련도 3 flash 재확인은 없앴다.
- 보정 : NVDA 리포트 labels 의 의견 매체 · 의견형 제목 규칙으로 관련도를 1 이하로 깎는다(올리지 않는다).
- 검사 : 헤드라인 · 요약의 숫자는 원문(제목 + 첫 문단)에 있는 것만, 인과 · 평가 말 금지, 요약은 영어 · 문장체면 그 줄만 뺀다. 두 번 탈락하면 헤드라인 없이(목록에서 빠짐).
- AI 가 전부 막힌 날 : 분류 없이 둔다 → 화면은 `판단 유보`.
store = {item_id: 기사} — 저장 위치 · 보관 기간은 부르는 쪽(수집기)이 정한다.
"""

import datetime
import importlib.util
import json
import os
import re
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import article_lead  # noqa: E402  — 기사 첫 문단 (공용) — 요약 줄(detail) 재료
import issue_codes  # noqa: E402  — 이슈 코드 어휘 (공용, doc/기획/이슈-분류-코드표.md)

_spec = importlib.util.spec_from_file_location("radar_universe_ns", os.path.join(BASE, "stock-radar", "universe.py"))   # 종목 후보 (scores 의 티커 범위)
U = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(U)

PROMPT = os.path.join(BASE, "prompts", "news_classify.txt")
LEAD_HOURS = 36   # 첫 문단은 이 시간 안의 기사만 받는다 — 목록은 오늘자만 보인다 (2026-10-25 사용자)
SNIPPET = 500     # 모델에 넣는 첫 문단 길이 — Groq 분당 8,000토큰 안에 한 배치가 들어가게
# 이슈 코드 → 데일리 뉴스 테마 (daily-report THEME_VOCAB) — 테마도 공용 처리에서 (2026-10-25 사용자: 데일리 AI 가 따로 정하지 않는다)
THEME = {"RATES_FED": "금리", "INFLATION": "매크로", "GROWTH_JOBS": "매크로", "TARIFF_TRADE": "정책/규제", "GEOPOLITICS": "지정학", "OIL_ENERGY": "에너지",
         "AI_CAPEX": "AI/반도체", "EARNINGS": "실적", "CORP_EVENT": "실적", "REGULATION": "정책/규제", "FISCAL_POLITICS": "정책/규제",
         "CREDIT_BANKS": "매크로", "MARKET_STRUCTURE": "매크로", "INVESTOR_CALLS": "기타", "FX_GLOBAL": "매크로", "CRYPTO": "기타",
         "REAL_ESTATE": "매크로", "OTHER": "기타"}

BATCH = 10   # 한 호출 기사 수 — Groq 분당 8,000토큰(입력 + 답) 안에 (2026-10-25, 옛 lite 25)
QWEN_BATCH = 4   # Qwen 이 첫 단계인 사슬(news)은 4건 — 답이 기사당 약 210토큰이라 10건이면 Qwen 분당 출력 1,000토큰(OTPM)에 걸려
                 # 그 몫이 전부 gpt-oss 로 넘어가 gpt-oss 하루 토큰 20만이 찼다 (2026-10-26: 10-25 종목 레이더 Qwen 25번 중 11번 429).
                 # 5건(출력 약 1,100)은 두 번째 호출부터 거절, 4건(817 ~ 905)은 62초 간격 3연속 성공 (llm_chain groq-qwen 주석)
MAX_MINUTES = 30   # 한 실행의 분류 시간 예산 — gpt-oss 가 하루 한도로 빠지면 Qwen 4건/분만 남아 느려진다. 남은 기사는 다음 실행 (NVDA 워크플로 제한 60분)
CLASSIFY_HOURS = 24   # 이보다 오래된 새 기사는 AI 에 보내지 않는다 — 목록은 최근 24시간, 중요 이슈도 최신 5줄이라 거의 안 보인다.
                      # 48 → 24 (2026-10-26 사용자): 하루 약 96건 · gpt-oss 약 44K 토큰 절약, 중요 이슈 약 3% 영향 (10-25 데이터)
                      # 10-25 새 기사 406건 중 115건(28%)이 2 ~ 8일 전 기사였다 (구글 뉴스 7일 검색이 매일 새로 섞여 들어옴)
AREAS = ("Earnings", "Flows", "Regulation", "Legal", "Product", "Demand", "Supply", "Corporate", "Macro", "Other")
DIRS = ("positive", "negative", "uncertain", "neutral")
EN = {"NVDA": "Nvidia", "AAPL": "Apple", "GOOGL": "Alphabet Google", "MSFT": "Microsoft", "AMZN": "Amazon", "META": "Meta Platforms",
      "AVGO": "Broadcom", "TSLA": "Tesla", "BRK-B": "Berkshire Hathaway", "LLY": "Eli Lilly", "MU": "Micron", "WMT": "Walmart",
      "JPM": "JPMorgan", "AMD": "AMD", "V": "Visa", "XOM": "Exxon Mobil", "JNJ": "Johnson & Johnson", "MA": "Mastercard",
      "ABBV": "AbbVie", "INTC": "Intel",
      # 2026-10-20 추가 29개 (doc/기획/종목-레이더-기획.md 10-12)
      "TSM": "TSMC", "ASML": "ASML", "LRCX": "Lam Research", "AMAT": "Applied Materials", "ORCL": "Oracle", "ANET": "Arista Networks",
      "VRT": "Vertiv", "EQIX": "Equinix", "CEG": "Constellation Energy", "CRWV": "CoreWeave", "SPCX": "SpaceX", "RKLB": "Rocket Lab",
      "KO": "Coca-Cola", "PG": "Procter & Gamble", "PM": "Philip Morris", "NFLX": "Netflix", "DIS": "Disney", "HD": "Home Depot",
      "MCD": "McDonald's", "CAT": "Caterpillar", "GE": "GE Aerospace", "COST": "Costco", "CVX": "Chevron", "LIN": "Linde",
      "NEM": "Newmont", "WELL": "Welltower", "PLD": "Prologis", "NEE": "NextEra Energy", "SO": "Southern Company",
      # 2026-10-25 추가 8개
      "COP": "ConocoPhillips", "SLB": "SLB Schlumberger", "EOG": "EOG Resources", "COIN": "Coinbase", "MSTR": "Strategy MicroStrategy",
      "HOOD": "Robinhood", "MARA": "Marathon Digital MARA", "CRCL": "Circle Internet",
      "VST": "Vistra", "SMR": "NuScale Power",
      "IONQ": "IonQ", "RGTI": "Rigetti Computing", "QBTS": "D-Wave Quantum", "QUBT": "Quantum Computing Inc", "IBM": "IBM"}


def _env():
    """로컬 실행이면 저장소 .env 에서 LLM 키만 읽는다 (Actions 는 secrets 가 환경 변수로 들어온다). Slack 웹훅은 읽지 않는다 — 로컬 시험이 알림을 보내지 않게."""
    path = os.path.join(BASE, "..", ".env")
    if os.environ.get("GEMINI_API_KEY") or not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        k, _, v = line.strip().partition("=")
        v = re.split(r"\s+#", v, 1)[0].strip().strip('"')   # 줄 끝 주석은 떼고
        if k in ("GEMINI_API_KEY", "NVIDIA_API_KEY", "GROQ_API_KEY") and v:
            os.environ.setdefault(k, v)


def _valid(items):
    ids = {x["item_id"] for x in items}

    def check(v):
        if not isinstance(v, list):
            raise ValueError("배열이 아님")
        for r in v:
            if r.get("item_id") not in ids or r.get("area") not in AREAS or not isinstance(r.get("scores"), list) or not r.get("fact"):
                raise ValueError(f"형식 탈락 {r.get('item_id')}")
            for sc in r["scores"]:
                if sc.get("ticker") not in U.BY_SYM or sc.get("direction") not in DIRS or sc.get("relevance") not in (0, 1, 2, 3):
                    raise ValueError(f"점수 탈락 {r.get('item_id')}")
        return v
    return check


def _cap(x):
    """의견 · 해설 기사는 관련도 1 이하 (NVDA labels.adjust 와 같은 규칙, 깎기만). nvda-report 의 labels · config 를 읽는다 —
    다른 `config` 모듈을 먼저 읽은 프로세스에서는 부르지 말 것 (종목 페이지 · 홈 · 데일리는 없음)."""
    if os.path.join(BASE, "nvda-report") not in sys.path:
        sys.path.insert(0, os.path.join(BASE, "nvda-report"))
    import labels
    import config
    src = (x.get("source") or "").lower()
    price_move = bool(labels.PRICE_MOVE_RE.search(x["title"])) and not labels.ACTION_RE.search(x["title"])   # 주가 움직임만 다룬 기사
    if (any(p in src for p in labels.OPINION_PUBLISHERS) or labels.OPINION_TITLE_RE.search(x["title"]) or config.is_secondary_source(src) or price_move):
        for sc in x["scores"]:
            sc["relevance"] = min(sc["relevance"], labels.MAX_OPINION_RELEVANCE)
        x["opinion"] = True


# ---------------------------------------------------------------- 사실 문장 검사 (파이썬, 2026-10-18 사용자 확정)
# lite 가 "$37 Billion" 을 "37억 달러"로 옮기고 "호재로 작용했다" 같은 인과 · 평가를 쓴 일(10-18)이 있어, 문장을 쓰기 전에 거른다.
# 탈락한 기사는 한 번 더 분류하고, 두 번 탈락하면 사실 문장 없이(원문 제목으로) 둔다. 라벨 · 관련도는 남긴다.

EN_UNIT = {"%": "%", "percent": "%", "trillion": 1e12, "tn": 1e12, "t": 1e12, "billion": 1e9, "bn": 1e9, "b": 1e9,
           "million": 1e6, "mn": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}
KO_UNIT = {"%": "%", "퍼센트": "%", "천억": 1e11, "백억": 1e10, "십억": 1e9, "조": 1e12, "억": 1e8, "천만": 1e7, "백만": 1e6, "십만": 1e5, "만": 1e4, "천": 1e3}
EN_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(%|percent|trillion|billion|million|thousand|tn|bn|mn|[tbmk](?![a-z0-9]))?", re.I)
KO_NUM = re.compile(r"(?<![A-Za-z])(\d[\d,]*(?:\.\d+)?)(?![A-Za-z\d])\s*(%|퍼센트|천억|백억|십억|조|억|천만|백만|십만|만|천)?\s*(월|일|년|분기|위|시|세대|호)?")   # 10b5-1 같은 이름 속 숫자는 건너뛴다
EN_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
            "dozen": 12, "hundred": 100}
BANNED = ("호재", "악재", "수혜", "작용했", "덕분", "때문", "영향으로", "전망이다", "기대된다", "상승세", "하락세", "끌어올", "끌어내")   # 인과 · 평가 · 예측 (프롬프트 규칙을 파이썬으로 한 번 더)
MAX_FACT_FAILS = 2


def _vals(text, rx, units, skip_dates=False):
    """숫자 → [(종류, 값)]. 한국어 `49만 7천` · `1조 2천억` 처럼 큰 단위 뒤에 작은 단위가 띄어쓰기로 이어지면 한 수로 합친다."""
    out, prev = [], None   # prev = (끝 위치, 단위 배수)
    text = text or ""
    for m in rx.finditer(text):
        if skip_dates and m.group(3):
            prev = None
            continue
        v = float(m.group(1).replace(",", ""))
        u = units.get((m.group(2) or "").lower(), 1) if m.group(2) else 1
        if u == "%":
            out.append(("%", v))
            prev = None
            continue
        if prev and out and out[-1][0] == "n" and not text[prev[0]:m.start()].strip() and u < prev[1]:
            out[-1] = ("n", out[-1][1] + v * u)
        else:
            out.append(("n", v * u))
        prev = (m.end(), u)
    return out


def fact_problem(x, field="fact", src_text=None, numbers=True):
    """사실 문장이 원문(제목, 첫 문단을 받은 기사는 제목 + 첫 문단)과 숫자가 맞지 않거나 인과 · 평가 말을 쓰면 그 이유, 괜찮으면 None.
    numbers=False = 말투만 (첫 문단으로 숫자를 확인한 기사를 나중에 다시 볼 때 — 첫 문단은 저장하지 않는다)."""
    f = x.get(field) or ""
    bad = [w for w in BANNED if w in f]
    if bad:
        return "말투 " + bad[0]
    if not numbers:
        return None
    text = src_text if src_text is not None else x["title"]
    src = _vals(text, EN_NUM, EN_UNIT) + [("n", float(v)) for w, v in EN_WORDS.items() if re.search(rf"\b{w}\b", text, re.I)]
    for kind, v in _vals(f, KO_NUM, KO_UNIT, skip_dates=True):
        if not any(k == kind and abs(v - s) <= max(abs(s), 1e-9) * 0.02 for k, s in src):
            return f"숫자 {v:g}"
    return None


def _num_problem(ko, src):
    """한국어 글의 숫자가 원문(영어)에 없으면 그 숫자, 괜찮으면 None (fact_problem 의 숫자 검사만)."""
    have = _vals(src, EN_NUM, EN_UNIT) + [("n", float(v)) for w, v in EN_WORDS.items() if re.search(rf"\b{w}\b", src, re.I)]
    for kind, v in _vals(ko, KO_NUM, KO_UNIT, skip_dates=True):
        if not any(k == kind and abs(v - s) <= max(abs(s), 1e-9) * 0.02 for k, s in have):
            return f"숫자 {v:g}"
    return None


def headline(x):
    """목록 헤드라인 — 원제 번역, 없으면 사실 문장."""
    return x.get("title_ko") or x.get("fact")


def summary(x):
    """요약 줄 — 첫 문단 · RSS 요약에서 뽑은 detail 만. 없으면 빈 줄 — 사실 문장으로 채우면 헤드라인을 다시 말한다(10-25 시험)."""
    return x.get("detail") or ""


def theme(x):
    return THEME.get(x.get("issue") or "OTHER", "기타")


def related(x, min_rel=2):
    """관련도 min_rel 이상인 종목 (높은 순)."""
    return [s["ticker"] for s in sorted(x.get("scores") or [], key=lambda s: -s["relevance"]) if s["relevance"] >= min_rel]


def detail_style_bad(d):
    """요약 줄 모양 검사 — 영어를 그대로 옮겼거나(라틴 글자가 30% 넘음) 문장체(-다 · -습니다)로 끝나면 True (2026-10-25 첫 실행에서 둘 다 나옴)."""
    letters = [c for c in d if c.isalpha()]
    latin = sum(1 for c in letters if c.isascii())
    return (letters and latin / len(letters) > 0.3) or bool(re.search(r"(다|요)\.?$", d.strip()))


def _apply(store, res, model, label, leads=None):
    """분류 결과를 저장 + 보정 + 문장 검사. 탈락은 다시 분류 대상으로 돌린다. 요약 줄(detail)은 검사에 걸리면 그 줄만 뺀다."""
    ok = bad = 0
    for r in res:
        x = store[r["item_id"]]
        x.update(area=r["area"], scores=r["scores"], fact=r["fact"].replace(" — ", ", ").replace("—", ", "), fact_en=r.get("fact_en"), ai_model=model)
        x["title_ko"] = (r.get("title_ko") or "").replace(" — ", ", ").replace("—", ", ").strip().rstrip(".") or None
        if x["title_ko"] and (detail_style_bad(x["title_ko"]) and not re.search(r"[가-힣]", x["title_ko"]) or _num_problem(x["title_ko"], x["title"])):
            x["title_ko"] = None   # 번역이 영어 그대로거나 숫자가 원제와 다르면 — 헤드라인은 사실 문장으로
        lead = (leads or {}).get(x.get("url"), "")
        src = x["title"] + " " + lead   # 숫자 대조 원문 — 첫 문단이 있으면 같이 (AI 가 헤드라인에도 첫 문단 숫자를 쓴다, 2026-10-25)
        x["fact_src"] = "lead" if lead else "title"
        x["detail"] = (r.get("detail") or "").replace(" — ", ", ").replace("—", ", ").strip() or None
        if x["detail"] and (x["detail"] == x["fact"] or detail_style_bad(x["detail"]) or fact_problem(x, "detail", src)):
            x["detail"] = None
        x["market_dir"] = r.get("market_dir") if r.get("market_dir") in DIRS else None   # 시장 전체에 대한 뉴스 방향 — 데일리 뉴스 방향 막대 (2026-10-31 사용자 P143). 빠져도 분류는 살린다
        x.update(issue_codes.coerce(r))   # 이슈 코드 · 세부 주제 · 범위 · 국가 · 예정 · 놀람 (doc/기획/이슈-분류-코드표.md, 2026-10-21) — 어휘 밖이면 OTHER
        _cap(x)
        why = fact_problem(x, "fact", src)
        if why:
            x["fact_fails"] = x.get("fact_fails", 0) + 1
            print(f"[news] {label} 문장 탈락 ({why}) {x['item_id']} : {x['fact'][:60]}")
            x["fact"] = x["fact_en"] = x["detail"] = None
            if x["fact_fails"] < MAX_FACT_FAILS:
                x["ai_model"] = None   # 다음 분류 때 다시
            bad += 1
        else:
            ok += 1
    return ok, bad


def _call(pool, head, companies, part, leads=None):
    items = [{"item_id": x["item_id"], "title": x["title"], "source": x["source"], "published_at": x["published_at"][:10],
              **({"snippet": leads[x["url"]][:SNIPPET]} if (leads or {}).get(x.get("url")) else {})} for x in part]
    return pool.generate_json(head + json.dumps({"companies": companies, "items": items}, ensure_ascii=False), temperature=0.0, validate=_valid(items))


def _leads(items, cache_path):
    """요약 줄 재료 {주소: 글}. 기사에 snippet(RSS 요약 — 홈 CNBC)이 있으면 그것, 없으면 최근 LEAD_HOURS 시간 기사의 첫 문단(cache_path 가 있을 때).
    snippet 은 저장하지 않는다(부르는 쪽이 지운다). 실패해도 분류는 제목만으로 간다."""
    out = {x["url"]: x["snippet"] for x in items if x.get("url") and x.get("snippet")}
    cut = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=LEAD_HOURS)).strftime("%Y-%m-%dT%H:%M")
    urls = [x["url"] for x in items if x.get("url") and x["url"] not in out and x["published_at"][:16] >= cut]
    if not urls or not cache_path:
        return out
    try:
        return {**article_lead.leads(urls, cache_path), **out}
    except Exception as e:  # noqa: BLE001
        print(f"[news] 첫 문단 실패 — 제목만으로 : {str(e)[:80]}")
        return out


def classify(store, save, lead_cache=None, label="radar-news"):
    """새 기사 · 문장 탈락 기사만 분류 (ai_model 이 없는 것). Groq 두 사슬(news · news-alt)을 배치마다 번갈아 쓴다.
    save(store) = 부르는 쪽의 저장 함수 (배치마다 부른다). lead_cache = 첫 문단 캐시 파일 (깃에 넣지 않는 곳, None 이면 기사를 열지 않는다)."""
    _env()
    from llm_chain import LLMPool, usage_line
    head = open(PROMPT, encoding="utf-8").read()
    companies = {s: f"{EN[s]} ({U.name(s)})" for s, *_ in U.CANDIDATES}
    try:
        pools = [LLMPool("news", label=label), LLMPool("news-alt", label=label)]
    except RuntimeError as e:
        print(f"[news] {e} — 분류 없이 둔다(판단 유보)")
        return store
    cut = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=CLASSIFY_HOURS)).strftime("%Y-%m-%dT%H:%M")
    old = sum(1 for v in store.values() if not v.get("ai_model") and v["published_at"][:16] < cut)
    if old:
        print(f"[news] {CLASSIFY_HOURS}시간보다 오래된 미분류 {old}건은 AI 에 보내지 않음")
    deadline = time.time() + MAX_MINUTES * 60
    for round_ in (1, 2):   # 2회째 = 이번 실행에서 문장 탈락한 기사 한 번 더
        todo = sorted((v for v in store.values() if not v.get("ai_model") and v["published_at"][:16] >= cut), key=lambda v: v["published_at"])
        if not todo:
            break
        ok = bad = 0
        leads = _leads(todo, lead_cache)
        i = n = 0
        while i < len(todo):
            if time.time() > deadline:
                print(f"[news] 시간 예산 {MAX_MINUTES}분 — 남은 {len(todo) - i}건은 다음 실행에서")
                break
            pool = pools[n % 2]
            size = QWEN_BATCH if pool.first_step == "groq-qwen" else BATCH   # gpt-oss 가 하루 한도로 빠지면 두 사슬 모두 Qwen 크기로
            try:
                res = _call(pool, head, companies, todo[i:i + size], leads)
            except RuntimeError as e:
                print(f"[news] 분류 실패 — 남은 {len(todo) - i}건은 다음 실행에서 : {e}")
                break
            o, b = _apply(store, res, pool.last_model, "news", leads)
            ok, bad = ok + o, bad + b
            i, n = i + size, n + 1
            save(store)   # 배치마다 저장 — 중간에 멈춰도 분류한 것은 남는다
            print(f"[news] {round_}회째 {min(i, len(todo))}/{len(todo)} ({pool.last_model})", flush=True)
        print(f"[news] {round_}회째 통과 {ok} · 탈락 {bad}")
    print(f"[news] {usage_line()}")
    return store


def recheck(store):
    """보정 규칙 · 문장 검사는 멱등 — 바뀐 규칙을 이미 분류한 기사에도 다시 적용한다 (분류 전에 한 번)."""
    for x in store.values():   # 보정 규칙 · 문장 검사는 멱등 — 바뀐 규칙을 이미 분류한 기사에도 다시 적용한다
        if x.get("scores"):
            _cap(x)
        if x.get("detail") and detail_style_bad(x["detail"]):
            x["detail"] = None   # 요약 줄만 뺀다 (숫자 검사는 첫 문단이 있는 분류 때만)
        chk = (lambda: fact_problem(x, numbers=x.get("fact_src") != "lead"))
        if x.get("fact") and chk():
            print(f"[news] 저장된 문장 탈락 ({chk()}) {x['item_id']} : {x['fact'][:60]}")
            x["fact_fails"] = x.get("fact_fails", 0) + 1
            x["fact"] = x["fact_en"] = x["detail"] = None
            if x["fact_fails"] < MAX_FACT_FAILS:
                x["ai_model"] = None
    return store
