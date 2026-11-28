"""뉴스 글 자료 사진 고르기 — 발행기(news-posts) 가 글마다 부른다. AI 0 · 바깥 요청 0 · 쓰기 0.

    import photo_pick as PP
    pick = PP.pick(post, stocks)    # stocks = news_render.match_stocks 결과 [(ticker, name, "kr"|"us")]
    html = PP.figure(pick)          # 사진 없으면 ""

재료: photo_index.json (photo_store.py 가 만든 사진 목록, 공개 저장소) · ../ref/quick_ref.json (853종목 업종).
규칙 = 운영지침 4-6 · 비공개 기획/자료-사진-이어가기.md. 고르는 순서(위에서 먼저 맞는 것 — 틀린 사진보다 사진 없음):
  1 인물  제목에 인물 이름(뒤에 '장남 · 가족' 이면 X)
  2 회사  글 종목 첫째만(제목에서 회사 이름 짐작 X — 미리 돌려 보기에서 상대 회사가 잡히는 오류 약 10%)
          회사 사진 있음 = 회사 사진만 · 없음 = 업종 사진 + 오른쪽 아래 흰 이름표
  3 기관 · 국제 · 시장  제목 낱말(같은 낱말이 다른 뜻으로 많이 쓰이는 것은 함께 있는 말이 있어야)
  4 기업 사건 · 실적인데 종목 없음 = 글 업종 사진
  5 분류  수집기 기사 분류 → 사건 분류 사진 (주가 전광판 = 한국 기사는 코스피 · 여의도, 미국 기사는 나스닥 · 월가 · 뉴욕증권거래소 빌려 씀)
  6 없음  (국제 분류인데 나라 · 사건 낱말 없음 포함)
같은 글 = 늘 같은 사진(글 번호 해시로 고정), 같은 폴더 기사끼리는 돌려 쓴다.
"""
import hashlib
import html as _h
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "photo_index.json")
REF = os.path.join(HERE, "..", "ref", "quick_ref.json")

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
    "기재부": "정부세종청사", "기획재정부": "정부세종청사", "금융위": "정부서울청사", "금융위원회": "정부서울청사", "금감원": "정부서울청사",
    "금융감독원": "정부서울청사", "중국 정부": "중국_정부", "국무원": "중국_정부",
}
WORLD = {
    "북한": "북한", "우크라이나": "우크라이나_전쟁", "러시아": "우크라이나_전쟁", "이스라엘": "이스라엘_·_가자", "가자": "이스라엘_·_가자",
    "이란": "중동_·_이란", "중동": "중동_·_이란", "대만": "대만_해협", "미중": "미중_관계", "G7": "G7_·_정상회의", "G20": "G7_·_정상회의",
    "정상회담": "G7_·_정상회의", "OPEC": "OPEC", "제재": "제재_·_수출_통제", "수출 통제": "제재_·_수출_통제", "수출통제": "제재_·_수출_통제",
    "지진": "자연재해", "태풍": "자연재해", "홍수": "자연재해", "산불": "자연재해", "감염병": "감염병", "독감": "감염병", "유조선": "유가_·_유조선",
}
MARKET = {
    "코스피": "한국거래소_·_코스피", "코스닥": "한국거래소_·_코스피", "한국거래소": "한국거래소_·_코스피", "여의도": "여의도",
    "나스닥": "나스닥", "뉴욕증시": "뉴욕증권거래소", "뉴욕 증시": "뉴욕증권거래소", "다우": "뉴욕증권거래소", "S&P": "뉴욕증권거래소",
    "월가": "월가", "월스트리트": "월가", "상하이": "상하이_·_홍콩_증시", "홍콩증시": "상하이_·_홍콩_증시", "항셍": "상하이_·_홍콩_증시",
}
CAT = {   # 수집기 기사 분류 → 사건 분류 폴더
    "CORP_EVENT": "기업_사건_·_인수합병", "MARKET_STRUCTURE": "@board", "AI_CAPEX": "AI_투자", "REGULATION": "규제_·_소송",
    "CREDIT_BANKS": "금융_·_신용_·_은행", "TARIFF_TRADE": "관세_·_무역", "EARNINGS": "실적_발표", "GROWTH_JOBS": "경기_·_고용",
    "REAL_ESTATE": "부동산_·_주택", "RATES_FED": "금리_·_연준", "FX_GLOBAL": "환율", "OIL_ENERGY": "유가_·_원자재",
    "FISCAL_POLITICS": "재정_·_정치_·_선거", "CRYPTO": "암호화폐", "INFLATION": "물가", "GEOPOLITICS": "@none",
}
BOARD = {   # 주가 전광판 = 이웃 폴더 빌려 쓰기(11-28 사용자) — 월가 사진을 한국 기사에 쓰지 않는다
    "kr": ["주가_전광판", "한국거래소_·_코스피", "여의도"],
    "us": ["주가_전광판", "나스닥", "월가", "뉴욕증권거래소"],
}
US_WORDS = r"미국|美|뉴욕|나스닥|S&P|다우|월가|연준"
NEED = {
    "대만": r"해협|양안|군사|침공|중국.*(압박|훈련)", "러시아": r"우크라|전쟁|휴전|드론|공격|파병", "대법원": r"미국|美|연방",
    "국방부": r"미국|美|펜타곤", "의회": r"미국|美|하원|상원", "정상회담": r"정상", "다우": r"지수|뉴욕|증시|마감",
}
SKIP_AFTER = r"\s*(장남|차남|아들|딸|일가|가족|동생|부인|전 부인|측근)"
# 업종 이름(종목 세부 업종 · 업종, 수집기 글 sector) → 업종 사진 폴더 (위에서 먼저 맞는 것)
IND = [
    ("2차전지|1차전지|ESS|연료전지|배터리", "2차전지"), ("데이터센터", "AI_·_데이터센터"),
    ("반도체 장비|반도체 테스트|반도체 후공정|반도체 부품|반도체 소재|반도체 · 디스플레이|반도체 설계", "메모리_·_반도체_장비"), ("반도체", "반도체"),
    ("조선|선박", "조선"), ("해운|택배|물류|화물|철도", "해운_·_컨테이너"), ("항공사|여객 항공|지주회사 \\(항공\\)", "항공"),
    ("우주", "우주_·_항공_산업"), ("방위|방산|탄약|인공위성", "방산"), ("원전|원자력|발전|전기 유틸리티|대체 전력|태양광|풍력", "원자력_·_전력"),
    ("중전기|전선|전기 부품|전기 제품|전력", "전력기기_·_변압기"), ("가스 유틸리티|가스 유통|수도|종합 공업|유틸리티", "유틸리티_·_가스"),
    ("석유|정유|가스", "정유_·_석유화학"), ("철강|금속|구리|광물", "철강"), ("화학|소재|비료|산업 가스|포장|용기|도료|OLED|동박", "화학_·_소재"),
    ("자동차|타이어|여객 육상", "자동차"), ("종합상사", "해운_·_컨테이너"), ("산업 지주|섬유", "화학_·_소재"), ("기계|중장비|모터|농기계|로봇", "로봇_·_기계"), ("건설|건자재|주택|부동산|리츠|임대", "건설_·_부동산"),
    ("증권|자산 운용|투자|거래소|펀드|다섹터 지주", "증권_·_투자"), ("은행|금융 지주|소비자 금융|리스|결제", "은행"), ("보험", "보험"),
    ("제약|바이오|라이프 사이언스|펩타이드|줄기세포|백신", "제약_·_바이오"), ("의료|병원|간호|헬스", "의료기기_·_병원"),
    ("게임|카지노|엔터|영화|음반|방송|출판|케이블", "게임_·_엔터테인먼트"), ("호텔|리조트|크루즈|여행|식당", "호텔_·_여행_·_카지노"),
    ("통신|타워", "통신"), ("소프트웨어|IT|인터넷|인터랙티브|광고|마케팅|데이터 처리|컨설팅|AI", "인터넷_·_소프트웨어"),
    ("담배|주류|양조", "담배_·_주류"), ("음료|식품|사탕|육류|농산물|제과|급식|수산", "식품_·_음료"), ("화장품|개인 관리|가정|생활용품", "화장품"),
    ("백화점|유통|소매|전문점|의류|신발|명품|여가|대형마트|쇼핑", "유통_·_대형마트"), ("전자|하드웨어|카메라|디스플레이|계측|가전|커넥터|기판", "반도체"),
]
SECTOR_FALLBACK = {"산업재": "로봇_·_기계", "금융": "증권_·_투자"}   # 세부 업종이 어느 폴더에도 안 맞는 것(서비스 · 지주 11곳) — 이름표가 회사를 말한다
HANGUL = "가-힣A-Za-z0-9"

_DATA = {}


def _load():
    if not _DATA:
        idx = json.load(open(INDEX, encoding="utf-8"))
        by_folder, by_sym = {}, {}
        for p in idx["photos"]:
            p = dict(p, url=idx["base"] + p["id"] + ".webp")
            if p["sym"]:
                by_sym.setdefault((p["group"].split("/")[-1].lower(), p["sym"].upper()), []).append(p)
            else:
                by_folder.setdefault(p["group"].split("/")[-1], []).append(p)
        ref = json.load(open(REF, encoding="utf-8")) if os.path.exists(REF) else {"kr": {}, "us": {}}
        _DATA.update(folder=by_folder, sym=by_sym, ref=ref)
    return _DATA


def word_re(name):
    # 앞: 글자 아님 · 뒤: 글자 아님 또는 조사 하나 — '파월'이 '파월스'에 붙지 않게
    return re.compile(rf"(?<![{HANGUL}]){re.escape(name)}(?=$|[^{HANGUL}]|[은는이가을를의에과와도로만](?:$|[^{HANGUL}]))")


def industry(text):
    return next((f for pat, f in IND if re.search(pat, text or "")), None)


def _choose(photos, key):
    """글 번호로 고정 — 같은 글은 늘 같은 사진, 같은 폴더 글끼리는 해시로 흩어진다."""
    photos = sorted(photos, key=lambda p: p["id"])
    return photos[int(hashlib.sha1(str(key).encode()).hexdigest(), 16) % len(photos)]


def _stock_rec(ticker, mk):
    ref = _load()["ref"]
    if mk == "kr":
        return next((v for s, v in ref["kr"].items() if s.split(".")[0] == ticker), None)
    return ref["us"].get(ticker)


def _ref_find(code, name):
    """853종목에서 코드 또는 한글 이름으로 → (ticker, name, mk)."""
    ref = _load()["ref"]
    for mk in ("kr", "us"):
        for s, v in ref[mk].items():
            t = s.split(".")[0] if mk == "kr" else s
            if (code and t == code) or (name and v["ko"] == name):
                return t, v["ko"], mk
    return None


def pick(post, stocks=()):
    """post = 수집기 글(title · cat · sector · id) · stocks = [(ticker, name, mk)] 글 종목(블로그 목록에 맞은 것).
    → {photo, label: (로고 심볼, 이름) | None, kind, why} 또는 None."""
    d = _load()
    folders = d["folder"]
    title = post.get("title") or ""
    key = post.get("id") or post.get("slug") or title

    def out(photos, kind, why, label=None):
        return {"photo": _choose(photos, key), "label": label, "kind": kind, "why": why} if photos else None

    for k, f in PEOPLE.items():
        m = word_re(k).search(title)
        if m and folders.get(f) and not re.match(SKIP_AFTER, title[m.end():]):
            return out(folders[f], "인물", k)
    first = (post.get("stocks") or [None])[0]   # 수집기 글 첫 종목 = 주인공(블로그 목록 밖이어도 둘째로 넘어가지 않는다)
    hit = None
    if first:
        code, nm = str(first.get("code") or ""), (first.get("name") or "").strip()
        hit = next(((t, n, mk) for t, n, mk in stocks if t == code or n == nm), None)
        if not hit:
            hit = _ref_find(code, nm) or (code, nm, "kr" if re.fullmatch(r"\d{6}", code) else "")
    elif stocks:
        hit = stocks[0]
    if hit:
        t, name, mk = hit
        own = d["sym"].get((mk, t.upper())) if mk else None
        if own:
            return out(own, "회사 사진", name)
        rec = _stock_rec(t, mk) if mk else None
        f = (industry((rec or {}).get("sub")) or industry((rec or {}).get("sector")) or SECTOR_FALLBACK.get((rec or {}).get("sector"))
             if rec else industry(post.get("sector")))
        logo = ((t + ".KS") if mk == "kr" else t) if t else ""
        if f and folders.get(f):
            return out(folders[f], "업종 사진 + 이름표", f"{name} → {f}" + ("" if rec else " (글 업종)"), (logo, name))
    for kind, table in (("기관", INST), ("국제", WORLD), ("시장", MARKET)):
        for k, f in table.items():
            if word_re(k).search(title) and folders.get(f) and (k not in NEED or re.search(NEED[k], title)):
                if k == "정상회담" and re.search(r"미국|美|미중", title) and re.search(r"중국|中|미중", title):
                    f = "미중_관계"
                return out(folders[f], kind, k)
    cat = post.get("cat") or ""
    f = industry(post.get("sector")) if cat in ("CORP_EVENT", "EARNINGS") else None
    if f and folders.get(f):
        return out(folders[f], "업종 사진", f"글 업종 '{post.get('sector')}'")
    f = CAT.get(cat)
    if f == "@board":
        mk = "us" if re.search(US_WORDS, title) else "kr"
        return out([p for g in BOARD[mk] for p in folders.get(g, [])], "시장", f"주가 전광판({'미국' if mk == 'us' else '한국'})")
    if f and f != "@none" and folders.get(f):
        return out(folders[f], "분류", cat)
    return None


def figure(pick, logo_html=None):
    """제목 아래 사진 칸(운영지침 4-6): 높이 200 · 모서리 10 · 출처 줄 11/16 #9CA3AF 오른쪽 · 요약 상자와 26.
    logo_html = 이름표 로고 그리는 함수(design_kit.ticker_logo) — 이름표가 있을 때만."""
    if not pick:
        return ""
    p = pick["photo"]
    chip = ""
    if pick.get("label") and logo_html:
        sym, name = pick["label"]
        logo = logo_html(sym, 24).replace("vertical-align:-4px;", "flex:none;")
        chip = (f'<span style="position:absolute;right:12px;bottom:12px;display:flex;align-items:center;gap:6px;height:32px;padding:0 12px 0 4px;'
                f'border-radius:16px;background:#fff;font-size:14px;line-height:20px;font-weight:700;color:#111;">{logo}{_h.escape(name)}</span>')
    a = 'style="color:inherit;text-decoration:none;"'
    cap = (f'자료 사진 · <a href="{_h.escape(p["source"])}" {a} rel="nofollow noopener" target="_blank">{_h.escape(p["artist"])}</a>'
           f' · <a href="{_h.escape(p["license_url"])}" {a} rel="nofollow noopener" target="_blank">{_h.escape(p["license"])}</a>'
           + (" · 일부 자름" if p.get("crop") else ""))
    what = re.sub(r"^(File:|flickr: )", "", p.get("title") or "").rsplit(".", 1)[0] if (p.get("title") or "").startswith("File:") else re.sub(r"^flickr: ", "", p.get("title") or "")
    return (f'<figure data-news-photo="{p["id"]}" style="margin:0 0 26px;"><div style="position:relative;">'
            f'<img src="{p["url"]}" alt="자료 사진: {_h.escape(what)}" width="{p["w"]}" height="{p["h"]}" loading="eager" '
            f'style="display:block;width:100%;height:200px;object-fit:cover;border-radius:10px;">{chip}</div>'
            f'<figcaption style="margin:6px 0 0;font-size:11px;line-height:16px;color:#9CA3AF;text-align:right;">{cap}</figcaption></figure>')
