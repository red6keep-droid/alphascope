"""브랜드 `AlphaScope` 로고 꼴 시안.
    .venv/bin/python experiments/design-samples/build_brand.py  → output/mock_brand.html
자리마다 둘레 글자 크기와 브랜드 크기(둘레 − 2)를 나란히 놓는다. 옛 표기(굵게만 · 띄어 쓰기)와 비교."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "nvda-report"))
import design_kit as dk  # noqa: E402
import render_html as R  # noqa: E402

M = R.brand_mark
OLD_LOGO = R.BLOG_LOGO.replace('display:block;', 'display:inline-block;vertical-align:-3px;margin-right:6px;', 1).replace('width="18" height="16"', 'width="21" height="19"', 1)
TITLE_NEW = (f'<span style="font-size:18px;font-weight:700;">{OLD_LOGO}<span data-brand-font="title" style="{R.BRAND_FONT}font-size:17px;">Newfact</span> 신호는?</span>')
ROWS = [   # (자리, 새 꼴 html, 옛 꼴 html) — 문장 속만 로고 꼴(로고 + 900 · 둘레 − 2), 카드 질문은 크기 그대로 · 글꼴만
    ("강조 카드 질문 (18) — 크기 · 로고 그대로, 글꼴만", TITLE_NEW,
     f'<span style="font-size:18px;font-weight:700;">{OLD_LOGO}<span style="font-size:17px;">Newfact</span> 신호는?</span>'),
    ("맨 앞 요약 · 본문 (19)", f'<span style="font-size:19px;line-height:35px;color:#333;">주가는 최근 며칠 ▼ 내렸고, {M(19)} 신호는 중립입니다.</span>',
     '<span style="font-size:19px;line-height:35px;color:#333;">주가는 최근 며칠 ▼ 내렸고, 가격 흐름(Newfact 신호)은 중립입니다.</span>'),
    ("카드 안 문장 (16)", f'<span style="font-size:16px;color:#333;">{M(16)} 사건표의 휴전 · 종전 날 3번입니다.</span>',
     '<span style="font-size:16px;color:#333;">Newfact 사건표의 휴전 · 종전 날 3번입니다.</span>'),
    ("작은 회색 안내 (14) — 15 이하 · 출처 · 툴팁은 글자 그대로", '<span style="font-size:14px;color:#7A7A7A;">시장에서 흔히 쓰는 설명입니다. Newfact의 주장은 아닙니다.</span>',
     '<span style="font-size:14px;color:#7A7A7A;">시장에서 흔히 쓰는 설명입니다. Newfact의 주장은 아닙니다.</span>'),
]
home = R.BLOG_LOGO.replace('width="18" height="16"', 'width="36" height="33"', 1).replace("display:block;", "display:inline-block;vertical-align:middle;margin-right:8px;", 1)
cell = "padding:14px 12px;border-bottom:1px solid #EEE;vertical-align:middle;"
body = (f'<div style="margin:0 0 20px;"><div style="font-size:14px;color:#7A7A7A;margin-bottom:6px;">기준 = 홈 로고 (로고 36 × 33 · 글자 22 · Noto Sans KR 900)</div>'
        f'{home}<span data-brand-font="title" style="{R.BRAND_FONT}font-size:22px;vertical-align:middle;">Newfact</span></div>'
        '<table style="width:100%;border-collapse:collapse;"><tr style="font-size:14px;color:#7A7A7A;"><th style="text-align:left;padding:6px 12px;">자리</th><th style="text-align:left;padding:6px 12px;">새 꼴</th><th style="text-align:left;padding:6px 12px;">지금 · 옛 꼴</th></tr>'
        + "".join(f'<tr><td style="{cell}font-size:14px;color:#555;white-space:nowrap;">{a}</td><td style="{cell}">{n}</td><td style="{cell}">{o}</td></tr>' for a, n, o in ROWS)
        + '</table><p style="font-size:14px;color:#7A7A7A;margin-top:16px;">툴팁은 글자만 보이는 자리라 로고 · 글꼴을 넣을 수 없습니다 — `Newfact` 글자만.</p>')
out = os.path.join(HERE, "output", "mock_brand.html")
os.makedirs(os.path.dirname(out), exist_ok=True)
dk.write_mock(body, out, "브랜드 표기 시안") or open(out, "w").write(f'<!doctype html><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap" rel="stylesheet"><body style="font-family:Noto Sans KR;padding:16px;">{body}')
print(out)
