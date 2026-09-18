"""집계 — 창별 트렌드 · Trend Score · 반응 통계(+플라시보) · 오늘의 이벤트 (기획서 7·8·10절).

전부 파이썬이 계산한다. 출력은 output/trump_analysis.json 하나. Gemini는 이 JSON을 설명만 한다.
"""

import datetime
import json
import os
import random
import statistics
import sys
from collections import defaultdict

import config
import db
import event_study
import mapping

UTC = datetime.timezone.utc


def _parse(ts):
    return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _fmt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _rank_pct(values):
    """값 리스트 → 0–100 순위 백분위 (동률은 평균 순위). 값이 하나면 50."""
    n = len(values)
    if n <= 1:
        return [50.0] * n
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return [r / (n - 1) * 100 for r in ranks]


# ── 로드 ────────────────────────────────────────────────────────────────

def load_events(conn):
    rows = conn.execute("SELECT * FROM trump_events ORDER BY first_post_at").fetchall()
    events = []
    for r in rows:
        e = dict(r)
        e["t"] = _parse(e["first_post_at"])
        e["affected"] = db.loads(e["affected_companies"])
        e["mentioned"] = db.loads(e.get("mentioned_companies"))
        e["labels"] = db.loads(e["confound_labels"])
        e["key"] = f"{e['topic']} / {e['subtopic']}" if e["subtopic"] else e["topic"]
        events.append(e)
    reactions = defaultdict(dict)
    for r in conn.execute("SELECT * FROM event_reactions"):
        reactions[r["event_id"]][r["symbol"]] = dict(r)
    for e in events:
        e["reactions"] = reactions.get(e["event_id"], {})
    return events


# ── 게시량 ──────────────────────────────────────────────────────────────

def post_volume(conn, now):
    def count(where, params):
        return conn.execute(f"SELECT COUNT(*) FROM trump_posts WHERE {where}", params).fetchone()[0]

    d1 = _fmt(now - datetime.timedelta(days=1))
    d7 = _fmt(now - datetime.timedelta(days=7))
    total_24h = count("published_at >= ?", (d1,))
    noise_24h = count("published_at >= ? AND noise_reason IS NOT NULL", (d1,))
    policy_24h = count("published_at >= ? AND ai_market_relevance >= ?", (d1, config.RELEVANCE_EVENT_MIN))
    pending_24h = count("published_at >= ? AND noise_reason IS NULL AND analyzed_at IS NULL", (d1,))
    per_day = conn.execute(
        """SELECT substr(published_at, 1, 10) AS day,
                  COUNT(*) AS total,
                  SUM(CASE WHEN ai_market_relevance >= ? THEN 1 ELSE 0 END) AS policy,
                  SUM(CASE WHEN noise_reason IS NULL AND analyzed_at IS NULL THEN 1 ELSE 0 END) AS pending
           FROM trump_posts WHERE published_at >= ? GROUP BY day ORDER BY day""",
        (config.RELEVANCE_EVENT_MIN, d7)).fetchall()
    return {
        "last_24h": {"total": total_24h, "noise": noise_24h, "policy": policy_24h, "pending": pending_24h,
                     "policy_ratio": round(policy_24h / total_24h, 3) if total_24h else None},
        "per_day_7d": [dict(r) for r in per_day],
    }


# ── 창별 트렌드 ─────────────────────────────────────────────────────────

def _bucket(events, start, end, dim):
    out = defaultdict(list)
    for e in events:
        if start <= e["t"] < end:
            for k in _dim_keys(e, dim):
                out[k].append(e)
    return out


def _dim_keys(e, dim):
    if dim == "topic":
        return [e["topic"]]
    if dim == "topic_subtopic":
        return [e["key"]]
    if dim == "target":
        return [e["target"]] if e["target"] and e["target"] != "general" else []
    if dim == "symbol":
        return e["affected"]
    if dim == "mentioned":
        return e["mentioned"]
    return []


def window_trends(events, now):
    out = {}
    for w in config.WINDOWS_DAYS:
        cur_start = now - datetime.timedelta(days=w)
        prev_start = now - datetime.timedelta(days=2 * w)
        has_prev = bool(events) and events[0]["t"] <= prev_start
        per_dim = {}
        for dim in ("topic", "topic_subtopic", "target", "symbol"):
            cur = _bucket(events, cur_start, now, dim)
            prev = _bucket(events, prev_start, cur_start, dim)
            rows = []
            for k in set(cur) | set(prev):
                c, p = cur.get(k, []), prev.get(k, [])
                rows.append({
                    "key": k,
                    "events": len(c), "posts": sum(e["post_count"] for e in c),
                    "avg_intensity": round(statistics.mean(e["event_intensity"] for e in c), 2) if c else None,
                    "max_intensity": max((e["event_intensity"] for e in c), default=None),
                    "neg_ratio": round(sum(e["event_direction"] == "negative" for e in c) / len(c), 2) if c else None,
                    "prev_events": len(p) if has_prev else None,
                    "delta_events": (len(c) - len(p)) if has_prev else None,
                    "prev_avg_intensity": round(statistics.mean(e["event_intensity"] for e in p), 2) if (p and has_prev) else None,
                })
            rows.sort(key=lambda r: (-r["events"], -(r["avg_intensity"] or 0)))
            per_dim[dim] = rows
        out[f"{w}D"] = {"window_days": w, "compare_to_previous": has_prev, "dims": per_dim}
    return out


# ── Trend Score ─────────────────────────────────────────────────────────

def trend_scores(events, now):
    w = config.TREND_SCORE_WINDOW
    cur_start = now - datetime.timedelta(days=w)
    prev_start = now - datetime.timedelta(days=2 * w)
    nov_start = now - datetime.timedelta(days=config.NOVELTY_LOOKBACK_DAYS)

    cur = _bucket(events, cur_start, now, "topic_subtopic")
    prev = _bucket(events, prev_start, cur_start, "topic_subtopic")
    seen_before = set(_bucket(events, nov_start, cur_start, "topic_subtopic"))
    keys = list(cur)
    if not keys:
        return []

    freq_delta = [len(cur[k]) - len(prev.get(k, [])) for k in keys]
    intensity = [statistics.mean(e["event_intensity"] for e in cur[k]) for k in keys]
    recency = [-(now - max(e["t"] for e in cur[k])).total_seconds() for k in keys]
    novelty = [100.0 if k not in seen_before else 0.0 for k in keys]

    f_s, i_s, r_s = _rank_pct(freq_delta), _rank_pct(intensity), _rank_pct(recency)
    wts = config.TREND_WEIGHTS
    rows = []
    for idx, k in enumerate(keys):
        score = (wts["frequency"] * f_s[idx] + wts["intensity"] * i_s[idx]
                 + wts["recency"] * r_s[idx] + wts["novelty"] * novelty[idx])
        rows.append({
            "key": k, "score": round(score, 1),
            "events_7d": len(cur[k]), "events_prev_7d": len(prev.get(k, [])),
            "avg_intensity": round(intensity[idx], 2),
            "last_event_at": _fmt(max(e["t"] for e in cur[k])),
            "is_new_90d": k not in seen_before,
            "components": {"frequency": round(f_s[idx]), "intensity": round(i_s[idx]),
                           "recency": round(r_s[idx]), "novelty": round(novelty[idx])},
        })
    rows.sort(key=lambda r: -r["score"])
    return rows[:config.TOP_TRENDS]


def new_entrants(events, now):
    w = config.TREND_SCORE_WINDOW
    cur_start = now - datetime.timedelta(days=w)
    nov_start = now - datetime.timedelta(days=config.NOVELTY_LOOKBACK_DAYS)
    out = {}
    # 종목 신규 등장은 매핑으로 붙은 종목이 아니라 본문에 실제 언급된 종목만 본다.
    for dim, out_key in (("target", "target"), ("mentioned", "symbol")):
        cur = set(_bucket(events, cur_start, now, dim))
        before = set(_bucket(events, nov_start, cur_start, dim))
        out[out_key] = sorted(cur - before)
    return out


# ── 반응 통계 ────────────────────────────────────────────────────────────
#
# 구간(horizon) 7개. 전부 일봉 OHLCV (분봉 없음, 2026-09-18 결정).
#   immediate  장외 게시물은 갭(abn_gap), 정규장 게시물은 장중(abn_intraday). 이벤트마다 종류가 다르다.
#   close · next_close · d3 · d5   기준 종가 대비 초과 반응 (%)
#   rel_range · rel_volume         변동폭·거래량 배수 (1.0 = 보통). 방향 무관, SPY 차감 없음
HORIZONS = ["immediate", "close", "next_close", "d3", "d5", "rel_range", "rel_volume"]
RATIO_HORIZONS = {"rel_range", "rel_volume"}


def _col(sym, hz):
    if hz in RATIO_HORIZONS:
        return hz
    return f"ret_{hz}" if sym == config.BENCHMARK else f"abn_{hz}"


def _immediate_kind(e):
    return "intraday" if e["market_session"] == "regular" else "gap"


def _stats(obs, ratio=False):
    """obs = [(kind, value)] → 요약. ratio면 배수(중심 1)로 다룬다. 값이 없으면 None."""
    vals = [v for _, v in obs if v is not None]
    if not vals:
        return None
    if ratio:
        mean, med = statistics.fmean(vals), statistics.median(vals)
        std = statistics.pstdev(vals) if len(vals) > 1 else None
        pos, neg = sum(v > 1 for v in vals), sum(v < 1 for v in vals)
        rnd = lambda x: None if x is None else round(x, 2)   # noqa: E731
    else:
        mean, med = statistics.fmean(vals) * 100, statistics.median(vals) * 100
        std = statistics.pstdev(vals) * 100 if len(vals) > 1 else None
        pos, neg = sum(v > 0 for v in vals), sum(v < 0 for v in vals)
        rnd = lambda x: None if x is None else round(x, 3)   # noqa: E731
    return {
        "n": len(vals), "unit": "x" if ratio else "pct",
        "mean": rnd(mean), "median": rnd(med), "std": rnd(std),
        "pos_pct": round(pos / len(vals) * 100, 1),
        "neg_pct": round(neg / len(vals) * 100, 1),
        "publishable": len(vals) >= config.MIN_CLEAN_N,
    }


def _placebo(obs, pool, seed, ratio=False):
    """관측 평균이 '보통 날' N개 평균 분포에서 얼마나 극단적인가 (양측 p).

    obs의 kind별 개수만큼 해당 kind의 풀에서 복원 추출해 평균을 만든다. 시드는 문자열이라 실행마다 같다.
    풀이 PLACEBO_MIN_POOL보다 작으면 검정하지 않는다(None).
    """
    kinds = defaultdict(int)
    vals = []
    for kind, v in obs:
        if v is not None:
            kinds[kind] += 1
            vals.append(v)
    if not vals or any(len(pool.get(k, [])) < config.PLACEBO_MIN_POOL for k in kinds):
        return None
    center = 1.0 if ratio else 0.0
    obs_mean = statistics.fmean(vals)
    dist = abs(obs_mean - center)
    rng = random.Random(seed)
    n = len(vals)
    extreme = 0
    for _ in range(config.PLACEBO_RESAMPLES):
        total = 0.0
        for k, cnt in kinds.items():
            total += sum(rng.choices(pool[k], k=cnt))
        if abs(total / n - center) >= dist:
            extreme += 1
    union = [v for k in kinds for v in pool[k]]
    base_neg = sum(v < center for v in union) / len(union) * 100
    p = (extreme + 1) / (config.PLACEBO_RESAMPLES + 1)     # 0이 되지 않게 — 최소 1/(B+1)
    return {
        "p_two_sided": round(p, 3),
        "pool_n": min(len(pool[k]) for k in kinds),
        "pool_neg_pct": round(base_neg, 1),
        "pool_mean": round(statistics.fmean(union) * (1 if ratio else 100), 3),
        "indistinguishable": p >= config.PLACEBO_NOISE_P,
    }


def _exclude_days(conn, events):
    days = {e["effective_day"] for e in events if e["effective_day"]}
    days |= {r["day"] for r in conn.execute("SELECT DISTINCT day FROM macro_calendar")}
    return days


def reaction_stats(events, conn=None):
    """(topic 또는 topic/subtopic) × symbol × horizon → 통계 (+ 플라시보). clean 이벤트만."""
    groups = defaultdict(lambda: defaultdict(lambda: {hz: [] for hz in HORIZONS}))
    counts = defaultdict(lambda: {"total": 0, "clean": 0, "confounded": 0, "pending": 0, "same_day_merged": 0,
                                  "immediate_kinds": {"gap": 0, "intraday": 0}})
    # 일 단위 구간에서는 같은 주제의 이벤트가 같은 거래일에 여럿 있어도 관측값은 하나다
    # (기준일·측정일이 같으면 수익률이 같다). N을 부풀리지 않기 위해 (주제, 기준일, 측정일)로 합친다.
    seen_day = set()
    for e in events:
        for gkey in {e["topic"], e["key"]}:
            counts[gkey]["total"] += 1
            if e["confounded_daily"]:
                counts[gkey]["confounded"] += 1
                continue
            has_any = any(r.get("ret_close") is not None for r in e["reactions"].values())
            if not has_any:
                counts[gkey]["pending"] += 1
                continue
            day_key = (gkey, e["baseline_day"], e["effective_day"])
            if day_key in seen_day:
                counts[gkey]["same_day_merged"] += 1
                continue
            seen_day.add(day_key)
            counts[gkey]["clean"] += 1
            ik = _immediate_kind(e)
            counts[gkey]["immediate_kinds"][ik] += 1
            for sym, r in e["reactions"].items():
                g = groups[gkey][sym]
                g["immediate"].append((ik, r.get(_col(sym, ik))))
                for hz in HORIZONS[1:]:
                    g[hz].append((hz, r.get(_col(sym, hz))))

    pools = event_study.placebo_pools(conn, _exclude_days(conn, events)) if conn is not None else {}
    out = {}
    for gkey, syms in groups.items():
        sym_out = {}
        for sym, horizons in syms.items():
            hz_out = {}
            for hz, obs in horizons.items():
                ratio = hz in RATIO_HORIZONS
                st = _stats(obs, ratio)
                if st and st["publishable"] and sym in pools:
                    st["placebo"] = _placebo(obs, pools[sym], f"{gkey}|{sym}|{hz}", ratio)
                hz_out[hz] = st
            sym_out[sym] = hz_out
        out[gkey] = {"counts": counts[gkey], "symbols": sym_out}
    for gkey, c in counts.items():
        out.setdefault(gkey, {"counts": c, "symbols": {}})
    return out


# ── 오늘의 이벤트 ─────────────────────────────────────────────────────

def recent_events(events, now, hours=24):
    since = now - datetime.timedelta(hours=hours)
    rows = []
    for e in reversed(events):
        if e["t"] < since:
            break
        rule = mapping.rule_by_id(e["mapping_rule_id"]) if e["mapping_rule_id"] else None
        rows.append({
            "event_id": e["event_id"], "first_post_at": e["first_post_at"],
            "topic": e["topic"], "subtopic": e["subtopic"], "target": e["target"],
            "direction": e["event_direction"], "intensity": e["event_intensity"],
            "post_count": e["post_count"], "session": e["market_session"],
            "effective_day": e["effective_day"],
            "confounded_daily": bool(e["confounded_daily"]), "confound_labels": e["labels"],
            "rule_id": e["mapping_rule_id"],
            "path_text": rule["path_text"] if rule else None,
            "etf": rule["etf"] if rule else None,
            "affected": e["affected"][:10],
        })
    rows.sort(key=lambda r: (-r["intensity"], -r["post_count"]))
    return rows


# ── 조립 ─────────────────────────────────────────────────────────────────

def build(conn, now=None, output_path=None):
    now = now or datetime.datetime.now(UTC)
    events = load_events(conn)
    analysis = {
        "generated_at": _fmt(now),
        "config": {
            "windows_days": config.WINDOWS_DAYS, "trend_weights": config.TREND_WEIGHTS,
            "min_clean_n": config.MIN_CLEAN_N, "cluster_gap_minutes": config.CLUSTER_GAP_MINUTES,
            "benchmark": config.BENCHMARK, "universe": config.ALL_SYMBOLS,
            "horizons": HORIZONS, "car_days": config.CAR_DAYS, "rel_lookback_days": config.REL_LOOKBACK_DAYS,
            "placebo_resamples": config.PLACEBO_RESAMPLES, "placebo_noise_p": config.PLACEBO_NOISE_P,
        },
        "data_status": {
            "posts_total": conn.execute("SELECT COUNT(*) FROM trump_posts").fetchone()[0],
            # 전체 미분류는 의도적으로 분류 범위 밖(90일 이전)인 글이 대부분이다. 리포트에 의미 있는 건 범위 안의 잔여.
            "posts_pending_all_time": conn.execute(
                "SELECT COUNT(*) FROM trump_posts WHERE noise_reason IS NULL AND analyzed_at IS NULL").fetchone()[0],
            "posts_pending_recent": conn.execute(
                "SELECT COUNT(*) FROM trump_posts WHERE noise_reason IS NULL AND analyzed_at IS NULL "
                "AND published_at >= ?",
                ((now - datetime.timedelta(days=config.CLASSIFY_SINCE_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ"),)
            ).fetchone()[0],
            "classify_since_days": config.CLASSIFY_SINCE_DAYS,
            "posts_classified": conn.execute("SELECT COUNT(*) FROM trump_posts WHERE analyzed_at IS NOT NULL").fetchone()[0],
            "events_total": len(events),
            "events_first_at": events[0]["first_post_at"] if events else None,
            "bars_last_day": conn.execute("SELECT MAX(day) FROM daily_bars WHERE symbol = ?",
                                          (config.BENCHMARK,)).fetchone()[0],
            "posts_last_collected_at": db.get_meta(conn, "posts_last_collected_at"),
        },
        "post_volume": post_volume(conn, now),
        "recent_events": recent_events(events, now),
        "trend_scores": trend_scores(events, now),
        "new_entrants": new_entrants(events, now),
        "windows": window_trends(events, now),
        "reactions": reaction_stats(events, conn),
    }
    output_path = output_path or os.path.join(config.OUTPUT_DIR, "trump_analysis.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    print(f"[aggregate] 이벤트 {len(events):,} · 최근 24h {len(analysis['recent_events'])} · "
          f"트렌드 {len(analysis['trend_scores'])} → {output_path}")
    return analysis


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build(db.connect())
