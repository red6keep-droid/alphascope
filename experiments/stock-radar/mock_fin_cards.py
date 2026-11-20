"""실적 탭 카드 둘 목업 — `재무 건전성은?` · `이익에 비해 주가 수준은?` (2026-11-20 사용자: 인베스팅 재정 상황 · 적정가치 화면 → "점수냐 순위냐" → Claude 제안 순위 → "목업 만들어 봐").

설계(2026-11-20 Claude, 사용자 확인 전):
- 점수 없음 · 순위만. 비교 묶음 = S&P 500 안 같은 업종(mock_earn_mom.PEER_GROUP). 항목을 섞어 하나로 만들지 않는다(섞는 순간 가중치 = 점수).
- 재무 건전성 = 부채비율 · 유동비율 · 이자보상배율 · 잉여현금 비율 · 현금 대비 빚. 줄마다 업종 안 순위, 오른쪽 = 여유 있는 쪽.
  답 = 부채비율 순위 구간 하나(위 4분의 1 = `빚 적은 쪽` · 아래 4분의 1 = `빚 많은 쪽` · 그 사이 `업종 수준`).
  사실 기준선(절대) = 유동비율 1배 미만 · 이자보상배율 1배 미만 · 자본잠식 — 해당할 때만 한 줄.
- 주가 수준 = 주가수익비율(지난 1년 · 다음 1년 예상) · 주가순자산비율 · 주가매출비율 · 주가 대비 잉여현금. 오른쪽 = 높은 쪽. `싸다 · 비싸다 · 저평가` 없음.
  답 = 지난 1년 주가수익비율 구간(적자면 주가매출비율). 줄 = 이 종목 5년 범위 안 위치(SEC 분기 이익 · 매출 × 분기 말 주가).
- 재료 = SEC companyfacts(돈 카드가 이미 받는 파일, 항목만 더) + 야후 종목 정보(시가총액 · 배수). AI 0.
"""
import datetime
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "mock_fin.json")

TAGS_ADD = {"rev": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
            "int": ("InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt", "InterestAndDebtExpense")}
INST_ADD = {"assets": ("Assets",), "liab": ("Liabilities",), "le": ("LiabilitiesAndStockholdersEquity",),
            "equity": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
            "cur_a": ("AssetsCurrent",), "cur_l": ("LiabilitiesCurrent",)}
KEEP = ("end", "cq", "rev", "int", "opinc", "ni", "fcf", "cash", "debt", "assets", "liab", "equity", "cur_a", "cur_l")
INFO = ("marketCap", "trailingPE", "forwardPE", "priceToBook", "priceToSalesTrailing12Months")


def fetch(groups, syms):
    import time
    import config
    import collect_capex as CX
    import requests
    import yfinance as yf
    CX.YEARS = max(getattr(CX, "YEARS", 4), 6)
    CX.TAGS.update(TAGS_ADD)
    CX.INSTANT_TAGS.update(INST_ADD)
    ua = {"User-Agent": config.EDGAR_USER_AGENT}
    cik = {v["ticker"]: str(v["cik_str"]).zfill(10) for v in requests.get("https://www.sec.gov/files/company_tickers.json", headers=ua, timeout=60).json().values()}
    out = {"fetched": datetime.date.today().isoformat(), "rows": {}, "shares": {}, "info": {}, "qclose": {}}
    for sym in sorted({x for g in groups.values() for x in g}):
        c = cik.get(sym) or cik.get(sym.replace("-", "."))
        try:
            if c:
                facts = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c}.json", headers=ua, timeout=60).json()
                rows = CX.rows_from_facts(facts, c)
                for r in rows:
                    if r.get("liab") is None and r.get("le") and r.get("equity") is not None:
                        r["liab"] = r["le"] - r["equity"]
                out["rows"][sym] = [{k: r.get(k) for k in KEEP} for r in rows[-24:]]
                time.sleep(0.15)   # SEC 초당 10번 아래
            info = yf.Ticker(sym).info or {}
            out["info"][sym] = {k: info.get(k) for k in INFO}
        except Exception as e:  # noqa: BLE001
            print(f"[fin] {sym} 실패: {str(e)[:80]}")
    out["shares"] = shares(syms)
    df = yf.download(list(syms), period="6y", progress=False, auto_adjust=False, threads=False)["Close"]
    for s in syms:
        ser = df[s].dropna()
        out["qclose"][s] = [(str(d.date()), float(v)) for d, v in ser.items()]
    json.dump(out, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return out


def shares(syms):
    """주식 수 기록 — 야후 get_shares_full × 그 뒤 분할(splits). SEC 표지 주식 수는 분할 전 숫자 그대로라 분할 반영 주가와 곱하면 어긋난다(엔비디아 2021 · 2024 분할, 5년 범위 5배로 나옴)."""
    import yfinance as yf
    out = {}
    for s in syms:
        t = yf.Ticker(s)
        ser = t.get_shares_full(start=(datetime.date.today() - datetime.timedelta(days=6 * 365)).isoformat())
        sp = [(str(d.date()), float(v)) for d, v in (t.splits.items() if t.splits is not None else [])]

        def adj(day, v):   # 그날 뒤에 있었던 분할을 곱한다 — 야후 주식 수 기록도 분할 전 숫자 그대로(엔비디아 2024-06 10:1 전 24.7억 주)
            for sd, ratio in sp:
                if sd > day:
                    v *= ratio
            return v
        out[s] = sorted({str(d.date()): adj(str(d.date()), float(v)) for d, v in ser.items()}.items()) if ser is not None else []
    return out


def load(groups, syms, force=False):
    if not force and os.path.exists(CACHE):
        return json.load(open(CACHE, encoding="utf-8"))
    return fetch(groups, syms)


# ---------------------------------------------------------------- 값

def _ttm(rows, k):
    last4 = rows[-4:]
    if len(last4) < 4 or any(r.get(k) is None for r in last4):
        return None
    if (datetime.date.fromisoformat(last4[-1]["end"]) - datetime.date.fromisoformat(last4[0]["end"])).days > 300:   # 빠진 분기가 있으면 1년 합이 아니다
        return None
    return sum(r[k] for r in last4)


def health(rows):
    rows = [r for r in rows if r.get("assets")]
    if not rows:
        return {}
    r = rows[-1]
    eq = r.get("equity")
    out = {"_r": r}
    out["dr"] = (r["liab"] / eq * 100 if eq and eq > 0 else float("inf")) if r.get("liab") is not None and eq is not None else None
    out["cr"] = r["cur_a"] / r["cur_l"] if r.get("cur_a") and r.get("cur_l") else None
    op, it = _ttm(rows, "opinc"), _ttm(rows, "int")
    out["ic"] = (op / it if it and it > 0 else None) if op is not None else None
    out["ic_none"] = op is not None and op > 0 and it == 0
    fcf, rev = _ttm(rows, "fcf"), _ttm(rows, "rev")
    out["fm"] = fcf / rev * 100 if fcf is not None and rev else None
    out["dc"] = r["debt"] / r["cash"] if r.get("debt") is not None and r.get("cash") else None
    out["ttm_op"], out["ttm_int"] = op, it
    return out


def valuation(info, rows):
    i = info or {}
    fcf = _ttm(rows or [], "fcf")
    pos = lambda v: v if isinstance(v, (int, float)) and v > 0 else None   # noqa: E731 — 적자 · 음수 배수는 순위에서 뺀다
    return {"pe": pos(i.get("trailingPE")), "fpe": pos(i.get("forwardPE")), "pb": pos(i.get("priceToBook")),
            "ps": pos(i.get("priceToSalesTrailing12Months")), "pf": pos(i["marketCap"] / fcf) if i.get("marketCap") and fcf else None}


def history(sym, d):
    """5년 분기 말 주가수익비율 · 주가매출비율 — 분기 말 종가 × 그 무렵 주식 수 ÷ 지난 4분기 순이익 · 매출."""
    rows, sh, px = d["rows"].get(sym) or [], d["shares"].get(sym) or [], d["qclose"].get(sym) or []
    if not (rows and sh and px):
        return {}
    out = {"pe": [], "ps": []}
    for i in range(3, len(rows)):
        end = rows[i]["end"]
        if end < (datetime.date.today() - datetime.timedelta(days=5 * 365 + 30)).isoformat():
            continue
        p = [v for dd, v in px if dd <= end]
        s = [v for dd, v in sh if dd >= end] or [sh[-1][1]]
        if not p:
            continue
        cap = p[-1] * s[0]
        ni, rev = _ttm(rows[:i + 1], "ni"), _ttm(rows[:i + 1], "rev")
        if ni and ni > 0:
            out["pe"].append(cap / ni)
        if rev:
            out["ps"].append(cap / rev)
    return out


# ---------------------------------------------------------------- 그리기

def _rank(me, others, high_right):
    vals = [v for v in others if v is not None] + [me]
    n = len(vals)
    if me is None or n < 5:
        return None
    rank = sorted(vals, reverse=high_right).index(me) + 1   # 1위 = 오른쪽 끝
    return {"rank": rank, "n": n, "pct": (n - rank) / max(n - 1, 1) * 100, "med": statistics.median(vals)}


def strip(R, dk, rows, left, mid, right):
    """줄마다 점 하나 — mock_earn_mom.mom_card 와 같은 모양. rows = [{lb, rank, n, pct, sub(html)}], 오른쪽 = 1위."""
    colors = [dk.lighten(b, 0.6) for b in R.RANGE_BASE]
    strong = [dk.lighten(b, 0.2) for b in R.RANGE_BASE]
    head = (f'<span style="display:flex;margin:0 84px 0 0;font-size:13px;line-height:18px;color:{R.NOTE};">'
            f'<span style="flex:0 0 25%;">{left}</span><span style="flex:0 0 50%;text-align:center;">{mid}</span><span style="flex:0 0 25%;text-align:right;">{right}</span></span>')
    body = ""
    for x in rows:
        z = 2 if x["pct"] >= 75 else 0 if x["pct"] < 25 else 1
        segs = "".join(f'<span style="position:absolute;top:0;left:calc({l}% + {1 if i else 0}px);width:calc({w}% - {1 if i in (0, 2) else 2}px);height:6px;border-radius:3px;background:{colors[i]};"></span>'
                       for i, (l, w) in enumerate(((0, 25), (25, 50), (75, 25))))
        midl = '<span style="position:absolute;left:50%;top:-4px;width:2px;height:14px;margin-left:-1px;background:#94A3B8;"></span>'
        dot = (f'<span style="position:absolute;top:-4px;left:clamp(0px, calc({x["pct"]:.1f}% - 7px), calc(100% - 14px));width:14px;height:14px;border-radius:50%;'
               f'background:{strong[z]};box-shadow:0 0 0 2px #fff;"></span>')
        body += (f'<span style="display:block;padding:14px 0 6px;font-size:15px;line-height:20px;color:#111;font-weight:700;">{x["lb"]}</span>'   # 이름은 막대 위 한 줄 — 긴 이름(주가순자산비율)이 좁은 칸에서 끊기지 않게
                 f'<span style="display:flex;align-items:center;">'
                 f'<span style="flex:1;position:relative;height:6px;">{segs}{midl}{dot}</span>'
                 f'<span style="flex:0 0 84px;text-align:right;font-size:15px;line-height:22px;color:#111;white-space:nowrap;">{dk.violet(str(x["rank"]) + "위")} / {x["n"]}</span></span>'
                 f'<span style="display:block;margin:4px 84px 0 0;font-size:13px;line-height:18px;color:{R.NOTE};">{x["sub"]}</span>')
    return f'<span style="{R.MULTI}margin:0 {dk.CHART_CARD_X}px;"><span style="display:block;padding:{dk.CHART_CARD_PAD}px 12px 12px;">{head}{body}</span></span>'


def _b(v):
    return f'<b style="color:#111;">{v}</b>'


HEALTH = (("dr", "부채비율", False, lambda v: "자본잠식" if v == float("inf") else f"{v:.0f}%", "총부채 ÷ 자본"),
          ("cr", "유동비율", True, lambda v: f"{v:.2f}배", "1년 안 돈이 되는 자산 ÷ 1년 안 갚을 빚"),
          ("ic", "이자보상배율", True, lambda v: f"{v:.1f}배", "지난 1년 영업이익 ÷ 이자 비용"),
          ("fm", "잉여현금 비율", True, lambda v: f"{v:.0f}%".replace("-", "−"), "지난 1년 잉여현금 ÷ 매출"),
          ("dc", "현금 대비 빚", False, lambda v: f"{v:.2f}배", "장기 부채 ÷ 현금"))


def health_card(R, dk, RP, name, sym, gname, peers, d):
    me = health(d["rows"].get(sym) or [])
    if not me:
        return None
    oth = [health(d["rows"].get(p) or []) for p in peers]
    rows, missing = [], []
    for k, lb, hi, fmt, mean in HEALTH:
        rk = _rank(me.get(k), [o.get(k) for o in oth], hi)
        if not rk:
            missing.append(lb)
            continue
        rows.append(dict(rk, lb=lb, k=k, sub=f'{_b(fmt(me[k]))} · 중앙값 {fmt(rk["med"])} · {mean}'))
    dr = next((x for x in rows if x["k"] == "dr"), None)
    if not dr:
        return None
    z = 2 if dr["pct"] >= 75 else 0 if dr["pct"] < 25 else 1
    state = ("빚 많은 쪽", "업종 수준", "빚 적은 쪽")[z]
    theme = {"빚 적은 쪽": ("positive", R.UP), "빚 많은 쪽": ("negative", R.DOWN)}.get(state, ("neutral", "#111"))
    r = me["_r"]
    end = f"{int(r['end'][5:7])}월 말"
    first = (f"{name}의 {end} 부채비율(총부채 ÷ 자본)은 {HEALTH[0][3](me['dr'])}로, S&P 500 안 {gname} {dr['n']}종목 가운데 빚이 적은 쪽부터 {dr['rank']}번째입니다. "
             f"아래 줄마다 같은 업종 안 위치를 따로 보여 드리며, 항목을 합쳐 점수를 내지는 않습니다.")
    lines = [(first, "plain"), (f'{dk.CHART_TITLE_M}같은 업종 안 위치 (오른쪽이 여유 있는 쪽)</span>{strip(R, dk, rows, "빠듯한 쪽", "중앙값", "여유 있는 쪽")}', "html")]
    facts = []   # 사실 기준선 — 해당할 때만
    if me.get("dr") == float("inf"):
        facts.append(("자본잠식", "부채가 자산보다 많습니다", "주주 몫(자본)이 0 아래"))
    if me.get("cr") is not None and me["cr"] < 1:
        facts.append(("유동비율 1배 미만", "1년 안에 갚을 빚이 1년 안에 돈이 되는 자산보다 많습니다", ""))
    if me.get("ic") is not None and me["ic"] < 1:
        facts.append(("이자보상배율 1배 미만", "지난 1년 영업이익으로 이자를 다 내지 못했습니다", ""))
    for t, v, n in facts:
        lines.append(("row", t, "해당", v))
    lines += [("row", "총자산", RP._bil(r["assets"]), f"{end} · 회사가 가진 모든 것"),
              ("row", "총부채", RP._bil(r["liab"]), "갚아야 할 돈 전부"),
              ("row", "자본", RP._bil(r["equity"]), "자산에서 부채를 뺀 주주 몫")]
    if missing:
        lines.append((f"{' · '.join(missing)}은 회사가 해당 항목을 따로 적지 않았거나 지난 1년 분기가 모자라 뺐습니다.", "note"))
    tip = ("빚 · 현금 사정을 같은 업종 회사들과 견준 위치. 항목마다 따로 순위를 매기고 합쳐서 점수를 내지 않는다\n"
           "· 나누는 법 : 부채비율이 업종에서 빚 적은 쪽 4분의 1이면 빚 적은 쪽, 많은 쪽 4분의 1이면 빚 많은 쪽, 그 사이는 업종 수준\n"
           "· 따로 알리는 경우 : 자본잠식 · 유동비율 1배 미만 · 이자보상배율 1배 미만은 순위와 상관없이 한 줄로\n"
           "· 참고 : 업종마다 빚을 쓰는 방식이 달라 다른 업종과는 견주지 않는다")
    return state, theme, lines, tip


VALUE = (("pe", "주가수익비율 (지난 1년)", lambda v: f"{v:.1f}배", "시가총액 ÷ 지난 1년 순이익"),
         ("fpe", "주가수익비율 (다음 1년 예상)", lambda v: f"{v:.1f}배", "애널리스트 이익 예상 기준"),
         ("pb", "주가순자산비율", lambda v: f"{v:.1f}배", "시가총액 ÷ 자본"),
         ("ps", "주가매출비율", lambda v: f"{v:.1f}배", "시가총액 ÷ 지난 1년 매출"),
         ("pf", "주가 대비 잉여현금", lambda v: f"{v:.1f}배", "시가총액 ÷ 지난 1년 잉여현금"))


def value_card(R, dk, RP, name, sym, gname, peers, d):
    me = valuation(d["info"].get(sym), d["rows"].get(sym))
    oth = [valuation(d["info"].get(p), d["rows"].get(p)) for p in peers]
    rows, skipped = [], []
    for k, lb, fmt, mean in VALUE:
        rk = _rank(me.get(k), [o.get(k) for o in oth], True)
        if not rk:
            skipped.append(lb)
            continue
        rows.append(dict(rk, lb=lb, k=k, val=fmt(me[k]), sub=f'{_b(fmt(me[k]))} · 중앙값 {fmt(rk["med"])} · {mean}'))
    base = next((x for x in rows if x["k"] == "pe"), None) or next((x for x in rows if x["k"] == "ps"), None)
    if not base:
        return None
    z = 2 if base["pct"] >= 75 else 0 if base["pct"] < 25 else 1
    state = ("업종보다 낮음", "업종 수준", "업종보다 높음")[z]
    # 숫자와 반대 색 — 업종보다 낮으면 빨강 · 높으면 파랑, 사이는 중립 (2026-11-20 사용자: `하락에 거는 돈은?` 처럼, 낮게 매겨지면 좋은 쪽이라 빨강. 옛 중립 회색 폐지)
    theme = {"업종보다 낮음": ("positive", R.UP), "업종보다 높음": ("negative", R.DOWN)}.get(state, ("neutral", "#111"))
    first = (f"{name}의 {base['lb']}은 {base['val']}로, S&P 500 안 {gname} {base['n']}종목 가운데 높은 쪽부터 {base['rank']}번째입니다. "
             f"높을수록 이익 · 매출에 비해 주가가 높게 매겨져 있다는 뜻입니다.")
    if base["k"] == "ps":
        first = f"{name}는 지난 1년 순이익이 적자라 주가수익비율 대신 주가매출비율로 견줍니다. " + first
    lines = [(first, "plain"), (f'{dk.CHART_TITLE_M}같은 업종 안 위치 (오른쪽이 높은 쪽)</span>{strip(R, dk, rows, "낮은 쪽", "중앙값", "높은 쪽")}', "html")]
    h = history(sym, d)
    for k, lb in (("pe", "주가수익비율"), ("ps", "주가매출비율")):
        hs, now = h.get(k) or [], me.get(k)
        if len(hs) >= 8 and now:
            lo, hi_ = min(hs), max(hs)
            below = sum(1 for v in hs if v < now)
            where = ("5년 중 가장 낮음" if below == 0 else "5년 중 가장 높음" if below == len(hs)
                     else f"5년 분기 말 {len(hs)}번 중 지금보다 낮았던 때 {below}번")
            lines.append(("row", f"{lb} 5년 범위", f"{lo:.0f} ~ {hi_:.0f}배", f"지금 {now:.1f}배 · {where}"))
    if me.get("pe") or me.get("ps"):
        if not any(len(h.get(k) or []) >= 8 for k in ("pe", "ps")):   # 빈 답 줄을 늘어놓지 않고 안내 한 줄 (판단 유보 노출 규칙)
            lines.append(("5년 범위는 분기 기록이 2년이 안 돼 내지 않았습니다.", "note"))
    if me.get("pe") is None:
        lines.append(("row", "주가수익비율 (지난 1년)", "계산 안 함", "지난 1년 순이익이 적자"))
    tip = ("이익 · 매출 · 자본에 비해 주가가 얼마나 높게 매겨져 있는지를 같은 업종 회사들과 견준 위치. 싸다 · 비싸다를 판정하지 않는다\n"
           "· 나누는 법 : 지난 1년 주가수익비율이 업종 높은 쪽 4분의 1이면 업종보다 높음, 낮은 쪽 4분의 1이면 업종보다 낮음, 그 사이는 업종 수준. 적자면 주가매출비율로\n"
           "· 5년 범위 : 지난 5년 분기 말 주가 × 주식 수 ÷ 그때까지 1년 이익 · 매출\n"
           "· 참고 : 성장이 빠른 회사는 배수가 높게 매겨지는 일이 많아, 높고 낮음만으로 좋고 나쁨을 말할 수 없다")
    return state, theme, lines, tip
