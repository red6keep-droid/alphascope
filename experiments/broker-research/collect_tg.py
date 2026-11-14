"""한국 증권사 목표가 — 증권사 공식 텔레그램 리서치 채널 글 본문에서 (2026-11-14 사용자 "증권사 보고서 · 목표가를 수집해서 넣자" → 텔레그램 확정).

    .venv/bin/python experiments/broker-research/collect_tg.py            # 새 글만 읽어 kr-stocks/data/broker_tg.json 에 더함
    .venv/bin/python experiments/broker-research/collect_tg.py --days 30  # 처음 · 다시 채우기

왜 텔레그램: 국내 증권사 목표가를 공식으로 받는 공개 API · 공공데이터가 없다(한경 컨센서스 · 네이버 리서치 = 비공식 화면, FnGuide = 유료).
증권사 리서치센터가 직접 운영하는 공개 채널은 리포트마다 `종목(코드) | BUY | TP 48만원(하향)` 같은 요약을 글로 올린다 → 글만 읽는다(PDF 열지 않음 · 저장 안 함).
실측(11-14, 최근 30일): 공식 채널 13곳 → 목표가 종목 219개, 우리 한국 385개 중 161개 · 정식 35개 중 29개.
- 읽기 = 텔레그램 공식 API(사용자 세션, tg_login.py). 키 = TELEGRAM_API_ID · TELEGRAM_API_HASH · TELEGRAM_SESSION(.env · GitHub Secret).
- 싣는 것 = 사실만(증권사 · 날짜 · 투자의견 · 목표가 · 상향/하향) + 원문 글 주소. 리포트 본문 · PDF 는 옮기지 않는다.
- AI 0 — 정규식. 종목 이름은 글에서 읽지 않고 코드로 우리 명단 이름을 붙인다(화면 쪽). 이상한 목표가(현재가 0.3배 밑 · 5배 위)는 화면 쪽에서 버린다.
- 결과 = kr-stocks/data/broker_tg.json(kr 상태 저장소에 보관 — 날짜별로 쌓이는 우리 기록) · 받기 현황 = feed_log `증권사 목표가 (텔레그램)`.
줄 모양 = 미국 증권사 변경(stock-radar collect_extra._changes)과 같은 칸 → 화면은 공용 R.broker_card 그대로:
  {at, firm, code, to, from, action, pt_action(Raises · Lowers · Maintains), pt, pt_prior, url, ch}
"""
import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [EXP, HERE]
OUT = os.path.join(EXP, "kr-stocks", "data", "broker_tg.json")
KEEP_DAYS = 400       # 기록은 1년 넘게 둔다 (목표가 변화 = 우리 기록, data-retention `우리 것`)
FIRST_DAYS = 30       # 처음 실행 · 이어 읽을 글 번호가 없을 때 거슬러 읽는 날
FEED = "증권사 목표가 (텔레그램)"

# 증권사가 직접 운영하는 리서치센터 · 팀 채널만 (애널리스트 개인 채널 · 모음 채널 제외). 11-14 실측에서 글에 목표가가 나온 곳.
CHANNELS = {
    "daolresearch": "다올투자증권", "HanaResearch": "하나증권", "ITforYouFromHana": "하나증권", "shinhanresearch": "신한투자증권",
    "shsmallcap": "신한투자증권", "lovequant": "흥국증권", "KyoboRSC": "교보증권", "ssi_research": "상상인증권", "KiwoomResearch": "키움증권",
    "hmsecresearch": "현대차증권", "sksresearch": "SK증권", "SmallCap": "유진투자증권", "meritz_research": "메리츠증권", "leadingR": "리딩투자증권",
    "yuantaresearch": "유안타증권", "KISemicon": "한국투자증권", "DSInvResearch": "DS투자증권",
}

CODE = re.compile(r"\(\s*A?(\d{6})(?:\.K[SQ])?\s*[,/)|]")
TP = re.compile(r"(?:목표\s*주?가|\bTP)\s*[:：]?\s*(?:₩\s*)?(\d[\d,]*(?:\.\d+)?)\s*(만)?\s*원?(?!\s*[%\d])", re.I)
GRADE = [(re.compile(r"Trading\s*Buy", re.I), "Trading Buy"), (re.compile(r"Strong\s*Buy", re.I), "Strong Buy"), (re.compile(r"\bBUY\b|매수", re.I), "Buy"),
         (re.compile(r"Outperform|비중\s*확대", re.I), "Outperform"), (re.compile(r"\bHOLD\b|중립|Marketperform|보유", re.I), "Hold"),
         (re.compile(r"\bSELL\b|매도|Underperform|비중\s*축소", re.I), "Sell"), (re.compile(r"Not\s*Rated|\bNR\b", re.I), "")]
MOVE = re.compile(r"(상향|하향|유지|신규|하회|상회)")


def env(name):
    v = os.environ.get(name, "").strip()
    if v:
        return v
    import tg_login
    try:
        return tg_login.env(name)
    except OSError:
        return ""


def grade_of(t):
    for rx, g in GRADE:
        if rx.search(t):
            return g
    return None


def parse(text):
    """글 하나 → [(코드, 목표가, 등급, 움직임)]. 종목 코드마다 그다음 코드 앞까지(최대 400자)에서 목표가를 찾는다 — 업종 글처럼 한 글에 여러 종목이 있어도."""
    out = []
    codes = list(CODE.finditer(text))
    for i, m in enumerate(codes):
        end = min(codes[i + 1].start() if i + 1 < len(codes) else len(text), m.end() + 400)
        seg = text[max(0, m.start() - 40):end]   # 앞 40자 — `[농심(004370) | BUY | TP …]` 처럼 이름 앞 괄호
        tp = TP.search(seg)
        if not tp:
            continue
        v = float(tp.group(1).replace(",", "")) * (10000 if tp.group(2) else 1)
        if v < 100:   # `목표가 22` 처럼 단위가 빠진 것 — 버린다
            continue
        head = seg[: tp.end() + 20]
        mv = MOVE.search(seg[tp.start(): tp.end() + 15]) or MOVE.search(head)
        out.append((m.group(1), v, grade_of(head), mv.group(1) if mv else None))
    seen, uniq = set(), []
    for r in out:
        if r[0] not in seen:
            seen.add(r[0])
            uniq.append(r)
    return uniq


def row(firm, ch, msg_id, at, code, pt, grade, move, prior):
    pt_action = {"상향": "Raises", "하향": "Lowers", "유지": "Maintains"}.get(move)
    pp = prior.get("pt") if prior else None
    if not pt_action and pp:   # 글에 말이 없으면 같은 증권사 지난 목표가와 비교
        pt_action = "Raises" if pt > pp * 1.001 else "Lowers" if pt < pp * 0.999 else "Maintains"
    g0 = prior.get("to") if prior else None
    action = "init" if move == "신규" else ""
    return {"at": at, "firm": firm, "code": code, "to": grade or (g0 or ""), "from": g0 or "", "action": action,
            "pt_action": pt_action or "", "pt": pt, "pt_prior": pp if pp and pp != pt else None, "url": f"https://t.me/{ch}/{msg_id}", "ch": ch}


def load(path=OUT):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"last": {}, "rows": []}


def run(days=None):
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    from telethon import errors
    import feed_log
    d = load()
    api_id, api_hash, sess = env("TELEGRAM_API_ID"), env("TELEGRAM_API_HASH"), env("TELEGRAM_SESSION")
    if not (api_id and api_hash and sess):
        print("[tg] 텔레그램 키 없음 — 지난 기록 그대로")
        feed_log.feed(FEED, ok=False, error="키 없음", every_days=1)
        return d
    now = datetime.datetime.now(datetime.timezone.utc)
    cut = now - datetime.timedelta(days=days or FIRST_DAYS)
    last_of = {}   # (증권사, 코드) → 가장 최근 줄 — 지난 목표가 · 등급 비교
    for r in sorted(d["rows"], key=lambda r: r["at"]):
        last_of[(r["firm"], r["code"])] = r
    have = {(r["firm"], r["code"], r["at"][:10]) for r in d["rows"]}
    new, read, fails = [], 0, []
    try:
        with TelegramClient(StringSession(sess), int(api_id), api_hash) as c:
            for ch, firm in CHANNELS.items():
                since = 0 if days else d["last"].get(ch, 0)
                top = since
                try:
                    for m in c.iter_messages(ch, limit=2000, min_id=since):
                        if m.date < cut:
                            break
                        read += 1
                        top = max(top, m.id)
                        at = m.date.strftime("%Y-%m-%dT%H:%M:%SZ")
                        for code, pt, grade, move in parse(m.message or ""):
                            if (firm, code, at[:10]) in have:   # 같은 증권사가 같은 날 같은 종목을 두 채널에 올린 것
                                continue
                            r = row(firm, ch, m.id, at, code, pt, grade, move, last_of.get((firm, code)))
                            new.append(r)
                            have.add((firm, code, at[:10]))
                except (ValueError, errors.RPCError) as e:
                    fails.append(f"{ch}: {e.__class__.__name__}")
                    continue
                d["last"][ch] = top
    except Exception as e:  # noqa: BLE001 — 세션 만료 · 막힘 → 지난 기록 그대로, 대시보드에 실패
        feed_log.feed(FEED, ok=False, error=f"{e.__class__.__name__}: {str(e)[:120]}", every_days=1)
        print(f"[tg] 읽기 실패 — 지난 기록 그대로: {e!r}")
        return d
    # 지난 목표가는 시간 순으로 다시 맞춘다 (한 번에 여러 날을 읽으면 위 last_of 가 새 줄을 모른다)
    rows = sorted(d["rows"] + new, key=lambda r: r["at"])
    prev = {}
    for r in rows:
        k = (r["firm"], r["code"])
        p = prev.get(k)
        if p and r.get("pt") and p.get("pt") and not r.get("pt_prior") and p["pt"] != r["pt"]:
            r["pt_prior"] = p["pt"]
            r["pt_action"] = r.get("pt_action") or ("Raises" if r["pt"] > p["pt"] else "Lowers")
        prev[k] = r
    keep = (now - datetime.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    d["rows"] = [r for r in rows if r["at"] >= keep]
    d["built"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, separators=(",", ":"))
    codes = {r["code"] for r in new}
    print(f"[tg] 채널 {len(CHANNELS) - len(fails)}/{len(CHANNELS)} · 새 글 {read} · 새 목표가 {len(new)}줄 · {len(codes)}종목 · 전체 {len(d['rows'])}줄"
          + (f" · 실패 {', '.join(fails)}" if fails else ""))
    last = max((r["at"] for r in d["rows"]), default="")
    feed_log.feed(FEED, ok=len(fails) < len(CHANNELS) // 2, label=f"최근 목표가 {last[:10]}" if last else "", data_date=last[:10],
                  got_new=bool(new), every_days=1, error="; ".join(fails)[:200])
    return d


def for_code(code, close=None, days=30, data=None):
    """화면용 — 이 종목의 최근 days 일 증권사 목표가(최신 먼저). 현재가 대비 0.3배 밑 · 5배 위 목표가는 잘못 읽은 것으로 보고 뺀다."""
    data = data if data is not None else load()
    cut = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    out = []
    for r in data.get("rows") or []:
        if r["code"] != code or r["at"] < cut:
            continue
        if close and r.get("pt") and not (0.3 <= r["pt"] / close <= 5):
            continue
        out.append(r)
    return sorted(out, key=lambda r: r["at"], reverse=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=0, help="이 날수만큼 처음부터 다시 읽기")
    a = ap.parse_args()
    run(a.days or None)
