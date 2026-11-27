"""시장 전망 지도(가칭) — 미국 목업. 기획: 비공개 doc/기획/시장-전망-리포트-기획.md 3 · 5 · 11 · 12절.

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


def md(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.month}.{d.day}"   # 날짜 = 점 · 앞자리 0 없음 (가이드라인 5절)


def gap(v, now, px=17):
    """지금 값과의 차이 — 증감 = 삼각형 + 절댓값 + 증감 색 (가이드라인 5절)."""
    p = (v / now - 1) * 100
    return (f'<span style="color:{dk.UP if p > 0 else dk.DOWN};white-space:nowrap;">'
            f'{dk.tri_span(p > 0, px)}{abs(p):.1f}%</span>')


def dots(rows, now, title):
    """※ 그래프 제목(카드 밖) + 흰 카드 — 회사 목표 = 주인공 주황 점, 지금 값 = 비교 회색 점선 (가이드라인 4 · 7-3 · 9절)."""
    vals = [r["value"] for r in rows] + [now]
    a, b = min(vals) * 0.98, max(vals) * 1.02
    x = lambda v: (v - a) / (b - a) * 100  # noqa: E731
    pts = "".join(f'<span title="{esc(r["firm"])} {r["value"]:,}" style="position:absolute;left:calc({x(r["value"]):.2f}% - 6px);top:{14 + (i % 3) * 10}px;'
                  f'width:12px;height:12px;border-radius:50%;background:{dk.CHART_MAIN};border:2px solid #fff;box-sizing:border-box;"></span>'
                  for i, r in enumerate(rows))
    now_x = x(now)
    anchor = "translateX(-100%)" if now_x > 80 else "translateX(0)" if now_x < 20 else "translateX(-50%)"
    now_line = (f'<span style="position:absolute;left:{now_x:.2f}%;top:6px;height:44px;border-left:2px dashed {dk.CHART_CMP};"></span>'
                f'<span style="position:absolute;left:{now_x:.2f}%;top:52px;transform:{anchor};font-size:12px;line-height:16px;color:{dk.SUB};white-space:nowrap;">지금 {now:,.0f}</span>')
    ends = (f'<span style="position:absolute;left:0;top:52px;font-size:12px;line-height:16px;color:{dk.SUB};">{a:,.0f}</span>'
            f'<span style="position:absolute;right:0;top:52px;font-size:12px;line-height:16px;color:{dk.SUB};">{b:,.0f}</span>')
    axis = '<span style="position:absolute;left:0;right:0;top:50px;border-top:1px solid #ECF0F5;"></span>'
    return (f'<div style="margin:0 {dk.ALIGN_PX}px;">{dk.CHART_TITLE_M}{esc(title)} (포인트)</span></div>'
            f'<div style="margin:0 {dk.CHART_CARD_X}px 8px;padding:{dk.CHART_CARD_PAD}px 12px 0;background:#fff;border:1px solid #E2E8F0;border-radius:8px;">'
            f'<div style="position:relative;height:78px;">{axis}{pts}{now_line}{ends}</div></div>')


def firm_rows(rows, now, show_prev=True):
    """이름 · 값 카드(표 대신, 7-4절) — 왼쪽 회사 │ 보조 줄(발표일 · 바꾼 것), 오른쪽 목표. 지금과의 차이는 보조 줄."""
    out = []
    for r in rows:
        sub = [f"{md(r['published'])} 발표"]
        if show_prev and r.get("prev"):
            sub.append(f"{r['prev']:,} 에서 {'올림' if r['value'] > r['prev'] else '내림'}")
        sub.append(f"지금보다 {gap(r['value'], now, 14)}")
        out.append((esc(r["firm"]), f"{r['value']:,}", " · ".join(sub)))
    return dk.ccard(out, fold_at=5 if len(out) > 5 else None, noun="회사")


def summary(rows, now, label):
    vs = sorted(r["value"] for r in rows)
    mid = vs[len(vs) // 2] if len(vs) % 2 else (vs[len(vs) // 2 - 1] + vs[len(vs) // 2]) / 2
    lo, hi = rows[-1], rows[0]
    return (f'<p style="margin:0 0 14px;padding:0 0 0 {dk.ALIGN_PX}px;font-size:{dk.BODY};line-height:{dk.LH_BODY};color:#333;word-break:keep-all;">'
            f'{label} 목표를 낸 곳은 {dk.violet(f"{len(rows)}곳")}입니다. 가운데 값은 <b>{mid:,.0f}</b>, '
            f'가장 낮은 곳은 {esc(lo["firm"])} {lo["value"]:,}, 가장 높은 곳은 {esc(hi["firm"])} {hi["value"]:,} 입니다. '
            f'지금 값({now:,.0f})에서 가운데 값까지 {gap(mid, now, 19)} 남았습니다.</p>')


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
    kday = f"{d.month}월 {d.day}일"
    stamp = (f'<p data-report-stamp="1" style="display:flex;gap:6px;align-items:flex-start;margin:0 0 14px;padding:10px 12px;background:#F3F4F6;border-radius:8px;'
             f'font-size:13px;line-height:19px;color:#6B7280;word-break:keep-all;"><span>{kday} 종가 기준 · 새 전망이 보도된 날 고칩니다.</span></p>')
    body = stamp + (f'<p data-seo-lead style="{dk.SEO_LEAD}">{kday} 기준으로 투자회사들이 낸 S&P 500 연말 목표를 회사별로 모았습니다. '
                    f'지금 값({now:,.0f})과 견주고, 작년 이맘때 같은 회사들이 본 올해 말 목표도 함께 봅니다.</p>')
    if nxt:
        body += dk.section(f"{this_y + 1}년 말 S&P 500 목표은?".replace("목표은", "목표는"),
                           summary(nxt, now, f"{this_y + 1}년 말") + dots(nxt, now, f"회사별 {this_y + 1}년 말 목표와 지금 값") + firm_rows(nxt, now), line=False)
    if last:
        below = sum(1 for r in last if r["value"] > now)
        body += dk.section(f"작년에 본 {this_y}년 말 목표와 지금은?",
                           f'<p style="margin:0 0 14px;padding:0 0 0 {dk.ALIGN_PX}px;font-size:{dk.BODY};line-height:{dk.LH_BODY};color:#333;word-break:keep-all;">'
                           f'{this_y - 1}년 11 ~ 12월에 {dk.violet(f"{len(last)}곳")}이 {this_y}년 말 목표를 냈습니다. '
                           f'지금 값({now:,.0f})은 그중 {dk.violet(f"{below}곳")}의 목표보다 아래입니다. 연말 종가로 다시 맞춰 봅니다.</p>'
                           + dots(last, now, f"작년에 낸 {this_y}년 말 목표와 지금 값") + firm_rows(last, now, show_prev=False), line=False)
    if cur:
        body += dk.section(f"올해 {this_y}년 말 목표를 바꾼 곳은?", firm_rows(cur, now), line=False)
    body += dk.muted("목표는 각 회사가 발표하고 언론이 보도한 숫자입니다. Newfact 의 전망이 아니며, 리포트 원문은 싣지 않습니다.")
    c = j["counts"]
    chk = "".join(f'<li style="margin:2px 0;">{esc(x["why"])} — {esc(x["title"][:120])}</li>' for x in j["check"])
    st = " · ".join(f'{s["status"]}' for s in j.get("status") or [])
    body += (f'<div style="margin:28px 0;padding:16px;border:1px dashed #CBD5E1;border-radius:8px;font-size:14px;line-height:20px;color:{dk.SUB};">'
             f'<b>관리자 확인용 (발행 화면에 넣지 않음)</b><br>받은 때 {esc(j["made"])} · 구글 뉴스 검색 {len(j.get("status") or [])}번(응답 {esc(st)})<br>'
             f'제목 {c["titles"]}건 → 잡힘 {c["got"]} · 확인 필요 {c["check"]} · 걸러짐 {c["dropped"]}<br>'
             f'작년 줄 = 11-25 시험 때 받은 제목(목업 자료) · AI 0'
             f'<details style="margin-top:8px;"><summary style="cursor:pointer;">확인 필요 {c["check"]}건 — 왜 빠졌나</summary><ul style="margin:6px 0 0 18px;padding:0;">{chk}</ul></details></div>')
    p = os.path.join(OUT, "mock_outlook_us.html")
    body = f'{dk.WRAP_OPEN}{dk.fix_colons(body)}{dk.WRAP_CLOSE}'
    dk.write_mock(body, p, "시장 전망 지도(가칭) 미국")
    print(f"[mock] {p} · 내년 {len(nxt)}곳 · 작년 {len(last)}곳 · 올해 {len(cur)}곳")


if __name__ == "__main__":
    main()
