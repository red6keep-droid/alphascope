"""시장 지도 — 목업.

    .venv/bin/python experiments/market-map/mock_map.py [--fetch]   → output/mock_market_map_us.html · _kr.html

네모 칸 지도(업종 칸 안에 종목 칸) + 손가락 확대 · 축소 + 화면을 덮는 전체 화면. 그리는 것은 market_map.js(캔버스 2D — 바깥 엔진 파일 없음).
자료 = 종목 목록 파일 <시장>/_lists.json(stock-lists/build_lists.py 가 매일 Cloudflare Pages 에 올리는 것) → 새 수집 · AI · 쓰기 0.
  --fetch 를 주면 Pages 에서 다시 받아 output/lists_<시장>.json 에 둔다. 안 주면 받아 둔 것을 쓴다.
칸 크기 = 시가총액 · 색 = 재료 하나씩(오늘 등락 / 지수 대비 / 거래량) — 하나의 점수로 합치지 않는다(헌법 제1조).
검색 엔진은 캔버스 안 글자를 못 읽는다 → 같은 내용을 업종 목록(글)으로 아래에 싣는다(전부 싣고 5개 펼침 + 나머지 접기).

목업에서만: 한국 목록 파일은 시가총액이 정식 35종목에만 있다 → 나머지는 ref/universe_all.json 의 값(명단 만들 때 값)으로 칸 크기를 잡는다. 정식 때는 목록 파일에 한국 시가총액을 채워야 한다.
"""
import datetime as dt
import html as _h
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
OUT = os.path.join(HERE, "output")
sys.path.insert(0, EXP)
import design_kit as dk  # noqa: E402

PAGES = "https://alpha-scope.pages.dev/"
BENCH = {"us": ("SPY", "S&P 500"), "kr": ("069500", "코스피 200")}   # 지수 = 그 지수를 따르는 상장지수펀드의 등락(목록 파일에 이미 있는 값)
TITLE = {"us": "미국 시장 지도", "kr": "한국 시장 지도"}
SHOW = 5
KEEP = ("t", "n", "s", "p", "r", "v", "h", "c", "u", "lg")


def esc(s):
    return _h.escape(str(s))


def sign(v, unit="%"):
    a = f"{abs(v):.1f}"
    return f"0.0{unit}" if a == "0.0" else f"{'▲' if v > 0 else '▼'}{a}{unit}"


def paint(v, text):
    c = dk.UP if v > 0.05 else dk.DOWN if v < -0.05 else "#111"
    return f'<span style="color:{c};white-space:nowrap;">{esc(text)}</span>'


def load(mkt, fetch):
    p = os.path.join(OUT, f"lists_{mkt}.json")
    if fetch or not os.path.exists(p):
        req = urllib.request.Request(PAGES + f"{mkt}/_lists.json", headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=60).read()
        os.makedirs(OUT, exist_ok=True)
        open(p, "wb").write(raw)
    return json.load(open(p, encoding="utf-8"))


def payload(mkt, j):
    rows = [{k: r[k] for k in KEEP if r.get(k) is not None} for r in j["rows"]]
    filled = 0
    if mkt == "kr":   # 목업에서만 — 빈 시가총액을 명단 값으로
        uni = json.load(open(os.path.join(EXP, "ref", "universe_all.json"), encoding="utf-8"))
        cap = {x["code"]: x.get("cap") for x in uni["kr"]}
        for r in rows:
            if not r.get("c") and cap.get(r["t"]):
                r["c"] = cap[r["t"]]
                filled += 1
    code, name = BENCH[mkt]
    b = next((e for e in j["etf"] if e["t"] == code), None)
    d = dt.date.fromisoformat(j["d"])
    asof = f"{d + dt.timedelta(days=1):%m.%d} 아침" if mkt == "us" else f"{d:%m.%d} 오후"   # 미국 종가 = 한국 다음 날 아침(날짜는 한국 시간 하나로)
    return {"m": mkt, "title": TITLE[mkt], "asof": asof, "bench": {"n": name, "r": b["r"] if b else 0.0}, "rows": rows}, filled


def sectors(p):
    """업종 목록(글) — 지도와 같은 셈: 시가총액 가중 평균 · 지수 대비 · 오른 · 내린 종목 수."""
    by = {}
    for r in p["rows"]:
        if not r.get("c") or r.get("r") is None:
            continue
        g = by.setdefault(r["s"], {"name": r["s"], "cap": 0, "sum": 0, "up": 0, "down": 0, "n": 0})
        g["cap"] += r["c"]; g["sum"] += r["c"] * r["r"]; g["n"] += 1
        g["up"] += r["r"] > 0.05; g["down"] += r["r"] < -0.05
    out = list(by.values())
    for g in out:
        g["avg"] = g["sum"] / g["cap"]
    return sorted(out, key=lambda g: -g["avg"])


def sector_rows(p):
    b = p["bench"]

    def row(g):
        rel = g["avg"] - b["r"]
        return ('<div style="display:flex;flex-direction:column;gap:2px;padding:10px 0;border-top:1px solid #EEF2F6;">'
                f'<span style="display:flex;flex-wrap:wrap;align-items:center;gap:2px 8px;font-size:16px;line-height:24px;color:#111;">'
                f'<b style="font-weight:700;">{esc(g["name"])}</b>{paint(g["avg"], sign(g["avg"]))}</span>'
                f'<span style="font-size:13px;line-height:19px;color:{dk.SUB};word-break:keep-all;">{esc(b["n"])}보다 {paint(rel, sign(rel, "%p"))}'
                f' · 오른 종목 {g["up"]} · 내린 종목 {g["down"]} · 모두 {g["n"]}종목</span></div>')
    gs = sectors(p)
    head = "".join(row(g) for g in gs[:SHOW]).replace("border-top:1px solid #EEF2F6;", "", 1)
    rest = gs[SHOW:]
    if not rest:
        return head
    return head + (f'<details style="margin:0;"><summary style="list-style:none;cursor:pointer;padding:10px 0 2px;border-top:1px solid #EEF2F6;font-size:14px;line-height:20px;font-weight:600;color:#333;">'
                   f'+ {len(rest)}개 업종 더 보기</summary>' + "".join(row(g) for g in rest) + '</details>')


def build(mkt, fetch):
    j = load(mkt, fetch)
    p, filled = payload(mkt, j)
    b = p["bench"]
    js = open(os.path.join(HERE, "market_map.js"), encoding="utf-8").read()
    data = json.dumps(p, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    other = "kr" if mkt == "us" else "us"
    switch = (f'<a href="mock_market_map_{other}.html" style="display:inline-flex;align-items:center;min-height:44px;font-size:14px;line-height:20px;font-weight:600;color:#333;text-decoration:underline;">'
              f'{TITLE[other]} 보기</a>')
    lead = (f'<p style="margin:0 0 10px;padding:0 {dk.ALIGN_PX}px;font-size:16px;line-height:24px;color:#111;word-break:keep-all;">'
            f'{p["asof"]} 기준 {esc(b["n"])} {paint(b["r"], sign(b["r"]))}. 칸이 클수록 시가총액이 큰 종목이고, 색은 고른 기준 하나를 보여 줍니다.</p>')
    mock_note = ('<div style="margin:28px 0 0;padding:16px;border:1px dashed #CBD5E1;border-radius:8px;font-size:14px;line-height:20px;color:' + dk.SUB + ';word-break:keep-all;">'
                 '목업 안내 : 값은 종목 목록 파일의 실제 값입니다. 지수 등락은 그 지수를 따르는 상장지수펀드(ETF)의 등락으로 대신했습니다.'
                 + (f' 한국은 시가총액이 없는 {filled}종목의 칸 크기를 명단을 만들 때의 값으로 잡았습니다.' if filled else '') + '</div>')
    body = (f'<div data-head-title="{TITLE[mkt]}">'
            + dk.section("오늘의 시장 지도", lead + f'<div data-market-map="1"><script type="application/json">{data}</script></div>'
                         + dk.muted("전체 화면에서 두 손가락으로 벌리면 커지고, 업종 이름을 누르면 그 업종만 크게 보입니다.") + f'<div style="padding:0 {dk.ALIGN_PX}px;">{switch}</div>', line=False)
            + dk.section("업종별로 보면", f'<div style="padding:0 {dk.ALIGN_PX}px;">{sector_rows(p)}</div>'
                         + dk.muted("업종 값은 그 업종 종목들의 시가총액 가중 평균입니다."), line=False)
            + mock_note + f'<script>{js}</script></div>')
    path = os.path.join(OUT, f"mock_market_map_{mkt}.html")
    dk.write_mock(body, path, TITLE[mkt])
    return path, len(p["rows"]), filled


if __name__ == "__main__":
    for m in ("us", "kr"):
        print(*build(m, "--fetch" in sys.argv))
