"""Firestore `summaries` → output/materials.json (한 묶음 날짜 `edition` 의 영상별 요약).

인증: 환경 변수 YTB_FIRESTORE_KEY(서비스 계정 키 JSON, GitHub Secret) → 없으면 gcloud 기본 인증(PC, red6keep 계정).
읽기만 한다 (권한도 읽기 전용). 자막 원문(transcripts)은 읽지 않는다 — 글에 쓰지 않는다.

    python collect.py                      # 오늘(KST) edition 전체
    python collect.py --edition 2026-10-23 --cutoff 07:55
    python collect.py --fixture            # Firestore 없이 시험용 가짜 재료
"""

import argparse
import datetime
import json
import os
import sys

import config

KEEP = ("edition", "date", "channelName", "title", "url", "publishedAt", "durationSec", "issues", "categories", "tickers", "sectors",
        "keywords", "speakers", "model")   # summary · numbers 는 안 가져온다 — 글에 쓰지 않는 것은 받지도 않는다 (4-2)


def _client():
    from google.cloud import firestore
    raw = os.environ.get(config.KEY_ENV, "").strip()
    if raw:
        from google.oauth2 import service_account
        info = json.loads(raw) if raw.startswith("{") else json.load(open(raw, encoding="utf-8"))
        creds = service_account.Credentials.from_service_account_info(info)
        return firestore.Client(project=config.FIRESTORE_PROJECT, credentials=creds)
    return firestore.Client(project=config.FIRESTORE_PROJECT)


def _iso(v):
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def fetch(edition, cutoff=None):
    """cutoff: (hour, minute) KST — createdAt 이 그 시각까지인 것만 (1차 글). None 이면 전부."""
    from google.cloud.firestore_v1.base_query import FieldFilter
    db = _client()
    docs = db.collection("summaries").where(filter=FieldFilter("edition", "==", edition)).stream()
    cut = None
    if cutoff:
        y, m, d = (int(x) for x in edition.split("-"))
        cut = datetime.datetime(y, m, d, cutoff[0], cutoff[1], tzinfo=config.KST)
    items = []
    for doc in docs:
        d = doc.to_dict() or {}
        created = d.get("createdAt")
        if cut is not None and created is not None and created > cut:
            continue
        rec = {k: d.get(k) for k in KEEP}
        rec["id"] = doc.id
        rec["createdAt"] = _iso(created)
        rec["issues"] = [i for i in (rec.get("issues") or []) if isinstance(i, dict)]
        items.append(rec)
    items.sort(key=lambda r: r.get("publishedAt") or "")
    return items


def save(items, edition, path=None):
    path = path or os.path.join(config.OUTPUT_DIR, "materials.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"edition": edition, "fetched_at": datetime.datetime.now(config.KST).isoformat(), "items": items}, f, ensure_ascii=False, indent=1)
    from collections import Counter
    ch = Counter(r.get("channelName") for r in items)
    print(f"[collect] edition {edition}: {len(items)}건 · " + " · ".join(f"{k} {v}" for k, v in ch.most_common()) + f" → {path}")
    return path


def fixture(edition):
    """시험용 — 실제 데이터 모양(2026-10-22 읽기)과 같은 칸. 숫자 · 문장은 가짜."""
    def it(i, ch, title, issues, tickers, speakers=(), created="06:30"):
        return {"id": f"vid{i:02d}xxxxxxx", "edition": edition, "date": edition, "channelName": ch, "title": title,
                "url": f"https://www.youtube.com/watch?v=vid{i:02d}xxxxxxx", "publishedAt": f"{edition}T{created}:00Z", "durationSec": 600,
                "issues": issues, "categories": sorted({x["category"] for x in issues}), "tickers": tickers, "sectors": [], "keywords": [],
                "speakers": list(speakers), "model": "fixture", "createdAt": f"{edition}T{created}:00+09:00"}
    def iss(cat, topic, stance, surprise="unknown", scope="market", tickers=(), country="US", note="가짜 주장"):
        return {"category": cat, "topic": topic, "stance": stance, "surprise": surprise, "scope": scope, "tickers": list(tickers), "country": country, "horizon": "weeks", "note": note}
    items = [
        it(1, "CNBC Television", "Fed officials signal patience on cuts", [iss("RATES_CB", "연준 12월 인하 기대 후퇴", "bearish", "surprise")], ["SPY"], ["Steve Liesman (CNBC)"]),
        it(2, "블룸버그 텔레비전", "Markets price fewer Fed cuts", [iss("RATES_CB", "12월 금리 인하 전망 약화", "bearish"), iss("AI_CAPEX", "AI 투자 과열 논쟁", "neutral", scope="sector", tickers=["NVDA", "MSFT"])], ["NVDA", "MSFT", "SPY"]),
        it(3, "폭스 비즈니스", "Musk merger talk", [iss("CORP_EVENT", "스페이스X 테슬라 합병설", "bullish", "surprise", "stock", ["TSLA", "SPACEX(비상장)"])], ["TSLA", "SPACEX(비상장)"]),
        it(4, "CNBC Television", "Chip stocks rally on data center demand", [iss("AI_CAPEX", "데이터센터 수요 강세", "bullish", scope="sector", tickers=["NVDA", "AMD"])], ["NVDA", "AMD"], ["Dan Ives (Wedbush)"]),
        it(5, "WSJ", "Oil slips on supply", [iss("ENERGY_COMMODITY", "유가 하락 공급 증가", "bearish", tickers=["USO"])], ["USO", "XOM"]),
        it(6, "CNBC Television", "Tariff talks with China", [iss("TARIFF_TRADE", "미중 관세 협상", "neutral", country="CN")], ["AAPL"]),
        it(7, "당잠사", "밤사이 미국장 정리와 오늘 한국장", [iss("AI_CAPEX", "반도체 수요 한국 영향", "bullish", scope="sector", tickers=["삼성전자(KR)", "SK하이닉스(KR)"], country="KR"), iss("FX", "원달러 환율 상승", "bearish", country="KR")], ["삼성전자(KR)", "SK하이닉스(KR)"], ["당잠사"], created="07:40"),
        it(8, "CNBC Mad Money", "Cramer on chips", [iss("AI_CAPEX", "반도체 실적 기대", "bullish", scope="stock", tickers=["NVDA", "AVGO"])], ["NVDA", "AVGO", "RKLB"], ["Jim Cramer (CNBC)"], created="09:10"),
        it(9, "증시각도기", "미국시황 — 금리와 반도체", [iss("RATES_CB", "연준 인하 기대 후퇴", "bearish"), iss("AI_CAPEX", "반도체 강세 지속", "bullish", scope="sector", tickers=["NVDA"])], ["NVDA", "SOXX"], ["증시각도기"], created="09:50"),
    ]
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edition", default=config.today_kst())
    ap.add_argument("--cutoff", help="HH:MM (KST) — 이 시각까지 들어온 것만")
    ap.add_argument("--fixture", action="store_true")
    a = ap.parse_args()
    cutoff = tuple(int(x) for x in a.cutoff.split(":")) if a.cutoff else None
    items = fixture(a.edition) if a.fixture else fetch(a.edition, cutoff)
    if cutoff and a.fixture:
        items = [r for r in items if r["createdAt"][11:16] <= f"{cutoff[0]:02d}:{cutoff[1]:02d}"]
    save(items, a.edition)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
