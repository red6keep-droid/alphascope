"""간단 정보 기준표 — 853종목 한글 이름 · 업종 · 세부 업종 (2026-11-14, 기획 비공개 기획/회원-내-종목-기획.md 6-3-2 ②).

    .venv/bin/python experiments/stock-quick/build_ref.py        # ref/quick_ref.json 만들기 · 채우기 (분기 1회, universe_all 다시 만든 뒤)

- 한국 이름 = DART 고유번호 목록의 한글 회사명(호출 1번, AI 0).
- 미국 이름 = 정식 종목 이름(universe.py) → 위키데이터 한국어 이름(SPARQL 1번) → 빈 것만 AI(50개씩).
- 업종 = 미국은 GICS 11 → 우리 업종 이름(taxonomy.SECTORS, 고정 표). 한국 업종 영어 이름(로고 메타데이터)은 AI 가 11 업종 중 하나로.
- 세부 업종 = 영어 이름(미국 GICS 126 · 한국 71)을 AI 가 한국어로 한 번 → 표에 저장, 다시 안 부른다.
- AI 사슬 = json-backup-first(Groq 먼저, Gemini lite 맨 뒤 — 운영지침 3-2). 이미 채운 칸은 건너뛰므로 다시 돌려도 호출 0.
- 바깥 요청에 개인 정보를 넣지 않는다(User-Agent 일반 이름).
"""

import datetime
import io
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(EXP)
OUT = os.path.join(EXP, "ref", "quick_ref.json")
UA = {"User-Agent": "AlphaScope-ref/0.1"}
sys.path.insert(0, EXP)
sys.path.insert(0, os.path.join(EXP, "stock-radar"))
sys.path.insert(0, os.path.join(EXP, "kr-stocks"))


def load_env():
    p = os.path.join(ROOT, ".env")
    if not os.path.exists(p):
        return
    for line in open(p, encoding="utf-8"):
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.rstrip("\n").split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"\''))


load_env()
import taxonomy  # noqa: E402
import universe as U  # noqa: E402
import universe_kr as K  # noqa: E402
from llm_chain import LLMPool  # noqa: E402

# 위키데이터 · AI 이름 고침표 (2026-11-14 눈으로 검토) — 여기 있는 것이 가장 우선. 틀린 이름을 찾으면 여기에 더한다
KO_FIX = {
    "GPC": "제뉴인 파츠", "ES": "에버소스 에너지", "ATO": "애트모스 에너지", "AMCR": "앰코어", "ALLE": "알레기온",
    "CIEN": "시에나", "WM": "웨이스트 매니지먼트", "SYY": "시스코(Sysco)", "KDP": "큐리그 닥터페퍼", "TWLO": "트윌리오",
    "OKE": "원오크", "IDXX": "아이덱스 래버러토리스", "IEX": "아이덱스 코퍼레이션", "FTV": "포티브",
    "NDSN": "노드슨", "PWR": "퀀타 서비스", "RSG": "리퍼블릭 서비스", "Q": "큐니티", "HWM": "하우멧 에어로스페이스",
    "CASY": "케이시스", "ELV": "엘리번스 헬스", "CB": "처브", "DHI": "D.R. 호튼", "BG": "번지", "TECH": "바이오테크니",
    "HSIC": "헨리 샤인", "GWW": "W.W. 그레인저", "AXON": "액손", "CBOE": "Cboe 글로벌 마켓", "PKG": "패키징 코퍼레이션 오브 아메리카",
    "L": "로우스 코퍼레이션", "C": "씨티그룹", "CNP": "센터포인트 에너지", "APTV": "앱티브", "SPGI": "S&P 글로벌", "TKO": "TKO 그룹",
    "OTIS": "오티스", "XYZ": "블록", "SYK": "스트라이커", "AON": "에이온", "ADP": "ADP", "AKAM": "아카마이", "FSLR": "퍼스트 솔라",
    "GEN": "젠 디지털", "ADBE": "어도비", "ON": "온세미", "FFIV": "F5", "MRK": "머크", "CRM": "세일즈포스", "BX": "블랙스톤",
    "F": "포드", "OXY": "옥시덴탈 페트롤리엄", "MNST": "몬스터 베버리지", "UNH": "유나이티드헬스 그룹", "BNY": "BNY",
    "ROK": "로크웰 오토메이션", "KKR": "KKR", "LULU": "룰루레몬", "FOX": "폭스 (B주)", "FOXA": "폭스 (A주)",
    "NWS": "뉴스 코프 (B주)", "NWSA": "뉴스 코프 (A주)", "SYK": "스트라이커", "GOOG": "알파벳 (C주)", "P": "에버퓨어",
}

GICS = {"Information Technology": "기술", "Financials": "금융", "Energy": "에너지", "Health Care": "헬스케어",
        "Consumer Staples": "필수 소비재", "Consumer Discretionary": "경기 소비재", "Utilities": "유틸리티",
        "Industrials": "산업재", "Materials": "소재", "Real Estate": "부동산", "Communication Services": "커뮤니케이션"}
SECTOR_NAMES = list(taxonomy.SECTORS.values())
KO_TAIL = re.compile(r"\s*(코퍼레이션|인코퍼레이티드|주식회사|홀딩스 인코퍼레이티드|Inc\.?|Corp\.?)$")
assert set(GICS.values()) == set(SECTOR_NAMES), "taxonomy 업종 이름과 GICS 표가 어긋남"


def dart_names():
    key = (os.environ.get("DART_API_KEY") or "").split(",")[0].strip()
    z = requests.get("https://opendart.fss.or.kr/api/corpCode.xml", params={"crtfc_key": key}, timeout=120)
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(z.content)).read("CORPCODE.xml"))
    out = {}
    for el in root.iter("list"):
        sc = (el.findtext("stock_code") or "").strip()
        if sc:
            out[sc] = {"name": el.findtext("corp_name").strip(), "corp": el.findtext("corp_code").strip()}
    return out


def wikidata_ko():
    q = """SELECT ?t ?ko WHERE { ?c p:P414 ?st . ?st ps:P414 ?ex ; pq:P249 ?t . VALUES ?ex { wd:Q13677 wd:Q82059 }
      ?c rdfs:label ?ko . FILTER(LANG(?ko) = "ko") }"""
    r = requests.get("https://query.wikidata.org/sparql", params={"query": q, "format": "json"},
                     headers={**UA, "Accept": "application/sparql-results+json"}, timeout=120)
    r.raise_for_status()
    ko = {}
    for b in r.json()["results"]["bindings"]:
        ko.setdefault(b["t"]["value"].replace(".", "-"), b["ko"]["value"])
    return ko


def ai_map(pool, items, prompt_head, check):
    """items = [(key, 영어)] → {key: 값} 50개씩. check(값) 이 False 면 그 칸은 버린다(다음 실행에 다시)."""
    got = {}
    for i in range(0, len(items), 50):
        part = items[i:i + 50]
        body = "\n".join(f"{k}\t{en}" for k, en in part)
        try:
            val = pool.generate_json(prompt_head + "\n\n" + body, max_tokens=4000)
        except Exception as e:  # noqa: BLE001
            print("AI 실패 — 다음 실행에 다시", str(e)[:120])
            continue
        for k, _ in part:
            v = val.get(k) if isinstance(val, dict) else None
            if v is not None and check(v):
                got[k] = v
    return got


def main():
    uni = json.load(open(os.path.join(EXP, "ref", "universe_all.json"), encoding="utf-8"))
    ref = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    us, kr = ref.setdefault("us", {}), ref.setdefault("kr", {})
    sub_ko = ref.setdefault("sub_ko", {})          # 영어 세부 업종 → 한국어
    kr_sector = ref.setdefault("kr_sector", {})    # 한국 영어 업종 → 우리 업종(11)
    pool = None

    def get_pool():
        nonlocal pool
        if pool is None:
            pool = LLMPool("json-backup-first", label="quick-ref")
        return pool

    # 한국 — DART 한글 이름
    dn = dart_names()
    for r in uni["kr"]:
        e = kr.setdefault(r["sym"], {})
        e["market"] = r["market"]
        e["en"] = r["name"]
        e["industry_en"] = r.get("industry") or ""
        full = K.BY_SYM.get(r["sym"])
        if full:
            e["ko"] = full[1]
        elif r["code"] in dn:
            e["ko"] = dn[r["code"]]["name"]
        if r["code"] in dn:
            e["corp"] = dn[r["code"]]["corp"]
        if full:
            e["full"] = True
    # 미국 — 정식 이름 → 위키데이터
    wk = wikidata_ko()
    for r in uni["us"]:
        e = us.setdefault(r["sym"], {})
        e["en"], e["sector"], e["sub_en"] = r["name"], GICS[r["sector"]], r["sub"]
        full = U.BY_SYM.get(r["sym"])
        if full:
            e["ko"], e["full"] = full[1], True
        elif not e.get("ko") and r["sym"] in wk:
            e["ko"], e["ko_src"] = wk[r["sym"]], "wikidata"

    # AI 1 — 위키데이터에 없는 미국 이름
    miss = [(s, e["en"]) for s, e in us.items() if not e.get("ko")]
    if miss:
        head = ("미국 상장사 영어 이름을 한국 언론이 흔히 쓰는 한글 이름으로 옮겨라. 법인 꼬리(Inc · Corp · Holdings 등)는 뺀다. "
                "한국에서 영어 그대로 쓰는 이름(예: 3M)은 그대로. 입력 줄 = 티커<TAB>영어 이름. "
                "JSON 객체 하나만: {\"티커\": \"한글 이름\"}.")
        got = ai_map(get_pool(), miss, head, lambda v: isinstance(v, str) and 0 < len(v) <= 30)
        for s, v in got.items():
            us[s]["ko"], us[s]["ko_src"] = v.strip(), "ai"
    # AI 2 — 세부 업종 한국어(미국 GICS + 한국 영어 업종)
    subs = sorted({e["sub_en"] for e in us.values()} | {e["industry_en"] for e in kr.values() if e.get("industry_en")})
    miss = [(f"s{i}", en) for i, en in enumerate(subs) if en not in sub_ko]
    if miss:
        head = ("주식 업종 분류 이름(영어)을 짧은 한국어 업종 이름으로 옮겨라(예: Semiconductors → 반도체, "
                "Integrated Oil & Gas → 종합 석유 · 가스). 2 ~ 12자, 약어 금지. 입력 줄 = 번호<TAB>영어. "
                "JSON 객체 하나만: {\"번호\": \"한국어\"}.")
        got = ai_map(get_pool(), miss, head, lambda v: isinstance(v, str) and 0 < len(v) <= 20)
        for k, en in miss:
            if k in got:
                sub_ko[en] = got[k].strip()
    # AI 3 — 한국 영어 업종 → 우리 업종 11 중 하나
    inds = sorted({e["industry_en"] for e in kr.values() if e.get("industry_en")})
    miss = [(f"i{i}", en) for i, en in enumerate(inds) if en not in kr_sector]
    if miss:
        head = ("업종 이름(영어)마다 아래 11개 업종 중 가장 맞는 하나를 골라라: " + " · ".join(SECTOR_NAMES) +
                ". 입력 줄 = 번호<TAB>영어. JSON 객체 하나만: {\"번호\": \"업종\"}.")
        got = ai_map(get_pool(), miss, head, lambda v: v in SECTOR_NAMES)
        for k, en in miss:
            if k in got:
                kr_sector[en] = got[k]
    # 정리 — 한국 업종 · 세부 업종 칸
    for s, e in kr.items():
        full = K.BY_SYM.get(s)
        e["sector"] = kr_sector.get(e.get("industry_en", ""))
        e["sub"] = sub_ko.get(e.get("industry_en", ""))
        if full and full[3]:
            e["sub_ours"] = full[3]   # 정식 종목은 한국 종목 페이지의 업종 이름도 같이
    for s, e in us.items():
        e["sub"] = sub_ko.get(e["sub_en"])
        if e.get("ko_src"):   # 위키데이터 · AI 이름의 법인 꼬리(타깃 코퍼레이션 → 타깃) — 정식 종목 이름은 손대지 않는다
            e["ko"] = KO_TAIL.sub("", e["ko"]).strip() or e["ko"]
        if s in KO_FIX and not e.get("full"):
            e["ko"], e["ko_src"] = KO_FIX[s], "fix"
    seen = {}
    for m, grp in (("us", us), ("kr", kr)):
        for sym, e in grp.items():
            seen.setdefault(e.get("ko"), []).append(sym)
    ref["dup_names"] = {k: v for k, v in seen.items() if k and len(v) > 1}   # 같은 한글 이름 두 종목 — 검색 · 이름 찾기에서 헷갈린다
    ref["built"] = datetime.date.today().isoformat()
    ref["ai_calls"] = pool.calls if pool else 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(ref, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    hole = {
        "미국 이름": sum(1 for e in us.values() if not e.get("ko")),
        "한국 이름": sum(1 for e in kr.values() if not e.get("ko")),
        "세부 업종": sum(1 for e in list(us.values()) + list(kr.values()) if not e.get("sub")),
        "한국 업종": sum(1 for e in kr.values() if not e.get("sector")),
    }
    print(f"저장 {OUT} · AI {ref['ai_calls']}회 · 빈 칸 {hole} · 겹치는 이름 {ref['dup_names']}")


if __name__ == "__main__":
    main()
