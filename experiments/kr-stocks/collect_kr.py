"""한국 종목 수집 — 일봉 · 시총(yfinance) + 자금 흐름(한국은행 ECOS) (기획 11-4 · 11-5).

yfinance 는 미국 종목과 같은 소스 · 같은 약관 위험(운영지침 D4-7)이고 예비 사슬은 없다(한국 종목은 유료 등급) —
막히면 그 실행은 "자료 지연" 으로 끝내고 알림만 보낸다. 안전장치: 묶음 다운로드 우선, 개별 호출은 순서대로 0.5초 간격.
ECOS 는 공공데이터포털 "이용허락범위 제한 없음" (D4-15). 하루 호출 3~4번.

    python collect_kr.py          # 받기 → data/snapshot.json · data/flows.json · data/history.json
    python collect_kr.py --show   # 받은 것 요약만
"""
import datetime
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

import universe_kr as U

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, ".."))
import notify  # noqa: E402

DATA = os.path.join(BASE, "data")
SNAP = os.path.join(DATA, "snapshot.json")
FLOWS = os.path.join(DATA, "flows.json")
HIST = os.path.join(DATA, "history.json")
HIST_MAX_AGE_DAYS = 7
KST = ZoneInfo("Asia/Seoul")
GAP = 0.5            # 개별 호출 사이 (초)
ECOS = "https://ecos.bok.or.kr/api"

# ECOS 통계표 · 항목 (2026-10-24 샘플 키로 확인, 운영지침 D4-15)
ECOS_DAILY = ("802Y001", {"0030000": "foreign_kospi", "0113000": "foreign_kosdaq", "0001000": "kospi", "0089000": "kosdaq",
                          "0087000": "volume_kospi", "0088000": "turnover_kospi", "0090000": "volume_kosdaq", "0091000": "turnover_kosdaq",
                          "0183000": "mcap_kospi"})          # 억원 · 지수 · 만주 · 억원
# 그 밖의 일별 표 (2026-10-24 사용자: 뉴스심리 · 금리 · 환율도) — (표, 주기, {항목: 이름})
ECOS_DAILY_MORE = [
    ("523Y001", "D", {"A001": "news_sentiment"}),                                             # 뉴스심리지수 (한국은행 실험적 통계, 2005~, 약 1주 지연)
    ("817Y002", "D", {"010200000": "ktb3", "010210000": "ktb10", "010300000": "corp_aa", "010320000": "corp_bbb"}),   # 시장금리 연%
    ("722Y001", "D", {"0101000": "base_rate"}),                                               # 한국은행 기준금리
    ("731Y001", "D", {"0000001": "usdkrw", "0000002": "jpykrw100", "0000053": "cnykrw"}),      # 매매기준율 원
]
ECOS_MONTHLY_MORE = [
    ("901Y014", "M", {"1100000": "div_yield", "1110000": "per", "1090000": "turnover_ratio", "1040000": "mcap_kospi_m"}),   # 배당수익률 % · PER 배 · 회전율 % · 시총 천원
    ("901Y057", "M", {"S25D": "fut_amt_avg"}),                                                 # 주가지수선물 일평균 계약금액 백만원
    ("901Y058", "M", {"S26BA": "call_vol", "S26CA": "put_vol", "S26AD": "opt_amt_avg"}),        # 옵션 거래량 계약 · 일평균 거래대금 백만원
    # 경제 바탕 (2026-10-24 사용자: "코스피가 올라도 물가 · 생산 지표가 나쁘면 반영이 안 될 수 있다") — 월별, 전년 동월 대비 · 1년 범위로 본다
    ("901Y009", "M", {"0": "cpi"}),                     # 소비자물가지수 2020=100 (국가데이터처)
    ("404Y014", "M", {"*AA": "ppi"}),                   # 생산자물가지수 2020=100
    ("513Y001", "M", {"E1000": "esi"}),                 # 경제심리지수(원계열)
    ("511Y002", "M", {"FME": "csi"}),                   # 소비자심리지수
    ("512Y013", "M", {"99988/AA": "bsi"}),              # 기업경기조사 전산업 업황실적 BSI (항목 둘)
    ("901Y118", "M", {"T002": "exports"}),              # 수출금액 천불 (관세청)
    ("901Y083", "M", {"166A": "emp_insured"}),          # 고용보험 가입자수 합계 (고용 대리 지표, 한국고용정보원)
    ("901Y033", "M", {"A00": "ip"}),                    # 전산업생산지수(농림어업 제외) 2020=100
    ("901Y067", "M", {"I16E": "lead_cycle"}),           # 경기선행지수 순환변동치
    ("403Y005", "M", {"A": "tot"}),                     # 순상품 교역조건지수 2020=100 (K12 — 검증: 높았던 달 뒤 수출형 묶음 오히려 부진, 값만)
]
BSI_START = "200901"   # 업종별 BSI 전 기간 (K5 바닥권 = 역대 하위 25% 를 재야 해서 짧게 받지 않는다)
FRED_DAILY = {"DCOILWTICO": "wti"}   # K21 WTI 유가 (FRED 공공, 일별) → 한국전력 카드 · 목록 '밤사이 미국' 카드
# 기업경영분석(분기, 한국은행) — 전산업 · 종합 (2026-10-24 사용자: "기업 경영분석 · 손익 지표도"). 항목 셋 = 산업/규모/지표
ECOS_QUARTERLY = [
    ("502Y002", "Q", {"1000/A/3000": "op_margin"}),     # 매출액영업이익률 % (전산업 · 종합)
    # 가계 — 개인의 매수 여력 (2026-10-24 사용자: "가계소득도 자금 수급에 도움되지 않나")
    ("901Y116", "Q", {"1/I36U/I36A": "hh_surplus", "1/I36V/I36A": "hh_surplus_rate", "1/I36T/I36A": "hh_disp_income"}),   # 가구당 월평균 가계수지(1인 이상 · 명목 · 전체가구): 흑자액 원 · 흑자율 % · 처분가능소득 원
    ("151Y001", "Q", {"1000000": "hh_credit"}),         # 가계신용 잔액 십억원
    ("281Y002", "Q", {"S14/F071ZZB/A": "hh_stock"}),    # 자금순환 잔액표: 가계 및 비영리단체가 보유한 거주자 발행 주식 · 출자지분 십억원
    ("281Y001", "Q", {"S14/F071ZZB/C": "hh_stock_buy"}),   # 자금순환 거래표: 가계의 거주자 주식 순취득(분기) 십억원
]
# 가계 금융자산 합계 = 잔액표 상위 항목 12개의 합 (합계 항목이 따로 없다) — 주식 비중의 분모
ECOS_HH_FIN_TOTAL = ("281Y002", "S14/?/A", {"F01ZZB", "F02TZB", "F03ZTB", "F04TTB", "F05TTB", "F06ZTB", "F07ZZB", "F08ZZB", "F09ZTB", "F11ZDB", "F12ZDB", "F13ZZB"})
ECOS_INVESTOR = ("901Y055", {"S22CA": "inst", "S22CB": "indiv", "S22CC": "foreign", "S22CD": "foreign_other", "S22CF": "corp_other",   # 순매수 (월, 백만원 — 천주 행은 버림)
                             "S22AA": "inst_sell", "S22AB": "indiv_sell", "S22AC": "foreign_sell", "S22AD": "foreign_other_sell", "S22AF": "corp_other_sell", "S22A": "all_sell",   # 매도
                             "S22BA": "inst_buy", "S22BB": "indiv_buy", "S22BC": "foreign_buy", "S22BD": "foreign_other_buy", "S22BF": "corp_other_buy", "S22B": "all_buy"})      # 매수
ECOS_FUNDS = ("901Y056", {"S23A": "deposits", "S23D": "margin_unpaid", "S23E": "credit_loan", "S23F": "credit_lend"})   # 월, 원


def _ecos_key():
    k = os.environ.get("ECOS_API_KEY", "").strip()
    if not k:
        try:
            from dotenv import load_dotenv
            load_dotenv(os.path.join(BASE, "..", "..", ".env"))
            k = os.environ.get("ECOS_API_KEY", "").strip()
        except ImportError:
            pass
    return k


# ── 일봉 · 시총 (yfinance) ────────────────────────────────────────────

def _bars(symbols, period="2y"):
    """묶음 다운로드 한 번. 비면 빈 dict (예비 없음 — 한국 종목은 유료 공급자뿐)."""
    df = yf.download(symbols, period=period, interval="1d", auto_adjust=False, group_by="ticker", progress=False, threads=3)
    out = {}
    for s in symbols:
        try:
            sub = df[s] if isinstance(df.columns, pd.MultiIndex) else df
            sub = sub.dropna(subset=["Close"])
        except (KeyError, TypeError, ValueError):
            continue
        if sub.empty:
            continue
        out[s] = [{"day": i.strftime("%Y-%m-%d"), "open": float(r["Open"]) if r["Open"] == r["Open"] else None, "high": float(r["High"]), "low": float(r["Low"]),
                   "close": float(r["Close"]), "adj": float(r["Adj Close"]), "volume": float(r["Volume"] or 0)} for i, r in sub.iterrows()]
    return out


def _caps(symbols):
    """시총 — 종목마다 fast_info 한 번, 0.5초 간격 (원화)."""
    out = {}
    for s in symbols:
        try:
            out[s] = float(yf.Ticker(s).fast_info.market_cap or 0) or None
        except Exception as e:   # noqa: BLE001
            print(f"[kr] {s} 시총 실패: {str(e)[:80]}")
            out[s] = None
        time.sleep(GAP)
    return out


def run_prices():
    syms = [c[0] for c in U.CANDIDATES]
    bars = _bars(syms + [U.BENCH, U.KOSDAQ])
    got = [s for s in syms if s in bars]
    if len(got) < len(syms) // 2:
        notify.event("수집 실패", f"한국 종목 일봉 {len(got)}/{len(syms)} — yfinance 응답 부족, 이 실행은 자료 지연")
        return None
    caps = _caps(got)
    # 미국 연결 짝(기획 11-3)의 최근 봉 — 밤사이 미국 움직임 → 오늘 한국 반응 카드. 묶음 한 번
    us = sorted({t for s in syms for t in U.PAIRS.get(s, ([], ""))[0]} | set(U.ADR.values()) | set(U.US_MARKET))   # 짝 + ADR(K24) + 미국 시장 변수(K25)
    us_bars = _bars(us, period="1mo") if us else {}
    snap = {"fetched_at": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M %Z"), "bars": bars, "caps": caps, "us_bars": us_bars,
            "missing": [s for s in syms if s not in bars]}
    os.makedirs(DATA, exist_ok=True)
    with open(SNAP, "w", encoding="utf-8") as f:
        json.dump(snap, f)
    last = max(b[-1]["day"] for s, b in bars.items() if s in syms)
    print(f"[kr] 일봉 {len(got)}/{len(syms)}종목 · 마지막 {last} · 시총 {sum(1 for v in caps.values() if v)}개 → {SNAP}")
    return snap


def history():
    """고점 하락 후 회복 통계 — 1999년부터(상장이 늦으면 상장부터), 비교는 KOSPI 같은 기간. 일주일에 한 번. 계산은 NVDA 리포트 history_stats 와 같다."""
    try:
        with open(HIST, encoding="utf-8") as f:
            h = json.load(f)
        if (datetime.date.today() - datetime.date.fromisoformat(h["built"])).days < HIST_MAX_AGE_DAYS:
            return h
    except (OSError, ValueError, KeyError):
        pass
    sys.path.insert(0, os.path.join(BASE, "..", "nvda-report"))
    import history_stats as HS
    syms = [c[0] for c in U.CANDIDATES] + [U.BENCH]
    df = yf.download(syms, start="1999-01-01", interval="1d", auto_adjust=False, group_by="ticker", progress=False, threads=3)
    out = {"built": datetime.date.today().isoformat(), "bench": U.BENCH, "stats": {}}
    try:
        bench = df[U.BENCH]["Close"].dropna()
    except KeyError:
        print("[kr] KOSPI 이력 없음 — 고점 회복 통계 건너뜀")
        return out
    for s in syms:
        try:
            c = df[s]["Close"].dropna()
        except KeyError:
            continue
        c = c[c > 0]
        if len(c) < 500:
            continue
        out["stats"][s] = {"from": c.index[0].strftime("%Y-%m-%d"), "to": c.index[-1].strftime("%Y-%m-%d"), "dd": HS.dd_summary(HS.drawdown_cycles(c)),
                           "bench_dd": HS.dd_summary(HS.drawdown_cycles(bench[bench.index >= c.index[0]]))}
    os.makedirs(DATA, exist_ok=True)
    with open(HIST, "w", encoding="utf-8") as f:
        json.dump(out, f)
    print(f"[kr] 고점 회복 통계 {len(out['stats'])}종목 → {HIST}")
    return out


# ── 자금 흐름 (ECOS) ──────────────────────────────────────────────────

def _customs(hs_list, years=3):
    """관세청 품목별 수출 (공공데이터포털 15100475 · 이용허락범위 제한 없음, 2026-10-31) — HS 품목들의 월 수출금액(달러) 합, 최근 years 해.
    국가 코드 없이 부르면 나라별 · 월별 줄 + 총계가 온다 → 월마다 나라별 줄을 더한다. 한 번에 1년만. 키 DATA_GO_KR_API_KEY 가 없으면 빈 목록."""
    import xml.etree.ElementTree as ET
    k = os.environ.get("DATA_GO_KR_API_KEY", "").strip()
    if not k:
        try:
            from dotenv import load_dotenv
            load_dotenv(os.path.join(BASE, "..", "..", ".env"))
            k = os.environ.get("DATA_GO_KR_API_KEY", "").strip()
        except ImportError:
            pass
    if not k:
        print("[kr] 관세청 키(DATA_GO_KR_API_KEY) 없음 — 방산 수출 건너뜀")
        return []
    y1 = datetime.date.today().year
    mon = {}
    for hs in hs_list:
        for y in range(y1 - years + 1, y1 + 1):
            try:
                r = requests.get("https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList",
                                 params={"serviceKey": k, "strtYymm": f"{y}01", "endYymm": f"{y}12", "hsSgn": hs}, timeout=60)
                root = ET.fromstring(r.content)
                if root.findtext("header/resultCode") != "00":
                    print(f"[kr] 관세청 {hs}/{y}: {(root.findtext('header/resultMsg') or '')[:60]}")
                    continue
                for it in root.findall("body/items/item"):
                    ym = it.findtext("year") or ""
                    if len(ym) == 7 and ym[4] == ".":
                        mon[f"{ym[:4]}-{ym[5:]}"] = mon.get(f"{ym[:4]}-{ym[5:]}", 0.0) + float(it.findtext("expDlr") or 0)
            except Exception as e:   # noqa: BLE001
                print(f"[kr] 관세청 {hs}/{y} 실패: {str(e)[:80]}")
            time.sleep(0.3)
    return [{"month": m, "v": v} for m, v in sorted(mon.items())]


def _ecos(key, stat, cycle, start, end, item, n=2000):
    """item 은 항목 코드 하나, 또는 항목이 둘인 표는 "ITEM1/ITEM2" (예: 기업경기조사 전산업/업황실적)."""
    url = f"{ECOS}/StatisticSearch/{key}/json/kr/1/{n}/{stat}/{cycle}/{start}/{end}/{item}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    j = r.json()
    if "StatisticSearch" not in j:
        raise RuntimeError(f"ECOS {stat}/{item}: {j.get('RESULT', {}).get('MESSAGE', '')[:120]}")
    return j["StatisticSearch"].get("row") or []


def run_flows():
    """외국인 일별 순매수(유가증권 · 코스닥) + KOSPI · KOSDAQ · 거래대금 · 시총(일) / 투자자별 월별 순매수 / 예탁금 · 미수금 · 신용융자(월)."""
    key = _ecos_key()
    if not key:
        print("[kr] ECOS_API_KEY 없음 — 자금 흐름 건너뜀")
        return None
    today = datetime.date.today()
    d0 = (today - datetime.timedelta(days=800)).strftime("%Y%m%d")
    d1 = today.strftime("%Y%m%d")
    out = {"fetched_at": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M %Z"), "daily": {}, "investor_m": {}, "funds_m": {}, "source": "한국은행 ECOS (자료: 한국거래소 · 금융투자협회)"}
    stat, items = ECOS_DAILY
    for item, key_name in items.items():
        rows = _ecos(key, stat, "D", d0, d1, item)
        out["daily"][key_name] = [{"day": f"{x['TIME'][:4]}-{x['TIME'][4:6]}-{x['TIME'][6:]}", "v": float(x["DATA_VALUE"])} for x in rows if x.get("DATA_VALUE") not in (None, "")]
        time.sleep(0.3)
    out["more_d"] = {}
    for stat, cyc, items in ECOS_DAILY_MORE:
        for item, key_name in items.items():
            try:
                rows = _ecos(key, stat, cyc, d0, d1, item)
                out["more_d"][key_name] = [{"day": f"{x['TIME'][:4]}-{x['TIME'][4:6]}-{x['TIME'][6:]}", "v": float(x["DATA_VALUE"])} for x in rows if x.get("DATA_VALUE") not in (None, "")]
            except Exception as e:   # noqa: BLE001 — 표 하나가 비어도 나머지는 살린다
                print(f"[kr] ECOS {stat}/{item} 실패: {str(e)[:80]}")
            time.sleep(0.3)
    m0 = (today.replace(day=1) - datetime.timedelta(days=366 * 3)).strftime("%Y%m")   # 월별은 3년치 — 전년 동월 대비 · 12개월 범위에 넉넉 (검증은 별도 스크립트가 전 기간을 받는다)
    m1 = today.strftime("%Y%m")
    stat, items = ECOS_INVESTOR
    for item, key_name in items.items():
        rows = _ecos(key, stat, "M", m0, m1, item)
        out["investor_m"][key_name] = [{"month": f"{x['TIME'][:4]}-{x['TIME'][4:]}", "v": float(x["DATA_VALUE"])} for x in rows
                                       if (x.get("UNIT_NAME") or "").strip() == "백만원" and x.get("DATA_VALUE") not in (None, "")]   # 금액 행만 (천주 행은 버림)
        time.sleep(0.3)
    stat, items = ECOS_FUNDS
    for item, key_name in items.items():
        rows = _ecos(key, stat, "M", m0, m1, item)
        out["funds_m"][key_name] = [{"month": f"{x['TIME'][:4]}-{x['TIME'][4:]}", "v": float(x["DATA_VALUE"])} for x in rows if x.get("DATA_VALUE") not in (None, "")]
        time.sleep(0.3)
    out["more_q"] = {}
    q0, q1 = f"{today.year - 4}Q1", f"{today.year}Q4"
    for stat, cyc, items in ECOS_QUARTERLY:
        for item, key_name in items.items():
            try:
                rows = _ecos(key, stat, cyc, q0, q1, item)
                out["more_q"][key_name] = [{"q": x["TIME"], "v": float(x["DATA_VALUE"])} for x in rows if x.get("DATA_VALUE") not in (None, "")]
            except Exception as e:   # noqa: BLE001
                print(f"[kr] ECOS {stat}/{item} 실패: {str(e)[:80]}")
            time.sleep(0.3)
    try:
        stat, path, top = ECOS_HH_FIN_TOTAL
        rows = _ecos(key, stat, "Q", q0, q1, path)
        tot = {}
        for x in rows:
            if x.get("ITEM_CODE2") in top and x.get("DATA_VALUE") not in (None, ""):
                tot[x["TIME"]] = tot.get(x["TIME"], 0.0) + float(x["DATA_VALUE"])
        out["more_q"]["hh_fin_total"] = [{"q": t, "v": v} for t, v in sorted(tot.items())]
    except Exception as e:   # noqa: BLE001
        print(f"[kr] ECOS 가계 금융자산 합계 실패: {str(e)[:80]}")
    time.sleep(0.3)
    out["more_m"] = {}
    for stat, cyc, items in ECOS_MONTHLY_MORE:
        for item, key_name in items.items():
            try:
                rows = _ecos(key, stat, cyc, m0, m1, item)
                out["more_m"][key_name] = [{"month": f"{x['TIME'][:4]}-{x['TIME'][4:]}", "v": float(x["DATA_VALUE"])} for x in rows if x.get("DATA_VALUE") not in (None, "")]
            except Exception as e:   # noqa: BLE001
                print(f"[kr] ECOS {stat}/{item} 실패: {str(e)[:80]}")
            time.sleep(0.3)
    # 업종 재료 지표 (기획 11-4, 2026-10-24) — 표 · 항목이 겹치면 한 번만 받는다. 수출물가지수는 원화 · 계약통화 두 줄이 오므로 원화 기준만
    out["industry"] = {}
    for key_name, (stat, item, *_rest) in U.INDICATORS.items():   # DERIVED 는 analyze 에서 두 시계열의 차로 만든다
        if stat == "customs":   # 관세청 품목 수출 — 아래 _customs 가 받는다 (2026-10-31)
            continue
        try:
            rows = _ecos(key, stat, "M", m0, m1, item)
            codes2 = {x.get("ITEM_CODE2") for x in rows}
            if len(codes2) > 1:   # 한 달에 여러 줄(하위 항목)이 오는 표 — 수출물가는 원화 기준, 그 밖은 값이 가장 큰 줄(= 합계)만
                names = {x.get("ITEM_CODE2"): x.get("ITEM_NAME2", "") for x in rows}
                if stat in ("402Y016", "401Y015", "402Y014"):   # 수출입물가는 원화 · 계약통화 두 줄 — 원화 기준만
                    pick = next((c for c, n in names.items() if "원화" in (n or "")), next(iter(names)))
                else:
                    tot = {}
                    for x in rows:
                        if x.get("DATA_VALUE") not in (None, ""):
                            tot[x.get("ITEM_CODE2")] = tot.get(x.get("ITEM_CODE2"), 0.0) + float(x["DATA_VALUE"])
                    pick = max(tot, key=tot.get) if tot else next(iter(names))
                rows = [x for x in rows if x.get("ITEM_CODE2") == pick]
            out["industry"][key_name] = [{"month": f"{x['TIME'][:4]}-{x['TIME'][4:]}", "v": float(x["DATA_VALUE"])} for x in rows if x.get("DATA_VALUE") not in (None, "")]
        except Exception as e:   # noqa: BLE001
            print(f"[kr] ECOS 업종 지표 {key_name} 실패: {str(e)[:80]}")
        time.sleep(0.3)
    for key_name, hs_list in U.CUSTOMS.items():
        got = _customs(hs_list)
        if got:
            out["industry"][key_name] = got
    # K1~K6 업종별 BSI — 표마다 "?/업종" 한 번에 항목 전부 (ITEM_CODE1 = 항목, ITEM_CODE2 = 업종)
    out["bsi"] = {}
    for ind in U.BSI_INDUSTRY:
        got = {}
        for stat in ("512Y007", "512Y008"):
            try:
                for x in _ecos(key, stat, "M", BSI_START, m1, f"?/{ind}", n=5000):
                    if x.get("DATA_VALUE") not in (None, ""):
                        got.setdefault(x["ITEM_CODE1"], []).append({"month": f"{x['TIME'][:4]}-{x['TIME'][4:]}", "v": float(x["DATA_VALUE"])})
            except Exception as e:   # noqa: BLE001
                print(f"[kr] ECOS BSI {ind}/{stat} 실패: {str(e)[:80]}")
            time.sleep(0.3)
        out["bsi"][ind] = {k: sorted(v, key=lambda r: r["month"]) for k, v in got.items()}
    # K10 업종 분기 기업경영분석 · K15 산업별 대출 (분기)
    out["fin_q"], out["loan_q"] = {}, {}
    for ind in U.FIN_INDUSTRY:
        for stat, item, name_, _unit in U.FIN_ITEMS:
            try:
                rows = _ecos(key, stat, "Q", q0, q1, f"{ind}/A/{item}")
                out["fin_q"].setdefault(ind, {})[stat] = [{"q": x["TIME"], "v": float(x["DATA_VALUE"])} for x in rows if x.get("DATA_VALUE") not in (None, "")]
            except Exception as e:   # noqa: BLE001
                print(f"[kr] ECOS 기업경영분석 {ind}/{stat} 실패: {str(e)[:80]}")
            time.sleep(0.3)
    for ind in U.LOAN_INDUSTRY:
        try:
            rows = _ecos(key, "131Y013", "Q", q0, q1, ind)
            out["loan_q"][ind] = [{"q": x["TIME"], "v": float(x["DATA_VALUE"])} for x in rows if x.get("DATA_VALUE") not in (None, "")]
        except Exception as e:   # noqa: BLE001
            print(f"[kr] ECOS 산업별 대출 {ind} 실패: {str(e)[:80]}")
        time.sleep(0.3)
    # K21 FRED 일별 (공공) — 키 없으면 건너뜀
    fk_ = os.environ.get("FRED_API_KEY", "").strip()
    if not fk_:
        try:
            from dotenv import load_dotenv
            load_dotenv(os.path.join(BASE, "..", "..", ".env"))
            fk_ = os.environ.get("FRED_API_KEY", "").strip()
        except ImportError:
            pass
    if fk_:
        for sid, key_name in FRED_DAILY.items():
            try:
                j = requests.get("https://api.stlouisfed.org/fred/series/observations",
                                 params={"series_id": sid, "api_key": fk_, "file_type": "json", "observation_start": (today - datetime.timedelta(days=800)).isoformat()}, timeout=30).json()
                out["more_d"][key_name] = [{"day": o["date"], "v": float(o["value"])} for o in j.get("observations", []) if o["value"] not in (".", "")]
            except Exception as e:   # noqa: BLE001
                print(f"[kr] FRED {sid} 실패: {str(e)[:80]}")
    os.makedirs(DATA, exist_ok=True)
    with open(FLOWS, "w", encoding="utf-8") as f:
        json.dump(out, f)
    fk = out["daily"].get("foreign_kospi") or []
    print(f"[kr] ECOS 일별 {len(fk)}일(마지막 {fk[-1]['day'] if fk else '-'}) · 투자자별 {len(out['investor_m'].get('foreign') or [])}개월 · 증시자금 {len(out['funds_m'].get('credit_loan') or [])}개월 → {FLOWS}")
    return out


def load():
    with open(SNAP, encoding="utf-8") as f:
        snap = json.load(f)
    try:
        with open(FLOWS, encoding="utf-8") as f:
            flows = json.load(f)
    except OSError:
        flows = None
    try:
        with open(HIST, encoding="utf-8") as f:
            hist = json.load(f)
    except OSError:
        hist = None
    return snap, flows, hist


def run():
    snap = run_prices()
    if snap is None:
        return None, None, None
    hist = history()
    flows = None
    try:
        flows = run_flows()
    except Exception as e:   # noqa: BLE001 — 자금 흐름이 실패해도 시세는 살린다
        print(f"[kr] ECOS 실패: {str(e)[:160]}")
        notify.event("수집 실패", f"ECOS 자금 흐름 — {str(e)[:120]}")
    return snap, flows, hist


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--show" in sys.argv:
        snap, flows, hist = load()
    else:
        snap, flows, hist = run()
    if snap:
        rows = sorted(((U.name(s), snap["caps"].get(s) or 0, snap["bars"][s][-1]) for s in snap["bars"] if s in U.BY_SYM), key=lambda r: -r[1])
        for n, cap, b in rows[:12]:
            print(f"   {n:10s} 시총 {cap / 1e12:6.1f}조  {b['day']} 종가 {int(b['close']):>9,}")
        if snap.get("missing"):
            print("   빠진 종목:", snap["missing"])
    if flows:
        fk = flows["daily"]["foreign_kospi"][-5:]
        print("   외국인 순매수(유가증권, 억원):", ", ".join(f"{x['day'][5:]} {x['v']:+,.0f}" for x in fk))
        cl = flows["funds_m"]["credit_loan"][-3:]
        print("   신용융자 잔고(조원):", ", ".join(f"{x['month']} {x['v'] / 1e12:.1f}" for x in cl))
    if hist:
        print(f"   고점 회복 통계 {len(hist['stats'])}종목 (built {hist['built']})")
