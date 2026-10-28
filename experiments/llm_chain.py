"""모든 리포트가 같이 쓰는 LLM 호출 + 예비 사슬 (2026-10-14 사용자: "리포트를 더 많이 생산할 거야. 예비키들이 엄청 중요해" → "함께 옮겨").

예전에는 엔비디아 · 트럼프(gemini_client + backup_llm 사본), 댓글 봇, 홈 뉴스 번역, 미국 증시 리포트가 각자 호출 코드를
들고 있었고, 미국 증시 리포트에는 예비가 없었다. 이제 공급자를 더하거나 순서를 바꾸는 곳은 이 파일 하나다.

쓰는 법 (파이프라인 폴더에서 experiments/ 를 sys.path 에 넣고):
    from llm_chain import LLMPool
    pool = LLMPool("json")                       # 사슬 이름은 CHAINS
    value = pool.generate_json(prompt, temperature=0.2, validate=None)
    pool.last_model                              # 답한 모델 (예: "gemini-3.6-flash", "groq:openai/gpt-oss-120b")

사슬은 단계를 차례로 시도한다. 키가 없는 단계는 건너뛰고, 한 단계가 끝까지 실패하면(한도 · 서버 과부하 · 형식 오류 ·
validate 탈락 모두) 다음 단계로. 전부 실패하면 RuntimeError.

Gemini 는 REST 로 부른다 — 홈 뉴스 워크플로에는 google-genai 가 없다. 필요한 패키지는 requests 하나.
Gemini 키는 하나 — 프로젝트 하나 (2026-10-19 사용자: 한 블로그에서 키 · 프로젝트를 여러 개 돌려 한도를 늘리는 건 약관 위반(사용량 제한 우회)).
GEMINI_API_KEY 에 키가 여럿 들어 있어도 첫 키만 쓴다(gemini_keys). 하루 한도는 모든 리포트가 나눠 쓰는 예산 — 새 기능은 Groq · NVIDIA 를 먼저 쓰고 Gemini 는 예비로.
(2026-10-14 ~ 10-18 에는 다른 프로젝트의 키 5개를 돌려 썼다 — 아래 프로젝트별 실측은 그때 기록.)
429 분당 한도를 받으면 KEY_COOLDOWN_SECONDS 한 번 쉬고, 하루 한도(PerDay)면 그 실행 동안 그 모델을 버린다.
503/500 은 키 문제가 아니라 기다렸다 다시 — 단계마다 attempts 횟수만큼(3·6·12·24s…).

Gemini 과부하(503) · 하루 한도 실측 (2026-10-16):
- 503 은 시간대가 아니라 날짜 단위로 오고(나쁜 날은 하루 종일), 같은 순간에도 모델마다 다르다 — 3.5-flash 가 503 일 때 3.5-flash-lite 는 200.
- 하루 한도 이름은 GenerateRequestsPerDayPerProjectPerModel — 프로젝트 × 모델. NVDA · 트럼프 프로젝트는 503 재시도까지 합쳐 20회째에
  걸렸다(503 도 횟수에 드는 것으로 보임). 데일리 프로젝트는 36회에도 안 걸림 — 프로젝트마다 한도가 다르다(AI Studio 할당량 화면에서 확인).
  3.6-flash 는 3.5-flash 가 소진된 키에서 첫 호출부터 PerDay → 3.x flash 끼리 한 버킷으로 보임. flash-lite 는 버킷이 따로(소진된 키로도 200).
- 그래서 3.5-flash 는 503 재시도를 2회로 줄이고(한도를 재시도로 태우지 않게) 바로 gemini-lite(3.5-flash-lite) 로 넘어간다.
  lite 정확도(2026-10-16, 저장된 Gemini 라벨 기준): NVDA 분류 80칸 중 75(3.5-flash 재실행 70 · DeepSeek 58) · 트럼프 120칸 중 85
  (주제 · 방향 26/30, 강도 11/30 — ±1 허용 54/60). 응답 15초 · 9초. lite 의 ai_model("gemini-3.5-flash-lite") 에는 콜론이 없어
  정식 분류로 남는다(재분류 대상 아님). 3.7 · 3.8-flash 는 측정 내내 503, 3.1-flash-lite 도 대부분 503 이라 후보에서 제외.

모델 실측 (2026-10-11, NVDA 실제 분류 프롬프트 6건 · 20건, 서술 프롬프트):
- Groq gpt-oss-120b (사고 low): 분류 20건 6.5초, Gemini 라벨과 24필드 중 18~19 일치, 서술 검증 통과.
  무료 등급 분당 8,000토큰 → 다음 호출까지 60초 간격. 미국 증시 리포트처럼 긴 프롬프트(3만 자 넘음)는 413 으로 바로 다음 단계.
- NVIDIA DeepSeek V4.1 Flash (사고 끔): 18/24, 20건 배치 2분 안팎. 공용 엔드포인트라 지연이 들쭉날쭉(3초↔19분).
- Groq Qwen 3.8 27B (사고 끔, 2026-10-14 추가): 분류 20건 6초, 80칸 중 56 — gpt-oss 와 같은 키, 한도는 모델마다 따로.
- NVIDIA gpt-oss-20b: 번역 5초 — 번역 전용 (분류는 전부 Other · 0 으로 탈락).
떨어진 후보: Llama(2026-10-14 — Groq 에서 내려감, NVIDIA Nemotron 70B · Ultra 253B 는 404), OpenRouter 무료 DeepSeek 없음(유료만), Mistral(Ministral 14B 14/24, Legal→Regulation 오분류, 서술에 없는 내용), Nemotron Super(빈 응답), GLM Flash(무응답), Gemma 4(504).
사고 모드는 켜도 라벨이 안 나아지고(low 18 → medium 19 → high 빈 응답) 서술은 길어져 검증 탈락 → 전부 low/끔.
새 공급자는 실제 프롬프트로 정확도를 비교한 뒤에만 STEPS · CHAINS 에 넣는다.
"""

import json
import os
import atexit
import re
import time
from collections import Counter, defaultdict

import requests

import ops_log  # noqa: F401  — 운영 기록 (experiments/ops_log.py, 2026-10-23): USAGE · EVENTS 를 실행 끝에 KV 로

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.6-flash"   # 10-28: 3.5-flash 이름 호출은 할당량 화면에서 3.6 Flash 로 집계 — 이름이 없어지기 전에 바꿈
GEMINI_LITE_MODEL = os.environ.get("GEMINI_LITE_MODEL", "").strip() or "gemini-3.5-flash-lite"   # 대체 모델 (2026-10-16) — 과부하 · 하루 한도 버킷이 따로
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
KEY_COOLDOWN_SECONDS = 60
GEMINI_ATTEMPTS = 5
RETRY_SLEEP_SECONDS = 3

# 공급자 단계. kind: gemini(REST, 다중 키) · openai(OpenAI 호환 REST)
STEPS = {
    "gemini": {"kind": "gemini", "env": "GEMINI_API_KEY", "model": GEMINI_MODEL, "timeout": 300,
               "attempts": 2},   # 503 재시도 2회만 — 하루 20회 한도를 재시도로 태우지 않게, 바로 gemini-lite 로 (2026-10-16)
    "gemini-lite": {"kind": "gemini", "env": "GEMINI_API_KEY", "model": GEMINI_LITE_MODEL, "timeout": 300,
                    "attempts": 4},   # 같은 키 · 다른 모델 — 3.5-flash 가 503 이거나 하루 한도여도 보통 바로 답한다 (2026-10-16)
    "groq": {"kind": "openai", "env": "GROQ_API_KEY", "url": "https://api.groq.com/openai/v1/chat/completions",
             "model": "openai/gpt-oss-120b", "min_interval": 60, "timeout": 120,
             "params": {"reasoning_effort": "low", "max_completion_tokens": 8000}},   # 분당 8,000토큰 → 호출 간격 60초
    "groq-qwen": {"kind": "openai", "env": "GROQ_API_KEY", "url": "https://api.groq.com/openai/v1/chat/completions",
                  "model": "qwen/qwen3.8-27b", "min_interval": 60, "timeout": 120,
                  # 분당 출력 1,000토큰(OTPM)이 따로 있다 (2026-10-26 실측). Groq 는 요청의 예상 출력(= max_completion_tokens 또는 직전 출력량)이
                  # 1,000을 넘으면 몇 분을 쉬어도 429 로 거절한다 — 출력 상한을 1,000으로 두고 답이 그 안에 들도록 배치를 작게 (뉴스 4건 · 인용 추출 16묶음).
                  # 같은 조건에서 62초 간격 3연속 성공(출력 817 ~ 905). 답이 1,000을 넘으면 잘려 JSON 이 깨지고 다음 단계로 넘어간다
                  "otpm": 1000,
                  "params": {"reasoning_effort": "none", "max_completion_tokens": 1000}},   # gpt-oss 와 한도가 따로 (모델마다 분당 8,000토큰)
    "nvidia-deepseek": {"kind": "openai", "env": "NVIDIA_API_KEY", "url": "https://integrate.api.nvidia.com/v1/chat/completions",
                        "model": "deepseek-ai/deepseek-v4.1-flash", "timeout": 300,
                        "params": {"max_tokens": 8000, "chat_template_kwargs": {"thinking": False}}},   # 사고 끄기 — 켜면 답이 비거나 5분 초과
    "nvidia-gptoss20": {"kind": "openai", "env": "NVIDIA_API_KEY", "url": "https://integrate.api.nvidia.com/v1/chat/completions",
                        "model": "openai/gpt-oss-20b", "timeout": 90,
                        "params": {"reasoning_effort": "low", "max_tokens": 2000}},
}

# 용도별 순서
CHAINS = {
    # 분류 · 서술 · 리포트 · 댓글 답글. DeepSeek 가 2순위 (2026-10-14 비교: 분류 Gemini 라벨과 80칸 중 DeepSeek 58 · Qwen 56 · gpt-oss 51,
    # 서술 세 가지를 모두 통과한 예비는 DeepSeek 뿐 — Groq 둘은 트럼프 서술 · 데일리가 분당 8,000토큰을 넘어 413, gpt-oss 는 NVDA 서술 숫자 방향을 틀림).
    # Groq 둘은 짧은 요청(분류 · 답글)용 3 · 4순위
    # gemini-lite 가 2순위 (2026-10-16): 3.5-flash 과부하 · 하루 한도 때 같은 키의 다른 모델이 먼저 받는다 — 분류 일치율이 DeepSeek 보다 높고 빠르다
    "json": ["gemini", "gemini-lite", "nvidia-deepseek", "groq-qwen", "groq"],
    # 데일리 서술만 DeepSeek 이 lite 보다 앞 (2026-10-16 사용자): 같은 데이터로 비교하니 lite 는 숫자는 맞지만 두루뭉술하고("다양한 업종")
    # 뉘앙스가 어긋남(+0.08% 를 "약보합", 전 지수 상승을 "혼조"). DeepSeek 이 더 구체적 — 단 10-15 에 방향 오류 2건 이력
    "json-daily": ["gemini", "nvidia-deepseek", "gemini-lite", "groq-qwen", "groq"],
    "translate": ["groq", "nvidia-gptoss20", "gemini-lite", "gemini"],          # 홈 뉴스 제목 번역 — 빠른 것부터 (2026-10-11)
    # 댓글 답글 — Gemini 는 맨 뒤 (2026-10-14 사용자: 댓글 한 건에 한도 1회가 나가니 리포트 몫을 남기자). 답글은 짧고 숫자를 쓰지 않아 예비 모델로 충분.
    # Groq 가 첫째, DeepSeek 은 예비 (2026-10-26 사용자: NVIDIA 는 예비 사슬에만 — 비교에서 답글 품질은 DeepSeek 이 가장 좋았다)
    "comment": ["groq", "groq-qwen", "nvidia-deepseek", "gemini-lite", "gemini"],
    # 예비 모델이 임시로 분류한 행을 Gemini 로 다시 분류할 때 (2026-10-15) — 예비로 덮어쓰지 않도록 Gemini 만 (lite 도 Gemini, 정식 분류)
    "json-gemini": ["gemini", "gemini-lite"],
    # 시총 TOP 10 뉴스 분류 — lite 먼저 (doc/기획/종목-레이더-기획.md 10-4: flash 하루 약 20회는 NVDA 리포트 몫으로 남긴다, lite 는 버킷이 따로)
    "json-lite": ["gemini-lite", "nvidia-deepseek", "groq-qwen", "groq"],
    # 새 기능 — 예비 공급자 먼저, Gemini 는 맨 뒤 (2026-10-19, 위 머리말: 키 하나를 모든 리포트가 나눠 쓴다). 인물 발언 레이더 인용 추출
    "json-backup-first": ["groq-qwen", "groq", "nvidia-deepseek", "gemini-lite"],
    # 출력이 긴 일(호출당 출력 1,000토큰 넘게 — 인물 레이더 분류 20건 · 카드 요약 16건)은 gpt-oss 먼저 (2026-10-26).
    # Qwen 은 분당 출력 1,000토큰(OTPM) 한도라 출력 2천 토큰짜리는 몇 분에 한 번만 받힌다 — 10-25 분류에서 Qwen 12번 중 11번 429
    "json-oss-first": ["groq", "groq-qwen", "nvidia-deepseek", "gemini-lite"],
    # 공용 뉴스 처리(news_store: 제목 번역 · 사실 문장 · 요약 · 종목 관련도) — Groq 먼저 (2026-10-25 사용자: "Gemini 는 쓸 곳이 많다, Groq 로 할 수 있는 건 Groq").
    # 두 사슬을 배치마다 번갈아 쓴다 — Groq 는 모델마다 분당 8,000토큰(호출 간격 60초)이라 qwen · gpt-oss 를 엇갈려 기다림을 반으로. Gemini lite 는 맨 뒤 예비
    "news": ["groq-qwen", "groq", "nvidia-deepseek", "gemini-lite"],
    "news-alt": ["groq", "groq-qwen", "nvidia-deepseek", "gemini-lite"],
}

# NVIDIA(build.nvidia.com) 무료 엔드포인트는 공식 FAQ 상 개발 · 테스트 · 연구 · 평가 전용 — "실제 최종 사용자에게 서비스하는 활동" 은
# production 이라 NVIDIA AI Enterprise 라이선스가 필요하다 (doc/운영/블로그-운영-지침.md D3-2). 2026-10-21 운영 사슬에서 뺐다가
# 2026-10-26 사용자 결정으로 예비 자리에만 되살렸다: 블로그가 '테스트 중' 단계이고 NVIDIA 계정은 다른 데 쓰지 않아 막혀도 잃을 것이 없다.
# 1순위로 두지 않는다 — 막히면 다음 단계로 넘어갈 뿐. 끄려면 LLM_ALLOW_NVIDIA=0.
if os.environ.get("LLM_ALLOW_NVIDIA", "").strip() == "0":
    CHAINS = {name: [s for s in steps if not s.startswith("nvidia")] for name, steps in CHAINS.items()}

# 예비 모델이 남긴 ai_model 은 "공급자:모델" (nvidia:… · groq:…). Gemini("gemini-…") · 규칙("rule") 에는 콜론이 없다
PROVISIONAL_SQL = "ai_model LIKE '%:%'"

USAGE = defaultdict(lambda: {"ok": 0, "fail": 0})   # 단계 → 성공 · 실패 수 (이번 실행)
EVENTS = Counter()   # 알릴 일 (이번 실행): "한도 Gemini 키 #1" · "예비 nvda-narrate → nvidia-deepseek" · "전부 실패 …" · "검사 탈락 …"
# Slack 알림 (2026-10-14 사용자: "한도가 걸린 걸 알림으로 보내줘") — 실행이 끝날 때 EVENTS 가 비어 있지 않으면 한 번만, SLACK_WEBHOOK_URL 로.
# 한도(429) · 예비 모델 사용 · 사슬 전부 실패 · 검사 탈락이 대상. 503 재시도는 흔해서 알리지 않는다 (예비로 넘어가면 그때 알린다)


def event(kind, detail):
    EVENTS[f"{kind} {detail}"] += 1


def _notify_summary():
    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not EVENTS or not url:
        return
    run = os.environ.get("GITHUB_WORKFLOW") or "로컬 실행"
    link = ""
    if os.environ.get("GITHUB_RUN_ID"):
        link = f"\n🔗 https://github.com/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    lines = [f"⚠️ AI 호출 알림 — {run}", ""]
    for k, n in EVENTS.most_common():
        lines.append(f"• {k}" + (f" ×{n}" if n > 1 else ""))
    lines += ["", f"단계별 성공/시도: {usage_line()}", link]
    try:
        requests.post(url, json={"text": "\n".join(lines), "unfurl_links": False}, timeout=20)
    except Exception as e:  # noqa: BLE001
        print(f"[llm] Slack 알림 실패: {e}")


atexit.register(_notify_summary)
# 하루 한도(429 PerDay)를 받은 (Gemini 키, 모델) — 태평양 자정까지 다시 오지 않으니 이번 실행(프로세스) 동안 건너뛴다.
# 2026-10-15: 키 1개가 429 를 받고도 60초 휴식 × 5회를 호출마다 반복해 트럼프 1,471초 · NVDA 1,117초가 걸림
# 2026-10-16: 한도 이름이 …PerDayPerProjectPerModel — 모델마다 따로다. 키 단위로 버리면 같은 키의 다른 모델(대체 모델)까지 건너뛴다
_EXHAUSTED_KEYS = set()
_ready_at = {}   # (주소, 모델) → 다음 호출 가능 시각 (분당 토큰 한도 간격용 — Groq 는 모델마다 한도가 따로)
RATE_RETRY_MAX_WAIT = 150   # 분당 한도 429 는 이만큼까지 기다렸다 한 번 더 (그보다 길면 다음 단계로)
_day_out = set()   # 하루 한도(TPD · 하루 요청)를 받은 OpenAI 호환 단계 — 이번 실행 동안 모든 사슬에서 건너뛴다 (Gemini 의 PerDay 와 같은 원칙, 2026-10-26)


def _groq_reason(text):
    """'Request too large … on output tokens per minute (OTPM): Limit 1000, Requested 1089' → 어느 한도인지만.
    앞 160자로 자르면 조직 · 모델 이름에 묻혀 TPM 인지 OTPM 인지 안 보였다 (2026-10-26)."""
    m = re.search(r"\bon ([a-z ]+\([A-Z]+\)[^.]*)", text)
    return m.group(1) if m else re.sub(r"org_[A-Za-z0-9]+", "org", text)[:160]


def _rate_wait(r):
    """분당 한도 429 → 기다릴 초. 하루 한도(TPD · RPD)는 기다려도 소용없으니 긴 값이 나오거나 None."""
    if "per day" in r.text:
        return None
    if r.headers.get("retry-after", "").replace(".", "", 1).isdigit():
        return float(r.headers["retry-after"]) + 1
    m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", r.text)
    if m:
        return int(m.group(1) or 0) * 60 + float(m.group(2)) + 1
    return None   # 출력 한도(OTPM) 429 는 기다려도 잘 안 풀린다 — 10-26 실측: 출력 2천 토큰짜리는 3분 넘게 쉬어도 거절. 바로 다음 단계로


class StepFailed(RuntimeError):
    pass


def parse_json(text):
    """모델 응답에서 첫 JSON 값. ```json 울타리 · 앞뒤 말 · 값 뒤 덧붙인 글("Extra data")을 견딘다."""
    text = (text or "").strip()
    m = re.search(r"[\[{]", text)
    if not m:
        raise ValueError("JSON 시작 문자를 찾지 못했습니다.")
    text = text[m.start():]
    try:
        value, _ = json.JSONDecoder().raw_decode(text)
    except ValueError:
        # 닫는 괄호 앞 쉼표(`,}` · `,]`) — 2026-10-16 flash-lite 분류 4배치 중 1배치가 문법 오류로 떨어짐. 내용 검증은 호출자의 validate 가 한다
        value, _ = json.JSONDecoder().raw_decode(re.sub(r",\s*([}\]])", r"\1", text))
    return value


_WARNED_KEYS = False


def gemini_keys():
    """Gemini 키는 하나만 (2026-10-19 사용자: 여러 키 · 프로젝트로 한도를 늘리는 건 약관 위반). 여럿 들어 있으면 첫 키만 쓰고 한 번 알린다."""
    global _WARNED_KEYS
    raw = os.environ.get("GEMINI_API_KEY", "")
    keys = [k.strip().strip('"') for k in re.split(r"[;,]", raw) if k.strip()]
    if len(keys) > 1 and not _WARNED_KEYS:
        _WARNED_KEYS = True
        print(f"[Gemini] GEMINI_API_KEY 에 키가 {len(keys)}개. 첫 키만 씁니다 (키 하나 원칙)")
    return keys[:1]


def _mask(key):
    """로그 · Slack 에 쓰는 키 이름 — 값은 앞자리도 내보내지 않는다 (2026-10-15 사용자: 키는 절대 노출 금지, 공개 리포라 로그도 공개)."""
    keys = gemini_keys()
    return f"#{keys.index(key) + 1}" if key in keys else "#?"


def _available(name):
    step = STEPS[name]
    return bool(gemini_keys()) if step["kind"] == "gemini" else bool(os.environ.get(step["env"], "").strip())


class LLMPool:
    def __init__(self, chain="json", label="llm", skip_when_day_out=None):
        self.chain = [s for s in CHAINS[chain] if _available(s)]
        # {하루 한도 단계: [건너뛸 단계]} — 그 단계가 하루 한도(_day_out)에 걸리면 같이 건너뛴다 (2026-10-28 인물 레이더:
        # gpt-oss TPD 소진 뒤 NVIDIA 가 연결 끊김으로 5/5 실패하며 45분 초과 → 바로 gemini-lite 로)
        self.skip_when_day_out = skip_when_day_out or {}
        if not self.chain:
            raise RuntimeError(f"[{label}] 사슬 '{chain}' 에 쓸 키가 하나도 없습니다 (GEMINI_API_KEY / GROQ_API_KEY / NVIDIA_API_KEY).")
        self.label = label
        self.model = STEPS[self.chain[0]]["model"]   # 주 모델 이름
        self.last_model = self.model
        self.calls = 0
        self.fallback_calls = 0
        self.rejected = []   # validate 에서 떨어진 답 [(단계, 값, 이유)] — 전부 실패했을 때 호출자가 고쳐 쓸 수 있게 (데일리)
        keys = gemini_keys()
        self._keys = keys
        self._cooldown_until = [0.0] * len(keys)
        self._next = 0
        print(f"[{label}] 사슬 {chain}: " + " → ".join(f"{s}({STEPS[s]['model']})" for s in self.chain)
              + (f" · Gemini 키 {len(keys)}개" if "gemini" in self.chain else ""))

    @property
    def first_step(self):
        """지금 먼저 시도될 단계 — 하루 한도로 빠진 단계는 건너뛴다. 배치 크기를 첫 모델에 맞추는 데 쓴다(news_store)."""
        return next((s for s in self.chain if s not in _day_out), None)

    # ---------------------------------------------------------------- Gemini
    def _pick_key(self, model):
        live = [i for i, k in enumerate(self._keys) if (k, model) not in _EXHAUSTED_KEYS]
        if not live:
            raise StepFailed("Gemini 하루 한도 소진 — 이번 실행은 건너뜀")
        now = time.time()
        n = len(self._keys)
        for offset in range(n):
            i = (self._next + offset) % n
            if i in live and self._cooldown_until[i] <= now:
                self._next = (i + 1) % n
                return i
        wait = min(self._cooldown_until[i] for i in live) - now
        if wait > KEY_COOLDOWN_SECONDS * 3:
            raise StepFailed("Gemini 모든 키 쿨다운")
        print(f"[{self.label}] Gemini 모든 키 쿨다운 — {wait:.0f}s 대기")
        time.sleep(max(wait, 1))
        return self._pick_key(model)

    def _gemini(self, step, prompt, temperature, max_tokens):
        gen = {"responseMimeType": "application/json"}
        if temperature is not None:
            gen["temperature"] = temperature
        if max_tokens:
            gen["maxOutputTokens"] = max_tokens
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen}
        last = ""
        minute_429 = 0
        attempts = step.get("attempts", GEMINI_ATTEMPTS)
        for attempt in range(1, attempts + 1):
            i = self._pick_key(step["model"])
            key = self._keys[i]
            try:
                r = requests.post(GEMINI_URL.format(model=step["model"]), params={"key": key}, json=body, timeout=step["timeout"])
            except requests.RequestException as e:
                last = f"네트워크: {str(e)[:120]}"
                wait = RETRY_SLEEP_SECONDS * (2 ** (attempt - 1))
                print(f"[{self.label}] Gemini {last} — {wait}s 뒤 재시도 ({attempt}/{attempts})")
                time.sleep(wait)
                continue
            if r.status_code == 429:
                # 본문의 quotaId 로 하루 한도와 분당 한도를 가른다 (…PerDay… / …PerMinute…)
                quota = (re.findall(r'"quotaId":\s*"([^"]+)"', r.text) or ["?"])[0]
                event("한도", f"Gemini 키 {_mask(key)} {quota} ({self.label})")
                if "PerDay" in r.text:
                    _EXHAUSTED_KEYS.add((key, step["model"]))
                    print(f"[{self.label}] Gemini 키 {_mask(key)} {step['model']} 하루 한도({quota}) → 이번 실행은 이 키로 이 모델을 쓰지 않음")
                    if all((k, step["model"]) in _EXHAUSTED_KEYS for k in self._keys):
                        raise StepFailed(f"Gemini 하루 한도 소진 ({quota})")
                    continue
                minute_429 += 1
                last = f"429 한도 ({quota})"
                if minute_429 > len(self._keys):   # 분당 한도는 키마다 한 번만 쉬고 다시 — 그래도 429 면 예비로
                    raise StepFailed(f"Gemini 분당 한도 반복 ({quota})")
                self._cooldown_until[i] = time.time() + KEY_COOLDOWN_SECONDS
                print(f"[{self.label}] Gemini 키 {_mask(key)} 분당 한도({quota}) → {KEY_COOLDOWN_SECONDS}s 휴식")
                continue
            if r.status_code in (500, 502, 503, 504):
                last = f"{r.status_code} 서버 과부하"
                wait = RETRY_SLEEP_SECONDS * (2 ** (attempt - 1))
                print(f"[{self.label}] Gemini {r.status_code} — {wait}s 뒤 재시도 ({attempt}/{attempts})")
                time.sleep(wait)
                continue
            if r.status_code != 200:
                last = f"{r.status_code}: {r.text[:160]}"
                print(f"[{self.label}] Gemini 키 {_mask(key)} {last}")
                time.sleep(RETRY_SLEEP_SECONDS)
                continue
            try:
                cand = r.json()["candidates"][0]
                text = "".join(p.get("text", "") for p in cand["content"]["parts"])
                return text
            except Exception as e:  # noqa: BLE001  — 안전 차단 등으로 본문이 없는 응답
                last = f"빈 응답: {str(e)[:80]} {r.text[:120]}"
                print(f"[{self.label}] Gemini {last}")
        raise StepFailed(f"Gemini {step['model']} {attempts}회 실패 · 마지막 {last}")

    # ---------------------------------------------------------------- OpenAI 호환
    def _openai(self, name, step, prompt, temperature, max_tokens):
        key = os.environ.get(step["env"], "").strip()
        slot = (step["url"], step["model"])
        gap = _ready_at.get(slot, 0) - time.time()
        if gap > 0:
            print(f"[{self.label}] {name} 분당 한도 간격 — {gap:.0f}s 대기")
            time.sleep(gap)
        body = {"model": step["model"], "messages": [{"role": "user", "content": prompt}]}
        if temperature is not None:
            body["temperature"] = temperature
        body.update(step.get("params", {}))
        if max_tokens:
            for k in ("max_tokens", "max_completion_tokens"):
                if k in body:
                    body[k] = min(max(body[k], max_tokens), step.get("otpm") or max_tokens)   # 출력 한도가 있는 모델은 그 위로 올리지 않는다
        for attempt in (1, 2):
            try:
                r = requests.post(step["url"], json=body, timeout=step["timeout"],
                                  headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"})
            except requests.RequestException as e:
                raise StepFailed(f"{name} 네트워크: {str(e)[:120]}")
            if r.status_code != 429 or attempt == 2:
                break
            # 분당 한도(TPM · OTPM)는 기다리면 풀린다 — 다른 워크플로가 같은 키로 막 쓴 경우 포함 (2026-10-26: 분류 Qwen 12번 중 11번이 이것으로 탈락)
            wait = _rate_wait(r)
            if wait is None or wait > RATE_RETRY_MAX_WAIT:
                break
            print(f"[{self.label}] {name} 429 {_groq_reason(r.text)} — {wait:.0f}s 뒤 한 번 더")
            time.sleep(wait)
        if r.status_code != 200:
            if r.status_code == 429 and "per day" in r.text:
                _day_out.add(name)
            raise StepFailed(f"{name} {r.status_code}: {_groq_reason(r.text)}")
        data = r.json()
        # 토큰을 실제로 쓴 호출만 간격 계산에 (401 · 413 같은 즉시 거절은 제외). 출력 한도가 있으면 쓴 출력만큼 더 쉰다
        out_tokens = (data.get("usage") or {}).get("completion_tokens") or 0
        _ready_at[slot] = time.time() + max(step.get("min_interval", 0), 60 * out_tokens / step["otpm"] if step.get("otpm") else 0)
        text = (data["choices"][0]["message"].get("content") or "").strip()
        if not text:
            raise StepFailed(f"{name}: 빈 응답 (사고 토큰이 출력 한도를 다 쓴 경우)")
        return text

    # ---------------------------------------------------------------- 사슬
    def generate_json(self, prompt, temperature=0.0, validate=None, max_tokens=None):
        """사슬을 차례로 → JSON 값. validate(value) 가 예외를 내면 그 단계는 실패로 보고 다음 단계로 (반환값이 있으면 그것을 쓴다)."""
        errors = []
        for n, name in enumerate(self.chain):
            step = STEPS[name]
            if name in _day_out:
                errors.append(f"{name}: 하루 한도 — 이번 실행은 건너뜀")
                continue
            tripped = next((t for t, skips in self.skip_when_day_out.items() if name in skips and t in _day_out), None)
            if tripped:
                errors.append(f"{name}: {tripped} 하루 한도 — 건너뜀")
                continue
            if n:
                kind = "대체" if step["kind"] == "gemini" else "예비"   # 같은 Gemini 의 다른 모델은 '대체' — Slack 에서 다른 공급자(예비)와 구분
                print(f"[{self.label}] {kind} → {name}({step['model']})")
                event(kind, f"{self.label} → {name}")
            try:
                text = (self._gemini(step, prompt, temperature, max_tokens) if step["kind"] == "gemini"
                        else self._openai(name, step, prompt, temperature, max_tokens))
                value = parse_json(text)
                if validate is not None:
                    try:
                        checked = validate(value)
                    except Exception as e:  # noqa: BLE001
                        self.rejected.append((name, value, str(e)))
                        event("검사 탈락", f"{self.label} {name}: {str(e)[:120]}")
                        raise
                    if checked is not None:
                        value = checked
            except Exception as e:  # noqa: BLE001
                USAGE[name]["fail"] += 1
                errors.append(f"{name}: {str(e)[:160]}")
                print(f"[{self.label}] {name} 실패 — {str(e)[:160]}")
                continue
            USAGE[name]["ok"] += 1
            self.calls += 1
            self.fallback_calls += n > 0
            self.last_model = step["model"] if step["kind"] == "gemini" else f"{name.split('-')[0]}:{step['model']}"
            return value
        event("전부 실패", f"{self.label}: " + " / ".join(errors)[:200])
        raise RuntimeError(f"[{self.label}] 사슬 전부 실패 · " + " / ".join(errors))


def usage_line():
    """이번 실행의 단계별 성공 · 실패 — 로그 마지막 줄용."""
    return " · ".join(f"{k} {v['ok']}/{v['ok'] + v['fail']}" for k, v in USAGE.items()) or "호출 없음"
