"""한국 간단 종목 업계상황 탭 목업 — 업종 고침 · 사업 묶음 뒤 모습.

    python experiments/stock-quick/mock_industry_tab.py            # 상태 저장소 flows.json 을 gh 로 받아 그린다
    python experiments/stock-quick/mock_industry_tab.py --flows F  # 받아 둔 flows.json

새 묶음 지표(정식 실행이 아직 안 받았을 수 있는 것)는 ECOS · 관세청에서 직접 받는다 — 키 = .env (ECOS_API_KEY · DATA_GO_KR_API_KEY).
업계 자금 흐름 카드(업종 ETF)는 일봉이 있어야 그려져 이 목업에서 뺀다. 종목을 더하려면 SAMPLES 에 한 줄.
결과 = output/mock_industry_tab_kr.html (목업 목록 http://localhost:8800/ PLAN 줄 `stock-quick/mock_industry_*`).
"""
import argparse
import html
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [HERE]
import full_kr as F  # noqa: E402  (full_kr 가 kr-stocks · nvda-report 경로를 넣는다)
import universe_kr as K  # noqa: E402
import analyze_kr  # noqa: E402
import render_kr  # noqa: E402
import collect_kr as C  # noqa: E402
import design_kit as dk  # noqa: E402
import render_html as R  # noqa: E402

# (종목, 목업에 적는 한 줄)
SAMPLES = [("267260.KS", "새 묶음 `전력기기`"), ("010120.KS", "새 묶음 `전력기기`"), ("001440.KS", "새 묶음 `전선`"),
           ("090430.KS", "새 묶음 `화장품`"), ("192820.KS", "새 묶음 `화장품` (위탁생산)"),
           ("454910.KS", "새 묶음 `로봇` — 완제품 로봇 회사만"), ("058610.KQ", "로봇 부품(감속기) — 수출 통계가 완제품만이라 카드 없음"),
           ("007660.KS", "새 묶음 `인쇄회로기판` — 물량 줄고 값 오름"), ("009150.KS", "새 묶음 `콘덴서` — 사업 일부만이라 안내 줄"), ("011070.KS", "카메라모듈 — 맞는 지표 없어 카드 없음"),
           ("214150.KQ", "새 묶음 `의료기기` — 수출 + 업계 경기(의료 · 정밀기기)"), ("096530.KQ", "진단 키트 — 진단 시약 수출이 넓고 출렁여 카드 없음"),
           ("003230.KS", "새 묶음 `라면`"), ("007310.KS", "새 묶음 `가공식품` — 판매 값과 원료 값"), ("139480.KS", "`대형마트` (유통을 업태별로)"), ("282330.KS", "`편의점`"), ("004170.KS", "`백화점` — 면세점도 있어 안내 줄"), ("011170.KS", "새 묶음 `석유화학` — 수출 + 업계 경기 · 수익성"), ("039490.KS", "새 묶음 `증권` — 거래대금"), ("032500.KQ", "새 묶음 `통신장비`"), ("003490.KS", "새 묶음 `항공`"), ("010950.KS", "새 묶음 `정유` — 수출금액과 원유 값"), ("011200.KS", "새 묶음 `해운`"), ("035900.KQ", "새 묶음 `엔터` — 음반 수출"), ("259960.KS", "새 묶음 `게임` — 통계청 게임 소프트웨어 생산"),
           ("008770.KS", "`면세점` — 함께 볼 지표 = 중국인 · 외국인 관광객"), ("383220.KS", "업계 카드 없음 · 함께 볼 지표 = 원/위안"),
           ("030200.KS", "`통신` — 함께 볼 지표 = 휴대전화 요금 물가"), ("181710.KS", "`플랫폼` — 함께 볼 지표 = 광고업 · 온라인 쇼핑"),
           ("036930.KQ", "건설 수주 → `반도체` 묶음으로 옮김"), ("032820.KQ", "메모리 값 → `원전 · 발전설비` 묶음으로 옮김"),
           ("003380.KQ", "지주회사 — 건설 수주 카드 뺌"), ("006260.KS", "지주회사 — 카드 없음")]
NEW_GROUPS = ("전력기기", "전선", "화장품", "로봇", "인쇄회로기판", "콘덴서", "의료기기",
              "라면", "가공식품", "백화점", "대형마트", "면세점", "편의점", "게임", "석유화학", "증권", "통신장비", "항공", "정유", "해운", "엔터")   # 정식 실행보다 먼저 지표를 직접 받는 묶음 — 묶음을 더하면 여기에도


def load_flows(path):
    if path:
        return json.load(open(path, encoding="utf-8"))
    tmp = os.path.join(tempfile.gettempdir(), "kr_flows_mock.json")
    with open(tmp, "wb") as f:
        subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw",
                        "repos/red6keep-droid/alphascope-state/contents/experiments/kr-stocks/data/flows.json?ref=kr-state"], stdout=f, check=True)
    return json.load(open(tmp, encoding="utf-8"))


def fetch_new(flows):
    key = C._ecos_key()
    ind = flows.setdefault("industry", {})
    for g in NEW_GROUPS:
        for k in K.BIZ[g]["inds"]:
            stat, item = K.INDICATORS[k][:2]
            if stat == "customs":
                ind[k] = C._customs(K.CUSTOMS[k])
                continue
            if stat == "kosis":
                ind[k] = C._kosis(item)
                continue
            rows = C._ecos(key, stat, "M", "202301", "202612", item)
            if len({x.get("ITEM_CODE2") for x in rows}) > 1:   # 수출입물가 = 원화 기준 (수집기와 같은 규칙)
                rows = [x for x in rows if "원화" in (x.get("ITEM_NAME2") or "")]
            ind[k] = [{"month": f"{x['TIME'][:4]}-{x['TIME'][4:]}", "v": float(x["DATA_VALUE"])} for x in rows if x.get("DATA_VALUE")]
            time.sleep(0.3)
    flows["industry"].update(C._tourism(flows["industry"]))   # 정식 실행보다 먼저 (2026-11-25 함께 볼 지표)
    flows["release_plan"] = C._release_plan() or flows.get("release_plan") or []
    for k in {k for v in list(K.RELATED.values()) + list(K.RELATED_CODE.values()) for k, _w in v}:   # 함께 볼 지표 중 상태 파일에 아직 없는 ECOS 지표
        if k in ind or k not in K.INDICATORS or K.INDICATORS[k][0] in ("customs", "tourism"):
            continue
        if K.INDICATORS[k][0] == "kosis":
            ind[k] = C._kosis(K.INDICATORS[k][1])
            continue
        stat, item = K.INDICATORS[k][:2]
        rows = C._ecos(key, stat, "M", "202301", "202612", item)
        if len({x.get("ITEM_CODE2") for x in rows}) > 1:
            rows = [x for x in rows if "원화" in (x.get("ITEM_NAME2") or "")]
        ind[k] = [{"month": f"{x['TIME'][:4]}-{x['TIME'][4:]}", "v": float(x["DATA_VALUE"])} for x in rows if x.get("DATA_VALUE")]
        time.sleep(0.3)
    bsi = flows.setdefault("bsi", {})
    for g in NEW_GROUPS:   # 업계 경기 업종이 상태 파일에 아직 없으면 직접 (정식 실행보다 먼저, 의료기기 C2700)
        for ind in (K.BIZ_STATS.get(g) or ())[:1]:
            if bsi.get(ind):
                continue
            got = {}
            for stat in ("512Y007", "512Y008"):
                for x in C._ecos(key, stat, "M", C.BSI_START, "202612", f"?/{ind}", n=5000):
                    if x.get("DATA_VALUE") not in (None, ""):
                        got.setdefault(x["ITEM_CODE1"], []).append({"month": f"{x['TIME'][:4]}-{x['TIME'][4:]}", "v": float(x["DATA_VALUE"])})
                time.sleep(0.3)
            bsi[ind] = {k: sorted(v, key=lambda r: r["month"]) for k, v in got.items()}


def _card_input(s, e, flows):
    rep = F.rep_of(s, e)
    if s not in K.BY_SYM:
        K.CANDIDATES.append((s, e["ko"], "q", e.get("sector") or "기타", list(K.groups(rep)) if rep else []))
        K.BY_SYM[s] = K.CANDIDATES[-1]
    c = F.code_of(s)
    if not rep and F.CARD.get(c) in K.BIZ:
        K.BIZ_OF[c] = F.CARD[c]
    return {"sym": s, "code": c, "name": e["ko"], "sector": e.get("sector"), "industry": analyze_kr.industry_rows(s, flows),
            "bsi": [], "fin": [], "related": [], "sector_flow": None}


def split_variants(flows, ref):
    """1-3 시안 — 증권 업계 카드: 1년 전 대비 `늘고 있음` 인데 최근 고점의 41%. 지금 · A(답 엇갈림) · B(답 그대로 + 고점 문장).
    아래 표 = 같은 규칙(판정 `늘고 있음` 류 + 지금 ≤ 최근 12개월 고점 70%)에 걸리는 다른 묶음 — 1-6."""
    x = _card_input("039490.KS", ref["039490.KS"], flows)
    out = ('<div style="margin:0 0 8px;font-size:14px;line-height:21px;color:#6B7280;word-break:keep-all;">'
           '1-3 시안 — 키움증권 업계상황 탭 `증권 업계 증시 거래는?`. 판정은 작년 같은 달 대비인데, 그래프는 6월 고점에서 넉 달째 내려옴. '
           '갈림 = 판정이 늘어나는 쪽인데 지금 값이 최근 12개월 고점의 70% 이하이고 3개월 넘게 연달아 줄어듦(보험 생산지수처럼 12월에만 튀는 계절 지표는 안 걸리게).</div>')
    rows = [(None, "지금", "작년 같은 달 대비 하나로 답합니다."),
            ("A", "A안 (추천)", "갈리면 답을 `엇갈림`(회색)으로, 문장에 고점 대비와 줄어든 달 수를 씁니다."),
            ("B", "B안", "답은 그대로 두고, 문장 끝에 고점 대비와 줄어든 달 수만 더합니다.")]
    for k, (mode, tag, how) in enumerate(rows):
        render_kr.SPLIT[0] = mode
        out += (f'<div style="margin:{8 if k == 0 else 28}px 0 0;font-size:16px;line-height:24px;font-weight:700;color:#111;">{html.escape(tag)}</div>'
                f'<div style="margin:0 0 6px;font-size:13px;line-height:19px;color:#6B7280;">{html.escape(how)}</div>' + R.small_rows(render_kr.card_industry_work(x)))
    render_kr.SPLIT[0] = None
    hits, checked = [], []
    ind = flows.get("industry") or {}
    for g, b in K.BIZ.items():   # 종목을 거치지 않고 묶음마다 첫 지표 계열을 직접 (카드 판정과 같은 첫 줄)
        if b.get("months", 1) != 1 or not b.get("inds"):
            continue
        key = b["inds"][0]
        if key not in K.INDICATORS or len(ind.get(key) or []) < 13:
            continue
        xs = ind[key]
        r0 = {"series": xs[-24:], "month": xs[-1]["month"], "kind": K.INDICATORS[key][3], "name": K.INDICATORS[key][2]}
        chg, _ = render_kr._window_change(r0, 1)
        lim = 0.5 if r0["kind"] == "pct" else 5
        up_w, dn_w = render_kr.BIZ_WORDS[b["mode"]]
        st = "판단 유보" if chg is None else up_w if chg >= lim else dn_w if chg <= -lim else "비슷함"
        checked.append(g)
        sp = render_kr.peak_split(r0, st, b["mode"])
        if sp:
            hits.append(f'{g} — {r0["name"]} : 작년 같은 달보다 {chg:+.1f}% ({st}), 지금 = 최근 고점({int(sp[0][5:])}월)의 {sp[2] * 100:.0f}% · {sp[3]}개월째 줄어')
    out += ('<div style="margin:28px 0 0;font-size:16px;line-height:24px;font-weight:700;color:#111;">같은 규칙에 걸리는 업계 카드 — 한 달 기준 묶음 전체, 지금 자료 (1-6)</div>'
            + "".join(f'<div style="font-size:14px;line-height:21px;color:#374151;">· {html.escape(h)}</div>' for h in hits)
            if hits else '<div style="margin:28px 0 0;font-size:14px;color:#6B7280;">같은 규칙에 걸리는 업계 카드 없음 (1-6)</div>')
    out += f'<div style="font-size:13px;color:#6B7280;">살펴본 묶음 {len(checked)}개 / 한 달 기준 묶음 {sum(1 for b in K.BIZ.values() if b.get("months", 1) == 1)}개</div>'
    return out + '<div style="margin:40px 0 0;padding-top:16px;border-top:2px solid #111;font-size:14px;color:#6B7280;">아래 = 지금 목업 전체</div>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flows", default="")
    a = ap.parse_args()
    flows = load_flows(a.flows)
    fetch_new(flows)
    ref = json.load(open(os.path.join(EXP, "ref", "quick_ref.json"), encoding="utf-8"))["kr"]
    body = ['<div style="margin:0 0 16px;">' + dk.muted("한국 간단 종목 업계상황 탭 — 업종 고침 뒤 모습. 지표 값은 실제 ECOS · 관세청 값. "
                                                       "업계 자금 흐름 카드(업종 ETF)는 이 목업에서 뺐습니다 — 운영 화면에는 대표 종목이 있는 묶음(반도체 등)에 나옵니다.") + "</div>"]
    body.append(split_variants(flows, ref))
    for s, note in SAMPLES:
        e = ref[s]
        rep = F.rep_of(s, e)
        K.CANDIDATES.append((s, e["ko"], "q", e.get("sector") or "기타", list(K.groups(rep)) if rep else []))
        K.BY_SYM[s] = K.CANDIDATES[-1]
        c = F.code_of(s)
        if c in F.CARD_OFF:
            K.SECTOR_FALLBACK_OFF.add(s)
        if not rep and F.CARD.get(c) in K.BIZ:   # full_kr.build 와 같은 순서
            K.BIZ_OF[c] = F.CARD[c]
            for tbl, ind in zip((K.BSI_INDUSTRY, K.FIN_INDUSTRY, K.LOAN_INDUSTRY), K.BIZ_STATS.get(F.CARD[c]) or ()):
                tbl[ind][1].append(s)
        if rep:
            F.alias(rep, s)
        x = {"sym": s, "code": c, "name": e["ko"], "sector": e.get("sector"), "industry": analyze_kr.industry_rows(s, flows),
             "bsi": analyze_kr.bsi_rows(s, flows), "fin": analyze_kr.fin_rows(s, flows), "related": analyze_kr.related_rows(s, flows), "sector_flow": None}
        body.append(f'<h3 style="margin:28px 0 4px;">{html.escape(e["ko"])} <span style="font-weight:400;font-size:13px;color:#64748B;">'
                    f'{html.escape(e.get("sector") or "")} · {html.escape(e.get("sub") or "")}</span></h3>'
                    f'<div style="margin:0 0 10px;font-size:13px;color:#64748B;">{html.escape(note)}</div>' + R.small_rows(render_kr.sec_industry_tab(x)))
    print(dk.write_mock(dk.formal("".join(body)), os.path.join(HERE, "output", "mock_industry_tab_kr.html"), "한국 간단 종목 업계상황 탭 — 업종 고침 뒤"))


if __name__ == "__main__":
    main()
