"""③단계 — 트럼프 브리지, 한 줄만 (2026-10-10 사용자: "한 줄만 붙여").

trump-trend가 `trump-state` 브랜치에 올린 `trump_analysis.json`(공개 리포, raw URL)을 읽어
그날 NVDA에 닿는 발언 이벤트(기획서 9절 조건: NVDA 매핑 또는 반도체 규칙, 강도 ≥ 5)를 ② "오늘 바뀐 것"에 한 줄로 붙인다.
과거 반응 통계는 trump-trend가 robust(BH 보정 q < 0.10)로 판정한 것이 있을 때만 괄호로 덧붙이고, 없으면 아무 말도 하지 않는다.
실패하면(네트워크·없는 날) 조용히 0건. 상태 파일 날짜가 기준일보다 오래되면 "(전일 기준)"을 붙인다.

    python experiments/nvda-report/trump_bridge.py --day 2026-10-09
"""

import argparse
import datetime
import json
import os
import subprocess
import sys

import requests

import config

DIR_KO = {"positive": "긍정", "negative": "부정", "uncertain": "불확실", "neutral": "중립"}
HORIZON_KO = {"next_close": "다음 날 종가", "close": "당일 종가", "d3": "3일", "d5": "5일", "immediate": "직후"}


def fetch_state():
    """raw URL → 실패하면 로컬 git(origin/trump-state). 둘 다 안 되면 None."""
    try:
        r = requests.get(config.TRUMP_STATE_URL, headers={"User-Agent": config.USER_AGENT}, timeout=30)
        if r.status_code == 200:
            return r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[trump] raw 읽기 실패: {str(e)[:80]}")
    try:
        out = subprocess.run(["git", "show", f"origin/trump-state:{config.TRUMP_STATE_PATH}"],
                             capture_output=True, text=True, timeout=30, cwd=os.path.join(config.BASE_DIR, "..", ".."))
        if out.returncode == 0 and out.stdout.strip():
            return json.loads(out.stdout)
    except Exception as e:  # noqa: BLE001
        print(f"[trump] git 읽기 실패: {str(e)[:80]}")
    return None


def is_nvda_event(e):
    affected = e.get("affected") or e.get("affected_companies") or []
    if isinstance(affected, str):
        affected = [a.strip() for a in affected.split(",")]
    return (config.SYMBOL in affected or e.get("rule_id") in config.TRUMP_SEMI_RULES) and (e.get("intensity") or 0) >= config.TRUMP_MIN_INTENSITY


def robust_stat(state, e):
    """같은 주제(하위주제 우선)의 NVDA 과거 반응 중 robust인 것 하나. 없으면 None."""
    reactions = state.get("reactions") or {}
    keys = [f"{e.get('topic')} / {e.get('subtopic')}", e.get("topic")]
    for k in keys:
        nv = ((reactions.get(k) or {}).get("symbols") or {}).get(config.SYMBOL) or {}
        for hz in ("next_close", "close", "d3", "d5"):
            st = nv.get(hz) or {}
            pl = st.get("placebo") or {}
            if pl.get("robust") and st.get("n"):
                return f"과거 같은 주제 {st['n']}건 NVDA {HORIZON_KO.get(hz, hz)} 중앙값 {st['median']:+.1f}% (q {pl.get('q_bh')})"
    return None


def select(state, day):
    """기준일(effective_day 또는 발언일)의 NVDA 이벤트만."""
    out = []
    for e in state.get("recent_events") or []:
        e_day = e.get("effective_day") or (e.get("first_post_at") or "")[:10]
        if e_day == day and is_nvda_event(e):
            out.append(e)
    return out


def events(day):
    """judge가 부르는 진입점. _ev 모양의 dict 목록."""
    state = fetch_state()
    if not state:
        return []
    gen = (state.get("generated_at") or "")[:10]
    stale = " (트럼프 데이터 전일 기준)" if gen and gen < day else ""
    out = []
    for e in select(state, day):
        topic = f"{e.get('topic')}" + (f"/{e.get('subtopic')}" if e.get("subtopic") else "")
        title = (f"트럼프 발언 — {topic} · 강도 {e.get('intensity')} · {DIR_KO.get(e.get('direction'), e.get('direction'))}"
                 + (f" · {e['path_text']}" if e.get("path_text") else "") + stale)
        stat = robust_stat(state, e)
        area = "Corporate" if e.get("topic") == "Company" else "Regulation"
        out.append({"area": area, "kind": "trump", "title": title, "fact": stat or title, "url": config.TRUMP_POST_URL or None,
                    "direction": e.get("direction") or "uncertain", "emphasis": True, "source": "trump-trend",
                    "published_at": e.get("first_post_at")})
    if out:
        print(f"[trump] NVDA 관련 발언 {len(out)}건{stale}")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=datetime.date.today().isoformat())
    a = ap.parse_args()
    for ev in events(a.day):
        print(ev)
    print("(끝)")
