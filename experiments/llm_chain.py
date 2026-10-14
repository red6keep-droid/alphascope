"""모든 리포트가 같이 쓰는 LLM 호출 + 예비 사슬 (2026-10-14 사용자: "리포트를 더 많이 생산할 거야. 예비키들이 엄청 중요해" → "함께 옮겨").

예전에는 엔비디아 · 트럼프(gemini_client + backup_llm 사본), 댓글 봇, 홈 뉴스 번역, 미국 증시 리포트가 각자 호출 코드를
들고 있었고, 미국 증시 리포트에는 예비가 없었다. 이제 공급자를 더하거나 순서를 바꾸는 곳은 이 파일 하나다.

쓰는 법 (파이프라인 폴더에서 experiments/ 를 sys.path 에 넣고):
    from llm_chain import LLMPool
    pool = LLMPool("json")                       # 사슬 이름은 CHAINS
    value = pool.generate_json(prompt, temperature=0.2, validate=None)
    pool.last_model                              # 답한 모델 (예: "gemini-3.5-flash", "groq:openai/gpt-oss-120b")

사슬은 단계를 차례로 시도한다. 키가 없는 단계는 건너뛰고, 한 단계가 끝까지 실패하면(한도 · 서버 과부하 · 형식 오류 ·
validate 탈락 모두) 다음 단계로. 전부 실패하면 RuntimeError.

Gemini 는 REST 로 부른다 — 홈 뉴스 워크플로에는 google-genai 가 없다. 필요한 패키지는 requests 하나.
Gemini 키는 GEMINI_API_KEY 에 ; 또는 , 로 여럿 (2026-10-14 사용자: 키 5개 모두 다른 프로젝트 → 프로젝트당 하루 약 20회씩).
호출마다 다음 키로 돌고, 429 를 받은 키는 KEY_COOLDOWN_SECONDS 쉰다. 503/500 은 키 문제가 아니라 기다렸다 다시(3·6·12·24·48s).

모델 실측 (2026-10-11, NVDA 실제 분류 프롬프트 6건 · 20건, 서술 프롬프트):
- Groq gpt-oss-120b (사고 low): 분류 20건 6.5초, Gemini 라벨과 24필드 중 18~19 일치, 서술 검증 통과.
  무료 등급 분당 8,000토큰 → 다음 호출까지 60초 간격. 미국 증시 리포트처럼 긴 프롬프트(3만 자 넘음)는 413 으로 바로 다음 단계.
- NVIDIA DeepSeek V4.1 Flash (사고 끔): 18/24, 20건 배치 2분 안팎. 공용 엔드포인트라 지연이 들쭉날쭉(3초↔19분).
- NVIDIA gpt-oss-20b: 번역 5초 — 번역 전용 (분류는 전부 Other · 0 으로 탈락).
떨어진 후보: Mistral(Ministral 14B 14/24, Legal→Regulation 오분류, 서술에 없는 내용), Nemotron Super(빈 응답), GLM Flash(무응답), Gemma 4(504).
사고 모드는 켜도 라벨이 안 나아지고(low 18 → medium 19 → high 빈 응답) 서술은 길어져 검증 탈락 → 전부 low/끔.
새 공급자는 실제 프롬프트로 정확도를 비교한 뒤에만 STEPS · CHAINS 에 넣는다.
"""

import json
import os
import re
import time
from collections import defaultdict

import requests

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.5-flash"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
KEY_COOLDOWN_SECONDS = 60
GEMINI_ATTEMPTS = 5
RETRY_SLEEP_SECONDS = 3

# 공급자 단계. kind: gemini(REST, 다중 키) · openai(OpenAI 호환 REST)
STEPS = {
    "gemini": {"kind": "gemini", "env": "GEMINI_API_KEY", "model": GEMINI_MODEL, "timeout": 300},
    "groq": {"kind": "openai", "env": "GROQ_API_KEY", "url": "https://api.groq.com/openai/v1/chat/completions",
             "model": "openai/gpt-oss-120b", "min_interval": 60, "timeout": 120,
             "params": {"reasoning_effort": "low", "max_completion_tokens": 8000}},   # 분당 8,000토큰 → 호출 간격 60초
    "nvidia-deepseek": {"kind": "openai", "env": "NVIDIA_API_KEY", "url": "https://integrate.api.nvidia.com/v1/chat/completions",
                        "model": "deepseek-ai/deepseek-v4.1-flash", "timeout": 300,
                        "params": {"max_tokens": 8000, "chat_template_kwargs": {"thinking": False}}},   # 사고 끄기 — 켜면 답이 비거나 5분 초과
    "nvidia-gptoss20": {"kind": "openai", "env": "NVIDIA_API_KEY", "url": "https://integrate.api.nvidia.com/v1/chat/completions",
                        "model": "openai/gpt-oss-20b", "timeout": 90,
                        "params": {"reasoning_effort": "low", "max_tokens": 2000}},
}

# 용도별 순서
CHAINS = {
    "json": ["gemini", "groq", "nvidia-deepseek"],               # 분류 · 서술 · 리포트 · 댓글 답글
    "translate": ["groq", "nvidia-gptoss20", "gemini"],          # 홈 뉴스 제목 번역 — 빠른 것부터 (2026-10-11)
}

USAGE = defaultdict(lambda: {"ok": 0, "fail": 0})   # 단계 → 성공 · 실패 수 (이번 실행)
_last_call = {}   # OpenAI 호환 공급자 → 마지막 호출 시각 (분당 토큰 한도 간격용)


class StepFailed(RuntimeError):
    pass


def parse_json(text):
    """모델 응답에서 첫 JSON 값. ```json 울타리 · 앞뒤 말 · 값 뒤 덧붙인 글("Extra data")을 견딘다."""
    text = (text or "").strip()
    m = re.search(r"[\[{]", text)
    if not m:
        raise ValueError("JSON 시작 문자를 찾지 못했습니다.")
    value, _ = json.JSONDecoder().raw_decode(text[m.start():])
    return value


def gemini_keys():
    raw = os.environ.get("GEMINI_API_KEY", "")
    return [k.strip().strip('"') for k in re.split(r"[;,]", raw) if k.strip()]


def _mask(key):
    return key[:8] + "***" if len(key) > 8 else key[:3] + "***"


def _available(name):
    step = STEPS[name]
    return bool(gemini_keys()) if step["kind"] == "gemini" else bool(os.environ.get(step["env"], "").strip())


class LLMPool:
    def __init__(self, chain="json", label="llm"):
        self.chain = [s for s in CHAINS[chain] if _available(s)]
        if not self.chain:
            raise RuntimeError(f"[{label}] 사슬 '{chain}' 에 쓸 키가 하나도 없습니다 (GEMINI_API_KEY / GROQ_API_KEY / NVIDIA_API_KEY).")
        self.label = label
        self.model = STEPS[self.chain[0]]["model"]   # 주 모델 이름
        self.last_model = self.model
        self.calls = 0
        self.fallback_calls = 0
        keys = gemini_keys()
        self._keys = keys
        self._cooldown_until = [0.0] * len(keys)
        self._next = 0
        print(f"[{label}] 사슬 {chain}: " + " → ".join(f"{s}({STEPS[s]['model']})" for s in self.chain)
              + (f" · Gemini 키 {len(keys)}개" if "gemini" in self.chain else ""))

    # ---------------------------------------------------------------- Gemini
    def _pick_key(self):
        now = time.time()
        n = len(self._keys)
        for offset in range(n):
            i = (self._next + offset) % n
            if self._cooldown_until[i] <= now:
                self._next = (i + 1) % n
                return i
        wait = min(self._cooldown_until) - now
        if wait > KEY_COOLDOWN_SECONDS * 3:
            raise StepFailed("Gemini 모든 키 쿨다운")
        print(f"[{self.label}] Gemini 모든 키 쿨다운 — {wait:.0f}s 대기")
        time.sleep(max(wait, 1))
        return self._pick_key()

    def _gemini(self, step, prompt, temperature, max_tokens):
        gen = {"responseMimeType": "application/json"}
        if temperature is not None:
            gen["temperature"] = temperature
        if max_tokens:
            gen["maxOutputTokens"] = max_tokens
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen}
        last = ""
        for attempt in range(1, GEMINI_ATTEMPTS + 1):
            i = self._pick_key()
            key = self._keys[i]
            try:
                r = requests.post(GEMINI_URL.format(model=step["model"]), params={"key": key}, json=body, timeout=step["timeout"])
            except requests.RequestException as e:
                last = f"네트워크: {str(e)[:120]}"
                wait = RETRY_SLEEP_SECONDS * (2 ** (attempt - 1))
                print(f"[{self.label}] Gemini {last} — {wait}s 뒤 재시도 ({attempt}/{GEMINI_ATTEMPTS})")
                time.sleep(wait)
                continue
            if r.status_code == 429:
                self._cooldown_until[i] = time.time() + KEY_COOLDOWN_SECONDS
                last = "429 한도"
                print(f"[{self.label}] Gemini 키 {_mask(key)} 한도 → {KEY_COOLDOWN_SECONDS}s 휴식")
                continue
            if r.status_code in (500, 502, 503, 504):
                last = f"{r.status_code} 서버 과부하"
                wait = RETRY_SLEEP_SECONDS * (2 ** (attempt - 1))
                print(f"[{self.label}] Gemini {r.status_code} — {wait}s 뒤 재시도 ({attempt}/{GEMINI_ATTEMPTS})")
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
        raise StepFailed(f"Gemini {GEMINI_ATTEMPTS}회 실패 · 마지막 {last}")

    # ---------------------------------------------------------------- OpenAI 호환
    def _openai(self, name, step, prompt, temperature, max_tokens):
        key = os.environ.get(step["env"], "").strip()
        gap = step.get("min_interval", 0) - (time.time() - _last_call.get(step["url"], 0))
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
                    body[k] = max(body[k], max_tokens)
        try:
            r = requests.post(step["url"], json=body, timeout=step["timeout"],
                              headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"})
        except requests.RequestException as e:
            raise StepFailed(f"{name} 네트워크: {str(e)[:120]}")
        if r.status_code != 200:
            raise StepFailed(f"{name} {r.status_code}: {r.text[:160]}")
        _last_call[step["url"]] = time.time()   # 토큰을 실제로 쓴 호출만 간격 계산에 (401 · 413 같은 즉시 거절은 제외)
        text = (r.json()["choices"][0]["message"].get("content") or "").strip()
        if not text:
            raise StepFailed(f"{name}: 빈 응답 (사고 토큰이 출력 한도를 다 쓴 경우)")
        return text

    # ---------------------------------------------------------------- 사슬
    def generate_json(self, prompt, temperature=0.0, validate=None, max_tokens=None):
        """사슬을 차례로 → JSON 값. validate(value) 가 예외를 내면 그 단계는 실패로 보고 다음 단계로 (반환값이 있으면 그것을 쓴다)."""
        errors = []
        for n, name in enumerate(self.chain):
            step = STEPS[name]
            if n:
                print(f"[{self.label}] 예비 → {name}({step['model']})")
            try:
                text = (self._gemini(step, prompt, temperature, max_tokens) if step["kind"] == "gemini"
                        else self._openai(name, step, prompt, temperature, max_tokens))
                value = parse_json(text)
                if validate is not None:
                    checked = validate(value)
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
        raise RuntimeError(f"[{self.label}] 사슬 전부 실패 · " + " / ".join(errors))


def usage_line():
    """이번 실행의 단계별 성공 · 실패 — 로그 마지막 줄용."""
    return " · ".join(f"{k} {v['ok']}/{v['ok'] + v['fail']}" for k, v in USAGE.items()) or "호출 없음"
