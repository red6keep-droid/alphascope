"""토론 모아보기 목업 — 하단 메뉴 `토론` 칸이 여는 화면 (2026-11-22 사용자: 네이버페이 증권 토론 탭 캡처, "그렇게 해").

  output/mock_board.html        회원 — 추천 · HOT · MY 탭, 토론방 줄, 실시간 키워드, 어디에 달린 글 꼬리표
  output/mock_board-guest.html  로그인 전 — MY 탭 누르면 로그인 창, 연필 = 로그인 창

실제는 Blogger 고정 페이지 하나(/p/board.html)가 board.newfact.app/v1/feed/{rec|hot|kw}.json 을 읽어 그린다(앱도 같은 파일).
  추천 = 최근 7일 글, 좋아요 − 싫어요 순(오래된 글이 늘 위에 남지 않게 7일만)
  HOT  = 최근 24시간 답글 · 좋아요를 그 자리 평소(지난 7일 하루 평균)와 견준 배수 순 — 큰 종목만 늘 위에 오지 않게(헌법 제1조 비교 대상)
  MY   = 내가 쓴 글 · 답글 단 글(GET /v1/me/items)
  실시간 키워드 = 글 제목 속 우리 종목 · 테마 사전 단어의 24시간 횟수 ÷ 평소 7일 하루 평균, 크게 늘어난 것만(AI 안 씀)
글 칸 = 토론 목록과 같은 꼴(mock_comments.item 모양) + 맨 위 꼬리표 = 어디에 달린 글(누르면 그 페이지 토론). 누르면 이미 만든 글 화면.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, EXP)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(EXP, "mock-invest"))
sys.path.insert(0, os.path.join(EXP, "my-stocks"))
import design_kit as dk  # noqa: E402
import mock_comments as mc  # noqa: E402
import mock_invest as mi  # noqa: E402
import mock_my_stocks as MS  # noqa: E402

esc = mc.esc
OUT = os.path.join(HERE, "output")
LIST = "mock_comments_member.html"

# 토론방 = 우리 자리(열쇠) — 이름 · 한 줄 설명 · 표시
ROOMS = [("all", "전체 토론방", "", ""), ("market-kr", "한국 증시", "오늘 한국 시장은?", "KR"), ("market-us", "미국 증시", "밤새 미국 시장은?", "US"),
         ("hot", "핫이슈", "엔비디아 실적 뒤 반도체", "HOT"), ("stock-nvda", "엔비디아", "NVDA", "NVDA"),
         ("stock-005930", "삼성전자", "005930", "005930"), ("stock-000660", "SK하이닉스", "000660", "000660")]
# 실시간 키워드 — (말, 24시간 횟수, 평소 하루 평균)
KEYWORDS = [("반도체", 42, 9), ("엔비디아 실적", 31, 4), ("환율", 18, 6), ("HBM", 14, 3), ("배당", 11, 4), ("금리 인하", 9, 3),
            ("2차전지", 8, 3), ("자사주", 7, 2)]
# 글 — (자리 이름, 자리 열쇠, 별명, 시각, 제목, 본문, 좋아요, 싫어요, 답글, 24시간 반응, 평소 하루 반응)
POSTS = [
    ("11.18 증시 시황", "market-kr", "반도체곰", "11.18 16:10", "오늘은 반도체 두 종목만 오른 날", "오늘 오른 건 반도체 두 종목 덕이고 나머지는 조용했던 것 같아요.", 12, 0, 7, 38, 6),
    ("엔비디아", "stock-nvda", "새벽장지기", "11.20 07:12", "실적 좋았는데 왜 빠졌을까요", "매출은 예상보다 높았는데 다음 분기 안내가 기대에 못 미쳤다는 말이 많네요.", 48, 6, 23, 120, 14),
    ("핫이슈 · 엔비디아 실적 뒤 반도체", "hot", "적립왕", "11.20 08:30", "하이닉스도 같이 빠질까 걱정입니다", "작년에도 엔비디아 실적 뒤 일주일은 같이 움직였던 기억이 있어요.", 31, 4, 15, 64, 5),
    ("미국 증시 · 11.20 마감", "market-us", "달러모으기", "11.20 07:40", "나스닥만 빠지고 다우는 올랐네요", "기술주에서 돈이 빠져 다른 업종으로 간 날 같습니다.", 22, 2, 9, 30, 8),
    ("삼성전자", "stock-005930", "느긋한개미", "11.19 18:05", "배당 기준일 지나고 어떻게 보세요", "배당 받고 나면 빠지는 경우가 많다던데 이번엔 어떨지 궁금합니다.", 19, 3, 11, 12, 7),
    ("SK하이닉스", "stock-000660", "차트탐험가", "11.19 16:20", "HBM 이야기 나오면 늘 오르네요", "기사 나올 때마다 같이 움직이는 게 신기합니다.", 27, 5, 6, 9, 6),
    ("주식 공부 3편", "p-study-3", "공부벌레", "11.17 21:05", "분할 매수는 몇 번으로 나누는 게 좋을까요?", "글 읽고 나니 세 번이 적당한지 다섯 번이 나은지 헷갈립니다.", 15, 0, 5, 3, 2),
]
MINE = [0, 4]   # MY 탭 = 내가 쓴 글 · 답글 단 글(목업: 이 두 글)

CSS = """<style>
/* 토론 모아보기 (2026-11-22 사용자) — 글 칸은 토론 목록(.comments)과 같은 꼴 */
.bd-tabs{display:flex;gap:4px;margin:0 0 14px;padding:4px;border-radius:12px;background:#F1F5F9;}
.bd-tab{flex:1;margin:0;padding:8px 0;border:0;border-radius:9px;background:none;font:inherit;font-size:16px;line-height:24px;font-weight:400;color:#6B7280;cursor:pointer;-webkit-tap-highlight-color:transparent;}
.bd-tab[aria-selected="true"]{background:#fff;color:#111;font-weight:700;box-shadow:0 1px 2px rgba(15,23,42,.08);}
.bd-rooms{display:flex;gap:8px;margin:0 -16px 20px;padding:0 16px;overflow-x:auto;scrollbar-width:none;}
.bd-rooms::-webkit-scrollbar{display:none;}
.bd-room{flex:none;display:flex;align-items:center;gap:8px;min-height:56px;padding:8px 14px;box-sizing:border-box;border:1px solid #E2E8F0;border-radius:12px;background:#fff;color:#111;text-decoration:none;-webkit-tap-highlight-color:transparent;}
.bd-room.is-on{border-color:#111;}
.bd-room b{display:block;color:#111;font-size:16px;line-height:24px;font-weight:700;white-space:nowrap;}
.bd-room small{display:block;font-size:13px;line-height:19px;color:#6B7280;white-space:nowrap;}
.bd-room img,.bd-room .bd-ico{flex:none;width:32px;height:32px;border-radius:50%;}
.bd-room .bd-ico{display:flex;align-items:center;justify-content:center;background:#F1F5F9;font-family:var(--num);font-size:12px;line-height:16px;font-weight:700;color:#333;}
.bd-room .bd-ico.is-hot{background:#FFF1E6;color:#E8710A;}
.bd-room .bd-ico svg{width:18px;height:18px;}
.bd-h{display:flex;align-items:center;gap:6px;margin:0 0 4px;font-size:19px;line-height:28px;font-weight:700;color:#111;}
.bd-h-sub{margin:0 0 10px;font-size:13px;line-height:19px;color:#6B7280;word-break:keep-all;}
.bd-kws{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 24px;}
.bd-kw{display:inline-flex;align-items:center;gap:6px;margin:0;padding:6px 12px;border:0;border-radius:8px;background:#F1F5F9;font:inherit;font-size:16px;line-height:24px;color:#333;cursor:pointer;-webkit-tap-highlight-color:transparent;}
.bd-kw small{font-family:var(--num);font-size:13px;line-height:19px;color:#E8710A;font-weight:700;}
.bd-kw.is-on{background:#111;color:#fff;}
.bd-kw.is-on small{color:#FDBA74;}
.bd-basis{display:flex;align-items:center;justify-content:space-between;margin:0 0 4px;padding:0 0 10px;border-bottom:1px solid #E2E8F0;font-size:13px;line-height:19px;color:#6B7280;}
.bd-list[hidden]{display:none;}
.comments .cv-tag{color:#333;text-decoration:none;}
.bd-hot{margin:6px 0 0;font-size:13px;line-height:19px;color:#6B7280;}
.bd-hot b{font-family:var(--num);color:#E8710A;font-weight:700;}
.bd-empty{padding:28px 0;text-align:center;font-size:16px;line-height:24px;color:#6B7280;}
</style>"""

FLAME = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
         + mi.ICON["hot"] + '</svg>')
ALL = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
       + mi.ICON["board"] + '</svg>')


def room_ico(mark):
    if mark == "":
        return f'<span class="bd-ico">{ALL}</span>'
    if mark == "HOT":
        return f'<span class="bd-ico is-hot">{FLAME}</span>'
    if mark in ("KR", "US"):
        return f'<span class="bd-ico">{"한국" if mark == "KR" else "미국"}</span>'
    return dk.ticker_logo(mark, 32)


def rooms():
    return '<div class="bd-rooms">' + "".join(
        f'<a class="bd-room{" is-on" if k == "all" else ""}" href="{"#" if k == "all" else LIST}">{room_ico(m)}<span><b>{esc(n)}</b>'
        + (f'<small>{esc(d)}</small>' if d else "") + '</span></a>' for k, n, d, m in ROOMS) + '</div>'


def keywords():
    chips = "".join(f'<button class="bd-kw" type="button" data-kw="{esc(w)}">{esc(w)}<small>×{n / base:.1f}</small></button>' for w, n, base in KEYWORDS)
    return ('<div class="bd-h">실시간 키워드</div>'
            '<p class="bd-h-sub">지난 24시간 글 제목에 나온 횟수를 평소(지난 7일 하루 평균)와 견줘 많이 늘어난 말입니다. ×는 평소의 몇 배인지입니다.</p>'
            f'<div class="bd-kws">{chips}</div>')


def react_btns(up, down, member):
    need = "" if member else " data-need-login"
    return (f'<button class="cv-react" type="button" data-react="up"{need} aria-label="좋아요 {up}">{mc.UP_ICON}<span>{up}</span></button>'
            f'<button class="cv-react" type="button" data-react="down"{need} aria-label="싫어요 {down}">{mc.DOWN_ICON}<span>{down}</span></button>')


def row(i, p, member, hot=False):
    where, key, name, when, title, text, up, down, nrep, h24, base = p
    link = "mock_comments_thread.html" if member else "mock_comments_thread-guest.html"
    hot_line = f'<p class="bd-hot">지난 24시간 반응 <b>{h24}</b> · 평소 하루 {base} (<b>×{h24 / base:.1f}</b>)</p>' if hot else ""
    return (f'<li class="cv-item" data-title="{esc(title)}"><a class="cv-tag" href="{LIST}">{esc(where)}</a>{mc.head(name, when, f"b{i}{int(hot)}", member)}'
            f'<a class="cv-main" href="{link}"><div class="cv-title">{esc(title)}</div><p class="cv-text">{esc(text)}</p></a>{hot_line}'
            f'<div class="cv-foot">{react_btns(up, down, member)}'
            f'<a class="cv-reply{" has" if nrep else ""}" href="{link}" aria-label="답글 {nrep}개">{mc.BUBBLE}<span>{nrep}</span></a></div>'
            f'{mc.menu_box(f"b{i}{int(hot)}", False) if member else ""}</li>')


def lists(member):
    rec = sorted(range(len(POSTS)), key=lambda i: -(POSTS[i][6] - POSTS[i][7]))
    hot = sorted(range(len(POSTS)), key=lambda i: -(POSTS[i][9] / POSTS[i][10]))
    out = (f'<div class="bd-list" data-list="rec"><div class="bd-basis"><span>최근 7일 · 좋아요 많은 순</span></div>'
           f'<ol class="cv-list">{"".join(row(i, POSTS[i], member) for i in rec)}</ol></div>'
           f'<div class="bd-list" data-list="hot" hidden><div class="bd-basis"><span>지난 24시간 반응이 평소보다 많이 늘어난 순</span></div>'
           f'<ol class="cv-list">{"".join(row(i, POSTS[i], member, hot=True) for i in hot)}</ol></div>')
    if member:
        out += (f'<div class="bd-list" data-list="my" hidden><div class="bd-basis"><span>내가 쓴 글 · 답글 단 글</span>'
                f'<a class="cv-myprof" href="mock_comments_profile.html">내 프로필</a></div>'
                f'<ol class="cv-list">{"".join(row(i, POSTS[i], member) for i in MINE)}</ol></div>')
    return out


JS = """<script>(function(){
var q=function(s,r){return (r||document).querySelector(s);},qa=function(s,r){return [].slice.call((r||document).querySelectorAll(s));};
qa('[data-btab]').forEach(function(t){t.addEventListener('click',function(){var k=t.getAttribute('data-btab');
if(k==='my'&&!q('[data-list="my"]')){var w=q('[data-win="login"]');if(w)w.hidden=false;return;}
qa('[data-btab]').forEach(function(x){x.setAttribute('aria-selected',String(x===t));});qa('[data-list]').forEach(function(l){l.hidden=l.getAttribute('data-list')!==k;});});});
qa('[data-kw]').forEach(function(b){b.addEventListener('click',function(){var on=!b.classList.contains('is-on'),w=b.getAttribute('data-kw');
qa('[data-kw]').forEach(function(x){x.classList.remove('is-on');});if(on)b.classList.add('is-on');
qa('.bd-list .cv-item').forEach(function(li){li.hidden=on&&li.getAttribute('data-title').indexOf(w.split(' ')[0])<0;});});});
var fab=q('.cv-fab');if(fab)fab.addEventListener('click',function(){var w=q('[data-win="'+(fab.hasAttribute('data-guest')?'login':'where')+'"]');if(w)w.hidden=false;});
})();</script>"""


def where_win():
    """연필 = 어느 토론방에 쓸지 먼저 고른다 — 글은 늘 한 자리(페이지)에 붙는다(자리 없는 글은 없음)."""
    rows = "".join(f'<a class="cv-sym-row" href="mock_comments_write.html">{esc(n)}<small>{esc(d)}</small></a>' for k, n, d, m in ROOMS if k != "all")
    return mc.win("where", "어느 토론방에 쓸까요?", rows + '<p class="cv-rules-sub">다른 종목은 종목 페이지의 토론에서 쓸 수 있습니다.</p>')


def build(name, member):
    tabs = "".join(f'<button class="bd-tab" type="button" role="tab" data-btab="{k}" aria-selected="{str(k == "rec").lower()}">{t}</button>'
                   for k, t in (("rec", "추천"), ("hot", "HOT"), ("my", "MY")))
    body = (CSS + f'<div class="bd-tabs" role="tablist">{tabs}</div>' + rooms() + keywords()
            + f'<section class="comments">{lists(member)}{mc.note()}</section>')
    path = dk.write_mock(MS.head_label("토론") + dk.align_titles(dk.WRAP_OPEN + body + dk.WRAP_CLOSE), os.path.join(OUT, name), "토론")
    if not path:
        return
    pg = open(path, encoding="utf-8").read()
    fab = f'<button class="cv-fab" type="button" aria-label="글쓰기"{"" if member else " data-guest"}>{mc.PENCIL}</button>'
    login = mc.win("login", "로그인하시겠습니까?", '로그인이 필요한 서비스입니다.<div class="cv-btns"><button class="cv-no" type="button" data-win-close>아니오</button>'
                   '<button class="cv-yes" type="button" data-login-go>로그인하기</button></div>')
    wins = login + (where_win() if member else "")
    closer = ("<script>document.querySelectorAll('[data-win]').forEach(function(w){w.addEventListener('click',function(e){"
              "if(e.target===w||e.target.closest('[data-win-close]'))w.hidden=true;});});</script>")
    nav = mi.nav_html("a", "board", unread=member) if member else mi.NAV_CSS + mi.theme_tabbar() + \
        "<script>setTimeout(function(){var a=document.querySelector(\".as-tabbar a[data-tab='board']\");if(a)a.classList.add('on');},0);</script>"
    pg = pg.replace("</head>", mc.CSS + "</head>", 1).replace("</body>", MS.MOCK_JS + fab + wins + closer + JS + nav + "</body>", 1)
    pg = pg.replace("<title>토론", "<title>토론 모아보기" + ("" if member else " · 로그인 전"), 1)
    open(path, "w", encoding="utf-8").write(pg)
    print(f"[토론] {name}")


def main():
    build("mock_board.html", True)
    build("mock_board-guest.html", False)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
