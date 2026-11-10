"""증시 전망 자동 등록 — 틀 R(큰 움직임 뒤 반등 · 조정 vs 지속), 기획 증시-전망-기획 8-1 · 8-2 · 8-3 (2026-11-11 사용자 "1을 먼저 해").

forecast_daily.run 이 판정 전에 부른다 (AI 호출 0). 하는 일:
1. 감지 — 지켜보는 계열(WATCH)마다 하루 움직임(업종은 S&P 500 대비 초과, 시장은 그대로)이 평소의 3배(직전 60거래일 표준편차) 넘고
   절대 기준도 넘은 날. detect_sector_shocks.py · detect_shocks.py 와 같은 기준.
2. 등록 시점 — 충격 다음 거래일 장 마감 뒤(= 오늘 봉이 충격 다음 날). 실행이 빠졌으면 하루 늦게까지(늦은 등록 표시 · 알림), 그보다 늦으면 하지 않는다.
3. 막는 장치 — 같은 계열에 아직 판정 안 난 전망이 있으면 건너뛴다 · 같은 계열 충격 5일 안(같은 묶음)이면 건너뛴다 ·
   판정 안 난 공개 전망이 MAX_OPEN 개면 skipped 기록만(기획 8-1, 나중에 '고르지 않은 사건'도 센다).
4. 틀 — 이름 · 자 · 기준 · 고리 · 문장 전부 규칙(8-2). 기준(금) = 그 자의 20거래일 움직임 1σ(최근 10년)를 정수로.
   우리 전망 = 같은 계열 · 같은 방향 지난 충격 뒤 20거래일 안에 절반을 되찾은 비율(hypo_pages.pick_side, 규칙 EH-2026-11-10 — 바깥 연구 가중 없음).
5. 저장 — 등록 파일 EH-YYYY-NNN.json 을 reg_dir(상태 저장소 records/hypotheses · 미리보기는 output/forecast/hypotheses)에, 같은 폴더 YYYY.jsonl 에 registered 한 줄.
   공개 증명(proof) · 고정 페이지는 forecast_daily · publish_forecast 가 다른 전망과 똑같이 만든다.
대상은 지수 · 업종만 — 종목 하나의 방향 전망은 공개하지 않는다(설계 3부 10-2, 매수 추천 금지).
"""
import datetime as dt
import glob
import json
import os

import hypo_pages as H

# (계열 기호, 시장 기호 또는 None, 독자 이름, 이/가 붙은 이름, 절대 기준(%·%p), 분류 라벨)
WATCH = [
    ("^GSPC", None, "S&P 500", "S&P 500이", 2.0, "미국 증시"),
    ("^SOX", "^GSPC", "반도체", "반도체가", 3.0, "반도체"),
    ("XLE", "^GSPC", "에너지 업종", "에너지 업종이", 2.5, "에너지"),
    ("XLF", "^GSPC", "금융 업종", "금융 업종이", 2.5, "금융"),
    ("XLK", "^GSPC", "기술 업종", "기술 업종이", 2.0, "기술"),
    ("XLV", "^GSPC", "헬스케어 업종", "헬스케어 업종이", 2.0, "헬스케어"),
    ("XLU", "^GSPC", "유틸리티 업종", "유틸리티 업종이", 2.0, "유틸리티"),
]
Z_MIN, LOOKBACK = 3.0, 60          # 평소의 3배 · 직전 60거래일 (detect_sector_shocks 와 같다)
MAX_OPEN = 3                       # 동시에 지켜보는 공개 전망 (기획 8-1)
SAME_EPISODE_DAYS = 5              # 같은 계열 충격이 이 안이면 같은 묶음 — 새로 등록하지 않는다
HIST_START = "1998-01-01"          # 같은 종류 기록 · 기준(금) 계산용 긴 일봉
LINE_YEARS = 10                    # 기준(금) = 최근 10년 20거래일 움직임 1σ (1998~2002 반도체 거품 구간이 기준을 7%p 로 부풀렸다)
WIN_D5, WIN_D20, WIN_D60 = 5, 20, 60


def _md(iso):
    return H.md(iso)


def _future_tdays(day, n):
    """day 다음 n 번째 미국 거래일 (연방 공휴일 제외 근사 — 결과 · 최종 날짜 표시용, 판정은 실제 시세 날짜로 한다)."""
    import pandas as pd
    from pandas.tseries.holiday import USFederalHolidayCalendar
    from pandas.tseries.offsets import CustomBusinessDay
    bd = CustomBusinessDay(calendar=USFederalHolidayCalendar())
    return (pd.Timestamp(day) + n * bd).date().isoformat()


def _long_history(syms):
    """긴 일봉(배당 반영) — 감지 · 기준 · 같은 종류 기록용. 실패하면 None (등록만 건너뛰고 판정은 그대로)."""
    try:
        import yfinance as yf
        df = yf.download(sorted(syms), start=HIST_START, progress=False, auto_adjust=True, threads=False)["Close"]
        return df if len(df) else None
    except Exception as e:  # noqa: BLE001
        print(f"[register] 긴 일봉 실패: {type(e).__name__}")
        return None


def _rel_path(c, m, i0, i1):
    """i0 종가 기준 i0..i1 상대수익 %(β 1) — 시장이 없으면 수익률 그대로."""
    out = []
    for i in range(i0, i1 + 1):
        v = (c.iloc[i] / c.iloc[i0] - 1) * 100
        if m is not None:
            v -= (m.iloc[i] / m.iloc[i0] - 1) * 100
        out.append(float(v))
    return out


def _series_stats(df, sym, mkt, amin):
    """→ (일별 움직임 Series, z Series, 충격 날 목록[(위치, 움직임)], 기준(금) 정수)."""
    import numpy as np
    c = df[sym].dropna()
    m = df[mkt].reindex(c.index).ffill() if mkt else None
    r = c.pct_change() * 100
    if m is not None:
        r = r - m.pct_change() * 100
    r = r.dropna()
    z = r / r.rolling(LOOKBACK).std().shift(1)
    hits = [d for d in r.index if abs(z.get(d, 0) or 0) >= Z_MIN and abs(r[d]) >= amin]
    lg = np.log(c).diff() - (np.log(m).diff() if m is not None else 0)
    recent = lg[lg.index >= lg.index[-1] - dt.timedelta(days=365 * LINE_YEARS)]
    line = max(1, int(round(float((recent.rolling(20).sum() * 100).std()))))
    return c, m, r, z, hits, line


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


def _next_id(year, reg_dirs):
    nums = []
    for d in reg_dirs:
        for p in glob.glob(os.path.join(d, f"EH-{year}-*.json")):
            b = os.path.basename(p)[:-5]
            if b.endswith("_prices"):
                continue
            try:
                nums.append(int(b.split("-")[2]))
            except (IndexError, ValueError):
                pass
    return f"EH-{year}-{(max(nums) + 1 if nums else 1):03d}"


def build(eid, w, today, shock_day, base_day, gap, z, line, rec, late):
    """틀 R 전망 한 장 — 기획 8-2 의 고정 문장에 이름만 끼운다 (hypotheses/EH-2026-001 전망 2 와 같은 칸)."""
    sym, mkt, subject, subj_ga, _amin, tag = w
    s = 1 if gap > 0 else -1
    shock, (rw, rv), dw = H.SHOCK[s], H.REV[s], H.DIR_WORD[s]
    unit = "%p" if mkt else "%"
    more = "오름" if s > 0 else "빠짐"
    m_ok, n = rec
    if n:
        pick, prob, why, strong = H.pick_side(m_ok, n)   # m_ok = 절반 되찾은(급락 뒤 반등 · 급등 뒤 조정) 횟수 = 갈래 1
    else:
        pick, prob, why, strong = 1, None, "같은 종류 기록 없음 — 고르기만 하고 유력 없음", False
    sc = [{"no": 1, "cond": f"{rw} 쪽이면", "name": f"{subject} {rw}", "dir": -s,
           "chain": [{"step": f"{shock} 폭의 4분의 1 {rv}", "state": "wait", "ev": "", "date": ""},
                     {"step": f"{shock} 폭의 절반 {rv}", "state": "wait", "ev": "", "date": ""}],
           "win": f"{subj_ga} {shock} 폭({abs(gap):.1f}{unit})의 절반을 {rv}한다"},
          {"no": 2, "cond": "지속 쪽이면", "name": f"{subject} {dw} 지속", "dir": s,
           "chain": [{"step": f"{shock} 뒤 {max(1, round(line / 3))}{unit} 더 {more}", "state": "wait", "ev": "", "date": ""},
                     {"step": f"{shock} 뒤 {line}{unit} 더 {more}", "state": "wait", "ev": "", "date": ""}],
           "win": f"{subj_ga} {shock} 뒤 {line}{unit} 더 {'오른다' if s > 0 else '빠진다'}"}]
    if n:
        k = m_ok if pick == 1 else n - m_ok
        sc[pick - 1]["odds"] = [k, n, "같은 종류 사건 뒤 20거래일"]
    d5, d20, d60 = _future_tdays(today, WIN_D5), _future_tdays(today, WIN_D20), _future_tdays(today, WIN_D60)
    vs = "S&P 500 보다 얼마나 더 움직였나(%p)" if mkt else "얼마나 움직였나(%)"
    slug = "forecast-" + eid[3:].lower()   # EH-2026-003 → forecast-2026-003 (영문 주소, 한 번 정하면 바꾸지 않는다)
    fc = {
        "no": 1, "slug": slug, "kind": "after", "auto": True, "publish": True,
        "title": f"{subject} {shock}, " + ("조정 올까 더 오를까?" if s > 0 else "반등할까 더 빠질까?"),
        "event": f"{_md(shock_day)} {subject} {shock}", "registered": today, "registered_display": _md(today), "posted": _md(today),
        "what": f"{_md(shock_day)} {subject}의 큰 {dw} 뒤 {rw}하는지, 더 이어지는지를 다음 거래일({_md(today)}) 장 마감 뒤에 두 갈래로 적어 두었습니다.",
        "ruler": f"{subject} vs S&P 500 상대수익" if mkt else f"{subject} 수익률",
        "ruler_plain": f"{_md(base_day)} 종가부터 {subj_ga} {vs}. {shock} 폭의 절반을 되찾으면 {rw}, 기준만큼 더 가면 지속으로 가른다",
        "ruler_short": f"{subject} vs 시장" if mkt else subject, "ruler_from": f"{_md(base_day)} 종가 대비", "recov_note": f"{_md(shock_day)} 하루 {shock} 폭 대비",
        "start_text": f"{_md(shock_day)} {shock} 뒤 두 갈래를 적었습니다. 다음 거래일부터 봅니다.",
        "hypothesis": "H-급락 뒤 (A 반등 vs B 추세 지속) — 설계 3부 2절 활성 가설 2" if s < 0 else "H-급등 뒤 (A 조정 vs B 추세 지속)",
        "scenarios": sc, "neither": f"그 사이({rw} 4분의 1 ~ 절반)에 머물면 어느 쪽도 아님",
        "checks": [{"date": d5, "label": "중간 확인", "note": f"{rw}의 이른 신호(4분의 1)만 본다"},
                   {"date": d20, "label": "결과", "note": f"{rw} 절반 · 지속 기준을 처음 적용"},
                   {"date": d60, "label": "최종", "note": "60거래일 뒤 확정. 끝난 전망으로 옮긴다"}],
        "dates": [["게시", _md(today)], [shock, _md(shock_day)], ["최종", _md(d60)], ["첫 확인", _md(d5)]],
        "tags": [tag, rw], "subject": subject, "subj_ga": subj_ga, "cmp": "시장보다" if mkt else None, "unit": unit, "line": float(line),
        "line_src": f"20거래일 움직임 1σ(최근 {LINE_YEARS}년) → 정수 {line}{unit}",
        "gap": round(gap, 1), "base_day": base_day, "end_day": d60, "beta": 1.0,
        "pick": pick, "pick_prob": prob, "pick_strong": strong, "pick_why": why,
        "pick_note": f"우리 전망 = pick_side(같은 계열 같은 방향 {n}번 중 {m_ok}번 20거래일 안에 절반을 되찾음) → ‘{sc[pick - 1]['name']}’" + ("" if strong else " · 유력 없음") + f" ({H.RULES})",
        "series": {"sub": sym, "mkt": mkt}, "shock_day": shock_day, "z": round(z, 1), "late": bool(late),
        "record": {"result": f"지켜보는 중 (자동 등록 {_md(today)}, 창 D+5 {_md(d5)} · D+20 {_md(d20)} · D+60 {_md(d60)})", "overlap": [],
                   "cooccur": {"note": "창 안 상위 3일 이슈 코드 개수 — 매일 갱신 단계에서 채움", "days": []}},
    }
    reg = {"id": eid, "rules": H.RULES, "event": fc["event"], "kind": "shock", "auto": True, "registered_at": today,
           "late_registration": "충격 다음 날 실행이 없어 하루 늦게 등록" if late else None, "forecasts": [fc]}
    return reg, fc


def register(px, today, pubs, states, reg_dir, read_dirs=(), alert=None):
    """오늘 등록할 전망 → [(reg, fc)]. px = forecast_daily 시세({키: {날짜: 종가}}), pubs = [(reg, fc)] 공개 전망, states = 판정 결과.
    reg_dir = 쓸 곳, read_dirs = 번호를 셀 곳(로컬 hypotheses 포함). 실패는 조용히 건너뛴다 — 판정 · 렌더는 그대로."""
    open_n = sum(1 for _, fc in pubs if not (states.get(fc["slug"]) or {}).get("result"))
    open_series = {(fc.get("series") or {"sub": "^SOX"})["sub"] for _, fc in pubs if not (states.get(fc["slug"]) or {}).get("result")}
    shocks_seen = {}
    for _, fc in pubs:
        sub = (fc.get("series") or {"sub": "^SOX"})["sub"]
        d = fc.get("shock_day")   # 손으로 만든 옛 전망(EH-2026-001 전망 2)은 칸이 없다 — 판정이 끝나 막지 않는다
        if d:
            shocks_seen.setdefault(sub, []).append(d)
    df = _long_history({w[0] for w in WATCH} | {w[1] for w in WATCH if w[1]})
    if df is None:
        return []
    import pandas as pd
    out, log, found = [], [], []
    for w in WATCH:   # 1) 감지 — 후보를 다 모은 뒤 크기(평소의 몇 배) 순으로 자리를 준다 (기획 8-1: 같은 종류면 크기 순)
        sym, mkt, subject, _ga, amin, _tag = w
        try:
            c, m, r, z, hits, line = _series_stats(df, sym, mkt, amin)
        except Exception as e:  # noqa: BLE001
            print(f"[register] {subject} 계산 실패: {type(e).__name__}")
            continue
        days = [d.date().isoformat() for d in c.index]
        if not days or days[-1] != today:   # 긴 일봉에 오늘 봉이 아직 없으면 다음 실행에서
            continue
        cand = [(d, k) for k, d in ((1, days[-2]), (2, days[-3])) if len(days) > 3]
        hit_days = {h.date().isoformat() for h in hits}
        shock = next(((d, k) for d, k in cand if d in hit_days), None)
        if not shock:
            continue
        shock_day, lag = shock
        found.append((abs(float(z[pd.Timestamp(shock_day)])), w, c, m, z, hits, line, shock_day, lag, days[days.index(shock_day) - 1]))
    for _az, w, c, m, z, hits, line, shock_day, lag, base_day in sorted(found, key=lambda x: -x[0]):   # 2) 등록
        sym, mkt, subject = w[0], w[1], w[2]
        why_skip = None
        if sym in open_series:
            why_skip = "같은 계열 전망이 아직 지켜보는 중"
        elif any(abs((dt.date.fromisoformat(shock_day) - dt.date.fromisoformat(x)).days) <= SAME_EPISODE_DAYS for x in shocks_seen.get(sym, [])):
            why_skip = "같은 묶음(5일 안)으로 이미 등록"
        elif open_n >= MAX_OPEN:
            why_skip = f"지켜보는 전망 {MAX_OPEN}개 — 자리 없음"
        sub = px.get(sym) or {}
        mk = px.get(mkt) or {} if mkt else None
        if base_day not in sub or shock_day not in sub or (mkt and (base_day not in mk or shock_day not in mk)):
            why_skip = why_skip or "판정용 시세에 충격 날이 없음"
        if why_skip:
            log.append({"day": today, "event": "skipped", "series": sym, "shock_day": shock_day, "why": why_skip})
            print(f"[register] {subject} {shock_day} 건너뜀 — {why_skip}")
            continue
        gap = (sub[shock_day] / sub[base_day] - 1) * 100 - ((mk[shock_day] / mk[base_day] - 1) * 100 if mkt else 0)   # 판정과 같은 시세 · β 1
        s = 1 if gap > 0 else -1
        rec = _record(c, m, hits, pd.Timestamp(shock_day), s)
        eid = _next_id(today[:4], [reg_dir, *read_dirs])
        reg, fc = build(eid, w, today, shock_day, base_day, gap, float(z[pd.Timestamp(shock_day)]), line, rec, late=lag > 1)
        try:
            os.makedirs(reg_dir, exist_ok=True)
            with open(os.path.join(reg_dir, f"{eid}.json"), "w", encoding="utf-8") as f:
                json.dump(reg, f, ensure_ascii=False, indent=1)
        except Exception as e:  # noqa: BLE001
            if alert:
                alert.save_failed("자동 등록 파일", e)
            continue
        log.append({"day": today, "event": "registered", "id": eid, "slug": fc["slug"], "series": sym, "shock_day": shock_day,
                    "gap": fc["gap"], "z": fc["z"], "line": line, "pick": fc["pick"], "record": list(rec), "late": lag > 1, "rules": H.RULES})
        print(f"[register] {eid} 등록 — {fc['title']} (충격 {shock_day} {fc['gap']:+.1f}{fc['unit']} · 평소의 {abs(fc['z']):.1f}배 · 기준 {line} · 기록 {rec[1]}번 중 {rec[0]}번)")
        if alert:
            if lag > 1:
                alert.registration_missed(fc["event"], late=True)
            alert.status_changed(fc["title"], "자동 등록")
        out.append((reg, fc))
        open_n += 1
        open_series.add(sym)
    if log:
        try:
            with open(os.path.join(reg_dir, f"{today[:4]}.jsonl"), "a", encoding="utf-8") as f:
                for row in log:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception as e:  # noqa: BLE001
            if alert:
                alert.save_failed("등록 기록", e)
    return out
