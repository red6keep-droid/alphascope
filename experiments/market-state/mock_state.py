"""시장 상태판 — 목업 (거시 흐름 지도 0-6 `다음 = 상태판 설계`). 11-28 홈 카드 뺌 → 홈은 자리가 바뀐 날만 `오늘 달라진 것` 한 줄.

    .venv/bin/python experiments/market-state/mock_state.py
→ (홈 짧은 카드는 11-28 뺌 — mock_state_home_* 는 휴지통)
  output/mock_state_detail.html (증시 리포트 첫 구획 자리 — 자세히, 미국 · 한국 + 정할 것 A안 · B안)

검증에서 살아남은 축만 판정에 쓴다(비공개 doc/기획/거시-흐름-지도.md 0-4 `검증 일곱 묶음 끝` 표):
  자리(상승 · 하락 · 소강 · 반등 — V8 의 안정 · 회복을 독자 말로) · 신용(하락 자리에서) · 한국만 해외 먼저 꺾임.
  나머지(경기 · 금리 · 업종 폭 · 지정학 · 정책 · 상승 나이 · 좁아짐)는 사실 줄로만.
숫자는 검증 저장소(data/store)에서 바로 계산 — 새 수집 · AI 0. 지난 기록 숫자는 검증 문서 값(HIST).
"""
import html as _h
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "output")
sys.path.insert(0, os.path.join(ROOT, "experiments"))
sys.path.insert(0, os.path.join(ROOT, "experiments", "issue_store"))
sys.path.insert(0, os.path.join(ROOT, "experiments", "kr-market-report"))
import design_kit as dk  # noqa: E402
from normal_range import load_close  # noqa: E402
from cycle_position_check import positions  # noqa: E402
from uncertainty_check import load_index, trailing_pct  # noqa: E402
import main as M  # noqa: E402 — 질문 카드(M._qc) · 묶음(M.C.cards_grid)

NAME = {"상승": "상승", "하락": "하락", "안정": "소강", "회복": "반등"}   # 독자 말 — `안정`은 V8 에서 오히려 더 빠진 쪽이라 오해를 부른다
STEPS = ["상승", "하락", "소강", "반등"]
BASE = {"us": "1990년부터 전체 거래일", "kr": "1997년부터 전체 거래일"}
BASE_N = {"us": "1990년부터의 전체 거래일(9,169일)", "kr": "1997년부터의 전체 거래일(7,237일)"}   # 뒤 여섯 달이 있는 날 — 자료 11-27
CONFIRM = 3   # 10% 선을 사흘 이어서 넘어야 자리를 바꾼다(11-28 사용자 A안)
STEP_NOTE = {"상승": "최고점에서 10% 안", "하락": "사흘 넘게 10% 아래 · 새 최저가", "소강": "새 최저가 없이 20거래일", "반등": "최저가보다 10% 넘게 위"}
FOREIGN = {"^N225": "닛케이", "^HSI": "항셍", "000001.SS": "상하이", "^TWII": "대만", "^GDAXI": "독일", "^STOXX50E": "유로 50"}
SECTORS = {"XLK": "기술", "XLE": "에너지", "XLI": "산업재", "XLF": "금융", "XLV": "헬스케어", "XLY": "임의소비재", "XLP": "필수소비재", "XLU": "유틸리티", "XLB": "소재"}
# 지난 기록 — 검증 문서(비공개 doc/검증/) 값. (여섯 달 뒤 상승 m/n, 비교 대상, 한마디) — 비교 대상 이름은 BASE(헌법 제1조 6항)
HIST = {   # 사흘 규칙(confirm=3)으로 다시 센 값 — results/cycle_position_c3.md (11-28)
    "us": {"상승": ("평소와 같음", "여섯 달 뒤 중앙 +6.1% · 아무 날 +5.7% · 날의 64%가 이 자리", "평소와 같았습니다"),
           "하락": ("16번 중 12번 상승", "여섯 달 뒤 중앙 +15.0% · 아무 날 +5.7%", "막 들어간 날 뒤는 오히려 좋았습니다"),
           "소강": ("7번 중 1번 상승", "7번 중 5번이 10% 넘게 더 빠짐 · 아무 날 22%", "조용해진 뒤가 더 위험했습니다"),
           "반등": ("9번 중 5번 상승", "여섯 달 뒤 중앙 +16.1% · 9번 중 5번은 10% 넘게 빠진 적 있음", "크게 오른 때와 다시 빠진 때로 갈렸습니다")},
    "kr": {"상승": ("평소와 같음", "여섯 달 뒤 중앙 +0.4% · 아무 날 +2.6% · 날의 33%가 이 자리", "평소와 같았습니다"),
           "하락": ("24번 중 15번 상승", "여섯 달 뒤 중앙 +12.6% · 아무 날 +2.6%", "막 들어간 날 뒤는 오히려 좋았습니다"),
           "소강": ("20번 중 14번 상승", "여섯 달 뒤 중앙 +3.1% · 아무 날 +2.6%", "평소와 같았습니다"),
           "반등": ("15번 중 4번 상승", "여섯 달 뒤 중앙 −3.8% · 아무 날 +2.6%", "반등이 다시 꺾인 쪽이 많았습니다")},
}

def esc(s):
    return _h.escape(str(s))


def md(d):
    return f"{d.month}월 {d.day}일"


def tag(label, rec=False):
    """정할 것 이름표 — 목업에서만 (A안 (추천) · B안)."""
    bg, ink = ("#F5F3FF", "#6D28D9") if rec else ("#F1F5F9", "#334155")
    return (f'<span style="display:inline-block;padding:1px 6px;margin:0 6px 0 0;border:1px dashed {ink};border-radius:4px;background:{bg};'
            f'font-size:12px;line-height:18px;font-weight:700;color:{ink};">{esc(label)}</span>')


def strip(cur):
    """자리 네 칸 — 지금 자리만 진하게. 순서 = 되풀이(상승 → 하락 → 소강 → 반등 → 상승)."""
    cells = []
    for s in STEPS:
        on = s == cur
        cells.append(f'<span style="flex:1 1 0;min-width:0;text-align:center;padding:6px 2px;border-radius:6px;'
                     f'background:{"#111" if on else "#fff"};border:1px solid {"#111" if on else "#E2E8F0"};'
                     f'color:{"#fff" if on else "#6B7280"};font-size:15px;line-height:20px;font-weight:{700 if on else 400};">{s}</span>')
    arrow = '<span aria-hidden="true" style="flex:none;color:#CBD5E1;font-size:14px;line-height:20px;">›</span>'
    return f'<div style="display:flex;align-items:center;gap:4px;margin:2px 0 0;">{arrow.join(cells)}</div>'


def strip_notes():
    return ('<div style="display:flex;gap:4px;margin:4px 0 0;">' + "".join(
        f'<span style="flex:1 1 0;min-width:0;text-align:center;font-size:12px;line-height:16px;color:{dk.NOTE};word-break:keep-all;">{esc(STEP_NOTE[s])}</span>'
        for s in STEPS) + '</div>')


# ---------- 계산 ----------
def market(sym, shift_foreign):
    c = load_close(sym)
    vix = load_close("^VIX")
    pos = positions(c, vix, CONFIRM).map(NAME)
    peak = c.cummax()
    i = len(c) - 1
    cur = pos.iloc[-1]
    start = pos.index[-1]
    k = i
    while k > 0 and pos.iloc[k - 1] == cur:
        k -= 1
    start = pos.index[k]
    pk_day = c.index[int(np.argmax(c.values))]
    depth = c.iloc[-1] / peak.iloc[-1] - 1
    below = c < peak * 0.9
    run = 0
    for v in below.values[::-1]:
        if not v:
            break
        run += 1
    # 마지막으로 −10% 아래였던 날 · 그 전 상승의 시작
    last_below = below[below].index[-1] if below.any() else None
    days_below_recent = int(below.iloc[-30:].sum())
    # 하락 안의 최저가
    low_day = None
    if depth < -0.10:
        seg = c[c.index >= start - pd.Timedelta(days=400)]
        seg = seg[seg.index >= (below[~below].index[-1] if (~below).any() else seg.index[0])]
        low_day = seg.idxmin()
    fdd = {}
    for s, nm in FOREIGN.items():
        f = load_close(s)
        d = f / f.rolling(252, min_periods=252).max() - 1
        if shift_foreign:
            d = d[d.index < c.index[-1]]
        fdd[nm] = d.iloc[-1]
    return dict(c=c, pos=pos, cur=cur, start=start, peak_day=pk_day, depth=depth, run_below=run, last_below=last_below,
                days_below_recent=days_below_recent, low_day=low_day, fdd=fdd, asof=c.index[-1])


def credit():
    d = pd.read_csv(os.path.join(ROOT, "data", "store", "fred", "BAA10Y_long.csv"))
    baa = pd.Series(d["value"].astype(float).values, pd.to_datetime(d["day"])).sort_index()
    b60 = baa.iloc[-1] - baa.iloc[-61]
    r = (load_close("HYG") / load_close("IEI")).dropna()
    h60 = r / r.shift(60) - 1
    pct = (h60.dropna() < h60.iloc[-1]).mean()
    return dict(baa=baa.iloc[-1], b60=b60, h60=h60.iloc[-1], hpct=pct, cut10=h60.dropna().quantile(.10), cut20=h60.dropna().quantile(.20))


def worry(idx):
    g = trailing_pct(load_index("gpr_daily", "gpr", 7, idx)).iloc[-1]
    e = trailing_pct(load_index("epu_daily", "epu", 1, idx)).iloc[-1]
    return g, e


def sectors():
    out = {}
    for s, nm in SECTORS.items():
        c = load_close(s)
        out[nm] = c.iloc[-1] / c.iloc[-252:].max() - 1
    return out


# ---------- 카드 ----------
def answer_word(m):
    return f"{m['cur']} 자리"


def first_sentence(m, mk):
    nm = "S&P 500" if mk == "us" else "코스피"
    s = f"{nm}는 최고점({md(m['peak_day'])})보다 {abs(m['depth']) * 100:.1f}% 아래입니다. "
    if m["cur"] == "상승":
        s += "고점에서 10% 안쪽이라 상승 자리입니다."
        if m["days_below_recent"]:
            s += f" {md(m['last_below'])} 하루 10% 선 아래로 내려갔다가 바로 돌아와, 사흘 이어지지 않아 자리는 그대로입니다." if m["days_below_recent"] == 1 else \
                f" 최근 30거래일 중 {m['days_below_recent']}일은 10% 선 아래였지만 사흘 이어지지 않았습니다."
    elif m["cur"] == "하락":
        s += f"{md(m['start'])}부터 하락 자리이고, 최근 20거래일 안에 최저가를 새로 썼습니다."
        if m["low_day"] is not None:
            s = s.replace("최저가를 새로 썼습니다.", f"최저가를 새로 썼습니다({md(m['low_day'])}).")
    elif m["cur"] == "소강":
        s += f"20거래일 넘게 새 최저가가 없고 변동성 지수(VIX)가 25 아래입니다."
    else:
        s += "하락 뒤 최저가보다 10% 넘게 올라온 반등 자리입니다."
    return s


def hist_lines(mk, cur):
    a, b, c = HIST[mk][cur]
    b = b.replace("아무 날", BASE[mk])
    return (f"지난 기록에서 {'미국' if mk == 'us' else '한국'} 증시가 {cur} 자리였을 때는 {c}.", (b.split(" · 날의")[0] if a == "평소와 같음" else a), b)


def detail_card(mk, m, cr, wr, sec):
    nm = "미국 증시는 지금 어디쯤?" if mk == "us" else "한국 증시는 지금 어디쯤?"
    h1, a, b = hist_lines(mk, m["cur"])
    lines = [(first_sentence(m, mk), "plain"), (strip(m["cur"]) + strip_notes(), "html"), (h1, "plain")]
    # 자리마다 지난 기록 네 줄 — 지금 자리는 굵게
    for s in STEPS:
        x, y, z = HIST[mk][s]
        y = y.replace("아무 날", BASE[mk])
        lines.append(("row", f'<span style="{"font-weight:700;" if s == m["cur"] else ""}">{s} 자리{" (지금)" if s == m["cur"] else ""}</span>', x, y))
    # 그래프 — 2년 종가 + 최고점 −10% 선
    c = m["c"].iloc[-504:]
    line = (m["c"].cummax() * 0.9).reindex(c.index)
    lab = [f"{d.year % 100:02d}.{d.month:02d}" if (k > 30 and d.month != c.index[k - 1].month and d.month % 3 == 1) else "" for k, d in enumerate(c.index)]   # 석 달마다 바뀌는 자리만
    chart = dk.trend_card(f"최근 2년 {'S&P 500' if mk == 'us' else '코스피'} · 최고점에서 10% 아래 선", lab,
                          [("S&P 500" if mk == "us" else "코스피", list(c.values), dk.CHART_MAIN, "solid"), ("최고점 −10% 선", list(line.values), dk.CHART_CMP, "guide")],
                          lambda v: f"{v:,.0f}")   # 점이 많으면 끝 값만 · 달 바뀌는 자리만(ends_only 는 날마다 점을 찍어 쓰지 않음)
    lines.append((chart, "html"))
    # 신용 — 판정은 하락 자리에서만, 상승 자리에선 사실
    b60, h60 = cr["b60"], cr["h60"]
    baa_word = "벌어짐" if b60 >= 0.20 else "평온"
    hy_word = "벌어지는 중" if h60 < cr["cut20"] else "평온"
    split = "엇갈림" if baa_word != hy_word.replace("는 중", "") and (baa_word == "평온") != (hy_word == "평온") else baa_word
    lines.append(("row", f"{'' if mk == 'us' else '미국 '}신용 (회사채 · 하이일드 금리차)", split,
                  f"회사채 60일 {b60:+.2f}%p · 하이일드 대리 60일 {h60 * 100:+.1f}% (2007년 뒤 아래 {cr['hpct'] * 100:.0f}%)".replace("-", "−"), "gap"))
    # 해외
    fd = m["fdd"]
    asia = [k for k in ("닛케이", "항셍", "상하이", "대만") if fd[k] < -0.10]
    eu = [k for k in ("독일", "유로 50") if fd[k] < -0.10]
    n_down = sum(v < -0.10 for v in fd.values())
    fword = "아시아 함께 하락" if len(asia) >= 3 and not eu else f"{n_down}곳 하락" if n_down else "평온"
    lines.append(("row", "해외 증시 (52주 고점 대비)", fword, " · ".join(f"{k} {v * 100:.1f}%".replace("-", "−") for k, v in fd.items())))
    if mk == "us":
        down = [k for k, v in sorted(sec.items(), key=lambda kv: kv[1]) if v < -0.10]
        lines.append(("row", "업종 (52주 고점 대비 −10% 아래)", f"9개 중 {len(down)}개", " · ".join(f"{k} {sec[k] * 100:.1f}%".replace("-", "−") for k in down)))
    lines.append(("row", "전쟁 · 정책 걱정 (지난 5년 중)", f"{wr[0] * 100:.0f} · {wr[1] * 100:.0f} 분위", "지정학 위험 지수 · 경제정책 불확실성 지수, 높음 = 80 분위 넘음"))
    if mk == "kr":
        lines.append(("row", "돈의 흐름", "증시에서 돈이 빠져나가나?", "한국 증시 리포트 수급 탭 카드로 이어집니다"))
    lines.append((f"자리는 종가로 정하고, 10% 선을 사흘 이어서 넘어야 바꿉니다. 비교 대상은 {BASE_N[mk]}이고, 같은 자리에 63거래일 넘게 없다가 다시 들어간 날을 한 번으로 셉니다. 지금 상태를 말하며 앞으로의 주가를 말하지 않습니다.", "note"))
    color = "#111" if m["cur"] == "상승" else dk.DOWN
    theme = "neutral" if m["cur"] == "상승" else "negative"
    tip = ("시장이 되풀이하는 네 자리(상승 · 하락 · 소강 · 반등) 중 지금 어디인지 종가로 정합니다\n"
           "· 10% 선을 사흘 이어서 넘어야 자리를 바꿉니다(하루짜리 출렁임은 그대로)\n"
           "· 상승 = 최고점에서 10% 안 · 하락 = 10% 넘게 아래이고 최근 20거래일 안에 새 최저가 · 소강 = 새 최저가 없이 20거래일 넘고 변동성 지수 25 아래 · 반등 = 최저가보다 10% 넘게 위\n"
           "· 신용은 하락 자리에 들어간 뒤 길게 갈지를 가른 축입니다(회사채 금리차가 60일 새 0.20%p 넘게 벌어진 채 시작한 하락 8번 중 4번 길었고, 아닌 하락 13번은 길지 않았습니다)")
    return M._qc(nm, answer_word(m), theme, color, lines, tip=tip, opened=True)


def change_rows():
    """홈 `오늘 달라진 것` 한 줄 — 자리가 바뀐 날에만(바뀌지 않은 날엔 홈에 없음). 예시 = 실제로 자리가 바뀐 최근 날."""
    ex = [("S&P 500 하락 자리로", "2025년 4월 7일", "사흘째 최고점보다 10% 넘게 아래",
           "지난 기록 : 하락 자리에 막 들어간 16번 중 여섯 달 뒤 12번 상승 · 1990년부터의 전체 거래일 75%"),
          ("S&P 500 상승 자리로", "2025년 5월 1일", "사흘째 최고점에서 10% 안",
           "상승 자리 = 1990년부터의 전체 거래일과 같은 범위"),
          ("코스피 하락 자리로", "2026년 10월 15일", "소강 뒤 최저가를 새로 씀",
           "지난 기록 : 하락 자리에 막 들어간 24번 중 여섯 달 뒤 15번 상승 · 1997년부터의 전체 거래일 57%")]
    out = ""
    for what, day, why, cmp_ in ex:
        out += (f'<div style="display:flex;align-items:flex-start;gap:8px;padding:10px 0;border-top:1px solid #EEF2F6;">'
                f'<span style="flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:2px;">'
                f'<span style="display:flex;flex-wrap:wrap;align-items:center;gap:2px 8px;font-size:16px;line-height:24px;">'
                f'<span style="flex:none;padding:1px 6px;border:1px solid #E2E8F0;border-radius:4px;background:#F8FAFC;font-size:12px;line-height:18px;font-weight:600;color:#334155;">상태</span>'
                f'<b style="font-weight:700;word-break:keep-all;">{esc(what)}</b><span>{esc(why)}</span></span>'
                f'<span style="font-size:13px;line-height:19px;color:{dk.SUB};word-break:keep-all;">{esc(cmp_)}</span>'
                f'<span style="font-size:12px;line-height:18px;color:{dk.NOTE};">예시 · 그날 = {esc(day)}</span></span>'
                f'<span aria-hidden="true" style="flex:none;color:#333;font-size:18px;line-height:24px;">›</span></div>')
    return out.replace("border-top:1px solid #EEF2F6;", "", 1)


def guide_box(title, html):
    return (f'<div style="margin:0 0 20px;padding:6px 14px 6px;border:1px dashed #94A3B8;border-radius:8px;background:#fff;">'
            f'<div style="padding:6px 0 8px;font-size:14px;line-height:20px;font-weight:700;color:#334155;">목업 안내 — {esc(title)}</div>{html}</div>')


def main():
    os.makedirs(OUT, exist_ok=True)
    us, kr = market("^GSPC", False), market("^KS11", True)
    cr = credit()
    wr = worry(us["c"].index)
    sec = sectors()
    home = guide_box("홈에는 자리가 바뀐 날에만 · `오늘 달라진 것` 카드의 한 줄로",
                     f'<div style="padding:0 0 8px;font-size:14px;line-height:20px;color:{dk.SUB};word-break:keep-all;">자리는 일부러 천천히 바뀌게 만든 판정이라(10% 선을 사흘 이어서), 홈에 늘 두면 몇 주 · 몇 달 같은 말이 뜹니다. 바뀐 날에만 아래처럼 한 줄 — 바뀌지 않은 날엔 홈에 나오지 않습니다. 누르면 증시 리포트의 이 판으로.</div>'
                     + change_rows())
    place = guide_box("놓일 자리 · 증시 리포트 안", f'<div style="padding:0 0 8px;font-size:14px;line-height:20px;color:{dk.SUB};word-break:keep-all;">미국 · 한국 증시 리포트에서 그날 움직임 구획들 <b>뒤</b>, `큰 흐름` 자리. 리포트를 여는 독자도 먼저 오늘 무엇이 움직였는지를 보고, 그 다음 배경으로 읽습니다.</div>')
    body = (f'<div data-head-title="시장 상태판">'
            + dk.muted("숫자는 11월 27일 종가로 검증 저장소에서 계산했습니다. 점선 상자는 목업에서만 보입니다.")
            + home + place
            + f'<a id="us"></a>' + dk.section("큰 흐름 — 미국 증시는 지금 어디쯤?", M.C.cards_grid(detail_card("us", us, cr, wr, sec)), line=False)
            + f'<a id="kr"></a>' + dk.section("큰 흐름 — 한국 증시는 지금 어디쯤?", M.C.cards_grid(detail_card("kr", kr, cr, wr, sec)), line=False)
            + '</div>')
    p = os.path.join(OUT, "mock_state_detail.html")
    print(dk.write_mock(body, p, "시장 상태판 — 지금 어디쯤?"))


if __name__ == "__main__":
    main()
