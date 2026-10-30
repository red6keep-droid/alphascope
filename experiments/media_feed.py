"""미디어 데일리 재료(방송 영상별 요약)를 다른 리포트로 나눠 보낸다 (2026-10-25 사용자).

- 한 종목이 중심인 이슈(scope=stock) → 그 종목 상세 페이지 · 엔비디아 리포트의 뉴스 목록
- 시장 · 업종 이슈(scope=market · sector) → 미국 데일리 뉴스 · 홈 주요 뉴스 (market())
사실 · 의견을 거르지 않는다(사용자: 전망 · 의견도 받는다). 의견이 섞이므로 채널 이름(그 영상 링크)과 `방송` 라벨을 늘 붙인다.
재료 = 수집기(red9keep/yutb-sub)의 Firestore `summaries` — media-daily/collect.py 와 같은 읽기 전용 키(YTB_FIRESTORE_KEY, 없으면 gcloud 기본 인증).
못 읽으면 빈 목록 — 받는 리포트는 방송 줄 없이 그대로 돈다. 시험용 = 환경 변수 MEDIA_FEED_JSON(수집기 모양 영상 목록 JSON 파일).

    python experiments/media_feed.py --day 2026-10-23            # 종목별 · 시장 줄 수 확인
"""

import argparse
import datetime
import importlib.util
import json
import os
import re
import sys
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
KST = datetime.timezone(datetime.timedelta(hours=9))

# media-daily/config.py 를 다른 이름으로 읽는다 — 받는 리포트(nvda-report 등)에 이미 `config` 모듈이 있다
_spec = importlib.util.spec_from_file_location("media_daily_config", os.path.join(BASE, "media-daily", "config.py"))
MC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MC)
_spec = importlib.util.spec_from_file_location("radar_universe", os.path.join(BASE, "stock-radar", "universe.py"))   # 종목 페이지 후보 · 업종 · 테마 묶음
UNI = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(UNI)
_spec = importlib.util.spec_from_file_location("radar_universe_kr", os.path.join(BASE, "kr-stocks", "universe_kr.py"))   # 한국 종목 35개 · 업종 · 테마
UNI_KR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(UNI_KR)

DIRECTION = {"bullish": "positive", "bearish": "negative", "neutral": "neutral"}
# 수집기 분류 17개 → 뉴스 목록 영역 라벨 (nvda-report render_report.AREA_KO 의 열 개)
AREA = {"EARNINGS": "Earnings", "CORP_EVENT": "Corporate", "AI_CAPEX": "Demand", "REGULATION": "Regulation", "MARKET_STRUCTURE": "Flows",
        "RATES_CB": "Macro", "INFLATION": "Macro", "GROWTH_JOBS": "Macro", "TARIFF_TRADE": "Macro", "GEOPOLITICS": "Macro",
        "ENERGY_COMMODITY": "Macro", "CREDIT_BANKS": "Macro", "FISCAL_POLITICS": "Macro", "FX": "Macro", "REAL_ESTATE": "Macro",
        "CRYPTO": "Other", "OTHER": "Other"}
# 요약 단계가 적는 다른 이름 → 우리 티커 (스페이스X 는 2026-06 나스닥 상장인데 요약은 아직 비상장으로 적는다)
ALIAS = {"SPACEX(비상장)": "SPCX", "스페이스X(비상장)": "SPCX", "SPACEX": "SPCX", "CWV(비상장)": "CRWV", "COREWEAVE(비상장)": "CRWV", "코어위브(비상장)": "CRWV", "TSMC(비상장)": "TSM", "TSMC": "TSM", "GOOG": "GOOGL", "BRK.B": "BRK-B", "BRK-A": "BRK-B"}
# 업종 이슈 → 묶음 (2026-10-25 사용자: "반도체 이슈면 반도체 종목 전부에"). 묶음 = 종목 업종 칸(universe.CANDIDATES) ∪ 테마 묶음(universe.WATCH)
# 1) 주제 낱말 2) 없으면 이슈 종목 둘 이상이 같이 속한 업종 · 묶음 3) 그것도 없으면 분류(에너지 · 가상자산 · 금융 · 부동산만 — AI 투자는 너무 넓다)
# 4) 다 없으면 이슈에 적힌 종목들의 페이지에만
SECTOR_WORDS = [("반도체", "반도체"), ("메모리", "반도체"), ("칩", "반도체"), ("데이터센터", "데이터 센터"), ("데이터 센터", "데이터 센터"),
                ("AI 인프라", "데이터 센터"), ("전력", "데이터 센터"), ("우주", "우주항공"), ("위성", "우주항공"), ("가상자산", "가상자산"),
                ("암호화폐", "가상자산"), ("비트코인", "가상자산"), ("코인", "가상자산"), ("유가", "에너지"), ("원유", "에너지"),
                ("석유", "에너지"), ("에너지", "에너지"), ("양자", "양자 컴퓨터"), ("은행", "금융"), ("빅테크", "빅테크"), ("제약", "헬스케어"),
                ("바이오", "헬스케어"), ("리츠", "부동산"), ("소비재", "필수 소비재")]
SECTOR_CATEGORY = {"ENERGY_COMMODITY": ("에너지",), "CRYPTO": ("가상자산",),
                   "CREDIT_BANKS": ("금융",), "REAL_ESTATE": ("부동산",)}
LABEL = "방송"   # 뉴스 줄의 세 번째 라벨 — 기사가 아니라 방송 내용(의견 포함)이라는 표시


def _client():
    from google.cloud import firestore
    raw = os.environ.get(MC.KEY_ENV, "").strip()
    if raw:
        from google.oauth2 import service_account
        info = json.loads(raw) if raw.startswith("{") else json.load(open(raw, encoding="utf-8"))
        return firestore.Client(project=MC.FIRESTORE_PROJECT, credentials=service_account.Credentials.from_service_account_info(info))
    return firestore.Client(project=MC.FIRESTORE_PROJECT)


def load(day, days=7):
    """edition(KST 묶음 날짜)이 day 부터 days 일 전까지인 영상 목록. 실패하면 []."""
    path = os.environ.get("MEDIA_FEED_JSON")
    if path:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d["items"] if isinstance(d, dict) else d
    d0 = datetime.date.fromisoformat(day)
    editions = [(d0 - datetime.timedelta(days=i)).isoformat() for i in range(days + 1)]
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        docs = _client().collection("summaries").where(filter=FieldFilter("edition", "in", editions)).stream()
        out = []
        for doc in docs:
            r = doc.to_dict() or {}
            r["id"] = doc.id
            out.append(r)
        print(f"[media_feed] 영상 {len(out)}개 ({editions[-1]} ~ {editions[0]})")
        return out
    except Exception as e:  # noqa: BLE001 — 키 없음 · 패키지 없음 · 네트워크: 방송 줄 없이 간다
        print(f"[media_feed] 읽기 실패 — 방송 줄 없이: {str(e)[:120]}")
        return []


_GROUPS = None


def channel_groups():
    """채널 ID → 묶음 — 'required'(필수) · 'kr'(한국 증시 채널) · 'main'(미국 일반). 수집기 Firestore `channels` 표의 required · limitGroup 을 읽는다.
    사용자가 수집기에서 채널을 더하거나 묶음을 바꾸면 여기는 손대지 않아도 따라온다 (2026-10-25: 한국 증시 채널 6개 추가). 못 읽으면 {} (모두 main)."""
    global _GROUPS
    if _GROUPS is None:
        _GROUPS = {}
        if not os.environ.get("MEDIA_FEED_JSON"):
            try:
                for d in _client().collection("channels").stream():
                    c = d.to_dict() or {}
                    _GROUPS[d.id] = "required" if c.get("required") else (c.get("limitGroup") or "main")
            except Exception as e:  # noqa: BLE001
                print(f"[media_feed] 채널 표 읽기 실패 — 모두 미국 일반으로: {str(e)[:80]}")
    return _GROUPS


def _ticker(t):
    t = str(t).strip().upper()
    return ALIAS.get(t, t)


def rows(items):
    """영상 × 이슈 한 줄씩. 같은 채널이 같은 주제를 여러 영상에서 다루면 가장 최근 하나만."""
    out, seen = [], set()
    for it in sorted(items, key=lambda r: str(r.get("publishedAt") or ""), reverse=True):
        ch = it.get("channelName") or ""
        for i, iss in enumerate(it.get("issues") or []):
            if not isinstance(iss, dict) or not iss.get("topic"):
                continue
            key = (ch, iss["topic"])
            if key in seen:
                continue
            seen.add(key)
            pub = it.get("publishedAt")
            out.append({"id": f"{it.get('id')}/{i}", "topic": iss["topic"], "note": iss.get("note") or "",
                        "category": iss.get("category") or "OTHER", "scope": iss.get("scope") or "",
                        "direction": DIRECTION.get(iss.get("stance"), "neutral"), "surprise": iss.get("surprise") == "surprise",
                        "tickers": [_ticker(t) for t in iss.get("tickers") or []], "country": iss.get("country") or "",
                        "channel": MC.CHANNEL_SHORT.get(ch, ch), "url": it.get("url"), "group": channel_groups().get(it.get("channelId"), "main"),
                        "published_at": pub.isoformat() if hasattr(pub, "isoformat") else str(pub or "")})
    return out


def _groups_of(sym):
    g = {c[3] for c in UNI.CANDIDATES if c[0] == sym}
    return g | {nm for nm, syms in UNI.WATCH if sym in syms}


def _members(group):
    return {c[0] for c in UNI.CANDIDATES if c[3] == group} | next((set(syms) for nm, syms in UNI.WATCH if nm == group), set())


def sector_groups(r):
    """업종 이슈가 가리키는 묶음 이름들."""
    hit = {g for w, g in SECTOR_WORDS if w in r["topic"]}
    if not hit:
        from collections import Counter
        cnt = Counter(g for t in set(r["tickers"]) for g in _groups_of(t))
        hit = {g for g, n in cnt.items() if n >= 2}   # 종목 하나의 업종 칸만으로 넓히지 않는다 (테슬라 → `소비 · 플랫폼` 전체 X)
    if not hit:
        hit = set(SECTOR_CATEGORY.get(r["category"], ()))
    return hit


def stocks_for(r):
    """이 이슈를 보일 종목 페이지들 — 종목 이슈는 중심 종목(들), 업종 이슈는 그 묶음 종목 전부 + 이슈에 적힌 종목(페이지가 있는 것). 시장 이슈는 없음.
    업종 이슈에 적힌 종목도 넣는다 (2026-10-25 사용자: '데이터 센터 전력' 이 미디어 데일리 관련 페이지의 AMD · 인텔 · 브로드컴에도)."""
    if r["scope"] == "stock":
        return {t for t in r["tickers"] if t in UNI.BY_SYM and for_ticker([r], t, UNI.name(t))}
    if r["scope"] == "sector":
        g = sector_groups(r)
        return set().union(set(), *(_members(x) for x in g)) | {t for t in r["tickers"] if t in UNI.BY_SYM}
    return set()


def for_page(rs, sym):
    """종목 페이지 하나에 보일 줄 — 그 종목이 중심인 이슈 + 그 종목이 속한 업종 이슈."""
    return [r for r in rs if sym in stocks_for(r)]


def for_ticker(rs, sym, name=""):
    """이 종목이 중심인 이슈만 — scope=stock 이고, 주제에 회사 이름이 있거나 첫 번째 종목일 때.
    종목 칸에 같이 적힌 것만으로는 넣지 않는다(10-22 '메타 테슬라 실적 및 AI 투자 부담' 에 NVDA 가 붙어 있었다).
    name = 한글 이름 ('알파벳(구글)' 이면 알파벳 · 구글 둘 다). 업종 · 시장 이슈는 market() 쪽."""
    names = [n.strip() for n in name.replace(")", "(").split("(") if n.strip()] + [sym]
    return [r for r in rs if r["scope"] == "stock" and sym in r["tickers"]
            and (sym in r.get("leads", r["tickers"][:1]) or any(n in t for t in r.get("topics", [r["topic"]]) for n in names))]


# 한국 종목 — 요약 단계가 미국 장외 티커로 적는 것 (SSNLF(KR) 등). 모르는 티커는 그대로 (media-daily render 에서 옮김)
KR_NAME = {"SSNLF": "삼성전자", "SSNNF": "삼성전자", "005930": "삼성전자", "000660": "SK하이닉스", "HXSCL": "SK하이닉스", "HYMTF": "현대차", "005380": "현대차", "LGEAF": "LG전자"}


def korea(iss, n=6):
    """한국장에 영향을 줄 만한 소식 — country=KR 이거나 한국 종목('(KR)')이 붙은 이슈, 최근 순 n 개 (media-daily cluster.korea_links 와 같은 기준).
    2026-10-25 사용자: 미국 데일리 `한국장` 탭으로. iss = issues() 결과."""
    out = [r for r in iss if r["category"] != "OTHER"
           and (r["country"] == "KR" or any("(KR)" in t for t in r["tickers"]) or "kr" in (r.get("groups") or [r.get("group")]))]   # 한국 증시 채널 이슈는 모두
    return sorted(out, key=lambda r: str(r["published_at"]), reverse=True)[:n]


def kr_label(r):
    """한국장 소식 줄 라벨 — 연결된 한국 종목 · 기업 이름, 없으면 분야 이름 (`[삼성전자] 애플 첫 폴더블 아이폰 출시`, 2026-10-23 사용자 안)."""
    for t in r["tickers"]:
        base = t.replace("(KR)", "").strip()
        # 한국 종목만 — 한글 이름 · 알려진 장외 티커 · 6자리 코드. 요약이 해외 종목에도 (KR) 을 붙인다(BABA(KR) · VOLVO(KR), 10-23) → 분야 이름으로
        if "(KR)" in t and (base in KR_NAME or base.isdigit() or re.search(r"[가-힣]", base)):
            return KR_NAME.get(base, base)
    return MC.CATEGORY_KO.get(r["category"], "한국")


# ---------------------------------------------------------------- 한국 종목 페이지 (2026-10-25 사용자: 한국 종목 상세 `오늘` 탭 = 방송 뉴스)

KR_CODE = {c[0].split(".")[0]: c[1] for c in UNI_KR.CANDIDATES}            # 005930 → 삼성전자
KR_BY_NAME = {c[1].upper(): c[0].split(".")[0] for c in UNI_KR.CANDIDATES}  # 삼성전자 → 005930 (NAVER 처럼 영문 이름은 대문자로 맞춘다)
KR_ALIAS = {"삼성": "005930", "하이닉스": "000660", "SK하이닉스": "000660", "현대자동차": "005380", "네이버": "035420", "LG엔솔": "373220",
            "포스코홀딩스": "005490", "한전": "015760", "한국조선해양": "009540", "현대중공업": "329180", "삼성바이오": "207940",
            # 영문 표기 — 미국 방송 요약이 `SK HYNIX(KR)` · `SKHYNIX(KR)` · `SAMSUNG ELECTRONICS(KR)` 처럼 적는다 (2026-10-30 점검: 10-22~30 기록에서 4건이 코드로 안 바뀜)
            "SKHYNIX": "000660", "HYNIX": "000660", "SAMSUNG": "005930", "SAMSUNGELECTRONICS": "005930", "SAMSUNGELEC": "005930",
            "HYUNDAI": "005380", "HYUNDAIMOTOR": "005380", "KIA": "000270", "LGENERGYSOLUTION": "373220", "LGES": "373220", "SAMSUNGSDI": "006400",
            "LGCHEM": "051910", "LGELECTRONICS": "066570", "CELLTRION": "068270", "SAMSUNGBIOLOGICS": "207940", "KAKAO": "035720", "POSCO": "005490",
            "POSCOHOLDINGS": "005490", "HANWHAAEROSPACE": "012450", "SKTELECOM": "017670", "KBFINANCIAL": "105560", "SHINHAN": "055550", "KEPCO": "015760",
            "DOOSANENERBILITY": "034020", "SKSQUARE": "402340", "HANMISEMICONDUCTOR": "042700", "ECOPROBM": "247540", "ECOPRO": "086520"}


def _kr_norm(s):
    """비교용 — 띄어쓰기 · 점 · 가운뎃점 · 하이픈을 빼고 대문자 (`SK HYNIX` = `SKHYNIX` = `SK하이닉스` 의 영문)."""
    return re.sub(r"[\s.·_\-]", "", s).upper()


_KR_BY_NAME_N = {_kr_norm(k): v for k, v in KR_BY_NAME.items()}
_KR_ALIAS_N = {_kr_norm(k): v for k, v in KR_ALIAS.items()}


def kr_code(t):
    """요약이 적는 한국 종목 표기 → 종목 코드(우리 35개 안), 아니면 None.
    `삼성전자(KR)` · `005930(KR)` · `SSNLF(KR)`(미국 장외 티커, KR_NAME) · `SK하이닉스` · `SK HYNIX(KR)` 처럼 제각각이다. 띄어쓰기 · 대소문자는 무시."""
    base = re.sub(r"\((KR|비상장)\)$", "", str(t)).strip()
    if base.isdigit() and base.zfill(6) in KR_CODE:
        return base.zfill(6)
    name = KR_NAME.get(base.upper(), base)
    k = _kr_norm(name)
    return _KR_BY_NAME_N.get(k) or _KR_ALIAS_N.get(k)


def _kr_members(group):
    """한국 묶음 — 테마(반도체 · 2차전지 · 바이오 · 방산 · 조선 · 원전) 또는 업종 이름."""
    return {c[0].split(".")[0] for c in UNI_KR.CANDIDATES if group in c[4] or c[3] == group}


KR_SECTOR_WORDS = [("반도체", "반도체"), ("메모리", "반도체"), ("HBM", "반도체"), ("배터리", "2차전지"), ("2차전지", "2차전지"), ("이차전지", "2차전지"),
                   ("바이오", "바이오"), ("제약", "바이오"), ("방산", "방산 · 조선 · 원전"), ("조선", "방산 · 조선 · 원전"), ("원전", "방산 · 조선 · 원전"),
                   ("은행", "금융"), ("금융", "금융"), ("보험", "금융"), ("자동차", "경기 소비재")]


KR_GLOBAL_GROUPS = {"반도체", "2차전지"}   # 미국 방송의 업종 이야기도 한국 종목에 닿는 묶음 (미국과 연결 — 마이크론 · 엔비디아 ↔ 삼성전자 · SK하이닉스)


def kr_stocks_for(r):
    """이 이슈를 보일 한국 종목 페이지(코드) — 종목 이슈는 중심 종목(첫 종목이거나 주제에 이름), 업종 이슈는 그 묶음 전부 + 적힌 한국 종목.
    미국 종목 페이지(stocks_for)와 같은 규칙. 시장 이슈는 데일리 한국장 탭(korea)."""
    codes = [c for c in (kr_code(t) for t in r["tickers"]) if c]
    if r["scope"] == "stock":
        leads = {kr_code(t) for t in r.get("leads", r["tickers"][:1])}
        topics = r.get("topics", [r["topic"]])
        return {c for c in codes if c in leads or any(KR_CODE[c] in t for t in topics)}
    if r["scope"] == "sector":
        groups = {g for w, g in KR_SECTOR_WORDS if any(w in t for t in r.get("topics", [r["topic"]]))}
        korean = r["country"] == "KR" or bool(codes) or "kr" in (r.get("groups") or [r.get("group")])
        if not korean:   # 미국 은행 · 바이오 뉴스가 한국 금융 · 바이오 전부에 붙지 않게 — 세계 공통 업종(반도체 · 2차전지)만 미국 이야기도 받는다
            groups &= KR_GLOBAL_GROUPS
        return set().union(set(codes), *(_kr_members(g) for g in groups))
    return set()


def for_kr_page(iss, code):
    """한국 종목 페이지 하나에 보일 방송 이슈."""
    return [r for r in iss if code in kr_stocks_for(r)]


def market(rs):
    """시장 전체 · 업종 이슈 (미국 데일리 뉴스 · 홈 주요 뉴스로). 한국 증시 채널만 다룬 이슈는 빼고 한국장 탭(korea)으로."""
    return [r for r in rs if r["scope"] in ("market", "sector") and set(r.get("groups") or [r.get("group", "main")]) != {"kr"}]


# 같은 이슈 묶기 — media-daily/cluster.py _similar 와 같은 규칙(분류가 같고 주제 낱말이 겹치면). 그 파일은 media-daily 의 config 를 읽어 여기서 부르지 않는다
_WORD = re.compile(r"[가-힣A-Za-z0-9]{2,}")
_STOP = {"기대", "전망", "우려", "논쟁", "강세", "약세", "상승", "하락", "증가", "감소", "영향", "관련", "지속", "확대", "축소", "가능성", "발표", "소식", "실적", "분기", "1분기", "2분기", "3분기", "4분기", "주가", "시장", "및", "AI", "ai", "성장", "투자", "급증", "흑자", "적자"}
# 데일리 뉴스 라벨(daily-report THEME_VOCAB) — 홈도 같은 이름
THEME = {"RATES_CB": "금리", "AI_CAPEX": "AI/반도체", "EARNINGS": "실적", "ENERGY_COMMODITY": "에너지", "TARIFF_TRADE": "정책/규제", "REGULATION": "정책/규제",
         "FISCAL_POLITICS": "정책/규제", "GEOPOLITICS": "지정학", "INFLATION": "매크로", "GROWTH_JOBS": "매크로", "FX": "매크로", "CREDIT_BANKS": "매크로",
         "REAL_ESTATE": "매크로", "MARKET_STRUCTURE": "매크로", "CRYPTO": "기타", "OTHER": "기타"}


def _words(t):
    return {w.lower() for w in _WORD.findall(str(t or "")) if w not in _STOP}


def _same(a, b):
    if a["category"] != b["category"]:
        return False
    wa, wb = _words(a["topic"]), _words(b["topic"])
    return bool(wa and wb and len(wa & wb) >= max(1, min(2, min(len(wa), len(wb)) // 2)))


def issues(rs, since=""):
    """**한 곳에서 먼저 정리** (2026-10-25 사용자: "중복은 한 곳에서 정리한 뒤 뿌린다") — 영상 × 이슈 줄을 같은 이슈끼리 하나로 합친다.
    규칙 = media-daily/cluster.py 와 같음: 분류가 같고 주제 낱말이 겹치면 같은 이슈, 묶음의 첫 줄(가장 최근)과만 비교(사슬 방지).
    이슈 하나 = 대표 줄(가장 최근 영상)의 칸 + topics(합친 주제들) · leads(줄마다 첫 종목) · tickers(합친 종목, 많이 나온 순) ·
    scope(많은 쪽) · direction(엇갈리면 중립) · n_channels · n_videos · channels · theme. 받는 곳(종목 페이지 · 엔비디아 · 데일리 · 홈)은 이 목록만 쓴다.
    since = 'YYYY-MM-DDTHH:MM' UTC 이후 영상만 묶는다 (방송 n곳도 그 안에서 센다)."""
    groups = []
    for r in sorted(rs, key=lambda r: str(r["published_at"]), reverse=True):
        if str(r["published_at"])[:16] < since:
            continue
        g = next((g for g in groups if _same(r, g[0])), None)
        if g is None:
            groups.append([r])
        else:
            g.append(r)
    out = []
    for g in groups:
        rep = g[0]
        st = Counter(r["direction"] for r in g).most_common()
        sc = Counter(r["scope"] for r in g if r["scope"]).most_common(1)
        out.append(dict(rep, topics=list(dict.fromkeys(r["topic"] for r in g)), leads={r["tickers"][0] for r in g if r["tickers"]},
                        tickers=[t for t, _ in Counter(t for r in g for t in r["tickers"]).most_common()],
                        scope=sc[0][0] if sc else rep["scope"], surprise=any(r["surprise"] for r in g),
                        direction=st[0][0] if len(st) == 1 or st[0][1] > st[1][1] else "neutral",   # 방송끼리 엇갈리면 중립
                        n_channels=len({r["channel"] for r in g}), n_videos=len(g), groups=sorted({r.get("group", "main") for r in g}),
                        channels=[c for c, _ in Counter(r["channel"] for r in g).most_common()], theme=THEME.get(rep["category"], "기타")))
    return out


PICK_ACTION = {"buy": "매수", "hold": "보유", "watch": "관망", "sell": "매도"}


def picks(items, since=""):
    """방송에서 나온 종목 의견 (2026-10-29 사용자 P85: "당잠사에서 톰 리가 추천했다 · 목표가") — 수집기 요약의 `picks` 칸을 그대로 옮긴다.
    한 줄 = {market · ticker · name · action(매수 · 보유 · 관망 · 매도) · speaker · own(본인 의견) / report(증권사 보고서를 방송이 전함) · target · currency ·
    reason · quote · channel · url(그 장면 시각) · published_at}. 같은 영상 · 같은 사람 · 같은 종목은 한 줄. since = 'YYYY-MM-DD' 이후 영상만."""
    out, seen = [], set()
    for it in sorted(items, key=lambda r: str(r.get("publishedAt") or ""), reverse=True):
        pub = it.get("publishedAt")
        pub = pub.isoformat() if hasattr(pub, "isoformat") else str(pub or "")
        if pub[:10] < since:
            continue
        ch = it.get("channelName") or ""
        for p in it.get("picks") or []:
            t = str(p.get("ticker") or "").strip().upper()
            key = (it.get("id"), p.get("speaker"), t)
            if not t or key in seen or p.get("action") not in PICK_ACTION:
                continue
            seen.add(key)
            url = it.get("url") or ""
            if url and p.get("atSec"):
                url += ("&" if "?" in url else "?") + f"t={int(p['atSec'])}"
            out.append({"market": p.get("market") or "", "ticker": t, "name": p.get("name") or "", "action": PICK_ACTION[p["action"]],
                        "speaker": (p.get("speaker") or "").strip(), "own": p.get("source") != "report", "target": p.get("targetPrice"),
                        "currency": p.get("currency") or "", "reason": (p.get("reason") or "").strip(), "quote": (p.get("quote") or "").strip(),
                        "channel": MC.CHANNEL_SHORT.get(ch, ch), "url": url, "published_at": pub})
    return out


def diag(vids, iss, tag="[media_feed 진단]"):
    """재료가 어디로 가는지 로그 한 묶음 (2026-10-30 사용자: 한국 종목 페이지 35개 중 31개가 방송 0건 — 재료 문제인지 나누기 문제인지 CI 로그로 가린다).
    영상의 채널 묶음(kr · main · required) · 묶음별 이슈 범위(시장 · 업종 · 종목) · 한국 종목별 배정 수 · 코드로 못 바꾼 한국 표기. 출력만 하고 아무것도 바꾸지 않는다."""
    gmap = channel_groups()
    vg = Counter(gmap.get(v.get("channelId"), "main") for v in vids)
    print(f"{tag} 영상 {len(vids)}개 — 채널 묶음별 {dict(vg)} · 채널 {dict(Counter(MC.CHANNEL_SHORT.get(v.get('channelName'), v.get('channelName')) for v in vids).most_common(12))}")
    for g in sorted({x for r in iss for x in r["groups"]}):
        sub = [r for r in iss if g in r["groups"]]
        print(f"{tag} 묶음 {g}: 이슈 {len(sub)} · 범위 {dict(Counter(r['scope'] or '-' for r in sub))} · 한국 종목 페이지에 닿는 이슈 {sum(1 for r in sub if kr_stocks_for(r))} · 미국 종목 페이지 {sum(1 for r in sub if stocks_for(r))}")
    per = Counter(KR_CODE.get(c, c) for r in iss for c in kr_stocks_for(r))
    print(f"{tag} 한국 종목별 배정: " + (" · ".join(f"{k} {v}" for k, v in per.most_common()) or "없음"))
    bad = Counter(t for r in iss for t in r["tickers"] if ("(KR)" in t or re.search(r"[가-힣]", t)) and not kr_code(t))
    if bad:
        print(f"{tag} 코드로 못 바꾼 한국 표기: {dict(bad.most_common(15))}")
    kr_only = [r for r in iss if "kr" in r["groups"] and not kr_stocks_for(r)]
    for r in kr_only[:12]:   # 한국 채널 이슈인데 종목 페이지로 안 가는 것 — 범위 · 종목 · 주제
        print(f"{tag}   kr 미배정: {r['scope'] or '-'} {r['category']} {r['tickers'][:4]} | {r['topic'][:50]}")


def market_top(iss, n):
    """시장 · 업종 이슈 중 방송 여러 곳이 같이 다룬 순으로 n 개 — 미국 데일리 뉴스 · 홈 주요 뉴스 (2026-10-25 사용자). iss = issues() 결과."""
    out = [r for r in market(iss) if r["category"] != "OTHER"]
    out.sort(key=lambda r: str(r["published_at"]), reverse=True)
    out.sort(key=lambda r: (-r["n_channels"], -r["n_videos"]))   # 방송 수 → 영상 수 → 최근
    return out[:n]


def event(r):
    """종목 페이지 · 엔비디아 리포트 뉴스 목록 한 줄 (nvda-report judge._ev 모양). 헤드라인 = 방송 주제, 요약 줄 = 방송 주장(note), 매체 자리 = 채널, 라벨 = 영역 · 방향 · 방송.
    has_fact=False · media=True — 중요 이슈(사실 문장) · AI 서술 입력에는 넣지 않는다 (의견이 섞여 있다)."""
    return {"area": AREA.get(r["category"], "Other"), "kind": "news", "title": r["topic"], "fact": r["topic"], "detail": r["note"], "url": r["url"],
            "direction": r["direction"], "emphasis": False, "published_at": r["published_at"],
            "source": r["channel"] + (f" · 방송 {r['n_channels']}곳" if r.get("n_channels", 1) > 1 else ""),
            "speaker": LABEL, "media": True, "has_fact": False, "rel": 0, "prio": False}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=datetime.datetime.now(KST).strftime("%Y-%m-%d"))
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    rs = rows(load(a.day, a.days))
    iss = issues(rs)
    c = Counter(t for r in iss for t in stocks_for(r))
    print(f"영상 × 이슈 {len(rs)}줄 → 이슈 {len(iss)}개 · 종목 중심 {sum(r['scope'] == 'stock' for r in iss)} · 시장 · 업종 {len(market(iss))}")
    print("종목별:", " · ".join(f"{k} {v}" for k, v in c.most_common(25)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
