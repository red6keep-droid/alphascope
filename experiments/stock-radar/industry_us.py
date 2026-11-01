"""미국 업계 카드 — FRED 공식 통계로 `업계상황` 탭의 `○○ 업계 ○○은?` 카드 (2026-11-01 사용자: 한국처럼 방향까지).

검증(doc/검증/미국-업종지표-검증.md, validate_industry_us.py): 24개 중 은행 대출 하나만 통과 — 나머지는 툴팁 `기록상` 에 '뚜렷한 관계가 없었다'.
사용자 결정(11-01): 독자는 업계 상황을 빨리 파악하려는 것이라 방향(▲▼)은 한국 카드처럼 붙이고, 맞는지는 기록으로 풀어 간다.

카드 = (꼬리 질문, FRED 번호, 지표 이름, 모드, 출처 기관, 검증 키). 모드: qty(늘고 있음 · 줄고 있음) · price(오르는 중 · 내리는 중) — 1년 전 같은 달보다 ±5%.
수익성 = 업종 기업이익(분기, 미국 경제분석국) 1년 전 같은 분기보다 ±10% → 나아짐 · 나빠짐.
"""
import datetime
import json
import os
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "data", "fred_us.json")
LIM_WORK, LIM_MONEY = 5.0, 10.0

FED, CENSUS, BLS, BEA = "미국 연방준비제도", "미국 인구조사국", "미국 노동통계국", "미국 경제분석국"

# 업계 묶음 → (카드 제목에 쓰는 업계 이름, 일감 · 값 카드들, 수익성 카드)
BIZ = {
    "semi":    ("반도체", [("생산은?", "IPG3344S", "반도체 생산지수", "qty", FED, "semi_ip"), ("제품 값은?", "PCU33443344", "반도체 생산자물가", "price", BLS, "semi_ppi")],
                ("N501RC1Q027SBEA", "컴퓨터 · 전자제품 업종 기업이익", "tech_profit")),
    "bigtech": ("빅테크", [("고객 설비투자는?", "NEWORDER", "핵심 자본재 주문", "qty", CENSUS, "capex_orders")], None),
    "mart":    ("대형 유통", [("판매는?", "RSGMS", "종합소매(대형마트) 판매", "qty", CENSUS, "retail_gm")], ("N415RC1Q027SBEA", "소매업 기업이익", "retail_profit")),
    "staples": ("소비재", [("소매 판매는?", "RSXFS", "소매판매 (외식 제외)", "qty", CENSUS, "retail_all")], None),
    "home":    ("건자재 유통", [("판매는?", "RSBMGESD", "건자재 · 원예 판매", "qty", CENSUS, "building_mat")], None),
    "food":    ("외식", [("판매는?", "RSFSDP", "외식 판매", "qty", CENSUS, "food_service")], None),
    "online":  ("온라인 유통", [("판매는?", "RSNSR", "무점포(온라인) 판매", "qty", CENSUS, "nonstore")], None),
    "auto":    ("자동차", [("판매는?", "TOTALSA", "신차 판매", "qty", BEA, "auto_sales"), ("생산은?", "IPG3361T3S", "자동차 · 부품 생산지수", "qty", FED, "auto_ip")], None),
    "bank":    ("은행", [("대출은?", "TOTLL", "은행 대출", "qty", FED, "bank_loans")], None),
    "oil":     ("석유", [("유가는?", "MCOILWTICO", "유가 (WTI)", "price", "미국 에너지정보청", "wti")], ("N404RC1Q027SBEA", "석유 · 석탄 제품 업종 기업이익", "oil_profit")),
    "power":   ("전력", [("생산은?", "IPG2211S", "전력 생산지수", "qty", FED, "power_ip"), ("전기요금은?", "CUSR0000SEHF01", "전기요금 (소비자물가)", "price", BLS, "power_cpi")],
                ("N419RC1Q027SBEA", "전기 · 가스 업종 기업이익", "util_profit")),
    "pharma":  ("제약", [("생산은?", "IPG3254S", "의약품 생산지수", "qty", FED, "pharma_ip"), ("제품 값은?", "PCU32543254", "의약품 생산자물가", "price", BLS, "pharma_ppi")], None),
    "machine": ("산업재", [("건설 투자는?", "PNRESCONS", "비주거 건설 지출", "qty", CENSUS, "nonres_build")], None),
    "chem":    ("화학", [("생산은?", "IPG325S", "화학 생산지수", "qty", FED, "chem_ip")], None),
}
SYM_BIZ = {**{s: "semi" for s in ("NVDA", "AVGO", "MU", "AMD", "INTC", "TSM", "ASML", "LRCX", "AMAT")},
           **{s: "bigtech" for s in ("AAPL", "GOOGL", "MSFT", "META", "ORCL")},
           "WMT": "mart", "COST": "mart", "KO": "staples", "PG": "staples", "PM": "staples", "HD": "home", "MCD": "food", "AMZN": "online", "TSLA": "auto",
           "JPM": "bank", "BRK-B": "bank", **{s: "oil" for s in ("XOM", "CVX", "COP", "SLB", "EOG")}, **{s: "power" for s in ("CEG", "NEE", "SO", "VST")},
           **{s: "pharma" for s in ("LLY", "JNJ", "ABBV")}, **{s: "machine" for s in ("CAT", "GE", "VRT")}, "LIN": "chem"}

# 검증 기록 (2026-11-01 validate_industry_us.py) — 키: (통과?, 6개월 상위25% − 하위25% 초과수익 %p). 통과만 숫자를 툴팁에 쓴다
RECORD = {"bank_loans": (True, 5.6)}


def _key():
    k = os.environ.get("FRED_API_KEY")
    root = os.path.join(BASE, "..", "..", ".env")
    if not k and os.path.exists(root):
        for line in open(root, encoding="utf-8"):
            if line.startswith("FRED_API_KEY="):
                k = line.split("=", 1)[1].strip().strip("\"'")
    return k


def _ids():
    out = set()
    for _n, works, money in BIZ.values():
        out |= {w[1] for w in works}
        if money:
            out.add(money[0])
    return sorted(out)


def fetch():
    """FRED 최근 4년 — 하루 한 번(캐시가 오늘이면 그대로). 실패한 지표는 지난 캐시 값을 둔다. 키가 없으면 캐시만."""
    old = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    today = datetime.date.today().isoformat()
    if old.get("fetched") == today:
        return old
    key = _key()
    if not key:
        print("[industry_us] FRED_API_KEY 없음 — 캐시만")
        return old
    start = f"{datetime.date.today().year - 4}-01-01"
    out = {"fetched": today}
    for sid in _ids():
        try:
            q = urllib.parse.urlencode({"series_id": sid, "api_key": key, "file_type": "json", "observation_start": start})
            obs = json.load(urllib.request.urlopen(f"https://api.stlouisfed.org/fred/series/observations?{q}", timeout=60))["observations"]
            out[sid] = [(o["date"][:7], float(o["value"])) for o in obs if o["value"] not in (".", "")]
        except Exception as e:  # noqa: BLE001 — 지표 하나 실패로 페이지를 막지 않는다
            print(f"[industry_us] {sid} 실패: {str(e)[:80]}")
            if old.get(sid):
                out[sid] = old[sid]
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(out, open(CACHE, "w", encoding="utf-8"))
    return out


def load():
    return json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}


def _monthly(rows):
    """[(YYYY-MM, 값)] — 주간(은행 대출)은 달 평균. 분기 자료는 그대로(분기 첫 달 표기)."""
    by = {}
    for m, v in rows:
        by.setdefault(m, []).append(v)
    return [{"month": m, "v": sum(v) / len(v)} for m, v in sorted(by.items())]


def _yoy(series, step):
    """마지막 값과 1년 전(월 자료 12칸 · 분기 4칸) 대비 % — (마지막 행, 변화 %)."""
    if len(series) <= step:
        return None, None
    last, prev = series[-1], series[-1 - step]
    return last, ((last["v"] / prev["v"] - 1) * 100 if prev["v"] else None)


def build(sym, data):
    """종목 → 업계 카드 재료 {biz, works: [...], money}. 자료 없으면 None."""
    b = SYM_BIZ.get(sym)
    if not b or not data:
        return None
    name, works, money = BIZ[b]
    out = {"biz": name, "works": [], "money": None}
    for q, sid, label, mode, src, vkey in works:
        ser = _monthly(data.get(sid) or [])
        if sid == "TOTLL" and ser and ser[-1]["month"] == datetime.date.today().strftime("%Y-%m"):
            ser = ser[:-1]   # 주간 자료 — 이번 달은 덜 찼다
        last, chg = _yoy(ser, 12)
        if not last:
            continue
        up, dn = ("늘고 있음", "줄고 있음") if mode == "qty" else ("오르는 중", "내리는 중")
        state = "판단 유보" if chg is None else up if chg >= LIM_WORK else dn if chg <= -LIM_WORK else "비슷함"
        out["works"].append({"q": q, "fred": sid, "name": label, "mode": mode, "src": src, "vkey": vkey, "month": last["month"], "v": last["v"], "chg": chg,
                             "state": state, "series": ser[-25:]})
    if money:
        sid, label, vkey = money
        ser = _monthly(data.get(sid) or [])
        last, chg = _yoy(ser, 4)
        if last:
            state = "판단 유보" if chg is None else "나아짐" if chg >= LIM_MONEY else "나빠짐" if chg <= -LIM_MONEY else "비슷함"
            out["money"] = {"fred": sid, "name": label, "src": BEA, "vkey": vkey, "month": last["month"], "v": last["v"], "chg": chg, "state": state, "series": ser[-9:]}
    return out if out["works"] or out["money"] else None
