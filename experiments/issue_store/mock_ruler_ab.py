"""판정 자 그래프 A · B · C 비교 목업.

    .venv/bin/python experiments/issue_store/mock_ruler_ab.py
      → output/mock_ruler_ab.html    A · B 나란히 (폰 폭 두 칸)
      → output/mock_ruler_a.html     A = 선 두 개(브로드컴 · 업종, 11.11 종가 대비 %) + 기준선은 업종 선을 따라 움직임
      → output/mock_ruler_b.html     B = 선 하나(업종보다 더 오른 폭) + 0선 = 업종 이름표, `vs` 없음
      → output/mock_ruler_c.html     C = 판정 그래프 빼고 위 비교 그래프에 기준선 둘 (사용자 제안)
자료 = 블로그의 실제 `브로드컴 급등` 전망(state nvda-state EH-2026-007) + 종가. 새 수집(야후 종가)만 · AI 없음. 블로그에는 안 나감.
"""
import copy
import datetime as dt
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))
import design_kit as dk  # noqa: E402
import forecast_daily as F  # noqa: E402
import hypo_pages as H  # noqa: E402

OUT = os.path.join(_HERE, "output")
REG = "state/nvda-state:experiments/nvda-report/output/state/records/hypotheses/EH-2026-007.json"
IND = "#14B8A6"   # 업종 청록 = 위 비교 그래프와 같은 색 (CMP_COLORS[1])


def build(variant, reg, px):
    fc = copy.deepcopy(reg["forecasts"][0])
    sub, mkt = F.series_of(fc)
    days, rel = F.series(px, F.base_of(fc), fc.get("beta") or 1.0, sub, mkt)
    st = H.judge(fc, days, rel)
    st["quote"] = H.quote_of(px.get(sub))
    st["compare"] = H.compare_of(px, fc.get("base_day") or F.base_of(fc), H.compare_lines(fc))
    H.chain_track(fc, st)
    ind_name = "업종" if "업종" in fc["ruler_short"] else "시장"
    cmp_name = (fc.get("cmp") or "").removesuffix("보다")   # 위 비교 그래프의 업종 선 이름 (반도체 지수)
    orig = dk.trend_card

    def card(title, labels, series, fmt, **kw):
        if variant == "c":   # 판정 그래프는 빼고, 위 비교 그래프에 기준선 둘 — 업종 선 + 기준 폭
            if title.startswith(fc["ruler_short"]):
                return ""
            g, L = fc["gap"], fc["line"]
            sgn = 1 if g > 0 else -1
            ind = next((v for nm, v, _, _ in series if nm == cmp_name), None)
            if ind:
                sh = lambda d: [None if v is None else round(v + d, 2) for v in ind]  # noqa: E731
                series = list(series) + [(f"{H.REV[sgn][0]} 기준", sh(g * 0.5), "#93C5FD" if sgn > 0 else "#FCA5A5", "guide"),
                                         (f"{H.DIR_WORD[sgn]} 지속 기준", sh(g + sgn * L), "#FCA5A5" if sgn > 0 else "#93C5FD", "guide")]
            return orig(title, labels, series, fmt, **kw)
        if not title.startswith(fc["ruler_short"]):
            return orig(title, labels, series, fmt, **kw)
        n = len(labels)
        guides = series[1:]
        if variant == "b":   # 선 하나 · 0선 = 업종 이름표
            return orig(f'{fc["subject"]}이 {ind_name}보다 더 오른 폭 (%p)', labels,
                        [(f'{fc["subject"]}', series[0][1], dk.CHART_MAIN, "solid"), (f"{ind_name} (0)", [0] * n, dk.CHART_CMP, "dash")] + guides, fmt, **kw)
        # A — 두 선(기준일 대비 %) · 기준선 = 업종 선 + 기준 폭
        st_days = st["days"]
        b = st_days[0]
        pct = lambda s, d: round((px[s][d] / px[s][b] - 1) * 100, 2) if d in px[s] and b in px[s] else None  # noqa: E731
        s_v = [pct(sub, d) for d in st_days]
        m_v = [pct(mkt, d) for d in st_days]
        g2 = [(nm, [None if m is None else round(m + v[0], 2) for m in m_v], col, kind) for nm, v, col, kind in guides]
        return orig(f'{H.md(b)} 종가 대비 (%)', labels,
                    [(fc["subject"], s_v, dk.CHART_MAIN, "solid"), (ind_name, m_v, IND, "solid")] + g2,
                    lambda v: f"{v:+.1f}%".replace("-", "−"), **dict(kw, legend_plain=False))   # 두 선이라 범례에 브로드컴도

    dk.trend_card = card
    if variant == "b":
        fc["ruler_short"] = f'{fc["subject"]}이 {ind_name}보다 더 오른 폭'
    else:
        fc["ruler_short"] = f'{fc["subject"]} · {ind_name}'   # `vs` 없이 — 제목 앞 `브로드컴 —` 값 줄도 빠진다
    try:
        html = H.forecast_body(reg, st, fc, others=[])
    finally:
        dk.trend_card = orig
    return html


def main():
    raw = subprocess.run(["git", "show", REG], cwd=os.path.dirname(os.path.dirname(_HERE)), capture_output=True).stdout
    if not raw:
        sys.exit("상태 브랜치(state/nvda-state)를 먼저 받으세요: git fetch state nvda-state")
    reg = json.loads(raw)
    sr = reg["forecasts"][0]["series"]
    px = F.fetch((dt.date.today() - dt.timedelta(days=40)).isoformat(), {sr["sub"], sr["mkt"], "^GSPC"})
    for v in ("a", "b", "c"):
        html = build(v, reg, px).replace("비교 대상 : 조정 기준", "조정 기준").replace("비교 대상 : 상승 지속 기준", "상승 지속 기준").replace('<details data-acc="1" class="fc-fsec"', '<details open data-acc="1" class="fc-fsec"')   # 비교용 = 접는 줄 펼친 채
        print(dk.write_mock(html.replace(f"{H.BLOG}p/", "mock_"), os.path.join(OUT, f"mock_ruler_{v}.html"), H.CARD_NAME))
    side = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>판정 그래프 A · B</title><style>body{margin:0;background:#F1F5F9;font-family:sans-serif;}'
            '.row{display:flex;gap:16px;padding:16px;overflow-x:auto;}.col{flex:none;width:400px;}'
            'h3{margin:0 0 8px;font-size:16px;line-height:24px;}p{margin:0 0 8px;font-size:13px;line-height:19px;color:#555;}'
            'iframe{width:400px;height:2400px;border:1px solid #CBD5E1;border-radius:8px;background:#fff;}</style></head><body><div class="row">'
            '<div class="col"><h3>A · 선 두 개</h3><p>브로드컴 · 업종을 각각 11.11 종가 대비 %로. 기준선은 업종 선을 따라 움직입니다.</p><iframe src="mock_ruler_a.html"></iframe></div>'
            '<div class="col"><h3>B · 선 하나 + 0선 = 업종</h3><p>제목 `업종보다 더 오른 폭`, 0선에 업종 이름표. vs 없음.</p><iframe src="mock_ruler_b.html"></iframe></div>'
            '<div class="col"><h3>C · 그래프 하나 + 기준선</h3><p>아래 판정 그래프를 빼고, 위 비교 그래프에 조정 기준 · 상승 지속 기준 두 선만 더했습니다.</p><iframe src="mock_ruler_c.html"></iframe></div>'
            '</div></body></html>')
    p = os.path.join(OUT, "mock_ruler_ab.html")
    open(p, "w", encoding="utf-8").write(side)
    print(p)


if __name__ == "__main__":
    main()
