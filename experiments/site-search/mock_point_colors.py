"""질문하기 포인트 색 시안 비교 (2026-11-12 사용자: "검은 글씨 주황이 안 어울린다, 어떤 색이 좋은지 시안으로" → "C 를 그라데이션으로 AI 느낌").

    python experiments/site-search/mock_point_colors.py   # output/mock_point_*.html + mock_point_colors.html(색 6안) + mock_point_gradient.html(C 그라데이션)

mock_search.html 을 먼저 만들고, 시안마다 포인트 변수(--as-point · --as-point-ink · --as-point-icon · --as-point-line)만 바꾼 사본을 만든다.
비교 페이지는 시안마다 질문하기 창(?chat=삼성전자 실적)을 iframe 으로 나란히 보인다.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")

# (키, 이름, 설명, 바탕, 글자, 말풍선 아이콘, 테두리) — 글자 대비는 WCAG 기준 (흰 바탕 위 글자가 아니라 버튼 바탕 위 글자)
OPTIONS = [
    ("a", "A 지금 · 연한 주황 + 검정", "그래프 주인공 주황 #F5B971 · 글자 #111 (대비 10.8:1)", "#F5B971", "#111111", "currentColor", "transparent"),
    ("b", "B 진한 주황 + 흰", "주황 계열 유지, 진하게 #C2410C · 흰 글자 (5.2:1) — 경고 주황 #E8710A 와 가까움", "#C2410C", "#FFFFFF", "currentColor", "transparent"),
    ("c", "C 청록 + 흰", "홈 `시장 흐름과 종목` · 증시 전망 아이콘 청록 #0E7490 · 흰 글자 (5.4:1) — 빨강 · 파랑 증감 색과 안 겹침", "#0E7490", "#FFFFFF", "currentColor", "transparent"),
    ("d", "D 검정 + 주황 아이콘", "버튼 · 말풍선 #111 · 흰 글자 (18.9:1), 포인트는 말풍선 아이콘만 주황 #F5B971", "#111111", "#FFFFFF", "#F5B971", "transparent"),
    ("e", "E 연한 주황 바탕 + 진한 주황 글자", "바탕 #FFF3E3 · 테두리 #F5B971 · 글자 #9A3412 (6.7:1) — 부드러운 톤", "#FFF3E3", "#9A3412", "currentColor", "#F5B971"),
    ("f", "F 짙은 청록 + 흰", "C 보다 한 단계 깊게 #115E59 · 흰 글자 (7.6:1) — 차분한 톤", "#115E59", "#FFFFFF", "currentColor", "transparent"),
]


# C 그라데이션 시안 (2026-11-12 사용자: "C 를 그라데이션을 활용해서 약간 AI 느낌으로").
# (키, 이름, 설명, 바탕(그라데이션 가능), 글자, 아이콘 색, 테두리, 반짝임 아이콘, 버튼 그림자)
# 흰 글자 대비는 그라데이션 양 끝 색마다 잰 값 중 낮은 쪽.
SHADOW = "0 8px 24px rgba(15,23,42,.25)"
GRADIENTS = [
    ("c", "C 기준 · 청록 한 색", "#0E7490 · 흰 글자 (5.4:1)", "#0E7490", "#FFFFFF", "currentColor", "transparent", False, SHADOW),
    ("g1", "C1 청록 → 바다 파랑", "#0E7490 → #0369A1 · 은은한 그라데이션 · 흰 글자 (5.4:1 이상)", "linear-gradient(135deg,#0E7490 0%,#0369A1 100%)", "#FFFFFF", "currentColor", "transparent", False, SHADOW),
    ("g2", "C2 짙은 청록 → 청록 → 초록 청록", "#155E75 → #0E7490 → #0F766E · 청록 안에서만 흐름 · 흰 글자 (5.4:1 이상)", "linear-gradient(135deg,#155E75 0%,#0E7490 50%,#0F766E 100%)", "#FFFFFF", "currentColor", "transparent", False, SHADOW),
    ("g3", "C3 청록 → 남보라 + 반짝임 아이콘", "#0E7490 → #4F46E5 · 질문하기 아이콘 ✦ · 흰 글자 (5.4:1 이상) — AI 느낌 가장 뚜렷", "linear-gradient(135deg,#0E7490 0%,#4F46E5 100%)", "#FFFFFF", "currentColor", "transparent", True, "0 8px 24px rgba(79,70,229,.32)"),
    ("g4", "C4 청록 → 보라 + 반짝임 + 빛 그림자", "#0E7490 → #6D28D9 · ✦ · 보라빛 그림자 · 흰 글자 (5.4:1 이상) — 보라는 일정 · 중립 강조 색과 겹침", "linear-gradient(135deg,#0E7490 0%,#6D28D9 100%)", "#FFFFFF", "currentColor", "transparent", True, "0 8px 28px rgba(109,40,217,.38)"),
    ("g5", "C5 청록 → 바다 파랑 + 반짝임", "C1 색 + ✦ 아이콘 — 색은 차분하게, 모양으로 AI 느낌", "linear-gradient(135deg,#0E7490 0%,#0369A1 100%)", "#FFFFFF", "currentColor", "transparent", True, "0 8px 24px rgba(3,105,161,.30)"),
]
CHAT_PATH = '<path d="M4 5h16v11H9l-5 4z"/>'
SPARKLE = ('<path d="M11 3l1.8 5.2L18 10l-5.2 1.8L11 17l-1.8-5.2L4 10l5.2-1.8z"/>'
           '<path d="M18.5 14.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/>')


def build(base, css_all, options, out_name, title, lead):
    cells = []
    for opt in options:
        key, name, desc, bg, ink, icon, line = opt[:7]
        sparkle, shadow = (opt[7], opt[8]) if len(opt) > 7 else (False, SHADOW)
        vars_ = f"--as-point:{bg};--as-point-ink:{ink};--as-point-icon:{icon};--as-point-line:{line};"
        css = f"<style>:root{{{vars_}}}.as-chat-fab{{box-shadow:{shadow}}}</style>"
        page = base.replace("</head>", css + "</head>", 1)
        if sparkle:
            page = page.replace(CHAT_PATH, SPARKLE, 1)   # 질문하기 버튼 아이콘만 (목업 사본에서만)
        fn = f"mock_point_{key}.html"
        with open(os.path.join(OUT, fn), "w", encoding="utf-8") as f:
            f.write(page)
        sw = (f'<div class="sw" style="{vars_}">'
              f'<button type="button" class="as-chat-fab" style="box-shadow:{shadow}"><svg viewBox="0 0 24 24" aria-hidden="true">{SPARKLE if sparkle else CHAT_PATH}</svg><span>질문하기</span></button>'
              '<div class="as-msg as-me">삼성전자 실적</div>'
              '<div class="as-chat"><form><input placeholder="예: 삼성전자 실적 알려줘"><button type="button">보내기</button></form></div></div>')
        cells.append(f'<figure><figcaption><b>{name}</b><span>{desc}</span></figcaption>{sw}'
                     f'<iframe src="{fn}?chat=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90%20%EC%8B%A4%EC%A0%81" loading="lazy"></iframe>'
                     f'<a href="{fn}">따로 열기 ›</a></figure>')
    html = ('<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{title}</title><style>'
            'body{margin:0;padding:24px 16px;background:#F3F4F6;font-family:"Noto Sans KR",sans-serif;color:#111}'
            'h1{font-size:22px;margin:0 0 6px}p.lead{margin:0 0 20px;color:#6B7280;font-size:14px;line-height:21px}'
            '.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:20px}'
            'figure{margin:0;background:#fff;border:1px solid #E2E8F0;border-radius:12px;padding:12px;display:flex;flex-direction:column;gap:8px}'
            'figcaption b{display:block;font-size:16px}figcaption span{display:block;font-size:13px;line-height:19px;color:#6B7280;margin-top:2px}'
            'iframe{width:100%;height:560px;border:1px solid #E2E8F0;border-radius:8px}'
            'figure a{font-size:13px;color:#111;align-self:flex-end}'
            '</style><style>' + css_all + '</style><style>'
            '.sw{display:flex;align-items:center;flex-wrap:wrap;gap:12px;padding:16px;background:#F8FAFC;border-radius:8px}'
            '.sw .as-chat-fab,.sw .as-chat{position:static}'
            '.sw .as-chat{width:auto;height:auto;flex:1 1 220px;border-radius:999px;border:0;background:none;box-shadow:none}'
            '.sw .as-chat form{border:0;padding:0}'
            f'</style></head><body><h1>{title}</h1><p class="lead">{lead}</p>'
            f'<div class="grid">{"".join(cells)}</div></body></html>')
    out = os.path.join(OUT, out_name)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("만듦:", os.path.relpath(out, os.path.dirname(os.path.dirname(HERE))))


def main():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, os.path.join(HERE, "mock_search.py")], env=env, check=True)
    base = open(os.path.join(OUT, "mock_search.html"), encoding="utf-8").read()
    css_all = open(os.path.join(HERE, "search.css"), encoding="utf-8").read()
    build(base, css_all, OPTIONS, "mock_point_colors.html", "질문하기 포인트 색 시안",
          "질문하기 버튼 · 내 질문 말풍선 · 보내기 버튼에 쓰는 색. 각 칸은 실제 목업(질문: 삼성전자 실적)이고, 질문하기 버튼은 창을 닫으면(×) 보입니다.")
    build(base, css_all, GRADIENTS, "mock_point_gradient.html", "질문하기 C 그라데이션 시안",
          "C 청록을 기준으로 그라데이션 · 반짝임 아이콘(✦)으로 AI 느낌을 낸 시안. 그라데이션은 질문하기 버튼 · 내 질문 말풍선 · 보내기 세 곳에 같은 방향(왼쪽 위 → 오른쪽 아래)으로 들어갑니다.")


if __name__ == "__main__":
    main()
