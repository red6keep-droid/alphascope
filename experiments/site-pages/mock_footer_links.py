"""푸터 링크 줄 목업 — 소개 · 개인정보처리방침 · 문의 (2026-11-21 사용자: 개인정보처리방침은 모든 화면에서 보여야 함).

    python experiments/site-pages/mock_footer_links.py   # → experiments/site-pages/output/mock_footer_links.html

푸터 CSS 는 테마(index.html)의 `6. footer` 구획을 그대로 읽어 쓴다 — 목업과 블로그가 어긋나지 않게.
새 규칙(링크 줄)만 이 파일의 NEW_CSS 에 있고, 확정되면 index.html · alphaflow-home.html 푸터에 같은 줄을 넣는다.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "output", "mock_footer_links.html")

# 링크 줄 — 13/19(가장 작은 글씨), 회색 #6B7280, 개인정보처리방침만 굵게 · 검정(개인정보위 작성지침: 다른 고지와 구분되게).
# 글자는 작아도 누르는 칸은 위아래 6 · 좌우 6 을 더해 높이 31(다른 작은 버튼과 같은 높이).
NEW_CSS = """
.footer-links { margin: 0 0 6px; font-size: 13px; line-height: 19px; text-align: center; color: #CBD5E1; }
.footer-links a { display: inline-block; padding: 6px 6px; color: #6B7280; text-decoration: none; -webkit-tap-highlight-color: transparent; }
.footer-links a:active { opacity: .55; }
.footer-links a.fl-privacy { color: #111; font-weight: 700; }
body.item-view .footer-links { margin: 5px 0 -6px; }   /* 상세 = 면책 줄 아래 11(5 + 글자 칸 6), 아래는 푸터 여백 19 그대로 */
"""

LINKS = ('<nav class="footer-links" aria-label="사이트 안내">'
         '<a href="/p/about.html">소개</a>·<a class="fl-privacy" href="/p/privacy.html">개인정보처리방침</a>·<a href="/p/contact.html">문의</a></nav>')

LEAD = ("뉴팩트 리포트는 공개된 시세 · SEC 공시 · FRED 경제 지표 · 뉴스를 정해진 규칙으로 정리한 기록이며, 투자를 권유하지 않습니다.")
MORE = ("<p>해설 문장 일부는 AI 가 씁니다. 모든 정보는 참고용이며, 앞으로의 결과는 지난 기록과 다를 수 있습니다. "
        "애널리스트 의견 · 목표가는 외부 의견을 옮긴 것입니다.</p>")
CHEV = ("<span class='footer-more' role='img' aria-label='더 보기'><svg viewBox='0 0 16 16' width='14' height='14' fill='none' stroke='currentColor' "
        "stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M4 6l4 4 4-4'/></svg></span>")


def theme_footer_css():
    s = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    a = s.index("6. footer")
    b = s.index("홈 카드 (2026-10-15", a)
    css = s[s.rfind("/*", 0, a):s.rfind("/*", 0, b)]
    root = re.search(r":root\s*\{.*?\n\}", s, re.S).group(0)
    return root + "\n" + css


def footer(item):
    return ("<footer class='site-footer'><details class='footer-disclaimer'><summary><span class='footer-title'>"
            "<span class='footer-name'>뉴팩트 주식 리포트</span>" + CHEV + "</span>"
            "<span class='footer-lead'>" + LEAD + "</span></summary>" + MORE + "</details>"
            + LINKS + "<p class='footer-copy'>© 2026 뉴팩트. All rights reserved.</p></footer>")


def phone(title, note, item):
    body_cls = "item-view" if item else "home-view"
    tail = ("<div class='endbar'>💬 댓글 · TOP</div>" if item else "<div class='card'>홈 마지막 카드</div>")
    return (f"<div class='col'><h2>{title}</h2><p class='note'>{note}</p>"
            f"<iframe srcdoc=\"{_doc(body_cls, tail + footer(item))}\"></iframe></div>")


def _doc(cls, inner):
    page = (f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}{NEW_CSS}"
            "body{margin:0;font-family:'Noto Sans KR',-apple-system,sans-serif;background:#fff;--gutter:14px;}"
            ".card{margin:16px 14px 16px;padding:24px;border:1px solid #E2E8F0;border-radius:12px;color:#94A3B8;font-size:14px;text-align:center;}"
            ".endbar{margin:0 14px 16px;padding:12px 0 20px;border-bottom:1px solid #E2E8F0;font-size:14px;color:#111;}"
            f"</style></head><body class='{cls}'>{inner}</body></html>")
    return page.replace("&", "&amp;").replace('"', "&quot;")


CSS = ""


def main():
    global CSS
    CSS = theme_footer_css()
    html = ("<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>푸터 링크 줄 목업</title><style>"
            "body{margin:0;padding:20px;font-family:-apple-system,'Noto Sans KR',sans-serif;background:#F3F4F6;color:#111;}"
            "h1{font-size:20px;margin:0 0 6px;} .lead{font-size:14px;color:#6B7280;margin:0 0 20px;line-height:1.6;}"
            ".wrap{display:flex;gap:24px;flex-wrap:wrap;} .col{width:390px;max-width:100%;}"
            "h2{font-size:16px;margin:0 0 4px;} .note{font-size:13px;color:#6B7280;margin:0 0 8px;line-height:1.5;}"
            "iframe{width:390px;max-width:100%;height:330px;border:1px solid #CBD5E1;border-radius:12px;background:#fff;}"
            "</style></head><body>"
            "<h1>푸터 링크 줄 — 소개 · 개인정보처리방침 · 문의</h1>"
            "<p class='lead'>모든 화면 푸터에 한 줄. 13/19 회색, 개인정보처리방침만 굵게 · 검정(법 작성지침: 다른 안내와 구분). "
            "누르는 칸 높이 31. 홈 · 목록 = 접힌 안내 아래 · 저작권 줄 위, 글 · 고정 페이지 = 면책 줄 아래(저작권 줄은 원래 없음).</p>"
            "<div class='wrap'>"
            + phone("홈 · 목록 화면", "면책 → 링크 줄 → 저작권", False)
            + phone("글 · 고정 페이지 (작은 푸터)", "면책 한 줄 → 링크 줄", True)
            + "</div></body></html>")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(html)
    print(OUT)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
