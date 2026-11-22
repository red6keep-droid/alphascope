"""종목 페이지 새 카드 넷 미리보기 — 정식 렌더러(render_pages) + 정식 수집 파일(data/peer_fin.json) 그대로 (2026-11-22 정식으로 옮김 · peer_cards.py).

    .venv/bin/python experiments/stock-radar/mock_earn_mom.py            # 받아 둔 peer_fin.json 으로 그리기만
    .venv/bin/python experiments/stock-radar/mock_earn_mom.py --fetch    # peer_cards.collect 한 번(상한 없이 전부) 뒤 그리기
    .venv/bin/python experiments/stock-radar/mock_earn_mom.py NVDA AAPL  # 종목 고르기 (기본 SPCX · NVDA)
    → output/mock_earnmom_<티커>.html

카드: `같은 업종 안 주가 순위는?`(오늘 탭 가격 카드 아래) · `발표 때 예상을 넘었나?` · `재무 건전성은?` · `이익에 비해 주가 수준은?`(실적 탭) + 돈 카드 현금흐름 세 줄.
설계 · 규칙은 peer_cards.py 머리말. 목업 때(2026-11-20 ~ 22)의 따로 받던 캐시(mock_earn_mom.json · mock_fin.json · mock_balance.json)는 더 쓰지 않는다.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_pages as RP  # noqa: E402
import peer_cards as PC  # noqa: E402

OUT = os.path.join(HERE, "output")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    syms = [a for a in sys.argv[1:] if not a.startswith("--")] or ["SPCX", "NVDA"]
    import analyze
    import analyze_tabs
    import collect
    import collect_extra
    import collect_news
    import industry_us
    snap, extra, news = collect.load(), collect_extra.load() or {}, collect_news.load()
    if "--fetch" in sys.argv:
        PC.FUND_MAX, PC.FUND_SECONDS = 10 ** 6, 10 ** 6
        PC.collect(snap)
    PC.DATA, PC.REV = PC.load(), (extra.get("revenue") or {}).get("series") or {}
    a = analyze.run(snap)
    fred = industry_us.load()
    a["stocks"] = [s for s in a["stocks"] if s["sym"] in syms]
    for s in a["stocks"]:
        analyze_tabs.build(s, snap, extra)
        s["industry_us"] = industry_us.build(s["sym"], fred)
    tmp = os.path.join(OUT, "_earnmom_tmp")
    RP.write_all(a, tmp, None, news)
    for s in a["stocks"]:
        src = os.path.join(tmp, f"mock_{s['sym']}.html")
        dst = os.path.join(OUT, f"mock_earnmom_{s['sym']}.html")
        html = open(src, encoding="utf-8").read().replace("— 목업</title>", "— 새 카드 목업</title>")
        open(dst, "w", encoding="utf-8").write(html)
        print("→", dst)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
