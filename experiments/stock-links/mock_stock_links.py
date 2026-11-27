"""문장 속 종목 이름 링크 시안 — 블로그 실제 문장 다섯 곳을 안마다 나란히 그린다.

    python experiments/stock-links/mock_stock_links.py     # output/mock_stock_links.html

안:
  지금 = 블로그 그대로(일부만 보라 링크, 나머지 글자)
  고른 안 = 전부 링크 · 검은 굵게 · 아주 연한 회색 점선(점 2px · 간격 5px)
모든 안 공통: 누르는 순간 연보라 바탕, 자기 페이지 이름 · 제목 · 지수(나스닥) · 우리 목록에 없는 회사는 링크 없음.
목업에서는 눌러도 이동하지 않고 아래에 "○○ 페이지로" 알림만 띄운다.
"""
import html
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
BLOG = "https://www.newfact.app"
INK = "#5012BB"          # 블로그 보라(종목 링크 · 색 강조 공통)
DOT = "#D1D5DB"          # 아주 연한 회색 점선
DOT_LEN, DOT_STEP = 2, 7  # 점 2px · 다음 점까지 7px (간격 5px — 기본 dotted 보다 덜 촘촘하게)
UP, DN = "#d93025", "#1a73e8"

# 문장 속 종목 표시 {이름: (코드, 주소)} — 이름표(names.json)에 있는 것만
STOCKS = {
    "엔비디아": ("NVDA", "/p/nvidia-nvda-stock.html"), "아마존": ("AMZN", "/p/amazon-amzn-stock.html"),
    "알파벳(구글)": ("GOOGL", "/p/alphabet-googl-stock.html"), "디즈니": ("DIS", "/p/disney-dis-stock.html"),
    "애플": ("AAPL", "/p/apple-aapl-stock.html"), "테슬라": ("TSLA", "/p/tesla-tsla-stock.html"),
    "HMM": ("011200", "/p/hmm-011200-stock.html"), "삼성전기": ("009150", "/p/samsung-electro-009150-stock.html"),
    "CJ ENM": ("035760", "/p/cj-enm-035760-stock.html"),
}


def pct(v, tri=True):
    c = UP if v > 0 else DN
    if tri:
        t = "&#9650;" if v > 0 else "&#9660;"
        return (f'<span style="color:{c};white-space:nowrap;"><span style="font-size:15px;vertical-align:1px;margin-right:2px;">{t}</span>'
                f'{abs(v):.2f}%</span>'.replace(".00%", "%"))
    return f'<span style="color:{c};white-space:nowrap;">{"+" if v > 0 else "&#8722;"}{abs(v)}%</span>'


def hl(t):
    """블로그 색 강조(보라 글자) — 종목 링크와 같은 색이라 섞이는지 보려고 그대로 둔다."""
    return f'<span style="color:{INK};">{t}</span>'


# 문장 안 종목 자리 = [[이름]] 또는 [[이름|이전 링크]](지금 블로그에서 링크가 걸린 것)
SECTIONS = [
    ("Newfact 뉴스 글 문단", "11월 27일 글 · 소제목 아래 문단. 굵은 핵심 문장 · 보라 강조 글자가 이미 있는 자리",
     '<div style="font-size:19px;line-height:29px;color:#111;font-weight:700;padding-left:6px;margin:4px 0 10px;">2. 엔비디아 선적 중단 여파</div>'
     '<p style="margin:0;padding:0 0 0 6px;">금리 경계감으로 기술주 전반이 흔들린 날, <b style="font-weight:700;color:#111;">[[엔비디아]]는 '
     + pct(-2.22) + ' 하락하며</b> 나스닥 약세를 이끌었습니다. ' + hl("말레이시아 등 동남아 칩 선적 중단") + '에 이어 '
     + hl("S&amp;P 글로벌의 신용등급 하향 검토") + ' 소식이 겹치며 투자 심리를 위축시켰습니다. [[엔비디아]] 의회 청문회를 앞둔 불확실성도 남아 있습니다.</p>',
     "소제목의 엔비디아 · 지수 나스닥은 링크 없음. 마지막 문장은 같은 이름이 한 문단에 두 번 나오는 경우를 보려고 11월 26일 글에서 옮겨 붙임"),
    ("한국 증시 리포트 뉴스 줄", "11월 26일 리포트 · 뉴스 탭 한 줄씩. 이름 여러 개가 짧은 줄에 몰리는 자리",
     '<div style="font-size:17px;line-height:28px;">'
     '<p style="margin:0 0 10px;padding-left:6px;">[[HMM]]이 임시주주총회를 통해 대표이사를 재선임했으며 임기는 2028년 3월까지다. '
     '"[[HMM]] 및 LX판토스에서 약 10년간 최고경영자(CEO)를 역임한 검증된 경영 전문가"</p>'
     '<p style="margin:0 0 10px;padding-left:6px;">[[삼성전기]]는 주주가치 제고를 위해 보통주 200만 주와 우선주 5만 3천430주의 자사주를 소각하기로 공시</p>'
     '<p style="margin:0;padding-left:6px;">방미통위 중재로 LG헬로비전과 [[CJ ENM]]이 콘텐츠 사용료 협상에 합의하여 채널 송출 중단 사태를 피했다.</p></div>',
     "LX판토스 · LG헬로비전은 우리 종목 목록에 없어 링크 없음 — 눌리는 이름과 안 눌리는 이름이 섞이는 모습"),
    ("미국 종목 페이지 첫 문단", "넷플릭스 페이지 · 맨 위 요약 문단. 자기 이름(넷플릭스)은 링크 없음",
     '<p style="margin:0;padding-left:6px;color:#333;">11월 26일 새벽 넷플릭스(NFLX) 종가는 $59.41로 전날보다 ' + pct(0.92)
     + ' 올랐습니다. 평소 하루 움직임 안의 변화였습니다. 같은 날 함께 보는 회사 [[아마존]] ' + pct(-3.1) + ' · [[알파벳(구글)]] '
     + pct(-2.1) + '는 반대로 내렸습니다. 다음 실적 발표는 1월 19일 예정입니다.</p>', ""),
    ("비교 종목 문장 (그래프 위)", "넷플릭스 페이지 · `함께 보는 회사` 그래프 위 문장. 이름 넷이 한 문장에",
     '<p style="margin:0;padding-left:6px;font-size:18px;line-height:32px;">오늘(11월 26일 새벽) 함께 보는 회사는 [[디즈니]] ' + pct(2.5, False)
     + ', [[알파벳(구글)]] ' + pct(-2.1, False) + ', [[아마존]] ' + pct(-3.1, False) + ', [[애플]] ' + pct(0.4, False)
     + '였고, 넷플릭스는 ' + pct(0.9, False) + '였습니다.</p>', ""),
    ("한국 종목 연관 종목 문장", "포스코퓨처엠 페이지 · 밤사이 미국 연관 종목",
     '<p style="margin:0;padding-left:6px;font-size:18px;line-height:32px;">밤사이(11월 26일 새벽 마감) 연관 종목은 [[테슬라]] ' + pct(-1.2, False)
     + '였고, 오늘 포스코퓨처엠은 ' + pct(-0.3, False) + '였다.</p>', ""),
]

VARIANTS = [
    ("now", "지금", "블로그 그대로 — 이 다섯 자리는 링크 없음"),
    ("c", "고른 안", "전부 링크 · 검은 굵게 · 아주 연한 회색 점선(간격 넓게)"),
]


def render(body, v):
    seen = set()

    def one(m):
        name = m.group(1)
        sym, path = STOCKS[name]
        first = name not in seen
        seen.add(name)
        if v == "now":
            return name
        # 점선 = 밑줄 대신 바탕 그림 — 점 길이 · 간격을 직접 정한다(text-decoration dotted 는 간격을 못 바꿔 촘촘하다)
        style = (f"color:#111;font-weight:700;text-decoration:none;padding-bottom:2px;"
                 f"background-image:linear-gradient(90deg,{DOT} {DOT_LEN}px,transparent {DOT_LEN}px);"
                 f"background-size:{DOT_STEP}px 1.5px;background-repeat:repeat-x;background-position:0 100%;")
        return (f'<a class="sl" href="{BLOG}{path}" data-stock="{sym}" data-name="{html.escape(name)}" '
                f'style="{style}">{name}</a>')

    out = []
    for p in re.split(r"(<p[^>]*>.*?</p>)", body, flags=re.S):   # 문단마다 `처음` 을 다시 센다
        seen.clear()
        out.append(re.sub(r"\[\[(.+?)\]\]", one, p))
    return "".join(out)


CSS = f"""
:root {{ color-scheme: light; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #F1F5F9; color: #111; font-family: 'Noto Sans KR', -apple-system, sans-serif; word-break: keep-all; }}
.wrap {{ max-width: 440px; margin: 0 auto; padding: 16px 16px 90px; }}
h1 {{ font-size: 20px; line-height: 28px; margin: 6px 0 6px; }}
.lead {{ font-size: 14px; line-height: 22px; color: #475569; margin: 0 0 14px; }}
.legend {{ background: #fff; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 12px; font-size: 13px; line-height: 21px; color: #334155; margin: 0 0 18px; }}
.legend b {{ color: #111; }}
.sec {{ margin: 26px 0 0; }}
.sec h2 {{ font-size: 17px; line-height: 24px; margin: 0 0 2px; }}
.sec .where {{ font-size: 13px; line-height: 19px; color: #64748B; margin: 0 0 10px; }}
.card {{ background: #fff; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px 12px 14px; margin: 0 0 10px; font-size: 19px; line-height: 35px; }}
.tag {{ display: inline-block; font-size: 12px; line-height: 18px; font-weight: 700; padding: 1px 8px; border-radius: 10px; margin: 0 0 6px; background: #E2E8F0; color: #334155; }}
.tag.a {{ background: #FEF3C7; color: #92400E; }} .tag.b {{ background: #EDE9FE; color: #5012BB; }} .tag.c {{ background: #DCFCE7; color: #166534; }}
.tag + .tdesc {{ display: inline; font-size: 12px; color: #64748B; margin-left: 6px; }}
.note {{ font-size: 12px; line-height: 18px; color: #64748B; margin: -4px 0 0; }}
a.sl {{ border-radius: 3px; -webkit-tap-highlight-color: transparent; }}
a.sl:active, a.sl.on {{ background: #EDE9FE; }}
@media (hover: hover) {{ a.sl:hover {{ background-color: #F3F4F6; }} }}
.toast {{ position: fixed; left: 50%; bottom: 22px; transform: translateX(-50%); background: #111; color: #fff; font-size: 14px; line-height: 20px;
  padding: 9px 14px; border-radius: 8px; opacity: 0; transition: opacity .15s; pointer-events: none; max-width: calc(100% - 32px); }}
.toast.show {{ opacity: .92; }}
"""

JS = """
var t=document.getElementById('toast'),h;
document.addEventListener('click',function(e){var a=e.target.closest('a.sl');if(!a)return;e.preventDefault();
a.classList.add('on');setTimeout(function(){a.classList.remove('on');},250);
t.textContent=a.dataset.name+' 페이지로 이동 (목업이라 이동하지 않음)';t.classList.add('show');clearTimeout(h);h=setTimeout(function(){t.classList.remove('show');},1600);});
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    secs = []
    for i, (title, where, body, note) in enumerate(SECTIONS, 1):
        cards = "".join(
            f'<div class="card"><span class="tag {k}">{lab}</span><span class="tdesc">{html.escape(d)}</span>{render(body, k)}</div>'
            for k, lab, d in VARIANTS)
        secs.append(f'<div class="sec"><h2>{i}. {title}</h2><p class="where">{html.escape(where)}</p>{cards}'
                    + (f'<p class="note">※ {html.escape(note)}</p>' if note else "") + "</div>")
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>문장 속 종목 링크 시안</title><style>{CSS}</style></head><body><div class="wrap">
<h1>문장 속 종목 이름 링크 — 시안</h1>
<p class="lead">블로그 실제 문장 다섯 곳을 안마다 그렸습니다. 종목 이름을 눌러 보세요 — 누르는 순간 연보라 바탕이 잠깐 보이고, 아래에 어느 페이지로 가는지 뜹니다(목업이라 이동은 하지 않음).</p>
<div class="legend"><b>지금</b> 블로그 그대로<br><b>고른 안</b> 전부 링크 · 검은 굵게 · 아주 연한 회색 점선(점 2px · 간격 5px · 글자 아래 2px)<br>
공통: 자기 페이지 이름 · 소제목 · 지수(나스닥) · 우리 목록에 없는 회사는 링크 없음.</div>
{''.join(secs)}
</div><div class="toast" id="toast"></div><script>{JS}</script></body></html>"""
    path = os.path.join(OUT, "mock_stock_links.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    print(path)


if __name__ == "__main__":
    main()
