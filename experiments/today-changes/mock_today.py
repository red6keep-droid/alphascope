"""오늘 달라진 것 — 목업 (기획: 비공개 doc/기획/컨설팅/오늘-달라진-것-기획.md, 2026-11-22 사용자: "목업에 먼저 배치해 봐, 내가 판단").

    .venv/bin/python experiments/today-changes/today_changes.py --state …   # 먼저 output/today_us.json · today_kr.json
    .venv/bin/python experiments/today-changes/mock_today.py                # → output/mock_today_home_us.html · _kr.html · mock_today_report_us.html · _kr.html

홈 = 기존 홈 목업(experiments/home-split/output/mock_home_*.html) 맨 위에 카드 한 칸을 끼운다 — 테마 원본은 건드리지 않는다(판단 뒤 테마로).
리포트 = 증시 리포트 글 첫 구획 자리 꼴(전부 싣고 5개 펼침 + 나머지 접기).
미국 · 한국은 따로(각자 화면 · 각자 리포트).
"""
import datetime as dt
import html as _h
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "output")
sys.path.insert(0, os.path.join(ROOT, "experiments"))
import design_kit as dk  # noqa: E402

SHOW = 5
KIND_INK = {"결과": ("#F5F3FF", "#DDD6FE", "#6D28D9"), "상태": ("#F8FAFC", "#E2E8F0", "#334155"), "일정": ("#F8FAFC", "#E2E8F0", "#334155")}
ICON = ('<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M8 2.5L13.5 13h-11z"/></svg>')   # 삼각형(Δ = 달라짐)


def esc(s):
    return _h.escape(str(s))


def paint(text):
    """▲ · ▼ 가 든 값에 방향 색 — 오름 빨강 · 내림 파랑(가이드라인)."""
    out = []
    for part in str(text).split(" "):
        c = dk.UP if "▲" in part else dk.DOWN if "▼" in part else None
        out.append(f'<span style="color:{c};white-space:nowrap;">{esc(part)}</span>' if c else esc(part))
    return " ".join(out)


def asof(j):
    d = dt.date.fromisoformat(j["day"])
    if j["market"] == "us":   # 미국 종가 = 한국 다음 날 아침 (날짜는 한국 시간 하나로)
        d += dt.timedelta(days=1)
        return f"{d:%m.%d} 아침"
    return f"{d:%m.%d} 오후"


def row(r, members_all=False):
    pill = ""
    if r["kind"] in KIND_INK:
        bg, bd, ink = KIND_INK[r["kind"]]
        pill = (f'<span style="flex:none;padding:1px 6px;border:1px solid {bd};border-radius:4px;background:{bg};'
                f'font-size:12px;line-height:18px;font-weight:600;color:{ink};white-space:nowrap;">{esc(r["kind"])}</span>')
    mem = ""
    ms = r.get("members") or []
    if ms:
        shown = ms if members_all else ms[:3]
        txt = " · ".join(f'{esc(m["name"])} {paint(m["change"])}' for m in shown)
        more = "" if members_all or len(ms) <= 3 else f" 외 {len(ms) - 3}종목"
        mem = f'<div style="font-size:13px;line-height:19px;color:{dk.SUB};word-break:keep-all;">{txt}{more}</div>'
    cmp_ = f'<div style="font-size:13px;line-height:19px;color:{dk.SUB};word-break:keep-all;">{paint(r["cmp"])}</div>' if r.get("cmp") else ""
    chev = '<span aria-hidden="true" style="flex:none;color:#333;font-size:18px;line-height:24px;">›</span>'
    return (f'<a href="{esc(r["href"])}" data-today-row="1" style="display:flex;align-items:flex-start;gap:8px;padding:10px 0;border-top:1px solid #EEF2F6;text-decoration:none;color:#111;">'
            f'<span style="flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:2px;">'
            f'<span style="display:flex;flex-wrap:wrap;align-items:center;gap:2px 8px;font-size:16px;line-height:24px;">{pill}'
            f'<b style="font-weight:700;word-break:keep-all;">{esc(r["what"])}</b><span style="font-weight:400;">{paint(r["change"])}</span></span>'
            f'{cmp_}{mem}</span>{chev}</a>')


def rows_html(j, members_all=False):
    rs = j["rows"]
    if not rs:
        return f'<div style="padding:10px 0;font-size:16px;line-height:24px;color:#111;">오늘은 평소 범위입니다. 크게 달라진 것이 없습니다.</div>'
    head = "".join(row(r, members_all) for r in rs[:SHOW]).replace("border-top:1px solid #EEF2F6;", "", 1)
    rest = rs[SHOW:]
    if not rest:
        return head
    more = (f'<details style="margin:0;"><summary style="list-style:none;cursor:pointer;padding:10px 0 2px;border-top:1px solid #EEF2F6;font-size:14px;line-height:20px;font-weight:600;color:#333;">'
            f'+ {len(rest)}개 더 보기</summary>' + "".join(row(r, members_all) for r in rest) + '</details>')
    return head + more


def home_card(j):
    """홈 맨 위 카드 한 칸 — 기존 카드(.report-col · .report-title · .report-card)와 같은 틀."""
    return ('<div class="report-col" id="today-col">'
            f'<h3 class="report-title"><span class="report-icon" style="background:#334155;" aria-hidden="true">{ICON}</span>오늘 달라진 것'
            f'<span class="report-card-date">{asof(j)}</span></h3>'
            f'<div class="report-card" style="display:block;padding:6px 16px;cursor:default;">{rows_html(j)}</div></div>')


def home(mkt, j):
    src = os.path.join(ROOT, "experiments", "home-split", "output", f"mock_home_{mkt}.html")
    t = open(src, encoding="utf-8").read()
    key = '<div class="report-col" id="us-report-col">'
    if key not in t:
        sys.exit("홈 목업에서 끼울 자리를 못 찾음")
    t = t.replace(key, home_card(j) + key, 1)
    for a, b in (("mock_home_us.html", "mock_today_home_us.html"), ("mock_home_kr.html", "mock_today_home_kr.html")):   # 미국 · 한국 전환도 새 목업끼리
        t = t.replace(f'href="{a}"', f'href="{b}"')
    p = os.path.join(OUT, f"mock_today_home_{mkt}.html")
    open(p, "w", encoding="utf-8").write(t)
    return p


def report(mkt, j):
    nm = "미국 증시 리포트" if mkt == "us" else "한국 증시 리포트"
    note = dk.muted("평소 = 직전 60거래일의 하루 움직임입니다. 업종 · 종목은 지수와 견준 움직임이 평소보다 뚜렷하게 컸을 때만 싣습니다.")
    body = (f'<div data-head-title="{nm}">'
            + dk.section("오늘 달라진 것", f'<div style="padding:0 {dk.ALIGN_PX}px;">{rows_html(j, members_all=True)}</div>' + note, line=False)
            + f'<div style="margin:28px 0;padding:16px;border:1px dashed #CBD5E1;border-radius:8px;font-size:14px;line-height:20px;color:{dk.SUB};">'
              '목업 안내 : 이 아래로 지금 증시 리포트 내용이 그대로 이어집니다.</div></div>')
    p = os.path.join(OUT, f"mock_today_report_{mkt}.html")
    dk.write_mock(body, p, f"오늘 달라진 것 — {nm} 첫 구획")
    return p


if __name__ == "__main__":
    for m in ("us", "kr"):
        j = json.load(open(os.path.join(OUT, f"today_{m}.json"), encoding="utf-8"))
        print(home(m, j))
        print(report(m, j))
