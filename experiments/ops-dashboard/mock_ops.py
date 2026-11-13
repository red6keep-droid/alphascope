"""운영 대시보드 목업 (2026-11-13 사용자: "관리에 필요한 모든 것을 추천해" → 1단계 범위, "디자인 규칙을 꼭 지켜서").

    python experiments/ops-dashboard/mock_ops.py   → output/mock_ops.html (목업 서버 `운영 대시보드` 묶음)

실제 화면은 관리자 전용 Worker(infra/ops-console)에 둔다. 가이드라인 14절 `운영 현황 페이지`: 블로그 테마를 불러오지 않으므로
Worker CSS 를 블로그 값과 같게 맞춘다 — 그래서 목업은 다른 목업과 똑같이 공용 부품(design_kit · daily-report/cards · tech_signals)으로 그린다.

1단계 = 지금 있는 기록(ops_log → KV) · GitHub API(gh-pages · 상태 브랜치 · Actions)만으로 그릴 수 있는 칸.
  탭: 요약 · 화면 · 발행 · 수집 · AI · 기록 · 전망
2단계(독자 · 검색 · 댓글 · 만료 달력)와 3단계(글 품질 검사)는 이 목업에 없다.
모든 숫자는 예시 값이다(인터넷 · AI 0).
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import design_kit as dk  # noqa: E402
import tech_signals as TS  # noqa: E402

_spec = importlib.util.spec_from_file_location("daily_cards", os.path.join(HERE, "..", "daily-report", "cards.py"))
QC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(QC)

OUT = os.path.join(HERE, "output")
NAME = "운영 대시보드"
NOW = "11월 13일 09:40"
OPS_COLOR = "#334155"   # 강조형 아이콘 색 = 이 기능 하나의 색 (가이드라인 8절 아이콘) — 운영 = 진한 회색, 홈 카드 색과 겹치지 않게

esc = dk.esc
V = dk.violet


# ---------------------------------------------------------------- 상태 표시 (같은 뜻 = 같은 모양, 가이드라인 1-3 · 8절)
def ok(text="정상"):
    return dk.pill(text, "good", bare=True)          # 녹색 외곽선 라벨 = 정상 (dk.PILL good)


def warn(text="확인필요"):
    return dk.pill(text, "uncertain", bare=True)     # 주황 외곽선 라벨 = 손이 필요한 것


def idle(text="건너뜀"):
    return dk.pill(text, "neutral", bare=True)       # 회색 = 예정대로 쉬었음


def over(html_text):
    """임계를 넘은 값 = 경고 주황 굵게 (가이드라인 4절 `경고는 주황 WARN — 임계를 넘은 값`)."""
    return f'<span style="color:{dk.WARN};font-weight:700;">{html_text}</span>'


def p(text):
    return f'<p style="font-size:{dk.BODY};line-height:{dk.LH_BODY};color:#333;margin:0 0 12px;word-break:keep-all;">{esc(text)}</p>'


def white_card(rows, fold_at=None, noun="", left=60):
    """이름 · 값 카드(표 대신, 7-4). rows = [(이름, 값HTML, 보조 줄)]. 4개 이상이면 앞 2줄 + 더 보기(7-5).
    left = 카드별 예외 비율(7-4 `ccard(rows, left=n)`) — 값이 라벨 · `64개 중 64개` 라 80/20 이면 넘친다."""
    return dk.ccard([(esc(n), v, s) for n, v, s in rows], fold_at=fold_at, noun=noun, left=left)


def chart_top(html, top=15):
    """카드 밖 그래프 제목(※) 위 +15 (2026-11-13 사용자). 탭 · 서브탭 바로 아래 그래프는 top=0.
    div 로 감싼다 — 그래프 조각(span display:block)이 서브탭의 hidden 을 이겨 다른 서브탭에도 보이던 것."""
    return f'<div style="margin-top:{top}px;">{html}</div>'


def head_row():
    """맨 위 질문 줄 — 강조형 아이콘(색 면 네모 24 · 글자와 8) + 상태 한 마디, 한 화면에 강조형은 이 자리 하나 (8절 아이콘)."""
    return (f'<div style="display:flex;align-items:center;gap:8px;margin:0 0 12px;padding-left:{dk.ALIGN_PX}px;">'
            f'{dk.solid_icon("pulse", OPS_COLOR)}'
            f'<span style="font-size:{dk.H2_SIZE};line-height:{dk.LH_H2};font-weight:700;color:#111;">블로그는 잘 돌고 있나?</span></div>')


# ---------------------------------------------------------------- 요약 (머리 + 첫 탭)
def summary_tab():
    lead = (f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">{NOW} 기준으로 손이 필요한 곳 '
            f'{V("2곳")}, 지켜볼 곳 {V("3곳")}이 있습니다.</p>')
    areas = [
        ("독자 화면", warn(), "한국 홈 시세 6시간째 그대로 · 테마 붙여넣기 대기"),
        ("수집", warn(), "CNN 공포탐욕 3일째 실패"),
        ("AI 한도", f'{V("85%")}', "Gemini flash 하루 20회 중 17회"),
        ("발행", ok(), "오늘 예정 9개 중 9개 끝남"),
        ("기록", ok(), "상태 브랜치 9개 오늘 저장"),
        ("증시 전망", f'{V("D−1")}', "11.14 판정일 1건"),
    ]
    status = white_card(areas)   # 판단 근거 카드는 접지 않는다 (7-5)
    todo = [
        ("테마 붙여넣기", warn("대기"), "저장소가 블로그보다 6커밋 앞섬 · 11.11부터"),
        ("Firestore 규칙 게시", warn("대기"), "게시 전에는 댓글 저장이 모두 거절됨"),
        ("증시 전망 판정 확인", f'<span style="color:{dk.VIOLET};font-weight:700;">11.14</span>', "물가 발표 뒤 S&P 500 은?"),
        ("테스트 중 라벨 떼기", f'{V("D+24")}', "인물 발언 · 2~4주 기간 끝남"),
    ]
    return (dk.cards(lead + head_row() + status)
            + dk.h2("요약", tab="요약")
            + dk.sub_label("내가 할 일")
            + white_card(todo, fold_at=2, noun="할 일")
            + dk.guide("목업", "모든 숫자는 예시 값입니다. 실제 화면은 관리자 전용 운영 페이지에 둡니다."))


# ---------------------------------------------------------------- 화면 — 독자가 보는 화면이 최신인가
def screen_tab():
    fresh = QC.question_card(
        "독자 화면은 최신인가?", "1곳 늦음", "neutral", "#111", [
            ("한국 홈 시세가 오전 3시 40분 뒤로 바뀌지 않았습니다. 같은 시각 한국 종목 실행은 성공으로 끝나, 올린 파일이 비어 있었는지 봐야 합니다.", "plain"),
            ("row", "한국 홈 시세", over("6시간째"), "기준 : 평일 4시간 안에 바뀜"),
            ("row", "미국 홈 시세", "1시간 전", "기준 : 장 마감 뒤 하루 5번"),
            ("row", "홈 뉴스", "2시간 전", "기준 : 하루 2번"),
            ("row", "홈 카드 재료", "3시간 전", "미국 증시 · 한국 증시 · 인물 발언 카드"),
        ], opened=True)
    theme = QC.question_card(
        "블로그 테마가 저장소와 같은가?", "6커밋 뒤", "neutral", "#111", [
            ("블로그에 붙은 테마가 11월 11일 판입니다. 그 뒤 하단 메뉴 · 글 끝 순서가 바뀌어 붙여넣기가 필요합니다.", "plain"),
            ("row", "블로그에 붙은 판", "11.11 18:20", "블로그 화면의 버전 표시"),
            ("row", "저장소 최신 판", "11.13 08:05", "index.html 마지막 커밋"),
        ])
    pages = [   # 판단 근거 카드 — 접지 않는다 (7-5)
        ("등록 종목 합계", V("136개"), "종목 99 · ETF 37 · 간단 종목 853개는 게시 전"),
        ("미국 종목 페이지", f'{V("64개")} 중 {V("64개")}', "오늘 갱신 · 새 페이지 0"),
        ("한국 종목 페이지", f'35개 중 {over("33개")}', "2개는 쓰기 상한으로 내일"),
        ("미국 ETF 페이지", f'{V("18개")} 중 {V("18개")}', "오늘 갱신"),
        ("한국 ETF 페이지", f'{V("19개")} 중 {V("19개")}', "오늘 갱신"),
    ]
    return (dk.h2("화면", tab="화면")
            + QC.cards_grid(fresh + theme)
            + dk.sub_label("고정 페이지 갱신")
            + white_card(pages))


# ---------------------------------------------------------------- 발행 — 자동 실행 · 글 수 · 쓰기 한도
def publish_tab():
    runs = [   # 손이 필요한 것 먼저, 나머지는 접는다
        ("한국 종목 · ETF", warn(), "kr-stocks · Worker 16:11 · 9분 · 성공했으나 홈 시세 0건 올림"),
        ("미국 증시 리포트", ok("성공"), "Worker 07:31 · 6분 · 글 1편"),
        ("미국 종목 · ETF · 전망", ok("성공"), "nvda-report · Worker 07:42 · 14분 · 엔비디아 글 1편 · 종목 64 · ETF 18 · 증시 전망 · 테마"),
        ("인물 발언", ok("성공"), "Worker 08:02 · 5분 · 글 1편"),
        ("방송 브리핑", ok("성공"), "Worker 08:01 · 3분 · 글 없음 · 기록만"),
        ("홈 시세", ok("성공"), "GitHub 06:37 · 2분"),
        ("홈 뉴스", ok("성공"), "Worker 06:45 · 3분"),
        ("댓글 답글", ok("성공"), "오늘 6번 · 답글 0건"),
        ("Gemini 모델 점검", idle(), "월요일만"),
    ]
    count = QC.question_card(
        "오늘 새 글은 몇 편?", "3편", "neutral", "#111", [
            ("평일 정기 글 3편이 올라갔습니다. 하루 한 자리 수 규칙 안입니다.", "plain"),
            (QC.chart_card("최근 14일 새 글 (편)",
                           [(d, [v]) for d, v in zip(
                               ("31", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"),
                               (3, 1, 0, 3, 3, 4, 3, 3, 1, 0, 3, 3, 3, 3))],
                           [QC.amber], [lambda v: "#111"], [], fmt=lambda v: f"{v:.0f}"), "html"),
        ], opened=True)
    w = ("Blogger 쓰기", "글 · 페이지 갱신")
    widths = dk.bar_widths([w[0]], ["312회"])
    quota = dk.card_of([dk.bar_row(esc(w[0]), 312 / 10000, dk.CHART_MAIN, "312회", widths,
                                   sub="전체 10,000 · 쓴 312 · 여유 9,688 · 429 중단 0번", first=True)])
    return (dk.h2("발행", tab="발행")
            + dk.sub_label("오늘 자동 실행")
            + white_card(runs, fold_at=2, noun="실행")
            + count
            + dk.sub_label("Blogger 쓰기 한도")
            + quota)


# ---------------------------------------------------------------- 수집 — 소스 · 예비 사슬 · 빈 칸 · 영상 뉴스
def collect_tab():
    blocked = QC.question_card(
        "막힌 수집 소스가 있나?", "1곳", "neutral", "#111", [
            ("CNN 공포탐욕이 11월 10일부터 응답하지 않습니다. 예비 소스가 없어 미국 증시 리포트의 그 칸이 비어 나갑니다.", "plain"),
            ("row", "CNN 공포탐욕", over("3일째"), "마지막 성공 : 11.10 06:45"),
            ("row", "Yahoo 시세", "정상", "예비 사슬로 넘어간 비율 4%"),
            ("row", "Google News", "정상", "어제 레이더 49번 모두 200"),
        ], opened=True)
    sources = [
        ("CNN 공포탐욕", warn("실패"), "3일째 · 예비 없음 · 미국 증시 리포트 한 칸"),
        ("Federal Register", ok(), "브라우저 UA 로 통과 중"),
        ("CNBC RSS", ok(), "예비 없음 · 막히면 데일리 중단"),
        ("FRED", ok(), "예비 없음 · 막히면 데일리 중단"),
        ("SEC EDGAR", ok(), "공시 · 내부자 거래"),
        ("CourtListener", ok(), "429 0번"),
        ("ARK 매매", ok(), "제3자 API · 구조 바뀌면 깨짐"),
    ]
    days = ("31", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13")
    chain = dk.trend_card("시세 예비 사슬로 넘어간 비율 (%)", list(days),
                          [("이 날", [2, 3, 2, 1, 4, 3, 2, 2, 5, 3, 4, 6, 5, 4], dk.CHART_MAIN, "solid"),
                           ("14일 평균", [3.3] * 14, dk.CHART_CMP, "dash")],
                          lambda v: f"{v:.0f}")
    empty = [
        ("미국 종목 애널리스트", f'{V("2%")}', "64개 중 1개 빈 칸"),
        ("미국 종목 공매도", f'{V("0%")}', "64개 모두 채움"),
        ("한국 종목 실적", f'{V("6%")}', "35개 중 2개 빈 칸"),
    ]
    media = [
        ("한국경제TV", "12건", "자막 12건 중 12건"),
        ("SBS Biz", "8건", "자막 8건 중 7건"),
        ("삼프로TV", "6건", "자막 6건 중 6건"),
        ("CNBC", "9건", "영어 자막 9건 중 9건"),
        ("Bloomberg", "4건", "영어 자막 4건 중 3건"),
    ]
    people = [("트럼프", 14), ("파월", 3), ("머스크", 6), ("젠슨 황", 2)]
    pw = dk.bar_widths([n for n, _ in people], [f"{v}건" for _, v in people])
    prow = [dk.bar_row(esc(n), v / 14, dk.CHART_MAIN, f"{v}건", pw, first=(i == 0)) for i, (n, v) in enumerate(people)]
    return (dk.h2("수집", tab="수집")
            + blocked
            + dk.sub_label("소스")
            + white_card(sources, fold_at=2, noun="소스")
            + dk.sub_label("예비사슬")
            + chart_top(chain, top=0)
            + dk.sub_label("빈칸")
            + white_card(empty)
            + dk.sub_label("영상뉴스")
            + white_card(media, fold_at=2, noun="채널")
            + dk.sub_label("인물발언")
            + dk.card_of(prow, fold_at=2, noun="인물"))


# ---------------------------------------------------------------- AI — 모델별 한도 · 시간대 · 예비 전환
def ai_tab():
    head = QC.question_card(
        "AI 한도는 넉넉한가?", "1개 80% 넘음", "neutral", "#111", [
            ("Gemini flash 가 하루 20회 중 17회를 썼습니다. 오늘 남은 실행 가운데 flash 를 부르는 것은 없습니다.", "plain"),
            ("row", "Gemini flash", over("17 / 20회"), "전체 20회 · 쓴 17회 · 여유 3회"),
            ("row", "Groq gpt-oss", "12만 / 20만", "전체 20만 토큰 · 여유 8만"),
        ], opened=True)
    models = [   # (이름, 쓴 양, 전체, 값 글자, 보조 줄 = 전체 → 쓴 양 → 여유)
        ("Gemini flash", 17, 20, "17 / 20회", "전체 20회 · 쓴 17회 · 여유 3회"),
        ("Gemini lite", 96, 500, "96 / 500회", "전체 500회 · 쓴 96회 · 여유 404회"),
        ("Groq gpt-oss", 12, 20, "12만 / 20만", "토큰 · 여유 8만"),
        ("Groq Qwen", 7, 20, "7만 / 20만", "토큰 · 여유 13만"),
        ("NVIDIA", 41, 1000, "41 / 1,000회", "여유 959회"),
    ]
    mw = dk.bar_widths([m[0] for m in models], [m[3] for m in models])
    mrows = [dk.bar_row(esc(n), u / t, dk.CHART_MAIN, over(v) if u / t >= 0.8 else v, mw, sub=s, first=(i == 0))
             for i, (n, u, t, v, s) in enumerate(models)]
    hours = QC.chart_card("시간대별 AI 사용 (만 토큰, 한국 시간)",
                          [(h, [v]) for h, v in (("0", 0.4), ("3", 0.2), ("6", 3.1), ("7", 5.2), ("8", 4.4), ("9", 0.6),
                                                 ("13", 1.2), ("16", 2.8), ("21", 0.9))],
                          [QC.amber], [lambda v: "#111"], [], fmt=lambda v: f"{v:.1f}")
    return (dk.h2("AI", tab="AI")
            + head
            + dk.sub_label("모델별")
            + dk.card_of(mrows, fold_at=2, noun="모델")
            + chart_top(hours)
            + dk.sub_label("예비전환")
            + white_card([("예비 모델로 넘어감", V("3번"), "Groq 한도 → NVIDIA 2번 · Gemini lite 1번"), ("사슬 전체 실패", V("0번"), "모든 모델이 답하지 못한 실행"), ("검사 탈락", V("1번"), "금지어 · 길이 검사에서 다시 부름")])
            + dk.sub_label("댓글답글")
            + dk.card_of([dk.bar_row("오늘", 4 / 30, dk.CHART_MAIN, "4 / 30건", dk.bar_widths(["오늘"], ["4 / 30건"]),
                                     sub="하루 상한 30건 · 여유 26건", first=True)]))


# ---------------------------------------------------------------- 기록 — 상태 브랜치 · 빠진 날 · 크기
def record_tab():
    head = QC.question_card(
        "기록이 빠진 날이 있나?", "최근 30일 1일", "neutral", "#111", [
            ("11월 8일 방송 기록이 비어 있습니다. 그날 방송 브리핑 실행이 예약 누락이었습니다.", "plain"),
            ("row", "방송 기록", over("11.08 빠짐"), "media-state"),
            ("row", "나머지 8곳", "빠진 날 없음", "최근 30일"),
        ], opened=True)
    branches = [
        ("방송 기록", warn("빠진날"), "media-state · 11.08 · 오늘 07:58"),
        ("미국 증시 리포트", ok(), "report-state · 오늘 07:36"),
        ("엔비디아 · 종목", ok(), "nvda-state · 오늘 07:55"),
        ("한국 종목", ok(), "kr-state · 어제 16:20"),
        ("인물 발언", ok(), "radar-state · 오늘 08:06"),
        ("트럼프 기록", ok(), "trump-state · 정기 실행 끝남"),
        ("소송 조사", ok(), "court-survey · 11.09"),
        ("댓글", warn("덮어쓰기"), "comment-state · 이력 없이 저장"),
        ("홈 · 그림", ok(), "gh-pages · 오늘 06:37"),
    ]
    days = ("10.14", "10.21", "10.28", "11.4", "11.11", "11.13")
    size = dk.trend_card("gh-pages 크기 (MB)", list(days),
                         [("gh-pages", [31, 33, 36, 38, 41, 42], dk.CHART_MAIN, "solid"),
                          ("jsDelivr 제한", [50] * 6, dk.CHART_CMP, "dash")],
                         lambda v: f"{v:.0f}")
    return (dk.h2("기록", tab="기록")
            + head
            + dk.sub_label("상태 브랜치")
            + white_card(branches, fold_at=2, noun="브랜치")
            + chart_top(size)
            + dk.guide("주의", "jsDelivr 제한(약 50MB)은 공식 문서로 다시 확인할 값입니다."))


# ---------------------------------------------------------------- 전망 — 판정일 · 근거 · 결과 · 알림
def forecast_tab():
    soon = QC.question_card(   # 7일 안 일정 = 보라 카드 (4절 · 7-1 예외)
        "다가오는 판정일은?", "11.14", "soon", QC.SOON, [
            ("내일 물가 발표 뒤 판정입니다. 시세가 들어오면 다음 날 아침 실행에서 결과가 적힙니다.", "plain"),
            ("row", "물가 발표 뒤 S&P 500 은?", "11.14", "등록 : 11.03 · 근거 3건"),
            ("row", "연말 반도체 업종은?", "12.04", "등록 : 11.05 · 근거 2건"),
        ], opened=True)
    live = [
        ("물가 발표 뒤 S&P 500 은?", "오늘", "근거 3건 · 판정 11.14"),
        ("연말 반도체 업종은?", over("4일 전"), "근거가 4일째 붙지 않음 · 판정 12.04"),
        ("코스피 급락 뒤 회복은?", "어제", "근거 2건 · 판정 2027.2"),
    ]
    alerts = [
        ("자료 누락", "11.12", "코스피 하루 건너뜀"),
        ("늦은 등록", "11.10", "한국 전망 1건 · 사건 하루 뒤 등록"),
    ]
    return (dk.h2("전망", tab="전망")
            + soon
            + dk.sub_label("진행중")
            + white_card(live)
            + dk.sub_label("판정")
            + white_card([("맞음", V("2건"), "등록 뒤 판정까지 끝난 전망"), ("틀림", V("1건"), "세부 전망으로 이어짐"), ("어느 쪽도 아님", V("1건"), "")])
            + dk.sub_label("알림")
            + white_card(alerts))


def main():
    os.makedirs(OUT, exist_ok=True)
    body = summary_tab() + screen_tab() + publish_tab() + collect_tab() + ai_tab() + record_tab() + forecast_tab()
    body = dk.align_titles(dk.WRAP_OPEN + body + dk.WRAP_CLOSE)
    path = dk.write_mock(body, os.path.join(OUT, "mock_ops.html"), NAME)
    print(f"[{NAME}] {path}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
