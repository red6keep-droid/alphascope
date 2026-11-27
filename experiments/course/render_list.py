"""주식 공부 목록 페이지(/p/study.html) — 과정별 편 목록.

    .venv/bin/python experiments/course/render_list.py              # output/mock_study_list.html
    .venv/bin/python experiments/course/render_list.py --publish    # Blogger 고정 페이지 /p/study.html 만들기 · 고치기

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
INTRO_NEW = "처음 배우는 기본부터, 흔히 듣는 말을 데이터로 확인하기까지"   # 입문 과정이 생겨 소개 줄을 넓힘 — 시안(--variant)에서만
# 시안: 펼친 카드만 색 · 들어오면 첫 카드만 펼침 · 오름 빨강 · 내림 파랑은 안 씀 → 녹색 · 노랑 두 가지
VARIANTS = {   # 이름 → (펼친 카드 바탕, 테두리 · 줄, 과정 이름표 글자)
    "green": ("#F0FDF4", "#E4F0E8", "#0F766E"),    # 테두리 · 구분선 = 바탕을 5% 진하게(240·253·244 × 0.95)
    "yellow": ("#FEF9E7", "#F1EDDB", "#92400E"),   # 같은 규칙(254·249·231 × 0.95)
}
CARD_THEME = {0: "green", 1: "yellow"}   # 시안: 과정 카드마다 펼친 색 — 입문 녹색 · 1과정(착각) 노랑, 나머지 흰색
ICON_PX = 40   # 32 → 40 · 입문 편 줄 앞 아이콘(사용자 그림 icons/ep_입문-NN.webp, 없으면 점선 자리) — 장면 그림 조각은 뺌
TWO_LINE = {   # 입문 편 제목 두 줄 — 끊는 자리
    "입문-01-주식이란.md": ("주식이 뭔가요?", "주가는 왜 날마다 바뀌나요?"),
    "입문-02-얼마로-시작.md": ("얼마가 있어야 시작하나요?", "잃으면 어떻게 되나요?"),
    "입문-03-계좌와-주문.md": ("계좌는 어디서 만들고", "주문은 어떻게 넣나요?"),
    "입문-04-화면-읽기.md": ("앱 화면의 숫자와 색은", "무슨 뜻인가요?"),
    "입문-05-수수료와-세금.md": ("사고팔 때 드는 돈과", "세금은 얼마인가요?"),
    "입문-06-종목과-시장.md": ("종목 하나를 고르나요,", "시장을 통째로 사나요?"),
    "입문-07-한국과-미국.md": ("한국 주식과 미국 주식은", "무엇이 다른가요?"),
    "입문-08-회사-소식.md": ("회사는 주주에게", "어떤 소식을 보내나요?"),
    "입문-09-금리와-환율.md": ("뉴스는 왜 금리와 환율로", "주가를 설명하나요?"),
    "입문-10-비싼가-싼가.md": ("이 주식,", "비싼 건가요 싼 건가요?"),
    "입문-11-차트와-지표.md": ("차트의 선과 지표는", "무엇을 알려 주나요?"),
    "입문-12-정보와-리딩방.md": ("정보는 어디서 얻고,", "누구 말을 믿어야 하나요?"),
    # 1과정도 같은 꼴 — 아이콘 · 두 줄 · 번호 없음
    "착각-기준.md": ("이 연재는", "이렇게 확인합니다"),
    "착각-01-실적.md": ("실적이 좋다는데", "왜 주가는 떨어질까?"),
    "착각-02-물림.md": ("고점에 물리면", "얼마나 오래 가나?"),
    "착각-03-공포매도.md": ("크게 빠진 날 팔면,", "언제 특히 비쌌나?"),
    "착각-04-되사기.md": ("판 값에 다시 사려다", "더 비싸게 사는 이유"),
    "착각-05-분할매수.md": ("분할 매수,", "하단을 기다리면 더 싸게 모일까?"),
    "착각-06-과열.md": ("과열이면", "떨어진다고요?"),
    "착각-07-볼린저.md": ("볼린저 하단에서 샀는데", "왜 더 떨어질까?"),
    "착각-08-골든크로스.md": ("골든크로스는 2010년대엔 틀리고", "2020년대엔 맞았다?"),
    "착각-09-파동.md": ("동전 던지기에도", "파동은 생긴다"),
    "착각-10-마치며.md": ("마치며,", "지표는 방향이 아니라 크기를 잰다"),
}
VARIANT = "green"   # 시안 확정 → 기본 모양(과정별 펼친 색 · 아이콘 · 두 줄 · 첫 카드만 펼침). None = 옛 모양
THUMB_PX = 44   # 입문 편 줄 앞 작은 그림 = 그 편 장면 그림 가운데 정사각(chars/thumb_입문-NN.webp 96px, 화면 44)

# (과정 이름, 한 줄 소개, [(번호, 편 제목, 초안 파일 이름 또는 None)])
COURSES = [
    ("주식 처음 시작하기", "도토리 숲 이야기로 주식의 기본을 처음부터 배웁니다.", [   # 입문 과정 — 1과정 앞, 이름표 `입문` (2026-11-22 발행)
        ("1", "주식이 뭔가요? 주가는 왜 날마다 바뀌나요?", "입문-01-주식이란.md"),
        ("2", "얼마가 있어야 시작하나요? 잃으면 어떻게 되나요?", "입문-02-얼마로-시작.md"),
        ("3", "계좌는 어디서 만들고 주문은 어떻게 넣나요?", "입문-03-계좌와-주문.md"),
        ("4", "앱 화면의 숫자와 색은 무슨 뜻인가요?", "입문-04-화면-읽기.md"),
        ("5", "사고팔 때 드는 돈과 세금은 얼마인가요?", "입문-05-수수료와-세금.md"),
        ("6", "종목 하나를 고르나요, 시장을 통째로 사나요?", "입문-06-종목과-시장.md"),
        ("7", "한국 주식과 미국 주식은 무엇이 다른가요?", "입문-07-한국과-미국.md"),
        ("8", "회사는 주주에게 어떤 소식을 보내나요?", "입문-08-회사-소식.md"),
        ("9", "뉴스는 왜 금리와 환율로 주가를 설명하나요?", "입문-09-금리와-환율.md"),
        ("10", "이 주식, 비싼 건가요 싼 건가요?", "입문-10-비싼가-싼가.md"),
        ("11", "차트의 선과 지표는 무엇을 알려 주나요?", "입문-11-차트와-지표.md"),
        ("12", "정보는 어디서 얻고, 누구 말을 믿어야 하나요?", "입문-12-정보와-리딩방.md"),
    ]),
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
    th_ = VARIANTS[CARD_THEME[k]] if VARIANT and k in CARD_THEME else None
    line = th_[1] if th_ else "#E2E8F0"
    for n, t, f in eps:
        url = urls.get(f) if f else None
        num = f'<span style="flex:none;width:32px;font-size:15px;line-height:24px;color:{(th_[2] if th_ else "#0F766E") if url else "#9CA3AF"};font-weight:700;">{n}</span>'
        if th_ and f:   # 시안: 번호 대신 아이콘 · 제목 두 줄
            ic = os.path.join(HERE, "icons", f"ep_{f[:5]}.webp")
            num = (f'<img src="{RC.img_src(os.path.join(HERE, "icons"), "ep_" + f[:5])}" alt="" width="{ICON_PX}" height="{ICON_PX}" style="flex:none;display:block;width:{ICON_PX}px;height:{ICON_PX}px;margin:0 20px 0 5px;max-width:none;border-radius:0;">'
                   if os.path.exists(ic) else
                   f'<span style="flex:none;width:{ICON_PX}px;height:{ICON_PX}px;margin:0 20px 0 5px;box-sizing:border-box;border:1px dashed #94A3B8;border-radius:8px;"></span>')
            if f in TWO_LINE:
                t = "\n".join(TWO_LINE[f])
        if url:
            rows.append(f'<a href="{html.escape(url)}" data-row-link="1" style="display:flex;align-items:center;gap:0;padding:12px {dk.ALIGN_PX}px;border-top:1px solid {line};text-decoration:none;color:inherit;">'
                        f'{num}<span style="flex:1 1 auto;min-width:0;font-size:17px;line-height:26px;font-weight:700;color:#111;word-break:keep-all;">{html.escape(t).replace(chr(10), "<br>")}</span>'
                        f'<span style="flex:none;margin-left:8px;color:#6B7280;">{CHEV.replace('width="16" height="16"', 'width="14" height="14"') if VARIANT else CHEV}</span></a>')
        else:
            rows.append(f'<div style="display:flex;align-items:center;padding:12px {dk.ALIGN_PX}px;border-top:1px solid {line};">'
                        f'{num}<span style="flex:1 1 auto;min-width:0;font-size:17px;line-height:26px;color:#9CA3AF;word-break:keep-all;">{html.escape(t)}</span>'
                        '<span style="flex:none;margin-left:8px;font-size:13px;line-height:18px;font-weight:700;color:#9CA3AF;white-space:nowrap;">준비 중</span></div>')
    state = f"{total}편 중 {done}편" if done else f"{total}편 준비 중"
    # 접기: 과정 이름 줄 오른쪽 접기 버튼 · 0편(들어가며)부터 편 목록 전체가 접힌다. details 라 JS 없이 접히고 접힌 글도 검색엔진이 읽는다.
    # 처음 상태 = 나온 편이 있는 과정만 펼침(지금 1과정), 준비 중뿐인 과정은 접힘. 카드 머리(과정 · 제목 · 소개) 전체가 누르는 자리
    btn0 = ('<span class="study-fold" aria-hidden="true" style="flex:none;display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;'
           'border:1px solid #E2E8F0;border-radius:6px;background:#fff;color:#111;box-sizing:border-box;">'
           '<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
           '<path d="M4 6l4 4 4-4"/></svg></span>')
    # 시안: 접기 버튼 = 강조 카드 접기 버튼(dk.emph_fold_btn, 31 네모 · 둥글기 7) — 펼친 카드에선 CSS 로 바탕 = 카드 바탕 20% 밝게 · 테두리 = 카드 테두리
    btn = dk.emph_fold_btn("#fff", "#E2E8F0", 0).replace('<span style=', '<span class="study-fold" aria-hidden="true" style=', 1) if VARIANT else btn0
    return (f'<details data-course="{k + 1}"{" open" if (k == 0 if VARIANT else done) else ""} style="margin:0 0 20px;background:#fff;border:1px solid #E2E8F0;border-radius:12px;overflow:hidden;">'
            f'<summary style="display:block;list-style:none;cursor:pointer;padding:16px {dk.ALIGN_PX + 10}px 14px;">'
            f'<span style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 0 4px;">'
            f'<span style="font-size:14px;line-height:20px;font-weight:700;color:{th_[2] if th_ else "#0F766E"};">{"입문" if k == 0 else f"{k}과정"}</span>'   # 맨 앞 = 입문 과정, 그다음부터 1과정 (2026-11-22)
            f'<span style="display:flex;align-items:center;gap:8px;">{"" if VARIANT else f'<span style="font-size:13px;line-height:18px;color:{dk.NOTE};">{state}</span>'}{btn}</span></span>'
            f'<span style="display:block;margin:0 0 6px;font-size:21px;line-height:30px;font-weight:800;color:#111;word-break:keep-all;">{html.escape(name)}</span>'
            f'<span style="display:block;font-size:15px;line-height:24px;color:#4B5563;word-break:keep-all;">{html.escape(intro)}</span></summary>'
            f'<div style="padding:0 10px;">{"".join(rows)}</div></details>')



def page(urls):
    # 맨 위 그림 = 사용자 그림 한 장(분석이 음악 · 상승이 · 하락이 책 읽기, 2026-11-15) — 요청 1회.
    # 크기 252 × 132
    art = (f'<img src="{RC.img_src(os.path.join(HERE, "banner"), "study_head")}" alt="" width="252" height="132" '
           'style="display:block;width:252px;height:132px;max-width:100%;object-fit:contain;margin:0 auto;border-radius:0;">')
    head = (f'<div data-study-head="1" style="padding:19px {dk.ALIGN_PX}px 8px;margin:0 0 16px;text-align:center;">'
            f'<div aria-hidden="true" style="margin:0 0 12px;">{art}</div>'
            #: `- 주식공부` 는 큰 제목이 아니라 머리 줄 옆 아주 작은 글씨(data-head-sub)
            '<h1 style="margin:0 0 6px;font-size:26px;line-height:36px;font-weight:800;color:#111;">주식 제대로 알기</h1>'
            f'<p data-seo-lead="1" style="margin:0;font-size:17px;line-height:26px;color:#333;word-break:keep-all;">{INTRO_NEW if VARIANT else INTRO}</p></div>')
    cards = "".join(course_card(k, *c, urls) for k, c in enumerate(COURSES))
    # 접기 표시 — 사파리 기본 삼각형 숨김 · 펼치면 화살표 위로 (글 안 style 한 줄, 테마 붙여넣기 없이)
    cards = ('<style>details[data-course]>summary::-webkit-details-marker{display:none}'
             'details[data-course] .study-fold svg{transition:transform .15s}details[data-course][open] .study-fold svg{transform:rotate(180deg)}'
             + ("".join(f'details[data-course="{k + 1}"][open]{{background:{VARIANTS[v][0]}!important;border-color:{VARIANTS[v][1]}!important}}'   # 시안: 펼친 카드만 색, 과정마다
                        f'details[data-course="{k + 1}"][open] .study-fold{{border-color:{VARIANTS[v][1]}!important;background:{dk.lighten(VARIANTS[v][0])}!important}}'
                        for k, v in CARD_THEME.items()) if VARIANT else '') + '</style>' + cards)
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
    RC.IMG_BASE = PC.INTRO_IMG_BASE   # 그림 = Pages 그림 저장소(img.newfact.app/study — 아이콘 · 배너 모두 있음, 2026-11-22)
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
    global VARIANT, OUT
    if "--variant" in sys.argv:   # 시안 목업: output/mock_study_list_green.html · _yellow.html (2026-11-22)
        VARIANT = sys.argv[sys.argv.index("--variant") + 1]
        OUT = OUT.replace(".html", f"_{VARIANT}.html")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # 목업 안 편 링크 = 같은 폴더의 글 목업(지금 렌더러 기준) — 블로그 주소면 고치기 전 발행본이 열린다
    # 발행 전 초안도 글 목업이 있으면 링크
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
