"""저녁 시황 묶음(briefing/{오늘}-pm.json)의 업종 줄을 종목 모아보기 목록 파일로 다시 — 간단 종목 실행(한국)이 목록을 만든 직후.

한국 종목 실행(15:50)이 묶음을 만들 때는 그날 목록 파일(kr/_lists.json, 간단 종목 실행 약 16:20)이 아직 없어 업종 줄이 옛 셈(대형주 1~3개 평균)이다.
수집기가 저녁 편 1차를 16:40 에 쓰므로 그 전에 목록 기준 숫자(업종 탭과 같은 셈)로 바꿔 올린다 — 수집기가 본문에 업종 숫자를 써도 표 · 업종 탭과 같게.
업종 줄만 바꾸고 나머지는 그대로. 이미 목록 기준이거나, 묶음 · 목록 날짜가 다르면 아무것도 쓰지 않는다(종료 0). AI 0 · 수집 0.

    python experiments/market-commentary/refresh_briefing_sectors.py --lists /tmp/qd/kr/_lists.json --out-dir deploy-brief
    → deploy-brief/briefing/{날짜}-pm.json (바꿨을 때만) — 워크플로가 gh-pages 에 올린다
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_briefing as BB  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lists", required=True, help="방금 만든 한국 목록 파일")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--date", help="KST 날짜 (기본 오늘)")
    a = ap.parse_args()
    day = a.date or datetime.datetime.now(BB.KST).date().isoformat()
    try:
        doc = json.load(open(a.lists, encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"[묶음 업종] 목록 파일 없음 — 그대로: {e}")
        return 0
    br = BB._get_json(f"{BB.RAW}/briefing/{day}-pm.json")
    if not br:
        print(f"[묶음 업종] {day}-pm 묶음 없음 — 그대로")
        return 0
    close = br.get("close") or {}
    if close.get("sectors_basis") == "lists":
        print(f"[묶음 업종] {day}-pm 이미 목록 기준 — 그대로")
        return 0
    secs = BB.sectors_from_lists(doc, br.get("trade_date"))
    if not secs:
        print(f"[묶음 업종] 목록 날짜 {doc.get('d')} ≠ 묶음 장 날짜 {br.get('trade_date')} — 그대로")
        return 0
    close["sectors"], close["sectors_basis"] = secs, "lists"
    br["close"] = close
    br["sectors_at"] = datetime.datetime.now(BB.KST).isoformat(timespec="seconds")   # 업종 줄을 바꾼 시각(생성 시각 generated 는 그대로)
    path = os.path.join(a.out_dir, "briefing", f"{day}-pm.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(br, ensure_ascii=False, separators=(",", ":")))
    print(f"[묶음 업종] {day}-pm 업종 {len(secs)}개 → 종목 모아보기 목록 기준 · {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
