"""증시 전망 자동 등록 — 틀 R(큰 움직임 뒤 반등 · 조정 vs 지속), 기획 증시-전망-기획 8-1 · 8-2 · 8-3 (2026-11-11 사용자 "1을 먼저 해" · "개별 종목도").

forecast_daily.run 이 판정 뒤 부른다 (AI 호출 0). 하는 일:
1. 감지 — 계열마다 하루 움직임이 평소의 3배(직전 60거래일 표준편차) 넘고 절대 기준도 넘은 날. detect_sector_shocks.py · detect_shocks.py 와 같은 기준.
   지수 · 업종(INDEX) = S&P 500 그대로 · 업종은 S&P 500 대비. 종목(STOCKS) = 종목 페이지가 있는 미국 20개, **자기 업종 지수 대비**(엔비디아 vs 반도체 지수).
2. 등록 시점 — 충격 다음 거래일 장 마감 뒤(= 오늘 봉이 충격 다음 날). 실행이 빠졌으면 하루 늦게까지(늦은 등록 표시 · 알림), 그보다 늦으면 하지 않는다.
3. 막는 장치 — 크기(평소의 몇 배) 순 · 같은 계열에 판정 안 난 전망이 있으면 건너뜀 · 같은 계열 5일 안 충격 = 같은 묶음 ·
   판정 안 난 공개 전망 지수 · 업종 MAX_OPEN · 종목 MAX_OPEN_STOCK 개 — 넘치면 skipped 기록만(기획 8-1).
4. 틀 — 이름 · 자 · 기준 · 고리 · 문장 전부 규칙(8-2). 기준(금) = 그 자의 20거래일 움직임 1σ(최근 10년) 정수.
   지수 · 업종: 우리 전망 = 같은 계열 · 같은 방향 지난 충격 뒤 20거래일 안 절반을 되찾은 비율(hypo_pages.pick_side, EH-2026-11-10).
   종목: **우리 전망을 고르지 않는다**(fc["pick"] 없음) — 두 갈래에 기록상 횟수만 나란히, 판정은 어느 쪽이 일어났나만, 성적표 밖 (매수 추천 금지, 2026-11-11 사용자).
5. 이유 카드(fc["reasons"]) — 등록 때 한 번 모아 고정: 기사 · 방송이 든 이유(종목 뉴스 분류의 이슈 코드 건수 · 대표 기사), 애널리스트 목표가 변경,
   우리 기록상 신호(평소의 몇 배 · 20거래일 평균 · 52주 고점). 원인 판단이 아니라 모은 것 (가이드라인 1절 4-2 단일 이유 단언 금지).
6. 저장 — EH-YYYY-NNN.json 을 reg_dir(상태 저장소 records/hypotheses · 미리보기는 output/forecast/hypotheses), 같은 폴더 YYYY.jsonl 에 registered · skipped 한 줄.
"""
import datetime as dt
import glob
import json
import os
import sys

import hypo_pages as H

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXP = os.path.dirname(_HERE)

INDEX = [   # 기호, 비교 기호(None = 그대로), 독자 이름, 비교 이름, 절대 기준, 분류 라벨
    {"sym": "^GSPC", "mkt": None, "name": "S&P 500", "mkt_name": None, "amin": 2.0, "tag": "미국 증시"},
    {"sym": "^SOX", "mkt": "^GSPC", "name": "반도체", "mkt_name": "S&P 500", "amin": 3.0, "tag": "반도체"},
    {"sym": "XLE", "mkt": "^GSPC", "name": "에너지 업종", "mkt_name": "S&P 500", "amin": 2.5, "tag": "에너지"},
    {"sym": "XLF", "mkt": "^GSPC", "name": "금융 업종", "mkt_name": "S&P 500", "amin": 2.5, "tag": "금융"},
    {"sym": "XLK", "mkt": "^GSPC", "name": "기술 업종", "mkt_name": "S&P 500", "amin": 2.0, "tag": "기술"},
    {"sym": "XLV", "mkt": "^GSPC", "name": "헬스케어 업종", "mkt_name": "S&P 500", "amin": 2.0, "tag": "헬스케어"},
    {"sym": "XLU", "mkt": "^GSPC", "name": "유틸리티 업종", "mkt_name": "S&P 500", "amin": 2.0, "tag": "유틸리티"},
]
# 종목 → 자기 업종 지수 (universe.CANDIDATES 의 묶음 이름 기준, 구글 · 메타는 통신 서비스 · 아마존 · 테슬라는 경기 소비재)
SECTOR_IDX = {"반도체": ("^SOX", "반도체 지수"), "빅테크": ("XLK", "기술 업종"), "소비 · 플랫폼": ("XLY", "경기 소비재 업종"), "금융": ("XLF", "금융 업종"),
              "헬스케어": ("XLV", "헬스케어 업종"), "필수 소비재": ("XLP", "필수 소비재 업종"), "결제": ("XLF", "금융 업종"), "에너지": ("XLE", "에너지 업종")}
TICKER_IDX = {"GOOGL": ("XLC", "통신 서비스 업종"), "META": ("XLC", "통신 서비스 업종")}
STOCK_N = 20            # 종목 페이지가 먼저 생긴 20개 (universe.CANDIDATES 앞 20)
STOCK_AMIN = 3.0        # 종목 절대 기준 %p (업종 대비)
Z_MIN, LOOKBACK = 3.0, 60
MAX_OPEN, MAX_OPEN_STOCK = 3, 2
SAME_EPISODE_DAYS = 5
HIST_START = "1998-01-01"
LINE_YEARS = 10         # 기준(금) = 최근 10년 (1998~2002 거품 구간이 반도체 기준을 7%p 로 부풀렸다)
WIN_D5, WIN_D20, WIN_D60 = 5, 20, 60


def stocks():
    """종목 계열 목록 — universe.CANDIDATES 앞 STOCK_N 개 (종목 페이지가 있는 것)."""
    sys.path.insert(0, os.path.join(_EXP, "stock-radar"))
    try:
        import universe
    except Exception:  # noqa: BLE001
        return []
    out = []
    for sym, name, slug, cat in universe.CANDIDATES[:STOCK_N]:
        idx = TICKER_IDX.get(sym) or SECTOR_IDX.get(cat)
        if not idx:
            continue
        name = name.split("(")[0]
        out.append({"sym": sym, "mkt": idx[0], "name": name, "mkt_name": idx[1], "amin": STOCK_AMIN, "tag": "종목", "stock": True, "page": slug})
    return out


def josa(word, pair=("이", "가")):
    """받침 있으면 pair[0], 없으면 pair[1] — 한글 끝 글자 · 영문 끝 글자(L · M · N · R 은 받침 소리)."""
    ch = word.strip()[-1]
    if "가" <= ch <= "힣":
        return word + (pair[0] if (ord(ch) - 0xAC00) % 28 else pair[1])
    return word + (pair[0] if ch.upper() in "LMNR0136" else pair[1])


def _md(iso):
    return H.md(iso)


def _future_tdays(day, n):
    """day 다음 n 번째 미국 거래일 (연방 공휴일 제외 근사 — 날짜 표시용, 판정은 실제 시세 날짜로 한다)."""
    import pandas as pd
    from pandas.tseries.holiday import USFederalHolidayCalendar
    from pandas.tseries.offsets import CustomBusinessDay
    return (pd.Timestamp(day) + n * CustomBusinessDay(calendar=USFederalHolidayCalendar())).date().isoformat()


def _long_history(syms):
    """긴 일봉(배당 반영) — 감지 · 기준 · 같은 종류 기록 · 신호용. 실패하면 None (등록만 건너뛰고 판정은 그대로)."""
    try:
        import yfinance as yf
        df = yf.download(sorted(syms), start=HIST_START, progress=False, auto_adjust=True, threads=False)["Close"]
        return df if len(df) else None
    except Exception as e:  # noqa: BLE001
        print(f"[register] 긴 일봉 실패: {type(e).__name__}")
        return None


def _rel_path(c, m, i0, i1):
    out = []
    for i in range(i0, i1 + 1):
        v = (c.iloc[i] / c.iloc[i0] - 1) * 100
        if m is not None:
            v -= (m.iloc[i] / m.iloc[i0] - 1) * 100
        out.append(float(v))
    return out


def _series_stats(df, w):
    """→ (종가, 비교 종가, z, 충격 날 목록, 기준(금) 정수)."""
    import numpy as np
    c = df[w["sym"]].dropna()
    m = df[w["mkt"]].reindex(c.index).ffill() if w["mkt"] else None
    r = c.pct_change() * 100
    if m is not None:
        r = r - m.pct_change() * 100
    r = r.dropna()
    z = r / r.rolling(LOOKBACK).std().shift(1)
    hits = [d for d in r.index if abs(z.get(d, 0) or 0) >= Z_MIN and abs(r[d]) >= w["amin"]]
    lg = np.log(c).diff() - (np.log(m).diff() if m is not None else 0)
    recent = lg[lg.index >= lg.index[-1] - dt.timedelta(days=365 * LINE_YEARS)]
    line = max(1, int(round(float((recent.rolling(20).sum() * 100).std()))))
    return c, m, z, hits, line


def _record(c, m, hits, shock_day, s):
    """같은 계열 · 같은 방향 지난 충격(같은 묶음은 첫날만) 뒤 20거래일 안에 충격 폭 절반을 되찾은 횟수 → (m, n)."""
    idx = {d: i for i, d in enumerate(c.index)}
    last, m_ok, n = None, 0, 0
    for d in hits:
        if d >= shock_day:
            break
        if last is not None and (d - last).days <= SAME_EPISODE_DAYS:
            last = d
            continue
        last = d
        i = idx.get(d)
        if i is None or i < 1 or i + WIN_D20 >= len(c):
            continue
        path = _rel_path(c, m, i - 1, i + WIN_D20)
        gap = path[1]
        if (1 if gap > 0 else -1) != s:
            continue
        n += 1
        if any(s * v <= s * gap * 0.5 for v in path[2:]):
            m_ok += 1
    return m_ok, n


# ---------------------------------------------------------------- 이유 카드 재료 (등록 때 한 번, 고정)

def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def radar_paths(state_dir=None):
    """종목 뉴스 분류 · 애널리스트 기록 — 워크플로는 상태 저장소 radar/(전망 단계가 레이더보다 먼저 돈다), 로컬은 stock-radar/data/."""
    base = os.path.join(state_dir, "radar") if state_dir else os.path.join(_EXP, "stock-radar", "data")
    return os.path.join(base, "news.json"), os.path.join(base, "est_history.json")


def reasons(w, shock_day, today, s, c, z_val, paths):
    """→ {"issues": [(이슈 이름, 건수)], "n": 모은 기사 수, "heads": [(헤드라인, 날짜, 매체)], "analyst": {...} 또는 None, "signals": [문장]}.
    기사 창 = 충격 전날 ~ 등록일 (UTC 날짜). 종목은 그 종목 점수(관련도 2 이상 · 충격과 같은 방향), 지수 · 업종은 시장 · 업종 범위 기사."""
    import collections
    try:
        sys.path.insert(0, _EXP)
        import issue_codes
        ko = issue_codes.ISSUE_KO
    except Exception:  # noqa: BLE001
        ko = {}
    news_path, est_path = paths
    news = _load(news_path) or {}
    lo = (dt.date.fromisoformat(shock_day) - dt.timedelta(days=1)).isoformat()
    hi = (dt.date.fromisoformat(today) + dt.timedelta(days=1)).isoformat()
    want = "positive" if s > 0 else "negative"
    picked = []
    for x in news.values():
        t = str(x.get("published_at") or "")[:10]
        if not (lo <= t < hi) or not x.get("fact"):
            continue
        if w.get("stock"):
            sc = next((q for q in x.get("scores") or [] if q.get("ticker") == w["sym"]), None)
            if not sc or sc.get("relevance", 0) < 2 or sc.get("direction") != want:
                continue
            picked.append((sc.get("relevance", 0), x))
        elif x.get("scope") in ("market", "sector") and x.get("issue") not in (None, "", "OTHER"):
            picked.append((1, x))
    cnt = collections.Counter(x.get("issue") for _, x in picked if x.get("issue") and x.get("issue") != "OTHER")
    issues = [(ko.get(k, k), n) for k, n in cnt.most_common(2) if n >= 2]
    top = [k for k, _ in cnt.most_common(1)]
    heads = [(x["fact"], str(x["published_at"])[:10], x.get("source") or "")
             for _, x in sorted(picked, key=lambda p: (-p[0], p[1].get("issue") not in top, str(p[1].get("published_at"))))[:2]]
    analyst = None
    if w.get("stock"):
        est = _load(est_path) or {}
        seen, down, up, cut_rating = set(), 0, 0, 0
        for day in sorted(est):
            if not (lo <= day <= today):
                continue
            for ch in (((est[day] or {}).get(w["sym"]) or {}).get("analysts") or {}).get("changes") or []:
                at = str(ch.get("at") or "")[:10]
                key = (ch.get("firm"), at, ch.get("pt"))
                if key in seen or not (lo <= at <= today):
                    continue
                seen.add(key)
                down += ch.get("pt_action") == "Lowers"
                up += ch.get("pt_action") == "Raises"
                cut_rating += ch.get("action") == "down"
        if down or up or cut_rating:
            analyst = {"down": down, "up": up, "downgrade": cut_rating}
    sig = [f"하루 움직임 평소의 {abs(z_val):.1f}배"]
    import pandas as pd
    i = c.index.get_loc(pd.Timestamp(shock_day))
    if i >= 20:
        ma = float(c.iloc[i - 19:i + 1].mean())
        sig.append(f"20거래일 평균 {'위' if c.iloc[i] >= ma else '아래'}")
    hi52 = float(c.iloc[max(0, i - 251):i + 1].max())
    off = (float(c.iloc[i]) / hi52 - 1) * 100
    if off <= -10:
        sig.append(f"52주 고점보다 {off:.0f}%".replace("-", "−"))
    return {"issues": issues, "n": len(picked), "heads": heads, "analyst": analyst, "signals": sig, "window": [lo, today]}


# ---------------------------------------------------------------- 등록 파일

def _next_id(year, reg_dirs):
    nums = []
    for d in reg_dirs:
        for p in glob.glob(os.path.join(d, f"EH-{year}-*.json")):
            b = os.path.basename(p)[:-5]
            try:
                nums.append(int(b.split("-")[2]))
            except (IndexError, ValueError):
                pass
    return f"EH-{year}-{(max(nums) + 1 if nums else 1):03d}"


def build(eid, w, today, shock_day, base_day, gap, z, line, rec, late, why=None):
    """틀 R 전망 한 장 — 기획 8-2 의 고정 문장에 이름만 끼운다 (hypotheses/EH-2026-001 전망 2 와 같은 칸)."""
    subject, mkt, mkt_name, stock = w["name"], w["mkt"], w["mkt_name"], bool(w.get("stock"))
    subj_ga = josa(subject)
    s = 1 if gap > 0 else -1
    shock, (rw, rv), dw = H.SHOCK[s], H.REV[s], H.DIR_WORD[s]
    unit = "%p" if mkt else "%"
    more = "오름" if s > 0 else "빠짐"
    m_ok, n = rec
    sc = [{"no": 1, "cond": f"{rw} 쪽이면", "name": f"{subject} {rw}", "dir": -s,
           "chain": [{"step": f"{shock} 폭의 4분의 1 {rv}", "state": "wait", "ev": "", "date": ""},
                     {"step": f"{shock} 폭의 절반 {rv}", "state": "wait", "ev": "", "date": ""}],
           "win": f"{subj_ga} {shock} 폭({abs(gap):.1f}{unit})의 절반을 {rv}한다"},
          {"no": 2, "cond": "지속 쪽이면", "name": f"{subject} {dw} 지속", "dir": s,
           "chain": [{"step": f"{shock} 뒤 {max(1, round(line / 3))}{unit} 더 {more}", "state": "wait", "ev": "", "date": ""},
                     {"step": f"{shock} 뒤 {line}{unit} 더 {more}", "state": "wait", "ev": "", "date": ""}],
           "win": f"{subj_ga} {shock} 뒤 {line}{unit} 더 {'오른다' if s > 0 else '빠진다'}"}]
    if stock:   # 종목 = 고르지 않는다 — 두 갈래에 기록상 횟수만 나란히 (2026-11-11 사용자)
        pick, prob, why_pick, strong = None, None, "종목은 우리 전망을 고르지 않는다 (매수 추천 금지)", False
        if n:
            sc[0]["odds"] = [m_ok, n, "같은 종류 사건 뒤 20거래일"]
            sc[1]["odds"] = [n - m_ok, n, "같은 종류 사건 뒤 20거래일 (절반을 되찾지 못한 횟수)"]
    elif n:
        pick, prob, why_pick, strong = H.pick_side(m_ok, n)
        sc[pick - 1]["odds"] = [m_ok if pick == 1 else n - m_ok, n, "같은 종류 사건 뒤 20거래일"]
    else:
        pick, prob, why_pick, strong = 1, None, "같은 종류 기록 없음 — 고르기만 하고 유력 없음", False
    d5, d20, d60 = _future_tdays(today, WIN_D5), _future_tdays(today, WIN_D20), _future_tdays(today, WIN_D60)
    vs = f"{mkt_name}보다 얼마나 더 움직였나(%p)" if mkt else "얼마나 움직였나(%)"
    slug = "forecast-" + eid[3:].lower()   # EH-2026-003 → forecast-2026-003 (영문 주소, 한 번 정하면 바꾸지 않는다)
    fc = {
        "no": 1, "slug": slug, "kind": "after", "auto": True, "publish": True, "target": "stock" if stock else "index",
        "title": f"{subject} {shock}, " + ("조정 올까 더 오를까?" if s > 0 else "반등할까 더 빠질까?"),
        "event": f"{_md(shock_day)} {subject} {shock}", "registered": today, "registered_display": _md(today), "posted": _md(today),
        "what": f"{_md(shock_day)} {subject}의 큰 {dw} 뒤 {rw}하는지, 더 이어지는지를 다음 거래일({_md(today)}) 장 마감 뒤에 두 갈래로 적어 두었습니다."
                + (" 종목은 어느 쪽이 맞을지 고르지 않고, 어느 쪽이 일어나는지만 적습니다." if stock else ""),
        "ruler": f"{subject} vs {mkt_name} 상대수익" if mkt else f"{subject} 수익률",
        "ruler_plain": f"{_md(base_day)} 종가부터 {subj_ga} {vs}. {shock} 폭의 절반을 되찾으면 {rw}, 기준만큼 더 가면 지속으로 가른다",
        "ruler_short": f"{subject} vs {'업종' if stock else '시장'}" if mkt else subject,
        "ruler_from": f"{_md(base_day)} 종가 대비", "recov_note": f"{_md(shock_day)} 하루 {shock} 폭 대비",
        "start_text": f"{_md(shock_day)} {shock} 뒤 두 갈래를 적었습니다. 다음 거래일부터 봅니다.",
        "hypothesis": "H-급락 뒤 (A 반등 vs B 추세 지속) — 설계 3부 2절 활성 가설 2" if s < 0 else "H-급등 뒤 (A 조정 vs B 추세 지속)",
        "scenarios": sc, "neither": f"그 사이({rw} 4분의 1 ~ 절반)에 머물면 어느 쪽도 아님",
        "checks": [{"date": d5, "label": "중간 확인", "note": f"{rw}의 이른 신호(4분의 1)만 본다"},
                   {"date": d20, "label": "결과", "note": f"{rw} 절반 · 지속 기준을 처음 적용"},
                   {"date": d60, "label": "최종", "note": "60거래일 뒤 확정. 끝난 전망으로 옮긴다"}],
        "dates": [["게시", _md(today)], [shock, _md(shock_day)], ["최종", _md(d60)], ["첫 확인", _md(d5)]],
        "tags": [w["tag"], rw], "subject": subject, "subj_ga": subj_ga, "cmp": f"{mkt_name}보다" if mkt else None, "unit": unit, "line": float(line),
        "line_src": f"20거래일 움직임 1σ(최근 {LINE_YEARS}년) → 정수 {line}{unit}",
        "gap": round(gap, 1), "base_day": base_day, "end_day": d60, "beta": 1.0,
        "pick": pick, "pick_prob": prob, "pick_strong": strong, "pick_why": why_pick,
        "pick_note": (f"고르지 않음 — 같은 종목 같은 방향 {n}번 중 {m_ok}번 절반을 되찾음 (두 갈래에 나란히)" if stock else
                      f"우리 전망 = pick_side(같은 계열 같은 방향 {n}번 중 {m_ok}번 20거래일 안에 절반을 되찾음) → ‘{sc[pick - 1]['name']}’" + ("" if strong else " · 유력 없음")) + f" ({H.RULES})",
        "series": {"sub": w["sym"], "mkt": mkt}, "shock_day": shock_day, "z": round(z, 1), "late": bool(late), "reasons": why,
        "stock_page": H.page_url(w["page"]) if stock and w.get("page") else None,
        "record": {"result": f"지켜보는 중 (자동 등록 {_md(today)}, 창 D+5 {_md(d5)} · D+20 {_md(d20)} · D+60 {_md(d60)})", "overlap": [],
                   "cooccur": {"note": "창 안 상위 3일 이슈 코드 개수 — 매일 갱신 단계에서 채움", "days": []}},
    }
    reg = {"id": eid, "rules": H.RULES, "event": fc["event"], "kind": "shock", "auto": True, "registered_at": today,
           "late_registration": "충격 다음 날 실행이 없어 하루 늦게 등록" if late else None, "forecasts": [fc]}
    return reg, fc


def register(px, today, pubs, states, reg_dir, read_dirs=(), alert=None, state_dir=None, news_paths=None):
    """오늘 등록할 전망 → [(reg, fc)]. px = forecast_daily 시세({키: {날짜: 종가}}), pubs = [(reg, fc)] 공개 전망, states = 판정 결과.
    reg_dir = 쓸 곳, read_dirs = 번호를 셀 곳(로컬 hypotheses 포함). 실패는 건너뛴다 — 판정 · 렌더는 그대로."""
    import pandas as pd

    def sub_of(fc):
        return (fc.get("series") or {"sub": "^SOX"})["sub"]

    def is_open(fc):
        return not (states.get(fc["slug"]) or {}).get("result")
    open_idx = sum(1 for _, fc in pubs if is_open(fc) and fc.get("target") != "stock")
    open_stock = sum(1 for _, fc in pubs if is_open(fc) and fc.get("target") == "stock")
    open_series = {sub_of(fc) for _, fc in pubs if is_open(fc)}
    shocks_seen = {}
    for _, fc in pubs:
        if fc.get("shock_day"):   # 손으로 만든 옛 전망(EH-2026-001 전망 2)은 칸이 없다 — 판정이 끝나 막지 않는다
            shocks_seen.setdefault(sub_of(fc), []).append(fc["shock_day"])
    watch = INDEX + stocks()
    df = _long_history({w["sym"] for w in watch} | {w["mkt"] for w in watch if w["mkt"]})
    if df is None:
        return []
    paths = news_paths or radar_paths(state_dir)
    out, log, found = [], [], []
    for w in watch:   # 1) 감지 — 후보를 다 모은 뒤 크기 순으로 자리를 준다 (기획 8-1)
        try:
            c, m, z, hits, line = _series_stats(df, w)
        except Exception as e:  # noqa: BLE001
            print(f"[register] {w['name']} 계산 실패: {type(e).__name__}")
            continue
        days = [d.date().isoformat() for d in c.index]
        if len(days) < 4 or days[-1] != today:   # 긴 일봉에 오늘 봉이 아직 없으면 다음 실행에서
            continue
        hit_days = {h.date().isoformat() for h in hits}
        shock = next(((d, k) for k, d in ((1, days[-2]), (2, days[-3])) if d in hit_days), None)
        if shock:
            found.append((abs(float(z[pd.Timestamp(shock[0])])), w, c, m, z, hits, line, shock[0], shock[1], days[days.index(shock[0]) - 1]))
    for _az, w, c, m, z, hits, line, shock_day, lag, base_day in sorted(found, key=lambda x: -x[0]):   # 2) 등록
        sym, mkt, stock = w["sym"], w["mkt"], bool(w.get("stock"))
        why_skip = None
        if sym in open_series:
            why_skip = "같은 계열 전망이 아직 지켜보는 중"
        elif any(abs((dt.date.fromisoformat(shock_day) - dt.date.fromisoformat(x)).days) <= SAME_EPISODE_DAYS for x in shocks_seen.get(sym, [])):
            why_skip = "같은 묶음(5일 안)으로 이미 등록"
        elif (open_stock >= MAX_OPEN_STOCK) if stock else (open_idx >= MAX_OPEN):
            why_skip = f"지켜보는 {'종목 ' if stock else ''}전망 {MAX_OPEN_STOCK if stock else MAX_OPEN}개 — 자리 없음"
        sub = px.get(sym) or {}
        mk = (px.get(mkt) or {}) if mkt else None
        if base_day not in sub or shock_day not in sub or (mkt and (base_day not in mk or shock_day not in mk)):
            why_skip = why_skip or "판정용 시세에 충격 날이 없음"
        if why_skip:
            log.append({"day": today, "event": "skipped", "series": sym, "shock_day": shock_day, "why": why_skip})
            print(f"[register] {w['name']} {shock_day} 건너뜀 — {why_skip}")
            continue
        gap = (sub[shock_day] / sub[base_day] - 1) * 100 - ((mk[shock_day] / mk[base_day] - 1) * 100 if mkt else 0)   # 판정과 같은 시세 · β 1
        s = 1 if gap > 0 else -1
        zv = float(z[pd.Timestamp(shock_day)])
        rec = _record(c, m, hits, pd.Timestamp(shock_day), s)
        try:
            why = reasons(w, shock_day, today, s, c, zv, paths)
        except Exception as e:  # noqa: BLE001
            print(f"[register] 이유 모으기 실패: {type(e).__name__}")
            why = None
        eid = _next_id(today[:4], [reg_dir, *read_dirs])
        reg, fc = build(eid, w, today, shock_day, base_day, gap, zv, line, rec, late=lag > 1, why=why)
        try:
            os.makedirs(reg_dir, exist_ok=True)
            with open(os.path.join(reg_dir, f"{eid}.json"), "w", encoding="utf-8") as f:
                json.dump(reg, f, ensure_ascii=False, indent=1)
        except Exception as e:  # noqa: BLE001
            if alert:
                alert.save_failed("자동 등록 파일", e)
            continue
        log.append({"day": today, "event": "registered", "id": eid, "slug": fc["slug"], "series": sym, "target": fc["target"], "shock_day": shock_day,
                    "gap": fc["gap"], "z": fc["z"], "line": line, "pick": fc["pick"], "record": list(rec), "late": lag > 1, "rules": H.RULES})
        print(f"[register] {eid} 등록 — {fc['title']} (충격 {shock_day} {fc['gap']:+.1f}{fc['unit']} · 평소의 {abs(fc['z']):.1f}배 · 기준 {line} · 기록 {rec[1]}번 중 {rec[0]}번)")
        if alert:
            if lag > 1:
                alert.registration_missed(fc["event"], late=True)
            alert.status_changed(fc["title"], "자동 등록")
        out.append((reg, fc))
        if stock:
            open_stock += 1
        else:
            open_idx += 1
        open_series.add(sym)
    if log:
        try:
            os.makedirs(reg_dir, exist_ok=True)
            with open(os.path.join(reg_dir, f"{today[:4]}.jsonl"), "a", encoding="utf-8") as f:
                for row in log:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception as e:  # noqa: BLE001
            if alert:
                alert.save_failed("등록 기록", e)
    return out
