"""FOMC 날짜표 — 회의 일정(연준 홈페이지) + 결정(연준 목표금리 FRED 시계열) (이슈 저장소 3절 2).

    python experiments/issue_store/fetch_fomc.py

저장: data/store/calendar/fomc.csv — day(결정 발표일 = 회의 마지막 날), scheduled(정기/긴급), sep(점도표 회의), decision(인상/동결/인하), change_bp, target_upper
- 회의 일정: fomchistorical{YYYY}.htm (6년 전까지) + fomccalendars.htm (최근). 긴급 회의 · 전화 회의는 '긴급'
- 결정: DFEDTAR(~2008-12-15) · DFEDTARU(2008-12-16~) 상단의 변화를 결정일 기준 다음 3영업일 안에서 찾는다
- 발표 시각: 14:00 ET (2011~ 기자회견 14:30). 2013 이전엔 시각이 달랐던 회의가 있다 — 반응은 당일 종가 · 다음 날로 본다
"""

import datetime
import html
import os
import re

import pandas as pd
import requests
from dotenv import dotenv_values

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "data", "store", "calendar")
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September",
                                      "October", "November", "December"], 1)}
UA = {"User-Agent": "Mozilla/5.0 (AlphaScope research)"}
# 긴급 전화 회의 → 발표일 (연준 보도자료 기준). 회의 페이지 날짜는 회의를 연 날이다
ANNOUNCED = {"2008-10-07": "2008-10-08",   # 각국 중앙은행 공조 인하, 10/8 07:00 ET
             "2020-03-02": "2020-03-03"}   # 코로나 긴급 인하, 3/3 10:00 ET


def _day(year, mon, dtext):
    """'27-28' · '31-1' (달 넘김) · '17' → 마지막 날 date. 'April 30-May 1' 같은 달 넘김은 다음 달로."""
    m = re.match(r"(\d+)(?:\s*-\s*(?:([A-Za-z]+)\s+)?(\d+))?", dtext.strip())
    first, mon2, last = m.group(1), m.group(2), m.group(3)
    end_mon = MONTHS.get(mon2, mon)
    if last and not mon2 and int(last) < int(first):
        end_mon = mon + 1
    return datetime.date(year + (1 if end_mon == 13 else 0), (end_mon - 1) % 12 + 1, int(last or first))


def historical(year):
    t = requests.get(f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{year}.htm", headers=UA, timeout=60).text
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))   # 글자만 — 'January 31-February 1 Meeting' 사이 태그 때문에 빠지던 것 (2017)
    out = []
    mon_re = r"(January|February|March|April|May|June|July|August|September|October|November|December|Jan/Feb|Apr/May|Oct/Nov|Jul/Aug|Mar/Apr|Nov/Dec)"
    for m in re.finditer(mon_re + r"\s+(\d+(?:\s*-\s*(?:[A-Za-z]+\s+)?\d+)?)\s*(\(unscheduled\)\s*Meeting|Meeting|\(unscheduled\)|Conference Call|\(notation vote\)|\(cancelled\))", t):
        kind = m.group(3)
        if "notation" in kind or "cancelled" in kind:
            continue
        mon = next(k for k in MONTHS if k.startswith(m.group(1).split("/")[0][:3]))   # 'Jan/Feb 31-1' 줄임 표기
        out.append({"day": _day(year, MONTHS[mon], m.group(2)), "scheduled": "unscheduled" not in kind and "Call" not in kind, "sep": None})
    return out


def recent():
    t = requests.get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", headers=UA, timeout=60).text
    out = []
    for block in re.split(r'<div class="panel panel-default">', t)[1:]:
        ym = re.search(r"(\d{4}) FOMC Meetings", block)
        if not ym:
            continue
        year = int(ym.group(1))
        for m in re.finditer(r'fomc-meeting__month[^>]*><strong>([A-Za-z/]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<', block, re.S):
            mon = next((k for k in MONTHS if k.startswith(m.group(1).split("/")[0][:3])), None)   # 'Jan/Feb' · 'Apr/May' 줄임 표기
            dtext = m.group(2)
            if not mon:
                continue
            unsched = "unscheduled" in dtext.lower() or "call" in dtext.lower()
            out.append({"day": _day(year, MONTHS[mon], re.sub(r"[^\d\-]", "", dtext.split("(")[0]) or dtext), "scheduled": not unsched, "sep": "*" in dtext})
    return out


def target_series():
    key = dotenv_values(os.path.join(ROOT, ".env")).get("FRED_API_KEY") or os.environ.get("FRED_API_KEY")
    s = []
    for sid in ("DFEDTAR", "DFEDTARU"):
        r = requests.get("https://api.stlouisfed.org/fred/series/observations", params={"series_id": sid, "api_key": key, "file_type": "json"}, timeout=60)
        r.raise_for_status()
        s += [(o["date"], float(o["value"])) for o in r.json()["observations"] if o["value"] != "."]
    ser = pd.Series(dict(s)).sort_index()
    ser.index = pd.to_datetime(ser.index)
    return ser[~ser.index.duplicated(keep="last")]


def main(first_year=1994):
    this = datetime.date.today().year
    rows = []
    for y in range(first_year, this + 1):
        try:
            got = historical(y)
        except Exception:
            got = []
        rows += got
    rows += recent()
    df = pd.DataFrame(rows)
    df["day"] = pd.to_datetime(df["day"])
    df = df.sort_values(["day", "scheduled"], ascending=[True, False]).drop_duplicates("day")   # 두 페이지 겹치는 해: 최근 페이지(sep 정보)가 뒤라 남게 — 아래에서 sep 합침
    sep = {pd.Timestamp(r["day"]): r["sep"] for r in recent()}
    df["sep"] = df["day"].map(sep).fillna(df["sep"])
    tgt = target_series()
    dec, bp, up = [], [], []
    for d in df["day"]:
        before = tgt[tgt.index < d]
        after = tgt[(tgt.index >= d) & (tgt.index <= d + pd.Timedelta(days=4))]
        if before.empty or after.empty or d > pd.Timestamp.today():
            dec.append(None); bp.append(None); up.append(None); continue
        ch = round((after.iloc[-1] - before.iloc[-1]) * 100)
        dec.append("인상" if ch > 0 else "인하" if ch < 0 else "동결"); bp.append(ch); up.append(after.iloc[-1])
    df["decision"], df["change_bp"], df["target_upper"] = dec, bp, up
    # 긴급 회의 페이지 날짜와 실제 발표일이 다른 경우 — FRED 적용일은 발표 다음 날일 때가 많아 쓰지 않고 발표일을 직접 적는다
    df["day"] = df["day"].replace({pd.Timestamp(k): pd.Timestamp(v) for k, v in ANNOUNCED.items()})
    # 목표금리가 바뀌었는데 짝이 되는 회의가 없는 날 = 회의 페이지에 없는 긴급 결정 (2008-10-08 공조 인하 · 2020-03-03 등)
    chg = tgt[tgt.diff().fillna(0) != 0]
    extra = []
    for d, v in chg.items():
        if d < df["day"].min():
            continue
        if ((df["day"] <= d) & (df["day"] >= d - pd.Timedelta(days=4))).any():
            continue
        prev = tgt[tgt.index < d].iloc[-1]
        ch = round((v - prev) * 100)
        extra.append({"day": d, "scheduled": False, "sep": None, "decision": "인상" if ch > 0 else "인하", "change_bp": ch, "target_upper": v})
    if extra:
        df = pd.concat([df, pd.DataFrame(extra)]).sort_values("day")
        print("회의 페이지에 없던 긴급 결정:", ", ".join(str(e["day"].date()) for e in extra))
    df["kind"], df["subkind"] = "금리", "FOMC"
    df["time_et"] = "14:00"
    os.makedirs(OUT, exist_ok=True)
    df["day"] = df["day"].dt.date
    df.to_csv(os.path.join(OUT, "fomc.csv"), index=False)
    print(f"FOMC {len(df)}회 ({df['day'].min()} ~ {df['day'].max()}) · 정기 {int(df['scheduled'].sum())} · 긴급 {int((~df['scheduled']).sum())}")
    print(df["decision"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
