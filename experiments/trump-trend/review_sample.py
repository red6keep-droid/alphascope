"""수동 검증 표본 추출 (기획서 5절·13절 ④).

분류된 게시물에서 무작위 N개를 뽑아 output/review_sample.md 로 낸다.
사람이 '노이즈 판정'과 'market_relevance'가 맞는지 표시한 뒤, 일치율을 손으로 세거나
--check 로 ok/ng 열을 읽어 집계한다.

    python experiments/trump-trend/review_sample.py            # 50개 추출 (seed 고정)
    python experiments/trump-trend/review_sample.py --n 30 --seed 7
"""

import argparse
import os
import random
import sys

import config
import db
import prefilter


def sample(conn, n, seed):
    rows = conn.execute(
        """SELECT id, published_at, content, noise_reason, ai_topic, ai_subtopic,
                  ai_target_country, ai_target_sector, ai_mentioned_companies,
                  ai_direction, ai_intensity, ai_market_relevance
           FROM trump_posts
           WHERE published_at >= date('now', ?)
             AND (analyzed_at IS NOT NULL OR noise_reason IS NOT NULL)""",
        (f"-{config.CLASSIFY_SINCE_DAYS} days",),
    ).fetchall()
    rows = [dict(r) for r in rows]
    random.Random(seed).shuffle(rows)
    # 사전 필터 노이즈와 Gemini 분류를 절반씩 — 둘 다 검증 대상이다
    noise = [r for r in rows if r["noise_reason"]][: n // 3]
    classified = [r for r in rows if not r["noise_reason"]][: n - len(noise)]
    out = noise + classified
    random.Random(seed).shuffle(out)
    return out


def render(rows, path):
    lines = [
        "# 수동 검증 표본", "",
        "각 행의 `판정` 열에 `ok` / `ng` 를 적는다. ng 이면 `메모`에 올바른 값을 적는다.",
        "기준: 사전 필터 노이즈가 맞는가 · topic 이 맞는가 · market_relevance(0–3) 가 기준표와 맞는가", "",
        "| # | 시각(UTC) | 본문 | 필터 | topic / sub | relevance | dir · int | 판정 | 메모 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for i, r in enumerate(rows, 1):
        text = prefilter.clean_text(r["content"])[:140].replace("|", "¦")
        sub = f"{r['ai_topic']} / {r['ai_subtopic']}" if r["ai_topic"] else "—"
        rel = r["ai_market_relevance"] if r["ai_market_relevance"] is not None else "—"
        di = f"{r['ai_direction']} · {r['ai_intensity']}" if r["ai_direction"] else "—"
        lines.append(f"| {i} | {r['published_at'][5:16]} | {text} | {r['noise_reason'] or ''} | {sub} | {rel} | {di} |  |  |")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20260915)
    args = ap.parse_args()
    conn = db.connect()
    rows = sample(conn, args.n, args.seed)
    path = render(rows, os.path.join(config.OUTPUT_DIR, "review_sample.md"))
    print(f"[review] {len(rows)}건 → {path}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
