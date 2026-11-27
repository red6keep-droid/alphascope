"""종목 `의견` 탭 맨 위 요약 문단의 하루 변화 재료 — 지난 기록일 값을 읽고, 오늘 보여 준 값을 기록한다.

요약 문단(render_html.opinions_summary)은 수준(`상승 쪽`)이 아니라 지난 기록일과 달라진 것을 말한다. 비교 대상 = 이 종목의 지난 기준 거래일 값.
    평균 목표가   records/verdicts 의 {sym}/analysts 줄(value.pt_mean) — 종목 기록이 시작된 날부터 있다
    Newfact 신호  records/opinion 의 {sym}/opinion 줄(sig) — 화면이 그날 실제로 보여 준 단기 신호. 판정 줄로 다시 계산하지 않는다
                  (기록 단계는 화면보다 먼저 돌아 방송 · 뉴스 의견 재료가 화면과 다를 수 있다)
    방송 새 의견  같은 줄의 picks(그날 화면에 있던 의견 id) — 지난 기록일까지 한 번도 없던 id 가 오늘의 새 의견

    records/opinion/{연}-{월}.jsonl   {date(실행 날짜 KST), as_of(기준 거래일), source, id "{sym}/opinion", sym, name, sig(+1 · 0 · −1), pt_mean, picks[], scheme}
같은 (date, id) 는 바꾼다(record_store). 화면을 다 그린 뒤 save() — 받기 실행에서만(main), --cached · 목업은 읽기만.
"""
import datetime

import record_store
import signal_groups as SG
import stock_records

KIND = "opinion"
PT_MIN = 0.001   # 평균 목표가가 0.1% 넘게 달라지면 바뀐 것으로 말한다
_HIST = {}    # state_dir → {"pt": {sym: {as_of: 값}}, "op": {sym: {as_of: 줄}}}
_TODAY = {}   # state_dir → 오늘 줄


def _load(state_dir, day):
    if state_dir in _HIST:
        return _HIST[state_dir]
    pt, op = {}, {}
    years = ([int(day[:4]) - 1] if day[5:7] == "01" else []) + [int(day[:4])]   # 1월에는 지난해 끝도 본다
    for y in years:
        for r in record_store.read(state_dir, "verdicts", y):
            if str(r.get("id") or "").endswith("/analysts"):
                v = (r.get("value") or {}).get("pt_mean")
                if v:
                    pt.setdefault(r.get("sym"), {})[str(r.get("as_of") or r.get("date"))] = float(v)
        for r in record_store.read(state_dir, KIND, y):
            op.setdefault(r.get("sym"), {})[str(r.get("as_of") or r.get("date"))] = r
    _HIST[state_dir] = {"pt": pt, "op": op}
    return _HIST[state_dir]


def signal_of(items):
    """함께 보기 줄 → 단기 신호(+1 · 0 · −1 · None). 요약 문단과 같은 계산."""
    rows = [x for x in items or [] if x and x[1]]
    return SG.horizon_votes(rows)["단기"][0] if rows else None


def for_stock(state_dir, sym, day):
    """→ {"day", "pt": [(기준일, 평균 목표가)], "sig": [(기준일, 신호)], "seen": 지난 기록일까지 화면에 있던 방송 의견 id 묶음 또는 None}.
    전부 오늘 기준일(day)보다 앞선 것만, 날짜순. 기록을 못 읽으면 None — 요약 문단은 변화 말 없이 오늘 값만 말한다."""
    if not state_dir or not day:
        return None
    try:
        h = _load(state_dir, day)
    except Exception as e:  # noqa: BLE001 — 기록을 못 읽어도 페이지는 만든다
        print(f"::warning::[op_change] 기록 읽기 실패 (변화 말 없이): {e!r}")
        return None
    ops = sorted((d, r) for d, r in (h["op"].get(sym) or {}).items() if d < day)
    return {"day": day,
            "pt": sorted((d, v) for d, v in (h["pt"].get(sym) or {}).items() if d < day),
            "sig": [(d, r["sig"]) for d, r in ops if r.get("sig") is not None],
            "seen": {i for _, r in ops for i in r.get("picks") or []} if ops else None}


def note(state_dir, source, sym, name, day, sig, pt_mean, picks):
    """오늘 화면이 보여 준 값 한 줄 — save() 때 쓴다."""
    if not state_dir or not day:
        return
    today = datetime.datetime.now(stock_records.KST).strftime("%Y-%m-%d")
    _TODAY.setdefault(state_dir, {})[sym] = {
        "date": today, "as_of": day, "source": source, "id": f"{sym}/opinion", "target": sym, "sym": sym, "name": name,
        "sig": sig, "pt_mean": pt_mean, "picks": sorted({stock_records.pick_id(p) for p in picks or []}), "scheme": SG.SCHEME}


def save(state_dir):
    rows = list((_TODAY.pop(state_dir, None) or {}).values())
    return record_store.append(state_dir, KIND, rows, monthly=True) if rows else 0
