"""시황 글 장 분위기 색 시안.

    python experiments/market-commentary/mock_story_theme.py

- 재료 = mock_story.py 의 목업 글 둘(한국 저녁 편 = 코스피 +1.99% 상승, 미국 아침 편 = S&P 500 하락) + 보합 = 한국 글 지수만 +0.1% 로 바꾼 것.
- 시안 A = 업종과 주요 종목까지 분위기 색(아이콘 · 제목 · 정리 카드) / 시안 B = 업종과 주요 종목은 지금 녹색 그대로.
- 그리기 = story_render.render(theme="flow" | "body"). 출력 output/mock_story_theme_{up|down|flat}_{a|b}.html (커밋 안 함). AI 0 · 네트워크 0.
"""
import copy
import json
import os
import shutil
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, ".."))
sys.path.insert(0, BASE)
import design_kit as dk  # noqa: E402
import mock_story as MS  # noqa: E402
from story_render import render, titles  # noqa: E402


def lists_for(slot):
    lf = os.path.join(BASE, "..", "stock-lists", "output", "lists", "kr" if slot == "pm" else "us", "_lists.json")
    return {str(r.get("t") or "").upper(): r for r in json.load(open(lf, encoding="utf-8"))["rows"]} if os.path.exists(lf) else {}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    shutil.copytree(os.path.join(BASE, "static", "mood"), os.path.join(BASE, "output", "story-mock", "mood"), dirs_exist_ok=True)
    flat_br = copy.deepcopy(MS.BRIEFING)
    flat_br["trade_date"] = "2026-11-16"
    for x, v in zip(flat_br["close"]["indices"], (0.12, -0.08)):
        x["chg_pct"] = v
    flat_col = dict(MS.SAMPLE, date="2026-11-16", title="반도체 강세에도 차익 매물, 코스피 보합 마감")
    cases = {"up": (MS.SAMPLE, MS.BRIEFING), "down": (MS.SAMPLE_US, MS.BRIEFING_US), "flat": (flat_col, flat_br)}
    names = {"up": "상승", "down": "하락", "flat": "보합"}
    for mood, (col, br) in cases.items():
        banner = MS.banner_for(col, dict(br, date=col["date"], slot=col["slot"]))
        for tag, theme, desc in (("a", "flow", "업종과 주요 종목까지"), ("b", "body", "업종과 주요 종목 제외")):
            _, h, _m = render(col, br, lists=lists_for(col["slot"]), mood_base="story-mock/mood/", banner_url=banner, banner_alt="AI 생성 이미지", theme=theme)
            out = os.path.join(BASE, "output", f"mock_story_theme_{mood}_{tag}.html")
            print(dk.write_mock(h, out, f"[{names[mood]} · 시안 {tag.upper()} {desc}] " + titles(col)[0]) or "index.html 없음")
