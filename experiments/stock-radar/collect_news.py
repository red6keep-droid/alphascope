"""공용 뉴스 수집 · 분류 (doc/종목-레이더-기획.md 10-4 · 10-8 2단계) — 상세 페이지 `오늘` 탭의 중요 이슈 · 뉴스.

- 수집 : 후보 20개마다 Google News RSS(최근 7일, 영어) 최근 PER_STOCK 건. 같은 제목은 한 건으로 친다(여러 종목에 겹치는 기사).
- 분류 : 기사마다 **한 번만**, 한 호출 BATCH 건. 한 호출에서 종목별 관련도 · 방향을 같이 받는다(scores). 영어 사실 문장(fact_en)도 같은 호출 — 영어판 준비(10-6).
- 사슬 : `json-lite` (flash-lite 먼저 — flash 하루 약 20회는 NVDA 리포트 몫). 예비 모델이 답한 건은 ai_model 에 콜론이 남아 다음 실행에서 다시 분류한다.
- 보정 : NVDA 리포트 labels 의 의견 매체 · 의견형 제목 규칙으로 관련도를 1 이하로 깎는다(올리지 않는다).
- AI 가 전부 막힌 날 : 분류 없이 둔다 → 화면은 원문 제목과 `판단 유보` 라벨 (10-4).
결과는 data/news.json (item_id → 기사). 8일이 지난 기사는 지운다.
"""

import datetime
import email.utils
import hashlib
import html as html_mod
import json
import os
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, ".."))
sys.path.insert(0, os.path.join(BASE, "..", "nvda-report"))

import universe as U  # noqa: E402

NEWS = os.path.join(BASE, "data", "news.json")
PROMPT = os.path.join(BASE, "prompts", "classify.txt")
PER_STOCK = 15
BATCH = 25   # 한 호출 기사 수 — 40 은 답(사실 문장 둘 · 종목 점수)이 길어 lite 응답이 느렸다 (2026-10-18)
KEEP_DAYS = 8
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
AREAS = ("Earnings", "Flows", "Regulation", "Legal", "Product", "Demand", "Supply", "Corporate", "Macro", "Other")
DIRS = ("positive", "negative", "uncertain", "neutral")
EN = {"NVDA": "Nvidia", "AAPL": "Apple", "GOOGL": "Alphabet Google", "MSFT": "Microsoft", "AMZN": "Amazon", "META": "Meta Platforms",
      "AVGO": "Broadcom", "TSLA": "Tesla", "BRK-B": "Berkshire Hathaway", "LLY": "Eli Lilly", "MU": "Micron", "WMT": "Walmart",
      "JPM": "JPMorgan", "AMD": "AMD", "V": "Visa", "XOM": "Exxon Mobil", "JNJ": "Johnson & Johnson", "MA": "Mastercard",
      "ABBV": "AbbVie", "INTC": "Intel",
      # 2026-10-20 추가 29개 (doc/종목-레이더-기획.md 10-12)
      "TSM": "TSMC", "ASML": "ASML", "LRCX": "Lam Research", "AMAT": "Applied Materials", "ORCL": "Oracle", "ANET": "Arista Networks",
      "VRT": "Vertiv", "EQIX": "Equinix", "CEG": "Constellation Energy", "CRWV": "CoreWeave", "SPCX": "SpaceX", "RKLB": "Rocket Lab",
      "KO": "Coca-Cola", "PG": "Procter & Gamble", "PM": "Philip Morris", "NFLX": "Netflix", "DIS": "Disney", "HD": "Home Depot",
      "MCD": "McDonald's", "CAT": "Caterpillar", "GE": "GE Aerospace", "COST": "Costco", "CVX": "Chevron", "LIN": "Linde",
      "NEM": "Newmont", "WELL": "Welltower", "PLD": "Prologis", "NEE": "NextEra Energy", "SO": "Southern Company"}


def _env():
    """로컬 실행이면 저장소 .env 에서 LLM 키만 읽는다 (Actions 는 secrets 가 환경 변수로 들어온다). Slack 웹훅은 읽지 않는다 — 로컬 시험이 알림을 보내지 않게."""
    path = os.path.join(BASE, "..", "..", ".env")
    if os.environ.get("GEMINI_API_KEY") or not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        k, _, v = line.strip().partition("=")
        v = re.split(r"\s+#", v, 1)[0].strip().strip('"')   # 줄 끝 주석은 떼고
        if k in ("GEMINI_API_KEY", "NVIDIA_API_KEY", "GROQ_API_KEY") and v:
            os.environ.setdefault(k, v)


def _strip(t):
    return re.sub(r"\s+", " ", html_mod.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip()


def _key(title):
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def fetch(sym):
    q = urllib.parse.quote(f'"{EN[sym]}" stock when:7d')
    r = requests.get(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en", headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    out = []
    for it in ET.fromstring(r.content).iter("item"):
        title = _strip(it.findtext("title"))
        src = _strip(it.findtext("source"))
        if src and title.endswith(" - " + src):
            title = title[: -len(src) - 3]
        try:
            pub = email.utils.parsedate_to_datetime(it.findtext("pubDate")).astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError):
            continue
        out.append({"title": title, "url": it.findtext("link"), "source": src, "published_at": pub, "query": sym})
    out.sort(key=lambda x: x["published_at"], reverse=True)
    return out[:PER_STOCK]


def collect(store):
    now = datetime.datetime.now(datetime.timezone.utc)
    cut = (now - datetime.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    store = {k: v for k, v in store.items() if v["published_at"] >= cut}
    seen = {_key(v["title"]): k for k, v in store.items()}
    new = 0
    for sym, *_ in U.CANDIDATES:
        time.sleep(1)   # 종목당 1회, 사이 1초 — 기획(알파-종목-리포트 341)대로. 49회 연속 요청을 피한다 (2026-10-21)
        try:
            items = fetch(sym)
        except Exception as e:   # noqa: BLE001
            print(f"[news] {sym} 받기 실패 : {e}")
            continue
        for x in items:
            k = _key(x["title"])
            if k in seen:
                store[seen[k]].setdefault("queries", [])
                if sym not in store[seen[k]]["queries"]:
                    store[seen[k]]["queries"].append(sym)
                continue
            iid = hashlib.sha1(k.encode()).hexdigest()[:12]
            store[iid] = dict(x, item_id=iid, queries=[sym])
            seen[k] = iid
            new += 1
    print(f"[news] 새 기사 {new}건 · 보관 {len(store)}건")
    return store


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
    """의견 · 해설 기사는 관련도 1 이하 (NVDA labels.adjust 와 같은 규칙, 깎기만)."""
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
RECHECK_MAX = 25   # 관련도 3 기사를 flash 로 다시 받는 하루 상한 — 한 호출 (기획 10-4 : 이벤트만 flash, 하루 0~3회)


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


def fact_problem(x):
    """사실 문장이 원문 제목과 숫자가 맞지 않거나 인과 · 평가 말을 쓰면 그 이유, 괜찮으면 None."""
    f = x.get("fact") or ""
    bad = [w for w in BANNED if w in f]
    if bad:
        return "말투 " + bad[0]
    src = _vals(x["title"], EN_NUM, EN_UNIT) + [("n", float(v)) for w, v in EN_WORDS.items() if re.search(rf"\b{w}\b", x["title"], re.I)]
    for kind, v in _vals(f, KO_NUM, KO_UNIT, skip_dates=True):
        if not any(k == kind and abs(v - s) <= max(abs(s), 1e-9) * 0.02 for k, s in src):
            return f"숫자 {v:g}"
    return None


def _apply(store, res, model, label):
    """분류 결과를 저장 + 보정 + 문장 검사. 탈락은 다시 분류 대상으로 돌린다."""
    ok = bad = 0
    for r in res:
        x = store[r["item_id"]]
        x.update(area=r["area"], scores=r["scores"], fact=r["fact"].replace(" — ", ", ").replace("—", ", "), fact_en=r.get("fact_en"), ai_model=model)
        _cap(x)
        why = fact_problem(x)
        if why:
            x["fact_fails"] = x.get("fact_fails", 0) + 1
            print(f"[news] {label} 문장 탈락 ({why}) {x['item_id']} : {x['fact'][:60]}")
            x["fact"] = x["fact_en"] = None
            if x["fact_fails"] < MAX_FACT_FAILS:
                x["ai_model"] = None   # 다음 분류 때 다시
            bad += 1
        else:
            ok += 1
    return ok, bad


def _call(pool, head, companies, part):
    items = [{"item_id": x["item_id"], "title": x["title"], "source": x["source"], "published_at": x["published_at"][:10]} for x in part]
    return pool.generate_json(head + json.dumps({"companies": companies, "items": items}, ensure_ascii=False), temperature=0.0, validate=_valid(items))


def classify(store):
    """1) 새 기사 · 탈락 기사 → lite (json-lite) 2) 관련도 3 기사 → flash (json) 로 다시 받아 덮는다."""
    _env()
    from llm_chain import LLMPool, usage_line
    head = open(PROMPT, encoding="utf-8").read()
    companies = {s: f"{EN[s]} ({U.name(s)})" for s, *_ in U.CANDIDATES}
    try:
        lite = LLMPool("json-lite", label="radar-news")
    except RuntimeError as e:
        print(f"[news] {e} — 분류 없이 둔다(판단 유보)")
        return store
    for round_ in (1, 2):   # 2회째 = 이번 실행에서 문장 탈락한 기사 한 번 더
        todo = sorted((v for v in store.values() if not v.get("ai_model") or ":" in v["ai_model"]), key=lambda v: v["published_at"])
        if not todo:
            break
        ok = bad = 0
        for i in range(0, len(todo), BATCH):
            try:
                res = _call(lite, head, companies, todo[i:i + BATCH])
            except RuntimeError as e:
                print(f"[news] 분류 실패 — 남은 {len(todo) - i}건은 다음 실행에서 : {e}")
                break
            o, b = _apply(store, res, lite.last_model, "lite")
            ok, bad = ok + o, bad + b
            save(store)   # 배치마다 저장 — 중간에 멈춰도 분류한 것은 남는다
            print(f"[news] {round_}회째 {min(i + BATCH, len(todo))}/{len(todo)} ({lite.last_model})", flush=True)
        print(f"[news] {round_}회째 통과 {ok} · 탈락 {bad}")
    top = [v for v in store.values() if v.get("scores") and not v.get("rechecked") and max(sc["relevance"] for sc in v["scores"]) >= 3]
    top = sorted(top, key=lambda v: v["published_at"], reverse=True)[:RECHECK_MAX]
    if top:
        try:
            flash = LLMPool("json", label="radar-news-check")
            res = _call(flash, head, companies, top)
            o, b = _apply(store, res, flash.last_model, "flash")
            for x in top:
                x["rechecked"] = flash.last_model
            print(f"[news] 관련도 3 다시 확인 {len(top)}건 ({flash.last_model}) · 통과 {o} · 탈락 {b}")
        except RuntimeError as e:
            print(f"[news] 관련도 3 다시 확인 실패 — 다음 실행에서 : {e}")
        save(store)
    print(f"[news] {usage_line()}")
    return store


def load():
    try:
        with open(NEWS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(store):
    os.makedirs(os.path.dirname(NEWS), exist_ok=True)
    with open(NEWS, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False)


def run():
    store = collect(load())
    for x in store.values():   # 보정 규칙 · 문장 검사는 멱등 — 바뀐 규칙을 이미 분류한 기사에도 다시 적용한다
        if x.get("scores"):
            _cap(x)
        if x.get("fact") and fact_problem(x):
            print(f"[news] 저장된 문장 탈락 ({fact_problem(x)}) {x['item_id']} : {x['fact'][:60]}")
            x["fact_fails"] = x.get("fact_fails", 0) + 1
            x["fact"] = x["fact_en"] = None
            if x["fact_fails"] < MAX_FACT_FAILS:
                x["ai_model"] = None
    save(store)
    store = classify(store)
    save(store)
    return store


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run()
