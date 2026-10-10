"""Gemini 호출 — 여러 키 라운드로빈 + 429 쿨다운. trump-trend gemini_client.py 복사본 (2026-10-08, 동일).

기존 generate_report.py의 키 표기(`GEMINI_API_KEY="k1;k2"`)를 그대로 쓴다.
차이는 순차 전환이 아니라 호출마다 다음 키로 돌고, 한도에 걸린 키는 잠시 쉰다는 것.
모든 키가 같은 GEMINI_MODEL을 쓴다 — 라벨 일관성을 위해.

예비 (2026-10-11): 모든 키가 쿨다운이거나 한도로 끝까지 실패하면 backup_llm 사슬(Groq gpt-oss-120b → NVIDIA DeepSeek)로 넘긴다.
예비 키가 하나도 없으면 예전처럼 예외. 어느 모델이 답했는지는 last_model에 남는다 (ai_model 컬럼용).
"""

import json
import os
import re
import time

from google import genai
from google.genai import types

import config
import backup_llm


class AllKeysExhausted(RuntimeError):
    pass


def _parse_json(text):
    m = re.search(r"[\[{]", text)
    if not m:
        raise ValueError("JSON 시작 문자를 찾지 못했습니다.")
    end = max(text.rfind("}"), text.rfind("]"))
    try:
        return json.loads(text[m.start(): end + 1])
    except json.JSONDecodeError as e:
        # 모델이 JSON 값 뒤에 무언가를 더 붙인 경우("Extra data") — 첫 값만 취한다 (2026-10-08, nvda-report 배치 2에서 5회 연속)
        if "Extra data" not in str(e):
            raise
        value, _ = json.JSONDecoder().raw_decode(text[m.start():])
        return value


def _mask(key):
    return key[:8] + "***" if len(key) > 8 else key[:3] + "***"


def _is_rate_limit(err):
    s = str(err)
    return "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower()


def _is_transient(err):
    """503 UNAVAILABLE(수요 폭주)·500·타임아웃 — 키 문제가 아니므로 키를 쉬게 하지 않고 기다렸다 다시 친다."""
    s = str(err)
    return "503" in s or "UNAVAILABLE" in s or "500" in s or "timed out" in s.lower() or "DEADLINE" in s


class GeminiPool:
    def __init__(self, keys=None, model=None):
        raw = os.environ.get("GEMINI_API_KEY", "")
        keys = keys or [k.strip() for k in re.split(r"[;,]", raw) if k.strip()]
        if not keys:
            raise RuntimeError("GEMINI_API_KEY 환경 변수(또는 .env)가 필요합니다.")
        self.model = model or os.environ.get("GEMINI_MODEL", config.DEFAULT_MODEL)
        self._clients = [(k, genai.Client(api_key=k)) for k in keys]
        self._cooldown_until = [0.0] * len(keys)
        self._next = 0
        self.calls = 0
        self.last_model = self.model
        self.fallback_calls = 0
        print(f"[gemini] 키 {len(keys)}개 · model={self.model}" + (" · 예비 " + " → ".join(s["model"] for s in backup_llm.available()) if backup_llm.available() else " · 예비 없음"))

    def _pick(self):
        now = time.time()
        n = len(self._clients)
        for offset in range(n):
            i = (self._next + offset) % n
            if self._cooldown_until[i] <= now:
                self._next = (i + 1) % n
                return i
        wait = min(self._cooldown_until) - now
        if wait > config.KEY_COOLDOWN_SECONDS * 3:
            raise AllKeysExhausted("모든 키가 쿨다운 중입니다.")
        print(f"[gemini] 모든 키 쿨다운 — {wait:.0f}s 대기")
        time.sleep(max(wait, 1))
        return self._pick()

    def _fallback(self, prompt, temperature, reason):
        result, name = backup_llm.run_chain(prompt, temperature=temperature, reason=reason)
        self.calls += 1
        self.fallback_calls += 1
        self.last_model = name
        return result

    def generate_json(self, prompt, temperature=0.0):
        last_error = None
        for attempt in range(1, config.PER_BATCH_ATTEMPTS + 1):
            try:
                i = self._pick()
            except AllKeysExhausted:
                return self._fallback(prompt, temperature, "모든 키 쿨다운")
            key, client = self._clients[i]
            try:
                resp = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=temperature,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    ),
                )
                self.calls += 1
                self.last_model = self.model
                return _parse_json(resp.text)
            except Exception as e:  # noqa: BLE001
                last_error = e
                if _is_rate_limit(e):
                    self._cooldown_until[i] = time.time() + config.KEY_COOLDOWN_SECONDS
                    print(f"[gemini] 키 {_mask(key)} 한도 → {config.KEY_COOLDOWN_SECONDS}s 휴식")
                elif _is_transient(e):
                    wait = config.RETRY_SLEEP_SECONDS * (2 ** (attempt - 1))
                    print(f"[gemini] 일시 오류(503/500) 시도 {attempt}/{config.PER_BATCH_ATTEMPTS} — {wait}s 뒤 재시도")
                    time.sleep(wait)
                else:
                    print(f"[gemini] 키 {_mask(key)} 시도 {attempt} 실패: {str(e)[:200]}")
                    time.sleep(config.RETRY_SLEEP_SECONDS)
        if _is_rate_limit(last_error):
            return self._fallback(prompt, temperature, f"{config.PER_BATCH_ATTEMPTS}회 모두 한도")
        raise RuntimeError(f"Gemini 호출 실패 ({config.PER_BATCH_ATTEMPTS}회): {str(last_error)[:200]}")
