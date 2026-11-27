"""한국 종목 손익 · 현금흐름 분기 표 — 금융감독원 OpenDART 단일회사 전체 재무제표(fnlttSinglAcntAll). 미국 collect_capex 표와 같은 줄 모양.

미국 표(stock-radar/collect_capex.py)는 SEC companyfacts 한 JSON 에서 뽑지만, 한국은 보고서마다 한 번 부른다 — 주요계정 API(collect_kr_dart, 매출)에는 현금흐름표가 없다.
- 손익계산서(IS · 없으면 CIS) : thstrm_amount = 그 석 달(분기 · 반기 보고서) · 1년치(사업보고서), thstrm_add_amount = 누적 → 4분기 = 1년치 − 3분기 누적 (매출 수집기와 같은 셈).
- 현금흐름표(CF) : 분기 보고서도 누적(연초부터)만 적는다 → 앞 보고서 누적을 빼 분기 값으로 (1분기 = 그대로, 반기 − 1분기, 3분기 − 반기, 1년 − 3분기). 앞 보고서가 없으면 그 분기는 None.
- 유출 항목(설비 투자 · 배당 · 자사주 · 상환)은 회사마다 부호가 달라 절댓값. 차입금 `순증가(감소)` 줄은 부호가 뜻이라 분기 차분 뒤 + 는 빌린 돈, − 는 갚은 돈.
- 계정은 표준 계정 ID(ifrs-full_… · dart_…) 먼저, 없으면 계정 이름(띄어쓰기 뺀 정규식). 없는 항목은 None(화면 `미수집`). 발행 · 자사주 · 배당 · 리스는 보고서가 있는데 줄이 없으면 그 기간 0.
- 연결(CFS) 먼저, 없으면(status 013) 별도(OFS). 연구개발비 · 장기 부채는 주요 재무제표 줄이 아니라 받지 않는다(카드에서 줄을 뺀다).
- 캐시 data/dart_fin_all.json(kr-state 에 보존) — 이미 받은 보고서는 다시 받지 않는다. 아직 안 나온 보고서는 7일마다 다시 물어본다.
한도(홈페이지 게시, 11-04 확인): 하루 20,000회 · 키 하나(매출 · 실적일 수집기와 같은 키). 첫 실행 35종목 × 4년 × 4보고서 ≈ 560회(별도 재시도 포함 최대 2배), 그 뒤로는 새 보고서만(분기마다 35회 안팎).
결과 한 줄 = {start, end, cq, capex, rnd(None), ocf, gp, opinc, ni, debt_in, debt_out, buyback, div, stock_in, lease, fcf, cash, debt(None), src(DART 보고서 주소), form, *_yoy}.

    python experiments/kr-stocks/collect_kr_fin.py     # 받기 → data/dart_fin_all.json, 종목별 분기 수 출력
"""

import datetime
import json
import os
import re
import sys
import time

import requests

import collect_kr_dart as D
import universe_kr as U

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stock-radar"))
import collect_capex as CX  # noqa: E402 — fcf · 1년 전 대비(_yoy), 4분기 합(summary) 은 미국 표와 같은 함수

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "data", "dart_fin_all.json")
FORM = {"11013": "분기보고서", "11012": "반기보고서", "11014": "분기보고서", "11011": "사업보고서"}
# 항목 : (재무제표, 표준 계정 ID 후보, 계정 이름 정규식(띄어쓰기 뺀 이름에), 종류) — flow3 = 손익(3개월 값 + 누적), cum = 현금흐름(누적), inst = 잔액
ITEMS = {
    "rev": (("IS", "CIS"), ("ifrs-full_Revenue",), r"^(매출액|수익\(매출액\)|매출|영업수익)(\(.*\))?$", "flow3"),
    "gp": (("IS", "CIS"), ("ifrs-full_GrossProfit",), r"^매출총이익", "flow3"),
    "opinc": (("IS", "CIS"), ("dart_OperatingIncomeLoss",), r"^영업이익", "flow3"),
    "ni": (("IS", "CIS"), ("ifrs-full_ProfitLoss",), r"^(연결)?(당기|분기|반기)?순이익", "flow3"),
    "ocf": (("CF",), ("ifrs-full_CashFlowsFromUsedInOperatingActivities",), r"^영업활동(으로인한|으로부터의)?현금흐름", "cum"),
    "capex": (("CF",), ("ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",), r"^유형자산의?취득", "cum"),
    "div": (("CF",), ("ifrs-full_DividendsPaidClassifiedAsFinancingActivities",), r"^배당금의?지급", "cum"),
    "buyback": (("CF",), ("dart_AcquisitionOfTreasuryShares", "ifrs-full_PaymentsToAcquireOrRedeemEntitysShares"), r"^자기주식의?(취득|매입)", "cum"),
    "stock_in": (("CF",), ("ifrs-full_ProceedsFromIssuingShares",), r"^(주식의?발행|유상증자)", "cum"),
    "lease": (("CF",), ("ifrs-full_PaymentsOfLeaseLiabilitiesClassifiedAsFinancingActivities",), r"^리스부채의?(상환|지급)", "cum"),
    "cash": (("BS",), ("ifrs-full_CashAndCashEquivalents",), r"^현금및현금성자산", "inst"),
    # 재무상태표 잔액 — `회사 살림은 튼튼한가?`. 같은 응답이라 호출 0
    "liab": (("BS",), ("ifrs-full_Liabilities",), r"^부채총계$", "inst"),
    "equity": (("BS",), ("ifrs-full_Equity",), r"^자본총계$", "inst"),
    "inv": (("BS",), ("ifrs-full_Inventories",), r"^재고자산$", "inst"),
    "recv": (("BS",), ("ifrs-full_CurrentTradeReceivables", "dart_ShortTermTradeReceivable", "ifrs-full_TradeAndOtherCurrentReceivables"), r"^(매출채권|매출채권및기타(유동)?채권)", "inst"),
}
# 여러 줄을 더하는 잔액 — 빌린 돈(차입금 · 사채, 리스 빼고) · 미리 받은 돈(계약부채) · 바로 쓸 수 있는 돈(현금 · 단기 예금 · 단기 투자). 표준 ID 먼저, 없으면 이름(ID 가 표준이 아닌 줄만)
SUMS = {
    "borrow": ({"ifrs-full_ShorttermBorrowings", "ifrs-full_CurrentPortionOfLongtermBorrowings", "ifrs-full_CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings",
                "ifrs-full_LongtermBorrowings", "ifrs-full_NoncurrentPortionOfNoncurrentBondsIssued", "ifrs-full_NoncurrentPortionOfNoncurrentLoansReceived",
                "ifrs-full_BondsIssued", "ifrs-full_CurrentPortionOfNoncurrentBondsIssued", "ifrs-full_NoncurrentPortionOfNoncurrentBorrowings",
                "ifrs-full_CurrentPortionOfNoncurrentBorrowings", "dart_ShortTermBorrowings", "dart_LongTermBorrowingsGross", "dart_BondsIssued",
                "dart_CurrentPortionOfBonds", "dart_CurrentPortionOfLongTermBorrowings"},
               r"^(단기차입금|장기차입금|사채|유동성장기부채|유동성사채|유동성장기차입금|유동성차입금|차입금|사채및차입금|유동성사채및단기차입금)$"),
    "contract": ({"ifrs-full_CurrentContractLiabilities", "ifrs-full_ContractLiabilities", "ifrs-full_NoncurrentContractLiabilities"}, r"^(유동|비유동)?(계약부채|초과청구공사)$"),
    "liquid": ({"ifrs-full_CashAndCashEquivalents", "ifrs-full_ShorttermDepositsNotClassifiedAsCashEquivalents", "dart_ShortTermDepositsNotClassifiedAsCashEquivalents",
                "ifrs-full_CurrentFinancialAssetsAtFairValueThroughProfitOrLoss"}, r"^(현금및현금성자산|단기금융상품|단기예금)$"),
}
FIN_VER = 2   # 2 = 재무상태표 줄(SUMS · liab ~ recv)까지 — 옛 보고서(1)는 한 번 다시 받는다 (하루 BACKFILL 회사 상한)
BACKFILL = 40
ABS_KEYS = {"capex", "div", "buyback", "stock_in", "lease"}   # 유출 · 유입 금액 — 부호 없이
ZERO_IF_REPORTED = {"div", "buyback", "stock_in", "lease", "debt_in", "debt_out"}   # 보고서는 있는데 줄이 없으면 0 (미국 ZERO_WHEN_ABSENT 와 같은 뜻)
# 차입 · 사채 줄 (현금흐름표 재무활동) — 이름으로만. 이자 · 리스 · 재무활동 합계 줄은 뺀다
_DEBT = re.compile(r"(차입금|차입|사채|회사채)")
_DEBT_NET = re.compile(r"순(증가|감소|증감)")
_DEBT_IN = re.compile(r"(의차입|증가|발행|조달|차입$|차입\(|인출)")
_DEBT_OUT = re.compile(r"(상환|감소|감액|지급)")
_DEBT_SKIP = re.compile(r"(이자|리스|재무활동|현금흐름|유동성|평가|손익|비용)")
RETRY_DAYS = 7


def _norm(name):
    return re.sub(r"\s+", "", name or "")


def _pick(rows, item):
    """보고서 줄 가운데 이 항목 한 줄 — 재무제표 순서(IS 먼저, 없으면 CIS) · 표준 ID 먼저, 없으면 이름."""
    sjs, ids, pat, _ = item
    for sj in sjs:
        part = [x for x in rows if x.get("sj_div") == sj]
        for i in ids:
            x = next((x for x in part if x.get("account_id") == i), None)
            if x:
                return x
        x = next((x for x in part if re.search(pat, _norm(x.get("account_nm")))), None)
        if x:
            return x
    return None


def _debt(rows):
    """재무활동 차입 · 사채 줄 합 — {"in": 빌린 돈, "out": 갚은 돈, "net": 순증감 줄(부호 그대로)} (누적). 줄이 하나도 없으면 {}."""
    out, hit = {"in": 0.0, "out": 0.0, "net": 0.0}, False
    for x in rows:
        if x.get("sj_div") != "CF":
            continue
        nm = _norm(x.get("account_nm"))
        v = D._amount(x.get("thstrm_amount"))
        if v is None or not _DEBT.search(nm) or _DEBT_SKIP.search(nm):
            continue
        if _DEBT_NET.search(nm):
            out["net"] += v
        elif _DEBT_OUT.search(nm):
            out["out"] += abs(v)
        elif _DEBT_IN.search(nm):
            out["in"] += abs(v)
        else:
            continue
        hit = True
    return out if hit else {}


def _sums(rows):
    """SUMS 잔액 — {이름: 합 또는 None}. 같은 ID 가 두 번(연결 · 별도 섞임) 나오면 한 번만."""
    out = {}
    for k, (ids, pat) in SUMS.items():
        seen, tot, hit = set(), 0.0, False
        for x in rows:
            if x.get("sj_div") != "BS":
                continue
            aid, nm = x.get("account_id") or "", _norm(x.get("account_nm"))
            std = aid.startswith(("ifrs-full_", "dart_"))
            if (aid in ids) if std else re.search(pat, nm):
                key = aid if std else nm
                v = D._amount(x.get("thstrm_amount"))
                if key in seen or v is None:
                    continue
                seen.add(key)
                tot += v
                hit = True
        out[k] = tot if hit else None
    if out.get("borrow") is None and any(x.get("sj_div") == "BS" for x in rows):
        out["borrow"] = 0.0   # 재무상태표는 있는데 차입 줄이 없다 = 빌린 돈 0 (크래프톤처럼 사채 · 차입이 없는 회사)
    return out


def _report(key, corp, year, rc):
    """보고서 하나 → {"v": {항목: [thstrm, add]}, "debt": {...}, "rcept": 접수번호, "fs": CFS|OFS} 또는 {"none": 오늘, "status": 코드}."""
    last = None
    for fs in ("CFS", "OFS"):
        r = requests.get(f"{D.API}/fnlttSinglAcntAll.json", params={"crtfc_key": key, "corp_code": corp, "bsns_year": str(year), "reprt_code": rc, "fs_div": fs}, timeout=30).json()
        last = r.get("status")
        if last == "000" and r.get("list"):
            rows = r["list"]
            v = {}
            for k, item in ITEMS.items():
                x = _pick(rows, item)
                if x:
                    v[k] = [D._amount(x.get("thstrm_amount")), D._amount(x.get("thstrm_add_amount"))]
            for k, x in _sums(rows).items():
                v[k] = [x, None]
            if v:
                return {"v": v, "debt": _debt(rows), "rcept": rows[0].get("rcept_no"), "fs": fs, "ver": FIN_VER}
        if last not in ("013", "000"):   # 013 = 자료 없음 → 별도 재무제표로. 그 밖(키 · 한도 오류)은 바로 멈춘다
            break
        time.sleep(0.2)
    return {"none": datetime.date.today().isoformat(), "status": last}


def _rows(mine, today):
    """한 회사의 캐시(보고서별) → 분기 줄 목록(오래된 순). 값이 하나도 없는 분기는 뺀다."""
    rows = []
    for year in range(today.year - D.YEARS + 1, today.year + 1):
        reps = {rc: mine.get(f"{year}-{rc}") or {} for rc, _ in D.REPORTS}
        prev_rc = None
        for i, (rc, mmdd) in enumerate(D.REPORTS):
            rep = reps[rc]
            if "v" not in rep:
                prev_rc = rc
                continue
            v, prev = rep["v"], (reps.get(prev_rc) if prev_rc else None)
            prev_ok = i == 0 or (prev is not None and "v" in prev)   # 1분기는 앞 보고서가 필요 없다
            row = {"start": f"{year}-{('01-01', '04-01', '07-01', '10-01')[i]}", "end": f"{year}-{mmdd}", "cq": f"{year}Q{i + 1}"}
            for k in SUMS:   # 잔액 — 그 분기 끝 값 그대로
                row[k] = (v.get(k) or [None])[0]
            for k, (_, _, _, kind) in ITEMS.items():
                a = v.get(k)
                if kind == "inst":
                    row[k] = a[0] if a else None
                elif kind == "flow3":
                    if rc != "11011":
                        row[k] = a[0] if a else None
                    else:   # 4분기 = 1년치 − 3분기 누적
                        q3 = (prev or {}).get("v", {}).get(k)
                        row[k] = a[0] - q3[1] if a and a[0] is not None and q3 and q3[1] is not None else None
                else:   # cum — 앞 보고서 누적을 뺀다. 줄이 없으면 0 (발행 · 배당 류) 또는 None (설비 투자 · 영업현금흐름)
                    cur = a[0] if a and a[0] is not None else (0.0 if k in ZERO_IF_REPORTED else None)
                    before = 0.0 if i == 0 else ((prev or {}).get("v", {}).get(k) or [None])[0]
                    if i > 0 and before is None:
                        before = 0.0 if (prev_ok and k in ZERO_IF_REPORTED) else None
                    if cur is None or before is None or not prev_ok:
                        row[k] = None
                    else:
                        row[k] = abs(cur) - abs(before) if k in ABS_KEYS else cur - before
            # 차입 · 사채 — 누적 차분, 순증감 줄은 부호로 나눈다
            dn, dp = rep.get("debt") or {}, ((prev or {}).get("debt") or {}) if i > 0 else {}
            if dn or (prev_ok and "v" in rep):
                if prev_ok:
                    cur_in, cur_out, cur_net = dn.get("in", 0.0), dn.get("out", 0.0), dn.get("net", 0.0)
                    b_in, b_out, b_net = dp.get("in", 0.0), dp.get("out", 0.0), dp.get("net", 0.0)
                    net = cur_net - b_net
                    row["debt_in"] = (cur_in - b_in) + max(net, 0.0)
                    row["debt_out"] = (cur_out - b_out) + max(-net, 0.0)
                else:
                    row["debt_in"] = row["debt_out"] = None
            else:
                row["debt_in"] = row["debt_out"] = None
            row["rnd"] = row["debt"] = None   # 주요 재무제표 줄이 아니다 — 카드에서 줄을 뺀다
            row["form"] = FORM[rc]
            row["src"] = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rep['rcept']}" if rep.get("rcept") else None
            if any(row.get(k) is not None for k in ("ocf", "capex", "gp", "opinc", "ni")):
                rows.append(row)
            prev_rc = rc
    rows.sort(key=lambda r: r["end"])
    return CX._yoy(rows)


def run():
    """→ {종목 티커: [분기 줄]} (미국 extra["capex"] 와 같은 모양). 키가 없으면 캐시로만."""
    key = D._key()
    today = datetime.date.today()
    cache = D._load(CACHE)
    calls = backfilled = 0
    if key:
        codes = D.corp_codes(key)
        for sym, *_ in U.CANDIDATES:
            corp = codes.get(sym.split(".")[0])
            if not corp:
                continue
            mine = cache.setdefault(corp, {})
            old = any("v" in r and r.get("ver", 1) < FIN_VER for r in mine.values() if isinstance(r, dict))
            if old and backfilled >= BACKFILL:
                old = False   # 오늘 몫을 다 썼다 — 옛 보고서는 다음 실행에
            backfilled += old
            for year in range(today.year - D.YEARS + 1, today.year + 1):
                for rc, mmdd in D.REPORTS:
                    if datetime.date.fromisoformat(f"{year}-{mmdd}") >= today:
                        continue
                    k = f"{year}-{rc}"
                    got = mine.get(k)
                    due = datetime.date.fromisoformat(f"{year}-{mmdd}") + datetime.timedelta(days=90 if rc == "11011" else 45)   # 법정 제출 기한
                    near = -5 <= (today - due).days <= 20   # 기한 앞뒤엔 매일 다시 묻는다 — 11-12 에 `없음` 이 남아 삼성전자 · NAVER 3분기가 11-19 까지 빠질 뻔했다 (2026-11-16)
                    if got and ("v" in got and (got.get("ver", 1) >= FIN_VER or not old)
                                or "v" not in got and got["none"] >= ((today if near else today - datetime.timedelta(days=RETRY_DAYS))).isoformat()):
                        continue
                    mine[k] = _report(key, corp, year, rc)
                    calls += 1
                    time.sleep(0.2)
            D._save(CACHE, cache)
    else:
        print("[dart-fin] DART_API_KEY 없음 — 캐시만")
        codes = (D._load(D.CORP) or {}).get("map") or {}
    out = {}
    for sym, *_ in U.CANDIDATES:
        mine = cache.get(codes.get(sym.split(".")[0]) or "", {})
        rows = _rows(mine, today) if mine else []
        if rows:
            out[sym] = rows
    n_cf = sum(1 for v in out.values() if any(r.get("ocf") is not None for r in v[-4:]))
    print(f"[dart-fin] 호출 {calls}번 · 재무상태표 다시 받은 회사 {backfilled} · 손익 · 현금흐름 표 {len(out)}종목 (최근 4분기 영업현금흐름 {n_cf}종목)")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    s = run()
    for sym in ("005930.KS", "000660.KS", "105560.KS"):
        for r in s.get(sym, [])[-5:]:
            print(sym, r["cq"], {k: None if r.get(k) is None else round(r[k] / 1e12, 2) for k in ("rev", "gp", "opinc", "ni", "ocf", "capex", "fcf", "div", "buyback", "debt_in", "debt_out", "cash")})
        print(sym, json.dumps({k: None if v is None else round(v / 1e12, 2) for k, v in CX.summary(s[sym]).items()} if s.get(sym) else {}, ensure_ascii=False))
