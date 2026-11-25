"""미국 간단 종목 업계상황 탭 목업 — 배정 고침 · 새 묶음 · 함께 볼 지표 뒤 모습 (2026-11-25 사용자 "미국도 한국처럼 끝까지").

    python experiments/stock-quick/mock_industry_tab_us.py

FRED 값을 직접 받는다(키 = .env FRED_API_KEY, 하루 한 번 — 임시 폴더 캐시). 업계 자금 흐름 카드(업종 ETF)는 일봉이 있어야 그려져 이 목업에서 뺀다.
종목을 더하려면 SAMPLES 에 한 줄. 결과 = output/mock_industry_tab_us.html (목업 목록 http://localhost:8800/).
"""
import html
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE]
import full_us as F  # noqa: E402  (full_us 가 stock-radar · nvda-report 경로를 넣는다)
import industry_us as I  # noqa: E402

RP, dk = F.RP, F.dk
# (종목, 목업에 적는 한 줄)
SAMPLES = [("HLT", "새 묶음 `여행 · 숙박` — 카드 없음 → 숙박 요금"), ("DAL", "새 묶음 `항공` — 여객 · 요금 + 항공유 값"), ("DHI", "새 묶음 `주택 건설`"), ("LMT", "새 묶음 `방산`"),
           ("RTX", "`항공우주` + `방산` 둘 다"), ("ETN", "비주거 건설 → `전기 장비`"), ("PCAR", "비주거 건설 → `트럭`"), ("UNP", "새 묶음 `철도`"), ("V", "새 묶음 `결제`"),
           ("GS", "새 묶음 `증권 · 자산운용` (분기)"), ("PGR", "새 묶음 `손해보험`"), ("ISRG", "새 묶음 `의료기기`"), ("UNH", "새 묶음 `건강보험`"), ("DELL", "새 묶음 `컴퓨터 장비`"),
           ("T", "새 묶음 `통신` (분기)"), ("NUE", "새 묶음 `철강`"), ("EQT", "유가 → `천연가스`"), ("VLO", "유가 → `정유` + 원유 값"), ("MO", "소매판매 → `담배`"),
           ("GIS", "소매판매 → `식료품`"), ("NVDA", "정식 종목 — 함께 볼 지표 = 데이터센터 매출"), ("JPM", "정식 종목 — 함께 볼 지표 = 금리 · 연체율"),
           ("FSLR", "반도체 카드 뺌 — 함께 볼 지표만"), ("SPG", "업계 카드 없음 — 함께 볼 지표만"), ("BRK-B", "은행 카드 뺌 — 함께 볼 지표만"), ("TTWO", "카드 없음")]


def main():
    I.CACHE = os.path.join(tempfile.gettempdir(), "fred_us_mock.json")
    data = I.fetch()
    ref = json.load(open(os.path.join(F.EXP, "ref", "quick_ref.json"), encoding="utf-8"))["us"]
    body = ['<div style="margin:0 0 16px;">' + dk.muted("미국 종목 업계상황 탭 — 배정 고침 뒤 모습. 지표 값은 실제 FRED 값. 업계 자금 흐름 카드(업종 ETF)는 이 목업에서 뺐습니다.") + "</div>"]
    for s, note in SAMPLES:
        e = ref.get(s) or {}
        x = {"sym": s, "name": e.get("ko") or s, "industry_us": I.build(s, data), "sector_flow": None}
        body.append(f'<h3 style="margin:28px 0 4px;">{html.escape(x["name"])} <span style="font-weight:400;font-size:13px;color:#64748B;">'
                    f'{html.escape(e.get("sector") or "")} · {html.escape(e.get("sub") or "")}</span></h3>'
                    f'<div style="margin:0 0 10px;font-size:13px;color:#64748B;">{html.escape(note)}</div>' + RP.sec_industry_tab(x))
    print(dk.write_mock("".join(body), os.path.join(HERE, "output", "mock_industry_tab_us.html"), "미국 종목 업계상황 탭 — 배정 고침 뒤"))


if __name__ == "__main__":
    main()
