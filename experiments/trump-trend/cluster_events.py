"""게시물 → 이벤트 클러스터링 (기획서 6절) + 세션·기준일·confounded (8절).

매 실행마다 이벤트를 전부 다시 만든다. 규칙이 결정적이므로 같은 입력이면 같은 event_id가 나온다.
"""

import datetime
import re
import sys
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo

import calendar_macro
import collect_prices
import config
import db
import labels
import mapping

ET = ZoneInfo("America/New_York")
UTC = datetime.timezone.utc

# 거시 발표 시각(ET) — confounded_intraday 근사. 분봉 확보 전에도 판정할 수 있게.
RELEASE_TIME_ET = {"FOMC": (14, 0), "CPI": (8, 30), "NFP": (8, 30), "GDP": (8, 30), "PCE": (8, 30)}


def _parse(ts):
    return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "general").lower()).strip("-") or "general"


def _target_of(post):
    countries = db.loads(post["ai_target_country"])
    sectors = db.loads(post["ai_target_sector"])
    if countries:
        return countries[0]
    if sectors:
        return sectors[0]
    return "general"


def _session(t_utc, trading_set):
    t = t_utc.astimezone(ET)
    day = t.strftime("%Y-%m-%d")
    if day not in trading_set:
        return "closed"
    hm = t.hour * 60 + t.minute
    if 9 * 60 + 30 <= hm < 16 * 60:
        return "regular"
    if 4 * 60 <= hm < 9 * 60 + 30:
        return "pre"
    if 16 * 60 <= hm < 20 * 60:
        return "after"
    return "closed"


def _baseline_and_effective(t_utc, trading_days):
    """기준 종가의 거래일(직전 종가)과 반응을 재는 거래일 D."""
    t = t_utc.astimezone(ET)
    day = t.strftime("%Y-%m-%d")
    after_close = t.hour * 60 + t.minute >= 16 * 60
    baseline = None
    effective = None
    for d in trading_days:
        if d < day or (d == day and after_close):
            baseline = d
        elif effective is None:
            effective = d
            break
    return baseline, effective


def _weighted_direction(posts):
    weight = Counter()
    for p in posts:
        weight[p["ai_direction"]] += p["ai_intensity"]
    ranked = weight.most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return "neutral"
    return ranked[0][0]


def _confounds(conn, t_utc, effective_day):
    labels = calendar_macro.labels_on(conn, effective_day) if effective_day else []
    daily = 1 if labels else 0
    intraday = 0
    t = t_utc.astimezone(ET)
    for lab in labels:
        kind = lab.split(":", 1)[0]
        if kind not in RELEASE_TIME_ET or t.strftime("%Y-%m-%d") != effective_day:
            continue
        h, m = RELEASE_TIME_ET[kind]
        release = t.replace(hour=h, minute=m, second=0, microsecond=0)
        if abs((t - release).total_seconds()) <= config.CONFOUND_INTRADAY_MINUTES * 60:
            intraday = 1
    return daily, intraday, labels


def load_candidates(conn):
    rows = conn.execute(
        """SELECT * FROM trump_posts
           WHERE analyzed_at IS NOT NULL AND noise_reason IS NULL AND ai_market_relevance >= ?
             AND ai_topic IN ({})
           ORDER BY published_at""".format(",".join("?" * len(config.TOPICS_MARKET))),
        (config.RELEVANCE_EVENT_MIN, *config.TOPICS_MARKET),
    ).fetchall()
    posts = [dict(r) for r in rows]
    for p in posts:   # 기존 행의 "Tariffs"/"tariff"도 같은 키로 묶이게 읽을 때 정규화
        p["ai_subtopic"] = labels.normalize_subtopic(p["ai_subtopic"])
    return posts


def cluster(posts):
    """시간순 게시물 → 이벤트 리스트 (각 이벤트는 post dict 리스트)."""
    gap = datetime.timedelta(minutes=config.CLUSTER_GAP_MINUTES)
    open_clusters = {}   # key → (last_time, list)
    events = []
    for p in posts:
        t = _parse(p["published_at"])
        key = (p["ai_topic"], (p["ai_subtopic"] or "").lower(), _target_of(p).lower())
        cur = open_clusters.get(key)
        if cur and t - cur[0] <= gap:
            cur[1].append(p)
            open_clusters[key] = (t, cur[1])
        else:
            bucket = [p]
            open_clusters[key] = (t, bucket)
            events.append(bucket)
    return events


def build(conn):
    trading_days = collect_prices.trading_days(conn)
    trading_set = set(trading_days)
    posts = load_candidates(conn)
    groups = cluster(posts)

    conn.execute("DELETE FROM trump_events")
    conn.execute("UPDATE trump_posts SET event_id = NULL")

    seq = defaultdict(int)
    rows = []
    for bucket in groups:
        first = bucket[0]
        t0 = _parse(first["published_at"])
        topic = first["ai_topic"]
        target = _target_of(first)
        day_key = (t0.strftime("%Y%m%d"), _slug(topic), _slug(target))
        seq[day_key] += 1
        event_id = f"evt_{day_key[0]}_{day_key[1]}_{day_key[2]}_{seq[day_key]:02d}"

        countries, sectors, mentioned = [], [], []
        for p in bucket:
            countries += db.loads(p["ai_target_country"])
            sectors += db.loads(p["ai_target_sector"])
            mentioned += db.loads(p["ai_mentioned_companies"])
        rule_id, affected = mapping.apply({
            "topic": topic, "subtopic": first["ai_subtopic"],
            "target_country": list(dict.fromkeys(countries)),
            "target_sector": list(dict.fromkeys(sectors)),
            "mentioned_companies": list(dict.fromkeys(mentioned)),
        })
        baseline, effective = _baseline_and_effective(t0, trading_days)
        c_daily, c_intra, labels = _confounds(conn, t0, effective)

        rows.append({
            "event_id": event_id, "topic": topic, "subtopic": first["ai_subtopic"] or "",
            "target": target,
            "first_post_at": first["published_at"], "last_post_at": bucket[-1]["published_at"],
            "post_count": len(bucket),
            "event_direction": _weighted_direction(bucket),
            "event_intensity": max(p["ai_intensity"] for p in bucket),
            "mapping_rule_id": rule_id,
            "mentioned_companies": db.dumps(list(dict.fromkeys(mentioned))),
            "affected_companies": db.dumps(affected),
            "market_session": _session(t0, trading_set),
            "baseline_day": baseline, "effective_day": effective,
            "confounded_intraday": c_intra, "confounded_daily": c_daily,
            "confound_labels": db.dumps(labels),
        })
        conn.executemany("UPDATE trump_posts SET event_id = ? WHERE id = ?",
                         [(event_id, p["id"]) for p in bucket])

    conn.executemany(
        """INSERT INTO trump_events
           (event_id, topic, subtopic, target, first_post_at, last_post_at, post_count,
            event_direction, event_intensity, mapping_rule_id, mentioned_companies, affected_companies,
            market_session, baseline_day, effective_day,
            confounded_intraday, confounded_daily, confound_labels)
           VALUES
           (:event_id, :topic, :subtopic, :target, :first_post_at, :last_post_at, :post_count,
            :event_direction, :event_intensity, :mapping_rule_id, :mentioned_companies, :affected_companies,
            :market_session, :baseline_day, :effective_day,
            :confounded_intraday, :confounded_daily, :confound_labels)""",
        rows,
    )
    conn.commit()
    multi = sum(1 for r in rows if r["post_count"] > 1)
    conf = sum(1 for r in rows if r["confounded_daily"])
    print(f"[events] 게시물 {len(posts):,}건 → 이벤트 {len(rows):,}개 (연타 {multi} · confounded_daily {conf})")
    return len(rows)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build(db.connect())
