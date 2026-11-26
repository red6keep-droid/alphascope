"""업계 카드 근거 줄 새 모양 목업 — 오른쪽 = 증감(색 굵게) 위 · 수준 값(작은 회색) 아래 (2026-11-26 사용자 "87 · 647.1 은 독자가 모른다").

    .venv/bin/python experiments/stock-quick/mock_industry_row.py

HD현대일렉트릭(전력기기) 한 종목을 세 가지로: 지금 / 바꾼 뒤 A(오른쪽 값만 증감으로) / 바꾼 뒤 B(A + 줄의 비교 기준을 결론 문장과 같게).
스위치 = render_kr.ROW_CHG_FIRST · ROW_SAME_BASE (운영은 둘 다 꺼짐). 결과 = output/mock_industry_row.html
"""
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE]
import mock_industry_tab as M  # noqa: E402

F, K, analyze_kr, render_kr, dk, R, EXP = M.F, M.K, M.analyze_kr, M.render_kr, M.dk, M.R, M.EXP
SYM = "267260.KS"
VERSIONS = [("지금", False, False, "오른쪽 굵은 값 = 수준 값(87 · 647.1), 증감은 아래 회색 줄 안"),
            ("바꾼 뒤 A — 오른쪽 값을 증감으로", True, False, "오른쪽 위 = 증감(빨강 · 파랑 굵게), 아래 = 수준 값(작은 회색). 비교 말은 `작년 같은 달 대비` 하나로. 비교 기준은 지금 그대로(경기 = 전달, 수출 = 한 달)"),
            ("바꾼 뒤 B — A + 비교 기준을 결론 문장과 같게", True, True, "경기 줄 = 결론 문장처럼 석 달 전 대비 · 수출 줄 = 결론 문장처럼 최근 3개월(작년 같은 3개월 대비)")]


def main():
    M.NEW_GROUPS = ("전력기기",)
    flows = M.load_flows("")
    M.fetch_new(flows)
    e = json.load(open(os.path.join(EXP, "ref", "quick_ref.json"), encoding="utf-8"))["kr"][SYM]
    K.CANDIDATES.append((SYM, e["ko"], "q", e.get("sector") or "기타", []))
    K.BY_SYM[SYM] = K.CANDIDATES[-1]
    c = F.code_of(SYM)
    K.BIZ_OF[c] = F.CARD[c]
    for tbl, ind in zip((K.BSI_INDUSTRY, K.FIN_INDUSTRY, K.LOAN_INDUSTRY), K.BIZ_STATS.get(F.CARD[c]) or ()):
        tbl[ind][1].append(SYM)
    x = {"sym": SYM, "code": c, "name": e["ko"], "sector": e.get("sector"), "industry": analyze_kr.industry_rows(SYM, flows),
         "bsi": analyze_kr.bsi_rows(SYM, flows), "fin": analyze_kr.fin_rows(SYM, flows), "related": analyze_kr.related_rows(SYM, flows), "sector_flow": None}
    body = ['<div style="margin:0 0 16px;">' + dk.muted(f"업계 카드 근거 줄 새 모양 — {e['ko']}(전력기기) 업계상황 탭을 세 가지로 그렸습니다. 값은 실제 ECOS 값. 카드는 접혀 있으니 눌러 펼쳐 보세요.") + "</div>"]
    for title, a, b, note in VERSIONS:
        render_kr.ROW_CHG_FIRST, render_kr.ROW_SAME_BASE = a, b
        body.append(f'<h3 style="margin:36px 0 4px;">{html.escape(title)}</h3>'
                    f'<div style="margin:0 0 10px;font-size:13px;color:#64748B;">{html.escape(note)}</div>' + R.small_rows(render_kr.sec_industry_tab(x)))
    render_kr.ROW_CHG_FIRST = render_kr.ROW_SAME_BASE = False
    print(dk.write_mock("".join(body), os.path.join(HERE, "output", "mock_industry_row.html"), "업계 카드 근거 줄 — 증감을 오른쪽 값으로"))


if __name__ == "__main__":
    main()
