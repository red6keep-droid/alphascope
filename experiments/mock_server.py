"""목업 보기 서버 — 태블릿·휴대폰에서 즐겨찾기 하나로 모든 목업을 연다 (2026-10-31 사용자).

    python experiments/mock_server.py          # 포트 8800 고정
    python experiments/mock_server.py 8801     # 포트 바꾸기

- `/` 인덱스는 열 때마다 experiments/*/output/*.html 을 새로 읽는다 — 목업이 늘거나 바뀌어도 새로고침만 하면 된다.
- 주소가 바뀌지 않게 포트를 고정하고, IP 대신 맥 이름(.local) 주소도 함께 찍는다.
- 같은 와이파이에 열리므로 output 폴더 밖(.env 등)은 내주지 않는다.
"""
import html
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
}
RECENT_N = 12


_themed = {}   # 경로 → (수정 시각, 테마 있음)


def themed(path, mtime):
    """블로그 테마(스타일)를 입힌 미리보기인가. 게시용 본문(X.html · *_body.html)은 스타일이 없어
    날것으로 보이므로 목록에서 뺀다 — 주소로는 그대로 열린다. 이름 규칙이 리포트마다 달라 내용으로 가른다."""
    hit = _themed.get(path)
    if not hit or hit[0] != mtime:
        with open(path, encoding="utf-8", errors="replace") as fh:
            s = fh.read().lower()
        hit = _themed[path] = (mtime, "<style" in s or 'rel="stylesheet"' in s)
    return hit[1]


def mockups():
    """[(폴더, 파일 이름, 수정 시각)] — 최근 수정 순."""
    out = []
    for d in sorted(os.listdir(BASE)):
        od = os.path.join(BASE, d, "output")
        if not os.path.isdir(od):
            continue
        for f in os.listdir(od):
            p = os.path.join(od, f)
            if f.endswith(".html") and themed(p, t := os.path.getmtime(p)):
                out.append((d, f, t))
    return sorted(out, key=lambda x: -x[2])


def row(d, f, t, show_dir=False):
    href = f"/{quote(d)}/output/{quote(f)}"
    when = datetime.fromtimestamp(t).strftime("%m-%d %H:%M")
    sub = f"{LABELS.get(d, d)} · {when}" if show_dir else when
    name = html.escape(f[:-5])
    return (f'<a class="row" href="{href}" data-q="{html.escape(d + " " + f).lower()}">'
            f'<span class="name">{name}</span><span class="sub">{html.escape(sub)}</span></a>')


def index_page():
    items = mockups()
    groups = {}
    for d, f, t in items:
        groups.setdefault(d, []).append((d, f, t))
    parts = ['<section><h2>최근 바뀐 목업</h2>', *(row(*x, show_dir=True) for x in items[:RECENT_N]), "</section>"]
    for d in sorted(groups, key=lambda k: -groups[k][0][2]):   # 최근에 손댄 폴더가 위
        parts.append(f'<details><summary>{html.escape(LABELS.get(d, d))} <span class="n">{len(groups[d])}</span></summary>')
        parts += [row(*x) for x in groups[d]]
        parts.append("</details>")
    now = datetime.now().strftime("%m-%d %H:%M:%S")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>목업 목록</title>
<style>
body{{margin:0;padding:16px;font:16px/1.4 -apple-system,"Apple SD Gothic Neo",sans-serif;background:#f6f7f9;color:#1d2127}}
h1{{font-size:20px;margin:0 0 4px}} .meta{{color:#8a919c;font-size:13px;margin-bottom:12px}}
input{{width:100%;box-sizing:border-box;font-size:16px;padding:10px 12px;border:1px solid #d5d9e0;border-radius:8px;margin-bottom:16px}}
h2{{font-size:15px;color:#5b6370;margin:0 0 8px}} section{{margin-bottom:20px}}
details{{background:#fff;border:1px solid #e3e6eb;border-radius:10px;margin-bottom:10px}}
summary{{padding:14px;font-weight:600;cursor:pointer}} .n{{color:#8a919c;font-weight:400;font-size:14px}}
details .row{{border:0;border-top:1px solid #eef0f3;border-radius:0;margin:0}}
.row{{display:flex;justify-content:space-between;align-items:center;gap:12px;min-height:48px;padding:10px 14px;background:#fff;
border:1px solid #e3e6eb;border-radius:10px;margin-bottom:8px;color:inherit;text-decoration:none}}
.row:active{{background:#eef2f8}} .name{{word-break:break-all}} .sub{{color:#8a919c;font-size:13px;white-space:nowrap}}
</style></head><body>
<h1>목업 목록</h1><div class="meta">{len(items)}개 · 불러온 시각 {now} · 새로고침하면 최신 목록</div>
<input id="q" type="search" placeholder="이름으로 찾기 (예: 005930, mock_)">
{''.join(parts)}
<script>
const q = document.getElementById('q'), ds = [...document.querySelectorAll('details')];
function filter() {{
  const v = q.value.trim().toLowerCase();
  document.querySelectorAll('.row').forEach(r => r.style.display = !v || r.dataset.q.includes(v) ? '' : 'none');
  if (v) ds.forEach(d => d.open = true);
}}
q.addEventListener('input', filter);
// 목업에서 '목록으로' 눌러 돌아오면 펼친 접기 · 검색어 · 스크롤을 그대로 (같은 창 전환)
try {{
  const s = JSON.parse(sessionStorage.getItem('mockIndex') || 'null');
  if (s) {{ ds.forEach((d, i) => d.open = s.open.includes(d.querySelector('summary').textContent));
           q.value = s.q; if (s.q) filter(); scrollTo(0, s.y); }}
}} catch (e) {{}}
addEventListener('pagehide', () => {{
  try {{ sessionStorage.setItem('mockIndex', JSON.stringify({{
    open: ds.filter(d => d.open).map(d => d.querySelector('summary').textContent), q: q.value, y: scrollY }})); }} catch (e) {{}}
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
