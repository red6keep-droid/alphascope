"""수동 검증 표본 (기획서 13절 ② — 50건, 관련성·신규성 일치 ≥ 85%).

분류된 문서에서 무작위 N개를 뽑아 output/review_sample.md로 낸다. 사람이 `판정` 열에 ok/ng를 적는다.
사전 필터 탈락(키워드·중복)도 1/3 섞는다 — 필터가 맞는지도 검증 대상이다.

    python experiments/nvda-report/review_sample.py            # 50건 (seed 고정)
    python experiments/nvda-report/review_sample.py --n 30 --seed 7
"""

import argparse
import os
import random
import sys

import config
import db


def sample(conn, n, seed):
    kinds = ",".join(f"'{k}'" for k in config.CLASSIFY_KINDS)
    rows = [dict(r) for r in conn.execute(
        f"""SELECT item_id, kind, source, published_at, title, summary, prefilter_reason,
                   ai_area, ai_direction, ai_novelty, ai_relevance, ai_fact
            FROM items WHERE kind IN ({kinds}) AND (analyzed_at IS NOT NULL OR prefilter_reason IS NOT NULL)""")]
    random.Random(seed).shuffle(rows)
    filtered = [r for r in rows if r["prefilter_reason"]][: n // 3]
    classified = [r for r in rows if not r["prefilter_reason"]][: n - len(filtered)]
    out = filtered + classified
    random.Random(seed).shuffle(out)
    return out


def render(rows, path):
    lines = [
        "# 엔비디아 리포트 — 분류 수동 검증 표본", "",
        "각 행의 `판정` 열에 `ok` / `ng`. ng이면 `메모`에 올바른 값. 기준: 사전 필터 사유가 맞는가 · area · relevance(0–3) · novelty · fact가 입력(제목·요약)에 있는 내용인가", "",
        "`입력 요약` = Gemini가 제목과 함께 본 RSS 요약 전문. 비어 있으면 제목만 보고 분류한 것이다 (Google News). 기사를 열어 볼 필요는 없다.", "",
        "| # | 날짜 | 종류·출처 | 제목 | 입력 요약 | 필터 | area · dir | rel | nov | fact | 판정 | 메모 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for i, r in enumerate(rows, 1):
        title = (r["title"] or "")[:110].replace("|", "¦")
        ad = f"{r['ai_area']} · {r['ai_direction']}" if r["ai_area"] else "—"
        fact = (r["ai_fact"] or "—").replace("|", "¦")
        summary = " ".join((r["summary"] or "").split()).replace("|", "¦") or "—"
        lines.append(f"| {i} | {r['published_at'][:10]} | {r['kind']}·{r['source']} | {title} | {summary} | {r['prefilter_reason'] or ''} | {ad} | "
                     f"{r['ai_relevance'] if r['ai_relevance'] is not None else '—'} | {r['ai_novelty'] or '—'} | {fact} |  |  |")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20261008)
    args = ap.parse_args()
    conn = db.connect()
    rows = sample(conn, args.n, args.seed)
    path = render(rows, os.path.join(config.OUTPUT_DIR, "review_sample.md"))
    print(f"[review] {len(rows)}건 → {path}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
