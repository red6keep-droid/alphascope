"""국민연금 지분율 — 한국 종목 페이지 기업 탭 한 줄 (2026-11-13 사용자 P545 "넣어줘").

재료 = 공공데이터포털 국민연금공단 파일 둘(이용허락 `제한 없음`, 사용자 확인 2026-11-13 · 운영지침 D4-15-1), nps/ 폴더에 원본 그대로(CP949):
  annual_YYYYMMDD.csv = 국내주식 투자정보(연 1회, 12월 말 기준 · 이듬해 9월쯤 올라옴) — 번호 · 종목명 · 평가액(억 원) · 자산군 내 비중 · 지분율
  major_YYYYMMDD.csv  = 대량보유주식 보고내역(분기, 지분 5% 이상 · 1%p 변동 때) — 번호 · 발행기관명(정식 이름) · 보고서 작성기준일 · 지분율
새 파일이 나오면 같은 이름 틀로 nps/ 에 넣기만 하면 된다(가장 새 연간 + 그 뒤 분기 보고 전부를 읽는다). AI 0 · 새 수집 0.

짝 맞추기: 연간 파일은 줄인 이름(`NAVER`) · 분기 파일은 정식 이름(`네이버`, `씨제이대한통운(주)`) →
우리 종목 이름과 OpenDART 기업개황 정식 이름(data/dart_company.json) 둘 다로 찾는다.
"""

import csv
import datetime
import glob
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
NPS = os.path.join(HERE, "nps")
STALE_DAYS = 548   # 18개월 넘은 숫자는 숨김 (P545)


def _norm(s):
    return re.sub(r"\(주\)|㈜|주식회사|\s", "", s or "")


def _rows(path):
    with open(path, encoding="cp949") as f:
        return list(csv.reader(io.StringIO(f.read())))[1:]


def _day(path):
    m = re.search(r"(\d{8})", os.path.basename(path))
    return f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else ""


def load(candidates, company=None):
    """candidates = [(sym, 이름, ...)], company = {코드: {corp_name}} → {코드: {"year": (기준일, %), "reports": [(날짜, %)]}}."""
    if company is None:
        try:
            with open(os.path.join(HERE, "data", "dart_company.json"), encoding="utf-8") as f:
                company = json.load(f).get("map") or {}
        except (OSError, ValueError):
            company = {}
    annual = sorted(glob.glob(os.path.join(NPS, "annual_*.csv")))
    if not annual:
        return {}
    a_day = _day(annual[-1])
    a = {}
    for r in _rows(annual[-1]):
        if len(r) >= 5:
            try:
                a[_norm(r[1])] = float(r[4])
            except ValueError:
                pass
    b = {}
    for p in sorted(glob.glob(os.path.join(NPS, "major_*.csv"))):
        for r in _rows(p):
            if len(r) >= 4 and r[2] > a_day:
                try:
                    b.setdefault(_norm(r[1]), []).append((r[2], float(r[3])))
                except ValueError:
                    pass
    out = {}
    for c in candidates:
        code = c[0][:6]
        keys = [_norm(c[1]), _norm((company.get(code) or {}).get("corp_name"))]
        y = next((a[k] for k in keys if k and k in a), None)
        rep = next((b[k] for k in keys if k and k in b), [])
        if y is not None or rep:
            out[code] = {"year": (a_day, y) if y is not None else None, "reports": sorted(set(rep))}
    return out


def _d(iso):
    return f"{int(iso[:4])}. {int(iso[5:7])}. {int(iso[8:10])}."


def row(info, today=None):
    """기업 탭 줄 값 HTML 재료 → (값, 아래 작은 회색 줄) 또는 None. 가장 새 숫자를 위에, 비교는 아래 작은 줄."""
    if not info:
        return None
    today = today or datetime.date.today().isoformat()
    y, reps = info.get("year"), info.get("reports") or []
    if reps:
        day, pct = reps[-1]
        prev = (reps[-2][1], f"{_d(reps[-2][0])} 보고") if len(reps) >= 2 else ((y[1], f"{int(y[0][:4])}년 말") if y else None)
        val = f"{pct:.2f}% ({_d(day)} 보고)"
    elif y:
        day, pct, prev = y[0], y[1], None
        val = f"{pct:.2f}% ({int(day[:4])}년 말 기준)"
    else:
        return None
    if (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(day)).days > STALE_DAYS:
        return None
    sub = ""
    if prev and abs(pct - prev[0]) >= 0.01:
        sub = f"{prev[1]} {prev[0]:.2f}%에서 {'늘렸습니다' if pct > prev[0] else '줄였습니다'}."
    return val, sub
