"""한국 종목 탭 재료 — `실적과 기대`(분기 매출 · 1주당 이익 예상) · `캘린더`(실적 발표일 · 미국과 연결 종목 실적일). yfinance (2026-10-25).

미국 종목(stock-radar collect_extra)과 같은 칸 모양으로 둔다 — 카드 판정 · 그림은 미국 카드 함수(analyze_tabs · nvda render_html)를 그대로 쓴다.
- 매출 : OpenDART 분기 매출(collect_kr_dart — 4년치, 1년 전 대비 8분기). DART 에 없는 종목(은행 · 보험 — 매출액 계정 없음)은 Yahoo quarterly_income_stmt(최근 5~6분기).
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


def run():
    import yfinance as yf
    out = {"day": datetime.date.today().isoformat(), "stocks": {}, "revenue": {"series": {}}, "earnings": {}, "pair_earnings": {}}
    for sym, *_ in U.CANDIDATES:
        t = yf.Ticker(sym)
        for key, f in (("revenue", lambda: _revenue(t)), ("eps", lambda: EX._eps(t)), ("earnings", lambda: _earn_dates(t))):
            try:
                v = f()
            except Exception as e:  # noqa: BLE001 — 한 칸이 실패해도 나머지는 받는다
                print(f"[kr-extra] {sym} {key} 실패: {str(e)[:80]}")
                continue
            if key == "revenue":
                out["revenue"]["series"][sym] = v
            elif key == "eps":
                out["stocks"][sym] = {"eps": v}
            else:
                out["earnings"][sym] = v
        time.sleep(0.5)
    try:   # DART 분기 매출이 있으면 그것으로 (2026-10-25 사용자: 1년치뿐인 Yahoo 대신)
        import collect_kr_dart
        for sym, rows in collect_kr_dart.run().items():
            if sum(1 for r in rows if r["yoy"] is not None) >= sum(1 for r in out["revenue"]["series"].get(sym) or [] if r.get("yoy") is not None):
                out["revenue"]["series"][sym] = rows
    except Exception as e:  # noqa: BLE001 — DART 가 막혀도 Yahoo 매출로 간다
        print(f"[kr-extra] DART 실패 — Yahoo 매출로: {str(e)[:120]}")
    try:   # 기업 정보 탭 — DART 기업개황 (2026-10-29 P84)
        import collect_kr_dart
        out["company"] = collect_kr_dart.company()
    except Exception as e:  # noqa: BLE001
        print(f"[kr-extra] 기업개황 실패: {str(e)[:120]}")
    for us in sorted({u for v in U.PAIRS.values() for u in v[0]}):   # 미국과 연결 종목 실적일 (캘린더)
        try:
            out["pair_earnings"][us] = [{"day": x["day"]} for x in _earn_dates(yf.Ticker(us))]
        except Exception as e:  # noqa: BLE001
            print(f"[kr-extra] {us} 실적일 실패: {str(e)[:80]}")
        time.sleep(0.5)
    os.makedirs(os.path.dirname(EXTRA), exist_ok=True)
    with open(EXTRA, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    n_rev = sum(1 for v in out["revenue"]["series"].values() if any(r.get("yoy") is not None for r in v))
    print(f"[kr-extra] 매출 {n_rev} · 이익 예상 {sum(1 for v in out['stocks'].values() if v['eps'].get('current'))} · 실적일 {len(out['earnings'])} · 연결 미국 {len(out['pair_earnings'])}")
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
