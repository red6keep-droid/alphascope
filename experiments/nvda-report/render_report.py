"""nvda_analysis.json → output/nvda_report.md (기획서 10절, 그림자 모드 점검용).

표는 여기서 파이썬이 그린다. Gemini 문장(narrative.json)은 ②단계 뒤에 끼운다.
"""

import datetime
import json
import os
import sys

import config

DIR_KO = {"positive": "긍정", "negative": "부정", "uncertain": "불확실", "neutral": "중립"}
AREA_KO = {"Earnings": "실적", "Flows": "수급", "Regulation": "규제", "Legal": "법무", "Product": "제품", "Demand": "수요",
           "Supply": "공급", "Corporate": "기업", "Macro": "거시", "Other": "기타"}
KIND_KO = {"EARNINGS": "NVDA 실적", "EARNINGS_PEER": "고객·공급·동종 실적", "FOMC": "FOMC", "CPI": "CPI", "NFP": "고용", "GDP": "GDP",
           "PCE": "PCE", "TSMC_REV": "TSMC 월매출", "EVENT": "행사", "INDEX": "지수", "OPEX": "옵션 만기", "COURT": "⚠ 법원"}
LABEL_KO = {
    "close": "종가", "ret_1d": "등락", "ret_vs_spy": "SPY 대비", "ret_vs_smh": "SMH 대비", "ret_vs_amd": "AMD 대비", "gap": "시가 갭",
    "range_pct": "일중 변동폭", "vol_ratio_20d": "거래량 배수(20일)",
    "ma50": "50일선", "ma200": "200일선", "pct_from_52w_high": "52주 고점 대비", "rsi14": "RSI 14", "ma_cross": "이평 교차",
    "iv_atm_30d": "ATM IV 30일", "iv_rank_60d": "IV 랭크 60일", "implied_move_next_earnings": "실적 implied move",
    "pc_ratio_oi": "풋/콜 (OI)", "pc_ratio_vol": "풋/콜 (거래량)", "gex_approx": "GEX 근사 (부호만)", "gex_flip_strike": "감마 0 행사가",
    "max_oi_strike_call": "최대 OI 콜", "max_oi_strike_put": "최대 OI 풋",
    "eps_est_cq": "당분기 EPS 컨센서스", "eps_est_cq_7d_chg_pct": "EPS 7일 변화", "rev_est_cq": "당분기 매출 컨센서스",
    "rev_est_cq_7d_chg_pct": "매출 7일 변화", "revisions_up_30d": "30일 상향", "revisions_down_30d": "30일 하향",
    "rating_counts": "등급 분포", "pt_mean": "목표가 평균", "pt_median": "목표가 중앙", "pt_high": "목표가 최고", "pt_low": "목표가 최저",
    "smh_shares_out": "SMH 발행주식수", "soxx_shares_out": "SOXX 발행주식수", "shares_short": "공매도 잔고", "short_pct_float": "유통주식 대비",
    "short_asof": "공매도 기준일", "forward_pe": "선행 PER",
    "news_count": "기준일 NVDA 기사 수", "news_avg_7d": "직전 7일 하루 평균", "news_pending": "분류 대기 문서",
}
GROUP_KO = {"price": "가격·거래량", "technical": "기술", "options": "옵션", "estimates": "추정치", "analysts": "애널리스트",
            "flows": "수급", "valuation": "밸류에이션", "news": "뉴스"}


def fmt(value, kind):
    if value is None or value == "":
        return "—"
    try:
        if kind == "usd":
            return f"${value:,.2f}"
        if kind == "usd0":
            return f"${value:,.0f}"
        if kind == "usd2":
            return f"${value:,.2f}"
        if kind == "usd_bn":
            return f"${value / 1e9:,.1f}B"
        if kind == "pct":
            return f"{value:.1f}%"
        if kind == "pct2":
            return f"{value:.2f}%"
        if kind == "pct_signed":
            return f"{value:+.2f}%"
        if kind == "pct_signed2":
            return f"{value:+.2f}%"
        if kind == "pp_signed":
            return f"{value:+.2f}%p"
        if kind == "x":
            return f"{value:.2f}×"
        if kind == "num0":
            return f"{value:.0f}"
        if kind == "num1":
            return f"{value:.1f}"
        if kind == "num2":
            return f"{value:.2f}"
        if kind == "int":
            return f"{int(value):,}"
        if kind == "iv":
            return f"{value * 100:.1f}%"
        if kind == "gex":
            sign = "양(+)" if value > 0 else "음(−)"
            return f"{sign} · ${abs(value) / 1e9:,.2f}B/1%"
        if kind == "shares_m":
            return f"{value / 1e6:,.1f}M주"
        if kind == "ratings":
            return f"강매수 {value.get('strongBuy', 0)} · 매수 {value.get('buy', 0)} · 보유 {value.get('hold', 0)} · 매도 {value.get('sell', 0) + value.get('strongSell', 0)}"
        if kind == "text":
            return {"golden": "골든 크로스", "death": "데드 크로스"}.get(value, str(value))
    except (TypeError, ValueError):
        return str(value)
    return str(value)


def _row(cells):
    return "| " + " | ".join(str(c) for c in cells) + " |"


def _table(headers, rows):
    if not rows:
        return "_데이터 없음_\n"
    out = [_row(headers), _row(["---"] * len(headers))]
    out += [_row(r) for r in rows]
    return "\n".join(out) + "\n"


def title_for(run_date):
    d = datetime.date.fromisoformat(run_date)
    return f"{config.REPORT_TITLE_PREFIX} — {d.year}년 {d.month}월 {d.day}일"


def section_headline(a):
    h = a["headline"]
    if h.get("close") is None:
        return "휴장 — 시세는 다음 거래일에 채워진다. 공시·기사·일정만 아래에 있다.\n"
    line = (f"**NVDA ${h['close']:,.2f} ({h['ret_1d']:+.2f}%)** · SPY 대비 {fmt(h.get('ret_vs_spy'), 'pp_signed')} · "
            f"SMH 대비 {fmt(h.get('ret_vs_smh'), 'pp_signed')} · AMD 대비 {fmt(h.get('ret_vs_amd'), 'pp_signed')} · "
            f"거래량 20일 평균의 {fmt(h.get('vol_ratio_20d'), 'x')}")
    if a.get("macro_today"):
        line += f" · 거시 일정: {', '.join(a['macro_today'])}"
    note = "" if a.get("is_latest_bar_today") else "\n\n_기준 거래일이 최신이 아닐 수 있다 — 일봉 수집 상태를 확인._"
    return line + note + "\n"


SOURCE_KO = {"edgar": "EDGAR", "yfinance": "yfinance", "calendar": "캘린더", "nvidianews": "NVIDIA 뉴스룸", "nvidiablog": "NVIDIA 블로그",
             "cnbc": "CNBC", "federalregister": "연방관보", "courtlistener": "CourtListener", "rss": "RSS"}
DOC_KINDS = ("news", "newsroom", "blog", "fedreg", "court")


def _event_line(e):
    tag = f"`{AREA_KO.get(e['area'], e['area'])}` {DIR_KO.get(e['direction'], e['direction'])}"
    if e["kind"] in DOC_KINDS:
        # 문서형: 사실 한 문장이 머리, 원문 제목은 링크 텍스트
        head = f"**{e['fact']}**" if e["emphasis"] else e["fact"]
        src = SOURCE_KO.get(e.get("source") or "", e.get("source") or "")
        link = f" [{src}: {e['title'][:70]}]({e['url']})" if e.get("url") else f" ({src}: {e['title'][:70]})"
        fact = ""
    else:
        head = f"**{e['title']}**" if e["emphasis"] else e["title"]
        link = f" [출처]({e['url']})" if e.get("url") else ""
        fact = f" — {e['fact']}" if e.get("fact") and e["fact"] != e["title"] else ""
    when = f" ({e['published_at'][:10]})" if e.get("published_at") else ""
    return f"- {tag} · {head}{fact}{link}{when}"


def section_events(a):
    if not a["events"]:
        return "오늘은 임계값을 넘은 이벤트가 없다.\n"
    out = [_event_line(e) for e in a["events"]]
    if a["events_overflow"]:
        out.append(f"\n<details><summary>그 외 {len(a['events_overflow'])}건</summary>\n")
        out += [_event_line(e) for e in a["events_overflow"]]
        out.append("\n</details>")
    if a.get("analyst_target_only"):
        out.append(f"\n목표가만 바뀐 애널리스트 {len(a['analyst_target_only'])}건 (등급 변경 아님): "
                   + " · ".join(t["title"] for t in a["analyst_target_only"][:6]))
    return "\n".join(out) + "\n"


def section_upcoming(a):
    rows = []
    d0 = datetime.date.fromisoformat(a["day"])
    for c in a["upcoming"]:
        dn = (datetime.date.fromisoformat(c["day"]) - d0).days
        conf = "" if c.get("confirmed", 1) else " (추정)"
        extra = ""
        if c["kind"] == "EARNINGS":
            im = next((x["value"] for x in a["status"]["options"] if x["key"] == "implied_move_next_earnings"), None)
            extra = f" · implied move ±{im:.1f}%" if im else ""
        rows.append([f"D{dn:+d}" if dn else "D0", c["day"], KIND_KO.get(c["kind"], c["kind"]), c["label"] + conf + extra])
    if not rows:
        return f"{config.CALENDAR_LOOKAHEAD_DAYS}일 내 일정 없음 (법원 일정은 {config.COURT_LOOKAHEAD_DAYS}일).\n"
    return _table(["D-n", "날짜", "종류", "내용"], rows)


def section_status(a):
    st = a["status"]
    out = []
    for group in ("price", "technical", "options", "estimates", "analysts", "flows", "valuation", "news"):
        cells = st.get(group) or []
        if not cells:
            continue
        rows = []
        for c in cells:
            v = fmt(c["value"], c["fmt"])
            if c["value"] is None or c["value"] == "":
                v = config.MISSING_HINTS.get(c["key"], config.MISSING_DEFAULT_HINT)
                if c["key"] == "iv_rank_60d":
                    v += f" (현재 {st.get('iv_rank_n', 0)}/{config.IV_RANK_WINDOW}일)"
            rows.append([LABEL_KO.get(c["key"], c["key"]), f"**{v}**" if c["flag"] else v])
        out.append(f"**{GROUP_KO[group]}**\n\n" + _table(["지표", "값"], rows))
    ds = a["data_status"]
    if ds.get("option_expiries"):
        out.append(f"_옵션 스냅샷 만기: {', '.join(ds['option_expiries'])} · 스냅샷 누적 {ds['option_snapshot_days']}일_\n")
    return "\n".join(out)


def section_cases(a):
    """추적 사건은 사건명과 다음 일정만. 판결·합의가 나면 ② "오늘 바뀐 것"에 올라간다 (2026-10-10 단순화)."""
    if not a["cases"]:
        return "추적 사안 없음.\n"
    rows = []
    for c in a["cases"]:
        nxt = f"{c['next_day']} {c['next_label']}" if c.get("next_day") else "잡힌 일정 없음"
        last = f" · 최근 {c['last_activity_at'][:10]} {c['last_activity_summary']}" if c.get("last_activity_summary") else ""
        rows.append([f"[{c.get('short_name') or c['title']}]({c['url']})", c.get("status") or "—", nxt + last])
    return _table(["사건", "상태", "다음 일정"], rows)


def section_checklist(a):
    rows = []
    for r in a["checklist"]:
        if r.get("value") is None:
            v = r.get("note") or "이번 실행에서 받지 못함 — 다음 실행에서 재시도"
        elif r["unit"] == "USD":
            v = f"${r['value'] / 1e9:,.2f}B" if abs(r["value"]) >= 1e9 else f"${r['value'] / 1e6:,.1f}M"
        elif r["unit"] in ("%", "% of shares"):
            v = f"{r['value']:.1f}%"
        elif r["unit"] == "배":
            v = f"{r['value']:.1f}배"
        elif r["unit"] == "분위":
            v = f"{r['value']:.0f}분위"
        else:
            v = f"{r['value']:,}"
        if r.get("arrow"):
            v = f"{v} {r['arrow']}"
        rows.append([r["label"], v, r.get("asof") or "—", (r.get("detail") or r.get("source") or "—")])
    return _table(["지표", "값", "기준일", "비고"], rows)


def section_narrative(out_path):
    path = os.path.join(os.path.dirname(out_path), "narrative.json")
    if not os.path.exists(path):
        return "_오늘은 이벤트가 없어 해석을 생략한다._\n"
    with open(path, "r", encoding="utf-8") as f:
        n = json.load(f)
    return "\n".join(f"- {s}" for s in n.get("today", [])) + "\n"


def section_footer(a):
    ds = a["data_status"]
    return "\n".join([
        "- 데이터: yfinance(일봉·옵션·추정치·애널리스트·기관·공매도) · SEC EDGAR(Form 4·8-K·10-Q) · FRED(거시 일정) · 정적 캘린더",
        f"- 생성 {a['generated_at']} (UTC) · 기준 거래일 {a['day']} · 일봉 마지막 {ds['bars_last_day']} · 수집 항목 {ds.get('items_by_kind') or '{}'}",
        "- 이 글은 보유 종목의 사실 추적이다. 매수·매도 판단을 담지 않으며, 사건과 가격 변화 사이의 인과를 단정하지 않는다.",
        "- 옵션 지표는 장 마감 후 1회 스냅샷이며 GEX는 딜러 포지션 가정이 조잡한 근사다. 부호만 참고.",
        "- 임계값은 초안이다. 30일 그림자 운영 뒤 '오늘 바뀐 것'이 하루 1~3건이 되도록 조정한다.",
    ]) + "\n"


def render(analysis_path=None, out_path=None):
    analysis_path = analysis_path or os.path.join(config.OUTPUT_DIR, "nvda_analysis.json")
    out_path = out_path or os.path.join(config.OUTPUT_DIR, "nvda_report.md")
    with open(analysis_path, "r", encoding="utf-8") as f:
        a = json.load(f)
    title = title_for(a["run_date"])
    parts = [
        f"# {title}", f"_기준 거래일(뉴욕) {a['day']}_", "",
        (f"> 🧪 **테스트 운영 중** — {config.TEST_NOTICE}\n" if a["data_status"].get("test_mode") else "")
        + (f"> ⚠️ 기사 {a['data_status']['items_pending']}건이 아직 분류되지 않아 오늘 항목이 불완전할 수 있다.\n" if a["data_status"].get("items_pending") else ""),
        "## ① 오늘 한 줄", section_headline(a),
        f"## ② 오늘 바뀐 것 ({a['events_total']}건)", section_events(a),
        f"## ③ 다가오는 것 ({config.CALENDAR_LOOKAHEAD_DAYS}일 이내 · 법원 일정 {config.COURT_LOOKAHEAD_DAYS}일)", section_upcoming(a),
        "## ④ 상태판", section_status(a),
        "## ⑤ 진행 중 사안", section_cases(a),
        "## ⑥ 보유 논리 점검표", section_checklist(a),
        "## ⑦ 오늘의 해석", section_narrative(out_path),
        "## ⑧ 출처·면책", section_footer(a),
    ]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    with open(os.path.join(os.path.dirname(out_path), "title.txt"), "w", encoding="utf-8") as f:
        f.write(title)
    print(f"[render] {out_path} ({title})")
    return out_path


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    render()
