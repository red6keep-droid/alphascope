"""하단 메뉴 `종목` → 묶음 탭 목록 목업 (2026-11-17 사용자 "추천대로 진행해서 목업") — 비공개 기획 `doc/기획/종목-탭-그룹-목록-기획.md`.

    python experiments/stock-lists/mock_stock_lists.py   → output/mock_stock-lists-*.html · mock_stock-star-*.html (목업 서버 `stock-lists` 묶음)

화면:
  mock_stock-lists-guest-us.html    로그인 전 · 미국 · `오늘 움직임` 탭으로 열림(관심 종목이 없으면 첫 탭 = 오늘 움직임)
  mock_stock-lists-guest-kr.html    로그인 전 · 한국 · `테마` 탭
  mock_stock-lists-member.html      로그인 · 관심 종목 담음 → `관심` 탭(담은 순 · 등락 순 · 편집)
  mock_stock-lists-member-empty.html 로그인 · 아직 안 담음
  mock_stock-star-member.html       종목 상세(엔비디아) 제목 옆 ☆ — 누르면 담기 · 알림 줄
  mock_stock-star-guest.html        종목 상세(SK하이닉스) 로그인 전 ☆ — 누르면 로그인 안내
별(☆)은 종목 상세 페이지 제목의 종목 이름 바로 뒤(회색 `주가 실적 일정` 앞)에만 둔다(2026-11-17 사용자). 목록 줄에는 없다 — 줄 전체가 링크라 잘못 누르기 쉽다. 빼기는 관심 탭 `편집`.

데이터 = 실제 값, 인터넷 · AI 0:
  간단 종목 853 = 원격 브랜치 quick-us · quick-kr 의 <코드>.json(운영 실행이 이미 올린 가격 요약, `git fetch origin quick-us quick-kr` 뒤)
  정식 종목 · ETF = gh-pages search/us.json · kr.json(브랜치에서 읽음) — S&P 500 밖 정식 종목(TSM · 아이온큐 등)과 미국 시가총액
  한국 시가총액 = ref/universe_all.json. 미국 간단 종목은 시가총액 값이 없다 → 목업 `시가총액` 탭 미국은 값 있는 종목만(구현 = SEC 주식 수 × 종가, 기획 3-1).
"""
import html
import json
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

OUT = os.path.join(HERE, "output")
BLOG = "https://alpha-scope.blogspot.com"
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
WATCH = ["NVDA", "005930.KS", "TSLA", "000660.KS", "IONQ", "PLTR", "373220.KS", "AAPL"]
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
            rows[d["s"]] = {"s": d["s"], "n": d["n"], "m": m, "sec": d.get("sec") or "기타", "f": bool(d.get("full")),
                            "c": d["c"], "r": (d.get("chg") or {}).get("1d"), "v": d.get("vol_ratio"), "h": d.get("off_hi"), "d": d["d"], "cap": None}
    etf = {"us": [], "kr": []}
    for m in ("us", "kr"):
        idx = json.loads(git_show(f"origin/gh-pages:search/{m}.json") or b"{}")
        for s in idx.get("stocks", []):
            p = s["p"]
            row = rows.get(s["s"]) or {"s": s["s"], "n": s["n"], "m": m, "sec": s.get("sec") or "기타", "f": True, "c": p["c"], "r": p.get("chg"),
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


# ── 화면 조각 ────────────────────────────────────────────────────────
def pct_html(v, px=15, bold=True):
    if v is None:
        return f'<span style="color:{dk.MUTED};">—</span>'
    col = dk.UP if v > 0 else dk.DOWN if v < 0 else dk.MUTED
    tri = "▲" if v > 0 else "▼" if v < 0 else ""
    t = f'<span style="font-size:{round(px * 0.8)}px;vertical-align:1px;margin-right:2px;">{tri}</span>' if tri else ""
    return f'<span style="color:{col};white-space:nowrap;{"font-weight:700;" if bold else ""}">{t}{abs(v):.2f}%</span>'


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


def row_html(r, i, sub=None, right_sub=None, rank=None, chips=""):
    """종목 줄 — 지금 목록 페이지 줄(list_row)과 같은 짜임: [순위] 로고 이름(굵게 16) / 회색 보조 줄 · 오른쪽 가격 / 등락. 줄 전체 = 종목 페이지."""
    sub = sub if sub is not None else f"{code(r)} · {r['sec']}"
    rk = (f'<span style="flex:none;width:26px;color:{dk.NOTE};font-weight:700;font-size:15px;line-height:24px;">{rank}</span>' if rank else "")
    left = (f'<span style="display:flex;align-items:flex-start;min-width:0;flex:1 1 auto;">{rk}'
            f'<span style="flex:none;display:flex;height:24px;align-items:center;">{dk.ticker_logo(r["s"], 22).replace("vertical-align:-4px;", "vertical-align:0;")}</span>'
            f'<span style="min-width:0;"><span style="display:block;font-size:16px;line-height:24px;font-weight:700;color:#111;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{esc(r["n"])}</span>'
            f'<span style="display:block;font-size:{dk.TINY};line-height:{dk.LH_TINY};color:{dk.NOTE};white-space:nowrap;">{sub}</span>{chips}</span></span>')
    rs = right_sub if right_sub is not None else pct_html(r["r"])
    right = (f'<span style="flex:none;display:flex;flex-direction:column;align-items:flex-end;white-space:nowrap;">'
             f'<span style="font-size:15px;line-height:24px;color:#111;">{esc(price_text(r))}</span>'
             f'<span style="font-size:15px;line-height:{dk.LH_TINY};">{rs}</span></span>')
    return (f'<span data-row-link="1" data-href="{attr(r["u"])}" data-sym="{attr(r["s"])}" style="{dk.MULTI_ROW}{"" if i == 0 else dk.MULTI_SEP}align-items:flex-start;">'
            f'{left}{right}</span>')


def list_card(items, render, empty=""):
    """앞에서 10개만, 다 펼침 (TOP)."""
    if not items:
        return empty
    shown = "".join(render(x, i) for i, x in enumerate(items[:TOP]))
    return f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{shown}</span></div>'



def pills(key, names, on=0, joined=False):
    """알약 줄. joined = 홈 `테마 종목` 아래 묶음 줄(#watch-tabs) 모양 — 칸이 붙은 한 줄 상자 (2026-11-17 사용자: 오늘 움직임 · 테마)."""
    return (f'<div class="seg-row{" sl-joined" if joined else ""}" data-sl-pills="{key}" style="padding:0 0 12px;">'
            + "".join(f'<button class="seg" type="button" data-sl-pill="{i}" aria-selected="{"true" if i == on else "false"}">{esc(n)}</button>' for i, n in enumerate(names))
            + "</div>")


def panels(key, bodies, on=0):
    return "".join(f'<div data-sl-panel="{key}:{i}"{"" if i == on else " hidden"}>{b}</div>' for i, b in enumerate(bodies))


def note(t):
    return f'<p style="font-size:13px;line-height:19px;color:{dk.NOTE};margin:4px 0 12px;padding-left:{dk.ALIGN_PX}px;word-break:keep-all;">{esc(t)}</p>'


def info_card(title, text, extra=""):
    return dk.dcard(f'<div style="font-size:17px;line-height:26px;font-weight:700;color:#111;">{esc(title)}</div>'
                    f'<div style="font-size:15px;line-height:24px;color:#333;margin:4px 0 0;word-break:keep-all;">{text}</div>{extra}')


# ── 탭 ──────────────────────────────────────────────────────────────
def move_tab(rows, m, stats):
    xs = [r for r in rows.values() if r["m"] == m and r["r"] is not None]
    groups = [
        ("많이 오름", sorted([r for r in xs if r["r"] >= UP_PCT], key=lambda r: -r["r"]), sorted(xs, key=lambda r: -r["r"]),
         f"오늘 {UP_PCT:.0f}% 넘게 오른 종목이 없습니다. 가장 많이 오른 10개입니다.", None),
        ("많이 내림", sorted([r for r in xs if r["r"] <= DOWN_PCT], key=lambda r: r["r"]), sorted(xs, key=lambda r: r["r"]),
         f"오늘 {abs(DOWN_PCT):.0f}% 넘게 내린 종목이 없습니다. 가장 많이 내린 10개입니다.", None),
        ("거래 급증", sorted([r for r in xs if (r["v"] or 0) >= VOL_X], key=lambda r: -r["v"]), sorted([r for r in xs if r["v"]], key=lambda r: -r["v"]),
         "평소 거래량의 2배를 넘은 종목이 없습니다. 거래가 가장 많이 늘어난 10개입니다.",
         lambda r: f'<span style="color:#333;">평소의 {r["v"]:.1f}배</span> · {pct_html(r["r"], 15, False)}'),
        ("52주 최고가 근처", sorted([r for r in xs if r["h"] is not None and r["h"] >= NEAR_HI], key=lambda r: -r["h"]),
         sorted([r for r in xs if r["h"] is not None], key=lambda r: -r["h"]),
         "52주 최고가에 2% 안으로 다가선 종목이 없습니다. 가장 가까운 10개입니다.",
         lambda r: '<span style="color:#333;">최고가</span>' if r["h"] >= 0 else f'<span style="color:#333;">최고가까지 {abs(r["h"]):.1f}%</span>'),
    ]
    bodies = []
    for name, hit, fallback, empty_text, rsub in groups:
        stats.append((m, name, len(hit)))
        render = lambda r, i, rsub=rsub: row_html(r, i, right_sub=rsub(r) if rsub else None)  # noqa: E731
        if hit:
            bodies.append(list_card(hit, render))
        else:
            bodies.append(note(empty_text) + list_card(fallback, render))
    basis = ("등락률 · 거래량은 마지막 종가 기준입니다. 거래 급증 = 오늘 거래량 ÷ 지난 20거래일 평균, "
             "52주 최고가 근처 = 지난 1년 가장 높은 종가에서 2% 안. 미국 S&P 500 · 한국 코스피 200 · 코스닥 150 종목을 봅니다.")
    return pills(f"move-{m}", [g[0] for g in groups], joined=True) + panels(f"move-{m}", bodies) + note(basis)


def theme_groups(m):
    if m == "us":
        g = [(n, syms) for n, syms in U.WATCH]
        g += [(t["name"], t["members"]) for t in taxonomy.THEMES.values()]
        return g
    return [(n.replace(" · ", "·"), syms) for n, syms in UK.WATCH]


def theme_tab(rows, m):
    groups = [(n, [rows[s] for s in syms if s in rows]) for n, syms in theme_groups(m)]
    groups = [(n, xs) for n, xs in groups if xs]
    bodies = []
    for n, xs in groups:
        up = sum(1 for r in xs if (r["r"] or 0) > 0)
        avg = sum(r["r"] or 0 for r in xs) / len(xs)
        head = (f'<p style="font-size:15px;line-height:24px;color:#333;margin:0 0 10px;padding-left:{dk.ALIGN_PX}px;word-break:keep-all;">'
                f'{len(xs)}종목 중 {up}개 오름 · 평균 {pct_html(avg, 15, False)}</p>')
        link = ""
        if m == "us" and n in ("반도체", "데이터 센터"):
            link = (f'<a href="{BLOG}/p/theme-ai-capex.html" style="display:block;margin:4px 0 12px;padding-left:{dk.ALIGN_PX}px;font-size:15px;line-height:24px;'
                    f'color:#111;font-weight:700;text-decoration:none;">AI 투자 자금 흐름 보기 →</a>')
        bodies.append(head + list_card(sorted(xs, key=lambda r: -(r["r"] or -99)), lambda r, i: row_html(r, i)) + link)
    return pills(f"theme-{m}", [n for n, _ in groups], joined=True) + panels(f"theme-{m}", bodies)


def sector_tab(rows, m):
    by = {}
    for r in rows.values():
        if r["m"] == m:
            by.setdefault(r["sec"], []).append(r)
    order = sorted(by, key=lambda k: -len(by[k]))
    bodies = []
    for k in order:
        xs = sorted(by[k], key=lambda r: -(r["cap"] or 0))
        bodies.append(list_card(xs, lambda r, i: row_html(r, i, sub=f"{code(r)}" + (f" · {cap_text(r)}" if r.get("cap") else ""))))
    return pills(f"sec-{m}", order, joined=True) + panels(f"sec-{m}", bodies)


def cap_tab(rows, m):
    xs = sorted([r for r in rows.values() if r["m"] == m and r.get("cap")], key=lambda r: -r["cap"])
    page = f"{BLOG}/p/{m}-market-cap-top10.html"
    nm = "미국" if m == "us" else "한국"
    return (list_card(xs, lambda r, i: row_html(r, i, sub=f"{code(r)} · {cap_text(r)}", rank=i + 1))
            + f'<a href="{page}" style="display:block;margin:4px 0 12px;padding-left:{dk.ALIGN_PX}px;font-size:15px;line-height:24px;color:#111;font-weight:700;text-decoration:none;">'
              f'{nm} 시가총액 상위 10 종목 페이지 →</a>')


def etf_tab(etf, m):
    xs = etf[m]
    return list_card(xs, lambda r, i: row_html(r, i, sub=esc(r["sec"]))) + note("지수 · 업종을 따라가는 상품입니다. 줄을 누르면 ETF 페이지로 갑니다.")


def watch_rows(rows, syms, edit=True):
    out = []
    for i, s in enumerate(syms):
        r = rows[s]
        h = row_html(r, i, sub=f"{code(r)} · {r['sec']}")   # 실적 발표일 칩 삭제 (2026-11-17 사용자)
        if edit:   # 편집 = 줄 왼쪽에 빼기 버튼(편집일 때만 보임)
            rm = (f'<button type="button" data-sl-rm aria-label="{attr(r["n"])} 빼기" hidden style="flex:none;width:28px;height:28px;margin:0 8px 0 0;border:0;border-radius:50%;'
                  f'background:{dk.DOWN};color:#fff;font-size:18px;line-height:28px;cursor:pointer;">−</button>')
            h = h.replace('align-items:flex-start;">', 'align-items:flex-start;">' + rm, 1)
        out.append(h)
    return out


def watch_tab(rows, state, m):
    """관심 탭 — state: guest · empty · member. 들어온 나라(m) 종목만 (2026-11-17 사용자: 한 나라만, 나라는 홈 국기 버튼으로 들어온 쪽)."""
    if state == "guest":
        recent = [rows[s] for s in RECENT if s in rows and rows[s]["m"] == m]
        login = (f'<a data-mock="1" style="{LOGIN_BTN}margin:14px 0 8px;">{G_LOGO}구글 계정으로 로그인</a>'
                 f'<p style="font-size:13px;line-height:19px;color:{dk.NOTE};text-align:center;margin:0;">댓글에 쓰는 로그인과 같습니다.</p>')
        return (info_card("관심 종목을 모아 보세요",
                          f'종목 페이지 제목 옆 <span style="color:{STAR};">★</span> 를 누르면 여기에 모입니다. 로그인하면 폰 · PC 어디서나 같은 목록을 봅니다.', login)
                + dk.h2("이 기기에서 최근 본 종목", one_line=True)
                + list_card(recent, lambda r, i: row_html(r, i, sub=f"{code(r)} · {r['sec']}"))
                + note("최근 본 종목은 이 브라우저에만 남고 서버로 보내지 않습니다."))
    if state == "empty":
        big = f'<svg viewBox="0 0 24 24" width="40" height="40" aria-hidden="true" style="display:block;margin:0 0 8px;"><path d="{STAR_PATH}" fill="none" stroke="{STAR}" stroke-width="1.6" stroke-linejoin="round"/></svg>'
        return info_card("아직 담은 종목이 없습니다",
                         f'종목 페이지 제목 옆 <span style="color:{STAR};">☆</span> 를 누르면 여기에 모입니다. '
                         '<b>오늘 움직임 · 테마 · 업종</b> 탭에서 종목을 둘러보세요.').replace("<div style=\"font-size:17px", big + "<div style=\"font-size:17px", 1)
    syms = [s for s in WATCH if s in rows and rows[s]["m"] == m]
    edit_btn = ('<button type="button" data-sl-edit style="flex:none;padding:4px 12px;border:1px solid #E2E8F0;border-radius:8px;background:#fff;'
                'font:inherit;font-size:14px;line-height:20px;font-weight:700;color:#111;cursor:pointer;">편집</button>')
    head = (f'<div style="display:flex;align-items:center;gap:8px;margin:0 0 12px;">'
            f'<span style="flex:none;margin-left:auto;font-size:14px;color:{dk.NOTE};">{len(syms)}종목</span>{edit_btn}</div>')
    card = f'<div data-cards="1" style="margin:0 0 8px;"><span data-grid="2" style="{dk.MULTI}">{"".join(watch_rows(rows, syms))}</span></div>'   # 담은 순 하나 — 정렬 버튼 삭제 (2026-11-17 사용자)
    return (head + card
            + note(f"{'한국' if m == 'us' else '미국'} 종목은 {'한국' if m == 'us' else '미국'} 화면에서 보입니다. 미국 · 한국 합쳐 200개까지 담을 수 있습니다."))


# ── 페이지 ───────────────────────────────────────────────────────────
TOAST_CSS = (".sl-toast{position:fixed;left:50%;transform:translateX(-50%);bottom:24px;z-index:60;display:flex;gap:14px;align-items:center;padding:12px 16px;"
             "background:#111;color:#fff;border-radius:10px;font-size:15px;line-height:22px;box-shadow:0 6px 20px rgba(0,0,0,.2);white-space:nowrap;}"
             ".sl-toast a{color:#FCD34D;font-weight:700;text-decoration:none;}"
             "@media (max-width:900px){.sl-toast{bottom:calc(85px + env(safe-area-inset-bottom));}}")
PAGE_CSS = ("<style>[data-sl-panel][hidden]{display:none !important;}"
            ".sl-top{display:flex;align-items:center;gap:8px;margin:0 0 6px;padding-left:6px;}"
            ".sl-day{font-size:14px;line-height:20px;color:#6B7280;}"
            "[data-sl-editing] [data-sl-rm]{display:inline-block !important;}"
            ".sl-joined{gap:0 !important;padding:0 !important;margin:0 0 12px;}"
            ".sl-joined .seg{flex:1 0 auto;padding:6px 14px;border:1px solid #E2E8F0;border-radius:0;background:#fff;color:var(--gray-600);font-weight:400;text-align:center;}"
            ".sl-joined .seg+.seg{border-left:0;}.sl-joined .seg:first-child{border-radius:7px 0 0 7px;}.sl-joined .seg:last-child{border-radius:0 7px 7px 0;}"
            ".sl-joined .seg:only-child{border-radius:7px;}"
            ".sl-joined .seg[aria-selected=\"true\"]{background:#fff;color:#111;font-weight:700;box-shadow:inset 0 0 0 1px #111;}"
            ".sl-title-day{flex:none;font-size:14px;line-height:20px;font-weight:400;color:#6B7280;white-space:nowrap;letter-spacing:0;}" + TOAST_CSS + "</style>")

PAGE_JS = """<script>(function(){
document.querySelectorAll('[data-sl-pills]').forEach(function(row){var k=row.getAttribute('data-sl-pills');
 row.querySelectorAll('[data-sl-pill]').forEach(function(b){b.addEventListener('click',function(){var i=b.getAttribute('data-sl-pill');
  row.querySelectorAll('[data-sl-pill]').forEach(function(x){x.setAttribute('aria-selected',x===b?'true':'false');});
  document.querySelectorAll('[data-sl-panel^="'+k+':"]').forEach(function(p){p.hidden=p.getAttribute('data-sl-panel')!==k+':'+i;});});});});
document.querySelectorAll('[data-sl-edit]').forEach(function(b){b.addEventListener('click',function(){var on=document.body.toggleAttribute('data-sl-editing');b.textContent=on?'완료':'편집';});});
document.addEventListener('click',function(e){var x=e.target.closest&&e.target.closest('[data-sl-rm]');if(!x)return;e.preventDefault();e.stopPropagation();
 var sym=x.closest('[data-sym]').getAttribute('data-sym');document.querySelectorAll('[data-sym="'+sym+'"]').forEach(function(r){r.remove();});},true);
document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('[data-mock]');if(a)e.preventDefault();});
var td=document.querySelector('[data-sl-title-day]'),meta=document.querySelector('.post-title .post-title-meta')||document.querySelector('.post-title');
if(td&&meta){var sp=document.createElement('span');sp.className='sl-title-day';sp.textContent=td.getAttribute('data-sl-title-day');meta.insertBefore(sp,meta.firstChild);}
})();</script>"""


def day_text(d, m):
    return dk.kst_close_day(d, "US" if m == "us" else "KR") + (" 새벽 마감 기준" if m == "us" else " 종가 기준")


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


def write(body, name, title="종목"):
    path = dk.write_mock(dk.align_titles(dk.WRAP_OPEN + body + dk.WRAP_CLOSE), os.path.join(OUT, name), title)
    if path:
        pg = open(path, encoding="utf-8").read().replace("</body>", PAGE_JS + "</body>", 1)
        open(path, "w", encoding="utf-8").write(pg)
    print(f"[종목 목록] {name}")


# ── 종목 상세 ☆ ──────────────────────────────────────────────────────
STAR_JS = """<style>.sl-star{display:inline-flex;flex:none;align-items:center;justify-content:center;width:22px;height:22px;margin:-1px 0 0 5px;vertical-align:middle;padding:0;border:0;background:none;cursor:pointer;color:#9CA3AF;-webkit-tap-highlight-color:transparent;}
.sl-star svg{width:22px;height:22px;display:block;}.sl-star[aria-pressed="true"]{color:%(star)s;}
.sl-sheet{position:fixed;inset:0;z-index:70;display:flex;align-items:flex-end;justify-content:center;background:rgba(15,23,42,.4);}
.sl-sheet>div{width:100%%;max-width:480px;box-sizing:border-box;background:#fff;border-radius:14px 14px 0 0;padding:22px 18px calc(18px + env(safe-area-inset-bottom));}
%(toast)s</style>
<script>(function(){
var STATE='%(state)s',on=false,P='%(path)s';
var t=document.querySelector('.pr-sticky .post-title')||document.querySelector('.post-title');if(!t)return;
var b=document.createElement('button');b.type='button';b.className='sl-star';b.setAttribute('aria-pressed','false');b.setAttribute('aria-label','관심 종목에 담기');
function draw(){b.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="'+P+'" fill="'+(on?'currentColor':'none')+'" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>';
 b.setAttribute('aria-pressed',on?'true':'false');b.setAttribute('aria-label',on?'관심 종목에서 빼기':'관심 종목에 담기');}
draw();
var lab=t.querySelector('.post-title-label'),sub=lab&&lab.querySelector('.post-title-sub');if(sub)lab.insertBefore(b,sub);else if(lab)lab.appendChild(b);else t.appendChild(b);
function toast(msg,link){var o=document.querySelector('.sl-toast');if(o)o.remove();var d=document.createElement('div');d.className='sl-toast';
 d.innerHTML='<span>'+msg+'</span>'+(link?'<a href="mock_stock-lists-member.html#tab-0">관심 목록 보기</a>':'');document.body.appendChild(d);setTimeout(function(){d.remove();},3000);}
b.addEventListener('click',function(){
 if(STATE==='guest'){var s=document.createElement('div');s.className='sl-sheet';
  s.innerHTML='<div><div style="font-size:18px;line-height:26px;font-weight:700;color:#111;">관심 종목은 로그인하면 담을 수 있습니다</div>'+
  '<div style="font-size:15px;line-height:24px;color:#333;margin:6px 0 16px;">담은 종목은 하단 메뉴 <b>종목</b> → <b>관심</b> 탭에 모입니다. 폰 · PC 어디서나 같은 목록입니다.</div>'+
  '<a href="#" data-x style="%(btn)s">%(glogo)s구글 계정으로 로그인</a>'+
  '<button type="button" data-x style="display:block;width:100%%;margin:10px 0 0;padding:10px;border:0;background:none;font:inherit;font-size:15px;color:#6B7280;cursor:pointer;">닫기</button></div>';
  s.addEventListener('click',function(e){if(e.target===s||e.target.closest('[data-x]')){e.preventDefault();s.remove();}});document.body.appendChild(s);return;}
 on=!on;draw();toast(on?'관심 종목에 담았습니다':'관심 종목에서 뺐습니다',on);});
})();</script>"""


def star_mock(src_rel, name, state):
    src = os.path.join(EXP, src_rel)
    if not os.path.exists(src):
        print(f"[종목 목록] {src_rel} 없음 — {name} 건너뜀")
        return
    pg = open(src, encoding="utf-8").read()
    add = STAR_JS % {"star": STAR, "state": state, "path": STAR_PATH, "btn": LOGIN_BTN, "glogo": G_LOGO, "toast": TOAST_CSS}
    pg = pg.replace("</body>", add + "</body>", 1)
    open(os.path.join(OUT, name), "w", encoding="utf-8").write(pg)
    print(f"[종목 목록] {name} (← {src_rel})")


def main():
    os.makedirs(OUT, exist_ok=True)
    rows, etf = load()
    print(f"[종목 목록] 종목 미국 {sum(r['m'] == 'us' for r in rows.values())} · 한국 {sum(r['m'] == 'kr' for r in rows.values())} · ETF {len(etf['us'])} + {len(etf['kr'])}"
          f" · 시총 값 미국 {sum(1 for r in rows.values() if r['m'] == 'us' and r['cap'])} · 한국 {sum(1 for r in rows.values() if r['m'] == 'kr' and r['cap'])}")
    stats = []
    write(page(rows, etf, "guest", "us", stats, 1), "mock_stock-lists-guest-us.html")
    write(page(rows, etf, "guest", "kr", stats, 2), "mock_stock-lists-guest-kr.html")
    write(page(rows, etf, "member", "us", [], 0), "mock_stock-lists-member.html")
    write(page(rows, etf, "member", "kr", [], 0), "mock_stock-lists-member-kr.html")
    write(page(rows, etf, "empty", "us", [], 0), "mock_stock-lists-member-empty.html")
    star_mock("stock-radar/output/mock_NVDA.html", "mock_stock-star-member.html", "member")
    star_mock("kr-stocks/output/mock_000660.html", "mock_stock-star-guest.html", "guest")
    for m, n, k in stats:
        print(f"  {m} {n}: {k}종목")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
