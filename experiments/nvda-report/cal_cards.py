"""캘린더 탭 — 질문 카드 넷의 재료 (가이드라인 2-8, 2026-10-18 Claude 설계 · 사용자 확인 전). AI 없음, DB 의 calendar · daily_bars 만.

비교 대상 (가이드라인 1-4-1)
  1. 다음 실적 발표는?                최근 8번 발표 다음 날 |움직임| vs 그때 평소 하루 움직임(EWMA, 가격 카드와 같은 자)
  2. 엔비디아가 함께 보는 회사 실적은?  그 회사 실적 다음 날 엔비디아 |움직임| 보통값 vs 엔비디아 보통 날 (최근 2년 일봉)
  3. 시장 전체를 흔들 일정은?          그 일정 날 S&P 500 |움직임| 보통값 vs S&P 500 보통 날 (2025~ 지난 일정)
  4. 진행 중 소송 일정은?              그래프 없음 — 비교 대상이 없다(1-4-1 마지막 줄)
"""

import datetime
import math
import statistics

import collect_market
import config
import normal_range_line

WINDOW = 30            # 카드에 보이는 앞으로의 범위 (일)
LIST_DAYS = 60         # `전체 일정 보기` 범위
SOON_DAYS = 7          # 이 안이면 카드 색을 주황으로
PEER_KO = {"MSFT": "마이크로소프트", "GOOGL": "구글", "AMZN": "아마존", "META": "메타", "ORCL": "오라클", "TSM": "TSMC",
           "AMD": "AMD", "AVGO": "브로드컴", "MU": "마이크론", "SMCI": "슈퍼마이크로", "DELL": "델"}
PEER_ROLE = {"MSFT": "고객", "GOOGL": "고객", "AMZN": "고객", "META": "고객", "ORCL": "고객", "DELL": "고객", "SMCI": "고객",
             "TSM": "공급", "MU": "공급", "AMD": "경쟁", "AVGO": "경쟁"}
MACRO_KO = {"FOMC": "금리 결정 (FOMC)", "CPI": "소비자물가 (CPI)", "NFP": "고용 지표", "PCE": "물가 (PCE)", "GDP": "성장률 (GDP)",
            "OPEX": "옵션 만기", "INDEX": "지수 재편"}
MACRO_KINDS = ("FOMC", "CPI", "NFP", "PCE", "GDP", "OPEX", "INDEX")


def _d(s):
    return datetime.date.fromisoformat(s)


def _rets(conn, sym, day):
    b = [x for x in collect_market.bars(conn, sym) if x["day"] <= day]
    return {b[i]["day"]: abs(b[i]["close"] / b[i - 1]["close"] - 1) * 100 for i in range(1, len(b))}, [x["day"] for x in b]


def _next_trading(days, d, same_day=False):
    return next((x for x in days if (x >= d if same_day else x > d)), None)


def _med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def card_earnings(conn, day, a):
    nxt = a.get("next_earnings")
    em = a.get("earnings_moves") or {}
    if not nxt:
        return None
    row = conn.execute("SELECT confirmed FROM calendar WHERE kind = 'EARNINGS' AND day = ?", (nxt,)).fetchone()
    sd = {r["day"]: r["sd"] for r in normal_range_line.series(conn, day)}   # 전날까지로 잰 평소 하루 (로그 수익률 σ)
    bars = []
    for m in em.get("moves") or []:
        s = sd.get(m["day"])
        bars.append({"day": m["day"], "ret": m["ret"], "move": abs(m["ret"]), "normal": s * 100 if s else None})
    left = (_d(nxt) - _d(day)).days
    exp = (a.get("expect") or {}).get("move") or {}
    return {"day": nxt, "left": left, "confirmed": bool(row["confirmed"]) if row else False, "bars": bars,
            "median": em.get("median_abs"), "normal": (a.get("normal_range") or {}).get("sigma_pct"), "market_exp": exp.get("earn_day")}


def card_peers(conn, day):
    end = (_d(day) + datetime.timedelta(days=WINDOW)).isoformat()
    up = [dict(r) for r in conn.execute("SELECT day, symbol, confirmed FROM calendar WHERE kind = 'EARNINGS_PEER' AND day > ? AND day <= ? ORDER BY day", (day, end))]
    rets, days = _rets(conn, config.SYMBOL, day)
    normal = _med(list(rets.values())[-252:])
    effect = {}
    for sym in sorted({u["symbol"] for u in up}):
        past = [r["day"] for r in conn.execute("SELECT day FROM calendar WHERE kind = 'EARNINGS_PEER' AND symbol = ? AND day < ? AND day >= ?", (sym, day, days[0]))]
        hits = [rets.get(_next_trading(days, d)) for d in past]   # 고객 · 경쟁사는 대개 장 마감 뒤 발표 → 다음 거래일
        hits = [h for h in hits if h is not None]
        effect[sym] = {"median": _med(hits), "n": len(hits)}
    return {"upcoming": up, "effect": effect, "normal": normal}


def card_macro(conn, day):
    end = (_d(day) + datetime.timedelta(days=WINDOW)).isoformat()
    up = [dict(r) for r in conn.execute(f"SELECT day, kind, label FROM calendar WHERE kind IN ({','.join('?' * len(MACRO_KINDS))}) AND day > ? AND day <= ? ORDER BY day",
                                        (*MACRO_KINDS, day, end))]
    rets, days = _rets(conn, "SPY", day)
    normal = _med(list(rets.values())[-252:])
    effect = {}
    for kind in MACRO_KINDS:
        past = sorted({r["day"] for r in conn.execute("SELECT day FROM calendar WHERE kind = ? AND day < ? AND day >= ?", (kind, day, days[0]))})
        hits = [rets.get(_next_trading(days, d, same_day=True)) for d in past]   # 지표는 장 전, FOMC 는 장중 오후 2시, 만기는 장중 — 모두 그날
        hits = [h for h in hits if h is not None]
        if hits:
            effect[kind] = {"median": _med(hits), "n": len(hits)}
    return {"upcoming": up, "effect": effect, "normal": normal}


def card_court(a, day):
    out = []
    for c in a.get("cases") or []:
        if c.get("next_day"):
            out.append({"name": c["short_name"], "day": c["next_day"], "label": c.get("next_label"), "left": (_d(c["next_day"]) - _d(day)).days})
    out.sort(key=lambda x: x["day"])
    return {"cases": out} if out else None


def all_upcoming(conn, day):
    end = (_d(day) + datetime.timedelta(days=LIST_DAYS)).isoformat()
    return [dict(r) for r in conn.execute("SELECT day, kind, label, symbol, confirmed FROM calendar WHERE day > ? AND day <= ? ORDER BY day, kind", (day, end))]


def build(conn, day, a):
    out = {}
    for k, f in (("earnings", lambda: card_earnings(conn, day, a)), ("peers", lambda: card_peers(conn, day)), ("macro", lambda: card_macro(conn, day)),
                 ("court", lambda: card_court(a, day)), ("all", lambda: all_upcoming(conn, day))):
        try:
            out[k] = f()
        except Exception as e:   # noqa: BLE001
            print(f"[cal_cards] {k} 실패 : {e}")
            out[k] = None
    return out
