"""시황 배너 모델 비교 화면 (2026-11-17) — Pollinations(목업) · Workers AI FLUX schnell · Lucid Origin, 같은 장면 · 같은 글자 틀.

    python experiments/market-commentary/banner_compare.py   # → output/banner-compare.html

먼저 banner_mock2(Pollinations) · banner-cf artifact(gh run download) · banner_text_mock 이 돌아 있어야 한다.
"""
import json
import os

import banner_mock2 as M

OUT = M.OUT
COLS = [("Pollinations (목업용)", "banner2/{s}.webp", "banner3/{s}-text.webp"),
        ("Workers AI · FLUX schnell", "banner-cf/flux-1-schnell/{s}.webp", "banner3/{s}-flux-1-schnell-text.webp"),
        ("Workers AI · Lucid Origin", "banner-cf/lucid-origin/{s}.webp", "banner3/{s}-lucid-origin-text.webp")]


def cell(rel):
    path = os.path.join(OUT, rel)
    if not os.path.exists(path):
        return '<div class="miss">없음</div>'
    return f'<img src="{rel}" alt=""><p class="kb">{os.path.getsize(path) / 1024:.0f}KB</p>'


def main():
    log = {}
    lp = os.path.join(OUT, "banner-cf", "log.json")
    if os.path.exists(lp):
        for r in json.load(open(lp, encoding="utf-8")):
            log[(r["model"], r["scene"])] = r
    head = "".join(f"<th>{c[0]}</th>" for c in COLS)
    rows = []
    for key, mk, sub, mood, title, _ in M.SAMPLES:
        if os.path.exists(os.path.join(OUT, COLS[0][2].format(s=key))):
            rows.append(f'<tr><td class="lab">{title}<br><small>글자 얹음</small></td>' + "".join(f"<td>{cell(c[2].format(s=key))}</td>" for c in COLS) + "</tr>")
        secs = ["", *(f' · {log[(m, key)]["sec"]}초' if (m, key) in log else "" for m in ("flux-1-schnell", "lucid-origin"))]
        rows.append(f'<tr><td class="lab">{title}<br><small>{sub} · {mood}</small></td>'
                    + "".join(f"<td>{cell(c[1].format(s=key))}<p class='kb'>{secs[i]}</p></td>" for i, c in enumerate(COLS)) + "</tr>")
    html = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>시황 배너 모델 비교</title><style>
body{{margin:0;background:#f5f6f8;color:#111;font-family:"Malgun Gothic",system-ui,sans-serif}}
main{{max-width:1500px;margin:0 auto;padding:24px 16px 60px;overflow-x:auto}}
h1{{font-size:22px;margin:0 0 6px}} .intro{{font-size:15px;line-height:1.7;color:#333;margin:0 0 18px}}
table{{border-collapse:separate;border-spacing:10px;min-width:900px}} th{{font-size:15px;text-align:left}}
td{{vertical-align:top;background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:8px;width:31%}}
td.lab{{width:9%;font-size:14px;font-weight:700;background:none;border:0}} small{{font-weight:400;color:#6b7280}}
img{{width:100%;display:block;border-radius:6px;aspect-ratio:1200/630;object-fit:cover}}
.kb{{font-size:11px;color:#9ca3af;margin:4px 0 0}} .miss{{aspect-ratio:1200/630;background:#f3f4f6;display:flex;align-items:center;justify-content:center;color:#9ca3af}}
</style></head><body><main>
<h1>시황 배너 — 모델 비교</h1>
<p class="intro">같은 장면 설명 · 같은 글자 틀. Pollinations = 앞 목업(워터마크 · 45초 제한), Workers AI 두 모델 = 2026-11-17 banner-cf-test 실행(12장 모두 성공).<br>
FLUX schnell 은 정사각 1024 를 위아래 잘라 1200×630, Lucid Origin 은 1200×630 그대로.</p>
<table><tr><th></th>{head}</tr>{''.join(rows)}</table>
</main></body></html>"""
    p = os.path.join(OUT, "banner-compare.html")
    open(p, "w", encoding="utf-8").write(html)
    print(f"[비교] {p}")


if __name__ == "__main__":
    main()
