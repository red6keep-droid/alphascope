"""AlphaScope 시황 해설 — 새 틀('이어 쓰는 시황 기사', 수집기 17절 format story) 블로그 화면 목업 (2026-11-17 사용자 "새 틀 화면 목업 만들어 줘").

    python experiments/market-commentary/mock_story.py

- 재료 = 수집기 시험 글(run 44024100385, 11-17 am)을 17절 칸 모양으로 옮기고 18~22절 규칙(제목 = 주제만 · 부호 없는 등락 · 이름 한 토막 → 소속만 · banner 칸)으로 고친 것 (11-19)(아래 SAMPLE) + 묶음 briefing/2026-11-17-am.json 숫자.
- 발행기가 할 일을 흉내 낸다: 합니다체(dk.formal) · 증감 숫자 삼각형 · 줄표 없애기 · 종목 링크 · 디자인 가이드라인 7-4(표 대신 이름 · 값 카드).
- 출력: output/mock_story.html (커밋 안 함). AI 0 · 네트워크 0.
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, ".."))
import design_kit as dk  # noqa: E402

OUT = os.path.join(BASE, "output", "mock_story.html")
BLOG = "https://alphascope.blogspot.com/"

# 수집기 columns/{날짜}-{slot} 새 칸 (17절 안 + 18절 블로그 부탁: sectors[].chg_pct 숫자)
SAMPLE = {
    "format": "story", "date": "2026-11-17", "slot": "am",
    "title": "앤트로픽 IPO와 엔비디아 악재에 기술주 급락, 나스닥 2.47% 하락",   # Q22: 주제만
    "summary": "앤트로픽 IPO를 앞둔 유동성 쏠림 우려와 엔비디아 리더십 악재가 겹치며 기술주 중심 하락세다.",
    "overview": ("11월 16일 뉴욕 증시는 앤트로픽 IPO를 앞둔 자금 이동과 엔비디아를 둘러싼 경영진 불확실성에 기술주를 중심으로 하락했다. "
                 "미국 상무부의 대중국 반도체 우회 수출 규제 강화 움직임도 투자 심리를 위축시켰다. "
                 "인플레이션 경계감과 지정학적 리스크가 더해진 가운데 시장의 시선은 오늘 밤 발표될 엔비디아 실적으로 쏠린다."),
    "indexLine": "11월 16일(월) 미국장: S&P 500 1.91% 하락 · 나스닥 종합 2.47% 하락 · 다우존스 1.40% 하락 · 러셀 2000 1.69% 하락",
    "market": ("기술 업종이 2.39% 내리며 가장 큰 하락 폭을 기록했고 에너지와 커뮤니케이션도 각각 1.91%, 1.72% 떨어졌다. "
               "종목별로는 알파벳이 3.52% 급락했으며 엔비디아와 아마존도 각각 2.95%, 2.49% 하락했다. "
               "반면 소재 업종은 0.59% 올랐고 유틸리티와 필수소비재도 각각 0.43%, 0.33% 상승하며 방어주 위주의 흐름을 보였다. "
               "이는 위험 회피 심리가 강해지며 기술주에 쏠렸던 자금이 상대적으로 안정적인 업종으로 옮겨갔음을 보여준다."),
    "drivers": [
        {"heading": "앤트로픽 IPO 기대와 유동성 쏠림 우려",
         "body": ("앤트로픽의 대규모 IPO 상장을 앞두고 시장 자금이 집중될 것이라는 전망이 제기되었다. "
                  "브래드 거스트너(알티미터 캐피털)는 앤트로픽 IPO에 역대 최대 규모인 50억 달러의 주문을 신청했다고 밝혔다. "
                  "에릭 프리먼(노던 트러스트)은 앤트로픽 IPO가 전체 AI 생태계의 수요를 가늠할 척도가 될 것으로 보았다. "
                  "반면 브라이언 모이니한(뱅크오브아메리카)은 앤트로픽 IPO로 관심이 쏠리면서 일반 기업들의 상장 일정이 순연되고 있다고 설명했다. "
                  "이 같은 대형 상장 이벤트가 기술주 전반의 유동성을 흡수할 수 있다는 경계감이 시장에 형성되어 있다.")},
        {"heading": "엔비디아 경영진 리스크와 규제 강화",
         "body": ("뉴욕타임스는 마코 루비오 국무장관이 안보 관련 경고 메모를 전달했다고 보도했다. "
                  "닐 캠플링 애널리스트는 이사회가 당장 대규모 경영진 교체에 나설 가능성은 낮지만 리더십 공백에 따른 불확실성이 크다고 평가했다. "
                  "동시에 미국 상무부는 제3국을 통한 대중국 AI 칩 우회 수출을 차단하는 규정 개정을 검토하며 반도체주를 압박했다. "
                  "오는 12월 상원 은행위원회에서 엔비디아 관련 청문회가 열릴 예정이다.")},
        {"heading": "인플레이션 압력과 연준 금리 경로 경계",
         "body": ("예상보다 높은 인플레이션 데이터 발표 이후 연준의 금리 운용에 대한 경계감이 부상했다. "
                  "BNP 파리바는 연준이 인플레이션 강도에 놀라며 추가 금리 인상이 불가피함을 인식하고 있다고 설명했다. "
                  "베스 해막(클리블랜드 연은 총재)은 인플레이션 심리 고착화를 막기 위해 점진적인 금리 인상으로 긴축을 유지해야 한다고 주장했다. "
                  "케빈 워시(연준 이사)는 AI 도입에 따른 생산성 향상이 인플레이션 압박을 빠르게 상쇄하지 못할 수 있음을 지적했다. "
                  "기업들의 비용 전가 움직임으로 인해 물가 상승 압력이 광범위하게 지속되는 상태다.")},
    ],
    "sectors": [
        {"name": "기술", "chg_pct": -2.39, "check": "엔비디아 실적 발표 후 반응"},
        {"name": "에너지", "chg_pct": -1.91, "check": "국제 유가 하락세 지속 여부"},
        {"name": "커뮤니케이션", "chg_pct": -1.72, "check": "알파벳 등 대형 기술주 수급"},
        {"name": "소재", "chg_pct": 0.59, "check": "방어적 매수세 유입 지속 여부"},
    ],
    "pointsTitle": "오늘 한국장 관전 포인트",
    "points": [
        "09:00 — 지난밤 미국 기술 업종 2.39% 하락 · 알파벳 3.52% 하락 뒤 한국장 첫 반응",
        "오늘 밤 미국 장 마감 뒤 — 엔비디아 실적 발표, AI 인프라 수요와 데이터센터 매출 전망 확인",
    ],
    "oneLine": "앤트로픽 IPO 유동성 흡수 우려와 엔비디아 리더십 악재가 겹치며 기술주 중심으로 위험 회피 장세가 펼쳐진 상태다.",
    "tickers": ["GOOGL", "NVDA", "AMZN"],
    "model": "gemini:gemini-4-hydrogen",
    "banner": {"titles": [["기술주 내림 뒤", "엔비디아 실적 기다림"], ["기술주 급락", "실적 대기"]], "keys": ["미국 기술 업종 약세", "반도체 관망", "한국장 첫 반응"]},
}
INDICES = [("S&P 500", "대형주", 7416.59, -1.91), ("나스닥", "기술주", 24509.76, -2.47),
           ("다우존스", "우량주", 51608.17, -1.40), ("러셀 2000", "소형주", 2742.94, -1.69)]   # 묶음 close.indices
LINKS = {"GOOGL": ("알파벳", "p/googl.html"), "NVDA": ("엔비디아", "p/nvda.html"), "AMZN": ("아마존", "p/amzn.html")}   # 종목 고정 페이지 (발행기는 pages_live 로)

def chg(v):
    """증감 = 부호 숫자 + 증감 색 + 굵게. 마무리 fix_colons 가 삼각형(글자의 80% · 위로 1 · 숫자와 2, dk.tri_span)으로 바꾼다 (가이드라인 5절).
    글자 크기 그대로의 ▲ 를 바로 쓰는 옛 함수는 쓰지 않는다 (2026-11-19 사용자 "삼각형 가이드에 맞나")."""
    col = dk.UP if v > 0 else dk.DOWN if v < 0 else dk.MUTED
    return f'<span style="color:{col};font-weight:700;white-space:nowrap;">{v:+.2f}%</span>' if v else '<span style="font-weight:700;">0.00%</span>'


DOWN_W = r"(?:내리|내린|내려|하락|떨어|급락|빠지|빠졌)"
UP_W = r"(?:오르|올랐|오른|상승|급등|뛰)"


def directional(html):
    """'2.39% 내리며' · '0.59% 올랐고'처럼 부호 없는 숫자 + 방향 낱말 → 삼각형 + 증감 색 (가이드라인 5절). '각각 1.91%, 1.72% 떨어졌다'도 같이."""
    def paint(m, up):
        nums = re.sub(r"(\d+(?:\.\d+)?)%", lambda n: chg(float(n.group(1)) * (1 if up else -1)), m.group(1))
        return nums + m.group(2)
    html = re.sub(r"((?:\d+(?:\.\d+)?%(?:,\s*)?)+)(\s*(?:씩\s*)?" + DOWN_W + ")", lambda m: paint(m, False), html)
    html = re.sub(r"((?:\d+(?:\.\d+)?%(?:,\s*)?)+)(\s*(?:씩\s*)?" + UP_W + ")", lambda m: paint(m, True), html)
    return html


def link_stocks(html, seen):
    """기사 속 종목 링크 — 처음 나온 이름만 보라 #7C3AED (가이드라인 10절)."""
    for t, (name, path) in LINKS.items():
        if t in seen or name not in html:
            continue
        html = html.replace(name, f'<a href="{BLOG}{path}" style="color:{dk.STOCK_LINK};text-decoration:none;">{name}</a>', 1)
        seen.add(t)
    return html


def prose(text, seen):
    """수집기 '-다'체 → 합니다체 · 증감 숫자 · 종목 링크."""
    return link_stocks(directional(dk.tint(dk.esc(dk.formal(text)))), seen)


def para(html):
    return f'<p style="margin:0 0 14px;padding:0 0 0 {dk.ALIGN_PX}px;word-break:keep-all;">{html}</p>'


def index_row():
    cells, themes = [], []
    for name, mean, close, cp in INDICES:
        cells.append(f'<span data-idx-cell="1" style="display:block;flex:0 0 auto;min-width:150px;box-sizing:border-box;background:#fff;padding:{14 - dk.VP}px 16px {14 - dk.VP}px 12px;">'
                     f'<span style="display:block;font-weight:700;color:#111;font-size:{dk.NAME};line-height:{dk.LH_CARD};white-space:nowrap;">{dk.paren(f"{name} ({mean})")}</span>'
                     f'<span style="display:block;margin-top:4px;line-height:25px;white-space:nowrap;"><span style="font-size:{dk.NAME};color:#111;">{close:,.2f}</span> '
                     f'<span style="font-size:{dk.CHG_SIZE};">{chg(cp)}</span></span></span>')
        themes.append("neutral")
    return (f'<div data-cards="1" style="overflow-x:auto;margin:0 0 16px;-webkit-overflow-scrolling:touch;scrollbar-width:none;">'
            f'<span style="display:flex;width:max-content;border-radius:8px;overflow:hidden;">{dk.dir_cells(cells, themes)}</span></div>')


def one_line_card(text, seen):
    bg, bd = dk.CARD_DIR["neutral"]
    return (f'<div style="background:{bg};border:1px solid {bd};border-radius:10px;padding:{24 - dk.VP}px 14px;margin:8px 0 0;">'
            f'<div style="font-size:14px;line-height:20px;font-weight:700;color:#6B7280;margin:0 0 6px;">핵심 한 줄</div>'
            f'<div style="font-size:18px;line-height:30px;font-weight:500;color:#111;word-break:keep-all;">{prose(text, seen)}</div></div>')


def points(items):
    rows = []
    for p in items:
        when, _, what = p.partition(" — ") if " — " in p else ("", "", p)
        if re.fullmatch(r"\d{1,2}:\d{2}", when.strip()) and "첫 반응" in what:
            when = ""   # 장 시작 줄의 `09:00` 은 늘 같은 시각이라 뺀다 (2026-11-19 사용자 "고정이면 삭제")
        lead = f'<b style="color:#111;">{dk.esc(when)}</b> : ' if when else ""
        rows.append(dk.dot_li(lead + directional(dk.tint(dk.esc(what))), lh=35, margin="12px 0"))
    return f'<ul style="list-style:none;margin:0 0 8px;padding:0 0 0 {dk.ALIGN_PX}px;">{"".join(rows)}</ul>'


def iconed(sec, icon):
    """구획 제목 앞 기본형 아이콘(회색 원 22 · 글자와 6, 가이드라인 8절) — 지수 · 업종 흐름 추세선 · 장을 움직인 변수 기사 · 업종별로 볼 것 막대 · 관전 포인트 과녁 (2026-11-19 사용자)."""
    return re.sub(r"(<h2[^>]*>)", lambda m: m.group(1) + f'<span style="flex:none;display:flex;align-self:center;margin-right:-4px;">{dk.soft_icon(icon)}</span>', sec, count=1)


def build(d):
    seen = set()
    # 제목 줄 = `11.17 미국 증시시황`(am = 미국 · pm = 한국), 그날 주제는 배너 아래 머리글로 (2026-11-17 사용자)
    y, m, dd = d["date"].split("-")
    title = f'{int(m)}.{dd} 증시 시황'   # 폰 제목 줄에 기준 날짜 · 공유가 같이 들어가게 미국 · 한국을 뺌 (2026-11-19 사용자)
    topic = d["title"]   # 수집기 Q22: title = 그날 주제만
    # 저장 제목(블로거 · 검색) = `11.17 미국 증시시황 : 주제` — 화면 제목 줄은 ` : ` 앞까지만 (테마가 자름, 발행기 · 테마 몫), 주제는 배너 아래 머리글 (2026-11-17 사용자)
    # 머리글의 `▼ 2.47% 하락` 처럼 삼각형 + 방향 낱말이 겹쳐도 그대로 둔다 (2026-11-17 사용자 "두 번 나와도 된다")
    stored_title = f"{title} : {topic}"  # noqa: F841 — 목업은 화면 제목 줄만 그린다
    headline = (f'<h2 data-headline="1" style="margin:0 0 12px;padding:0 0 0 {dk.ALIGN_PX}px;font-size:22px;line-height:32px;font-weight:700;color:#111;'
                f'word-break:keep-all;">{dk.esc(topic)}</h2>')
    # 기준 날짜 = 제목 줄 오른쪽 · 공유 버튼 앞 (테마가 [data-title-basis] 를 옮김, 2026-11-19 사용자). 회색 기준 상자(data-report-stamp)는 쓰지 않는다 — 공유 버튼도 제목 줄에 남는다
    # 기준 줄 = `11.16 미국 종가`(아침) · `11.17 한국 종가`(저녁) — 제목 줄이 두 편 같아(`11.17 증시 시황`) 편 구분을 여기서 (2026-11-19 사용자 가안)
    basis = '11.16 미국 종가' if d['slot'] == 'am' else f'{int(m)}.{dd} 한국 종가'
    stamp = f'<p data-title-basis="1" style="margin:0 0 14px;font-size:13px;line-height:19px;color:#6B7280;">{basis}</p>'
    banner = ('<figure style="margin:0 0 16px;"><img src="story-mock/banner-am.webp" alt="AI 생성 이미지 — 기술주 내림 뒤 엔비디아 실적 기다림" width="900" height="350" style="display:block;width:100%;height:auto;">'
              '</figure>')   # banner.py 확정 사양(900×350), 배경 = 11-17 Lucid Origin 시험 그림
    lead = f'<p data-seo-lead="1" data-lead="1" style="{dk.SEO_LEAD}padding:0 0 0 {dk.ALIGN_PX}px;">11월 17일 아침, {prose(d["summary"], set(LINKS))}</p>'
    body = [stamp, banner, headline, lead]
    # 강조 바탕 카드 = 대표 지수(첫 칸) 방향 색, 외곽선 · 접기 없음 (2026-11-19 사용자)
    cp0 = INDICES[0][3]
    bg = dk.CARD_DIR["positive" if cp0 > 0 else "negative" if cp0 < 0 else "neutral"][0]

    def soft_card(inner, head="", margin="0 0 8px", bg=bg):
        return (f'<div style="background:{bg};border-radius:10px;padding:{18 - dk.VP}px 14px;margin:{margin};">'
                f'{head}<p style="margin:0;word-break:keep-all;">{inner}</p></div>')

    # 한눈에 보기 = 보라 테마 바탕 + 카드 안 제목 = 강조형 아이콘(보라 네모 24 · 글자와 8) + 구획 제목 크기 (2026-11-19 사용자)
    # 제목 = h2 (테마의 폰 구획 제목 20/26 을 같이 받게 — span 이면 폰에서 22 로 남아 다른 구획 제목보다 컸다, 2026-11-19 사용자 "폰트 사이즈 통일")
    ov_head = (f'<h2 style="display:flex;align-items:center;gap:8px;margin:0 0 8px;padding:0;font-size:{dk.H2_SIZE};line-height:{dk.LH_H2};font-weight:700;color:#111;">'
               f'{dk.solid_icon("pulse", "#7C3AED")}<span>한눈에 보기</span></h2>')
    body.append(soft_card(prose(d["overview"], seen), ov_head, "24px 0 8px", dk.CARD_DIR["uncertain"][0]))
    # 지수 · 업종 흐름: 끝의 정리 문장('이는 …')은 따로 강조 바탕 카드 (2026-11-19 사용자 "정리하는 글이니깐")
    sents = re.split(r"(?<=다\.)\s+", d["market"].strip())
    wrap_up = sents.pop() if len(sents) > 1 and re.match(r"(이는|이 같은|이처럼|결국)", sents[-1]) else ""
    mk = index_row() + para(prose(" ".join(sents), seen))
    if wrap_up:
        mk += soft_card(prose(wrap_up, seen), margin="0 0 8px")
    body.append(iconed(dk.section("지수 · 업종 흐름", mk), "trend"))
    drv = "".join(dk.sub_label(f'{i}. {x["heading"]}') + para(prose(x["body"], seen)) for i, x in enumerate(d["drivers"], 1))
    body.append(iconed(dk.section("장을 움직인 변수", drv), "news"))
    if d["sectors"]:
        rows = [(f'<b>{dk.esc(s["name"])}</b>', chg(s["chg_pct"]), dk.esc(s["check"])) for s in d["sectors"]]
        body.append(iconed(dk.section("업종별로 볼 것", '<div data-cards="1">' + dk.ccard(rows) + '</div>'
), "bars"))   # `아래 줄 = 다음 장에서 볼 것` 안내 줄 삭제 (2026-11-19 사용자)
    body.append(iconed(dk.section(d["pointsTitle"], points(d["points"])), "target"))
    body.append(one_line_card(d["oneLine"], seen))
    # 글 끝 꼬리말 없음 — 출처 · 면책 · AI 고지는 블로그 공통 푸터 하나에만 (가이드라인 2절 8, 2026-11-19 사용자)
    # 함께 보는 페이지 = 공용 dk.related_buttons(구분선 목록 · 3px 점 · 16 보통 · 오른쪽 나가는 아이콘 · data-related, 가이드라인 10절) — 옛 dot_li 목록은 규칙 밖 (2026-11-19 사용자)
    body.append(dk.related_buttons([("미국 증시 리포트", f"{BLOG}search/label/%EB%AF%B8%EA%B5%AD%20%EC%A6%9D%EC%8B%9C%20%EB%A6%AC%ED%8F%AC%ED%8A%B8"),
                                    ("증시 전망", f"{BLOG}search/label/%EC%A6%9D%EC%8B%9C%20%EC%A0%84%EB%A7%9D")]))
    html = dk.WRAP_OPEN + dk.fix_colons("".join(body)) + dk.WRAP_CLOSE
    return title, html


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    t, h = build(SAMPLE)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    print(dk.write_mock(h, OUT, t) or "index.html 없음 — 목업 못 만듦")
