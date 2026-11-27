"""분기 · 반기 · 사업보고서 본문 `II. 사업의 내용 > 4. 매출 및 수주상황` — 사업 부문별 매출 · 수주잔고.

정식 한국 종목(35)만. 보고서 하나 = 원문 1회(document.xml) + AI 1회(Gemini lite, 사슬 json-lite-only).
- 원문에서 그 절만 파이썬이 잘라(보통 1천 ~ 5천 자) AI 에게 `표를 그대로 옮겨 적기`만 시킨다 — 더하기 · 해석은 파이썬.
- 막는 장치: AI 가 적은 숫자는 모두 원문에 있어야 한다(쉼표 · 괄호 빼고 대조, 하나라도 없으면 그 보고서 버림). 부문 합 = 표 합계(내부 조정 줄 빼고 ±3% 밖이면 버림).
  못 읽은 보고서는 `fail` 로 남겨 다시 부르지 않는다(카드는 없이).
- 하루 상한 CAP 건 · 보고서 번호별 캐시(data/dart_biz.json, kr-state). 설계 순서 3-2 의 예외: 표 모양이 회사마다 달라 파이썬 틀로 못 읽고,
  Groq 는 분당 8천 토큰이라 긴 절 하나에 걸리며 하루 20만 토큰이 아침에 차는 날이 있어 lite 의 남는 몫으로(기업 소개와 같은 이유). flash 로 넘어가지 않는다.
결과 {접수번호: {"end", "unit", "cur_label", "rows": [{"seg", "item", "cur", "prev"}], "total", "backlog": {"total", "items": [{"name", "v"}]} | None}}

    python experiments/kr-stocks/dart_biz.py 042660 005930      # 시험 — 최근 보고서 5개씩 읽어 출력
"""

import datetime
import io
import json
import os
import re
import sys
import zipfile
from html import unescape

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(BASE))
API = "https://opendart.fss.or.kr/api"
CACHE = os.path.join(BASE, "data", "dart_biz.json")
REPORTS_PER_CO = 5   # 최근 보고서 5개 — 이번 분기 · 1년 전 같은 분기(부문 1년 전 대비) · 수주잔고 다섯 점
CAP = 30
UNIT = {"조원": 1e12, "억원": 1e8, "백만원": 1e6, "천원": 1e3, "원": 1.0}

PROMPT = """다음은 한국 상장사 정기보고서의 '매출 및 수주상황' 절이다. 표에 적힌 숫자를 그대로 옮겨 JSON 하나로만 답하라. 계산 · 합산 · 추정은 하지 마라.
{
 "unit": "표 머리의 단위 (억원 · 백만원 · 천원 · 원 · 조원 중 하나)",
 "cur_label": "매출실적 표의 첫 숫자 열 이름 그대로 (예: 제53기 3분기)",
 "rows": [ {"seg": "사업부문 이름", "item": "품목 · 지역 · 구분 (없으면 빈 글자)", "cur": 첫 숫자 열 값, "prev": 둘째 숫자 열 값 또는 null} ],
 "total": 매출실적 표 합계 행의 첫 숫자 열 값 또는 null,
 "backlog": {"total": 수주잔고 합계 또는 null, "items": [{"name": "품목", "v": 수주잔고}]} 또는 null
}
규칙:
- rows 에는 매출실적 표의 가장 잘게 나뉜 행만 넣는다. 부문 소계 · 합계 · 내부매출 · 연결조정 행은 rows 에 넣지 않는다. 수출 · 내수가 나뉘면 각각 넣고 그 부문 '합 계' 행은 넣지 않는다.
- 숫자는 표 글자 그대로(쉼표만 빼고). 괄호 숫자는 음수. '-' 는 null.
- 수주상황 표가 없거나 '해당사항 없음' 이면 backlog 는 null. 수주잔고 열의 '금액' 값을 쓴다(수량이 아니라).
- 표가 아예 없으면 {"rows": []}.
"""


def _key():
    return os.environ.get("DART_API_KEY", "").strip()


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(path, d):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def _text(x):
    t = re.sub(r"<TR[^>]*>", "\n", x, flags=re.I)
    t = re.sub(r"<T[DHE][^>]*>", " | ", t, flags=re.I)
    t = re.sub(r"<P[^>]*>", "\n", t, flags=re.I)
    t = unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def section(xml):
    """`매출 및 수주상황` 절 글자 — 목차 다음 본문 제목부터 다음 절(5.) 제목 앞까지. 판매경로 · 전략 글은 길어서 뺀다(표만 필요)."""
    hits = [m.start() for m in re.finditer(r"<TITLE[^>]*>\s*\d+\.\s*매출\s*및\s*수주\s*상황\s*</TITLE>", xml)]
    if not hits:
        return ""
    st = hits[-1]
    en = re.search(r"<TITLE[^>]*>\s*\d+\.\s", xml[st + 10:])
    t = _text(xml[st:st + 10 + en.start()] if en else xml[st:st + 200000])
    # `나. 판매경로 · 전략` 글은 표가 아니다 — 그 뒤로는 표 줄 · 짧은 줄(소제목 · 단위)만 남겨 AI 입력을 줄인다. 수주 표 제목이 `다. 수주상황` 이 아닌 회사도 있다(한화오션)
    m1 = re.search(r"\n[나-하]\.\s*판매\s*경로", t)
    if m1:
        t = t[:m1.start()] + "\n" + "\n".join(ln for ln in t[m1.start():].split("\n") if ln.startswith(" |") or len(ln) < 60 or re.search(r"(단위|수주잔고)", ln))
    return t[:12000]


def document(key, rcept):
    r = requests.get(f"{API}/document.xml", params={"crtfc_key": key, "rcept_no": rcept}, timeout=120)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = sorted(z.namelist(), key=lambda n: -z.getinfo(n).file_size)   # 본문 = 가장 큰 파일 (첨부 감사보고서는 따로)
    return z.read(names[0]).decode("utf-8", errors="replace")


def _digits(src):
    return {re.sub(r"[,()\s-]", "", m) for m in re.findall(r"\(?-?[\d,]+(?:\.\d+)?\)?", src.replace("△", "-"))}


def _n(x):
    """AI 가 숫자를 글자(`1,234` · `(56)` · `-`)로 줄 때가 있다 — 숫자로. 못 바꾸면 ValueError."""
    if x is None or isinstance(x, (int, float)):
        return x
    t = str(x).replace(",", "").replace(" ", "").replace("△", "-").replace("▲", "-")   # △ = 음수 (삼성전자 연결조정)
    if t in ("", "-", "−"):
        return None
    neg = t.startswith("(") and t.endswith(")")
    v = float(t.strip("()"))
    return -v if neg else v


def norm(v):
    if not isinstance(v, dict):
        raise ValueError("JSON 아님")
    v["unit"] = str(v.get("unit") or "").replace(" ", "")
    for r in v.get("rows") or []:
        r["cur"], r["prev"] = _n(r.get("cur")), _n(r.get("prev"))
    v["total"] = _n(v.get("total"))
    bl = v.get("backlog")
    if isinstance(bl, dict):
        bl["total"] = _n(bl.get("total"))
        for x in bl.get("items") or []:
            x["v"] = _n(x.get("v"))
        if bl["total"] is None and not any(x.get("v") is not None for x in bl.get("items") or []):
            v["backlog"] = None
    return v


def check(v, src):
    """AI 답 검사 — 숫자는 모두 원문에, 부문 합 ≈ 합계. 통과 못 하면 ValueError."""
    v = norm(v)
    if v.get("unit") not in UNIT:
        raise ValueError("단위 없음")
    have = _digits(src)
    nums = [r.get(k) for r in v.get("rows") or [] for k in ("cur", "prev")] + [v.get("total")]
    bl = v.get("backlog") or {}
    nums += [bl.get("total")] + [x.get("v") for x in bl.get("items") or []]
    for n in nums:
        if n is None:
            continue
        s = f"{abs(n):,.0f}".replace(",", "") if float(n).is_integer() else str(abs(n))
        if s not in have and f"{abs(n):,.1f}".replace(",", "") not in have:
            raise ValueError(f"원문에 없는 숫자 {n}")
    rows = [r for r in v.get("rows") or [] if r.get("cur") is not None]
    if rows and v.get("total"):
        tot = sum(r["cur"] for r in rows)
        if abs(tot - v["total"]) > abs(v["total"]) * 0.03 and not re.search(r"(내부|연결\s*조정|조정)", src):
            raise ValueError(f"부문 합 {tot:,.0f} ≠ 합계 {v['total']:,.0f}")
    return v


def reports(fin_cache, corp, n=REPORTS_PER_CO):
    """dart_fin_all 캐시(collect_kr_fin)의 이 회사 보고서 — 최근 n 개 [(분기 끝, 접수번호)]. 보고서 목록을 따로 부르지 않는다."""
    mm = {"11013": "03-31", "11012": "06-30", "11014": "09-30", "11011": "12-31"}
    out = []
    for k, r in (fin_cache.get(corp) or {}).items():
        if isinstance(r, dict) and r.get("rcept"):
            y, rc = k.split("-")
            out.append((f"{y}-{mm[rc]}", r["rcept"]))
    return sorted(out)[-n:]


def run(codes, corp_map, fin_cache, cache_path=CACHE, cap=CAP):
    key = _key()
    cache = _load(cache_path)
    if not key:
        print("[biz] DART_API_KEY 없음 — 캐시만")
        return cache
    todo = [(code, end, rc) for code in codes for end, rc in reports(fin_cache, corp_map.get(code) or "") if rc not in cache]
    todo.sort(key=lambda x: x[1], reverse=True)   # 새 보고서부터
    pool = None
    done = fail = 0
    for code, end, rc in todo[:cap]:
        try:
            src = section(document(key, rc))
        except Exception as e:  # noqa: BLE001
            print(f"[biz] {code} {rc} 원문 실패: {str(e)[:80]}")
            continue
        if not src:
            cache[rc] = {"code": code, "end": end, "fail": "절 없음"}
            continue
        if pool is None:
            from llm_chain import LLMPool
            pool = LLMPool("json-lite-only", label="kr-biz")
        try:
            v = pool.generate_json(PROMPT + "\n---\n" + src, temperature=0.0, validate=lambda x: check(x, src), max_tokens=4000)
            cache[rc] = dict(check(v, src), code=code, end=end, model=pool.last_model or "", at=datetime.date.today().isoformat())
            done += 1
        except Exception as e:  # noqa: BLE001
            cache[rc] = {"code": code, "end": end, "fail": str(e)[:120]}
            fail += 1
        _save(cache_path, cache)
    _save(cache_path, cache)
    print(f"[biz] 보고서 읽음 {done} · 못 읽음 {fail} · 남은 대기 {max(0, len(todo) - cap)} · AI {pool.calls if pool else 0}번")
    return cache


def series(cache, code):
    """한 종목 → 분기 끝 순 [{end, unit, rows, total, backlog, cur_label}] (읽은 것만)."""
    return sorted((v for v in cache.values() if v.get("code") == code and not v.get("fail")), key=lambda v: v["end"])


if __name__ == "__main__":
    import collect_kr_dart as D
    import collect_kr_fin as FIN
    cm = D.corp_codes(_key())
    c = run(sys.argv[1:], cm, D._load(FIN.CACHE), cache_path=os.environ.get("BIZ_CACHE", CACHE))
    for k in sys.argv[1:]:
        for v in series(c, k):
            print(k, v["end"], v.get("cur_label"), v.get("unit"), "rows", len(v.get("rows") or []), "total", v.get("total"), "backlog", (v.get("backlog") or {}).get("total"))
    for k, v in c.items():
        if v.get("fail"):
            print("못 읽음", v.get("code"), v.get("end"), v["fail"])
