"""집 IP(VPN)로만 받는 곳을 받아 experiments/home-ip/data/ 에 둔다 — `.github/workflows/home-ip.yml` 이 하루 한 번 14:30 KST.

    HOME_SOURCE_ADDRESS=<ppp0 주소> python experiments/home-ip/fetch_home_ip.py
    python experiments/home-ip/fetch_home_ip.py --skip "유튜브 수집과 겹쳐 건너뜀"   # VPN 을 안 열었을 때 대시보드 기록만

받는 것(home_ip.py 머리말):
  - 미래에셋 TIGER 구성 · 보수: 받은 지 7일 지난 것만(kr_holdings 주 1회 규칙과 같음) — 보통 주 1번 7종목 × 2요청
  - 마이클 버리 substack RSS: 매번 1요청
실패하면 그 파일은 지난 것 그대로 둔다. 결과는 운영 대시보드 `주기 자료는 제때 받았나?` 의 `집 IP 받기 (VPN)` 줄.
AI 0 · Blogger · gh-pages 쓰기 0.
"""

import argparse
import datetime
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, EXP)
sys.path.insert(0, os.path.join(EXP, "stock-etf"))

import feed_log  # noqa: E402
import home_ip  # noqa: E402

FEED = "집 IP 받기 (VPN)"
MAX_AGE = 7


def tiger_syms():
    import etf_universe as E
    import kr_holdings as KH
    out = []
    for sym in E.KR_SYMS:
        try:
            if KH.brand(E.BY_SYM[sym][1]) == "TIGER":
                out.append(sym)
        except ValueError:
            pass
    return out


def fetch_mirae(today):
    import kr_holdings as KH
    p = home_ip.path(home_ip.MIRAE_FILE)
    try:
        with open(p, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        cache = {}
    KH._s = home_ip.session(dict(KH._s.headers))   # 미래에셋 요청만 집 IP 로
    syms = tiger_syms()
    got, fails = 0, []
    for sym in syms:
        old = cache.get(sym) or {}
        if old.get("got") and (today - datetime.date.fromisoformat(old["got"])).days < MAX_AGE:
            continue
        try:
            new = KH._mirae(sym)
            new["got"] = today.isoformat()
            cache[sym] = new
            got += 1
            print(f"[home-ip] 미래에셋 {sym} 구성 {new.get('n') or len(new.get('top') or [])}줄")
        except Exception as e:  # noqa: BLE001
            fails.append(f"{sym.split('.')[0]} {str(e)[:60]}")
            print(f"::warning::[home-ip] 미래에셋 {sym} 실패 (지난 값 유지): {str(e)[:100]}")
    if got:
        os.makedirs(home_ip.DIR, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    have = len([s for s in syms if s in cache])
    return f"미래에셋 {have}/{len(syms)}개(이번 {got})", fails


def fetch_feeds():
    s = home_ip.session({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"})
    ok, fails = 0, []
    for url, name in home_ip.FEEDS.items():
        try:
            r = s.get(url, timeout=30)
            r.raise_for_status()
            if b"<rss" not in r.content[:2000] and b"<feed" not in r.content[:2000]:
                raise ValueError("RSS 아님")
            os.makedirs(home_ip.DIR, exist_ok=True)
            with open(home_ip.path(name), "wb") as f:
                f.write(r.content)
            ok += 1
            print(f"[home-ip] {url} {len(r.content):,}B")
        except Exception as e:  # noqa: BLE001
            fails.append(f"{name} {str(e)[:60]}")
            print(f"::warning::[home-ip] {url} 실패 (지난 파일 유지): {str(e)[:100]}")
        time.sleep(2)
    return f"RSS {ok}/{len(home_ip.FEEDS)}", fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip", default="", help="VPN 을 열지 못했거나 건너뛴 이유 — 대시보드에 실패로만 남긴다")
    a = ap.parse_args()
    if a.skip or not os.environ.get("HOME_SOURCE_ADDRESS", "").strip():
        why = a.skip or "집 IP(VPN) 연결 실패"
        print(f"::warning::[home-ip] {why} — 지난 값 그대로")
        feed_log.feed(FEED, ok=False, error=why, every_days=1, detail="미래에셋 TIGER · 버리 RSS 는 지난 값으로")
        return
    today = datetime.date.today()
    m_label, m_fails = fetch_mirae(today)
    f_label, f_fails = fetch_feeds()
    fails = m_fails + f_fails
    feed_log.feed(FEED, ok=not fails, label=f"{m_label} · {f_label}", data_date=today.isoformat(), got_new=True,
                  error=" / ".join(fails)[:200], every_days=1, detail="14:30 KST 하루 한 번 · 유튜브 수집과 겹치면 기다림")


if __name__ == "__main__":
    main()
