"""AlphaScope 시황 해설 — 새 틀('이어 쓰는 시황 기사', 수집기 17절 format story) 블로그 화면 목업.

    python experiments/market-commentary/mock_story.py

- 재료 = 수집기 시험 글(run 44024100385, 11-17 am)을 17절 칸 모양으로 옮기고 18~22절 규칙(제목 = 주제만 · 부호 없는 등락 · 이름 한 토막 → 소속만 · banner 칸)으로 고친 것 (11-19)(아래 SAMPLE) + 묶음 briefing/2026-11-17-am.json 숫자.
- 그리기는 발행기와 같은 story_render.render (2026-11-19 발행기와 공용으로 뗌).
- 출력: output/mock_story.html (커밋 안 함). AI 0 · 네트워크 0.
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, ".."))
import design_kit as dk  # noqa: E402

OUT = os.path.join(BASE, "output", "mock_story.html")
BLOG = "https://www.newfact.app/"

# 새 틀 목업 재료 — 수집기 11-18 저녁 시험 글의 사실만으로 블로그가 손으로 다시 쓴 것.
# 수집기에 부탁한 꼴(요청 27절): 한눈에 보기 3문장 · 변수마다 3문장(일 → 시장에 왜 → 남은 것) · `**결과**` · `==원인 · 변수==` · takeaway.
SAMPLE = {
 "format": "story",
 "date": "2026-11-18",
 "slot": "pm",
 "title": "엔비디아 실적 안도에 반도체 반등, 코스피 5,000선 회복",
 "summary": "엔비디아 호실적에 반도체주가 반등하며 코스피가 5,000선을 회복했습니다.",
 "overview": "나흘 연속 내리며 5,000선을 내줬던 코스피가 **엔비디아 호실적에 힘입어 하루 만에 5,000선을 되찾았습니다**. ==AI 수요가 꺾이지 않았다는 확인==이 삼성전자와 SK하이닉스로 매수세를 불러왔고, ==한중 FTA 후속 협상 타결== 소식이 오름폭을 키웠습니다. 다만 반등을 이끈 것은 반도체 한 축이어서, 오늘 밤 앤트로픽 상장과 미국의 대중국 수출 통제에 미국 기술주가 어떻게 반응하는지가 다음 장의 관건입니다.",
 "drivers": [
  {
   "heading": "반도체 반등과 외국인 수급",
   "body": "앤트로픽 상장에 자금이 쏠릴 것이라는 우려로 나흘 내리 밀렸던 시장을 돌려세운 것은 **엔비디아의 3분기 매출 1,158억 달러와 4분기 전망 약 1,300억 달러**였습니다. AI 투자가 이어진다는 숫자가 확인되자, ==고점보다 평균 55% 낮아진 삼성전자와 SK하이닉스에 과도한 우려가 반영됐다는 시각==(이창민 KB증권 연구원)에 힘이 실렸습니다. 그러나 올해 외국인 순매도의 85%가 두 종목에 몰려 있고, ==MSCI 지수 비중 상한을 넘을 때마다 매도가 나오는 구조==(하나증권)는 그대로 남아 있습니다."
  },
  {
   "heading": "한중 정상회담과 교류 확대",
   "body": "반도체가 지수를 끌어올린 날, 오름폭을 넓힌 것은 한중 관계였습니다. 이재명 대통령과 시진핑 주석의 세 번째 정상회담에서 **한중 FTA 서비스 · 투자 후속 협상이 실질 타결**됐고, ==중국이 영화와 게임에 최혜국 대우를 주고 관광 · 유통 · 건설 시장을 더 열기로== 하면서 관련 업종에 기대가 붙었습니다. 다만 정식 서명과 발효가 남아 있어, 실제 한한령 해제를 확인하기 전까지는 신중해야 한다는 시각(이지현 이지스 대표)도 함께 나왔습니다."
  }
 ],
 "takeaway": "기술주와 일부 대형주에만 매수세가 몰렸고, 헬스케어와 소재로는 번지지 않았습니다.",
 "sectors": [
  {
   "name": "기술",
   "chg_pct": 3.64,
   "check": "수출 통제와 앤트로픽 상장 영향"
  },
  {
   "name": "헬스케어",
   "chg_pct": -2.39,
   "check": "대형 바이오주 하락세 진정 여부"
  },
  {
   "name": "금융",
   "chg_pct": 1.51,
   "check": "미국 금융망 장애 여파와 금리"
  },
  {
   "name": "소재",
   "chg_pct": -1.46,
   "check": "화학·비철금속 약세 진정 여부"
  }
 ],
 "pointsTitle": "오늘 밤 미국장 관전 포인트",
 "points": [
  "앤트로픽 나스닥 상장 — 공모 흥행과 자금 쏠림 여부",
  "미국 대중국 반도체 수출 통제 — 중국 대응과 기술주 영향"
 ],
 "oneLine": "엔비디아 호실적에 힘입어 반도체주가 반등하며 코스피가 5,000선 위로 올라섰습니다.",
 "tickers": [
  "NVDA",
  "066570",
  "402340",
  "000660",
  "005930",
  "032830",
  "005380",
  "207940",
  "068270",
  "051910",
  "006400"
 ],
 "banner": {
  "titles": [
   [
    "엔비디아 호실적에",
    "반도체와 지수 반등"
   ],
   [
    "반도체주 강세 힘입어",
    "국내 증시 동반 상승"
   ]
  ],
  "keys": [
   "기술 업종 강세",
   "헬스케어 약세",
   "국내 지수 반등"
  ]
 }
}
# 묶음 close (briefing/2026-11-18-pm.json 숫자 그대로) — 지수 칸 · 업종 표 · 종목 표
BRIEFING = {
 "trade_date": "2026-11-18",
 "close": {
  "indices": [
   {
    "name": "코스피",
    "close": 5067.44,
    "chg_pct": 1.99
   },
   {
    "name": "코스닥",
    "close": 662.81,
    "chg_pct": 1.96
   }
  ],
  "sectors": [
   {
    "name": "기술",
    "chg_pct": 3.64
   },
   {
    "name": "산업재",
    "chg_pct": -0.15
   },
   {
    "name": "경기 소비재",
    "chg_pct": 1.6
   },
   {
    "name": "헬스케어",
    "chg_pct": -2.39
   },
   {
    "name": "금융",
    "chg_pct": 1.51
   },
   {
    "name": "커뮤니케이션",
    "chg_pct": 0.05
   },
   {
    "name": "소재",
    "chg_pct": -1.46
   },
   {
    "name": "유틸리티",
    "chg_pct": 0.0
   }
  ],
  "movers": [
   {
    "name": "LG전자",
    "ticker": "066570",
    "chg_pct": 5.96
   },
   {
    "name": "삼성생명",
    "ticker": "032830",
    "chg_pct": 5.37
   },
   {
    "name": "SK스퀘어",
    "ticker": "402340",
    "chg_pct": 4.42
   },
   {
    "name": "SK하이닉스",
    "ticker": "000660",
    "chg_pct": 4.19
   },
   {
    "name": "삼성바이오로직스",
    "ticker": "207940",
    "chg_pct": -3.39
   },
   {
    "name": "현대차",
    "ticker": "005380",
    "chg_pct": 3.09
   },
   {
    "name": "LG화학",
    "ticker": "051910",
    "chg_pct": -3.03
   },
   {
    "name": "삼성화재",
    "ticker": "000810",
    "chg_pct": 2.85
   },
   {
    "name": "셀트리온",
    "ticker": "068270",
    "chg_pct": -2.58
   },
   {
    "name": "삼성SDI",
    "ticker": "006400",
    "chg_pct": -2.36
   },
   {
    "name": "삼성전자",
    "ticker": "005930",
    "chg_pct": 2.31
   },
   {
    "name": "삼성물산",
    "ticker": "028260",
    "chg_pct": 2.07
   },
   {
    "name": "에코프로",
    "ticker": "086520",
    "chg_pct": 2.07
   },
   {
    "name": "HD한국조선해양",
    "ticker": "009540",
    "chg_pct": -1.72
   },
   {
    "name": "한미반도체",
    "ticker": "042700",
    "chg_pct": 1.45
   },
   {
    "name": "한화에어로스페이스",
    "ticker": "012450",
    "chg_pct": 1.44
   },
   {
    "name": "고려아연",
    "ticker": "010130",
    "chg_pct": -1.36
   },
   {
    "name": "알테오젠",
    "ticker": "196170",
    "chg_pct": -1.21
   },
   {
    "name": "두산에너빌리티",
    "ticker": "034020",
    "chg_pct": 1.06
   },
   {
    "name": "에코프로비엠",
    "ticker": "247540",
    "chg_pct": 0.94
   },
   {
    "name": "하나금융지주",
    "ticker": "086790",
    "chg_pct": -0.72
   },
   {
    "name": "신한지주",
    "ticker": "055550",
    "chg_pct": -0.57
   },
   {
    "name": "HD현대중공업",
    "ticker": "329180",
    "chg_pct": -0.39
   },
   {
    "name": "SK텔레콤",
    "ticker": "017670",
    "chg_pct": -0.36
   },
   {
    "name": "한화오션",
    "ticker": "042660",
    "chg_pct": -0.33
   },
   {
    "name": "카카오",
    "ticker": "035720",
    "chg_pct": 0.32
   },
   {
    "name": "KB금융",
    "ticker": "105560",
    "chg_pct": -0.26
   },
   {
    "name": "포스코퓨처엠",
    "ticker": "003670",
    "chg_pct": 0.24
   },
   {
    "name": "카카오뱅크",
    "ticker": "323410",
    "chg_pct": -0.24
   },
   {
    "name": "NAVER",
    "ticker": "035420",
    "chg_pct": 0.18
   },
   {
    "name": "LG에너지솔루션",
    "ticker": "373220",
    "chg_pct": -0.16
   },
   {
    "name": "현대로템",
    "ticker": "064350",
    "chg_pct": 0.15
   },
   {
    "name": "기아",
    "ticker": "000270",
    "chg_pct": 0.11
   },
   {
    "name": "POSCO홀딩스",
    "ticker": "005490",
    "chg_pct": 0.0
   },
   {
    "name": "한국전력",
    "ticker": "015760",
    "chg_pct": 0.0
   }
  ]
 }
}


# 미국장(아침 편) 새 틀 목업 재료 — 수집기 11-18 아침 시험 글의 사실만으로 블로그가 손으로 다시 쓴 것(요청 28절 꼴)
SAMPLE_US = {
 "format": "story",
 "date": "2026-11-18",
 "slot": "am",
 "title": "대중 AI 칩 규제와 실적 경계에 3대 지수 일제히 하락",
 "summary": "미국의 대중 AI 칩 규제와 실적 경계에 뉴욕 3대 지수가 일제히 하락했습니다.",
 "overview": "미국의 대중국 AI 반도체 원격 접근 제한이 나오자 **11개 업종이 모두 내리며 3대 지수가 일제히 하락했습니다**. ==해외 데이터센터를 거친 우회 경로까지 막는 규정==이 반도체 공급망 전반에 경계심을 키웠고, 시스템 장애를 겪은 마이크로소프트와 금융주 약세가 낙폭을 더했습니다. 다만 장 마감 뒤 엔비디아가 시장 예상을 웃돈 3분기 실적을 내놓아, 오늘 한국장에서는 이 호실적이 반도체주 첫 반응에 얼마나 반영되는지가 관건입니다.",
 "drivers": [
  {
   "heading": "AI 칩 원격 접근 제한",
   "body": "미국 상무부가 **동남아시아 등 해외 데이터센터를 통한 중국의 첨단 AI 반도체 원격 접근을 차단하는 새 규정**을 내놓으면서 정규장의 반도체주가 눌렸습니다. 중국의 내년 예상 연산 능력 가운데 약 3분의 1이 해외 데이터센터 임대와 맞물려 있어, ==엔비디아의 아시아 매출과 데이터센터 투자 속도에 미칠 영향==에 관심이 모였습니다. 피에르 페라구는 중국 매출 비중이 약 10%에 그쳐 ==최근 매도세가 과도하다==고 본 반면, 스티브 아이즈먼(전 뉴버거 버먼 포트폴리오 매니저)은 우회 경로가 막히면 ==데이터센터 매출의 15~20%가 영향을 받을 수 있다==고 경고했습니다."
  },
  {
   "heading": "고금리 경계와 연준 경로",
   "body": "반도체 규제가 기술주를 누른 날, 증시 전반의 부담을 키운 것은 금리였습니다. 미국 10월 소매판매가 전월 대비 0.2% 늘며 소비가 이어지자 **미국 10년물 국채 금리가 5% 안팎의 높은 수준을 유지**했습니다. 물가와 소비가 쉽게 꺾이지 않으면서 ==12월 금리 인상 가능성==을 보는 시각(장재철 피나클 경제 연구소 대표)과 ==점진적인 금리 인하==를 예상하는 시각이 엇갈렸습니다."
  }
 ],
 "takeaway": "모든 업종이 내린 가운데 금융과 헬스케어의 낙폭이 컸고, 매수세는 브로드컴 등 일부 종목으로만 선별적으로 들어왔습니다.",
 "sectors": [],
 "pointsTitle": "오늘 한국장 관전 포인트",
 "points": [
  "지난밤 미국 금융 업종 1.82% 하락 · 마이크로소프트 2.65% 하락 뒤 한국장 첫 반응",
  "엔비디아 실적 뒤 반도체주 — 3분기 호실적이 국내 주가로 이어지는지"
 ],
 "oneLine": "미국의 대중국 AI 칩 원격 접근 제한과 전산망 장애 여파로 11개 업종이 모두 내렸고, 장 마감 뒤 엔비디아는 예상을 웃돈 3분기 실적을 발표했습니다.",
 "tickers": [
  "NVDA",
  "MSFT",
  "AVGO",
  "GOOGL",
  "LLY",
  "TSLA"
 ],
 "banner": {
  "titles": [
   [
    "대중 칩 규제에 약세",
    "엔비디아 호실적 확인"
   ],
   [
    "뉴욕 전 업종 하락",
    "반도체주 반응 주목"
   ],
   [
    "AI 칩 규제 여파",
    "엔비디아 실적 소화"
   ]
  ],
  "keys": [
   "미국 금융 업종 약세",
   "뉴욕 기술주 하락"
  ]
 }
}
# 묶음 close (briefing/2026-11-18-am.json 숫자 그대로)
BRIEFING_US = {
 "trade_date": "2026-11-17",
 "close": {
  "indices": [
   {
    "name": "S&P 500",
    "close": 7340.53,
    "chg_pct": -1.07
   },
   {
    "name": "나스닥 종합",
    "close": 24328.38,
    "chg_pct": -0.77
   },
   {
    "name": "다우존스",
    "close": 50759.42,
    "chg_pct": -1.68
   },
   {
    "name": "러셀 2000",
    "close": 2701.87,
    "chg_pct": -1.51
   }
  ],
  "sectors": [
   {
    "name": "금융",
    "chg_pct": -1.82
   },
   {
    "name": "헬스케어",
    "chg_pct": -1.74
   },
   {
    "name": "부동산",
    "chg_pct": -1.71
   },
   {
    "name": "커뮤니케이션",
    "chg_pct": -1.46
   },
   {
    "name": "필수소비재",
    "chg_pct": -1.36
   },
   {
    "name": "유틸리티",
    "chg_pct": -1.36
   },
   {
    "name": "소재",
    "chg_pct": -1.22
   },
   {
    "name": "경기소비재",
    "chg_pct": -0.89
   },
   {
    "name": "기술",
    "chg_pct": -0.68
   },
   {
    "name": "산업재",
    "chg_pct": -0.55
   },
   {
    "name": "에너지",
    "chg_pct": -0.52
   }
  ],
  "movers": [
   {
    "name": "마이크로소프트",
    "ticker": "MSFT",
    "chg_pct": -2.65
   },
   {
    "name": "브로드컴",
    "ticker": "AVGO",
    "chg_pct": 2.43
   },
   {
    "name": "알파벳",
    "ticker": "GOOGL",
    "chg_pct": -1.52
   },
   {
    "name": "일라이 릴리",
    "ticker": "LLY",
    "chg_pct": -1.17
   },
   {
    "name": "버크셔 해서웨이",
    "ticker": "BRK-B",
    "chg_pct": -0.91
   },
   {
    "name": "메타",
    "ticker": "META",
    "chg_pct": -0.86
   },
   {
    "name": "애플",
    "ticker": "AAPL",
    "chg_pct": -0.5
   },
   {
    "name": "엔비디아",
    "ticker": "NVDA",
    "chg_pct": -0.44
   },
   {
    "name": "아마존",
    "ticker": "AMZN",
    "chg_pct": -0.37
   },
   {
    "name": "테슬라",
    "ticker": "TSLA",
    "chg_pct": 0.13
   }
  ]
 }
}
OUT_US = os.path.join(BASE, "output", "mock_story_us.html")


SAMPLES = os.path.join(BASE, "samples")   # 수집기 최신 시험 글 · 묶음 (git 제외 — 수집기가 시험 글을 비공개로 둠). 없으면 위 SAMPLE(11-17)


def latest_samples():
    """samples/{날짜}-{am|pm}.column.json + .briefing.json 중 가장 새 날짜 → {slot: (column, briefing, key)}."""
    import json
    if not os.path.isdir(SAMPLES):
        return {}
    keys = sorted({f[:-len(".column.json")] for f in os.listdir(SAMPLES) if f.endswith(".column.json")})
    out = {}
    for k in keys:
        b = os.path.join(SAMPLES, f"{k}.briefing.json")
        if os.path.exists(b):
            out[k[-2:]] = (json.load(open(os.path.join(SAMPLES, f"{k}.column.json"), encoding="utf-8")), json.load(open(b, encoding="utf-8")), k)
    return out


def banner_for(col, br):
    """배너 = 발행기와 같은 banner.make, AI 없이 기본 그림(목업은 Workers AI 를 쓰지 않는다)."""
    import banner as BN
    info = BN.make(br, col, out_dir=os.path.join(BASE, "output", "story-mock"), use_ai=False)
    return ("story-mock/" + info["ref"]) if info else None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    from story_render import render, titles
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    import json
    import shutil   # 목업 = output/story-mock/mood/ 에 복사해 상대 주소로(태블릿 목업 서버에서도 보이게). 발행 = gh-pages images/commentary/mood/
    shutil.copytree(os.path.join(BASE, "static", "mood"), os.path.join(BASE, "output", "story-mock", "mood"), dirs_exist_ok=True)
    mood = "story-mock/mood/"
    for col, br, out in ((SAMPLE, BRIEFING, OUT), (SAMPLE_US, BRIEFING_US, OUT_US)):   # 한국장(저녁 편) · 미국장(아침 편)
        lf = os.path.join(BASE, "..", "stock-lists", "output", "lists", "kr" if col["slot"] == "pm" else "us", "_lists.json")   # 종목 모아보기 목업이 쓰는 로컬 목록 파일
        lists = {str(r.get("t") or "").upper(): r for r in json.load(open(lf, encoding="utf-8"))["rows"]} if os.path.exists(lf) else {}
        _, h, _m = render(col, br, lists=lists, mood_base=mood, banner_url=banner_for(col, dict(br, date=col["date"], slot=col["slot"])), banner_alt="AI 생성 이미지")
        print(dk.write_mock(h, out, titles(col)[0]) or "index.html 없음 — 목업 못 만듦")
