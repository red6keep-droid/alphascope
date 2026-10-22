"""미디어 데일리 — 유튜브 수집기(red9keep/yutb-sub)의 영상별 요약(Firestore `summaries`)으로 "방송이 본 미국장" 글.

기획 · 결정: doc/기획/유튜브-자막-기사-검토.md 7 · 11절 (2026-10-22 사용자: 데일리는 그대로, 미디어 데일리를 따로. 중복은 짧게 + 데일리 링크).
재료는 요약 문장이 아니라 이슈 칸(분류 · 방향 · 예상 밖 · 종목 · 발언자)과 영상 링크 — 자막 원문 · 요약 문장은 글 · 공개 브랜치에 두지 않는다 (운영지침 4-2 예외 D4-13).
"""

import datetime
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
KST = datetime.timezone(datetime.timedelta(hours=9))

FIRESTORE_PROJECT = "ytb-v1-b96d5"
KEY_ENV = "YTB_FIRESTORE_KEY"   # 서비스 계정 키 JSON 전체 (GitHub Secret). 없으면 gcloud 기본 인증(ADC)

TITLE_NAME = "미디어 데일리 · 방송이 본 미국장"
SLUG_NAME = "media daily"          # 주소 고정용 영문 제목 "media daily YYYY-MM-DD" → /media-daily-YYYY-MM-DD.html
LABELS = ["미디어 데일리", "미국 증시", "자동 리포트"]
TEST_MODE = True                   # 첫 발행 2~4주 `테스트 중` 라벨 (운영지침 2-2)

# 1차(08:00) 재료 컷 — createdAt 이 이 시각(KST)까지. 2차(10:15 갱신)는 컷 없음
PHASE1_CUTOFF = (7, 55)
MIN_ITEMS = 5                      # 재료가 이보다 적으면 그날은 내지 않는다 (빈 구획 · "자료 없음" 금지)
TOP_ISSUES = 5                     # 본문 이슈 상위 n
MIN_CLUSTER = 1                    # 이슈 묶음 최소 영상 수 (1 = 혼자 다룬 이슈도 후보, 순서는 채널 수 · 영상 수가 정한다)
REQUIRED_CHANNELS = {"당잠사", "증시각도기", "CNBC Mad Money"}   # 필수 채널 — 2차 "장 초반에 이어 볼 것" 과 한국 연결의 재료
KOREA_CHANNELS = {"당잠사", "증시각도기"}

NARRATE_CHAIN = "json-backup-first"   # 서술은 예비 공급자 먼저 (운영지침 3-2: Groq → lite → flash)

# 분류 17개 (수집기 doc/데이터-설계.md) → 우리 이슈 코드 (experiments/issue_codes.py). 이름이 다른 셋만 바꾼다
CATEGORY_KO = {
    "RATES_CB": "금리 · 중앙은행", "INFLATION": "물가", "GROWTH_JOBS": "경기 · 고용", "TARIFF_TRADE": "관세 · 무역", "GEOPOLITICS": "지정학",
    "ENERGY_COMMODITY": "에너지 · 원자재", "AI_CAPEX": "AI 투자", "EARNINGS": "실적", "CORP_EVENT": "기업 이벤트", "CREDIT_BANKS": "은행 · 신용",
    "MARKET_STRUCTURE": "수급 · 변동성", "REGULATION": "규제", "FISCAL_POLITICS": "재정 · 정치", "FX": "환율", "CRYPTO": "암호화폐",
    "REAL_ESTATE": "부동산", "OTHER": "그 밖",
}
STANCE_KO = {"bullish": "긍정", "bearish": "부정", "neutral": "중립"}
SURPRISE_KO = {"surprise": "예상 밖", "expected": "예상대로", "unknown": ""}
SPEAKER_KO = {"Jim Cramer": "짐 크레이머", "Steve Liesman": "스티브 리스먼", "Dan Ives": "댄 아이브스", "Jerome Powell": "제롬 파월", "Scott Bessent": "스콧 베센트",
              "Donald Trump": "도널드 트럼프", "Elon Musk": "일론 머스크", "Jensen Huang": "젠슨 황", "Jamie Dimon": "제이미 다이먼", "Tom Lee": "톰 리", "Larry Kudlow": "래리 커들로"}
CHANNEL_SHORT = {"CNBC Television": "CNBC", "블룸버그 텔레비전": "블룸버그", "폭스 비즈니스": "폭스", "CNBC Mad Money": "Mad Money"}


def today_kst():
    return datetime.datetime.now(KST).strftime("%Y-%m-%d")


def korean_date(d):
    y, m, dd = d.split("-")[:3]
    return f"{int(y)}년 {int(m)}월 {int(dd)}일"


def post_title(d):
    return f"{TITLE_NAME} {korean_date(d)}"
