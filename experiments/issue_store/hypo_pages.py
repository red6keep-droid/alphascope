"""증시 전망 — 전망 고정 페이지 · 목록 고정 페이지 · 홈 카드 JSON 렌더러 + 판정 엔진(틀 S · 틀 R).

    python experiments/issue_store/hypo_pages.py      # EH-2026-001 목업(전망 1 · 2 · 목록 · hypo.json) → output/ (그 다음 home_mock.py)
    python experiments/issue_store/forecast_cases.py  # 경우의 수 목업(A 거시 · B 업종 · C 종목 × 상황 탭) → output/mock_forecast-cases.html

용어 (2026-11-07 사용자: "반등 · 되돌림 차이가 있나, 하락 지속이면 상승 지속은? 용어부터 통일") — 기획 증시-전망-기획 9절:
- 방향 = `상승` · `하락` 둘뿐(블로그 신호 용어와 같다).
- 사건 전 전망(틀 S) 갈래 = `{대상} 상승` · `{대상} 하락`. 조건 = 사건의 두 결과(`… 시`).
- 충격 뒤 전망(틀 R) 갈래 = 급락 뒤 `{대상} 반등` · `{대상} 하락 지속`, 급등 뒤 `{대상} 조정` · `{대상} 상승 지속` (2026-11-07 사용자: "되돌림은 생소하다, 미디어도 반등을 쓴다").
  반등 = 빠진 폭의 절반을 회복, 조정 = 오른 폭의 절반을 반납. 지속 = 충격 방향으로 금만큼 더 가는 것. `되돌림` 은 쓰지 않는다.
- 국면(날마다) = `지켜보는 중` · `{갈래} 조짐`(금의 3분의 1 · 반등 · 조정은 4분의 1). 판정 = `맞음` · `틀림` · `어느 쪽도 아님`(창 끝까지 금 안).
- 갈래 카드의 답 = 그 갈래에 일어난 사실: `지켜보는 중` · `조짐` · `일어남` · `일어나지 않음`. 맞음 · 틀림은 맨 위 `전망 결과` 에만.
- 표시 라벨 = 사건 전 전망은 `실제 결과`(일어난 조건), 충격 뒤 전망은 `우리 전망`(기록상 분포로 고른 쪽).
- 독자 말(2026-11-07 저녁 재점검): `금` → `기준`, `충격 폭` → `급락 폭` · `급등 폭`, `창` → `60거래일 안에`, 구획 `더 알아보기` → `더 궁금한 것`, 갈래 구획은 `두 갈래 전망` 하나.
- 2026-11-07 밤 개선 10 전부 채택(기획 10절): ① 자 = 시장 모형 β 조정 초과수익(abnormal) ② 우리 전망에 기록상 비율(n번 중 m번) + 브라이어 ③ 고정 시점 판정(D+5 · 20 · 60) 병기, 플라시보는 검증해 때 ④ 뉴스 유무 갈림(Chan 2003: 뉴스 동반 = 지속 가중, 원인 미상 = 반등 · 조정 가중) ⑤ 거래량 배수 ⑥ GPR · EPU 배경 ⑦ 기록 카드 n번 중 m번 + 범위 ⑧ 실적 전망 기준 = 옵션 내재 예상 폭
- 11-07 밤 11절 채택(1 · 2 · 3 · 6): 틀 S 에 시장 예상 확률(market_prob) → 결과 줄 `예상대로` · `예상 밖` · 목록 맨 위 `우리 전망 성적표`(scoreboard) · 기록 카드 `가장 비슷했던 때` 셋(history.alike) · 시점 고정(운영자 상자). 4 · 5 는 발행 단계 · 검증해 때
- 11-07 밤 선반영 · 느린 누적 (사용자: "뻔한 결과는 먼저 반영되고, 하루 1%씩 쌓이는 하락은 3배 감지에 안 걸린다"): 틀 S 에 `detect_day`(감지일 = 시장 확률 ≥ 70% 사흘 + 뉴스 묶음 집중) — 감지일부터 사건 전날까지 `선반영 중` 국면, 결과일 종가로 자를 다시 놓고 뒤를 잰다. 예상대로 쪽 갈래는 `priced`(이미 반영): 결과 뒤 기준 넘게 더 가면 틀림, 되돌리거나 20거래일 기준 안이면 맞음. 느린 누적 = 틀 R 에 감지만 다른 것(10거래일 누적 2σ, 하루 기준 미달).
- 11-07 밤 "묘사가 아니라 경고" (사용자: 출발점은 중간선거처럼 "이렇게 되면 이런 일이 올 수 있으니 미리 생각해 두자"였다): ① 맨 위 `앞으로 올 수 있는 일` 카드(fc["prepare"]) = 다가오는 사건 × 지금 분위기 × 기록 → 조건부 경고 + 볼 것, 매수 · 매도 말 없음 ② 국면 문장 끝에 앞을 보는 꼬리("기준까지 1.2%p 남았습니다. 넘으면 ‘…’").
- 11-07 밤 지도 13-5 순서대로: ① `한국은 어떻게?` 카드(fc["korea"]: 미국 사건 → 한국 다음 날, 기록상 같은 방향 비율 · 크기 배수 — 2016~ 실측: 반도체 지수 큰 날 뒤 코스피 77% 같은 방향 · 0.26배, KODEX 반도체 75% · 0.38배, S&P 500 큰 날 뒤 코스피 82% · 0.28배) ② 판정 `보류`(fc["ambiguous"]: 결과가 두 조건 어느 쪽도 아님 — 채점 안 하고 움직임만) · `무효`(fc["void"]: 사건 취소 · 연기 · 자료 결함) ③ 번복(fc["reversal_of"]: 같은 사건 n회차, 성적표에서 묶음 한 건) · 연속 사건(묶음 전망: 조건 = "넷 중 셋 이상", 자 = 마지막 결과일 종가부터, 구성 사건은 따로 등록 안 함)
- 11-07 밤 재점검 14절 순서대로: ① 공개 등록 증명(proof_record → 공개 저장소 gh-pages proof/{slug}.json, 날짜 줄 `등록 증명` 링크 = 그 파일의 커밋 기록) ② 가벼운 페이지(날짜 줄 = 게시 · 사건 · 결과 셋 + 등록 증명, 현재 증시 · 한국 · 분위기는 `지금은?` 접기 하나) ④ 공개 = fc["publish"] 가 False 가 아닌 전망만(EH-001 전망 1 = 사후 등록 샘플 → 내부)
- 11-07 밤 틀림의 가치 (사용자: 인하는 됐는데 S&P 500 이 빠지면? 교정하나?): 교정 안 함(사전 등록). 고리 상태 `끊김`(대리 지표가 반대) + 틀린 뒤 `어디서 끊겼나` 카드(fc["broke"]: 끊긴 고리 · 미리 적어 둔 갈림점 중 일어난 쪽 · 등록 때 경고 · 다음 세부 전망)
- 운영자 확인용(operator_box) = 목업에서만 그리는 회색 작은 글씨 상자 — 쓰인 요인(80개 중) · 이슈 코드 · 범위 비율 · 동행 · 겹침 · 규칙 버전. 발행 코드는 op 를 넘기지 않는다.
"""
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

# ---------------------------------------------------------------- 용어 · 색
DIR_WORD = {1: "상승", -1: "하락"}
THEME = {1: "positive", -1: "negative", 0: "neutral"}
INK = {1: dk.UP, -1: dk.DOWN, 0: "#111"}
PHASE_INK = {"negative": dk.DOWN, "positive": dk.UP}
RESULT = {"hit": "맞음", "miss": "틀림", "neither": "어느 쪽도 아님", "hold": "판정 보류", "void": "무효"}
EARLY = 1 / 3            # 조짐 = 금의 3분의 1
R_EARLY, R_HIT = 0.25, 0.5   # 반등 · 조정 조짐 = 충격 폭 4분의 1 회복(반납), 반등 · 조정 = 절반
REV = {-1: ("반등", "회복"), 1: ("조정", "반납")}   # 충격 방향 → (갈래 말, 동사)
SHOCK = {-1: "급락", 1: "급등"}
RULES = "EH-2026-11-07b"   # 자 β 조정 · 뉴스 유무 갈림 · 비율 · 고정 시점 병기
NEWS_TILT = 0.10            # 뉴스 유무 갈림 — 1위 이슈 뚜렷하면 지속 쪽 10%p, 원인 미상이면 반등 · 조정 쪽 10%p (Chan 2003)


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


def pick_side(rate_rev, news):
    """틀 R 우리 전망 — ① 뉴스 유무 ② 같은 종류 기록 비율. rate_rev = 기록상 반등(조정) 비율 m/n, news = 1위 이슈 뚜렷(True) · 원인 미상(False).
    → (갈래 번호 1=반등·조정 / 2=지속, 그 갈래의 확률, 설명)."""
    p = min(0.95, max(0.05, rate_rev - (NEWS_TILT if news else -NEWS_TILT)))
    side = 1 if p >= 0.5 else 2
    why = f'기록상 {rate_rev * 100:.0f}% {"−" if news else "+"} 뉴스 {"동반(지속 가중)" if news else "없음(되돌림 가중)"} {NEWS_TILT * 100:.0f}%p → {p * 100:.0f}%'
    return side, (p if side == 1 else 1 - p), why


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


def num_html(text):
    """증감 숫자 = 증감 색 + 굵게 (가이드 3-3-1). 부호 있는 숫자는 부호로, 부호 없는 차이는 뒤 말로 방향을 정한다."""
    h = dk.esc(text)
    h = _SIGNED.sub(lambda m: f'<b style="color:{dk.UP if m.group(1)[0] == "+" else dk.DOWN};">{m.group(1)}</b>', h)
    return _GAP.sub(lambda m: f'<b style="color:{dk.DOWN if any(w in m.group(2) for w in ("빠", "뒤처", "내렸")) else dk.UP};">{m.group(1)}</b>{m.group(2)}', h)


# ---------------------------------------------------------------- 판정 엔진 — 숫자 → 국면 · 판정 (사람 손 없음, 기획 8-2)

def move_text(fc, v, ref=None):
    """자의 값 → 쉬운 문장. 상대 자(cmp 있음) = `반도체가 시장보다 3.4%p 더 빠졌습니다`, 절대 자 = `S&P 500 이 결정일 종가보다 4.1% 내렸습니다`."""
    unit, a = fc.get("unit", "%p"), abs(v)
    if fc.get("cmp"):
        return f'{fc["subj_ga"]} {fc["cmp"]} {a:.1f}{unit} 더 {"올랐" if v > 0 else "빠졌"}습니다'
    return f'{fc["subj_ga"]} {ref or fc.get("ref") or fc["ruler_from"]} {a:.1f}{unit} {"올랐" if v > 0 else "내렸"}습니다'


PRICED_WORDS = {"priced_in": "선반영 중"}


def _entry(day, key, label, d, text, rel, theme=None):
    return {"day": day, "key": key, "label": label, "dir": d, "theme": theme or "neutral", "text": text, "rel": rel}


def judge(fc, days, rel, cond=None, vix=None):
    """전망 하나의 날마다 기록 → state. days · rel = 자의 기준일부터의 값(None = 아직 없는 날, 그래프 빈 자리).
    틀 S(kind pre): 기준일 = 사건 결과일 종가. cond = 일어난 조건 번호(None = 사건 전).
    틀 R(kind after): 기준일 = 충격 전날 종가, fc["gap"] = 등록 때 적은 충격 폭(고정). fc["pick"] = 우리 전망 갈래.
    창 = fc["end_day"](D+60) 까지 금을 넘지 않으면 `어느 쪽도 아님`. 판정한 날에서 기록을 멈춘다(다음 움직임은 다음 전망의 몫)."""
    L, unit, sc = fc["line"], fc.get("unit", "%p"), fc["scenarios"]
    reg = fc["registered"]
    log = [_entry(reg, "start", "지켜보는 중", 0, fc["start_text"], 0.0)]
    result, last_rel, recov, ev_off = None, None, None, 0.0
    if fc.get("void"):   # 사건 취소 · 연기 · 자료 결함 → 무효: 채점하지 않고 멈춘다. 새 날짜가 있으면 세부 전망으로 다시 적는다
        v = fc["void"]
        log.append(_entry(v["day"], "void", RESULT["void"], 0, v["text"], 0.0))
        return {"log": log, "result": {"word": RESULT["void"], "crossed": None, "day": v["day"]}, "cond": None, "rel": None, "days": days, "rel_series": rel, "fixed": {}, "vix": None}
    missing = []   # 자료가 빈 날 — 멈추지 않고 건너뛴다 (2026-11-07 사용자: 하루 누락이면 틀이 망가지나? → 전엔 여기서 break 했다). 빈 날은 '자료 대기' 로 기록하고 다음 날 채워지면 그날부터 이어 잰다
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
                tag = f'시장 예상({fc["outcomes"][0]} {mp}%)이 먼저 반영되는 중입니다.' if mp else "결과 전에 먼저 움직이는 중입니다."
                log.append(_entry(day, "priced_in", "선반영 중", d0, f"{move_text(fc, r, ref=f'감지일({md(det)}) 종가보다')}. {tag}", r))
                continue
            if day < fc["event_day"] or cond is None:
                continue
            if det and day == fc["event_day"]:
                ev_off = r   # 결과일 종가로 자를 다시 놓는다
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
            if day == fc["event_day"]:
                mp = fc.get("market_prob")
                sur = ""
                if mp:
                    pc = mp["probs"][cond - 1]
                    sur = f' 시장이 {pc}%로 본 쪽이라 예상대로입니다.' if pc >= 50 else f' 시장은 {100 - pc}%로 반대쪽을 봤던 터라 예상 밖입니다.'
                log.append(_entry(day, "base", "지켜보는 중", 0, f'결과가 나왔습니다 : {fc["outcomes"][cond - 1]}.{sur} 이날 종가부터 잽니다.', r))
                continue
            a = sc[cond - 1]
            dd = a["dir"]
            x = dd * r
            mv = move_text(fc, r)
            if a.get("priced"):   # 이미 반영 갈래 — 더 가면 틀림, 되돌리거나 20거래일 기준 안이면 맞음
                if x >= L:
                    result = {"word": RESULT["miss"], "crossed": None, "day": day}
                    log.append(_entry(day, "miss", RESULT["miss"], dd, f'{mv}. 결과 뒤에도 기준({L:g}{unit}) 넘게 더 가, ‘{a["name"]}’이 틀렸습니다 — 먼저 반영된 것이 다가 아니었습니다.', r, THEME[dd]))
                    break
                if -x >= L:
                    result = {"word": RESULT["hit"], "crossed": cond, "day": day}
                    log.append(_entry(day, "hit", RESULT["hit"], -dd, f'{mv}. 결과가 나오자 되돌려 ‘{a["name"]}’이 맞았습니다 — 먼저 올랐던 만큼 돌려준 모양입니다.', r, THEME[-dd]))
                    break
                if fc.get("priced_end") and day >= fc["priced_end"]:
                    result = {"word": RESULT["hit"], "crossed": cond, "day": day}
                    log.append(_entry(day, "hit", RESULT["hit"], 0, f'결과 뒤 20거래일 동안 기준({L:g}{unit}) 안에 머물렀습니다. {mv}. ‘{a["name"]}’이 맞았습니다 — 결과 전에 이미 반영된 대로입니다.', r, "neutral"))
                    break
                log.append(_entry(day, "watch", "지켜보는 중", 0, f"{mv}. 아직 기준 안입니다 — 먼저 반영된 대로 가는 중입니다.", r))
                continue
            if x >= L:
                result = {"word": RESULT["hit"], "crossed": cond, "day": day}
                tail = f' 세부 전망 ‘{fc["follow"]["title"]}’ 에서 이어 갑니다.' if fc.get("follow") else ""
                log.append(_entry(day, "hit", RESULT["hit"], dd, f'{mv}. 기준({L:g}{unit})을 넘어 미리 적은 ‘{a["name"]}’이 맞았습니다.{tail}', r, THEME[dd]))
                break
            if -x >= L:
                result = {"word": RESULT["miss"], "crossed": None, "day": day}
                log.append(_entry(day, "miss", RESULT["miss"], -dd, f'{mv}. 미리 적은 ‘{a["name"]}’과 반대로 기준({L:g}{unit})을 넘어 틀렸습니다.', r, THEME[-dd]))
                break
            ahead = f' 기준까지 {L - abs(x):.1f}{unit} 남았습니다. 넘으면 ‘{a["name"] if x >= 0 else fc["subject"] + " " + DIR_WORD[-dd]}’입니다.'   # 앞을 보는 꼬리 (묘사 X)
            if x >= L * EARLY:
                log.append(_entry(day, "lean", f'{a["name"]} 조짐', dd, f'{mv}. ‘{a["name"]}’ 쪽으로 기울고 있습니다.{ahead}', r))
            elif -x >= L * EARLY:
                nm = f'{fc["subject"]} {DIR_WORD[-dd]}'
                log.append(_entry(day, "lean_x", f"{nm} 조짐", -dd, f"{mv}. 미리 적은 것과 반대인 ‘{nm}’ 쪽으로 기울고 있습니다.{ahead}", r))
            else:
                log.append(_entry(day, "watch", "지켜보는 중", 0, f"{mv}. 아직 어느 쪽으로도 기울지 않았습니다.{ahead}", r))
        else:
            gap = fc["gap"]
            s = 1 if gap > 0 else -1
            recov = 1 - r / gap
            ext = s * (r - gap)
            last_rel = r
            b1, b2 = sc[0], sc[1]
            pick = sc[fc["pick"] - 1]["name"]
            crossed = 1 if recov >= R_HIT else (2 if ext >= L else None)
            if crossed:
                ok = crossed == fc["pick"]
                result = {"word": RESULT["hit" if ok else "miss"], "crossed": crossed, "day": day}
                what = (f'{SHOCK[s]} 폭({abs(gap):.1f}{unit})의 {recov * 100:.0f}%를 {REV[s][1]}해 ‘{b1["name"]}’이 일어났습니다' if crossed == 1
                        else f'{SHOCK[s]} 뒤 {ext:.1f}{unit} 더 {"올라" if s > 0 else "빠져"} ‘{b2["name"]}’이 일어났습니다')
                dd = sc[crossed - 1]["dir"]
                log.append(_entry(day, "hit" if ok else "miss", result["word"], dd,
                                  f'{what}. 우리가 고른 ‘{pick}’이 {"맞았" if ok else "틀렸"}습니다.', r, THEME[dd]))
                break
            ahead = (f' ‘{b1["name"]}’까지 {max(0.0, (R_HIT - recov) * abs(gap)):.1f}{unit} 더 {REV[s][1]}하면, ‘{b2["name"]}’까지 {max(0.0, L - ext):.1f}{unit} 더 {"오르면" if s > 0 else "빠지면"}입니다.')
            if recov >= R_EARLY:
                log.append(_entry(day, "lean", f'{b1["name"]} 조짐', b1["dir"], f'{SHOCK[s]} 폭의 {recov * 100:.0f}%를 {REV[s][1]}했습니다. ‘{b1["name"]}’ 쪽으로 기울고 있습니다.{ahead}', r))
            elif ext >= L * EARLY:
                log.append(_entry(day, "lean_x", f'{b2["name"]} 조짐', b2["dir"], f'{SHOCK[s]} 뒤 {ext:.1f}{unit} 더 {"올랐" if s > 0 else "빠졌"}습니다. ‘{b2["name"]}’ 쪽으로 기울고 있습니다.{ahead}', r))
            else:
                log.append(_entry(day, "watch", "지켜보는 중", 0, f"{move_text(fc, r)}. {SHOCK[s]} 뒤 아직 어느 쪽으로도 기울지 않았습니다.{ahead}", r))
        if fc.get("end_day") and day >= fc["end_day"] and not result:
            result = {"word": RESULT["neither"], "crossed": None, "day": day}
            log[-1] = _entry(day, "neither", RESULT["neither"], 0, f'60거래일 안에 기준({L:g}{unit})을 넘지 않았습니다. {move_text(fc, r)}. 어느 쪽도 아닙니다.', r)
            break
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
    st = {"log": log, "result": result, "cond": cond, "rel": last_rel, "days": days, "rel_series": rel, "fixed": fixed, "missing": missing,
          "vix": vix[[j for j, v in enumerate(rel) if v is not None][-1]] if vix else None}
    if fc["kind"] == "after" and last_rel is not None:
        st["recovery"] = max(0.0, (1 - last_rel / fc["gap"]) * 100)
    return st


# ---------------------------------------------------------------- 전망 페이지 — 공용 카드 유형만 (가이드라인 2-1)

CHAIN = {"done": ("확인", "down"), "wait": ("대기", "flat"), "no": ("해당 없음", "flat"), "broken": ("끊김", "caution")}   # 끊김 = 조건은 일어났는데 그 고리의 대리 지표가 반대로 감 (2026-11-07: 틀린 전망의 가치 = 어디서 끊겼나)   # 대기 = 회색, 실제 결과 = 노랑 (P319)
END_PULL = 21   # 강조 카드가 그래프로 끝날 때 아래 여백 당기기 (P140)


def branch_view(fc, st, sc):
    """갈래 카드 하나의 모양 — 답(그 갈래에 일어난 사실) · 테마 · 라벨 · 활성 · 펼침."""
    res, log = st.get("result"), st.get("log") or []
    key = log[-1]["key"] if log else "start"
    if fc["kind"] == "pre":
        cond = st.get("cond")
        if cond is None:
            return {"answer": "지켜보는 중", "theme": "neutral", "label": None, "active": True, "opened": sc["no"] == 1}
        if sc["no"] != cond:
            return {"answer": "일어나지 않음", "theme": "neutral", "label": None, "active": False, "opened": False}
        label, toward = "실제 결과", key == "lean"
    else:
        label = "우리 전망" if sc["no"] == fc["pick"] else None
        toward = (key == "lean" and sc["no"] == 1) or (key == "lean_x" and sc["no"] == 2)
    if res:
        if res.get("crossed") == sc["no"]:
            return {"answer": "일어남", "theme": THEME[sc["dir"]], "label": label, "active": True, "opened": True}
        return {"answer": "일어나지 않음", "theme": "neutral", "label": label, "active": bool(label), "opened": bool(label)}
    return {"answer": "조짐" if toward else "지켜보는 중", "theme": "neutral", "label": label, "active": True,
            "opened": fc["kind"] == "pre" or sc["no"] == fc.get("pick")}


def _scenario_card(sc, v):
    """갈래 카드 = 데일리 질문 카드(강조 카드 · 접기, 가이드 2-7) — 첫 줄 조건 + 라벨 · 오른쪽 답. 펼치면 고리 줄 + `이 전망이 맞으면`."""
    th, d = v["theme"], sc["dir"]
    ink = INK[d] if v["answer"] in ("일어남", "조짐") else ("#111" if v["active"] else dk.MUTED)
    def box(state):   # 근거 줄 값 = 라벨 박스(확인 = 그 갈래 방향 색, 대기 · 해당 없음 = 회색). 질문 카드는 <span 으로 시작하는 값을 그대로 쓴다(P330)
        word, kind = CHAIN[state]
        k = (("down" if d < 0 else "up") if v["active"] else "flat") if kind == "down" else kind
        return TS.box(k, word, dk.esc, sym=False, fit=True)
    lines = [("row", c["step"], box(c["state"]), c["ev"]) for c in sc["chain"]] + [("row", f'‘{sc["name"]}’ 이 되는 기준', "", sc["win"])]   # 옛 `이 전망이 맞으면` — 지시어 대신 갈래 이름 (2026-11-07 사용자)
    if sc.get("odds"):   # 우리 전망 갈래 — 기록상 n번 중 m번 (개선 ②: 확률이 있어야 실력을 잰다)
        m, n, note = sc["odds"]
        lines.insert(0, ("row", "기록상", f"{n}번 중 {m}번", note))
    html = qc.question_card(sc["cond"], v["answer"], th, ink, lines, fold=True, opened=v["opened"])
    if v["label"]:
        last = dk.esc(sc["cond"]).rpartition(" ")[2]
        html = html.replace(f'{last}</span>', f'{last}<span style="display:inline-block;margin-left:8px;vertical-align:2px;">{TS.box("caution", v["label"], dk.esc, sym=False, fit=True)}</span></span>', 1)
    if not v["active"]:
        html = html.replace("color:#111;", f"color:{dk.MUTED};")
    return html


def _now_block(fc, st):
    """현재 증시는? = 질문 카드 — 쉬운 말 한 줄 · 근거 줄 · 카드 안 그래프(금 선 · 평소 비교선)."""
    log = st.get("log") or []
    e = log[-1] if log else _entry("", "start", "지켜보는 중", 0, "", 0.0)
    unit, L = fc.get("unit", "%p"), fc["line"]
    sent = e["text"].split(". ")[0] + "." if e["text"] else ""
    lines = [("SENTENCE_SLOT", "plain"), ("row", fc["ruler_short"], fmt_v(st.get("rel"), unit), fc["ruler_from"] + (" · 시장 움직임의 몫을 뺀 값" if fc.get("beta") else ""))]
    if st.get("volume_x"):   # 거래량 배수 (개선 ⑤) — 되돌림은 거래량 없는 급변에서 흔하다
        lines.append(("row", "거래량", f'평소의 {st["volume_x"]:.1f}배', "60일 평균 대비"))
    if fc["kind"] == "after":
        rec = st.get("recovery")
        s0 = 1 if fc["gap"] > 0 else -1
        lines.append(("row", f'{REV[s0][1]}한 비율', f"{rec:.0f}%" if rec is not None else "—", f'{SHOCK[s0]} 폭 {abs(fc["gap"]):.1f}{unit} 대비'))
    if st.get("vix") is not None:
        lines.append(("row", "불안 지수 (VIX)", f'{st["vix"]:.1f}', ""))
    days, vals = st.get("days", []), st.get("rel_series", [])
    if days:
        n = len(days)
        at = st.get("label_at") or [0, n // 2, n - 1]
        labels = [md(dd) if i in at else "" for i, dd in enumerate(days)]
        if fc["kind"] == "pre":
            guides = [(f"상승 기준 +{L:g}{unit}", [L] * n, "#FCA5A5", "dash"), (f"하락 기준 -{L:g}{unit}", [-L] * n, "#93C5FD", "dash")]
        else:
            g, s = fc["gap"], (1 if fc["gap"] > 0 else -1)
            guides = [(f"{REV[s][0]} 기준", [g * 0.5] * n, "#FCA5A5" if s < 0 else "#93C5FD", "dash"), (f"{DIR_WORD[s]} 지속 기준", [g + s * L] * n, "#93C5FD" if s < 0 else "#FCA5A5", "dash")]
        if fc.get("baseline") is not None:
            guides.append((f'{fc.get("baseline_label", "평소")} {fc["baseline"]:+.1f}', [fc["baseline"]] * n, dk.CHART_CMP, "dash"))
        gr = dk.trend_card(f'{fc["ruler_short"]} ({unit})', labels, [(fc["ruler_short"], vals, dk.CHART_MAIN, "solid")] + guides, lambda v: fmt_v(v, unit))
        lines.append((f'<span data-end-chart="1" style="display:block;margin:0 0 -{END_PULL}px;">{gr}</span>', "html"))
    html = qc.question_card("현재 증시는?", e["label"], e["theme"] if e["theme"] in qc.CARD_DIR else "neutral", INK[e["dir"]], lines, fold=True, opened=True)
    return html.replace("SENTENCE_SLOT", num_html(sent))


def _pressure_card(fc):
    """지금 시장 분위기는? — 층 사이 압력 (2026-11-07 사용자: 거시 → 업종 → 종목으로 분위기가 내려오고, 그 분위기는 언론이 키운다. 케이스가 서로 단절돼 보이면 안 된다).
    fc["pressure"] = {"answer": 한 마디, "rows": [(이름, 값, 근거)]} — 값은 이미 매일 나오는 우리 판정(signal_groups regime · shock · sector_flow · news)과 공포 · 탐욕 지수 그대로.
    fc["parent"] = (no, title, slug) 위 층 전망, fc["children"] = [(no, title, slug)] 아래 층 전망. 전망은 혼자가 아니라 사슬의 한 칸으로 보인다."""
    pr = fc.get("pressure")
    if not pr and not fc.get("parent") and not fc.get("children"):
        return ""
    lines = [(f"주식은 혼자 움직이지 않습니다. 시장 → 업종 → 종목 순으로 분위기가 내려오고, 그 분위기는 뉴스와 방송이 키웁니다. ‘{fc['title']}’ 위에 있는 흐름입니다.", "plain")]
    if pr:
        lines += [("row", k, v, n) for k, v, n in pr["rows"]]
    if fc.get("parent"):
        n, t, sl = fc["parent"]
        lines.append((f'‘{dk.esc(fc["title"])}’ 는 <a href="{page_url(sl)}" style="color:#111;">‘{dk.esc(t)}’</a> 에서 내려온 세부 전망입니다. ‘{dk.esc(t)}’ 의 지금 국면이 배경입니다.', "html"))
    for n, t, sl in fc.get("children", []):
        lines.append((f'세부 전망 : <a href="{page_url(sl)}" style="color:#111;">‘{dk.esc(t)}’</a>', "html"))
    return qc.question_card("지금 시장 분위기는?", pr["answer"] if pr else "사슬 보기", "neutral", "#111", lines, fold=True, opened=bool(pr))


def _broke_card(fc):
    """어디서 끊겼나 — 틀린 전망의 가치 (2026-11-07 사용자). fc["broke"] = {"lead", "items": [(이름, 글, 근거)]}. 변명이 아니라 미리 적어 둔 것과 대조만."""
    b = fc.get("broke")
    if not b:
        return ""
    lines = [(b["lead"], "plain")]
    for cond, rec, watch in b["items"]:
        lines.append((f'<span style="display:block;padding:10px 0 0;font-size:{dk.EMPH_Q};line-height:{dk.LH_EMPH_Q};font-weight:700;color:#111;word-break:keep-all;">{dk.esc(cond)}</span>'
                      f'<span style="display:block;margin-top:2px;font-size:{dk.NAME};line-height:{dk.LH_CARD};color:#333;word-break:keep-all;">{num_html(rec)}</span>'
                      + (f'<span style="display:block;margin-top:2px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};word-break:keep-all;">{dk.esc(watch)}</span>' if watch else ""), "html"))
    return qc.question_card("어디서 끊겼나", b.get("answer", "고리 대조"), "neutral", "#111", lines, fold=True, opened=True)


def _prepare_card(fc):
    """앞으로 올 수 있는 일 — 경고 · 대비 카드 (2026-11-07 사용자: 묘사가 아니라 "이렇게 되면 이런 일이 올 수 있으니 미리 생각해 두자").
    fc["prepare"] = {"lead": 한 줄, "items": [(조건, 기록상 한 줄, 볼 것)], "chain": 사슬 한 줄(없으면 생략)}.
    규칙: 조건부(“~하면”) + 기록상 n번 중 m번 + 볼 것. 매수 · 매도 · 비중 말 없음. 날짜 붙은 ‘위험 구간’ 아님 — 다가오는 사건 하나에 묶인 조건부 경고(1절 4-2 예외)."""
    pr = fc.get("prepare")
    if not pr:
        return ""
    lines = [(pr["lead"], "plain")]
    for cond, rec, watch in pr["items"]:   # 조건(굵게) · 문장 · 볼 것(작은 글씨) 세 줄 블록 — row 는 값 칸이 줄바꿈 없음이라 긴 문장에서 카드가 깨진다 (2026-11-07 사용자)
        lines.append((f'<span style="display:block;padding:10px 0 0;font-size:{dk.EMPH_Q};line-height:{dk.LH_EMPH_Q};font-weight:700;color:#111;word-break:keep-all;">{dk.esc(cond)}</span>'
                      f'<span style="display:block;margin-top:2px;font-size:{dk.NAME};line-height:{dk.LH_CARD};color:#333;word-break:keep-all;">{num_html(rec)}</span>'
                      + (f'<span style="display:block;margin-top:2px;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};word-break:keep-all;">볼 것 : {dk.esc(watch)}</span>' if watch else ""), "html"))
    if pr.get("chain"):
        lines.append((pr["chain"], "note"))
    return qc.question_card("앞으로 올 수 있는 일", pr.get("answer", "미리 생각해 둘 것"), "uncertain", "#C2410C", lines, fold=True, opened=True)


def _korea_card(fc):
    """한국은 어떻게? — 미국 사건은 다음 날 아침 한국장으로 연결된다 (‘닿다’ 금지 — 영향 · 이어짐은 연결, 범위 끝은 도달, 2026-11-07) (지도 13-4, 한국 독자의 첫 질문). fc["korea"] = {"lead", "rows": [(이름, 값, 근거)], "note"}.
    값은 기록상 비율 · 배수(2016~ 실측)와 실제 다음 날 값(있으면). 매수 · 매도 말 없음."""
    k = fc.get("korea")
    if not k:
        return ""
    lines = [(k["lead"], "plain")] + [("row", a, b, c) for a, b, c in k["rows"]]
    if k.get("note"):
        lines.append((k["note"], "note"))
    return qc.question_card("한국은 어떻게?", k.get("answer", "다음 날 아침"), "neutral", "#111", lines, fold=True, opened=True)


def _history_card(fc):
    """기록상 비슷한 때는? — 독자가 다음으로 묻는 것(얼마나 더 가나 · 보통은 어땠나)을 기준선으로. 숫자는 중앙값 · 횟수만, 단언 없음.
    fc["history"] = {"what": 조건 문장, "n": 횟수, "since": 시작 연도, "rows": [(기간, 값 글)]}. 없으면 그리지 않는다."""
    h = fc.get("history")
    if not h:
        return ""
    lines = [(f'{h["what"]} {h["since"]}년부터 {h["n"]}번 있었습니다. 그 뒤 몇 번이나 올랐는지와 보통 범위입니다.', "plain")]
    for r in h["rows"]:   # (기간, 값 글) 옛 형식 또는 (기간, 오른 횟수, 범위 글) 새 형식 (개선 ⑦: 중앙값 하나는 한 건에 뒤집힌다)
        if len(r) == 2:
            lines.append(("row", r[0], r[1], ""))
        else:
            k, m, rng = r
            lines.append(("row", f"{k} 올랐다", f'{h["n"]}번 중 {m}번', f"보통 {rng}"))
    for when, name, val in h.get("alike", []):   # 가장 비슷했던 때 셋 (11절 3: 독자는 숫자보다 사건 이름을 기억한다)
        lines.append(("row", f"{when} {name}".strip(), val, "가장 비슷했던 때 · 20거래일 뒤"))
    lines.append(("기록은 눈금일 뿐 이번이 그대로 되풀이된다는 뜻은 아닙니다.", "note"))
    return qc.question_card("기록상 비슷한 때는?", f'{h["n"]}번', "neutral", "#111", lines, fold=True, opened=False)


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
    lines = [(nx["lead"], "plain")] + list(nx["lines"])
    if nx.get("tail"):
        lines.append((nx["tail"], "plain"))
    return qc.question_card(nx.get("title", "앞으로 볼 것은?"), nx.get("answer", "지켜보는 중"), "neutral", "#111", lines, fold=True, opened=False)


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


def _day_entry(e, first, bd):
    """하루 = 날짜 · 국면(18px 굵게, 방향 색) + 아래 문장(증감 색 · 굵게)."""
    return (f'<div style="padding:{0 if first else 14 - dk.VP}px 0 {14 - dk.VP}px;{"" if first else "border-top:1px solid " + bd + ";"}">'
            f'<span style="display:flex;align-items:baseline;gap:10px;font-size:{dk.EMPH_Q};line-height:{dk.LH_EMPH_Q};font-weight:700;">'
            f'<span style="color:#111;white-space:nowrap;">{dk.esc(md(e["day"]))}</span>'
            f'<span style="color:{INK[e["dir"]]};">{dk.esc(e["label"])}</span></span>'
            f'<span style="display:block;margin-top:2px;font-size:{dk.NAME};line-height:{dk.LH_CARD};color:#333;word-break:keep-all;">{num_html(e["text"])}</span></div>')


def _top_card(fc, log):
    """전망 결과 — 날짜 줄(카드 밖, P320) + 강조 카드: 오늘 → `지난 경과 보기` 펼침(날짜 내림차순). 겹침이 있으면 카드 아래 안내 줄."""
    theme = log[-1]["theme"]
    bg, bd = dk.CARD_DIR.get(theme, dk.CARD_DIR["neutral"])
    full = fc["dates"]
    items = full[:2] + ([full[-1]] if len(full) > 2 else [])   # 가볍게: 게시 · 사건 · 결과 셋만 (나머지 — 시장 예상 · 감지 · 최종 — 는 경과 · 경고 카드에) (14절 2)
    proof = (f'<a href="{dk.esc(fc["proof_url"])}" style="color:{dk.SUB};text-decoration:underline;white-space:nowrap;">등록 증명</a>' if fc.get("proof_url") else "")
    dates = (f'<span style="display:flex;flex-wrap:wrap;gap:4px 16px;margin:0 0 8px;{dk.GUIDE_IND}'
             f'font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};">'
             + "".join(f'<span style="white-space:nowrap;{"margin-left:auto;" if i == len(items) - 1 else ""}">{dk.esc(k)} : <b style="color:#111;">{dk.esc(v)}</b></span>'
                       for i, (k, v) in enumerate(items)) + (f'<span>{proof}</span>' if proof else "") + "</span>")
    days = list(reversed(log))
    body = _day_entry(days[0], True, bd)
    if len(days) > 1:
        more = "".join(_day_entry(e, False, bd) for e in days[1:])
        btn = dk.FOLD_IN_CARD.replace("#E2E8F0", bd)
        body += (f'<details data-acc="1" data-fold="1" data-label="지난 경과 보기" style="margin:0;">'
                 f'<summary style="{btn}margin:0 -14px -{dk.EMPH_PAD - dk.VP_EMPH}px;"><span>지난 경과 보기</span> {dk.ACC_CHEV}</summary>'
                 f'<div>{more}</div></details>')
    out = dates + dk.dcard(body, theme=theme)
    for o in fc.get("overlap", []):   # 겹침 — 독자 한 줄. 지시어(이 전망) · 번호(전망 2) 없이 제목으로, `창` 대신 `전망 기간`, 이어 적은 것은 `세부 전망` (2026-11-07 사용자)
        # "효과를 지웠다" 는 단언이지만 "영향을 미친 것으로 보인다" 는 쓸 수 있다 (같은 날 사용자)
        me, other = f'‘{fc["title"]}’', f'‘{o.get("title", "")}’'
        if o.get("role") == "parent":   # 이 전망이 세부 전망 쪽
            text = f'{me} 는 {other} 전망 기간 안에 일어난 {o["event"]}을 따로 적은 세부 전망입니다.'
        else:
            start, end = md(fc.get("event_day") or fc["registered"]), md(fc["end_day"]) if fc.get("end_day") else ""
            text = f'{o["day"]} {o["event"]}이 {me} 전망 기간({start}~{end}) 안에 일어나, 세부 전망 {other} 으로 따로 적었습니다.'
            text += {"same": f' 그 뒤 {fc["subject"]}이 같은 방향으로 더 움직여, {o["event"]}이 힘을 보탠 것으로 보입니다.',
                     "opposite": f' 그 뒤 {fc["subject"]}이 반대 방향으로 움직여, {o["event"]}이 {me} 에 영향을 미친 것으로 보입니다.'}.get(o.get("sign"), "")
        out += f'<span style="display:block;margin:8px 0 0;{dk.GUIDE_IND}font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};">{dk.esc(text)}</span>'
    return out


def forecasts(reg, public=False):
    fs = reg.get("forecasts") or [reg["forecast"]]
    return [f for f in fs if f.get("publish", True)] if public else fs


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


def forecast_body(reg, state=None, fc=None, others=None, op=None):
    """others = 다른 전망 링크 [(no, title, slug)] — 없으면 같은 사건의 전망들. op = 운영자 확인용 [(이름, 값)] — 목업에서만, 발행 때는 None."""
    st = state or {}
    fc = fc or forecasts(reg)[0]
    log = st.get("log") or [_entry(fc["registered"], "start", "지켜보는 중", 0, fc["start_text"], 0.0)]
    head = f'<div data-lead="1" style="margin:0 0 8px;">{dk.section("전망 결과", _top_card(fc, log), line=False)}</div>' + _broke_card(fc) + _prepare_card(fc)
    sides = "<div>" + "".join(_scenario_card(sc, branch_view(fc, st, sc)) for sc in fc["scenarios"]) + "</div>"
    more = (_event_chart(reg) if fc.get("event_chart") else "") + _history_card(fc) + _next_card(fc)
    if others is None:
        others = [(o["no"], o["title"], o["slug"]) for o in forecasts(reg) if o["slug"] != fc["slug"]]
    links = ([dk.dot_li(f'<a href="{page_url(s)}" style="color:#111;">{dk.esc(t)}</a>', size=3, lh=dk.LH_BODY, margin=dk.LI_MARGIN) for n, t, s in others]
             + [dk.dot_li(f'<a href="{page_url(LIST_SLUG)}" style="color:#111;">{dk.esc(CARD_NAME)} 전체 목록</a>', size=3, lh=dk.LH_BODY, margin=dk.LI_MARGIN)])
    body = (head
            + (operator_box(op) if op else "")
            + dk.section("두 갈래 전망", sides, line=False)   # 사건 전 · 충격 뒤 같은 이름 (2026-11-07 재점검: 결과별 · 갈래별 둘로 갈리지 않게)
            + dk.section("지금은?", dk.fold("현재 증시 · 한국 · 시장 분위기 보기", _now_block(fc, st) + _korea_card(fc) + _pressure_card(fc)), line=False)   # 셋을 하나로 접음 (14절 2)
            + dk.section("더 궁금한 것", more, line=False)   # 옛 `더 알아보기` (2026-11-07 사용자: 제목이 이상하다)
            + sec("다른 전망", dk.dot_ul(links), []))
    return dk.fix_colons(f'<div data-list-url="{page_url(LIST_SLUG)}" data-seo-lead="{dk.esc(seo_lead(fc, st))}">{body}</div>')


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
    tags = dk.pill_row("".join(dk.pill(t, kind="area", bare=True) for t in fc.get("tags", [])))
    left = (f'<a href="{page_url(fc["slug"])}" style="display:block;color:#111;font-weight:700;font-size:18px;line-height:34px;text-decoration:none;word-break:keep-all;">'
            f'{dk.esc(fc["title"])}</a>'
            f'<span style="display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;margin:8px 0 1px;line-height:1;">{tags}'
            f'<span style="color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};">{dk.esc(fc["posted"])} 게시</span>'
            + (f'<a href="{dk.esc(fc["record_url"])}" style="color:{dk.SUB};font-size:{dk.TINY};line-height:{dk.LH_TINY};text-decoration:underline;">등록 기록</a>' if fc.get("record_url") else "")
            + "</span>")
    right = f'<b style="color:{INK[e["dir"]]};font-size:{dk.BODY};white-space:nowrap;">{dk.esc(e["label"])}</b>'
    inner = (f'<div data-row-link="1" style="display:flex;justify-content:space-between;align-items:center;gap:12px;">'
             f'<div style="{dk.COL_L}">{left}</div><div style="{dk.COL_R}">{right}</div></div>')
    return dk.dcard(inner, theme=e["theme"])


def scoreboard_card(sc):
    """우리 전망 성적표 (11절 2) — sc = {"n", "hit", "miss", "neither", "watch", "picked_hit": (m, n), "note"}. 겹친 전망은 따로."""
    lines = [("큰 사건마다 결과가 나오기 전에 두 갈래를 적어 두고, 지나고 나서 맞았는지를 그대로 셉니다. 지우거나 고치지 않습니다.", "plain"),
             ("row", "맞음", f'{sc["hit"]}개', ""), ("row", "틀림", f'{sc["miss"]}개', ""), ("row", "어느 쪽도 아님", f'{sc["neither"]}개', ""), ("row", "지켜보는 중", f'{sc["watch"]}개', "")]
    for key, name in (("hold", "판정 보류"), ("void", "무효")):
        if sc.get(key):
            lines.append(("row", name, f'{sc[key]}개', "세지 않음"))
    if sc.get("picked_hit"):
        m, n = sc["picked_hit"]
        lines.append(("row", "우리가 고른 쪽이 맞은 비율", f"{n}번 중 {m}번", "급락 · 급등 뒤 전망만"))
    if sc.get("note"):
        lines.append((sc["note"], "note"))
    return qc.question_card("우리 전망 성적표", f'{sc["n"]}개', "neutral", "#111", lines, fold=True, opened=True)


def list_body(pairs, states=None, done=(), score=None):
    """pairs = [(reg, fc)] 열린 전망, states = {slug: state}, done = [(전망, 결과, 최종)] 끝난 전망(지우지 않고 쌓는다). score = 성적표(없으면 안 그린다)."""
    states = states or {}
    rows = [_row(fc, states.get(fc["slug"], {})) for _, fc in pairs]
    opened = (scoreboard_card(score) if score else "") + ("".join(rows) if rows else dk.muted("지금 지켜보는 전망이 없습니다"))
    tip = "큰 사건마다 두 갈래 전망을 미리 적어 두고, 사건 뒤 날마다 숫자를 한 마디로 바꿔 확인합니다"
    sec1 = f'<div style="margin:12px 0 0;">{opened}</div>'
    if done:
        body2 = dk.table(["전망", "일어난 쪽", "결과"], [list(c) for c in done])
    else:
        body2 = f'<div style="padding:6px 0 4px {dk.ALIGN_PX}px;font-size:{dk.NAME};line-height:{dk.LH_CARD};color:{dk.MUTED};">아직 없습니다</div>'
    sec2 = sec("끝난 전망", body2, [("안내", "확인이 끝난 전망은 지우지 않고 여기 쌓입니다")])
    return dk.fix_colons(f'<div data-list-url="{BLOG}" data-seo-lead="증시 전망, 큰 사건 전에 두 갈래 전망을 적어 두고 숫자로 확인한 기록" data-tip="{dk.esc(tip)}">{sec1 + sec2}</div>')


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
    s1 = judge(f1, days, vals, cond=1, vix=vix)
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
        fc["record_url"] = fc["proof_url"]
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
            print(dk.write_mock(local(forecast_body(r, states[fc["slug"]], fc, others=oth, op=op)), os.path.join(out_dir, f'mock_{fc["slug"]}.html'), forecast_title(fc)))
    score = {"n": 2, "hit": 0, "miss": 0, "neither": 0, "watch": 2, "note": "결과가 나오기 전에 적은 전망만 셉니다. 사건 뒤에 적은 보기는 넣지 않습니다."}
    print(dk.write_mock(local(list_body(pub, states, score=score)), os.path.join(out_dir, f"mock_{LIST_SLUG}.html"), CARD_NAME))
    with open(os.path.join(out_dir, "hypo.json"), "w", encoding="utf-8") as f:
        json.dump(home_card(pub, "2026-11-07T04:00:00Z"), f, ensure_ascii=False, indent=1)
