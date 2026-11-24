"""발행 시간 — 모든 서비스의 기준 발행 시각과 실제 시각, 늦은 날은 왜 늦었는지 (2026-11-24 사용자).

    "독자들한테 공지한 시간… 약속한 발행 시간에 실패했으면 그 누적 그래프를 계속 그려줘."
    "우리 발행시간 체크 페이지에서 모든 서비스의 기준 발행시간을 알고 싶고 왜 기준시간에 발행이 안되는지 현황 파악하고 싶다."
    (독자에게 새 시각을 알리지는 않는다 — 내부 기준은 이 페이지에만)

비교 대상(헌법 제1조) = 서비스마다 기준 시각.
  - 독자 약속 = 독자에게 알린 시각(안내 상자 · 홈 카드). 페이지에 `독자 약속` 으로 표시
  - 내부 기준 = 알리지 않은 서비스 — 11-14~24 실제 시각을 보고 정한 `보통 끝나는 시각`. 페이지에 `내부 기준`
실제 시각 (모두 공개 기록 · AI 0):
  - 글 = Blogger 공개 피드 게시 시각
  - 화면 자료 = gh-pages 파일 커밋 시각(GitHub API) — 그 시각 뒤 첫 커밋
  - 간단 종목 = 그 시장 quick-data 실행이 끝난 시각(GitHub Actions, 5분 넘게 돈 성공 실행)
판정: 기준 + GRACE_MIN 분 안 = 정시 · 그 뒤 = 늦음 · 그날 없음 = 안 나감 · 오늘 기준 전 = 기다림 · EXCLUDE = 제외.
원인(늦음 · 안 나감만): 그날 맡은 워크플로 실행 기록(GitHub Actions)으로 —
  앞 단계 늦음(이어 붙는 서비스) · 실행 없음(예약이 안 옴) · 실패(실패한 단계 이름) · 늦게 시작(예약보다 N분) · 오래 걸림(가장 오래 걸린 단계)
  지난 날 원인은 바뀌지 않으므로 cache(KV dash:ontime-why)에 두고 다시 묻지 않는다.

    python experiments/ops-dashboard/ontime.py        → output/ontime.html (로컬 — GITHUB_TOKEN 이 있으면 원인까지)
"""
import datetime as dt
import os
import re
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import design_kit as dk  # noqa: E402
import mock_ops as M  # noqa: E402

QC = M.QC
esc, V = dk.esc, dk.violet
NOTE_C = dk.NOTE
ok, warn, idle, over, white_card, chart_top = M.ok, M.warn, M.idle, M.over, M.white_card, M.chart_top

BLOG = "https://www.newfact.app"
REPO = "red6keep-droid/alphascope"
KST = dt.timezone(dt.timedelta(hours=9))
UA = {"User-Agent": "alphascope-ops-dashboard"}
START = dt.date(2026, 11, 1)    # 기록 시작
GRACE_MIN = 10                  # 기준 시각 10분 뒤까지 정시 (`무렵`)
GRID_DAYS = 7                   # `최근` 표 날짜 칸 수 — 폰 폭. 지난 날 전부는 `원인` 탭 목록 · 누적 그래프에

US_HOL = set(dk.US_HOLIDAYS)
KR_HOL = set(dk.KR_HOLIDAYS)


def _us_day(d):
    """KST d 아침 미국 자료 = 전날(미국 날짜)이 미국 장날 — KST 화~토, 미국 휴장 다음 날 빼고."""
    p = d - dt.timedelta(days=1)
    return p.weekday() < 5 and p.isoformat() not in US_HOL


def _us_am_day(d):
    """미국 시황 아침 편 — 실제로 나온 날(11-21 토 · 11-23 월)에 맞춰 월~토."""
    return d.weekday() < 6 and (d - dt.timedelta(days=1 if d.weekday() else 3)).isoformat() not in US_HOL


def _kr_day(d):
    return d.weekday() < 5 and d.isoformat() not in KR_HOL


def _every(d):
    return True


# ---------------------------------------------------------------- 서비스 표
# key · 이름 · 짧은 이름(표) · 기준 · 독자 약속인가 · 근거 · 시작일 · 날 · 자료 · 워크플로 · 예약 시작(KST) · 앞 단계 key
#   자료 = ("post", 라벨 고르기) · ("file", gh-pages 경로, 이 시각 뒤 첫 커밋) · ("run", 워크플로, run-name 끝)
SERVICES = [
    dict(key="news_am", name="홈 주요 뉴스 (아침)", short="뉴스 아침", at="07:00", reader=False, why="예약 06:45 · 보통 06:46 끝",
         since=dt.date(2026, 11, 14), due=_every, src=("file", "news.json", "05:00"), wf="news.yml", start="06:45"),
    dict(key="us_report", name="미국 증시 리포트", short="미국 리포트", at="08:00", reader=True, why="안내 상자 `아침 8시 무렵` (11.24까지 7시 30분)",
         since=START, due=_us_day, src=("post", lambda e: "데일리 브리핑" in e["labels"]), wf="test-daily-report.yml", start="06:40"),
    dict(key="issue_am", name="Hot Issue (아침)", short="Hot Issue", at="08:00", reader=False, why="미국 종목 실행 안 · 보통 07:34~07:40",
         since=dt.date(2026, 11, 14), due=_every, src=("file", "issues.json", "05:00"), wf="nvda-report.yml", start="07:30", up="us_report"),
    dict(key="hypo_am", name="증시 전망 (아침 판정)", short="전망 아침", at="08:00", reader=False, why="미국 종목 실행 안 · 보통 07:34~07:40",
         since=dt.date(2026, 11, 14), due=_every, src=("file", "hypo.json", "05:00"), wf="nvda-report.yml", start="07:30", up="us_report"),
    dict(key="us_pages", name="미국 종목 페이지", short="미국 종목", at="08:00", reader=True, why="안내 상자 `아침 8시 무렵` (11.24까지 7시 30분) · 검색 색인 커밋",
         since=dt.date(2026, 11, 14), due=_us_day, src=("file", "search/us.json", "05:00"), wf="nvda-report.yml", start="07:30", up="us_report"),
    dict(key="themes", name="테마 페이지", short="테마", at="08:10", reader=False, why="미국 종목 실행 끝 무렵 · 보통 08:05~08:13 · 바뀐 날만 올려 화~토만 셈",
         since=dt.date(2026, 11, 14), due=_us_day, src=("file", "themes.json", "05:00"), wf="nvda-report.yml", start="07:30", up="us_report"),
    dict(key="radar", name="주요 인물 발언", short="인물 발언", at="08:30", reader=False, why="미국 종목 뒤 이어 붙이기 · 보통 08:22~08:37",
         since=START, due=_every, src=("post", lambda e: "인물 발언" in e["labels"]), wf="people-radar.yml", start="08:00", up="us_pages"),
    dict(key="us_brief", name="미국 증시시황 (아침 편)", short="미국 시황", at="08:40", reader=True, why="홈 시황 카드 `08:40`",
         since=dt.date(2026, 11, 21), due=_us_am_day, src=("post", lambda e: "증시 시황" in e["labels"] and "미국 증시" in e["labels"]),
         wf="commentary.yml", start="08:40", up="us_report"),
    dict(key="quick_us", name="간단 종목 853 (미국)", short="간단 미국", at="09:00", reader=True, why="안내 상자 `아침 9시 무렵` (11.24 고침)",
         since=dt.date(2026, 11, 17), due=_us_day, src=("run", "quick-data.yml", "· us"), wf="quick-data.yml", start="08:20", up="us_pages"),
    dict(key="kr_report", name="한국 증시 리포트", short="한국 리포트", at="16:30", reader=True, why="안내 상자 `오후 4시 30분 무렵` (11.23까지 4시 10분)",
         since=START, due=_kr_day, src=("post", lambda e: "한국 증시 리포트" in e["labels"]), wf="kr-stocks.yml", start="15:50"),
    dict(key="kr_pages", name="한국 종목 페이지", short="한국 종목", at="16:30", reader=True, why="안내 상자 `오후 4시 30분 무렵` (11.23까지 4시 10분) · 검색 색인 커밋",
         since=dt.date(2026, 11, 14), due=_kr_day, src=("file", "search/kr.json", "15:00"), wf="kr-stocks.yml", start="15:50"),
    dict(key="kr_home", name="한국 홈 시세", short="한국 홈", at="16:30", reader=False, why="한국 종목 실행 안 · kr.json",
         since=dt.date(2026, 11, 14), due=_kr_day, src=("file", "kr.json", "15:00"), wf="kr-stocks.yml", start="15:50"),
    dict(key="hypo_pm", name="증시 전망 (한국 판정)", short="전망 한국", at="16:40", reader=False, why="한국 장 마감 뒤 forecast-kr · 보통 16:08~16:29",
         since=dt.date(2026, 11, 17), due=_kr_day, src=("file", "hypo.json", "15:00"), wf="kr-stocks.yml", start="15:50"),
    dict(key="quick_kr", name="간단 종목 853 (한국)", short="간단 한국", at="17:00", reader=True, why="안내 상자 `오후 5시 무렵` (11.24 고침)",
         since=dt.date(2026, 11, 17), due=_kr_day, src=("run", "quick-data.yml", "· kr"), wf="quick-data.yml", start="16:40", up="kr_pages"),
    dict(key="kr_brief", name="한국 증시시황 (저녁 편)", short="한국 시황", at="21:00", reader=True, why="홈 시황 카드 `21:00`",
         since=dt.date(2026, 11, 20), due=_kr_day, src=("post", lambda e: "증시 시황" in e["labels"] and "한국 증시" in e["labels"]),
         wf="commentary.yml", start="17:00"),
    dict(key="news_pm", name="홈 주요 뉴스 (저녁)", short="뉴스 저녁", at="22:00", reader=False, why="예약 21:45 · 보통 21:46 끝",
         since=dt.date(2026, 11, 14), due=_every, src=("file", "news.json", "21:00"), wf="news.yml", start="21:45"),
]
BY_KEY = {s["key"]: s for s in SERVICES}

# 기준을 바꾼 이력 — 그 날짜 전은 옛 시각으로 판정 (기록을 고쳐 쓰지 않는다)
AT_BEFORE = {
    "kr_report": [(dt.date(2026, 11, 24), "16:10")], "kr_pages": [(dt.date(2026, 11, 24), "16:10")],   # 11-24 안내 4시 30분으로
    "us_report": [(dt.date(2026, 11, 25), "07:30")], "us_pages": [(dt.date(2026, 11, 25), "07:30")],   # 11-24 안내 아침 8시로
}

# 세지 않는 날 — (key, 날짜): 까닭
_BUG = "코드 오류(Python 3.10 SyntaxError)로 미국 리포트가 세 번 멈춤 — 사용자 제외"
EXCLUDE = {(k, dt.date(2026, 11, 24)): _BUG for k in ("us_report", "us_brief", "us_pages", "issue_am", "hypo_am", "themes", "radar", "quick_us")}


# 예약 시작을 바꾼 이력 — 원인 `늦게 시작` 을 그날 예약과 견준다 (cron-trigger · 워크플로 주석 기준)
START_BEFORE = {
    "kr_report": [(dt.date(2026, 11, 20), "16:10")], "kr_pages": [(dt.date(2026, 11, 20), "16:10")],   # 11-20 한국 실행 16:10 → 15:50
    "kr_home": [(dt.date(2026, 11, 20), "16:10")], "hypo_pm": [(dt.date(2026, 11, 20), "16:10")],
    "us_report": [(dt.date(2026, 11, 20), "07:00")],   # 11-20 미국 실행 한 줄로 — 07:00 → 06:40
    "quick_kr": [(dt.date(2026, 11, 20), "17:40")],
}


def start_on(key, d):
    for until, old in START_BEFORE.get(key, []):
        if d < until:
            return old
    return BY_KEY[key]["start"]


def at_on(key, d):
    for until, old in AT_BEFORE.get(key, []):
        if d < until:
            return old
    return BY_KEY[key]["at"]


def _hhmm(x):
    return dt.time(int(x[:2]), int(x[3:]))


# ---------------------------------------------------------------- 자료 읽기
_TITLE_DATE = re.compile(r"(\d{4})년 (\d{1,2})월 (\d{1,2})일")
_TITLE_MD = re.compile(r"^(\d{1,2})\.(\d{1,2}) ")


def _date_by_title(e):
    """제목 날짜(`2026년 11월 21일` · `11.21 증시 시황`)가 있으면 그 날, 없으면 게시 KST 날짜."""
    m = _TITLE_DATE.search(e["title"])
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    m = _TITLE_MD.match(e["title"])
    if m:
        y = e["pub"].year - (1 if e["pub"].month == 1 and int(m[1]) == 12 else 0)
        return dt.date(y, int(m[1]), int(m[2]))
    return e["pub"].date()


def fetch_posts(since):
    start = dt.datetime.combine(since - dt.timedelta(days=1), dt.time(), KST).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out, idx = [], 1
    for _ in range(40):
        r = requests.get(f"{BLOG}/feeds/posts/summary", params={"alt": "json", "max-results": 150, "published-min": start, "start-index": idx},
                         headers=UA, timeout=30)
        r.raise_for_status()
        es = (r.json().get("feed") or {}).get("entry") or []
        for e in es:
            pub = dt.datetime.fromisoformat(e["published"]["$t"]).astimezone(KST)
            link = next((x["href"] for x in e.get("link") or [] if x.get("rel") == "alternate"), "")
            out.append({"title": e["title"]["$t"], "labels": {c["term"] for c in e.get("category") or []}, "pub": pub, "url": link})
        idx += len(es)
        if not es:
            break
    return out


def _gh_headers():
    h = {"Accept": "application/vnd.github+json", **UA}
    if os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    return h


def gh(path, params=None):
    r = requests.get(f"https://api.github.com/repos/{REPO}{path}", headers=_gh_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _t(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(KST)


def fetch_commits(path, since):
    out = []
    for page in range(1, 8):
        js = gh("/commits", {"sha": "gh-pages", "path": path, "since": f"{since - dt.timedelta(days=1)}T00:00:00Z", "per_page": 100, "page": page})
        out += [(_t(c["commit"]["committer"]["date"]), c.get("html_url", "")) for c in js]
        if len(js) < 100:
            break
    return out


def fetch_runs(wf, since):
    """워크플로 실행 — [{id, start, end, event, concl, title, url}] (created ≥ since 전날 KST)."""
    out = []
    for page in range(1, 11):
        js = gh(f"/actions/workflows/{wf}/runs", {"created": f">={since - dt.timedelta(days=1)}", "per_page": 100, "page": page})
        rs = js.get("workflow_runs") or []
        for r in rs:
            out.append({"id": r["id"], "start": _t(r.get("run_started_at") or r["created_at"]), "end": _t(r["updated_at"]), "event": r.get("event", ""),
                        "status": r.get("status"), "concl": r.get("conclusion") or "", "title": r.get("display_title") or "", "url": r.get("html_url", "")})
        if len(rs) < 100:
            break
    return out


# ---------------------------------------------------------------- 실제 시각
def actuals(svc, posts, commits, runs):
    """→ {날짜: (시각, 주소)} — 그날 첫 것."""
    kind = svc["src"][0]
    first = {}

    def put(d, t, url):
        if d not in first or t < first[d][0]:
            first[d] = (t, url)

    if kind == "post":
        for p in posts:
            if svc["src"][1](p):
                put(_date_by_title(p), p["pub"], p["url"])
    elif kind == "file":
        after = _hhmm(svc["src"][2])
        for t, url in commits.get(svc["src"][1]) or []:
            if t.time() >= after:
                put(t.date(), t, url)
    else:   # run — 그 시장 실행 가운데 5분 넘게 돈 성공 실행이 끝난 시각
        for r in runs.get(svc["src"][1]) or []:
            if r["title"].endswith(svc["src"][2]) and r["concl"] == "success" and (r["end"] - r["start"]).total_seconds() >= 300:
                put(r["end"].date(), r["end"], r["url"])
    return first


def judge(svc, first, now):
    """→ [(날짜, 상태, 실제 시각 | None, 늦은 분, 주소)]."""
    out, d = [], svc["since"]
    while d <= now.date():
        if svc["due"](d):
            t, url = first.get(d, (None, ""))
            if (svc["key"], d) in EXCLUDE:
                out.append((d, "skip", t, 0, url))
            else:
                promise = dt.datetime.combine(d, _hhmm(at_on(svc["key"], d)), KST)
                limit = promise + dt.timedelta(minutes=GRACE_MIN)
                if t:
                    late = round((t - promise).total_seconds() / 60)
                    out.append((d, "on" if t <= limit else "late", t, late, url))
                elif now <= limit:
                    out.append((d, "wait", None, 0, ""))
                else:
                    out.append((d, "miss", None, round((now - promise).total_seconds() / 60), ""))
        d += dt.timedelta(days=1)
    return out


# ---------------------------------------------------------------- 원인
TAGS = ["앞 단계 늦음", "실행 없음", "실패", "늦게 시작", "여유 부족", "오래 걸림", "다시 돌림", "원인 못 찾음"]


def _steps(run_id):
    js = gh(f"/actions/runs/{run_id}/jobs", {"per_page": 50})
    return [(j.get("name", ""), s) for j in js.get("jobs") or [] for s in j.get("steps") or []]


def why(svc, d, st, t, res_by_key, runs):
    """늦음 · 안 나감 하나의 원인 → (태그 목록, 글). 실행 기록이 없으면 ([`원인 못 찾음`], …)."""
    tags, bits = [], []
    up = svc.get("up")
    if up:
        u = next((x for x in res_by_key.get(up, []) if x[0] == d), None)
        if u and u[1] in ("late", "miss", "skip"):
            tags.append("앞 단계 늦음")
            bits.append(f"앞 단계 {BY_KEY[up]['short']} " + (f"{_hm(u[2])}" if u[2] else "안 나감"))
    st_at = start_on(svc["key"], d)
    sched = dt.datetime.combine(d, _hhmm(st_at), KST)
    end = t or dt.datetime.combine(d, dt.time(23, 59), KST)
    rs = [r for r in runs.get(svc["wf"]) or [] if sched - dt.timedelta(hours=2) <= r["start"] <= end]
    if svc["src"][0] == "run":
        rs = [r for r in rs if r["title"].endswith(svc["src"][2])]
    if runs.get(svc["wf"]) is None:
        return (tags or ["원인 못 찾음"]), (" · ".join(bits) or "실행 기록을 읽지 못함")
    if not rs:
        tags.append("실행 없음")
        bits.append(f"{st_at} 예약 뒤 {svc['wf'].replace('.yml', '')} 실행이 없음")
        return tags, " · ".join(bits)
    # 실패 = 실패 · 시간 초과 · 5분 넘게 돌다 취소(겹친 실행이 곧바로 취소된 것은 빼고)
    bad = [r for r in rs if r["concl"] in ("failure", "timed_out") or (r["concl"] == "cancelled" and (r["end"] - r["start"]).total_seconds() >= 300)]
    if bad:
        r = bad[0]
        step = ""
        try:
            step = next((f"{s['name']}" for _, s in _steps(r["id"]) if s.get("conclusion") == "failure"), "")
        except Exception:  # noqa: BLE001
            pass
        word = {"failure": "실패", "cancelled": "취소", "timed_out": "시간 초과"}[r["concl"]]
        tags.append("실패")
        bits.append(f"{_hm(r['start'])} 실행 {word}" + (f" — `{step}`" if step else "") + (f" (모두 {len(bad)}번)" if len(bad) > 1 else ""))
    first = min(rs, key=lambda r: r["start"])
    gap = round((first["start"] - sched).total_seconds() / 60)
    if gap > 10 and "앞 단계 늦음" not in tags:
        tags.append("늦게 시작")
        bits.append(f"예약 {st_at} → 시작 {_hm(first['start'])} ({gap}분 늦음)")
    good = [r for r in rs if r["concl"] == "success" and (not t or r["end"] >= t - dt.timedelta(minutes=5))]
    main = min(good, key=lambda r: r["start"]) if good else None
    if main and not bad:
        mins = round((main["end"] - main["start"]).total_seconds() / 60)
        if mins >= 20:
            slow = ""
            try:
                ss = [(s["name"], (_t(s["completed_at"]) - _t(s["started_at"])).total_seconds() / 60) for _, s in _steps(main["id"])
                      if s.get("started_at") and s.get("completed_at")]
                if ss:
                    n, m = max(ss, key=lambda x: x[1])
                    slow = f" — 가장 긴 단계 `{n}` {round(m)}분"
            except Exception:  # noqa: BLE001
                pass
            tags.append("오래 걸림")
            bits.append(f"{_hm(main['start'])} 시작 · {mins}분 걸림{slow}")
    # 여유 부족 — 예약 시작부터 기준까지 시간이 실행이 결과를 내는 데 걸린 시간보다 짧다 (11-20 전 한국 = 16:10 예약 · 16:10 약속)
    made = [r for r in rs if t and r["start"] <= t <= r["end"] + dt.timedelta(minutes=5)]
    rerun = bool(made) and made[0]["id"] != first["id"] and made[0]["start"] - first["start"] > dt.timedelta(minutes=30)
    if t and not bad and not rerun and gap <= 10:
        need = round((t - first["start"]).total_seconds() / 60)
        slack = round((dt.datetime.combine(d, _hhmm(at_on(svc["key"], d)), KST) - sched).total_seconds() / 60)
        if need > slack + GRACE_MIN:
            tags.append("여유 부족")
            bits.append(f"예약 {st_at} ~ 기준 {at_on(svc['key'], d)} 여유 {slack}분인데 결과까지 {need}분")
    if rerun:   # 결과가 나온 실행이 첫 실행이 아니면 — 다시 돌린 실행
        how = {"workflow_dispatch": "수동 · Worker", "schedule": "GitHub 예약", "workflow_run": "이어 붙이기"}.get(made[0]["event"], made[0]["event"])
        tags.append("다시 돌림")
        bits.append(f"{_hm(made[0]['start'])} 다시 돌린 실행({how})에서 나감")
    if not tags:
        tags.append("원인 못 찾음")
        bits.append(f"실행 {len(rs)}번 · 첫 시작 {_hm(first['start'])} — 실행은 제때였는데 결과가 늦음(게시 · 올리기 단계 확인)")
    pairs = sorted(zip(tags, bits), key=lambda x: TAGS.index(x[0]))   # 원인 순서 고정 — 앞 단계 · 실행 없음 · 실패 · 늦게 시작 · 여유 부족 · 오래 걸림 · 다시 돌림
    return [x[0] for x in pairs], " · ".join(x[1] for x in pairs)


# ---------------------------------------------------------------- 그리기 도우미
def _hm(t):
    return t.astimezone(KST).strftime("%H:%M")


def _md(d):
    return f"{d.month}.{d.day}"


def _late_text(m):
    return f"{m // 60}시간 {m % 60}분" if m >= 60 else f"{m}분"


def _pill(st, late):
    if st == "on":
        return ok("정시")
    if st == "late":
        return warn(f"{_late_text(late)} 늦음")
    if st == "miss":
        return warn("안 나감")
    if st == "skip":
        return idle("제외")
    return idle("기다림")


def _link(url, text):
    return f'<a href="{esc(url)}" style="color:inherit;">{esc(text)}</a>' if url else esc(text)


WEEK = "월화수목금토일"
GOOD, BAD, GRAY, LINE = "#15803D", "#C2410C", "#94A3B8", "#E2E8F0"


def _cell(x):
    """표 칸 — 실제 시각(누르면 글 · 커밋 · 실행), 색 = 판정."""
    if not x:
        return f'<span style="color:{LINE};">·</span>'
    d, st, t, m, url = x
    if st == "miss":
        return f'<span style="color:{BAD};font-weight:700;">없음</span>'
    if st == "wait":
        return f'<span style="color:{GRAY};">대기</span>'
    if st == "skip":
        return f'<span style="color:{GRAY};">{_link(url, _hm(t)) if t else "제외"}</span>'
    col = GOOD if st == "on" else BAD
    sub = f'<br><span style="font-size:11px;font-weight:400;">+{f"{m // 60}:{m % 60:02d}" if m >= 60 else f"{m}분"}</span>' if st == "late" else ""
    return f'<span style="color:{col};font-weight:{700 if st == "late" else 400};">{_link(url, _hm(t))}{sub}</span>'


def grid(res, now):
    """최근 GRID_DAYS 날 표 — 줄 = 서비스(기준 시각 순), 칸 = 날짜(최신 오른쪽)."""
    days = [now.date() - dt.timedelta(days=i) for i in range(GRID_DAYS - 1, -1, -1)]
    th = (f'<th style="width:78px;padding:8px 2px 8px 12px;text-align:left;font-weight:400;font-size:12px;line-height:16px;color:{NOTE_C};">서비스 · 기준</th>'
          + "".join(f'<th style="padding:8px 1px;text-align:center;font-weight:400;font-size:12px;line-height:16px;color:{"#111" if d == now.date() else NOTE_C};">'
                    f'{_md(d)}<br>{WEEK[d.weekday()]}</th>' for d in days))
    rows = ""
    for svc, ds in res:
        by = {x[0]: x for x in ds}
        mark = "" if svc["reader"] else f'<span style="color:{GRAY};"> 내부</span>'
        rows += (f'<tr><td style="border-top:1px solid {LINE};padding:7px 2px 7px 12px;font-size:13px;line-height:17px;color:#333;word-break:keep-all;">'
                 f'{esc(svc["short"])}<br><span style="font-size:11px;color:{NOTE_C};">{at_on(svc["key"], now.date())}{mark}</span></td>'
                 + "".join(f'<td style="border-top:1px solid {LINE};padding:7px 1px;text-align:center;font-size:12px;line-height:16px;white-space:nowrap;">{_cell(by.get(d))}</td>'
                           for d in days) + "</tr>")
    tbl = (f'<table style="display:table;width:100%;border-collapse:collapse;table-layout:fixed;">'
           f'<tr>{th}</tr>{rows}</table>')   # display:table — 테마 .post-body table{display:block} 이 표를 좁게 만든다
    return f'<div data-cards="1" style="margin:0 0 8px;"><span style="{dk.MULTI}">{tbl}</span></div>'


# ---------------------------------------------------------------- 페이지
def _counted(ds):
    return [x for x in ds if x[1] in ("on", "late", "miss")]


def summary(res, now):
    """운영 대시보드 요약 칸 · 할 일 — (값HTML, 보조, 오늘 어긴 것 [(이름, 글)])."""
    allc = [x for _, ds in res for x in _counted(ds)]
    bad = sum(x[1] != "on" for x in allc)
    today = [(svc["name"], _pill(x[1], x[3])) for svc, ds in res for x in ds if x[0] == now.date() and x[1] in ("late", "miss")]
    return (warn(f"늦음 · 안 나감 {bad}번") if bad else ok("모두 정시")), f"서비스 {len(res)}개 · 기준 {len(allc)}번 중 정시 {len(allc) - bad}번", today


def page_body(res, reasons, now):
    allc = [x for _, ds in res for x in _counted(ds)]
    rd = [x for svc, ds in res if svc["reader"] for x in _counted(ds)]
    late = sum(x[1] == "late" for x in allc)
    miss = sum(x[1] == "miss" for x in allc)
    lead = (f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">{now.month}월 {now.day}일 {now:%H:%M} 기준, 서비스 {len(res)}개의 기준 시각 '
            f'{V(f"{len(allc)}번")} 가운데 정시 {V(f"{len(allc) - late - miss}번")}, 늦음 {V(f"{late}번")}, 안 나감 {V(f"{miss}번")}입니다. '
            f'독자에게 알린 약속만 보면 {len(rd)}번 중 정시 {sum(x[1] == "on" for x in rd)}번입니다.</p>')
    head = (f'<div style="display:flex;align-items:center;gap:8px;margin:0 0 12px;padding-left:{dk.ALIGN_PX}px;">'
            f'{dk.solid_icon("clock", M.OPS_COLOR)}'
            f'<span style="font-size:{dk.H2_SIZE};line-height:{dk.LH_H2};font-weight:700;color:#111;">기준 시각에 나갔나?</span></div>')

    # 오늘 — 문제(늦음 · 안 나감) 먼저, 그다음 기다림 · 정시 · 제외. 5개 펼침 + 접기
    order = {"miss": 0, "late": 1, "wait": 2, "on": 3, "skip": 4}
    trows = []
    for svc, ds in res:
        x = next((x for x in ds if x[0] == now.date()), None)
        if not x:
            continue
        d, st, t, m, url = x
        a = at_on(svc["key"], d)
        if t:
            txt = f"기준 {a} → " + _link(url, _hm(t))
        elif st == "wait":
            left = round((dt.datetime.combine(d, _hhmm(a), KST) - now).total_seconds() / 60)
            txt = f"기준 {a} · " + (f"{_late_text(left)} 남음" if left > 0 else f"{GRACE_MIN}분 유예 중")
        else:
            txt = f"기준 {a} · 아직 없음"
        r = reasons.get(f"{svc['key']}|{d}")
        if r:
            txt += " · " + esc(r[1])
        elif st == "skip":
            txt += " · " + esc(EXCLUDE[(svc["key"], d)])
        trows.append((order[st], a, svc["name"] + ("" if svc["reader"] else " (내부 기준)"), _pill(st, m), txt))
    trows.sort(key=lambda r: (r[0], r[1]))
    top = dk.cards(lead + head + dk.sub_label("오늘") + white_card([r[2:] for r in trows], fold_at=5, noun="서비스"))

    # 원인 — 지난 날까지 모든 늦음 · 안 나감, 최신 위. 원인별 횟수(최근 14일 · 전체)
    evs = []
    for svc, ds in res:
        for d, st, t, m, url in ds:
            if st in ("late", "miss"):
                tags, text = reasons.get(f"{svc['key']}|{d}", (["원인 못 찾음"], "실행 기록을 아직 보지 않음"))
                evs.append((d, at_on(svc["key"], d), svc, st, t, m, tags, text))
    evs.sort(key=lambda e: (e[0], e[1]), reverse=True)
    cut = now.date() - dt.timedelta(days=13)
    tally = []
    for tg in TAGS:
        n14 = sum(tg in e[6] for e in evs if e[0] >= cut)
        nall = sum(tg in e[6] for e in evs)
        if nall:
            tally.append((tg, V(f"{n14}번"), f"최근 14일 · 11.1부터 {nall}번"))
    by_svc = sorted(((svc, sum(x[1] != "on" for x in _counted(ds)), len(_counted(ds))) for svc, ds in res), key=lambda x: -x[1])
    svc_rows = [(s["name"], warn(f"{b}번") if b else ok("0번"), f"기준 {s['at']} · 정시 {n - b}/{n}") for s, b, n in by_svc if n]
    ev_rows = [(f"{_md(d)} {svc['short']}", _pill(st, m),
                f"기준 {a} → " + (_hm(t) if t else "없음") + " · " + esc(text)) for d, a, svc, st, t, m, tags, text in evs]

    # 누적 — 모두 · 독자 약속 · 내부 기준
    days = [START + dt.timedelta(days=i) for i in range((now.date() - START).days + 1)]

    def cum(pred):
        c, xs = 0, []
        for d in days:
            c += sum(1 for svc, ds in res if pred(svc) for x in ds if x[0] == d and x[1] in ("late", "miss"))
            xs.append(c)
        return xs

    cumc = chart_top(dk.trend_card("기준 시각을 넘긴 횟수 (누적, 번)", [_md(d) for d in days],
                                   [("모두", cum(lambda s: True), "#111827", "solid"), ("독자 약속", cum(lambda s: s["reader"]), dk.CHART_SERIES[0], "solid"),
                                    ("내부 기준", cum(lambda s: not s["reader"]), dk.CHART_SERIES[1], "solid")],
                                   lambda v: f"{v:.0f}", legend_note=f"늦음 + 안 나감 · 기준 {GRACE_MIN}분 뒤까지 정시"), top=0)

    # 기준 — 모든 서비스
    std = [(s["name"], f"{s['at']}", ("독자 약속 · " if s["reader"] else "내부 기준 · ") + s["why"]
            + " · " + {"post": "글 게시 시각", "file": f"gh-pages {s['src'][1] if s['src'][0] == 'file' else ''} 커밋", "run": "실행 끝 시각"}[s["src"][0]])
           for s in sorted(SERVICES, key=lambda s: s["at"])]

    legend = (f'<p style="margin:4px 0 12px;padding-left:{dk.ALIGN_PX}px;font-size:13px;line-height:19px;color:{NOTE_C};word-break:keep-all;">'
              f'<span style="color:{GOOD};">초록 = 정시</span> · <span style="color:{BAD};font-weight:700;">주황 = 늦음 · 없음</span> · '
              f'회색 = 제외 · 대기 · 점 = 나오지 않는 날. 시각을 누르면 그 글 · 커밋 · 실행이 열립니다. `내부` = 독자에게 알리지 않은 기준.</p>')
    return (top
            + dk.h2("최근", tab="최근") + grid(res, now) + legend
            + dk.h2("원인", tab="원인")
            + dk.sub_label("원인별 횟수", "한 번 늦은 데 원인이 둘이면 둘 다 셉니다.") + white_card(tally or [("늦은 일", ok("없음"), "")])
            + dk.sub_label("서비스별 늦음 · 안 나감") + white_card(svc_rows, fold_at=5, noun="서비스")
            + dk.sub_label("늦은 날 하나하나") + white_card(ev_rows or [("늦은 날", ok("없음"), "")], fold_at=5, noun="건")
            + dk.h2("누적", tab="누적") + cumc
            + dk.h2("기준", tab="기준")
            + dk.sub_label("서비스별 기준 시각") + white_card(std, fold_at=5, noun="서비스")
            + dk.guide("판정", f"기준 시각 {GRACE_MIN}분 뒤까지 정시, 그 뒤는 늦음, 그날 결과가 없으면 안 나감입니다. 오늘 기준 전이면 세지 않습니다. "
                       "원인은 그날 맡은 GitHub 실행 기록으로 봅니다 — 앞 단계 늦음(이어 붙는 서비스) · 실행 없음 · 실패(실패한 단계) · 늦게 시작(예약보다 10분 넘게) · "
                       "여유 부족(예약 ~ 기준 시간보다 실행이 오래 걸림) · 오래 걸림(20분 넘게, 가장 긴 단계) · 다시 돌림(첫 실행이 아닌 실행에서 나감). Hot Issue 오후 · 방송 줄처럼 바뀐 날만 올리는 자료는 `안 나감`을 가릴 수 없어 넣지 않았습니다."))


def build(now, cache=None):
    """→ (페이지 본문, 요약, 원인 cache). cache = {"key|날짜": [태그, 글]} — 오늘이 아닌 날 원인은 다시 묻지 않는다."""
    cache = dict(cache or {})
    posts = fetch_posts(START)
    commits = {p: fetch_commits(p, START) for p in sorted({s["src"][1] for s in SERVICES if s["src"][0] == "file"})}
    res = []
    run_cache = {}

    def runs_for(wf):
        if wf not in run_cache:
            try:
                run_cache[wf] = fetch_runs(wf, START)
            except Exception as e:  # noqa: BLE001
                print(f"[ontime] {wf} 실행 목록 못 읽음 {type(e).__name__}")
                run_cache[wf] = None
        return run_cache[wf]

    for svc in SERVICES:
        runs = {svc["src"][1]: runs_for(svc["src"][1])} if svc["src"][0] == "run" else {}
        res.append((svc, judge(svc, actuals(svc, posts, commits, runs), now)))
    res.sort(key=lambda r: r[0]["at"])
    res_by_key = {svc["key"]: ds for svc, ds in res}
    reasons = {}
    for svc, ds in res:
        for d, st, t, m, url in ds:
            if st not in ("late", "miss"):
                continue
            k = f"{svc['key']}|{d}"
            if k in cache and d < now.date():
                reasons[k] = cache[k]
                continue
            rs = runs_for(svc["wf"])
            reasons[k] = list(why(svc, d, st, t, res_by_key, {svc["wf"]: rs}))
            if d < now.date() and rs is not None:
                cache[k] = reasons[k]
    return page_body(res, reasons, now), summary(res, now), cache


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import build_ops as B
    now = dt.datetime.now(KST)
    body, (val, sub, today), cache = build(now)
    page = B.shell(dk.align_titles(dk.WRAP_OPEN + body + dk.WRAP_CLOSE), now, title="발행 시간")
    os.makedirs(B.OUT, exist_ok=True)
    with open(os.path.join(B.OUT, "ontime.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print(f"[ontime] output/ontime.html {len(page) // 1024}KB · {sub} · 원인 {len(cache)}건 저장할 것")
