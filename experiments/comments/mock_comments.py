"""댓글 다듬기 목업.

    python experiments/comments/mock_comments.py   → output/mock_comments_*.html (목업 서버 `comments` 묶음)

증시 시황 글 목업(market-commentary/output/mock_story.html) 아래 버튼 줄에 `댓글` 을 붙이고 댓글 판을 연 채로 그린다.

구조:
  목록   글마다 이름 + 오른쪽 날짜 → 제목(굵게) → 글 → 말풍선 아이콘 + 답글 수. 최신이 위. 글 · 아이콘을 누르면 글 화면으로.
         쓰기 = 오른쪽 아래 동그란 연필 버튼(누르면 쓰기 창: 제목 + 글). 로그인 전이면 로그인 창.
  글 화면 `댓글 목록` 으로 돌아가기 → 그 사람 글(제목 · 날짜 · 글) → `답글 n` → 입력 칸 → 안내 상자 → 답글들(이름 + 오른쪽 날짜).
         로그인 전 입력 칸 = `답글을 쓰려면 로그인해 주세요` 상자 → 누르면 `로그인하시겠습니까?` 창(아니오 · 로그인하기).
  안내 상자 = 신고 3번 자동 가림 · 링크 막기(우리가 실제로 하는 것만 적는다 — AI 감지는 없다).
  그 밖: 점 세 개 = 신고(내 글은 삭제) · 가려진 글 · 날짜 줄(시황은 댓글이 날짜를 넘어 이어진다) · 오늘 남은 댓글 · 별명.
화면:
  mock_comments_member.html         목록 — 로그인 뒤
  mock_comments_guest.html          목록 — 로그인 전
  mock_comments_thread.html         글 화면 — 로그인 뒤
  mock_comments_thread-guest.html   글 화면 — 로그인 전
  mock_comments_first.html          처음 쓸 때 — 연필 버튼 → 프로필 만들기 창 → 운영 원칙 창 → 프로필 설정(추천 별명 · 소개)
  mock_comments_write.html          글쓰기 — 화면 전체(제목 · 스티커 · 종목 붙이기 · 내용), 예시로 채운 채 열림
  mock_comments_profile.html        내 프로필 — 별명 · 소개 · 내가 쓴 글
스티커 = 주식 공부 캐릭터 컷(course/chars/c_*.webp → output/stickers/ 사본). 종목 카드 값은 예시.
프로필 그림 = 사용자 그림 24종(동물 a01~a12 · 일반 p01~p12) — cut_avatars.py 가 output/avatars/ 에 자른다(2026-11-22, 수정 모음 P631).
댓글 · 별명은 예시 값. 인터넷 · AI 0. 테마 댓글 JS 는 data-post-id 가 없어 이 칸을 건드리지 않는다.
"""
import html
import json
import hashlib
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import design_kit as dk  # noqa: E402

OUT = os.path.join(HERE, "output")
BASE = os.path.join(HERE, "..", "market-commentary", "output", "mock_story.html")
esc = lambda t: html.escape(str(t), quote=False)

# 새 구조 값 — 글씨 · 색 · 버튼은 블로그 댓글(.comments .cm-*) · 팝업(.rt-pop*) 것을 그대로 쓴다
CSS = """<style>
.comments .cv-list{list-style:none;margin:0;padding:0;}
.comments .cv-item{padding:18px 0;border-top:1px solid #E2E8F0;}
.comments .cv-list > .cv-item:first-child{border-top:0;}
.comments .cv-day{padding:14px 0 0;border-top:1px solid #E2E8F0;font-size:14px;line-height:20px;color:#6B7280;}
.comments .cv-day a{display:inline-flex;align-items:center;gap:4px;color:#6B7280;text-decoration:none;}
.comments .cv-day svg{width:14px;height:14px;}
.comments .cv-list > .cv-day:first-child{border-top:0;}
.comments .cv-day + .cv-item{border-top:0;padding-top:10px;}
.comments .cv-head{display:flex;align-items:center;gap:7px;min-height:32px;}
.comments .cv-head .cm-avatar{flex:none;}
.comments .cv-head .cm-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
/* P614 숫자 = Inter: 토론 칸 · 화면 전체 창 글꼴 = 테마 --report-font('AS Num' 맨 앞) · 숫자만 있는 자리 = --num */
.comments,.cv-full,.cv-page{font-family:var(--report-font);}
/* P615 날짜 = 가장 작은 글씨 13/19 */
.comments .cm-date,.cv-pmeta,.cv-rtime{font-family:var(--num);font-size:13px;line-height:19px;font-variant-numeric:tabular-nums;}
.comments .cv-react span,.comments .cv-reply span,.cm-count,.cv-lab small,.cv-frow{font-family:var(--num);}
.cv-mine small{font-size:13px;line-height:19px;}
.comments .cv-head .cm-date{margin-left:auto;}
.comments .cv-menu{flex:none;display:flex;align-items:center;justify-content:center;width:32px;height:32px;margin:0 -8px 0 0;padding:0;background:none;border:0;color:#6B7280;cursor:pointer;-webkit-tap-highlight-color:transparent;}
.comments .cv-main{display:block;margin:2px 0 0 31px;color:inherit;text-decoration:none;}
.comments .cv-title{font-size:16px;line-height:24px;font-weight:700;color:#111;word-break:keep-all;overflow-wrap:anywhere;}
/* 목록 한 칸 = 네이버 토론 목록 느낌: 어디 글인지 꼬리표 → 이름 줄 → 큰 제목 → 내용 3줄 → 좋아요 · 싫어요 · 답글 */
.comments .cv-tag{display:inline-block;margin:0 0 10px;padding:4px 10px;border-radius:6px;background:#F1F5F9;font-size:14px;line-height:20px;font-weight:700;color:#333;}
.comments .cv-list .cv-main .cv-title{margin:4px 0 0;font-size:16px;line-height:24px;}   /* 종목 카드 이름과 같은 16/24 굵게 */
.comments .cv-list .cv-main .cv-text{margin:6px 0 0;color:#6B7280;}
.comments .cv-foot{gap:16px;}
.comments .cv-react{display:inline-flex;align-items:center;gap:6px;margin:0;padding:4px 0;background:none;border:0;font:inherit;font-size:14px;line-height:20px;color:#333;font-variant-numeric:tabular-nums;cursor:pointer;-webkit-tap-highlight-color:transparent;}
.comments .cv-react svg{width:20px;height:20px;}
.comments .cv-react.is-on{color:#111;font-weight:700;}
.comments .cv-react.is-on svg{fill:#111;stroke:#111;}
.comments .cv-react.is-on svg path:last-child{stroke:#fff;}
/* 글 화면 = 새 페이지 */
.cv-tbar{justify-content:space-between;}
.cv-tbar-t{flex:1;min-width:0;display:flex;align-items:center;justify-content:center;gap:2px;font-size:16px;line-height:24px;font-weight:700;color:#111;text-decoration:none;}
.cv-tbar-t svg{width:16px;height:16px;}
.cv-page .comments{margin:0;padding:0;border:0;}
.cv-page .cv-head .cm-date:empty{flex:1;}
.cv-ptitle{margin:14px 0 0;font-size:22px;line-height:32px;font-weight:700;color:#111;word-break:keep-all;overflow-wrap:anywhere;}
.cv-pmeta{margin:4px 0 0;color:#7A7A7A;}
.cv-ptext{margin:18px 0 0;font-size:16px;line-height:26px;color:#333;white-space:pre-wrap;word-break:keep-all;overflow-wrap:anywhere;}
.cv-big-react{display:flex;gap:12px;margin:16px 0 0;padding:0 0 16px;border-bottom:1px solid #E2E8F0;}   /* P617 목록과 같은 아이콘 꼴 */
.cv-me{display:flex;align-items:center;gap:7px;margin:0 0 10px;}
.cv-myprof{margin-left:auto;padding:5px 11px;border-radius:8px;background:#fff;border:1px solid #111;color:#111;font-size:13px;line-height:19px;font-weight:700;text-decoration:none;}
.cv-page .comments .cv-rlist .cv-text{margin:6px 0 0;}
.cv-page .comments .cv-rlist .cv-stk,.cv-page .comments .cv-rlist .cv-stock,.cv-page .comments .cv-pop,.cv-page .comments .cv-hidden{margin-left:0;}
.cv-rtime{margin:6px 0 0;color:#7A7A7A;}
.cv-page .comments .cv-rlist .cv-foot{margin:4px 0 0;}
.cv-page .cv-post-menu{margin-left:0;}
.cv-page .cm-submit{background:#fff;border:1px solid #111;color:#111;}   /* 검은 바탕 버튼 금지(목록 버튼만) */
/* 하루 상한 안내 — 화면 아래 잠깐 뜨는 검은 띠 */
.cv-toast{position:fixed;left:16px;right:16px;bottom:24px;z-index:1100;max-width:400px;margin:0 auto;padding:12px 16px;border-radius:8px;background:#111;color:#fff;font-size:14px;line-height:20px;text-align:center;}
.cv-toast[hidden]{display:none;}
.comments .cv-text{margin:4px 0 0;font-size:16px;line-height:26px;color:#333;white-space:pre-wrap;word-break:keep-all;overflow-wrap:anywhere;}
.comments .cv-main .cv-text{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}
.comments .cv-hidden{margin:0;font-size:14px;line-height:20px;color:#94A3B8;}   /* P620 아바타 원 옆 한 줄 */
.comments .cm-avatar.is-hidden{background:#CBD5E1;color:#fff;}
.comments .cm-avatar.is-hidden svg{width:14px;height:14px;display:block;}
.comments .cv-foot{display:flex;align-items:center;margin:8px 0 0 31px;}
.comments .cv-reply{display:inline-flex;align-items:center;gap:6px;padding:4px 8px 4px 0;color:#333;text-decoration:none;font-size:14px;line-height:20px;font-weight:700;font-variant-numeric:tabular-nums;-webkit-tap-highlight-color:transparent;}
.comments .cv-reply.has{color:#333;}
.comments .cv-reply svg{width:20px;height:20px;}
.comments .cv-reply span,.comments .cv-react span{font-weight:400;}
.comments .cv-pop{margin:6px 0 0 31px;padding:12px;border:1px solid #E2E8F0;border-radius:8px;background:#fff;}
.comments .cv-pop[hidden]{display:none;}
.comments .cv-pop-h{font-size:14px;line-height:20px;font-weight:700;color:#111;}
.comments .cv-chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 12px;}
.comments .cv-chip{padding:5px 12px;border:1px solid #E2E8F0;border-radius:16px;background:#fff;font:inherit;font-size:14px;line-height:22px;color:#6B7280;cursor:pointer;-webkit-tap-highlight-color:transparent;}
.comments .cv-chip.is-on{border-color:#111;color:#111;font-weight:700;}
.comments .cv-done{margin:0;font-size:14px;line-height:20px;color:#6B7280;}
/* 안내 상자 — 주의 색(노랑 안내 상자 dk.notice 와 같은 바탕 · 테두리), 느낌표 아이콘 + 14/20 */
.comments .cv-guard{display:flex;align-items:flex-start;gap:6px;margin:14px 0 4px;padding:9px 11px;background:#FFF8E1;border:1px solid #F9E6B5;border-radius:8px;font-size:13px;line-height:19px;color:#333;word-break:keep-all;}   /* P619 = 자료 늦음 상자(dk.report_stamp late)와 같은 꼴 */
.comments .cv-guard svg{flex:none;width:14px;height:14px;margin-top:2px;color:#E8710A;}
/* 이전 댓글 더 보기 · 로그인 버튼 = 페이지 이동 버튼(R.out_btn)의 글자 14/20 굵게 · 안쪽 8 12 · 높이 38. 아이콘 없음 */
.comments .cm-more,.comments .cm-login{padding:8px 12px;font-size:14px;line-height:20px;}
/* 글 화면 */
.comments .cv-back{display:inline-flex;align-items:center;gap:6px;margin:14px 0 6px;padding:6px 0;color:#111;text-decoration:none;font-size:14px;line-height:20px;font-weight:700;}
.comments .cv-back svg{width:16px;height:16px;}
.comments .cv-post{padding:8px 0 18px;border-bottom:1px solid #E2E8F0;}
.comments .cv-post .cv-title{margin:8px 0 0;font-size:19px;line-height:28px;}
.comments .cv-post .cv-text{margin:14px 0 0;}
.comments .cv-post .cv-pop{margin-left:0;}
.comments .cv-count{margin:18px 0 10px;font-size:16px;line-height:24px;font-weight:700;color:#111;}
.comments .cv-fake{display:block;width:100%;box-sizing:border-box;margin:0;padding:11px 12px;background:#fff;border:1px solid #CBD5E1;border-radius:8px;font:inherit;font-size:16px;line-height:26px;color:#94A3B8;text-align:left;cursor:pointer;-webkit-tap-highlight-color:transparent;}
.comments .cv-rlist .cv-item{padding:14px 0;}
.comments .cv-rlist .cv-text{margin:4px 0 0 31px;}
.comments [data-rform][hidden]{display:none;}
.comments .cm-left{font-size:14px;line-height:20px;color:#7A7A7A;}
.comments .cm-count-row{display:flex;align-items:center;gap:10px;}
/* 쓰기 동그란 버튼 — 화면 오른쪽 아래 고정. 기본 버튼 꼴 */
.cv-fab{position:fixed;right:16px;bottom:84px;z-index:900;display:flex;align-items:center;justify-content:center;width:56px;height:56px;padding:0;border:1px solid #111;border-radius:50%;background:#fff;color:#111;box-shadow:0 2px 10px rgba(0,0,0,.16);cursor:pointer;-webkit-tap-highlight-color:transparent;}
.cv-fab[hidden]{display:none;}
.cv-fab svg{width:24px;height:24px;}
/* 창 — 테마 팝업(.rt-pop*) 틀 그대로, 짧은 창 폭 400 */
.cv-win .rt-pop-box{max-width:400px;}
.cv-win::before{content:"";position:fixed;left:0;right:0;top:-100px;bottom:-100px;background:rgba(15,23,42,.45);}
.cv-win .rt-pop-head{border-bottom:1px solid #E2E8F0;}
.cv-win .cv-win-body{padding:26px 20px 20px;font-size:19px;line-height:28px;color:#333;word-break:keep-all;overflow-y:auto;}
.cv-btns{display:flex;gap:8px;margin:24px 0 0;}
.cv-btns button{flex:1;margin:0;padding:11px 12px;border-radius:8px;font:inherit;font-size:16px;line-height:24px;font-weight:700;cursor:pointer;-webkit-tap-highlight-color:transparent;}
.cv-no{background:#fff;border:1px solid #B5BAC0;color:#111;}
.cv-yes{background:#fff;border:1px solid #111;color:#111;}
.cv-write input,.cv-write textarea{display:block;width:100%;box-sizing:border-box;margin:0;padding:11px 12px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;font:inherit;font-size:16px;line-height:26px;color:#333;}
.cv-write input{margin:0 0 8px;font-weight:700;color:#111;}
.cv-write textarea{min-height:128px;resize:none;}
.cv-write input:focus,.cv-write textarea:focus{outline:none;border-color:#111;}
.cv-write ::placeholder{color:#94A3B8;font-weight:400;}
.cv-write .cv-row{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:8px 0 0;font-size:14px;line-height:20px;color:#7A7A7A;}
.cv-write .cv-send{margin:0;padding:8px 24px;background:#fff;border:1px solid #111;color:#111;border-radius:8px;font:inherit;font-size:16px;line-height:24px;font-weight:700;cursor:pointer;}
.cv-write .cv-send[disabled]{opacity:.4;cursor:default;}
.cv-err{margin:8px 0 0;font-size:14px;line-height:20px;color:#B91C1C;}
.cv-err[hidden],.cv-nick[hidden],[data-wform][hidden]{display:none;}
.cv-nick-p{margin:0 0 12px;font-size:16px;line-height:26px;color:#333;}
.cv-nick-row{display:flex;gap:6px;}
.cv-write .cv-nick-row input{margin:0;font-weight:400;}
.cv-nick-msg{margin:8px 0 0;font-size:14px;line-height:20px;color:#B91C1C;}
.cv-nick-msg[hidden]{display:none;}
/* 스티커(우리 캐릭터) · 종목 카드 — 글 · 답글 안 */
.comments .cv-stk{display:block;width:96px;height:96px;margin:8px 0 0;object-fit:contain;}
.comments .cv-rlist .cv-stk{margin-left:31px;}
/* 문장 속 스티커 — 글자 줄 안에 그림. 줄 높이는 그림만큼 늘어난다 */
.cv-stk-in{display:inline-block;width:80px;height:80px;margin:2px 2px;vertical-align:bottom;object-fit:contain;}
.cv-stock{display:block;margin:10px 0 0;padding:12px;border:1px solid #E2E8F0;border-radius:10px;background:#fff;color:inherit;text-decoration:none;}
.comments .cv-rlist .cv-stock{margin-left:31px;}
.cv-stock-top{display:flex;align-items:center;gap:0;}
.cv-stock-name{min-width:0;flex:1;}
.cv-stock-name b{display:block;font-size:16px;line-height:24px;font-weight:700;color:#111;}
.cv-stock-name span{display:block;font-size:13px;line-height:19px;color:#6B7280;}
.cv-stock-px{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;}
.cv-stock-px b{display:block;font-size:16px;line-height:24px;font-weight:700;color:#111;}
.cv-stock-px span{display:flex;align-items:center;justify-content:flex-end;gap:2px;font-size:14px;line-height:20px;font-weight:700;}
.cv-stock svg.cv-spark{display:block;width:100%;height:48px;margin:8px 0 0;}
.cv-stock-note{margin:6px 0 0;font-size:13px;line-height:19px;color:#6B7280;}
/* 화면 전체 창 — 글쓰기 · 프로필 설정 · 내 프로필. 위 줄 = 닫기 네모 32 · 제목 · (오른쪽) 끝내기 버튼 */
.cv-full{position:fixed;left:0;right:0;top:0;bottom:0;z-index:1000;display:flex;flex-direction:column;background:#fff;}
.cv-full[hidden]{display:none;}
.cv-bar{flex:none;display:flex;align-items:center;gap:10px;min-height:56px;padding:0 16px;border-bottom:1px solid #E2E8F0;}
.cv-bar-x{flex:none;display:flex;align-items:center;justify-content:center;width:32px;height:32px;padding:0;border:1px solid #E2E8F0;border-radius:8px;background:#fff;color:#111;cursor:pointer;text-decoration:none;}
.cv-bar-x svg{width:14px;height:14px;}
.cv-bar-t{flex:1;min-width:0;font-size:19px;line-height:28px;font-weight:700;color:#111;}
.cv-bar-ok{flex:none;margin:0;padding:6px 14px;background:#fff;border:1px solid #111;color:#111;border-radius:8px;font:inherit;font-size:14px;line-height:20px;font-weight:700;cursor:pointer;}
.cv-bar-ok[disabled]{opacity:.4;cursor:default;}
.cv-full-body{flex:1;overflow-y:auto;padding:16px 16px 40px;max-width:720px;width:100%;margin:0 auto;box-sizing:border-box;}
.cv-where{margin:0 0 12px;font-size:14px;line-height:20px;color:#6B7280;}
.cv-full input.cv-in,.cv-full textarea.cv-in{display:block;width:100%;box-sizing:border-box;margin:0;padding:11px 12px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;font:inherit;font-size:16px;line-height:26px;color:#333;}
.cv-full input.cv-in:focus,.cv-full textarea.cv-in:focus{outline:none;border-color:#111;}
.cv-full ::placeholder{color:#94A3B8;font-weight:400;}
.cv-full input.cv-title-in{font-weight:700;color:#111;}
.cv-full textarea.cv-in{min-height:180px;resize:none;}
.cv-tools{display:flex;gap:6px;margin:8px 0;}
.cv-tool{display:inline-flex;align-items:center;gap:6px;margin:0;padding:6px 12px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;font:inherit;font-size:14px;line-height:20px;font-weight:700;color:#111;cursor:pointer;-webkit-tap-highlight-color:transparent;}
.cv-tool.is-on{border-color:#111;}
.cv-tool svg{width:16px;height:16px;}
.cv-panel{margin:0 0 8px;padding:12px;border:1px solid #E2E8F0;border-radius:10px;background:#F8FAFC;}
.cv-panel[hidden]{display:none;}
/* 스티커 칸 — 흰 바탕 · 줄 없음 · 캐릭터 탭(테마 .tab 과 같은 밑줄 탭). 누르면 글쓴 자리에 바로 들어가고 칸은 열린 채(여러 개 연속) */
.cv-panel.is-stk{padding:0;border:0;border-radius:0;background:#fff;}
.cv-stk-tabs{display:flex;border-bottom:1px solid #E2E8F0;}
.cv-stk-tab{display:flex;flex-direction:column;margin:0;padding:8px 14px 0;background:none;border:0;font:inherit;font-size:16px;line-height:24px;font-weight:400;color:#6B7280;cursor:pointer;-webkit-tap-highlight-color:transparent;}
.cv-stk-tab:first-child{padding-left:0;}
.cv-stk-tab::after{content:"";display:block;height:2px;margin-top:8px;background:transparent;}
.cv-stk-tab[aria-selected="true"]{font-weight:700;color:#111;}
.cv-stk-tab[aria-selected="true"]::after{background:#111;}
.cv-stk-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;max-height:296px;overflow-y:auto;padding:8px 0;}
.cv-stk-grid[hidden]{display:none;}
.cv-stk-pick{display:flex;align-items:center;justify-content:center;height:72px;padding:4px;border:0;border-radius:8px;background:#fff;cursor:pointer;-webkit-tap-highlight-color:transparent;}
.cv-stk-pick:active{background:#F1F5F9;}
.cv-stk-pick img{display:block;width:62px;height:62px;object-fit:contain;}
/* 내용 칸 = 글자와 스티커가 섞이는 칸 */
.cv-full .cv-ed{min-height:180px;padding:11px 12px;border:1px solid #E2E8F0;border-radius:8px;font-size:16px;line-height:26px;color:#333;white-space:pre-wrap;word-break:keep-all;overflow-wrap:break-word;}
.cv-full .cv-ed:focus{outline:none;border-color:#111;}
.cv-full .cv-ed:empty::before{content:attr(data-ph);color:#94A3B8;}
.cv-sym-row{display:flex;align-items:center;width:100%;margin:0;padding:9px 0;background:none;border:0;border-top:1px solid #E2E8F0;font:inherit;font-size:16px;line-height:24px;color:#111;text-align:left;cursor:pointer;}
.cv-sym-row:first-of-type{border-top:0;}
.cv-sym-row small{margin-left:auto;font-size:14px;color:#6B7280;}
.cv-attach{position:relative;margin:0 0 8px;}
.cv-attach[hidden]{display:none;}
.cv-attach .cv-stk{width:96px;height:96px;margin:0;}
.cv-attach .cv-stock{margin:0;}
.cv-attach-x{position:absolute;top:-8px;right:-8px;display:flex;align-items:center;justify-content:center;width:24px;height:24px;padding:0;border:1px solid #E2E8F0;border-radius:50%;background:#fff;color:#111;cursor:pointer;}
.cv-attach-x svg{width:10px;height:10px;}
.cv-frow{display:flex;align-items:center;justify-content:space-between;margin:8px 0 0;font-size:14px;line-height:20px;color:#7A7A7A;}
/* 프로필 */
.cv-lab{display:flex;align-items:center;gap:8px;margin:20px 0 8px;font-size:16px;line-height:24px;font-weight:700;color:#111;}
.cv-lab small{margin-left:auto;font-size:14px;font-weight:400;color:#7A7A7A;font-variant-numeric:tabular-nums;}
.cv-reroll{display:inline-flex;align-items:center;gap:4px;margin:0;padding:3px 10px;background:#fff;border:1px solid #E2E8F0;border-radius:16px;font:inherit;font-size:14px;line-height:20px;font-weight:400;color:#111;cursor:pointer;}
.cv-reroll svg{width:14px;height:14px;}
.cv-hint{margin:6px 0 0;font-size:14px;line-height:20px;color:#6B7280;}
.cv-hint.is-bad{color:#B91C1C;}
.cv-big-av{display:block;width:72px;height:72px;margin:8px auto 0;border-radius:50%;overflow:hidden;}
.cv-big-av img{display:block;width:100%;height:100%;}
/* 프로필 그림 고르기 — 스티커 칸과 같은 밑줄 탭(동물 · 일반) · 4 × 3 · 원 48 · 고른 그림 = 검은 테두리 2 */
.cv-ava-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:12px 0 0;}
.cv-ava-grid[hidden]{display:none;}
.cv-ava-pick{display:flex;align-items:center;justify-content:center;height:56px;margin:0;padding:0;border:0;background:none;cursor:pointer;-webkit-tap-highlight-color:transparent;}
.cv-ava-pick img{display:block;width:48px;height:48px;border-radius:50%;box-sizing:border-box;border:2px solid transparent;}
.cv-ava-pick.is-on img{border-color:#111;}
.cv-prof{display:flex;align-items:center;gap:12px;}
.cv-prof-name{flex:1;min-width:0;font-size:19px;line-height:28px;font-weight:700;color:#111;}
.cv-prof .cv-big-av{flex:none;width:56px;height:56px;margin:0;}
.cv-prof-intro{margin:8px 0 14px;font-size:16px;line-height:26px;color:#333;}
.cv-edit{display:block;width:100%;box-sizing:border-box;margin:0;padding:8px 12px;background:#fff;border:1px solid #B5BAC0;border-radius:8px;font:inherit;font-size:14px;line-height:20px;font-weight:700;color:#111;text-align:center;cursor:pointer;}
.cv-mine-h{margin:28px 0 0;padding:0 0 8px;border-bottom:1px solid #E2E8F0;font-size:16px;line-height:24px;font-weight:700;color:#111;}
.cv-mine{display:block;padding:14px 0;border-bottom:1px solid #E2E8F0;color:inherit;text-decoration:none;}
.cv-mine small{display:block;color:#6B7280;}
.cv-mine b{display:block;margin:2px 0 0;font-size:16px;line-height:24px;font-weight:700;color:#111;}
.cv-mine .cv-reply{padding:6px 0 0;}
.cv-rules{margin:0;padding:0;list-style:none;}
.cv-rules li{display:flex;align-items:flex-start;gap:7px;margin:0 0 11px;padding-left:7px;font-size:19px;line-height:28px;color:#333;}
.cv-rules li::before{content:"";flex:none;width:3px;height:3px;margin-top:12px;border-radius:50%;background:#111;}
.cv-rules-sub{margin:15px 0 0;font-size:13px;line-height:19px;color:#6B7280;}
.cv-rules-sub a{color:#6B7280;text-decoration:underline;text-underline-offset:3px;}
</style>"""

LOGO = ('<svg viewBox="0 0 313 286" width="14" height="13" aria-hidden="true"><path d="M313 134L164.968 286H35L189.03 134H313Z" fill="#DD0000"/>'
        '<path d="M164.519 0H287L128.954 147H0L164.519 0Z" fill="#000000"/></svg>')
_SVG = 'aria-hidden="true" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"'
BUBBLE = (f'<svg viewBox="0 0 22 22" width="22" height="22" {_SVG} stroke-width="1.6">'
          '<path d="M4.5 4.5h13a2 2 0 0 1 2 2v7.5a2 2 0 0 1-2 2H10l-4 3.5v-3.5H4.5a2 2 0 0 1-2-2V6.5a2 2 0 0 1 2-2z"/></svg>')
PENCIL = f'<svg viewBox="0 0 16 16" {_SVG} stroke-width="1.6"><path d="M10.5 2.5l3 3L6 13H3v-3z"/><path d="M9 14h4.5"/></svg>'
DOTS = '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="currentColor"><circle cx="8" cy="3" r="1.3"/><circle cx="8" cy="8" r="1.3"/><circle cx="8" cy="13" r="1.3"/></svg>'
BACK = f'<svg viewBox="0 0 16 16" {_SVG} stroke-width="1.6"><path d="M13 8H3M7 4 3 8l4 4"/></svg>'
THUMB = (f'<svg viewBox="0 0 24 24" width="20" height="20" {_SVG} stroke-width="1.6"{{}}>'
         '<path d="M7 10v11H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1z"/>'
         '<path d="M7 10l4-7.5a2.5 2.5 0 0 1 3 2.9L13.3 9h5.6a2 2 0 0 1 2 2.4l-1.6 8A2 2 0 0 1 17.3 21H7"/></svg>')
UP_ICON, DOWN_ICON = THUMB.format(""), THUMB.format(' style="transform:rotate(180deg)"')
SHARE = f'<svg viewBox="0 0 16 16" {_SVG} stroke-width="1.6"><path d="M9.5 2.5H13.5V6.5M13.5 2.5 8 8M11.5 9.5v3a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3"/></svg>'
GO = f'<svg viewBox="0 0 16 16" {_SVG} stroke-width="1.6"><path d="M6 3.5 10.5 8 6 12.5"/></svg>'
SIREN = f'<svg viewBox="0 0 16 16" {_SVG} stroke-width="1.6"><path d="M4.5 12.5V9a3.5 3.5 0 0 1 7 0v3.5M3 12.5h10M8 2v1.3M2.8 4.2l.9.9M13.2 4.2l-.9.9"/></svg>'   # 신고 = 경광등(가려진 글 원 안, P620)
WARN = f'<svg viewBox="0 0 16 16" {_SVG} stroke-width="1.6"><path d="M8 2 14.5 13.5h-13z"/><path d="M8 6.5v3.2M8 11.6v.1"/></svg>'
REASONS = ("리딩방 · 광고", "욕설 · 비방", "개인정보", "거짓 정보 · 시세 조종 의심", "기타")
ME = "주린이탈출"
# 프로필 그림 24종 — cut_avatars.py 가 output/avatars/ 에 자른다.
# 처음엔 회원마다 자동 배정(목록이 한 그림으로 도배되지 않게) · 내 프로필에서 바꾼다. 서버엔 번호만(a01 · p07).
AVA_TABS = [("동물", "a"), ("일반", "p")]
ME_AVA = "a06"   # 목업: 나 = 곰


def ava_of(name):
    """회원 → 그림 번호. 목업은 별명 글자 합으로 고정 배정(실서비스 = 가입 때 회원 번호로 배정 · 바꾸면 고른 값)."""
    if name == ME:
        return ME_AVA
    n = int(hashlib.md5(name.encode()).hexdigest(), 16) % 24
    return f'{"ap"[n // 12]}{n % 12 + 1:02d}'


def ava_src(k):
    return f"avatars/{k}.webp"


def ava_picker(on):
    tabs = "".join(f'<button class="cv-stk-tab" type="button" role="tab" data-atab="{p}" aria-selected="{str(p == on[0]).lower()}">{n}</button>' for n, p in AVA_TABS)
    grids = "".join(f'<div class="cv-ava-grid" data-agrid="{p}"{"" if p == on[0] else " hidden"}>'
                    + "".join(f'<button class="cv-ava-pick{" is-on" if f"{p}{i:02d}" == on else ""}" type="button" data-ava="{p}{i:02d}" aria-label="{n} 그림 {i}">'
                              f'<img src="{ava_src(f"{p}{i:02d}")}" alt="" width="48" height="48"></button>' for i in range(1, 13))
                    + '</div>' for n, p in AVA_TABS)
    return f'<div class="cv-lab">프로필 그림</div><div class="cv-stk-tabs" role="tablist">{tabs}</div>{grids}'
GUARD = "신고가 3번 쌓인 댓글은 자동으로 가려집니다. 오픈채팅 · 텔레그램 주소와 연락처는 등록되지 않습니다."

# 글 = (별명, 날짜, 제목, 글, 상태, [답글 (별명, 날짜, 글)…]) · 상태: "" · "hidden" 가려짐 · "me" 내 글. 답글 별명이 "" 이면 가려진 답글
THREAD = ("반도체곰", "11.18 16:10", "오늘은 반도체 두 종목만 오른 날",
          "오늘 오른 건 반도체 두 종목 덕이고 나머지는 조용했던 것 같습니다. 오른 종목 수도 같이 보여 주시면 좋겠어요.", "", [
              ("데이터센터", "11.18 16:31", "저도 그게 궁금했습니다. 지수만 보면 다 오른 줄 알겠더라고요."),
              ("새내기", "11.18 16:40", "오른 종목 수는 어디서 볼 수 있나요?"),
              ("owner", "11.18 16:58", "코스피 리포트의 `오른 종목이 많았나?` 칸에 오른 종목 수와 내린 종목 수가 있습니다."),
              ("반도체곰", "11.18 17:03", "찾았습니다[:mid_proof:] 오른 종목이 절반이 안 됐네요[:down_calm:]"),
              ("", "11.18 17:15", ""),
              ("장기보유", "11.18 17:30", "지수는 올랐는데 제 계좌는 그대로였던 이유가 있었네요."),
              (ME, "11.18 17:44", "저도 리포트에서 같이 보고 왔습니다. 감사합니다[:mid_thanks:]"),
          ])
# 날짜 묶음(최신 날이 위)
DAYS = [
    ("11.18 증시 시황에 달린 댓글", [
        (ME, "11.18 17:40", "미국 물가 발표는 언제 반영되나요?", "내일 미국 물가 발표가 있던데 한국 장에는 모레 반영되는 건가요?", "me", [
            ("owner", "11.18 17:55", "미국 발표는 한국 시간으로 밤 10시 30분이라 다음 날 아침 한국 장에 반영됩니다."),
            ("조심조심", "11.18 18:10", "발표 날 밤에는 야간 선물도 같이 움직입니다."),
        ]),
        ("새내기", "11.18 17:02", "환율 설명이 쉬웠습니다", "환율이 내리면 왜 외국인이 사는지 본문 설명이 이해가 잘 됐습니다. 감사합니다.", "", [
            ("장기보유", "11.18 17:20", "저도 그 부분이 좋았습니다."),
        ]),
        THREAD,
    ]),
    ("11.17 증시 시황에 달린 댓글", [
        ("", "11.17 19:20", "", "", "hidden", []),
        ("조심조심", "11.17 18:05", "내일 옵션 만기일입니다", "만기일에는 장 끝에 지수가 흔들릴 때가 있어서 저는 종가 주문을 안 넣습니다.", "", []),
        ("장기보유", "11.17 16:42", "외국인은 파는데 지수는 버팁니다", "외국인이 사흘째 파는데 지수는 버티네요. 개인이 받아 주는 건가요?", "", [
            ("owner", "11.17 17:05", "네, 11.17에는 개인이 순매수였습니다. 수급 표는 코스피 리포트 `누가 샀나?` 칸에 있습니다."),
            ("장기보유", "11.17 17:12", "감사합니다[:mid_thanks:] 리포트에서 확인했습니다."),
            ("조심조심", "11.17 18:30", "개인이 받는 장은 오래 못 간다는 말도 있던데, 지난 기록은 어땠는지 궁금하네요."),
            ("데이터센터", "11.17 19:02", "저는 외국인 선물 쪽도 같이 봅니다. 현물만 보면 헷갈릴 때가 있어서요."),
        ]),
    ]),
]
# 글에 붙은 스티커 · 종목 (제목 또는 답글 글로 찾는다) — 스티커 = 우리 캐릭터 컷, 종목 = 코드만 저장하고 카드는 우리 종가 파일로 그린다
EXTRA = {
    "미국 물가 발표는 언제 반영되나요?": {"stk": "up_wonder"},
    "오늘은 반도체 두 종목만 오른 날": {"sym": "000660"},
    "외국인은 파는데 지수는 버팁니다": {"stk": "up_wait"},
        "지수는 올랐는데 제 계좌는 그대로였던 이유가 있었네요.": {"stk": "up_cry"},
}
# 종목 카드 예시 값 — (이름, 아래 줄, 값, 등락, 오름?, 선 그래프 점)
STOCKS = {
    "000660": ("SK하이닉스", "000660 · 코스피", "612,000원", "+4.26%", True, [30, 28, 31, 27, 25, 26, 22, 20, 21, 17, 15, 16, 12, 10]),
    "005930": ("삼성전자", "005930 · 코스피", "98,700원", "+2.81%", True, [28, 29, 26, 27, 24, 22, 23, 20, 21, 18, 17, 15, 14, 12]),
    "NVDA": ("엔비디아", "NVDA · 나스닥", "$125.53", "-14.01%", False, [10, 12, 11, 14, 15, 14, 16, 15, 17, 16, 22, 26, 29, 31]),
}
STICKERS = [   # (탭 이름, [컷 …]) 그림 여섯 장(course/sheet_to_webp.py 로 자름) 먼저, 그 뒤 옛 주식 공부 컷
    ("상승이", ["up_flip", "up_panic", "up_throw", "up_box", "up_flat", "up_cheer", "up_chicken", "up_night",
                "up_pray", "up_treadmill", "up_recheck", "up_flowers",
                "up_laptop", "up_search", "up_book", "up_coffee", "up_walk", "up_news", "up_tablet", "up_ponder",
                "up_surprised", "up_cry", "up_sweat", "up_regret", "up_relief", "up_wait", "up_wonder", "up_buy"]),
    ("하락이", ["down_hammock", "down_nap", "down_extinguish", "down_airport", "down_piggy", "down_noear", "down_shrug", "down_spa",
                "down_thumb", "down_frown", "down_float", "down_bye",
                "down_happy", "down_calm", "down_grumpy", "down_sulky"]),
    ("분석이", ["mid_whistle", "mid_balance", "mid_chalk", "mid_egg", "mid_measure", "mid_gavel",
                "mid_question", "mid_clap", "mid_proof", "mid_peace", "mid_hourglass", "mid_thanks",
                "mid_travel", "mid_workout", "mid_sleep", "mid_music", "mid_eat", "mid_photo", "mid_map", "mid_stretch",
                "mid_think", "mid_caution", "mid_explain"]),
    ("같이", ["pair_gym", "pair_game", "pair_trip", "pair_race", "pair_study", "pair_wonder", "pair_play", "pair_cheer"]),
]
TITLES = {   # 목업 목록에 보이는 이름
    "mock_comments_member.html": "댓글 목록 (로그인 뒤)",
    "mock_comments_guest.html": "댓글 목록 (로그인 전)",
    "mock_comments_thread.html": "댓글 글 화면 · 답글 · 스티커 붙은 모습 (로그인 뒤)",
    "mock_comments_thread-guest.html": "댓글 글 화면 (로그인 전)",
    "mock_comments_first.html": "댓글 처음 쓸 때 · 프로필 만들기 · 운영 원칙",
    "mock_comments_write.html": "댓글 글쓰기 · 스티커 고르기 · 종목 붙이기",
    "mock_comments_profile.html": "댓글 내 프로필",
}
REACT_LIMIT = 30   # 좋아요 · 싫어요 하루 상한. 누른 걸 취소해도 돌려주지 않는다(쓰기 횟수는 이미 쓰였으므로)
REACT_LEFT = 2     # 목업: 오늘 28번 누른 상태로 시작 — 세 번째 누르면 상한 안내가 뜬다
NICK_A = ["느긋한", "꾸준한", "침착한", "용감한", "성실한", "든든한", "신중한", "씩씩한"]
NICK_B = ["개미", "장기투자자", "배당수집가", "분할매수러", "차트탐험가", "적립왕", "가계부장", "공부벌레"]
X_ICON = f'<svg viewBox="0 0 16 16" {_SVG} stroke-width="2"><path d="M3 3l10 10M13 3 3 13"/></svg>'
SMILE = f'<svg viewBox="0 0 16 16" {_SVG} stroke-width="1.6"><circle cx="8" cy="8" r="6"/><path d="M5.5 9.5c.6 1 1.5 1.5 2.5 1.5s1.9-.5 2.5-1.5M6 6.3v.2M10 6.3v.2"/></svg>'
CHART = f'<svg viewBox="0 0 16 16" {_SVG} stroke-width="1.6"><path d="M2 11.5l4-4 3 3 5-6"/><path d="M10.5 4.5H14v3.5"/></svg>'
ROLL = f'<svg viewBox="0 0 16 16" {_SVG} stroke-width="1.6"><path d="M13 8a5 5 0 1 1-1.5-3.6M13 2.5v3h-3"/></svg>'
TOTAL = 27   # 예시: 자리 전체 글 수(아래로 더 있음)


def avatar(name, kind=""):
    if name == "owner":
        return f'<span class="cm-avatar is-owner">{LOGO}</span>'
    if kind == "hidden":
        return f'<span class="cm-avatar is-hidden">{SIREN}</span>'
    return f'<span class="cm-avatar" style="background:none;"><img src="{ava_src(ava_of(name))}" alt="" width="24" height="24"></span>'


def head(name, when, key, member, date=True):
    """이름 줄 — 사진 · 이름 · (오른쪽) 날짜 · 점 세 개(신고, 내 글은 삭제). 로그인 전에는 점 세 개가 로그인 창을 연다."""
    owner = name == "owner"
    menu = "" if owner else (f'<button class="cv-menu" type="button" aria-label="더 보기" data-menu="{key}"'
                             f'{"" if member else " data-need-login"}>{DOTS}</button>')
    return (f'<div class="cv-head">{avatar(name)}<span class="cm-name">{"Newfact" if owner else esc(name)}</span>'
            + (f'<span class="cm-date">{when}</span>' if date else '<span class="cm-date"></span>') + f'{menu}</div>')


def menu_box(key, mine):
    if mine:
        return f'<div class="cv-pop" data-menu-box="{key}" hidden><button class="cm-btn" type="button">삭제</button></div>'
    chips = "".join(f'<button class="cv-chip" type="button" data-pick>{esc(t)}</button>' for t in REASONS)
    return (f'<div class="cv-pop" data-menu-box="{key}" hidden><div class="cv-pop-h">신고하는 이유</div>'
            f'<div class="cv-chips">{chips}</div><button class="cm-btn" type="button" data-report-send disabled>신고하기</button></div>')


STK_TOKEN = re.compile(r"\[:([a-z]+_[a-z]+):\]")


def rich(text):
    """글 → HTML. 문장 속 스티커 [:up_cry:] = 글자 사이 그림(저장은 짧은 표시만, 그림은 우리 파일)."""
    return STK_TOKEN.sub(lambda m: f'<img class="cv-stk-in" src="stickers/c_{m.group(1)}.webp" alt="" width="80" height="80">', esc(text))


def sticker(key):
    return f'<img class="cv-stk" src="stickers/c_{key}.webp" alt="" width="96" height="96">'


def stock_card(sym, tag="a"):
    """종목 카드 — 로고 · 이름 · 값 · 등락 · 작은 선 그래프. 누르면 그 종목 페이지로. 값은 가장 최근 종가(우리가 이미 올리는 파일)."""
    name, sub, px, chg, up, pts = STOCKS[sym]
    ink, line = ("#B91C1C", "#ED8E87") if up else ("#1D4ED8", "#82B1F0")
    step = 300 / (len(pts) - 1)
    path = " ".join(f"{round(i * step)},{y + 4}" for i, y in enumerate(pts))
    return (f'<{tag} class="cv-stock"{" href=" + chr(34) + "#" + chr(34) if tag == "a" else ""}><span class="cv-stock-top">{dk.name_logo(sym + ".KS" if sym.isdigit() else sym, name, 32)}'
            f'<span class="cv-stock-name"><b>{esc(name)}</b><span>{esc(sub)}</span></span>'
            f'<span class="cv-stock-px"><b>{px}</b><span style="color:{ink};">{dk.tri_span(up, 14)}{chg.lstrip("+-")}</span></span></span>'
            f'<svg class="cv-spark" viewBox="0 0 300 40" preserveAspectRatio="none" aria-hidden="true"><polyline points="{path}" fill="none" stroke="{line}" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>'
            f'<span class="cv-stock-note" style="display:block;">11.18 종가 기준</span></{tag}>')


def extras(key):
    e = EXTRA.get(key, {})
    return (stock_card(e["sym"]) if "sym" in e else "") + (sticker(e["stk"]) if "stk" in e else "")


def hidden_row():   # 신고 3번 = 자동으로 가린다 — 운영자가 보고 되살리거나 지운다
    return (f'<li class="cv-item"><div class="cv-head">{avatar("", "hidden")}'
            '<span class="cv-hidden">신고가 쌓여 가려진 댓글입니다.</span></div></li>')


def reacts(seed, member):
    h = sum(ord(ch) * (i + 1) for i, ch in enumerate(seed))
    up, down = h % 13, (h // 7) % 4
    need = "" if member else " data-need-login"
    return (f'<button class="cv-react" type="button" data-react="up"{need} aria-label="좋아요 {up}">{UP_ICON}<span>{up}</span></button>'
            f'<button class="cv-react" type="button" data-react="down"{need} aria-label="싫어요 {down}">{DOWN_ICON}<span>{down}</span></button>')


def item(c, member, key, link, tag=""):
    name, when, title, text, state, replies = c
    if state == "hidden":
        return hidden_row()
    n = len(replies)
    return (f'<li class="cv-item">{f"<span class=cv-tag>{esc(tag)}</span>" if tag else ""}{head(name, when, key, member)}'
            f'<a class="cv-main" href="{link}"><div class="cv-title">{esc(title)}</div><p class="cv-text">{rich(text)}</p>{extras(title).replace("<a ", "<span ").replace("</a>", "</span>")}</a>'
            f'<div class="cv-foot">{reacts(name + title, member)}<a class="cv-reply{" has" if n else ""}" href="{link}" aria-label="답글 {n}개 · 답글 쓰기">{BUBBLE}<span>{n}</span></a></div>'
            f'{menu_box(key, state == "me") if member else ""}</li>')


def guard():
    return f'<div class="cv-guard">{WARN}<span>{esc(GUARD)}</span></div>'


def note():
    return dk.excl_note("회원이 쓴 의견이며 Newfact의 의견이 아닙니다. 투자 권유가 아니고, 판단과 책임은 읽는 분에게 있습니다.", margin="14px 0 0")


def list_view(member, first):
    link = "mock_comments_thread.html" if member else "mock_comments_thread-guest.html"
    if first:
        return 0, guard() + '<div class="cm-status">첫 댓글을 남겨 주세요.</div>' + note()
    rows, k = "", 0
    for day, cs in DAYS:
        tag = day.replace("에 달린 댓글", "")   # 날짜 줄 대신 글마다 꼬리표(어느 날 어느 글에 쓴 댓글인지)
        for c in cs:
            rows += item(c, member, f"t{k}", link, tag)
            k += 1
    return TOTAL, (guard() + f'<ol class="cv-list">{rows}</ol>'
                   f'<button class="cm-more" type="button">댓글 {TOTAL - k}개 더 보기</button>' + note())


def thread_page(member):
    """글 화면 = 새 페이지. 목록 칸을 누르면 열린다.
    실제는 Blogger 페이지 하나(/p/comment.html?post=…&c=…)가 주소의 번호로 글을 읽어 그린다 — 댓글마다 주소가 생겨 공유도 된다.
    위 줄(뒤로 · 어느 글 › · 공유) → 글쓴이 → 제목 → 날짜 → 본문 → 좋아요 · 싫어요 상자 → 답글 n → 내 이름 · 내 프로필 → 쓰는 칸 → 안내 → 답글들."""
    name, when, title, text, _, replies = THREAD
    back = "mock_comments_member.html" if member else "mock_comments_guest.html"
    top = (f'<div class="cv-bar cv-tbar"><a class="cv-bar-x" href="{back}" aria-label="댓글 목록으로">{BACK}</a>'
           f'<a class="cv-tbar-t" href="#" aria-label="11.18 증시 시황 글로 가기">11.18 증시 시황{GO}</a>'
           f'<button class="cv-bar-x" type="button" aria-label="공유" data-share>{SHARE}</button></div>')
    post = (f'{head(name, when, "p", member, date=False)}{menu_box("p", False) if member else ""}'
            f'<h1 class="cv-ptitle">{esc(title)}</h1><div class="cv-pmeta">{when}</div>'
            f'<p class="cv-ptext">{rich(text)}</p>{extras(title)}'
            f'<div class="cv-big-react">{reacts(name + title, member)}</div>')
    if member:
        me = f'<div class="cv-me">{avatar(ME)}<span class="cm-name">{ME}</span><a class="cv-myprof" href="mock_comments_profile.html">내 프로필</a></div>'
        box = (me + '<button class="cv-fake" type="button" data-open-rform>의견을 남겨 보세요</button>'
               '<div data-rform hidden><form class="cm-form" onsubmit="return false"><textarea class="cm-input" data-ta maxlength="2000" rows="4" placeholder="의견을 남겨 보세요" aria-label="답글 쓰기"></textarea>'
               '<div class="cm-foot"><div class="cm-count-row"><span class="cm-count" data-count>0 / 2000</span><span class="cm-left">오늘 남은 댓글 28개</span></div>'
               '<div class="cm-foot-btns"><button class="cm-submit" type="submit" data-send disabled>등록</button></div></div>'
               '<div class="cv-err" data-err hidden>오픈채팅 · 텔레그램 주소와 연락처는 올릴 수 없습니다. 지우고 다시 등록해 주세요.</div></form></div>')
    else:
        box = '<button class="cv-fake" type="button" data-need-login>답글을 쓰려면 로그인해 주세요</button>'
    rows = ""
    for k, r in enumerate(replies):
        who, rwhen, rtext = r
        if not who:
            rows += hidden_row()
            continue
        rows += (f'<li class="cv-item">{head(who, rwhen, f"r{k}", member, date=False)}<p class="cv-text">{rich(rtext)}</p>{extras(rtext)}'
                 f'<div class="cv-rtime">{rwhen}</div><div class="cv-foot">{reacts(who + rtext, member)}</div>'
                 f'{menu_box(f"r{k}", who == ME) if member and who != "owner" else ""}</li>')
    return (f'<div class="cv-full cv-page" data-win="thread">{top}<div class="cv-full-body"><div class="comments is-open">{post}'
            f'<div class="cv-count">답글 {len(replies)}</div>{box}{guard()}<ol class="cv-list cv-rlist">{rows}</ol>{note()}</div></div></div>')


def win(wid, title, body, cls=""):
    """창 — 테마 팝업 틀(.rt-pop*): 흰 상자 · 모서리 12 · 제목 19 굵게 · 닫기 네모 32 · 제목 아래 선."""
    return (f'<div class="rt-pop cv-win {cls}" data-win="{wid}" hidden><div class="rt-pop-box" role="dialog" aria-modal="true" aria-label="{esc(title)}">'
            f'<div class="rt-pop-head"><div class="rt-pop-title">{esc(title)}</div><button type="button" class="rt-pop-close" aria-label="닫기" data-win-close>×</button></div>'
            f'<div class="cv-win-body">{body}</div></div></div>')


def bar(title, ok="", ok_attr="", close_href=""):
    """화면 전체 창 위 줄 — 닫기 네모 · 제목 · 끝내기 버튼."""
    x = (f'<a class="cv-bar-x" href="{close_href}" aria-label="닫기">{X_ICON}</a>' if close_href
         else f'<button class="cv-bar-x" type="button" aria-label="닫기" data-win-close>{X_ICON}</button>')
    return (f'<div class="cv-bar">{x}<div class="cv-bar-t">{esc(title)}</div>'
            + (f'<button class="cv-bar-ok" type="button" {ok_attr} disabled>{ok}</button>' if ok else "") + "</div>")


def write_full(left):
    """글쓰기 — 화면 전체. 제목 · 스티커 · 종목 붙이기 · 내용."""
    tabs = "".join(f'<button class="cv-stk-tab" type="button" role="tab" data-stab="{i}" aria-selected="{str(i == 0).lower()}">{n}</button>' for i, (n, _) in enumerate(STICKERS))
    grids = "".join(f'<div class="cv-stk-grid" data-sgrid="{i}"{"" if i == 0 else " hidden"}>'
                    + "".join(f'<button class="cv-stk-pick" type="button" data-stk="{k}" aria-label="{n} 스티커 넣기"><img src="stickers/c_{k}.webp" alt="" width="62" height="62"></button>' for k in ks)
                    + "</div>" for i, (n, ks) in enumerate(STICKERS))
    rows = f'<div class="cv-stk-tabs" role="tablist">{tabs}</div>{grids}'
    syms = "".join(f'<button class="cv-sym-row" type="button" data-sym="{k}">{dk.name_logo(k + ".KS" if k.isdigit() else k, v[0], 24)}{esc(v[0])}<small>{esc(v[1])}</small></button>' for k, v in STOCKS.items())
    cards = "".join(f'<template data-card="{k}">{stock_card(k, "div")}</template>' for k in STOCKS)
    return (f'<div class="cv-full" data-win="write" hidden>{bar("글쓰기", "등록하기", "data-wsend")}<div class="cv-full-body">'
            '<p class="cv-where">한국 증시 시황에 쓰는 글</p>'
            '<input class="cv-in cv-title-in" data-wtitle maxlength="40" placeholder="제목" aria-label="제목">'
            f'<div class="cv-tools"><button class="cv-tool" type="button" data-tool="stk">{SMILE}스티커</button>'
            f'<button class="cv-tool" type="button" data-tool="sym">{CHART}종목 붙이기</button></div>'
            f'<div class="cv-panel is-stk" data-panel="stk" hidden>{rows}</div>'
            f'<div class="cv-panel" data-panel="sym" hidden><input class="cv-in" placeholder="종목 이름 · 코드" aria-label="종목 찾기" style="margin:0 0 4px;">{syms}</div>'
            f'<div class="cv-attach" data-att="sym" hidden><div data-att-body></div><button class="cv-attach-x" type="button" aria-label="종목 빼기" data-att-x>{X_ICON}</button></div>'
            '<div class="cv-ed" data-wta contenteditable="true" role="textbox" aria-multiline="true" aria-label="내용" data-ph="내용을 입력하세요. 쓰다가 스티커를 누르면 그 자리에 들어갑니다."></div>'
            f'<div class="cv-frow"><span data-wcount>0 / 2000</span><span>오늘 남은 댓글 {left}개</span></div>'
            '<p class="cv-err" data-werr hidden>오픈채팅 · 텔레그램 주소와 연락처는 올릴 수 없습니다. 지우고 다시 등록해 주세요.</p>'
            f'{cards}</div></div>')


def profile_set():
    """프로필 설정 — 별명(추천 별명 다시 뽑기) · 소개. 사진은 받지 않고 그림 24종(동물 · 일반 탭)에서 고른다."""
    return (f'<div class="cv-full" data-win="pset" hidden>{bar("프로필 설정", "완료", "data-pdone")}<div class="cv-full-body">'
            f'<div class="cv-big-av"><img data-pav src="{ava_src("a01")}" alt="" width="72" height="72"></div>'
            f'<div class="cv-lab">별명<button class="cv-reroll" type="button" data-reroll>{ROLL}추천</button><small data-pcount>0 / 12</small></div>'
            '<input class="cv-in" data-pnick maxlength="12" placeholder="별명 2~12자" aria-label="별명">'
            '<p class="cv-hint" data-phint>추천 별명입니다. 바꿔 쓰셔도 됩니다.</p>'
            '<div class="cv-lab">소개<small data-icount>0 / 100</small></div>'
            '<textarea class="cv-in" data-pintro maxlength="100" placeholder="소개를 적어 주세요. 비워 두셔도 됩니다." aria-label="소개" style="min-height:104px;"></textarea>'
            + ava_picker("a01") +
            '<p class="cv-hint">댓글에는 구글 이름과 사진 대신 별명과 고른 그림이 보입니다. 별명은 30일에 한 번 바꿀 수 있습니다.</p>'
            '</div></div>')


def windows(member, first):
    login = win("login", "로그인하시겠습니까?",
                '로그인이 필요한 서비스입니다.<div class="cv-btns"><button class="cv-no" type="button" data-win-close>아니오</button>'
                '<button class="cv-yes" type="button" data-login-go>로그인하기</button></div>')
    if not member:
        return login
    out = login + write_full(30 if first else 28)
    if first:   # 로그인하고 처음 — 프로필 만들기 → 운영 원칙 → 프로필 설정
        ask = win("pask", "프로필을 만들어 주세요",
                  '댓글을 쓰려면 별명이 필요합니다. 10초면 끝납니다.<div class="cv-btns"><button class="cv-no" type="button" data-win-close>나중에 하기</button>'
                  '<button class="cv-yes" type="button" data-go="rules">지금 만들기</button></div>')
        rules = win("rules", "운영 원칙을 지켜 주세요",
                    '<ul class="cv-rules"><li>다른 사람 · 회사를 사칭하거나 헐뜯는 글</li><li>거짓 정보 · 시세를 움직이려는 글</li>'
                    '<li>욕설 · 혐오 표현</li><li>광고 · 리딩방 권유 · 오픈채팅과 연락처</li></ul>'
                    '위 글은 올릴 수 없습니다. 신고가 3번 쌓이면 자동으로 가려지고, 되풀이하면 글쓰기가 정지됩니다.'
                    '<p class="cv-rules-sub">사안에 따라 법적 책임이 따를 수 있습니다. <a href="#">자세한 운영 원칙 보기</a></p>'
                    '<div class="cv-btns"><button class="cv-yes" type="button" data-go="pset">확인</button></div>')
        out += ask + rules + profile_set()
    return out


def profile_page():
    """내 프로필 — 별명 · 소개 · 프로필 편집 · 내가 쓴 글(어느 글에 썼는지 · 제목 · 답글 수). 본인만 본다."""
    mine = [("한국 증시 시황 · 11.18 17:40", "미국 물가 발표는 언제 반영되나요?", 2),
            ("주식 공부 3편 · 11.16 21:05", "분할 매수는 몇 번으로 나누는 게 좋을까요?", 5),
            ("증시 전망 · 11.14 09:12", "연말 전망에서 환율 가정이 궁금합니다", 0)]
    rows = "".join(f'<a class="cv-mine" href="mock_comments_thread.html"><small>{esc(w)}</small><b>{esc(t)}</b>'
                   f'<span class="cv-reply{" has" if n else ""}">{BUBBLE}<span>{n}</span></span></a>' for w, t, n in mine)
    return (f'<div class="cv-full comments" data-win="profile">{bar("내 프로필", close_href="mock_comments_member.html")}<div class="cv-full-body">'
            f'<div class="cv-prof"><div class="cv-prof-name">{ME}</div><div class="cv-big-av"><img src="{ava_src(ME_AVA)}" alt="" width="56" height="56"></div></div>'
            '<p class="cv-prof-intro">적립식으로 모으는 3년 차입니다.</p>'
            '<button class="cv-edit" type="button">프로필 편집</button>'
            f'<div class="cv-mine-h">내가 쓴 글 {len(mine)}</div>{rows}'
            + dk.excl_note("내 프로필은 나만 볼 수 있습니다.", margin="14px 0 0") + '</div></div>')


JS = """<script>(function(){
var q=function(s,r){return (r||document).querySelector(s);},qa=function(s,r){return [].slice.call((r||document).querySelectorAll(s));};
var BAD=/open\\.kakao|t\\.me\\/|telegram|band\\.us|텔레그램|오픈채팅|01[016789][- ]?\\d{3,4}[- ]?\\d{4}/i;
var sec=q('#comments-mock'),tg=q('[data-cm-toggle]'),fab=q('.cv-fab');
if(tg)tg.addEventListener('click',function(){var p=q('.comments-panel',sec);p.hidden=!p.hidden;sec.classList.toggle('is-open',!p.hidden);if(fab)fab.hidden=p.hidden;});
setTimeout(function(){var n=q('.post-nav');if(n)window.scrollTo(0,n.getBoundingClientRect().top+window.pageYOffset-70);},300);
function openWin(id){var w=q('[data-win="'+id+'"]');if(!w)return;w.hidden=false;var f=q('.cv-yes',w);if(f)f.focus();}
qa('[data-win]').forEach(function(w){w.addEventListener('click',function(e){if((e.target===w&&!w.classList.contains('cv-full'))||e.target.closest('[data-win-close]'))w.hidden=true;});});
document.addEventListener('keydown',function(e){if(e.key==='Escape')qa('[data-win]:not([data-win="profile"])').forEach(function(w){w.hidden=true;});});
qa('[data-need-login]').forEach(function(b){b.addEventListener('click',function(){openWin('login');});});
var RLEFT=__RLEFT__,toast=document.createElement('div');toast.className='cv-toast';toast.hidden=true;document.body.appendChild(toast);
function say(t){toast.textContent=t;toast.hidden=false;clearTimeout(say.t);say.t=setTimeout(function(){toast.hidden=true;},2500);}
qa('[data-share]').forEach(function(b){b.addEventListener('click',function(){if(navigator.share){navigator.share({title:document.title,url:location.href}).catch(function(){});}else{say('주소를 복사했습니다.');}});});
qa('[data-react]').forEach(function(b){if(b.hasAttribute('data-need-login'))return;b.addEventListener('click',function(){var on=!b.classList.contains('is-on'),n=q('span',b);
if(on){if(RLEFT<=0){say('좋아요 · 싫어요는 하루 30번까지 누를 수 있습니다. 내일 다시 눌러 주세요.');return;}RLEFT--;}
qa('[data-react]',b.parentNode).forEach(function(x){if(x.classList.contains('is-on')){x.classList.remove('is-on');q('span',x).textContent=+q('span',x).textContent-1;}});
if(on){b.classList.add('is-on');n.textContent=+n.textContent+1;}});});
var lg=q('[data-login-go]');if(lg)lg.addEventListener('click',function(){alert('목업: 여기서 구글 로그인 창이 뜹니다.');});
if(fab)fab.addEventListener('click',function(){openWin(fab.hasAttribute('data-guest')?'login':fab.hasAttribute('data-first')?'pask':'write');});
qa('[data-menu]').forEach(function(b){if(b.hasAttribute('data-need-login'))return;b.addEventListener('click',function(){var x=q('[data-menu-box="'+b.getAttribute('data-menu')+'"]');if(x)x.hidden=!x.hidden;});});
qa('[data-pick]').forEach(function(b){b.addEventListener('click',function(){var box=b.closest('.cv-pop');qa('[data-pick]',box).forEach(function(x){x.classList.remove('is-on');});b.classList.add('is-on');q('[data-report-send]',box).disabled=false;});});
qa('[data-report-send]').forEach(function(b){b.addEventListener('click',function(){b.closest('.cv-pop').innerHTML='<p class=\\"cv-done\\">신고를 받았습니다. 같은 댓글에 신고가 3번 쌓이면 자동으로 가리고 운영자가 확인합니다.</p>';});});
var of=q('[data-open-rform]');if(of)of.addEventListener('click',function(){of.style.display='none';q('[data-rform]').hidden=false;q('[data-ta]').focus();});
var ta=q('[data-ta]'),send=q('[data-send]'),err=q('[data-err]');
if(ta){ta.addEventListener('input',function(){q('[data-count]').textContent=ta.value.length+' / 2000';send.disabled=!ta.value.trim();err.hidden=true;});
send.addEventListener('click',function(){if(BAD.test(ta.value)){err.hidden=false;return;}alert('목업: 등록하면 답글 맨 아래에 바로 붙습니다.');});}
qa('[data-go]').forEach(function(b){b.addEventListener('click',function(){qa('[data-win]').forEach(function(w){w.hidden=true;});openWin(b.getAttribute('data-go'));if(b.getAttribute('data-go')==='pset')roll();});});
qa('[data-tool]').forEach(function(b){b.addEventListener('click',function(){var k=b.getAttribute('data-tool');qa('[data-panel]').forEach(function(p){p.hidden=p.getAttribute('data-panel')!==k||!p.hidden;});qa('[data-tool]').forEach(function(x){x.classList.toggle('is-on',x===b&&!q('[data-panel="'+k+'"]').hidden);});});});
function attach(kind,html){var a=q('[data-att="'+kind+'"]');q('[data-att-body]',a).innerHTML=html;a.hidden=false;qa('[data-panel]').forEach(function(p){p.hidden=true;});qa('[data-tool]').forEach(function(x){x.classList.remove('is-on');});if(window.cvChk)cvChk();}
var wed=q('[data-wta]'),wrange=null;
function keep(){var s=window.getSelection();if(s.rangeCount&&wed.contains(s.getRangeAt(0).startContainer))wrange=s.getRangeAt(0).cloneRange();}
if(wed){['keyup','mouseup','input','focus'].forEach(function(e){wed.addEventListener(e,keep);});document.addEventListener('selectionchange',keep);}
function putStk(k){var im=document.createElement('img');im.className='cv-stk-in';im.src='stickers/c_'+k+'.webp';im.alt='';im.width=80;im.height=80;im.setAttribute('data-k',k);
if(!wrange){wrange=document.createRange();wrange.selectNodeContents(wed);wrange.collapse(false);}
wrange.deleteContents();wrange.insertNode(im);wrange.setStartAfter(im);wrange.collapse(true);var s=window.getSelection();s.removeAllRanges();s.addRange(wrange);if(window.cvChk)cvChk();}
qa('[data-stk]').forEach(function(b){b.addEventListener('mousedown',function(e){e.preventDefault();});b.addEventListener('click',function(){putStk(b.getAttribute('data-stk'));});});
qa('[data-stab]').forEach(function(t){t.addEventListener('click',function(){var i=t.getAttribute('data-stab');qa('[data-stab]').forEach(function(x){x.setAttribute('aria-selected',String(x===t));});qa('[data-sgrid]').forEach(function(g){g.hidden=g.getAttribute('data-sgrid')!==i;});});});
qa('[data-atab]').forEach(function(t){t.addEventListener('click',function(){var p=t.getAttribute('data-atab');qa('[data-atab]').forEach(function(x){x.setAttribute('aria-selected',String(x===t));});qa('[data-agrid]').forEach(function(g){g.hidden=g.getAttribute('data-agrid')!==p;});});});
qa('[data-ava]').forEach(function(b){b.addEventListener('click',function(){qa('[data-ava]').forEach(function(x){x.classList.toggle('is-on',x===b);});q('[data-pav]').src='avatars/'+b.getAttribute('data-ava')+'.webp';});});
qa('[data-sym]').forEach(function(b){b.addEventListener('click',function(){attach('sym',q('template[data-card="'+b.getAttribute('data-sym')+'"]').innerHTML);});});
qa('[data-att-x]').forEach(function(b){b.addEventListener('click',function(){b.closest('[data-att]').hidden=true;if(window.cvChk)cvChk();});});
var A=__NICK_A__,B=__NICK_B__,pn=q('[data-pnick]'),pd=q('[data-pdone]'),ph=q('[data-phint]'),pi=q('[data-pintro]');
function pchk(){var v=pn.value.trim();q('[data-pcount]').textContent=v.length+' / 12';pd.disabled=v.length<2;}
function roll(){if(!pn)return;pn.value=A[Math.floor(Math.random()*A.length)]+B[Math.floor(Math.random()*B.length)];ph.className='cv-hint';ph.textContent='추천 별명입니다. 바꿔 쓰셔도 됩니다.';pchk();}
if(pn){pn.addEventListener('input',function(){ph.className='cv-hint';ph.textContent='2~12자로 적어 주세요.';pchk();});q('[data-reroll]').addEventListener('click',roll);
pi.addEventListener('input',function(){q('[data-icount]').textContent=pi.value.length+' / 100';});
pd.addEventListener('click',function(){var v=pn.value.trim();
if(/운영자|관리자|뉴팩트|newfact/i.test(v)){ph.className='cv-hint is-bad';ph.textContent='운영자로 보일 수 있는 별명은 쓸 수 없습니다.';return;}
if(v==='장기보유'){ph.className='cv-hint is-bad';ph.textContent='이미 쓰는 분이 있는 별명입니다.';return;}
location.href='mock_comments_profile.html';});}
var wt=q('[data-wtitle]'),wa=q('[data-wta]'),ws=q('[data-wsend]'),we=q('[data-werr]');
function wtext(){var o='';wa.childNodes.forEach(function f(n){if(n.nodeType===3)o+=n.nodeValue;else if(n.tagName==='IMG')o+='[:'+n.getAttribute('data-k')+':]';else if(n.tagName==='BR')o+='\\n';else{if(n.tagName==='DIV'&&o)o+='\\n';n.childNodes.forEach(f);}});return o;}
if(wa){var chk=window.cvChk=function(){var t=wtext();q('[data-wcount]').textContent=t.length+' / 2000';ws.disabled=!(wt.value.trim()&&t.trim());we.hidden=true;};
wt.addEventListener('input',chk);wa.addEventListener('input',chk);wa.addEventListener('paste',function(e){e.preventDefault();document.execCommand('insertText',false,(e.clipboardData||window.clipboardData).getData('text'));});
ws.addEventListener('click',function(){if(BAD.test(wt.value+' '+wa.textContent)){we.hidden=false;return;}alert('목업: 등록하면 목록 맨 위에 바로 붙습니다.');});}
var demo=document.body.getAttribute('data-demo');if(demo==='write'){openWin('write');wt.value='하이닉스 오늘 왜 이렇게 올랐나요';attach('sym',q('template[data-card="000660"]').innerHTML);wa.textContent='외국인이 많이 샀다던데 ';putStk('up_surprised');wa.appendChild(document.createTextNode(' 내일도 이어질지 궁금합니다 '));wrange=null;putStk('up_wonder');putStk('mid_question');wa.blur();q('[data-tool="stk"]').click();chk();}
})();</script>"""


def build(name, member=True, first=False, thread=False, demo=""):
    page = open(BASE, encoding="utf-8").read()
    n, body = list_view(member, first and not thread)
    sec = f'<section class="comments is-foldable is-open" id="comments-mock"><div class="comments-panel">{body}</div></section>'
    fab = "" if thread else (f'<button class="cv-fab" type="button" aria-label="댓글 쓰기"{"" if member else " data-guest"}{" data-first" if first else ""}>{PENCIL}</button>')
    nav = '<p class="post-nav">'
    i = page.index(nav) + len(nav)   # 버튼 줄 왼쪽 끝 `댓글 n` — 댓글이 있으면 검정
    page = (page[:i] + f'<button class="post-nav-cm{" has-cm" if n else ""}" type="button" data-cm-toggle aria-controls="comments-mock">{BUBBLE}'
            f'<span class="cm-label">댓글 {n}</span></button>' + page[i:])
    end = page.index("</p>", i) + 4
    page = page[:end] + CSS + sec + page[end:]
    js = JS.replace("__NICK_A__", json.dumps(NICK_A, ensure_ascii=False)).replace("__NICK_B__", json.dumps(NICK_B, ensure_ascii=False)).replace("__RLEFT__", str(REACT_LEFT))
    if demo:
        page = re.sub(r"<body", f'<body data-demo="{demo}"', page, count=1)
    page = page.replace("</body>", fab + (thread_page(member) if thread else "") + windows(member, first) + (profile_page() if demo == "profile" else "") + js + "</body>", 1)
    page = re.sub(r"<title>[^<]*</title>", f"<title>{TITLES[name]} — 목업</title>", page, count=1)   # 목업 목록에서 화면을 이름으로 찾게
    open(os.path.join(OUT, name), "w", encoding="utf-8").write(page)
    print(f"[댓글] {name}")


def main():
    os.makedirs(os.path.join(OUT, "stickers"), exist_ok=True)
    for _, ks in STICKERS:   # 스티커 줄에 든 컷만 course/chars 에서 사본
        for k in ks:
            shutil.copyfile(os.path.join(HERE, "..", "course", "chars", f"c_{k}.webp"), os.path.join(OUT, "stickers", f"c_{k}.webp"))
    build("mock_comments_member.html")
    build("mock_comments_guest.html", member=False)
    build("mock_comments_thread.html", thread=True)
    build("mock_comments_thread-guest.html", member=False, thread=True)
    build("mock_comments_first.html", first=True)
    build("mock_comments_write.html", demo="write")
    build("mock_comments_profile.html", demo="profile")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
