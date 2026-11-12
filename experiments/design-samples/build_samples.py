"""디자인 샘플 — 아이콘 두 꼴 · 안내 아이콘 · 라벨 (2026-11-12 사용자: "아이콘 규칙을 정하고 샘플로 등록, 라벨도").

    python experiments/design-samples/build_samples.py      # output/mock_icons_labels.html

규칙 원본 = 디자인-가이드라인.md 8절 `라벨` · `아이콘`. 여기 그림은 모두 실제 코드에서 바로 부른다
(design_kit.soft_icon · solid_icon · pill · INFO_ICON, tech_signals.box, 홈 테마 alphaflow-home.html 의 .report-icon) —
규칙을 바꾸면 이 파일을 다시 돌려 샘플이 따라오는지 본다. 목업 서버(mock_server.py) 목록에 `design-samples` 로 보인다.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(EXP)
sys.path[:0] = [EXP, os.path.join(EXP, "issue_store")]
import design_kit as dk  # noqa: E402
import tech_signals as T  # noqa: E402

OUT = os.path.join(HERE, "output", "mock_icons_labels.html")

# 기본형 그림 — 어디에 쓰나 (이름은 design_kit.ICON_GLYPHS 키)
SOFT_USES = [
    ("calendar", "증시 전망 팝업 `단기` · `중기` · 검색 `실적 발표일`"),
    ("news", "증시 전망 팝업 `뉴스 기사` · 검색 `최근 소식`"),
    ("pulse", "검색 `오늘 주가`"),
    ("trend", "검색 `기간별 등락`"),
    ("bars", "검색 `실적`"),
    ("target", "검색 `EPS · PER · 목표가`"),
    ("gauge", "검색 `기술 지표`"),
    ("building", "검색 `회사 정보`"),
    ("range", "검색 `52주 범위`"),
    ("volume", "검색 `거래량`"),
    ("pie", "검색 `시가총액`"),
    ("clock", "(예비) 시각 · 경과"),
    ("person", "(예비) 인물"),
    ("scale", "(예비) 전망"),
]


def home_icons():
    """홈 카드 제목 아이콘(.report-icon) — 테마 원본에서 그대로 (색 면 네모 24 · 모서리 6 · 흰 그림 16)."""
    src = open(os.path.join(ROOT, "alphaflow-home.html"), encoding="utf-8").read()
    seen, out = set(), []
    for m in re.finditer(r'<span class="report-icon" style="background:(#[0-9A-Fa-f]{6});"[^>]*>(<svg.*?</svg>)', src, re.S):
        if m.group(0) in seen:
            continue
        seen.add(m.group(0))
        svg = m.group(2).replace("<svg ", '<svg width="16" height="16" style="display:block;" ', 1)
        out.append((m.group(1), f'<span style="display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:6px;background:{m.group(1)};color:#fff;">{svg}</span>'))
    return out


def sec(title, sub, body):
    return (f'<section style="margin:0 0 40px;"><h2 style="font-size:20px;line-height:28px;margin:0 0 4px;">{title}</h2>'
            f'<p style="margin:0 0 16px;font-size:14px;line-height:21px;color:#6B7280;">{sub}</p>{body}</section>')


def row(left, name, note):
    return (f'<div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #E2E8F0;">'
            f'<span style="flex:none;width:44px;display:flex;justify-content:center;">{left}</span>'
            f'<span style="flex:none;width:120px;font-size:14px;font-family:ui-monospace,monospace;color:#333;">{name}</span>'
            f'<span style="font-size:14px;line-height:20px;color:#333;">{note}</span></div>')


def main():
    soft = "".join(row(dk.soft_icon(k), k, u) for k, u in SOFT_USES)
    soft_demo = (f'<div style="margin:16px 0 0;padding:16px;border:1px solid #E2E8F0;border-radius:12px;">'
                 f'<div style="display:flex;align-items:center;gap:6px;font-size:15px;line-height:22px;font-weight:700;color:#111;">{dk.soft_icon("bars")}실적</div>'
                 f'<div style="display:flex;align-items:center;gap:6px;margin-top:14px;font-size:15px;line-height:22px;font-weight:700;color:#111;">{dk.soft_icon("calendar")}단기 <span style="font-weight:400;color:#6B7280;">· 며칠</span></div>'
                 f'<p style="margin:10px 0 0;font-size:13px;color:#6B7280;">쓰는 모양 = 소제목 15/22 굵게, 아이콘과 글자 6</p></div>')
    import hypo_pages as H  # noqa: E402 — 증시 전망 질문 줄 저울(강조형의 첫 쓰임)
    solid = (row(H.scale_icon(24), "scale 24", "증시 전망 질문 줄 앞 (청록 #0E7490)")
             + row(H.scale_icon(18), "scale 18", "증시 전망 목록 줄 앞")
             + "".join(row(h, c, "홈 카드 제목 앞(.report-icon)") for c, h in home_icons())
             + row(dk.solid_icon("bars", "#0E7490"), "solid_icon", "새로 만들 때 = design_kit.solid_icon(그림, 색)"))
    guide = (row(f'<span style="color:#6B7280;display:inline-flex;">{dk.INFO_ICON}</span>', "ⓘ 14", "안내 글 앞(dk.guide) — 정보 · 기준 설명")
             + row(f'<span style="color:#6B7280;display:inline-flex;">{H.EXCL_ICON}</span>', "! 13", "주의 · 한계 안내 한 줄 앞(증시 전망 근거 안내 · 검색 종목 페이지 안내)")
             + row(f'<span style="color:#111;display:inline-flex;">{dk.QUESTION_ICON}</span>', "? 20", "툴팁(11절) — 누르면 팝업"))
    pills = "".join(row(dk.pill(t, k, bare=True), f"pill {k}", u) for k, t, u in (
        ("area", "반도체", "뉴스 영역"), ("positive", "긍정", "긍정"), ("negative", "부정", "부정"), ("neutral", "논의중", "중립 · 상태"),
        ("uncertain", "불확실", "불확실"), ("good", "녹색", "녹색")))
    esc = dk.esc
    boxes = "".join(row(T.box(k, t, esc, sym=(k != "caution")), f"box {k}", u) for k, t, u in (
        ("up", "상승", "기술지표 · 의견 · 호재"), ("down", "하락", "기술지표 · 리스크"), ("flat", "중립", "중립"), ("caution", "주의", "과매수 · 과매도 (▲▼ 없음)")))
    new = row('<span style="display:inline-block;background:#B91C1C;color:#fff;font-weight:700;border-radius:3px;padding:1px 4px;line-height:12px;font-size:11px;">N</span>',
              "N", "가끔 바뀌는 칸이 지난번과 달라진 날")
    body = (sec("아이콘 · 기본형", "회색 면 원 22(#E5E7EB) 안 진회색 선 그림(#4B5563, 원의 0.55 · 선 1.6). 소제목 · 구획 제목 앞. 색을 쓰지 않는다 — 뜻이 아니라 칸 구분.", soft + soft_demo)
            + sec("아이콘 · 강조형", "색 면 네모(24 · 모서리 6, 목록 줄 18 · 모서리 4~5) 안 흰 선 그림(크기의 2/3). 강조 카드 · 질문 줄 · 홈 카드 제목 앞, 글자와 8. 색 = 그 기능 하나의 색.", solid)
            + sec("안내 아이콘", "글과 같은 색의 외곽선 원. 면 없음.", guide)
            + sec("라벨 · 외곽선 라벨 (dk.pill)", "1px 테두리 · 모서리 4 · 14px 보통 · 안쪽 3 5 2. 글 앞뒤에 붙으면 세로 가운데, 라벨과 글 5 · 라벨끼리 2.", pills)
            + sec("라벨 · 채운 상자 (tech_signals.box)", "14/18 굵게 · 폭 50 · 모서리 4. 판정 · 의견.", boxes)
            + sec("라벨 · N", "바탕 #B91C1C · 흰 글자 굵게 · 모서리 3.", new))
    html = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>디자인 샘플 · 아이콘 · 라벨</title><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap">'
            '<style>body{margin:0;background:#fff;color:#111;font-family:"Noto Sans KR",sans-serif;}main{max-width:720px;margin:0 auto;padding:28px 16px 60px;}</style></head>'
            f'<body><main><h1 style="font-size:24px;margin:0 0 6px;">아이콘 · 라벨 샘플</h1>'
            f'<p style="margin:0 0 32px;font-size:14px;color:#6B7280;">규칙 원본 = 디자인-가이드라인.md 8절. 이 화면은 실제 코드 함수로 그린다.</p>{body}</main></body></html>')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"만듦: {OUT}")


if __name__ == "__main__":
    main()
