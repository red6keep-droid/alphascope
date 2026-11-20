"""한국 정식 종목 보고서 `매출 및 수주상황` 읽기(dart_biz, Gemini lite 하루 30건) — 게시 뒤 단계 (2026-11-20 사용자 "①~⑥ 전부 적용").

옛: 수집 단계(main_kr.py) 안에서 돌아 게시 전 시간을 썼다 — 11-19 · 11-20 은 21~22건에 Gemini 503 재시도까지 겹쳐 수집이 30분을 넘었고
11-20 은 본 잡이 시간 제한에 끊겼다. 이제 kr-stocks.yml 이 게시 · kr.json 배포 뒤, 상태 저장 앞에 부른다.
결과는 data/ 캐시(kr-state 에 저장)에 쌓이고 다음 실행 화면부터 쓰인다 — 분기 보고서라 하루 늦어도 같다. 실패하면 지난 캐시.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import collect_kr
    import collect_kr_dart
    import collect_kr_fin
    import dart_biz
    codes = [c[0].split(".")[0] for c in collect_kr.U.CANDIDATES]
    cmap = collect_kr_dart.corp_codes(collect_kr_dart._key())
    dart_biz.run(codes, cmap, collect_kr_dart._load(collect_kr_fin.CACHE))
