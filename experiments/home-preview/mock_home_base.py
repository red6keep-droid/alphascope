"""홈 기준 줄 목업 — 오늘 실제 자료로.

    python experiments/home-preview/mock_home_base.py     # output/mock_home_base.html

build_theme.py --preview(가짜 자료 홈)를 만든 뒤, 날짜를 정하는 파일만 지금 독자가 받는 실제 파일(jsDelivr gh-pages)로 바꿔 끼운다:
  stocks.json · kr.json · themes.json · hypo.json · issues.json · news.json · cards/report.json · cards/kr-report.json · cards/radar.json
→ 맨 위 `미국 … 아침 · 한국 … 오후 기준` 한 줄과, 그 기준과 다른 카드 날짜만 남는 모습을 오늘 상태 그대로 본다.
받는 시각의 자료라 다시 돌리면 그때 상태가 된다. 받지 못한 파일은 미리보기 가짜 자료 그대로.
"""
import json
import os
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "output", "mock_home_base.html")
CDN = "https://cdn.jsdelivr.net/gh/red6keep-droid/alphascope@gh-pages/"
FILES = ["stocks.json", "kr.json", "themes.json", "hypo.json", "issues.json", "news.json",
         "cards/report.json", "cards/kr-report.json", "cards/radar.json"]
ANCHOR = "  /* 댓글 미리보기"


def real():
    got = {}
    for f in FILES:
        try:
            with urllib.request.urlopen(CDN + f, timeout=20) as r:
                got[f] = json.load(r)
        except Exception as e:  # 못 받으면 가짜 자료 그대로
            print(f"  {f}: 못 받음 ({e!r}) — 미리보기 자료 그대로")
    return got


def main():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, os.path.join(ROOT, "build_theme.py"), "--preview"], cwd=ROOT, env=env,
                   check=True, stdout=subprocess.DEVNULL)
    with open(os.path.join(ROOT, "preview.html"), encoding="utf-8") as f:
        page = f.read()
    if ANCHOR not in page:
        sys.exit("끼울 자리를 못 찾음 — build_theme.py 미리보기 구조 확인")
    data = real()
    js = (
        "  /* 목업: 날짜를 정하는 파일은 지금 jsDelivr 실제 파일 (mock_home_base.py) */\n"
        f"  var PV_REAL = {json.dumps(data, ensure_ascii=False)};\n"
        "  var pvFetch = window.fetch;\n"
        "  window.fetch = function (url) {\n"
        "    var p = String(url).split('?')[0];\n"
        "    for (var k in PV_REAL) if (p.slice(-(k.length + 1)) === '/' + k) { var b = PV_REAL[k]; return Promise.resolve({ ok: true, status: 200, json: function () { return Promise.resolve(b); } }); }\n"
        "    return pvFetch(url);\n"
        "  };\n\n"
    )
    page = page.replace(ANCHOR, js + ANCHOR, 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    days = {k: (data.get(k) or {}).get("day") or (data.get(k) or {}).get("generated") for k in FILES}
    print(f"목업 → {OUT}")
    for k, v in days.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
