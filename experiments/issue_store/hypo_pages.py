"""증시 전망 — 전망 고정 페이지 · 목록 고정 페이지 · 홈 카드 JSON 렌더러 + 판정 엔진(틀 S · 틀 R).

    python experiments/issue_store/hypo_pages.py      # EH-2026-001 목업(전망 1 · 2 · 목록 · hypo.json) → output/ (그 다음 home_mock.py)
    python experiments/issue_store/forecast_cases.py  # 경우의 수 목업(A 거시 · B 업종 · C 종목 × 상황 탭) → output/mock_forecast-cases.html

용어 (2026-11-07 사용자: "반등 · 되돌림 차이가 있나, 하락 지속이면 상승 지속은? 용어부터 통일") — 기획 증시-전망-기획 9절:
- 방향 = `상승` · `하락` 둘뿐(블로그 신호 용어와 같다).
- 사건 전 전망(틀 S) 갈래 = `{대상} 상승` · `{대상} 하락`. 조건 = 사건의 두 결과(`… 시`).
- 충격 뒤 전망(틀 R) 갈래 = 급락 뒤 `{대상} 반등` · `{대상} 하락 지속`, 급등 뒤 `{대상} 조정` · `{대상} 상승 지속` (2026-11-07 사용자: "되돌림은 생소하다, 미디어도 반등을 쓴다").
  반등 = 빠진 폭의 절반을 회복, 조정 = 오른 폭의 절반을 반납. 지속 = 충격 방향으로 금만큼 더 가는 것. `되돌림` 은 쓰지 않는다.
- 국면(날마다) = `지켜보는 중` · `{갈래} 우세`(금의 3분의 1 · 반등 · 조정은 4분의 1). 판정 = `맞음` · `틀림` · `제자리`(창 끝까지 금 안).
- 갈래 카드의 답 = 그 갈래에 일어난 사실: `지켜보는 중` · `우세` · `실현` · `해당 없음`(P415, 옛 `일어나지 않음`). 맞음 · 틀림은 맨 위 `전망 결과` 에만.
- 표시 라벨 = 충격 뒤 전망의 `우리 전망`(기록상 분포로 고른 쪽)만. 사건 전 전망의 `실제 결과` 라벨은 삭제(P414 — 일어난 쪽은 답 · 색으로 보인다).
- 갈래 순서 = 높은 쪽(상승 이름표) 위 `전망 A` · 낮은 쪽 아래 `전망 B`(P411, 화면 순서만 — 판정 번호 no 는 그대로). `그 밖이면` 같은 조건은 짝 조건의 반대 문장으로 자동(P412).
- 독자 말(2026-11-07 저녁 재점검): `금` → `기준`, `충격 폭` → `급락 폭` · `급등 폭`, `창` → `60거래일 안에`, 구획 `더 알아보기` → `더 궁금한 것`, 갈래 구획은 `두 갈래 전망` 하나.
- 2026-11-07 밤 개선 10 전부 채택(기획 10절): ① 자 = 시장 모형 β 조정 초과수익(abnormal) ② 우리 전망에 기록상 비율(n번 중 m번) + 브라이어 ③ 고정 시점 판정(D+5 · 20 · 60) 병기, 플라시보는 검증해 때 ④ ~~뉴스 유무 갈림(Chan 2003)~~ 2026-11-10 폐지(바깥 연구 일반화) ⑤ 거래량 배수 ⑥ GPR · EPU 배경 ⑦ 기록 카드 n번 중 m번 + 범위 ⑧ 실적 전망 기준 = 옵션 내재 예상 폭
- 11-07 밤 11절 채택(1 · 2 · 3 · 6): 틀 S 에 시장 예상 확률(market_prob) → 결과 줄 `예상대로` · `예상 밖` · 목록 맨 위 `우리 전망 성적표`(scoreboard) · 기록 카드 `가장 비슷했던 때` 셋(history.alike) · 시점 고정(운영자 상자). 4 · 5 는 발행 단계 · 검증해 때
- 11-07 밤 선반영 · 느린 누적 (사용자: "뻔한 결과는 먼저 반영되고, 하루 1%씩 쌓이는 하락은 3배 감지에 안 걸린다"): 틀 S 에 `detect_day`(감지일 = 시장 확률 ≥ 70% 사흘 + 뉴스 묶음 집중) — 감지일부터 사건 전날까지 `선반영 중` 국면, 결과일 종가로 자를 다시 놓고 뒤를 잰다. 예상대로 쪽 갈래는 `priced`(이미 반영): 결과 뒤 기준 넘게 더 가면 틀림, 반대로 가거나 20거래일 기준 안이면 맞음. 느린 누적 = 틀 R 에 감지만 다른 것(10거래일 누적 2σ, 하루 기준 미달).
- 11-07 밤 "묘사가 아니라 경고" (사용자: 출발점은 중간선거처럼 "이렇게 되면 이런 일이 올 수 있으니 미리 생각해 두자"였다): ① 맨 위 `앞으로 올 수 있는 일` 카드(fc["prepare"]) = 다가오는 사건 × 지금 분위기 × 기록 → 조건부 경고 + 볼 것, 매수 · 매도 말 없음 ② 국면 문장 끝에 앞을 보는 꼬리("기준까지 1.2%p 남았습니다. 넘으면 ‘…’").
- 11-07 밤 지도 13-5 순서대로: ① `한국은 어떻게?` 카드(fc["korea"]: 미국 사건 → 한국 다음 날, 기록상 같은 방향 비율 · 크기 배수 — 2016~ 실측: 반도체 지수 큰 날 뒤 코스피 77% 같은 방향 · 0.26배, KODEX 반도체 75% · 0.38배, S&P 500 큰 날 뒤 코스피 82% · 0.28배) ② 판정 `보류`(fc["ambiguous"]: 결과가 두 조건 어느 쪽도 아님 — 채점 안 하고 움직임만) · `무효`(fc["void"]: 사건 취소 · 연기 · 자료 결함) ③ 번복(fc["reversal_of"]: 같은 사건 n회차, 성적표에서 묶음 한 건) · 연속 사건(묶음 전망: 조건 = "넷 중 셋 이상", 자 = 마지막 결과일 종가부터, 구성 사건은 따로 등록 안 함)
- 11-07 밤 재점검 14절 순서대로: ① 공개 등록 증명(proof_record → 공개 저장소 gh-pages proof/{slug}.json, 날짜 줄 `등록 증명` 링크 = 그 파일의 커밋 기록) ② 가벼운 페이지(날짜 줄 = 게시 · 사건 · 결과 셋 + 등록 증명, 현재 증시 · 한국 · 분위기는 `지금은?` 접기 하나) ④ 공개 = fc["publish"] 가 False 가 아닌 전망만(EH-001 전망 1 = 사후 등록 샘플 → 내부)
- 11-07 밤 틀림의 가치 (사용자: 인하는 됐는데 S&P 500 이 빠지면? 교정하나?): 교정 안 함(사전 등록). 고리 상태 `끊김`(대리 지표가 반대) + 틀린 뒤 `어디서 끊겼나` 카드(fc["broke"]: 끊긴 고리 · 미리 적어 둔 갈림점 중 일어난 쪽 · 등록 때 경고 · 다음 세부 전망)
- 11-07 밤 독자 문장 = 과한 수치만 말로 (사용자 정정: "전부 빼면 날마다 같은 문장이 반복된다"): **한 문장에 핵심 숫자 하나는 둔다**(시장 대비 %p · 기준까지 남은 값 · 불안 지수 · 되찾은 비율) + 세기 말을 곁들임. 말로만 쓰는 것 = 비율(n번 중 m번) · 확률(시장 예상 %) · 건수(뉴스 n건) · 배수 · 거래일 수
- 11-07 밤 `오늘 나온 것` 한 줄 (사용자: 모자란 일별 자료 추가): today_line(info) — 그날 경제지표 발표 · 10년 금리 · 신용 위험 웃돈 · 장단기 금리 차 · 뉴스 1위 묶음을 말로. 판정에는 안 쓰고 보이기만(고르기 편향 방지)
- 운영자 확인용(operator_box) = 목업에서만 그리는 회색 작은 글씨 상자 — 쓰인 요인(80개 중) · 이슈 코드 · 범위 비율 · 동행 · 겹침 · 규칙 버전. 발행 코드는 op 를 넘기지 않는다.
"""
import copy
import json
import os
import re as _re
import sys
from datetime import date, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
import design_kit as dk  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "daily-report"))
import cards as qc  # noqa: E402
import tech_signals as TS  # noqa: E402  종목 페이지 강조 카드 안 라벨 박스(BOX)

BLOG = "https://alpha-scope.blogspot.com/"
PROOF_REPO = "red6keep-droid/alphascope"   # 공개 저장소 — gh-pages/proof/{slug}.json 커밋 시각 = 등록 증명 (비공개 alphascope-state 는 독자가 못 연다)
LIST_SLUG = "forecast-list"
CARD_NAME = "증시 전망"
# 글 보기 고정 머리 줄 글자 (2026-11-09 사용자: 질문이 머리 줄 · 본문 맨 위에 두 번 나온다) — 테마가 본문 [data-head-title] 로 바꾼다. 블로그 글 제목(검색)은 그대로
HEAD_FORECAST, HEAD_LIST = "증시 전망 보기", "증시 전망 목록"
RELATED = dk.related_buttons(dk.report_links("us", "kr", "people"))   # 글 끝 `함께 보는 페이지` — 모든 리포트 공통 (2026-11-09 사용자)


# 질문 속 종목명 앞 로고 (2026-11-09 사용자: "개별 종목에 관한 전망이면 해당하는 종목명 앞에 로고") — 미국 · 한국 종목 후보의 한글 이름을 찾아
# 각 이름의 첫 자리 앞에 design_kit.ticker_logo(우리 gh-pages 사본). 로고 파일이 없는 한국 종목은 이름 첫 글자 배지(테마 krAvatar 와 같게)
_STOCK_NAMES = None


def _stock_names():
    global _STOCK_NAMES
    if _STOCK_NAMES is None:
        import importlib.util
        out = {}
        for rel in (("stock-radar", "universe.py"), ("kr-stocks", "universe_kr.py")):
            path = os.path.join(os.path.dirname(_HERE), *rel)
            try:
                spec = importlib.util.spec_from_file_location("_fc_" + rel[1][:-3], path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                for c in mod.CANDIDATES:
                    out.setdefault(c[1], c[0])
            except Exception:   # 후보 모듈을 못 읽으면 로고 없이 — 페이지는 그대로 나간다
                continue
        _STOCK_NAMES = out
    return _STOCK_NAMES


def _logo_for(sym, name, size):
    if sym.endswith((".KS", ".KQ")) and not dk._logo_files().get(sym.upper()):
        fs = max(8, int(size * 0.5))
        return (f'<span aria-hidden="true" style="display:inline-block;width:{size}px;height:{size}px;line-height:{size}px;border-radius:50%;'
                f'vertical-align:-4px;margin-right:6px;background:#E2E8F0;color:#334155;font-size:{fs}px;font-weight:700;text-align:center;">{dk.esc(name[:1])}</span>')
    return dk.ticker_logo(sym, size)


def with_logos(text, size=22):
    """이스케이프한 질문 글자 + 종목명마다(처음 한 번) 앞에 로고. 긴 이름부터 맞춘다 — `에코프로비엠` 안의 `에코프로` 에 두 번 붙지 않게"""
    names = _stock_names()
    html = dk.esc(text)
    if not names:
        return html
    pat = _re.compile("|".join(_re.escape(dk.esc(n)) for n in sorted(names, key=len, reverse=True)))
    seen = set()
    rev = {dk.esc(n): n for n in names}

    def rep(m):
        n = rev[m.group(0)]
        if n in seen:
            return m.group(0)
        seen.add(n)
        return '<span style="white-space:nowrap;">' + _logo_for(names[n], n, size) + m.group(0) + "</span>"
    return pat.sub(rep, html)


def is_stock_fc(fc):
    """개별 종목 전망인가 — 자동 등록이 종목 페이지 미국 종목에서 감지한 것(target=stock). 직접 쓴 전망 · 지수 · 업종은 아님"""
    return fc.get("target") == "stock"


def title_for(fc, size=22):
    """질문 글자 — 개별 종목 전망만 종목명 앞 로고, 거시 · 업종 전망은 글자만(앞에 저울 아이콘) (2026-11-11 사용자)"""
    return with_logos(fc["title"], size) if is_stock_fc(fc) else dk.esc(fc["title"])


def scale_icon(size=24):
    """증시 전망 저울 아이콘 — 청록 #0E7490 사각(P457) · 모서리 = 크기/4 · 그림 = 크기의 2/3 (상세 질문 줄 24 · 목록 줄 18)"""
    g = round(size * 2 / 3)
    return (f'<span style="display:inline-flex;align-items:center;justify-content:center;width:{size}px;height:{size}px;border-radius:{round(size / 4)}px;background:#0E7490;color:#fff;" aria-hidden="true">'
            f'<svg viewBox="0 0 16 16" width="{g}" height="{g}" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="display:block;">'
            '<path d="M8 2v12M4.5 14h7"/><path d="M2.5 5h11"/><path d="M4 5 2 9.5h4L4 5zM12 5l-2 4.5h4L12 5z"/></svg></span>')
# 상세 하단 버튼 · 머리 줄 화살표 = 전망 목록 (2026-11-09 사용자: 홈이 아니라 목록으로) — 테마가 data-nav="list" · data-title-back 을 읽는다

# ---------------------------------------------------------------- 용어 · 색
DIR_WORD = {1: "상승", -1: "하락"}
THEME = {1: "positive", -1: "negative", 0: "neutral"}
INK = {1: dk.UP, -1: dk.DOWN, 0: "#111"}
PHASE_INK = {"negative": dk.DOWN, "positive": dk.UP}
RESULT = {"hit": "맞음", "miss": "틀림", "neither": "제자리", "hold": "판정 보류", "void": "무효", "done": "결과"}   # done = 고르지 않는 전망(종목, fc["pick"] 없음)이 어느 쪽인지 난 날 — 맞음 · 틀림 없이 일어난 갈래 이름 (2026-11-11)
EARLY = 1 / 3            # 우세 = 금의 3분의 1
R_EARLY, R_HIT = 0.25, 0.5   # 반등 · 조정 우세 = 충격 폭 4분의 1 회복(반납), 반등 · 조정 = 절반
LEAN = "조짐이 보임"   # 타임라인 국면 `상승 조짐이 보임` · `조정 조짐이 보임` (2026-11-08 사용자, 옛 `○○ 조짐` → `○○ 우세`)
ANS_LEAN, ANS_HIT = "우세함", "실현됨"   # 갈래 카드 답 (2026-11-08 사용자, 옛 `조짐` · `일어남`)
REV = {-1: ("반등", "회복"), 1: ("조정", "반납")}   # 충격 방향 → (갈래 말, 동사)
SHOCK = {-1: "급락", 1: "급등"}


# ---------------------------------------------------------------- 독자 말 — 숫자 대신 세기 (2026-11-07 사용자: "몇 포인트 · 퍼센트 · 몇 건은 정말 좋지 않다, 문장으로")
def strength(v, L=3.0):
    """움직임 크기(기준 L 대비) → 거의 같게 · 조금 · 꽤 · 크게 · 아주 크게."""
    a = abs(v) / (L or 3.0)
    return "거의 같게" if a < 0.15 else "조금" if a < 0.4 else "꽤" if a < 0.8 else "크게" if a < 1.8 else "아주 크게"


def share_word(m, n):
    r = m / n if n else 0
    return "드물었습니다" if r < 0.25 else "적은 편이었습니다" if r < 0.45 else "반반이었습니다" if r <= 0.55 else "많은 편이었습니다" if r < 0.75 else "대부분이었습니다"


def near_word(left, L):
    a = left / (L or 3.0)
    return "거의 다 왔습니다" if a < 0.2 else "가까워졌습니다" if a < 0.5 else "아직 멉니다"


def prob_word(p):
    return "거의 확실하게" if p >= 85 else "대체로" if p >= 70 else "조금 더" if p >= 55 else "반반으로"


def vix_word(v):
    return "낮음" if v < 15 else "보통" if v < 20 else "높음" if v < 30 else "매우 높음"


def recov_word(r):
    return "조금" if r < 0.25 else "상당 부분" if r < 0.4 else "절반 가까이" if r < 0.5 else "절반 넘게" if r < 0.8 else "대부분"


_RE_NN = _re.compile(r"(\d+)\s*번 중\s*(\d+)\s*번")
_RE_PAREN = _re.compile(r"\s*\((?=[^()]*(?:%|배|번|σ|\bp\b))[^()]*\)")
_RE_PCT = _re.compile(r"[+\-−]?\d+(?:\.\d+)?\s*%p?")
_RE_X = _re.compile(r"(\d+(?:\.\d+)?)\s*배")


def wordify(text, L=3.0):
    """독자 문장에 남은 수치를 말로 — 'n번 중 m번' → 비율 말, 수치 괄호는 지움, 남은 %·%p 는 세기 말. 날짜(11.18) · 이름은 그대로. HTML 이 아닌 글에만."""
    t = _RE_NN.sub(lambda m: "기록상 " + share_word(int(m.group(2)), int(m.group(1))).replace("이었습니다", ""), text or "")
    for a_, b_ in (("60거래일", "석 달"), ("40거래일", "두 달"), ("20거래일", "한 달"), ("10거래일", "2주"), ("5거래일", "일주일")):
        t = t.replace(a_, b_)
    t = _re.sub(r"(\d+(?:\.\d+)?)\s*%로", lambda m: prob_word(float(m.group(1))), t)                                  # '87%로 봤다' → '거의 확실하게 봤다'
    t = _re.sub(r"(시장 예상[^·\d]*?)\s*(\d+(?:\.\d+)?)\s*%", lambda m: f"{m.group(1)} {prob_word(float(m.group(2)))}", t)   # '시장 예상 82%' → '시장 예상 대체로'
    t = _re.sub(r"(부정|긍정)\s*(?:보도\s*)?(\d+)\s*%", lambda m: f"{m.group(1)} 보도가 많음", t)                         # '부정 72%' → '부정 보도가 많음'
    t = _re.sub(r"누적\s*[+\-−]?\s*[\d.]+\s*%p?", "누적으로 꽤 내림", t)
    t = _RE_X.sub(lambda m: ("훨씬 작게" if float(m.group(1)) < 0.5 else "조금 작게" if float(m.group(1)) < 0.9 else "비슷하게" if float(m.group(1)) < 1.2 else "크게" if float(m.group(1)) < 2.5 else "아주 크게"), t)
    return t.replace("기록상 기록상", "기록상")
RULES = "EH-2026-11-10"   # 자 β 조정 · 비율 · 고정 시점 병기 — 뉴스 유무 10%p 가중 폐지 · `유력` = 기록이 반반과 분명히 다를 때만 (2026-11-10 사용자)
# 옛 EH-2026-11-07b 의 NEWS_TILT(뉴스 동반 급변은 지속 쪽 10%p, Chan 2003) 폐지 — 바깥 연구 하나를 우리 사건에 그대로 일반화한 가정이고,
# 큰 사건은 거의 다 뉴스가 있어 사실상 늘 지속 쪽으로 기울였다. 전망 2(11.05 반도체 급락)에서 기록상 반등 54% 를 지속 56% 로 뒤집어 틀림 (2026-11-10 사용자).


def beta(y, x, window=120):
    """시장 모형 β — 추정 창 = 사건 전 window 거래일(사건 전 5일 버퍼). y · x = 일별 수익률 목록(같은 길이, 끝이 사건 직전). 자료 부족하면 1.0."""
    n = min(len(y), len(x), window)
    if n < 30:
        return 1.0
    ys, xs = y[-n:], x[-n:]
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((a - mx) ** 2 for a in xs)
    return round(sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / sxx, 2) if sxx else 1.0


def abnormal(sub, mkt, base_i, b=1.0):
    """자 = β 조정 누적 초과수익(%p): 대상 누적수익 − β × 비교 계열 누적수익 (기준일 base_i 종가 = 0). None 은 그대로."""
    out = []
    for i in range(len(sub)):
        if sub[i] is None or mkt[i] is None:
            out.append(None)
        else:
            out.append(round((sub[i] / sub[base_i] - 1) * 100 - b * (mkt[i] / mkt[base_i] - 1) * 100, 2))
    return out


def pick_side(m, n):
    """틀 R 우리 전망 = 같은 종류 기록만. m = 기록상 반등(급등 뒤면 조정) 횟수, n = 전체.
    → (갈래 번호 1=반등·조정 / 2=지속, 그 갈래의 비율, 설명, 유력 여부).
    유력 = 95% 윌슨 구간이 50% 를 넘지 않을 때만 — 표본이 말하는 것보다 세게 말하지 않는다 (2026-11-10 사용자: 56% 에 `유력`)."""
    p = m / n
    side = 1 if p >= 0.5 else 2
    q = p if side == 1 else 1 - p
    z = 1.96
    lo = (q + z * z / (2 * n) - z * ((q * (1 - q) + z * z / (4 * n)) / n) ** 0.5) / (1 + z * z / n)
    strong = lo > 0.5
    why = f'기록상 {m}/{n} = {p * 100:.0f}% · 95% 구간 아래 끝 {lo * 100:.0f}% → {"유력" if strong else "반반(유력 없음)"}'
    return side, q, why, strong


def odds_meaningful(m, n):
    """기록이 한쪽으로 뚜렷한가 — 95% 윌슨 구간이 50% 를 벗어남(pick_side 의 `유력` 잣대) + 말이 `반반` 이 아님."""
    return bool(n) and pick_side(m, n)[3] and "반반" not in share_word(m, n)


def brier(p, hit):
    """브라이어 = (확률 − 결과)² — 0 이 완벽, 0.25 가 동전 던지기."""
    return round((p - (1.0 if hit else 0.0)) ** 2, 3)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def page_url(slug):
    return f"{BLOG}p/{slug}.html"


def md(iso):
    p = str(iso).split("-")
    return f"{p[1]}.{p[2]}" if len(p) == 3 else ".".join(p)


def fmt_v(v, unit="%p"):
    return "—" if v is None else (f"0.0{unit}" if abs(v) < 0.05 else f"{v:+.1f}{unit}")


def sec(title, html, tips):
    return dk.section(title, html, aside=dk.tips_right(tips))


_SIGNED = _re.compile(r"(?<![\w.])([+\-−]\d+(?:\.\d+)?%p?)")
_GAP = _re.compile(r"(\d+(?:\.\d+)?%p?)(\s*(?:더 빠졌|더 빠진|뒤처짐|더 올랐|더 오르|내렸|올랐))")


def tri_text(h):
    """부호 숫자 → 삼각형 (P423, 2026-11-08 사용자: 오른 것은 모두 ▲) — esc 된 글에 쓴다. 굵게 없이 증감 색만."""
    h = _SIGNED.sub(lambda m: f'<span style="color:{dk.UP if m.group(1)[0] == "+" else dk.DOWN};white-space:nowrap;">{"▲" if m.group(1)[0] == "+" else "▼"}&nbsp;{m.group(1)[1:]}</span>', h)
    # 부호 없는 차이 + 방향 말(`0.18%p 올랐음` · `1.8%p 더 빠졌`) — 뒤 말로 방향을 정해 같은 삼각형으로 (num_html 의 _GAP 과 같은 규칙)
    def gap(m):
        down = any(w in m.group(2) for w in ("빠", "뒤처", "내렸"))
        return f'<span style="color:{dk.DOWN if down else dk.UP};white-space:nowrap;">{"▼" if down else "▲"}&nbsp;{m.group(1)}</span>{m.group(2)}'
    return _GAP.sub(gap, h)


def num_html(text):
    """증감 숫자 = 증감 색 + 굵게 (가이드 3-3-1). 부호 있는 숫자는 부호로, 부호 없는 차이는 뒤 말로 방향을 정한다."""
    h = dk.esc(text)
    h = _SIGNED.sub(lambda m: f'<b style="color:{dk.UP if m.group(1)[0] == "+" else dk.DOWN};">{m.group(1)}</b>', h)
    return _GAP.sub(lambda m: f'<b style="color:{dk.DOWN if any(w in m.group(2) for w in ("빠", "뒤처", "내렸")) else dk.UP};">{m.group(1)}</b>{m.group(2)}', h)


# ---------------------------------------------------------------- 판정 엔진 — 숫자 → 국면 · 판정 (사람 손 없음, 기획 8-2)

def move_text(fc, v, ref=None):
    """자의 값 → 쉬운 문장. 상대 자(cmp 있음) = `반도체가 시장보다 3.4%p 더 빠졌습니다`, 절대 자 = `S&P 500 이 결정일 종가보다 4.1% 내렸습니다`."""
    unit, a = fc.get("unit", "%p"), abs(v)
    w = strength(v, fc.get("line", 3.0))   # 핵심 숫자 하나 + 세기 말 (2026-11-07 정정)
    if fc.get("cmp"):
        if w == "거의 같게":
            return f'{fc["subj_ga"]} {fc["cmp"].replace("보다", "와")} 거의 같게 움직였습니다({a:.1f}{unit})'
        return f'{fc["subj_ga"]} {fc["cmp"]} {a:.1f}{unit} 더 {"올랐" if v > 0 else "빠졌"}습니다, {w} {"오른" if v > 0 else "빠진"} 편입니다'
    if w == "거의 같게":
        return f'{fc["subj_ga"]} {ref or fc.get("ref") or fc["ruler_from"]} 거의 움직이지 않았습니다({a:.1f}{unit})'
    return f'{fc["subj_ga"]} {ref or fc.get("ref") or fc["ruler_from"]} {a:.1f}{unit} {"올랐" if v > 0 else "내렸"}습니다, {w} {"오른" if v > 0 else "내린"} 편입니다'


PRICED_WORDS = {"priced_in": "선반영 중"}


def today_line(info):
    """그날 나온 것 → 짧은 문장들 (숫자 X). info = {"releases": [이름], "rate10": 하루 변화(%p), "hy": 하루 변화(%p), "curve": 값, "news": (묶음 이름, 방향)}."""
    if not info:
        return ""
    out = []
    if info.get("releases"):
        out.append(" · ".join(info["releases"]) + "가 발표됐습니다.")
    r = info.get("rate10")
    if r is not None and abs(r) >= 0.04:
        out.append(f'금리는 {"조금 " if abs(r) < 0.08 else "크게 " if abs(r) >= 0.15 else ""}{"올랐습니다" if r > 0 else "내렸습니다"}.')
    h = info.get("hy")
    if h is not None and abs(h) >= 0.08:
        out.append("신용 위험 웃돈이 " + ("크게 벌어졌습니다. 회사채 시장이 겁을 먹은 모습입니다." if h >= 0.2 else "벌어졌습니다." if h > 0 else "좁혀졌습니다."))
    c = info.get("curve")
    if c is not None and c < 0:
        out.append("장단기 금리는 거꾸로입니다.")
    # 뉴스 1위 묶음 문장은 뺐다 — 같은 날 `관련 주식 정보` 근거 줄 · 그날 팝업과 겹친다 (2026-11-11 사용자). 시장 지표(발표 · 금리 · 신용 · 장단기)만
    return " ".join(out)


def _entry(day, key, label, d, text, rel, theme=None):
    return {"day": day, "key": key, "label": label, "dir": d, "theme": theme or "neutral", "text": text, "rel": rel}


def judge(fc, days, rel, cond=None, vix=None):
    """전망 하나의 날마다 기록 → state. days · rel = 자의 기준일부터의 값(None = 아직 없는 날, 그래프 빈 자리).
    틀 S(kind pre): 기준일 = 결과 직전 종가(fc["base_day"]) — 장 전 · 장중 발표(물가 08:30 · FOMC 14:00 · 밤사이 선거)는 발표 전날 종가, 장 마감 뒤 발표(실적)는 발표 날 종가.
    발표 날 반응까지 판정에 넣는다 (2026-11-08 검증: 반응은 발표 날 하루에 있고 다음 날부터는 평소와 같다 → 옛 '결과 날 종가부터' 는 사건 몫을 빼고 쟀다). base_day 없으면 옛 방식(결과 날 종가).
    cond = 일어난 조건 번호(None = 사건 전).
    틀 R(kind after): 기준일 = 충격 전날 종가, fc["gap"] = 등록 때 적은 충격 폭(고정). fc["pick"] = 우리 전망 갈래.
    창 = fc["end_day"](D+40, 2026-11-11 사용자 · 옛 등록은 D+60 그대로) 까지 금을 넘지 않으면 `제자리`. 판정한 날에서 기록을 멈춘다(다음 움직임은 다음 전망의 몫)."""
    L, unit, sc = fc["line"], fc.get("unit", "%p"), fc["scenarios"]
    reg = fc["registered"]
    log = [_entry(reg, "start", "지켜보는 중", 0, fc["start_text"], 0.0)]
    result, last_rel, recov, ev_off = None, None, None, 0.0
    if fc.get("void"):   # 사건 취소 · 연기 · 자료 결함 → 무효: 채점하지 않고 멈춘다. 새 날짜가 있으면 세부 전망으로 다시 적는다
        v = fc["void"]
        log.append(_entry(v["day"], "void", RESULT["void"], 0, v["text"], 0.0))
        return {"log": log, "result": {"word": RESULT["void"], "crossed": None, "day": v["day"]}, "cond": None, "rel": None, "days": days, "rel_series": rel, "fixed": {}, "vix": None}
    missing = []   # 자료가 빈 날 — 멈추지 않고 건너뛴다 (2026-11-07 사용자: 하루 누락이면 틀이 망가지나? → 전엔 여기서 break 했다). 빈 날은 '자료 대기' 로 기록하고 다음 날 채워지면 그날부터 이어 잰다
    bday = fc.get("base_day") or fc.get("event_day")
    early = fc["kind"] == "pre" and bday and fc.get("event_day") and bday < fc["event_day"]   # 결과 직전 종가가 발표 전날 — 발표 날도 판정하는 날
    for i, day in enumerate(days):
        r = rel[i]
        if r is None:
            if any(v is not None for v in rel[i + 1:]):   # 중간 구멍 — 건너뛰고 적어 둔다
                missing.append(day)
            else:   # 뒤가 전부 빈 자리(아직 안 온 날) — 끝
                break
            continue
        if day <= reg and fc["kind"] == "after":
            continue
        if fc["kind"] == "pre":
            det = fc.get("detect_day")
            if det and det <= day < fc["event_day"]:   # 선반영 구간 — 감지일 종가가 0
                last_rel = r
                mp = fc.get("market_prob", {}).get("probs", [None])[0]
                d0 = 1 if r > 0 else (-1 if r < 0 else 0)
                tag = f'시장이 {prob_word(mp)} 본 ‘{fc["outcomes"][0]}’ 쪽이 먼저 반영되는 중입니다.' if mp else "결과 전에 먼저 움직이는 중입니다."
                log.append(_entry(day, "priced_in", "선반영 중", d0, f"{move_text(fc, r, ref=f'감지일({md(det)}) 종가보다')}. {tag}", r))
                if day == bday:
                    ev_off = r   # 결과 직전 종가(발표 전날)로 자를 다시 놓는다
                continue
            if det and day == bday:
                ev_off = r   # 결과 직전 종가로 자를 다시 놓는다
            if day < fc["event_day"] or cond is None:
                continue
            r = r - ev_off
            last_rel = r
            if fc.get("ambiguous"):   # 결과가 두 조건 어느 쪽도 아님 → 판정 보류: 채점 안 하고 움직임만 적는다
                am = fc["ambiguous"]
                if day == fc["event_day"]:
                    log.append(_entry(day, "hold", RESULT["hold"], 0, f'결과가 나왔습니다 : {am["outcome"]}. 미리 적은 두 조건({" / ".join(fc["outcomes"])}) 어느 쪽도 아니라 이 전망은 채점하지 않고 움직임만 적습니다. {am.get("why", "")}', r, "neutral"))
                    result = {"word": RESULT["hold"], "crossed": None, "day": day}
                else:
                    log.append(_entry(day, "hold", RESULT["hold"], 0, f"{move_text(fc, r)}. 보류한 전망이라 맞음 · 틀림은 세지 않습니다.", r, "neutral"))
                if fc.get("end_day") and day >= fc["end_day"]:
                    break
                continue
            if day == fc["event_day"] and not early:
                mp = fc.get("market_prob")
                sur = ""
                if mp:
                    pc = mp["probs"][cond - 1]
                    sur = f' 시장이 {prob_word(pc)} 본 쪽이라 예상대로입니다.' if pc >= 50 else f' 시장은 {prob_word(100 - pc)} 반대쪽을 봤던 터라 예상 밖입니다.'
                log.append(_entry(day, "base", "지켜보는 중", 0, f'결과가 나왔습니다 : {fc["outcomes"][cond - 1]}.{sur} 이날 종가부터 잽니다.', r))
                continue
            a = sc[cond - 1]
            dd = a["dir"]
            x = dd * r
            mv = move_text(fc, r)
            if a.get("priced"):   # 이미 반영 갈래 — 더 가면 틀림, 반대로 가거나 20거래일 기준 안이면 맞음
                if x >= L:
                    result = {"word": RESULT["miss"], "crossed": None, "day": day}
                    log.append(_entry(day, "miss", RESULT["miss"], dd, f'{mv}. 결과 뒤에도 기준({L:g}{unit}) 넘게 더 가, ‘{a["name"]}’이 틀렸습니다 — 먼저 반영된 것이 다가 아니었습니다.', r, THEME[dd]))
                    break
                if -x >= L:
                    result = {"word": RESULT["hit"], "crossed": cond, "day": day}
                    log.append(_entry(day, "hit", RESULT["hit"], -dd, f'{mv}. 결과가 나오자 먼저 움직인 쪽과 반대로 가 ‘{a["name"]}’이 맞았습니다 — 먼저 오른 만큼 조정을 받은 모양입니다.', r, THEME[-dd]))
                    break
                if fc.get("priced_end") and day >= fc["priced_end"]:
                    result = {"word": RESULT["hit"], "crossed": cond, "day": day}
                    log.append(_entry(day, "hit", RESULT["hit"], 0, f'결과 뒤 한 달 가까이 기준 안에 머물렀습니다. {mv}. ‘{a["name"]}’이 맞았습니다 — 결과 전에 이미 반영된 대로입니다.', r, "neutral"))
                    break
                log.append(_entry(day, "watch", "지켜보는 중", 0, f"{mv}. 아직 기준 안입니다 — 먼저 반영된 대로 가는 중입니다.", r))
                continue
            if x >= L:
                result = {"word": RESULT["hit"], "crossed": cond, "day": day}
                log.append(_entry(day, "hit", RESULT["hit"], dd, f'{mv}. 기준({L:g}{unit})을 넘어 미리 적은 ‘{a["name"]}’이 맞았습니다.', r, THEME[dd]))
                if fc.get("follow"):   # 맞음 줄 국면 옆 `(세부 전망으로 이어감 ›)` 링크 — 본문 꼬리 문장 대신 (P453, 2026-11-08 사용자)
                    log[-1]["follow"] = fc["follow"]
                break
            if -x >= L:
                result = {"word": RESULT["miss"], "crossed": None, "day": day}
                log.append(_entry(day, "miss", RESULT["miss"], -dd, f'{mv}. 미리 적은 ‘{a["name"]}’과 반대로 기준({L:g}{unit})을 넘어 틀렸습니다.', r, THEME[-dd]))
                if fc.get("follow"):   # 틀림 줄에도 `(세부 전망으로 이어감 ›)` (P464) — 반대로 크게 간 움직임을 세부 전망이 이어받을 때
                    log[-1]["follow"] = fc["follow"]
                break
            ahead = f' 기준까지 {L - abs(x):.1f}{unit} 남았습니다. 넘으면 ‘{a["name"] if x >= 0 else fc["subject"] + " " + DIR_WORD[-dd]}’입니다.'   # 앞을 보는 꼬리 (묘사 X)
            if x >= L * EARLY:
                log.append(_entry(day, "lean", f'{a["name"]} {LEAN}', dd, f'{mv}. ‘{a["name"]}’ 쪽으로 기울고 있습니다.{ahead}', r))
            elif -x >= L * EARLY:
                nm = f'{fc["subject"]} {DIR_WORD[-dd]}'
                log.append(_entry(day, "lean_x", f"{nm} {LEAN}", -dd, f"{mv}. 미리 적은 것과 반대인 ‘{nm}’ 쪽으로 기울고 있습니다.{ahead}", r))
            else:
                log.append(_entry(day, "watch", "지켜보는 중", 0, f"{mv}. 아직 어느 쪽으로도 기울지 않았습니다.{ahead}", r))
        else:
            gap = fc["gap"]
            s = 1 if gap > 0 else -1
            recov = 1 - r / gap
            ext = s * (r - gap)
            last_rel = r
            b1, b2 = sc[0], sc[1]
            pick = sc[fc["pick"] - 1]["name"] if fc.get("pick") else None
            crossed = 1 if recov >= R_HIT else (2 if ext >= L else None)
            if crossed and not pick:   # 종목 전망 = 우리가 고르지 않는다 — 일어난 쪽만 적고 성적표에 넣지 않는다 (2026-11-11 사용자, 매수 추천 금지)
                word = REV[s][0] if crossed == 1 else f"{DIR_WORD[s]} 지속"
                result = {"word": word, "crossed": crossed, "day": day, "unscored": True}
                what = (f'{SHOCK[s]} 폭의 {recov * 100:.0f}%({recov_word(recov)})를 {REV[s][1]}해 ‘{b1["name"]}’이 일어났습니다' if crossed == 1
                        else f'{SHOCK[s]} 뒤 {ext:.1f}{unit} 더 {"올라" if s > 0 else "빠져"} ‘{b2["name"]}’이 일어났습니다')
                dd = sc[crossed - 1]["dir"]
                log.append(_entry(day, "done", word, dd, f'{what}.', r, THEME[dd]))
                break
            if crossed:
                ok = crossed == fc["pick"]
                result = {"word": RESULT["hit" if ok else "miss"], "crossed": crossed, "day": day}
                what = (f'{SHOCK[s]} 폭의 {recov * 100:.0f}%({recov_word(recov)})를 {REV[s][1]}해 ‘{b1["name"]}’이 일어났습니다' if crossed == 1
                        else f'{SHOCK[s]} 뒤 {ext:.1f}{unit} 더 {"올라" if s > 0 else "빠져"} ‘{b2["name"]}’이 일어났습니다')
                dd = sc[crossed - 1]["dir"]
                log.append(_entry(day, "hit" if ok else "miss", result["word"], dd,
                                  f'{what}. 우리가 고른 ‘{pick}’이 {"맞았" if ok else "틀렸"}습니다.', r, THEME[dd]))
                break
            ahead = f' ‘{b1["name"]}’까지 {max(0.0, (R_HIT - recov) * abs(gap)):.1f}{unit} 더 {REV[s][1]}하면, ‘{b2["name"]}’까지 {max(0.0, L - ext):.1f}{unit} 더 {"오르면" if s > 0 else "빠지면"}입니다.'
            if recov >= R_EARLY:
                log.append(_entry(day, "lean", f'{b1["name"]} {LEAN}', b1["dir"], f'{SHOCK[s]} 폭의 {recov * 100:.0f}%({recov_word(recov)})를 {REV[s][1]}했습니다. ‘{b1["name"]}’ 쪽으로 기울고 있습니다.{ahead}', r))
            elif ext >= L * EARLY:
                log.append(_entry(day, "lean_x", f'{b2["name"]} {LEAN}', b2["dir"], f'{SHOCK[s]} 뒤 {ext:.1f}{unit} 더 {"올랐" if s > 0 else "빠졌"}습니다. ‘{b2["name"]}’ 쪽으로 기울고 있습니다.{ahead}', r))
            else:
                log.append(_entry(day, "watch", "지켜보는 중", 0, f"{move_text(fc, r)}. {SHOCK[s]} 뒤 아직 어느 쪽으로도 기울지 않았습니다.{ahead}", r))
        if fc.get("end_day") and day >= fc["end_day"] and not result:
            result = {"word": RESULT["neither"], "crossed": None, "day": day}
            log[-1] = _entry(day, "neither", RESULT["neither"], 0, f'정해 둔 기간({"두 달" if fc.get("window", 60) <= 40 else "석 달"} 가까이) 안에 기준을 넘지 않았습니다. {move_text(fc, r)}. 제자리입니다.', r)
            break
    if fc["kind"] == "after":   # 틀 R 타임라인 숫자 = 충격 날 종가부터 (2026-11-08 사용자: 조정 조짐인데 ▲ — 기준일(충격 전날)부터 재면 반납 중에도 ▲ 로 보였다)
        for e in log:
            if e["key"] != "start" and e.get("rel") is not None:
                e["shown"] = e["rel"] - fc["gap"]
    # 고정 시점 판정(내부) — 첫 넘김 판정은 먼저 넘은 쪽을 보상하므로 D+5 · 20 · 60 그날 값도 적는다 (개선 ③)
    start = fc["event_day"] if fc["kind"] == "pre" else fc["registered"]
    idx = [i for i, d in enumerate(days) if d >= start and rel[i] is not None]
    fixed = {}
    for k in (5, 20, 60):
        if len(idx) > k:
            v = rel[idx[k]] - (ev_off if fc["kind"] == "pre" else 0.0)
            if fc["kind"] == "pre":
                side = f'{fc["subject"]} {DIR_WORD[1 if v > 0 else -1]}' if abs(v) >= L else "기준 안"
            else:
                g = fc["gap"]; s_ = 1 if g > 0 else -1
                side = sc[0]["name"] if (1 - v / g) >= R_HIT else (sc[1]["name"] if s_ * (v - g) >= L else "기준 안")
            fixed[k] = (days[idx[k]], v, side)
    if missing and not result:   # 독자에게도 한 줄: 어느 날 자료가 비었는지 (기록은 멈추지 않는다)
        log.append(_entry(days[max(i for i, v in enumerate(rel) if v is not None)], "gap", log[-1]["label"], log[-1]["dir"], f'{" · ".join(md(d) for d in missing[-3:])} 시세 자료가 늦게 와서 그날은 비워 두었습니다. 채워지면 그날 값으로 다시 적습니다.', last_rel, log[-1]["theme"]))
    if early and cond:   # 발표 날 줄 앞에 결과 한 줄 — 따로 `지켜보는 중` 줄을 두지 않는다
        mp = fc.get("market_prob")
        sur = ""
        if mp:
            pc = mp["probs"][cond - 1]
            sur = f' 시장이 {prob_word(pc)} 본 쪽이라 예상대로입니다.' if pc >= 50 else f' 시장은 {prob_word(100 - pc)} 반대쪽을 봤던 터라 예상 밖입니다.'
        for e in log:
            if e["day"] == fc["event_day"] and e["key"] not in ("start", "priced_in"):
                e["text"] = f'결과가 나왔습니다 : {fc["outcomes"][cond - 1]}.{sur} 결과 직전 종가({md(bday)})부터 잽니다. ' + e["text"]
                break
    st = {"log": log, "result": result, "cond": cond, "rel": last_rel, "days": days, "rel_series": rel, "fixed": fixed, "missing": missing,
          "vix": vix[[j for j, v in enumerate(rel) if v is not None][-1]] if vix and any(v is not None for v in rel) else None}   # 값이 하나도 없는 날(기준일 시세 없음)에 멈추던 것 (2026-11-11)
    if fc["kind"] == "after" and last_rel is not None:
        st["recovery"] = max(0.0, (1 - last_rel / fc["gap"]) * 100)
    return st


# ---------------------------------------------------------------- 전망 페이지 — 공용 카드 유형만 (가이드라인 2-1)

CHAIN = {"done": ("확인", "down"), "wait": ("대기", "flat"), "no": ("해당 없음", "flat"), "broken": ("끊김", "caution")}   # 끊김 = 조건은 일어났는데 그 고리의 대리 지표가 반대로 감 (2026-11-07: 틀린 전망의 가치 = 어디서 끊겼나)   # 대기 = 회색, 실제 결과 = 노랑 (P319)
END_PULL = 21   # 강조 카드가 그래프로 끝날 때 아래 여백 당기기 (P140)


NOT_HAPPENED = "해당 없음"   # 갈래 답 — 옛 `일어나지 않음` (P415, 2026-11-08 사용자 "더 짧은 말" → Claude 결정: 고리 줄 라벨과 같은 말)
DIM_TEXT, DIM_SUB = dk.MUTED, "#BDBDBD"   # 해당 없는 갈래 = 조건 글씨(#999) 톤, 작은 글씨는 더 흐리게 (P420)
DIM_BOX = ("#F3F5F8", "#E9ECF0", DIM_TEXT)   # 흐린 라벨 — 바탕 · 테두리는 중립 라벨(#E8EDF3 · #D6DEE8)보다 연하게, 글자 = 조건 글씨와 같은 #999 (P416 · P420)


def dim_box(text):
    bg, bd, fg = DIM_BOX
    fb, fbd, ffg = TS.BOX["flat"]
    return (TS.box("flat", text, dk.esc, sym=False, fit=True)
            .replace(f"background:{fb};", f"background:{bg};", 1).replace(f"border:1px solid {fbd};", f"border:1px solid {bd};", 1).replace(f"color:{ffg};", f"color:{fg};", 1))


def _dim(html):
    """해당 없는 갈래 카드 안 글씨 전부 흐리게 (P420, 2026-11-08 사용자: 이름표 · 답 · 펼친 문장까지 조건 글씨 톤으로) — 증감 색 숫자도 회색."""
    for c in ("#111", "#111111", "#333", "#333333", dk.UP, dk.DOWN, INK.get(1, ""), INK.get(-1, "")):
        if c:
            html = html.replace(f"color:{c};", f"color:{DIM_TEXT};")
    for c in (qc.NOTE, dk.SUB):
        html = html.replace(f"color:{c};", f"color:{DIM_SUB};")
    return html


def branch_view(fc, st, sc):
    """갈래 카드 하나의 모양 — 답(그 갈래에 일어난 사실) · 테마 · 라벨 · 활성 · 펼침."""
    res, log = st.get("result"), st.get("log") or []
    key = log[-1]["key"] if log else "start"
    if fc["kind"] == "pre":
        cond = st.get("cond")
        if cond is None:
            return {"answer": "", "theme": "neutral", "label": None, "active": True, "opened": False}   # 결과 전 = 전망 문장 + 접기 버튼만 (2026-11-07 사용자)
        if sc["no"] != cond:
            return {"answer": NOT_HAPPENED, "theme": "neutral", "label": None, "active": False, "opened": False}
        label, toward = None, key == "lean"   # `실제 결과` 라벨 삭제 (P414)
    else:
        label = "유력" if sc["no"] == fc.get("pick") and fc.get("pick_strong", True) else None   # pick_strong 없음 = 옛 규칙으로 등록된 전망(등록 그대로) · False = 기록이 반반이라 고르기만 하고 `유력` 은 안 붙임 (2026-11-10)   # 옛 `우리 전망` — 카드 이름표 `전망 A · B` 와 겹쳐 헷갈림 (2026-11-08 사용자)
        toward = (key == "lean" and sc["no"] == 1) or (key == "lean_x" and sc["no"] == 2)
    if res:
        if res.get("crossed") == sc["no"]:
            return {"answer": ANS_HIT, "theme": THEME[sc["dir"]], "label": label, "active": True, "opened": True}   # 옛 `일어남` (2026-11-08 사용자: 실현)
        if fc["kind"] == "pre":   # 실제로 온 조건인데 그 갈래가 안 맞음 — `실제 결과` 라벨이 없어졌으니(P414) 흐리지 않고 판정 한 마디를 답으로
            return {"answer": res.get("word") or RESULT["miss"], "theme": "neutral", "label": None, "active": True, "opened": True}
        return {"answer": NOT_HAPPENED, "theme": "neutral", "label": label, "active": bool(label), "opened": bool(label)}
    return {"answer": ANS_LEAN if toward else "", "theme": "uncertain" if toward else "neutral", "label": label, "active": True,   # 우세 = 보라 강조 카드 (P421, 2026-11-08 사용자)
            "opened": fc["kind"] == "pre" or sc["no"] == fc.get("pick") or not fc.get("pick")}


NUM_KO = ["하나", "둘", "셋", "넷", "다섯", "여섯"]
NEG_COND = [("크게 넘으면", "크게 넘지 못하면"), ("넘으면", "넘지 못하면"), ("웃돌면", "웃돌지 못하면"), ("높으면", "낮으면"), ("낮으면", "높으면"),
            ("오르면", "오르지 못하면"), ("인하 시", "동결 · 인상 시")]
NEG_OUT = [("크게 넘음", "크게 넘지 못함"), ("넘음", "넘지 못함"), ("높음", "낮음"), ("낮음", "높음"), ("금리 인하", "동결 · 인상")]


def _neg(text, table):
    """짝 조건의 반대 문장 — 정확한 여집합(‘크게 넘음’ 의 반대 = ‘크게 넘지 못함’, 조금 넘은 경우 포함). `n 이상이` → `n−1 이하만`."""
    m = _re.search(r"(하나|둘|셋|넷|다섯|여섯) 이상(이)? ", text)
    if m and NUM_KO.index(m.group(1)) > 0:
        return text[:m.start()] + f"{NUM_KO[NUM_KO.index(m.group(1)) - 1]} 이하만 " + text[m.end():]
    for a, b in table:
        if text.endswith(a):
            return text[:-len(a)] + b
    return None


def _fill_other(fc):
    """`그 밖이면` · `그 밖` 을 짝의 반대 문장으로 (P412, 2026-11-08 사용자: B 조건도 혼자 읽혀야 한다, 사람이 쓰지 않고 자동). 화면에만 — 등록 자료는 그대로."""
    scs = fc["scenarios"]
    if len(scs) < 2:
        return
    for i, sc in enumerate(scs[:2]):
        other = scs[1 - i]
        if sc["cond"].startswith("그 밖"):
            tail = _re.search(r"\s*\(.*\)\s*$", sc["cond"])
            neg = _neg(_re.sub(r"\s*\(.*\)\s*$", "", other["cond"]), NEG_COND)
            if neg:
                sc["cond"] = neg + (tail.group(0) if tail else "")
        if sc.get("chain") and sc["chain"][0]["step"] == "그 밖" and other.get("chain"):
            sc["chain"][0]["step"] = _neg(other["chain"][0]["step"], NEG_OUT) or "그 밖"
    outs = fc.get("outcomes")
    if outs and len(outs) == 2:
        fc["outcomes"] = [o if o != "그 밖" else (_neg(outs[1 - k], NEG_OUT) or o) for k, o in enumerate(outs)]


TAG_DOWN = ("낮", "내리", "내려", "인하", "하락", "못 넘", "밑돌", "감산", "줄이", "조정")   # 조정 = 급등 뒤 내려오는 갈래 → 파랑 · 전망 B (2026-11-08 사용자: A · B 는 늘 빨강 하나 · 파랑 하나, 상승 = A)   # 감산 · 증산 = OPEC+ 회의(B 업종 기본 사례, P460)   # 조건 글자가 '아래로' 인 갈래
TAG_UP = ("높", "오르", "올라", "인상", "상승", "넘", "웃돌", "반등", "증산", "늘리")


def _tag_kind(sc):
    """`전망A` · `전망B` 순서 · 이름표 색 · 실현됨 카드 색 = 그 갈래가 맞으면 가격이 가는 방향(sc["dir"]) (2026-11-08 사용자:
    가격을 올릴 전망 = 전망A · 빨강, 내릴 전망 = 전망B · 파랑 — 옛 P408 조건 글자 방향은 `감산`(에너지 ▲)을 파랑 · B 로 두는 등 어긋났다).
    dir 이 0 인 갈래만 옛 규칙(조건 글자)으로 정한다."""
    if sc.get("dir", 0):
        return "up" if sc["dir"] > 0 else "down"
    c = sc["cond"]
    if "지속" in c:
        return "down" if sc["dir"] < 0 else "up"
    if any(w in c for w in ("못하면", "못 넘", "이하만", "미치지")):   # 반대 문장(P412) — `크게 넘지 못하면` · `둘 이하만` = 낮은 쪽
        return "down"
    hits = [(c.find(w), "down") for w in TAG_DOWN if w in c] + [(c.find(w), "up") for w in TAG_UP if w in c]
    hits = [h for h in hits if not (h[1] == "up" and "못 넘" in c and c.find("못 넘") + 2 == h[0])]
    if hits:
        return min(hits)[1]
    return "up" if sc.get("dir", 0) > 0 else "down" if sc.get("dir", 0) < 0 else "flat"   # 조건 글에 방향 말이 없으면 주가 방향으로 — 회색 이름표 대신 빨강 · 파랑 (2026-11-08 사용자)


def _small_row(html, name, text, theme):
    """`‘○○’ 이 되는 기준` 줄 = 작은 회색 한 덩어리 (P430 · P432, 2026-11-08 사용자: 전부 작은 회색, 대상 이름 두 번 쓰지 않기).
    질문 카드가 만든 그 줄(li)을 통째로 바꾼다 — 구분선 색 · 위아래 10 은 다른 근거 줄과 같게."""
    i = html.find(dk.esc(name))
    j = html.rfind("<li ", 0, i)
    k = html.find("</li>", i)
    if i < 0 or j < 0 or k < 0:
        return html
    if text is None:   # 줄 자체를 뺀다 (P487)
        return html[:j] + html[k + len("</li>"):]
    bd = qc.CARD_DIR.get(theme, qc.CARD_DIR["neutral"])[1]
    line = dk.darken(dk.lighten(dk.lighten(bd), 0.3), 0.02)   # 질문 카드 줄 구분선과 같은 셈
    li = (f'<li style="list-style:none;margin:0;padding:10px 0;border-top:1px solid {line};font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{qc.NOTE};word-break:keep-all;">'
          f'{dk.esc(text)}</li>')
    return html[:j] + li + html[k + len("</li>"):]


def _crit_text(sc, Lw):
    """기준 한 줄 — `‘S&P 500 상승’ 기준 : 12.09 종가보다 4% 넘게 오름`. 문장 맨 앞 대상 이름(갈래 이름의 앞부분)은 겹쳐 뺀다."""
    win = wordify(sc["win"], Lw)
    subj = _re.sub(r"\s*(상승 지속|하락 지속|이미 반영|상승|하락|반등|조정)$", "", sc["name"])
    win = _re.sub(rf"(^|\s){_re.escape(subj)}\s*(이|가|은|는)\s+", r"\1", win)   # 앞 · 가운데 어디든 `S&P 500 이` 는 갈래 이름과 겹친다
    win = _re.sub(rf"^{_re.escape(subj)}\s+", "", win)
    for a, b in (("오른다", "오름"), ("내린다", "내림"), ("빠진다", "빠짐"), ("회복한다", "회복"), ("반납한다", "반납"), ("받는다", "받음")):   # 한 줄 요약이라 명사형 끝
        win = win.replace(a, b)
    sw = side_word(sc)
    return f'{sw} 기준 : {win}' if sw else f'‘{sc["name"]}’ 기준 : {win}'   # 자동 등록은 `반등 기준` — 대상 이름 반복 없이 (2026-11-11 사용자)


def news_pill(text, colors, inline=True):
    """뉴스 기사 줄 라벨(dk.pill) 크기 — 글자 14 · 보통 굵기 · 안쪽 3/5/2 · 행간 1 · 모서리 4. 색 = (바탕, 테두리, 글자)
    (2026-11-08 사용자: 뉴스 기사 긍정 · 부정 라벨 크기). inline = 문장 끝에 5 띄워 붙임(한글 가운데 보정 PILL_MID), False = flex 줄 안(gap 이 띄우고 가운데 정렬)."""
    bg, bd, fg = colors
    pos = f"margin:0 0 0 {dk.PILL_GAP}px;{dk.PILL_MID}vertical-align:middle;" if inline else "margin:0;flex:none;"
    return (f'<span style="display:inline-block;background:{bg};color:{fg};border:1px solid {bd};border-radius:4px;padding:3px 5px 2px;{pos}'
            f'font-size:{dk.PILL_SIZE};font-weight:400;line-height:1;white-space:nowrap;">{dk.esc(text)}</span>')


def overlap_pill():
    """`겹침` 라벨 = 뉴스 기사 줄 라벨 크기 · 보라(VIOLET_BOX, 2026-11-08 사용자: 겹침 같은 관계 라벨 = 보라) · flex 줄 안 세로 가운데 (2026-11-08 사용자 — 옛 P468 회색 상자)."""
    return news_pill("겹침", VIOLET_BOX, inline=False)   # 보라 (2026-11-08 사용자 — 옛 노랑)


def violet_word(text, color=None):
    """보라 굵은 글씨 꼬리 — 상자 없이, 앞 글자와 5 띄움 · 글자는 앞 글보다 1px 작게 (2026-11-08 사용자: 질문 끝 `세부전망` · 조건 끝 `- 유력` 을 라벨 대신 글자로)."""
    return f'<span style="margin-left:{dk.PILL_GAP}px;font-size:calc(1em - 1px);color:{color or dk.VIOLET};font-weight:700;white-space:nowrap;">{dk.esc(text)}</span>'


def _tag_title(html, cond, box, stack=False, tail=""):
    """강조 카드 첫 줄 맨 앞 라벨 — 라벨 칸(flex:none) + 제목 칸(min-width 0). 제목이 두 줄이 되면 둘째 줄은 라벨 아래로 들어가지 않고 제목 첫 글자 선에서 시작 (P434, 2026-11-08 사용자, 가이드라인 2-7).
    질문 카드가 마지막 낱말을 nowrap 으로 감싸 문장 통째로는 못 찾으니 첫 낱말 앞에 칸을 열고, 제목 span 이 닫히는 자리(답 칸 바로 앞)에서 닫는다."""
    first = ">" + dk.esc(cond).split(" ")[0]
    i = html.find(first)
    ans = html.find('<span style="flex:none;white-space:nowrap;font-weight:', i)
    if i < 0 or ans < 0:
        return html
    close = html.rfind("</span>", i, ans)   # 제목 span 의 닫는 태그
    lh = int(dk.LH_EMPH_Q.rstrip("px"))
    top = 0 if stack else (lh - 24) // 2 - 1   # 라벨 상자를 제목 첫 줄 가운데에 — 잉크 실측(4배 캡처)에서 라벨이 글보다 1px 아래라 1 올림 (P486, 2026-11-11 사용자)
    # stack = 시장예상 · 유력 라벨이 붙으면 라벨 줄 아래로 조건 글을 내린다 (P474, 2026-11-08 사용자)
    flex = "flex-direction:column;align-items:flex-start;gap:6px;" if stack else "align-items:flex-start;gap:8px;"   # 이름표 ↔ 조건 글 8 (2026-11-08 사용자: 3 은 너무 붙어 이전 여백으로)
    cls = ' class="fc-th-wrap fc-th-stack"' if stack else ' class="fc-th-wrap"'
    opener = (f'><span{cls} style="display:flex;{flex}"><span class="fc-th-lab" style="flex:none;display:flex;margin-top:{top}px;">{box}</span>'
              f'<span style="flex:1 1 auto;min-width:0;word-break:keep-all;">')
    body = html[i + 1:close]
    if tail:   # 문장 끝 라벨 — 마지막 낱말을 감싼 nowrap 칸 안에 넣어 낱말과 같이 줄을 바꾼다
        body = body[:-7] + tail + "</span>" if body.endswith("</span>") else body + tail
    return html[:i] + opener + body + "</span></span>" + html[close:]


# ── 갈래별 근거 (2026-11-11 사용자: "전망 카드에 각각 이유를 · 두 줄 정도 넣고 더보기를 하면 팝업창으로") ──
# 재료 = 등록 때 고정한 fc["reasons"] 의 good · bad · open (forecast_register.side_news — 기사 요약 줄 태그). 오름 쪽 갈래(dir +1) = 좋은 소식, 내림 쪽 = 나쁜 소식.
# 자리 = 갈래 카드 펼침 안 맨 아래(같은 날 사용자: "근거는 전망 펼침 안에"). 머리 `근거 n건` + 기사 사실 두 줄(애널리스트 집계 줄은 팝업에만) + 외곽선 `더보기` 버튼.
# 방향이 안 정해진 일(open)은 두 카드 위 공통 줄 — 버리지 않는다. 논의 중인 줄은 `논의중` 라벨(띄어쓰기 없음 · 글과 세로 가운데)만, 순서는 낮추지 않는다.
# 팝업 = 테마 뉴스 팝업([data-news-pop] → [data-news-pop-body]) 그대로. 끝 안내 = 느낌표 아이콘 + 가장 작은 글씨 13/19.
WHY_SHOWN = 2
WHY_WORD = "관련 주식 정보"   # 옛 `근거` (P488, 2026-11-11 사용자)
WHY_HEAD_FS, WHY_HEAD_LH = 17, 28   # 갈래 카드 `근거` 제목 = 고리 줄 이름과 같은 17 (2026-11-11 사용자)
CHAIN_FS = 17   # 갈래 카드 고리 줄 이름(`급락 폭의 4분의 1 회복`) — 카드 줄 18 에서 한 단계 작게 (2026-11-11 사용자)
WHY_FS, WHY_LH = 16, 26
SIG_NAME = "알파스코프 신호"   # 독자 문장에서 `우리 신호` 대신 (2026-11-11 사용자: 독자는 `우리`가 누군지 모른다)
WHY_NOTE = "전망에 따른 주식 정보를 모은 것입니다. 판단하거나 어느 쪽이 맞을지 고른 것은 아닙니다."   # P498, 2026-11-11 사용자 문구
EXCL_ICON = ('<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true" style="flex:none;display:block;" fill="none" stroke="currentColor" stroke-width="1.6">'
             '<circle cx="8" cy="8" r="6.5"/><path d="M8 4.6v4.4" stroke-linecap="round"/><circle cx="8" cy="11.2" r=".9" fill="currentColor" stroke="none"/></svg>')   # 느낌표 = INFO_ICON(i) 뒤집은 모양


def _talk_mark():
    """`논의중` 라벨 = 공용 외곽선 라벨(dk.pill 회색) — 글과 세로 가운데 · 글자와 5 (디자인 가이드 8절)."""
    return dk.pill("논의중", "neutral")


WHY_HZ = (("단기", "며칠"), ("중기", "한 달~분기"))   # 우리 신호 기간 제목 (signal_groups.HORIZONS, 2026-11-11 사용자: "기간은 단기 · 중기로 타이틀")
CAL_ICON = ('<svg viewBox="0 0 22 22" width="22" height="22" fill="none" aria-hidden="true" style="flex:none;margin-right:6px;position:relative;top:6px;">'
            '<circle cx="11" cy="11" r="11" fill="#E5E7EB"/><g transform="translate(2 2)" stroke="#4B5563" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">'
            '<rect x="5" y="5.8" width="8" height="7" rx="1"/><path d="M5 8.4h8M7 4.6v2M11 4.6v2"/></g></svg>')   # 팝업 `단기` · `중기` 앞 = 회색 면 원 안 달력 (P505, 2026-11-11 사용자: 외곽선 원 X)
NEWS_ICON = ('<svg viewBox="0 0 22 22" width="22" height="22" fill="none" aria-hidden="true" style="flex:none;margin-right:6px;position:relative;top:6px;">'
             '<circle cx="11" cy="11" r="11" fill="#E5E7EB"/><g transform="translate(2 2)" stroke="#4B5563" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">'
             '<path d="M5 5.2h6v7.6H5.9a.9.9 0 0 1-.9-.9V5.2Z"/><path d="M11 7.4h2v4.5a.9.9 0 0 1-.9.9"/><path d="M6.7 7.4h2.6M6.7 9.4h2.6"/></g></svg>')   # 팝업 `뉴스 기사` 앞 = 회색 면 원 안 신문 (P505)
WHY_TITLE_W = 30   # 카드 안 묶음 제목 칸(`기사` · `단기` · `중기`) 폭


def _sig_text(r):
    return f'{r["name"]} : {r["state"]}'


def _sig_html(name, value):
    """팝업 신호 줄 = 이름 회색 · `:` 뒤 값 그대로 (P511, 2026-11-11 사용자)."""
    return f'<span style="color:{dk.SUB};">{dk.esc(name)}</span> : {dk.esc(value)}'


TAIL_SEP = 10   # 꼬리 `-` 칸 폭 — 꼬리가 다음 줄로 넘어가면 이 칸이 글 상자 왼쪽 밖으로 밀려 잘린다(overflow:hidden)


def _src_tail(meta):
    """기사 팝업 발언자처럼 문장 끝에 `- 11.07 · Reuters`(작은 회색 · 한 덩어리) — 줄이 바뀌어 꼬리가 줄 첫머리로 가면 `-` 는 안 보인다 (2026-11-11 사용자).
    앞 빈칸(TAIL_SEP + 4)은 문장에 붙고(단어 잇기 문자), 꼬리는 그만큼 왼쪽으로 당겨 `-` 가 빈칸 위에 놓인다."""
    if not meta:
        return ""
    return (f'\u2060<span style="display:inline-block;width:{TAIL_SEP + 4}px;"></span><wbr>'
            f'<span style="display:inline-block;white-space:nowrap;margin-left:-{TAIL_SEP}px;font-size:{dk.TINY};color:{dk.SUB};">'
            f'<span style="display:inline-block;width:{TAIL_SEP}px;">-</span>{dk.esc(meta)}</span>')


def _pop_li(text, meta="", talk=False, html=False, label=""):
    """팝업 한 줄 = 글머리 점(또는 왼쪽 라벨, P515) + 문장(+ 논의중) + 끝 꼬리 `- 날짜 · 매체` (옛: 날짜 · 매체 아랫줄). 왼쪽 들여쓰기 5 (P519)."""
    lead = (f'<span style="flex:none;display:flex;align-items:center;height:{dk.POP_LH}px;">{label}</span>' if label
            else '<span style="flex:none;width:3px;height:3px;margin-top:12px;border-radius:50%;background:#111;"></span>')
    return (f'<span style="display:flex;align-items:flex-start;gap:{6 if label else 7}px;margin:{dk.POP_ITEM_GAP}px 0;padding-left:{POP_LI_PAD}px;">{lead}'
            f'<span style="display:block;min-width:0;overflow:hidden;font-size:{dk.BODY};line-height:{dk.POP_LH}px;color:#333;word-break:keep-all;">'
            f'{text if html else dk.esc(text)}{_talk_mark().replace("top:-1px;", "top:-2px;", 1) if talk else ""}{_src_tail(meta)}</span></span>')   # 팝업 문장 안 `논의중` = 1px 더 올림 — 잉크 실측 상자 가운데가 한글보다 0.75px 아래 (P504)


POP_LI_PAD = 5   # 팝업 줄 왼쪽 들여쓰기 (P519, 2026-11-11 사용자)
POP_SUB_GAP, POP_SUB_FIRST = 31, 14   # 팝업 소제목 위 여백 — 첫 소제목은 팝업 제목 바로 아래라 40% 줄임 (P506 · P509, 2026-11-11 사용자: 모든 팝업 같은 규칙)


def _pop_first(html):
    """팝업 글 맨 앞이 소제목이면 그 위 여백만 POP_SUB_FIRST 로."""
    head = f'<span style="display:block;margin:{POP_SUB_GAP}px 0 0;'
    return f'<span style="display:block;margin:{POP_SUB_FIRST}px 0 0;' + html[len(head):] if html.startswith(head) else html


def _art_li(r, talk=None, label=""):
    """근거 기사 한 줄 — 요약 줄이 둘 이상 있으면 줄 전체를 누르면 그 기사 팝업(팝업 위 팝업, P516: 테마가 팝업 안 [data-news-pop] 을 한 겹 더 띄운다).
    기사 팝업 = 공용 dk.news_pop_body(요약 줄 · 원문 보기). 한 줄짜리는 팝업 없이 줄만(뉴스 형식 8절 — 한 줄 뉴스는 싣지 않는다)."""
    meta = " · ".join(q for q in (md(r["day"]) if r.get("day") else "", r.get("src") or "") if q)
    li = _pop_li(r["t"], meta, r.get("stage") == "talk" if talk is None else talk, label=label)
    if len(r.get("lines") or []) < 2:
        return li
    pid = dk.news_pop_id("whyart", (r.get("url") or "") + r["t"])
    return (f'<span data-news-pop="{dk.esc(pid)}" role="button" tabindex="0" style="display:block;cursor:pointer;">{li}</span>'
            + dk.news_pop_body(pid, r["t"], r["lines"], source=r.get("src") or "", kind="기사", url=r.get("url")))


def _pop_sub(title):
    return f'<span style="display:block;margin:{POP_SUB_GAP}px 0 0;font-size:15px;line-height:22px;font-weight:700;color:#111;">{title}</span>'   # 위 16 → 26 (P502)


def _why_pop(pid, title, rows, total, sigs=(), as_of=None, page=None):
    """팝업 글 = `기사`(줄마다 사실 · 날짜 · 매체, 논의중) → `단기 · 며칠` → `중기 · 한 달~분기`(우리 신호 `이름 : 판정`) → 느낌표 안내."""
    out = ""
    if rows:
        out += _pop_sub(f"{NEWS_ICON}뉴스 기사") if sigs else ""   # 옛 `기사` (P501)
        for r in rows:
            out += _art_li(r)
        if total > len(rows):
            out += f'<span style="display:block;margin:8px 0 0;font-size:14px;line-height:20px;color:{dk.SUB};">외 {total - len(rows)}건</span>'
    for hz, span in WHY_HZ:
        xs = [r for r in sigs if r["hz"] == hz]
        if xs:
            out += _pop_sub(f'{CAL_ICON}{hz} <span style="font-weight:400;color:{dk.SUB};">· {span}</span>') + "".join(_pop_li(_sig_html(r["name"], r["state"]), html=True) for r in xs)
    if sigs and as_of:   # 기준 날짜 — 종목 페이지가 있으면 링크 `10.30 종목 페이지 ›` (2026-11-11 사용자: `우리 신호 = … 값` 은 독자가 모른다)
        st = f'display:inline-flex;align-items:center;gap:2px;margin:14px 0 0;font-size:13px;line-height:19px;color:{dk.SUB};'
        out += (f'<a href="{dk.esc(page)}" style="{dk.FOLD_BTN}display:inline-flex;margin:16px 0 0;text-decoration:none;font-weight:400;">{SIG_NAME} 기준 : {md(as_of)} 종목 페이지{_CHEV_R}</a>' if page   # 인물 발언 팝업 `○○ 발언 더 보기` 와 같은 외곽선 버튼 (P503)
                else f'<span style="{st}">{SIG_NAME} 기준 : {md(as_of)}</span>')
    return f'<div data-news-pop-body="{dk.esc(pid)}" data-news-pop-title="{dk.esc(title)}" hidden>{_pop_first(out)}</div>'


CHEV14 = dk.ACC_CHEV.replace("acc-chev", "fc-right").replace('width="16" height="16"', 'width="14" height="14"', 1)   # 줄 끝 › 16 → 14 (10% 작게, 2026-11-11 사용자)
_CHEV_R = f'<span aria-hidden="true" style="flex:none;display:inline-flex;transform:rotate(-90deg);color:#333;">{CHEV14}</span>'   # 줄 끝 › (타임라인 근거 줄과 같은 것)


def _one_line(inner, grow=True, color="#111"):
    return (f'<span style="min-width:0;flex:{"1 1 auto" if grow else "0 1 auto"};overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:{WHY_FS}px;line-height:{WHY_LH}px;color:{color};">{inner}</span>')


def _why_group(title, lines_html):
    """카드 안 묶음 = 왼쪽 제목 칸(13/19 굵게 회색, 첫 줄 가운데) + 오른쪽 줄들."""
    return (f'<span style="display:flex;align-items:flex-start;gap:8px;margin:2px 0;">'
            f'<span style="flex:none;width:{WHY_TITLE_W}px;display:flex;align-items:center;height:{WHY_LH}px;font-size:13px;line-height:19px;font-weight:700;color:{dk.SUB};">{title}</span>'
            f'<span style="min-width:0;flex:1 1 auto;display:flex;flex-direction:column;">{lines_html}</span></span>')


def _why_lines(rows, sigs=()):
    """카드에 보이는 줄 — `기사` 두 줄(애널리스트 집계 줄 = 매체 없는 줄은 팝업에만) + `단기` · `중기` 한 줄씩(신호 이름 : 판정 · 로 잇고 말줄임)."""
    news = [r for r in rows if r.get("src")] or rows
    out = ""
    if news:
        ls = "".join(f'<span style="display:flex;align-items:center;min-width:0;">{_one_line(dk.esc(r["t"]), grow=False)}'
                     + (_talk_mark().replace(f"margin:0 {dk.PILL_GAP}px;", f"margin:0 0 0 {dk.PILL_GAP}px;flex:none;", 1) if r.get("stage") == "talk" else "") + "</span>"
                     for r in news[:WHY_SHOWN])
        out += _why_group("기사", ls) if sigs else ls
    for hz, _ in WHY_HZ:
        xs = [r for r in sigs if r["hz"] == hz]
        if xs:
            out += _why_group(hz, _one_line(dk.esc(" · ".join(_sig_text(r) for r in xs))))
    return out


def _why_more(pid):
    """외곽선 `더보기` 버튼 — `이전전망 ›` 버튼과 같은 모양(13/19 · 흰 바탕 · #E2E8F0 · 모서리 6 · 굵기 600)."""
    return (f'<span data-news-pop="{dk.esc(pid)}" role="button" tabindex="0" style="flex:none;display:inline-flex;align-items:center;gap:2px;cursor:pointer;'
            f'padding:2px 6px 2px 8px;border:1px solid #E2E8F0;border-radius:6px;background:#fff;font-size:13px;line-height:19px;font-weight:600;color:#333;white-space:nowrap;">더보기'
            f'<span style="display:inline-flex;transform:rotate(-90deg);">{dk.ACC_CHEV.replace("acc-chev", "fc-right").replace(chr(39) + "16" + chr(39), chr(39) + "14" + chr(39))}</span></span>')


def _why_head(title, total, pid):
    return (f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin:0 0 4px;">'
            f'<span style="font-size:14px;line-height:20px;font-weight:700;color:#111;">{title} <span style="font-weight:400;color:{dk.SUB};">{total}건</span></span>'
            + (_why_more(pid) if pid else "") + "</span>")


def _sigs(fc, d):
    sg = (fc.get("reasons") or {}).get("our_signals") or {}
    return [r for r in sg.get("rows") or [] if r.get("dir") == d], sg.get("as_of")


def side_word(sc):
    """갈래를 부르는 짧은 말 — 자동 등록 `반등한다` · `지속한다`(옛 등록 `반등 쪽이면` · `지속 쪽이면`도) → `반등` · `지속`, 그 밖(사건 전 조건 문장)은 None."""
    c = (sc.get("cond") or "").strip()
    for suf in ("쪽이면", "한다"):
        if c.endswith(suf) and 0 < len(c) - len(suf) <= 6:
            return c.removesuffix(suf).strip()
    return None


def cond_text(sc):
    """카드 첫 줄 조건 글 — 옛 자동 등록 `반등 쪽이면` 도 `반등한다` 로 (P482, 2026-11-11 사용자: "전망이니까 `반등한다` · `지속한다`")."""
    c = sc.get("cond") or ""
    return side_word(sc) + "한다" if c.endswith("쪽이면") and side_word(sc) else c


def _first_line(rows, sigs):
    """근거 칸에 보이는 한 줄 = 기사 맨 위(매체 있는 줄 먼저) → 없으면 신호 `이름 : 판정` (2026-11-11 사용자: 첫 줄 하나만, 나머지는 팝업)."""
    news = [r for r in rows if r.get("src")] or rows
    if news:
        r = news[0]
        return (f'<span style="display:flex;align-items:center;min-width:0;flex:0 1 auto;">{_one_line(dk.esc(r["t"]), grow=False)}'
                + (_talk_mark().replace(f"margin:0 {dk.PILL_GAP}px;", f"margin:0 0 0 {dk.PILL_GAP}px;flex:none;", 1) if r.get("stage") == "talk" else "") + "</span>")
    return f'<span style="display:flex;align-items:center;min-width:0;flex:0 1 auto;">{_one_line(dk.esc(_sig_text(sigs[0])), grow=False)}</span>'


def side_why(fc, sc, border):
    """갈래 카드 펼침 안 맨 아래 근거 칸 — `근거 n건` · 더보기 + 기사 두 줄 + 단기 · 중기 신호. 재료가 없으면 빈 문자열(옛 등록)."""
    w = fc.get("reasons") or {}
    if "good" not in w and not w.get("our_signals"):
        return ""
    key, word = ("good", "좋은 소식") if sc["dir"] > 0 else ("bad", "나쁜 소식")
    rows, n_news = w.get(key) or [], (w.get("count") or {}).get(key, len(w.get(key) or []))
    sigs, as_of = _sigs(fc, 1 if sc["dir"] > 0 else -1)
    total = n_news + len(sigs)
    head = (f'<span style="display:block;margin:0 0 2px;font-size:{WHY_HEAD_FS}px;line-height:{WHY_HEAD_LH}px;color:{dk.SUB};">{WHY_WORD}'
            f' <span style="font-size:14px;color:{dk.SUB};">{total}건</span></span>')   # 옛 14 굵게 → 카드 줄 이름과 같은 크기 (2026-11-11 사용자: 근거를 큰 글씨로)
    if not total:
        return (f'<div data-why="1" style="margin:12px 0 4px;padding-top:10px;border-top:1px solid {border};">{head}'
                f'<span style="display:block;font-size:14px;line-height:20px;color:{dk.SUB};">같은 기간 {word}이나 이 쪽 신호는 없었습니다.</span></div>')
    pid = dk.news_pop_id("why", f'{fc.get("slug")}-{key}')
    sw = side_word(sc)
    pop = _why_pop(pid, f'{sw} 요인' if sw else f'‘{sc["name"]}’ 요인', rows, n_news, sigs, as_of, fc.get("stock_page"))   # 옛 `‘메타 반등’ 쪽 근거` (2026-11-11 사용자: 대상 이름 반복 · 없어 보이는 말)
    # 더보기 버튼 없음 — 첫 줄 끝 › · 칸 전체를 누르면 팝업 (타임라인 근거 줄과 같은 방식, 2026-11-11 사용자)
    return (f'<div data-why="1" data-news-pop="{dk.esc(pid)}" role="button" tabindex="0" style="margin:12px 0 4px;padding-top:10px;border-top:1px solid {border};cursor:pointer;">{head}'
            f'<span style="display:flex;align-items:center;gap:4px;min-width:0;">{_first_line(rows, sigs)}{_CHEV_R}</span>{pop}</div>')


OPEN_TITLE = "향방미정"   # 붙여 쓰기 · 회색 라벨 (2026-11-11 사용자)   # 옛 `방향이 아직 안 정해진 일` 카드 (2026-11-11 사용자: 문장을 줄여 새 제목, 카드 없이 타임라인 위 한 줄)


def timeline_lead(fc, log):
    """레일 맨 위 두 줄 = 시계 아이콘 마디 + `Timeline` 제목, 그 아래 마디 없이 점선만 + `향방미정` 줄 — 시계부터 날짜 동그라미까지 한 줄로 이어진다 (2026-11-11 사용자).
    위 여백 = 옛 구획 제목 위 28 + TL_TITLE_GAP."""
    big = CLOCK.replace('width="16" height="16"', f'width="{TL_TITLE_ICON}" height="{TL_TITLE_ICON}"', 1)
    icon = f'<span style="display:inline-flex;color:{dk.SUB};">{big}</span>'
    title = (f'<div data-tl-title="1" style="padding:0 0 11px;font-size:{TL_TITLE_FS}px;line-height:{TL_TITLE_ICON + 4}px;font-weight:700;color:#111;">Timeline</div>')
    out = f'<div style="height:{28 + TL_TITLE_GAP}px;"></div>' + _tl_row(icon, TL_TITLE_ICON + 4, 0, title, True, False)
    ol = open_line(fc, log)
    if ol:
        out += _tl_row("", 0, 0, ol, False, False)
    return out


def timeline_title():
    """타임라인 구획 제목 `Timeline`(영어) — `향방미정` 줄 위, 위 여백 +30 (P484 · P485, 2026-11-11 사용자). 구획 제목 글씨(dk.h2), 밑줄 없음."""
    h = (dk.h2("Timeline", line=False).replace(f"font-size:{dk.H2_SIZE};", f"font-size:{TL_TITLE_FS}px;", 1).replace("align-items:baseline;", "align-items:center;", 1)
         .replace(">Timeline", '><span style="display:inline-flex;color:' + dk.SUB + ';margin-right:-4px;">' + CLOCK.replace('width="16" height="16"', f'width="{TL_TITLE_ICON}" height="{TL_TITLE_ICON}"', 1) + '</span>Timeline', 1))   # 3.10 호환 — f-string 안 따옴표 겹침 금지   # 제목 앞 시계 (2026-11-11 사용자 — 옛 오늘 줄 마디)
    return f'<div data-tl-title="1" style="padding-top:{TL_TITLE_GAP}px;">{h}</div>'


TL_TITLE_FS = 18   # `Timeline` = 구획 제목 22 에서 3 작게 (2026-11-11 사용자: 2 → 1 더)
TL_TITLE_ICON = 20   # 제목 앞 시계 크기 (제목 19 와 비슷하게)
TL_TITLE_GAP = 10   # +30 → +20 (P490)


OPEN_GAP = 35   # `향방미정` 줄 ~ 첫 날짜 = 타임라인 근거 줄 ~ 다음 날짜와 같은 35 (실측, 2026-11-11 사용자: "날짜 사이 여백과 동일")


def open_pill():
    """`향방미정` 라벨 = 회색 강조 카드 색(바탕 #F8FAFC · 테두리 #E2E8F0, dk.CARD_DIR neutral) · 글자는 회색 라벨 그대로 (2026-11-11 사용자)."""
    bg, bd = dk.CARD_DIR["neutral"]
    return (dk.pill(OPEN_TITLE, "neutral", bare=True).replace("vertical-align:middle;", "vertical-align:middle;flex:none;", 1)
            .replace("background:#fff;", f"background:{bg};", 1).replace(f"border:1px solid {dk.PILL['neutral'][0]};", f"border:1px solid {bd};", 1))


def open_line(fc, log):
    """타임라인 위 한 줄 `향방 미정  11.10  기사 [논의중] ›` — 좋고 나쁨 자체가 갈리는 기사(open)를 등록 때 + 날마다 쌓은 것에서 가장 최근 하나만,
    줄 전체를 누르면 팝업에 전부(최근 순 · 날짜 · 매체). 우리 신호 중립은 사건이 아니라 넣지 않는다. 없으면 빈 문자열."""
    rows, seen = [], set()
    for r in ((fc.get("reasons") or {}).get("open") or []) + [r for e in log or [] for r in ((e.get("why") or {}).get("open") or [])]:
        if r.get("t") and r["t"] not in seen:
            seen.add(r["t"])
            rows.append(r)
    if not rows:
        return ""
    rows.sort(key=lambda r: r.get("day") or "", reverse=True)
    top = rows[0]
    pid = dk.news_pop_id("whyopen", fc.get("slug"))
    pop = "".join(_art_li(r, talk=False) for r in rows)   # `논의중` 라벨 없음 — 향방미정이 이미 정해지지 않은 일 (2026-11-11 사용자)
    body = f'<div data-news-pop-body="{dk.esc(pid)}" data-news-pop-title="{OPEN_TITLE}" hidden>{pop}</div>'
    chev = f'<span aria-hidden="true" style="flex:none;display:inline-flex;transform:rotate(-90deg);color:#333;">{CHEV14}</span>'
    return (f'<div data-why-open="1" data-news-pop="{dk.esc(pid)}" role="button" tabindex="0" style="display:flex;align-items:center;gap:8px;margin:0 0 {OPEN_GAP}px;padding:0 {dk.ALIGN_PX}px 0 0;cursor:pointer;">'
            + open_pill()
            + (f'<span style="flex:none;font-size:13px;line-height:19px;color:{dk.SUB};">{md(top["day"])}</span>' if top.get("day") else "")
            + f'<span style="display:flex;align-items:center;gap:4px;min-width:0;flex:0 1 auto;">{_one_line(dk.esc(top["t"]), grow=False)}{chev}</span>{body}</div>')


def _scenario_card(sc, v, tag=None, extra=None, compact=False, mkt=False, why=""):
    """갈래 카드 = 데일리 질문 카드(강조 카드 · 접기, 가이드 2-7) — 첫 줄 조건 + 라벨 · 오른쪽 답. 펼치면 고리 줄 + `이 전망이 맞으면`."""
    th, d = v["theme"], sc["dir"]
    tk = _tag_kind(sc)
    if tk in ("up", "down"):   # 카드 색 = 이름표 색 (2026-11-08 사용자: 전망A = 빨강 · 전망B = 파랑, 실현됨이면 그 색 카드) — 주가 방향(dir)이 아니라 이름표 방향
        d = 1 if tk == "up" else -1
        if v["answer"] in (ANS_HIT, ANS_LEAN):   # 우세함도 그 전망 색 카드 (2026-11-08 사용자 — 옛 P421 보라)
            th = THEME[d]
    ink = INK[d] if v["answer"] in (ANS_HIT, ANS_LEAN) else ("#111" if v["active"] else dk.MUTED)
    def box(state):   # 근거 줄 값 = 라벨 박스(확인 = 그 갈래 방향 색, 대기 · 해당 없음 = 회색). 질문 카드는 <span 으로 시작하는 값을 그대로 쓴다(P330)
        word, kind = CHAIN[state]
        if state == "no":   # `해당 없음` = 흐린 회색 라벨 (P417)
            return dim_box(word)
        k = (("down" if d < 0 else "up") if v["active"] else "flat") if kind == "down" else kind
        b = TS.box(k, word, dk.esc, sym=False, fit=True)
        return b.replace("font-weight:700;", "font-weight:400;", 1) if state == "wait" else b   # 덜 중요한 라벨 = 보통 굵기 (P500)
    Lw = sc.get("_L", 3.0)
    lines = [("row", f'<span style="font-size:{CHAIN_FS}px;">{dk.esc(wordify(c["step"], Lw))}</span>', box(c["state"]), wordify(c["ev"], Lw)) for c in sc["chain"]] + [("row", f'‘{sc["name"]}’ 이 되는 기준', "", wordify(sc["win"], Lw))]   # 옛 `이 전망이 맞으면` — 지시어 대신 갈래 이름 (2026-11-07 사용자)
    if sc.get("odds") and odds_meaningful(*sc["odds"][:2]):   # 기록상 줄 = 한쪽으로 뚜렷할 때만(윌슨 구간, `유력` 과 같은 잣대) — 반반은 적지 않는다 (2026-11-11 사용자: "반반이면 어쩌라고")
        m, n, note = sc["odds"]
        lines.insert(0, ("row", "기록상", share_word(m, n).replace("이었습니다", ""), wordify(note, Lw)))
    lines += _ahead_lines(extra or [], Lw)   # 미리 알아 둘 것 (옛 `앞으로 올 수 있는 일`, 2026-11-07 사용자)
    html = qc.question_card(cond_text(sc), v["answer"], th, ink, lines, fold=True, opened=False)   # 전망 카드는 처음에 모두 닫힘 — 일어난 갈래도 (P462, 2026-11-08 사용자). 답 · 색으로 상태는 닫힌 채 보인다
    html = _small_row(html, f'‘{sc["name"]}’ 이 되는 기준', None if side_word(sc) else _crit_text(sc, Lw), th)   # 자동 등록 = 기준 줄 없음(고리 마지막 줄 `급락 폭의 절반 회복` 과 같은 말, P487)
    if compact is None:   # 얇은 카드 = 결과가 났고 해당 없는 갈래만, 일어난 갈래는 원래 크기 (P471, 2026-11-08 사용자)
        compact = v["answer"] == NOT_HAPPENED
    marks = [m for m in (v["label"], MKT_LABEL if mkt else None) if m]   # 유력 · 시장예상 = 조건 끝 보라 굵은 글씨 `- 유력` (2026-11-08 사용자: 라벨 상자 대신 글자)
    boxes = violet_word("- " + " · ".join(marks), color=None if v["active"] else DIM_TEXT) if marks else ""   # 해당 없는 갈래 = 흐린 글씨 (P416 과 같게)
    # 자리 = 조건 문장 끝 · 뉴스 기사 라벨 크기 (2026-11-08 사용자 — 옛 P473 `전망 A · B` 이름표 옆 · 조건 글 아랫줄)
    if why:   # 근거 칸 = 펼침 안 맨 아래 (2026-11-11 사용자: "근거는 전망 펼침 안에") — 펼친 몸통(</ul></div>) 바로 뒤, </details> 앞
        k = html.rfind("</details>")
        if k > 0:
            html = html[:k] + why + html[k:]
    if not v["active"]:
        html = _dim(html)
    if tag:   # 카드 첫 줄 맨 앞 이름표 `전망 A` (P386) — 우리 전망 라벨과 같은 크기
        tbox = TS.box(_tag_kind(sc), tag, dk.esc, sym=False, fit=True) if v["active"] else dim_box(tag)   # 해당 없는 갈래 = 이름표까지 흐린 회색 (P416)
        # 이름표 폭 고정 54 · 글자 왼쪽 붙임 — `전망 A` · `전망 B` 글자 폭 차이(0.5px)로 조건 글 시작선이 어긋나지 않게 (P478, 2026-11-08 사용자: 세로 기준선 일치)
        tbox = tbox.replace("justify-content:center;", "justify-content:flex-start;", 1).replace("padding-left:7px;padding-right:7px;", f"width:{TAG_W}px;padding-left:7px;padding-right:0;", 1)
        if compact:   # 접힌 얇은 카드 = 이름표 상자의 바탕 · 테두리만 지워 글씨로 (P472 → P478) — 상자 폭 · 안쪽 여백은 그대로라 `전망 A` 글자와 조건 글 시작선이 펼친 카드(`전망 B`)와 같은 세로선
            tbox = tbox.replace('<span style="display:inline-flex;align-items:center;justify-content:flex-start;gap:3px;', '<span class="fc-th-ghost" style="display:inline-flex;align-items:center;justify-content:flex-start;gap:3px;', 1)
        html = _tag_title(html, cond_text(sc), tbox, tail=boxes)   # 짧으면 이름표 · 조건 글 · 라벨 한 줄 (옛 stack: 라벨 줄 아래로 조건 글)
    if compact:
        html = _thin(html, th)
    return html


TAG_W = 50   # `전망A · B` 이름표 폭 (P478) — 띄어쓰기를 뺀 굵은 14 `전망B` 글자 + 왼쪽 7 + 테두리 2 + 여유 3 (2026-11-08 사용자: 띄어쓰기 없이, 옛 54)
MKT_LABEL, MKT_MIN = "시장예상", 60   # 사건 전 전망 — 시장이 한쪽 결과를 60% 넘게 볼 때 그 갈래에 노랑 `시장예상`(P475) (P470, 2026-11-08 사용자: 띄어쓰기 없이). 우리 판단이 아니라 시장 확률(market_prob)


def _mkt_no(fc):
    """시장예상 라벨이 붙을 갈래 번호 — 사건 전(틀 S) · market_prob 한쪽 ≥ 60% 일 때만, 아니면 None."""
    probs = (fc.get("market_prob") or {}).get("probs") or []
    if fc.get("kind") != "pre" or not probs or max(probs) < MKT_MIN:
        return None
    return probs.index(max(probs)) + 1


THIN_CSS = ("<style>"   # 접힌 `해당 없음` 카드 = 얇은 한 줄, 펼치면 원래 카드 (P472, 2026-11-08 사용자: 접었을 때만 작게)
            ".fc-thin:not(:has(>details[open])){padding:2px 14px!important;border-radius:7px!important;min-height:31px;box-sizing:border-box;display:flex;flex-direction:column;justify-content:center;}"   # 높이 31 = 세부 전망 버튼 (라벨이 없으면 글자만이라 26 이 되던 것)
            ".fc-thin:not(:has(>details[open])) .fc-th-row{line-height:20px!important;}"
            ".fc-thin:not(:has(>details[open])) .fc-th-t{font-size:14px!important;}"
            ".fc-thin:not(:has(>details[open])) .fc-th-a{font-size:14px!important;font-weight:700!important;}"
            ".fc-thin:not(:has(>details[open])) .fc-th-fold{display:none!important;}"
            ".fc-thin:not(:has(>details[open])) .fc-th-chev{display:inline-flex!important;}"
            ".fc-thin:not(:has(>details[open])) .fc-th-ghost{background:transparent!important;border-color:transparent!important;color:" + DIM_TEXT + "!important;}"
            ".fc-thin:not(:has(>details[open])) .fc-th-lab{margin-top:0!important;align-self:center;}"
            ".fc-thin:not(:has(>details[open])) .fc-th-wrap{align-items:center!important;}"   # 이름표 칸 · 조건 글 세로 가운데 (P478) — 한 낱말 조건은 nowrap 칸 안에 들어가 자식 선택자로는 못 잡았다
            ".fc-thin:not(:has(>details[open])) .fc-th-stack{flex-direction:row!important;gap:8px!important;}"   # 접힌 얇은 카드는 라벨이 있어도 한 줄
            "</style>")


def _thin(html, theme):
    """결과가 난 뒤 `해당 없음` 갈래 카드 — 접혀 있으면 세부 전망 버튼처럼 얇은 한 줄(높이 31 · 글자 14 · 모서리 7 · 화살표만 · 이름표 = 보통 글씨),
    펼치면 원래 카드 모양 (P469 → P472, 2026-11-08 사용자). 모양 바꾸기는 THIN_CSS 가 details[open] 으로 — 여기선 클래스만 단다."""
    html = html.replace('<div style="background:', '<div class="fc-thin" style="background:', 1)
    html = html.replace('<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;position:relative;', '<span class="fc-th-row" style="display:flex;justify-content:space-between;align-items:center;gap:12px;position:relative;', 1)
    html = html.replace('<span style="flex:1 1 auto;min-width:0;font-weight:', '<span class="fc-th-t" style="flex:1 1 auto;min-width:0;font-weight:', 1)
    html = html.replace('<span style="flex:none;white-space:nowrap;font-weight:', '<span class="fc-th-a" style="flex:none;white-space:nowrap;font-weight:', 1)
    fold = f'<span style="display:inline-flex;flex:none;align-items:center;justify-content:center;width:{dk.FOLD_BOX}px;height:{dk.FOLD_BOX}px;'
    chev = f'<span class="fc-th-chev" style="display:none;flex:none;margin-left:4px;color:{DIM_TEXT};">{dk.ACC_CHEV}</span>'   # 접기 네모 대신 화살표만
    html = html.replace(fold, chev + fold.replace('<span style=', '<span class="fc-th-fold" style=', 1), 1)
    return html

def _now_plain(fc, st):
    """현재 증시는? — 카드 없이 접는 줄 안에 값 줄 + 그래프 (P425, 2026-11-08 사용자: 카드가 하나뿐이면 카드 형식 X, `한국은 어떻게?` 삭제)."""
    rows, chart = _now_block(fc, st, parts=True)
    # 첫 줄(자 이름 · 값 · `종가 대비 · 꽤 오름`)은 그래프 제목과 겹쳐 지우고 값만 그래프 제목 오른쪽에 한 줄로 (P428, 2026-11-08 사용자). 나머지 줄(회복 폭 · 불안 지수)은 그대로
    first, rest = (rows[0], rows[1:]) if rows else (None, [])
    out = _plain_rows("", [(n, fmt_tri(v), note) for n, v, note in rest]) if rest else ""
    if chart:
        if first and first[1]:
            head_start = chart.find(dk.CHART_TITLE_M)
            if head_start >= 0:
                end = chart.find("</span>", head_start + len(dk.CHART_TITLE_M))
                title = chart[head_start + len(dk.CHART_TITLE_M):end]
                line = (f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:0 0 {dk.CHART_TITLE_GAP}px;">'
                        f'{dk.CHART_TITLE}{title}</span><span style="flex:none;font-size:{dk.NAME};line-height:{dk.LH_CARD};font-weight:400;">{fmt_tri(first[1])}</span></span>')
                chart = chart[:head_start] + line + chart[end + len("</span>"):]
        # 그래프 폭 = 왼쪽 글자 기준선 6 ~ 접기 버튼 오른쪽 끝 (P438, 2026-11-08 사용자) — 흰 카드의 양쪽 −5 넓힘(CHART_CARD_X)은 여기서 끈다
        chart = chart.replace(f"margin:0 {dk.CHART_CARD_X}px;", "margin:0;", 1)
        out += f'<div style="margin:{12 if rest else 4}px 0 0;padding:0 0 0 {dk.ALIGN_PX}px;">{chart}</div>'
    return out


def fmt_tri(v):
    return tri_text(dk.esc(v)) if v else v


def _now_block(fc, st, parts=False):
    """현재 증시는? = 질문 카드 — 쉬운 말 한 줄 · 근거 줄 · 카드 안 그래프(금 선 · 평소 비교선)."""
    log = st.get("log") or []
    e = log[-1] if log else _entry("", "start", "지켜보는 중", 0, "", 0.0)
    unit, L = fc.get("unit", "%p"), fc["line"]
    rv = st.get("rel")
    rel_word = "" if rv is None else (("거의 같음" if strength(rv, L) == "거의 같게" else f'{strength(rv, L)} {"강함" if rv > 0 else "약함"}') if fc.get("cmp") else ("거의 그대로" if strength(rv, L) == "거의 같게" else f'{strength(rv, L)} {"오름" if rv > 0 else "내림"}'))
    # 첫 문장은 `전망 결과` 카드 문장과 겹쳐 뺀다 · 거래량은 독자에게 뜻이 안 읽혀 운영자 상자로 (2026-11-07 사용자 "이걸 왜 알아야 하나" → Claude 정리)
    lines = [("row", fc["ruler_short"], fmt_v(rv, unit), (fc["ruler_from"] + (" · " + rel_word if rel_word else "")))]   # 값 = 숫자 + 세기 말 (2026-11-07 정정)
    # `급락 폭 중 회복` 줄 삭제 (2026-11-11 사용자: 반등 쪽 판단처럼 읽히고 타임라인에 이미 있다)
    if st.get("vix") is not None and (fc["kind"] == "after" or fc.get("baseline") is not None):   # 불안 지수는 그 전망의 기록 · 고르기가 쓸 때만
        lines.append(("row", "불안 지수 (VIX)", f'{st["vix"]:.1f}', vix_word(st["vix"])))
    days, vals = st.get("days", []), st.get("rel_series", [])
    if days and sum(v is not None for v in vals) >= 2:   # 점 하나면 막대 하나로 보여 그리지 않는다
        n = len(days)
        at = st.get("label_at") or [0, n // 2, n - 1]
        labels = [md(dd) if i in at else "" for i, dd in enumerate(days)]
        if fc["kind"] == "pre":
            guides = [("상승 기준", [L] * n, "#FCA5A5", "dash"), ("하락 기준", [-L] * n, "#93C5FD", "dash")]
        else:
            g, s = fc["gap"], (1 if fc["gap"] > 0 else -1)
            guides = [(f"{REV[s][0]} 기준", [g * 0.5] * n, "#FCA5A5" if s < 0 else "#93C5FD", "dash"), (f"{DIR_WORD[s]} 지속 기준", [g + s * L] * n, "#93C5FD" if s < 0 else "#FCA5A5", "dash")]
        if fc.get("baseline") is not None:
            guides.append((fc.get("baseline_label", "평소"), [fc["baseline"]] * n, dk.CHART_CMP, "dash"))
        gr = dk.trend_card(f'{fc["ruler_short"]} ({unit})', labels, [(fc["ruler_short"], vals, dk.CHART_MAIN, "solid")] + guides, lambda v: fmt_v(v, unit))
        lines.append((f'<span data-end-chart="1" style="display:block;margin:0 0 -{END_PULL}px;">{gr}</span>', "html"))
    if parts:   # 카드 없이 쓸 때 (P425) — (값 줄, 그래프)
        return [(x[1], x[2], x[3]) for x in lines if x[0] == "row"], (gr if days and sum(v is not None for v in vals) >= 2 else "")
    return qc.question_card("현재 증시는?", e["label"], e["theme"] if e["theme"] in qc.CARD_DIR else "neutral", INK[e["dir"]], lines, fold=True, opened=True)


def _pressure_card(fc):
    """지금 시장 분위기는? — 층 사이 압력 (2026-11-07 사용자: 거시 → 업종 → 종목으로 분위기가 내려오고, 그 분위기는 언론이 키운다. 케이스가 서로 단절돼 보이면 안 된다).
    fc["pressure"] = {"answer": 한 마디, "rows": [(이름, 값, 근거)]} — 값은 이미 매일 나오는 우리 판정(signal_groups regime · shock · sector_flow · news)과 공포 · 탐욕 지수 그대로.
    fc["parent"] = (no, title, slug) 위 층 전망, fc["children"] = [(no, title, slug)] 아래 층 전망. 전망은 혼자가 아니라 사슬의 한 칸으로 보인다."""
    pr = fc.get("pressure")
    if not pr and not fc.get("parent") and not fc.get("children"):
        return ""
    lines = [(f"주식은 혼자 움직이지 않습니다. 시장 → 업종 → 종목 순으로 분위기가 내려오고, 그 분위기는 뉴스와 방송이 키웁니다. ‘{fc['title']}’ 위에 있는 흐름입니다.", "plain")]
    if pr:   # 값 · 근거의 숫자는 말로 (근거 숫자 줄은 뺌)
        lines += [("row", k, wordify(_re.sub(r"^\d+(\.\d+)?\s*", "", str(v))) or str(v), "") for k, v, n in pr["rows"]]
    if fc.get("parent"):
        n, t, sl = fc["parent"]
        lines.append((f'‘{dk.esc(fc["title"])}’ 는 <a href="{page_url(sl)}" style="color:#111;">‘{dk.esc(t)}’</a> 에서 내려온 세부 전망입니다. ‘{dk.esc(t)}’ 의 지금 국면이 배경입니다.', "html"))
    for n, t, sl in fc.get("children", []):
        lines.append((f'세부 전망 : <a href="{page_url(sl)}" style="color:#111;">‘{dk.esc(t)}’</a>', "html"))
    return qc.question_card("지금 시장 분위기는?", pr["answer"] if pr else "사슬 보기", "neutral", "#111", lines, fold=True, opened=bool(pr))


def _broke_card(fc):
    """어디서 끊겼나 — 틀린 전망의 가치 (2026-11-07 사용자). fc["broke"] = {"lead", "items": [(이름, 글, 근거)]}. 변명이 아니라 미리 적어 둔 것과 대조만.
    모양 = `현재 증시는?` · `기록상 비슷한 때는?` 와 같은 접는 줄 + 제목 뒤 노랑 `끊김` 라벨, 옛 강조 카드 · 답 `고리 대조` 삭제 (P435, 2026-11-08 사용자).
    안 = 첫 문장 + 구분선 줄(이름 · 문장 · 작은 회색 근거), 글자 왼쪽 기준선 6 · 굵게 없음 (P424 와 같게)."""
    b = fc.get("broke")
    if not b:
        return ""
    L, A = fc.get("line", 3.0), dk.ALIGN_PX
    out = f'<p style="margin:0 0 4px;padding:0 {A}px 0 {A}px;font-size:{dk.NAME};line-height:{dk.LH_CARD};color:#111;word-break:keep-all;">{tri_text(dk.esc(wordify(b["lead"], L)))}</p>'
    for i, (name, rec, note) in enumerate(b["items"]):
        out += (f'<div style="padding:{14 - dk.VP}px {A}px {14 - dk.VP}px {A}px;{"border-top:1px solid #E2E8F0;" if i else ""}">'
                f'<span style="display:block;font-size:{dk.NAME};line-height:{dk.LH_CARD};color:#111;word-break:keep-all;">{dk.esc(name)}</span>'
                f'<span style="display:block;margin-top:2px;font-size:{dk.NAME};line-height:{dk.LH_CARD};color:#333;word-break:keep-all;">{tri_text(dk.esc(wordify(rec, L)))}</span>'
                + (f'<span style="display:block;margin-top:2px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};word-break:keep-all;">{dk.esc(wordify(note, L))}</span>' if note else "")
                + '</div>')
    return _fold_row("어디서 끊겼나", out, label=TS.box("caution", "끊긴 고리", dk.esc, sym=False, fit=True))   # `끊김` 만 두면 전망이 끊긴 것처럼 읽힌다 — 끊긴 건 고리 하나, 전망은 종료 (P464, 2026-11-08). 고리 줄 상태 이름표는 `끊김` 그대로


def _ahead_lines(items, L):
    """미리 알아 둘 것 블록 — 조건(굵게) · 기록상 문장 · 볼 것(작은 글씨). 옛 `앞으로 올 수 있는 일` 카드 줄을 갈래 카드 안으로 (2026-11-07 사용자)."""
    out = []
    for cond, rec, watch in items:
        rec = _re.sub(r"\.\s*선반영$", "", rec)   # 이름표가 `선반영` 이라 문장 끝 같은 말은 뺀다
        # 조건 제목 = 그래프 제목과 같은 모양(※ + 16/24 굵게, P431, 2026-11-08 사용자)
        out.append(((f'<span style="display:block;padding:10px 0 0;font-size:{dk.NAME};line-height:{dk.LH_CARD};font-weight:700;color:#111;word-break:keep-all;">{dk.CHART_MARK}{dk.esc(cond)}</span>' if cond else "")
                    + f'<span style="display:block;margin-top:{2 if cond else 8}px;font-size:{dk.NAME};line-height:{dk.LH_CARD};color:#333;word-break:keep-all;">{num_html(wordify(rec, L))}</span>'
                    + (f'<span style="display:block;margin-top:2px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};word-break:keep-all;">볼 것 : {dk.esc(wordify(watch, L))}</span>' if watch else ""), "html"))
    return out


def _split_ahead(fc, st):
    """옛 prepare → (갈래별 덧붙일 줄 {no: [item]}, 셋째 카드 (이름표, item) 또는 None).
    결과 전: 1번 → 전망 A, 2번 → 전망 B, 3번 → 셋째 카드(사건 전 = `선반영`, 충격 뒤 = `제자리`).
    결과 뒤: 다음에 올 수 있는 일 → 일어난 갈래 카드 안. 상태 설명뿐인 것(보류 · 무효의 lead)은 경과 문장에 이미 있어 버린다.
    lead(지금 분위기) 는 `지금은?` 분위기 카드에, 사슬 한 줄은 갈래 카드 고리 줄에 이미 있어 옮기지 않는다 (Claude 판단, 2026-11-07)."""
    pr = fc.get("prepare") or {}
    items = [tuple(x) for x in pr.get("items", [])]
    res = st.get("result")
    if not items or (res and res.get("word") in (RESULT["hold"], RESULT["void"])):
        return {}, None
    if res:
        won = res.get("crossed") or (st.get("cond") if fc["kind"] == "pre" else None) or 1
        return {won: items}, None
    per = {i + 1: [it] for i, it in enumerate(items[:2])}
    # 셋째 카드: 사건 전 `선반영` 은 선반영 조건(감지 · 시장 예상 70% 이상)일 때만 — 기본 화면엔 없다 (2026-11-08 사용자). 충격 뒤 `제자리` 은 그대로
    third = (("선반영" if fc["kind"] == "pre" else "제자리"), items[2]) if len(items) > 2 and (fc["kind"] != "pre" or _priced(fc)) else None
    return per, third


def _third_card(tag, item, L):
    cond, rec, watch = item
    lines = _ahead_lines([("", rec, watch)], L)
    html = qc.question_card(cond, "", "neutral", "#111", lines, fold=True, opened=False)
    return _tag_title(html, cond, TS.box("flat", tag, dk.esc, sym=False, fit=True))


def _prepare_card(fc):
    """앞으로 올 수 있는 일 — 경고 · 대비 카드 (2026-11-07 사용자: 묘사가 아니라 "이렇게 되면 이런 일이 올 수 있으니 미리 생각해 두자").
    fc["prepare"] = {"lead": 한 줄, "items": [(조건, 기록상 한 줄, 볼 것)], "chain": 사슬 한 줄(없으면 생략)}.
    규칙: 조건부(“~하면”) + 기록상 n번 중 m번 + 볼 것. 매수 · 매도 · 비중 말 없음. 날짜 붙은 ‘위험 구간’ 아님 — 다가오는 사건 하나에 묶인 조건부 경고(1절 4-2 예외)."""
    pr = fc.get("prepare")
    if not pr:
        return ""
    L = fc.get("line", 3.0)
    lines = [(wordify(pr["lead"], L), "plain")]
    for cond, rec, watch in pr["items"]:   # 조건(굵게) · 문장 · 볼 것(작은 글씨) 세 줄 블록 — row 는 값 칸이 줄바꿈 없음이라 긴 문장에서 카드가 깨진다 (2026-11-07 사용자)
        lines.append((f'<span style="display:block;padding:10px 0 0;font-size:{dk.EMPH_Q};line-height:{dk.LH_EMPH_Q};font-weight:700;color:#111;word-break:keep-all;">{dk.esc(cond)}</span>'
                      f'<span style="display:block;margin-top:2px;font-size:{dk.NAME};line-height:{dk.LH_CARD};color:#333;word-break:keep-all;">{num_html(wordify(rec, L))}</span>'
                      + (f'<span style="display:block;margin-top:2px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};word-break:keep-all;">볼 것 : {dk.esc(wordify(watch, L))}</span>' if watch else ""), "html"))
    if pr.get("chain"):
        lines.append((_re.sub(r"\s*\([^()]*\d[^()]*\)", "", pr["chain"]), "note"))   # 사슬 시차 숫자(당일~이틀 · 1~20일)도 독자에겐 뺀다
    return qc.question_card("앞으로 올 수 있는 일", pr.get("answer", "미리 생각해 둘 것"), "uncertain", "#C2410C", lines, fold=True, opened=True)


def _korea_card(fc):
    """한국은 어떻게? — 미국 사건은 다음 날 아침 한국장으로 연결된다 (‘닿다’ 금지 — 영향 · 이어짐은 연결, 범위 끝은 도달, 2026-11-07) (지도 13-4, 한국 독자의 첫 질문). fc["korea"] = {"lead", "rows": [(이름, 값, 근거)], "note"}.
    값은 기록상 비율 · 배수(2016~ 실측)와 실제 다음 날 값(있으면). 매수 · 매도 말 없음."""
    k = fc.get("korea")
    if not k:
        return ""
    # 잰 기록 줄(‘n번 중 m번’)만 — 상식 문장(원/달러) · 안내 줄(확인 시각)은 뺀다. 아래 줄은 실제 다음 날 값(날짜가 든 문장)일 때만 (2026-11-07 사용자 · Claude 판단, P391)
    lines = [(wordify(k["lead"]), "plain")] + [("row", wordify(a), wordify(b), wordify(c)) for a, b, c in k["rows"] if "번 중" in b]
    if k.get("note") and _re.search(r"\d{2}\.\d{2}", k["note"]):
        lines.append((wordify(k["note"]), "note"))
    return qc.question_card("한국은 어떻게?", k.get("answer", "다음 날 아침"), "neutral", "#111", lines, fold=True, opened=True)


def _history_card(fc):
    """기록상 비슷한 때는? — 독자가 다음으로 묻는 것(얼마나 더 가나 · 보통은 어땠나)을 기준선으로. 숫자는 중앙값 · 횟수만, 단언 없음.
    fc["history"] = {"what": 조건 문장, "n": 횟수, "since": 시작 연도, "rows": [(기간, 값 글)]}. 없으면 그리지 않는다."""
    h = fc.get("history")
    if not h:
        return ""
    L = fc.get("line", 3.0)
    what = _re.sub(r"하루\s*[\d.]+\s*%p?\s*넘게", "하루에 크게", h["what"])   # '하루 3% 넘게' → '하루에 크게'
    if h.get("vs_base"):   # 평소와 나란히 (2026-11-07 검증: 평소 비교 없는 '10번 중 6번 올랐다' 는 아무 달과 같은 숫자였다)
        lead = f'{wordify(what, L)} {h["since"]}년부터 {h["n"]}번 있었습니다. 그 뒤를 평소(아무 날이나 고른 때)와 나란히 놓았습니다.'
    else:
        lead = f'{wordify(what, L)} {h["since"]}년부터 여러 번 있었습니다. 그 뒤 오른 일이 얼마나 흔했는지입니다.'
    rows = []
    for r in h["rows"]:   # 값 = 말 (숫자 X, 2026-11-07)
        if len(r) == 4:   # [이름, 횟수, 전체, 평소 %] → `10번 중 n번` · 아래 `평소 10번 중 m번`
            nm, m, n, bp = r
            ten = lambda pct: f"10번 중 {round(pct / 10)}번" if pct >= 5 else "10번 중 1번 미만"
            same = _binom_p(m, n, bp / 100) >= 0.1   # 우연으로 볼 만한 차이면 숫자를 나란히 두지 않고 `평소와 비슷` — 10번 기준 반올림이 1 vs 2 처럼 차이를 부풀린다 (2026-11-07)
            rows.append((nm, "평소와 비슷" if same else ten(m / n * 100), f"{ten(m / n * 100)} · 평소 {ten(bp)}" if same else f"평소 {ten(bp)}"))
            continue
        if len(r) == 2:
            rows.append((wordify(r[0], L), wordify(r[1], L), ""))
        else:
            k, m, rng = r
            rows.append((f"{k.replace('5거래일', '일주일').replace('20거래일', '한 달').replace('60거래일', '석 달')} 올랐다", f'10번 중 {round(m / h["n"] * 10)}번', ""))   # 숫자로 통일 (2026-11-07 사용자: 많은 편 · 열에 6 꼴 → 10번 중 6번)
    for when, name, val in h.get("alike", []):   # 가장 비슷했던 때 셋 — 이름 + 그 뒤 한 달의 말
        try:
            v = float(str(val).replace("−", "-").replace("%p", "").replace("%", ""))
            vw = "기준 안" if abs(v) < L else f'기준 넘게 {"오름" if v > 0 else "내림"}'   # 세기 말은 기준 대비 — +1.9% 를 `꽤 오름` 이라 한 과장 고침 (2026-11-07 사용자)
        except ValueError:
            vw = wordify(str(val), L)
        rows.append((wordify(f"{when} {name}".strip(), L), f"{vw} ({val})", h.get("alike_note", "가장 비슷했던 때 · 그 뒤 한 달")))
    return _plain_sec("기록상 비슷한 때는?", lead, rows, "기록은 눈금일 뿐 이번이 그대로 되풀이된다는 뜻은 아닙니다.")


def _binom_p(k, n, p):
    """양쪽 정확 이항 p (validate_fomc_history.binom_p 와 같은 셈)."""
    import math
    pr = lambda i: math.comb(n, i) * p ** i * (1 - p) ** (n - i)
    pk = pr(k)
    return min(1.0, sum(pr(i) for i in range(n + 1) if pr(i) <= pk * (1 + 1e-9)))


def _plain_rows(lead, rows, note="", lines=True):
    """접는 줄 안 내용 — 글자는 왼쪽 기준선 6(제목 점과 같은 선, P424) · 오른쪽도 6(좌우 같게, P461), 구분선은 끝까지. 굵게 없음 · 증감 숫자 = ▲ · ▼ + 색 (P423 · P424, 2026-11-08 사용자)."""
    A = dk.ALIGN_PX
    out = f'<p style="margin:0 0 4px;padding:0 {A}px 0 {A}px;font-size:{dk.NAME};line-height:{dk.LH_CARD};color:#111;word-break:keep-all;">{tri_text(dk.esc(lead))}</p>' if lead else ""
    for i, (name, val, sub) in enumerate(rows):
        out += (f'<div style="padding:{14 - dk.VP}px {A}px {14 - dk.VP}px {A}px;{"border-top:1px solid #E2E8F0;" if i and lines else ""}">'
                f'<span style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;font-size:{dk.NAME};line-height:{dk.LH_CARD};">'
                f'<span style="color:#111;word-break:keep-all;">{dk.esc(name)}</span>'
                + (f'<span style="flex:none;max-width:55%;text-align:right;color:#111;word-break:keep-all;">{val if str(val).startswith("<") else tri_text(dk.esc(val))}</span>' if val else "") + '</span>'
                + (f'<span style="display:block;margin-top:2px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};word-break:keep-all;">{dk.esc(sub)}</span>' if sub else "")
                + '</div>')
    if note:
        out += f'<span style="display:block;margin:4px 0 0;padding:0 {A}px 0 {A}px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};word-break:keep-all;">{dk.esc(note)}</span>'
    return out


def _plain_sec(title, lead, rows, note="", lines=True):
    """카드 없이 구분선 구획 — 제목(아래 선) · 첫 문장 · 구분선 줄(이름 굵게 + 오른쪽 값 · 아래 작은 회색) · 작은 안내 (2026-11-07 사용자: `더 궁금한 것` 제목 삭제, 두 카드를 카드 말고 구분선으로)."""
    out = _plain_rows(lead, rows, note, lines)
    # 제목 줄 = 위 · 아래 구분선 사이 제목(21, 구획 제목 22 보다 1 작게) + 오른쪽 공식 접기 버튼, 누르면 내용 (2026-11-07 사용자). 위 선은 묶음(_fold_group)이 긋고 각 줄은 아래 선만
    return (f'<details data-acc="1" class="fc-fsec" style="margin:0;border-bottom:1px solid #E2E8F0;">'
            f'<summary style="list-style:none;cursor:pointer;display:flex;align-items:center;gap:0;padding:8px 0 8px {dk.ALIGN_PX}px;">'
            '<span aria-hidden="true" style="flex:none;width:3px;height:3px;border-radius:50%;background:#111;margin-right:8px;"></span>'
            f'<span class="fc-fsec-t" style="flex:1 1 auto;min-width:0;font-size:16px;line-height:26px;font-weight:400;color:#111;">{dk.esc(title)}</span>{dk.fold_btn()}</summary>'
            f'<div style="padding:4px 0 {16 - dk.VP}px;">{out}</div></details>')


# 접는 구획 제목 = `함께 보는 페이지` 제목과 같은 글씨(19 굵게 · 왼쪽 기준선 6) (2026-11-07 사용자, 옛 21)


def _reasons_card(fc):
    """무엇이 이유로 꼽혔나? — 자동 등록 때 모아 고정한 fc["reasons"] (forecast_register.reasons, 2026-11-11 사용자).
    기사 · 방송이 든 이유(이슈 건수 · 대표 기사) · 애널리스트 목표가 변경 · 우리 기록상 신호. 원인을 판단하지 않고 모은 것만 — 가이드라인 1절 4-2."""
    w = fc.get("reasons")
    if not w:
        return ""
    rows = []
    if w.get("issues"):
        rows.append(("기사가 든 이유", " · ".join(f"{k} {n}건" for k, n in w["issues"]),
                     f'{md(w["window"][0])} ~ {md(w["window"][1])} {"이 종목을 주로 다룬 같은 방향" if fc.get("target") == "stock" else "시장 · 업종"} 기사 {w.get("n", 0)}건 가운데'))
    if "good" in w or w.get("our_signals"):   # 갈래별 근거가 있는 등록 = 카드 없음 (2026-11-11 사용자: 중복을 지우니 안내 글뿐) — 큰 움직임 크기는 급락일 줄, 종목 링크는 `현재 증시는?`
        return ""
    side = False
    if not side:
        for h, day, src in w.get("heads") or []:
            rows.append((h, "", f"{md(day)} · {src}" if src else md(day)))
        a = w.get("analyst")
        if a:
            parts = ([f'목표가 내림 {a["down"]}곳'] if a.get("down") else []) + ([f'목표가 올림 {a["up"]}곳'] if a.get("up") else []) + ([f'의견 낮춤 {a["downgrade"]}곳'] if a.get("downgrade") else [])
            rows.append(("애널리스트", " · ".join(parts), "같은 기간 바뀐 것"))
    if w.get("signals"):
        rows.append(("우리 기록상", "", " · ".join(w["signals"])))
    if not rows:
        return ""
    note = ("기사 주제 · 우리 기록에서 모은 것입니다. 원인을 판단한 것은 아닙니다. 기사 · 애널리스트 줄은 전망 카드의 근거에 있습니다." if side
            else "기사 · 애널리스트 · 우리 기록에서 모은 것입니다. 원인을 판단한 것은 아닙니다.")
    body = _plain_rows("", rows, note=note)
    if fc.get("stock_page"):
        body += (f'<a href="{dk.esc(fc["stock_page"])}" style="display:block;margin:8px 0 0;padding:0 {dk.ALIGN_PX}px;font-size:{dk.TINY};line-height:{dk.LH_TINY};'
                 f'color:#333;text-decoration:underline;text-underline-offset:3px;">{dk.esc(fc["subject"])} 종목 페이지 ›</a>')
    return _fold_row("무엇이 이유로 꼽혔나?", body).replace('<details data-acc="1"', '<details data-acc="1" open', 1)   # 독자가 가장 먼저 묻는 것 — 펼친 채로


def _fold_row(title, html, label="", side=""):
    """`기록상 비슷한 때는?` 과 같은 접는 구분선 줄 — 안에 카드 html 그대로 (P418: 옛 `지금은?` 구획 제목 + `현재 증시 · 한국 보기` 버튼)."""
    return (f'<details data-acc="1" class="fc-fsec" style="margin:0;border-bottom:1px solid #E2E8F0;">'
            f'<summary style="list-style:none;cursor:pointer;display:flex;align-items:center;gap:0;padding:8px 0 8px {dk.ALIGN_PX}px;">'
            # 라벨이 있으면 점 대신 왼쪽에 라벨(특별한 줄 — `끊김`, P437), 없으면 3px 점
            + (f'<span style="flex:none;display:flex;margin-right:8px;">{label}</span>' if label else
               '<span aria-hidden="true" style="flex:none;width:3px;height:3px;border-radius:50%;background:#111;margin-right:8px;"></span>')
            + f'<span class="fc-fsec-t" style="flex:1 1 auto;min-width:0;font-size:16px;line-height:26px;font-weight:400;color:#111;">{dk.esc(title)}</span>'
            + (f'<span style="flex:none;margin-right:8px;font-size:13px;line-height:19px;color:{dk.SUB};white-space:nowrap;">{dk.esc(side)}</span>' if side else "")   # 접기 버튼 앞 작은 회색 (`11.10 종가`, 2026-11-11 사용자)
            + f'{dk.fold_btn()}</summary>'
            f'<div style="padding:4px 0 {16 - dk.VP}px;">{html}</div></details>')


FOLD_CSS = '<style>.fc-fsec[open]>summary .fc-fsec-t{font-weight:700 !important;}</style>'   # 접는 줄을 펼치면 제목 굵게 (P429, 2026-11-08 사용자)


def _fold_group(html):
    return f'{FOLD_CSS}<div style="margin:28px 0 24px;border-top:1px solid #E2E8F0;">{html}</div>' if html else ""


def operator_box(op):
    """운영자 확인용 상자 — 목업에서만 (2026-11-07 사용자: 80개 요인 중 무엇이 쓰였고 어떻게 판정됐는지 나 혼자 확인, 독자에게는 숨김).
    회색 바탕 · 작은 글씨 14px. 발행 렌더는 op=None 이라 그리지 않는다. 안에 쓰는 말은 내부 말(이슈 코드 · 범위 비율 · 규칙 버전) 그대로."""
    rows = "".join(f'<div style="display:flex;gap:10px;margin:0 0 3px;"><span style="flex:none;min-width:88px;font-weight:700;color:#475569;">{dk.esc(k)}</span>'
                   f'<span style="color:#334155;word-break:keep-all;">{dk.esc(v)}</span></div>' for k, v in op)
    return (f'<details data-op="1" class="fc-det" style="margin:0 0 16px;padding:0 12px;border:1px dashed #CBD5E1;border-radius:8px;background:#F1F5F9;font-size:14px;line-height:22px;">'
            f'<summary style="cursor:pointer;padding:10px 0;font-weight:700;color:#64748B;list-style:none;">운영자 확인용 — 블로그에는 나가지 않습니다 <span class="fc-chev">▾</span></summary>'
            f'<div style="padding:0 0 10px;">{rows}<button type="button" class="fc-fold" onclick="this.closest(\'details\').removeAttribute(\'open\')">접기</button></div></details>')


def _next_card(fc):
    """앞으로 볼 것은? — 위험은 주의사항처럼, 숫자 없이. 접어 둔다(2026-11-07 사용자)."""
    nx = fc["next"]
    L = fc.get("line", 3.0)
    rows = []
    for x in nx["lines"]:   # `이름 : 문장` → 이름 굵게 + 아래 문장 (답 칸 `지켜보는 중` 없음, 카드 없이 구분선)
        x = x if isinstance(x, str) else x[0]
        a, _, b = wordify(x, L).partition(" : ")
        rows.append((a, "", b) if b else (a, "", ""))
    html = _plain_sec(nx.get("title", "앞으로 볼 것은?"), wordify(nx["lead"], L), rows, wordify(nx.get("tail", ""), L), lines=False)   # 줄 사이 구분선 없음 (2026-11-07 사용자)
    return html.replace(f'font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};word-break:keep-all;">', f'font-size:{dk.NAME};line-height:{dk.LH_CARD};color:#333;word-break:keep-all;">')   # 여기 아래 줄은 본문 문장이라 작은 회색이 아니라 본문 글씨


def _event_chart(reg):
    """EH-2026-001 전망 1 만 — 선거 전후 하루 등락 막대(사건표 rows)."""
    rows = reg["event_table"]["rows"]
    num = lambda x: float(x.replace("−", "-")) if x else None   # noqa: E731
    groups = [(r[0][:5], [num(r[3]), num(r[1])]) for r in rows]
    chart = qc.chart_card("선거 전후 하루 등락 (%)", groups, [qc.sign_bg, qc.gray], [qc.sign_fg, qc.note_fg],
                          [("반도체", qc.sign_bg(-1)), ("S&P 500", qc.GRAY_BAR)], fmt=lambda v: f"{v:+.1f}".replace("-", "−"))
    sox = {r[0][:5]: r[3] for r in rows}
    c1 = qc.question_card("선거 전후 반도체는?", f"11.05 {sox['11.05']}%", "negative", dk.DOWN, [
        ("SENT1", "plain"), (f'<span data-end-chart="1" style="display:block;margin:0 0 -{END_PULL}px;">{chart}</span>', "html")], fold=True, opened=False)
    return c1.replace("SENT1", num_html("선거 결과가 나온 다음 날(11.05) 반도체는 하루 -12.25% 빠져 1994년 이후 두 번째로 큰 하락이었습니다. "
                                        "선거 전인 10.30 에도 이미 -7.2% 빠졌습니다."))


PLUS_BOX, PLUS_RADIUS, PLUS_ICON = 22, 6, 10   # 지난 날 펼침 + 아이콘: 공식 접기 버튼(네모 31 · 화살표 18)보다 작게 (2026-11-07 사용자)
PLUS_CSS = ('<style>.fc-day>summary{list-style:none;cursor:pointer;}.fc-day>summary::-webkit-details-marker{display:none;}'
            '.fc-day[open]>summary .fc-plus-v{display:none;}'
            '.fc-more>summary::-webkit-details-marker{display:none;}.fc-more[open]>summary{display:none;}</style>')   # 지난 경과 더 보기 = 펼치면 버튼을 숨기고 타임라인이 이어진다 (P418)   # 펼치면 세로획을 숨겨 − 로. 테마 붙여넣기 없이 되도록 본문 안 style (render_html 여러 그래프와 같은 방식)


def _plus(bd):
    return (f'<span aria-hidden="true" style="display:inline-flex;flex:none;align-items:center;justify-content:center;width:{PLUS_BOX}px;height:{PLUS_BOX}px;'
            f'box-sizing:border-box;border:1px solid {bd};border-radius:{PLUS_RADIUS}px;background:#fff;color:#111;align-self:center;">'
            f'<svg viewBox="0 0 12 12" width="{PLUS_ICON}" height="{PLUS_ICON}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">'
            f'<path d="M2 6h8"/><path class="fc-plus-v" d="M6 2v8"/></svg></span>')


def _day_cols(e, unit="%", subj=""):
    """타임라인 머리 줄 네 칸 = 날짜 · 국면 · 기준일부터 움직임(▲ · ▼, P422) — 버튼은 _waiting 이 넷째 칸에.
    등록 날 = `개시`, `개시` · `지켜보는 중` 은 검정 보통 굵기, 그 밖 국면은 방향 색 굵게 (P426, 2026-11-08 사용자)."""
    start = e.get("key") == "start"
    label = "개시" if start else e["label"]
    if subj and label.startswith(subj + " "):   # 페이지가 이미 그 대상 이야기라 국면에서 대상 이름은 뺀다 — `엔비디아 상승 우세` → `상승 우세` (P440, 2026-11-08 사용자)
        label = label[len(subj) + 1:]
    calm = start or label == "지켜보는 중"
    r = None if start else e.get("shown", e.get("rel"))
    val = (dk.emph_tri(dk.arrow(r, 1, unit).replace("font-weight:700;", "font-weight:400;"), TL_TRI) if r is not None and round(r, 1) != 0 else "")   # ▲ · ▼ 16 → 14 (10% 작게, 정수, P497)
    ink = dk.VIOLET if e.get("key") in RESULT else ("#111" if calm else INK[e["dir"]])   # 판정(맞음 · 틀림 · 제자리 · 보류 · 무효) = 보라 (P469, 2026-11-08 사용자) — 방향 색 X
    lab = f'<span style="color:{ink};{"" if e.get("key") in RESULT else "font-weight:400;"}white-space:nowrap;">{dk.esc(label)}</span>'   # `○○ 조짐` 도 보통 굵기, 판정만 굵게 (P483, 2026-11-11 사용자)
    # 옛 `(세부 전망으로 이어감 ›)` 괄호 링크(P453)는 뺐다 — 바로 위 끝 줄 `세부 전망으로 이어집니다 ›`(P465)와 겹쳐서 (P466, 2026-11-08 사용자)
    return (f'<span style="color:#111;white-space:nowrap;">{dk.esc(md(e["day"]))}</span>',
            lab,
            val), (md(e["day"]), label, (f'▲ {abs(r):.1f}{unit}' if val else ""))


def _aligned(x, unit, subj=""):
    """세로선을 맞추는 줄 = 증감 값이 있는 `지켜보는 중` 줄 · `○○ 우세` 줄 — 같은 국면 말끼리 한 묶음 (P427 · P440, 2026-11-08 사용자).
    개시 · 맞음 · 틀림 · 값 없는 줄은 맞추지 않는다. 돌려주는 값 = 묶음 이름(국면 말) 또는 None."""
    if x.get("key") == "start":
        return None
    _, (d, label, v) = _day_cols(x, unit, subj)
    return label if v and (label == "지켜보는 중" or label.endswith(LEAN)) else None


_TL_EM = {" ": 0.262, ".": 0.278, "%": 0.906, "p": 0.591, "▲": 0.694, "▼": 0.694}   # Noto Sans KR 16px 실측(Chrome, 2026-11-11) / 16


def _tl_w(t, px=16):
    """국면 칸 폭 = 글자 폭 실측 비율 합 + 2 (P492 · P493: 옛 _est_w 는 한글 1em · 빈칸 .55em 로 잡아 긴 국면 말일수록 칸이 넓었다 — `하락 지속 조짐이 보임` 170 vs 실제 137).
    한글 .865em · 숫자 .445em. 칸 사이 8 과 합쳐 국면 ~ 값 간격 = 약 10 (옛 약 23 의 절반)."""
    em = sum(0.865 if ord(c) > 0x2E80 else 0.445 if c.isdigit() else _TL_EM.get(c, 0.55) for c in str(t))
    return int(em * px + 0.999) + 2


def _col_widths(days, unit, subj=""):
    """칸 폭 — 날짜 칸은 맞추는 줄 전체에서, 국면 · 움직임 칸은 같은 국면 말 묶음 안에서 가장 긴 글. 정수 px.
    → {묶음 이름: (날짜, 국면, 움직임)}"""
    rows = [(g, _day_cols(x, unit, subj)[1]) for x in days if (g := _aligned(x, unit, subj))]
    w = lambda ts, i: max([int(qc._est_w(t[i], 16)) if i != 1 else _tl_w(t[i]) for t in ts] + [0])   # noqa: E731  — 추정이 실제보다 2~4px 넓어 여유를 따로 두지 않는다(여유를 두면 이어 쓰는 줄보다 간격이 벌어짐, 2026-11-08 캡처)
    dw = w([t for _, t in rows], 0)
    out = {}
    for g in {g for g, _ in rows}:
        ts = [t for gg, t in rows if gg == g]
        out[g] = (dw, w(ts, 1), w(ts, 2) + 2)
    return out


def _day_text(e):
    o = e.get("overlap")
    ov = (f'<span style="display:block;margin-top:4px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};word-break:keep-all;">'
          f'겹친 사건 : <b style="color:{dk.VIOLET};">{dk.esc(_re.sub(r"(?<! )[(]", " (", o["event"]))}</b>'   # 사건 이름만 보라 굵게 (2026-11-08 사용자: 겹침은 중요하니 겹친 사건만 보라)
          + (" · 세부 전망으로 따로 적었습니다" if o.get("slug") else "") + '</span>') if o else ""   # P468 — 셋째 겹침부터는 따로 안 적으니(SUB_MAX) 꼬리 말 없음
    return (f'<span style="display:block;margin-top:2px;font-size:{dk.NAME};line-height:{dk.LH_CARD};color:#333;word-break:keep-all;">{num_html(wordify(e["text"]))}</span>'
            + ov + (f'<span style="display:block;margin-top:4px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};word-break:keep-all;">오늘 시장 : {dk.esc(wordify(e["today"]))}</span>' if e.get("today") else ""))


PAST_SHOWN = 5   # 지난 날 줄은 최근 5개까지 바로, 그 앞은 `지난 경과 n개 더 보기` 안에


def _result_item(fc):
    """날짜 목록 맨 끝 `결과` — 아직 결과 전(값 '결과 전')이면 없음 (2026-11-07 사용자: 결과 전 표시는 필요 없는 정보)."""
    last = fc["dates"][-1] if len(fc["dates"]) > 2 else None
    return last if last and last[0] == "결과" and last[1] != "결과 전" else None


def _date_row(fc, out=False):
    """맨 위 날짜 줄 = 결과(사건 전, P456 `발표` 삭제) / 급락일 · 급등일(충격 뒤) — 두 갈래 카드 위, 왼쪽 끝선, 등록 증명만 오른쪽 끝 (2026-11-07 사용자).
    옛 이름 `사건` · `선거` 는 독자가 알고 싶은 '언제 결과가 나오나' 를 말하지 않아 `결과 발표` 로 (Claude 결정, 확인일 · 일정 · 이벤트보다 뜻이 바로 읽힌다)."""
    items = [list(x) for x in fc["dates"][:2]]
    if fc["kind"] == "pre":   # 결과 날짜 = `사건` 칸 — 선반영 · D-day 전망은 둘째 칸이 `감지` 라 이름으로 찾는다 (P460 점검에서 찾음)
        ev = next((list(x) for x in fc["dates"] if x[0] in ("사건", "선거", "결과 발표")), None)
        if ev:
            items = [items[0], ev]
    if len(items) > 1:
        if fc["kind"] == "pre":
            items[1][0] = "결과"   # `발표` 글자 삭제 (P456, 2026-11-08 사용자)
            m = _re.match(r"^\d{2}\.\d{2}(?:\s*~\s*\d{2}\.\d{2})?", str(items[1][1]))
            if m:   # 날짜만 — `01.26~01.28 빅테크 실적 주간 (4건)` 의 사건 이름은 뺀다 (2026-11-08 사용자: 결과 날짜만 오른쪽 정렬)
                items[1][1] = m.group(0).replace(" ", "")
        elif fc.get("gap") is not None:
            items[1][0] = SHOCK[1 if fc["gap"] > 0 else -1] + "일"
            m = _re.match(r"^\d{2}\.\d{2}", str(items[1][1]))
            if m:   # 날짜 줄은 날짜만 — 사건 설명(`유예 철회 (같은 사건 2회차)`)은 번복 · 겹침 카드에 (P443)
                items[1][1] = m.group(0)
    # `등록 증명` 링크 삭제 (2026-11-09 사용자: 독자에게 과한 정보 · 일반 독자는 GitHub 를 모른다). 증명 파일(gh-pages proof/) 커밋은 내부 기록으로 그대로 둔다
    proof = ""
    items = items[1:]   # `게시` 날짜는 빼고 결과 발표(충격 뒤 = 급락일 · 급등일)만 — 게시일은 타임라인 맨 아래 `개시` 줄에 있다 (P455, 2026-11-08 사용자)
    # 질문 제목 줄 오른쪽 끝 (P455) — 등록 증명은 그 아래
    return (f'<span style="display:flex;flex:none;flex-direction:column;align-items:flex-end;font-size:{dk.TINY};font-weight:400;color:{dk.SUB};">'
            # 결과 날짜 = 늘 검정 (P471, 옛 P413 결과 뒤 보라는 없앰) — 글자 `결과 :` 는 회색
            + "".join(f'<span style="white-space:nowrap;">{dk.esc(k)} : <span style="color:#111;">{dk.esc(wordify(v))}</span>{_shock_size(fc) if fc["kind"] != "pre" else ""}</span>' for k, v in items)
            + (f'<span>{proof}</span>' if proof else "") + "</span>")


def _shock_size(fc):
    """급락일 · 급등일 뒤 = 그날 움직임(증감 색 ▲ · ▼) · 평소의 몇 배 (2026-11-11 사용자 — 옛 `무엇이 이유로 꼽혔나?` 의 `우리 기록상` 첫 줄)."""
    g, z = fc.get("gap"), fc.get("z")
    if g is None:
        return ""
    col = dk.UP if g > 0 else dk.DOWN
    out = f' · <span style="color:{col};">{"▲" if g > 0 else "▼"} {abs(g):.1f}{dk.esc(fc.get("unit", "%"))}</span>'   # 굵게 빼기 (P495)
    return out + (f' · 평소의 <span style="color:#111;">{abs(z):.1f}배</span>' if z else "")


def quote_of(closes):
    """{날짜: 종가} → {"day", "close", "chg"(전날 대비 %)} — 현재 증시는? 종목 줄. 둘 미만이면 None."""
    ds = sorted(d for d, v in (closes or {}).items() if v)
    if len(ds) < 2:
        return None
    c, p = closes[ds[-1]], closes[ds[-2]]
    return {"day": ds[-1], "close": round(float(c), 2), "chg": round((c / p - 1) * 100, 2)}


def _stock_now(fc, st):
    """현재 증시는? 맨 위 종목 줄 (종목 전망만) = 한 줄 [로고 · 종목명 · 티커 · 종가 · 전날 대비 ……… ›], 줄 전체가 종목 페이지 링크 (2026-11-11 사용자 — 옛 `종목 바로가기` 버튼 삭제)."""
    if not is_stock_fc(fc):
        return ""
    sym = (fc.get("series") or {}).get("sub", "")
    q = st.get("quote") or {}
    price = ""
    if q:
        col = dk.UP if q["chg"] > 0 else dk.DOWN if q["chg"] < 0 else "#111"
        tri = "▲ " if q["chg"] > 0 else "▼ " if q["chg"] < 0 else ""
        price = (f'<b style="flex:none;color:#111;">${q["close"]:,.2f}</b>'
                 f'<span style="flex:none;color:{col};font-weight:600;">{tri}{abs(q["chg"]):.2f}%</span>')
    inner = (f'<span style="flex:none;display:flex;">{_logo_for(sym, fc.get("subject", ""), 22).replace("margin-right:6px;", "")}</span>'
             f'<b style="flex:none;color:#111;">{dk.esc(fc.get("subject", ""))}</b>'
             f'<span style="flex:none;font-size:13px;line-height:19px;color:{dk.SUB};">{dk.esc(sym)}</span>{price}'
             f'<span style="flex:1 1 auto;"></span>'
             f'<span aria-hidden="true" style="flex:none;display:inline-flex;transform:rotate(-90deg);color:#333;">{CHEV14}</span>')
    style = (f'display:flex;align-items:center;gap:8px;margin:4px 0 12px;padding:0 {dk.ALIGN_PX}px;font-size:{dk.NAME};line-height:{dk.LH_CARD};'
             f'color:#111;text-decoration:none;white-space:nowrap;overflow:hidden;')
    if fc.get("stock_page"):
        return f'<a data-stock-now="1" href="{dk.esc(fc["stock_page"])}" aria-label="{dk.esc(fc.get("subject", ""))} 종목 페이지" style="{style}">{inner}</a>'
    return f'<div data-stock-now="1" style="{style}">{inner.rsplit("<span aria-hidden", 1)[0]}</div>'


def _close_day(st):
    """현재 증시는? 접기 버튼 앞 `11.10 종가` — 시세 · 비교 그래프의 마지막 날."""
    d = (st.get("quote") or {}).get("day") or ((st.get("compare") or {}).get("days") or [None])[-1]
    return f"{md(d)} 종가" if d else ""


def compare_lines(fc):
    """비교 그래프 계열 [(기호, 이름)] — 종목 전망 = 종목 · 소속 업종 · S&P 500, 업종 전망 = 업종 · S&P 500, S&P 500 자체 = 없음."""
    sr = fc.get("series") or {}
    sub, mkt = sr.get("sub"), sr.get("mkt")
    if not sub or not mkt:
        return []
    out = [(sub, fc.get("subject", sub)), (mkt, (fc.get("cmp") or "").removesuffix("보다") or mkt)]
    if mkt != "^GSPC":
        out.append(("^GSPC", "S&P 500"))
    return out


def compare_of(px, base_day, lines):
    """{기호: {날짜: 종가}} → {"base", "days", "lines": [[이름, [기준일 대비 %]]]} — 기준일(충격 전날 종가) = 0. 휴장이면 그 전 거래일."""
    if not lines or not px.get(lines[0][0]):
        return None
    main = px[lines[0][0]]
    have = sorted(d for d in main if d <= base_day)
    if not have:
        return None
    b = have[-1]
    days = sorted(d for d in main if d >= b)
    out = []
    for sym, name in lines:
        c = px.get(sym) or {}
        if b not in c:
            continue
        out.append([name, [round((c[d] / c[b] - 1) * 100, 2) if d in c else None for d in days]])
    return {"base": b, "days": days, "lines": out} if len(out) >= 2 and len(days) >= 2 else None


CMP_COLORS = (dk.CHART_MAIN, "#5FBFAF")   # 주인공 주황 · 업종 청록 — S&P 500 은 비교 대상 회색 점선 (dk.CHART_CMP)


def _compare_chart(fc, st):
    """현재 증시는? 비교 그래프 (2026-11-11 사용자: 메타 · S&P 500 · 업종 평균을 겹친 선, 일자순) — 기준일 종가 대비 %, 숫자는 계열마다 끝 값만."""
    cp = st.get("compare")
    if not cp:
        return ""
    days, n = cp["days"], len(cp["days"])
    at = {0, n // 2, n - 1}
    labels = [md(d) if i in at else "" for i, d in enumerate(days)]
    series = [(nm, vals, CMP_COLORS[i] if i < 2 and nm != "S&P 500" else dk.CHART_CMP, "solid" if i < 2 and nm != "S&P 500" else "dash")
              for i, (nm, vals) in enumerate(cp["lines"])]
    gr = dk.trend_card(f'{md(cp["base"])} 종가 대비 (%)', labels, series, lambda v: f"{v:+.1f}%".replace("-", "−"), ends_only=True)
    if not gr:
        return ""
    gr = gr.replace(f"margin:0 {dk.CHART_CARD_X}px;", "margin:0;", 1)
    return f'<div data-compare="1" style="margin:4px 0 16px;padding:0 0 0 {dk.ALIGN_PX}px;">{gr}</div>'


def _priced(fc):
    """선반영 조건 — 감지일이 있거나(먼저 움직임 감지) 시장 예상 한쪽이 70% 이상 (기획 8절 선반영 규칙)."""
    mp = (fc.get("market_prob") or {}).get("probs") or []
    return bool(fc.get("detect_day")) or (bool(mp) and max(mp) >= 70)


def _market_line(fc):   # 화면에서 뺌 (2026-11-08 사용자: `시장은 … 쪽을 조금 더 보고 있습니다` 삭제 — 시장 쪽은 갈래 카드 `- 시장예상` 이 보인다). 다시 쓸 때만 부른다
    """결과 전 시장 예상 한 줄 — 날짜 줄 아래 (2026-11-07 사용자: 결과 전에 필요한 건 지금 무엇을 정하는가에 닿는 정보). 확률 숫자는 말로."""
    mp = (fc.get("market_prob") or {}).get("probs")
    if fc["kind"] != "pre" or not mp or not fc.get("outcomes") or not _priced(fc):   # 시장 예상 줄은 선반영 근거로만 (2026-11-08 사용자)
        return ""
    p = mp[0]
    text = (f'시장은 ‘{fc["outcomes"][0]}’ 쪽을 {prob_word(p)} 보고 있습니다.' if p >= 55 else
            f'시장은 ‘{fc["outcomes"][1]}’ 쪽을 {prob_word(100 - p)} 보고 있습니다.' if p <= 45 else "시장 예상은 반반입니다.")
    return f'<span style="display:block;margin:-4px 0 8px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:#333;word-break:keep-all;">{dk.esc(text)}</span>'


CLOCK = ('<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true" '
         'style="flex:none;align-self:center;"><circle cx="8" cy="8" r="6.5"/><path d="M8 4.5V8l2.5 1.5"/></svg>')


TL_LINE = "#CBD5E1"   # 타임라인 세로 점선 = 비교 · 기준선 회색 (가이드 8절 ③)
TL_RAIL = 20          # 왼쪽 레일 폭 = 맨 위 시계 아이콘 20 (2026-11-11 — 옛 16)
TL_WHY_INK = dk.SUB   # 타임라인 근거 줄 = 회색(세 톤 셋째 #6B7280, 2026-11-11 사용자: "논의중 회색 글씨 컬러로") — 옛 시험 #4B5563
_TL_WHY_INK_OLD = "#4B5563"   # 타임라인 근거 줄 — 시험: #333 이 검정과 거의 같아 보여 이 줄만 #4B5563 (2026-11-11 사용자 "이 줄만 먼저"), 연한 검정 톤 결정 전
TL_TRI = 14           # 타임라인 증감 ▲ · ▼ 크기 (P497)
TL_DOT = 8            # 지난 날 점
TL_DAY_GAP = 15       # 날짜 줄 묶음 사이 더 띄움 (2026-11-11 사용자)


def _tl_row(node, node_h, top_pad, content, first, last):
    """타임라인 한 줄 = 왼쪽 레일(위 점선 · 마디 · 아래 점선) + 오른쪽 내용. 레일은 내용 높이만큼 늘어나 다음 줄 점선과 이어진다."""
    seg = f"width:0;border-left:1px dashed {TL_LINE};"
    rail = (f'<span aria-hidden="true" style="display:flex;flex-direction:column;align-items:center;flex:none;width:{TL_RAIL}px;">'
            f'<span style="{seg if not first else "width:0;"}height:{top_pad}px;flex:none;"></span>'
            f'<span style="display:flex;align-items:center;justify-content:center;height:{node_h}px;flex:none;">{node}</span>'
            f'<span style="{seg if not last else "width:0;"}flex:1;min-height:0;"></span></span>')
    return f'<div style="display:flex;align-items:stretch;gap:8px;">{rail}<div style="flex:1;min-width:0;">{content}</div></div>'


END_STOP = ('<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true" style="flex:none;">'
            '<circle cx="8" cy="8" r="6.5"/><rect x="5.5" y="5.5" width="5" height="5" rx="1" fill="currentColor" stroke="none"/></svg>')   # 끝 줄 마디 — 원 안 네모(멈춤), 시계와 같은 16 · 같은 회색 (P465)
END_GO = ('<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex:none;">'
          '<circle cx="8" cy="8" r="6.5"/><path d="M5 8h6M8.5 5.5 11 8l-2.5 2.5"/></svg>')   # 원 안 오른쪽 화살표(이어짐)


def _side_names(fc):
    """{+1: (갈래 이름, `반등`), −1: (…, `지속`)} — 갈래 dir 로 (급락 뒤 반등 = +1, 급등 뒤 조정 = −1)."""
    out = {}
    for sc in (fc or {}).get("scenarios") or []:
        if sc.get("dir") in (1, -1):
            out[sc["dir"]] = (sc["name"], side_word(sc) or ("전망A" if _tag_kind(sc) == "up" else "전망B"))   # 사건 전 전망 = 갈래 이름표 `전망A` · `전망B`(조건 문장은 라벨로 길다, 2026-11-11 경우의 수 목업에서 찾음)   # `반등` · `지속` (2026-11-11 사용자: `쪽` 삭제)
    return out


def drop_subj(t, subj):
    """타임라인 근거 줄 · 그날 팝업에서 문장 맨 앞 대상 이름 빼기 — 한 페이지가 그 대상 이야기라 `메타, …` 가 줄마다 반복된다 (2026-11-11 사용자).
    `메타, ` · `메타 ` · `메타는/가/의 ` 만 뺀다. 가운데 든 이름(`유럽연합, 메타에 …`) · 붙은 말(`메타와`) · 뺀 뒤 빈 문장은 그대로."""
    if subj and t and t.startswith(subj):
        m = _re.match(r"(?:,\s*|(?:은|는|이|가|의)\s+|\s+)", t[len(subj):])
        rest = t[len(subj) + m.end():] if m else ""
        if rest.strip():
            return rest
    return t


def _side_pill(word, kind="flat"):
    """타임라인 `반등` · `지속` 라벨 = 그 갈래 `전망A` · `전망B` 이름표와 같은 색(TS.box, 2026-11-11 사용자 — 옛 회색 dk.pill)."""
    pk = {"up": "positive", "down": "negative"}.get(kind, "neutral")   # 뉴스 기사 긍정 · 부정 라벨 모양 · 크기 (P514, 2026-11-11 사용자: TS.box 는 크다)
    return dk.pill(word, pk, bare=True).replace("vertical-align:middle;", f"vertical-align:middle;flex:none;margin-right:{dk.PILL_GAP}px;", 1)


def day_why_html(x, fc):
    """타임라인 그날 줄 아래 근거 한 줄 + 그날 더보기 팝업 (2026-11-11 사용자).
    기운 쪽(우세 · 실현)이 있는 날 = 그 쪽 근거 맨 위 한 줄, `지켜보는 중` 날 = 그날 근거 맨 위 한 줄 앞에 `반등` · `지속` 라벨. 그날 소식이 없으면 없음.
    팝업 = 갈래별 그날 기사(날짜 · 매체 · 논의중) · 방향이 안 정해진 일 · 우리 신호 바뀐 것(전날 → 그날)."""
    subj = (fc or {}).get("subject", "")
    w = {k: ([dict(r, t=drop_subj(r.get("t", ""), subj)) for r in v] if k in ("good", "bad", "open") else v) for k, v in (x.get("why") or {}).items()}
    names = _side_names(fc)
    kinds = {sc["dir"]: _tag_kind(sc) for sc in (fc or {}).get("scenarios") or [] if sc.get("dir") in (1, -1)}
    key_of = {1: "good", -1: "bad"}
    groups = [(d, w.get(key_of[d]) or []) for d in (1, -1) if d in names]
    total = sum(len(rs) for _, rs in groups) + len(w.get("open") or []) + len(w.get("changes") or [])
    if not total:
        return ""
    lean = x.get("dir") if x.get("key") != "watch" else 0
    pick, label = None, ""
    if lean in names and w.get(key_of[lean]):
        pick = w[key_of[lean]][0]
    else:
        cands = [(d, rs) for d, rs in groups if rs]
        if cands:   # 그날 건수가 많은 쪽 → 같으면 대상에 가까운 줄 → 더 최근 기사 (늘 반등 쪽이 먼저 뽑히던 것, 2026-11-11 가상 목업에서 찾음)
            d, rs = max(cands, key=lambda c: (len(c[1]), c[1][0].get("lv", 0), c[1][0].get("day", "")))
            pick, label = rs[0], _side_pill(names[d][1], kinds.get(d, "flat"))
    pid = dk.news_pop_id("whyday", f'{fc.get("slug")}-{x["day"]}')
    pop = ""
    for d, rs in groups:
        if rs:
            lab = _side_pill(names[d][1], kinds.get(d, "flat")).replace(f"margin-right:{dk.PILL_GAP}px;", "", 1)
            pop += "".join(_art_li(r, label=lab) for r in rs)   # 줄마다 왼쪽 라벨 · 오른쪽 기사 (P515 — 옛 P507 묶음 제목 라벨)
    if w.get("open"):
        pop += "".join(_art_li(r, talk=False, label=open_pill()) for r in w["open"])
    for hz, span in WHY_HZ:
        cs = [c for c in w.get("changes") or [] if c["hz"] == hz]
        if cs:
            pop += _pop_sub(f'{CAL_ICON}{SIG_NAME} {hz} <span style="font-weight:400;color:{dk.SUB};">· 바뀐 것</span>')
            pop += "".join(_pop_li(_sig_html(c["name"], f'{c["from"]} → {c["to"]}' if c.get("from") else c["to"]), html=True) for c in cs)
    body = f'<div data-news-pop-body="{dk.esc(pid)}" data-news-pop-title="{dk.esc(md(x["day"]) + " " + WHY_WORD)}" hidden>{_pop_first(pop)}</div>'
    if pick:
        line = (f'<span style="display:flex;align-items:center;min-width:0;flex:0 1 auto;">{label}{_one_line(dk.esc(pick["t"]), grow=False, color=TL_WHY_INK)}'
                + (_talk_mark().replace(f"margin:0 {dk.PILL_GAP}px;", f"margin:0 0 0 {dk.PILL_GAP}px;flex:none;", 1) if pick.get("stage") == "talk" else "") + "</span>")
    elif w.get("open"):   # 갈래 기사 없이 향방미정만 있는 날 — 그 줄 + `향방미정` 라벨 (옛: 빈 `: ›` 줄, 2026-11-11 경우의 수 목업에서 찾음)
        o = w["open"][0]
        line = (f'<span style="display:flex;align-items:center;min-width:0;flex:0 1 auto;">{open_pill().replace("flex:none;", f"flex:none;margin-right:{dk.PILL_GAP}px;", 1)}'
                f'{_one_line(dk.esc(o["t"]), grow=False, color=TL_WHY_INK)}</span>')
    else:   # 기사 없이 신호만 바뀐 날
        c = (w.get("changes") or [{}])[0]
        txt = f'{c.get("name", "")} : {c["from"]} → {c.get("to", "")}' if c.get("from") else f'{c.get("name", "")} : {c.get("to", "")}'
        line = f'<span style="display:flex;align-items:center;min-width:0;flex:0 1 auto;">{_one_line(dk.esc(txt), grow=False, color=TL_WHY_INK)}</span>'
    # 줄 전체 = 팝업 버튼, 끝에 › 만 (2026-11-11 사용자: `근거 n건` · 더보기 버튼 삭제, 문장을 누르면 팝업)
    chev = f'<span aria-hidden="true" style="flex:none;display:inline-flex;transform:rotate(-90deg);color:#333;">{CHEV14}</span>'
    return (f'<div data-why-day="1" data-news-pop="{dk.esc(pid)}" role="button" tabindex="0" style="display:flex;align-items:center;gap:4px;margin:-4px 0 {12 - dk.VP}px;cursor:pointer;">'
            f'{line}{chev}{body}</div>')


def why_note_html(fc):
    """근거 안내 — 페이지에 한 번, 접는 줄 묶음(`현재 증시는?`) 아래 (2026-11-11 사용자: 팝업마다 반복하지 않기 → 현재 증시 아래로). 느낌표 아이콘 + 가장 작은 글씨 13/19, 아이콘 = 첫 줄 가운데."""
    w = (fc or {}).get("reasons") or {}
    if "good" not in w and not w.get("our_signals"):
        return ""
    return (f'<div data-why-note="1" style="display:flex;align-items:flex-start;gap:4px;margin:12px 0 0;padding:0 {dk.ALIGN_PX}px;font-size:13px;line-height:19px;color:{dk.SUB};word-break:keep-all;">'
            f'<span style="flex:none;display:flex;align-items:center;height:19px;">{EXCL_ICON}</span><span>{WHY_NOTE}</span></div>')


def _waiting(log, unit="%", subj="", fc=None):
    """카드 아래 세로 타임라인 — 결과 전 · 결과 뒤 같은 모양 (P409 · P418, 2026-11-08 사용자: 아래 내용은 A 1번 화면과 통일).
    오늘 = 시계 아이콘 + 날짜 · 국면 · ▲ 움직임 + (펼쳐 둔 채) 문장 · 오늘 나온 것, + 버튼으로 접고 펼침(P422). 지난 날 = 점 + 같은 머리 줄(+ 펼침).
    마디 사이는 세로 점선. 지난 날이 많으면 최근 PAST_SHOWN 개 + 맨 아래 `지난 경과 n개 더 보기`(펼치면 같은 타임라인으로 이어짐)."""
    days = list(reversed(log))
    e = days[0]
    lh = int(dk.LH_CARD.rstrip("px"))
    cws = _col_widths(days, unit, subj)

    def head(x):   # 맞추는 줄(값 있는 지켜보는 중 · 우세) = 네 칸 격자, 나머지 = 글 길이대로 이어 쓰기 (P427 · P440)
        a, b, c = _day_cols(x, unit, subj)[0]
        # 겹친 사건 날 = 값 뒤(+ 버튼 칸) 회색 `겹침` 이름표 — 세로 기준선(날짜 · 국면 · 값)은 그대로 (P468, 2026-11-08 사용자: 타임라인에도 겹침 표시)
        # → 날짜 뒤 · 국면 앞 노랑 `겹침` 라벨 (2026-11-08 사용자). 라벨이 든 줄은 네 칸 격자 대신 이어 쓰기(국면 칸 폭을 밀어내지 않게)
        tag = overlap_pill() if x.get("overlap") else ""
        tail = _plus("#E2E8F0")
        if tag:
            return (f'<summary style="display:flex;align-items:center;gap:8px;padding:{{pad}}px 0;font-size:{dk.NAME};line-height:{dk.LH_CARD};font-weight:700;">'
                    f'{a}{tag}{b}{c}{tail}</summary>')
        g = _aligned(x, unit, subj)
        if g:
            cw = cws[g]
            return (f'<summary style="display:grid;grid-template-columns:{cw[0]}px {cw[1]}px {cw[2]}px auto;column-gap:8px;align-items:center;'
                    f'padding:{{pad}}px 0;font-size:{dk.NAME};line-height:{dk.LH_CARD};font-weight:700;">{a}{b}<span>{c}</span>{tail}</summary>')
        return (f'<summary style="display:flex;align-items:center;gap:8px;padding:{{pad}}px 0;font-size:{dk.NAME};line-height:{dk.LH_CARD};font-weight:700;">'
                f'{a}{b}{c}{tail}</summary>')
    clock = f'<span style="display:block;width:{TL_DOT}px;height:{TL_DOT}px;box-sizing:border-box;border:2px solid {TL_LINE};border-radius:50%;background:#fff;"></span>'   # 오늘 줄 마디 = 지난 날과 같은 동그라미 (2026-11-11 사용자: 시계는 Timeline 제목 앞으로)
    # 아래 여백 = 지난 날 줄과 같은 10 (접혀도 펼쳐도) — 옛 4px 띄움은 접으면 다음 줄과 붙어 좁았다 (P436, 2026-11-08 사용자)
    past = days[1:]
    gap = f'<div style="height:{TL_DAY_GAP}px;"></div>'   # 날짜와 날짜 사이 +10 (2026-11-11 사용자) — 마지막 줄 아래엔 없음
    today = (f'<details class="fc-day" open style="margin:0;padding:0 0 {12 - dk.VP}px;">' + head(e).replace("{pad}", "0") + f'{_day_text(e)}</details>') + (day_why_html(e, fc) if fc else "") + (gap if past else "")
    out = PLUS_CSS + '<div style="margin:0 0 24px;">' + (timeline_lead(fc, log) if fc else "")
    lead = bool(fc)
    end = e.get("key") in RESULT   # 판정이 난 전망 — 시계 줄 위에 끝 줄 하나 (P465, 2026-11-08 사용자): 세부 전망이 이어받으면 `세부 전망으로 이어집니다 ›`, 아니면 `전망이 종료되었습니다`
    if end:
        f = e.get("follow")
        if f and f.get("slug"):
            node, txt = END_GO, (f'<a href="{page_url(f["slug"])}" style="display:inline-flex;align-items:center;gap:2px;color:#111;text-decoration:none;">세부 전망으로 이어집니다'
                                 f'<span style="display:inline-flex;transform:rotate(-90deg);">{dk.ACC_CHEV.replace("acc-chev", "fc-right")}</span></a>')
        else:
            node, txt = END_STOP, "전망이 종료되었습니다"
        out += _tl_row(f'<span style="display:inline-flex;color:{dk.SUB};">{node}</span>', lh, 0,
                       f'<div style="padding:0 0 {12 - dk.VP}px;font-size:{dk.NAME};line-height:{dk.LH_CARD};font-weight:700;color:#111;">{txt}</div>', not lead, False)
    out += _tl_row(clock, lh, 0, today, not end and not lead, False)   # 오늘 줄은 지난 날이 없어도 문장 끝까지 점선을 내린다
    if past:
        shown = past if len(past) <= PAST_SHOWN + 2 else past[:PAST_SHOWN]   # 1~2개 숨기려고 버튼을 두지 않는다
        rest = past[len(shown):]
        dot = f'<span style="display:block;width:{TL_DOT}px;height:{TL_DOT}px;box-sizing:border-box;border:2px solid {TL_LINE};border-radius:50%;background:#fff;"></span>'

        def row(x, last):
            fold = (f'<details class="fc-day" style="margin:0;">' + head(x).replace("{pad}", str(12 - dk.VP)) +
                    f'<div style="padding:0 0 {12 - dk.VP}px;margin-top:-4px;">{_day_text(x)}</div></details>') + (day_why_html(x, fc) if fc else "") + ("" if last else gap)   # 근거 줄 = 접어도 보인다
            return _tl_row(dot, lh, 12 - dk.VP, fold, False, last)
        out += "".join(row(x, i == len(shown) - 1 and not rest) for i, x in enumerate(shown))
        if rest:
            label = f"지난 경과 {len(rest)}개 더 보기"
            btn = (f"display:inline-flex;align-items:center;gap:4px;padding:6px 12px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;"
                   f"font:inherit;font-size:{dk.TINY};line-height:{dk.LH_TINY};font-weight:600;color:#333;cursor:pointer;")
            up = f'<span style="display:inline-flex;transform:rotate(180deg);">{dk.ACC_CHEV.replace("acc-chev", "fc-up")}</span>'
            # 펼치면 맨 아래 `접기` 버튼 — 펼친 뒤 다시 접을 수 없던 것 (P439, 2026-11-08 사용자). 접으면 버튼 자리로 돌아오게 스크롤을 맞춘다
            close = (f'<div style="padding:6px 0 0 {TL_RAIL + 8}px;"><button type="button" style="{btn}" '
                     'onclick="var d=this.closest(\'details\');d.open=false;d.scrollIntoView({block:\'nearest\'});">'
                     f'접기 {up}</button></div>')
            out += (f'<details class="fc-more" style="margin:0;">'
                    f'<summary style="list-style:none;cursor:pointer;padding:6px 0 0 {TL_RAIL + 8}px;">'
                    f'<span style="{btn}">{label} {dk.ACC_CHEV}</span></summary>'
                    + "".join(row(x, i == len(rest) - 1) for i, x in enumerate(rest)) + close + '</details>')
    return out + "</div>"


# ---------------------------------------------------------------- 겹침이 쌓일 때 (2026-11-08 사용자 · Claude 제안 채택)
# 겹침 개수는 압력 점수가 아니다 — 방향이 없고(같은 방향 · 반대가 섞임) 기록을 촘촘히 한 업종일수록 많아진다. 시장 불안은 층 압력 · 불안 지수가 맡는다.
# 겹침이 쌓이면 흐려지는 것은 판정(결과를 한 사건 탓으로 볼 수 없음) → ① 세부 전망 깊이 한 단계 · 처음 전망 아래 둘까지 ② 셋째부터는 타임라인 표시만
# ③ 겹침이 2개를 넘는 전망은 성적표에서 따로 셈 ④ 독자에게 방향 없는 사실 한 줄.
SUB_MAX = 2        # 처음 전망 하나 아래 세부 전망(겹침으로 따로 적는 것) 최대 개수
CROWD_MAX = 2      # 겹침이 이보다 많으면 `여러 사건이 겹친 전망` — 맞음 · 틀림에 넣지 않고 따로 센다


def root_of(fc, by_slug):
    """처음 전망 — 세부 전망 안에서 겹친 사건도 처음 전망 아래로 적는다(세부 전망의 세부 전망은 만들지 않음, 깊이 한 단계)."""
    seen = set()
    while True:
        b = _back_of(fc)
        if not b or b[1] in seen or b[1] not in by_slug:
            return fc
        seen.add(b[1])
        fc = by_slug[b[1]]


def place_overlap(root):
    """새 사건이 처음 전망(root)의 기간 안에 겹쳤을 때 → "sub"(세부 전망으로 따로 등록) 또는 "mark"(타임라인 겹침 표시만).
    세부 전망은 처음 전망 아래 SUB_MAX 개까지. 그 뒤 사건은 따로 등록하지 않는다(판정이 이미 흐려져 새 전망을 세워도 가를 수 없음)."""
    subs = [o for o in root.get("overlap", []) if o.get("role") != "parent" and o.get("slug")]
    return "sub" if len(subs) < SUB_MAX else "mark"


def overlaps_of(fc):
    """이 전망 기간에 겹친 사건 (자기를 낳은 처음 전망 쪽 표시 role parent 는 빼고)."""
    return [o for o in fc.get("overlap", []) if o.get("role") != "parent"]


def is_crowded(fc):
    """겹침이 CROWD_MAX 개를 넘는 전망 — 성적표에서 맞음 · 틀림 대신 `여러 사건이 겹친 전망` 으로 따로 센다."""
    return len(overlaps_of(fc)) > CROWD_MAX


def crowd_line(fc):
    """독자 한 줄 — 방향 말 없이 사실만. 겹침이 CROWD_MAX 개를 넘을 때만."""
    n = len(overlaps_of(fc))
    if n <= CROWD_MAX:
        return ""
    # 개수 + 무엇이 겹쳤는지만 (2026-11-08 사용자: 셋 · 다섯이 겹쳐도 독자는 무엇이 겹쳤는지 알아야 한다 — 해석 문장은 뺌)
    evs = " · ".join(f'{o.get("day", "")} {_re.sub(r"(?<! )\(", " (", o["event"])}'.strip() for o in overlaps_of(fc))
    return dk.muted(f"큰 사건 {n}개가 겹쳤습니다 : {evs}")


def _overlap_lines(fc):
    """겹침 안내 줄 — 타임라인 바로 아래 (P418, 옛 `전망 결과` 카드 아래)."""
    out = ""
    for o in fc.get("overlap", []):   # 겹침 — 독자 한 줄. 지시어(이 전망) · 번호(전망 2) 없이 제목으로, `창` 대신 `전망 기간`, 이어 적은 것은 `세부 전망` (2026-11-07 사용자)
        # "효과를 지웠다" 는 단언이지만 "영향을 미친 것으로 보인다" 는 쓸 수 있다 (같은 날 사용자)
        me, other = f'‘{fc["title"]}’', f'‘{o.get("title", "")}’'
        if o.get("role") == "parent":   # 이 전망이 세부 전망 쪽
            text = f'{me} 는 {other} 전망 기간 안에 일어난 {o["event"]}을 따로 적은 세부 전망입니다.'
        else:
            start, end = md(fc.get("event_day") or fc["registered"]), md(fc["end_day"]) if fc.get("end_day") else ""
            text = f'{o["day"]} {o["event"]}이 {me} 전망 기간({start}~{end}) 안에 일어나, 세부 전망 {other} 으로 따로 적었습니다.'
            # 방향 문장(`힘을 보탠 것으로 보입니다`)은 없앰 — 매일 바뀌는 해석이고 원인 몫은 나눌 수 없다. 카드는 바뀌지 않는 사실 + 바로가기만 (P450, 2026-11-08 사용자)
        out += _overlap_card(o, text)
    return out


def _link_a(label, slug, theme="neutral"):
    """긴 바로가기 버튼 본체 — 카드 안(_link_btn) · 질문 아래(세부 전망으로 이어감, P463)가 같이 쓴다."""
    bg, bd = dk.CARD_DIR[theme]
    hue = dk.FOLD_HUE.get(bd.upper())
    ink = dk.mix("#111111", hue, 0.2) if hue else "#111"
    right = f'<span style="display:inline-flex;flex:none;transform:rotate(-90deg);">{dk.ACC_CHEV.replace("acc-chev", "fc-right")}</span>'
    return (f'<a href="{page_url(slug)}" style="display:flex;align-items:center;justify-content:center;gap:4px;width:100%;height:{dk.FOLD_BOX}px;box-sizing:border-box;padding:0 12px;'
            f'background:{dk.lighten(bg)};border:1px solid {bd};border-radius:{dk.FOLD_RADIUS}px;color:{ink};font-size:14px;line-height:20px;font-weight:700;text-decoration:none;">'
            f'<span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{dk.esc(label)}</span>{right}</a>')


def _back_of(fc):
    """세부 전망 페이지면 (이전 전망 제목, 주소), 아니면 None — 이어받은 전망(follow_of) · 겹쳐서 따로 적은 전망(overlap role parent)."""
    b = fc.get("follow_of")
    if b and b.get("slug"):
        return b["title"], b["slug"]
    r = fc.get("reversal_of")   # 번복 n회차 = 앞 회차의 세부 전망 (2026-11-08 사용자: 회색 번복 카드 대신 세부 전망 카드 · `이전전망 ›`)
    if r and r[1]:
        return r[0], r[1]
    for o in fc.get("overlap", []):
        if o.get("role") == "parent" and o.get("slug"):
            return o.get("title", ""), o["slug"]
    return None


def _follow_btn(fc, st=None):
    """질문 아래 세부 전망 카드들 — 이어감 · 겹침을 한 모양(보라 카드)으로 (P479, 2026-11-08 사용자: 겹침 카드와 세부 전망 카드를 하나로).
    첫 줄 = `세부전망`(이 전망에서 갈라져 나간 쪽) · `이전전망`(이 전망이 갈라져 나온 쪽), 둘째 줄 = 그 전망 제목, 셋째 줄 = 생긴 이유 `이어감 · 날짜 판정 뒤` · `겹침 · 날짜 사건`."""
    st = st or {}
    res = st.get("result") or {}
    out = ""
    f, back = fc.get("follow"), fc.get("follow_of")
    if f and f.get("slug"):
        out += _sub_card(f["title"], f["slug"])   # 이어감 안내 줄은 없앰 — 셋째 줄은 겹침만 (P480, 2026-11-08 사용자)
    rb = fc.get("reversed_by")   # 번복 — 다음 회차를 세부전망 카드로, 셋째 줄 `[번복] 날짜 사건` (2026-11-08 사용자 — 옛 P443 회색 번복 카드)
    if rb and rb[1]:
        out += _sub_card(rb[0], rb[1], note=f'번복 · {rb[3] if len(rb) > 3 else ""}'.strip())
    # 이전전망 카드는 없앰 — 질문 앞 `세부전망` 라벨 + 날짜 아래 작은 `이전전망 ›` 버튼으로 (P481)
    for o in fc.get("overlap", []):
        if not o.get("slug") or o.get("role") == "parent":
            continue
        ev = _re.sub(r"(?<! )\(", " (", o["event"])   # `물가 발표(CPI)` → `물가 발표 (CPI)`
        out += _sub_card(o.get("title", ""), o["slug"], head="이전전망" if o.get("role") == "parent" else "세부전망", note=f'겹침 · {o.get("day", "")} {ev}'.replace("  ", " "))
    return out


VIOLET_BOX = ("#EDE9FE", "#DDD6FE", dk.VIOLET)   # 보라 테마 라벨 — 상자 모양은 TS.box 와 같고 색만 (P476)


def violet_box(text):
    bg, bd, fg = TS.BOX["flat"]
    return TS.box("flat", text, dk.esc, sym=False, fit=True).replace(f"background:{bg};", f"background:{VIOLET_BOX[0]};").replace(f"border:1px solid {bd};", f"border:1px solid {VIOLET_BOX[1]};").replace(f"color:{fg};", f"color:{VIOLET_BOX[2]};")


def _note_row(note):
    """세부 전망 카드 셋째 줄 — `겹침 · 12.10 물가 발표 (CPI)` → 노랑 `겹침` 라벨 + 검정 글씨, 세로 가운데 (2026-11-08 사용자 — 옛 회색 글씨 한 줄)."""
    for w in ("겹침", "번복"):   # 생긴 이유 라벨 — 보라 뉴스 라벨 크기 (번복 = 2026-11-08 사용자: 세부 전망 카드로 통일)
        if note.startswith(w + " · "):
            return (f'<span style="display:flex;align-items:center;gap:6px;margin-top:4px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:#111;word-break:keep-all;">'
                    f'{news_pill(w, VIOLET_BOX, inline=False)}<span>{dk.esc(note[len(w) + 3:])}</span></span>')
    return f'<span style="font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};word-break:keep-all;">{dk.esc(note)}</span>'


def _sub_card(title, slug, head="세부전망", note=""):
    """세부 전망 카드 — 전망 A · B 카드와 같은 크기 · 같은 제목 글씨, 보라 테마(uncertain). 첫 줄 = 보라 글씨 `세부전망`(라벨 상자 없음, 띄어쓰기 없음),
    그 아래 줄 = 세부 전망 제목, 오른쪽 = 상자 없는 › 화살표. 카드 전체가 세부 전망 페이지 링크 (P476 → P477, 2026-11-08 사용자)."""
    bg, bd = qc.CARD_DIR["uncertain"]
    hue = dk.FOLD_HUE.get(bd.upper())
    ink = dk.mix("#111111", hue, 0.2) if hue else "#111"
    chev = dk.ACC_CHEV.replace('width="16" height="16"', f'width="{dk.FOLD_ICON}" height="{dk.FOLD_ICON}"').replace("<svg ", '<svg style="display:block;transform:rotate(-90deg);" ', 1)
    head = (f'<span style="display:flex;justify-content:space-between;align-items:center;gap:12px;">'
            f'<span style="flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:2px;">'
            f'<span style="font-size:14px;line-height:20px;font-weight:700;color:{dk.VIOLET};">{dk.esc(head)}</span>'
            f'<span style="font-weight:{dk.STATE_TITLE_W};color:#111;font-size:{dk.EMPH_Q};line-height:{dk.LH_EMPH_Q};word-break:keep-all;">{dk.esc(title)}</span>'
            + (_note_row(note) if note else "") + '</span>'
            f'<span style="flex:none;display:inline-flex;color:{ink};">{chev}</span></span>')
    return (f'<a href="{page_url(slug)}" style="display:block;text-decoration:none;color:inherit;background:{bg};border:1px solid {bd};border-radius:10px;'
            f'padding:{dk.EMPH_PAD - dk.VP_EMPH}px 14px;margin:0 0 8px;line-height:{dk.LH_EMPH};">{head}</a>')


def _link_btn(label, slug, theme="neutral"):
    """카드 안 바로가기 버튼 — 미국 증시 리포트 카드 안 `더 보기` 버튼(cards.more_details, P417)과 같은 모양 · 카드 폭 가득, 오른쪽 화살표 (P444, 2026-11-08 사용자).
    버튼이 카드 끝이면 아래 여백 = 좌우 여백 14 (qc.end_fix 가 data-qmore-end 줄을 고친다)."""
    a = _link_a(label, slug, theme)
    return (f'<span data-qmore-end="1" style="display:block;padding-top:{qc.MORE_GAP_TOP - 6}px;">{a}</span>', "html")


def _reversal_card(fc):
    """번복 카드 — 같은 사건이 뒤집혀 n회차로 이어 적은 전망끼리 잇는다 (P443, 2026-11-08: `다른 전망` 구획을 없애며 회차 링크가 사라져 겹침 카드와 같은 모양으로).
    fc["reversal_of"] = (앞 회차 제목, slug, 이 회차 번호) — 이 페이지가 n회차. fc["reversed_by"] = (다음 회차 제목, slug, 회차 번호, 뒤집은 사건) — 이 페이지가 앞 회차.
    회색 이름표 `번복` + 제목 = 뒤집은 사건, 답 = `n회차` · `n회차로 이어짐`(회색 카드 · 검정 답), 펼치면 설명 문장 → 날짜 → 회차 링크."""
    out = ""
    for key in ("reversal_of", "reversed_by"):
        r = fc.get(key)
        if not r:
            continue
        title_o, slug, n = r[0], r[1], r[2]
        ev = (fc.get("event") if key == "reversal_of" else (r[3] if len(r) > 3 else "")) or "번복"
        m = _re.match(r"^(\d{2}\.\d{2})\s+(.*)$", ev)
        day, name = (m.group(1), m.group(2)) if m else ("", ev)
        if key == "reversal_of":
            text = f'{day} {name}로 같은 사건이 뒤집혀 {n}회차로 적었습니다. 앞 회차 ‘{title_o}’ 는 판정대로 두고, 성적표에서는 두 회차를 한 건으로 셉니다.'.strip()
            ans, link_name = f"{n}회차", f"{n - 1}회차 전망"
        else:
            text = f'{day} {name}로 같은 사건이 뒤집혀 {n}회차 ‘{title_o}’ 로 이어 적었습니다. 이 전망은 판정대로 두고, 성적표에서는 두 회차를 한 건으로 셉니다.'.strip()
            ans, link_name = f"{n}회차로 이어짐", f"{n}회차 전망"
        lines = [(text, "plain")] + ([_link_btn(f"{link_name} : {title_o}", slug)] if slug else [])   # 날짜 줄 삭제(제목 앞 날짜) · 링크 = 긴 버튼 (P444)
        head = f"{day} {name}".strip()   # 제목 앞 날짜 (P444)
        html = qc.end_fix(qc.question_card(head, ans, "neutral", "#111", lines, fold=True, opened=False))
        out += _tag_title(html, head, violet_box("번복"))
    return out


def _overlap_card(o, text):
    """겹침 카드 — 두 갈래 카드 위, 회색 이름표 `겹침` + 제목 = 겹친 사건 (P441, 2026-11-08 사용자: 화면에서 무엇이 겹쳤는지 보이지 않았다, 겹침은 사건이니 카드로).
    답 없음 — 바뀌지 않는 사실만(무엇이 언제 겹쳤나 · 따로 적었다 · 바로가기). 펼치면 설명 문장 · 바로가기 버튼 (P450)."""
    parent = o.get("role") == "parent"
    title = o.get("title", "") if parent else f'{o.get("day", "")} {o["event"]}'.strip()   # 제목 앞 날짜 (P444, 2026-11-08 사용자)
    ans = ""   # 오른쪽 답(같은 방향 · 반대 방향) 없앰 — 매일 바뀌는 해석 (P450)
    lines = [(text, "plain")]   # 날짜 줄은 제목 앞으로 옮겨 삭제 (P444)
    if o.get("slug"):   # `보기` 링크 대신 긴 바로가기 버튼 `세부 전망 : 제목` (P444)
        lines.append(_link_btn(f'{"전망" if parent else "세부 전망"} : {o.get("title", "")}', o["slug"]))
    html = qc.end_fix(qc.question_card(title, ans, "neutral", "#111", lines, fold=True, opened=False))
    return _tag_title(html, title, overlap_pill())   # 노랑 뉴스 라벨 크기 (2026-11-08 사용자)


def reg_dirs(state_dir=None):
    """등록 파일 폴더 — 손으로 만든 hypotheses/ + 자동 등록(forecast_register) 폴더: 상태 저장소 records/hypotheses, 미리보기는 output/forecast/hypotheses (2026-11-11)."""
    auto = os.path.join(state_dir, "records", "hypotheses") if state_dir else os.path.join(_HERE, "output", "forecast", "hypotheses")
    return [os.path.join(_HERE, "hypotheses"), auto]


def load_regs(state_dir=None):
    import glob as _glob
    out = []
    for d in reg_dirs(state_dir):
        out += [load(p) for p in sorted(_glob.glob(os.path.join(d, "EH-*.json"))) if not p.endswith("_prices.json")]
    return out


def forecasts(reg, public=False):
    fs = reg.get("forecasts") or [reg["forecast"]]
    return [f for f in fs if f.get("publish", True)] if public else fs


def pre_base_day(event_day, release_et, trading_days):
    """결과 직전 종가의 날 — 장 마감(16:00 ET) 뒤 발표면 발표 날, 아니면 발표 전 마지막 거래일 (2026-11-08)."""
    if (release_et or "08:30") >= "16:00":
        return event_day
    prev = [d for d in trading_days if d < event_day]
    return prev[-1] if prev else event_day


def proof_record(reg, fc):
    """공개 등록 증명 — 등록 때 고정되는 칸만 모아 정렬 JSON + sha256. 이 파일을 공개 저장소 gh-pages/proof/{slug}.json 에 커밋하면
    커밋 시각이 '사건 전에 적었다' 의 증명이 된다(누구나 GitHub 커밋 기록으로 확인). 결과 · 국면은 넣지 않는다(바뀌는 값)."""
    import hashlib
    keep = {"id": reg.get("id"), "slug": fc["slug"], "title": fc["title"], "kind": fc["kind"], "registered": fc["registered"],
            "event": fc.get("event"), "event_day": fc.get("event_day"), "ruler": fc.get("ruler_short"), "line": fc.get("line"), "unit": fc.get("unit", "%p"),
            "gap": fc.get("gap"), "pick": fc.get("pick"), "pick_prob": fc.get("pick_prob"), "market_prob": fc.get("market_prob"), "rules": reg.get("rules"),
            "scenarios": [{"cond": c["cond"], "name": c["name"], "dir": c["dir"], "win": c["win"]} for c in fc["scenarios"]]}
    body = json.dumps(keep, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    keep["sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return keep


def proof_url(fc):
    return f"https://github.com/{PROOF_REPO}/commits/gh-pages/proof/{fc['slug']}.json"


def _op_mood(fc):
    """시장 분위기 중 그 전망이 실제로 쓰는 것만 운영자 상자로 — 충격 뒤 전망의 불안 지수 · 뉴스 분위기(우리 전망 고르기 재료). 나머지(공포 · 탐욕 · 지정학 · 정책 불확실성 · 업계 상대수익)는 쓰지 않아 버린다 (P391)."""
    if fc["kind"] != "after":
        return []
    keep = {"시장 충격 국면": "불안 지수", "뉴스 · 방송": "뉴스 분위기"}
    return [(keep[a], f"{b} · {c}" if c else b) for a, b, c in (fc.get("pressure") or {}).get("rows", []) if a in keep]


def forecast_body(reg, state=None, fc=None, others=None, op=None):
    """others = 다른 전망 링크 [(no, title, slug)] — 없으면 같은 사건의 전망들. op = 운영자 확인용 [(이름, 값)] — 목업에서만, 발행 때는 None."""
    st = state or {}
    fc = copy.deepcopy(fc or forecasts(reg)[0])   # 화면용 손질(P412 반대 문장)이 등록 자료 · 증명 값에 번지지 않게
    _fill_other(fc)
    log = st.get("log") or [_entry(fc["registered"], "start", "지켜보는 중", 0, fc["start_text"], 0.0)]
    if fc.get("overlap"):   # 겹친 사건 날 줄에 겹침 표시 (P468) — 상태 자료는 고치지 않게 줄을 복사
        ov = {o.get("day"): o for o in fc["overlap"] if o.get("role") != "parent"}
        log = [dict(x, overlap=ov[md(x["day"])]) if md(x.get("day") or "") in ov else x for x in log]
    before = fc["kind"] == "pre" and not st.get("cond") and not st.get("result")   # 사건 전 등록 화면 — 결과가 없으니 `전망 결과` 를 그리지 않는다 (2026-11-07 사용자)
    # 결과 뒤도 결과 전과 같은 타임라인 — `전망 결과` 제목 · 강조 카드 · `결과 :` 상자 없음 (P418, 결과 날짜 = 날짜 줄 보라 P413 · 결과 내용 = 갈래 카드 첫 고리 줄)
    head = (_waiting(log, fc.get("unit", "%p"), fc.get("subject", ""), fc) if before else f'<div data-lead="1">{_waiting(log, fc.get("unit", "%p"), fc.get("subject", ""), fc)}</div>')   # `앞으로 올 수 있는 일` 카드 삭제 — 내용은 갈래 카드 · 셋째 카드 안으로 (2026-11-07 사용자 · Claude 판단)
    for sc in fc["scenarios"]:
        sc["_L"] = fc.get("line", 3.0)
    # 두 갈래 카드 = 페이지 맨 위, 구획 제목 없이 · 카드마다 `전망 A` · `전망 B` 이름표 (P386). 문장 안에서는 계속 갈래 이름으로 부른다(번호 금지 규칙)
    per, third = _split_ahead(fc, st)
    order = sorted(fc["scenarios"], key=lambda sc: {"up": 0, "flat": 1, "down": 2}[_tag_kind(sc)])   # 높은 쪽 위 = 전망 A, 낮은 쪽 아래 = 전망 B (P411, 화면 순서만 · 판정 no 그대로)
    sides = (THIN_CSS + '<div style="margin:0 0 24px;">' + "".join(   # 옛 open_why 카드 = 타임라인 위 `향방 미정` 한 줄로 (2026-11-11 사용자)   # 회색 번복 카드 없앰 — 회차는 세부전망 카드 · `이전전망 ›` 로 잇는다 (2026-11-08 사용자)   # 겹침 카드는 없앰 — 질문 아래 세부 전망 카드 셋째 줄 `겹침 · …` 로 (P479)   # 번복 · 겹침 카드 = 전망 A 위 (P441 · P443)
             _scenario_card(sc, branch_view(fc, st, sc), tag="전망" + chr(65 + i), extra=per.get(sc["no"]), compact=None, mkt=sc["no"] == _mkt_no(fc),
                            why=side_why(fc, sc, dk.CARD_DIR[branch_view(fc, st, sc)["theme"]][1])) for i, sc in enumerate(order))
             + (_third_card(third[0], third[1], fc.get("line", 3.0)) if third else "") + "</div>")   # 셋째 카드 = `선반영` (사건 전) · `제자리` (충격 뒤) (2026-11-07 사용자)
    now = "" if before else _fold_row("현재 증시는?", _stock_now(fc, st) + _compare_chart(fc, st) + _now_plain(fc, st), side=_close_day(st))   # 종목 전망 = 맨 위 종목 줄 · 바로가기 (2026-11-11 사용자)   # 옛 `지금은?` 구획 → 접는 줄, 기록 줄과 한 묶음 (P418) · 카드 없이 · 한국 카드 삭제 (P425)
    more = (_event_chart(reg) if fc.get("event_chart") else "") + _fold_group(_reasons_card(fc) + _broke_card(fc) + now + _history_card(fc))   # 어디서 끊겼나 = 접는 줄 묶음 맨 위 (P435)   # `앞으로 볼 것은?` 삭제 — 안내 문구 · 내부 방법 설명뿐, 위험 · 다음 일은 갈래 카드 안에 (P394)
    # 질문 제목 = 날짜 줄 위 (P454, 2026-11-08 사용자: 머리 줄은 `증시 전망`, 질문은 길 수 있어 본문 맨 위에 따로). 구획 제목 글씨(22/28 · 폰 20/26), 아래가 날짜 줄이라 밑줄 없음
    # 질문 줄 = 왼쪽 질문 · 오른쪽 결과 발표 날짜 한 줄, 질문이 길면 날짜 칸을 침범하지 않고 왼쪽 칸 안에서 두 줄 (P455, 2026-11-08 사용자). 날짜는 질문 첫 줄 글자 바닥에 맞춘다(baseline)
    # 질문 앞 = 증시 전망 저울 아이콘(배경 = 홈 `시장 흐름과 종목` 아이콘 청록 #0E7490, P457) 24 · 모서리 6 · 그림 16, P456). 한 줄 높이(1lh = 22/28 · 폰 20/26)를 아이콘 · 날짜 칸이 물려받아 첫 줄 가운데, 둘째 줄은 아이콘 아래로 들어가지 않는다
    icon = f'<span style="display:flex;flex:none;align-items:center;height:1lh;">{scale_icon(24)}</span>'
    # 개별 종목 전망(자동 등록 target=stock)만 티커 로고 · 저울 없음, 거시 · 업종 전망은 종목명이 있어도 로고 없이 저울만 (2026-11-11 사용자 — 옛 11-10 `질문에 종목명이 있으면 로고`)
    title_html = title_for(fc)
    if is_stock_fc(fc):
        icon = ""
    back = _back_of(fc)   # 세부 전망 페이지 — 질문 앞 보라 `세부전망` 라벨 + 날짜 아래 작은 `이전전망 ›` 버튼 (P481, 2026-11-08 사용자: 세부 전망은 전망이 있어야 있는 것)
    sub_lab = violet_word("- 세부전망") if back else ""   # 질문 문장 끝 · 보라 굵은 글씨, 상자 없음 (2026-11-08 사용자 — 옛 P481 질문 앞 상자 → 라벨)
    back_btn = (f'<a href="{page_url(back[1])}" style="display:inline-flex;align-items:center;gap:2px;margin-top:6px;padding:2px 6px 2px 8px;border:1px solid #E2E8F0;border-radius:6px;background:#fff;'
                f'font-size:13px;line-height:19px;font-weight:600;color:#333;text-decoration:none;white-space:nowrap;">이전전망'
                f'<span style="display:inline-flex;transform:rotate(-90deg);">{dk.ACC_CHEV.replace("acc-chev", "fc-right").replace(chr(39) + "16" + chr(39), chr(39) + "14" + chr(39))}</span></a>') if back else ""
    # 머리 줄 구분선 ~ 질문 = 테마 .pr-sticky 아래 14 + 아이콘 위 2 = 16 → 위 여백 16 더해 32 (2026-11-09 사용자: 100% 늘려) → +10 = 위 여백 26 · 보이는 42 (같은 날 사용자)
    q = (f'<h2 style="{dk.H2}display:flex;flex-wrap:nowrap;align-items:flex-start;gap:8px;margin:26px 0 11px;">' + icon
         + f'<span style="flex:1 1 auto;min-width:0;display:flex;flex-direction:column;"><span style="word-break:keep-all;">{title_html}{sub_lab}</span>'
         # 날짜(급락일 · 결과) · `이전전망 ›` = 제목 아래 줄, 오른쪽 정렬 (2026-11-08 사용자 — 옛 P455 제목 줄 오른쪽 끝)
         + f'<span style="display:flex;flex-wrap:wrap;justify-content:flex-end;align-items:center;gap:4px 10px;margin-top:29px;line-height:{dk.LH_TINY};">'
         + _date_row(fc, out=not before and fc["kind"] == "pre").replace("flex-direction:column;align-items:flex-end;", "flex-wrap:wrap;align-items:center;gap:4px 10px;", 1)
         + back_btn.replace("margin-top:6px;", "", 1) + '</span></span></h2>') + _follow_btn(fc, st)
    body = (q + sides + head + crowd_line(fc)   # 겹침이 2개를 넘으면 사실 한 줄 (2026-11-08)
            + (operator_box(op + _op_mood(fc) + ([("거래량", f'평소의 {st["volume_x"]:.1f}배 — 기록만 — 우리 전망 고르기엔 안 씀')] if fc["kind"] == "after" and st.get("volume_x") else [])) if op else "")
            + more + why_note_html(fc)   # 근거 안내 = `현재 증시는?` 아래 한 번 (2026-11-11 사용자)   # `더 궁금한 것` 제목 삭제 — 기록 · 앞으로 볼 것은 각자 구분선 구획 (2026-11-07 사용자)
            )   # `다른 전망` 구획 삭제 — 글 아래 [목록] 버튼이 전망 목록으로 간다, 이어진 전망은 겹침 카드 안 링크로 (P442, 2026-11-08 사용자)
    return dk.fix_colons(f'<div data-list-url="{page_url(LIST_SLUG)}" data-head-title="{HEAD_FORECAST}" data-nav="list" data-title-back="{page_url(LIST_SLUG)}" data-title-back-label="목록" data-seo-lead="{dk.esc(seo_lead(fc, st))}">{body}{RELATED}</div>')


def seo_lead(fc, st=None):
    log = (st or {}).get("log") or []
    return f'증시 전망 — {fc["title"]} 두 갈래, 지금 {log[-1]["label"] if log else "지켜보는 중"}'


def forecast_title(fc):
    return fc["title"]


# ---------------------------------------------------------------- 목록 페이지

def _row(fc, st):
    """목록 한 장 = 제목(18px 굵게 · 행간 34) + 분류 라벨 · 게시일 + 오른쪽 국면 한 마디. 카드 색 = 국면 테마."""
    log = st.get("log") or [_entry("", "start", "지켜보는 중", 0, "", 0.0)]
    e = log[-1]
    sub = fc.get("follow_of") or fc.get("reversal_of") or any(o.get("role") == "parent" for o in fc.get("overlap", []))   # 번복 n회차도 세부 전망 (2026-11-08)   # 이어받았거나 겹쳐서 따로 적은 전망 = 세부 전망 (P464)
    tags = dk.pill_row((violet_box("세부 전망") if sub else "") + "".join(dk.pill(t, kind="area", bare=True) for t in fc.get("tags", [])))
    left = (f'<a href="{page_url(fc["slug"])}" style="display:block;color:#111;font-weight:400;font-size:18px;line-height:28px;text-decoration:none;word-break:keep-all;overflow-wrap:anywhere;">'   # 보통 굵기 · 긴 낱말도 카드 안에서 줄 바꿈 (2026-11-08 사용자: 목록 전부 레귤러, 카드 밖으로 삐져나옴)
            + ("" if is_stock_fc(fc) else f'<span style="display:inline-flex;vertical-align:-3px;margin-right:6px;">{scale_icon(18)}</span>')   # 거시 · 업종 줄 앞 저울 = 종목 줄 로고 자리 (2026-11-11 사용자)
            + f'{title_for(fc, 18)}</a>'
            f'<span style="display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;margin:8px 0 1px;line-height:1;min-width:0;">{tags.replace("white-space:nowrap;", "flex-wrap:wrap;", 1)}'
            f'<span style="color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};">{dk.esc(fc["posted"])} 게시</span>'
            # `등록 기록` 링크 삭제 (2026-11-09 사용자: 독자에게 과한 정보 · GitHub 는 일반 독자에게 어렵다)
            + "</span>")
    lab = e["label"][len(fc["subject"]) + 1:] if fc.get("subject") and e["label"].startswith(fc["subject"] + " ") else e["label"]   # 대상 이름은 제목에 있으니 뺀다 — `에너지 업종 조정 우세` 이 카드 밖으로 넘쳤다 (P464, 타임라인 P440 과 같은 규칙)
    right = f'<span style="color:{INK[e["dir"]]};font-size:16px;line-height:24px;font-weight:400;word-break:keep-all;overflow-wrap:anywhere;">{dk.esc(lab)}</span>'   # 보통 굵기 · 줄 바꿈 허용 — `조정 조짐이 보임` 이 오른쪽 칸 밖으로 나가던 것 (2026-11-08)
    inner = (f'<div data-row-link="1" style="display:flex;justify-content:space-between;align-items:center;gap:12px;">'
             f'<div style="{dk.COL_L}">{left}</div><div style="{dk.COL_R}">{right}</div></div>')
    return dk.dcard(inner, theme=e["theme"])


def scoreboard_card(sc):
    """우리 전망 성적표 (11절 2) — sc = {"n", "hit", "miss", "neither", "watch", "picked_hit": (m, n), "note"}. 겹친 전망은 따로."""
    lines = [("큰 사건마다 결과가 나오기 전에 두 갈래를 적어 두고, 지나고 나서 맞았는지를 그대로 셉니다. 지우거나 고치지 않습니다.", "plain"),
             ("row", "맞음", f'{sc["hit"]}개', ""), ("row", "틀림", f'{sc["miss"]}개', ""), ("row", "제자리", f'{sc["neither"]}개', ""), ("row", "지켜보는 중", f'{sc["watch"]}개', "")]
    for key, name in (("hold", "판정 보류"), ("void", "무효")):
        if sc.get(key):
            lines.append(("row", name, f'{sc[key]}개', "세지 않음"))
    if sc.get("picked_hit"):
        m, n = sc["picked_hit"]
        lines.append(("row", "우리가 고른 쪽이 맞은 일", share_word(m, n).replace("이었습니다", ""), "급락 · 급등 뒤 전망만"))
    if sc.get("crowded"):   # 겹침이 2개를 넘은 전망 — 맞음 · 틀림에 넣지 않음 (2026-11-08)
        lines.append(("row", "여러 사건이 겹친 전망", f'{sc["crowded"]}개', "세지 않음"))
    if sc.get("note"):
        lines.append((sc["note"], "note"))
    return qc.question_card("우리 전망 성적표", f'{sc["n"]}개', "neutral", "#111", lines, fold=True, opened=False)   # 늘 닫힌 채로 (2026-11-08 사용자)


DONE_PER_PAGE, DONE_PAGES_SHOWN = 10, 5   # 끝난 전망 한 쪽 10개 · 쪽 번호는 한 번에 5개까지 (2026-11-08 사용자)


def done_list(done):
    """끝난 전망 — 접힌 구획(제목 18 굵게 — 구획 제목 22 보다 확실히 작게, 2026-11-08 사용자: 21 은 똑같아 보임 · 개수 · 화살표), 펼치면 `함께 보는 페이지` 같은 구분선 목록: 점 + 전망 제목(15 보통 = 함께 보기 줄 16 보다 작게) + ›.
    줄을 누르면 그 전망 페이지. 아래 쪽 번호 — 스크립트 없이 CSS 라디오로 넘긴다(블로그 본문에서 스크립트가 지워져도 돈다) (2026-11-08 사용자: 표 → 제목만 · 쪽 번호로 쌓기).
    done = [(제목, 일어난 쪽, 결과) 또는 (제목, 일어난 쪽, 결과, slug)]."""
    n = len(done)
    head = (f'<summary style="list-style:none;cursor:pointer;display:flex;align-items:center;gap:8px;padding:0 {dk.ALIGN_PX}px 10px;border-bottom:1px solid #E2E8F0;'
            f'font-size:18px;line-height:26px;font-weight:700;color:#111;">끝난 전망<span style="font-size:15px;font-weight:400;color:{dk.SUB};">{n}개</span>'
            f'<span class="fc-done-chev" style="margin-left:auto;display:inline-flex;color:{dk.SUB};">{dk.ACC_CHEV}</span></summary>')
    if not n:   # 끝난 전망이 하나도 없으면 구획째 숨긴다 — 옛 `아직 없습니다` 접는 줄 (2026-11-10 사용자)
        return ""
    dot = '<span aria-hidden="true" style="flex:none;width:3px;height:3px;border-radius:50%;background:#111;margin-right:8px;"></span>'
    chev = f'<span style="flex:none;display:inline-flex;margin-left:8px;color:{dk.NOTE};transform:rotate(-90deg);">{dk.ACC_CHEV}</span>'

    def row(d):
        url = page_url(d[3]) if len(d) > 3 and d[3] else "#"
        return (f'<a href="{dk.esc(url)}" data-row-link="1" style="display:flex;align-items:center;padding:11px {dk.ALIGN_PX}px;border-bottom:1px solid #E2E8F0;'
                f'font-size:15px;line-height:23px;font-weight:400;color:#111;text-decoration:none;">{dot}<span style="flex:1 1 auto;min-width:0;word-break:keep-all;overflow-wrap:anywhere;">{dk.esc(d[0])}</span>{chev}</a>')
    pages = [done[i:i + DONE_PER_PAGE] for i in range(0, n, DONE_PER_PAGE)]
    m = len(pages)
    css = ".fc-done[open] .fc-done-chev{transform:rotate(180deg);} .fc-done summary::-webkit-details-marker{display:none;} .fc-pp{display:none;}"
    css += "".join(f"#fcpg{i}:checked~.fc-pp[data-p='{i}']{{display:block;}}" for i in range(1, m + 1))
    nums_style = "display:inline-flex;align-items:center;justify-content:center;min-width:32px;height:32px;padding:0 6px;border-radius:6px;font-size:15px;cursor:pointer;"

    def nav(cur):   # 지금 쪽 둘레 5개 + 앞 · 뒤 화살표
        lo = max(1, min(cur - DONE_PAGES_SHOWN // 2, m - DONE_PAGES_SHOWN + 1))
        hi = min(m, lo + DONE_PAGES_SHOWN - 1)
        btn = lambda i, t, lab: (f'<label for="fcpg{i}" aria-label="{lab}" style="{nums_style}' + ("background:#111;color:#fff;font-weight:700;" if i == cur and t.isdigit() else "color:#333;") + f'">{t}</label>')
        out = (btn(cur - 1, "‹", "앞 쪽") if cur > 1 else "")
        out += "".join(btn(i, str(i), f"{i}쪽") for i in range(lo, hi + 1))
        out += (btn(cur + 1, "›", "다음 쪽") if cur < m else "")
        return f'<div style="display:flex;justify-content:center;gap:4px;padding:12px 0 0;">{out}</div>' if m > 1 else ""
    radios = "".join(f'<input type="radio" name="fcpg" id="fcpg{i}"{" checked" if i == 1 else ""} hidden>' for i in range(1, m + 1))
    body = "".join(f'<div class="fc-pp" data-p="{i}">' + "".join(row(d) for d in pg) + nav(i) + '</div>' for i, pg in enumerate(pages, 1))
    return f'<style>{css}</style><details class="fc-done" style="margin:28px 0 0;">{head}<div>{radios}{body}</div></details>'


def list_body(pairs, states=None, done=(), score=None):
    """pairs = [(reg, fc)] 열린 전망, states = {slug: state}, done = [(전망, 결과, 최종)] 끝난 전망(지우지 않고 쌓는다). score = 성적표(없으면 안 그린다)."""
    states = states or {}
    rows = [_row(fc, states.get(fc["slug"], {})) for _, fc in pairs]
    opened = "".join(rows) if rows else dk.muted("지금 지켜보는 전망이 없습니다")
    # 옛 data-tip(페이지 맨 바깥) 삭제 — 테마가 [data-tip] 을 누르면 팝업이라 페이지 어디를 눌러도(접기 줄 포함) 팝업이 떴다 (2026-11-08 사용자)
    sec1 = f'<div style="margin:12px 0 0;">{opened}</div>'
    board = f'<div style="margin:28px 0 0;">{scoreboard_card(score)}</div>' if score else ""   # 성적표 = 지켜보는 전망 아래 · 끝난 전망 바로 위 (2026-11-08 사용자 — 옛 맨 위)
    sec2 = board + done_list(done)
    return dk.fix_colons(f'<div data-list-url="{BLOG}" data-head-title="{HEAD_LIST}" data-seo-lead="증시 전망, 큰 사건 전에 두 갈래 전망을 적어 두고 숫자로 확인한 기록">{sec1 + sec2}{RELATED}</div>')


# ---------------------------------------------------------------- 홈 카드 JSON (국면 한 마디는 넣지 않는다 — 2026-11-07 사용자, 제목 · 라벨 · 게시일만)

def home_card(pairs, generated=""):
    out = {"id": "hypo-card", "label": CARD_NAME, "generated": generated, "list_url": page_url(LIST_SLUG), "open": [], "done_count": 0}
    for reg, fc in pairs:
        out["open"].append({"no": fc["no"], "eh": reg["id"], "title": fc["title"], "url": page_url(fc["slug"]),
                            "posted": fc["posted"], "tags": fc.get("tags", []), "event": fc["event"]})
    return out


# ---------------------------------------------------------------- EH-2026-001 목업 (실제 시세 표본)

def _pad(days, n_more, holidays=("2026-11-26", "2026-12-25")):
    d = date.fromisoformat(days[-1])
    out = list(days)
    while len(out) < len(days) + n_more:
        d += timedelta(days=1)
        if d.weekday() < 5 and d.isoformat() not in holidays:
            out.append(d.isoformat())
    return out


def eh001_states(reg, data):
    rec = [r for r in data["recent"] if r["d"] >= "2026-11-02"]
    base = next(r for r in rec if r["d"] == "2026-11-04")
    days = _pad([r["d"] for r in rec], 20)
    vals = [(r["sox"] / base["sox"] - 1) * 100 - (r["spx"] / base["spx"] - 1) * 100 for r in rec] + [None] * 20
    vix = [r["vix"] for r in rec]
    f1, f2 = forecasts(reg)
    b1 = next(r for r in rec if r["d"] == f1.get("base_day", "2026-11-04"))   # 전망 1 = 밤사이 선거 결과 → 11.03 종가부터 (2026-11-08)
    vals1 = [(r["sox"] / b1["sox"] - 1) * 100 - (r["spx"] / b1["spx"] - 1) * 100 for r in rec] + [None] * 20
    s1 = judge(f1, days, vals1, cond=1, vix=vix)
    s2 = judge(f2, days, vals, vix=vix)
    for s in (s1, s2):
        s["label_at"] = [0, 2, len(days) - 1]
    return {f1["slug"]: s1, f2["slug"]: s2}


if __name__ == "__main__":
    out_dir = os.path.join(_HERE, "output")
    os.makedirs(os.path.join(out_dir, "proof"), exist_ok=True)
    reg = load(os.path.join(_HERE, "hypotheses", "EH-2026-001.json"))
    reg2 = load(os.path.join(_HERE, "hypotheses", "EH-2026-002.json"))
    data = load(sys.argv[1] if len(sys.argv) > 1 else os.path.join(_HERE, "hypotheses", "EH-2026-001_prices.json"))
    states = eh001_states(reg, data)
    for fc in forecasts(reg2):   # 11.07 늦은 등록 — 시세 표본이 11.05 까지라 등록 줄 하나
        states[fc["slug"]] = judge(fc, [], [], cond=None)
    regs = [reg, reg2]
    pub = [(r, fc) for r in regs for fc in forecasts(r, public=True)]   # 공개 = publish 가 False 아닌 것 (14절 4)
    for r, fc in pub:   # 공개 등록 증명 파일 — 발행 단계에서 공개 저장소 gh-pages/proof/ 로 커밋
        fc["proof_url"] = proof_url(fc)
        # 목록 `등록 기록` 링크도 독자에게 내보내지 않는다 (2026-11-09 사용자: GitHub 는 일반 독자에게 어렵다) — proof_url 은 운영 상자(내부)에만
        with open(os.path.join(out_dir, "proof", f'{fc["slug"]}.json'), "w", encoding="utf-8") as f:
            json.dump(proof_record(r, fc), f, ensure_ascii=False, indent=1)
    others_all = [(fc["no"], fc["title"], fc["slug"]) for _, fc in pub]

    def local(html):
        return html.replace(f"{BLOG}p/", "mock_")
    for r in regs:
        for fc in forecasts(r):
            rec = fc.get("record") or {}
            op = [("공개", "예 — 블로그에 나감" if fc.get("publish", True) else "아니오 — 내부 보기(사후 등록 샘플)"),
                  ("규칙", r.get("rules", "")), ("자료", "B1 일봉 _SOX · _GSPC · _VIX (시세 표본 11.05 까지) · A8 사건표 · A10 충격 국면 기준선(VIX>28, n=119)"),
                  ("등록", f'{fc["registered"]} · {r.get("registered_commit") or "커밋 미기록"} · {r.get("late_registration") or fc.get("sample_note", "")}'),
                  ("등록 증명", (fc.get("proof_url", "") + " · sha256 " + proof_record(r, fc)["sha256"][:16] + "…") if fc.get("publish", True) else "공개 안 함"),
                  ("우리 전망", fc.get("pick_note", "— (사건 전 전망: 실제 결과가 가른다)")),
                  ("자", f'β {fc.get("beta", 1.0)} — 업종 발 사건(범위 비율 ≥ 2)은 β 1 단순 차이, 시장이 다른 이유로 움직일 때만 β 조정(추정 창 250거래일)'),
                  ("시점 고정", "등록 때 쓴 값(이슈 코드 · 분위기 · 시장 예상 확률 · β · 기록 분포)은 그날 스냅샷으로 registered 줄에 저장, 뒤에 다시 계산하지 않는다 (11절 6)")]
            ko = {"result": "결과", "overlap": "겹침", "cooccur": "동행"}
            op += [(ko.get(k, k), str(v)[:240]) for k, v in rec.items()]
            oth = [o for o in others_all if o[2] != fc["slug"]]
            print(dk.write_mock(local(forecast_body(r, states[fc["slug"]], fc, others=oth, op=op)), os.path.join(out_dir, f'mock_{fc["slug"]}.html'), CARD_NAME))   # 머리 줄 = `증시 전망` (P454). 블로그 글 제목은 질문 그대로(검색) — 머리 줄 이름 바꾸기는 테마 수정 필요
    score = {"n": 2, "hit": 0, "miss": 0, "neither": 0, "watch": 2, "note": "결과가 나오기 전에 적은 전망만 셉니다. 사건 뒤에 적은 보기는 넣지 않습니다."}
    print(dk.write_mock(local(list_body(pub, states, score=score)), os.path.join(out_dir, f"mock_{LIST_SLUG}-eh.html"), CARD_NAME))   # 실제 등록만 — mock_forecast-list.html 은 forecast_cases.py 가 상황 탭 전부로 (2026-11-08)
    with open(os.path.join(out_dir, "hypo.json"), "w", encoding="utf-8") as f:
        json.dump(home_card(pub, "2026-11-07T04:00:00Z"), f, ensure_ascii=False, indent=1)
