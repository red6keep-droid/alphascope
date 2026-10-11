"""CNN 공포·탐욕 지수 (Fear & Greed) — 시장 국면 카드 글머리표용 (2026-10-11 사용자).

엔드포인트는 브라우저 헤더가 없으면 418을 돌려준다. 기준 거래일 행(daily_state.fng_score · fng_rating)에 저장한다.
실패하면 조용히 None — 카드는 그 항목을 비운다. 등급 한글: extreme fear 극단적 공포 · fear 공포 · neutral 중립 · greed 탐욕 · extreme greed 극단적 탐욕.
"""

import requests

import config
import db

RATING_KO = {"extreme fear": "극단적 공포", "fear": "공포", "neutral": "중립", "greed": "탐욕", "extreme greed": "극단적 탐욕"}
HEADERS = {"User-Agent": config.BROWSER_USER_AGENT, "Accept": "application/json, text/plain, */*",
           "Accept-Language": "en-US,en;q=0.9", "Referer": "https://www.cnn.com/markets/fear-and-greed", "Origin": "https://www.cnn.com"}


def fetch():
    r = requests.get(config.FNG_URL, headers=HEADERS, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    fg = r.json().get("fear_and_greed") or {}
    score, rating = fg.get("score"), (fg.get("rating") or "").lower()
    if score is None:
        return None
    return {"score": float(score), "rating": rating, "rating_ko": RATING_KO.get(rating, rating), "timestamp": fg.get("timestamp")}


def collect(conn, day):
    try:
        v = fetch()
    except Exception as e:  # noqa: BLE001
        print(f"[fng] 실패 — 공포·탐욕 칸 비움: {e}")
        return None
    if not v:
        print("[fng] 값 없음")
        return None
    conn.execute("INSERT OR IGNORE INTO daily_state(day) VALUES (?)", (day,))
    conn.execute("UPDATE daily_state SET fng_score = ?, fng_rating = ? WHERE day = ?", (v["score"], v["rating"], day))
    conn.commit()
    print(f"[fng] 공포·탐욕 {v['score']:.0f} ({v['rating_ko']}) · {v.get('timestamp')}")
    return v
