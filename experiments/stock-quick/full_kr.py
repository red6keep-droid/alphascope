"""간단 정보(한국) = 한국 정식 종목 렌더러 그대로.

full_us.py 와 같은 원칙 — 정식 계산(analyze_kr) · 정식 카드(render_kr)를 그대로 부르고, 막히는 줄(방송 뉴스 · 방송 의견 · 미국과 연결 짝)만 뺀다.
11-12 목업(mock_quick.page_kr_full)과 같은 화면을 853종목 매일 실행으로.
  - 탭 = 오늘 · 매수의견(애널리스트 — 값이 있을 때만) · 실적(분기 매출 · 이익 예상 · 돈을 어디에 쓰나 + 시장 일정) · 업계상황 · 기업.
  - 실적 탭 일정 = 정식과 같은 세 카드: 다음 실적 발표는?(DART 잠정실적 1년 전 같은 분기로 어림 `무렵` — 예정일을 미리 알리는 회사가 드물다, 기획 6-3-2 ⑥)
    · 미국 연관 종목 일정은?(검증 통과 짝만, Finnhub 달력은 미국 간단 실행 것) · 시장 전체를 흔들 일정은?.
  - 함께 움직이는 종목 = 같은 업종에서 1년 등락이 가장 비슷하게 움직인 3곳(상관 계산, full_us.corr_peers). 정식의 `미국과 연결`(검증한 짝)은 빌려 오지 않는다.
  - 업계 카드 = 업종 원자료(로고 메타데이터 industry_en)가 분명한 업종만 정식 대표 종목의 업계 자료로 잇는다(IND_REP). 원자료가 틀린 종목은 KR_FIX.
재료 (AI 0 · Blogger 0 · 그림 0):
  - 일봉 2년(collect_kr._bars) — 간단 종목 + 코스피 · 코스닥 · 업종 ETF.
  - 자금 흐름 · 업계 통계(flows.json) · 정식 종목 시총 · 이익 예상 · DART 매출(비교 묶음 `시총 상위 20개`) = 한국 정식 실행 상태(kr-state)를 읽기만.
  - 분기 매출 · 손익 · 현금흐름(DART) · 기업개황(DART) · 애널리스트 · 이익 예상(야후) = 간단 종목 몫은 cache_dir 에 따로, 하루 BUDGET 종목까지.
  - 고점 회복 통계(1999~, 코스피 대비) = 7일 · 하루 BUDGET.
"""

import datetime
import json
import os
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
KRD = os.path.join(EXP, "kr-stocks")
sys.path[:0] = [EXP, KRD, os.path.join(EXP, "nvda-report"), os.path.join(EXP, "daily-report"), HERE]

import design_kit as dk  # noqa: E402
import candle_chart as CC  # noqa: E402
import detail_cache as DC  # noqa: E402
import universe_kr as K  # noqa: E402
import analyze_kr  # noqa: E402
import render_kr  # noqa: E402
import collect_kr_dart as D  # noqa: E402
import collect_kr_fin as FIN  # noqa: E402
import full_us  # noqa: E402

R = render_kr.R
WHEN = full_us.WHEN_KR   # 시장마다 따로 (2026-11-24 — 옛 미국 · 한국 모두 `오후 5시 40분`)
LATE_DAY = None   # full_us.LATE_DAY 와 같은 뜻 — 한국 종목 날짜 (collect_quick 이 넣는다)
BUDGET = {"detail": 60, "dart": int(os.environ.get("QUICK_DART_BUDGET") or 40), "company": 60, "hist": 100}
DART_MINUTES = int(os.environ.get("QUICK_DART_MINUTES") or 20)   # 매출 · 손익 받기 시간 상한 — DART 가 느린 날에도 실행이 끝나 저장값을 남기게 (2026-11-16)
# 화면 실행(장 마감 뒤)은 DART 를 새로 받지 않고 저장값만.
# 받기는 새벽 실행(quick-dart.yml → dart_fill.py)이 하고 같은 quick-state 에 남긴다. QUICK_DART_FETCH=0 = 받지 않음
DART_FETCH = os.environ.get("QUICK_DART_FETCH", "1") != "0"
DETAIL_FIELDS = ("analysts", "eps")
MARKET = sorted({K.BENCH, K.KOSDAQ, *K.SECTOR_ETF_LIST})


def _links():
    """미국 연결 종목 — AI 후보 · 짝 하나씩 검증 통과만. {한국 코드: [기록]}, 차이 큰 순."""
    try:
        d = json.load(open(os.path.join(EXP, "ref", "kr_us_links.json"), encoding="utf-8"))["links"]
    except (OSError, ValueError, KeyError):
        return {}
    return {k: sorted((r for r in e.get("tested") or [] if r.get("pass")), key=lambda r: -(r.get("spread1") or 0)) for k, e in d.items() if e.get("pass")}


LINKS = _links()
LINK_US = sorted({r["t"] for rows in LINKS.values() for r in rows})
US_KO = {s: e.get("ko") or s for s, e in (full_us._load(os.path.join(EXP, "ref", "quick_ref.json"), {}).get("us") or {}).items()}

# 업종 원자료(industry_en) → 업계 자료를 빌려 올 한국 정식 종목. 그 업종 종목 대부분에 맞는 것만 (2026-11-14 Claude) — 나머지는 업계 카드 없이
IND_REP = {
    "Semiconductors": "000660.KS",
    "Pharmaceuticals: Major": "068270.KS", "Biotechnology": "196170.KQ",
    "Major Banks": "105560.KS", "Regional Banks": "105560.KS",
    "Multi-Line Insurance": "000810.KS", "Property/Casualty Insurance": "000810.KS", "Life/Health Insurance": "032830.KS",
    "Auto Parts: OEM": "005380.KS", "Automotive Aftermarket": "005380.KS",
    "Homebuilding": "028260.KS", "Engineering & Construction": "028260.KS",
    "Steel": "005490.KS",
    "Major Telecommunications": "017670.KS",
    "Aerospace & Defense": "064350.KS",
    "Packaged Software": "035420.KS", "Internet Software/Services": "035420.KS",
}
# 종목 하나씩 — 원자료 업종이 틀렸거나 한 업종에 다른 사업이 섞인 것 (코드: 대표 종목, None = 업계 카드 없음)
KR_FIX = {
    "009830": None,          # 한화솔루션 — 원자료 `반도체`, 실제는 화학 · 태양광
    "009150": None,          # 삼성전기 — 원자료 `반도체`, 실제는 전자 부품(적층세라믹콘덴서 · 기판)
    "010140": "009540.KS",   # 삼성중공업 — 원자료 `건설 기계`, 실제는 조선
    "082740": "009540.KS",   # 한화엔진 — 선박 엔진
    "071970": "009540.KS",   # HD현대마린엔진 — 선박 엔진
    "443060": "009540.KS",   # HD현대마린솔루션 — 원자료 `도매 유통`, 실제는 선박 서비스
}


# 업계 카드가 실제 사업과 맞지 않는 종목 — 대표 종목도 큰 업종 대체도 쓰지 않는다.
# 업종 고침(큰 업종 · 세부 업종)은 build_ref.py 가 같은 파일로 quick_ref.json 에 넣는다
try:
    _FIX = json.load(open(os.path.join(EXP, "ref", "kr_industry_fix.json"), encoding="utf-8"))
except (OSError, ValueError):
    _FIX = {}
CARD_OFF = set(_FIX.get("card_off") or {})
# 종목마다 고른 사업 묶음 → 그 묶음의 업계 자료를 빌려 올 정식 종목. 원자료 업종의 대표 종목이 같은 묶음이면 그것을 그대로(생보 · 손보 구분 등)
CARD = {c: x["group"] for c, x in (_FIX.get("card") or {}).items()}
GROUP_REP = {"반도체": "000660.KS", "가전": "066570.KS", "2차전지": "373220.KS", "자동차": "005380.KS", "바이오": "068270.KS",
             "은행": "105560.KS", "보험": "000810.KS", "플랫폼": "035420.KS", "통신": "017670.KS", "조선": "009540.KS",
             "방산": "064350.KS", "원전 · 발전설비": "034020.KS", "건설": "028260.KS", "철강": "005490.KS", "비철금속": "010130.KS", "전력": "015760.KS"}


def code_of(sym):
    return sym.split(".")[0]


def rep_of(sym, e):
    c = code_of(sym)
    if c in CARD:
        old = IND_REP.get(e.get("industry_en"))
        return old if old and K.BIZ_OF.get(code_of(old)) == CARD[c] else GROUP_REP.get(CARD[c])   # 정식 종목이 없는 묶음(전력기기 · 전선) = None, build 가 지표만 잇는다
    if c in CARD_OFF:
        return None
    if c in KR_FIX:
        return KR_FIX[c]
    return IND_REP.get(e.get("industry_en"))


def alias(rep, sym):
    """대표 종목의 업계 칸을 이 종목에 잇는다 — 업종 ETF · 업계 통계 · 사업 묶음만. 미국과 연결 짝(PAIRS)은 빌리지 않는다(그 종목에서 검증한 것)."""
    if rep in K.SECTOR_ETF:
        K.SECTOR_ETF[sym] = K.SECTOR_ETF[rep]
    for n in ("BSI_INDUSTRY", "FIN_INDUSTRY", "LOAN_INDUSTRY"):
        for _code, (_name, syms) in getattr(K, n).items():
            if rep in syms and sym not in syms:
                syms.append(sym)
    if code_of(rep) in K.BIZ_OF:
        K.BIZ_OF[code_of(sym)] = K.BIZ_OF[code_of(rep)]


# ---------------------------------------------------------------- 재료

_load, _save = full_us._load, full_us._save


def bars(syms):
    import collect_kr
    out = {}
    allsyms = list(dict.fromkeys(list(syms) + MARKET + LINK_US))   # 미국 연결 종목 — 밤사이 움직임 (약 60종목, 묶음 하나)
    for i in range(0, len(allsyms), 100):
        try:
            out.update(collect_kr._bars(allsyms[i:i + 100]))
        except Exception as e:  # noqa: BLE001
            print(f"[quick-kr] 일봉 묶음 {i} 실패: {str(e)[:120]}")
        time.sleep(2)
    # 마지막 봉 대조 겸 값 = 네이버 — 정식 한국 종목과 같은 함수 (2026-11-23). 네이버도 못 받은 종목만 KIS_NEED_OUT 파일로 →
    # quick-data.yml 이 수집 뒤 그 종목만 한국투자증권으로 확인
    return collect_kr._fix_last(out)


def details(cache_dir, syms):
    """애널리스트 · 이익 예상 — 한국 정식(collect_kr_extra)과 같은 함수 · 같은 주기, 하루 BUDGET. 비어 온 칸은 7일 뒤 다시."""
    import collect_kr_extra as KX
    import yfinance as yf
    cache = DC.DetailCache(os.path.join(cache_dir, "kr"))
    tried = cache.blobs.get("tried", {}).get("v") or {}
    today = cache.today.isoformat()
    plan = []
    for s in syms:
        due = []
        for f in DETAIL_FIELDS:
            t = (tried.get(s) or {}).get(f)
            if cache.get(s, f) is None and t and (cache.today - datetime.date.fromisoformat(t)).days < full_us.RETRY_EMPTY:
                continue
            if cache.due(s, f):
                due.append(f)
        if due:
            plan.append((sum(1 for f in DETAIL_FIELDS if cache.get(s, f) is not None), zlib.crc32(s.encode()), s, tuple(due)))
    plan.sort()
    jobs = plan[:BUDGET["detail"]]
    for _, _, s, due in jobs:
        t = yf.Ticker(s)
        fn = {"analysts": lambda: KX._analysts(t), "eps": lambda: KX.EX._eps(t)}
        for f in due:
            try:
                v = fn[f]()
            except Exception as e:  # noqa: BLE001
                print(f"[quick-kr] {s} {f} 실패: {str(e)[:80]}")
                v = None
            if not cache.put(s, f, v):
                tried.setdefault(s, {})[f] = today
        time.sleep(0.5)   # 정식 한국 수집과 같은 간격
    cache.blobs["tried"] = {"v": tried, "day": today}
    cache.save("간단 정보 한국")
    print(f"[quick-kr] 상세 값 새로 받은 종목 {len(jobs)} · 남은 대기 {len(plan) - len(jobs)}")
    return {s: {f: cache.get(s, f) for f in DETAIL_FIELDS} for s in syms}


def rev_rows(cache, codes, syms):
    """DART 주요계정 캐시 → {sym: [{end, rev, cq, yoy, src}]} — collect_kr_dart.run 의 뒷부분과 같은 셈(받기 없이)."""
    today = datetime.date.today()
    out = {}
    for sym in syms:
        mine = cache.get(codes.get(code_of(sym)) or "", {})
        rows = []
        for year in range(today.year - D.YEARS + 1, today.year + 1):
            q = {rc: mine.get(f"{year}-{rc}") or {} for rc, _ in D.REPORTS}
            for i, (rc, mmdd) in enumerate(D.REPORTS):
                rev = q[rc].get("rev")
                if rc == "11011":
                    q3 = q["11014"].get("add")
                    rev = rev - q3 if rev is not None and q3 is not None else None
                if rev is not None:
                    rows.append({"end": f"{year}-{mmdd}", "rev": rev, "cq": f"{year}Q{i + 1}", "src": "dart"})
        by = {r["cq"]: r["rev"] for r in rows}
        for r in rows:
            prev = by.get(f"{int(r['cq'][:4]) - 1}{r['cq'][4:]}")
            r["yoy"] = (r["rev"] / prev - 1) * 100 if prev else None
        if rows:
            out[sym] = rows
    return out


def dart(cache_dir, syms):
    """간단 종목 DART — 회사 번호(한 달 한 번) · 분기 매출 · 손익 · 현금흐름(이미 받은 보고서는 다시 안 받음) · 기업개황(90일). 하루 BUDGET 회사."""
    key = D._key()
    keep = (D.CORP, D.CACHE, D.COMPANY, FIN.CACHE, list(K.CANDIDATES))
    D.CORP, D.CACHE = os.path.join(cache_dir, "kr", "dart_corp.json"), os.path.join(cache_dir, "kr", "dart_fin.json")
    D.COMPANY, FIN.CACHE = os.path.join(cache_dir, "kr", "dart_company.json"), os.path.join(cache_dir, "kr", "dart_fin_all.json")
    try:
        K.CANDIDATES[:] = [(s, "", "", "", []) for s in syms]
        codes = D.corp_codes(key) if key else (_load(D.CORP, {}) or {}).get("map") or {}
        prog = _load(os.path.join(cache_dir, "kr", "dart_done.json"), {})   # 회사마다 마지막으로 살핀 날 — 하루 BUDGET 을 오래된 것부터
        today = datetime.date.today()
        todo = sorted((s for s in syms if code_of(s) in codes and (not prog.get(s) or (today - datetime.date.fromisoformat(prog[s])).days >= 7)),
                      key=lambda s: prog.get(s) or "")[:BUDGET["dart"]]
        if not DART_FETCH:
            todo = []   # 화면 실행 — 새벽 실행이 받아 둔 저장값만
        if key and todo:
            # 5곳씩 나눠 받고 DART_MINUTES 를 넘기면 남은 회사는 다음 실행에 — 11-16 DART 가 느려(손익 표 호출당 약 6초, 11-14 의 3~4배)
            # 40곳에 83분이 걸려 실행 전체가 상한에 취소됐고, 취소된 실행은 저장값을 못 남겨 다음 실행이 같은 일을 처음부터 했다 (2026-11-16)
            t0, done = time.time(), []
            for i in range(0, len(todo), 5):
                if time.time() - t0 > DART_MINUTES * 60:
                    print(f"[quick-kr] DART {DART_MINUTES}분 넘음 — {len(todo) - len(done)}곳은 다음 실행에", flush=True)
                    break
                part = todo[i:i + 5]
                K.CANDIDATES[:] = [(s, "", "", "", []) for s in part]
                try:
                    D.run()     # 매출 — 새 보고서만 (회사마다 저장)
                    FIN.run()   # 손익 · 현금흐름 — 새 보고서만
                except Exception as e:  # noqa: BLE001
                    print(f"[quick-kr] DART 실패 — 지난 값: {str(e)[:120]}")
                done += part
            for s in done:
                prog[s] = str(today)
            _save(os.path.join(cache_dir, "kr", "dart_done.json"), prog)
            todo = done
        K.CANDIDATES[:] = [(s, "", "", "", []) for s in syms]
        rev = rev_rows(_load(D.CACHE, {}), codes, syms)
        _k = D._key
        D._key = lambda: ""   # 손익 표는 받기 없이 캐시로만 (FIN.run 이 키가 없으면 캐시를 읽는다)
        try:
            cash = FIN.run()
        finally:
            D._key = _k
        comp = _load(D.COMPANY, {"map": {}, "day": {}})
        comp.setdefault("day", {})
        old = sorted((s for s in syms if code_of(s) in codes and (not comp["day"].get(code_of(s)) or (today - datetime.date.fromisoformat(comp["day"][code_of(s)])).days >= 90)),
                     key=lambda s: comp["day"].get(code_of(s)) or "")[:BUDGET["company"]]
        if key and old and DART_FETCH:
            import requests
            for s in old:
                c = code_of(s)
                try:
                    r = requests.get(f"{D.API}/company.json", params={"crtfc_key": key, "corp_code": codes[c]}, timeout=30).json()
                    if r.get("status") == "000":
                        comp["map"][c] = {k: (r.get(k) or "").strip() for k in D.COMPANY_KEYS}
                    comp["day"][c] = str(today)
                except Exception as e:  # noqa: BLE001
                    print(f"[quick-kr] {c} 기업개황 실패: {str(e)[:80]}")
                time.sleep(0.2)
            _save(D.COMPANY, comp)
    finally:
        D.CORP, D.CACHE, D.COMPANY, FIN.CACHE, cands = keep
        K.CANDIDATES[:] = cands
    print(f"[quick-kr] DART 새로 살핀 회사 {len(todo)} · 매출 {len(rev)} · 손익 표 {len(cash)} · 기업개황 {len(comp['map'])}")
    return {"revenue": rev, "capex": cash, "company": comp["map"]}


def history(cache_dir, syms):
    """고점 하락 후 회복 통계 — 한국 정식 collect_kr.history 와 같은 계산(코스피 같은 기간 bench_dd), 7일 · 하루 BUDGET."""
    import yfinance as yf
    import history_stats as HS
    path = os.path.join(cache_dir, "kr", "hist.json")
    c = _load(path, {"stats": {}, "day": {}})
    today = datetime.date.today()
    if c.get("method") != HS.DD_METHOD:   # 사이클 정의가 바뀌면 모든 종목을 다시 받을 차례로 (하루 BUDGET 안에서)
        c["day"], c["method"] = {}, HS.DD_METHOD
    todo = sorted((s for s in syms if not c["day"].get(s) or (today - datetime.date.fromisoformat(c["day"][s])).days >= 7),
                  key=lambda s: (s in c["stats"], c["day"].get(s) or ""))[:BUDGET["hist"]]
    if todo:
        try:
            df = yf.download(todo + [K.BENCH], start="1999-01-01", interval="1d", auto_adjust=False, group_by="ticker", progress=False, threads=3)
            bench = df[K.BENCH]["Close"].dropna()
            for s in todo:
                c["day"][s] = str(today)
                try:
                    cl = df[s]["Close"].dropna()
                except KeyError:
                    continue
                cl = cl[cl > 0]
                if len(cl) < 500:
                    continue
                c["stats"][s] = {"from": cl.index[0].strftime("%Y-%m-%d"), "to": cl.index[-1].strftime("%Y-%m-%d"), "dd": HS.dd_summary(HS.drawdown_cycles(cl)),
                                 "bench_dd": HS.dd_summary(HS.drawdown_cycles(bench[bench.index >= cl.index[0]]))}
            _save(path, c)
        except Exception as e:  # noqa: BLE001
            print(f"[quick-kr] 고점 회복 통계 실패 — 지난 값: {str(e)[:100]}")
    print(f"[quick-kr] 고점 회복 통계 새로 {len(todo)} · 전체 {len(c['stats'])}")
    return {"stats": c["stats"], "bench": K.BENCH}


def earn_kr(cache_dir, ref_kr, syms, key=None):
    """한국 실적 발표일 = DART 잠정실적 첫 공시일 — 정식(collect_kr_earn_dart)과 같은 판정, 간단 종목 몫은 cache_dir/kr/dart_earn.json.
    처음 = 최근 3년(카드는 2년 움직임 · 1년 전 같은 분기로 다음 날짜 어림), 그 뒤 = 회사마다 7일에 한 번, 어림한 다음 발표일 앞 14일 ~ 뒤 3일 안이면 매일.
    정식 종목 몫(kr-state data/dart_earn.json)과 합쳐 렌더러가 쓰는 표(collect_kr_earn_dart._cache)에 넣는다. → 이번에 살핀 회사 수"""
    import collect_kr_earn_dart as KE
    path = os.path.join(cache_dir, "kr", "dart_earn.json")
    c = _load(path, {"days": {}, "checked": {}})
    full = _load(KE.OUT, {"days": {}})
    today = datetime.date.today()
    key = key or KE._key()

    def due(code):
        t = c["checked"].get(code)
        if not t:
            return True
        if (today - datetime.date.fromisoformat(t)).days >= 7:
            return True
        est = [datetime.date.fromisoformat(d) + datetime.timedelta(days=364) for d in c["days"].get(code) or []]
        return t < str(today) and any(-3 <= (e - today).days <= 14 for e in est)

    codes = {code_of(s): ref_kr[s].get("corp") for s in syms if ref_kr.get(s, {}).get("corp")}
    todo = sorted((k for k in codes if due(k)), key=lambda k: c["checked"].get(k) or "")
    n = calls = 0
    if key:
        end = today.strftime("%Y%m%d")
        for code in todo:
            prev = c["days"].get(code) or []
            bgn = ((datetime.date.fromisoformat(prev[-1]) - datetime.timedelta(days=KE.GAP_DAYS)) if prev else today - datetime.timedelta(days=3 * 365)).strftime("%Y%m%d")
            try:
                new = KE.first_prelim(KE.filings(key, codes[code], bgn, end))
            except Exception as e:  # noqa: BLE001 — 이 회사만 다음 실행에
                print(f"[quick-kr] {code} 잠정실적 실패: {str(e)[:80]}")
                continue
            keep = []
            for d in sorted(set(prev) | set(new)):   # 이어 붙일 때 40일 규칙을 다시 (정식 run 과 같다)
                if keep and (datetime.date.fromisoformat(d) - datetime.date.fromisoformat(keep[-1])).days < KE.GAP_DAYS:
                    continue
                keep.append(d)
            c["days"][code], c["checked"][code] = keep, str(today)
            n += 1
        _save(path, c)
    else:
        print("[quick-kr] DART_API_KEY 없음 — 실적일은 지난 값")
    KE._cache = {"days": {**c["days"], **(full.get("days") or {})}}   # 정식 종목은 정식 실행 값이 이긴다
    print(f"[quick-kr] 잠정실적 날짜 살핀 회사 {n} · 날짜 있는 회사 {sum(1 for v in c['days'].values() if v)}/{len(codes)}")
    return n


def full_group():
    """비교 묶음 `시총 상위 20개` 재료 — 한국 정식 실행 상태(kr-stocks/data: detail_cache 시총 · 이익 예상, dart_fin 매출)를 읽기만."""
    data = os.path.join(KRD, "data")
    cache = DC.DetailCache(data)
    full = [c[0] for c in K.CANDIDATES]
    caps = {s: cache.get(s, "caps") for s in full if cache.get(s, "caps")}
    group = set(sorted(caps, key=lambda s: -caps[s])[:K.PEER_GROUP_N])
    codes = (_load(os.path.join(data, "dart_corp.json"), {}) or {}).get("map") or {}
    rev = rev_rows(_load(os.path.join(data, "dart_fin.json"), {}), codes, list(group))
    eps = {s: {"eps": cache.get(s, "eps")} for s in group if cache.get(s, "eps")}
    return group, rev, eps


# ---------------------------------------------------------------- 화면

def pairs_card(s, peers, by):
    """`함께 움직이는 종목은?` — ① 밤사이 미국 연결 종목(검증 통과한 짝이 있을 때만, 정식 한국 `미국과 연결` 과 같은 판정 · 막대)
    ② 같은 업종에서 1년 등락이 가장 비슷한 한국 종목들의 오늘 등락 (미국 간단 정보와 같은 판정 · 같은 막대)."""
    moves = [(p, by[p]) for p in peers if by.get(p) is not None]
    links = s.get("us_links") or []
    if not moves and not links:
        return ""
    day = render_kr._md(s["day"])
    vb = s["tech"].get("vs_bench")
    lines = []
    if links:   # 판정 = 밤사이 미국 (정식 pairs_state 와 같은 말)
        rets = [m["ret"] for m, _ in links]
        ups, downs = sum(1 for x in rets if x >= 0.5), sum(1 for x in rets if x <= -0.5)
        state = "엇갈림" if ups and downs else "올랐음" if ups else "내렸음" if downs else "비슷함"
        us_day = dk.kst_close_day(links[0][0]["day"], "US") + " 새벽"   # 독자 = 한국 시간 (2026-11-14 날짜 규칙) — 미국 종가 = 다음 날 새벽
        lines.append((f"밤사이({us_day} 마감) 미국 연관 종목은 " + ", ".join(f"{US_KO.get(m['sym'], m['sym'])} {render_kr._sgn(m['ret'])}%" for m, _ in links)
                      + f"였고, 오늘 {dk.josa(s['name'], '은')} {render_kr._sgn(s['ret_1d'])}%였다.", "plain"))
        kr = [(s["name"], "", s["ret_1d"], "me")] + ([("KOSPI", "", s["ret_1d"] - vb, "bench")] if vb is not None else [])
        lines.append((R.pair_bars([(f"밤사이 미국 ({us_day})", [(US_KO.get(m["sym"], m["sym"]), why, m["ret"], "us") for m, why in links]),
                                   (f"오늘 한국 ({day})", kr)]), "html"))
    else:
        rets = [r for _, r in moves]
        ups, downs = sum(1 for x in rets if x >= 0.5), sum(1 for x in rets if x <= -0.5)
        state = "엇갈림" if ups and downs else "같이 올랐음" if ups else "같이 내렸음" if downs else "비슷함"
        lines.append((f"오늘({day}) 함께 움직여 온 종목은 " + ", ".join(f"{K.name(p)} {render_kr._sgn(r)}%" for p, r in moves)
                      + f"였고, {dk.josa(s['name'], '은')} {render_kr._sgn(s['ret_1d'])}%였다.", "plain"))
    theme, col = {"엇갈림": ("uncertain", R.SOON), "같이 올랐음": ("positive", R.UP), "같이 내렸음": ("negative", R.DOWN),
                  "올랐음": ("positive", R.UP), "내렸음": ("negative", R.DOWN)}.get(state, ("neutral", R.MUTED))
    if moves:
        rows = [(K.name(p), "", r, "us") for p, r in moves] + ([] if links else [(s["name"], "", s["ret_1d"], "me")] + ([("KOSPI", "", s["ret_1d"] - vb, "bench")] if vb is not None else []))
        lines.append((R.pair_bars([(f"함께 움직여 온 한국 종목 ({day})" if links else f"함께 움직여 온 종목 ({day})", rows)]), "html"))
    if links:   # 연관 종목 기록(고정값) = 미국 페이지와 같은 작은 표
        recs = [(r["t"], US_KO.get(r["t"], r["t"]), ", ".join(x for x in (r.get("why") or "", render_kr.RP.rec_years(r.get("n"))) if x), r["spread1"])
                for r in LINKS.get(s["sym"]) or [] if r["t"] in {m["sym"] for m, _ in links}]
        lines.append((render_kr.RP.link_record_table("미국 연관 종목 기록", recs, theme), "html"))
    R.add_small_note(lines, ("함께 움직여 온 종목은 같은 업종에서 최근 1년 하루 등락률이 가장 비슷한 종목입니다. " if moves else "")
                     + "±0.5% 넘게 움직인 종목만 오른 곳 · 내린 곳으로 셉니다.")
    tip = "미국 연관 종목은 사업으로 이어진 미국 종목 가운데, 그 종목이 크게 움직인 밤 다음 날 이 종목도 같은 쪽으로 열려 온 것만 골랐습니다." if links else ""   # 카드 작은 글씨 → 툴팁
    card = R._state_card("함께 움직이는 종목은?", state, theme, col, lines, "", tip=tip, fold=True)
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{card}</div>'


def sec_expect(s):
    """render_kr.sec_expect 와 같은 카드 — 받지 못한 것은 빼고(빈 답 금지)."""
    ex = s.get("expect") or {}
    out = ""
    spec = (("회사는 돈을 더 벌고 있나?", "revenue", render_kr.RP.card_revenue), (R.EPS_TITLE, "eps", R.card_eps),
            ("돈을 어디에 쓰나?", "capex", lambda c: render_kr.RP.card_capex(c, render_kr.KR_MONEY)))
    for title, key, fn in spec:
        c = ex.get(key)
        if not c:
            continue
        lines, tip = render_kr._rename(fn(c), s["name"])
        tip = tip.replace("SEC EDGAR", "금융감독원 전자공시(OpenDART)").replace("(억 달러)", "(억 원)")
        theme, col = R.EXPECT_THEME.get(c["state"], ("neutral", R.MUTED))
        lines = render_kr.report_head(s, list(lines)) if key == "revenue" else list(lines)   # 잠정실적 숫자 — 정식과 같은 줄
        out += R._state_card(title, c["state"], theme, col, lines, "", tip=tip, fold=True, opened=not out)
    out += render_kr.report_balance_card(s) if out else ""   # 회사 살림은 튼튼한가? — 정식과 같은 카드. 사업 부문 · 수주(AI)는 정식만
    return f'<div data-cards="1" data-grid="cards" style="margin:0 0 8px;">{out}</div>' if out else ""


MEDIA_OK = False   # 방송 자료를 실제로 읽었나 — 읽었을 때만 방송 줄 · 방송 의견(없으면 `없음` 카드). 못 읽었으면 그 칸 없이


def media_inputs():
    """방송 이슈(24시간 · 7일) · 방송 의견(최근 5거래일) — 한국 정식 write_all 과 같은 읽기(읽기 전용 키 YTB_FIRESTORE_KEY, 수집기 Storage feed 파일). AI 0.
    키가 없거나 실패하면 빈 값 = 방송 칸 없이."""
    global MEDIA_OK
    MEDIA_OK = False
    MF = render_kr.media_feed
    render_kr.MEDIA, render_kr.MEDIA_WEEK, render_kr.PICKS = [], [], []
    if not (os.environ.get("YTB_FIRESTORE_KEY") or os.environ.get("MEDIA_FEED_JSON") or os.environ.get("QUICK_MEDIA_LOCAL")):   # QUICK_MEDIA_LOCAL = 목업(PC 의 gcloud 기본 인증으로 읽기)
        print("[quick-kr] 방송 자료 키 없음 — 방송 줄 · 방송 의견 없이")
        return
    try:
        now = render_kr.NOW
        vids = MF.load(now.astimezone(MF.KST).strftime("%Y-%m-%d"), days=render_kr.PICK_DAYS - 1)
        rows = MF.rows(vids)
        render_kr.MEDIA = MF.issues(rows, (now - datetime.timedelta(hours=render_kr.TODAY_HOURS)).strftime("%Y-%m-%dT%H:%M"))
        render_kr.MEDIA_WEEK = MF.issues(rows, (now - datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M"))
        render_kr.PICKS = MF.picks(vids, render_kr.PICK_SINCE)
        MEDIA_OK = True
        print(f"[quick-kr] 방송 영상 {len(vids)} · 이슈 {len(render_kr.MEDIA)} · 종목 의견 {len(render_kr.PICKS)}")
    except Exception as e:  # noqa: BLE001
        print(f"[quick-kr] 방송 자료 실패 — 없이: {str(e)[:100]}")


def opinions_tab(s):
    ps = render_kr._picks(s) if MEDIA_OK else []
    if not s.get("analysts") and not s.get("broker") and not ps:
        return ""
    keep = R.picks_card
    if not MEDIA_OK:
        R.picks_card = full_us._no_picks   # 방송 자료를 못 읽었으면 카드 없이 — 읽었는데 없으면 정식처럼 `없음` 카드
    try:
        closes = [b["close"] for b in (render_kr.BARS.get(s["sym"]) or [])[-R.PICK_SHOW_DAYS:]]
        return R.opinions_cards(s["name"], s.get("analysts") or [], s.get("close"), ps if MEDIA_OK else None, render_kr.won, lambda: render_kr.together_items(s),
                                m0=render_kr.man_won, m2=render_kr.won, closes=closes, broker=s.get("broker"))   # 증권사 목표가(텔레그램, 2026-11-14)
    finally:
        R.picks_card = keep


def body(s, a, peers, by, related_links, extra_today=""):
    today = (R.day_path_chart(s["tech"].get("path"), s["tech"].get("bench_path"), s["name"], "KOSPI") + render_kr.price_card(s) + render_kr.sec_regime(s)
             + render_kr.sec_tech(s) + pairs_card(s, peers, by) + render_kr.sec_states(s) + extra_today)
    op = opinions_tab(s)
    cal = render_kr.sec_calendar(s, ("earnings", "peers", "macro"), open_first=False)   # 정식과 같은 세 카드
    ex = sec_expect(s)
    ea = ex + (R.group_title("주요 일정") + cal if cal else "")
    title = f"{s['name']} 주가"
    return dk.link_page(_body(s, today, op, ea, title, related_links), {"s": s, "peers": peers}, own=s["sym"], where=s["sym"])   # 비교 종목 이름 → 그 종목 페이지 (정식 detail_body 와 같게)


def _body(s, today, op, ea, title, related_links):
    return render_kr.wrap(f'<div data-quick-title="{dk.esc(title)}"><span data-kr-code="{s["code"]}" hidden></span>'
            + dk.report_stamp(dk.kst_close_day(s["day"], "KR"), WHEN, late=bool(LATE_DAY) and str(s["day"])[:10] < LATE_DAY)
            + render_kr.lead(s) + CC.card(s["name"], render_kr.BARS.get(s["sym"]) or [], 0, title="") + CC.chart_talk.block(render_kr.BARS.get(s["sym"]) or [], s["name"], "kr") + CC.kr_live(s.get("code")) + '<div style="height:20px;"></div>'   # 봉차트 하나만 — 정식 page_block 은 목업 · 발행 두 벌 + 스크립트(조각엔 페이지 본문 스크립트 하나로)
            + R._section("오늘", today, line=False, tab="오늘") + render_kr.RP.sec_crash(s)   # 급락일에 버텼을 때만
            + ((lambda n: dk.keep_tone(R._section("뉴스", n, tab="오늘")) if n else "")(render_kr.sec_today(s) if MEDIA_OK else render_kr.sec_facts_only(s)))   # 방송 뉴스 + 한국 기사 사건 — 정식과 같은 구획, 최근 7일 0건이면 숨김 · 방송을 못 읽으면 기사 사건만
            + (R._section("매수의견", op, tab="매수의견") if op else "")
            + (R._section("실적", ea, tab="실적") if ea else "")
            + R._section("업계상황", render_kr.sec_industry_tab(s), tab="업계상황")
            + R._section("기업", render_kr.sec_company(s), tab="기업")   # `최근 공시는?` 뺐다 — 정식과 같게
            + R.related_buttons(related_links) + "</div>")


def build(ref_kr, bars_all, flows, hist_full, det, dart_data, hist_quick, only=None, related=None, extra_today=None, caps=None, us_earn=None, disc=None):
    """간단 종목(정식 아님) 화면 조각 {코드: html}."""
    quick = [s for s, e in ref_kr.items() if not e.get("full") and len(bars_all.get(s) or []) >= 30 and (only is None or s in only)]
    groups = {}
    for s, e in ref_kr.items():
        if s in K.BY_SYM:
            groups.setdefault(K.sector(s), []).append(s)
            continue
        if len(bars_all.get(s) or []) < 30:
            continue
        rep = rep_of(s, e)
        K.CANDIDATES.append((s, e["ko"], f"quick-{code_of(s)}", e.get("sector") or "기타", list(K.groups(rep)) if rep else []))
        K.BY_SYM[s] = K.CANDIDATES[-1]
        if code_of(s) in CARD_OFF:
            K.SECTOR_FALLBACK_OFF.add(s)
        if not rep and CARD.get(code_of(s)) in K.BIZ:   # 대표 종목이 없는 새 묶음 — 업계 일감 지표는 BIZ, 업계 경기 · 수익성은 아래 업종 통계. 업계 자금 흐름(업종 ETF)은 없다
            K.BIZ_OF[code_of(s)] = CARD[code_of(s)]
            for tbl, ind in zip((K.BSI_INDUSTRY, K.FIN_INDUSTRY, K.LOAN_INDUSTRY), K.BIZ_STATS.get(CARD[code_of(s)]) or ()):   # 업계 경기 · 수익성 = 그 묶음이 속한 업종 통계(안내 줄 = K.BIZ_MIX_NOTE)
                if s not in tbl[ind][1]:
                    tbl[ind][1].append(s)
        if rep:
            alias(rep, s)
        groups.setdefault(e.get("sector") or "기타", []).append(s)
    peers = full_us.corr_peers(bars_all, {k: [s for s in v if bars_all.get(s)] for k, v in groups.items()})
    group, grev, geps = full_group()
    hist = {"stats": {**(hist_full or {}).get("stats", {}), **hist_quick.get("stats", {})}, "bench": K.BENCH}
    snap = {"bars": bars_all, "caps": {}, "fetched_at": datetime.datetime.now().isoformat(timespec="minutes")}
    extra = {"stocks": {**geps, **{s: {f: (det.get(s) or {}).get(f) for f in DETAIL_FIELDS} for s in quick}},
             "revenue": {"series": {**grev, **dart_data["revenue"]}}, "capex": dart_data["capex"], "company": dart_data["company"],
             "earnings": {}, "pair_earnings": {t: (us_earn or {}).get(t) or [] for t in LINK_US}}   # 미국 연관 종목 실적일 = 미국 간단 실행이 받은 Finnhub 달력(earn_us.json) 그대로 (2026-11-16)
    stocks = [x for x in (analyze_kr.stock(s, snap, hist, flows) for s in quick) if x]
    if not stocks:
        return {}
    day = max(x["day"] for x in stocks)
    market = analyze_kr.flows(flows, bars_all.get(K.BENCH)) or {}
    mr = analyze_kr.A.market_regime({"bars": {analyze_kr.NC.REGIME_BENCHMARK: bars_all.get(K.BENCH) or []}})
    crash = render_kr.RP.CW.compute(bars_all, "kr", quick)   # 급락장에서 어땠나? — 정식과 같은 계산, 일봉만
    for x in stocks:
        x.update(market_regime=mr, sector_flow=analyze_kr.sector_flow(snap, x["sym"]), fx=market.get("fx"), crash=render_kr.RP.CW.for_stock(crash, x["sym"]),
                 rank=None, in_top=False, pairs={},
                 cap=((caps or {}).get(x["sym"]) or {}).get("cap"), cap_rank=((caps or {}).get(x["sym"]) or {}).get("rank"))   # 기업 탭 시가총액 줄
    a = {"day": day, "stocks": stocks, "market": market, "crash": {}}
    # render_kr.write_all 의 준비 부분 그대로 (파일 쓰기 · 목록 페이지 · 방송 읽기 빼고)
    render_kr.KR_PRICES.clear()
    render_kr.KR_PRICES.update({x["code"]: (x["name"], x.get("ret_1d")) for x in stocks if x.get("ret_1d") is not None})
    render_kr.attach_broker(stocks)   # 증권사 목표가 — 한국 정식 실행이 kr-state 에 남긴 broker_tg.json 을 읽기만
    macro_rows = render_kr.us_calendar()
    render_kr.US_NAMES.update(US_KO)   # 미국 연관 종목 일정 카드 — 정식 명단 밖 미국 종목도 한글 이름
    for x in stocks:   # `미국 연관 종목 일정은?` = 검증 통과한 짝(LINKS)만 — 정식 PAIRS 자리에 (analyze 뒤라 오늘 탭 판정에는 안 섞인다)
        if LINKS.get(x["sym"]):
            K.PAIRS[x["sym"]] = ([r["t"] for r in LINKS[x["sym"]]], "")
    for x in stocks:
        x["company"] = extra["company"].get(x["code"]) or {}
        render_kr.build_expect(x, extra, group)
        x["_revenue_rows"] = extra["revenue"]["series"].get(x["sym"]) or []
        try:
            render_kr.build_calendar(x, snap, extra, macro_rows)
        except Exception as e:  # noqa: BLE001
            print(f"[quick-kr] {x['sym']} 캘린더 실패: {e}")
    render_kr.NOW = datetime.datetime.now(datetime.timezone.utc)
    render_kr.BARS = bars_all
    render_kr.PICK_SINCE = R.pick_window(bars_all.get(K.BENCH) or [], render_kr.media_feed.KST, now=render_kr.NOW)[1]
    media_inputs()   # 방송 줄 · 방송 의견 — 그 종목 자료가 있을 때 줄, 의견은 없으면 `없음` 카드
    snap_us = {"us_bars": {t: bars_all[t] for t in LINK_US if bars_all.get(t)}}
    for x in stocks:   # 밤사이 미국 연결 종목 — 정식 analyze_kr.us_move 그대로(한국 날짜보다 앞선 마지막 미국 종가)
        x["us_links"] = [(m, r.get("why") or "") for r in LINKS.get(x["sym"]) or [] for m in [analyze_kr.us_move(r["t"], snap_us, x["day"])[0]] if m]
    by = {x["sym"]: x.get("ret_1d") for x in stocks}
    for s in peers:
        for p in peers[s]:
            if p not in by and len(bars_all.get(p) or []) >= 2 and bars_all[p][-1]["day"] == day and bars_all[p][-2].get("adj"):
                by[p] = (bars_all[p][-1]["adj"] / bars_all[p][-2]["adj"] - 1) * 100
    out, fails = {}, 0
    for x in stocks:
        try:
            x["disc"] = disc(x["sym"]) if disc else []
            out[x["code"]] = body(x, a, list(peers.get(x["sym"]) or {}), by, related(x["sym"], ref_kr[x["sym"]]) if related else [],
                                  extra_today(x["sym"]) if extra_today else "")
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"[quick-kr] {x['sym']} 화면 실패: {e!r}")
    print(f"[quick-kr] 화면 {len(out)}/{len(quick)} · 실패 {fails}")
    return out
