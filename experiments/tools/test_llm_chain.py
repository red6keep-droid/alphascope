# 2026-10-16 llm_chain 가짜 응답 시험 (네트워크 없음). 사용: python -I experiments/tools/test_llm_chain.py
"""llm_chain 가짜 응답 시험 — 네트워크 없이. 시나리오별로 호출 순서 · 대기 시간 · 답한 모델을 확인한다."""
import os
import sys
import time

sys.path.insert(0, "D:/Alpha-Scope.blogspot/experiments")
os.environ["GEMINI_API_KEY"] = "k-test"
os.environ["NVIDIA_API_KEY"] = "n-test"
os.environ["GROQ_API_KEY"] = ""
os.environ["SLACK_WEBHOOK_URL"] = ""
import llm_chain  # noqa: E402

CALLS = []
SLEPT = [0.0]
time.sleep = lambda s: SLEPT.__setitem__(0, SLEPT[0] + s)
QUEUE = {}   # model → list of (status, text)


class R:
    def __init__(self, status, text):
        self.status_code, self.text = status, text

    def json(self):
        import json
        return json.loads(self.text)


def fake_post(url, params=None, json=None, timeout=None, headers=None):
    model = url.split("/models/")[1].split(":")[0] if "/models/" in url else json["model"]
    CALLS.append(model)
    q = QUEUE.get(model) or [(200, OK_OPENAI if "deepseek" in model else OK)]
    status, text = q.pop(0) if len(q) > 1 else q[0]
    return R(status, text)


OK = '{"candidates":[{"content":{"parts":[{"text":"{\\"x\\": 1}"}]}}]}'
OK_OPENAI = '{"choices":[{"message":{"content":"{\\"x\\": 2}"}}]}'
E503 = '{"error":{"code":503,"status":"UNAVAILABLE"}}'
E429D = '{"error":{"code":429,"details":[{"violations":[{"quotaId":"GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}}'
llm_chain.requests.post = fake_post


def run(name, queue, chain="json"):
    CALLS.clear(); SLEPT[0] = 0; QUEUE.clear(); QUEUE.update(queue); llm_chain._EXHAUSTED_KEYS.clear()
    pool = llm_chain.LLMPool(chain, label="t")
    try:
        v = pool.generate_json("p")
        out = f"답 {v} · 모델 {pool.last_model}"
    except RuntimeError as e:
        out = f"실패: {str(e)[:80]}"
    print(f"--- {name}: {out}\n    호출 {CALLS} · 대기 {SLEPT[0]:.0f}s")
    return list(CALLS), SLEPT[0]


c, s = run("1 flash 503 계속 → lite", {"gemini-3.5-flash": [(503, E503)]})
assert c == ["gemini-3.5-flash"] * 2 + ["gemini-3.5-flash-lite"] and s == 9, (c, s)
c, s = run("2 flash 하루 한도 → lite 즉시", {"gemini-3.5-flash": [(429, E429D)]})
assert c == ["gemini-3.5-flash", "gemini-3.5-flash-lite"] and s == 0, (c, s)
# 같은 프로세스의 다음 풀 — flash 는 호출하지 않고 lite 로
CALLS.clear(); pool = llm_chain.LLMPool("json", label="t2"); pool.generate_json("p")
assert CALLS == ["gemini-3.5-flash-lite"], CALLS
print("    (다음 풀) 호출", CALLS)
c, s = run("3 flash · lite 둘 다 503 → DeepSeek", {"gemini-3.5-flash": [(503, E503)], "gemini-3.5-flash-lite": [(503, E503)]})
assert c == ["gemini-3.5-flash"] * 2 + ["gemini-3.5-flash-lite"] * 4 + ["deepseek-ai/deepseek-v4.1-flash"] and s == 9 + 45, (c, s)
c, s = run("4 json-gemini: 둘 다 실패 → 예비 없이 실패", {"gemini-3.5-flash": [(503, E503)], "gemini-3.5-flash-lite": [(429, E429D)]}, chain="json-gemini")
assert c == ["gemini-3.5-flash"] * 2 + ["gemini-3.5-flash-lite"], c
c, s = run("5 정상: flash 바로 성공", {})
assert c == ["gemini-3.5-flash"] and s == 0, (c, s)
c, s = run("6 flash 503 한 번 뒤 성공", {"gemini-3.5-flash": [(503, E503), (200, OK)]})
assert c == ["gemini-3.5-flash"] * 2 and s == 3, (c, s)
print("\n이벤트:", dict(llm_chain.EVENTS))
print("모두 통과")
