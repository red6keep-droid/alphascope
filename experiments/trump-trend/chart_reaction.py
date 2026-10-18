"""과거 반응 그래프 PNG — 주제 × 구간(당일·5일)마다 한 장 (2026-10-11 사용자: "당일 변화와 5일 동안 변화 그래프, 탭으로 연결").

trump_analysis.json 의 reactions → output/images/trump-reaction-{day}-{주제}-{구간}.png, output/reaction_charts.json.
한 줄 = 자산 하나. 막대 = 발언 뒤 S&P 500(SPY) 대비 평균 초과 수익률. 회색 띠 = 발언 없는 날에서 같은 수를 뽑았을 때 평균의 95% 범위
(aggregate._placebo 의 band_lo/hi). 진한 막대 = 다중 검정 보정 뒤에도 남은 것(robust), 나머지는 옅게.
그림 안 글자는 영문·숫자만 (CI 우분투에 한글 글꼴 없음) — 한글 설명은 렌더러의 글머리표에.
"""

import json
import os
import re
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import config  # noqa: E402

HORIZONS = {"close": "Same day", "d5": "+5 trading days"}
DIRECTIONS = (("negative", "negative posts"), ("positive", "positive posts"), ("", "all posts"))   # 그룹 키 "주제#방향", "" = 전체
UP, DOWN = "#d93025", "#1a73e8"


def _repo_slug():
    slug = os.environ.get("GITHUB_REPOSITORY")
    if slug:
        return slug
    try:
        url = subprocess.run(["git", "config", "--get", "remote.origin.url"], capture_output=True, text=True, check=True).stdout.strip()
        m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
        if m:
            return m.group(1)
    except Exception:  # noqa: BLE001
        pass
    return "red6keep-droid/alphascope"


def rows_for(blk, horizon):
    """(자산, 평균, 띠 아래, 띠 위, robust, q, n) — 게시 가능한 것만, ALL_SYMBOLS 순서."""
    out = []
    for sym in config.ALL_SYMBOLS:
        st = (blk["symbols"].get(sym) or {}).get(horizon)
        if not st or not st.get("publishable"):
            continue
        pl = st.get("placebo") or {}
        out.append({"sym": sym, "mean": st["mean"], "lo": pl.get("band_lo"), "hi": pl.get("band_hi"),
                    "robust": bool(pl.get("robust")), "q": pl.get("q_bh"), "p": pl.get("p_two_sided"), "n": st["n"]})
    return out


def draw(rows, title, path):
    n = len(rows)
    fig, ax = plt.subplots(figsize=(7.2, 0.42 * n + 1.3))
    ys = list(range(n))[::-1]
    for y, r in zip(ys, rows):
        if r["lo"] is not None:
            ax.add_patch(plt.Rectangle((r["lo"], y - 0.38), r["hi"] - r["lo"], 0.76, color="#EEF2F6", zorder=0))
        col = UP if r["mean"] > 0 else DOWN
        ax.barh(y, r["mean"], height=0.55, color=col, alpha=1.0 if r["robust"] else 0.28, zorder=2)
        if r["robust"]:
            ax.text(r["mean"] + (0.05 if r["mean"] > 0 else -0.05), y, f"{r['mean']:+.2f}%", va="center",
                    ha="left" if r["mean"] > 0 else "right", fontsize=10, color=col, fontweight="bold", zorder=3)
    ax.axvline(0, color="#94A3B8", lw=0.8)
    ax.set_yticks(ys)
    ax.set_yticklabels([r["sym"] for r in rows], fontsize=10)
    ax.set_title(title, fontsize=11, loc="left", color="#334155")
    ax.set_xlabel("avg excess return vs SPY (%)", fontsize=9, color="#475569")
    lim = max([abs(r["mean"]) for r in rows] + [abs(r["lo"] or 0) for r in rows] + [abs(r["hi"] or 0) for r in rows] + [0.5]) * 1.25
    ax.set_xlim(-lim, lim)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def topics_for(a):
    """리포트에 내는 주제 — render_html.sec_reactions 와 같은 고르기 (오늘 이벤트 주제, 없으면 관측 많은 셋)."""
    keys = []
    for e in a["recent_events"]:
        if e["topic"] not in keys:
            keys.append(e["topic"])
    return keys or sorted((k for k in a["reactions"] if "#" not in k and " / " not in k), key=lambda k: -a["reactions"][k]["counts"]["clean"])[:3]


def run(analysis=None, day=None):
    if analysis is None:
        with open(os.path.join(config.OUTPUT_DIR, "trump_analysis.json"), "r", encoding="utf-8") as f:
            analysis = json.load(f)
    day = day or (analysis.get("data_status") or {}).get("bars_last_day") or "latest"
    slug = _repo_slug()
    out, refs = {}, []
    for topic in topics_for(analysis):
        for d, dlabel in DIRECTIONS:
            gkey = f"{topic}#{d}" if d else topic
            blk = analysis["reactions"].get(gkey)
            if not blk:
                continue
            for h, label in HORIZONS.items():
                rows = rows_for(blk, h)
                if not rows:
                    continue
                safe = re.sub(r"[^A-Za-z0-9]+", "-", gkey).strip("-").lower()
                ref = f"images/trump-reaction-{day}-{safe}-{h}.png"
                path = os.path.join(config.OUTPUT_DIR, ref)
                draw(rows, f"{topic} | {dlabel} | {label} (n={rows[0]['n']})", path)
                out.setdefault(gkey, {})[h] = {"ref": ref, "path": path, "url": f"https://cdn.jsdelivr.net/gh/{slug}@gh-pages/{ref}"}
                refs.append(ref)
    with open(os.path.join(config.OUTPUT_DIR, "reaction_charts.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(os.path.join(config.OUTPUT_DIR, "image_refs.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(refs))
    print(f"[chart] 과거 반응 그래프 {len(refs)}장 → output/images")
    return out


if __name__ == "__main__":
    run()
