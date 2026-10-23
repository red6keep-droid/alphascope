"""운영 기록 — 실행 하나가 무엇을 했는지(게시 · 예비 모델 · 수집 실패 · 중단 이유)를 Cloudflare KV 에 한 건으로 남긴다 (2026-10-23 사용자).

관리자 전용 운영 페이지(infra/ops-console)가 이 기록과 GitHub 실행 목록을 합쳐 "오늘 리포트가 왜 안 나갔나"를 보여 준다.
공개 저장소라 *-state 브랜치 · gh-pages 에는 두지 않는다 — Actions 로그도 공개지만 한곳에 모은 운영 정보까지 공개할 이유는 없다.

파이프라인 코드는 고치지 않는다. import 만 하면:
  - print 출력을 그대로 흘려보내면서 "[게시 완료]" · "이미 게시됨" · "게시하지 않는다" · "실패" · "::warning::" 줄을 골라 담는다
  - llm_chain 의 단계별 성공/시도(USAGE) · 예비 전환 · 검사 탈락 · 한도(EVENTS), notify 의 운영 알림(EVENTS) 을 끝에 읽는다
  - 잡히지 않은 예외(Traceback 마지막 줄)와 종료 코드를 남긴다
notify · llm_chain 이 import 하므로 대부분의 파이프라인은 따로 import 하지 않아도 된다.

OPS_CF_ACCOUNT_ID · OPS_CF_KV_NAMESPACE_ID · OPS_CF_API_TOKEN 이 모두 있을 때만 보낸다(그 외 — 로컬 실행 · 설정 전 — 아무것도 안 한다).
보내기 실패는 print 만 — 운영 기록 때문에 리포트가 죽으면 안 된다.
비밀값: 환경변수 가운데 KEY · TOKEN · SECRET · WEBHOOK 이름의 값과 URL 쿼리의 key= · token= 은 보내기 전에 *** 로 지운다 (키 노출 금지).
"""

import atexit
import datetime
import json
import os
import re
import sys
import time
import traceback

TTL_SECONDS = 180 * 86400        # KV 보관 180일
MAX_LINES = 80                   # 경고 줄 상한 (같은 줄은 한 번)
KST = datetime.timezone(datetime.timedelta(hours=9))

_STARTED = time.time()
_lines = []                      # [(분류, 줄)]
_seen = set()
_publish = []                    # [{"status", "url"?, "reason"?}]
_exit = {"code": 0, "exception": None}
_installed = False

# LLM 사슬이 찍는 줄은 USAGE · EVENTS 로 따로 남기므로 경고에서 뺀다 — "[people-narrate] groq 실패 — …" · "[x] 예비 → …"
_LLM_LINE = re.compile(r"^\[[\w-]+\] (\S+ 실패 — |예비 → |대체 → |사슬 |\S+ 분당 한도 간격|Gemini )")
_WARN = re.compile(r"실패|::warning::|::error::|Forbidden|Traceback|오류|에러|중단|0건|없음 —")
_COLLECT = re.compile(r"collect|수집|feeds|edgar|fedreg|finra|calendar|일정|price_source|FRED|yfinance|ARK|rss|options|estimates|analysts|holdings|court|실적|지수|시계열|Firestore", re.I)
_PUBLISHED = re.compile(r"\[게시 완료\]\s*(\S+)|본문 갱신:\s*(\S+)|\[publish\] 게시:\s*(\S+)")
_ALREADY = re.compile(r"이미 게시됨:\s*(\S+)|같은 제목의 글이 이미 있습니다:\s*(\S+)")
_SKIP = re.compile(r"게시하지 않는다|게시하지 않습니다|게시를 중단|글을 만들지 않는다|게시 dry-run|publish dry-run")


def _secret_values():
    vals = []
    for k, v in os.environ.items():
        if v and len(v) >= 8 and re.search(r"KEY|TOKEN|SECRET|WEBHOOK|PASSWORD|CREDENTIAL", k, re.I):
            vals.append(v)
    return sorted(vals, key=len, reverse=True)


def scrub(text):
    text = str(text)
    for v in _secret_values():
        text = text.replace(v, "***")
    return re.sub(r"(?i)\b((?:api_?)?key|apikey|token|access_token|secret)=([^&\s\"']+)", r"\1=***", text)


def _take(line):
    line = line.strip()
    if not line:
        return
    m = _PUBLISHED.search(line)
    if m:
        url = next(g for g in m.groups() if g)
        if not any(p.get("url") == url for p in _publish):
            _publish.append({"status": "updated" if "갱신" in line else "published", "url": url})
        return
    m = _ALREADY.search(line)
    if m:
        _publish.append({"status": "already", "url": next(g for g in m.groups() if g)})
        return
    if _SKIP.search(line):
        _publish.append({"status": "dry-run" if "dry-run" in line else "skipped", "reason": line[:200]})
        return
    if _LLM_LINE.search(line) or not _WARN.search(line):
        return
    key = line[:160]
    if key in _seen or len(_lines) >= MAX_LINES:
        return
    _seen.add(key)
    _lines.append(("collect" if _COLLECT.search(line) else "other", line[:300]))


class _Tee:
    """print 를 그대로 내보내면서 줄 단위로 _take 에 넘긴다. reconfigure 등 나머지는 원래 스트림으로."""

    def __init__(self, stream):
        self._stream = stream
        self._buf = ""

    def write(self, s):
        try:
            self._buf += s
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                _take(line)
        except Exception:  # noqa: BLE001  — 기록은 절대 출력을 막지 않는다
            self._buf = ""
        return self._stream.write(s)

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _excepthook(etype, value, tb):
    if not issubclass(etype, SystemExit):
        frames = traceback.extract_tb(tb)
        where = f"{os.path.basename(frames[-1].filename)}:{frames[-1].lineno}" if frames else ""
        _exit["exception"] = f"{etype.__name__}: {str(value)[:300]}" + (f" ({where})" if where else "")
        _exit["code"] = 1
    _orig_excepthook(etype, value, tb)


_orig_excepthook = sys.excepthook


def _record():
    llm = sys.modules.get("llm_chain")
    notify = sys.modules.get("notify")
    usage = {k: dict(v) for k, v in getattr(llm, "USAGE", {}).items()} if llm else {}
    llm_events = dict(getattr(llm, "EVENTS", {})) if llm else {}
    notes = dict(getattr(notify, "EVENTS", {})) if notify else {}
    now = time.time()
    return {
        "v": 1,
        "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "event": os.environ.get("GITHUB_EVENT_NAME", ""),
        "script": os.path.relpath(os.path.abspath(sys.argv[0] or "?"), os.environ.get("GITHUB_WORKSPACE", os.getcwd())).replace("\\", "/"),
        "args": " ".join(sys.argv[1:])[:120],
        "started": datetime.datetime.fromtimestamp(_STARTED, KST).isoformat(timespec="seconds"),
        "seconds": round(now - _STARTED),
        "exit": dict(_exit),
        "publish": _publish,
        "llm": {"usage": usage, "events": llm_events},
        "notify": notes,
        "warnings": [{"cat": c, "text": t} for c, t in _lines],
    }


def _interesting(rec):
    return bool(rec["publish"] or rec["llm"]["usage"] or rec["llm"]["events"] or rec["notify"] or rec["warnings"] or rec["exit"]["exception"] or rec["exit"]["code"])


def _send():
    acc, ns, tok = (os.environ.get(k, "").strip() for k in ("OPS_CF_ACCOUNT_ID", "OPS_CF_KV_NAMESPACE_ID", "OPS_CF_API_TOKEN"))
    if not (acc and ns and tok and os.environ.get("GITHUB_RUN_ID")):
        return
    try:
        rec = _record()
        if not _interesting(rec):
            return
        body = scrub(json.dumps(rec, ensure_ascii=False))
        day = datetime.datetime.fromtimestamp(_STARTED, KST).strftime("%Y-%m-%d")
        key = f"ops:{day}:{rec['run_id']}:{int(_STARTED * 1000)}"
        import requests
        r = requests.put(f"https://api.cloudflare.com/client/v4/accounts/{acc}/storage/kv/namespaces/{ns}/values/{key}",
                         params={"expiration_ttl": TTL_SECONDS}, data=body.encode("utf-8"),
                         headers={"Authorization": f"Bearer {tok}", "Content-Type": "text/plain; charset=utf-8"}, timeout=20)
        if r.status_code != 200:
            print(f"[ops_log] 운영 기록 저장 실패 HTTP {r.status_code}", file=sys.__stdout__)
    except Exception as e:  # noqa: BLE001
        print(f"[ops_log] 운영 기록 저장 실패: {type(e).__name__}", file=sys.__stdout__)


def _wrap_exit():
    orig = sys.exit

    def exit_(code=0):
        _exit["code"] = code if isinstance(code, int) else (0 if code is None else 1)
        orig(code)
    sys.exit = exit_


def install():
    global _installed
    if _installed:
        return
    _installed = True
    sys.stdout = _Tee(sys.stdout)
    sys.excepthook = _excepthook
    _wrap_exit()
    atexit.register(_send)


install()
