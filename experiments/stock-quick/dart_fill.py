"""간단 종목(한국) DART 받기만 — 새벽 실행 quick-dart.yml.

장 마감 뒤 화면 실행(quick-data kr)에서 DART 매출 · 손익 · 기업개황 받기(매일 21~30분)를 빼고 여기로 옮겼다.
화면 실행은 QUICK_DART_FETCH=0 으로 저장값만 읽는다. 같은 저장값 폴더(quick-state)를 읽고 쓴다 — 워크플로가 받아 오고 다시 올린다.
새벽이라 서두를 일이 없어 시간 상한 · 하루 회사 수를 늘린다(QUICK_DART_MINUTES · QUICK_DART_BUDGET, 워크플로에서). 같은 함수(full_kr.dart)라 받는 방식은 그대로.

    python experiments/stock-quick/dart_fill.py --cache /tmp/qcache
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True, help="저장값 폴더(quick-state)")
    a = ap.parse_args()
    os.environ["QUICK_DART_FETCH"] = "1"
    import full_kr as FK
    ref = json.load(open(os.path.join(EXP, "ref", "quick_ref.json"), encoding="utf-8"))
    syms = sorted(s for s, e in ref["kr"].items() if not e.get("full"))   # 정식 종목은 정식 한국 실행이 받는다 (collect_quick 의 q_kr 와 같은 명단)
    os.makedirs(os.path.join(a.cache, "kr"), exist_ok=True)
    t0 = time.time()
    print(f"[dart-fill] 간단 한국 {len(syms)}종목 · 하루 {FK.BUDGET['dart']}곳 · 상한 {FK.DART_MINUTES}분", flush=True)
    FK.dart(a.cache, syms)
    print(f"[dart-fill] 끝 {(time.time() - t0) / 60:.1f}분", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
