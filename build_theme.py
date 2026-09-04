"""alphaflow-home.html (표준 미리보기) → index.html / preview.html 생성.

디자인 CSS/마크업/JS 의 단일 출처는 alphaflow-home.html 이다.
디자인을 바꿀 때는 그 파일만 고치고 이 스크립트를 다시 돌린다.

    python build_theme.py              # index.html   — 블로거에 올리는 테마 XML
    python build_theme.py --preview    # preview.html — 브라우저로 여는 디자인 확인용

Blogger 전용 부분(위젯 선언, 뷰 분기, 글 보기·댓글 스타일)은 이 파일이 갖는다.
그 영역은 블로거에 올리기 전에는 눈으로 볼 수 없으므로, preview.html 이
같은 CSS 에 더미 콘텐츠를 채워 홈 / 목록 / 글 보기 세 화면을 보여준다.
네트워크 없이 동작하도록 시세·뉴스 fetch 는 고정 목업으로 가로챈다.
"""

import html as html_mod
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import quote

# Windows 기본 콘솔(cp949)은 em dash 같은 문자를 못 찍어 죽는다.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

SOURCE = "alphaflow-home.html"
TARGET = "index.html"
PREVIEW_TARGET = "preview.html"

# ---------------------------------------------------------------- 표준 파일에서 추출


def extract(src):
    """표준 파일에서 CSS / 마크업 / JS 를 원본 그대로 뽑아낸다."""

    def one(pattern, label):
        m = re.search(pattern, src, re.S)
        if not m:
            sys.exit(f"[build_theme] {label} 를 찾을 수 없습니다. {SOURCE} 구조가 바뀌었나요?")
        return m.group(1)

    return {
        "css": one(r"<style>\n(.*?)\n</style>", "<style> 블록"),
        "js": one(r"<script>\n(.*?)\n</script>", "<script> 블록"),
        "navbar": one(r'(<header class="navbar">.*?</header>)', "navbar"),
        "dashboard": one(r'<main class="main-content">\n(.*?)\n</main>', "<main> 대시보드"),
        "breaking": one(r'(<div class="breaking">.*?</div>\n</div>)', "BREAKING 티커"),
        "footer": one(r"(<footer class=\"site-footer\">.*?</footer>)", "footer"),
    }


def to_xml_attrs(html):
    """Blogger 테마는 XML 이므로 속성 구분자를 작은따옴표로 바꾼다.

    (expr: 표현식 안에서 큰따옴표를 문자열 구분자로 쓰기 위함)
    """
    return re.sub(r'(\s[a-zA-Z-]+)="([^"]*)"', r"\1='\2'", html)


# ------------------------------------------------------- Blogger 전용 추가 스타일

BLOGGER_CSS = """
/* ==========================================================================
   Blogger — 최신 리포트 카드 목록
   ========================================================================== */

.reports { display: flex; flex-direction: column; gap: 16px; }

.post-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
}

.post-card {
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  overflow: hidden;
  transition: box-shadow .18s ease, transform .18s ease;
}
.post-card:hover {
  box-shadow: 0 6px 24px rgba(15, 23, 42, .07);
  transform: translateY(-2px);
}

.post-card-img {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  background: linear-gradient(140deg, #16324F 0%, #26506F 55%, #3E7396 100%);
}

.post-card-body { display: flex; flex-direction: column; gap: 8px; padding: 18px 20px 20px; }
.post-card-meta {
  display: flex; align-items: center; gap: 8px;
  font-family: var(--num);
  font-size: 12px;
  color: var(--gray-400);
}
.post-card-title {
  margin: 0;
  font-weight: 700;
  font-size: 16px;
  line-height: 1.45;
  letter-spacing: -.3px;
  color: var(--ink);
}
.post-card-title a:hover { color: var(--accent); }
.post-card-snippet, .post-card-snippet p { margin: 0; font-size: 13px; line-height: 1.7; color: var(--gray-500); }

.blog-pager { display: flex; justify-content: center; gap: 12px; padding-top: 4px; }
.blog-pager a {
  padding: 10px 22px;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--ink);
}
.blog-pager a:hover { border-color: var(--accent); color: var(--accent); }

/* ==========================================================================
   Blogger — 글 보기
   ========================================================================== */

.post-shell { width: 100%; max-width: 860px; margin: 0 auto; }

.post-outer-container {
  padding: 40px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
}

.post-title {
  margin: 0 0 10px;
  font-weight: 700;
  font-size: 28px;
  line-height: 1.4;
  letter-spacing: -.6px;
  color: var(--ink);
}
.post-title a { color: inherit; }

/* 리포트 본문은 인라인 스타일을 갖고 있어 컨테이너만 잡아준다 */
.post-body { font-size: 15px; line-height: 1.8; color: #333; }
.post-body img { max-width: 100%; height: auto; border-radius: 12px; }
.post-body table { width: 100%; border-collapse: collapse; }
.post-body a { color: var(--down); }

.byline, .post-footer, .post-bottom, .post-labels {
  font-size: 12px;
  color: var(--gray-400);
}
.post-labels a {
  display: inline-block;
  margin: 6px 6px 0 0;
  padding: 3px 10px;
  background: var(--surface-sub);
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  color: var(--gray-600);
}
.jump-link { display: none; }

/* 댓글 */
.comments {
  width: 100%;
  max-width: 860px;
  margin: 20px auto 0;
  padding: 28px 40px 32px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
}
.comments h3, .comments .comments-title {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
}
.comments ol, .comments ul { list-style: none; padding: 0; margin: 0; }
.comments .comment { padding: 14px 0; border-bottom: 1px solid var(--border); }
.comments .comment:last-child { border-bottom: 0; }
.comments .comment-header .user, .comments .user a {
  font-size: 13px;
  font-weight: 700;
  color: var(--ink);
}
.comments .datetime, .comments .comment-header .datetime a {
  font-size: 12px;
  color: var(--gray-400);
}
.comments .comment-content { margin-top: 6px; font-size: 14px; line-height: 1.7; color: var(--gray-600); }
.comments .comment-actions a { margin-right: 10px; font-size: 12px; color: var(--gray-400); }
.comments .avatar-image-container img { width: 36px; height: 36px; border-radius: 50%; }
.comments iframe { width: 100%; border: 0; }
.comments .continue a, .comments .loadmore a {
  display: inline-block;
  margin-top: 12px;
  font-size: 13px;
  font-weight: 700;
  color: var(--accent);
}

/* 레이아웃 모드에서만 보이는 보관용 위젯 */
.hidden-widgets { display: none; }

/* 대시보드가 없는 뷰는 상단 여백을 조금 준다 */
body.no-dashboard .main-content { padding-top: 32px; }

@media (max-width: 900px) {
  .post-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .post-outer-container, .comments { padding: 24px; }
  .post-title { font-size: 22px; }
}
@media (max-width: 680px) {
  .post-grid { grid-template-columns: minmax(0, 1fr); }
}
"""

# ------------------------------------------------------------------ 테마 스켈레톤

TEMPLATE = """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE html>
<html b:css='false' b:defaultwidgetversion='2' b:layoutsVersion='3' b:responsive='true' b:templateUrl='indie.xml' b:templateVersion='1.3.3' expr:dir='data:blog.languageDirection' expr:lang='data:blog.locale' xmlns='http://www.w3.org/1999/xhtml' xmlns:b='http://www.google.com/2005/gml/b' xmlns:data='http://www.google.com/2005/gml/data' xmlns:expr='http://www.google.com/2005/gml/expr'>
  <head>
    <meta content='width=device-width, initial-scale=1' name='viewport'/>
    <title><data:view.title.escaped/></title>
    <b:include data='blog' name='all-head-content'/>
    <link href='https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;900&amp;family=Inter:wght@400;600;700;800&amp;display=swap' rel='stylesheet'/>

    <b:skin version='1.0'><![CDATA[/*
<Variable name="keycolor" description="Main Color" type="color" default="#FF3333" value="#FF3333"/>
<Group description="Page Text">
  <Variable name="body.text.color" description="Text color" type="color" default="#0F172A" value="#0F172A"/>
</Group>
<Group description="Backgrounds">
  <Variable name="body.background.color" description="Page background" type="color" default="#F9FAFB" value="#F9FAFB"/>
  <Variable name="posts.background.color" description="Card background" type="color" default="#FFFFFF" value="#FFFFFF"/>
</Group>
<Group description="Links">
  <Variable name="body.link.color" description="Link color" type="color" default="#FF3333" value="#FF3333"/>
</Group>
*/

__CSS__

__BLOGGER_CSS__
]]></b:skin>

    <b:template-skin><![CDATA[
      body#layout .navbar,
      body#layout .header-bar,
      body#layout .breaking,
      body#layout .site-footer { display: none; }
      body#layout .hidden-widgets { display: block; }
      body#layout .main-content { display: block; max-width: none; padding: 0; }
    ]]></b:template-skin>
  </head>

  <body>
    <b:class cond='data:view.isSingleItem' name='item-view'/>
    <b:class cond='data:view.isArchive' name='archive-view'/>
    <b:class cond='data:view.isLabelSearch' name='label-view'/>
    <b:class cond='!data:view.isHomepage' name='no-dashboard'/>

    <!-- =================================================================
         navbar
         ================================================================= -->
    <header class='navbar'>
      <div class='nav-left'>
        <b:section class='logo-holder' id='header' maxwidgets='1' name='Header' showaddelement='false'>
          <b:widget id='Header1' locked='true' title='AlphaFlow (Header)' type='Header' visible='true'>
            <b:includable id='main'>
              <a class='logo' expr:href='data:blog.homepageUrl'>
                <svg class='logo-mark' viewBox='0 0 36 33'>
                  <path d='M13.2 0H32.6L19.4 16.6H0L13.2 0Z' fill='#000000'/>
                  <path d='M17.7 15.2H35.5L22.3 32.4H4.5L17.7 15.2Z' fill='#DD0000'/>
                </svg>
                <span class='logo-word'>AlphaFlow</span>
              </a>
            </b:includable>
          </b:widget>
        </b:section>

        <button class='nav-toggle' type='button' aria-controls='primary-menu' aria-expanded='false'>
          <svg viewBox='0 0 24 24' width='20' height='20' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round'>
            <path d='M3 6h18M3 12h18M3 18h18'/>
          </svg>
          <span class='sr-only'>메뉴 열기</span>
        </button>

        <nav class='menu-items' id='primary-menu'>
          <a class='nav-item' expr:href='data:blog.homepageUrl'>
            <b:attr cond='data:view.isHomepage' name='aria-current' value='page'/>홈</a>
__NAV_ITEMS__
        </nav>
      </div>

      <div class='nav-right'>
        <b:section class='search-holder' id='search_top' maxwidgets='1' name='Search' showaddelement='false'>
          <b:widget id='BlogSearch1' locked='true' title='Search This Blog' type='BlogSearch' visible='true'>
            <b:includable id='main'>
              <form class='search-bar' expr:action='data:blog.searchUrl' method='get' role='search'>
                <svg viewBox='0 0 14 14' fill='none' stroke='currentColor' stroke-width='2'>
                  <circle cx='5.75' cy='5.75' r='4.5'/>
                  <path d='M9.3 9.3 12.8 12.8' stroke-linecap='round'/>
                </svg>
                <input aria-label='검색' autocomplete='off' name='q' placeholder='종목, 뉴스, 매크로 검색...' type='search' expr:value='data:view.search.query'/>
              </form>
            </b:includable>
          </b:widget>
        </b:section>

        <button class='icon-btn' type='button'>
          <svg viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>
            <path d='M18 8A6 6 0 1 0 6 8c0 7-3 9-3 9h18s-3-2-3-9'/>
            <path d='M13.7 21a2 2 0 0 1-3.4 0'/>
          </svg>
          <span class='sr-only'>알림</span>
        </button>

        <div class='avatar'></div>
      </div>
    </header>

    <div class='header-bar'></div>

    <main class='main-content'>
      <!-- 대시보드: 홈에서만 -->
      <b:if cond='data:view.isHomepage and !data:view.isLayoutMode'>
__DASHBOARD__
      </b:if>

      <!-- 게시글: 홈 하단의 최신 리포트 목록 / 글 보기 본문 -->
      <b:section class='page-body' id='page_body' name='Page Body' showaddelement='false'>
        <b:widget id='FeaturedPost1' locked='true' title='' type='FeaturedPost' visible='true'>
          <b:includable id='main'><b:comment>AlphaFlow 테마에서는 표시하지 않음</b:comment></b:includable>
        </b:widget>

        <b:widget id='Blog1' locked='true' title='Blog Posts' type='Blog' visible='true'>
          <b:includable id='main'>
            <b:if cond='data:view.isSingleItem'>
              <div class='post-shell'>
                <b:loop values='data:posts' var='post'>
                  <article class='post-outer-container'>
                    <b:include data='post' name='post'/>
                  </article>
                  <b:include data='post' name='commentPicker'/>
                </b:loop>
              </div>
            <b:else/>
              <section class='reports'>
                <div class='section-head'>
                  <h2 class='section-title'>
                    <b:if cond='data:view.isHomepage'>최신 리포트<b:else/><data:view.title.escaped/></b:if>
                  </h2>
                  <span class='section-note'>AI 자동 생성 · 매 거래일 06:00 KST</span>
                </div>
                <div class='post-grid'>
                  <b:loop values='data:posts' var='post'>
                    <article class='post-card'>
                      <a expr:href='data:post.url'>
                        <b:if cond='data:post.featuredImage'>
                          <img class='post-card-img' expr:alt='data:post.title' expr:src='data:post.featuredImage'/>
                        <b:else/>
                          <span class='post-card-img'></span>
                        </b:if>
                      </a>
                      <div class='post-card-body'>
                        <div class='post-card-meta'>
                          <b:eval expr='data:post.date format &quot;yyyy.MM.dd&quot;'/>
                        </div>
                        <h3 class='post-card-title'>
                          <a expr:href='data:post.url'><data:post.title/></a>
                        </h3>
                        <div class='post-card-snippet'>
                          <b:include data='post' name='postSnippet'/>
                        </div>
                      </div>
                    </article>
                  </b:loop>
                </div>
                <b:include name='postPagination'/>
              </section>
            </b:if>
          </b:includable>
__BLOG_INCLUDABLES__
        </b:widget>

        <b:widget id='PopularPosts1' locked='true' title='' type='PopularPosts' visible='true'>
          <b:includable id='main'><b:comment>AlphaFlow 테마에서는 표시하지 않음</b:comment></b:includable>
        </b:widget>
      </b:section>
    </main>

__BREAKING__

__FOOTER_BLOCK__

    <!-- =================================================================
         보관용 위젯 — 화면에는 나오지 않지만 레이아웃 모드에서 관리 가능
         ================================================================= -->
    <div class='hidden-widgets'>
      <b:section class='clearboth' id='page_list_top' name='Page List (Top)' showaddelement='false'>
        <b:widget id='PageList1' locked='true' title='' type='PageList' visible='true'>
          <b:includable id='main'><b:comment>상단 메뉴는 테마가 직접 렌더링함</b:comment></b:includable>
        </b:widget>
      </b:section>

      <b:section ads='true' id='ads' name='Ads' showaddelement='false'>
        <b:widget id='AdSense1' locked='true' title='' type='AdSense' visible='true'>
          <b:includable id='main'><b:comment>미사용</b:comment></b:includable>
        </b:widget>
        <b:widget id='AdSense2' locked='true' title='' type='AdSense' visible='true'>
          <b:includable id='main'><b:comment>미사용</b:comment></b:includable>
        </b:widget>
      </b:section>

      <b:section id='sidebar_top' name='Sidebar (Top)'>
        <b:widget id='Profile1' locked='true' title='About Me' type='Profile' visible='true'>
          <b:includable id='main'><b:comment>미사용</b:comment></b:includable>
        </b:widget>
      </b:section>

      <b:section id='sidebar_bottom' name='Sidebar (Bottom)' preferred='yes'>
        <b:widget id='BlogArchive1' locked='false' title='' type='BlogArchive' visible='true'>
          <b:includable id='main'><b:comment>미사용</b:comment></b:includable>
        </b:widget>
        <b:widget id='Label1' locked='false' title='Labels' type='Label' visible='true'>
          <b:includable id='main'><b:comment>미사용</b:comment></b:includable>
        </b:widget>
        <b:widget id='ReportAbuse1' locked='true' title='' type='ReportAbuse' visible='true'>
          <b:includable id='main'><b:comment>미사용</b:comment></b:includable>
        </b:widget>
      </b:section>
    </div>

    <script>
      //<![CDATA[
__JS__
      //]]>
    </script>
  </body>
</html>
"""

NAV_LABELS = ["시장", "섹터", "종목", "거시경제", "뉴스", "일정", "관심종목"]


def nav_items():
    out = []
    for label in NAV_LABELS:
        out.append(
            "          <a class='nav-item' expr:href='data:blog.homepageUrl + &quot;search/label/{0}&quot;'>\n"
            "            <b:attr cond='data:view.search.label == &quot;{0}&quot;' name='aria-current' value='page'/>{0}</a>".format(label)
        )
    return "\n".join(out)


def blog_includables(backup_path="index.indie-backup.html"):
    """기존 테마의 Blog1 위젯에서 main 이외의 includable 을 그대로 가져온다.

    글 렌더링(post/postBody/postFooter)과 댓글(comments/threadedComments) 로직은
    Blogger 가 검증한 기존 구현을 재사용하는 편이 안전하다.
    """
    src = io.open(backup_path, encoding="utf-8").read()
    m = re.search(
        r"<b:widget id='Blog1'.*?</b:widget>", src, re.S
    )
    if not m:
        sys.exit("[build_theme] 백업에서 Blog1 위젯을 찾을 수 없습니다.")
    widget = m.group(0)

    # main 은 새로 쓰므로 제외하고, 나머지 includable 만 추출
    blocks = re.findall(
        r"(<b:includable id='(?!main')[^>]*>.*?</b:includable>|<b:includable id='(?!main')[^>]*/>)",
        widget,
        re.S,
    )
    if len(blocks) < 20:
        sys.exit(f"[build_theme] Blog1 includable 추출이 부족합니다 ({len(blocks)}개).")
    return "\n".join("          " + b.strip() for b in blocks), len(blocks)


def indent(text, spaces):
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else line for line in text.split("\n"))


def build_theme(parts):
    """블로거에 붙여넣는 테마 XML 을 만든다."""
    includables, n = blog_includables()

    out = TEMPLATE
    out = out.replace("__CSS__", parts["css"])
    out = out.replace("__BLOGGER_CSS__", BLOGGER_CSS.strip())
    out = out.replace("__NAV_ITEMS__", nav_items())
    out = out.replace("__DASHBOARD__", indent(to_xml_attrs(parts["dashboard"]), 6))
    out = out.replace("__BLOG_INCLUDABLES__", includables)
    out = out.replace("__BREAKING__", indent(to_xml_attrs(parts["breaking"]), 4))
    out = out.replace(
        "__FOOTER_BLOCK__",
        indent(footer_with_attribution(to_xml_attrs(parts["footer"])), 4),
    )
    out = out.replace("__JS__", indent(parts["js"], 6))

    # 남은 플레이스홀더 확인
    left = re.findall(r"__[A-Z_]+__", out)
    if left:
        sys.exit(f"[build_theme] 치환되지 않은 플레이스홀더: {set(left)}")

    # XML 검증 (CDATA 안의 CSS/JS 는 파서가 통째로 넘긴다)
    try:
        ET.fromstring(out.split("<!DOCTYPE html>", 1)[1])
    except ET.ParseError as e:
        ln, col = e.position
        line = out.split("<!DOCTYPE html>", 1)[1].split("\n")[ln - 1]
        sys.exit(f"[build_theme] XML 오류 {e}\n  {line[max(0, col - 70):col + 70]!r}")

    io.open(TARGET, "w", encoding="utf-8", newline="\n").write(out)
    print(f"{TARGET} 생성 완료 — {out.count(chr(10)) + 1}줄, Blog1 includable {n}개 재사용, XML 검증 통과")


def footer_with_attribution(footer_html):
    """푸터 안에 Attribution1 위젯 섹션을 넣는다 (Blogger 필수 위젯)."""
    attribution = (
        "  <b:section class='attribution' id='footer' name='Footer' showaddelement='false' tag='div'>\n"
        "    <b:widget id='Attribution1' locked='true' title='' type='Attribution' visible='true'>\n"
        "      <b:widget-settings>\n"
        "        <b:widget-setting name='copyright'/>\n"
        "      </b:widget-settings>\n"
        "      <b:includable id='main' var='this'>\n"
        "        <p class='footer-copy'>\n"
        "          <b:if cond='data:copyright != &quot;&quot;'>\n"
        "            <data:copyright/>\n"
        "          <b:else/>\n"
        "            © 2026 ALPHAFLOW. All rights reserved.\n"
        "          </b:if>\n"
        "        </p>\n"
        "      </b:includable>\n"
        "    </b:widget>\n"
        "  </b:section>\n"
    )
    # 기존 정적 copyright 문단을 Attribution 위젯으로 교체
    return re.sub(
        r"  <p class='footer-copy'>.*?</p>\n",
        attribution,
        footer_html,
        flags=re.S,
    )



# ==========================================================================
#  preview.html — 브라우저로 여는 디자인 확인용
# ==========================================================================
#
#  index.html 은 블로거 XML 이라 브라우저가 <b:widget> 을 렌더링하지 못한다.
#  그래서 같은 CSS 에 더미 콘텐츠를 채운 평범한 HTML 을 따로 뽑는다.
#  확인 대상은 배치·여백·크기이므로 데이터는 전부 고정 목업이다.

PREVIEW_CSS = """
/* ==========================================================================
   preview.html 전용 — 테마(index.html)에는 들어가지 않는다
   ========================================================================== */

/* 뷰 전환: 홈 / 목록 / 글 보기 */
body[data-pv-view="home"] #pv-post { display: none; }
body[data-pv-view="list"] #pv-dashboard,
body[data-pv-view="list"] #pv-post { display: none; }
body[data-pv-view="post"] #pv-dashboard,
body[data-pv-view="post"] #pv-reports { display: none; }

.pv-bar {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 9999;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 8px;
  background: rgba(15, 23, 42, .93);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, .28);
  font: 500 12px/1 system-ui, -apple-system, 'Segoe UI', sans-serif;
  color: #E2E8F0;
}
.pv-bar-label { padding: 0 4px; font-size: 10px; font-weight: 700; letter-spacing: 1px; color: #64748B; }
.pv-bar button {
  padding: 6px 11px;
  background: transparent;
  border: 1px solid rgba(226, 232, 240, .22);
  border-radius: 6px;
  font: inherit;
  color: #E2E8F0;
  cursor: pointer;
}
.pv-bar button:hover { border-color: rgba(226, 232, 240, .55); }
.pv-bar button[aria-pressed="true"] { background: #FFFFFF; border-color: #FFFFFF; color: #0F172A; }
.pv-bar-w {
  min-width: 54px;
  padding-left: 4px;
  font-variant-numeric: tabular-nums;
  text-align: right;
  color: #94A3B8;
}
@media print { .pv-bar { display: none; } }
"""


def _svg_data_uri(top, bottom):
    """오프라인에서도 뜨는 인라인 SVG 커버.

    실제 커버 이미지와 같은 1024x400 비율이라 카드에서 잘리는 정도까지 볼 수 있다.
    """
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1024 400'>"
        "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0' stop-color='{0}'/><stop offset='1' stop-color='{1}'/>"
        "</linearGradient></defs>"
        "<rect width='1024' height='400' fill='url(#g)'/>"
        "<circle cx='838' cy='96' r='150' fill='#FFFFFF' opacity='.14'/>"
        "<circle cx='150' cy='330' r='96' fill='#FFFFFF' opacity='.10'/>"
        "<path d='M0 300 L205 244 L400 286 L620 178 L822 232 L1024 148' fill='none' "
        "stroke='#FFFFFF' stroke-width='11' stroke-linecap='round' stroke-linejoin='round' "
        "opacity='.55'/>"
        "</svg>"
    ).format(top, bottom)
    return "data:image/svg+xml," + quote(svg, safe="")


def _avatar_data_uri(fill):
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 36 36'>"
        "<rect width='36' height='36' fill='{0}'/>"
        "<circle cx='18' cy='14' r='6' fill='#FFFFFF' opacity='.85'/>"
        "<path d='M6 36c0-7 5.4-11 12-11s12 4 12 11z' fill='#FFFFFF' opacity='.85'/>"
        "</svg>"
    ).format(fill)
    return "data:image/svg+xml," + quote(svg, safe="")


# 카드가 깨지기 쉬운 경우를 일부러 섞었다.
# 긴 제목(줄바꿈) / 커버 없는 글(그라데이션 대체) / 짧은 스니펫.
PREVIEW_POSTS = [
    {
        "date": "2026.09.03",
        "title": "미국 증시 데일리 브리핑 — 나스닥 사상 최고치 경신, 반도체와 소프트웨어가 함께 끌어올린 하루",
        "snippet": "3대 지수가 모두 상승 마감했습니다. 나스닥은 1.4% 오르며 사상 최고치를 다시 썼고, "
                   "반도체 섹터가 지수 상승분의 절반 이상을 설명했습니다.",
        "cover": ("#2563EB", "#7DD3FC"),
    },
    {
        "date": "2026.09.02",
        "title": "연준 의사록 공개 앞두고 관망세, 러셀 2000만 나 홀로 약세",
        "snippet": "중소형주 지수가 0.6% 밀리며 대형주와 온도차를 보였습니다. 금리 민감도가 높은 종목군에서 "
                   "차익 실현 물량이 나왔습니다.",
        "cover": ("#0EA5E9", "#A7F3D0"),
    },
    {
        "date": "2026.09.01",
        "title": "9월 첫 거래일, 에너지 섹터 반등",
        "snippet": "유가가 배럴당 3% 오르며 에너지 섹터가 시장을 앞섰습니다.",
        "cover": None,  # 커버 이미지가 없는 글 — .post-card-img 그라데이션 대체 확인용
    },
    {
        "date": "2026.08.29",
        "title": "8월 마지막 거래일 요약과 9월 관전 포인트",
        "snippet": "8월 한 달간 S&P 500은 2.8% 상승했습니다. 9월에는 고용지표와 CPI 발표가 몰려 있어 "
                   "변동성이 커질 수 있습니다. 특히 둘째 주에 이벤트가 집중됩니다.",
        "cover": ("#6366F1", "#FBCFE8"),
    },
    {
        "date": "2026.08.28",
        "title": "빅테크 실적 시즌 마무리, 가이던스는 엇갈렸다",
        "snippet": "클라우드 매출 성장률이 시장 기대를 웃돈 반면, 광고 부문 전망은 보수적이었습니다.",
        "cover": ("#F59E0B", "#FDE68A"),
    },
    {
        "date": "2026.08.27",
        "title": "VIX 15선 회복, 위험 선호 심리 재점화",
        "snippet": "변동성 지수가 다시 15선을 회복하며 위험 자산 선호가 살아났습니다.",
        "cover": ("#14B8A6", "#BAE6FD"),
    },
]

PREVIEW_COMMENTS = [
    {
        "author": "김투자",
        "when": "2026년 9월 3일 오전 9:12",
        "body": "반도체 비중 확대 의견 잘 봤습니다. 다만 밸류에이션 부담은 어떻게 보시나요?",
        "avatar": "#2563EB",
        "reply": None,
    },
    {
        "author": "AlphaFlow",
        "when": "2026년 9월 3일 오전 10:04",
        "body": "선행 PER 기준으로는 5년 평균을 웃돌지만, 실적 상향 속도가 더 빨라 부담이 완화되는 구간으로 "
                "보고 있습니다. 다만 가이던스가 꺾이면 되돌림이 클 수 있어 분할 접근을 권합니다.",
        "avatar": "#DD0000",
        "reply": True,
    },
    {
        "author": "장기보유",
        "when": "2026년 9월 3일 오후 2:47",
        "body": "매일 잘 보고 있습니다. 러셀 2000 지표도 같이 실어주시면 좋겠어요.",
        "avatar": "#14B8A6",
        "reply": None,
    },
]

PREVIEW_POST_TITLE = "미국 증시 데일리 브리핑 — 2026년 9월 3일"

FALLBACK_POST_BODY = """<div style="font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;font-size:15px;line-height:1.7;color:#333;">

  <img src="__COVER__" alt="데일리 브리핑 커버 이미지" style="width:100%;max-width:760px;border-radius:8px;margin:0 0 16px 0;display:block;"/>

  <h2 style="color:#111;border-bottom:2px solid #eee;padding-bottom:8px;">오늘의 시장 요약</h2>
  <div><div>오늘 미국 증시는 3대 지수가 일제히 상승 마감했습니다. 반도체 섹터가 상승을 주도한 가운데
  소프트웨어와 온라인 서비스가 뒤를 받쳤고, 변동성 지수는 15선 아래에서 안정적인 흐름을 유지했습니다.</div></div>

  <h2 style="color:#111;border-bottom:2px solid #eee;padding-bottom:8px;">주요 지수</h2>
  <table style="width:100%;border-collapse:collapse;margin:8px 0;font-size:14px;">
    <tr style="background:#f5f5f5;">
      <th style="padding:8px;border:1px solid #ddd;text-align:left;">지수</th>
      <th style="padding:8px;border:1px solid #ddd;text-align:right;">종가</th>
      <th style="padding:8px;border:1px solid #ddd;text-align:right;">등락률</th>
    </tr>
    <tr>
      <td style="padding:8px;border:1px solid #ddd;">S&amp;P 500</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;">7,747.71</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;"><span style="color:#d93025;">+1.06%</span></td>
    </tr>
    <tr>
      <td style="padding:8px;border:1px solid #ddd;">Nasdaq</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;">26,584.06</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;"><span style="color:#d93025;">+1.40%</span></td>
    </tr>
    <tr>
      <td style="padding:8px;border:1px solid #ddd;">Russell 2000</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;">2,968.27</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;"><span style="color:#1a73e8;">-0.24%</span></td>
    </tr>
  </table>

  <h2 style="color:#111;border-bottom:2px solid #eee;padding-bottom:8px;">주요 뉴스</h2>
  <ul>
    <li><a href="#" style="color:#1a73e8;">반도체 ETF에 사상 최대 자금 유입</a> — CNBC</li>
    <li><a href="#" style="color:#1a73e8;">연준 위원 "금리 인하 서두를 필요 없다"</a> — Reuters</li>
  </ul>

  <p style="margin-top:24px;font-size:12px;color:#999;border-top:1px solid #eee;padding-top:10px;">
    본 리포트는 데이터 수집(FRED · Yahoo Finance)과 AI 분석(Gemini)을 자동으로 결합해 생성한 테스트 산출물입니다.
    투자 판단의 근거로 활용하지 마십시오. 데이터 출처: FRED, Yahoo Finance, CNBC.<br/>
    기준일: 2026-09-03 · 데이터 갱신: 2026-09-03 21:05 KST
  </p>

</div>"""

SAVED_POST_BODY = "experiments/daily-report/output/report_body.html"


def preview_post_body():
    """실제로 생성된 리포트 본문이 로컬에 있으면 그걸 쓰고, 없으면 더미로 대체한다.

    output/ 은 gitignore 대상이라 다른 환경에서는 없는 게 정상이다.
    """
    try:
        body = io.open(SAVED_POST_BODY, encoding="utf-8").read().strip()
        return body, f"실제 리포트 본문({SAVED_POST_BODY})"
    except OSError:
        cover = _svg_data_uri("#2563EB", "#7DD3FC")
        return FALLBACK_POST_BODY.replace("__COVER__", cover), "더미 본문"


def preview_reports():
    """홈 하단·라벨 목록에 쓰이는 글 카드 그리드."""
    cards = []
    for post in PREVIEW_POSTS:
        title = html_mod.escape(post["title"], quote=False)
        if post["cover"]:
            thumb = (
                "<img class=\"post-card-img\" src=\"%s\" alt=\"%s\"/>"
                % (_svg_data_uri(*post["cover"]), html_mod.escape(post["title"]))
            )
        else:
            thumb = "<span class=\"post-card-img\"></span>"

        cards.append(
            "      <article class=\"post-card\">\n"
            "        <a href=\"#\">%s</a>\n"
            "        <div class=\"post-card-body\">\n"
            "          <div class=\"post-card-meta\">%s</div>\n"
            "          <h3 class=\"post-card-title\"><a href=\"#\">%s</a></h3>\n"
            "          <div class=\"post-card-snippet\"><p>%s</p></div>\n"
            "        </div>\n"
            "      </article>"
            % (thumb, post["date"], title, html_mod.escape(post["snippet"], quote=False))
        )

    return (
        "  <section class=\"reports\" id=\"pv-reports\">\n"
        "    <div class=\"section-head\">\n"
        "      <h2 class=\"section-title\" id=\"pv-reports-title\">최신 리포트</h2>\n"
        "      <span class=\"section-note\">AI 자동 생성 · 매 거래일 06:00 KST</span>\n"
        "    </div>\n"
        "    <div class=\"post-grid\">\n"
        + "\n".join(cards) + "\n"
        "    </div>\n"
        "    <div class=\"blog-pager\">\n"
        "      <a href=\"#\">이전 게시물</a>\n"
        "      <a href=\"#\">홈</a>\n"
        "    </div>\n"
        "  </section>"
    )


def preview_comments():
    items = []
    for c in PREVIEW_COMMENTS:
        items.append(
            "          <li class=\"comment%s\">\n"
            "            <div class=\"avatar-image-container\"><img src=\"%s\" alt=\"\"/></div>\n"
            "            <div class=\"comment-block\">\n"
            "              <div class=\"comment-header\">\n"
            "                <cite class=\"user\">%s</cite>\n"
            "                <span class=\"datetime\"><a href=\"#\">%s</a></span>\n"
            "              </div>\n"
            "              <p class=\"comment-content\">%s</p>\n"
            "              <div class=\"comment-actions\">\n"
            "                <a href=\"#\">답글</a><a href=\"#\">삭제</a>\n"
            "              </div>\n"
            "            </div>\n"
            "          </li>"
            % (
                " comment-reply" if c["reply"] else "",
                _avatar_data_uri(c["avatar"]),
                html_mod.escape(c["author"], quote=False),
                c["when"],
                html_mod.escape(c["body"], quote=False),
            )
        )

    return (
        "      <div class=\"comments\">\n"
        "        <h3 class=\"comments-title\">댓글 %d</h3>\n"
        "        <ol>\n"
        % len(PREVIEW_COMMENTS)
        + "\n".join(items) + "\n"
        "        </ol>\n"
        "        <div class=\"continue\"><a href=\"#\">댓글 쓰기</a></div>\n"
        "      </div>"
    )


def preview_post():
    body, _ = preview_post_body()
    return (
        "  <div id=\"pv-post\">\n"
        "    <div class=\"post-shell\">\n"
        "      <article class=\"post-outer-container\">\n"
        "        <div class=\"post\">\n"
        "          <h3 class=\"post-title entry-title\">%s</h3>\n"
        "          <div class=\"byline post-author vcard\">글쓴이 <span class=\"fn\">AlphaFlow</span></div>\n"
        "          <div class=\"byline post-timestamp\">2026년 9월 3일 오전 6:00</div>\n"
        "          <div class=\"post-body entry-content float-container\">\n"
        "%s\n"
        "          </div>\n"
        "          <div class=\"post-bottom\">\n"
        "            <div class=\"post-footer float-container\">\n"
        "              <div class=\"post-labels\">라벨:\n"
        "                <a href=\"#\">시장</a><a href=\"#\">거시경제</a><a href=\"#\">종목</a>\n"
        "              </div>\n"
        "            </div>\n"
        "          </div>\n"
        "        </div>\n"
        "      </article>\n"
        "%s\n"
        "    </div>\n"
        "  </div>"
        % (html_mod.escape(PREVIEW_POST_TITLE, quote=False), indent(body, 12), preview_comments())
    )


# ------------------------------------------------------------- 목업 시세·뉴스

MOCK_INDICES = [
    {"s": "^GSPC", "name": "S&P 500", "p": 7747.71, "c": 81.11, "cp": 1.06,
     "prev": 7666.60, "dh": 7756.76, "dl": 7686.71, "yh": 7816.70, "yl": 6316.91, "st": "장마감"},
    {"s": "^IXIC", "name": "나스닥 종합", "p": 26584.06, "c": 366.23, "cp": 1.40,
     "prev": 26217.83, "dh": 26644.57, "dl": 26325.06, "yh": 27190.21, "yl": 20690.25, "st": "장마감"},
    {"s": "^DJI", "name": "다우존스", "p": 53061.95, "c": -624.16, "cp": -1.16,
     "prev": 53686.11, "dh": 53700.02, "dl": 52918.44, "yh": 54744.33, "yl": 45057.28, "st": "장마감"},
    {"s": "^RUT", "name": "러셀 2000", "p": 2953.17, "c": -15.10, "cp": -0.51,
     "prev": 2968.27, "dh": 2976.62, "dl": 2941.08, "yh": 3069.71, "yl": 2303.46, "st": "장마감"},
]

# (티커, 가격, 등락률, 거래량) — 상승·하락과 거래량 편차를 섞어 정렬 탭까지 확인한다.
_MOCK_ROWS = [
    ("AAPL", 328.21, 1.62, 53370900),
    ("MSFT", 510.12, 0.84, 21044300),
    ("NVDA", 228.45, 3.71, 198442100),
    ("AMZN", 258.90, -0.42, 38122700),
    ("GOOGL", 342.48, 1.05, 26890400),
    ("META", 610.68, -1.87, 15330800),
    ("TSLA", 376.37, 4.26, 112905600),
    ("BRK-B", 508.13, 0.11, 3204100),
    ("AVGO", 357.16, 2.94, 29771200),
    ("JPM", 362.06, -0.73, 9880500),
]

MOCK_STOCKS = [
    {"s": t, "p": p, "c": round(p * cp / (100 + cp), 2), "cp": cp, "v": v, "n": 26, "candles": []}
    for t, p, cp, v in _MOCK_ROWS
]

MOCK_NEWS = [
    {"title": "Semiconductor ETFs see record inflows as AI capex guidance climbs",
     "summary": "Investors poured a record $4.1 billion into chip-focused funds last week, "
                "betting that AI infrastructure spending has further to run.",
     "source": "CNBC", "published": "2026-09-03 20:41:00", "link": "#"},
    {"title": "Fed official says there is no rush to cut rates further",
     "summary": "The policymaker pointed to resilient consumer spending.",
     "source": "Reuters", "published": "2026-09-03 19:55:00", "link": "#"},
    {"title": "Oil steadies near $74 after inventory draw",
     "summary": "Crude held gains following a larger-than-expected drawdown.",
     "source": "Bloomberg", "published": "2026-09-03 18:30:00", "link": "#"},
    {"title": "Retail earnings point to a resilient but value-seeking consumer",
     "summary": "Discount chains outperformed department stores again this quarter.",
     "source": "CNBC", "published": "2026-09-03 17:12:00", "link": "#"},
    {"title": "Treasury yields slip as August jobs report comes into focus",
     "summary": "The 10-year yield eased three basis points ahead of Friday's payrolls print.",
     "source": "MarketWatch", "published": "2026-09-03 16:04:00", "link": "#"},
    {"title": "Dollar weakens against the yen for a third straight session",
     "summary": "Traders trimmed long dollar positions.",
     "source": "Reuters", "published": "2026-09-03 15:20:00", "link": "#"},
    {"title": "Housing starts beat forecasts but permits signal a slowdown ahead",
     "summary": "Single-family permits fell for a second month.",
     "source": "Bloomberg", "published": "2026-09-03 14:02:00", "link": "#"},
    {"title": "Gold holds near record as central bank buying continues",
     "summary": "Official sector demand remains the dominant bid.",
     "source": "CNBC", "published": "2026-09-03 13:15:00", "link": "#"},
]


def preview_mock_js():
    """fetch 를 가로채 고정 데이터를 돌려준다. 네트워크도 서버도 필요 없다."""
    data = {
        "updated_at": "2026-09-03 20:45:00 UTC",
        "interval": "15m",
        "indices": MOCK_INDICES,
        "stocks": MOCK_STOCKS,
    }
    news = {"updated_at": "2026-09-03 20:41:00 UTC", "items": MOCK_NEWS}

    return (
        "  var PV_DATA = %s;\n"
        "  var PV_NEWS = %s;\n"
        "\n"
        "  /* 디자인만 확인하므로 실제 시세를 부르지 않는다. */\n"
        "  window.fetch = function (url) {\n"
        "    var body = String(url).indexOf('news.json') >= 0 ? PV_NEWS : PV_DATA;\n"
        "    return Promise.resolve({ json: function () { return Promise.resolve(body); } });\n"
        "  };"
        % (
            json.dumps(data, ensure_ascii=False),
            json.dumps(news, ensure_ascii=False),
        )
    )


PREVIEW_SWITCH_JS = """  (function () {
    var body = document.body;
    var buttons = document.querySelectorAll('.pv-bar button');
    var reportsTitle = document.getElementById('pv-reports-title');
    var homeLink = document.querySelector('.menu-items .nav-item');

    /* 테마는 홈이 아닌 뷰에 no-dashboard 를 붙인다 (b:class cond=!isHomepage). */
    function setView(view) {
      body.setAttribute('data-pv-view', view);
      body.classList.toggle('no-dashboard', view !== 'home');
      if (reportsTitle) reportsTitle.textContent = (view === 'list') ? '시장' : '최신 리포트';
      /* 메뉴의 현재 위치 표시도 뷰를 따라간다 (테마의 b:attr aria-current 흉내). */
      if (homeLink) {
        if (view === 'home') homeLink.setAttribute('aria-current', 'page');
        else homeLink.removeAttribute('aria-current');
      }
      Array.prototype.forEach.call(buttons, function (b) {
        b.setAttribute('aria-pressed', String(b.getAttribute('data-pv-view') === view));
      });
      try { sessionStorage.setItem('pv-view', view); } catch (e) {}
    }

    Array.prototype.forEach.call(buttons, function (b) {
      b.addEventListener('click', function () {
        var view = b.getAttribute('data-pv-view');
        location.hash = view;
        setView(view);
      });
    });

    /* preview.html#post 처럼 주소로 바로 열 수도 있다. */
    var VIEWS = ['home', 'list', 'post'];
    function fromHash() {
      var v = String(location.hash || '').replace('#', '');
      return VIEWS.indexOf(v) >= 0 ? v : null;
    }
    window.addEventListener('hashchange', function () {
      var v = fromHash();
      if (v) setView(v);
    });

    var saved = null;
    try { saved = sessionStorage.getItem('pv-view'); } catch (e) {}
    setView(fromHash() || saved || 'home');

    /* 브레이크포인트(1360 / 1180 / 900 / 680) 확인용 폭 표시 */
    var readout = document.getElementById('pv-width');
    function showWidth() { readout.textContent = window.innerWidth + 'px'; }
    window.addEventListener('resize', showWidth);
    showWidth();
  })();"""


PREVIEW_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>AlphaFlow — 디자인 미리보기</title>
<!-- build_theme.py --preview 가 생성한 파일입니다. 직접 고치지 마십시오.
     디자인은 alphaflow-home.html, 블로거 전용 영역은 build_theme.py 에서 고칩니다. -->
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;900&amp;family=Inter:wght@400;600;700;800&amp;display=swap" rel="stylesheet"/>
<style>
__CSS__

__BLOGGER_CSS__

__PREVIEW_CSS__
</style>
</head>
<body data-pv-view="home">

__NAVBAR__

<div class="header-bar"></div>

<main class="main-content">
  <div id="pv-dashboard">
__DASHBOARD__
  </div>

__REPORTS__

__POST__
</main>

__BREAKING__

__FOOTER__

<div class="pv-bar" role="group" aria-label="미리보기 화면 전환">
  <span class="pv-bar-label">PREVIEW</span>
  <button type="button" data-pv-view="home" aria-pressed="true">홈</button>
  <button type="button" data-pv-view="list">목록</button>
  <button type="button" data-pv-view="post">글 보기</button>
  <span class="pv-bar-w" id="pv-width">—</span>
</div>

<script>
(function () {
  'use strict';
__MOCK__
})();
</script>

<script>
__JS__
</script>

<script>
__SWITCH__
</script>
</body>
</html>
"""


def build_preview(parts):
    """브라우저로 여는 디자인 확인용 HTML 을 만든다."""
    _, body_source = preview_post_body()

    out = PREVIEW_TEMPLATE
    out = out.replace("__CSS__", parts["css"])
    out = out.replace("__BLOGGER_CSS__", BLOGGER_CSS.strip())
    out = out.replace("__PREVIEW_CSS__", PREVIEW_CSS.strip())
    out = out.replace("__NAVBAR__", parts["navbar"])
    out = out.replace("__DASHBOARD__", indent(parts["dashboard"], 2))
    out = out.replace("__REPORTS__", preview_reports())
    out = out.replace("__POST__", preview_post())
    out = out.replace("__BREAKING__", parts["breaking"])
    out = out.replace("__FOOTER__", parts["footer"])
    out = out.replace("__MOCK__", preview_mock_js())
    out = out.replace("__JS__", parts["js"])
    out = out.replace("__SWITCH__", PREVIEW_SWITCH_JS)

    left = re.findall(r"__[A-Z_]+__", out)
    if left:
        sys.exit(f"[build_theme] 치환되지 않은 플레이스홀더: {set(left)}")

    io.open(PREVIEW_TARGET, "w", encoding="utf-8", newline="\n").write(out)
    print(
        f"{PREVIEW_TARGET} 생성 완료 — {out.count(chr(10)) + 1}줄, "
        f"글 카드 {len(PREVIEW_POSTS)}개 · 댓글 {len(PREVIEW_COMMENTS)}개, {body_source}"
    )
    print("  브라우저로 열어 홈 / 목록 / 글 보기 를 전환하며 확인하십시오.")


def main():
    parts = extract(io.open(SOURCE, encoding="utf-8").read())
    if "--preview" in sys.argv[1:]:
        build_preview(parts)
    else:
        build_theme(parts)


if __name__ == "__main__":
    main()
