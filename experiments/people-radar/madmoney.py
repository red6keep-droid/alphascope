"""짐 크레이머 1차 자료 = 매드머니 방송 기록 (2026-11-11 사용자: "크레이머는 매드머니 유튜브 독점 채널이 있다. 이미 우리가 수집 중이다").

매드머니 자막은 유튜브 수집기 → 방송 분배(media-daily, 평일 KST 10:15)가 이슈 · 방향 · 종목 · 이슈 코드를 붙여
우리 방송 기록(상태 저장소 media-state, records/issues, source=ytb)에 쌓는다. 여기서는 그 기록을 읽기만 한다 — AI 0, 구글 뉴스 0.
- 인물 발언은 KST 08:00 에 돈다. 그 시각엔 전날 밤(미국 동부 18시 = KST 08시) 방송이 아직 없어 **하루 전 방송**이 들어간다 (사용자 A안).
  그래서 집계 창을 매드머니만 MADMONEY_WINDOW_HOURS 로 넓힌다 (aggregate._labeled).
- 영상 한 편 × 이슈 한 줄 = 발언 한 행. 라벨은 방송 기록 것을 그대로 옮긴다 (트럼프 Truth Social 이 trump-state 라벨을 쓰는 것과 같은 방식).
"""

import json
import os
import subprocess

import config

CHANNEL = "CNBC Mad Money"   # media-daily config.REQUIRED_CHANNELS 의 이름
COLLECTOR = "madmoney"
SPEAKER = "cramer"
LOCAL_DIR = os.path.join(config.BASE_DIR, "..", "media-daily", "output", "state", "records", "issues")
GIT_PATH = "state/media-state:experiments/media-daily/output/state/records/issues/{year}.jsonl"
DIRECTION = {"bullish": "positive", "bearish": "negative"}
TOPIC_BY_SCOPE = {"stock": "Stock Call", "sector": "Sector Call"}   # 그 밖(market · macro) = Market Outlook


def load(years):
    """방송 기록 가운데 매드머니 줄만 {기록 id: 줄}. 로컬 상태 폴더 + 상태 브랜치를 합친다 (못 읽으면 빈 값 — 크레이머는 구글 뉴스만으로)."""
    texts = []
    for y in years:
        p = os.path.join(LOCAL_DIR, f"{y}.jsonl")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                texts.append(f.read())
        try:
            texts.append(subprocess.run(["git", "show", GIT_PATH.format(year=y)], capture_output=True, text=True, encoding="utf-8",
                                        check=True, cwd=config.BASE_DIR).stdout)
        except Exception as e:  # noqa: BLE001
            print(f"[madmoney] 방송 기록 {y} 못 읽음: {str(e)[:80]}")
    out = {}
    for text in texts:
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("source") == "ytb" and r.get("channel") == CHANNEL and r.get("id") and r.get("published"):
                out[str(r["id"])] = r
    return out


def title_of(r):
    topic = (r.get("subtopic") or "").strip()
    return f'{r.get("title") or "Mad Money"} — {topic}' if topic else (r.get("title") or "Mad Money")


def labels(r, ticker_re):
    """방송 기록 한 줄 → statements 분류 칸 (classify.LABEL_COLS)."""
    syms = [s for s in (r.get("symbols") or []) if ticker_re.match(str(s))][:8]
    scope = r.get("scope") or ""
    topic = TOPIC_BY_SCOPE.get(scope, "Market Outlook")
    if topic == "Stock Call" and not syms:
        topic = "Market Outlook"
    return {
        "ai_topic": topic, "ai_subtopic": (r.get("subtopic") or "")[:60],
        "ai_target_country": json.dumps([r["country"]] if r.get("country") else [], ensure_ascii=False),
        "ai_target_sector": "[]",
        "ai_mentioned_companies": json.dumps(syms, ensure_ascii=False),
        "ai_direction": DIRECTION.get(r.get("stance"), "neutral"),
        "ai_intensity": 6 if syms else 4,          # 종목을 짚은 의견 = 수치 없는 강한 주장(5-6), 시장 일반 = 의견(3-4)
        "ai_market_relevance": 3 if syms else 2,
        "ai_issue": r.get("issue") or "INVESTOR_CALLS",
    }
