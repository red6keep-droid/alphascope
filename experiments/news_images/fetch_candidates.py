"""뉴스 글 그림 후보 받기 — 사용자 검수용으로 맥 폴더에 정리.

    python experiments/news_images/fetch_candidates.py                 # 전부
    python experiments/news_images/fetch_candidates.py --only topics   # 주제 그림만
    python experiments/news_images/fetch_candidates.py --only companies --limit 20

출처 = 위키미디어 공용(Wikimedia Commons)만. 공용은 자유 이용 그림만 받는 곳이고, 그중에서도
상업 이용이 되는 이용 조건(퍼블릭 도메인 · CC0 · CC BY · CC BY-SA)만 받는다. 나무위키는 비영리 조건이라 쓰지 않는다.
회사 = 위키데이터에서 상장 거래소 + 종목 코드로 찾음(이름으로 찾지 않아 다른 회사가 섞이지 않음): 대표 사진(P18) · 로고(P154).
주제 = 아래 TOPICS 의 영어 검색어로 공용 검색, 주제마다 후보 몇 장.

결과: ~/Desktop/Newfact-그림-검수/ 폴더별 그림 + 출처.csv(저작자 · 이용 조건 · 원본 주소) + 검수표.html(한 화면에 다 보기).
사용자가 쓰지 않을 그림을 지우면, 나중에 올리는 스크립트가 남은 그림만 출처.csv 와 맞춰 올린다.
AI 호출 0 · 블로그 · gh-pages 쓰기 0. 위키미디어 조회만(한 번 실행, 정기 실행 아님).
"""

import argparse
import csv
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.expanduser("~/Desktop/Newfact-그림-검수")
UA = "NewfactImageReview/0.1 (one-off license-checked image candidates)"
API = "https://commons.wikimedia.org/w/api.php"
WIDTH = 1280
OK_LICENSE = re.compile(r"^(cc0|public domain|pd\b|pd-|cc by(-sa)? [0-9.]+|cc by(-sa)?$|kogl type 1|attribution)", re.I)

# 주제 그림 — 폴더 → 주제 → 영어 검색어들 (공용은 영어 설명이 대부분)
TOPICS = {
    "3_업종": {
        "반도체": ["semiconductor wafer", "semiconductor fab cleanroom", "semiconductor factory Korea", "integrated circuit chip closeup", "silicon wafer cleanroom worker"],
        "메모리 · 반도체 장비": ["DRAM memory chip", "lithography machine ASML", "semiconductor equipment cleanroom", "memory module RAM"],
        "AI · 데이터센터": ["data center server racks", "GPU accelerator board"],
        "2차전지": ["lithium-ion battery cells", "battery factory", "electric vehicle battery pack", "battery cell production line"],
        "자동차": ["car factory assembly line", "Hyundai car factory", "Hyundai Motor Ulsan plant", "car carrier export cars port"],
        "조선": ["shipyard Ulsan", "shipbuilding dock ship", "crude oil tanker VLCC", "LNG carrier ship", "shipyard Geoje", "ship launching ceremony", "tanker ship at sea"],
        "해운 · 컨테이너": ["container ship at sea", "container terminal port Busan", "cargo ship port", "container terminal gantry cranes", "bulk carrier ship", "car carrier ship", "Port of Busan containers", "freight shipping export"],
        "항공": ["Korean Air airplane", "commercial airliner takeoff", "Incheon airport airplane", "airliner cabin passengers"],
        "방산": ["K9 Thunder howitzer", "K2 Black Panther tank", "fighter jet KF-21", "K9 howitzer exercise", "missile launcher defense exhibition"],
        "원자력 · 전력": ["nuclear power plant Korea", "power transmission lines transformer substation", "nuclear power plant cooling tower", "power plant chimney"],
        "전력기기 · 변압기": ["power transformer substation", "high voltage transformer", "electrical substation", "high voltage power lines"],
        "정유 · 석유화학": ["oil refinery night", "petrochemical plant Ulsan", "oil refinery", "petrochemical complex", "oil storage tanks"],
        "철강": ["steel mill blast furnace", "POSCO Pohang steelworks", "blast furnace", "molten steel pouring", "steelworks", "hot rolled steel coils", "Hyundai Steel Dangjin", "Gwangyang steelworks", "steel plant converter", "steel coils warehouse", "steel pipes stacked", "rebar steel bars", "steel beams", "steel plates factory", "rolling mill", "molten iron furnace", "steelworker molten metal", "ladle molten steel", "steel mill sparks", "steel cutting sparks", "plasma cutting steel plate", "oxy fuel cutting steel", "foundry molten metal pouring", "electric arc furnace", "continuous casting steel slab"],
        "화학 · 소재": ["chemical plant", "chemical industry complex", "chemical factory pipes", "Yeosu industrial complex"],
        "제약 · 바이오": ["pharmaceutical laboratory", "biotechnology lab pipette", "vaccine vials", "pharmaceutical factory production", "laboratory scientist microscope", "pills tablets medicine"],
        "의료기기 · 병원": ["hospital operating room", "medical device MRI scanner", "hospital corridor", "CT scanner hospital", "surgical robot", "hospital building Seoul", "ultrasound medical device"],
        "은행": ["bank branch Seoul", "bank building Wall Street", "bank teller counter", "ATM machines bank", "bank headquarters Seoul", "Korean won banknotes"],
        "증권 · 투자": ["stock trading screen", "Yeouido financial district", "Korea Exchange", "stock exchange trading floor", "stock market display board", "stock ticker", "trading room monitors", "stock market chart"],
        "보험": ["insurance company headquarters building", "insurance office building Seoul", "office workers financial district"],
        "건설 · 부동산": ["construction site cranes Seoul", "apartment complex Seoul", "apartment construction Korea", "tower crane construction site", "high-rise apartments Seoul", "Seoul skyline apartments"],
        "유통 · 대형마트": ["supermarket aisle", "hypermarket store interior Korea", "shopping mall interior", "department store Seoul", "supermarket shelves", "shopping cart supermarket"],
        "온라인 쇼핑 · 배송": ["parcel delivery truck", "logistics warehouse conveyor", "delivery boxes"],
        "통신": ["cell tower 5G antenna", "telecommunication tower", "mobile phone network antenna", "fiber optic cable"],
        "인터넷 · 소프트웨어": ["software developer code screen", "Naver Green Factory", "programmers working office laptops", "Kakao headquarters Pangyo", "Pangyo Techno Valley", "startup office open space", "software engineers office", "computer programming screen code", "server room data", "laptop coding developer"],
        "게임 · 엔터테인먼트": ["video game convention G-Star", "K-pop concert stage", "G-Star BEXCO Busan", "Gamescom visitors hall", "esports tournament arena", "Tokyo Game Show booth", "gaming PC esports players", "concert crowd stage lights"],
        "화장품": ["cosmetics store Myeongdong", "cosmetic products", "cosmetics shop Seoul", "skincare products"],
        "식품 · 음료": ["food factory production line", "ramen noodles Korea", "food processing factory", "beverage bottling line", "convenience store Korea"],
        "로봇 · 기계": ["industrial robot arm", "excavator construction machinery", "factory automation robots", "industrial machinery factory", "CNC machine tool", "construction excavator"],
        "우주 · 항공 산업": ["Nuri rocket launch", "satellite in orbit", "rocket launch", "aircraft engine factory", "airplane assembly line"],
        "유틸리티 · 가스": ["LNG carrier ship", "natural gas pipeline", "gas pipeline", "water treatment plant", "LNG terminal tanks"],
        "담배 · 주류": ["cigarette factory", "brewery tanks", "beer brewery", "whisky distillery barrels", "soju bottles", "cigarettes pack"],
        "호텔 · 여행 · 카지노": ["casino interior", "cruise ship", "Incheon airport terminal", "hotel lobby", "resort pool", "travelers airport departures"],
    },
    "4_정부-기관": {
        "백악관": ["White House north facade"],
        "미국 의회": ["United States Capitol"],
        "미국 재무부": ["Treasury Building Washington"],
        "미국 연준": ["Marriner S. Eccles Federal Reserve Board Building"],
        "미국 상무부 · 무역": ["Herbert C. Hoover Building Commerce"],
        "미국 증권거래위원회": ["SEC headquarters Washington"],
        "미국 대법원": ["Supreme Court of the United States building"],
        "펜타곤": ["The Pentagon aerial"],
        "한국 대통령실": ["Yongsan presidential office", "Cheong Wa Dae"],
        "한국 국회": ["National Assembly Proceeding Hall Seoul"],
        "정부세종청사": ["Government Complex Sejong"],
        "정부서울청사": ["Government Complex Seoul"],
        "한국은행": ["Bank of Korea headquarters"],
        "금융위 · 금감원": ["Financial Supervisory Service Korea building"],
        "공정거래위원회": ["Fair Trade Commission Korea"],
        "유럽중앙은행": ["European Central Bank Frankfurt"],
        "일본은행": ["Bank of Japan head office"],
        "중국 정부": ["Great Hall of the People Beijing", "Zhongnanhai"],
    },
    "5_인물": {
        "트럼프": ["Donald Trump official portrait 2025"],
        "베센트": ["Scott Bessent official portrait"],
        "파월": ["Jerome Powell official portrait"],
        "연준 의장 후보 해싯": ["Kevin Hassett"],
        "워시": ["Kevin Warsh"],
        "러트닉": ["Howard Lutnick official portrait"],
        "그리어 무역대표": ["Jamieson Greer"],
        "밴스": ["JD Vance official portrait"],
        "이재명": ["Lee Jae-myung 2025"],
        "이창용": ["Rhee Chang-yong", "Rhee Chang-yong Bank of Korea governor", "Chang Yong Rhee IMF"],
        "시진핑": ["Xi Jinping 2023"],
        "푸틴": ["Vladimir Putin 2023"],
        "젤렌스키": ["Volodymyr Zelensky official portrait"],
        "김정은": ["Kim Jong Un 2019"],
        "이시바 · 일본 총리": ["Sanae Takaichi"],
        "네타냐후": ["Benjamin Netanyahu 2023"],
        "젠슨 황": ["Jensen Huang"],
        "일론 머스크": ["Elon Musk 2023"],
        "샘 올트먼": ["Sam Altman"],
        "팀 쿡": ["Tim Cook"],
        "사티아 나델라": ["Satya Nadella"],
        "저커버그": ["Mark Zuckerberg 2019"],
        "리사 수": ["Lisa Su AMD"],
        "워런 버핏": ["Warren Buffett"],
        "이재용": ["Lee Jae-yong Samsung"],
        "최태원": ["Chey Tae-won"],
        "정의선": ["Chung Eui-sun"],
        "구광모": ["Koo Kwang-mo"],
        "캐시 우드": ["Cathie Wood"],
        "마이클 버리": ["Michael Burry", "Michael Burry investor", "Scion Asset Management"],
        "짐 크레이머": ["Jim Cramer"],
    },
    "6_전쟁-국제": {
        "중동 · 이란": ["Strait of Hormuz satellite", "Tehran skyline"],
        "이스라엘 · 가자": ["Gaza Strip", "Israel Defense Forces"],
        "우크라이나 전쟁": ["War in Ukraine destroyed building", "Kyiv Independence Square"],
        "북한": ["Panmunjom Joint Security Area", "Pyongyang skyline", "North Korean missile parade"],
        "대만 해협": ["Taipei 101 skyline", "Taiwan Strait"],
        "미중 관계": ["China United States flags"],
        "유가 · 유조선": ["oil tanker at sea", "oil pumpjack"],
        "제재 · 수출 통제": ["cargo containers customs inspection"],
        "자연재해": ["earthquake damage building", "typhoon satellite image"],
        "감염병": ["coronavirus electron microscope", "face masks crowd"],
        "G7 · 정상회의": ["G7 summit leaders", "APEC summit Gyeongju"],
        "OPEC": ["OPEC headquarters Vienna"],
    },
    "7_시장-지수": {
        "뉴욕증권거래소": ["New York Stock Exchange facade", "NYSE trading floor"],
        "나스닥": ["Nasdaq MarketSite Times Square"],
        "월가": ["Wall Street sign", "Charging Bull"],
        "한국거래소 · 코스피": ["Korea Exchange Yeouido", "Korea Exchange building Busan", "Korea Exchange", "KRX Korea Exchange Seoul", "Busan International Financial Center"],
        "여의도": ["Yeouido skyline"],
        "도쿄 증시": ["Tokyo Stock Exchange Arrowhead"],
        "상하이 · 홍콩 증시": ["Hong Kong Exchanges building", "Shanghai Lujiazui skyline"],
        "주가 전광판": ["stock ticker board", "stock market chart screen"],
    },
    "8_사건-분류": {
        "금리 · 연준": ["Federal Reserve Eccles building", "FOMC meeting"],
        "물가": ["supermarket price tags", "grocery shopping cart", "supermarket aisle shoppers", "traditional market Seoul vegetables", "Gwangjang Market", "fruit vegetable market stall prices"],
        "경기 · 고용": ["job fair crowd", "shopping street crowd Seoul"],
        "관세 · 무역": ["container port cranes", "cargo ship containers"],
        "환율": ["United States dollar banknotes", "South Korean won banknotes", "currency exchange board", "currency exchange office sign", "money exchange booth airport", "foreign currency banknotes colorful"],
        "유가 · 원자재": ["gold bars", "copper cathodes", "crude oil barrels", "oil refinery", "oil pumpjack field", "gold bullion", "copper mine open pit", "iron ore stockpile"],
        "AI 투자": ["AI data center", "Nvidia GPU"],
        "실적 발표": ["earnings conference call", "annual report charts"],
        "기업 사건 · 인수합병": ["handshake business deal", "corporate headquarters lobby"],
        "규제 · 소송": ["courtroom", "judge gavel"],
        "재정 · 정치 · 선거": ["ballot box election", "United States Capitol dome"],
        "금융 · 신용 · 은행": ["bank vault", "bank run queue"],
        "암호화폐": ["Bitcoin coin", "cryptocurrency mining rig"],
        "부동산 · 주택": ["Seoul apartments Gangnam", "housing construction suburb"],
        "파업 · 노동": ["labor union strike rally"],
        "임시 휴업 · 폐점": ["closed store shutter", "store closing sign"],
        "반도체 수출": ["semiconductor export container"],
    },
}


try:
    import certifi
    import ssl
    CTX = ssl.create_default_context(cafile=certifi.where())   # 맥 파이썬은 기본 인증서가 없다
except ImportError:
    CTX = None


def get(url, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=60, context=CTX).read()
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(60 * (i + 1) if "429" in str(e) else 3 * (i + 1))   # 429 = 위키미디어 속도 제한 → 1분 · 2분 … 쉬고 다시


def api(**params):
    params.update(format="json", formatversion=2)
    return json.loads(get(API + "?" + urllib.parse.urlencode(params)))


def safe(s):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s).strip("_")[:60]


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", html.unescape(s or "")).strip()


def file_infos(titles):
    """파일 제목 → 이미지 정보(크기 · 썸네일 주소 · 저작자 · 이용 조건). 50개씩."""
    out = {}
    for i in range(0, len(titles), 50):
        r = api(action="query", titles="|".join(titles[i:i + 50]), prop="imageinfo",
                iiprop="url|size|mime|extmetadata", iiurlwidth=WIDTH)
        for p in r["query"].get("pages", []):
            if "imageinfo" in p:
                out[p["title"]] = p["imageinfo"][0]
        time.sleep(0.3)
    return out


def license_of(ii):
    m = ii.get("extmetadata", {})
    lic = strip_tags(m.get("LicenseShortName", {}).get("value", ""))
    return lic, strip_tags(m.get("Artist", {}).get("value", ""))[:120], strip_tags(m.get("Restrictions", {}).get("value", ""))


ROWS = []


def save(ii, title, rel, note=""):
    lic, artist, restr = license_of(ii)
    if not OK_LICENSE.search(lic):
        return False
    url = ii.get("thumburl") or ii["url"]
    ext = ".png" if ii.get("mime") in ("image/svg+xml", "image/png") else ".jpg"
    rel = rel + ext
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        try:
            data = get(url)
        except Exception as e:
            print(f"    건너뜀 {title}: {e}", flush=True)
            return False
        d = os.path.dirname(path)
        if any(os.path.getsize(os.path.join(d, f)) == len(data) and open(os.path.join(d, f), "rb").read() == data
               for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))):
            return False   # 같은 폴더에 같은 그림이 이미 있음(다시 돌릴 때)
        with open(path, "wb") as f:
            f.write(data)
        time.sleep(1.5)   # 그림 받기는 천천히 (11-25 0.2초 간격에 429)
    ROWS.append({"file": rel, "title": title, "license": lic, "artist": artist, "restrictions": restr,
                 "source": ii.get("descriptionurl", ""), "width": ii.get("width"), "height": ii.get("height"), "note": note})
    return True


# ---------- 회사 ----------
SPARQL = """
SELECT ?item ?ticker ?img ?logo ?cat ?ko ?en WHERE {
  VALUES ?ticker { %s }
  ?item p:P414 ?st . ?st pq:P249 ?ticker .
  OPTIONAL { ?item wdt:P18 ?img }
  OPTIONAL { ?item wdt:P154 ?logo }
  OPTIONAL { ?item wdt:P373 ?cat }
  OPTIONAL { ?item rdfs:label ?ko FILTER(lang(?ko)="ko") }
  OPTIONAL { ?item rdfs:label ?en FILTER(lang(?en)="en") }
}"""


def wikidata(tickers):
    rows = []
    for i in range(0, len(tickers), 200):
        vals = " ".join('"%s"' % t for t in tickers[i:i + 200])
        q = urllib.parse.urlencode({"query": SPARQL % vals, "format": "json"})
        rows += json.loads(get("https://query.wikidata.org/sparql?" + q))["results"]["bindings"]
        time.sleep(1)
    return rows


def norm(s):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"(?i)\b(inc|corp|corporation|co|ltd|company|holdings?|group|plc|the)\b", "", s.lower()))


def companies(limit=None):
    u = json.load(open(os.path.join(BASE, "ref", "universe_all.json")))
    want = [("KR", x["code"], x["name"]) for x in u["kr"]] + [("US", x["sym"].replace("-", "."), x["name"]) for x in u["us"]]
    if limit:
        want = want[:limit]
    rows = wikidata([t for _, t, _ in want])
    by = {}
    for r in rows:
        by.setdefault(r["ticker"]["value"], []).append(r)
    qr = json.load(open(os.path.join(BASE, "ref", "quick_ref.json")))
    KO = {k.split(".")[0]: v.get("ko") for k, v in qr["kr"].items()}
    KO.update({k.replace("-", "."): v.get("ko") for k, v in qr.get("us", {}).items() if isinstance(v, dict) and v.get("ko")})
    found = {}
    for mk, t, name in want:
        cands = by.get(t, [])
        if mk == "US":   # 미국 티커는 다른 나라 거래소의 같은 글자와 겹칠 수 있다 → 이름이 맞는 항목만
            cands = [c for c in cands if norm(c.get("en", {}).get("value", "")) and
                     (norm(c["en"]["value"]) in norm(name) or norm(name) in norm(c["en"]["value"]))]
        else:            # 한국은 그룹 항목(삼성 · LG)보다 이름이 맞는 회사 항목
            cands.sort(key=lambda c: -(norm(c.get("en", {}).get("value", "")) in norm(name) and len(norm(c.get("en", {}).get("value", "")))) or 0)
        if cands:
            found[(mk, t, name)] = cands
    titles = set()
    for cs in found.values():
        for c in cs:
            for k in ("img", "logo"):
                if k in c:
                    titles.add("File:" + urllib.parse.unquote(c[k]["value"].rsplit("/", 1)[1]))
    infos = file_infos(sorted(titles))
    stat = {"명단": len(want), "위키데이터 찾음": len(found), "사진": 0, "로고": 0}
    for (mk, t, name), cs in found.items():
        ko = KO.get(t) or next((c["ko"]["value"] for c in cs if "ko" in c), "") or name
        label = f"{t}_{safe(ko)}"
        done = {"img": set(), "logo": set()}
        for c in cs:
            for k, folder in (("img", "1_기업-사진"), ("logo", "2_기업-로고")):
                if k in c:
                    title = "File:" + urllib.parse.unquote(c[k]["value"].rsplit("/", 1)[1])
                    if title in done[k] or title not in infos:
                        continue
                    n = len(done[k]) + 1
                    if save(infos[title], title, f"{folder}/{mk}/{label}" + (f"_{n}" if n > 1 else ""), note=name):
                        done[k].add(title)
        stat["사진"] += bool(done["img"])
        stat["로고"] += bool(done["logo"])
        print(f"  {mk} {t} {ko}: 사진 {len(done['img'])} · 로고 {len(done['logo'])}", flush=True)
    # 대표 사진이 없는 회사 → 공용에서 '이름 + 본사 · 건물' 검색, 파일 이름에 회사 이름이 든 것만(다른 건물이 섞이지 않게)
    stat["사진(검색 보강)"] = 0
    have = {r["file"].split("/")[2].split("_")[0] for r in ROWS if r["file"].startswith("1_기업-사진/")}
    for mk, t, name in want:
        if t in have:
            continue
        cs = found.get((mk, t, name), [])
        en = next((c["en"]["value"] for c in cs if "en" in c), "") or re.sub(r"(?i),?\s*(co\.?,?\s*ltd\.?|inc\.?|corp\.?|corporation)$", "", name)
        ko = KO.get(t) or next((c["ko"]["value"] for c in cs if "ko" in c), "") or name
        key = norm(en)[:6]
        if len(key) < 3:
            continue
        got = 0
        cats = {c["cat"]["value"] for c in cs if "cat" in c}
        files = []
        for cat in sorted(cats):
            r = api(action="query", generator="categorymembers", gcmtitle="Category:" + cat, gcmtype="file", gcmlimit=50,
                    prop="imageinfo", iiprop="url|size|mime|extmetadata", iiurlwidth=WIDTH)
            files += r.get("query", {}).get("pages", [])
            time.sleep(0.4)
        if not files:
            r = api(action="query", generator="search", gsrnamespace=6, gsrlimit=15, gsrsearch=f"{en} filetype:bitmap",
                    prop="imageinfo", iiprop="url|size|mime|extmetadata", iiurlwidth=WIDTH)
            files = [p for p in r.get("query", {}).get("pages", []) if key in norm(p["title"])]
            time.sleep(0.4)
        BUILD = re.compile(r"(?i)headquarter|hq|building|tower|campus|office|plant|factory|fab|store|shop|branch|center|centre|본사|사옥|공장|빌딩")
        files.sort(key=lambda p: (not BUILD.search(p["title"]), p.get("index", 0)))
        for p in files:
            ii = (p.get("imageinfo") or [None])[0]
            if not ii or (ii.get("width") or 0) < 900 or ii["width"] < ii.get("height", 0) * 0.9 or re.search(r"(?i)logo|\.svg", p["title"]) \
                    or not (key in norm(p["title"]) or BUILD.search(p["title"])):
                continue
            if save(ii, p["title"], f"1_기업-사진/{mk}/{t}_{safe(ko)}_후보{got + 1}", note=f"{name} · 공용 분류/검색"):
                got += 1
            if got >= 3:
                break
        stat["사진(검색 보강)"] += bool(got)
        if got:
            print(f"  {mk} {t} {ko}: 검색 사진 {got}", flush=True)
    return stat


# ---------- 주제 ----------
def last_num(folder, topic, pat):
    """이미 쓴 가장 큰 번호 — 검수 폴더 · 완료 · 사용안함까지 본다(빈 주제를 다시 받을 때 옛 파일 이름과 겹치지 않게, 11-27)."""
    nums = []
    for base in (OUT, os.path.join(OUT, "완료"), os.path.join(OUT, "사용안함")):
        d = os.path.join(base, folder, safe(topic))
        nums += [int(m.group(1)) for f in (os.listdir(d) if os.path.isdir(d) else []) for m in [re.search(pat, f)] if m]
    return max(nums, default=0)


def topics(per_query=4, only=None):
    stat = {}
    have = set()
    if os.path.exists(os.path.join(OUT, "출처.csv")):
        have = {r["title"] for r in csv.DictReader(open(os.path.join(OUT, "출처.csv"), encoding="utf-8-sig"))}
    for folder, items in TOPICS.items():
        for topic, queries in items.items():
            if only and topic not in only:
                continue
            d = os.path.join(OUT, folder, safe(topic))
            n = last_num(folder, topic, r"_(\d+)\.")   # 다시 돌릴 때 번호를 이어 붙인다(이미 받은 파일 · 사용자가 지운 번호를 덮지 않게)
            seen = set(have)
            for q in queries:
                r = api(action="query", generator="search", gsrnamespace=6, gsrlimit=15,
                        gsrsearch=f"{q} filetype:bitmap", prop="imageinfo",
                        iiprop="url|size|mime|extmetadata", iiurlwidth=WIDTH)
                pages = sorted(r.get("query", {}).get("pages", []), key=lambda p: p.get("index", 99))
                got = 0
                for p in pages:
                    ii = (p.get("imageinfo") or [None])[0]
                    if not ii or p["title"] in seen or (ii.get("width") or 0) < 900 or ii.get("width", 0) < ii.get("height", 0) * 0.9 and folder != "5_인물":
                        continue
                    seen.add(p["title"])
                    if save(ii, p["title"], f"{folder}/{safe(topic)}/{safe(topic)}_{n + 1:02d}", note=q):
                        n += 1
                        got += 1
                    if got >= per_query:
                        break
                time.sleep(0.5)
            stat[f"{folder}/{topic}"] = n
            print(f"  {folder}/{topic}: {n}장", flush=True)
    return stat


# ---------- Openverse(플리커 CC 사진) ----------
OV_LIC = {"by": "CC BY", "by-sa": "CC BY-SA", "cc0": "CC0", "pdm": "Public domain"}   # ND(고침 금지) · NC(비영리)는 받지 않는다


def openverse(per_topic=4, only=None):
    """주제 그림만(회사 사진은 공용 · 위키데이터가 정확). 파일 이름 = 주제_flickrNN — 출처가 이름에 보이게."""
    stat = {}
    have = set()   # 이미 받은(뺀 것 포함) 원본 주소 — 다시 받지 않는다
    if os.path.exists(os.path.join(OUT, "출처.csv")):
        have = {r["source"] for r in csv.DictReader(open(os.path.join(OUT, "출처.csv"), encoding="utf-8-sig"))}
    for folder, items in TOPICS.items():
        for topic, queries in items.items():
            if only and topic not in only:
                continue
            d = os.path.join(OUT, folder, safe(topic))
            n = last_num(folder, topic, r"_flickr(\d+)\.")
            got = 0
            for q in queries:
                url = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(
                    {"q": q, "source": "flickr", "license_type": "commercial", "page_size": 20,
                     "mature": "false"})
                try:
                    res = json.loads(get(url)).get("results", [])
                except Exception as e:
                    print(f"    Openverse 실패 {q}: {e}", flush=True)
                    res = []
                k = 0
                for r in res:
                    lic = OV_LIC.get(r.get("license"))
                    if r.get("foreign_landing_url") in have:
                        continue
                    if not lic or (r.get("width") or 0) < 1000 or (folder != "5_인물" and (r.get("width") or 0) < (r.get("height") or 0) * 0.9):
                        continue
                    lic_s = lic + (" " + r["license_version"] if r.get("license_version") and lic.startswith("CC BY") else "")
                    ii = {"thumburl": r["url"], "mime": "image/jpeg", "descriptionurl": r.get("foreign_landing_url", ""),
                          "width": r.get("width"), "height": r.get("height"),
                          "extmetadata": {"LicenseShortName": {"value": lic_s}, "Artist": {"value": r.get("creator") or ""}}}
                    if save(ii, "flickr: " + (r.get("title") or ""), f"{folder}/{safe(topic)}/{safe(topic)}_flickr{n + 1:02d}", note=f"Openverse · {q}"):
                        n += 1
                        got += 1
                        k += 1
                    if k >= 2 or got >= per_topic:
                        break
                time.sleep(3)   # 열쇠 없는 사용은 분당 요청이 적다
                if got >= per_topic:
                    break
            stat[f"{folder}/{topic}"] = got
            print(f"  [플리커] {folder}/{topic}: {got}장", flush=True)
    return stat


def rebuild_topics():
    """출처.csv 에 줄이 없는 주제 그림(위키미디어 쪽)의 출처를 되살린다 — 같은 검색을 다시 해 그림 내용이 똑같은 파일에만 붙인다.
    받기가 중간에 강제로 멈추면 출처.csv 를 못 써서 생긴다(11-25). 새 파일은 만들지 않는다."""
    have = set()
    if os.path.exists(os.path.join(OUT, "출처.csv")):
        have = {r["file"] for r in csv.DictReader(open(os.path.join(OUT, "출처.csv"), encoding="utf-8-sig"))}
    fixed = 0
    for folder, items in TOPICS.items():
        for topic, queries in items.items():
            d = os.path.join(OUT, folder, safe(topic))
            if not os.path.isdir(d):
                continue
            miss = {f: open(os.path.join(d, f), "rb").read() for f in os.listdir(d)
                    if "flickr" not in f and f"{folder}/{safe(topic)}/{f}" not in have and not f.startswith(".")}
            if not miss:
                continue
            for q in queries:
                if not miss:
                    break
                r = api(action="query", generator="search", gsrnamespace=6, gsrlimit=15, gsrsearch=f"{q} filetype:bitmap",
                        prop="imageinfo", iiprop="url|size|mime|extmetadata", iiurlwidth=WIDTH)
                for p in r.get("query", {}).get("pages", []):
                    ii = (p.get("imageinfo") or [None])[0]
                    if not ii or not miss or not OK_LICENSE.search(license_of(ii)[0]):
                        continue
                    try:
                        data = get(ii.get("thumburl") or ii["url"])
                    except Exception:
                        continue
                    time.sleep(1.5)
                    for f, b in list(miss.items()):
                        if b == data:
                            lic, artist, restr = license_of(ii)
                            ROWS.append({"file": f"{folder}/{safe(topic)}/{f}", "title": p["title"], "license": lic, "artist": artist,
                                         "restrictions": restr, "source": ii.get("descriptionurl", ""), "width": ii.get("width"),
                                         "height": ii.get("height"), "note": q})
                            del miss[f]
                            fixed += 1
                time.sleep(0.5)
            print(f"  [출처 복구] {folder}/{topic}: 남은 {len(miss)} " + " ".join(miss), flush=True)
    return {"출처 되살림": fixed}


def write_sheet():
    rows_path = os.path.join(OUT, "출처.csv")
    old = []
    if os.path.exists(rows_path):
        old = list(csv.DictReader(open(rows_path, encoding="utf-8-sig")))
    allrows = {r["file"]: r for r in old}
    for r in ROWS:
        allrows[r["file"]] = r
    keys = ["file", "title", "license", "artist", "restrictions", "source", "width", "height", "note"]
    with open(rows_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for k in sorted(allrows):
            w.writerow({x: allrows[k].get(x, "") for x in keys})
    groups = {}
    for k in sorted(allrows):
        groups.setdefault(os.path.dirname(k), []).append(allrows[k])
    parts = ["<!doctype html><meta charset=utf-8><title>Newfact 그림 검수</title><style>"
             "body{font-family:-apple-system,sans-serif;margin:16px;background:#fafafa}h2{margin:28px 0 8px;font-size:17px}"
             ".g{display:flex;flex-wrap:wrap;gap:10px}.c{width:260px;background:#fff;border:1px solid #ddd;border-radius:8px;overflow:hidden;font-size:12px}"
             ".c img{width:260px;height:170px;object-fit:cover;display:block;background:#eee}.c.logo img{object-fit:contain}.c div{padding:6px 8px;color:#555;word-break:break-all}"
             ".c b{color:#111}.r{color:#b45309}</style><h1>Newfact 그림 검수</h1>"
             "<p>쓰지 않을 그림은 폴더에서 파일을 지우면 됩니다. 출처 · 이용 조건은 <code>출처.csv</code>. 지운 파일은 여기서 깨져 보입니다.</p>"]
    for g, rs in groups.items():
        parts.append(f"<h2>{html.escape(g)} ({len(rs)})</h2><div class=g>")
        for r in rs:
            cls = "c logo" if "로고" in g else "c"
            parts.append(f"<div class='{cls}'><a href='{html.escape(r['source'])}' target=_blank><img loading=lazy src='{html.escape(r['file'])}'></a>"
                         f"<div><b>{html.escape(os.path.basename(r['file']))}</b><br>{html.escape(r['license'])} · {html.escape(r['artist'][:60])}"
                         + (f"<br><span class=r>제한: {html.escape(r['restrictions'][:80])}</span>" if r.get("restrictions") else "") + "</div></div>")
        parts.append("</div>")
    open(os.path.join(OUT, "검수표.html"), "w", encoding="utf-8").write("".join(parts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["companies", "topics", "openverse", "rebuild"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--topics", help="쉼표로 주제 이름 — 그 주제만 다시 받아 후보를 더한다")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    stats = {}
    try:
        if a.only in (None, "topics"):
            stats["주제"] = topics(only=set(a.topics.split(",")) if a.topics else None)
        if a.only == "rebuild":
            stats["복구"] = rebuild_topics()
        if a.only == "openverse":
            stats["플리커"] = openverse(only=set(a.topics.split(",")) if a.topics else None)
        if a.only in (None, "companies"):
            stats["회사"] = companies(a.limit)
    finally:
        write_sheet()
        json.dump(stats, open(os.path.join(OUT, "요약.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps(stats.get("회사", {}), ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
