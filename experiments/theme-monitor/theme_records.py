"""테마 상태 기록 — 테마 페이지가 그날 계산한 상태를 테마마다 하루 한 줄씩 쌓는다 (2026-11-24 사용자, 헌법 제4조 · 기록 대장 빈 칸 2).

    python experiments/theme-monitor/theme_records.py --state "$STATE_DIR"     # nvda-report.yml 테마 단계, main.py 다음

- 재료: output/themes_analysis.json(main.py 가 만든 것 그대로) — 테마마다 그날 상태 · 시장 대비 · 20일선 위 종목 수 · 바구니별 **구성 종목**과 종목 등락.
- 왜: 테마 페이지는 매일 다시 그려지고 페이지 해시만 남았다. 가격 계산은 나중에 다시 할 수 있어도 **그날 어떤 종목이 그 테마였나 · 그날 우리가 매긴 상태**는
  구성을 바꾸면 사라진다(헌법 제4조 4 · 6항).
- 쓰는 곳: --state/records/themes/{연}.jsonl — 한 줄 = {"date", "theme", "id": "theme/{key}", "source": "themes", ...그 테마 분석 그대로}.
  같은 (date, theme) 는 바꾼다(같은 날 다시 돈 실행 = 그날 마지막 판). 다른 날 줄은 건드리지 않는다. 아래 Save state 가 nvda-state 에 커밋.
- 크기: 하루 약 11KB(테마 3개, 11-24 실측 파일) → 1년 약 3MB. AI 0 · 수집 0. 실패해도 테마 페이지는 그대로.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "output", "themes_analysis.json")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--src", default=SRC)
    a = ap.parse_args()
    if not os.path.exists(a.src):
        print("[theme-records] themes_analysis.json 없음 — 건너뜀")
        return
    with open(a.src, encoding="utf-8") as f:
        an = json.load(f)
    day = str(an.get("day") or "")[:10]
    themes = an.get("themes") or {}
    if not day or not themes:
        print("[theme-records] 날짜 · 테마 없음 — 건너뜀")
        return
    d = os.path.join(a.state, "records", "themes")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{day[:4]}.jsonl")
    keep = []
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                if not (r.get("date") == day and r.get("theme") in themes):
                    keep.append(line.rstrip("\n"))
    new = [json.dumps({"date": day, "theme": k, "id": f"theme/{k}", "source": "themes", **v}, ensure_ascii=False, default=str) for k, v in themes.items()]
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(keep + new) + "\n")
    print(f"[theme-records] {day} 테마 {len(new)}개 기록 · {p} {os.path.getsize(p) / 1e3:.0f}KB · 모두 {len(keep) + len(new)}줄")


if __name__ == "__main__":
    main()
