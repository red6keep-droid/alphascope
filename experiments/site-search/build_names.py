"""검색어 미리보기 목록 — 정식 · 간단 종목 전부의 이름 · 티커(코드) · 페이지 주소 (2026-11-16 사용자: "삼" 한 글자만 써도 검색어가 미리 뜨게, 종목 검색 입력창 전부).

검색 창(search.js)은 처음 열 때 이 파일 하나를 더 읽어, 글자를 칠 때마다 이름 · 티커 · 코드 · 영문 이름으로 찾아 아래에 목록을 띄운다.
값(주가 · 실적)은 넣지 않는다 — 즉답 색인(search/us.json · kr.json)은 정식 종목만 그대로. 간단 종목을 고르면 그 종목 페이지로 간다.
주소: 정식 = 종목 분석 페이지, 간단 = 전용 페이지(shells.json, 발행된 것), 아직 발행 전 = /p/stock.html?s=코드(일반 페이지 — 발행되면 전용 페이지로 넘긴다).
순서 재료 c = 시가총액(한국 = 간단 실행 cap_rank.json, 정식 · 간단 같은 셈). 미국 간단은 시총이 없어 0.
AI 0 · 독자 1명당 요청 1번(Cloudflare Pages 정적 파일, 처음 검색 창을 열 때만).

    python experiments/site-search/build_names.py --cache /tmp/qcache --shells /tmp/qd/shells.json --out /tmp/cfp/names.json
"""
import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path[:0] = [EXP, os.path.join(EXP, "stock-radar"), os.path.join(EXP, "kr-stocks")]
import universe as U  # noqa: E402
import universe_kr as K  # noqa: E402

BLOG = "https://www.newfact.app"
try:
    from build_search_index import EXTRA_ALIAS as ALIAS   # noqa: E402
except Exception:  # noqa: BLE001 — 줄임말 없이도 목록은 만든다
    ALIAS = {}


def _load(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def build(ref, shells, caps, logos=None):
    """logos = ref/ticker_logos.json 의 logos — 미리보기 줄 앞 작은 로고(2026-11-19 사용자). 없는 종목은 화면이 원 배지로."""
    logos = logos or {}
    out = []
    for m, rows in (("us", ref.get("us") or {}), ("kr", ref.get("kr") or {})):
        for sym, e in rows.items():
            file = sym.split(".")[0]
            full = bool(e.get("full"))
            if full and sym in (U.BY_SYM if m == "us" else K.BY_SYM):
                url = (U if m == "us" else K).page_url(sym)
            else:
                url = shells.get(file) or f"{BLOG}/p/stock.html?s={file}"
            row = {"n": e.get("ko") or sym, "t": file, "m": m, "u": url}
            if e.get("en"):
                row["e"] = e["en"]
            c = (caps.get(sym) or {}).get("cap")
            if c:
                row["c"] = round(c / 1e8)   # 억 원 — 순서만 쓴다
            if full:
                row["f"] = 1
            if ALIAS.get(sym):
                row["a"] = ALIAS[sym]   # 줄임말(삼전 · 하닉) — 즉답 색인과 같은 표
            lg = (logos.get(sym.upper()) or {}).get("file")
            if lg:
                row["lg"] = lg
            out.append(row)
    for sym, *_ in U.CANDIDATES + K.CANDIDATES:   # 명단(quick_ref) 밖 정식 종목도 — 빠짐 없이
        m = "kr" if sym.endswith((".KS", ".KQ")) else "us"
        if not any(r["t"] == sym.split(".")[0] and r["m"] == m for r in out):
            row = {"n": (U if m == "us" else K).name(sym), "t": sym.split(".")[0], "m": m, "u": (U if m == "us" else K).page_url(sym), "f": 1}
            lg = (logos.get(sym.upper()) or {}).get("file")
            if lg:
                row["lg"] = lg
            out.append(row)
    return out


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="", help="quick-state 폴더 (kr/cap_rank.json)")
    ap.add_argument("--shells", default="", help="전용 페이지 주소표 {파일 이름: 주소}")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ref = _load(os.path.join(EXP, "ref", "quick_ref.json"), {})
    shells = _load(a.shells, {}) if a.shells else {}
    caps = (_load(os.path.join(a.cache, "kr", "cap_rank.json"), {}) or {}).get("caps") or {} if a.cache else {}
    logos = (_load(os.path.join(EXP, "ref", "ticker_logos.json"), {}) or {}).get("logos") or {}
    rows = build(ref, shells, caps, logos)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump({"built": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"), "stocks": rows},
              open(a.out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"[names] 종목 {len(rows)}개(미국 {sum(r['m'] == 'us' for r in rows)} · 한국 {sum(r['m'] == 'kr' for r in rows)}) · "
          f"전용 페이지 {sum(1 for r in rows if '/p/stock.html?s=' not in r['u'])} · 로고 {sum(1 for r in rows if r.get('lg'))} · {os.path.getsize(a.out) / 1024:.0f}KB → {a.out}")


if __name__ == "__main__":
    main()
