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
/* 캐릭터 = 이름 + 왕관(금색 하나, 빨강 · 파랑 X), 이름 · 그림 = 소개 페이지 링크 */
.cv-char{display:inline-flex;align-items:center;gap:3px;color:#111;text-decoration:none;}
.cv-char .cv-crown{flex:none;}
.cv-char-av{display:flex;flex:none;color:inherit;}
.cv-ch-top{margin:0 0 6px;font-size:16px;line-height:26px;color:#333;word-break:keep-all;}
.cv-ch{padding:18px 0;border-top:1px solid #E2E8F0;scroll-margin-top:70px;}
.cv-ch:target{background:#FFFBEA;margin:0 -16px;padding:18px 16px;border-radius:12px;}
.cv-ch-name{flex:1;min-width:0;}
.cv-ch-name b{display:inline-flex;align-items:center;gap:4px;font-size:19px;line-height:28px;color:#111;}
.cv-ch-name small{display:block;font-size:14px;line-height:20px;color:#6B7280;}
.cv-ch-sees{display:inline-block;margin:0 0 8px;padding:3px 10px;border-radius:6px;background:#F1F5F9;font-size:14px;line-height:20px;font-weight:700;color:#333;}
.cv-ch p{margin:8px 0 0;font-size:16px;line-height:26px;color:#333;word-break:keep-all;}
.cv-ch-h{margin:12px 0 0;font-size:14px;line-height:20px;font-weight:700;color:#111;}
.cv-ch-post{display:block;padding:8px 0 0;color:inherit;text-decoration:none;}
.cv-ch-post small{display:block;font-size:13px;line-height:19px;color:#6B7280;}
.cv-ch-post b{display:block;font-size:15px;line-height:22px;font-weight:700;color:#111;}
/* P614 숫자 = Inter: 토론 칸 · 화면 전체 창 글꼴 = 테마 --report-font('AS Num' 맨 앞) · 숫자만 있는 자리 = --num */
.comments,.cv-full,.cv-page{font-family:var(--report-font);}
/* P615 날짜 = 가장 작은 글씨 13/19 */
.comments .cm-date,.cv-pmeta,.cv-rtime{font-family:var(--num);font-size:12px;line-height:18px;font-variant-numeric:normal;}   /* 날짜 · 시각 = 12, 고정폭 숫자 끔(Inter 고정폭은 1 에 받침이 붙어 블로그 숫자와 달라 보임, 11-28 사용자) */
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
.comments .cv-react{display:inline-flex;align-items:center;gap:6px;margin:0;padding:4px 0;background:none;border:0;font:inherit;font-size:13px;line-height:20px;color:#333;font-variant-numeric:normal;cursor:pointer;-webkit-tap-highlight-color:transparent;}
.comments .cv-react svg{width:18px;height:18px;}   /* 아이콘 20 → 18(10% 작게, 11-28) */
/* 누른 상태 = 좋아요 부드러운 빨강 #ED8E87 · 싫어요 부드러운 파랑 #82B1F0 채움 + 숫자 같은 색 굵게(dk.CHART_UP · CHART_DN, 11-27 사용자). 소매 선만 흰색 */
.comments .cv-react.is-on span{font-weight:700;}
.comments .cv-react[data-react="up"].is-on{color:#ED8E87;}
.comments .cv-react[data-react="up"].is-on svg{fill:#ED8E87;stroke:#ED8E87;}
.comments .cv-react[data-react="down"].is-on{color:#82B1F0;}
.comments .cv-react[data-react="down"].is-on svg{fill:#82B1F0;stroke:#82B1F0;}
/* 캐릭터 그림 = 그림 속 색 원 가장자리(위쪽 0.5px 틈)가 보이지 않게 살짝 키워 원 틀로 자른다 */
.comments .cm-avatar img,.cv-big-av img{transform:scale(1.06);}
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
.comments .cv-reply{display:inline-flex;align-items:center;gap:6px;padding:4px 8px 4px 0;color:#333;text-decoration:none;font-size:13px;line-height:20px;font-weight:700;font-variant-numeric:normal;-webkit-tap-highlight-color:transparent;}
.comments .cv-reply.has{color:#333;}
.comments .cv-reply svg{width:18px;height:18px;}
.comments .cv-reply span,.comments .cv-react span{font-weight:400;}
.comments .cv-pop{margin:6px 0 0 31px;padding:12px;border:0;border-radius:8px;background:#F3F4F6;}   /* 연한 회색 바탕 · 외곽선 없음(기준 상자와 같은 회색) */
/* 신고 상자 = 왼쪽 칸(제목 → 그 아래 신고하기) · 오른쪽 칸(이유 칩). 칩은 제목 칸을 넘지 않고 오른쪽 칸 안에서 줄바꿈 */
.comments .cv-pop:has(.cv-chips){display:grid;grid-template-columns:auto minmax(0,1fr);grid-template-rows:auto 1fr;column-gap:12px;row-gap:10px;align-items:start;}
.comments .cv-pop:has(.cv-chips) .cv-pop-h{grid-column:1;grid-row:1;display:flex;align-items:center;gap:4px;white-space:nowrap;padding:6px 0 0;}   /* 왼쪽 여백 = 상자 안쪽 12 하나(오른쪽과 같게, 11-28) */
.comments .cv-pop-h svg{flex:none;width:16px;height:16px;}
.comments .cv-pop:has(.cv-chips) .cv-chips{grid-column:2;grid-row:1 / span 2;margin:0 0 0 10px;justify-content:flex-start;}
.comments .cv-pop:has(.cv-chips) [data-report-send]{grid-column:1;grid-row:2;align-self:start;justify-self:start;margin:0;padding:6px 14px;background:#fff;border:1px solid #888;border-radius:8px;color:#111;font:inherit;font-size:14px;line-height:20px;font-weight:700;cursor:pointer;}
.comments .cv-pop:has(.cv-chips) [data-report-send]:hover{border-color:#111;}   /* 늘 진한 테두리 · 진한 글자(흐리게 하지 않음) — 이유 없이 누르면 안내 띠 */
.comments .cv-pop .cv-done{grid-column:1 / -1;}
.comments .cv-pop[hidden]{display:none;}
.comments .cv-pop-h{font-size:14px;line-height:20px;font-weight:700;color:#111;}
.comments .cv-chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 12px;}
.comments .cv-chip{padding:5px 12px;border:1px solid #E2E8F0;border-radius:16px;background:#fff;font:inherit;font-size:14px;line-height:22px;color:#6B7280;cursor:pointer;-webkit-tap-highlight-color:transparent;}
.comments .cv-chip.is-on{border-color:#111;color:#111;font-weight:700;}
.comments .cv-done{margin:0;font-size:14px;line-height:20px;color:#6B7280;}
/* 안내 상자 — 주의 색(노랑 안내 상자 dk.notice 와 같은 바탕 · 테두리), 느낌표 아이콘 + 14/20 */
.comments .cv-guard{display:flex;align-items:flex-start;gap:6px;margin:14px 0 4px;padding:9px 11px;background:#FFF8E1;border:1px solid #F9E6B5;border-radius:8px;font-size:13px;line-height:19px;color:#333;word-break:keep-all;}   /* P619 = 자료 늦음 상자(dk.report_stamp late)와 같은 꼴 */
.comments .cv-guard svg{flex:none;width:14px;height:14px;margin-top:2px;color:currentColor;}
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
/* 스티커 줄 — 문장 줄과 따로 한 줄(글 위 · 글 아래). 비면 안 보임 */
.cv-stk-row{display:block;line-height:0;}
.cv-stk-row:empty{display:none;}
/* 글쓰기 내용 상자 = 위 스티커 줄 → 글자 칸 → 아래 스티커 줄. 테두리는 상자가 갖는다. 스티커를 누르면 빠진다 */
.cv-full .cv-edbox{padding:6px 12px;border:1px solid #E2E8F0;border-radius:8px;}
.cv-full .cv-edbox:focus-within{border-color:#111;}
.cv-full .cv-edbox .cv-ed{min-height:140px;padding:5px 0;border:0;border-radius:0;}
.cv-edbox .cv-stk-row img{cursor:pointer;}
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
# 좋아요 · 싫어요 = 엄지 두 개를 따로 그린다(돌리지 않음). 바깥선 → 소매 선 순서 — 눌린 상태에서 소매 선만 흰색으로 남는다
_TH = f'<svg viewBox="0 0 24 24" width="20" height="20" {_SVG} stroke-width="1.7">'
UP_ICON = (_TH + '<path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"/>'
           '<path d="M7 10v12"/></svg>')
DOWN_ICON = (_TH + '<path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z"/>'
             '<path d="M17 14V2"/></svg>')
SHARE = f'<svg viewBox="0 0 16 16" {_SVG} stroke-width="1.6"><path d="M9.5 2.5H13.5V6.5M13.5 2.5 8 8M11.5 9.5v3a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3"/></svg>'
GO = f'<svg viewBox="0 0 16 16" {_SVG} stroke-width="1.6"><path d="M6 3.5 10.5 8 6 12.5"/></svg>'
SIREN = f'<svg viewBox="0 0 16 16" {_SVG} stroke-width="1.6"><path d="M4.5 12.5V9a3.5 3.5 0 0 1 7 0v3.5M3 12.5h10M8 2v1.3M2.8 4.2l.9.9M13.2 4.2l-.9.9"/></svg>'   # 신고 = 경광등(가려진 글 원 안, P620)
WARN = f'<svg viewBox="0 0 16 16" {_SVG} stroke-width="1.6"><path d="M8 2 14.5 13.5h-13z"/><path d="M8 6.5v3.2M8 11.6v.1"/></svg>'
REASONS = ("리딩방 · 광고", "욕설 · 비방", "개인정보", "거짓 정보 · 시세 조종 의심", "기타")
ME = "주린이탈출"
# 프로필 그림 24종 — cut_avatars.py 가 output/avatars/ 에 자른다.
# 처음엔 회원마다 자동 배정(목록이 한 그림으로 도배되지 않게) · 내 프로필에서 바꾼다. 서버엔 번호만(a01 · p07).
AVA_TABS = [("동물", "a"), ("일반", "p")]
ME_AVA = "a12"   # 목업: 나 = 오리
# 캐릭터 10명 — 자기 이름으로 쓰고 이름 옆 왕관으로 회원과 갈린다. 이름 · 그림 · 왕관을 누르면 소개 페이지의 그 캐릭터 자리로.
# (이름, 그림, 종류(히어로 판), 보는 것 한 줄, 소개, 흐름 자리). 그림은 캐릭터 몫으로 예약 — 회원 자동 배정에서 뺀다.
CHARS = [
    ("기록이", "p01", "로봇", "지난 비슷한 때", "오늘 같은 날이 전에도 있었는지 기록에서 꺼내 옵니다. 날짜는 꼭 붙입니다.", "기록"),
    ("견줌이", "p07", "요원", "비교 대상", "숫자가 나오면 일단 묻는다. 무엇과 견준 건데? 비교 대상이 없으면 없다고 말하는 편.", "비교"),
    ("실적이", "p09", "바이킹", "실적 · 이익 예상", "실적과 이익 예상, 그것만 봐요. 얼마나 바뀌었는지요. 음, 나머지는 다음 실적 때 다시 볼게요.", "종목"),
    ("물결이", "p02", "가면 히어로", "가격 · 거래량", "가격이 움직이면 거래량부터 봐요! 따라왔는지, 시장 전체가 움직인 날인지 바로 가려요.", "종목"),
    ("엇박이", "p04", "선글라스 고양이", "갈리는 지표", "다들 같은 쪽을 볼 때, 반대쪽을 가리키는 지표는 없을까요? 그걸 찾아서 되물어요.", "갈림"),
    ("새싹이", "p05", "외계인", "처음 보는 말", "이 말은 무슨 뜻이에요? 어려운 말이 나오면 제가 대신 물어볼게요.", "입문"),
    ("돈길이", "p12", "공룡", "실제 돈의 흐름", "돈이 어디로 가는지… 그게 제일 궁금하네요. 업종 ETF 에 실제로 들어온 돈을 운용사 값으로 세어 봐요. 급할 건 없어요, 내일도 셀 거니까요.", "돈의 흐름"),
    ("채점이", "p08", "마녀", "미리 적은 전망", "미리 적어 둔 가설을 센다. 판정일까지 며칠. 지금 어느 쪽. 그것만.", "전망 · 결과"),
    ("소식이", "p10", "토끼 귀 소녀", "이슈 단계", "새 소식은 방향과 단계만 전한다고 해요. 확정인지, 아직 논의 중인지요.", "이슈"),
    ("이음이", "p06", "우주인", "미국과 한국", "밤새 미국이 이랬는데 오늘 한국은 어땠나, 둘을 이어서 보면 재밌더라고요.", "함께 움직인 것"),
]
CHAR = {c[0]: c for c in CHARS}
CHAR_AVAS = {c[1] for c in CHARS}
# 캐릭터 그림 = 히어로 판(11-27). 공주(p03) · 왕(p11)은 머리 왕관이 캐릭터 왕관 표시와 헷갈려
# 캐릭터에도 회원 그림에도 안 씀(자동 배정 · 고르기 둘 다 뺌).
CROWN_AVAS = {"p03", "p11"}
CHAR_PAGE = "mock_comments_characters.html"
CROWN = ('<svg class="cv-crown" viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">'   # 왕관 = 금색 · 끝 구슬 셋 · 아래 띠(시안 A)
         '<path d="M4 18.5h16v2H4z" fill="#E0A21B"/><path d="M4 17 3 8l5 4 4-7 4 7 5-4-1 9z" fill="#F4B942" stroke="#C9870F" stroke-width="1" stroke-linejoin="round"/>'
         '<circle cx="3" cy="7.5" r="1.6" fill="#F4B942" stroke="#C9870F" stroke-width="1"/><circle cx="12" cy="4.2" r="1.8" fill="#F4B942" stroke="#C9870F" stroke-width="1"/>'
         '<circle cx="21" cy="7.5" r="1.6" fill="#F4B942" stroke="#C9870F" stroke-width="1"/></svg>')
CROWN_IN = CROWN.replace("<svg ", '<svg style="vertical-align:-2px;" ', 1)   # 문장 속 왕관
CROWN_BIG = CROWN.replace('width="14" height="14"', 'width="18" height="18"')
CROWN_NAME = CROWN.replace('width="14" height="14"', 'width="24" height="24"')   # 댓글 이름 옆 = 캐릭터 그림(.cm-avatar 24)과 같은 크기
# 캐릭터가 쓴 글 예시(소개 페이지 `쓴 글`) — 목록 · 종목 화면에 든 글은 그 화면으로, 나머지는 글 화면 예시로
CHAR_POSTS = {
    "기록이": [("11.18 증시 시황", "오늘 같은 날, 기록에 두 번 있었습니다"), ("11.17 미국 증시 리포트", "평소 범위 밖으로 나간 날, 다음 5일의 기록입니다")],
    "견줌이": [("11.18 증시 시황", "거래대금 12조? 무엇과 견준 건데"), ("11.26 삼성전자", "외국인 순매수 3천억, 평소 대비로는 1.8배네")],
    "실적이": [("11.27 SK하이닉스", "이익 예상, 한 달 새 그대로예요")],
    "물결이": [("11.27 SK하이닉스", "오늘 상승, 거래량도 따라왔어요!"), ("11.18 증시 시황", "두 종목 거래량만 평소의 2.1배!")],
    "엇박이": [("11.26 미국 증시 리포트", "단기 신호는 상승 쪽인데, 돈은 왜 5일째 빠질까요?")],
    "새싹이": [("11.18 증시 시황", "평소가 20일 평균이라는 뜻이에요?")],
    "돈길이": [("11.26 반도체 업계", "반도체 ETF 에… 실제 돈이 5일째 들어왔네요")],
    "채점이": [("11.25 증시 전망", "가설 ③. 판정일까지 7일. 다섯 날 중 셋이 가설 쪽")],
    "소식이": [("11.26 미국 증시 리포트", "관세 이슈, 아직 논의 중 단계라고 해요")],
    "이음이": [("11.27 한국 증시 리포트", "밤새 미국 반도체 −2%, 오늘 한국 반도체도 −1.5%더라고요")],
}


def ava_of(name):
    """회원 → 그림 번호. 목업은 별명 글자 합으로 고정 배정(실서비스 = 가입 때 회원 번호로 배정 · 바꾸면 고른 값)."""
    if name == ME:
        return ME_AVA
    if name in CHAR:
        return CHAR[name][1]
    pool = [k for k in [f"a{i:02d}" for i in range(1, 13)] + [f"p{i:02d}" for i in range(1, 13)] if k not in CHAR_AVAS | CROWN_AVAS and k != ME_AVA]
    return pool[int(hashlib.md5(name.encode()).hexdigest(), 16) % len(pool)]


def ava_src(k):
    return f"avatars/{k}.webp"


def ava_picker(on):
    tabs = "".join(f'<button class="cv-stk-tab" type="button" role="tab" data-atab="{p}" aria-selected="{str(p == on[0]).lower()}">{n}</button>' for n, p in AVA_TABS)
    grids = "".join(f'<div class="cv-ava-grid" data-agrid="{p}"{"" if p == on[0] else " hidden"}>'
                    + "".join(f'<button class="cv-ava-pick{" is-on" if f"{p}{i:02d}" == on else ""}" type="button" data-ava="{p}{i:02d}" aria-label="{n} 그림 {i}">'
                              f'<img src="{ava_src(f"{p}{i:02d}")}" alt="" width="48" height="48"></button>' for i in range(1, 13) if f"{p}{i:02d}" not in CROWN_AVAS)
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
              ("물결이", "11.18 17:08", "두 종목 거래량, 평소(20일 평균)의 2.1배! 지수가 오른 날 거래량이 두 종목에만 몰린 건 11월 들어 두 번째예요."),
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
        ("기록이", "11.18 16:20", "오늘 같은 날, 기록에 두 번 있었습니다", "오늘 지수는 올랐는데 오른 종목은 절반이 안 됐습니다. 2024-08 과 2025-04 에도 같은 날이 있었습니다. 그 다음 5일은 두 번 중 한 번 상승이었습니다. 이번은 어느 쪽일지 적어 둡니다.", "", [
            ("장기보유", "11.18 16:45", "그때 두 번은 뭐가 달랐나요?"),
        ]),
        THREAD,
        ("견줌이", "11.18 16:05", "거래대금 12조? 무엇과 견준 건데", "코스피 거래대금 12.4조 원. 많아 보이네. 근데 평소(20일 평균)와 견주면 1.1배. 배수로 보면 오늘은 그냥 보통 날이군.", "", [
            ("새싹이", "11.18 16:12", "평소가 20일 평균이라는 뜻이에요? 왜 하필 20일이에요?[:mid_question:]"),
            ("조심조심", "11.18 16:33", "저도 거래대금만 보고 큰 날인 줄 알았네요."),
        ]),
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
    "오전 납품 기사 보셨나요": {"stk": "up_news"},   # 댓글 카드 · 댓글 화면 예시 — 글 아래 큰 스티커
        "지수는 올랐는데 제 계좌는 그대로였던 이유가 있었네요.": {"stk": "up_cry"},
}
# 종목 카드 예시 값 — (이름, 아래 줄, 값, 등락, 오름?, 선 그래프 점)
STOCKS = {
    "000660": ("SK하이닉스", "000660 · 코스피", "612,000원", "+4.26%", True, [30, 28, 31, 27, 25, 26, 22, 20, 21, 17, 15, 16, 12, 10]),
    "005930": ("삼성전자", "005930 · 코스피", "98,700원", "+2.81%", True, [28, 29, 26, 27, 24, 22, 23, 20, 21, 18, 17, 15, 14, 12]),
    "NVDA": ("엔비디아", "NVDA · 나스닥", "$125.53", "-14.01%", False, [10, 12, 11, 14, 15, 14, 16, 15, 17, 16, 22, 26, 29, 31]),
}
STICKERS = [   # (탭 이름, [컷 …]) 그림 여섯 장(course/sheet_to_webp.py 로 자름) 먼저, 그 뒤 옛 주식 공부 컷
    ("상승이", ["up_flip", "up_panic", "up_throw", "up_box", "up_flat", "up_chicken", "up_night",
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
# 스티커 크기 고르기(11-28) — 그림은 모두 같은 칸(320 정사각)인데 캐릭터 혼자 있는 컷은 몸이 칸을 꽉 채워 크게,
# 소품이 많은 컷은 작게 보인다. 컷마다 캐릭터 몸 색 넓이를 재서 같은 캐릭터 가운데값보다 큰 컷만 줄인다
# (약 1.2배 이상 = 15% · 1.1배 안팎 = 10%). 작은 컷은 키우지 않는다(칸을 넘는다).
STK_SHRINK = {
    15: ["up_sweat", "up_panic", "up_buy", "up_chicken", "up_surprised",
         "down_calm", "down_happy",
         "mid_thanks", "mid_explain", "mid_think", "mid_clap", "mid_stretch"],
    10: ["up_walk",
         "down_shrug", "down_thumb", "down_grumpy", "down_frown", "down_sulky",
         "mid_caution", "mid_eat", "mid_workout", "mid_music", "mid_photo"],
}
STK_BOX = {   # 자리마다 (선택자, 기본 px, 10% 줄인 px, 15% 줄인 px) — 모두 정수
    "list": (".comments .cv-stk", 96, 86, 82),
    "inline": (".cv-stk-in", 80, 72, 68),
    "pick": (".cv-stk-pick img", 62, 56, 53),
    "card": (".cc-stk", 56, 50, 48),
}


def stk_css():
    out = "/* 스티커 크기 고르기 — 몸이 크게 든 컷만 10 · 15% 작게(STK_SHRINK) */\n"
    for pct, col in ((10, 2), (15, 3)):
        for sel, *px in STK_BOX.values():
            sels = ",".join(f'{sel}[src$="c_{k}.webp"]' for k in STK_SHRINK[pct])
            out += f"{sels}{{width:{px[col - 1]}px;height:{px[col - 1]}px;}}\n"
    tight = ",".join(f'.comments .cv-stk[src$="c_{k}.webp"]' for ks in STK_SHRINK.values() for k in ks)
    out += f"{tight}{{margin-top:13px;}}\n"   # 몸이 칸을 꽉 채우는 컷 = 위 글자와 붙어 보임 → 8 + 5 (글 화면 · 붙인 스티커)
    tight_in = ",".join(f'.cv-stk-in[src$="c_{k}.webp"]' for ks in STK_SHRINK.values() for k in ks)
    out += f"{tight_in}{{margin-top:7px;}}\n"   # 목록 본문 안 스티커(cv-stk-in)도 같이 → 2 + 5 (11-28, 처음엔 cv-stk 에만 넣어 목록에 안 먹었다)
    return out


CSS = CSS.replace("</style>", stk_css() + "</style>", 1)
TITLES = {   # 목업 목록에 보이는 이름
    "mock_comments_member.html": "댓글 목록 (로그인 뒤)",
    "mock_comments_guest.html": "댓글 목록 (로그인 전)",
    "mock_comments_thread.html": "댓글 글 화면 · 답글 · 스티커 붙은 모습 (로그인 뒤)",
    "mock_comments_thread-guest.html": "댓글 글 화면 (로그인 전)",
    "mock_comments_first.html": "댓글 처음 쓸 때 · 프로필 만들기 · 운영 원칙",
    "mock_comments_write.html": "댓글 글쓰기 · 스티커 고르기 · 종목 붙이기",
    "mock_comments_profile.html": "댓글 내 프로필",
    "mock_comments_characters.html": "Newfact 캐릭터 소개 — 10명 · 보는 칸 · 쓴 글 (댓글의 왕관 · 이름을 누르면 여기로)",
}
STK_MAX = 3   # 댓글 하나에 스티커 3개까지(처음 · 끝 합쳐서) — 넘겨 누르면 안내 띠, 서버도 4개부터 거절
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


def name_tag(name):
    """이름 — 운영자 = Newfact · 캐릭터 = 이름 + 왕관(소개 페이지의 그 캐릭터 자리로 가는 링크) · 회원 = 별명."""
    if name == "owner":
        return '<span class="cm-name">Newfact</span>'
    if name in CHAR:
        return f'<a class="cm-name cv-char" href="{CHAR_PAGE}#{name}" aria-label="{esc(name)} — Newfact 캐릭터 소개">{esc(name)}{CROWN_NAME}</a>'
    return f'<span class="cm-name">{esc(name)}</span>'


def avatar_tag(name):
    return f'<a class="cv-char-av" href="{CHAR_PAGE}#{name}" aria-label="{esc(name)} 소개">{avatar(name)}</a>' if name in CHAR else avatar(name)


def head(name, when, key, member, date=True, mine=False):
    """이름 줄 — 사진 · 이름 · (오른쪽) 날짜 · 점 세 개(신고, 내 글은 삭제). 로그인 전에는 점 세 개가 로그인 창을 연다."""
    owner = name == "owner"
    menu = "" if owner else (f'<button class="cv-menu" type="button" aria-label="{"삭제" if mine else "신고"}" data-menu="{key}"'
                             f'{"" if member else " data-need-login"}>{DOTS}</button>')
    return (f'<div class="cv-head">{avatar_tag(name)}{name_tag(name)}'
            + (f'<span class="cm-date">{when}</span>' if date else '<span class="cm-date"></span>') + f'{menu}</div>')


def menu_box(key, mine):
    if mine:
        return f'<div class="cv-pop" data-menu-box="{key}" hidden><button class="cm-btn" type="button">삭제</button></div>'
    chips = "".join(f'<button class="cv-chip" type="button" data-pick>{esc(t)}</button>' for t in REASONS)
    return (f'<div class="cv-pop" data-menu-box="{key}" hidden><div class="cv-pop-h">{SIREN}신고하는 이유</div>'
            f'<div class="cv-chips">{chips}</div><button class="cm-btn" type="button" data-report-send>신고하기</button></div>')


STK_TOKEN = re.compile(r"\[:([a-z]+_[a-z]+):\]")


def rich(text):
    """글 → HTML. 스티커 [:up_cry:] 는 문장 줄에 넣지 않는다 — 글 위 줄(글자 앞에 붙은 것) · 글 아래 줄(나머지, 문장 사이 것 포함)에 따로 한 줄로.
    저장은 짧은 표시만, 그림은 우리 파일."""
    img = lambda k: f'<img class="cv-stk-in" src="stickers/c_{k}.webp" alt="" width="80" height="80">'
    row = lambda ks: f'<span class="cv-stk-row">{"".join(map(img, ks))}</span>' if ks else ""
    lead = re.match(r"(?:\s*\[:[a-z]+_[a-z]+:\])+", text)
    head = STK_TOKEN.findall(lead.group(0)) if lead else []
    rest = text[lead.end():] if lead else text
    tail = STK_TOKEN.findall(rest)
    body = re.sub(r"[ \t]{2,}", " ", STK_TOKEN.sub(" ", rest)).strip()
    return row(head) + esc(body) + row(tail)


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
    up, down = counts(seed)
    h = sum(ord(ch) * (i + 1) for i, ch in enumerate(seed))
    need = "" if member else " data-need-login"
    on = " is-on" if member and up and h % 3 == 0 else ""   # 목업: 몇 개는 이미 누른 모습(부드러운 빨강)으로 시작
    return (f'<button class="cv-react{on}" type="button" data-react="up"{need} aria-label="좋아요 {up}">{UP_ICON}<span>{up}</span></button>'
            f'<button class="cv-react" type="button" data-react="down"{need} aria-label="싫어요 {down}">{DOWN_ICON}<span>{down}</span></button>')


def item(c, member, key, link, tag=""):
    name, when, title, text, state, replies = c
    if state == "hidden":
        return hidden_row()
    n = rcount(name + title)
    return (f'<li class="cv-item">{f"<span class=cv-tag>{esc(tag)}</span>" if tag else ""}{head(name, when, key, member, mine=state == "me")}'
            f'<a class="cv-main" href="{link}"><div class="cv-title">{esc(title)}</div><p class="cv-text">{rich(text)}</p>{extras(title).replace("<a ", "<span ").replace("</a>", "</span>")}</a>'
            f'<div class="cv-foot">{reacts(name + title, member)}<a class="cv-reply{" has" if n else ""}" href="{link}" aria-label="답글 {n}개 · 답글 쓰기">{BUBBLE}<span>{n}</span></a></div>'
            f'{menu_box(key, state == "me") if member else ""}</li>')


def guard():
    """안내 상자 = 종목 페이지 맨 위 회색 기준 상자(dk.report_stamp)와 같은 값을 글 안 style 로 — 바탕 #F3F4F6 · 글자 13/19 #6B7280 · 아이콘 14 같은 회색."""
    ico = WARN.replace("<svg ", '<svg width="14" height="14" style="flex:none;margin-top:2px;" ', 1)
    return ('<p class="cv-guard" style="display:flex;gap:6px;align-items:flex-start;margin:14px 0 14px;padding:10px 12px;background:#F3F4F6;border:0;'
            f'border-radius:8px;font-size:13px;line-height:19px;color:#6B7280;word-break:keep-all;">{ico}<span>{esc(GUARD)}</span></p>')


def note():
    return dk.excl_note("회원이 쓴 의견이며 Newfact의 의견이 아닙니다. 투자 권유가 아니고, 판단과 책임은 읽는 분에게 있습니다.", margin="14px 0 0")   # 왕관 글 = AI 문장은 뺌(11-27 사용자)


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
        rows += (f'<li class="cv-item">{head(who, rwhen, f"r{k}", member, date=False, mine=who == ME)}<p class="cv-text">{rich(rtext)}</p>{extras(rtext)}'
                 f'<div class="cv-rtime">{rwhen}</div><div class="cv-foot">{reacts(who + rtext, member)}</div>'
                 f'{menu_box(f"r{k}", who == ME) if member and who != "owner" else ""}</li>')
    return (f'<div class="cv-full cv-page" data-win="thread">{top}<div class="cv-full-body"><div class="comments is-open">{post}'
            f'<div class="cv-count">답글 {rcount(name + title)}</div>{box}{guard()}<ol class="cv-list cv-rlist">{rows}</ol>{note()}</div></div></div>')


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
            '<div class="cv-edbox"><div class="cv-stk-row" data-stk-top></div>'
            '<div class="cv-ed" data-wta contenteditable="true" role="textbox" aria-multiline="true" aria-label="내용" data-ph="내용을 입력하세요. 스티커는 글 위나 아래 줄에 3개까지 들어갑니다."></div>'
            '<div class="cv-stk-row" data-stk-bot></div></div>'
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
qa('[data-pick]').forEach(function(b){b.addEventListener('click',function(){var box=b.closest('.cv-pop');qa('[data-pick]',box).forEach(function(x){x.classList.remove('is-on');});b.classList.add('is-on');});});
qa('[data-report-send]').forEach(function(b){b.addEventListener('click',function(){if(!q('[data-pick].is-on',b.closest('.cv-pop'))){say('신고하는 이유를 골라 주세요.');return;}b.closest('.cv-pop').innerHTML='<p class=\\"cv-done\\">신고를 받았습니다. 같은 댓글에 신고가 3번 쌓이면 자동으로 가리고 운영자가 확인합니다.</p>';});});
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
/* 스티커는 문장 줄에 넣지 않는다 — 글자 칸 위 줄 · 아래 줄에만. 커서가 글 맨 앞이면 위 줄, 아니면 아래 줄. 합쳐서 __STK_MAX__개. 누르면 빠진다 */
var stop=q('[data-stk-top]'),sbot=q('[data-stk-bot]');
function putStk(k){if(qa('img',stop).length+qa('img',sbot).length>=__STK_MAX__){say('스티커는 __STK_MAX__개까지 넣을 수 있습니다.');return;}
var im=document.createElement('img');im.className='cv-stk-in';im.src='stickers/c_'+k+'.webp';im.alt='';im.width=80;im.height=80;im.setAttribute('data-k',k);im.title='누르면 빠집니다';
var before='x';if(wrange){var r=document.createRange();r.selectNodeContents(wed);r.setEnd(wrange.startContainer,wrange.startOffset);before=r.toString();}
((!before.trim()&&wed.textContent.trim())?stop:sbot).appendChild(im);
im.addEventListener('click',function(){im.parentNode.removeChild(im);if(window.cvChk)cvChk();});if(window.cvChk)cvChk();}
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
function wtext(){var o='';wa.childNodes.forEach(function f(n){if(n.nodeType===3)o+=n.nodeValue;else if(n.tagName==='BR')o+='\\n';else{if(n.tagName==='DIV'&&o)o+='\\n';n.childNodes.forEach(f);}});function tk(row){return qa('img',row).map(function(x){return '[:'+x.getAttribute('data-k')+':]';}).join('');}return tk(stop)+o+tk(sbot);}
if(wa){var chk=window.cvChk=function(){var t=wtext();q('[data-wcount]').textContent=t.length+' / 2000';ws.disabled=!(wt.value.trim()&&t.trim());we.hidden=true;};
wt.addEventListener('input',chk);wa.addEventListener('input',chk);wa.addEventListener('paste',function(e){e.preventDefault();document.execCommand('insertText',false,(e.clipboardData||window.clipboardData).getData('text'));});
ws.addEventListener('click',function(){if(BAD.test(wt.value+' '+wa.textContent)){we.hidden=false;return;}alert('목업: 등록하면 목록 맨 위에 바로 붙습니다.');});}
var demo=document.body.getAttribute('data-demo');if(demo==='write'){openWin('write');wt.value='하이닉스 오늘 왜 이렇게 올랐나요';attach('sym',q('template[data-card="000660"]').innerHTML);wa.textContent='외국인이 많이 샀다던데 내일도 이어질지 궁금합니다 ';wrange=null;putStk('up_surprised');putStk('mid_question');wa.blur();q('[data-tool="stk"]').click();chk();}
})();</script>"""


KEY_RE = re.compile(r"(apiKey:\s*')[^']*(')")   # 목업은 로그인 · Firestore 를 안 쓴다 — 테마에 든 Firebase 웹 키 값은 비워서 쓴다


def write_out(name, page):
    open(os.path.join(OUT, name), "w", encoding="utf-8").write(KEY_RE.sub(r"\1\2", page))
    print(f"[댓글] {name}")


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
    js = JS.replace("__NICK_A__", json.dumps(NICK_A, ensure_ascii=False)).replace("__NICK_B__", json.dumps(NICK_B, ensure_ascii=False)).replace("__RLEFT__", str(REACT_LEFT)).replace("__STK_MAX__", str(STK_MAX))
    if demo:
        page = re.sub(r"<body", f'<body data-demo="{demo}"', page, count=1)
    page = page.replace("</body>", fab + (thread_page(member) if thread else "") + windows(member, first) + (profile_page() if demo == "profile" else "") + js + "</body>", 1)
    page = re.sub(r"<title>[^<]*</title>", f"<title>{TITLES[name]} — 목업</title>", page, count=1)   # 목업 목록에서 화면을 이름으로 찾게
    write_out(name, page)


# ── 글 아래 댓글 카드 · 댓글 화면 ─────────────────────────────────────────────
# 글 · 종목 페이지 끝 = 댓글을 상자(카드)로: 1개면 카드 하나, 2개 이상이면 좌우로 밀어 보는 카드 + 점. 점 아래 `댓글 더 보기` → 댓글 화면.
# 댓글 화면 = 새 페이지: 종목 페이지에서 왔으면 위에 그 종목 봉차트 → 댓글 목록 → 오른쪽 아래 연필(쓰기).
# NEW = 24시간 안에 쓴 댓글(목업 지금 = 11.27 15:40). 카드는 최신 CARD_N 개가 저절로 넘어가고, 나머지는 댓글 화면에 전부(버리지 않음).
STOCK_BASE = os.path.join(HERE, "..", "kr-stocks", "output", "mock_000660.html")
STOCK_REAL = os.path.join(HERE, "..", "kr-stocks", "output", "000660.html")   # 차트 자료 = 발행 본문 쪽(내 평단 없는 것)
STORY_BANNER = "../../market-commentary/output/story-mock/images/commentary-2026-11-18-pm.webp"   # 시황 글 배너(목업 사본)
STOCK_REF = os.path.join(HERE, "ref", "000660_bars.json")   # 일봉 사본(git) — 종목 출력(kr-stocks/output)은 git 에 없어 다른 PC 에서는 이 사본으로 그린다
KOSPI_REAL = os.path.join(HERE, "..", "kr-market-report", "output", "report_body.html")   # 시황 글 댓글 화면 = 코스피 봉차트(한국 증시 리포트와 같은 차트)
NOW = (11, 27, 15 * 60 + 40)
CARD_N = 3   # 카드 = 최신 3개, 저절로 넘어감(3초) · 손대면 멈췄다가 다시
STOCK_CMTS = [   # SK하이닉스 페이지에 달린 댓글 예시 (최신이 위) — 꼴은 DAYS 와 같다
    ("반도체곰", "11.27 15:21", "사흘 하락 뒤 오늘 크게 상승했네요", "사흘 하락하고 오늘 8% 넘게 상승했습니다. 외국인 순매수가 같이 늘었는지 수급 탭에서 확인해 보려고요.", "", [
        ("데이터센터", "11.27 15:30", "거래량도 평소보다 많았습니다[:up_surprised:]"),
        ("owner", "11.27 15:38", "11.27 외국인 순매수는 수급 탭 `누가 샀나?` 칸에 장 마감 뒤 올라갑니다."),
    ]),
    ("물결이", "11.27 15:05", "오늘 상승, 거래량도 따라왔어요!", "사흘 하락 뒤 오늘 8.94% 상승! 거래량은 평소(20일 평균)의 2.3배예요. 코스피는 0.6% 상승이라 시장 전체가 움직인 날은 아니에요.", "", [
        ("실적이", "11.27 15:12", "이익 예상, 한 달 새 그대로예요. 가격만 먼저 움직인 날. 음, 저는 다음 실적 때 다시 볼게요."),
        ("반도체곰", "11.27 15:25", "거래량 배수도 수급 탭에서 볼 수 있나요?"),
    ]),
    ("데이터센터", "11.27 11:02", "오전 납품 기사 보셨나요", "오전에 나온 납품 기사 뒤로 거래량이 평소보다 많습니다. 기사 자체는 지난달 발표를 다시 쓴 것 같기도 하고요.", "", []),
    (ME, "11.26 20:15", "실적 발표 다음 날 움직임이 궁금합니다", "지난 실적 발표 때 다음 날 얼마나 움직였는지 기록에서 볼 수 있으면 좋겠어요.", "me", [
        ("owner", "11.26 20:40", "실적 탭 `발표 다음 날` 칸에 지난 8번의 발표 다음 날 등락이 있습니다."),
    ]),
    ("장기보유", "11.25 09:40", "최고가 대비 많이 내려왔네요", "최고가 대비 40% 가까이 하락했습니다. 시장 전체 때문인지 이 종목만의 일인지 궁금합니다.", "", [
        ("조심조심", "11.25 10:12", "같은 기간 코스피도 같이 하락했으니 반도체 업계 전체를 같이 봐야 할 것 같아요."),
    ]),
    ("", "11.24 22:10", "", "", "hidden", []),
    ("새내기", "11.24 18:30", "120일 이동평균선은 어떻게 보나요", "보라색 선이 120일 평균이라는데 지금 가격이 그 아래면 어떤 뜻인가요?[:mid_question:]", "", [
        ("owner", "11.24 19:02", "지난 120거래일 종가 평균보다 지금 가격이 낮다는 뜻입니다. 그 자체로 앞으로의 방향을 말해 주지는 않습니다."),
    ]),
    ("조심조심", "11.23 21:05", "미국 반도체 지수도 같이 봅니다", "밤사이 미국 반도체 지수가 크게 움직이면 다음 날 아침 영향이 커서 저는 같이 봅니다.", "", []),
]
STOCK_TOTAL = 327
ONE_CMT = ("새내기", "11.27 14:52", "오늘 시황 잘 읽었습니다", "환율 설명이 쉬워서 이해가 잘 됐습니다[:mid_thanks:] 내일 미국 물가 발표 뒤 시황도 기다리겠습니다.", "", [])
ONE_CMT_R = ("장기보유", "11.27 16:48", "외국인 순매수 표 잘 봤습니다", "수급 탭에서 외국인이 사흘 만에 순매수로 돌아선 걸 확인했습니다[:mid_proof:] 업종별로도 나눠 보면 좋겠네요.", "", [])
ONE_CMT_I = ("조심조심", "11.27 09:12", "반도체 지수는 오르는데", "업계 전체는 괜찮은데 엔비디아만 빠지는 걸 보면 회사 일로 보는 게 맞겠네요.", "", [])
ONE_CMT_F = ("장기보유", "11.27 10:30", "전망A 맞았네요", "급락 뒤에 더 빠질 줄 알았는데 생각보다 빨리 회복했습니다[:mid_question:]", "", [])
ARTICLE_CMTS = [   # Newfact 기사(크래프톤 거대언어모델 출시)에 달린 댓글 예시 5개 (최신이 위)
    ("게임좋아", "11.27 11:42", "게임 회사가 언어모델까지 만드네요", "게임 안 캐릭터 대사에 쓰려는 건지 궁금합니다[:mid_question:] 기사에 나온 쓰임새를 보니 게임 밖에서도 쓰려는 것 같네요.", "", []),
    ("장기보유", "11.27 11:30", "자체 개발이라는 점이 눈에 띕니다", "다른 회사 모델을 빌려 쓰는 게 아니라 직접 만들었다는 게 핵심이네요. 개발비가 실적에 어떻게 반영될지는 다음 분기에 확인해 보겠습니다.", "", []),
    ("새내기", "11.27 11:05", "거대언어모델이 정확히 뭔가요?", "기사에 나온 말인데 처음 들어 봐서요[:mid_think:] 주식 공부 글에도 설명이 있으면 좋겠습니다.", "", []),
    ("조심조심", "11.27 10:48", "출시와 성과는 따로 봐야겠네요", "정식 출시까지는 확인된 사실이고, 실제로 얼마나 쓰일지는 아직 숫자가 없네요. 이용자 수가 나오면 다시 보겠습니다.", "", []),
    ("반도체곰", "11.27 10:21", "기사 깔끔하게 정리돼 있네요", "무엇이 새로 나왔는지 한눈에 들어왔습니다[:mid_thanks:]", "", []),
]
ARTICLE_TOTAL = 214   # 목업 댓글 수 = 세 자리
REPORT_CMTS = [ONE_CMT_R,
    ("데이터센터", "11.27 16:31", "업종별 등락 표가 보기 좋네요", "어느 업종이 평소보다 크게 움직였는지 한눈에 들어옵니다[:mid_proof:]", "", []),
    ("새내기", "11.27 16:20", "평소 범위 밖이 무슨 뜻인가요?", "리포트에 자주 나오는 말인데 기준이 궁금합니다[:mid_think:]", "", []),
    ("조심조심", "11.27 16:08", "거래대금도 같이 봐야겠네요", "지수는 올랐는데 거래대금이 평소보다 많았는지 표에서 다시 확인했습니다.", "", []),
    ("게임좋아", "11.27 15:57", "마감 뒤 바로 올라와서 좋습니다", "퇴근길에 오늘 장을 정리하기 편했습니다[:mid_thanks:]", "", []),
]
STORY_CMTS = [ONE_CMT,
    ("장기보유", "11.27 14:40", "환율과 외국인 흐름을 같이 설명해 주네요", "두 가지를 따로 보다가 이어서 읽으니 이해가 됩니다.", "", []),
    ("반도체곰", "11.27 14:28", "반도체 얘기가 앞에 나온 이유", "오늘 지수를 움직인 업종이라 먼저 다룬 거군요[:mid_explain:]", "", []),
    ("조심조심", "11.27 14:15", "내일 일정도 적혀 있어서 좋습니다", "물가 발표 시각을 따로 찾지 않아도 되네요.", "", []),
    ("데이터센터", "11.27 14:03", "용어 풀이가 도움이 됐습니다", "어려운 말마다 괄호로 풀어 줘서 읽기 쉬웠습니다[:mid_clap:]", "", []),
]
ISSUE_CMTS = [ONE_CMT_I,
    ("장기보유", "11.27 09:03", "단계가 바뀌면 다시 보겠습니다", "아직 확정된 게 없으니 다음 단계로 넘어가는 날을 기다려 봅니다[:mid_hourglass:]", "", []),
    ("새내기", "11.27 08:51", "수습 단계가 세 칸이네요", "지금 어느 칸인지 표시돼 있어서 흐름을 따라가기 쉽습니다.", "", []),
    ("데이터센터", "11.27 08:40", "지난 비슷한 일과 비교가 있네요", "그때는 며칠 걸렸는지 같이 보여 줘서 참고가 됩니다[:mid_proof:]", "", []),
    ("게임좋아", "11.27 08:27", "소식이 많아서 헷갈렸는데", "날짜 순서로 정리돼 있어서 한 번에 읽었습니다[:mid_thanks:]", "", []),
]
FORECAST_CMTS = [ONE_CMT_F,
    ("조심조심", "11.27 10:18", "미리 적어 둔 전망이라 믿음이 갑니다", "급락한 날 적어 두고 그대로 판정하는 방식이 좋네요.", "", []),
    ("새내기", "11.27 10:05", "전망B는 왜 해당 없음인가요?", "두 갈래 중 하나만 판정된다는 뜻인지 궁금합니다[:mid_think:]", "", []),
    ("데이터센터", "11.27 09:52", "급락일 숫자가 바로 보여서 좋습니다", "평소의 몇 배였는지 같이 적혀 있어서 비교가 쉬웠습니다.", "", []),
    ("반도체곰", "11.27 09:40", "다음 전망도 기다리겠습니다", "크게 빠질 때마다 이렇게 정리되면 좋겠네요[:mid_clap:]", "", []),
]
REPORT_TOTAL, STORY_TOTAL, ISSUE_TOTAL, FORECAST_TOTAL = 148, 263, 512, 137   # 목업 댓글 수 = 세 자리
TITLES.update({
    "mock_comments_page-report.html": "댓글 화면 — KOSPI 한 줄 · 홈 카드 하루 그래프 · 댓글 목록 · 쓰기 (한국 증시 리포트에서)",
    "mock_comments_cards.html": "글 아래 댓글 카드 — 2개 이상 = 좌우로 밀기 · 점 · 댓글 더 보기 (종목 페이지)",
    "mock_comments_card-one.html": "글 아래 댓글 카드 — 1개 = 카드 하나 · NEW (시황 글)",
    "mock_comments_page-stock.html": "댓글 화면 — 종목 가격 · 홈 카드 꼴 그래프 · 댓글 목록 · 쓰기 (종목 페이지에서)",
    "mock_comments_page.html": "댓글 화면 — 배너 그림 · 댓글 목록 · 쓰기 (시황 글에서)",
    "mock_comments_page-issue.html": "댓글 화면 — Hot Issue 제목 · 게이지 카드 그대로 · 아래 댓글 (핫이슈에서)",
    "mock_comments_page-forecast.html": "댓글 화면 시안 — 전망 제목 · 전망A · B 카드 (증시 전망에서)",
    "mock_comments_page-article.html": "댓글 화면 시안 — 기사 제목 · 자료 사진 (Newfact 기사에서)",
})
CC_CSS = """<style>
/* 글 아래 댓글 카드 — 흰 상자 · 모서리 12 · 옅은 그림자. 2개 이상이면 좌우로 밀기(옆 카드 끝이 살짝 보임) */
.cc-track{display:flex;gap:10px;margin:14px -16px 0;padding:2px 16px 6px;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none;-webkit-overflow-scrolling:touch;}
.cc-track::-webkit-scrollbar{display:none;}
.cc-card{flex:0 0 calc(100% - 36px);box-sizing:border-box;min-width:0;padding:14px 16px 12px;border:1px solid #E2E8F0;border-radius:12px;background:#fff;box-shadow:0 1px 6px rgba(15,23,42,.06);color:inherit;text-decoration:none;scroll-snap-align:center;-webkit-tap-highlight-color:transparent;}
.cc-one .cc-card{flex-basis:100%;}
.cc-head{display:flex;align-items:center;gap:7px;min-height:24px;}
.cc-head .cm-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:14px;line-height:20px;}
.cc-date{margin-left:auto;flex:none;font-family:var(--num);font-size:12px;line-height:18px;color:#7A7A7A;font-variant-numeric:normal;}
.cc-title{margin:8px 0 0;font-size:16px;line-height:24px;font-weight:700;color:#111;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.cc-new{display:inline-block;margin:0 5px 0 0;padding:0 5px;border-radius:4px;background:#DD0000;color:#fff;font-family:var(--num);font-size:11px;line-height:17px;font-weight:700;vertical-align:2px;}
.cc-text{margin:4px 0 0;font-size:14px;line-height:22px;color:#6B7280;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.cc-foot{display:flex;align-items:center;gap:16px;margin:12px 0 0;font-family:var(--num);font-size:13px;line-height:20px;color:#333;font-variant-numeric:normal;}
.cc-foot span{display:inline-flex;align-items:center;gap:6px;}
.cc-foot svg{width:18px;height:18px;}
.cc-row{display:flex;align-items:center;gap:10px;}
.cc-body{flex:1;min-width:0;}
.cc-stk{flex:none;width:56px;height:56px;margin:6px 0 0;object-fit:contain;}
.cc-dots{display:flex;justify-content:center;gap:6px;margin:10px 0 0;}
.cc-dot{width:6px;height:6px;padding:0;border:0;border-radius:50%;background:#CBD5E1;cursor:pointer;}
.cc-dot.is-on{background:#333;}
/* 점 아래 `댓글 더 보기` = 페이지 이동 버튼 꼴(흰 바탕 · 회색 테두리 · 14/20 굵게) */
.cc-more{display:block;margin:14px 0 0;padding:8px 12px;border:1px solid #B5BAC0;border-radius:8px;background:#fff;font-size:14px;line-height:20px;font-weight:700;color:#111;text-align:center;text-decoration:none;}
/* 댓글 화면 — 종목 그래프 */
.cc-chart{margin:0 0 8px;}
/* 그래프 위 가격 머리 — 코드 · 시장 13 회색 → 이름 19 굵게 → 종가 30 굵게 → 전날 대비 16 증감 색 → 날짜 13 회색 */
.cc-px{margin:0 0 7px;padding-left:6px;font-family:var(--num);color:#111;}
.cc-px-one{font-size:19px;line-height:28px;font-weight:700;font-variant-numeric:tabular-nums;}
.cc-px-one b{font-family:var(--report-font);}
.cc-px-one > span{margin:0 4px;}
.cc-px-one .cc-px-c{font-size:17px;}
.cc-px-one .cc-px-big{font-size:28px;line-height:36px;font-weight:700;}   /* 종목 가격 = 크게 */
.cc-px-one .cc-px-big small{margin-left:1px;font-family:var(--report-font);font-size:19px;font-weight:700;}
.cc-days{display:flex;justify-content:space-between;padding:0 10px 6px;font-family:var(--num);font-size:13px;line-height:19px;color:#6B7280;font-variant-numeric:tabular-nums;}   /* 그래프 안 아래 날짜 = 가장 작은 글씨 */   /* 등락 = 종가보다 2 작게 */
.cc-banner{display:block;width:100%;height:auto;margin:0;border-radius:8px;}   /* 아래 여백은 cc-after-card 20 하나로(11-28) */
.cc-px-sub{font-size:13px;line-height:19px;color:#6B7280;}
.cc-px-name{margin:2px 0 0;font-family:var(--report-font);font-size:19px;line-height:28px;font-weight:700;}
.cc-px-now{margin:2px 0 0;font-size:30px;line-height:38px;font-weight:700;font-variant-numeric:tabular-nums;}
.cc-px-now small{margin-left:2px;font-family:var(--report-font);font-size:19px;font-weight:700;}
.cc-px-chg{font-size:16px;line-height:24px;font-weight:700;font-variant-numeric:tabular-nums;}
.cc-px-day{margin:6px 0 0;font-size:13px;line-height:19px;color:#6B7280;font-variant-numeric:tabular-nums;}
.cc-page .cc-page-h{margin:18px 0 0;padding-left:6px;font-size:16px;line-height:24px;font-weight:700;color:#111;}
</style>"""
CC_JS = """<script>(function(){
[].forEach.call(document.querySelectorAll('[data-cc]'),function(w){var t=w.querySelector('.cc-track'),d=[].slice.call(w.querySelectorAll('.cc-dot'));if(!t||!d.length)return;
var cs=[].slice.call(t.querySelectorAll('.cc-card'));
function cur(){var c=t.scrollLeft+t.clientWidth/2,b=0,bd=1e9;cs.forEach(function(x,i){var m=x.offsetLeft+x.offsetWidth/2-t.offsetLeft,dd=Math.abs(m-c);if(dd<bd){bd=dd;b=i;}});d.forEach(function(x,i){x.classList.toggle('is-on',i===b);});}
t.addEventListener('scroll',function(){clearTimeout(cur.t);cur.t=setTimeout(cur,60);},{passive:true});
function go(i){var c=cs[i];t.scrollTo({left:c.offsetLeft-t.offsetLeft-(t.clientWidth-c.offsetWidth)/2,behavior:'smooth'});}
d.forEach(function(x,i){x.addEventListener('click',function(){go(i);hold();});});cur();
var held=0;function hold(){held=Date.now();}['touchstart','pointerdown','wheel'].forEach(function(e){t.addEventListener(e,hold,{passive:true});});
setInterval(function(){if(document.hidden||Date.now()-held<5000)return;var i=d.findIndex(function(x){return x.classList.contains('is-on');});go((i+1)%cs.length);},3000);});
})();</script>"""


def is_new(when):
    """24시간 안에 쓴 댓글인가 — when = 'MM.DD HH:MM', 목업 지금 = NOW."""
    md, hm = when.split()
    m, d = map(int, md.split("."))
    h, mi = map(int, hm.split(":"))
    mins = (NOW[1] - d) * 1440 + NOW[2] - (h * 60 + mi) if m == NOW[0] else 99999
    return 0 <= mins < 1440


def counts(seed):
    h = sum(ord(ch) * (i + 1) for i, ch in enumerate(seed))
    return 100 + h % 900, 100 + (h // 7) % 900   # 목업 = 세 자리(100~999) — 0 · 한 자리면 화면 파악이 어렵다(11-27 사용자)


def rcount(seed):
    """목업 답글 수 = 세 자리(100~999). 글 화면에 실제로 그린 답글은 몇 개뿐이어도 숫자는 크게."""
    h = sum(ord(ch) * (i + 3) for i, ch in enumerate(seed))
    return 100 + (h // 13) % 900


def card(c, link):
    """카드 한 장 — 이름 줄(그림 · 별명 · 오른쪽 날짜) → NEW + 제목 한 줄 → 글 한 줄 → 좋아요 · 싫어요 · 답글 수. 카드 전체가 글 화면 링크."""
    name, when, title, text, _, replies = c
    up, down = counts(name + title)
    new = '<span class="cc-new">NEW</span>' if is_new(when) else ""
    m = STK_TOKEN.search(text)   # 캐릭터 스티커 = 카드 오른쪽 작은 그림(글 아래 큰 스티커 · 문장 속 스티커 중 첫 것)
    k = EXTRA.get(title, {}).get("stk") or (m and m.group(1))
    pic = f'<img class="cc-stk" src="stickers/c_{k}.webp" alt="" width="56" height="56">' if k else ""
    return (f'<a class="cc-card" href="{link}"><div class="cc-head">{avatar(name)}{name_tag(name).replace("<a ", "<span ").replace("</a>", "</span>")}'
            f'<span class="cc-date">{when}</span></div><div class="cc-row"><div class="cc-body"><div class="cc-title">{new}{esc(title)}</div>'
            f'<p class="cc-text">{esc(STK_TOKEN.sub(" ", text).strip())}</p></div>{pic}</div>'
            f'<div class="cc-foot"><span aria-label="좋아요 {up}">{UP_ICON}{up}</span><span aria-label="싫어요 {down}">{DOWN_ICON}{down}</span>'
            f'<span aria-label="답글 {rcount(name + title)}개">{BUBBLE}{rcount(name + title)}</span></div></a>')


def cards_block(cmts, page_link):
    """글 아래 댓글 칸 — 카드(최신 CARD_N 개, 가려진 글 빼고) + 점(2개 이상) + `댓글 더 보기`."""
    shown = [c for c in cmts if c[4] != "hidden"][:CARD_N]
    one = len(shown) == 1
    dots = "" if one else ('<div class="cc-dots">' + "".join(
        f'<button class="cc-dot" type="button" aria-label="{i + 1}번째 댓글"></button>' for i in range(len(shown))) + "</div>")
    return (f'<div data-cc class="{"cc-one" if one else ""}"><div class="cc-track">'
            + "".join(card(c, "mock_comments_thread.html") for c in shown)
            + f'</div>{dots}<a class="cc-more" href="{page_link}">댓글 더 보기</a></div>')


def price_head(name, sub, bars, dec, won, one=False):
    """그래프 위 가격 머리 — 코드 · 시장(작게) → 이름(굵게) → 그날 종가(크게) → 전날 대비(증감 색 ▲▼) → 날짜 · 종가 기준. 값 = 차트와 같은 일봉의 마지막 두 날."""
    last, prev = bars[-1], bars[-2]
    c, pc = last["close"], prev["close"]
    diff, pct = c - pc, (c - pc) / pc * 100
    up = diff >= 0
    f = lambda v: f"{v:,.{dec}f}"
    y, m, dd = last["day"].split("-")
    chg = (f'<span style="color:{dk.UP if up else dk.DOWN};">{dk.tri_span(up, 16) if diff else ""}{f(abs(diff))} ({abs(pct):.2f}%)</span>')
    if one:   # 종목 = 한 줄 `1,182,000원 ▲97,000 (8.94%)` — 가격만 크게, 이름은 제목 줄에
        chg = chg.replace('<span style=', '<span class="cc-px-c" style=', 1)
        return (f'<div class="cc-px cc-px-one"><span class="cc-px-big" style="margin-left:0;">{f(c)}{"<small>원</small>" if won else ""}</span> {chg}</div>')
    return (f'<div class="cc-px"><div class="cc-px-sub">{esc(sub)}</div><div class="cc-px-name">{esc(name)}</div>'
            f'<div class="cc-px-now">{f(c)}{"<small>원</small>" if won else ""}</div><div class="cc-px-chg">{chg}</div>'
            f'<div class="cc-px-day">{int(m)}.{dd} 종가 기준</div></div>')


STOCK_DAYS = 60   # 종목 댓글 화면 그래프 = 최근 60거래일(약 3개월) 종가 — 종목은 장중 자료를 모으지 않아 하루 그래프 대신 같은 꼴로 일봉


def candle_data(src):
    """종목 일봉 — 이 PC 에 종목 출력(src)이 있으면 그것을 읽고 사본(ref)을 새로 쓴다, 없으면(집 PC 등) git 의 사본을 읽는다."""
    if os.path.exists(src):
        raw = open(src, encoding="utf-8").read()
        d = json.loads(html.unescape(re.search(r'data-candle="([^"]*)"', raw).group(1)))
        os.makedirs(os.path.dirname(STOCK_REF), exist_ok=True)
        with open(STOCK_REF, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
        return d
    print(f"[댓글] 종목 출력 없음 → 일봉 사본 {os.path.relpath(STOCK_REF, HERE)}")
    return json.load(open(STOCK_REF, encoding="utf-8"))


def stock_day(src, sub):
    """종목 댓글 화면 맨 위 = 가격 머리 + 홈 카드 하루 그래프와 같은 꼴(점선 = 비교 기준).
    비교 대상 = 60거래일 전 종가(점선) — 위는 빨강 · 아래는 파랑. 그래프 아래 한 줄로 무엇과 견준 선인지 적는다."""
    d = candle_data(src)
    bars = [dict(zip(("day", "open", "high", "low", "close", "volume"), r)) for r in d["bars"]]
    seg = bars[-STOCK_DAYS - 1:]
    n = len(seg) - 1
    cs = [b["close"] for b in seg[1:]]
    dd = {"prev": seg[0]["close"], "close": cs[-1], "h": max(cs), "l": min(cs),
          "m": [round(k * 390 / (n - 1)) for k in range(n)], "c": cs}
    md = lambda b: "{}.{}".format(int(b["day"][5:7]), b["day"][8:10])
    dates = [md(seg[1]), md(seg[1 + n // 2]), md(seg[-1])]   # 처음 · 가운데 · 끝
    return (price_head(d["name"], sub, bars, d.get("dec", 0), True, one=True) + f'<div class="cc-chart">{day_chart(dd, dec=0, dates=dates)}</div>')


def stock_chart(src, sub, won, one=False):
    """댓글 화면 위 봉차트 — 종목 = 그 종목(000660.html), 시황 = 코스피(리포트 본문). 같은 차트(candle_chart), 자료 = 그 파일의 일봉."""
    import candle_chart as cc
    raw = open(src, encoding="utf-8").read()
    d = json.loads(html.unescape(re.search(r'data-candle="([^"]*)"', raw).group(1)))
    bars = [dict(zip(("day", "open", "high", "low", "close", "volume"), r)) for r in d["bars"]]
    return price_head(d["name"], sub, bars, d.get("dec", 0), won, one) + f'<div class="cc-chart">{cc.card(d["name"], bars, d.get("dec", 0), title="")}</div>' + cc.SCRIPT   # SCRIPT 는 한 번만 돈다(종목 페이지에 이미 있어도 됨)


KOSPI_DAY = os.path.join(HERE, "..", "market-commentary", "static", "sample_cards", "kr-report.json")   # 홈 한국 증시 카드 하루 그래프 예시 자료


def day_chart(d, dec=2, dates=None):
    """홈 증시 카드 `하루 그래프`(테마 fillDayChart)를 같은 셈으로 — 전날 종가 점선 위 빨강 · 아래 파랑 · 최고 · 최저 점.
    오른쪽 위 숫자(등락 · 종가)는 뺀다 — 바로 위 제목 줄이 같은 값을 보여 준다."""
    W, H, T, B, S, UP, DN = 340, 150, 52, 32, 390, "#d93025", "#1a73e8"
    pc = float(d["prev"])
    lo, hi = min(d["c"] + [pc]), max(d["c"] + [pc])
    X = lambda m: min(m, S) / S * W
    Y = lambda v: T + (hi - v) / (hi - lo) * (H - T - B)
    f1 = lambda n: f"{n:.1f}"
    pts = [(X(m), Y(c)) for m, c in zip(d["m"], d["c"])]
    top = min(pts, key=lambda q: q[1]); bot = max(pts, key=lambda q: q[1])
    by, i = Y(pc), "dc-cpage"
    line = " ".join(f"{f1(x)},{f1(y)}" for x, y in pts)
    area = f"M{f1(pts[0][0])},{f1(by)} L" + " L".join(line.split(" ")) + f" L{f1(pts[-1][0])},{f1(by)} Z"
    ns = ' vector-effect="non-scaling-stroke"'
    grid = "".join(f'<line x1="0" x2="{W}" y1="{f1(H * k / 4)}" y2="{f1(H * k / 4)}" stroke="#EEF1F5" stroke-width="1"{ns}/>' for k in (1, 2, 3))
    half = lambda c, clip: (f'<g clip-path="url(#{clip})"><path d="{area}" fill="url(#g{clip})"/>'
                            f'<polyline points="{line}" fill="none" stroke="{c}" stroke-width="1.8" stroke-linejoin="round"{ns}/></g>')
    svg = (f'<svg viewBox="0 0 {W} {H}" aria-hidden="true">{grid}<defs>'
           f'<clipPath id="{i}u"><rect x="0" y="0" width="{W}" height="{f1(by)}"/></clipPath>'
           f'<clipPath id="{i}d"><rect x="0" y="{f1(by)}" width="{W}" height="{f1(H - by)}"/></clipPath>'
           f'<linearGradient id="g{i}u" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{UP}" stop-opacity=".22"/><stop offset="1" stop-color="{UP}" stop-opacity=".02"/></linearGradient>'
           f'<linearGradient id="g{i}d" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{DN}" stop-opacity=".22"/><stop offset="1" stop-color="{DN}" stop-opacity=".02"/></linearGradient></defs>'
           + half(UP, i + "u") + half(DN, i + "d")
           + f'<line x1="0" x2="{W}" y1="{f1(by)}" y2="{f1(by)}" stroke="#9CA3AF" stroke-width="1" stroke-dasharray="2 3"{ns}/>'
           f'<circle cx="{f1(top[0])}" cy="{f1(top[1])}" r="3" fill="#fff" stroke="{UP}" stroke-width="1.5"{ns}/>'
           f'<circle cx="{f1(bot[0])}" cy="{f1(bot[1])}" r="3" fill="#fff" stroke="{DN}" stroke-width="1.5"{ns}/></svg>')

    def mark(q, kind, col, val):
        x, y = q[0] / W * 100, q[1] / H * 100
        ty = "calc(-100% - 5px)" if kind == "최고" else "5px"
        if x < 20:
            hx, tx = "left:10px;", "0"
        elif x > 80:
            hx, tx = "right:10px;", "0"
        else:
            hx, tx = f"left:{f1(x)}%;", "-50%"
        return (f'<span class="day-mark" style="{hx}top:{f1(y)}%;transform:translate({tx},{ty});color:{col};">'
                f'<span class="k">{kind}</span> {float(val):,.{dec}f}</span>')
    body = svg + mark(top, "최고", UP, d["h"]) + mark(bot, "최저", DN, d["l"])
    if not dates:
        return f'<div class="day-chart" role="img" aria-label="KOSPI 하루 그래프">{body}</div>'
    # 날짜 줄 = 그래프 상자 안 맨 아래(가장 작은 글씨 13/19) — 그림 칸(최고 · 최저 자리)은 그대로 두고 그 밑에 붙인다
    row = "".join(f"<span>{t}</span>" for t in dates)
    return (f'<div class="day-chart" role="img" aria-label="최근 3개월 종가 그래프"><div style="position:relative;">{body}</div>'
            f'<div class="cc-days">{row}</div></div>')


def report_top():
    """리포트 댓글 화면 맨 위 = `KOSPI 종가 ▲등락 (%)` 한 줄 + 홈 카드 하루 그래프. 값은 둘 다 같은 하루 자료(전날 종가 · 종가)."""
    d = json.load(open(KOSPI_DAY, encoding="utf-8"))["intraday"]
    c, pc = float(d["close"]), float(d["prev"])
    diff = c - pc
    up = diff >= 0
    chg = (f'<span class="cc-px-c" style="color:{dk.UP if up else dk.DOWN};">{dk.tri_span(up, 14) if diff else ""}'
           f'{abs(diff):,.2f} ({abs(diff) / pc * 100:.2f}%)</span>')
    return f'<div class="cc-px cc-px-one"><b>KOSPI</b> <span>{c:,.2f}</span> {chg}</div><div class="cc-chart">{day_chart(d)}</div>'


def _chg(v):
    up = v >= 0
    return f'<span style="color:{dk.UP if up else dk.DOWN};">{dk.tri_span(up, 14)}{abs(v):.1f}%</span>'


PTITLE = '<h2 style="margin:4px 0 12px;padding:0 0 0 6px;font-size:22px;line-height:30px;font-weight:700;color:#111;word-break:keep-all;">{}</h2>'   # 긴 글 제목 = 제목 줄이 아니라 본문 맨 위(원래 글과 같게, 11-27 사용자)


def issue_top():
    """시안 — 핫이슈 댓글 화면 맨 위 = 이슈 제목 → `주가도 같은 쪽인가?` 한 줄(그 종목 vs 비교 지수, 헌법 제1조 대조군) + 작은 회색 기준."""
    return (PTITLE.format("젠슨 황 사임, 엔비디아는 수습되나?")
            + f'<div class="cc-px cc-px-one">엔비디아 {_chg(-12.7)} <span style="color:#D1D5DB;">·</span> 반도체 지수 {_chg(8.1)}</div>'
            '<div class="cc-px cc-px-sub">사건 뒤 전체 · 11.06 → 11.13 · 미국 11.13 종가 기준</div>')


def forecast_top():
    """시안 — 증시 전망 댓글 화면 맨 위 = 전망 제목 → 전망A · 전망B 카드(전망 페이지 갈래 카드를 줄인 판: 연한 주황 상자 · 전망 꼬리표 · 갈래 이름 · 오른쪽 판정, 접기 · 세부 줄 없음).
    판정이 난 갈래 = 빨강 꼬리표 + 빨강 판정, 해당 없는 갈래 = 회색(원래 글과 같은 흐림)."""
    def card(lab, name, verdict, on):
        tag = (f'<span style="flex:none;display:inline-flex;align-items:center;padding:3px 7px 2px;border-radius:4px;font-size:13px;line-height:17px;font-weight:700;white-space:nowrap;'
               + ('background:#FDE8E8;border:1px solid #F6CACA;color:#B91C1C;' if on else 'background:#F3F5F8;border:1px solid #E9ECF0;color:#9CA3AF;') + f'">{lab}</span>')
        return (f'<div style="display:flex;align-items:center;gap:8px;margin:0 0 6px;padding:11px 12px;background:#FFF7EE;border:1px solid #FEE6CA;border-radius:10px;">{tag}'
                f'<span style="flex:1 1 auto;min-width:0;font-size:16px;line-height:24px;font-weight:500;color:{"#111" if on else "#9CA3AF"};word-break:keep-all;">{name}</span>'
                f'<span style="flex:none;font-size:16px;line-height:24px;font-weight:700;color:{"#d93025" if on else "#9CA3AF"};white-space:nowrap;">{verdict}</span></div>')
    return (PTITLE.format("엔비디아 실적 뒤 반도체는?")
            + card("전망A", "예상을 크게 넘으면", "실현됨", True) + card("전망B", "예상을 크게 넘지 못하면", "해당 없음", False)
            + '<div class="cc-px cc-px-sub" style="margin-top:2px;">결과 11.17</div>')


PAGE_CSS = """<style>
/* 댓글 보기 화면 공통 기준(11-28) = Newfact 기사 댓글 보기에서 다듬은 값. 종목 · 리포트 · 시황 · Hot Issue · 증시 전망 · 기사 모두 같다 */
.cc-page .cc-page-h{margin-top:4px;}                     /* `댓글 n` 위 18 → 9 → 4 */
.cc-page .cc-page-h .cc-n{font-weight:400;}              /* 숫자는 굵게 빼기 */
.cc-page .cv-guard{margin:5px 0 9px !important;background:none !important;border:1px solid #E2E8F0 !important;}   /* 위 14 → 7 → 5 · 아래(첫 댓글까지) 14 → 9 · 회색 면 빼고 회색 외곽선만 */
.cc-page .cv-list .cv-main .cv-title{margin-top:1px;}    /* 이름 줄 ~ 제목 4 → 3 → 1 */
.cc-page .cv-list .cv-main .cv-text{margin-top:4px;line-height:24px;color:#454C55;}   /* 제목 아래 6 → 4 · 행간 26 → 25 → 24(16px 글자 = 짝수 행간, 11-28) · 글자 #6B7280 → #606773 → #565D68 → #4D545E → #454C55(10%씩 네 번 진하게) */
.cc-page [data-cmore]{margin:8px 0 0;}
.cc-page [data-cmore].is-open .acc-chev{transform:rotate(180deg);}
/* 종목 댓글 보기 맨 위(11-28) — 가격 28 → 26 */
.cc-px-one .cc-px-big{font-size:26px;line-height:34px;}
/* `댓글 n` 바로 위가 외곽선 있는 카드 · 그래프 · 배너 그림인 화면(종목 · 리포트 · Hot Issue · 증시 전망 · 시황) = 위 끝 ~ `댓글 n` 20 (11-28, 시황 11-28).
   기사(사진)만 예외 = 공통값 4. 위 카드의 아래 여백은 0 으로 두고 이 20 하나로 잰다 */
.cc-page.cc-after-card{margin-top:0;}
.cc-page.cc-after-card .cc-page-h{margin-top:20px;}
</style>"""
# 더 보기 = 디자인 키트 more_list 규칙(처음 5 · 누를 때마다 10 · 흰 버튼 FOLD_BTN 전체 폭 + 아래 화살표 · 다 펼치면 `접기`).
# 목업은 아래 10개를 돌려 붙여 214까지 늘린다(실서비스 = 다음 10개를 서버에서 받음).
ARTICLE_MORE = [
    ("주린이탈출", "11.27 10:02", "매개변수 300억개면 큰 편인가요?", "다른 회사 모델과 비교한 표가 있으면 좋겠습니다[:mid_question:]", "", []),
    ("데이터센터", "11.27 09:55", "추론 비용을 줄였다는 부분", "비용 효율을 개선했다고 하는데 얼마나 줄었는지 숫자가 궁금하네요.", "", []),
    ("장투러", "11.27 09:41", "프리뷰 때보다 점수가 올랐네요", "프리뷰 대비 5.9점 상승이라고 적혀 있네요. 다음 버전도 비교해 보겠습니다.", "", []),
    ("오늘도출근", "11.27 09:30", "게임 말고 어디에 쓰일까요", "기사에는 쓰임새가 자세히 안 나와서 다음 소식을 기다려 봅니다.", "", []),
    ("차트보는곰", "11.27 09:12", "출시일이 25일이었군요", "주말 사이 나온 소식이라 놓쳤는데 정리돼 있어서 좋네요[:mid_thanks:]", "", []),
    ("새벽시장", "11.27 08:58", "다른 게임사도 비슷한가요?", "국내 게임사 중 자체 언어모델을 만든 곳이 또 있는지 궁금합니다.", "", []),
    ("천천히", "11.27 08:40", "용어 설명 고맙습니다", "활성화 매개변수라는 말을 처음 알았습니다.", "", []),
    ("숫자확인", "11.27 08:21", "평가 점수가 세 가지네요", "점수마다 무엇을 재는 건지 알면 더 이해가 쉬울 것 같아요.", "", []),
    ("퇴근길", "11.27 08:05", "기사 짧고 좋네요", "핵심만 있어서 출근길에 읽기 편했습니다.", "", []),
    ("관찰중", "11.27 07:48", "다음 분기 실적에서 확인", "개발비가 얼마나 들었는지는 실적 발표 때 보겠습니다[:mid_hourglass:]", "", []),
]


def page_more(pool, shown, total):
    rows = "".join(item(c, True, f"m{k}", "mock_comments_thread.html") for k, c in enumerate(pool))
    n = min(dk.MORE_STEP, total - shown)
    return (f'<template id="cc-more-tpl">{rows}</template>'
            f'<button type="button" data-cmore data-total="{total}" data-shown="{shown}" style="{dk.FOLD_BTN}width:100%;">'
            f'<span>댓글 {n}개 더 보기</span> {dk.ACC_CHEV}</button>'
            "<script>(function(){var b=document.querySelector('.cc-page [data-cmore]');if(!b)return;"
            "var list=document.querySelector('.cc-page .cv-list'),tpl=document.getElementById('cc-more-tpl'),total=+b.dataset.total,first=+b.dataset.shown,shown=first,step=10;"
            "function label(){var r=total-shown;b.querySelector('span').textContent=r>0?'댓글 '+Math.min(step,r)+'개 더 보기':'접기';b.classList.toggle('is-open',r<=0);}"
            "b.addEventListener('click',function(){if(shown>=total){list.querySelectorAll('.cc-add').forEach(function(x){x.remove();});shown=first;label();b.scrollIntoView({block:'center'});return;}"
            "var src=tpl.content.querySelectorAll('li.cv-item'),n=Math.min(step,total-shown);for(var i=0;i<n;i++){var li=src[(shown-first+i)%src.length].cloneNode(true);li.classList.add('cc-add');list.appendChild(li);}"
            "shown+=n;label();});})();</script>")


def article_top():
    """Newfact 기사 댓글 화면 맨 위 = 원래 기사 제목(문장 그대로, 기사와 같은 26/38 굵게) → 그 기사의 자료 사진 + 출처 줄.
    사진 = 뉴스 글 목업 `사진 5`(최신 기사 · 확정 규칙)와 같은 값: 높이 200 · 모서리 10 · 회사 기사인데 회사 사진 없음 = 업종 사진 + 오른쪽 아래 흰 이름표(로고 24 + 이름 14 굵게, 높이 32)
    · 출처 줄 = `자료 사진 · 사진가 · 이용 조건` 11/16 연회색 오른쪽 정렬, 링크 밑줄 없음."""
    tag = ('<span style="position:absolute;right:12px;bottom:12px;display:flex;align-items:center;height:32px;padding:0 12px 0 4px;border-radius:16px;background:#fff;'
           'font-size:14px;line-height:20px;font-weight:700;color:#111;"><img src="https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/images/logos/KR_259960.svg?v=2" '
           'alt="" width="24" height="24" loading="lazy" style="display:inline-block;width:24px;height:24px;border-radius:50%;flex:none;margin-right:6px;background:#fff;'
           'object-fit:cover;outline:1px solid #E2E8F0;outline-offset:-1px;">크래프톤</span>')
    return ('<h2 style="margin:4px 0 12px;padding:0 0 0 6px;font-size:26px;line-height:38px;font-weight:700;color:#111;word-break:keep-all;">'   # 기사 제목 = 원래 기사(data-headline)와 같은 26/38(폰은 테마가 22로)
              '<span style="display:block;font-size:26px;line-height:38px;">크래프톤, 자체 개발 거대언어모델 정식 출시</span></h2>'
            + '<figure style="margin:0 0 4px;"><div style="position:relative;"><img src="../../news-posts/output/mock_img/industry_game.jpg" alt="자료 사진: e스포츠 대회장" '
            f'style="display:block;width:100%;height:200px;object-fit:cover;border-radius:10px;">{tag}</div>'
            '<figcaption style="margin:6px 0 0;font-size:11px;line-height:16px;color:#9CA3AF;text-align:right;">자료 사진 · '
            '<a href="https://commons.wikimedia.org/wiki/File:Iskandar_Investment_Esports_Carnival_2019.jpg" style="color:inherit;text-decoration:none;">Chongkian</a> · '
            '<a href="https://creativecommons.org/licenses/by-sa/4.0/deed.ko" style="color:inherit;text-decoration:none;">CC BY-SA 4.0</a></figcaption></figure>')


TAIL = """<script>(function(){function set(){var l=document.querySelector('.post-title-label')||document.querySelector('.post-title');if(!l||l.querySelector('.post-title-sub'))return;var t=document.createElement('span');t.className='post-title-sub';t.style.cssText='position:relative;top:1px;';t.textContent='댓글 보기';l.appendChild(t);}
window.addEventListener('load',function(){setTimeout(set,300);});})();</script>"""   # 댓글 화면 제목 줄 끝 = 작은 회색 `댓글 보기`(종목 제목 꼬리와 같은 .post-title-sub, 11-27 사용자 B안 + 문구). 글자 획 가운데가 제목보다 0.6px 위 → 1px 내림(11-28)


def top(kind):
    """댓글 화면 맨 위 — 종목 = 가격 머리 + 그 종목 봉차트 · 리포트 = 코스피 한 줄 + 봉차트 · 시황 = 그 글의 배너 그림."""
    if kind == "stock":
        return stock_day(STOCK_REAL, "000660 코스피")
    if kind == "report":
        return report_top()
    if kind == "issue":
        return issue_top()
    if kind == "forecast":
        return forecast_top()
    if kind == "article":
        return article_top()
    # 제목 줄(.pr-sticky) 바로 아래가 배너 그림 = 제목 줄 구분선을 뺀다(시황 글 story_render 와 같은 규칙, 11-28). 여백 14 는 둔다(배너가 둥근 카드 꼴)
    return ('<style>body:has(.cc-banner) .pr-sticky{border-bottom:0;}</style>'
            f'<img class="cc-banner" src="{STORY_BANNER}" alt="AI 생성 이미지" width="900" height="374">')


ISSUE_BASE = os.path.join(HERE, "..", "issue_store", "output", "mock_issue_nvidia_ceo_public.html")   # Hot Issue 원래 페이지(목업)


def issue_head():
    """Hot Issue 댓글 화면 맨 위 = 원래 Hot Issue 페이지 본문 맨 위를 그대로 — 제목 블록(h2 · 게시 날짜) → 흰 게이지 카드(`최근 일주일 뉴스는 어느 쪽?`)까지.
    그 아래(`주가도 같은 쪽인가?` · 사태 진행 상황 · 관련 뉴스 …)는 잘라 내고 댓글이 이어진다(11-28 사용자). 돌아가기는 댓글 화면 쪽 표시를 쓰므로 원래 것은 뺀다."""
    p = open(ISSUE_BASE, encoding="utf-8").read()
    op = '<div class="post-body entry-content">'
    a = p.index(op) + len(op)
    b = p[a:p.index('<div class="post-share-buttons', a)]
    cut = b.rindex('<div style="margin:0 0 8px;">', 0, b.index('>주가도 같은 '))   # 흰 게이지 카드(`최근 일주일 뉴스는 어느 쪽?`)까지만 — 주가 · 사태 진행 강조 카드부터 잘라 냄(11-28 사용자)
    head = re.sub(r'\sdata-title-back(-label)?="[^"]*"', "", b[:cut])
    return head + "</div>"   # 맨 바깥 data-head-title 상자 닫기


FORECAST_BASE = os.path.join(HERE, "..", "issue_store", "output", "mock_forecast_fix.html")   # 증시 전망 페이지(최신 꼴, 목업 · git 밖)
FORECAST_PAGE = "S&amp;P 500 급락, 반등할까 더 빠질까? (끝남 · 맞음"   # 그 안의 전망 한 편 — 급락일 · 전망A 반등한다 · 전망B 지속한다


def _div_end(t, i):
    """t[i] 에서 여는 <div 의 짝 닫는 </div> 끝 위치."""
    depth, k = 0, i
    for m in re.finditer(r"<div\b|</div>", t[i:]):
        depth += 1 if m.group(0) != "</div>" else -1
        if depth == 0:
            return i + m.end()
    return len(t)


def forecast_head():
    """증시 전망 댓글 화면 맨 위 = 증시 전망 보기 페이지와 같은 꼴(11-28 사용자) — 제목(아이콘) · 급락일 줄 · 전망A · 전망B 카드까지.
    카드는 펼치지 않는다: 오른쪽 펼치기 버튼과 펼쳐야 보이는 안쪽(단계 · 관련 주식 정보 · 뉴스 · 신호)을 빼고 머리 줄만. 그 아래(Timeline …)는 잘라 내고 댓글."""
    t = open(FORECAST_BASE, encoding="utf-8").read()
    m = re.search(r'border-top:2px solid #111;[^"]*">' + re.escape(FORECAST_PAGE) + r'[^<]*, 바꾼 뒤</div>', t)   # 괄호 안 꼬리(· 기록 뚜렷 등)가 바뀌어도 찾게(11-28)
    a = t.index("</div>", m.end()) + 6   # 라벨 아래 설명 줄 건너뜀
    e = t.find('border-top:2px solid #111;', a)
    g = t[a:e if e > 0 else t.index('<div class="post-share-buttons', a)]   # 다음 편 라벨 또는 페이지 끝까지
    c = g.rindex('<div style="margin:0 0 24px;">', 0, g.index(">전망A<"))   # 전망 카드 묶음
    head = g[:_div_end(g, c)]
    head = re.sub(r"(<summary\b[^>]*>.*?</summary>).*?</details>", r"\1</details>", head, flags=re.S)   # 펼친 안쪽 빼기
    head = re.sub(r'<span style="display:inline-flex;flex:none;align-items:center;justify-content:center;width:31px;height:31px;[^"]*">.*?</span>', "", head, flags=re.S)   # 펼치기 버튼 빼기
    head = head.replace("<summary ", '<summary onclick="return false;" ').replace("cursor:pointer;", "cursor:default;")
    head = re.sub(r'\sdata-title-back(-label)?="[^"]*"', "", head)
    return head + "</div>"   # 맨 바깥 data-head-title 상자 닫기


CARD_TOP = {"stock", "report", "issue", "forecast", "story"}   # 맨 위가 외곽선 카드 · 그래프 · 배너 그림인 댓글 보기(시황 11-28 추가)


def comment_page(cmts, total, back, kind):
    """댓글 화면 본문 — 봉차트(종목 = 그 종목, 시황 = 코스피) → `댓글 n` → 안내 → 목록 → 더 보기. 쓰기 = 오른쪽 아래 연필.
    제목 줄은 따로 그리지 않는다 — 글의 h3.post-title 을 테마가 고정 제목 줄(뒤로 · 로고 + 제목 · 공유)로 만든다(디자인 가이드 2절 1)."""
    rows = "".join(item(c, True, f"t{k}", "mock_comments_thread.html") for k, c in enumerate(cmts))
    more = page_more(ARTICLE_MORE if kind == "article" else cmts, len(cmts), total) if total > len(cmts) else ""   # 더 보기 규칙(10개씩 · 화살표 흰 버튼)
    mark = (f'<span data-title-back="{back}" data-title-back-label="돌아가기" hidden></span>'
            + ('<span data-kr-code="000660" hidden></span>' if kind == "stock" else ""))
    heads = {"issue": (ISSUE_BASE, issue_head), "forecast": (FORECAST_BASE, forecast_head)}   # 원래 페이지 머리 그대로(틀은 git 에 없음 — 없는 PC 는 아래 예전 시안으로)
    if kind in heads and os.path.exists(heads[kind][0]):
        return (heads[kind][1]() + f'<div data-design="2" style="font-family:var(--report-font);">{mark}{TAIL}'
                f'{PAGE_CSS}<div class="comments is-open cc-page{" cc-after-card" if kind in CARD_TOP else ""}"><div class="cc-page-h">댓글 <span class="cc-n">{total}</span></div>{guard()}<ol class="cv-list">{rows}</ol>{more}</div></div>')
    return (f'<div data-design="2" style="font-family:var(--report-font);">{mark}{TAIL}{top(kind)}'
            f'{PAGE_CSS}<div class="comments is-open cc-page{" cc-after-card" if kind in CARD_TOP else ""}"><div class="cc-page-h">댓글 <span class="cc-n">{total}</span></div>{guard()}<ol class="cv-list">{rows}</ol>{more}</div></div>')


def build_cc(name, base, cmts, total, page_link="", page=None):
    """page=None → 글 끝에 카드 칸 · page=(제목, 돌아갈 곳, 종목?) → 그 글 틀에 본문만 댓글 화면으로 바꾼 새 페이지."""
    if not os.path.exists(base):   # 종목 페이지 틀(kr-stocks/output)이 없는 PC = 시황 글 틀로(제목 줄 로고만 빠진다)
        print(f"[댓글] {os.path.basename(base)} 없음 → 시황 글 틀로 그림")
        base = BASE
    p = open(base, encoding="utf-8").read()
    js = JS.replace("__NICK_A__", json.dumps(NICK_A, ensure_ascii=False)).replace("__NICK_B__", json.dumps(NICK_B, ensure_ascii=False)).replace("__RLEFT__", str(REACT_LEFT)).replace("__STK_MAX__", str(STK_MAX))
    if page:
        title, back, kind = page
        p = re.sub(r'(<h3 class="post-title">)[^<]*(</h3>)', lambda m: m.group(1) + esc(title) + m.group(2), p, count=1)
        op = '<div class="post-body entry-content">'
        a = p.index(op) + len(op)
        e = p.index('</div><div class="post-share-buttons', a)
        p = p[:a] + CSS + CC_CSS + comment_page(cmts, total, back, kind) + p[e:]
        fab = f'<button class="cv-fab" type="button" aria-label="댓글 쓰기">{PENCIL}</button>'
        p = p.replace("</body>", fab + windows(True, False) + js + "</body>", 1)
    else:
        nav = '<p class="post-nav">'
        i = p.index(nav) + len(nav)
        p = (p[:i] + f'<a class="post-nav-cm has-cm" href="{page_link}" style="text-decoration:none;" aria-label="댓글 {total}개 · 댓글 화면으로">{BUBBLE}'   # 버튼 줄 `댓글 n` = 댓글 화면으로
             f'<span class="cm-label">댓글 {total}</span></a>' + p[i:])
        end = p.index("</p>", i) + 4
        sec = f'<section class="comments is-foldable is-open" id="comments-mock"><div class="comments-panel">{cards_block(cmts, page_link)}</div></section>'
        p = p[:end] + CSS + CC_CSS + sec + p[end:]
        p = p.replace("</body>", windows(True, False) + js + CC_JS + "</body>", 1)
    p = re.sub(r"<title>[^<]*</title>", f"<title>{TITLES[name]} — 목업</title>", p, count=1)
    write_out(name, p)


def chars_page():
    """캐릭터 소개 페이지 — 맨 위 한 문단 → 캐릭터마다 그림 · 이름 + 왕관 · 동물 · 보는 칸 · 소개 · 쓴 글 → 회색 문장. 댓글의 이름 · 왕관이 #이름 으로 온다."""
    where = {"11.18 증시 시황": "mock_comments_member.html", "11.27 SK하이닉스": "mock_comments_page-stock.html"}
    secs = ""
    for name, ava, animal, sees, intro, _ in CHARS:
        posts = "".join(f'<a class="cv-ch-post" href="{where.get(w, "mock_comments_thread.html")}"><small>{esc(w)}</small><b>{esc(t)}</b></a>'
                        for w, t in CHAR_POSTS.get(name, []))
        secs += (f'<section class="cv-ch" id="{name}"><div class="cv-prof"><div class="cv-big-av"><img src="{ava_src(ava)}" alt="" width="56" height="56"></div>'
                 f'<div class="cv-ch-name"><b>{esc(name)}{CROWN_BIG}</b><small>{esc(animal)}</small></div></div>'
                 f'<p><span class="cv-ch-sees">보는 것 · {esc(sees)}</span><br>{esc(intro)}</p>'
                 f'<div class="cv-ch-h">쓴 글</div>{posts}</section>')
    mark = '<span data-title-back="mock_comments_member.html" data-title-back-label="돌아가기" hidden></span>'
    return (f'<div data-design="2" style="font-family:var(--report-font);">{mark}'
            f'<p class="cv-ch-top">댓글에서 이름 옆에 {CROWN_IN} 왕관이 붙은 열 명은 Newfact 캐릭터예요. '
            '저마다 보는 칸이 하나씩 있고, Newfact 가 모은 자료의 숫자만 가지고 AI 로 글을 써요. 사고팔라는 말은 하지 않아요. 판단은 읽는 분의 몫이에요.</p>'
            f'<div class="comments is-open cc-page">{secs}</div>'
            + dk.excl_note("캐릭터 글은 회원이 신고할 수 있고, 신고가 3번 쌓이면 다른 글과 똑같이 가려집니다.", margin="14px 0 0") + '</div>')


def build_chars(name):
    p = open(BASE, encoding="utf-8").read()
    p = re.sub(r'(<h3 class="post-title">)[^<]*(</h3>)', lambda m: m.group(1) + "Newfact 캐릭터" + m.group(2), p, count=1)
    op = '<div class="post-body entry-content">'
    a = p.index(op) + len(op)
    e = p.index('</div><div class="post-share-buttons', a)
    p = p[:a] + CSS + CC_CSS + chars_page() + p[e:]
    p = re.sub(r"<title>[^<]*</title>", f"<title>{TITLES[name]} — 목업</title>", p, count=1)
    write_out(name, p)


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
    build_chars("mock_comments_characters.html")
    build_cc("mock_comments_cards.html", STOCK_BASE, STOCK_CMTS, STOCK_TOTAL, "mock_comments_page-stock.html")
    build_cc("mock_comments_card-one.html", BASE, [ONE_CMT], 1, "mock_comments_page.html")
    build_cc("mock_comments_page-stock.html", STOCK_BASE, STOCK_CMTS, STOCK_TOTAL, "mock_comments_page-stock.html",
             page=("SK하이닉스", "mock_comments_cards.html", "stock"))
    build_cc("mock_comments_page-report.html", BASE, REPORT_CMTS, REPORT_TOTAL, "mock_comments_page-report.html",
             page=("11.27 한국 증시 리포트", "../../kr-market-report/output/kr_report_mock.html", "report"))
    build_cc("mock_comments_page.html", BASE, STORY_CMTS, STORY_TOTAL, "mock_comments_page.html",
             page=("11.27 증시 시황", "mock_comments_card-one.html", "story"))
    build_cc("mock_comments_page-issue.html", ISSUE_BASE, ISSUE_CMTS, ISSUE_TOTAL, "mock_comments_page-issue.html",
             page=("Hot Issue", "../../issue_store/output/mock_issue_nvidia_ceo_public.html", "issue"))
    build_cc("mock_comments_page-forecast.html", BASE, FORECAST_CMTS, FORECAST_TOTAL, "mock_comments_page-forecast.html",
             page=("증시 전망", "../../issue_store/output/mock_real_forecast-nvda-2026q3.html", "forecast"))
    build_cc("mock_comments_page-article.html", BASE, ARTICLE_CMTS, ARTICLE_TOTAL, "mock_comments_page-article.html",
             page=("Newfact 기사", "../../news-posts/output/mock_news_photo_5.html", "article"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
