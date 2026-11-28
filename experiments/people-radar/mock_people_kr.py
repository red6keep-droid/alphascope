"""인물 발언 한국 연관 종목 시안 — 연결 자산(미국 기호)에 한국 종목 페이지의 `미국 연관 종목` 짝(universe_kr.PAIRS)을 거꾸로 붙인다.
엔비디아 발언 → 삼성전자 · SK하이닉스 · SK스퀘어. 새 수집 · AI 0. 상태 저장소의 마지막 레이더(radar.json)를 실제 렌더러로 그린다.

    git fetch state radar-state
    .venv/bin/python experiments/people-radar/mock_people_kr.py   → output/mock_people_kr.html (목업 서버 발행 예정 칸)

지금 = 미국 기호만
시안 A = 연결 자산 줄 아래 따로 `한국 연관 종목 : 삼성전자 · SK하이닉스 · SK스퀘어` (목록 줄 · 발언 줄)
시안 B = 같은 줄 끝에 `· 한국 : 삼성전자 · SK하이닉스`
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.dirname(HERE), os.path.join(os.path.dirname(HERE), "kr-stocks")]
import design_kit as dk  # noqa: E402
import render_html as R  # noqa: E402
import universe_kr as U  # noqa: E402
from mock_person_cards import _show  # noqa: E402

KR_MAX = 3
SHOW = ("huang", "musk", "cramer")   # 엔비디아 · 테슬라 · 마이크론이 연결 자산에 나오는 인물
_ORDER = {s: i for i, s in enumerate(U.BY_SYM)}   # 한국 종목 목록 순서(시가총액 순)
REV = {}
for k, (us, _why) in U.PAIRS.items():
    for u in us:
        REV.setdefault(u, []).append(k)


def kr_of(assets):
    out = []
    for a in assets:
        for k in sorted(REV.get(a, []), key=lambda k: _ORDER.get(k, 999)):
            if k not in out:
                out.append(k)
    return out[:KR_MAX]


def kr_html(syms):
    return " · ".join(dk.stock_link(k, dk.esc(U.name(k))) for k in syms)


_path = R._path_line


def variant(kind):
    def path_line(s, card):
        out = _path(s, card)
        ks = kr_of((s.get("path") or {}).get("assets") or [])
        if not out or not ks:
            return out
        if kind == "A":
            return out + [R._sub(dk.keep_tone(f"한국 연관 종목 : {kr_html(ks)}"), "#111")]
        return [out[0].replace("</span>", f" · 한국 : {kr_html(ks)}</span>", 1)] + out[1:]
    R._path_line = _path if kind == "now" else path_line


def list_rows(html, r, kind):
    """목록 줄 `연결 자산 : NVDA · …` 아래(A) · 끝(B)에 한국 종목."""
    if kind == "now":
        return html
    by = {p["speaker"]: kr_of(((p["signals"][0].get("path") or {}).get("assets")) or []) for p in r["people"]}

    def rep(m):
        ks = by.get(m.group(1))
        if not ks:
            return m.group(0)
        seg = m.group(0)
        tail = re.search(r'(연결 자산 : [^<]*)</span>', seg)
        if not tail:
            return seg
        if kind == "A":
            add = (f'</span><span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.SUB};margin-top:2px;">'
                   f'한국 연관 종목 : {kr_html(ks)}</span>')
            return seg.replace(tail.group(0), tail.group(1) + add, 1)
        return seg.replace(tail.group(0), f"{tail.group(1)} · 한국 : {kr_html(ks)}</span>", 1)
    return re.sub(r'data-person="([\w-]+)".*?</a>', rep, html, flags=re.S)


def tag(t, sub):
    return (f'<div style="margin:28px 0 8px;padding:8px 12px;background:#FEF3C7;border-radius:8px;font-size:15px;line-height:22px;color:#92400E;">'
            f'<b>{dk.esc(t)}</b> · {dk.esc(sub)}</div>')


def main():
    r = json.loads(_show("radar.json"))
    cards = (json.loads(_show("narrative.json") or "null") or {}).get("cards")
    r["people"] = [p for sp in SHOW for p in r["people"] if p["speaker"] == sp]
    body = []
    for kind, t, sub in (("now", "지금", "연결 자산이 미국 기호뿐"),
                         ("A", "시안 A (추천)", "연결 자산 줄 아래 따로 `한국 연관 종목` — 한국 종목 페이지 `미국 연관 종목` 짝을 거꾸로, 시가총액 순 셋까지"),
                         ("B", "시안 B", "같은 줄 끝에 `· 한국 : …`")):
        variant(kind)
        body += [tag(t, sub), list_rows(R.sec_people_list(r, cards), r, kind), R.sec_people(r, cards).replace(" hidden", "")]
    variant("now")
    out = os.path.join(HERE, "output", "mock_people_kr.html")
    dk.write_mock(dk.fix_colons(dk.WRAP_OPEN + "".join(body) + dk.WRAP_CLOSE), out, "주요 인물 발언 — 한국 연관 종목 시안")
    print(out)


if __name__ == "__main__":
    main()
