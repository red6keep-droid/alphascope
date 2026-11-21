"""종목별 토론방 목업 (2026-11-20 사용자 "가 종목별 토론방으로 목업 만들어 줘").

    python experiments/stock-board/mock_board.py   → output/mock_board_NVDA*.html (목업 서버 `stock-board` 묶음)

종목 페이지 맨 끝 탭 `토론방` — 엔비디아 목업(stock-radar/output/mock_NVDA.html)에 탭 하나를 붙여 그린다. 열면 바로 토론방 탭(#tab-토론방).
화면 세 가지:
  mock_board_NVDA.html        로그인 뒤 — 회원 의견 분위기 · 글 쓰기(열고 닫기) · 최신순/공감순 · 글 5개 + 더 보기 · 내 글(방금) · 가려진 글 · 신고
  mock_board_NVDA-guest.html  로그인 전 — 읽기는 누구나, 쓰기 자리에 구글 로그인
  mock_board_NVDA-empty.html  글이 아직 없을 때
글 · 이름은 예시 값. 인터넷 · AI 0. 실제 구조(쓰기 = Worker → Firestore + R2 사본, 읽기 = R2 사본 + Cloudflare 캐시)는 답변 · 기획에.
"""
import html
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import design_kit as dk  # noqa: E402

OUT = os.path.join(HERE, "output")
BASE = os.path.join(HERE, "..", "stock-radar", "output", "mock_NVDA.html")
TAB = "토론방"
esc = lambda t: html.escape(str(t), quote=False)

# 글 줄 = 블로그 댓글(.comments .cm-*)과 같은 값 — 테마 JS 가 .comments 를 찾아 글 아래 줄을 옮기므로 이름만 .bd 로
CSS = """<style>
.bd-list{list-style:none;margin:0;padding:0;}
.bd-item{display:grid;grid-template-columns:24px minmax(0,1fr);column-gap:7px;align-items:start;padding:18px 0;border-top:1px solid #E2E8F0;}
.bd-item:first-child{border-top:0;}
.bd-av{display:flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:#94A3B8;color:#fff;font-weight:700;font-size:12px;line-height:24px;}
.bd-head{display:flex;align-items:center;flex-wrap:wrap;gap:4px 10px;line-height:24px;}
.bd-name{font-size:14px;line-height:20px;color:#111;}
.bd-date{font-size:14px;line-height:20px;color:#7A7A7A;white-space:nowrap;}
.bd-text{margin:4px 0 0;font-size:16px;line-height:26px;color:#333;white-space:pre-wrap;overflow-wrap:anywhere;}
.bd-text.is-hidden{color:#94A3B8;font-size:14px;line-height:20px;}
.bd-acts{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;}
.bd-btn{display:inline-flex;align-items:center;gap:4px;margin:0;padding:5px 12px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;font:inherit;font-size:14px;line-height:22px;font-weight:700;color:#111;cursor:pointer;-webkit-tap-highlight-color:transparent;}
.bd-btn.is-on{border-color:#111;}
.bd-btn.is-quiet{font-weight:400;color:#6B7280;}
.bd-wide{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;box-sizing:border-box;margin:0;padding:11px 12px;background:#fff;border:1px solid #B5BAC0;border-radius:8px;font:inherit;font-size:16px;line-height:24px;font-weight:700;color:#111;cursor:pointer;text-align:center;}
.bd-wide.is-dark{background:#111;border-color:#111;color:#fff;}
.bd-sort{display:flex;gap:6px;margin:20px 0 4px;}
.bd-chip{padding:5px 12px;border:1px solid #E2E8F0;border-radius:16px;background:#fff;font:inherit;font-size:14px;line-height:22px;color:#6B7280;cursor:pointer;}
.bd-chip.is-on{border-color:#111;color:#111;font-weight:700;}
.bd-write{margin:12px 0 0;padding:14px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;}
.bd-write[hidden],.bd-report[hidden],.bd-more-box[hidden]{display:none;}
.bd-dirs{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 12px;}
.bd-ta{display:block;width:100%;box-sizing:border-box;min-height:120px;padding:10px 12px;border:1px solid #CBD5E1;border-radius:8px;background:#fff;font:inherit;font-size:16px;line-height:26px;color:#111;resize:vertical;}
.bd-meta{display:flex;justify-content:space-between;margin:6px 0 12px;font-size:14px;line-height:20px;color:#6B7280;}
.bd-err{margin:0 0 12px;font-size:14px;line-height:20px;color:#B91C1C;}
.bd-err[hidden]{display:none;}
.bd-report{grid-column:2;margin-top:10px;padding:12px;border:1px solid #E2E8F0;border-radius:8px;background:#fff;}
.bd-mine{grid-column:2;margin:6px 0 0;font-size:14px;line-height:20px;color:#6B7280;}
.bd-sec{font-size:16px;line-height:24px;font-weight:700;color:#111;margin:0 0 8px;}
.bd-bar{display:flex;height:10px;border-radius:5px;overflow:hidden;margin:10px 0 8px;background:#E2E8F0;}
.bd-legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:14px;line-height:20px;color:#333;}
</style>"""

DIR_PILL = {"up": dk.pill("▲상승", "positive", bare=True), "down": dk.pill("▼하락", "negative", bare=True), "flat": dk.pill("중립", "area", bare=True), "": ""}

# (이름, 머리글자, 언제, 방향, 글, 공감, 답글, 상태) — 예시
POSTS = [
    ("반도체곰", "반", "3분 전", "down", "실적 발표 전에 너무 많이 올라서 발표 날 크게 흔들릴 것 같습니다. 작년에도 발표 다음 날 빠졌던 기억이 있어요.", 4, 2, ""),
    ("데이터센터", "데", "12분 전", "up", "클라우드 회사들이 내년 투자를 더 늘린다고 했으니 수요는 아직 괜찮다고 봅니다.", 11, 5, ""),
    ("", "", "25분 전", "", "", 0, 0, "hidden"),
    ("장기보유", "장", "1시간 전", "flat", "오늘 거래량이 평소보다 적네요. 발표까지는 옆으로 갈 것 같습니다.", 2, 0, ""),
    ("엔비디아팬", "엔", "2시간 전", "up", "블랙웰 다음 제품 일정이 앞당겨졌다는 기사 보셨나요? 공식 발표인지 확인해 보고 싶네요.", 7, 3, ""),
    ("조심조심", "조", "3시간 전", "down", "중국 수출 규제 소식이 또 나오면 단기로는 부담일 듯합니다.", 5, 1, ""),
    ("새내기", "새", "5시간 전", "", "엔비디아는 실적 발표가 장 마감 뒤에 나오나요? 처음이라 여쭤봅니다.", 3, 4, ""),
]
MORE = 41   # 더 보기 뒤에 남은 글 수(예시)


def post(p, i, member=True):
    name, ini, when, d, text, likes, replies, state = p
    if state == "hidden":   # 신고 3번이면 자동으로 가린다 — 운영자가 보고 되살리거나 지운다
        return ('<li class="bd-item"><span class="bd-av" style="background:#CBD5E1;"></span><div>'
                '<p class="bd-text is-hidden">신고가 쌓여 가려진 글입니다. 운영자가 확인하고 있습니다.</p></div></li>')
    acts = (f'<button class="bd-btn" type="button" data-like="{likes}">공감 <span>{likes}</span></button>'
            f'<button class="bd-btn" type="button">답글 {replies}</button>'
            + (f'<button class="bd-btn is-quiet" type="button" data-report="{i}">신고</button>' if member else ""))
    report = (f'<div class="bd-report" data-report-box="{i}" hidden><div class="bd-sec" style="font-size:14px;line-height:20px;">신고하는 이유</div>'
              '<div class="bd-dirs" style="margin:6px 0 10px;">'
              + "".join(f'<button class="bd-chip" type="button" data-pick="1">{t}</button>' for t in ("광고 · 리딩방", "욕설 · 비방", "거짓 정보", "도배"))
              + '</div><button class="bd-btn" type="button" data-report-send="1">신고하기</button></div>') if member else ""
    return (f'<li class="bd-item"><span class="bd-av">{esc(ini)}</span><div>'
            f'<div class="bd-head"><span class="bd-name">{esc(name)}</span>{DIR_PILL[d]}<span class="bd-date">{when}</span></div>'
            f'<p class="bd-text">{esc(text)}</p><div class="bd-acts">{acts}</div></div>{report}</li>')


def my_post():
    """방금 쓴 내 글 — 쓴 사람 화면에는 바로 붙여 보여 준다."""
    return ('<li class="bd-item"><span class="bd-av" style="background:#475569;">나</span><div>'
            f'<div class="bd-head"><span class="bd-name">주린이탈출</span>{DIR_PILL["up"]}<span class="bd-date">방금</span></div>'
            '<p class="bd-text">발표 전까지는 들고 가 보려고 합니다. 다들 발표 날 어떻게 하시나요?</p>'
            '<div class="bd-acts"><button class="bd-btn" type="button">공감 0</button><button class="bd-btn" type="button">고치기</button>'
            '<button class="bd-btn is-quiet" type="button">지우기</button></div></div>'
            '<p class="bd-mine">다른 분들 화면에는 1분 안에 보입니다.</p></li>')


def mood_card():
    """회원들은 어느 쪽인가? — 최근 7일 글에 쓴 사람이 고른 방향. 카드 색 = 답 방향(가이드라인 7-1). 우리 판정이 아니라 회원 생각을 센 것."""
    up, down, flat = 23, 11, 6
    tot = up + down + flat
    seg = lambda n, c: f'<span style="width:{round(n * 100 / tot)}%;background:{c};"></span>'
    body = ('<div class="bd-sec">회원들은 어느 쪽인가?</div>'
            f'<div style="font-size:18px;line-height:28px;font-weight:700;color:#B91C1C;">{dk.tri_span(True, 18)}상승 쪽이 많습니다</div>'
            f'<div class="bd-bar">{seg(up, "#ED8E87")}{seg(flat, "#CBD5E1")}{seg(down, "#82B1F0")}</div>'
            f'<div class="bd-legend"><span>▲상승 {up}</span><span>중립 {flat}</span><span>▼하락 {down}</span></div>'
            + dk.excl_note("최근 7일 글에서 쓴 분이 고른 방향을 센 것입니다. Newfact의 판단이 아닙니다.", margin="10px 0 0"))
    return dk.dcard(body, theme="positive")


def write_box():
    dirs = "".join(f'<button class="bd-chip{" is-on" if k == "" else ""}" type="button" data-dir="{k}">{t}</button>'
                   for k, t in (("up", "▲상승"), ("down", "▼하락"), ("flat", "중립"), ("", "고르지 않음")))
    return ('<div class="bd-write" data-write hidden>'
            '<div class="bd-sec" style="margin:0;">어느 쪽으로 보시나요?</div>'
            f'<div class="bd-dirs">{dirs}</div>'
            '<textarea class="bd-ta" data-ta maxlength="1000" placeholder="엔비디아에 대한 생각을 적어 주세요. 오픈채팅 · 텔레그램 링크와 연락처는 올릴 수 없습니다."></textarea>'
            '<div class="bd-meta"><span data-count>0 / 1000</span><span>오늘 남은 글 9개</span></div>'
            '<p class="bd-err" data-err hidden>오픈채팅 · 텔레그램 링크는 올릴 수 없습니다. 링크를 지우고 다시 올려 주세요.</p>'
            '<button class="bd-wide is-dark" type="button" data-send>올리기</button></div>')


def rules():
    return dk.excl_note("회원이 쓴 의견이며 Newfact의 의견이 아닙니다. 투자 권유가 아니고, 판단과 책임은 읽는 분에게 있습니다.", margin="12px 0 0")


def tab(member=True, empty=False):
    lead = f'<p style="{dk.TAB_LEAD_GAP}font-size:{dk.BODY};line-height:{dk.LH_BODY};color:#333;word-break:keep-all;">엔비디아를 보는 회원들의 생각을 나누는 곳입니다.</p>'
    if empty:
        return (lead + dk.dcard('<div style="font-size:17px;line-height:26px;font-weight:700;color:#111;">아직 글이 없습니다</div>'
                                '<div style="font-size:15px;line-height:24px;color:#333;margin:4px 0 0;">엔비디아에 대한 첫 이야기를 남겨 주세요.</div>')
                + '<button class="bd-wide" type="button" data-open-write>글 쓰기</button>' + write_box() + rules())
    if member:
        top = '<button class="bd-wide" type="button" data-open-write style="margin-top:4px;">글 쓰기</button>' + write_box()
    else:
        top = (f'<a class="bd-wide" style="margin-top:4px;text-decoration:none;">{_g_logo()}구글 계정으로 글 쓰기</a>'
               '<p style="font-size:14px;line-height:20px;color:#6B7280;text-align:center;margin:6px 0 0;">읽기는 누구나 됩니다. 글 쓰기 · 공감 · 신고는 댓글과 같은 로그인으로 합니다.</p>')
    sort = ('<div class="bd-sort"><button class="bd-chip is-on" type="button">최신순</button>'
            '<button class="bd-chip" type="button">공감순</button></div>')
    items = (my_post() if member else "") + "".join(post(p, i, member) for i, p in enumerate(POSTS[:5]))
    rest = "".join(post(p, i + 5, member) for i, p in enumerate(POSTS[5:]))
    more = (f'<ul class="bd-list bd-more-box" data-more-box hidden>{rest}</ul>'
            f'<button class="bd-wide" type="button" data-more style="margin-top:6px;">글 {len(POSTS) - 5 + MORE}개 더 보기</button>')
    return lead + mood_card() + top + rules() + sort + f'<ul class="bd-list">{items}</ul>' + more


def _g_logo():
    return ('<svg viewBox="0 0 18 18" width="18" height="18" aria-hidden="true"><path fill="#4285F4" d="M17.6 9.2c0-.6-.1-1.2-.2-1.8H9v3.4h4.8a4.1 4.1 0 0 1-1.8 2.7v2.2h2.9c1.7-1.6 2.7-3.9 2.7-6.5z"/>'
            '<path fill="#34A853" d="M9 18c2.4 0 4.5-.8 6-2.2l-2.9-2.2c-.8.5-1.8.9-3.1.9-2.4 0-4.4-1.6-5.1-3.8H.9v2.3A9 9 0 0 0 9 18z"/>'
            '<path fill="#FBBC05" d="M3.9 10.7a5.4 5.4 0 0 1 0-3.4V5H.9a9 9 0 0 0 0 8l3-2.3z"/>'
            '<path fill="#EA4335" d="M9 3.6c1.3 0 2.5.5 3.5 1.4l2.6-2.6A9 9 0 0 0 .9 5l3 2.3C4.6 5.2 6.6 3.6 9 3.6z"/></svg>')


JS = """<script>(function(){
var q=function(s,r){return (r||document).querySelector(s);},qa=function(s,r){return [].slice.call((r||document).querySelectorAll(s));};
qa('[data-open-write]').forEach(function(b){b.addEventListener('click',function(){var w=q('[data-write]');w.hidden=!w.hidden;b.textContent=w.hidden?'글 쓰기':'닫기';if(!w.hidden)q('[data-ta]').focus();});});
qa('[data-dir]').forEach(function(b){b.addEventListener('click',function(){qa('[data-dir]').forEach(function(x){x.classList.remove('is-on');});b.classList.add('is-on');});});
var ta=q('[data-ta]');if(ta)ta.addEventListener('input',function(){q('[data-count]').textContent=ta.value.length+' / 1000';q('[data-err]').hidden=true;});
var send=q('[data-send]');if(send)send.addEventListener('click',function(){if(/open\\.kakao|t\\.me\\/|텔레그램|오픈채팅/i.test(ta.value)){q('[data-err]').hidden=false;return;}alert('목업: 올리면 목록 맨 위에 바로 붙고, 다른 분 화면에는 1분 안에 보입니다.');});
qa('[data-like]').forEach(function(b){b.addEventListener('click',function(){var on=b.classList.toggle('is-on'),n=+b.getAttribute('data-like')+(on?1:0);b.querySelector('span').textContent=n;});});
qa('[data-report]').forEach(function(b){b.addEventListener('click',function(){var x=q('[data-report-box="'+b.getAttribute('data-report')+'"]');x.hidden=!x.hidden;});});
qa('[data-pick]').forEach(function(b){b.addEventListener('click',function(){b.classList.toggle('is-on');});});
qa('[data-report-send]').forEach(function(b){b.addEventListener('click',function(){b.closest('.bd-report').innerHTML='<p class=\"bd-text is-hidden\" style=\"margin:0;\">신고를 받았습니다. 같은 글에 신고가 3번 쌓이면 자동으로 가리고 운영자가 확인합니다.</p>';});});
var mb=q('[data-more]');if(mb)mb.addEventListener('click',function(){q('[data-more-box]').hidden=false;mb.textContent='글 20개 더 보기';});
})();</script>"""


def build(name, member=True, empty=False):
    page = open(BASE, encoding="utf-8").read()
    add = dk.h2(TAB, tab=TAB) + CSS + tab(member, empty)
    end = page.index('</div><div class="post-share-buttons')   # 글 본문(post-body) 끝 = 마지막 탭 뒤
    page = page[:end] + add + page[end:]
    page = re.sub(r"(<body[^>]*>)", r"\1<script>if(!location.hash)history.replaceState(null,'','#tab-'+encodeURIComponent('토론방'));</script>", page, count=1)
    page = page.replace("</body>", JS + "</body>", 1)
    open(os.path.join(OUT, name), "w", encoding="utf-8").write(page)
    print(f"[토론방] {name}")


def main():
    os.makedirs(OUT, exist_ok=True)
    build("mock_board_NVDA.html")
    build("mock_board_NVDA-guest.html", member=False)
    build("mock_board_NVDA-empty.html", empty=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
