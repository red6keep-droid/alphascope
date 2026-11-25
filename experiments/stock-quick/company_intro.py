"""종목 주가(간단 종목) 기업 소개 두 문장 — 한 번 만들어 저장, 다시 부르지 않는다 (2026-11-15 사용자).

왜: 종목마다 고정 페이지(전용 주소)를 만들면, 같은 틀로 찍은 853개가 서로 닮아 구글이 색인하지 않을 수 있다
    (11-10 정식 미국 종목 `크롤링됨 - 현재 색인 생성되지 않음` → 맨 앞 요약 닮음 87% → 74% 로 낮춘 일). 회사마다 다른 소개 문장이 가장 큰 차이.
모양: 정식 종목 소개(universe.ABOUT · universe_kr.ABOUT)와 같은 꼴 — "스타벅스는 … 기업이다. …" 두 문장, 숫자 없음.
      첫 문장 = 맨 앞 요약 아래 10px ※ 줄(lead_note), 전체 = `기업` 탭 소개. 정식 렌더러가 ABOUT 표를 읽으므로 apply() 가 표에 넣기만 한다.

재료: 야후 회사 설명(info.longBusinessSummary, 영어) — 하루 FETCH_CAP 종목까지 받아 저장(받은 날짜와 함께, 빈 설명도 저장해 다시 안 받음).
AI: Gemini lite 만(사슬 json-lite-only), 20종목 묶음, 하루 CALL_CAP 번까지 (2026-11-15 사용자: 급하지 않으니 lite 남는 몫으로).
    하루 한도(429 PerDay)면 사슬이 그 모델을 버리고 RuntimeError → 즉시 멈추고 다음 날 이어서. flash · Groq 로 넘기지 않는다.
    검사 통과 못 한 문장은 버린다(다음 날 다시). 야후 설명이 없는 종목 = 업종 문장(파이썬, AI 0).
저장: --cache(비공개 quick-state)/intro.json {sym: {"ko", "src": "yahoo"|"sector", "at", "model"}} · intro_src.json {sym: {"en", "at"}}

    .venv/bin/python experiments/stock-quick/company_intro.py --cache DIR [--only UBER,259960.KS] [--fetch N] [--calls N] [--dry]
"""
import argparse
import datetime
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [EXP, os.path.join(EXP, "stock-radar"), os.path.join(EXP, "kr-stocks")]

import design_kit as dk  # noqa: E402

FETCH_CAP = 200   # 하루 야후 회사 설명 받기 상한 — 상세 값(미국 90 · 한국 60)과 합쳐도 야후 요청이 몰리지 않게. 768종목이면 약 4거래일
CALL_CAP = 25     # 하루 Gemini lite 호출 상한 = 하루 500회의 5% (2026-11-15 사용자 합의)
BATCH = 20
SRC_CHARS = 700   # 설명 앞부분만 — 첫 몇 문장에 무엇을 하는 회사인지가 있다

PROMPT = """아래는 상장 회사들의 영어 회사 설명이다. 회사마다 한국어 소개를 정확히 두 문장으로 써라.
- 첫 문장: "<한국어 회사 이름>은 … 기업이다." 또는 "<이름>는 …" (받침에 맞는 조사 하나만) 꼴로, 이 회사를 다른 회사와 구별하는 핵심 사업 하나를 구체적으로(예: "온라인 게임을 만드는", "차량 호출 앱을 운영하는").
  '관련 사업 · 솔루션 · 서비스를 제공하는' 같은 막연한 말과 지역 나열은 쓰지 마라. 회사 이름은 주어진 한국어 이름 그대로, 조사는 받침에 맞게.
- 둘째 문장: 설명에 나온 대표 제품 · 브랜드 · 서비스 이름과 주요 고객을 구체적으로. 예: "대표 게임은 …이다." "…와 …를 만들어 …에 판다."
- 업종 칸은 참고만 하고 그 이름을 문장에 그대로 붙이지 마라("식당 기업" X → "커피 전문점을 운영하는 기업" O).
- 문체: 평서체 '-다'로 끝낸다. 각 문장 70자 안팎.
- 숫자 · 연도 · 순위 · 점유율을 쓰지 마라. '최고 · 최대 · 선도 · 혁신 · 세계적' 같은 평가 말, 앞으로의 전망 · 투자 의견을 쓰지 마라.
- 설명에 없는 내용을 지어내지 마라. 영어 고유 제품명은 한국어로 옮기거나 그대로 둔다.
JSON 하나로만 답한다: {"<키>": "<두 문장>", ...} — 아래 모든 키를 빠짐없이.

키\t한국어 이름\t업종\t영어 설명"""


def _now():
    return datetime.date.today().isoformat()


def _load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save(path, v):
    tmp = path + ".tmp"
    json.dump(v, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    os.replace(tmp, path)


def fix_josa(ko, name):
    """첫 머리 `한화는(는)` · `우버은(는)` 처럼 AI 가 지시문의 `은(는)` 을 베낀 것 → 받침에 맞는 조사 하나 (파이썬, dk.josa)."""
    m = re.match(r"^(.+?)\s*(?:은|는)?\s*\((?:은|는)\)\s*", ko or "")
    if m and name and m.group(1).strip() == name:
        return dk.josa(name, "은") + " " + ko[m.end():]
    return ko


def load(cache_dir):
    """{sym: 두 문장} — 렌더러가 쓰는 값만. 조사는 읽을 때도 고친다(예전에 저장된 것)."""
    ref = _load(os.path.join(EXP, "ref", "quick_ref.json"), {})
    names = {s: e.get("ko") or "" for m in ("us", "kr") for s, e in (ref.get(m) or {}).items()}
    return {s: fix_josa(v["ko"], names.get(s, "")) for s, v in _load(os.path.join(cache_dir, "intro.json"), {}).items() if v.get("ko")}


def apply(cache_dir):
    """정식 렌더러의 ABOUT 표에 넣는다 — 미국 = 티커, 한국 = 6자리 코드. 정식 종목 문구(직접 쓴 것)는 덮지 않는다."""
    import universe as U
    import universe_kr as K
    n = 0
    for s, ko in load(cache_dir).items():
        if s.endswith((".KS", ".KQ")):
            c = s.split(".")[0]
            if c not in K.ABOUT:
                K.ABOUT[c] = ko
                n += 1
        elif s not in U.ABOUT:
            U.ABOUT[s] = ko
            n += 1
    return n


def check(ko, name):
    """두 문장 · 한국어 · 숫자 없음 · 길이 · 평가 말 없음 · 회사 이름으로 시작."""
    if not isinstance(ko, str):
        return None
    ko = fix_josa(re.sub(r"\s+", " ", ko).strip(), name)
    sents = [x for x in re.split(r"(?<=다\.)\s*", ko) if x]
    hangul = len(re.findall(r"[가-힣]", ko))
    if not (1 <= len(sents) <= 3 and 30 <= len(ko) <= 260 and hangul >= len(ko) * 0.5):
        return None
    if re.search(r"\d", ko) or re.search(r"최고|최대|선도|혁신|세계적|유망|추천|매수|매도|전망", ko):
        return None
    if not ko.endswith("다.") or not ko.startswith(name[:2]):
        return None
    return ko


def sector_sentence(e):
    """야후 설명이 없을 때 — 업종 · 세부 업종으로 (AI 0). 한 문장."""
    name, sub, sec = e.get("ko") or e.get("en"), e.get("sub") or "", e.get("sector") or ""
    what = f"{sec} 업종의 {sub} 기업이다." if sub and sub != sec else f"{sec} 업종 기업이다."
    return f"{dk.josa(name, '은')} {what}"


def fetch_src(syms, cap):
    """야후 회사 설명 — 종목마다 info 한 번. 실패하면 그 종목은 다음 날 다시(저장 안 함)."""
    import yfinance as yf
    got = {}
    for s in syms[:cap]:
        try:
            got[s] = {"en": ((yf.Ticker(s).info or {}).get("longBusinessSummary") or "").strip(), "at": _now()}
        except Exception as e:  # noqa: BLE001
            print(f"[intro] {s} 설명 실패: {str(e)[:80]}")
        time.sleep(0.6)
    return got


def run(cache_dir, ref, only=None, fetch_cap=FETCH_CAP, call_cap=CALL_CAP, dry=False):
    """ref = quick_ref.json — 정식 종목(full)은 건너뛴다(직접 쓴 소개가 있다)."""
    intro_p, src_p = os.path.join(cache_dir, "intro.json"), os.path.join(cache_dir, "intro_src.json")
    intro, src = _load(intro_p, {}), _load(src_p, {})
    entries = {s: e for m in ("us", "kr") for s, e in (ref.get(m) or {}).items() if not e.get("full")}
    if only:
        entries = {s: e for s, e in entries.items() if s in only}
    todo = [s for s in sorted(entries) if s not in intro]

    need_src = [s for s in todo if s not in src]
    if need_src and fetch_cap:
        src.update(fetch_src(need_src, fetch_cap))
        if not dry:
            _save(src_p, src)

    # 설명이 빈 종목 = 업종 문장 (AI 0)
    for s in todo:
        if s in src and not src[s]["en"]:
            intro[s] = {"ko": sector_sentence(entries[s]), "src": "sector", "at": _now(), "model": ""}

    ready = [s for s in todo if s not in intro and (src.get(s) or {}).get("en")]
    calls = made = 0
    if ready and call_cap:
        from llm_chain import LLMPool
        pool = LLMPool("json-lite-only", label="quick-intro")
        for i in range(0, len(ready), BATCH):
            if calls >= call_cap:
                break
            part = ready[i:i + BATCH]
            body = "\n".join(f"{s}\t{entries[s].get('ko') or entries[s].get('en')}\t{entries[s].get('sub') or entries[s].get('sector') or ''}\t"
                             + re.sub(r"\s+", " ", src[s]["en"])[:SRC_CHARS] for s in part)
            calls += 1
            try:
                val = pool.generate_json(PROMPT + "\n" + body, temperature=0.2, max_tokens=4000)
            except Exception as e:  # noqa: BLE001 — 하루 한도(PerDay) 포함: 멈추고 다음 날 이어서
                print(f"[intro] AI 멈춤 — 다음 실행에 이어서: {str(e)[:160]}")
                break
            for s in part:
                ko = check((val or {}).get(s) if isinstance(val, dict) else None, entries[s].get("ko") or "")
                if ko:
                    intro[s] = {"ko": ko, "src": "yahoo", "at": _now(), "model": pool.last_model or ""}
                    made += 1
    if not dry:
        _save(intro_p, intro)
    left = sum(1 for s in entries if s not in intro)
    print(f"[intro] 설명 받음 {sum(1 for s in need_src[:fetch_cap] if s in src)} · AI {calls}번 · 새 소개 {made}"
          f" · 업종 문장 {sum(1 for v in intro.values() if v['src'] == 'sector')} · 전체 {len(intro)}/{len(entries)} · 남음 {left}")
    return intro


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--fetch", type=int, default=FETCH_CAP)
    ap.add_argument("--calls", type=int, default=CALL_CAP)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    ref = _load(os.path.join(EXP, "ref", "quick_ref.json"), {})
    only = {x.strip() for x in a.only.split(",") if x.strip()} or None
    out = run(a.cache, ref, only, a.fetch, a.calls, a.dry)
    for s in sorted(only or [])[:10]:
        print(s, "→", (out.get(s) or {}).get("ko"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv

    load_dotenv(os.path.join(EXP, "..", ".env"))
    main()
