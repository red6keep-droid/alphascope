"""목업 — 국가 경쟁력으로 본 한국 테마 종목 (지켜볼 것까지).

기획 doc/기획/국가-경쟁력-기획.md 9절 가설(H1~H5)을 테마 카드로 옮긴 것. 발행 전 목업이라 로컬 HTML만.
점유율 숫자는 data/store/competitiveness/(fetch_atlas.py)에서 계산, 회사 점유율은 기획 7절.

    python experiments/competitiveness/mock_themes.py && open experiments/competitiveness/output/mock_themes.html
"""
import html
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "data" / "store" / "competitiveness"
OUT = Path(__file__).resolve().parent / "output" / "mock_themes.html"
YEARS = (2014, 2019, 2024)

# 글자 · 색 — 디자인-가이드라인 3절 · 4절 · 5절
BODY, TINY, NAME = 19, 14, 16
LH_BODY, LH_CARD, LH_TINY = 34, 24, 20
C_TITLE, C_TEXT, C_GUIDE, C_SUB = "#111", "#333", "#6B7280", "#7A7A7A"
PILL = {  # 테두리, 글자, 배경
    "pos": ("#FCA5A5", "#B91C1C", "#FEF2F2"),
    "neg": ("#93C5FD", "#1D4ED8", "#EFF6FF"),
    "mix": ("#FDBA74", "#C2410C", "#fff"),
    "neu": ("#CBD5E1", "#64748B", "#fff"),
    "area": ("#CBD5E1", "#334155", "#fff"),
}

# 테마 — codes: HS92 4자리(세계 수출 점유율)
THEMES = [
    {
        "group": "중국이 아직 못 따라오는 곳",
        "name": "메모리 · 고대역폭 메모리(HBM)", "hyp": "H1 · H3", "codes": ["8542", "8523"],
        "share": ("pos", "▲ 커지는 중"), "share_note": "집적회로 · 저장장치 세계 수출 점유율 5년 사이 13.6 → 14.7%",
        "price": ("pos", "있음"), "price_note": "2025년 하반기부터 D램 값이 크게 올랐다는 보도(트렌드포스 4분기 D램 매출 +29.4%)",
        "who": ("mix", "1등이 바뀜"), "who_note": "고대역폭 메모리 1등이 삼성전자 → SK하이닉스(2022년 50%, 최근 분기 50~69%)",
        "stocks": [
            ("SK하이닉스", "000660", "고대역폭 메모리 1등, 지금 몫을 가져가는 쪽"),
            ("삼성전자", "005930", "D램 매출 1위권 · 고대역폭 메모리는 뒤쫓는 쪽, 몫을 되찾는지"),
            ("한미반도체", "042700", "고대역폭 메모리를 쌓는 장비, 생산이 늘면 따라가지만 고객이 몇 곳뿐"),
        ],
        "watch": [
            ("경쟁력", "반도체 수출금액 · 물량", "관세청 · 매월 1일 · 10일 단위", "물량은 느는데 금액이 줄면 값이 밀리는 것"),
            ("값을 정할 힘", "D램 수출물가", "한국은행 · 매월", "3개월 연속 하락"),
            ("값을 정할 힘", "회사 영업이익률", "전자공시 · 분기", "매출은 느는데 이익률이 줄 때"),
            ("몫", "고대역폭 메모리 회사별 점유율", "트렌드포스 · 카운터포인트 보도 · 분기", "1등 몫이 두 분기 연속 줄 때"),
        ],
        "turn": "중국 메모리(창신메모리 · 양쯔메모리)가 고급 제품에서 점유율을 얻기 시작할 때",
    },
    {
        "group": "중국이 아직 못 따라오는 곳",
        "name": "화장품", "hyp": "H3", "codes": ["3304"],
        "share": ("pos", "▲ 커지는 중"), "share_note": "세계 수출 점유율 30년 꾸준히 증가 · 5년 사이 9.5 → 12.9%",
        "price": ("neu", "판단 유보"), "price_note": "수출 단가(금액 ÷ 무게)를 아직 모으지 않았다",
        "who": ("mix", "새 회사로 이동"), "who_note": "나라 점유율은 커졌지만 옛 대표(아모레퍼시픽)는 2016~2023 주가 하락, 몫은 새 브랜드 · 위탁생산 · 유통으로",
        "stocks": [
            ("코스맥스", "192820", "위탁생산, 새 브랜드가 많아질수록 일감이 늘어나는 쪽"),
            ("한국콜마", "161890", "위탁생산, 코스맥스와 같은 자리"),
            ("에이피알", "278470", "새 브랜드 · 미용 기기, 몫을 새로 가져간 쪽"),
            ("실리콘투", "257720", "한국 화장품 해외 유통, 브랜드가 아니라 길목"),
            ("아모레퍼시픽", "090430", "옛 대표, 중국 의존을 줄이고 몫을 되찾는지"),
            ("LG생활건강", "051900", "옛 대표, 같은 질문"),
        ],
        "watch": [
            ("경쟁력", "화장품 수출 · 나라별(미국 · 일본 · 중국)", "관세청 · 매월", "미국 · 일본 수출이 꺾일 때"),
            ("값을 정할 힘", "수출 단가(금액 ÷ 무게)", "관세청 · 매월", "물량만 늘고 단가가 내려갈 때"),
            ("몫", "회사별 매출 증가율 · 해외 비중", "전자공시 · 분기", "위탁생산 매출이 브랜드 매출보다 늦게 늘 때"),
        ],
        "turn": "미국 수출 증가세가 멈추고 단가가 내려갈 때",
    },
    {
        "group": "중국이 아직 못 따라오는 곳",
        "name": "유기발광 디스플레이(OLED)", "hyp": "H1", "codes": None,
        "share": ("pos", "한국 81%"), "share_note": "디스플레이 전체는 중국 53 · 한국 32%(2025)지만 유기발광은 한국 81 · 중국 18%",
        "price": ("neu", "판단 유보"), "price_note": "패널 값 자료를 아직 모으지 않았다",
        "who": ("mix", "엇갈림"), "who_note": "액정(LCD)은 중국이 가져감(한국 10%), 유기발광은 삼성디스플레이(비상장 · 삼성전자 자회사) · LG디스플레이",
        "stocks": [
            ("LG디스플레이", "034220", "액정을 접고 유기발광으로 옮기는 중, 적자에서 벗어나는지"),
        ],
        "watch": [
            ("경쟁력", "유기발광 나라별 점유율", "옴디아 · 한국디스플레이산업협회 · 분기", "중국(BOE)이 아이폰 · 노트북 패널을 더 가져갈 때"),
            ("값을 정할 힘", "회사 영업이익률", "전자공시 · 분기", "적자로 돌아갈 때"),
        ],
        "turn": "중국 유기발광 점유율이 20%를 넘을 때",
    },
    {
        "group": "안보가 만든 곳",
        "name": "방산", "hyp": "H1 · H5", "codes": ["9301", "8710"],
        "share": ("pos", "▲ 커지는 중"), "share_note": "무기 · 전차 세계 수출 점유율 2.8 → 24.7%(2024 인도가 몰린 해) · 무기 수출 전체(SIPRI)는 3.0%로 세계 9위",
        "price": ("pos", "있음"), "price_note": "수주 잔고가 쌓여 있다는 보도, 우리 자료로는 아직 확인 전",
        "who": ("neu", "대표 회사"), "who_note": "정부 간 계약이라 몫은 기존 대형사에",
        "stocks": [
            ("한화에어로스페이스", "012450", "자주포(K9) · 다연장 로켓(천무) · 장갑차(레드백)"),
            ("현대로템", "064350", "전차(K2), 폴란드 계약"),
            ("LIG넥스원", "079550", "유도무기(천궁 II), 중동 수출"),
            ("한국항공우주산업", "047810", "경공격기(FA-50) · 헬기"),
        ],
        "watch": [
            ("경쟁력", "무기 수출 점유율", "SIPRI · 매년 3월", "순위가 내려갈 때"),
            ("값을 정할 힘", "수주 잔고 · 새 계약", "전자공시 · 수시", "잔고가 두 분기 연속 줄 때"),
            ("몫", "나라별 계약(폴란드 · 중동 · 유럽)", "국방부 · 회사 공시", "한 나라에 몰린 계약이 끝나 갈 때"),
        ],
        "turn": "전쟁 종료 · 유럽 자체 생산 확대로 새 계약이 끊길 때",
    },
    {
        "group": "안보가 만든 곳",
        "name": "원전", "hyp": "H5", "codes": ["8401"],
        "share": ("pos", "▲ 커지는 중"), "share_note": "원자로 · 핵연료 세계 수출 점유율 5년 사이 0.8 → 7.1%, 금액은 아직 작다(3억 달러)",
        "price": ("neu", "판단 유보"), "price_note": "계약 단위가 커서 해마다 튄다, 수주로 본다",
        "who": ("neu", "대표 회사"), "who_note": "정부(한국수력원자력)가 따고 기기 · 설계 회사가 나눈다",
        "stocks": [
            ("두산에너빌리티", "034020", "원자로 주기기 · 가스터빈"),
            ("한전기술", "052690", "원전 설계"),
            ("한국전력", "015760", "원전 수출 주체의 모회사, 이익은 전기요금(정부)에 묶여 있다"),
        ],
        "watch": [
            ("경쟁력", "해외 원전 수주 · 우선협상", "정부 · 회사 공시 · 수시", "입찰에서 연달아 빠질 때"),
            ("값을 정할 힘", "수주 잔고", "전자공시 · 분기", "잔고가 줄 때"),
        ],
        "turn": "해외 입찰 탈락 · 국내 원전 정책이 바뀔 때",
    },
    {
        "group": "안보가 만든 곳",
        "name": "전력기기(변압기)", "hyp": "H2", "codes": ["8504"],
        "share": ("neu", "작음 · 비슷함"), "share_note": "변압기 세계 수출 점유율 3.0 → 3.4% · 중국 31%",
        "price": ("pos", "있음"), "price_note": "미국 전력망 · 데이터센터 수요로 변압기가 모자라 값이 올랐다는 보도",
        "who": ("neu", "대표 회사"), "who_note": "미국에 공장 · 납품 기록이 있는 몇 곳",
        "stocks": [
            ("HD현대일렉트릭", "267260", "초고압 변압기, 미국 비중이 큼"),
            ("효성중공업", "298040", "초고압 변압기, 미국 공장"),
            ("LS ELECTRIC", "010120", "배전 · 전력 기기"),
        ],
        "watch": [
            ("경쟁력", "변압기 수출금액 · 미국 비중", "관세청 · 매월", "미국 수출이 꺾일 때"),
            ("값을 정할 힘", "수출 단가 · 영업이익률", "관세청 · 전자공시", "단가가 내려가기 시작할 때"),
            ("값을 정할 힘", "수주 잔고", "전자공시 · 분기", "잔고가 줄 때"),
        ],
        "turn": "미국 변압기 공급이 따라잡아 단가가 내려갈 때",
    },
    {
        "group": "중국과 겹치는 곳",
        "name": "조선", "hyp": "H2", "codes": ["8901"],
        "share": ("neg", "▼ 꺾이는 중"), "share_note": "신규 수주 점유율 44%(2018) → 17%(2024) → 21%(2025) · 중국 63~70%",
        "price": ("pos", "있음"), "price_note": "골라 받기 · 배값 상승으로 이익이 늘었다, 점유율과 주가가 엇갈린 대표 예",
        "who": ("neu", "대표 회사"), "who_note": "대형 3사가 액화천연가스선 · 고부가선에 집중",
        "stocks": [
            ("HD한국조선해양", "009540", "HD현대 조선 계열 지주"),
            ("HD현대중공업", "329180", "대형선 · 군함"),
            ("한화오션", "042660", "액화천연가스선 · 잠수함 · 미국 조선소"),
            ("삼성중공업", "010140", "액화천연가스선 · 해양 설비"),
        ],
        "watch": [
            ("경쟁력", "신규 수주 점유율(표준선 환산톤수)", "클락슨 보도 · 매월", "고부가선(액화천연가스선)에서도 중국에 밀릴 때"),
            ("값을 정할 힘", "새 배 값 지수(신조선가)", "클락슨 보도 · 매주", "지수가 꺾일 때"),
            ("값을 정할 힘", "선박 수주액", "한국은행 기계수주 · 매월", "3개월 연속 감소"),
        ],
        "turn": "새 배 값 지수가 꺾이고 중국이 고부가선 수주를 늘릴 때",
    },
    {
        "group": "중국과 겹치는 곳",
        "name": "배터리 · 양극재", "hyp": "H4", "codes": ["8507"],
        "share": ("neg", "▼ 꺾이는 중"), "share_note": "한국 3사 세계 점유율 34.7%(2020) → 15.4%(2025) · CATL 39%",
        "price": ("neg", "약함"), "price_note": "중국 저가 배터리(리튬인산철) · 리튬 값 하락",
        "who": ("neg", "고객을 따라감"), "who_note": "양극재 수출 점유율은 65%로 1위지만 고객(한국 3사)이 꺾이자 함께 꺾였다",
        "stocks": [
            ("LG에너지솔루션", "373220", "배터리 셀, 미국 공장 · 에너지 저장 장치로 되찾는지"),
            ("삼성SDI", "006400", "배터리 셀, 같은 질문"),
            ("SK이노베이션", "096770", "SK온(배터리)의 모회사"),
            ("에코프로비엠", "247540", "양극재, 고객 따라가는 쪽"),
            ("포스코퓨처엠", "003670", "양극재 · 음극재"),
            ("엘앤에프", "066970", "양극재"),
        ],
        "watch": [
            ("경쟁력", "한국 3사 세계 점유율(중국 포함)", "SNE리서치 보도 · 매월", "중국 제외 점유율까지 꺾일 때"),
            ("값을 정할 힘", "리튬 값 · 회사 영업이익률", "전자공시 · 분기", "적자가 이어질 때"),
            ("몫", "에너지 저장 장치 · 미국 공장 매출", "회사 실적 발표 · 분기", "미국 보조금이 줄 때"),
        ],
        "turn": "중국 제외 시장(미국 · 유럽)에서도 중국 회사가 점유율을 얻을 때",
    },
    {
        "group": "중국과 겹치는 곳",
        "name": "철강 · 석유화학 (견줄 쪽)", "hyp": "H1 · H2", "codes": ["7208", "7210"],
        "share": ("neg", "▼ 꺾이는 중"), "share_note": "열연 · 도금 강판 세계 수출 점유율 11.8 → 10.3% · 중국 14 → 30%",
        "price": ("neg", "약함"), "price_note": "석유화학은 점유율이 그대로인데도 중국 과잉 공급으로 적자 · 구조조정",
        "who": ("neu", "판단 유보"), "who_note": "업계 전체가 밀리는 쪽, 위 테마와 견주어 보는 기준",
        "stocks": [
            ("POSCO홀딩스", "005490", "철강, 이차전지 소재로 옮기는 중"),
            ("LG화학", "051910", "석유화학, LG에너지솔루션 모회사"),
            ("롯데케미칼", "011170", "석유화학, 구조조정 한가운데"),
        ],
        "watch": [
            ("경쟁력", "철강 · 석유화학 수출 물량", "관세청 · 매월", "중국 수출이 더 늘 때"),
            ("값을 정할 힘", "열연 강판 · 석유화학 수출물가", "한국은행 · 매월", "물가가 바닥을 벗어나는지"),
        ],
        "turn": "중국 감산이 실제로 시작될 때(반대로 회복 신호)",
    },
]


def load():
    prods = json.load(open(STORE / "products_hs92_4.json"))
    c2p = {v["code"]: k for k, v in prods.items()}
    data = {}
    for k in ("KOR", "CHN", "JPN", "TWN", "USA", "DEU"):
        d = defaultdict(dict)
        for r in json.load(open(STORE / f"cpy_{k}.json")):
            d[r["productId"]][r["year"]] = r
        data[k] = d
    return c2p, data


def share(c2p, data, k, codes, y):
    kv = w = 0
    for c in codes:
        r = data[k].get(c2p[c], {}).get(y)
        if r and r["globalMarketShare"]:
            kv += r["exportValue"]
            w += r["exportValue"] / r["globalMarketShare"]
    return kv / w * 100 if w else 0


def pill(kind, text):
    b, f, bg = PILL[kind]
    return (f'<span style="display:inline-block;border:1px solid {b};color:{f};background:{bg};border-radius:4px;'
            f'font-size:{TINY}px;line-height:1;padding:3px 5px 2px;white-space:nowrap;vertical-align:middle;'
            f'position:relative;top:-1px">{html.escape(text)}</span>')


def chart(vals, rival):
    """연도별 한국(진한) · 비교 나라(회색) 막대 — 최신 오른쪽, 범례 오른쪽(가이드라인 8절 · 시간 그래프 규칙). 비교 나라 = 그 산업 2024 점유율 1위(한국 제외)."""
    top = max(max(v) for v in vals.values()) or 1
    cols = []
    for i, y in enumerate(YEARS):
        bars = []
        for k, color in (("KOR", "#334155"), (rival, "#CBD5E1")):
            v = vals[k][i]
            h = max(2, round(v / top * 72))
            bars.append(f'<div style="display:flex;flex-direction:column;align-items:center;justify-content:flex-end;width:34px">'
                        f'<div style="font-size:15px;line-height:15px;margin-bottom:4px;color:{C_TEXT}">{v:.0f}</div>'
                        f'<div style="width:24px;height:{h}px;background:{color};border-radius:2px 2px 0 0"></div></div>')
        cols.append(f'<div style="display:flex;flex-direction:column;align-items:center">'
                    f'<div style="display:flex;gap:4px;align-items:flex-end;height:96px">{"".join(bars)}</div>'
                    f'<div style="font-size:{TINY}px;line-height:{LH_TINY}px;color:{C_GUIDE};margin-top:4px">{y}</div></div>')
    legend = (f'<div style="display:flex;justify-content:flex-end;gap:12px;font-size:{TINY}px;line-height:{LH_TINY}px;color:{C_GUIDE};margin-bottom:6px">'
              f'<span><span style="display:inline-block;width:10px;height:10px;background:#334155;border-radius:2px;margin-right:4px"></span>한국</span>'
              f'<span><span style="display:inline-block;width:10px;height:10px;background:#CBD5E1;border-radius:2px;margin-right:4px"></span>{COUNTRY_KO[rival]}</span></div>')
    return (f'<div style="margin:10px 0 4px">{legend}<div style="display:flex;justify-content:space-around">{"".join(cols)}</div>'
            f'<div style="font-size:{TINY}px;line-height:{LH_TINY}px;color:{C_GUIDE};margin-top:6px">세계 수출 점유율(%) · 비교는 이 산업 1위 나라 · 하버드 경제복잡도 아틀라스</div></div>')


def q_row(label, verdict, note):
    kind, text = verdict
    return (f'<div style="display:flex;gap:10px;padding:8px 0;border-top:1px solid #F1F5F9">'
            f'<div style="flex:none;width:96px;font-size:{NAME}px;font-weight:700;color:{C_TITLE}">{label}</div>'
            f'<div style="flex:1;min-width:0">{pill(kind, text)}'
            f'<div style="font-size:{TINY}px;line-height:{LH_TINY}px;color:{C_SUB};margin-top:4px">{html.escape(note)}</div></div></div>')


def stock_row(name, code, role):
    return (f'<div data-row-link style="display:flex;gap:10px;align-items:baseline;padding:8px 12px;border:1px solid #E2E8F0;'
            f'border-radius:8px;margin-bottom:6px;background:#fff">'
            f'<div style="flex:none;font-size:{NAME}px;font-weight:700;color:{C_TITLE};white-space:nowrap">{html.escape(name)}'
            f'<span style="font-size:12px;font-weight:400;color:{C_SUB};margin-left:4px">{code}</span></div>'
            f'<div style="flex:1;min-width:0;font-size:{TINY}px;line-height:{LH_TINY}px;color:{C_TEXT}">{html.escape(role)}</div></div>')


def watch_block(watch, turn):
    rows = "".join(
        f'<div style="display:flex;gap:10px;padding:8px 0;border-top:1px solid #F1F5F9">'
        f'<div style="flex:none;width:96px">{pill("area", axis)}</div>'
        f'<div style="flex:1;min-width:0"><div style="font-weight:700;color:{C_TITLE}">{html.escape(what)}</div>'
        f'<div style="font-size:{TINY}px;line-height:{LH_TINY}px;color:{C_SUB}">{html.escape(src)}</div>'
        f'<div style="font-size:{TINY}px;line-height:{LH_TINY}px;color:{C_TEXT};margin-top:2px">꺾임 신호 : {html.escape(sig)}</div></div></div>'
        for axis, what, src, sig in watch)
    return (f'<details style="margin-top:10px"><summary style="cursor:pointer;font-size:{NAME}px;font-weight:700;color:{C_TITLE};padding:6px 0">지켜볼 것 보기</summary>'
            f'{rows}<div style="margin-top:8px;padding:10px 12px;background:#FFF7ED;border:1px solid #FEE6CA;border-radius:8px;line-height:{LH_CARD}px">'
            f'<span style="font-weight:700">가장 먼저 볼 꺾임</span> : {html.escape(turn)}</div></details>')


def theme_card(t, c2p, data):
    vals = rival = None
    if t["codes"]:
        vals = {k: [share(c2p, data, k, t["codes"], y) for y in YEARS] for k in data}
        rival = max((k for k in data if k != "KOR"), key=lambda k: vals[k][-1])
    return (f'<section style="border:1px solid #E2E8F0;border-radius:8px;padding:14px 14px 10px;margin:0 0 16px;background:#fff;line-height:{LH_CARD}px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px">'
            f'<div style="font-size:{BODY + 1}px;font-weight:700;color:{C_TITLE}">{html.escape(t["name"])}</div>{pill("neu", "가설 " + t["hyp"])}</div>'
            f'{chart(vals, rival) if vals else ""}'
            f'<div style="margin-top:6px">{q_row("경쟁력", t["share"], t["share_note"])}'
            f'{q_row("값을 정할 힘", t["price"], t["price_note"])}{q_row("몫", t["who"], t["who_note"])}</div>'
            f'<div style="font-size:{NAME}px;font-weight:700;color:{C_TITLE};margin:12px 0 6px">지켜볼 종목</div>'
            f'{"".join(stock_row(*s) for s in t["stocks"])}'
            f'{watch_block(t["watch"], t["turn"])}</section>')


# ---------- 독자 질문 다섯 개 (본론 앞) ----------
# 산업 묶음 — 5년 변화 그래프용(HS92 4자리)
INDUSTRIES = [
    ("양극재", ["2841"]), ("방산", ["9301", "8710"]), ("원전", ["8401"]), ("화장품", ["3304"]),
    ("승용차", ["8703"]), ("메모리", ["8542", "8523"]), ("석유화학", ["2902", "3901", "3902", "3903"]),
    ("전력기기", ["8504"]), ("선박", ["8901"]), ("철강", ["7208", "7210"]), ("배터리 셀", ["8507"]),
]
COUNTRY_KO = {"KOR": "한국", "CHN": "중국", "JPN": "일본", "TWN": "대만", "USA": "미국", "DEU": "독일"}

H2 = f'font-size:22px;line-height:28px;font-weight:700;color:{C_TITLE};margin:28px 0 12px'
CARD = f'border:1px solid #E2E8F0;border-radius:8px;padding:12px 14px;background:#fff;line-height:{LH_CARD}px'
GUIDE = f'font-size:{TINY}px;line-height:{LH_TINY}px;color:{C_GUIDE};padding-left:12px;margin:3px 0 1px'


def q_title(n, q):
    return f'<h2 style="{H2}">{n}. {html.escape(q)}</h2>'


def answer(one_liner, body_text):
    return (f'<div style="{CARD};margin-bottom:10px"><div style="font-weight:700;color:{C_TITLE}">{html.escape(one_liner)}</div>'
            f'<div style="margin-top:4px">{body_text}</div></div>')


def details(summary, inner):
    return (f'<details style="margin:6px 0 4px"><summary style="cursor:pointer;font-size:{NAME}px;font-weight:700;color:{C_TITLE};padding:6px 0">'
            f'{html.escape(summary)}</summary>{inner}</details>')


def top_products(c2p, data, n=8, min_value=3e9):
    """2024 한국 수출 30억 달러 이상 품목 가운데 세계 점유율 높은 순 · 6개 나라 안 순위."""
    prods = json.load(open(STORE / "products_hs92_4.json"))
    rows = []
    for pid, v in data["KOR"].items():
        r = v.get(2024)
        if not r or pid not in prods or (r["exportValue"] or 0) < min_value or not r["globalMarketShare"]:
            continue
        shares = {k: (data[k].get(pid, {}).get(2024) or {}).get("globalMarketShare") or 0 for k in data}
        rank = 1 + sum(1 for k, s in shares.items() if s > shares["KOR"])
        rows.append((shares["KOR"] * 100, prods[pid]["code"], r["exportValue"] / 1e9, rank, max(shares, key=shares.get)))
    rows.sort(reverse=True)
    return rows[:n]


PRODUCT_KO = {"2841": "양극재 등 금속산염", "8523": "저장장치(SSD 등)", "9301": "군용 무기", "2902": "방향족 석유화학", "3903": "스티렌 수지",
              "8901": "선박", "8710": "전차 · 장갑차", "8524": "기록 매체", "2901": "에틸렌 등", "8542": "반도체 집적회로", "3304": "화장품",
              "7210": "도금 강판", "2710": "석유제품", "8703": "승용차", "8473": "컴퓨터 부품", "7208": "열연 강판", "3902": "프로필렌 수지",
              "8529": "통신 · 디스플레이 부품", "8479": "산업용 기계", "8507": "배터리", "8534": "인쇄회로기판", "8504": "변압기"}


def hbar_rows(items, unit="%p"):
    """가로 막대 — 값 양수 빨강 ▲ · 음수 파랑 ▼ (4절), 가운데 0 축."""
    top = max(abs(v) for _, v in items) or 1
    out = []
    for name, v in items:
        w = max(2, round(abs(v) / top * 70))
        color, sign = ("#d93025", "▲") if v > 0 else ("#1a73e8", "▼") if v < 0 else ("#999", "")
        left = f'<div style="width:{w}px;height:14px;background:{color};border-radius:2px 0 0 2px;margin-left:auto"></div>' if v < 0 else ""
        right = f'<div style="width:{w}px;height:14px;background:{color};border-radius:0 2px 2px 0"></div>' if v > 0 else ""
        out.append(f'<div style="display:flex;align-items:center;gap:6px;padding:3px 0">'
                   f'<div style="flex:none;width:62px;font-size:{NAME}px;font-weight:700;color:{C_TITLE};text-align:right;white-space:nowrap">{html.escape(name)}</div>'
                   f'<div style="flex:none;width:72px;display:flex;justify-content:flex-end">{left}</div>'
                   f'<div style="flex:none;width:1px;height:20px;background:#CBD5E1"></div>'
                   f'<div style="flex:none;width:72px">{right}</div>'
                   f'<div style="flex:none;font-size:15px;color:{color};white-space:nowrap">{sign} {abs(v):.1f}{unit}</div></div>')
    return "".join(out)


def intro(c2p, data):
    chg = []
    for name, codes in INDUSTRIES:
        k = share(c2p, data, "KOR", codes, 2024) - share(c2p, data, "KOR", codes, 2019)
        c = share(c2p, data, "CHN", codes, 2024) - share(c2p, data, "CHN", codes, 2019)
        chg.append((name, k, c))
    chg.sort(key=lambda x: -x[1])

    # 1. 무엇을 잘하나
    tp = top_products(c2p, data)
    tp_rows = "".join(
        f'<div style="display:flex;gap:10px;align-items:center;padding:6px 0;border-top:1px solid #F1F5F9">'
        f'<div style="flex:1;min-width:0;font-size:{NAME}px;font-weight:700;color:{C_TITLE}">{html.escape(PRODUCT_KO.get(code, code))}'
        f'<span style="font-size:12px;font-weight:400;color:{C_SUB};margin-left:4px">{val * 10:.0f}억 달러</span></div>'
        f'<div style="flex:none;width:112px;display:flex;align-items:center;gap:6px"><div style="width:{max(2, round(s / tp[0][0] * 70))}px;height:14px;background:#334155;border-radius:2px"></div>'
        f'<span style="font-size:15px">{s:.0f}%</span></div>'
        f'<div style="flex:none;width:76px">{pill("pos" if rank == 1 else "neu", f"6국 중 {rank}위")}</div></div>'
        for s, code, val, rank, top in tp)
    q1 = (q_title(1, "한국은 세계에서 무엇을 잘하나요?") +
          answer("반도체 · 저장장치 · 양극재 · 선박 · 화장품 · 석유화학에서 세계 몫이 큽니다.",
                 "세계로 나간 물건 100개 가운데 한국 것이 몇 개인지(세계 수출 점유율)로 봤습니다. 양극재는 65%로 세계 1위, 반도체 집적회로는 15%로 대만 · 중국에 이어 3위, 선박은 중국에 이어 2위입니다. 단위는 2024년 한국에서 나간 수출이라 해외 공장 생산은 들어 있지 않습니다.") +
          f'<div style="{CARD}"><div style="display:flex;justify-content:space-between;font-size:{TINY}px;line-height:{LH_TINY}px;color:{C_GUIDE}"><span>품목 · 2024 수출액</span><span>세계 점유율 · 한국 · 중국 · 일본 · 대만 · 미국 · 독일 중 순위</span></div>{tp_rows}</div>' +
          f'<div style="{GUIDE}">ⓘ 2024년 수출 30억 달러 이상 품목 가운데 세계 점유율이 높은 순 · 하버드 경제복잡도 아틀라스(국제무역 통계를 나라끼리 맞춘 값)</div>')

    # 2. 커지나 줄어드나
    q2 = (q_title(2, "그 힘은 커지고 있나요, 줄고 있나요?") +
          answer("갈립니다. 양극재 · 방산 · 원전 · 화장품은 커지고, 배터리 셀 · 철강 · 선박은 줄었습니다.",
                 "2019년과 2024년의 세계 점유율 차이(%p)입니다. 5년을 쓴 이유는 1년 숫자는 반도체 값이나 무기 인도 시점에 따라 크게 흔들리기 때문입니다. 방산 · 원전은 큰 계약이 물건을 넘긴 해에 몰려 잡히니 숫자가 커 보여도 금액은 아직 작습니다.") +
          f'<div style="{CARD}"><div style="font-size:{TINY}px;line-height:{LH_TINY}px;color:{C_GUIDE};margin-bottom:4px">한국 세계 수출 점유율 변화 · 2019 → 2024</div>{hbar_rows([(n, k) for n, k, _ in chg])}</div>')

    # 3. 누가 가져가나 — 여섯 나라 모두
    moves, full = [], []
    for name, codes in INDUSTRIES:
        d = {k: share(c2p, data, k, codes, 2024) - share(c2p, data, k, codes, 2019) for k in data}
        up, dn = max(d, key=d.get), min(d, key=d.get)
        moves.append((name, up, d[up], dn, d[dn]))
        full.append((name, d))
    order = [n for n, _, _ in chg]
    moves.sort(key=lambda m: order.index(m[0]))
    full.sort(key=lambda f: order.index(f[0]))
    cell = lambda k, v: (f'<span style="color:#d93025">{COUNTRY_KO[k]} ▲ {v:.1f}</span>' if v > 0 else
                         f'<span style="color:#1a73e8">{COUNTRY_KO[k]} ▼ {abs(v):.1f}</span>')
    move_rows = "".join(
        f'<div style="display:flex;align-items:center;gap:6px;padding:5px 0;border-top:1px solid #F1F5F9">'
        f'<div style="flex:none;width:62px;font-size:{NAME}px;font-weight:700;color:{C_TITLE};white-space:nowrap">{html.escape(n)}</div>'
        f'<div style="flex:1;font-size:15px;white-space:nowrap">{cell(up, uv)}</div>'
        f'<div style="flex:1;font-size:15px;white-space:nowrap">{cell(dn, dv)}</div></div>'
        for n, up, uv, dn, dv in moves)
    head = (f'<div style="display:flex;gap:6px;font-size:{TINY}px;line-height:{LH_TINY}px;color:{C_GUIDE}">'
            f'<div style="flex:none;width:62px">산업</div><div style="flex:1">가장 늘어난 나라</div><div style="flex:1">가장 줄어든 나라</div></div>')
    th = "".join(f'<th style="font-weight:400;color:{C_GUIDE};padding:4px 6px;text-align:right;white-space:nowrap">{COUNTRY_KO[k]}</th>' for k in data)
    trs = "".join(
        f'<tr><td style="font-weight:700;color:{C_TITLE};padding:4px 6px;white-space:nowrap;border-top:1px solid #F1F5F9">{html.escape(n)}</td>' +
        "".join(f'<td style="padding:4px 6px;text-align:right;white-space:nowrap;border-top:1px solid #F1F5F9;color:{"#d93025" if v > 0 else "#1a73e8" if v < 0 else "#999"}">{"▲" if v > 0 else "▼" if v < 0 else ""} {abs(v):.1f}</td>' for v in d.values()) + '</tr>'
        for n, d in full)
    table = (f'<div style="overflow-x:auto"><table style="border-collapse:collapse;font-size:15px;line-height:{LH_CARD}px;min-width:100%">'
             f'<thead><tr><th style="font-weight:400;color:{C_GUIDE};padding:4px 6px;text-align:left">산업</th>{th}</tr></thead><tbody>{trs}</tbody></table></div>'
             f'<div style="font-size:{TINY}px;line-height:{LH_TINY}px;color:{C_GUIDE};margin-top:4px">세계 수출 점유율 변화(%p) · 2019 → 2024 · 여섯 나라 밖의 나라는 넣지 않았습니다</div>')
    q3 = (q_title(3, "누가 한국 몫을 가져가고, 한국은 누구 몫을 가져오나요?") +
          answer("한국이 잃은 곳은 모두 중국이 가져갔고, 한국이 얻은 곳은 주로 일본 몫을 가져온 것입니다.",
                 "한국 · 중국 · 일본 · 대만 · 미국 · 독일 여섯 나라를 같은 5년으로 놓고, 산업마다 누가 가장 늘고 누가 가장 줄었는지 봤습니다. 선박 · 철강 · 배터리 셀은 중국이 16~18%p씩 늘었고 일본 · 독일도 같이 줄었습니다. 양극재 · 화장품은 일본이 줄고 한국이 늘었습니다. 메모리는 대만, 석유화학은 미국이 상대입니다. 그래서 테마를 세 묶음으로 나눴습니다. ① 중국이 아직 못 따라오는 곳(고대역폭 메모리 · 유기발광 · 화장품) ② 안보가 만든 곳(방산 · 원전 · 전력기기) ③ 중국과 겹치는 곳(조선 · 배터리 · 철강 · 석유화학).") +
          f'<div style="{CARD}">{head}{move_rows}</div>' +
          details("여섯 나라 모두 보기", f'<div style="{CARD}">{table}</div>') +
          f'<div style="{GUIDE}">ⓘ 유럽은 독일로 대표했습니다. 유럽연합 전체 · 베트남 · 인도 등은 다음 판에서 더합니다.</div>')

    # 4. 사 두면 오르나
    cases = "".join(
        f'<div style="display:flex;gap:10px;padding:8px 0;border-top:1px solid #F1F5F9">'
        f'<div style="flex:none;width:72px;font-size:{NAME}px;font-weight:700;color:{C_TITLE}">{a}</div>'
        f'<div style="flex:1;min-width:0;font-size:{TINY}px;line-height:{LH_TINY}px;color:{C_TEXT}">{b}</div></div>'
        for a, b in (("조선", "수주 점유율은 44%에서 21%로 반토막. 그런데 배를 골라 받고 배값이 오르면서 2024~25년 주가는 크게 올랐습니다."),
                     ("화장품", "나라 점유율은 30년 내내 커졌는데 옛 대표(아모레퍼시픽)는 2016~2023년 주가가 내렸습니다. 몫은 새 브랜드 · 위탁생산 · 유통 회사로 갔습니다."),
                     ("양극재", "세계 1위(65%)인데 고객인 한국 배터리 3사 점유율이 35%에서 15%로 꺾이자 양극재 회사 주가도 2023년 고점 뒤 크게 떨어졌습니다."),
                     ("석유화학", "점유율은 오히려 커졌는데(22 → 24%) 중국 과잉 공급으로 업계는 적자 · 구조조정 중입니다.")))
    q4 = (q_title(4, "경쟁력 있는 산업의 주식을 사 두면 오르나요?") +
          answer("그렇게 단순하지 않았습니다. 점유율과 주가가 엇갈린 사례가 많습니다.",
                 "나라가 잘 판다고 그 이익이 주주에게 오는 것은 아니었습니다. 이익은 값을 정할 힘이 있는 회사에, 그리고 그 몫을 새로 가져가는 회사에 갔습니다. 오래된 연구도 같은 말을 합니다. 경제가 빨리 큰 나라일수록 주식 수익이 높지는 않았고(리터, 16개국 100년), 시장을 몇 회사가 나눠 가진 업종의 수익률은 오히려 낮았습니다(허우 · 로빈슨, 미국 40년).") +
          f'<div style="{CARD}"><div style="font-size:{TINY}px;line-height:{LH_TINY}px;color:{C_GUIDE}">점유율과 주가가 엇갈린 사례</div>{cases}</div>' +
          f'<div style="{GUIDE}">ⓘ 주가 흐름은 알려진 사실을 옮긴 것이고 우리 자료로 계산한 수익률이 아닙니다.</div>')

    # 5. 그럼 무엇을 봐야 하나
    guide = "".join(
        f'<div style="display:flex;gap:10px;padding:8px 0;border-top:1px solid #F1F5F9"><div style="flex:none;font-weight:700;width:104px;color:{C_TITLE}">{a}</div>'
        f'<div style="flex:1"><div>{b}</div><div style="font-size:{TINY}px;line-height:{LH_TINY}px;color:{C_SUB}">{c}</div></div></div>'
        for a, b, c in (("경쟁력", "그 산업에서 한국 몫이 5년 전보다 커졌나", "세계 수출 점유율 · 회사 점유율"),
                        ("값을 정할 힘", "많이 파는 것보다 비싸게 팔 수 있나", "수출 단가 · 수출물가 · 영업이익률 · 수주 잔고"),
                        ("몫", "나라가 번 것을 어느 회사가 가져가나", "회사별 점유율 · 매출 증가율")))
    q5 = (q_title(5, "그럼 무엇을 지켜봐야 하나요?") +
          answer("테마마다 세 가지를 같이 봅니다. 경쟁력, 값을 정할 힘, 몫.",
                 "경쟁력은 그 산업이 살아 있는지를 알려 주고, 나머지 둘은 그 이익을 누가 얼마나 가져가는지를 알려 줍니다. 아래 테마 카드마다 이 세 가지의 지금 상태와, 꺾일 때 가장 먼저 나타날 신호를 적었습니다.") +
          f'<div style="{CARD}">{guide}</div>' +
          f'<div style="{GUIDE}">ⓘ 같은 테마 안에서도 몫을 가져가는 회사와 놓치는 회사가 갈립니다. 종목은 테마 안 역할로 나눴고, 사라는 뜻이 아닙니다.</div>')
    return q1 + q2 + q3 + q4 + q5


def main():
    c2p, data = load()
    groups, body = [], []
    for t in THEMES:
        if t["group"] not in groups:
            groups.append(t["group"])
            body.append(f'<h2 style="{H2}">{html.escape(t["group"])}</h2>')
        body.append(theme_card(t, c2p, data))
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>한국 경쟁력 테마 종목</title>
<style>body{{margin:0;background:#F8FAFC;font-family:-apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;color:{C_TEXT}}}
.wrap{{max-width:720px;margin:0 auto;padding:16px 16px 40px;font-size:{BODY}px;line-height:{LH_BODY}px}}
[data-row-link]:active{{background:#F1F5F9!important}}
@media (max-width:680px){{h2{{font-size:20px!important;line-height:26px!important}}}}</style></head>
<body><div class="wrap">
<h1 style="font-size:27px;line-height:36px;color:{C_TITLE};margin:8px 0 10px">한국은 무엇을 잘하나, 그 종목은 오를까</h1>
<p data-seo-lead style="margin:0 0 12px">한국이 세계에서 경쟁력 있는 산업과 그 테마 종목을 숫자로 봅니다. "경쟁력 있는 산업의 주식을 사 두면 시간이 지나면 오르지 않을까"라는 물음에서 시작해, 한국이 무엇을 잘하는지 · 그 힘이 커지는지 · 누가 그 몫을 가져가는지 · 정말 주가로 이어졌는지 · 그럼 무엇을 지켜봐야 하는지 순서로 답합니다.</p>
{intro(c2p, data)}
<h2 style="{H2};margin-top:36px">테마별로 보기</h2>
<div style="{GUIDE}">ⓘ 세 묶음 · 9개 테마 · 종목은 테마 안 역할로 나눴습니다. 카드 아래 `지켜볼 것 보기`에 지표 · 출처 · 꺾임 신호가 있습니다.</div>
{"".join(body)}
</div></body></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page)
    print(OUT)


if __name__ == "__main__":
    main()
