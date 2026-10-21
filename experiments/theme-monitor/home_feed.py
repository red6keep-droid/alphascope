"""홈 `테마` 카드 데이터 → output/home/themes.json (2026-10-21 사용자: "홈에 카드를 만들어 각각의 페이지로 진입할 수 있게").

    python experiments/theme-monitor/home_feed.py     # output/themes_analysis.json → output/home/themes.json

테마마다 한 줄: 이름 · 상태 · 핵심 숫자 한 마디 · 페이지 주소. 홈 JS(alphaflow-home.html `테마` 카드)가 jsDelivr 로 읽는다.
워크플로가 stocks.json 과 같은 deploy-home 폴더로 gh-pages 에 올린다.
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import themes as T  # noqa: E402

SRC = os.path.join(_HERE, "output", "themes_analysis.json")
OUT = os.path.join(_HERE, "output", "home", "themes.json")


def _pp(v, digits=1, unit="%p"):
    return "" if v is None else f"{v:+.{digits}f}{unit}".replace("-", "−")


def summary(key, a):
    """카드 둘째 줄 — 핵심 숫자 한 마디 (증감 기호 포함 — 홈 JS 가 색을 칠한다)."""
    if key == "ai":
        return f"20일 S&P 500 대비 {_pp(a['whole'].get('rel_20d'))}"
    if key == "fed":
        if a.get("state") == "자료 없음":
            return "자료 없음"
        return f"기준금리 − 2년물 {_pp(a['gap_bp'], 0, 'bp')} · 20일 변화 {_pp(a['gap_change_bp'], 0, 'bp')}"
    if key == "insider":
        return f"{a['days']}일 계획 외 매수 {a['buy_n']}건 · 매도 {a['sell_n']}건"
    return ""


def build(analysis):
    rows = []
    for t in T.THEMES:
        a = analysis["themes"].get(t["key"])
        if not a:
            continue
        rows.append({"key": t["key"], "title": t["title"], "question": t["question"], "state": a.get("state"),
                     "kind": a.get("theme_kind", "neutral"), "sub": summary(t["key"], a), "url": T.page_url(t)})
    return {"day": analysis["day"], "themes": rows}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    with open(SRC, encoding="utf-8") as f:
        data = build(json.load(f))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"[theme-home] {len(data['themes'])}개 → {OUT}")
