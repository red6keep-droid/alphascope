"""인물 발언 구획 — 미국 종목 페이지 `오늘` 탭(뉴스 아래) · 미국 증시 리포트 `오늘` 탭(뉴스 아래) (2026-11-07 사용자, 목업).

재료 = 인물 레이더가 쓰는 people_mentions.json (people-radar/stock_mentions.py). 모양 = 공용 뉴스 카드(news_item, 인물 발언 글과 같음).
3줄 보이고 나머지는 접기, 맨 아래 `주요 인물 발언 전체 보기` 링크. 발언이 없으면 구획을 통째로 뺀다(빈 답 금지).
"""

import datetime
import json
import re
import os

import design_kit as dk

KST = datetime.timezone(datetime.timedelta(hours=9))
PATH = os.environ.get("PEOPLE_MENTIONS_JSON") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "people-radar", "output", "state", "people_mentions.json")
ALL_URL = "https://alpha-scope.blogspot.com/search/label/%EC%9D%B8%EB%AC%BC%20%EB%B0%9C%EC%96%B8"   # 라벨 `인물 발언` 목록 — 발행 때 최신 글 주소로
SHOWN = 5   # 5건 + 10건씩 더 보기 (2026-11-07 사용자 P340, 옛 3)
TOPIC_KO = {"Trade": "무역", "Fed": "연준 · 금리", "Tax": "세금", "Energy": "에너지", "Immigration": "이민", "Regulation": "규제",
            "Geopolitics": "지정학", "Company": "기업", "Stock Call": "종목 의견", "Position": "매매", "Sector Call": "업종 의견",
            "Macro Warning": "거시 경고", "Market Outlook": "시장 전망", "Policy": "정책 의견", "Product": "제품", "Investment": "투자",
            "Earnings": "실적", "Deal": "거래 · 제휴", "Industry View": "업계 평가", "Politics": "정치"}   # people-radar/config.TOPIC_KO 와 같게
DIR_KO = {"positive": "긍정", "negative": "부정", "neutral": "중립"}
_data = None


def load():
    global _data
    if _data is None:
        try:
            with open(PATH, encoding="utf-8") as f:
                _data = json.load(f)
        except (OSError, ValueError):
            _data = {}
    return _data


def _when(iso):
    dt = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).astimezone(KST)
    return dt.strftime("%m.%d %H:%M")


def _row(it):
    meta = [_when(it["at"])]
    if it["n_reports"]:
        meta.append(f"보도 {it['n_reports']}곳")
    if it["publisher"] and it["publisher"] != "googlenews" and not it["primary"] and re.fullmatch(r"[\x20-\x7E가-힣·]+", it["publisher"]):   # 아랍어 등 못 읽는 매체명은 뺀다
        meta.append(it["publisher"])
    d = it["direction"]
    pills = [dk.pill(dk.ISSUE_KO.get(it.get("issue") or "OTHER", "그 밖"), bare=True),   # 분야 라벨 = 기록 이슈 코드 이름 (2026-11-07 사용자 P339, 옛: 인물 주제)
             dk.pill(DIR_KO.get(d, d), d if d in ("positive", "negative") else "neutral", bare=True),
             dk.pill(f"강도 {it['intensity']}", bare=True)]
    return dk.news_item(dk.esc(it["headline"]), it["url"], it["detail"], (), " ".join(pills), meta)


def _list(ids, items):
    rows = [_row(items[i]) for i in ids if i in items]
    if not rows:
        return ""
    out = dk.more_list(rows, "인물 발언", SHOWN, indent=dk.ALIGN_PX)
    out += (f'<p style="margin:0 0 8px;padding:0 {dk.ALIGN_PX}px;font-size:{dk.TINY};line-height:{dk.LH_TINY};">'
            f'<a href="{ALL_URL}" style="color:#111;font-weight:700;text-decoration:none;">주요 인물 발언 전체 보기 ›</a></p>')
    return out


def for_stock(sym):
    """종목 페이지 — 최근 7일 이 종목을 지목한 발언. 없으면 ""."""
    d = load()
    return _list(d.get("by_stock", {}).get(sym, []), d.get("items", {}))


def for_market():
    """미국 증시 리포트 — 최근 24시간 시장 관련도 높은 발언(인물마다 하나). 없으면 ""."""
    d = load()
    return _list(d.get("market", []), d.get("items", {}))
