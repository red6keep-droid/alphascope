"""ETF 고정 페이지 게시 — 종목 페이지 게시기(stock-radar/publish_pages.publish)를 그대로 쓴다: 바뀐 것만 PUT(해시) · 새 페이지 하루 10개 · 429 백오프 · 영문 주소.

    python experiments/stock-etf/publish_etf.py --market us [--dry]
    python experiments/stock-etf/publish_etf.py --market kr [--dry]

본문 = etf_pages.py 가 만든 output/pages/<키>.html. 해시 · 발행 목록은 시장별 data 폴더(etf_page_hashes.json · etf_pages_live.json) — 각 상태 저장소에 보관.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [HERE, EXP, os.path.join(EXP, "stock-radar")]
import etf_pages as P  # noqa: E402
import etf_universe as E  # noqa: E402
import publish_pages as PP  # noqa: E402


def targets_for(market):
    syms = E.US_SYMS if market == "us" else E.KR_SYMS

    def targets(only=None):
        out = []
        for sym in syms:
            k = E.key(sym)
            if only and k not in only:
                continue
            path = os.path.join(P.OUT, f"{k}.html")
            if os.path.exists(path):
                out.append((k, E.page_title(sym), E.slug(sym).replace("-", " "), E.page_url(sym), path))
        return out
    return targets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", choices=("us", "kr"), required=True)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("only", nargs="*")
    a = ap.parse_args()
    PP.targets = targets_for(a.market)
    PP.HASHES = os.path.join(P.data_dir(a.market), "etf_page_hashes.json")
    PP.PAGES_LIVE = P.live_path(a.market)
    PP._body = lambda path: open(path, encoding="utf-8").read()   # 종목 페이지 전용 링크 바꾸기(미국 증시 리포트 · 엔비디아 글)는 ETF 본문에 없다
    os.makedirs(P.data_dir(a.market), exist_ok=True)
    ok = PP.publish(only=set(a.only) or None, dry=a.dry)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv

    load_dotenv(os.path.join(EXP, "..", ".env"))
    main()
