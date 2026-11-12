"""한국 전망 근거 — 이미 다른 페이지가 쓰는 한국 자료로 미국과 같은 칸(good · bad · open)을 채운다 (2026-11-12 사용자: "한국 전망은 근거가 약하지 않아?").

미국 근거 = 기사 요약 줄(AI 분류해 둔 news.json). 한국은 기사 수집이 없어 등록 · 타임라인 근거가 비었다(이유 카드는 가격 신호만).
새 수집 · AI 없이 붙는 한국 자료 넷:
  ① 한국 증시 방송 이슈 — media_feed(수집기가 이미 요약 줄 · 방향을 붙임, 한국 증시 리포트 뉴스 탭의 재료). 요약 두 줄 못 되는 것은 싣지 않는다(뉴스 형식 8절)
  ② 외국인 순매수 — kr-state flows.json(한국은행 ECOS, 한국 증시 리포트 `외국인은 사고 있나?` 카드). 평소보다 클 때 · 사흘 넘게 이어질 때만
  ③ 전날 밤 미국 — 이미 받는 미국 시세(반도체 지수 · S&P 500 · 나스닥). 기준보다 크게 움직였을 때만
  ④ 실적 공시 — kr-state dart_earn.json(DART 공시일). 좋고 나쁨은 공시 날짜만으로 모르니 향방미정(open)
줄 모양 = forecast_register.side_news 와 같다 {"t", "dir", "day", "src", "lv", "lines"?, "url"?} → 렌더(side_why · day_why_html · open_line)를 그대로 쓴다.
근거 줄은 판정에 쓰지 않는다 — 사실을 모아 보일 뿐(가이드라인 1절 4-2: 단일 변수 단언 금지).
"""
import datetime as dt
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXP = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_EXP)
KST = dt.timezone(dt.timedelta(hours=9))
CLOSE = "15:30"   # 한국 장 마감 — 그날 근거 = 전 거래일 마감 뒤 ~ 그날 마감까지

SECTOR_WORDS = {   # 업종 전망 대상 → 방송 이슈 주제에 이 낱말이 있으면 그 업종 이야기 (media_feed.KR_SECTOR_WORDS 의 업종 이름은 넓어 — 자동차 = 경기 소비재 — 따로 둔다)
    "091160.KS": ("반도체", "메모리", "HBM", "D램", "DRAM", "낸드", "파운드리", "삼성전자", "하이닉스"),
    "091170.KS": ("은행", "금융지주", "대출", "예대", "밸류업"),
    "091180.KS": ("자동차", "완성차", "현대차", "기아", "車"),
    "117460.KS": ("정유", "석유화학", "화학", "유가", "에너지"),
}
US_LINK = {   # 한국 대상 → 전날 밤 미국 비교 (기호, 이름, 기준 %)
    "semi": ("^SOX", "미국 반도체 지수", 2.0),
    "^KS11": ("^GSPC", "S&P 500", 1.0),
    "^KQ11": ("^IXIC", "나스닥", 1.5),
}
FLOW_MULT, FLOW_STREAK = 1.5, 3   # 외국인 = 최근 20거래일 크기 중앙값의 1.5배 넘거나 같은 쪽 사흘 이상


# ---------------------------------------------------------------- 자료 읽기 (상태 저장소 · Firestore — 새 수집 아님)

def _kr_state(path, state_dir=None):
    """kr-state 의 파일 — CI 는 KR_STATE_DIR(체크아웃), 로컬은 git 의 state/kr-state 브랜치, 둘 다 없으면 저장소 파일."""
    base = os.environ.get("KR_STATE_DIR")
    if base and os.path.exists(os.path.join(base, path)):
        with open(os.path.join(base, path), encoding="utf-8") as f:
            return json.load(f)
    try:
        raw = subprocess.run(["git", "show", f"state/kr-state:{path}"], cwd=_ROOT, capture_output=True, check=True).stdout
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        p = os.path.join(_ROOT, path)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    return None


def _kr_state_text(path):
    try:
        return subprocess.run(["git", "show", f"state/kr-state:{path}"], cwd=_ROOT, capture_output=True, check=True).stdout.decode("utf-8")
    except Exception:  # noqa: BLE001
        base = os.environ.get("KR_STATE_DIR") or _ROOT
        p = os.path.join(base, path)
        return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


CTX = None   # forecast_daily 가 한 번 읽어 둔다 — forecast_register.reasons(한국 등록) · attach_why 가 같이 쓴다


def fc_of_w(w):
    """자동 등록 감시 목록 한 줄(w) → kr_why 가 읽는 전망 모양."""
    return {"series": {"sub": w["sym"], "mkt": w.get("mkt")}, "target": "stock" if w.get("stock") else "index", "tags": [w.get("tag")], "subject": w["name"]}


def load_ctx(today, px=None):
    """한 번만 읽어 전망 여럿이 같이 쓴다. today = 실행 날(KST 날짜)."""
    sys.path.insert(0, _EXP)
    ctx = {"media": [], "flows": {}, "dart": {}, "px": px or {}}
    try:
        import media_feed as mf
        rows = mf.rows(mf.load(today, days=10))
        ctx["media"] = rows
        ctx["mf"] = mf
    except Exception as e:  # noqa: BLE001
        print(f"[kr_why] 방송 읽기 실패 — 방송 줄 없이: {type(e).__name__}")
    fl = _kr_state("experiments/kr-stocks/data/flows.json") or {}
    ctx["flows"] = {k: {r["day"]: r["v"] for r in v} for k, v in (fl.get("daily") or {}).items() if k.startswith("foreign_")}
    ctx["dart"] = (_kr_state("experiments/kr-stocks/data/dart_earn.json") or {}).get("days") or {}
    ctx["est"] = _kr_state("experiments/kr-stocks/data/est_history.json") or {}   # 애널리스트 평균 목표가 · 이익 예상 (한국 종목 페이지가 매일 쌓음)
    ctx["verdicts"] = [json.loads(x) for x in _kr_state_text(f"experiments/kr-stocks/data/records/verdicts/{today[:4]}.jsonl").splitlines() if x.strip()]   # 알파스코프 신호 (한국 종목 페이지 판정 기록)
    return ctx


# ---------------------------------------------------------------- 대상 · 창

def target(fc):
    """→ (기호, 종류 index · sector · stock, 종목 코드)."""
    sym = (fc.get("series") or {}).get("sub") or ""
    kind = "stock" if fc.get("target") == "stock" else ("sector" if sym in SECTOR_WORDS else "index")
    return sym, kind, sym.split(".")[0] if kind == "stock" else None


def _utc_bound(day):
    """그날 한국 장 마감(KST) → UTC 'YYYY-MM-DDTHH:MM' (방송 published_at 과 비교)."""
    t = dt.datetime.fromisoformat(f"{day}T{CLOSE}").replace(tzinfo=KST).astimezone(dt.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M")


def _kst_day(utc):
    try:
        return dt.datetime.fromisoformat(str(utc)[:19]).replace(tzinfo=dt.timezone.utc).astimezone(KST).strftime("%Y-%m-%d")
    except ValueError:
        return str(utc)[:10]


def _eok(v):
    """억 원 → `3조 4,039억 원`."""
    jo, eok = divmod(abs(int(round(v))), 10000)
    if jo and not eok:
        return f"{jo}조 원"
    return (f"{jo}조 " if jo else "") + f"{eok:,}억 원"


# ---------------------------------------------------------------- 자료별 줄

def _broadcast(fc, lo, hi, ctx):
    mf = ctx.get("mf")
    if not mf:
        return []
    sym, kind, code = target(fc)
    a, b = _utc_bound(lo), _utc_bound(hi)
    rows = [r for r in ctx["media"] if a < str(r["published_at"])[:16] <= b]
    if kind != "stock":
        rows = [r for r in rows if mf.is_korea(r)]   # 시장 · 업종 = 한국 증시 내용만 (미국 은행 뉴스가 한국 은행에 붙지 않게)
    else:   # 종목 = 한국 증시 내용이거나 한국 회사를 직접 든 방송만 — 미국 반도체 업종 방송(CNBC · 블룸버그)은 `전날 밤 미국 반도체 지수` 줄이 대신한다 (2026-11-12 목업: 삼성전자 46줄 대부분이 미국 방송)
        rows = [r for r in rows if mf.is_korea(r) or any(mf.kr_code(t) for t in r.get("tickers") or [])]
    out = []
    for r in mf.issues(rows, ""):
        if r["category"] == "OTHER" or len([x for x in (r.get("lines") or []) if x]) < 2:
            continue
        topics = " ".join(r.get("topics") or [r["topic"]]).replace("한국은행", "")   # `한국은행 통화정책` 이 은행 업종에 붙던 것 (2026-11-12 목업)
        if kind == "stock":
            if code not in mf.kr_stocks_for(r):
                continue
            lv = 3
        elif kind == "sector":
            if not any(w in topics for w in SECTOR_WORDS[sym]):
                continue
            lv = 2
        else:
            if r["scope"] != "market":
                continue
            lv = 1
        d = "uncertain" if r.get("split") else r["direction"] if r["direction"] in ("positive", "negative") else None
        if not d:
            continue
        n = r.get("n_channels", 1)
        out.append({"t": r["topic"], "dir": d, "day": _kst_day(r["published_at"]), "lv": lv, "kind": "방송",
                    "src": r["channel"] + (f" 외 {n - 1}곳" if n > 1 else ""), "lines": [x for x in r["lines"] if x][:5], "url": r.get("url")})
    return out


def _flow(fc, days, ctx):
    """외국인 순매수 — 창 안 거래일마다, 평소보다 크거나 같은 쪽으로 사흘 넘게 이어질 때만. 코스닥(지수 · 코스닥 종목)은 코스닥, 나머지는 유가증권시장."""
    sym, kind, code = target(fc)
    kq = sym == "^KQ11" or sym.endswith(".KQ")
    ser = ctx["flows"].get("foreign_kosdaq" if kq else "foreign_kospi") or {}
    name = "코스닥" if kq else "유가증권시장"
    ks = sorted(ser)
    out = []
    for d in days:
        if d not in ser:
            continue
        i = ks.index(d)
        v = ser[d]
        prev = [abs(ser[k]) for k in ks[max(0, i - 20):i]]
        med = sorted(prev)[len(prev) // 2] if prev else 0
        streak = 1
        for k in reversed(ks[:i]):
            if (ser[k] > 0) == (v > 0):
                streak += 1
            else:
                break
        big = med and abs(v) >= med * FLOW_MULT
        if not (big or streak >= FLOW_STREAK):
            continue
        tail = f" ({['', '', '이틀', '사흘', '나흘', '닷새'][streak] if streak <= 5 else f'{streak}거래일'}째)" if streak >= 2 else ""
        out.append({"t": f"외국인 {name} {_eok(v)} {'순매수' if v > 0 else '순매도'}{tail}" + (" · 평소보다 많음" if big else ""),
                    "dir": "positive" if v > 0 else "negative", "day": d, "lv": 1 if kind != "stock" else 1, "kind": "수급", "src": "한국거래소"})
    return out


def _us_night(fc, days, ctx):
    """전날 밤 미국 — 한국 그날 아침 전에 끝난 미국 장(그날보다 앞선 마지막 미국 거래일)."""
    sym, kind, code = target(fc)
    px = ctx.get("px") or {}
    semi = sym == "091160.KS" or (kind == "stock" and "반도체" in (fc.get("tags") or []) ) or (kind == "stock" and code in ("005930", "000660", "042700"))
    key = "semi" if semi else ("^KQ11" if sym == "^KQ11" or sym.endswith(".KQ") else "^KS11")
    us, name, th = US_LINK[key]
    ser = px.get(us) or {}
    ks = sorted(ser)
    out = []
    for d in days:
        prior = [k for k in ks if k < d]
        if len(prior) < 2:
            continue
        a, b = ser[prior[-2]], ser[prior[-1]]
        mv = (b / a - 1) * 100
        if abs(mv) < th:
            continue
        out.append({"t": f"전날 밤 {name} {abs(mv):.1f}% {'상승' if mv > 0 else '하락'}", "dir": "positive" if mv > 0 else "negative",
                    "day": d, "lv": 2 if semi else 1, "kind": "미국", "src": f"미국 {prior[-1][5:7]}.{prior[-1][8:]} 종가"})
    return out


def _dart(fc, days, ctx):
    sym, kind, code = target(fc)
    if kind != "stock":
        return []
    have = set(ctx["dart"].get(code) or [])
    return [{"t": "분기 실적 공시", "dir": "uncertain", "day": d, "lv": 3, "kind": "공시", "src": "DART"} for d in days if d in have]


def _analyst(fc, lo, hi, ctx):
    """애널리스트 — 미국은 증권사별 목표가 변경(올림 n곳), 한국 자료(야후)는 평균만 있어 창 앞뒤 평균 목표가 · 이익 예상(EPS) 변화로. 1% 넘게 바뀐 것만."""
    sym, kind, code = target(fc)
    if kind != "stock":
        return []
    est = ctx.get("est") or {}
    ds = [d for d in sorted(est) if sym in (est[d] or {})]
    before = [d for d in ds if d <= lo]
    within = [d for d in ds if lo < d <= hi]
    if not within:
        return []
    a, b = est[(before or ds)[-1] if before else ds[0]][sym], est[within[-1]][sym]
    out = []
    for name, get in (("평균 목표가", lambda x: ((x or {}).get("analysts") or {}).get("pt_mean")), ("이익 예상", lambda x: ((x or {}).get("eps") or {}).get("current"))):
        va, vb = get(a), get(b)
        if not va or not vb:
            continue
        ch = (vb / va - 1) * 100
        if abs(ch) < 1:
            continue
        out.append({"t": f"애널리스트 {name} {abs(ch):.1f}% {'올림' if ch > 0 else '내림'}", "dir": "positive" if ch > 0 else "negative",
                    "day": within[-1], "lv": 3, "kind": "애널리스트", "src": "증권사 평균"})
    return out


def signals(fc, day, ctx):
    """알파스코프 신호 — 한국 종목 페이지 판정 기록(kr-state records/verdicts)의 그날까지 마지막 값. forecast_register.our_signals 와 같은 모양
    {"as_of", "rows": [{key, name, state, dir, hz, group}]}. 종목 = 그 종목 신호 전부, 지수 = 한국 증시 분위기, 업종 = 분위기 + 그 업종 종목의 업계 자금."""
    sys.path.insert(0, _EXP)
    import signal_groups as SG
    sym, kind, code = target(fc)
    rows = [r for r in ctx.get("verdicts") or [] if str(r.get("date") or "") <= day]
    if not rows:
        return None
    short = {k for _, ks in SG.SHORT for k in ks}

    def latest(s):
        mine = [r for r in rows if r.get("sym") == s]
        if not mine:
            return None, {}
        d = max(r["date"] for r in mine)
        return d, {r["id"].split("/", 1)[1]: r for r in mine if r["date"] == d}
    got, as_of = {}, None
    if kind == "stock":
        as_of, got = latest(sym)
    else:
        sys.path.insert(0, _HERE)
        import forecast_register as R
        members = [w["sym"] for w in R.kr_stocks() if kind == "index" or w["mkt"] == sym]
        for s in members:
            d, g = latest(s)
            for k in ("regime", "shock") + (("sector_flow",) if kind == "sector" else ()):
                if k in g and k not in got:
                    got[k], as_of = g[k], max(as_of or d, d)
    out = [{"key": k, "name": got[k].get("label") or SG.TABLE[k]["name"], "state": got[k]["state"], "dir": int(got[k].get("direction") or 0),
            "hz": "단기" if k in short else "중기", "group": SG.GROUP_OF.get(k, "")} for k in SG.ORDER if k in got and got[k].get("state")]
    as_of = max((r.get("as_of") or "" for k, r in got.items()), default=as_of) or as_of
    return {"as_of": as_of, "rows": out} if out else None


def _tdays(lo, hi, ctx, fc):
    """창(lo 다음 날 ~ hi)의 한국 거래일 — 그 대상 시세 날짜로 (가짜 달력 없음)."""
    sym = (fc.get("series") or {}).get("sub")
    ser = (ctx.get("px") or {}).get(sym) or {}
    ds = [d for d in sorted(ser) if lo < d <= hi]
    return ds or [hi]


def rows(fc, lo, hi, ctx):
    """lo(전 거래일, 제외) ~ hi(포함) 사이 근거 → side_news 와 같은 {"good", "bad", "open", "count"}."""
    days = _tdays(lo, hi, ctx, fc)
    allr = []
    for fn, args in ((_broadcast, (fc, lo, hi, ctx)), (_flow, (fc, days, ctx)), (_us_night, (fc, days, ctx)), (_dart, (fc, days, ctx)), (_analyst, (fc, lo, hi, ctx))):
        try:
            allr += fn(*args)
        except Exception as e:  # noqa: BLE001 — 자료 하나가 빠져도 나머지로
            print(f"[kr_why] {fn.__name__} 실패: {type(e).__name__}: {str(e)[:80]}")
    allr.sort(key=lambda r: r["day"], reverse=True)
    allr.sort(key=lambda r: -r["lv"])
    out, cnt = {}, {}
    for key, d in (("good", "positive"), ("bad", "negative"), ("open", "uncertain")):
        sel = [r for r in allr if r["dir"] == d]
        out[key], cnt[key] = sel[:30], len(sel)
    out["count"] = cnt
    return out


def day_why(fc, day, prev_day, ctx, prev_sigs=None):
    """타임라인 그날 근거 — forecast_register.day_why 와 같은 모양: 갈래 줄 + 알파스코프 신호 중 전날과 달라진 것(changes) + 그날 신호 전체(sigs, 다음 날 비교용)."""
    out = {"day": day, **rows(fc, prev_day or day, day, ctx)}
    sg = signals(fc, day, ctx) or {}
    cur = sg.get("rows") or []
    before = {r["name"]: r for r in prev_sigs or []}
    out["changes"] = [{"name": r["name"], "from": before[r["name"]]["state"], "to": r["state"], "dir": r["dir"], "hz": r["hz"]}
                      for r in cur if r["name"] in before and before[r["name"]]["state"] != r["state"]]
    out["sigs"] = cur or (prev_sigs or [])
    return out
