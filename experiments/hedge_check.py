"""말투 검사 (hedge_check) — AI 요약이 원문의 '대략 · 예상' 을 빼서 추정을 확정된 사실처럼 쓰는 것을 막는다 (2026-11-12 사용자).

사례: 폭스 비즈니스 방송 "ANTHROPIC'S REVENUES GREW, LIKE, 145 PERCENT … AROUND 45% OR SO … LOOKS LIKE … 25%" →
요약 "앤트로픽의 분기별 매출 성장률이 145%에서 45% 그리고 25%로 둔화" (발언자 추정이 사실처럼 읽힘).

규칙 (파이썬 글자 대조, AI 없음):
- 한국어 줄의 숫자마다 원문(영어)에서 같은 값의 숫자를 찾고, 그 숫자가 든 원문 문장에 예상 말(expect · forecast · could · looks like …)이나
  어림 말(about · around · like · roughly …)이 있는지 본다. 같은 값이 원문 여러 곳에 있으면 모두 그런 말과 함께일 때만 친다(한 곳이라도 단정이면 단정).
- 예상 말인데 한국어 줄에 `예상 · 전망 · 추정 · 목표 · 계획 · 예정 · 가이던스` 같은 말이 없으면 줄 끝에 ` (예상)`.
- 어림 말인데 그 숫자 앞뒤에 `약 · 가량 · 안팎 · 정도 · 이상 · 넘게 · 가까이 · 수준` 이 없으면 숫자 앞에 `약 `.
- 원문에 없는 숫자는 여기서 보지 않는다 — 그건 news_store._num_problem · fact_check 가 이미 뺀다.
쓰는 곳: news_summary._check (기사 요약 다섯 줄) · people-radar/narrate (인물 발언 헤드라인 · 설명). 방송 요약은 자막을 가진 수집기(yutb-sub)에 같은 규칙.
"""

import re

EN_UNIT = {"%": "%", "percent": "%", "trillion": 1e12, "tn": 1e12, "t": 1e12, "billion": 1e9, "bn": 1e9, "b": 1e9,
           "million": 1e6, "mn": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}
KO_UNIT = {"%": "%", "퍼센트": "%", "천억": 1e11, "백억": 1e10, "십억": 1e9, "조": 1e12, "억": 1e8, "천만": 1e7, "백만": 1e6, "십만": 1e5, "만": 1e4, "천": 1e3}
EN_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(%|percent|trillion|billion|million|thousand|tn|bn|mn|[tbmk](?![a-z0-9]))?", re.I)
KO_NUM = re.compile(r"(?<![A-Za-z\d.])(\d[\d,]*(?:\.\d+)?)(?![A-Za-z\d])\s*(%p|%|퍼센트|천억|백억|십억|조|억|천만|백만|십만|만|천)?\s*(월|일|년|분기|위|시|세대|호)?")

FWD_EN = re.compile(r"\b(expect\w*|forecast\w*|project(?:s|ed|ion\w*)|estimat\w*|guid\w*|outlook|could|(?:may|might)(?=\s+(?:not\s+)?(?:be|have|rise|fall|reach|see|hit|grow|decline|increase|drop|top|exceed|need|take|slow|climb|jump|surge|slip|end))|likely|looks like|seen at"
                    r"|price target|targets?\s+(?:of|to)|targeting|predict\w*|anticipat\w*|on track to|poised to)\b", re.I)   # `May 5` · `Target Corp` 는 아님
APPROX_BEFORE = re.compile(r"\b(about|around|roughly|approximately|nearly|almost|like|close to|some|an estimated|est\.)[\s,$]*$", re.I)   # 숫자 바로 앞 (`companies like Nvidia` 는 아님)
APPROX_AFTER = re.compile(r"^[\s%a-z]{0,12}\bor so\b", re.I)                                                                          # 숫자 바로 뒤 `45% or so`
KO_FWD = re.compile(r"예상|전망|추정|목표|계획|예정|가이던스|관측|가능|볼|보고|기대|우려")
KO_APPROX = re.compile(r"약\s*$|가량|안팎|정도|남짓|이상|넘게|넘는|가까이|수준|여\s")


def _val(num, unit, units):
    v = float(num.replace(",", ""))
    u = units.get((unit or "").lower(), 1) if unit else 1
    if unit == "%p":
        return ("%", v)
    return ("%", v) if u == "%" else ("n", v * u)


def _sentence(text, i, j):
    """원문에서 [i, j) 숫자가 든 문장 — 마침표 · 물음표 · 줄바꿈 · 자막 시각 표시([03:18])로 끊는다."""
    a = max(text.rfind(c, 0, i) for c in (". ", "? ", "! ", "\n", "] "))
    b = [k for k in (text.find(c, j) for c in (". ", "? ", "! ", "\n", " [")) if k != -1]
    return text[a + 1 if a >= 0 else 0: min(b) if b else len(text)]


def _src_hedge(kind, v, src):
    """원문에서 같은 값의 숫자들 → ("fwd" | "approx" | None). 모든 자리가 그런 말과 함께일 때만."""
    marks = []
    for m in EN_NUM.finditer(src):
        k, s = _val(m.group(1), m.group(2), EN_UNIT)
        if k != kind or abs(s - v) > max(abs(v), 1e-9) * 0.02:
            continue
        sent = _sentence(src, m.start(), m.end())
        approx = APPROX_BEFORE.search(src[max(0, m.start() - 20):m.start()]) or APPROX_AFTER.search(src[m.end():m.end() + 14])
        marks.append("fwd" if FWD_EN.search(sent) else "approx" if approx else None)
    if not marks or None in marks:
        return None
    return "fwd" if "fwd" in marks else "approx"


def hedge(ko, src):
    """한국어 줄 · 원문 → (고친 줄, 고친 이유 목록). 고칠 것이 없으면 (ko, [])."""
    ko, src = str(ko or ""), str(src or "")
    if not ko or not src:
        return ko, []
    why, fwd, approx_at = [], False, []
    for m in KO_NUM.finditer(ko):
        if m.group(3):   # 날짜 · 순위 · 분기 숫자
            continue
        kind, v = _val(m.group(1), m.group(2), KO_UNIT)
        h = _src_hedge(kind, v, src)
        if h == "fwd":
            fwd = True
        elif h == "approx":
            near = ko[max(0, m.start() - 3):m.start()] + ko[m.end():m.end() + 6]
            if not KO_APPROX.search(near):
                approx_at.append(m.start())
    for i in sorted(approx_at, reverse=True):
        ko = ko[:i] + "약 " + ko[i:]
        why.append("어림")
    if fwd and not KO_FWD.search(ko):
        ko = ko + " (예상)"
        why.append("예상")
    return ko, why


def hedge_text(obj):
    """원문 객체(dict · list · str) → 글 하나 (인물 발언 원문 항목처럼 여러 칸에 나뉜 것)."""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " \n".join(hedge_text(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return " \n".join(hedge_text(v) for v in obj)
    return ""


if __name__ == "__main__":   # 사례 시험
    src = ("BECAUSE HERE'S THE THING, AN ANTHROPIC'S REVENUES GREW, LIKE, 145 PERCENT SHE SEQUENTIALLY IN Q2. THAT SLOWED TO AROUND 45% OR SO IN Q3. "
           "[03:29] THAT LOOKS LIKE IT'S SLOWING AGAIN IN Q4 TO, LIKE, 25% GROWTH. SOFTBANK IS TAKING A 3.7 BILLION WRITE-DOWN ON POWER GENERATION EQUIPMENT.")
    more = (" Nvidia posted revenue of $57 billion. Retail sales rose 12% in May. Chipmakers like Nvidia gained 3%. "
            "Target Corp shares fell 8%. Analysts expect fourth-quarter revenue of $65 billion. The deal is worth about $2 billion.")
    for ko in ["앤트로픽의 분기별 매출 성장률이 145%에서 45% 그리고 25%로 둔화", "소프트뱅크 37억 달러 자산 상각 단행", "엔비디아 매출 570억 달러 기록",
               "5월 소매 판매 12% 증가", "엔비디아 등 반도체주 3% 상승", "타깃 주가 8% 하락", "4분기 매출 650억 달러", "4분기 매출 650억 달러 전망", "인수 규모 20억 달러"]:
        print(hedge(ko, src + more))
