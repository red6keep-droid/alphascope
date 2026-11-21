"""하단 메뉴 `종목` → 묶음 탭 목록 목업 (2026-11-17 사용자 "추천대로 진행해서 목업") — 비공개 기획 `doc/기획/종목-탭-그룹-목록-기획.md`.

    python experiments/stock-lists/mock_stock_lists.py   → output/mock_stock-lists-*.html · mock_stock-star-*.html (목업 서버 `stock-lists` 묶음)

화면:
  mock_stock-lists-watch.html       관심 종목 담음 · 미국 → `관심` 탭(담은 순 · 업종 묶음 · 편집 · 아래 브라우저 저장 안내)
  mock_stock-lists-watch-kr.html    관심 종목 담음 · 한국
  mock_stock-lists-empty.html       아직 안 담음 · 미국 → 빈 화면 + 이 기기에서 최근 본 종목 (목업은 `관심` 탭으로 열림)
  mock_stock-star-us.html           종목 상세(엔비디아) 제목 옆 ☆ — 누르면 바로 담기 · 알림 줄
  mock_stock-star-kr.html           종목 상세(SK하이닉스) 같은 동작
관심 종목 = 로그인 없이 이 브라우저(localStorage)에만 저장 (2026-11-19 사용자). 로그인 · 서버 보관은 나중 — 그 전에는 로그인 안내 문구를 넣지 않는다.
별(☆)은 종목 상세 페이지 제목의 종목 이름 바로 뒤(회색 `주가 실적 일정` 앞)에만 둔다(2026-11-17 사용자). 목록 줄에는 없다 — 줄 전체가 링크라 잘못 누르기 쉽다. 빼기는 관심 탭 `편집`.

데이터 = 실제 값, 인터넷 · AI 0:
  간단 종목 853 = 원격 브랜치 quick-us · quick-kr 의 <코드>.json(운영 실행이 이미 올린 가격 요약, `git fetch origin quick-us quick-kr` 뒤)
  정식 종목 · ETF = gh-pages search/us.json · kr.json(브랜치에서 읽음) — S&P 500 밖 정식 종목(TSM · 아이온큐 등)과 미국 시가총액
  한국 시가총액 = ref/universe_all.json. 미국 간단 종목은 시가총액 값이 없다 → 목업 `시가총액` 탭 미국은 값 있는 종목만(구현 = SEC 주식 수 × 종가, 기획 3-1).
"""
import html
import json
import re
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.dirname(EXP)
sys.path.insert(0, EXP)
sys.path.insert(0, os.path.join(EXP, "stock-radar"))
sys.path.insert(0, os.path.join(EXP, "kr-stocks"))
import design_kit as dk  # noqa: E402
import taxonomy  # noqa: E402
import universe as U  # noqa: E402
import universe_kr as UK  # noqa: E402
sys.path.insert(0, HERE)
import build_lists as BL  # noqa: E402  업종 11개로 맞추기(sector11) — 실제 목록 파일과 같은 셈

OUT = os.path.join(HERE, "output")
BLOG = "https://www.newfact.app"
esc = lambda t: html.escape(str(t), quote=False)  # noqa: E731
attr = lambda t: html.escape(str(t), quote=True)  # noqa: E731

# 오늘 움직임 기준 (기획 2-3 제안값)
UP_PCT, DOWN_PCT, VOL_X, NEAR_HI = 3.0, -3.0, 2.0, -2.0
TOP = 10   # 이 페이지 목록은 10개까지만, 접기 없이 다 펼침 (2026-11-17 사용자 "10개만 보여줘. 다른 종목들도 모두 10개 이상은 보여주지마") — CLAUDE.md `상한으로 버리지 않기`의 예외. 관심 탭(회원이 담은 목록)은 제외
STAR = "#F5B400"
STAR_PATH = "M12 3.2l2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 17l-5.4 2.9 1.1-6.1-4.5-4.2 6.1-.8z"
G_LOGO = ('<svg viewBox="0 0 18 18" width="18" height="18" aria-hidden="true"><path fill="#4285F4" d="M17.6 9.2c0-.6-.1-1.2-.2-1.8H9v3.4h4.8a4.1 4.1 0 0 1-1.8 2.7v2.2h2.9c1.7-1.6 2.7-3.9 2.7-6.5z"/>'
          '<path fill="#34A853" d="M9 18c2.4 0 4.5-.8 6-2.2l-2.9-2.2c-.8.5-1.8.9-3.1.9-2.4 0-4.4-1.6-5.1-3.8H.9v2.3A9 9 0 0 0 9 18z"/>'
          '<path fill="#FBBC05" d="M3.9 10.7a5.4 5.4 0 0 1 0-3.4V5H.9a9 9 0 0 0 0 8l3-2.3z"/>'
          '<path fill="#EA4335" d="M9 3.6c1.3 0 2.5.5 3.5 1.4l2.6-2.6A9 9 0 0 0 .9 5l3 2.3C4.6 5.2 6.6 3.6 9 3.6z"/></svg>')
LOGIN_BTN = ("display:flex;align-items:center;justify-content:center;gap:10px;width:100%;box-sizing:border-box;height:52px;border-radius:10px;"
             "font-size:17px;line-height:24px;font-weight:700;text-decoration:none;cursor:pointer;background:#fff;color:#111;border:1px solid #CBD5E1;")

# 예시 관심 종목(담은 순) · 최근 본 종목 — 실제는 Firestore watch/{uid} · 브라우저 저장
# 예시 관심 종목 — 미국 7업종 · 한국 4업종 (경우 단추는 업종 탭 확정 뒤 삭제, 2026-11-18)
WATCH = ["NVDA", "AAPL", "MSFT", "TSLA", "AMZN", "JPM", "LLY", "XOM", "META", "GOOGL", "CAT", "IONQ", "PLTR",
         "005930.KS", "000660.KS", "035420.KS", "005380.KS", "105560.KS", "373220.KS", "012450.KS"]
RECENT = ["NVDA", "AAPL", "005930.KS", "TSLA"]


# ── 자료 ───────────────────────────────────────────────────────────
def git_show(ref):
    r = subprocess.run(["git", "show", ref], capture_output=True, cwd=ROOT)
    return r.stdout if r.returncode == 0 else None


def git_ls(ref, path):
    r = subprocess.run(["git", "ls-tree", "--name-only", f"{ref}:{path}"], capture_output=True, text=True, cwd=ROOT)
    return r.stdout.split() if r.returncode == 0 else []


def load():
    rows = {}
    for br, m in (("origin/quick-us", "us"), ("origin/quick-kr", "kr")):
        names = [f for f in git_ls(br, m) if f.endswith(".json") and f not in ("version.json", "bench.json")]
        if not names:
            sys.exit(f"{br} 가 없습니다 — 먼저 `git fetch --depth 1 origin quick-us:refs/remotes/origin/quick-us quick-kr:refs/remotes/origin/quick-kr`")
        for f in names:
            d = json.loads(git_show(f"{br}:{m}/{f}"))
            if d.get("status") == "halted" or not d.get("c"):
                continue
            rows[d["s"]] = {"s": d["s"], "n": d["n"], "m": m, "sec": BL.sector11(d.get("sec")), "f": bool(d.get("full")),
                            "c": d["c"], "r": (d.get("chg") or {}).get("1d"), "v": d.get("vol_ratio"), "h": d.get("off_hi"), "d": d["d"], "cap": None}
    etf = {"us": [], "kr": []}
    for m in ("us", "kr"):
        idx = json.loads(git_show(f"origin/gh-pages:search/{m}.json") or b"{}")
        for s in idx.get("stocks", []):
            p = s["p"]
            row = rows.get(s["s"]) or {"s": s["s"], "n": s["n"], "m": m, "sec": BL.sector11(s.get("sec")), "f": True, "c": p["c"], "r": p.get("chg"),
                                       "v": round(p["v"] / p["va"], 2) if p.get("va") else None,
                                       "h": round((p["c"] / p["h52"][0] - 1) * 100, 2) if p.get("h52") else None, "d": p["d"], "cap": None}
            row["f"], row["u"], row["ne"] = True, s["u"], s.get("ne")
            if s.get("cap"):
                row["cap"] = s["cap"]
            rows[s["s"]] = row
        for e in idx.get("etfs", []):
            p = e["p"]
            etf[e["m"]].append({"s": e["s"], "n": e["n"], "m": e["m"], "sec": e.get("tr") or "", "f": True, "c": p["c"], "r": p.get("chg"), "u": e["u"], "d": p["d"], "etf": 1})
    uni = json.load(open(os.path.join(EXP, "ref", "universe_all.json"), encoding="utf-8"))
    for x in uni["kr"]:
        if x["sym"] in rows and x.get("cap"):
            rows[x["sym"]]["cap"] = rows[x["sym"]]["cap"] or x["cap"]
    for r in rows.values():
        r.setdefault("u", f"{BLOG}/p/stock.html?s={r['s'].split('.')[0]}")
    return rows, etf


def extra_rows(rows, syms):
    """목록 파일에 아직 없는 새 정식 후보(SKHY · ARM, 2026-11-18) — 목업만 야후 일봉 2개로 종가 · 등락을 채운다. 실패하면 뺀다(운영은 정식 수집이 채움)."""
    import urllib.request
    base = max(r["d"] for r in rows.values() if r["m"] == "us")   # 기준일은 목록 파일 날짜 그대로 (야후 최신 날이 페이지 날짜를 끌어올리지 않게)
    for sym in syms:
        if sym in rows:
            continue
        try:
            req = urllib.request.Request(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d", headers={"User-Agent": "Mozilla/5.0"})
            res = json.load(urllib.request.urlopen(req, timeout=8))["chart"]["result"][0]
            cl = [c for c in res["indicators"]["quote"][0]["close"] if c]
            rows[sym] = {"s": sym, "n": (U.name(sym) if sym in U.BY_SYM else sym), "m": "us", "sec": "기술", "f": True, "c": round(cl[-1], 2),
                         "r": round((cl[-1] / cl[-2] - 1) * 100, 2), "v": None, "h": None, "d": base, "cap": None, "u": f"{BLOG}/p/stock.html?s={sym}"}
        except Exception as e:   # noqa: BLE001
            print(f"[종목 목록] {sym} 가격 못 받음 — 목업에서 뺌 ({e})")
    return rows


# ── 화면 조각 ────────────────────────────────────────────────────────
def pct_html(v, px=15, bold=True):
    if v is None:
        return f'<span style="color:{dk.MUTED};">—</span>'
    col = dk.UP if v > 0 else dk.DOWN if v < 0 else dk.MUTED
    tri = "▲" if v > 0 else "▼" if v < 0 else ""
    t = f'<span style="font-size:{round(px * 0.8)}px;vertical-align:1px;margin-right:2px;">{tri}</span>' if tri else ""
    return f'<span style="color:{col};white-space:nowrap;{"font-weight:700;" if bold else ""}">{t}{abs(v):.2f}%</span>'


def dir_col(v):
    return dk.UP if v and v > 0 else dk.DOWN if v and v < 0 else "#111"


def price_text(r):
    return f"${r['c']:,.2f}" if r["m"] == "us" else f"{r['c']:,.0f}원"


def cap_text(r):
    c = r.get("cap")
    if not c:
        return ""
    if r["m"] == "us":
        return f"{c / 1e12:.2f}조 달러" if c >= 1e12 else f"{c / 1e8:,.0f}억 달러"
    return (f"{c / 1e12:,.0f}조 원" if c >= 1e13 else f"{c / 1e12:.1f}조 원") if c >= 1e12 else f"{c / 1e8:,.0f}억 원"


def code(r):
    return r["s"].split(".")[0]


def sub_of(r, tail):
    """종목 줄 회색 보조 줄 — 한국 종목은 종목 코드(숫자)를 넣지 않는다 (2026-11-18 사용자). 미국은 티커 · tail."""
    return tail if r["m"] == "kr" else (f"{code(r)} · {tail}" if tail else code(r))


def row_html(r, i, sub=None, right_sub=None, rank=None, chips=""):
    """종목 줄 — 지금 목록 페이지 줄(list_row)과 같은 짜임: [순위] 로고 이름(굵게 16) / 회색 보조 줄 · 오른쪽 가격 / 등락. 줄 전체 = 종목 페이지."""
    sub = sub if sub is not None else sub_of(r, r['sec'])
    rk = (f'<span style="flex:none;width:26px;color:{dk.NOTE};font-weight:700;font-size:15px;line-height:24px;">{rank}</span>' if rank else "")
    # 로고 22 → 44, 이름 · 보조 줄 두 줄의 세로 가운데 (2026-11-17 사용자 "로고 2배 · 오른쪽 글자와 미들 정렬")
    left = (f'<span style="display:flex;align-items:center;min-width:0;flex:1 1 auto;">{rk}'
            f'<span style="flex:none;display:flex;align-items:center;">{dk.ticker_logo(r["s"], LOGO_PX).replace("vertical-align:-4px;", "vertical-align:0;").replace("margin-right:6px;", f"margin-right:{LOGO_GAP}px;")}</span>'
            f'<span style="min-width:0;"><span style="display:block;font-size:16px;line-height:24px;font-weight:700;color:#111;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{esc(r["n"])}</span>'
            f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};white-space:nowrap;">{sub}</span>{chips}</span></span>')
    rs = right_sub if right_sub is not None else pct_html(r["r"], CHG_PX)
    right = (f'<span style="flex:none;display:flex;flex-direction:column;align-items:flex-end;white-space:nowrap;">'
             f'<span style="font-size:{CHG_PX}px;line-height:24px;">{rs}</span>'
             f'<span style="font-size:15px;line-height:{dk.LH_TINY};color:{dir_col(r["r"])};">{esc(price_text(r))}</span></span>')   # 증감 위 · 가격 아래 (2026-11-17 사용자 규칙), 가격 = 증감과 같은 색 (2026-11-18 사용자)
    return (f'<span data-row-link="1" data-href="{attr(r["u"])}" data-sym="{attr(r["s"])}" style="{ROW_STYLE}{f"padding-top:{ROW_TOP}px;" if i == 0 else dk.MULTI_SEP}align-items:flex-start;">'
            f'{left}{right}</span>')


LIST_BOX = "display:block;margin:0 0 8px;border-bottom:1px solid #E2E8F0;"   # 카드 없이 구분선 목록 — 맨 위 선 없음 · 줄 사이 · 맨 끝 선 (2026-11-17 사용자 "카드로 하지 말고 그냥 구분선으로", 가이드라인 구분선 목록 = dk.rule_rows 와 같은 틀)
ROW_TOP = dk.RULE_GAP - 1 - dk.VP - 3   # 첫 줄 위 = 24 − 3 = 21 (2026-11-17 사용자: 처음엔 첫 종목 자리 유지, 이어 "타이슨 푸드도 같이 3픽셀 더")
ROW_PAD = ROW_TOP - 5                    # 구분선 위아래 = 21 − 5 = 16 (2026-11-17 사용자: −5 뒤 전체 −3)
ROW_STYLE = dk.MULTI_ROW.replace(f"padding:{dk.SEP_GAP - dk.VP - 1}px 12px;", f"padding:{ROW_PAD}px {dk.ALIGN_PX}px;")   # 좌우 = 왼쪽 기준선 6


def list_card(items, render, empty=""):
    """앞에서 10개만, 다 펼침 (TOP). 카드가 아니라 구분선 목록 (2026-11-17 사용자)."""
    if not items:
        return empty
    shown = "".join(render(x, i) for i, x in enumerate(items[:TOP]))
    return f'<div data-cards="1" style="margin:0 0 8px;"><span data-list="1" style="{LIST_BOX}">{shown}</span></div>'



def pills(key, names, on=0, joined=False):
    """알약 줄. joined = 홈 `테마 종목` 아래 묶음 줄(#watch-tabs) 모양 — 칸이 붙은 한 줄 상자 (2026-11-17 사용자: 오늘 움직임 · 테마)."""
    return (f'<div class="seg-row{" sl-joined" if joined else ""}" data-sl-pills="{key}" style="padding:0 0 12px;">'
            + "".join(f'<button class="seg" type="button" data-sl-pill="{i}" aria-selected="{"true" if i == on else "false"}">{esc(n)}</button>' for i, n in enumerate(names))
            + "</div>")


def panels(key, bodies, on=0):
    return "".join(f'<div data-sl-panel="{key}:{i}"{"" if i == on else " hidden"}>{b}</div>' for i, b in enumerate(bodies))


def note(t):
    return f'<p style="font-size:13px;line-height:19px;color:{dk.NOTE};margin:4px 0 12px;padding-left:{dk.ALIGN_PX}px;word-break:keep-all;">{esc(t)}</p>'


def empty_box(title, text, extra=""):
    """관심 탭 안내(로그인 전 · 담은 종목 없음) — 카드 없이 가운데 정렬, 제목 17/26 레귤러 · 문장 15/24, 글자 전부 회색 (2026-11-19 사용자)."""
    return (f'<div style="text-align:center;padding:32px {dk.ALIGN_PX}px 24px;">'
            f'<div style="font-size:17px;line-height:26px;font-weight:400;color:{dk.NOTE};">{esc(title)}</div>'
            f'<div style="font-size:15px;line-height:24px;color:{dk.NOTE};margin:4px 0 0;word-break:keep-all;">{text}</div>{extra}</div>')


def recent_head():
    """`이 기기에서 최근 본 종목` — 기본형 아이콘(시계, 회색 원 22) + 소제목 15/22 굵게, 글자와 6 (가이드라인 8절) · 아래 구분선 #E2E8F0 (2026-11-19 사용자). 접기 버튼은 넣었다가 뺐다(같은 날 사용자)."""
    return (f'<div style="display:flex;align-items:center;gap:6px;margin:8px 0 0;padding:0 0 12px {dk.ALIGN_PX}px;border-bottom:1px solid #E2E8F0;font-size:15px;line-height:22px;font-weight:700;color:#111;">'
            f'{dk.soft_icon("clock")}이 기기에서 최근 본 종목</div>')


def info_card(title, text, extra=""):
    return dk.dcard(f'<div style="font-size:17px;line-height:26px;font-weight:700;color:#111;">{esc(title)}</div>'
                    f'<div style="font-size:15px;line-height:24px;color:#333;margin:4px 0 0;word-break:keep-all;">{text}</div>{extra}')


# ── 히트맵 (테마 · 업종 탭 묶음 고르기, 2026-11-18 사용자 "네모난 히트맵이 상단에, 누르면 그 종목들") ──
# 칸 크기 = 묶음 시가총액 합의 제곱근(작은 묶음도 눌릴 크기로 남게 — 원값이면 반도체 하나가 판을 덮는다). 시가총액 값이 절반 넘게 없는 묶음(목업의 미국 업종)은 종목 수.
# 칸 색 = 묶음 전 종목 하루 등락 단순 평균(10개 목록 밖 종목도 포함), 빨강 오름 · 파랑 내림 4단계 + 보합 회색. 글자 = 이름 · ▲▼ 평균. 칸은 하나도 버리지 않는다.
HEAT_W, HEAT_GAP = 360, 2   # 판 기준 너비(폰) — 칸 위치는 % 로 써서 실제 너비에 맞춰 늘어난다
# 색 = D안(사이트 강조 카드 바탕 계열) + 세기 4단계 조금 (2026-11-18 사용자 "D안, 컬러 대비 조금만" · 시안 mock_heat_colors.py)
# 글자(이름 · 숫자) = 칸과 같은 방향 색 — 파랑 칸엔 파랑 글자, 빨강 칸엔 빨강 글자 (2026-11-18 사용자). 가장 진한 칸은 한 톤 짙은 글자(대비).
HEAT_UP = ["#FFF7EE", "#FFECE0", "#FDDDD0", "#F9CBBD"]
HEAT_DN = ["#EFF6FF", "#E2EEFE", "#D0E3FD", "#BCD6FB"]
HEAT_FLAT = "#F8FAFC"
HEAT_FG_UP, HEAT_FG_DN = [dk.UP, dk.UP, dk.UP, "#B3261E"], [dk.DOWN, dk.DOWN, dk.DOWN, "#1558B0"]


def heat_color(v):
    """(바탕, 글자) — 0.1% 미만 보합 · 1 · 2 · 3% 경계."""
    if v is None or abs(v) < 0.1:
        return HEAT_FLAT, "#333"
    k = 0 if abs(v) < 1 else 1 if abs(v) < 2 else 2 if abs(v) < 3 else 3
    return (HEAT_UP if v > 0 else HEAT_DN)[k], (HEAT_FG_UP if v > 0 else HEAT_FG_DN)[k]


def squarify(vals, x, y, w, h):
    """squarified treemap — vals 는 큰 순, 합 = w*h 로 맞춘 넓이. [(x, y, w, h)]."""
    out, i = [], 0
    while i < len(vals):
        short = min(w, h)
        row, best = [vals[i]], None
        def worst(r):
            sm = sum(r)
            return max(max(short * short * v / (sm * sm), (sm * sm) / (short * short * v)) for v in r)
        best = worst(row)
        j = i + 1
        while j < len(vals):
            cand = row + [vals[j]]
            wc = worst(cand)
            if wc > best:
                break
            row, best, j = cand, wc, j + 1
        sm = sum(row)
        if w >= h:   # 왼쪽에 세로 줄
            cw = sm / h
            yy = y
            for v in row:
                out.append((x, yy, cw, v / cw)); yy += v / cw
            x, w = x + cw, w - cw
        else:        # 위에 가로 줄
            rh = sm / w
            xx = x
            for v in row:
                out.append((xx, y, v / rh, rh)); xx += v / rh
            y, h = y + rh, h - rh
        i = j
    return out


def heat_size(xs):
    caps = [r["cap"] for r in xs if r.get("cap")]
    if len(caps) * 2 >= len(xs):
        return sum(caps) ** 0.5, "cap"
    return float(len(xs)), "n"


def heatmap(key, groups, color=None, label=None):
    """groups = [(이름, 종목 줄들)] → (판 HTML, 큰 순으로 다시 놓은 groups). 칸 = 기존 알약과 같은 data-sl-pill(같은 탭 전환 JS)."""
    sized = []
    for n, xs in groups:
        sz, how = heat_size(xs)
        rs = [r["r"] for r in xs if r["r"] is not None]
        sized.append((sz, n, xs, sum(rs) / len(rs) if rs else None, how))
    if len({t[4] for t in sized}) > 1:   # 한 판 안에서 잣대를 섞지 않는다
        sized = [(float(len(xs)), n, xs, a, "n") for _, n, xs, a, _ in sized]
    floor = 0.04 * sum(t[0] for t in sized)   # 칸 최소 = 판의 4% — 2종목짜리 업종이 가는 선으로 보였다 (2026-11-18)
    sized = [(max(t[0], floor),) + t[1:] for t in sized]
    sized.sort(key=lambda t: -t[0])
    H = 240 if len(sized) <= 8 else 300
    tot = sum(t[0] for t in sized)
    rects = squarify([t[0] * HEAT_W * H / tot for t in sized], 0, 0, HEAT_W, H)
    cells = []
    for i, ((_, n, xs, avg, _), (x, y, w, h)) in enumerate(zip(sized, rects)):
        bg, fg = (color or heat_color)(avg)   # 색 시안 비교(mock_heat_colors.py)는 color · label 을 바꿔 끼운다
        pct = label(avg) if label else "" if avg is None else f'{"▲" if avg > 0 else "▼" if avg < 0 else ""}{abs(avg):.2f}%'
        big = w >= 90 and h >= 64
        name_px = 15 if big else 13
        show_pct = h >= 40 and w >= 40
        inner = (f'<span class="hm-n" style="font-size:{name_px}px;line-height:{name_px + 5}px;">{esc(n)}</span>'
                 + (f'<span class="hm-p" style="font-size:{name_px - 1}px;line-height:{name_px + 3}px;">{pct}</span>' if show_pct else ""))
        pos = (f"left:{x / HEAT_W * 100:.3f}%;top:{y / H * 100:.3f}%;width:{w / HEAT_W * 100:.3f}%;height:{h / H * 100:.3f}%;")
        cells.append(f'<button type="button" class="hm-c" data-sl-pill="{i}" aria-selected="{"true" if i == 0 else "false"}" '
                     f'aria-label="{attr(n)} {attr(pct)}" style="{pos}background:{bg};color:{fg};--hm-fg:{fg};">{inner}</button>')
    how = sized[0][4] if sized else "cap"
    board = (f'<div class="hm" data-sl-pills="{key}" data-sl-heat style="height:{H}px;">{"".join(cells)}</div>')
    basis = "칸 크기 = 시가총액" if how == "cap" else "칸 크기 = 종목 수"
    return board, [(n, xs) for _, n, xs, _, _ in sized], f"{basis} · 색 = 묶음 평균 등락(마지막 종가)"


# ── 탭 ──────────────────────────────────────────────────────────────
def move_tab(rows, m, stats):
    xs = [r for r in rows.values() if r["m"] == m and r["r"] is not None]
    groups = [
        ("상승 종목", sorted([r for r in xs if r["r"] >= UP_PCT], key=lambda r: -r["r"]), sorted(xs, key=lambda r: -r["r"]),
         f"{UP_PCT:.0f}% 넘게 오른 종목이 없어 많이 오른 순입니다.", None),
        ("하락 종목", sorted([r for r in xs if r["r"] <= DOWN_PCT], key=lambda r: r["r"]), sorted(xs, key=lambda r: r["r"]),
         f"{abs(DOWN_PCT):.0f}% 넘게 내린 종목이 없어 많이 내린 순입니다.", None),
        ("거래 급증", sorted([r for r in xs if (r["v"] or 0) >= VOL_X], key=lambda r: -r["v"]), sorted([r for r in xs if r["v"]], key=lambda r: -r["v"]),
         "평소의 2배를 넘은 종목이 없어 많이 늘어난 순입니다.",
         lambda r: f'<span style="color:{dk.NOTE};font-size:{dk.TINY};">평소의 {r["v"]:.1f}배 · </span>{pct_html(r["r"], CHG_PX)}'),   # 말 = 회색 보조 줄과 같은 크기 · 색, 증감 = 다른 탭처럼 굵게 (2026-11-18 사용자)
        ("52주 최고가 근처", sorted([r for r in xs if r["h"] is not None and r["h"] >= NEAR_HI], key=lambda r: -r["h"]),
         sorted([r for r in xs if r["h"] is not None], key=lambda r: -r["h"]),
         "최고가 2% 안 종목이 없어 가까운 순입니다.",
         lambda r: f'<span style="color:{dk.UP};font-weight:700;font-size:{CHG_PX}px;">최고가</span>' if r["h"] >= 0
         else f'<span style="color:{dk.NOTE};font-size:{dk.TINY};">최고가까지 </span><b style="color:{dk.DOWN};font-size:{CHG_PX}px;">{abs(r["h"]):.1f}%</b>'),   # 말 = 보조 줄 크기 · 색, 최고가 · 남은 % = 증감 숫자 크기 굵게 (2026-11-18 사용자)   # 최고가 = 빨강 굵게, 남은 % = 파랑 굵게, 크기 = 보조 줄 (2026-11-18 사용자)
    ]
    bodies = []
    for name, hit, fallback, empty_text, rsub in groups:
        stats.append((m, name, len(hit)))
        render = lambda r, i, rsub=rsub: row_html(r, i, right_sub=rsub(r) if rsub else None)  # noqa: E731
        if hit:
            bodies.append(list_card(hit, render))
        else:
            bodies.append(list_card(fallback, render) + note(empty_text))   # 탭 · 묶음 줄 바로 아래엔 정보 없음 — 안내는 목록 아래 (2026-11-17 사용자)
    basis = "마지막 종가 기준 · 거래 급증 = 20일 평균의 2배 이상"   # 짧게 (2026-11-17 사용자 "읽어볼 사람 거의 없어, 짤막하게")
    return pills(f"move-{m}", [g[0] for g in groups], joined=True) + panels(f"move-{m}", bodies) + note(basis)


def theme_groups(m):
    if m == "us":
        g = [(n, syms) for n, syms in U.WATCH_NEXT]   # 다음 테마 구성 목업 (2026-11-18)
        g += [(t["name"], t["members"]) for t in taxonomy.THEMES.values()]
        return g
    return [(n.replace(" · ", "·"), syms) for n, syms in UK.WATCH]


def theme_tab(rows, m):
    groups = [(n, [rows[s] for s in syms if s in rows]) for n, syms in theme_groups(m)]
    groups = [(n, xs) for n, xs in groups if xs]
    board, groups, basis = heatmap(f"theme-{m}", groups)
    bodies = []
    for n, xs in groups:
        # `n종목 중 n개 오름 · 평균` 줄 삭제 — 탭 · 묶음 줄 아래 바로 목록 (2026-11-17 사용자)
        link = ""
        if m == "us" and n in ("AI 칩", "메모리", "칩 생산", "반도체 장비", "데이터 센터"):   # 반도체를 넷으로 나눔 (2026-11-19)
            link = (f'<a href="{BLOG}/p/theme-ai-capex.html" style="display:block;margin:4px 0 12px;padding-left:{dk.ALIGN_PX}px;font-size:15px;line-height:24px;'
                    f'color:#111;font-weight:700;text-decoration:none;">AI 투자 자금 흐름 보기 →</a>')
        bodies.append(list_card(sorted(xs, key=lambda r: -(r["r"] or -99)), lambda r, i: row_html(r, i)) + link)
    return board + panels(f"theme-{m}", bodies) + note(basis)   # 히트맵이 묶음 줄 자리 (2026-11-18 사용자)


def sector_tab(rows, m):
    by = {}
    for r in rows.values():
        if r["m"] == m:
            by.setdefault(r["sec"], []).append(r)
    board, groups, basis = heatmap(f"sec-{m}", [(k, by[k]) for k in by])
    order = [n for n, _ in groups]
    bodies = []
    for k in order:
        xs = sorted(by[k], key=lambda r: -(r["cap"] or 0))
        bodies.append(list_card(xs, lambda r, i: row_html(r, i, sub=sub_of(r, cap_text(r) if r.get("cap") else ""))))
    return board + panels(f"sec-{m}", bodies) + note(basis)


def cap_tab(rows, m):
    xs = sorted([r for r in rows.values() if r["m"] == m and r.get("cap")], key=lambda r: -r["cap"])
    return list_card(xs, lambda r, i: row_html(r, i, sub=sub_of(r, cap_text(r)), rank=i + 1))   # `시가총액 상위 10 종목 페이지 →` 줄 삭제 — 여기서 다 본다 (2026-11-19 사용자)


def etf_tab(etf, m):
    xs = etf[m]
    return list_card(xs, lambda r, i: row_html(r, i, sub=esc(r["sec"]))) + note("지수 · 업종을 따라가는 상품")


GRIP = ('<span data-sl-grip aria-label="끌어서 순서 바꾸기" style="display:none;flex:none;align-self:center;width:32px;height:32px;margin:0 -6px 0 0;align-items:center;justify-content:center;'
        'color:#9CA3AF;cursor:grab;touch-action:none;"><svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true"><path d="M4 6.5h12M4 10h12M4 13.5h12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></span>')
# 빼기 = 흰 바탕 + 연한 빨강 테두리 선 1 + 빨강 − (2026-11-18 사용자 "빨간 채움 말고 흰 바탕 라인으로, 너무 세지 않게" — 옛 #E5484D 채움 · 흰 −)
RM = ('<button type="button" data-sl-rm aria-label="{name} 빼기" style="display:none;flex:none;align-self:center;width:24px;height:24px;margin:0 10px 0 0;padding:0;border:1px solid #F3A6A3;border-radius:50%;box-sizing:border-box;'
      'background:#fff;cursor:pointer;"><svg viewBox="0 0 22 22" width="22" height="22" aria-hidden="true"><path d="M7 11h8" stroke="#E5484D" stroke-width="1.6" stroke-linecap="round"/></svg></button>')
LOGO_GAP = 11  # 로고 ~ 종목 이름 6 → 11 (2026-11-18 사용자 "5픽셀 정도 여백")
LOGO_PX = 35   # 종목 줄 로고 (2026-11-17 사용자: 22 의 2배 = 44 → 20% 작게 = 35)
CHG_PX = 17    # 오른쪽 윗줄 증감 글자 15 → 16 (2026-11-17 사용자 "한 포인트 더") → 17 (2026-11-18 사용자 "1포인트 더"), 삼각형 = 80% → 14
# 저장 안내 = 목록 아래 작은 회색 (2026-11-19 사용자: 로그인 없이 브라우저에 임시 저장). 서버 보관(로그인)이 생기면 `계정에 보관하려면 로그인하세요` 를 더한다 — 그 전엔 넣지 않는다
SAVE_NOTE = "관심 종목은 이 브라우저에만 저장됩니다. 홈 화면에 추가해 두면 더 오래 남습니다."
A2HS_BTN = ("display:inline-block;margin:0 0 0 6px;padding:0 7px;border:1px solid #CBD5E1;border-radius:6px;background:#fff;"
            "font:inherit;font-size:12px;line-height:18px;font-weight:700;color:#111;vertical-align:baseline;cursor:pointer;-webkit-tap-highlight-color:transparent;")


def save_note():
    """저장 안내 + 아주 작은 `홈 화면에 추가` 버튼 (2026-11-19 사용자 "최대한 작게") — 12/18 굵게 · 외곽선 · 높이 20.
    누르면 테마의 홈 화면 추가 안내(window.asA2hs: 안드로이드 설치 창 · 아이폰 방법)를 바로 연다. 이미 홈 화면 앱이거나 PC 면 버튼을 숨긴다(asA2hs 없음)."""
    return (f'<p style="font-size:13px;line-height:19px;color:{dk.NOTE};margin:4px 0 12px;padding-left:{dk.ALIGN_PX}px;word-break:keep-all;">{esc(SAVE_NOTE)}'
            f'<button type="button" data-sl-a2hs hidden style="{A2HS_BTN}">홈 화면에 추가</button></p>'
            "<script>(function(){function go(){var b=document.querySelector('[data-sl-a2hs]');if(!b||!window.asA2hs)return;b.hidden=false;"
            "b.onclick=function(){window.asA2hs();};}if(document.readyState==='complete')go();else window.addEventListener('load',go);})();</script>")


WATCH_MAX = 100   # 미국 · 한국 합쳐 100개 (2026-11-17 사용자 "200개 담는 사람이 누가 있다고 · 100개까지만"). 안내 문장은 두지 않고, 넘칠 때만 알림


def watch_rows(rows, syms):
    """관심 줄 = 다른 탭 줄과 같은 모양. 편집 모드에서만 왼쪽 빼기(−) · 오른쪽 끌기(≡)가 나오고 가격 칸이 숨는다."""
    out = []
    for i, s in enumerate(syms):
        r = rows[s]
        h = row_html(r, i)
        h = h.replace('align-items:flex-start;">', 'align-items:flex-start;">' + RM.format(name=attr(r["n"])), 1)
        h = h.replace('<span style="flex:none;display:flex;flex-direction:column;align-items:flex-end;', '<span data-sl-price style="flex:none;display:flex;flex-direction:column;align-items:flex-end;', 1)
        out.append(h[:-len("</span>")] + GRIP + "</span>")
    return out


SEARCH_ICON = ('<svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" '
               'style="flex:none;display:block;"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>')   # 테마 헤더 검색 아이콘과 같은 꼴 (2026-11-19 사용자 "종목 검색해서 담기 앞에 돋보기")
PLUS_ICON = ('<span aria-hidden="true" style="flex:none;display:inline-flex;width:22px;height:22px;border-radius:50%;background:#E5E7EB;align-items:center;justify-content:center;">'
             '<svg viewBox="0 0 12 12" width="12" height="12"><path d="M6 1.5v9M1.5 6h9" stroke="#4B5563" stroke-width="1.6" stroke-linecap="round"/></svg></span>')


def watch_member(rows, syms, m, all_rows):
    """관심 탭(로그인) — 탭 바로 아래는 목록뿐 (2026-11-17 사용자: 탭 밑에 정보 없음, 종목 수 · 편집 버튼 · 나라 안내 · 200개 안내 삭제).
    편집 모드 들어가기 = ① 줄을 길게 누르기(0.5초) ② 목록 맨 끝 줄 오른쪽 `편집`. 맨 끝 줄 왼쪽 = `종목 추가`(검색 팝업에서 바로 담기).
    편집 모드 = 줄 왼쪽 빼기 · 오른쪽 끌어서 순서 바꾸기, 화면 맨 아래 고정 바 `전체 삭제` · `완료`(하단 메뉴 자리를 잠시 덮음)."""
    lst = f'<div data-cards="1"{"" if syms else " hidden"} style="margin:0 0 8px;"><span data-list="1" data-sl-list style="{LIST_BOX}">{"".join(watch_rows(rows, syms))}</span></div>'
    foot = (f'<div data-sl-foot style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:6px {dk.ALIGN_PX}px 12px;">'
            f'<button type="button" data-sl-add style="display:inline-flex;align-items:center;gap:8px;padding:8px 0;border:0;background:none;font:inherit;font-size:16px;line-height:24px;font-weight:700;color:#111;cursor:pointer;">{PLUS_ICON}종목 추가</button>'
            f'<button type="button" data-sl-edit style="padding:8px 0 8px 12px;border:0;background:none;font:inherit;font-size:15px;line-height:22px;color:{dk.NOTE};cursor:pointer;">편집</button></div>')
    # 빈 상태 = 카드 없이 가운데 정렬 · 글자 전부 회색 · 제목 레귤러 · 큰 별 없음(문장 속 ★ 만) · 버튼 앞 돋보기 (2026-11-19 사용자)
    find_btn = f'<button type="button" data-sl-add style="{dk.FOLD_BTN}width:100%;box-sizing:border-box;margin:16px 0 0;font:inherit;font-size:15px;line-height:22px;font-weight:700;">{SEARCH_ICON}종목 검색해서 담기</button>'
    empty = empty_box("담은 종목이 없습니다",
                      f'종목을 검색해서 바로 담거나, 종목 페이지 제목 옆 <span style="color:{STAR};">★</span> 를 누르면 여기에 모입니다.', find_btn)
    bar = ('<div data-sl-bar role="toolbar" aria-label="관심 종목 편집">'
           '<button type="button" data-sl-clear class="sl-bar-btn">전체 삭제</button>'
           '<button type="button" data-sl-done class="sl-bar-btn sl-bar-main">완료</button></div>')
    # 검색 자료(목업) — 실제 = 블로그 검색 색인(gh-pages search/<시장>.json + 간단 종목 목록 _lists.json), 팝업을 열 때 한 번 받음
    data = [{"s": r["s"], "n": r["n"], "c": code(r), "sec": r["sec"], "m": r["m"], "p": price_text(r), "r": r["r"], "k": r.get("cap") or 0} for r in all_rows.values()]
    held = [s for s in WATCH if s in all_rows]
    cfg = {"m": m, "max": WATCH_MAX, "held": held if syms else [s for s in held if all_rows[s]["m"] != m], "recent": RECENT,
           "row": ROW_STYLE, "logo": LOGO_PX, "top": ROW_TOP, "pad": ROW_PAD, "sep": dk.MULTI_SEP, "rm": RM, "grip": GRIP, "note": dk.NOTE, "up": dk.UP, "down": dk.DOWN, "muted": dk.MUTED, "star": STAR, "starPath": STAR_PATH, "chg": CHG_PX, "gap": LOGO_GAP}
    js = ('<script type="application/json" id="sl-data">' + json.dumps({"cfg": cfg, "rows": data}, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    # 이 기기에서 최근 본 종목 = 담은 종목이 없을 때만 (2026-11-19 사용자: 관심 종목이 있으면 같이 안 보인다)
    recent = [all_rows[x] for x in RECENT if x in all_rows and all_rows[x]["m"] == m]
    recent_html = (recent_head() + list_card(recent, lambda r, i: row_html(r, i)).replace(f"padding-top:{ROW_TOP}px;", "", 1)) if recent else ""
    return (f'<div data-sl-watch="1"><div data-sl-comp></div>{lst}<div data-sl-has{"" if syms else " hidden"}>{foot}</div>'
            f'<div data-sl-empty{"" if not syms else " hidden"}>{empty}{recent_html}</div>{save_note()}</div>{bar}{js}')


def watch_tab(rows, state, m):
    """관심 탭 — state: empty(아직 안 담음) · watch(담음). 들어온 나라(m) 종목만 (2026-11-17 사용자). 로그인 화면 없음 — 브라우저 저장 (2026-11-19 사용자)."""
    syms = [] if state == "empty" else [s for s in WATCH if s in rows and rows[s]["m"] == m]
    return watch_member(rows, syms, m, rows)


# ── 페이지 ───────────────────────────────────────────────────────────
TOAST_CSS = (".sl-toast{position:fixed;left:50%;transform:translateX(-50%);bottom:24px;z-index:60;display:flex;gap:14px;align-items:center;padding:12px 16px;"
             "background:#111;color:#fff;border-radius:10px;font-size:15px;line-height:22px;box-shadow:0 6px 20px rgba(0,0,0,.2);white-space:nowrap;}"
             ".sl-toast a{color:#FCD34D;font-weight:700;text-decoration:none;}"
             "@media (max-width:900px){.sl-toast{bottom:calc(85px + env(safe-area-inset-bottom));}}")
PAGE_CSS = ("<style>[data-sl-panel][hidden]{display:none !important;}"
            ".sl-top{display:flex;align-items:center;gap:8px;margin:0 0 6px;padding-left:6px;}"
            ".sl-day{font-size:14px;line-height:20px;color:#6B7280;}"
            "[data-sl-watch] [data-row-link]{-webkit-touch-callout:none;-webkit-user-select:none;user-select:none;}"
            "[data-sl-editing] [data-sl-watch] [data-sl-rm]{display:inline-block !important;}"
            "[data-sl-editing] [data-sl-watch] [data-sl-grip]{display:inline-flex !important;}"
            "[data-sl-editing] [data-sl-watch] [data-sl-price]{display:none !important;}"
            "[data-sl-editing] [data-sl-watch] [data-row-link]{cursor:default;}"
            "[data-sl-editing] [data-sl-foot]{visibility:hidden;}"
            "[data-sl-watch] .sl-drag{background:#F8FAFC;box-shadow:0 4px 14px rgba(15,23,42,.12);position:relative;z-index:2;}"
            "[data-sl-bar]{display:none;position:fixed;left:0;right:0;bottom:0;z-index:50;gap:10px;padding:10px 16px calc(10px + env(safe-area-inset-bottom));background:#fff;border-top:1px solid #E2E8F0;box-sizing:border-box;}"
            "[data-sl-editing] [data-sl-bar]{display:flex;}"
            ".sl-bar-btn{flex:1 1 0;height:48px;border-radius:8px;border:1px solid #CBD5E1;background:#fff;color:#111;font:inherit;font-size:16px;line-height:24px;font-weight:700;cursor:pointer;}"
            ".sl-bar-main{background:#111;border-color:#111;color:#fff;}"
            "[data-sl-editing] .sl-toast{bottom:calc(84px + env(safe-area-inset-bottom)) !important;}"
            ".sl-pop{position:fixed;left:0;right:0;top:-100px;bottom:-100px;z-index:1000;display:flex;justify-content:center;align-items:center;padding:100px 16px;box-sizing:border-box;background:rgba(15,23,42,.45);}"
            ".sl-pop.sl-top-pop{align-items:flex-start;padding-top:calc(100px + 6vh);}"
            ".sl-pop>div{width:100%;max-width:520px;max-height:min(640px,80vh);display:flex;flex-direction:column;background:#fff;border-radius:12px;overflow:hidden;}"
            ".sl-pop.sl-short>div{max-width:400px;}"
            ".sl-pop-head{flex:none;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 12px 12px 18px;border-bottom:1px solid #E2E8F0;font-size:19px;line-height:28px;font-weight:700;color:#111;}"
            ".sl-x{flex:none;width:32px;height:32px;border:1px solid #E2E8F0;border-radius:8px;background:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0;}"
            ".sl-x:hover{border-color:#111;}"
            ".sl-pop-body{flex:1 1 auto;overflow:auto;padding:14px 18px 18px;}"
            ".sl-q{width:100%;box-sizing:border-box;height:44px;border:1px solid #CBD5E1;border-radius:8px;padding:0 12px 0 38px;font:inherit;font-size:16px;color:#111;background:#fff url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Ccircle cx='8.5' cy='8.5' r='5.5' fill='none' stroke='%239CA3AF' stroke-width='1.8'/%3E%3Cpath d='M13 13l4 4' stroke='%239CA3AF' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E\") no-repeat 12px 50%/18px;outline:none;}"
            ".sl-q:focus{border-color:#111;}"
            ".sl-res-h{font-size:15px;line-height:22px;font-weight:700;color:#111;margin:18px 0 4px;}"
            ".sl-res{display:flex;align-items:center;gap:10px;padding:12px 0;cursor:pointer;-webkit-tap-highlight-color:transparent;}"
            ".sl-res+.sl-res{border-top:1px solid #E2E8F0;}"
            ".sl-res-star{flex:none;width:32px;height:32px;display:flex;align-items:center;justify-content:center;margin-left:auto;color:#9CA3AF;}"
            ".sl-res-star[aria-pressed=\"true\"]{color:" + STAR + ";}"
            ".sl-joined{gap:0 !important;padding:0 !important;margin:0 0 12px;}"
            ".sl-joined .seg{flex:1 0 auto;padding:6px 14px;border:1px solid #E2E8F0;border-radius:0;background:#fff;color:var(--gray-600);font-weight:400;text-align:center;}"
            ".sl-joined .seg+.seg{border-left:0;}.sl-joined .seg:first-child{border-radius:7px 0 0 7px;}.sl-joined .seg:last-child{border-radius:0 7px 7px 0;}"
            ".sl-joined .seg:only-child{border-radius:7px;}"
            ".sl-joined .seg[aria-selected=\"true\"]{background:#fff;color:#111;font-weight:700;box-shadow:inset 0 0 0 1px #111;}"
            ".hm{position:relative;margin:0 0 14px;background:#fff;}"
            ".hm-c{position:absolute;box-sizing:border-box;margin:0;padding:4px;border:" + str(HEAT_GAP) + "px solid #fff;border-radius:6px;font:inherit;cursor:pointer;"
            "display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;overflow:hidden;text-align:center;-webkit-tap-highlight-color:transparent;}"
            ".hm-n{display:block;max-width:100%;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}"
            ".hm-p{display:block;font-weight:400;white-space:nowrap;}"
            ".hm-c[aria-selected=\"true\"]{box-shadow:inset 0 0 0 1.5px var(--hm-fg);}"   # 고른 칸 = 칸 글자와 같은 방향 색 테두리 1.5 (2026-11-18 사용자 2안 · 굵기 1.5, 옛 검정 2)
            ".hm-c:active{filter:brightness(.94);}"
            ".cp-pills{margin:0 0 12px;}"
            ".sl-title-day{flex:none;font-size:13px;line-height:19px;font-weight:400;color:#6B7280;white-space:nowrap;letter-spacing:0;}" + TOAST_CSS + "</style>")

PAGE_JS = """<script>(function(){
document.querySelectorAll('[data-sl-pills]').forEach(function(row){var k=row.getAttribute('data-sl-pills');
 row.querySelectorAll('[data-sl-pill]').forEach(function(b){b.addEventListener('click',function(){var i=b.getAttribute('data-sl-pill');
  row.querySelectorAll('[data-sl-pill]').forEach(function(x){x.setAttribute('aria-selected',x===b?'true':'false');});
  document.querySelectorAll('[data-sl-panel^="'+k+':"]').forEach(function(p){p.hidden=p.getAttribute('data-sl-panel')!==k+':'+i;});});});});
document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('[data-mock]');if(a)e.preventDefault();});
var td=document.querySelector('[data-sl-title-day]'),meta=document.querySelector('.post-title .post-title-meta')||document.querySelector('.post-title');
if(td&&meta){var sp=document.createElement('span');sp.className='sl-title-day';sp.textContent=td.getAttribute('data-sl-title-day');meta.insertBefore(sp,meta.firstChild);}
})();</script>"""


# 관심 탭 편집 · 검색 담기 (2026-11-17 사용자: 편집 버튼 없이 편집 모드 · 순서 바꾸기 · 전체 삭제 · 검색해서 바로 담기 · 100개)
WATCH_JS = """<script>(function(){
var W=document.querySelector('[data-sl-watch]'),D=document.getElementById('sl-data');if(!W||!D)return;
var J=JSON.parse(D.textContent),C=J.cfg,BY={};J.rows.forEach(function(r){BY[r.s]=r;});
var held=C.held.slice(),L=W.querySelector('[data-sl-list]'),body=document.body;
function rowsEl(){return [].slice.call(L.children);}
function mine(){return rowsEl().map(function(x){return x.getAttribute('data-sym');});}
function all(){var a=held.slice();mine().forEach(function(s){if(a.indexOf(s)<0)a.push(s);});return a;}
/* 업종 탭 (2026-11-18 사용자): 오늘 움직임과 같은 묶음 줄 `전체 · 기술 · 경기 소비재 …`(담은 개수 많은 순). 칸 나누기 시안은 지저분해 접음.
   누르면 그 업종 종목만, 담기 · 빼기 때마다 다시 그린다 */
var cur='';
function secOf(x){var r=BY[x.getAttribute('data-sym')];return r?r.sec:'기타';}
function comp(){var box=W.querySelector('[data-sl-comp]'),cnt={},ks=[],n=rowsEl().length;
 rowsEl().forEach(function(x){var k=secOf(x);if(!cnt[k]){cnt[k]=0;ks.push(k);}cnt[k]++;});
 ks.sort(function(a,b){return cnt[b]-cnt[a];});if(cur&&!cnt[cur])cur='';
 if(ks.length<2){cur='';box.innerHTML='';return;}   /* 업종 둘 이상일 때만 (2026-11-19 사용자) */
 function pill(k,t){return '<button class="seg" type="button" data-comp="'+esc(k)+'" aria-selected="'+(cur===k)+'">'+t+'</button>';}
 box.innerHTML='<div class="seg-row sl-joined cp-pills">'+pill('','전체')+ks.map(function(k){return pill(k,esc(k));}).join('')+'</div>';}
function seps(){comp();var vis=rowsEl().filter(function(x){var on=!cur||secOf(x)===cur;x.style.display=on?'flex':'none';return on;});
 vis.forEach(function(x,i){x.style.borderTop=i?'1px solid #E2E8F0':'0';x.style.paddingTop=(i?C.pad:C.top)+'px';});var n=rowsEl().length;
 L.parentNode.hidden=!n;W.querySelector('[data-sl-has]').hidden=!n;W.querySelector('[data-sl-empty]').hidden=!!n;if(!n)edit(false);}
W.addEventListener('click',function(e){var b=e.target.closest('[data-comp]');if(!b)return;cur=b.getAttribute('data-comp');seps();});
seps();
function edit(on){if(on)body.setAttribute('data-sl-editing','');else body.removeAttribute('data-sl-editing');}
function toast(msg){var o=document.querySelector('.sl-toast');if(o)o.remove();var d=document.createElement('div');d.className='sl-toast';d.innerHTML='<span>'+msg+'</span>';body.appendChild(d);setTimeout(function(){d.remove();},2600);}
function esc(t){return String(t).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function badge(r,z){z=z||22;return '<span aria-hidden="true" style="display:inline-block;width:'+z+'px;height:'+z+'px;border-radius:50%;margin-right:6px;line-height:'+z+'px;background:#2F6F68;color:#fff;font-size:'+Math.max(9,Math.round(z*.42))+'px;font-weight:700;text-align:center;">'+esc(/^[0-9]/.test(r.c)?r.n.slice(0,1):r.c.replace(/[-.]/g,'').slice(0,2))+'</span>';}
function pct(v){if(v==null)return '<span style="color:'+C.muted+';">—</span>';var col=v>0?C.up:v<0?C.down:C.muted,t=v>0?'▲':v<0?'▼':'';
 return '<span style="color:'+col+';font-weight:700;white-space:nowrap;">'+(t?'<span style="font-size:'+Math.round(C.chg*.8)+'px;vertical-align:1px;margin-right:2px;">'+t+'</span>':'')+Math.abs(v).toFixed(2)+'%</span>';}
function rowHtml(r){return '<span data-row-link="1" data-href="#" data-sym="'+esc(r.s)+'" style="'+C.row+'align-items:flex-start;">'+C.rm.replace('{name}',esc(r.n))+
 '<span style="display:flex;align-items:center;min-width:0;flex:1 1 auto;"><span style="flex:none;display:flex;align-items:center;">'+badge(r,C.logo).replace('margin-right:6px','margin-right:'+C.gap+'px')+'</span>'+
 '<span style="min-width:0;"><span style="display:block;font-size:16px;line-height:24px;font-weight:700;color:#111;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'+esc(r.n)+'</span>'+
 '<span style="display:block;font-size:14px;line-height:20px;color:'+C.note+';white-space:nowrap;">'+(r.m==='kr'?'':esc(r.c)+' · ')+esc(r.sec)+'</span></span></span>'+
 '<span data-sl-price style="flex:none;display:flex;flex-direction:column;align-items:flex-end;white-space:nowrap;"><span style="font-size:'+C.chg+'px;line-height:24px;">'+pct(r.r)+'</span><span style="font-size:15px;line-height:20px;color:'+(r.r>0?C.up:r.r<0?C.down:'#111')+';">'+esc(r.p)+'</span></span>'+C.grip+'</span>';}
function add(s){var r=BY[s];if(!r)return false;var a=all();if(a.indexOf(s)>=0)return true;
 if(a.length>=C.max){toast('관심 종목은 '+C.max+'개까지 담을 수 있습니다');return false;}
 if(r.m===C.m){L.insertAdjacentHTML('beforeend',rowHtml(r));seps();}else{held.push(s);}
 toast(r.m===C.m?'관심 종목에 담았습니다':(r.m==='kr'?'한국':'미국')+' 화면 관심 종목에 담았습니다');return true;}
function drop(s){held=held.filter(function(x){return x!==s;});var e=L.querySelector('[data-sym="'+s+'"]');if(e)e.remove();seps();}

/* ① 길게 누르기(0.5초) = 편집 모드 */
var T=0,sx=0,sy=0,eat=false;
W.addEventListener('pointerdown',function(e){if(body.hasAttribute('data-sl-editing'))return;var row=e.target.closest('[data-sl-list] [data-row-link]');if(!row)return;
 sx=e.clientX;sy=e.clientY;clearTimeout(T);T=setTimeout(function(){T=0;eat=true;row.classList.remove('is-pressed');edit(true);if(navigator.vibrate)navigator.vibrate(12);},500);});
W.addEventListener('pointermove',function(e){if(T&&(Math.abs(e.clientX-sx)>8||Math.abs(e.clientY-sy)>8)){clearTimeout(T);T=0;}});
['pointerup','pointercancel','pointerleave'].forEach(function(k){W.addEventListener(k,function(){if(T){clearTimeout(T);T=0;}});});
W.addEventListener('contextmenu',function(e){if(e.target.closest('[data-sl-list]'))e.preventDefault();});
/* 편집 중 · 길게 누른 직후 = 줄 이동 막기, 빼기 버튼 */
document.addEventListener('click',function(e){var t=e.target;
 if(eat&&t.closest('[data-sl-list]')){eat=false;e.preventDefault();e.stopPropagation();return;}eat=false;
 var x=t.closest('[data-sl-rm]');if(x){e.preventDefault();e.stopPropagation();drop(x.closest('[data-sym]').getAttribute('data-sym'));return;}
 if(body.hasAttribute('data-sl-editing')&&t.closest('[data-sl-list] [data-row-link]')){e.preventDefault();e.stopPropagation();}},true);
/* ② 목록 끝 `편집` */
W.querySelectorAll('[data-sl-edit]').forEach(function(b){b.addEventListener('click',function(){edit(true);});});
document.querySelector('[data-sl-done]').addEventListener('click',function(){edit(false);});

/* 끌어서 순서 바꾸기(≡) */
L.addEventListener('pointerdown',function(e){var g=e.target.closest('[data-sl-grip]');if(!g||!body.hasAttribute('data-sl-editing'))return;e.preventDefault();
 var row=g.closest('[data-row-link]');row.classList.add('sl-drag');try{g.setPointerCapture(e.pointerId);}catch(_){}
 function mv(ev){var after=null,rs=rowsEl();for(var i=0;i<rs.length;i++){if(rs[i]===row)continue;var b=rs[i].getBoundingClientRect();if(ev.clientY<b.top+b.height/2){after=rs[i];break;}}
  if(after!==row.nextSibling||!after){L.insertBefore(row,after);seps();}}
 function up(){row.classList.remove('sl-drag');g.removeEventListener('pointermove',mv);g.removeEventListener('pointerup',up);g.removeEventListener('pointercancel',up);}
 g.addEventListener('pointermove',mv);g.addEventListener('pointerup',up);g.addEventListener('pointercancel',up);});

/* 팝업 공통 틀 (가이드라인 팝업: 흰 상자 12 · 가림막 · 닫기 네모 32 · 바깥 · Esc) */
var X='<svg viewBox="0 0 14 14" width="14" height="14" aria-hidden="true"><path d="M2 2l10 10M12 2 2 12" stroke="#111" stroke-width="2" stroke-linecap="round"/></svg>';
function pop(title,inner,cls){var o=document.createElement('div');o.className='sl-pop '+(cls||'');
 o.innerHTML='<div role="dialog" aria-modal="true"><div class="sl-pop-head"><span>'+title+'</span><button type="button" class="sl-x" aria-label="닫기">'+X+'</button></div><div class="sl-pop-body">'+inner+'</div></div>';
 function close(){o.remove();document.removeEventListener('keydown',k);}function k(e){if(e.key==='Escape')close();}
 o.addEventListener('click',function(e){if(e.target===o||e.target.closest('.sl-x'))close();});document.addEventListener('keydown',k);body.appendChild(o);o.close=close;return o;}

/* 전체 삭제 = 확인 창 */
document.querySelector('[data-sl-clear]').addEventListener('click',function(){var n=rowsEl().length;if(!n)return;
 var o=pop('관심 종목을 모두 뺄까요?','<p style="margin:0 0 18px;font-size:16px;line-height:26px;color:#333;word-break:keep-all;">이 화면 관심 종목 '+n+'개가 목록에서 빠집니다.</p>'+
  '<div style="display:flex;gap:10px;"><button type="button" class="sl-bar-btn" data-c>취소</button><button type="button" class="sl-bar-btn sl-bar-main" data-ok>모두 빼기</button></div>','sl-short');
 o.querySelector('[data-c]').onclick=o.close;o.querySelector('[data-ok]').onclick=function(){mine().forEach(drop);o.close();toast('관심 종목을 모두 뺐습니다');};});

/* 종목 추가 = 검색 팝업, 줄 누르면 ☆ ↔ ★ */
function star(on){return '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="'+C.starPath+'" fill="'+(on?'currentColor':'none')+'" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>';}
function res(r){var on=all().indexOf(r.s)>=0;return '<div class="sl-res" data-s="'+esc(r.s)+'">'+badge(r)+'<span style="min-width:0;"><span style="display:block;font-size:16px;line-height:24px;font-weight:700;color:#111;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'+esc(r.n)+'</span>'+
 '<span style="display:block;font-size:14px;line-height:20px;color:'+C.note+';white-space:nowrap;">'+(r.m==='kr'?'':esc(r.c)+' · ')+esc(r.sec)+(r.m!==C.m?' · '+(r.m==='kr'?'한국':'미국'):'')+'</span></span>'+
 '<span class="sl-res-star" role="button" aria-pressed="'+on+'" aria-label="'+(on?'관심 종목에서 빼기':'관심 종목에 담기')+'">'+star(on)+'</span></div>';}
function find(q){q=q.trim().toLowerCase();if(!q)return null;var a=[],b=[];J.rows.forEach(function(r){var n=r.n.toLowerCase(),c=r.c.toLowerCase();
 if(n.indexOf(q)===0||c.indexOf(q)===0)a.push(r);else if(n.indexOf(q)>0||c.indexOf(q)>0)b.push(r);});
 var k=function(x,y){return ((x.m===C.m?0:1)-(y.m===C.m?0:1))||(y.k-x.k);};return a.sort(k).concat(b.sort(k)).slice(0,30);}
W.querySelectorAll('[data-sl-add]').forEach(function(b){b.addEventListener('click',function(){
 var o=pop('관심 종목 추가','<input class="sl-q" type="search" placeholder="종목 이름 · 코드" autocomplete="off" enterkeyhint="search"><div data-out></div>','sl-top-pop'),q=o.querySelector('.sl-q'),out=o.querySelector('[data-out]');
 function draw(){var xs=find(q.value);if(xs===null){var rc=C.recent.map(function(s){return BY[s];}).filter(function(r){return r&&r.m===C.m;});
   out.innerHTML=rc.length?'<div class="sl-res-h">최근 본 종목</div>'+rc.map(res).join(''):'';return;}
  out.innerHTML=xs.length?'<div style="height:6px;"></div>'+xs.map(res).join(''):'<p style="margin:18px 0 0;font-size:15px;line-height:22px;color:'+C.note+';">찾는 종목이 없습니다.</p>';}
 q.addEventListener('input',draw);draw();setTimeout(function(){q.focus();},30);
 out.addEventListener('click',function(e){var r=e.target.closest('.sl-res');if(!r)return;var s=r.getAttribute('data-s'),on=all().indexOf(s)>=0;
  if(on){drop(s);toast('관심 종목에서 뺐습니다');}else add(s);
  var now=all().indexOf(s)>=0,st=r.querySelector('.sl-res-star');st.setAttribute('aria-pressed',now);st.innerHTML=star(now);});});});
})();</script>"""


def day_text(d, m):
    """증시 시황 기준 줄과 같은 꼴 `11.19 한국 종가` · `11.18 미국 종가`(미국 = 미국 장 날짜) (2026-11-19 사용자)."""
    return f"{int(d[5:7])}.{d[8:10]} {'미국' if m == 'us' else '한국'} 종가"


def page(rows, etf, state, m, stats, tab):
    """한 나라만 — 나라는 페이지 안 버튼이 아니라 들어온 쪽(헤더 국기 스위치가 적는 as-home-mkt, 하단 `종목` 칸이 #m= 로 넘김)으로 정한다 (2026-11-17 사용자).
    다른 나라를 보려면 헤더 국기 스위치로 그 나라 홈 → `종목`."""
    day = max(r["d"] for r in rows.values() if r["m"] == m)
    # 소개 문장 삭제 · 기준일은 제목 줄 오른쪽(공유 버튼 앞) — 테마 JS 가 제목 줄(.post-title-meta)로 옮긴다 (2026-11-17 사용자)
    top = f'<span data-sl-title-day="{attr(day_text(day, m))}" hidden></span>'
    # 빈 머리 표시 — 테마 탭 장치는 `첫 data-cards/data-lead 부터 첫 h2 전까지`를 첫 탭 머리로 옮긴다. 없으면 관심 탭 안 카드가 걸려 알약 줄 위로 올라갔다
    body = (top + '<span data-lead="1" hidden></span>'
            + dk.h2("관심", tab="관심") + watch_tab(rows, state, m)
            + dk.h2("오늘 움직임", tab="오늘 움직임") + move_tab(rows, m, stats)
            + dk.h2("테마", tab="테마") + theme_tab(rows, m)
            + dk.h2("업종", tab="업종") + sector_tab(rows, m)
            + dk.h2("시가총액", tab="시가총액") + cap_tab(rows, m)
            + dk.h2("ETF", tab="ETF") + etf_tab(etf, m))
    hash_js = f"<script>if(!/#tab-/.test(location.hash))history.replaceState(null,'',location.pathname+location.search+'#tab-{tab}');</script>"
    return hash_js + PAGE_CSS + body


def tab_star():
    """관심 탭 이름 앞 노란 별 — 실제 페이지(stock_lists.js tabStar · publish_stock_lists_page CSS)를 그대로 떼어 붙인다 (2026-11-19 사용자: 모든 목업에 같게)."""
    js = open(os.path.join(HERE, "stock_lists.js"), encoding="utf-8").read()
    pub = open(os.path.join(HERE, "publish_stock_lists_page.py"), encoding="utf-8").read()
    m = re.search(r"  \(function tabStar\(\) \{.*?\n  \}\)\(\);", js, re.S)
    c = re.search(r'"(\.post-body \.rt-tab \.sl-tab-star\{[^"]*)"', pub)
    if not (m and c):
        print("[종목 목록] 관심 탭 별 코드를 못 찾음 — 목업에 별 없음")
        return ""
    return f"<style>{c.group(1)}</style><script>\n{m.group(0)}\n</script>"


def write(body, name, title="종목 모아보기"):   # 옛 `종목` (2026-11-18 사용자 "제목을 좀 더")
    path = dk.write_mock(dk.align_titles(dk.WRAP_OPEN + body + dk.WRAP_CLOSE), os.path.join(OUT, name), title)
    if path:
        pg = open(path, encoding="utf-8").read().replace("</body>", PAGE_JS + WATCH_JS + tab_star() + "</body>", 1)
        open(path, "w", encoding="utf-8").write(pg)
    print(f"[종목 목록] {name}")


# ── 종목 상세 ☆ ──────────────────────────────────────────────────────
STAR_JS = """<style>/* 별 아래 끝 = 종목 이름 글자 아래선 (2026-11-19 사용자: 별이 위로 떠 보임 — 3배 캡처 실측 3px 아래로 → 2px 다시 올림 = 1px, 사용자) */.sl-star{display:inline-flex;flex:none;align-items:center;justify-content:center;width:22px;height:22px;margin:0 0 0 5px;position:relative;top:1px;vertical-align:middle;padding:0;border:0;background:none;cursor:pointer;color:#9CA3AF;-webkit-tap-highlight-color:transparent;}
.sl-star svg{width:22px;height:22px;display:block;}.sl-star[aria-pressed="true"]{color:%(star)s;}
%(toast)s</style>
<script>(function(){
var LINK='%(link)s',on=false,P='%(path)s';   /* 로그인 없이 바로 담기 — 실제는 이 브라우저 localStorage (2026-11-19 사용자) */
var t=document.querySelector('.pr-sticky .post-title')||document.querySelector('.post-title');if(!t)return;
var b=document.createElement('button');b.type='button';b.className='sl-star';b.setAttribute('aria-pressed','false');b.setAttribute('aria-label','관심 종목에 담기');
function draw(){b.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="'+P+'" fill="'+(on?'currentColor':'none')+'" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>';
 b.setAttribute('aria-pressed',on?'true':'false');b.setAttribute('aria-label',on?'관심 종목에서 빼기':'관심 종목에 담기');}
draw();
var lab=t.querySelector('.post-title-label'),sub=lab&&lab.querySelector('.post-title-sub');if(sub)lab.insertBefore(b,sub);else if(lab)lab.appendChild(b);else t.appendChild(b);
function toast(msg,link){var o=document.querySelector('.sl-toast');if(o)o.remove();var d=document.createElement('div');d.className='sl-toast';
 d.innerHTML='<span>'+msg+'</span>'+(link?'<a href="'+LINK+'#tab-0">관심 목록 보기</a>':'');document.body.appendChild(d);setTimeout(function(){d.remove();},3000);}
b.addEventListener('click',function(){
 on=!on;draw();toast(on?'관심 종목에 담았습니다':'관심 종목에서 뺐습니다',on);});
})();</script>"""


def star_mock(src_rel, name, link):
    src = os.path.join(EXP, src_rel)
    if not os.path.exists(src):
        print(f"[종목 목록] {src_rel} 없음 — {name} 건너뜀")
        return
    pg = open(src, encoding="utf-8").read()   # ☆ 는 이제 테마 JS 가 그린다(2026-11-19 적용) — 종목 목업을 그대로 복사, 따로 끼우지 않음
    open(os.path.join(OUT, name), "w", encoding="utf-8").write(pg)
    print(f"[종목 목록] {name} (← {src_rel})")


def main():
    os.makedirs(OUT, exist_ok=True)
    rows, etf = load()
    extra_rows(rows, [x for _, syms in U.WATCH_NEXT for x in syms])
    print(f"[종목 목록] 종목 미국 {sum(r['m'] == 'us' for r in rows.values())} · 한국 {sum(r['m'] == 'kr' for r in rows.values())} · ETF {len(etf['us'])} + {len(etf['kr'])}"
          f" · 시총 값 미국 {sum(1 for r in rows.values() if r['m'] == 'us' and r['cap'])} · 한국 {sum(1 for r in rows.values() if r['m'] == 'kr' and r['cap'])}")
    stats = []
    write(page(rows, etf, "watch", "us", [], 0), "mock_stock-lists-watch.html")
    write(page(rows, etf, "watch", "kr", [], 0), "mock_stock-lists-watch-kr.html")
    write(page(rows, etf, "empty", "us", stats, 0), "mock_stock-lists-empty.html")
    star_mock("stock-radar/output/mock_NVDA.html", "mock_stock-star-us.html", "mock_stock-lists-watch.html")
    star_mock("kr-stocks/output/mock_000660.html", "mock_stock-star-kr.html", "mock_stock-lists-watch-kr.html")
    for old in ("mock_stock-lists-guest-us.html", "mock_stock-lists-guest-kr.html", "mock_stock-lists-member.html", "mock_stock-lists-member-kr.html",
                "mock_stock-lists-member-empty.html", "mock_stock-star-member.html", "mock_stock-star-guest.html"):   # 로그인 전제 옛 목업 (2026-11-19 브라우저 저장으로 바꿈)
        if os.path.exists(os.path.join(OUT, old)):
            os.remove(os.path.join(OUT, old))
    for m, n, k in stats:
        print(f"  {m} {n}: {k}종목")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
