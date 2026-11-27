"""사이트 기본 페이지 3개 — 소개(/p/about.html) · 개인정보처리방침(/p/privacy.html) · 문의(/p/contact.html).
애드센스 신청 전 필수 페이지.

    .venv/bin/python experiments/site-pages/render_site_pages.py            # output/mock_about.html · mock_privacy.html · mock_contact.html
    .venv/bin/python experiments/site-pages/render_site_pages.py --dry      # 발행 미리 보기(쓰기 없음)
    .venv/bin/python experiments/site-pages/render_site_pages.py --publish  # Blogger 고정 페이지 만들기 · 고치기 (사용자 승인 뒤에만)

- 개인정보처리방침 내용은 코드에서 확인한 실제 동작대로(firestore.rules · comment-reply · 테마 localStorage). 동작이 바뀌면 여기도 고친다.
- 문의 이메일(CONTACT_EMAIL)은 사용자가 정할 때까지 빈칸 — 비어 있으면 발행하지 않는다.
- 광고 문단(ADS_ON)은 애드센스 승인 · 광고 게재와 같은 날 켠다.
"""
import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import design_kit as dk  # noqa: E402

OUT = os.path.join(HERE, "output")
CONTACT_EMAIL = "contact@newfact.app"   # 2026-11-21 도메인 구입 뒤 — Cloudflare 이메일 라우팅으로 운영자 네이버 메일함에 전달
ADS_ON = False              # 광고를 실제로 붙이는 날 True
EFFECTIVE = "2026년 11월 21일"   # 시행일 — 내용을 바꾸면 날짜도 바꾸고 아래 '바뀐 내용' 줄에 남긴다

P = f"font-size:{dk.BODY};line-height:{dk.LH_BODY};color:#333;margin:0 0 16px;word-break:keep-all;padding-left:{dk.ALIGN_PX}px;"
UL = f"font-size:{dk.BODY};line-height:{dk.LH_BODY};color:#333;margin:0 0 16px;padding-left:{dk.ALIGN_PX + 22}px;word-break:keep-all;"
TH = "text-align:left;padding:10px 12px;border-bottom:1px solid #E2E8F0;font-weight:700;color:#111;white-space:nowrap;vertical-align:top;"
TD = "padding:10px 12px;border-bottom:1px solid #E2E8F0;color:#333;vertical-align:top;word-break:keep-all;"


def p(t):
    return f'<p style="{P}">{t}</p>'


def ul(items):
    return f'<ul style="{UL}">' + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def table(head, rows):
    h = "".join(f'<th style="{TH}">{c}</th>' for c in head)
    b = "".join("<tr>" + "".join(f'<td style="{TD}">{c}</td>' for c in r) + "</tr>" for r in rows)
    return (f'<div style="overflow-x:auto;margin:0 0 16px;"><table style="border-collapse:collapse;width:100%;font-size:{dk.NAME};line-height:{dk.LH_CARD};'
            f'background:#fff;border:1px solid #E2E8F0;border-radius:8px;"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>')


def brand(size=None):
    """문장 속 `Newfact` = 로고 + 로고 글꼴(Noto Sans KR 900) — 리포트 문장과 같은 render_html.brand_mark."""
    sys.path.insert(0, os.path.join(HERE, "..", "nvda-report"))
    import render_html as R  # noqa: E402
    return R.brand_mark(size or int(str(dk.BODY).rstrip("px")))


def lead(t):
    return f'<p data-seo-lead="1" style="{dk.SEO_LEAD}padding-left:{dk.ALIGN_PX}px;">{t}</p>'


def mail():
    if CONTACT_EMAIL:
        e = html.escape(CONTACT_EMAIL)
        return f'<a href="mailto:{e}">{e}</a>'
    return '<b style="color:#B91C1C;">[문의용 이메일 — 정해지면 채움]</b>'


def wrap(body):
    return dk.WRAP_OPEN + body + dk.WRAP_CLOSE


# ── 소개 ─────────────────────────────────────────────────────────────
def _label(name):
    """메뉴와 같은 라벨 주소(home-split/mock_menu.L) — 화면 이름은 메뉴에 보이는 말 그대로(헌법 제10조)."""
    from urllib.parse import quote
    return "/search/label/" + quote(name)


def _icons():
    """전체 메뉴 줄과 같은 선 아이콘(home-split/mock_menu.IC) — 색 없이 글자색(currentColor)."""
    sys.path.insert(0, os.path.join(HERE, "..", "home-split"))
    import mock_menu as M  # noqa: E402
    return {k: v.replace('class="mi"', 'width="22" height="22" style="display:block;"') for k, v in M.IC.items()}


TITLE_PX = 26         # 큰 제목 글자
ABOUT_PX = 17         # 소개 페이지 본문 글자
ABOUT_LH = 31         # 본문 행간 — 19 · 35 를 글자 비율대로 줄임(35 × 17 / 19 ≈ 31, 사용자 "글자 비율에 맞게 행간도")
ITEM_LH = ABOUT_LH - 2   # 아이콘 단락(무엇을 하나요 · 어떻게 만드나요)만 본문보다 2 좁게 (사용자 2차)
ITEM_GAP = 22         # 아이콘 단락 사이 · 제목 아래 — 행간 여백(29 − 17 = 12)보다 크게
SECTION_GAP = 48      # 구획 사이(큰 구분) — 구획 안 여백(22 · 16 · 10)보다 크게
RULE_PX, RULE_LH, RULE_GAP = 16, 26, 10   # 지키는 원칙 = 16 회색, 점 줄 사이 10 = 행간 여백보다 넓게
# 여백 원칙: 영역은 여백으로 가른다 — 영역 사이 여백은 그 안 문장의 행간 여백과 같으면 안 되고,
# 작은 구분(단락 · 점 줄) < 큰 구분(구획). 작은 여백을 큰 구분에 쓰지 않는다.


def _how_icons():
    """어떻게 만드나요 단락 아이콘 — 메뉴 아이콘과 같은 선 굵기 1.8 · 24 칸."""
    sys.path.insert(0, os.path.join(HERE, "..", "home-split"))
    import mock_menu as M  # noqa: E402
    d = {
        "data": "<ellipse cx='12' cy='6' rx='7' ry='2.5'/><path d='M5 6v12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V6'/><path d='M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5'/>",
        "compare": "<path d='M4 20h16'/><path d='M8 17V9M16 17V5'/><path d='M5 9h6M13 5h6'/>",
        "fact": "<circle cx='12' cy='12' r='8.5'/><path d='M8.2 12.3l2.6 2.6 5-5.4'/>",
        "rule": "<rect x='5' y='3' width='14' height='18' rx='2'/><path d='M8.5 7h7'/><path d='M8.5 11.5h1M11.5 11.5h1M14.5 11.5h1M8.5 15h1M11.5 15h1M14.5 15h1M8.5 18h1M11.5 18h1M14.5 18h1'/>",
        "study": "<path d='M2.5 9.5L12 5l9.5 4.5L12 14z'/><path d='M6.5 11.5v4.5c0 1.3 2.5 2.5 5.5 2.5s5.5-1.2 5.5-2.5v-4.5'/><path d='M21.5 9.5v5'/>",
        "record": "<path d='M12 3.5l8.5 4.5L12 12.5 3.5 8z'/><path d='M3.5 12L12 16.5 20.5 12'/><path d='M3.5 16L12 20.5 20.5 16'/>",
    }
    return {k: M.svg(v).replace('class="mi"', 'width="22" height="22" style="display:block;"') for k, v in d.items()}


def about():
    # — 헌법 전문(가 이름의 뜻 · 나 독자 · 라 기록) · 제1 · 2 · 5 · 6 · 7조와
    # 지금 메뉴(리포트 둘 · 증시 시황 · 증시 전망 · Hot Issue · 종목 목록 · Newfact 뉴스 · 주요 인물 발언 · 주식 공부)에 맞춤.
    # 고침: 독자 = 개인 투자자 · 페이지 전체 글자 단위 줄바꿈 · 로고는 첫 문장만 · 본문 17 · 행간 비율대로 ·
    # 제목 = 구분선 없이 본문 선 · 물음표 · 무엇을 하나요 · 어떻게 만드나요 = 아이콘 + 이름 줄 / 설명 줄(아이콘 칸 침범 없음, 링크 색 없음) ·
    # 지키는 원칙 = 16 회색 · 2px 점 · '누가 계산해도 같은 숫자' 문장 · 앞으로 · 연락 구획 뺌.
    ic = {**_icons(), **_how_icons()}
    al = dk.ALIGN_PX

    def h(title, gap=11, big=False):
        # big = 큰 제목(Newfact 란 · 무엇을 하나요? · 어떻게 만드나요?) — TITLE_PX · 행간 +8
        if big:
            return h(title, gap).replace(f"font-size:{dk.H2_SIZE};", f"font-size:{TITLE_PX}px !important;", 1).replace(f"line-height:{dk.LH_H2};", f"line-height:{TITLE_PX + 8}px !important;", 1)   # !important = 테마가 폰에서 구획 제목을 20 으로 덮는 것을 이김
        return dk.h2(title, line=False).replace("margin:28px 0 11px;padding:0;", f"margin:{SECTION_GAP}px 0 {gap}px;padding:0 0 0 {al}px;", 1)

    def para(t):
        return f'<p style="font-size:{ABOUT_PX}px;line-height:{ABOUT_LH}px;color:#333;margin:0 0 16px;padding-left:{al}px;">{t}</p>'

    def item(key, name, text, href=None):
        inner = (f'<span style="flex:none;width:22px;height:{ITEM_LH}px;display:flex;align-items:center;color:#333;">{ic[key]}</span>'
                 f'<span style="flex:1;min-width:0;"><span style="display:block;font-weight:700;color:#111;">{name}</span>'
                 f'<span style="display:block;">{text}</span></span>')
        box = (f"display:flex;gap:12px;align-items:flex-start;margin:0 0 {ITEM_GAP}px;padding-left:{al}px;"
               f"font-size:{ABOUT_PX}px;line-height:{ITEM_LH}px;color:#333;text-decoration:none;")
        return f'<a href="{href}" style="{box}">{inner}</a>' if href else f'<div style="{box}">{inner}</div>'

    def rule(t):
        dot = f'<span style="flex:none;width:2px;height:{RULE_LH}px;display:flex;align-items:center;"><span style="width:2px;height:2px;border-radius:1px;background:#6B7280;"></span></span>'
        return f'<li style="display:flex;gap:8px;margin:0 0 {RULE_GAP}px;">{dot}<span style="flex:1;min-width:0;">{t}</span></li>'

    rules = (f'<ul style="list-style:none;margin:0;padding:0 0 0 {al}px;font-size:{RULE_PX}px;line-height:{RULE_LH}px;color:#6B7280;">'
             + "".join(rule(t) for t in [
                 "특정 종목의 매수 · 매도를 권유하지 않고, 개별 투자 상담을 하지 않습니다. 판단은 독자가 합니다.",
                 "확인된 변화와 그날 있었던 소식을 나눠 적습니다. 소식 하나를 주가가 움직인 원인으로 단정하지 않습니다.",
                 "전망은 결과가 나오기 전에 적고, 판정 기준도 미리 정합니다. 맞은 전망과 틀린 전망을 모두 그대로 남깁니다.",
                 "과거 기록은 조건과 표본 수를 함께 적고, 앞으로도 같다고 말하지 않습니다.",
                 "외부 의견(애널리스트 의견 · 목표가 · 인물 발언)은 누구의 말인지 밝혀 옮깁니다.",
                 "모든 독자에게 같은 글을 보여 줍니다. 유료 회원 · 유료 정보가 없습니다.",
             ]) + "</ul>")
    # 6차: 제목 줄 = `Newfact 소개`(로고는 제목 줄에만 — 뉴스 글 제목과 같은 테마 장치: 본문 [data-headline] + [data-news-post] 표식 →
    # 저장 제목의 `Newfact ` 를 머리 줄 로고로 바꿈, 테마 붙여넣기 없음) · 문장 속 Newfact 는 로고 없이 글자만 · '짧게' 뺌 ·
    # 설명글이 아니라 소개글 — 독자에게 주는 가치 · 하려는 일 · 계속 노력한다는 뜻을 문장에 녹임(과장 · 적중 자랑 없이, 헌법 제5 · 6 · 7조 안에서) ·
    # 주식 공부 = 주식 공부 페이지 소개 문장에 맞춤 · 아이콘 학사모.
    # 7차: 제목 줄 `소개`(폰 18 · PC 23 — 11-27 1 줄임) = 작은 회색 글씨 · 사이 막대 없이 로고 글자와 비슷하게(Noto Sans KR 900 · 검정) — 이 페이지 안 style 로만 덮음 ·
    # `Newfact` 굵게 = 맨 위 문장 + `Newfact 란` 구획만(확인된 사실만 · 앞으로의 Newfact 는 보통 굵기)
    B = lambda t: f'<b style="font-weight:700;color:#111;">{t}</b>'
    NF = B("Newfact")
    mark = ('<style>.nf-title .nf-title-sub{font-family:\'Noto Sans KR\',sans-serif;font-weight:900;font-size:18px;line-height:22px;color:#000;letter-spacing:-0.3px;}'
            '.nf-title .nf-title-sub::before{display:none;}.nf-title{gap:6px;}'
            '@media (min-width:681px){.nf-title .nf-title-sub{font-size:23px;line-height:28px;}}</style>'
            '<span data-headline="1" data-news-post="about" hidden></span>')
    lead_p = lead(NF + " 는 미국 · 한국 주식시장에서 오늘 무엇이 달라졌는지를 데이터로 찾아 알리고, 그 변화가 어떻게 이어졌는지를 기록하는 주식 데이터 리포트입니다.")
    lead_p = lead_p.replace(f"font-size:{dk.BODY};line-height:{dk.LH_BODY};", f"font-size:{ABOUT_PX}px;line-height:{ABOUT_LH}px;", 1)
    body = (
        mark + lead_p
        + h("Newfact 란", big=True)
        + para("Newfact = " + B("New") + " + " + B("Fact") + ".<br>새로 생긴 변화 가운데 확인할 수 있는 사실이라는 뜻입니다. "
               "뉴스가 무슨 일이 일어났는지를 말한다면, " + NF + " 는 무엇이 평소와 달라졌는지를 말합니다.")
        + para("주식 정보는 넘쳐 나지만, 그 안에서 내 판단에 정말 필요한 사실을 골라내기는 갈수록 어렵습니다. "
               + NF + " 는 매일 시장을 확인하면서도 자료를 하나하나 분석할 시간은 없는 개인 투자자를 대신해, 수많은 자료를 먼저 읽고 견주어 봅니다. "
               "오늘 정말 달라진 것이 무엇인지, 평소와 얼마나 다른지, 무엇과 이어지는지를 한눈에 확인하실 수 있습니다.")
        + para("아침에는 밤사이 미국 시장을, 저녁에는 그날 한국 시장을 전합니다. "
               "바쁜 하루에도 시장의 중요한 변화를 놓치지 않도록, 믿고 볼 수 있는 기록을 날마다 쌓아 갑니다.")
        + h("무엇을 하나요?", gap=ITEM_GAP, big=True)
        + item("report", "증시 리포트", "장이 끝나면 지수 · 금리 · 환율 · 업종 움직임과 주요 뉴스를 한 편에 모읍니다. "
               "미국 장은 한국 아침에, 한국 장은 그날 저녁에 나와 하루 시장을 한 번에 살필 수 있습니다.")
        + item("story", "증시 시황", "숫자만으로는 보이지 않는 그날 시장의 흐름과 눈에 띈 종목을, 글 한 편으로 읽기 쉽게 풀어 씁니다.", _label("증시 시황"))
        + item("news", "Newfact 뉴스", "국내 여러 보도에서 확인된 사실만 추리고, 관련 종목이 시장과 견줘 얼마나 움직였는지를 함께 보여 줍니다.", _label("Newfact 뉴스"))
        + item("stock", "종목 페이지", "미국 · 한국 주요 종목과 상장지수펀드(ETF)의 가격 흐름, 평소 움직임과의 비교, 실적 · 공시, 함께 움직이는 종목을 한 화면에 모았습니다. "
               "여러 곳을 찾아다니지 않아도 됩니다.", "/p/stock-lists.html")
        + item("forecast", "증시 전망", "시장이 갈 수 있는 갈래와 그 근거를 미리 적어 두고, 정한 날에 실제로 어떻게 됐는지 다시 확인합니다.", "/p/forecast-list.html")
        + item("issue", "Hot Issue", "시장을 흔드는 큰 사건이 생기면 뉴스 흐름과 시장 반응을 처음부터 이어서 기록합니다. 사건의 전체 흐름을 한 자리에서 따라갈 수 있습니다.")
        + item("people", "주요 인물 발언", "시장에 영향을 주는 인물이 무엇을 말했는지 모아, 말의 방향이 어떻게 바뀌어 가는지 볼 수 있게 정리합니다.", _label("인물 발언"))
        + item("study", "주식 공부", "처음 배우는 기본부터 흔히 듣는 말을 데이터로 확인하기까지, 주식을 제대로 알아 가는 강좌입니다.", "/p/study.html")
        + h("어떻게 만드나요?", gap=ITEM_GAP, big=True)
        + item("data", "공개 자료 · 종가 기준", "공개된 시세 · 미국 증권거래위원회(SEC)와 금융감독원 전자공시(DART) 공시 · 미국 연방준비은행(FRED)과 한국은행(ECOS) 경제 지표 · 뉴스를 모아, "
               "미리 정한 계산 규칙으로 숫자를 만듭니다. 가격은 종가 기준입니다.")
        + item("compare", "비교 대상과 함께", "숫자는 견줄 대상이 있어야 뜻이 생깁니다. 종목은 시장 · 업종과, 지표는 그 지표의 평소와 견준 값을 함께 싣습니다.")
        #: 수집기 글 = 같은 사건 보도 여러 건에서 사실만 뽑아 씀. '새로 쓴 글' · 부정문(단독 안 씀 등) 쓰지 않기
        + item("fact", "확인된 사실만", "Newfact 의 국내 기사는 같은 사건을 다룬 여러 보도에서 확인된 사실만 모아 전달합니다.")
        + item("rule", "숫자는 규칙이, 글은 AI 가 돕습니다", "뉴스 분류 · 번역 · 해설 문장 일부는 AI 가 쓰며, 숫자 계산은 AI 가 하지 않습니다.")
        + item("record", "같은 기준으로 쌓는 기록", "기록은 날마다 같은 기준으로 쌓습니다. 하루치 기록은 작지만, 쌓일수록 지난 비슷한 때에 어떻게 됐는지를 더 깊이 보여 드릴 수 있습니다.")
        + h("지키는 원칙", gap=ITEM_GAP)
        + rules
        + h("앞으로의 Newfact")
        + para("Newfact 는 아직 자라는 중입니다. 다루는 종목과 자료를 꾸준히 넓히고, 더 쉽게 읽히도록 화면을 계속 고쳐 가고 있습니다. "
               "화려한 예측보다 확인할 수 있는 사실을, 한 번의 적중보다 날마다 같은 기준으로 쌓은 기록을 더 값지게 여깁니다.")
        + para("개인 투자자가 스스로 판단하는 데 꼭 필요한 자료가 되도록 노력하겠습니다. Newfact 가 성장해 가는 모습을 지켜봐 주세요.")
    )
    # 글자 단위 줄바꿈 = 페이지 전체(사용자 3차) — 감싸는 div 한 번 + 첫 문장 keep-all 바꿈
    return wrap('<div style="word-break:break-all;">' + body.replace("word-break:keep-all", "word-break:break-all") + "</div>")


# ── 개인정보처리방침 ─────────────────────────────────────────────────
def privacy():
    ads = []
    if ADS_ON:
        ads = [dk.section("광고와 쿠키", p(
            "이 블로그는 Google 애드센스 광고를 싣습니다. Google 을 포함한 제3자 광고 업체는 쿠키를 사용해, 이용자가 이 블로그나 다른 웹사이트를 방문한 기록을 바탕으로 광고를 보여 줄 수 있습니다. "
            "Google 의 광고 쿠키 사용으로 Google 과 파트너는 이용자의 방문 기록에 따라 광고를 게재할 수 있습니다.")
            + p('맞춤 광고는 <a href="https://adssettings.google.com" rel="nofollow noopener" target="_blank">Google 광고 설정</a>에서 끌 수 있고, '
                '<a href="https://www.aboutads.info" rel="nofollow noopener" target="_blank">www.aboutads.info</a> 에서 다른 제3자 업체의 맞춤 광고 쿠키도 거부할 수 있습니다. '
                'Google 이 정보를 쓰는 방식은 <a href="https://policies.google.com/technologies/partner-sites" rel="nofollow noopener" target="_blank">Google 파트너 사이트 정책</a>에 있습니다.'))]
    return wrap(
        lead(brand() + f"(이하 '블로그')는 이용자의 개인정보를 필요한 만큼만 받고, 받은 목적에만 씁니다. 이 방침은 {EFFECTIVE}부터 적용합니다.")
        + dk.section("1. 받는 정보와 쓰는 곳", table(
            ["언제", "받는 정보", "쓰는 곳"],
            [["글만 읽을 때", "블로그가 직접 받는 정보 없음", "—"],
             ["Google 로그인(댓글을 쓸 때)", "Google 계정 이름 · 프로필 사진 주소 · 이메일 주소 · 로그인 식별 번호", "댓글 작성자 표시, 본인 댓글 삭제, 같은 사람의 연속 등록 제한"],
             ["댓글을 쓸 때", "댓글 내용 · 작성 시각 · 마지막 댓글 시각", "댓글 표시, 댓글에 답글 달기, 짧은 시간 반복 등록(도배) 막기"],
             ["이메일로 문의할 때", "보낸 사람 이메일 주소 · 이름(적은 경우) · 메일 내용", "답장, 개인정보 · 권리 · 정정 요청 처리"]])
            + p("이메일 주소는 Google 로그인 서비스(Firebase 인증)에 저장될 뿐, 화면에 보이지 않고 댓글과 함께 저장하지 않습니다. "
                "댓글 작성자 이름 · 프로필 사진 · 댓글 내용은 <b>누구나 볼 수 있게 공개</b>됩니다."))
        + dk.section("2. 보관 기간과 지우기", ul([
            "댓글과 작성자 이름 · 사진은 작성자가 지울 때까지 보관합니다. 댓글 옆 삭제 버튼으로 언제든 직접 지울 수 있습니다.",
            "로그인 정보 삭제를 원하면 아래 연락처로 요청해 주세요. 확인 뒤 지체 없이 지웁니다.",
            "문의 메일은 답장과 요청 처리가 끝난 날부터 1년 동안 보관한 뒤 지웁니다. 같은 요청이 다시 올 때 확인하기 위해서입니다.",
            "법령에 따라 보관해야 하는 경우는 그 기간 동안만 보관합니다.",
        ]))
        + dk.section("3. 처리를 맡기는 곳 · 국외 이전", p(
            "블로그는 아래 업체의 서비스로 정보를 저장하고 처리합니다. 서버가 국외(주로 미국)에 있어, 댓글을 쓰는 시점에 인터넷으로 옮겨집니다.")
            + table(["업체(국가)", "옮기는 정보", "목적", "보관"],
                    [["Google LLC — Firebase(미국)", "로그인 정보, 댓글 내용 · 이름 · 사진", "로그인, 댓글 저장", "댓글 삭제 · 삭제 요청 때까지"],
                     ["Google LLC — Blogger(미국)", "블로그 방문 기록(Google 이 수집)", "블로그 운영 · 방문 통계", "Google 정책에 따름"],
                     ["NVIDIA · Groq · Google(미국)", "댓글 내용, 글 제목 (이름 · 사진 · 이메일은 보내지 않음)", "AI 로 댓글 답글 만들기", "블로그는 답글을 받은 뒤 보관하지 않음"],
                     ["Slack(미국)", "댓글 내용, 작성자 표시 이름", "운영자에게 새 댓글 알림", "운영자 알림 채널"],
                     ["Cloudflare, Inc. — 이메일 라우팅(미국)", "문의 메일(보낸 주소 · 내용)", "문의 주소로 온 메일을 운영자 메일함으로 전달", "저장하지 않고 전달만 함"],
                     ["네이버(한국)", "문의 메일(보낸 주소 · 내용)", "운영자 메일함 보관 · 답장", "처리 끝난 날부터 1년"]])
            + p("이용자는 댓글을 쓰지 않는 것으로 국외 이전을 거부할 수 있습니다. 이 경우 글을 읽는 데는 제한이 없고 댓글만 쓸 수 없습니다. "
                "문의 메일은 Cloudflare 를 거쳐 전달되므로, 원하지 않으면 이메일 대신 댓글로 남기거나 메일에 개인정보를 적지 않으셔도 됩니다."))
        + dk.section("4. 브라우저에 저장하는 것", p(
            "화면 설정(홈에서 미국 · 한국 중 무엇을 볼지, 장중 시세 켜기, 로그인 여부 표시)을 이용자 브라우저의 저장소(localStorage)에 남깁니다. "
            "이 값은 블로그 서버로 보내지 않으며, 브라우저의 사이트 데이터 삭제로 지울 수 있습니다."))
        + "".join(ads)
        + dk.section("5. 제3자 제공", p("법령에 따른 요청이 있는 경우를 빼고, 이용자의 개인정보를 제3자에게 팔거나 넘기지 않습니다."))
        + dk.section("6. 이용자의 권리", p(
            "이용자는 자기 개인정보를 보거나 고치거나 지우거나 처리를 멈춰 달라고 요청할 수 있습니다. 아래 연락처로 요청하면 지체 없이 처리합니다. "
            "만 14세 미만은 댓글을 쓰지 않도록 부탁드립니다."))
        + dk.section("7. 개인정보 보호 연락처", p(f"개인정보 관련 문의 · 요청: {mail()}")
            + p('개인정보 침해 상담은 개인정보침해신고센터(국번 없이 118, <a href="https://privacy.kisa.or.kr" rel="nofollow noopener" target="_blank">privacy.kisa.or.kr</a>), '
                '개인정보분쟁조정위원회(1833-6972, <a href="https://www.kopico.go.kr" rel="nofollow noopener" target="_blank">www.kopico.go.kr</a>)에서도 받을 수 있습니다.'))
        + dk.section("8. 방침이 바뀌면", p(f"내용이 바뀌면 이 페이지에 시행일과 함께 알립니다. 현재 시행일: {EFFECTIVE}."))
    )


# ── 문의 ─────────────────────────────────────────────────────────────
def contact():
    return wrap(
        #: 이메일은 누구나(비회원 포함) 보낼 수 있는 세 주제만 — 개인정보 · 권리 · 오류 정정.
        # 일반 의견 · 제안은 댓글, 개별 투자 상담은 회원이어도 받지 않음(유사투자자문 위험).
        lead(brand() + "는 개인정보 요청 · 권리 침해 · 내용 오류를 이메일로 받습니다. 회원이 아니어도 보낼 수 있습니다.")
        + dk.section("이메일", p(mail()) + p("보통 영업일 기준 3일 안에 답장합니다."))
        + dk.section("이메일로 받는 것", ul([
            "<b>개인정보</b> — 내 댓글 · 로그인 정보를 보거나 지워 달라는 요청 (<a href=\"/p/privacy.html\">개인정보처리방침</a>)",
            "<b>저작권 · 상표 · 권리 침해</b> — 권리자의 요청은 확인 뒤 바로 반영합니다.",
            "<b>사실 오류 · 정정 요청</b> — 페이지 주소와 틀린 부분을 함께 적어 주시면 빨리 고칠 수 있습니다.",
        ]))
        + dk.section("의견 · 제안은 댓글로", p(
            "보고 싶은 데이터, 불편한 화면, 글 내용에 대한 질문은 각 글 아래 댓글로 남겨 주세요. 다른 독자와 함께 보고 답합니다."))
        + dk.section("답하지 않는 것", p(
            "특정 종목을 사거나 팔아야 하는지, 내 계좌를 어떻게 할지 같은 <b>개별 투자 상담</b>에는 이메일 · 댓글 어디서도 답하지 않습니다. 투자 판단과 책임은 투자자 본인에게 있습니다."))
    )


PAGES = [("about", "Newfact 소개", about), ("privacy", "개인정보처리방침", privacy), ("contact", "문의", contact)]


def publish(dry=False):
    """고정 페이지 게시 — 주식 공부 목록(course/render_list.publish)과 같은 게시기(429 백오프 · 해시가 같으면 건너뜀)."""
    if not CONTACT_EMAIL:
        print("[사이트 페이지] 문의 이메일이 비어 있어 발행하지 않습니다 (CONTACT_EMAIL)")
        return False
    root = os.path.dirname(os.path.dirname(HERE))
    sys.path[:0] = [os.path.join(root, "experiments", "stock-radar"), os.path.join(root, "experiments", "daily-report"),
                    os.path.join(root, "experiments", "course")]
    import publish_course as PC
    import publish_pages as PP
    import universe as U
    PC._env()
    os.makedirs(OUT, exist_ok=True)
    tg = []
    for key, title, fn in PAGES:
        body = os.path.join(OUT, f"{key}_page.html")
        open(body, "w", encoding="utf-8").write(fn())
        tg.append((key, title, key, f"{U.BLOG}/p/{key}.html", body))
    PP.targets = lambda only=None: tg
    PP.HASHES = os.path.join(OUT, "page_hashes.json")
    PP.PAGES_LIVE = os.path.join(OUT, "pages_live.json")
    PP._body = lambda path: open(path, encoding="utf-8").read()
    return PP.publish(dry=dry)


def main():
    if "--publish" in sys.argv or "--dry" in sys.argv:
        sys.exit(0 if publish(dry="--dry" in sys.argv) else 1)
    os.makedirs(OUT, exist_ok=True)
    import re
    svg = re.search(r"<svg class='logo-full'.*?</svg>", open(os.path.join(HERE, "..", "..", "index.html"), encoding="utf-8").read(), re.S)
    tpl = f"<template data-nf-logo>{svg.group(0)}</template>" if svg else ""   # 목업엔 머리 줄 로고가 없어 본문 틀로(뉴스 글 목업과 같음)
    for key, title, fn in PAGES:
        path = dk.write_mock(fn() + (tpl if key == "about" else ""), os.path.join(OUT, f"mock_{key}.html"), title)
        print(f"[{title}] → {path}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
