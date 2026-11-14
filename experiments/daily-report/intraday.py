"""홈 미국 증시 · 한국 증시 카드의 하루(장중) 그래프 재료 — 지수 5분봉 하루치 (2026-11-14 사용자 "그렇게 진행해줘").

    fetch("^GSPC", "2026.11.14", us=True)  → {"sym","day","prev","close","h","l","m":[분],"c":[값]} 또는 None

- 요청 = 지수 하나에 야후 2번(5분봉 하루치 · 일봉 5일) — 장 마감 뒤 정기 실행에서 카드 JSON 을 만들 때 한 번만. AI 0, 방문자 요청 0.
- m = 그날 첫 봉으로부터 지난 분(0 = 장 시작), 장 길이 390분(한국 09:00 ~ 15:30 · 미국 09:30 ~ 16:00). 수능일(10:00 시작)도 첫 봉 기준이라 같다.
- 마지막 점 = 일봉 종가(동시호가 · 마감 경매 반영)를 장 마감 자리(390분)에 — 5분봉 마지막 값과 종가가 다를 수 있다.
- prev · close · h · l = 일봉(그날 실제 최고 · 최저). 카드 숫자는 이것만 쓴다.
- 날짜 확인: 한국 = 카드 날짜와 같은 날, 미국 = 카드 날짜(한국 아침) 전 1 ~ 4일 안의 마지막 장. 안 맞거나 점이 모자라면 None → 홈은 옛 그림.
"""
import datetime

SESSION_MIN = 390
MIN_POINTS = 20


def _card_day(s):
    try:
        y, m, d = (int(x) for x in str(s).split("."))
        return datetime.date(y, m, d)
    except (ValueError, TypeError):
        return None


def fetch(sym, card_date, us):
    try:
        import yfinance as yf
        t = yf.Ticker(sym)
        bars = t.history(period="5d", interval="5m", auto_adjust=False)
        daily = t.history(period="7d", interval="1d", auto_adjust=False)
    except Exception as e:   # 수집 실패 → 옛 그림
        print(f"[intraday] {sym}: 받기 실패 {type(e).__name__}")
        return None
    if bars is None or bars.empty or daily is None or len(daily) < 2:
        print(f"[intraday] {sym}: 자료 없음")
        return None
    day = bars.index[-1].date()
    want = _card_day(card_date)
    if want is None:
        return None
    gap = (want - day).days
    if (us and not 1 <= gap <= 4) or (not us and gap != 0):
        print(f"[intraday] {sym}: 장 날짜 {day} ↔ 카드 날짜 {want} 안 맞음 — 쓰지 않는다")
        return None
    dd = [i for i, x in enumerate(daily.index) if x.date() == day]
    if not dd or dd[-1] < 1:
        print(f"[intraday] {sym}: 일봉에 {day} 없음")
        return None
    i = dd[-1]
    row, prev = daily.iloc[i], float(daily["Close"].iloc[i - 1])
    one = bars[[x.date() == day for x in bars.index]]
    one = one[one["Close"].notna()]
    if len(one) < MIN_POINTS:
        print(f"[intraday] {sym}: 5분봉 {len(one)}개 — 모자라 쓰지 않는다")
        return None
    t0 = one.index[0]
    m = [int((x - t0).total_seconds() // 60) for x in one.index]
    c = [round(float(v), 2) for v in one["Close"]]
    keep = [k for k, mm in enumerate(m) if mm <= SESSION_MIN]
    m, c = [m[k] for k in keep], [c[k] for k in keep]
    close = round(float(row["Close"]), 2)
    # 야후 코스피 5분봉은 14:55 에서 끝난다(마지막 35분 없음, 11-13 확인) → 마지막 봉에서 마감(390분) 종가까지 곧게 잇는다.
    # 단축 장(미국 추수감사절 다음 날 등)은 마지막 봉이 한참 이르다 → 마지막 봉 바로 뒤까지만
    end = SESSION_MIN if m[-1] >= SESSION_MIN - 40 else m[-1] + 5
    if m[-1] < end:
        m.append(end); c.append(close)
    out = {"sym": sym, "day": day.isoformat(), "prev": round(prev, 2), "close": close,
           "h": round(max(float(row["High"]), max(c)), 2), "l": round(min(float(row["Low"]), min(c)), 2), "m": m, "c": c}
    print(f"[intraday] {sym}: {day} 점 {len(c)}개 · 전날 {out['prev']} → 종가 {close} · 최고 {out['h']} · 최저 {out['l']}")
    return out


if __name__ == "__main__":
    import json
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "^GSPC"
    print(json.dumps(fetch(sym, sys.argv[2], us=sym != "^KS11"), ensure_ascii=False)[:400])
