"""인물 발언 건수 비교 대상 시안 — 글 맨 앞 줄 `최근 24시간 시장 발언 n건 · n명` · 인물 줄 `오늘 n건` 에 지난 30일 하루 평균을 붙인다.
상태 저장소의 마지막 레이더(radar.json, strips = 인물별 하루 건수 60일)를 실제 렌더러로 그린다. 인터넷 · AI 0. 글은 블로그에 나가지 않는다.

    git fetch state radar-state
    .venv/bin/python experiments/people-radar/mock_people_counts.py   → output/mock_people_counts.html (목업 서버 발행 예정 칸)

지금 = 건수만
시안 A = 숫자로 나란히 `· 지난 30일 하루 평균 33건 · 9명` / 인물 줄 `오늘 6건 · 30일 평균 6건`
시안 B = 말로 `· 평소보다 적음(지난 30일 하루 평균 33건)` / 인물 줄 `오늘 6건 · 평소 수준`
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE)]
import design_kit as dk  # noqa: E402
import render_html as R  # noqa: E402
from mock_person_cards import _show  # noqa: E402

DAYS = range(1, 31)   # 어제부터 30일 — 오늘(0)은 뺀다
MORE, LESS = 1.5, 0.67   # 평균의 1.5배 이상 = 많음, 0.67배 이하 = 적음, 그 사이 = 평소 수준


def usual(r):
    st = r["strips"]
    tot = [sum(st[sp][d]["n"] for sp in st) for d in DAYS]
    ppl = [sum(1 for sp in st if st[sp][d]["n"]) for d in DAYS]
    have = [i for i, t in enumerate(tot) if t]   # 수집이 빈 날은 뺀다
    avg = lambda xs: sum(xs[i] for i in have) / len(have)  # noqa: E731
    per = {sp: sum(st[sp][d]["n"] for d in DAYS) / len(have) for sp in st}
    return round(avg(tot)), round(avg(ppl)), per, len(have)


def word(now, base):
    return "평소보다 많음" if base and now >= base * MORE else "평소보다 적음" if base and now <= base * LESS else "평소 수준"


def tag(t, sub):
    return (f'<div style="margin:28px 0 8px;padding:8px 12px;background:#FEF3C7;border-radius:8px;font-size:15px;line-height:22px;color:#92400E;">'
            f'<b>{dk.esc(t)}</b> · {dk.esc(sub)}</div>')


def main():
    r = json.loads(_show("radar.json"))
    cards = (json.loads(_show("narrative.json") or "null") or {}).get("cards")
    d = r["generated_at"][:10]
    tot, ppl, per, nd = usual(r)
    lead, lst = R.sec_seo_lead(r, d, cards), R.sec_people_list(r, cards)
    line = f"시장 발언 {r['event_count']}건 · {r['people_count']}명"

    def rows(fn):
        return re.sub(r'data-person="([\w-]+)"(.*?)오늘 (\d+)건', lambda m: f'data-person="{m.group(1)}"{m.group(2)}{fn(m.group(1), int(m.group(3)))}', lst, flags=re.S)
    a_lead = lead.replace(line, f"{line} · 지난 {nd}일 하루 평균 {tot}건 · {ppl}명")
    b_lead = lead.replace(line, f"{line} · {word(r['event_count'], tot)}(지난 {nd}일 하루 평균 {tot}건)")
    body = [tag("지금", "건수만 — 평소와 견주지 않음"), lead, lst,
            tag("시안 A (추천)", f"숫자로 나란히 — 글 맨 앞 줄 · 인물 줄 모두 지난 {nd}일 하루 평균"), a_lead,
            rows(lambda sp, n: f"오늘 {n}건 · {nd}일 평균 {per.get(sp, 0):.0f}건" if per.get(sp, 0) >= 1 else f"오늘 {n}건 · {nd}일 평균 1건 미만"),
            tag("시안 B", f"말로 — 평균의 1.5배 이상 `평소보다 많음`, 0.67배 이하 `평소보다 적음`"), b_lead,
            rows(lambda sp, n: f"오늘 {n}건 · {word(n, per.get(sp, 0))}")]
    out = os.path.join(HERE, "output", "mock_people_counts.html")
    dk.write_mock(dk.WRAP_OPEN + "".join(body) + dk.WRAP_CLOSE, out, "주요 인물 발언 — 건수 비교 시안")
    print(out, tot, ppl, nd)


if __name__ == "__main__":
    main()
