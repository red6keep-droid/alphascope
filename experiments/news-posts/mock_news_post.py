"""Newfact 주요 기사 · 한국 기사 제목 묶음 — 블로그 화면 목업 (2026-11-23 사용자 "여기서 새로 그려").

    python experiments/news-posts/mock_news_post.py

- 재료: samples/posts.json · samples/headlines.json 이 있으면 그것(수집기 블로그 저장소에서 받은 실제 자료 — fetch_samples.py, git 제외).
  없으면 아래 SAMPLE_POST(11-18 시황 해설 시험 글의 사실로 블로그가 손으로 쓴 예시) · SAMPLE_HEADLINES(지어낸 예시, 매체 · 주소 가짜).
- 같은 날 시장 움직임 = yfinance 일봉(코스피 · 코스닥 · 종목). 장중 값은 쓰지 않는다(오늘은 15:40 KST 뒤에만).
- 출력: output/mock_news_post*.html · output/mock_news_headlines.html. AI 0 · 쓰기 0.
"""
import datetime
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, ".."))
import design_kit as dk  # noqa: E402
import news_render as NR  # noqa: E402

OUT = os.path.join(BASE, "output")
SAMPLES = os.path.join(BASE, "samples")
LISTS = {mk: os.path.join(BASE, "..", "stock-lists", "output", "lists", mk, "_lists.json") for mk in ("kr", "us")}   # 한국 + 미국 (2026-11-23 사용자 "미국 종목도")

SAMPLE_POST = {
    "id": "sample-1",
    "title": "엔비디아 호실적 뒤 삼성전자 · SK하이닉스 반등, 외국인 매도 구조는 남아",
    "summary": "엔비디아가 3분기 실적과 4분기 전망을 내놓은 뒤 나흘 내리던 삼성전자와 SK하이닉스가 함께 반등했습니다. 외국인 순매도가 두 종목에 몰리는 구조는 그대로입니다.",
    "body": ("엔비디아가 **3분기 매출 1,158억 달러**를 발표하고 4분기 매출 전망을 약 1,300억 달러로 내놓았습니다. "
             "==AI 데이터센터 투자가 이어진다는 숫자==가 나오면서, 앤트로픽 상장에 자금이 쏠릴 것이라는 우려로 나흘 연속 내렸던 국내 반도체주에 매수세가 들어왔습니다.\n\n"
             "삼성전자와 SK하이닉스는 이날 함께 **반등**했습니다. 두 종목 주가는 고점보다 평균 55% 낮아진 상태였고, "
             "==과도한 우려가 이미 주가에 반영됐다는 분석==(이창민 KB증권 연구원)이 나왔습니다.\n\n"
             "다만 올해 외국인 순매도의 85%가 두 종목에 몰려 있습니다. "
             "==MSCI 지수 비중 상한을 넘을 때마다 매도가 나오는 구조==(하나증권)도 **그대로 남아 있습니다**."),
    "date": "2026-11-18", "cat": "AI_CAPEX", "direction": "up", "stage": "confirmed",
    "stocks": [{"name": "삼성전자", "code": "005930"}, {"name": "SK하이닉스", "code": "000660"}, {"name": "엔비디아", "code": ""}],   # 미국 종목 = 수집기처럼 코드 빈 값
    "sector": "기술", "slug": "nvidia-earnings-samsung-hynix-rebound", "version": 2,
}


def _fake(no, ev, cat, title, h, m):
    return {"title": title, "outlet": f"예시 매체 {no}", "url": f"https://www.outlet-{no}.example/news/{1000 + no * 7 + h}",
            "publishedAt": f"2026-11-18T{h:02d}:{m:02d}:00+09:00", "foundAt": None, "event": ev, "cat": cat, "stocks": []}


SAMPLE_HEADLINES = [{"run": "sample", "part": 1, "parts": 1, "version": 1, "items": [
    _fake(1, "반도체 반등", "AI_CAPEX", "가상 반도체 대형주 일제히 반등, 외국인 닷새 만에 순매수", 15, 41),
    _fake(2, "반도체 반등", "AI_CAPEX", "예시 기사: 메모리 업황 우려 덜며 반도체주 강세", 15, 52),
    _fake(3, "반도체 반등", "AI_CAPEX", "예시 기사: 반도체 두 종목이 지수 상승의 절반 이상 차지", 16, 5),
    _fake(4, "정책금리 동결 전망", "RATES_FED", "가상 중앙은행, 다음 주 금리 동결 무게", 14, 10),
    _fake(5, "정책금리 동결 전망", "RATES_FED", "예시 기사: 환율 부담에 금리 인하 미룰 듯", 13, 2),
    _fake(6, "가상 제조사 A 공장 증설", "CORP_EVENT", "가상 제조사 A, 해외 공장 증설 계약 체결", 11, 30),
    _fake(7, "가상 제조사 A 공장 증설", "CORP_EVENT", "예시 기사: 제조사 A 증설 규모 1조 원대", 12, 15),
    _fake(8, "대출 규제 완화 검토", "REGULATION", "가상 금융당국, 대출 규제 완화 검토", 10, 0),
    _fake(9, "유가 하락", "OIL_ENERGY", "예시 기사: 국제 유가 사흘째 하락", 9, 20),
    _fake(10, "유가 하락", "OIL_ENERGY", "예시 기사: 원유 재고 늘며 유가 약세", 9, 45),
    _fake(11, "유가 하락", "OIL_ENERGY", "예시 기사: 정유주 약세, 유가 내림세 영향 지켜봐야", 10, 40),
    _fake(12, "유가 하락", "OIL_ENERGY", "예시 기사: 항공주는 유가 하락에 강세", 11, 5),
    _fake(13, "유가 하락", "OIL_ENERGY", "예시 기사: 산유국 증산 논의 이어져", 8, 30),
    _fake(14, "가상 지수 마감", "MARKET_STRUCTURE", "가상 지수 2% 오른 채 마감", 15, 35),
    _fake(15, "환율 하락", "FX_GLOBAL", "예시 기사: 원 · 달러 환율 1,400원 아래로", 15, 50),
]}]


def load(name, fallback):
    p = os.path.join(SAMPLES, name)
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8")), True
    return fallback, False


_cache = {}


def closes_of(sym):
    if sym not in _cache:
        import yfinance as yf
        h = yf.Ticker(sym).history(period="1y", auto_adjust=False)["Close"].dropna()
        _cache[sym] = [(str(i.date()), float(v)) for i, v in h.items()]
    return _cache[sym]


def closed_through():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    return now.strftime("%Y-%m-%d") if now.hour * 60 + now.minute >= 15 * 60 + 40 else (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(OUT, exist_ok=True)
    lists = {r["t"]: dict(r, mk=mk) for mk, p in LISTS.items() if os.path.exists(p) for r in json.load(open(p, encoding="utf-8"))["rows"]}
    posts, real = load("posts.json", [SAMPLE_POST])
    print("글 재료:", "수집기 실제 글" if real else "예시 글", len(posts), "편")
    upto = closed_through()
    jobs = [("mock_news_post.html" if i == 0 else f"mock_news_post_{i + 1}.html", post)
            for i, post in enumerate(sorted(posts, key=lambda p: str(p.get("createdAt") or p["date"]), reverse=True))]
    if real:   # 실제 글에 종목이 없을 때도 종목 줄(한국 + 미국)을 볼 수 있게 예시 글도 함께
        jobs.append(("mock_news_post_example.html", SAMPLE_POST))
    for name, post in jobs:
        market = NR.same_day(post, lists, closes_of, upto)
        _, html, meta = NR.render(post, market, lists)
        out = os.path.join(OUT, name)
        print(dk.write_mock(html, out, NR.titles(post)[0]) or "index.html 없음", "· 기준", meta["basis"], "· 종목", [s["name"] for s in market["stocks"]])
    docs, real_h = load("headlines.json", SAMPLE_HEADLINES)
    day = max(str(it.get("publishedAt") or it.get("foundAt") or "")[:10] for d in docs for it in d.get("items") or [])
    sec = NR.headlines_section(docs, day)
    page = dk.WRAP_OPEN + sec + dk.WRAP_CLOSE
    print(dk.write_mock(page, os.path.join(OUT, "mock_news_headlines.html"), "한국 증시 리포트 · 뉴스 (한국 기사 묶음)"),
          "·", "수집기 실제 제목" if real_h else "예시 제목", "·", day)
