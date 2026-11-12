"""한국 전망 근거 목업 (2026-11-12 사용자: "우리가 채울 수 있는 근거를 목업으로 보고 싶어").

    .venv/bin/python experiments/issue_store/mock_kr_why.py
      → output/mock_kr_why-map.html    대상별 · 날짜별로 kr_why 가 채운 근거(방송 · 외국인 · 전날 밤 미국 · 공시) 전부
      → output/mock_kr_why-<slug>.html 한국 전망 페이지에 채운 모습 (로컬 자동 등록 + 한국 반도체 업종 급락 가상 등록)
자료 = 실제 최근 자료(방송 Firestore · kr-state flows · dart_earn · 시세). 새 수집 · AI 없음. 블로그에는 안 나감.
"""
import copy
import datetime as dt
import glob
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))
import design_kit as dk  # noqa: E402
import forecast_daily as F  # noqa: E402
import forecast_register as R  # noqa: E402
import hypo_pages as H  # noqa: E402
import kr_why as K  # noqa: E402

OUT = os.path.join(_HERE, "output")
DAYS = 6   # 지도에 보일 최근 한국 거래일
STOCKS = ["005930.KS", "000660.KS", "005380.KS", "000270.KS", "105560.KS", "035420.KS", "196170.KQ"]
SIDE = {"good": ("상승 쪽", "up"), "bad": ("하락 쪽", "down"), "open": ("향방미정", "flat")}


def fake_fc(w):
    """지도용 — 대상 정보만 담은 전망 모양."""
    return {"series": {"sub": w["sym"], "mkt": w["mkt"]}, "target": "stock" if w.get("stock") else "index", "tags": [w.get("tag")], "subject": w["name"]}


def map_page(targets, px, ctx):
    ks = sorted(px["^KS11"])
    days = ks[-DAYS:]
    body = (f'<p style="margin:0 0 12px;padding:0 {dk.ALIGN_PX}px;font-size:15px;line-height:24px;color:#333;">'
            f'최근 한국 거래일 {len(days)}일({H.md(days[0])} ~ {H.md(days[-1])}) 동안 한국 전망 근거 칸에 들어갈 줄입니다. '
            '방송 = 한국 증시 방송 이슈(요약 두 줄 이상) · 수급 = 외국인 순매수(평소보다 크거나 사흘 넘게) · 미국 = 전날 밤 미국 장(기준보다 크게) · 공시 = 실적 공시일. 운영자 확인용 목업입니다.</p>')
    summary = []
    for w in targets:
        fc = fake_fc(w)
        lines, tot = [], {"good": 0, "bad": 0, "open": 0}
        kinds = {}
        for i, d in enumerate(days):
            prev = ks[ks.index(d) - 1]
            r = K.rows(fc, prev, d, ctx)
            got = [(k, x) for k in ("good", "bad", "open") for x in r[k]]
            for k, x in got:
                tot[k] += 1
                kinds[x["kind"]] = kinds.get(x["kind"], 0) + 1
            if not got:
                lines.append(("row", f'<span style="color:{dk.SUB};">{H.md(d)}</span>', f'<span style="color:{dk.SUB};">근거 없음</span>', ""))
                continue
            for j, (k, x) in enumerate(got):
                nm, kind = SIDE[k]
                lab = H.TS.box(kind, nm, dk.esc, sym=False, fit=True).replace("font-weight:700;", "font-weight:400;", 1)
                lines.append(("row", f'<span style="color:#111;">{H.md(d) if j == 0 else ""}</span>',
                              f'<span style="display:flex;align-items:center;gap:6px;justify-content:flex-end;">{lab}</span>',
                              f'{x["kind"]} · {x["t"]} · {x["src"]}'))
        empty = sum(1 for i, d in enumerate(days) if not any(K.rows(fc, ks[ks.index(d) - 1], d, ctx)[k] for k in ("good", "bad", "open")))
        summary.append((w["name"], tot, kinds, empty))
        head = f'상승 쪽 {tot["good"]} · 하락 쪽 {tot["bad"]} · 향방미정 {tot["open"]} · 빈 날 {empty}/{len(days)}'
        rows_html = "".join(
            f'<div style="padding:10px {dk.ALIGN_PX}px;border-top:1px solid #E2E8F0;display:flex;gap:10px;align-items:flex-start;">'
            f'<span style="flex:none;width:44px;font-size:14px;line-height:22px;">{a}</span><span style="flex:none;">{b}</span>'
            f'<span style="flex:1 1 auto;min-width:0;font-size:15px;line-height:22px;color:#333;word-break:keep-all;">{dk.esc(c)}</span></div>'
            for _, a, b, c in lines)
        body += H._fold_row(f'{w["name"]}  ·  {head}', rows_html)
    # 맨 위 요약 표
    tr = "".join(f'<tr><td style="padding:6px 8px;border-top:1px solid #E2E8F0;">{dk.esc(n)}</td>'
                 f'<td style="padding:6px 8px;border-top:1px solid #E2E8F0;text-align:right;">{t["good"]}</td>'
                 f'<td style="padding:6px 8px;border-top:1px solid #E2E8F0;text-align:right;">{t["bad"]}</td>'
                 f'<td style="padding:6px 8px;border-top:1px solid #E2E8F0;text-align:right;">{t["open"]}</td>'
                 f'<td style="padding:6px 8px;border-top:1px solid #E2E8F0;font-size:13px;color:{dk.SUB};">{" · ".join(f"{k} {v}" for k, v in kd.items()) or "—"}</td>'
                 f'<td style="padding:6px 8px;border-top:1px solid #E2E8F0;text-align:right;">{e}/{len(days)}</td></tr>' for n, t, kd, e in summary)
    table = ('<div style="overflow-x:auto;margin:0 0 16px;"><table style="border-collapse:collapse;width:100%;font-size:14px;line-height:20px;">'
             '<tr style="color:#6B7280;"><th style="text-align:left;padding:6px 8px;">대상</th><th style="padding:6px 8px;">상승 쪽</th><th style="padding:6px 8px;">하락 쪽</th>'
             '<th style="padding:6px 8px;">향방미정</th><th style="text-align:left;padding:6px 8px;">자료별</th><th style="padding:6px 8px;">빈 날</th></tr>' + tr + '</table></div>')
    return dk.h2("한국 전망 근거 지도", line=True) + body.replace("</p>", "</p>" + table, 1)


def fill(fc, st, px, ctx):
    """전망 하나에 한국 근거 — 등록 이유(등록 창) + 타임라인 날마다."""
    reg = fc["registered"]
    ks = sorted(px[(fc.get("series") or {})["sub"]])
    lo = fc.get("shock_day") or reg
    lo = ks[ks.index(lo) - 1] if lo in ks and ks.index(lo) else lo
    fc.setdefault("reasons", {}).update(K.rows(fc, lo, reg, ctx))
    fc["reasons"]["our_signals"] = K.signals(fc, reg, ctx)
    prev, sigs = reg, (fc["reasons"]["our_signals"] or {}).get("rows")
    for e in st["log"]:
        if e.get("key") == "start" or not e.get("day"):
            continue
        e["why"] = K.day_why(fc, e["day"], prev, ctx, sigs)
        prev, sigs = e["day"], e["why"].get("sigs") or sigs


def semi_case(px):
    """가상 등록 — 최근 한국 반도체 업종(KODEX 반도체 vs 코스피) 하루 가장 크게 빠진 날 다음 거래일에 등록했다고 치고."""
    w = next(x for x in R.KR_INDEX if x["sym"] == "091160.KS")
    s, m = px[w["sym"]], px[w["mkt"]]
    ds = [d for d in sorted(s) if d in m]
    moves = [(((s[b] / s[a]) - (m[b] / m[a])) * 100, b, a) for a, b in zip(ds, ds[1:])][-20:]
    gap, shock, base = min(moves)
    today = ds[ds.index(shock) + 1]
    reg, fc = R.build("EH-2026-090", w, today, shock, base, gap, 3.0, 3, (0, 0), False,
                      {"issues": [], "n": 0, "heads": [], "analyst": None, "signals": ["하루 움직임 평소의 3배 넘게 (가상)"], "window": [shock, today]})
    fc["title"] = fc["title"] + " (가상)"
    return reg, fc


def main():
    regs = [H.load(p) for p in sorted(glob.glob(os.path.join(OUT, "forecast", "hypotheses", "EH-*.json")))]
    kr_regs = [(r, fc) for r in regs for fc in H.forecasts(r) if fc.get("market") == "kr"]
    targets = R.KR_INDEX + [w for w in R.kr_stocks() if w["sym"] in STOCKS]
    syms = {w["sym"] for w in targets} | {w["mkt"] for w in targets if w["mkt"]} | {"^SOX", "^GSPC", "^IXIC"} | {(fc.get("series") or {}).get("sub") for _, fc in kr_regs} | {(fc.get("series") or {}).get("mkt") for _, fc in kr_regs}
    px = F.fetch((dt.date.today() - dt.timedelta(days=60)).isoformat(), {s for s in syms if s})
    ctx = K.load_ctx(dt.datetime.now(K.KST).strftime("%Y-%m-%d"), px)
    print(dk.write_mock(map_page(targets, px, ctx), os.path.join(OUT, "mock_kr_why-map.html"), "한국 전망 근거"))
    sr, sfc = semi_case(px)
    for r, fc in kr_regs + [(sr, sfc)]:
        fc = copy.deepcopy(fc)
        sub, mkt = F.series_of(fc)
        days, rel = F.series(px, F.base_of(fc), fc.get("beta") or 1.0, sub, mkt)
        st = H.judge(fc, days, rel)
        if H.is_stock_fc(fc):
            st["quote"] = H.quote_of(px.get(sub))
        st["compare"] = H.compare_of(px, fc.get("base_day") or F.base_of(fc), H.compare_lines(fc))
        fill(fc, st, px, ctx)
        H.chain_track(fc, st)
        if st.get("result"):
            fc["end_text"] = H.end_text(fc, st)   # 실제 실행은 split_done 이 붙인다
        html = H.forecast_body(r, st, fc, others=[])
        print(dk.write_mock(html.replace(f"{H.BLOG}p/", "mock_"), os.path.join(OUT, f'mock_kr_why-{fc["slug"]}.html'), H.CARD_NAME))
        w = fc["reasons"]
        print(f'  {fc["title"]}: 등록 근거 상승 {w["count"]["good"]} · 하락 {w["count"]["bad"]} · 향방미정 {w["count"]["open"]} / 타임라인 근거 날 {sum(1 for e in st["log"] if e.get("why") and any(e["why"][k] for k in ("good", "bad")))}/{len(st["log"]) - 1}')


if __name__ == "__main__":
    main()
