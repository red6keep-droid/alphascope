"""한국 종목 — 수집 → 분석 → 목록 · 상세 HTML (기획 11절).
    python experiments/kr-stocks/main_kr.py            # 받고 그리기 (yfinance · ECOS)
    python experiments/kr-stocks/main_kr.py --cached   # 받은 것(data/*.json)으로 그리기만
결과 output/<종목코드>.html (본문) · output/mock_<종목코드>.html (블로그 테마를 입힌 미리보기) · output/images/ (가격 그래프).
"""
import os
import sys

import analyze_kr
import collect_kr
import render_kr

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cached = "--cached" in sys.argv
    snap, flows, hist = collect_kr.load() if cached else collect_kr.run()
    if snap is None:
        print("[kr] 시세 없음 — 이 실행은 자료 지연 (페이지를 만들지 않는다)")
        sys.exit(0)
    a = analyze_kr.run(snap, flows, hist)
    pages = render_kr.write_all(a, OUT, snap)
    # 오늘(KST) 봉이 있나 — 휴장일 · 데이터 지연이면 0. 워크플로는 1일 때만 게시한다 (수동 실행은 강제 가능)
    import datetime
    from zoneinfo import ZoneInfo
    fresh = a["day"] == datetime.datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")
    with open(os.path.join(OUT, "fresh.txt"), "w", encoding="utf-8") as f:
        f.write("1" if fresh else "0")
    print(f"[kr] {a['day']} · 페이지 {len(pages)}개 → {OUT}" + ("" if fresh else " · 오늘 봉 없음(휴장일 또는 지연) — 게시 건너뜀 표시"))
