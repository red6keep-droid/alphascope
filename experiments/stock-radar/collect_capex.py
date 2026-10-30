"""돈을 어디에 쓰나 — 설비 투자(자본 지출) · 연구개발 · 영업현금흐름 · 자금 조달(부채 발행 · 상환 · 자사주 · 배당 · 증자) 분기 표, SEC XBRL companyfacts 로. AI 없음.

2026-10-30 사용자: "각 기업의 자본 지출 현황 · 채권 발행 같은 자금 조달도" → 미국 후보 전부(한국은 미국 뒤, OpenDART).
재료 = collect_extra.revenue() 가 분기 매출 때 이미 받는 companyfacts JSON 하나 — 같은 JSON 에서 아래 항목을 더 뽑는다 (SEC 호출 수 그대로).

현금흐름표 값은 10-Q 에 누적(연초부터)으로 적히는 회사가 많다 → 같은 회계연도 시작일끼리 이어 붙여 차분해 분기 값으로 만든다(_quarters_cf).
손익 항목(연구개발비)은 3개월 값이 있으면 그대로, 누적만 있으면 같은 차분. 잔액(현금 · 장기 부채)은 분기 말 값 그대로.
회사마다 항목 이름이 다르다(설비 투자 = PaymentsToAcquirePropertyPlantAndEquipment 또는 PaymentsToAcquireProductiveAssets(리츠)) → 후보 가운데 최근 4년 분기가 가장 많은 것 하나.
없는 항목은 None(화면에 '미수집', 0 아님). 외국 회사(TSM · ASML, 20-F · IFRS)는 us-gaap 이 없어 표 자체가 없다.
결과 한 줄 = {start, end, cq, capex, rnd, ocf, debt_in, debt_out, buyback, div, stock_in, lease, cash, debt, src(그 분기 공시 색인 URL), form}.
"""

import datetime

# 항목 후보 (앞에서부터 — 분기 수가 같으면 앞 것)
TAGS = {
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets", "PaymentsForCapitalImprovements",
              "PaymentsToAcquireOtherPropertyPlantAndEquipment",
              "PaymentsToAcquireOilAndGasPropertyAndEquipment", "PaymentsToExploreAndDevelopOilAndGasProperties", "PaymentsToAcquireOilAndGasProperty"),   # 석유 · 가스(COP 류)
    "rnd": ("ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"),
    "ocf": ("NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
    "debt_in": ("ProceedsFromIssuanceOfLongTermDebt", "ProceedsFromIssuanceOfSeniorLongTermDebt", "ProceedsFromIssuanceOfDebt",
                "ProceedsFromDebtNetOfIssuanceCosts", "ProceedsFromIssuanceOfUnsecuredDebt"),
    "debt_out": ("RepaymentsOfLongTermDebt", "RepaymentsOfDebt", "RepaymentsOfSeniorDebt", "RepaymentsOfLongTermDebtAndCapitalSecurities",
                 "RepaymentsOfUnsecuredDebt"),
    "buyback": ("PaymentsForRepurchaseOfCommonStock",),
    "div": ("PaymentsOfDividends", "PaymentsOfDividendsCommonStock"),
    "stock_in": ("ProceedsFromIssuanceOfCommonStock", "ProceedsFromIssuanceOrSaleOfEquity"),
    "lease": ("FinanceLeasePrincipalPayments",),
}
INSTANT_TAGS = {
    "cash": ("CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
    "debt": ("LongTermDebt", "LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"),
}
FORMS = ("10-Q", "10-K", "10-Q/A", "10-K/A")
ZERO_WHEN_ABSENT = {"debt_in", "debt_out", "buyback", "div", "stock_in", "lease"}
YEARS = 4


def _d(s):
    return datetime.date.fromisoformat(s)


def _cq(start, end):
    m = _d(start) + (_d(end) - _d(start)) / 2
    return f"{m.year}Q{(m.month - 1) // 3 + 1}"


def _quarters_cf(facts):
    """기간 값 → 분기 값 {(start, end): (val, accn, form, filed)}.
    같은 시작일(회계연도 첫날)의 누적 값들을 끝날 순으로 이어 차분한다. 3개월 값은 그대로. 같은 기간이 여러 번 공시되면 가장 늦게 공시한 값."""
    span = {}
    for f in facts:
        if "start" not in f or f.get("form") not in FORMS or f.get("val") is None:
            continue
        key = (f["start"], f["end"])
        if key not in span or f["filed"] > span[key]["filed"]:
            span[key] = f
    by_start = {}
    for (s, e), f in span.items():
        by_start.setdefault(s, []).append((e, f))
    out = {}
    for s, items in by_start.items():
        items.sort()
        prev_end, prev_val = None, 0.0
        for e, f in items:
            seg_start = s if prev_end is None else (_d(prev_end) + datetime.timedelta(days=1)).isoformat()
            days = (_d(e) - _d(seg_start)).days
            if 70 <= days <= 110:   # 차분한 조각이 한 분기
                key = (seg_start, e)
            elif prev_end is None and 160 <= days <= 200:
                # 연초 조각이 반기 — 1분기 10-Q 에 이 줄이 없었다는 뜻(발행 · 자사주처럼 그 분기에 0 이면 줄을 안 적는다) → 반기 값은 통째로 2분기 것
                key = ((_d(e) - datetime.timedelta(days=91)).isoformat(), e)
            else:
                key = None
            if key and (key not in out or f["filed"] > out[key][3]):
                out[key] = (f["val"] - prev_val, f.get("accn"), f.get("form"), f["filed"])
            prev_end, prev_val = e, f["val"]
    return out


def _best(facts_all, tags, cutoff):
    best, used = {}, None
    for t in tags:
        q = _quarters_cf((facts_all.get(t) or {}).get("units", {}).get("USD", []))
        q = {k: v for k, v in q.items() if k[1] >= cutoff}
        if len(q) > len(best):
            best, used = q, t
    return best, used


def _instants(facts_all, tags, cutoff):
    best, used = {}, None
    for t in tags:
        d = {}
        for f in (facts_all.get(t) or {}).get("units", {}).get("USD", []):
            if "start" in f or f.get("form") not in FORMS or f["end"] < cutoff or f.get("val") is None:
                continue
            if f["end"] not in d or f["filed"] > d[f["end"]][1]:
                d[f["end"]] = (f["val"], f["filed"])
        if len(d) > len(best):
            best, used = d, t
    return {k: v[0] for k, v in best.items()}, used


def rows_from_facts(facts, cik):
    """companyfacts JSON → 분기 표(오래된 순). us-gaap 이 없거나 설비 투자 · 영업현금흐름이 모두 없으면 []."""
    gaap = (facts or {}).get("facts", {}).get("us-gaap", {})
    if not gaap:
        return []
    cutoff = (datetime.date.today() - datetime.timedelta(days=YEARS * 365)).isoformat()
    series, used = {}, {}
    for k, tags in TAGS.items():
        series[k], used[k] = _best(gaap, tags, cutoff)
    inst = {}
    for k, tags in INSTANT_TAGS.items():
        inst[k], used[k] = _instants(gaap, tags, cutoff)
    if not series["capex"] and not series["ocf"]:
        return []
    # 분기 축 = 설비 투자 · 영업현금흐름 기간의 합집합 (끝날 기준으로 맞춘다 — 같은 회사라 회계 분기가 같다)
    ends = {}
    for k in ("ocf", "capex"):
        for (s, e), v in series[k].items():
            ends.setdefault(e, s)
    rows = []
    for e in sorted(ends):
        s = ends[e]
        row = {"start": s, "end": e, "cq": _cq(s, e)}
        src = None
        for k in TAGS:
            v = series[k].get((s, e))
            if v is None:   # 시작일이 다르게 적힌 같은 분기(드묾) — 끝날이 같은 것으로
                v = next((x for (s2, e2), x in series[k].items() if e2 == e), None)
            row[k] = None if v is None else float(v[0])
            if v is not None and k in ("capex", "ocf") and v[1]:
                src = v
        for k in INSTANT_TAGS:
            row[k] = inst[k].get(e)
        row["form"] = src[2] if src else None
        row["src"] = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{src[1].replace('-', '')}/" if src and src[1] else None
        rows.append(row)
    for r in rows:   # 1년 전 같은 분기 대비 (설비 투자)
        prev = [x for x in rows if abs((_d(r["end"]) - _d(x["end"])).days - 364) <= 20]
        r["capex_yoy"] = (r["capex"] / prev[0]["capex"] - 1) * 100 if prev and r["capex"] and prev[0].get("capex") else None
    return rows


def summary(rows, n=4):
    """최근 n 분기 합 · 그 전 n 분기 합 (항목별) — 카드의 '최근 4분기' 줄과 늘림 · 줄임 판정 재료. 값이 하나라도 없는 항목은 None."""
    def tot(part, k, zero_ok):
        vs = [r.get(k) for r in part]
        if not vs or (not zero_ok and any(v is None for v in vs)):
            return None
        return sum(v or 0 for v in vs)
    last, before = rows[-n:], rows[-2 * n:-n]
    out = {}
    for k in TAGS:
        # 발행 · 상환 · 자사주 · 배당 · 증자 · 리스는 그 해에 없으면 줄 자체를 안 적는 회사가 많다 → 표 어딘가에 값이 있는 항목이면 빈 분기를 0 으로 더한다.
        # 설비 투자 · 연구개발 · 영업현금흐름은 빈 분기가 있으면 합을 내지 않는다(미수집)
        zero_ok = k in ZERO_WHEN_ABSENT and any(r.get(k) is not None for r in rows)
        out[k] = tot(last, k, zero_ok) if len(last) == n else None
        out[k + "_prev"] = tot(before, k, zero_ok) if len(before) == n else None
    return out
