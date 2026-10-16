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
  font-size: 14px;
  color: var(--gray-400);
}
.post-card-title {
  margin: 0;
  font-weight: 700;
  font-size: 20px;   /* 목록 카드 제목 +1 (2026-10-13) */
  line-height: 1.45;
  letter-spacing: -.3px;
  color: var(--ink);
}
.post-card-title a:hover { color: var(--accent); }
.post-card-snippet, .post-card-snippet p { margin: 0; font-size: 16px; line-height: 1.7; color: var(--gray-500); }
/* 목록 카드 요약 (2026-10-13 사용자): 테마 JS가 홈 카드와 같은 2줄 요약(.report-columns)으로 바꾼다. 바꾸기 전 · 실패 시 블로거 기본 요약은 2줄에서 자른다 */
.post-card-snippet:not(.report-columns) { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; }

.blog-pager { display: flex; justify-content: center; gap: 12px; padding-top: 4px; }
/* 글 더 보기 — 목록 버튼과 같은 검은 테마 버튼, 가로 30% 넓게 (2026-10-13 사용자: "모든 하단 버튼은 블랙 테마 버튼") */
.blog-pager a {
  padding: 12px 42px;
  background: #111;
  border: 1px solid #111;
  border-radius: 8px;
  font-size: 16px;
  line-height: 24px;
  font-weight: 700;
  color: #fff;
}
.blog-pager a:hover { background: #000; color: #fff; }

/* ==========================================================================
   Blogger — 글 보기
   ========================================================================== */

/* main-content 는 border-box 라 좌우 gutter 가 안쪽 폭을 그만큼 깎는다. gutter 를 더해 콘텐츠 폭이 정확히 --shell(980).
   2026-10-15 부터 홈 · 목록도 테마 .main-content 가 같은 식이라 이 줄은 글 보기용 중복 (지워도 같다) */
body.item-view .main-content { max-width: calc(var(--shell) + var(--gutter) * 2); }

.post-shell { width: 100%; max-width: var(--shell); margin: 0 auto; min-width: 0; }

.post-outer-container {
  padding: 40px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
}

.post-title {
  margin: 0 0 10px;
  font-weight: 700;
  font-size: 35px;   /* 제목 +1 (2026-10-13 사용자: "타이틀 사이즈도 1포인트 크게") */
  line-height: 48px;
  letter-spacing: -.6px;
  color: var(--ink);
}
.post-title a { color: inherit; }
.post-title .title-logo { width: 32px; height: 32px; border-radius: 8px; margin-right: 5px; vertical-align: -5px; background: #F1F5F9; }   /* 엔비디아 리포트 제목 앞 티커 로고 (2026-10-13 사용자) */
@media (max-width: 680px) { .post-title .title-logo { width: 26px; height: 26px; vertical-align: -4px; } }
/* 글 제목 끝의 " — 날짜"는 16px, 볼드 없이 — 모든 리포트·모든 화면 폭 (2026-10-12 사용자). 테마 JS가 span.post-title-date 로 감싼다 */
.post-title .post-title-date, .post-card-title .post-title-date { font-size: 16px; font-weight: 400; white-space: nowrap; }
.post-title .post-title-date { font-size: 14px; }   /* 글 보기 제목 옆 날짜 = 홈 리포트 제목 옆 날짜(.report-card-date) 14px (2026-10-13 사용자) */
/* 글 보기 제목: 날짜 줄 오른쪽 끝에 공유 아이콘 버튼 (2026-10-12 사용자) — 테마 JS가 날짜 + 버튼을 .post-title-meta 로 묶는다.
   제목과 같은 줄에 들어가면 그 줄 오른쪽, 모자라면 다음 줄에 날짜 왼쪽 · 버튼 오른쪽 */
.post-title:has(.post-title-meta) { display: flex; flex-wrap: wrap; align-items: center; column-gap: 8px; }
.post-title-meta { flex: 1 0 auto; display: flex; align-items: center; justify-content: space-between; gap: 8px; letter-spacing: 0; }
.title-share { flex: none; display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; margin-left: auto; padding: 0;
  background: #fff; border: 1px solid #E2E8F0; border-radius: 8px; color: #111; cursor: pointer; }
.title-share:hover { border-color: #111; }
/* 공유 팝업 (툴팁 팝업과 같은 상자) — 플랫폼 버튼은 왼쪽부터 한 줄로, 넘치면 다음 줄 */
.share-pop .share-buttons { justify-content: flex-start !important; }
/* 제목 아래 날짜 줄(October 11, 2026) 삭제 (2026-10-12 사용자) */
.post-timestamp { display: none !important; }
/* 글 보기: 첫 제목 위 여백 70% 줄임 (2026-10-12 사용자) — 위 32+40 → 10+12 */
body.item-view .main-content, body.item-view.no-dashboard .main-content { padding-top: 30px; }
/* 글 제목 위 보이는 여백 30px (2026-10-12 사용자 20 → 2026-10-13 사용자: "상단 타이틀의 위쪽 여백을 10픽셀 추가"). 행간 반쪽만큼 뺀 값 */
body.item-view .post-outer-container { padding-top: 13px; }

/* 리포트 본문은 인라인 스타일을 갖고 있어 컨테이너만 잡아준다 */
.post-body { font-size: 19px; line-height: 34px; color: #333; overflow-wrap: anywhere; }   /* 행간 px 정수 — 리포트 본문과 같은 34px (2026-10-12 사용자) */
/* 데일리 문단: PC 는 문장마다 한 줄(data-sent 블록), 모바일은 문장이 이어 흐른다(아래 @media) — 좁은 화면에서 "니다." 만 남는 고아 줄 방지 (2026-10-16 사용자).
   keep-all 로 단어 중간에서 끊지 않고, text-wrap: pretty 로 마지막 줄이 너무 짧지 않게 (지원 브라우저만) */
.post-body [data-para] { word-break: keep-all; text-wrap: pretty; }
.post-body [data-sent] { display: block; }
.post-body img { max-width: 100%; height: auto; border-radius: 12px; }
.post-body table { width: 100%; border-collapse: collapse; }
/* 셀에 nowrap 이 있는 표(리포트 본문)는 글 폭을 밀어내지 않고 표 안에서만 가로 스크롤한다 */
.post-body table { display: block; max-width: 100%; overflow-x: auto; }
/* 표 칸은 글자 중간에서 끊지 않는다 — 좁은 화면에서 칸을 쥐어짜지 말고 표가 옆으로 넘쳐 스크롤되게 (2026-10-11 사용자) */
.post-body td, .post-body th { word-break: keep-all; overflow-wrap: normal; }
/* 아코디언 (리포트 details[data-acc]): 기본 삼각형 숨기고 화살표 아이콘을 펼치면 위로 (2026-10-11) */
.post-body details[data-acc] > summary::-webkit-details-marker { display: none; }
.post-body details[data-acc][open] > summary .acc-chev { transform: rotate(180deg); }
/* 카드 안 펼침 (details[data-fold], 2026-10-13 사용자): 테마 JS가 펼친 줄을 버튼 위로 옮기고 글자를 '접기'로 — .is-open 이면 화살표 위로 */
.post-body details[data-fold] > summary::-webkit-details-marker { display: none; }
.post-body details[data-fold].is-open > summary .acc-chev { transform: rotate(180deg); }
.post-body [data-fold-more][hidden] { display: none !important; }
/* 툴팁 (리포트 [data-tip]) → 팝업창 (2026-10-12 사용자: "툴팁은 팝업창으로, 내용 18포인트"). ? 아이콘을 누르면(PC 클릭 · 폰 탭 · Enter) 화면 가운데 창이 뜬다.
   테마 JS가 .rt-pop 을 만든다. 닫기: × 버튼 · 바깥 누르기 · Esc. 줄바꿈(&#10;)은 창 안에서 줄을 바꾼다 */
.post-body [data-tip] { outline: none; cursor: pointer; }
.post-body [data-tip]:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 50%; }
.rt-pop { position: fixed; inset: 0; z-index: 1000; display: flex; align-items: center; justify-content: center; padding: 16px; background: rgba(15,23,42,.45); }
.rt-pop[hidden] { display: none; }
.rt-pop-box { position: relative; display: flex; flex-direction: column; width: 100%; max-width: 520px; max-height: 80vh; overflow: hidden; padding: 0; background: #fff; border-radius: 12px; box-shadow: 0 12px 40px rgba(0,0,0,.25); }
/* 팝업 제목 · 닫기는 위에 고정, 내용만 스크롤 (2026-10-13 사용자) */
.rt-pop-head { position: relative; flex: none; padding: 20px 60px 12px 20px; border-bottom: 1px solid #F1F5F9; }
.rt-pop-body, .share-pop-body { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 12px 20px 22px; }
.rt-pop-title { margin: 0; font-size: 19px; font-weight: 700; line-height: 24px; color: #111; }
.rt-pop-body { font-size: 19px; font-weight: 400; line-height: 34px; color: #333; word-break: keep-all; }
/* 툴팁 내용 행간 = 본문 34px (2026-10-12 사용자: "툴팁도 본문 행간으로 동일하게"). 팝업 글머리표: 점 칸(3px, 첫 줄 가운데 = (34 − 3) / 2 → 15px)과 글 칸을 나눠 둘째 줄이 점 아래로 들어가지 않게 (2026-10-12 사용자: 툴팁도 포함) */
.rt-pop-li { display: flex; align-items: flex-start; gap: 7px; margin: 9px 0; padding-left: 8px; }   /* 팝업 글머리표 들여쓰기 8px (2026-10-14 사용자: 14 → 8) */   /* 글머리표 사이 +6 (2026-10-12 사용자) */
.rt-pop-dot { flex: none; width: 3px; height: 3px; margin-top: 15px; border-radius: 50%; background: currentColor; }
.rt-pop-li > span:last-child { min-width: 0; }
.rt-pop-p.has-label:not(:first-child), .rt-pop-li + .rt-pop-p { margin-top: 12px; }   /* 용어 묶음 사이 · 글머리표 뒤 문단 띄움 (2026-10-12) */
.rt-pop-p b { color: #111; }
.rt-pop-close { position: absolute; top: 12px; right: 12px; width: 32px; height: 32px; border: 1px solid #E2E8F0; border-radius: 8px; background: #fff; color: #111; font-size: 20px; line-height: 28px; cursor: pointer; }
/* 리포트 탭 (엔비디아 글 보기, 가이드라인 11절): 상단 탭은 액센트 빨강 밑줄 3px, 서브탭은 밑줄형 14px 회색 (2026-10-11) */
.post-body .rt-tabs { display: flex; gap: 7px; overflow-x: auto; scrollbar-width: none; margin: 12px 0 14px; padding-bottom: 2px; border-bottom: 2px solid #eee; }
.post-body .rt-tabs::-webkit-scrollbar { display: none; }
/* 탭 이름 사이 간격 +10% (2026-10-13 사용자: "모든 탭메뉴명과 메뉴명 사이 여백을 10% 늘려") — 탭 30 → 33, 서브탭 22 → 24, 전환 30 → 32, 하위탭 20 → 22 */
.post-body .rt-tab { flex: none; padding: 8px 13px; font: inherit; font-size: 19px; line-height: 24px; font-weight: 700; color: #6B7280; border: 0; background: none; border-bottom: 3px solid transparent; margin-bottom: -2px; white-space: nowrap; cursor: pointer; }   /* 탭 18px (2026-10-12 사용자) */
.post-body .rt-tab[aria-selected="true"] { color: var(--accent); border-bottom-color: var(--accent); }
.post-body .rt-panel[hidden] { display: none; }
.post-body .rt-sub { display: flex; align-items: center; gap: 2px; overflow-x: auto; scrollbar-width: none; margin: 0 0 12px; border-bottom: 1px solid #E2E8F0; }
.post-body .rt-subtab { flex: none; padding: 6px 11px; font: inherit; font-size: 19px; line-height: 24px; font-weight: 400; color: #6B7280; background: none; border: 0; border-bottom: 3px solid transparent; margin-bottom: -1px; white-space: nowrap; cursor: pointer; }
.post-body .rt-subtab[aria-selected="true"] { color: #111; font-weight: 700; border-bottom-color: var(--accent); }
/* 데스크톱 2열 (2026-10-11 사용자: "모바일이 아닐 때 카드를 중간 구분선 있는 2열로"): 렌더러가 단 data-grid 표시를 테마가 그린다.
   data-grid=2 (C 카드 줄 묶음) → 2열 그리드 + 짝수 칸 왼쪽 세로 구분선. 둘째 칸의 인라인 border-top 은 지운다(첫 줄에 선이 생기지 않게).
   data-grid=cards (상태 카드 묶음) → 카드 둘씩 나란히. 모바일(680px 이하)은 그대로 한 줄 */
@media (min-width: 681px) {
  .post-body [data-grid="2"] { display: grid !important; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  .post-body [data-grid="2"] > span:nth-child(even) { border-left: 1px solid var(--grid-line, #E2E8F0); }   /* 강조 카드는 --grid-line 으로 오렌지 */
  .post-body [data-grid="2"] > span:nth-child(2) { border-top: 0 !important; }
  .post-body [data-grid="cards"] { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 8px; align-items: stretch; }
  .post-body [data-grid="cards"] > div { margin: 0 !important; }
  /* 읽는 법 카드의 글머리표 2열 (data-guide-grid, 2026-10-11 사용자) */
  .post-body ul[data-guide-grid] { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); column-gap: 28px; }
}
/* 전환 버튼 (data-switch, 당일 · 5일 그래프): 회색 바탕 알약 둘, 선택은 흰 바탕 · 검정 굵게 (2026-10-11) */
.post-body .rt-segs { display: inline-flex; gap: 2px; padding: 3px; margin: 4px 0 8px; background: #F1F5F9; border-radius: 8px; }
.post-body .rt-segs[hidden] { display: none; }
.post-body .rt-seg { padding: 6px 15px; font: inherit; font-size: 19px; line-height: 24px; font-weight: 400; color: #6B7280; background: none; border: 0; border-radius: 6px; cursor: pointer; }
.post-body .rt-seg[aria-pressed="true"] { background: #fff; color: #111; font-weight: 700; box-shadow: 0 1px 3px rgba(0,0,0,.12); }
.post-body [data-switch-panel][hidden], .post-body [data-hz-panel][hidden] { display: none; }
.post-body .rt-segs--in-sub { margin: 0 0 4px auto; flex: none; }
/* 하위탭 (부정 발언 · 긍정 발언 · 전체): 서브탭보다 한 단계 아래 — 16px, 밑줄 2px 검정, 줄 아래 선 없음. 표본이 모자란 탭은 흐리게 (2026-10-11) */
.post-body .rt-dirs { display: flex; gap: 4px; overflow-x: auto; scrollbar-width: none; margin: 0 0 8px; }
.post-body .rt-dirs[hidden] { display: none; }
.post-body .rt-dir { flex: none; padding: 4px 9px; font: inherit; font-size: 19px; line-height: 24px; font-weight: 400; color: #6B7280; background: none; border: 0; border-bottom: 2px solid transparent; white-space: nowrap; cursor: pointer; }
.post-body .rt-dir[aria-selected="true"] { color: #111; font-weight: 700; border-bottom-color: #111; }
.post-body .rt-dir[data-empty] { color: #CBD5E1; }
/* E 2열 카드는 폰에서도 2열 (2026-10-12 사용자: "왜 2열로 적용 안 했냐") — 예전의 폰 한 칸 쌓기 규칙 삭제.
   반 폭 칸에는 이름과 값이 한 줄에 들었다 안 들었다 해서, 폰에서는 칸마다 이름 위 · 값 아래 오른쪽으로 고르게 둔다 */
@media (max-width: 680px) {
  .post-body [data-pair] > span > span:last-child { flex-basis: 100% !important; text-align: right; }
}
/* 테마가 ul 을 전역 초기화(list-style:none, padding 0)하므로 글 본문의 목록은 글머리표를 되살린다 (2026-10-11).
   글머리표는 글 바깥 칸에(outside) — 줄이 바뀌어도 글이 글머리표 아래로 들어가지 않는다 (2026-10-12 사용자: "블릿과 글을 분리, 모든 블로그 글").
   리포트 목록은 인라인 padding:0 · list-style:none + 점 칸(dot_li)이라 이 규칙을 받지 않는다 — 옛 글 목록용 */
.post-body ul { list-style: disc outside; padding-left: 20px; }
.post-body ol { list-style: decimal outside; padding-left: 24px; }
.post-body a { color: var(--down); }

.byline, .post-footer, .post-bottom, .post-labels {
  font-size: 14px;
  color: var(--gray-400);
}
/* 글 아래 라벨(데일리 브리핑 · 미국 증시 · 자동 리포트 …)은 보이지 않게 (2026-10-12 사용자: "이런 태그는 삭제").
   라벨 자체는 글에 남긴다 — 홈 카드 · 목록 · 메뉴가 라벨 피드로 글을 찾는다 */
.post-labels { display: none !important; }
/* 헤더 아래 빈 띠는 두지 않는다 — 제목 위 여백은 본문 영역이 갖는다(홈 · 글 보기 모두 보이는 20px, 2026-10-12 사용자) */
.header-bar { height: 0 !important; padding: 0 !important; }
.post-labels a {
  display: inline-block;
  margin: 6px 6px 0 0;
  padding: 3px 10px;
  background: var(--surface-sub);
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  color: var(--gray-600);
}
.jump-link { display: none; }

/* 글 아래 목록으로 돌아가는 버튼 */
.post-nav { display: flex; justify-content: center; margin: 40px 0 0; }
.post-nav-list {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 42px;   /* 가로 30% 넓게 — 하단 버튼 공통 (2026-10-13 사용자) */
  background: #111;
  border: 1px solid #111;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
}
.post-nav-list:hover { background: #000; color: #fff; }   /* 검은 테마 버튼 (2026-10-12 사용자) */
/* 글 아래 줄: 목록(검은 버튼)은 가운데, 오른쪽 끝에 TOP 글자 버튼 16px (2026-10-13 사용자) */
.post-nav { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 8px; }
.post-nav .post-nav-list { grid-column: 2; }
.post-nav-top { grid-column: 3; justify-self: end; display: inline-flex; align-items: center; gap: 4px; padding: 8px 0; background: none; border: 0;
  font: inherit; font-size: 16px; line-height: 24px; font-weight: 700; color: #111; cursor: pointer; -webkit-tap-highlight-color: transparent; }
.post-nav-top:hover { color: var(--accent); }
.post-nav-top { gap: 6px; }   /* 화살표는 원형 외곽선 22px 안 (2026-10-14 사용자: "top 버튼 우측의 화살표 아이콘에 원형 외각선") */
.post-nav .post-nav-top { margin-right: 10px; }   /* 오른쪽 끝에서 10px 안쪽 (2026-10-13 사용자) */
/* 목록 버튼 위: 본문과 40px. 본문이 카드 밖 글로 끝나면 20px · 구분선 · 20px (테마 JS .ends-text, 2026-10-12 사용자) */
body.item-view .post-outer-container { padding-bottom: 0 !important; }
body.item-view .post-bottom, body.item-view .post-footer { margin: 0; padding: 0; }
.post-shell .post-nav { margin: 40px 0 0; }
.post-shell.ends-text .post-nav { margin-top: 17px; padding-top: 20px; border-top: 1px solid #E2E8F0; }   /* 끝 글자 → 구분선 20 (행간 반쪽 3 을 뺌) */

/* 이미 게시된 글 보정 — 리포트 본문은 인라인 font-size 를 달고 나오므로 CSS 가 밀린다.
   옛 글(15/14/12px)만 골라 덮어쓰도록 태그 종류까지 지정한다. 새 글은 렌더러가
   이미 18/17/14px 로 내보내므로 아래 선택자에 걸리지 않는다. */
.post-body > div[style*="font-size:15px"] { font-size: 18px !important; }
.post-body table[style*="font-size:14px"] { font-size: 17px !important; }
.post-body div[style*="font-size:14px"] { font-size: 17px !important; }
.post-body p[style*="font-size:12px"] { font-size: 14px !important; }
.post-body img[style*="max-width:760px"] { max-width: 1024px !important; }
/* 새 디자인 글(data-design="2", 2026-10-11 디자인 가이드라인 적용분)은 위 보정에서 제외 — 안내 글 14px·표를 그대로 둔다 */
.post-body [data-design="2"] div[style*="font-size:14px"] { font-size: 14px !important; }
.post-body [data-design="2"] table[style*="font-size:14px"] { font-size: 14px !important; }
.post-body [data-design="2"] > div[style*="font-size:15px"] { font-size: 15px !important; }

/* 공유 버튼 (2026-10-12 사용자: 공유 아이콘을 누르면 소셜 아이콘이 보이게) — b:css='false' 라 블로거 위젯 CSS 가 없다.
   기본은 "공유" 버튼 하나, 누르면(.is-open, 테마 JS) 플랫폼 버튼 줄이 아래에 펼쳐진다. 창을 여는 JS 도 테마가 직접 단다 */
.post-share-buttons { margin: 20px 0 0; }
.post-share-buttons-bottom { display: flex; justify-content: flex-end; margin: 28px 0 0; padding-top: 16px; border-top: 1px solid var(--border); }   /* 공유는 콘텐츠 오른쪽 (2026-10-12 사용자) */
.goog-inline-block { display: inline-block; }
.sharing { position: relative; display: flex; flex-direction: column; align-items: flex-end; }
/* 공유 버튼은 16px 작은 버튼 (2026-10-12 사용자: "16포인트의 작은 버튼으로 콘텐츠 우측에 정렬") */
.sharing-button {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px; line-height: 24px;
  background: var(--surface); border: 1px solid var(--border-strong); border-radius: 8px;
  font-size: 16px; font-weight: 700; color: var(--ink); cursor: pointer;
}
.sharing-button::after { content: '공유'; }
.sharing-button:hover, .sharing.is-open .sharing-button { border-color: #111; }
.share-buttons-container { display: none; margin-top: 10px; }
.sharing.is-open .share-buttons-container { display: block; }
.share-buttons, .share-buttons.hidden { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; margin: 0; padding: 0; list-style: none; }
.share-buttons li { margin: 0; }
.sharing-platform-button {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 12px;
  background: var(--surface-sub); border: 1px solid var(--border-strong); border-radius: 8px;
  font-size: 14px; font-weight: 700; color: var(--gray-600); cursor: pointer;
}
.sharing-platform-button:hover { border-color: #111; color: #111; }
.platform-sharing-text { white-space: nowrap; }
.post-share-buttons svg, .sharing svg, svg.svg-icon-24, .touch-icon { width: 20px; height: 20px; flex: none; fill: currentColor; }
.sharing-button svg, .sharing-button .touch-icon { width: 16px; height: 16px; }

/* 댓글 — 우리 것 (2026-10-14 사용자: "우리가 댓글 프로그램을 만드는 건 어때?" — 폰에서 블로거 댓글 입력창이 좁다. 디자인 가이드 10-2).
   블로거 댓글(blogger.com iframe · 전체 페이지)을 버리고 테마 JS 가 Firebase(Firestore REST + Google 로그인)로 그린다.
   마크업은 테마 JS "댓글" IIFE 가 만든다 — 열기 버튼만 카드, 펼친 목록 · 쓰기 칸은 카드 밖 본문 폭 전체, 댓글 사이 1px 구분선.
   글자: 이름 16px 굵게, 글 19px · 행간 24, 날짜 · 안내 · 버튼 14px. 사진 24px. 입력창은 본문 폭 전체(폰 화면 − 28px). */
.comments {
  width: 100%; max-width: var(--shell); margin: 40px auto 0;   /* 목록 버튼과 40px (2026-10-12 사용자) */
  font-size: 19px; line-height: 24px; color: #333; word-break: keep-all;
}
.comments .comments-title { margin: 0; padding: 0; border: 0; font-size: 16px; line-height: 24px; }
/* 열기 버튼 = 흰 카드, `댓글 n` 16px 굵게 · 오른쪽 공식 접기 화살표(테두리 없이). 기본 닫힘, 주소가 #comments · #c… 면 열린 채로 (2026-10-12 · 13 사용자) */
.comments-toggle { display: flex; width: 100%; align-items: center; justify-content: space-between; gap: 12px; margin: 0; padding: 8px 8px 8px 16px; background: #fff; border: 1px solid #E2E8F0; border-radius: 8px; font: inherit; font-size: 16px; font-weight: 700; line-height: 24px; color: #111; text-align: left; cursor: pointer; -webkit-tap-highlight-color: transparent; }
.comments-panel[hidden] { display: none; }
/* 공식 접기 버튼 (가이드 10-6) — 31px 네모 · 모서리 7 · 화살표 18 · 왼쪽 4 */
.fold-box { display: inline-flex; flex: none; align-items: center; justify-content: center; width: 31px; height: 31px; box-sizing: border-box; margin-left: 4px; border: 1px solid #E2E8F0; border-radius: 7px; background: #fff; color: #111; }
.comments-toggle .fold-box { border: 0; }   /* 댓글 열기 화살표는 테두리 없이 (2026-10-13 사용자) */
.comments-toggle .fold-box .acc-chev { transition: transform .15s; }
.comments.is-open .comments-toggle .fold-box .acc-chev { transform: rotate(180deg); }
/* 댓글 목록 — 댓글 사이 1px 구분선(위아래 14), 첫 댓글은 선 없이 위 18 */
.comments .cm-list, .comments .cm-replies { list-style: none; margin: 0; padding: 0; }
.comments .cm-list > .cm-item { padding: 18px 0; border-top: 1px solid #E2E8F0; }   /* 댓글 사이 위아래 14 → 18 (+30%, 2026-10-14 사용자) */
.comments .cm-list > .cm-item:first-child { border-top: 0; padding-top: 18px; }
/* 댓글 한 개 = 두 칸 grid(사진 | 글). 답글 묶음 · 답글 쓰기 칸은 글 칸 아래 줄 (2026-10-13 사용자: "댓글에 댓글은 레이아웃이 깨진다") */
.comments .cm-item { display: grid; grid-template-columns: 24px minmax(0, 1fr); column-gap: 7px; align-items: start; }   /* 사진 · 이름 10 → 7 (−30%, 2026-10-14 사용자) */
.comments .cm-avatar { grid-column: 1; grid-row: 1; display: flex; align-items: center; justify-content: center; width: 24px; height: 24px; margin-top: 0; border-radius: 50%; overflow: hidden; background: #94A3B8; color: #fff; font-family: var(--num); font-weight: 700; font-size: 12px; line-height: 24px; }   /* 사진 24px (2026-10-13 사용자) — 사진이 없으면 머리글자 원 */
.comments .cm-avatar img { width: 24px; height: 24px; display: block; }
.comments .cm-avatar.is-owner { background: #fff; border: 1px solid #E2E8F0; box-sizing: border-box; }   /* 운영자 = AlphaScope 로고 (2026-10-14 사용자) */
.comments .cm-avatar.is-owner svg { width: 14px; height: 13px; display: block; }
.comments .cm-body { grid-column: 2; grid-row: 1; min-width: 0; }
.comments .cm-head { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 10px; margin: 0; line-height: 24px; }
.comments .cm-name { font-size: 16px; font-weight: 700; color: #111; }
.comments .cm-tag { display: inline-block; margin: 0; padding: 3px 5px 2px; border: 1px solid #CBD5E1; border-radius: 4px; background: #fff; font-size: 14px; font-weight: 400; line-height: 1; color: #334155; vertical-align: middle; position: relative; top: -1px; }   /* 운영자 라벨 — 영역 라벨 모양 (가이드 5절) */
.comments .cm-date { font-family: var(--num); font-size: 14px; line-height: 20px; color: #7A7A7A; white-space: nowrap; }
.comments .cm-text { margin: 4px 0 0; font-size: 19px; line-height: 24px; color: #333; white-space: pre-wrap; overflow-wrap: anywhere; }
.comments .cm-text.is-deleted { color: #94A3B8; font-size: 14px; line-height: 20px; }   /* 원 댓글이 지워진 답글 묶음의 자리 */
/* 동작 버튼(답글 · 삭제)은 할 수 있는 사람에게만 — 로그인 전에는 보이지 않는다 (2026-10-13 사용자: "로그인 전에는 기능이 안 되는 버튼은 노출하지 마라") */
.comments .cm-actions { display: flex; flex-wrap: wrap; justify-content: flex-start; gap: 6px; margin-top: 8px; }
.comments .cm-actions:empty { display: none; }
.comments .cm-btn { display: inline-flex; align-items: center; margin: 0; padding: 5px 12px; background: #fff; border: 1px solid #E2E8F0; border-radius: 8px; font: inherit; font-size: 14px; line-height: 21px; font-weight: 700; color: #111; cursor: pointer; -webkit-tap-highlight-color: transparent; }
.comments .cm-btn:hover { border-color: #111; }
.comments .cm-btn[disabled] { opacity: .4; cursor: default; }
.comments .cm-replies { grid-column: 2; margin: 0; }   /* 답글은 원 댓글 글 왼쪽 선에 맞춰 */
.comments .cm-replies > .cm-item { padding: 18px 0 0; border-top: 0; }
.comments .cm-replybox { grid-column: 2; margin-top: 10px; }
.comments .cm-replybox:empty { display: none; }
.comments .cm-status { padding: 14px 0; font-size: 14px; line-height: 20px; color: #7A7A7A; text-align: center; }   /* 불러오는 중 · 못 불러옴 · 첫 댓글 안내도 가운데 (2026-10-14 사용자) */
.comments .cm-status[hidden] { display: none; }
/* 쓰기 칸 — 윗선 아래. 댓글이 없으면 선 없이 (댓글 목록 바로 아래 흰 버튼 하나였던 자리, 2026-10-13 사용자) */
.comments .cm-write { margin-top: 0; padding-top: 14px; border-top: 1px solid #E2E8F0; }
.comments .cm-write.is-first { border-top: 0; }
.comments .cm-login { display: block; width: 100%; padding: 11px 12px; background: #fff; border: 1px solid #B5BAC0; border-radius: 8px; color: #111; font: inherit; font-size: 16px; line-height: 24px; font-weight: 700; text-align: center; cursor: pointer; -webkit-tap-highlight-color: transparent; }   /* 공식 흰 버튼 — 외곽선 #E2E8F0 → 20% 진하게 #B5BAC0 (2026-10-14 사용자, 가이드 2-3 흰 버튼) */
.comments .cm-login:hover { border-color: #111; }
.comments .cm-login[disabled] { opacity: .5; cursor: default; }
.comments .cm-me { display: flex; align-items: center; gap: 7px; margin-bottom: 10px; line-height: 24px; }
.comments .cm-me .cm-avatar { grid-column: auto; grid-row: auto; }
.comments .cm-link { margin-left: auto; padding: 0; background: none; border: 0; font: inherit; font-size: 14px; line-height: 20px; color: #7A7A7A; cursor: pointer; }
.comments .cm-link:hover { color: #111; }
/* 입력창 — 본문 폭 전체, 테두리 #E2E8F0 · 모서리 8, 안쪽 11 · 12, 글 19px · 행간 24, 처음 4줄 높이. 글을 쓰면 아래로 늘어난다 */
.comments .cm-input { display: block; width: 100%; min-height: 118px; margin: 0; padding: 11px 12px; box-sizing: border-box; background: #fff; border: 1px solid #E2E8F0; border-radius: 8px; font: inherit; font-size: 19px; line-height: 24px; color: #333; resize: none; overflow: hidden; }
.comments .cm-input:focus { outline: none; border-color: #111; }
.comments .cm-input::placeholder { color: #94A3B8; }
.comments .cm-foot { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 8px; }
.comments .cm-count { font-family: var(--num); font-size: 14px; line-height: 20px; color: #7A7A7A; font-variant-numeric: tabular-nums; }
.comments .cm-foot-btns { display: flex; align-items: center; gap: 6px; }
.comments .cm-submit { display: inline-flex; align-items: center; margin: 0; padding: 8px 24px; background: #111; border: 1px solid #111; border-radius: 8px; font: inherit; font-size: 16px; line-height: 24px; font-weight: 700; color: #fff; cursor: pointer; -webkit-tap-highlight-color: transparent; }   /* 등록 — 검은 테마 버튼 (2026-10-13 사용자: "모든 하단 버튼은 블랙 테마 버튼") */
.comments .cm-submit:hover { background: #000; }
.comments .cm-submit[disabled] { opacity: .4; cursor: default; }
.comments .cm-error { margin-top: 8px; font-size: 14px; line-height: 20px; color: #B91C1C; text-align: center; }   /* 오류 안내는 가운데 (2026-10-14 사용자) */
.comments .cm-error:empty { display: none; }

/* 레이아웃 모드에서만 보이는 보관용 위젯 */
.hidden-widgets { display: none; }

/* 대시보드가 없는 뷰는 상단 여백을 조금 준다 */
body.no-dashboard .main-content { padding-top: 32px; }

@media (max-width: 900px) {
  .post-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .post-outer-container { padding: 24px; }
  body.item-view .post-outer-container { padding-top: 13px; }   /* 카드 위 → 제목 글자 보이는 20 (2026-10-12 사용자) */
  .post-title { font-size: 27px; line-height: 36px; }
}
@media (max-width: 680px) {
  .post-grid { grid-template-columns: minmax(0, 1fr); }
  /* 글 보기(모바일): 화면 가장자리에서 본문까지 정확히 20px. 카드 테두리·안쪽 패딩은 없앤다 (2026-10-10) */
  body.item-view .main-content { padding-left: 14px; padding-right: 14px; }   /* 2026-10-11 사용자: 콘텐츠 영역 좌우 14px */
  .post-outer-container { padding: 16px 0 24px; border: 0; border-radius: 0; background: transparent; }
  body.item-view .post-outer-container { padding-top: 0; }
  body.item-view .main-content, body.item-view.no-dashboard .main-content { padding-top: 31px; }   /* 헤더 → 제목 글자 보이는 30 (2026-10-13 사용자: +10) */
  .post-title { font-size: 23px; line-height: 32px; letter-spacing: -.3px; }   /* 22 → 23 (+1, 2026-10-13) */   /* 폰 제목 2px 작게 24 → 22 (2026-10-13 사용자) */
  .post-body h2 { font-size: 20px !important; line-height: 26px !important; }   /* 폰 구획 제목 20 (공식 22 − 2, 2026-10-13) */   /* 리포트 구획 제목 21 → 19 — 렌더러 인라인 크기를 덮는다 (2026-10-13 사용자) */
  .post-body { font-size: 19px; line-height: 34px; }   /* 본문 19 (2026-10-13 사용자: 블로그 전체 본문 19포인트) */
  .post-body [data-sent] { display: inline; }   /* 모바일: 문장 줄바꿈 없이 이어 흐른다 — 문단(빈 줄)만 남는다 (2026-10-16 사용자) */
  /* 데스크톱용 커버 이미지 확대 규칙(1024px !important)이 모바일에서 글 폭을 벌리지 않게 */
  .post-body img, .post-body img[style*="max-width"] { max-width: 100% !important; }
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
    <!-- 검색 (2026-10-13 사용자): Google Search Console 소유 확인. 블로거 설정의 검색 설명이 비어 있으면 홈 · 목록에 기본 설명을 단다(글 보기는 블로거가 본문 앞부분으로 채운다) -->
    <meta content='GWtZLHo2CgnmBBgSxQQg0BKY_xKZJTSba7BBOZ6e4Ts' name='google-site-verification'/>
    <!-- 네이버 서치어드바이저 소유 확인 (2026-10-15 사용자). 블로거는 루트에 HTML 파일을 못 올려 메타 태그 방식 -->
    <meta content='4b16f0e43da3e199130fd61a86cb96dff343fb9d' name='naver-site-verification'/>
    <b:if cond='!data:view.isSingleItem and data:blog.metaDescription == &quot;&quot;'>
      <meta content='__SITE_DESC__' name='description'/>
    </b:if>
    <!-- 홈 화면 아이콘 (2026-10-13 사용자, 디자인 가이드 10-4). 블로거에는 파일을 못 올리므로 리포 pwa/ 를 jsDelivr 로 쓴다 -->
    <link href='https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@main/pwa/manifest.json' rel='manifest'/>
    <link href='https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@main/pwa/apple-touch-icon.png' rel='apple-touch-icon'/>
    <meta content='#FFFFFF' name='theme-color'/>
    <meta content='yes' name='mobile-web-app-capable'/>
    <meta content='yes' name='apple-mobile-web-app-capable'/>
    <meta content='AlphaScope' name='apple-mobile-web-app-title'/>
    <meta content='default' name='apple-mobile-web-app-status-bar-style'/>
    <link href='https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;900&amp;family=Inter:wght@400;600;700;800&amp;display=swap' rel='stylesheet'/>

    <b:skin version='1.0'><![CDATA[/*
<Variable name="keycolor" description="Main Color" type="color" default="#FF3333" value="#FF3333"/>
<Group description="Page Text">
  <Variable name="body.text.color" description="Text color" type="color" default="#0F172A" value="#0F172A"/>
</Group>
<Group description="Backgrounds">
  <Variable name="body.background.color" description="Page background" type="color" default="#FFFFFF" value="#FFFFFF"/>
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
          <b:widget id='Header1' locked='true' title='AlphaScope (Header)' type='Header' visible='true'>
            <b:includable id='main'>
              <a class='logo' expr:href='data:blog.homepageUrl'>
                <svg class='logo-mark' viewBox='0 0 313 286'>
                  <path d='M313 134L164.968 286H35L189.03 134H313Z' fill='#DD0000'/>
                  <path d='M164.519 0H287L128.954 147H0L164.519 0Z' fill='#000000'/>
                </svg>
                <span class='logo-word'>AlphaScope</span>
              </a>
            </b:includable>
          </b:widget>
        </b:section>

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
              <form class='search-bar' id='site-search' expr:action='data:blog.searchUrl' method='get' role='search'>
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

        <!-- 폰: 알림 · 검색 · 메뉴 순서로 오른쪽 정렬 (2026-10-12 사용자) -->
        <button class='search-toggle' type='button' aria-controls='site-search' aria-expanded='false'>
          <svg viewBox='0 0 14 14' fill='none' stroke='currentColor' stroke-width='2'>
            <circle cx='5.75' cy='5.75' r='4.5'/>
            <path d='M9.3 9.3 12.8 12.8' stroke-linecap='round'/>
          </svg>
          <span class='sr-only'>검색 열기</span>
        </button>

        <button class='nav-toggle' type='button' aria-controls='primary-menu' aria-expanded='false'>
          <svg viewBox='0 0 24 24' width='20' height='20' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round'>
            <path d='M3 6h18M3 12h18M3 18h18'/>
          </svg>
          <span class='sr-only'>메뉴 열기</span>
        </button>

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
          <b:includable id='main'><b:comment>AlphaScope 테마에서는 표시하지 않음</b:comment></b:includable>
        </b:widget>

        <b:widget id='Blog1' locked='true' title='Blog Posts' type='Blog' visible='true'>
          <b:includable id='main'>
            <b:if cond='data:view.isSingleItem'>
              <div class='post-shell'>
                <b:loop values='data:posts' var='post'>
                  <article class='post-outer-container'>
                    <b:include data='post' name='post'/>
                  </article>
                  <p class='post-nav'>
                    <b:comment>목록 버튼은 글의 연재(라벨)로 간다 — 트럼프 트렌드 글이면 그 라벨 목록, 아니면 데일리 리포트 목록.
                      오른쪽 끝 TOP 은 맨 위로 (2026-10-13 사용자). 이전 글 · 다음 글은 같은 날 삭제.</b:comment>
                    <b:if cond='data:post.labels any (l =&gt; l.name == &quot;__TRUMP_LABEL__&quot;)'>
                      <a class='post-nav-list' expr:href='data:blog.homepageUrl + &quot;__TRUMP_LIST_PATH__&quot;'>목록</a>
                    <b:elseif cond='data:post.labels any (l =&gt; l.name == &quot;__NVDA_LABEL__&quot;)'/>
                      <a class='post-nav-list' expr:href='data:blog.homepageUrl + &quot;__NVDA_LIST_PATH__&quot;'>목록</a>
                    <b:else/>
                      <a class='post-nav-list' expr:href='data:blog.homepageUrl + &quot;__LIST_PATH__&quot;'>목록</a>
                    </b:if>
                    <button aria-label='맨 위로' class='post-nav-top' type='button'>TOP<svg aria-hidden='true' fill='none' height='22' stroke='currentColor' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.6' viewBox='0 0 22 22' width='22'><circle cx='11' cy='11' r='10'/><path d='M11 15.5V7M7.5 10.5 11 7l3.5 3.5'/></svg></button>
                  </p>
                  <b:comment>댓글은 우리 것 — 테마 JS "댓글" IIFE 가 Firebase 로 그린다 (2026-10-14 사용자: 폰에서 블로거 댓글 입력창이 좁다). 블로거 댓글(commentPicker)은 더 쓰지 않는다.</b:comment>
                  <section class='comments' expr:data-post-id='data:post.id' id='comments'><h3 class='comments-title'>댓글</h3></section>
                </b:loop>
              </div>
            <b:elseif cond='data:view.isHomepage'/>
              <b:comment>홈 아래 최근 리포트 링크 영역은 삭제 (2026-10-14 사용자). 홈은 위 대시보드만.</b:comment>
            <b:else/>
              <section class='reports'>
                <div class='section-head'>
                  <h2 class='section-title'>
                    <b:if cond='data:view.isLabelSearch and data:view.search.label == &quot;__TRUMP_LABEL__&quot;'>트럼프 SNS 트렌드 목록
                    <b:elseif cond='data:view.isLabelSearch and data:view.search.label == &quot;__NVDA_LABEL__&quot;'/>엔비디아 리포트 목록
                    <b:elseif cond='data:view.isLabelSearch'/>미국 증시 리포트 목록
                    <b:else/><data:view.title.escaped/></b:if>
                  </h2>
                  <span class='section-note'>
                    <b:if cond='data:view.isLabelSearch and (data:view.search.label == &quot;__TRUMP_LABEL__&quot; or data:view.search.label == &quot;__NVDA_LABEL__&quot;)'>AI 자동 생성 · 매일 아침 · 미국장 마감 후
                    <b:else/>AI 자동 생성 · 매 거래일 아침 · 미국장 마감 후</b:if>
                  </span>
                </div>
                <div class='post-grid'>
                  <b:loop values='data:posts' var='post'>
                    <article class='post-card'>
                      <b:comment>트럼프 · 엔비디아 글은 카드 위 이미지를 두지 않는다 — 제목 · 요약만 (2026-10-13 사용자). 데일리는 커버 이미지 그대로.</b:comment>
                      <b:if cond='!(data:post.labels any (l =&gt; l.name == &quot;__TRUMP_LABEL__&quot; or l.name == &quot;__NVDA_LABEL__&quot;))'>
                      <a expr:href='data:post.url'>
                        <b:if cond='data:post.featuredImage'>
                          <img class='post-card-img' expr:alt='data:post.title' expr:src='data:post.featuredImage'/>
                        <b:else/>
                          <span class='post-card-img'></span>
                        </b:if>
                      </a>
                      </b:if>
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
          <b:includable id='main'><b:comment>AlphaScope 테마에서는 표시하지 않음</b:comment></b:includable>
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

# 홈 · 목록의 검색 설명 (블로거 설정의 검색 설명이 비어 있을 때만, 2026-10-13 사용자: 구글 검색에 잘 안 나온다)
# 특정 종목 이름은 넣지 않는다 — 종목별 리포트는 늘어날 수 있다 (2026-10-13 사용자)
SITE_DESC = "미국 증시 지수와 섹터, 트럼프 발언, 종목별 주가와 뉴스를 매일 아침 정리하는 자동 리포트"

# 상단 메뉴 = 지금 있는 리포트 연재 (2026-10-13 사용자: "리포트들은 메뉴에 있어야 하고 클릭하면 리포트 리스트 화면으로"). (보이는 이름, 블로거 라벨)
NAV_LABELS = [("미국 증시 리포트", "데일리 브리핑"), ("트럼프 SNS 트렌드", "트럼프 트렌드"), ("엔비디아 리포트", "엔비디아")]

# 데일리 리포트 목록 화면. publish_blogger.LABELS 의 첫 라벨과 같아야 한다 —
# 파이프라인이 실제로 붙이는 라벨이라야 목록에 글이 잡힌다.
REPORT_LABEL = "데일리 브리핑"
LIST_PATH = "search/label/" + quote(REPORT_LABEL)

# 트럼프 SNS 트렌드 연재. experiments/trump-trend/report_title.LABELS 의 첫 라벨과 같아야 한다.
# 글 하단 '목록' 버튼과 라벨 목록 화면 제목이 이 라벨로 연재를 가른다.
TRUMP_LABEL = "트럼프 트렌드"
TRUMP_LIST_PATH = "search/label/" + quote(TRUMP_LABEL)

# 엔비디아 리포트 연재 (experiments/nvda-report/report_title.LABELS 의 첫 라벨). 목록 버튼이 데일리 목록으로 가던 것을 바로잡음 (2026-10-12)
NVDA_LABEL = "엔비디아"
NVDA_LIST_PATH = "search/label/" + quote(NVDA_LABEL)


def nav_items():
    out = []
    for name, label in NAV_LABELS:
        # 주소는 인코딩한다 — "트럼프 트렌드"처럼 띄어쓰기가 있는 라벨 때문. 비교는 원문으로.
        out.append(
            "          <a class='nav-item' expr:href='data:blog.homepageUrl + &quot;search/label/{1}&quot;'>\n"
            "            <b:attr cond='data:view.search.label == &quot;{0}&quot;' name='aria-current' value='page'/>{2}</a>".format(label, quote(label), name)
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


# PC 글자 — 네이버 블로그 글(스마트에디터 ONE) 기준 (2026-10-15 사용자: "blog.naver.com/lmkek41/224417597667 화면 참고해서 폰트 적용,
# 본문 폰트 사이즈도 이것으로, 행간은 기존보다 늘었어, 폰트 두께는 1단계 두껍게" — PC 만).
# 그 글: 나눔바른고딕(se-ff-nanumbarungothic) · 본문 16px(se-fs-fs16) · 행간 2.0 · 자간 0.
# 그래서 본문 19 → 16, 16px 보다 큰 글자는 같은 비율(16/19)로 줄이되 16 아래로는 내리지 않는다(17 · 18 → 16). 16px 이하는 그대로.
# 문단 글(행간이 글자의 1.6배 이상)은 행간 = 글자 × 2.0, 한 줄짜리 글은 글자와 같은 비율로.
# 굵기: 나눔바른고딕은 Regular 다음이 Bold 라 Medium 이 없다 → 아주 얇은 윤곽선(0.25px)으로 한 단계 두껍게 보이게 (사용자 선택).
# (같은 날 앞서: 본문 16 · 16/19 → 네이버 뉴스 기사 17 · 행간 1.56 · 자간 -0.3 → 지금)
# 손으로 적지 않고 빌드 때 테마 CSS 를 읽어 만든다 — 새로 넣는 큰 글자도 PC 에서 같이 줄어든다.
# 모바일 · 태블릿(900px 이하)용 규칙은 읽지 않고, 결과는 모두 @media (min-width: 901px) 안이다(@font-face 만 밖 — 쓰일 때만 내려받는다).
PC_MIN = 901
PC_BODY = 16
PC_RATIO = PC_BODY / 19
PC_PARA_LH = 2.0           # 네이버 블로그 본문 문단 line-height:2.0
PC_FONT = "'AS Barun', 'NanumBarunGothic', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif"
PC_STROKE = "0.25px"       # 한 단계 두껍게 (Medium 대신)
BARUN = "https://hangeul.pstatic.net/hangeul_static/webfont/NanumBarunGothic/"   # 네이버 한글 글꼴 공식 배포
PC_FIXED = {".post-title": (28, 36)}   # 글 제목 28 · 36 (네이버 뉴스 기사 제목, 같은 날)
POST_INLINE_SIZES = (17, 18, 19, 20, 21, 22, 26, 28)   # 리포트 렌더러가 본문에 인라인으로 넣는 16 초과 크기
POST_INLINE_LH = {27: 19, 28: 22, 32: 18, 34: 19}       # 렌더러 인라인 행간 → 그 행간을 쓰는 글자 크기


def _half(x):
    v = round(x * 2) / 2
    return f"{v:g}px"


def _pc_size(size):
    return max(float(PC_BODY), round(size * PC_RATIO * 2) / 2)


def _pc_lh(size, lh):
    new = _pc_size(size)
    return new * PC_PARA_LH if lh / size >= 1.6 else lh * new / size


def pc_type_css(css):
    """16px 초과 font-size 규칙을 PC 에서 네이버 기사 기준(본문 17)으로 줄이는 CSS. 같은 선택자는 마지막 선언 기준."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rules = {}   # 선택자 → (크기, 행간, !important) — 순서 유지, 같은 선택자는 나중 것이 이긴다

    def walk(text, skip):
        i = 0
        while i < len(text):
            j = text.find("{", i)
            if j < 0:
                return
            head = text[i:j].strip()
            depth, k = 1, j + 1
            while depth and k < len(text):
                depth += {"{": 1, "}": -1}.get(text[k], 0)
                k += 1
            body = text[j + 1:k - 1]
            if head.startswith("@media"):
                walk(body, skip or "max-width" in head or "prefers-reduced-motion" in head)
            elif head.startswith("@"):
                pass   # @keyframes 등
            elif not skip:
                fs = re.search(r"(?<![-\w])font-size:\s*([\d.]+)px\s*(!important)?", body)
                if fs:
                    lh = re.search(r"(?<![-\w])line-height:\s*([\d.]+)px", body)
                    rules.pop(head, None)
                    rules[head] = (float(fs.group(1)), float(lh.group(1)) if lh else None, bool(fs.group(2)))
            i = k

    walk(css, False)
    out = []
    for sel, (size, lh, imp) in rules.items():
        if size <= 16:
            continue
        bang = " !important" if imp else ""
        if sel in PC_FIXED:
            fs_, lh_ = PC_FIXED[sel]
            out.append(f"  {sel} {{ font-size: {fs_}px{bang}; line-height: {lh_}px{bang}; }}")
            continue
        decl = f"font-size: {_pc_size(size):g}px{bang};"
        if lh:
            decl += f" line-height: {_half(_pc_lh(size, lh))}{bang};"
        out.append(f"  {sel} {{ {decl} }}")
    # 리포트 본문의 인라인 크기 (렌더러 style="font-size:19px" 등) — 테마 규칙보다 이기도록 !important
    for n in POST_INLINE_SIZES:
        out.append(f'  .post-body [style*="font-size:{n}px"], .post-body [style*="font-size: {n}px"] {{ font-size: {_pc_size(n):g}px !important; }}')
    for n, size in POST_INLINE_LH.items():
        new_lh = round(_pc_lh(size, n) * 2) / 2
        out.append(f'  .post-body [style*="line-height:{n}px"], .post-body [style*="line-height: {n}px"] {{ line-height: {new_lh:g}px !important; }}')
        # 글머리표 점(design_kit.dot_li)은 첫 줄 가운데 = (행간 − 점) / 2 — 행간이 줄면 점도 올린다
        for dot in (2, 3):
            out.append(f'  .post-body li[style*="line-height:{n}px"] > span[style*="height:{dot}px"][style*="margin-top:{(n - dot) // 2}px"]'
                       f' {{ margin-top: {round((new_lh - dot) / 2)}px !important; }}')
    # 테마의 3px 점 — 본문 행간(17 × 1.56 = 26.5)의 첫 줄 가운데
    out.append(f"  .report-columns li::before, .kv-row--block li::before, .rt-pop-dot {{ margin-top: {round((round(PC_BODY * PC_PARA_LH * 2) / 2 - 3) / 2)}px; }}")
    # 글꼴 — 나눔바른고딕. 테마의 글꼴 변수와 리포트 본문 인라인 글꼴(design_kit.WRAP_OPEN)을 바꾼다. 숫자 칸(--num, Inter)은 그대로
    out.append(f"  :root {{ --sans: {PC_FONT}; --report-font: {PC_FONT}; }}")
    out.append("  .logo-word { font-family: 'Noto Sans KR', sans-serif; }")   # 로고 글자는 그대로
    out.append("  .post-body [style*=\"font-family\"]:not([style*=\"monospace\"]) { font-family: var(--report-font) !important; }")
    out.append(f"  body {{ -webkit-text-stroke: {PC_STROKE}; }}")
    face = ("@font-face {{ font-family: 'AS Barun'; font-weight: {w}; font-display: swap; "
            "src: url({u}NanumBarunGothicWeb{s}.woff) format('woff'); }}")
    return ("/* PC 글자 — build_theme.pc_type_css 가 만든다. 직접 고치지 말 것 (2026-10-15 사용자, 네이버 블로그 글 기준) */\n"
            + face.format(w=400, u=BARUN, s="") + "\n" + face.format(w=700, u=BARUN, s="Bold") + "\n"
            f"@media (min-width: {PC_MIN}px) {{\n" + "\n".join(out) + "\n}")


def build_theme(parts):
    """블로거에 붙여넣는 테마 XML 을 만든다."""
    includables, n = blog_includables()
    # 공유 버튼: 제목 아래(headerByline)에는 두지 않고 본문 아래(postFooter)에만 (2026-10-10 사용자)
    includables = includables.replace(
        "<b:include cond='data:view.isMultipleItems or data:widgets.Blog.first.headerByline.items.share' data='{ shareButtonClass: &quot;post-share-buttons-top&quot;, overridden: true }' name='maybeAddShareButtons'/>",
        "<b:comment>공유 버튼은 본문 아래(postFooter)에만 둔다</b:comment>")
    includables = includables.replace("post-share-buttons-bottom invisible", "post-share-buttons-bottom")

    out = TEMPLATE
    out = out.replace("__CSS__", parts["css"])
    out = out.replace("__BLOGGER_CSS__", BLOGGER_CSS.strip() + "\n\n" + pc_type_css(parts["css"] + "\n" + BLOGGER_CSS))
    out = out.replace("__NAV_ITEMS__", nav_items())
    out = out.replace("__SITE_DESC__", html_mod.escape(SITE_DESC, quote=True))
    out = out.replace("__LIST_PATH__", LIST_PATH)
    out = out.replace("__TRUMP_LABEL__", TRUMP_LABEL)
    out = out.replace("__TRUMP_LIST_PATH__", TRUMP_LIST_PATH)
    out = out.replace("__NVDA_LABEL__", NVDA_LABEL)
    out = out.replace("__NVDA_LIST_PATH__", NVDA_LIST_PATH)
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
        "            © 2026 ALPHASCOPE. All rights reserved.\n"
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

/* 뷰 전환: 홈 / 목록 / 글 보기.
   홈은 글 목록을 내지 않는다 — 오늘 리포트는 상단 브리핑이 대신한다. */
body[data-pv-view="home"] #pv-post,
body[data-pv-view="home"] #pv-reports { display: none; }
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
.pv-bar-label { padding: 0 4px; font-size: 12px; font-weight: 700; letter-spacing: 1px; color: #64748B; }
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
        "title": "미국 증시 리포트 — 나스닥 사상 최고치 경신, 반도체와 소프트웨어가 함께 끌어올린 하루",
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

PREVIEW_COMMENTS = [   # 우리 댓글(Firestore 문서)과 같은 꼴 — avatar 는 미리보기용 색 (2026-10-14)
    {"id": "c1", "uid": "u1", "name": "김투자", "avatar": "#2563EB", "parent": "", "created": "2026-09-03T00:12:00Z",
     "text": "반도체 비중 확대 의견 잘 봤습니다. 다만 밸류에이션 부담은 어떻게 보시나요?"},
    {"id": "c2", "uid": "owner", "name": "AlphaScope", "avatar": "#DD0000", "parent": "c1", "created": "2026-09-03T01:04:00Z",
     "text": "선행 PER 기준으로는 5년 평균을 웃돌지만, 실적 상향 속도가 더 빨라 부담이 완화되는 구간으로 "
             "보고 있습니다. 다만 가이던스가 꺾이면 되돌림이 클 수 있어 분할 접근을 권합니다."},
    {"id": "c3", "uid": "u3", "name": "장기보유", "avatar": "#14B8A6", "parent": "", "created": "2026-09-03T05:47:00Z",
     "text": "매일 잘 보고 있습니다.\n러셀 2000 지표도 같이 실어주시면 좋겠어요."},
]

PREVIEW_POST_TITLE = "미국 증시 리포트 — 2026년 9월 3일"

FALLBACK_POST_BODY = """<div style="font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;font-size:19px;line-height:34px;color:#333;">

  <img src="__COVER__" alt="데일리 브리핑 커버 이미지" style="width:100%;max-width:1024px;border-radius:8px;margin:0 0 16px 0;display:block;"/>

  <h2 style="color:#111;border-bottom:2px solid #eee;padding-bottom:8px;">오늘 한 줄</h2>
  <div><div>오늘 미국 증시는 3대 지수가 일제히 상승 마감했습니다. 반도체 섹터가 상승을 주도한 가운데
  소프트웨어와 온라인 서비스가 뒤를 받쳤고, 변동성 지수는 15선 아래에서 안정적인 흐름을 유지했습니다.</div></div>

  <h2 style="color:#111;border-bottom:2px solid #eee;padding-bottom:8px;">주요 지수</h2>
  <table style="width:100%;border-collapse:collapse;margin:8px 0;font-size:17px;">
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

  <h2 style="color:#111;border-bottom:2px solid #eee;padding-bottom:8px;">시장 분위기</h2>
  <div><div>위험 자산 선호가 이어지며 방어 섹터에서 성장 섹터로 자금이 옮겨갔습니다.</div></div>

  <h2 style="color:#111;border-bottom:2px solid #eee;padding-bottom:8px;">오늘의 급등주 TOP 5</h2>
  <table style="width:100%;border-collapse:collapse;margin:8px 0;font-size:17px;">
    <tr style="background:#f5f5f5;">
      <th style="padding:8px;border:1px solid #ddd;text-align:left;">종목</th>
      <th style="padding:8px;border:1px solid #ddd;text-align:right;">가격</th>
      <th style="padding:8px;border:1px solid #ddd;text-align:right;">등락률</th>
      <th style="padding:8px;border:1px solid #ddd;text-align:right;">거래량</th>
    </tr>
    <tr>
      <td style="padding:8px;border:1px solid #ddd;">TSLA</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;">$376.37</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;"><span style="color:#d93025;font-weight:bold;">+4.26%</span></td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;">112,905,600</td>
    </tr>
    <tr>
      <td style="padding:8px;border:1px solid #ddd;">NVDA</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;">$228.45</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;"><span style="color:#d93025;font-weight:bold;">+3.71%</span></td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;">198,442,100</td>
    </tr>
    <tr>
      <td style="padding:8px;border:1px solid #ddd;">AVGO</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;">$357.16</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;"><span style="color:#d93025;font-weight:bold;">+2.94%</span></td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;">29,771,200</td>
    </tr>
    <tr>
      <td style="padding:8px;border:1px solid #ddd;">AAPL</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;">$328.21</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;"><span style="color:#d93025;font-weight:bold;">+1.62%</span></td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;">53,370,900</td>
    </tr>
    <tr>
      <td style="padding:8px;border:1px solid #ddd;">GOOGL</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;">$342.48</td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;"><span style="color:#d93025;font-weight:bold;">+1.05%</span></td>
      <td style="padding:8px;border:1px solid #ddd;text-align:right;">26,890,400</td>
    </tr>
  </table>
  <div style="margin-top:6px;"><div>반도체와 전기차가 상승을 이끌었고 거래량도 평균을 크게 웃돌았습니다.</div></div>

  <h2 style="color:#111;border-bottom:2px solid #eee;padding-bottom:8px;">주요 뉴스</h2>
  <ul>
    <li><a href="#" style="color:#1a73e8;">반도체 ETF에 사상 최대 자금 유입</a> — CNBC</li>
    <li><a href="#" style="color:#1a73e8;">연준 위원 "금리 인하 서두를 필요 없다"</a> — Reuters</li>
  </ul>

  <h2 style="color:#111;border-bottom:2px solid #eee;padding-bottom:8px;">종합 — 현재 시장 상태</h2>
  <div><div>상승 추세는 유지되나 지수 상승분이 소수 대형주에 쏠려 있어 참여폭을 함께 봐야 합니다.</div>
  <div>금리 여건은 중립이며 연준의 다음 신호를 기다리는 국면입니다.</div></div>

  <h2 style="color:#111;border-bottom:2px solid #eee;padding-bottom:8px;">주의할 위험요인</h2>
  <div><div>반도체 밸류에이션 부담과 차익 실현 물량이 단기 변동성을 키울 수 있습니다.</div>
  <div>이번 주 발표될 고용지표가 금리 기대를 되돌릴 위험이 남아 있습니다.</div></div>

  <p style="margin-top:24px;font-size:14px;color:#999;border-top:1px solid #eee;padding-top:10px;">
    본 리포트는 데이터 수집(FRED · Yahoo Finance)과 AI 분석(Gemini)을 자동으로 결합해 생성한 테스트 산출물입니다.
    투자 판단의 근거로 활용하지 마십시오. 데이터 출처: FRED, Yahoo Finance, CNBC.<br/>
    기준일: 2026-09-03 · 데이터 갱신: 2026-09-03 21:05 KST
  </p>

</div>"""

SAVED_POST_BODY = "experiments/daily-report/output/report_body.html"

# 홈 두 번째 카드(트럼프 SNS 트렌드)용. 글 보기 탭은 데일리 리포트만 보여주므로
# 이 본문은 홈 카드에만 쓰인다. h2 는 experiments/trump-trend/render_html.py build_body 와 같아야 한다.
SAVED_TRUMP_BODY = "experiments/trump-trend/output/trump_report_body.html"
SAVED_NVDA_BODY = "experiments/nvda-report/output/nvda_report_body.html"
PREVIEW_NVDA_TITLE = "엔비디아 리포트 — 2026년 9월 3일"
PREVIEW_TRUMP_TITLE = "트럼프 SNS 트렌드 — 2026년 9월 3일"
FALLBACK_TRUMP_BODY = """<div style="font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;font-size:19px;line-height:34px;color:#333;">
<h2 style="color:#111;border-bottom:2px solid #eee;padding-bottom:8px;margin-top:28px;">오늘 한 줄</h2>
<div style="font-size:20px;font-weight:bold;color:#111;">지난 24시간 게시물 <b>36</b>건 중 정책 관련 <b>2</b>건, 이벤트 <b>2</b>개. 가장 강한 발언은 <b>Regulation / Artificial Intelligence</b> (강도 10).</div>
<h2 style="color:#111;border-bottom:2px solid #eee;padding-bottom:8px;margin-top:28px;">오늘의 발언</h2>
<table style="width:100%;border-collapse:collapse;"><tr><th>시각</th><th>주제</th></tr><tr><td>10-04 21:23</td><td>Regulation / AI</td></tr></table>
<h2 style="color:#111;border-bottom:2px solid #eee;padding-bottom:8px;margin-top:28px;">무엇이 달라졌나</h2>
<ul style='margin:8px 0 8px 20px;'><li style='margin:4px 0;'>최근 90일간 등장하지 않았던 Regulation / Medicare 주제가 최근 7일간 1건 나타났으며 트렌드 점수 68.8점이 관찰됐다.</li><li style='margin:4px 0;'>Trade / Tariff 주제는 직전 7일간 0건에서 최근 7일간 2건으로 증가한 변화가 관찰됐다.</li><li style='margin:4px 0;'>신규 진입 대상으로는 South Korea와 BAYRY, CVS가 나타났다.</li></ul>
<h2 style="color:#111;border-bottom:2px solid #eee;padding-bottom:8px;margin-top:28px;">내일 볼 것</h2>
<ul style='margin:8px 0 8px 20px;'><li style='margin:4px 0;'>과거 Regulation 이벤트 28건에서 익일 평균 -0.54% 초과 반응이 발언 없는 날 대비 드문 크기(p=0.002)로 관찰된 XLI가 관찰 대상으로 나타났다.</li><li style='margin:4px 0;'>과거 Trade 이벤트 23건에서 +3거래일 평균 2.001% 초과 반응이 발언 없는 날 대비 드문 크기(p=0.002)로 관찰된 AAPL이 관찰 대상으로 나타났다.</li></ul>
<div style="margin-top:32px;padding-top:12px;border-top:1px solid #eee;font-size:15px;color:#777;line-height:20px;">데이터: Truth Social 게시물 공개 아카이브(CNN) · 가격 Yahoo Finance · 거시 일정 FRED. 이 글의 시장 반응 수치는 과거 발언 이후 <b>관찰된 값</b>이며 인과 관계나 향후 방향을 의미하지 않습니다. 투자 권고가 아닙니다.</div>
</div>"""


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


FALLBACK_NVDA_BODY = """<div style="font-size:19px;line-height:34px;color:#333;">
<h2>① 오늘 한 줄</h2>
<div style="font-size:20px;color:#111;"><b>NVDA $229.28</b> (-0.52%) · SPY 대비 -1.12%p · SMH 대비 +0.13%p · AMD 대비 +1.51%p · 거래량 20일 평균의 0.77×</div>
<h2>② 오늘 바뀐 것 (2건)</h2>
<ul><li>수급 중립 · Form 4 — 이사 증여</li><li>기업 긍정 · 월드 모델 스타트업 투자</li></ul>
<h2>⑦ 오늘의 해석</h2>
<ul><li>수급 영역에서 중립 방향의 Form 4 이사 증여 사실이 공시됐다.</li><li>2026년 10월 14일에 CPI 일정이 잡혀 있다.</li><li>데이터센터 매출 QoQ는 직전 분기보다 낮아진 18.4%로 나타났다.</li></ul>
<div style="margin-top:32px;padding-top:12px;border-top:1px solid #eee;font-size:15px;color:#999;">데이터 출처 · 투자 권고가 아닙니다.</div>
</div>"""


def preview_nvda_body():
    """엔비디아 데일리 본문 — 로컬 산출물이 있으면 그것, 없으면 더미."""
    try:
        body = io.open(SAVED_NVDA_BODY, encoding="utf-8").read().strip()
        return body, f"엔비디아 본문({SAVED_NVDA_BODY})"
    except OSError:
        return FALLBACK_NVDA_BODY, "엔비디아 더미 본문"


def preview_trump_body():
    """트럼프 트렌드 본문 — 로컬 산출물이 있으면 그것, 없으면 더미."""
    try:
        body = io.open(SAVED_TRUMP_BODY, encoding="utf-8").read().strip()
        return body, f"트럼프 본문({SAVED_TRUMP_BODY})"
    except OSError:
        return FALLBACK_TRUMP_BODY, "트럼프 더미 본문"


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
        "      <h2 class=\"section-title\" id=\"pv-reports-title\">미국 증시 리포트 목록</h2>\n"
        "      <span class=\"section-note\">AI 자동 생성 · 매 거래일 아침 · 미국장 마감 후</span>\n"
        "    </div>\n"
        "    <div class=\"post-grid\">\n"
        + "\n".join(cards) + "\n"
        "    </div>\n"
        "    <div class=\"blog-pager\">\n"
        "      <a class=\"blog-pager-older-link\" href=\"#\">More posts</a>\n"
        "    </div>\n"
        "  </section>"
    )


def preview_comments():
    """템플릿과 같은 빈 댓글 영역 — 안은 테마 JS "댓글" IIFE 가 PV_COMMENTS_MOCK 으로 그린다 (2026-10-14)."""
    return (
        "      <section class=\"comments\" id=\"comments\" data-post-id=\"preview\"><h3 class=\"comments-title\">댓글</h3></section>"
    )


# 블로거가 실제로 내보내는 공유 위젯 마크업. 아이콘 sprite 는 blogspot 도메인
# 기준이라 로컬에서 못 받아오므로, 같은 클래스에 인라인 도형만 채워 넣는다.
PREVIEW_SHARE_ICON = (
    "<svg class=\"svg-icon-24 touch-icon\" viewBox=\"0 0 24 24\" aria-hidden=\"true\">"
    "<circle cx=\"18\" cy=\"5\" r=\"3\"/><circle cx=\"6\" cy=\"12\" r=\"3\"/>"
    "<circle cx=\"18\" cy=\"19\" r=\"3\"/>"
    "<path d=\"M8.6 10.7l6.8-4M8.6 13.3l6.8 4\" stroke=\"currentColor\" "
    "stroke-width=\"2\" fill=\"none\"/></svg>"
)

PREVIEW_SHARE_PLATFORMS = ["링크 가져오기", "Facebook", "X", "Pinterest", "이메일"]


def preview_share_buttons():
    items = "\n".join(
        "            <li><span class=\"sharing-platform-button\">%s"
        "<span class=\"platform-sharing-text\">%s</span></span></li>"
        % (PREVIEW_SHARE_ICON, html_mod.escape(name, quote=False))
        for name in PREVIEW_SHARE_PLATFORMS
    )
    return (
        "          <div class=\"post-share-buttons post-share-buttons-bottom\">\n"
        "            <div class=\"byline post-share-buttons goog-inline-block\">\n"
        "              <div class=\"sharing\">\n"
        "                <button class=\"sharing-button touch-icon-button\">%s</button>\n"
        "                <div class=\"share-buttons-container\">\n"
        "                  <ul class=\"share-buttons hidden\">\n"
        "%s\n"
        "                  </ul>\n"
        "                </div>\n"
        "              </div>\n"
        "            </div>\n"
        "          </div>" % (PREVIEW_SHARE_ICON, items)
    )


def preview_post():
    body, _ = preview_post_body()
    return (
        "  <div id=\"pv-post\">\n"
        "    <div class=\"post-shell\">\n"
        "      <article class=\"post-outer-container\">\n"
        "        <div class=\"post\">\n"
        "          <h3 class=\"post-title entry-title\">%s</h3>\n"
        "          <div class=\"byline post-author vcard\">글쓴이 <span class=\"fn\">AlphaScope</span></div>\n"
        "          <div class=\"byline post-timestamp\">2026년 9월 3일 오전 6:00</div>\n"
        "          <div class=\"post-body entry-content float-container\">\n"
        "%s\n"
        "          </div>\n"
        "%s\n"
        "          <div class=\"post-bottom\">\n"
        "            <div class=\"post-footer float-container\">\n"
        "              <div class=\"post-labels\">라벨:\n"
        "                <a href=\"#\">시장</a><a href=\"#\">거시경제</a><a href=\"#\">종목</a>\n"
        "              </div>\n"
        "            </div>\n"
        "          </div>\n"
        "        </div>\n"
        "      </article>\n"
        "      <p class=\"post-nav\">\n"
        "        <a class=\"post-nav-list\" href=\"#list\">목록</a>\n"
        "        <button class=\"post-nav-top\" type=\"button\" aria-label=\"맨 위로\">TOP<svg viewBox=\"0 0 22 22\" width=\"22\" height=\"22\" aria-hidden=\"true\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.6\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><circle cx=\"11\" cy=\"11\" r=\"10\"/><path d=\"M11 15.5V7M7.5 10.5 11 7l3.5 3.5\"/></svg></button>\n"
        "      </p>\n"
        "%s\n"
        "    </div>\n"
        "  </div>"
        % (html_mod.escape(PREVIEW_POST_TITLE, quote=False), indent(body, 12),
           preview_share_buttons(), preview_comments())
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
     "source": "CNBC", "published": "2026-09-03 20:41:00", "link": "#",
     "title_ko": "AI 설비투자 전망 상향에 반도체 ETF로 사상 최대 자금 유입",
     "why_ko": "지난주 반도체 펀드에 41억 달러가 들어와 AI 투자 기대가 이어지고 있다."},   # 선정 이유 미리보기 (2026-10-14)
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

    # 상단 브리핑은 블로거 피드에서 최신 글을 읽어 채운다. 글 본문은 글 보기
    # 탭과 같은 것을 써서, 두 화면의 내용이 어긋나 보이지 않게 한다.
    body, _ = preview_post_body()
    trump_body, _ = preview_trump_body()
    nvda_body, _ = preview_nvda_body()

    def one_entry_feed(title, body, href):
        return {
            "feed": {
                "entry": [{
                    "title": {"$t": title},
                    "published": {"$t": "2026-09-03T06:00:00.000+09:00"},
                    "content": {"$t": body},
                    "link": [{"rel": "alternate", "href": href}],
                }]
            }
        }

    feed = one_entry_feed(PREVIEW_POST_TITLE, body, "#post")
    # 트럼프 카드. 글 보기 탭이 데일리 리포트 전용이라 라벨 목록 흉내(#list)로 보낸다.
    trump_feed = one_entry_feed(PREVIEW_TRUMP_TITLE, trump_body, "#list")
    nvda_feed = one_entry_feed(PREVIEW_NVDA_TITLE, nvda_body, "#list")

    return (
        "  var PV_DATA = %s;\n"
        "  var PV_NEWS = %s;\n"
        "  var PV_FEED = %s;\n"
        "  var PV_TRUMP_FEED = %s;\n"
        "  var PV_NVDA_FEED = %s;\n"
        "\n"
        "  /* 디자인만 확인하므로 실제 시세를 부르지 않는다. 피드는 라벨로 가른다. */\n"
        "  window.fetch = function (url) {\n"
        "    var u = String(url), body;\n"
        "    if (u.indexOf('/feeds/posts') >= 0) {\n"
        "      var lab = decodeURIComponent(u);\n"
        "      body = lab.indexOf('트럼프 트렌드') >= 0 ? PV_TRUMP_FEED : lab.indexOf('엔비디아') >= 0 ? PV_NVDA_FEED : PV_FEED;\n"
        "    }\n"
        "    else if (u.indexOf('news.json') >= 0) body = PV_NEWS;\n"
        "    else body = PV_DATA;\n"
        "    return Promise.resolve({ json: function () { return Promise.resolve(body); } });\n"
        "  };\n"
        "\n"
        "  /* 댓글 미리보기 — Firebase 대신 메모리. 로그인 버튼을 누르면 운영자(AlphaScope)로 로그인한 셈이 된다 (2026-10-14) */\n"
        "  var PV_CM = %s, pvUser = null, pvCb = function () {};\n"
        "  window.PV_COMMENTS_MOCK = {\n"
        "    owner: 'owner',\n"
        "    list: function () { return Promise.resolve(PV_CM.slice()); },\n"
        "    add: function (d) { d.id = 'm' + Date.now(); d.created = new Date().toISOString(); PV_CM.push(d); return Promise.resolve(d); },\n"
        "    del: function (id) { PV_CM = PV_CM.filter(function (c) { return c.id !== id; }); return Promise.resolve({}); },\n"
        "    auth: {\n"
        "      onAuth: function (cb) { pvCb = cb; cb(pvUser); },\n"
        "      login: function () { pvUser = { uid: 'owner', name: 'AlphaScope', photo: '' }; pvCb(pvUser); return Promise.resolve(); },\n"
        "      logout: function () { pvUser = null; pvCb(null); return Promise.resolve(); },\n"
        "      token: function () { return Promise.resolve('mock'); }\n"
        "    }\n"
        "  };"
        % (
            json.dumps(data, ensure_ascii=False),
            json.dumps(news, ensure_ascii=False),
            json.dumps(feed, ensure_ascii=False),
            json.dumps(trump_feed, ensure_ascii=False),
            json.dumps(nvda_feed, ensure_ascii=False),
            json.dumps([dict(c, photo=_avatar_data_uri(c["avatar"])) for c in PREVIEW_COMMENTS], ensure_ascii=False),
        )
    )


PREVIEW_SWITCH_JS = """  (function () {
    var body = document.body;
    var buttons = document.querySelectorAll('.pv-bar button');
    var homeLink = document.querySelector('.menu-items .nav-item');

    /* 테마는 홈이 아닌 뷰에 no-dashboard 를 붙인다 (b:class cond=!isHomepage). */
    function setView(view) {
      body.setAttribute('data-pv-view', view);
      body.classList.toggle('no-dashboard', view !== 'home');
      /* 테마의 b:class cond=data:view.isSingleItem 에 해당한다. */
      body.classList.toggle('item-view', view === 'post');
      /* 메뉴의 현재 위치 표시도 뷰를 따라간다 (테마의 b:attr aria-current 흉내). */
      if (homeLink) {
        if (view === 'home') homeLink.setAttribute('aria-current', 'page');
        else homeLink.removeAttribute('aria-current');
      }
      Array.prototype.forEach.call(buttons, function (b) {
        b.setAttribute('aria-pressed', String(b.getAttribute('data-pv-view') === view));
      });
      try { sessionStorage.setItem('pv-view', view); } catch (e) {}
      document.dispatchEvent(new Event('pv-view-change'));
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

    /* 브레이크포인트(1360 / 1180 / 900 / 680) 확인용 폭 표시.
       글 보기에서는 리포트가 실제로 몇 px 로 그려졌는지 같이 보여준다. */
    var readout = document.getElementById('pv-width');
    function showWidth() {
      var text = window.innerWidth + 'px';
      var shell = document.querySelector('#pv-post .post-shell');
      if (shell && body.getAttribute('data-pv-view') === 'post') {
        text += ' · 본문 ' + Math.round(shell.getBoundingClientRect().width) + 'px';
      }
      readout.textContent = text;
    }
    window.addEventListener('resize', showWidth);
    document.addEventListener('pv-view-change', showWidth);
    showWidth();
  })();"""


PREVIEW_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>AlphaScope — 디자인 미리보기</title>
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
    _, trump_source = preview_trump_body()

    out = PREVIEW_TEMPLATE
    out = out.replace("__CSS__", parts["css"])
    out = out.replace("__BLOGGER_CSS__", BLOGGER_CSS.strip() + "\n\n" + pc_type_css(parts["css"] + "\n" + BLOGGER_CSS))
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
        f"글 카드 {len(PREVIEW_POSTS)}개 · 댓글 {len(PREVIEW_COMMENTS)}개, {body_source}, {trump_source}"
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
