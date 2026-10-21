"""테마 모니터 — 레이더 자료로 신호 계산 → 테마 페이지 HTML · 목업 (doc/테마-모니터-기획.md, 1단계 2026-10-21).

    python experiments/theme-monitor/main.py          # data/*.json(레이더 수집 결과) + FRED → output/<slug>.html · mock_<slug>.html · themes_analysis.json
엔비디아 워크플로의 레이더 단계 뒤에서 돈다 (같은 snapshot · extra). 게시는 3단계(publish).
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "stock-radar"))

import theme_analyze as analyze  # noqa: E402
import theme_render as render  # noqa: E402
import collect  # noqa: E402
import collect_extra  # noqa: E402

OUT = os.path.join(_HERE, "output")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_HERE, "..", "..", ".env"))
    a = analyze.run(collect.load(), collect_extra.load() or {})
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "themes_analysis.json"), "w", encoding="utf-8") as f:
        json.dump(a, f, ensure_ascii=False, indent=1, default=str)
    pages = render.write_all(a, OUT)
    for k, v in a["themes"].items():
        print(f"[theme] {k}: {v.get('state')}")
    print(f"[theme] {a['day']} · 페이지 {len(pages)}개 → {OUT}")
