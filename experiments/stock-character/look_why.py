"""뉴팩트 개성 있는 아이 찾기 게임 — 5단계 "왜" 첫 걸음: 테슬라 한 명의 3년 시간표 (2026-11-24 사용자 "이제 남은 이유라든지 이런 거 할 수 있어?" → "그렇게 해").

길잡이 = 비공개 alphascope-docs/doc/기획/종목-그래프-패턴-분류-목적.md 0-0 · 0-4 · 7-21.
한 아이(테슬라)만 본다(바닥 규칙 7). 새 칸 · 새 문턱 없음 — 기준 설정(최근 3년 · 20일 간격 · 가운데 80% · 칸 넷 · 3구간 이어짐)의 드러난 시기를
look_band.compute() 값 그대로 다시 구하고, 그 앞뒤에 있던 일을 우리가 가진 자료로만 늘어놓는다. 판정하지 않는다(점검 16).
  자료: 일봉 · 거래량(bars_us.pkl) · 실적 발표(earn_days_us.csv) · SEC 수시 공시 항목 번호(earn_raw/us/*.json, 본문은 안 읽음) · 시장 전체가 흔들린 날(파도).
  비교 대상(헌법 제1조): 테슬라 자신의 드러난 시기 안 ↔ 뒤, 그리고 같은 구간의 S&P 500 대부분의 종목(가운데 80%). 새 AI 호출 · 수집 0.

    python experiments/stock-character/look_why.py      # → output/mock_why_TSLA.html — 목업 목록 `개성 있는 아이 찾기 게임`
"""

import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import look_band as LB  # noqa: E402
import look_stones as LS  # noqa: E402

SYM, KO = "TSLA", "테슬라"
W, BAND, MINRUN = 20, 80, 3          # 기준 설정(길잡이 0-4)
OUT = os.path.join(HERE, "output", f"mock_why_{SYM}.html")
RAW = os.path.join(LB.STORE, "earn_raw", "us")
# SEC 8-K 항목 번호의 공식 이름(우리말로). 9.01(첨부 서류)은 다른 항목에 붙어 나오는 것이라 화면에 안 적는다.
ITEM = {"1.01": "중요한 계약 체결", "1.02": "중요한 계약 종료", "1.03": "파산 · 법정관리", "2.01": "자산 인수 · 처분 완료", "2.03": "회사 채무 발생",
        "2.04": "채무 조기 상환 사유 발생", "2.05": "구조조정 비용", "2.06": "자산 손상", "3.01": "상장 유지 문제", "3.02": "등록하지 않은 주식 발행",
        "3.03": "주주 권리 변경", "4.01": "감사인 변경", "4.02": "이전 재무제표 정정", "5.01": "지배권 변경", "5.02": "임원 · 이사 선임 · 퇴임 · 보수",
        "5.03": "정관 변경", "5.05": "윤리 강령 변경", "5.07": "주주총회 표결 결과", "5.08": "주주 추천 이사 후보 일정", "7.01": "공정 공시 자료",
        "8.01": "기타 중요 사항"}


def q(a, p):
    """화면(look_band_page.html)의 q 와 같은 사이 값."""
    i = (len(a) - 1) * p
    f = int(np.floor(i))
    return a[f] + (a[min(f + 1, len(a) - 1)] - a[f]) * (i - f)


def filings(path, d0):
    """실적 외 8-K(2.02 가 없는 것) — 접수일 목록."""
    j = json.load(open(path))
    return j.get("cik"), [r for r in j["rows"] if r["form"] == "8-K" and r["filed"] >= d0 and "2.02" not in r["items"]]


def main():
    R = LB.compute()
    rows, labels, days, waves = R["rows"], R["labels"][W], R["days"], R["waves"]
    np_ = len(labels)
    t = (100 - BAND) / 200
    me = next(x for x in rows if x["s"] == SYM)
    lim = []                                    # 구간마다 칸 [하루 폭, 돌 수]의 (아래 끝, 가운데, 위 끝)
    for p in range(np_):
        lim.append([])
        for c in (0, 1):
            v = sorted(x["w"][W][p][c] for x in rows if x["w"][W][p])
            lim[p].append([q(v, t), q(v, .5), q(v, 1 - t)])
    # 평범 밖 = 칸 넷 중 하나라도 범위 밖(화면과 같은 판정)
    mix = []
    for p in range(np_):
        r = me["w"][W][p]
        if not r:
            mix.append(None)
            continue
        side = 0
        for c in range(4):
            v = sorted(x["w"][W][p][c] for x in rows if x["w"][W][p])
            lo, hi = q(v, t), q(v, 1 - t)
            side |= 1 if r[c] > hi else 2 if r[c] < lo else 0
        mix.append(side)
    runs, cur = [], None
    for p, v in enumerate(mix):
        if v is None:
            continue
        if v:
            if cur is None:
                cur = [p, p]
                runs.append(cur)
            cur[1] = p
        else:
            cur = None
    shown = [r for r in runs if r[1] - r[0] + 1 >= MINRUN]
    short = [r for r in runs if r[1] - r[0] + 1 < MINRUN]
    a0, b0 = shown[0]                          # 테슬라는 드러난 시기가 하나(길잡이 7-20)
    inside = list(range(a0, b0 + 1))
    after = [p for p in range(b0 + 1, np_) if me["w"][W][p]]

    # 일 목록
    d = R["bars"][SYM]
    d = d[(d["open"] > 0) & (d["volume"] > 0)]
    idx, ret = d.index, (d["close"].pct_change() * 100).values
    vm = (d["volume"] / d["volume"].rolling(250, min_periods=60).median()).values
    eg = R["earn"][R["earn"]["sym"] == SYM]
    sched = LS.sched_days(idx, eg)
    main_days = {e[0] for e in me["e"]}
    span = [tuple(s.split(" ~ ")) for s in labels]
    piece = lambda ds: next((p for p, (a, b) in enumerate(span) if a <= ds <= b), None)
    ev = []
    for e in me["e"]:
        ev.append({"d": e[0], "k": "실적", "r": e[1], "x": f"실적 발표 뒤 첫 거래일 · 평소 하루 등락 {e[2]:.1f}%"})
    for i, tm in enumerate(idx):
        ds = str(tm.date())
        if tm < days[0] or abs(ret[i]) < LS.STONE or ds in main_days:
            continue
        if i in sched:
            ev.append({"d": ds, "k": "실적 곁", "r": round(float(ret[i]), 1), "x": "실적 항목 공시가 있던 날 앞뒤(본 발표가 아닌 것)"})
        elif tm in waves:
            ev.append({"d": ds, "k": "시장", "r": round(float(ret[i]), 1), "x": "시장 전체가 흔들린 날(S&P 500 의 20% 넘는 종목이 ±5%)"})
        else:
            ev.append({"d": ds, "k": "돌", "r": round(float(ret[i]), 1), "x": f"예고 없는 돌 · 거래량 평소의 {vm[i]:.1f}배"})
    cik, fl = filings(os.path.join(RAW, f"{SYM}.json"), str(days[0].date()))
    for r in fl:
        names = [ITEM.get(k, k) for k in r["items"].split(",") if k and k != "9.01"]
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{r['acc'].replace('-', '')}/" if cik else ""
        ev.append({"d": r["filed"], "k": "공시", "r": None, "x": " · ".join(names), "u": url})
    for e in ev:
        e["p"] = piece(e["d"])
    ev = [e for e in ev if e["p"] is not None]
    ev.sort(key=lambda e: (e["d"], e["k"]))

    # 견주기 — 드러난 시기 안 ↔ 뒤
    med = lambda a: float(np.median(a)) if len(a) else None
    v0 = lambda ps: med([me["w"][W][p][0] for p in ps])
    h0 = lambda ps: med([lim[p][0][2] for p in ps])
    v1 = lambda ps: float(np.mean([me["w"][W][p][1] for p in ps]))
    h1 = lambda ps: med([lim[p][1][2] for p in ps])
    # 실적 외 공시 — 구간 하나에 몇 건. S&P 500 은 회사마다 같은 구간의 건수 평균 → 가운데 값
    def rate(rs, ps):
        return sum(1 for r in rs if piece(r["filed"]) in ps) / len(ps)
    rates_in, rates_af = [], []
    for f in glob.glob(os.path.join(RAW, "*.json")):
        _, rs = filings(f, str(days[0].date()))
        rates_in.append(rate(rs, set(inside)))
        rates_af.append(rate(rs, set(after)))
    e_in = [abs(e[1]) for e in me["e"] if piece(e[0]) in inside]
    e_af = [abs(e[1]) for e in me["e"] if piece(e[0]) in after]
    # S&P 500 — 회사마다 같은 구간 실적 반응 크기의 가운데 값 → 그 가운데 값
    ein_all = [med([abs(e[1]) for e in x["e"] if piece(e[0]) in inside]) for x in rows]
    eaf_all = [med([abs(e[1]) for e in x["e"] if piece(e[0]) in after]) for x in rows]
    ein_all, eaf_all = [v for v in ein_all if v is not None], [v for v in eaf_all if v is not None]
    cmp_ = [["평소 하루 폭", f"{v0(inside):.1f}%", f"{v0(after):.1f}%", f"{h0(inside):.1f}%", f"{h0(after):.1f}%", "구간마다의 가운데 값"],
            ["예고 없는 돌 수", f"{v1(inside):.1f}일", f"{v1(after):.1f}일", f"{h1(inside):.0f}일", f"{h1(after):.0f}일", "구간 하나에 평균"],
            ["실적 외 공시", f"{rate(fl, set(inside)):.2f}건", f"{rate(fl, set(after)):.2f}건", f"{med(rates_in):.2f}건", f"{med(rates_af):.2f}건", "구간 하나에 평균 · S&P 500 은 가운데 값"],
            ["실적 발표 반응", f"{med(e_in):.1f}%", f"{med(e_af):.1f}%", f"{med(ein_all):.1f}%", f"{med(eaf_all):.1f}%",
             f"첫 거래일 등락 크기 가운데 값 · {KO} 안 {len(e_in)}번 · 뒤 {len(e_af)}번 · S&P 500 은 회사마다의 가운데 값의 가운데 값"]]
    data = {"sym": SYM, "ko": KO, "labels": labels, "last": str(R["last"].date()), "first": str(days[0].date()),
            "v": [me["w"][W][p][:2] if me["w"][W][p] else None for p in range(np_)], "lim": lim, "mix": mix,
            "run": [a0, b0], "short": short, "ev": ev, "cmp": cmp_, "nkids": len(rows), "nfirms": len(rates_in)}
    head = open(os.path.join(HERE, "look_band_page.html"), encoding="utf-8").read()
    head = head[:head.index("</style>")]           # 디자인 값은 원본 화면과 같은 것을 쓴다
    head = re.sub(r"<title>.*?</title>", f"<title>{KO} 왜 시간표</title>", head)
    page = open(os.path.join(HERE, "look_why_page.html"), encoding="utf-8").read()
    html = head + page.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    open(OUT, "w", encoding="utf-8").write(html)
    print(f"화면 → {OUT} · 드러난 시기 {labels[a0].split(' ~ ')[0]} ~ {labels[b0].split(' ~ ')[1]} ({b0 - a0 + 1}구간) · 짧게 스친 것 {len(short)}번 · 일 {len(ev)}건 · {os.path.getsize(OUT) // 1024}KB")
    for c in cmp_:
        print("  " + " | ".join(c))


if __name__ == "__main__":
    main()
