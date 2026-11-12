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
   갈래별 근거(good · bad · open) — 기사 요약 줄 태그에서 이 대상에 걸린 사실을 좋은 소식 · 나쁜 소식 · 방향이 안 정해진 일로 (side_news, 2026-11-11 사용자).
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
# 한국 계열 (2026-11-12 사용자 "적용해" — 검증 validate_kr_register.py · 기획 8-1): 코스피 그대로 · 코스닥과 KODEX 업종은 코스피 대비
# (코스닥을 그대로 재면 93번 중 30번이 코스피와 같은 묶음). 한국 열린 전망은 미국과 따로 센다. VIX 자리는 비운다(판정은 회복 · 기준만).
KR_INDEX = [
    {"sym": "^KS11", "mkt": None, "name": "코스피", "mkt_name": None, "amin": 2.0, "tag": "한국 증시", "kr": True},
    {"sym": "^KQ11", "mkt": "^KS11", "name": "코스닥", "mkt_name": "코스피", "amin": 2.0, "tag": "한국 증시", "kr": True},
    {"sym": "091160.KS", "mkt": "^KS11", "name": "한국 반도체 업종", "mkt_name": "코스피", "amin": 3.0, "tag": "반도체", "kr": True},
    {"sym": "091170.KS", "mkt": "^KS11", "name": "한국 은행 업종", "mkt_name": "코스피", "amin": 2.5, "tag": "금융", "kr": True},
    {"sym": "091180.KS", "mkt": "^KS11", "name": "한국 자동차 업종", "mkt_name": "코스피", "amin": 2.5, "tag": "자동차", "kr": True},
    {"sym": "117460.KS", "mkt": "^KS11", "name": "한국 에너지화학 업종", "mkt_name": "코스피", "amin": 2.5, "tag": "에너지", "kr": True},
]
KR_MARKETS = ("^KS11", "^KQ11")
KR_BANKS = ("105560.KS", "055550.KS", "086790.KS")   # 은행 지주 → KODEX 은행 (보험 · 인터넷 은행은 코스피)
KR_AUTOS = ("005380.KS", "000270.KS")
STOCK_AMIN = 3.0        # 종목 절대 기준 %p (업종 대비)
Z_MIN, LOOKBACK = 3.0, 60
MAX_OPEN, MAX_OPEN_STOCK = 3, 2
MAX_OPEN_KR, MAX_OPEN_KR_STOCK = 2, 2   # 한국 지수 · 업종 · 종목 — 미국 자리와 따로 (2026-11-12)
KR_FRESH_DAYS = 4                       # 한국 마지막 봉이 미국 마지막 봉보다 이만큼 넘게 오래되면 (한국 연휴 · 자료 지연) 등록하지 않는다
SAME_EPISODE_DAYS = 5
HIST_START = "1998-01-01"
LINE_YEARS = 10         # 기준(금) = 최근 10년 (1998~2002 거품 구간이 반도체 기준을 7%p 로 부풀렸다)
WIN_D5, WIN_D20, WIN_END = 5, 20, 40   # 기간 만료 = 40거래일(두 달) — 2026-11-11 사용자 (옛 60). 지난 충격 1,626번에 지금 판정 규칙: 20거래일 안 77% · 40 안 93% · 60 안 96% 가 끝남


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


def is_kr(sym):
    return bool(sym) and (sym in KR_MARKETS or sym.endswith((".KS", ".KQ")))


def kr_stocks():
    """한국 종목 계열 — universe_kr.CANDIDATES 전부(종목 페이지가 있는 것). 비교 = 반도체 · 은행 · 자동차는 KODEX 업종, 코스닥 종목은 코스닥, 나머지는 코스피."""
    sys.path.insert(0, os.path.join(_EXP, "kr-stocks"))
    try:
        import universe_kr
    except Exception:  # noqa: BLE001
        return []
    out = []
    for sym, name, slug, _cat, tags in universe_kr.CANDIDATES:
        if sym.endswith(".KQ"):
            mk = ("^KQ11", "코스닥")
        elif "반도체" in tags:
            mk = ("091160.KS", "한국 반도체 업종")
        elif sym in KR_BANKS:
            mk = ("091170.KS", "한국 은행 업종")
        elif sym in KR_AUTOS:
            mk = ("091180.KS", "한국 자동차 업종")
        else:
            mk = ("^KS11", "코스피")
        out.append({"sym": sym, "mkt": mk[0], "name": name, "mkt_name": mk[1], "amin": STOCK_AMIN, "tag": "한국 종목", "stock": True, "page": slug, "kr": True})
    return out


def kst_partial_day(now=None):
    """한국 장이 아직 안 끝났으면 오늘(KST) 날짜 — 그날 한국 봉은 장중 값이라 감지 · 판정에 쓰지 않는다. 끝났거나 주말이면 None.
    nvda-report 13:00 KST 실행이 한국 장중이다 (2026-11-12). 마감 15:30 + 지연 여유 → 16:00, 수능일은 장이 한 시간 늦게 끝나 17:00."""
    now = now or dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    if now.weekday() >= 5:
        return None
    day = now.date().isoformat()
    close_h = 16
    try:
        sys.path.insert(0, os.path.join(_EXP, "kr-stocks"))
        import universe_kr
        if day in universe_kr.EXAM_DAYS:
            close_h = 17
    except Exception:  # noqa: BLE001
        pass
    return day if now.hour < close_h else None


def josa(word, pair=("이", "가")):
    """받침 있으면 pair[0], 없으면 pair[1] — 한글 끝 글자 · 영문 끝 글자(L · M · N · R 은 받침 소리)."""
    ch = word.strip()[-1]
    if "가" <= ch <= "힣":
        return word + (pair[0] if (ord(ch) - 0xAC00) % 28 else pair[1])
    return word + (pair[0] if ch.upper() in "LMNR0136" else pair[1])


def _md(iso):
    return H.md(iso)


def _future_tdays(day, n, kr=False):
    """day 다음 n 번째 거래일 — 미국 = 연방 공휴일 제외 근사, 한국 = 주말만 뺀 근사(공휴일 달력 없음). 날짜 표시 · 만료일용, 판정은 실제 시세 날짜로 한다."""
    import pandas as pd
    from pandas.tseries.holiday import USFederalHolidayCalendar
    from pandas.tseries.offsets import BDay, CustomBusinessDay
    off = BDay() if kr else CustomBusinessDay(calendar=USFederalHolidayCalendar())
    return (pd.Timestamp(day) + n * off).date().isoformat()


def _long_history(syms):
    """긴 일봉(배당 반영) — 감지 · 기준 · 같은 종류 기록 · 신호용. 실패하면 None (등록만 건너뛰고 판정은 그대로)."""
    try:
        import yfinance as yf
        df = yf.download(sorted(syms), start=HIST_START, progress=False, auto_adjust=True, threads=False)["Close"]
        part = kst_partial_day()
        if part and len(df):   # 한국 장중 봉은 빈칸으로 (미국 봉은 그대로)
            import pandas as pd
            kr_cols = [x for x in df.columns if is_kr(x)]
            df.loc[df.index >= pd.Timestamp(part), kr_cols] = float("nan")
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


def _price_signals(shock_day, c, z_val):
    """우리 기록상 신호 문장 — 평소의 몇 배 · 20거래일 평균 위 · 아래 · 52주 고점 −10% 이하."""
    import pandas as pd
    sig = [f"하루 움직임 평소의 {abs(z_val):.1f}배"]
    i = c.index.get_loc(pd.Timestamp(shock_day))
    if i >= 20:
        ma = float(c.iloc[i - 19:i + 1].mean())
        sig.append(f"20거래일 평균 {'위' if c.iloc[i] >= ma else '아래'}")
    hi52 = float(c.iloc[max(0, i - 251):i + 1].max())
    off = (float(c.iloc[i]) / hi52 - 1) * 100
    if off <= -10:
        sig.append(f"52주 고점보다 {off:.0f}%".replace("-", "−"))
    return sig


def reasons(w, shock_day, today, s, c, z_val, paths):
    """→ {"issues": [(이슈 이름, 건수)], "n": 모은 기사 수, "heads": [(헤드라인, 날짜, 매체)], "analyst": {...} 또는 None, "signals": [문장]}.
    기사 창 = 충격 전날 ~ 등록일 (UTC 날짜). 종목은 그 종목 점수(관련도 2 이상 · 충격과 같은 방향), 지수 · 업종은 시장 · 업종 범위 기사."""
    import collections
    if w.get("kr"):   # 한국 = 아직 한국 기사 분류가 없다 — 미국 기사가 붙지 않게 우리 기록상 신호만 (갈래 근거 · 우리 신호 없음 → 날마다 근거도 건너뜀)
        return {"issues": [], "n": 0, "heads": [], "analyst": None, "signals": _price_signals(shock_day, c, z_val), "window": [shock_day, today]}
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
    analyst = _analyst(w["sym"], lo, today, est_path) if w.get("stock") else None
    sig = _price_signals(shock_day, c, z_val)
    out = {"issues": issues, "n": len(picked), "heads": heads, "analyst": analyst, "signals": sig, "window": [lo, today]}
    try:
        out.update(side_news(w, lo, hi, news, os.path.join(os.path.dirname(news_path), "news_summaries.json"), analyst))
    except Exception as e:  # noqa: BLE001
        print(f"[register] 갈래 근거 실패: {type(e).__name__}")
    try:
        out["our_signals"] = our_signals(w, lo, today, os.path.dirname(news_path))   # `signals` 는 옛 `우리 기록상` 문장 목록 — 이름을 나눈다
    except Exception as e:  # noqa: BLE001
        print(f"[register] 우리 신호 실패: {type(e).__name__}")
    return out


# ---------------------------------------------------------------- 우리 신호 (2026-11-11 사용자: "우리가 가지고 있는 모든 신호를 분리해서 근거에")
# 종목 페이지 판정(stock_records → 상태 저장소 radar/records/verdicts)의 그날 마지막 값을 signal_groups 관행 방향(상승 쪽 +1 · 하락 쪽 −1 · 중립 0)대로
# 갈래에 나눈다 — 전망을 두 갈래로 나눈 것처럼 신호도 나눌 뿐, 맞을지는 독자가 판단한다. 검증 결과로 빼거나 거꾸로 놓지 않는다(같은 날 사용자: 검증도 가설).
# 기간 = 단기(SHORT 분류) · 중기(MID · 업계 현황). 과열(세지 않는 줄)도 넣는다. 전망 등록이 레이더보다 먼저 돌아 값은 전날 종목 페이지 것 — as_of 로 적는다.
# 지수 · 업종 전망 = 시장 신호(증시 분위기 · 충격 국면), 업종은 + 그 업종 종목의 업계 자금.
MARKET_KEYS = ("regime", "shock")


def our_signals(w, lo, today, radar_dir):
    """→ {"as_of": 날짜, "rows": [{"key", "name", "state", "dir", "hz"(단기 · 중기), "group"}]} 또는 None."""
    sys.path.insert(0, _EXP)
    import record_store
    import signal_groups as SG
    rows = [r for r in record_store.read(radar_dir, "verdicts", today[:4]) if str(r.get("date") or "") <= today]
    if not rows:
        return None
    kind, sym, etf = _target(w)
    short = {k for _, ks in SG.SHORT for k in ks}
    hz_of = lambda k: "단기" if k in short else "중기"   # noqa: E731 — MID · 업계 현황(분기)은 중기

    def latest(target):
        mine = [r for r in rows if r.get("sym") == target]
        if not mine:
            return None, {}
        day = max(r["date"] for r in mine)
        return day, {r["id"].split("/", 1)[1]: r for r in mine if r["date"] == day and "/pick/" not in r["id"]}
    out, as_of = [], None
    if kind == "stock":
        as_of, got = latest(sym)
        picks = [r for r in rows if r.get("sym") == sym and "/pick/" in r.get("id", "") and lo <= str(r.get("date")) <= today]
    else:
        _etf_of("NVDA")   # universe 불러오기
        members = [s for s in (_UNI.BY_SYM if _UNI else {}) if kind == "market" or _etf_of(s) == etf]
        got, picks = {}, []
        for s in members:
            d, g = latest(s)
            if not g:
                continue
            as_of = max(as_of or d, d)
            for k in MARKET_KEYS + (("sector_flow",) if kind == "sector" else ()):
                if k in g and k not in got:
                    got[k] = g[k]
    for k in SG.ORDER:
        r = got.get(k)
        if not r or not r.get("state") or k == "analysts":
            continue
        out.append({"key": k, "name": r.get("label") or SG.TABLE[k]["name"], "state": r["state"], "dir": int(r.get("direction") or 0),
                    "hz": hz_of(k), "group": SG.GROUP_OF.get(k, "")})
    for r in picks:   # 방송 의견 = 사람마다 한 줄 (기간 안)
        if r.get("state"):
            out.append({"key": "picks", "name": f'방송 의견 · {r.get("speaker") or r.get("channel") or ""}'.rstrip(" ·"), "state": r["state"],
                        "dir": int(r.get("direction") or 0), "hz": "단기", "group": SG.GROUP_OF.get("picks", "")})
    return {"as_of": as_of, "rows": out} if out else None


# ---------------------------------------------------------------- 갈래별 근거 (2026-11-11 사용자)
# 기사 요약 줄 태그(news_summary: 대상 · 주제 · 방향 · 단계)에서 이 전망 대상에 걸린 사실 줄만 골라 좋은 소식 · 나쁜 소식 · 방향이 안 정해진 일로 나눈다.
# 좋은 소식 = 오름 쪽 갈래(dir +1) 카드, 나쁜 소식 = 내림 쪽 갈래(dir −1) 카드 — 화면이 sc["dir"] 로 짝짓는다. 원인 판단이 아니라 기사에 붙은 성격을 모은 것.
# 논의 중(검토 · 협상 · 보도된 계획)도 방향대로 넣는다 — "논의 중이라는 이야기라도 시장에 충격을 준다". `불확실`은 버리지 않고 open 으로 (두 갈래 모두에 걸린 일).
# 주가 · 지수 움직임만 적은 줄(tag.price)과 방향 없는 줄(neutral)은 뺀다. 요약이 없는 기사는 기사 단위 값(종목 점수 · market_dir · stage)으로.
TAG_ETF = {"^SOX": "SMH"}   # 우리 지수 기호 → 요약 태그의 업종 ETF
SIDE_KEEP = 30              # 갈래마다 저장하는 줄 — 넘치면 건수만 (팝업에 `외 n건`)


def _target(w):
    """→ (종류, 기호, 업종 ETF). 종류 = market · sector · stock."""
    if w.get("stock"):
        return "stock", w["sym"], TAG_ETF.get(w["mkt"], w["mkt"])
    if not w.get("mkt"):
        return "market", None, None
    return "sector", None, TAG_ETF.get(w["sym"], w["sym"])


def side_news(w, lo, hi, news, summary_path, analyst=None):
    """→ {"good": [줄], "bad": [줄], "open": [줄], "count": {good · bad · open: 전체 건수}}. 줄 = {"t", "day", "src", "stage", "lv"(3 종목 · 2 업종 · 1 시장)}."""
    kind, sym, etf = _target(w)
    summ = _load(summary_path) or {}
    rows, seen = [], set()
    try:
        sys.path.insert(0, _EXP)
        from news_summary import _price_only
    except Exception:  # noqa: BLE001
        def _price_only(t):
            return False

    def add(t, d, stage, lv, x, lines=()):
        t = (t or "").strip()
        if not t or d not in ("positive", "negative", "uncertain") or t in seen or _price_only(t):
            return
        seen.add(t)
        row = {"t": t, "dir": d, "stage": stage, "lv": lv, "day": str(x.get("published_at") or "")[:10], "src": x.get("source") or ""}
        # 기사 팝업 재료(P516, 2026-11-11 사용자: 줄을 누르면 그 기사 팝업) — 이미 처리해 둔 요약 줄 · 원문 주소를 같이 둔다. 새 수집 · AI 0
        ls = [str(q).strip() for q in (lines or []) if str(q).strip()][:5]
        if len(ls) >= 2:
            row["lines"] = ls
        if x.get("url"):
            row["url"] = x["url"]
        rows.append(row)

    for iid, x in news.items():
        day = str(x.get("published_at") or "")[:10]
        if not (lo <= day < hi):
            continue
        sm = summ.get(iid) or {}
        tags = sm.get("tags") or []
        if any(tags):
            for ln, tg in zip(sm.get("lines") or [], tags):
                if not tg or tg.get("price"):
                    continue
                if kind == "market":
                    lv = 1 if tg["scope"] == "market" else 0
                elif kind == "sector":
                    lv = 2 if tg.get("sector") == etf and tg["scope"] in ("sector", "stock") else 0
                else:
                    lv = 3 if sym in tg.get("tickers", []) else (2 if tg["scope"] == "sector" and tg.get("sector") == etf else 0)
                if lv:
                    add(ln, tg["dir"], tg.get("stage"), lv, x, sm.get("lines"))
            continue
        if not x.get("fact") or x.get("opinion"):   # 요약 줄이 없는 기사 — 기사 단위 값 (의견 · 주가 움직임 기사는 제목이 곧 의견이라 뺀다. 요약 줄은 사실만이라 위에서 받는다)
            continue
        if kind == "market":
            if x.get("scope") == "market":
                add(x["fact"], x.get("market_dir"), x.get("stage"), 1, x)
        else:
            sc = [q for q in x.get("scores") or [] if q.get("relevance", 0) >= 2]
            # 기사 대표 문장이 그 회사 이야기일 때만 (11-11 로컬 확인: 엔비디아 점수가 붙은 기사의 문장이 `애플 시가총액 기록` 이었다)
            if kind == "stock":
                q = next((q for q in sc if q.get("ticker") == sym), None)
                if q and _named(sym, x["fact"]):
                    add(x["fact"], q.get("direction"), x.get("stage"), 3, x)
            else:
                ds = [q.get("direction") for q in sc if _etf_of(q.get("ticker")) == etf and _named(q.get("ticker"), x["fact"])]
                if ds:
                    d = "uncertain" if "positive" in ds and "negative" in ds else next((v for v in ds if v != "neutral"), "neutral")
                    add(x["fact"], d, x.get("stage"), 2, x)
    end = (dt.date.fromisoformat(hi) - dt.timedelta(days=1)).isoformat()   # hi 는 창 끝 다음 날(열린 끝)
    if analyst:   # 애널리스트 = 그 종목 사실 (같은 기간 바뀐 것)
        if analyst.get("up"):
            rows.append({"t": f"애널리스트 목표가 올림 {analyst['up']}곳", "dir": "positive", "stage": "done", "lv": 3, "day": end, "src": ""})
        if analyst.get("down") or analyst.get("downgrade"):
            parts = ([f"목표가 내림 {analyst['down']}곳"] if analyst.get("down") else []) + ([f"의견 낮춤 {analyst['downgrade']}곳"] if analyst.get("downgrade") else [])
            rows.append({"t": "애널리스트 " + " · ".join(parts), "dir": "negative", "stage": "done", "lv": 3, "day": end, "src": ""})
    rows.sort(key=lambda r: r["day"], reverse=True)
    rows.sort(key=lambda r: -r["lv"])   # 대상에 가까운 줄 먼저, 같은 층은 최근 먼저 (안정 정렬) — 논의 중이라고 낮추지 않는다
    out, count = {}, {}
    for key, d in (("good", "positive"), ("bad", "negative"), ("open", "uncertain")):
        sel = [{k: r[k] for k in ("t", "day", "src", "stage", "lv")} for r in rows if r["dir"] == d]
        out[key], count[key] = sel[:SIDE_KEEP], len(sel)
    out["count"] = count
    return out


_UNI = None


def _named(sym, text):
    """문장에 그 종목 한국어 이름(괄호 앞)이 있나."""
    _etf_of(sym)
    if not _UNI or sym not in _UNI.BY_SYM:
        return False
    nm = _UNI.BY_SYM[sym][1].split("(")[0].strip()
    return bool(nm) and nm in (text or "")


def _etf_of(sym):
    """종목 → 업종 ETF (universe.sector_etf, 요약 태그와 같은 기준)."""
    global _UNI
    if _UNI is None:
        sys.path.insert(0, os.path.join(_EXP, "stock-radar"))
        try:
            import universe
            _UNI = universe
        except Exception:  # noqa: BLE001
            _UNI = False
    if not _UNI or sym not in _UNI.BY_SYM:
        return None
    return _UNI.sector_etf(sym)[0]


def _analyst(sym, lo, today, est_path):
    """lo ~ today 에 바뀐 애널리스트 목표가 · 의견 → {"down", "up", "downgrade"} 또는 None."""
    est = _load(est_path) or {}
    seen, down, up, cut_rating = set(), 0, 0, 0
    for day in sorted(est):
        if not (lo <= day <= today):
            continue
        for ch in (((est[day] or {}).get(sym) or {}).get("analysts") or {}).get("changes") or []:
            at = str(ch.get("at") or "")[:10]
            key = (ch.get("firm"), at, ch.get("pt"))
            if key in seen or not (lo <= at <= today):
                continue
            seen.add(key)
            down += ch.get("pt_action") == "Lowers"
            up += ch.get("pt_action") == "Raises"
            cut_rating += ch.get("action") == "down"
    return {"down": down, "up": up, "downgrade": cut_rating} if (down or up or cut_rating) else None


# ---------------------------------------------------------------- 날마다 근거 (2026-11-11 사용자: 타임라인 그날 줄에 한 줄 + 그날 더보기 팝업, 날마다 쌓임)
# 그날 = 직전 타임라인 날 다음 날 ~ 그날(기사 게시 UTC 날짜). 갈래 · 방향이 안 정해진 일은 side_news 그대로, 우리 신호는 전날 기록과 달라진 것만(changes).
# 전망 단계가 레이더보다 먼저 돌아 그날 기사가 다음 실행에 더 들어온다 → forecast_daily 가 최근 REDO_DAYS 날은 다시 모아 덮고 그 앞은 고정.
REDO_DAYS = 2


def w_of(fc):
    """등록 파일 fc → side_news · our_signals 가 쓰는 계열 정보."""
    sr = fc.get("series") or {}
    return {"sym": sr.get("sub"), "mkt": sr.get("mkt"), "stock": fc.get("target") == "stock"}


def day_why(fc, day, prev_day, radar_dir, prev_sigs=None):
    """→ {"day", "good", "bad", "open", "count", "changes": [{name, from, to, dir, hz}], "sigs": [그날 신호 전체 — 다음 날 비교용]}."""
    w = w_of(fc)
    if not w["sym"]:
        return None
    lo = (dt.date.fromisoformat(prev_day) + dt.timedelta(days=1)).isoformat() if prev_day else day
    hi = (dt.date.fromisoformat(day) + dt.timedelta(days=1)).isoformat()
    news = _load(os.path.join(radar_dir, "news.json")) or {}
    an = _analyst(w["sym"], lo, day, os.path.join(radar_dir, "est_history.json")) if w["stock"] else None
    out = {"day": day, **side_news(w, lo, hi, news, os.path.join(radar_dir, "news_summaries.json"), an)}
    try:
        sg = our_signals(w, lo, day, radar_dir) or {}
    except Exception:  # noqa: BLE001
        sg = {}
    cur = [r for r in sg.get("rows") or [] if r["key"] != "picks"]
    before = {r["name"]: r for r in prev_sigs or []}
    out["changes"] = [{"name": r["name"], "from": before[r["name"]]["state"], "to": r["state"], "dir": r["dir"], "hz": r["hz"]}
                      for r in cur if r["name"] in before and before[r["name"]]["state"] != r["state"]]
    out["changes"] += [{"name": r["name"], "from": None, "to": r["state"], "dir": r["dir"], "hz": r["hz"]}
                       for r in sg.get("rows") or [] if r["key"] == "picks" and lo <= day]   # 방송 의견 = 그 기간 새로 나온 것
    out["sigs"] = cur or (prev_sigs or [])
    return out


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
    sc = [{"no": 1, "cond": f"{rw}한다", "name": f"{subject} {rw}", "dir": -s,
           "chain": [{"step": f"{shock} 폭의 4분의 1 {rv}", "state": "wait", "ev": "", "date": ""},
                     {"step": f"{shock} 폭의 절반 {rv}", "state": "wait", "ev": "", "date": ""}],
           "win": f"{subj_ga} {shock} 폭({abs(gap):.1f}{unit})의 절반을 {rv}한다"},
          {"no": 2, "cond": "지속한다", "name": f"{subject} {dw} 지속", "dir": s,
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
    kr = bool(w.get("kr"))
    d5, d20, d60 = _future_tdays(today, WIN_D5, kr), _future_tdays(today, WIN_D20, kr), _future_tdays(today, WIN_END, kr)   # d60 = 만료일 (이름은 옛것, 값은 WIN_END)
    vs = f"{mkt_name}보다 얼마나 더 움직였나(%p)" if mkt else "얼마나 움직였나(%)"
    slug = "forecast-" + eid[3:].lower()   # EH-2026-003 → forecast-2026-003 (영문 주소, 한 번 정하면 바꾸지 않는다)
    fc = {
        "no": 1, "slug": slug, "kind": "after", "auto": True, "publish": True, "target": "stock" if stock else "index", "market": "kr" if kr else "us",
        "title": f"{subject} {shock}, " + ("조정 올까 더 오를까?" if s > 0 else "반등할까 더 빠질까?"),
        "event": f"{_md(shock_day)} {subject} {shock}", "registered": today, "registered_display": _md(today), "posted": _md(today),
        "what": f"{_md(shock_day)} {subject}의 큰 {dw} 뒤 {rw}하는지, 더 이어지는지를 다음 거래일({_md(today)}) 장 마감 뒤에 두 갈래로 적어 두었습니다."
                + (" 종목은 어느 쪽이 맞을지 고르지 않고, 어느 쪽이 일어나는지만 적습니다." if stock else ""),
        "ruler": f"{subject} vs {mkt_name} 상대수익" if mkt else f"{subject} 수익률",
        "ruler_plain": f"{_md(base_day)} 종가부터 {subj_ga} {vs}. {shock} 폭의 절반을 되찾으면 {rw}, 기준만큼 더 가면 지속으로 가른다",
        "ruler_short": f"{subject} vs {'업종' if stock and mkt not in KR_MARKETS else '시장'}" if mkt else subject,
        "ruler_from": f"{_md(base_day)} 종가 대비", "recov_note": f"{_md(shock_day)} 하루 {shock} 폭 대비",
        "start_text": f"{_md(shock_day)} {shock} 뒤 두 갈래를 적었습니다. 다음 거래일부터 봅니다.",
        "hypothesis": "H-급락 뒤 (A 반등 vs B 추세 지속) — 설계 3부 2절 활성 가설 2" if s < 0 else "H-급등 뒤 (A 조정 vs B 추세 지속)",
        "scenarios": sc, "neither": f"그 사이({rw} 4분의 1 ~ 절반)에 머물면 어느 쪽도 아님",
        "checks": [{"date": d5, "label": "중간 확인", "note": f"{rw}의 이른 신호(4분의 1)만 본다"},
                   {"date": d20, "label": "한 달", "note": "판정은 날마다 — 여기는 한 달 지점 확인일 뿐"},
                   {"date": d60, "label": "최종", "note": f"{WIN_END}거래일 뒤 확정. 끝난 전망으로 옮긴다"}],
        "dates": [["게시", _md(today)], [shock, _md(shock_day)], ["최종", _md(d60)], ["첫 확인", _md(d5)]],
        "tags": [w["tag"], rw], "subject": subject, "subj_ga": subj_ga, "cmp": f"{mkt_name}보다" if mkt else None, "unit": unit, "line": float(line),
        "line_src": f"20거래일 움직임 1σ(최근 {LINE_YEARS}년) → 정수 {line}{unit}",
        "gap": round(gap, 1), "base_day": base_day, "end_day": d60, "window": WIN_END, "beta": 1.0,
        "pick": pick, "pick_prob": prob, "pick_strong": strong, "pick_why": why_pick,
        "pick_note": (f"고르지 않음 — 같은 종목 같은 방향 {n}번 중 {m_ok}번 절반을 되찾음 (두 갈래에 나란히)" if stock else
                      f"우리 전망 = pick_side(같은 계열 같은 방향 {n}번 중 {m_ok}번 20거래일 안에 절반을 되찾음) → ‘{sc[pick - 1]['name']}’" + ("" if strong else " · 유력 없음")) + f" ({H.RULES})",
        "series": {"sub": w["sym"], "mkt": mkt}, "shock_day": shock_day, "z": round(z, 1), "late": bool(late), "reasons": why,
        "stock_page": H.page_url(w["page"]) if stock and w.get("page") else None,
        "record": {"result": f"지켜보는 중 (자동 등록 {_md(today)}, 창 D+5 {_md(d5)} · D+20 {_md(d20)} · D+{WIN_END} {_md(d60)})", "overlap": [],
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
    def slot(fc):   # 자리 = (한국?, 종목?) — 한국은 미국과 따로 센다
        return (is_kr(sub_of(fc)), fc.get("target") == "stock")
    opened = {}
    for _, fc in pubs:
        if is_open(fc):
            opened[slot(fc)] = opened.get(slot(fc), 0) + 1
    cap = {(False, False): MAX_OPEN, (False, True): MAX_OPEN_STOCK, (True, False): MAX_OPEN_KR, (True, True): MAX_OPEN_KR_STOCK}
    open_series = {sub_of(fc) for _, fc in pubs if is_open(fc)}
    shocks_seen = {}
    for _, fc in pubs:
        if fc.get("shock_day"):   # 손으로 만든 옛 전망(EH-2026-001 전망 2)은 칸이 없다 — 판정이 끝나 막지 않는다
            shocks_seen.setdefault(sub_of(fc), []).append(fc["shock_day"])
    watch = INDEX + stocks() + KR_INDEX + kr_stocks()
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
        if w.get("kr"):   # 한국 = 한국 마지막 봉이 등록일 (미국 실행 07:30 KST = 한국 장 마감 뒤 · 다음 장 전). 장중 봉은 _long_history 가 뺐다
            if len(days) < 4 or (dt.date.fromisoformat(today) - dt.date.fromisoformat(days[-1])).days > KR_FRESH_DAYS:
                continue
        elif len(days) < 4 or days[-1] != today:   # 긴 일봉에 오늘 봉이 아직 없으면 다음 실행에서
            continue
        hit_days = {h.date().isoformat() for h in hits}
        shock = next(((d, k) for k, d in ((1, days[-2]), (2, days[-3])) if d in hit_days), None)
        if shock:
            found.append((abs(float(z[pd.Timestamp(shock[0])])), w, c, m, z, hits, line, shock[0], shock[1], days[days.index(shock[0]) - 1], days[-1]))
    for _az, w, c, m, z, hits, line, shock_day, lag, base_day, reg_day in sorted(found, key=lambda x: -x[0]):   # 2) 등록
        sym, mkt, stock = w["sym"], w["mkt"], bool(w.get("stock"))
        sl = (bool(w.get("kr")), stock)
        why_skip = None
        if sym in open_series:
            why_skip = "같은 계열 전망이 아직 지켜보는 중"
        elif any(abs((dt.date.fromisoformat(shock_day) - dt.date.fromisoformat(x)).days) <= SAME_EPISODE_DAYS for x in shocks_seen.get(sym, [])):
            why_skip = "같은 묶음(5일 안)으로 이미 등록"
        elif opened.get(sl, 0) >= cap[sl]:
            why_skip = f"지켜보는 {'한국 ' if sl[0] else ''}{'종목 ' if stock else ''}전망 {cap[sl]}개 — 자리 없음"
        sub = px.get(sym) or {}
        mk = (px.get(mkt) or {}) if mkt else None
        if base_day not in sub or shock_day not in sub or (mkt and (base_day not in mk or shock_day not in mk)):
            why_skip = why_skip or "판정용 시세에 충격 날이 없음"
        if why_skip:
            log.append({"day": reg_day, "event": "skipped", "series": sym, "shock_day": shock_day, "why": why_skip})
            print(f"[register] {w['name']} {shock_day} 건너뜀 — {why_skip}")
            continue
        gap = (sub[shock_day] / sub[base_day] - 1) * 100 - ((mk[shock_day] / mk[base_day] - 1) * 100 if mkt else 0)   # 판정과 같은 시세 · β 1
        s = 1 if gap > 0 else -1
        zv = float(z[pd.Timestamp(shock_day)])
        rec = _record(c, m, hits, pd.Timestamp(shock_day), s)
        try:
            why = reasons(w, shock_day, reg_day, s, c, zv, paths)
        except Exception as e:  # noqa: BLE001
            print(f"[register] 이유 모으기 실패: {type(e).__name__}")
            why = None
        eid = _next_id(reg_day[:4], [reg_dir, *read_dirs])
        reg, fc = build(eid, w, reg_day, shock_day, base_day, gap, zv, line, rec, late=lag > 1, why=why)
        try:
            os.makedirs(reg_dir, exist_ok=True)
            with open(os.path.join(reg_dir, f"{eid}.json"), "w", encoding="utf-8") as f:
                json.dump(reg, f, ensure_ascii=False, indent=1)
        except Exception as e:  # noqa: BLE001
            if alert:
                alert.save_failed("자동 등록 파일", e)
            continue
        log.append({"day": reg_day, "event": "registered", "id": eid, "slug": fc["slug"], "series": sym, "target": fc["target"], "shock_day": shock_day,
                    "gap": fc["gap"], "z": fc["z"], "line": line, "pick": fc["pick"], "record": list(rec), "late": lag > 1, "rules": H.RULES})
        print(f"[register] {eid} 등록 — {fc['title']} (충격 {shock_day} {fc['gap']:+.1f}{fc['unit']} · 평소의 {abs(fc['z']):.1f}배 · 기준 {line} · 기록 {rec[1]}번 중 {rec[0]}번)")
        if alert:
            if lag > 1:
                alert.registration_missed(fc["event"], late=True)
            alert.status_changed(fc["title"], "자동 등록")
        out.append((reg, fc))
        opened[sl] = opened.get(sl, 0) + 1
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
