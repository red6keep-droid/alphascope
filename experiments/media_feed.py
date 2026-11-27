"""미디어 데일리 재료(방송 영상별 요약)를 다른 리포트로 나눠 보낸다.

- 한 종목이 중심인 이슈(scope=stock) → 그 종목 상세 페이지 · 엔비디아 리포트의 뉴스 목록
- 시장 · 업종 이슈(scope=market · sector) → 미국 데일리 뉴스 · 홈 주요 뉴스 (market())
- 한국 증시 내용(is_korea — 채널이 아니라 이슈의 국가 · 중심 종목으로, 2026-10-30) → 데일리 한국장 탭 · 한국 증시 리포트 (korea()) · 한국 종목 페이지 (kr_stocks_for)
사실 · 의견을 거르지 않는다. 의견이 섞이므로 채널 이름(그 영상 링크)과 `방송` 라벨을 늘 붙인다.
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
sys.path.insert(0, BASE)
import issue_codes  # noqa: E402  — 기록 이슈 코드 (P339)
_spec = importlib.util.spec_from_file_location("radar_universe", os.path.join(BASE, "stock-radar", "universe.py"))   # 종목 페이지 후보 · 업종 · 테마 묶음
UNI = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(UNI)
_spec = importlib.util.spec_from_file_location("radar_universe_kr", os.path.join(BASE, "kr-stocks", "universe_kr.py"))   # 한국 종목 35개 · 업종 · 테마
UNI_KR = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(UNI_KR)

DIRECTION = {"bullish": "positive", "bearish": "negative", "neutral": "neutral"}
# 수집기 분류 17개 → 뉴스 목록 영역 라벨 (nvda-report render_report.AREA_KO 의 열 개)
AREA = {"EARNINGS": "Earnings", "CORP_EVENT": "Corporate", "AI_CAPEX": "Demand", "REGULATION": "Regulation", "MARKET_STRUCTURE": "Flows",
        "RATES_FED": "Macro", "INFLATION": "Macro", "GROWTH_JOBS": "Macro", "TARIFF_TRADE": "Macro", "GEOPOLITICS": "Macro",
        "OIL_ENERGY": "Macro", "CREDIT_BANKS": "Macro", "FISCAL_POLITICS": "Macro", "FX_GLOBAL": "Macro", "REAL_ESTATE": "Macro",
        "INVESTOR_CALLS": "Flows", "CRYPTO": "Other", "OTHER": "Other"}   # 키 = 기록 이슈 코드 (rows 가 수집기 옛 이름을 바꿔 둔다, P339)
# 요약 단계가 적는 다른 이름 → 우리 티커 (스페이스X 는 2026-06 나스닥 상장인데 요약은 아직 비상장으로 적는다)
ALIAS = {"SPACEX(비상장)": "SPCX", "스페이스X(비상장)": "SPCX", "SPACEX": "SPCX", "CWV(비상장)": "CRWV", "COREWEAVE(비상장)": "CRWV", "코어위브(비상장)": "CRWV", "TSMC(비상장)": "TSM", "TSMC": "TSM", "GOOG": "GOOGL", "BRK.B": "BRK-B", "BRK-A": "BRK-B"}
# 업종 이슈 → 묶음. 묶음 = 종목 업종 칸(universe.CANDIDATES) ∪ 테마 묶음(universe.WATCH)
# 1) 주제 낱말 2) 없으면 이슈 종목 둘 이상이 같이 속한 업종 · 묶음 3) 그것도 없으면 분류(에너지 · 가상자산 · 금융 · 부동산만 — AI 투자는 너무 넓다)
# 4) 다 없으면 이슈에 적힌 종목들의 페이지에만
SECTOR_WORDS = [("반도체", "반도체"), ("메모리", "반도체"), ("칩", "반도체"), ("HBM", "반도체"), ("GPU", "반도체"), ("파운드리", "반도체"),
                ("데이터센터", "데이터 센터"), ("데이터 센터", "데이터 센터"), ("AI 인프라", "데이터 센터"), ("전력", "데이터 센터"),
                ("클라우드", "데이터 센터"), ("네오클라우드", "데이터 센터"),   # 클라우드 수요 · 네오클라우드(CRWV 등)는 데이터 센터 묶음
                ("우주", "우주항공"), ("위성", "우주항공"), ("스타링크", "우주항공"),
                ("가상자산", "가상자산"), ("암호화폐", "가상자산"), ("비트코인", "가상자산"), ("코인", "가상자산"), ("토큰화", "가상자산"),
                ("유가", "에너지"), ("원유", "에너지"), ("석유", "에너지"), ("에너지", "에너지"), ("유전", "에너지"), ("정제", "에너지"),
                ("휘발유", "에너지"), ("호르무즈", "에너지"), ("원자력", "에너지"),
                ("양자", "양자 컴퓨터"), ("은행", "금융"), ("결제", "결제"), ("카드", "결제"),
                ("빅테크", "빅테크"), ("매그니피센트", "빅테크"), ("소프트웨어", "빅테크"),
                ("제약", "헬스케어"), ("바이오", "헬스케어"), ("백신", "헬스케어"), ("치료제", "헬스케어"), ("메디케어", "헬스케어"),
                ("건강보험", "헬스케어"), ("의료", "헬스케어"),
                ("리츠", "부동산"), ("부동산", "부동산"), ("소비재", "필수 소비재"), ("소매", "필수 소비재"), ("유통", "필수 소비재"),
                ("레스토랑", "경기 소비재"), ("외식", "경기 소비재"), ("전자상거래", "소비 · 플랫폼"), ("전기차", "소비 · 플랫폼"),
                ("스트리밍", "커뮤니케이션"), ("정전", "유틸리티"), ("전력망", "유틸리티"), ("유틸리티", "유틸리티"),
                ("금값", "소재"), ("구리", "소재")]
# AI 설비투자 이야기(2026-10-30 보강 — 그 전엔 업종 낱말 없는 이슈의 1/3): 돈 쓰는 쪽(빅테크) + 받는 쪽(데이터 센터) 두 묶음 ≈ 11 페이지.
# 반도체 묶음까지는 안 넓힌다('빅테크 3분기 실적' 이 MU · LRCX 페이지에까지 가는 건 과함 — 반도체 · HBM · GPU 낱말이 있으면 그때).
# 분류(AI_CAPEX) 통째로도 아직 안 넓힌다 — '할리우드 AI 제작' · 'AI 와 비판적 사고' 같은 것도 그 분류에 들어온다.
SECTOR_WORDS += [(w, g) for w in ("AI 지출", "AI 투자", "AI 설비투자", "설비투자", "CAPEX", "자본 지출", "자본지출", "하이퍼스케일러", "하이퍼스케러")
                 for g in ("빅테크", "데이터 센터")]
# 2차 보강:
# AI 모델 · AI 기업 이야기 = 모델 만드는 쪽(빅테크), AI 붐 과열 = 돈 쓰는 쪽 + 받는 쪽. 사이버 보안 · 항공 · 스포츠 · 관세 일반은 우리 묶음이 없어 그대로 둔다.
SECTOR_WORDS += [("AI 모델", "빅테크"), ("AI 기업", "빅테크"), ("프론티어 AI", "빅테크"), ("오픈소스 AI", "빅테크"), ("생성형 AI", "빅테크"), ("LLM", "빅테크"),
                 ("AI 붐", "빅테크"), ("AI 붐", "데이터 센터"), ("AI 거품", "빅테크"), ("AI 거품", "데이터 센터"),
                 ("검색", "빅테크"), ("광고", "빅테크"), ("소셜 미디어", "빅테크"), ("앱스토어", "빅테크"), ("아이폰", "빅테크"), ("스마트폰", "빅테크"),
                 ("서버", "데이터 센터"), ("네트워크 장비", "데이터 센터"), ("냉각", "데이터 센터"), ("AI 인프라", "데이터 센터"),
                 ("스테이블코인", "가상자산"), ("이더리움", "가상자산"), ("지니어스", "가상자산"), ("디지털 자산", "가상자산"), ("크립토", "가상자산"),
                 ("증권", "금융"), ("자산운용", "금융"), ("금융주", "금융"), ("금융 자문", "금융"), ("브로커", "금융"), ("투자은행", "금융"),
                 ("주택", "부동산"), ("모기지", "부동산"), ("MLS", "부동산"), ("상업용 부동산", "부동산"),
                 ("자동차", "소비 · 플랫폼"), ("자율주행", "소비 · 플랫폼"), ("로보택시", "소비 · 플랫폼"), ("휴머노이드", "소비 · 플랫폼"),
                 ("비만", "헬스케어"), ("GLP", "헬스케어"), ("의료기기", "헬스케어"), ("신약", "헬스케어"), ("FDA", "헬스케어"),
                 ("천연가스", "에너지"), ("LNG", "에너지"), ("셰일", "에너지"), ("석탄", "에너지"), ("OPEC", "에너지"),
                 ("귀금속", "소재"), ("금 가격", "소재"), ("광산", "소재"), ("리튬", "소재"), ("희토류", "소재"),
                 ("식음료", "필수 소비재"), ("담배", "필수 소비재"), ("생활용품", "필수 소비재"), ("식료품", "필수 소비재"),
                 ("영화", "커뮤니케이션"), ("할리우드", "커뮤니케이션"), ("엔터테인먼트", "커뮤니케이션"), ("테마파크", "커뮤니케이션"), ("콘텐츠", "커뮤니케이션")]
SECTOR_CATEGORY = {"OIL_ENERGY": ("에너지",), "CRYPTO": ("가상자산",),
                   "CREDIT_BANKS": ("금융",), "REAL_ESTATE": ("부동산",)}
LABEL = "방송"   # 뉴스 줄의 세 번째 라벨 — 기사가 아니라 방송 내용(의견 포함)이라는 표시


def _creds(scopes=None):
    """수집기 읽기 전용 서비스 계정(YTB_FIRESTORE_KEY) — Firestore · Storage 같은 키. 없으면 None(gcloud 기본 인증)."""
    raw = os.environ.get(MC.KEY_ENV, "").strip()
    if not raw:
        return None
    from google.oauth2 import service_account
    info = json.loads(raw) if raw.startswith("{") else json.load(open(raw, encoding="utf-8"))
    return service_account.Credentials.from_service_account_info(info, scopes=scopes)


def _client():
    from google.cloud import firestore
    return firestore.Client(project=MC.FIRESTORE_PROJECT, credentials=_creds())


# 방송 요약 읽기 = 수집기 Storage 파일 (2026-11-16 수집기 안내 News-doc/블로그-Firestore-읽기-줄이기.md).
# 수집기 Firestore 하루 읽기가 무료 몫 5만을 넘었다(11-14 7.9만) — 블로그가 30일치(약 2,500문서)를 부를 때마다 통째로 읽은 탓으로 본다.
# 수집기가 묶음 날짜(edition)별 JSON 을 비공개 버킷에 올린다:
#   feed/index.json                 {"updatedAt", "editions": {날짜: {"count", "updatedAt"}}, "channelsUpdatedAt"}
#   feed/editions/YYYY-MM-DD.json   {"edition", "updatedAt", "count", "items": [summaries 문서 + "id"]} — 시각은 ISO 글자
#   feed/channels.json              {"updatedAt", "items": [channels 문서 + "id"]}
# 블로그는 Firestore 를 읽지 않는다. 받는 순서:
#  ① 한 실행(프로세스) 안 = edition 별로 한 번만 (_MEM). 데일리 kr_news · render_html 처럼 두 곳이 불러도 한 번.
#  ② 날짜별 파일 캐시(MEDIA_CACHE_DIR, 기본 ~/.cache/alphascope-media) — index.json 의 그 날짜 updatedAt 과 같으면 받지 않는다.
#     오늘 · 어제도 바뀌었을 때만 받는다. 저장소 밖 폴더(`git add -A` 에 안 섞이게), Actions 는 actions/cache 로 남긴다. MEDIA_CACHE_DIR=off 면 안 씀.
#  ③ Storage 를 못 받으면(권한 주기 전 · 네트워크) 예비 = 옛 방식: 그제 이전은 날짜 파일, 나머지는 Firestore 쿼리. 그것도 못 하면 방송 줄 없이.
FEED_BUCKET = "ytb-v1-b96d5.firebasestorage.app"
FEED_PREFIX = "feed"
_MEM = {}               # edition → 영상 목록 (이 프로세스 안)
_INDEX = {}             # feed/index.json (이 프로세스 안 한 번) — "v" 키에 값, 못 받으면 None
_SESSION = []
CACHE_KEEP_DAYS = 45    # 이보다 오래된 날짜 파일은 지운다 (가장 긴 PICK_DAYS 30일 + 여유)


def _feed(path):
    """버킷의 JSON 한 개. 없거나 못 받으면 None. google-cloud-storage 를 따로 깔지 않고 Storage JSON API 를 google-auth 세션으로 부른다."""
    try:
        if not _SESSION:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            scope = ["https://www.googleapis.com/auth/devstorage.read_only"]
            _SESSION.append(AuthorizedSession(_creds(scope) or google.auth.default(scopes=scope)[0]))
        from urllib.parse import quote
        r = _SESSION[0].get(f"https://storage.googleapis.com/storage/v1/b/{FEED_BUCKET}/o/{quote(path, safe='')}?alt=media", timeout=30)
        if r.status_code != 200:
            print(f"[media_feed] Storage {path} 못 받음: HTTP {r.status_code}")
            return None
        return r.json()
    except Exception as e:  # noqa: BLE001 — 키 없음 · 네트워크
        print(f"[media_feed] Storage {path} 못 받음: {type(e).__name__} {str(e)[:80]}")
        return None


def _feed_index():
    if "v" not in _INDEX:
        d = _feed(f"{FEED_PREFIX}/index.json")
        _INDEX["v"] = d if isinstance(d, dict) and isinstance(d.get("editions"), dict) else None
    return _INDEX["v"]


def _cache_dir():
    d = os.environ.get("MEDIA_CACHE_DIR", "").strip()
    if d.lower() == "off":
        return None
    return d or os.path.join(os.path.expanduser("~"), ".cache", "alphascope-media")


def _jsonable(r):
    """Firestore 시각(DatetimeWithNanoseconds) → ISO 글자. Storage 파일 · 예비 Firestore · 날짜 파일의 모양을 같게 한다 —
    정렬이 str(publishedAt) 이라 datetime(`2026-11-15 10:00`)과 글자(`2026-11-15T10:00`)가 섞이면 순서가 틀어진다."""
    if isinstance(r, dict):
        return {k: _jsonable(v) for k, v in r.items()}
    if isinstance(r, list):
        return [_jsonable(v) for v in r]
    return r.isoformat() if isinstance(r, (datetime.datetime, datetime.date)) else r


def _cache_read(cdir, ed):
    """날짜 파일 → {"updatedAt", "items"}. updatedAt None = 예비 Firestore 로 받은 것(그제 이전만 쓴다). 없으면 None."""
    try:
        with open(os.path.join(cdir, f"{ed}.json"), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and isinstance(d.get("items"), list) else None


def _cache_write(cdir, ed, items, updated_at=None):
    try:
        os.makedirs(cdir, exist_ok=True)
        tmp = os.path.join(cdir, f"{ed}.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"updatedAt": updated_at, "items": items}, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(cdir, f"{ed}.json"))
    except OSError as e:
        print(f"[media_feed] 캐시 쓰기 실패 {ed}: {str(e)[:80]}")


def _cache_prune(cdir, today):
    cut = (today - datetime.timedelta(days=CACHE_KEEP_DAYS)).isoformat()
    try:
        for fn in os.listdir(cdir):
            if fn.endswith(".json") and fn[:10] < cut:
                os.remove(os.path.join(cdir, fn))
    except OSError:
        pass


def _firestore_editions(need):
    """예비 — Storage 를 못 받을 때만. edition → 영상 목록. 실패하면 예외."""
    from google.cloud.firestore_v1.base_query import FieldFilter
    fresh = {ed: [] for ed in need}
    for i in range(0, len(need), 30):   # Firestore `in` 은 30개까지
        for doc in _client().collection("summaries").where(filter=FieldFilter("edition", "in", need[i:i + 30])).stream():
            r = _jsonable(doc.to_dict() or {})
            r["id"] = doc.id
            if r.get("edition") in fresh:
                fresh[r["edition"]].append(r)
    return fresh


_CHECKED = set()        # 이 프로세스에서 개수를 이미 맞춰 본 edition


def _check_recent(editions, got, today):
    """최근 묶음(어제 · 오늘 · 오후면 내일)이 늦은 파일인지 — Firestore 개수 세기(count, 묶음 하나에 1 읽기)와 받은 요약 수를 맞춰 본다.
    수집기는 실행이 끝날 때 파일을 한꺼번에 발행하고(worker/collector.py finally), 발행에 실패해도 수집은 성공으로 끝난다.
    그러면 목차는 정상인데 파일이 옛것 — 개수가 다르면 그 묶음을 got 에서 빼 Firestore 로 읽게 한다(약 70 ~ 110 읽기, 그런 때만).
    시간 기준(몇 시간 그대로면)은 밤처럼 수집이 원래 없는 때도 걸려 쓰지 않았다. 개수 세기를 못 하면 파일을 그대로 쓴다.
    → (확인한 묶음 수, 늦은 묶음 수)"""
    lo = (today - datetime.timedelta(days=1)).isoformat()
    recent = [ed for ed in editions if ed >= lo and ed in got and ed not in _CHECKED]
    if not recent:
        return 0, 0
    late = 0
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter
        col = _client().collection("summaries")
        for ed in recent:
            n_fs = col.where(filter=FieldFilter("edition", "==", ed)).count().get()[0][0].value
            _CHECKED.add(ed)
            if n_fs != len(got[ed]):
                print(f"[media_feed] {ed} 묶음 파일이 늦음: 파일 {len(got[ed])}개 · Firestore {n_fs}개, 이 묶음만 Firestore 로")
                del got[ed]
                _MEM.pop(ed, None)
                late += 1
    except Exception as e:  # noqa: BLE001 — 권한 · 네트워크: 파일을 그대로 쓴다
        print(f"[media_feed] 최근 묶음 개수 확인 실패, 파일 그대로: {type(e).__name__} {str(e)[:80]}")
    return len(recent), late


def load(day, days=7):
    """edition(KST 묶음 날짜)이 day 부터 days 일 전까지인 영상 목록. 실패하면 [].
    수집기 Storage 파일을 받는다 — 날짜 파일 캐시의 updatedAt 이 index.json 과 같으면 받지 않는다(위 주석)."""
    path = os.environ.get("MEDIA_FEED_JSON")
    if path:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d["items"] if isinstance(d, dict) else d
    d0 = datetime.date.fromisoformat(day)
    editions = [(d0 - datetime.timedelta(days=i)).isoformat() for i in range(days + 1)]
    now = datetime.datetime.now(KST)
    today = now.date()
    cur = (now + datetime.timedelta(hours=12)).date()   # 수집기 edition_day — 묶음은 낮 12시에 바뀐다(전날 12:00 ~ 오늘 11:59 = 오늘)
    if d0 == today and cur > d0:
        editions.insert(0, cur.isoformat())   # 오후 실행: 12시 뒤에 받은 영상은 `내일` 묶음 — 옛 코드는 이걸 안 읽어 21:45 홈 뉴스 · 16:10 한국 종목이 그날 오후 방송을 놓쳤다 (2026-11-16 확인)
    settled = (today - datetime.timedelta(days=2)).isoformat()   # 예비(Firestore) 때 날짜 파일을 믿는 범위 (그제 이전)
    cdir = _cache_dir()
    got = {ed: _MEM[ed] for ed in editions if ed in _MEM}
    n_mem, n_file, n_dl, n_none, n_read, n_chk, n_late = len(got), 0, 0, 0, 0, 0, 0
    need = [ed for ed in editions if ed not in got]
    index = _feed_index() if need else None
    if index is not None:
        for ed in need:
            meta = index["editions"].get(ed)
            if not meta:   # 수집 기록이 없는 날 (주말 · 발행 전)
                got[ed] = _MEM[ed] = []
                n_none += 1
                continue
            uat = meta.get("updatedAt")
            c = _cache_read(cdir, ed) if cdir else None
            if c is not None and uat and c.get("updatedAt") == uat:
                got[ed] = _MEM[ed] = c["items"]
                n_file += 1
                continue
            d = _feed(f"{FEED_PREFIX}/editions/{ed}.json")
            if isinstance(d, dict) and isinstance(d.get("items"), list):
                items = _jsonable(d["items"])
                got[ed] = _MEM[ed] = items
                n_dl += 1
                if cdir:
                    _cache_write(cdir, ed, items, uat)
            elif c is not None:   # 받기 실패 — 옛 날짜 파일이라도 (조금 늦은 내용이 빈칸보다 낫다)
                got[ed] = _MEM[ed] = c["items"]
                n_file += 1
        n_chk, n_late = _check_recent(editions, got, today)
        need = [ed for ed in editions if ed not in got]   # 여기 남은 것 = 파일 받기 실패 · 캐시 없음 · 파일이 늦은 최근 묶음 → Firestore 로
    elif need:   # 예비 — 옛 방식: 그제 이전은 날짜 파일(updatedAt 상관없이)
        for ed in need:
            c = _cache_read(cdir, ed) if cdir and ed <= settled else None
            if c is not None:
                got[ed] = _MEM[ed] = c["items"]
                n_file += 1
        need = [ed for ed in editions if ed not in got]
    if need:
        try:
            fresh = _firestore_editions(need)
            for ed, items in fresh.items():
                got[ed] = _MEM[ed] = items
                n_read += len(items)
                if cdir and ed <= settled:
                    _cache_write(cdir, ed, items, None)   # updatedAt 없음 — Storage 가 돌아오면 다시 받는다
        except Exception as e:  # noqa: BLE001 — 키 없음 · 패키지 없음 · 네트워크: 방송 줄 없이 간다(받은 날짜만)
            print(f"[media_feed] 예비 Firestore 읽기 실패, 방송 줄 없이: {str(e)[:120]}")
            if not got:
                return []
    if cdir and (n_dl or n_read):
        _cache_prune(cdir, today)
    out = [dict(r) for ed in editions for r in got.get(ed, [])]   # 얕은 복사 — 부르는 쪽이 고쳐도 _MEM 은 그대로
    print(f"[media_feed] 영상 {len(out)}개 ({editions[-1]} ~ {editions[0]}) / Storage 받기 {n_dl}일 · 날짜 파일 {n_file}일"
          f" · 실행 안 재사용 {n_mem}일 · 기록 없는 날 {n_none}일 · 최근 묶음 개수 확인 {n_chk}일 · 파일 늦음 {n_late}일 · Firestore 읽기 {n_read}개")
    return out


_GROUPS = None


def channel_groups():
    """채널 ID → 묶음 — 'required'(필수) · 'kr'(한국 증시 채널) · 'main'(미국 일반). 수집기 채널 표의 required · limitGroup 을 읽는다.
    사용자가 수집기에서 채널을 더하거나 묶음을 바꾸면 여기는 손대지 않아도 따라온다 (2026-10-25: 한국 증시 채널 6개 추가). 못 읽으면 {} (모두 main).
    읽는 곳 = Storage feed/channels.json (2026-11-16), 못 받으면 예비로 Firestore `channels`."""
    global _GROUPS
    if _GROUPS is None:
        _GROUPS = {}
        if not os.environ.get("MEDIA_FEED_JSON"):
            d = _feed(f"{FEED_PREFIX}/channels.json")
            if isinstance(d, dict) and isinstance(d.get("items"), list):
                rows = [(c.get("id"), c) for c in d["items"] if isinstance(c, dict) and c.get("id")]
            else:
                rows = []
                try:
                    rows = [(x.id, x.to_dict() or {}) for x in _client().collection("channels").stream()]
                except Exception as e:  # noqa: BLE001
                    print(f"[media_feed] 채널 표 읽기 실패, 모두 미국 일반으로: {str(e)[:80]}")
            for cid, c in rows:
                _GROUPS[cid] = "required" if c.get("required") else (c.get("limitGroup") or "main")
    return _GROUPS


def _ticker(t):
    t = str(t).strip().upper()
    return ALIAS.get(t, t)


# 한국 방송 요약 줄 앞머리의 한국 사람 이름 지우기.
# 수집기는 11-26 저녁(News-doc 52절)부터 새 요약에만 이 규칙을 쓰고 이미 저장된 요약은 다시 만들지 않는다 → 옛 줄이 7일 창에 남아 화면에 나왔다.
# 같은 규칙을 블로그가 읽을 때 한 번 더(AI 0): 회사를 알면 `회사 직함` · 모르면 채널 이름 · 기자가 전한 줄 = 사실이라 출처 없음.
# 국가 요직 · 금융 수장 · 대기업 총수(총재 · 장관 · 회장 등)는 이름 그대로(News-text-doc 23절과 같은 예외).
_KR_SURNAME = "김이박최정강조윤장임한오서신권황안송류유전홍고문양손배백허남심노하곽성차주우구민진나지엄채원천방공현함변염여추도소석선설마길연위표명기반왕금옥육인맹제모탁국어은편용예경봉사부태"
_KR_TITLE = (r"리서치센터장|센터장|본부장|부문장|팀장|파트장|실장|수석연구원|책임연구원|연구원|애널리스트|이코노미스트|전략가|대표이사|대표|부사장|사장|"
             r"전무|상무|이사|부장|차장|과장|매니저|PV|PB|위원|교수|소장|CIO|CEO|기자|앵커")
_KR_PUBLIC = re.compile(r"(대통령|총리|장관|총재|위원장|회장|의장|원장|청장)$")
_KR_PREFIX = re.compile(r"^\s*([^:：]{1,40}?)\s*(진행자 발언|기자 보도|발언|보도)\s*[:：]\s*(.+)$")
_KR_NAME = re.compile(rf"(?:^|(?<=\s))[{_KR_SURNAME}][가-힣]{{1,2}}\s+(?=(?:{_KR_TITLE})(?:\s|$))")


def kr_line_no_name(line, channel):
    """한국 방송 줄 한 줄 — 접두의 한국 사람 이름을 회사 직함 · 채널 이름으로. 이름이 없는 줄은 그대로."""
    m = _KR_PREFIX.match(str(line or ""))
    if not m:
        return line
    who, verb, text = m.group(1).strip(), m.group(2), m.group(3).strip()
    if _KR_PUBLIC.search(who):
        return line
    if not _KR_NAME.search(who):
        return line
    if verb == "기자 보도" or re.search(r"(기자|앵커)$", who):
        return text   # 기자 · 앵커가 전한 것 = 사실 줄 → 출처 없음 (46 · 47절 규칙)
    rest = re.sub(r"\s+", " ", _KR_NAME.sub("", who)).strip()
    t = re.search(rf"(?:^|\s)((?:{_KR_TITLE}))$", rest)
    org = (rest[:t.start()] if t else rest).strip()
    org = re.sub(r"(?<=[가-힣]) (?=[가-힣])", "", org)   # `한국 투자 증권` → `한국투자증권`
    if org:
        return f"{org} {t.group(1) if t else ''}".strip() + f" 발언 : {text}"
    return f"{channel} 발언 : {text}" if channel else text   # 회사 모름 = 채널 이름, 채널도 없으면 출처 없이


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
            if re.search("[가-힣]", ch):   # 한국어 채널만 — 미국 방송 줄은 그대로
                iss = dict(iss, lines=[kr_line_no_name(x, MC.CHANNEL_SHORT.get(ch, ch)) for x in (iss.get("lines") or []) if x])
            out.append({"id": f"{it.get('id')}/{i}", "topic": iss["topic"], "note": iss.get("note") or "",
                        "lines": [str(x) for x in (iss.get("lines") or []) if x][:5],   # 수집기 요약 다섯 줄 — 데일리 뉴스 팝업 (2026-11-05 요청, yutb-sub doc/요청-이슈-요약-다섯-줄.md)
                        "category": issue_codes.FROM_YTB_CATEGORY.get(iss.get("category") or "OTHER", "OTHER"), "scope": iss.get("scope") or "",
                        "direction": DIRECTION.get(iss.get("stance"), "neutral"), "surprise": iss.get("surprise") == "surprise",
                        "tickers": [_ticker(t) for t in iss.get("tickers") or []], "country": iss.get("country") or "",
                        "channel": MC.CHANNEL_SHORT.get(ch, ch), "url": it.get("url"), "group": channel_groups().get(it.get("channelId"), "main"),
                        "published_at": pub.isoformat() if hasattr(pub, "isoformat") else str(pub or "")})
    return out


def _groups_of(sym):
    g = {c[3] for c in UNI.CANDIDATES if c[0] == sym}
    g |= {nm for nm, syms in UNI.WATCH if sym in syms}
    return g | {old for old, news in getattr(UNI, "WATCH_ALIAS", {}).items() if g & set(news)}   # 옛 묶음 이름(`반도체`)도 — 새 네 묶음 종목이 반도체 이슈를 받게 (2026-11-19)


def _members(group):
    names = [group] + getattr(UNI, "WATCH_ALIAS", {}).get(group, [])
    return {c[0] for c in UNI.CANDIDATES if c[3] == group} | {x for nm, syms in UNI.WATCH if nm in names for x in syms}


def sector_groups(r):
    """업종 이슈가 가리키는 묶음 이름들."""
    topics = r.get("topics", [r["topic"]])   # 묶인 주제 전부 — '사이버 보안 섹터 M&A / 소프트웨어 섹터 M&A' 는 대표 주제만 보면 놓친다 (2026-10-30)
    hit = {g for w, g in SECTOR_WORDS if any(w in t for t in topics)}
    if not hit:
        from collections import Counter
        cnt = Counter(g for t in set(r["tickers"]) for g in _groups_of(t))
        hit = {g for g, n in cnt.items() if n >= 2}   # 종목 하나의 업종 칸만으로 넓히지 않는다 (테슬라 → `소비 · 플랫폼` 전체 X)
    if not hit:
        hit = set(SECTOR_CATEGORY.get(r["category"], ()))
    return hit


def stocks_for(r):
    """이 이슈를 보일 종목 페이지들 — 종목 이슈는 중심 종목(들), 업종 이슈는 그 묶음 종목 전부 + 이슈에 적힌 종목(페이지가 있는 것). 시장 이슈는 없음.
    업종 이슈에 적힌 종목도 넣는다."""
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


def is_korea(r):
    """한국 증시 내용인가 — **채널이 아니라 이슈 내용으로**. 수집기가 이슈마다 적는 주된 국가(country)로:
    KR 이면 한국, 다른 나라면 미국 쪽(단, 종목 이슈의 중심 종목이 한국 종목이면 한국), 비어 있으면(10-22~30 기록 3%) 채널 묶음(한국 증시 채널 = kr)으로 보조.
    10-22~30 기록: 혼합 채널 증시각도기 34건이 US 22 · KR 9 로 갈리고 KR 9건은 실제 한국 시황(국내 증시 급락 · 원달러 환율 · 증안펀드). 한국 종목이 붙었지만 국가가 미국인 11건
    (애플 폴더블 아이폰에 삼성전자)은 미국 시장 이야기로 — 그 종목 페이지에는 kr_stocks_for 가 따로 싣는다."""
    if r["country"] == "KR":
        return True
    if r["country"]:
        leads = r.get("leads", r["tickers"][:1])   # 중심 종목이 모두 한국 종목일 때만 — '3분기 실적 호조' 처럼 여러 회사가 한 이슈로 묶이면(낱말 비교 한계) SK하이닉스 하나로 전체를 한국으로 보내지 않게
        return r["scope"] == "stock" and bool(leads) and all(kr_code(t) for t in leads)
    return "kr" in (r.get("groups") or [r.get("group")])


def us_to_kr(iss, n=None):
    """미국 증시 리포트 `한국장` 탭 — 미국(한국 아닌) 이야기인데 한국 종목이 걸린 이슈.
    예: 애플 폴더블 아이폰 → 삼성전자, 마이크론 실적 → SK하이닉스. 한국 증시 이야기(is_korea)는 한국 증시 리포트에만."""
    out = [r for r in iss if r["category"] != "OTHER" and not is_korea(r) and any(kr_code(t) for t in r["tickers"])]
    out = sorted(out, key=lambda r: str(r["published_at"]), reverse=True)
    return out[:n] if n else out


def korea(iss, n=6):
    """한국장에 영향을 줄 만한 소식 — country=KR 이거나 한국 종목('(KR)')이 붙은 이슈, 최근 순 n 개 (media-daily cluster.korea_links 와 같은 기준).
: 미국 데일리 `한국장` 탭으로. iss = issues() 결과."""
    out = [r for r in iss if r["category"] != "OTHER" and is_korea(r)]   # 채널이 아니라 내용으로 — 옛: (KR) 종목이 붙으면 전부 · 한국 채널 이슈는 전부
    return sorted(out, key=lambda r: str(r["published_at"]), reverse=True)[:n]


def kr_label(r):
    """한국장 소식 줄 라벨 = 분야 이름 (P339). 옛: 연결된 한국 종목 이름, 없으면 분야 (2026-10-23)."""
    return issue_codes.ISSUE_KO.get(r["category"], "그 밖")


# ---------------------------------------------------------------- 한국 종목 페이지

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
                   ("은행", "금융"), ("금융", "금융"), ("보험", "금융"), ("자동차", "경기 소비재"),
                   # 2차 보강: 데이터 센터 · AI 인프라 수요는 HBM → 반도체 테마, 전력 → 한국전력, 전기차 → 2차전지 + 완성차, 통신 · 인터넷 · 플랫폼 → NAVER · 카카오 · SKT
                   ("데이터 센터", "반도체"), ("데이터센터", "반도체"), ("AI 인프라", "반도체"), ("D램", "반도체"), ("DRAM", "반도체"), ("낸드", "반도체"),
                   ("파운드리", "반도체"), ("GPU", "반도체"), ("AI 칩", "반도체"),
                   ("전기차", "2차전지"), ("전기차", "경기 소비재"), ("양극재", "2차전지"), ("ESS", "2차전지"), ("리튬", "2차전지"),
                   ("전력", "유틸리티"), ("전기요금", "유틸리티"), ("전력망", "유틸리티"), ("원전", "유틸리티"),
                   ("철강", "소재"), ("화학", "소재"), ("아연", "소재"), ("석유화학", "소재"),
                   ("증권", "금융"), ("지주사", "금융"), ("통신", "커뮤니케이션"), ("인터넷", "커뮤니케이션"), ("플랫폼", "커뮤니케이션"),
                   ("의약품", "바이오"), ("신약", "바이오"), ("CDMO", "바이오"), ("치료제", "바이오"), ("백신", "바이오"),
                   ("국방", "방산 · 조선 · 원전"), ("해양플랜트", "방산 · 조선 · 원전"), ("가전", "기술"), ("스마트폰", "기술"), ("디스플레이", "기술")]


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
        korean = is_korea(r) or bool(codes)
        if not korean:   # 미국 은행 · 바이오 뉴스가 한국 금융 · 바이오 전부에 붙지 않게 — 세계 공통 업종(반도체 · 2차전지)만 미국 이야기도 받는다
            groups &= KR_GLOBAL_GROUPS
        return set().union(set(codes), *(_kr_members(g) for g in groups))
    return set()


def for_kr_page(iss, code):
    """한국 종목 페이지 하나에 보일 방송 이슈."""
    return [r for r in iss if code in kr_stocks_for(r)]


def market(rs):
    """시장 전체 · 업종 이슈 (미국 데일리 뉴스 · 홈 주요 뉴스로). 한국 증시 내용(is_korea)은 빼고 한국장 탭(korea) · 한국 증시 리포트로 — 채널이 아니라 내용으로 가른다.
"""
    return [r for r in rs if r["scope"] in ("market", "sector") and not is_korea(r)]


# 같은 이슈 묶기 — media-daily/cluster.py _similar 와 같은 규칙(분류가 같고 주제 낱말이 겹치면). 그 파일은 media-daily 의 config 를 읽어 여기서 부르지 않는다
_WORD = re.compile(r"[가-힣A-Za-z0-9]{2,}")
_STOP = {"기대", "전망", "우려", "논쟁", "강세", "약세", "상승", "하락", "증가", "감소", "영향", "관련", "지속", "확대", "축소", "가능성", "발표", "소식", "실적", "분기", "1분기", "2분기", "3분기", "4분기", "주가", "시장", "및", "AI", "ai", "성장", "투자", "급증", "흑자", "적자"}
# 데일리 뉴스 라벨(daily-report THEME_VOCAB) — 홈도 같은 이름
THEME = dict(issue_codes.ISSUE_KO)   # 분야 라벨 · 칩 — 옛: 8개로 뭉갬(거시경제 · 정책/규제 …)


def _words(t):
    return {w.lower() for w in _WORD.findall(str(t or "")) if w not in _STOP}


def _same(a, b):
    if a["category"] != b["category"]:
        return False
    wa, wb = _words(a["topic"]), _words(b["topic"])
    return bool(wa and wb and len(wa & wb) >= max(1, min(2, min(len(wa), len(wb)) // 2)))


def issues(rs, since=""):
    """**한 곳에서 먼저 정리** — 영상 × 이슈 줄을 같은 이슈끼리 하나로 합친다.
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
                        split=len({r["direction"] for r in g} - {"neutral"}) > 1,   # 긍정 · 부정이 같이 있음 → `엇갈림` 라벨 (미디어 데일리 순위 글에서 옮겨 옴, 2026-10-30)
                        n_channels=len({r["channel"] for r in g}), n_videos=len(g), groups=sorted({r.get("group", "main") for r in g}),
                        channels=[c for c, _ in Counter(r["channel"] for r in g).most_common()], theme=THEME.get(rep["category"], "기타")))
    return out


PICK_ACTION = {"buy": "매수", "hold": "보유", "watch": "관망", "sell": "매도"}
# 종목 의견의 티커 바로잡기.
# 수집기 요약이 티커를 비우거나(스페이스X 4건) 옛 이름(SPACEX · BRK.B)으로 적는다 — 뉴스 줄(rows)처럼 ALIAS 를 쓰고, 비었으면 종목 이름으로 찾는다.
_US_BY_NAME = {re.sub(r"\s+", "", n).lower(): t for t, n, *_ in UNI.CANDIDATES}


def _pick_ticker(p):
    t = _ticker(p.get("ticker") or "")
    if not t and str(p.get("market") or "").upper() == "US":
        t = _US_BY_NAME.get(re.sub(r"\s+", "", str(p.get("name") or "")).lower(), "")
    return t


def _as_utc(s):
    """ISO 문자열 → UTC 시각 (끝의 Z · 시간대 없음은 UTC 로). 못 읽으면 None."""
    try:
        t = datetime.datetime.fromisoformat(str(s).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.replace(tzinfo=datetime.timezone.utc) if t.tzinfo is None else t.astimezone(datetime.timezone.utc)


def picks(items, since=""):
    """방송에서 나온 종목 의견 — 수집기 요약의 `picks` 칸을 그대로 옮긴다.
    한 줄 = {market · ticker · name · action(매수 · 보유 · 관망 · 매도) · speaker · own(본인 의견) / report(증권사 보고서를 방송이 전함) · target · currency ·
    reason · quote · channel · url(그 장면 시각) · published_at}. 같은 영상 · 같은 사람 · 같은 종목은 한 줄. since = 'YYYY-MM-DD' 이후 영상만."""
    out, seen = [], set()
    cut = _as_utc(since) if since and len(since) > 10 else None   # 시각까지 주면 시각으로 자른다 — 방송 의견 5일
    for it in sorted(items, key=lambda r: str(r.get("publishedAt") or ""), reverse=True):
        pub = it.get("publishedAt")
        pub = pub.isoformat() if hasattr(pub, "isoformat") else str(pub or "")
        if cut is not None:
            t = _as_utc(pub)
            if t is None or t < cut:
                continue
        elif pub[:10] < since:
            continue
        ch = it.get("channelName") or ""
        for p in it.get("picks") or []:
            t = _pick_ticker(p)
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
                        "channel": MC.CHANNEL_SHORT.get(ch, ch), "url": url, "published_at": pub, "at_sec": p.get("atSec")})   # at_sec = 영상 속 발언 시각 (P200)
    return out


def diag(vids, iss, tag="[media_feed 진단]"):
    """재료가 어디로 가는지 로그 한 묶음.
    영상의 채널 묶음(kr · main · required) · 묶음별 이슈 범위(시장 · 업종 · 종목) · 한국 종목별 배정 수 · 코드로 못 바꾼 한국 표기. 출력만 하고 아무것도 바꾸지 않는다."""
    gmap = channel_groups()
    vg = Counter(gmap.get(v.get("channelId"), "main") for v in vids)
    print(f"{tag} 영상 {len(vids)}개 — 채널 묶음별 {dict(vg)} · 채널 {dict(Counter(MC.CHANNEL_SHORT.get(v.get('channelName'), v.get('channelName')) for v in vids).most_common(12))}")
    for g in sorted({x for r in iss for x in r["groups"]}):
        sub = [r for r in iss if g in r["groups"]]
        print(f"{tag} 묶음 {g}: 이슈 {len(sub)} · 범위 {dict(Counter(r['scope'] or '-' for r in sub))} · 한국 증시 내용 {sum(1 for r in sub if is_korea(r))} (국가 KR {sum(1 for r in sub if r['country'] == 'KR')} · 국가 비어 있음 {sum(1 for r in sub if not r['country'])})"
              f" · 한국 종목 페이지에 닿는 이슈 {sum(1 for r in sub if kr_stocks_for(r))} · 미국 종목 페이지 {sum(1 for r in sub if stocks_for(r))}")
    per = Counter(KR_CODE.get(c, c) for r in iss for c in kr_stocks_for(r))
    print(f"{tag} 한국 종목별 배정: " + (" · ".join(f"{k} {v}" for k, v in per.most_common()) or "없음"))
    bad = Counter(t for r in iss for t in r["tickers"] if ("(KR)" in t or re.search(r"[가-힣]", t)) and not kr_code(t))
    if bad:
        print(f"{tag} 코드로 못 바꾼 한국 표기: {dict(bad.most_common(15))}")
    kr_only = [r for r in iss if is_korea(r) and not kr_stocks_for(r)]
    for r in kr_only[:12]:   # 한국 증시 내용인데 종목 페이지로 안 가는 것(시장 이슈는 정상 — 한국장 탭 · 한국 증시 리포트 몫) — 범위 · 종목 · 주제
        print(f"{tag}   한국 내용 · 종목 페이지 미배정: {r['scope'] or '-'} {r['category']} {r['country'] or '-'} {r['tickers'][:4]} | {r['topic'][:50]}")


def market_top(iss, n):
    """시장 · 업종 이슈 중 방송 여러 곳이 같이 다룬 순으로 n 개 — 미국 데일리 뉴스 · 홈 주요 뉴스. iss = issues() 결과."""
    out = [r for r in market(iss) if r["category"] != "OTHER"]
    out.sort(key=lambda r: str(r["published_at"]), reverse=True)
    out.sort(key=lambda r: (-r["n_channels"], -r["n_videos"]))   # 방송 수 → 영상 수 → 최근
    return out[:n]


def direction_counts(iss):
    """뉴스 방향 막대 재료 {positive · negative · uncertain · neutral: 건수} — 방송 이슈 한 줄 = 1건, 긍정 · 부정이 섞인 `엇갈림` 은 불확실로 (P143)."""
    out = {}
    for r in iss:
        d = "uncertain" if r.get("split") else r.get("direction") if r.get("direction") in ("positive", "negative") else "neutral"
        out[d] = out.get(d, 0) + 1
    return out


def kr_related(r, prices):
    """방송 이슈의 한국 종목 → [(이름, 그날 등락%)] — prices = {코드: (이름, 등락)} (P355)."""
    out = []
    for t in r.get("tickers") or []:
        c = kr_code(t)
        if c and c in prices and all(c != x for x, _ in out):
            out.append((c, prices[c]))
    return [(nm, v) for _, (nm, v) in out]


def event(r, n_all=0, prices=None):
    """종목 페이지 · 엔비디아 리포트 뉴스 목록 한 줄 (nvda-report judge._ev 모양). 헤드라인 = 방송 주제, 요약 줄 = 방송 주장(note), 매체 자리 = 채널, 라벨 = 영역 · 방향 · 방송.
    has_fact=False · media=True — 중요 이슈(사실 문장) · AI 서술 입력에는 넣지 않는다 (의견이 섞여 있다)."""
    return {"area": AREA.get(r["category"], "Other"), "kind": "news", "title": r["topic"], "fact": r["topic"], "detail": r["note"], "url": r["url"],
            "direction": "uncertain" if r.get("split") else r["direction"], "emphasis": False, "published_at": r["published_at"],
            "source": r["channel"] + (f" · 방송 {r['n_channels']}곳" if r.get("n_channels", 1) > 1 and not n_all else ""), "n_all": n_all,   # 분모를 알면 칸 막대(P338), 모르면 옛 글씨
            "speaker": LABEL, "media": True, "has_fact": False, "rel": 0, "prio": False,
            "issue": r.get("category"), "related": kr_related(r, prices) if prices else [], "pop_lines": r.get("lines") or [], "n_channels": r.get("n_channels", 1), "channel": r["channel"], "pop_key": r.get("id") or r["url"]}   # 요약 팝업 재료 (2026-11-07 P337)


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
