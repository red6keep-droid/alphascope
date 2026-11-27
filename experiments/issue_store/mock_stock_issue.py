"""종목 이슈 목업 — 종목 급락 · 급등 전망이 끝나도 사건 자체를 계속 따라가는 페이지.

    .venv/bin/python experiments/issue_store/mock_stock_issue.py   → output/mock_stock_issue_nvda.html

설계:
- 증시 전망(가격 질문 · 판정 나면 끝)과 종목 이슈(사건 질문 · 기사가 잦아들 때까지)는 따로, 서로 링크.
- 열림 = 종목 전망 자동 등록 때 이유 카드 이슈 코드 1위가 사건(기업 사건 · 규제 · 소송) + 48시간 기사 평소의 3배 이상. 실적 같은 일정은 열지 않음.
- 화면 = Hot Issue 틀(mock_issue_watch) 재사용: 바늘(수습 ↔ 악화) · 진행 상황 사다리 · 관련 뉴스 · News Timeline(기준 가격 = 그 종목).
  뺌 = 수혜주 · 과거 기록 주가(한 종목 사건은 사례가 적어 일반화) · 시장 지표 묶음 → `주가도 같은 쪽인가?`(종목 vs 업종) 한 장.
- 닫힘 = 5거래일 기사가 평소 수준 → `추적 종료` 표시, 페이지는 남김. 동시에 3개까지.
목업 = AI 0(쪽 · 단계 = 글자 패턴) · 새 수집 0(공용 뉴스 + 종목 레이더 뉴스 + 구글 뉴스 검색 캐시, Hot Issue 목업과 같음) · 블로그에 안 나감.
mock_issue_watch 는 고치지 않는다 — 설정만 이 파일에서 끼운다(발행 코드 issue_watch_daily 의 이슈 셋에는 안 들어감).
"""
import datetime as dt
import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import mock_issue_watch as IW  # noqa: E402

dk, H, qc = IW.dk, IW.H, IW.qc
KST = IW.KST

ISS = {"id": "NVDA_CEO", "name": "엔비디아 CEO 사임", "q": "젠슨 황 사임, 엔비디아는 수습되나?", "by": "자동",
       "pat": r"젠슨|Jensen|엔비디아 ?(CEO|최고경영자|이사회)|Nvidia'?s? (CEO|board)|크레스|Kress|황 (CEO|사임|퇴임|복귀)",
       "gq": "젠슨 황 사임 OR 엔비디아 CEO OR 젠슨 황 조사 OR 엔비디아 임시 CEO", "since": "2026-11-10",
       "chain": None, "cases": ()}
SYM, SYM_NM, SECTOR, SECTOR_NM = "NVDA", "엔비디아", "^SOX", "반도체 지수"
FORECAST = ("엔비디아 급락, 반등할까 더 빠질까?", "forecast-2026-003", "11.12 하락 지속으로 끝남")   # 이 이슈를 연 증시 전망 (상태 저장소 EH-2026-003)
EVENT_BASE = "2026-11-06"   # 사건 전 마지막 종가 = 증시 전망 기준일(base_day)

IW.CFG["NVDA_CEO"] = dict(
    slug="issue-nvidia-ceo", good="수습", bad="악화", watch="수습", file="mock_stock_issue_nvda.html",
    side_pat=[("멀어짐", r"사임 ?(및|하고|과|와|,|…)|사임.{0,6}(급락|폭락|증발)|resign(s|ed)? and"),   # 사임 + 임시 CEO 가 한 제목이면 큰 일(사임) 쪽 — 수습 낱말보다 먼저
              ("종전", r"임시 ?(CEO|최고경영자)|직무 ?대행|후임|선임|임명|복귀|해명|무혐의|종결|안정|지지|interim|appoint|successor|cleared|return"),
              ("확전", r"사임|퇴임|해임|조사|의혹|스캔들|간첩|스파이|연루|소송|기소|급락|폭락|증발|배신|이탈|resign|step(s|ped)? down|probe|investigat|scandal|lawsuit|plunge")],
    tip="수습 = 임시 CEO · 후임 · 복귀 · 해명 · 조사 종결 소식\n악화 = 사임 · 조사 · 의혹 · 소송 · 급락 소식",
    groups=[], extra=[], skip=(), case_cols=[], case_exp={}, case_re=None, case_name="", case_note="", bridge="", bridge_sym=SYM, chart=None,
    stages={"종전": [("임시 체제", r"임시 ?(CEO|최고경영자)|직무 ?대행|interim"), ("이사회 대응", r"이사회|board|복귀 검토|주주"),
                     ("후임 확정", r"후임 (확정|선임|발표)|신임 CEO|새 CEO|정식 CEO|successor named"), ("조사 종결", r"조사 (종결|마무리)|무혐의|cleared")],
            "확전": [("의혹 · 보도", r"의혹|보도|연루|스캔들|간첩|스파이|report"), ("조사", r"조사|probe|investigat"),
                     ("사임", r"사임|퇴임|해임|resign|step(s|ped)? down"), ("소송 · 제재", r"소송|기소|제재|벌금|lawsuit|indict|charge")]})
IW.TL_REF["NVDA_CEO"] = (SYM_NM, SYM, "{:,.2f}달러")
IW.REF2["NVDA_CEO"] = [(SYM_NM, SYM, None, "{:,.2f}달러", -1), ("엔비디아 반도체 대비", SYM, SECTOR, None, -1)]   # 비교 지표 둘 — 회사 일인지 업계 일인지 (과거 사례 없음 · 이유로만, 2026-11-22)
IW.STAGE_Q["NVDA_CEO"] = "사태 진행 상황"   # Hot Issue `전쟁 진행 상황` 자리


def prices():
    import yfinance as yf
    df = yf.download([SYM, SECTOR, "^GSPC"], start="2026-01-01", progress=False, auto_adjust=True, threads=False)["Close"]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df


def _chg(s, a, b):
    s = s.dropna()
    a0 = s[s.index <= pd.Timestamp(a)].iloc[-1]
    b0 = s[s.index <= pd.Timestamp(b)].iloc[-1]
    return (b0 / a0 - 1) * 100


def tri_val(v, fs, unit="%p", weight=700):
    """증감 값 = 가이드 5절 삼각형(그 자리 글자 fs 의 80% 정수 · 위로 1 · 숫자와 2, dk.tri_span) + 증감 색 — 띄어쓰기 없음."""
    return (f'<span style="color:{dk.UP if v > 0 else dk.DOWN};font-weight:{weight};white-space:nowrap;">{dk.tri_span(v > 0, fs)}{abs(v):.1f}{unit}</span>'
            if round(v, 1) else f'<span style="font-weight:{weight};">0.0{unit}</span>')


def rel_move(g5, when=""):
    """`엔비디아 주가는 (같은 기간) 반도체 지수 대비 ▼ 20.8%p 움직였습니다` — 업종 대비 값 = ▼ · ▲ + 증감 색 굵게.
    옛 `20.8%p 더 빠졌습니다` 는 숫자에 방향 표시가 없었다. 삼각형과 숫자는 한 덩어리(dk.arrow nowrap). 3%p 안이면 `비슷하게` (숫자 없음)."""
    if abs(g5) < 3:
        return dk.esc(f"{SYM_NM} 주가는 {when}{SECTOR_NM}와 비슷하게 움직였습니다.")
    return dk.esc(f"{SYM_NM} 주가는 {when}{SECTOR_NM} 대비 ") + tri_val(g5, int(dk.STATE_SENT_FS.rstrip("px"))) + " 움직였습니다."   # 문장 글자 18 → 삼각형 14


def q_price(px, word):
    """주가도 같은 쪽인가? — 종목 vs 자기 업종(증시 전망 종목 자와 같은 비교). 기간 = 최근 5거래일(바늘 `최근 일주일` 과 같게) + 사건 뒤 전체.
    3%p = 종목 전망 절대 기준(forecast_register.STOCK_AMIN)과 같은 선."""
    s = px[SYM].dropna()
    d1, d5 = s.index[-1], s.index[-6]
    rows, gaps = [], {}
    for lab, a in (("최근 일주일", d5), ("사건 뒤 전체", pd.Timestamp(EVENT_BASE))):
        n, m = _chg(px[SYM], a, d1), _chg(px[SECTOR], a, d1)
        gaps[lab] = n - m
        span = f"{H.md(a.strftime('%Y-%m-%d'))} → {H.md(d1.strftime('%Y-%m-%d'))}"
        sg = lambda v: f"{'+' if v >= 0 else '−'}{abs(v):.1f}%"   # noqa: E731
        rows.append(("row", dk.esc(lab), IW._sp(tri_val(n - m, int(dk.EMPH_Q.rstrip("px")), weight=400)),
                     f"{SYM_NM} {sg(n)} · {SECTOR_NM} {sg(m)} ({span})"))   # 값 = 업종 대비 ▲ · ▼ %p(증감 색, P423), 뜻 = 두 값 그대로
    g5 = gaps["최근 일주일"]
    mk = "수습" if g5 >= 3 else "악화" if g5 <= -3 else None
    ns = IW.news_side(word)
    if mk is None:
        ans = "업종과 비슷"
    elif ns is None:
        ans = f"주가만 {mk} 쪽"
    else:
        ans = f"같은 쪽 ({mk})" if ns == mk else "엇갈림"
    nd = f"{ns} 소식이 더 많았습니다" if ns else "수습 · 악화 소식이 엇갈렸습니다"
    verdict = "" if mk is None or ns is None else (" 뉴스와 주가가 같은 쪽을 가리킵니다." if ns == mk else " 뉴스와 주가가 서로 다른 쪽을 가리킵니다.")
    first = dk.esc(f"최근 일주일 뉴스는 {nd}. ") + rel_move(g5, "같은 기간 ") + dk.esc(verdict)
    tip = (f"주가 = {SYM_NM}에서 같은 업종 지수({SECTOR_NM}) 움직임을 뺀 값 — 업종 전체가 같이 움직인 몫은 빼고 이 회사 일만.\n"
           "업종보다 3%p 넘게 더 빠지면 악화 쪽, 더 오르면 수습 쪽 (증시 전망 종목 기준과 같은 선).\n"
           "사건 뒤 전체 = 사건 전 마지막 종가(증시 전망 기준일)부터.\n예측이 아니라 지금까지 일어난 일입니다.")
    # 카드 색 = 답 방향 (가이드라인 7-1: 답에 보라 금지) — 같은 쪽(악화) = 파랑 · 같은 쪽(수습) = 빨강 카드, 엇갈림 · 업종과 비슷 = 회색.
    # 옛: 움직임이 있으면 보라(IW._theme) → `같은 쪽 (악화)` 가 보라 카드에 파랑 쪽 말이라 왜 보라인지 안 읽혔다
    side = mk if (ns is None or ns == mk) else None
    th, ink = {"수습": ("positive", dk.UP), "악화": ("negative", dk.DOWN)}.get(side, ("neutral", "#111"))
    lines = [(first, "rich")] + rows + [(IW._excl(f"미국 {H.md(d1.strftime('%Y-%m-%d'))} 종가 기준입니다."), "html")]
    return IW._good_red(qc.question_card("주가도 같은 쪽인가?", ans, th, ink, lines, tip=tip)), ans, g5


def collect():
    """이슈 페이지 · 종목 페이지 카드가 같이 쓰는 값 — 기사 · 사건 · 가격."""
    IW.use(ISS)
    items = IW.SB.load_news()
    now = dt.datetime.now(dt.timezone.utc)
    today = now.astimezone(KST).date()
    days = [(today - dt.timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    gdays = [(today - dt.timedelta(days=i)).isoformat() for i in range(41, -1, -1)]
    gn, capped = IW.gnews(ISS, gdays)
    rows = IW.merge_rows(IW.news_rows(items, ISS["pat"]), IW.news_rows(gn, ISS["pat"]))
    n48, base, hot = IW.news_level(rows, now)
    cur = {**ISS, "rows": rows, "n48": n48, "base48": base, "hot": hot, "capped": capped,
           "n_store": sum(not r["gn"] for r in rows), "n_gn": sum(r["gn"] for r in rows)}
    px = prices()
    counts = IW.counts_24h(rows, now)
    IW.NOW_LABEL[0] = f"지금 {now.astimezone(KST):%H}시"
    r48 = [r for r in rows if now - r["t"] <= dt.timedelta(hours=48)]
    r14 = [r for r in rows if r["t"].astimezone(KST).date().isoformat() >= days[0]]
    evs = sorted(IW.events(r14), key=lambda e: e["first"], reverse=True)
    IW._AI["cache"] = None   # 목업 = 글자 패턴만 — Hot Issue 판정 캐시가 켜져 있으면 stage_of 가 판정 전 사건을 모두 단계에서 뺀다
    word = IW.gauge_word(evs, today)
    return dict(now=now, today=today, days=days, cur=cur, px=px, counts=counts, r48=r48, evs=evs, word=word)


def page(c, public=False):
    """public=True = 블로그 발행 — 운영자 상자 · 아직 없는 닫힘 규칙 안내는 뺀다."""
    now, today, days, cur, px, counts, r48, evs, word = (c[k] for k in ("now", "today", "days", "cur", "px", "counts", "r48", "evs", "word"))
    q = IW.title_h2(ISS)
    # 이 이슈를 연 증시 전망 = 이미 끝난 과거 기록 → 맨 아래 작은 구분선 줄
    link = (f'<div data-related="1" style="margin-top:28px;">{dk.related_title("관련 증시 전망")}'
            + dk.related_rows([(f"{FORECAST[0]} ({FORECAST[2]})", H.page_url(FORECAST[1]))]) + '</div>')
    gauge = IW.gauge_card(evs, today)
    c_price, align, _ = q_price(px, word)
    qcards = f'<div style="margin:0 0 8px;">{c_price + IW.q_stage(evs)}</div>'
    c_news, r2w = IW.q_news(cur, counts, days, r48)
    today_evs = [e for e in evs if e["first"].astimezone(KST).date() == today]
    sec_list = (dk.section("관련 뉴스", c_news + IW.side_bars(today_evs, evs), line=False)
                + f'<div style="margin:0 0 24px;padding:0 0 {IW.TL_BOTTOM}px;">{IW.news_timeline(evs, days[::-1], px)}</div>')
    note = ("기사가 5거래일 동안 평소 수준으로 돌아오면 추적을 마칩니다. 페이지는 기록으로 남습니다.")
    tail = (f'<div data-why-note="1" style="display:flex;align-items:flex-start;gap:4px;margin:12px 0 0;padding:0 {dk.ALIGN_PX}px;font-size:13px;line-height:19px;color:{dk.SUB};word-break:keep-all;">'
            f'<span style="flex:none;display:flex;align-items:center;height:19px;">{H.EXCL_ICON}</span><span>{dk.esc(note)}</span></div>')
    op = H.operator_box([
        ("목업", "설계 시안 — 블로그에 안 나감. AI 0(쪽 · 단계 = 글자 패턴 CFG['NVDA_CEO']), 새 수집 0"),
        ("모으기", f"키워드 /{ISS['pat']}/ — 공용 뉴스 + 종목 레이더 뉴스 {cur['n_store']}건 + 구글 뉴스 한국어 {cur['n_gn']}건, 겹침 제거 · 사건 {len(evs)}개"),
        ("열림 규칙(안)", "종목 전망 자동 등록 때 이유 카드 이슈 코드 1위 = 기업 사건 · 규제 · 소송 + 48시간 기사 평소의 3배 이상 → 이슈 페이지 열기. 엔비디아 11-09: 규제 · 산업정책 10 · 기업 사건 2 → 해당"),
        ("닫힘 규칙(안)", "5거래일 동안 48시간 기사 수가 평소의 1.5배 아래 → `추적 종료`(머리 줄 아래 회색 라벨), 페이지 유지 · 갱신 멈춤. 동시에 열린 종목 이슈 3개까지"),
        ("증시 전망 쪽 연결(안)", "전망 페이지 타임라인 끝 줄 = `종목 이슈로 이어집니다 ›`(세부 전망 끝 줄과 같은 모양 P465). 종목 페이지 중요 이슈 카드 · Hot Issue 목록에도 링크"),
        ("뺀 카드", "수혜주는? · 과거 기록에서 … 때 주가는? — 한 종목 사건은 비슷한 사례가 적어 일반화가 된다. 시장 지표 묶음 → 종목 vs 업종 한 장"),
        ("AI(운영 때)", "Hot Issue 판정과 같은 방식(json-backup-first, 20건 묶음, 이슈당 하루 최대 5회, 07:30 한 번)"),
        ("주가 기준", f"{SYM_NM} − {SECTOR_NM}, 최근 5거래일 · 사건 뒤({EVENT_BASE} 종가부터), ±3%p = 종목 전망 기준 STOCK_AMIN"),
    ])
    body = q + gauge + qcards + sec_list + ("" if public else op + tail) + link
    body = body.replace('data-cards="1" ', "")
    rev = {v: k for k, v in IW.H._stock_names().items()}
    body = dk.link_page(body, {"iss": ISS, "cur": cur}, name_of=rev.get, where="stock-issue")   # 데이터에 나온 종목 이름 → 그 종목 페이지
    return dk.fix_colons(f'<div data-head-title="{IW.HEAD_TITLE}"{IW.H.head_date_attr()} data-seo-lead="{dk.esc(IW.HEAD_TITLE + " — " + ISS["q"] + " 뉴스와 주가 " + align)}">{body}</div>')


RETURN_PAT = r"CEO ?(로 )?복귀|복귀(했|한|하고|하며|…|에|일|,| 후| 뒤)|경영 일선 복귀|return(s|ed)? as CEO|reinstat"   # 복귀 검토(이사회 대응)는 안 걸림
RETURN_VARIANTS = [   # (이름표, 메뉴 · 홈 이름, 질문, 수습 사다리 셋째 칸)
    ("지금", ISS["name"], ISS["q"], None),
    ("A안 (추천)", "엔비디아 CEO 복귀", "젠슨 황 복귀, 엔비디아는 수습되나?", ("복귀 · 후임 확정", RETURN_PAT + r"|후임 (확정|선임|발표)|신임 CEO|새 CEO|정식 CEO|successor named")),
    ("B안", "엔비디아 CEO 사임 · 복귀", "사임 뒤 복귀한 젠슨 황, 엔비디아는 수습되나?", ("복귀", RETURN_PAT)),
]


def return_variants(c):
    """젠슨 황 복귀(11-23) 뒤 이름 · 질문 · 수습 사다리 시안 — 머리 줄 + `사태 진행 상황` 카드만 셋 나란히. 아래 본문은 `지금` 그대로."""
    base = list(IW.C["stages"]["종전"])
    out = ('<p style="margin:16px 6px 8px;font-size:14px;line-height:21px;color:#6B7280;word-break:keep-all;">'
           '11-23 젠슨 황 CEO 복귀 뒤 시안입니다. 바꾸는 것 = 메뉴 · 홈 카드 이름, 페이지 질문, 수습 단계 셋째 칸. '
           '단계는 기사 제목 글자로 정해지고(AI 0) 같은 값이 이슈 단계 기록에 쌓입니다. 주소(issue-nvidia-ceo)는 그대로입니다.</p>')
    for k, (tag, name, q, step) in enumerate(RETURN_VARIANTS):
        st = list(base)
        if step:
            st[2] = step
        IW.C["stages"]["종전"] = st
        ladder = " → ".join(s[0] for s in st)
        out += (f'<div style="margin:{8 if k == 0 else 36}px 0 0;padding:0 6px;font-size:16px;line-height:24px;font-weight:700;color:#111;">{dk.esc(tag)}</div>'
                f'<div style="padding:0 6px;font-size:13px;line-height:19px;color:#6B7280;word-break:keep-all;">메뉴 · 홈 카드 이름 = {dk.esc(name)} · 수습 단계 = {dk.esc(ladder)}</div>'
                + IW.title_h2({**ISS, "q": q}) + f'<div style="margin:0 0 8px;">{IW.q_stage(c["evs"])}</div>')
    IW.C["stages"]["종전"] = base
    return out + '<div style="margin:40px 6px 0;padding-top:16px;border-top:2px solid #111;font-size:14px;color:#6B7280;">아래 = 지금 페이지 전체</div>'


HOT_PILL = ("#EDE9FE", "#DDD6FE")   # `세부전망` 보라 라벨과 같은 바탕 · 테두리 (가이드라인 14절 증시 전망 P481)
STOCK_PAGE = os.path.join(_HERE, "..", "stock-radar", "output", "NVDA.html")   # 종목 페이지 본문(목업 다시 그리기가 만든 것)
PRICE_CARD = '<div data-cards="1" style="margin:0 0 8px;"><details data-acc="1"><summary style="list-style:none;cursor:pointer;display:block;">'


def hot_btn(href, weight=700):
    """`Hot Issue 자세히 보기 ›` — Hot Issue 라벨 색(바탕 #EDE9FE · 테두리 #DDD6FE · 글자 VIOLET) 그대로 버튼으로.
    크기 = 카드 안 바로가기 버튼(H._link_a: 폭 가득 · 높이 FOLD_BOX · 모서리 FOLD_RADIUS · 14/20), 위 여백 = 카드 끝 버튼 자리(qc.MORE_GAP_TOP − 6)."""
    right = f'<span style="display:inline-flex;flex:none;transform:rotate(-90deg);">{dk.ACC_CHEV.replace("acc-chev", "fc-right")}</span>'
    a = (f'<a href="{href}" style="display:flex;align-items:center;justify-content:center;gap:4px;width:100%;height:{dk.FOLD_BOX}px;box-sizing:border-box;padding:0 12px;'
         f'background:{HOT_PILL[0]};border:1px solid {HOT_PILL[1]};border-radius:{dk.FOLD_RADIUS}px;color:{dk.VIOLET};font-size:14px;line-height:20px;font-weight:{weight};text-decoration:none;">'
         f'<span style="white-space:nowrap;">Hot Issue 자세히 보기</span>{right}</a>')
    return f'<span data-qmore-end="1" style="display:block;padding-top:{qc.MORE_GAP_TOP - 6}px;">{a}</span>'


def stock_card(c, href, weight=700):
    """종목 페이지 오늘 탭 가격 카드 바로 아래 Hot Issue 카드.
    닫힘 = 보라 강조 카드(uncertain): 첫 줄 보라 라벨 `Hot Issue`, 둘째 줄 이슈 제목, 오른쪽 답 = 뉴스 바늘 말(방향 색 — 답에는 보라를 쓰지 않는다) + 접기 버튼.
    펼침 = ① 한 문장(이번 주 뉴스 쪽 + 주가 업종 대비) ② 단계 두 줄(쪽 이름 · 어디까지 · 그 단계의 가장 최근 일) ③ 최근 소식 세 줄(날짜 · 쪽 라벨 · 한 줄) ④ `Hot Issue 자세히 보기 ›` 버튼.
    이슈 페이지가 이미 센 값만 옮긴다 — 새 계산 · AI 0."""
    evs, today, px, word = c["evs"], c["today"], c["px"], c["word"]
    g, b = IW.C["good"], IW.C["bad"]
    ns = IW.news_side(word)
    ink = dk.UP if ns == g else dk.DOWN if ns == b else "#111"
    _, _, g5 = q_price(px, word)
    news = IW.WEEK_DESC[word]
    lines = [(dk.esc(f"최근 일주일은 {news}. ") + rel_move(g5, "같은 기간 "), "rich")]
    hits = {s: IW._stage_hits(evs, s) for s in ("종전", "확전")}
    for s in ("확전", "종전"):   # 더 멀리 간 쪽이 위로 오게 하지 않고 늘 악화 → 수습 차례(이슈 페이지 답 두 줄과 같은 말)
        r = IW._reach(hits[s])
        col = dk.UP if s == "종전" else dk.DOWN
        nm = IW._sp(f'<b style="color:{col};">{dk.esc(IW.SIDE_LABEL[s])}</b>')
        if r is None:
            lines.append(("row", nm, "아직 없음", ""))
            continue
        e = hits[s][r]
        lines.append(("row", nm, f"{IW.C['stages'][s][r][0]} 단계", f"{H.md(e['first'].astimezone(KST).date().isoformat())} {e['title']}"))
    # `최근 소식` 세 줄 삭제 — 바로 아래 뉴스 구획과 겹친다
    lines.append((hot_btn(href, weight), "html"))
    card = qc.question_card("@@HOT@@", f'<span style="color:{ink};">{dk.esc(word)}</span>', "uncertain", ink, lines)
    pill = (f'<span style="display:inline-block;background:{HOT_PILL[0]};border:1px solid {HOT_PILL[1]};color:{dk.VIOLET};border-radius:4px;padding:3px 5px 2px;'
            f'font-size:{dk.PILL_SIZE};font-weight:700;line-height:1;white-space:nowrap;">Hot Issue</span>')
    head = (f'<span style="display:flex;flex-direction:column;align-items:flex-start;gap:6px;">{pill}'
            f'<span style="word-break:keep-all;">{dk.esc(ISS["q"])}</span></span>')
    card = card.replace('<span style="white-space:nowrap;">@@HOT@@</span>', head, 1)
    return f'<div data-cards="1" style="margin:0 0 8px;">{qc.end_fix(card) if hasattr(qc, "end_fix") else card}</div>'


def stock_page(c, href):
    """종목 페이지 목업 — 가격 카드 바로 아래에 Hot Issue 카드를 끼운다 (발행 코드 render_pages 는 안 고침)."""
    import re
    if not os.path.exists(STOCK_PAGE):
        return None
    s = open(STOCK_PAGE, encoding="utf-8").read()
    i = s.find(PRICE_CARD)
    if i < 0:
        return None
    depth, end = 0, None
    for t in re.finditer(r"<div\b|</div>", s[i:]):
        depth += 1 if t.group(0) == "<div" else -1
        if depth == 0:
            end = i + t.end()
            break
    return s[:end] + stock_card(c, href) + s[end:]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(IW.OUT, exist_ok=True)
    c = collect()
    fn = IW.CFG["NVDA_CEO"]["file"]
    print(dk.write_mock(return_variants(c) + page(c), os.path.join(IW.OUT, fn), IW.HEAD_TITLE))
    sp = stock_page(c, fn)
    # 버튼 글자 굵기 시안 A(굵게) · B(보통) — 펼친 카드 둘 나란히
    cmp_ = ('<p style="margin:16px 6px 20px;font-size:14px;line-height:21px;color:#6B7280;">종목 페이지 Hot Issue 카드의 `Hot Issue 자세히 보기` 버튼 글자 굵기 시안입니다. '
            '버튼 색 = Hot Issue 라벨 색. 둘 다 펼친 상태입니다.</p>')
    for k, (w, nm) in enumerate(((700, "A. 굵게 (700, 지금 카드 안 버튼과 같음)"), (400, "B. 보통 (400)"))):
        card = stock_card(c, fn, w).replace('<details data-acc="1">', '<details data-acc="1" open>', 1)
        cmp_ += f'<div style="margin:{0 if k == 0 else 28}px 0 8px;font-size:16px;line-height:24px;font-weight:700;color:#111;">{nm}</div>' + card
    print(dk.write_mock(f'<div data-head-title="Hot Issue 버튼 시안">{cmp_}</div>', os.path.join(IW.OUT, "mock_stock_issue_btn.html"), "Hot Issue 버튼 시안"))
    if sp:
        print(dk.write_mock(sp, os.path.join(IW.OUT, "mock_stock_issue_nvda_page.html"), "엔비디아 NVDA 주가"))
