"""목업 보기 서버 — 태블릿·휴대폰에서 즐겨찾기 하나로 모든 목업을 연다 (2026-10-31 사용자).

    python experiments/mock_server.py          # 포트 8800 고정
    python experiments/mock_server.py 8801     # 포트 바꾸기

- `/` 인덱스는 열 때마다 experiments/*/output/*.html 을 새로 읽는다 — 목업이 늘거나 바뀌어도 새로고침만 하면 된다.
- 주소가 바뀌지 않게 포트를 고정하고, IP 대신 맥 이름(.local) 주소도 함께 찍는다.
- 같은 와이파이에 열리므로 output 폴더 밖(.env 등)은 내주지 않는다.
- 즐겨찾기(☆ 누르기)는 맨 위에 (2026-11-01 사용자). 기록은 맥의 experiments/.mock_prefs.json 하나 — 태블릿 · 맥이 같은 목록을 본다.
- 2026-11-07 사용자: 이름으로 찾기 · 자주 연 목업 삭제, 종목 목업은 `한국 종목` · `미국 종목` 대신 종목 이름(삼성전자 · 애플)을 보인다.
"""
import html
import re
import json
import threading
import os
import socket
import subprocess
import sys
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote, urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8800

# 폴더 이름 → 인덱스에 보일 이름. 없는 폴더는 폴더 이름 그대로.
LABELS = {
    "kr-stocks": "한국 종목",
    "kr-market-report": "한국 증시 리포트",
    "stock-radar": "미국 종목",
    "nvda-report": "엔비디아 리포트",
    "daily-report": "데일리 리포트",
    "trump-trend": "트럼프 트렌드",
    "people-radar": "주요 인물 발언",
    "theme-monitor": "테마",
    "media-daily": "미디어 데일리",
    "competitiveness": "국가 경쟁력",
    "home-split": "홈 나누기",   # 미국 화면 · 한국 화면 (2026-11-10 사용자, H35)
    "issue_store": "증시 전망",   # 사건 가설 질문 페이지 · 목록 · 홈 카드 목업 (2026-11-06)
}
RECENT_N = 12
STOCK_DIRS = ("kr-stocks", "stock-radar")   # 폴더 이름 대신 종목 이름을 보이는 폴더 (2026-11-07 사용자)
PREFS = os.path.join(BASE, ".mock_prefs.json")   # {"star": ["폴더/파일"]} — output 밖이라 서버가 내주지 않는다
_lock = threading.Lock()


def load_prefs():
    try:
        with open(PREFS, encoding="utf-8") as fh:
            p = json.load(fh)
    except (OSError, ValueError):
        p = {}
    return {"star": p.get("star", [])}


def save_prefs(p):
    with open(PREFS + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(p, fh, ensure_ascii=False)
    os.replace(PREFS + ".tmp", PREFS)


_themed = {}   # 경로 → (수정 시각, 테마 있음, 종목 이름)
_TITLE = re.compile(r"<title>([^<]*?) 주가", re.I)


def themed(path, mtime):
    """블로그 테마(스타일)를 입힌 미리보기인가. 게시용 본문(X.html · *_body.html)은 스타일이 없어
    날것으로 보이므로 목록에서 뺀다 — 주소로는 그대로 열린다. 이름 규칙이 리포트마다 달라 내용으로 가른다."""
    hit = _themed.get(path)
    if not hit or hit[0] != mtime:
        with open(path, encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
        s = raw.lower()
        m = _TITLE.search(raw)   # `애플 AAPL 주가 …` → 애플 · `삼성전자 주가 …` → 삼성전자
        nm = re.sub(r"\s+[A-Z][A-Z0-9.\-]*$", "", m.group(1).strip()) if m else ""
        hit = _themed[path] = (mtime, "<style" in s or 'rel="stylesheet"' in s, html.unescape(nm))
    return hit[1]


def stock_name(d, f):
    """종목 목업이면 제목의 종목 이름, 아니면 빈 문자열."""
    if d not in STOCK_DIRS:
        return ""
    hit = _themed.get(os.path.join(BASE, d, "output", f))
    return hit[2] if hit else ""


def mockups():
    """[(폴더, 파일 이름, 수정 시각)] — 최근 수정 순."""
    out = []
    for d in sorted(os.listdir(BASE)):
        od = os.path.join(BASE, d, "output")
        if not os.path.isdir(od):
            continue
        for f in os.listdir(od):
            p = os.path.join(od, f)
            if d in STOCK_DIRS and not f.startswith("mock_"):   # 게시용 본문(AAPL.html)은 목업이 아니다 — mock_AAPL 과 같은 내용, 주소로는 열린다 (2026-11-07 사용자)
                continue
            if f.endswith(".html") and themed(p, t := os.path.getmtime(p)):
                out.append((d, f, t))
    return sorted(out, key=lambda x: -x[2])


def row(d, f, t, show_dir=False, stars=()):
    href = f"/{quote(d)}/output/{quote(f)}"
    when = datetime.fromtimestamp(t).strftime("%m-%d %H:%M")
    nm = stock_name(d, f)
    label = nm or (LABELS.get(d, d) if show_dir else "")
    sub = f"{label} · {when}" if label else when
    name = html.escape(f[:-5])
    key = html.escape(f"{d}/{f}")
    on = f"{d}/{f}" in stars
    return (f'<div class="row"><a class="go" href="{href}">'
            f'<span class="name">{name}</span><span class="sub">{html.escape(sub)}</span></a>'
            f'<button class="star{" on" if on else ""}" data-k="{key}" aria-label="즐겨찾기">{"★" if on else "☆"}</button></div>')


def index_page():
    items = mockups()
    with _lock:
        prefs = load_prefs()
    stars = prefs["star"]
    by_key = {f"{d}/{f}": (d, f, t) for d, f, t in items}
    groups = {}
    for d, f, t in items:
        groups.setdefault(d, []).append((d, f, t))
    parts = []
    fav = [by_key[k] for k in stars if k in by_key]   # 누른 순서대로
    if fav:
        parts += ['<section><h2>★ 즐겨찾기</h2>', *(row(*x, show_dir=True, stars=stars) for x in fav), "</section>"]
    parts += ['<section><h2>최근 바뀐 목업</h2>', *(row(*x, show_dir=True, stars=stars) for x in items[:RECENT_N]), "</section>"]
    for d in sorted(groups, key=lambda k: -groups[k][0][2]):   # 최근에 손댄 폴더가 위
        parts.append(f'<details><summary>{html.escape(LABELS.get(d, d))} <span class="n">{len(groups[d])}</span></summary>')
        parts += [row(*x, stars=stars) for x in groups[d]]
        parts.append("</details>")
    now = datetime.now().strftime("%m-%d %H:%M:%S")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>목업 목록</title>
<style>
body{{margin:0;padding:16px;font:16px/1.4 -apple-system,"Apple SD Gothic Neo",sans-serif;background:#f6f7f9;color:#1d2127}}
h1{{font-size:20px;margin:0 0 4px}} .meta{{color:#8a919c;font-size:13px;margin-bottom:16px}}
h2{{font-size:15px;color:#5b6370;margin:0 0 8px}} section{{margin-bottom:20px}}
details{{background:#fff;border:1px solid #e3e6eb;border-radius:10px;margin-bottom:10px}}
summary{{padding:14px;font-weight:600;cursor:pointer}} .n{{color:#8a919c;font-weight:400;font-size:14px}}
details .row{{border:0;border-top:1px solid #eef0f3;border-radius:0;margin:0}}
.row{{display:flex;align-items:stretch;min-height:48px;background:#fff;border:1px solid #e3e6eb;border-radius:10px;margin-bottom:8px}}
.go{{flex:1 1 auto;min-width:0;display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 4px 10px 14px;color:inherit;text-decoration:none}}
.go:active{{background:#eef2f8}} .name{{word-break:break-all}} .sub{{color:#8a919c;font-size:13px;white-space:nowrap}}
.star{{flex:0 0 48px;border:0;background:none;font-size:22px;color:#c3c8d0;cursor:pointer;padding:0}} .star.on{{color:#f5a623}}
</style></head><body>
<h1>목업 목록</h1><div class="meta">{len(items)}개 · 불러온 시각 {now} · 새로고침하면 최신 목록</div>
{''.join(parts)}
<script>
const ds = [...document.querySelectorAll('details')];
// ☆ 누르면 즐겨찾기 넣기 · 빼기 → 목록을 다시 받아 맨 위 즐겨찾기에 반영
document.querySelectorAll('.star').forEach(b => b.addEventListener('click', async () => {{
  await fetch('/star?k=' + encodeURIComponent(b.dataset.k), {{method: 'POST'}});
  try {{ sessionStorage.setItem('mockIndex', JSON.stringify({{
    open: ds.filter(d => d.open).map(d => d.querySelector('summary').textContent), y: scrollY }})); }} catch (e) {{}}
  location.reload();
}}));
// 목업에서 '목록으로' 눌러 돌아오면 펼친 접기 · 스크롤을 그대로 (같은 창 전환)
try {{
  const s = JSON.parse(sessionStorage.getItem('mockIndex') || 'null');
  if (s) {{ ds.forEach((d, i) => d.open = s.open.includes(d.querySelector('summary').textContent));
           scrollTo(0, s.y); }}
}} catch (e) {{}}
addEventListener('pagehide', () => {{
  try {{ sessionStorage.setItem('mockIndex', JSON.stringify({{
    open: ds.filter(d => d.open).map(d => d.querySelector('summary').textContent), y: scrollY }})); }} catch (e) {{}}
}});
</script></body></html>"""

# 목업 맨 아래에 끼워 넣는 '목록으로' 버튼 — 목업 파일은 건드리지 않고 보낼 때만 붙인다.
BACK_BAR = ('<div style="padding:24px 16px 40px;text-align:center;background:#f6f7f9;border-top:1px solid #e3e6eb">'
            '<a href="/" style="display:inline-block;min-width:200px;padding:14px 24px;border-radius:10px;background:#1d2127;'
            'color:#fff;font:600 16px/1.2 -apple-system,\'Apple SD Gothic Neo\',sans-serif;text-decoration:none">← 목업 목록으로</a></div>')


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=BASE, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")   # 목업을 고친 뒤 새로고침하면 바로 보이게
        super().end_headers()

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/star":
            self.send_error(404)
            return
        k = unquote(dict(x.split("=", 1) for x in u.query.split("&") if "=" in x).get("k", ""))
        with _lock:
            p = load_prefs()
            p["star"] = [x for x in p["star"] if x != k] if k in p["star"] else p["star"] + [k]
            save_prefs(p)
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            body = index_page().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        seg = path.strip("/").split("/")
        if len(seg) < 3 or seg[1] != "output" or ".." in seg:   # output 폴더 안만
            self.send_error(404)
            return
        fp = os.path.join(BASE, *seg)
        if len(seg) == 3 and fp.endswith(".html") and os.path.isfile(fp):
            with open(fp, encoding="utf-8", errors="replace") as fh:
                page = fh.read()
            i = page.lower().rfind("</body>")
            page = page[:i] + BACK_BAR + page[i:] if i >= 0 else page + BACK_BAR
            body = page.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, *a):
        pass


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "?"


if __name__ == "__main__":
    try:
        host = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True).stdout.strip()
    except OSError:
        host = ""
    print("목업 목록:")
    if host:
        print(f"  http://{host}.local:{PORT}/   ← 즐겨찾기 추천 (와이파이 IP 가 바뀌어도 그대로)")
    print(f"  http://{lan_ip()}:{PORT}/")
    print("끄기: Ctrl+C", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
