"""한국 종목 탭 재료 — `실적과 기대`(분기 매출 · 1주당 이익 예상) · `캘린더`(실적 발표일 · 미국과 연결 종목 실적일). yfinance (2026-10-25).

미국 종목(stock-radar collect_extra)과 같은 칸 모양으로 둔다 — 카드 판정 · 그림은 미국 카드 함수(analyze_tabs · nvda render_html)를 그대로 쓴다.
- 매출 : OpenDART 분기 매출(collect_kr_dart — 4년치, 1년 전 대비 8분기). DART 에 없는 종목(은행 · 보험 — 매출액 계정 없음)은 Yahoo quarterly_income_stmt(최근 5~6분기).
- 이익 · 현금흐름 : OpenDART 전체 재무제표 분기 표(collect_kr_fin — 매출총이익 · 영업이익 · 순이익 · 영업현금흐름 · 설비 투자 · 배당 · 자사주 · 차입, 2026-11-04) → extra["capex"].
- 1주당 이익 예상 : eps_trend · eps_revisions 의 +1y (nvda-report expect._eps 그대로).
- 실적 발표일 : earnings_dates (지난 · 앞으로). 한국 회사는 장 전 · 장중 발표가 많아 그날 반응으로 본다(when=bmo).
옵션(개별 종목 옵션 없음) · 공매도(Yahoo 에 없음, 한국거래소 자료는 약관 확인 전)는 받지 않는다.

    python experiments/kr-stocks/collect_kr_extra.py    # 받기 → data/extra.json
"""

import datetime
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "..", "nvda-report"))
import expect as EX  # noqa: E402

import universe_kr as U  # noqa: E402

EXTRA = os.path.join(BASE, "data", "extra.json")


def _cq(end):
    d = datetime.date.fromisoformat(end)
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def _revenue(t):
    q = t.quarterly_income_stmt
    if q is None or q.empty or "Total Revenue" not in q.index:
        return []
    rows = sorted(({"end": c.strftime("%Y-%m-%d"), "rev": float(v)} for c, v in q.loc["Total Revenue"].items() if v == v), key=lambda r: r["end"])
    by_cq = {_cq(r["end"]): r for r in rows}
    for r in rows:
        r["cq"] = _cq(r["end"])
        prev = by_cq.get(f"{int(r['cq'][:4]) - 1}{r['cq'][4:]}")
        r["yoy"] = (r["rev"] / prev["rev"] - 1) * 100 if prev and prev["rev"] else None
    return rows


def _earn_dates(t):
    e = t.earnings_dates
    if e is None or e.empty:
        return []
    return [{"day": d, "when": "bmo"} for d in sorted({x.strftime("%Y-%m-%d") for x in e.index})]


def _analysts(t):
    """애널리스트 등급 분포 · 목표가 — 미국 collect_extra._analysts 와 같은 칸 (2026-10-31 사용자: 한국도 `애널리스트 · 방송 의견은?`). 원화."""
    out = {}
    rec = t.recommendations
    if rec is not None and not rec.empty:
        r0 = rec.iloc[0]
        out["rating_counts"] = {k: int(r0[k]) for k in ("strongBuy", "buy", "hold", "sell", "strongSell")}
    pt = t.analyst_price_targets or {}
    for k in ("mean", "median", "high", "low"):
        if pt.get(k):
            out["pt_" + k] = float(pt[k])
    return out


def run():
    import yfinance as yf
    sys.path.insert(0, os.path.join(BASE, ".."))
    import detail_cache as DC
    cache = DC.shared(os.path.join(BASE, "data"))   # 칸마다 바뀌는 주기에만 (2026-11-12 사용자) — 매출 30일 · 실적 뒤, 이익 예상 · 의견 주 1회(종목별 요일) · 실적 뒤, 실적일 주 1회 · 14일 안이면 매일
    out = {"day": datetime.date.today().isoformat(), "stocks": {}, "revenue": {"series": {}}, "earnings": {}, "pair_earnings": {}}
    n_new = 0
    for sym, *_ in U.CANDIDATES:
        past, nxt = DC.earn_info(cache, sym)
        due = [k for k in ("revenue", "eps", "earnings", "analysts") if cache.due(sym, k, earn_days=past, next_earn=nxt)]
        cache.reused += 4 - len(due)
        if due:
            n_new += 1
            t = yf.Ticker(sym)
            fns = {"revenue": lambda: _revenue(t), "eps": lambda: EX._eps(t), "earnings": lambda: _earn_dates(t), "analysts": lambda: _analysts(t)}
            for key in due:
                try:
                    v = fns[key]()
                except Exception as e:  # noqa: BLE001 — 한 칸이 실패해도 나머지는 받는다
                    print(f"[kr-extra] {sym} {key} 실패: {str(e)[:80]}")
                    v = None
                cache.put(sym, key, v)
            time.sleep(0.5)
        for key in ("revenue", "eps", "earnings", "analysts"):
            v = cache.get(sym, key)
            if v is None:
                continue
            if key == "revenue":
                out["revenue"]["series"][sym] = v
            elif key == "earnings":
                out["earnings"][sym] = v
            else:
                out["stocks"].setdefault(sym, {})[key] = v
    print(f"[kr-extra] 새로 받은 종목 {n_new}/{len(U.CANDIDATES)} (나머지 저장값)")
    try:   # DART 분기 매출이 있으면 그것으로 (2026-10-25 사용자: 1년치뿐인 Yahoo 대신)
        import collect_kr_dart
        for sym, rows in collect_kr_dart.run().items():
            if sum(1 for r in rows if r["yoy"] is not None) >= sum(1 for r in out["revenue"]["series"].get(sym) or [] if r.get("yoy") is not None):
                out["revenue"]["series"][sym] = rows
    except Exception as e:  # noqa: BLE001 — DART 가 막혀도 Yahoo 매출로 간다
        print(f"[kr-extra] DART 실패 — Yahoo 매출로: {str(e)[:120]}")
    try:   # 돈을 어디에 쓰나 · 이익 줄 — DART 손익 · 현금흐름 분기 표 (2026-11-04 사용자, 미국 extra["capex"] 와 같은 모양). 실패하면 그 카드만 없다
        import collect_kr_fin
        out["capex"] = collect_kr_fin.run()
    except Exception as e:  # noqa: BLE001
        print(f"[kr-extra] DART 손익 · 현금흐름 실패: {str(e)[:120]}")
    try:   # 기업 정보 탭 — DART 기업개황 (2026-10-29 P84)
        import collect_kr_dart
        out["company"] = collect_kr_dart.company()
    except Exception as e:  # noqa: BLE001
        print(f"[kr-extra] 기업개황 실패: {str(e)[:120]}")
    pe = cache.blob("pair_earnings", 7)   # 미국 연결 종목 실적일 — 주 1회 (2026-11-12, 전에는 실행마다 20여 회)
    if pe is not None:
        out["pair_earnings"] = pe
    else:
        for us in sorted({u for v in U.PAIRS.values() for u in v[0]}):   # 미국과 연결 종목 실적일 (캘린더)
            try:
                out["pair_earnings"][us] = [{"day": x["day"]} for x in _earn_dates(yf.Ticker(us))]
            except Exception as e:  # noqa: BLE001
                print(f"[kr-extra] {us} 실적일 실패: {str(e)[:80]}")
            time.sleep(0.5)
        cache.put_blob("pair_earnings", out["pair_earnings"])
    try:   # 추정치 · 등급 · 목표가 날짜별 기록 (K16, 2026-10-31 — 옛 extra.json 은 매일 덮어써 이력이 안 남았다)
        sys.path.insert(0, os.path.join(BASE, ".."))
        import est_history
        est_history.append(os.path.join(BASE, "data", "est_history.json"), out["day"], out["stocks"])
    except Exception as e:  # noqa: BLE001
        print(f"[kr-extra] 추정치 기록 실패: {str(e)[:120]}")
    cache.save("한국 종목")
    os.makedirs(os.path.dirname(EXTRA), exist_ok=True)
    with open(EXTRA, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    n_rev = sum(1 for v in out["revenue"]["series"].values() if any(r.get("yoy") is not None for r in v))
    print(f"[kr-extra] 매출 {n_rev} · 이익 예상 {sum(1 for v in out['stocks'].values() if (v.get('eps') or {}).get('current'))} · 실적일 {len(out['earnings'])} · 연결 미국 {len(out['pair_earnings'])}")
    return out


def load():
    try:
        with open(EXTRA, encoding="utf-8") as f:
            out = json.load(f)
    except (OSError, ValueError):
        out = {}
    if not out.get("company"):   # 기업개황은 따로 캐시(dart_company.json) — --cached 그리기에서도 쓴다
        import collect_kr_dart
        out["company"] = (collect_kr_dart._load(collect_kr_dart.COMPANY) or {}).get("map") or {}
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    run()
