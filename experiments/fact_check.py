"""서술 문장의 숫자 검사 — 모든 리포트 공용 (2026-10-14 사용자: "a 로 해줘").

왜: 예비 모델 Groq 가 NVDA 서술에서 원본 "데이터센터 매출 직전 분기 대비 +18.4%" 를 "18.4% 감소" 로 썼다.
서술 검증은 금지 표현 · 어미 · 길이만 봐서 그대로 게시될 뻔했다. 게시되는 문장이 틀리는 것이 가장 위험하다.

검사 두 가지 (모델에 보낸 데이터 = source 기준):
1) 숫자: 문장의 숫자(%, 소수, 100 이상, 억 · 조 · 달러 등 단위)는 source 어딘가의 숫자와 표시 자릿수 반올림으로 같아야 한다.
   비율(0.184 → 18.4%) · 단위(962억 → 9.62e10) · 부호 없는 크기도 맞춘다.
2) 방향: 숫자 바로 뒤(또는 앞)에 증가 · 상승 / 감소 · 하락 같은 말이 붙고, source 에 그 크기의 값이 한쪽 부호로만 있으면 부호가 맞아야 한다.
   source 에 부호 없는 크기만 있으면(예: 낙폭 12 로 저장) 방향은 보지 않는다 — 잘못 막지 않는 쪽을 택한다.

크기를 말하는 표현(고점 대비 · 낙폭 · 변동폭)과 크기 칸(dd · range · gap …)은 방향을 보지 않는다.
건너뛰는 숫자: 날짜 · 시각 · 기간(10월 14일, 07:30, 20일 평균, 3분기), 100 미만 정수(건수 · 순위 · RSI 14 등), 연도, 지수 이름(S&P 500, 러셀 2000).
기준은 과거에 실제 게시된 Gemini 서술(nvda 10일 · 트럼프 27일 · 데일리)을 하나도 막지 않는 것 — 바꾸면 scratchpad 의 보정 스크립트로 다시 확인한다.
"""

import re

UNITS = {"조": 1e12, "억": 1e8, "만": 1e4, "천": 1e3, "B": 1e9, "bn": 1e9, "M": 1e6, "K": 1e3, "T": 1e12}
SKIP_AFTER = re.compile(r"^\s*(월|일|년|시|분기|분|초|주(?!가)|개월|거래일|번째|차|위|배|회|명|건|개|bp)")
SKIP_BEFORE = re.compile(r"(S&P\s*|러셀\s*|Russell\s*|RSI\s*|MA\s*|Q|FY|H)$", re.I)
NUM = re.compile(r"(?<![\w.])([+\-−▲▼]?)\s?\$?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s?(%p|%|조|억|만|천|bn|B|M|K|T)?(?![\w])")
UP = re.compile(r"(증가|상승|올라|오른|오름|늘어|늘었|늘|확대|개선|반등|급등|강세|플러스|웃돌|↑)")
# 크기만 저장하는 칸(낙폭 · 변동폭 · 갭 등) — 부호가 방향을 뜻하지 않는다
MAG_KEY = re.compile(r"(dd|drawdown|from_high|off_high|from_low|range|gap|dist|abs|atr|width|낙폭|변동폭|폭)", re.I)
# 문장에서 크기를 말하는 표현 — "고점 대비 12% 하락" 은 낙폭 크기라 방향 검사를 하지 않는다
MAG_TEXT = re.compile(r"(고점 대비|저점 대비|낙폭|하락폭|상승폭|변동폭|등락폭|폭이|폭은|폭\s)")
DOWN = re.compile(r"(감소|하락|내려|내린|내림|떨어|줄어|줄었|축소|악화|급락|약세|마이너스|밑돌|↓|낙폭)")


def _source_numbers(obj, out=None):
    """source 의 모든 숫자 (부호 포함). 문자열 속 숫자도 — ▲ · ▼ · - 를 부호로."""
    if out is None:
        out = []
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, str):
        for m in NUM.finditer(obj):
            v = float(m.group(2).replace(",", "") + ("." + m.group(3) if m.group(3) else ""))
            sign = -1 if m.group(1) in ("-", "−", "▼") else 1
            v *= UNITS.get(m.group(4) or "", 1)
            out.append(sign * v)
            if m.group(1) not in ("-", "−", "▼", "+", "▲"):
                out.append(None)   # 부호를 모르는 크기 — 방향 검사에서 '모름'으로 친다
                out.append(v)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if MAG_KEY.search(str(k)) and isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append(None)   # 크기 칸 — 부호를 모르는 값으로
                out.append(abs(float(v)))
                continue
            _source_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _source_numbers(v, out)
    return out


def _matches(n, decimals, unit_mul, pct, v):
    """문장 숫자 n(표시 자릿수 decimals) 가 source 값 v 의 크기와 같은가."""
    a = abs(v)
    cands = [a * 100, a] if pct else [a / unit_mul]
    if not pct and unit_mul == 1:
        cands.append(a * 100)   # 비율을 %없이 쓴 경우는 드물지만 허용
    tol = 0.5 * 10 ** (-decimals) + 1e-9
    return any(abs(c - n) <= tol for c in cands)


def check(sentences, source):
    """문장 목록 → 문제 목록(빈 목록이면 통과)."""
    vals = _source_numbers(source)
    problems = []
    for s in sentences:
        if not isinstance(s, str):
            continue
        for m in NUM.finditer(s):
            sign_txt, intpart, frac, unit = m.group(1), m.group(2), m.group(3), m.group(4) or ""
            before, after = s[:m.start()], s[m.end():]
            if SKIP_AFTER.match(after) or SKIP_BEFORE.search(before[-10:]):
                continue
            if re.match(r"^\s*[:/]\s*\d", after) or re.search(r"\d\s*[:/]\s*$", before):   # 07:30 · 10/14
                continue
            n = float(intpart.replace(",", "") + ("." + frac if frac else ""))
            pct = unit in ("%", "%p")
            if not frac and not unit and n < 100:
                continue
            if not frac and not unit and 1900 <= n <= 2100:
                continue
            decimals = len(frac) if frac else 0
            mul = UNITS.get(unit, 1)
            hits = [v for v in vals if v is not None and _matches(n, decimals, mul, pct, v)]
            if not hits:
                problems.append(f"원본에 없는 숫자 {m.group(0).strip()}: {s[:80]}")
                continue
            # 방향 — 숫자 앞뒤 12자 안의 말 (숫자 뒤가 우선)
            word = after[:12]
            say_up, say_down = bool(UP.search(word)), bool(DOWN.search(word))
            if not (say_up or say_down):
                word = before[-12:]
                say_up, say_down = bool(UP.search(word)), bool(DOWN.search(word))
            if sign_txt in ("+", "▲"):
                say_up, say_down = True, False
            elif sign_txt in ("-", "−", "▼"):
                say_up, say_down = False, True
            if say_up == say_down or MAG_TEXT.search(before[-12:] + s[m.start():m.end()] + after[:8]):
                continue
            unsigned = any(vals[i - 1] is None and vals[i] is not None and _matches(n, decimals, mul, pct, vals[i])
                           for i in range(1, len(vals)))
            if unsigned or any(v == 0 for v in hits):
                continue
            pos, neg = any(v > 0 for v in hits), any(v < 0 for v in hits)
            if say_up and neg and not pos:
                problems.append(f"방향 반대 (원본은 감소) {m.group(0).strip()}: {s[:80]}")
            elif say_down and pos and not neg:
                problems.append(f"방향 반대 (원본은 증가) {m.group(0).strip()}: {s[:80]}")
    return problems



def split_sentences(text):
    parts = re.split(r"(?<=\.)\s+", text.strip())
    return [p for p in parts if p.strip()]


def drop_bad(text, source):
    """문단에서 숫자 검사에 걸린 문장만 뺀다 → (고친 글, 문제 목록). 모든 모델이 검사에 걸린 날의 마지막 수단 (데일리)."""
    keep, problems = [], []
    for sent in split_sentences(text):
        p = check([sent], source)
        if p:
            problems += p
        else:
            keep.append(sent)
    return " ".join(keep), problems
