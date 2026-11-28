"""자료 사진 고르기 미리 돌려 보기 — 실제 글에 붙이지 않고, 지난 기사 제목 · 발행 글에 사진 규칙을 적용해 결과만 센다.

    python experiments/news_images/photo_pick_dryrun.py            # 표 + 예시를 화면에, 자세한 결과는 output/photo_dryrun.json

재료(읽기만, git 제외): news-posts/samples/posts.json · headlines.json (fetch_samples.py 로 받음)
사진 목록: ~/Desktop/Newfact-그림-검수/완료/ (사용자 검수 끝난 사진)

고르는 순서(위에서 먼저 맞는 것) — 틀린 사진보다 사진 없음:
  1 인물     제목에 인물 이름 → 그 인물 사진
  2 회사     글의 종목(발행 글) 또는 제목 속 회사 이름(853종목) → 회사 사진, 없으면 업종 사진 + 이름표
  3 기관     제목에 기관 이름(한국은행 · 연준 · 백악관 …) → 기관 사진
  4 국제     전쟁 · 북한 · 중동 · 제재 … → 국제 사진
  5 시장     코스피 · 나스닥 · 월가 … → 시장 사진
  6 분류     기사 분류(cat) → 사건 분류 사진(금리 · 환율 · 실적 …)
  7 없음
AI 호출 0 · 바깥 요청 0.
"""
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
SAMPLES = os.path.join(EXP, "news-posts", "samples")
DONE = os.path.expanduser("~/Desktop/Newfact-그림-검수/완료")
IMG = (".jpg", ".jpeg", ".png")

# 이름 → 폴더. 제목 속 낱말로 찾는다(앞뒤가 한글 낱말 가운데가 아니어야 맞음 — '파월'이 '파월스'에 붙지 않게)
PEOPLE = {
    "트럼프": "트럼프", "파월": "파월", "젠슨 황": "젠슨_황", "젠슨황": "젠슨_황", "머스크": "일론_머스크", "이재명": "이재명",
    "이창용": "이창용", "시진핑": "시진핑", "푸틴": "푸틴", "젤렌스키": "젤렌스키", "네타냐후": "네타냐후", "김정은": "김정은",
    "베센트": "베센트", "러트닉": "러트닉", "그리어": "그리어_무역대표", "밴스": "밴스", "해싯": "연준_의장_후보_해싯", "워시": "워시",
    "이시바": "이시바_·_일본_총리", "버핏": "워런_버핏", "올트먼": "샘_올트먼", "저커버그": "저커버그", "팀 쿡": "팀_쿡",
    "나델라": "사티아_나델라", "리사 수": "리사_수", "캐시 우드": "캐시_우드", "크레이머": "짐_크레이머", "이재용": "이재용",
    "정의선": "정의선", "최태원": "최태원",
}
INST = {
    "한국은행": "한국은행", "한은": "한국은행", "금통위": "한국은행", "연준": "미국_연준", "Fed": "미국_연준", "FOMC": "미국_연준",
    "백악관": "백악관", "대통령실": "한국_대통령실", "국회": "한국_국회", "의회": "미국_의회", "상원": "미국_의회", "하원": "미국_의회",
    "공정위": "공정거래위원회", "공정거래위": "공정거래위원회", "대법원": "미국_대법원", "재무부": "미국_재무부", "상무부": "미국_상무부_·_무역",
    "SEC": "미국_증권거래위원회", "증권거래위원회": "미국_증권거래위원회", "ECB": "유럽중앙은행", "유럽중앙은행": "유럽중앙은행",
    "일본은행": "일본은행", "日銀": "일본은행", "BOJ": "일본은행", "펜타곤": "펜타곤", "국방부": "펜타곤",
    "기재부": "정부세종청사", "기획재정부": "정부세종청사", "금융위": "정부서울청사", "금감원": "정부서울청사", "금융감독원": "정부서울청사",
    "중국 정부": "중국_정부", "국무원": "중국_정부",
}
WORLD = {
    "북한": "북한", "우크라이나": "우크라이나_전쟁", "러시아": "우크라이나_전쟁", "이스라엘": "이스라엘_·_가자", "가자": "이스라엘_·_가자",
    "이란": "중동_·_이란", "중동": "중동_·_이란", "대만": "대만_해협", "미중": "미중_관계", "G7": "G7_·_정상회의", "G20": "G7_·_정상회의",
    "정상회담": "G7_·_정상회의", "OPEC": "OPEC", "제재": "제재_·_수출_통제", "수출 통제": "제재_·_수출_통제", "수출통제": "제재_·_수출_통제",
    "지진": "자연재해", "태풍": "자연재해", "홍수": "자연재해", "산불": "자연재해", "감염병": "감염병", "독감": "감염병", "유조선": "유가_·_유조선",
}
MARKET = {
    "코스피": "한국거래소_·_코스피", "코스닥": "한국거래소_·_코스피", "한국거래소": "한국거래소_·_코스피", "여의도": "여의도",
    "나스닥": "나스닥", "뉴욕증시": "뉴욕증권거래소", "다우": "뉴욕증권거래소", "S&P": "뉴욕증권거래소", "월가": "월가", "월스트리트": "월가",
    "상하이": "상하이_·_홍콩_증시", "홍콩증시": "상하이_·_홍콩_증시", "항셍": "상하이_·_홍콩_증시",
}
CAT = {   # 수집기 기사 분류 → 사건 분류 폴더
    "CORP_EVENT": "기업_사건_·_인수합병", "MARKET_STRUCTURE": "@market", "AI_CAPEX": "AI_투자", "REGULATION": "규제_·_소송",
    "CREDIT_BANKS": "금융_·_신용_·_은행", "TARIFF_TRADE": "관세_·_무역", "EARNINGS": "실적_발표", "GROWTH_JOBS": "경기_·_고용",
    "REAL_ESTATE": "부동산_·_주택", "RATES_FED": "금리_·_연준", "FX_GLOBAL": "환율", "OIL_ENERGY": "유가_·_원자재",
    "FISCAL_POLITICS": "재정_·_정치_·_선거", "CRYPTO": "암호화폐", "INFLATION": "물가", "GEOPOLITICS": "@world",
}
HANGUL = "가-힣A-Za-z0-9"
# 같은 낱말이 다른 뜻으로 많이 쓰이는 것 — 함께 있어야 하는 말(NEED) · 있으면 빼는 말(SKIP)
NEED = {
    "대만": r"해협|양안|군사|침공|중국.*(압박|훈련)", "러시아": r"우크라|전쟁|휴전|드론|공격|파병", "대법원": r"미국|美|연방",
    "국방부": r"미국|美|펜타곤", "의회": r"미국|美|하원|상원", "정상회담": r"정상", "다우": r"지수|뉴욕|증시|마감",
}
SKIP_AFTER = r"\s*(장남|차남|아들|딸|일가|가족|동생|부인|전 부인|측근)"   # '트럼프 장남' = 트럼프 사진 X
NO_TITLE_MATCH = {"SK", "LG", "GS", "CJ", "LS", "NC", "나스닥", "다우", "삼성", "현대", "한화", "롯데", "두산"}   # 그룹 · 시장 이름과 같은 회사 이름은 제목에서 찾지 않는다(글 종목으로만)
BROKER_WORDS = r"목표가|목표주가|투자의견|투자 의견|커버리지|리포트"



def word_re(name):
    # 앞: 글자 아님 · 뒤: 글자 아님 또는 조사(은 는 이 가 을 를 의 에 과 와 도 로 만) 하나
    return re.compile(rf"(?<![{HANGUL}]){re.escape(name)}(?=$|[^{HANGUL}]|[은는이가을를의에과와도로만](?:$|[^{HANGUL}]))")


def folder_photos():
    out = {}
    for top in os.listdir(DONE):
        p = os.path.join(DONE, top)
        if not os.path.isdir(p) or top.startswith("1_"):
            continue
        for g in os.listdir(p):
            q = os.path.join(p, g)
            if os.path.isdir(q):
                out[g] = len([f for f in os.listdir(q) if f.lower().endswith(IMG)])
    return out


def load_companies():
    sys.path.insert(0, HERE)
    ref = json.load(open(os.path.join(EXP, "ref", "quick_ref.json"), encoding="utf-8"))
    photo = {m: {f.split("_")[0] for f in os.listdir(os.path.join(DONE, "1_기업-사진", m))} for m in ("KR", "US")}
    names = {}
    for m, mk in (("kr", "KR"), ("us", "US")):
        for sym, v in ref[m].items():
            key = sym.split(".")[0]
            rec = {"sym": sym, "ko": v["ko"], "photo": key in photo[mk], "sector": v["sector"], "sub": v.get("sub", "")}
            names[key] = rec
            if len(v["ko"]) >= 2:   # 한 글자 이름(볼 · 델)은 제목에서 찾지 않는다
                names.setdefault("@" + v["ko"], rec)
    return names


def industry_of(rec):
    from cover_map import industry_folder   # 세부 업종 → 업종 폴더(임시 낱말 표)
    return industry_folder(rec["sector"], rec["sub"])


# 글의 업종 이름(수집기 sector) · 종목 세부 업종 → 업종 사진 폴더 (위에서 먼저 맞는 것, 임시 낱말 표 — 발행기로 옮길 때 다듬기)
IND = [
    ("2차전지|1차전지|ESS|연료전지|배터리", "2차전지"), ("데이터센터", "AI_·_데이터센터"),
    ("반도체 장비|반도체 테스트|반도체 후공정|반도체 부품|반도체 소재|반도체 · 디스플레이|반도체 설계", "메모리_·_반도체_장비"), ("반도체", "반도체"),
    ("조선|선박", "조선"), ("해운|택배|물류|화물|철도", "해운_·_컨테이너"), ("항공사|여객 항공|지주회사 \\(항공\\)", "항공"),
    ("우주", "우주_·_항공_산업"), ("방위|방산|탄약|인공위성", "방산"), ("원전|원자력|발전|전기 유틸리티|대체 전력|태양광|풍력", "원자력_·_전력"),
    ("중전기|전선|전기 부품|전기 제품|전력", "전력기기_·_변압기"), ("가스 유틸리티|가스 유통|수도|종합 공업|유틸리티", "유틸리티_·_가스"),
    ("석유|정유|가스", "정유_·_석유화학"), ("철강|금속|구리|광물", "철강"), ("화학|소재|비료|산업 가스|포장|용기|도료|OLED|동박", "화학_·_소재"),
    ("자동차|타이어", "자동차"), ("기계|중장비|모터|농기계|로봇", "로봇_·_기계"), ("건설|건자재|주택|부동산|리츠|임대", "건설_·_부동산"),
    ("은행|금융 지주|소비자 금융|리스|결제", "은행"), ("보험", "보험"), ("증권|자산|투자|거래소|펀드", "증권_·_투자"),
    ("제약|바이오|라이프 사이언스|펩타이드|줄기세포|백신", "제약_·_바이오"), ("의료|병원|간호|헬스", "의료기기_·_병원"),
    ("게임|카지노|엔터|영화|음반|방송|출판|케이블", "게임_·_엔터테인먼트"), ("호텔|리조트|크루즈|여행|식당", "호텔_·_여행_·_카지노"),
    ("통신|타워", "통신"), ("소프트웨어|IT|인터넷|인터랙티브|광고|마케팅|데이터 처리|컨설팅|AI", "인터넷_·_소프트웨어"),
    ("담배|주류|양조", "담배_·_주류"), ("음료|식품|사탕|육류|농산물|제과|급식|수산", "식품_·_음료"), ("화장품|개인 관리|가정|생활용품", "화장품"),
    ("백화점|유통|소매|전문점|의류|신발|명품|여가|대형마트|쇼핑", "유통_·_대형마트"), ("전자|하드웨어|카메라|디스플레이|계측|가전|커넥터|기판", "반도체"),
]


def industry(text):
    return next((f for pat, f in IND if re.search(pat, text or "")), None)


def pick(title, cat, stocks, comp, regs, have, sector=""):
    for kind, table in (("인물", PEOPLE),):
        for k, f in table.items():
            m = regs[k].search(title)
            if m and have.get(f) and not re.match(SKIP_AFTER, title[m.end():]):
                return kind, f, k
    if stocks:   # 글의 첫 종목 = 주인공(둘째 종목으로 넘어가지 않는다)
        s0 = stocks[0]
        rec = comp.get(str(s0.get("code") or "").split(".")[0]) or comp.get("@" + str(s0.get("name") or ""))
        if rec:
            return ("회사 사진" if rec["photo"] else "업종 사진 + 이름표"), rec["ko"], "글 종목"
        f = industry(sector)
        if f and have.get(f):   # 853종목 밖 회사 = 글의 업종 이름으로 업종 사진 + 이름표
            return "업종 사진 + 이름표", f"{s0.get('name')} → {f}", "글 업종(종목 밖)"
    broker = re.search(BROKER_WORDS, title)
    hits = []
    for k, rec in comp.items():
        if not k.startswith("@") or k[1:] in NO_TITLE_MATCH:
            continue
        m = regs[k].search(title)
        if m and not (broker and rec["sector"] == "금융"):
            hits.append((m.start(), -len(k), rec))
    if hits:
        rec = min(hits, key=lambda x: (x[0], x[1]))[2]   # 제목에서 가장 먼저 나온 회사
        return ("회사 사진" if rec["photo"] else "업종 사진 + 이름표"), rec["ko"], "제목 회사 이름"
    for kind, table in (("기관", INST), ("국제", WORLD), ("시장", MARKET)):
        for k, f in table.items():
            if regs[k].search(title) and have.get(f) and (k not in NEED or re.search(NEED[k], title)):
                if k == "정상회담" and re.search(r"미국|美|미중", title) and re.search(r"중국|中|미중", title):
                    f = "미중_관계"
                return kind, f, k
    f = industry(sector) if cat in ("CORP_EVENT", "EARNINGS") else None
    if f and have.get(f):   # 종목 없는 회사 기사(홈플러스 등) = 글의 업종 사진, 이름표 없음
        return "업종 사진", f, f"글 업종 '{sector}'"
    f = CAT.get(cat)
    if f == "@market":
        return "시장", "주가_전광판", "분류 MARKET_STRUCTURE"
    if f == "@world":   # 나라 · 사건이 안 잡힌 국제 기사 = 틀릴 수 있어 사진 없음
        return "없음", "", "분류 GEOPOLITICS(낱말 없음)"
    if f and have.get(f):
        return "분류", f, cat
    return "없음", "", cat or ""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    have = folder_photos()
    comp = load_companies()
    keys = list(PEOPLE) + list(INST) + list(WORLD) + list(MARKET) + [k for k in comp if k.startswith("@")]
    regs = {k: word_re(k[1:] if k.startswith("@") else k) for k in keys}
    posts = json.load(open(os.path.join(SAMPLES, "posts.json"), encoding="utf-8"))
    heads = json.load(open(os.path.join(SAMPLES, "headlines.json"), encoding="utf-8"))
    seen, items = set(), []
    for d in heads:
        for it in d.get("items") or []:
            ev = it.get("event") or it.get("title") or ""
            if ev in seen:   # 같은 사건 묶음은 한 번만(기사 하나 = 사건 하나로 센다)
                continue
            seen.add(ev)
            items.append(("제목 묶음", ev, it.get("cat"), it.get("stocks"), ""))
    for p in posts:
        items.append(("발행 글", p.get("title", ""), p.get("cat"), p.get("stocks"), p.get("sector", "")))
    res = collections.Counter()
    rows = []
    for src, title, cat, stocks, sector in items:
        kind, what, why = pick(title, cat, stocks, comp, regs, have, sector)
        res[(src, kind)] += 1
        rows.append({"src": src, "title": title, "cat": cat, "kind": kind, "photo": what, "why": why})
    out = os.path.join(HERE, "output")
    os.makedirs(out, exist_ok=True)
    json.dump(rows, open(os.path.join(out, "photo_dryrun.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for src in ("발행 글", "제목 묶음"):
        tot = sum(v for (s, _), v in res.items() if s == src)
        print(f"\n{src} {tot}건")
        for (s, k), v in sorted(res.items(), key=lambda x: -x[1]):
            if s == src:
                print(f"  {k:10s} {v:6d}  {v / tot:6.1%}")
    return rows


if __name__ == "__main__":
    main()
