"""사이트 기본 페이지 3개 — 소개(/p/about.html) · 개인정보처리방침(/p/privacy.html) · 문의(/p/contact.html).
애드센스 신청 전 필수 페이지 (2026-11-16 사용자 "진행해줘", 계획 문서: alphascope-docs doc/기획/애드센스-신청-준비.md).

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
def about():
    return wrap(
        lead("뉴팩트는 미국 · 한국 주식시장의 공개 데이터를 정해진 규칙으로 계산해, 매일 기록으로 남기는 주식 데이터 리포트입니다.")
        + dk.section("무엇을 하나요", ul([
            "<b>증시 리포트</b> — 장이 끝나면 지수 · 금리 · 환율 · 업종 움직임과 그날의 주요 뉴스를 정리합니다.",
            "<b>종목 페이지</b> — 시가총액 상위 종목의 가격 흐름, 평소 움직임과의 비교, 공시, 함께 움직이는 종목을 한 화면에 모읍니다.",
            "<b>증시 전망</b> — 시장이 갈 수 있는 갈래와 그 근거를 적고, 정한 날에 맞았는지 다시 확인합니다.",
            "<b>Hot Issue</b> — 시장에 큰 사건이 있을 때 뉴스 흐름과 시장 반응을 함께 기록합니다.",
            "<b>주식 공부</b> — 주식에서 흔히 듣는 말을 실제 데이터로 확인해 봅니다.",
        ]))
        + dk.section("어떻게 만드나요", p(
            "공개된 시세 · 미국 SEC 공시 · 미국 연방준비은행(FRED) · 한국은행(ECOS) 경제 지표 · 뉴스를 모아, 미리 정한 계산 규칙으로 숫자를 만듭니다. "
            "같은 조건이면 누가 계산해도 같은 숫자가 나오도록 규칙을 공개된 말로 설명하려고 합니다. "
            "뉴스 분류 · 번역 · 해설 문장 일부는 AI 가 쓰며, 숫자 계산은 AI 가 하지 않습니다.")
            + p("지난 기록은 지우지 않습니다. 전망이 틀린 날도 그대로 남겨, 어떤 조건에서 맞고 틀렸는지 쌓아 가는 것이 목표입니다."))
        + dk.section("지키는 원칙", ul([
            "특정 종목의 매수 · 매도를 권유하지 않고, 개별 투자 상담을 하지 않습니다.",
            "모든 독자에게 같은 글을 보여 줍니다. 유료 회원 · 유료 정보가 없습니다.",
            "과거 기록은 조건과 표본 수를 함께 적고, 앞으로도 같다고 말하지 않습니다.",
            "외부 의견(애널리스트 의견 · 목표가 · 인물 발언)은 누구의 말인지 밝혀 옮깁니다.",
        ]))
        + dk.section("연락", p(f"오류 신고 · 개인정보 · 그 밖의 문의는 <a href=\"/p/contact.html\">문의 페이지</a>를 이용해 주세요."))
    )


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
        lead(f"뉴팩트(이하 '블로그')는 이용자의 개인정보를 필요한 만큼만 받고, 받은 목적에만 씁니다. 이 방침은 {EFFECTIVE}부터 적용합니다.")
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
        # 2026-11-16 사용자 결정: 이메일은 누구나(비회원 포함) 보낼 수 있는 세 주제만 — 개인정보 · 권리 · 오류 정정.
        # 일반 의견 · 제안은 댓글, 개별 투자 상담은 회원이어도 받지 않음(유사투자자문 위험).
        lead("뉴팩트는 개인정보 요청 · 권리 침해 · 내용 오류를 이메일로 받습니다. 회원이 아니어도 보낼 수 있습니다.")
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


PAGES = [("about", "소개", about), ("privacy", "개인정보처리방침", privacy), ("contact", "문의", contact)]


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
    for key, title, fn in PAGES:
        path = dk.write_mock(fn(), os.path.join(OUT, f"mock_{key}.html"), title)
        print(f"[{title}] → {path}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
