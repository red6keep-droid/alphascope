"""Gemini 예비 공급자 사슬 (OpenAI 호환 REST) — 2026-10-11 사용자: "무료 한도 초과·갑자기 막힘을 막게 2중 3중으로".

순서는 config.FALLBACK_CHAIN. 실측(2026-10-11, 실제 분류 프롬프트 6건·20건, 서술 프롬프트) 기준:
- Groq gpt-oss-120b (사고 low): 분류 20건 6.5초, Gemini 라벨과 24필드 중 18~19 일치, 서술 검증 통과.
  무료 등급 분당 8,000토큰 → 20건 배치(≈7,000)는 통과하지만 다음 호출까지 60초 간격이 필요.
- NVIDIA DeepSeek V4.1 Flash (사고 끔): 18/24, 20건 배치 2분 안팎. 공용 엔드포인트라 지연이 들쭉날쭉(같은 모델이 3초↔19분).
떨어진 후보: Mistral(Ministral 14B 14/24, Legal→Regulation 오분류, 서술에 없는 내용 지어냄 · Large/Medium/Small은 등급 밖),
  gpt-oss-20b(분류 전부 Other·0), Nemotron Super(빈 응답), GLM Flash(무응답), Gemma 4(504).
사고 모드는 켜도 라벨이 안 나아지고(low 18 → medium 19 → high 빈 응답) 서술은 길어져 검증 탈락 → 전부 low/끔.
"""

import json
import os
import re
import time

import requests

import config

PROVIDERS = {
    "groq":   {"url": "https://api.groq.com/openai/v1/chat/completions", "env": "GROQ_API_KEY"},
    "nvidia": {"url": "https://integrate.api.nvidia.com/v1/chat/completions", "env": "NVIDIA_API_KEY"},
}
_last_call = {}   # provider → 마지막 호출 시각 (분당 토큰 한도 간격용)


def api_key(provider):
    return os.environ.get(PROVIDERS[provider]["env"], "").strip()


def available():
    """키가 있는 사슬 단계만."""
    return [step for step in config.FALLBACK_CHAIN if api_key(step["provider"])]


def _parse_json(text):
    m = re.search(r"[\[{]", text)
    if not m:
        raise ValueError("JSON 시작 문자를 찾지 못했습니다.")
    value, _ = json.JSONDecoder().raw_decode(text[m.start():])
    return value


def chat_json(step, prompt, temperature=0.0):
    """사슬 한 단계로 프롬프트 하나 → JSON 값. 실패는 예외 (호출자가 다음 단계로)."""
    provider, model = step["provider"], step["model"]
    key = api_key(provider)
    if not key:
        raise RuntimeError(f"{PROVIDERS[provider]['env']} 없음")
    gap = step.get("min_interval", 0) - (time.time() - _last_call.get(provider, 0))
    if gap > 0:
        print(f"[backup] {provider} 분당 한도 간격 — {gap:.0f}s 대기")
        time.sleep(gap)
    body = {"model": model, "temperature": temperature, "messages": [{"role": "user", "content": prompt}]}
    body.update(step.get("params", {}))
    r = requests.post(PROVIDERS[provider]["url"], json=body, timeout=step.get("timeout", 300),
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"})
    if r.status_code != 200:
        raise RuntimeError(f"{provider} {model} {r.status_code}: {r.text[:160]}")
    _last_call[provider] = time.time()   # 토큰을 실제로 쓴 호출만 간격 계산에 넣는다 (401 같은 즉시 거절은 제외)
    content = (r.json()["choices"][0]["message"].get("content") or "").strip()
    if not content:
        raise RuntimeError(f"{provider} {model}: 빈 응답 (사고 토큰이 출력 한도를 다 쓴 경우)")
    return _parse_json(content)


def run_chain(prompt, temperature=0.0, reason=""):
    """사슬을 순서대로. 성공하면 (결과, 모델 이름). 전부 실패하면 RuntimeError."""
    steps = available()
    if not steps:
        raise RuntimeError(f"Gemini 실패 ({reason}) · 예비 키 없음 (GROQ_API_KEY / NVIDIA_API_KEY)")
    errors = []
    for step in steps:
        name = f"{step['provider']}:{step['model']}"
        print(f"[backup] {reason} → 예비 {name}")
        try:
            return chat_json(step, prompt, temperature), name
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {str(e)[:120]}")
            print(f"[backup] {name} 실패 — {str(e)[:120]}")
    raise RuntimeError("예비 전부 실패 · " + " / ".join(errors))
