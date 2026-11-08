"""증시 전망 매일 갱신 — 발행 최소판 (기획 증시-전망-기획 5절 · 14절 5, 2026-11-07).

    python experiments/issue_store/forecast_daily.py               # 기본 = 미리보기: 시세 받기 → 판정 → 기록 · 페이지 · 증명 파일을 output/forecast/ 에만
    python experiments/issue_store/forecast_daily.py --state DIR   # 기록을 상태 저장소 폴더(records/forecasts · records/hypotheses)에 덧붙인다
    (Blogger 게시 · gh-pages 증명 커밋 · 워크플로 연결은 아직 없음 — 사용자 확인 뒤 다음 단계)

하는 일 (순서 = 기록 먼저, 렌더 나중):
1. hypotheses/EH-*.json 에서 공개 전망(publish 가 False 아님)만 고른다. 목업 파일(forecast_cases.py)은 절대 읽지 않는다 — 가상 숫자 차단(14절 3).
2. 시세: yfinance → 실패하면 price_source 예비 사슬(FRED → …). 하나도 못 받으면 Slack ‘자료 대기’ 알림 뒤 끝(페이지는 전날 그대로).
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

assert "forecast_cases" not in sys.modules, "목업 모듈을 읽으면 안 된다 (가상 숫자 차단)"

OUT = os.path.join(_HERE, "output", "forecast")
SYMS = {"sox": "^SOX", "spx": "^GSPC", "vix": "^VIX", "kospi": "^KS11", "kodex_semi": "091160.KS"}


def fetch(start):
    """{키: {날짜: 종가}} — yfinance 먼저, 빈 계열만 예비 사슬."""
    out = {k: {} for k in SYMS}
    try:
        import yfinance as yf
        df = yf.download(list(SYMS.values()), start=start, progress=False, auto_adjust=False, threads=False)["Close"]
        for k, sym in SYMS.items():
            if sym in df:
                s = df[sym].dropna()
                out[k] = {d.date().isoformat(): float(v) for d, v in s.items()}
    except Exception as e:  # noqa: BLE001
        print(f"[forecast] yfinance 실패: {type(e).__name__}")
    for k, sym in SYMS.items():
        if not out[k]:
            try:
                import price_source
                out[k] = {d: float(c) for d, c in price_source.daily_closes(sym, start)}
            except Exception as e:  # noqa: BLE001
                print(f"[forecast] 예비 사슬 실패 {sym}: {type(e).__name__}")
    return out


def series(px, base_day, beta, sub="sox", mkt="spx"):
    """기준일부터 거래일(시세 날짜 기준 — 가짜 달력 없음) · β 조정 상대수익. 한쪽만 빈 날은 None(건너뜀)."""
    days = sorted(d for d in set(px[sub]) | set(px[mkt]) if d >= base_day)
    if not days or base_day not in px[sub] or base_day not in px[mkt]:
        return days, [None] * len(days)
    b0s, b0m = px[sub][base_day], px[mkt][base_day]
    rel = [round((px[sub][d] / b0s - 1) * 100 - beta * (px[mkt][d] / b0m - 1) * 100, 2) if d in px[sub] and d in px[mkt] else None for d in days]
    return days, rel


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


def run(state_dir=None):
    regs = [H.load(p) for p in sorted(glob.glob(os.path.join(_HERE, "hypotheses", "EH-*.json"))) if not p.endswith("_prices.json")]
    pub = [(r, fc) for r in regs for fc in H.forecasts(r, public=True)]
    start = (dt.date.fromisoformat(min(base_of(fc) for _, fc in pub)) - dt.timedelta(days=10)).isoformat()
    px = fetch(start)
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
    for r, fc in pub:
        try:
            days, rel = series(px, base_of(fc), fc.get("beta") or 1.0)
            vix = [px["vix"].get(d) for d in days] if px["vix"] else None
            cond = fc.get("cond_known")   # 결과가 난 사건 전 전망 — 결과 칸은 사건 날 코드(실적 · FOMC)가 채운다
            st = H.judge(fc, days, rel, cond=cond, vix=vix if vix and all(v is not None for v in vix) else None)
            for e in st["log"]:   # 오늘 나온 것 — 판정엔 안 쓰고 보이기만 (기획 9-2)
                e["today"] = H.today_line(today_info(e["day"]))
            states[fc["slug"]] = st
            FA.missing_days(st.get("missing", []))
            e = st["log"][-1]
            lines.append((r["id"], {"day": today, "slug": fc["slug"], "phase": e["key"], "label": e["label"], "rel": st.get("rel"),
                                    "result": (st.get("result") or {}).get("word"), "missing": st.get("missing", []), "rules": r.get("rules")}))
        except Exception as e:  # noqa: BLE001
            FA.judge_failed(fc["title"], e)
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
        f.write(H.list_body(pub, states))
    with open(os.path.join(OUT, "hypo.json"), "w", encoding="utf-8") as f:
        json.dump(H.home_card(pub, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")), f, ensure_ascii=False, indent=1)
    for r, fc in pub:
        st = states.get(fc["slug"]) or {}
        print(f'[forecast] {fc["slug"]}: {st.get("log", [{}])[-1].get("label")} · 값 {st.get("rel")} · 빈 날 {len(st.get("missing", []))}')
    print(f"[forecast] 시세 마지막 날 {today} · 페이지 {len(states)} + 목록 → {OUT}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=None)
    sys.exit(run(ap.parse_args().state))
