"""인물 페이지 과거 참고치 시안 — ref/reaction_refs.json(트럼프 × 관세 · 연준 × FOMC)을 인물 요약 카드 자리에 그린다.
인터넷 · AI 0. 글은 블로그에 나가지 않는다.

    .venv/bin/python experiments/people-radar/mock_people_refs.py   → output/mock_people_refs.html (목업 서버 `주요 인물 발언` 묶음)

시안 A = 따로 된 질문 카드 `○○ 날, 시장은 평소보다 움직였나?` (트럼프 · 파월 둘 다)
시안 B = 파월 `다음 일정은?` 카드 안 한 줄(일정이 있는 인물만 — 트럼프는 자리가 없다)
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE)]
import config  # noqa: E402
import design_kit as dk  # noqa: E402
import render_html as R  # noqa: E402

spec = importlib.util.spec_from_file_location("dr_cards", os.path.join(config.BASE_DIR, "..", "daily-report", "cards.py"))
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)

refs = json.load(open(R.REFS_PATH, encoding="utf-8"))
NOTE = "움직임 = 하루 등락 폭(오르든 내리든)의 가운데 값입니다. 방향을 알려 주는 숫자가 아닙니다"


def bigger(a, b):
    return b and a / b >= R.REF_DIFF


def comma(n):
    return f"{n:,}"


def ref_card(q, v, extra_note=""):
    """그런 날 vs 이름 있는 대조군(같은 기간 그런 일이 없던 날) · 있으면 비슷한 큰 일정 날."""
    more = bigger(v["med_abs"], v["base_abs"])
    alt = v.get("alt")
    first = f"기록상 {v['label']}에 S&P 500은 하루 보통 {v['med_abs']}% 움직였습니다. "
    if alt:
        same = not bigger(v["med_abs"], alt["med_abs"])
        first += (f"{v['base_label']}({v['base_abs']}%)보다 " + ("컸고" if more else "차이가 없었고")
                  + f", {alt['label']}({alt['med_abs']:.2f}%)" + ("과는 비슷했습니다. 큰 발표가 있는 날이면 대체로 이만큼 움직였습니다." if same else "보다도 컸습니다."))
        ans = "큰 발표일 수준" if same and more else "평소보다 큼" if more else "평소와 비슷"
    else:
        first += f"{v['base_label']}({v['base_abs']}%)" + ("보다 컸습니다." if more else "과 차이가 없었습니다.")
        ans = "평소보다 큼" if more else "평소와 비슷"
    lines = [(first, "plain"), ("row", v["label"].replace("이 있던 날", " 날"), f"{v['med_abs']}%", f"{v['period']} {comma(v['n'])}일")]
    if alt:
        lines.append(("row", alt["label"], f"{alt['med_abs']:.2f}%", f"{comma(alt['n'])}일"))
    lines += [("row", v["base_label"], f"{v['base_abs']}%", f"{comma(v['base_n'])}일"),
              ("row", "오른 날 비율", f"{v['up_pct']}%", f"{v['base_label']} {v['base_up']}%"),
              (NOTE, "note")]
    if extra_note:
        lines.append((extra_note, "note"))
    return C.question_card(q, ans, "neutral", "#111", lines)


def next_card(day, kind, left, ref_line=None):
    lines = [(f"{day} {dk.josa(kind, '이')} 있습니다. 오늘부터 {left}일 남았습니다.", "plain"), ("row", kind, day, "")]
    if ref_line:
        lines.append((ref_line, "note"))
    return C.question_card("다음 일정은?", f"D-{left}", "neutral", "#111", lines)


def tag(t, sub):
    return (f'<div style="margin:28px 0 8px;padding:8px 12px;background:#FEF3C7;border-radius:8px;font-size:15px;line-height:22px;color:#92400E;">'
            f'<b>{dk.esc(t)}</b> · {dk.esc(sub)}</div>')


def main():
    fed, tr = refs["fed"]["Fed"], refs["trump"]["Trade"]
    body = [tag("지금", "파월 인물 페이지 맨 위 — 다음 일정 카드만(과거 참고치 0)"), next_card("12월 9일", "FOMC", 11)]
    body += [tag("시안 A", "따로 된 카드 — 파월 · 트럼프 둘 다"),
             next_card("12월 9일", "FOMC", 11),
             ref_card("FOMC 결정일, 시장은 평소보다 움직였나?", fed),
             '<div style="height:16px"></div>',
             ref_card("관세 발언 날, 시장은 평소보다 움직였나?", tr,
                      "트럼프 1기(2017 ~ 2020년) 트윗 기록입니다. 지금 발언과 다를 수 있습니다")]
    body += [tag("시안 B", "다음 일정 카드 안 한 줄 — 일정이 있는 파월만, 트럼프는 자리 없음"),
             next_card("12월 9일", "FOMC", 11,
                       f"기록상 FOMC 결정일에 S&P 500은 하루 {fed['med_abs']}% 움직였습니다. FOMC가 없던 날 {fed['base_abs']}% · CPI · 고용 보고서 발표일 {fed['alt']['med_abs']:.2f}% · 방향이 아니라 움직임 폭입니다")]
    out = os.path.join(HERE, "output", "mock_people_refs.html")
    dk.write_mock("".join(body), out, "주요 인물 발언 — 과거 참고치 시안")
    print(out)


if __name__ == "__main__":
    main()
