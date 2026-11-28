"""ETF 로 실제 들어오고 나간 돈 — 운용사가 날마다 내는 기준가 · 좌수 · 순자산 이력.

    python experiments/etf_flows.py XLK XLE          # 로컬 확인 — 표만 찍는다

왜: 야후 ETF 순자산 칸은 며칠씩 안 바뀌어 좌수를 거꾸로 셀 수 없다. 운용사 파일은 좌수(Shares Outstanding)를 날마다 준다.
    하루 순유입 = (오늘 좌수 − 어제 좌수) × 오늘 기준가.  n일 순유입 = 그 합.
지금 받는 곳: 스테이트 스트리트(SPDR) — S&P 500 · 업종 11 · 세부 업종 7. 파일 하나에 상장 뒤 전체 이력이 들어 있어 지난 값도 다시 계산된다.
다른 운용사 ETF 는 SSGA 에 없으면 None(부르는 쪽이 줄을 비운다 — 다른 값으로 채우지 않는다).
하루 한 번만 받는다: cache_dir 를 주면 그날 받은 요약을 etf_flows.json 에 두고 같은 날 다시 부르지 않는다. 요청 사이 1초.
ETF 한 개로 들어온 돈이다 — 업계 전체의 돈이 아니다(화면 문구도 그렇게 쓴다).
"""
import datetime
import io
import json
import os
import re
import sys
import time
import zipfile

SSGA = {"SPY", "XLK", "XLF", "XLE", "XLV", "XLP", "XLY", "XLU", "XLI", "XLB", "XLRE", "XLC", "KBE", "KRE", "KIE", "XBI", "XOP", "XRT", "XME"}
SSGA_URL = "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/navhist-us-en-{}.xlsx"
SRC_NAME = "State Street"
DAYS = (5, 20, 60)
YEAR_N = 252
GAP_S = 1.0
_last_call = [0.0]


def _parse(blob):
    """navhist xlsx → [(날짜, 기준가, 좌수, 순자산)] 오래된 것 → 최신. 엑셀 라이브러리 없이 읽는다(칸 넷뿐)."""
    z = zipfile.ZipFile(io.BytesIO(blob))
    ss = [re.sub(r"<[^>]+>", "", x) for x in re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode("utf-8"), flags=re.S)]
    rows = []
    for r in re.findall(r"<row[^>]*>(.*?)</row>", z.read("xl/worksheets/sheet1.xml").decode("utf-8"), flags=re.S):
        c = [(ss[int(v)] if 't="s"' in at and v else v) for at, v in re.findall(r"<c ([^>]*)>(?:<v>(.*?)</v>)?", r)]
        if len(c) < 4:
            continue
        try:
            rows.append((datetime.datetime.strptime(c[0].strip(), "%d-%b-%Y").date().isoformat(), float(c[1]), float(c[2]), float(c[3])))
        except ValueError:
            continue   # 머리말 · 꼬리말 줄
    return sorted(rows)


def history(sym, tries=2):
    """운용사 이력. SSGA 에 없는 ETF · 실패는 None."""
    if sym not in SSGA:
        return None
    import requests
    for k in range(tries):
        wait = GAP_S - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        try:
            r = requests.get(SSGA_URL.format(sym.lower()), headers={"User-Agent": "Mozilla/5.0"}, timeout=40)
            r.raise_for_status()
            rows = _parse(r.content)
            if len(rows) > max(DAYS):
                return rows
        except Exception as ex:  # noqa: BLE001
            print(f"[etf-flow] {sym} 이력 받기 실패({k + 1}): {str(ex)[:120]}")
    return None


def daily_flows(rows):
    """[(날짜, 그날 순유입 달러)] — (오늘 좌수 − 어제 좌수 × 분할 비율) × 오늘 기준가.
    주식 분할 · 병합 날(기준가가 1/k 로, 좌수가 k 배로 같이 뛴 날)은 어제 좌수를 k 배로 맞춰 센다 — 안 맞추면 분할이 통째로 유입으로 잡힌다."""
    out = []
    for i in range(1, len(rows)):
        (_, n0, s0, _), (d, n1, s1, _) = rows[i - 1], rows[i]
        k = 1.0
        if n0 > 0 and n1 > 0 and s0 > 0:
            pr, sr = n0 / n1, s1 / s0
            for cand in (2, 3, 4, 5, 10, 1 / 2, 1 / 3, 1 / 4, 1 / 5, 1 / 10):
                if abs(pr / cand - 1) < 0.12 and abs(sr / cand - 1) < 0.12:
                    k = cand
                    break
        out.append((d, (s1 - s0 * k) * n1))
    return out


WEEK_STEP, WEEK_N = 5, 24   # 카드 선 그래프 — 5거래일마다 쌓은 값, 120거래일(약 여섯 달)


def weekly(rows, n=WEEK_N, step=WEEK_STEP):
    """최근 n×step 거래일 순유입을 step 거래일마다 쌓은 값 → {"labels": ["6.12", …], "vals": [달러, …]}. 첫 점 = 첫 묶음까지 쌓인 값."""
    fl = daily_flows(rows)[-n * step:]
    labels, vals, acc = [], [], 0.0
    for k in range(0, len(fl), step):
        chunk = fl[k:k + step]
        acc += sum(v for _, v in chunk)
        d = chunk[-1][0]
        labels.append(f"{int(d[5:7])}.{int(d[8:])}")
        vals.append(round(acc, 0))
    return {"labels": labels, "vals": vals, "step": step}


def summary(rows):
    """이력 → 마지막 날 값과 5 · 20 · 60거래일 순유입(달러 · 그 구간 첫날 순자산 대비 %)."""
    d, nav, sh, aum = rows[-1]
    out = {"as_of": d, "nav": nav, "units": sh, "aum": aum, "src": "ssga"}
    fl = daily_flows(rows)
    if len(rows) > WEEK_N * WEEK_STEP:
        out["weekly"] = weekly(rows)
    for n in DAYS:
        if len(rows) > n:
            flow = sum(v for _, v in fl[-n:])
            base = rows[-n - 1][3]
            out[f"flow{n}"] = round(flow, 0)
            out[f"flow{n}_pct"] = round(flow / base * 100, 2) if base else None
    v = [x for _, x in fl[-YEAR_N - 20:]]
    if len(v) > 60:   # 비교 대상 — 지난 1년 20거래일 순유입의 아래 4분의 1 · 가운데 · 위 4분의 1 (ETF 페이지 `이 ETF에 돈이 들어오나?`)
        s20 = sorted(sum(v[i:i + 20]) for i in range(len(v) - 20))
        q = lambda p: s20[min(len(s20) - 1, int(p * (len(s20) - 1)))]  # noqa: E731
        out["flow20_q"] = [round(q(0.25), 0), round(q(0.5), 0), round(q(0.75), 0)]
    return out


def fund(sym, cache_dir=None):
    """ETF 한 개의 요약(summary). cache_dir 가 있으면 오늘(UTC) 받은 값을 다시 받지 않는다. 없으면 None."""
    if sym not in SSGA:
        return None
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(cache_dir, "etf_flows.json") if cache_dir else None
    cache = {}
    if path and os.path.exists(path):
        try:
            cache = json.load(open(path, encoding="utf-8"))
        except ValueError:
            cache = {}
    if cache.get("day") == today and "flow20_q" in ((cache.get("funds") or {}).get(sym) or {}):   # 비교 대상 칸이 없는 옛 요약은 다시
        return cache["funds"][sym]
    rows = history(sym)
    if not rows:
        return None
    out = summary(rows)
    if path:
        cache = cache if cache.get("day") == today else {"day": today, "funds": {}}
        cache["funds"][sym] = out
        os.makedirs(cache_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for s in sys.argv[1:] or ["XLK"]:
        x = fund(s)
        print(s, "없음" if not x else f"{x['as_of']} 순자산 {x['aum'] / 1e8:,.0f}억$ · 20일 {x['flow20'] / 1e8:+,.1f}억$ ({x['flow20_pct']:+.1f}%) · 5일 {x['flow5'] / 1e8:+,.1f} · 60일 {x['flow60'] / 1e8:+,.1f}")
