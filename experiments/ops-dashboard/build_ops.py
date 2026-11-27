"""운영 대시보드 — 실제 자료로 그린다.

    python experiments/ops-dashboard/build_ops.py                       → output/ops.html (로컬 확인)
    python experiments/ops-dashboard/build_ops.py --state-heads FILE --upload   → KV dash:html (워크플로 ops-dashboard.yml)

모양은 목업(mock_ops.py)과 같은 도우미 · 공용 부품(design_kit · daily-report/cards)으로 그린다 — 디자인 규칙의 원본이 하나.
관리자 전용 Worker(infra/ops-console)가 로그인을 확인한 뒤 KV 의 dash:html 을 그대로 보낸다. 블로그 테마 CSS · JS 로 감싸
탭 · 서브탭 · 툴팁 · 더 보기가 블로그와 똑같이 움직인다.

자료 (AI 0 · 시세 API 0, 이미 있는 기록만 읽는다):
  - 운영 기록: Cloudflare KV ops:{날짜}:… (experiments/ops_log.py 가 실행마다 씀) — 발행 · AI 사용량 · 수집 실패
  - GitHub Actions 실행 목록 (공개 저장소, GITHUB_TOKEN)
  - gh-pages 데이터 파일(raw.githubusercontent.com) — 독자 화면의 갱신 시각 · 종목 색인 · 증시 전망 목록 · 크기(트리 API 1회)
  - Blogger 공개 피드 — 최근 14일 새 글 수
  - 상태 저장소(비공개) 브랜치 마지막 커밋 시각 — 워크플로가 --state-heads 파일로 넘긴다
가짜 값은 없다. 읽지 못한 자료는 그 칸에 `읽지 못함` 으로 적는다.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import Counter, defaultdict

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import design_kit as dk  # noqa: E402
import mock_ops as M  # noqa: E402  — 같은 도우미(ok · warn · idle · over · white_card · chart_top · head_row)
import ontime  # noqa: E402  — 발행 시간 페이지 (/ontime)

QC = M.QC
esc, V = dk.esc, dk.violet
ok, warn, idle, over, white_card, chart_top = M.ok, M.warn, M.idle, M.over, M.white_card, M.chart_top

REPO = "red6keep-droid/alphascope"
BLOG = "https://www.newfact.app"
RAW = f"https://raw.githubusercontent.com/{REPO}/gh-pages/"
KST = dt.timezone(dt.timedelta(hours=9))
PT_OFFSET = -8   # 태평양 표준시(11월 ~ 3월). 서머타임이면 -7 — Gemini 하루 한도가 이 자정에 초기화된다 (AI-모델-현황 7절)
OUT = os.path.join(HERE, "output")
UA = {"User-Agent": "alphascope-ops-dashboard"}

# 정기 실행 — 이름 · 파일 · 예정(KST 시각, 요일 0=월). infra/cron-trigger JOBS 와 같게. 늦게 시작해도 경고하지 않도록 예정 + 90분부터 `실행 없음`
WORKFLOWS = [
    ("미국 종목 뉴스 먼저 분류", "radar-news-early.yml", "04:30", (1, 2, 3, 4, 5)),   # 2026-11-20 — 엔비디아 실행 뉴스 분류를 장 마감 전에
    ("미국 증시 리포트", "test-daily-report.yml", "06:40", (1, 2, 3, 4, 5)),   # 옛 07:00 — 미국 실행 한 줄로(2026-11-20), 엔비디아 · 인물 발언은 이어 붙이기(예정 시각은 예비)
    ("미국 종목 · ETF · 전망", "nvda-report.yml", "07:30", (0, 1, 2, 3, 4, 5, 6)),
    ("인물 발언", "people-radar.yml", "08:00", (0, 1, 2, 3, 4, 5, 6)),
    ("방송 브리핑", "media-daily.yml", "08:00", (0, 1, 2, 3, 4)),
    ("한국 종목 · 한국 증시 리포트", "kr-stocks.yml", "15:50", (0, 1, 2, 3, 4)),   # 옛 16:10 (2026-11-20)
    ("홈 시세", "update.yml", "10:00", (0, 1, 2, 3, 4)),
    ("홈 뉴스", "news.yml", "06:45", (0, 1, 2, 3, 4, 5, 6)),
    ("집 IP 받기 (미래에셋 · 버리)", "home-ip.yml", "14:30", (0, 1, 2, 3, 4, 5, 6)),   # 2026-11-17 집 공유기 VPN
    ("간단 종목 한국 DART 새벽 받기", "quick-dart.yml", "03:25", (0, 1, 2, 3, 4, 5, 6)),   # 2026-11-20 — 장 마감 뒤 실행에서 뺌(GitHub cron)
    # 하루 여러 번 도는 것은 첫 예약 시각만(그 뒤 실행은 같은 줄 `n번` 으로 셈)
    ("간단 종목 뉴스", "quick-news.yml", "06:20", (1, 2, 3, 4, 5)),
    ("간단 종목 853 주가", "quick-data.yml", "08:20", (1, 2, 3, 4, 5)),   # 미국 08:20(화~토) · 한국 16:40(평일)
    ("증시 시황 해설", "commentary.yml", "08:40", (0, 1, 2, 3, 4, 5, 6)),   # 아침 08:40 · 저녁 17:00(평일) · 21:00
    ("한국 기사 공용 저장소", "kr-facts.yml", "09:20", (0, 1, 2, 3, 4, 5, 6)),   # 09:20 · 12:20 · 15:20(평일) · 18:20
    ("Newfact 뉴스 발행", "news-posts.yml", "09:50", (0, 1, 2, 3, 4, 5, 6)),   # 09:50 · 13:50 · 16:10(평일, 기준일 고치기) · 18:50 · 22:50
    ("간단 종목 새 페이지", "quick-shells-new.yml", "23:40", (0, 1, 2, 3, 4, 5, 6)),
    ("기록 사본", "state-backup.yml", "23:40", (0, 1, 2, 3, 4, 5, 6)),
    ("트럼프 기록", "trump-trend.yml", "", ()),
    ("소송 조사", "court-survey.yml", "", ()),
    ("Gemini 모델 점검", "gemini-model-check.yml", "", ()),
]
COMMENT_WF = "comment-reply.yml"

# 하루 한도 (doc/운영/AI-모델-현황.md 7 · 7-1절). kind = req(요청 수) · tok(토큰). 단계 이름 = llm_chain.STEPS 키 (운영 기록 usage 의 키)
# llm_chain 에 새 단계를 넣으면 여기에도 한 줄 — 빠뜨려도 운영 기록에 나온 단계는 아래 ai_tab 이 `한도 표 없음` 줄로 따로 보여 준다
MODELS = [
    ("Gemini flash", "gemini", "req", 20, "pt"),
    ("Gemini 3.5 lite", "gemini-lite", "req", 500, "pt"),
    ("Gemini 3.1 lite", "gemini-lite31", "req", 500, "pt"),      # 2026-11-15 news-quick · kr-lead 첫 자리 (3.5 lite 와 따로 셈)
    ("Gemma 4 26B", "gemma-26b", "req", 14_400, "pt"),            # 2026-11-15 news-quick 셋째. 실제 상한은 분당 토큰 1만 6천
    ("Groq gpt-oss", "groq", "tok", 200_000, "24h"),
    ("Groq Qwen", "groq-qwen", "tok", 200_000, "24h"),
    ("NVIDIA DeepSeek", "nvidia-deepseek", "req", 0, "24h"),
]

# 독자 화면 파일 — (이름, gh-pages 경로, 기준 문구, 늦음 판정)
SCREEN_FILES = [
    ("미국 홈 시세", "data.json", "평일 장 마감 뒤 하루 안"),
    ("한국 홈 · 한국 증시", "kr.json", "한국 장 마감(15:50 실행) 뒤"),
    ("홈 뉴스", "news.json", "하루 2번 (06:45 · 21:45)"),
    ("미국 증시 리포트 카드", "cards/report.json", "평일 아침"),
    ("한국 증시 리포트 카드", "cards/kr-report.json", "한국 장 마감 뒤"),
    ("인물 발언 카드", "cards/radar.json", "매일 아침"),
    ("증시 전망 카드", "hypo.json", "매일 아침"),
    # themes.json 은 바뀐 날만 올라가 시각으로 늦음을 가리지 못해 넣지 않음
    ("Hot Issue 카드", "issues.json", "매일 아침"),
    ("Newfact 주요 기사 카드", "news-posts.json", "하루 4번 (09:50 · 13:50 · 18:50 · 22:50)"),
    ("한국 기사 사실 (kr-facts)", "kr-facts.json", "하루 2~4번 (09:20 ~ 18:20)"),
]
STALE_HOURS = {"news.json": 16, "news-posts.json": 16, "kr-facts.json": 16}   # 밤 사이 가장 긴 빈틈 + 여유. 그 밖은 30시간

# 지금의 실패 줄 규칙 = ops_log._WARN 과 같게 (import 하면 이 실행도 운영 기록을 남긴다). 이미 쌓인 기록을 다시 거른다 — `40건` · `신규 0건` 오탐 (2026-11-21)
WARN_NOW = re.compile(r"실패|::warning::|::error::|Forbidden|Traceback|오류|에러|중단|(?<![\d,.])(?<!신규 )(?<!변경 )0건|없음 —")

# 수집 실패 줄 → 소스 이름 (ops_log warnings cat=collect · notify)
SOURCES = [
    ("CNN 공포탐욕", r"cnn|fear|공포"), ("Yahoo 시세", r"yahoo|yfinance|yf\b"), ("FRED", r"fred"),
    ("SEC EDGAR", r"edgar|sec\b|내부자"), ("Federal Register", r"fedreg|federal register"), ("CNBC", r"cnbc"),
    ("CourtListener", r"court"), ("ARK 매매", r"\bark\b"), ("Google News", r"google news|news\.google"),
    ("Firestore", r"firestore"), ("Polygon", r"polygon"), ("Twelve Data", r"twelve"), ("Alpha Vantage", r"alpha ?vantage"),
    ("한국 시세(KRX · 네이버)", r"krx|pykrx|naver|네이버"), ("FINRA 공매도", r"finra|공매도"), ("일정 · 실적", r"calendar|일정|실적"),
]

# 기록 브랜치 — (이름, 브랜치, 늦음 기준 시간 · 0 = 정기 실행 없음). *-state 7개는 비공개 상태 저장소(alphascope-state, 워크플로가 --state-heads 로),
# 소송 조사 · 그림 브랜치는 공개 저장소(GitHub API /branches 3회)
BRANCHES = [
    ("미국 증시 리포트", "report-state", 30), ("엔비디아 · 종목", "nvda-state", 30), ("한국 종목", "kr-state", 30),
    ("인물 발언", "radar-state", 30), ("방송 기록", "media-state", 30), ("댓글", "comment-state", 30),
    ("트럼프 기록", "trump-state", 0), ("소송 조사", "court-survey", 0), ("한국 그림", "kr-images", 30), ("인물 그림", "radar-images", 30),
    # 비공개 상태 저장소의 기록 브랜치 — 워크플로가 --state-heads 로 넘긴다
    ("한국 기사 사실", "kr-facts", 30), ("Newfact 뉴스 기록", "news-posts", 30), ("뉴스 분류 기록", "news-records", 30),
]


# ---------------------------------------------------------------- 시각
def now_kst():
    return dt.datetime.now(KST)


def parse_time(s):
    """'2026-11-13 01:15:37 UTC' · '2026-11-12T22:03:53Z' · ISO+09:00 → aware datetime."""
    if not s:
        return None
    s = str(s).strip().replace(" UTC", "Z").replace(" ", "T", 1)
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def ago(t, now):
    m = int((now - t).total_seconds() // 60)
    if m < 60:
        return f"{max(m, 0)}분 전"
    if m < 48 * 60:
        return f"{m // 60}시간 전"
    return f"{m // 1440}일 전"


def hm(t):
    return t.astimezone(KST).strftime("%H:%M")


def md(t):
    t = t.astimezone(KST)
    return f"{t.month}.{t.day}"


def biz_hours_since(t, now):
    """주말(KST 토 · 일)을 뺀 지난 시간 — 평일에만 바뀌는 파일을 주말에 늦음으로 보지 않게."""
    h, cur = 0.0, t.astimezone(KST)
    end = now.astimezone(KST)
    while cur < end:
        nxt = min(end, (cur + dt.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0))
        if cur.weekday() < 5:
            h += (nxt - cur).total_seconds() / 3600
        cur = nxt
    return h


def last_kr_day(now):
    """오늘 16:40 이 지났으면 오늘, 아니면 그 전 평일 (공휴일은 모른다)."""
    d = now.astimezone(KST)
    if d.weekday() < 5 and (d.hour, d.minute) >= (16, 40):
        return d.date()
    d -= dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d.date()


# ---------------------------------------------------------------- 자료 읽기 (실패해도 계속 — 칸에 `읽지 못함`)
def gh(path, params=None):
    h = dict(UA, Accept="application/vnd.github+json")
    if os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    r = requests.get(f"https://api.github.com/repos/{REPO}{path}", params=params, headers=h, timeout=30)
    r.raise_for_status()
    return r.json()


def raw(path):
    r = requests.get(RAW + path, headers=UA, timeout=30)
    r.raise_for_status()
    return r.json()


def kv_conf():
    c = [os.environ.get(k, "").strip() for k in ("OPS_CF_ACCOUNT_ID", "OPS_CF_KV_NAMESPACE_ID", "OPS_CF_API_TOKEN")]
    return c if all(c) else None


def kv_url(c, tail):
    return f"https://api.cloudflare.com/client/v4/accounts/{c[0]}/storage/kv/namespaces/{c[1]}/{tail}"


def kv_records(days):
    """운영 기록 — days(KST 날짜 문자열) 의 ops:{날짜}:… 전부."""
    c = kv_conf()
    if not c:
        return None
    h = {"Authorization": f"Bearer {c[2]}"}
    out = []
    for d in days:
        cursor = ""
        while True:
            q = {"prefix": f"ops:{d}:", "limit": 1000}
            if cursor:
                q["cursor"] = cursor
            j = requests.get(kv_url(c, "keys"), params=q, headers=h, timeout=30).json()
            for k in j.get("result") or []:
                r = requests.get(kv_url(c, f"values/{k['name']}"), headers=h, timeout=30)
                if r.status_code == 200:
                    try:
                        out.append(r.json())
                    except ValueError:
                        pass
            cursor = (j.get("result_info") or {}).get("cursor") or ""
            if not cursor:
                break
    return out


# 주기 자료 — 기록이 아직 없어도 줄은 보인다
FEEDS = ["국민연금 대량보유 내역", "국민연금 국내주식 투자 현황", "한국 ETF 구성 · 보수 (운용사)", "미국 ETF 구성 · 보수 (야후)", "증권사 목표가 (텔레그램)", "집 IP 받기 (VPN)", "업종 · 세부 업종 ETF 순자산 (야후)"]


def kv_feeds():
    """feed:* 전부 → {이름: 기록}. KV 설정이 없으면 FEED_LOCAL 파일(로컬 확인용), 그것도 없으면 None."""
    c = kv_conf()
    if not c:
        p = os.environ.get("FEED_LOCAL", "").strip()
        if p and os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
        return None
    h = {"Authorization": f"Bearer {c[2]}"}
    j = requests.get(kv_url(c, "keys"), params={"prefix": "feed:", "limit": 1000}, headers=h, timeout=30).json()
    out = {}
    for k in j.get("result") or []:
        r = requests.get(kv_url(c, f"values/{requests.utils.quote(k['name'], safe='')}"), headers=h, timeout=30)
        if r.status_code == 200:
            try:
                v = r.json()
                out[v.get("name") or k["name"][5:]] = v
            except ValueError:
                pass
    return out


def kv_put(key, text):
    c = kv_conf()
    r = requests.put(kv_url(c, f"values/{key}"), data=text.encode("utf-8"),
                     headers={"Authorization": f"Bearer {c[2]}", "Content-Type": "text/plain; charset=utf-8"}, timeout=60)
    r.raise_for_status()


def kv_get_json(key):
    c = kv_conf()
    if not c:
        return None
    r = requests.get(kv_url(c, f"values/{key}"), headers={"Authorization": f"Bearer {c[2]}"}, timeout=30)
    return r.json() if r.status_code == 200 else None


def load_runs(now):
    """오늘(KST) 정기 실행 · 댓글 실행 목록 — 워크플로마다 1번(댓글은 5분마다라 3쪽까지)."""
    day = now.date()
    rng = f"{(day - dt.timedelta(days=1)).isoformat()}T15:00:00Z..{day.isoformat()}T14:59:59Z"
    runs = {}
    for _, f, _, _ in WORKFLOWS + [("", COMMENT_WF, "", ())]:
        got = []
        for page in range(1, 4 if f == COMMENT_WF else 2):
            j = gh(f"/actions/workflows/{f}/runs", {"created": rng, "per_page": 100, "page": page})
            got += j.get("workflow_runs") or []
            if len(j.get("workflow_runs") or []) < 100:
                break
        runs[f] = got
    return runs


def blog_posts(now, days=14):
    """Blogger 공개 피드 — 최근 days 일 새 글 수 (KST 날짜별)."""
    start = (now - dt.timedelta(days=days)).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    c, idx = Counter(), 1
    for _ in range(30):   # 블로그 피드가 한 번에 5개 남짓만 준다 — start-index 로 넘긴다
        r = requests.get(f"{BLOG}/feeds/posts/summary", params={"alt": "json", "max-results": 150, "published-min": start, "start-index": idx},
                         headers=UA, timeout=30)
        r.raise_for_status()
        feed = r.json().get("feed") or {}
        es = feed.get("entry") or []
        for e in es:
            t = parse_time(e["published"]["$t"])
            if t:
                c[t.astimezone(KST).date()] += 1
        idx += len(es)
        if not es or idx > int((feed.get("openSearch$totalResults") or {}).get("$t") or 0):
            break
    return c


def gh_pages_size():
    sha = gh("/branches/gh-pages")["commit"]["commit"]["tree"]["sha"]
    t = gh(f"/git/trees/{sha}", {"recursive": "1"})
    return sum(x.get("size", 0) for x in t.get("tree") or [] if x.get("type") == "blob") / 1048576, bool(t.get("truncated"))


def safe(fn, *a):
    try:
        return fn(*a), ""
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {str(e)[:120]}"


# ---------------------------------------------------------------- 판정 → 칸
class Issues:
    """손이 필요한 일(요약 탭 `내가 할 일`) · 영역별 상태."""

    def __init__(self):
        self.todo = []          # (이름, 값HTML, 보조)
        self.area = {}          # 영역 → (값HTML, 보조)
        self.need = 0
        self.watch = 0
        self.limits = []        # 리스크 탭 `한도 여유` — (이름, 쓴 비율, 값 문구, 보조)

    def add(self, name, value_html, sub, need=True):
        self.todo.append((name, value_html, sub))
        if need:
            self.need += 1
        else:
            self.watch += 1


def screen_tab(now, I):
    rows, late = [], []
    for name, path, rule in SCREEN_FILES:
        j, err = safe(raw, path)
        if j is None:
            rows.append(("row", name, warn("읽지 못함"), err[:60]))
            late.append(name)
            continue
        t = parse_time(j.get("updated_at") or j.get("generated"))
        if path in ("kr.json", "cards/kr-report.json"):
            day = str(j.get("day") or j.get("date") or "").replace(".", "-")
            want = last_kr_day(now)
            stale = bool(day) and day < want.isoformat()
            val = (over(f"{day[5:].replace('-', '.').lstrip('0')} 값") if stale else (ago(t, now) if t else day))
        elif t is None:
            rows.append(("row", name, warn("시각 없음"), rule))
            continue
        else:
            limit = STALE_HOURS.get(path)
            stale = ((now - t).total_seconds() / 3600 > limit) if limit else (biz_hours_since(t, now) > 30 if path in ("data.json", "cards/report.json") else (now - t).total_seconds() / 3600 > 30)
            val = over(ago(t, now)) if stale else ago(t, now)
        if stale:
            late.append(name)
        rows.append(("row", name, val, f"기준 : {rule}"))
    if late:
        lead = f"{', '.join(late)}이 기준보다 늦습니다. 그 파일을 만드는 실행이 돌았는지 발행 탭에서 확인하세요."
        I.add("독자 화면 늦음", warn(f"{len(late)}곳"), " · ".join(late))
        I.area["화면"] = (warn(), f"{len(late)}곳 늦음 · " + late[0])
    else:
        lead = "독자가 보는 홈 시세 · 뉴스 · 카드 재료가 모두 기준 시간 안에 바뀌었습니다."
        I.area["화면"] = (ok(), f"{len(rows)}곳 모두 기준 안")
    fresh = QC.question_card("독자 화면은 최신인가?", f"{len(late)}곳 늦음" if late else "모두 최신", "neutral", "#111",
                             [(lead, "plain")] + rows, opened=True)

    pages = []
    for m, label in (("us", "미국"), ("kr", "한국")):
        j, err = safe(raw, f"search/{m}.json")
        if j is None:
            pages.append((f"{label} 종목 색인", warn("읽지 못함"), err[:60]))
            continue
        for key, kind in (("stocks", "종목"), ("etfs", "ETF")):
            items = [x for x in j.get(key) or [] if x.get("u")]
            if not items:
                continue
            days = Counter((x.get("p") or {}).get("d") for x in items)
            newest = max(d for d in days if d) if any(days) else ""
            fresh_n = days.get(newest, 0)
            if m == "kr" and newest and newest < last_kr_day(now).isoformat():
                fresh_n = 0   # 한국은 마지막 거래일 값이어야 최신 (공휴일은 모른다)
            val = f'{V(f"{len(items)}개")} 중 ' + (V(f"{fresh_n}개") if fresh_n == len(items) else over(f"{fresh_n}개"))
            pages.append((f"{label} {kind} 페이지", val, f"최근 값 {newest[5:].replace('-', '.')} 기준 · 색인 {key}" if newest else "가격 날짜 없음"))
            if fresh_n < len(items):
                I.add(f"{label} {kind} 페이지 지난 값", over(f"{len(items) - fresh_n}개"), f"{len(items)}개 중 최근 값 {fresh_n}개", need=False)
    return (dk.h2("화면", tab="화면") + fresh
            + dk.sub_label("고정 페이지 최근 값", "종목 검색 색인(search/us.json · kr.json)의 가격 날짜로 셉니다. 정식 페이지가 있는 종목 · ETF 만.")
            + white_card(pages))


def run_rows(runs, recs_by_run, now, I):
    rows, bad, done, expected = [], [], 0, 0
    for name, f, at, days in WORKFLOWS:
        rs = sorted(runs.get(f) or [], key=lambda r: r["created_at"])
        # 분으로 비교 — 예정 + 90분이 자정을 넘기면 오늘은 판정하지 않음
        due = bool(now.weekday() in days and at and now.hour * 60 + now.minute >= int(at[:2]) * 60 + int(at[3:]) + 90)
        if now.weekday() in days and at:
            expected += 1
        if not rs:
            if due:
                rows.append((0, name, warn("실행 없음"), f"{f.replace('.yml', '')} · 예정 {at} · 예약이 오지 않음"))
                bad.append(name)
            elif at and now.weekday() in days:
                rows.append((3, name, idle("실행 전"), f"예정 {at}"))
            else:
                rows.append((4, name, idle("오늘 없음"), "정기 실행 없음" if not at else "오늘은 쉬는 요일"))
            continue
        # 보여 줄 실행 = 글 · 페이지를 낸 마지막 실행, 없으면 마지막 실행 (예비 GitHub 예약이 1분 만에 `이미 있음` 으로 끝나는 경우)
        last = next((r for r in reversed(rs) if any(x.get("publish") for x in recs_by_run.get(str(r["id"]), []))), rs[-1])
        fails = [r for r in rs if r.get("conclusion") == "failure"]
        t0 = parse_time(last["created_at"])
        t1 = parse_time(last.get("updated_at"))
        mins = f"{max(1, round((t1 - t0).total_seconds() / 60))}분" if t0 and t1 and last.get("status") == "completed" else ""
        recs = [x for r in rs for x in recs_by_run.get(str(r["id"]), [])]
        pubs = [p for x in recs for p in x.get("publish") or []]
        posts = len({p.get("url") for p in pubs if p.get("status") == "published"})
        upd = len({p.get("url") for p in pubs if p.get("status") == "updated"})
        exc = next((x["exit"]["exception"] for x in recs if (x.get("exit") or {}).get("exception")), "")
        how = "GitHub 예약" if last.get("event") == "schedule" else "Worker · 수동"
        bits = [f.replace(".yml", ""), f"{how} {hm(t0)}"] + ([mins] if mins else []) + ([f"{len(rs)}번"] if len(rs) > 1 else [])
        bits += ([f"글 {posts}편"] if posts else []) + ([f"페이지 갱신 {upd}개"] if upd else [])
        if last.get("status") != "completed":
            rows.append((2, name, idle("진행 중"), " · ".join(bits)))
        elif last.get("conclusion") == "failure" or exc:
            rows.append((0, name, warn("실패"), " · ".join(bits + [exc[:80] if exc else "실행 기록에서 실패 단계를 보세요"])))
            bad.append(name)
        else:
            done += 1
            rows.append((1 if fails else 2, name, ok("성공"), " · ".join(bits + ([f"앞선 실패 {len(fails)}번"] if fails else []))))
    rows.sort(key=lambda r: r[0])
    cm = runs.get(COMMENT_WF) or []
    cm_fail = sum(r.get("conclusion") == "failure" for r in cm)
    rows.append(("댓글 답글", warn(f"실패 {cm_fail}") if cm_fail else ok("성공"), f"5분마다 · 오늘 {len(cm)}번"))
    for b in bad:
        I.add(f"{b} 실행", warn("확인필요"), "발행 탭에서 실행 기록 확인")
    I.area["발행"] = (warn() if bad else ok(), f"오늘 예정 {expected}개 중 {done}개 성공" + (f" · 문제 {len(bad)}개" if bad else ""))
    return [r[1:] if len(r) == 4 else r for r in rows]


def publish_tab(now, runs, recs, I):
    by_run = defaultdict(list)
    for x in recs or []:
        by_run[str(x.get("run_id"))].append(x)
    if runs is None:
        runs_html = white_card([("실행 목록", warn("읽지 못함"), "GitHub API")])
        I.area["발행"] = (warn("읽지 못함"), "GitHub 실행 목록")
    else:
        runs_html = white_card(run_rows(runs, by_run, now, I), fold_at=3, noun="실행")
    posts, err = safe(blog_posts, now)
    if posts is None:
        count = white_card([("최근 14일 새 글", warn("읽지 못함"), err[:60])])
    else:
        days = [(now - dt.timedelta(days=i)).date() for i in range(13, -1, -1)]
        today_n = posts.get(now.date(), 0)
        count = QC.question_card(
            "오늘 새 글은 몇 편?", f"{today_n}편", "neutral", "#111", [
                (f"오늘 {today_n}편, 최근 14일 {sum(posts.get(d, 0) for d in days)}편이 올라갔습니다. 고정 페이지 갱신은 세지 않습니다.", "plain"),
                (QC.chart_card("최근 14일 새 글 (편)", [(str(d.day), [posts.get(d, 0)]) for d in days],
                               [QC.amber], [lambda v: "#111"], [], fmt=lambda v: f"{v:.0f}"), "html"),
            ], opened=True)
    return (dk.h2("발행", tab="발행")
            + dk.sub_label("오늘 자동 실행", "GitHub Actions 실행 목록 + 운영 기록(글 · 페이지 수). 예정 시각 90분 뒤에도 실행이 없으면 `실행 없음`.")
            + runs_html + count)


def feeds_card(now, feeds, I):
    """`주기 자료는 제때 받았나?` — 분기 · 연 · 주마다 받는 자료의 마지막 확인 · 가진 자료 · 다음 기한. 판정 = feed_log.status."""
    import feed_log
    rows, bad, late = [], [], []
    for name in FEEDS + sorted(set(feeds or {}) - set(FEEDS)):
        rec = (feeds or {}).get(name)
        if feeds is None:
            rows.append((name, warn("읽지 못함"), "운영 기록(KV)"))
            continue
        if not rec:
            rows.append((name, idle("기록 없음"), "아직 한 번도 확인하지 않음 — 첫 정기 실행 뒤 생긴다"))
            continue
        st, why = feed_log.status(rec, now)
        t = parse_time(rec.get("checked"))
        bits = [rec.get("label") or "자료 없음", f"확인 {ago(t, now)}" if t else ""]
        if rec.get("expect_new") and st == "정상":
            bits.append(f"다음 기한 {rec['expect_new'][2:].replace('-', '.')}")
        sub = " · ".join(b for b in bits if b) + (f" — {why}" if why else "")
        if st == "실패":
            rows.append((name, warn("실패"), sub))
            bad.append(name)
        elif st == "늦음":
            rows.append((name, warn("늦음"), sub))
            late.append(name)
        else:
            rows.append((name, ok(), sub))
    rows.sort(key=lambda r: 0 if ("실패" in r[1] or "늦음" in r[1]) else 1)
    if bad or late:
        I.add("주기 자료", warn(f"{len(bad) + len(late)}곳"), " · ".join(bad + late), need=bool(bad))
    state = f"{len(bad)}곳 실패" if bad else f"{len(late)}곳 늦음" if late else "제때" if feeds is not None else "읽지 못함"
    head = QC.question_card("주기 자료는 제때 받았나?", state, "neutral", "#111",
                            [("분기 · 연 · 주마다 받는 자료입니다. 받기 · 읽기가 실패하면 실패, 확인이 주기의 2배 넘게 없거나 새 자료 기한이 지나면 늦음.", "plain")]
                            + [("row", n, v, s) for n, v, s in rows[:3]], opened=True)
    return head + (dk.sub_label("주기 자료") + white_card(rows, fold_at=4, noun="자료") if len(rows) > 3 else "")


def collect_tab(recs, I, feeds=None, now=None):
    lines = []
    for x in recs or []:
        lines += [w["text"] for w in x.get("warnings") or [] if w.get("cat") == "collect" and WARN_NOW.search(w["text"])]   # 이미 쌓인 기록도 지금 규칙으로 다시 거른다(40건 · 신규 0건 오탐, 2026-11-21)
        lines += [k for k in (x.get("notify") or {})]
    by = defaultdict(list)
    for ln in dict.fromkeys(lines):
        src = next((n for n, pat in SOURCES if re.search(pat, ln, re.I)), "그 밖")
        by[src].append(ln)
    srcs = sorted(by.items(), key=lambda kv: (kv[0] == "그 밖", -len(kv[1])))
    if recs is None:
        head_line, state = "운영 기록(KV)을 읽지 못했습니다. 워크플로 설정의 OPS_CF 값을 확인하세요.", "읽지 못함"
        I.area["수집"] = (warn("읽지 못함"), "운영 기록")
    elif not srcs:
        head_line, state = "오늘 운영 기록에 수집 실패 줄이 없습니다.", "없음"
        I.area["수집"] = (ok(), "오늘 수집 실패 줄 없음")
    else:
        names = [n for n, _ in srcs if n != "그 밖"]
        head_line = (f"오늘 {', '.join(names[:3])}{' 등' if len(names) > 3 else ''}에서 실패 줄이 나왔습니다. 예비가 받았는지는 줄 내용을 보세요."
                     if names else "소스를 가리지 못한 실패 줄이 있습니다.")
        state = f"{len(srcs)}곳"
        I.area["수집"] = (warn(), f"{len(srcs)}곳 실패 줄 · {srcs[0][0]}")
        I.add("수집 실패 줄", warn(f"{len(srcs)}곳"), " · ".join(n for n, _ in srcs[:3]), need=False)
    rows = [("row", n, over(f"{len(ls)}줄"), ls[0][:70]) for n, ls in srcs[:4]]
    head = QC.question_card("막힌 수집 소스가 있나?", state, "neutral", "#111", [(head_line, "plain")] + rows, opened=True)
    every = [(n, f"{len(ls)}줄", ls[0][:90]) for n, ls in srcs]
    return (dk.h2("수집", tab="수집") + feeds_card(now or now_kst(), feeds, I) + head
            + (dk.sub_label("소스별 실패 줄", "운영 기록의 수집 경고(cat=collect)와 운영 알림(notify)을 소스 이름으로 묶었습니다. 오늘(KST) 실행만.")
               + white_card(every, fold_at=3, noun="소스") if every else ""))


def ai_tab(now, recs2, I):
    """recs2 = 어제 · 오늘 운영 기록 (Gemini 창은 태평양 자정부터, Groq · NVIDIA 는 최근 24시간)."""
    if recs2 is None:
        I.area["AI 한도"] = (warn("읽지 못함"), "운영 기록")
        return dk.h2("AI", tab="AI") + white_card([("운영 기록", warn("읽지 못함"), "OPS_CF 설정 확인")])
    pt_now = now.astimezone(dt.timezone(dt.timedelta(hours=PT_OFFSET)))
    pt_start = pt_now.replace(hour=0, minute=0, second=0, microsecond=0)
    win = {"pt": pt_start, "24h": now - dt.timedelta(hours=24)}
    used = defaultdict(lambda: {"req": 0, "tok": 0, "old": 0})
    hours = Counter()
    events = Counter()
    for x in recs2:
        t = parse_time(x.get("started"))
        if not t:
            continue
        for step, u in ((x.get("llm") or {}).get("usage") or {}).items():
            for w, start in win.items():
                if t >= start:
                    k = (step, w)
                    used[k]["req"] += u.get("req", u.get("ok", 0) + u.get("fail", 0))
                    used[k]["tok"] += u.get("tok", 0)
                    used[k]["old"] += "tok" not in u
            if t.astimezone(KST).date() == now.date():
                hours[t.astimezone(KST).hour] += u.get("tok", 0)
        if t.astimezone(KST).date() == now.date():
            for k, n in ((x.get("llm") or {}).get("events") or {}).items():
                kind = (re.match(r"(검사 탈락|전부 실패|Gemini 실패|예비|대체|한도)", k) or [None, "그 밖"])[1]
                events[kind] += n
    rows, heads, hot = [], [], []
    known = {m[1] for m in MODELS}
    extra = sorted({step for step, _ in used if step not in known})   # 운영 기록엔 있는데 MODELS 에 없는 단계 — 버리지 않고 한도 없이 보여 준다
    models = MODELS + [(step, step, "req", 0, "24h") for step in extra]
    names = [m[0] for m in models]
    vals = []
    for name, step, kind, limit, w in models:
        u = used[(step, w)]
        n = u[kind]
        if kind == "tok":
            v = f"{n / 10000:.1f}만 / {limit // 10000}만" if limit else f"{n / 10000:.1f}만"
            sub = f"전체 {limit // 10000}만 토큰 · 쓴 {n / 10000:.1f}만 · 여유 {max(limit - n, 0) / 10000:.1f}만 · 최근 24시간"
        else:
            v = f"{n:,} / {limit:,}회" if limit else f"{n:,}회"
            sub = (f"전체 {limit:,}회 · 쓴 {n:,}회 · 여유 {max(limit - n, 0):,}회 · 태평양 자정부터" if limit
                   else "한도 표 없음 · build_ops MODELS 에 추가 필요 · 최근 24시간" if step in extra
                   else "하루 한도 표시 없음 · 예비 자리 · 최근 24시간")
        if u["old"] and kind == "tok":
            sub += " · 토큰 기록 전 실행 있음"
        frac = n / limit if limit else 0
        vals.append(v)
        rows.append((name, frac, v, sub))
        if limit:
            I.limits.append((f"AI · {name}", frac, v, sub))
        if limit and frac >= 0.8:
            hot.append(name)
            heads.append(("row", name, over(v), sub))
    mw = dk.bar_widths(names, vals)
    mrows = [dk.bar_row(esc(n), min(f, 1), dk.CHART_MAIN, over(v) if f >= 0.8 else v, mw, sub=s, first=(i == 0)) for i, (n, f, v, s) in enumerate(rows)]
    if hot:
        lead = f"{', '.join(hot)}이 하루 한도의 80%를 넘었습니다. 넘치면 사슬의 다음 모델로 내려갑니다(llm_chain)."
        I.area["AI 한도"] = (over(f"{len(hot)}개 80%"), " · ".join(hot))
        I.add("AI 한도 80% 넘음", over(f"{len(hot)}개"), " · ".join(hot), need=False)
    else:
        lead = "모든 모델이 하루 한도의 80% 아래입니다."
        I.area["AI 한도"] = (ok(), "모두 80% 아래")
    head = QC.question_card("AI 한도는 넉넉한가?", f"{len(hot)}개 80% 넘음" if hot else "넉넉함", "neutral", "#111",
                            [(lead, "plain")] + (heads or [("row", r[0], r[2], r[3]) for r in rows[:2]]), opened=True)
    hrs = [(str(h), [round(hours[h] / 10000, 1)]) for h in sorted(hours) if hours[h]]
    hour_chart = chart_top(QC.chart_card("시간대별 AI 사용 (만 토큰, 한국 시간)", hrs, [QC.amber], [lambda v: "#111"], [], fmt=lambda v: f"{v:.1f}")) if hrs else ""
    ev = [("예비 모델로 넘어감", V(f"{events['예비']}번"), "Groq · NVIDIA 등 다른 공급자로"),
          ("Gemini 안에서 바꿈", V(f"{events['대체']}번"), "flash ↔ lite"),
          ("한도에 걸림", V(f"{events['한도']}번"), "429 · 하루 · 분당"),
          ("검사 탈락", V(f"{events['검사 탈락']}번"), "답 검사에서 떨어져 다음 모델로"),
          ("사슬 전체 실패", over(f"{events['전부 실패']}번") if events["전부 실패"] else V("0번"), "모든 모델이 답하지 못함")]
    if events["전부 실패"]:
        I.add("AI 사슬 전체 실패", over(f"{events['전부 실패']}번"), "AI 탭 → 예비전환")
    return (dk.h2("AI", tab="AI") + head
            + dk.sub_label("모델별") + dk.card_of(mrows, fold_at=2, noun="모델") + hour_chart
            + dk.sub_label("예비전환") + white_card(ev, fold_at=3, noun="항목"))


def record_tab(now, heads, I):
    rows, late = [], []
    heads = dict(heads or {}) if heads is not None else None
    for br in ("court-survey", "kr-images", "radar-images"):
        d, _ = safe(lambda b: gh(f"/branches/{b}")["commit"]["commit"]["committer"]["date"], br)
        if d and heads is not None:
            heads[br] = d
    if heads is None:
        rows.append(("상태 저장소", warn("읽지 못함"), "워크플로가 브랜치 시각을 넘기지 않음"))
    else:
        for name, br, hrs in BRANCHES:
            t = parse_time(heads.get(br))
            if not t:
                rows.append((name, warn("없음"), br))
                continue
            age = (now - t).total_seconds() / 3600
            if hrs and age > hrs + (48 if now.weekday() in (5, 6, 0) else 0):
                rows.append((name, warn("늦음"), f"{br} · {md(t)} {hm(t)}"))
                late.append(name)
            else:
                rows.append((name, ok() if hrs else idle("정기 없음"), f"{br} · {ago(t, now)}"))
        rows.sort(key=lambda r: 0 if "늦음" in r[1] or "없음" in r[1] and "정기" not in r[1] else 1)
    if late:
        I.add("기록 브랜치 늦음", warn(f"{len(late)}곳"), " · ".join(late))
    I.area["기록"] = ((warn(), f"{len(late)}곳 늦음") if late else (ok(), f"상태 브랜치 {len(rows)}개 기준 안")) if heads is not None else (warn("읽지 못함"), "상태 저장소")
    size, err = safe(gh_pages_size)
    if size:
        I.limits.append(("gh-pages 크기", size[0] / 50, f"{size[0]:.1f} / 50MB", "jsDelivr 가 읽는 상자 약 50MB"))
    hist = kv_get_json("dash:hist") or {}
    if size:
        hist[now.date().isoformat()] = round(size[0], 2)
        hist = dict(sorted(hist.items())[-60:])
    pts = sorted(hist.items())[-30:]
    size_html = ""
    if len(pts) >= 2:
        size_html = chart_top(dk.trend_card("gh-pages 크기 (MB)", [d[5:].replace("-", ".").lstrip("0") for d, _ in pts],
                                            [("gh-pages", [v for _, v in pts], dk.CHART_MAIN, "solid"),
                                             ("jsDelivr 제한", [50] * len(pts), dk.CHART_CMP, "dash")], lambda v: f"{v:.0f}"))
    size_row = [("gh-pages 크기", V(f"{size[0]:.1f}MB") if size else warn("읽지 못함"),
                 "jsDelivr 제한 약 50MB · 공식 문서로 다시 확인할 값" if size else err[:60])]
    head = QC.question_card("기록이 제때 쌓이나?", f"{len(late)}곳 늦음" if late else "제때", "neutral", "#111",
                            [("상태 저장소(비공개) 브랜치의 마지막 저장 시각입니다. 정기 실행이 있는 브랜치는 30시간(주말 +48) 넘게 그대로면 늦음.", "plain")]
                            + [("row", n, v, s) for n, v, s in rows[:3]], opened=True)
    return (dk.h2("기록", tab="기록") + head
            + records_status_card(now)
            + dk.sub_label("상태 브랜치") + white_card(rows, fold_at=3, noun="브랜치")
            + dk.sub_label("gh-pages") + white_card(size_row) + size_html), hist


def records_status_card(now, st=None):
    """기록 현황 — 기록 대장 줄마다 처음 · 마지막 날짜 · 쌓인 양.
    재료 = KV dash:records(밤 기록 사본 실행이 experiments/record_status.py 로 센 것). 알림 · `지금 문제` 줄은 넣지 않는다."""
    if st is None:
        st = kv_get_json("dash:records")
        p = os.environ.get("RECORDS_LOCAL", "").strip()   # 로컬 목업 확인용 — record_status.py --out 파일 (FEED_LOCAL 과 같은 방식)
        if st is None and p and os.path.exists(p):
            st = json.load(open(p, encoding="utf-8"))
    if not st:
        return dk.sub_label("기록 현황") + white_card([("기록 현황", warn("읽지 못함"), "밤 기록 사본 실행(state-backup.yml)이 dash:records 를 아직 안 올림")])
    def _d(s):
        return f"{int(s[5:7])}.{s[8:10]}" if s else ""
    rows = []
    for it in st.get("items") or []:
        if it.get("missing"):
            rows.append((it["name"], idle("브랜치 없음"), it.get("where") or ""))
            continue
        if not it.get("files"):
            rows.append((it["name"], idle("아직 없음"), f"{it.get('asset')} · {it.get('where')}"))
            continue
        span = f"{_d(it.get('first'))} ~ {_d(it.get('last'))} · " if it.get("first") else ""
        rows.append((it["name"], V(_d(it.get("last")) or f"{it['files']}개"),
                     f"{span}{it['n']:,}줄 · {it['bytes'] / 1e6:.1f}MB · {it.get('asset')} · {it.get('where')}"))
    made = parse_time(st.get("made"))
    note = f"기준 {md(made)} {hm(made)} (밤 기록 사본 실행이 셈)" if made else ""
    bk = st.get("backup") or {}
    bt = parse_time(bk.get("made"))
    back = [("기록 사본", V(f"{(bk.get('gz') or 0) / 1e6:.1f}MB") if bk else warn("읽지 못함"),
             f"{bk.get('where', '')} · {md(bt)} {hm(bt)} · 가장 큰 파일 {((bk.get('biggest') or {}).get('gz') or 0) / 1e6:.1f}MB" if bk and bt else "")]
    return (dk.sub_label("기록 현황") + (f'<p style="margin:0 0 8px;font-size:13px;line-height:19px;color:#6B7280;">{esc(note)} · 값 = 마지막으로 쌓인 날, 아래 줄 = 처음 ~ 마지막 · 쌓인 양 · 자산 · 브랜치</p>' if note else "")
            + white_card(rows, fold_at=5, noun="기록") + white_card(back))


def forecast_tab(now, I):
    j, err = safe(raw, "hypo.json")
    if j is None:
        I.area["증시 전망"] = (warn("읽지 못함"), "hypo.json")
        return dk.h2("전망", tab="전망") + white_card([("전망 목록", warn("읽지 못함"), err[:60])])
    live = j.get("open") or []
    done = j.get("done_count") or {}
    rows = [(x.get("title", ""), "미국" if x.get("market") == "us" else "한국", f"등록 {x.get('posted', '')} · {x.get('event', '')}") for x in live]
    stalled = (j.get("ops") or {}).get("stalled") or []   # 판정이 멈춘 전망 — forecast_daily(event_results.stalled)가 hypo.json ops 에
    I.area["증시 전망"] = ((warn(f"판정 멈춤 {len(stalled)}건"), " · ".join(x.get("title", "") for x in stalled)[:60]) if stalled else
                          (V(f"{len(live)}건"), "진행 중 · 끝난 " + " · ".join(f"{'미국' if k == 'us' else '한국'} {v}" for k, v in done.items())))
    stall_rows = [(x.get("title", ""), warn("판정 멈춤"), x.get("why", "")[:80]) for x in stalled]
    if stalled:   # 요약 탭 `지금 문제` 에도
        I.add("증시 전망 판정 멈춤", warn(f"{len(stalled)}건"), " · ".join(x.get("title", "") for x in stalled)[:80])
    head = QC.question_card("진행 중인 전망은?", f"{len(live)}건", "neutral", "#111",
                            [(f"공개된 전망 {len(live)}건이 진행 중입니다. 판정이 2거래일 넘게 안 쌓이거나 사건 뒤 결과 칸이 비면 아래 `판정 멈춤` 에 올라옵니다.", "plain")]
                            + [("row", mk, f"{n}건", " · ".join(t for t, m, _ in rows if m == mk)[:60])
                               for mk, n in Counter(m for _, m, _ in rows).items()], opened=True)
    return (dk.h2("전망", tab="전망") + head
            + dk.sub_label("판정 멈춤") + white_card(stall_rows or [("멈춘 전망", "없음", "매일 아침 전망 실행이 검사")])
            + dk.sub_label("진행중") + white_card(rows or [("진행 중인 전망", "없음", "")], fold_at=3, noun="전망")
            + dk.sub_label("끝난 전망") + white_card([(f"{'미국' if k == 'us' else '한국'}", V(f"{v}건"), "목록의 끝난 전망") for k, v in done.items()] or [("끝난 전망", "없음", "")]))


# ---------------------------------------------------------------- 리스크 · 메모
# 리스크 = 아직 깨지지 않았지만 곧 문제가 될 곳. 자동 = 한도 여유 · 되풀이 실패, 적어 둔 리스크 = 메모 탭에서 종류 `리스크` 로 쓴 것.
# 메모 = 운영자가 찾은 문제를 적고 Claude 가 점검 · 답을 다는 곳. 저장 = KV memo:all (지우지 않음, 관리자 Worker 만 읽고 씀).
# 메모 목록은 Worker 가 화면을 보낼 때 <!--MEMO_LIST--> · <!--RISK_MEMOS--> · <!--MEMO_OPTIONS--> 자리에 채운다 — 쓰자마자 보이게.
MEMO_KEY = "memo:all"
MEMO_TAB_URL = "/#tab-%EB%A9%94%EB%AA%A8"   # #tab-메모
OPEN_STATES = ("열림", "확인 중", "보류")


def week_fails(now):
    """정기 실행마다 최근 7일 실패 — {파일: [실패 시각 …]}. 워크플로마다 GitHub API 1번."""
    since = (now - dt.timedelta(days=7)).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = {}
    for _, f, _, _ in WORKFLOWS:
        j = gh(f"/actions/workflows/{f}/runs", {"created": f">={since}", "status": "failure", "per_page": 100})
        out[f] = [parse_time(r["created_at"]) for r in j.get("workflow_runs") or []]
    return out


def risk_tab(now, I, fails, kv_writes):
    limits = list(I.limits)
    if kv_writes is not None:
        limits.append(("Cloudflare KV 쓰기 (오늘, 추정)", kv_writes / 1000, f"{kv_writes:,} / 1,000건",
                       "운영 기록 · 대시보드 · 메모 · 주기 자료가 같은 KV 를 씀 · 하루 1,000건 무료"))
    limits.sort(key=lambda r: -r[1])
    hot = [r for r in limits if r[1] >= 0.8]
    lrows = [(n, over(f"{f * 100:.0f}%") if f >= 0.8 else V(f"{f * 100:.0f}%"), f"{v} · {s}") for n, f, v, s in limits]

    rep, frows = [], []
    if fails is None:
        frows = [("최근 7일 실패", warn("읽지 못함"), "GitHub 실행 목록")]
    else:
        for name, f, _, _ in WORKFLOWS:
            ts = sorted(t for t in fails.get(f) or [] if t)
            if len(ts) >= 2:
                rep.append(name)
                frows.append((name, warn(f"{len(ts)}번"), f"{f.replace('.yml', '')} · " + " · ".join(f"{md(t)} {hm(t)}" for t in ts)))
        frows = frows or [("되풀이 실패", ok("없음"), "최근 7일 같은 실행이 2번 넘게 실패한 곳 없음")]
    for n in rep:
        I.add(f"{n} 되풀이 실패", warn("리스크"), "리스크 탭 → 되풀이 실패", need=False)
    bits = ([f"한도 80% 넘음 {len(hot)}곳"] if hot else []) + ([f"되풀이 실패 {len(rep)}곳"] if rep else [])
    I.area["리스크"] = (warn(f"{len(hot) + len(rep)}곳"), " · ".join(bits)) if bits else (ok(), "한도 여유 · 되풀이 실패 없음")
    lead = ("곧 문제가 될 곳입니다. " + " · ".join(bits) + ".") if bits else "한도는 모두 80% 아래이고, 최근 7일 되풀이해 실패한 실행이 없습니다."
    head = QC.question_card("곧 문제가 될 곳은?", " · ".join(bits) if bits else "없음", "neutral", "#111",
                            [(lead, "plain")] + [("row", *r) for r in (lrows[:len(hot)] + frows[:len(rep)])], opened=True)
    return (dk.h2("리스크", tab="리스크") + head
            + dk.sub_label("한도 여유", "하루 한도 · 저장 한도 가운데 이미 쓴 비율. 80% 를 넘으면 주황.")
            + white_card(lrows or [("한도", warn("읽지 못함"), "")], fold_at=5, noun="한도")
            + dk.sub_label("되풀이 실패", "최근 7일 같은 정기 실행이 2번 넘게 실패. 한 번은 우연, 되풀이는 원인이 남아 있다는 뜻.")
            + white_card(frows, fold_at=5, noun="실행")
            + dk.sub_label("적어 둔 리스크", "메모 탭에서 종류를 `리스크` 로 쓴 것 가운데 해결되지 않은 것.")
            + "<!--RISK_MEMOS-->")


FIELD = ("display:block;box-sizing:border-box;width:100%;margin:0 0 8px;padding:12px;border:1px solid #E2E8F0;border-radius:8px;"
         "background:#fff;color:#111;font:inherit;font-size:16px;line-height:24px;")
BUTTON = ("display:inline-block;background:#111;border:1px solid #111;color:#fff;border-radius:8px;font-size:16px;font-weight:700;"
          "line-height:24px;padding:10px 32px;cursor:pointer;")


def memo_tab(memos):
    items = (memos or {}).get("items") or []
    n_open = sum(x.get("status") in OPEN_STATES for x in items)
    lead = ("운영하다 찾은 문제를 적어 두면 Claude 가 점검해 원인 · 고친 것을 그 메모에 답으로 답니다. "
            "메모와 답은 지우지 않고 쌓입니다(관리자만 보는 저장소, 해결한 건은 비공개 문서 저장소에도 한 줄).")
    new_form = (f'<form method="post" action="/memo" style="margin:0 0 8px;">'
                f'<select name="kind" aria-label="종류" style="{FIELD}"><option value="문제">문제 — 지금 안 되는 것</option>'
                f'<option value="리스크">리스크 — 아직 괜찮지만 곧 문제가 될 것</option></select>'
                f'<textarea name="text" rows="4" required maxlength="4000" placeholder="무엇을 봤나요? 어느 화면 · 몇 시 · 무엇이 이상한지" style="{FIELD}"></textarea>'
                f'<button type="submit" style="{BUTTON}">메모 남기기</button></form>')
    note_form = (f'<form method="post" action="/memo/note" style="margin:0 0 8px;">'
                 f'<select name="id" required aria-label="메모" style="{FIELD}"><!--MEMO_OPTIONS--></select>'
                 f'<select name="status" aria-label="상태" style="{FIELD}"><option value="">상태 그대로</option>'
                 + "".join(f'<option value="{s}">{s}</option>' for s in ("열림", "확인 중", "보류", "해결")) +
                 f'</select><textarea name="note" rows="3" maxlength="4000" placeholder="덧붙일 말 (선택)" style="{FIELD}"></textarea>'
                 f'<button type="submit" style="{BUTTON}">덧붙이기</button></form>')
    return (dk.h2("메모", tab="메모")
            + M.p(lead)
            + dk.sub_label("새 메모") + new_form
            + dk.sub_label("메모 목록", "열린 것 먼저. 아래 줄 = 쓴 때 · 종류 · 답과 상태가 바뀐 이력.")
            + "<!--MEMO_LIST-->"
            + dk.sub_label("답 · 상태 바꾸기") + note_form
            + "<!--MEMO_TPL_SLOT-->"), n_open


def memo_templates():
    """Worker 가 메모 줄을 그릴 때 쓰는 카드 조각 — 디자인 규칙의 원본(dk.ccard · 라벨)을 그대로 잘라 넘긴다."""
    html = white_card([("__N__", "__V__", "__S__"), ("__N__", "__V__", "__S__")])
    key = '<span style="display:flex;justify-content:space-between'
    i1 = html.index(key)
    i2 = html.index(key, i1 + 1)
    end = html.rindex("</span></div>")
    t = {"open": html[:i1], "first": html[i1:i2], "next": html[i2:end], "close": html[end:],
         "pill": {"열림": warn("__T__"), "확인 중": idle("__T__"), "보류": idle("__T__"), "해결": ok("__T__")}}
    return "<!--MEMO_TPL " + json.dumps(t, ensure_ascii=False) + " MEMO_TPL-->"


def summary_tab(now, I):
    order = ["발행 시간", "리스크", "화면", "수집", "AI 한도", "발행", "기록", "증시 전망", "메모"]   # 발행 시간 = 독자와의 약속, 맨 위
    lead = (f'<p data-seo-lead="1" style="{dk.SEO_LEAD}">{now.month}월 {now.day}일 {now:%H:%M} 기준으로 손이 필요한 곳 '
            f'{V(f"{I.need}곳")}, 지켜볼 곳 {V(f"{I.watch}곳")}이 있습니다.</p>')
    status = white_card([(a if a != "화면" else "독자 화면", *I.area.get(a, (idle("자료 없음"), ""))) for a in order])
    todo = I.todo or [("할 일", ok("없음"), "모든 칸이 기준 안")]
    return (dk.cards(lead + M.head_row() + status)
            + dk.h2("요약", tab="요약")
            + dk.sub_label("내가 할 일") + white_card(todo, fold_at=3, noun="할 일")
            + dk.guide("자료", "운영 기록(Cloudflare KV) · GitHub 실행 목록 · gh-pages 파일 · Blogger 피드 · 상태 저장소 브랜치. "
                       "한 시간마다 새로 만듭니다. 날짜별 실행 상세는 아래 `날짜별 실행`."))


def shell(body, now, title="운영 현황"):
    """블로그 테마 CSS · JS 로 감싼 한 페이지 (dk.write_mock 과 같은 추출, 목업 표시 · 공유 위젯 없음). title = 운영 현황 · 발행 시간(/ontime)."""
    idx = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    css = re.search(r"<b:skin version='1.0'><!\[CDATA\[(.*?)\]\]></b:skin>", idx, re.S).group(1)
    js = re.search(r"//<!\[CDATA\[(.*?)//\]\]>", idx, re.S).group(1)
    foot = (f'<p style="margin:24px 0 0;font-size:14px;line-height:20px;color:#6B7280;">{now.month}.{now.day} {now:%H:%M} 만듦 · '
            + ('<a href="/">운영 현황</a>' if title != "운영 현황" else '<a href="/ontime">발행 시간</a>')
            + ' · <a href="/runs">날짜별 실행</a> · <a href="/logout">로그아웃</a></p>')
    return ('<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="robots" content="noindex,nofollow"><title>{title}</title><style>{css}</style>'
            '<style>.title-share{display:none!important}</style></head>'   # 공유 버튼 없음 — 관리자 화면은 공유할 곳이 아니다
            '<body class="item-view no-dashboard"><main class="main-content"><div class="post-shell"><article class="post-outer-container"><div class="post">'
            f'<h3 class="post-title">{title}</h3><div class="post-body entry-content">{body}{foot}</div></div></article></div></main>'
            f'<script>{js}</script></body></html>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state-heads", help="상태 저장소 브랜치 → 마지막 커밋 ISO 시각 JSON (워크플로가 만든다)")
    ap.add_argument("--upload", action="store_true", help="KV dash:html · dash:hist · dash:ontime(+ ontime-why) 으로 올린다")
    a = ap.parse_args()
    now = now_kst()
    I = Issues()
    today, yday = now.date().isoformat(), (now.date() - dt.timedelta(days=1)).isoformat()
    recs2, err = safe(kv_records, [yday, today])
    if err:
        print(f"[ops] 운영 기록 읽기 실패 {err}")
    recs_today = None if recs2 is None else [x for x in recs2 if str(x.get("started", ""))[:10] == today]
    runs, err = safe(load_runs, now)
    if err:
        print(f"[ops] 실행 목록 읽기 실패 {err}")
    heads = None
    if a.state_heads and os.path.exists(a.state_heads):
        heads = json.load(open(a.state_heads, encoding="utf-8"))

    # 발행 시간(/ontime) — 약속 시각에 글이 나갔나, 어긴 횟수 누적. 요약 탭 맨 위 칸 · 할 일에도
    ontime_page = None
    why_cache = (safe(kv_get_json, "dash:ontime-why")[0] or {}) if kv_conf() else {}   # 지난 날 늦은 원인 — 바뀌지 않으므로 다시 묻지 않는다 (GitHub API 아낌)
    got, err = safe(ontime.build, now, why_cache, recs2)   # 운영 기록 = 소리 없이 멈춘 스크립트 원인
    if got:
        ontime_body, ontime_tab, (ot_val, ot_sub, ot_today), why_cache = got   # 탭 = 운영 현황 안 `발행 시간`(요약 다음), 단독 페이지 /ontime 도 그대로
        I.area["발행 시간"] = (ot_val, ot_sub + " · `발행 시간` 탭")
        for n, v, _, _ in ot_today:
            I.add(f"{n} 기준 시각", v, "`발행 시간` 탭에서 원인 확인")   # 알림은 보내지 않는다 — 모든 건 페이지에서
        ontime_page = shell(dk.align_titles(dk.WRAP_OPEN + ontime_body + dk.WRAP_CLOSE), now, title="발행 시간")
    else:
        I.area["발행 시간"] = (warn("읽지 못함"), err[:60])
        ontime_tab = dk.h2("발행 시간", tab="발행 시간") + white_card([("발행 시간", warn("읽지 못함"), err[:60])])
        print(f"[ops] 발행 시간 만들기 실패 {err}")
    # 문법 검사(syntax-check.yml) — 마지막 검사가 실패면 할 일에
    sc, _ = safe(lambda: (gh("/actions/workflows/syntax-check.yml/runs", {"per_page": 1}).get("workflow_runs") or [None])[0])
    if sc and sc.get("conclusion") == "failure":
        I.add("파이썬 문법 검사 실패", warn("확인필요"), f"{sc.get('head_sha', '')[:8]} 푸시 · 이대로면 그 파일을 쓰는 실행이 멈춤")
    screen = screen_tab(now, I)
    publish = publish_tab(now, runs, recs_today, I)
    feeds, err = safe(kv_feeds)
    if err:
        print(f"[ops] 주기 자료 기록 읽기 실패 {err}")
    collect = collect_tab(recs_today, I, feeds, now)
    ai = ai_tab(now, recs2, I)
    record, hist = record_tab(now, heads, I)
    forecast = forecast_tab(now, I)
    fails, err = safe(week_fails, now)
    if err:
        print(f"[ops] 최근 7일 실패 읽기 실패 {err}")
    # KV 쓰기 추정 = 오늘 운영 기록 건수 + 대시보드(시간마다 4건) — 주기 자료 · 메모는 드물어 뺌
    kv_writes = None if recs_today is None else len(recs_today) + 4 * (now.hour + 1)
    risk = risk_tab(now, I, fails, kv_writes)
    memos = (safe(kv_get_json, MEMO_KEY)[0] or {}) if kv_conf() else None
    memo, n_open = memo_tab(memos)
    I.area["메모"] = ((warn(f"열림 {n_open}개"), "메모 탭 — Claude 가 점검할 것") if n_open else (ok("없음"), "열린 메모 없음")) if memos is not None \
        else (idle("자료 없음"), "운영 화면(Worker)에서 봄")
    body = summary_tab(now, I) + ontime_tab + risk + screen + publish + collect + ai + record + forecast + memo
    body = dk.align_titles(dk.WRAP_OPEN + body + dk.WRAP_CLOSE)
    html = dk.fix_colons(body) if hasattr(dk, "fix_colons") else body
    page = shell(html, now).replace("<!--MEMO_TPL_SLOT-->", memo_templates())   # 글자 다듬기(fix_colons) 뒤에 — 조각이 바뀌지 않게
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "ops.html"), "w", encoding="utf-8") as f:
        f.write(page)
    if ontime_page:
        with open(os.path.join(OUT, "ontime.html"), "w", encoding="utf-8") as f:
            f.write(ontime_page)
    print(f"[ops] output/ops.html {len(page) // 1024}KB · 손 {I.need} · 지켜볼 {I.watch}")
    if a.upload:
        if not kv_conf():
            sys.exit("[ops] OPS_CF 값이 없어 올리지 못함")
        kv_put("dash:html", page)
        kv_put("dash:hist", json.dumps(hist))
        if ontime_page:
            kv_put("dash:ontime", ontime_page)
            kv_put("dash:ontime-why", json.dumps(why_cache, ensure_ascii=False))
        print("[ops] KV dash:html 올림")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
