"""사건 전 전망(kind = pre)의 결과 칸 채우기 — 사건 날이 지나면 미리 적은 두 갈래 중 어느 쪽인지 코드가 정한다 (2026-11-22 사용자).

옛: forecast_daily 가 fc["cond_known"] 을 읽기만 했고 채우는 코드가 없었다 → 엔비디아 실적(11.17) 뒤 판정이 11.16 에서 멈췄다.

규칙 (사람이 고르지 않는다 — 등록 때 적은 갈래 · 실적 달력 earnings.csv 와 같은 기준):
- 실적 · 갈래 ["예상을 크게 넘음", "그 밖"] = 주당순이익 서프라이즈 5% 이상이면 1, 아니면 2
  (build_calendar_misc.band 의 `크게 상회` = surprise_pct ≥ 5, market_prob `최근 12번 중 크게 넘은 10번` 도 이 기준)
- 자료 = yfinance earnings_dates 의 EPS Estimate · Reported EPS · Surprise(%) — earnings.csv 지난 값(5.54 · 6.16)과 같은 곳
- 한 번 정하면 고정(results.json) — 다시 받지 않는다. 값을 못 받으면 비워 두고 다음 실행에 다시(추정으로 채우지 않음)
- 규칙이 없는 갈래(FOMC 등)는 건너뛰고 `규칙 없음` 으로 알린다 → forecast_alerts 가 운영 알림
"""
import datetime as dt
import json
import os
import re

BIG_BEAT = 5.0   # 크게 넘음 = 주당순이익 서프라이즈 5% 이상 (earnings.csv `크게 상회` 와 같은 값)
EARN_OUTCOMES = ["예상을 크게 넘음", "그 밖"]
NAME_SYM = {"엔비디아": "NVDA", "브로드컴": "AVGO", "AMD": "AMD", "마이크론": "MU", "애플": "AAPL", "마이크로소프트": "MSFT",
            "아마존": "AMZN", "알파벳": "GOOGL", "구글": "GOOGL", "메타": "META", "테슬라": "TSLA", "인텔": "INTC", "퀄컴": "QCOM"}


def path_of(state_dir):
    return os.path.join(state_dir, "records", "forecasts", "results.json") if state_dir else None


def load(state_dir):
    p = path_of(state_dir)
    try:
        return json.load(open(p, encoding="utf-8")) if p and os.path.exists(p) else {}
    except (OSError, ValueError):
        return {}


def save(state_dir, res):
    p = path_of(state_dir)
    if not p:
        return
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, sort_keys=True)


def earn_symbol(fc):
    """`11.17 엔비디아 실적` → NVDA. fc["event_symbol"] 이 있으면 그것."""
    if fc.get("event_symbol"):
        return fc["event_symbol"]
    m = re.search(r"(\S+)\s*실적$", fc.get("event", ""))
    return NAME_SYM.get(m.group(1)) if m else None


def eps_surprise(sym, day):
    """그 발표일(미국 날짜)의 {eps_est, eps_actual, surprise_pct} — 실제 값이 아직 없으면 None."""
    import yfinance as yf
    ed = yf.Ticker(sym).get_earnings_dates(limit=12)
    if ed is None or ed.empty:
        return None
    for ts, row in ed.iterrows():
        if ts.strftime("%Y-%m-%d") != day:
            continue
        est, act, sp = row.get("EPS Estimate"), row.get("Reported EPS"), row.get("Surprise(%)")
        if act is None or act != act or est is None or est != est:   # NaN = 아직 발표 전 · 자료 안 들어옴
            return None
        if sp is None or sp != sp:
            sp = (float(act) / float(est) - 1) * 100 if float(est) else None
        return {"eps_est": round(float(est), 4), "eps_actual": round(float(act), 4), "surprise_pct": round(float(sp), 2) if sp is not None else None}
    return None


def fill(pub, state_dir, today=None):
    """사건 날이 지난 사건 전 전망마다 결과 칸을 채운다. fc["cond_known"] 을 넣고 results.json 에 고정.
    돌려주는 값 = 못 채운 전망 [(slug, 까닭)] — forecast_alerts 가 운영 알림으로 올린다."""
    today = today or dt.date.today().isoformat()
    res = load(state_dir)
    pending, changed = [], False
    for _, fc in pub:
        if fc.get("kind") != "pre" or not fc.get("event_day") or fc.get("cond_known") or fc.get("ambiguous"):
            continue
        slug = fc["slug"]
        if slug in res and res[slug].get("cond"):
            fc["cond_known"] = res[slug]["cond"]
            continue
        if fc["event_day"] >= today:   # 사건 전 — 미국 장 마감 뒤 발표는 다음 날 아침(한국)에 값이 들어온다
            continue
        if fc.get("outcomes") != EARN_OUTCOMES:
            pending.append((slug, f"{fc.get('event')} 결과를 정할 규칙이 없음(지금은 실적 `크게 넘음 · 그 밖` 만)"))
            continue
        sym = earn_symbol(fc)
        if not sym:
            pending.append((slug, f"{fc.get('event')} 종목을 못 찾음"))
            continue
        try:
            v = eps_surprise(sym, fc["event_day"])
        except Exception as e:  # noqa: BLE001
            pending.append((slug, f"{fc.get('event')} 주당순이익 받기 실패"))
            continue
        if not v or v.get("surprise_pct") is None:
            pending.append((slug, f"{fc.get('event')} 실제 주당순이익을 아직 못 받음"))
            continue
        cond = 1 if v["surprise_pct"] >= BIG_BEAT else 2
        res[slug] = {"cond": cond, "outcome": EARN_OUTCOMES[cond - 1], "symbol": sym, "event_day": fc["event_day"], **v,
                     "rule": f"주당순이익 서프라이즈 {BIG_BEAT:g}% 이상 = 크게 넘음", "src": "yfinance earnings_dates",
                     "recorded_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        fc["cond_known"] = cond
        changed = True
        print(f"[forecast] 결과 채움 {slug}: {sym} 주당순이익 예상 {v['eps_est']} · 실제 {v['eps_actual']} · {v['surprise_pct']:+.2f}% → {EARN_OUTCOMES[cond - 1]}")
    if changed:
        save(state_dir, res)
    return pending


# ---------------------------------------------------------------- 판정 날 겹침 (2026-11-22 사용자 1~3)
# 판정이 난 날, 결과 뒤 첫 반응일이 아닌 날에 하루 움직임이 기준(fc line) 넘게 컸고 그날 관련 Hot Issue 가 hot 이면 → 겹침.
# ① 그날 줄에 겹침 표시 ② 판정은 숫자대로 쓰되 이유는 "실적만의 결과라고 볼 수 없습니다" ③ 성적표는 `여러 사건이 겹친 전망` 으로 따로 센다.
# 사람이 고르지 않는다 — 이름 = 상태 기록 records/issues/{ID}.jsonl 의 hot, 여럿이면 뉴스가 평소보다 많이 늘어난(n48 ÷ base48) 순.
# 관련 = Hot Issue 가 보는 계열(Hot Issue 기준 가격 · 업종 — mock_issue_watch TL_REF · mock_stock_issue SECTOR 와 같은 값)이 전망 계열과 같을 때.
ISSUE_SERIES = {"NVDA_CEO": ("엔비디아 CEO 사임", {"sox", "NVDA", "^SOX"}), "EXPORT": ("반도체 수출 통제", {"sox", "^SOX"}),
                "TARIFF": ("관세", {"spx", "^GSPC"}), "IRAN": ("이란 전쟁", {"spx", "^GSPC"})}


def hot_issues(state_dir, days):
    """그 날들(한국 날짜 기록)에 hot 이던 Hot Issue [(id, 이름, 늘어난 배수)] — 늘어난 배수 큰 순."""
    out = {}
    for iid, (name, _) in ISSUE_SERIES.items():
        p = os.path.join(state_dir or "", "records", "issues", f"{iid}.jsonl")
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            try:
                j = json.loads(line)
            except ValueError:
                continue
            if j.get("day") in days and j.get("hot"):
                x = (j.get("n48") or 0) / max(j.get("base48") or 1, 1)
                out[iid] = (name, max(x, out.get(iid, (name, 0.0))[1]))
    return sorted(((i, n, x) for i, (n, x) in out.items()), key=lambda t: -t[2])


def mark_overlap(fc, st, state_dir, sub):
    """판정 난 날이 다른 사건과 겹쳤으면 st 를 고친다(줄 표시 · 이유 문장 · result["overlap"]). 겹침이면 사건 이름, 아니면 None."""
    import hypo_pages as H
    if fc.get("kind") != "pre":   # 급락 · 급등 뒤에 적은 전망은 그 큰 움직임이 바로 맞히려던 것 — 사건 전에 적은 전망(실적 · 발표)만 (forecast-2 11.09 반등이 걸렸다)
        return None
    res = st.get("result") or {}
    d = res.get("day")
    if not d or res.get("unscored") or not st.get("log") or st["log"][-1].get("key") not in ("hit", "miss"):
        return None
    days, rel = st.get("days") or [], st.get("rel_series") or []
    if d not in days:
        return None
    i = days.index(d)
    prev = next((rel[k] for k in range(i - 1, -1, -1) if rel[k] is not None), None)
    if prev is None or rel[i] is None:
        return None
    ev = fc.get("event_day")
    after = [x for x in days if ev and x > ev]
    if after and d == after[0]:   # 결과 뒤 첫 반응일 = 그 사건 자체의 반응 — 겹침이 아니다
        return None
    if abs(rel[i] - prev) < float(fc.get("line") or 3.0):   # 하루 움직임이 기준보다 작으면 그날 하루 사건 탓으로 보지 않는다
        return None
    nd = (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()   # 미국 종가는 한국 다음 날 아침 기록에 같이 잡힌다
    hits = [n for iid, n, _ in hot_issues(state_dir, {d, nd}) if sub in ISSUE_SERIES[iid][1]]
    s = 1 if rel[i] - prev > 0 else -1
    names = " · ".join(hits) if hits else f'{fc.get("subject", "")} {H.SHOCK[s]}'.strip()
    e = st["log"][-1]
    sc = fc["scenarios"][(res.get("crossed") or 1) - 1]
    what = "실적" if "실적" in fc.get("event", "") else "그 사건"
    verdict = f'‘{sc["name"]}’{H._ig(sc["name"])} 맞았습니다' if e["key"] == "hit" else "틀렸습니다"
    e["text"] = (f'{H.move_text(fc, e["rel"])}. 미리 적은 기준으로는 {verdict}. '
                 f'다만 결과가 나온 뒤 {H.md(d)} {names} 소식이 겹쳐, {what}만의 결과라고 볼 수 없습니다.')
    e["overlap"] = {"event": names}
    res["overlap"] = {"day": d, "event": names}
    print(f"[forecast] 판정 날 겹침 {fc['slug']}: {d} {names} → 성적표 따로")
    return names


# ---------------------------------------------------------------- 멈춘 전망 잡기 (2026-11-22 사용자 2번: 엔비디아 전망이 11.16 에서 멈췄는데 운영 페이지 · 알림에 안 잡혔다)
STALL_DAYS = 2   # 판정이 안 난 전망의 마지막 기록이 그 전망 시세 마지막 날보다 이 거래일 수 넘게 뒤처지면 `판정 멈춤`


def stalled(pub, states, pending):
    """판정이 안 난 전망 중 멈춘 것 [{"title", "slug", "why"}] — 운영 페이지(hypo.json ops) · Slack(forecast_alerts.stalled) 이 같이 쓴다.
    ① 결과 칸이 비어 판정을 못 이어 감(fill 의 pending) ② 마지막 기록 뒤로 시세는 있는데 기록이 STALL_DAYS 거래일 넘게 없음."""
    import hypo_pages as H
    why = {s: w for s, w in pending}
    out = []
    for _, fc in pub:
        slug = fc["slug"]
        st = states.get(slug) or {}
        if st.get("result"):
            continue
        log = [e for e in st.get("log") or [] if e.get("day")]
        days = st.get("days") or []
        last = str(log[-1]["day"])[:10] if log else None
        lag = sum(1 for d in days if last and d > last)
        w = why.get(slug)
        if not w and lag > STALL_DAYS:
            w = f"판정 기록이 {H.md(last)} 뒤로 {lag}거래일 비어 있음"
        elif w and lag:
            w = f"{w}, 기록이 {H.md(last)} 에서 {lag}거래일째 멈춤"
        if w:
            out.append({"title": fc["title"], "slug": slug, "why": w})
    if "*" in why:
        out.append({"title": "결과 채우기", "slug": "", "why": why["*"]})
    return out
