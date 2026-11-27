"""돈이 어디로 가나 — 업종 11 · 세부 업종 20 · 시장(S&P 500) 의 하루 한 줄 기록.

    python experiments/flow_records.py --state "$STATE_DIR/radar"      # 정기 실행(미국 장 마감 뒤 본 실행, 하루 한 번)
    python experiments/flow_records.py --dry                           # 로컬 확인 — 표만 찍고 쓰지 않는다
    python experiments/flow_records.py --dry --no-fund                 # 야후 순자산 호출 없이 가격 계산만

왜 지금: ETF 순자산 · 기준가의 지난 값은 무료로 다시 받을 수 없다 — 쌓기 시작한 날부터만 "실제로 들어오고 나간 돈"을 셀 수 있다.
화면 · AI 없음. 기록만 쌓고, 무엇을 독자에게 보일지는 기록이 쌓인 뒤 정한다.

읽는 것: 레이더가 이미 받은 일봉(stock-radar/data/snapshot.json, 2년) — 새 가격 수집 없음(세부 업종 티커는 collect.py 묶음 요청에 얹었다).
새로 받는 것: 야후 ETF 정보(순자산 · 기준가) 32개 × 하루 한 번. 못 받은 ETF 는 fund 칸을 비운다 — **전날 값을 복사하지 않는다**(복사하면 '돈이 안 움직인 날'로 읽힌다).

쓰는 곳: record_store `flows` — {state}/records/flows/{YYYY}.jsonl, 한 줄 = 한 ETF 의 하루. id = flow/<ETF>.
    price     시장 대비 수익 차이(%p) 5 · 20 · 60 · 120거래일, 하루 등락, 200일 평균선 위인지
    cell      네 칸 — 주도 · 약화 · 소외 · 개선 (9월 연구 signal-study/sectors.py 와 같은 식, 다만 여기는 ETF 가격 기준):
              level = (ETF ÷ 시장) ÷ 그 60일 평균 − 1,  mom = level − 10거래일 전 level
              level>0 · mom>0 주도 | level>0 · mom≤0 약화 | level≤0 · mom≤0 소외 | level≤0 · mom>0 개선
    down · up 최근 60거래일 중 시장이 내린 날 · 오른 날만 골라, 그날들의 시장 대비 하루 차이 평균(%p)과 시장보다 나았던 날 수.
              down.big = 시장이 1% 넘게 내린 날만. "시장이 빠질 때 더 빠지나 · 버티나".
    turnover  거래대금(종가 × 거래량) 20일 평균, 같은 층 안 비중(%), 최근 5일 ÷ 60일 평균(배) — 관심이 몰리는 곳
    fund      야후 순자산(aum) · 기준가(nav) · 좌수 추정(units = aum ÷ nav). 원값만 — 순유입은 읽는 쪽이 계산한다:
              순유입 ≈ (오늘 units − 어제 units) × 오늘 nav.  야후 sharesOutstanding 칸은 순자산과 안 맞아(11-20 XLK · SMH 확인) 참고로만 둔다.
              **야후가 순자산을 날마다 고치는지는 쌓아 봐야 안다** — 며칠째 같은 값이면 운용사 파일(스테이트 스트리트 · 아이셰어즈 · 반에크 · 퍼스트 트러스트)로 바꾼다.
나중 결과(그 뒤 며칠 수익)는 쓰지 않는다 — 읽는 쪽이 일봉으로 계산한다(record_store 원칙). 실패해도 다른 단계는 계속.
"""

import argparse
import datetime
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import record_store  # noqa: E402
import taxonomy as TX  # noqa: E402

KST = datetime.timezone(datetime.timedelta(hours=9))
SNAP = os.path.join(_HERE, "stock-radar", "data", "snapshot.json")
BENCH = "SPY"
REL_DAYS = (5, 20, 60, 120)
LEVEL_DAYS, MOM_DAYS = 60, 10      # 네 칸 — sectors.py 와 같은 창
WINDOW = 60                        # 시장이 내린 날 · 오른 날을 고르는 창(거래일)
BIG_DOWN = -0.01                   # 시장이 1% 넘게 내린 날
FEED_NAME = "업종 · 세부 업종 ETF 순자산 (야후)"

LAYERS = ([(BENCH, "S&P 500", "시장", None)]
          + [(e, n, "업종", None) for e, n in TX.SECTORS.items()]
          + [(e, n, "세부 업종", p) for e, (n, p) in TX.RECORD_SUBS.items()])


def _r(x, n=2):
    return None if x is None else round(float(x), n)


def _series(bars):
    """일봉 → {날짜: (조정 종가, 종가, 거래량)}. 조정 종가가 비면 종가."""
    return {b["day"]: (b.get("adj") or b["close"], b["close"], b.get("volume") or 0.0) for b in bars or [] if b.get("close")}


def price_row(etf, bench):
    """etf · bench = _series 결과. 시장과 같은 날만 맞춰 센다. 시장 마지막 날 봉이 없으면 None(늦은 봉 — 어긋난 날끼리 비교하지 않는다)."""
    days = sorted(set(etf) & set(bench))
    if len(days) < LEVEL_DAYS + MOM_DAYS + 1 or days[-1] != max(bench):
        return None
    e = [etf[d][0] for d in days]
    b = [bench[d][0] for d in days]
    out = {"as_of": days[-1], "price": {"close": _r(etf[days[-1]][1]), "day_pct": _r((e[-1] / e[-2] - 1) * 100)}}
    for n in REL_DAYS:
        if len(days) > n:
            out["price"][f"ret{n}"] = _r((e[-1] / e[-1 - n] - 1) * 100)
            out["price"][f"rel{n}"] = _r(((e[-1] / e[-1 - n]) - (b[-1] / b[-1 - n])) * 100)
    if len(days) >= 200:
        out["price"]["above200"] = bool(e[-1] > sum(e[-200:]) / 200)

    ratio = [x / y for x, y in zip(e, b)]

    def level(end):   # end = 끝 위치(파이썬 조각 끝, 0 = 오늘까지)
        w = ratio[len(ratio) - end - LEVEL_DAYS:len(ratio) - end]
        return w[-1] / (sum(w) / len(w)) - 1

    lv, mom = level(0), level(0) - level(MOM_DAYS)
    out["level"], out["mom"] = _r(lv * 100, 3), _r(mom * 100, 3)
    out["cell"] = ("주도" if mom > 0 else "약화") if lv > 0 else ("개선" if mom > 0 else "소외")

    de = [e[i] / e[i - 1] - 1 for i in range(len(e) - WINDOW, len(e))]
    db = [b[i] / b[i - 1] - 1 for i in range(len(b) - WINDOW, len(b))]

    def side(pick):
        ex = [x - y for x, y in zip(de, db) if pick(y)]
        return {"n": len(ex), "avg": _r(sum(ex) / len(ex) * 100, 3) if ex else None, "better": sum(1 for x in ex if x > 0)}

    out["down"] = dict(side(lambda y: y < 0), big=side(lambda y: y <= BIG_DOWN))
    out["up"] = side(lambda y: y > 0)

    dv = [etf[d][1] * etf[d][2] for d in days]
    out["turnover"] = {"avg20": _r(sum(dv[-20:]) / 20, 0), "x5_60": _r((sum(dv[-5:]) / 5) / (sum(dv[-60:]) / 60)) if sum(dv[-60:]) else None}
    return out


def fetch_fund(sym, tries=2):
    """야후 ETF 정보 → 순자산 · 기준가 원값. 못 받으면 None."""
    import yfinance as yf
    for k in range(tries):
        try:
            i = yf.Ticker(sym).info or {}
            aum, nav = i.get("totalAssets"), i.get("navPrice")
            if aum and nav:
                return {"aum": float(aum), "nav": float(nav), "units": round(float(aum) / float(nav), 1), "yahoo_shares": i.get("sharesOutstanding")}
        except Exception as ex:  # noqa: BLE001
            print(f"[flow] {sym} 순자산 받기 실패({k + 1}): {str(ex)[:120]}")
        time.sleep(2)
    return None


def build(snap, with_fund=True):
    bars = snap.get("bars") or {}
    bench = _series(bars.get(BENCH))
    if not bench:
        raise SystemExit("[flow] 시장(SPY) 일봉 없음 — 기록하지 않는다")
    today = datetime.datetime.now(KST).strftime("%Y-%m-%d")
    rows, late = [], []
    for etf, name, layer, parent in LAYERS:
        p = price_row(_series(bars.get(etf)), bench)
        if not p:
            late.append(etf)
            continue
        row = {"date": today, "source": "radar", "id": f"flow/{etf}", "target": etf, "name": name, "layer": layer, "scheme": TX.VERSION, **p}
        if layer == "시장":   # 시장 줄은 자기 자신과의 비교라 네 칸 · 내린 날 성적이 뜻이 없다 — 가격 · 거래대금 · 순자산만
            for k in ("level", "mom", "cell", "down", "up"):
                row.pop(k, None)
            row["price"] = {k: v for k, v in row["price"].items() if not k.startswith("rel")}
        if parent:
            row["parent"] = parent
        rows.append(row)
    for layer in ("업종", "세부 업종"):   # 같은 층 안 거래대금 비중
        grp = [r for r in rows if r["layer"] == layer]
        tot = sum(r["turnover"]["avg20"] or 0 for r in grp)
        for r in grp:
            r["turnover"]["share"] = _r((r["turnover"]["avg20"] or 0) / tot * 100) if tot else None
    got = 0
    if with_fund:
        for r in rows:
            f = fetch_fund(r["target"])
            if f:
                r["fund"], got = f, got + 1
            time.sleep(0.4)
    return rows, late, got


def _table(rows):
    print(f"{'ETF':6}{'이름':14}{'칸':4}{'20일':>8}{'60일':>8}{'내린 날':>9}{'오른 날':>9}{'대금배':>7}{'순자산(억$)':>12}")
    for r in sorted(rows, key=lambda r: (r["layer"] != "시장", r["layer"] != "업종", -(r["price"].get("rel20") or 0))):
        f = r.get("fund")
        print(f"{r['target']:6}{r['name'][:10]:14}{r.get('cell', '-'):4}{r['price'].get('rel20', 0):>+9.1f}{r['price'].get('rel60', 0):>+9.1f}"
              f"{((r.get('down') or {}).get('avg') or 0):>+10.2f}{((r.get('up') or {}).get('avg') or 0):>+10.2f}{(r['turnover']['x5_60'] or 0):>8.2f}{(f['aum'] / 1e8 if f else float('nan')):>12.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", help="record_store 상태 폴더 (정기 실행: $STATE_DIR/radar)")
    ap.add_argument("--snapshot", default=SNAP)
    ap.add_argument("--no-fund", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    with open(a.snapshot, encoding="utf-8") as f:
        snap = json.load(f)
    rows, late, got = build(snap, with_fund=not a.no_fund)
    _table(rows)
    as_of = max((r["as_of"] for r in rows), default="")
    print(f"[flow] {len(rows)}/{len(LAYERS)}줄 · 기준 거래일 {as_of} · 순자산 {got}개" + (f" · 봉 없음 · 늦음: {', '.join(late)}" if late else ""))
    if a.dry or not a.state:
        return
    n = record_store.append(a.state, "flows", rows)
    print(f"[flow] 기록 {n}줄 → {a.state}/records/flows")
    if not a.no_fund:
        try:
            import feed_log
            ok = got >= len(rows) / 2 and bool(rows)
            feed_log.feed(FEED_NAME, ok, label=f"{got}/{len(LAYERS)}개", data_date=as_of, got_new=got > 0, every_days=2,
                          error="" if ok else f"순자산 {got}/{len(LAYERS)}개만 받음", detail=("늦은 봉: " + ", ".join(late)) if late else "")
        except Exception as ex:  # noqa: BLE001
            print(f"[flow] 주기 자료 기록 실패: {ex}")


if __name__ == "__main__":
    main()
