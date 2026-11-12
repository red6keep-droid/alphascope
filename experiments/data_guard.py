"""빈 값 막기 (data_guard) — 야후(yfinance)가 오류 없이 빈 값을 줄 때 페이지가 비거나 옛 값이 섞인 채 나가지 않게 (2026-11-12 사용자: "빈 값이 치명적이니 대비책").

야후는 IP 를 영구 차단하지 않고 잠깐 조인다 — 빈 표 · "possibly delisted" · 429 가 오류 없이 섞여 와서 실행은 성공으로 끝나고 카드만 빈다.
그래서 세 가지를 한다 (파이썬만, AI 0):
  1. 지난 좋은 값으로 메우기 — 잘 안 바뀌는 칸(실적일 · 애널리스트 · 이익 예상 · 회사 정보 · 시총)은 비면 마지막으로 받은 값을 쓴다.
     칸마다 며칠까지 쓸지(MAX_DAYS) 정해 두고, 넘으면 비운다(오래된 값이 오늘 값처럼 보이지 않게). 날마다 바뀌는 옵션 · 변동성은 메우지 않는다.
  2. 일봉 신선도 — 종목마다 마지막 봉 날짜를 다수결 날짜와 비교. 비었거나 늦은 종목은 그 실행에서 페이지를 고쳐 쓰지 않는다(어제 페이지 그대로).
     늦은 종목이 BLOCK_RATIO 넘으면 야후 쪽 문제로 보고 그 실행의 페이지 갱신을 전부 멈춘다.
  3. 알림 — 칸마다 빈 비율이 ALERT_RATIO 를 넘거나 페이지를 건너뛰면 Slack 한 통(notify, 실행 끝에 묶어서).
기록: data/last_good.json = {칸: {종목: {"v": 값, "day": 받은 날}}} (상태 브랜치에 남긴다) · data/guard.json = 이번 실행 결과(건너뛸 페이지 · 멈춤 · 칸별 비율).
"""

import datetime
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ALERT_RATIO = 0.10   # 칸마다 이만큼 넘게 비면 알림
BLOCK_RATIO = 0.30   # 일봉이 이만큼 넘게 비거나 늦으면 그 실행의 페이지 갱신 전부 멈춤
NAME = {"caps": "시총", "earnings": "실적일", "analysts": "애널리스트 의견", "eps": "이익 예상", "short": "공매도", "company": "회사 정보",
        "revenue": "매출", "options": "옵션 변동성", "bars": "일봉"}   # Slack · 로그는 한국어 이름표 (2026-11-07 알림 규칙)
MAX_DAYS = {          # 지난 값을 며칠까지 쓰나 (달력 날짜) — 0 은 메우지 않음
    "caps": 3, "earnings": 14, "analysts": 14, "eps": 14, "short": 14, "company": 30, "revenue": 30, "options": 0,
}


def _empty(v):
    if v is None:
        return True
    if isinstance(v, (list, dict, str)):
        return len(v) == 0
    if isinstance(v, float):
        return v != v or v == 0.0
    return False


class Guard:
    def __init__(self, data_dir, label, today=None):
        self.label = label
        self.path = os.path.join(data_dir, "last_good.json")
        self.report_path = os.path.join(data_dir, "guard.json")
        self.today = today or datetime.date.today().isoformat()
        try:
            with open(self.path, encoding="utf-8") as f:
                self.store = json.load(f)
        except (OSError, ValueError):
            self.store = {}
        self.stats = {}        # 칸 → Counter(ok, carried, missing)
        self.skip = []         # 이번 실행에서 고쳐 쓰지 않을 페이지(종목)
        self.block = False
        self.bars_day = None

    # ---------------------------------------------------------------- 1. 메우기
    def fill(self, field, values, syms=None):
        """values = {종목: 값} — 빈 값은 지난 좋은 값(MAX_DAYS 안)으로, 좋은 값은 기록. 고친 dict 를 돌려준다."""
        keep = MAX_DAYS.get(field, 0)
        mem = self.store.setdefault(field, {})
        c = self.stats.setdefault(field, Counter())
        out = dict(values)
        for s in (syms if syms is not None else list(values)):
            v = values.get(s)
            if not _empty(v):
                mem[s] = {"v": v, "day": self.today}
                c["ok"] += 1
                continue
            old = mem.get(s)
            age = (datetime.date.fromisoformat(self.today) - datetime.date.fromisoformat(old["day"])).days if old else None
            if old and keep and age <= keep:
                out[s] = old["v"]
                c["carried"] += 1
            else:
                c["missing"] += 1
        return out

    def fill_nested(self, field, stocks, syms=None):
        """stocks = {종목: {칸: 값, ...}} 안의 한 칸만 메운다 (extra.json 의 stocks)."""
        got = self.fill(field, {s: (v or {}).get(field) for s, v in stocks.items()}, syms or list(stocks))
        for s, v in got.items():
            if not _empty(v):
                stocks.setdefault(s, {})[field] = v
        return stocks

    # ---------------------------------------------------------------- 2. 일봉 신선도
    def check_bars(self, bars, syms):
        """bars = {종목: [{"day", ...}]} — 다수결 마지막 날보다 늦거나 빈 종목은 skip. 너무 많으면 block."""
        last = {s: (bars.get(s) or [{}])[-1].get("day") for s in syms}
        days = Counter(d for d in last.values() if d)
        if not days:
            self.block, self.skip = True, list(syms)
            self.stats["bars"] = Counter(missing=len(syms))
            return self.skip
        self.bars_day = days.most_common(1)[0][0]
        bad = [s for s, d in last.items() if not d or d < self.bars_day]
        self.skip = sorted(set(self.skip) | set(bad))
        self.stats["bars"] = Counter(ok=len(syms) - len(bad), missing=sum(1 for s in bad if not last[s]), stale=sum(1 for s in bad if last[s]))
        if len(bad) > len(syms) * BLOCK_RATIO:
            self.block = True
        return bad

    # ---------------------------------------------------------------- 3. 기록 · 알림
    def finish(self):
        """last_good.json · guard.json 쓰기 + 알림. 페이지 게시 단계가 guard.json 을 읽는다."""
        rates = {}
        alerts = []
        for field, c in self.stats.items():
            n = sum(c.values())
            if not n:
                continue
            bad = n - c["ok"]
            rates[field] = {"n": n, **c}
            if bad / n > ALERT_RATIO:
                alerts.append(f"{NAME.get(field, field)} {bad}/{n}" + (f"(지난 값 {c['carried']})" if c.get("carried") else ""))
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.store, f, ensure_ascii=False)
        rep = {"at": self.today, "bars_day": self.bars_day, "skip": self.skip, "block": self.block, "rates": rates}
        with open(self.report_path, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)
        line = " · ".join(f"{NAME.get(k, k)} {v['n'] - v.get('ok', 0)}/{v['n']}" for k, v in rates.items())
        print(f"[guard] {self.label} 빈 값 {line or '없음'} · 건너뛸 페이지 {len(self.skip)}" + (" · 페이지 갱신 멈춤" if self.block else ""))
        try:
            import notify
            if self.block:
                notify.event("빈 값", f"{self.label} 일봉 {len(self.skip)}종목 비거나 늦음 — 이번 실행 페이지 갱신 멈춤(어제 페이지 그대로)")
            elif self.skip:
                notify.event("빈 값", f"{self.label} 일봉 비거나 늦은 {', '.join(self.skip[:8])}{' 외' if len(self.skip) > 8 else ''} — 그 페이지만 갱신 건너뜀")
            if alerts:
                notify.event("빈 값", f"{self.label} " + " · ".join(alerts))
        except Exception as e:  # noqa: BLE001 — 알림 때문에 수집이 죽으면 안 된다
            print(f"[guard] 알림 실패: {e}")
        return rep


def guard_run(data_dir, label, syms, snap, extra, nested=("analysts", "eps", "short", "company"), snap_path=None, extra_path=None):
    """종목 파이프라인 한 번 — 시총 · 실적일 · 상세 칸 메우기 + 일봉 신선도 + 기록 · 알림. 메운 값은 snapshot · extra 파일에도 다시 쓴다(--cached 그리기와 같게)."""
    g = Guard(data_dir, label)
    if snap is not None:
        if isinstance(snap.get("caps"), dict):
            snap["caps"] = g.fill("caps", snap["caps"], syms)
        if isinstance(snap.get("earnings"), dict):
            snap["earnings"] = g.fill("earnings", snap["earnings"], syms)
        g.check_bars(snap.get("bars") or {}, syms)
    if extra:
        st = extra.setdefault("stocks", {})
        for f in nested:
            g.fill_nested(f, st, syms)
        if isinstance(extra.get("earnings"), dict):   # 한국 extra 는 실적일이 위에 있다
            extra["earnings"] = g.fill("earnings", extra["earnings"], syms)
        rev = (extra.get("revenue") or {}).get("series")
        if isinstance(rev, dict):
            extra["revenue"]["series"] = g.fill("revenue", rev, syms)
        if any("iv" in (v or {}) for v in st.values()):   # 옵션 = 세기만 (날마다 바뀌어 메우지 않음)
            g.fill("options", {s: (st.get(s) or {}).get("iv") for s in syms}, syms)
    for path, obj in ((snap_path, snap), (extra_path, extra)):
        if path and obj:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False)
    return g.finish()


def load_report(data_dir):
    """게시 단계용 — 이번 실행 guard.json. 없으면 막지 않는다(예전처럼)."""
    try:
        with open(os.path.join(data_dir, "guard.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"skip": [], "block": False}
