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
    dd = (c / peak - 1).iloc[-60:]
    deep_day, deep = dd.idxmin(), dd.min()
    line = peak.iloc[-1] * 0.9
    return dict(c=c, pos=pos, cur=cur, start=start, peak_day=pk_day, depth=depth, run_below=run, last_below=last_below,
                deep_day=deep_day, deep=deep, line=line, to_line=line / c.iloc[-1] - 1,
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
# 독자 말(11-28 다시 짬): `상승 자리`는 오르는 중이 아니라 "고점에서 10% 안"이라는 뜻이었다 — 방향 말로 부르지 않고 잰 것 그대로.
#   상승 → 흔한 범위(고점에서 10% 안) / 하락 · 소강 · 반등 → 큰 하락(10% 넘게) 안의 빠지는 중 · 멈춤 · 되오르는 중
SUB = {"하락": "빠지는 중", "소강": "멈춤", "반등": "되오르는 중"}
UP_PCT = {"us": "75%", "kr": "57%"}   # 전체 거래일 중 여섯 달 뒤 오른 비율
REC = {   # 지난 기록 한 문장 — 사흘 규칙으로 센 값(results/cycle_position_c3.md)
    "us": {"상승": "1990년부터 거래일의 64%가 흔한 범위였고, 그 뒤 여섯 달은 전체 거래일과 같았습니다(가운데 값 6.1% 상승 · 전체 거래일 5.7% 상승).",
           "하락": "S&P 500이 큰 하락에 막 들어간 16번 가운데 12번은 여섯 달 뒤 올라 있었습니다(전체 거래일은 75%).",
           "소강": "큰 하락 안에서 멈춘 7번 가운데 5번은 여섯 달 안에 10% 넘게 더 빠졌습니다(전체 거래일은 22%).",
           "반등": "큰 하락 안에서 되오른 9번 가운데 5번은 여섯 달 뒤 올라 있었고, 5번은 그 사이 10% 넘게 다시 빠진 적이 있습니다."},
    "kr": {"상승": "1997년부터 거래일의 33%가 흔한 범위였고, 그 뒤 여섯 달은 전체 거래일과 비슷했습니다(가운데 값 0.4% 상승 · 전체 거래일 2.6% 상승).",
           "하락": "코스피가 큰 하락 안에서 빠지기 시작한 24번 가운데 15번은 여섯 달 뒤 올라 있었습니다(전체 거래일은 57%).",
           "소강": "큰 하락 안에서 멈춘 20번 가운데 14번은 여섯 달 뒤 올라 있었습니다(전체 거래일은 57%).",
           "반등": "큰 하락 안에서 되오른 15번 가운데 여섯 달 뒤 올라 있던 것은 4번입니다(전체 거래일은 57%)."},
}


def pct(v, d=1):
    return f"{v * 100:+.{d}f}%".replace("-", "−")


def zone(m):
    return "흔한 범위" if m["cur"] == "상승" else "큰 하락"


def answer_word(m):
    return f"{pct(m['depth'])} · {zone(m)}"


def distance_bar(m):
    """고점에서 얼마나 내려와 있나 — 0 ~ −25% 눈금, −10% 선에서 흔한 범위 | 큰 하락."""
    d = min(abs(m["depth"]) * 100, 25)
    x = round(d / 25 * 100, 1)
    over = abs(m["depth"]) * 100 > 25
    lab = f"지금 {pct(m['depth'])}" + (" →" if over else "")
    side = "right:0;" if x > 70 else f"left:{x}%;transform:translateX(-50%);" if x > 12 else "left:0;"
    return ('<div style="margin:4px 0 2px;">'
            f'<div style="position:relative;height:22px;"><span style="position:absolute;{side}top:0;white-space:nowrap;font-size:14px;line-height:20px;font-weight:700;color:#111;">{lab}</span></div>'
            '<div style="position:relative;height:12px;border-radius:6px;overflow:hidden;background:#E2E8F0;">'
            '<span style="position:absolute;left:40%;right:0;top:0;bottom:0;background:#BFDBFE;"></span></div>'
            f'<div style="position:relative;height:0;"><span style="position:absolute;left:calc({x}% - 8px);top:-14px;width:16px;height:16px;box-sizing:border-box;border-radius:50%;background:#fff;border:4px solid #111;"></span></div>'
            f'<div style="position:relative;height:40px;margin-top:6px;font-size:13px;line-height:18px;color:{dk.NOTE};">'
            '<span style="position:absolute;left:0;top:0;">고점</span>'
            '<span style="position:absolute;left:40%;top:0;transform:translateX(-50%);">−10%</span>'
            '<span style="position:absolute;right:0;top:0;">−25%</span>'
            '<span style="position:absolute;left:0;width:40%;top:20px;text-align:center;color:#334155;font-weight:600;">흔한 범위</span>'
            '<span style="position:absolute;left:40%;right:0;top:20px;text-align:center;color:#1D4ED8;font-weight:600;">큰 하락</span></div></div>')


def where_sentence(m, mk):
    nm = "S&P 500은" if mk == "us" else "코스피는"
    s = f"{nm} 가장 높았던 {md(m['peak_day'])}보다 {abs(m['depth']) * 100:.1f}% 낮습니다. "
    if m["cur"] == "상승":
        s += "고점에서 10% 안쪽으로 내려오는 것은 흔한 범위입니다."
        if m["deep"] < m["depth"] - 0.02:
            s += f" {md(m['deep_day'])}에는 {abs(m['deep']) * 100:.1f}% 아래까지 내려갔다가 돌아왔습니다."
    else:
        s += "고점에서 10% 넘게 내려온 큰 하락입니다."
        if m["cur"] == "하락" and m["low_day"] is not None:
            s += f" {md(m['low_day'])}에 가장 낮은 값을 새로 써, 아직 빠지는 중입니다."
        elif m["cur"] == "소강":
            s += " 20거래일 넘게 가장 낮은 값을 새로 쓰지 않아, 멈춘 상태입니다."
        elif m["cur"] == "반등":
            s += " 가장 낮았던 값보다 10% 넘게 올라와, 되오르는 중입니다."
    return s


def main_card(mk, m, cr):
    nm = "S&P 500" if mk == "us" else "코스피"
    lines = [(where_sentence(m, mk), "plain"), (distance_bar(m), "html")]
    c = m["c"].iloc[-504:]
    line = (m["c"].cummax() * 0.9).reindex(c.index)
    lab = [f"{d.year % 100:02d}.{d.month:02d}" if (k > 60 and d.month != c.index[k - 1].month and d.month % 3 == 1) else "" for k, d in enumerate(c.index)]
    lines.append((dk.trend_card(f"최근 2년 {nm} · 고점보다 10% 아래 선", lab,
                                [(nm, list(c.values), dk.CHART_MAIN, "solid"), ("고점보다 10% 아래 선", list(line.values), dk.CHART_CMP, "guide")],
                                lambda v: f"{v:,.0f}"), "html"))
    lines.append(("지난 기록 : " + REC[mk][m["cur"]], "plain"))
    if m["cur"] == "상승":
        lines.append(("row", "큰 하락으로 보는 선", f"{m['line']:,.0f}", f"고점보다 10% 아래 · 지금보다 {abs(m['to_line']) * 100:.1f}% 아래 · 종가가 사흘 이어서 밑돌 때"))
    else:
        lines.append(("row", "큰 하락 안에서 지금은", SUB[m["cur"]], "빠지는 중 = 20거래일 안에 가장 낮은 값을 새로 씀 · 멈춤 = 새로 쓰지 않음 · 되오르는 중 = 가장 낮은 값보다 10% 넘게 위"))
        if mk == "us":
            on = cr["b60"] >= 0.20
            lines.append(("row", "길게 간 하락의 조건", "해당" if on else "해당 안 함",
                          f"회사채 금리차가 60일 새 0.20%p 넘게 벌어짐 · 지금 {cr['b60']:+.2f}%p · 이 조건에서 시작한 하락 8번 중 4번이 길었고, 아닌 13번은 길지 않았습니다".replace("-", "−")))
    lines.append((f"여섯 달 앞을 보는 판입니다. 하루 · 한 주의 오르내림은 말하지 않습니다. 종가로 재고, 10% 선을 사흘 이어서 넘어야 범위를 바꿉니다. 비교 대상은 {BASE_N[mk]}입니다.", "note"))
    big = m["cur"] != "상승"
    tip = ("지금 하락이 흔한 범위인지 큰 하락인지를, 고점에서 떨어진 거리로 잽니다\n"
           "· 흔한 범위 = 가장 높았던 종가에서 10% 안 · 큰 하락 = 10% 넘게 아래(사흘 이어서)\n"
           "· 오르는 중 · 내리는 중을 말하지 않습니다. 지금 서 있는 곳과, 지난 같은 곳에서 여섯 달 뒤가 어땠는지를 보여 줍니다")
    return M._qc("고점에서 얼마나 내려왔나?", answer_word(m), "negative" if big else "neutral", dk.DOWN if big else "#111", lines, tip=tip, opened=True)


def outside_card(mk, m, cr, wr, sec):
    b60, h60 = cr["b60"], cr["h60"]
    baa_calm, hy_calm = b60 < 0.20, h60 >= cr["cut20"]
    cword = "평온" if baa_calm and hy_calm else "벌어짐" if not baa_calm and not hy_calm else "엇갈림"
    fd = m["fdd"]
    asia = [k for k in ("닛케이", "항셍", "상하이", "대만") if fd[k] < -0.10]
    eu = [k for k in ("독일", "유로 50") if fd[k] < -0.10]
    n_down = sum(v < -0.10 for v in fd.values())
    fword = "아시아 함께 하락" if len(asia) >= 3 and not eu else f"{n_down}곳 하락" if n_down else "평온"
    lines = [("하락이 길어질지를 가른 것은 지난 기록에서 신용이었습니다. 나머지는 지금 값만 싣습니다.", "plain"),
             ("row", f"{'' if mk == 'us' else '미국 '}신용 (회사채 · 하이일드 금리차)", cword,
              f"회사채 60일 {b60:+.2f}%p · 하이일드 대리 60일 {h60 * 100:+.1f}% (2007년 뒤 아래 {cr['hpct'] * 100:.0f}%)".replace("-", "−")),
             ("row", "해외 증시 (52주 고점 대비)", fword, " · ".join(f"{k} {v * 100:.1f}%".replace("-", "−") for k, v in fd.items()))]
    if mk == "us":
        down = [k for k, v in sorted(sec.items(), key=lambda kv: kv[1]) if v < -0.10]
        lines.append(("row", "업종 (52주 고점 대비 −10% 아래)", f"9개 중 {len(down)}개", " · ".join(f"{k} {sec[k] * 100:.1f}%".replace("-", "−") for k in down)))
    lines.append(("row", "전쟁 · 정책 걱정 (지난 5년 중)", f"{wr[0] * 100:.0f} · {wr[1] * 100:.0f} 분위", "지정학 위험 지수 · 경제정책 불확실성 지수, 높음 = 80 분위 넘음"))
    if mk == "kr":
        lines.append(("row", "돈의 흐름", "증시에서 돈이 빠져나가나?", "한국 증시 리포트 수급 탭 카드로 이어집니다"))
    return M._qc("바깥 사정은?", f"신용 {cword} · {fword}", "neutral", "#111", lines, opened=False)


def change_rows():
    """홈 `오늘 달라진 것` 한 줄 — 범위가 바뀐 날에만. 예시 = 실제로 바뀐 최근 날."""
    ex = [("S&P 500 큰 하락으로", "2025년 4월 7일", "사흘째 고점보다 10% 넘게 아래",
           "지난 기록 : 큰 하락에 막 들어간 16번 중 여섯 달 뒤 12번 상승 · 1990년부터 전체 거래일 75%"),
          ("S&P 500 흔한 범위로", "2025년 5월 1일", "사흘째 고점에서 10% 안",
           "지난 기록 : 흔한 범위의 여섯 달 뒤 = 1990년부터 전체 거래일과 같음"),
          ("코스피 다시 빠지는 중", "2026년 10월 15일", "멈춤 뒤 가장 낮은 값을 새로 씀",
           "지난 기록 : 큰 하락 안에서 빠지기 시작한 24번 중 여섯 달 뒤 15번 상승 · 1997년부터 전체 거래일 57%")]
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
    sub = f'font-size:14px;line-height:20px;color:{dk.SUB};word-break:keep-all;'
    home = guide_box("홈에는 범위가 바뀐 날에만 · `오늘 달라진 것` 카드의 한 줄로",
                     f'<div style="padding:0 0 8px;{sub}">범위는 천천히 바뀝니다(10% 선을 사흘 이어서). 바뀐 날에만 아래처럼 한 줄 — 바뀌지 않은 날엔 홈에 나오지 않습니다.</div>' + change_rows())
    place = guide_box("놓일 자리 · 증시 리포트 안", f'<div style="padding:0 0 8px;{sub}">미국 · 한국 증시 리포트에서 그날 움직임 구획들 <b>뒤</b>, `큰 흐름` 자리. 첫 카드는 펼쳐 두고 `바깥 사정은?`은 접어 둡니다.</div>')
    body = (f'<div data-head-title="시장 상태판">'
            + dk.muted("숫자는 11월 27일 종가로 검증 저장소에서 계산했습니다. 점선 상자는 목업에서만 보입니다.")
            + '<a id="us"></a>' + dk.section("큰 흐름 — 미국 증시", M.C.cards_grid(main_card("us", us, cr) + outside_card("us", us, cr, wr, sec)), line=False)
            + '<a id="kr"></a>' + dk.section("큰 흐름 — 한국 증시", M.C.cards_grid(main_card("kr", kr, cr) + outside_card("kr", kr, cr, wr, sec)), line=False)
            + home + place
            + '</div>')
    p = os.path.join(OUT, "mock_state_detail.html")
    print(dk.write_mock(body, p, "시장 상태판 — 고점에서 얼마나 내려왔나?"))


if __name__ == "__main__":
    main()
