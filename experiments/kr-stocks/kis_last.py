"""한국투자증권 최근 일봉 받기 — 집 IP(VPN newfact 계정)로, 대조용.

    HOME_SOURCE_ADDRESS=<ppp0 주소> python experiments/kr-stocks/kis_last.py --need /tmp/kis_need.json   # 워크플로가 쓰는 길(2026-11-26)

: 순서 = 야후 → 네이버 → 한국투자증권(맨 뒤, 부를 때마다 폰 알림). 워크플로(kr-stocks · quick-data)는 수집 **뒤**,
collect_kr._fix_last 가 남긴 `네이버도 못 받은 종목` 파일(--need)이 비어 있지 않을 때만 VPN 을 열고 이걸 부른다 — 평소 0번.
--need 는 그 종목만 받아 야후 마지막 봉이 맞나 틀리나만 로그에 적는다(종목 · 칸 이름만, 한국투자증권 값은 파일 · 로그에 남기지 않음 — 공개 실행 로그).

    HOME_SOURCE_ADDRESS=<ppp0 주소> python experiments/kr-stocks/kis_last.py            # 한국 종목 수집(kr-stocks) 35종목 · 지수 · ETF
    HOME_SOURCE_ADDRESS=<ppp0 주소> python experiments/kr-stocks/kis_last.py --quick --out PATH   # 간단 종목(한국 350)

왜: 11-23 야후가 한국 전 종목 시가 0.0 · 장 막판 전에서 멈춘 종가(삼성전자 177,500 vs 거래소 180,600)를 줬다.
한국투자증권 값은 **대조에만** 쓴다 — 야후와 다른 칸은 네이버 값으로 바꾼다(collect_kr._fix_last). 블로그에 싣는 값의 출처는 야후 · 네이버.
집 IP 로만 부른다(home_ip.session — VPN 주소가 없으면 예외, GitHub 주소로 몰래 나가지 않음). 개인 사용 모양 그대로: 실행마다 토큰 1번, 0.35초 간격(넘기면 1초 쉬고 한 번 더).
결과 = data/kis_last.json {"day": 오늘(KST), "fetched_at", "base": 실전/모의, "bars": {심볼: {날짜: 봉}}}. 실패하면 파일을 안 쓴다 → 수집기는 네이버로만 대조.
AI 0 · Blogger · gh-pages 쓰기 0.
"""

import argparse
import datetime
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, ".."))
import universe_kr as U  # noqa: E402
import etf_universe  # noqa: E402
import home_ip  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
GAP = 0.35   # 호출 사이(초) — 0.1 초는 `초당 거래건수 초과` 8/66 (2026-11-23 집 IP 시험)
OUT = os.path.join(BASE, "data", "kis_last.json")
KIS_INDEX = {U.BENCH: "0001", U.KOSDAQ: "1001"}
KIS_BASES = [("실전", "https://openapi.koreainvestment.com:9443"), ("모의", "https://openapivts.koreainvestment.com:29443")]


def kr_symbols():
    """한국 종목 수집(collect_kr.run_prices)이 받는 한국 심볼과 같은 목록."""
    syms = [c[0] for c in U.CANDIDATES] + [U.BENCH, U.KOSDAQ] + sorted(U.SECTOR_ETF_LIST) + sorted(etf_universe.KR_SYMS)
    return list(dict.fromkeys(s for s in syms if s in KIS_INDEX or s.endswith((".KS", ".KQ"))))


def _code(sym):
    if sym in KIS_INDEX:
        return KIS_INDEX[sym]
    c = sym.split(".")[0]
    return c if len(c) == 6 else None


def token(sess, key, sec):
    for name, base in KIS_BASES:
        try:
            j = sess.post(base + "/oauth2/tokenP", json={"grant_type": "client_credentials", "appkey": key, "appsecret": sec}, timeout=15).json()
        except Exception as e:   # noqa: BLE001
            print(f"[kis] 토큰 실패({name}): {str(e)[:80]}")
            continue
        if j.get("access_token"):
            return name, base, j["access_token"]
        print(f"[kis] 토큰 거절({name}): {(j.get('error_description') or j.get('msg1') or '')[:100]}")
    return None


def bars(sess, base, tok, key, sec, sym, start, end):
    idx = sym in KIS_INDEX
    path, tr = (("/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice", "FHKUP03500100") if idx else
                ("/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice", "FHKST03010100"))
    params = {"FID_COND_MRKT_DIV_CODE": "U" if idx else "J", "FID_INPUT_ISCD": _code(sym), "FID_INPUT_DATE_1": start.replace("-", ""),
              "FID_INPUT_DATE_2": end.replace("-", ""), "FID_PERIOD_DIV_CODE": "D"}
    if not idx:
        params["FID_ORG_ADJ_PRC"] = "0"
    hdr = {"content-type": "application/json; charset=utf-8", "authorization": "Bearer " + tok, "appkey": key, "appsecret": sec, "tr_id": tr, "custtype": "P"}
    j = sess.get(base + path, params=params, headers=hdr, timeout=10).json()
    if j.get("rt_cd") != "0":
        raise RuntimeError(j.get("msg1", "")[:80])
    pre = "bstp_nmix_" if idx else "stck_"
    out = {}
    for r in j.get("output2") or []:
        d = r.get("stck_bsop_date") or ""
        try:
            o, h, lo = float(r[pre + "oprc"]), float(r[pre + "hgpr"]), float(r[pre + "lwpr"])
            c = float(r[pre + "prpr"] if idx else r["stck_clpr"])
        except (KeyError, TypeError, ValueError):
            continue
        if len(d) == 8 and c > 0:
            day = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            out[day] = {"open": o, "high": h, "low": lo, "close": c, "volume": float(r.get("acml_vol") or 0)}
    return out


def check_need(need, got):
    """네이버도 못 받은 종목의 야후 마지막 봉 대조 — 로그엔 종목 · 칸 이름만(한국투자증권 값 X). 값은 바꾸지 않는다(야후 그대로)."""
    ok, diff, late, none = [], [], [], []
    for s, t in need.items():
        ref = got.get(s) or {}
        r = ref.get(t.get("day"))
        if not r:
            none.append(s)
            continue
        bad = [k for k in ("open", "high", "low", "close") if r.get(k) and abs((t.get(k) or 0) - r[k]) > 1e-6 * max(1.0, r[k])]
        (diff if bad else ok).append(f"{s}({'·'.join(bad)})" if bad else s)
        if any(d > t["day"] for d in ref):
            late.append(s)
    print(f"[kis] 대조 {len(ok) + len(diff)}줄 · 맞음 {len(ok)} · 다름 {len(diff)} · 늦은 봉 {len(late)} · 못 받음 {len(none)} (싣는 값 = 야후 그대로)")
    if diff or late:
        print(f"::warning::[kis] 야후 마지막 봉이 한국투자증권과 다름(네이버도 실패) — 화면 값 = 야후 그대로: "
              f"{', '.join(diff[:10])}" + (f" · 늦은 봉 {', '.join(late[:10])}" if late else ""))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--need", help="collect_kr._fix_last 가 쓴 확인 대상(JSON) — 그 종목만 받아 야후 마지막 봉과 대조, 결과는 로그만(파일 안 씀)")
    ap.add_argument("--codes", help="심볼 목록 파일(한 줄에 하나, 005930.KS · ^KS11) — 없으면 한국 종목 수집 목록")
    ap.add_argument("--quick", action="store_true", help="간단 종목(한국 350) 명단 = experiments/ref/quick_ref.json + 지수 · 업종 ETF")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--days", type=int, default=7, help="며칠 전부터 (늦은 봉 확인용)")
    a = ap.parse_args()
    need = None
    if a.need:
        try:
            with open(a.need, encoding="utf-8") as f:
                need = json.load(f).get("bars") or {}
        except (OSError, ValueError):
            need = {}
        if not need:   # 토큰도 받지 않는다 — 토큰 = 폰 알림
            print("[kis] 한국투자증권 건너뜀(필요 0)")
            return 0
    key, sec = os.environ.get("KIS_APP_KEY", "").strip(), os.environ.get("KIS_APP_SECRET", "").strip()
    if not (key and sec):
        print("::warning::[kis] 한국투자증권 키 없음 — 대조는 네이버로만")
        return 0
    try:
        sess = home_ip.session()
    except Exception as e:   # noqa: BLE001
        print(f"::warning::[kis] 집 IP 없음 — 대조는 네이버로만: {e}")
        return 0
    t = token(sess, key, sec)
    if not t:
        print("::warning::[kis] 한국투자증권 토큰을 못 받음 — 대조는 네이버로만")
        return 0
    name, base, tok = t
    if need is not None:
        syms = list(need)
    elif a.codes:
        syms = [x.strip() for x in open(a.codes, encoding="utf-8") if x.strip()]
    elif a.quick:
        with open(os.path.join(BASE, "..", "ref", "quick_ref.json"), encoding="utf-8") as f:
            syms = list(json.load(f)["kr"]) + [U.BENCH, U.KOSDAQ] + sorted(U.SECTOR_ETF_LIST)
        syms = list(dict.fromkeys(syms))
    else:
        syms = kr_symbols()
    today = datetime.datetime.now(KST).date()
    start, end = (today - datetime.timedelta(days=a.days)).isoformat(), today.isoformat()
    got, fail, t0 = {}, [], time.time()
    for s in syms:
        if not _code(s):
            continue
        try:
            try:
                b = bars(sess, base, tok, key, sec, s, start, end)
            except RuntimeError as e:   # 초당 건수 넘김 — 1초 쉬고 한 번 더
                if "초당" not in str(e):
                    raise
                time.sleep(1.0)
                b = bars(sess, base, tok, key, sec, s, start, end)
            if b:
                got[s] = b
            else:
                fail.append(s)
        except Exception as e:   # noqa: BLE001
            fail.append(s)
            if len(fail) <= 3:
                print(f"[kis] {s} 실패: {str(e)[:80]}")
        time.sleep(GAP)
    print(f"[kis] {name} · 집 IP · {len(got)}/{len(syms)} 받음 · {time.time() - t0:.0f}초" + (f" · 실패 {len(fail)}: {', '.join(fail[:8])}" if fail else ""))
    if need is not None:
        return check_need(need, got)
    if not got:
        print("::warning::[kis] 받은 것 0 — 파일 안 씀, 대조는 네이버로만")
        return 0
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"day": end, "fetched_at": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M %Z"), "base": name, "bars": got}, f, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
