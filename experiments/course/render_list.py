"""주식 공부 목록 페이지(/p/study.html) — 과정별 편 목록 (2026-11-15 사용자: 목록 페이지도 목업에).

    .venv/bin/python experiments/course/render_list.py              # output/mock_study_list.html
    .venv/bin/python experiments/course/render_list.py --publish    # Blogger 고정 페이지 /p/study.html 만들기 · 고치기 (바뀐 것만, 2026-11-15 사용자)

- 커리큘럼 문서 4절: 맨 위 캐릭터 그림(banner/study_head.webp, 사용자 그림) + 한 줄 소개 → 과정 카드 → 편 목록. 나온 편 = 줄 전체 링크, 안 나온 편 = 회색 `준비 중`.
- 나온 편 주소 = published.json (publish_course.py 가 발행 때 씀). 편 목록 = 아래 COURSES (커리큘럼 문서 2절). 편이 나올 때만 갱신.
- 번호 칸은 글 본문 번호 목록과 같은 규칙(기준선에서 시작 · 32px).
"""
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_course as RC  # noqa: E402

dk = RC.dk
OUT = os.path.join(HERE, "output", "mock_study_list.html")
INTRO = "주식에서 흔히 듣는 말, 데이터로 확인해 봤습니다"

# (과정 이름, 한 줄 소개, [(번호, 편 제목, 초안 파일 이름 또는 None)])
COURSES = [
    ("초보가 흔히 하는 착각", "많이 듣는 말을 하나씩 꺼내, 아무 날에 산 사람과 비교해 확인합니다.", [
        ("0", "들어가며", "착각-00-들어가며.md"),
        ("", "이 연재는 이렇게 확인합니다", "착각-기준.md"),   # 기준 페이지(편 번호 없음 · 편 수에 안 셈, 2026-11-21)
        ("1", "실적이 좋다는데 왜 주가는 떨어질까?", "착각-01-실적.md"),
        ("2", "고점에 물리면 얼마나 오래 가나?", "착각-02-물림.md"),
        ("3", "크게 빠진 날 팔면, 언제 특히 비쌌나?", "착각-03-공포매도.md"),
        ("4", "판 값에 다시 사려다 더 비싸게 사는 이유", "착각-04-되사기.md"),   # 블로그 목록은 published.json 에 주소가 생길 때만 링크
        ("5", "분할 매수, 하단을 기다리면 더 싸게 모일까?", "착각-05-분할매수.md"),
        ("6", "과열이면 떨어진다고요?", "착각-06-과열.md"),
        ("7", "볼린저 하단에서 샀는데 왜 더 떨어질까?", "착각-07-볼린저.md"),
        ("8", "골든크로스는 2010년대엔 틀리고 2020년대엔 맞았다?", "착각-08-골든크로스.md"),
        ("9", "동전 던지기에도 파동은 생긴다", "착각-09-파동.md"),
        ("10", "마치며, 지표는 방향이 아니라 크기를 잰다", "착각-10-마치며.md"),
    ]),
    ("숫자 읽는 법", "Newfact 페이지에 나오는 숫자를 어떻게 읽는지 알려 드립니다.", [
        ("1", "평소 하루에 얼마나 움직이나", None),
        ("2", "볼린저 밴드 읽는 법", None),
        ("3", "공시(8-K)는 무엇을 보면 되나", None),
        ("4", "증시 전망은 어떻게 맞았다고 하나", None),
    ]),
    ("책 속 주장, 데이터로 확인하기", "주식책에 나오는 주장 하나를 골라 실제 주가로 확인합니다.", [
        ("1", "『차트 패턴』 쌍바닥 뒤에 사면 정말 오를까?", None),
        ("2", "『급등의 법칙』 거래량이 몰리면 오를까?", None),
        ("3", "『잘 잃어야 잘 번다』 손절하면 덜 잃을까?", None),
        ("4", "『파동 눌림목 매매법』 눌림에서 사면 나을까?", None),
        ("5", "『시장의 사이클과 바닥에서 매수하는 방법』 바닥 신호는 맞을까?", None),
        ("6", "『추세추종 절대수익』 52주 신고가에 사면 나을까?", None),
    ]),
]
CHEV = ('<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"><path d="M6 3.5 10.5 8 6 12.5"/></svg>')


def course_card(k, name, intro, eps, urls):
    done = sum(1 for n, _, f in eps if n and f and urls.get(f))
    total = sum(1 for n, _, _ in eps if n)
    rows = []
    for n, t, f in eps:
        url = urls.get(f) if f else None
        num = f'<span style="flex:none;width:32px;font-size:15px;line-height:24px;color:{"#0F766E" if url else "#9CA3AF"};font-weight:700;">{n}</span>'
        if url:
            rows.append(f'<a href="{html.escape(url)}" data-row-link="1" style="display:flex;align-items:center;gap:0;padding:12px {dk.ALIGN_PX}px;border-top:1px solid #E2E8F0;text-decoration:none;color:inherit;">'
                        f'{num}<span style="flex:1 1 auto;min-width:0;font-size:17px;line-height:26px;font-weight:700;color:#111;word-break:keep-all;">{html.escape(t)}</span>'
                        f'<span style="flex:none;margin-left:8px;color:#6B7280;">{CHEV}</span></a>')
        else:
            rows.append(f'<div style="display:flex;align-items:center;padding:12px {dk.ALIGN_PX}px;border-top:1px solid #E2E8F0;">'
                        f'{num}<span style="flex:1 1 auto;min-width:0;font-size:17px;line-height:26px;color:#9CA3AF;word-break:keep-all;">{html.escape(t)}</span>'
                        '<span style="flex:none;margin-left:8px;font-size:13px;line-height:18px;font-weight:700;color:#9CA3AF;white-space:nowrap;">준비 중</span></div>')
    state = f"{total}편 중 {done}편" if done else f"{total}편 준비 중"
    # 접기 (2026-11-15 사용자): 과정 이름 줄 오른쪽 접기 버튼 · 0편(들어가며)부터 편 목록 전체가 접힌다. details 라 JS 없이 접히고 접힌 글도 검색엔진이 읽는다.
    # 처음 상태 = 나온 편이 있는 과정만 펼침(지금 1과정), 준비 중뿐인 과정은 접힘. 카드 머리(과정 · 제목 · 소개) 전체가 누르는 자리
    btn = ('<span class="study-fold" aria-hidden="true" style="flex:none;display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;'
           'border:1px solid #E2E8F0;border-radius:6px;background:#fff;color:#111;box-sizing:border-box;">'
           '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
           '<path d="M4 6l4 4 4-4"/></svg></span>')
    return (f'<details data-course="{k + 1}"{" open" if done else ""} style="margin:0 0 20px;background:#fff;border:1px solid #E2E8F0;border-radius:12px;overflow:hidden;">'
            f'<summary style="display:block;list-style:none;cursor:pointer;padding:16px {dk.ALIGN_PX + 10}px 14px;">'
            f'<span style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 0 4px;">'
            f'<span style="font-size:14px;line-height:20px;font-weight:700;color:#0F766E;">{k + 1}과정</span>'
            f'<span style="display:flex;align-items:center;gap:8px;"><span style="font-size:13px;line-height:18px;color:{dk.NOTE};">{state}</span>{btn}</span></span>'
            f'<span style="display:block;margin:0 0 6px;font-size:21px;line-height:30px;font-weight:800;color:#111;word-break:keep-all;">{html.escape(name)}</span>'
            f'<span style="display:block;font-size:15px;line-height:24px;color:#4B5563;word-break:keep-all;">{html.escape(intro)}</span></summary>'
            f'<div style="padding:0 10px;">{"".join(rows)}</div></details>')



def page(urls):
    # 맨 위 그림 = 사용자 그림 한 장(분석이 음악 · 상승이 · 하락이 책 읽기, 2026-11-15) — 요청 1회.
    # 크기 252 × 132 (11-15 사용자: 30% 작게 — 폰 약 360 → 252, 정수 px 라 높이 132 · 비율 차이는 contain 으로)
    art = (f'<img src="{RC.img_src(os.path.join(HERE, "banner"), "study_head")}" alt="" width="252" height="132" '
           'style="display:block;width:252px;height:132px;max-width:100%;object-fit:contain;margin:0 auto;border-radius:0;">')
    head = (f'<div data-study-head="1" style="padding:19px {dk.ALIGN_PX}px 8px;margin:0 0 16px;text-align:center;">'
            f'<div aria-hidden="true" style="margin:0 0 12px;">{art}</div>'
            # 2026-11-20 사용자: `- 주식공부` 는 큰 제목이 아니라 머리 줄 옆 아주 작은 글씨(data-head-sub)
            '<h1 style="margin:0 0 6px;font-size:26px;line-height:36px;font-weight:800;color:#111;">주식 제대로 알기</h1>'
            f'<p data-seo-lead="1" style="margin:0;font-size:17px;line-height:26px;color:#333;word-break:keep-all;">{INTRO}</p></div>')
    cards = "".join(course_card(k, *c, urls) for k, c in enumerate(COURSES))
    # 접기 표시 — 사파리 기본 삼각형 숨김 · 펼치면 화살표 위로 (글 안 style 한 줄, 테마 붙여넣기 없이)
    cards = ('<style>details[data-course]>summary::-webkit-details-marker{display:none}'
             'details[data-course] .study-fold svg{transition:transform .15s}details[data-course][open] .study-fold svg{transform:rotate(180deg)}</style>' + cards)
    return (RC.share_tag() + f'<span data-head-label="{RC.HEAD_LABEL}" data-head-sub="{RC.HEAD_SUB}" hidden></span><span data-nav="home" hidden></span>'
            + dk.WRAP_OPEN + head + cards + dk.WRAP_CLOSE)


KEY, TITLE = "study", "주식 제대로 알기 - 주식공부"   # 주소 /p/study.html(바꾸지 않음) — 처음 만들 때 영문 이름으로 정해진다. 제목 = 검색 결과 제목이라 `주식 공부` 를 남김 (2026-11-20)


def publish(urls, dry=False):
    """고정 페이지 게시 — 종목 분석 게시기(stock-radar/publish_pages.publish)를 그대로(429 백오프 · 해시가 같으면 건너뜀). 그림 = gh-pages images/study/."""
    root = os.path.dirname(os.path.dirname(HERE))
    sys.path[:0] = [os.path.join(root, "experiments", "stock-radar"), os.path.join(root, "experiments", "daily-report")]
    import publish_course as PC
    import publish_pages as PP
    import universe as U
    RC.IMG_BASE = PC.IMG_BASE
    PC._env()
    body = os.path.join(HERE, "output", "study_page.html")
    open(body, "w", encoding="utf-8").write(page(urls))
    data = os.path.join(HERE, "output")   # 발행 기록(해시) — git 제외 폴더
    os.makedirs(data, exist_ok=True)
    PP.targets = lambda only=None: [(KEY, TITLE, KEY, f"{U.BLOG}/p/{KEY}.html", body)]
    PP.HASHES = os.path.join(data, "page_hashes.json")
    PP.PAGES_LIVE = os.path.join(data, "pages_live.json")
    PP._body = lambda path: open(path, encoding="utf-8").read()
    return PP.publish(dry=dry)


def main():
    p = os.path.join(HERE, "published.json")
    urls = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    if "--publish" in sys.argv or "--dry" in sys.argv:
        sys.exit(0 if publish(urls, dry="--dry" in sys.argv) else 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # 목업 안 편 링크 = 같은 폴더의 글 목업(지금 렌더러 기준) — 블로그 주소면 고치기 전 발행본이 열린다 (2026-11-20 사용자: 목업에서 확인)
    # 발행 전 초안도 글 목업이 있으면 링크 (2026-11-20 사용자: 목업에서 빠지지 않게)
    files = {f for c in COURSES for _, _, f in c[2] if f} | set(urls)
    urls = {k: f"mock_{os.path.splitext(k)[0]}.html" for k in files if os.path.exists(os.path.join(HERE, "output", f"mock_{os.path.splitext(k)[0]}.html"))}
    path = dk.write_mock(page(urls), OUT, TITLE)
    if path:
        pg = open(path, encoding="utf-8").read().replace("</body>", RC.MOCK_HEAD_JS + "</body>", 1)
        open(path, "w", encoding="utf-8").write(pg)
    print(f"[주식 공부 목록] → {path}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
