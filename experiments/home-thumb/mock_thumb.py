"""홈 미국 증시 · 한국 증시 카드 그래프(썸네일) 시안 목업 (2026-11-14 사용자: "썸네일이라 글씨가 하나도 안 보인다 — 시안을 보고 결정").

    python experiments/home-thumb/mock_thumb.py     # output/mock_home_thumb.html (+ output/thumb_*.webp)

자료 = 저장소에 받아 둔 일봉(kr-stocks · stock-radar data/snapshot.json) — 인터넷 없이. 미국은 S&P 500 대신 SPY 일봉(모양은 같다).
시안마다 실제 홈 카드 폭(폰 340 · PC 300)에 넣어 본다. 그림 안 글자는 모두 빼고, 꼭 필요한 숫자는 그림 밖 HTML 글자로(작아도 또렷하게).
"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
OUT = os.path.join(HERE, "output")
UP, DN, FLAT, MA20, GRID, NOTE = "#d93025", "#1a73e8", "#9CA3AF", "#E5534B", "#ECF0F5", "#6B7280"
MAIN, MAIN_FILL = "#F59E0B", "#FEF3C7"   # 가이드라인 그래프 색 ② 주인공 수준 값 = 주황(dk.CHART_MAIN) — 지수 수준 선
W, H, DPI = 6.8, 3.0, 200   # 그림 비율 = 지금 카드 그림(10.24 × 4.6)과 비슷한 2.27 : 1


def load():
    kr = json.load(open(os.path.join(EXP, "kr-stocks", "data", "snapshot.json"), encoding="utf-8"))["bars"]["^KS11"]
    us = json.load(open(os.path.join(EXP, "stock-radar", "data", "snapshot.json"), encoding="utf-8"))["bars"]["SPY"]
    clean = lambda bars: [b for b in bars if b.get("close")]
    return {"kr": ("코스피", clean(kr)), "us": ("S&P 500", clean(us))}


def sma(c, n):
    return [sum(c[i - n + 1:i + 1]) / n if i >= n - 1 else None for i in range(len(c))]


def fig():
    f, ax = plt.subplots(figsize=(W, H), dpi=DPI)
    f.subplots_adjust(0.01, 0.04, 0.99, 0.96)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])
    return f, ax


def candles(ax, bars, width=0.6):
    for i, b in enumerate(bars):
        o, h, l, c = b.get("open") or b["close"], b["high"] or b["close"], b["low"] or b["close"], b["close"]
        col = FLAT if c == o else UP if c > o else DN
        ax.vlines(i, l, h, color=col, linewidth=1.4)
        ax.add_patch(plt.Rectangle((i - width / 2, min(o, c)), width, max(abs(c - o), (h - l) * 0.01 or 1e-9), color=col, linewidth=0))
    ax.set_xlim(-0.8, len(bars) - 0.2)


def save(f, name):
    p = os.path.join(OUT, name)
    f.savefig(p, dpi=DPI, pil_kwargs={"lossless": False, "quality": 90})
    plt.close(f)
    return name


def draw_all(key, label, bars):
    names = {}
    c = [b["close"] for b in bars]
    # B 봉만 30일
    b30 = bars[-30:]
    f, ax = fig(); candles(ax, b30)
    lo, hi = min(b["low"] or b["close"] for b in b30), max(b["high"] or b["close"] for b in b30)
    ax.set_ylim(lo - (hi - lo) * 0.06, hi + (hi - lo) * 0.06)
    names["B"] = save(f, f"thumb_{key}_B.webp")
    # C 봉 30일 + 20일선 하나 + 마지막 종가 가로 점선
    f, ax = fig(); candles(ax, b30)
    m = sma(c, 20)[-30:]
    ax.plot(range(30), m, color=MA20, linewidth=2)
    ax.axhline(c[-1], color=UP if c[-1] >= c[-2] else DN, linewidth=1, linestyle=(0, (2, 2)))
    ax.set_ylim(lo - (hi - lo) * 0.06, hi + (hi - lo) * 0.06)
    names["C"] = save(f, f"thumb_{key}_C.webp")
    # D 3개월 종가 선 + 아래 면 (기간 증감 색) + 시작 기준 점선
    c60 = c[-63:]
    col = MAIN
    f, ax = fig()
    lo2, hi2 = min(c60), max(c60)
    base = lo2 - (hi2 - lo2) * 0.15
    ax.plot(range(len(c60)), c60, color=col, linewidth=2.6, solid_capstyle="round")
    ax.fill_between(range(len(c60)), c60, base, color=MAIN_FILL, linewidth=0)
    ax.axhline(c60[0], color=FLAT, linewidth=1, linestyle=(0, (2, 2)))
    ax.plot([len(c60) - 1], [c60[-1]], "o", color=col, markersize=6)
    ax.set_ylim(base, hi2 + (hi2 - lo2) * 0.08); ax.set_xlim(-1, len(c60) + 1)
    names["D"] = save(f, f"thumb_{key}_D.webp")
    # F 1년 종가 선 + 1년 고점 · 저점 가로 띠 (지금 어디쯤인지)
    c1 = c[-252:]
    col1 = MAIN
    f, ax = fig()
    lo3, hi3 = min(c1), max(c1)
    ax.axhspan(lo3, hi3, color="#F1F5F9", linewidth=0)
    ax.plot(range(len(c1)), c1, color=col1, linewidth=2.2)
    ax.plot([len(c1) - 1], [c1[-1]], "o", color=col1, markersize=6)
    ax.set_ylim(lo3 - (hi3 - lo3) * 0.08, hi3 + (hi3 - lo3) * 0.08); ax.set_xlim(-2, len(c1) + 3)
    names["F"] = save(f, f"thumb_{key}_F.webp")
    return names


def head(label, bars):
    c = [b["close"] for b in bars]
    d = (c[-1] / c[-2] - 1) * 100
    col = UP if d > 0 else DN if d < 0 else "#111"
    tri = "▲" if d > 0 else "▼" if d < 0 else ""
    return c[-1], d, col, tri


def card(title, img, overlay="", note=""):
    ov = (f'<div style="position:absolute;left:10px;top:8px;font-size:15px;line-height:21px;font-weight:700;color:#111;'
          f'background:rgba(255,255,255,.85);border-radius:6px;padding:2px 6px;">{overlay}</div>') if overlay else ""
    return (f'<div style="background:#fff;border:1px solid #F3F4F6;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.06);padding:16px 10px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin:0 0 10px;"><b style="font-size:17px;line-height:24px;">{title}</b>'
            f'<span style="font-size:14px;line-height:20px;color:#7A7A7A;">11월 14일 아침</span></div>'
            f'<div style="position:relative;">{ov}<img src="{img}" style="display:block;width:100%;height:auto;border:1px solid #eee;border-radius:8px;"></div>'
            f'<div style="margin:10px 0 0;font-size:15px;line-height:23px;color:#333;">요약 문장 두 줄이 이 자리에 들어갑니다. 지수가 어떻게 움직였는지 짧게…</div>'
            f'{note}</div>')


def main():
    os.makedirs(OUT, exist_ok=True)
    data = load()
    # A 지금 그림 = 그대로 (한국 = 저장소의 최근 그림, 미국 = 같은 코드로 SPY)
    import sys
    sys.path.insert(0, os.path.join(EXP, "nvda-report"))
    import chart_price as CS
    rows = []
    SPECS = [
        ("A", "지금 그림", "봉 30일 · 이동평균 3개 · 볼린저 · 영문 제목 · 범례 · 날짜 · 가격 눈금 — 카드 크기에선 글자가 안 읽힘"),
        ("B", "봉만 (30일)", "글자 · 선 모두 뺌. 최근 한 달 오르내림 모양만"),
        ("C", "봉 + 20일선 + 오늘 종가 점선", "봉에 선 하나와 오늘 위치만 더함. 글자 없음"),
        ("D", "3개월 선 그래프 + 면", "작은 크기에서 가장 잘 읽히는 꼴. 선 = 주황(그래프 규칙: 지수 수준 = 주인공 주황), 점선 = 3개월 전 값, 점 = 오늘"),
        ("E", "D + 그림 위 HTML 글자", "그림 안 글자 대신 그림 위에 또렷한 HTML 글자(지수 · 오늘 등락). 글자는 그림이 아니라 카드 글자라 작아져도 선명"),
        ("F", "1년 선 + 1년 범위 띠", "회색 띠 = 1년 최고 ~ 최저. 지금이 1년 범위의 어디쯤인지 한눈에. 글자 없음"),
    ]
    for key, (label, bars) in data.items():
        names = draw_all(key, label, bars)
        a = f"thumb_{key}_A.webp"
        CS.draw([b for b in bars if b.get("open")][-(30 + 200):], os.path.join(OUT, a), symbol="KOSPI" if key == "kr" else "S&P 500")
        names["A"] = a
        names["E"] = names["D"]
        v, d, col, tri = head(label, bars)
        lvl = f" {v:,.2f}" if key == "kr" else ""   # 미국 견본은 SPY 라 지수 값은 빼고 등락만
        rows.append((key, label, names, f'{label}{lvl} <span style="color:{col};">{tri}{abs(d):.2f}%</span>'))
    title = {"kr": "한국 증시 리포트", "us": "미국 증시 리포트"}
    sec = []
    for code, name, why in SPECS:
        cells = []
        for key, label, names, ov in rows:
            cells.append(f'<div style="flex:1 1 300px;max-width:340px;">{card(title[key], names[code], ov if code == "E" else "")}</div>')
        sec.append(f'<section style="margin:0 0 28px;"><h2 style="font-size:19px;line-height:27px;margin:0 0 2px;">{code}. {name}</h2>'
                   f'<p style="font-size:14px;line-height:20px;color:{NOTE};margin:0 0 10px;">{why}</p>'
                   f'<div style="display:flex;flex-wrap:wrap;gap:12px;">{"".join(cells)}</div></section>')
    html = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>홈 카드 그래프 시안 — 목업</title></head>'
            '<body style="margin:0;background:#F5F7FA;font-family:-apple-system,\'Pretendard\',\'Apple SD Gothic Neo\',sans-serif;color:#111;">'
            '<div style="max-width:720px;margin:0 auto;padding:16px;">'
            '<h1 style="font-size:21px;line-height:29px;margin:0 0 4px;">홈 카드 그래프 시안</h1>'
            f'<p style="font-size:14px;line-height:20px;color:{NOTE};margin:0 0 18px;">실제 홈 카드 폭(폰 약 340px)에 넣어 본 모습입니다. 자료 = 저장소에 받아 둔 일봉(미국은 S&amp;P 500 대신 SPY — 모양은 같음).</p>'
            + "".join(sec) + "</div></body></html>")
    with open(os.path.join(OUT, "mock_home_thumb.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("만듦:", os.path.join(OUT, "mock_home_thumb.html"))


if __name__ == "__main__":
    main()
