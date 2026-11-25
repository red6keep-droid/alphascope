"""시장 전망 지도(가칭) — 미국 목업. 기획: 비공개 doc/기획/시장-전망-리포트-기획.md 3 · 5 · 11 · 12절 (2026-11-25 사용자 "미국 먼저 시작해").

    python experiments/market-outlook/outlook_us.py              # 먼저 output/outlook_us.json
    python experiments/market-outlook/mock_outlook_us.py         # → output/mock_outlook_us.html

- 독자 화면: 내년 말 목표(회사별 점 · 범위) · 올해 말 목표 · 작년 이맘때 본 올해 말 목표와 지금 값.
- 아래 회색 상자: 거르기 결과(관리자 확인용 — 발행 화면에는 넣지 않는다).
- 작년 줄은 시험 때 받은 제목(output/rss_us_lastyear.json)을 같은 거르기에 넣은 것 — 목업 자료이고 기록이 아니다.
- 매수 · 매도 말 없음. 회사의 전망은 늘 회사 이름을 주어로. 오름 빨강 · 내림 파랑(가이드라인).
"""
import datetime as dt
import html as _h
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
sys.path.insert(0, os.path.join(HERE, ".."))
import design_kit as dk  # noqa: E402
import outlook_us as OU  # noqa: E402

SHOW = 5


def esc(s):
    return _h.escape(str(s))


def latest_by_firm(items, horizon):
    """회사마다 그 기한의 가장 최근 목표 + 그 앞 목표(바꿨으면)."""
    by = {}
    for it in sorted((i for i in items if i["horizon"] == horizon and i.get("value")), key=lambda x: x["published"]):
        by.setdefault(it["firm"], []).append(it)
    rows = []
    for firm, hist in by.items():
        cur = hist[-1]
        prev = next((h for h in reversed(hist[:-1]) if h["value"] != cur["value"]), None)
        rows.append({"firm": firm, "value": cur["value"], "published": cur["published"], "prev": prev["value"] if prev else None,
                     "sources": sum(len(h["sources"]) for h in hist), "links": cur["sources"]})
    return sorted(rows, key=lambda r: -r["value"])


def gap(v, now):
    p = (v / now - 1) * 100
    c = dk.UP if p > 0 else dk.DOWN
    tri = "▲" if p > 0 else "▼"
    return f'<span style="color:{c};white-space:nowrap;">{tri} {abs(p):.1f}%</span>'


def dots(rows, now, lo=None, hi=None):
    """회사별 점 + 지금 값 세로선. 축 = 값들과 지금 값을 다 담는 범위."""
    vals = [r["value"] for r in rows] + [now]
    a, b = (lo or min(vals)) * 0.98, (hi or max(vals)) * 1.02
    x = lambda v: (v - a) / (b - a) * 100  # noqa: E731
    pts = "".join(f'<span title="{esc(r["firm"])} {r["value"]:,}" style="position:absolute;left:calc({x(r["value"]):.2f}% - 6px);top:{10 + (i % 3) * 9}px;'
                  f'width:12px;height:12px;border-radius:50%;background:#334155;border:2px solid #fff;"></span>' for i, r in enumerate(rows))
    now_line = (f'<span style="position:absolute;left:{x(now):.2f}%;top:2px;bottom:18px;border-left:2px dashed {dk.DOWN};"></span>'
                f'<span style="position:absolute;left:{x(now):.2f}%;bottom:0;transform:translateX(-50%);font-size:12px;color:{dk.DOWN};white-space:nowrap;">지금 {now:,.0f}</span>')
    ends = (f'<span style="position:absolute;left:0;bottom:0;font-size:12px;color:{dk.SUB};">{a:,.0f}</span>'
            f'<span style="position:absolute;right:0;bottom:0;font-size:12px;color:{dk.SUB};">{b:,.0f}</span>')
    return (f'<div style="position:relative;height:64px;margin:6px {dk.ALIGN_PX}px 14px;border-top:1px solid #E2E8F0;">'
            f'{pts}{now_line}{ends}</div>')


def table(rows, now, show_prev=True):
    out = []
    for i, r in enumerate(rows):
        prev = (f'<div style="font-size:13px;line-height:19px;color:{dk.SUB};">{r["prev"]:,} → {r["value"]:,}'
                f' ({"올림" if r["value"] > r["prev"] else "내림"})</div>') if show_prev and r.get("prev") else ""
        d = dt.date.fromisoformat(r["published"])
        out.append(f'<div style="display:flex;justify-content:space-between;gap:12px;padding:10px 12px;{"border-top:1px solid #E2E8F0;" if i else ""}">'
                   f'<div style="min-width:0;"><div style="font-weight:600;">{esc(r["firm"])}</div>{prev}'
                   f'<div style="font-size:13px;line-height:19px;color:{dk.SUB};">{d:%m.%d} 발표 · 보도 {r["sources"]}건</div></div>'
                   f'<div style="text-align:right;white-space:nowrap;"><div style="font-weight:700;">{r["value"]:,}</div>'
                   f'<div style="font-size:13px;line-height:19px;">지금보다 {gap(r["value"], now)}</div></div></div>')
    head, rest = out[:SHOW], out[SHOW:]
    more = (f'<details><summary style="padding:10px 12px;border-top:1px solid #E2E8F0;color:{dk.SUB};cursor:pointer;">{len(rest)}곳 더 보기</summary>'
            + "".join(rest) + "</details>") if rest else ""
    return f'<div style="margin:0 0 6px;background:#fff;border:1px solid #E2E8F0;border-radius:8px;font-size:15px;line-height:22px;">{"".join(head)}{more}</div>'


def summary(rows, now, label):
    vs = sorted(r["value"] for r in rows)
    mid = vs[len(vs) // 2] if len(vs) % 2 else (vs[len(vs) // 2 - 1] + vs[len(vs) // 2]) / 2
    lo, hi = rows[-1], rows[0]
    return (f'<p style="margin:0 0 6px;padding:0 {dk.ALIGN_PX}px;font-size:16px;line-height:26px;word-break:keep-all;">'
            f'{label} — 회사 {len(rows)}곳 · 가운데 <b>{mid:,.0f}</b> · 가장 낮음 {lo["value"]:,}({esc(lo["firm"])}) · '
            f'가장 높음 {hi["value"]:,}({esc(hi["firm"])}). 지금 {now:,.0f} 에서 가운데까지 {gap(mid, now)}</p>')


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    j = json.load(open(OU.RESULT, encoding="utf-8"))
    now, day = j["spx"]["close"], j["spx"]["day"]
    this_y = int(day[:4])
    nxt = latest_by_firm(j["items"], f"{this_y + 1}-12")
    cur = latest_by_firm(j["items"], f"{this_y}-12")
    ly = json.load(open(os.path.join(OUT, "rss_us_lastyear.json"), encoding="utf-8"))
    ly_items, _, _ = OU.sift(ly["rows"])
    last = latest_by_firm([i for i in ly_items if i["published"] < f"{this_y}-01-15"], f"{this_y}-12")   # 작년 이맘때(연초 전까지) 낸 것만
    d = dt.date.fromisoformat(day)

    body = (f'<p data-seo-lead style="{dk.SEO_LEAD}">투자회사들이 낸 S&P 500 연말 목표를 회사별로 모았습니다. '
            f'{d:%m.%d} 종가 {now:,.0f} 와 견줘 보고, 작년 이맘때 같은 회사들이 본 올해 말 목표와 지금 값도 함께 봅니다.</p>')
    if nxt:
        body += dk.section(f"{this_y + 1}년 말 S&P 500 목표", summary(nxt, now, f"{this_y + 1}년 말") + dots(nxt, now) + table(nxt, now), line=False)
    if last:
        body += dk.section(f"작년 이맘때 본 {this_y}년 말 목표와 지금",
                           f'<p style="margin:0 0 6px;padding:0 {dk.ALIGN_PX}px;font-size:16px;line-height:26px;word-break:keep-all;">'
                           f'{this_y - 1}년 11 ~ 12월에 {len(last)}곳이 낸 목표입니다. 지금 {now:,.0f} 는 '
                           f'{sum(1 for r in last if r["value"] > now)}곳의 목표보다 아래, {sum(1 for r in last if r["value"] <= now)}곳의 목표보다 위입니다. '
                           f'연말(12.31 종가)에 다시 맞춰 봅니다.</p>'
                           + dots(last, now) + table(last, now, show_prev=False), line=False)
    if cur:
        body += dk.section(f"올해 들어 바꾼 {this_y}년 말 목표", table(cur, now), line=False)
    body += dk.muted("목표는 각 회사가 발표하고 언론이 보도한 숫자입니다. Newfact 의 전망이 아니며, 사거나 팔라는 뜻이 아닙니다. 리포트 원문은 싣지 않습니다.")

    c = j["counts"]
    chk = "".join(f'<li style="margin:2px 0;">{esc(x["why"])} — {esc(x["title"][:120])}</li>' for x in j["check"])
    st = " · ".join(f'{s["status"]}' for s in j.get("status") or [])
    body += (f'<div style="margin:28px 0;padding:16px;border:1px dashed #CBD5E1;border-radius:8px;font-size:14px;line-height:20px;color:{dk.SUB};">'
             f'<b>관리자 확인용 (발행 화면에 넣지 않음)</b><br>받은 때 {esc(j["made"])} · 구글 뉴스 검색 {len(j.get("status") or [])}번(응답 {esc(st)})<br>'
             f'제목 {c["titles"]}건 → 잡힘 {c["got"]} · 확인 필요 {c["check"]} · 걸러짐 {c["dropped"]}<br>'
             f'작년 줄 = 11-25 시험 때 받은 제목(목업 자료) · AI 0'
             f'<details style="margin-top:8px;"><summary style="cursor:pointer;">확인 필요 {c["check"]}건 — 왜 빠졌나</summary><ul style="margin:6px 0 0 18px;padding:0;">{chk}</ul></details></div>')
    p = os.path.join(OUT, "mock_outlook_us.html")
    dk.write_mock(body, p, "시장 전망 지도(가칭) — 미국")
    print(f"[mock] {p} · 내년 {len(nxt)}곳 · 작년 {len(last)}곳 · 올해 {len(cur)}곳")


if __name__ == "__main__":
    main()
