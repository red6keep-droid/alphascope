"""증시 전망 매일 갱신 — 발행 최소판 (기획 증시-전망-기획 5절 · 14절 5, 2026-11-07).

    python experiments/issue_store/forecast_daily.py               # 기본 = 미리보기: 시세 받기 → 판정 → 기록 · 페이지 · 증명 파일을 output/forecast/ 에만
    python experiments/issue_store/forecast_daily.py --state DIR   # 기록을 상태 저장소 폴더(records/forecasts · records/hypotheses)에 덧붙인다
    (Blogger 게시 · gh-pages 증명 커밋 · 워크플로 연결은 아직 없음 — 사용자 확인 뒤 다음 단계)

하는 일 (순서 = 기록 먼저, 렌더 나중):
1. hypotheses/EH-*.json 에서 공개 전망(publish 가 False 아님)만 고른다. 목업 파일(forecast_cases.py)은 절대 읽지 않는다 — 가상 숫자 차단(14절 3).
2. 시세: yfinance → 실패하면 price_source 예비 사슬(FRED → …). 하나도 못 받으면 Slack ‘자료 대기’ 알림 뒤 끝(페이지는 전날 그대로).
2-1. 자동 등록(forecast_register, 2026-11-11): 지수 · 업종 · 종목(업종 대비)이 평소의 3배 넘게 움직인 다음 날이면 틀 R 전망을 새로 적는다(AI 0, 지수 · 업종 3 · 종목 2, 종목은 고르지 않음, 이유 카드).
3. 판정: 매일 시세 이력 전체에서 다시 계산(stateless) — 어제 실행이 죽어도 오늘이 다시 잰다. 빈 날은 건너뛰고 알림.
4. 기록: records/forecasts/{EH}.jsonl 에 그날 한 줄(국면 · 값 · 결과 · 빈 날) 덧붙이기. 결과는 처음 난 날 값으로 고정(시점 고정).
5. 렌더: 전망 페이지 · 목록 · hypo.json · 공개 증명 파일(proof/{slug}.json).
AI 호출 0. 실패는 forecast_alerts 로 한국어 알림(원문 없음).
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))
import hypo_pages as H  # noqa: E402
import forecast_alerts as FA  # noqa: E402
import forecast_register as R  # noqa: E402

assert "forecast_cases" not in sys.modules, "목업 모듈을 읽으면 안 된다 (가상 숫자 차단)"

OUT = os.path.join(_HERE, "output", "forecast")
SYMS = {"sox": "^SOX", "spx": "^GSPC", "vix": "^VIX", "kospi": "^KS11", "kodex_semi": "091160.KS"}


def fetch(start, extra=()):
    """{키: {날짜: 종가}} — yfinance 먼저, 빈 계열만 예비 사슬. 같은 계열을 별칭(sox)과 기호(^SOX) 둘 다로 꺼낼 수 있다.
    extra = 자동 등록 계열 · 자동 전망 계열 기호 (2026-11-11)."""
    syms = dict(SYMS)
    for x in extra:
        if x and x not in syms.values():
            syms[x] = x
    out = {k: {} for k in syms}
    try:
        import yfinance as yf
        df = yf.download(list(syms.values()), start=start, progress=False, auto_adjust=False, threads=False)["Close"]
        for k, sym in syms.items():
            if sym in df:
                s = df[sym].dropna()
                out[k] = {d.date().isoformat(): float(v) for d, v in s.items()}
    except Exception as e:  # noqa: BLE001
        print(f"[forecast] yfinance 실패: {type(e).__name__}")
    for k, sym in syms.items():
        if not out[k]:
            try:
                import price_source
                out[k] = {d: float(c) for d, c in price_source.daily_closes(sym, start)}
            except Exception as e:  # noqa: BLE001
                print(f"[forecast] 예비 사슬 실패 {sym}: {type(e).__name__}")
    part = R.kst_partial_day()
    if part:   # 한국 장중(13:00 KST 실행) 봉은 빼다 — 장중 값으로 판정 · 등록하지 않는다 (2026-11-12)
        for k, sym in syms.items():
            if R.is_kr(sym):
                out[k] = {d: v for d, v in out[k].items() if d < part}
    for k, sym in syms.items():
        out[sym] = out[k]
    return out


def series(px, base_day, beta, sub="sox", mkt="spx"):
    """기준일부터 거래일(시세 날짜 기준 — 가짜 달력 없음) · β 조정 상대수익. 한쪽만 빈 날은 None(건너뜀). mkt=None 이면 수익률 그대로(시장 자체 전망)."""
    have = sorted(d for d in px[sub] if d <= base_day and (mkt is None or d in px[mkt]))
    if have and have[-1] != base_day:   # 기준일이 휴장일(EH-2026-002 감지일 11.07 = 토요일)이면 그 전 마지막 거래일 종가 — 전엔 값이 전부 비어 판정이 멈췄다 (2026-11-11)
        base_day = have[-1]
    if mkt is None:
        days = sorted(d for d in px[sub] if d >= base_day)
        if not days or base_day not in px[sub]:
            return days, [None] * len(days)
        b0 = px[sub][base_day]
        return days, [round((px[sub][d] / b0 - 1) * 100, 2) for d in days]
    days = sorted(d for d in set(px[sub]) | set(px[mkt]) if d >= base_day)
    if not days or base_day not in px[sub] or base_day not in px[mkt]:
        return days, [None] * len(days)
    b0s, b0m = px[sub][base_day], px[mkt][base_day]
    rel = [round((px[sub][d] / b0s - 1) * 100 - beta * (px[mkt][d] / b0m - 1) * 100, 2) if d in px[sub] and d in px[mkt] else None for d in days]
    return days, rel


PRIOR_DAYS = 5   # 감지일 앞 몇 거래일 안의 충격을 보나


def prior_shock(px, fc, sub, mkt):
    """사건 전 전망(감지일 있는 틀 S)의 감지일 앞 PRIOR_DAYS 거래일 안에 같은 계열이 하루에 금(fc["line"], 20거래일 1σ) 넘게 움직인 날 → {"day", "move"}.
    한 달 치 움직임이 하루에 난 날 바로 뒤를 0 으로 재면 그 뒤 되돌림이 선반영처럼 읽힌다 (2026-11-12 사용자: 11.05 반도체 −12% → 11.06 기준 엔비디아 실적 타임라인이 전부 ▲).
    가장 큰 하루 하나만. 없으면 None. 새 수집 없음 — 이미 받은 종가."""
    det = fc.get("detect_day")
    if fc["kind"] != "pre" or not det or sub not in px:
        return None
    beta, L = fc.get("beta") or 1.0, fc.get("line", 3.0)
    ds = [d for d in sorted(px[sub]) if d <= det and (mkt is None or d in px.get(mkt, {}))][-(PRIOR_DAYS + 1):]
    best = None
    for a, b in zip(ds, ds[1:]):
        v = (px[sub][b] / px[sub][a] - 1) * 100 - (beta * (px[mkt][b] / px[mkt][a] - 1) * 100 if mkt else 0.0)
        if abs(v) >= L and (best is None or abs(v) > abs(best[1])):
            best = (b, round(v, 2))
    return {"day": best[0], "move": best[1]} if best else None


def series_of(fc):
    """전망의 (계열, 시장) 키 — 자동 등록은 fc["series"], 손으로 만든 옛 전망은 반도체 vs S&P 500."""
    s = fc.get("series") or {}
    return (s["sub"], s.get("mkt")) if s.get("sub") else ("sox", "spx")


_FRED = {}
_REL = {}


def _load_side():
    """FRED 일별(fetch_fred_daily) · 경제지표 발표일(calendar/econ_releases.csv) — 없으면 빈 채로(그 줄만 생략)."""
    import csv
    import fetch_fred_daily as FF
    for sid in ("DGS10", "BAMLH0A0HYM2", "T10Y2Y"):
        _FRED[sid] = FF.load(sid)
    p = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "data", "store", "calendar", "econ_releases.csv")
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            _REL.setdefault(r["day"], []).append(r["subkind"])


def _diff(series, day):
    ks = sorted(k for k in series if k <= day)
    return round(series[ks[-1]] - series[ks[-2]], 3) if len(ks) >= 2 and ks[-1] == day else None


def today_info(day):
    if not _FRED and not _REL:
        _load_side()
    return {"releases": _REL.get(day, [])[:2], "rate10": _diff(_FRED.get("DGS10", {}), day), "hy": _diff(_FRED.get("BAMLH0A0HYM2", {}), day),
            "curve": _FRED.get("T10Y2Y", {}).get(day)}


def base_of(fc):
    if fc["kind"] == "pre":
        return fc.get("detect_day") or fc.get("base_day") or fc["event_day"]
    return fc.get("base_day", "2026-11-04")


def why_path(slug, state_dir=None):
    """날마다 근거 저장 — 등록 파일 옆 why/{slug}.json = {날짜: day_why}. 상태 저장소에 남아야 8일 뒤 기사가 지워져도 팝업이 그대로다."""
    return os.path.join(H.reg_dirs(state_dir)[1], "why", f"{slug}.json")


def attach_why(fc, st, state_dir=None):
    """타임라인 날(st["log"])마다 근거 — 저장된 날은 그대로, 없는 날 · 최근 REDO_DAYS 날은 새로 모아 덮는다. 판정이 난 뒤엔 쌓지 않는다(로그가 멈춘다).
    갈래별 근거가 없는 옛 등록(reasons 에 good 없음)은 건너뛴다. log 줄에 e["why"] 를 붙여 렌더가 읽는다."""
    if "good" not in (fc.get("reasons") or {}):
        return
    path = why_path(fc["slug"], state_dir)
    saved = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
    radar = os.path.dirname(R.radar_paths(state_dir)[0])
    log = [e for e in st.get("log") or [] if e.get("day") and e.get("key") != "start"]
    days = [e["day"] for e in log]
    redo = set(days[-R.REDO_DAYS:])
    cut = (dt.date.today() - dt.timedelta(days=8)).isoformat()   # 기사 파일이 8일만 남는다 — 그보다 오래된 빈 날은 새로 만들지 않는다
    prev_sigs, changed = None, False
    for i, d in enumerate(days):
        if d in saved and d not in redo:
            prev_sigs = saved[d].get("sigs") or prev_sigs
            continue
        if d < cut:
            continue
        rec = R.day_why(fc, d, days[i - 1] if i else fc.get("registered"), radar, prev_sigs)
        if rec:
            saved[d], changed = rec, True
            prev_sigs = rec.get("sigs") or prev_sigs
    if changed:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(saved, f, ensure_ascii=False, indent=1)
    for e in log:
        if e["day"] in saved:
            e["why"] = {k: v for k, v in saved[e["day"]].items() if k != "sigs"}


def run(state_dir=None):
    regs = H.load_regs(state_dir)
    pub = [(r, fc) for r in regs for fc in H.forecasts(r, public=True)]
    first = min([base_of(fc) for _, fc in pub] + [(dt.date.today() - dt.timedelta(days=30)).isoformat()])   # 자동 등록이 볼 최근 며칠도 받는다
    start = (dt.date.fromisoformat(first) - dt.timedelta(days=14)).isoformat()   # 10 → 14: 감지일 앞 PRIOR_DAYS 거래일 충격까지 보려고
    extra = {x for w in R.INDEX + R.stocks() + R.KR_INDEX + R.kr_stocks() for x in (w["sym"], w["mkt"]) if x} | {(fc.get("series") or {}).get("sub") for _, fc in pub} | {(fc.get("series") or {}).get("mkt") for _, fc in pub}
    px = fetch(start, extra)
    if not px["sox"] or not px["spx"]:
        FA.no_prices()
        return 1
    today = max(px["spx"])
    os.makedirs(os.path.join(OUT, "proof"), exist_ok=True)
    states, lines = {}, []
    tdays_all = sorted(px["spx"])
    for r, fc in pub:
        if fc["kind"] == "pre" and not fc.get("base_day"):   # 결과 직전 종가 (2026-11-08) — 장 마감 뒤 발표만 발표 날 종가
            fc["base_day"] = H.pre_base_day(fc["event_day"], fc.get("release_et"), tdays_all)
    def judge(r, fc):
        try:
            sub, mkt = series_of(fc)
            days, rel = series(px, base_of(fc), fc.get("beta") or 1.0, sub, mkt)
            fc["prior_shock"] = prior_shock(px, fc, sub, mkt)
            vix = [px["vix"].get(d) for d in days] if px["vix"] else None
            cond = fc.get("cond_known")   # 결과가 난 사건 전 전망 — 결과 칸은 사건 날 코드(실적 · FOMC)가 채운다
            st = H.judge(fc, days, rel, cond=cond, vix=vix if vix and all(v is not None for v in vix) else None)
            for e in st["log"]:   # 오늘 나온 것 — 판정엔 안 쓰고 보이기만 (기획 9-2)
                e["today"] = H.today_line(today_info(e["day"]))
            if H.is_stock_fc(fc):   # 현재 증시는? 맨 위 종목 줄 — 판정용으로 이미 받은 종가에서 (새 수집 없음, 2026-11-11 사용자)
                st["quote"] = H.quote_of(px.get(sub))
            if fc["kind"] == "after":   # 현재 증시는? 비교 그래프 — 종목 · 업종 · S&P 500 (이미 받은 종가, 2026-11-11 사용자)
                st["compare"] = H.compare_of(px, fc.get("base_day") or base_of(fc), H.compare_lines(fc))
            if fc["kind"] == "after":   # 타임라인 날마다 근거 (2026-11-11 사용자) — 실패해도 판정 · 렌더는 그대로
                try:
                    attach_why(fc, st, state_dir)
                except Exception as e:  # noqa: BLE001
                    print(f"[forecast] 날마다 근거 실패 {fc['slug']}: {type(e).__name__}")
            states[fc["slug"]] = st
            FA.missing_days(st.get("missing", []))
            e = st["log"][-1]
            lines.append((r["id"], {"day": today, "slug": fc["slug"], "phase": e["key"], "label": e["label"], "rel": st.get("rel"),
                                    "result": (st.get("result") or {}).get("word"), "missing": st.get("missing", []), "rules": r.get("rules")}))
        except Exception as e:  # noqa: BLE001
            FA.judge_failed(fc["title"], e)

    for r, fc in pub:
        judge(r, fc)
    # 자동 등록 (기획 8-1 · 틀 R, AI 0) — 오늘 봉이 충격 다음 날이면 새 전망을 적고 바로 첫 판정(시작 줄)까지
    try:
        reg_dir = H.reg_dirs(state_dir)[1]
        for r, fc in R.register(px, today, pub, states, reg_dir, read_dirs=H.reg_dirs(state_dir)[:1], alert=FA, state_dir=state_dir):
            pub.append((r, fc))
            judge(r, fc)
    except Exception as e:  # noqa: BLE001
        FA.judge_failed("자동 등록", e)
    # 기록 먼저 (덧붙이기만 · 같은 날 두 번이면 두 줄 — 읽는 쪽이 마지막 줄)
    if state_dir:
        try:
            d = os.path.join(state_dir, "records", "forecasts")
            os.makedirs(d, exist_ok=True)
            for eh, row in lines:
                with open(os.path.join(d, f"{eh}.jsonl"), "a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception as e:  # noqa: BLE001
            FA.save_failed("상태 저장소", e)
    # 렌더 나중
    opened, done, score = H.split_done(pub, states)   # 판정 난 전망 = `끝난 전망` (2026-11-12 사용자) — 끝 줄 문구 · 다음 전망도 여기서 붙는다
    others = [(fc["no"], fc["title"], fc["slug"]) for _, fc in pub]
    for r, fc in pub:
        if fc["slug"] not in states:
            continue
        fc["proof_url"] = H.proof_url(fc)
        with open(os.path.join(OUT, "proof", f'{fc["slug"]}.json'), "w", encoding="utf-8") as f:
            json.dump(H.proof_record(r, fc), f, ensure_ascii=False, indent=1)
        html = H.forecast_body(r, states[fc["slug"]], fc, others=[o for o in others if o[2] != fc["slug"]])
        with open(os.path.join(OUT, f'{fc["slug"]}.html'), "w", encoding="utf-8") as f:
            f.write(html)
    with open(os.path.join(OUT, f"{H.LIST_SLUG}.html"), "w", encoding="utf-8") as f:
        f.write(H.list_body(opened, states, done=done, score=score))
    with open(os.path.join(OUT, "hypo.json"), "w", encoding="utf-8") as f:
        json.dump(H.home_card(opened, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), len(done)), f, ensure_ascii=False, indent=1)
    for r, fc in pub:
        st = states.get(fc["slug"]) or {}
        print(f'[forecast] {fc["slug"]}: {st.get("log", [{}])[-1].get("label")} · 값 {st.get("rel")} · 빈 날 {len(st.get("missing", []))}')
    print(f"[forecast] 시세 마지막 날 {today} · 페이지 {len(states)} + 목록 → {OUT}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=None)
    sys.exit(run(ap.parse_args().state))
