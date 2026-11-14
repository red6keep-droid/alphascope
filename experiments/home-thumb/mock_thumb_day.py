"""홈 미국 증시 · 한국 증시 카드 그래프 — 하루(장중) 선 그래프 시안 (2026-11-14 사용자: 네이버 페이 증권 코스피 1일 화면처럼, 숫자는 잘 보이게).

    python experiments/home-thumb/mock_thumb_day.py     # output/mock_home_thumb_day.html (+ output/day_*.webp)

자료 = intraday_sample.json (목업용으로 야후 5분봉을 한 번 받아 둔 것). 실제 적용 때는 정기 실행이 장 마감 뒤 5분봉을 받아야 한다(새 수집 — 한도 표 먼저).
그림 = 선 · 면 · 기준 점선 · 최고 · 최저 점만(글자 없음). 숫자 · 시각 · 최고 · 최저 글자는 모두 카드 HTML 글자로 얹는다 — 작은 카드에서도 또렷하게.
색 = 전날 종가보다 위 빨강 · 아래 파랑(네이버와 같은 꼴, 한국 증감 색), 기준 점선 = 전날 종가.
"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import to_rgb  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
UP, DN, NOTE, INK = "#d93025", "#1a73e8", "#6B7280", "#111"
W, H, DPI = 6.8, 2.6, 200
SLOTS = 78   # 5분 칸 수 — 한국 09:00 ~ 15:30 · 미국 09:30 ~ 16:00 (6시간 30분)
START = {"^KS11": (9, 0), "^GSPC": (9, 30)}
AXIS = {"^KS11": ["09:00", "11:10", "13:20", "15:30"], "^GSPC": ["23:30", "01:40", "03:50", "06:00"]}   # 미국 = 한국 시간(겨울) — 날짜 · 시각은 한국 시간 하나로(가이드라인)


def slot(sym, hm):
    h, m = map(int, hm.split(":"))
    sh, sm = START[sym]
    return ((h * 60 + m) - (sh * 60 + sm)) / 5


def gradient_fill(ax, x, y, base, color, above):
    """선과 기준선 사이를 선 쪽이 진하고 기준선 쪽이 옅은 그라데이션으로 (네이버처럼)."""
    ys = np.where(above, np.maximum(y, base), np.minimum(y, base))
    poly = ax.fill_between(x, ys, base, color="none", linewidth=0)
    lo, hi = (base, max(y.max(), base)) if above else (min(y.min(), base), base)
    if hi - lo <= 0:
        return
    r, g, b = to_rgb(color)
    grad = np.zeros((100, 1, 4)); grad[:, 0, :3] = (r, g, b)
    a = np.linspace(0.22, 0.0, 100) if above else np.linspace(0.0, 0.22, 100)   # 위쪽 행 = hi
    grad[:, 0, 3] = a
    im = ax.imshow(grad, aspect="auto", extent=[x.min(), x.max(), lo, hi], origin="upper", zorder=1)
    im.set_clip_path(poly.get_paths()[0], transform=ax.transData)


def draw(sym, d, name):
    x = np.array([slot(sym, t) for t in d["t"]] + [SLOTS], dtype=float)   # 마지막 칸 = 장 마감(종가)까지 잇는다
    y = np.array(d["c"] + [d["c"][-1]], dtype=float)
    base = d["prev"]
    lo, hi = min(y.min(), base), max(y.max(), base)
    pad = (hi - lo) * 0.22 / (1 - 0.44)   # 위아래 각 22% = 최고 · 최저 글자 자리(그림 안에 들어가게)
    ylo, yhi = lo - pad, hi + pad
    f, ax = plt.subplots(figsize=(W, H), dpi=DPI)
    f.subplots_adjust(0, 0, 1, 1)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_xlim(0, SLOTS); ax.set_ylim(ylo, yhi)
    for gx in (SLOTS / 3, SLOTS * 2 / 3):
        ax.axvline(gx, color="#EEF1F5", linewidth=1.2, zorder=0)
    ax.axhline(base, color="#C4CBD4", linewidth=1.4, linestyle=(0, (2, 3)), zorder=2)
    # 선을 기준선에서 잘라 위 = 빨강 · 아래 = 파랑 (기준선을 지나는 점을 끼워 넣어 색이 정확히 바뀌게)
    xs, ys = [x[0]], [y[0]]
    for i in range(1, len(x)):
        if (y[i - 1] - base) * (y[i] - base) < 0:
            t = (base - y[i - 1]) / (y[i] - y[i - 1])
            xs.append(x[i - 1] + t * (x[i] - x[i - 1])); ys.append(base)
        xs.append(x[i]); ys.append(y[i])
    xs, ys = np.array(xs), np.array(ys)
    gradient_fill(ax, xs, ys, base, UP, True)
    gradient_fill(ax, xs, ys, base, DN, False)
    ax.plot(xs, np.where(ys >= base, ys, np.nan), color=UP, linewidth=2.4, zorder=3, solid_joinstyle="round")
    ax.plot(xs, np.where(ys <= base, ys, np.nan), color=DN, linewidth=2.4, zorder=3, solid_joinstyle="round")
    imin, imax = int(y.argmin()), int(y.argmax())
    for i, col in ((imin, DN), (imax, UP)):
        ax.plot([x[i]], [y[i]], "o", markersize=7, markerfacecolor="#fff", markeredgecolor=col, markeredgewidth=2, zorder=4)
    p = os.path.join(OUT, f"day_{name}.webp")
    f.savefig(p, dpi=DPI, pil_kwargs={"quality": 90})
    plt.close(f)
    fx = lambda i: x[i] / SLOTS * 100
    fy = lambda i: (yhi - y[i]) / (yhi - ylo) * 100
    return {"img": os.path.basename(p), "min": (fx(imin), fy(imin), y[imin]), "max": (fx(imax), fy(imax), y[imax])}


def fmt(v):
    return f"{v:,.2f}"


def head_vals(d):
    c, pc = d["c"][-1], d["prev"]
    ch = c - pc
    col = UP if ch > 0 else DN if ch < 0 else INK
    return c, ch, ch / pc * 100, col


def mark(pt, kind):
    """최고 · 최저 글자 — 그림 위 HTML. 점 아래(최저) · 위(최고), 오른쪽 끝에 가까우면 왼쪽으로 붙인다."""
    x, y, v = pt
    col = DN if kind == "최저" else UP
    side = "right:%.1f%%;" % (100 - x) if x > 60 else "left:%.1f%%;" % x
    shift = "translate(%s, %s)" % ("8px" if x <= 60 else "-8px" if x > 60 else "0", "6px" if kind == "최저" else "calc(-100% - 6px)")
    return (f'<span style="position:absolute;{side}top:{y:.1f}%;transform:{shift};font-size:13px;line-height:19px;color:{col};white-space:nowrap;'
            f'background:rgba(255,255,255,.8);padding:0 2px;border-radius:3px;">{kind} {fmt(v)}</span>')


def chart_html(c, axis_labels, marks=True, axis=True):
    m = (mark(c["min"], "최저") + mark(c["max"], "최고")) if marks else ""
    ax = ('<div style="display:flex;justify-content:space-between;font-size:12px;line-height:18px;color:#9CA3AF;margin:4px 0 0;font-variant-numeric:tabular-nums;">'
          + "".join(f"<span>{t}</span>" for t in axis_labels) + "</div>") if axis else ""
    return f'<div style="position:relative;"><img src="{c["img"]}" style="display:block;width:100%;height:auto;">{m}</div>{ax}'


def range52(d, c):
    lo, hi = d["y52"]
    p = max(0, min(100, (c - lo) / (hi - lo) * 100))
    return (f'<div style="margin:12px 0 0;"><div style="position:relative;height:8px;border:1px solid #CBD5E1;border-radius:2px;background:#F1F5F9;">'
            f'<span style="position:absolute;left:{p:.1f}%;top:50%;width:12px;height:12px;border-radius:50%;background:#374151;transform:translate(-50%,-50%);"></span></div>'
            f'<div style="display:flex;justify-content:space-between;margin:6px 0 0;font-size:13px;line-height:19px;color:{NOTE};"><span>1년 최저</span><span>1년 최고</span></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:15px;line-height:21px;font-weight:700;font-variant-numeric:tabular-nums;"><span>{fmt(lo)}</span><span>{fmt(hi)}</span></div></div>')


def card(title, date, inner):
    return (f'<div style="background:#fff;border:1px solid #F3F4F6;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.06);padding:16px 10px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin:0 0 10px;"><b style="font-size:17px;line-height:24px;">{title}</b>'
            f'<span style="font-size:14px;line-height:20px;color:#7A7A7A;">{date}</span></div>{inner}'
            f'<div style="margin:12px 0 0;font-size:15px;line-height:23px;color:#333;">요약 문장 두 줄이 이 자리에 들어갑니다. 지수가 어떻게 움직였는지 짧게…</div></div>')


def main():
    os.makedirs(OUT, exist_ok=True)
    data = json.load(open(os.path.join(HERE, "intraday_sample.json"), encoding="utf-8"))
    mk = {"^KS11": ("kr", "코스피", "한국 증시 리포트", "11월 13일 오후", "11월 13일 장마감"),
          "^GSPC": ("us", "S&P 500", "미국 증시 리포트", "11월 14일 아침", "11월 14일 새벽 장마감")}
    built = {}
    for sym, d in data.items():
        key, name, title, date, closed = mk[sym]
        built[sym] = (d, draw(sym, d, key), name, title, date, closed)

    def big(d, name, closed, size=26):
        c, ch, pct, col = head_vals(d)
        sg = "+" if ch > 0 else "−" if ch < 0 else ""
        return (f'<div style="font-size:13px;line-height:19px;color:{NOTE};">{name}</div>'
                f'<div style="font-size:{size}px;line-height:{size + 8}px;font-weight:800;letter-spacing:-0.3px;font-variant-numeric:tabular-nums;">{fmt(c)}</div>'
                f'<div style="font-size:16px;line-height:22px;color:{col};font-variant-numeric:tabular-nums;">{sg}{fmt(abs(ch))} ({abs(pct):.2f}%)</div>'
                f'<div style="font-size:13px;line-height:19px;color:{NOTE};margin:4px 0 8px;">{closed}</div>')

    def one(d, name):
        c, ch, pct, col = head_vals(d)
        tri = "▲" if ch > 0 else "▼" if ch < 0 else ""
        return (f'<div style="display:flex;align-items:baseline;gap:6px;flex-wrap:wrap;margin:0 0 8px;font-variant-numeric:tabular-nums;">'
                f'<span style="font-size:14px;color:{NOTE};">{name}</span><b style="font-size:21px;line-height:29px;">{fmt(c)}</b>'
                f'<span style="font-size:15px;color:{col};">{tri}{fmt(abs(ch))} {"+" if ch > 0 else "−" if ch < 0 else ""}{abs(pct):.2f}%</span></div>')

    def over(d, name, c_html):
        c, ch, pct, col = head_vals(d)
        tri = "▲" if ch > 0 else "▼" if ch < 0 else ""
        right = c_html.find("최고") >= 0 and float(c_html.split("최고")[0].rsplit("left:", 1)[-1].split("%")[0] or 100) < 50 if "left:" in c_html.split("최고")[0].rsplit("<span", 1)[-1] else False
        lab = (f'<div style="position:absolute;{"right" if right else "left"}:8px;top:6px;z-index:1;background:rgba(255,255,255,.85);border-radius:6px;padding:2px 6px;font-variant-numeric:tabular-nums;">'
               f'<b style="font-size:19px;line-height:25px;">{fmt(c)}</b> <span style="font-size:14px;color:{col};">{tri}{abs(pct):.2f}%</span></div>')
        return f'<div style="position:relative;">{lab}{c_html}</div>'

    SPECS = [
        ("G1", "네이버처럼 — 큰 숫자 + 하루 그래프 + 시각", "이름 · 큰 지수 · 전날 대비 · 장마감 날짜를 그래프 위에. 최고 · 최저는 점 옆 글자. 시각 = 한국 시간",
         lambda d, c, n, cl, ax: big(d, n, cl) + chart_html(c, ax)),
        ("G2", "한 줄 숫자 + 하루 그래프", "숫자를 한 줄로 줄여 그래프를 더 크게. 최고 · 최저 · 시각은 같음",
         lambda d, c, n, cl, ax: one(d, n) + chart_html(c, ax)),
        ("G3", "G1 + 1년 범위 막대", "네이버 52주 막대처럼 지금이 1년 최저 ~ 최고 사이 어디인지 아래에 더함",
         lambda d, c, n, cl, ax: big(d, n, cl) + chart_html(c, ax) + range52(d, d["c"][-1])),
        ("G4", "그래프 위에 숫자 얹기 (가장 작게)", "숫자를 그래프 왼쪽 위에 얹고 시각 줄을 뺌. 카드 높이가 가장 낮음",
         lambda d, c, n, cl, ax: over(d, n, chart_html(c, ax, axis=False))),
    ]
    secs = []
    for code, nm, why, fn in SPECS:
        cells = []
        for sym in ("^KS11", "^GSPC"):
            d, c, name, title, date, closed = built[sym]
            cells.append(f'<div style="flex:1 1 300px;max-width:340px;">{card(title, date, fn(d, c, name, closed, AXIS[sym]))}</div>')
        secs.append(f'<section style="margin:0 0 28px;"><h2 style="font-size:19px;line-height:27px;margin:0 0 2px;">{code}. {nm}</h2>'
                    f'<p style="font-size:14px;line-height:20px;color:{NOTE};margin:0 0 10px;">{why}</p>'
                    f'<div style="display:flex;flex-wrap:wrap;gap:12px;">{"".join(cells)}</div></section>')
    html = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>홈 카드 하루 그래프 시안 — 목업</title></head>'
            '<body style="margin:0;background:#F5F7FA;font-family:-apple-system,\'Pretendard\',\'Apple SD Gothic Neo\',sans-serif;color:#111;">'
            '<div style="max-width:720px;margin:0 auto;padding:16px;">'
            '<h1 style="font-size:21px;line-height:29px;margin:0 0 4px;">홈 카드 하루 그래프 시안</h1>'
            f'<p style="font-size:14px;line-height:20px;color:{NOTE};margin:0 0 18px;">11월 13일 실제 5분봉(야후)으로 그렸습니다. 그림엔 선 · 면 · 점만, 숫자 · 시각 · 최고 · 최저는 카드 글자입니다. '
            '빨강 = 전날 종가보다 위, 파랑 = 아래, 점선 = 전날 종가.</p>'
            + "".join(secs) + "</div></body></html>")
    with open(os.path.join(OUT, "mock_home_thumb_day.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("만듦:", os.path.join(OUT, "mock_home_thumb_day.html"))


if __name__ == "__main__":
    main()
