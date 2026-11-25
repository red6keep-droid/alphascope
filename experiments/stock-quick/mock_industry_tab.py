"""한국 간단 종목 업계상황 탭 목업 — 업종 고침 · 사업 묶음 뒤 모습 (2026-11-25 사용자 `하림지주가 왜 건설` → 316개 점검 → 묶음 추가).

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

# (종목, 목업에 적는 한 줄)
SAMPLES = [("267260.KS", "새 묶음 `전력기기`"), ("010120.KS", "새 묶음 `전력기기`"), ("001440.KS", "새 묶음 `전선`"),
           ("090430.KS", "새 묶음 `화장품`"), ("192820.KS", "새 묶음 `화장품` (위탁생산)"),
           ("454910.KS", "새 묶음 `로봇` — 완제품 로봇 회사만"), ("058610.KQ", "로봇 부품(감속기) — 수출 통계가 완제품만이라 카드 없음"),
           ("007660.KS", "새 묶음 `인쇄회로기판` — 물량 줄고 값 오름"), ("009150.KS", "새 묶음 `콘덴서` — 사업 일부만이라 안내 줄"), ("011070.KS", "카메라모듈 — 맞는 지표 없어 카드 없음"),
           ("036930.KQ", "건설 수주 → `반도체` 묶음으로 옮김"), ("032820.KQ", "메모리 값 → `원전 · 발전설비` 묶음으로 옮김"),
           ("003380.KQ", "지주회사 — 건설 수주 카드 뺌"), ("006260.KS", "지주회사 — 카드 없음")]
NEW_GROUPS = ("전력기기", "전선", "화장품", "로봇", "인쇄회로기판", "콘덴서")   # 정식 실행보다 먼저 지표를 직접 받는 묶음 — 묶음을 더하면 여기에도


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
            rows = C._ecos(key, stat, "M", "202301", "202612", item)
            if len({x.get("ITEM_CODE2") for x in rows}) > 1:   # 수출입물가 = 원화 기준 (수집기와 같은 규칙)
                rows = [x for x in rows if "원화" in (x.get("ITEM_NAME2") or "")]
            ind[k] = [{"month": f"{x['TIME'][:4]}-{x['TIME'][4:]}", "v": float(x["DATA_VALUE"])} for x in rows if x.get("DATA_VALUE")]
            time.sleep(0.3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flows", default="")
    a = ap.parse_args()
    flows = load_flows(a.flows)
    fetch_new(flows)
    ref = json.load(open(os.path.join(EXP, "ref", "quick_ref.json"), encoding="utf-8"))["kr"]
    body = ['<div style="margin:0 0 16px;">' + dk.muted("한국 간단 종목 업계상황 탭 — 업종 고침 뒤 모습. 지표 값은 실제 ECOS · 관세청 값. "
                                                       "업계 자금 흐름 카드(업종 ETF)는 이 목업에서 뺐습니다 — 운영 화면에는 대표 종목이 있는 묶음(반도체 등)에 나옵니다.") + "</div>"]
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
             "bsi": analyze_kr.bsi_rows(s, flows), "fin": analyze_kr.fin_rows(s, flows), "sector_flow": None}
        body.append(f'<h3 style="margin:28px 0 4px;">{html.escape(e["ko"])} <span style="font-weight:400;font-size:13px;color:#64748B;">'
                    f'{html.escape(e.get("sector") or "")} · {html.escape(e.get("sub") or "")}</span></h3>'
                    f'<div style="margin:0 0 10px;font-size:13px;color:#64748B;">{html.escape(note)}</div>' + render_kr.sec_industry_tab(x))
    print(dk.write_mock("".join(body), os.path.join(HERE, "output", "mock_industry_tab_kr.html"), "한국 간단 종목 업계상황 탭 — 업종 고침 뒤"))


if __name__ == "__main__":
    main()
