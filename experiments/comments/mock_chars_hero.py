"""캐릭터 소개 시안 B — 캐릭터 10명 그림을 동물 판(a) 대신 히어로 판(p)으로.

mock_comments.py 의 소개 페이지를 그대로 쓰고 그림 · 종류만 바꾼다(그 파일은 고치지 않음).
공주(p03) · 왕(p11)은 머리에 왕관이 있어 캐릭터 표시(이름 옆 왕관)와 헷갈리므로 뺀다 → 남은 10장 = 10명.
  python experiments/comments/mock_chars_hero.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mock_comments as M  # noqa: E402

NAME = "mock_comments_characters-hero.html"
# 이름 → (그림, 종류, 왜 이 짝)
HERO = {
    "기록이": ("p01", "로봇", "다 기억하고 날짜를 붙여 꺼냄"),
    "견줌이": ("p07", "요원", "의심 많고 나란히 놓고 확인"),
    "실적이": ("p09", "바이킹", "듬직하고 잘 안 놀람"),
    "물결이": ("p02", "가면 히어로", "반응이 제일 빠름"),
    "엇박이": ("p04", "선글라스 고양이", "삐딱하지만 예의 바름"),
    "새싹이": ("p05", "외계인", "여기 온 지 얼마 안 돼 말뜻을 물음"),
    "돈길이": ("p12", "공룡", "여유 있고 꾸준함"),
    "채점이": ("p08", "마녀", "적어 둔 쪽지를 판정일에 펼침"),
    "소식이": ("p10", "토끼 귀 소녀", "큰 귀로 들은 대로만 전함"),
    "이음이": ("p06", "우주인", "밤(미국)과 낮(한국)을 오감"),
}
OLD = {c[0]: (c[1], c[2]) for c in M.CHARS}


def compare():
    rows = "".join(
        f'<tr><td style="padding:6px 8px 6px 0;font-weight:700;white-space:nowrap;">{n}</td>'
        f'<td style="padding:6px 8px;"><img src="{M.ava_src(OLD[n][0])}" alt="" width="40" height="40" style="display:block;border-radius:50%;"></td>'
        f'<td style="padding:6px 8px;color:#6B7280;white-space:nowrap;">{OLD[n][1]}</td>'
        f'<td style="padding:6px 8px;"><img src="{M.ava_src(h[0])}" alt="" width="40" height="40" style="display:block;border-radius:50%;"></td>'
        f'<td style="padding:6px 0 6px 8px;"><b>{h[1]}</b><br><small style="color:#6B7280;">{h[2]}</small></td></tr>'
        for n, h in HERO.items())
    left = "".join(f'<img src="{M.ava_src(k)}" alt="" width="40" height="40" style="border-radius:50%;margin-right:6px;">' for k in ("p03", "p11"))
    return ('<div style="border:2px dashed #F59E0B;border-radius:12px;padding:12px 14px;margin:0 0 20px;">'
            '<p style="margin:0 0 8px;font-size:15px;line-height:24px;color:#92400E;font-weight:700;">시안 B — 캐릭터 그림 = 히어로 판 (시안 A = 지금 동물 판)</p>'
            '<table style="border-collapse:collapse;font-size:15px;line-height:22px;"><thead><tr style="color:#6B7280;font-size:13px;">'
            '<th></th><th colspan="2" style="text-align:left;padding:0 8px;">A 동물</th><th colspan="2" style="text-align:left;padding:0 8px;">B 히어로</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
            f'<p style="margin:10px 0 0;font-size:14px;line-height:22px;color:#6B7280;">{left}<br>캐릭터에서 뺀 둘(공주 · 왕) — 머리 왕관이 캐릭터 왕관 표시와 겹침</p></div>')


M.CHARS = [(n, HERO[n][0], HERO[n][1], sees, intro, flow) for n, _, _, sees, intro, flow in M.CHARS]
M.CHAR = {c[0]: c for c in M.CHARS}
M.CHAR_AVAS = {c[1] for c in M.CHARS}
_page = M.chars_page
M.chars_page = lambda: _page().replace('<p class="cv-ch-top">', compare() + '<p class="cv-ch-top">', 1)
M.TITLES[NAME] = "Newfact 캐릭터 소개 — 시안 B 히어로 그림"

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    M.build_chars(NAME)
