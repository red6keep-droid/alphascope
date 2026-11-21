"""주식 공부 기준 페이지 · 9편 그림 — 실제 주가와 '순서만 섞은 가짜 주가'를 나란히 (2026-11-21 사용자: 가짜 파동 설명이 어렵다 → 그림으로).

    .venv/bin/python experiments/course/make_shuffle_fig.py            # → experiments/course/figs/shuffle_quiz.html
    .venv/bin/python experiments/course/make_shuffle_fig.py MSFT 2015 1

- 한 종목 · 한 해의 하루 등락률을 그대로 쓰고 순서만 섞는다(cycle_persistence.py 의 가짜 주가와 같은 방법, 로그 수익률 permutation).
  같은 등락률을 다 더하므로 가짜 주가도 시작 · 끝이 실제와 같다.
- 종목 · 해 · 씨앗은 아래 기본값 고정 — 보기 좋은 것을 골라 가며 바꾸지 않는다(바꾸면 초안 `발행 전 확인`에 적는다).
- 렌더러(render_course.py)가 초안의 `[그림] shuffle_quiz` 줄 자리에 이 조각을 그대로 넣는다. 그림 파일이 아니라 글 안 SVG 라 따로 올릴 것이 없다.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BARS = os.path.join(HERE, "..", "..", "data", "store", "bars")
OUT = os.path.join(HERE, "figs")
SYM, YEAR, SEED = "MSFT", 2015, 1
W, H, PAD_L, PAD_R, PAD_T, PAD_B = 320, 120, 4, 58, 10, 10   # 오른쪽 58 = 마지막 값 글자 자리(점 오른쪽, 선 그래프 규칙)
LINE = "#F59E0B"   # 두 그래프 같은 색 — 색으로 어느 쪽이 실제인지 드러나지 않게. 주황 = 그래프 통일 주황 (2026-11-21 사용자 P556, 옛 #334155)


def series(sym, year, seed):
    c = pd.read_parquet(os.path.join(BARS, f"{sym}.parquet"))["close"]
    c = c[(c.index >= f"{year - 1}-12-25") & (c.index <= f"{year}-12-31")]
    c = c[c.index >= c[c.index < f"{year}-01-01"].index[-1]]   # 전해 마지막 거래일부터 — 첫날 등락도 포함
    r = np.diff(np.log(c.values))
    real = np.concatenate([[0], np.cumsum(r)])
    fake = np.concatenate([[0], np.cumsum(np.random.default_rng(seed).permutation(r))])
    return np.exp(real) * 100, np.exp(fake) * 100


def panel(name, y, lo, hi):
    n = len(y)
    px = lambda i: PAD_L + round(i / (n - 1) * (W - PAD_L - PAD_R))
    py = lambda v: PAD_T + round((hi - v) / (hi - lo) * (H - PAD_T - PAD_B))
    pts = " ".join(f"{px(i)},{py(v)}" for i, v in enumerate(y))
    base = py(100)
    end = f"{y[-1] - 100:+.0f}%"
    return (f'<div style="padding:12px 0 4px;"><span style="display:block;font-size:15px;line-height:22px;font-weight:700;color:#111;">{name}</span>'
            f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{name} 한 해 주가" style="display:block;overflow:visible;">'
            f'<line x1="{PAD_L}" y1="{base}" x2="{W - PAD_R}" y2="{base}" stroke="#CBD5E1" stroke-width="1"/>'
            f'<polyline points="{pts}" fill="none" stroke="{LINE}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{px(n - 1)}" cy="{py(y[-1])}" r="3" fill="{LINE}"/>'
            f'<text x="{px(n - 1) + 8}" y="{py(y[-1]) + 5}" font-size="14" font-weight="700" fill="#111">{end}</text></svg></div>')


def main():
    sym = sys.argv[1] if len(sys.argv) > 1 else SYM
    year = int(sys.argv[2]) if len(sys.argv) > 2 else YEAR
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else SEED
    real, fake = series(sym, year, seed)
    lo, hi = min(real.min(), fake.min()), max(real.max(), fake.max())
    body = (panel("그래프 가", fake, lo, hi) + '<div style="border-top:1px solid #E2E8F0;"></div>' + panel("그래프 나", real, lo, hi))   # 가 = 섞은 가짜 · 나 = 실제
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "shuffle_quiz.html")
    open(path, "w", encoding="utf-8").write(
        f'<div data-course-fig="shuffle_quiz" data-src="{sym} {year} seed {seed}" style="margin:24px 0 28px;padding:4px 16px;background:#F8FAFC;border-radius:12px;">{body}</div>')
    print(f"[그림] {sym} {year} seed {seed} · 거래일 {len(real) - 1} · 끝 {real[-1] - 100:+.1f}% (가짜 {fake[-1] - 100:+.1f}%) → {path}")


if __name__ == "__main__":
    main()
