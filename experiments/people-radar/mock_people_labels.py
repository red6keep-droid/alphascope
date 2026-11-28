"""인물 발언 줄 라벨 시안 — 방향 말(`긍정 · 부정` → 요약 카드와 같은 `상승 의견 · 하락 의견`) · `강도 n` 처리.
상태 저장소의 마지막 레이더(radar.json)를 실제 렌더러로 그린다. 인터넷 · AI 0. 글은 블로그에 나가지 않는다.

    git fetch state radar-state
    .venv/bin/python experiments/people-radar/mock_people_labels.py   → output/mock_people_labels.html (목업 서버 발행 예정 칸)

지금 = `긍정` 알약 · `강도 7`
시안 A = 요약 카드와 같은 상자 `▲ 상승 의견` · `▼ 하락 의견` · `— 중립`, 강도 뺌
시안 B = 알약 모양 그대로 글자만 `상승 의견` · `하락 의견`, 강도 뺌
시안 C = 시안 A + 강도 8 이상만 `강한 말` 회색 알약
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE)]
import design_kit as dk  # noqa: E402
import people_section as PS  # noqa: E402
import render_html as R  # noqa: E402
from mock_person_cards import _show  # noqa: E402

PEOPLE = ("trump", "wood", "ackman")   # 상승 · 하락 · 중립 · 강도 높은 발언이 다 나오는 인물
ROWS = 5     # 인물마다 발언 다섯까지
WORD = {"positive": ("up", "상승 의견"), "negative": ("down", "하락 의견"), "neutral": ("flat", "중립")}
_pill, _dir = dk.pill, R._dir_pill


def variant(kind):
    def pill(text, k="area", lead=False, bare=False):
        if text.startswith("강도 "):
            n = int(text.split()[1])
            return _pill("강한 말", "area", bare=bare) if kind == "C" and n >= 8 else ""
        return _pill(text, k, lead, bare)

    def dir_pill(d):
        b, w = WORD.get(d, WORD["neutral"])
        if kind == "B":
            return _pill(w, d if d in ("positive", "negative") else "neutral", bare=True)
        return PS._box(b, w)
    if kind == "now":
        dk.pill, R._dir_pill = _pill, _dir
    else:
        dk.pill, R._dir_pill = pill, dir_pill


def tag(t, sub):
    return (f'<div style="margin:28px 0 8px;padding:8px 12px;background:#FEF3C7;border-radius:8px;font-size:15px;line-height:22px;color:#92400E;">'
            f'<b>{dk.esc(t)}</b> · {dk.esc(sub)}</div>')


def main():
    radar = json.loads(_show("radar.json"))
    cards = (json.loads(_show("narrative.json") or "null") or {}).get("cards")
    radar["people"] = [dict(p, signals=p["signals"][:ROWS]) for sp in PEOPLE for p in radar["people"] if p["speaker"] == sp]
    body = []
    for kind, t, sub in (("now", "지금", "`긍정 · 부정` 알약 + `강도 n` — 요약 카드는 `▲ 상승 의견 · ▼ 하락 의견`"),
                         ("A", "시안 A (추천)", "요약 카드와 같은 상자 `▲ 상승 의견` · `▼ 하락 의견` · `— 중립`, 강도 뺌"),
                         ("B", "시안 B", "알약 모양 그대로 글자만 `상승 의견` · `하락 의견`, 강도 뺌"),
                         ("C", "시안 C", "시안 A + 강도 8 이상만 `강한 말`")):
        variant(kind)
        body += [tag(t, sub), R.sec_people(radar, cards).replace(" hidden", "")]
    variant("now")
    out = os.path.join(HERE, "output", "mock_people_labels.html")
    dk.write_mock(dk.WRAP_OPEN + "".join(body) + dk.WRAP_CLOSE, out, "주요 인물 발언 — 발언 줄 라벨 시안")
    print(out)


if __name__ == "__main__":
    main()
