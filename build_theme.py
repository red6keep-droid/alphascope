"""alphaflow-home.html (표준 미리보기) → index.html (Blogger 테마 XML) 생성.

디자인 CSS/마크업/JS 의 단일 출처는 alphaflow-home.html 이다.
디자인을 바꿀 때는 그 파일만 고치고 이 스크립트를 다시 돌린다.

    python build_theme.py

Blogger 전용 부분(위젯 선언, 뷰 분기, 글 보기·댓글 스타일)은 이 파일이 갖는다.
"""

import io
import re
import sys
import xml.etree.ElementTree as ET

# Windows 기본 콘솔(cp949)은 em dash 같은 문자를 못 찍어 죽는다.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

SOURCE = "alphaflow-home.html"
TARGET = "index.html"

# ---------------------------------------------------------------- 표준 파일에서 추출


def extract(src):
    """표준 파일에서 CSS / 대시보드 마크업 / JS 를 뽑아낸다."""

    def one(pattern, label):
        m = re.search(pattern, src, re.S)
        if not m:
            sys.exit(f"[build_theme] {label} 를 찾을 수 없습니다. {SOURCE} 구조가 바뀌었나요?")
        return m.group(1)

    css = one(r"<style>\n(.*?)\n</style>", "<style> 블록")
    js = one(r"<script>\n(.*?)\n</script>", "<script> 블록")
    dashboard = one(r'<main class="main-content">\n(.*?)\n</main>', "<main> 대시보드")
    breaking = one(r'(<div class="breaking">.*?</div>\n</div>)', "BREAKING 티커")
    footer = one(r"(<footer class=\"site-footer\">.*?</footer>)", "footer")

    # Blogger 테마는 XML 이므로 속성 구분자를 작은따옴표로 바꾼다.
    # (expr: 표현식 안에서 큰따옴표를 문자열 구분자로 쓰기 위함)
    def to_xml_attrs(html):
        return re.sub(r'(\s[a-zA-Z-]+)="([^"]*)"', r"\1='\2'", html)

    return {
        "css": css,
        "js": js,
        "dashboard": to_xml_attrs(dashboard),
        "breaking": to_xml_attrs(breaking),
        "footer": to_xml_attrs(footer),
    }


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


def main():
    src = io.open(SOURCE, encoding="utf-8").read()
    parts = extract(src)
    includables, n = blog_includables()

    out = TEMPLATE
    out = out.replace("__CSS__", parts["css"])
    out = out.replace("__BLOGGER_CSS__", BLOGGER_CSS.strip())
    out = out.replace("__NAV_ITEMS__", nav_items())
    out = out.replace("__DASHBOARD__", indent(parts["dashboard"], 6))
    out = out.replace("__BLOG_INCLUDABLES__", includables)
    out = out.replace("__BREAKING__", indent(parts["breaking"], 4))
    out = out.replace("__FOOTER_BLOCK__", indent(footer_with_attribution(parts["footer"]), 4))
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


if __name__ == "__main__":
    main()
