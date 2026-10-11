"""가격 패널 PNG — 30거래일 봉차트 + 5·20·60일선 + 볼린저 (2026-10-11 사용자: 표를 그래프로, 5·20·30일 누적 방향).

모양은 graph-v1 앱(Expo, Victory Native)의 규칙을 따른다: 상승 빨강 #f44336 · 하락 파랑 #2196f3,
5일선 주황 #ff5722 · 20일선 보라 #9c27b0 · 60일선 파랑 #2196f3 · 볼린저 초록 점선 #2e7d32, 오른쪽 현재가 태그.
정적 그림이라 기간 버튼 대신 30일 창 하나에 5일·20일 전 지점을 세로선으로 긋고, 그 아래 5·20·30일 변화를 표로 붙인다.

- 입력: daily_bars(NVDA). 이동평균·볼린저는 창 앞 60일을 더 읽어 계산한다.
- 출력: output/images/nvda-price-YYYY-MM-DD.png · 반환 dict(image_ref, url, changes) — render_html이 ① 아래에 넣는다.
- 글자는 영문·숫자만 (CI 우분투에 한글 폰트가 없다). 한글 설명은 HTML 쪽에서.
- 게시 경로: 워크플로가 output/images/*.png 를 gh-pages 에 올리고 jsDelivr 캐시를 비운 뒤 Blogger 게시 (daily-report 커버와 같은 경로).
"""

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

import config  # noqa: E402

WINDOW = 30            # 보이는 거래일
MARKS = (5, 20)        # 세로선: n거래일 전
LOOKBACK = 60          # 지표 계산용 추가 일수
UP, DOWN = "#f44336", "#2196f3"
MA_COLORS = {5: "#ff5722", 20: "#9c27b0", 60: "#2196f3"}
BOLL = "#2e7d32"
DEFAULT_REPO_SLUG = "red6keep-droid/alphascope"


def _repo_slug():
    return os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO_SLUG


def load_bars(conn, symbol="NVDA", n=WINDOW + LOOKBACK):
    rows = conn.execute("SELECT day, open, high, low, close, volume FROM daily_bars WHERE symbol=? ORDER BY day DESC LIMIT ?",
                        (symbol, n)).fetchall()
    return [dict(day=r[0], open=r[1], high=r[2], low=r[3], close=r[4], volume=r[5]) for r in reversed(rows)]


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


def changes(bars):
    """5·20·30거래일 전 종가 대비 변화율 (%). 데이터가 모자라면 None."""
    closes = [b["close"] for b in bars]
    out = {}
    for n in (5, 20, 30):
        out[n] = (closes[-1] / closes[-1 - n] - 1) * 100 if len(closes) > n else None
    return out


def draw(bars, path, symbol="NVDA"):
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
    sub = " · ".join(f"{n}d {ch[n]:+.1f}%" for n in (5, 20, 30) if ch[n] is not None)
    ax.set_title(f"{symbol} — last {len(view)} trading days   {sub}", loc="left", fontsize=11, color="#111", pad=10)
    ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=4)

    fig.tight_layout()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=100)
    plt.close(fig)
    return ch


def run(conn, day, symbol="NVDA"):
    """PNG를 만들고 {image_ref, url, changes, path} 를 돌려준다. 일봉이 없으면 None."""
    bars = load_bars(conn, symbol)
    if len(bars) < 2:
        print("[chart] 일봉 부족 — 그래프 생략")
        return None
    image_ref = f"images/nvda-price-{day}.png"
    path = os.path.join(config.OUTPUT_DIR, image_ref)
    ch = draw(bars, path, symbol)
    url = f"https://cdn.jsdelivr.net/gh/{_repo_slug()}@gh-pages/{image_ref}"
    with open(os.path.join(config.OUTPUT_DIR, "image_ref.txt"), "w", encoding="utf-8") as f:
        f.write(image_ref)
    with open(os.path.join(config.OUTPUT_DIR, "chart.json"), "w", encoding="utf-8") as f:
        json.dump({"image_ref": image_ref, "url": url, "changes": {str(k): v for k, v in ch.items()}, "window": len(bars[-WINDOW:])}, f, ensure_ascii=False)
    print(f"[chart] {path} · {url} · " + " · ".join(f"{n}d {v:+.1f}%" for n, v in ch.items() if v is not None))
    return {"image_ref": image_ref, "url": url, "path": path, "changes": ch, "bars": len(bars)}


if __name__ == "__main__":
    import sys
    import db
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    conn = db.connect()
    day = conn.execute("SELECT max(day) FROM daily_bars WHERE symbol='NVDA'").fetchone()[0]
    print(run(conn, day))
