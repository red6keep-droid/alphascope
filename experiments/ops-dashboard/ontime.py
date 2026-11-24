"""발행 시간 — 독자에게 알린 발행 시각에 글이 나갔는지, 어긴 횟수를 날마다 쌓아 그린다 (2026-11-24 사용자).

    "독자들한테 공지한 시간(7시 30분)… 약속한 발행 시간에 실패했으면 그 누적 그래프를 계속 그려줘.
     독자들하고의 약속인데 제 시간에 안 나가면 블로그의 신뢰 문제… 발행 시간 페이지를 별도로."

비교 대상(헌법 제1조) = 독자에게 알린 약속 시각. 실제 값 = Blogger 공개 피드의 글 게시 시각(published).
판정 (그날 약속 시각 + 유예 GRACE_MIN 분이 기준):
  - 정시 = 기준 안에 게시
  - 늦음 = 기준 뒤 게시 (몇 분 늦었는지 같이)
  - 안 나감 = 기준이 지났는데 그날 글이 없음 (오늘이면 `아직 안 나감` 으로 이미 어긴 것에 셈)
  - 기다림 = 오늘 · 기준 전 (세지 않음)
어긴 것 = 늦음 + 안 나감. 누적 그래프는 START 부터 날마다 어긴 횟수를 더한다.

기록은 Blogger 피드 자체다 — 글 게시 시각은 바뀌지 않으므로 매시 다시 계산해도 같은 값이 나온다(따로 저장하지 않음).
AI 0 · 시세 API 0 · Blogger 쓰기 0 · gh-pages 쓰기 0. Blogger 공개 피드 읽기 실행당 2~3번(150편씩).

    python experiments/ops-dashboard/ontime.py        → output/ontime.html (로컬 확인 — 피드만 읽는다)
"""
import datetime as dt
import os
import re
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import design_kit as dk  # noqa: E402
import mock_ops as M  # noqa: E402

QC = M.QC
esc, V = dk.esc, dk.violet
ok, warn, idle, over, white_card, chart_top = M.ok, M.warn, M.idle, M.over, M.white_card, M.chart_top

BLOG = "https://www.newfact.app"
KST = dt.timezone(dt.timedelta(hours=9))
UA = {"User-Agent": "alphascope-ops-dashboard"}
START = dt.date(2026, 11, 1)    # 기록 시작 — 종가 안내 상자(아침 7시 30분 · 오후 4시 10분 무렵)를 단 11-14 전부터, 11월 전체
GRACE_MIN = 10                  # 안내 문구가 `무렵` 이라 10분까지 정시로 본다. 0 으로 하면 약속 시각 그대로

US_HOL = set(dk.US_HOLIDAYS)
KR_HOL = set(dk.KR_HOLIDAYS)


def _us_day(d):
    """KST d 아침에 미국 글이 나오는 날 = 그 전날(미국 날짜)이 미국 장날 — KST 화~토, 미국 휴장 다음 날 빼고."""
    p = d - dt.timedelta(days=1)
    return p.weekday() < 5 and p.isoformat() not in US_HOL


def _us_am_day(d):
    """미국 시황 아침 편 — 실제로 나온 날(11-21 토 · 11-23 월)에 맞춰 월~토로 본다. 수집기 편성이 정해지면 이 줄을 고친다."""
    return d.weekday() < 6 and (d - dt.timedelta(days=1 if d.weekday() else 3)).isoformat() not in US_HOL


def _kr_day(d):
    return d.weekday() < 5 and d.isoformat() not in KR_HOL


_TITLE_DATE = re.compile(r"(\d{4})년 (\d{1,2})월 (\d{1,2})일")
_TITLE_MD = re.compile(r"^(\d{1,2})\.(\d{1,2}) ")


def _date_by_title(e, pub):
    """제목의 날짜(`2026년 11월 21일` · `11.21 증시 시황`)가 있으면 그 날, 없으면 게시한 KST 날짜 — 자정 넘어 늦게 나간 글도 제 날에 붙게."""
    m = _TITLE_DATE.search(e["title"])
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    m = _TITLE_MD.match(e["title"])
    if m:
        y = pub.year - (1 if pub.month == 1 and int(m[1]) == 12 else 0)
        return dt.date(y, int(m[1]), int(m[2]))
    return pub.date()


# 약속 — (이름, 약속 시각 KST, 독자에게 알린 곳, 시작일, 그날 나와야 하나, 글 고르기)
PROMISES = [
    ("미국 증시 리포트", "07:30", "종목 · 리포트 안내 상자 `아침 7시 30분 무렵`", START, _us_day,
     lambda e: "데일리 브리핑" in e["labels"]),
    ("한국 증시 리포트", "16:30", "종목 · 리포트 안내 상자 `오후 4시 30분 무렵` (11.23까지 4시 10분)", START, _kr_day,
     lambda e: "한국 증시 리포트" in e["labels"]),
    ("미국 증시시황 (아침 편)", "08:40", "홈 시황 카드 `08:40`", dt.date(2026, 11, 21), _us_am_day,
     lambda e: "증시 시황" in e["labels"] and "미국 증시" in e["labels"]),
    ("한국 증시시황 (저녁 편)", "21:00", "홈 시황 카드 `21:00`", dt.date(2026, 11, 20), _kr_day,
     lambda e: "증시 시황" in e["labels"] and "한국 증시" in e["labels"]),
]

# 약속 시각을 바꾼 이력 — 그 날짜 전은 옛 시각으로 판정 (기록을 고쳐 쓰지 않는다)
AT_BEFORE = {
    "한국 증시 리포트": [(dt.date(2026, 11, 24), "16:10")],   # 2026-11-24 사용자: 실제 게시 16:17~16:29 → 안내 문구를 4시 30분으로
}

# 세지 않는 날 — (이름, 날짜): 까닭. 화면 `날짜별` 에는 `제외` 로 남긴다
EXCLUDE = {
    ("미국 증시 리포트", dt.date(2026, 11, 24)): "코드 오류(Python 3.10 SyntaxError)로 세 번 멈춤 · 09:58 수동 게시 — 사용자 제외",
    ("미국 증시시황 (아침 편)", dt.date(2026, 11, 24)): "같은 오류 — 리포트가 멈춰 아침 해설 재료가 없었음 · 사용자 제외",
}


def at_on(name, at, d):
    for until, old in AT_BEFORE.get(name, []):
        if d < until:
            return old
    return at


def fetch_posts(since):
    """since(KST 날짜) 뒤 공개 글 — [{title, labels, pub(KST)}]."""
    start = dt.datetime.combine(since - dt.timedelta(days=1), dt.time(), KST).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out, idx = [], 1
    for _ in range(40):   # 피드가 한 번에 다 주지 않는다 — start-index 로 넘긴다
        r = requests.get(f"{BLOG}/feeds/posts/summary", params={"alt": "json", "max-results": 150, "published-min": start, "start-index": idx},
                         headers=UA, timeout=30)
        r.raise_for_status()
        es = (r.json().get("feed") or {}).get("entry") or []
        for e in es:
            pub = dt.datetime.fromisoformat(e["published"]["$t"]).astimezone(KST)
            link = next((x["href"] for x in e.get("link") or [] if x.get("rel") == "alternate"), "")
            out.append({"title": e["title"]["$t"], "labels": {c["term"] for c in e.get("category") or []}, "pub": pub, "url": link})
        idx += len(es)
        if not es:
            break
    return out


def judge(posts, now):
    """→ [(약속, [(날짜, 상태, 게시 시각 | None, 늦은 분)])]. 상태 = on · late · miss · wait · skip(EXCLUDE)."""
    today = now.date()
    res = []
    for name, at, where, since, due, pick in PROMISES:
        first = {}
        for p in posts:
            if pick(p):
                d = _date_by_title(p, p["pub"])
                if d not in first or p["pub"] < first[d]["pub"]:
                    first[d] = p
        days, d = [], since
        while d <= today:
            if due(d) and (name, d) in EXCLUDE:
                p = first.get(d)
                days.append((d, "skip", p["pub"] if p else None, 0))
            elif due(d):
                hh, mm = map(int, at_on(name, at, d).split(":"))
                limit = dt.datetime.combine(d, dt.time(hh, mm), KST) + dt.timedelta(minutes=GRACE_MIN)
                promise = limit - dt.timedelta(minutes=GRACE_MIN)
                p = first.get(d)
                if p:
                    late = round((p["pub"] - promise).total_seconds() / 60)
                    days.append((d, "on" if p["pub"] <= limit else "late", p["pub"], late))
                elif now <= limit:
                    days.append((d, "wait", None, 0))
                else:
                    days.append((d, "miss", None, round((now - promise).total_seconds() / 60)))
            d += dt.timedelta(days=1)
        res.append(((name, at, where, since), days))
    return res


def _hm(t):
    return t.astimezone(KST).strftime("%H:%M")


def _md(d):
    return f"{d.month}.{d.day}"


def _late_text(m):
    return f"{m // 60}시간 {m % 60}분" if m >= 60 else f"{m}분"


def _pill(st, late):
    if st == "on":
        return ok("정시")
    if st == "late":
        return warn(f"{_late_text(late)} 늦음")
    if st == "miss":
        return warn("안 나감")
    if st == "skip":
        return idle("제외")
    return idle("기다림")


def summary(res, now):
    """운영 대시보드 요약 칸 · 할 일 — (값HTML, 보조, 오늘 어긴 것 [(이름, 글)])."""
    total = sum(1 for _, ds in res for _, s, _, _ in ds if s in ("on", "late", "miss"))
    bad = sum(1 for _, ds in res for _, s, _, _ in ds if s in ("late", "miss"))
    today = [(p[0], _pill(s, m)) for p, ds in res for d, s, _, m in ds if d == now.date() and s in ("late", "miss")]
    val = warn(f"어김 {bad}번") if bad else ok("모두 정시")
    return val, f"{_md(START)}부터 약속 {total}번 중 정시 {total - bad}번", today


def page_body(res, now):
    tot = sum(1 for _, ds in res for _, s, _, _ in ds if s in ("on", "late", "miss"))
    late = sum(1 for _, ds in res for _, s, _, _ in ds if s == "late")
    miss = sum(1 for _, ds in res for _, s, _, _ in ds if s == "miss")
    lead = (f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">{now.month}월 {now.day}일 {now:%H:%M} 기준, {START.month}월 {START.day}일부터 독자에게 알린 발행 '
            f'{V(f"{tot}번")} 가운데 정시 {V(f"{tot - late - miss}번")}, 늦음 {V(f"{late}번")}, 안 나감 {V(f"{miss}번")}입니다.</p>')
    head = (f'<div style="display:flex;align-items:center;gap:8px;margin:0 0 12px;padding-left:{dk.ALIGN_PX}px;">'
            f'{dk.solid_icon("clock", M.OPS_COLOR)}'
            f'<span style="font-size:{dk.H2_SIZE};line-height:{dk.LH_H2};font-weight:700;color:#111;">약속한 시각에 나갔나?</span></div>')
    rows = []
    for (name, at, where, since), ds in res:
        done = [x for x in ds if x[1] in ("on", "late", "miss")]
        n_on = sum(x[1] == "on" for x in done)
        today = next((x for x in ds if x[0] == now.date()), None)
        if today:
            st = _pill(today[1], today[3])
            got = f" · 오늘 {_hm(today[2])}" if today[2] else ""
        else:
            st, got = idle("오늘 없음"), ""
        lates = [x[3] for x in done if x[1] == "late"]
        avg = f" · 늦은 날 평균 {_late_text(round(sum(lates) / len(lates)))}" if lates else ""
        rows.append((name, st, f"약속 {at}{got} · 정시 {n_on}/{len(done)}{avg}"))
    top = dk.cards(lead + head + white_card(rows))

    # 누적 — 날마다 어긴 횟수(늦음 + 안 나감)를 더한다. 가로축 = START ~ 오늘 모든 날
    days = [START + dt.timedelta(days=i) for i in range((now.date() - START).days + 1)]
    series, cum_all = [], [0] * len(days)
    for k, ((name, *_), ds) in enumerate(res):
        bad_day = {d for d, s, _, _ in ds if s in ("late", "miss")}
        c, xs = 0, []
        for i, d in enumerate(days):
            c += d in bad_day
            xs.append(c)
            cum_all[i] += d in bad_day
        series.append((name, xs))
    for i in range(1, len(cum_all)):
        cum_all[i] += cum_all[i - 1]
    cols = list(dk.CHART_SERIES) + ["#EC4899"]
    cum = chart_top(dk.trend_card("약속을 어긴 횟수 (누적, 번)", [_md(d) for d in days],
                                  [("모두", cum_all, "#111827", "solid")] + [(n, xs, cols[k % len(cols)], "solid") for k, (n, xs) in enumerate(series)],
                                  lambda v: f"{v:.0f}", legend_note=f"늦음 + 안 나감 · 약속 시각 {GRACE_MIN}분 뒤까지 정시"), top=0)

    # 시각 — 약속마다 실제 게시 시각(시) vs 약속 시각 기준선
    def hfmt(v):
        h, m = int(v), round((v - int(v)) * 60)
        if m == 60:
            h, m = h + 1, 0
        return f"{h}:{m:02d}"

    times = ""
    for (name, at, where, since), ds in res:
        got = [(d, t) for d, s, t, _ in ds if t]
        if len(got) < 2:
            continue
        hour = lambda x: int(x[:2]) + int(x[3:]) / 60   # noqa: E731
        vals = [t.hour + t.minute / 60 for _, t in got]
        guide = [hour(at_on(name, at, d)) for d, _ in got]   # 약속을 바꾼 날부터 기준선도 바뀐다
        times += chart_top(dk.trend_card(f"{name} 게시 시각", [_md(d) for d, _ in got],
                                         [("게시", vals, dk.CHART_MAIN, "solid"), (f"약속 {at}", guide, dk.CHART_CMP, "guide")],
                                         hfmt, legend_note="안 나간 날은 점이 없습니다"))

    # 날짜별 — 최신 위, 5개 펼침 + 나머지 접기 (상한으로 버리지 않기)
    lst = []
    for (name, at, *_), ds in res:
        for d, s, t, m in ds:
            lst.append((d, at_on(name, at, d), name, s, t, m))
    lst.sort(key=lambda x: (x[0], x[1]), reverse=True)
    day_rows = [(f"{_md(d)} {name}", _pill(s, m), f"약속 {at} · " + (f"게시 {_hm(t)}" if t else ("아직 기다림" if s == "wait" else "글 없음"))
                 + (f" · {EXCLUDE[(name, d)]}" if s == "skip" else ""))
                for d, at, name, s, t, m in lst]
    where_rows = [(name, f"{at}", where) for (name, at, where, since), _ in res]

    return (top
            + dk.h2("누적", tab="누적") + cum
            + dk.h2("시각", tab="시각") + (times or white_card([("게시 시각", idle("자료 부족"), "약속마다 2번 넘게 나가야 그립니다")]))
            + dk.h2("날짜별", tab="날짜별") + white_card(day_rows, fold_at=5, noun="날")
            + dk.h2("약속", tab="약속")
            + dk.sub_label("독자에게 알린 시각") + white_card(where_rows)
            + dk.guide("판정", f"Blogger 공개 피드의 글 게시 시각을 약속 시각과 견줍니다. 약속 시각 {GRACE_MIN}분 뒤까지는 정시(`무렵`), 그 뒤는 늦음, "
                       "그날 글이 없으면 안 나감입니다. 오늘 아직 약속 시각 전이면 세지 않습니다. 미국 글은 전날 미국 장이 선 날(KST 화~토, 미국 휴장 다음 날 빼고), "
                       "한국 글은 한국 장날만 셉니다. 고정 종목 페이지 갱신은 글이 아니라 아직 세지 않습니다."))


def build(now):
    """→ (페이지 본문 HTML, 요약 (값, 보조, 오늘 어긴 것)) — 피드를 못 읽으면 예외."""
    res = judge(fetch_posts(START), now)
    return page_body(res, now), summary(res, now)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import build_ops as B
    now = dt.datetime.now(KST)
    body, (val, sub, today) = build(now)
    page = B.shell(dk.align_titles(dk.WRAP_OPEN + body + dk.WRAP_CLOSE), now, title="발행 시간")
    os.makedirs(B.OUT, exist_ok=True)
    with open(os.path.join(B.OUT, "ontime.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print(f"[ontime] output/ontime.html {len(page) // 1024}KB · {sub} · 오늘 어김 {today}")
