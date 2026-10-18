"""S&P 500 가격 그래프 PNG — 엔비디아 chart_price.py 와 같은 모양 (30거래일 봉 + 5 · 20 · 60일선 + 볼린저), 탭 위에 놓는다
(2026-10-18 사용자: "다른 리포트처럼 상단에 S&P 500 그래프, 클릭하면 확대").

- 입력: yfinance ^GSPC 일봉 1년 (이동평균 200일까지 · 볼린저용). 기준일(analysis.as_of) 이후 바는 자른다.
- 출력: output/images/spx-price-YYYY-MM-DD.png · output/chart.json {image_ref, url, window} · output/chart_ref.txt (워크플로가 CDN 확인)
- 그림 글자는 영문 · 숫자만 (CI 우분투에 한글 폰트가 없다). 그리는 코드는 엔비디아 쪽 사본 — 모양을 바꿀 때는 두 곳을 같이 본다.
- 게시 경로: 워크플로가 output/images/*.png 를 gh-pages 에 올리고 jsDelivr 캐시를 비운다 (커버 이미지와 같은 경로).
"""

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE, "output")
SYMBOL = "^GSPC"
WINDOW = 30
MARKS = (5, 20)
CHANGE_WINDOWS = (5, 20, 60, 120)
MA_WINDOWS = (5, 20, 60, 120, 200)
UP, DOWN = "#f44336", "#2196f3"
MA_COLORS = {5: "#ff5722", 20: "#9c27b0", 60: "#2196f3"}
BOLL = "#2e7d32"
DEFAULT_REPO_SLUG = "red6keep-droid/alphascope"


def _repo_slug():
    return os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO_SLUG


def load_bars(as_of=None):
    import yfinance as yf

    df = yf.Ticker(SYMBOL).history(period="1y", interval="1d", auto_adjust=True)
    bars = []
    for ts, r in df.iterrows():
        day = ts.strftime("%Y-%m-%d")
        if as_of and day > as_of:
            continue
        if any(v != v for v in (r["Open"], r["High"], r["Low"], r["Close"])):   # NaN
            continue
        bars.append(dict(day=day, open=float(r["Open"]), high=float(r["High"]), low=float(r["Low"]), close=float(r["Close"])))
    return bars


def _sma(values, n):
    out = []
    for i in range(len(values)):
        out.append(sum(values[i - n + 1:i + 1]) / n if i >= n - 1 else None)
    return out


def _boll(values, n=20, k=2.0):
    up, lo = [], []
    for i in range(len(values)):
        if i < n - 1:
            up.append(None); lo.append(None); continue
        s = values[i - n + 1:i + 1]
        m = sum(s) / n
        sd = (sum((v - m) ** 2 for v in s) / n) ** 0.5
        up.append(m + k * sd); lo.append(m - k * sd)
    return up, lo


def ma_rel(bars):
    """현재 종가가 n일 평균선보다 몇 % 위·아래인지. 데이터가 모자라면 None."""
    closes = [b["close"] for b in bars]
    out = {}
    for n in MA_WINDOWS:
        out[n] = (closes[-1] / (sum(closes[-n:]) / n) - 1) * 100 if len(closes) >= n else None
    return out


def changes(bars):
    """CHANGE_WINDOWS 거래일 전 종가 대비 변화율 (%). 데이터가 모자라면 None."""
    closes = [b["close"] for b in bars]
    out = {}
    for n in CHANGE_WINDOWS:
        out[n] = (closes[-1] / closes[-1 - n] - 1) * 100 if len(closes) > n else None
    return out


def draw(bars, path, symbol="S&P 500"):
    if len(bars) < 2:
        raise ValueError("일봉이 부족합니다.")
    closes = [b["close"] for b in bars]
    ma = {n: _sma(closes, n) for n in MA_COLORS}
    bu, bl = _boll(closes)
    s = max(0, len(bars) - WINDOW)           # 창 시작 인덱스
    view = bars[s:]
    xs = list(range(len(view)))

    fig, ax = plt.subplots(figsize=(10.24, 4.6), dpi=100)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # 볼린저
    def seg(series):
        return [(x, series[s + x]) for x in xs if series[s + x] is not None]
    for series, ls, lw, col, label in ((bu, "--", 1.0, BOLL, "Bollinger (20, 2σ)"), (bl, "--", 1.0, BOLL, None)):
        pts = seg(series)
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], ls, lw=lw, color=col, alpha=.8, label=label)

    # 봉
    w = 0.6
    for x, b in zip(xs, view):
        col = UP if b["close"] >= b["open"] else DOWN
        ax.plot([x, x], [b["low"], b["high"]], color=col, lw=1.0)
        lo, hi = sorted((b["open"], b["close"]))
        ax.add_patch(Rectangle((x - w / 2, lo), w, max(hi - lo, closes[-1] * 0.0005), facecolor=col, edgecolor=col, lw=0))

    # 이동평균
    for n, col in MA_COLORS.items():
        pts = seg(ma[n])
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], lw=1.3, color=col, label=f"MA{n}")

    # 5·20일 전 세로선
    last = xs[-1]
    for n in MARKS:
        if last - n >= 0:
            ax.axvline(last - n, color="#999", lw=0.8, ls=(0, (2, 2)))
            ax.text(last - n, ax.get_ylim()[0], f" {n}d", va="bottom", ha="left", fontsize=8, color="#777")

    # 오른쪽 현재가 태그
    cur = view[-1]["close"]
    ax.annotate(f"{cur:,.2f}", xy=(last, cur), xytext=(last + 1.2, cur), fontsize=9, color="white", fontweight="bold",
                va="center", ha="left", bbox=dict(boxstyle="round,pad=0.25", fc=UP if view[-1]["close"] >= view[-1]["open"] else DOWN, ec="none"),
                annotation_clip=False)
    ax.axhline(cur, color="#bbb", lw=0.6, ls=(0, (1, 3)))

    # 축
    step = max(3, WINDOW // 5)
    ticks = list(range(last, -1, -step))[::-1]
    ax.set_xticks(ticks)
    ax.set_xticklabels([view[i]["day"][5:].replace("-", "/") for i in ticks], fontsize=9, color="#666")
    ax.set_xlim(-0.8, last + 4.5)
    ax.yaxis.tick_right()
    ax.tick_params(axis="y", labelsize=9, colors="#666", length=0)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color="#f0f0f0", lw=0.8)
    ax.grid(axis="x", color="#f5f5f5", lw=0.8, ls=(0, (4, 4)))
    for sp in ("top", "left", "bottom", "right"):
        ax.spines[sp].set_visible(False)

    ch = changes(bars)
    mr = ma_rel(bars)
    sub = "vs MA " + " · ".join(f"{n} {mr[n]:+.1f}%" for n in MA_WINDOWS if mr[n] is not None)
    ax.set_title(f"{symbol}  last {len(view)} trading days   {sub}", loc="left", fontsize=11, color="#111", pad=10)
    ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=4)

    fig.tight_layout()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=100)
    plt.close(fig)
    return ch


def run(day, as_of=None, output_dir=OUTPUT_DIR):
    """PNG 를 만들고 chart.json 을 쓴다. 실패하면 None — 리포트는 그래프 없이 나간다."""
    bars = load_bars(as_of)
    if len(bars) < 2:
        print("[chart] 일봉 부족 — 그래프 생략")
        return None
    image_ref = f"images/spx-price-{day}.png"
    path = os.path.join(output_dir, image_ref)
    draw(bars, path)
    url = f"https://cdn.jsdelivr.net/gh/{_repo_slug()}@gh-pages/{image_ref}"
    info = {"image_ref": image_ref, "url": url, "window": len(bars[-WINDOW:]), "last_day": bars[-1]["day"]}
    with open(os.path.join(output_dir, "chart.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False)
    with open(os.path.join(output_dir, "chart_ref.txt"), "w", encoding="utf-8") as f:
        f.write(image_ref + "\n")
    print(f"[chart] {path} · {url}")
    return info


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(run(sys.argv[1] if len(sys.argv) > 1 else "test"))
