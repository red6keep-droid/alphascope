"""상세 값 저장 (detail_cache) — 잘 안 바뀌는 값은 바뀌는 주기에 맞춰 드물게 받고, 그 사이에는 저장해 둔 값을 쓴다 (2026-11-12 사용자 "기업 정보는 한 번만 받으면 유지되는 것 아니냐" → "정식 종목에도").

왜: 정식 종목은 하루 네 번 실행마다 종목당 약 10번 야후를 불렀다(64종목 하루 약 2,500회). 같은 날 같은 값이 대부분이고,
    호출이 많을수록 야후가 빈 값으로 조이는 일이 잦아진다. 또 extra.json 이 실행 사이에 남지 않아 '주 1회'라고 적힌 매출 · 함께 보는 회사 실적일도 매번 받았다.
칸별 주기 (DUE):
    options(옵션 · 변동성)  — 새 거래일마다 (같은 날 실행끼리는 다시 안 받음)
    caps(시총)              — 새 거래일마다
    analysts · eps(애널리스트 · 이익 예상) — 7일, 또는 종목별 요일(나눠 받기)이면 3일, 또는 실적 발표가 지난 뒤 처음
    short(공매도)           — 14일 (한 달 두 번 공시)
    earnings(실적일)        — 7일, 다음 실적이 14일 안이면 매일, 실적 발표가 지난 뒤 처음
    company(기업 정보)      — 90일
    revenue(분기 매출 · 한국) — 30일, 또는 실적 발표가 지난 뒤 처음
빈 값은 저장하지 않는다 — 받다 비면 지난 값을 그대로 쓰고 다음 실행에 다시 받는다 (data_guard 와 같은 생각).
파일: <data>/detail_cache.json = {"stocks": {종목: {칸: {"v": 값, "day": 받은 날, "bar": 받은 거래일}}}, "blobs": {이름: {"v", "day"}}} — 상태 브랜치에 남긴다.
"""

import datetime
import json
import os
import zlib

WEEKLY, SPREAD_MIN = 7, 3


def _empty(v):
    if v is None:
        return True
    if isinstance(v, (list, dict, str)):
        return len(v) == 0
    if isinstance(v, float):
        return v != v or v == 0.0
    return False


class DetailCache:
    def __init__(self, data_dir, today=None):
        self.path = os.path.join(data_dir, "detail_cache.json")
        self.today = today or datetime.date.today()
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {}
        self.stocks = d.get("stocks") or {}
        self.blobs = d.get("blobs") or {}
        self.tried = 0
        self.failed = 0
        self.reused = 0

    # ---------------------------------------------------------------- 칸 값
    def get(self, sym, field):
        x = (self.stocks.get(sym) or {}).get(field)
        return x["v"] if x else None

    def age(self, sym, field):
        x = (self.stocks.get(sym) or {}).get(field)
        return (self.today - datetime.date.fromisoformat(x["day"])).days if x else None

    def put(self, sym, field, value, bar=None):
        """받은 값 — 비었으면 저장하지 않고 실패로 센다."""
        self.tried += 1
        if _empty(value):
            self.failed += 1
            return False
        self.stocks.setdefault(sym, {})[field] = {"v": value, "day": self.today.isoformat(), "bar": bar}
        return True

    def due(self, sym, field, bar=None, earn_days=(), next_earn=None):
        """이번 실행에 새로 받아야 하나. bar = 이번 마지막 거래일, earn_days = 지난 실적 발표일들, next_earn = 다음 실적일."""
        x = (self.stocks.get(sym) or {}).get(field)
        if not x:
            return True
        age = (self.today - datetime.date.fromisoformat(x["day"])).days
        after_earn = any(x["day"] < d <= self.today.isoformat() for d in earn_days or ())   # 받은 뒤에 실적 발표가 있었다
        if field in ("options", "caps"):
            return bar is not None and x.get("bar") != bar
        if field in ("analysts", "eps"):
            spread = zlib.crc32(sym.encode()) % 5 == self.today.weekday()   # 종목마다 정해진 요일 — 한 날에 몰리지 않게
            return age >= WEEKLY or (spread and age >= SPREAD_MIN) or after_earn
        if field == "short":
            return age >= 14
        if field == "earnings":
            near = next_earn is not None and 0 <= (datetime.date.fromisoformat(next_earn) - self.today).days <= 14
            return age >= WEEKLY or (near and age >= 1) or after_earn
        if field == "company":
            return age >= 90
        if field == "revenue":
            return age >= 30 or after_earn
        return age >= 1

    # ---------------------------------------------------------------- 묶음 값 (매출 표 · 함께 보는 회사 실적일처럼 종목 묶음 하나)
    def blob(self, name, max_days):
        """저장한 묶음이 max_days 안이면 그 값, 아니면 None."""
        x = self.blobs.get(name)
        if x and (self.today - datetime.date.fromisoformat(x["day"])).days < max_days:
            return x["v"]
        return None

    def put_blob(self, name, value):
        if not _empty(value):
            self.blobs[name] = {"v": value, "day": self.today.isoformat()}

    def save(self, label=""):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"stocks": self.stocks, "blobs": self.blobs}, f, ensure_ascii=False)
        print(f"[detail] {label} 새로 받음 {self.tried - self.failed}/{self.tried} · 저장값 씀 {self.reused}")
        if self.tried >= 10 and self.failed / self.tried > 0.10:
            try:
                import notify
                notify.event("빈 값", f"{label} 상세 값 {self.failed}/{self.tried} 비어 옴 — 지난 값으로 계속")
            except Exception:  # noqa: BLE001
                pass


_SHARED = {}


def shared(data_dir):
    """같은 실행 안에서 한 개만 — 수집 모듈 여럿이 같은 파일을 덮어쓰지 않게."""
    key = os.path.abspath(data_dir)
    if key not in _SHARED:
        _SHARED[key] = DetailCache(data_dir)
    return _SHARED[key]


def earn_info(cache, sym, today=None):
    """저장한 실적일 → (지난 발표일들, 다음 발표일)."""
    t = (today or cache.today).isoformat()
    v = cache.get(sym, "earnings") or []
    return [x["day"] for x in v if x["day"] <= t], next((x["day"] for x in v if x["day"] >= t), None)
